"""
直接转发器，用于直接转发消息（不需要下载重新上传）
支持统一的过滤功能：文本替换、关键词过滤、媒体类型过滤
"""

import asyncio
from typing import List, Tuple, Dict, Union, Optional, Set

from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait, ChatForwardsRestricted, ChannelPrivate

from src.utils.logger import get_logger
from src.modules.forward.message_filter import MessageFilter
from src.utils.ui_config_models import MediaType

_logger = get_logger()

class DirectForwarder:
    """
    直接转发器，使用Telegram原生转发功能
    支持统一的过滤功能
    """
    
    def __init__(self, client: Client, history_manager=None):
        """
        初始化直接转发器
        
        Args:
            client: Pyrogram客户端实例
            history_manager: 历史记录管理器实例，用于记录已转发的消息
        """
        self.client = client
        self.history_manager = history_manager
        
        # 初始化消息过滤器
        self.message_filter = MessageFilter()
    
    async def forward_media_group_directly(self, 
                                         messages: List[Message], 
                                         source_channel: str, 
                                         source_id: int, 
                                         target_channels: List[Tuple[str, int, str]],
                                         hide_author: bool = False,
                                         pair_config: Dict = None) -> bool:
        """
        直接转发媒体组到目标频道，支持统一的过滤功能
        
        Args:
            messages: 消息列表
            source_channel: 源频道标识符
            source_id: 源频道ID
            target_channels: 目标频道列表(频道标识符, 频道ID, 频道信息)
            hide_author: 是否隐藏作者
            pair_config: 频道对配置（包含过滤规则）
            
        Returns:
            bool: 是否成功转发到至少一个目标频道
        """
        if not messages:
            _logger.warning("消息列表为空，跳过转发")
            return False
        
        # 如果提供了频道对配置，应用过滤规则
        filtered_messages = messages
        if pair_config:
            filtered_messages, _, filter_stats = self.message_filter.apply_all_filters(messages, pair_config)
            
            if not filtered_messages:
                _logger.info(f"⚠️ 所有消息都被过滤器过滤掉，跳过转发")
                return False
            
            if len(filtered_messages) != len(messages):
                _logger.info(f"✅ 过滤完成，剩余 {len(filtered_messages)}/{len(messages)} 条消息进行转发")
        
        # 检查是否需要文本替换
        text_replacements = {}
        if pair_config:
            # 构建文本替换字典
            text_filter_list = pair_config.get('text_filter', [])
            if text_filter_list:
                for rule in text_filter_list:
                    original = rule.get('original_text', '')
                    target = rule.get('target_text', '')
                    if original:  # 只添加非空的原文
                        text_replacements[original] = target
        
        # 如果有文本替换需求，需要使用copy方式而不是forward方式
        need_text_replacement = bool(text_replacements)
        force_copy_mode = need_text_replacement or pair_config.get('remove_captions', False)
        
        # 检查是否是单条消息
        is_single = len(filtered_messages) == 1
        
        # 消息ID列表（用于日志和事件）
        message_ids = [msg.id for msg in filtered_messages]
        
        # 媒体组ID（用于事件通知）
        group_id = f"single_{message_ids[0]}" if is_single else f"group_{message_ids[0]}"
        
        # 转发成功计数
        success_count = 0
        
        for target_channel, target_id, target_info in target_channels:
            # 检查是否已转发到此频道
            all_forwarded = True
            for message in filtered_messages:
                if not self.history_manager or not self.history_manager.is_message_forwarded(source_channel, message.id, target_channel):
                    all_forwarded = False
                    break
            
            if all_forwarded:
                _logger.debug(f"消息已转发到频道 {target_info}，跳过")
                continue
            
            try:
                _logger.info(f"转发消息到频道 {target_info}")
                
                if is_single:
                    # 单条消息转发
                    message = filtered_messages[0]
                    
                    # 处理文本替换
                    final_caption = None
                    if force_copy_mode:
                        original_caption = message.caption or ""
                        if pair_config.get('remove_captions', False):
                            final_caption = ""
                        elif text_replacements and original_caption:
                            final_caption, _ = self.message_filter.apply_text_replacements(original_caption, text_replacements)
                        else:
                            final_caption = original_caption
                    
                    try:
                        if force_copy_mode:
                            # 使用copy_message支持文本替换
                            _logger.debug(f"使用copy_message方法转发消息 {message.id} (支持文本替换)")
                            
                            forwarded = await self.client.copy_message(
                                chat_id=target_id,
                                from_chat_id=source_id,
                                message_id=message.id,
                                caption=final_caption
                            )
                        elif hide_author:
                            # 使用copy_message隐藏作者
                            _logger.debug(f"使用copy_message方法隐藏作者转发消息 {message.id}")
                            
                            forwarded = await self.client.copy_message(
                                chat_id=target_id,
                                from_chat_id=source_id,
                                message_id=message.id
                            )
                        else:
                            # 使用forward_messages保留作者信息
                            _logger.debug(f"使用forward_messages方法保留作者转发消息 {message.id}")
                            
                            forwarded = await self.client.forward_messages(
                                chat_id=target_id,
                                from_chat_id=source_id,
                                message_ids=message.id,
                                disable_notification=True
                            )
                        
                        # 转发成功后才记录历史
                        if self.history_manager:
                            self.history_manager.add_forward_record(
                                source_channel,
                                message.id,
                                target_channel,
                                source_id
                            )
                        
                        _logger.info(f"✅ 消息 {message.id} 转发到 {target_info} 成功")
                        success_count += 1
                    except Exception as e:
                        _logger.error(f"转发单条消息 {message.id} 到 {target_info} 失败: {e}，跳过")
                        continue
                else:
                    # 媒体组转发
                    try:
                        if force_copy_mode:
                            # 需要文本替换或移除说明，使用copy_media_group
                            _logger.debug(f"使用copy_media_group方法转发媒体组 (支持文本替换)")
                            
                            # 获取第一条消息用于文本处理
                            first_message = None
                            original_caption = ""
                            for msg in filtered_messages:
                                if msg.caption:
                                    first_message = msg
                                    original_caption = msg.caption
                                    break
                            
                            # 处理标题
                            final_caption = None
                            if pair_config.get('remove_captions', False):
                                final_caption = ""
                            elif text_replacements and original_caption:
                                final_caption, _ = self.message_filter.apply_text_replacements(original_caption, text_replacements)
                            else:
                                final_caption = original_caption if original_caption else None
                            
                            # 只需要第一条消息的ID，因为copy_media_group会自动获取同一组的所有消息
                            first_message_id = message_ids[0]
                            forwarded = await self.client.copy_media_group(
                                chat_id=target_id,
                                from_chat_id=source_id,
                                message_id=first_message_id,
                                captions=final_caption
                            )
                        elif hide_author:
                            # 使用copy_media_group方法隐藏作者
                            _logger.debug(f"使用copy_media_group方法隐藏作者转发媒体组消息")
                            
                            # 只需要第一条消息的ID，因为copy_media_group会自动获取同一组的所有消息
                            first_message_id = message_ids[0]
                            forwarded = await self.client.copy_media_group(
                                chat_id=target_id,
                                from_chat_id=source_id,
                                message_id=first_message_id
                            )
                        else:
                            # 使用forward_messages批量转发
                            _logger.debug(f"使用forward_messages方法保留作者批量转发媒体组消息")
                            
                            forwarded = await self.client.forward_messages(
                                chat_id=target_id,
                                from_chat_id=source_id,
                                message_ids=message_ids,
                                disable_notification=True
                            )
                        
                        # 转发成功后才记录历史
                        if self.history_manager:
                            for message in filtered_messages:
                                self.history_manager.add_forward_record(
                                    source_channel,
                                    message.id,
                                    target_channel,
                                    source_id
                                )
                        
                        _logger.info(f"✅ 媒体组 {message_ids} 转发到 {target_info} 成功")
                        success_count += 1
                    except Exception as e:
                        _logger.error(f"转发媒体组 {message_ids} 到 {target_info} 失败: {e}，跳过")
                        continue
                
                # 转发延迟
                await asyncio.sleep(1)
            
            except FloodWait as e:
                _logger.warning(f"转发消息时遇到限制，等待 {e.x} 秒")
                
                try:
                    await asyncio.sleep(e.x)
                    # 重试此频道
                    retry_result = await self.forward_media_group_directly(
                        filtered_messages, source_channel, source_id, 
                        [(target_channel, target_id, target_info)], hide_author, pair_config
                    )
                    if retry_result:
                        success_count += 1
                except Exception as retry_e:
                    _logger.error(f"重试转发到频道 {target_info} 失败: {retry_e}")
            
            except Exception as e:
                _logger.error(f"转发消息到频道 {target_info} 失败: {e}")
                import traceback
                _logger.error(traceback.format_exc())
                continue
        
        # 返回是否至少有一个频道转发成功
        return success_count > 0
    
    def _convert_text_filter_to_replacements(self, text_filter_list: List[Dict]) -> Dict[str, str]:
        """
        将UI格式的文本过滤规则转换为替换字典
        
        Args:
            text_filter_list: UI格式的文本过滤规则列表
            
        Returns:
            Dict[str, str]: 文本替换字典 {原文: 替换文本}
        """
        text_replacements = {}
        if text_filter_list:
            for rule in text_filter_list:
                original = rule.get('original_text', '')
                target = rule.get('target_text', '')
                if original:  # 只添加非空的原文
                    text_replacements[original] = target
        return text_replacements 