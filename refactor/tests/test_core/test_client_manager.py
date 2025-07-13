"""
ClientManager 单元测试
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path

from core.client_manager import ClientManager


class TestClientManager:
    """ClientManager 测试类"""
    
    def setup_method(self):
        """测试前准备"""
        self.config = {
            'session_name': 'test_session',
            'api_id': '12345',
            'api_hash': 'test_hash',
            'session_path': 'test_sessions'
        }
        self.client_manager = ClientManager(self.config)
    
    def test_initialization(self):
        """测试初始化"""
        assert self.client_manager.session_name == 'test_session'
        assert self.client_manager.api_id == '12345'
        assert self.client_manager.api_hash == 'test_hash'
        assert self.client_manager.session_path == Path('test_sessions')
        assert self.client_manager.auto_reconnect is True
        assert self.client_manager.max_reconnect_attempts == 5
    
    def test_set_event_bus(self):
        """测试设置事件总线"""
        mock_event_bus = Mock()
        self.client_manager.set_event_bus(mock_event_bus)
        
        assert hasattr(self.client_manager, 'event_bus')
        assert self.client_manager.event_bus == mock_event_bus
        assert self.client_manager.flood_wait_handler.event_bus == mock_event_bus
        assert self.client_manager.error_handler.event_bus == mock_event_bus
    
    @pytest.mark.asyncio
    async def test_initialize_with_existing_session(self):
        """测试初始化现有会话"""
        # 模拟会话文件存在
        with patch('pathlib.Path.exists', return_value=True):
            with patch.object(self.client_manager, '_restore_session', return_value=True):
                result = await self.client_manager.initialize()
                assert result is True
    
    @pytest.mark.asyncio
    async def test_initialize_without_session(self):
        """测试初始化无会话文件"""
        # 模拟会话文件不存在
        with patch('pathlib.Path.exists', return_value=False):
            with patch.object(self.client_manager, '_perform_first_login', return_value=True):
                result = await self.client_manager.initialize()
                assert result is True
    
    @pytest.mark.asyncio
    async def test_initialize_failure(self):
        """测试初始化失败"""
        with patch('pathlib.Path.exists', side_effect=Exception("Test error")):
            result = await self.client_manager.initialize()
            assert result is False
    
    @pytest.mark.asyncio
    async def test_restore_session_success(self):
        """测试恢复会话成功"""
        mock_user = Mock()
        mock_user.first_name = "Test"
        mock_user.username = "testuser"
        with patch.object(self.client_manager.client, 'start', new_callable=AsyncMock):
            with patch.object(self.client_manager.client, 'get_me', new_callable=AsyncMock, return_value=mock_user):
                with patch.object(self.client_manager, '_start_connection_monitor', new_callable=AsyncMock):
                    result = await self.client_manager._restore_session()
                    assert result is True
                    assert self.client_manager.is_authenticated is True
                    assert self.client_manager.is_connected is True
    
    @pytest.mark.asyncio
    async def test_restore_session_failure(self):
        """测试恢复会话失败"""
        with patch.object(self.client_manager.client, 'start', side_effect=Exception("Test error")):
            result = await self.client_manager._restore_session()
            assert result is False
    
    @pytest.mark.asyncio
    async def test_perform_first_login_success(self):
        """测试首次登录成功"""
        mock_user = Mock()
        mock_user.first_name = "Test"
        mock_user.username = "testuser"
        with patch.object(self.client_manager.client, 'start', new_callable=AsyncMock):
            with patch.object(self.client_manager.client, 'get_me', new_callable=AsyncMock, return_value=mock_user):
                with patch.object(self.client_manager, '_start_connection_monitor', new_callable=AsyncMock):
                    result = await self.client_manager._perform_first_login()
                    assert result is True
                    assert self.client_manager.is_authenticated is True
                    assert self.client_manager.is_connected is True
    
    @pytest.mark.asyncio
    async def test_perform_first_login_failure(self):
        """测试首次登录失败"""
        with patch.object(self.client_manager.client, 'start', side_effect=Exception("Test error")):
            result = await self.client_manager._perform_first_login()
            assert result is False
    
    @pytest.mark.asyncio
    async def test_handle_connection_loss(self):
        """测试处理连接丢失"""
        mock_event_bus = Mock()
        self.client_manager.set_event_bus(mock_event_bus)
        
        with patch.object(self.client_manager, '_attempt_reconnect'):
            await self.client_manager._handle_connection_loss()
            
            assert self.client_manager.is_connected is False
            mock_event_bus.emit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_attempt_reconnect_success(self):
        """测试重连成功"""
        with patch.object(self.client_manager, '_restore_session', return_value=True):
            await self.client_manager._attempt_reconnect()
            
            assert self.client_manager.reconnect_attempts == 0
    
    @pytest.mark.asyncio
    async def test_attempt_reconnect_failure(self):
        """测试重连失败"""
        with patch.object(self.client_manager, '_restore_session', return_value=False):
            with patch.object(self.client_manager, 'max_reconnect_attempts', 1):
                await self.client_manager._attempt_reconnect()
                
                assert self.client_manager.reconnect_attempts == 1
    
    @pytest.mark.asyncio
    async def test_check_connection_status_now_success(self):
        """测试立即检查连接状态成功"""
        with patch.object(self.client_manager.client, 'get_me', new_callable=AsyncMock):
            result = await self.client_manager.check_connection_status_now()
            assert result is True
    
    @pytest.mark.asyncio
    async def test_check_connection_status_now_failure(self):
        """测试立即检查连接状态失败"""
        with patch.object(self.client_manager.client, 'get_me', side_effect=Exception("Test error")):
            with patch.object(self.client_manager, '_handle_connection_loss'):
                result = await self.client_manager.check_connection_status_now()
                assert result is False
    
    @pytest.mark.asyncio
    async def test_stop(self):
        """测试停止客户端管理器"""
        mock_task = Mock()
        self.client_manager.connection_monitor_task = mock_task
        
        with patch.object(self.client_manager.client, 'stop'):
            await self.client_manager.stop()
            
            assert self.client_manager.should_stop is True
            assert self.client_manager.is_running is False
            assert self.client_manager.is_connected is False
            assert self.client_manager.is_authenticated is False
    
    def test_get_client(self):
        """测试获取客户端"""
        mock_client = Mock()
        self.client_manager.client = mock_client
        
        result = self.client_manager.get_client()
        assert result == mock_client
    
    def test_get_user(self):
        """测试获取用户信息"""
        mock_user = Mock()
        self.client_manager.user = mock_user
        
        result = self.client_manager.get_user()
        assert result == mock_user
    
    def test_is_ready(self):
        """测试检查客户端是否准备就绪"""
        # 测试未准备就绪
        assert self.client_manager.is_ready() is False
        
        # 测试准备就绪
        self.client_manager.client = Mock()
        self.client_manager.is_connected = True
        self.client_manager.is_authenticated = True
        
        assert self.client_manager.is_ready() is True
    
    def test_get_status(self):
        """测试获取状态"""
        mock_user = Mock()
        mock_user.id = 123
        mock_user.username = "testuser"
        mock_user.first_name = "Test"
        self.client_manager.user = mock_user
        
        status = self.client_manager.get_status()
        
        assert status['is_connected'] is False
        assert status['is_authenticated'] is False
        assert status['auto_reconnect'] is True
        assert status['reconnect_attempts'] == 0
        assert status['user']['id'] == 123
        assert status['user']['username'] == "testuser"
        assert status['user']['first_name'] == "Test"
    
    @pytest.mark.asyncio
    async def test_repair_session_database_success(self):
        """测试修复会话数据库成功"""
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.unlink'):
                result = await self.client_manager.repair_session_database()
                assert result is True
    
    @pytest.mark.asyncio
    async def test_repair_session_database_no_file(self):
        """测试修复会话数据库 - 文件不存在"""
        with patch('pathlib.Path.exists', return_value=False):
            result = await self.client_manager.repair_session_database()
            assert result is True
    
    @pytest.mark.asyncio
    async def test_repair_session_database_failure(self):
        """测试修复会话数据库失败"""
        with patch('pathlib.Path.exists', side_effect=Exception("Test error")):
            result = await self.client_manager.repair_session_database()
            assert result is False
    
    def test_set_auto_reconnect(self):
        """测试设置自动重连"""
        self.client_manager.set_auto_reconnect(False)
        assert self.client_manager.auto_reconnect is False
        
        self.client_manager.set_auto_reconnect(True)
        assert self.client_manager.auto_reconnect is True
    
    def test_set_max_reconnect_attempts(self):
        """测试设置最大重连次数"""
        self.client_manager.set_max_reconnect_attempts(10)
        assert self.client_manager.max_reconnect_attempts == 10
    
    def test_set_reconnect_delay(self):
        """测试设置重连延迟"""
        self.client_manager.set_reconnect_delay(2.0)
        assert self.client_manager.reconnect_delay == 2.0 