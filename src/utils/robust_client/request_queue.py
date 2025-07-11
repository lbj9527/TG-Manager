"""
强壮Telegram客户端 - 请求队列管理模块
负责并发控制、请求优先级管理和线程池支持
"""

import asyncio
import time
from typing import Dict, Any, Optional, Callable, Awaitable, Union
from enum import Enum, IntEnum
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
import threading

from src.utils.logger import get_logger

logger = get_logger()


class RequestPriority(IntEnum):
    """请求优先级"""
    CRITICAL = 1    # 关键请求（如认证）
    HIGH = 2        # 高优先级（如用户操作）
    NORMAL = 3      # 普通优先级（如消息发送）
    LOW = 4         # 低优先级（如批量操作）
    BACKGROUND = 5  # 后台任务


class RequestType(Enum):
    """请求类型"""
    AUTH = "auth"                   # 认证请求
    MESSAGE = "message"             # 消息相关
    MEDIA = "media"                 # 媒体相关
    CHANNEL = "channel"             # 频道相关
    USER = "user"                   # 用户相关
    FILE = "file"                   # 文件操作
    ADMIN = "admin"                 # 管理操作
    BATCH = "batch"                 # 批量操作


@dataclass
class QueuedRequest:
    """队列中的请求"""
    request_id: str
    func: Callable[..., Awaitable[Any]]
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    priority: RequestPriority = RequestPriority.NORMAL
    request_type: RequestType = RequestType.MESSAGE
    timeout: float = 30.0
    max_retries: int = 3
    retry_count: int = 0
    created_time: float = field(default_factory=time.time)
    context: str = "unknown"
    
    def __lt__(self, other):
        """用于优先级队列排序"""
        if not isinstance(other, QueuedRequest):
            return NotImplemented
        return (self.priority.value, self.created_time) < (other.priority.value, other.created_time)


@dataclass
class RequestResult:
    """请求结果"""
    request_id: str
    success: bool
    result: Any = None
    error: Optional[Exception] = None
    execution_time: float = 0.0
    retry_count: int = 0


