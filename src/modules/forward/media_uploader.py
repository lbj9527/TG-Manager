"""
媒体上传器，用于上传媒体组到目标频道
"""

import asyncio
import shutil
from pathlib import Path
from typing import List, Tuple, Dict, Union, Optional, Any
import time
import os
from concurrent.futures import ThreadPoolExecutor

from pyrogram import Client
from pyrogram.types import Message, InputMediaPhoto, InputMediaVideo, InputMediaDocument, InputMediaAudio
from pyrogram.errors import FloodWait

from src.modules.forward.media_group_download import MediaGroupDownload
from src.utils.video_processor import VideoProcessor
from src.utils.logger import get_logger
from src.utils.translation_manager import tr
from src.utils.flood_wait_handler import FloodWaitHandler, execute_with_flood_wait

# 导入原生的 FloodWait 处理器
try:
    from src.utils.flood_wait_handler import FloodWaitHandler, execute_with_flood_wait
    FLOOD_WAIT_HANDLER_AVAILABLE = True
except ImportError:
    FLOOD_WAIT_HANDLER_AVAILABLE = False

_logger = get_logger()

class MediaUploader:
    """
    媒体上传器，负责将下载的媒体组上传到目标频道
    集成原生FloodWait处理器，提供智能限流处理
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
        self._video_durations = {}
        
        # 选择最佳可用的FloodWait处理器
        if FLOOD_WAIT_HANDLER_AVAILABLE:
            self._flood_wait_method = "native"
            self.flood_wait_handler = FloodWaitHandler(max_retries=3, base_delay=1.0)
            _logger.info("MediaUploader: 使用原生FloodWait处理器")
        else:
            self._flood_wait_method = "none"
            _logger.warning("MediaUploader: 未找到可用的FloodWait处理器")
    
    async def _execute_with_flood_wait(self, func, *args, **kwargs):
        """
        统一的FloodWait处理执行器，根据可用性选择最佳处理器
        
        Args:
            func: 要执行的函数
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            函数执行结果
        """
        max_retries = self.general_config.get('max_retries', 3)
        
        if self._flood_wait_method == "native":
            return await self.flood_wait_handler.handle_flood_wait(func, *args, **kwargs)
        else:
            # 没有FloodWait处理器，直接执行
            return await func(*args, **kwargs)
    
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
        message_ids = [m.id for m in media_group_download.messages]
        group_id = tr("ui.forward.log.single_message") if len(message_ids) == 1 else tr("ui.forward.log.media_group_count", count=len(message_ids))
        
        # 检查媒体组是否为空
        if not media_group:
            _logger.warning(f"媒体组为空（可能所有文件都是0字节），跳过上传到 {target_info}")
            return False
        
        # 统计媒体组信息
        media_group_size = len(media_group)
        _logger.info(f"准备上传 {media_group_size} 个有效媒体文件到 {target_info}")
            
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
        
        # 使用FloodWaitHandler处理上传
        async def upload_operation():
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
            
            return sent_messages
        
        # 使用FloodWaitHandler执行上传操作
        upload_result = await self._execute_with_flood_wait(upload_operation)
        
        if upload_result is not False and upload_result is not None:
            sent_messages = upload_result
            
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
        else:
            error_message = f"上传媒体到 {target_info} 失败，已达到最大重试次数 {max_retries}"
            _logger.error(error_message)
            return False
    
    async def prepare_media_group_for_upload_parallel(self, 
                                                     media_group_download: MediaGroupDownload, 
                                                     thumbnails: Dict[str, str] = None) -> List[Union[InputMediaPhoto, InputMediaVideo, InputMediaDocument, InputMediaAudio]]:
        """
        并行方式为上传准备媒体组，优化性能
        
        Args:
            media_group_download: 媒体组下载结果
            thumbnails: 缩略图字典，键为文件路径，值为缩略图路径
            
        Returns:
            List[Union[InputMediaPhoto, InputMediaVideo, InputMediaDocument, InputMediaAudio]]: 准备好的媒体组
        """
        import asyncio
        
        file_caption = media_group_download.caption
        
        async def create_input_media(index: int, file_info: Tuple) -> Optional[Union[InputMediaPhoto, InputMediaVideo, InputMediaDocument, InputMediaAudio]]:
            """
            异步创建单个InputMedia对象
            
            Args:
                index: 文件索引
                file_info: (file_path, media_type) 元组
                
            Returns:
                创建的InputMedia对象或None
            """
            file_path, media_type = file_info
            file_path_str = str(file_path)
            
            try:
                # 异步检查文件是否存在
                import aiofiles.os
                if not await aiofiles.os.path.exists(file_path_str):
                    _logger.warning(f"文件不存在: {file_path_str}，跳过")
                    return None
                
                # 检查文件大小，过滤0字节文件
                try:
                    file_size = await aiofiles.os.path.getsize(file_path_str)
                    if file_size == 0:
                        _logger.warning(f"文件大小为0B，跳过上传: {file_path_str}")
                        return None
                    _logger.debug(f"文件 {file_path.name} 大小: {file_size} 字节")
                except Exception as size_error:
                    _logger.error(f"无法获取文件大小: {file_path_str}, 错误: {size_error}")
                    return None
                    
                # 只为第一个文件添加标题
                current_caption = file_caption if index == 0 else None
                
                # 根据媒体类型创建不同的InputMedia对象
                if media_type == "photo":
                    return InputMediaPhoto(file_path_str, caption=current_caption)
                    
                elif media_type == "video":
                    # 并行获取视频元数据和缩略图
                    async def get_video_metadata():
                        return await asyncio.gather(
                            self._get_video_width_async(file_path_str),
                            self._get_video_height_async(file_path_str),
                            self._get_video_duration_async(file_path_str),
                            return_exceptions=True
                        )
                    
                    width, height, duration = await get_video_metadata()
                    
                    # 处理可能的异常结果
                    width = width if not isinstance(width, Exception) else None
                    height = height if not isinstance(height, Exception) else None
                    duration = duration if not isinstance(duration, Exception) else None
                    
                    # 获取缩略图路径
                    thumb = None
                    if thumbnails and file_path_str in thumbnails:
                        thumb = thumbnails.get(file_path_str)
                        if thumb and not await aiofiles.os.path.exists(thumb):
                            _logger.warning(f"缩略图文件不存在: {thumb}，不使用缩略图")
                            thumb = None
                            
                    return InputMediaVideo(
                        file_path_str, 
                        caption=current_caption, 
                        supports_streaming=True,
                        thumb=thumb,
                        width=width,
                        height=height,
                        duration=duration
                    )
                    
                elif media_type == "document":
                    return InputMediaDocument(file_path_str, caption=current_caption)
                    
                elif media_type == "audio":
                    return InputMediaAudio(file_path_str, caption=current_caption)
                    
                else:
                    _logger.warning(f"不支持的媒体类型: {media_type}，文件: {file_path_str}")
                    return None
                    
            except Exception as e:
                _logger.error(f"并行创建媒体对象失败: {e}，文件: {file_path_str}, 类型: {media_type}")
                return None
        
        # 并行创建所有InputMedia对象
        tasks = [
            create_input_media(i, file_info) 
            for i, file_info in enumerate(media_group_download.downloaded_files)
        ]
        
        _logger.debug(f"开始并行创建 {len(tasks)} 个InputMedia对象")
        start_time = time.time()
        
        # 并行执行所有任务
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        preparation_time = time.time() - start_time
        _logger.debug(f"并行InputMedia准备完成，耗时: {preparation_time:.2f}秒")
        
        # 过滤掉None和异常结果
        media_group = []
        original_file_count = len(tasks)
        zero_size_files = []
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                _logger.error(f"创建第{i+1}个InputMedia对象时发生异常: {result}")
            elif result is not None:
                media_group.append(result)
            else:
                # 记录被过滤的文件信息
                if i < len(media_group_download.downloaded_files):
                    file_path, media_type = media_group_download.downloaded_files[i]
                    zero_size_files.append(f"{file_path.name}({media_type})")
        
        # 记录过滤结果
        if zero_size_files:
            _logger.warning(f"过滤掉 {len(zero_size_files)} 个0字节文件: {', '.join(zero_size_files)}")
        
        valid_file_count = len(media_group)
        filtered_count = original_file_count - valid_file_count
        
        if filtered_count > 0:
            _logger.info(f"媒体组重组完成: 原有{original_file_count}个文件，过滤{filtered_count}个无效文件，剩余{valid_file_count}个有效文件")
        
        # 如果所有文件都被过滤掉了
        if not media_group:
            _logger.warning(f"所有文件都被过滤（0字节或异常），无法创建媒体组")
            return []
        
        _logger.info(f"成功创建 {len(media_group)}/{original_file_count} 个有效InputMedia对象")
        return media_group

    async def _get_video_width_async(self, video_path: str) -> Optional[int]:
        """
        异步获取视频宽度
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            Optional[int]: 视频宽度，如果无法获取则返回None
        """
        # 首先检查缓存
        if video_path in self._video_dimensions:
            return self._video_dimensions[video_path][0]
        
        # 异步获取视频尺寸
        try:
            loop = asyncio.get_event_loop()
            dimensions = await loop.run_in_executor(
                None, 
                self.video_processor.get_video_dimensions,
                video_path
            )
            if dimensions and len(dimensions) >= 2:
                width, height = dimensions[:2]
                self._video_dimensions[video_path] = (width, height)
                return width
        except Exception as e:
            _logger.debug(f"异步获取视频宽度失败: {e}")
        
        return None

    async def _get_video_height_async(self, video_path: str) -> Optional[int]:
        """
        异步获取视频高度
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            Optional[int]: 视频高度，如果无法获取则返回None
        """
        # 首先检查缓存
        if video_path in self._video_dimensions:
            return self._video_dimensions[video_path][1]
        
        # 异步获取视频尺寸
        try:
            loop = asyncio.get_event_loop()
            dimensions = await loop.run_in_executor(
                None, 
                self.video_processor.get_video_dimensions,
                video_path
            )
            if dimensions and len(dimensions) >= 2:
                width, height = dimensions[:2]
                self._video_dimensions[video_path] = (width, height)
                return height
        except Exception as e:
            _logger.debug(f"异步获取视频高度失败: {e}")
        
        return None

    async def _get_video_duration_async(self, video_path: str) -> Optional[int]:
        """
        异步获取视频时长
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            Optional[int]: 视频时长（秒），如果无法获取则返回None
        """
        # 首先检查缓存
        if video_path in self._video_durations:
            return self._video_durations[video_path]
        
        # 异步获取视频时长
        try:
            loop = asyncio.get_event_loop()
            duration = await loop.run_in_executor(
                None, 
                self.video_processor.get_video_duration,
                video_path
            )
            if duration is not None:
                # 确保时长是整数类型
                duration = int(duration)
                self._video_durations[video_path] = duration
                return duration
        except Exception as e:
            _logger.debug(f"异步获取视频时长失败: {e}")
        
        return None

    async def generate_thumbnails_parallel(self, media_group_download: MediaGroupDownload) -> Dict[str, str]:
        """
        并行为视频文件生成缩略图，优化性能
        
        Args:
            media_group_download: 媒体组下载结果
            
        Returns:
            Dict[str, str]: 缩略图字典，键为文件路径，值为缩略图路径
        """
        import asyncio
        
        # 筛选出视频文件
        video_files = [
            (file_path, media_type) 
            for file_path, media_type in media_group_download.downloaded_files 
            if media_type == "video"
        ]
        
        if not video_files:
            _logger.debug("没有视频文件需要生成缩略图")
            return {}
        
        async def generate_single_thumbnail(file_path, media_type):
            """
            异步生成单个视频的缩略图
            
            Args:
                file_path: 视频文件路径
                media_type: 媒体类型
                
            Returns:
                Tuple[str, Optional[str]]: (文件路径, 缩略图路径)
            """
            try:
                loop = asyncio.get_event_loop()
                
                # 在线程池中执行缩略图生成
                thumbnail_result = await loop.run_in_executor(
                    None,
                    self.video_processor.extract_thumbnail,
                    str(file_path)
                )
                
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
                
                # 保存视频尺寸信息到缓存
                if width and height:
                    self._video_dimensions[str(file_path)] = (width, height)
                if duration:
                    self._video_durations[str(file_path)] = duration
                
                if thumbnail_path:
                    _logger.debug(f"并行生成视频 {file_path.name} 缩略图成功")
                    return (str(file_path), thumbnail_path)
                else:
                    _logger.warning(f"并行生成视频 {file_path.name} 缩略图失败：返回空路径")
                    return (str(file_path), None)
                    
            except Exception as e:
                _logger.warning(f"并行生成视频 {file_path.name} 缩略图失败: {e}")
                return (str(file_path), None)
        
        _logger.debug(f"开始并行生成 {len(video_files)} 个视频缩略图")
        start_time = time.time()
        
        # 并行生成所有视频的缩略图
        tasks = [
            generate_single_thumbnail(file_path, media_type)
            for file_path, media_type in video_files
        ]
        
        # 使用信号量限制并发数，避免过多的FFmpeg进程
        semaphore = asyncio.Semaphore(3)  # 最多3个并发缩略图生成
        
        async def limited_thumbnail_generation(task):
            async with semaphore:
                return await task
        
        # 执行所有任务（带并发限制）
        results = await asyncio.gather(
            *[limited_thumbnail_generation(task) for task in tasks],
            return_exceptions=True
        )
        
        generation_time = time.time() - start_time
        _logger.debug(f"并行缩略图生成完成，耗时: {generation_time:.2f}秒")
        
        # 处理结果
        thumbnails = {}
        success_count = 0
        for result in results:
            if isinstance(result, Exception):
                _logger.error(f"并行生成缩略图时发生异常: {result}")
            elif result and len(result) == 2:
                file_path, thumbnail_path = result
                if thumbnail_path:
                    thumbnails[file_path] = thumbnail_path
                    success_count += 1
        
        _logger.info(f"并行缩略图生成完成: {success_count}/{len(video_files)} 个成功")
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