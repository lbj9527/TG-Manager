"""
MessageFetcher 单元测试
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from pyrogram.types import Message

from common.message_fetcher import MessageFetcher


class TestMessageFetcher:
    """MessageFetcher 测试类"""
    
    def setup_method(self):
        """测试前准备"""
        self.mock_client = Mock()
        self.message_fetcher = MessageFetcher(self.mock_client)
    
    def test_initialization(self):
        """测试初始化"""
        assert self.message_fetcher.client == self.mock_client
        assert self.message_fetcher.cache_enabled is True
        assert self.message_fetcher.cache_size == 1000
        assert isinstance(self.message_fetcher.message_cache, dict)
    
    def test_set_event_bus(self):
        """测试设置事件总线"""
        mock_event_bus = Mock()
        self.message_fetcher.set_event_bus(mock_event_bus)
        
        assert hasattr(self.message_fetcher, 'event_bus')
        assert self.message_fetcher.event_bus == mock_event_bus
        assert self.message_fetcher.flood_wait_handler.event_bus == mock_event_bus
        assert self.message_fetcher.error_handler.event_bus == mock_event_bus
    
    @pytest.mark.asyncio
    async def test_get_messages_success(self):
        """测试获取消息成功"""
        mock_message = Mock(spec=Message)
        mock_message.id = 123
        
        with patch.object(self.message_fetcher, '_get_single_message_with_cache', return_value=mock_message):
            result = await self.message_fetcher.get_messages(12345, [123, 456])
            
            assert len(result) == 2
            assert result[0] == mock_message
            assert result[1] == mock_message
    
    @pytest.mark.asyncio
    async def test_get_messages_partial_failure(self):
        """测试获取消息部分失败"""
        mock_message = Mock(spec=Message)
        mock_message.id = 123
        
        with patch.object(self.message_fetcher, '_get_single_message_with_cache', side_effect=[mock_message, Exception("Error")]):
            result = await self.message_fetcher.get_messages(12345, [123, 456])
            
            assert len(result) == 2
            assert result[0] == mock_message
            assert result[1] is None
    
    @pytest.mark.asyncio
    async def test_get_messages_all_failure(self):
        """测试获取消息全部失败"""
        with patch.object(self.message_fetcher, '_get_single_message_with_cache', side_effect=Exception("Error")):
            result = await self.message_fetcher.get_messages(12345, [123, 456])
            
            assert len(result) == 2
            assert result[0] is None
            assert result[1] is None
    
    @pytest.mark.asyncio
    async def test_get_chat_history_success(self):
        """测试获取聊天历史成功"""
        mock_messages = [Mock(spec=Message) for _ in range(3)]
        
        async def mock_get_chat_history(*args, **kwargs):
            for msg in mock_messages:
                yield msg
        
        with patch.object(self.mock_client, 'get_chat_history', side_effect=mock_get_chat_history):
            result = await self.message_fetcher.get_chat_history(12345, limit=3)
            
            assert len(result) == 3
            assert result == mock_messages
    
    @pytest.mark.asyncio
    async def test_get_chat_history_failure(self):
        """测试获取聊天历史失败"""
        with patch.object(self.mock_client, 'get_chat_history', side_effect=Exception("Error")):
            result = await self.message_fetcher.get_chat_history(12345, limit=3)
            
            assert result == []
    
    @pytest.mark.asyncio
    async def test_get_messages_in_range_success(self):
        """测试获取消息范围成功"""
        mock_messages = []
        for i in range(5, 0, -1):  # 5, 4, 3, 2, 1
            msg = Mock(spec=Message)
            msg.id = i
            mock_messages.append(msg)
        
        async def mock_get_chat_history(*args, **kwargs):
            for msg in mock_messages:
                yield msg
        
        with patch.object(self.mock_client, 'get_chat_history', side_effect=mock_get_chat_history):
            result = await self.message_fetcher.get_messages_in_range(12345, 2, 4)
            
            assert len(result) == 3
            assert [msg.id for msg in result] == [2, 3, 4]
    
    @pytest.mark.asyncio
    async def test_get_messages_in_range_failure(self):
        """测试获取消息范围失败"""
        with patch.object(self.mock_client, 'get_chat_history', side_effect=Exception("Error")):
            result = await self.message_fetcher.get_messages_in_range(12345, 1, 10)
            
            assert result == []
    
    @pytest.mark.asyncio
    async def test_search_messages_success(self):
        """测试搜索消息成功"""
        mock_messages = [Mock(spec=Message) for _ in range(2)]
        
        async def mock_search_messages(*args, **kwargs):
            for msg in mock_messages:
                yield msg
        
        with patch.object(self.mock_client, 'search_messages', side_effect=mock_search_messages):
            result = await self.message_fetcher.search_messages(12345, "test query", limit=2)
            
            assert len(result) == 2
            assert result == mock_messages
    
    @pytest.mark.asyncio
    async def test_search_messages_failure(self):
        """测试搜索消息失败"""
        with patch.object(self.mock_client, 'search_messages', side_effect=Exception("Error")):
            result = await self.message_fetcher.search_messages(12345, "test query")
            
            assert result == []
    
    @pytest.mark.asyncio
    async def test_get_media_messages_success(self):
        """测试获取媒体消息成功"""
        mock_messages = []
        for i in range(3):
            msg = Mock(spec=Message)
            msg.media = Mock()
            msg.media.value = 'photo'
            mock_messages.append(msg)
        
        async def mock_get_chat_history(*args, **kwargs):
            for msg in mock_messages:
                yield msg
        
        with patch.object(self.mock_client, 'get_chat_history', side_effect=mock_get_chat_history):
            result = await self.message_fetcher.get_media_messages(12345, limit=3)
            
            assert len(result) == 3
    
    @pytest.mark.asyncio
    async def test_get_media_messages_with_filter(self):
        """测试获取媒体消息带过滤"""
        mock_messages = []
        for i, media_type in enumerate(['photo', 'video', 'document']):
            msg = Mock(spec=Message)
            msg.media = Mock()
            msg.media.value = media_type
            mock_messages.append(msg)
        
        async def mock_get_chat_history(*args, **kwargs):
            for msg in mock_messages:
                yield msg
        
        with patch.object(self.mock_client, 'get_chat_history', side_effect=mock_get_chat_history):
            result = await self.message_fetcher.get_media_messages(12345, limit=3, media_types=['photo'])
            
            assert len(result) == 1
            assert result[0].media.value == 'photo'
    
    @pytest.mark.asyncio
    async def test_get_message_count_success(self):
        """测试获取消息总数成功"""
        mock_message = Mock(spec=Message)
        mock_message.id = 100
        
        async def mock_get_chat_history(*args, **kwargs):
            yield mock_message
        
        with patch.object(self.mock_client, 'get_chat_history', side_effect=mock_get_chat_history):
            result = await self.message_fetcher.get_message_count(12345)
            
            assert result == 100
    
    @pytest.mark.asyncio
    async def test_get_message_count_failure(self):
        """测试获取消息总数失败"""
        with patch.object(self.mock_client, 'get_chat_history', side_effect=Exception("Error")):
            result = await self.message_fetcher.get_message_count(12345)
            
            assert result == 0
    
    @pytest.mark.asyncio
    async def test_get_single_message_with_cache_enabled(self):
        """测试获取单条消息（缓存启用）"""
        mock_message = Mock(spec=Message)
        mock_message.id = 123
        
        with patch.object(self.message_fetcher, '_get_single_message', return_value=mock_message):
            result = await self.message_fetcher._get_single_message_with_cache(12345, 123)
            
            assert result == mock_message
            assert "12345_123" in self.message_fetcher.message_cache
    
    @pytest.mark.asyncio
    async def test_get_single_message_with_cache_disabled(self):
        """测试获取单条消息（缓存禁用）"""
        mock_message = Mock(spec=Message)
        self.message_fetcher.cache_enabled = False
        
        with patch.object(self.message_fetcher, '_get_single_message', return_value=mock_message):
            result = await self.message_fetcher._get_single_message_with_cache(12345, 123)
            
            assert result == mock_message
            assert "12345_123" not in self.message_fetcher.message_cache
    
    @pytest.mark.asyncio
    async def test_get_single_message_with_cache_hit(self):
        """测试获取单条消息（缓存命中）"""
        mock_message = Mock(spec=Message)
        self.message_fetcher.message_cache["12345_123"] = mock_message
        
        result = await self.message_fetcher._get_single_message_with_cache(12345, 123)
        
        assert result == mock_message
    
    @pytest.mark.asyncio
    async def test_get_single_message_success(self):
        """测试获取单条消息成功"""
        mock_message = Mock(spec=Message)
        
        with patch.object(self.message_fetcher.flood_wait_handler, 'execute_with_flood_wait', return_value=mock_message):
            result = await self.message_fetcher._get_single_message(12345, 123)
            
            assert result == mock_message
    
    @pytest.mark.asyncio
    async def test_get_single_message_failure(self):
        """测试获取单条消息失败"""
        with patch.object(self.message_fetcher.flood_wait_handler, 'execute_with_flood_wait', side_effect=Exception("Error")):
            result = await self.message_fetcher._get_single_message(12345, 123)
            
            assert result is None
    
    def test_get_media_type_photo(self):
        """测试获取媒体类型 - 照片"""
        mock_message = Mock(spec=Message)
        mock_message.media = Mock()
        mock_message.media.value = 'photo'
        
        result = self.message_fetcher._get_media_type(mock_message)
        assert result == 'photo'
    
    def test_get_media_type_video(self):
        """测试获取媒体类型 - 视频"""
        mock_message = Mock(spec=Message)
        mock_message.media = Mock()
        mock_message.media.value = 'video'
        
        result = self.message_fetcher._get_media_type(mock_message)
        assert result == 'video'
    
    def test_get_media_type_text(self):
        """测试获取媒体类型 - 文本"""
        mock_message = Mock(spec=Message)
        mock_message.media = None
        
        result = self.message_fetcher._get_media_type(mock_message)
        assert result == 'text'
    
    def test_get_media_type_unknown(self):
        """测试获取媒体类型 - 未知"""
        mock_message = Mock(spec=Message)
        mock_message.media = Mock()
        mock_message.media.value = 'unknown_type'
        
        result = self.message_fetcher._get_media_type(mock_message)
        assert result == 'unknown'
    
    def test_add_to_cache(self):
        """测试添加到缓存"""
        mock_message = Mock(spec=Message)
        
        self.message_fetcher._add_to_cache("test_key", mock_message)
        
        assert "test_key" in self.message_fetcher.message_cache
        assert self.message_fetcher.message_cache["test_key"] == mock_message
    
    def test_add_to_cache_overflow(self):
        """测试缓存溢出"""
        self.message_fetcher.cache_size = 2
        
        # 添加3个条目，应该删除最旧的
        self.message_fetcher._add_to_cache("key1", Mock())
        self.message_fetcher._add_to_cache("key2", Mock())
        self.message_fetcher._add_to_cache("key3", Mock())
        
        assert len(self.message_fetcher.message_cache) == 2
        assert "key1" not in self.message_fetcher.message_cache
        assert "key2" in self.message_fetcher.message_cache
        assert "key3" in self.message_fetcher.message_cache
    
    def test_clear_cache(self):
        """测试清空缓存"""
        self.message_fetcher.message_cache["test_key"] = Mock()
        
        self.message_fetcher.clear_cache()
        
        assert len(self.message_fetcher.message_cache) == 0
    
    def test_set_cache_enabled(self):
        """测试设置缓存启用状态"""
        self.message_fetcher.set_cache_enabled(False)
        assert self.message_fetcher.cache_enabled is False
        
        self.message_fetcher.set_cache_enabled(True)
        assert self.message_fetcher.cache_enabled is True
    
    def test_set_cache_size(self):
        """测试设置缓存大小"""
        self.message_fetcher.set_cache_size(500)
        assert self.message_fetcher.cache_size == 500
    
    def test_get_cache_stats(self):
        """测试获取缓存统计信息"""
        self.message_fetcher.message_cache["test_key"] = Mock()
        
        stats = self.message_fetcher.get_cache_stats()
        
        assert stats['enabled'] is True
        assert stats['size'] == 1000
        assert stats['current_count'] == 1
        assert stats['hit_rate'] == 0.0 