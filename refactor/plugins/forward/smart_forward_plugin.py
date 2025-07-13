"""
智能转发插件

基于消息处理抽象层，实现统一的转发逻辑。
"""
from typing import Any, Dict
from abstractions.base_message_processor import BaseMessageProcessor
from plugins.forward.base_forward_plugin import BaseForwardPlugin

class SmartForwardPlugin(BaseForwardPlugin):
    """智能转发插件，使用消息处理抽象层"""
    def __init__(self, client: Any, config: Dict[str, Any]):
        super().__init__(client, config)
        self.message_processor = BaseMessageProcessor(client, self.channel_resolver, self.emit)
        # 重写消息处理器以适配转发逻辑
        self.message_processor._forward_message = self._forward_message_implementation

    async def _forward_message_implementation(self, message, pair_config, processed_text):
        """
        实现转发逻辑
        """
        # 获取目标频道
        target_channels = await self._get_target_channels(pair_config)
        # 检查源频道转发权限
        source_can_forward = await self.channel_resolver.check_forward_permission(message.chat.id)
        if source_can_forward:
            await self._forward_directly(message, target_channels, pair_config, processed_text)
        else:
            await self.restricted_handler.handle_restricted_forward(message, target_channels, pair_config, processed_text)
        return True 