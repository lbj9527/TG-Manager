"""
处理禁止转发内容的模块，使用生产者-消费者模式进行下载和上传
"""

import asyncio
from pathlib import Path
from typing import List, Dict, Tuple, Any, Union, Optional
from datetime import datetime

from pyrogram import Client
from pyrogram.types import Message, InputMediaPhoto, InputMediaVideo, InputMediaDocument, InputMediaAudio
from pyrogram.errors import FloodWait, ChatForwardsRestricted

from src.utils.channel_resolver import ChannelResolver
from src.utils.logger import get_logger
from src.modules.forward.message_downloader import MessageDownloader
from src.modules.forward.media_uploader import MediaUploader
from src.modules.forward.media_group_download import MediaGroupDownload
from src.modules.forward.utils import get_safe_path_name, ensure_temp_dir, clean_directory
from src.utils.video_processor import VideoProcessor

_logger = get_logger()

class RestrictedForwardHandler:
    """
    处理禁止转发内容的处理器，使用下载后重新上传的方式
    """
    
    def __init__(self, client: Client, channel_resolver: ChannelResolver):
        """
        初始化处理器
        
        Args:
            client: Pyrogram客户端实例
            channel_resolver: 频道解析器实例
        """
        self.client = client
        self.channel_resolver = channel_resolver
        
        # 创建临时目录
        self.tmp_path = Path('tmp/monitor')
        self.tmp_path.mkdir(exist_ok=True, parents=True)
        
        # 初始化下载器和上传器
        self.message_downloader = MessageDownloader(client)
        self.media_uploader = MediaUploader(client, None, {'max_retries': 3})
        
        # 创建视频处理器，用于处理视频缩略图和元数据
        self.video_processor = VideoProcessor()
        
        # 创建临时会话目录
        self.temp_dir = self._create_temp_dir()
        
        # 视频元数据缓存
        self._video_dimensions = {}
        self._video_durations = {}
    
    def _create_temp_dir(self) -> Path:
        """
        创建临时目录
        
        Returns:
            Path: 临时目录路径
        """
        return ensure_temp_dir(self.tmp_path, 'monitor')
    
    def _process_video_metadata(self, video_path: str) -> Tuple[Optional[str], Optional[int], Optional[int], Optional[int]]:
        """
        处理视频元数据，提取缩略图、尺寸和时长
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            Tuple[Optional[str], Optional[int], Optional[int], Optional[int]]: 
                (缩略图路径, 宽度, 高度, 时长)，如果提取失败则相应值为None
        """
        try:
            # 使用视频处理器提取缩略图和元数据
            result = self.video_processor.extract_thumbnail(str(video_path))
            
            if not result:
                _logger.warning(f"无法为视频生成缩略图和元数据: {video_path}")
                return None, None, None, None
            
            # 分析返回结果，提取缩略图路径和视频元数据
            if isinstance(result, tuple):
                if len(result) >= 4:
                    thumb_path, width, height, duration = result
                    # 确保时长是整数类型
                    if duration is not None:
                        duration = int(duration)
                    return thumb_path, width, height, duration
                elif len(result) >= 3:
                    thumb_path, width, height = result
                    return thumb_path, width, height, None
                else:
                    thumb_path = result[0]
                    return thumb_path, None, None, None
            else:
                return result, None, None, None
        except Exception as e:
            _logger.error(f"处理视频元数据失败: {e}")
            return None, None, None, None
    
    async def process_restricted_message(self, 
                                       message: Message, 
                                       source_channel: str, 
                                       source_id: int,
                                       target_channels: List[Tuple[str, int, str]],
                                       caption: str = None,
                                       remove_caption: bool = False) -> Tuple[List[Message], bool]:
        """
        处理禁止转发的单条消息
        
        Args:
            message: 要处理的消息
            source_channel: 源频道标识符
            source_id: 源频道ID
            target_channels: 目标频道列表 [(channel_id_or_username, resolved_id, display_name)]
            caption: 要替换的标题（可选）
            remove_caption: 是否移除标题
            
        Returns:
            Tuple[List[Message], bool]: (发送结果列表, 是否实际修改了标题)
        """
        if not target_channels or not message:
            _logger.warning("没有有效的目标频道或消息为空，跳过处理禁止转发的消息")
            return [], False
        
        # 获取原始标题
        original_caption = message.caption or message.text
        
        # 确定实际修改状态
        actually_modified = False
        
        # 临时目录变量，用于清理
        message_temp_dir = None
        
        try:
            # 检查是否是媒体消息
            if message.media:
                # 分离第一个目标频道和其余目标频道
                first_target, *other_targets = target_channels
                
                # 特殊处理贴纸消息 - 贴纸是一种特殊的媒体消息，但不需要下载
                if message.sticker:
                    _logger.info(f"处理禁止转发的贴纸消息 [ID: {message.id}]，使用copy_message方式")
                    
                    # 处理所有目标频道
                    sent_messages = []
                    
                    # 复制到所有目标频道
                    for target, target_id, target_info in target_channels:
                        try:
                            # 首先尝试copy_message
                            try:
                                sent_message = await self.client.copy_message(
                                    chat_id=target_id,
                                    from_chat_id=source_id,
                                    message_id=message.id
                                )
                                sent_messages.append(sent_message)
                                _logger.info(f"已将贴纸消息从源频道复制到 {target_info}")
                            except Exception as copy_e:
                                # 如果复制失败，直接发送贴纸
                                _logger.warning(f"复制贴纸失败，尝试直接发送: {copy_e}")
                                sent_message = await self.client.send_sticker(
                                    chat_id=target_id,
                                    sticker=message.sticker.file_id
                                )
                                sent_messages.append(sent_message)
                                _logger.info(f"已直接发送贴纸到 {target_info}")
                            
                            await asyncio.sleep(0.5)  # 添加延迟避免触发限制
                        except Exception as e:
                            _logger.error(f"发送贴纸到目标频道 {target_info} 失败: {e}")
                    
                    # 贴纸消息通常没有标题，不算修改
                    return sent_messages, False
                
                # 特殊处理语音消息 - 语音消息不需要下载上传，直接使用file_id
                if message.voice:
                    _logger.info(f"处理禁止转发的语音消息 [ID: {message.id}]，使用send_voice方式")
                    
                    # 处理所有目标频道
                    sent_messages = []
                    
                    # 决定使用的标题
                    final_caption = None
                    if remove_caption:
                        final_caption = ""  # 移除标题
                        actually_modified = bool(original_caption)
                    elif caption is not None:
                        final_caption = caption
                        actually_modified = (original_caption != caption)
                    else:
                        final_caption = original_caption
                        actually_modified = False
                    
                    # 发送到所有目标频道
                    for target, target_id, target_info in target_channels:
                        try:
                            # 首先尝试copy_message
                            try:
                                sent_message = await self.client.copy_message(
                                    chat_id=target_id,
                                    from_chat_id=source_id,
                                    message_id=message.id,
                                    caption=final_caption
                                )
                                sent_messages.append(sent_message)
                                _logger.info(f"已将语音消息从源频道复制到 {target_info}")
                            except Exception as copy_e:
                                # 如果复制失败，直接发送语音
                                _logger.warning(f"复制语音失败，尝试直接发送: {copy_e}")
                                kwargs = {
                                    'chat_id': target_id,
                                    'voice': message.voice.file_id
                                }
                                if final_caption:
                                    kwargs['caption'] = final_caption
                                sent_message = await self.client.send_voice(**kwargs)
                                sent_messages.append(sent_message)
                                _logger.info(f"已直接发送语音到 {target_info}")
                            
                            await asyncio.sleep(0.5)  # 添加延迟避免触发限制
                        except Exception as e:
                            _logger.error(f"发送语音到目标频道 {target_info} 失败: {e}")
                    
                    return sent_messages, actually_modified
                
                # 特殊处理视频笔记消息 - 视频笔记不需要下载上传，直接使用file_id
                if message.video_note:
                    _logger.info(f"处理禁止转发的视频笔记消息 [ID: {message.id}]，使用send_video_note方式")
                    
                    # 处理所有目标频道
                    sent_messages = []
                    
                    # 发送到所有目标频道（视频笔记没有标题）
                    for target, target_id, target_info in target_channels:
                        try:
                            # 首先尝试copy_message
                            try:
                                sent_message = await self.client.copy_message(
                                    chat_id=target_id,
                                    from_chat_id=source_id,
                                    message_id=message.id
                                )
                                sent_messages.append(sent_message)
                                _logger.info(f"已将视频笔记消息从源频道复制到 {target_info}")
                            except Exception as copy_e:
                                # 如果复制失败，直接发送视频笔记
                                _logger.warning(f"复制视频笔记失败，尝试直接发送: {copy_e}")
                                sent_message = await self.client.send_video_note(
                                    chat_id=target_id,
                                    video_note=message.video_note.file_id
                                )
                                sent_messages.append(sent_message)
                                _logger.info(f"已直接发送视频笔记到 {target_info}")
                            
                            await asyncio.sleep(0.5)  # 添加延迟避免触发限制
                        except Exception as e:
                            _logger.error(f"发送视频笔记到目标频道 {target_info} 失败: {e}")
                    
                    # 视频笔记消息没有标题，不算修改
                    return sent_messages, False
                
                # 为消息创建单独的临时目录
                safe_source_name = get_safe_path_name(source_channel)
                safe_target_name = get_safe_path_name(first_target[0])
                message_temp_dir = self.temp_dir / f"{safe_source_name}_to_{safe_target_name}_{message.id}"
                message_temp_dir.mkdir(exist_ok=True, parents=True)
                
                _logger.info(f"处理禁止转发的媒体消息 [ID: {message.id}]")
                
                # 下载媒体文件
                downloaded_files = await self.message_downloader.download_messages([message], message_temp_dir, source_id)
                
                if not downloaded_files:
                    _logger.warning(f"消息 [ID: {message.id}] 没有媒体文件可下载，跳过")
                    return [], False
                
                # 决定是否使用消息原始标题
                if remove_caption:
                    final_caption = ""  # 使用空字符串而不是None来移除caption
                    # 只有原本有标题时，移除才算修改
                    if original_caption:
                        actually_modified = True
                    _logger.debug(f"移除标题模式，实际修改状态: {actually_modified}")
                elif caption is not None:
                    final_caption = caption
                    # 只有替换后的标题与原始标题不同时才算修改
                    if original_caption != caption:
                        actually_modified = True
                    _logger.debug(f"使用替换后的标题: '{caption}'，实际修改状态: {actually_modified}")
                else:
                    final_caption = message.caption or message.text
                    actually_modified = False
                    _logger.debug(f"使用原始标题，无修改")
                
                # 预处理视频元数据
                thumbnails = {}
                if message.video:
                    for file_path, media_type in downloaded_files:
                        if media_type == "video":
                            # 提取视频元数据并生成缩略图
                            thumb_path, width, height, duration = self._process_video_metadata(str(file_path))
                            if thumb_path:
                                thumbnails[str(file_path)] = thumb_path
                                # 缓存视频尺寸和时长信息
                                if width and height:
                                    self._video_dimensions[str(file_path)] = (width, height)
                                if duration:
                                    self._video_durations[str(file_path)] = duration
                                _logger.debug(f"为视频 {file_path.name} 生成缩略图和元数据成功: 尺寸={width}x{height}, 时长={duration}秒")
                    
                # 创建MediaGroupDownload对象，即使只有一个消息
                media_group_download = MediaGroupDownload(
                    source_channel=source_channel,
                    source_id=source_id,
                    messages=[message],
                    download_dir=message_temp_dir,
                    downloaded_files=downloaded_files,
                    caption=final_caption
                )
                
                # 准备上传的媒体组
                media_group = self.media_uploader.prepare_media_group_for_upload(media_group_download, thumbnails)
                
                # 上传到第一个目标频道
                _logger.debug(f"开始上传媒体到目标频道 {first_target[2]}，缩略图数量: {len(thumbnails)}")
                sent_messages = await self.media_uploader.upload_media_group_to_channel(
                    media_group,
                    media_group_download,
                    first_target[0],
                    first_target[1],
                    first_target[2],
                    thumbnails
                )
                
                # 清理缩略图
                if thumbnails:
                    for thumb_path in thumbnails.values():
                        try:
                            Path(thumb_path).unlink(missing_ok=True)
                            _logger.debug(f"已删除缩略图: {thumb_path}")
                        except Exception as e:
                            _logger.warning(f"删除缩略图失败: {e}")
                
                # 如果上传成功并且有其他目标频道，则从第一个目标频道复制到其他目标频道
                if sent_messages and other_targets:
                    _logger.info(f"从第一个目标频道复制到其他 {len(other_targets)} 个目标频道")
                    first_sent_message = sent_messages[0] if isinstance(sent_messages, list) else sent_messages
                    
                    # 处理单条消息
                    for target, target_id, target_info in other_targets:
                        try:
                            # 确定要使用的caption
                            caption_to_use = final_caption
                            if remove_caption:
                                caption_to_use = ""  # 确保移除caption时使用空字符串
                                
                            await self.client.copy_message(
                                chat_id=target_id,
                                from_chat_id=first_target[1],
                                message_id=first_sent_message.id,
                                caption=caption_to_use
                            )
                            _logger.info(f"已将消息从第一个目标频道复制到 {target_info}")
                            await asyncio.sleep(0.5)  # 添加延迟避免触发限制
                        except Exception as e:
                            _logger.error(f"复制到目标频道 {target_info} 失败: {e}")
                
                sent_result = sent_messages if isinstance(sent_messages, list) else [sent_messages]
                return sent_result, actually_modified
            else:
                # 非媒体消息(文本/表情/位置等)，无需下载上传，直接使用copy_message
                _logger.info(f"处理禁止转发的非媒体消息 [ID: {message.id}]，使用copy_message方式")
                
                # 处理所有目标频道
                sent_messages = []
                
                # 确定标题
                if remove_caption:
                    final_text = ""  # 使用空字符串而不是None来移除caption
                    # 只有原本有标题时，移除才算修改
                    if original_caption:
                        actually_modified = True
                    _logger.debug(f"移除标题模式，实际修改状态: {actually_modified}")
                elif caption is not None:
                    final_text = caption
                    # 只有替换后的标题与原始标题不同时才算修改
                    if original_caption != caption:
                        actually_modified = True
                    _logger.debug(f"使用替换后的标题: '{caption}'，实际修改状态: {actually_modified}")
                else:
                    final_text = message.text or message.caption
                    actually_modified = False
                    _logger.debug(f"使用原始文本，无修改")
                
                # 复制到所有目标频道
                for target, target_id, target_info in target_channels:
                    try:
                        sent_message = await self.client.copy_message(
                            chat_id=target_id,
                            from_chat_id=source_id,
                            message_id=message.id,
                            caption=final_text
                        )
                        sent_messages.append(sent_message)
                        _logger.info(f"已将非媒体消息从源频道复制到 {target_info}")
                        await asyncio.sleep(0.5)  # 添加延迟避免触发限制
                    except Exception as e:
                        _logger.error(f"复制到目标频道 {target_info} 失败: {e}")
                
                return sent_messages, actually_modified
        
        except Exception as e:
            _logger.error(f"处理禁止转发的消息失败: {e}")
            import traceback
            _logger.error(f"错误详情: {traceback.format_exc()}")
            return [], False
        finally:
            # 确保清理临时目录
            if message_temp_dir:
                self.media_uploader.cleanup_media_group_dir(message_temp_dir)
    
    async def process_restricted_media_group(self,
                                          messages: List[Message],
                                          source_channel: str,
                                          source_id: int,
                                          target_channels: List[Tuple[str, int, str]],
                                          caption: str = None,
                                          remove_caption: bool = False) -> Tuple[List[Message], bool]:
        """
        处理禁止转发的媒体组
        
        Args:
            messages: 媒体组消息列表
            source_channel: 源频道标识符
            source_id: 源频道ID
            target_channels: 目标频道列表 [(channel_id_or_username, resolved_id, display_name)]
            caption: 要替换的标题（可选）
            remove_caption: 是否移除标题
            
        Returns:
            Tuple[List[Message], bool]: (第一个目标频道的发送结果, 是否实际修改了标题)
        """
        if not target_channels or not messages:
            _logger.warning("没有有效的目标频道或消息为空，跳过处理禁止转发的媒体组")
            return [], False
        
        # 临时目录变量，用于清理
        group_temp_dir = None
        
        try:
            # 分离第一个目标频道和其余目标频道
            first_target, *other_targets = target_channels
            
            # 获取媒体组ID
            media_group_id = messages[0].media_group_id
            message_ids = [m.id for m in messages]
            
            # 为媒体组创建单独的临时目录
            safe_source_name = get_safe_path_name(source_channel)
            safe_target_name = get_safe_path_name(first_target[0])
            group_temp_dir = self.temp_dir / f"{safe_source_name}_to_{safe_target_name}_{media_group_id}"
            group_temp_dir.mkdir(exist_ok=True, parents=True)
            
            _logger.info(f"处理禁止转发的媒体组 [ID: {media_group_id}]，包含 {len(messages)} 条消息")
            
            # 下载媒体文件
            downloaded_files = await self.message_downloader.download_messages(messages, group_temp_dir, source_id)
            
            if not downloaded_files:
                _logger.warning(f"媒体组 [ID: {media_group_id}] 没有媒体文件可下载，跳过")
                return [], False
            
            # 获取原始标题
            original_caption = None
            for msg in messages:
                if msg.caption:
                    original_caption = msg.caption
                    break
            
            # 确定实际修改状态
            actually_modified = False
            
            # 决定是否使用消息原始标题
            if remove_caption:
                final_caption = ""  # 使用空字符串而不是None来移除caption
                # 只有原本有标题时，移除才算修改
                if original_caption:
                    actually_modified = True
                _logger.debug(f"移除标题模式，实际修改状态: {actually_modified}")
            elif caption is not None:
                final_caption = caption
                # 只有替换后的标题与原始标题不同时才算修改
                if original_caption != caption:
                    actually_modified = True
                _logger.debug(f"使用替换后的标题: '{caption}'，实际修改状态: {actually_modified}")
            else:
                # 使用原始标题，不算修改
                final_caption = original_caption
                actually_modified = False
                _logger.debug(f"使用原始标题，无修改")
            
            # 预处理视频元数据
            thumbnails = {}
            for file_path, media_type in downloaded_files:
                if media_type == "video":
                    # 提取视频元数据并生成缩略图
                    thumb_path, width, height, duration = self._process_video_metadata(str(file_path))
                    if thumb_path:
                        thumbnails[str(file_path)] = thumb_path
                        # 缓存视频尺寸和时长信息
                        if width and height:
                            self._video_dimensions[str(file_path)] = (width, height)
                        if duration:
                            self._video_durations[str(file_path)] = duration
                        _logger.debug(f"为视频 {file_path.name} 生成缩略图和元数据成功: 尺寸={width}x{height}, 时长={duration}秒")
            
            # 创建MediaGroupDownload对象
            media_group_download = MediaGroupDownload(
                source_channel=source_channel,
                source_id=source_id,
                messages=messages,
                download_dir=group_temp_dir,
                downloaded_files=downloaded_files,
                caption=final_caption
            )
            
            # 准备上传的媒体组
            media_group = self.media_uploader.prepare_media_group_for_upload(media_group_download, thumbnails)
            
            # 上传到第一个目标频道
            _logger.debug(f"开始上传媒体组到目标频道 {first_target[2]}，缩略图数量: {len(thumbnails)}")
            sent_messages = await self.media_uploader.upload_media_group_to_channel(
                media_group,
                media_group_download,
                first_target[0],
                first_target[1],
                first_target[2],
                thumbnails
            )
            
            # 清理缩略图
            if thumbnails:
                for thumb_path in thumbnails.values():
                    try:
                        Path(thumb_path).unlink(missing_ok=True)
                        _logger.debug(f"已删除缩略图: {thumb_path}")
                    except Exception as e:
                        _logger.warning(f"删除缩略图失败: {e}")
            
            # 如果上传成功并且有其他目标频道，则从第一个目标频道复制到其他目标频道
            if sent_messages and other_targets and isinstance(sent_messages, list) and len(sent_messages) > 0:
                _logger.info(f"从第一个目标频道复制媒体组到其他 {len(other_targets)} 个目标频道")
                
                # 对于媒体组，需要通过第一条消息找到完整的媒体组
                first_sent_message = sent_messages[0]
                
                for target, target_id, target_info in other_targets:
                    try:
                        # 使用media_group_id复制整个媒体组
                        if len(sent_messages) > 1 and hasattr(first_sent_message, 'media_group_id') and first_sent_message.media_group_id:
                            await self.client.copy_media_group(
                                chat_id=target_id,
                                from_chat_id=first_target[1],
                                message_id=first_sent_message.id
                            )
                            _logger.info(f"已将媒体组从第一个目标频道复制到 {target_info}")
                        else:
                            # 单条消息复制
                            await self.client.copy_message(
                                chat_id=target_id,
                                from_chat_id=first_target[1],
                                message_id=first_sent_message.id,
                                caption=final_caption
                            )
                            _logger.info(f"已将单条媒体消息从第一个目标频道复制到 {target_info}")
                        
                        await asyncio.sleep(0.5)  # 添加延迟避免触发限制
                    except Exception as e:
                        _logger.error(f"复制到目标频道 {target_info} 失败: {e}")
            
            sent_result = sent_messages if isinstance(sent_messages, list) else [sent_messages]
            return sent_result, actually_modified
        
        except Exception as e:
            _logger.error(f"处理禁止转发的媒体组失败: {e}")
            import traceback
            _logger.error(f"错误详情: {traceback.format_exc()}")
            return [], False
        finally:
            # 确保清理临时目录
            if group_temp_dir:
                self.media_uploader.cleanup_media_group_dir(group_temp_dir) 
    
    def cleanup_temp_dirs(self):
        """
        清理临时目录中残留的空文件夹
        """
        try:
            if self.temp_dir.exists():
                # 清理temp_dir下的所有子目录
                for sub_dir in self.temp_dir.iterdir():
                    if sub_dir.is_dir():
                        try:
                            # 检查目录是否为空
                            if not list(sub_dir.iterdir()):
                                sub_dir.rmdir()
                                _logger.debug(f"清理空的临时子目录: {sub_dir}")
                            else:
                                # 如果不为空，尝试递归清理
                                self.media_uploader.cleanup_media_group_dir(sub_dir)
                                _logger.debug(f"清理非空的临时子目录: {sub_dir}")
                        except Exception as e:
                            _logger.debug(f"清理临时子目录 {sub_dir} 失败: {e}")
                
                # 尝试删除temp_dir自身（如果为空）
                try:
                    if not list(self.temp_dir.iterdir()):
                        self.temp_dir.rmdir()
                        _logger.debug(f"清理空的临时根目录: {self.temp_dir}")
                except Exception as e:
                    _logger.debug(f"清理临时根目录失败: {e}")
                    
        except Exception as e:
            _logger.debug(f"清理临时目录时发生错误: {e}")
    
    def __del__(self):
        """
        析构函数，确保临时目录被清理
        """
        try:
            self.cleanup_temp_dirs()
        except Exception:
            # 析构函数中不应该抛出异常
            pass 