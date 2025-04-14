"""
TG-Manager 事件发射器基类
提供基于Qt Signal的事件发射基础实现，可以被各个模块继承使用
"""

from PySide6.QtCore import QObject, Signal
from src.utils.logger import get_logger

logger = get_logger()

class BaseEventEmitter(QObject):
    """基础事件发射器类，提供通用的事件处理方法"""
    
    # 基础信号定义
    status_updated = Signal(str)  # 状态更新信号
    error_occurred = Signal(str, str)  # 错误信号 (错误信息, 错误详情)
    
    def __init__(self, original_instance):
        """初始化事件发射器基类
        
        Args:
            original_instance: 原始实例对象
        """
        super().__init__()
        self.original = original_instance
        self._setup_event_listeners()
        
    def _setup_event_listeners(self):
        """设置事件监听器，将原始实例的emit方法调用转换为信号发射"""
        # 保存原始的emit方法
        original_emit = getattr(self.original, 'emit', None)
        
        # 如果原始实例没有emit方法，则为其添加一个
        if original_emit is None:
            setattr(self.original, 'emit', self._dummy_emit)
            logger.debug(f"原始{type(self.original).__name__}没有emit方法，已添加dummy方法")
        else:
            # 替换emit方法以同时触发Qt信号
            def enhanced_emit(event_type, *args, **kwargs):
                # 调用原始emit
                original_emit(event_type, *args, **kwargs)
                # 同时触发Qt信号
                self._emit_qt_signal(event_type, *args, **kwargs)
            
            setattr(self.original, 'emit', enhanced_emit)
            logger.debug(f"已增强原始{type(self.original).__name__}的emit方法")
            
        # 为原始实例添加add_event_listener和on方法
        if not hasattr(self.original, 'add_event_listener'):
            setattr(self.original, 'add_event_listener', self._dummy_add_event_listener)
            logger.debug(f"原始{type(self.original).__name__}没有add_event_listener方法，已添加dummy方法")
            
        if not hasattr(self.original, 'on'):
            setattr(self.original, 'on', self._dummy_add_event_listener)  # on方法与add_event_listener功能相同
            logger.debug(f"原始{type(self.original).__name__}没有on方法，已添加dummy方法")
    
    def _dummy_emit(self, event_type, *args, **kwargs):
        """虚拟的emit方法，用于在原始实例没有emit方法时提供替代
        
        Args:
            event_type: 事件类型
            *args: 位置参数
            **kwargs: 关键字参数
        """
        # 转发到Qt信号
        self._emit_qt_signal(event_type, *args, **kwargs)
        logger.debug(f"虚拟emit: {event_type}, args: {args}, kwargs: {kwargs}")
    
    def _dummy_add_event_listener(self, event_type, callback):
        """虚拟的add_event_listener/on方法，用于在原始实例没有该方法时提供替代
        
        Args:
            event_type: 事件类型
            callback: 回调函数
        """
        logger.debug(f"虚拟add_event_listener: {event_type}, callback: {callback}")
        
        # 根据事件类型连接到对应的信号（如果存在）
        signal_name = self._convert_event_type_to_signal_name(event_type)
        if hasattr(self, signal_name):
            signal = getattr(self, signal_name)
            signal.connect(callback)
            logger.debug(f"已连接回调到信号 {signal_name}")
        else:
            logger.warning(f"找不到与事件类型 {event_type} 对应的信号 {signal_name}")
    
    def _convert_event_type_to_signal_name(self, event_type):
        """将事件类型转换为信号名称
        
        例如: "status" -> "status_updated", "error" -> "error_occurred"
        
        Args:
            event_type: 事件类型
            
        Returns:
            str: 对应的信号名称
        """
        # 基本的转换规则
        conversion_map = {
            "status": "status_updated",
            "error": "error_occurred",
            "progress": "progress_updated",
            "complete": "all_completed",
            "download_complete": "download_completed",
            "all_downloads_complete": "all_downloads_completed",
            "message_received": "message_received",
            "forward_complete": "forward_completed",
            "upload_complete": "upload_completed",
            "keyword_matched": "keyword_matched"
        }
        
        # 返回转换后的名称，如果没有特定转换则添加"_updated"后缀
        return conversion_map.get(event_type, f"{event_type}_updated")
    
    def _emit_qt_signal(self, event_type, *args, **kwargs):
        """根据事件类型发射对应的Qt信号
        
        子类应该重写此方法以处理特定的事件类型
        
        Args:
            event_type: 事件类型
            *args: 位置参数
            **kwargs: 关键字参数
        """
        try:
            # 基本的事件处理
            if event_type == "status":
                if args and isinstance(args[0], str):
                    self.status_updated.emit(args[0])
                    logger.debug(f"发射status_updated信号: {args[0]}")
            
            elif event_type == "error":
                error_msg = args[0] if args else "未知错误"
                error_detail = kwargs.get("details", "")
                self.error_occurred.emit(error_msg, error_detail)
                logger.debug(f"发射error_occurred信号: {error_msg}, 详情: {error_detail}")
                
            # 其他事件类型由子类处理
                
        except Exception as e:
            logger.error(f"发射Qt信号时发生错误: {e}")
    
    # 转发属性访问到原始实例
    def __getattr__(self, name):
        """转发属性访问到原始实例
        
        Args:
            name: 属性名
            
        Returns:
            Any: 属性值
        """
        return getattr(self.original, name) 