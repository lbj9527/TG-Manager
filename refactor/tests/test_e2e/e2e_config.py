"""
端到端测试配置文件

用于管理端到端测试的环境变量和配置参数。
"""

import os
from typing import Dict, Any, Optional


class E2EConfig:
    """端到端测试配置管理"""
    
    @staticmethod
    def get_telegram_config() -> Dict[str, Any]:
        """获取Telegram API配置"""
        return {
            'api_id': os.getenv('TELEGRAM_API_ID', ''),
            'api_hash': os.getenv('TELEGRAM_API_HASH', ''),
            'phone_number': os.getenv('TELEGRAM_PHONE_NUMBER', ''),
            'session_name': os.getenv('TELEGRAM_SESSION_NAME', 'test_session_e2e'),
            'session_path': os.getenv('TELEGRAM_SESSION_PATH', 'test_sessions')
        }
    
    @staticmethod
    def get_login_config() -> Dict[str, Any]:
        """获取登录配置"""
        return {
            'phone_number': os.getenv('TELEGRAM_PHONE_NUMBER', ''),
            'code_timeout': int(os.getenv('CODE_TIMEOUT', '60')),
            'two_fa_password': os.getenv('TWO_FA_PASSWORD', '')
        }
    
    @staticmethod
    def get_proxy_config() -> Optional[Dict[str, Any]]:
        """获取代理配置"""
        use_proxy = os.getenv('USE_PROXY', 'false').lower() == 'true'
        
        if not use_proxy:
            return None
        
        return {
            'scheme': os.getenv('PROXY_SCHEME', 'socks5'),  # socks5, http, https
            'hostname': os.getenv('PROXY_HOST', ''),
            'port': int(os.getenv('PROXY_PORT', '1080')),
            'username': os.getenv('PROXY_USERNAME', ''),
            'password': os.getenv('PROXY_PASSWORD', '')
        }
    
    @staticmethod
    def get_test_config() -> Dict[str, Any]:
        """获取完整测试配置"""
        config = {
            'session_name': 'test_session_e2e',
            'session_path': 'test_sessions',
            'auto_reconnect': True,
            'max_reconnect_attempts': int(os.getenv('MAX_RECONNECT_ATTEMPTS', '3')),
            'reconnect_delay': float(os.getenv('RECONNECT_DELAY', '2.0')),
            'monitor_interval': int(os.getenv('MONITOR_INTERVAL', '10')),
            'test_timeout': int(os.getenv('TEST_TIMEOUT', '300')),
            **E2EConfig.get_telegram_config(),
            **E2EConfig.get_login_config()
        }
        
        # 添加代理配置
        proxy_config = E2EConfig.get_proxy_config()
        if proxy_config:
            config['proxy'] = proxy_config
        
        return config
    
    @staticmethod
    def validate_config() -> bool:
        """验证配置是否完整"""
        telegram_config = E2EConfig.get_telegram_config()
        login_config = E2EConfig.get_login_config()
        
        # 检查必需的Telegram配置
        if not telegram_config['api_id']:
            print("错误: 缺少 TELEGRAM_API_ID 环境变量")
            return False
        
        if not telegram_config['api_hash']:
            print("错误: 缺少 TELEGRAM_API_HASH 环境变量")
            return False
        
        # 检查登录配置
        if not login_config['phone_number']:
            print("错误: 缺少 TELEGRAM_PHONE_NUMBER 环境变量")
            return False
        
        # 检查代理配置（如果启用）
        if os.getenv('USE_PROXY', 'false').lower() == 'true':
            proxy_config = E2EConfig.get_proxy_config()
            if not proxy_config['hostname']:
                print("错误: 启用代理但缺少 PROXY_HOST 环境变量")
                return False
            
            if not proxy_config['port']:
                print("错误: 启用代理但缺少 PROXY_PORT 环境变量")
                return False
        
        return True
    
    @staticmethod
    def print_config_info():
        """打印配置信息"""
        print("=== 端到端测试配置信息 ===")
        
        telegram_config = E2EConfig.get_telegram_config()
        login_config = E2EConfig.get_login_config()
        
        print(f"Telegram API ID: {telegram_config['api_id'][:8]}..." if telegram_config['api_id'] else "未设置")
        print(f"Telegram API Hash: {telegram_config['api_hash'][:8]}..." if telegram_config['api_hash'] else "未设置")
        print(f"Phone Number: {login_config['phone_number']}" if login_config['phone_number'] else "未设置")
        print(f"Session Name: {telegram_config['session_name']}")
        print(f"Session Path: {telegram_config['session_path']}")
        print(f"Code Timeout: {login_config['code_timeout']}秒")
        print(f"2FA Password: {'已设置' if login_config['two_fa_password'] else '未设置'}")
        
        proxy_config = E2EConfig.get_proxy_config()
        if proxy_config:
            print(f"代理配置: {proxy_config['scheme']}://{proxy_config['hostname']}:{proxy_config['port']}")
        else:
            print("代理配置: 未启用")
        
        print("==========================")


def load_env_from_file(env_file: str = '.env.e2e'):
    """从文件加载环境变量"""
    if not os.path.exists(env_file):
        print(f"警告: 环境变量文件 {env_file} 不存在")
        return
    
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value
    
    print(f"已从 {env_file} 加载环境变量")


def setup_e2e_environment():
    """设置端到端测试环境"""
    # 尝试加载环境变量文件
    load_env_from_file()
    
    # 验证配置
    if not E2EConfig.validate_config():
        print("\n请设置以下环境变量:")
        print("TELEGRAM_API_ID=你的Telegram API ID")
        print("TELEGRAM_API_HASH=你的Telegram API Hash")
        print("TELEGRAM_PHONE_NUMBER=你的手机号码（包含国家代码）")
        print("\n如果需要代理，还需要设置:")
        print("USE_PROXY=true")
        print("PROXY_SCHEME=socks5")
        print("PROXY_HOST=代理服务器地址")
        print("PROXY_PORT=代理服务器端口")
        print("PROXY_USERNAME=代理用户名 (可选)")
        print("PROXY_PASSWORD=代理密码 (可选)")
        print("\n如果启用了两步验证，还需要设置:")
        print("TWO_FA_PASSWORD=你的两步验证密码")
        return False
    
    # 打印配置信息
    E2EConfig.print_config_info()
    return True


if __name__ == "__main__":
    # 测试配置加载
    setup_e2e_environment() 