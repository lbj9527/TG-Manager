"""
UI配置模型模块，为UI界面提供配置数据模型和验证逻辑
"""

import re
from typing import List, Dict, Any, Union, Optional
from datetime import datetime
from pydantic import BaseModel, Field, validator, root_validator
from enum import Enum, auto


class MediaType(str, Enum):
    """媒体类型枚举"""
    TEXT = "text"
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
    SOCKS4 = "SOCKS4"
    SOCKS5 = "SOCKS5"
    HTTP = "HTTP"
    HTTPS = "HTTPS"


class UIGeneralConfig(BaseModel):
    """通用配置模型"""
    api_id: int = Field(..., description="Telegram API ID")
    api_hash: str = Field(..., description="Telegram API Hash")
    limit: int = Field(50, description="每次批量获取消息的数量", ge=1, le=1000)
    pause_time: int = Field(60, description="API限制后的暂停时间(秒)", ge=1)
    timeout: int = Field(30, description="网络请求超时时间(秒)", ge=5, le=300)
    max_retries: int = Field(3, description="最大重试次数", ge=0, le=10)
    proxy_enabled: bool = Field(False, description="是否启用代理")
    proxy_type: ProxyType = Field(ProxyType.SOCKS5, description="代理类型")
    proxy_addr: str = Field("127.0.0.1", description="代理服务器地址")
    proxy_port: int = Field(1080, description="代理服务器端口", ge=1, le=65535)
    proxy_username: Optional[str] = Field(None, description="代理用户名(可选)")
    proxy_password: Optional[str] = Field(None, description="代理密码(可选)")

    @validator('api_id')
    def validate_api_id(cls, v):
        if v <= 0:
            raise ValueError("API ID必须是正整数")
        return v

    @validator('api_hash')
    def validate_api_hash(cls, v):
        if not re.match(r'^[a-f0-9]{32}$', v.lower()):
            raise ValueError("API Hash必须是32位十六进制字符串")
        return v

    @validator('proxy_addr')
    def validate_proxy_addr(cls, v, values):
        if values.get('proxy_enabled', False):
            if not v:
                raise ValueError("启用代理时，代理地址不能为空")
        return v


class UITextFilterItem(BaseModel):
    """文本替换项模型"""
    original_text: str = Field(..., description="原始文本")
    target_text: str = Field("", description="替换为的目标文本")

    class Config:
        title = "文本替换规则"


class UIChannelPair(BaseModel):
    """频道对配置模型"""
    source_channel: str = Field(..., description="源频道")
    target_channels: List[str] = Field(..., description="目标频道列表")

    @validator('source_channel')
    def validate_source_channel(cls, v):
        return cls.validate_channel_id(v, "源频道")

    @validator('target_channels')
    def validate_target_channels(cls, v):
        if not v:
            raise ValueError("目标频道列表不能为空")
        for i, channel in enumerate(v):
            v[i] = cls.validate_channel_id(channel, f"目标频道[{i}]")
        return v

    @classmethod
    def validate_channel_id(cls, channel_id: str, field_name: str) -> str:
        # 频道ID可以是数字、@用户名或完整的t.me链接
        if not channel_id:
            raise ValueError(f"{field_name}不能为空")
        
        # 标准化频道ID
        channel_id = channel_id.strip()
        
        # 检查是否为t.me链接
        if channel_id.startswith('https://t.me/'):
            # 验证链接格式
            if not re.match(r'^https://t\.me/([a-zA-Z][a-zA-Z0-9_]{3,}|joinchat/[a-zA-Z0-9_-]+|c/[0-9]+|[a-zA-Z0-9_-]+)(/[0-9]+)?$', channel_id):
                raise ValueError(f"{field_name}链接格式不正确")
        # 检查是否为@用户名
        elif channel_id.startswith('@'):
            # 验证用户名格式
            if not re.match(r'^@[a-zA-Z][a-zA-Z0-9_]{3,}$', channel_id):
                raise ValueError(f"{field_name}用户名格式不正确")
        # 检查是否为数字ID或带前缀的ID
        else:
            # 验证数字ID或带前缀的ID
            if not re.match(r'^-?[0-9]+$', channel_id) and not re.match(r'^[+\-][a-zA-Z0-9_-]+$', channel_id):
                raise ValueError(f"{field_name}ID格式不正确")
        
        return channel_id

    class Config:
        title = "频道配对"


class UIMonitorChannelPair(UIChannelPair):
    """监听频道对配置模型"""
    remove_captions: bool = Field(False, description="是否移除媒体说明文字")
    text_filter: List[UITextFilterItem] = Field(default_factory=list, description="文本替换规则")

    class Config:
        title = "监听频道配对"


