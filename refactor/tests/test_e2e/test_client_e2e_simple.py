#!/usr/bin/env python3
"""
简化的客户端端到端测试

专门用于测试ClientManager的核心功能，包括登录、会话管理和自动重连。
"""

import asyncio
import os
import sys
import time
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from e2e_config import setup_e2e_environment, E2EConfig
from core.client_manager import ClientManager


def print_banner():
    """打印测试横幅"""
    print("=" * 60)
    print("🚀 TG-Manager 客户端端到端测试")
    print("=" * 60)
    print("测试真实的Telegram登录、会话管理和自动重连功能")
    print("需要配置有效的Telegram API凭据和手机号码")
    print("=" * 60)


def print_config_guide():
    """打印配置指南"""
    print("\n📋 配置指南:")
    print("1. 复制环境变量配置文件:")
    print("   cp env.e2e.example .env.e2e")
    print("\n2. 编辑 .env.e2e 文件，填写以下信息:")
    print("   - TELEGRAM_API_ID: 从 https://my.telegram.org/apps 获取")
    print("   - TELEGRAM_API_HASH: 从 https://my.telegram.org/apps 获取")
    print("   - TELEGRAM_PHONE_NUMBER: 你的手机号码（包含国家代码）")
    print("   - TWO_FA_PASSWORD: 两步验证密码（如果启用）")
    print("\n3. 如果需要代理，设置代理配置:")
    print("   - USE_PROXY=true")
    print("   - PROXY_SCHEME=socks5")
    print("   - PROXY_HOST=代理服务器地址")
    print("   - PROXY_PORT=代理服务器端口")
    print("\n4. 重新运行测试:")
    print("   python test_client_e2e_simple.py")


async def test_complete_login_flow():
    """测试完整的登录流程"""
    print("\n🧪 测试完整的登录流程")
    print("-" * 40)
    
    # 获取测试配置
    config = E2EConfig.get_test_config()
    
    # 确保测试会话目录存在
    test_session_path = Path(config['session_path'])
    test_session_path.mkdir(parents=True, exist_ok=True)
    
    # 清理可能存在的测试会话文件
    test_session_file = test_session_path / f"{config['session_name']}.session"
    if test_session_file.exists():
        test_session_file.unlink()
        print(f"已清理现有会话文件: {test_session_file}")
    
    # 创建客户端管理器
    client_manager = ClientManager(config)
    
    try:
        print("初始化客户端管理器...")
        start_time = time.time()
        
        # 初始化客户端管理器
        success = await client_manager.initialize()
        
        init_time = time.time() - start_time
        
        if success:
            print(f"✅ 客户端管理器初始化成功 - 耗时: {init_time:.2f}秒")
            
            # 验证登录状态
            if client_manager.is_authenticated:
                print("✅ 用户认证成功")
            else:
                print("❌ 用户认证失败")
                return False
            
            if client_manager.is_connected:
                print("✅ 客户端连接成功")
            else:
                print("❌ 客户端连接失败")
                return False
            
            # 验证用户信息
            user = client_manager.get_user()
            if user:
                print(f"✅ 用户信息获取成功: {user.first_name} (@{user.username})")
                print(f"   手机号码: {user.phone_number}")
                print(f"   用户ID: {user.id}")
            else:
                print("❌ 无法获取用户信息")
                return False
            
            # 验证客户端状态
            status = client_manager.get_status()
            print(f"✅ 客户端状态: {status}")
            
            return True
        else:
            print(f"❌ 客户端管理器初始化失败 - 耗时: {init_time:.2f}秒")
            return False
            
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        return False
    finally:
        # 清理资源
        print("清理资源...")
        await client_manager.cleanup()


async def test_session_restoration():
    """测试会话恢复功能"""
    print("\n🧪 测试会话恢复功能")
    print("-" * 40)
    
    # 获取测试配置
    config = E2EConfig.get_test_config()
    
    # 第一次登录，创建会话文件
    print("第一次登录，创建会话文件...")
    client_manager1 = ClientManager(config)
    
    try:
        # 初始化并登录
        success = await client_manager1.initialize()
        if not success:
            print("❌ 首次登录失败")
            return False
        
        # 获取用户信息
        user1 = client_manager1.get_user()
        if not user1:
            print("❌ 无法获取用户信息")
            return False
        
        print(f"✅ 首次登录成功: {user1.first_name} (@{user1.username})")
        
    finally:
        await client_manager1.cleanup()
    
    # 第二次登录，应该恢复会话
    print("第二次登录，应该恢复会话...")
    client_manager2 = ClientManager(config)
    
    try:
        # 初始化（应该恢复会话）
        success = await client_manager2.initialize()
        if not success:
            print("❌ 会话恢复失败")
            return False
        
        # 验证用户信息一致
        user2 = client_manager2.get_user()
        if not user2:
            print("❌ 无法获取用户信息")
            return False
        
        if user2.id == user1.id and user2.phone_number == user1.phone_number:
            print(f"✅ 会话恢复成功: {user2.first_name} (@{user2.username})")
            print("✅ 用户信息一致")
            return True
        else:
            print("❌ 用户信息不一致")
            return False
        
    finally:
        await client_manager2.cleanup()


