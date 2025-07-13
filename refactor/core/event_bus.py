"""
事件总线系统

提供统一的事件管理功能，支持事件的发射和监听。
"""

import asyncio
from typing import Any, Callable, Dict, List, Optional, Union
from loguru import logger


class EventBus:
    """
    事件总线，负责管理事件的发射和监听。
    
    提供统一的事件系统，支持同步和异步事件处理器。
    """
    
    def __init__(self):
        """初始化事件总线。"""
        self._handlers: Dict[str, List[Callable]] = {}
        self._async_handlers: Dict[str, List[Callable]] = {}
        self._logger = logger.bind(name="EventBus")
    
    def on(self, event_type: str, handler: Callable) -> None:
        """
        注册事件处理器。
        
        Args:
            event_type: 事件类型
            handler: 事件处理器函数
        """
        if asyncio.iscoroutinefunction(handler):
            if event_type not in self._async_handlers:
                self._async_handlers[event_type] = []
            self._async_handlers[event_type].append(handler)
            self._logger.debug(f"注册异步事件处理器: {event_type}")
        else:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(handler)
            self._logger.debug(f"注册同步事件处理器: {event_type}")
    
    def off(self, event_type: str, handler=None) -> None:
        """
        移除事件处理器。
        
        Args:
            event_type: 事件类型
            handler: 要移除的处理器，如果为None则移除所有处理器
        """
        if event_type not in self._handlers and event_type not in self._async_handlers:
            return
        
        if handler is None:
            # 移除所有处理器
            if event_type in self._handlers:
                del self._handlers[event_type]
            if event_type in self._async_handlers:
                del self._async_handlers[event_type]
            self._logger.debug(f"移除所有事件处理器: {event_type}")
        else:
            # 移除指定处理器
            if event_type in self._handlers and handler in self._handlers[event_type]:
                self._handlers[event_type].remove(handler)
                if not self._handlers[event_type]:  # 如果没有处理器了，删除整个事件
                    del self._handlers[event_type]
            
            if event_type in self._async_handlers and handler in self._async_handlers[event_type]:
                self._async_handlers[event_type].remove(handler)
                if not self._async_handlers[event_type]:  # 如果没有处理器了，删除整个事件
                    del self._async_handlers[event_type]
            
            self._logger.debug(f"移除事件处理器: {event_type}")
    
    def emit(self, event_type: str, *args, **kwargs) -> None:
        """
        发射事件。
        
        Args:
            event_type: 事件类型
            *args: 位置参数
            **kwargs: 关键字参数
        """
        # 处理同步处理器
        if event_type in self._handlers:
            for handler in self._handlers[event_type]:
                try:
                    handler(*args, **kwargs)
                except Exception as e:
                    self._logger.error(f"同步事件处理器执行失败: {event_type}, 错误: {e}")
        
        # 处理异步处理器
        if event_type in self._async_handlers:
            for handler in self._async_handlers[event_type]:
                try:
                    # 创建异步任务
                    asyncio.create_task(self._execute_async_handler(handler, *args, **kwargs))
                except Exception as e:
                    self._logger.error(f"异步事件处理器创建任务失败: {event_type}, 错误: {e}")
    
    async def emit_async(self, event_type: str, *args, **kwargs) -> None:
        """
        异步发射事件。
        
        Args:
            event_type: 事件类型
            *args: 位置参数
            **kwargs: 关键字参数
        """
        # 处理同步处理器
        if event_type in self._handlers:
            for handler in self._handlers[event_type]:
                try:
                    handler(*args, **kwargs)
                except Exception as e:
                    self._logger.error(f"同步事件处理器执行失败: {event_type}, 错误: {e}")
        
        # 处理异步处理器
        if event_type in self._async_handlers:
            tasks = []
            for handler in self._async_handlers[event_type]:
                try:
                    task = asyncio.create_task(self._execute_async_handler(handler, *args, **kwargs))
                    tasks.append(task)
                except Exception as e:
                    self._logger.error(f"异步事件处理器创建任务失败: {event_type}, 错误: {e}")
            
            # 等待所有异步任务完成
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _execute_async_handler(self, handler: Callable, *args, **kwargs) -> None:
        """
        执行异步事件处理器。
        
        Args:
            handler: 异步事件处理器
            *args: 位置参数
            **kwargs: 关键字参数
        """
        try:
            await handler(*args, **kwargs)
        except Exception as e:
            self._logger.error(f"异步事件处理器执行失败: {e}")
    
    def has_handlers(self, event_type: str) -> bool:
        """
        检查是否有事件处理器。
        
        Args:
            event_type: 事件类型
            
        Returns:
            bool: 是否有处理器
        """
        return (event_type in self._handlers and len(self._handlers[event_type]) > 0) or \
               (event_type in self._async_handlers and len(self._async_handlers[event_type]) > 0)
    
    def get_handler_count(self, event_type: str) -> int:
        """
        获取事件处理器数量。
        
        Args:
            event_type: 事件类型
            
        Returns:
            int: 处理器数量
        """
        sync_count = len(self._handlers.get(event_type, []))
        async_count = len(self._async_handlers.get(event_type, []))
        return sync_count + async_count
    
    def clear(self) -> None:
        """清空所有事件处理器。"""
        self._handlers.clear()
        self._async_handlers.clear()
        self._logger.debug("清空所有事件处理器")
    
    def get_registered_events(self) -> List[str]:
        """
        获取所有已注册的事件类型。
        
        Returns:
            List[str]: 事件类型列表
        """
        events = set(self._handlers.keys())
        events.update(self._async_handlers.keys())
        return list(events) 