class RequestStats:
    """请求统计"""
    
    def __init__(self):
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.retried_requests = 0
        self.average_execution_time = 0.0
        self.requests_by_type: Dict[RequestType, int] = {}
        self.requests_by_priority: Dict[RequestPriority, int] = {}
        self._lock = threading.Lock()
    
    def record_request(self, request: QueuedRequest, result: RequestResult):
        """记录请求统计"""
        with self._lock:
            self.total_requests += 1
            
            if result.success:
                self.successful_requests += 1
            else:
                self.failed_requests += 1
            
            if result.retry_count > 0:
                self.retried_requests += 1
            
            # 更新平均执行时间
            self.average_execution_time = (
                (self.average_execution_time * (self.total_requests - 1) + result.execution_time)
                / self.total_requests
            )
            
            # 按类型统计
            self.requests_by_type[request.request_type] = (
                self.requests_by_type.get(request.request_type, 0) + 1
            )
            
            # 按优先级统计
            self.requests_by_priority[request.priority] = (
                self.requests_by_priority.get(request.priority, 0) + 1
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            return {
                "total_requests": self.total_requests,
                "successful_requests": self.successful_requests,
                "failed_requests": self.failed_requests,
                "retried_requests": self.retried_requests,
                "success_rate": self.successful_requests / max(1, self.total_requests),
                "average_execution_time": self.average_execution_time,
                "requests_by_type": dict(self.requests_by_type),
                "requests_by_priority": dict(self.requests_by_priority)
            }
    
    def reset(self):
        """重置统计"""
        with self._lock:
            self.total_requests = 0
            self.successful_requests = 0
            self.failed_requests = 0
            self.retried_requests = 0
            self.average_execution_time = 0.0
            self.requests_by_type.clear()
            self.requests_by_priority.clear()


class RateLimiter:
    """速率限制器"""
    
    def __init__(self, max_requests: int, time_window: float):
        """
        初始化速率限制器
        
        Args:
            max_requests: 时间窗口内最大请求数
            time_window: 时间窗口（秒）
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """获取请求许可"""
        async with self._lock:
            now = time.time()
            
            # 清除过期的请求记录
            self.requests = [req_time for req_time in self.requests if now - req_time < self.time_window]
            
            # 检查是否超过限制
            if len(self.requests) >= self.max_requests:
                # 计算需要等待的时间
                oldest_request = min(self.requests)
                wait_time = self.time_window - (now - oldest_request)
                
                if wait_time > 0:
                    logger.debug(f"速率限制，等待 {wait_time:.2f} 秒")
                    await asyncio.sleep(wait_time)
                    return await self.acquire()  # 递归重试
            
            # 记录请求时间
            self.requests.append(now)


class RequestQueueManager:
    """请求队列管理器"""
    
    def __init__(self, 
                 max_concurrent_requests: int = 10,
                 max_queue_size: int = 1000,
                 default_timeout: float = 30.0,
                 rate_limit_requests: int = 30,
                 rate_limit_window: float = 60.0):
        """
        初始化请求队列管理器
        
        Args:
            max_concurrent_requests: 最大并发请求数
            max_queue_size: 最大队列大小
            default_timeout: 默认超时时间
            rate_limit_requests: 速率限制请求数
            rate_limit_window: 速率限制时间窗口
        """
        self.max_concurrent_requests = max_concurrent_requests
        self.max_queue_size = max_queue_size
        self.default_timeout = default_timeout
        
        # 请求队列
        self.request_queue = asyncio.PriorityQueue(maxsize=max_queue_size)
        self.active_requests: Dict[str, asyncio.Task] = {}
        self.pending_results: Dict[str, asyncio.Future] = {}
        
        # 控制信号
        self._running = False
        self._worker_tasks: list = []
        self._semaphore = asyncio.Semaphore(max_concurrent_requests)
        
        # 统计和限流
        self.stats = RequestStats()
        self.rate_limiter = RateLimiter(rate_limit_requests, rate_limit_window)
        
        # 线程池
        self.thread_pool = ThreadPoolExecutor(max_workers=max_concurrent_requests)
        
        # 回调函数
        self.on_request_completed: Optional[Callable[[QueuedRequest, RequestResult], None]] = None
        self.on_queue_full: Optional[Callable[[], None]] = None
        
        logger.info(f"请求队列管理器已初始化 (最大并发: {max_concurrent_requests})")
    
    async def start(self):
        """启动请求队列处理"""
        if self._running:
            return
        
        self._running = True
        
        # 启动工作协程
        for i in range(self.max_concurrent_requests):
            task = asyncio.create_task(self._worker(f"worker-{i}"))
            self._worker_tasks.append(task)
        
        logger.info(f"已启动 {len(self._worker_tasks)} 个请求处理工作协程")
    
    async def stop(self):
        """停止请求队列处理"""
        if not self._running:
            return
        
        self._running = False
        
        # 取消所有工作任务
        for task in self._worker_tasks:
            task.cancel()
        
        # 等待所有任务完成
        if self._worker_tasks:
            await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        
        # 取消所有活跃请求
        for request_id, task in self.active_requests.items():
            task.cancel()
        
        # 关闭线程池
        self.thread_pool.shutdown(wait=False)
        
        logger.info("请求队列管理器已停止")
    
    async def submit_request(self,
                            func: Callable[..., Awaitable[Any]],
                            *args,
                            request_id: Optional[str] = None,
                            priority: RequestPriority = RequestPriority.NORMAL,
                            request_type: RequestType = RequestType.MESSAGE,
                            timeout: float = None,
                            max_retries: int = 3,
                            context: str = "unknown",
                            **kwargs) -> str:
        """
        提交请求到队列
        
        Args:
            func: 要执行的异步函数
            *args: 函数位置参数
            request_id: 请求ID（可选）
            priority: 请求优先级
            request_type: 请求类型
            timeout: 超时时间
            max_retries: 最大重试次数
            context: 上下文信息
            **kwargs: 函数关键字参数
            
        Returns:
            str: 请求ID
        """
        if not self._running:
            raise RuntimeError("请求队列管理器未启动")
        
        # 生成请求ID
        if request_id is None:
            request_id = f"{int(time.time() * 1000000)}"
        
        # 创建请求对象
        request = QueuedRequest(
            request_id=request_id,
            func=func,
            args=args,
            kwargs=kwargs,
            priority=priority,
            request_type=request_type,
            timeout=timeout or self.default_timeout,
            max_retries=max_retries,
            context=context
        )
        
        # 创建结果Future
        future = asyncio.Future()
        self.pending_results[request_id] = future
        
        try:
            # 将请求加入队列
            self.request_queue.put_nowait(request)
            logger.debug(f"请求已加入队列: {request_id} (优先级: {priority.name})")
            
        except asyncio.QueueFull:
            logger.error("请求队列已满")
            future.set_exception(RuntimeError("请求队列已满"))
            
            if self.on_queue_full:
                try:
                    self.on_queue_full()
                except Exception as e:
                    logger.error(f"队列满回调执行失败: {e}")
        
        return request_id
    
    async def get_result(self, request_id: str, timeout: float = None) -> RequestResult:
        """
        获取请求结果
        
        Args:
            request_id: 请求ID
            timeout: 等待超时时间
            
        Returns:
            RequestResult: 请求结果
        """
        if request_id not in self.pending_results:
            raise ValueError(f"未知的请求ID: {request_id}")
        
        future = self.pending_results[request_id]
        
        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            logger.error(f"等待请求结果超时: {request_id}")
            raise
        finally:
            # 清理Future
            if request_id in self.pending_results:
                del self.pending_results[request_id]
    
    async def execute_request(self,
                            func: Callable[..., Awaitable[Any]],
                            *args,
                            priority: RequestPriority = RequestPriority.NORMAL,
                            request_type: RequestType = RequestType.MESSAGE,
                            timeout: float = None,
                            max_retries: int = 3,
                            context: str = "unknown",
                            **kwargs) -> Any:
        """
        执行请求并等待结果
        
        Args:
            func: 要执行的异步函数
            *args: 函数位置参数
            priority: 请求优先级
            request_type: 请求类型
            timeout: 超时时间
            max_retries: 最大重试次数
            context: 上下文信息
            **kwargs: 函数关键字参数
            
        Returns:
            Any: 请求结果
        """
        request_id = await self.submit_request(
            func, *args,
            priority=priority,
            request_type=request_type,
            timeout=timeout,
            max_retries=max_retries,
            context=context,
            **kwargs
        )
        
        result = await self.get_result(request_id, timeout=timeout)
        
        if not result.success:
            raise result.error or RuntimeError("请求执行失败")
        
        return result.result
    
    async def _worker(self, worker_name: str):
        """工作协程"""
        logger.debug(f"请求处理工作协程 {worker_name} 已启动")
        
        while self._running:
            try:
                # 从队列获取请求
                request = await self.request_queue.get()
                
                # 执行请求
                await self._execute_single_request(request)
                
                # 标记任务完成
                self.request_queue.task_done()
                
            except asyncio.CancelledError:
                logger.debug(f"工作协程 {worker_name} 已取消")
                break
            except Exception as e:
                logger.error(f"工作协程 {worker_name} 发生错误: {e}")
    
    async def _execute_single_request(self, request: QueuedRequest):
        """执行单个请求"""
        start_time = time.time()
        
        try:
            # 应用速率限制
            await self.rate_limiter.acquire()
            
            # 获取信号量
            async with self._semaphore:
                # 执行请求
                result = await asyncio.wait_for(
                    request.func(*request.args, **request.kwargs),
                    timeout=request.timeout
                )
                
                # 创建成功结果
                execution_time = time.time() - start_time
                request_result = RequestResult(
                    request_id=request.request_id,
                    success=True,
                    result=result,
                    execution_time=execution_time,
                    retry_count=request.retry_count
                )
                
        except Exception as e:
            logger.error(f"请求执行失败: {request.request_id}, 错误: {e}")
            
            # 创建失败结果
            execution_time = time.time() - start_time
            request_result = RequestResult(
                request_id=request.request_id,
                success=False,
                error=e,
                execution_time=execution_time,
                retry_count=request.retry_count
            )
        
        # 记录统计
        self.stats.record_request(request, request_result)
        
        # 设置结果
        if request.request_id in self.pending_results:
            future = self.pending_results[request.request_id]
            if not future.done():
                future.set_result(request_result)
        
        # 调用完成回调
        if self.on_request_completed:
            try:
                self.on_request_completed(request, request_result)
            except Exception as callback_error:
                logger.error(f"请求完成回调执行失败: {callback_error}")
    
    def get_queue_status(self) -> Dict[str, Any]:
        """获取队列状态"""
        return {
            "running": self._running,
            "queue_size": self.request_queue.qsize(),
            "max_queue_size": self.max_queue_size,
            "active_requests": len(self.active_requests),
            "max_concurrent_requests": self.max_concurrent_requests,
            "pending_results": len(self.pending_results),
            "stats": self.stats.get_stats()
        }
    
    def clear_queue(self):
        """清空队列"""
        while not self.request_queue.empty():
            try:
                self.request_queue.get_nowait()
                self.request_queue.task_done()
            except asyncio.QueueEmpty:
                break
        
        logger.info("请求队列已清空")
    
    def reset_stats(self):
        """重置统计"""
        self.stats.reset()
        logger.debug("请求队列统计已重置") 