"""
消息下载器，负责下载消息中的媒体文件
"""

import asyncio
from pathlib import Path
from typing import List, Tuple, Optional

from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait

from src.utils.logger import get_logger

# 导入pyropatch FloodWait处理器
try:
    from src.utils.pyropatch_flood_handler import (
        execute_with_pyropatch_flood_wait,
        is_pyropatch_available
    )
    PYROPATCH_AVAILABLE = True
except ImportError:
    PYROPATCH_AVAILABLE = False

# 导入原有FloodWait处理器作为备选
try:
    from src.utils.flood_wait_handler import FloodWaitHandler, execute_with_flood_wait
    FALLBACK_HANDLER_AVAILABLE = True
except ImportError:
    FALLBACK_HANDLER_AVAILABLE = False

_logger = get_logger()

class MessageDownloader:
    """
    消息下载器，负责下载消息中的媒体文件
    集成pyropatch和内置FloodWait处理器，提供智能限流处理
    """
    
    def __init__(self, client: Client):
        """
        初始化消息下载器
        
        Args:
            client: Pyrogram客户端实例
        """
        self.client = client
        
        # 选择最佳可用的FloodWait处理器
        if PYROPATCH_AVAILABLE and is_pyropatch_available():
            self._flood_wait_method = "pyropatch"
            _logger.info("MessageDownloader: 使用pyropatch FloodWait处理器")
        elif FALLBACK_HANDLER_AVAILABLE:
            self._flood_wait_method = "fallback"
            self.flood_wait_handler = FloodWaitHandler(max_retries=3, base_delay=1.0)
            _logger.info("MessageDownloader: 使用内置FloodWait处理器")
        else:
            self._flood_wait_method = "none"
            _logger.warning("MessageDownloader: 未找到可用的FloodWait处理器")
    
    async def download_messages(self, messages: List[Message], download_dir: Path, chat_id: int) -> List[Tuple[Path, str]]:
        """
        下载消息中的媒体文件
        
        Args:
            messages: 消息列表
            download_dir: 下载目录
            chat_id: 频道ID
            
        Returns:
            List[Tuple[Path, str]]: 下载的文件路径和媒体类型列表
        """
        downloaded_files = []
        
        for message in messages:
            try:
                download_result = await self._download_single_message(message, download_dir, chat_id)
                if download_result:
                    downloaded_files.append(download_result)
            
            except Exception as e:
                _logger.error(f"下载消息 {message.id} 的媒体文件失败: {e}")
                # 记录详细错误信息
                import traceback
                error_details = traceback.format_exc()
                _logger.error(f"下载错误详情:\n{error_details}")
                continue
        
        return downloaded_files
    
    async def _execute_with_flood_wait(self, func, *args, **kwargs):
        """
        统一的FloodWait处理执行器，根据可用性选择最佳处理器
        
        Args:
            func: 要执行的函数
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            函数执行结果
        """
        if self._flood_wait_method == "pyropatch":
            return await execute_with_pyropatch_flood_wait(func, *args, max_retries=3, **kwargs)
        elif self._flood_wait_method == "fallback":
            return await self.flood_wait_handler.handle_flood_wait(func, *args, **kwargs)
        else:
            # 没有FloodWait处理器，直接执行
            return await func(*args, **kwargs)
    
    async def _download_single_message(self, message: Message, download_dir: Path, chat_id: int) -> Optional[Tuple[Path, str]]:
        """
        下载单个消息的媒体文件，使用智能FloodWait处理器
        
        Args:
            message: 消息对象
            download_dir: 下载目录
            chat_id: 频道ID
            
        Returns:
            Optional[Tuple[Path, str]]: 下载成功返回(文件路径, 媒体类型)，失败返回None
        """
        if message.photo:
            # 下载照片
            file_path = download_dir / f"{chat_id}_{message.id}_photo.jpg"
            
            async def download_photo():
                await self.client.download_media(message, file_name=str(file_path))
                return file_path, "photo"
            
            result = await self._execute_with_flood_wait(download_photo)
            if result:
                file_path, media_type = result
                # 检查下载的文件大小
                if file_path.exists() and file_path.stat().st_size > 0:
                    _logger.debug(f"照片下载成功: {file_path} ({file_path.stat().st_size} 字节)")
                    return (file_path, media_type)
                else:
                    _logger.warning(f"下载的照片文件大小为0或不存在，跳过: {file_path}")
                    if file_path.exists():
                        file_path.unlink()  # 删除0字节文件
        
        elif message.video:
            # 下载视频
            if message.video.file_name:
                # 处理文件名以确保安全
                safe_file_name = self._get_safe_path_name(message.video.file_name)
                # 如果文件名在处理后为空，使用默认名称
                if not safe_file_name or safe_file_name.strip() == "":
                    safe_file_name = f"{chat_id}_{message.id}_video.mp4"
            else:
                safe_file_name = f"{chat_id}_{message.id}_video.mp4"
                
            file_path = download_dir / safe_file_name
            
            async def download_video():
                await self.client.download_media(message, file_name=str(file_path))
                return file_path, "video"
            
            result = await self._execute_with_flood_wait(download_video)
            if result:
                file_path, media_type = result
                # 检查下载的文件大小
                if file_path.exists() and file_path.stat().st_size > 0:
                    _logger.debug(f"视频下载成功: {file_path} ({file_path.stat().st_size} 字节)")
                    return (file_path, media_type)
                else:
                    _logger.warning(f"下载的视频文件大小为0或不存在，跳过: {file_path}")
                    if file_path.exists():
                        file_path.unlink()  # 删除0字节文件
        
        elif message.document:
            # 下载文档
            if message.document.file_name:
                # 处理文件名以确保安全
                safe_file_name = self._get_safe_path_name(message.document.file_name)
                # 如果文件名在处理后为空，使用默认名称
                if not safe_file_name or safe_file_name.strip() == "":
                    safe_file_name = f"{chat_id}_{message.id}_document"
            else:
                safe_file_name = f"{chat_id}_{message.id}_document"
                
            file_path = download_dir / safe_file_name
            
            async def download_document():
                await self.client.download_media(message, file_name=str(file_path))
                return file_path, "document"
            
            result = await self._execute_with_flood_wait(download_document)
            if result:
                file_path, media_type = result
                # 检查下载的文件大小
                if file_path.exists() and file_path.stat().st_size > 0:
                    _logger.debug(f"文档下载成功: {file_path} ({file_path.stat().st_size} 字节)")
                    return (file_path, media_type)
                else:
                    _logger.warning(f"下载的文档文件大小为0或不存在，跳过: {file_path}")
                    if file_path.exists():
                        file_path.unlink()  # 删除0字节文件
        
        elif message.audio:
            # 下载音频
            if message.audio.file_name:
                # 处理文件名以确保安全
                safe_file_name = self._get_safe_path_name(message.audio.file_name)
                # 如果文件名在处理后为空，使用默认名称
                if not safe_file_name or safe_file_name.strip() == "":
                    safe_file_name = f"{chat_id}_{message.id}_audio.mp3"
            else:
                safe_file_name = f"{chat_id}_{message.id}_audio.mp3"
                
            file_path = download_dir / safe_file_name
            
            async def download_audio():
                await self.client.download_media(message, file_name=str(file_path))
                return file_path, "audio"
            
            result = await self._execute_with_flood_wait(download_audio)
            if result:
                file_path, media_type = result
                # 检查下载的文件大小
                if file_path.exists() and file_path.stat().st_size > 0:
                    _logger.debug(f"音频下载成功: {file_path} ({file_path.stat().st_size} 字节)")
                    return (file_path, media_type)
                else:
                    _logger.warning(f"下载的音频文件大小为0或不存在，跳过: {file_path}")
                    if file_path.exists():
                        file_path.unlink()  # 删除0字节文件
        
        elif message.animation:
            # 下载动画(GIF)
            file_path = download_dir / f"{chat_id}_{message.id}_animation.mp4"
            
            async def download_animation():
                await self.client.download_media(message, file_name=str(file_path))
                return file_path, "video"  # 作为视频上传
            
            result = await self._execute_with_flood_wait(download_animation)
            if result:
                file_path, media_type = result
                # 检查下载的文件大小
                if file_path.exists() and file_path.stat().st_size > 0:
                    _logger.debug(f"动画下载成功: {file_path} ({file_path.stat().st_size} 字节)")
                    return (file_path, media_type)
                else:
                    _logger.warning(f"下载的动画文件大小为0或不存在，跳过: {file_path}")
                    if file_path.exists():
                        file_path.unlink()  # 删除0字节文件
        
        return None  # 没有可下载的媒体
    
    async def _retry_download_media(self, message: Message, download_dir: Path, chat_id: int) -> Optional[Tuple[Path, str]]:
        """
        DEPRECATED: 保留用于向后兼容性
        使用_download_single_message方法替代
        """
        _logger.warning("_retry_download_media方法已废弃，请使用_download_single_message")
        return await self._download_single_message(message, download_dir, chat_id)
    
    def _get_safe_path_name(self, path_str: str) -> str:
        """
        获取安全的路径名称，移除或替换不安全的字符
        
        Args:
            path_str: 原始路径字符串
            
        Returns:
            str: 安全的路径字符串
        """
        if not path_str:
            return ""
        
        # 移除或替换Windows和Unix系统中的危险字符
        import re
        # 替换路径分隔符和其他危险字符
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', path_str)
        # 移除前后空格
        safe_name = safe_name.strip()
        # 限制长度，避免路径过长
        if len(safe_name) > 255:
            safe_name = safe_name[:255]
        
        return safe_name 