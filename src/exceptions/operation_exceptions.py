"""
操作相关异常类，用于处理API调用、网络请求和任务执行等错误
"""

from typing import List, Dict, Any, Optional, Union
from datetime import datetime


class BaseOperationException(Exception):
    """操作异常基类"""
    
    def __init__(self, message: str, details: Optional[str] = None, 
                 suggestion: Optional[str] = None, error_code: Optional[str] = None,
                 recoverable: bool = False):
        """
        初始化操作异常
        
        Args:
            message: 错误消息
            details: 详细错误信息
            suggestion: 解决建议
            error_code: 错误代码
            recoverable: 是否可恢复的错误
        """
        self.message = message
        self.details = details
        self.suggestion = suggestion
        self.error_code = error_code
        self.recoverable = recoverable
        self.timestamp = datetime.now()
        super().__init__(message)
    
    def __str__(self) -> str:
        """返回格式化的错误信息"""
        error_str = self.message
        if self.details:
            error_str += f"\n详情: {self.details}"
        if self.suggestion:
            error_str += f"\n建议: {self.suggestion}"
        if self.error_code:
            error_str += f"\n错误代码: {self.error_code}"
        if self.recoverable:
            error_str += "\n(此错误可能可以通过重试解决)"
        return error_str
    
    def to_dict(self) -> Dict[str, Any]:
        """将异常转换为字典格式，方便序列化和日志记录"""
        return {
            "type": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
            "suggestion": self.suggestion,
            "error_code": self.error_code,
            "recoverable": self.recoverable,
            "timestamp": self.timestamp.isoformat()
        }


class APIError(BaseOperationException):
    """API错误，当Telegram API调用失败时抛出"""
    
    def __init__(self, message: str, api_name: Optional[str] = None, 
                 details: Optional[str] = None, suggestion: Optional[str] = None,
                 error_code: Optional[str] = None, recoverable: bool = False):
        super().__init__(
            message,
            details or (f"API: {api_name}" if api_name else None),
            suggestion or "请检查API参数和权限设置",
            error_code or "API_ERROR",
            recoverable
        )
        self.api_name = api_name


class RateLimitError(APIError):
    """速率限制错误，当API调用频率过高时抛出"""
    
    def __init__(self, message: str, wait_seconds: int = 0, api_name: Optional[str] = None,
                 details: Optional[str] = None):
        suggestion = f"请等待 {wait_seconds} 秒后重试" if wait_seconds > 0 else "请降低API调用频率"
        super().__init__(
            message,
            api_name,
            details or (f"需要等待: {wait_seconds}秒" if wait_seconds > 0 else None),
            suggestion,
            "RATE_LIMIT_ERROR",
            True  # 可恢复的错误
        )
        self.wait_seconds = wait_seconds


class NetworkError(BaseOperationException):
    """网络错误，当网络连接失败时抛出"""
    
    def __init__(self, message: str, details: Optional[str] = None, 
                 suggestion: Optional[str] = None, retry_after: int = 0):
        super().__init__(
            message,
            details,
            suggestion or "请检查网络连接和代理设置",
            "NETWORK_ERROR",
            True  # 网络错误通常是可恢复的
        )
        self.retry_after = retry_after


class AuthError(BaseOperationException):
    """认证错误，当API凭据无效或会话过期时抛出"""
    
    def __init__(self, message: str, details: Optional[str] = None, 
                 suggestion: Optional[str] = None):
        super().__init__(
            message,
            details,
            suggestion or "请检查API ID和API Hash，确保它们正确",
            "AUTH_ERROR",
            False  # 认证错误通常需要用户干预
        )


class ChannelError(BaseOperationException):
    """频道错误，当频道不存在或无权访问时抛出"""
    
    def __init__(self, message: str, channel_id: Optional[str] = None,
                 details: Optional[str] = None, suggestion: Optional[str] = None):
        super().__init__(
            message,
            details or (f"频道: {channel_id}" if channel_id else None),
            suggestion or "请检查频道ID和访问权限",
            "CHANNEL_ERROR",
            False
        )
        self.channel_id = channel_id


