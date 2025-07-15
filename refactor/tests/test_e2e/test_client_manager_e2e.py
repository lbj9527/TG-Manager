"""
ClientManager 端到端测试

测试真实的Telegram登录、会话管理和自动重连功能。
"""

import asyncio
import pytest
import time
from pathlib import Path
from typing import Dict, Any

from core.client_manager import ClientManager
from test_e2e.e2e_config import E2EConfig, setup_e2e_environment


class TestClientManagerE2E:
    """ClientManager端到端测试类"""
    
    @pytest.fixture(autouse=True)
    def setup_test_environment(self):
        """设置测试环境"""
        # 设置端到端测试环境
        if not setup_e2e_environment():
            pytest.skip("端到端测试环境未正确配置")
        
        # 获取测试配置
        self.config = E2EConfig.get_test_config()
        
        # 确保测试会话目录存在
        test_session_path = Path(self.config['session_path'])
        test_session_path.mkdir(parents=True, exist_ok=True)
        
        # 清理可能存在的测试会话文件
        test_session_file = test_session_path / f"{self.config['session_name']}.session"
        if test_session_file.exists():
            test_session_file.unlink()
    
    @pytest.mark.asyncio
    async def test_complete_login_flow(self):
        """测试完整的登录流程"""
        # 创建客户端管理器
        client_manager = ClientManager(self.config)
        
        try:
            # 初始化客户端管理器
            success = await client_manager.initialize()
            assert success, "客户端管理器初始化失败"
            
            # 验证登录状态
            assert client_manager.is_authenticated, "用户未认证"
            assert client_manager.is_connected, "客户端未连接"
            assert client_manager.user is not None, "用户信息为空"
            
            # 验证用户信息
            user = client_manager.get_user()
            assert user is not None, "无法获取用户信息"
            assert user.phone_number == self.config['phone_number'], "手机号码不匹配"
            
            print(f"登录成功: {user.first_name} (@{user.username})")
            
            # 验证客户端状态
            status = client_manager.get_status()
            assert status['is_connected'], "连接状态错误"
            assert status['is_authenticated'], "认证状态错误"
            assert status['user'] is not None, "用户状态错误"
            
        finally:
            # 清理资源
            await client_manager.cleanup()
    
    @pytest.mark.asyncio
    async def test_session_restoration(self):
        """测试会话恢复功能"""
        # 第一次登录，创建会话文件
        client_manager1 = ClientManager(self.config)
        
        try:
            # 初始化并登录
            success = await client_manager1.initialize()
            assert success, "首次登录失败"
            
            # 获取用户信息
            user1 = client_manager1.get_user()
            assert user1 is not None, "无法获取用户信息"
            
            print(f"首次登录成功: {user1.first_name} (@{user1.username})")
            
        finally:
            await client_manager1.cleanup()
        
        # 第二次登录，应该恢复会话
        client_manager2 = ClientManager(self.config)
        
        try:
            # 初始化（应该恢复会话）
            success = await client_manager2.initialize()
            assert success, "会话恢复失败"
            
            # 验证用户信息一致
            user2 = client_manager2.get_user()
            assert user2 is not None, "无法获取用户信息"
            assert user2.id == user1.id, "用户ID不匹配"
            assert user2.phone_number == user1.phone_number, "手机号码不匹配"
            
            print(f"会话恢复成功: {user2.first_name} (@{user2.username})")
            
        finally:
            await client_manager2.cleanup()
    
    @pytest.mark.asyncio
    async def test_connection_monitoring(self):
        """测试连接监控功能"""
        # 创建客户端管理器
        client_manager = ClientManager(self.config)
        
        try:
            # 初始化
            success = await client_manager.initialize()
            assert success, "客户端管理器初始化失败"
            
            # 验证初始状态
            assert client_manager.is_connected, "初始连接状态错误"
            
            # 测试连接状态检查
            is_connected = await client_manager.check_connection_status_now()
            assert is_connected, "连接状态检查失败"
            
            # 等待一段时间，验证连接监控
            await asyncio.sleep(5)
            
            # 再次检查连接状态
            is_connected = await client_manager.check_connection_status_now()
            assert is_connected, "连接监控期间连接丢失"
            
            print("连接监控测试通过")
            
        finally:
            await client_manager.cleanup()
    
    @pytest.mark.asyncio
    async def test_auto_reconnect(self):
        """测试自动重连功能"""
        # 创建客户端管理器
        client_manager = ClientManager(self.config)
        
        try:
            # 初始化
            success = await client_manager.initialize()
            assert success, "客户端管理器初始化失败"
            
            # 获取初始用户信息
            initial_user = client_manager.get_user()
            assert initial_user is not None, "无法获取用户信息"
            
            # 模拟连接丢失（停止客户端）
            await client_manager.client.stop()
            client_manager.is_connected = False
            client_manager.is_authenticated = False
            
            # 等待重连
            max_wait_time = 30  # 最大等待30秒
            wait_interval = 2   # 每2秒检查一次
            waited_time = 0
            
            while waited_time < max_wait_time:
                await asyncio.sleep(wait_interval)
                waited_time += wait_interval
                
                if client_manager.is_connected and client_manager.is_authenticated:
                    break
            
            # 验证重连成功
            assert client_manager.is_connected, "自动重连失败"
            assert client_manager.is_authenticated, "重连后认证失败"
            
            # 验证用户信息一致
            reconnected_user = client_manager.get_user()
            assert reconnected_user is not None, "重连后无法获取用户信息"
            assert reconnected_user.id == initial_user.id, "重连后用户ID不匹配"
            
            print("自动重连测试通过")
            
        finally:
            await client_manager.cleanup()
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """测试错误处理"""
        # 创建错误配置
        error_config = self.config.copy()
        error_config['api_id'] = 'invalid_api_id'
        error_config['api_hash'] = 'invalid_api_hash'
        
        # 创建客户端管理器
        client_manager = ClientManager(error_config)
        
        try:
            # 尝试初始化（应该失败）
            success = await client_manager.initialize()
            assert not success, "使用无效配置应该失败"
            
            print("错误处理测试通过")
            
        finally:
            await client_manager.cleanup()
    
    @pytest.mark.asyncio
    async def test_config_validation(self):
        """测试配置验证"""
        # 测试必需配置
        required_fields = ['api_id', 'api_hash', 'phone_number']
        
        for field in required_fields:
            # 创建缺少字段的配置
            invalid_config = self.config.copy()
            invalid_config[field] = ''
            
            # 创建客户端管理器
            client_manager = ClientManager(invalid_config)
            
            try:
                # 尝试初始化（应该失败）
                success = await client_manager.initialize()
                assert not success, f"缺少{field}应该导致初始化失败"
                
            finally:
                await client_manager.cleanup()
        
        print("配置验证测试通过")
    
    @pytest.mark.asyncio
    async def test_session_management(self):
        """测试会话管理"""
        # 创建客户端管理器
        client_manager = ClientManager(self.config)
        
        try:
            # 初始化
            success = await client_manager.initialize()
            assert success, "客户端管理器初始化失败"
            
            # 测试会话数据库修复
            repair_success = await client_manager.repair_session_database()
            assert repair_success, "会话数据库修复失败"
            
            # 测试状态获取
            status = client_manager.get_status()
            assert isinstance(status, dict), "状态应该是字典类型"
            assert 'is_connected' in status, "状态缺少连接信息"
            assert 'is_authenticated' in status, "状态缺少认证信息"
            assert 'user' in status, "状态缺少用户信息"
            
            print("会话管理测试通过")
            
        finally:
            await client_manager.cleanup()
    
    @pytest.mark.asyncio
    async def test_performance(self):
        """测试性能"""
        # 创建客户端管理器
        client_manager = ClientManager(self.config)
        
        try:
            # 记录初始化开始时间
            start_time = time.time()
            
            # 初始化
            success = await client_manager.initialize()
            assert success, "客户端管理器初始化失败"
            
            # 计算初始化时间
            init_time = time.time() - start_time
            assert init_time < 30, f"初始化时间过长: {init_time:.2f}秒"
            
            # 记录连接检查开始时间
            start_time = time.time()
            
            # 检查连接状态
            is_connected = await client_manager.check_connection_status_now()
            assert is_connected, "连接状态检查失败"
            
            # 计算连接检查时间
            check_time = time.time() - start_time
            assert check_time < 5, f"连接检查时间过长: {check_time:.2f}秒"
            
            print(f"性能测试通过 - 初始化: {init_time:.2f}秒, 连接检查: {check_time:.2f}秒")
            
        finally:
            await client_manager.cleanup()


if __name__ == "__main__":
    # 直接运行测试
    asyncio.run(TestClientManagerE2E().test_complete_login_flow()) 