"""
插件管理器

负责插件的加载、卸载和管理，提供统一的插件接口。
"""

import asyncio
import importlib
import inspect
from pathlib import Path
from typing import Any, Dict, List, Optional, Type
from loguru import logger

from abstractions.base_handler import BaseHandler


class PluginManager:
    """
    插件管理器，负责管理所有插件的生命周期。
    
    提供插件的加载、卸载、启用、禁用等功能。
    """
    
    def __init__(self, client, config: Dict[str, Any]):
        """
        初始化插件管理器。
        
        Args:
            client: Telegram客户端实例
            config: 应用配置
        """
        self.client = client
        self.config = config
        self.plugins: Dict[str, BaseHandler] = {}
        self.plugin_configs: Dict[str, Dict[str, Any]] = {}
        self.event_bus = None  # 将在set_event_bus中设置
        self._logger = logger.bind(name="PluginManager")
    
    def set_event_bus(self, event_bus) -> None:
        """
        设置事件总线。
        
        Args:
            event_bus: 事件总线实例
        """
        self.event_bus = event_bus
        self._logger.debug("事件总线已设置")
    
    def load_plugins(self, plugins_dir: str = "plugins") -> None:
        """
        加载所有插件。
        
        Args:
            plugins_dir: 插件目录路径
        """
        plugins_path = Path(plugins_dir)
        if not plugins_path.exists():
            self._logger.warning(f"插件目录不存在: {plugins_dir}")
            return
        
        # 遍历插件目录
        for plugin_dir in plugins_path.iterdir():
            if plugin_dir.is_dir() and not plugin_dir.name.startswith('_'):
                self._load_plugin_from_directory(plugin_dir)
    
    def _load_plugin_from_directory(self, plugin_dir: Path) -> None:
        """
        从目录加载插件。
        
        Args:
            plugin_dir: 插件目录路径
        """
        plugin_name = plugin_dir.name
        
        # 查找插件主文件
        plugin_files = [
            plugin_dir / "__init__.py",
            plugin_dir / f"{plugin_name}.py",
            plugin_dir / "plugin.py"
        ]
        
        plugin_file = None
        for file in plugin_files:
            if file.exists():
                plugin_file = file
                break
        
        if not plugin_file:
            self._logger.warning(f"插件目录中没有找到主文件: {plugin_dir}")
            return
        
        try:
            # 导入插件模块
            module_name = f"plugins.{plugin_name}"
            if plugin_file.name == "__init__.py":
                module_name = f"plugins.{plugin_name}"
            elif plugin_file.name == f"{plugin_name}.py":
                module_name = f"plugins.{plugin_name}.{plugin_name}"
            else:
                module_name = f"plugins.{plugin_name}.plugin"
            
            module = importlib.import_module(module_name)
            
            # 查找插件类
            plugin_class = self._find_plugin_class(module)
            if not plugin_class:
                self._logger.warning(f"插件模块中没有找到插件类: {module_name}")
                return
            
            # 创建插件实例
            plugin_config = self.config.get(plugin_name.upper(), {})
            plugin_instance = plugin_class(self.client, plugin_config)
            
            # 设置事件总线
            if hasattr(plugin_instance, 'set_event_bus'):
                plugin_instance.set_event_bus(self.event_bus)
            
            # 注册插件
            self.plugins[plugin_name] = plugin_instance
            self.plugin_configs[plugin_name] = plugin_config
            
            self._logger.info(f"插件加载成功: {plugin_name}")
            
        except Exception as e:
            self._logger.error(f"加载插件失败: {plugin_name}, 错误: {e}")
    
    def _find_plugin_class(self, module) -> Optional[Type[BaseHandler]]:
        """
        在模块中查找插件类。
        
        Args:
            module: 模块对象
            
        Returns:
            Optional[Type[BaseHandler]]: 插件类，如果没找到则返回None
        """
        for name, obj in inspect.getmembers(module):
            if (inspect.isclass(obj) and 
                issubclass(obj, BaseHandler) and 
                obj != BaseHandler):
                return obj
        return None
    
    def get_plugin(self, plugin_name: str) -> Optional[BaseHandler]:
        """
        获取插件实例。
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            Optional[BaseHandler]: 插件实例，如果不存在则返回None
        """
        return self.plugins.get(plugin_name)
    
    def get_all_plugins(self) -> Dict[str, BaseHandler]:
        """
        获取所有插件实例。
        
        Returns:
            Dict[str, BaseHandler]: 插件名称到插件实例的映射
        """
        return self.plugins.copy()
    
    def unload_plugin(self, plugin_name: str) -> bool:
        """
        卸载插件。
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            bool: 是否成功卸载
        """
        if plugin_name not in self.plugins:
            self._logger.warning(f"插件不存在: {plugin_name}")
            return False
        
        try:
            plugin = self.plugins[plugin_name]
            
            # 调用插件的清理方法
            if hasattr(plugin, 'cleanup'):
                if asyncio.iscoroutinefunction(plugin.cleanup):
                    asyncio.create_task(plugin.cleanup())
                else:
                    plugin.cleanup()
            
            # 移除插件
            del self.plugins[plugin_name]
            if plugin_name in self.plugin_configs:
                del self.plugin_configs[plugin_name]
            
            self._logger.info(f"插件卸载成功: {plugin_name}")
            return True
            
        except Exception as e:
            self._logger.error(f"卸载插件失败: {plugin_name}, 错误: {e}")
            return False
    
    def reload_plugin(self, plugin_name: str) -> bool:
        """
        重新加载插件。
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            bool: 是否成功重新加载
        """
        # 先卸载插件
        if not self.unload_plugin(plugin_name):
            return False
        
        # 重新加载插件
        try:
            # 这里需要重新导入模块
            # 由于Python的模块缓存机制，我们需要手动清理
            module_name = f"plugins.{plugin_name}"
            if module_name in sys.modules:
                del sys.modules[module_name]
            
            # 重新加载
            self._load_plugin_from_directory(Path("plugins") / plugin_name)
            return plugin_name in self.plugins
            
        except Exception as e:
            self._logger.error(f"重新加载插件失败: {plugin_name}, 错误: {e}")
            return False
    
    def enable_plugin(self, plugin_name: str) -> bool:
        """
        启用插件。
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            bool: 是否成功启用
        """
        plugin = self.get_plugin(plugin_name)
        if not plugin:
            self._logger.warning(f"插件不存在: {plugin_name}")
            return False
        
        try:
            if hasattr(plugin, 'enable'):
                if asyncio.iscoroutinefunction(plugin.enable):
                    asyncio.create_task(plugin.enable())
                else:
                    plugin.enable()
            
            self._logger.info(f"插件启用成功: {plugin_name}")
            return True
            
        except Exception as e:
            self._logger.error(f"启用插件失败: {plugin_name}, 错误: {e}")
            return False
    
    def disable_plugin(self, plugin_name: str) -> bool:
        """
        禁用插件。
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            bool: 是否成功禁用
        """
        plugin = self.get_plugin(plugin_name)
        if not plugin:
            self._logger.warning(f"插件不存在: {plugin_name}")
            return False
        
        try:
            if hasattr(plugin, 'disable'):
                if asyncio.iscoroutinefunction(plugin.disable):
                    asyncio.create_task(plugin.disable())
                else:
                    plugin.disable()
            
            self._logger.info(f"插件禁用成功: {plugin_name}")
            return True
            
        except Exception as e:
            self._logger.error(f"禁用插件失败: {plugin_name}, 错误: {e}")
            return False
    
    def get_plugin_status(self, plugin_name: str) -> Dict[str, Any]:
        """
        获取插件状态。
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            Dict[str, Any]: 插件状态信息
        """
        plugin = self.get_plugin(plugin_name)
        if not plugin:
            return {"exists": False}
        
        status = {
            "exists": True,
            "name": plugin_name,
            "enabled": getattr(plugin, 'enabled', True),
            "config": self.plugin_configs.get(plugin_name, {})
        }
        
        # 获取插件特定的状态信息
        if hasattr(plugin, 'get_status'):
            try:
                plugin_status = plugin.get_status()
                status.update(plugin_status)
            except Exception as e:
                self._logger.error(f"获取插件状态失败: {plugin_name}, 错误: {e}")
        
        return status
    
    def get_all_plugin_status(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有插件状态。
        
        Returns:
            Dict[str, Dict[str, Any]]: 所有插件的状态信息
        """
        status = {}
        for plugin_name in self.plugins:
            status[plugin_name] = self.get_plugin_status(plugin_name)
        return status
    
    async def cleanup(self) -> None:
        """清理所有插件。"""
        for plugin_name in list(self.plugins.keys()):
            await self.unload_plugin(plugin_name)
        
        self._logger.info("所有插件已清理") 