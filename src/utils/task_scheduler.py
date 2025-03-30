"""
任务调度器模块，用于管理和调度异步任务
"""

import asyncio
import threading
import heapq
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Coroutine, TypeVar, Generic, Union, Set, Tuple, Awaitable
from enum import Enum

from src.utils.logger import get_logger
from src.utils.controls import TaskContext, CancelToken, PauseToken
from src.utils.events import EventEmitter
from src.utils.ui_state import UICallback, get_ui_callback
from src.utils.task_manager import Task, TaskInfo, TaskStatus, TaskPriority, TaskGroup

# 获取日志记录器
logger = get_logger()

# 任务结果泛型
T = TypeVar('T')


class ScheduleMode(Enum):
    """任务调度模式"""
    FIFO = "fifo"        # 先进先出
    PRIORITY = "priority" # 按优先级
    FAIR = "fair"        # 公平调度（考虑优先级和等待时间）


class TaskScheduler(EventEmitter):
    """任务调度器，负责管理和调度异步任务"""
    
    def __init__(self, 
                max_concurrent_tasks: int = 5, 
                schedule_mode: ScheduleMode = ScheduleMode.FAIR,
                ui_callback: Optional[UICallback] = None):
        """
        初始化任务调度器
        
        Args:
            max_concurrent_tasks: 最大并发任务数
            schedule_mode: 调度模式
            ui_callback: UI回调
        """
        super().__init__()
        self.max_concurrent_tasks = max_concurrent_tasks
        self.schedule_mode = schedule_mode
        self.ui_callback = ui_callback or get_ui_callback()
        
        # 任务字典和队列
        self._tasks: Dict[str, Task] = {}
        self._pending_tasks: List[Tuple[int, int, str]] = []  # [(优先级, 创建时间戳, 任务ID)]
        self._running_tasks: Set[str] = set()
        
        # 运行标志和控制事件
        self._running = False
        self._scheduler_event = asyncio.Event()
        self._lock = threading.RLock()
        
        # 调度器任务
        self._scheduler_task: Optional[asyncio.Task] = None
        
        # 统计信息
        self.stats = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "cancelled_tasks": 0
        }
    
    async def start(self) -> None:
        """启动调度器"""
        if self._running:
            logger.warning("任务调度器已在运行")
            return
            
        self._running = True
        self._scheduler_event.set()
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        
        logger.info(f"任务调度器已启动，最大并发任务数: {self.max_concurrent_tasks}, 调度模式: {self.schedule_mode.value}")
        self.emit("status", "任务调度器已启动")
    
    async def stop(self) -> None:
        """停止调度器"""
        if not self._running:
            return
            
        self._running = False
        self._scheduler_event.set()
        
        if self._scheduler_task:
            await self._scheduler_task
            self._scheduler_task = None
            
        logger.info("任务调度器已停止")
        self.emit("status", "任务调度器已停止")
    
    async def _scheduler_loop(self) -> None:
        """调度器主循环"""
        try:
            while self._running:
                # 检查是否有空闲槽位运行任务
                await self._check_and_schedule_tasks()
                
                # 等待状态变化事件或超时
                try:
                    await asyncio.wait_for(self._scheduler_event.wait(), 1.0)
                    self._scheduler_event.clear()
                except asyncio.TimeoutError:
                    # 定期检查，即使没有事件
                    pass
        except Exception as e:
            logger.error(f"调度器循环异常: {e}")
            self.emit("error", f"调度器异常: {e}", "SCHEDULER", False)
        finally:
            self._running = False
    
    async def _check_and_schedule_tasks(self) -> None:
        """检查并调度任务"""
        with self._lock:
            # 计算可用槽位
            available_slots = self.max_concurrent_tasks - len(self._running_tasks)
            if available_slots <= 0 or not self._pending_tasks:
                return
                
            # 根据调度模式确保队列排序
            if self.schedule_mode == ScheduleMode.PRIORITY or self.schedule_mode == ScheduleMode.FAIR:
                # 保持堆排序
                heapq.heapify(self._pending_tasks)
            
            # 获取要启动的任务
            tasks_to_start = []
            while available_slots > 0 and self._pending_tasks:
                _, _, task_id = heapq.heappop(self._pending_tasks)
                if task_id in self._tasks:
                    tasks_to_start.append(task_id)
                    available_slots -= 1
        
        # 启动任务
        for task_id in tasks_to_start:
            task = self._tasks.get(task_id)
            if task and task.info.status == TaskStatus.PENDING:
                await self._start_task(task)
    
    async def _start_task(self, task: Task) -> None:
        """启动任务"""
        try:
            with self._lock:
                if task.info.task_id in self._running_tasks:
                    return
                    
                self._running_tasks.add(task.info.task_id)
            
            # 启动任务
            await task.start()
            
            # 监听任务状态变化
            def on_task_finished(_):
                asyncio.create_task(self._on_task_finished(task.info.task_id))
                
            task.events.on("complete", on_task_finished)
            task.events.on("error", lambda _: on_task_finished(None))
            task.events.on("cancel", lambda: on_task_finished(None))
            
            logger.info(f"任务已启动: {task.info.name} [{task.info.task_id}]")
            self.emit("task_started", task.info.task_id, task.info.name)
            
        except Exception as e:
            logger.error(f"启动任务失败: {task.info.name} [{task.info.task_id}], 错误: {e}")
            # 移除运行任务集合中的任务
            with self._lock:
                self._running_tasks.discard(task.info.task_id)
            
            # 激活调度器重新检查
            self._scheduler_event.set()
    
    async def _on_task_finished(self, task_id: str) -> None:
        """任务完成时的处理"""
        task = self._tasks.get(task_id)
        if not task:
            return
            
        # 更新统计信息
        if task.info.status == TaskStatus.COMPLETED:
            self.stats["completed_tasks"] += 1
        elif task.info.status == TaskStatus.FAILED:
            self.stats["failed_tasks"] += 1
        elif task.info.status == TaskStatus.CANCELLED:
            self.stats["cancelled_tasks"] += 1
        
        # 从运行任务集合中移除
        with self._lock:
            self._running_tasks.discard(task_id)
        
        # 触发事件
        self.emit("task_finished", task_id, task.info.status)
        
        # 记录日志
        status_str = task.info.status.name
        logger.info(f"任务已结束: {task.info.name} [{task.info.task_id}], 状态: {status_str}")
        
        # 激活调度器检查新任务
        self._scheduler_event.set()
    
    def create_task(self, 
                  name: str,
                  coro_factory: Callable[[], Coroutine],
                  group: TaskGroup = TaskGroup.OTHER,
                  priority: TaskPriority = TaskPriority.NORMAL,
                  description: str = "",
                  metadata: Dict[str, Any] = None,
                  task_context: Optional[TaskContext] = None,
                  on_progress: Optional[Callable[[float, str], None]] = None,
                  on_complete: Optional[Callable[[Any], None]] = None,
                  on_error: Optional[Callable[[Exception], None]] = None,
                  on_cancel: Optional[Callable[[], None]] = None) -> str:
        """
        创建任务
        
        Args:
            name: 任务名称
            coro_factory: 协程工厂函数
            group: 任务组
            priority: 优先级
            description: 描述
            metadata: 元数据
            task_context: 任务上下文
            on_progress: 进度回调
            on_complete: 完成回调
            on_error: 错误回调
            on_cancel: 取消回调
            
        Returns:
            str: 任务ID
        """
        # 生成任务ID
        task_id = str(uuid.uuid4())
        
        # 创建任务信息
        task_info = TaskInfo(
            task_id=task_id,
            name=name,
            group=group,
            priority=priority,
            description=description,
            metadata=metadata or {}
        )
        
        # 创建任务上下文（如果没有提供）
        if not task_context:
            task_context = TaskContext()
        
        # 创建任务对象
        task = Task(
            task_info=task_info,
            coro_factory=coro_factory,
            task_context=task_context,
            on_progress=on_progress,
            on_complete=on_complete,
            on_error=on_error,
            on_cancel=on_cancel,
            ui_callback=self.ui_callback
        )
        
        # 添加到任务字典
        with self._lock:
            self._tasks[task_id] = task
            
            # 添加到待处理队列
            task_priority = 0 - task_info.priority.value  # 负值使高优先级在堆顶
            created_timestamp = int(datetime.now().timestamp())
            heapq.heappush(self._pending_tasks, (task_priority, created_timestamp, task_id))
            
            self.stats["total_tasks"] += 1
        
        # 触发事件
        self.emit("task_created", task_id, name)
        logger.info(f"任务已创建: {name} [{task_id}], 优先级: {priority.name}")
        
        # 激活调度器检查新任务
        self._scheduler_event.set()
        
        return task_id
    
    async def cancel_task(self, task_id: str) -> bool:
        """
        取消任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功取消
        """
        task = self._tasks.get(task_id)
        if not task:
            return False
            
        # 如果任务已完成或已取消，直接返回
        if task.info.is_finished:
            return False
            
        # 如果任务还在待处理队列中，从队列中移除
        with self._lock:
            for i, (_, _, tid) in enumerate(self._pending_tasks):
                if tid == task_id:
                    self._pending_tasks.pop(i)
                    task.info.status = TaskStatus.CANCELLED
                    task.info.completed_at = datetime.now()
                    
                    # 触发事件
                    self.emit("task_cancelled", task_id, task.info.name)
                    logger.info(f"待处理任务已取消: {task.info.name} [{task_id}]")
                    
                    # 更新统计信息
                    self.stats["cancelled_tasks"] += 1
                    
                    # 维护堆属性
                    heapq.heapify(self._pending_tasks)
                    return True
        
        # 任务已经在运行，调用其取消方法
        result = await task.cancel()
        
        if result:
            self.emit("task_cancelled", task_id, task.info.name)
            logger.info(f"运行中任务已取消: {task.info.name} [{task_id}]")
            
        return result
    
    async def pause_task(self, task_id: str) -> bool:
        """
        暂停任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功暂停
        """
        task = self._tasks.get(task_id)
        if not task:
            return False
            
        result = await task.pause()
        
        if result:
            self.emit("task_paused", task_id, task.info.name)
            logger.info(f"任务已暂停: {task.info.name} [{task_id}]")
            
        return result
    
    async def resume_task(self, task_id: str) -> bool:
        """
        恢复任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功恢复
        """
        task = self._tasks.get(task_id)
        if not task:
            return False
            
        result = await task.resume()
        
        if result:
            self.emit("task_resumed", task_id, task.info.name)
            logger.info(f"任务已恢复: {task.info.name} [{task_id}]")
            
        return result
    
    def get_task_info(self, task_id: str) -> Optional[TaskInfo]:
        """
        获取任务信息
        
        Args:
            task_id: 任务ID
            
        Returns:
            Optional[TaskInfo]: 任务信息
        """
        task = self._tasks.get(task_id)
        return task.info if task else None
    
    def get_all_tasks(self) -> Dict[str, TaskInfo]:
        """
        获取所有任务信息
        
        Returns:
            Dict[str, TaskInfo]: 任务ID到任务信息的映射
        """
        return {task_id: task.info for task_id, task in self._tasks.items()}
    
    def get_tasks_by_status(self, status: TaskStatus) -> Dict[str, TaskInfo]:
        """
        按状态获取任务信息
        
        Args:
            status: 任务状态
            
        Returns:
            Dict[str, TaskInfo]: 任务ID到任务信息的映射
        """
        return {task_id: task.info for task_id, task in self._tasks.items() 
                if task.info.status == status}
    
    def get_tasks_by_group(self, group: TaskGroup) -> Dict[str, TaskInfo]:
        """
        按组获取任务信息
        
        Args:
            group: 任务组
            
        Returns:
            Dict[str, TaskInfo]: 任务ID到任务信息的映射
        """
        return {task_id: task.info for task_id, task in self._tasks.items() 
                if task.info.group == group}
    
    def clear_finished_tasks(self) -> int:
        """
        清理已完成的任务
        
        Returns:
            int: 清理的任务数量
        """
        with self._lock:
            # 查找已完成任务
            finished_tasks = [task_id for task_id, task in self._tasks.items() 
                             if task.info.is_finished]
            
            # 移除任务
            for task_id in finished_tasks:
                del self._tasks[task_id]
                
            return len(finished_tasks)
    
    async def set_max_concurrent_tasks(self, count: int) -> None:
        """
        设置最大并发任务数
        
        Args:
            count: 最大并发任务数
        """
        if count < 1:
            count = 1
            
        self.max_concurrent_tasks = count
        logger.info(f"最大并发任务数已设置为: {count}")
        
        # 激活调度器重新检查
        self._scheduler_event.set()
    
    def set_schedule_mode(self, mode: ScheduleMode) -> None:
        """
        设置调度模式
        
        Args:
            mode: 调度模式
        """
        self.schedule_mode = mode
        logger.info(f"调度模式已设置为: {mode.value}")
        
        # 如果是优先级模式或公平模式，需要重新排序队列
        if mode == ScheduleMode.PRIORITY or mode == ScheduleMode.FAIR:
            with self._lock:
                heapq.heapify(self._pending_tasks)
                
        # 激活调度器重新检查
        self._scheduler_event.set()


# 全局任务调度器实例
_global_task_scheduler: Optional[TaskScheduler] = None

def get_task_scheduler() -> TaskScheduler:
    """
    获取全局任务调度器实例
    
    Returns:
        TaskScheduler: 全局任务调度器实例
    """
    global _global_task_scheduler
    if _global_task_scheduler is None:
        _global_task_scheduler = TaskScheduler()
    return _global_task_scheduler

async def init_task_scheduler(max_concurrent_tasks: int = 5, 
                           schedule_mode: ScheduleMode = ScheduleMode.FAIR) -> TaskScheduler:
    """
    初始化全局任务调度器
    
    Args:
        max_concurrent_tasks: 最大并发任务数
        schedule_mode: 调度模式
    
    Returns:
        TaskScheduler: 全局任务调度器实例
    """
    scheduler = get_task_scheduler()
    scheduler.max_concurrent_tasks = max_concurrent_tasks
    scheduler.schedule_mode = schedule_mode
    await scheduler.start()
    return scheduler 