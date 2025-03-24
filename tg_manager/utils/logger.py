"""
日志记录模块
提供统一的日志记录功能
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


class Logger:
    """日志记录器类，提供统一的日志记录接口"""
    
    def __init__(self, name: str = "tg_manager", log_level: int = logging.INFO):
        """
        初始化日志记录器
        
        Args:
            name: 日志记录器名称
            log_level: 日志级别，默认为INFO
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(log_level)
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        
        # 清除现有的处理器
        if self.logger.handlers:
            self.logger.handlers.clear()
        
        # 添加控制台处理器
        self._add_console_handler()
        
        # 添加文件处理器
        self._add_file_handler()
    
    def _add_console_handler(self) -> None:
        """添加控制台日志处理器"""
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # 设置日志格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(console_handler)
    
    def _add_file_handler(self) -> None:
        """添加文件日志处理器"""
        log_file = self.log_dir / "tg_manager.log"
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        
        # 设置日志格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
    
    def get_logger(self) -> logging.Logger:
        """获取日志记录器实例"""
        return self.logger


# 创建默认日志记录器
default_logger = Logger().get_logger()

# 提供快捷函数
def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    获取指定名称的日志记录器
    
    Args:
        name: 日志记录器名称，如果为None则返回默认日志记录器
        
    Returns:
        日志记录器实例
    """
    if name is None:
        return default_logger
    return logging.getLogger(name) 