"""
上传器模块
负责上传本地文件或下载的临时文件到目标频道，组织媒体组，处理多频道分发
"""

import os
import asyncio
import glob
from typing import List, Dict, Any, Union, Optional, Tuple
from pathlib import Path

from pyrogram import Client
from pyrogram.types import Message, InputMediaPhoto, InputMediaVideo, InputMediaAudio, InputMediaDocument
from pyrogram.errors import FloodWait

from tg_manager.utils.logger import get_logger
from tg_manager.utils.retry_manager import RetryManager
from tg_manager.services.channel_resolver import ChannelResolver
from tg_manager.services.history_manager import HistoryManager

logger = get_logger("uploader")


class Uploader:
    """
    上传器类，用于上传本地文件到Telegram频道
    """
    
    # 媒体组最大文件数
    MAX_MEDIA_GROUP_SIZE = 10
    
    # 支持的媒体类型扩展名映射
    MEDIA_EXTENSIONS = {
        "photo": [".jpg", ".jpeg", ".png", ".webp"],
        "video": [".mp4", ".avi", ".mkv", ".mov", ".flv", ".webm"],
        "document": [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".rar", ".7z", ".tar", ".gz"],
        "audio": [".mp3", ".ogg", ".m4a", ".wav", ".flac", ".aac"]
    }
    
    def __init__(self, 
                 client: Client,
                 channel_resolver: ChannelResolver,
                 history_manager: HistoryManager,
                 max_retries: int = 3,
                 timeout: int = 300,
                 caption_template: str = "{filename}"):
        """
        初始化上传器
        
        Args:
            client: Pyrogram客户端实例
            channel_resolver: 频道解析器实例
            history_manager: 历史记录管理器实例
            max_retries: 上传失败后的最大重试次数
            timeout: 上传超时时间（秒）
            caption_template: 标题模板，支持{filename}变量
        """
        self.client = client
        self.channel_resolver = channel_resolver
        self.history_manager = history_manager
        self.retry_manager = RetryManager(max_retries=max_retries, timeout=timeout)
        self.caption_template = caption_template
    
    async def upload_directory(self, 
                              directory: str, 
                              target_channels: List[str],
                              remove_after_upload: bool = False) -> Dict[str, Any]:
        """
        上传指定目录中的文件到目标频道
        
        Args:
            directory: 本地目录路径
            target_channels: 目标频道列表
            remove_after_upload: 上传成功后是否删除本地文件
            
        Returns:
            上传结果统计信息
        """
        if not os.path.exists(directory) or not os.path.isdir(directory):
            logger.error(f"目录不存在或不是有效目录: {directory}")
            return {"status": "failed", "error": "目录不存在或不是有效目录"}
        
        # 获取媒体组列表
        media_groups = self._scan_media_groups(directory)
        if not media_groups:
            logger.warning(f"目录中没有找到有效的媒体文件: {directory}")
            return {"status": "success", "uploaded": 0, "skipped": 0, "failed": 0, "message": "目录中没有找到有效的媒体文件"}
        
        logger.info(f"找到 {len(media_groups)} 个媒体组，准备上传到 {len(target_channels)} 个频道")
        
        # 上传统计信息
        stats = {
            "total_groups": len(media_groups),
            "uploaded_groups": 0,
            "skipped_groups": 0,
            "failed_groups": 0,
            "total_files": sum(len(files) for _, files in media_groups),
            "uploaded_files": 0,
            "skipped_files": 0,
            "failed_files": 0,
            "channels": {}
        }
        
        # 初始化各频道的统计信息
        for channel in target_channels:
            stats["channels"][channel] = {
                "uploaded_groups": 0,
                "skipped_groups": 0,
                "failed_groups": 0,
                "uploaded_files": 0
            }
        
        # 逐个上传媒体组
        for group_caption, files in media_groups:
            group_uploaded = 0
            group_failed = 0
            
            for target_channel in target_channels:
                channel_info = await self.channel_resolver.get_channel_info(target_channel)
                if not channel_info:
                    logger.error(f"无法获取频道信息: {target_channel}")
                    stats["channels"][target_channel]["failed_groups"] += 1
                    group_failed += 1
                    continue
                
                # 检查是否已上传
                all_uploaded = True
                for file_path in files:
                    if not self.history_manager.is_file_uploaded(file_path, target_channel):
                        all_uploaded = False
                        break
                
                if all_uploaded:
                    logger.info(f"所有文件已上传到频道 {target_channel}，跳过")
                    stats["channels"][target_channel]["skipped_groups"] += 1
                    stats["skipped_files"] += len(files)
                    continue
                
                # 上传媒体组
                try:
                    upload_result = await self._upload_media_group(
                        files, 
                        channel_info.channel_id, 
                        group_caption
                    )
                    
                    if upload_result["status"] == "success":
                        # 更新上传历史记录
                        for file_info in upload_result["files"]:
                            if file_info["status"] == "success":
                                self.history_manager.add_uploaded_file(
                                    file_info["file_path"],
                                    target_channel,
                                    file_info["file_size"],
                                    file_info["media_type"]
                                )
                                stats["uploaded_files"] += 1
                                stats["channels"][target_channel]["uploaded_files"] += 1
                            else:
                                stats["failed_files"] += 1
                        
                        stats["channels"][target_channel]["uploaded_groups"] += 1
                        group_uploaded += 1
                    else:
                        stats["channels"][target_channel]["failed_groups"] += 1
                        stats["failed_files"] += len(files)
                        group_failed += 1
                
                except Exception as e:
                    logger.error(f"上传媒体组到 {target_channel} 失败: {e}")
                    stats["channels"][target_channel]["failed_groups"] += 1
                    stats["failed_files"] += len(files)
                    group_failed += 1
            
            # 更新媒体组统计信息
            if group_uploaded == len(target_channels):
                stats["uploaded_groups"] += 1
                # 如果所有频道都上传成功，且配置了删除选项，则删除本地文件
                if remove_after_upload:
                    for file_path in files:
                        try:
                            os.remove(file_path)
                            logger.debug(f"已删除本地文件: {file_path}")
                        except Exception as e:
                            logger.warning(f"删除本地文件失败: {file_path}, 错误: {e}")
            elif group_failed == len(target_channels):
                stats["failed_groups"] += 1
            else:
                stats["skipped_groups"] += 1
        
        logger.info(f"上传完成，总计: {stats['total_groups']} 个媒体组, "
                   f"上传成功: {stats['uploaded_groups']}, "
                   f"跳过: {stats['skipped_groups']}, "
                   f"失败: {stats['failed_groups']}")
        
        return {
            "status": "success",
            "stats": stats
        }
    
    async def _upload_media_group(self, 
                                 files: List[str], 
                                 chat_id: int, 
                                 caption: Optional[str] = None) -> Dict[str, Any]:
        """
        上传媒体组到指定频道
        
        Args:
            files: 文件路径列表
            chat_id: 目标频道ID
            caption: 媒体组标题
            
        Returns:
            上传结果信息
        """
        # 使用实例方法进行重试
        async def upload_media_group_with_retry():
            if not files:
                return {"status": "failed", "error": "没有文件可上传"}
            
            # 限制媒体组大小
            if len(files) > self.MAX_MEDIA_GROUP_SIZE:
                logger.warning(f"媒体组文件数量超过限制 ({len(files)} > {self.MAX_MEDIA_GROUP_SIZE})，将被分割")
                # 分割成多个媒体组
                results = []
                for i in range(0, len(files), self.MAX_MEDIA_GROUP_SIZE):
                    chunk = files[i:i + self.MAX_MEDIA_GROUP_SIZE]
                    result = await self._upload_media_group(chunk, chat_id, caption)
                    results.append(result)
                
                # 合并结果
                merged_result = {
                    "status": "success" if all(r["status"] == "success" for r in results) else "partial_success",
                    "files": []
                }
                for result in results:
                    if "files" in result:
                        merged_result["files"].extend(result["files"])
                
                return merged_result
            
            # 处理单个文件
            if len(files) == 1:
                return await self._upload_single_file(files[0], chat_id, caption)
            
            # 准备媒体组
            media_group = []
            file_infos = []
            
            for file_path in files:
                media_type = self._get_media_type_from_file(file_path)
                file_size = os.path.getsize(file_path)
                
                # 根据文件类型创建对应的InputMedia对象
                if media_type == "photo":
                    media = InputMediaPhoto(file_path)
                elif media_type == "video":
                    media = InputMediaVideo(file_path)
                elif media_type == "audio":
                    media = InputMediaAudio(file_path)
                else:
                    # 默认作为文档处理
                    media = InputMediaDocument(file_path)
                
                # 为第一个媒体添加标题
                if len(media_group) == 0 and caption:
                    media.caption = caption
                
                media_group.append(media)
                
                file_infos.append({
                    "file_path": file_path,
                    "media_type": media_type,
                    "file_size": file_size,
                    "status": "pending"
                })
            
            # 尝试上传媒体组
            try:
                # 处理FloodWait异常
                while True:
                    try:
                        await self.client.send_media_group(chat_id, media_group)
                        break
                    except FloodWait as e:
                        logger.warning(f"触发FloodWait，等待 {e.x} 秒")
                        await asyncio.sleep(e.x)
                
                # 标记所有文件为成功
                for file_info in file_infos:
                    file_info["status"] = "success"
                
                logger.info(f"成功上传媒体组 ({len(files)} 个文件) 到频道 {chat_id}")
                
                return {
                    "status": "success",
                    "files": file_infos
                }
            
            except Exception as e:
                logger.error(f"上传媒体组失败: {e}")
                
                # 标记所有文件为失败
                for file_info in file_infos:
                    file_info["status"] = "failed"
                    file_info["error"] = str(e)
                
                return {
                    "status": "failed",
                    "error": str(e),
                    "files": file_infos
                }
                
        # 使用重试管理器执行上传
        try:
            return await self.retry_manager.retry_async(upload_media_group_with_retry)
        except Exception as e:
            logger.error(f"重试上传媒体组失败: {e}", exc_info=True)
            return {"status": "failed", "error": str(e)}
    
    async def _upload_single_file(self, 
                                 file_path: str, 
                                 chat_id: int, 
                                 caption: Optional[str] = None) -> Dict[str, Any]:
        """
        上传单个文件到指定频道
        
        Args:
            file_path: 文件路径
            chat_id: 目标频道ID
            caption: 文件标题
            
        Returns:
            上传结果信息
        """
        # 使用实例方法进行重试
        async def upload_single_file_with_retry():
            if not os.path.exists(file_path):
                return {"status": "failed", "error": f"文件不存在: {file_path}"}
            
            media_type = self._get_media_type_from_file(file_path)
            file_size = os.path.getsize(file_path)
            
            # 处理标题
            if caption is None:
                file_name = os.path.basename(file_path)
                caption = self.caption_template.format(filename=file_name)
            
            file_info = {
                "file_path": file_path,
                "media_type": media_type,
                "file_size": file_size,
                "status": "pending"
            }
            
            try:
                # 根据媒体类型上传文件
                if media_type == "photo":
                    while True:
                        try:
                            await self.client.send_photo(chat_id, file_path, caption=caption)
                            break
                        except FloodWait as e:
                            logger.warning(f"触发FloodWait，等待 {e.x} 秒")
                            await asyncio.sleep(e.x)
                
                elif media_type == "video":
                    while True:
                        try:
                            await self.client.send_video(chat_id, file_path, caption=caption)
                            break
                        except FloodWait as e:
                            logger.warning(f"触发FloodWait，等待 {e.x} 秒")
                            await asyncio.sleep(e.x)
                
                elif media_type == "audio":
                    while True:
                        try:
                            await self.client.send_audio(chat_id, file_path, caption=caption)
                            break
                        except FloodWait as e:
                            logger.warning(f"触发FloodWait，等待 {e.x} 秒")
                            await asyncio.sleep(e.x)
                
                else:
                    # 默认作为文档处理
                    while True:
                        try:
                            await self.client.send_document(chat_id, file_path, caption=caption)
                            break
                        except FloodWait as e:
                            logger.warning(f"触发FloodWait，等待 {e.x} 秒")
                            await asyncio.sleep(e.x)
                
                logger.info(f"成功上传文件 '{os.path.basename(file_path)}' 到频道 {chat_id}")
                file_info["status"] = "success"
                
                return {
                    "status": "success",
                    "files": [file_info]
                }
            
            except Exception as e:
                logger.error(f"上传文件 '{os.path.basename(file_path)}' 失败: {e}")
                file_info["status"] = "failed"
                file_info["error"] = str(e)
                
                return {
                    "status": "failed",
                    "error": str(e),
                    "files": [file_info]
                }
                
        # 使用重试管理器执行上传
        try:
            return await self.retry_manager.retry_async(upload_single_file_with_retry)
        except Exception as e:
            logger.error(f"重试上传文件失败: {e}", exc_info=True)
            return {"status": "failed", "error": str(e), "files": [{"file_path": file_path, "status": "failed", "error": str(e)}]}
    
    def _scan_media_groups(self, directory: str) -> List[Tuple[str, List[str]]]:
        """
        扫描目录，组织媒体组
        
        Args:
            directory: 本地目录路径
            
        Returns:
            媒体组列表，每个元素为 (标题, 文件路径列表) 元组
        """
        groups = []
        
        # 检查目录是否是上传根目录
        if self._is_upload_root_directory(directory):
            # 扫描子目录作为媒体组
            for subdir in os.listdir(directory):
                subdir_path = os.path.join(directory, subdir)
                if os.path.isdir(subdir_path):
                    files = self._get_media_files_in_directory(subdir_path)
                    if files:
                        groups.append((subdir, files))
        else:
            # 将当前目录作为一个媒体组
            files = self._get_media_files_in_directory(directory)
            if files:
                dir_name = os.path.basename(directory)
                groups.append((dir_name, files))
        
        return groups
    
    def _is_upload_root_directory(self, directory: str) -> bool:
        """
        检查目录是否是上传根目录（包含子目录作为媒体组）
        
        Args:
            directory: 本地目录路径
            
        Returns:
            如果是上传根目录则返回True，否则返回False
        """
        # 检查是否有子目录，且子目录中有媒体文件
        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)
            if os.path.isdir(item_path) and self._get_media_files_in_directory(item_path):
                return True
        
        return False
    
    def _get_media_files_in_directory(self, directory: str) -> List[str]:
        """
        获取目录中的媒体文件
        
        Args:
            directory: 本地目录路径
            
        Returns:
            媒体文件路径列表
        """
        if not os.path.exists(directory) or not os.path.isdir(directory):
            return []
        
        # 获取所有文件
        files = []
        for root, _, filenames in os.walk(directory):
            for filename in filenames:
                file_path = os.path.join(root, filename)
                # 检查是否是支持的媒体文件
                if self._is_supported_media_file(file_path):
                    files.append(file_path)
        
        # 按文件名排序
        files.sort()
        
        return files
    
    def _is_supported_media_file(self, file_path: str) -> bool:
        """
        检查文件是否是支持的媒体文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            如果是支持的媒体文件则返回True，否则返回False
        """
        ext = os.path.splitext(file_path)[1].lower()
        
        for media_type, extensions in self.MEDIA_EXTENSIONS.items():
            if ext in extensions:
                return True
        
        return False
    
    def _get_media_type_from_file(self, file_path: str) -> str:
        """
        根据文件扩展名获取媒体类型
        
        Args:
            file_path: 文件路径
            
        Returns:
            媒体类型字符串
        """
        ext = os.path.splitext(file_path)[1].lower()
        
        for media_type, extensions in self.MEDIA_EXTENSIONS.items():
            if ext in extensions:
                return media_type
        
        # 默认作为文档处理
        return "document" 