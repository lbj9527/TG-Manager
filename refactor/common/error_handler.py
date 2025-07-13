"""
统一错误处理器

提供错误分类、处理和恢复机制，统一管理应用中的各种错误。
"""

import asyncio
import traceback
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
from loguru import logger


class ErrorType(Enum):
    """错误类型枚举。"""
    NETWORK = "network"
    API = "api"
    AUTHENTICATION = "authentication"
    PERMISSION = "permission"
    MEDIA = "media"
    CONFIGURATION = "configuration"
    VALIDATION = "validation"
    RESOURCE = "resource"
    UNKNOWN = "unknown"


class ErrorSeverity(Enum):
    """错误严重程度枚举。"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorInfo:
    """错误信息类。"""
    
    def __init__(self, error: Exception, error_type: ErrorType, severity: ErrorSeverity, context: Dict[str, Any] = None):
        """
        初始化错误信息。
        
        Args:
            error: 异常对象
            error_type: 错误类型
            severity: 错误严重程度
            context: 错误上下文信息
        """
        self.error = error
        self.error_type = error_type
        self.severity = severity
        self.context = context or {}
        self.timestamp = asyncio.get_event_loop().time()
        self.traceback = traceback.format_exc()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式。
        
        Returns:
            Dict[str, Any]: 错误信息字典
        """
        return {
            'error_type': self.error_type.value,
            'severity': self.severity.value,
            'message': str(self.error),
            'context': self.context,
            'timestamp': self.timestamp,
            'traceback': self.traceback
        }


