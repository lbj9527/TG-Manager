"""
核心模块

提供应用的核心功能，包括客户端管理、插件管理、事件总线等。
"""

from .client_manager import ClientManager
from .plugin_manager import PluginManager
from .event_bus import EventBus
from .app_core import AppCore

__all__ = [
    'ClientManager',
    'PluginManager',
    'EventBus',
    'AppCore'
] 