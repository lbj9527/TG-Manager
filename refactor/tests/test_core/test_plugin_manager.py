"""
插件管理器测试

测试插件管理器的核心功能。
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

from core.plugin_manager import PluginManager
from core.event_bus import EventBus


class TestPluginManager:
    """插件管理器测试"""
    
    @pytest.fixture
    def mock_client(self):
        """模拟客户端"""
        client = Mock()
        client.get_me = AsyncMock(return_value=Mock(id=123456, first_name="Test User"))
        return client
    
    @pytest.fixture
    def mock_config(self):
        """模拟配置"""
        return {
            'plugins': {
                'forward': {
                    'enabled': True,
                    'config': {'test': 'value'}
                },
                'monitor': {
                    'enabled': True,
                    'config': {'test': 'value'}
                }
            }
        }
    
    @pytest.fixture
    def event_bus(self):
        """事件总线"""
        return EventBus()
    
    @pytest.fixture
    def plugin_manager(self, mock_client, mock_config, event_bus):
        """插件管理器实例"""
        manager = PluginManager(mock_client, mock_config)
        manager.set_event_bus(event_bus)
        return manager
    
    def test_initialization(self, plugin_manager, mock_client, mock_config):
        """测试初始化"""
        assert plugin_manager.client == mock_client
        assert plugin_manager.config == mock_config
        assert plugin_manager.plugins == {}
        assert plugin_manager.event_bus is not None
    
    def test_set_event_bus(self, plugin_manager, event_bus):
        """测试设置事件总线"""
        new_event_bus = EventBus()
        plugin_manager.set_event_bus(new_event_bus)
        assert plugin_manager.event_bus == new_event_bus
    
    @pytest.mark.asyncio
    async def test_load_plugins_success(self, plugin_manager):
        """测试成功加载插件"""
        # 模拟插件类
        mock_plugin_class = Mock()
        mock_plugin_instance = Mock()
        mock_plugin_class.return_value = mock_plugin_instance
        
        with patch('core.plugin_manager.importlib.import_module') as mock_import:
            mock_module = Mock()
            mock_module.TestPlugin = mock_plugin_class
            mock_import.return_value = mock_module
            
            # 模拟插件配置
            plugin_config = {
                'plugins': {
                    'test_plugin': {
                        'enabled': True,
                        'class': 'test_module.TestPlugin',
                        'config': {'test': 'value'}
                    }
                }
            }
            plugin_manager.config = plugin_config
            
            # 加载插件
            await plugin_manager.load_plugins()
            
            # 验证插件被加载
            assert 'test_plugin' in plugin_manager.plugins
            assert plugin_manager.plugins['test_plugin'] == mock_plugin_instance
    
    @pytest.mark.asyncio
    async def test_load_plugins_disabled(self, plugin_manager):
        """测试加载禁用的插件"""
        # 模拟插件配置（禁用状态）
        plugin_config = {
            'plugins': {
                'test_plugin': {
                    'enabled': False,
                    'class': 'test_module.TestPlugin',
                    'config': {'test': 'value'}
                }
            }
        }
        plugin_manager.config = plugin_config
        
        # 加载插件
        await plugin_manager.load_plugins()
        
        # 验证插件未被加载
        assert 'test_plugin' not in plugin_manager.plugins
    
    @pytest.mark.asyncio
    async def test_load_plugins_import_error(self, plugin_manager):
        """测试插件导入错误"""
        with patch('core.plugin_manager.importlib.import_module') as mock_import:
            mock_import.side_effect = ImportError("Module not found")
            
            # 模拟插件配置
            plugin_config = {
                'plugins': {
                    'test_plugin': {
                        'enabled': True,
                        'class': 'test_module.TestPlugin',
                        'config': {'test': 'value'}
                    }
                }
            }
            plugin_manager.config = plugin_config
            
            # 加载插件（应该处理错误）
            await plugin_manager.load_plugins()
            
            # 验证插件未被加载
            assert 'test_plugin' not in plugin_manager.plugins
    
    @pytest.mark.asyncio
    async def test_load_plugins_instantiation_error(self, plugin_manager):
        """测试插件实例化错误"""
        # 模拟插件类抛出异常
        mock_plugin_class = Mock()
        mock_plugin_class.side_effect = Exception("Instantiation failed")
        
        with patch('core.plugin_manager.importlib.import_module') as mock_import:
            mock_module = Mock()
            mock_module.TestPlugin = mock_plugin_class
            mock_import.return_value = mock_module
            
            # 模拟插件配置
            plugin_config = {
                'plugins': {
                    'test_plugin': {
                        'enabled': True,
                        'class': 'test_module.TestPlugin',
                        'config': {'test': 'value'}
                    }
                }
            }
            plugin_manager.config = plugin_config
            
            # 加载插件（应该处理错误）
            await plugin_manager.load_plugins()
            
            # 验证插件未被加载
            assert 'test_plugin' not in plugin_manager.plugins
    
    def test_get_plugin_existing(self, plugin_manager):
        """测试获取存在的插件"""
        mock_plugin = Mock()
        plugin_manager.plugins['test_plugin'] = mock_plugin
        
        result = plugin_manager.get_plugin('test_plugin')
        assert result == mock_plugin
    
    def test_get_plugin_nonexistent(self, plugin_manager):
        """测试获取不存在的插件"""
        result = plugin_manager.get_plugin('nonexistent_plugin')
        assert result is None
    
    @pytest.mark.asyncio
    async def test_unload_plugin_existing(self, plugin_manager):
        """测试卸载存在的插件"""
        mock_plugin = Mock()
        mock_plugin.cleanup = AsyncMock()
        plugin_manager.plugins['test_plugin'] = mock_plugin
        
        # 卸载插件
        await plugin_manager.unload_plugin('test_plugin')
        
        # 验证插件被卸载
        assert 'test_plugin' not in plugin_manager.plugins
        mock_plugin.cleanup.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_unload_plugin_nonexistent(self, plugin_manager):
        """测试卸载不存在的插件"""
        # 卸载不存在的插件（应该不报错）
        await plugin_manager.unload_plugin('nonexistent_plugin')
        
        # 验证插件列表不变
        assert plugin_manager.plugins == {}
    
    @pytest.mark.asyncio
    async def test_unload_all_plugins(self, plugin_manager):
        """测试卸载所有插件"""
        # 添加多个插件
        mock_plugin1 = Mock()
        mock_plugin1.cleanup = AsyncMock()
        mock_plugin2 = Mock()
        mock_plugin2.cleanup = AsyncMock()
        
        plugin_manager.plugins['plugin1'] = mock_plugin1
        plugin_manager.plugins['plugin2'] = mock_plugin2
        
        # 卸载所有插件
        await plugin_manager.unload_all_plugins()
        
        # 验证所有插件被卸载
        assert plugin_manager.plugins == {}
        mock_plugin1.cleanup.assert_called_once()
        mock_plugin2.cleanup.assert_called_once()
    
    def test_get_loaded_plugins(self, plugin_manager):
        """测试获取已加载的插件列表"""
        # 添加插件
        plugin_manager.plugins['plugin1'] = Mock()
        plugin_manager.plugins['plugin2'] = Mock()
        
        # 获取插件列表
        plugins = plugin_manager.get_loaded_plugins()
        
        # 验证返回的插件列表
        assert 'plugin1' in plugins
        assert 'plugin2' in plugins
        assert len(plugins) == 2
    
    def test_is_plugin_loaded(self, plugin_manager):
        """测试检查插件是否已加载"""
        # 添加插件
        plugin_manager.plugins['test_plugin'] = Mock()
        
        # 检查已加载的插件
        assert plugin_manager.is_plugin_loaded('test_plugin') is True
        
        # 检查未加载的插件
        assert plugin_manager.is_plugin_loaded('nonexistent_plugin') is False
    
    @pytest.mark.asyncio
    async def test_reload_plugin(self, plugin_manager):
        """测试重新加载插件"""
        # 先加载一个插件
        mock_plugin = Mock()
        mock_plugin.cleanup = AsyncMock()
        plugin_manager.plugins['test_plugin'] = mock_plugin
        
        # 模拟重新加载
        new_mock_plugin = Mock()
        mock_plugin_class = Mock()
        mock_plugin_class.return_value = new_mock_plugin
        
        with patch('core.plugin_manager.importlib.import_module') as mock_import:
            mock_module = Mock()
            mock_module.TestPlugin = mock_plugin_class
            mock_import.return_value = mock_module
            
            # 模拟插件配置
            plugin_config = {
                'plugins': {
                    'test_plugin': {
                        'enabled': True,
                        'class': 'test_module.TestPlugin',
                        'config': {'test': 'value'}
                    }
                }
            }
            plugin_manager.config = plugin_config
            
            # 重新加载插件
            await plugin_manager.reload_plugin('test_plugin')
            
            # 验证旧插件被清理，新插件被加载
            mock_plugin.cleanup.assert_called_once()
            assert plugin_manager.plugins['test_plugin'] == new_mock_plugin
    
    @pytest.mark.asyncio
    async def test_cleanup(self, plugin_manager):
        """测试清理资源"""
        # 添加插件
        mock_plugin = Mock()
        mock_plugin.cleanup = AsyncMock()
        plugin_manager.plugins['test_plugin'] = mock_plugin
        
        # 清理资源
        await plugin_manager.cleanup()
        
        # 验证所有插件被清理
        mock_plugin.cleanup.assert_called_once()
        assert plugin_manager.plugins == {}
    
    def test_get_plugin_status(self, plugin_manager):
        """测试获取插件状态"""
        # 添加插件
        mock_plugin = Mock()
        mock_plugin.get_status = Mock(return_value={'status': 'running'})
        plugin_manager.plugins['test_plugin'] = mock_plugin
        
        # 获取插件状态
        status = plugin_manager.get_plugin_status('test_plugin')
        
        # 验证状态
        assert status == {'status': 'running'}
        mock_plugin.get_status.assert_called_once()
    
    def test_get_plugin_status_nonexistent(self, plugin_manager):
        """测试获取不存在插件的状态"""
        status = plugin_manager.get_plugin_status('nonexistent_plugin')
        assert status is None
    
    def test_get_all_plugin_statuses(self, plugin_manager):
        """测试获取所有插件状态"""
        # 添加多个插件
        mock_plugin1 = Mock()
        mock_plugin1.get_status = Mock(return_value={'status': 'running'})
        mock_plugin2 = Mock()
        mock_plugin2.get_status = Mock(return_value={'status': 'stopped'})
        
        plugin_manager.plugins['plugin1'] = mock_plugin1
        plugin_manager.plugins['plugin2'] = mock_plugin2
        
        # 获取所有插件状态
        statuses = plugin_manager.get_all_plugin_statuses()
        
        # 验证状态
        assert 'plugin1' in statuses
        assert 'plugin2' in statuses
        assert statuses['plugin1'] == {'status': 'running'}
        assert statuses['plugin2'] == {'status': 'stopped'} 