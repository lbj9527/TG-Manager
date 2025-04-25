"""
TG-Manager 事件发射器上传器
提供基于Qt Signal的上传器实现，包装原始上传器类，增加信号支持
"""

from PySide6.QtCore import Signal
from src.modules.uploader import Uploader as OriginalUploader
from src.utils.logger import get_logger
from src.utils.event_emitter import BaseEventEmitter
from typing import Any, Dict

logger = get_logger()

class EventEmitterUploader(BaseEventEmitter):
    """基于Qt Signal的上传器包装类，包装原始上传器以提供信号支持"""
    
    # 上传器特有的信号定义
    progress_updated = Signal(int, int, int)  # 进度更新信号 (进度百分比, 当前索引, 总数)
    upload_completed = Signal(object)  # 上传完成信号 (结果数据)
    media_uploaded = Signal(object)  # 媒体上传信号 (媒体数据)
    all_uploads_completed = Signal()  # 所有上传完成信号
    file_already_uploaded = Signal(object)  # 文件已上传信号 (文件数据)
    final_message_sent = Signal(object)  # 最终消息发送成功信号 (消息数据)
    final_message_error = Signal(object)  # 最终消息发送失败信号 (错误数据)
    
    def __init__(self, original_uploader: OriginalUploader):
        """初始化上传器包装类
        
        Args:
            original_uploader: 原始上传器实例
        """
        # 调用基类构造函数
        super().__init__(original_uploader)
        
        # 本地引用，方便访问
        self.uploader = original_uploader
        
        # 传递重要属性到本地
        self.client = self.uploader.client
        self.ui_config_manager = self.uploader.ui_config_manager
        self.channel_resolver = self.uploader.channel_resolver
        self.history_manager = self.uploader.history_manager
        self.app = self.uploader.app
    
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
                
            # 处理上传器特有的事件类型
            if event_type == "progress":
                if len(args) >= 3:
                    progress = args[0]  # 进度百分比
                    idx = args[1]  # 当前索引
                    total = args[2]  # 总数
                    self.progress_updated.emit(progress, idx, total)
                    logger.debug(f"发射progress_updated信号: {progress}%, {idx}/{total}")
            
            elif event_type == "complete":
                # 第二个参数是完成的数据字典
                if len(args) >= 2 and isinstance(args[1], dict):
                    result_data = args[1]
                    self.upload_completed.emit(result_data)
                    # 同时发射所有上传完成信号
                    self.all_uploads_completed.emit()
                    logger.debug(f"发射upload_completed和all_uploads_completed信号")
                
            elif event_type == "media_upload" or event_type == "file_uploaded":
                # 第一个参数是媒体数据字典
                if args and isinstance(args[0], dict):
                    media_data = args[0]
                    self.media_uploaded.emit(media_data)
                    logger.debug(f"发射media_uploaded信号: {media_data}")
                    
                    # 如果是单个文件上传，额外发送file_uploaded事件，兼容旧的处理方式
                    if event_type == "media_upload" and 'file_name' in media_data:
                        # 向所有监听file_uploaded事件的处理器发送数据
                        # 发送到上传视图处理文件上传完成
                        if hasattr(self.original, '_listeners') and 'file_uploaded' in self.original._listeners:
                            for callback in self.original._listeners['file_uploaded']:
                                try:
                                    callback(media_data, True)  # 传递字典和成功状态
                                except Exception as e:
                                    logger.error(f"调用file_uploaded回调时出错: {e}")
            
            elif event_type == "all_uploads_complete":
                self.all_uploads_completed.emit()
                logger.debug("发射all_uploads_completed信号")
                
            elif event_type == "file_already_uploaded":
                if args and isinstance(args[0], dict):
                    file_data = args[0]
                    self.file_already_uploaded.emit(file_data)
                    logger.debug(f"发射file_already_uploaded信号: {file_data}")
                    
            elif event_type == "final_message_sent":
                if args and isinstance(args[0], dict):
                    message_data = args[0]
                    self.final_message_sent.emit(message_data)
                    logger.debug(f"发射final_message_sent信号: {message_data}")
                    
            elif event_type == "final_message_error":
                if args and isinstance(args[0], dict):
                    error_data = args[0]
                    self.final_message_error.emit(error_data)
                    logger.debug(f"发射final_message_error信号: {error_data}")
                
        except Exception as e:
            logger.error(f"发射Qt信号时发生错误: {e}")
    
    # 包装关键方法
    async def upload_files(self, task_context=None):
        """包装上传方法，添加信号发射
        
        Args:
            task_context: 任务上下文
            
        Returns:
            上传结果
        """
        try:
            # 发送开始状态
            self.status_updated.emit("开始上传文件...")
            
            # 调用原始方法
            result = await self.uploader.upload_files(task_context)
            
            # 发送所有上传完成信号
            self.all_uploads_completed.emit()
            
            return result
            
        except Exception as e:
            # 发送错误信号
            self.error_occurred.emit(f"上传过程中发生错误: {e}", "")
            # 重新抛出异常
            raise 