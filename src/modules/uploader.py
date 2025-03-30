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
from src.utils.events import EventEmitter
from src.utils.controls import CancelToken, PauseToken, TaskContext

logger = get_logger()

class Uploader(EventEmitter):
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
        # 初始化事件发射器
        super().__init__()
        
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
        
        # 任务控制
        self.task_context = None
    
    async def upload_local_files(self, task_context: Optional[TaskContext] = None):
        """
        上传本地文件到目标频道
        
        Args:
            task_context: 任务上下文，用于控制任务执行
        """
        # 初始化任务上下文
        self.task_context = task_context or TaskContext()
        
        status_message = "开始上传本地文件到目标频道"
        logger.info(status_message)
        self.emit("status", status_message)
        
        # 获取目标频道列表
        target_channels = self.upload_config.target_channels
        if not target_channels:
            error_msg = "未配置目标频道，无法上传文件"
            logger.warning(error_msg)
            self.emit("error", error_msg, error_type="CONFIG", recoverable=False)
            return
        
        logger.info(f"配置的目标频道数量: {len(target_channels)}")
        self.emit("info", f"配置的目标频道数量: {len(target_channels)}")
        
        # 获取上传目录
        upload_dir = Path(self.upload_config.directory)
        if not upload_dir.exists() or not upload_dir.is_dir():
            error_msg = f"上传目录不存在或不是目录: {upload_dir}"
            logger.error(error_msg)
            self.emit("error", error_msg, error_type="DIRECTORY", recoverable=False)
            return
        
        # 上传计数
        upload_count = 0
        total_uploaded = 0
        
        # 获取媒体组列表（每个子文件夹作为一个媒体组）
        media_groups = [d for d in upload_dir.iterdir() if d.is_dir()]
        
        # 发出开始事件
        if not media_groups:
            logger.info(f"在 {upload_dir} 中未找到媒体组文件夹，将作为单个文件上传")
            self.emit("info", f"在 {upload_dir} 中未找到媒体组文件夹，将作为单个文件上传")
            
            # 获取单个文件数量，用于进度计算
            single_files = [f for f in upload_dir.iterdir() if f.is_file() and f.name != "title.txt"]
            total_files = len(single_files)
            self.emit("total_files", total_files)
            
            # 将当前目录下的文件作为单独文件上传
            success_count = await self._upload_single_files(upload_dir, target_channels)
            total_uploaded += success_count
            
        else:
            # 发送媒体组总数
            total_groups = len(media_groups)
            logger.info(f"找到 {total_groups} 个媒体组文件夹")
            self.emit("info", f"找到 {total_groups} 个媒体组文件夹", total_groups=total_groups)
            self.emit("total_media_groups", total_groups)
            
            # 上传每个媒体组
            for idx, group_dir in enumerate(media_groups, 1):
                # 检查是否已取消
                if not await self.task_context.check_continue():
                    logger.info("上传任务已取消")
                    self.emit("status", "上传任务已取消")
                    return
                
                group_info = f"处理媒体组 [{idx}/{total_groups}]: {group_dir.name}"
                logger.info(group_info)
                self.emit("status", group_info)
                
                # 获取媒体组文件
                files = [f for f in group_dir.iterdir() if f.is_file()]
                
                if not files:
                    logger.warning(f"媒体组 {group_dir.name} 中没有文件，跳过")
                    self.emit("warning", f"媒体组 {group_dir.name} 中没有文件，跳过")
                    continue
                
                # 检查是否达到限制
                if self.general_config.limit > 0 and upload_count >= self.general_config.limit:
                    pause_msg = f"已达到上传限制 {self.general_config.limit}，暂停 {self.general_config.pause_time} 秒"
                    logger.info(pause_msg)
                    self.emit("status", pause_msg)
                    
                    # 等待暂停时间
                    for i in range(self.general_config.pause_time):
                        # 检查是否已取消
                        if self.task_context.cancel_token.is_cancelled:
                            logger.info("上传任务已取消")
                            self.emit("status", "上传任务已取消")
                            return
                            
                        # 检查是否被暂停
                        if self.task_context.pause_token.is_paused:
                            await self.task_context.wait_if_paused()
                            
                        await asyncio.sleep(1)
                        remaining = self.general_config.pause_time - i - 1
                        if remaining > 0 and remaining % 5 == 0:  # 每5秒更新一次状态
                            self.emit("status", f"暂停中，还剩 {remaining} 秒...")
                    
                    upload_count = 0
                
                # 上传媒体组
                success = await self._upload_media_group(files, group_dir.name, target_channels)
                if success:
                    upload_count += 1
                    total_uploaded += 1
                    # 发送进度事件
                    self.emit("progress", (idx / total_groups) * 100, idx, total_groups)
        
        complete_msg = f"本地文件上传完成，共上传 {total_uploaded} 个文件/媒体组"
        logger.info(complete_msg)
        self.emit("status", complete_msg)
        self.emit("complete", True, {"total_uploaded": total_uploaded})
    
    async def _upload_single_files(self, directory: Path, target_channels: List[str]):
        """
        将目录中的单个文件上传到目标频道
        
        Args:
            directory: 文件目录
            target_channels: 目标频道列表
            
        Returns:
            int: 成功上传的文件数量
        """
        # 获取所有文件
        files = [f for f in directory.iterdir() if f.is_file()]
        
        if not files:
            warning_msg = f"目录 {directory} 中没有文件，无法上传"
            logger.warning(warning_msg)
            self.emit("warning", warning_msg)
            return 0
        
        info_msg = f"在 {directory} 中找到 {len(files)} 个文件待上传"
        logger.info(info_msg)
        self.emit("info", info_msg)
        
        # 尝试读取title.txt文件作为默认标题
        default_caption = ""
        title_file_path = directory / "title.txt"
        if title_file_path.exists() and title_file_path.is_file():
            try:
                with open(title_file_path, "r", encoding="utf-8") as f:
                    default_caption = f.read().strip()
                logger.info(f"从 {title_file_path} 读取默认标题成功")
                self.emit("info", f"从 {title_file_path} 读取默认标题成功")
            except Exception as e:
                error_msg = f"读取标题文件 {title_file_path} 失败: {e}"
                logger.error(error_msg)
                self.emit("error", error_msg, error_type="FILE_READ", recoverable=True)
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
                    # 检查是否已取消
                    if self.task_context and self.task_context.cancel_token.is_cancelled:
                        logger.info("上传任务已取消")
                        self.emit("status", "上传任务已取消")
                        return upload_count
                    
                    # 解析频道ID
                    channel_id = await self.channel_resolver.get_channel_id(channel)
                    # 获取频道信息
                    channel_info, (channel_title, _) = await self.channel_resolver.format_channel_info(channel_id)
                    
                    # 检查频道转发权限
                    status_msg = f"检查频道权限: {channel_info}"
                    logger.info(status_msg)
                    self.emit("status", status_msg)
                    
                    if await self.channel_resolver.check_forward_permission(channel_id):
                        non_restricted_channels.append((channel, channel_id, channel_info))
                        logger.info(f"频道 {channel_info} 允许转发")
                        self.emit("info", f"频道 {channel_info} 允许转发")
                    else:
                        restricted_channels.append((channel, channel_id, channel_info))
                        logger.info(f"频道 {channel_info} 禁止转发")
                        self.emit("info", f"频道 {channel_info} 禁止转发")
                except Exception as e:
                    error_msg = f"检查频道 {channel} 权限失败: {e}"
                    logger.error(error_msg)
                    self.emit("error", error_msg, error_type="CHANNEL_CHECK", recoverable=True)
                    continue
                    
            # 合并频道列表，非禁止转发的频道排在前面
            sorted_target_channels = non_restricted_channels + restricted_channels
            
            info_msg = f"非禁止转发频道: {len(non_restricted_channels)}个, 禁止转发频道: {len(restricted_channels)}个"
            logger.info(info_msg)
            self.emit("info", info_msg)
        except Exception as e:
            error_msg = f"排序目标频道失败: {e}"
            logger.error(error_msg)
            self.emit("error", error_msg, error_type="CHANNEL_SORT", recoverable=True)
            # 如果排序失败，使用原始列表
            sorted_target_channels = [(channel, None, channel) for channel in target_channels]
        
        # 有效文件数量（不包括title.txt）
        valid_files = [f for f in files if f.name != "title.txt"]
        total_files = len(valid_files)
        self.emit("total_files", total_files)
        
        # 上传每个文件
        for idx, file_path in enumerate(valid_files, 1):
            # 检查是否已取消任务
            if self.task_context and self.task_context.cancel_token.is_cancelled:
                logger.info("上传任务已取消")
                self.emit("status", "上传任务已取消")
                return upload_count
            
            # 等待暂停恢复
            if self.task_context:
                await self.task_context.wait_if_paused()
            
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
                self.emit("file_skipped", str(file_path), "already_uploaded")
                continue
            
            # 检查是否达到限制
            if self.general_config.limit > 0 and upload_count >= self.general_config.limit:
                pause_msg = f"已达到上传限制 {self.general_config.limit}，暂停 {self.general_config.pause_time} 秒"
                logger.info(pause_msg)
                self.emit("status", pause_msg)
                
                # 等待暂停时间
                for i in range(self.general_config.pause_time):
                    # 检查是否已取消
                    if self.task_context and self.task_context.cancel_token.is_cancelled:
                        logger.info("上传任务已取消")
                        self.emit("status", "上传任务已取消")
                        return upload_count
                        
                    # 检查是否被暂停
                    if self.task_context and self.task_context.pause_token.is_paused:
                        await self.task_context.wait_if_paused()
                        
                    await asyncio.sleep(1)
                    remaining = self.general_config.pause_time - i - 1
                    if remaining > 0 and remaining % 5 == 0:  # 每5秒更新一次状态
                        self.emit("status", f"暂停中，还剩 {remaining} 秒...")
                
                upload_count = 0
            
            # 生成文件标题，优先使用从title.txt读取的内容
            if default_caption:
                caption = default_caption
            else:
                caption = self.upload_config.caption_template.format(
                    filename=file_path.stem,
                    extension=file_path.suffix.lstrip('.'),
                    datetime=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                )
            
            # 使用智能上传策略：首先尝试上传到一个非禁止转发的频道，然后复制转发到其他频道
            success = await self._upload_and_forward_file(file_path, caption, sorted_target_channels)
            
            if success:
                upload_count += 1
                # 发送进度事件
                progress_pct = (idx / total_files) * 100
                self.emit("progress", progress_pct, idx, total_files)
                self.emit("file_uploaded", str(file_path), success)
            else:
                self.emit("file_upload_failed", str(file_path))
                
            # 等待一小段时间，避免频繁请求
            await asyncio.sleep(1)
            
        return upload_count
    
    async def _upload_media_group(self, files: List[Path], group_name: str, target_channels: List[str]) -> bool:
        """
        将媒体组上传到目标频道
        
        Args:
            files: 媒体组文件列表
            group_name: 媒体组名称
            target_channels: 目标频道列表
            
        Returns:
            bool: 是否成功上传
        """
        # 检查是否已取消
        if self.task_context and self.task_context.cancel_token.is_cancelled:
            logger.info("上传任务已取消")
            self.emit("status", "上传任务已取消")
            return False
        
        # 等待暂停恢复
        if self.task_context:
            await self.task_context.wait_if_paused()
        
        try:
            # 检查每个目标频道的转发权限，将非禁止转发的频道排在前面
            sorted_target_channels = []
            non_restricted_channels = []
            restricted_channels = []
            
            for channel in target_channels:
                try:
                    # 解析频道ID
                    channel_id = await self.channel_resolver.get_channel_id(channel)
                    # 获取频道信息
                    channel_info, (channel_title, _) = await self.channel_resolver.format_channel_info(channel_id)
                    
                    # 检查频道转发权限
                    status_msg = f"检查频道权限: {channel_info}"
                    logger.info(status_msg)
                    self.emit("status", status_msg)
                    
                    if await self.channel_resolver.check_forward_permission(channel_id):
                        non_restricted_channels.append((channel, channel_id, channel_info))
                        logger.info(f"频道 {channel_info} 允许转发")
                        self.emit("info", f"频道 {channel_info} 允许转发")
                    else:
                        restricted_channels.append((channel, channel_id, channel_info))
                        logger.info(f"频道 {channel_info} 禁止转发")
                        self.emit("info", f"频道 {channel_info} 禁止转发")
                except Exception as e:
                    error_msg = f"检查频道 {channel} 权限失败: {e}"
                    logger.error(error_msg)
                    self.emit("error", error_msg, error_type="CHANNEL_CHECK", recoverable=True)
                    continue
            
            # 合并频道列表，非禁止转发的频道排在前面
            sorted_target_channels = non_restricted_channels + restricted_channels
            
            info_msg = f"非禁止转发频道: {len(non_restricted_channels)}个, 禁止转发频道: {len(restricted_channels)}个"
            logger.info(info_msg)
            self.emit("info", info_msg)
            
            if not sorted_target_channels:
                error_msg = f"没有有效的目标频道，媒体组 {group_name} 上传失败"
                logger.error(error_msg)
                self.emit("error", error_msg, error_type="NO_CHANNELS", recoverable=False)
                return False
            
            # 获取媒体文件
            media_files = []
            for f in files:
                # 跳过title.txt文件
                if f.name.lower() == "title.txt":
                    continue
                # 判断文件类型
                media_type = self._get_media_type(f)
                if media_type in ["photo", "video", "document", "audio"]:
                    media_files.append((f, media_type))
            
            if not media_files:
                warning_msg = f"媒体组 {group_name} 中没有有效的媒体文件，跳过"
                logger.warning(warning_msg)
                self.emit("warning", warning_msg)
                return False
            
            # 对媒体文件按名称排序，确保顺序稳定
            media_files.sort(key=lambda x: x[0].name)
            
            # 尝试读取标题文件
            caption = ""
            title_file_path = next((f for f in files if f.name.lower() == "title.txt"), None)
            if title_file_path:
                try:
                    with open(title_file_path, "r", encoding="utf-8") as f:
                        caption = f.read().strip()
                    logger.info(f"从 {title_file_path} 读取媒体组标题成功")
                    self.emit("info", f"从 {title_file_path} 读取媒体组标题成功")
                except Exception as e:
                    error_msg = f"读取媒体组标题文件失败: {e}"
                    logger.error(error_msg)
                    self.emit("error", error_msg, error_type="FILE_READ", recoverable=True)
                    # 如果读取失败，使用默认的caption
                    caption = self.upload_config.caption_template.format(
                        filename=group_name,
                        extension="",
                        datetime=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    )
            else:
                # 使用默认的caption模板
                caption = self.upload_config.caption_template.format(
                    filename=group_name,
                    extension="",
                    datetime=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                )
            
            # 准备媒体组
            status_msg = f"准备上传媒体组 {group_name}，共 {len(media_files)} 个文件"
            logger.info(status_msg)
            self.emit("status", status_msg)
            
            # 使用智能上传策略：首先尝试上传到一个非禁止转发的频道，然后复制转发到其他频道
            success = await self._upload_and_forward_media_group(media_files, caption, sorted_target_channels, group_name)
            
            if success:
                self.emit("media_group_uploaded", group_name, len(media_files))
                return True
            else:
                self.emit("media_group_upload_failed", group_name)
                return False
            
        except Exception as e:
            error_msg = f"上传媒体组 {group_name} 失败: {e}"
            logger.error(error_msg)
            import traceback
            error_details = traceback.format_exc()
            logger.error(error_details)
            self.emit("error", error_msg, error_type="MEDIA_GROUP_UPLOAD", recoverable=True, details=error_details)
            return False
    
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
    
    def _get_media_type(self, file_path: Path) -> Optional[str]:
        """
        根据文件扩展名确定媒体类型
        
        Args:
            file_path: 文件路径
            
        Returns:
            str: 媒体类型 ('photo', 'video', 'document', 'audio') 或 None
        """
        # 获取小写扩展名（不含点）
        ext = file_path.suffix.lower().lstrip('.')
        
        # 预定义的媒体类型扩展名映射
        photo_extensions = {"jpg", "jpeg", "png", "webp", "heif", "heic"}
        video_extensions = {"mp4", "mkv", "mov", "avi", "wmv", "flv", "webm", "m4v", "3gp"}
        audio_extensions = {"mp3", "m4a", "ogg", "wav", "flac", "aac"}
        document_extensions = {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "zip", "rar", "7z", "tar", "gz"}
        
        # 照片类型
        if ext in photo_extensions:
            return "photo"
        
        # 视频类型
        elif ext in video_extensions:
            return "video"
        
        # 音频类型
        elif ext in audio_extensions:
            return "audio"
        
        # 文档类型（所有其他类型都作为文档处理）
        elif ext in document_extensions:
            return "document"
        
        # 不支持的类型
        else:
            logger.warning(f"文件扩展名 '{ext}' 不在配置的支持类型列表中")
            return None
    
    async def _upload_and_forward_file(self, file_path: Path, caption: str, sorted_target_channels: List[Tuple[str, Optional[int], str]]) -> bool:
        """
        智能上传单个文件并转发到其他频道
        
        首先尝试上传到一个非禁止转发的频道，然后复制转发到其他频道
        
        Args:
            file_path: 文件路径
            caption: 文件标题
            sorted_target_channels: 已排序的目标频道列表，格式为 (channel_id_or_username, resolved_id, display_name)
            
        Returns:
            bool: 是否成功上传和转发
        """
        # 确定媒体类型
        media_type = self._get_media_type(file_path)
        if not media_type:
            error_msg = f"文件 {file_path.name} 类型不受支持，跳过"
            logger.error(error_msg)
            self.emit("error", error_msg, error_type="UNSUPPORTED_MEDIA", recoverable=True)
            return False
        
        # 为视频文件生成缩略图
        thumbnail_path = None
        if media_type == "video":
            try:
                thumbnail_path = self.video_processor.extract_thumbnail(str(file_path))
                if thumbnail_path:
                    logger.info(f"为视频 {file_path.name} 生成缩略图成功")
                    self.emit("info", f"为视频 {file_path.name} 生成缩略图成功")
            except Exception as e:
                error_msg = f"为视频 {file_path.name} 生成缩略图失败: {e}"
                logger.error(error_msg)
                self.emit("error", error_msg, error_type="THUMBNAIL_GENERATION", recoverable=True)
                # 继续上传，但没有缩略图
        
        try:
            # 记录是否已经成功上传到某个非禁止转发频道
            first_upload_success = False
            first_success_channel_id = None
            first_success_message_id = None
            
            # 上传文件到每个目标频道
            for channel, channel_id, channel_info in sorted_target_channels:
                # 检查是否已取消
                if self.task_context and self.task_context.cancel_token.is_cancelled:
                    logger.info("上传任务已取消")
                    self.emit("status", "上传任务已取消")
                    # 清理缩略图
                    if thumbnail_path:
                        self.video_processor.delete_thumbnail(thumbnail_path)
                    return False
                
                # 等待暂停恢复
                if self.task_context:
                    await self.task_context.wait_if_paused()
                
                # 检查是否已上传到此频道
                if self.history_manager.is_file_uploaded(str(file_path), channel):
                    logger.debug(f"文件 {file_path.name} 已上传到频道 {channel_info}，跳过")
                    self.emit("info", f"文件 {file_path.name} 已上传到频道 {channel_info}，跳过")
                    continue
                
                try:
                    # 如果尚未解析频道ID，现在解析
                    if channel_id is None:
                        channel_id = await self.channel_resolver.get_channel_id(channel)
                        channel_info, _ = await self.channel_resolver.format_channel_info(channel_id)
                    
                    # 发送状态更新
                    status_msg = f"正在上传文件 {file_path.name} 到频道 {channel_info}"
                    logger.info(status_msg)
                    self.emit("status", status_msg)
                    
                    # 如果已经成功上传到非禁止转发频道，使用复制转发方式
                    if first_upload_success and first_success_channel_id and first_success_message_id:
                        info_msg = f"使用复制转发方式将文件 {file_path.name} 从已上传频道转发到 {channel_info}"
                        logger.info(info_msg)
                        self.emit("info", info_msg)
                        
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
                            
                            success_msg = f"文件 {file_path.name} 复制转发到频道 {channel_info} 成功"
                            logger.info(success_msg)
                            self.emit("info", success_msg)
                        except FloodWait as e:
                            wait_msg = f"复制转发遇到限制，等待 {e.x} 秒后重试"
                            logger.warning(wait_msg)
                            self.emit("warning", wait_msg)
                            await asyncio.sleep(e.x)
                            # 重试复制转发
                            try:
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
                                
                                success_msg = f"文件 {file_path.name} 复制转发到频道 {channel_info} 成功"
                                logger.info(success_msg)
                                self.emit("info", success_msg)
                            except Exception as e:
                                error_msg = f"重试复制转发文件 {file_path.name} 到频道 {channel_info} 失败: {e}"
                                logger.error(error_msg)
                                self.emit("error", error_msg, error_type="COPY_MEDIA_GROUP_RETRY", recoverable=True)
                                continue
                        except Exception as e:
                            error_msg = f"使用copy_media_group复制文件 {file_path.name} 到频道 {channel_info} 失败: {e}"
                            logger.error(error_msg)
                            self.emit("error", error_msg, error_type="COPY_MEDIA_GROUP", recoverable=True)
                            continue
                    else:
                        # 首次上传，直接发送文件
                        info_msg = f"直接上传文件 {file_path.name} 到频道 {channel_info}"
                        logger.info(info_msg)
                        self.emit("info", info_msg)
                        
                        try:
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
                                success_msg = f"文件 {file_path.name} 上传到频道 {channel_info} 成功"
                                logger.info(success_msg)
                                self.emit("info", success_msg)
                                
                                # 记录第一次成功上传的信息，用于后续复制转发
                                if not first_upload_success:
                                    first_upload_success = True
                                    first_success_channel_id = channel_id
                                    first_success_message_id = message.id
                        except FloodWait as e:
                            wait_msg = f"上传文件遇到限制，等待 {e.x} 秒后重试"
                            logger.warning(wait_msg)
                            self.emit("warning", wait_msg)
                            await asyncio.sleep(e.x)
                            # 重试上传
                            try:
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
                                    # 记录上传历史
                                    self.history_manager.add_upload_record(
                                        str(file_path),
                                        channel,
                                        os.path.getsize(file_path),
                                        media_type
                                    )
                                    success_msg = f"文件 {file_path.name} 重试上传到频道 {channel_info} 成功"
                                    logger.info(success_msg)
                                    self.emit("info", success_msg)
                                    
                                    # 记录第一次成功上传的信息，用于后续复制转发
                                    if not first_upload_success:
                                        first_upload_success = True
                                        first_success_channel_id = channel_id
                                        first_success_message_id = message.id
                            except Exception as e:
                                error_msg = f"重试上传文件 {file_path.name} 到频道 {channel_info} 失败: {e}"
                                logger.error(error_msg)
                                self.emit("error", error_msg, error_type="UPLOAD_RETRY", recoverable=True)
                                continue
                        except Exception as e:
                            error_msg = f"上传文件 {file_path.name} 到频道 {channel_info} 失败: {e}"
                            logger.error(error_msg)
                            self.emit("error", error_msg, error_type="UPLOAD", recoverable=True)
                            continue
                    
                    # 上传延迟
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    error_msg = f"处理文件 {file_path.name} 上传到频道 {channel_info} 时出错: {e}"
                    logger.error(error_msg)
                    import traceback
                    error_details = traceback.format_exc()
                    logger.error(error_details)
                    self.emit("error", error_msg, error_type="PROCESS", recoverable=True, details=error_details)
                    continue
            
            # 清理缩略图
            if thumbnail_path:
                self.video_processor.delete_thumbnail(thumbnail_path)
            
            # 如果没有成功上传到任何一个频道，提示错误
            if not first_upload_success:
                error_msg = f"文件 {file_path.name} 无法上传到任何目标频道"
                logger.error(error_msg)
                self.emit("error", error_msg, error_type="ALL_FAILED", recoverable=True)
                return False
            
            return True
            
        except Exception as e:
            error_msg = f"上传文件 {file_path.name} 失败: {e}"
            logger.error(error_msg)
            import traceback
            error_details = traceback.format_exc()
            logger.error(error_details)
            self.emit("error", error_msg, error_type="UPLOAD_PROCESS", recoverable=True, details=error_details)
            
            # 清理缩略图
            if thumbnail_path:
                self.video_processor.delete_thumbnail(thumbnail_path)
                
            return False
    
    async def _upload_and_forward_media_group(self, media_files: List[Tuple[Path, str]], caption: str, 
                                     sorted_target_channels: List[Tuple[str, Optional[int], str]], 
                                     group_name: str) -> bool:
        """
        智能上传媒体组并转发到其他频道
        
        首先尝试上传到一个非禁止转发的频道，然后复制转发到其他频道
        
        Args:
            media_files: 媒体文件列表，格式为 [(file_path, media_type), ...]
            caption: 媒体组标题
            sorted_target_channels: 已排序的目标频道列表，格式为 (channel_id_or_username, resolved_id, display_name)
            group_name: 媒体组名称
            
        Returns:
            bool: 是否成功上传和转发
        """
        # 限制每个媒体组最多10个文件（Telegram API限制）
        if len(media_files) > 10:
            warning_msg = f"媒体组 {group_name} 文件数量超过10个，将只上传前10个文件"
            logger.warning(warning_msg)
            self.emit("warning", warning_msg)
            media_files = media_files[:10]
        
        # 确保媒体文件列表不为空
        if not media_files:
            warning_msg = f"媒体组 {group_name} 中没有有效媒体文件"
            logger.warning(warning_msg)
            self.emit("warning", warning_msg)
            return False
        
        # 为媒体组中的视频生成缩略图
        thumbnails = {}
        for file_path, media_type in media_files:
            # 检查是否已取消
            if self.task_context and self.task_context.cancel_token.is_cancelled:
                logger.info("上传任务已取消")
                self.emit("status", "上传任务已取消")
                # 清理已生成的缩略图
                for thumb_path in thumbnails.values():
                    self.video_processor.delete_thumbnail(thumb_path)
                return False
            
            if media_type == "video":
                try:
                    thumbnail_path = self.video_processor.extract_thumbnail(str(file_path))
                    if thumbnail_path:
                        thumbnails[str(file_path)] = thumbnail_path
                        logger.info(f"为视频 {file_path.name} 生成缩略图成功")
                        self.emit("info", f"为视频 {file_path.name} 生成缩略图成功")
                except Exception as e:
                    error_msg = f"为视频 {file_path.name} 生成缩略图失败: {e}"
                    logger.error(error_msg)
                    self.emit("error", error_msg, error_type="THUMBNAIL_GENERATION", recoverable=True)
                    # 继续上传，但没有缩略图
        
        try:
            # 检查所有频道是否都已上传所有文件
            for channel, _, channel_info in sorted_target_channels:
                # 检查是否已取消
                if self.task_context and self.task_context.cancel_token.is_cancelled:
                    logger.info("上传任务已取消")
                    self.emit("status", "上传任务已取消")
                    # 清理缩略图
                    for thumb_path in thumbnails.values():
                        self.video_processor.delete_thumbnail(thumb_path)
                    return False
                
                # 等待暂停恢复
                if self.task_context:
                    await self.task_context.wait_if_paused()
                
                # 检查是否已上传到此频道
                all_uploaded = True
                for file_path, _ in media_files:
                    if not self.history_manager.is_file_uploaded(str(file_path), channel):
                        all_uploaded = False
                        break
                
                if all_uploaded:
                    logger.debug(f"媒体组 {group_name} 已上传到频道 {channel_info}，跳过")
                    self.emit("info", f"媒体组 {group_name} 已上传到频道 {channel_info}，跳过")
                    continue
            
            # 创建媒体组
            media_group = []
            for i, (file_path, media_type) in enumerate(media_files):
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
            
            # 记录是否已经成功上传到某个非禁止转发频道
            first_upload_success = False
            first_success_channel_id = None
            first_success_message_ids = None  # 对于媒体组，可能有多个消息ID
            
            # 上传媒体组到每个目标频道
            for channel, channel_id, channel_info in sorted_target_channels:
                # 检查是否已取消
                if self.task_context and self.task_context.cancel_token.is_cancelled:
                    logger.info("上传任务已取消")
                    self.emit("status", "上传任务已取消")
                    # 清理缩略图
                    for thumb_path in thumbnails.values():
                        self.video_processor.delete_thumbnail(thumb_path)
                    return False
                
                # 等待暂停恢复
                if self.task_context:
                    await self.task_context.wait_if_paused()
                
                # 检查是否已上传到此频道
                all_uploaded = True
                for file_path, _ in media_files:
                    if not self.history_manager.is_file_uploaded(str(file_path), channel):
                        all_uploaded = False
                        break
                
                if all_uploaded:
                    logger.debug(f"媒体组 {group_name} 已上传到频道 {channel_info}，跳过")
                    self.emit("info", f"媒体组 {group_name} 已上传到频道 {channel_info}，跳过")
                    continue
                
                try:
                    # 如果尚未解析频道ID，现在解析
                    if channel_id is None:
                        channel_id = await self.channel_resolver.get_channel_id(channel)
                        channel_info, _ = await self.channel_resolver.format_channel_info(channel_id)
                    
                    # 发送状态更新
                    status_msg = f"正在上传媒体组 {group_name} 到频道 {channel_info}"
                    logger.info(status_msg)
                    self.emit("status", status_msg)
                    
                    # 如果已经成功上传到非禁止转发频道，使用复制转发方式
                    if first_upload_success and first_success_channel_id and first_success_message_ids:
                        info_msg = f"使用复制转发方式将媒体组 {group_name} 从已上传频道转发到 {channel_info}"
                        logger.info(info_msg)
                        self.emit("info", info_msg)
                        
                        try:
                            if len(media_group) == 1:
                                # 单个媒体使用copy_message
                                forwarded = await self.client.copy_message(
                                    chat_id=channel_id,
                                    from_chat_id=first_success_channel_id,
                                    message_id=first_success_message_ids[0]
                                )
                            else:
                                # 媒体组使用copy_media_group
                                forwarded = await self.client.copy_media_group(
                                    chat_id=channel_id,
                                    from_chat_id=first_success_channel_id,
                                    message_id=first_success_message_ids[0]
                                )
                            
                            # 记录上传历史
                            for file_path, media_type in media_files:
                                self.history_manager.add_upload_record(
                                    str(file_path),
                                    channel,
                                    os.path.getsize(file_path),
                                    media_type
                                )
                            
                            success_msg = f"媒体组 {group_name} 使用copy_media_group复制到频道 {channel_info} 成功"
                            logger.info(success_msg)
                            self.emit("info", success_msg)
                            
                            # 添加上传延迟
                            delay_time = self.upload_config.delay_between_uploads if hasattr(self.upload_config, 'delay_between_uploads') else 2
                            delay_msg = f"等待 {delay_time} 秒后继续下一个上传"
                            logger.debug(delay_msg)
                            self.emit("debug", delay_msg)
                            await asyncio.sleep(delay_time)
                        except FloodWait as e:
                            wait_msg = f"复制转发遇到限制，等待 {e.x} 秒后重试"
                            logger.warning(wait_msg)
                            self.emit("warning", wait_msg)
                            await asyncio.sleep(e.x)
                            # 重试复制转发
                            try:
                                if len(media_group) == 1:
                                    # 单个媒体使用copy_message
                                    forwarded = await self.client.copy_message(
                                        chat_id=channel_id,
                                        from_chat_id=first_success_channel_id,
                                        message_id=first_success_message_ids[0]
                                    )
                                else:
                                    # 媒体组使用copy_media_group
                                    forwarded = await self.client.copy_media_group(
                                        chat_id=channel_id,
                                        from_chat_id=first_success_channel_id,
                                        message_id=first_success_message_ids[0]
                                    )
                                
                                # 记录上传历史
                                for file_path, media_type in media_files:
                                    self.history_manager.add_upload_record(
                                        str(file_path),
                                        channel,
                                        os.path.getsize(file_path),
                                        media_type
                                    )
                                
                                success_msg = f"媒体组 {group_name} 重试使用copy_media_group复制到频道 {channel_info} 成功"
                                logger.info(success_msg)
                                self.emit("info", success_msg)
                                
                                # 添加上传延迟
                                delay_time = self.upload_config.delay_between_uploads if hasattr(self.upload_config, 'delay_between_uploads') else 2
                                delay_msg = f"等待 {delay_time} 秒后继续下一个上传"
                                logger.debug(delay_msg)
                                self.emit("debug", delay_msg)
                                await asyncio.sleep(delay_time)
                            except Exception as e:
                                error_msg = f"重试使用copy_media_group复制媒体组 {group_name} 到频道 {channel_info} 失败: {e}"
                                logger.error(error_msg)
                                self.emit("error", error_msg, error_type="COPY_MEDIA_GROUP_RETRY", recoverable=True)
                                continue
                        except Exception as e:
                            error_msg = f"使用copy_media_group复制媒体组 {group_name} 到频道 {channel_info} 失败: {e}"
                            logger.error(error_msg)
                            self.emit("error", error_msg, error_type="COPY_MEDIA_GROUP", recoverable=True)
                            continue
                    else:
                        # 首次上传，直接发送媒体组
                        info_msg = f"直接上传媒体组 {group_name} 到频道 {channel_info}"
                        logger.info(info_msg)
                        self.emit("info", info_msg)
                        
                        try:
                            if len(media_group) == 1:
                                # 单个媒体
                                if isinstance(media_group[0], InputMediaPhoto):
                                    message = await self.client.send_photo(
                                        chat_id=channel_id,
                                        photo=media_group[0].media,
                                        caption=media_group[0].caption
                                    )
                                    messages = [message]
                                elif isinstance(media_group[0], InputMediaVideo):
                                    message = await self.client.send_video(
                                        chat_id=channel_id,
                                        video=media_group[0].media,
                                        caption=media_group[0].caption,
                                        supports_streaming=True,
                                        thumb=thumbnails.get(media_group[0].media)
                                    )
                                    messages = [message]
                                elif isinstance(media_group[0], InputMediaDocument):
                                    message = await self.client.send_document(
                                        chat_id=channel_id,
                                        document=media_group[0].media,
                                        caption=media_group[0].caption
                                    )
                                    messages = [message]
                                elif isinstance(media_group[0], InputMediaAudio):
                                    message = await self.client.send_audio(
                                        chat_id=channel_id,
                                        audio=media_group[0].media,
                                        caption=media_group[0].caption
                                    )
                                    messages = [message]
                                else:
                                    error_msg = f"不支持的媒体类型: {type(media_group[0])}"
                                    logger.error(error_msg)
                                    self.emit("error", error_msg, error_type="UNSUPPORTED_MEDIA", recoverable=True)
                                    continue
                            else:
                                # 多个媒体组成的媒体组
                                messages = await self.client.send_media_group(
                                    chat_id=channel_id,
                                    media=media_group
                                )
                            
                            # 记录上传历史
                            for file_path, media_type in media_files:
                                self.history_manager.add_upload_record(
                                    str(file_path),
                                    channel,
                                    os.path.getsize(file_path),
                                    media_type
                                )
                            
                            success_msg = f"媒体组 {group_name} 上传到频道 {channel_info} 成功"
                            logger.info(success_msg)
                            self.emit("info", success_msg)
                            
                            # 记录第一次成功上传的信息，用于后续复制转发
                            if not first_upload_success and messages:
                                first_upload_success = True
                                first_success_channel_id = channel_id
                                first_success_message_ids = [msg.id for msg in messages]
                        except FloodWait as e:
                            wait_msg = f"上传媒体组遇到限制，等待 {e.x} 秒后重试"
                            logger.warning(wait_msg)
                            self.emit("warning", wait_msg)
                            await asyncio.sleep(e.x)
                            # 重试上传
                            try:
                                if len(media_group) == 1:
                                    # 单个媒体
                                    if isinstance(media_group[0], InputMediaPhoto):
                                        message = await self.client.send_photo(
                                            chat_id=channel_id,
                                            photo=media_group[0].media,
                                            caption=media_group[0].caption
                                        )
                                        messages = [message]
                                    elif isinstance(media_group[0], InputMediaVideo):
                                        message = await self.client.send_video(
                                            chat_id=channel_id,
                                            video=media_group[0].media,
                                            caption=media_group[0].caption,
                                            supports_streaming=True,
                                            thumb=thumbnails.get(media_group[0].media)
                                        )
                                        messages = [message]
                                    elif isinstance(media_group[0], InputMediaDocument):
                                        message = await self.client.send_document(
                                            chat_id=channel_id,
                                            document=media_group[0].media,
                                            caption=media_group[0].caption
                                        )
                                        messages = [message]
                                    elif isinstance(media_group[0], InputMediaAudio):
                                        message = await self.client.send_audio(
                                            chat_id=channel_id,
                                            audio=media_group[0].media,
                                            caption=media_group[0].caption
                                        )
                                        messages = [message]
                                    else:
                                        error_msg = f"不支持的媒体类型: {type(media_group[0])}"
                                        logger.error(error_msg)
                                        self.emit("error", error_msg, error_type="UNSUPPORTED_MEDIA", recoverable=True)
                                        continue
                                else:
                                    # 多个媒体组成的媒体组
                                    messages = await self.client.send_media_group(
                                        chat_id=channel_id,
                                        media=media_group
                                    )
                                
                                # 记录上传历史
                                for file_path, media_type in media_files:
                                    self.history_manager.add_upload_record(
                                        str(file_path),
                                        channel,
                                        os.path.getsize(file_path),
                                        media_type
                                    )
                                
                                success_msg = f"媒体组 {group_name} 重试上传到频道 {channel_info} 成功"
                                logger.info(success_msg)
                                self.emit("info", success_msg)
                                
                                # 记录第一次成功上传的信息，用于后续复制转发
                                if not first_upload_success and messages:
                                    first_upload_success = True
                                    first_success_channel_id = channel_id
                                    first_success_message_ids = [msg.id for msg in messages]
                            except Exception as e:
                                error_msg = f"重试上传媒体组 {group_name} 到频道 {channel_info} 失败: {e}"
                                logger.error(error_msg)
                                self.emit("error", error_msg, error_type="UPLOAD_RETRY", recoverable=True)
                                continue
                        except Exception as e:
                            error_msg = f"上传媒体组 {group_name} 到频道 {channel_info} 失败: {e}"
                            logger.error(error_msg)
                            self.emit("error", error_msg, error_type="UPLOAD", recoverable=True)
                            continue
                    
                    # 上传延迟
                    await asyncio.sleep(2)
                
                except Exception as e:
                    error_msg = f"处理媒体组 {group_name} 上传到频道 {channel_info} 时出错: {e}"
                    logger.error(error_msg)
                    import traceback
                    error_details = traceback.format_exc()
                    logger.error(error_details)
                    self.emit("error", error_msg, error_type="PROCESS", recoverable=True, details=error_details)
                    continue
            
            # 清理缩略图
            for thumbnail_path in thumbnails.values():
                self.video_processor.delete_thumbnail(thumbnail_path)
            
            # 如果没有成功上传到任何一个频道，提示错误
            if not first_upload_success:
                error_msg = f"媒体组 {group_name} 无法上传到任何目标频道"
                logger.error(error_msg)
                self.emit("error", error_msg, error_type="ALL_FAILED", recoverable=True)
                return False
            
            return True
            
        except Exception as e:
            error_msg = f"上传媒体组 {group_name} 失败: {e}"
            logger.error(error_msg)
            import traceback
            error_details = traceback.format_exc()
            logger.error(error_details)
            self.emit("error", error_msg, error_type="UPLOAD_PROCESS", recoverable=True, details=error_details)
            
            # 清理缩略图
            for thumbnail_path in thumbnails.values():
                self.video_processor.delete_thumbnail(thumbnail_path)
                
            return False 