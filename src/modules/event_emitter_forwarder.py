"""
TG-Manager 事件发射器转发器
提供基于Qt Signal的转发器实现，包装原始转发器类，增加信号支持
"""

from PySide6.QtCore import Signal
from src.modules.forward.forwarder import Forwarder as OriginalForwarder
from src.utils.logger import get_logger
from src.utils.event_emitter import BaseEventEmitter
from typing import Any, Dict, List

logger = get_logger()

class EventEmitterForwarder(BaseEventEmitter):
    """基于Qt Signal的转发器包装类，包装原始转发器以提供信号支持"""
    
    # 转发器特有的信号定义
    progress_updated = Signal(int, int, int, str)  # 进度更新信号 (进度百分比, 当前, 总数, 操作类型)
    info_updated = Signal(str)  # 信息更新信号
    warning_updated = Signal(str)  # 警告信号
    debug_updated = Signal(str)  # 调试信息信号
    forward_completed = Signal(int)  # 转发完成信号 (转发数量)
    all_forwards_completed = Signal()  # 所有转发完成信号
    message_forwarded = Signal(int, str)  # 消息转发信号 (消息ID, 目标信息)
    media_group_forwarded = Signal(List, str, int)  # 媒体组转发信号 (消息ID列表, 目标信息, 数量)
    media_group_downloaded = Signal(str, int, int)  # 媒体组下载信号 (组ID, 消息数量, 下载文件数量)
    media_group_uploaded = Signal(str, List, List, List)  # 媒体组上传信号 (组ID, 消息ID列表, 上传成功目标, 剩余目标)
    
    def __init__(self, original_forwarder: OriginalForwarder):
        """初始化转发器包装类
        
        Args:
            original_forwarder: 原始转发器实例
        """
        # 调用基类构造函数
        super().__init__(original_forwarder)
        
        # 本地引用，方便访问
        self.forwarder = original_forwarder
        
        # 传递重要属性到本地
        self.client = self.forwarder.client
        self.ui_config_manager = self.forwarder.ui_config_manager
        self.channel_resolver = self.forwarder.channel_resolver
        self.history_manager = self.forwarder.history_manager
        self.downloader = self.forwarder.downloader
        self.uploader = self.forwarder.uploader
        self.app = self.forwarder.app
    
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
                
            # 处理转发器特有的事件类型
            if event_type == "progress":
                if len(args) >= 3:
                    progress = args[0]  # 进度百分比
                    current = args[1]  # 当前索引
                    total = args[2]  # 总数
                    operation_type = args[3] if len(args) > 3 else ""  # 操作类型
                    self.progress_updated.emit(progress, current, total, operation_type)
                    logger.debug(f"发射progress_updated信号: {progress}%, {current}/{total}, 类型: {operation_type}")
            
            elif event_type == "info":
                if args and isinstance(args[0], str):
                    info_message = args[0]
                    self.info_updated.emit(info_message)
                    logger.debug(f"发射info_updated信号: {info_message}")
                    
            elif event_type == "warning":
                if args and isinstance(args[0], str):
                    warning_message = args[0]
                    self.warning_updated.emit(warning_message)
                    logger.debug(f"发射warning_updated信号: {warning_message}")
                    
            elif event_type == "debug":
                if args and isinstance(args[0], str):
                    debug_message = args[0]
                    self.debug_updated.emit(debug_message)
                    logger.debug(f"发射debug_updated信号: {debug_message}")
                
            elif event_type == "complete":
                if args and isinstance(args[0], int):
                    count = args[0]
                    self.forward_completed.emit(count)
                    logger.debug(f"发射forward_completed信号: {count}")
                    
            elif event_type == "all_forwards_complete":
                self.all_forwards_completed.emit()
                logger.debug("发射all_forwards_completed信号")
                
            elif event_type == "message_forwarded":
                if len(args) >= 2:
                    message_id = args[0]
                    target_info = args[1]
                    self.message_forwarded.emit(message_id, target_info)
                    logger.debug(f"发射message_forwarded信号: msg_id={message_id}, target={target_info}")
                    
            elif event_type == "media_group_forwarded":
                if len(args) >= 3:
                    message_ids = args[0]
                    target_info = args[1]
                    count = args[2]
                    self.media_group_forwarded.emit(message_ids, target_info, count)
                    logger.debug(f"发射media_group_forwarded信号: {len(message_ids)}条消息, target={target_info}")
                    
            elif event_type == "media_group_downloaded":
                if len(args) >= 3:
                    group_id = args[0]
                    message_count = args[1]
                    file_count = args[2]
                    self.media_group_downloaded.emit(group_id, message_count, file_count)
                    logger.debug(f"发射media_group_downloaded信号: group={group_id}, msgs={message_count}, files={file_count}")
                    
            elif event_type == "media_group_uploaded":
                if len(args) >= 4:
                    group_id = args[0]
                    message_ids = args[1]
                    uploaded_targets = args[2]
                    remaining_targets = args[3]
                    self.media_group_uploaded.emit(group_id, message_ids, uploaded_targets, remaining_targets)
                    logger.debug(f"发射media_group_uploaded信号: group={group_id}, msgs={len(message_ids)}")
                
        except Exception as e:
            logger.error(f"发射Qt信号时发生错误: {e}")
    
    # 包装关键方法
    async def forward_messages(self):
        """包装转发方法，添加信号发射
        
        Returns:
            转发结果
        """
        try:
            # 发送开始状态
            self.status_updated.emit("开始转发消息...")
            
            # 调用原始方法
            result = await self.forwarder.forward_messages()
            
            # 发送所有转发完成信号
            self.all_forwards_completed.emit()
            
            return result
            
        except Exception as e:
            # 发送错误信号
            self.error_occurred.emit(f"转发过程中发生错误: {e}", "")
            # 重新抛出异常
            raise 