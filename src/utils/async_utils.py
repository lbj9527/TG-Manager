"""
TG-Manager 异步操作工具模块
提供统一的异步操作接口和错误处理
"""

import asyncio
import PySide6.QtAsyncio as QtAsyncio
from functools import wraps
from typing import Callable, Any, Coroutine, TypeVar
from loguru import logger

T = TypeVar('T')

def create_task(coro: Coroutine) -> asyncio.Task:
    """创建异步任务
    
    使用QtAsyncio创建异步任务，并添加全局异常处理
    
    Args:
        coro: 协程对象
        
    Returns:
        asyncio.Task: 已创建的任务
    """
    try:
        task = QtAsyncio.asyncio.create_task(coro)
        task.add_done_callback(_handle_task_exception)
        return task
    except AttributeError as e:
        # 如果QtAsyncio不可用，退回到标准asyncio
        logger.warning(f"QtAsyncio创建任务失败，退回到标准asyncio: {e}")
        try:
            task = asyncio.create_task(coro)
            task.add_done_callback(_handle_task_exception)
            return task
        except RuntimeError:
            # 如果没有正在运行的事件循环，使用get_event_loop
            loop = asyncio.get_event_loop()
            task = loop.create_task(coro)
            task.add_done_callback(_handle_task_exception)
            return task

def _handle_task_exception(task):
    """处理任务异常
    
    Args:
        task: 异步任务
    """
    try:
        # 检查任务状态
        if task.cancelled():
            return
        
        # 获取异常（如果有）
        exception = task.exception()
        if exception:
            logger.error(f"异步任务出错: {exception}")
            # 异常详情记录到日志
            import traceback
            formatted_tb = ''.join(traceback.format_exception(
                type(exception), exception, exception.__traceback__))
            logger.debug(f"异常详情:\n{formatted_tb}")
    except asyncio.CancelledError:
        # 忽略取消错误
        pass
    except Exception as e:
        logger.error(f"处理任务异常时出错: {e}")

def qt_connect_async(signal, coro_func: Callable[..., Coroutine[Any, Any, T]]):
    """将Qt信号连接到异步函数
    
    Args:
        signal: Qt信号
        coro_func: 异步函数
        
    Returns:
        连接函数
    """
    @wraps(coro_func)
    def slot(*args, **kwargs):
        create_task(coro_func(*args, **kwargs))
    
    signal.connect(slot)
    return slot

async def safe_sleep(seconds: float) -> None:
    """安全的异步睡眠
    
    不会在取消时引发异常
    
    Args:
        seconds: 睡眠秒数
    """
    try:
        await asyncio.sleep(seconds)
    except asyncio.CancelledError:
        # 静默处理取消
        raise

class AsyncTimer:
    """异步定时器
    
    定期执行异步任务
    """
    def __init__(self, interval: float, callback: Callable[[], Coroutine]):
        """初始化
        
        Args:
            interval: 间隔时间（秒）
            callback: 要执行的异步回调函数
        """
        self.interval = interval
        self.callback = callback
        self.task = None
        self.running = False
        
    async def _timer_loop(self):
        """定时器循环"""
        self.running = True
        try:
            while self.running:
                await self.callback()
                await safe_sleep(self.interval)
        except asyncio.CancelledError:
            self.running = False
            raise
        finally:
            self.running = False
    
    def start(self):
        """启动定时器"""
        if not self.running:
            self.task = create_task(self._timer_loop())
    
    def stop(self):
        """停止定时器"""
        if self.running and self.task:
            self.running = False
            self.task.cancel()

def as_task(coro_func: Callable[..., Coroutine[Any, Any, T]]):
    """装饰器：将协程函数包装为自动创建任务
    
    用于装饰那些需要在调用时自动创建任务的协程函数
    
    Args:
        coro_func: 协程函数
        
    Returns:
        装饰后的函数，调用时自动创建任务
    """
    @wraps(coro_func)
    def wrapper(*args, **kwargs):
        return create_task(coro_func(*args, **kwargs))
    return wrapper

async def gather_with_concurrency(n: int, *tasks):
    """限制并发数量的gather
    
    类似于asyncio.gather，但限制同时运行的任务数量
    
    Args:
        n: 最大并发任务数
        tasks: 要执行的任务列表
        
    Returns:
        任务结果列表
    """
    semaphore = asyncio.Semaphore(n)
    
    async def sem_task(task):
        async with semaphore:
            return await task
    
    return await asyncio.gather(*(sem_task(task) for task in tasks))

def get_event_loop():
    """获取事件循环
    
    尝试获取QtAsyncio事件循环，如果不可用则回退到标准asyncio
    
    Returns:
        事件循环
    """
    try:
        return QtAsyncio.asyncio.get_event_loop()
    except (ImportError, AttributeError) as e:
        logger.warning(f"QtAsyncio获取事件循环失败，退回到标准asyncio: {e}")
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.get_event_loop()

def time() -> float:
    """获取时间
    
    返回当前事件循环的时间
    
    Returns:
        浮点型时间
    """
    try:
        return QtAsyncio.asyncio.get_event_loop().time()
    except (ImportError, AttributeError):
        try:
            return asyncio.get_running_loop().time()
        except RuntimeError:
            return asyncio.get_event_loop().time() 