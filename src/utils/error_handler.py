"""
错误处理服务模块，提供统一的异常处理机制
"""

import sys
import traceback
from datetime import datetime
from typing import List, Dict, Any, Optional, Union, Callable, Type, TypeVar
import logging

from src.exceptions.ui_exceptions import BaseUIException, ConfigError
from src.exceptions.operation_exceptions import (
    BaseOperationException, APIError, NetworkError, TaskError, 
    ResourceError, PermissionError, TaskCancelledError, RateLimitError
)
from src.utils.logger import get_logger

# 类型变量，用于泛型函数
T = TypeVar('T')
R = TypeVar('R')

# 获取日志记录器
logger = get_logger()


class ErrorHandler:
    """错误处理服务，提供统一的异常处理机制"""
    
    def __init__(self):
        """初始化错误处理服务"""
        # 记录所有错误
        self.error_log: List[Dict[str, Any]] = []
        # 错误处理器映射
        self.handlers: Dict[Type[Exception], List[Callable[[Exception], None]]] = {}
        # 默认错误处理器
        self.default_handler: Optional[Callable[[Exception], None]] = None
        # 最后一个错误
        self.last_error: Optional[Exception] = None
        # UI错误显示回调
        self.ui_error_callback: Optional[Callable[[str, str, str, bool], None]] = None
    
    def register_handler(self, exception_type: Type[Exception], 
                         handler: Callable[[Exception], None]) -> None:
        """
        注册错误处理器
        
        Args:
            exception_type: 异常类型
            handler: 处理函数
        """
        if exception_type not in self.handlers:
            self.handlers[exception_type] = []
        self.handlers[exception_type].append(handler)
    
    def set_default_handler(self, handler: Callable[[Exception], None]) -> None:
        """
        设置默认错误处理器
        
        Args:
            handler: 处理函数
        """
        self.default_handler = handler
    
    def set_ui_error_callback(self, callback: Callable[[str, str, str, bool], None]) -> None:
        """
        设置UI错误显示回调
        
        Args:
            callback: 回调函数，接受标题、消息、详情和是否可恢复参数
        """
        self.ui_error_callback = callback
    
    def handle(self, exception: Exception) -> None:
        """
        处理异常
        
        Args:
            exception: 异常对象
        """
        # 记录错误
        self.last_error = exception
        error_info = self._get_error_info(exception)
        self.error_log.append(error_info)
        
        # 记录到日志
        if isinstance(exception, (BaseUIException, BaseOperationException)):
            logger.error(str(exception))
        else:
            logger.error(f"未处理的异常: {type(exception).__name__}: {str(exception)}")
            logger.debug(traceback.format_exc())
        
        # 查找并执行处理器
        handled = False
        for exc_type, handlers in self.handlers.items():
            if isinstance(exception, exc_type):
                for handler in handlers:
                    handler(exception)
                handled = True
        
        # 如果没有找到处理器，使用默认处理器
        if not handled and self.default_handler:
            self.default_handler(exception)
        
        # 显示UI错误
        self._show_ui_error(exception)
    
    def _get_error_info(self, exception: Exception) -> Dict[str, Any]:
        """
        获取错误信息
        
        Args:
            exception: 异常对象
            
        Returns:
            Dict[str, Any]: 错误信息字典
        """
        timestamp = datetime.now()
        
        if isinstance(exception, (BaseUIException, BaseOperationException)):
            # 使用自定义异常的to_dict方法
            error_info = exception.to_dict()
            error_info["timestamp"] = timestamp.isoformat()
            return error_info
        else:
            # 处理标准异常
            return {
                "type": type(exception).__name__,
                "message": str(exception),
                "details": traceback.format_exc(),
                "timestamp": timestamp.isoformat()
            }
    
    def _show_ui_error(self, exception: Exception) -> None:
        """
        显示UI错误
        
        Args:
            exception: 异常对象
        """
        if not self.ui_error_callback:
            return
        
        title = "操作错误"
        message = str(exception)
        details = ""
        recoverable = False
        
        if isinstance(exception, BaseUIException):
            title = "界面错误"
            message = exception.message
            details = exception.details or ""
            # UI错误通常不可恢复
            recoverable = False
            
            # 特殊处理
            if isinstance(exception, ConfigError):
                title = "配置错误"
                
        elif isinstance(exception, BaseOperationException):
            title = "操作错误"
            message = exception.message
            details = exception.details or ""
            recoverable = exception.recoverable
            
            # 特殊处理
            if isinstance(exception, APIError):
                title = "API错误"
            elif isinstance(exception, NetworkError):
                title = "网络错误"
            elif isinstance(exception, TaskError):
                title = "任务错误"
                if isinstance(exception, TaskCancelledError):
                    # 任务取消通常不需要显示为错误
                    return
            elif isinstance(exception, ResourceError):
                title = "资源错误"
            elif isinstance(exception, PermissionError):
                title = "权限错误"
            elif isinstance(exception, RateLimitError):
                title = "速率限制"
                message = f"{message} (需等待 {exception.wait_seconds} 秒)"
        
        # 调用UI错误回调
        self.ui_error_callback(title, message, details, recoverable)
    
    def get_error_log(self) -> List[Dict[str, Any]]:
        """
        获取错误日志
        
        Returns:
            List[Dict[str, Any]]: 错误日志列表
        """
        return self.error_log
    
    def clear_error_log(self) -> None:
        """清空错误日志"""
        self.error_log = []
    
    def get_last_error(self) -> Optional[Exception]:
        """
        获取最后一个错误
        
        Returns:
            Optional[Exception]: 最后一个错误对象
        """
        return self.last_error


