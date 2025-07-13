"""
下载功能抽象基类

定义下载功能的通用接口，包括媒体下载、消息下载、进度跟踪等功能。
"""

import asyncio
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from loguru import logger

from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait

from abstractions.base_handler import BaseHandler


class BaseDownloader(BaseHandler):
    """
    下载功能抽象基类，为下载插件提供统一接口。
    
    所有下载插件都应该继承此类并实现必要的方法。
    """
    
    def __init__(self, client, config: Dict[str, Any]):
        """
        初始化下载器。
        
        Args:
            client: Telegram客户端实例
            config: 下载配置
        """
        super().__init__(client, config)
        self.download_path = Path(config.get('download_path', 'downloads'))
        self.is_downloading = False
        self.current_progress = (0, 0)  # (current, total)
        self.downloaded_count = 0
        self.total_size = 0
    
    @abstractmethod
    async def download_media(self, message, save_path: Path) -> bool:
        """
        下载媒体文件。
        
        Args:
            message: Telegram消息对象
            save_path: 保存路径
            
        Returns:
            bool: 是否成功下载
        """
        pass
    
    @abstractmethod
    async def download_messages(self, chat_id: int, message_ids: List[int]) -> List[bool]:
        """
        下载消息。
        
        Args:
            chat_id: 聊天ID
            message_ids: 消息ID列表
            
        Returns:
            List[bool]: 下载结果列表
        """
        pass
    
    @abstractmethod
    async def get_media_info(self, message) -> Dict[str, Any]:
        """
        获取媒体信息。
        
        Args:
            message: Telegram消息对象
            
        Returns:
            Dict[str, Any]: 媒体信息
        """
        pass
    
    async def download_media_from_channels(self) -> bool:
        """
        从配置的频道下载媒体文件。
        
        Returns:
            bool: 是否成功完成下载
        """
        self.is_downloading = True
        self.downloaded_count = 0
        self.total_size = 0
        
        try:
            download_settings = self.config.get('downloadSetting', [])
            
            for setting in download_settings:
                if not self.enabled:
                    break
                
                await self._process_channel_setting(setting)
                
                # 更新进度
                self._update_progress()
                
                # 检查取消状态
                if not self.is_downloading:
                    break
            
            self.emit("download_completed", self.downloaded_count, self.total_size)
            return True
            
        except Exception as e:
            self._logger.error(f"下载过程中发生错误: {e}")
            self.emit("download_error", str(e))
            return False
        finally:
            self.is_downloading = False
    
    async def _process_channel_setting(self, setting: Dict[str, Any]) -> None:
        """
        处理单个频道设置。
        
        Args:
            setting: 频道下载设置
        """
        source_channels = setting.get('source_channels', '')
        start_id = setting.get('start_id', 0)
        end_id = setting.get('end_id', 0)
        media_types = setting.get('media_types', [])
        keywords = setting.get('keywords', [])
        global_limit = setting.get('global_limit', 1000)
        
        # 解析频道ID
        channel_id = await self._resolve_channel_id(source_channels)
        if not channel_id:
            self._logger.error(f"无法解析频道ID: {source_channels}")
            return
        
        # 获取消息列表
        messages = await self._get_messages_in_range(channel_id, start_id, end_id, global_limit)
        
        # 过滤消息
        filtered_messages = self._filter_messages(messages, media_types, keywords)
        
        # 下载媒体文件
        await self._download_filtered_messages(filtered_messages, source_channels)
    
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
    
    async def _get_messages_in_range(self, chat_id: int, start_id: int, end_id: int, limit: int) -> List:
        """
        获取指定范围内的消息。
        
        Args:
            chat_id: 聊天ID
            start_id: 起始消息ID
            end_id: 结束消息ID
            limit: 限制数量
            
        Returns:
            List: 消息列表
        """
        messages = []
        
        try:
            if start_id > 0 and end_id > 0:
                # 指定范围
                for message_id in range(start_id, end_id + 1):
                    if len(messages) >= limit:
                        break
                    
                    try:
                        message = await self.client.get_messages(chat_id, message_id)
                        if message:
                            messages.append(message)
                    except Exception as e:
                        self._logger.warning(f"获取消息失败: {message_id}, 错误: {e}")
            else:
                # 获取最新消息
                messages = await self.client.get_messages(chat_id, limit=limit)
            
            return messages
            
        except Exception as e:
            self._logger.error(f"获取消息列表失败: {e}")
            return []
    
    def _filter_messages(self, messages: List, media_types: List[str], keywords: List[str]) -> List:
        """
        过滤消息。
        
        Args:
            messages: 消息列表
            media_types: 媒体类型列表
            keywords: 关键词列表
            
        Returns:
            List: 过滤后的消息列表
        """
        filtered_messages = []
        
        for message in messages:
            # 检查媒体类型
            if media_types and not self._is_media_type_match(message, media_types):
                continue
            
            # 检查关键词
            if keywords and not self._contains_keywords(message, keywords):
                continue
            
            filtered_messages.append(message)
        
        return filtered_messages
    
    def _is_media_type_match(self, message, media_types: List[str]) -> bool:
        """
        检查媒体类型是否匹配。
        
        Args:
            message: 消息对象
            media_types: 媒体类型列表
            
        Returns:
            bool: 是否匹配
        """
        if not message.media:
            return False
        
        message_media_type = str(message.media.value)
        return message_media_type in media_types
    
    def _contains_keywords(self, message, keywords: List[str]) -> bool:
        """
        检查消息是否包含关键词。
        
        Args:
            message: 消息对象
            keywords: 关键词列表
            
        Returns:
            bool: 是否包含关键词
        """
        text = message.text or message.caption or ""
        if not text:
            return False
        
        text_lower = text.lower()
        for keyword in keywords:
            if keyword.lower() in text_lower:
                return True
        
        return False
    
    async def _download_filtered_messages(self, messages: List, channel_name: str) -> None:
        """
        下载过滤后的消息。
        
        Args:
            messages: 消息列表
            channel_name: 频道名称
        """
        for message in messages:
            if not self.enabled or not self.is_downloading:
                break
            
            try:
                # 创建保存路径
                save_path = self._create_save_path(message, channel_name)
                
                # 下载媒体文件
                success = await self.download_media(message, save_path)
                
                if success:
                    self.downloaded_count += 1
                    # 更新文件大小统计
                    media_info = await self.get_media_info(message)
                    self.total_size += media_info.get('file_size', 0)
                
                # 发射进度事件
                self.emit("download_progress", self.downloaded_count, len(messages))
                
            except Exception as e:
                self._logger.error(f"下载消息失败: {message.id}, 错误: {e}")
    
    def _create_save_path(self, message, channel_name: str) -> Path:
        """
        创建保存路径。
        
        Args:
            message: 消息对象
            channel_name: 频道名称
            
        Returns:
            Path: 保存路径
        """
        # 创建频道目录
        channel_dir = self.download_path / self._sanitize_filename(channel_name)
        channel_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建文件名
        if message.media_group_id:
            # 媒体组
            filename = f"{message.media_group_id}_{message.id}"
        else:
            # 单条消息
            filename = f"single_{message.id}"
        
        # 添加文件扩展名
        media_info = self._get_media_info_sync(message)
        if media_info.get('file_name'):
            filename = media_info['file_name']
        
        return channel_dir / filename
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        清理文件名，移除非法字符。
        
        Args:
            filename: 原始文件名
            
        Returns:
            str: 清理后的文件名
        """
        import re
        # 移除或替换非法字符
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        return filename.strip()
    
    def _get_media_info_sync(self, message) -> Dict[str, Any]:
        """
        同步获取媒体信息。
        
        Args:
            message: 消息对象
            
        Returns:
            Dict[str, Any]: 媒体信息
        """
        if not message.media:
            return {}
        
        media_info = {
            'media_type': str(message.media.value),
            'file_name': None,
            'file_size': 0
        }
        
        # 根据媒体类型获取文件名
        if hasattr(message, 'document') and message.document:
            media_info['file_name'] = message.document.file_name
            media_info['file_size'] = message.document.file_size
        elif hasattr(message, 'photo') and message.photo:
            media_info['file_name'] = f"photo_{message.id}.jpg"
            media_info['file_size'] = message.photo.file_size
        elif hasattr(message, 'video') and message.video:
            media_info['file_name'] = message.video.file_name or f"video_{message.id}.mp4"
            media_info['file_size'] = message.video.file_size
        
        return media_info
    
    def _update_progress(self) -> None:
        """更新下载进度。"""
        self.current_progress = (self.downloaded_count, self.total_size)
        self.emit("progress_updated", self.downloaded_count, self.total_size)
    
    async def stop_download(self) -> None:
        """停止下载。"""
        self.is_downloading = False
        self.enabled = False
        self._logger.info("下载已停止")
    
    def get_download_status(self) -> Dict[str, Any]:
        """
        获取下载状态。
        
        Returns:
            Dict[str, Any]: 下载状态信息
        """
        return {
            "is_downloading": self.is_downloading,
            "downloaded_count": self.downloaded_count,
            "total_size": self.total_size,
            "current_progress": self.current_progress,
            "enabled": self.enabled
        }
    
    async def start(self) -> bool:
        """
        启动下载器。
        
        Returns:
            bool: 是否成功启动
        """
        self.enabled = True
        self._logger.info("下载器已启动")
        return True
    
    async def stop(self) -> bool:
        """
        停止下载器。
        
        Returns:
            bool: 是否成功停止
        """
        await self.stop_download()
        return True 