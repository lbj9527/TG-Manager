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
    phone_number: Optional[str] = Field(None, description="Telegram账号手机号码")
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
    auto_restart_session: bool = Field(True, description="连接断开后自动重连")

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

    @validator('proxy_port')
    def validate_proxy_port(cls, v, values):
        if values.get('proxy_enabled', False):
            if v < 1 or v > 65535:
                raise ValueError("代理端口必须在1-65535范围内")
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
    media_types: List[MediaType] = Field(
        default_factory=lambda: [MediaType.TEXT, MediaType.PHOTO, MediaType.VIDEO, MediaType.DOCUMENT, MediaType.AUDIO, MediaType.ANIMATION],
        description="要转发的媒体类型"
    )
    start_id: int = Field(0, description="起始消息ID (0表示从最早消息开始)")
    end_id: int = Field(0, description="结束消息ID (0表示转发到最新消息)")
    # 启用/禁用状态
    enabled: bool = Field(True, description="是否启用此频道对转发")
    # 转发选项参数
    remove_captions: bool = Field(False, description="是否移除媒体说明文字")
    hide_author: bool = Field(False, description="是否隐藏原作者")
    send_final_message: bool = Field(False, description="是否在转发完成后发送最后一条消息")
    final_message_html_file: str = Field("", description="最后一条消息的HTML文件路径")
    enable_web_page_preview: bool = Field(False, description="是否启用最终消息的网页预览")
    # 新增字段：文本替换规则和关键词过滤
    text_filter: List[Dict[str, str]] = Field(
        default_factory=lambda: [{"original_text": "", "target_text": ""}],
        description="文本替换规则列表"
    )
    keywords: List[str] = Field(default_factory=list, description="关键词列表(用于关键词过滤)")
    # 新增字段：排除含链接消息
    exclude_links: bool = Field(False, description="是否排除含链接的消息")

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

    @validator('text_filter')
    def validate_text_filter(cls, v):
        if not v:
            return [{"original_text": "", "target_text": ""}]
        
        # 确保每个规则都有必要的字段
        validated_rules = []
        for rule in v:
            if isinstance(rule, dict):
                validated_rule = {
                    "original_text": rule.get("original_text", ""),
                    "target_text": rule.get("target_text", "")
                }
                validated_rules.append(validated_rule)
            else:
                # 如果不是字典，创建默认规则
                validated_rules.append({"original_text": "", "target_text": ""})
        
        # 如果没有有效规则，添加默认规则
        if not validated_rules:
            validated_rules = [{"original_text": "", "target_text": ""}]
        
        return validated_rules

    @validator('keywords')
    def validate_keywords(cls, v):
        # 过滤空关键词并去除首尾空格
        if isinstance(v, list):
            # 过滤掉空字符串和仅包含空白字符的关键词
            filtered_keywords = [keyword.strip() for keyword in v if keyword and keyword.strip()]
            return filtered_keywords
        return v

    @validator('final_message_html_file')
    def validate_final_message_html_file(cls, v):
        # 如果路径为空，直接返回
        if not v:
            return v
        # 检查路径是否包含非法字符
        if re.search(r'[<>"|?*]', v):
            raise ValueError("最终消息HTML文件路径包含非法字符")
        return v

    @classmethod
    def validate_channel_id(cls, channel_id: str, field_name: str) -> str:
        """
        验证并标准化频道ID/链接格式
        
        Args:
            channel_id: 频道ID/链接
            field_name: 字段名称（用于错误消息）
        
        Returns:
            str: 标准化后的频道ID/链接
        
        Raises:
            ValueError: 当频道ID/链接格式无效时
        """
        # 频道ID可以是数字、@用户名、完整的t.me链接或+开头的私有ID
        if not channel_id:
            raise ValueError(f"{field_name}不能为空")
        
        # 标准化频道ID
        channel_id = channel_id.strip()
        
        # 优先处理特殊格式：通过/+或+开头的私有链接
        if channel_id.startswith('+') or '/+' in channel_id:
            # 如果是https://t.me/+xxx格式的私有频道邀请链接
            if channel_id.startswith('https://t.me/+'):
                invite_code = channel_id.split('/+', 1)[1].split('/', 1)[0]
                if invite_code:
                    return '+' + invite_code  # 只保留邀请码部分，格式为+xxx
            # 已经是+xxx格式的私有频道ID
            elif channel_id.startswith('+') and len(channel_id) > 1:
                return channel_id
        
        # 检查是否为t.me链接
        if channel_id.startswith('https://t.me/'):
            # 放宽链接格式限制
            if '/joinchat/' in channel_id or '/c/' in channel_id or '/s/' in channel_id:
                return channel_id  # 支持joinchat、频道、超级群组链接
            # 尝试提取用户名或ID
            parts = channel_id.split('/')
            if len(parts) >= 4:
                username = parts[3].split('?')[0]  # 移除可能的查询参数
                if username:
                    # 检查是否包含消息ID (格式如 https://t.me/username/123)
                    if len(parts) >= 5 and parts[4].isdigit():
                        return channel_id  # 保持原链接，包含消息ID
                    # 否则只返回用户名部分
                    return '@' + username
        
        # 检查是否为@用户名
        if channel_id.startswith('@'):
            username = channel_id[1:]
            # 放宽用户名验证要求
            if len(username) >= 3:
                return channel_id
        
        # 检查是否为数字ID
        if re.match(r'^-?[0-9]+$', channel_id):
            return channel_id
        
        # 尝试处理其他格式的私有链接或ID
        if re.match(r'^[+\-][a-zA-Z0-9_-]+$', channel_id):
            return channel_id
        
        # 特殊处理：可能是不带@的用户名
        if re.match(r'^[a-zA-Z][a-zA-Z0-9_]{3,}$', channel_id):
            return '@' + channel_id
        
        # 所有验证都失败
        raise ValueError(f"{field_name}格式不正确，支持@用户名、数字ID、t.me链接或私有频道链接")

    class Config:
        title = "频道配对"


