"""
UI状态管理模块，用于实现业务逻辑与界面分离
"""

from typing import Dict, List, Any, Optional, Callable, TypeVar, Generic, Union, Set
from collections import defaultdict
import threading
import asyncio
import logging
from enum import Enum, auto

from src.utils.logger import get_logger
from src.utils.events import EventEmitter

# 获取日志记录器
logger = get_logger()

# 用于泛型的类型参数
T = TypeVar('T')

class UICallback:
    """UI回调接口，用于处理业务逻辑状态变更和通知UI界面"""
    
    def __init__(self):
        """初始化UI回调"""
        # 注册各种回调函数
        self.status_callback: Optional[Callable[[str], None]] = None
        self.progress_callback: Optional[Callable[[int, int, str], None]] = None
        self.info_callback: Optional[Callable[[str], None]] = None
        self.warning_callback: Optional[Callable[[str], None]] = None
        self.error_callback: Optional[Callable[[str, str, str, bool], None]] = None
        self.media_callback: Optional[Callable[[str, Any, Dict[str, Any]], None]] = None
        self.complete_callback: Optional[Callable[[bool, Dict[str, Any]], None]] = None
    
    def set_status_callback(self, callback: Callable[[str], None]) -> 'UICallback':
        """
        设置状态回调
        
        Args:
            callback: 回调函数，参数为状态消息
            
        Returns:
            UICallback: 实例自身，支持链式调用
        """
        self.status_callback = callback
        return self
    
    def set_progress_callback(self, callback: Callable[[int, int, str], None]) -> 'UICallback':
        """
        设置进度回调
        
        Args:
            callback: 回调函数，参数为当前进度值、总进度值和进度描述
            
        Returns:
            UICallback: 实例自身，支持链式调用
        """
        self.progress_callback = callback
        return self
    
    def set_info_callback(self, callback: Callable[[str], None]) -> 'UICallback':
        """
        设置信息回调
        
        Args:
            callback: 回调函数，参数为信息消息
            
        Returns:
            UICallback: 实例自身，支持链式调用
        """
        self.info_callback = callback
        return self
    
    def set_warning_callback(self, callback: Callable[[str], None]) -> 'UICallback':
        """
        设置警告回调
        
        Args:
            callback: 回调函数，参数为警告消息
            
        Returns:
            UICallback: 实例自身，支持链式调用
        """
        self.warning_callback = callback
        return self
    
    def set_error_callback(self, callback: Callable[[str, str, str, bool], None]) -> 'UICallback':
        """
        设置错误回调
        
        Args:
            callback: 回调函数，参数为错误标题、错误消息、详细信息和是否可恢复
            
        Returns:
            UICallback: 实例自身，支持链式调用
        """
        self.error_callback = callback
        return self
    
    def set_media_callback(self, callback: Callable[[str, Any, Dict[str, Any]], None]) -> 'UICallback':
        """
        设置媒体回调
        
        Args:
            callback: 回调函数，参数为媒体操作类型、媒体数据和附加信息
            
        Returns:
            UICallback: 实例自身，支持链式调用
        """
        self.media_callback = callback
        return self
    
    def set_complete_callback(self, callback: Callable[[bool, Dict[str, Any]], None]) -> 'UICallback':
        """
        设置完成回调
        
        Args:
            callback: 回调函数，参数为是否成功和统计信息
            
        Returns:
            UICallback: 实例自身，支持链式调用
        """
        self.complete_callback = callback
        return self
    
    def update_status(self, message: str) -> None:
        """
        更新状态
        
        Args:
            message: 状态消息
        """
        if self.status_callback:
            self.status_callback(message)
    
    def update_progress(self, current: int, total: int, message: str = "") -> None:
        """
        更新进度
        
        Args:
            current: 当前进度值
            total: 总进度值
            message: 进度描述
        """
        if self.progress_callback:
            self.progress_callback(current, total, message)
    
    def show_info(self, message: str) -> None:
        """
        显示信息
        
        Args:
            message: 信息消息
        """
        if self.info_callback:
            self.info_callback(message)
    
    def show_warning(self, message: str) -> None:
        """
        显示警告
        
        Args:
            message: 警告消息
        """
        if self.warning_callback:
            self.warning_callback(message)
    
    def show_error(self, title: str, message: str, details: str = "", recoverable: bool = False) -> None:
        """
        显示错误
        
        Args:
            title: 错误标题
            message: 错误消息
            details: 详细信息
            recoverable: 是否可恢复
        """
        if self.error_callback:
            self.error_callback(title, message, details, recoverable)
    
    def notify_media(self, operation: str, media_data: Any, extra_info: Dict[str, Any] = None) -> None:
        """
        通知媒体操作
        
        Args:
            operation: 操作类型，如'found', 'download', 'upload'
            media_data: 媒体数据
            extra_info: 附加信息
        """
        if self.media_callback:
            self.media_callback(operation, media_data, extra_info or {})
    
    def notify_complete(self, success: bool, stats: Dict[str, Any] = None) -> None:
        """
        通知任务完成
        
        Args:
            success: 是否成功
            stats: 统计信息
        """
        if self.complete_callback:
            self.complete_callback(success, stats or {})


