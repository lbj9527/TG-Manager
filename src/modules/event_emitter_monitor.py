"""
TG-Manager 事件发射器监听器
提供基于Qt Signal的监听器实现，包装原始监听器类，增加信号支持
"""

from PySide6.QtCore import Signal
from src.modules.monitor import Monitor as OriginalMonitor
from src.utils.logger import get_logger
from src.utils.event_emitter import BaseEventEmitter
from typing import Any, Dict, List, Optional

logger = get_logger()

class EventEmitterMonitor(BaseEventEmitter):
    """基于Qt Signal的监听器包装类，包装原始监听器以提供信号支持"""
    
    # 监听器特有的信号定义
    message_received = Signal(int, str)  # 消息接收信号 (消息ID, 来源信息)
    keyword_matched = Signal(int, str)  # 关键词匹配信号 (消息ID, 关键词)
    message_processed = Signal(int)  # 消息处理完成信号 (消息ID)
    monitoring_started = Signal()  # 监听开始信号
    monitoring_stopped = Signal()  # 监听停止信号
    new_message_updated = Signal(int, str)  # 新消息更新信号 (消息ID, 来源信息)
    forward_updated = Signal(int, int, int, bool, bool)  # 转发状态更新信号 (源消息ID, 源频道ID, 目标ID, 成功标志, 修改标志)
    text_replaced = Signal(str, str, List)  # 文本替换信号 (原文本, 修改后文本, 替换规则)
    history_progress = Signal(int, int)  # 历史消息获取进度信号 (已获取消息数, 限制数)
    history_complete = Signal(int)  # 历史消息获取完成信号 (总消息数)
    
    def __init__(self, original_monitor: OriginalMonitor):
        """初始化监听器包装类
        
        Args:
            original_monitor: 原始监听器实例
        """
        # 调用基类构造函数
        super().__init__(original_monitor)
        
        # 本地引用，方便访问
        self.monitor = original_monitor
        
        # 传递重要属性到本地
        self.client = self.monitor.client
        self.ui_config_manager = self.monitor.ui_config_manager
        self.channel_resolver = self.monitor.channel_resolver
        self.app = self.monitor.app
        
        # 监听任务控制变量
        self.should_stop = self.monitor.should_stop
        self.monitor_tasks = self.monitor.monitor_tasks
    
    def _emit_qt_signal(self, event_type, *args, **kwargs):
        """根据事件类型发射对应的Qt信号
        
        Args:
            event_type: 事件类型
            *args: 位置参数
            **kwargs: 关键字参数
        """
        try:
            # 先处理基本事件类型
            if event_type in ["status", "error"]:
                # 调用基类处理基本事件
                super()._emit_qt_signal(event_type, *args, **kwargs)
                return
                
            # 处理监听器特有的事件类型
            if event_type == "message_received":
                if len(args) >= 2:
                    message_id = args[0]
                    source_info = args[1]
                    self.message_received.emit(message_id, source_info)
                    logger.debug(f"发射message_received信号: msg_id={message_id}, source={source_info}")
            
            elif event_type == "new_message":
                if len(args) >= 2:
                    message_id = args[0]
                    source_info = args[1]
                    self.new_message_updated.emit(message_id, source_info)
                    logger.debug(f"发射new_message_updated信号: msg_id={message_id}, source={source_info}")
            
            elif event_type == "keyword_matched":
                if len(args) >= 2:
                    message_id = args[0]
                    keywords = args[1]
                    self.keyword_matched.emit(message_id, keywords)
                    logger.debug(f"发射keyword_matched信号: msg_id={message_id}, keywords={keywords}")
                    
            elif event_type == "message_processed":
                if args and isinstance(args[0], int):
                    message_id = args[0]
                    self.message_processed.emit(message_id)
                    logger.debug(f"发射message_processed信号: msg_id={message_id}")
                    
            elif event_type == "forward":
                # forward(source_message_id, source_chat_id, target_id, success, modified=False)
                if len(args) >= 4:
                    source_message_id = args[0]
                    source_chat_id = args[1]
                    target_id = args[2]
                    success = args[3]
                    modified = kwargs.get("modified", False)
                    self.forward_updated.emit(source_message_id, source_chat_id, target_id, success, modified)
                    logger.debug(f"发射forward_updated信号: msg_id={source_message_id}, target={target_id}, success={success}")
                    
            elif event_type == "text_replaced":
                if len(args) >= 3:
                    text = args[0]
                    modified_text = args[1]
                    replacements = args[2]
                    self.text_replaced.emit(text, modified_text, replacements)
                    logger.debug(f"发射text_replaced信号: 替换了 {len(replacements)} 处文本")
                    
            elif event_type == "history_progress":
                if len(args) >= 2:
                    count = args[0]
                    limit = args[1]
                    self.history_progress.emit(count, limit)
                    logger.debug(f"发射history_progress信号: {count}/{limit}")
                    
            elif event_type == "history_complete":
                if args and isinstance(args[0], int):
                    count = args[0]
                    self.history_complete.emit(count)
                    logger.debug(f"发射history_complete信号: 总共 {count} 条消息")
                
        except Exception as e:
            logger.error(f"发射Qt信号时发生错误: {e}")
    
    # 包装关键方法
    async def start_monitoring(self, task_context=None):
        """包装监听开始方法，添加信号发射
        
        Args:
            task_context: 任务上下文
            
        Returns:
            监听结果
        """
        try:
            # 发送开始状态
            self.status_updated.emit("开始监听频道消息...")
            # 发送监听开始信号
            self.monitoring_started.emit()
            
            # 调用原始方法 - 不传递任何参数，因为Monitor.start_monitoring不接受参数
            result = await self.monitor.start_monitoring()
            
            # 监听结束
            self.monitoring_stopped.emit()
            
            return result
            
        except Exception as e:
            # 发送错误信号
            self.error_occurred.emit(f"监听过程中发生错误: {e}", "")
            # 发送监听停止信号
            self.monitoring_stopped.emit()
            # 重新抛出异常
            raise
            
    async def stop_monitoring(self):
        """包装停止监听方法，添加信号发射
        
        Returns:
            结果
        """
        try:
            # 发送状态
            self.status_updated.emit("正在停止监听...")
            
            # 调用原始方法
            result = await self.monitor.stop_monitoring()
            
            # 发送监听停止信号
            self.monitoring_stopped.emit()
            
            # 发送停止完成状态
            self.status_updated.emit("监听已停止")
            
            return result
            
        except Exception as e:
            # 发送错误信号
            self.error_occurred.emit(f"停止监听过程中发生错误: {e}", "")
            # 发送监听停止信号
            self.monitoring_stopped.emit()
            # 重新抛出异常
            raise 