class UIMonitorChannelPair(BaseModel):
    """监听频道对模型"""
    source_channel: str = Field(..., description="源频道链接或ID")
    target_channels: List[str] = Field(..., description="目标频道列表")
    remove_captions: bool = Field(False, description="是否移除媒体说明")
    text_filter: List[Dict[str, str]] = Field(
        default_factory=lambda: [{"original_text": "", "target_text": ""}],
        description="文本替换规则列表"
    )
    media_types: List[MediaType] = Field(
        default_factory=lambda: [
            MediaType.PHOTO, MediaType.VIDEO, MediaType.DOCUMENT, 
            MediaType.AUDIO, MediaType.ANIMATION, MediaType.STICKER,
            MediaType.VOICE, MediaType.VIDEO_NOTE
        ],
        description="该频道对要监听的媒体类型"
    )
    # 过滤选项
    keywords: List[str] = Field(default_factory=list, description="关键词列表(用于关键词过滤)")
    exclude_forwards: bool = Field(False, description="是否排除转发消息")
    exclude_replies: bool = Field(False, description="是否排除回复消息")
    exclude_text: bool = Field(False, description="是否排除纯文本消息")
    exclude_links: bool = Field(False, description="是否排除包含链接的消息")

    @validator('source_channel')
    def validate_source_channel(cls, v):
        return UIChannelPair.validate_channel_id(v, "源频道")

    @validator('target_channels')
    def validate_target_channels(cls, v):
        if not v:
            raise ValueError("至少需要一个目标频道")
        
        validated_channels = []
        for i, channel in enumerate(v):
            if not channel or not channel.strip():
                continue  # 跳过空的频道
            validated_channel = UIChannelPair.validate_channel_id(channel, f"第{i+1}个目标频道")
            validated_channels.append(validated_channel)
        
        if not validated_channels:
            raise ValueError("至少需要一个有效的目标频道")
        
        return validated_channels

    @validator('text_filter')
    def validate_text_filter(cls, v):
        if not v:
            return [{"original_text": "", "target_text": ""}]
        
        # 确保每个规则都有必要的字段
        validated_rules = []
        for rule in v:
            if isinstance(rule, dict):
                validated_rule = {
                    "original_text": rule.get("original_text", ""),
                    "target_text": rule.get("target_text", "")
                }
                validated_rules.append(validated_rule)
        
        # 如果没有有效规则，添加一个空规则
        if not validated_rules:
            validated_rules = [{"original_text": "", "target_text": ""}]
        
        return validated_rules

    @validator('media_types')
    def validate_media_types(cls, v):
        if not v:
            # 如果为空，返回默认的所有媒体类型
            return [
                MediaType.PHOTO, MediaType.VIDEO, MediaType.DOCUMENT, 
                MediaType.AUDIO, MediaType.ANIMATION, MediaType.STICKER,
                MediaType.VOICE, MediaType.VIDEO_NOTE
            ]
        return v

    @validator('keywords')
    def validate_keywords(cls, v):
        # 过滤空关键词并去除首尾空格
        if isinstance(v, list):
            # 过滤掉空字符串和仅包含空白字符的关键词
            filtered_keywords = [keyword.strip() for keyword in v if keyword and keyword.strip()]
            return filtered_keywords
        return v

    class Config:
        title = "监听频道对"


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
    dir_size_limit_enabled: bool = Field(False, description="是否启用下载目录大小限制")
    dir_size_limit: int = Field(1000, description="下载目录大小限制(MB)", ge=1, le=100000)

    @validator('downloadSetting')
    def validate_download_settings(cls, v):
        if not v:
            raise ValueError("至少需要一个下载设置项")
        return v

    @validator('download_path')
    def validate_download_path(cls, v):
        if not v:
            raise ValueError("下载路径不能为空")
        # 修改路径字符检查，允许Windows盘符格式（如D:）
        if re.search(r'[<>"|?*]', v):
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
    delay_between_uploads: float = Field(0.5, description="上传间隔时间(秒)", ge=0)
    options: dict = Field(
        default_factory=lambda: {
            "use_folder_name": True,
            "read_title_txt": False,
            "send_final_message": False,
            "auto_thumbnail": True,
            "final_message_html_file": "",
            "enable_web_page_preview": False
        },
        description="上传选项"
    )

    @validator('target_channels')
    def validate_target_channels(cls, v):
        if not v:
            raise ValueError("目标频道列表不能为空")
        for i, channel in enumerate(v):
            v[i] = UIChannelPair.validate_channel_id(channel, f"目标频道[{i}]")
        return v

    @validator('delay_between_uploads')
    def round_delay_between_uploads(cls, v):
        """将上传延迟四舍五入到一位小数，避免浮点数精度问题"""
        if v is not None:
            return round(v, 1)
        return v

    @validator('directory')
    def validate_directory(cls, v):
        if not v:
            raise ValueError("上传目录不能为空")
        # 修改路径字符检查，允许Windows盘符格式（如D:）
        if re.search(r'[<>"|?*]', v):
            raise ValueError("上传目录包含非法字符")
        return v

    class Config:
        title = "上传配置"


