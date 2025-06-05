"""
媒体上传器，用于上传媒体组到目标频道
"""

import asyncio
import shutil
from pathlib import Path
from typing import List, Tuple, Dict, Union, Optional, Any

from pyrogram import Client
from pyrogram.types import Message, InputMediaPhoto, InputMediaVideo, InputMediaDocument, InputMediaAudio
from pyrogram.errors import FloodWait

from src.modules.forward.media_group_download import MediaGroupDownload
from src.utils.video_processor import VideoProcessor
from src.utils.logger import get_logger

_logger = get_logger()

class MediaUploader:
    """
    媒体上传器，负责将下载的媒体组上传到目标频道
    """
    
    def __init__(self, client: Client, history_manager=None, general_config: Dict[str, Any] = None):
        """
        初始化媒体上传器
        
        Args:
            client: Pyrogram客户端实例
            history_manager: 历史记录管理器实例，用于记录已上传的消息
            general_config: 通用配置，包含重试次数等
        """
        self.client = client
        self.history_manager = history_manager
        self.general_config = general_config or {}
        self.video_processor = VideoProcessor()
        self._video_dimensions = {}
    
    async def upload_media_group_to_channel(self, 
                                          media_group: List[Union[InputMediaPhoto, InputMediaVideo, InputMediaDocument, InputMediaAudio]], 
                                          media_group_download: MediaGroupDownload, 
                                          target_channel: str, 
                                          target_id: int, 
                                          target_info: str,
                                          thumbnails: Dict[str, str] = None) -> Union[List[Message], bool]:
        """
        上传媒体组到指定频道，处理重试逻辑
        
        Args:
            media_group: 要上传的媒体组
            media_group_download: 媒体组下载结果
            target_channel: 目标频道标识符
            target_id: 目标频道ID
            target_info: 目标频道信息
            thumbnails: 缩略图字典，键为文件路径，值为缩略图路径
            
        Returns:
            Union[List[Message], bool]: 上传成功时返回消息对象列表，失败时返回False
        """
        retry_count = 0
        max_retries = self.general_config.get('max_retries', 3)
        
        message_ids = [m.id for m in media_group_download.messages]
        group_id = "单条消息" if len(message_ids) == 1 else f"媒体组(共{len(message_ids)}条)"
        
        # 检查媒体组是否为空
        if not media_group:
            _logger.error(f"媒体组为空，无法上传")
            return False
            
        # 检查每个媒体项的文件路径
        for i, media_item in enumerate(media_group):
            media_file = getattr(media_item, 'media', None)
            if media_file is None:
                _logger.error(f"媒体项 {i+1}/{len(media_group)} 没有media属性")
                return False
                
            if isinstance(media_file, str):
                if not Path(media_file).exists():
                    _logger.error(f"媒体文件不存在: {media_file}")
                    return False
                    
                # 记录文件信息以便调试
                # try:
                #     file_size = Path(media_file).stat().st_size
                #     _logger.info(f"媒体文件 {i+1}/{len(media_group)}: {media_file}, 大小: {file_size} 字节")
                # except Exception as e:
                #     _logger.warning(f"无法获取媒体文件信息: {media_file}, 错误: {e}")
        
        while retry_count < max_retries:          
            try:
                if len(media_group) == 1:
                    # 单个媒体
                    media_item = media_group[0]
                    sent_message = None
                    
                    if isinstance(media_item, InputMediaPhoto):
                        debug_message = f"尝试发送照片到 {target_info}"
                        _logger.debug(debug_message)
                        
                        sent_message = await self.client.send_photo(
                            chat_id=target_id,
                            photo=media_item.media,
                            caption=media_item.caption,
                            disable_notification=True
                        )
                    elif isinstance(media_item, InputMediaVideo):
                        # 使用缩略图
                        thumb = None
                        if thumbnails:
                            thumb = thumbnails.get(media_item.media)
                            if thumb and not Path(thumb).exists():
                                _logger.warning(f"缩略图文件不存在: {thumb}，不使用缩略图")
                                thumb = None
                        
                        debug_message = f"尝试发送视频到 {target_info}"
                        _logger.debug(debug_message)
                        
                        sent_message = await self.client.send_video(
                            chat_id=target_id,
                            video=media_item.media,
                            caption=media_item.caption,
                            supports_streaming=True,
                            thumb=thumb,
                            width=self._get_video_width(media_item.media),
                            height=self._get_video_height(media_item.media),
                            duration=self._get_video_duration(media_item.media),
                            disable_notification=True
                        )
                    elif isinstance(media_item, InputMediaDocument):
                        debug_message = f"尝试发送文档到 {target_info}"
                        _logger.debug(debug_message)
                        
                        sent_message = await self.client.send_document(
                            chat_id=target_id,
                            document=media_item.media,
                            caption=media_item.caption,
                            disable_notification=True
                        )
                    elif isinstance(media_item, InputMediaAudio):
                        debug_message = f"尝试发送音频到 {target_info}"
                        _logger.debug(debug_message)
                        
                        sent_message = await self.client.send_audio(
                            chat_id=target_id,
                            audio=media_item.media,
                            caption=media_item.caption,
                            disable_notification=True
                        )
                    else:
                        warning_message = f"未知媒体类型: {type(media_item)}"
                        _logger.warning(warning_message)
                        return False
                    
                    # 确保sent_message存在
                    if not sent_message:
                        _logger.warning(f"媒体上传成功，但没有获取到消息对象")
                        sent_messages = []
                    else:
                        sent_messages = [sent_message]
                else:
                    # 媒体组
                    debug_message = f"尝试发送媒体组到 {target_info}"
                    _logger.debug(debug_message)
                    
                    sent_messages = await self.client.send_media_group(
                        chat_id=target_id,
                        media=media_group,
                        disable_notification=True
                    )
                
                # 记录转发历史
                if self.history_manager:
                    for message in media_group_download.messages:
                        self.history_manager.add_forward_record(
                            media_group_download.source_channel,
                            message.id,
                            target_channel,
                            media_group_download.source_id
                        )
                
                # 上传成功后立即清理缩略图
                if thumbnails:
                    debug_message = f"上传成功，清理缩略图: {group_id} 到 {target_info}"
                    _logger.debug(debug_message)
                    for video_path, thumbnail_path in thumbnails.items():
                        self.video_processor.delete_thumbnail(thumb_path=thumbnail_path)
                        _logger.debug(f"已删除缩略图: {thumbnail_path}")
                
                success_message = f"媒体上传到 {target_info} 成功"
                _logger.info(success_message)
                
                # 返回消息对象列表，用于后续复制
                return sent_messages
            
            except FloodWait as e:
                warning_message = f"上传媒体时遇到限制，等待 {e.x} 秒"
                _logger.warning(warning_message)
                
                try:
                    await asyncio.sleep(e.x)
                except asyncio.CancelledError:
                    warning_message = "上传任务已取消(FloodWait等待期间)"
                    _logger.warning(warning_message)
                    return False
            
            except Exception as e:
                retry_count += 1
                error_message = f"上传媒体到频道 {target_info} 失败 (尝试 {retry_count}/{max_retries}): {str(e)}"
                _logger.error(error_message)
                
                # 记录详细错误信息
                import traceback
                error_details = traceback.format_exc()
                _logger.error(f"错误详情:\n{error_details}")
                
                # 检查是否是无效文件错误
                if "Invalid file" in str(e):
                    # 记录每个媒体项的详细信息
                    for i, media_item in enumerate(media_group):
                        media_file = getattr(media_item, 'media', None)
                        item_type = type(media_item).__name__
                        _logger.error(f"媒体项 {i+1}/{len(media_group)} 类型: {item_type}, 文件: {media_file}")
                
                if retry_count >= max_retries:
                    break
                
                status_message = f"将在 {2 * retry_count} 秒后重试上传 {group_id}"
                _logger.info(status_message)
                
                # 指数退避
                try:
                    await asyncio.sleep(2 * retry_count)
                except asyncio.CancelledError:
                    warning_message = "上传任务已取消(重试等待期间)"
                    _logger.warning(warning_message)
                    return False
        
        error_message = f"上传媒体到 {target_info} 失败，已达到最大重试次数 {max_retries}"
        _logger.error(error_message)
        return False
    
    def prepare_media_group_for_upload(self, 
                                       media_group_download: MediaGroupDownload, 
                                       thumbnails: Dict[str, str] = None) -> List[Union[InputMediaPhoto, InputMediaVideo, InputMediaDocument, InputMediaAudio]]:
        """
        为上传准备媒体组
        
        Args:
            media_group_download: 媒体组下载结果
            thumbnails: 缩略图字典，键为文件路径，值为缩略图路径
            
        Returns:
            List[Union[InputMediaPhoto, InputMediaVideo, InputMediaDocument, InputMediaAudio]]: 准备好的媒体组
        """
        media_group = []
        file_caption = media_group_download.caption
        
        for file_path, media_type in media_group_download.downloaded_files:
            file_path_str = str(file_path)
            
            # 检查文件是否存在
            if not Path(file_path_str).exists():
                _logger.warning(f"文件不存在: {file_path_str}，跳过")
                continue
                
            # 只为第一个文件添加标题
            if media_group and file_caption:
                file_caption = None
            
            try:
                # 根据媒体类型创建不同的InputMedia对象
                if media_type == "photo":
                    media_group.append(InputMediaPhoto(file_path_str, caption=file_caption))
                elif media_type == "video":
                    # 获取缩略图路径
                    thumb = None
                    if thumbnails and file_path_str in thumbnails:
                        thumb = thumbnails.get(file_path_str)
                        if thumb and not Path(thumb).exists():
                            _logger.warning(f"缩略图文件不存在: {thumb}，不使用缩略图")
                            thumb = None
                            
                    media_group.append(InputMediaVideo(
                        file_path_str, 
                        caption=file_caption, 
                        supports_streaming=True,
                        thumb=thumb,
                        width=self._get_video_width(file_path_str),
                        height=self._get_video_height(file_path_str),
                        duration=self._get_video_duration(file_path_str)
                    ))
                elif media_type == "document":
                    media_group.append(InputMediaDocument(file_path_str, caption=file_caption))
                elif media_type == "audio":
                    media_group.append(InputMediaAudio(file_path_str, caption=file_caption))
                else:
                    _logger.warning(f"不支持的媒体类型: {media_type}，文件: {file_path_str}")
            except Exception as e:
                _logger.error(f"创建媒体对象失败: {e}，文件: {file_path_str}, 类型: {media_type}")
                continue
        
        return media_group
    
    def generate_thumbnails(self, media_group_download: MediaGroupDownload) -> Dict[str, str]:
        """
        为视频文件生成缩略图
        
        Args:
            media_group_download: 媒体组下载结果
            
        Returns:
            Dict[str, str]: 缩略图字典，键为文件路径，值为缩略图路径
        """
        thumbnails = {}
        
        for file_path, media_type in media_group_download.downloaded_files:
            if media_type == "video":
                try:
                    thumbnail_result = self.video_processor.extract_thumbnail(str(file_path))
                    thumbnail_path = None
                    width = None
                    height = None
                    duration = None
                    
                    # 处理返回值可能是元组的情况
                    if isinstance(thumbnail_result, tuple) and len(thumbnail_result) >= 1:
                        if len(thumbnail_result) >= 4:
                            thumbnail_path, width, height, duration = thumbnail_result
                            # 确保时长是整数类型
                            if duration is not None:
                                duration = int(duration)
                        elif len(thumbnail_result) >= 3:
                            thumbnail_path, width, height = thumbnail_result
                        else:
                            thumbnail_path = thumbnail_result[0]
                    else:
                        thumbnail_path = thumbnail_result
                    
                    if thumbnail_path:
                        thumbnails[str(file_path)] = thumbnail_path
                        # 保存视频尺寸信息
                        if width and height:
                            self._video_dimensions[str(file_path)] = (width, height)
                        debug_message = f"为视频 {file_path.name} 生成缩略图成功"
                        _logger.debug(debug_message)
                except Exception as e:
                    warning_message = f"为视频 {file_path.name} 生成缩略图失败: {e}"
                    _logger.warning(warning_message)
        
        return thumbnails
    
    def cleanup_thumbnails(self, thumbnails: Dict[str, str]):
        """
        清理所有缩略图
        
        Args:
            thumbnails: 缩略图字典，键为文件路径，值为缩略图路径
        """
        if thumbnails and thumbnails.values():
            for thumbnail_path in thumbnails.values():
                if thumbnail_path:  # 确保缩略图路径有效
                    self.video_processor.delete_thumbnail(thumbnail_path)
                    _logger.debug(f"清理缩略图: {thumbnail_path}")
    
    def cleanup_media_group_dir(self, media_group_dir: Path):
        """
        清理媒体组目录，并递归清理空的父目录
        
        Args:
            media_group_dir: 媒体组目录
        """
        if media_group_dir and media_group_dir.exists():
            try:
                # 删除媒体组目录
                shutil.rmtree(media_group_dir)
                _logger.debug(f"已删除媒体组目录: {media_group_dir}")
                
                # 递归清理空的父目录
                self._cleanup_empty_parent_dirs(media_group_dir.parent)
                
            except Exception as e:
                _logger.error(f"删除媒体组目录失败: {e}")
    
    def _cleanup_empty_parent_dirs(self, dir_path: Path):
        """
        递归清理空的父目录，但不删除根临时目录
        
        Args:
            dir_path: 要检查和清理的目录路径
        """
        try:
            # 定义不应删除的根目录（如tmp、tmp/monitor等）
            protected_dirs = {'tmp', 'monitor', 'forward'}
            
            # 如果目录不存在或者是受保护的目录，停止清理
            if not dir_path.exists() or dir_path.name in protected_dirs:
                return
            
            # 检查目录是否为空
            try:
                # 列出目录中的所有项目
                dir_contents = list(dir_path.iterdir())
                
                # 如果目录为空，删除它并继续检查父目录
                if not dir_contents:
                    _logger.debug(f"发现空目录，准备删除: {dir_path}")
                    dir_path.rmdir()
                    _logger.debug(f"已删除空目录: {dir_path}")
                    
                    # 递归检查父目录
                    self._cleanup_empty_parent_dirs(dir_path.parent)
                else:
                    # 目录不为空，停止清理
                    _logger.debug(f"目录不为空，停止清理: {dir_path} (包含 {len(dir_contents)} 个项目)")
                    
            except PermissionError:
                _logger.debug(f"没有权限访问目录: {dir_path}")
            except OSError as e:
                _logger.debug(f"无法访问目录 {dir_path}: {e}")
                
        except Exception as e:
            _logger.debug(f"清理空父目录时发生错误: {e}")
            # 这里只记录debug级别的日志，因为清理失败不是致命错误
    
    def _get_video_width(self, video_path: str) -> Optional[int]:
        """
        获取视频宽度
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            Optional[int]: 视频宽度，如果无法获取则返回None
        """
        # 首先检查缓存
        if video_path in self._video_dimensions:
            return self._video_dimensions[video_path][0]
        
        # 如果缓存中没有，使用video_processor获取
        dimensions = self.video_processor.get_video_dimensions(video_path)
        if dimensions:
            # 缓存结果
            self._video_dimensions[video_path] = dimensions
            return dimensions[0]
        return None
    
    def _get_video_height(self, video_path: str) -> Optional[int]:
        """
        获取视频高度
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            Optional[int]: 视频高度，如果无法获取则返回None
        """
        # 首先检查缓存
        if video_path in self._video_dimensions:
            return self._video_dimensions[video_path][1]
        
        # 如果缓存中没有，使用video_processor获取
        dimensions = self.video_processor.get_video_dimensions(video_path)
        if dimensions:
            # 缓存结果
            self._video_dimensions[video_path] = dimensions
            return dimensions[1]
        return None
    
    def _get_video_duration(self, video_path: str) -> Optional[int]:
        """
        获取视频时长
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            Optional[int]: 视频时长(秒)，如果无法获取则返回None
        """
        # 使用video_processor获取
        duration = self.video_processor.get_video_duration(video_path)
        # 将浮点数转换为整数，避免'float' object has no attribute 'to_bytes'错误
        if duration is not None:
            return int(duration)
        return None 