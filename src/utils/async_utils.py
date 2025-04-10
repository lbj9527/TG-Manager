"""
TG-Manager 异步操作工具模块
提供统一的异步操作接口和错误处理
"""

import asyncio
import sys
from functools import wraps
from typing import Callable, Any, Coroutine, TypeVar, Optional, Dict, Union
from loguru import logger

# 删除QtAsyncio，导入qasync
import qasync
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

T = TypeVar('T')

# 保存qasync的事件循环引用
_loop = None

def get_event_loop():
    """获取事件循环
    
    获取qasync事件循环，如果不可用则回退到标准asyncio
    
    Returns:
        事件循环
    """
    global _loop
    try:
        if _loop is not None:
            return _loop
        _loop = qasync.QEventLoop()
        return _loop
    except (ImportError, AttributeError) as e:
        logger.warning(f"qasync获取事件循环失败，退回到标准asyncio: {e}")
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.get_event_loop()

def create_task(coro: Coroutine) -> asyncio.Task:
    """创建异步任务
    
    使用qasync创建异步任务，并添加全局异常处理
    
    Args:
        coro: 协程对象
        
    Returns:
        asyncio.Task: 已创建的任务
    """
    try:
        loop = get_event_loop()
        task = loop.create_task(coro)
        task.add_done_callback(_handle_task_exception)
        return task
    except AttributeError as e:
        # 如果qasync事件循环不可用，退回到标准asyncio
        logger.warning(f"qasync创建任务失败，退回到标准asyncio: {e}")
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

class AsyncTaskManager:
    """异步任务管理器，用于管理和控制异步任务"""
    
    def __init__(self):
        """初始化任务管理器"""
        self.tasks: Dict[str, asyncio.Task] = {}
        self.active = True
    
    def add_task(self, name: str, coro: Coroutine) -> asyncio.Task:
        """添加并启动一个新任务
        
        Args:
            name: 任务名称
            coro: 协程对象
        
        Returns:
            asyncio.Task: 创建的任务
        """
        # 如果同名任务已存在，先取消它
        self.cancel_task(name)
        
        # 创建新任务
        task = create_task(coro)
        # 设置任务名称（如果可用）
        try:
            task.set_name(name)
        except AttributeError:
            # Python 3.7以下版本不支持set_name
            pass
            
        self.tasks[name] = task
        
        # 添加完成回调以自动清理
        task.add_done_callback(lambda t: self._on_task_done(name, t))
        
        return task
    
    def cancel_task(self, name: str) -> bool:
        """取消指定名称的任务
        
        Args:
            name: 任务名称
        
        Returns:
            bool: 是否成功取消任务
        """
        if name in self.tasks:
            task = self.tasks[name]
            if not task.done() and not task.cancelled():
                task.cancel()
                return True
        return False
    
    def cancel_all_tasks(self) -> None:
        """取消所有任务"""
        for name in list(self.tasks.keys()):
            self.cancel_task(name)
    
    def get_task(self, name: str) -> Optional[asyncio.Task]:
        """获取指定名称的任务
        
        Args:
            name: 任务名称
        
        Returns:
            Optional[asyncio.Task]: 任务对象，如果不存在则返回None
        """
        return self.tasks.get(name)
    
    def is_task_running(self, name: str) -> bool:
        """检查指定任务是否正在运行
        
        Args:
            name: 任务名称
        
        Returns:
            bool: 任务是否正在运行
        """
        task = self.get_task(name)
        return task is not None and not task.done() and not task.cancelled()
    
    def _on_task_done(self, name: str, task: asyncio.Task) -> None:
        """任务完成回调函数
        
        Args:
            name: 任务名称
            task: 完成的任务
        """
        # 从字典中移除任务
        if name in self.tasks:
            del self.tasks[name]
        
        # 检查任务是否有异常
        if not task.cancelled():
            try:
                exc = task.exception()
                if exc:
                    logger.error(f"任务 '{name}' 执行出错: {exc}")
                    # 导入traceback模块
                    import traceback
                    formatted_tb = traceback.format_exc()
                    logger.debug(f"错误详情:\n{formatted_tb}")
            except asyncio.CancelledError:
                pass  # 忽略已取消的任务
            except asyncio.InvalidStateError:
                pass  # 忽略无效状态
    
    def shutdown(self) -> None:
        """关闭任务管理器，取消所有任务"""
        self.active = False
        self.cancel_all_tasks()

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

def time() -> float:
    """获取时间
    
    返回当前事件循环的时间
    
    Returns:
        浮点型时间
    """
    try:
        return get_event_loop().time()
    except (ImportError, AttributeError):
        try:
            return asyncio.get_running_loop().time()
        except RuntimeError:
            return asyncio.get_event_loop().time()

# 新增函数：初始化qasync事件循环
def init_qasync_loop():
    """初始化qasync事件循环
    
    在Qt应用程序启动前调用此函数初始化qasync事件循环
    """
    global _loop
    try:
        _loop = qasync.QEventLoop()
        asyncio.set_event_loop(_loop)
        return _loop
    except Exception as e:
        logger.error(f"初始化qasync事件循环失败: {e}")
        raise

# 新增函数：运行Qt应用和asyncio事件循环
def run_qt_asyncio(app, main_coro_func):
    """运行Qt应用和asyncio事件循环
    
    Args:
        app: Qt应用实例或包含app属性的应用程序对象
        main_coro_func: 主协程函数（不是协程对象）
        
    Returns:
        应用退出代码
    """
    try:
        # 检查app是否为QApplication实例，如果不是，尝试获取其app属性
        if not isinstance(app, QApplication) and hasattr(app, 'app') and isinstance(app.app, QApplication):
            qt_app = app.app
            logger.debug("使用app对象的app属性作为QApplication实例")
        else:
            qt_app = app
            logger.debug("直接使用传入的对象作为QApplication实例")
        
        # 创建qasync事件循环
        loop = qasync.QEventLoop(qt_app)
        asyncio.set_event_loop(loop)
        
        # 设置全局_loop变量
        global _loop
        _loop = loop
        
        # 创建关闭事件
        app_close_event = asyncio.Event()
        qt_app.aboutToQuit.connect(app_close_event.set)
        
        # 创建主任务
        loop.create_task(main_coro_func())
        
        # 运行事件循环直到应用关闭
        with loop:
            return loop.run_until_complete(app_close_event.wait())
    except Exception as e:
        logger.error(f"运行qasync事件循环失败: {e}")
        raise 