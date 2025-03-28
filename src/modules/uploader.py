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
from src.utils.video_processor import VideoProcessor

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
        
        # 初始化视频处理器
        self.video_processor = VideoProcessor()
    
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
        
        # 尝试读取title.txt文件作为默认标题
        default_caption = ""
        title_file_path = directory / "title.txt"
        if title_file_path.exists() and title_file_path.is_file():
            try:
                with open(title_file_path, "r", encoding="utf-8") as f:
                    default_caption = f.read().strip()
                logger.info(f"从 {title_file_path} 读取默认标题成功")
            except Exception as e:
                logger.error(f"读取标题文件 {title_file_path} 失败: {e}")
                # 如果读取失败，使用默认的caption模板
        
        # 上传计数
        upload_count = 0
        
        # 检查每个目标频道的转发权限，将非禁止转发的频道排在前面
        sorted_target_channels = []
        try:
            non_restricted_channels = []
            restricted_channels = []
            
            for channel in target_channels:
                try:
                    # 解析频道ID
                    channel_id = await self.channel_resolver.get_channel_id(channel)
                    # 获取频道信息
                    channel_info, (channel_title, _) = await self.channel_resolver.format_channel_info(channel_id)
                    
                    # 检查频道转发权限
                    if await self.channel_resolver.check_forward_permission(channel_id):
                        non_restricted_channels.append((channel, channel_id, channel_info))
                    else:
                        restricted_channels.append((channel, channel_id, channel_info))
                except Exception as e:
                    logger.error(f"检查频道 {channel} 权限失败: {e}")
                    continue
                    
            # 合并频道列表，非禁止转发的频道排在前面
            sorted_target_channels = non_restricted_channels + restricted_channels
            
            logger.info(f"非禁止转发频道: {len(non_restricted_channels)}个, 禁止转发频道: {len(restricted_channels)}个")
        except Exception as e:
            logger.error(f"排序目标频道失败: {e}")
            # 如果排序失败，使用原始列表
            sorted_target_channels = [(channel, None, channel) for channel in target_channels]
        
        # 上传每个文件
        for file_path in files:
            # 跳过title.txt文件本身
            if file_path.name == "title.txt":
                continue
                
            # 检查是否已上传
            already_uploaded = True
            for channel, _, _ in sorted_target_channels:
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
            
            # 生成文件标题，优先使用从title.txt读取的内容
            if default_caption:
                caption = default_caption
            else:
                caption = self.upload_config.caption_template.format(
                    filename=file_path.stem,
                    extension=file_path.suffix.lstrip('.'),
                    full_name=file_path.name,
                    date=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
            
            # 确定媒体类型
            media_type = self._get_media_type(file_path)
            
            # 为视频文件生成缩略图
            thumbnail_path = None
            if media_type == "video":
                thumbnail_path = self.video_processor.extract_thumbnail(str(file_path))
            
            # 记录是否已经成功上传到某个非禁止转发频道
            first_upload_success = False
            first_success_channel_id = None
            first_success_message_id = None
            
            # 上传文件到每个目标频道
            for channel, channel_id, channel_info in sorted_target_channels:
                # 检查是否已上传到此频道
                if self.history_manager.is_file_uploaded(str(file_path), channel):
                    logger.debug(f"文件 {file_path.name} 已上传到频道 {channel_info}，跳过")
                    continue
                
                try:
                    # 如果尚未解析频道ID，现在解析
                    if channel_id is None:
                        channel_id = await self.channel_resolver.get_channel_id(channel)
                        channel_info, _ = await self.channel_resolver.format_channel_info(channel_id)
                    
                    # 如果已经成功上传到非禁止转发频道，使用复制转发方式
                    if first_upload_success and first_success_channel_id and first_success_message_id:
                        logger.info(f"使用复制转发方式将文件 {file_path.name} 从已上传频道转发到 {channel_info}")
                        
                        try:
                            # 使用copy_message复制消息
                            forwarded = await self.client.copy_message(
                                chat_id=channel_id,
                                from_chat_id=first_success_channel_id,
                                message_id=first_success_message_id
                            )
                            
                            # 记录上传历史
                            self.history_manager.add_upload_record(
                                str(file_path),
                                channel,
                                os.path.getsize(file_path),
                                media_type
                            )
                            
                            logger.info(f"文件 {file_path.name} 复制转发到频道 {channel_info} 成功")
                            upload_count += 1
                        except Exception as e:
                            logger.error(f"复制转发文件 {file_path.name} 到频道 {channel_info} 失败: {e}")
                    else:
                        # 首次上传，直接发送文件
                        logger.info(f"直接上传文件 {file_path.name} 到频道 {channel_info}")
                        
                        # 上传文件，对于视频类型，传入缩略图
                        if media_type == "video":
                            message = await self.client.send_video(
                                chat_id=channel_id,
                                video=str(file_path),
                                caption=caption,
                                supports_streaming=True,
                                thumb=thumbnail_path
                            )
                        else:
                            # 其他类型使用通用的上传方法
                            message = await self._upload_file(file_path, caption, channel_id, media_type)
                        
                        if message:
                            # 记录上传历史
                            self.history_manager.add_upload_record(
                                str(file_path),
                                channel,
                                os.path.getsize(file_path),
                                media_type
                            )
                            logger.info(f"文件 {file_path.name} 上传到频道 {channel_info} 成功")
                            upload_count += 1
                            
                            # 记录第一次成功上传的信息，用于后续复制转发
                            if not first_upload_success:
                                first_upload_success = True
                                first_success_channel_id = channel_id
                                first_success_message_id = message.id
                    
                    # 上传延迟
                    await asyncio.sleep(1)
                
                except FloodWait as e:
                    logger.warning(f"上传文件时遇到限制，等待 {e.x} 秒")
                    await asyncio.sleep(e.x)
                    # 重试此频道
                    retry_success = False
                    try:
                        if first_upload_success and first_success_channel_id and first_success_message_id:
                            # 使用复制转发重试
                            forwarded = await self.client.copy_message(
                                chat_id=channel_id,
                                from_chat_id=first_success_channel_id,
                                message_id=first_success_message_id
                            )
                            retry_success = True
                        else:
                            # 直接上传重试
                            if media_type == "video":
                                message = await self.client.send_video(
                                    chat_id=channel_id,
                                    video=str(file_path),
                                    caption=caption,
                                    supports_streaming=True,
                                    thumb=thumbnail_path
                                )
                            else:
                                message = await self._upload_file(file_path, caption, channel_id, media_type)
                            
                            if message:
                                retry_success = True
                                if not first_upload_success:
                                    first_upload_success = True
                                    first_success_channel_id = channel_id
                                    first_success_message_id = message.id
                        
                        if retry_success:
                            # 记录上传历史
                            self.history_manager.add_upload_record(
                                str(file_path),
                                channel,
                                os.path.getsize(file_path),
                                media_type
                            )
                            logger.info(f"文件 {file_path.name} 重试上传到频道 {channel_info} 成功")
                            upload_count += 1
                    except Exception as e:
                        logger.error(f"重试上传文件 {file_path.name} 到频道 {channel_info} 失败: {e}")
                
                except Exception as e:
                    logger.error(f"上传文件 {file_path.name} 到频道 {channel_info} 失败: {e}")
                    continue
            
            # 如果没有成功上传到任何一个频道，提示错误
            if not first_upload_success:
                logger.error(f"文件 {file_path.name} 无法上传到任何目标频道")
            
            # 清理当前文件的缩略图
            if thumbnail_path:
                self.video_processor.delete_thumbnail(thumbnail_path)
    
    async def _upload_media_group(self, files: List[Path], group_name: str, target_channels: List[str]) -> bool:
        """
        将文件作为媒体组上传到目标频道
        
        Args:
            files: 文件列表
            group_name: 媒体组名称
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
        
        # 获取媒体组目录路径（第一个文件的父目录）
        if valid_files:
            group_dir = valid_files[0][0].parent
            
            # 尝试读取title.txt文件作为caption
            caption = ""
            title_file_path = group_dir / "title.txt"
            if title_file_path.exists() and title_file_path.is_file():
                try:
                    with open(title_file_path, "r", encoding="utf-8") as f:
                        caption = f.read().strip()
                    logger.info(f"从 {title_file_path} 读取媒体组标题成功")
                except Exception as e:
                    logger.error(f"读取标题文件 {title_file_path} 失败: {e}")
                    # 如果读取失败，默认使用文件夹名作为标题
                    caption = group_name
            else:
                # 如果标题文件不存在，使用文件夹名作为默认标题
                logger.info(f"标题文件 {title_file_path} 不存在，使用文件夹名 {group_name} 作为标题")
                caption = group_name
        else:
            caption = group_name
        
        # 为媒体组中的视频生成缩略图
        thumbnails = {}
        for file_path, media_type in valid_files:
            if media_type == "video":
                thumbnail_path = self.video_processor.extract_thumbnail(str(file_path))
                if thumbnail_path:
                    thumbnails[str(file_path)] = thumbnail_path
        
        # 检查每个目标频道的转发权限，将非禁止转发的频道排在前面
        non_restricted_channels = []
        restricted_channels = []
        
        for channel in target_channels:
            try:
                # 解析频道ID
                channel_id = await self.channel_resolver.get_channel_id(channel)
                # 获取频道信息
                channel_info, (channel_title, _) = await self.channel_resolver.format_channel_info(channel_id)
                
                # 检查是否已上传到此频道
                all_uploaded = True
                for file_path, _ in valid_files:
                    if not self.history_manager.is_file_uploaded(str(file_path), channel):
                        all_uploaded = False
                        break
                
                if all_uploaded:
                    logger.debug(f"媒体组 {group_name} 已上传到频道 {channel_info}，跳过")
                    continue
                
                # 检查频道转发权限
                if await self.channel_resolver.check_forward_permission(channel_id):
                    non_restricted_channels.append((channel, channel_id, channel_info))
                else:
                    restricted_channels.append((channel, channel_id, channel_info))
            except Exception as e:
                logger.error(f"检查频道 {channel} 权限失败: {e}")
                continue
                
        # 合并频道列表，非禁止转发的频道排在前面
        sorted_target_channels = non_restricted_channels + restricted_channels
        
        if not sorted_target_channels:
            logger.warning(f"媒体组 {group_name} 没有有效的目标频道，跳过")
            # 清理缩略图
            for thumbnail_path in thumbnails.values():
                self.video_processor.delete_thumbnail(thumbnail_path)
            return False
            
        logger.info(f"非禁止转发频道: {len(non_restricted_channels)}个, 禁止转发频道: {len(restricted_channels)}个")
        
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
                # 检查是否有缩略图
                thumb = thumbnails.get(str(file_path))
                media_group.append(
                    InputMediaVideo(
                        str(file_path), 
                        caption=file_caption, 
                        supports_streaming=True,
                        thumb=thumb
                    )
                )
            elif media_type == "document":
                media_group.append(
                    InputMediaDocument(str(file_path), caption=file_caption)
                )
            elif media_type == "audio":
                media_group.append(
                    InputMediaAudio(str(file_path), caption=file_caption)
                )
        
        success = True
        first_upload_success = False
        first_success_channel_id = None
        first_success_message_id = None
        
        # 先尝试上传到非禁止转发频道
        for channel, channel_id, channel_info in sorted_target_channels:
            try:
                # 如果已经成功上传到某个非禁止转发频道，则使用copy_media_group方法
                if first_upload_success and first_success_channel_id and first_success_message_id:
                    logger.info(f"使用复制转发方式将媒体组 {group_name} 从已上传频道转发到 {channel_info}")
                    
                    try:
                        if len(media_group) == 1:
                            # 单个媒体使用copy_message
                            forwarded = await self.client.copy_message(
                                chat_id=channel_id,
                                from_chat_id=first_success_channel_id,
                                message_id=first_success_message_id
                            )
                        else:
                            # 媒体组使用copy_media_group
                            forwarded = await self.client.copy_media_group(
                                chat_id=channel_id,
                                from_chat_id=first_success_channel_id,
                                message_id=first_success_message_id
                            )
                        
                        # 记录上传历史
                        for file_path, media_type in valid_files:
                            self.history_manager.add_upload_record(
                                str(file_path),
                                channel,
                                os.path.getsize(file_path),
                                media_type
                            )
                        
                        logger.info(f"媒体组 {group_name} 复制转发到频道 {channel_info} 成功")
                    except Exception as e:
                        logger.error(f"复制转发媒体组 {group_name} 到频道 {channel_info} 失败: {e}")
                        success = False
                else:
                    # 首次上传，直接发送媒体组
                    logger.info(f"直接上传媒体组 {group_name} 到频道 {channel_info}")
                    
                    try:
                        if len(media_group) == 1:
                            # 单个媒体
                            message = await self.client.send_photo(
                                chat_id=channel_id,
                                photo=media_group[0].media,
                                caption=media_group[0].caption
                            ) if isinstance(media_group[0], InputMediaPhoto) else (
                                await self.client.send_video(
                                    chat_id=channel_id,
                                    video=media_group[0].media,
                                    caption=media_group[0].caption,
                                    supports_streaming=True,
                                    thumb=thumbnails.get(media_group[0].media)
                                ) if isinstance(media_group[0], InputMediaVideo) else (
                                    await self.client.send_document(
                                        chat_id=channel_id,
                                        document=media_group[0].media,
                                        caption=media_group[0].caption
                                    ) if isinstance(media_group[0], InputMediaDocument) else (
                                        await self.client.send_audio(
                                            chat_id=channel_id,
                                            audio=media_group[0].media,
                                            caption=media_group[0].caption
                                        )
                                    )
                                )
                            )
                            
                            # 记录第一次成功上传的信息，用于后续复制转发
                            if not first_upload_success:
                                first_upload_success = True
                                first_success_channel_id = channel_id
                                first_success_message_id = message.id
                        else:
                            # 媒体组
                            messages = await self.client.send_media_group(
                                chat_id=channel_id,
                                media=media_group
                            )
                            
                            # 记录第一次成功上传的信息，用于后续复制转发
                            if not first_upload_success and messages:
                                first_upload_success = True
                                first_success_channel_id = channel_id
                                first_success_message_id = messages[0].id
                        
                        # 记录上传历史
                        for file_path, media_type in valid_files:
                            self.history_manager.add_upload_record(
                                str(file_path),
                                channel,
                                os.path.getsize(file_path),
                                media_type
                            )
                        
                        logger.info(f"媒体组 {group_name} 上传到频道 {channel_info} 成功")
                    except Exception as e:
                        logger.error(f"上传媒体组 {group_name} 到频道 {channel_info} 失败: {e}")
                        # 如果是第一个尝试的频道且失败，需要继续尝试其他频道
                        if not first_upload_success:
                            continue
                        success = False
                
                # 上传延迟
                await asyncio.sleep(2)
            
            except FloodWait as e:
                logger.warning(f"上传媒体组时遇到限制，等待 {e.x} 秒")
                await asyncio.sleep(e.x)
                # 重试上传 - 但不清理缩略图，因为还会使用
                channel_success = await self._upload_media_group(files, group_name, [channel])
                if not channel_success:
                    success = False
            
            except Exception as e:
                logger.error(f"上传媒体组 {group_name} 到频道 {channel} 失败: {e}")
                success = False
        
        # 如果没有成功上传到任何一个频道，提示错误
        if not first_upload_success:
            logger.error(f"媒体组 {group_name} 无法上传到任何目标频道")
            success = False
        
        # 上传完成后清理缩略图（无论成功失败）
        logger.debug(f"媒体组 {group_name} 已处理完所有目标频道，清理缩略图")
        for thumbnail_path in thumbnails.values():
            self.video_processor.delete_thumbnail(thumbnail_path)
        
        return success
    
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
                # 为视频生成缩略图
                thumbnail_path = self.video_processor.extract_thumbnail(str(file_path))
                
                result = await self.client.send_video(
                    chat_id=chat_id,
                    video=str(file_path),
                    caption=caption,
                    supports_streaming=True,
                    thumb=thumbnail_path
                )
                
                # 清理缩略图
                if thumbnail_path:
                    self.video_processor.delete_thumbnail(thumbnail_path)
                    
                return result
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