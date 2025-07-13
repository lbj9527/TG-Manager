"""
TextProcessor 单元测试
"""
import pytest
from unittest.mock import Mock
from common.text_processor import TextProcessor

class TestTextProcessor:
    def setup_method(self):
        self.processor = TextProcessor()

    def test_extract_text_from_message_text(self):
        """测试从文本消息提取文本"""
        message = Mock()
        message.text = "Hello World"
        message.caption = None
        
        result = self.processor._extract_text_from_message(message)
        assert result == "Hello World"

    def test_extract_text_from_message_caption(self):
        """测试从媒体消息提取标题"""
        message = Mock()
        message.text = None
        message.caption = "Test Caption"
        
        result = self.processor._extract_text_from_message(message)
        assert result == "Test Caption"

    def test_extract_text_from_message_empty(self):
        """测试从空消息提取文本"""
        message = Mock()
        message.text = None
        message.caption = None
        
        result = self.processor._extract_text_from_message(message)
        assert result == ""

    def test_build_text_replacements(self):
        """测试构建文本替换规则"""
        pair_config = {
            'text_filter': [
                {'original_text': 'A', 'target_text': 'B'},
                {'original_text': 'Hello', 'target_text': 'Hi'},
                {'original_text': '', 'target_text': 'Empty'}  # 应该被忽略
            ]
        }
        
        result = self.processor._build_text_replacements(pair_config)
        expected = {'A': 'B', 'Hello': 'Hi'}
        assert result == expected

    def test_apply_text_replacements_no_replacements(self):
        """测试无替换规则的情况"""
        text = "Hello World"
        replacements = {}
        
        result, has_replacement = self.processor.apply_text_replacements(text, replacements)
        assert result == "Hello World"
        assert has_replacement is False

    def test_apply_text_replacements_single_replacement(self):
        """测试单个文本替换"""
        text = "Hello World"
        replacements = {'Hello': 'Hi'}
        
        result, has_replacement = self.processor.apply_text_replacements(text, replacements)
        assert result == "Hi World"
        assert has_replacement is True

    def test_apply_text_replacements_multiple_replacements(self):
        """测试多个文本替换"""
        text = "Hello A World"
        replacements = {'Hello': 'Hi', 'A': 'B'}
        
        result, has_replacement = self.processor.apply_text_replacements(text, replacements)
        assert result == "Hi B World"
        assert has_replacement is True

    def test_apply_text_replacements_no_match(self):
        """测试无匹配的替换"""
        text = "Hello World"
        replacements = {'Goodbye': 'Bye'}
        
        result, has_replacement = self.processor.apply_text_replacements(text, replacements)
        assert result == "Hello World"
        assert has_replacement is False

    def test_is_media_message_true(self):
        """测试媒体消息检测"""
        message = Mock()
        message.media = Mock()
        
        result = self.processor._is_media_message(message)
        assert result is True

    def test_is_media_message_false(self):
        """测试非媒体消息检测"""
        message = Mock()
        message.media = None
        
        result = self.processor._is_media_message(message)
        assert result is False

    def test_process_message_text_with_replacements(self):
        """测试完整的消息文本处理（有替换）"""
        message = Mock()
        message.text = "Hello A World"
        message.caption = None
        
        pair_config = {
            'text_filter': [
                {'original_text': 'A', 'target_text': 'B'}
            ],
            'remove_captions': False
        }
        
        result, has_replacement = self.processor.process_message_text(message, pair_config)
        assert result == "Hello B World"
        assert has_replacement is True

    def test_process_message_text_remove_captions(self):
        """测试移除媒体标题"""
        message = Mock()
        message.text = None
        message.caption = "Test Caption"
        message.media = Mock()  # 媒体消息
        
        pair_config = {
            'text_filter': [],
            'remove_captions': True
        }
        
        result, has_replacement = self.processor.process_message_text(message, pair_config)
        assert result is None
        assert has_replacement is True

    def test_process_message_text_no_changes(self):
        """测试无变化的文本处理"""
        message = Mock()
        message.text = "Hello World"
        message.caption = None
        
        pair_config = {
            'text_filter': [],
            'remove_captions': False
        }
        
        result, has_replacement = self.processor.process_message_text(message, pair_config)
        assert result == "Hello World"
        assert has_replacement is False 