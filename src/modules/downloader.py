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
                
                # 获取频道信息（现在返回字符串和(标题,ID)元组）
                channel_info, (channel_title, _) = await self.channel_resolver.format_channel_info(real_channel_id)
                logger.info(f"解析频道: {channel_info}")
                
                # 创建频道目录（如果需要按频道组织）
                if self.download_config.organize_by_chat:
                    # 使用"频道标题-频道ID"格式创建目录
                    folder_name = f"{channel_title}-{real_channel_id}"
                    # 确保文件夹名称有效（移除非法字符）
                    folder_name = self._sanitize_filename(folder_name)
                    channel_path = self.download_path / folder_name
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
        # 因此我们从最大ID开始请求，设置offset为0，让API本身帮我们筛选最新消息
        
        # 已获取的消息数量
        fetched_count = 0
        
        try:
            # 使用get_chat_history获取指定范围内的消息
            # 我们可以通过设置offset_id参数为actual_end_id+1来获取比此ID小的消息
            # 注意：Telegram offset_id是上限，不包含此ID
            offset_id = actual_end_id + 1
            
            while fetched_count < total_messages:
                limit = min(100, total_messages - fetched_count)  # 最多获取100条，但不超过剩余所需数量
                logger.info(f"获取消息批次: chat_id={chat_id}, offset_id={offset_id}, limit={limit}, 已获取={fetched_count}/{total_messages}")
                
                batch_count = 0
                async for message in self.client.get_chat_history(
                    chat_id=chat_id,
                    limit=limit,  # 限制每批次的消息数量
                    offset_id=offset_id  # 获取ID小于此值的消息
                ):
                    batch_count += 1
                    
                    # 只处理在范围内的消息
                    if message.id >= actual_start_id and message.id <= actual_end_id:
                        fetched_count += 1
                        yield message
                    
                    # 更新下一轮请求的offset_id
                    offset_id = message.id
                    
                    # 如果已经达到或低于开始ID，则停止获取
                    if message.id < actual_start_id:
                        logger.info(f"已达到最小ID {actual_start_id}，停止获取")
                        return
                
                # 如果这批次没有获取到任何消息，则退出循环
                if batch_count == 0:
                    logger.info("没有更多消息可获取")
                    break
                
                # 避免频繁请求
                await asyncio.sleep(0.5)
            
            logger.info(f"消息获取完成，共获取{fetched_count}条消息")
        
        except FloodWait as e:
            logger.warning(f"获取消息时遇到限制，等待 {e.x} 秒")
            await asyncio.sleep(e.x)
        except Exception as e:
            logger.error(f"获取消息失败: {e}")
            logger.exception("详细错误信息")
    
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

    def _sanitize_filename(self, filename: str) -> str:
        """
        清理文件名，移除非法字符
        
        Args:
            filename: 原始文件名
            
        Returns:
            str: 清理后的文件名
        """
        # 替换Windows和UNIX系统中的非法字符
        invalid_chars = r'<>:"/\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename 