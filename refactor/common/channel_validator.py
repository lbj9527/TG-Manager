"""
统一频道验证器

提供统一的频道验证接口，包括频道信息获取、权限检查等功能。
"""

import asyncio
import time
from typing import Any, Dict, List, Optional, Tuple, Union
from loguru import logger

from pyrogram import Client
from pyrogram.errors import (
    FloodWait, ChannelPrivate, ChatAdminRequired, 
    UserNotParticipant, ChatWriteForbidden
)
from pyrogram.types import Chat, ChatMember

from common.flood_wait_handler import FloodWaitHandler
from common.error_handler import ErrorHandler, ErrorType


class ChannelValidator:
    """统一频道验证器"""
    
    def __init__(self, client: Client):
        self.client = client
        self.flood_wait_handler = FloodWaitHandler()
        self.error_handler = ErrorHandler()
        
        # 缓存配置
        self.cache_enabled = True
        self.cache_size = 500
        self.channel_cache: Dict[str, Dict[str, Any]] = {}
        self.permission_cache: Dict[str, Dict[str, Any]] = {}
    
    def set_event_bus(self, event_bus) -> None:
        """设置事件总线"""
        self.event_bus = event_bus
        self.flood_wait_handler.set_event_bus(event_bus)
        self.error_handler.set_event_bus(event_bus)
    
    async def validate_channel(self, channel_id: Union[int, str]) -> Tuple[bool, Optional[str]]:
        """
        验证频道是否有效
        
        Args:
            channel_id: 频道ID或用户名
            
        Returns:
            (是否有效, 错误信息)
        """
        try:
            logger.info(f"验证频道: {channel_id}")
            
            # 检查缓存
            if self.cache_enabled:
                cache_key = str(channel_id)
                if cache_key in self.channel_cache:
                    cache_data = self.channel_cache[cache_key]
                    if not self._is_cache_expired(cache_data):
                        logger.debug(f"从缓存获取频道验证结果: {channel_id}")
                        return cache_data['valid'], cache_data.get('error')
            
            # 获取频道信息
            chat = await self._get_chat_info(channel_id)
            
            if chat:
                # 验证成功
                result = (True, None)
                if self.cache_enabled:
                    self._add_to_channel_cache(str(channel_id), {
                        'valid': True,
                        'chat_info': self._extract_chat_info(chat),
                        'timestamp': self._get_current_timestamp()
                    })
                return result
            else:
                # 验证失败
                result = (False, "无法获取频道信息")
                if self.cache_enabled:
                    self._add_to_channel_cache(str(channel_id), {
                        'valid': False,
                        'error': result[1],
                        'timestamp': self._get_current_timestamp()
                    })
                return result
                
        except Exception as e:
            error_info = self.error_handler.handle_error(e, {
                'operation': 'validate_channel',
                'channel_id': channel_id
            })
            logger.error(f"验证频道失败: {error_info}")
            return False, str(error_info)
    
    async def get_channel_info(self, channel_id: Union[int, str]) -> Optional[Dict[str, Any]]:
        """
        获取频道信息
        
        Args:
            channel_id: 频道ID或用户名
            
        Returns:
            频道信息字典
        """
        try:
            logger.info(f"获取频道信息: {channel_id}")
            
            # 检查缓存
            if self.cache_enabled:
                cache_key = str(channel_id)
                if cache_key in self.channel_cache:
                    cache_data = self.channel_cache[cache_key]
                    if not self._is_cache_expired(cache_data):
                        logger.debug(f"从缓存获取频道信息: {channel_id}")
                        return cache_data.get('chat_info')
            
            # 获取频道信息
            chat = await self._get_chat_info(channel_id)
            
            if chat:
                chat_info = self._extract_chat_info(chat)
                
                # 更新缓存
                if self.cache_enabled:
                    self._add_to_channel_cache(str(channel_id), {
                        'valid': True,
                        'chat_info': chat_info,
                        'timestamp': self._get_current_timestamp()
                    })
                
                return chat_info
            
            return None
            
        except Exception as e:
            error_info = self.error_handler.handle_error(e, {
                'operation': 'get_channel_info',
                'channel_id': channel_id
            })
            logger.error(f"获取频道信息失败: {error_info}")
            return None
    
    async def check_permissions(self, channel_id: Union[int, str], 
                               required_permissions: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        检查频道权限
        
        Args:
            channel_id: 频道ID或用户名
            required_permissions: 需要的权限列表
            
        Returns:
            权限检查结果
        """
        try:
            logger.info(f"检查频道权限: {channel_id}")
            
            # 检查缓存
            if self.cache_enabled:
                cache_key = f"{channel_id}_permissions"
                if cache_key in self.permission_cache:
                    cache_data = self.permission_cache[cache_key]
                    if not self._is_cache_expired(cache_data):
                        logger.debug(f"从缓存获取权限信息: {channel_id}")
                        return cache_data['permissions']
            
            # 获取当前用户信息
            me = await self.client.get_me()
            
            # 获取频道成员信息
            member = await self._get_chat_member(channel_id, me.id)
            
            if not member:
                result = {
                    'can_access': False,
                    'reason': '无法获取成员信息',
                    'permissions': {}
                }
            else:
                # 分析权限
                permissions = self._analyze_permissions(member)
                
                # 检查所需权限
                can_access = True
                missing_permissions = []
                
                if required_permissions:
                    for perm in required_permissions:
                        if not permissions.get(perm, False):
                            can_access = False
                            missing_permissions.append(perm)
                
                result = {
                    'can_access': can_access,
                    'member_type': member.status.value,
                    'permissions': permissions,
                    'missing_permissions': missing_permissions
                }
            
            # 更新缓存
            if self.cache_enabled:
                self._add_to_permission_cache(f"{channel_id}_permissions", {
                    'permissions': result,
                    'timestamp': self._get_current_timestamp()
                })
            
            return result
            
        except Exception as e:
            error_info = self.error_handler.handle_error(e, {
                'operation': 'check_permissions',
                'channel_id': channel_id,
                'required_permissions': required_permissions
            })
            logger.error(f"检查频道权限失败: {error_info}")
            return {
                'can_access': False,
                'reason': str(error_info),
                'permissions': {}
            }
    
    async def check_forward_permission(self, channel_id: Union[int, str]) -> bool:
        """
        检查转发权限
        
        Args:
            channel_id: 频道ID或用户名
            
        Returns:
            是否可以转发
        """
        try:
            logger.info(f"检查转发权限: {channel_id}")
            
            # 检查缓存
            if self.cache_enabled:
                cache_key = f"{channel_id}_forward"
                if cache_key in self.permission_cache:
                    cache_data = self.permission_cache[cache_key]
                    if not self._is_cache_expired(cache_data):
                        logger.debug(f"从缓存获取转发权限: {channel_id}")
                        return cache_data['can_forward']
            
            # 获取频道信息
            chat = await self._get_chat_info(channel_id)
            
            if not chat:
                return False
            
            # 检查是否为私有频道
            if chat.type.value in ['private', 'bot']:
                # 私有频道通常可以转发
                can_forward = True
            else:
                # 公共频道，检查权限
                permissions = await self.check_permissions(channel_id)
                can_forward = permissions.get('can_access', False)
            
            # 更新缓存
            if self.cache_enabled:
                self._add_to_permission_cache(f"{channel_id}_forward", {
                    'can_forward': can_forward,
                    'timestamp': self._get_current_timestamp()
                })
            
            return can_forward
            
        except Exception as e:
            error_info = self.error_handler.handle_error(e, {
                'operation': 'check_forward_permission',
                'channel_id': channel_id
            })
            logger.error(f"检查转发权限失败: {error_info}")
            return False
    
    async def resolve_channel_id(self, channel_name: str) -> Optional[int]:
        """
        解析频道名称到ID
        
        Args:
            channel_name: 频道名称或用户名
            
        Returns:
            频道ID
        """
        try:
            logger.info(f"解析频道ID: {channel_name}")
            
            # 检查缓存
            if self.cache_enabled:
                cache_key = f"resolve_{channel_name}"
                if cache_key in self.channel_cache:
                    cache_data = self.channel_cache[cache_key]
                    if not self._is_cache_expired(cache_data):
                        logger.debug(f"从缓存获取频道ID: {channel_name}")
                        return cache_data.get('channel_id')
            
            # 清理频道名称
            clean_name = self._clean_channel_name(channel_name)
            
            # 尝试获取频道信息
            chat = await self._get_chat_info(clean_name)
            
            if chat:
                channel_id = chat.id
                
                # 更新缓存
                if self.cache_enabled:
                    self._add_to_channel_cache(f"resolve_{channel_name}", {
                        'channel_id': channel_id,
                        'timestamp': self._get_current_timestamp()
                    })
                
                return channel_id
            
            return None
            
        except Exception as e:
            error_info = self.error_handler.handle_error(e, {
                'operation': 'resolve_channel_id',
                'channel_name': channel_name
            })
            logger.error(f"解析频道ID失败: {error_info}")
            return None
    
    async def get_channel_members_count(self, channel_id: Union[int, str]) -> Optional[int]:
        """
        获取频道成员数量
        
        Args:
            channel_id: 频道ID或用户名
            
        Returns:
            成员数量
        """
        try:
            logger.info(f"获取频道成员数量: {channel_id}")
            
            chat = await self._get_chat_info(channel_id)
            
            if chat:
                return chat.members_count
            
            return None
            
        except Exception as e:
            error_info = self.error_handler.handle_error(e, {
                'operation': 'get_channel_members_count',
                'channel_id': channel_id
            })
            logger.error(f"获取频道成员数量失败: {error_info}")
            return None
    
    async def _get_chat_info(self, chat_id: Union[int, str]) -> Optional[Chat]:
        """获取聊天信息"""
        try:
            async def get_chat():
                return await self.client.get_chat(chat_id)
            
            return await self.flood_wait_handler.execute_with_flood_wait(get_chat)
            
        except Exception as e:
            error_info = self.error_handler.handle_error(e, {
                'operation': 'get_chat_info',
                'chat_id': chat_id
            })
            logger.error(f"获取聊天信息失败: {error_info}")
            return None
    
    async def _get_chat_member(self, chat_id: Union[int, str], user_id: int) -> Optional[ChatMember]:
        """获取聊天成员信息"""
        try:
            async def get_member():
                return await self.client.get_chat_member(chat_id, user_id)
            
            return await self.flood_wait_handler.execute_with_flood_wait(get_member)
            
        except Exception as e:
            error_info = self.error_handler.handle_error(e, {
                'operation': 'get_chat_member',
                'chat_id': chat_id,
                'user_id': user_id
            })
            logger.error(f"获取聊天成员信息失败: {error_info}")
            return None
    
    def _extract_chat_info(self, chat: Chat) -> Dict[str, Any]:
        """提取聊天信息"""
        return {
            'id': chat.id,
            'type': chat.type.value,
            'title': chat.title,
            'username': chat.username,
            'first_name': chat.first_name,
            'last_name': chat.last_name,
            'members_count': chat.members_count,
            'description': chat.description,
            'is_verified': chat.is_verified,
            'is_restricted': chat.is_restricted,
            'is_scam': chat.is_scam,
            'is_fake': chat.is_fake
        }
    
    def _analyze_permissions(self, member: ChatMember) -> Dict[str, bool]:
        """分析成员权限"""
        permissions = {}
        
        if hasattr(member, 'privileges'):
            # 管理员权限
            privileges = member.privileges
            permissions.update({
                'can_manage_chat': privileges.can_manage_chat,
                'can_delete_messages': privileges.can_delete_messages,
                'can_manage_video_chats': privileges.can_manage_video_chats,
                'can_restrict_members': privileges.can_restrict_members,
                'can_promote_members': privileges.can_promote_members,
                'can_change_info': privileges.can_change_info,
                'can_invite_users': privileges.can_invite_users,
                'can_post_messages': privileges.can_post_messages,
                'can_edit_messages': privileges.can_edit_messages,
                'can_pin_messages': privileges.can_pin_messages,
                'can_post_stories': privileges.can_post_stories,
                'can_edit_stories': privileges.can_edit_stories,
                'can_delete_stories': privileges.can_delete_stories
            })
        
        # 基本权限
        permissions.update({
            'can_send_messages': getattr(member, 'can_send_messages', True),
            'can_send_media_messages': getattr(member, 'can_send_media_messages', True),
            'can_send_other_messages': getattr(member, 'can_send_other_messages', True),
            'can_add_web_page_previews': getattr(member, 'can_add_web_page_previews', True)
        })
        
        return permissions
    
    def _clean_channel_name(self, channel_name: str) -> str:
        """清理频道名称"""
        # 移除@符号
        if channel_name.startswith('@'):
            channel_name = channel_name[1:]
        
        # 移除https://t.me/前缀
        if channel_name.startswith('https://t.me/'):
            channel_name = channel_name[13:]
        
        # 移除http://t.me/前缀
        if channel_name.startswith('http://t.me/'):
            channel_name = channel_name[12:]
        
        return channel_name.strip()
    
    def _get_current_timestamp(self) -> float:
        """获取当前时间戳"""
        return time.time()
    
    def _is_cache_expired(self, cache_data: Dict[str, Any], ttl: int = 1800) -> bool:
        """检查缓存是否过期"""
        timestamp = cache_data.get('timestamp', 0)
        return (self._get_current_timestamp() - timestamp) > ttl
    
    def _add_to_channel_cache(self, cache_key: str, data: Dict[str, Any]) -> None:
        """添加到频道缓存"""
        if len(self.channel_cache) >= self.cache_size:
            # 删除最旧的条目
            oldest_key = next(iter(self.channel_cache))
            del self.channel_cache[oldest_key]
        
        self.channel_cache[cache_key] = data
    
    def _add_to_permission_cache(self, cache_key: str, data: Dict[str, Any]) -> None:
        """添加到权限缓存"""
        if len(self.permission_cache) >= self.cache_size:
            # 删除最旧的条目
            oldest_key = next(iter(self.permission_cache))
            del self.permission_cache[oldest_key]
        
        self.permission_cache[cache_key] = data
    
    def clear_cache(self) -> None:
        """清空缓存"""
        self.channel_cache.clear()
        self.permission_cache.clear()
        logger.info("频道验证器缓存已清空")
    
    def set_cache_enabled(self, enabled: bool) -> None:
        """设置缓存启用状态"""
        self.cache_enabled = enabled
        logger.info(f"频道验证器缓存已{'启用' if enabled else '禁用'}")
    
    def set_cache_size(self, size: int) -> None:
        """设置缓存大小"""
        self.cache_size = size
        logger.info(f"频道验证器缓存大小设置为: {size}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        return {
            'enabled': self.cache_enabled,
            'size': self.cache_size,
            'channel_cache_count': len(self.channel_cache),
            'permission_cache_count': len(self.permission_cache)
        } 