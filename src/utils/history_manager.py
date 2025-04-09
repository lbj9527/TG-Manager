"""
历史记录管理器模块，管理下载、上传和转发的历史记录
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Union, Optional, Set, Any

from src.utils.logger import get_logger

logger = get_logger()

class HistoryManager:
    """历史记录管理器，统一管理下载、上传和转发历史记录"""
    
    def __init__(self):
        """初始化历史记录管理器"""
        # 确保history文件夹存在
        history_dir = "history"
        if not os.path.exists(history_dir):
            os.makedirs(history_dir)
            logger.info(f"创建历史记录文件夹：{history_dir}")
            
        # 设置历史记录文件路径
        self.download_history_path = os.path.join(history_dir, "download_history.json")
        self.upload_history_path = os.path.join(history_dir, "upload_history.json")
        self.forward_history_path = os.path.join(history_dir, "forward_history.json")
        
        # 初始化历史记录文件
        self._init_history_files()
    
    def _init_history_files(self):
        """初始化历史记录文件"""
        self._init_file(self.download_history_path, {"channels": {}, "last_updated": ""})
        self._init_file(self.upload_history_path, {"files": {}, "last_updated": ""})
        self._init_file(self.forward_history_path, {"channels": {}, "last_updated": ""})
    
    def _init_file(self, file_path: str, default_content: Dict[str, Any]):
        """
        初始化指定的历史记录文件
        
        Args:
            file_path: 文件路径
            default_content: 默认内容
        """
        if not os.path.exists(file_path):
            with open(file_path, 'w', encoding='utf-8') as f:
                default_content["last_updated"] = datetime.now().isoformat()
                json.dump(default_content, f, ensure_ascii=False, indent=2)
            logger.info(f"创建历史记录文件：{file_path}")
    
    def _read_history(self, file_path: str) -> Dict[str, Any]:
        """
        读取历史记录文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            Dict[str, Any]: 历史记录数据
        """
        try:
            # 检查文件是否存在且非空
            if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
                logger.warning(f"历史记录文件不存在或为空: {file_path}，创建新文件")
                # 根据文件类型创建默认结构
                if file_path == self.download_history_path:
                    default_content = {"channels": {}, "last_updated": datetime.now().isoformat()}
                elif file_path == self.upload_history_path:
                    default_content = {"files": {}, "last_updated": datetime.now().isoformat()}
                elif file_path == self.forward_history_path:
                    default_content = {"channels": {}, "last_updated": datetime.now().isoformat()}
                else:
                    default_content = {"last_updated": datetime.now().isoformat()}
                
                # 写入默认内容
                self._write_history(file_path, default_content)
                return default_content
            
            # 读取并解析文件
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:  # 再次检查内容是否为空
                    raise json.JSONDecodeError("Empty file", "", 0)
                return json.loads(content)
                
        except json.JSONDecodeError as e:
            logger.error(f"读取历史记录文件失败（JSON格式错误）：{file_path}, 错误：{e}")
            # 根据文件类型创建默认结构
            if file_path == self.download_history_path:
                default_content = {"channels": {}, "last_updated": datetime.now().isoformat()}
            elif file_path == self.upload_history_path:
                default_content = {"files": {}, "last_updated": datetime.now().isoformat()}
            elif file_path == self.forward_history_path:
                default_content = {"channels": {}, "last_updated": datetime.now().isoformat()}
            else:
                default_content = {"last_updated": datetime.now().isoformat()}
            
            # 创建备份并写入默认内容
            if os.path.exists(file_path):
                backup_path = f"{file_path}.bak.{int(time.time())}"
                try:
                    os.rename(file_path, backup_path)
                    logger.warning(f"已将损坏的历史记录文件备份为: {backup_path}")
                except Exception as rename_err:
                    logger.error(f"备份损坏的历史记录文件失败: {rename_err}")
            
            # 写入默认内容
            self._write_history(file_path, default_content)
            return default_content
            
        except FileNotFoundError:
            logger.warning(f"历史记录文件不存在: {file_path}，创建新文件")
            # 根据文件类型创建默认结构
            if file_path == self.download_history_path:
                default_content = {"channels": {}, "last_updated": datetime.now().isoformat()}
            elif file_path == self.upload_history_path:
                default_content = {"files": {}, "last_updated": datetime.now().isoformat()}
            elif file_path == self.forward_history_path:
                default_content = {"channels": {}, "last_updated": datetime.now().isoformat()}
            else:
                default_content = {"last_updated": datetime.now().isoformat()}
            
            # 写入默认内容
            self._write_history(file_path, default_content)
            return default_content
            
        except Exception as e:
            logger.error(f"读取历史记录文件失败（未知错误）：{file_path}, 错误：{e}")
            # 返回一个安全的默认值
            return {"channels": {}, "files": {}, "last_updated": datetime.now().isoformat()}
    
    def _write_history(self, file_path: str, data: Dict[str, Any]):
        """
        写入历史记录文件
        
        Args:
            file_path: 文件路径
            data: 历史记录数据
        """
        # 确保last_updated字段存在
        data["last_updated"] = datetime.now().isoformat()
        
        # 使用临时文件进行原子写入，避免写入过程中的文件损坏
        temp_path = f"{file_path}.tmp"
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # 在Windows上，可能需要先删除原文件再重命名
            if os.path.exists(file_path):
                os.remove(file_path)
            os.rename(temp_path, file_path)
        except Exception as e:
            logger.error(f"写入历史记录文件失败：{file_path}, 错误：{e}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise
    
    # 下载历史记录方法
    def is_message_downloaded(self, channel_id: str, message_id: int) -> bool:
        """
        检查消息是否已下载
        
        Args:
            channel_id: 频道ID或用户名
            message_id: 消息ID
            
        Returns:
            bool: 是否已下载
        """
        history = self._read_history(self.download_history_path)
        channels = history.get("channels", {})
        
        if channel_id not in channels:
            return False
        
        downloaded_messages = channels[channel_id].get("downloaded_messages", [])
        return message_id in downloaded_messages
    
    def add_download_record(self, channel_id: str, message_id: int, real_channel_id: Optional[int] = None):
        """
        添加下载记录
        
        Args:
            channel_id: 频道ID或用户名
            message_id: 消息ID
            real_channel_id: 真实频道ID（数字形式）
        """
        history = self._read_history(self.download_history_path)
        channels = history.get("channels", {})
        
        if channel_id not in channels:
            channels[channel_id] = {
                "channel_id": real_channel_id,
                "downloaded_messages": []
            }
        
        if message_id not in channels[channel_id].get("downloaded_messages", []):
            channels[channel_id].setdefault("downloaded_messages", []).append(message_id)
            history["channels"] = channels
            self._write_history(self.download_history_path, history)
            logger.debug(f"添加下载记录：频道 {channel_id}, 消息ID {message_id}")
    
    def get_downloaded_messages(self, channel_id: str) -> List[int]:
        """
        获取频道已下载的消息ID列表
        
        Args:
            channel_id: 频道ID或用户名
            
        Returns:
            List[int]: 已下载的消息ID列表
        """
        history = self._read_history(self.download_history_path)
        channels = history.get("channels", {})
        
        if channel_id not in channels:
            return []
        
        return channels[channel_id].get("downloaded_messages", [])
    
    # 为了兼容性添加别名
    def is_downloaded(self, channel_id: str, message_id: int) -> bool:
        """
        检查消息是否已下载，是is_message_downloaded的别名
        
        Args:
            channel_id: 频道ID或用户名
            message_id: 消息ID
            
        Returns:
            bool: 是否已下载
        """
        return self.is_message_downloaded(channel_id, message_id)
    
    # 上传历史记录方法
    def is_file_uploaded(self, file_path: str, target_channel: str) -> bool:
        """
        检查文件是否已上传到指定频道
        
        Args:
            file_path: 文件路径
            target_channel: 目标频道
            
        Returns:
            bool: 是否已上传
        """
        history = self._read_history(self.upload_history_path)
        files = history.get("files", {})
        
        if file_path not in files:
            return False
        
        uploaded_to = files[file_path].get("uploaded_to", [])
        return target_channel in uploaded_to
    
    def add_upload_record(self, file_path: str, target_channel: str, file_size: int, media_type: str):
        """
        添加上传记录
        
        Args:
            file_path: 文件路径
            target_channel: 目标频道
            file_size: 文件大小（字节）
            media_type: 媒体类型
        """
        history = self._read_history(self.upload_history_path)
        files = history.get("files", {})
        
        if file_path not in files:
            files[file_path] = {
                "uploaded_to": [],
                "upload_time": datetime.now().isoformat(),
                "file_size": file_size,
                "media_type": media_type
            }
        
        if target_channel not in files[file_path].get("uploaded_to", []):
            files[file_path].setdefault("uploaded_to", []).append(target_channel)
            history["files"] = files
            self._write_history(self.upload_history_path, history)
            logger.debug(f"添加上传记录：文件 {file_path} 到频道 {target_channel}")
    
    def get_uploaded_files(self, target_channel: Optional[str] = None) -> List[str]:
        """
        获取已上传到指定频道的文件列表
        
        Args:
            target_channel: 目标频道，为None则获取所有已上传文件
            
        Returns:
            List[str]: 已上传的文件路径列表
        """
        history = self._read_history(self.upload_history_path)
        files = history.get("files", {})
        
        if target_channel is None:
            return list(files.keys())
        
        return [
            file_path for file_path, data in files.items()
            if target_channel in data.get("uploaded_to", [])
        ]
    
    # 转发历史记录方法
    def is_message_forwarded(self, source_channel: str, message_id: int, target_channel: str) -> bool:
        """
        检查消息是否已转发到指定目标频道
        
        Args:
            source_channel: 源频道
            message_id: 消息ID
            target_channel: 目标频道
            
        Returns:
            bool: 是否已转发
        """
        history = self._read_history(self.forward_history_path)
        channels = history.get("channels", {})
        
        if source_channel not in channels:
            return False
        
        forwarded_messages = channels[source_channel].get("forwarded_messages", {})
        message_id_str = str(message_id)  # JSON键必须是字符串
        
        if message_id_str not in forwarded_messages:
            return False
        
        return target_channel in forwarded_messages[message_id_str]
    
    def add_forward_record(self, source_channel: str, message_id: int, target_channel: str, real_source_id: Optional[int] = None):
        """
        添加转发记录
        
        Args:
            source_channel: 源频道
            message_id: 消息ID
            target_channel: 目标频道
            real_source_id: 真实源频道ID（数字形式）
        """
        history = self._read_history(self.forward_history_path)
        channels = history.get("channels", {})
        
        if source_channel not in channels:
            channels[source_channel] = {
                "channel_id": real_source_id,
                "forwarded_messages": {}
            }
        
        message_id_str = str(message_id)
        forwarded_messages = channels[source_channel].setdefault("forwarded_messages", {})
        
        if message_id_str not in forwarded_messages:
            forwarded_messages[message_id_str] = []
        
        if target_channel not in forwarded_messages[message_id_str]:
            forwarded_messages[message_id_str].append(target_channel)
            history["channels"] = channels
            self._write_history(self.forward_history_path, history)
            logger.debug(f"添加转发记录：源频道 {source_channel} 的消息ID {message_id} 到目标频道 {target_channel}")
    
    def get_forwarded_messages(self, source_channel: str, target_channel: Optional[str] = None) -> List[int]:
        """
        获取从源频道已转发到目标频道的消息ID列表
        
        Args:
            source_channel: 源频道
            target_channel: 目标频道，为None则获取所有已转发消息
            
        Returns:
            List[int]: 已转发的消息ID列表
        """
        history = self._read_history(self.forward_history_path)
        channels = history.get("channels", {})
        
        if source_channel not in channels:
            return []
        
        forwarded_messages = channels[source_channel].get("forwarded_messages", {})
        
        if target_channel is None:
            return [int(msg_id) for msg_id in forwarded_messages.keys()]
        
        return [
            int(msg_id) for msg_id, targets in forwarded_messages.items()
            if target_channel in targets
        ] 