class MessageError(BaseOperationException):
    """消息错误，当消息不存在或无法处理时抛出"""
    
    def __init__(self, message: str, message_id: Optional[int] = None, 
                 channel_id: Optional[str] = None, details: Optional[str] = None,
                 suggestion: Optional[str] = None):
        _details = details
        if not _details:
            if message_id and channel_id:
                _details = f"消息ID: {message_id}, 频道: {channel_id}"
            elif message_id:
                _details = f"消息ID: {message_id}"
            elif channel_id:
                _details = f"频道: {channel_id}"
        
        super().__init__(
            message,
            _details,
            suggestion or "请检查消息ID和访问权限",
            "MESSAGE_ERROR",
            False
        )
        self.message_id = message_id
        self.channel_id = channel_id


class MediaError(BaseOperationException):
    """媒体文件错误，当媒体文件无法下载或处理时抛出"""
    
    def __init__(self, message: str, file_type: Optional[str] = None,
                 file_path: Optional[str] = None, details: Optional[str] = None,
                 suggestion: Optional[str] = None, recoverable: bool = False):
        _details = details
        if not _details:
            parts = []
            if file_type:
                parts.append(f"文件类型: {file_type}")
            if file_path:
                parts.append(f"文件路径: {file_path}")
            if parts:
                _details = ", ".join(parts)
        
        super().__init__(
            message,
            _details,
            suggestion or "请检查文件格式和权限",
            "MEDIA_ERROR",
            recoverable
        )
        self.file_type = file_type
        self.file_path = file_path


class TaskError(BaseOperationException):
    """任务错误，当任务执行失败时抛出"""
    
    def __init__(self, message: str, task_id: Optional[str] = None,
                 task_type: Optional[str] = None, details: Optional[str] = None,
                 suggestion: Optional[str] = None, recoverable: bool = False):
        _details = details
        if not _details:
            parts = []
            if task_id:
                parts.append(f"任务ID: {task_id}")
            if task_type:
                parts.append(f"任务类型: {task_type}")
            if parts:
                _details = ", ".join(parts)
        
        super().__init__(
            message,
            _details,
            suggestion or "请检查任务参数和环境设置",
            "TASK_ERROR",
            recoverable
        )
        self.task_id = task_id
        self.task_type = task_type


class TaskCancelledError(TaskError):
    """任务取消错误，当任务被用户手动取消时抛出"""
    
    def __init__(self, message: str = "任务已被取消", task_id: Optional[str] = None,
                 task_type: Optional[str] = None, details: Optional[str] = None):
        super().__init__(
            message,
            task_id,
            task_type,
            details,
            "任务已被用户取消，无需进一步操作",
            False
        )


class ResourceError(BaseOperationException):
    """资源错误，当资源无法访问或处理时抛出"""
    
    def __init__(self, message: str, resource_type: Optional[str] = None,
                 resource_id: Optional[str] = None, details: Optional[str] = None,
                 suggestion: Optional[str] = None, recoverable: bool = False):
        _details = details
        if not _details:
            parts = []
            if resource_type:
                parts.append(f"资源类型: {resource_type}")
            if resource_id:
                parts.append(f"资源ID: {resource_id}")
            if parts:
                _details = ", ".join(parts)
        
        super().__init__(
            message,
            _details,
            suggestion or "请检查资源权限和可用性",
            "RESOURCE_ERROR",
            recoverable
        )
        self.resource_type = resource_type
        self.resource_id = resource_id


class PermissionError(BaseOperationException):
    """权限错误，当没有足够的权限执行操作时抛出"""
    
    def __init__(self, message: str, operation: Optional[str] = None,
                 details: Optional[str] = None, suggestion: Optional[str] = None):
        super().__init__(
            message,
            details or (f"操作: {operation}" if operation else None),
            suggestion or "请确保有足够的权限执行此操作",
            "PERMISSION_ERROR",
            False
        )
        self.operation = operation 