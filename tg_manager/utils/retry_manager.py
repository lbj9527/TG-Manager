"""
重试管理模块
实现失败重试逻辑，根据配置的max_retries和timeout控制重试策略
"""

import time
import random
import asyncio
from typing import Callable, TypeVar, Optional, Any
from functools import wraps

from tg_manager.utils.logger import get_logger

logger = get_logger("retry_manager")

# 定义泛型类型变量
T = TypeVar('T')


class RetryManager:
    """重试管理类，提供操作失败重试功能"""
    
    def __init__(self, max_retries: int = 3, timeout: int = 30, 
                 backoff_factor: float = 1.5, jitter: float = 0.1):
        """
        初始化重试管理器
        
        Args:
            max_retries: 最大重试次数
            timeout: 超时时间（秒）
            backoff_factor: 退避系数，每次重试等待时间将乘以此系数
            jitter: 随机抖动系数，用于避免重试风暴
        """
        self.max_retries = max_retries
        self.timeout = timeout
        self.backoff_factor = backoff_factor
        self.jitter = jitter
    
    def retry(self, func: Callable[..., T]) -> Callable[..., T]:
        """
        重试装饰器，用于自动重试失败的操作
        
        Args:
            func: 要执行的函数
            
        Returns:
            装饰后的函数
        """
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception = None
            wait_time = 1.0
            
            for attempt in range(self.max_retries + 1):
                try:
                    if attempt > 0:
                        logger.info(f"重试第{attempt}次 '{func.__name__}'，等待 {wait_time:.2f} 秒")
                        time.sleep(wait_time)
                        
                        # 应用指数退避和随机抖动
                        wait_time = wait_time * self.backoff_factor * (1 + random.uniform(-self.jitter, self.jitter))
                    
                    return func(*args, **kwargs)
                except Exception as e:
                    logger.warning(f"函数 '{func.__name__}' 执行失败: {e}")
                    last_exception = e
                    
                    # 检查是否是最后一次尝试
                    if attempt >= self.max_retries:
                        logger.error(f"已达到最大重试次数 ({self.max_retries})，放弃操作")
                        break
            
            # 重试后仍然失败，抛出最后一个异常
            if last_exception:
                raise last_exception
            
            raise RuntimeError(f"函数 '{func.__name__}' 执行失败，已达到最大重试次数")
        
        return wrapper
    
    async def retry_async(self, func, *args, **kwargs):
        """异步重试函数。

        根据设置的重试策略，自动重试失败的异步操作。

        Args:
            func (callable): 要执行的异步函数
            *args: 传递给函数的位置参数
            **kwargs: 传递给函数的关键字参数

        Returns:
            Any: 函数的返回值

        Raises:
            Exception: 如果所有重试都失败，则抛出最后一个异常
        """
        last_exception = None
        attempt = 0
        
        while attempt < self.max_retries + 1:
            try:
                if attempt > 0:
                    wait_time = self._get_wait_time(attempt - 1)
                    logger.info(f"异步重试第{attempt}次，等待 {wait_time:.2f} 秒")
                    
                    try:
                        # 使用可中断的等待
                        await asyncio.sleep(wait_time)
                    except asyncio.CancelledError:
                        logger.info("重试等待被取消")
                        raise  # 重新抛出取消异常
                
                # 直接尝试执行函数
                return await func(*args, **kwargs)
            
            except asyncio.CancelledError:
                # 如果是取消异常，直接重新抛出，不进行重试
                logger.info("操作被取消，中断重试")
                raise
            
            except Exception as e:
                attempt += 1
                last_exception = e
                
                if attempt > self.max_retries:
                    logger.error(f"已达到最大异步重试次数 ({self.max_retries})，放弃操作")
                    break
                    
                logger.warning(f"操作失败 (尝试 {attempt}/{self.max_retries}): {e}")
        
        if last_exception:
            raise last_exception
        
        raise RuntimeError("所有重试都失败，但没有捕获到异常")
        
    def _get_wait_time(self, attempt):
        """计算重试等待时间，应用指数退避和随机抖动。"""
        wait_time = 1.0 * (self.backoff_factor ** attempt)
        jitter_amount = wait_time * self.jitter
        return wait_time + random.uniform(-jitter_amount, jitter_amount)


# 提供便捷函数用于创建带有默认参数的重试管理器
def create_retry_manager(max_retries: Optional[int] = None, 
                        timeout: Optional[int] = None) -> RetryManager:
    """
    创建重试管理器
    
    Args:
        max_retries: 最大重试次数，如果为None则使用默认值3
        timeout: 超时时间（秒），如果为None则使用默认值30
        
    Returns:
        重试管理器实例
    """
    max_retries = max_retries if max_retries is not None else 3
    timeout = timeout if timeout is not None else 30
    
    return RetryManager(max_retries=max_retries, timeout=timeout) 