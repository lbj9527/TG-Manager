"""
FloodWait处理器

统一处理Telegram API限流，提供智能等待和重试机制。
"""

import asyncio
import time
from typing import Any, Callable, Optional
from loguru import logger


class FloodWaitHandler:
    """
    FloodWait处理器，统一处理Telegram API限流。
    
    提供智能等待、指数退避、重试机制等功能。
    """
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 300.0):
        """
        初始化FloodWait处理器。
        
        Args:
            max_retries: 最大重试次数
            base_delay: 基础延迟时间（秒）
            max_delay: 最大延迟时间（秒）
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self._logger = logger.bind(name="FloodWaitHandler")
        self._flood_wait_cache = {}  # 缓存FloodWait信息
    
    async def execute_with_flood_wait(self, func: Callable, *args, **kwargs) -> Any:
        """
        执行函数并处理FloodWait。
        
        Args:
            func: 要执行的函数
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            Any: 函数执行结果
            
        Raises:
            Exception: 当重试次数用尽时抛出异常
        """
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                return result
                
            except Exception as e:
                last_exception = e
                
                # 检查是否为FloodWait错误
                wait_time = self._extract_flood_wait_time(e)
                if wait_time is not None:
                    self._logger.warning(f"检测到FloodWait，等待 {wait_time} 秒")
                    
                    # 发射FloodWait事件
                    self._emit_flood_wait_event(wait_time, str(e))
                    
                    # 等待指定时间
                    await self._wait_with_progress(wait_time)
                    continue
                
                # 检查是否为其他可重试的错误
                if self._is_retryable_error(e) and attempt < self.max_retries:
                    delay = self._calculate_backoff_delay(attempt)
                    self._logger.warning(f"可重试错误，{delay} 秒后重试: {e}")
                    await asyncio.sleep(delay)
                    continue
                
                # 不可重试的错误或重试次数用尽
                break
        
        # 所有重试都失败了
        self._logger.error(f"函数执行失败，已重试 {self.max_retries} 次: {last_exception}")
        raise last_exception
    
    def _extract_flood_wait_time(self, exception: Exception) -> Optional[int]:
        """
        从异常中提取FloodWait等待时间。
        
        Args:
            exception: 异常对象
            
        Returns:
            Optional[int]: 等待时间（秒），如果不是FloodWait则返回None
        """
        error_message = str(exception).lower()
        
        # 检查是否为FloodWait错误
        if "flood" in error_message and "wait" in error_message:
            # 尝试提取等待时间
            import re
            time_match = re.search(r'(\d+)', error_message)
            if time_match:
                return int(time_match.group(1))
        
        return None
    
    def _is_retryable_error(self, exception: Exception) -> bool:
        """
        检查是否为可重试的错误。
        
        Args:
            exception: 异常对象
            
        Returns:
            bool: 是否为可重试的错误
        """
        error_message = str(exception).lower()
        
        # 可重试的错误类型
        retryable_errors = [
            "network",
            "connection",
            "timeout",
            "temporary",
            "server",
            "internal"
        ]
        
        return any(error_type in error_message for error_type in retryable_errors)
    
    def _calculate_backoff_delay(self, attempt: int) -> float:
        """
        计算指数退避延迟时间。
        
        Args:
            attempt: 重试次数
            
        Returns:
            float: 延迟时间（秒）
        """
        delay = self.base_delay * (2 ** attempt)
        return min(delay, self.max_delay)
    
    async def _wait_with_progress(self, wait_time: int) -> None:
        """
        带进度显示的等待。
        
        Args:
            wait_time: 等待时间（秒）
        """
        start_time = time.time()
        remaining_time = wait_time
        
        while remaining_time > 0:
            # 发射进度事件
            progress = (wait_time - remaining_time) / wait_time * 100
            self._emit_flood_wait_progress(progress, remaining_time)
            
            # 等待1秒或剩余时间
            sleep_time = min(1, remaining_time)
            await asyncio.sleep(sleep_time)
            
            remaining_time = wait_time - (time.time() - start_time)
    
    def _emit_flood_wait_event(self, wait_time: int, error_message: str) -> None:
        """
        发射FloodWait事件。
        
        Args:
            wait_time: 等待时间
            error_message: 错误消息
        """
        # 这里可以通过事件总线发射事件
        # 暂时只记录日志
        self._logger.info(f"FloodWait事件: 等待 {wait_time} 秒, 错误: {error_message}")
    
    def _emit_flood_wait_progress(self, progress: float, remaining_time: float) -> None:
        """
        发射FloodWait进度事件。
        
        Args:
            progress: 进度百分比
            remaining_time: 剩余时间
        """
        # 这里可以通过事件总线发射事件
        # 暂时只记录日志
        if int(progress) % 10 == 0:  # 每10%记录一次
            self._logger.debug(f"FloodWait进度: {progress:.1f}%, 剩余 {remaining_time:.1f} 秒")
    
    def set_event_bus(self, event_bus) -> None:
        """
        设置事件总线。
        
        Args:
            event_bus: 事件总线实例
        """
        self.event_bus = event_bus
    
    def get_flood_wait_info(self, chat_id: Optional[int] = None) -> dict:
        """
        获取FloodWait信息。
        
        Args:
            chat_id: 聊天ID，如果为None则返回全局信息
            
        Returns:
            dict: FloodWait信息
        """
        if chat_id is None:
            return {
                'total_flood_waits': len(self._flood_wait_cache),
                'cached_chats': list(self._flood_wait_cache.keys())
            }
        
        return self._flood_wait_cache.get(chat_id, {})
    
    def clear_flood_wait_cache(self, chat_id: Optional[int] = None) -> None:
        """
        清理FloodWait缓存。
        
        Args:
            chat_id: 聊天ID，如果为None则清理所有缓存
        """
        if chat_id is None:
            self._flood_wait_cache.clear()
            self._logger.debug("已清理所有FloodWait缓存")
        else:
            self._flood_wait_cache.pop(chat_id, None)
            self._logger.debug(f"已清理聊天 {chat_id} 的FloodWait缓存")


# 全局FloodWait处理器实例
_global_flood_wait_handler = FloodWaitHandler()


def execute_with_flood_wait(func: Callable, *args, **kwargs) -> Any:
    """
    使用全局FloodWait处理器执行函数。
    
    Args:
        func: 要执行的函数
        *args: 位置参数
        **kwargs: 关键字参数
        
    Returns:
        Any: 函数执行结果
    """
    return _global_flood_wait_handler.execute_with_flood_wait(func, *args, **kwargs)


def set_global_flood_wait_handler(handler: FloodWaitHandler) -> None:
    """
    设置全局FloodWait处理器。
    
    Args:
        handler: FloodWait处理器实例
    """
    global _global_flood_wait_handler
    _global_flood_wait_handler = handler


def get_global_flood_wait_handler() -> FloodWaitHandler:
    """
    获取全局FloodWait处理器。
    
    Returns:
        FloodWaitHandler: 全局FloodWait处理器实例
    """
    return _global_flood_wait_handler 