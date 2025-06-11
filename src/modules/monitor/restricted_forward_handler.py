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
    处理禁止转发内容的处理器
    支持媒体类型过滤、文本替换、关键词过滤等功能
    """
    
    def __init__(self, client: Client, channel_resolver: ChannelResolver):
        self.client = client
        self.channel_resolver = channel_resolver
        
        # 创建下载器和上传器
        self.message_downloader = MessageDownloader(client)
        self.media_uploader = MediaUploader(client)
        
        # 创建主临时目录
        self.temp_dir = self._create_temp_dir()
        
        # 缓存视频尺寸和时长信息
        self._video_dimensions = {}
        self._video_durations = {}
        
        # 视频处理器（用于生成缩略图和提取元数据）
        self.video_processor = VideoProcessor()
        
        _logger.info(f"RestrictedForwardHandler初始化完成，临时目录: {self.temp_dir}")
    
    def _create_temp_dir(self) -> Path:
        """创建临时目录"""
        temp_dir = Path.cwd() / "temp" / "restricted_forward"
        temp_dir.mkdir(parents=True, exist_ok=True)
        return temp_dir
    
    def _process_video_metadata(self, video_path: str) -> Tuple[Optional[str], Optional[int], Optional[int], Optional[int]]:
        """
        处理视频元数据并生成缩略图
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            Tuple[缩略图路径, 宽度, 高度, 时长]
        """
        try:
            # 使用视频处理器生成缩略图和获取元数据
            thumbnail_result = self.video_processor.extract_thumbnail(video_path)
            
            # 处理返回值可能是元组的情况
            thumb_path = None
            width = None
            height = None
            duration = None
            
            if isinstance(thumbnail_result, tuple) and len(thumbnail_result) >= 4:
                # 如果返回的是包含所有信息的元组
                thumb_path, width, height, duration = thumbnail_result
                # 确保时长是整数类型
                if duration is not None:
                    duration = int(duration)
            elif isinstance(thumbnail_result, tuple) and len(thumbnail_result) >= 3:
                # 如果返回的是三元组
                thumb_path, width, height = thumbnail_result
                # 单独获取时长
                duration = self.video_processor.get_video_duration(video_path)
                if duration is not None:
                    duration = int(duration)
            elif isinstance(thumbnail_result, tuple) and len(thumbnail_result) >= 1:
                # 如果只返回缩略图路径
                thumb_path = thumbnail_result[0]
                # 单独获取尺寸和时长
                dimensions = self.video_processor.get_video_dimensions(video_path)
                if dimensions:
                    width, height = dimensions
                duration = self.video_processor.get_video_duration(video_path)
                if duration is not None:
                    duration = int(duration)
            else:
                # 如果返回的是字符串路径
                thumb_path = thumbnail_result
                # 单独获取尺寸和时长
                dimensions = self.video_processor.get_video_dimensions(video_path)
                if dimensions:
                    width, height = dimensions
                duration = self.video_processor.get_video_duration(video_path)
                if duration is not None:
                    duration = int(duration)
            
            return thumb_path, width, height, duration
            
        except Exception as e:
            _logger.error(f"处理视频元数据失败: {e}")
            return None, None, None, None
    
    def _apply_media_type_filter(self, messages: List[Message], allowed_media_types: List[str]) -> List[Message]:
        """
        应用媒体类型过滤
        
        Args:
            messages: 消息列表
            allowed_media_types: 允许的媒体类型列表
            
        Returns:
            List[Message]: 过滤后的消息列表
        """
        if not allowed_media_types:
            return messages
        
        filtered_messages = []
        for message in messages:
            message_media_type = self._get_message_media_type(message)
            
            if message_media_type and self._is_media_type_allowed(message_media_type, allowed_media_types):
                filtered_messages.append(message)
            else:
                if message_media_type:
                    media_type_names = {
                        "photo": "照片", "video": "视频", "document": "文件", "audio": "音频",
                        "animation": "动画", "sticker": "贴纸", "voice": "语音", "video_note": "视频笔记"
                    }
                    media_type_name = media_type_names.get(message_media_type, message_media_type)
                    _logger.info(f"消息 [ID: {message.id}] 媒体类型({media_type_name})不在允许列表中，过滤")
                else:
                    _logger.info(f"消息 [ID: {message.id}] 无媒体类型，过滤")
        
        return filtered_messages
    
    def _get_message_media_type(self, message: Message) -> Optional[str]:
        """获取消息的媒体类型"""
        if message.photo:
            return "photo"
        elif message.video:
            return "video"
        elif message.document:
            return "document"
        elif message.audio:
            return "audio"
        elif message.animation:
            return "animation"
        elif message.sticker:
            return "sticker"
        elif message.voice:
            return "voice"
        elif message.video_note:
            return "video_note"
        return None
    
    def _is_media_type_allowed(self, message_media_type: str, allowed_media_types: List[str]) -> bool:
        """检查消息的媒体类型是否在允许列表中"""
        if not allowed_media_types:
            return True
        return message_media_type in allowed_media_types
    
    def _apply_text_replacements(self, text: str, text_replacements: Dict[str, str]) -> str:
        """
        应用文本替换
        
        Args:
            text: 原始文本
            text_replacements: 文本替换规则字典
            
        Returns:
            str: 替换后的文本
        """
        if not text or not text_replacements:
            return text
        
        result_text = text
        for find_text, replace_text in text_replacements.items():
            if find_text in result_text:
                result_text = result_text.replace(find_text, replace_text)
                _logger.debug(f"应用文本替换: '{find_text}' -> '{replace_text}'")
        
        return result_text

    def _apply_universal_message_filters(self, messages: List[Message], pair_config: dict) -> Tuple[List[Message], List[Message]]:
        """
        应用通用消息过滤规则（最高优先级判断）
        
        Args:
            messages: 消息列表
            pair_config: 频道对配置
            
        Returns:
            Tuple[List[Message], List[Message]]: (通过过滤的消息列表, 被过滤的消息列表)
        """
        if not messages:
            return [], []
            
        try:
            # 获取该频道对的过滤选项
            exclude_forwards = pair_config.get('exclude_forwards', False)
            exclude_replies = pair_config.get('exclude_replies', False)
            exclude_text = pair_config.get('exclude_text', pair_config.get('exclude_media', False))
            exclude_links = pair_config.get('exclude_links', False)
            
            passed_messages = []
            filtered_messages = []
            
            for message in messages:
                should_filter = False
                filter_reason = ""
                
                # 【最高优先级1】排除转发消息
                if exclude_forwards and message.forward_from:
                    should_filter = True
                    filter_reason = "转发消息"
                
                # 【最高优先级2】排除回复消息
                elif exclude_replies and message.reply_to_message:
                    should_filter = True
                    filter_reason = "回复消息"
                
                # 【最高优先级3】排除纯文本消息
                elif exclude_text:
                    # 检查是否为纯文本消息（没有任何媒体内容）
                    is_media_message = bool(message.photo or message.video or message.document or 
                                          message.audio or message.animation or message.sticker or 
                                          message.voice or message.video_note)
                    if not is_media_message and (message.text or message.caption):
                        should_filter = True
                        filter_reason = "纯文本消息"
                
                # 【最高优先级4】排除包含链接的消息
                elif exclude_links:
                    # 检查消息文本或说明中是否包含链接
                    text_to_check = message.text or message.caption or ""
                    if self._contains_links(text_to_check):
                        should_filter = True
                        filter_reason = "包含链接的消息"
                
                if should_filter:
                    _logger.info(f"RestrictedForwardHandler: 消息 [ID: {message.id}] 被通用过滤规则过滤: {filter_reason}")
                    filtered_messages.append(message)
                else:
                    passed_messages.append(message)
            
            return passed_messages, filtered_messages
            
        except Exception as e:
            _logger.error(f"应用通用消息过滤时发生错误: {str(e)}")
            # 发生错误时返回原始消息列表，让后续处理决定
            return messages, []

    def _contains_links(self, text: str) -> bool:
        """
        检查文本中是否包含链接
        
        Args:
            text: 要检查的文本
            
        Returns:
            bool: 是否包含链接
        """
        import re
        
        if not text:
            return False
        
        # 简单的URL正则匹配
        url_patterns = [
            r'https?://[^\s]+',  # http或https链接
            r'www\.[^\s]+',      # www链接
            r't\.me/[^\s]+',     # Telegram链接
            r'[^\s]+\.[a-z]{2,}[^\s]*'  # 一般域名
        ]
        
        for pattern in url_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        return False

    async def process_restricted_message(self, 
                                       message: Message, 
                                       source_channel: str, 
                                       source_id: int,
                                       target_channels: List[Tuple[str, int, str]],
                                       caption: str = None,
                                       remove_caption: bool = False,
                                       allowed_media_types: List[str] = None,
                                       text_replacements: Dict[str, str] = None) -> Tuple[List[Message], bool]:
        """
        处理单条禁止转发的消息
        
        Args:
            message: 要处理的消息
            source_channel: 源频道标识符
            source_id: 源频道ID
            target_channels: 目标频道列表 [(channel_id_or_username, resolved_id, display_name)]
            caption: 要替换的标题（可选）
            remove_caption: 是否移除标题
            allowed_media_types: 允许的媒体类型列表（可选）
            text_replacements: 文本替换规则字典（可选）
            
        Returns:
            Tuple[List[Message], bool]: (发送的消息列表, 是否实际修改了标题)
        """
        if not target_channels:
            _logger.warning("没有有效的目标频道，跳过处理禁止转发的消息")
            return [], False
        
        # 应用媒体类型过滤
        if allowed_media_types:
            filtered_messages = self._apply_media_type_filter([message], allowed_media_types)
            if not filtered_messages:
                _logger.info(f"消息 [ID: {message.id}] 被媒体类型过滤，跳过处理")
                return [], False
            message = filtered_messages[0]
        
        # 临时目录变量，用于清理
        message_temp_dir = None
        
        try:
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
                                message_id=message.id,
                                disable_notification=True
                            )
                            sent_messages.append(sent_message)
                            _logger.info(f"已将贴纸消息从源频道复制到 {target_info}")
                        
                        except Exception as copy_error:
                            _logger.warning(f"直接复制贴纸消息到 {target_info} 失败: {copy_error}，跳过")
                            continue
                        
                        await asyncio.sleep(0.5)  # 添加延迟避免触发限制
                    except Exception as e:
                        _logger.error(f"处理贴纸消息到 {target_info} 失败: {e}")
                
                return sent_messages, False
            
            # 检查是否是媒体消息
            if message.media:
                # 获取原始标题
                original_caption = message.caption or ""
                
                # 确定最终标题
                final_caption = None
                actually_modified = False
                
                if remove_caption:
                    # 移除标题
                    final_caption = None
                    actually_modified = bool(original_caption)  # 只有原本有标题时，移除才算修改
                else:
                    if caption is not None:
                        # 使用指定的标题
                        final_caption = caption
                        actually_modified = (caption != original_caption)
                    else:
                        # 应用文本替换到原始标题
                        if text_replacements and original_caption:
                            replaced_caption = self._apply_text_replacements(original_caption, text_replacements)
                            final_caption = replaced_caption
                            actually_modified = (replaced_caption != original_caption)
                        else:
                            # 使用原始标题
                            final_caption = original_caption if original_caption else None
                
                # 为消息创建单独的临时目录
                safe_source_name = get_safe_path_name(source_channel)
                safe_target_name = get_safe_path_name(first_target[0])
                message_temp_dir = self.temp_dir / f"{safe_source_name}_to_{safe_target_name}_{message.id}"
                message_temp_dir.mkdir(exist_ok=True, parents=True)
                
                _logger.info(f"处理禁止转发的媒体消息 [ID: {message.id}]，标题修改: {actually_modified}")
                
                # 下载媒体文件
                downloaded_files = await self.message_downloader.download_messages([message], message_temp_dir, source_id)
                
                if not downloaded_files:
                    _logger.warning(f"消息 [ID: {message.id}] 没有媒体文件可下载，跳过")
                    return [], False
                
                # 处理视频缩略图
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
                    
                    # 获取上传后的消息
                    if isinstance(sent_messages, list) and sent_messages:
                        first_sent_message = sent_messages[0]
                    else:
                        first_sent_message = sent_messages
                    
                    for target, target_id, target_info in other_targets:
                        try:
                            await self.client.copy_message(
                                chat_id=target_id,
                                from_chat_id=first_target[1],
                                message_id=first_sent_message.id,
                                disable_notification=True
                            )
                            _logger.info(f"已将媒体消息从第一个目标频道复制到 {target_info}")
                            await asyncio.sleep(0.5)  # 添加延迟避免触发限制
                        except Exception as e:
                            _logger.error(f"复制到目标频道 {target_info} 失败: {e}")
                
                sent_result = sent_messages if isinstance(sent_messages, list) else [sent_messages]
                return sent_result, actually_modified
            
            else:
                # 处理文本消息（不常见的情况，因为通常只有媒体消息会被禁止转发）
                _logger.info(f"处理禁止转发的文本消息 [ID: {message.id}]")
                
                # 获取原始文本
                original_text = message.text or message.caption or ""
                
                # 确定最终文本
                final_text = original_text
                actually_modified = False
                
                if text_replacements and original_text:
                    replaced_text = self._apply_text_replacements(original_text, text_replacements)
                    final_text = replaced_text
                    actually_modified = (replaced_text != original_text)
                
                sent_messages = []
                for target, target_id, target_info in target_channels:
                    try:
                        if final_text != original_text:
                            # 如果文本被修改，发送新文本消息
                            sent_message = await self.client.send_message(
                                chat_id=target_id,
                                text=final_text,
                                disable_notification=True
                            )
                        else:
                            # 否则直接复制
                            sent_message = await self.client.copy_message(
                                chat_id=target_id,
                                from_chat_id=source_id,
                                message_id=message.id,
                                disable_notification=True
                            )
                        
                        sent_messages.append(sent_message)
                        _logger.info(f"已将文本消息发送到 {target_info}")
                        await asyncio.sleep(0.5)  # 添加延迟避免触发限制
                    except Exception as e:
                        _logger.error(f"发送文本消息到 {target_info} 失败: {e}")
                
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
                                          remove_caption: bool = False,
                                          allowed_media_types: List[str] = None,
                                          text_replacements: Dict[str, str] = None) -> Tuple[List[Message], bool]:
        """
        处理禁止转发的媒体组
        
        Args:
            messages: 媒体组消息列表
            source_channel: 源频道标识符
            source_id: 源频道ID
            target_channels: 目标频道列表 [(channel_id_or_username, resolved_id, display_name)]
            caption: 要替换的标题（可选）
            remove_caption: 是否移除标题
            allowed_media_types: 允许的媒体类型列表（可选）
            text_replacements: 文本替换规则字典（可选）
            
        Returns:
            Tuple[List[Message], bool]: (第一个目标频道的发送结果, 是否实际修改了标题)
        """
        # 记录媒体组处理开始
        media_group_id = messages[0].media_group_id if messages else "unknown"
        _logger.info(f"处理禁止转发的媒体组 [ID: {media_group_id}]，包含 {len(messages)} 条消息")
        
        # 【重要】先从完整媒体组获取原始说明，再进行媒体类型过滤
        # 这样可以确保即使被过滤的消息包含说明，也能被正确提取
        original_caption = None
        _logger.debug(f"【步骤1】从完整媒体组（{len(messages)}条消息）中提取原始说明:")
        
        for i, msg in enumerate(messages):
            _logger.debug(f"  消息 {i+1} (ID: {msg.id}): caption='{msg.caption}', 媒体类型='{self._get_message_media_type(msg)}'")
            if msg.caption and msg.caption.strip():
                original_caption = msg.caption.strip()
                _logger.debug(f"  -> ✓ 找到原始说明: '{original_caption}'")
                break
        
        _logger.debug(f"【步骤1结果】提取的原始说明: '{original_caption}'")
        
        # 【步骤2】应用媒体类型过滤
        _logger.debug(f"【步骤2】应用媒体类型过滤，允许类型: {allowed_media_types}")
        filtered_messages = self._apply_media_type_filter(messages, allowed_media_types or [])
        _logger.info(f"媒体组媒体类型过滤后剩余 {len(filtered_messages)} 条消息")
        
        if not filtered_messages:
            _logger.warning(f"媒体组 [ID: {media_group_id}] 所有消息都被媒体类型过滤掉，跳过处理")
            return [], False
        
        _logger.info(f"处理禁止转发的媒体组，包含 {len(filtered_messages)} 条有效媒体消息")
        
        # 临时目录变量，用于清理
        group_temp_dir = None
        
        try:
            # 创建临时目录用于下载媒体文件
            group_temp_dir = self._create_temp_dir() / f"{source_id}_to_{target_channels[0][0]}_{media_group_id}"
            group_temp_dir.mkdir(parents=True, exist_ok=True)
            
            # 【步骤3】下载媒体文件（使用过滤后的消息）
            _logger.debug(f"【步骤3】下载过滤后的媒体文件到: {group_temp_dir}")
            downloaded_files = await self.message_downloader.download_messages(filtered_messages, group_temp_dir, source_id)
            
            if not downloaded_files:
                _logger.warning(f"媒体组 [ID: {media_group_id}] 没有媒体文件可下载，跳过")
                return [], False
            
            # 【步骤4】确定最终说明（处理文本替换）
            actually_modified = False
            final_caption = None
            
            _logger.debug(f"【步骤4】处理媒体组说明和文本替换:")
            _logger.debug(f"  原始说明: '{original_caption}'")
            _logger.debug(f"  指定说明: '{caption}'")
            _logger.debug(f"  移除说明: {remove_caption}")
            _logger.debug(f"  文本替换规则: {text_replacements}")
            
            if original_caption:
                # 媒体组有原始说明的情况
                if remove_caption:
                    # 如果配置要求移除说明
                    final_caption = None
                    actually_modified = True
                    _logger.debug(f"  -> 移除原始说明，标记为已修改")
                elif caption is not None:
                    # 如果指定了替换说明（优先级最高）
                    final_caption = caption
                    # 【修复】对指定说明也应用文本替换
                    if text_replacements:
                        final_caption = self._apply_text_replacements(final_caption, text_replacements)
                        _logger.debug(f"  -> 指定说明应用文本替换: '{caption}' -> '{final_caption}'")
                    actually_modified = True
                    _logger.debug(f"  -> 使用指定说明: '{final_caption}'，标记为已修改")
                elif text_replacements:
                    # 如果有文本替换规则，应用到原始说明
                    final_caption = self._apply_text_replacements(original_caption, text_replacements)
                    actually_modified = (final_caption != original_caption)
                    _logger.debug(f"  -> 应用文本替换: '{original_caption}' -> '{final_caption}', 修改={actually_modified}")
                else:
                    # 保持原始说明不变
                    final_caption = original_caption
                    actually_modified = False
                    _logger.debug(f"  -> 保持原始说明不变: '{final_caption}'")
            else:
                # 媒体组无原始说明的情况
                if caption is not None:
                    # 如果指定了说明，使用指定说明
                    final_caption = caption
                    # 【修复】对指定说明也应用文本替换
                    if text_replacements:
                        final_caption = self._apply_text_replacements(final_caption, text_replacements)
                        _logger.debug(f"  -> 指定说明应用文本替换: '{caption}' -> '{final_caption}'")
                    actually_modified = True
                    _logger.debug(f"  -> 媒体组无原始说明，使用指定说明: '{final_caption}', 标记为已修改")
                else:
                    # 没有原始说明也没有指定说明
                    final_caption = None
                    actually_modified = False
                    _logger.debug(f"  -> 媒体组无原始说明，也无指定说明，不使用文本替换功能")
            
            _logger.debug(f"【步骤4结果】最终说明: '{final_caption}', 是否修改: {actually_modified}")
            
            # 处理视频缩略图
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
            _logger.debug(f"开始上传媒体组到目标频道 {target_channels[0][2]}，缩略图数量: {len(thumbnails)}")
            sent_messages = await self.media_uploader.upload_media_group_to_channel(
                media_group,
                media_group_download,
                target_channels[0][0],
                target_channels[0][1],
                target_channels[0][2],
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
            if sent_messages and len(target_channels) > 1:
                _logger.info(f"从第一个目标频道复制媒体组到其他 {len(target_channels) - 1} 个目标频道")
                
                # 对于媒体组，需要通过第一条消息找到完整的媒体组
                first_sent_message = sent_messages[0]
                
                for target, target_id, target_info in target_channels[1:]:
                    try:
                        # 使用media_group_id复制整个媒体组
                        if len(sent_messages) > 1 and hasattr(first_sent_message, 'media_group_id') and first_sent_message.media_group_id:
                            await self.client.copy_media_group(
                                chat_id=target_id,
                                from_chat_id=target_channels[0][1],
                                message_id=first_sent_message.id,
                                disable_notification=True
                            )
                            _logger.info(f"已将媒体组从第一个目标频道复制到 {target_info}")
                        else:
                            # 单条消息复制
                            await self.client.copy_message(
                                chat_id=target_id,
                                from_chat_id=target_channels[0][1],
                                message_id=first_sent_message.id,
                                caption=final_caption,
                                disable_notification=True
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

    async def process_restricted_media_group_to_multiple_targets(self,
                                                              messages: List[Message],
                                                              source_channel: str,
                                                              source_id: int,
                                                              target_channels: List[Tuple[str, int, str]],
                                                              caption: str = None,
                                                              remove_caption: bool = False,
                                                              allowed_media_types: List[str] = None,
                                                              text_replacements: Dict[str, str] = None,
                                                              event_emitter=None,
                                                              message_type: str = "媒体组") -> bool:
        """
        统一处理禁止转发的媒体组到多个目标频道（优化版本：1次下载上传 + (N-1)次直接复制）
        
        Args:
            messages: 媒体组消息列表
            source_channel: 源频道标识符
            source_id: 源频道ID
            target_channels: 禁止转发的目标频道列表 [(channel_id_or_username, resolved_id, display_name)]
            caption: 要替换的标题（可选）
            remove_caption: 是否移除标题
            allowed_media_types: 允许的媒体类型列表（可选）
            text_replacements: 文本替换规则字典（可选）
            event_emitter: 事件发射器（可选）
            message_type: 消息类型标识（"媒体组" 或 "重组媒体组"）
            
        Returns:
            bool: 是否所有目标频道都处理成功
        """
        if not target_channels or not messages:
            _logger.warning("没有有效的目标频道或消息为空，跳过处理禁止转发的媒体组")
            return False
            
        try:
            # 第一步：下载上传到第一个目标频道
            first_target = target_channels[0]
            _, first_target_id, first_target_info = first_target
            
            _logger.info(f"对第一个禁止转发频道 {first_target_info} 使用下载上传方式处理{message_type}")
            
            # 使用现有的process_restricted_media_group方法处理第一个频道
            sent_messages, actually_modified = await self.process_restricted_media_group(
                messages=messages,
                source_channel=source_channel,
                source_id=source_id,
                target_channels=[first_target],
                caption=caption,
                remove_caption=remove_caption,
                allowed_media_types=allowed_media_types,
                text_replacements=text_replacements
            )
            
            if not sent_messages:
                _logger.error(f"第一个禁止转发频道 {first_target_info} 处理失败，其他频道也将失败")
                
                # 发射所有频道的转发失败事件
                if event_emitter:
                    self._emit_all_targets_failure(event_emitter, source_id, target_channels, 
                                                 messages, message_type)
                return False
            
            _logger.info(f"成功使用下载上传方式将{message_type}发送到第一个禁止转发频道 {first_target_info}")
            
            # 发射第一个频道的转发成功事件
            if event_emitter:
                self._emit_target_success(event_emitter, source_id, first_target_info, 
                                        messages, actually_modified, message_type)
            
            # 第二步：直接从第一个频道复制转发到其他频道（优化版本 - 无历史查询）
            if len(target_channels) > 1:
                remaining_targets = target_channels[1:]
                _logger.info(f"第一个频道成功，开始从 {first_target_info} 直接复制转发{message_type}到其他 {len(remaining_targets)} 个禁止转发频道")
                
                success = await self._copy_from_first_to_remaining_targets(
                    first_target_id, remaining_targets, sent_messages, 
                    source_id, messages, actually_modified, message_type, event_emitter
                )
                
                return success
            else:
                # 只有一个目标频道，直接返回成功
                return True
                
        except Exception as e:
            _logger.error(f"统一处理禁止转发{message_type}时发生错误: {str(e)}")
            import traceback
            _logger.error(f"错误详情: {traceback.format_exc()}")
            
            # 发射所有频道的转发失败事件
            if event_emitter:
                self._emit_all_targets_failure(event_emitter, source_id, target_channels, 
                                             messages, message_type)
            return False

    async def _copy_from_first_to_remaining_targets(self, 
                                                  first_target_id: int, 
                                                  remaining_targets: List[Tuple[str, int, str]], 
                                                  sent_messages: List, 
                                                  source_id: int,
                                                  original_messages: List[Message], 
                                                  actually_modified: bool, 
                                                  message_type: str,
                                                  event_emitter=None) -> bool:
        """
        从第一个成功的目标频道直接复制转发到其他频道（无历史查询优化版本）
        
        Args:
            first_target_id: 第一个成功的目标频道ID
            remaining_targets: 剩余的目标频道列表
            sent_messages: 第一个频道成功发送的消息列表
            source_id: 源频道ID
            original_messages: 原始消息列表
            actually_modified: 是否实际修改了标题
            message_type: 消息类型标识
            event_emitter: 事件发射器（可选）
            
        Returns:
            bool: 是否所有剩余频道都处理成功
        """
        try:
            if not sent_messages:
                _logger.error("第一个频道没有返回发送的消息，无法进行复制转发")
                return False
            
            # 提取发送成功的消息ID，按顺序排列
            sent_message_ids = []
            if isinstance(sent_messages, list):
                sent_message_ids = [msg.id for msg in sent_messages if hasattr(msg, 'id')]
            else:
                _logger.warning("发送的消息不是列表格式，尝试提取单个消息ID")
                if hasattr(sent_messages, 'id'):
                    sent_message_ids = [sent_messages.id]
            
            if not sent_message_ids:
                _logger.error("无法从发送的消息中提取有效的消息ID")
                return False
            
            _logger.info(f"从第一个频道获取到{message_type}的 {len(sent_message_ids)} 个消息ID，开始直接复制转发")
            
            all_success = True
            
            # 复制到其他频道
            for target, target_id, target_info in remaining_targets:
                try:
                    # 直接使用已知的消息ID进行转发，无需历史查询
                    await self.client.forward_messages(
                        chat_id=target_id,
                        from_chat_id=first_target_id,
                        message_ids=sent_message_ids,
                        disable_notification=True
                    )
                    _logger.info(f"成功直接复制{message_type}到 {target_info}")
                    
                    # 发射转发成功事件
                    if event_emitter:
                        self._emit_target_success(event_emitter, source_id, target_info, 
                                                original_messages, actually_modified, message_type)
                    
                except Exception as e:
                    _logger.error(f"直接复制{message_type}到 {target_info} 失败: {str(e)}")
                    all_success = False
                    
                    # 发射转发失败事件
                    if event_emitter:
                        self._emit_target_failure(event_emitter, source_id, target_info, 
                                                original_messages, message_type)
                
                # 添加短暂延迟避免触发速率限制
                await asyncio.sleep(0.3)
            
            return all_success
            
        except Exception as e:
            _logger.error(f"优化版{message_type}复制转发时出错: {str(e)}")
            
            # 为所有剩余目标发射转发失败事件
            if event_emitter:
                for target, target_id, target_info in remaining_targets:
                    self._emit_target_failure(event_emitter, source_id, target_info, 
                                            original_messages, message_type)
            return False
    
    def _emit_target_success(self, event_emitter, source_id: int, target_info: str, 
                           messages: List[Message], actually_modified: bool, message_type: str):
        """发射单个目标频道的转发成功事件"""
        try:
            # 使用缓存获取源频道信息
            if hasattr(self.channel_resolver, 'get_cached_channel_info'):
                source_info_str = self.channel_resolver.get_cached_channel_info(source_id)
            else:
                source_info_str = str(source_id)
            
            # 生成显示ID
            message_ids = [msg.id for msg in messages]
            display_id = self._generate_display_id(message_ids, message_type)
            
            # 发射事件
            event_emitter("forward", display_id, source_info_str, target_info, True, actually_modified)
            
        except Exception as e:
            _logger.error(f"发射转发成功事件失败: {e}")
    
    def _emit_target_failure(self, event_emitter, source_id: int, target_info: str, 
                           messages: List[Message], message_type: str):
        """发射单个目标频道的转发失败事件"""
        try:
            # 使用缓存获取源频道信息
            if hasattr(self.channel_resolver, 'get_cached_channel_info'):
                source_info_str = self.channel_resolver.get_cached_channel_info(source_id)
            else:
                source_info_str = str(source_id)
            
            # 生成显示ID
            message_ids = [msg.id for msg in messages]
            display_id = self._generate_display_id(message_ids, message_type)
            
            # 发射事件
            event_emitter("forward", display_id, source_info_str, target_info, False)
            
        except Exception as e:
            _logger.error(f"发射转发失败事件失败: {e}")
    
    def _emit_all_targets_failure(self, event_emitter, source_id: int, 
                                target_channels: List[Tuple[str, int, str]], 
                                messages: List[Message], message_type: str):
        """发射所有目标频道的转发失败事件"""
        for target, target_id, target_info in target_channels:
            self._emit_target_failure(event_emitter, source_id, target_info, messages, message_type)
    
    def _generate_display_id(self, message_ids: List[int], message_type: str) -> str:
        """生成安全的显示ID，用于UI显示"""
        try:
            if not message_ids:
                import time
                timestamp = int(time.time())
                return f"{message_type}[0个文件]-{timestamp}"
            
            message_count = len(message_ids)
            min_message_id = min(message_ids)
            
            if min_message_id <= 0:
                import time
                timestamp = int(time.time())
                return f"{message_type}[{message_count}个文件]-{timestamp}"
            
            display_id = f"{message_type}[{message_count}个文件]-{min_message_id}"
            
            # 重组媒体组需要特殊前缀
            if message_type == "重组媒体组":
                return f"重组媒体组[{message_count}个文件]-{min_message_id}"
            else:
                return display_id
                
        except Exception as e:
            _logger.error(f"生成显示ID时出错: {e}")
            import time
            timestamp = int(time.time())
            return f"{message_type}[未知]-{timestamp}"
    
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