"""
错误处理系统使用示例

本示例展示如何使用异常类和错误处理服务来管理和处理错误。
"""

import os
import sys
import json
import traceback
import asyncio
from typing import Dict, Any, List, Optional
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# 导入异常类和错误处理服务
from src.exceptions.ui_exceptions import (
    ConfigError, ConfigValidationError, ConfigFileError, 
    UIRenderError, UIDataBindingError
)
from src.exceptions.operation_exceptions import (
    APIError, NetworkError, TaskError, ResourceError, 
    PermissionError, RateLimitError, TaskCancelledError
)
from src.utils.error_handler import (
    get_error_handler, safe_execute, safe_execute_async,
    with_error_handling, with_error_handling_async
)


def print_separator(title: str):
    """打印分隔线"""
    print("\n" + "=" * 60)
    print(f" {title} ".center(60, "="))
    print("=" * 60 + "\n")


def setup_error_handler():
    """设置错误处理器示例"""
    print_separator("设置错误处理器")
    
    # 获取错误处理器实例
    error_handler = get_error_handler()
    
    # 设置UI错误回调函数
    def show_error_dialog(title: str, message: str, details: str, recoverable: bool):
        """模拟UI错误对话框显示"""
        print(f"\n[{title}] {message}")
        if details:
            print(f"详细信息: {details}")
        if recoverable:
            print("此错误可恢复，可以重试操作")
        else:
            print("此错误不可恢复，请解决问题后再试")
    
    error_handler.set_ui_error_callback(show_error_dialog)
    
    # 注册特定异常处理器
    def handle_network_error(exception: NetworkError):
        """处理网络错误"""
        print(f"网络错误处理器: {exception}")
        if exception.retry_after > 0:
            print(f"将在 {exception.retry_after} 秒后自动重试")
    
    def handle_rate_limit(exception: RateLimitError):
        """处理API速率限制错误"""
        print(f"速率限制处理器: {exception}")
        print(f"将在 {exception.wait_seconds} 秒后自动重试API调用")
    
    error_handler.register_handler(NetworkError, handle_network_error)
    error_handler.register_handler(RateLimitError, handle_rate_limit)
    
    # 设置默认处理器
    def default_handler(exception: Exception):
        """默认错误处理器"""
        print(f"默认处理器: {type(exception).__name__}: {exception}")
    
    error_handler.set_default_handler(default_handler)
    
    print("错误处理器设置完成")


def demo_config_errors():
    """演示配置错误处理"""
    print_separator("配置错误处理")
    
    # 模拟配置错误
    try:
        # 配置文件不存在
        raise ConfigFileError(
            "无法加载配置文件", 
            "config.json", 
            "文件不存在或无法访问", 
            "请确保配置文件位于正确位置并且有读取权限"
        )
    except Exception as e:
        get_error_handler().handle(e)
    
    # 模拟配置验证错误
    try:
        # 字段验证失败
        raise ConfigValidationError(
            "配置验证失败",
            "GENERAL.api_id",
            ["API ID必须是正整数", "API ID不能为空"],
            "请检查API ID是否正确设置"
        )
    except Exception as e:
        get_error_handler().handle(e)


def demo_operation_errors():
    """演示操作错误处理"""
    print_separator("操作错误处理")
    
    # 模拟API错误
    try:
        raise APIError(
            "无法获取频道信息",
            "get_chat",
            "Telegram API返回错误代码 400",
            "请检查频道ID是否正确",
            "API_BAD_REQUEST",
            False
        )
    except Exception as e:
        get_error_handler().handle(e)
    
    # 模拟网络错误
    try:
        raise NetworkError(
            "网络连接失败",
            "无法连接到Telegram服务器",
            "请检查网络连接和代理设置",
            30  # 30秒后重试
        )
    except Exception as e:
        get_error_handler().handle(e)
    
    # 模拟速率限制错误
    try:
        raise RateLimitError(
            "API调用频率过高",
            60,  # 等待60秒
            "get_messages"
        )
    except Exception as e:
        get_error_handler().handle(e)


def demo_error_decorators():
    """演示错误处理装饰器"""
    print_separator("错误处理装饰器")
    
    # 使用错误处理装饰器
    @with_error_handling
    def unsafe_function(value: int):
        """可能抛出异常的函数"""
        if value < 0:
            raise ValueError("值不能为负数")
        if value == 0:
            raise ZeroDivisionError("值不能为零")
        return 100 / value
    
    # 测试装饰器
    print("调用 unsafe_function(10):")
    result = unsafe_function(10)
    print(f"结果: {result}")
    
    print("\n调用 unsafe_function(0):")
    result = unsafe_function(0)
    print(f"结果: {result}")  # 应为None
    
    print("\n调用 unsafe_function(-5):")
    result = unsafe_function(-5)
    print(f"结果: {result}")  # 应为None


async def demo_async_error_handling():
    """演示异步错误处理"""
    print_separator("异步错误处理")
    
    # 创建一些异步函数
    async def api_call(success: bool):
        """模拟API调用"""
        await asyncio.sleep(1)  # 模拟网络延迟
        if not success:
            raise APIError(
                "API调用失败",
                "send_message",
                "服务器返回错误代码 403",
                "请检查bot权限",
                "FORBIDDEN",
                False
            )
        return "API调用成功"
    
    # 使用异步错误处理装饰器
    @with_error_handling_async
    async def complex_operation():
        """复杂操作，包含多个API调用"""
        print("执行复杂操作...")
        result1 = await api_call(True)
        print(f"第一步: {result1}")
        
        # 这一步会失败
        result2 = await api_call(False)
        print(f"第二步: {result2}")  # 不会执行到这里
        
        return "操作完成"
    
    # 执行异步操作
    result = await complex_operation()
    print(f"复杂操作结果: {result}")  # 应为None
    
    # 使用safe_execute_async
    result = await safe_execute_async(api_call, True)
    print(f"安全执行成功调用: {result}")
    
    result = await safe_execute_async(api_call, False)
    print(f"安全执行失败调用: {result}")  # 应为None


def show_error_log():
    """显示错误日志"""
    print_separator("错误日志")
    
    # 获取错误日志
    error_handler = get_error_handler()
    error_log = error_handler.get_error_log()
    
    print(f"记录了 {len(error_log)} 个错误")
    for i, error in enumerate(error_log):
        print(f"\n错误 #{i+1}:")
        print(f"类型: {error.get('type', 'Unknown')}")
        print(f"消息: {error.get('message', 'No message')}")
        print(f"时间: {error.get('timestamp', 'Unknown')}")
        if 'details' in error and error['details']:
            print(f"详情: {error['details']}")
        if 'suggestion' in error and error['suggestion']:
            print(f"建议: {error['suggestion']}")


async def main():
    """主函数"""
    try:
        # 设置错误处理器
        setup_error_handler()
        
        # 演示配置错误处理
        demo_config_errors()
        
        # 演示操作错误处理
        demo_operation_errors()
        
        # 演示错误处理装饰器
        demo_error_decorators()
        
        # 演示异步错误处理
        await demo_async_error_handling()
        
        # 显示错误日志
        show_error_log()
        
        print("\n示例运行完成")
    
    except Exception as e:
        print(f"未捕获的异常: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main()) 