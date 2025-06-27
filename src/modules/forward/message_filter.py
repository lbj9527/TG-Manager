"""
消息过滤器，用于过滤符合条件的消息
提供统一的文本替换、关键词过滤、媒体类型过滤功能
"""

from typing import List, Dict, Any, Tuple, Optional
import re

from pyrogram.types import Message

from src.utils.logger import get_logger

_logger = get_logger()

class MessageFilter:
    """
    统一的消息过滤器，用于过滤特定类型的消息
    支持文本替换、关键词过滤、媒体类型过滤等功能
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化消息过滤器
        
        Args:
            config: 配置信息，包含过滤规则
        """
        self.config = config or {}
    
    def apply_keyword_filter(self, messages: List[Message], keywords: List[str]) -> Tuple[List[Message], List[Message]]:
        """
        应用关键词过滤，支持媒体组级别的过滤
        媒体组中任何一条消息包含关键词，则整个媒体组都通过过滤
        
        Args:
            messages: 消息列表
            keywords: 关键词列表
            
        Returns:
            Tuple[List[Message], List[Message]]: (通过的消息, 被过滤的消息)
        """
        if not keywords:
            return messages, []
        
        # 首先按媒体组分组
        media_groups = self._group_messages_by_media_group(messages)
        
        passed_messages = []
        filtered_messages = []
        
        # 用于统计
        passed_groups = []
        filtered_groups = []
        
        for group_messages in media_groups:
            # 检查媒体组中是否有任何消息包含关键词
            group_has_keyword = False
            keywords_found_in_group = []
            
            for message in group_messages:
                # 获取要检查的文本内容
                text_content = ""
                if message.caption:
                    text_content = message.caption
                elif message.text:
                    text_content = message.text
                
                if text_content:
                    # 检查是否包含任何关键词（不区分大小写）
                    for keyword in keywords:
                        if keyword.lower() in text_content.lower():
                            group_has_keyword = True
                            if keyword not in keywords_found_in_group:
                                keywords_found_in_group.append(keyword)
            
            # 获取媒体组ID用于日志
            group_ids = [msg.id for msg in group_messages]
            
            if group_has_keyword:
                # 整个媒体组通过过滤
                passed_messages.extend(group_messages)
                passed_groups.append(group_ids)
                _logger.debug(f"媒体组 [ID: {group_ids}] 包含关键词 {keywords_found_in_group}，整个媒体组通过过滤")
            else:
                # 整个媒体组被过滤
                filtered_messages.extend(group_messages)
                filtered_groups.append(group_ids)
        
        # 汇总日志显示
        if filtered_groups:
            filtered_count = sum(len(group) for group in filtered_groups)
            group_count = len(filtered_groups)
            sample_groups = filtered_groups[:3]  # 显示前3个媒体组
            group_display = []
            for group in sample_groups:
                if len(group) == 1:
                    group_display.append(str(group[0]))
                else:
                    group_display.append(f"[{','.join(map(str, group))}]")
            
            more_indicator = f", +{group_count - 3}个媒体组" if group_count > 3 else ""
            _logger.info(f"关键词过滤: {group_count} 个媒体组({filtered_count} 条消息)不包含关键词 {keywords} 被过滤 (组ID: {', '.join(group_display)}{more_indicator})")
        
        if passed_groups:
            passed_count = sum(len(group) for group in passed_groups)
            group_count = len(passed_groups)
            sample_groups = passed_groups[:3]  # 显示前3个媒体组
            group_display = []
            for group in sample_groups:
                if len(group) == 1:
                    group_display.append(str(group[0]))
                else:
                    group_display.append(f"[{','.join(map(str, group))}]")
            
            more_indicator = f", +{group_count - 3}个媒体组" if group_count > 3 else ""
            _logger.info(f"关键词过滤: {group_count} 个媒体组({passed_count} 条消息)包含关键词通过过滤 (组ID: {', '.join(group_display)}{more_indicator})")
        
        return passed_messages, filtered_messages
    
    def apply_media_type_filter(self, messages: List[Message], allowed_media_types: List[str]) -> Tuple[List[Message], List[Message]]:
        """
        应用媒体类型过滤，支持媒体组级别的过滤
        
        Args:
            messages: 消息列表
            allowed_media_types: 允许的媒体类型列表
            
        Returns:
            Tuple[List[Message], List[Message]]: (通过的消息, 被过滤的消息)
        """
        if not allowed_media_types:
            return messages, []
        
        # 按媒体组分组
        media_groups = self._group_messages_by_media_group(messages)
        
        passed_messages = []
        filtered_messages = []
        
        for group_messages in media_groups:
            # 检查媒体组中是否有任何消息的媒体类型在允许列表中
            group_has_allowed_media = False
            
            for message in group_messages:
                message_media_type = self._get_message_media_type(message)
                
                if message_media_type:
                    if self._is_media_type_allowed(message_media_type, allowed_media_types):
                        group_has_allowed_media = True
                        break
            
            group_ids = [msg.id for msg in group_messages]
            
            if group_has_allowed_media:
                passed_messages.extend(group_messages)
                _logger.debug(f"媒体组 [ID: {group_ids}] 包含允许的媒体类型，通过过滤")
            else:
                filtered_messages.extend(group_messages)
                media_types_in_group = [self._get_message_media_type(msg) for msg in group_messages]
                _logger.debug(f"媒体组 [ID: {group_ids}] 媒体类型 {media_types_in_group} 不在允许列表中，被过滤")
        
        return passed_messages, filtered_messages
    
    def apply_text_replacements(self, text: str, text_replacements: Dict[str, str]) -> Tuple[str, bool]:
        """
        应用文本替换规则到文本内容
        
        Args:
            text: 原始文本
            text_replacements: 文本替换规则字典 {原文: 替换文本}
            
        Returns:
            Tuple[str, bool]: (替换后的文本, 是否发生了替换)
        """
        if not text or not text_replacements:
            return text, False
        
        result_text = text
        has_replacement = False
        
        for find_text, replace_text in text_replacements.items():
            if find_text and find_text in result_text:
                result_text = result_text.replace(find_text, replace_text)
                has_replacement = True
                _logger.debug(f"应用文本替换: '{find_text}' -> '{replace_text}'")
        
        return result_text, has_replacement
    
    def apply_general_filters(self, messages: List[Message], pair_config: Dict[str, Any]) -> Tuple[List[Message], List[Message]]:
        """
        应用通用过滤规则，支持媒体组级别的过滤
        （排除转发消息、回复消息、纯文本消息、包含链接的消息）
        
        Args:
            messages: 消息列表
            pair_config: 频道对配置
            
        Returns:
            Tuple[List[Message], List[Message]]: (通过的消息, 被过滤的消息)
        """
        # 按媒体组分组
        media_groups = self._group_messages_by_media_group(messages)
        
        passed_messages = []
        filtered_messages = []
        
        # 获取过滤规则
        exclude_forwards = pair_config.get('exclude_forwards', False)
        exclude_replies = pair_config.get('exclude_replies', False)
        exclude_text = pair_config.get('exclude_text', False)
        exclude_links = pair_config.get('exclude_links', False)
        
        for group_messages in media_groups:
            should_filter_group = False
            filter_reason = ""
            
            # 检查媒体组中是否有任何消息触发过滤规则
            for message in group_messages:
                # 排除转发消息
                if exclude_forwards and message.forward_from:
                    should_filter_group = True
                    filter_reason = "包含转发消息"
                    break
                
                # 排除回复消息
                if exclude_replies and message.reply_to_message:
                    should_filter_group = True
                    filter_reason = "包含回复消息"
                    break
                
                # 排除纯文本消息（整个媒体组都是纯文本才过滤）
                if exclude_text:
                    is_media_message = bool(message.photo or message.video or message.document or 
                                          message.audio or message.animation or message.sticker or 
                                          message.voice or message.video_note)
                    if not is_media_message and (message.text or message.caption):
                        # 检查整个媒体组是否都是纯文本
                        all_text = True
                        for msg in group_messages:
                            if (msg.photo or msg.video or msg.document or msg.audio or 
                                msg.animation or msg.sticker or msg.voice or msg.video_note):
                                all_text = False
                                break
                        if all_text:
                            should_filter_group = True
                            filter_reason = "纯文本媒体组"
                            break
                
                # 排除包含链接的消息
                if exclude_links:
                    text_to_check = message.text or message.caption or ""
                    if self._contains_links(text_to_check):
                        should_filter_group = True
                        filter_reason = "包含链接的消息"
                        break
            
            group_ids = [msg.id for msg in group_messages]
            
            if should_filter_group:
                filtered_messages.extend(group_messages)
                _logger.info(f"媒体组 [ID: {group_ids}] 被通用过滤规则过滤: {filter_reason}")
            else:
                passed_messages.extend(group_messages)
        
        return passed_messages, filtered_messages
    
    def apply_all_filters(self, messages: List[Message], pair_config: Dict[str, Any]) -> Tuple[List[Message], List[Message], Dict[str, Any]]:
        """
        应用所有过滤规则的统一入口
        
        Args:
            messages: 消息列表
            pair_config: 频道对配置
            
        Returns:
            Tuple[List[Message], List[Message], Dict[str, Any]]: (通过的消息, 被过滤的消息, 过滤统计信息)
        """
        original_count = len(messages)
        filter_stats = {
            'original_count': original_count,
            'keyword_filtered': 0,
            'media_type_filtered': 0,
            'general_filtered': 0,
            'final_count': 0
        }
        
        current_messages = messages[:]
        all_filtered_messages = []
        
        # 1. 应用关键词过滤
        keywords = pair_config.get('keywords', [])
        _logger.debug(f"关键词配置: {keywords} (类型: {type(keywords)})")
        if keywords:
            current_messages, keyword_filtered = self.apply_keyword_filter(current_messages, keywords)
            all_filtered_messages.extend(keyword_filtered)
            filter_stats['keyword_filtered'] = len(keyword_filtered)
        else:
            _logger.debug(f"未设置关键词过滤，跳过关键词过滤")
        
        # 2. 应用媒体类型过滤
        allowed_media_types = pair_config.get('media_types', [])
        if allowed_media_types:
            # 确保媒体类型是字符串列表，使用.value属性正确转换枚举
            media_types_str = []
            for t in allowed_media_types:
                if hasattr(t, 'value'):
                    media_types_str.append(t.value)
                else:
                    media_types_str.append(str(t))
            current_messages, media_filtered = self.apply_media_type_filter(current_messages, media_types_str)
            all_filtered_messages.extend(media_filtered)
            filter_stats['media_type_filtered'] = len(media_filtered)
            if len(media_filtered) > 0:
                _logger.info(f"媒体类型过滤: 过滤了 {len(media_filtered)} 条不符合类型要求的消息")
        
        # 3. 应用通用过滤规则
        current_messages, general_filtered = self.apply_general_filters(current_messages, pair_config)
        all_filtered_messages.extend(general_filtered)
        filter_stats['general_filtered'] = len(general_filtered)
        filter_stats['final_count'] = len(current_messages)
        
        if len(general_filtered) > 0:
            _logger.info(f"通用过滤: 过滤了 {len(general_filtered)} 条消息 (转发/回复/链接/纯文本)")
        
        # 总结日志
        total_filtered = len(all_filtered_messages)
        if total_filtered > 0:
            _logger.info(f"📊 过滤结果: {original_count} 条消息 → {len(current_messages)} 条通过 (过滤了 {total_filtered} 条)")
        else:
            _logger.info(f"📊 过滤结果: 所有 {original_count} 条消息都通过了过滤")
        
        return current_messages, all_filtered_messages, filter_stats
    
    def _group_messages_by_media_group(self, messages: List[Message]) -> List[List[Message]]:
        """
        将消息按媒体组进行分组
        
        Args:
            messages: 消息列表
            
        Returns:
            List[List[Message]]: 分组后的消息列表，每个子列表代表一个媒体组
        """
        if not messages:
            return []
        
        # 按媒体组ID分组
        groups = {}
        
        for message in messages:
            # 获取媒体组ID，如果没有则使用消息ID作为唯一组
            group_id = getattr(message, 'media_group_id', None) or message.id
            
            if group_id not in groups:
                groups[group_id] = []
            groups[group_id].append(message)
        
        # 按消息ID排序每个组内的消息
        for group_messages in groups.values():
            group_messages.sort(key=lambda msg: msg.id)
        
        # 按第一个消息的ID排序各个组
        sorted_groups = sorted(groups.values(), key=lambda group: group[0].id)
        
        return sorted_groups
    
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
        elif message.text or message.caption:
            # 纯文本消息（包括只有文本或说明的消息）
            return "text"
        return None
    
    def _is_media_type_allowed(self, message_media_type: str, allowed_media_types: List[str]) -> bool:
        """检查消息的媒体类型是否在允许列表中"""
        if not allowed_media_types:
            return True
        return message_media_type in allowed_media_types
    
    def _contains_links(self, text: str) -> bool:
        """检查文本是否包含链接"""
        if not text:
            return False
        
        # 常见的链接模式
        link_patterns = [
            r'https?://[^\s]+',     # HTTP/HTTPS链接
            r'www\.[^\s]+',         # www开头的链接
            r't\.me/[^\s]+',        # Telegram链接
            r'@\w+',                # @用户名
        ]
        
        for pattern in link_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        return False
    
    def is_media_allowed(self, message: Message, source_channel: str = None) -> bool:
        """
        检查消息媒体类型是否在允许列表中（兼容旧接口）
        
        Args:
            message: 消息对象
            source_channel: 源频道
            
        Returns:
            bool: 是否允许
        """
        forward_config = self.config.get('FORWARD', {})
        
        # 如果没有指定源频道，使用公共设置
        if not source_channel:
            media_types = forward_config.get('media_types', [])
        else:
            # 查找对应的频道对配置
            channel_pairs = forward_config.get('forward_channel_pairs', [])
            media_types = []
            
            # 查找匹配的频道对
            for pair in channel_pairs:
                if pair.get('source_channel') == source_channel and 'media_types' in pair:
                    media_types = pair['media_types']
                    break
            
            # 如果找不到对应的配置，使用默认值
            if not media_types:
                # 使用所有支持的媒体类型作为默认值
                media_types = ["text", "photo", "video", "document", "audio", "animation"]
                _logger.warning(f"找不到源频道 {source_channel} 的媒体类型配置，使用默认值")
        
        # 确保媒体类型是字符串列表，使用.value属性正确转换枚举
        media_types_str = []
        for t in media_types:
            if hasattr(t, 'value'):
                media_types_str.append(t.value)
            else:
                media_types_str.append(str(t))
        
        # 获取消息媒体类型
        message_media_type = self._get_message_media_type(message)
        
        if not message_media_type:
            # 如果无法识别媒体类型，默认不允许
            return False
        
        return self._is_media_type_allowed(message_media_type, media_types_str) 