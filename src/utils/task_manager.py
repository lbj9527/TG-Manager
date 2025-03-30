"""
任务管理系统模块，用于管理和控制异步任务
"""

import asyncio
import threading
import time
import uuid
from datetime import datetime
from enum import Enum, auto
from typing import Dict, List, Any, Optional, Callable, Coroutine, TypeVar, Generic, Union, Set, Tuple
import traceback

from src.utils.logger import get_logger
from src.utils.controls import TaskContext, CancelToken, PauseToken
from src.utils.events import EventEmitter
from src.utils.ui_state import UICallback, get_ui_callback

# 获取日志记录器
logger = get_logger()

# 任务结果泛型
T = TypeVar('T')

class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = auto()  # 等待执行
    RUNNING = auto()  # 正在执行
    PAUSED = auto()   # 暂停
    COMPLETED = auto() # 已完成
    FAILED = auto()   # 失败
    CANCELLED = auto() # 已取消


class TaskPriority(Enum):
    """任务优先级枚举"""
    LOW = 0       # 低优先级
    NORMAL = 1    # 普通优先级
    HIGH = 2      # 高优先级
    URGENT = 3    # 紧急优先级


class TaskGroup(Enum):
    """任务组枚举"""
    DOWNLOAD = "download"     # 下载任务
    UPLOAD = "upload"         # 上传任务
    FORWARD = "forward"       # 转发任务
    MONITOR = "monitor"       # 监控任务
    SYSTEM = "system"         # 系统任务
    OTHER = "other"           # 其他任务


