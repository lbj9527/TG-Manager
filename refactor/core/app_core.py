"""
应用核心模块

协调客户端管理、插件管理、事件总线等核心组件的工作。
"""

import asyncio
from typing import Any, Dict, Optional
from loguru import logger

from .client_manager import ClientManager
from .plugin_manager import PluginManager
from .event_bus import EventBus
from config.config_manager import ConfigManager


class AppCore:
    """应用核心，协调各个组件的工作"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.is_running = False
        self.should_stop = False
        
        # 初始化核心组件
        self.event_bus = EventBus()
        self.config_manager = ConfigManager(config)
        self.client_manager = ClientManager(config)
        self.plugin_manager = PluginManager(self.client_manager.get_client(), config)
        
        # 设置事件总线
        self.client_manager.set_event_bus(self.event_bus)
        self.plugin_manager.set_event_bus(self.event_bus)
        
        # 注册事件处理器
        self._register_event_handlers()
    
    def _register_event_handlers(self) -> None:
        """注册事件处理器"""
        # 客户端相关事件
        self.event_bus.on("client_connected", self._on_client_connected)
        self.event_bus.on("client_disconnected", self._on_client_disconnected)
        self.event_bus.on("client_logged_in", self._on_client_logged_in)
        self.event_bus.on("client_reconnected", self._on_client_reconnected)
        self.event_bus.on("client_reconnect_failed", self._on_client_reconnect_failed)
        
        # 插件相关事件
        self.event_bus.on("plugin_loaded", self._on_plugin_loaded)
        self.event_bus.on("plugin_unloaded", self._on_plugin_unloaded)
        self.event_bus.on("plugin_error", self._on_plugin_error)
        
        # 错误相关事件
        self.event_bus.on("error_occurred", self._on_error_occurred)
    
    async def start(self) -> bool:
        """启动应用核心"""
        try:
            logger.info("启动应用核心...")
            self.is_running = True
            self.should_stop = False
            
            # 初始化配置管理器
            await self.config_manager.initialize()
            
            # 初始化客户端管理器
            if not await self.client_manager.initialize():
                logger.error("客户端管理器初始化失败")
                return False
            
            # 等待客户端准备就绪
            if not self.client_manager.is_ready():
                logger.error("客户端未准备就绪")
                return False
            
            # 更新插件管理器的客户端引用
            self.plugin_manager.client = self.client_manager.get_client()
            
            # 加载插件
            self.plugin_manager.load_plugins()
            
            logger.info("应用核心启动成功")
            return True
            
        except Exception as e:
            logger.error(f"启动应用核心失败: {e}")
            return False
    
    async def stop(self) -> None:
        """停止应用核心"""
        logger.info("停止应用核心...")
        self.should_stop = True
        self.is_running = False
        
        # 停止插件管理器
        await self.plugin_manager.cleanup()
        
        # 停止客户端管理器
        await self.client_manager.stop()
        
        # 停止配置管理器
        await self.config_manager.cleanup()
        
        logger.info("应用核心已停止")
    
    def get_status(self) -> Dict[str, Any]:
        """获取应用状态"""
        return {
            'is_running': self.is_running,
            'client_status': self.client_manager.get_status(),
            'plugin_status': self.plugin_manager.get_all_plugin_status(),
            'config_status': self.config_manager.get_status()
        }
    
    def get_client_manager(self) -> ClientManager:
        """获取客户端管理器"""
        return self.client_manager
    
    def get_plugin_manager(self) -> PluginManager:
        """获取插件管理器"""
        return self.plugin_manager
    
    def get_config_manager(self) -> ConfigManager:
        """获取配置管理器"""
        return self.config_manager
    
    def get_event_bus(self) -> EventBus:
        """获取事件总线"""
        return self.event_bus
    
    # 事件处理器方法
    def _on_client_connected(self, data: Dict[str, Any]) -> None:
        """客户端连接事件处理"""
        logger.info(f"客户端已连接: {data.get('username', 'Unknown')}")
    
    def _on_client_disconnected(self, data: Dict[str, Any]) -> None:
        """客户端断开连接事件处理"""
        logger.warning(f"客户端已断开连接: {data.get('reason', 'Unknown')}")
    
    def _on_client_logged_in(self, data: Dict[str, Any]) -> None:
        """客户端登录事件处理"""
        logger.info(f"客户端登录成功: {data.get('username', 'Unknown')}")
    
    def _on_client_reconnected(self, data: Dict[str, Any]) -> None:
        """客户端重连事件处理"""
        logger.info("客户端重连成功")
    
    def _on_client_reconnect_failed(self, data: Dict[str, Any]) -> None:
        """客户端重连失败事件处理"""
        logger.error(f"客户端重连失败，尝试次数: {data.get('attempts', 0)}")
    
    def _on_plugin_loaded(self, plugin_name: str) -> None:
        """插件加载事件处理"""
        logger.info(f"插件已加载: {plugin_name}")
    
    def _on_plugin_unloaded(self, plugin_name: str) -> None:
        """插件卸载事件处理"""
        logger.info(f"插件已卸载: {plugin_name}")
    
    def _on_plugin_error(self, plugin_name: str, error: str) -> None:
        """插件错误事件处理"""
        logger.error(f"插件 {plugin_name} 发生错误: {error}")
    
    def _on_error_occurred(self, error_message: str, error_type: str) -> None:
        """错误事件处理"""
        logger.error(f"应用错误 [{error_type}]: {error_message}")
    
    async def reload_config(self) -> bool:
        """重新加载配置"""
        try:
            logger.info("重新加载配置...")
            
            # 重新加载配置
            if await self.config_manager.reload():
                # 更新插件配置
                self.plugin_manager.update_config(self.config_manager.get_config())
                logger.info("配置重新加载成功")
                return True
            else:
                logger.error("配置重新加载失败")
                return False
                
        except Exception as e:
            logger.error(f"重新加载配置时出错: {e}")
            return False
    
    async def restart_plugins(self) -> bool:
        """重启所有插件"""
        try:
            logger.info("重启所有插件...")
            
            # 停止所有插件
            await self.plugin_manager.cleanup()
            
            # 重新加载插件
            self.plugin_manager.load_plugins()
            
            logger.info("插件重启完成")
            return True
            
        except Exception as e:
            logger.error(f"重启插件时出错: {e}")
            return False
    
    async def check_connection_status(self) -> bool:
        """检查连接状态"""
        return await self.client_manager.check_connection_status_now()
    
    async def repair_session(self) -> bool:
        """修复会话"""
        return await self.client_manager.repair_session_database() 