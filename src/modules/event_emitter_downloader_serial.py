"""
TG-Manager 事件发射器串行下载器
提供基于Qt Signal的串行下载器实现，包装原始串行下载器类，增加信号支持
"""

from PySide6.QtCore import Signal
from src.modules.downloader_serial import DownloaderSerial as OriginalDownloaderSerial
from src.utils.logger import get_logger
from src.utils.event_emitter import BaseEventEmitter
import asyncio
from typing import Any, Optional, Dict, List

logger = get_logger()

class EventEmitterDownloaderSerial(BaseEventEmitter):
    """基于Qt Signal的串行下载器包装类，包装原始串行下载器以提供信号支持"""
    
    # 串行下载器特有的信号定义
    progress_updated = Signal(int, int, str)  # 进度更新信号 (当前, 总数, 文件名)
    download_completed = Signal(int, str, int)  # 下载完成信号 (消息ID, 文件名, 文件大小)
    all_downloads_completed = Signal()  # 所有下载完成信号
    
    def __init__(self, original_downloader: OriginalDownloaderSerial):
        """初始化串行下载器包装类
        
        Args:
            original_downloader: 原始串行下载器实例
        """
        # 调用基类构造函数
        super().__init__(original_downloader)
        
        # 本地引用，方便访问
        self.downloader_serial = original_downloader
        
        # 传递重要属性到本地，避免总是通过__getattr__访问
        self.client = self.downloader_serial.client
        self.ui_config_manager = self.downloader_serial.ui_config_manager
        self.channel_resolver = self.downloader_serial.channel_resolver
        self.history_manager = self.downloader_serial.history_manager
        self.app = self.downloader_serial.app
        
        # 复制重要属性
        self.use_keywords = self.downloader_serial.use_keywords
        self.download_path = self.downloader_serial.download_path
    
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
                
            # 处理串行下载器特有的事件类型
            if event_type == "progress":
                if len(args) >= 2:
                    current = args[0]
                    total = args[1]
                    filename = args[2] if len(args) > 2 else ""
                    self.progress_updated.emit(current, total, filename)
                    logger.debug(f"发射progress_updated信号: {current}/{total} - {filename}")
            
            elif event_type == "download_complete":
                if len(args) >= 3:
                    message_id = args[0]
                    filename = args[1]
                    file_size = args[2]
                    self.download_completed.emit(message_id, filename, file_size)
                    logger.debug(f"发射download_completed信号: msg_id={message_id}, file={filename}")
            
            elif event_type == "all_downloads_complete":
                self.all_downloads_completed.emit()
                logger.debug("发射all_downloads_completed信号")
                
        except Exception as e:
            logger.error(f"发射Qt信号时发生错误: {e}")
    
    # 包装关键方法，以便在调用前后添加信号发射
    async def download_media_from_channels(self):
        """包装下载方法，添加信号发射
            
        Returns:
            下载结果
        """
        try:
            # 发送开始状态
            self.status_updated.emit("开始串行下载媒体文件...")
            
            # 调用原始方法
            result = await self.downloader_serial.download_media_from_channels()
            
            # 确保发送完成信号
            self.all_downloads_completed.emit()
            
            return result
            
        except Exception as e:
            # 发送错误信号
            self.error_occurred.emit(f"串行下载过程中发生错误: {e}", "")
            # 重新抛出异常
            raise
            
    def set_keywords_mode(self, enabled: bool = False):
        """设置关键词下载模式
        
        Args:
            enabled: 是否启用关键词模式
        """
        # 调用原始方法
        self.downloader_serial.set_keywords_mode(enabled)
        
        # 更新本地属性
        self.use_keywords = self.downloader_serial.use_keywords
        
        # 发送状态更新信号
        mode_text = "开启" if enabled else "关闭"
        self.status_updated.emit(f"串行下载器关键词模式: {mode_text}")
        logger.debug(f"串行下载器关键词模式设置为: {mode_text}") 