"""
强壮Telegram客户端 - 异常处理模块
智能分类和处理各种Telegram API异常
"""

import asyncio
import time
from typing import Dict, Any, Optional, Callable, Union, Type
from enum import Enum
from dataclasses import dataclass

from pyrogram.errors import (
    FloodWait, SessionPasswordNeeded, PhoneCodeInvalid, PhoneCodeExpired,
    AuthKeyUnregistered, UserDeactivated, Unauthorized,
    InternalServerError, BadRequest, Forbidden, NotAcceptable
)

# 处理Pyrogram版本差异
try:
    from pyrogram.errors import NetworkError
except ImportError:
    # 如果没有NetworkError，创建一个基础异常类代替
    class NetworkError(Exception):
        """网络错误的兼容性类"""
        pass

from src.utils.logger import get_logger

logger = get_logger()


class ExceptionCategory(Enum):
    """异常分类"""
    FLOOD_WAIT = "flood_wait"           # 限流异常
    NETWORK_ERROR = "network_error"     # 网络错误
    AUTH_ERROR = "auth_error"           # 认证错误
    PERMISSION_ERROR = "permission_error"  # 权限错误
    API_ERROR = "api_error"             # API错误
    TIME_SYNC_ERROR = "time_sync_error" # 时间同步错误
    UNKNOWN_ERROR = "unknown_error"     # 未知错误


class HandlingStrategy(Enum):
    """处理策略"""
    RETRY = "retry"                     # 重试
    WAIT_AND_RETRY = "wait_and_retry"   # 等待后重试
    USER_INTERVENTION = "user_intervention"  # 需要用户干预
    IGNORE = "ignore"                   # 忽略
    FAIL_FAST = "fail_fast"             # 快速失败


@dataclass
class ExceptionInfo:
    """异常信息"""
    category: ExceptionCategory
    strategy: HandlingStrategy
    retry_count: int = 0
    max_retries: int = 3
    wait_time: float = 0.0
    can_retry: bool = True
    requires_reconnection: bool = False
    user_message: Optional[str] = None


