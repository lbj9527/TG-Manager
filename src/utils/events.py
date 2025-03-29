"""
事件系统模块，用于实现组件间的事件通知机制
"""

from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

class EventEmitter:
    """
    事件发射器类，负责管理事件监听和触发
    
    支持以下事件类型:
    - progress: 进度更新事件(进度百分比, 当前项, 总项数)
    - status: 状态更新事件(状态消息)
    - error: 错误事件(错误消息, 错误类型, 是否可恢复)
    - complete: 完成事件(完成状态, 统计信息)
    - media_found: 媒体发现事件(媒体类型, 媒体ID, 频道信息)
    - media_download: 媒体下载事件(媒体信息, 下载路径, 文件大小)
    - media_upload: 媒体上传事件(媒体信息, 目标频道, 上传状态)
    - forward: 转发事件(消息ID, 源频道, 目标频道, 转发状态)
    """
    
    def __init__(self):
        """初始化事件发射器"""
        self.listeners = defaultdict(list)
    
    def on(self, event: str, callback: Callable) -> 'EventEmitter':
        """
        注册事件监听器
        
        Args:
            event: 事件名称
            callback: 回调函数
            
        Returns:
            事件发射器实例，用于链式调用
        """
        self.listeners[event].append(callback)
        return self
    
    def off(self, event: str, callback: Optional[Callable] = None) -> 'EventEmitter':
        """
        移除事件监听器
        
        Args:
            event: 事件名称
            callback: 要移除的回调函数，如果为None则移除该事件的所有监听器
            
        Returns:
            事件发射器实例，用于链式调用
        """
        if callback is None:
            self.listeners[event].clear()
        else:
            self.listeners[event] = [cb for cb in self.listeners[event] if cb != callback]
        return self
    
    def emit(self, event: str, *args: Any, **kwargs: Any) -> 'EventEmitter':
        """
        触发事件，调用所有注册的监听器
        
        Args:
            event: 事件名称
            *args: 传递给监听器的位置参数
            **kwargs: 传递给监听器的关键字参数
            
        Returns:
            事件发射器实例，用于链式调用
        """
        for callback in self.listeners[event]:
            try:
                callback(*args, **kwargs)
            except Exception as e:
                print(f"事件处理器错误: {event} - {e}")
        return self
    
    def once(self, event: str, callback: Callable) -> 'EventEmitter':
        """
        注册一次性事件监听器，触发一次后自动移除
        
        Args:
            event: 事件名称
            callback: 回调函数
            
        Returns:
            事件发射器实例，用于链式调用
        """
        def one_time_callback(*args: Any, **kwargs: Any) -> None:
            self.off(event, one_time_callback)
            callback(*args, **kwargs)
        
        return self.on(event, one_time_callback)
    
    def listeners_count(self, event: str) -> int:
        """
        获取指定事件的监听器数量
        
        Args:
            event: 事件名称
            
        Returns:
            监听器数量
        """
        return len(self.listeners[event])
    
    def has_listeners(self, event: str) -> bool:
        """
        检查是否有监听器注册到指定事件
        
        Args:
            event: 事件名称
            
        Returns:
            是否有监听器
        """
        return self.listeners_count(event) > 0 