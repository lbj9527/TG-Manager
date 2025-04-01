"""
日志工具模块，提供统一的日志记录功能
"""

import os
import sys
from datetime import datetime
from pathlib import Path

from loguru import logger

# 创建日志目录
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# 生成日志文件名（按日期）
today = datetime.now().strftime('%Y%m%d')
daily_log_file = log_dir / f"tg_forwarder_{today}.log"
fixed_log_file = log_dir / "tg_manager.log"

# 清除默认处理器
logger.remove()

# 添加控制台处理器
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO"
)

# 添加按日期的文件处理器
logger.add(
    daily_log_file,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {function}:{line} - {message}",
    level="DEBUG",
    rotation="00:00",  # 每天零点创建新日志文件
    retention="30 days",  # 保留30天的日志文件
    encoding="utf-8"
)

# 添加固定名称的日志文件处理器
logger.add(
    fixed_log_file,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {function}:{line} - {message}",
    level="DEBUG",
    rotation="10 MB",  # 每10MB轮换
    retention=3,  # 保留3个备份
    encoding="utf-8"
)

def get_logger():
    """
    获取配置好的logger实例
    
    Returns:
        loguru.logger: 日志记录器实例
    """
    return logger 