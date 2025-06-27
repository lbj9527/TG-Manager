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
    
    def _filter_unforwarded_ids(self, start_id: int, end_id: int, source_channel: str, target_channels: List[str], history_manager) -> List[int]:
        """
        根据转发历史预过滤未转发的消息ID
        
        Args:
            start_id: 起始消息ID
            end_id: 结束消息ID
            source_channel: 源频道标识
            target_channels: 目标频道列表
            history_manager: 历史管理器实例
            
        Returns:
            List[int]: 未转发到任何目标频道的消息ID列表
        """
        if not history_manager:
            # 如果没有历史管理器，返回全部ID
            return list(range(start_id, end_id + 1))
        
        unforwarded_ids = []
        total_ids = end_id - start_id + 1
        
        _logger.info(f"开始预过滤已转发的消息ID，范围: {start_id}-{end_id} (共{total_ids}个ID)")
        
        # 遍历ID范围，检查每个ID是否已转发到所有目标频道
        for msg_id in range(start_id, end_id + 1):
            is_fully_forwarded = True
            
            # 检查是否已转发到所有目标频道
            for target_channel in target_channels:
                if not history_manager.is_message_forwarded(source_channel, msg_id, target_channel):
                    is_fully_forwarded = False
                    break
            
            # 如果没有完全转发，则添加到未转发列表
            if not is_fully_forwarded:
                unforwarded_ids.append(msg_id)
        
        filtered_count = total_ids - len(unforwarded_ids)
        _logger.info(f"预过滤完成: 总消息 {total_ids} 个, 已转发 {filtered_count} 个, 需要获取 {len(unforwarded_ids)} 个")
        
        return unforwarded_ids

    async def _resolve_message_range(self, source_id: int, pair: dict) -> tuple[int, int, bool]:
        """
        解析和验证消息ID范围，处理end_id=0的情况
        
        Args:
            source_id: 源频道ID
            pair: 频道对配置，包含start_id和end_id
            
        Returns:
            tuple: (start_id, end_id, is_valid) - 解析后的范围和是否有效
        """
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
        
        # 如果没有设置范围，使用原有逻辑
        if start_id == 0 and end_id == 0:
            _logger.info("未设置消息ID范围，使用原有的完整获取逻辑")
            return start_id, end_id, False
        
        # 如果end_id为0，表示获取到最新消息，需要先获取实际的最新消息ID
        if end_id == 0:
            try:
                # 获取频道最新消息来确定消息ID上限
                async for message in self.message_iterator.client.get_chat_history(source_id, limit=1):
                    end_id = message.id
                    _logger.info(f"end_id=0，自动获取频道最新消息ID: {end_id}")
                    break
                else:
                    _logger.warning(f"无法获取频道 {source_id} 的最新消息，跳过优化处理")
                    return start_id, end_id, False
            except Exception as e:
                _logger.error(f"获取频道 {source_id} 最新消息ID失败: {e}，跳过优化处理")
                return start_id, end_id, False
        
        # 确保起始ID合理
        if start_id <= 0:
            start_id = 1
        
        # 确保范围合理
        if start_id > end_id:
            _logger.warning(f"起始ID {start_id} 大于结束ID {end_id}，跳过优化处理")
            return start_id, end_id, False
        
        return start_id, end_id, True

    async def get_media_groups_optimized(self, source_id: int, source_channel: str, target_channels: List[str], pair: dict = None, history_manager=None) -> Tuple[Dict[str, List[Message]], Dict[str, str]]:
        """
        优化的获取源频道媒体组方法，先过滤已转发的消息ID再获取消息
        
        Args:
            source_id: 源频道ID
            source_channel: 源频道标识
            target_channels: 目标频道列表，用于检查转发历史
            pair: 频道对配置，包含start_id和end_id
            history_manager: 历史管理器实例
            
        Returns:
            Tuple[Dict[str, List[Message]], Dict[str, str]]: (媒体组ID与消息列表的映射, 媒体组文本映射)
        """
        media_groups: Dict[str, List[Message]] = {}
        media_group_texts: Dict[str, str] = {}
        
        # 解析消息范围
        start_id, end_id, is_valid = await self._resolve_message_range(source_id, pair)
        
        # 如果范围无效，回退到原有逻辑
        if not is_valid:
            fallback_groups = await self.get_media_groups(source_id, source_channel, pair)
            return fallback_groups, {}
        
        # 预过滤已转发的消息ID
        unforwarded_ids = self._filter_unforwarded_ids(start_id, end_id, source_channel, target_channels, history_manager)
        
        # 如果没有未转发的消息，直接返回空结果
        if not unforwarded_ids:
            _logger.info("所有消息都已转发，无需获取新消息")
            return media_groups, media_group_texts
        
        # 按指定ID列表获取消息
        all_messages = []
        async for message in self.message_iterator.iter_messages_by_ids(source_id, unforwarded_ids):
            all_messages.append(message)
        
        # 应用过滤规则（使用新的统一过滤器）
        if pair and all_messages:
            filtered_messages, _, filter_stats = self.message_filter.apply_all_filters(all_messages, pair)
            # 获取媒体组文本映射
            media_group_texts = filter_stats.get('media_group_texts', {})
            _logger.info(f"过滤完成: 原始消息 {len(all_messages)} 条，通过过滤 {len(filtered_messages)} 条")
            if media_group_texts:
                _logger.debug(f"🔍 MediaGroupCollector获取到媒体组文本: {len(media_group_texts)} 个")
        else:
            filtered_messages = all_messages
        
        # 将过滤后的消息按媒体组分组
        for message in filtered_messages:
            # 获取媒体组ID
            group_id = str(message.media_group_id) if message.media_group_id else f"single_{message.id}"
            
            # 添加到媒体组
            if group_id not in media_groups:
                media_groups[group_id] = []
            
            media_groups[group_id].append(message)
        
        # 按消息ID排序每个媒体组内的消息
        for group_id in media_groups:
            media_groups[group_id].sort(key=lambda x: x.id)
        
        _logger.info(f"优化获取完成: 获得 {len(media_groups)} 个媒体组")
        return media_groups, media_group_texts

    async def get_media_groups_info_optimized(self, source_id: int, source_channel: str, target_channels: List[str], pair: dict = None, history_manager=None) -> List[Tuple[str, List[int]]]:
        """
        优化的获取源频道媒体组基本信息方法，先过滤已转发的消息ID再获取消息
        
        Args:
            source_id: 源频道ID
            source_channel: 源频道标识
            target_channels: 目标频道列表，用于检查转发历史
            pair: 频道对配置，包含start_id和end_id
            history_manager: 历史管理器实例
            
        Returns:
            List[Tuple[str, List[int]]]: 媒体组ID与消息ID列表的映射
        """
        media_groups_info = []
        media_groups: Dict[str, List[int]] = {}
        
        # 解析消息范围
        start_id, end_id, is_valid = await self._resolve_message_range(source_id, pair)
        
        # 如果范围无效，回退到原有逻辑
        if not is_valid:
            return await self.get_media_groups_info(source_id, pair)
        
        # 预过滤已转发的消息ID
        unforwarded_ids = self._filter_unforwarded_ids(start_id, end_id, source_channel, target_channels, history_manager)
        
        # 如果没有未转发的消息，直接返回空结果
        if not unforwarded_ids:
            _logger.info("所有消息都已转发，无需获取新消息")
            return media_groups_info
        
        # 按指定ID列表获取消息
        all_messages = []
        async for message in self.message_iterator.iter_messages_by_ids(source_id, unforwarded_ids):
            all_messages.append(message)
        
        # 应用过滤规则（使用新的统一过滤器）
        if pair and all_messages:
            filtered_messages, _, filter_stats = self.message_filter.apply_all_filters(all_messages, pair)
            _logger.info(f"过滤完成: 原始消息 {len(all_messages)} 条，通过过滤 {len(filtered_messages)} 条")
        else:
            filtered_messages = all_messages
        
        # 将过滤后的消息按媒体组分组（只保存ID）
        for message in filtered_messages:
            # 获取媒体组ID
            group_id = str(message.media_group_id) if message.media_group_id else f"single_{message.id}"
            
            # 添加到媒体组
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
        
        _logger.info(f"优化获取媒体组信息完成: 获得 {len(media_groups_info)} 个媒体组")
        return media_groups_info

    async def get_media_groups(self, source_id: int, source_channel: str, pair: dict = None) -> Dict[str, List[Message]]:
        """
        获取源频道的媒体组消息
        
        Args:
            source_id: 源频道ID
            source_channel: 源频道标识
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
        
        _logger.info(f"开始获取媒体组消息，范围: start_id={start_id}, end_id={end_id}")
        
        # 收集所有消息
        all_messages = []
        async for message in self.message_iterator.iter_messages(source_id, start_id, end_id):
            all_messages.append(message)
        
        _logger.info(f"获取到原始消息 {len(all_messages)} 条")
        
        # 应用过滤规则（使用新的统一过滤器）
        if pair and all_messages:
            filtered_messages, _, filter_stats = self.message_filter.apply_all_filters(all_messages, pair)
            _logger.info(f"过滤完成: 原始消息 {len(all_messages)} 条，通过过滤 {len(filtered_messages)} 条")
        else:
            filtered_messages = all_messages
        
        # 将过滤后的消息按媒体组分组
        for message in filtered_messages:
            # 获取媒体组ID
            group_id = str(message.media_group_id) if message.media_group_id else f"single_{message.id}"
            
            # 添加到媒体组
            if group_id not in media_groups:
                media_groups[group_id] = []
            
            media_groups[group_id].append(message)
        
        # 按消息ID排序每个媒体组内的消息
        for group_id in media_groups:
            media_groups[group_id].sort(key=lambda x: x.id)
        
        _logger.info(f"获取完成: 共 {len(media_groups)} 个媒体组")
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
            
        _logger.info(f"开始获取媒体组信息，范围: start_id={start_id}, end_id={end_id}")
        
        # 收集所有消息
        all_messages = []
        async for message in self.message_iterator.iter_messages(source_id, start_id, end_id):
            all_messages.append(message)
        
        _logger.info(f"获取到原始消息 {len(all_messages)} 条")
        
        # 应用过滤规则（使用新的统一过滤器）
        if pair and all_messages:
            filtered_messages, _, filter_stats = self.message_filter.apply_all_filters(all_messages, pair)
            _logger.info(f"过滤完成: 原始消息 {len(all_messages)} 条，通过过滤 {len(filtered_messages)} 条")
        else:
            filtered_messages = all_messages
        
        # 将过滤后的消息按媒体组分组（只保存ID）
        for message in filtered_messages:
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
        
        _logger.info(f"获取媒体组信息完成: 找到 {len(media_groups_info)} 个媒体组")
        return media_groups_info 