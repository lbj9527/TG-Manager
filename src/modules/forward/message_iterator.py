"""
消息迭代器，用于从频道获取消息
"""

import asyncio
from typing import Union, Optional, List, AsyncGenerator

from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait

from src.utils.logger import get_logger

_logger = get_logger()

class MessageIterator:
    """
    消息迭代器，用于高效地获取频道消息
    """
    
    def __init__(self, client: Client, channel_resolver=None):
        """
        初始化消息迭代器
        
        Args:
            client: Pyrogram客户端实例
            channel_resolver: 频道解析器实例，用于获取消息ID范围
        """
        self.client = client
        self.channel_resolver = channel_resolver
    
    async def check_message_range(self, chat_id: Union[str, int], start_id: int, end_id: int) -> tuple[int, int]:
        """
        检查并调整消息ID范围，确保范围合理
        
        Args:
            chat_id: 频道ID
            start_id: 起始消息ID
            end_id: 结束消息ID
            
        Returns:
            tuple: (调整后的起始ID, 调整后的结束ID)
        """
        try:
            # 获取频道最新消息来确定消息ID上限
            async for message in self.client.get_chat_history(chat_id, limit=1):
                max_available_id = message.id
                _logger.info(f"频道 {chat_id} 最新消息ID: {max_available_id}")
                
                # 调整结束ID，不能超过最新消息ID
                if end_id == 0 or end_id > max_available_id:
                    end_id = max_available_id
                    _logger.info(f"结束ID已调整为最新消息ID: {end_id}")
                
                break
            else:
                _logger.warning(f"无法获取频道 {chat_id} 的最新消息")
                return start_id, end_id
            
            # 确保起始ID不大于结束ID
            if start_id > end_id:
                _logger.warning(f"起始ID {start_id} 大于结束ID {end_id}，已交换")
                start_id, end_id = end_id, start_id
            
            # 限制单次获取的消息数量，避免过大的范围
            max_range = 10000  # 最多一次获取10000条消息
            if end_id - start_id + 1 > max_range:
                _logger.warning(f"消息范围过大 ({end_id - start_id + 1} 条)，已限制为最多 {max_range} 条")
                end_id = start_id + max_range - 1
            
            return start_id, end_id
            
        except Exception as e:
            _logger.error(f"检查消息范围时出错: {e}")
            return start_id, end_id

    async def iter_messages(self, chat_id: Union[str, int], start_id: int = 0, end_id: int = 0) -> AsyncGenerator[Message, None]:
        """
        迭代获取频道消息，按从旧到新的顺序返回
        
        Args:
            chat_id: 频道ID
            start_id: 起始消息ID
            end_id: 结束消息ID
        
        Yields:
            Message: 消息对象，按照从旧到新的顺序
        """
        # 如果有channel_resolver，使用它获取有效的消息ID范围
        if self.channel_resolver:
            actual_start_id, actual_end_id = await self.channel_resolver.get_message_range(chat_id, start_id, end_id)
        else:
            # 使用内置的范围检查方法
            actual_start_id, actual_end_id = await self.check_message_range(chat_id, start_id, end_id)
        
        # 如果无法获取有效范围，则直接返回
        if actual_start_id is None or actual_end_id is None:
            _logger.error(f"无法获取有效的消息ID范围: chat_id={chat_id}, start_id={start_id}, end_id={end_id}")
            return
        
        # 计算需要获取的消息数量
        total_messages = actual_end_id - actual_start_id + 1
        _logger.info(f"开始获取消息: chat_id={chat_id}, 开始id={actual_start_id}, 结束id={actual_end_id}，共{total_messages}条消息")
        
        # 限流相关配置 - 平衡速度和稳定性
        batch_size = 30  # 适中的批次大小，平衡速度和稳定性
        base_delay = 2.0  # 适中的基础延迟时间
        max_delay = 120.0  # 增加最大延迟时间到2分钟
        retry_count = 0
        
        # 动态延迟调整因子
        flood_wait_count = 0  # 记录遇到限流的次数
        conservative_mode = False  # 极保守模式开关
        
        # 如果消息数量很大且预期会有限流，可以考虑启用极保守模式
        if total_messages > 2000:  # 提高阈值，只有超过2000条消息才启用保守模式
            _logger.info(f"消息数量很大({total_messages}条)，将采用保守的获取策略")
            base_delay = 4.0  # 适度增加到4秒
            batch_size = 20   # 减少到20个
        elif total_messages > 1000:
            _logger.info(f"消息数量较大({total_messages}条)，将采用适度保守的获取策略")
            base_delay = 3.0  # 适度增加到3秒
            batch_size = 25   # 减少到25个
        
        try:
            # 分批获取消息ID
            total_batches = (total_messages + batch_size - 1) // batch_size
            _logger.info(f"开始分批获取消息，总共{total_messages}个ID，每批{batch_size}个，批次间延迟{base_delay}秒")
            
            fetched_messages_map = {}
            failed_ids = []
            
            # 分批获取消息ID
            for batch_num, batch_start in enumerate(range(actual_start_id, actual_end_id + 1, batch_size), 1):
                batch_end = min(batch_start + batch_size - 1, actual_end_id)
                batch_ids = list(range(batch_start, batch_end + 1))
                
                _logger.info(f"获取消息批次: ID {batch_start}-{batch_end} (第{batch_num}/{total_batches}批)")
                
                retry_count = 0
                while retry_count < 3:
                    try:
                        # 使用get_messages按ID批量获取
                        messages = await self.client.get_messages(chat_id, batch_ids)
                        
                        # 处理获取到的消息
                        valid_count = 0
                        for message in messages:
                            if message and message.id in set(batch_ids):
                                fetched_messages_map[message.id] = message
                                valid_count += 1
                        
                        _logger.info(f"批次 {batch_start}-{batch_end} 完成，获取到 {valid_count} 条有效消息")
                        
                        # 重置重试计数和限流计数（批次成功）
                        retry_count = 0
                        
                        # 动态调整延迟：成功获取后可以稍微减少延迟
                        if flood_wait_count > 0:
                            base_delay = max(3.0, base_delay * 0.9)  # 略微减少延迟
                            flood_wait_count = max(0, flood_wait_count - 1)
                        
                        break  # 成功，跳出重试循环
                        
                    except FloodWait as e:
                        flood_wait_count += 1
                        wait_time = e.x
                        _logger.warning(f"遇到限流，需要等待 {wait_time} 秒后重试 (第{flood_wait_count}次限流)")
                        
                        # 动态调整策略：根据限流次数增加基础延迟
                        if flood_wait_count > 2:
                            base_delay = min(max_delay, base_delay * 1.5)
                            batch_size = max(5, batch_size // 2)  # 进一步减小批次大小
                            _logger.warning(f"频繁限流，调整参数: 批次大小={batch_size}, 基础延迟={base_delay}秒")
                        
                        await asyncio.sleep(wait_time)
                        retry_count += 1
                        
                    except Exception as e:
                        retry_count += 1
                        _logger.error(f"获取批次 {batch_start}-{batch_end} 时出错: {e}")
                        
                        if retry_count >= 3:
                            _logger.warning(f"批次获取失败次数过多，改为逐个获取")
                            # 改为逐个获取
                            for msg_id in batch_ids:
                                try:
                                    await asyncio.sleep(1.0)  # 逐个获取时的延迟
                                    message = await self.client.get_messages(chat_id, msg_id)
                                    if message and message.id == msg_id:
                                        fetched_messages_map[msg_id] = message
                                except FloodWait as fw:
                                    _logger.warning(f"逐个获取时遇到限流，等待 {fw.x} 秒")
                                    await asyncio.sleep(fw.x)
                                    try:
                                        message = await self.client.get_messages(chat_id, msg_id)
                                        if message and message.id == msg_id:
                                            fetched_messages_map[msg_id] = message
                                    except Exception as retry_e:
                                        _logger.debug(f"逐个获取消息 {msg_id} 失败: {retry_e}")
                                        failed_ids.append(msg_id)
                                except Exception as single_e:
                                    _logger.debug(f"逐个获取消息 {msg_id} 失败: {single_e}")
                                failed_ids.append(msg_id)
                            break  # 跳出重试循环
                        else:
                            # 重试当前批次
                            await asyncio.sleep(min(base_delay * retry_count, max_delay))
                
                # 批次间延迟，避免过于频繁的请求
                if batch_num < total_batches:
                    _logger.debug(f"等待 {base_delay} 秒后继续下一批次...")
                    await asyncio.sleep(base_delay)
            
            # 检查获取结果
            fetched_count = len(fetched_messages_map)
            missing_count = total_messages - fetched_count
            
            if missing_count > 0:
                missing_ids = [msg_id for msg_id in range(actual_start_id, actual_end_id + 1) if msg_id not in fetched_messages_map]
                _logger.warning(f"有 {missing_count} 条消息无法获取，可能已被删除或不存在")
                _logger.debug(f"无法获取的消息ID示例: {missing_ids[:10]}{'...' if len(missing_ids) > 10 else ''}")
            
            _logger.info(f"消息获取完成，共获取 {fetched_count}/{total_messages} 条消息，成功率: {fetched_count/total_messages*100:.1f}%")
            
            # 按ID升序返回消息（从旧到新）
            for msg_id in sorted(fetched_messages_map.keys()):
                yield fetched_messages_map[msg_id]
        
        except FloodWait as e:
            _logger.warning(f"获取消息时遇到限制，等待 {e.x} 秒")
            await asyncio.sleep(e.x)
        except Exception as e:
            _logger.error(f"获取消息失败: {e}")
            _logger.exception("详细错误信息：") 