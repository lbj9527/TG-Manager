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

_logger = get_logger()

class MessageDownloader:
    """
    消息下载器，负责下载消息中的媒体文件
    """
    
    def __init__(self, client: Client):
        """
        初始化消息下载器
        
        Args:
            client: Pyrogram客户端实例
        """
        self.client = client
    
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
                if message.photo:
                    # 下载照片
                    file_path = download_dir / f"{chat_id}_{message.id}_photo.jpg"
                    await self.client.download_media(message, file_name=str(file_path))
                    downloaded_files.append((file_path, "photo"))
                    _logger.debug(f"照片下载成功: {file_path}")
                
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
                    await self.client.download_media(message, file_name=str(file_path))
                    downloaded_files.append((file_path, "video"))
                    _logger.debug(f"视频下载成功: {file_path}")
                
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
                    await self.client.download_media(message, file_name=str(file_path))
                    downloaded_files.append((file_path, "document"))
                    _logger.debug(f"文档下载成功: {file_path}")
                
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
                    await self.client.download_media(message, file_name=str(file_path))
                    downloaded_files.append((file_path, "audio"))
                    _logger.debug(f"音频下载成功: {file_path}")
                
                elif message.animation:
                    # 下载动画(GIF)
                    file_path = download_dir / f"{chat_id}_{message.id}_animation.mp4"
                    await self.client.download_media(message, file_name=str(file_path))
                    downloaded_files.append((file_path, "video"))  # 作为视频上传
                    _logger.debug(f"动画下载成功: {file_path}")
            
            except FloodWait as e:
                _logger.warning(f"下载媒体文件时遇到限制，等待 {e.x} 秒")
                await asyncio.sleep(e.x)
                # 重试下载
                retry_result = await self._retry_download_media(message, download_dir, chat_id)
                if retry_result:
                    downloaded_files.append(retry_result)
            
            except Exception as e:
                _logger.error(f"下载消息 {message.id} 的媒体文件失败: {e}")
                # 记录详细错误信息
                import traceback
                error_details = traceback.format_exc()
                _logger.error(f"下载错误详情:\n{error_details}")
                continue
        
        return downloaded_files
        
    async def _retry_download_media(self, message: Message, download_dir: Path, chat_id: int) -> Optional[Tuple[Path, str]]:
        """
        重试下载媒体文件
        
        Args:
            message: 消息对象
            download_dir: 下载目录
            chat_id: 频道ID
            
        Returns:
            Optional[Tuple[Path, str]]: 下载成功返回(文件路径, 媒体类型)，失败返回None
        """
        retry_count = 0
        max_retries = 3  # 使用默认值，可以从配置中获取
        
        while retry_count < max_retries:
            try:
                if message.photo:
                    file_path = download_dir / f"{chat_id}_{message.id}_photo.jpg"
                    await self.client.download_media(message, file_name=str(file_path))
                    return (file_path, "photo")
                
                elif message.video:
                    if message.video.file_name:
                        # 处理文件名以确保安全
                        safe_file_name = self._get_safe_path_name(message.video.file_name)
                        # 如果文件名在处理后为空，使用默认名称
                        if not safe_file_name or safe_file_name.strip() == "":
                            safe_file_name = f"{chat_id}_{message.id}_video.mp4"
                    else:
                        safe_file_name = f"{chat_id}_{message.id}_video.mp4"
                        
                    file_path = download_dir / safe_file_name
                    await self.client.download_media(message, file_name=str(file_path))
                    return (file_path, "video")
                
                elif message.document:
                    if message.document.file_name:
                        # 处理文件名以确保安全
                        safe_file_name = self._get_safe_path_name(message.document.file_name)
                        # 如果文件名在处理后为空，使用默认名称
                        if not safe_file_name or safe_file_name.strip() == "":
                            safe_file_name = f"{chat_id}_{message.id}_document"
                    else:
                        safe_file_name = f"{chat_id}_{message.id}_document"
                        
                    file_path = download_dir / safe_file_name
                    await self.client.download_media(message, file_name=str(file_path))
                    return (file_path, "document")
                
                elif message.audio:
                    if message.audio.file_name:
                        # 处理文件名以确保安全
                        safe_file_name = self._get_safe_path_name(message.audio.file_name)
                        # 如果文件名在处理后为空，使用默认名称
                        if not safe_file_name or safe_file_name.strip() == "":
                            safe_file_name = f"{chat_id}_{message.id}_audio.mp3"
                    else:
                        safe_file_name = f"{chat_id}_{message.id}_audio.mp3"
                        
                    file_path = download_dir / safe_file_name
                    await self.client.download_media(message, file_name=str(file_path))
                    return (file_path, "audio")
                
                elif message.animation:
                    file_path = download_dir / f"{chat_id}_{message.id}_animation.mp4"
                    await self.client.download_media(message, file_name=str(file_path))
                    return (file_path, "video")
                
                return None
            
            except FloodWait as e:
                _logger.warning(f"重试下载时遇到限制，等待 {e.x} 秒")
                await asyncio.sleep(e.x)
            
            except Exception as e:
                retry_count += 1
                _logger.error(f"重试下载失败 (尝试 {retry_count}/{max_retries}): {e}")
                # 记录详细错误信息
                import traceback
                error_details = traceback.format_exc()
                _logger.error(f"重试下载错误详情:\n{error_details}")
                
                if retry_count >= max_retries:
                    break
                await asyncio.sleep(2 * retry_count)  # 指数退避
        
        return None
        
    def _get_safe_path_name(self, path_str: str) -> str:
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
            import hashlib
            safe_str = hashlib.md5(path_str.encode()).hexdigest()
            
        return safe_str 