"""
文本过滤器模块，负责处理消息文本的过滤和替换
"""

import re
from typing import Dict, List, Tuple, Optional
from pyrogram.types import Message

from src.utils.logger import get_logger

logger = get_logger()

class TextFilter:
    """
    文本过滤器，用于处理消息文本的过滤和替换
    """
    
    def __init__(self, monitor_config: dict):
        """
        初始化文本过滤器
        
        Args:
            monitor_config: 监听配置字典
        """
        self.monitor_config = monitor_config
        
        # 统计替换规则数量
        total_text_filter_rules = 0
        
        # 文本替换规则字典，使用源频道ID作为键
        self.channel_text_replacements = {}
        # 移除标题选项字典，使用源频道ID作为键
        self.channel_remove_captions = {}
        
        for pair in self.monitor_config.get('monitor_channel_pairs', []):
            source_channel = pair.get('source_channel', '')
            
            # 加载文本替换规则
            text_replacements = {}
            if pair.get('text_filter'):
                for item in pair.get('text_filter', []):
                    # 只有当original_text不为空时才添加替换规则
                    if item.get('original_text'):
                        text_replacements[item.get('original_text')] = item.get('target_text', '')
                        total_text_filter_rules += 1
            
            # 存储每个源频道的配置
            self.channel_text_replacements[source_channel] = text_replacements
            self.channel_remove_captions[source_channel] = pair.get('remove_captions', False)
            
            if text_replacements:
                logger.debug(f"频道 {source_channel} 已加载 {len(text_replacements)} 条文本替换规则")
        
        logger.info(f"总共加载 {total_text_filter_rules} 条文本替换规则")
    
    def check_keywords(self, message: Message) -> bool:
        """
        检查消息是否包含配置的关键词
        
        Args:
            message: Pyrogram消息对象
            
        Returns:
            bool: 是否通过关键词过滤
        """
        keywords = self.monitor_config.get('keywords', [])
        
        # 如果没有设置关键词，则所有消息都通过
        if not keywords:
            return True
        
        # 获取消息文本
        text = message.text or message.caption or ""
        
        # 检查是否包含关键词
        matched_keywords = [keyword for keyword in keywords if re.search(keyword, text, re.IGNORECASE)]
        
        if not matched_keywords:
            logger.debug(f"消息 [ID: {message.id}] 不包含任何关键词，忽略")
            return False
            
        # 如果包含关键词，记录
        keywords_str = ", ".join(matched_keywords)
        logger.info(f"消息 [ID: {message.id}] 匹配关键词: {keywords_str}")
        return True
    
    def apply_text_replacements(self, text: str, text_replacements: Dict[str, str]) -> str:
        """
        应用文本替换规则
        
        Args:
            text: 需要替换的文本
            text_replacements: 文本替换规则字典
            
        Returns:
            str: 替换后的文本
        """
        return self.apply_text_replacements_static(text, text_replacements)
    
    @staticmethod
    def apply_text_replacements_static(text: str, text_replacements: Dict[str, str]) -> str:
        """
        静态方法：应用文本替换规则，不需要实例化TextFilter
        
        Args:
            text: 需要替换的文本
            text_replacements: 文本替换规则字典
            
        Returns:
            str: 替换后的文本
        """
        if not text or not text_replacements:
            return text
        
        modified_text = text
        replacement_made = False
        replacements = []
        
        for original, replacement in text_replacements.items():
            if original in modified_text:
                old_text = modified_text
                modified_text = modified_text.replace(original, replacement)
                if old_text != modified_text:
                    replacement_made = True
                    replacements.append((original, replacement))
                    logger.debug(f"文本替换: '{original}' -> '{replacement}'")
        
        if replacement_made:
            logger.info(f"已应用文本替换，原文本: '{text}'，新文本: '{modified_text}'")
        
        return modified_text
    
    @staticmethod
    def apply_universal_filters(message: Message, pair_config: dict) -> Tuple[bool, str]:
        """
        应用通用消息过滤规则（最高优先级判断）- 统一过滤逻辑入口
        
        Args:
            message: 消息对象
            pair_config: 频道对配置
            
        Returns:
            tuple[bool, str]: (是否被过滤, 过滤原因)
        """
        try:
            # 获取该频道对的过滤选项
            exclude_forwards = pair_config.get('exclude_forwards', False)
            exclude_replies = pair_config.get('exclude_replies', False)
            exclude_text = pair_config.get('exclude_text', pair_config.get('exclude_media', False))
            exclude_links = pair_config.get('exclude_links', False)
            
            # 【最高优先级1】排除转发消息
            if exclude_forwards and (message.forward_from or message.forward_from_chat):
                filter_reason = "转发消息"
                logger.info(f"消息 [ID: {message.id}] 是{filter_reason}，根据过滤规则跳过")
                return True, filter_reason

            # 【最高优先级2】排除回复消息
            if exclude_replies and message.reply_to_message:
                filter_reason = "回复消息"
                logger.info(f"消息 [ID: {message.id}] 是{filter_reason}，根据过滤规则跳过")
                return True, filter_reason

            # 【最高优先级3】排除纯文本消息
            if exclude_text:
                # 检查是否为纯文本消息（没有任何媒体内容）
                is_media_message = bool(message.photo or message.video or message.document or 
                                      message.audio or message.animation or message.sticker or 
                                      message.voice or message.video_note)
                if not is_media_message and (message.text or message.caption):
                    filter_reason = "纯文本消息"
                    logger.info(f"消息 [ID: {message.id}] 是{filter_reason}，根据过滤规则跳过")
                    return True, filter_reason

            # 【最高优先级4】排除包含链接的消息
            if exclude_links:
                # 检查消息文本或说明中是否包含链接
                text_to_check = message.text or message.caption or ""
                if TextFilter._contains_links(text_to_check):
                    filter_reason = "包含链接的消息"
                    logger.info(f"消息 [ID: {message.id}] {filter_reason}，根据过滤规则跳过")
                    return True, filter_reason

            # 所有过滤检查都通过
            return False, ""
            
        except Exception as e:
            logger.error(f"应用通用消息过滤时发生错误: {str(e)}")
            # 发生错误时认为消息不被过滤，让后续处理决定
            return False, ""
    
    @staticmethod
    def apply_universal_filters_to_list(messages: List[Message], pair_config: dict) -> Tuple[List[Message], List[Message]]:
        """
        应用通用消息过滤规则到消息列表（批量处理版本）
        
        Args:
            messages: 消息列表
            pair_config: 频道对配置
            
        Returns:
            Tuple[List[Message], List[Message]]: (通过过滤的消息列表, 被过滤的消息列表)
        """
        if not messages:
            return [], []
            
        try:
            passed_messages = []
            filtered_messages = []
            
            for message in messages:
                is_filtered, filter_reason = TextFilter.apply_universal_filters(message, pair_config)
                
                if is_filtered:
                    logger.info(f"消息 [ID: {message.id}] 被通用过滤规则过滤: {filter_reason}")
                    filtered_messages.append(message)
                else:
                    passed_messages.append(message)
            
            return passed_messages, filtered_messages
            
        except Exception as e:
            logger.error(f"应用通用消息过滤到列表时发生错误: {str(e)}")
            # 发生错误时返回原始消息列表，让后续处理决定
            return messages, []
    
    @staticmethod
    def apply_keyword_filter(message: Message, keywords: List[str]) -> Tuple[bool, str]:
        """
        应用关键词过滤
        
        Args:
            message: 消息对象
            keywords: 关键词列表
            
        Returns:
            tuple[bool, str]: (是否被过滤, 过滤原因)
        """
        if not keywords:
            return False, ""
        
        text_to_check = (message.text or message.caption or "").lower()
        keywords_passed = any(keyword.lower() in text_to_check for keyword in keywords)
        
        if not keywords_passed:
            filter_reason = f"不包含关键词({', '.join(keywords)})"
            return True, filter_reason
        
        return False, ""
    
    @staticmethod
    def apply_media_type_filter(message: Message, allowed_media_types: List) -> Tuple[bool, str]:
        """
        应用媒体类型过滤
        
        Args:
            message: 消息对象
            allowed_media_types: 允许的媒体类型列表
            
        Returns:
            tuple[bool, str]: (是否被过滤, 过滤原因)
        """
        if not allowed_media_types:
            return False, ""
        
        message_media_type = TextFilter._get_message_media_type(message)
        if message_media_type and not TextFilter._is_media_type_allowed(message_media_type, allowed_media_types):
            media_type_names = {
                "photo": "照片", "video": "视频", "document": "文件", "audio": "音频",
                "animation": "动画", "sticker": "贴纸", "voice": "语音", "video_note": "视频笔记"
            }
            media_type_name = media_type_names.get(message_media_type.value, message_media_type.value)
            filter_reason = f"媒体类型({media_type_name})不在允许列表中"
            return True, filter_reason
        
        return False, ""
    
    @staticmethod
    def _get_message_media_type(message: Message):
        """
        获取消息的媒体类型
        
        Args:
            message: 消息对象
            
        Returns:
            MediaType: 媒体类型枚举，如果是纯文本消息则返回None
        """
        from src.utils.ui_config_models import MediaType
        
        if message.photo:
            return MediaType.PHOTO
        elif message.video:
            return MediaType.VIDEO
        elif message.document:
            return MediaType.DOCUMENT
        elif message.audio:
            return MediaType.AUDIO
        elif message.animation:
            return MediaType.ANIMATION
        elif message.sticker:
            return MediaType.STICKER
        elif message.voice:
            return MediaType.VOICE
        elif message.video_note:
            return MediaType.VIDEO_NOTE
        else:
            # 纯文本消息，不需要媒体类型过滤
            return None
    
    @staticmethod
    def _is_media_type_allowed(message_media_type, allowed_media_types):
        """
        已废弃：请统一使用 src.utils.text_utils.is_media_type_allowed
        """
        from src.utils.text_utils import is_media_type_allowed
        return is_media_type_allowed(message_media_type, allowed_media_types)
    
    @staticmethod
    def _contains_links(text: str) -> bool:
        """
        检查文本中是否包含链接
        
        Args:
            text: 要检查的文本
            
        Returns:
            bool: 是否包含链接
        """
        from src.utils.text_utils import contains_links
        return contains_links(text)
    
    @staticmethod
    def process_text_and_caption(message: Message, text_replacements: Dict[str, str], 
                                remove_captions: bool) -> Tuple[Optional[str], bool]:
        """
        处理消息的文本替换和标题移除
        
        Args:
            message: 消息对象
            text_replacements: 文本替换规则
            remove_captions: 是否移除标题
            
        Returns:
            tuple[Optional[str], bool]: (替换后的文本, 是否应该移除标题)
        """
        # 检查是否为媒体消息
        from src.utils.text_utils import is_media_message
        is_media = is_media_message(message)
        
        # 获取原始文本
        text = message.text or message.caption or ""
        replaced_text = None
        should_remove_caption = False
        
        # 应用文本替换
        if text and text_replacements:
            replaced_text = TextFilter.apply_text_replacements_static(text, text_replacements)
            if replaced_text != text:
                logger.info(f"消息 [ID: {message.id}] 已应用文本替换")
        
        # 处理移除媒体说明的逻辑
        if remove_captions:
            if is_media:
                # 媒体消息：移除说明文字，忽略文本替换的结果
                should_remove_caption = True
                replaced_text = None  # 强制清空文本替换结果
                logger.debug(f"媒体消息 [ID: {message.id}] 将移除说明文字，忽略文本替换结果")
            else:
                # 纯文本消息：移除媒体说明无效，但文本替换依然有效
                if replaced_text and replaced_text != text:
                    logger.debug(f"纯文本消息 [ID: {message.id}] 移除媒体说明无效，但文本替换已应用")
                else:
                    logger.debug(f"纯文本消息 [ID: {message.id}] 移除媒体说明无效")
        else:
            # 不移除媒体说明时，使用文本替换的结果
            should_remove_caption = False
        
        return replaced_text, should_remove_caption 