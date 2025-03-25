"""
日志记录模块
提供统一的日志记录功能
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional, Dict


# 保存已创建的日志记录器
_loggers: Dict[str, logging.Logger] = {}


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    获取指定名称的日志记录器
    
    Args:
        name: 日志记录器名称，如果为None则返回根日志记录器
        
    Returns:
        日志记录器实例
    """
    # 默认使用根记录器名称
    logger_name = "tg_manager" if name is None else f"tg_manager.{name}"
    
    # 如果已创建过该记录器，直接返回
    if logger_name in _loggers:
        return _loggers[logger_name]
    
    # 创建新记录器
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    
    # 清除可能存在的旧处理器
    if logger.handlers:
        logger.handlers.clear()
    
    # 创建日志目录
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # 添加控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d:%(funcName)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # 添加文件处理器
    log_file = log_dir / "tg_manager.log"
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # 防止日志传播到父级记录器，避免重复
    logger.propagate = False
    
    # 保存记录器实例以便复用
    _loggers[logger_name] = logger
    
    return logger 