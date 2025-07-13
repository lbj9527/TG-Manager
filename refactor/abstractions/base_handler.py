"""
基础处理器抽象类

为所有插件提供统一的接口和基础功能。
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from loguru import logger


class BaseHandler(ABC):
    """
    基础处理器抽象类，为所有插件提供统一接口。
    
    所有插件都应该继承此类并实现必要的方法。
    """
    
    def __init__(self, client, config: Dict[str, Any]):
        """
        初始化基础处理器。
        
        Args:
            client: Telegram客户端实例
            config: 插件配置
        """
        self.client = client
        self.config = config
        self.enabled = True
        self.event_bus = None
        self._logger = logger.bind(name=self.__class__.__name__)
    
    def set_event_bus(self, event_bus) -> None:
        """
        设置事件总线。
        
        Args:
            event_bus: 事件总线实例
        """
        self.event_bus = event_bus
        self._logger.debug("事件总线已设置")
    
    def emit(self, event_type: str, *args, **kwargs) -> None:
        """
        发射事件。
        
        Args:
            event_type: 事件类型
            *args: 位置参数
            **kwargs: 关键字参数
        """
        if self.event_bus:
            self.event_bus.emit(event_type, *args, **kwargs)
    
    async def emit_async(self, event_type: str, *args, **kwargs) -> None:
        """
        异步发射事件。
        
        Args:
            event_type: 事件类型
            *args: 位置参数
            **kwargs: 关键字参数
        """
        if self.event_bus:
            await self.event_bus.emit_async(event_type, *args, **kwargs)
    
    @abstractmethod
    async def start(self) -> bool:
        """
        启动处理器。
        
        Returns:
            bool: 是否成功启动
        """
        pass
    
    @abstractmethod
    async def stop(self) -> bool:
        """
        停止处理器。
        
        Returns:
            bool: 是否成功停止
        """
        pass
    
    async def enable(self) -> bool:
        """
        启用处理器。
        
        Returns:
            bool: 是否成功启用
        """
        self.enabled = True
        self._logger.info("处理器已启用")
        return True
    
    async def disable(self) -> bool:
        """
        禁用处理器。
        
        Returns:
            bool: 是否成功禁用
        """
        self.enabled = False
        self._logger.info("处理器已禁用")
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取处理器状态。
        
        Returns:
            Dict[str, Any]: 状态信息
        """
        return {
            "enabled": self.enabled,
            "config": self.config
        }
    
    async def cleanup(self) -> None:
        """
        清理处理器资源。
        
        子类可以重写此方法以执行特定的清理操作。
        """
        self._logger.debug("处理器清理完成")
    
    def validate_config(self) -> bool:
        """
        验证配置。
        
        Returns:
            bool: 配置是否有效
        """
        # 基础实现，子类可以重写
        return True
    
    def get_config_schema(self) -> Dict[str, Any]:
        """
        获取配置模式。
        
        Returns:
            Dict[str, Any]: 配置模式定义
        """
        # 基础实现，子类可以重写
        return {}
    
    def update_config(self, new_config: Dict[str, Any]) -> bool:
        """
        更新配置。
        
        Args:
            new_config: 新配置
            
        Returns:
            bool: 是否成功更新
        """
        try:
            self.config.update(new_config)
            self._logger.info("配置已更新")
            return True
        except Exception as e:
            self._logger.error(f"更新配置失败: {e}")
            return False 