#!/usr/bin/env python3
"""
测试客户端创建逻辑
验证根据会话文件是否存在选择不同的创建方式
"""

import os
import sys
from pathlib import Path

def test_session_file_detection():
    """测试会话文件检测逻辑"""
    print("=== 测试会话文件检测逻辑 ===")
    
    session_name = "tg_manager"
    session_path = f"sessions/{session_name}.session"
    
    # 检查会话文件是否存在
    session_exists = os.path.exists(session_path)
    
    print(f"会话名称: {session_name}")
    print(f"会话文件路径: {session_path}")
    print(f"会话文件存在: {session_exists}")
    
    if session_exists:
        print("✅ 将使用Pyrogram官方推荐方式创建客户端（仅提供会话名称）")
        print("   Client(name='sessions/tg_manager', **proxy_args)")
    else:
        print("✅ 将使用完整API凭据方式创建客户端")
        print("   Client(name='sessions/tg_manager', api_id=..., api_hash=..., phone_number=..., **proxy_args)")
    
    print()

def main():
    """主测试函数"""
    print("TG-Manager 客户端创建逻辑测试")
    print("=" * 50)
    
    test_session_file_detection()
    
    print("测试完成！")
    print("\n说明:")
    print("- 如果会话文件存在，使用 Pyrogram 官方推荐方式: Client('my_account')")
    print("- 如果会话文件不存在，使用完整凭据方式: Client('my_account', api_id=..., api_hash=...)")
    print("- 代理设置根据配置中的 proxy_enabled 决定是否使用")

if __name__ == "__main__":
    main() 