class UIStateValue(Generic[T]):
    """UI状态值，包含值和元数据"""
    
    def __init__(self, value: T, metadata: Dict[str, Any] = None):
        """
        初始化UI状态值
        
        Args:
            value: 状态值
            metadata: 元数据
        """
        self.value = value
        self.metadata = metadata or {}
        self.timestamp = asyncio.get_event_loop().time() if asyncio.get_event_loop().is_running() else 0


class UIState:
    """UI状态管理类，用于管理业务逻辑的状态并提供给UI界面"""
    
    def __init__(self):
        """初始化UI状态管理器"""
        self._state: Dict[str, UIStateValue] = {}
        self._callbacks: Dict[str, List[Callable[[Any, Dict[str, Any]], None]]] = defaultdict(list)
        self._lock = threading.RLock()
        self._event_emitter = EventEmitter()
    
    def set(self, key: str, value: Any, metadata: Dict[str, Any] = None) -> None:
        """
        设置状态值
        
        Args:
            key: 状态键
            value: 状态值
            metadata: 元数据
        """
        with self._lock:
            old_state = self._state.get(key)
            self._state[key] = UIStateValue(value, metadata)
        
        # 触发回调
        for callback in self._callbacks.get(key, []):
            try:
                callback(value, metadata or {})
            except Exception as e:
                logger.error(f"状态回调错误: {key} - {e}")
        
        # 触发事件
        self._event_emitter.emit(f"state_changed:{key}", value, metadata or {})
        self._event_emitter.emit("state_changed", key, value, metadata or {})
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取状态值
        
        Args:
            key: 状态键
            default: 默认值
            
        Returns:
            状态值，如果不存在则返回默认值
        """
        with self._lock:
            state = self._state.get(key)
            if state is None:
                return default
            return state.value
    
    def get_with_metadata(self, key: str) -> Optional[UIStateValue]:
        """
        获取状态值和元数据
        
        Args:
            key: 状态键
            
        Returns:
            状态值对象，如果不存在则返回None
        """
        with self._lock:
            return self._state.get(key)
    
    def remove(self, key: str) -> None:
        """
        移除状态
        
        Args:
            key: 状态键
        """
        with self._lock:
            if key in self._state:
                del self._state[key]
    
    def watch(self, key: str, callback: Callable[[Any, Dict[str, Any]], None]) -> None:
        """
        监视状态变化
        
        Args:
            key: 状态键
            callback: 回调函数，参数为新值和元数据
        """
        with self._lock:
            self._callbacks[key].append(callback)
    
    def unwatch(self, key: str, callback: Optional[Callable] = None) -> None:
        """
        取消监视
        
        Args:
            key: 状态键
            callback: 回调函数，如果为None则移除所有回调
        """
        with self._lock:
            if callback is None:
                self._callbacks[key].clear()
            else:
                self._callbacks[key] = [cb for cb in self._callbacks[key] if cb != callback]
    
    def on(self, event: str, callback: Callable) -> None:
        """
        注册事件监听器
        
        Args:
            event: 事件名称，可以是'state_changed'或'state_changed:{key}'
            callback: 回调函数
        """
        self._event_emitter.on(event, callback)
    
    def off(self, event: str, callback: Optional[Callable] = None) -> None:
        """
        移除事件监听器
        
        Args:
            event: 事件名称
            callback: 回调函数，如果为None则移除所有监听器
        """
        self._event_emitter.off(event, callback)
    
    def clear(self) -> None:
        """清空所有状态"""
        with self._lock:
            self._state.clear()


class EventToUIAdapter:
    """事件到UI回调的适配器，将EventEmitter事件转发到UICallback"""
    
    def __init__(self, ui_callback: UICallback):
        """
        初始化适配器
        
        Args:
            ui_callback: UI回调接口
        """
        self.ui_callback = ui_callback
    
    def adapt(self, event_emitter: EventEmitter) -> 'EventToUIAdapter':
        """
        将事件发射器事件适配到UI回调
        
        Args:
            event_emitter: 事件发射器
            
        Returns:
            EventToUIAdapter: 实例自身，支持链式调用
        """
        # 注册状态更新事件
        event_emitter.on("status", self._on_status)
        
        # 注册进度更新事件
        event_emitter.on("progress", self._on_progress)
        
        # 注册信息事件
        event_emitter.on("info", self._on_info)
        
        # 注册警告事件
        event_emitter.on("warning", self._on_warning)
        
        # 注册错误事件
        event_emitter.on("error", self._on_error)
        
        # 注册媒体事件
        event_emitter.on("media_found", lambda *args, **kwargs: 
                        self._on_media("found", *args, **kwargs))
        event_emitter.on("media_download", lambda *args, **kwargs: 
                        self._on_media("download", *args, **kwargs))
        event_emitter.on("media_upload", lambda *args, **kwargs: 
                        self._on_media("upload", *args, **kwargs))
        
        # 注册完成事件
        event_emitter.on("complete", self._on_complete)
        
        return self
    
    def _on_status(self, message: str) -> None:
        """处理状态事件"""
        self.ui_callback.update_status(message)
    
    def _on_progress(self, current: int, total: int, message: str = "") -> None:
        """处理进度事件"""
        self.ui_callback.update_progress(current, total, message)
    
    def _on_info(self, message: str) -> None:
        """处理信息事件"""
        self.ui_callback.show_info(message)
    
    def _on_warning(self, message: str) -> None:
        """处理警告事件"""
        self.ui_callback.show_warning(message)
    
    def _on_error(self, message: str, error_type: str = "", 
                 recoverable: bool = False, details: str = "") -> None:
        """处理错误事件"""
        self.ui_callback.show_error(error_type or "错误", message, details, recoverable)
    
    def _on_media(self, operation: str, *args, **kwargs) -> None:
        """处理媒体事件"""
        # 根据不同的媒体操作类型，提取相关参数
        media_data = args[0] if args else None
        extra_info = kwargs.copy()
        if len(args) > 1:
            extra_info.update({f"arg{i}": arg for i, arg in enumerate(args[1:], 1)})
        
        self.ui_callback.notify_media(operation, media_data, extra_info)
    
    def _on_complete(self, success: bool = True, stats: Dict[str, Any] = None) -> None:
        """处理完成事件"""
        self.ui_callback.notify_complete(success, stats or {})


# 全局UI状态实例
global_ui_state = UIState()

def get_ui_state() -> UIState:
    """
    获取全局UI状态实例
    
    Returns:
        UIState: 全局UI状态实例
    """
    return global_ui_state

# 全局UI回调实例
global_ui_callback = UICallback()

def get_ui_callback() -> UICallback:
    """
    获取全局UI回调实例
    
    Returns:
        UICallback: 全局UI回调实例
    """
    return global_ui_callback 