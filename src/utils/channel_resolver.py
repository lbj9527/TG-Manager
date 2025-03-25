"""
频道解析器模块，负责解析各种格式的频道标识符，验证频道有效性，并管理频道状态
"""

import re
import time
from typing import Dict, List, Tuple, Optional, Union, Any
from datetime import datetime, timedelta

from pyrogram.errors import FloodWait, ChannelPrivate, UserNotParticipant
from pyrogram.types import Chat, Message

from src.utils.logger import get_logger

logger = get_logger()

class ChannelResolver:
    """
    频道解析器，用于将各种格式的频道标识符标准化，获取频道实例，缓存频道状态
    """
    
    def __init__(self, client):
        """
        初始化频道解析器
        
        Args:
            client: Pyrogram客户端实例
        """
        self.client = client
        # 缓存频道ID和实例，避免重复请求
        self._channel_cache: Dict[str, Tuple[int, Union[Chat, None]]] = {}
        # 缓存频道转发状态，减少API请求
        self._forward_status_cache: Dict[str, Tuple[bool, datetime]] = {}
        # 缓存过期时间（分钟）
        self._cache_expiry_minutes = 60
    
    async def resolve_channel(self, channel_identifier: str) -> Tuple[str, Optional[int]]:
        """
        解析频道标识符，获取标准化的频道ID和消息ID
        
        支持的格式：
        - 用户名格式: @channel_name
        - 纯用户名格式: channel_name
        - 链接格式: https://t.me/channel_name
        - 消息链接格式: https://t.me/channel_name/123
        - 数字ID格式: 1234567890
        - 私有频道链接格式: https://t.me/c/1234567890
        - 私有频道消息链接格式: https://t.me/c/1234567890/123
        - 邀请链接格式: https://t.me/+abcdefghijk
        - 纯邀请码格式: +abcdefghijk
        
        Args:
            channel_identifier: 频道标识符
            
        Returns:
            Tuple[str, Optional[int]]: (标准化频道ID, 消息ID或None)
        
        Raises:
            ValueError: 无法解析的频道标识符
        """
        # 清理标识符
        channel_identifier = channel_identifier.strip()
        
        # 尝试从缓存中获取
        if channel_identifier in self._channel_cache:
            channel_id, _ = self._channel_cache[channel_identifier]
            return channel_identifier, channel_id
        
        # 消息ID默认为None
        message_id = None
        
        # 处理不同格式的频道标识符
        if channel_identifier.startswith('@'):
            # @channel_name 格式
            channel_id = channel_identifier
        elif channel_identifier.startswith('+') or channel_identifier.startswith('https://t.me/+'):
            # 邀请链接格式
            if channel_identifier.startswith('https://t.me/+'):
                invite_code = channel_identifier.replace('https://t.me/+', '+')
            else:
                invite_code = channel_identifier
            channel_id = invite_code
        elif channel_identifier.startswith('https://t.me/c/'):
            # 私有频道链接格式
            match = re.match(r'https://t.me/c/(\d+)(?:/(\d+))?', channel_identifier)
            if match:
                chat_id, msg_id = match.groups()
                channel_id = int(chat_id)
                if msg_id:
                    message_id = int(msg_id)
            else:
                raise ValueError(f"无法解析私有频道链接：{channel_identifier}")
        elif channel_identifier.startswith('https://t.me/'):
            # 公开频道链接格式
            match = re.match(r'https://t.me/([^/]+)(?:/(\d+))?', channel_identifier)
            if match:
                username, msg_id = match.groups()
                channel_id = f"@{username}"
                if msg_id:
                    message_id = int(msg_id)
            else:
                raise ValueError(f"无法解析频道链接：{channel_identifier}")
        elif channel_identifier.isdigit() or (channel_identifier.startswith('-') and channel_identifier[1:].isdigit()):
            # 数字ID格式
            channel_id = int(channel_identifier)
        else:
            # 假设是纯用户名格式
            channel_id = f"@{channel_identifier}"
        
        return channel_id, message_id
    
    async def get_channel_entity(self, channel_id: Union[str, int]) -> Chat:
        """
        获取频道实体
        
        Args:
            channel_id: 频道ID或用户名
            
        Returns:
            Chat: 频道实体
            
        Raises:
            ChannelPrivate: 无法访问的私有频道
            ValueError: 无法获取频道实体
        """
        # 尝试从缓存中获取
        str_channel_id = str(channel_id)
        if str_channel_id in self._channel_cache:
            _, chat = self._channel_cache[str_channel_id]
            if chat:
                return chat
        
        # 获取频道实体
        try:
            chat = await self.client.get_chat(channel_id)
            # 缓存频道实体
            self._channel_cache[str_channel_id] = (chat.id, chat)
            
            # 返回实体
            return chat
        except FloodWait as e:
            logger.warning(f"获取频道信息被限制，等待 {e.x} 秒: {channel_id}")
            time.sleep(e.x)
            return await self.get_channel_entity(channel_id)
        except Exception as e:
            logger.error(f"获取频道实体失败：{channel_id}, 错误：{e}")
            raise ValueError(f"无法获取频道实体：{channel_id}, 错误：{str(e)}")
    
    async def get_channel_id(self, channel_identifier: str) -> int:
        """
        获取频道的数字ID
        
        Args:
            channel_identifier: 频道标识符
            
        Returns:
            int: 频道的数字ID
        """
        channel_id, _ = await self.resolve_channel(channel_identifier)
        
        # 如果已经是数字ID，直接返回
        if isinstance(channel_id, int):
            return channel_id
        
        # 尝试从缓存中获取
        str_channel_id = str(channel_id)
        if str_channel_id in self._channel_cache:
            numeric_id, _ = self._channel_cache[str_channel_id]
            return numeric_id
        
        # 获取频道实体
        chat = await self.get_channel_entity(channel_id)
        
        # 缓存并返回数字ID
        self._channel_cache[str_channel_id] = (chat.id, chat)
        return chat.id
    
    async def check_forward_permission(self, channel_id: Union[str, int]) -> bool:
        """
        检查频道是否允许转发
        
        Args:
            channel_id: 频道ID或用户名
            
        Returns:
            bool: 是否允许转发
        """
        # 尝试从缓存中获取
        str_channel_id = str(channel_id)
        if str_channel_id in self._forward_status_cache:
            status, cache_time = self._forward_status_cache[str_channel_id]
            # 检查缓存是否过期
            if datetime.now() - cache_time < timedelta(minutes=self._cache_expiry_minutes):
                return status
        
        # 获取频道实体
        try:
            chat = await self.get_channel_entity(channel_id)
            
            # 检查权限（需要进一步实际测试）
            if hasattr(chat, 'noforwards') and chat.noforwards:
                # 明确标记为禁止转发
                forward_allowed = False
            else:
                # 尝试获取一条消息并检查has_protected_content属性
                messages = await self.client.get_messages(chat.id, limit=1)
                if messages and hasattr(messages[0], 'has_protected_content') and messages[0].has_protected_content:
                    forward_allowed = False
                else:
                    forward_allowed = True
            
            # 缓存转发状态
            self._forward_status_cache[str_channel_id] = (forward_allowed, datetime.now())
            
            return forward_allowed
        except (ChannelPrivate, UserNotParticipant):
            # 无法访问的频道，假设禁止转发
            self._forward_status_cache[str_channel_id] = (False, datetime.now())
            return False
        except Exception as e:
            logger.error(f"检查转发权限失败：{channel_id}, 错误：{e}")
            # 发生错误，保守地假设禁止转发
            self._forward_status_cache[str_channel_id] = (False, datetime.now())
            return False
    
    async def get_non_restricted_channels(self, channel_ids: List[Union[str, int]]) -> List[Union[str, int]]:
        """
        获取不受转发限制的频道列表
        
        Args:
            channel_ids: 频道ID或用户名列表
            
        Returns:
            List[Union[str, int]]: 不受限制的频道列表
        """
        result = []
        for channel_id in channel_ids:
            if await self.check_forward_permission(channel_id):
                result.append(channel_id)
        return result
    
    async def format_channel_info(self, channel_id: Union[str, int]) -> str:
        """
        获取频道的格式化信息，用于日志和显示
        
        Args:
            channel_id: 频道ID或用户名
            
        Returns:
            str: 格式化的频道信息
        """
        try:
            chat = await self.get_channel_entity(channel_id)
            if chat.username:
                return f"@{chat.username} (ID: {chat.id})"
            elif hasattr(chat, 'title') and chat.title:
                return f"{chat.title} (ID: {chat.id})"
            else:
                return f"频道 (ID: {chat.id})"
        except Exception:
            # 如果无法获取频道信息，则返回原始ID
            return str(channel_id) 