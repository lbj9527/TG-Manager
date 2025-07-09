"""
文本处理工具模块，提供通用的文本处理功能
"""

import re
from typing import Optional, List
from pyrogram.types import MessageEntity

from src.utils.logger import get_logger

logger = get_logger()

def contains_links(text: str, entities: Optional[List[MessageEntity]] = None) -> bool:
    """
    检查文本中是否包含链接
    
    Args:
        text: 要检查的文本
        entities: Telegram消息实体列表（用于检测隐式链接）
        
    Returns:
        bool: 是否包含链接
    """
    if not text:
        return False
    
    # 1. 检查Telegram消息实体中的链接（优先级最高，能检测隐式链接）
    if entities:
        for entity in entities:
            # 获取实体类型，处理pyrogram的MessageEntityType枚举
            entity_type = None
            if hasattr(entity, 'type'):
                raw_type = entity.type
                
                # 处理pyrogram的MessageEntityType枚举
                if hasattr(raw_type, 'name'):
                    # 这是一个枚举，获取名称并转为小写
                    entity_type = raw_type.name.lower()
                elif hasattr(raw_type, 'value'):
                    # 这是一个枚举，获取值
                    entity_type = str(raw_type.value).lower()
                else:
                    # 直接转换为字符串
                    entity_type = str(raw_type).lower()
            
            # 检查是否为链接相关的实体类型
            link_types = ['url', 'text_link', 'email', 'phone_number']
            if entity_type and entity_type in link_types:
                logger.debug(f"发现链接实体: {entity_type}")
                return True
    
    # 2. 检查显式链接模式（作为备用检测）
    url_patterns = [
        r'https?://[^\s]+',  # http或https链接
        r'www\.[^\s]+',      # www链接
        r't\.me/[^\s]+',     # Telegram链接
        r'[^\s]+\.[a-z]{2,}[^\s]*',  # 一般域名
        r'@\w+',             # @用户名
    ]
    
    for pattern in url_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            logger.debug(f"发现显式链接模式: {pattern}")
            return True
    
    return False

def extract_text_from_message(message) -> str:
    """
    从消息中提取文本内容
    
    Args:
        message: 消息对象
        
    Returns:
        str: 提取的文本内容
    """
    if not message:
        return ""
    
    # 优先使用caption，其次使用text
    if hasattr(message, 'caption') and message.caption:
        return message.caption
    elif hasattr(message, 'text') and message.text:
        return message.text
    
    return ""

def is_media_message(message) -> bool:
    """
    检查消息是否为媒体消息
    
    Args:
        message: 消息对象
        
    Returns:
        bool: 是否为媒体消息
    """
    if not message:
        return False
    
    return bool(
        message.photo or message.video or message.document or 
        message.animation or message.audio or message.voice or 
        message.video_note or message.sticker
    ) 

def is_media_type_allowed(message_media_type, allowed_media_types) -> bool:
    """
    检查消息的媒体类型是否在允许列表中
    Args:
        message_media_type: 消息的媒体类型（可为枚举或字符串）
        allowed_media_types: 允许的媒体类型列表（可为枚举或字符串）
    Returns:
        bool: 是否允许该媒体类型
    """
    if not allowed_media_types:
        return True
    for allowed_type in allowed_media_types:
        allowed_value = allowed_type.value if hasattr(allowed_type, 'value') else allowed_type
        message_value = message_media_type.value if hasattr(message_media_type, 'value') else message_media_type
        if allowed_value == message_value:
            return True
    return False 