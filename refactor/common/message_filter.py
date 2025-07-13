"""
统一消息过滤器

提供所有过滤功能，包括通用过滤、关键词、媒体类型、链接等。
"""
import re
from typing import Any, Dict, Tuple, List
from loguru import logger

class MessageFilter:
    """统一的消息过滤器，提供所有过滤功能"""
    def __init__(self):
        self.logger = logger

    def apply_universal_filters(self, message: Any, pair_config: Dict[str, Any]) -> Tuple[bool, str]:
        """
        应用通用过滤规则（最高优先级）
        Returns: (是否过滤, 原因)
        """
        if pair_config.get('exclude_forwards', False) and (getattr(message, 'forward_from', None) or getattr(message, 'forward_from_chat', None)):
            return True, "转发消息"
        if pair_config.get('exclude_replies', False) and getattr(message, 'reply_to_message', None):
            return True, "回复消息"
        if pair_config.get('exclude_text', False) and not getattr(message, 'media', None):
            return True, "纯文本消息"
        if pair_config.get('exclude_links', False) and self._contains_links(message):
            return True, "包含链接"
        return False, ""

    def apply_keyword_filter(self, message: Any, pair_config: Dict[str, Any]) -> bool:
        """
        应用关键词过滤
        Returns: 是否通过
        """
        keywords = pair_config.get('keywords', [])
        if not keywords:
            return True
        text = getattr(message, 'text', None) or getattr(message, 'caption', None) or ""
        if not text:
            return False
        for keyword in keywords:
            if keyword.lower() in text.lower():
                self.logger.info(f"消息 [ID: {getattr(message, 'id', None)}] 匹配关键词: {keyword}")
                return True
        return False

    def apply_media_type_filter(self, message: Any, pair_config: Dict[str, Any]) -> bool:
        """
        应用媒体类型过滤
        Returns: 是否通过
        """
        allowed_media_types = pair_config.get('media_types', [])
        if not allowed_media_types:
            return True
        message_media_type = self._get_message_media_type(message)
        if not message_media_type:
            return True  # 纯文本消息，如果没有明确排除则通过
        return message_media_type in allowed_media_types

    def _contains_links(self, message: Any) -> bool:
        """
        检查消息是否包含链接
        """
        text = getattr(message, 'text', None) or getattr(message, 'caption', None) or ""
        if not text:
            return False
        link_patterns = [
            r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
            r'www\.(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
            r't\.me/[a-zA-Z0-9_]+',
            r'telegram\.me/[a-zA-Z0-9_]+'
        ]
        for pattern in link_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        entities = getattr(message, 'entities', []) or []
        for entity in entities:
            if getattr(entity, 'type', None) in ['url', 'text_link']:
                return True
        return False

    def _get_message_media_type(self, message: Any) -> str:
        """
        获取消息的媒体类型
        """
        media = getattr(message, 'media', None)
        if not media:
            return None
        media_type_map = {
            'photo': 'photo',
            'video': 'video',
            'document': 'document',
            'audio': 'audio',
            'animation': 'animation',
            'sticker': 'sticker',
            'voice': 'voice',
            'video_note': 'video_note'
        }
        value = getattr(media, 'value', None)
        return media_type_map.get(value, None) 