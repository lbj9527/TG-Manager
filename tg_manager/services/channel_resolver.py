"""
频道解析器模块
负责解析频道标识符(链接/用户名/ID)，验证频道有效性，管理频道状态缓存
"""

import re
import time
from typing import Dict, Tuple, Union, Optional, List, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import asyncio

from pyrogram import Client
from pyrogram.types import Chat
from pyrogram.enums import ChatType

from tg_manager.utils.logger import get_logger

logger = get_logger("channel_resolver")


@dataclass
class ChannelInfo:
    """频道信息数据类"""
    channel_id: int  # 频道/群组的实际ID
    username: Optional[str] = None  # 频道用户名，如果有的话
    title: Optional[str] = None  # 频道标题
    can_forward: Optional[bool] = None  # 是否可以转发消息
    last_check: Optional[float] = None  # 最后检查时间戳
    
    def __post_init__(self):
        if self.last_check is None:
            self.last_check = time.time()


class ChannelResolver:
    """频道解析器，用于解析和验证各种格式的Telegram频道标识符"""
    
    # 链接模式正则表达式
    CHANNEL_PATTERNS = {
        # 用户名格式: @channel_name
        'username_prefix': re.compile(r'^@([a-zA-Z]\w{3,30}[a-zA-Z0-9])$'),
        
        # 纯用户名格式: channel_name
        'username': re.compile(r'^([a-zA-Z]\w{3,30}[a-zA-Z0-9])$'),
        
        # 链接格式: https://t.me/channel_name
        'public_link': re.compile(r'^(?:https?://)?(?:www\.)?t(?:elegram)?\.(?:me|dog)/([a-zA-Z]\w{3,30}[a-zA-Z0-9])(?:/.*)?$'),
        
        # 消息链接格式: https://t.me/channel_name/123
        'message_link': re.compile(r'^(?:https?://)?(?:www\.)?t(?:elegram)?\.(?:me|dog)/([a-zA-Z]\w{3,30}[a-zA-Z0-9])/(\d+)(?:/.*)?$'),
        
        # 私有频道链接格式: https://t.me/c/1234567890
        'private_link': re.compile(r'^(?:https?://)?(?:www\.)?t(?:elegram)?\.(?:me|dog)/c/(\d+)(?:/.*)?$'),
        
        # 私有频道消息链接格式: https://t.me/c/1234567890/123
        'private_message_link': re.compile(r'^(?:https?://)?(?:www\.)?t(?:elegram)?\.(?:me|dog)/c/(\d+)/(\d+)(?:/.*)?$'),
        
        # 邀请链接格式: https://t.me/+abcdefghijk
        'invite_link': re.compile(r'^(?:https?://)?(?:www\.)?t(?:elegram)?\.(?:me|dog)/\+([a-zA-Z0-9_-]+)$'),
        
        # 纯邀请码格式: +abcdefghijk
        'invite_code': re.compile(r'^\+([a-zA-Z0-9_-]+)$'),
        
        # 带前缀的邀请链接格式: @https://t.me/+abcdefghijk
        'prefixed_invite_link': re.compile(r'^@(?:https?://)?(?:www\.)?t(?:elegram)?\.(?:me|dog)/\+([a-zA-Z0-9_-]+)$'),
        
        # 数字ID格式: 1234567890
        'numeric_id': re.compile(r'^-?(\d+)$')
    }
    
    def __init__(self, client: Client, cache_timeout: int = 3600):
        """
        初始化频道解析器
        
        Args:
            client: Pyrogram客户端实例
            cache_timeout: 缓存超时时间（秒），默认1小时
        """
        self.client = client
        self.cache_timeout = cache_timeout
        self.channel_cache: Dict[str, ChannelInfo] = {}
    
    def parse_channel_link(self, channel_link: str) -> Tuple[Union[str, int], Optional[int]]:
        """
        解析频道链接，支持多种格式
        
        Args:
            channel_link: 频道链接或标识符
            
        Returns:
            元组，包含 (频道ID或用户名, 消息ID)
            如果没有消息ID，则第二个元素为None
        """
        # 尝试匹配所有模式
        for pattern_name, pattern in self.CHANNEL_PATTERNS.items():
            match = pattern.match(channel_link)
            if match:
                if pattern_name in ['username_prefix', 'username']:
                    # 用户名格式
                    return match.group(1), None
                elif pattern_name == 'public_link':
                    # 公开链接格式
                    return match.group(1), None
                elif pattern_name == 'message_link':
                    # 消息链接格式
                    return match.group(1), int(match.group(2))
                elif pattern_name == 'private_link':
                    # 私有频道链接格式
                    return int(match.group(1)), None
                elif pattern_name == 'private_message_link':
                    # 私有频道消息链接格式
                    return int(match.group(1)), int(match.group(2))
                elif pattern_name in ['invite_link', 'invite_code', 'prefixed_invite_link']:
                    # 邀请链接格式，需要特殊处理
                    return f"+{match.group(1)}", None
                elif pattern_name == 'numeric_id':
                    # 数字ID格式
                    return int(match.group(1)), None
        
        # 如果没有匹配，尝试作为用户名处理(移除@前缀)
        if channel_link.startswith('@'):
            return channel_link[1:], None
        
        # 如果仍然无法解析，返回原始链接
        logger.warning(f"无法解析频道链接: {channel_link}")
        return channel_link, None
    
    async def get_channel_info(self, channel_identifier: Union[str, int]) -> Optional[ChannelInfo]:
        """
        获取频道信息，支持缓存
        
        Args:
            channel_identifier: 频道标识符，可以是链接、用户名或ID
            
        Returns:
            频道信息对象，如果获取失败则返回None
        """
        # 先解析频道标识符
        channel_id_or_username, _ = self.parse_channel_link(str(channel_identifier))

        
        # 生成缓存键
        cache_key = str(channel_id_or_username)
        
        # 检查缓存是否有效
        if cache_key in self.channel_cache:
            channel_info = self.channel_cache[cache_key]
            # 检查缓存是否过期
            if time.time() - channel_info.last_check < self.cache_timeout:
                logger.warning(f"使用缓存的频道信息: {cache_key}")
                return channel_info
        
        # 尝试获取频道信息
        try:
            chat = await self.client.get_chat(channel_id_or_username)
            
            # 判断是否为频道或群组
            if not (chat.type in [ChatType.CHANNEL, ChatType.SUPERGROUP, ChatType.GROUP]):
                logger.warning(f"标识符 {channel_identifier} 不是频道或群组，类型是: {chat.type}")
                return None
            
            # 创建频道信息对象
            channel_info = ChannelInfo(
                channel_id=chat.id,
                username=chat.username,
                title=chat.title,
                can_forward=await self._check_forward_permission(chat),
                last_check=time.time()
            )
            
            # 更新缓存
            self.channel_cache[cache_key] = channel_info
            # 使用真实ID也进行缓存，方便后续查询
            self.channel_cache[str(chat.id)] = channel_info
            
            logger.info(f"已获取频道信息: {chat.title} ({chat.id}), 可转发: {channel_info.can_forward}")
            return channel_info
        
        except Exception as e:
            logger.error(f"获取频道信息失败: {channel_identifier}, 错误: {e}")
            return None
    
    async def _check_forward_permission(self, chat: Chat) -> bool:
        """
        检查频道是否允许转发内容
        
        Args:
            chat: Pyrogram Chat对象
            
        Returns:
            如果允许转发则返回True，否则返回False
        """
        try:
            # 对于频道，检查是否设置了禁止转发标志
            if hasattr(chat, "has_protected_content") and chat.has_protected_content:
                return False
            
            # 对于群组，检查是否设置了禁止转发标志
            if chat.type in ["group", "supergroup"]:
                if hasattr(chat, "restrictions") and any(r.reason == "restricted" for r in chat.restrictions):
                    return False
            
            return True
        except Exception as e:
            logger.error(f"检查转发权限失败: {chat.id}, 错误: {e}")
            # 默认为可以转发
            return True
    
    async def sort_channels_by_forward_permission(self, 
                                                 channels: List[str]) -> Tuple[List[str], List[str]]:
        """
        根据转发权限对频道列表进行排序
        
        Args:
            channels: 频道标识符列表
            
        Returns:
            元组，包含 (可转发频道列表, 不可转发频道列表)
        """
        forwardable = []
        non_forwardable = []
        
        for channel in channels:
            info = await self.get_channel_info(channel)
            if info and info.can_forward:
                forwardable.append(channel)
            else:
                non_forwardable.append(channel)
        
        return forwardable, non_forwardable
    
    async def resolve_real_id(self, channel_identifier: Union[str, int]) -> Optional[int]:
        """
        解析频道标识符为真实ID
        
        Args:
            channel_identifier: 频道标识符
            
        Returns:
            频道的真实ID，如果解析失败则返回None
        """
        info = await self.get_channel_info(channel_identifier)
        return info.channel_id if info else None
    
    def format_channel_for_display(self, channel_identifier: Union[str, int]) -> str:
        """
        格式化频道标识符用于显示
        
        Args:
            channel_identifier: 频道标识符
            
        Returns:
            用于显示的频道格式
        """
        # 解析频道标识符
        channel_id_or_username, _ = self.parse_channel_link(str(channel_identifier))
        
        # 查找缓存中的信息
        cache_key = str(channel_id_or_username)
        if cache_key in self.channel_cache:
            info = self.channel_cache[cache_key]
            if info.title:
                return f"{info.title} ({channel_id_or_username})"
        
        # 如果没有缓存信息，返回原始标识符
        return str(channel_identifier)
    
    def clear_cache(self) -> None:
        """清除频道缓存"""
        self.channel_cache.clear()
        logger.info("已清除频道缓存")
    
    def clear_expired_cache(self) -> None:
        """清除过期的频道缓存"""
        now = time.time()
        expired_keys = [
            k for k, v in self.channel_cache.items() 
            if now - v.last_check >= self.cache_timeout
        ]
        
        for key in expired_keys:
            del self.channel_cache[key]
        
        logger.info(f"已清除 {len(expired_keys)} 个过期频道缓存") 