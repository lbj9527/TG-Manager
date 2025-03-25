"""
上传模块，负责将本地文件上传到目标频道
"""

import os
import time
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Union, Any, Optional, Tuple
import mimetypes

from pyrogram import Client
from pyrogram.types import InputMediaPhoto, InputMediaVideo, InputMediaDocument, InputMediaAudio, Message
from pyrogram.errors import FloodWait, MediaEmpty, MediaInvalid

from src.utils.config_manager import ConfigManager
from src.utils.channel_resolver import ChannelResolver
from src.utils.history_manager import HistoryManager
from src.utils.logger import get_logger

logger = get_logger()

class Uploader:
    """
    上传模块，负责将本地文件上传到目标频道
    """
    
    def __init__(self, client: Client, config_manager: ConfigManager, channel_resolver: ChannelResolver, history_manager: HistoryManager):
        """
        初始化上传模块
        
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
        
        # 获取上传配置
        self.upload_config = self.config_manager.get_upload_config()
        self.general_config = self.config_manager.get_general_config()
        
        # 初始化MIME类型
        mimetypes.init()
    
    async def upload_local_files(self):
        """
        上传本地文件到目标频道
        """
        logger.info("开始上传本地文件到目标频道")
        
        # 获取目标频道列表
        target_channels = self.upload_config.target_channels
        if not target_channels:
            logger.warning("未配置目标频道，无法上传文件")
            return
        
        logger.info(f"配置的目标频道数量: {len(target_channels)}")
        
        # 获取上传目录
        upload_dir = Path(self.upload_config.directory)
        if not upload_dir.exists() or not upload_dir.is_dir():
            logger.error(f"上传目录不存在或不是目录: {upload_dir}")
            return
        
        # 上传计数
        upload_count = 0
        
        # 获取媒体组列表（每个子文件夹作为一个媒体组）
        media_groups = [d for d in upload_dir.iterdir() if d.is_dir()]
        
        if not media_groups:
            logger.info(f"在 {upload_dir} 中未找到媒体组文件夹，将作为单个文件上传")
            # 将当前目录下的文件作为单独文件上传
            await self._upload_single_files(upload_dir, target_channels)
        else:
            # 上传每个媒体组
            for group_dir in media_groups:
                logger.info(f"处理媒体组: {group_dir.name}")
                
                # 获取媒体组文件
                files = [f for f in group_dir.iterdir() if f.is_file()]
                
                if not files:
                    logger.warning(f"媒体组 {group_dir.name} 中没有文件，跳过")
                    continue
                
                # 检查是否达到限制
                if self.general_config.limit > 0 and upload_count >= self.general_config.limit:
                    logger.info(f"已达到上传限制 {self.general_config.limit}，暂停 {self.general_config.pause_time} 秒")
                    await asyncio.sleep(self.general_config.pause_time)
                    upload_count = 0
                
                # 上传媒体组
                success = await self._upload_media_group(files, group_dir.name, target_channels)
                if success:
                    upload_count += 1
        
        logger.info("本地文件上传完成")
    
    async def _upload_single_files(self, directory: Path, target_channels: List[str]):
        """
        将目录中的单个文件上传到目标频道
        
        Args:
            directory: 文件目录
            target_channels: 目标频道列表
        """
        # 获取所有文件
        files = [f for f in directory.iterdir() if f.is_file()]
        
        if not files:
            logger.warning(f"目录 {directory} 中没有文件，无法上传")
            return
        
        logger.info(f"在 {directory} 中找到 {len(files)} 个文件待上传")
        
        # 上传计数
        upload_count = 0
        
        # 上传每个文件
        for file_path in files:
            # 检查是否已上传
            already_uploaded = True
            for channel in target_channels:
                if not self.history_manager.is_file_uploaded(str(file_path), channel):
                    already_uploaded = False
                    break
            
            if already_uploaded:
                logger.debug(f"文件 {file_path.name} 已上传到所有目标频道，跳过")
                continue
            
            # 检查是否达到限制
            if self.general_config.limit > 0 and upload_count >= self.general_config.limit:
                logger.info(f"已达到上传限制 {self.general_config.limit}，暂停 {self.general_config.pause_time} 秒")
                await asyncio.sleep(self.general_config.pause_time)
                upload_count = 0
            
            # 生成文件标题
            caption = self.upload_config.caption_template.format(
                filename=file_path.stem,
                extension=file_path.suffix.lstrip('.'),
                full_name=file_path.name,
                date=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            
            # 上传文件到每个目标频道
            for channel in target_channels:
                # 检查是否已上传到此频道
                if self.history_manager.is_file_uploaded(str(file_path), channel):
                    logger.debug(f"文件 {file_path.name} 已上传到频道 {channel}，跳过")
                    continue
                
                try:
                    # 解析频道ID
                    channel_id = await self.channel_resolver.get_channel_id(channel)
                    
                    # 确定媒体类型
                    media_type = self._get_media_type(file_path)
                    
                    # 上传文件
                    message = await self._upload_file(file_path, caption, channel_id, media_type)
                    
                    if message:
                        # 记录上传历史
                        self.history_manager.add_upload_record(
                            str(file_path),
                            channel,
                            os.path.getsize(file_path),
                            media_type
                        )
                        logger.info(f"文件 {file_path.name} 上传到频道 {channel} 成功")
                        upload_count += 1
                    
                    # 上传延迟
                    await asyncio.sleep(1)
                
                except Exception as e:
                    logger.error(f"上传文件 {file_path.name} 到频道 {channel} 失败: {e}")
                    continue
    
    async def _upload_media_group(self, files: List[Path], group_name: str, target_channels: List[str]) -> bool:
        """
        将文件作为媒体组上传到目标频道
        
        Args:
            files: 文件列表
            group_name: 媒体组名称（用作标题）
            target_channels: 目标频道列表
            
        Returns:
            bool: 是否成功上传
        """
        # 限制每个媒体组最多10个文件
        if len(files) > 10:
            logger.warning(f"媒体组 {group_name} 文件数量超过10个，将只上传前10个文件")
            files = files[:10]
        
        # 筛选支持的媒体类型文件
        valid_files = []
        for file_path in files:
            media_type = self._get_media_type(file_path)
            if media_type in ['photo', 'video', 'document', 'audio']:
                valid_files.append((file_path, media_type))
        
        if not valid_files:
            logger.warning(f"媒体组 {group_name} 中没有有效的媒体文件，跳过")
            return False
        
        # 生成媒体组标题
        caption = group_name
        
        # 上传到每个目标频道
        for channel in target_channels:
            # 检查是否已上传到此频道
            all_uploaded = True
            for file_path, _ in valid_files:
                if not self.history_manager.is_file_uploaded(str(file_path), channel):
                    all_uploaded = False
                    break
            
            if all_uploaded:
                logger.debug(f"媒体组 {group_name} 已上传到频道 {channel}，跳过")
                continue
            
            try:
                # 解析频道ID
                channel_id = await self.channel_resolver.get_channel_id(channel)
                
                # 创建媒体组
                media_group = []
                for i, (file_path, media_type) in enumerate(valid_files):
                    # 只在第一个媒体上添加标题
                    file_caption = caption if i == 0 else ""
                    
                    if media_type == "photo":
                        media_group.append(
                            InputMediaPhoto(str(file_path), caption=file_caption)
                        )
                    elif media_type == "video":
                        media_group.append(
                            InputMediaVideo(str(file_path), caption=file_caption)
                        )
                    elif media_type == "document":
                        media_group.append(
                            InputMediaDocument(str(file_path), caption=file_caption)
                        )
                    elif media_type == "audio":
                        media_group.append(
                            InputMediaAudio(str(file_path), caption=file_caption)
                        )
                
                # 发送媒体组
                if len(media_group) == 1:
                    # 单个媒体
                    message = await self.client.send_media_group(
                        chat_id=channel_id,
                        media=media_group
                    )
                else:
                    # 媒体组
                    messages = await self.client.send_media_group(
                        chat_id=channel_id,
                        media=media_group
                    )
                
                # 记录上传历史
                for file_path, media_type in valid_files:
                    self.history_manager.add_upload_record(
                        str(file_path),
                        channel,
                        os.path.getsize(file_path),
                        media_type
                    )
                
                logger.info(f"媒体组 {group_name} 上传到频道 {channel} 成功")
                
                # 上传延迟
                await asyncio.sleep(2)
            
            except FloodWait as e:
                logger.warning(f"上传媒体组时遇到限制，等待 {e.x} 秒")
                await asyncio.sleep(e.x)
                # 重试上传
                return await self._upload_media_group(files, group_name, [channel])
            
            except Exception as e:
                logger.error(f"上传媒体组 {group_name} 到频道 {channel} 失败: {e}")
                return False
        
        return True
    
    async def _upload_file(self, file_path: Path, caption: str, chat_id: int, media_type: str) -> Optional[Message]:
        """
        上传单个文件到频道
        
        Args:
            file_path: 文件路径
            caption: 文件标题
            chat_id: 频道ID
            media_type: 媒体类型
            
        Returns:
            Optional[Message]: 上传成功返回的消息对象，失败返回None
        """
        try:
            if media_type == "photo":
                return await self.client.send_photo(
                    chat_id=chat_id,
                    photo=str(file_path),
                    caption=caption
                )
            elif media_type == "video":
                return await self.client.send_video(
                    chat_id=chat_id,
                    video=str(file_path),
                    caption=caption
                )
            elif media_type == "document":
                return await self.client.send_document(
                    chat_id=chat_id,
                    document=str(file_path),
                    caption=caption
                )
            elif media_type == "audio":
                return await self.client.send_audio(
                    chat_id=chat_id,
                    audio=str(file_path),
                    caption=caption
                )
            elif media_type == "animation":
                return await self.client.send_animation(
                    chat_id=chat_id,
                    animation=str(file_path),
                    caption=caption
                )
            else:
                # 默认作为文档发送
                return await self.client.send_document(
                    chat_id=chat_id,
                    document=str(file_path),
                    caption=caption
                )
        
        except FloodWait as e:
            logger.warning(f"上传文件时遇到限制，等待 {e.x} 秒")
            await asyncio.sleep(e.x)
            return await self._upload_file(file_path, caption, chat_id, media_type)
        
        except (MediaEmpty, MediaInvalid) as e:
            logger.error(f"媒体文件无效: {file_path}, 错误: {e}")
            return None
        
        except Exception as e:
            logger.error(f"上传文件失败: {file_path}, 错误: {e}")
            return None
    
    def _get_media_type(self, file_path: Path) -> str:
        """
        根据文件扩展名确定媒体类型
        
        Args:
            file_path: 文件路径
            
        Returns:
            str: 媒体类型
        """
        mime_type, _ = mimetypes.guess_type(file_path)
        
        if mime_type:
            if mime_type.startswith('image'):
                return "photo"
            elif mime_type.startswith('video'):
                return "video"
            elif mime_type.startswith('audio'):
                return "audio"
            elif mime_type == 'image/gif':
                return "animation"
        
        # 根据扩展名判断
        extension = file_path.suffix.lower()
        
        if extension in ['.jpg', '.jpeg', '.png', '.webp']:
            return "photo"
        elif extension in ['.mp4', '.avi', '.mov', '.mkv']:
            return "video"
        elif extension in ['.mp3', '.m4a', '.ogg', '.wav']:
            return "audio"
        elif extension == '.gif':
            return "animation"
        else:
            return "document" 