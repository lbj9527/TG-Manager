"""
BaseMessageProcessor 单元测试
"""
import pytest
from unittest.mock import Mock, AsyncMock
from abstractions.base_message_processor import BaseMessageProcessor

class TestBaseMessageProcessor:
    def setup_method(self):
        self.mock_client = Mock()
        self.mock_channel_resolver = Mock()
        self.mock_emit = Mock()
        self.processor = BaseMessageProcessor(
            self.mock_client, 
            self.mock_channel_resolver, 
            self.mock_emit
        )

    def test_initialization(self):
        """测试初始化"""
        assert self.processor.client == self.mock_client
        assert self.processor.channel_resolver == self.mock_channel_resolver
        assert self.processor.emit == self.mock_emit
        assert hasattr(self.processor, 'text_processor')
        assert hasattr(self.processor, 'message_filter')
        assert hasattr(self.processor, 'media_group_processor')

    @pytest.mark.asyncio
    async def test_process_message_universal_filter(self):
        """测试通用过滤"""
        message = Mock()
        message.id = 123
        message.forward_from = Mock()  # 转发消息
        
        pair_config = {'exclude_forwards': True}
        
        # 模拟通用过滤返回True
        self.processor.message_filter.apply_universal_filters = Mock(return_value=(True, "转发消息"))
        
        result = await self.processor.process_message(message, pair_config)
        assert result is False
        self.mock_emit.assert_called_once_with("message_filtered", 123, "通用过滤", "转发消息")

    @pytest.mark.asyncio
    async def test_process_message_keyword_filter(self):
        """测试关键词过滤"""
        message = Mock()
        message.id = 123
        message.forward_from = None
        
        pair_config = {'keywords': ['test']}
        
        # 模拟通用过滤通过，关键词过滤失败
        self.processor.message_filter.apply_universal_filters = Mock(return_value=(False, ""))
        self.processor.message_filter.apply_keyword_filter = Mock(return_value=False)
        
        result = await self.processor.process_message(message, pair_config)
        assert result is False
        self.mock_emit.assert_called_once_with("message_filtered", 123, "关键词过滤", "不包含关键词")

    @pytest.mark.asyncio
    async def test_process_message_media_type_filter(self):
        """测试媒体类型过滤"""
        message = Mock()
        message.id = 123
        message.forward_from = None
        
        pair_config = {'media_types': ['photo']}
        
        # 模拟前两个过滤通过，媒体类型过滤失败
        self.processor.message_filter.apply_universal_filters = Mock(return_value=(False, ""))
        self.processor.message_filter.apply_keyword_filter = Mock(return_value=True)
        self.processor.message_filter.apply_media_type_filter = Mock(return_value=False)
        
        result = await self.processor.process_message(message, pair_config)
        assert result is False
        self.mock_emit.assert_called_once_with("message_filtered", 123, "媒体类型过滤", "媒体类型不匹配")

    @pytest.mark.asyncio
    async def test_process_message_text_replacement(self):
        """测试文本替换"""
        message = Mock()
        message.id = 123
        message.forward_from = None
        message.text = "Hello A World"
        
        pair_config = {'text_filter': [{'original_text': 'A', 'target_text': 'B'}]}
        
        # 模拟所有过滤通过
        self.processor.message_filter.apply_universal_filters = Mock(return_value=(False, ""))
        self.processor.message_filter.apply_keyword_filter = Mock(return_value=True)
        self.processor.message_filter.apply_media_type_filter = Mock(return_value=True)
        
        # 模拟文本替换
        self.processor.text_processor.process_message_text = Mock(return_value=("Hello B World", True))
        
        # 模拟转发逻辑
        self.processor._forward_message = AsyncMock(return_value=True)
        
        result = await self.processor.process_message(message, pair_config)
        assert result is True
        self.mock_emit.assert_called_with("text_replacement_applied", "消息文本", "Hello A World", "Hello B World")

    @pytest.mark.asyncio
    async def test_process_message_success(self):
        """测试消息处理成功"""
        message = Mock()
        message.id = 123
        message.forward_from = None
        message.text = "Hello World"
        
        pair_config = {}
        
        # 模拟所有过滤通过
        self.processor.message_filter.apply_universal_filters = Mock(return_value=(False, ""))
        self.processor.message_filter.apply_keyword_filter = Mock(return_value=True)
        self.processor.message_filter.apply_media_type_filter = Mock(return_value=True)
        
        # 模拟无文本替换
        self.processor.text_processor.process_message_text = Mock(return_value=("Hello World", False))
        
        # 模拟转发逻辑
        self.processor._forward_message = AsyncMock(return_value=True)
        
        result = await self.processor.process_message(message, pair_config)
        assert result is True
        # 不应该发射文本替换事件
        self.mock_emit.assert_not_called()

    @pytest.mark.asyncio
    async def test_forward_message_not_implemented(self):
        """测试转发方法未实现"""
        message = Mock()
        pair_config = {}
        processed_text = "test"
        
        with pytest.raises(NotImplementedError):
            await self.processor._forward_message(message, pair_config, processed_text)

    @pytest.mark.asyncio
    async def test_process_message_no_emit(self):
        """测试无事件发射器的情况"""
        processor = BaseMessageProcessor(self.mock_client, self.mock_channel_resolver, None)
        
        message = Mock()
        message.id = 123
        message.forward_from = Mock()
        
        pair_config = {'exclude_forwards': True}
        
        # 模拟通用过滤返回True
        processor.message_filter.apply_universal_filters = Mock(return_value=(True, "转发消息"))
        
        # 不应该抛出异常
        result = await processor.process_message(message, pair_config)
        assert result is False 