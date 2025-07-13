"""
MessageFilter 单元测试
"""
import pytest
from unittest.mock import Mock
from common.message_filter import MessageFilter

class TestMessageFilter:
    def setup_method(self):
        self.filter = MessageFilter()

    def test_apply_universal_filters_exclude_forwards(self):
        """测试排除转发消息"""
        message = Mock()
        message.forward_from = Mock()
        message.forward_from_chat = None
        
        pair_config = {'exclude_forwards': True}
        
        should_filter, reason = self.filter.apply_universal_filters(message, pair_config)
        assert should_filter is True
        assert reason == "转发消息"

    def test_apply_universal_filters_exclude_replies(self):
        """测试排除回复消息"""
        message = Mock()
        message.forward_from = None
        message.forward_from_chat = None
        message.reply_to_message = Mock()
        
        pair_config = {'exclude_replies': True}
        
        should_filter, reason = self.filter.apply_universal_filters(message, pair_config)
        assert should_filter is True
        assert reason == "回复消息"

    def test_apply_universal_filters_exclude_text(self):
        """测试排除纯文本消息"""
        message = Mock()
        message.forward_from = None
        message.forward_from_chat = None
        message.reply_to_message = None
        message.media = None
        
        pair_config = {'exclude_text': True}
        
        should_filter, reason = self.filter.apply_universal_filters(message, pair_config)
        assert should_filter is True
        assert reason == "纯文本消息"

    def test_apply_universal_filters_exclude_links(self):
        """测试排除包含链接的消息"""
        message = Mock()
        message.forward_from = None
        message.forward_from_chat = None
        message.reply_to_message = None
        message.media = Mock()
        message.text = "Check this link: https://example.com"
        message.caption = None
        message.entities = []
        
        pair_config = {'exclude_links': True}
        
        should_filter, reason = self.filter.apply_universal_filters(message, pair_config)
        assert should_filter is True
        assert reason == "包含链接"

    def test_apply_universal_filters_no_filters(self):
        """测试无过滤规则"""
        message = Mock()
        message.forward_from = None
        message.forward_from_chat = None
        message.reply_to_message = None
        message.media = Mock()
        message.text = "Normal message"
        message.caption = None
        message.entities = []
        
        pair_config = {}
        
        should_filter, reason = self.filter.apply_universal_filters(message, pair_config)
        assert should_filter is False
        assert reason == ""

    def test_apply_keyword_filter_with_keywords_match(self):
        """测试关键词过滤匹配"""
        message = Mock()
        message.text = "Hello World"
        message.caption = None
        
        pair_config = {'keywords': ['Hello', 'World']}
        
        result = self.filter.apply_keyword_filter(message, pair_config)
        assert result is True

    def test_apply_keyword_filter_with_keywords_no_match(self):
        """测试关键词过滤不匹配"""
        message = Mock()
        message.text = "Hello World"
        message.caption = None
        
        pair_config = {'keywords': ['Goodbye', 'Bye']}
        
        result = self.filter.apply_keyword_filter(message, pair_config)
        assert result is False

    def test_apply_keyword_filter_no_keywords(self):
        """测试无关键词配置"""
        message = Mock()
        message.text = "Hello World"
        message.caption = None
        
        pair_config = {}
        
        result = self.filter.apply_keyword_filter(message, pair_config)
        assert result is True

    def test_apply_keyword_filter_empty_text(self):
        """测试空文本的关键词过滤"""
        message = Mock()
        message.text = None
        message.caption = None
        
        pair_config = {'keywords': ['Hello']}
        
        result = self.filter.apply_keyword_filter(message, pair_config)
        assert result is False

    def test_apply_media_type_filter_allowed_type(self):
        """测试媒体类型过滤允许的类型"""
        message = Mock()
        message.media = Mock()
        message.media.value = "photo"
        
        pair_config = {'media_types': ['photo', 'video']}
        
        result = self.filter.apply_media_type_filter(message, pair_config)
        assert result is True

    def test_apply_media_type_filter_not_allowed_type(self):
        """测试媒体类型过滤不允许的类型"""
        message = Mock()
        message.media = Mock()
        message.media.value = "document"
        
        pair_config = {'media_types': ['photo', 'video']}
        
        result = self.filter.apply_media_type_filter(message, pair_config)
        assert result is False

    def test_apply_media_type_filter_no_media_types(self):
        """测试无媒体类型配置"""
        message = Mock()
        message.media = Mock()
        message.media.value = "photo"
        
        pair_config = {}
        
        result = self.filter.apply_media_type_filter(message, pair_config)
        assert result is True

    def test_apply_media_type_filter_text_message(self):
        """测试纯文本消息的媒体类型过滤"""
        message = Mock()
        message.media = None
        
        pair_config = {'media_types': ['photo', 'video']}
        
        result = self.filter.apply_media_type_filter(message, pair_config)
        assert result is True

    def test_contains_links_http_url(self):
        """测试检测HTTP链接"""
        message = Mock()
        message.text = "Check this: http://example.com"
        message.caption = None
        message.entities = []
        
        result = self.filter._contains_links(message)
        assert result is True

    def test_contains_links_https_url(self):
        """测试检测HTTPS链接"""
        message = Mock()
        message.text = "Check this: https://example.com"
        message.caption = None
        message.entities = []
        
        result = self.filter._contains_links(message)
        assert result is True

    def test_contains_links_www_url(self):
        """测试检测WWW链接"""
        message = Mock()
        message.text = "Check this: www.example.com"
        message.caption = None
        message.entities = []
        
        result = self.filter._contains_links(message)
        assert result is True

    def test_contains_links_telegram_url(self):
        """测试检测Telegram链接"""
        message = Mock()
        message.text = "Check this: t.me/username"
        message.caption = None
        message.entities = []
        
        result = self.filter._contains_links(message)
        assert result is True

    def test_contains_links_no_links(self):
        """测试无链接的消息"""
        message = Mock()
        message.text = "Normal message without links"
        message.caption = None
        message.entities = []
        
        result = self.filter._contains_links(message)
        assert result is False

    def test_contains_links_with_entities(self):
        """测试通过实体检测链接"""
        message = Mock()
        message.text = "Check this link"
        message.caption = None
        
        entity = Mock()
        entity.type = "url"
        message.entities = [entity]
        
        result = self.filter._contains_links(message)
        assert result is True

    def test_get_message_media_type_photo(self):
        """测试获取照片媒体类型"""
        message = Mock()
        message.media = Mock()
        message.media.value = "photo"
        
        result = self.filter._get_message_media_type(message)
        assert result == "photo"

    def test_get_message_media_type_video(self):
        """测试获取视频媒体类型"""
        message = Mock()
        message.media = Mock()
        message.media.value = "video"
        
        result = self.filter._get_message_media_type(message)
        assert result == "video"

    def test_get_message_media_type_unknown(self):
        """测试未知媒体类型"""
        message = Mock()
        message.media = Mock()
        message.media.value = "unknown_type"
        
        result = self.filter._get_message_media_type(message)
        assert result is None

    def test_get_message_media_type_no_media(self):
        """测试无媒体消息"""
        message = Mock()
        message.media = None
        
        result = self.filter._get_message_media_type(message)
        assert result is None 