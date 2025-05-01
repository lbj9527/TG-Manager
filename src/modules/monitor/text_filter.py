"""
文本过滤器模块，负责处理消息文本的过滤和替换
"""

import re
from typing import Dict, List
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