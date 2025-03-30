"""
日志事件适配器，连接日志系统和事件系统
"""

from typing import Optional
from src.utils.events import EventEmitter
from src.utils.logger import get_logger

class LoggerEventAdapter:
    """
    日志事件适配器，将日志系统连接到事件系统
    
    此适配器确保所有日志消息也可以通过事件系统传递，
    同时保留原有的日志记录功能，用于调试和问题排查
    """
    
    def __init__(self, event_emitter: EventEmitter):
        """
        初始化日志事件适配器
        
        Args:
            event_emitter: 事件发射器实例
        """
        self.logger = get_logger()
        self.event_emitter = event_emitter
        
    def debug(self, message: str) -> None:
        """
        记录调试级别日志，但不通过事件系统传递
        
        Args:
            message: 日志消息
        """
        self.logger.debug(message)
    
    def info(self, message: str) -> None:
        """
        记录信息级别日志，并通过事件系统发送info事件
        
        Args:
            message: 日志消息
        """
        self.logger.debug(f"[INFO] {message}")  # 降级为debug，避免双重输出
        self.event_emitter.emit("info", message)
    
    def status(self, message: str) -> None:
        """
        记录状态消息，并通过事件系统发送status事件
        
        Args:
            message: 状态消息
        """
        self.logger.debug(f"[STATUS] {message}")  # 降级为debug，避免双重输出
        self.event_emitter.emit("status", message)
    
    def warning(self, message: str) -> None:
        """
        记录警告级别日志，并通过事件系统发送warning事件
        
        Args:
            message: 警告消息
        """
        self.logger.warning(message)  # 警告级别保留，便于问题排查
        self.event_emitter.emit("warning", message)
    
    def error(self, message: str, error_type: str = "GENERAL", 
             recoverable: bool = False, details: Optional[str] = None,
             **kwargs) -> None:
        """
        记录错误级别日志，并通过事件系统发送error事件
        
        Args:
            message: 错误消息
            error_type: 错误类型
            recoverable: 是否可恢复
            details: 详细错误信息
            **kwargs: 其他关键字参数
        """
        self.logger.error(message)
        if details:
            self.logger.debug(details)
        self.event_emitter.emit("error", message, error_type=error_type, 
                               recoverable=recoverable, details=details, **kwargs) 