"""
TG-Manager 文件工具类
提供文件操作相关的工具函数
"""

import os
import hashlib
from pathlib import Path
from typing import Union, Optional
from src.utils.logger import get_logger

logger = get_logger()

def calculate_file_hash(file_path: Union[str, Path], algorithm: str = 'md5', buffer_size: int = 65536) -> Optional[str]:
    """
    计算文件的哈希值
    
    Args:
        file_path: 文件路径
        algorithm: 哈希算法，默认为md5，支持sha1、sha256等
        buffer_size: 读取缓冲区大小，默认64KB
        
    Returns:
        Optional[str]: 文件哈希值，如果文件不存在或读取失败则返回None
    """
    if isinstance(file_path, str):
        file_path = Path(file_path)
    
    if not file_path.exists() or not file_path.is_file():
        logger.warning(f"文件不存在或不是文件: {file_path}")
        return None
    
    try:
        hash_obj = getattr(hashlib, algorithm)()
        
        with open(file_path, 'rb') as f:
            while True:
                data = f.read(buffer_size)
                if not data:
                    break
                hash_obj.update(data)
        
        return hash_obj.hexdigest()
    except Exception as e:
        logger.error(f"计算文件哈希值时出错: {e}")
        return None

def get_file_size(file_path: Union[str, Path]) -> int:
    """
    获取文件大小
    
    Args:
        file_path: 文件路径
        
    Returns:
        int: 文件大小（字节）
    """
    if isinstance(file_path, str):
        file_path = Path(file_path)
    
    if not file_path.exists() or not file_path.is_file():
        return 0
    
    try:
        return file_path.stat().st_size
    except Exception as e:
        logger.error(f"获取文件大小时出错: {e}")
        return 0 