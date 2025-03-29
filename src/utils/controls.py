"""
控制类模块，提供任务控制相关的类和工具
"""

import threading
import asyncio
from typing import Optional, Dict, Any

class CancelToken:
    """
    取消令牌类，用于取消异步操作
    """
    
    def __init__(self):
        """初始化取消令牌"""
        self._is_cancelled = False
        self._lock = threading.Lock()
        
    @property
    def is_cancelled(self) -> bool:
        """
        获取是否已取消
        
        Returns:
            是否已取消
        """
        with self._lock:
            return self._is_cancelled
            
    def cancel(self) -> None:
        """
        标记为已取消
        """
        with self._lock:
            self._is_cancelled = True
            
    def reset(self) -> None:
        """
        重置取消状态
        """
        with self._lock:
            self._is_cancelled = False
            
    def __bool__(self) -> bool:
        """
        允许直接在if语句中使用
        
        Returns:
            是否已取消
        """
        return self.is_cancelled

class PauseToken:
    """
    暂停令牌类，用于暂停/恢复异步操作
    """
    
    def __init__(self, paused: bool = False):
        """
        初始化暂停令牌
        
        Args:
            paused: 初始是否为暂停状态
        """
        self._paused = paused
        self._event = asyncio.Event()
        if not paused:
            self._event.set()
        
    @property
    def is_paused(self) -> bool:
        """
        获取是否处于暂停状态
        
        Returns:
            是否处于暂停状态
        """
        return not self._event.is_set()
        
    def pause(self) -> None:
        """
        暂停操作
        """
        self._event.clear()
        self._paused = True
        
    def resume(self) -> None:
        """
        恢复操作
        """
        self._event.set()
        self._paused = False
        
    async def wait_if_paused(self) -> None:
        """
        如果处于暂停状态，则等待恢复
        """
        await self._event.wait()
        
    def __bool__(self) -> bool:
        """
        允许直接在if语句中使用
        
        Returns:
            是否处于暂停状态
        """
        return self.is_paused

class TaskContext:
    """
    任务上下文类，集成多种控制机制
    """
    
    def __init__(self, 
                cancel_token: Optional[CancelToken] = None, 
                pause_token: Optional[PauseToken] = None):
        """
        初始化任务上下文
        
        Args:
            cancel_token: 取消令牌
            pause_token: 暂停令牌
        """
        self.cancel_token = cancel_token or CancelToken()
        self.pause_token = pause_token or PauseToken()
        self.meta = {}  # 用于存储任务相关的元数据
        
    async def check_cancelled(self) -> bool:
        """
        检查是否已取消，如已取消则返回True
        
        Returns:
            是否已取消
        """
        return self.cancel_token.is_cancelled
        
    async def wait_if_paused(self) -> None:
        """
        如果处于暂停状态，则等待恢复
        """
        await self.pause_token.wait_if_paused()
        
    async def check_continue(self) -> bool:
        """
        检查是否可以继续执行：未取消且不处于暂停状态或已恢复
        
        Returns:
            是否可以继续执行
        """
        if await self.check_cancelled():
            return False
            
        await self.wait_if_paused()
        return True
        
    def set_meta(self, key: str, value: Any) -> None:
        """
        设置元数据
        
        Args:
            key: 键
            value: 值
        """
        self.meta[key] = value
        
    def get_meta(self, key: str, default: Any = None) -> Any:
        """
        获取元数据
        
        Args:
            key: 键
            default: 默认值
            
        Returns:
            元数据值
        """
        return self.meta.get(key, default) 