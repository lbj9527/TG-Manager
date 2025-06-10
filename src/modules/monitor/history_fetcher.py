"""
历史消息获取模块，负责获取频道的历史消息
"""

import asyncio
from typing import List

from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait

from src.utils.channel_resolver import ChannelResolver
from src.utils.logger import get_logger

logger = get_logger()

async def get_channel_history(client: Client, channel_resolver: ChannelResolver, channel: str, limit: int = 100, should_stop_flag: bool = False) -> List[Message]:
    """
    获取指定频道的历史消息
    
    Args:
        client: Pyrogram客户端实例
        channel_resolver: 频道解析器实例
        channel: 频道ID或用户名
        limit: 获取消息的数量限制
        should_stop_flag: 任务是否应该停止的标志
        
    Returns:
        获取到的消息列表
    """
    logger.info(f"正在获取频道 {channel} 的历史消息")
    
    try:
        channel_id, _ = await channel_resolver.resolve_channel(channel)
        if not channel_id:
            logger.error(f"无法解析频道: {channel}", error_type="CHANNEL_RESOLVE", recoverable=False)
            return []
            
        channel_info_str, _ = await channel_resolver.format_channel_info(channel_id)
        logger.info(f"获取 {channel_info_str} 的历史消息，限制 {limit} 条")
        
        messages = []
        async for message in client.get_chat_history(channel_id, limit=limit):
            if should_stop_flag:
                logger.warning("历史消息获取任务已取消")
                break
                
            messages.append(message)
            
            # 每20条消息记录日志
            if len(messages) % 20 == 0:
                logger.debug(f"已获取 {len(messages)} 条消息")
                
        logger.info(f"完成获取 {channel_info_str} 的历史消息，共 {len(messages)} 条")
        return messages
        
    except FloodWait as e:
        logger.warning(f"获取历史消息时遇到限制，需要等待 {e.x} 秒")
        await asyncio.sleep(e.x)
        # 递归重试
        return await get_channel_history(client, channel_resolver, channel, limit, should_stop_flag)
        
    except Exception as e:
        logger.error(f"获取历史消息失败: {str(e)}", error_type="GET_HISTORY", recoverable=True)
        return [] 