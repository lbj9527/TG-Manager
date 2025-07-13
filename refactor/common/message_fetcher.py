"""
统一消息获取器

提供统一的消息获取接口，支持批量获取、范围获取、搜索等功能。
"""

import asyncio
from typing import Any, Dict, List, Optional, Union
from loguru import logger

from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait, ChannelPrivate, ChatAdminRequired

from common.flood_wait_handler import FloodWaitHandler
from common.error_handler import ErrorHandler, ErrorType


class MessageFetcher:
    """统一消息获取器"""
    
    def __init__(self, client: Client):
        self.client = client
        self.flood_wait_handler = FloodWaitHandler()
        self.error_handler = ErrorHandler()
        
        # 缓存配置
        self.cache_enabled = True
        self.cache_size = 1000
        self.message_cache: Dict[str, Message] = {}
    
    def set_event_bus(self, event_bus) -> None:
        """设置事件总线"""
        self.event_bus = event_bus
        self.flood_wait_handler.set_event_bus(event_bus)
        self.error_handler.set_event_bus(event_bus)
    
    async def get_messages(self, chat_id: Union[int, str], message_ids: List[int]) -> List[Optional[Message]]:
        """
        获取指定消息ID列表的消息
        
        Args:
            chat_id: 聊天ID
            message_ids: 消息ID列表
            
        Returns:
            消息列表，如果某个消息获取失败则为None
        """
        try:
            logger.info(f"获取消息: 聊天ID {chat_id}, 消息数量 {len(message_ids)}")
            
            messages = []
            for message_id in message_ids:
                try:
                    message = await self._get_single_message_with_cache(chat_id, message_id)
                    messages.append(message)
                except Exception as e:
                    error_info = self.error_handler.handle_error(e, {
                        'operation': 'get_single_message',
                        'chat_id': chat_id,
                        'message_id': message_id
                    })
                    logger.error(f"获取消息 {message_id} 失败: {error_info}")
                    messages.append(None)
            
            logger.info(f"消息获取完成: 成功 {len([m for m in messages if m])}/{len(message_ids)}")
            return messages
            
        except Exception as e:
            error_info = self.error_handler.handle_error(e, {
                'operation': 'get_messages',
                'chat_id': chat_id,
                'message_ids': message_ids
            })
            logger.error(f"批量获取消息失败: {error_info}")
            return [None] * len(message_ids)
    
    async def get_chat_history(self, chat_id: Union[int, str], limit: int = 100, 
                              offset_id: int = 0) -> List[Message]:
        """
        获取聊天历史消息
        
        Args:
            chat_id: 聊天ID
            limit: 获取数量限制
            offset_id: 偏移消息ID
            
        Returns:
            消息列表
        """
        try:
            logger.info(f"获取聊天历史: 聊天ID {chat_id}, 限制 {limit}, 偏移 {offset_id}")
            
            messages = []
            async for message in self.client.get_chat_history(
                chat_id, limit=limit, offset_id=offset_id
            ):
                messages.append(message)
                if len(messages) >= limit:
                    break
            
            logger.info(f"聊天历史获取完成: {len(messages)} 条消息")
            return messages
            
        except Exception as e:
            error_info = self.error_handler.handle_error(e, {
                'operation': 'get_chat_history',
                'chat_id': chat_id,
                'limit': limit,
                'offset_id': offset_id
            })
            logger.error(f"获取聊天历史失败: {error_info}")
            return []
    
    async def get_messages_in_range(self, chat_id: Union[int, str], start_id: int, 
                                   end_id: int, limit: Optional[int] = None) -> List[Message]:
        """
        获取指定ID范围内的消息
        
        Args:
            chat_id: 聊天ID
            start_id: 起始消息ID
            end_id: 结束消息ID
            limit: 数量限制（可选）
            
        Returns:
            消息列表
        """
        try:
            logger.info(f"获取消息范围: 聊天ID {chat_id}, 范围 {start_id}-{end_id}")
            
            messages = []
            current_limit = limit or (end_id - start_id + 1)
            
            async for message in self.client.get_chat_history(
                chat_id, limit=current_limit, offset_id=end_id
            ):
                if message.id < start_id:
                    break
                if message.id <= end_id:
                    messages.append(message)
                if len(messages) >= current_limit:
                    break
            
            # 按消息ID排序
            messages.sort(key=lambda m: m.id)
            
            logger.info(f"消息范围获取完成: {len(messages)} 条消息")
            return messages
            
        except Exception as e:
            error_info = self.error_handler.handle_error(e, {
                'operation': 'get_messages_in_range',
                'chat_id': chat_id,
                'start_id': start_id,
                'end_id': end_id,
                'limit': limit
            })
            logger.error(f"获取消息范围失败: {error_info}")
            return []
    
    async def search_messages(self, chat_id: Union[int, str], query: str, 
                             limit: int = 100) -> List[Message]:
        """
        搜索消息
        
        Args:
            chat_id: 聊天ID
            query: 搜索查询
            limit: 数量限制
            
        Returns:
            匹配的消息列表
        """
        try:
            logger.info(f"搜索消息: 聊天ID {chat_id}, 查询 '{query}', 限制 {limit}")
            
            messages = []
            async for message in self.client.search_messages(
                chat_id, query=query, limit=limit
            ):
                messages.append(message)
                if len(messages) >= limit:
                    break
            
            logger.info(f"消息搜索完成: {len(messages)} 条匹配消息")
            return messages
            
        except Exception as e:
            error_info = self.error_handler.handle_error(e, {
                'operation': 'search_messages',
                'chat_id': chat_id,
                'query': query,
                'limit': limit
            })
            logger.error(f"搜索消息失败: {error_info}")
            return []
    
    async def get_media_messages(self, chat_id: Union[int, str], limit: int = 100,
                                media_types: Optional[List[str]] = None) -> List[Message]:
        """
        获取媒体消息
        
        Args:
            chat_id: 聊天ID
            limit: 数量限制
            media_types: 媒体类型列表（可选）
            
        Returns:
            媒体消息列表
        """
        try:
            logger.info(f"获取媒体消息: 聊天ID {chat_id}, 限制 {limit}")
            
            messages = []
            async for message in self.client.get_chat_history(chat_id, limit=limit * 2):
                if message.media:
                    media_type = self._get_media_type(message)
                    if not media_types or media_type in media_types:
                        messages.append(message)
                        if len(messages) >= limit:
                            break
            
            logger.info(f"媒体消息获取完成: {len(messages)} 条消息")
            return messages
            
        except Exception as e:
            error_info = self.error_handler.handle_error(e, {
                'operation': 'get_media_messages',
                'chat_id': chat_id,
                'limit': limit,
                'media_types': media_types
            })
            logger.error(f"获取媒体消息失败: {error_info}")
            return []
    
    async def get_message_count(self, chat_id: Union[int, str]) -> int:
        """
        获取聊天消息总数
        
        Args:
            chat_id: 聊天ID
            
        Returns:
            消息总数
        """
        try:
            logger.info(f"获取消息总数: 聊天ID {chat_id}")
            
            # 使用get_chat_history获取最新消息的ID作为估算
            count = 0
            async for message in self.client.get_chat_history(chat_id, limit=1):
                count = message.id
                break
            
            logger.info(f"消息总数估算: {count}")
            return count
            
        except Exception as e:
            error_info = self.error_handler.handle_error(e, {
                'operation': 'get_message_count',
                'chat_id': chat_id
            })
            logger.error(f"获取消息总数失败: {error_info}")
            return 0
    
    async def _get_single_message_with_cache(self, chat_id: Union[int, str], 
                                           message_id: int) -> Optional[Message]:
        """获取单条消息（带缓存）"""
        if not self.cache_enabled:
            return await self._get_single_message(chat_id, message_id)
        
        # 生成缓存键
        cache_key = f"{chat_id}_{message_id}"
        
        # 检查缓存
        if cache_key in self.message_cache:
            logger.debug(f"从缓存获取消息: {cache_key}")
            return self.message_cache[cache_key]
        
        # 获取消息
        message = await self._get_single_message(chat_id, message_id)
        
        # 添加到缓存
        if message:
            self._add_to_cache(cache_key, message)
        
        return message
    
    async def _get_single_message(self, chat_id: Union[int, str], 
                                message_id: int) -> Optional[Message]:
        """获取单条消息"""
        try:
            async def get_message():
                return await self.client.get_messages(chat_id, message_id)
            
            return await self.flood_wait_handler.execute_with_flood_wait(get_message)
            
        except Exception as e:
            error_info = self.error_handler.handle_error(e, {
                'operation': 'get_single_message',
                'chat_id': chat_id,
                'message_id': message_id
            })
            logger.error(f"获取单条消息失败: {error_info}")
            return None
    
    def _get_media_type(self, message: Message) -> str:
        """获取消息的媒体类型"""
        if not message.media:
            return "text"
        
        media_type_map = {
            'photo': 'photo',
            'video': 'video',
            'document': 'document',
            'audio': 'audio',
            'animation': 'animation',
            'sticker': 'sticker',
            'voice': 'voice',
            'video_note': 'video_note'
        }
        
        return media_type_map.get(message.media.value, 'unknown')
    
    def _add_to_cache(self, cache_key: str, message: Message) -> None:
        """添加到缓存"""
        if len(self.message_cache) >= self.cache_size:
            # 删除最旧的条目
            oldest_key = next(iter(self.message_cache))
            del self.message_cache[oldest_key]
        
        self.message_cache[cache_key] = message
    
    def clear_cache(self) -> None:
        """清空缓存"""
        self.message_cache.clear()
        logger.info("消息缓存已清空")
    
    def set_cache_enabled(self, enabled: bool) -> None:
        """设置缓存启用状态"""
        self.cache_enabled = enabled
        logger.info(f"消息缓存已{'启用' if enabled else '禁用'}")
    
    def set_cache_size(self, size: int) -> None:
        """设置缓存大小"""
        self.cache_size = size
        logger.info(f"消息缓存大小设置为: {size}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        return {
            'enabled': self.cache_enabled,
            'size': self.cache_size,
            'current_count': len(self.message_cache),
            'hit_rate': 0.0  # TODO: 实现命中率统计
        } 