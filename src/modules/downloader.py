"""
下载模块，负责下载历史消息的媒体文件
"""

import os
import time
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Union, Any, Optional, Set

from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait

from src.utils.config_manager import ConfigManager
from src.utils.channel_resolver import ChannelResolver
from src.utils.history_manager import HistoryManager
from src.utils.logger import get_logger

logger = get_logger()

class Downloader:
    """
    下载模块，负责下载历史消息的媒体文件
    """
    
    def __init__(self, client: Client, config_manager: ConfigManager, channel_resolver: ChannelResolver, history_manager: HistoryManager):
        """
        初始化下载模块
        
        Args:
            client: Pyrogram客户端实例
            config_manager: 配置管理器实例
            channel_resolver: 频道解析器实例
            history_manager: 历史记录管理器实例
        """
        self.client = client
        self.config_manager = config_manager
        self.channel_resolver = channel_resolver
        self.history_manager = history_manager
        
        # 获取下载配置
        self.download_config = self.config_manager.get_download_config()
        self.general_config = self.config_manager.get_general_config()
        
        # 创建下载目录
        self.download_path = Path(self.download_config.download_path)
        self.download_path.mkdir(exist_ok=True)
    
    async def download_media_from_channels(self):
        """
        从配置的源频道下载媒体文件
        """
        logger.info("开始从频道下载媒体文件")
        
        # 获取源频道列表
        source_channels = self.download_config.source_channels
        logger.info(f"配置的源频道数量: {len(source_channels)}")
        
        # 下载计数
        download_count = 0
        
        # 遍历每个源频道
        for channel in source_channels:
            logger.info(f"准备从频道 {channel} 下载媒体文件")
            
            try:
                # 解析频道ID
                real_channel_id = await self.channel_resolver.get_channel_id(channel)
                logger.info(f"real_channel_id: {real_channel_id}")
                channel_info = await self.channel_resolver.format_channel_info(real_channel_id)
                logger.info(f"解析频道: {channel_info}")
                
                # 创建频道目录（如果需要按频道组织）
                if self.download_config.organize_by_chat:
                    channel_path = self.download_path / str(real_channel_id)
                    channel_path.mkdir(exist_ok=True)
                else:
                    channel_path = self.download_path
                
                # 获取已下载的消息ID列表
                downloaded_messages = self.history_manager.get_downloaded_messages(channel)
                logger.info(f"已下载的消息数量: {len(downloaded_messages)}")
                
                # 设置消息范围
                start_id = self.download_config.start_id
                end_id = self.download_config.end_id
                
                # 获取并下载消息
                async for message in self._iter_messages(real_channel_id, start_id, end_id):
                    # 检查是否达到限制
                    if self.general_config.limit > 0 and download_count >= self.general_config.limit:
                        logger.info(f"已达到下载限制 {self.general_config.limit}，暂停 {self.general_config.pause_time} 秒")
                        await asyncio.sleep(self.general_config.pause_time)
                        download_count = 0
                    
                    # 检查消息ID是否已下载
                    if message.id in downloaded_messages:
                        logger.debug(f"消息 {message.id} 已下载，跳过")
                        continue
                    
                    # 下载媒体文件
                    if await self._download_message_media(message, channel_path, real_channel_id):
                        # 添加下载记录
                        self.history_manager.add_download_record(channel, message.id, real_channel_id)
                        download_count += 1
                        
                        # 下载延迟
                        await asyncio.sleep(0.5)
            
            except Exception as e:
                logger.error(f"下载频道 {channel} 的媒体文件失败: {e}")
                continue
        
        logger.info("所有频道的媒体文件下载完成")
    
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
        
        offset = 0  # 使用offset_id而不是offset
        
        while True:
            try:
                # 使用get_chat_history代替get_messages
                logger.info(f"获取聊天记录: chat_id={chat_id}, start_id={curr_id}, end_id={stop_id}, limit=100")
                
                # 获取一批消息
                messages = []
                async for message in self.client.get_chat_history(
                    chat_id=chat_id,
                    limit=100,  # 每次获取100条消息
                    offset_id=curr_id  # 使用消息索引作为offset
                ):
                    messages.append(message)
                    
                    # 检查消息ID是否在范围内
                    if reverse and message.id <= stop_id:
                        yield message
                        return
                    elif not reverse and stop_id > 0 and message.id >= stop_id:
                        yield message
                        return
                    
                    yield message
                
                # 如果没有获取到消息，说明已经到达消息列表末尾
                if not messages:
                    break
                
                # 更新offset用于下一次获取
                offset += len(messages)
                
                # 避免频繁请求
                await asyncio.sleep(0.5)
            
            except FloodWait as e:
                logger.warning(f"获取消息时遇到限制，等待 {e.x} 秒")
                await asyncio.sleep(e.x)
            except Exception as e:
                logger.error(f"获取消息失败: {e}")
                logger.exception("详细错误信息")
                break
    
    async def _download_message_media(self, message: Message, download_path: Path, chat_id: int) -> bool:
        """
        下载消息中的媒体文件
        
        Args:
            message: 消息对象
            download_path: 下载路径
            chat_id: 频道ID
        
        Returns:
            bool: 是否成功下载
        """
        media_types = self.download_config.media_types
        
        try:
            if message.photo and "photo" in media_types:
                # 下载照片
                file_path = download_path / f"{chat_id}-{message.id}-photo.jpg"
                await self.client.download_media(message, file_name=str(file_path))
                logger.info(f"下载照片成功: {file_path}")
                return True
            
            elif message.video and "video" in media_types:
                # 下载视频
                file_name = message.video.file_name
                if not file_name:
                    file_name = f"{chat_id}-{message.id}-video.mp4"
                file_path = download_path / f"{chat_id}-{message.id}-{file_name}"
                await self.client.download_media(message, file_name=str(file_path))
                logger.info(f"下载视频成功: {file_path}")
                return True
            
            elif message.document and "document" in media_types:
                # 下载文档
                file_name = message.document.file_name
                if not file_name:
                    file_name = f"{chat_id}-{message.id}-document"
                file_path = download_path / f"{chat_id}-{message.id}-{file_name}"
                await self.client.download_media(message, file_name=str(file_path))
                logger.info(f"下载文档成功: {file_path}")
                return True
            
            elif message.audio and "audio" in media_types:
                # 下载音频
                file_name = message.audio.file_name
                if not file_name:
                    file_name = f"{chat_id}-{message.id}-audio.mp3"
                file_path = download_path / f"{chat_id}-{message.id}-{file_name}"
                await self.client.download_media(message, file_name=str(file_path))
                logger.info(f"下载音频成功: {file_path}")
                return True
            
            elif message.animation and "animation" in media_types:
                # 下载动画(GIF)
                file_path = download_path / f"{chat_id}-{message.id}-animation.mp4"
                await self.client.download_media(message, file_name=str(file_path))
                logger.info(f"下载动画成功: {file_path}")
                return True
            
            elif message.sticker and "sticker" in media_types:
                # 下载贴纸
                file_path = download_path / f"{chat_id}-{message.id}-sticker.webp"
                await self.client.download_media(message, file_name=str(file_path))
                logger.info(f"下载贴纸成功: {file_path}")
                return True
            
            return False
        
        except FloodWait as e:
            logger.warning(f"下载媒体文件时遇到限制，等待 {e.x} 秒")
            await asyncio.sleep(e.x)
            return await self._download_message_media(message, download_path, chat_id)
        
        except Exception as e:
            logger.error(f"下载消息 {message.id} 的媒体文件失败: {e}")
            return False 