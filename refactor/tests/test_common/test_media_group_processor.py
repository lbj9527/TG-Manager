"""
MediaGroupProcessor 单元测试
"""
import pytest
from unittest.mock import Mock
from common.media_group_processor import MediaGroupProcessor

class TestMediaGroupProcessor:
    def setup_method(self):
        self.processor = MediaGroupProcessor()

    def test_process_media_group_message_single_message(self):
        """测试处理单条消息（非媒体组）"""
        message = Mock()
        message.media_group_id = None
        
        pair_config = {'test': 'config'}
        
        result = self.processor.process_media_group_message(message, pair_config)
        assert result is None

    def test_process_media_group_message_new_group(self):
        """测试处理新的媒体组消息"""
        message = Mock()
        message.media_group_id = "group_123"
        
        pair_config = {'test': 'config'}
        
        result = self.processor.process_media_group_message(message, pair_config)
        assert result is None  # 媒体组不完整
        
        # 检查缓存
        assert "group_123" in self.processor.media_group_cache
        cached_data = self.processor.media_group_cache["group_123"]
        assert cached_data['messages'] == [message]
        assert cached_data['config'] == pair_config

    def test_process_media_group_message_existing_group(self):
        """测试处理已存在的媒体组消息"""
        # 先添加一条消息到媒体组
        message1 = Mock()
        message1.media_group_id = "group_123"
        
        pair_config = {'test': 'config'}
        
        self.processor.media_group_cache["group_123"] = {
            'messages': [message1],
            'timestamp': 1234567890,
            'config': pair_config
        }
        
        # 添加第二条消息
        message2 = Mock()
        message2.media_group_id = "group_123"
        
        result = self.processor.process_media_group_message(message2, pair_config)
        assert result is None  # 媒体组不完整
        
        # 检查缓存
        cached_data = self.processor.media_group_cache["group_123"]
        assert len(cached_data['messages']) == 2
        assert message1 in cached_data['messages']
        assert message2 in cached_data['messages']

    def test_get_complete_media_group(self):
        """测试获取完整媒体组"""
        messages = [Mock(), Mock()]
        config = {'test': 'config'}
        
        self.processor.media_group_cache["group_123"] = {
            'messages': messages,
            'timestamp': 1234567890,
            'config': config
        }
        
        result = self.processor._get_complete_media_group("group_123")
        assert result is not None
        assert result[0] == messages
        assert result[1] == config
        
        # 检查缓存已清理
        assert "group_123" not in self.processor.media_group_cache

    def test_get_complete_media_group_not_found(self):
        """测试获取不存在的媒体组"""
        result = self.processor._get_complete_media_group("nonexistent_group")
        assert result is None

    def test_is_media_group_complete(self):
        """测试媒体组完整性检查"""
        # 当前实现总是返回True，这里测试接口
        result = self.processor._is_media_group_complete("group_123")
        assert result is True

    def test_process_media_group_message_complete_group(self, monkeypatch):
        """测试处理完整媒体组"""
        # 模拟媒体组完整性检查返回True
        monkeypatch.setattr(self.processor, '_is_media_group_complete', lambda x: True)
        message = Mock()
        message.media_group_id = "group_123"
        pair_config = {'test': 'config'}
        # 先添加一条消息
        self.processor.media_group_cache["group_123"] = {
            'messages': [Mock(), Mock(), message],
            'timestamp': 1234567890,
            'config': pair_config
        }
        result = self.processor.process_media_group_message(message, pair_config)
        assert result is not None
        assert result[0][-1] == message
        assert result[1] == pair_config

    def test_media_group_cache_cleanup(self):
        """测试媒体组缓存清理"""
        # 添加一些测试数据
        self.processor.media_group_cache["group_1"] = {
            'messages': [Mock()],
            'timestamp': 1234567890,
            'config': {'test': 'config1'}
        }
        
        self.processor.media_group_cache["group_2"] = {
            'messages': [Mock()],
            'timestamp': 1234567890,
            'config': {'test': 'config2'}
        }
        
        # 获取完整媒体组，应该清理缓存
        result = self.processor._get_complete_media_group("group_1")
        assert result is not None
        assert "group_1" not in self.processor.media_group_cache
        assert "group_2" in self.processor.media_group_cache  # 其他组不受影响 