class UIDownloadSettingItem(BaseModel):
    """下载设置项模型"""
    source_channels: str = Field(..., description="源频道")
    start_id: int = Field(0, description="起始消息ID (0表示从最新消息开始)")
    end_id: int = Field(0, description="结束消息ID (0表示下载到最早消息)")
    media_types: List[MediaType] = Field(
        default_factory=lambda: [MediaType.PHOTO, MediaType.VIDEO, MediaType.DOCUMENT, MediaType.AUDIO, MediaType.ANIMATION],
        description="要下载的媒体类型"
    )
    keywords: List[str] = Field(default_factory=list, description="关键词列表(用于关键词下载模式)")

    @validator('source_channels')
    def validate_source_channel(cls, v):
        return UIChannelPair.validate_channel_id(v, "源频道")

    @validator('start_id')
    def validate_start_id(cls, v):
        if v < 0:
            raise ValueError("起始消息ID不能小于0")
        return v

    @validator('end_id')
    def validate_end_id(cls, v, values):
        if v < 0:
            raise ValueError("结束消息ID不能小于0")
        if v > 0 and values.get('start_id', 0) > 0 and v < values['start_id']:
            raise ValueError("结束消息ID必须大于起始消息ID (当两者都不为0时)")
        return v

    @validator('keywords')
    def validate_keywords(cls, v):
        # 验证每个关键词非空
        for i, keyword in enumerate(v):
            if not keyword.strip():
                raise ValueError(f"关键词[{i}]不能为空")
        return [k.strip() for k in v]

    class Config:
        title = "下载设置项"


class UIDownloadConfig(BaseModel):
    """下载配置模型"""
    downloadSetting: List[UIDownloadSettingItem] = Field(
        default_factory=list, 
        description="下载设置列表"
    )
    download_path: str = Field("downloads", description="下载文件保存路径")
    parallel_download: bool = Field(False, description="是否启用并行下载")
    max_concurrent_downloads: int = Field(
        10, 
        description="最大并发下载数",
        ge=1, 
        le=50
    )

    @validator('downloadSetting')
    def validate_download_settings(cls, v):
        if not v:
            raise ValueError("至少需要一个下载设置项")
        return v

    @validator('download_path')
    def validate_download_path(cls, v):
        if not v:
            raise ValueError("下载路径不能为空")
        # 简单的路径字符检查
        if re.search(r'[<>:"|?*]', v):
            raise ValueError("下载路径包含非法字符")
        return v

    @validator('max_concurrent_downloads')
    def validate_max_concurrent_downloads(cls, v, values):
        if values.get('parallel_download', False) and v < 1:
            raise ValueError("启用并行下载时，最大并发下载数不能小于1")
        return v

    class Config:
        title = "下载配置"


class UIUploadConfig(BaseModel):
    """上传配置模型"""
    target_channels: List[str] = Field(..., description="目标频道列表")
    directory: str = Field("uploads", description="上传文件目录")
    caption_template: str = Field("{filename}", description="说明文字模板")
    delay_between_uploads: float = Field(0.5, description="上传间隔时间(秒)", ge=0)

    @validator('target_channels')
    def validate_target_channels(cls, v):
        if not v:
            raise ValueError("目标频道列表不能为空")
        for i, channel in enumerate(v):
            v[i] = UIChannelPair.validate_channel_id(channel, f"目标频道[{i}]")
        return v

    @validator('directory')
    def validate_directory(cls, v):
        if not v:
            raise ValueError("上传目录不能为空")
        # 简单的路径字符检查
        if re.search(r'[<>:"|?*]', v):
            raise ValueError("上传目录包含非法字符")
        return v

    @validator('caption_template')
    def validate_caption_template(cls, v):
        # 检查模板中的占位符是否有效
        valid_placeholders = ["{filename}", "{date}", "{time}", "{datetime}"]
        # 简单检查是否包含有效占位符
        has_valid_placeholder = any(placeholder in v for placeholder in valid_placeholders)
        if not has_valid_placeholder and "{" in v:
            raise ValueError("无效的说明文字模板占位符，有效的占位符包括: {filename}, {date}, {time}, {datetime}")
        return v

    class Config:
        title = "上传配置"


class UIForwardConfig(BaseModel):
    """转发配置模型"""
    forward_channel_pairs: List[UIChannelPair] = Field(..., description="转发频道对列表")
    remove_captions: bool = Field(False, description="是否移除媒体说明文字")
    hide_author: bool = Field(False, description="是否隐藏原作者")
    media_types: List[MediaType] = Field(
        default_factory=lambda: [MediaType.PHOTO, MediaType.VIDEO, MediaType.DOCUMENT, MediaType.AUDIO, MediaType.ANIMATION],
        description="要转发的媒体类型"
    )
    forward_delay: float = Field(0.1, description="转发间隔时间(秒)", ge=0)
    start_id: int = Field(0, description="起始消息ID (0表示从最新消息开始)")
    end_id: int = Field(0, description="结束消息ID (0表示转发到最早消息)")
    tmp_path: str = Field("tmp", description="临时文件路径")

    @validator('forward_channel_pairs')
    def validate_forward_channel_pairs(cls, v):
        if not v:
            raise ValueError("至少需要一个转发频道对")
        return v

    @validator('start_id')
    def validate_start_id(cls, v):
        if v < 0:
            raise ValueError("起始消息ID不能小于0")
        return v

    @validator('end_id')
    def validate_end_id(cls, v, values):
        if v < 0:
            raise ValueError("结束消息ID不能小于0")
        if v > 0 and values.get('start_id', 0) > 0 and v < values['start_id']:
            raise ValueError("结束消息ID必须大于起始消息ID (当两者都不为0时)")
        return v

    @validator('tmp_path')
    def validate_tmp_path(cls, v):
        if not v:
            raise ValueError("临时文件路径不能为空")
        # 简单的路径字符检查
        if re.search(r'[<>:"|?*]', v):
            raise ValueError("临时文件路径包含非法字符")
        return v

    class Config:
        title = "转发配置"


