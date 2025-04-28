"""
视频处理工具，用于提取视频第一帧作为缩略图
"""

import os
from pathlib import Path
from typing import Optional, Dict, Tuple, Any, Union

from moviepy import VideoFileClip
from PIL import Image

from src.utils.logger import get_logger
from src.utils.resource_manager import ResourceManager, TempFile

logger = get_logger()

class VideoProcessor:
    """
    视频处理器，用于处理视频文件的相关操作
    """
    
    def __init__(self, resource_manager: Optional[ResourceManager] = None, thumb_dir: str = "tmp/thumb"):
        """
        初始化视频处理器
        
        Args:
            resource_manager: 资源管理器实例，如果为None则使用内部简单管理
            thumb_dir: 缩略图保存目录，当resource_manager为None时使用
        """
        self.resource_manager = resource_manager
        self.thumb_dir = Path(thumb_dir)
        # 缩略图路径与视频路径的映射
        self._thumb_map: Dict[str, str] = {}
        # 视频尺寸缓存
        self._video_dimensions: Dict[str, Tuple[int, int]] = {}
        # 视频时长缓存
        self._video_durations: Dict[str, float] = {}
        
        # 如果未提供资源管理器，则确保缩略图目录存在
        if resource_manager is None:
            # 确保缩略图目录存在
            self.thumb_dir.mkdir(parents=True, exist_ok=True)
    
    async def extract_thumbnail_async(self, video_path: str) -> Union[str, Tuple[str, int, int, float]]:
        """
        异步从视频中提取第一帧作为缩略图
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            Union[str, Tuple[str, int, int, float]]: 
                - 如果成功: 元组(缩略图路径, 宽度, 高度, 时长)
                - 如果失败: None
        """
        # 检查视频文件是否存在
        video_path_obj = Path(video_path)
        if not video_path_obj.exists():
            logger.error(f"视频文件不存在: {video_path}")
            return None
        
        # 如果使用资源管理器
        if self.resource_manager:
            async with TempFile(self.resource_manager, ".jpg", "thumbnails") as temp_file:
                # 提取缩略图和尺寸
                result = await self._extract_frame_to_file(video_path, temp_file.path)
                if not result or result[0] is not True:
                    return None
                
                _, width, height, duration = result
                
                # 将缩略图路径与视频路径关联
                thumb_path_str = str(temp_file.path)
                self._thumb_map[video_path] = thumb_path_str
                # 缓存视频尺寸
                self._video_dimensions[video_path] = (width, height)
                # 缓存视频时长
                self._video_durations[video_path] = duration
                
                return (thumb_path_str, width, height, duration)
        else:
            # 使用传统方式管理缩略图
            # 生成缩略图文件名（使用视频文件名+.jpg）
            thumb_filename = f"{video_path_obj.stem}_thumb.jpg"
            thumb_path = self.thumb_dir / thumb_filename
            
            # 提取缩略图和尺寸
            result = await self._extract_frame_to_file(video_path, thumb_path)
            if not result or result[0] is not True:
                return None
            
            _, width, height, duration = result
            
            # 将缩略图路径与视频路径关联
            thumb_path_str = str(thumb_path)
            self._thumb_map[video_path] = thumb_path_str
            # 缓存视频尺寸
            self._video_dimensions[video_path] = (width, height)
            # 缓存视频时长
            self._video_durations[video_path] = duration
            
            return (thumb_path_str, width, height, duration)
    
    async def _extract_frame_to_file(self, video_path: str, output_path: Path) -> Tuple[bool, int, int, float]:
        """
        从视频中提取第一帧并保存到指定文件，同时获取视频尺寸和时长
        
        Args:
            video_path: 视频文件路径
            output_path: 输出图片路径
            
        Returns:
            Tuple[bool, int, int, float]: (操作是否成功, 视频宽度, 视频高度, 视频时长(秒))
        """
        try:
            # 提取视频第一帧
            with VideoFileClip(str(video_path)) as clip:
                # 获取视频尺寸
                video_width, video_height = int(clip.w), int(clip.h)
                # 获取视频时长(秒)
                video_duration = float(clip.duration)
                
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
                img.save(str(output_path), "JPEG", quality=quality, optimize=True)
                
                # 检查文件大小，如果超过200KB，降低质量并重新保存
                while output_path.stat().st_size > 200 * 1024 and quality > 10:
                    quality -= 10
                    img.save(str(output_path), "JPEG", quality=quality, optimize=True)
                
                logger.debug(f"成功为视频 {Path(video_path).name} 创建缩略图: {output_path}, 视频尺寸: {video_width}x{video_height}, 时长: {video_duration}秒")
                return (True, video_width, video_height, video_duration)
        
        except Exception as e:
            logger.error(f"提取视频缩略图失败: {video_path}, 错误: {e}")
            return (False, 0, 0, 0.0)
    
    def extract_thumbnail(self, video_path: str) -> Union[str, Tuple[str, int, int, float]]:
        """
        从视频中提取第一帧作为缩略图（同步版本）
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            Union[str, Tuple[str, int, int, float]]: 
                - 如果成功: 元组(缩略图路径, 宽度, 高度, 时长)
                - 如果失败: None
        """
        try:
            video_path_obj = Path(video_path)
            if not video_path_obj.exists():
                logger.error(f"视频文件不存在: {video_path}")
                return None
            
            # 根据是否使用资源管理器决定保存路径
            if self.resource_manager:
                # 使用资源管理器创建临时文件
                thumb_path, resource_id = self.resource_manager.create_temp_file(
                    extension=".jpg", 
                    category="thumbnails"
                )
                # 记录资源ID与视频路径的关联
                self._thumb_map[video_path] = str(thumb_path)
            else:
                # 使用传统方式
                thumb_filename = f"{video_path_obj.stem}_thumb.jpg"
                thumb_path = self.thumb_dir / thumb_filename
                self._thumb_map[video_path] = str(thumb_path)
                
            # 提取视频第一帧和尺寸
            with VideoFileClip(str(video_path)) as clip:
                # 获取视频尺寸
                video_width, video_height = int(clip.w), int(clip.h)
                # 获取视频时长(秒)
                video_duration = float(clip.duration)
                
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
                
                # 缓存视频尺寸
                self._video_dimensions[video_path] = (video_width, video_height)
                # 缓存视频时长
                self._video_durations[video_path] = video_duration
                
                logger.debug(f"成功为视频 {video_path_obj.name} 创建缩略图: {thumb_path}, 视频尺寸: {video_width}x{video_height}, 时长: {video_duration}秒")
                return (str(thumb_path), video_width, video_height, video_duration)
        
        except Exception as e:
            logger.error(f"提取视频缩略图失败: {video_path}, 错误: {e}")
            return None
    
    def get_video_dimensions(self, video_path: str) -> Optional[Tuple[int, int]]:
        """
        获取视频的尺寸
        
        Args:
            video_path: a所提的路径
            
        Returns:
            Optional[Tuple[int, int]]: 视频尺寸 (宽, 高)，如果失败返回None
        """
        # 首先检查缓存
        if video_path in self._video_dimensions:
            return self._video_dimensions[video_path]
        
        try:
            with VideoFileClip(str(video_path)) as clip:
                width, height = int(clip.w), int(clip.h)
                # 缓存结果
                self._video_dimensions[video_path] = (width, height)
                return (width, height)
        except Exception as e:
            logger.error(f"获取视频尺寸失败: {video_path}, 错误: {e}")
            return None
    
    def get_video_duration(self, video_path: str) -> Optional[float]:
        """
        获取视频的时长
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            Optional[float]: 视频时长(秒)，如果失败返回None
        """
        # 首先检查缓存
        if video_path in self._video_durations:
            return self._video_durations[video_path]
        
        try:
            with VideoFileClip(str(video_path)) as clip:
                duration = float(clip.duration)
                # 缓存结果
                self._video_durations[video_path] = duration
                return duration
        except Exception as e:
            logger.error(f"获取视频时长失败: {video_path}, 错误: {e}")
            return None
    
    def delete_thumbnail(self, video_path: Optional[str] = None, thumb_path: Optional[str] = None) -> bool:
        """
        删除缩略图文件
        
        Args:
            video_path: 视频文件路径，如果提供则删除与该视频关联的缩略图
            thumb_path: 缩略图路径，如果video_path未提供则直接删除此路径的缩略图
            
        Returns:
            bool: 操作是否成功
        """
        try:
            # 确定要删除的缩略图路径
            path_to_delete = None
            resource_path = None
            
            if video_path and video_path in self._thumb_map:
                path_to_delete = self._thumb_map[video_path]
                # 从映射中移除
                del self._thumb_map[video_path]
                # 也清除尺寸缓存
                if video_path in self._video_dimensions:
                    del self._video_dimensions[video_path]
                resource_path = path_to_delete
            elif thumb_path:
                path_to_delete = thumb_path
                # 检查并更新映射
                for vid_path, thumb in list(self._thumb_map.items()):
                    if thumb == thumb_path:
                        del self._thumb_map[vid_path]
                        # 也清除尺寸缓存
                        if vid_path in self._video_dimensions:
                            del self._video_dimensions[vid_path]
                        break
                resource_path = path_to_delete
            else:
                return False
            
            # 根据是否使用资源管理器决定删除方式
            if self.resource_manager:
                # 尝试通过资源管理器释放资源
                result = self.resource_manager.release_resource(resource_path, force_delete=True)
                if result:
                    logger.debug(f"通过资源管理器删除缩略图: {path_to_delete}")
                    return True
                # 如果资源管理器没有管理这个资源，尝试直接删除
            
            # 直接删除文件
            if path_to_delete and os.path.exists(path_to_delete):
                os.remove(path_to_delete)
                logger.debug(f"直接删除缩略图: {path_to_delete}")
                return True
            
            return False
        except Exception as e:
            logger.error(f"删除缩略图失败: {thumb_path or video_path}, 错误: {e}")
            return False
    
    def clear_all_thumbnails(self) -> int:
        """
        清理所有缩略图
        
        Returns:
            int: 清理的缩略图数量
        """
        count = 0
        
        # 使用资源管理器清理或手动清理
        if self.resource_manager:
            # 通过资源管理器释放所有缩略图资源
            for video_path, thumb_path in list(self._thumb_map.items()):
                if self.resource_manager.release_resource(thumb_path, force_delete=True):
                    count += 1
                    del self._thumb_map[video_path]
        else:
            # 手动删除所有缩略图
            for video_path, thumb_path in list(self._thumb_map.items()):
                if os.path.exists(thumb_path):
                    try:
                        os.remove(thumb_path)
                        count += 1
                    except Exception as e:
                        logger.error(f"删除缩略图失败: {thumb_path}, 错误: {e}")
                
                # 从映射中移除
                del self._thumb_map[video_path]
            
            # 如果thumb_dir存在且是目录，尝试删除目录中的所有.jpg文件
            if self.thumb_dir.exists() and self.thumb_dir.is_dir():
                for jpg_file in self.thumb_dir.glob("*_thumb.jpg"):
                    try:
                        jpg_file.unlink()
                        count += 1
                    except Exception as e:
                        logger.error(f"删除缩略图文件失败: {jpg_file}, 错误: {e}")
        
        # 清空尺寸缓存
        self._video_dimensions.clear()
        
        logger.info(f"已清理 {count} 个缩略图")
        return count
    