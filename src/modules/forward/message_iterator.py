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
        actual_start_id, actual_end_id = None, None
        if self.channel_resolver:
            actual_start_id, actual_end_id = await self.channel_resolver.get_message_range(chat_id, start_id, end_id)
        else:
            actual_start_id, actual_end_id = start_id, end_id
        
        # 如果无法获取有效范围，则直接返回
        if actual_start_id is None or actual_end_id is None:
            _logger.error(f"无法获取有效的消息ID范围: chat_id={chat_id}, start_id={start_id}, end_id={end_id}")
            return
        
        # 计算需要获取的消息数量
        total_messages = actual_end_id - actual_start_id + 1
        _logger.info(f"开始获取消息: chat_id={chat_id}, 开始id={actual_start_id}, 结束id={actual_end_id}，共{total_messages}条消息")
        
        try:
            # 收集指定范围内的所有消息
            all_messages = []
            
            # 优化策略：使用更高效的方式获取消息
            # 1. 从较大的批次开始，逐步减小批次大小
            # 2. 跟踪已尝试获取的消息ID，避免重复尝试
            # 3. 设置最大尝试次数，防止无限循环
            
            # 创建要获取的消息ID列表，按从旧到新的顺序排序
            message_ids_to_fetch = list(range(actual_start_id, actual_end_id + 1))
            fetched_messages_map = {}  # 用于存储已获取的消息，键为消息ID
            
            # 每次批量获取的最大消息数量
            max_batch_size = 100
            
            # 获取消息的最大尝试次数，避免无限循环
            max_attempts = 2
            attempt_count = 0
            
            while message_ids_to_fetch and attempt_count < max_attempts:
                attempt_count += 1
                
                # 根据剩余消息数量确定当前批次大小
                batch_size = min(max_batch_size, len(message_ids_to_fetch))
                
                # 计算当前批次的offset_id，以获取小于此ID的消息
                # 由于Telegram API是获取"小于offset_id"的消息，需要加1
                current_offset_id = max(message_ids_to_fetch) + 1
                
                _logger.info(f"尝试获取消息批次 (第{attempt_count}次): chat_id={chat_id}, offset_id={current_offset_id}, 剩余未获取消息数={len(message_ids_to_fetch)}")
                
                # 记录此批次成功获取的消息数
                batch_success_count = 0
                
                # 获取一批消息
                async for message in self.client.get_chat_history(
                    chat_id=chat_id,
                    limit=batch_size,
                    offset_id=current_offset_id
                ):
                    # 检查消息ID是否在我们需要的范围内
                    if message.id in message_ids_to_fetch:
                        fetched_messages_map[message.id] = message
                        message_ids_to_fetch.remove(message.id)
                        batch_success_count += 1
                    
                    # 如果消息ID小于我们要获取的最小ID，可以停止这一批次的获取
                    if message.id < min(message_ids_to_fetch, default=actual_start_id):
                        _logger.debug(f"消息ID {message.id} 小于当前需要获取的最小ID {min(message_ids_to_fetch, default=actual_start_id)}，停止当前批次获取")
                        break
                
                _logger.info(f"已获取 {batch_success_count} 条消息，剩余 {len(message_ids_to_fetch)} 条消息待获取")
                
                # 如果此批次没有获取到任何消息，说明可能有些消息不存在或已被删除
                if batch_success_count == 0:
                    # 检查是否需要缩小获取范围，尝试一条一条地获取
                    if batch_size > 1:
                        _logger.info(f"未获取到任何消息，尝试减小批次大小")
                        max_batch_size = max(1, max_batch_size // 2)
                    else:
                        # 如果已经是最小批次大小，且仍未获取到消息，记录并移除前一部分消息ID
                        # 这些可能是不存在或已删除的消息
                        if message_ids_to_fetch:
                            ids_to_skip = message_ids_to_fetch[:min(10, len(message_ids_to_fetch))]
                            _logger.warning(f"无法获取以下消息ID，可能不存在或已被删除：{ids_to_skip}")
                            for id_to_skip in ids_to_skip:
                                message_ids_to_fetch.remove(id_to_skip)
                
                # 避免频繁请求，休眠一小段时间
                await asyncio.sleep(0.5)
            
            # 检查是否还有未获取的消息
            if message_ids_to_fetch:
                _logger.warning(f"以下消息ID无法获取，将被跳过：{message_ids_to_fetch}")
            
            # 将获取到的消息按ID升序排序（从旧到新）
            all_messages = [fetched_messages_map[msg_id] for msg_id in sorted(fetched_messages_map.keys())]
            _logger.info(f"消息获取完成，共获取{len(all_messages)}/{total_messages}条消息，已按ID升序排序（从旧到新）")
            
            # 逐个返回排序后的消息
            for message in all_messages:
                yield message
        
        except FloodWait as e:
            _logger.warning(f"获取消息时遇到限制，等待 {e.x} 秒")
            await asyncio.sleep(e.x)
        except Exception as e:
            _logger.error(f"获取消息失败: {e}")
            _logger.exception("详细错误信息：") 