class UIMonitorConfig(BaseModel):
    """监听配置模型"""
    monitor_channel_pairs: List[UIMonitorChannelPair] = Field(..., description="监听频道对列表")
    media_types: List[MediaType] = Field(
        default_factory=lambda: [
            MediaType.PHOTO, MediaType.VIDEO, MediaType.DOCUMENT, 
            MediaType.AUDIO, MediaType.ANIMATION, MediaType.STICKER,
            MediaType.VOICE, MediaType.VIDEO_NOTE
        ],
        description="要监听的媒体类型"
    )
    duration: Optional[str] = Field(None, description="监听截止日期 (格式: YYYY-MM-DD)")
    forward_delay: float = Field(1.0, description="转发间隔时间(秒)", ge=0)

    @validator('monitor_channel_pairs')
    def validate_monitor_channel_pairs(cls, v):
        if not v:
            raise ValueError("至少需要一个监听频道对")
        return v

    @validator('duration')
    def validate_duration(cls, v):
        if v is not None:
            try:
                # 验证日期格式
                datetime.strptime(v, "%Y-%m-%d")
                # 检查日期是否已经过期
                if datetime.strptime(v, "%Y-%m-%d") < datetime.now():
                    raise ValueError("监听截止日期不能是过去的日期")
            except ValueError as e:
                if "does not match format" in str(e):
                    raise ValueError("监听截止日期格式不正确，应为 YYYY-MM-DD")
                raise
        return v

    class Config:
        title = "监听配置"


class UIConfig(BaseModel):
    """完整UI配置模型"""
    GENERAL: UIGeneralConfig
    DOWNLOAD: UIDownloadConfig
    UPLOAD: UIUploadConfig
    FORWARD: UIForwardConfig
    MONITOR: UIMonitorConfig

    class Config:
        title = "TG-Manager 配置"


# 用于UI界面生成的全局函数
def create_default_config() -> UIConfig:
    """
    创建默认配置
    
    Returns:
        UIConfig: 默认配置对象
    """
    return UIConfig(
        GENERAL=UIGeneralConfig(
            api_id=0,
            api_hash="",
            limit=50,
            pause_time=60,
            timeout=30,
            max_retries=3,
            proxy_enabled=False,
            proxy_type=ProxyType.SOCKS5,
            proxy_addr="127.0.0.1",
            proxy_port=1080
        ),
        DOWNLOAD=UIDownloadConfig(
            downloadSetting=[
                UIDownloadSettingItem(
                    source_channels="",
                    start_id=0,
                    end_id=0,
                    media_types=[MediaType.PHOTO, MediaType.VIDEO, MediaType.DOCUMENT, MediaType.AUDIO, MediaType.ANIMATION],
                    keywords=[]
                )
            ],
            download_path="downloads",
            parallel_download=False,
            max_concurrent_downloads=10
        ),
        UPLOAD=UIUploadConfig(
            target_channels=[""],
            directory="uploads",
            caption_template="{filename}",
            delay_between_uploads=0.5
        ),
        FORWARD=UIForwardConfig(
            forward_channel_pairs=[
                UIChannelPair(
                    source_channel="",
                    target_channels=[""]
                )
            ],
            remove_captions=False,
            hide_author=False,
            media_types=[MediaType.PHOTO, MediaType.VIDEO, MediaType.DOCUMENT, MediaType.AUDIO, MediaType.ANIMATION],
            forward_delay=0.1,
            start_id=0,
            end_id=0,
            tmp_path="tmp"
        ),
        MONITOR=UIMonitorConfig(
            monitor_channel_pairs=[
                UIMonitorChannelPair(
                    source_channel="",
                    target_channels=[""],
                    remove_captions=False,
                    text_filter=[]
                )
            ],
            media_types=[
                MediaType.PHOTO, MediaType.VIDEO, MediaType.DOCUMENT, 
                MediaType.AUDIO, MediaType.ANIMATION, MediaType.STICKER,
                MediaType.VOICE, MediaType.VIDEO_NOTE
            ],
            duration=None,
            forward_delay=1.0
        )
    )


def config_to_dict(config: UIConfig) -> Dict[str, Any]:
    """
    将配置对象转换为字典
    
    Args:
        config: 配置对象
        
    Returns:
        Dict[str, Any]: 配置字典
    """
    return config.dict()


def dict_to_config(config_dict: Dict[str, Any]) -> UIConfig:
    """
    将配置字典转换为配置对象
    
    Args:
        config_dict: 配置字典
        
    Returns:
        UIConfig: 配置对象
    """
    return UIConfig(**config_dict) 