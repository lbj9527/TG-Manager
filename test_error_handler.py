#!/usr/bin/env python3
"""
错误处理功能测试脚本
测试新的错误处理系统是否能正确分类和显示各种错误
"""

import sys
import os
import asyncio
from unittest.mock import Mock, patch

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.error_handler import ErrorHandler, get_error_handler


class MockException(Exception):
    """模拟异常类"""
    pass


def test_error_classification():
    """测试错误分类功能"""
    print("🧪 测试错误分类功能...")
    
    error_handler = ErrorHandler()
    
    # 测试用例
    test_cases = [
        # (异常对象, 期望的错误类型, 描述)
        (MockException("PEER_ID_INVALID"), "channel_invalid", "频道ID无效"),
        (MockException("CHANNEL_PRIVATE"), "channel_private", "私有频道"),
        (MockException("USER_NOT_PARTICIPANT"), "channel_not_joined", "未加入频道"),
        (MockException("CHAT_NOT_FOUND"), "channel_not_found", "频道不存在"),
        (MockException("FORBIDDEN"), "permission_denied", "权限不足"),
        (MockException("MEDIA_EMPTY"), "media_error", "媒体文件错误"),
        (MockException("NETWORK_ERROR"), "network_error", "网络错误"),
        (MockException("FLOOD_WAIT"), "rate_limit", "请求过于频繁"),
        (MockException("UNAUTHORIZED"), "auth_error", "认证错误"),
        (MockException("DATABASE_LOCKED"), "system_error", "系统错误"),
        (MockException("UNKNOWN_ERROR"), "unknown_error", "未知错误"),
    ]
    
    for exception, expected_type, description in test_cases:
        result = error_handler.classify_error(exception)
        status = "✅" if result == expected_type else "❌"
        print(f"  {status} {description}: {result} (期望: {expected_type})")
    
    print()


def test_channel_info_extraction():
    """测试频道信息提取功能"""
    print("🔍 测试频道信息提取功能...")
    
    error_handler = ErrorHandler()
    
    # 测试用例
    test_cases = [
        # (异常对象, 期望的频道信息, 描述)
        (MockException("PEER_ID_INVALID for chat 123456789"), "123456789", "数字频道ID"),
        (MockException("Channel @example_channel not found"), "@example_channel", "用户名频道"),
        (MockException("https://t.me/example_channel error"), "example_channel", "链接频道"),
        (MockException("频道 123456789 无效"), "123456789", "中文频道ID"),
        (MockException("频道 @example_channel 不存在"), "@example_channel", "中文用户名频道"),
        (MockException("Generic error without channel info"), None, "无频道信息"),
    ]
    
    for exception, expected_info, description in test_cases:
        result = error_handler.extract_channel_info(exception)
        status = "✅" if result == expected_info else "❌"
        print(f"  {status} {description}: {result} (期望: {expected_info})")
    
    print()


def test_error_messages():
    """测试错误消息模板"""
    print("📝 测试错误消息模板...")
    
    error_handler = ErrorHandler()
    
    # 测试所有错误类型的消息模板
    error_types = [
        "channel_invalid", "channel_private", "channel_not_joined", 
        "channel_not_found", "permission_denied", "media_error",
        "network_error", "rate_limit", "auth_error", "system_error", "unknown_error"
    ]
    
    for error_type in error_types:
        template = error_handler.ERROR_MESSAGES.get(error_type)
        if template:
            print(f"  ✅ {error_type}: {template['title']} - {template['message'][:50]}...")
        else:
            print(f"  ❌ {error_type}: 缺少消息模板")
    
    print()


def test_translation_keys():
    """测试翻译键是否存在"""
    print("🌐 测试翻译键...")
    
    # 导入翻译管理器
    from src.utils.translation_manager import get_translation_manager, tr
    
    translation_manager = get_translation_manager()
    
    # 测试错误相关的翻译键
    error_keys = [
        "ui.settings.errors.channel_invalid.title",
        "ui.settings.errors.channel_invalid.message", 
        "ui.settings.errors.channel_invalid.suggestion",
        "ui.settings.errors.channel_private.title",
        "ui.settings.errors.channel_private.message",
        "ui.settings.errors.channel_private.suggestion",
        "ui.settings.errors.permission_denied.title",
        "ui.settings.errors.permission_denied.message",
        "ui.settings.errors.permission_denied.suggestion",
    ]
    
    for key in error_keys:
        try:
            translated = tr(key)
            if translated and translated != key:
                print(f"  ✅ {key}: {translated}")
            else:
                print(f"  ⚠️  {key}: 翻译为空或未找到")
        except Exception as e:
            print(f"  ❌ {key}: 翻译失败 - {e}")
    
    print()


def test_error_handler_singleton():
    """测试错误处理器单例模式"""
    print("🔧 测试错误处理器单例模式...")
    
    # 获取两个实例
    handler1 = get_error_handler()
    handler2 = get_error_handler()
    
    # 检查是否为同一个实例
    if handler1 is handler2:
        print("  ✅ 单例模式工作正常")
    else:
        print("  ❌ 单例模式失败")
    
    print()


def main():
    """主测试函数"""
    print("🚀 开始测试错误处理功能...\n")
    
    try:
        test_error_classification()
        test_channel_info_extraction()
        test_error_messages()
        test_translation_keys()
        test_error_handler_singleton()
        
        print("🎉 所有测试完成！")
        
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main() 