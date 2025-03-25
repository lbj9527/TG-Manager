"""
转发模块，负责将消息从源频道转发到目标频道
"""

import os
import time
import asyncio
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Union, Any, Optional, Tuple, Set

from pyrogram import Client
from pyrogram.types import Message, InputMediaPhoto, InputMediaVideo, InputMediaDocument, InputMediaAudio
from pyrogram.errors import FloodWait, ChatForwardsRestricted, ChannelPrivate

from src.utils.config_manager import ConfigManager
from src.utils.channel_resolver import ChannelResolver
from src.utils.history_manager import HistoryManager
from src.modules.downloader import Downloader
from src.modules.uploader import Uploader
from src.utils.logger import get_logger

logger = get_logger()

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
                source_info = await self.channel_resolver.format_channel_info(source_channel)
                logger.info(f"源频道: {source_info}")
                
                # 检查源频道转发权限
                source_can_forward = await self.channel_resolver.check_forward_permission(source_channel)
                
                # 获取有效的目标频道
                valid_target_channels = []
                for target in target_channels:
                    try:
                        target_id = await self.channel_resolver.get_channel_id(target)
                        target_info = await self.channel_resolver.format_channel_info(target)
                        valid_target_channels.append((target, target_id, target_info))
                    except Exception as e:
                        logger.error(f"解析目标频道 {target} 失败: {e}")
                
                if not valid_target_channels:
                    logger.warning(f"源频道 {source_channel} 没有有效的目标频道，跳过")
                    continue
                
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
                    
                    # 区分转发模式
                    if source_can_forward:
                        # 源频道允许转发，直接使用转发功能
                        await self._forward_media_group_directly(messages, source_channel, source_id, valid_target_channels)
                    else:
                        # 源频道禁止转发，使用下载后上传的方式
                        await self._forward_media_group_via_download(messages, source_channel, source_id, valid_target_channels)
                    
                    forward_count += 1
                    
                    # 转发延迟
                    await asyncio.sleep(self.forward_config.forward_delay)
            
            except Exception as e:
                logger.error(f"转发频道 {source_channel} 的消息失败: {e}")
                continue
        
        logger.info("转发消息完成")
    
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
        迭代获取频道消息
        
        Args:
            chat_id: 频道ID
            start_id: 起始消息ID
            end_id: 结束消息ID
        
        Yields:
            Message: 消息对象
        """
        # 确定消息ID的迭代方向和限制
        if start_id == 0 and end_id == 0:
            # 默认获取最新消息
            curr_id = 0
            stop_id = 0
            reverse = False
        elif end_id == 0:
            # 从指定ID开始获取最新消息
            curr_id = start_id
            stop_id = 0
            reverse = False
        elif start_id == 0:
            # 获取直到指定ID的所有消息
            curr_id = 0
            stop_id = end_id
            reverse = False
        elif start_id < end_id:
            # 正向获取消息
            curr_id = start_id
            stop_id = end_id
            reverse = False
        else:
            # 逆向获取消息
            curr_id = start_id
            stop_id = end_id
            reverse = True
        
        offset_id = curr_id
        remaining_limit = None  # None表示获取全部消息
        
        while True:
            try:
                messages = await self.client.get_messages(
                    chat_id=chat_id,
                    offset_id=offset_id,
                    limit=100  # 每次获取100条消息
                )
                
                if not messages:
                    break
                
                for message in messages:
                    if reverse and message.id <= stop_id:
                        return
                    elif not reverse and stop_id > 0 and message.id >= stop_id:
                        return
                    
                    yield message
                
                # 更新offset_id用于下一次获取
                offset_id = messages[-1].id
                
                # 避免频繁请求
                await asyncio.sleep(0.5)
            
            except FloodWait as e:
                logger.warning(f"获取消息时遇到限制，等待 {e.x} 秒")
                await asyncio.sleep(e.x)
            except Exception as e:
                logger.error(f"获取消息失败: {e}")
                break
    
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
                    forwarded = await self.client.forward_messages(
                        chat_id=target_id,
                        from_chat_id=source_id,
                        message_ids=message.id,
                        disable_notification=True
                    )
                    
                    # 记录转发历史
                    self.history_manager.add_forward_record(
                        source_channel,
                        message.id,
                        target_channel,
                        source_id
                    )
                    
                    logger.info(f"消息 {message.id} 转发到 {target_info} 成功")
                else:
                    # 媒体组转发
                    message_ids = [msg.id for msg in messages]
                    forwarded = await self.client.forward_messages(
                        chat_id=target_id,
                        from_chat_id=source_id,
                        message_ids=message_ids,
                        disable_notification=True
                    )
                    
                    # 记录转发历史
                    for message in messages:
                        self.history_manager.add_forward_record(
                            source_channel,
                            message.id,
                            target_channel,
                            source_id
                        )
                    
                    logger.info(f"媒体组 {message_ids} 转发到 {target_info} 成功")
                
                # 转发延迟
                await asyncio.sleep(1)
            
            except ChatForwardsRestricted:
                logger.warning(f"频道 {target_info} 禁止转发，尝试使用下载后上传的方式")
                await self._forward_media_group_via_download(messages, source_channel, source_id, [(target_channel, target_id, target_info)])
            
            except FloodWait as e:
                logger.warning(f"转发消息时遇到限制，等待 {e.x} 秒")
                await asyncio.sleep(e.x)
                await self._forward_media_group_directly(messages, source_channel, source_id, [(target_channel, target_id, target_info)])
            
            except Exception as e:
                logger.error(f"转发消息到频道 {target_info} 失败: {e}")
                continue
    
    async def _forward_media_group_via_download(self, messages: List[Message], source_channel: str, source_id: int, 
                                             target_channels: List[Tuple[str, int, str]]):
        """
        通过下载后上传的方式转发媒体组
        
        Args:
            messages: 消息列表
            source_channel: 源频道标识符
            source_id: 源频道ID
            target_channels: 目标频道列表(频道标识符, 频道ID, 频道信息)
        """
        # 创建临时目录
        temp_dir = self.tmp_path / f"forward_{source_id}_{int(time.time())}"
        temp_dir.mkdir(exist_ok=True)
        
        try:
            # 下载媒体文件
            downloaded_files = await self._download_messages(messages, temp_dir, source_id)
            if not downloaded_files:
                logger.warning(f"没有媒体文件可下载，跳过转发")
                return
            
            # 获取消息文本
            caption = None
            for message in messages:
                if message.caption or message.text:
                    caption = message.caption or message.text
                    break
            
            # 移除原始标题
            if self.forward_config.remove_captions:
                caption = None
            
            # 创建媒体组
            media_group = []
            for file_path, media_type in downloaded_files:
                # 只有第一个媒体添加标题
                file_caption = caption if caption and len(media_group) == 0 else ""
                
                if media_type == "photo":
                    media_group.append(InputMediaPhoto(str(file_path), caption=file_caption))
                elif media_type == "video":
                    media_group.append(InputMediaVideo(str(file_path), caption=file_caption))
                elif media_type == "document":
                    media_group.append(InputMediaDocument(str(file_path), caption=file_caption))
                elif media_type == "audio":
                    media_group.append(InputMediaAudio(str(file_path), caption=file_caption))
            
            # 依次上传到每个目标频道
            first_success_message = None
            
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
                    logger.info(f"上传媒体到频道 {target_info}")
                    
                    if len(media_group) == 1:
                        # 单个媒体
                        if media_group[0].media.startswith("photo"):
                            sent_message = await self.client.send_photo(
                                chat_id=target_id,
                                photo=media_group[0].media,
                                caption=media_group[0].caption
                            )
                        elif media_group[0].media.startswith("video"):
                            sent_message = await self.client.send_video(
                                chat_id=target_id,
                                video=media_group[0].media,
                                caption=media_group[0].caption
                            )
                        elif media_group[0].media.startswith("document"):
                            sent_message = await self.client.send_document(
                                chat_id=target_id,
                                document=media_group[0].media,
                                caption=media_group[0].caption
                            )
                        elif media_group[0].media.startswith("audio"):
                            sent_message = await self.client.send_audio(
                                chat_id=target_id,
                                audio=media_group[0].media,
                                caption=media_group[0].caption
                            )
                        
                        # 保存第一次成功的消息，用于后续复制
                        if first_success_message is None:
                            first_success_message = sent_message
                    else:
                        # 媒体组
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
                    
                    # 记录转发历史
                    for message in messages:
                        self.history_manager.add_forward_record(
                            source_channel,
                            message.id,
                            target_channel,
                            source_id
                        )
                    
                    logger.info(f"媒体上传到 {target_info} 成功")
                    
                    # 上传延迟
                    await asyncio.sleep(1)
                
                except FloodWait as e:
                    logger.warning(f"上传媒体时遇到限制，等待 {e.x} 秒")
                    await asyncio.sleep(e.x)
                    # 重试上传
                    await self._forward_media_group_via_download(messages, source_channel, source_id, [(target_channel, target_id, target_info)])
                
                except Exception as e:
                    logger.error(f"上传媒体到频道 {target_info} 失败: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"下载后上传转发失败: {e}")
        
        finally:
            # 清理临时文件
            try:
                shutil.rmtree(temp_dir)
                logger.debug(f"清理临时目录: {temp_dir}")
            except Exception as e:
                logger.error(f"清理临时目录失败: {e}")
    
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
                
                elif message.video:
                    # 下载视频
                    file_name = message.video.file_name
                    if not file_name:
                        file_name = f"{chat_id}_{message.id}_video.mp4"
                    file_path = download_dir / file_name
                    await self.client.download_media(message, file_name=str(file_path))
                    downloaded_files.append((file_path, "video"))
                
                elif message.document:
                    # 下载文档
                    file_name = message.document.file_name
                    if not file_name:
                        file_name = f"{chat_id}_{message.id}_document"
                    file_path = download_dir / file_name
                    await self.client.download_media(message, file_name=str(file_path))
                    downloaded_files.append((file_path, "document"))
                
                elif message.audio:
                    # 下载音频
                    file_name = message.audio.file_name
                    if not file_name:
                        file_name = f"{chat_id}_{message.id}_audio.mp3"
                    file_path = download_dir / file_name
                    await self.client.download_media(message, file_name=str(file_path))
                    downloaded_files.append((file_path, "audio"))
                
                elif message.animation:
                    # 下载动画(GIF)
                    file_path = download_dir / f"{chat_id}_{message.id}_animation.mp4"
                    await self.client.download_media(message, file_name=str(file_path))
                    downloaded_files.append((file_path, "video"))  # 作为视频上传
            
            except FloodWait as e:
                logger.warning(f"下载媒体文件时遇到限制，等待 {e.x} 秒")
                await asyncio.sleep(e.x)
                # 重试下载
                continue
            
            except Exception as e:
                logger.error(f"下载消息 {message.id} 的媒体文件失败: {e}")
                continue
        
        return downloaded_files 