class FloodWaitHandler:
    """FloodWait处理器"""
    
    def __init__(self, max_retries: int = 5, base_delay: float = 0.5):
        """
        初始化FloodWait处理器
        
        Args:
            max_retries: 最大重试次数
            base_delay: 基础延迟时间
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.active_waits: Dict[str, float] = {}  # 活跃的等待任务
    
    async def handle_flood_wait(self, flood_wait: FloodWait, context: str = "unknown") -> bool:
        """
        处理FloodWait异常
        
        Args:
            flood_wait: FloodWait异常对象
            context: 上下文信息
            
        Returns:
            bool: 是否应该重试
        """
        wait_time = flood_wait.x
        logger.warning(f"收到FloodWait，需要等待 {wait_time} 秒 (上下文: {context})")
        
        # 记录等待时间
        self.active_waits[context] = time.time() + wait_time
        
        try:
            # 等待指定时间
            await asyncio.sleep(wait_time)
            
            # 清除等待记录
            if context in self.active_waits:
                del self.active_waits[context]
            
            logger.info(f"FloodWait等待完成，可以重试 (上下文: {context})")
            return True
            
        except asyncio.CancelledError:
            logger.info(f"FloodWait等待被取消 (上下文: {context})")
            if context in self.active_waits:
                del self.active_waits[context]
            raise
        except Exception as e:
            logger.error(f"FloodWait处理过程中出错: {e}")
            if context in self.active_waits:
                del self.active_waits[context]
            return False
    
    def get_remaining_wait_time(self, context: str = "unknown") -> float:
        """
        获取剩余等待时间
        
        Args:
            context: 上下文信息
            
        Returns:
            float: 剩余等待时间（秒）
        """
        if context not in self.active_waits:
            return 0.0
        
        remaining = self.active_waits[context] - time.time()
        return max(0.0, remaining)


class ExceptionClassifier:
    """异常分类器"""
    
    @staticmethod
    def classify_exception(exception: Exception) -> ExceptionInfo:
        """
        分类异常
        
        Args:
            exception: 异常对象
            
        Returns:
            ExceptionInfo: 异常信息
        """
        # FloodWait异常
        if isinstance(exception, FloodWait):
            return ExceptionInfo(
                category=ExceptionCategory.FLOOD_WAIT,
                strategy=HandlingStrategy.WAIT_AND_RETRY,
                wait_time=exception.x,
                max_retries=5,
                can_retry=True
            )
        
        # 认证相关异常
        elif isinstance(exception, (AuthKeyUnregistered, UserDeactivated, Unauthorized)):
            return ExceptionInfo(
                category=ExceptionCategory.AUTH_ERROR,
                strategy=HandlingStrategy.USER_INTERVENTION,
                can_retry=False,
                requires_reconnection=True,
                user_message="认证失败，请重新登录"
            )
        
        elif isinstance(exception, (SessionPasswordNeeded, PhoneCodeInvalid, PhoneCodeExpired)):
            return ExceptionInfo(
                category=ExceptionCategory.AUTH_ERROR,
                strategy=HandlingStrategy.USER_INTERVENTION,
                can_retry=True,
                user_message="需要提供验证码或密码"
            )
        
        # 网络相关异常
        elif isinstance(exception, NetworkError):
            return ExceptionInfo(
                category=ExceptionCategory.NETWORK_ERROR,
                strategy=HandlingStrategy.RETRY,
                max_retries=3,
                can_retry=True,
                requires_reconnection=True
            )
        
        # 权限相关异常
        elif isinstance(exception, (Forbidden, NotAcceptable)):
            return ExceptionInfo(
                category=ExceptionCategory.PERMISSION_ERROR,
                strategy=HandlingStrategy.FAIL_FAST,
                can_retry=False,
                user_message="权限不足或操作不被允许"
            )
        
        # API错误
        elif isinstance(exception, (BadRequest, InternalServerError)):
            return ExceptionInfo(
                category=ExceptionCategory.API_ERROR,
                strategy=HandlingStrategy.RETRY,
                max_retries=2,
                can_retry=True
            )
        
        # 时间同步错误检测
        elif ExceptionClassifier._is_time_sync_error(exception):
            return ExceptionInfo(
                category=ExceptionCategory.TIME_SYNC_ERROR,
                strategy=HandlingStrategy.USER_INTERVENTION,
                can_retry=False,
                user_message="系统时间同步错误，请同步系统时间"
            )
        
        # 其他异常
        else:
            return ExceptionInfo(
                category=ExceptionCategory.UNKNOWN_ERROR,
                strategy=HandlingStrategy.RETRY,
                max_retries=1,
                can_retry=True
            )
    
    @staticmethod
    def _is_time_sync_error(exception: Exception) -> bool:
        """
        检查是否是时间同步错误
        
        Args:
            exception: 异常对象
            
        Returns:
            bool: 是否是时间同步错误
        """
        error_str = str(exception).lower()
        error_type = type(exception).__name__
        
        time_sync_keywords = [
            "badmsgnotification", "msg_id is too high", "msg_id is too low",
            "time has to be synchronized", "time synchronization", "clock",
            "invalid message identifier", "message identifier", "msg_id",
            "client time has to be synchronized"
        ]
        
        # 检查错误字符串
        for keyword in time_sync_keywords:
            if keyword in error_str:
                return True
        
        # 检查错误类型
        return "badmsgnotification" in error_type.lower()


class RobustExceptionHandler:
    """强壮异常处理器"""
    
    def __init__(self, max_retries: int = 3):
        """
        初始化异常处理器
        
        Args:
            max_retries: 默认最大重试次数
        """
        self.max_retries = max_retries
        self.flood_wait_handler = FloodWaitHandler()
        self.exception_stats: Dict[str, int] = {}
        
        # 回调函数
        self.on_user_intervention_required: Optional[Callable[[ExceptionInfo], None]] = None
        self.on_reconnection_required: Optional[Callable[[ExceptionInfo], None]] = None
        self.on_exception_handled: Optional[Callable[[Exception, ExceptionInfo], None]] = None
    
    async def handle_exception(self, exception: Exception, context: str = "unknown") -> bool:
        """
        处理异常
        
        Args:
            exception: 异常对象
            context: 上下文信息
            
        Returns:
            bool: 是否应该重试
        """
        # 分类异常
        exception_info = ExceptionClassifier.classify_exception(exception)
        
        # 更新统计
        exception_type = type(exception).__name__
        self.exception_stats[exception_type] = self.exception_stats.get(exception_type, 0) + 1
        
        logger.info(f"处理异常: {exception_type} (分类: {exception_info.category.value}, 策略: {exception_info.strategy.value})")
        
        # 根据策略处理异常
        should_retry = False
        
        try:
            if exception_info.strategy == HandlingStrategy.FLOOD_WAIT:
                should_retry = await self._handle_flood_wait(exception, exception_info, context)
            
            elif exception_info.strategy == HandlingStrategy.WAIT_AND_RETRY:
                should_retry = await self._handle_wait_and_retry(exception, exception_info, context)
            
            elif exception_info.strategy == HandlingStrategy.RETRY:
                should_retry = self._handle_retry(exception, exception_info, context)
            
            elif exception_info.strategy == HandlingStrategy.USER_INTERVENTION:
                should_retry = self._handle_user_intervention(exception, exception_info, context)
            
            elif exception_info.strategy == HandlingStrategy.IGNORE:
                should_retry = False
                logger.info(f"忽略异常: {exception}")
            
            elif exception_info.strategy == HandlingStrategy.FAIL_FAST:
                should_retry = False
                logger.error(f"快速失败异常: {exception}")
            
            # 调用异常处理完成回调
            if self.on_exception_handled:
                try:
                    self.on_exception_handled(exception, exception_info)
                except Exception as callback_error:
                    logger.error(f"异常处理回调执行失败: {callback_error}")
            
            return should_retry
            
        except Exception as handler_error:
            logger.error(f"异常处理器内部错误: {handler_error}")
            return False
    
    async def _handle_flood_wait(self, exception: Exception, info: ExceptionInfo, context: str) -> bool:
        """处理FloodWait异常"""
        if isinstance(exception, FloodWait):
            return await self.flood_wait_handler.handle_flood_wait(exception, context)
        return False
    
    async def _handle_wait_and_retry(self, exception: Exception, info: ExceptionInfo, context: str) -> bool:
        """处理等待后重试的异常"""
        if isinstance(exception, FloodWait):
            return await self.flood_wait_handler.handle_flood_wait(exception, context)
        
        # 其他需要等待的异常
        if info.wait_time > 0:
            logger.info(f"等待 {info.wait_time} 秒后重试")
            await asyncio.sleep(info.wait_time)
        
        return info.can_retry
    
    def _handle_retry(self, exception: Exception, info: ExceptionInfo, context: str) -> bool:
        """处理重试异常"""
        if info.retry_count >= info.max_retries:
            logger.error(f"重试次数已达上限 ({info.max_retries})，不再重试")
            return False
        
        info.retry_count += 1
        logger.info(f"准备重试 (第 {info.retry_count}/{info.max_retries} 次)")
        return True
    
    def _handle_user_intervention(self, exception: Exception, info: ExceptionInfo, context: str) -> bool:
        """处理需要用户干预的异常"""
        logger.warning(f"需要用户干预: {info.user_message or str(exception)}")
        
        # 调用用户干预回调
        if self.on_user_intervention_required:
            try:
                self.on_user_intervention_required(info)
            except Exception as callback_error:
                logger.error(f"用户干预回调执行失败: {callback_error}")
        
        # 如果需要重连
        if info.requires_reconnection and self.on_reconnection_required:
            try:
                self.on_reconnection_required(info)
            except Exception as callback_error:
                logger.error(f"重连要求回调执行失败: {callback_error}")
        
        return False  # 通常需要用户干预的异常不能自动重试
    
    def get_exception_stats(self) -> Dict[str, int]:
        """获取异常统计"""
        return self.exception_stats.copy()
    
    def reset_stats(self):
        """重置异常统计"""
        self.exception_stats.clear()
        logger.debug("异常统计已重置")
    
    def get_flood_wait_status(self) -> Dict[str, float]:
        """获取FloodWait状态"""
        return {
            context: self.flood_wait_handler.get_remaining_wait_time(context)
            for context in self.flood_wait_handler.active_waits
        } 