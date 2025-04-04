"""
配置管理器模块，负责加载和管理配置信息
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Union, Optional
import datetime

from pydantic import BaseModel, validator, Field
from src.utils.logger import get_logger

logger = get_logger()

class GeneralConfig(BaseModel):
    """通用配置模型"""
    api_id: int
    api_hash: str
    limit: int = 50
    pause_time: int = 60
    timeout: int = 30
    max_retries: int = 3
    proxy_enabled: bool = False
    proxy_type: str = "SOCKS5"
    proxy_addr: str = "127.0.0.1"
    proxy_port: int = 1080
    proxy_username: Optional[str] = None
    proxy_password: Optional[str] = None

class DownloadSettingItem(BaseModel):
    """下载设置项模型"""
    source_channels: str
    start_id: int = 0
    end_id: int = 0
    media_types: List[str] = ["photo", "video", "document", "audio", "animation"]
    keywords: List[str] = []

class DownloadConfig(BaseModel):
    """下载配置模型"""
    downloadSetting: List[DownloadSettingItem] = []
    download_path: str = "downloads"
    parallel_download: bool = False
    max_concurrent_downloads: int = 10

class UploadConfig(BaseModel):
    """上传配置模型"""
    target_channels: List[str]
    directory: str = "uploads"
    caption_template: str = "{filename}"

class TextFilterItem(BaseModel):
    """文本替换项模型"""
    original_text: str
    target_text: str = ""  # 默认为空字符串，表示替换为空

class ChannelPair(BaseModel):
    """频道对配置模型"""
    source_channel: str
    target_channels: List[str]

class MonitorChannelPair(ChannelPair):
    """监听频道对配置模型，扩展ChannelPair添加更多配置项"""
    remove_captions: bool = False
    text_filter: List[TextFilterItem] = []

class ForwardConfig(BaseModel):
    """转发配置模型"""
    forward_channel_pairs: List[ChannelPair]
    remove_captions: bool = False
    hide_author: bool = False
    media_types: List[str] = ["photo", "video", "document", "audio", "animation"]
    forward_delay: int = 3
    start_id: int = 0
    end_id: int = 0
    tmp_path: str = "tmp"

class MonitorConfig(BaseModel):
    """监听配置模型"""
    monitor_channel_pairs: List[MonitorChannelPair]
    media_types: List[str] = ["photo", "video", "document", "audio", "animation"]
    duration: Optional[str] = None
    forward_delay: int = 3

class Config(BaseModel):
    """完整配置模型"""
    GENERAL: GeneralConfig
    DOWNLOAD: DownloadConfig
    UPLOAD: UploadConfig
    FORWARD: ForwardConfig
    MONITOR: MonitorConfig

class ConfigManager:
    """配置管理器类，负责加载和处理配置文件"""
    
    def __init__(self, config_path: str = "config.json"):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径，默认为'config.json'
        """
        self.config_path = config_path
        self.config = self._load_config()
        logger.info(f"配置加载成功：{config_path}")
    
    def _load_config(self) -> Config:
        """
        加载配置文件
        
        如果配置文件不存在，则创建默认配置文件
        
        Returns:
            Config: 配置对象
        
        Raises:
            json.JSONDecodeError: 配置文件JSON格式错误
            ValueError: 配置数据验证失败
        """
        try:
            if not os.path.exists(self.config_path):
                logger.warning(f"配置文件不存在：{self.config_path}，将创建默认配置文件")
                # 创建默认配置模板
                default_config = self._create_default_config_template()
                # 确保目录存在
                os.makedirs(os.path.dirname(os.path.abspath(self.config_path)), exist_ok=True)
                # 写入默认配置
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, ensure_ascii=False, indent=2)
                # 返回创建的默认配置
                return Config(**default_config)
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            return Config(**config_data)
        except json.JSONDecodeError as e:
            logger.error(f"配置文件JSON格式错误：{e}")
            raise
        except Exception as e:
            logger.error(f"配置加载失败：{e}")
            raise ValueError(f"配置验证失败：{e}")
    
    def _create_default_config_template(self) -> Dict[str, Any]:
        """
        创建默认配置模板
        
        Returns:
            Dict[str, Any]: 默认配置字典
        """
        return {
            "GENERAL": {
                "api_id": 12345678,  # 占位符 API ID，用户需要替换为自己的真实值
                "api_hash": "0123456789abcdef0123456789abcdef",  # 占位符 API Hash，用户需要替换为自己的真实值
                "limit": 50,
                "pause_time": 60,
                "timeout": 30,
                "max_retries": 3,
                "proxy_enabled": False,
                "proxy_type": "SOCKS5",
                "proxy_addr": "127.0.0.1",
                "proxy_port": 1080,
                "proxy_username": None,
                "proxy_password": None
            },
            "DOWNLOAD": {
                "downloadSetting": [
                    {
                        "source_channels": "@username",  # 占位符频道名，用户需要替换为实际频道
                        "start_id": 0,
                        "end_id": 0,
                        "media_types": ["photo", "video", "document", "audio", "animation"],
                        "keywords": []
                    }
                ],
                "download_path": "downloads",
                "parallel_download": False,
                "max_concurrent_downloads": 10
            },
            "UPLOAD": {
                "target_channels": ["@username"],  # 占位符频道名，用户需要替换为实际频道
                "directory": "uploads",
                "caption_template": "{filename}",
                "delay_between_uploads": 0.5,
                "options": {
                    "use_folder_name": True,
                    "read_title_txt": False,
                    "use_custom_template": False,
                    "auto_thumbnail": True
                }
            },
            "FORWARD": {
                "forward_channel_pairs": [
                    {
                        "source_channel": "@username",  # 占位符频道名，用户需要替换为实际频道
                        "target_channels": ["@username"]  # 占位符频道名，用户需要替换为实际频道
                    }
                ],
                "remove_captions": False,
                "hide_author": False,
                "media_types": ["photo", "video", "document", "audio", "animation"],
                "forward_delay": 3,
                "start_id": 0,
                "end_id": 0,
                "tmp_path": "tmp"
            },
            "MONITOR": {
                "monitor_channel_pairs": [
                    {
                        "source_channel": "@username",  # 占位符频道名，用户需要替换为实际频道
                        "target_channels": ["@username"],  # 占位符频道名，用户需要替换为实际频道
                        "remove_captions": False,
                        "text_filter": []
                    }
                ],
                "media_types": ["photo", "video", "document", "audio", "animation", "sticker", "voice", "video_note"],
                "duration": (datetime.datetime.now().replace(year=datetime.datetime.now().year + 1)).strftime("%Y-%m-%d"),  # 设置为一年后
                "forward_delay": 3
            },
            "UI": {
                "theme": "深色主题",
                "confirm_exit": True,
                "minimize_to_tray": True,
                "start_minimized": False,
                "enable_notifications": True,
                "notification_sound": True,
                "window_geometry": None,
                "window_state": None
            }
        }
    
    def get_general_config(self) -> GeneralConfig:
        """获取通用配置"""
        return self.config.GENERAL
    
    def get_download_config(self) -> DownloadConfig:
        """获取下载配置"""
        return self.config.DOWNLOAD
    
    def get_upload_config(self) -> UploadConfig:
        """获取上传配置"""
        return self.config.UPLOAD
    
    def get_forward_config(self) -> ForwardConfig:
        """获取转发配置"""
        return self.config.FORWARD
    
    def get_monitor_config(self) -> MonitorConfig:
        """获取监听配置"""
        return self.config.MONITOR
    
    def get_proxy_settings(self) -> Dict[str, Any]:
        """
        获取代理设置
        
        Returns:
            Dict[str, Any]: 代理设置字典，用于Pyrogram客户端
        """
        general = self.get_general_config()
        if not general.proxy_enabled:
            return {}
        
        proxy = {
            "scheme": general.proxy_type.lower(),
            "hostname": general.proxy_addr,
            "port": general.proxy_port
        }
        
        if general.proxy_username and general.proxy_password:
            proxy["username"] = general.proxy_username
            proxy["password"] = general.proxy_password
            
        return {"proxy": proxy} 