class UIForwardConfig(BaseModel):
    """转发配置模型"""
    forward_channel_pairs: List[UIChannelPair] = Field(..., description="转发频道对列表")
    forward_delay: float = Field(0.1, description="转发间隔时间(秒)", ge=0)
    tmp_path: str = Field("tmp", description="临时文件路径")

    @validator('forward_channel_pairs')
    def validate_forward_channel_pairs(cls, v):
        if not v:
            raise ValueError("至少需要一个转发频道对")
        return v

    @validator('forward_delay')
    def round_forward_delay(cls, v):
        return round(v, 1)

    @validator('tmp_path')
    def validate_tmp_path(cls, v):
        if not v:
            raise ValueError("临时文件路径不能为空")
        # 修改路径字符检查，允许Windows盘符格式（如D:）
        if re.search(r'[<>"|?*]', v):
            raise ValueError("临时文件路径包含非法字符")
        return v

    class Config:
        title = "转发配置"


class UIMonitorConfig(BaseModel):
    """监听配置模型"""
    monitor_channel_pairs: List[UIMonitorChannelPair] = Field(..., description="监听频道对列表")
    duration: Optional[str] = Field(None, description="监听截止日期 (格式: YYYY-MM-DD)")

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


class UIUIConfig(BaseModel):
    """用户界面配置模型"""
    theme: str = Field("深色主题", description="界面主题")
    confirm_exit: bool = Field(True, description="退出时是否需要确认")
    minimize_to_tray: bool = Field(True, description="最小化到系统托盘")
    start_minimized: bool = Field(False, description="启动时最小化")
    enable_notifications: bool = Field(True, description="启用通知")
    notification_sound: bool = Field(True, description="启用通知声音")
    window_geometry: Optional[str] = Field(None, description="窗口几何位置")
    window_state: Optional[str] = Field(None, description="窗口状态(包含工具栏位置)")

    class Config:
        title = "界面配置"


