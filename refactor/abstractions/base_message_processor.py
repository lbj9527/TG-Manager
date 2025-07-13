"""
消息处理抽象基类

提供统一的消息处理流程，供转发、监听等插件继承。
"""

from typing import Any, Dict, Optional, Callable
import asyncio
from common.text_processor import TextProcessor
from common.message_filter import MessageFilter
from common.media_group_processor import MediaGroupProcessor

class BaseMessageProcessor:
    """消息处理抽象基类，提供通用的消息处理功能"""
    def __init__(self, client: Any, channel_resolver: Any, emit: Optional[Callable] = None):
        self.client = client
        self.channel_resolver = channel_resolver
        self.emit = emit
        # 自动组合通用组件
        self.text_processor = TextProcessor()
        self.message_filter = MessageFilter()
        self.media_group_processor = MediaGroupProcessor()

    async def process_message(self, message: Any, pair_config: Dict[str, Any]) -> bool:
        """
        处理单条消息的通用流程
        """
        # 1. 应用通用过滤规则
        should_filter, filter_reason = self.message_filter.apply_universal_filters(message, pair_config)
        if should_filter:
            if self.emit:
                self.emit("message_filtered", message.id, "通用过滤", filter_reason)
            return False
        # 2. 应用关键词过滤
        if not self.message_filter.apply_keyword_filter(message, pair_config):
            if self.emit:
                self.emit("message_filtered", message.id, "关键词过滤", "不包含关键词")
            return False
        # 3. 应用媒体类型过滤
        if not self.message_filter.apply_media_type_filter(message, pair_config):
            if self.emit:
                self.emit("message_filtered", message.id, "媒体类型过滤", "媒体类型不匹配")
            return False
        # 4. 处理文本替换
        processed_text, has_replacement = self.text_processor.process_message_text(message, pair_config)
        if has_replacement and self.emit:
            self.emit("text_replacement_applied", "消息文本", getattr(message, 'text', None), processed_text)
        # 5. 子类实现具体的转发/监听逻辑
        return await self._forward_message(message, pair_config, processed_text)

    async def _forward_message(self, message: Any, pair_config: Dict[str, Any], processed_text: Optional[str]) -> bool:
        """
        子类需要实现的转发/监听逻辑
        """
        raise NotImplementedError 