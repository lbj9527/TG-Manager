#!/usr/bin/env python3
"""
端到端测试运行器

运行TG-Manager重构项目的端到端测试，验证真实的Telegram登录和功能。
"""

import asyncio
import os
import sys
import time
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 添加tests目录到Python路径
tests_dir = project_root / "tests"
sys.path.insert(0, str(tests_dir))

# 设置环境变量
os.environ['PYTHONPATH'] = f"{project_root}:{tests_dir}:{os.environ.get('PYTHONPATH', '')}"

from test_e2e.e2e_config import setup_e2e_environment, E2EConfig
from test_e2e.test_client_manager_e2e import TestClientManagerE2E


def print_banner():
    """打印测试横幅"""
    print("=" * 60)
    print("🚀 TG-Manager 端到端测试")
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
    print("   python run_e2e_tests.py")


def run_single_test(test_method_name: str):
    """运行单个测试方法"""
    print(f"\n🧪 运行测试: {test_method_name}")
    print("-" * 40)
    
    # 创建测试实例
    test_instance = TestClientManagerE2E()
    
    # 设置测试环境
    test_instance.setup_test_environment()
    
    # 获取测试方法
    test_method = getattr(test_instance, test_method_name)
    
    try:
        # 运行测试
        start_time = time.time()
        asyncio.run(test_method())
        end_time = time.time()
        
        print(f"✅ 测试通过 - 耗时: {end_time - start_time:.2f}秒")
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def run_all_tests():
    """运行所有端到端测试"""
    print("\n🧪 运行所有端到端测试")
    print("=" * 40)
    
    # 定义测试方法列表
    test_methods = [
        'test_complete_login_flow',
        'test_session_restoration',
        'test_connection_monitoring',
        'test_auto_reconnect',
        'test_error_handling',
        'test_config_validation',
        'test_session_management',
        'test_performance'
    ]
    
    # 运行测试
    passed = 0
    failed = 0
    
    for test_method in test_methods:
        try:
            if run_single_test(test_method):
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ 测试 {test_method} 异常: {e}")
            failed += 1
    
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
            print("python run_e2e_tests.py                    # 运行所有测试")
            print("python run_e2e_tests.py test_name          # 运行指定测试")
            print("python run_e2e_tests.py --help             # 显示帮助")
            print("\n可用的测试方法:")
            test_instance = TestClientManagerE2E()
            for method in dir(test_instance):
                if method.startswith('test_') and callable(getattr(test_instance, method)):
                    print(f"  - {method}")
            return 0
        
        # 运行指定测试
        if hasattr(TestClientManagerE2E(), test_name):
            success = run_single_test(test_name)
            return 0 if success else 1
        else:
            print(f"❌ 未知的测试方法: {test_name}")
            return 1
    
    # 运行所有测试
    success = run_all_tests()
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