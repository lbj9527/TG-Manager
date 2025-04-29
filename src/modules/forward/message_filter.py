"""
消息过滤器，用于过滤符合条件的消息
"""

from typing import List, Dict, Any

from pyrogram.types import Message

from src.utils.logger import get_logger

_logger = get_logger()

class MessageFilter:
    """
    消息过滤器，用于过滤特定类型的消息
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化消息过滤器
        
        Args:
            config: 配置信息，包含过滤规则
        """
        self.config = config or {}
    
    def is_media_allowed(self, message: Message, source_channel: str = None) -> bool:
        """
        检查消息媒体类型是否在允许列表中
        
        Args:
            message: 消息对象
            source_channel: 源频道
            
        Returns:
            bool: 是否允许
        """
        forward_config = self.config.get('FORWARD', {})
        
        # 如果没有指定源频道，使用公共设置
        if not source_channel:
            media_types = forward_config.get('media_types', [])
        else:
            # 查找对应的频道对配置
            channel_pairs = forward_config.get('forward_channel_pairs', [])
            media_types = []
            
            # 查找匹配的频道对
            for pair in channel_pairs:
                if pair.get('source_channel') == source_channel and 'media_types' in pair:
                    media_types = pair['media_types']
                    break
            
            # 如果找不到对应的配置，使用默认值
            if not media_types:
                # 使用所有支持的媒体类型作为默认值
                media_types = ["photo", "video", "document", "audio", "animation"]
                _logger.warning(f"找不到源频道 {source_channel} 的媒体类型配置，使用默认值")
        
        # 确保媒体类型是字符串列表
        media_types_str = [str(t) for t in media_types]
        
        if message.photo and "photo" in media_types_str:
            return True
        elif message.video and "video" in media_types_str:
            return True
        elif message.document and "document" in media_types_str:
            return True
        elif message.audio and "audio" in media_types_str:
            return True
        elif message.animation and "animation" in media_types_str:
            return True
        elif (message.text or message.caption) and "text" in media_types_str:
            return True
        
        return False 