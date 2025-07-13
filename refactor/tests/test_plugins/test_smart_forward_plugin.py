"""
SmartForwardPlugin 单元测试
"""
import pytest
from unittest.mock import Mock, AsyncMock
from plugins.forward.smart_forward_plugin import SmartForwardPlugin

class TestSmartForwardPlugin:
    def setup_method(self):
        self.mock_client = Mock()
        self.mock_config = {'dummy': 'value'}
        self.plugin = SmartForwardPlugin(self.mock_client, self.mock_config)

    def test_initialization(self):
        assert self.plugin.client == self.mock_client
        assert self.plugin.config == self.mock_config
        assert hasattr(self.plugin, 'message_processor')

    @pytest.mark.asyncio
    async def test_forward_message_implementation(self):
        # 模拟依赖
        self.plugin._get_target_channels = AsyncMock(return_value=['target1'])
        self.plugin.channel_resolver = Mock()
        self.plugin.channel_resolver.check_forward_permission = AsyncMock(return_value=True)
        self.plugin._forward_directly = AsyncMock()
        self.plugin.restricted_handler = Mock()
        self.plugin.restricted_handler.handle_restricted_forward = AsyncMock()
        # 构造消息
        message = Mock()
        message.chat.id = 123
        pair_config = {}
        processed_text = 'text'
        # 测试允许转发
        await self.plugin._forward_message_implementation(message, pair_config, processed_text)
        self.plugin._forward_directly.assert_awaited()
        # 测试禁止转发
        self.plugin.channel_resolver.check_forward_permission = AsyncMock(return_value=False)
        await self.plugin._forward_message_implementation(message, pair_config, processed_text)
        self.plugin.restricted_handler.handle_restricted_forward.assert_awaited() 