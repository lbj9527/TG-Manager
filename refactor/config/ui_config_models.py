"""
UI配置模型

定义UI配置的数据模型，使用Pydantic进行数据验证。
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum

class MediaType(str, Enum):
    """媒体类型枚举"""
    PHOTO = "photo"
    VIDEO = "video"
    DOCUMENT = "document"
    AUDIO = "audio"
    ANIMATION = "animation"
    STICKER = "sticker"
    VOICE = "voice"
    VIDEO_NOTE = "video_note"

class ProxyType(str, Enum):
    """代理类型枚举"""
    SOCKS5 = "socks5"
    HTTP = "http"
    HTTPS = "https"

class UIGeneralConfig(BaseModel):
    """通用配置"""
    api_id: str = Field(..., description="Telegram API ID")
    api_hash: str = Field(..., description="Telegram API Hash")
    session_name: str = Field(default="tg_manager", description="会话名称")
    session_path: str = Field(default="sessions", description="会话文件路径")
    language: str = Field(default="zh_CN", description="界面语言")
    theme: str = Field(default="light_blue", description="界面主题")
    auto_reconnect: bool = Field(default=True, description="自动重连")
    max_reconnect_attempts: int = Field(default=5, description="最大重连次数")
    reconnect_delay: float = Field(default=1.0, description="重连延迟")

class UIDownloadConfig(BaseModel):
    """下载配置"""
    download_path: str = Field(default="downloads", description="下载路径")
    download_setting: List[Dict[str, Any]] = Field(default_factory=list, description="下载设置")

class UIUploadConfig(BaseModel):
    """上传配置"""
    directory: str = Field(default="uploads", description="上传目录")
    target_channels: List[str] = Field(default_factory=list, description="目标频道")
    options: Dict[str, Any] = Field(default_factory=dict, description="上传选项")

class UIForwardConfig(BaseModel):
    """转发配置"""
    forward_channel_pairs: List[Dict[str, Any]] = Field(default_factory=list, description="转发频道对")
    forward_delay: float = Field(default=0.1, description="转发延迟")
    tmp_path: str = Field(default="tmp", description="临时文件路径")

class UIMonitorConfig(BaseModel):
    """监听配置"""
    monitor_channel_pairs: List[Dict[str, Any]] = Field(default_factory=list, description="监听频道对")
    duration: str = Field(default="2024-12-31", description="监听截止日期")

class UIConfig(BaseModel):
    """UI配置主模型"""
    general: UIGeneralConfig = Field(default_factory=UIGeneralConfig, description="通用配置")
    download: UIDownloadConfig = Field(default_factory=UIDownloadConfig, description="下载配置")
    upload: UIUploadConfig = Field(default_factory=UIUploadConfig, description="上传配置")
    forward: UIForwardConfig = Field(default_factory=UIForwardConfig, description="转发配置")
    monitor: UIMonitorConfig = Field(default_factory=UIMonitorConfig, description="监听配置")
    
    class Config:
        """Pydantic配置"""
        validate_assignment = True
        extra = "forbid" 