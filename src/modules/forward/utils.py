"""
转发模块通用工具函数
"""

import hashlib
from pathlib import Path
import os
import shutil
from typing import List, Optional, Dict, Any, Union
from datetime import datetime

def get_safe_path_name(path_str: str) -> str:
    """
    将路径字符串转换为安全的文件名，移除无效字符
    
    Args:
        path_str: 原始路径字符串
        
    Returns:
        str: 处理后的安全路径字符串
    """
    # 替换URL分隔符
    safe_str = path_str.replace('://', '_').replace(':', '_')
    
    # 替换路径分隔符
    safe_str = safe_str.replace('\\', '_').replace('/', '_')
    
    # 替换其他不安全的文件名字符
    unsafe_chars = '<>:"|?*'
    for char in unsafe_chars:
        safe_str = safe_str.replace(char, '_')
        
    # 如果结果太长，取MD5哈希值
    if len(safe_str) > 100:
        safe_str = hashlib.md5(path_str.encode()).hexdigest()
        
    return safe_str

def ensure_temp_dir(base_path: Union[str, Path], session_prefix: str = None) -> Path:
    """
    确保临时目录存在，如果不存在则创建
    
    Args:
        base_path: 基础路径
        session_prefix: 会话前缀，默认为None
        
    Returns:
        Path: 临时目录路径
    """
    # 确保base_path是Path对象
    if isinstance(base_path, str):
        base_path = Path(base_path)
    
    # 创建基础目录
    base_path.mkdir(exist_ok=True, parents=True)
    
    # 创建带时间戳的会话目录
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if session_prefix:
        session_dir = base_path / f"{session_prefix}_{timestamp}"
    else:
        session_dir = base_path / timestamp
        
    session_dir.mkdir(exist_ok=True, parents=True)
    
    return session_dir

def clean_directory(dir_path: Union[str, Path]) -> bool:
    """
    清理目录
    
    Args:
        dir_path: 目录路径
        
    Returns:
        bool: 是否成功清理
    """
    # 确保dir_path是Path对象
    if isinstance(dir_path, str):
        dir_path = Path(dir_path)
    
    if not dir_path.exists():
        return True
    
    try:
        shutil.rmtree(dir_path)
        return True
    except Exception:
        return False

def estimate_media_size(message: Any) -> int:
    """
    估计媒体文件大小
    
    Args:
        message: 消息对象
        
    Returns:
        int: 预估的文件大小（字节）
    """
    if hasattr(message, 'photo') and message.photo:
        # 使用最大尺寸的照片
        if isinstance(message.photo, list):
            if len(message.photo) > 0:
                photo = message.photo[-1]  # 获取最大尺寸
                return photo.file_size if hasattr(photo, 'file_size') and photo.file_size else 0
        return 0
    elif hasattr(message, 'video') and message.video:
        return message.video.file_size if hasattr(message.video, 'file_size') and message.video.file_size else 0
    elif hasattr(message, 'document') and message.document:
        return message.document.file_size if hasattr(message.document, 'file_size') and message.document.file_size else 0
    elif hasattr(message, 'audio') and message.audio:
        return message.audio.file_size if hasattr(message.audio, 'file_size') and message.audio.file_size else 0
    elif hasattr(message, 'animation') and message.animation:
        return message.animation.file_size if hasattr(message.animation, 'file_size') and message.animation.file_size else 0
    elif hasattr(message, 'voice') and message.voice:
        return message.voice.file_size if hasattr(message.voice, 'file_size') and message.voice.file_size else 0
    elif hasattr(message, 'video_note') and message.video_note:
        return message.video_note.file_size if hasattr(message.video_note, 'file_size') and message.video_note.file_size else 0
    return 0 