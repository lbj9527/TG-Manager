"""
转发插件基类

定义转发插件的通用接口和基础结构。
"""
from typing import Any, Dict

class BaseForwardPlugin:
    """转发插件基类"""
    def __init__(self, client: Any, config: Dict[str, Any]):
        self.client = client
        self.config = config
        self.channel_resolver = None  # 由主程序注入
        self.emit = None  # 事件发射器，由主程序注入
        self.restricted_handler = None  # 禁止转发处理器，由主程序注入

    async def _get_target_channels(self, pair_config: Dict[str, Any]):
        """
        获取目标频道列表（需子类实现具体逻辑）
        """
        raise NotImplementedError

    async def _forward_directly(self, message, target_channels, pair_config, processed_text):
        """
        直接转发逻辑（需子类实现具体逻辑）
        """
        raise NotImplementedError 