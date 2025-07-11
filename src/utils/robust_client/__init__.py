"""
强壮Telegram客户端模块
提供强壮的Telegram客户端架构实现
"""

from .config_manager import (
    ClientConfigManager,
    ProxyConfig,
    ConnectionConfig,
    ClientConfig,
    ProxyType
)

from .connection_manager import (
    ConnectionManager,
    ConnectionState,
    ConnectionMetrics,
    ExponentialBackoff
)

from .exception_handler import (
    RobustExceptionHandler,
    ExceptionClassifier,
    FloodWaitHandler,
    ExceptionCategory,
    ExceptionInfo,
    HandlingStrategy
)

from .request_queue import (
    RequestQueueManager,
    QueuedRequest,
    RequestResult,
    RequestPriority,
    RequestType,
    RequestStats,
    RateLimiter
)

from .robust_telegram_client import RobustTelegramClient

__all__ = [
    # 配置管理
    'ClientConfigManager',
    'ProxyConfig',
    'ConnectionConfig', 
    'ClientConfig',
    'ProxyType',
    
    # 连接管理
    'ConnectionManager',
    'ConnectionState',
    'ConnectionMetrics',
    'ExponentialBackoff',
    
    # 异常处理
    'RobustExceptionHandler',
    'ExceptionClassifier',
    'FloodWaitHandler',
    'ExceptionCategory',
    'ExceptionInfo',
    'HandlingStrategy',
    
    # 请求队列
    'RequestQueueManager',
    'QueuedRequest',
    'RequestResult',
    'RequestPriority',
    'RequestType',
    'RequestStats',
    'RateLimiter',
    
    # 核心客户端
    'RobustTelegramClient'
]

__version__ = "1.0.0" 