# 单例模式
_error_handler = ErrorHandler()

def get_error_handler() -> ErrorHandler:
    """
    获取错误处理服务实例
    
    Returns:
        ErrorHandler: 错误处理服务实例
    """
    return _error_handler


def safe_execute(func: Callable[..., T], *args: Any, 
                 **kwargs: Any) -> Optional[T]:
    """
    安全执行函数，捕获异常并交给错误处理器处理
    
    Args:
        func: 要执行的函数
        *args: 函数参数
        **kwargs: 函数关键字参数
        
    Returns:
        Optional[T]: 函数返回值，如果发生异常则返回None
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        get_error_handler().handle(e)
        return None


async def safe_execute_async(func: Callable[..., T], *args: Any, 
                            **kwargs: Any) -> Optional[T]:
    """
    安全执行异步函数，捕获异常并交给错误处理器处理
    
    Args:
        func: 要执行的异步函数
        *args: 函数参数
        **kwargs: 函数关键字参数
        
    Returns:
        Optional[T]: 函数返回值，如果发生异常则返回None
    """
    try:
        return await func(*args, **kwargs)
    except Exception as e:
        get_error_handler().handle(e)
        return None


def with_error_handling(func: Callable[..., T]) -> Callable[..., Optional[T]]:
    """
    错误处理装饰器，为函数添加错误处理
    
    Args:
        func: 要装饰的函数
        
    Returns:
        Callable[..., Optional[T]]: 装饰后的函数
    """
    def wrapper(*args: Any, **kwargs: Any) -> Optional[T]:
        return safe_execute(func, *args, **kwargs)
    return wrapper


def with_error_handling_async(func: Callable[..., T]) -> Callable[..., T]:
    """
    异步错误处理装饰器，为异步函数添加错误处理
    
    Args:
        func: 要装饰的异步函数
        
    Returns:
        Callable[..., T]: 装饰后的异步函数
    """
    async def wrapper(*args: Any, **kwargs: Any) -> Optional[T]:
        return await safe_execute_async(func, *args, **kwargs)
    return wrapper


def convert_exception(from_exception: Type[Exception], 
                     to_exception: Type[Exception], 
                     converter: Callable[[Exception], Exception]) -> Callable[[T], T]:
    """
    异常转换装饰器，将一种异常转换为另一种异常
    
    Args:
        from_exception: 要转换的异常类型
        to_exception: 转换后的异常类型
        converter: 转换函数
        
    Returns:
        Callable[[T], T]: 装饰后的函数
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return func(*args, **kwargs)
            except from_exception as e:
                raise converter(e)
            except Exception as e:
                raise e
        return wrapper
    return decorator


def convert_exception_async(from_exception: Type[Exception], 
                           to_exception: Type[Exception], 
                           converter: Callable[[Exception], Exception]) -> Callable[[T], T]:
    """
    异步异常转换装饰器，将一种异常转换为另一种异常
    
    Args:
        from_exception: 要转换的异常类型
        to_exception: 转换后的异常类型
        converter: 转换函数
        
    Returns:
        Callable[[T], T]: 装饰后的异步函数
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return await func(*args, **kwargs)
            except from_exception as e:
                raise converter(e)
            except Exception as e:
                raise e
        return wrapper
    return decorator 