class TaskInfo:
    """任务信息类，记录任务的基本信息和状态"""
    
    def __init__(self, 
                 task_id: str,
                 name: str,
                 group: TaskGroup = TaskGroup.OTHER,
                 priority: TaskPriority = TaskPriority.NORMAL,
                 description: str = "",
                 metadata: Dict[str, Any] = None):
        """
        初始化任务信息
        
        Args:
            task_id: 任务ID
            name: 任务名称
            group: 任务组
            priority: 任务优先级
            description: 任务描述
            metadata: 任务元数据
        """
        self.task_id = task_id
        self.name = name
        self.group = group
        self.priority = priority
        self.description = description
        self.metadata = metadata or {}
        
        # 任务状态相关
        self.status = TaskStatus.PENDING
        self.created_at = datetime.now()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.progress: float = 0.0
        self.progress_message: str = ""
        self.result: Any = None
        self.error: Optional[Exception] = None
        self.dependencies: Set[str] = set()  # 依赖的任务ID
        
        # 统计信息
        self.retry_count: int = 0
        self.pause_count: int = 0
        self.total_paused_time: float = 0.0
        self.last_pause_time: Optional[float] = None
    
    @property
    def running_time(self) -> float:
        """
        获取任务运行时间（秒）
        
        Returns:
            float: 运行时间
        """
        if not self.started_at:
            return 0.0
            
        end_time = self.completed_at or datetime.now()
        total_seconds = (end_time - self.started_at).total_seconds()
        
        # 减去暂停时间
        return total_seconds - self.total_paused_time
    
    @property
    def is_active(self) -> bool:
        """
        判断任务是否处于活动状态
        
        Returns:
            bool: 是否处于活动状态
        """
        return self.status in (TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.PAUSED)
    
    @property
    def is_finished(self) -> bool:
        """
        判断任务是否已完成（成功、失败或取消）
        
        Returns:
            bool: 是否已完成
        """
        return self.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典表示
        
        Returns:
            Dict[str, Any]: 字典表示
        """
        return {
            "task_id": self.task_id,
            "name": self.name,
            "group": self.group.value,
            "priority": self.priority.value,
            "description": self.description,
            "status": self.status.name,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "progress": self.progress,
            "progress_message": self.progress_message,
            "running_time": self.running_time,
            "retry_count": self.retry_count,
            "pause_count": self.pause_count,
            "is_active": self.is_active,
            "is_finished": self.is_finished,
            "error": str(self.error) if self.error else None,
            "metadata": self.metadata
        }
        
    def __str__(self) -> str:
        """字符串表示"""
        return f"Task[{self.task_id}] {self.name} ({self.status.name})"


class Task(Generic[T]):
    """任务类，表示一个异步任务"""
    
    def __init__(self, 
                 task_info: TaskInfo,
                 coro_factory: Callable[[], Coroutine],
                 task_context: Optional[TaskContext] = None,
                 on_progress: Optional[Callable[[float, str], None]] = None,
                 on_complete: Optional[Callable[[T], None]] = None,
                 on_error: Optional[Callable[[Exception], None]] = None,
                 on_cancel: Optional[Callable[[], None]] = None,
                 ui_callback: Optional[UICallback] = None):
        """
        初始化任务
        
        Args:
            task_info: 任务信息
            coro_factory: 协程工厂函数，返回要执行的协程
            task_context: 任务上下文
            on_progress: 进度回调
            on_complete: 完成回调
            on_error: 错误回调
            on_cancel: 取消回调
            ui_callback: UI回调
        """
        self.info = task_info
        self.coro_factory = coro_factory
        self.context = task_context or TaskContext()
        self.ui_callback = ui_callback or get_ui_callback()
        
        # 回调函数
        self.on_progress = on_progress
        self.on_complete = on_complete
        self.on_error = on_error
        self.on_cancel = on_cancel
        
        # 任务对象
        self.task: Optional[asyncio.Task] = None
        
        # 事件发射器
        self.events = EventEmitter()
    
    async def start(self) -> 'Task[T]':
        """
        启动任务
        
        Returns:
            Task: 任务实例自身
        """
        if self.task and not self.task.done():
            logger.warning(f"任务已在运行中: {self.info}")
            return self
        
        # 更新任务状态
        self.info.status = TaskStatus.RUNNING
        self.info.started_at = datetime.now() if not self.info.started_at else self.info.started_at
        
        # 通知状态更新
        self._notify_status_change()
        
        # 创建并启动任务
        self.task = asyncio.create_task(self._run_task())
        
        return self
    
    async def _run_task(self) -> Optional[T]:
        """
        运行任务
        
        Returns:
            Optional[T]: 任务结果
        """
        try:
            # 执行任务协程
            result = await self.coro_factory()
            
            # 更新任务状态
            self.info.status = TaskStatus.COMPLETED
            self.info.completed_at = datetime.now()
            self.info.result = result
            self.info.progress = 1.0
            self.info.progress_message = "任务完成"
            
            # 触发完成回调
            if self.on_complete:
                try:
                    self.on_complete(result)
                except Exception as e:
                    logger.error(f"任务完成回调出错: {e}")
            
            # 通知状态更新
            self._notify_status_change()
            self.events.emit("complete", result)
            
            # 通知UI回调
            if self.ui_callback:
                self.ui_callback.notify_complete(True, {
                    "task_id": self.info.task_id,
                    "name": self.info.name,
                    "result": result
                })
            
            return result
            
        except asyncio.CancelledError:
            # 任务被取消
            self.info.status = TaskStatus.CANCELLED
            self.info.completed_at = datetime.now()
            
            # 触发取消回调
            if self.on_cancel:
                try:
                    self.on_cancel()
                except Exception as e:
                    logger.error(f"任务取消回调出错: {e}")
            
            # 通知状态更新
            self._notify_status_change()
            self.events.emit("cancel")
            
            return None
            
        except Exception as e:
            # 任务出错
            self.info.status = TaskStatus.FAILED
            self.info.completed_at = datetime.now()
            self.info.error = e
            
            # 记录错误详情
            error_details = traceback.format_exc()
            logger.error(f"任务执行失败: {self.info.name}\n{error_details}")
            
            # 触发错误回调
            if self.on_error:
                try:
                    self.on_error(e)
                except Exception as callback_error:
                    logger.error(f"任务错误回调出错: {callback_error}")
            
            # 通知状态更新
            self._notify_status_change()
            self.events.emit("error", e)
            
            # 通知UI回调
            if self.ui_callback:
                self.ui_callback.show_error(
                    "任务出错", 
                    f"{self.info.name}执行失败: {str(e)}", 
                    error_details, 
                    False
                )
            
            return None
    
    def update_progress(self, progress: float, message: str = "") -> None:
        """
        更新任务进度
        
        Args:
            progress: 进度值（0.0-1.0）
            message: 进度消息
        """
        # 更新任务信息
        self.info.progress = progress
        self.info.progress_message = message
        
        # 触发进度回调
        if self.on_progress:
            try:
                self.on_progress(progress, message)
            except Exception as e:
                logger.error(f"任务进度回调出错: {e}")
        
        # 触发事件
        self.events.emit("progress", progress, message)
        
        # 通知UI回调
        if self.ui_callback:
            current = int(progress * 100)
            self.ui_callback.update_progress(current, 100, message)
    
    async def pause(self) -> bool:
        """
        暂停任务
        
        Returns:
            bool: 是否成功暂停
        """
        if not self.task or self.task.done():
            return False
            
        if self.info.status != TaskStatus.RUNNING:
            return False
            
        # 更新状态
        self.info.status = TaskStatus.PAUSED
        self.info.pause_count += 1
        self.info.last_pause_time = time.time()
        
        # 发送暂停信号
        self.context.pause_token.pause()
        
        # 通知状态更新
        self._notify_status_change()
        self.events.emit("pause")
        
        return True
    
    async def resume(self) -> bool:
        """
        恢复任务
        
        Returns:
            bool: 是否成功恢复
        """
        if not self.task or self.task.done():
            return False
            
        if self.info.status != TaskStatus.PAUSED:
            return False
            
        # 更新暂停时间统计
        if self.info.last_pause_time:
            self.info.total_paused_time += time.time() - self.info.last_pause_time
            self.info.last_pause_time = None
            
        # 更新状态
        self.info.status = TaskStatus.RUNNING
        
        # 发送恢复信号
        self.context.pause_token.resume()
        
        # 通知状态更新
        self._notify_status_change()
        self.events.emit("resume")
        
        return True
    
    async def cancel(self) -> bool:
        """
        取消任务
        
        Returns:
            bool: 是否成功取消
        """
        if not self.task or self.task.done():
            return False
            
        # 发送取消信号
        self.context.cancel_token.cancel()
        
        # 取消任务
        self.task.cancel()
        
        # 等待任务结束
        try:
            await self.task
        except asyncio.CancelledError:
            pass
            
        # 状态在_run_task中已更新
        return True
    
    def _notify_status_change(self) -> None:
        """通知任务状态变化"""
        self.events.emit("status_change", self.info.status, self.info)
    
    @property
    def result(self) -> Optional[T]:
        """获取任务结果"""
        return self.info.result
    
    @property
    def error(self) -> Optional[Exception]:
        """获取任务错误"""
        return self.info.error 