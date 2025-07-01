"""
直接转发器，用于直接转发消息（不需要下载重新上传）
支持统一的过滤功能：文本替换、关键词过滤、媒体类型过滤
"""

import asyncio
from typing import List, Tuple, Dict, Union, Optional, Set, Any

from pyrogram import Client
from pyrogram.types import Message, InputMediaPhoto, InputMediaVideo, InputMediaDocument, InputMediaAudio, InputMediaAnimation
from pyrogram.errors import FloodWait, ChatForwardsRestricted, ChannelPrivate

from src.utils.logger import get_logger
from src.modules.forward.message_filter import MessageFilter
from src.utils.ui_config_models import MediaType

_logger = get_logger()

class DirectForwarder:
    """
    直接转发器，使用Telegram原生转发功能
    支持统一的过滤功能
    """
    
    def __init__(self, client: Client, history_manager=None, general_config: Dict[str, Any] = None, emit=None):
        """
        初始化直接转发器
        
        Args:
            client: Pyrogram客户端实例
            history_manager: 历史记录管理器实例，用于记录已转发的消息
            general_config: 通用配置
            emit: 事件发射函数，用于发送转发进度信号
        """
        self.client = client
        self.history_manager = history_manager
        self.general_config = general_config or {}
        self.emit = emit  # 添加事件发射函数
        
        # 初始化停止标志
        self.should_stop = False
        
        # 初始化消息过滤器
        self.message_filter = MessageFilter()
    
    async def forward_media_group_directly(self, 
                                         messages: List[Message], 
                                         source_channel: str, 
                                         source_id: int, 
                                         target_channels: List[Tuple[str, int, str]],
                                         hide_author: bool = False,
                                         pair_config: Dict = None) -> bool:
        """
        直接转发媒体组到目标频道，支持统一的过滤功能和媒体组文本重组
        
        Args:
            messages: 消息列表
            source_channel: 源频道标识符
            source_id: 源频道ID
            target_channels: 目标频道列表(频道标识符, 频道ID, 频道信息)
            hide_author: 是否隐藏作者
            pair_config: 频道对配置（包含过滤规则）
            
        Returns:
            bool: 是否成功转发到至少一个目标频道
        """
        if not messages:
            _logger.warning("消息列表为空，跳过转发")
            return False
        
        # 如果提供了频道对配置，应用过滤规则
        filtered_messages = messages
        media_group_texts = {}
        
        # 优先使用Forwarder传递的媒体组文本信息（避免重复过滤）
        if pair_config and 'media_group_texts' in pair_config:
            media_group_texts = pair_config.get('media_group_texts', {})
            _logger.debug(f"🔍 DirectForwarder接收到Forwarder传递的媒体组文本: {len(media_group_texts)} 个")
            # for group_id, text in media_group_texts.items():
            #     _logger.debug(f"  媒体组 {group_id}: '{text[:50]}...'")
            # 不需要重新过滤，因为MediaGroupCollector已经过滤过了
            filtered_messages = messages
        elif pair_config:
            # 如果没有预传递的文本信息，才进行过滤
            filtered_messages, _, filter_stats = self.message_filter.apply_all_filters(messages, pair_config)
            media_group_texts = filter_stats.get('media_group_texts', {})
            
            # 添加调试日志查看媒体组文本内容
            if media_group_texts:
                _logger.debug(f"🔍 DirectForwarder获取到媒体组文本: {list(media_group_texts.keys())}")
                for group_id, text in media_group_texts.items():
                    _logger.debug(f"  媒体组 {group_id}: '{text[:50]}...'")
            else:
                _logger.debug(f"🔍 DirectForwarder未获取到任何媒体组文本")
            
            if not filtered_messages:
                _logger.info(f"⚠️ 所有消息都被过滤器过滤掉，跳过转发")
                return False
            
            if len(filtered_messages) != len(messages):
                _logger.info(f"✅ 过滤完成，剩余 {len(filtered_messages)}/{len(messages)} 条消息进行转发")
                
                # 如果是媒体组且进行了媒体类型过滤，需要重组
                original_media_group_id = getattr(messages[0], 'media_group_id', None)
                if original_media_group_id and len(filtered_messages) > 1:
                    _logger.info(f"📝 媒体组部分过滤，需要重组媒体组并应用标题")
        
        # 检查是否需要文本替换
        text_replacements = {}
        if pair_config:
            # 构建文本替换字典
            text_filter_list = pair_config.get('text_filter', [])
            if text_filter_list:
                for rule in text_filter_list:
                    original = rule.get('original_text', '')
                    target = rule.get('target_text', '')
                    if original:  # 只添加非空的原文
                        text_replacements[original] = target
        
        # 检查是否是重组的媒体组（多条消息但原本是一个媒体组）
        original_media_group_id = getattr(messages[0], 'media_group_id', None) if messages else None
        
        # 判断是否需要重组：
        # 1. 消息有媒体组ID（说明原本是媒体组）
        # 2. 配置中排除了某些媒体类型（可能导致过滤）
        # 3. 当前消息数量大于1（避免单条消息使用重组模式）
        current_group_size = len(filtered_messages)
        
        # 检查配置是否排除了某些常见的媒体类型
        allowed_media_types = pair_config.get('media_types', []) if pair_config else []
        all_media_types = ['text', 'photo', 'video', 'document', 'audio', 'animation', 'sticker', 'voice', 'video_note']
        has_excluded_media_types = len(allowed_media_types) < len(all_media_types)
        
        # 重组条件：有媒体组ID，排除了某些媒体类型，且当前有多条消息
        has_filtering = (original_media_group_id is not None and 
                        has_excluded_media_types and 
                        current_group_size > 1)
        
        is_regrouped_media = has_filtering

        # 如果检测到可能的过滤，强制重组模式（避免copy_media_group绕过过滤结果）
        if has_filtering:
            excluded_types = [t for t in all_media_types if t not in allowed_media_types]
            _logger.info(f"🔧 检测到媒体组可能被过滤 (媒体组ID: {original_media_group_id}, 排除类型: {excluded_types}, 当前消息数: {current_group_size})，使用重组模式确保过滤生效")
        
        # 如果有文本替换需求或需要重组，需要使用copy方式
        need_text_replacement = bool(text_replacements)
        force_copy_mode = (need_text_replacement or 
                         pair_config.get('remove_captions', False) or 
                         is_regrouped_media)
        
        # 检查是否是单条消息
        is_single = len(filtered_messages) == 1
        
        # 消息ID列表（用于日志和事件）
        message_ids = [msg.id for msg in filtered_messages]
        
        # 媒体组ID（用于事件通知）
        group_id = f"single_{message_ids[0]}" if is_single else f"group_{message_ids[0]}"
        
        # 转发成功计数
        success_count = 0
        
        for target_channel, target_id, target_info in target_channels:
            # 检查是否收到停止信号
            if self.should_stop:
                _logger.info("收到停止信号，终止目标频道转发")
                break
                
            # 检查是否已转发到此频道
            all_forwarded = True
            for message in filtered_messages:
                if not self.history_manager or not self.history_manager.is_message_forwarded(source_channel, message.id, target_channel):
                    all_forwarded = False
                    break
            
            if all_forwarded:
                _logger.debug(f"消息已转发到频道 {target_info}，跳过")
                continue
            
            try:
                _logger.info(f"转发消息到频道 {target_info}")
                
                if is_single:
                    # 单条消息转发
                    message = filtered_messages[0]
                    
                    # 处理文本替换
                    final_caption = None
                    if force_copy_mode:
                        original_caption = message.caption or ""
                        if pair_config.get('remove_captions', False):
                            final_caption = ""
                        elif text_replacements and original_caption:
                            final_caption, _ = self.message_filter.apply_text_replacements(original_caption, text_replacements)
                        else:
                            final_caption = original_caption
                    
                    try:
                        if force_copy_mode:
                            # 使用copy_message支持文本替换
                            _logger.debug(f"使用copy_message方法转发消息 {message.id} (支持文本替换)")
                            
                            forwarded = await self.client.copy_message(
                                chat_id=target_id,
                                from_chat_id=source_id,
                                message_id=message.id,
                                caption=final_caption
                            )
                        elif hide_author:
                            # 使用copy_message隐藏作者
                            _logger.debug(f"使用copy_message方法隐藏作者转发消息 {message.id}")
                            
                            forwarded = await self.client.copy_message(
                                chat_id=target_id,
                                from_chat_id=source_id,
                                message_id=message.id
                            )
                        else:
                            # 使用forward_messages保留作者信息
                            _logger.debug(f"使用forward_messages方法保留作者转发消息 {message.id}")
                            
                            forwarded = await self.client.forward_messages(
                                chat_id=target_id,
                                from_chat_id=source_id,
                                message_ids=message.id,
                                disable_notification=True
                            )
                        
                        # 转发成功后才记录历史
                        if self.history_manager:
                            self.history_manager.add_forward_record(
                                source_channel,
                                message.id,
                                target_channel,
                                source_id
                            )
                        
                        _logger.info(f"✅ 消息 {message.id} 转发到 {target_info} 成功")
                        success_count += 1
                        
                        # 发射单条消息转发完成信号
                        if self.emit:
                            try:
                                self.emit("message_forwarded", message.id, target_info)
                            except Exception as e:
                                _logger.debug(f"发射message_forwarded信号失败: {e}")
                                
                    except Exception as e:
                        _logger.error(f"转发单条消息 {message.id} 到 {target_info} 失败: {e}，跳过")
                        continue
                else:
                    # 媒体组转发（包括重组后的媒体组）
                    try:
                        if is_regrouped_media:
                            # 重组的媒体组：使用send_media_group发送，保持真正的媒体组格式
                            _logger.info(f"📝 重组媒体组转发: 使用send_media_group发送 {len(filtered_messages)} 条媒体")
                            
                            # 添加调试日志查看媒体组ID
                            _logger.debug(f"🔍 当前媒体组ID: {original_media_group_id}")
                            _logger.debug(f"🔍 可用的媒体组文本: {list(media_group_texts.keys())}")
                            
                            # 获取媒体组原始文本（如果有保存的）
                            group_caption = ""
                            if original_media_group_id and original_media_group_id in media_group_texts:
                                group_caption = media_group_texts[original_media_group_id]
                                _logger.debug(f"✅ 使用保存的媒体组文本: '{group_caption[:50]}...'")
                            
                            # 如果没有保存的媒体组文本，寻找第一个有标题的消息作为媒体组标题
                            if not group_caption:
                                _logger.debug(f"🔍 未找到保存的媒体组文本，在过滤后的消息中寻找标题")
                                for msg in filtered_messages:
                                    if msg.caption:
                                        group_caption = msg.caption
                                        _logger.debug(f"✅ 使用第一个有标题的消息作为媒体组标题: '{group_caption[:50]}...'")
                                        break
                                
                                # 如果过滤后的消息中没有标题，尝试从原始消息中寻找
                                if not group_caption:
                                    _logger.debug(f"🔍 过滤后的消息中没有标题，尝试从原始消息中寻找")
                                    for msg in messages:
                                        if msg.caption:
                                            group_caption = msg.caption
                                            _logger.debug(f"✅ 从原始消息中找到标题: '{group_caption[:50]}...'")
                                            break
                            
                            if not group_caption:
                                _logger.warning(f"⚠️ 无法找到媒体组标题，媒体组将没有说明文字")
                            
                            # 检查是否移除说明
                            remove_captions = pair_config.get('remove_captions', False)
                            _logger.debug(f"🔍 移除说明配置: {remove_captions}")
                            
                            # 创建InputMedia列表
                            media_list = []
                            for i, message in enumerate(filtered_messages):
                                # 处理每条消息的标题
                                if remove_captions:
                                    # 如果配置了移除说明，所有消息都不带标题
                                    caption = ""
                                elif group_caption and i == 0:
                                    # 有媒体组文本时，第一条消息使用媒体组文本作为标题
                                    caption = group_caption
                                    # 应用文本替换
                                    if text_replacements:
                                        caption, _ = self.message_filter.apply_text_replacements(caption, text_replacements)
                                        _logger.debug(f"文本替换后的媒体组标题: '{caption[:50]}...'")
                                else:
                                    # 其余消息不带标题，保持Telegram媒体组的标准格式
                                    caption = ""
                                
                                # 根据消息类型创建对应的InputMedia对象
                                input_media = await self._create_input_media_from_message(message, caption)
                                if input_media:
                                    media_list.append(input_media)
                                else:
                                    _logger.warning(f"无法为消息 {message.id} 创建InputMedia对象，跳过")
                            
                            if media_list:
                                # 使用send_media_group发送重组后的媒体组
                                _logger.debug(f"发送包含 {len(media_list)} 个媒体的重组媒体组")
                                forwarded_messages = await self.client.send_media_group(
                                    chat_id=target_id,
                                    media=media_list,
                                    disable_notification=True
                                )
                                
                                # 记录转发历史
                                if self.history_manager:
                                    for message in filtered_messages:
                                        self.history_manager.add_forward_record(
                                            source_channel,
                                            message.id,
                                            target_channel,
                                            source_id
                                        )
                                
                                _logger.info(f"✅ 重组媒体组 {message_ids} 转发到 {target_info} 成功")
                                success_count += 1
                                
                                # 发射媒体组转发完成信号
                                if self.emit:
                                    try:
                                        # 同时传递频道ID以便UI精确匹配
                                        self.emit("media_group_forwarded", message_ids, target_info, len(message_ids), target_id)
                                    except Exception as e:
                                        _logger.debug(f"发射media_group_forwarded信号失败: {e}")
                                        
                            else:
                                _logger.error(f"无法创建任何有效的InputMedia对象，重组媒体组转发失败")
                                continue
                        elif force_copy_mode:
                            # 普通媒体组，需要文本替换或移除说明
                            _logger.debug(f"使用copy_media_group方法转发媒体组 (支持文本替换)")
                            
                            # 获取第一条消息用于文本处理
                            first_message = None
                            original_caption = ""
                            for msg in filtered_messages:
                                if msg.caption:
                                    first_message = msg
                                    original_caption = msg.caption
                                    break
                            
                            # 处理标题
                            final_caption = None
                            if pair_config.get('remove_captions', False):
                                final_caption = ""
                            elif text_replacements and original_caption:
                                final_caption, _ = self.message_filter.apply_text_replacements(original_caption, text_replacements)
                            else:
                                final_caption = original_caption if original_caption else None
                            
                            # 只需要第一条消息的ID，因为copy_media_group会自动获取同一组的所有消息
                            first_message_id = message_ids[0]
                            forwarded = await self.client.copy_media_group(
                                chat_id=target_id,
                                from_chat_id=source_id,
                                message_id=first_message_id,
                                captions=final_caption
                            )
                            
                            # 转发成功后才记录历史
                            if self.history_manager:
                                for message in filtered_messages:
                                    self.history_manager.add_forward_record(
                                        source_channel,
                                        message.id,
                                        target_channel,
                                        source_id
                                    )
                            
                            _logger.info(f"✅ 媒体组 {message_ids} 转发到 {target_info} 成功")
                            success_count += 1
                            
                            # 发射媒体组转发完成信号
                            if self.emit:
                                try:
                                    # 同时传递频道ID以便UI精确匹配
                                    self.emit("media_group_forwarded", message_ids, target_info, len(message_ids), target_id)
                                except Exception as e:
                                    _logger.debug(f"发射media_group_forwarded信号失败: {e}")
                            
                        elif hide_author:
                            # 使用copy_media_group方法隐藏作者
                            _logger.debug(f"使用copy_media_group方法隐藏作者转发媒体组消息")
                            
                            # 只需要第一条消息的ID，因为copy_media_group会自动获取同一组的所有消息
                            first_message_id = message_ids[0]
                            forwarded = await self.client.copy_media_group(
                                chat_id=target_id,
                                from_chat_id=source_id,
                                message_id=first_message_id
                            )
                            
                            # 转发成功后才记录历史
                            if self.history_manager:
                                for message in filtered_messages:
                                    self.history_manager.add_forward_record(
                                        source_channel,
                                        message.id,
                                        target_channel,
                                        source_id
                                    )
                            
                            _logger.info(f"✅ 媒体组 {message_ids} 转发到 {target_info} 成功")
                            success_count += 1
                            
                            # 发射媒体组转发完成信号
                            if self.emit:
                                try:
                                    # 同时传递频道ID以便UI精确匹配
                                    self.emit("media_group_forwarded", message_ids, target_info, len(message_ids), target_id)
                                except Exception as e:
                                    _logger.debug(f"发射media_group_forwarded信号失败: {e}")
                                    
                        else:
                            # 使用forward_messages批量转发
                            _logger.debug(f"使用forward_messages方法保留作者批量转发媒体组消息")
                            
                            forwarded = await self.client.forward_messages(
                                chat_id=target_id,
                                from_chat_id=source_id,
                                message_ids=message_ids,
                                disable_notification=True
                            )
                            
                            # 转发成功后才记录历史
                            if self.history_manager:
                                for message in filtered_messages:
                                    self.history_manager.add_forward_record(
                                        source_channel,
                                        message.id,
                                        target_channel,
                                        source_id
                                    )
                            
                            _logger.info(f"✅ 媒体组 {message_ids} 转发到 {target_info} 成功")
                            success_count += 1
                            
                            # 发射媒体组转发完成信号
                            if self.emit:
                                try:
                                    # 同时传递频道ID以便UI精确匹配
                                    self.emit("media_group_forwarded", message_ids, target_info, len(message_ids), target_id)
                                except Exception as e:
                                    _logger.debug(f"发射media_group_forwarded信号失败: {e}")
                            
                    except Exception as e:
                        _logger.error(f"转发媒体组 {message_ids} 到 {target_info} 失败: {e}，跳过")
                        continue
                
                # 转发延迟
                await asyncio.sleep(1)
            
            except FloodWait as e:
                _logger.warning(f"转发消息时遇到限制，等待 {e.x} 秒")
                
                try:
                    await asyncio.sleep(e.x)
                    # 重试此频道
                    retry_result = await self.forward_media_group_directly(
                        filtered_messages, source_channel, source_id, 
                        [(target_channel, target_id, target_info)], hide_author, pair_config
                    )
                    if retry_result:
                        success_count += 1
                except Exception as retry_e:
                    _logger.error(f"重试转发到频道 {target_info} 失败: {retry_e}")
            
            except Exception as e:
                _logger.error(f"转发消息到频道 {target_info} 失败: {e}")
                import traceback
                _logger.error(traceback.format_exc())
                continue
        
        # 返回是否至少有一个频道转发成功
        return success_count > 0
    
    def _convert_text_filter_to_replacements(self, text_filter_list: List[Dict]) -> Dict[str, str]:
        """
        将UI格式的文本过滤规则转换为替换字典
        
        Args:
            text_filter_list: UI格式的文本过滤规则列表
            
        Returns:
            Dict[str, str]: 文本替换字典 {原文: 替换文本}
        """
        text_replacements = {}
        if text_filter_list:
            for rule in text_filter_list:
                original = rule.get('original_text', '')
                target = rule.get('target_text', '')
                if original:  # 只添加非空的原文
                    text_replacements[original] = target
        return text_replacements 

    async def _create_input_media_from_message(self, message: Message, caption: str) -> Optional[Union[InputMediaPhoto, InputMediaVideo, InputMediaDocument, InputMediaAudio, InputMediaAnimation]]:
        """
        根据消息类型创建对应的InputMedia对象
        
        Args:
            message: 消息对象
            caption: 消息的标题
            
        Returns:
            Optional[Union[InputMediaPhoto, InputMediaVideo, InputMediaDocument, InputMediaAudio, InputMediaAnimation]]: 创建的InputMedia对象或None
        """
        if message.photo:
            return InputMediaPhoto(message.photo.file_id, caption=caption)
        elif message.video:
            return InputMediaVideo(message.video.file_id, caption=caption)
        elif message.document:
            return InputMediaDocument(message.document.file_id, caption=caption)
        elif message.audio:
            return InputMediaAudio(message.audio.file_id, caption=caption)
        elif message.animation:
            return InputMediaAnimation(message.animation.file_id, caption=caption)
        else:
            _logger.warning(f"消息 {message.id} 不包含支持的媒体类型，无法创建InputMedia对象")
            return None 