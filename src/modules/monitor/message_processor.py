"""
消息处理器模块，负责处理和转发消息
"""

import asyncio
import time
from typing import List, Tuple, Callable, Dict, Any

from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait, ChatForwardsRestricted, ChannelPrivate

from src.utils.channel_resolver import ChannelResolver
from src.utils.logger import get_logger
from src.modules.monitor.restricted_forward_handler import RestrictedForwardHandler

logger = get_logger()

class MessageProcessor:
    """
    消息处理器，负责处理和转发消息
    """
    
    def __init__(self, client: Client, channel_resolver: ChannelResolver, network_error_handler: Callable = None):
        """
        初始化消息处理器
        
        Args:
            client: Pyrogram客户端实例
            channel_resolver: 频道解析器实例
            network_error_handler: 网络错误处理器回调函数
        """
        self.client = client
        self.channel_resolver = channel_resolver
        self.network_error_handler = network_error_handler
        self.monitor_config = {}
        
        # 创建禁止转发处理器 - 延迟初始化，在设置配置时创建
        self.restricted_handler = None
        
        # 事件发射器引用 - 将在Monitor中设置
        self.emit = None
        
        # 频道信息缓存引用（由Monitor模块设置）
        self.channel_info_cache = None
        
        # 性能监控器引用（由Monitor模块设置）
        self.performance_monitor = None
        
    def set_monitor_config(self, monitor_config: Dict[str, Any]):
        """
        设置监控配置
        
        Args:
            monitor_config: 监控配置字典
        """
        self.monitor_config = monitor_config
        
        # 初始化禁止转发处理器
        self.restricted_handler = RestrictedForwardHandler(self.client, self.channel_resolver)
    
    def set_channel_info_cache(self, cache_dict: dict):
        """
        设置频道信息缓存的引用
        
        Args:
            cache_dict: 频道信息缓存字典
        """
        self.channel_info_cache = cache_dict
    
    def get_cached_channel_info(self, channel_id: int) -> str:
        """
        获取缓存的频道信息，避免重复API调用
        
        Args:
            channel_id: 频道ID
            
        Returns:
            str: 频道信息字符串
        """
        if self.channel_info_cache:
            cached_info = self.channel_info_cache.get_channel_info(channel_id)
            if cached_info:
                return cached_info[0]  # 返回display_name
        
        # 如果没有缓存，返回简单格式
        return f"频道 (ID: {channel_id})"
    
    def set_performance_monitor(self, performance_monitor):
        """
        设置性能监控器
        
        Args:
            performance_monitor: 性能监控器实例
        """
        self.performance_monitor = performance_monitor
    
    async def forward_message(self, message: Message, target_channels: List[Tuple[str, int, str]], 
                              use_copy: bool = True, replace_caption: str = None, remove_caption: bool = False,
                              text_replacements: Dict[str, str] = None, allowed_media_types: List[str] = None) -> bool:
        """
        转发消息到多个目标频道
        
        Args:
            message: 要转发的消息
            target_channels: 目标频道列表 [(频道标识, 频道ID, 频道信息)]
            use_copy: 是否使用copy_message（适用于需要修改内容的情况）
            replace_caption: 替换的标题文本
            remove_caption: 是否移除标题
            text_replacements: 文本替换规则字典（用于禁止转发频道）
            allowed_media_types: 允许的媒体类型列表（用于禁止转发频道）
            
        Returns:
            bool: 是否至少有一个频道转发成功
        """
        # 记录转发开始时间
        start_time = time.time()
        
        source_channel = message.chat.username or message.chat.id
        source_chat_id = message.chat.id
        source_message_id = message.id
        source_title = self.get_cached_channel_info(source_chat_id)
        source_display_name = source_title
        
        success_count = 0
        failed_count = 0
        
        # 获取原始文本内容用于比较
        original_text = message.text or message.caption or ""
        
        # 确定是否实际修改了文本内容
        text_modified = False
        if remove_caption and original_text:
            # 如果移除了原本存在的标题，算作修改
            text_modified = True
        elif replace_caption is not None and replace_caption != original_text:
            # 如果替换后的标题与原始标题不同，算作修改
            text_modified = True
        
        # 获取可以转发的目标频道（批量检查权限，减少API调用）
        valid_targets = []
        restricted_targets = []
        
        logger.info(f"开始转发消息 [ID: {source_message_id}] 从 {source_title} 到 {len(target_channels)} 个目标频道")
        
        # 一次性检查源频道转发权限
        source_can_forward = await self.channel_resolver.check_forward_permission(source_chat_id)
        
        if source_can_forward:
            # 源频道允许转发，直接转发到目标频道
            for target, target_id, target_info in target_channels:
                try:
                    # 记录单次转发开始时间
                    single_start_time = time.time()
                    
                    # 检查是否为纯文本消息且需要文本替换
                    is_text_message = not message.media and message.text
                    needs_text_replacement = replace_caption is not None and replace_caption != message.text
                    
                    if is_text_message and needs_text_replacement:
                        # 对于纯文本消息且需要文本替换，直接使用send_message（最快）
                        text_to_send = replace_caption if not remove_caption else ""
                        
                        await self.client.send_message(
                            chat_id=target_id,
                            text=text_to_send,
                            disable_notification=True
                        )
                        success_count += 1
                        logger.info(f"已使用文本发送方式将消息 {source_message_id} 从 {source_title} 发送到 {target_info}")
                        
                        # 发射转发成功事件
                        if self.emit:
                            self.emit("forward", source_message_id, source_display_name, target_info, True, modified=text_modified)
                    elif use_copy:
                        # 使用copy_message复制消息（适用于媒体消息或无文本替换的纯文本消息）
                        caption = None
                        
                        # 【修复】改进移除媒体说明的逻辑 - 优先级：移除媒体说明 > 文本替换
                        if remove_caption:
                            # 移除媒体说明 - 最高优先级，忽略文本替换
                            caption = ""
                            logger.debug(f"移除媒体说明，忽略文本替换")
                        elif message.text or message.caption:
                            # 不移除媒体说明时，才考虑文本替换
                            caption = replace_caption if replace_caption is not None else (message.caption or message.text)
                        
                        await self.client.copy_message(
                            chat_id=target_id,
                            from_chat_id=source_chat_id,
                            message_id=source_message_id,
                            caption=caption,
                            disable_notification=True
                        )
                        success_count += 1
                        logger.info(f"已使用复制方式将消息 {source_message_id} 从 {source_title} 发送到 {target_info}")
                        
                        # 发射转发成功事件
                        if self.emit:
                            self.emit("forward", source_message_id, source_display_name, target_info, True, modified=text_modified)
                    else:
                        # 使用forward_messages保留原始信息
                        await self.client.forward_messages(
                            chat_id=target_id,
                            from_chat_id=source_chat_id,
                            message_ids=source_message_id,
                            disable_notification=True
                        )
                        success_count += 1
                        logger.info(f"已将消息 {source_message_id} 从 {source_title} 转发到 {target_info}")
                        
                        # 发射转发成功事件
                        if self.emit:
                            self.emit("forward", source_message_id, source_display_name, target_info, True, modified=False)
                    
                    # 记录单次转发耗时
                    single_duration = time.time() - single_start_time
                    if self.performance_monitor:
                        self.performance_monitor.record_forwarding_time(single_duration)
                    
                except ChatForwardsRestricted:
                    logger.warning(f"目标频道 {target_info} 禁止转发消息，尝试使用复制方式发送")
                    try:
                        # 检查是否为纯文本消息且需要文本替换
                        is_text_message = not message.media and message.text
                        needs_text_replacement = replace_caption is not None and replace_caption != message.text
                        
                        if is_text_message and needs_text_replacement:
                            # 对于纯文本消息且需要文本替换，直接使用send_message
                            text_to_send = replace_caption if not remove_caption else ""
                            
                            await self.client.send_message(
                                chat_id=target_id,
                                text=text_to_send,
                                disable_notification=True
                            )
                            success_count += 1
                            logger.info(f"已使用文本替换方式将消息 {source_message_id} 从 {source_title} 发送到 {target_info}")
                            
                            # 发射转发成功事件
                            if self.emit:
                                self.emit("forward", source_message_id, source_display_name, target_info, True, modified=text_modified)
                        else:
                            # 使用copy_message复制消息
                            caption = None
                            
                            # 【修复】改进移除媒体说明的逻辑 - 优先级：移除媒体说明 > 文本替换
                            if remove_caption:
                                # 移除媒体说明 - 最高优先级，忽略文本替换
                                caption = ""
                                logger.debug(f"移除媒体说明，忽略文本替换")
                            elif message.text or message.caption:
                                # 不移除媒体说明时，才考虑文本替换
                                caption = replace_caption if replace_caption is not None else (message.caption or message.text)
                                
                            await self.client.copy_message(
                                chat_id=target_id,
                                from_chat_id=source_chat_id,
                                message_id=source_message_id,
                                caption=caption,
                                disable_notification=True
                            )
                            success_count += 1
                            logger.info(f"已使用复制方式将消息 {source_message_id} 从 {source_title} 发送到 {target_info}")
                            
                            # 发射转发成功事件
                            if self.emit:
                                self.emit("forward", source_message_id, source_display_name, target_info, True, modified=text_modified)
                    except Exception as copy_e:
                        failed_count += 1
                        logger.error(f"复制消息失败: {str(copy_e)}", error_type="COPY_MESSAGE", recoverable=True)
                        
                        # 发射转发失败事件
                        if self.emit:
                            self.emit("forward", source_message_id, source_display_name, target_info, False)
                        
                        # 尝试重新发送修改后的消息
                        try:
                            # 获取原始消息的文本或标题
                            text = message.text or message.caption or ""
                            if replace_caption is not None:
                                text = replace_caption
                            if remove_caption:
                                text = None
                            await self.send_modified_message(message, text, [(target, target_id, target_info)])
                            success_count += 1
                            logger.info(f"已使用修改方式将消息 {source_message_id} 从 {source_title} 发送到 {target_info}")
                            
                            # 发射转发成功事件（重试成功）
                            if self.emit:
                                self.emit("forward", source_message_id, source_display_name, target_info, True, modified=text_modified)
                        except Exception as modified_e:
                            logger.error(f"发送修改后的消息失败: {str(modified_e)}", error_type="SEND_MODIFIED", recoverable=True)
                    
                except FloodWait as e:
                    logger.warning(f"触发FloodWait，等待 {e.x} 秒后继续")
                    await asyncio.sleep(e.x)
                    # 重试转发
                    try:
                        # 检查是否为纯文本消息且需要文本替换
                        is_text_message = not message.media and message.text
                        needs_text_replacement = replace_caption is not None and replace_caption != message.text
                        
                        if is_text_message and needs_text_replacement:
                            # 对于纯文本消息且需要文本替换，直接使用send_message
                            text_to_send = replace_caption if not remove_caption else ""
                            
                            await self.client.send_message(
                                chat_id=target_id,
                                text=text_to_send,
                                disable_notification=True
                            )
                            success_count += 1
                            logger.info(f"重试成功：已使用文本替换方式将消息 {source_message_id} 从 {source_title} 发送到 {target_info}")
                            
                            # 发射转发成功事件
                            if self.emit:
                                self.emit("forward", source_message_id, source_display_name, target_info, True, modified=text_modified)
                        else:
                            # 使用copy_message复制消息
                            caption = None
                            if message.text or message.caption:
                                # 【修复】改进移除媒体说明的逻辑 - 优先级：移除媒体说明 > 文本替换
                                if remove_caption:
                                    # 移除媒体说明 - 最高优先级，忽略文本替换
                                    caption = ""
                                    logger.debug(f"移除媒体说明，忽略文本替换")
                                else:
                                    # 不移除媒体说明时，才考虑文本替换
                                    caption = replace_caption if replace_caption is not None else (message.caption or message.text)
                                
                            await self.client.copy_message(
                                chat_id=target_id,
                                from_chat_id=source_chat_id,
                                message_id=source_message_id,
                                caption=caption,
                                disable_notification=True
                            )
                            success_count += 1
                            logger.info(f"重试成功：已将消息 {source_message_id} 从 {source_title} 发送到 {target_info}")
                            
                            # 发射转发成功事件
                            if self.emit:
                                self.emit("forward", source_message_id, source_display_name, target_info, True, modified=text_modified)
                    except Exception as retry_e:
                        failed_count += 1
                        logger.error(f"重试转发失败: {str(retry_e)}", error_type="FORWARD_RETRY", recoverable=True)
                        
                except ChannelPrivate:
                    failed_count += 1
                    logger.error(f"无法访问目标频道 {target_info}，可能是私有频道或未加入", error_type="CHANNEL_PRIVATE", recoverable=True)
                    
                    # 发射转发失败事件
                    if self.emit:
                        self.emit("forward", source_message_id, source_display_name, target_info, False)
                    
                except Exception as e:
                    failed_count += 1
                    logger.error(f"转发消息 {source_message_id} 到 {target_info} 失败: {str(e)}", error_type="FORWARD", recoverable=True)
                    
                    # 发射转发失败事件
                    if self.emit:
                        self.emit("forward", source_message_id, source_display_name, target_info, False)
                    
                    # 如果是copy_message失败，尝试使用其他方法
                    if "Can't copy this message" in str(e) or "copy" in str(e).lower():
                        try:
                            logger.info(f"copy_message失败，尝试使用forward_messages方式: {target_info}")
                            await self.client.forward_messages(
                                chat_id=target_id,
                                from_chat_id=source_chat_id,
                                message_ids=source_message_id,
                                disable_notification=True
                            )
                            success_count += 1
                            failed_count -= 1  # 撤销失败计数
                            logger.info(f"降级成功：已将消息 {source_message_id} 从 {source_title} 转发到 {target_info}")
                            
                            # 发射转发成功事件（重试成功）
                            if self.emit:
                                self.emit("forward", source_message_id, source_display_name, target_info, True, modified=False)
                        except Exception as fallback_e:
                            logger.error(f"降级转发也失败: {str(fallback_e)}", error_type="FORWARD_FALLBACK", recoverable=True)
                
                # 转发间隔：减少到0.2秒，提高转发速度
                if len(target_channels) > 1:  # 只有多个目标时才需要间隔
                    await asyncio.sleep(0.2)
        else:
            # 源频道禁止转发，使用下载-上传方式或copy方式处理
            logger.info(f"源频道禁止转发，将使用适当的处理方式")
            
            try:
                # 使用禁止转发处理器处理消息(无论是否为媒体消息)
                sent_messages, actually_modified = await self.restricted_handler.process_restricted_message(
                    message=message,
                    source_channel=source_channel,
                    source_id=source_chat_id,
                    target_channels=target_channels,
                    caption=replace_caption,
                    remove_caption=remove_caption,
                    text_replacements=text_replacements,
                    allowed_media_types=allowed_media_types
                )
                
                if sent_messages:
                    success_count = len(target_channels)
                    if message.media:
                        logger.info(f"已使用下载-上传方式成功将媒体消息 {source_message_id} 从 {source_title} 发送到所有目标频道")
                    else:
                        logger.info(f"已使用copy方式成功将非媒体消息 {source_message_id} 从 {source_title} 发送到所有目标频道")
                    
                    # 发射所有目标频道的转发成功事件
                    if self.emit:
                        for target, target_id, target_info in target_channels:
                            self.emit("forward", source_message_id, source_display_name, target_info, True, modified=actually_modified)
                else:
                    # 消息处理失败，尝试使用send_modified_message
                    logger.warning(f"处理失败，尝试使用修改后的消息发送")
                    for target, target_id, target_info in target_channels:
                        try:
                            # 获取原始消息的文本或标题
                            text = message.text or message.caption or ""
                            if replace_caption is not None:
                                text = replace_caption
                            if remove_caption:
                                text = None
                            await self.send_modified_message(message, text, [(target, target_id, target_info)])
                            success_count += 1
                            logger.info(f"已使用修改方式将消息 {source_message_id} 从 {source_title} 发送到 {target_info}")
                            
                            # 发射转发成功事件
                            if self.emit:
                                self.emit("forward", source_message_id, source_display_name, target_info, True, modified=text_modified)
                        except Exception as modified_e:
                            failed_count += 1
                            logger.error(f"发送修改后的消息失败: {str(modified_e)}", error_type="SEND_MODIFIED", recoverable=True)
                            
                            # 发射转发失败事件
                            if self.emit:
                                self.emit("forward", source_message_id, source_display_name, target_info, False)
            except Exception as e:
                failed_count = len(target_channels)
                logger.error(f"处理禁止转发的消息失败: {str(e)}", error_type="RESTRICTED_MESSAGE", recoverable=True)
                import traceback
                logger.error(f"错误详情: {traceback.format_exc()}", error_type="DETAILED_ERROR", recoverable=True)
                
                # 发射所有目标频道的转发失败事件
                if self.emit:
                    for target, target_id, target_info in target_channels:
                        self.emit("forward", source_message_id, source_display_name, target_info, False)
        
        # 统计结果
        logger.info(f"消息 [ID: {source_message_id}] 转发完成: 成功 {success_count}, 失败 {failed_count}")    
            
        # 记录转发结束时间
        end_time = time.time()
        forward_duration = end_time - start_time
        logger.info(f"消息 [ID: {source_message_id}] 转发完成，耗时 {forward_duration:.2f} 秒")
        
        overall_success = success_count > 0
        
        # 记录性能监控数据
        if self.performance_monitor:
            for _ in range(success_count):
                self.performance_monitor.record_message_forwarded(forward_duration / len(target_channels), True)
            for _ in range(failed_count):
                self.performance_monitor.record_message_forwarded(forward_duration / len(target_channels), False)
                
        return overall_success
    
    async def send_modified_message(self, original_message: Message, new_text: str, target_channels: List[Tuple[str, int, str]], remove_caption: bool = False) -> bool:
        """
        发送修改后的消息到所有目标频道
        
        Args:
            original_message: 原始消息
            new_text: 新的文本内容
            target_channels: 目标频道列表
            remove_caption: 是否移除标题
            
        Returns:
            bool: 是否成功发送
        """
        if not target_channels:
            logger.warning(f"没有有效的目标频道，跳过发送修改后的消息 [ID: {original_message.id}]")
            return False
            
        try:
            source_chat = original_message.chat
            source_chat_id = source_chat.id
            source_message_id = original_message.id
            
            # 尝试获取频道信息
            try:
                source_title = source_chat.title
            except:
                source_title = str(source_chat_id)
                
            logger.info(f"开始发送修改后的消息 [ID: {source_message_id}] 从 {source_title} 到 {len(target_channels)} 个目标频道")
            
            # 如果是移除标题模式并且消息中有媒体
            if remove_caption and (
                original_message.photo or 
                original_message.video or 
                original_message.document or 
                original_message.animation or 
                original_message.audio
            ):
                # 使用空标题
                caption_to_use = ""
                logger.debug(f"使用空标题（移除标题模式）")
            else:
                # 使用新文本
                caption_to_use = new_text
                if new_text != (original_message.text or original_message.caption or ""):
                    logger.debug(f"使用修改后的文本: '{new_text}'")
            
            # 发送到所有目标频道
            success_count = 0
            failed_count = 0
            
            for target, target_id, target_info in target_channels:
                try:
                    sent_message = None
                    
                    # 根据消息类型重新发送
                    if original_message.photo:
                        # 照片消息
                        kwargs = {
                            'chat_id': target_id,
                            'photo': original_message.photo.file_id
                        }
                        if not remove_caption and caption_to_use:
                            kwargs['caption'] = caption_to_use
                        kwargs['disable_notification'] = True
                        sent_message = await self.client.send_photo(**kwargs)
                    elif original_message.video:
                        # 视频消息
                        kwargs = {
                            'chat_id': target_id,
                            'video': original_message.video.file_id,
                            'supports_streaming': True
                        }
                        if not remove_caption and caption_to_use:
                            kwargs['caption'] = caption_to_use
                        kwargs['disable_notification'] = True
                        sent_message = await self.client.send_video(**kwargs)
                    elif original_message.document:
                        # 文档消息
                        kwargs = {
                            'chat_id': target_id,
                            'document': original_message.document.file_id
                        }
                        if not remove_caption and caption_to_use:
                            kwargs['caption'] = caption_to_use
                        kwargs['disable_notification'] = True
                        sent_message = await self.client.send_document(**kwargs)
                    elif original_message.animation:
                        # 动画/GIF消息
                        kwargs = {
                            'chat_id': target_id,
                            'animation': original_message.animation.file_id
                        }
                        if not remove_caption and caption_to_use:
                            kwargs['caption'] = caption_to_use
                        kwargs['disable_notification'] = True
                        sent_message = await self.client.send_animation(**kwargs)
                    elif original_message.audio:
                        # 音频消息
                        kwargs = {
                            'chat_id': target_id,
                            'audio': original_message.audio.file_id
                        }
                        if not remove_caption and caption_to_use:
                            kwargs['caption'] = caption_to_use
                        kwargs['disable_notification'] = True
                        sent_message = await self.client.send_audio(**kwargs)
                    elif original_message.sticker:
                        # 贴纸消息
                        sent_message = await self.client.send_sticker(
                            chat_id=target_id,
                            sticker=original_message.sticker.file_id,
                            disable_notification=True
                        )
                    elif original_message.voice:
                        # 语音消息
                        kwargs = {
                            'chat_id': target_id,
                            'voice': original_message.voice.file_id
                        }
                        if not remove_caption and caption_to_use:
                            kwargs['caption'] = caption_to_use
                        kwargs['disable_notification'] = True
                        sent_message = await self.client.send_voice(**kwargs)
                    elif original_message.video_note:
                        # 视频笔记消息
                        sent_message = await self.client.send_video_note(
                            chat_id=target_id,
                            video_note=original_message.video_note.file_id,
                            disable_notification=True
                        )
                    else:
                        # 纯文本消息
                        sent_message = await self.client.send_message(
                            chat_id=target_id,
                            text=caption_to_use,
                            disable_notification=True
                        )
                    
                    if sent_message:
                        success_count += 1
                        logger.info(f"已将修改后的消息从 {source_title} 发送到 {target_info}")
                    
                except FloodWait as e:
                    logger.warning(f"触发FloodWait，等待 {e.x} 秒后继续")
                    await asyncio.sleep(e.x)
                    # 重试发送不再实现，以简化代码
                    failed_count += 1
                    
                except Exception as e:
                    failed_count += 1
                    logger.error(f"发送修改后的消息到 {target_info} 失败: {str(e)}", error_type="SEND_MODIFIED", recoverable=True)
                
                # 发送间隔
                await asyncio.sleep(0.5)
            
            # 统计结果
            logger.info(f"消息 [ID: {source_message_id}] 修改后发送完成: 成功 {success_count}, 失败 {failed_count}")
            
        except Exception as e:
            logger.error(f"处理修改后消息发送时发生异常: {str(e)}", error_type="MODIFIED_PROCESS", recoverable=True)
            return False
            
        return True 