class UIConfig(BaseModel):
    """完整UI配置模型"""
    GENERAL: UIGeneralConfig
    DOWNLOAD: UIDownloadConfig
    UPLOAD: UIUploadConfig
    FORWARD: UIForwardConfig
    MONITOR: UIMonitorConfig
    UI: UIUIConfig

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
            api_id=12345678,  # 占位符 API ID，用户需要替换为自己的真实值
            api_hash="0123456789abcdef0123456789abcdef",  # 占位符 API Hash，用户需要替换为自己的真实值
            phone_number=None,
            limit=50,
            pause_time=60,
            timeout=30,
            max_retries=3,
            proxy_enabled=False,
            proxy_type=ProxyType.SOCKS5,
            proxy_addr="127.0.0.1",
            proxy_port=1080,  # 确保即使禁用代理，端口值也有效
            proxy_username=None,
            proxy_password=None,
            auto_restart_session=True  # 默认启用自动重连
        ),
        DOWNLOAD=UIDownloadConfig(
            downloadSetting=[
                UIDownloadSettingItem(
                    source_channels="@username",  # 占位符频道名，用户需要替换为实际频道
                    start_id=0,
                    end_id=0,
                    media_types=[MediaType.PHOTO, MediaType.VIDEO, MediaType.DOCUMENT, MediaType.AUDIO, MediaType.ANIMATION],
                    keywords=[]
                )
            ],
            download_path="downloads",
            parallel_download=False,
            max_concurrent_downloads=10,
            dir_size_limit_enabled=False,
            dir_size_limit=1000  # 默认1000MB (1GB)
        ),
        UPLOAD=UIUploadConfig(
            target_channels=["@username"],  # 占位符频道名，用户需要替换为实际频道
            directory="uploads",
            delay_between_uploads=0.5
        ),
        FORWARD=UIForwardConfig(
            forward_channel_pairs=[
                UIChannelPair(
                    source_channel="@username",  # 占位符频道名，用户需要替换为实际频道
                    target_channels=["@username"],  # 占位符频道名，用户需要替换为实际频道
                    media_types=[MediaType.TEXT, MediaType.PHOTO, MediaType.VIDEO, MediaType.DOCUMENT, MediaType.AUDIO, MediaType.ANIMATION],
                    start_id=0,
                    end_id=0,
                    remove_captions=False,
                    hide_author=False,
                    send_final_message=False,
                    final_message_html_file="",
                    text_filter=[{"original_text": "", "target_text": ""}],
                    keywords=[]
                )
            ],
            forward_delay=0.1,
            tmp_path="tmp"
        ),
        MONITOR=UIMonitorConfig(
            monitor_channel_pairs=[
                UIMonitorChannelPair(
                    source_channel="@example_source",
                    target_channels=["@example_target1", "@example_target2"],
                    remove_captions=False,
                    text_filter=[
                        {"original_text": "示例文本", "target_text": "替换后的文本"}
                    ],
                    media_types=[MediaType.PHOTO, MediaType.VIDEO, MediaType.DOCUMENT, MediaType.AUDIO, MediaType.ANIMATION],
                    keywords=["示例关键词1", "示例关键词2"],
                    exclude_forwards=False,
                    exclude_replies=False,
                    exclude_text=False,
                    exclude_links=False
                )
            ],
            duration=(datetime.now().replace(year=datetime.now().year + 1)).strftime("%Y-%m-%d"),  # 设置为一年后
        ),
        UI=UIUIConfig(
            theme="深色主题",
            confirm_exit=True,
            minimize_to_tray=True,
            start_minimized=False,
            enable_notifications=True,
            notification_sound=True,
            window_geometry=None,
            window_state=None
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