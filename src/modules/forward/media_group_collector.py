"""
媒体组收集器，用于收集媒体组消息
"""

from typing import Dict, List, Optional, Tuple, Set, Any

from pyrogram.types import Message

from src.modules.forward.message_iterator import MessageIterator
from src.modules.forward.message_filter import MessageFilter
from src.utils.logger import get_logger

_logger = get_logger()

class MediaGroupCollector:
    """
    媒体组收集器，用于从频道获取媒体组消息
    """
    
    def __init__(self, message_iterator: MessageIterator, message_filter: MessageFilter):
        """
        初始化媒体组收集器
        
        Args:
            message_iterator: 消息迭代器实例
            message_filter: 消息过滤器实例
        """
        self.message_iterator = message_iterator
        self.message_filter = message_filter
    
    async def get_media_groups(self, source_id: int, source_channel: str, pair: dict = None) -> Dict[str, List[Message]]:
        """
        获取源频道的媒体组消息
        
        Args:
            source_id: 源频道ID
            source_channel: 源频道
            pair: 频道对配置，包含start_id和end_id
            
        Returns:
            Dict[str, List[Message]]: 媒体组ID与消息列表的映射
        """
        media_groups: Dict[str, List[Message]] = {}
        
        # 确保pair是有效的字典
        if pair is None:
            pair = {}
        
        # 设置消息范围
        try:
            start_id = int(pair.get('start_id', 0) or 0)
        except (ValueError, TypeError):
            _logger.warning(f"无效的start_id值 '{pair.get('start_id')}', 将使用默认值0")
            start_id = 0
            
        try:
            end_id = int(pair.get('end_id', 0) or 0)
        except (ValueError, TypeError):
            _logger.warning(f"无效的end_id值 '{pair.get('end_id')}', 将使用默认值0")
            end_id = 0
        
        # 获取消息
        async for message in self.message_iterator.iter_messages(source_id, start_id, end_id):
            # 筛选媒体类型
            if not self.message_filter.is_media_allowed(message, source_channel):
                continue
            
            # 获取媒体组ID
            group_id = str(message.media_group_id) if message.media_group_id else f"single_{message.id}"
            
            # 添加到媒体组
            if group_id not in media_groups:
                media_groups[group_id] = []
            
            media_groups[group_id].append(message)
        
        # 按消息ID排序每个媒体组内的消息
        for group_id in media_groups:
            media_groups[group_id].sort(key=lambda x: x.id)
        
        return media_groups
    
    async def get_media_groups_info(self, source_id: int, pair: dict = None) -> List[Tuple[str, List[int]]]:
        """
        获取源频道的媒体组基本信息（不下载内容）
        
        Args:
            source_id: 源频道ID
            pair: 频道对配置，包含start_id和end_id和source_channel
            
        Returns:
            List[Tuple[str, List[int]]]: 媒体组ID与消息ID列表的映射
        """
        media_groups_info = []
        media_groups: Dict[str, List[int]] = {}
        
        # 确保pair是有效的字典
        if pair is None:
            pair = {}
        
        # 设置消息范围
        try:
            start_id = int(pair.get('start_id', 0) or 0)
        except (ValueError, TypeError):
            _logger.warning(f"无效的start_id值 '{pair.get('start_id')}', 将使用默认值0")
            start_id = 0
            
        try:
            end_id = int(pair.get('end_id', 0) or 0)
        except (ValueError, TypeError):
            _logger.warning(f"无效的end_id值 '{pair.get('end_id')}', 将使用默认值0")
            end_id = 0
            
        # 获取源频道标识符，用于传递给消息过滤器
        source_channel = pair.get('source_channel')
        
        # 获取消息基本信息
        async for message in self.message_iterator.iter_messages(source_id, start_id, end_id):
            # 筛选媒体类型，传入源频道信息
            if not self.message_filter.is_media_allowed(message, source_channel):
                continue
            
            # 获取媒体组ID
            group_id = str(message.media_group_id) if message.media_group_id else f"single_{message.id}"
            
            # 添加到媒体组信息
            if group_id not in media_groups:
                media_groups[group_id] = []
            
            media_groups[group_id].append(message.id)
        
        # 转换为列表格式，便于顺序处理
        for group_id, message_ids in media_groups.items():
            # 按消息ID排序
            message_ids.sort()
            media_groups_info.append((group_id, message_ids))
        
        # 按第一个消息ID排序，确保从旧到新处理
        media_groups_info.sort(key=lambda x: x[1][0] if x[1] else 0)
        
        # 添加更详细的日志输出
        _logger.info(f"找到 {len(media_groups_info)} 个媒体组")
        for i, (group_id, message_ids) in enumerate(media_groups_info[:10]):  # 只记录前10个，避免日志过长
            _logger.info(f"媒体组 {i+1}/{len(media_groups_info)}: group_id={group_id}, 消息IDs={message_ids}")
        
        if len(media_groups_info) > 10:
            _logger.info(f"还有 {len(media_groups_info) - 10} 个媒体组未显示")
        
        return media_groups_info 