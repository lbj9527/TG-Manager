"""
视频处理工具，用于提取视频第一帧作为缩略图
"""

import os
from pathlib import Path
from typing import Optional

from moviepy import VideoFileClip
from PIL import Image

from src.utils.logger import get_logger

logger = get_logger()

class VideoProcessor:
    """
    视频处理器，用于处理视频文件的相关操作
    """
    
    def __init__(self, thumb_dir: str = "tmp/thumb"):
        """
        初始化视频处理器
        
        Args:
            thumb_dir: 缩略图保存目录
        """
        self.thumb_dir = Path(thumb_dir)
        # 确保缩略图目录存在
        self.thumb_dir.mkdir(parents=True, exist_ok=True)
    
    def extract_thumbnail(self, video_path: str) -> Optional[str]:
        """
        从视频中提取第一帧作为缩略图
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            Optional[str]: 缩略图路径，如果失败则返回None
        """
        try:
            video_path = Path(video_path)
            if not video_path.exists():
                logger.error(f"视频文件不存在: {video_path}")
                return None
                
            # 生成缩略图文件名（使用视频文件名+.jpg）
            thumb_filename = f"{video_path.stem}_thumb.jpg"
            thumb_path = self.thumb_dir / thumb_filename
            
            # 提取视频第一帧
            with VideoFileClip(str(video_path)) as clip:
                # 获取第一帧
                frame = clip.get_frame(0)
                
                # 将帧保存为图片
                img = Image.fromarray(frame)
                
                # 调整图片尺寸，确保符合Telegram要求（最大320x320）
                width, height = img.size
                if width > 320 or height > 320:
                    # 保持宽高比缩小
                    ratio = min(320 / width, 320 / height)
                    new_width = int(width * ratio)
                    new_height = int(height * ratio)
                    img = img.resize((new_width, new_height), Image.LANCZOS)
                
                # 保存缩略图，压缩以确保文件大小不超过200KB
                quality = 85
                img.save(str(thumb_path), "JPEG", quality=quality, optimize=True)
                
                # 检查文件大小，如果超过200KB，降低质量并重新保存
                while thumb_path.stat().st_size > 200 * 1024 and quality > 10:
                    quality -= 10
                    img.save(str(thumb_path), "JPEG", quality=quality, optimize=True)
                
                logger.debug(f"成功为视频 {video_path.name} 创建缩略图: {thumb_path}")
                return str(thumb_path)
        
        except Exception as e:
            logger.error(f"提取视频缩略图失败: {video_path}, 错误: {e}")
            return None
    
    def delete_thumbnail(self, thumb_path: str) -> bool:
        """
        删除缩略图文件
        
        Args:
            thumb_path: 缩略图路径
            
        Returns:
            bool: 操作是否成功
        """
        try:
            if thumb_path and os.path.exists(thumb_path):
                os.remove(thumb_path)
                logger.debug(f"已删除缩略图: {thumb_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"删除缩略图失败: {thumb_path}, 错误: {e}")
            return False
    