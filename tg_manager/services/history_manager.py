"""
历史记录管理模块
统一管理download_history.json/upload_history.json/forward_history.json
提供原子化读写接口
"""

import os
import json
import time
from typing import Dict, List, Any, Union, Optional
from datetime import datetime
import threading
from pathlib import Path

from tg_manager.utils.logger import get_logger

logger = get_logger("history_manager")


class HistoryManager:
    """历史记录管理类，用于处理下载、上传和转发的历史记录"""
    
    def __init__(self, 
                 download_history_path: str = "data/download_history.json",
                 upload_history_path: str = "data/upload_history.json",
                 forward_history_path: str = "data/forward_history.json"):
        """
        初始化历史记录管理器
        
        Args:
            download_history_path: 下载历史记录文件路径
            upload_history_path: 上传历史记录文件路径
            forward_history_path: 转发历史记录文件路径
        """
        self.download_history_path = download_history_path
        self.upload_history_path = upload_history_path
        self.forward_history_path = forward_history_path
        
        # 创建文件锁，确保多线程安全
        self.download_lock = threading.Lock()
        self.upload_lock = threading.Lock()
        self.forward_lock = threading.Lock()
        
        # 确保数据目录存在
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        
        # 初始化历史记录文件
        self._init_history_files()
    
    def _init_history_files(self) -> None:
        """初始化所有历史记录文件，如果不存在则创建"""
        self._init_download_history()
        self._init_upload_history()
        self._init_forward_history()
    
    def _init_download_history(self) -> None:
        """初始化下载历史记录文件"""
        if not os.path.exists(self.download_history_path):
            default_history = {
                "channels": {},
                "last_updated": datetime.now().isoformat()
            }
            with open(self.download_history_path, 'w', encoding='utf-8') as f:
                json.dump(default_history, f, ensure_ascii=False, indent=2)
            logger.info(f"已创建下载历史记录文件: {self.download_history_path}")
    
    def _init_upload_history(self) -> None:
        """初始化上传历史记录文件"""
        if not os.path.exists(self.upload_history_path):
            default_history = {
                "files": {},
                "last_updated": datetime.now().isoformat()
            }
            with open(self.upload_history_path, 'w', encoding='utf-8') as f:
                json.dump(default_history, f, ensure_ascii=False, indent=2)
            logger.info(f"已创建上传历史记录文件: {self.upload_history_path}")
    
    def _init_forward_history(self) -> None:
        """初始化转发历史记录文件"""
        if not os.path.exists(self.forward_history_path):
            default_history = {
                "channels": {},
                "last_updated": datetime.now().isoformat()
            }
            with open(self.forward_history_path, 'w', encoding='utf-8') as f:
                json.dump(default_history, f, ensure_ascii=False, indent=2)
            logger.info(f"已创建转发历史记录文件: {self.forward_history_path}")
    
    def get_download_history(self) -> Dict[str, Any]:
        """
        获取下载历史记录
        
        Returns:
            下载历史记录数据
        """
        with self.download_lock:
            try:
                with open(self.download_history_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                logger.error(f"读取下载历史记录失败: {e}")
                self._init_download_history()
                return {"channels": {}, "last_updated": datetime.now().isoformat()}
    
    def get_upload_history(self) -> Dict[str, Any]:
        """
        获取上传历史记录
        
        Returns:
            上传历史记录数据
        """
        with self.upload_lock:
            try:
                with open(self.upload_history_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                logger.error(f"读取上传历史记录失败: {e}")
                self._init_upload_history()
                return {"files": {}, "last_updated": datetime.now().isoformat()}
    
    def get_forward_history(self) -> Dict[str, Any]:
        """
        获取转发历史记录
        
        Returns:
            转发历史记录数据
        """
        with self.forward_lock:
            try:
                with open(self.forward_history_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                logger.error(f"读取转发历史记录失败: {e}")
                self._init_forward_history()
                return {"channels": {}, "last_updated": datetime.now().isoformat()}
    
    def is_message_downloaded(self, channel_id: Union[int, str], message_id: int) -> bool:
        """
        检查消息是否已下载
        
        Args:
            channel_id: 频道ID或用户名
            message_id: 消息ID
            
        Returns:
            如果消息已下载则返回True，否则返回False
        """
        channel_key = str(channel_id)
        history = self.get_download_history()
        
        if channel_key not in history["channels"]:
            return False
        
        downloaded_messages = history["channels"][channel_key].get("downloaded_messages", [])
        return message_id in downloaded_messages
    
    def add_downloaded_message(self, channel_id: Union[int, str], message_id: int, 
                               real_channel_id: Optional[int] = None) -> None:
        """
        添加已下载消息到历史记录
        
        Args:
            channel_id: 频道ID或用户名
            message_id: 消息ID
            real_channel_id: 实际的频道数字ID
        """
        channel_key = str(channel_id)
        with self.download_lock:
            history = self.get_download_history()
            
            if channel_key not in history["channels"]:
                history["channels"][channel_key] = {
                    "channel_id": real_channel_id if real_channel_id is not None else channel_id,
                    "downloaded_messages": []
                }
            
            if message_id not in history["channels"][channel_key]["downloaded_messages"]:
                history["channels"][channel_key]["downloaded_messages"].append(message_id)
                history["last_updated"] = datetime.now().isoformat()
                
                with open(self.download_history_path, 'w', encoding='utf-8') as f:
                    json.dump(history, f, ensure_ascii=False, indent=2)
    
    def is_file_uploaded(self, file_path: str, target_channel: str) -> bool:
        """
        检查文件是否已上传到目标频道
        
        Args:
            file_path: 文件路径
            target_channel: 目标频道
            
        Returns:
            如果文件已上传到指定频道则返回True，否则返回False
        """
        history = self.get_upload_history()
        file_key = os.path.normpath(file_path)
        
        if file_key not in history["files"]:
            return False
        
        uploaded_to = history["files"][file_key].get("uploaded_to", [])
        return target_channel in uploaded_to
    
    def add_uploaded_file(self, file_path: str, target_channel: str, 
                          file_size: int, media_type: str) -> None:
        """
        添加已上传文件到历史记录
        
        Args:
            file_path: 文件路径
            target_channel: 目标频道
            file_size: 文件大小（字节）
            media_type: 媒体类型
        """
        file_key = os.path.normpath(file_path)
        with self.upload_lock:
            history = self.get_upload_history()
            
            if file_key not in history["files"]:
                history["files"][file_key] = {
                    "uploaded_to": [],
                    "upload_time": datetime.now().isoformat(),
                    "file_size": file_size,
                    "media_type": media_type
                }
            
            if target_channel not in history["files"][file_key]["uploaded_to"]:
                history["files"][file_key]["uploaded_to"].append(target_channel)
                history["last_updated"] = datetime.now().isoformat()
                
                with open(self.upload_history_path, 'w', encoding='utf-8') as f:
                    json.dump(history, f, ensure_ascii=False, indent=2)
    
    def is_message_forwarded(self, 
                             source_channel: Union[int, str], 
                             message_id: int, 
                             target_channel: str) -> bool:
        """
        检查消息是否已转发到目标频道
        
        Args:
            source_channel: 源频道ID或用户名
            message_id: 消息ID
            target_channel: 目标频道
            
        Returns:
            如果消息已转发到指定频道则返回True，否则返回False
        """
        source_key = str(source_channel)
        message_key = str(message_id)
        history = self.get_forward_history()
        
        if source_key not in history["channels"]:
            return False
        
        forwarded_messages = history["channels"][source_key].get("forwarded_messages", {})
        if message_key not in forwarded_messages:
            return False
        
        return target_channel in forwarded_messages[message_key]
    
    def add_forwarded_message(self, 
                              source_channel: Union[int, str], 
                              message_id: int, 
                              target_channel: str,
                              real_channel_id: Optional[int] = None) -> None:
        """
        添加已转发消息到历史记录
        
        Args:
            source_channel: 源频道ID或用户名
            message_id: 消息ID
            target_channel: 目标频道
            real_channel_id: 实际的频道数字ID
        """
        source_key = str(source_channel)
        message_key = str(message_id)
        
        with self.forward_lock:
            history = self.get_forward_history()
            
            if source_key not in history["channels"]:
                history["channels"][source_key] = {
                    "channel_id": real_channel_id if real_channel_id is not None else source_channel,
                    "forwarded_messages": {}
                }
            
            if message_key not in history["channels"][source_key]["forwarded_messages"]:
                history["channels"][source_key]["forwarded_messages"][message_key] = []
            
            if target_channel not in history["channels"][source_key]["forwarded_messages"][message_key]:
                history["channels"][source_key]["forwarded_messages"][message_key].append(target_channel)
                history["last_updated"] = datetime.now().isoformat()
                
                with open(self.forward_history_path, 'w', encoding='utf-8') as f:
                    json.dump(history, f, ensure_ascii=False, indent=2)
                    
    def get_downloaded_messages(self, channel_id: Union[int, str]) -> List[int]:
        """
        获取指定频道所有已下载的消息ID列表
        
        Args:
            channel_id: 频道ID或用户名
            
        Returns:
            已下载消息ID列表
        """
        channel_key = str(channel_id)
        history = self.get_download_history()
        
        if channel_key not in history["channels"]:
            return []
        
        return history["channels"][channel_key].get("downloaded_messages", [])
    
    def get_forwarded_messages(self, source_channel: Union[int, str]) -> Dict[str, List[str]]:
        """
        获取指定源频道所有已转发的消息和目标频道
        
        Args:
            source_channel: 源频道ID或用户名
            
        Returns:
            已转发消息字典，键为消息ID，值为目标频道列表
        """
        source_key = str(source_channel)
        history = self.get_forward_history()
        
        if source_key not in history["channels"]:
            return {}
        
        return history["channels"][source_key].get("forwarded_messages", {}) 