async def test_connection_monitoring():
    """测试连接监控功能"""
    print("\n🧪 测试连接监控功能")
    print("-" * 40)
    
    # 获取测试配置
    config = E2EConfig.get_test_config()
    
    # 创建客户端管理器
    client_manager = ClientManager(config)
    
    try:
        # 初始化
        success = await client_manager.initialize()
        if not success:
            print("❌ 客户端管理器初始化失败")
            return False
        
        # 验证初始状态
        if not client_manager.is_connected:
            print("❌ 初始连接状态错误")
            return False
        
        print("✅ 初始连接状态正常")
        
        # 测试连接状态检查
        print("检查连接状态...")
        is_connected = await client_manager.check_connection_status_now()
        if is_connected:
            print("✅ 连接状态检查成功")
        else:
            print("❌ 连接状态检查失败")
            return False
        
        # 等待一段时间，验证连接监控
        print("等待5秒，验证连接监控...")
        await asyncio.sleep(5)
        
        # 再次检查连接状态
        is_connected = await client_manager.check_connection_status_now()
        if is_connected:
            print("✅ 连接监控期间连接正常")
            return True
        else:
            print("❌ 连接监控期间连接丢失")
            return False
        
    finally:
        await client_manager.cleanup()


async def test_error_handling():
    """测试错误处理"""
    print("\n🧪 测试错误处理")
    print("-" * 40)
    
    # 获取测试配置
    config = E2EConfig.get_test_config()
    
    # 创建错误配置
    error_config = config.copy()
    error_config['api_id'] = 'invalid_api_id'
    error_config['api_hash'] = 'invalid_api_hash'
    
    # 创建客户端管理器
    client_manager = ClientManager(error_config)
    
    try:
        # 尝试初始化（应该失败）
        success = await client_manager.initialize()
        if not success:
            print("✅ 使用无效配置正确失败")
            return True
        else:
            print("❌ 使用无效配置应该失败但成功了")
            return False
        
    finally:
        await client_manager.cleanup()


async def test_performance():
    """测试性能"""
    print("\n🧪 测试性能")
    print("-" * 40)
    
    # 获取测试配置
    config = E2EConfig.get_test_config()
    
    # 创建客户端管理器
    client_manager = ClientManager(config)
    
    try:
        # 记录初始化开始时间
        start_time = time.time()
        
        # 初始化
        success = await client_manager.initialize()
        if not success:
            print("❌ 客户端管理器初始化失败")
            return False
        
        # 计算初始化时间
        init_time = time.time() - start_time
        if init_time < 30:
            print(f"✅ 初始化时间正常: {init_time:.2f}秒")
        else:
            print(f"❌ 初始化时间过长: {init_time:.2f}秒")
            return False
        
        # 记录连接检查开始时间
        start_time = time.time()
        
        # 检查连接状态
        is_connected = await client_manager.check_connection_status_now()
        if not is_connected:
            print("❌ 连接状态检查失败")
            return False
        
        # 计算连接检查时间
        check_time = time.time() - start_time
        if check_time < 5:
            print(f"✅ 连接检查时间正常: {check_time:.2f}秒")
        else:
            print(f"❌ 连接检查时间过长: {check_time:.2f}秒")
            return False
        
        print(f"✅ 性能测试通过 - 初始化: {init_time:.2f}秒, 连接检查: {check_time:.2f}秒")
        return True
        
    finally:
        await client_manager.cleanup()


async def run_all_tests():
    """运行所有测试"""
    print("\n🧪 运行所有端到端测试")
    print("=" * 40)
    
    # 定义测试函数列表
    test_functions = [
        ('完整登录流程', test_complete_login_flow),
        ('会话恢复功能', test_session_restoration),
        ('连接监控功能', test_connection_monitoring),
        ('错误处理', test_error_handling),
        ('性能测试', test_performance)
    ]
    
    # 运行测试
    passed = 0
    failed = 0
    
    for test_name, test_func in test_functions:
        try:
            print(f"\n开始测试: {test_name}")
            if await test_func():
                passed += 1
                print(f"✅ {test_name} 测试通过")
            else:
                failed += 1
                print(f"❌ {test_name} 测试失败")
        except Exception as e:
            failed += 1
            print(f"❌ {test_name} 测试异常: {e}")
    
    # 打印测试结果
    print("\n" + "=" * 40)
    print("📊 测试结果汇总")
    print("=" * 40)
    print(f"✅ 通过: {passed}")
    print(f"❌ 失败: {failed}")
    print(f"📈 总计: {passed + failed}")
    print(f"🎯 成功率: {passed / (passed + failed) * 100:.1f}%" if (passed + failed) > 0 else "🎯 成功率: 0%")
    
    return failed == 0


def main():
    """主函数"""
    print_banner()
    
    # 检查环境配置
    if not setup_e2e_environment():
        print("\n❌ 环境配置错误")
        print_config_guide()
        return 1
    
    # 打印当前配置信息
    print("\n📋 当前配置:")
    E2EConfig.print_config_info()
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        test_name = sys.argv[1]
        if test_name == '--help' or test_name == '-h':
            print("\n📖 使用说明:")
            print("python test_client_e2e_simple.py                    # 运行所有测试")
            print("python test_client_e2e_simple.py test_name          # 运行指定测试")
            print("python test_client_e2e_simple.py --help             # 显示帮助")
            print("\n可用的测试:")
            print("  - test_complete_login_flow")
            print("  - test_session_restoration")
            print("  - test_connection_monitoring")
            print("  - test_error_handling")
            print("  - test_performance")
            return 0
        
        # 运行指定测试
        test_map = {
            'test_complete_login_flow': test_complete_login_flow,
            'test_session_restoration': test_session_restoration,
            'test_connection_monitoring': test_connection_monitoring,
            'test_error_handling': test_error_handling,
            'test_performance': test_performance
        }
        
        if test_name in test_map:
            success = asyncio.run(test_map[test_name]())
            return 0 if success else 1
        else:
            print(f"❌ 未知的测试: {test_name}")
            return 1
    
    # 运行所有测试
    success = asyncio.run(run_all_tests())
    return 0 if success else 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⏹️  测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 运行测试时发生错误: {e}")
        sys.exit(1) 