"""
转发模块，负责将消息从源频道转发到目标频道
"""

import os
import time
import asyncio
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Union, Any, Optional, Tuple, Set, NamedTuple
from queue import Queue
from dataclasses import dataclass
import re

from pyrogram import Client
from pyrogram.types import Message, InputMediaPhoto, InputMediaVideo, InputMediaDocument, InputMediaAudio
from pyrogram.errors import FloodWait, ChatForwardsRestricted, ChannelPrivate

from src.utils.config_manager import ConfigManager
from src.utils.channel_resolver import ChannelResolver
from src.utils.history_manager import HistoryManager
from src.modules.downloader import Downloader
from src.modules.uploader import Uploader
from src.utils.logger import get_logger
from src.utils.video_processor import VideoProcessor

logger = get_logger()

@dataclass
class MediaGroupDownload:
    """媒体组下载结果"""
    source_channel: str
    source_id: int
    messages: List[Message]
    download_dir: Path
    downloaded_files: List[Tuple[Path, str]]
    caption: Optional[str] = None

class Forwarder:
    """
    转发模块，负责将消息从源频道转发到目标频道
    """
    
    def __init__(self, client: Client, config_manager: ConfigManager, channel_resolver: ChannelResolver, history_manager: HistoryManager, downloader: Downloader, uploader: Uploader):
        """
        初始化转发模块
        
        Args:
            client: Pyrogram客户端实例
            config_manager: 配置管理器实例
            channel_resolver: 频道解析器实例
            history_manager: 历史记录管理器实例
            downloader: 下载模块实例
            uploader: 上传模块实例
        """
        self.client = client
        self.config_manager = config_manager
        self.channel_resolver = channel_resolver
        self.history_manager = history_manager
        self.downloader = downloader
        self.uploader = uploader
        
        # 获取转发配置
        self.forward_config = self.config_manager.get_forward_config()
        self.general_config = self.config_manager.get_general_config()
        
        # 创建临时目录
        self.tmp_path = Path(self.forward_config.tmp_path)
        self.tmp_path.mkdir(exist_ok=True)
        
        # 创建下载完成的媒体组队列
        self.media_group_queue = asyncio.Queue()
        
        # 生产者-消费者控制
        self.download_running = False
        self.upload_running = False
        self.producer_task = None
        self.consumer_task = None
        
        # 初始化视频处理器
        self.video_processor = VideoProcessor()
    
    async def forward_messages(self):
        """
        从源频道转发消息到目标频道
        """
        logger.info("开始转发消息")
        
        # 获取频道对列表
        channel_pairs = self.forward_config.forward_channel_pairs
        logger.info(f"配置的频道对数量: {len(channel_pairs)}")
        
        # 转发计数
        forward_count = 0
        
        # 处理每个频道对
        for pair in channel_pairs:
            source_channel = pair.source_channel
            target_channels = pair.target_channels
            
            if not target_channels:
                logger.warning(f"源频道 {source_channel} 没有配置目标频道，跳过")
                continue
            
            logger.info(f"准备从 {source_channel} 转发到 {len(target_channels)} 个目标频道")
            
            try:
                # 解析源频道ID
                source_id = await self.channel_resolver.get_channel_id(source_channel)
                source_info_str, (source_title, _) = await self.channel_resolver.format_channel_info(source_id)
                logger.info(f"源频道: {source_info_str}")
                
                # 检查源频道转发权限
                source_can_forward = await self.channel_resolver.check_forward_permission(source_id)
                logger.info(f"源频道转发权限: {source_can_forward}")
                
                # 获取有效的目标频道
                valid_target_channels = []
                for target in target_channels:
                    try:
                        target_id = await self.channel_resolver.get_channel_id(target)
                        target_info_str, (target_title, _) = await self.channel_resolver.format_channel_info(target_id)
                        valid_target_channels.append((target, target_id, target_info_str))
                    except Exception as e:
                        logger.error(f"解析目标频道 {target} 失败: {e}")
                
                if not valid_target_channels:
                    logger.warning(f"源频道 {source_channel} 没有有效的目标频道，跳过")
                    continue
                
                if source_can_forward:
                    # 源频道允许转发，直接使用转发功能
                    # 获取媒体组和消息
                    media_groups = await self._get_media_groups(source_id)
                    
                    # 处理每个媒体组
                    for group_id, messages in media_groups.items():
                        # 检查是否全部已转发
                        all_forwarded = True
                        for message in messages:
                            for target, _, _ in valid_target_channels:
                                if not self.history_manager.is_message_forwarded(source_channel, message.id, target):
                                    all_forwarded = False
                                    break
                            if not all_forwarded:
                                break
                        
                        if all_forwarded:
                            logger.debug(f"媒体组 {group_id} 已转发到所有目标频道，跳过")
                            continue
                        
                        # 检查是否达到限制
                        if self.general_config.limit > 0 and forward_count >= self.general_config.limit:
                            logger.info(f"已达到转发限制 {self.general_config.limit}，暂停 {self.general_config.pause_time} 秒")
                            await asyncio.sleep(self.general_config.pause_time)
                            forward_count = 0
                        
                        # 直接转发
                        await self._forward_media_group_directly(messages, source_channel, source_id, valid_target_channels)
                        
                        forward_count += 1
                        
                        # 转发延迟
                        await asyncio.sleep(self.forward_config.forward_delay)
                else:
                    # 源频道禁止转发，使用生产者-消费者模式下载后上传
                    logger.info("源频道禁止转发，使用下载后上传的方式")
                    
                    # 创建临时目录
                    temp_dir = self.tmp_path / f"forward_{source_id}_{int(time.time())}"
                    temp_dir.mkdir(exist_ok=True)
                    
                    try:
                        # 启动生产者-消费者模式处理
                        await self._process_parallel_download_upload(
                            source_channel, 
                            source_id, 
                            temp_dir, 
                            valid_target_channels
                        )
                    except Exception as e:
                        logger.error(f"并行下载上传处理失败: {e}")
                    finally:
                        # 清理临时文件
                        try:
                            shutil.rmtree(temp_dir)
                            logger.debug(f"清理临时目录: {temp_dir}")
                        except Exception as e:
                            logger.error(f"清理临时目录失败: {e}")
            
            except Exception as e:
                logger.error(f"转发频道 {source_channel} 的消息失败: {e}")
                continue
        
        logger.info("转发消息完成")

    async def _process_parallel_download_upload(self, 
                                          source_channel: str, 
                                          source_id: int, 
                                          temp_dir: Path, 
                                          target_channels: List[Tuple[str, int, str]]):
        """
        使用真正的并行处理模式下载和上传媒体组
        
        Args:
            source_channel: 源频道标识符
            source_id: 源频道ID
            temp_dir: 临时下载目录
            target_channels: 目标频道列表
        """
        # 重置队列和状态
        self.media_group_queue = asyncio.Queue()
        self.download_running = True
        self.upload_running = True
        
        # 获取媒体组ID列表，但不立即下载内容
        media_groups_info = await self._get_media_groups_info(source_id)
        logger.info(f"找到 {len(media_groups_info)} 个媒体组需要处理")
        
        if not media_groups_info:
            logger.info("没有媒体组需要处理")
            return
        
        # 创建生产者和消费者任务
        self.producer_task = asyncio.create_task(
            self._producer_download_media_groups_parallel(
                source_channel, source_id, media_groups_info, temp_dir, target_channels
            )
        )
        
        self.consumer_task = asyncio.create_task(
            self._consumer_upload_media_groups(target_channels)
        )
        
        # 等待任务完成
        try:
            # 等待生产者完成
            await self.producer_task
            logger.info("生产者(下载)任务完成")
            
            # 发送结束信号
            await self.media_group_queue.put(None)
            
            # 等待消费者完成
            await self.consumer_task
            logger.info("消费者(上传)任务完成")
            
            # 检查临时目录是否为空，如果不为空，可能有一些媒体组未能成功上传
            if any(temp_dir.iterdir()):
                logger.warning(f"临时目录 {temp_dir} 中仍有文件，可能有部分媒体组未能成功上传")
        except Exception as e:
            logger.error(f"并行处理出错: {str(e)}")
            # 取消任务
            if not self.producer_task.done():
                self.producer_task.cancel()
            if not self.consumer_task.done():
                self.consumer_task.cancel()
            raise

    async def _get_media_groups_info(self, source_id: int) -> List[Tuple[str, List[int]]]:
        """
        获取源频道的媒体组基本信息（不下载内容）
        
        Args:
            source_id: 源频道ID
            
        Returns:
            List[Tuple[str, List[int]]]: 媒体组ID与消息ID列表的映射
        """
        media_groups_info = []
        media_groups: Dict[str, List[int]] = {}
        
        # 设置消息范围
        start_id = self.forward_config.start_id
        end_id = self.forward_config.end_id
        
        # 获取消息基本信息
        async for message in self._iter_messages(source_id, start_id, end_id):
            # 筛选媒体类型
            if not self._is_media_allowed(message):
                continue
            
            # 获取媒体组ID
            group_id = message.media_group_id if message.media_group_id else f"single_{message.id}"
            
            # 添加到媒体组信息
            if group_id not in media_groups:
                media_groups[group_id] = []
            
            media_groups[group_id].append(message.id)
        
        # 转换为列表格式，便于顺序处理
        for group_id, message_ids in media_groups.items():
            # 按消息ID排序
            message_ids.sort()
            media_groups_info.append((group_id, message_ids))
        
        # 按第一个消息ID排序，确保从旧到新处理
        media_groups_info.sort(key=lambda x: x[1][0] if x[1] else 0)
        
        return media_groups_info

    async def _producer_download_media_groups_parallel(self, 
                                                 source_channel: str, 
                                                 source_id: int, 
                                                 media_groups_info: List[Tuple[str, List[int]]], 
                                                 temp_dir: Path,
                                                 target_channels: List[Tuple[str, int, str]]):
        """
        生产者：并行下载媒体组
        
        Args:
            source_channel: 源频道标识符
            source_id: 源频道ID
            media_groups_info: 媒体组信息列表[(group_id, [message_ids])]
            temp_dir: 临时下载目录
            target_channels: 目标频道列表，用于检查是否已转发
        """
        try:
            forward_count = 0
            
            for group_id, message_ids in media_groups_info:
                try:
                    # 检查是否已全部转发
                    all_forwarded = True
                    forwarded_targets = []
                    not_forwarded_targets = []
                    
                    for target_channel, target_id, target_info in target_channels:
                        target_all_forwarded = True
                        for message_id in message_ids:
                            if not self.history_manager.is_message_forwarded(source_channel, message_id, target_channel):
                                target_all_forwarded = False
                                all_forwarded = False
                                break
                        
                        if target_all_forwarded:
                            forwarded_targets.append(target_info)
                        else:
                            not_forwarded_targets.append(target_info)
                    
                    if all_forwarded:
                        logger.info(f"媒体组 {group_id} (消息IDs: {message_ids}) 已转发到所有目标频道，跳过")
                        continue
                    elif forwarded_targets:
                        logger.info(f"媒体组 {group_id} (消息IDs: {message_ids}) 已部分转发: 已转发到 {forwarded_targets}, 未转发到 {not_forwarded_targets}")
                    
                    # 检查是否达到限制
                    if self.general_config.limit > 0 and forward_count >= self.general_config.limit:
                        logger.info(f"已达到转发限制 {self.general_config.limit}，暂停 {self.general_config.pause_time} 秒")
                        await asyncio.sleep(self.general_config.pause_time)
                        forward_count = 0
                    
                    # 为每个媒体组创建安全的目录名
                    # 将媒体组ID转为字符串，并替换可能的非法路径字符
                    safe_group_id = str(group_id).replace('/', '_').replace('\\', '_').replace(':', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_')
                    
                    # 为每个媒体组创建单独的下载目录
                    group_dir = temp_dir / safe_group_id
                    group_dir.mkdir(exist_ok=True)
                    
                    # 获取完整消息对象
                    messages = []
                    for message_id in message_ids:
                        try:
                            message = await self.client.get_messages(source_id, message_id)
                            if message:
                                messages.append(message)
                        except Exception as e:
                            logger.error(f"获取消息 {message_id} 失败: {e}")
                    
                    if not messages:
                        logger.warning(f"媒体组 {group_id} 没有获取到有效消息，跳过")
                        continue
                    
                    # 下载媒体文件
                    downloaded_files = await self._download_messages(messages, group_dir, source_id)
                    if not downloaded_files:
                        logger.warning(f"媒体组 {group_id} 没有媒体文件可下载，跳过")
                        continue
                    
                    # 获取消息文本
                    caption = None
                    for message in messages:
                        if message.caption or message.text:
                            caption = message.caption or message.text
                            break
                    
                    # 移除原始标题
                    if self.forward_config.remove_captions:
                        caption = None
                    
                    # 创建媒体组下载结果对象
                    media_group_download = MediaGroupDownload(
                        source_channel=source_channel,
                        source_id=source_id,
                        messages=messages,
                        download_dir=group_dir,
                        downloaded_files=downloaded_files,
                        caption=caption
                    )
                    
                    # 将下载完成的媒体组放入队列
                    logger.info(f"媒体组 {group_id} 下载完成，放入上传队列: 消息IDs={[m.id for m in messages]}")
                    await self.media_group_queue.put(media_group_download)
                    
                    forward_count += 1
                    
                    # 添加适当的延迟，避免API限制
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"处理媒体组 {group_id} 失败: {str(e)}")
                    continue
        except Exception as e:
            logger.error(f"生产者并行下载任务异常: {str(e)}")
        finally:
            self.download_running = False
            logger.info("生产者(下载)任务结束")
    
    async def _get_media_groups(self, source_id: int) -> Dict[str, List[Message]]:
        """
        获取源频道的媒体组消息
        
        Args:
            source_id: 源频道ID
            
        Returns:
            Dict[str, List[Message]]: 媒体组ID与消息列表的映射
        """
        media_groups: Dict[str, List[Message]] = {}
        
        # 设置消息范围
        start_id = self.forward_config.start_id
        end_id = self.forward_config.end_id
        
        # 获取消息
        async for message in self._iter_messages(source_id, start_id, end_id):
            # 筛选媒体类型
            if not self._is_media_allowed(message):
                continue
            
            # 获取媒体组ID
            group_id = message.media_group_id if message.media_group_id else f"single_{message.id}"
            
            # 添加到媒体组
            if group_id not in media_groups:
                media_groups[group_id] = []
            
            media_groups[group_id].append(message)
        
        # 按消息ID排序每个媒体组内的消息
        for group_id in media_groups:
            media_groups[group_id].sort(key=lambda x: x.id)
        
        return media_groups
    
    async def _iter_messages(self, chat_id: Union[str, int], start_id: int = 0, end_id: int = 0):
        """
        迭代获取频道消息，按从旧到新的顺序返回
        
        Args:
            chat_id: 频道ID
            start_id: 起始消息ID
            end_id: 结束消息ID
        
        Yields:
            Message: 消息对象，按照从旧到新的顺序
        """
        # 使用channel_resolver获取有效的消息ID范围
        actual_start_id, actual_end_id = await self.channel_resolver.get_message_range(chat_id, start_id, end_id)
        
        # 如果无法获取有效范围，则直接返回
        if actual_start_id is None or actual_end_id is None:
            logger.error(f"无法获取有效的消息ID范围: chat_id={chat_id}, start_id={start_id}, end_id={end_id}")
            return
        
        # 计算需要获取的消息数量
        total_messages = actual_end_id - actual_start_id + 1
        logger.info(f"开始获取消息: chat_id={chat_id}, 开始id={actual_start_id}, 结束id={actual_end_id}，共{total_messages}条消息")
        
        # Telegram的get_chat_history按消息ID降序返回（从新到旧）
        # 我们需要先收集所有消息，然后按照ID升序排序，以便按照从旧到新的顺序处理
        
        try:
            # 收集指定范围内的所有消息
            all_messages = []
            offset_id = actual_end_id + 1
            fetched_count = 0
            
            while fetched_count < total_messages:
                limit = min(100, total_messages - fetched_count)  # 最多获取100条，但不超过剩余所需数量
                
                batch_count = 0
                batch_messages = []
                
                # 获取一批消息
                async for message in self.client.get_chat_history(
                    chat_id=chat_id,
                    limit=limit,  # 限制每批次的消息数量
                    offset_id=offset_id  # 获取ID小于此值的消息
                ):
                    batch_count += 1
                    
                    # 只处理在范围内的消息
                    if message.id >= actual_start_id and message.id <= actual_end_id:
                        fetched_count += 1
                        batch_messages.append(message)
                    
                    # 更新下一轮请求的offset_id
                    offset_id = message.id
                    
                    # 如果已经达到或低于开始ID，则停止获取
                    if message.id < actual_start_id:
                        logger.info(f"已达到最小ID {actual_start_id}，停止获取")
                        break
                
                # 将这批消息添加到总消息列表
                all_messages.extend(batch_messages)
                logger.info(f"获取消息批次: chat_id={chat_id}, offset_id={offset_id}, limit={limit}, 已获取={fetched_count}/{total_messages}")
                
                # 如果这批次没有获取到任何消息，则退出循环
                if batch_count == 0:
                    logger.info("没有更多消息可获取")
                    break
                
                # 避免频繁请求
                await asyncio.sleep(0.5)
            
            # 按消息ID升序排序（从旧到新）
            all_messages.sort(key=lambda x: x.id)
            logger.info(f"消息获取完成，共获取{len(all_messages)}条消息，已按ID升序排序（从旧到新）")
            
            # 逐个返回排序后的消息
            for message in all_messages:
                yield message
        
        except FloodWait as e:
            logger.warning(f"获取消息时遇到限制，等待 {e.x} 秒")
            await asyncio.sleep(e.x)
        except Exception as e:
            logger.error(f"获取消息失败: {e}")
    
    def _is_media_allowed(self, message: Message) -> bool:
        """
        检查消息媒体类型是否在允许列表中
        
        Args:
            message: 消息对象
            
        Returns:
            bool: 是否允许
        """
        media_types = self.forward_config.media_types
        
        if message.photo and "photo" in media_types:
            return True
        elif message.video and "video" in media_types:
            return True
        elif message.document and "document" in media_types:
            return True
        elif message.audio and "audio" in media_types:
            return True
        elif message.animation and "animation" in media_types:
            return True
        elif (message.text or message.caption) and "text" in media_types:
            return True
        
        return False
    
    async def _forward_media_group_directly(self, messages: List[Message], source_channel: str, source_id: int, 
                                          target_channels: List[Tuple[str, int, str]]):
        """
        直接转发媒体组到目标频道
        
        Args:
            messages: 消息列表
            source_channel: 源频道标识符
            source_id: 源频道ID
            target_channels: 目标频道列表(频道标识符, 频道ID, 频道信息)
        """
        # 检查是否是单条消息
        is_single = len(messages) == 1
        
        # 获取是否隐藏作者配置
        hide_author = self.forward_config.hide_author
        
        for target_channel, target_id, target_info in target_channels:
            # 检查是否已转发到此频道
            all_forwarded = True
            for message in messages:
                if not self.history_manager.is_message_forwarded(source_channel, message.id, target_channel):
                    all_forwarded = False
                    break
            
            if all_forwarded:
                logger.debug(f"消息已转发到频道 {target_info}，跳过")
                continue
            
            try:
                logger.info(f"转发消息到频道 {target_info}")
                
                if is_single:
                    # 单条消息转发
                    message = messages[0]
                    
                    try:
                        if hide_author:
                            # 使用copy_message隐藏作者
                            logger.debug(f"使用copy_message方法隐藏作者转发消息 {message.id}")
                            forwarded = await self.client.copy_message(
                                chat_id=target_id,
                                from_chat_id=source_id,
                                message_id=message.id
                            )
                        else:
                            # 使用forward_messages保留作者信息
                            logger.debug(f"使用forward_messages方法保留作者转发消息 {message.id}")
                            forwarded = await self.client.forward_messages(
                                chat_id=target_id,
                                from_chat_id=source_id,
                                message_ids=message.id,
                                disable_notification=True
                            )
                        
                        # 转发成功后才记录历史
                        self.history_manager.add_forward_record(
                            source_channel,
                            message.id,
                            target_channel,
                            source_id
                        )
                        
                        logger.info(f"消息 {message.id} 转发到 {target_info} 成功")
                    except Exception as e:
                        logger.error(f"转发单条消息 {message.id} 到 {target_info} 失败: {e}，跳过")
                        continue
                else:
                    # 媒体组转发
                    message_ids = [msg.id for msg in messages]
                    
                    try:
                        if hide_author:
                            # 使用copy_media_group方法一次性转发整个媒体组
                            logger.debug(f"使用copy_media_group方法隐藏作者转发媒体组消息")
                            # 只需要第一条消息的ID，因为copy_media_group会自动获取同一组的所有消息
                            first_message_id = message_ids[0]
                            forwarded = await self.client.copy_media_group(
                                chat_id=target_id,
                                from_chat_id=source_id,
                                message_id=first_message_id
                            )
                        else:
                            # 使用forward_messages批量转发
                            logger.debug(f"使用forward_messages方法保留作者批量转发媒体组消息")
                            forwarded = await self.client.forward_messages(
                                chat_id=target_id,
                                from_chat_id=source_id,
                                message_ids=message_ids,
                                disable_notification=True
                            )
                        
                        # 转发成功后才记录历史
                        for message in messages:
                            self.history_manager.add_forward_record(
                                source_channel,
                                message.id,
                                target_channel,
                                source_id
                            )
                        
                        logger.info(f"媒体组 {message_ids} 转发到 {target_info} 成功")
                    except Exception as e:
                        logger.error(f"转发媒体组 {message_ids} 到 {target_info} 失败: {e}，跳过")
                        continue
                
                # 转发延迟
                await asyncio.sleep(1)
            
            except FloodWait as e:
                logger.warning(f"转发消息时遇到限制，等待 {e.x} 秒")
                await asyncio.sleep(e.x)
                await self._forward_media_group_directly(messages, source_channel, source_id, [(target_channel, target_id, target_info)])
            
            except Exception as e:
                logger.error(f"转发消息到频道 {target_info} 失败: {e}")
                continue
    
    async def _consumer_upload_media_groups(self, target_channels: List[Tuple[str, int, str]]):
        """
        消费者：上传媒体组到目标频道
        
        Args:
            target_channels: 目标频道列表(频道标识符, 频道ID, 频道信息)
        """
        try:
            while True:
                # 从队列获取下一个媒体组
                media_group_download = await self.media_group_queue.get()
                
                # 检查是否结束信号
                if media_group_download is None:
                    logger.info("收到结束信号，消费者准备退出")
                    break
                
                try:
                    # 记录媒体组的目录，以便上传后删除
                    media_group_dir = media_group_download.download_dir
                    message_ids = [m.id for m in media_group_download.messages]
                    source_channel = media_group_download.source_channel
                    
                    # 记录媒体组信息
                    group_id = "单条消息" if len(message_ids) == 1 else f"媒体组(共{len(message_ids)}条)"
                    logger.info(f"开始处理{group_id}: 消息IDs={message_ids}, 来源={source_channel}")
                    
                    # 提前检查哪些频道已经转发过
                    forwarded_targets = []
                    not_forwarded_targets = []
                    
                    for target_channel, _, target_info in target_channels:
                        all_forwarded = True
                        for message in media_group_download.messages:
                            if not self.history_manager.is_message_forwarded(media_group_download.source_channel, message.id, target_channel):
                                all_forwarded = False
                                break
                        
                        if all_forwarded:
                            forwarded_targets.append(target_info)
                        else:
                            not_forwarded_targets.append(target_info)
                    
                    if forwarded_targets:
                        logger.info(f"{group_id} {message_ids} 已转发到: {forwarded_targets}")
                    
                    if not not_forwarded_targets:
                        logger.info(f"{group_id} {message_ids} 已转发到所有目标频道，跳过上传")
                        # 清理已全部转发的媒体组目录
                        if media_group_dir.exists():
                            try:
                                shutil.rmtree(media_group_dir)
                                logger.debug(f"删除已全部转发的媒体组目录: {media_group_dir}")
                            except Exception as e:
                                logger.error(f"删除媒体组目录失败: {str(e)}")
                        self.media_group_queue.task_done()
                        continue
                    
                    # 为视频文件生成缩略图
                    thumbnails = {}
                    for file_path, media_type in media_group_download.downloaded_files:
                        if media_type == "video":
                            thumbnail_path = self.video_processor.extract_thumbnail(str(file_path))
                            if thumbnail_path:
                                thumbnails[str(file_path)] = thumbnail_path
                    
                    # 创建媒体组
                    media_group = []
                    for file_path, media_type in media_group_download.downloaded_files:
                        # 确保文件路径是字符串类型
                        file_path_str = str(file_path)
                        
                        # 检查文件是否存在
                        if not os.path.exists(file_path_str):
                            logger.warning(f"文件不存在，跳过: {file_path_str}")
                            continue
                            
                        # 只有第一个媒体添加标题
                        file_caption = media_group_download.caption if media_group_download.caption and len(media_group) == 0 else ""
                        
                        if media_type == "photo":
                            media_group.append(InputMediaPhoto(file_path_str, caption=file_caption))
                        elif media_type == "video":
                            # 获取缩略图路径
                            thumb = thumbnails.get(file_path_str)
                            media_group.append(InputMediaVideo(
                                file_path_str, 
                                caption=file_caption, 
                                supports_streaming=True,
                                thumb=thumb
                            ))
                        elif media_type == "document":
                            media_group.append(InputMediaDocument(file_path_str, caption=file_caption))
                        elif media_type == "audio":
                            media_group.append(InputMediaAudio(file_path_str, caption=file_caption))
                    
                    if not media_group:
                        logger.warning("没有有效的媒体文件可上传，跳过这个媒体组")
                        # 清理空目录
                        if media_group_dir.exists():
                            try:
                                shutil.rmtree(media_group_dir)
                                logger.debug(f"删除空媒体组目录: {media_group_dir}")
                            except Exception as e:
                                logger.error(f"删除空媒体组目录失败: {str(e)}")
                        self.media_group_queue.task_done()
                        continue
                    
                    # 标记是否所有目标频道都已上传成功
                    all_targets_uploaded = True
                    remaining_targets = not_forwarded_targets.copy()
                        
                    # 依次上传到需要转发的目标频道
                    first_success_message = None
                    
                    for target_channel, target_id, target_info in target_channels:
                        # 检查是否已转发到此频道
                        all_forwarded = True
                        for message in media_group_download.messages:
                            if not self.history_manager.is_message_forwarded(media_group_download.source_channel, message.id, target_channel):
                                all_forwarded = False
                                break
                        
                        if all_forwarded:
                            logger.debug(f"{group_id} {message_ids} 已转发到频道 {target_info}，跳过")
                            continue
                        
                        try:
                            logger.info(f"上传{group_id} {message_ids} 到频道 {target_info}")
                            
                            if len(media_group) == 1:
                                # 单个媒体
                                try:
                                    media_item = media_group[0]
                                    if isinstance(media_item, InputMediaPhoto):
                                        sent_message = await self.client.send_photo(
                                            chat_id=target_id,
                                            photo=media_item.media,
                                            caption=media_item.caption
                                        )
                                    elif isinstance(media_item, InputMediaVideo):
                                        # 使用缩略图
                                        thumb = None
                                        if thumbnails:
                                            thumb = thumbnails.get(media_item.media)
                                        sent_message = await self.client.send_video(
                                            chat_id=target_id,
                                            video=media_item.media,
                                            caption=media_item.caption,
                                            supports_streaming=True,
                                            thumb=thumb
                                        )
                                    elif isinstance(media_item, InputMediaDocument):
                                        sent_message = await self.client.send_document(
                                            chat_id=target_id,
                                            document=media_item.media,
                                            caption=media_item.caption
                                        )
                                    elif isinstance(media_item, InputMediaAudio):
                                        sent_message = await self.client.send_audio(
                                            chat_id=target_id,
                                            audio=media_item.media,
                                            caption=media_item.caption
                                        )
                                    else:
                                        logger.warning(f"未知媒体类型: {type(media_item)}")
                                        continue
                                    
                                    # 保存第一次成功的消息，用于后续复制
                                    if first_success_message is None:
                                        first_success_message = sent_message
                                except Exception as e:
                                    logger.error(f"发送单个媒体失败: {str(e)}")
                                    all_targets_uploaded = False
                                    continue
                            else:
                                # 媒体组
                                try:
                                    if first_success_message is not None:
                                        # 如果已有成功消息，使用复制转发
                                        sent_messages = await self.client.copy_media_group(
                                            chat_id=target_id,
                                            from_chat_id=first_success_message.chat.id,
                                            message_id=first_success_message.id
                                        )
                                    else:
                                        # 首次发送媒体组
                                        sent_messages = await self.client.send_media_group(
                                            chat_id=target_id,
                                            media=media_group
                                        )
                                        
                                        # 保存第一次成功的消息，用于后续复制
                                        if sent_messages and first_success_message is None:
                                            first_success_message = sent_messages[0]
                                except Exception as e:
                                    logger.error(f"发送媒体组失败: {str(e)}")
                                    all_targets_uploaded = False
                                    continue
                            
                            # 记录转发历史
                            for message in media_group_download.messages:
                                self.history_manager.add_forward_record(
                                    media_group_download.source_channel,
                                    message.id,
                                    target_channel,
                                    media_group_download.source_id
                                )
                            
                            logger.info(f"{group_id} {message_ids} 上传到 {target_info} 成功")
                            if target_info in remaining_targets:
                                remaining_targets.remove(target_info)
                            
                            # 上传延迟
                            await asyncio.sleep(1)
                        
                        except FloodWait as e:
                            logger.warning(f"上传媒体时遇到限制，等待 {e.x} 秒")
                            await asyncio.sleep(e.x)
                            # 继续尝试上传
                            success = await self._upload_media_group_to_channel(
                                media_group, 
                                media_group_download, 
                                target_channel, 
                                target_id, 
                                target_info,
                                thumbnails
                            )
                            if not success:
                                all_targets_uploaded = False
                            elif target_info in remaining_targets:
                                remaining_targets.remove(target_info)
                        
                        except Exception as e:
                            logger.error(f"上传媒体到频道 {target_info} 失败: {str(e)}")
                            all_targets_uploaded = False
                            continue
                    
                    # 媒体组上传完成后（无论成功失败），都清理缩略图
                    logger.debug(f"{group_id} {message_ids} 已处理完所有目标频道，清理缩略图")
                    for thumbnail_path in thumbnails.values():
                        self.video_processor.delete_thumbnail(thumbnail_path)
                    
                    # 媒体组上传完成后，清理媒体组的本地文件
                    if all_targets_uploaded:
                        logger.info(f"{group_id} {message_ids} 已成功上传到所有目标频道，清理本地文件: {media_group_dir}")
                        try:
                            # 删除媒体组目录及其所有文件
                            if media_group_dir.exists():
                                shutil.rmtree(media_group_dir)
                                logger.debug(f"已删除媒体组目录: {media_group_dir}")
                        except Exception as e:
                            logger.error(f"删除媒体组目录失败: {str(e)}")
                    else:
                        logger.warning(f"{group_id} {message_ids} 未能成功上传到所有目标频道，仍有 {remaining_targets} 未转发完成，保留本地文件: {media_group_dir}")
                
                except Exception as e:
                    logger.error(f"处理媒体组上传失败: {str(e)}")
                finally:
                    # 标记此项为处理完成
                    self.media_group_queue.task_done()
        
        except asyncio.CancelledError:
            logger.warning("消费者任务被取消")
        except Exception as e:
            logger.error(f"消费者任务异常: {str(e)}")
        finally:
            self.upload_running = False
            logger.info("消费者(上传)任务结束")
    
    async def _upload_media_group_to_channel(self, media_group, media_group_download, target_channel, target_id, target_info, thumbnails=None):
        """
        上传媒体组到指定频道，处理重试逻辑
        
        Args:
            media_group: 要上传的媒体组
            media_group_download: 媒体组下载结果
            target_channel: 目标频道标识符
            target_id: 目标频道ID
            target_info: 目标频道信息
            thumbnails: 缩略图字典，键为文件路径，值为缩略图路径
        """
        retry_count = 0
        max_retries = self.general_config.max_retries
        
        while retry_count < max_retries:
            try:
                if len(media_group) == 1:
                    # 单个媒体
                    media_item = media_group[0]
                    if isinstance(media_item, InputMediaPhoto):
                        sent_message = await self.client.send_photo(
                            chat_id=target_id,
                            photo=media_item.media,
                            caption=media_item.caption
                        )
                    elif isinstance(media_item, InputMediaVideo):
                        # 使用缩略图
                        thumb = None
                        if thumbnails:
                            thumb = thumbnails.get(media_item.media)
                        sent_message = await self.client.send_video(
                            chat_id=target_id,
                            video=media_item.media,
                            caption=media_item.caption,
                            supports_streaming=True,
                            thumb=thumb
                        )
                    elif isinstance(media_item, InputMediaDocument):
                        sent_message = await self.client.send_document(
                            chat_id=target_id,
                            document=media_item.media,
                            caption=media_item.caption
                        )
                    elif isinstance(media_item, InputMediaAudio):
                        sent_message = await self.client.send_audio(
                            chat_id=target_id,
                            audio=media_item.media,
                            caption=media_item.caption
                        )
                    else:
                        logger.warning(f"未知媒体类型: {type(media_item)}")
                        return False
                else:
                    # 媒体组
                    sent_messages = await self.client.send_media_group(
                        chat_id=target_id,
                        media=media_group
                    )
                
                # 记录转发历史
                for message in media_group_download.messages:
                    self.history_manager.add_forward_record(
                        media_group_download.source_channel,
                        message.id,
                        target_channel,
                        media_group_download.source_id
                    )
                
                logger.info(f"媒体上传到 {target_info} 成功")
                return True
            
            except FloodWait as e:
                logger.warning(f"上传媒体时遇到限制，等待 {e.x} 秒")
                await asyncio.sleep(e.x)
            
            except Exception as e:
                retry_count += 1
                logger.error(f"上传媒体到频道 {target_info} 失败 (尝试 {retry_count}/{max_retries}): {str(e)}")
                if retry_count >= max_retries:
                    break
                await asyncio.sleep(2 * retry_count)  # 指数退避
        
        return False

    async def _download_messages(self, messages: List[Message], download_dir: Path, chat_id: int) -> List[Tuple[Path, str]]:
        """
        下载消息中的媒体文件
        
        Args:
            messages: 消息列表
            download_dir: 下载目录
            chat_id: 频道ID
            
        Returns:
            List[Tuple[Path, str]]: 下载的文件路径和媒体类型列表
        """
        downloaded_files = []
        
        for message in messages:
            try:
                if message.photo:
                    # 下载照片
                    file_path = download_dir / f"{chat_id}_{message.id}_photo.jpg"
                    await self.client.download_media(message, file_name=str(file_path))
                    downloaded_files.append((file_path, "photo"))
                    logger.debug(f"照片下载成功: {file_path}")
                
                elif message.video:
                    # 下载视频
                    file_name = message.video.file_name
                    if not file_name:
                        file_name = f"{chat_id}_{message.id}_video.mp4"
                    file_path = download_dir / file_name
                    await self.client.download_media(message, file_name=str(file_path))
                    downloaded_files.append((file_path, "video"))
                    logger.debug(f"视频下载成功: {file_path}")
                
                elif message.document:
                    # 下载文档
                    file_name = message.document.file_name
                    if not file_name:
                        file_name = f"{chat_id}_{message.id}_document"
                    file_path = download_dir / file_name
                    await self.client.download_media(message, file_name=str(file_path))
                    downloaded_files.append((file_path, "document"))
                    logger.debug(f"文档下载成功: {file_path}")
                
                elif message.audio:
                    # 下载音频
                    file_name = message.audio.file_name
                    if not file_name:
                        file_name = f"{chat_id}_{message.id}_audio.mp3"
                    file_path = download_dir / file_name
                    await self.client.download_media(message, file_name=str(file_path))
                    downloaded_files.append((file_path, "audio"))
                    logger.debug(f"音频下载成功: {file_path}")
                
                elif message.animation:
                    # 下载动画(GIF)
                    file_path = download_dir / f"{chat_id}_{message.id}_animation.mp4"
                    await self.client.download_media(message, file_name=str(file_path))
                    downloaded_files.append((file_path, "video"))  # 作为视频上传
                    logger.debug(f"动画下载成功: {file_path}")
            
            except FloodWait as e:
                logger.warning(f"下载媒体文件时遇到限制，等待 {e.x} 秒")
                await asyncio.sleep(e.x)
                # 重试下载
                retry_result = await self._retry_download_media(message, download_dir, chat_id)
                if retry_result:
                    downloaded_files.append(retry_result)
            
            except Exception as e:
                logger.error(f"下载消息 {message.id} 的媒体文件失败: {e}")
                continue
        
        return downloaded_files
        
    async def _retry_download_media(self, message: Message, download_dir: Path, chat_id: int) -> Optional[Tuple[Path, str]]:
        """
        重试下载媒体文件
        
        Args:
            message: 消息对象
            download_dir: 下载目录
            chat_id: 频道ID
            
        Returns:
            Optional[Tuple[Path, str]]: 下载成功返回(文件路径, 媒体类型)，失败返回None
        """
        retry_count = 0
        max_retries = self.general_config.max_retries
        
        while retry_count < max_retries:
            try:
                if message.photo:
                    file_path = download_dir / f"{chat_id}_{message.id}_photo.jpg"
                    await self.client.download_media(message, file_name=str(file_path))
                    return (file_path, "photo")
                
                elif message.video:
                    file_name = message.video.file_name
                    if not file_name:
                        file_name = f"{chat_id}_{message.id}_video.mp4"
                    file_path = download_dir / file_name
                    await self.client.download_media(message, file_name=str(file_path))
                    return (file_path, "video")
                
                elif message.document:
                    file_name = message.document.file_name
                    if not file_name:
                        file_name = f"{chat_id}_{message.id}_document"
                    file_path = download_dir / file_name
                    await self.client.download_media(message, file_name=str(file_path))
                    return (file_path, "document")
                
                elif message.audio:
                    file_name = message.audio.file_name
                    if not file_name:
                        file_name = f"{chat_id}_{message.id}_audio.mp3"
                    file_path = download_dir / file_name
                    await self.client.download_media(message, file_name=str(file_path))
                    return (file_path, "audio")
                
                elif message.animation:
                    file_path = download_dir / f"{chat_id}_{message.id}_animation.mp4"
                    await self.client.download_media(message, file_name=str(file_path))
                    return (file_path, "video")
                
                return None
            
            except FloodWait as e:
                logger.warning(f"重试下载时遇到限制，等待 {e.x} 秒")
                await asyncio.sleep(e.x)
            
            except Exception as e:
                retry_count += 1
                logger.error(f"重试下载失败 (尝试 {retry_count}/{max_retries}): {e}")
                if retry_count >= max_retries:
                    break
                await asyncio.sleep(2 * retry_count)  # 指数退避
        
        return None 