class ErrorHandler:
    """
    统一错误处理器。
    
    提供错误分类、处理、恢复和统计功能。
    """
    
    def __init__(self):
        """初始化错误处理器。"""
        self._logger = logger.bind(name="ErrorHandler")
        self._error_handlers: Dict[ErrorType, List[Callable]] = {}
        self._error_history: List[ErrorInfo] = []
        self._max_history_size = 1000
        self._event_bus = None
        self._recovery_strategies: Dict[ErrorType, Callable] = {}
        
        # 初始化默认错误处理器
        self._init_default_handlers()
    
    def set_event_bus(self, event_bus) -> None:
        """
        设置事件总线。
        
        Args:
            event_bus: 事件总线实例
        """
        self._event_bus = event_bus
    
    def register_error_handler(self, error_type: ErrorType, handler: Callable) -> None:
        """
        注册错误处理器。
        
        Args:
            error_type: 错误类型
            handler: 错误处理函数
        """
        if error_type not in self._error_handlers:
            self._error_handlers[error_type] = []
        self._error_handlers[error_type].append(handler)
        self._logger.debug(f"注册错误处理器: {error_type.value}")
    
    def register_recovery_strategy(self, error_type: ErrorType, strategy: Callable) -> None:
        """
        注册错误恢复策略。
        
        Args:
            error_type: 错误类型
            strategy: 恢复策略函数
        """
        self._recovery_strategies[error_type] = strategy
        self._logger.debug(f"注册恢复策略: {error_type.value}")
    
    def handle_error(self, error: Exception, context: Dict[str, Any] = None) -> ErrorInfo:
        """
        处理错误。
        
        Args:
            error: 异常对象
            context: 错误上下文信息
            
        Returns:
            ErrorInfo: 错误信息对象
        """
        # 分类错误
        error_type = self._classify_error(error)
        severity = self._determine_severity(error, error_type)
        
        # 创建错误信息
        error_info = ErrorInfo(error, error_type, severity, context)
        
        # 记录错误
        self._log_error(error_info)
        
        # 添加到历史记录
        self._add_to_history(error_info)
        
        # 发射错误事件
        self._emit_error_event(error_info)
        
        # 调用错误处理器
        self._call_error_handlers(error_info)
        
        # 尝试恢复
        self._attempt_recovery(error_info)
        
        return error_info
    
    async def handle_error_async(self, error: Exception, context: Dict[str, Any] = None) -> ErrorInfo:
        """
        异步处理错误。
        
        Args:
            error: 异常对象
            context: 错误上下文信息
            
        Returns:
            ErrorInfo: 错误信息对象
        """
        # 分类错误
        error_type = self._classify_error(error)
        severity = self._determine_severity(error, error_type)
        
        # 创建错误信息
        error_info = ErrorInfo(error, error_type, severity, context)
        
        # 记录错误
        self._log_error(error_info)
        
        # 添加到历史记录
        self._add_to_history(error_info)
        
        # 发射错误事件
        await self._emit_error_event_async(error_info)
        
        # 调用错误处理器
        await self._call_error_handlers_async(error_info)
        
        # 尝试恢复
        await self._attempt_recovery_async(error_info)
        
        return error_info
    
    def _classify_error(self, error: Exception) -> ErrorType:
        """
        分类错误。
        
        Args:
            error: 异常对象
            
        Returns:
            ErrorType: 错误类型
        """
        error_message = str(error).lower()
        error_class = type(error).__name__.lower()
        
        # 网络错误
        if any(keyword in error_message for keyword in ['network', 'connection', 'timeout', 'socket']):
            return ErrorType.NETWORK
        
        # API错误
        if any(keyword in error_message for keyword in ['api', 'telegram', 'bot']):
            return ErrorType.API
        
        # 认证错误
        if any(keyword in error_message for keyword in ['auth', 'login', 'session', 'token']):
            return ErrorType.AUTHENTICATION
        
        # 权限错误
        if any(keyword in error_message for keyword in ['permission', 'forbidden', 'unauthorized']):
            return ErrorType.PERMISSION
        
        # 媒体错误
        if any(keyword in error_message for keyword in ['media', 'file', 'photo', 'video', 'document']):
            return ErrorType.MEDIA
        
        # 配置错误
        if any(keyword in error_message for keyword in ['config', 'setting', 'parameter']):
            return ErrorType.CONFIGURATION
        
        # 验证错误
        if any(keyword in error_message for keyword in ['validation', 'invalid', 'format']):
            return ErrorType.VALIDATION
        
        # 资源错误
        if any(keyword in error_message for keyword in ['resource', 'memory', 'disk', 'file']):
            return ErrorType.RESOURCE
        
        return ErrorType.UNKNOWN
    
    def _determine_severity(self, error: Exception, error_type: ErrorType) -> ErrorSeverity:
        """
        确定错误严重程度。
        
        Args:
            error: 异常对象
            error_type: 错误类型
            
        Returns:
            ErrorSeverity: 错误严重程度
        """
        error_message = str(error).lower()
        
        # 严重错误
        if any(keyword in error_message for keyword in ['critical', 'fatal', 'emergency']):
            return ErrorSeverity.CRITICAL
        
        # 高严重程度错误
        if error_type in [ErrorType.AUTHENTICATION, ErrorType.PERMISSION]:
            return ErrorSeverity.HIGH
        
        # 中等严重程度错误
        if error_type in [ErrorType.NETWORK, ErrorType.API, ErrorType.MEDIA]:
            return ErrorSeverity.MEDIUM
        
        # 低严重程度错误
        if error_type in [ErrorType.CONFIGURATION, ErrorType.VALIDATION]:
            return ErrorSeverity.LOW
        
        return ErrorSeverity.MEDIUM
    
    def _log_error(self, error_info: ErrorInfo) -> None:
        """
        记录错误日志。
        
        Args:
            error_info: 错误信息对象
        """
        log_message = f"错误类型: {error_info.error_type.value}, 严重程度: {error_info.severity.value}, 消息: {error_info.error}"
        
        if error_info.severity == ErrorSeverity.CRITICAL:
            self._logger.critical(log_message)
        elif error_info.severity == ErrorSeverity.HIGH:
            self._logger.error(log_message)
        elif error_info.severity == ErrorSeverity.MEDIUM:
            self._logger.warning(log_message)
        else:
            self._logger.info(log_message)
    
    def _add_to_history(self, error_info: ErrorInfo) -> None:
        """
        添加错误到历史记录。
        
        Args:
            error_info: 错误信息对象
        """
        self._error_history.append(error_info)
        
        # 限制历史记录大小
        if len(self._error_history) > self._max_history_size:
            self._error_history = self._error_history[-self._max_history_size:]
    
    def _emit_error_event(self, error_info: ErrorInfo) -> None:
        """
        发射错误事件。
        
        Args:
            error_info: 错误信息对象
        """
        if self._event_bus:
            self._event_bus.emit("error_occurred", error_info.to_dict())
    
    async def _emit_error_event_async(self, error_info: ErrorInfo) -> None:
        """
        异步发射错误事件。
        
        Args:
            error_info: 错误信息对象
        """
        if self._event_bus:
            await self._event_bus.emit_async("error_occurred", error_info.to_dict())
    
    def _call_error_handlers(self, error_info: ErrorInfo) -> None:
        """
        调用错误处理器。
        
        Args:
            error_info: 错误信息对象
        """
        handlers = self._error_handlers.get(error_info.error_type, [])
        for handler in handlers:
            try:
                handler(error_info)
            except Exception as e:
                self._logger.error(f"错误处理器执行失败: {e}")
    
    async def _call_error_handlers_async(self, error_info: ErrorInfo) -> None:
        """
        异步调用错误处理器。
        
        Args:
            error_info: 错误信息对象
        """
        handlers = self._error_handlers.get(error_info.error_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(error_info)
                else:
                    handler(error_info)
            except Exception as e:
                self._logger.error(f"错误处理器执行失败: {e}")
    
    def _attempt_recovery(self, error_info: ErrorInfo) -> bool:
        """
        尝试错误恢复。
        
        Args:
            error_info: 错误信息对象
            
        Returns:
            bool: 是否成功恢复
        """
        strategy = self._recovery_strategies.get(error_info.error_type)
        if strategy:
            try:
                result = strategy(error_info)
                if result:
                    self._logger.info(f"错误恢复成功: {error_info.error_type.value}")
                return bool(result)
            except Exception as e:
                self._logger.error(f"错误恢复失败: {e}")
        
        return False
    
    async def _attempt_recovery_async(self, error_info: ErrorInfo) -> bool:
        """
        异步尝试错误恢复。
        
        Args:
            error_info: 错误信息对象
            
        Returns:
            bool: 是否成功恢复
        """
        strategy = self._recovery_strategies.get(error_info.error_type)
        if strategy:
            try:
                if asyncio.iscoroutinefunction(strategy):
                    result = await strategy(error_info)
                else:
                    result = strategy(error_info)
                
                if result:
                    self._logger.info(f"错误恢复成功: {error_info.error_type.value}")
                return bool(result)
            except Exception as e:
                self._logger.error(f"错误恢复失败: {e}")
        
        return False
    
    def _init_default_handlers(self) -> None:
        """初始化默认错误处理器。"""
        # 网络错误处理器
        self.register_error_handler(ErrorType.NETWORK, self._handle_network_error)
        
        # 认证错误处理器
        self.register_error_handler(ErrorType.AUTHENTICATION, self._handle_auth_error)
        
        # 权限错误处理器
        self.register_error_handler(ErrorType.PERMISSION, self._handle_permission_error)
        
        # 媒体错误处理器
        self.register_error_handler(ErrorType.MEDIA, self._handle_media_error)
    
    def _handle_network_error(self, error_info: ErrorInfo) -> None:
        """
        处理网络错误。
        
        Args:
            error_info: 错误信息对象
        """
        self._logger.warning("检测到网络错误，可能需要检查网络连接")
    
    def _handle_auth_error(self, error_info: ErrorInfo) -> None:
        """
        处理认证错误。
        
        Args:
            error_info: 错误信息对象
        """
        self._logger.error("检测到认证错误，可能需要重新登录")
    
    def _handle_permission_error(self, error_info: ErrorInfo) -> None:
        """
        处理权限错误。
        
        Args:
            error_info: 错误信息对象
        """
        self._logger.error("检测到权限错误，请检查用户权限")
    
    def _handle_media_error(self, error_info: ErrorInfo) -> None:
        """
        处理媒体错误。
        
        Args:
            error_info: 错误信息对象
        """
        self._logger.warning("检测到媒体错误，可能是文件格式不支持或文件损坏")
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """
        获取错误统计信息。
        
        Returns:
            Dict[str, Any]: 错误统计信息
        """
        stats = {
            'total_errors': len(self._error_history),
            'error_types': {},
            'severity_levels': {},
            'recent_errors': []
        }
        
        # 统计错误类型
        for error_info in self._error_history:
            error_type = error_info.error_type.value
            severity = error_info.severity.value
            
            stats['error_types'][error_type] = stats['error_types'].get(error_type, 0) + 1
            stats['severity_levels'][severity] = stats['severity_levels'].get(severity, 0) + 1
        
        # 最近错误
        stats['recent_errors'] = [error.to_dict() for error in self._error_history[-10:]]
        
        return stats
    
    def clear_error_history(self) -> None:
        """清空错误历史记录。"""
        self._error_history.clear()
        self._logger.info("错误历史记录已清空")
    
    def get_errors_by_type(self, error_type: ErrorType) -> List[ErrorInfo]:
        """
        获取指定类型的错误。
        
        Args:
            error_type: 错误类型
            
        Returns:
            List[ErrorInfo]: 错误信息列表
        """
        return [error for error in self._error_history if error.error_type == error_type]
    
    def get_errors_by_severity(self, severity: ErrorSeverity) -> List[ErrorInfo]:
        """
        获取指定严重程度的错误。
        
        Args:
            severity: 错误严重程度
            
        Returns:
            List[ErrorInfo]: 错误信息列表
        """
        return [error for error in self._error_history if error.severity == severity]

    @property
    def event_bus(self):
        """获取事件总线"""
        return self._event_bus


# 全局错误处理器实例
_global_error_handler = ErrorHandler()


def handle_error(error: Exception, context: Dict[str, Any] = None) -> ErrorInfo:
    """
    使用全局错误处理器处理错误。
    
    Args:
        error: 异常对象
        context: 错误上下文信息
        
    Returns:
        ErrorInfo: 错误信息对象
    """
    return _global_error_handler.handle_error(error, context)


async def handle_error_async(error: Exception, context: Dict[str, Any] = None) -> ErrorInfo:
    """
    使用全局错误处理器异步处理错误。
    
    Args:
        error: 异常对象
        context: 错误上下文信息
        
    Returns:
        ErrorInfo: 错误信息对象
    """
    return await _global_error_handler.handle_error_async(error, context)


def set_global_error_handler(handler: ErrorHandler) -> None:
    """
    设置全局错误处理器。
    
    Args:
        handler: 错误处理器实例
    """
    global _global_error_handler
    _global_error_handler = handler


def get_global_error_handler() -> ErrorHandler:
    """
    获取全局错误处理器。
    
    Returns:
        ErrorHandler: 全局错误处理器实例
    """
    return _global_error_handler 