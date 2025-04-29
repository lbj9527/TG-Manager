"""
直接转发器，用于直接转发消息（不需要下载重新上传）
"""

import asyncio
from typing import List, Tuple, Dict, Union, Optional, Set

from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait, ChatForwardsRestricted, ChannelPrivate

from src.utils.logger import get_logger

_logger = get_logger()

class DirectForwarder:
    """
    直接转发器，使用Telegram原生转发功能
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
    
    async def forward_media_group_directly(self, 
                                         messages: List[Message], 
                                         source_channel: str, 
                                         source_id: int, 
                                         target_channels: List[Tuple[str, int, str]],
                                         hide_author: bool = False) -> bool:
        """
        直接转发媒体组到目标频道
        
        Args:
            messages: 消息列表
            source_channel: 源频道标识符
            source_id: 源频道ID
            target_channels: 目标频道列表(频道标识符, 频道ID, 频道信息)
            hide_author: 是否隐藏作者
            
        Returns:
            bool: 是否成功转发到至少一个目标频道
        """
        # 检查是否是单条消息
        is_single = len(messages) == 1
        
        # 消息ID列表（用于日志和事件）
        message_ids = [msg.id for msg in messages]
        
        # 媒体组ID（用于事件通知）
        group_id = f"single_{message_ids[0]}" if is_single else f"group_{message_ids[0]}"
        
        # 转发成功计数
        success_count = 0
        
        for target_channel, target_id, target_info in target_channels:
            # 检查是否已转发到此频道
            all_forwarded = True
            for message in messages:
                if not self.history_manager or not self.history_manager.is_message_forwarded(source_channel, message.id, target_channel):
                    all_forwarded = False
                    break
            
            if all_forwarded:
                debug_message = f"消息已转发到频道 {target_info}，跳过"
                _logger.debug(debug_message)
                continue
            
            try:
                info_message = f"转发消息到频道 {target_info}"
                _logger.info(info_message)
                
                if is_single:
                    # 单条消息转发
                    message = messages[0]
                    
                    try:
                        if hide_author:
                            # 使用copy_message隐藏作者
                            debug_message = f"使用copy_message方法隐藏作者转发消息 {message.id}"
                            _logger.debug(debug_message)
                            
                            forwarded = await self.client.copy_message(
                                chat_id=target_id,
                                from_chat_id=source_id,
                                message_id=message.id
                            )
                        else:
                            # 使用forward_messages保留作者信息
                            debug_message = f"使用forward_messages方法保留作者转发消息 {message.id}"
                            _logger.debug(debug_message)
                            
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
                        
                        success_message = f"消息 {message.id} 转发到 {target_info} 成功"
                        _logger.info(success_message)
                        success_count += 1
                    except Exception as e:
                        error_message = f"转发单条消息 {message.id} 到 {target_info} 失败: {e}，跳过"
                        _logger.error(error_message)
                        continue
                else:
                    # 媒体组转发
                    try:
                        if hide_author:
                            # 使用copy_media_group方法一次性转发整个媒体组
                            debug_message = f"使用copy_media_group方法隐藏作者转发媒体组消息"
                            _logger.debug(debug_message)
                            
                            # 只需要第一条消息的ID，因为copy_media_group会自动获取同一组的所有消息
                            first_message_id = message_ids[0]
                            forwarded = await self.client.copy_media_group(
                                chat_id=target_id,
                                from_chat_id=source_id,
                                message_id=first_message_id
                            )
                        else:
                            # 使用forward_messages批量转发
                            debug_message = f"使用forward_messages方法保留作者批量转发媒体组消息"
                            _logger.debug(debug_message)
                            
                            forwarded = await self.client.forward_messages(
                                chat_id=target_id,
                                from_chat_id=source_id,
                                message_ids=message_ids,
                                disable_notification=True
                            )
                        
                        # 转发成功后才记录历史
                        if self.history_manager:
                            for message in messages:
                                self.history_manager.add_forward_record(
                                    source_channel,
                                    message.id,
                                    target_channel,
                                    source_id
                                )
                        
                        success_message = f"媒体组 {message_ids} 转发到 {target_info} 成功"
                        _logger.info(success_message)
                        success_count += 1
                    except Exception as e:
                        error_message = f"转发媒体组 {message_ids} 到 {target_info} 失败: {e}，跳过"
                        _logger.error(error_message)
                        continue
                
                # 转发延迟
                await asyncio.sleep(1)
            
            except FloodWait as e:
                warning_message = f"转发消息时遇到限制，等待 {e.x} 秒"
                _logger.warning(warning_message)
                
                try:
                    await asyncio.sleep(e.x)
                    # 重试此频道
                    retry_result = await self.forward_media_group_directly(messages, source_channel, source_id, [(target_channel, target_id, target_info)], hide_author)
                    if retry_result:
                        success_count += 1
                except Exception as retry_e:
                    error_message = f"重试转发到频道 {target_info} 失败: {retry_e}"
                    _logger.error(error_message)
            
            except Exception as e:
                error_message = f"转发消息到频道 {target_info} 失败: {e}"
                _logger.error(error_message)
                import traceback
                error_details = traceback.format_exc()
                _logger.error(error_details)
                continue
        
        # 返回是否至少有一个频道转发成功
        return success_count > 0 