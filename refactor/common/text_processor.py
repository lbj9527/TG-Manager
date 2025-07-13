"""
统一文本处理器

处理文本替换、标题移除等文本相关操作。
"""
from typing import Any, Dict, Tuple
from loguru import logger

class TextProcessor:
    """统一的文本处理器，处理文本替换和文本相关操作"""
    def __init__(self):
        self.logger = logger

    def process_message_text(self, message: Any, pair_config: Dict[str, Any]) -> Tuple[str, bool]:
        """
        处理消息文本，包括文本替换和标题移除
        Returns: (处理后的文本, 是否发生替换)
        """
        text = self._extract_text_from_message(message)
        if not text:
            return None, False
        text_replacements = self._build_text_replacements(pair_config)
        processed_text, has_replacement = self.apply_text_replacements(text, text_replacements)
        should_remove_caption = pair_config.get('remove_captions', False)
        if should_remove_caption and self._is_media_message(message):
            processed_text = None
            has_replacement = True
        return processed_text, has_replacement

    def apply_text_replacements(self, text: str, text_replacements: Dict[str, str]) -> Tuple[str, bool]:
        """
        应用文本替换规则
        """
        if not text or not text_replacements:
            return text, False
        result_text = text
        has_replacement = False
        for find_text, replace_text in text_replacements.items():
            if find_text and find_text in result_text:
                result_text = result_text.replace(find_text, replace_text)
                has_replacement = True
                self.logger.debug(f"文本替换: '{find_text}' -> '{replace_text}'")
        return result_text, has_replacement

    def _extract_text_from_message(self, message: Any) -> str:
        """
        从消息中提取文本内容
        """
        return getattr(message, 'text', None) or getattr(message, 'caption', None) or ""

    def _build_text_replacements(self, pair_config: Dict[str, Any]) -> Dict[str, str]:
        """
        构建文本替换规则字典
        """
        text_replacements = {}
        text_filter_list = pair_config.get('text_filter', [])
        for rule in text_filter_list:
            if isinstance(rule, dict):
                original_text = rule.get('original_text', '')
                target_text = rule.get('target_text', '')
                if original_text:
                    text_replacements[original_text] = target_text
        return text_replacements

    def _is_media_message(self, message: Any) -> bool:
        """
        检查是否为媒体消息
        """
        return bool(getattr(message, 'media', None)) 