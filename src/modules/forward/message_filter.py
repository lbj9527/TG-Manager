"""
消息过滤器，用于过滤符合条件的消息
提供统一的文本替换、关键词过滤、媒体类型过滤功能
"""

from typing import List, Dict, Any, Tuple, Optional
import re
import logging

from pyrogram.types import Message

from src.utils.logger import get_logger
from src.utils.translation_manager import tr

_logger = logging.getLogger(__name__)

class MessageFilter:
    """
    统一的消息过滤器，用于过滤特定类型的消息
    支持文本替换、关键词过滤、媒体类型过滤等功能
    """
    
    def __init__(self, config: Dict[str, Any] = None, emit=None):
        """
        初始化消息过滤器
        
        Args:
            config: 配置信息，包含过滤规则
            emit: 事件发射函数，用于发送过滤事件到UI
        """
        self.config = config or {}
        self.emit = emit  # 添加事件发射器
    
    def apply_keyword_filter(self, messages: List[Message], keywords: List[str]) -> Tuple[List[Message], List[Message]]:
        """
        应用关键词过滤，支持媒体组级别的过滤
        媒体组中任何一条消息包含关键词，则整个媒体组都通过过滤
        
        Args:
            messages: 消息列表
            keywords: 关键词列表
            
        Returns:
            Tuple[List[Message], List[Message]]: (通过的消息, 被过滤的消息)
        """
        if not keywords:
            return messages, []
        
        # 首先按媒体组分组
        media_groups = self._group_messages_by_media_group(messages)
        
        passed_messages = []
        filtered_messages = []
        
        # 用于统计
        passed_groups = []
        filtered_groups = []
        
        for group_messages in media_groups:
            # 检查媒体组中是否有任何消息包含关键词
            group_has_keyword = False
            keywords_found_in_group = []
            
            for message in group_messages:
                # 获取要检查的文本内容
                text_content = ""
                if message.caption:
                    text_content = message.caption
                elif message.text:
                    text_content = message.text
                
                if text_content:
                    # 检查是否包含任何关键词（不区分大小写）
                    for keyword in keywords:
                        if keyword.lower() in text_content.lower():
                            group_has_keyword = True
                            if keyword not in keywords_found_in_group:
                                keywords_found_in_group.append(keyword)
            
            # 获取媒体组ID用于日志
            group_ids = [msg.id for msg in group_messages]
            
            if group_has_keyword:
                # 整个媒体组通过过滤
                passed_messages.extend(group_messages)
                passed_groups.append(group_ids)
                _logger.debug(f"媒体组 [ID: {group_ids}] 包含关键词 {keywords_found_in_group}，整个媒体组通过过滤")
            else:
                # 整个媒体组被过滤
                filtered_messages.extend(group_messages)
                filtered_groups.append(group_ids)
        
        # 汇总日志显示
        if filtered_groups:
            filtered_count = sum(len(group) for group in filtered_groups)
            group_count = len(filtered_groups)
            sample_groups = filtered_groups[:3]  # 显示前3个媒体组
            group_display = []
            for group in sample_groups:
                if len(group) == 1:
                    group_display.append(str(group[0]))
                else:
                    group_display.append(f"[{','.join(map(str, group))}]")
            
            more_indicator = f", +{group_count - 3}个媒体组" if group_count > 3 else ""
            _logger.info(f"关键词过滤: {group_count} 个媒体组({filtered_count} 条消息)不包含关键词 {keywords} 被过滤 (组ID: {', '.join(group_display)}{more_indicator})")
        
        if passed_groups:
            passed_count = sum(len(group) for group in passed_groups)
            group_count = len(passed_groups)
            sample_groups = passed_groups[:3]  # 显示前3个媒体组
            group_display = []
            for group in sample_groups:
                if len(group) == 1:
                    group_display.append(str(group[0]))
                else:
                    group_display.append(f"[{','.join(map(str, group))}]")
            
            more_indicator = f", +{group_count - 3}个媒体组" if group_count > 3 else ""
            _logger.info(f"关键词过滤: {group_count} 个媒体组({passed_count} 条消息)包含关键词通过过滤 (组ID: {', '.join(group_display)}{more_indicator})")
        
        return passed_messages, filtered_messages
    
    def apply_media_type_filter(self, messages: List[Message], allowed_media_types: List[str]) -> Tuple[List[Message], List[Message]]:
        """
        应用媒体类型过滤，支持消息级别的精确过滤
        
        Args:
            messages: 消息列表
            allowed_media_types: 允许的媒体类型列表
            
        Returns:
            Tuple[List[Message], List[Message]]: (通过的消息, 被过滤的消息)
        """
        if not allowed_media_types:
            return messages, []
        
        # 按媒体组分组
        media_groups = self._group_messages_by_media_group(messages)
        
        passed_messages = []
        filtered_messages = []
        
        for group_messages in media_groups:
            group_passed = []
            group_filtered = []
            
            # 对媒体组中的每条消息单独进行媒体类型检查
            for message in group_messages:
                message_media_type = self._get_message_media_type(message)
                
                if message_media_type and self._is_media_type_allowed(message_media_type, allowed_media_types):
                    group_passed.append(message)
                else:
                    group_filtered.append(message)
                    # 根据媒体类型是否为None提供不同的日志信息
                    if message_media_type is None:
                        _logger.debug(f"消息 [ID: {message.id}] 无法识别媒体类型（可能是空消息、特殊消息类型），被过滤")
                        # 发射过滤事件到UI
                        if self.emit:
                            self.emit("message_filtered", message.id, tr("ui.forward.log.single_message"), tr("ui.forward.log.unrecognized_media_type"))
                    else:
                        _logger.debug(f"消息 [ID: {message.id}] 媒体类型 '{message_media_type}' 不在允许列表中，被过滤")
                        # 发射过滤事件到UI
                        if self.emit:
                            self.emit("message_filtered", message.id, tr("ui.forward.log.single_message"), tr("ui.forward.log.media_type_not_allowed", media_type=message_media_type))
            
            # 添加通过和被过滤的消息
            passed_messages.extend(group_passed)
            filtered_messages.extend(group_filtered)
            
            # 日志记录
            if group_passed and group_filtered:
                passed_ids = [msg.id for msg in group_passed]
                filtered_ids = [msg.id for msg in group_filtered]
                _logger.info(f"媒体组部分过滤: 通过消息 {passed_ids}, 过滤消息 {filtered_ids}")
            elif group_filtered:
                filtered_ids = [msg.id for msg in group_filtered]
                _logger.debug(f"媒体组全部过滤: {filtered_ids}")
        
        return passed_messages, filtered_messages
    
    def apply_text_replacements(self, text: str, text_replacements: Dict[str, str]) -> Tuple[str, bool]:
        """
        应用文本替换规则到文本内容
        
        Args:
            text: 原始文本
            text_replacements: 文本替换规则字典 {原文: 替换文本}
            
        Returns:
            Tuple[str, bool]: (替换后的文本, 是否发生了替换)
        """
        if not text or not text_replacements:
            return text, False
        
        result_text = text
        has_replacement = False
        
        for find_text, replace_text in text_replacements.items():
            if find_text and find_text in result_text:
                result_text = result_text.replace(find_text, replace_text)
                has_replacement = True
                _logger.debug(f"应用文本替换: '{find_text}' -> '{replace_text}'")
        
        return result_text, has_replacement
    
    def apply_general_filters(self, messages: List[Message], pair_config: Dict[str, Any]) -> Tuple[List[Message], List[Message]]:
        """
        应用通用过滤规则，支持媒体组级别的过滤
        （排除纯文本消息、包含链接的消息）
        
        Args:
            messages: 消息列表
            pair_config: 频道对配置
            
        Returns:
            Tuple[List[Message], List[Message]]: (通过的消息, 被过滤的消息)
        """
        # 按媒体组分组
        media_groups = self._group_messages_by_media_group(messages)
        
        passed_messages = []
        filtered_messages = []
        
        # 获取过滤规则（已删除转发消息和回复消息过滤）
        exclude_text = pair_config.get('exclude_text', False)
        exclude_links = pair_config.get('exclude_links', False)
        
        for group_messages in media_groups:
            should_filter_group = False
            filter_reason = ""
            
            # 检查媒体组中是否有任何消息触发过滤规则
            for message in group_messages:
                # 排除纯文本消息（整个媒体组都是纯文本才过滤）
                if exclude_text:
                    from src.utils.text_utils import is_media_message
                    is_media = is_media_message(message)
                    if not is_media and (message.text or message.caption):
                        # 检查整个媒体组是否都是纯文本
                        all_text = True
                        for msg in group_messages:
                            if is_media_message(msg):
                                all_text = False
                                break
                        if all_text:
                            should_filter_group = True
                            filter_reason = "纯文本媒体组"
                            break
                
                # 排除包含链接的消息
                if exclude_links:
                    text_to_check = message.text or message.caption or ""
                    message_entities = getattr(message, 'entities', None) or getattr(message, 'caption_entities', None)
                    if self._contains_links(text_to_check, message_entities):
                        should_filter_group = True
                        filter_reason = "包含链接的消息"
                        break
            
            group_ids = [msg.id for msg in group_messages]
            
            if should_filter_group:
                filtered_messages.extend(group_messages)
                _logger.info(f"媒体组 [ID: {group_ids}] 被通用过滤规则过滤: {filter_reason}")
                
                # 发射过滤事件到UI
                if self.emit:
                    for message in group_messages:
                        if len(group_messages) == 1:
                            # 单个消息
                            self.emit("message_filtered", message.id, tr("ui.forward.log.single_message"), filter_reason)
                        else:
                            # 媒体组消息
                            self.emit("message_filtered", f"{group_ids[0]}-{group_ids[-1]}", tr("ui.forward.log.media_group_message"), filter_reason)
                            break  # 对于媒体组，只发射一次事件
            else:
                passed_messages.extend(group_messages)
        
        return passed_messages, filtered_messages
    
    def apply_keyword_filter_with_text_processing(self, messages: List[Message], keywords: List[str]) -> Tuple[List[Message], List[Message], Dict[str, str]]:
        """
        应用关键词过滤，并处理媒体组文本重组
        媒体组中任何一条消息包含关键词，则整个媒体组都通过过滤，同时记录文本内容
        
        Args:
            messages: 消息列表
            keywords: 关键词列表
            
        Returns:
            Tuple[List[Message], List[Message], Dict[str, str]]: (通过的消息, 被过滤的消息, 媒体组文本映射)
        """
        if not keywords:
            return messages, [], {}
        
        # 首先按媒体组分组
        media_groups = self._group_messages_by_media_group(messages)
        
        passed_messages = []
        filtered_messages = []
        media_group_texts = {}  # 存储媒体组ID到文本的映射
        
        # 用于统计
        passed_groups = []
        filtered_groups = []
        
        for group_messages in media_groups:
            # 检查媒体组中是否有任何消息包含关键词
            group_has_keyword = False
            keywords_found_in_group = []
            group_text = ""  # 记录媒体组的文本内容
            
            for message in group_messages:
                # 获取要检查的文本内容
                text_content = ""
                if message.caption:
                    text_content = message.caption
                elif message.text:
                    text_content = message.text
                
                # 记录第一个有文本的消息内容作为媒体组文本
                if text_content and not group_text:
                    group_text = text_content
                
                if text_content:
                    # 检查是否包含任何关键词（不区分大小写）
                    for keyword in keywords:
                        if keyword.lower() in text_content.lower():
                            group_has_keyword = True
                            if keyword not in keywords_found_in_group:
                                keywords_found_in_group.append(keyword)
            
            # 获取媒体组ID用于日志和文本映射
            group_ids = [msg.id for msg in group_messages]
            media_group_id = getattr(group_messages[0], 'media_group_id', None)
            
            if group_has_keyword:
                # 整个媒体组通过过滤
                passed_messages.extend(group_messages)
                passed_groups.append(group_ids)
                
                # 如果是媒体组且有文本，记录文本内容
                if media_group_id and group_text:
                    media_group_texts[media_group_id] = group_text
                
                _logger.debug(f"媒体组 [ID: {group_ids}] 包含关键词 {keywords_found_in_group}，整个媒体组通过过滤")
            else:
                # 整个媒体组被过滤
                filtered_messages.extend(group_messages)
                filtered_groups.append(group_ids)
                
                # 发射过滤事件到UI
                if self.emit:
                    for message in group_messages:
                        if len(group_messages) == 1:
                            # 单个消息
                            self.emit("message_filtered", group_ids[0], tr("ui.forward.log.single_message"), tr("ui.forward.log.not_contain_keywords", keywords=keywords))
                        else:
                            # 媒体组消息
                            self.emit("message_filtered", f"{group_ids[0]}-{group_ids[-1]}", tr("ui.forward.log.media_group_message"), tr("ui.forward.log.not_contain_keywords", keywords=keywords))
                            break  # 对于媒体组，只发射一次事件
        
        # 汇总日志显示
        if filtered_groups:
            filtered_count = sum(len(group) for group in filtered_groups)
            group_count = len(filtered_groups)
            sample_groups = filtered_groups[:3]  # 显示前3个媒体组
            group_display = []
            for group in sample_groups:
                if len(group) == 1:
                    group_display.append(str(group[0]))
                else:
                    group_display.append(f"[{','.join(map(str, group))}]")
            
            more_indicator = f", +{group_count - 3}个媒体组" if group_count > 3 else ""
            _logger.info(f"关键词过滤: {group_count} 个媒体组({filtered_count} 条消息)不包含关键词 {keywords} 被过滤 (组ID: {', '.join(group_display)}{more_indicator})")
        
        if passed_groups:
            passed_count = sum(len(group) for group in passed_groups)
            group_count = len(passed_groups)
            sample_groups = passed_groups[:3]  # 显示前3个媒体组
            group_display = []
            for group in sample_groups:
                if len(group) == 1:
                    group_display.append(str(group[0]))
                else:
                    group_display.append(f"[{','.join(map(str, group))}]")
            
            more_indicator = f", +{group_count - 3}个媒体组" if group_count > 3 else ""
            _logger.info(f"关键词过滤: {group_count} 个媒体组({passed_count} 条消息)包含关键词通过过滤 (组ID: {', '.join(group_display)}{more_indicator})")
        
        return passed_messages, filtered_messages, media_group_texts
    
    def apply_all_filters(self, messages: List[Message], pair_config: Dict[str, Any]) -> Tuple[List[Message], List[Message], Dict[str, Any]]:
        """
        应用所有过滤规则的统一入口
        
        Args:
            messages: 消息列表
            pair_config: 频道对配置
            
        Returns:
            Tuple[List[Message], List[Message], Dict[str, Any]]: (通过的消息, 被过滤的消息, 过滤统计信息)
        """
        original_count = len(messages)
        filter_stats = {
            'original_count': original_count,
            'general_filtered': 0,
            'keyword_filtered': 0,
            'media_type_filtered': 0,
            'final_count': 0,
            'media_group_texts': {}  # 新增: 媒体组文本映射
        }
        
        current_messages = messages[:]
        all_filtered_messages = []
        
        # 0. 预提取媒体组文本（在任何过滤开始之前）
        # 这确保即使包含文本的消息被媒体类型过滤掉，我们仍能保留文本内容
        media_group_texts = self._extract_media_group_texts(current_messages)
        filter_stats['media_group_texts'] = media_group_texts
        if media_group_texts:
            _logger.debug(f"📝 预提取媒体组文本: 找到 {len(media_group_texts)} 个媒体组的文本内容")
        
        # 1. 应用通用过滤规则（排除纯文本消息、包含链接的消息）
        current_messages, general_filtered = self.apply_general_filters(current_messages, pair_config)
        all_filtered_messages.extend(general_filtered)
        filter_stats['general_filtered'] = len(general_filtered)
        if len(general_filtered) > 0:
            _logger.info(f"通用过滤: 过滤了 {len(general_filtered)} 条消息 (链接/纯文本)")
        
        # 2. 应用关键词过滤（使用新的带文本处理的方法）
        keywords = pair_config.get('keywords', [])
        _logger.debug(f"关键词配置: {keywords} (类型: {type(keywords)})")
        if keywords:
            current_messages, keyword_filtered, keyword_media_group_texts = self.apply_keyword_filter_with_text_processing(current_messages, keywords)
            all_filtered_messages.extend(keyword_filtered)
            filter_stats['keyword_filtered'] = len(keyword_filtered)
            # 合并关键词过滤产生的媒体组文本（但预提取的优先级更高）
            for group_id, text in keyword_media_group_texts.items():
                if group_id not in media_group_texts:
                    media_group_texts[group_id] = text
        else:
            _logger.debug(f"未设置关键词过滤，跳过关键词过滤")
        
        # 3. 应用媒体类型过滤（现在是消息级别的精确过滤）
        allowed_media_types = pair_config.get('media_types', [])
        if allowed_media_types:
            # 确保媒体类型是字符串列表，使用.value属性正确转换枚举
            media_types_str = []
            for t in allowed_media_types:
                if hasattr(t, 'value'):
                    media_types_str.append(t.value)
                else:
                    media_types_str.append(str(t))
            current_messages, media_filtered = self.apply_media_type_filter(current_messages, media_types_str)
            all_filtered_messages.extend(media_filtered)
            filter_stats['media_type_filtered'] = len(media_filtered)
            if len(media_filtered) > 0:
                _logger.info(f"媒体类型过滤: 过滤了 {len(media_filtered)} 条不符合类型要求的消息")
        
        # 更新最终的媒体组文本映射
        filter_stats['media_group_texts'] = media_group_texts
        filter_stats['final_count'] = len(current_messages)
        
        # 总结日志
        total_filtered = len(all_filtered_messages)
        if total_filtered > 0:
            _logger.info(f"📊 过滤结果: {original_count} 条消息 → {len(current_messages)} 条通过 (过滤了 {total_filtered} 条)")
        else:
            _logger.info(f"📊 过滤结果: 所有 {original_count} 条消息都通过了过滤")
        
        return current_messages, all_filtered_messages, filter_stats
    
    def _group_messages_by_media_group(self, messages: List[Message]) -> List[List[Message]]:
        """
        将消息按媒体组进行分组
        
        Args:
            messages: 消息列表
            
        Returns:
            List[List[Message]]: 分组后的消息列表，每个子列表代表一个媒体组
        """
        if not messages:
            return []
        
        # 按媒体组ID分组
        groups = {}
        
        for message in messages:
            # 获取媒体组ID，如果没有则使用消息ID作为唯一组
            group_id = getattr(message, 'media_group_id', None) or message.id
            
            if group_id not in groups:
                groups[group_id] = []
            groups[group_id].append(message)
        
        # 按消息ID排序每个组内的消息
        for group_messages in groups.values():
            group_messages.sort(key=lambda msg: msg.id)
        
        # 按第一个消息的ID排序各个组
        sorted_groups = sorted(groups.values(), key=lambda group: group[0].id)
        
        return sorted_groups
    
    def _get_message_media_type(self, message: Message) -> Optional[str]:
        """获取消息的媒体类型"""
        if message.photo:
            return "photo"
        elif message.video:
            return "video"
        elif message.document:
            return "document"
        elif message.audio:
            return "audio"
        elif message.animation:
            return "animation"
        elif message.sticker:
            return "sticker"
        elif message.voice:
            return "voice"
        elif message.video_note:
            return "video_note"
        elif message.text or message.caption:
            # 纯文本消息（包括只有文本或说明的消息）
            return "text"
        return None
    
    def _is_media_type_allowed(self, message_media_type, allowed_media_types):
        """
        已废弃：请统一使用 src.utils.text_utils.is_media_type_allowed
        """
        from src.utils.text_utils import is_media_type_allowed
        return is_media_type_allowed(message_media_type, allowed_media_types)
    
    def _contains_links(self, text: str, entities=None) -> bool:
        """
        检查文本是否包含链接
        
        Args:
            text: 文本内容
            entities: Telegram消息实体列表（用于检测隐式链接）
        
        Returns:
            bool: 是否包含链接
        """
        from src.utils.text_utils import contains_links
        return contains_links(text, entities)
    
    def is_media_allowed(self, message: Message, source_channel: str = None) -> bool:
        """
        检查消息媒体类型是否在允许列表中（兼容旧接口）
        
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
                media_types = ["text", "photo", "video", "document", "audio", "animation"]
                _logger.warning(f"找不到源频道 {source_channel} 的媒体类型配置，使用默认值")
        
        # 确保媒体类型是字符串列表，使用.value属性正确转换枚举
        media_types_str = []
        for t in media_types:
            if hasattr(t, 'value'):
                media_types_str.append(t.value)
            else:
                media_types_str.append(str(t))
        
        # 获取消息媒体类型
        message_media_type = self._get_message_media_type(message)
        
        if not message_media_type:
            # 如果无法识别媒体类型，默认不允许
            return False
        
        return self._is_media_type_allowed(message_media_type, media_types_str)
    
    def _extract_media_group_texts(self, messages: List[Message]) -> Dict[str, str]:
        """
        预提取所有媒体组的文本内容
        在任何过滤开始之前执行，确保文本内容不会因为媒体类型过滤而丢失
        
        Args:
            messages: 消息列表
            
        Returns:
            Dict[str, str]: 媒体组ID到文本内容的映射
        """
        if not messages:
            _logger.debug("🔍 _extract_media_group_texts: 消息列表为空，返回空映射")
            return {}
        
        _logger.debug(f"🔍 _extract_media_group_texts: 开始处理 {len(messages)} 条消息")
        
        # 按媒体组分组
        media_groups = self._group_messages_by_media_group(messages)
        media_group_texts = {}
        
        _logger.debug(f"🔍 _extract_media_group_texts: 分组结果，共 {len(media_groups)} 个组")
        
        for i, group_messages in enumerate(media_groups):
            # 获取媒体组ID
            media_group_id = getattr(group_messages[0], 'media_group_id', None)
            
            _logger.debug(f"🔍 组 {i+1}: 包含 {len(group_messages)} 条消息，媒体组ID: {media_group_id}")
            
            # 只处理真正的媒体组（有媒体组ID的）
            if not media_group_id:
                _logger.debug(f"🔍 组 {i+1}: 跳过，不是真正的媒体组（无媒体组ID）")
                continue
            
            # 寻找媒体组中第一个有文本内容的消息
            group_text = ""
            for j, message in enumerate(group_messages):
                text_content = ""
                if message.caption:
                    text_content = message.caption
                elif message.text:
                    text_content = message.text
                
                _logger.debug(f"🔍 组 {i+1} 消息 {j+1} (ID: {message.id}): caption='{message.caption[:30] if message.caption else None}', text='{message.text[:30] if message.text else None}'")
                
                if text_content:
                    group_text = text_content
                    _logger.debug(f"🔍 组 {i+1}: 在消息 {j+1} (ID: {message.id}) 中找到文本内容")
                    break  # 找到第一个有文本的消息就停止
            
            # 如果找到了文本内容，记录到映射中
            if group_text:
                media_group_texts[media_group_id] = group_text
                _logger.debug(f"✅ 媒体组 {media_group_id} 提取文本成功: '{group_text[:50]}...'")
            else:
                _logger.debug(f"❌ 媒体组 {media_group_id} 未找到文本内容")
        
        _logger.debug(f"🔍 _extract_media_group_texts: 完成，共提取 {len(media_group_texts)} 个媒体组的文本")
        
        return media_group_texts 