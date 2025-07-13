"""
上传功能抽象基类

定义上传功能的通用接口，包括文件上传、媒体组上传、消息复制等功能。
"""

import asyncio
import hashlib
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from loguru import logger

from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait

from abstractions.base_handler import BaseHandler


class BaseUploader(BaseHandler):
    """
    上传功能抽象基类，为上传插件提供统一接口。
    
    所有上传插件都应该继承此类并实现必要的方法。
    """
    
    def __init__(self, client, config: Dict[str, Any]):
        """
        初始化上传器。
        
        Args:
            client: Telegram客户端实例
            config: 上传配置
        """
        super().__init__(client, config)
        self.upload_path = Path(config.get('directory', 'uploads'))
        self.target_channels = config.get('target_channels', [])
        self.options = config.get('options', {})
        self.is_uploading = False
        self.current_progress = (0, 0)  # (current, total)
        self.uploaded_count = 0
        self.total_size = 0
        self.file_hash_cache = {}
    
    @abstractmethod
    async def upload_media(self, file_path: Path, chat_id: int, caption: Optional[str] = None) -> Tuple[bool, Any]:
        """
        上传媒体文件。
        
        Args:
            file_path: 文件路径
            chat_id: 目标聊天ID
            caption: 说明文字
            
        Returns:
            Tuple[bool, Any]: (是否成功, 消息对象或错误信息)
        """
        pass
    
    @abstractmethod
    async def upload_media_group(self, files: List[Path], chat_id: int, caption: Optional[str] = None) -> Tuple[bool, List[Any]]:
        """
        上传媒体组。
        
        Args:
            files: 文件路径列表
            chat_id: 目标聊天ID
            caption: 说明文字
            
        Returns:
            Tuple[bool, List[Any]]: (是否成功, 消息对象列表)
        """
        pass
    
    @abstractmethod
    async def copy_message(self, from_chat_id: int, message_id: int, to_chat_id: int) -> Tuple[bool, Any]:
        """
        复制消息。
        
        Args:
            from_chat_id: 源聊天ID
            message_id: 消息ID
            to_chat_id: 目标聊天ID
            
        Returns:
            Tuple[bool, Any]: (是否成功, 消息对象或错误信息)
        """
        pass
    
    async def upload_local_files(self) -> bool:
        """
        上传本地文件到目标频道。
        
        Returns:
            bool: 是否成功完成上传
        """
        self.is_uploading = True
        self.uploaded_count = 0
        self.total_size = 0
        
        try:
            # 获取媒体组列表
            media_groups = [d for d in self.upload_path.iterdir() if d.is_dir()]
            
            for group_dir in media_groups:
                if not self.enabled or not self.is_uploading:
                    break
                
                await self._process_media_group(group_dir)
                
                # 更新进度
                self._update_progress()
            
            # 发送最终消息
            await self._send_final_message()
            
            self.emit("upload_completed", self.uploaded_count, self.total_size)
            return True
            
        except Exception as e:
            self._logger.error(f"上传过程中发生错误: {e}")
            self.emit("upload_error", str(e))
            return False
        finally:
            self.is_uploading = False
    
    async def _process_media_group(self, group_dir: Path) -> None:
        """
        处理媒体组目录。
        
        Args:
            group_dir: 媒体组目录
        """
        # 获取媒体组中的文件
        media_files = [f for f in group_dir.iterdir() if f.is_file() and self._is_valid_media_file(f)]
        
        if not media_files:
            self._logger.warning(f"媒体组目录中没有有效文件: {group_dir}")
            return
        
        # 获取标题
        caption = self._get_caption(group_dir)
        
        # 解析目标频道
        target_channels = await self._resolve_target_channels()
        
        if len(media_files) == 1:
            # 单个文件，直接上传
            await self._upload_single_file(media_files[0], target_channels, caption)
        else:
            # 多个文件，作为媒体组上传
            await self._upload_media_group_files(media_files, target_channels, caption)
    
    def _is_valid_media_file(self, file_path: Path) -> bool:
        """
        检查是否为有效的媒体文件。
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 是否为有效媒体文件
        """
        valid_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.mp4', '.avi', '.mov', '.mkv', '.mp3', '.wav', '.pdf', '.doc', '.docx'}
        return file_path.suffix.lower() in valid_extensions
    
    def _get_caption(self, group_dir: Path) -> Optional[str]:
        """
        获取媒体组标题。
        
        Args:
            group_dir: 媒体组目录
            
        Returns:
            Optional[str]: 标题
        """
        # 检查是否使用文件夹名称
        if self.options.get('use_folder_name', True):
            return group_dir.name
        
        # 检查是否读取title.txt
        if self.options.get('read_title_txt', False):
            title_file = group_dir / "title.txt"
            if title_file.exists():
                try:
                    return title_file.read_text(encoding='utf-8').strip()
                except Exception as e:
                    self._logger.error(f"读取title.txt失败: {e}")
        
        return None
    
    async def _resolve_target_channels(self) -> List[Tuple[str, int, Dict[str, Any]]]:
        """
        解析目标频道。
        
        Returns:
            List[Tuple[str, int, Dict[str, Any]]]: 目标频道列表
        """
        resolved_channels = []
        
        for channel in self.target_channels:
            try:
                channel_id = await self._resolve_channel_id(channel)
                if channel_id:
                    channel_info = await self._get_channel_info(channel_id)
                    resolved_channels.append((channel, channel_id, channel_info))
            except Exception as e:
                self._logger.error(f"解析目标频道失败: {channel}, 错误: {e}")
        
        return resolved_channels
    
    async def _resolve_channel_id(self, channel_name: str) -> Optional[int]:
        """
        解析频道ID。
        
        Args:
            channel_name: 频道名称或ID
            
        Returns:
            Optional[int]: 频道ID
        """
        try:
            # 如果是数字，直接返回
            if channel_name.isdigit():
                return int(channel_name)
            
            # 尝试获取频道信息
            chat = await self.client.get_chat(channel_name)
            return chat.id
            
        except Exception as e:
            self._logger.error(f"解析频道ID失败: {channel_name}, 错误: {e}")
            return None
    
    async def _get_channel_info(self, channel_id: int) -> Dict[str, Any]:
        """
        获取频道信息。
        
        Args:
            channel_id: 频道ID
            
        Returns:
            Dict[str, Any]: 频道信息
        """
        try:
            chat = await self.client.get_chat(channel_id)
            return {
                'id': chat.id,
                'title': chat.title,
                'type': str(chat.type.value)
            }
        except Exception as e:
            self._logger.error(f"获取频道信息失败: {channel_id}, 错误: {e}")
            return {'id': channel_id, 'title': str(channel_id), 'type': 'unknown'}
    
    async def _upload_single_file(self, file_path: Path, target_channels: List[Tuple[str, int, Dict[str, Any]]], caption: Optional[str] = None) -> None:
        """
        上传单个文件。
        
        Args:
            file_path: 文件路径
            target_channels: 目标频道列表
            caption: 说明文字
        """
        for channel_name, channel_id, channel_info in target_channels:
            if not self.enabled or not self.is_uploading:
                break
            
            try:
                # 检查文件哈希
                file_hash = self._calculate_file_hash(file_path)
                if self._is_file_already_uploaded(file_hash, channel_id):
                    self._logger.info(f"文件已上传: {file_path.name} -> {channel_name}")
                    continue
                
                # 上传文件
                success, result = await self.upload_media(file_path, channel_id, caption)
                
                if success:
                    self.uploaded_count += 1
                    self.total_size += file_path.stat().st_size
                    self._mark_file_as_uploaded(file_hash, channel_id)
                    
                    self.emit("file_uploaded", {
                        'file_name': file_path.name,
                        'channel_name': channel_name,
                        'message_id': result.id if hasattr(result, 'id') else None
                    })
                else:
                    self.emit("file_upload_error", {
                        'file_name': file_path.name,
                        'channel_name': channel_name,
                        'error': str(result)
                    })
                
            except Exception as e:
                self._logger.error(f"上传文件失败: {file_path.name} -> {channel_name}, 错误: {e}")
                self.emit("file_upload_error", {
                    'file_name': file_path.name,
                    'channel_name': channel_name,
                    'error': str(e)
                })
    
    async def _upload_media_group_files(self, files: List[Path], target_channels: List[Tuple[str, int, Dict[str, Any]]], caption: Optional[str] = None) -> None:
        """
        上传媒体组文件。
        
        Args:
            files: 文件列表
            target_channels: 目标频道列表
            caption: 说明文字
        """
        for channel_name, channel_id, channel_info in target_channels:
            if not self.enabled or not self.is_uploading:
                break
            
            try:
                # 过滤已上传的文件
                filtered_files = []
                for file_path in files:
                    file_hash = self._calculate_file_hash(file_path)
                    if not self._is_file_already_uploaded(file_hash, channel_id):
                        filtered_files.append(file_path)
                
                if not filtered_files:
                    self._logger.info(f"媒体组所有文件已上传: {channel_name}")
                    continue
                
                # 上传媒体组
                success, results = await self.upload_media_group(filtered_files, channel_id, caption)
                
                if success:
                    self.uploaded_count += len(filtered_files)
                    self.total_size += sum(f.stat().st_size for f in filtered_files)
                    
                    # 标记文件为已上传
                    for file_path in filtered_files:
                        file_hash = self._calculate_file_hash(file_path)
                        self._mark_file_as_uploaded(file_hash, channel_id)
                    
                    self.emit("media_group_uploaded", {
                        'file_count': len(filtered_files),
                        'channel_name': channel_name,
                        'message_ids': [r.id for r in results if hasattr(r, 'id')]
                    })
                else:
                    self.emit("media_group_upload_error", {
                        'file_count': len(filtered_files),
                        'channel_name': channel_name,
                        'error': str(results)
                    })
                
            except Exception as e:
                self._logger.error(f"上传媒体组失败: {channel_name}, 错误: {e}")
                self.emit("media_group_upload_error", {
                    'file_count': len(files),
                    'channel_name': channel_name,
                    'error': str(e)
                })
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """
        计算文件哈希值。
        
        Args:
            file_path: 文件路径
            
        Returns:
            str: 文件哈希值
        """
        if file_path in self.file_hash_cache:
            return self.file_hash_cache[file_path]
        
        try:
            with open(file_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
                self.file_hash_cache[file_path] = file_hash
                return file_hash
        except Exception as e:
            self._logger.error(f"计算文件哈希失败: {file_path}, 错误: {e}")
            return ""
    
    def _is_file_already_uploaded(self, file_hash: str, channel_id: int) -> bool:
        """
        检查文件是否已上传。
        
        Args:
            file_hash: 文件哈希值
            channel_id: 频道ID
            
        Returns:
            bool: 是否已上传
        """
        # 这里应该检查历史记录
        # 暂时返回False，实际实现中应该查询数据库
        return False
    
    def _mark_file_as_uploaded(self, file_hash: str, channel_id: int) -> None:
        """
        标记文件为已上传。
        
        Args:
            file_hash: 文件哈希值
            channel_id: 频道ID
        """
        # 这里应该更新历史记录
        # 实际实现中应该写入数据库
        pass
    
    async def _send_final_message(self) -> None:
        """发送最终消息。"""
        send_final_message = self.options.get('send_final_message', False)
        if not send_final_message:
            return
        
        html_file_path = self.options.get('final_message_html_file', '')
        if not html_file_path or not Path(html_file_path).exists():
            return
        
        try:
            # 读取HTML文件
            with open(html_file_path, 'r', encoding='utf-8') as f:
                html_content = f.read().strip()
            
            # 发送到所有目标频道
            target_channels = await self._resolve_target_channels()
            for channel_name, channel_id, channel_info in target_channels:
                try:
                    enable_web_page_preview = self.options.get('enable_web_page_preview', False)
                    message = await self.client.send_message(
                        chat_id=channel_id,
                        text=html_content,
                        parse_mode="html",
                        disable_web_page_preview=not enable_web_page_preview
                    )
                    
                    self.emit("final_message_sent", {
                        'channel_name': channel_name,
                        'message_id': message.id
                    })
                    
                except Exception as e:
                    self._logger.error(f"发送最终消息失败: {channel_name}, 错误: {e}")
                    self.emit("final_message_error", {
                        'channel_name': channel_name,
                        'error': str(e)
                    })
                    
        except Exception as e:
            self._logger.error(f"读取最终消息文件失败: {e}")
    
    def _update_progress(self) -> None:
        """更新上传进度。"""
        self.current_progress = (self.uploaded_count, self.total_size)
        self.emit("progress_updated", self.uploaded_count, self.total_size)
    
    async def stop_upload(self) -> None:
        """停止上传。"""
        self.is_uploading = False
        self.enabled = False
        self._logger.info("上传已停止")
    
    def get_upload_status(self) -> Dict[str, Any]:
        """
        获取上传状态。
        
        Returns:
            Dict[str, Any]: 上传状态信息
        """
        return {
            "is_uploading": self.is_uploading,
            "uploaded_count": self.uploaded_count,
            "total_size": self.total_size,
            "current_progress": self.current_progress,
            "enabled": self.enabled,
            "target_channels": self.target_channels
        }
    
    async def start(self) -> bool:
        """
        启动上传器。
        
        Returns:
            bool: 是否成功启动
        """
        self.enabled = True
        self._logger.info("上传器已启动")
        return True
    
    async def stop(self) -> bool:
        """
        停止上传器。
        
        Returns:
            bool: 是否成功停止
        """
        await self.stop_upload()
        return True 