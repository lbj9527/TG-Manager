"""
消息处理器模块，负责处理和转发消息
"""

import asyncio
from typing import List, Tuple, Callable, Dict, Any

from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait, ChatForwardsRestricted, ChannelPrivate

from src.utils.channel_resolver import ChannelResolver
from src.utils.logger import get_logger

logger = get_logger()

class MessageProcessor:
    """
    消息处理器，负责处理和转发消息
    """
    
    def __init__(self, client: Client, channel_resolver: ChannelResolver, network_error_handler: Callable = None):
        """
        初始化消息处理器
        
        Args:
            client: Pyrogram客户端实例
            channel_resolver: 频道解析器实例
            network_error_handler: 网络错误处理函数
        """
        self.client = client
        self.channel_resolver = channel_resolver
        self.network_error_handler = network_error_handler
        self.monitor_config = {}
        
    def set_monitor_config(self, monitor_config: Dict[str, Any]):
        """
        设置监控配置
        
        Args:
            monitor_config: 监控配置字典
        """
        self.monitor_config = monitor_config
    
    async def forward_message(self, message: Message, target_channels: List[Tuple[str, int, str]]) -> bool:
        """
        转发消息到所有目标频道
        
        Args:
            message: 要转发的消息
            target_channels: 目标频道列表 (channel_id_or_username, resolved_id, display_name)
            
        Returns:
            bool: 是否成功转发
        """
        if not target_channels:
            logger.warning(f"没有有效的目标频道，跳过转发消息 [ID: {message.id}]")
            return False
            
        try:
            source_chat = message.chat
            source_chat_id = source_chat.id
            source_message_id = message.id
            
            # 尝试获取频道信息
            try:
                source_title = source_chat.title
            except:
                source_title = str(source_chat_id)
            
            logger.info(f"开始转发消息 [ID: {source_message_id}] 从 {source_title} 到 {len(target_channels)} 个目标频道")
            
            # 转发到所有目标频道
            success_count = 0
            failed_count = 0
            
            for target, target_id, target_info in target_channels:
                try:
                    # 转发消息
                    await self.client.forward_messages(
                        chat_id=target_id,
                        from_chat_id=source_chat_id,
                        message_ids=source_message_id
                    )
                    
                    success_count += 1
                    logger.info(f"已将消息 {source_message_id} 从 {source_title} 转发到 {target_info}")
                    
                except ChatForwardsRestricted:
                    logger.warning(f"目标频道 {target_info} 禁止转发消息，尝试使用复制方式发送")
                    try:
                        # 使用copy_message复制消息而不是转发
                        await self.client.copy_message(
                            chat_id=target_id,
                            from_chat_id=source_chat_id,
                            message_id=source_message_id
                        )
                        success_count += 1
                        logger.info(f"已使用复制方式将消息 {source_message_id} 从 {source_title} 发送到 {target_info}")
                    except Exception as copy_e:
                        failed_count += 1
                        logger.error(f"复制消息失败: {str(copy_e)}", error_type="COPY_MESSAGE", recoverable=True)
                        # 尝试重新发送修改后的消息
                        try:
                            # 获取原始消息的文本或标题
                            text = message.text or message.caption or ""
                            await self.send_modified_message(message, text, [(target, target_id, target_info)])
                            success_count += 1
                            logger.info(f"已使用修改方式将消息 {source_message_id} 从 {source_title} 发送到 {target_info}")
                        except Exception as modified_e:
                            logger.error(f"发送修改后的消息失败: {str(modified_e)}", error_type="SEND_MODIFIED", recoverable=True)
                    
                except FloodWait as e:
                    logger.warning(f"触发FloodWait，等待 {e.x} 秒后继续")
                    await asyncio.sleep(e.x)
                    # 重试转发
                    try:
                        # 优先使用copy_message避免转发限制
                        await self.client.copy_message(
                            chat_id=target_id,
                            from_chat_id=source_chat_id,
                            message_id=source_message_id
                        )
                        success_count += 1
                        logger.info(f"重试成功：已将消息 {source_message_id} 从 {source_title} 发送到 {target_info}")
                    except Exception as retry_e:
                        failed_count += 1
                        logger.error(f"重试转发失败: {str(retry_e)}", error_type="FORWARD_RETRY", recoverable=True)
                        
                except ChannelPrivate:
                    failed_count += 1
                    logger.error(f"无法访问目标频道 {target_info}，可能是私有频道或未加入", error_type="CHANNEL_PRIVATE", recoverable=True)
                    
                except Exception as e:
                    failed_count += 1
                    logger.error(f"转发消息 {source_message_id} 到 {target_info} 失败: {str(e)}", error_type="FORWARD", recoverable=True)
                
                # 转发间隔
                await asyncio.sleep(0.5)
            
            # 统计结果
            logger.info(f"消息 [ID: {source_message_id}] 转发完成: 成功 {success_count}, 失败 {failed_count}")    
                
        except Exception as e:
            logger.error(f"处理消息转发时发生异常: {str(e)}", error_type="FORWARD_PROCESS", recoverable=True)
            
            # 检测网络相关错误
            error_name = type(e).__name__.lower()
            if any(net_err in error_name for net_err in ['network', 'connection', 'timeout', 'socket']):
                # 网络相关错误，通知应用程序检查连接状态
                if self.network_error_handler:
                    await self.network_error_handler(e)
                
            return False
        
        return True
    
    async def send_modified_message(self, original_message: Message, new_text: str, target_channels: List[Tuple[str, int, str]], remove_caption: bool = False) -> bool:
        """
        发送修改后的消息到所有目标频道
        
        Args:
            original_message: 原始消息
            new_text: 新的文本内容
            target_channels: 目标频道列表
            remove_caption: 是否移除标题
            
        Returns:
            bool: 是否成功发送
        """
        if not target_channels:
            logger.warning(f"没有有效的目标频道，跳过发送修改后的消息 [ID: {original_message.id}]")
            return False
            
        try:
            source_chat = original_message.chat
            source_chat_id = source_chat.id
            source_message_id = original_message.id
            
            # 尝试获取频道信息
            try:
                source_title = source_chat.title
            except:
                source_title = str(source_chat_id)
                
            logger.info(f"开始发送修改后的消息 [ID: {source_message_id}] 从 {source_title} 到 {len(target_channels)} 个目标频道")
            
            # 如果是移除标题模式并且消息中有媒体
            if remove_caption and (
                original_message.photo or 
                original_message.video or 
                original_message.document or 
                original_message.animation or 
                original_message.audio
            ):
                # 使用空标题
                caption_to_use = ""
                logger.debug(f"使用空标题（移除标题模式）")
            else:
                # 使用新文本
                caption_to_use = new_text
                if new_text != (original_message.text or original_message.caption or ""):
                    logger.debug(f"使用修改后的文本: '{new_text}'")
            
            # 发送到所有目标频道
            success_count = 0
            failed_count = 0
            
            for target, target_id, target_info in target_channels:
                try:
                    sent_message = None
                    
                    # 根据消息类型重新发送
                    if original_message.photo:
                        # 照片消息
                        sent_message = await self.client.send_photo(
                            chat_id=target_id,
                            photo=original_message.photo.file_id,
                            caption=caption_to_use if not remove_caption else None
                        )
                    elif original_message.video:
                        # 视频消息
                        sent_message = await self.client.send_video(
                            chat_id=target_id,
                            video=original_message.video.file_id,
                            caption=caption_to_use if not remove_caption else None,
                            supports_streaming=True
                        )
                    elif original_message.document:
                        # 文档消息
                        sent_message = await self.client.send_document(
                            chat_id=target_id,
                            document=original_message.document.file_id,
                            caption=caption_to_use if not remove_caption else None
                        )
                    elif original_message.animation:
                        # 动画/GIF消息
                        sent_message = await self.client.send_animation(
                            chat_id=target_id,
                            animation=original_message.animation.file_id,
                            caption=caption_to_use if not remove_caption else None
                        )
                    elif original_message.audio:
                        # 音频消息
                        sent_message = await self.client.send_audio(
                            chat_id=target_id,
                            audio=original_message.audio.file_id,
                            caption=caption_to_use if not remove_caption else None
                        )
                    else:
                        # 纯文本消息
                        sent_message = await self.client.send_message(
                            chat_id=target_id,
                            text=caption_to_use
                        )
                    
                    if sent_message:
                        success_count += 1
                        logger.info(f"已将修改后的消息从 {source_title} 发送到 {target_info}")
                    
                except FloodWait as e:
                    logger.warning(f"触发FloodWait，等待 {e.x} 秒后继续")
                    await asyncio.sleep(e.x)
                    # 重试发送不再实现，以简化代码
                    failed_count += 1
                    
                except Exception as e:
                    failed_count += 1
                    logger.error(f"发送修改后的消息到 {target_info} 失败: {str(e)}", error_type="SEND_MODIFIED", recoverable=True)
                
                # 发送间隔
                await asyncio.sleep(0.5)
            
            # 统计结果
            logger.info(f"消息 [ID: {source_message_id}] 修改后发送完成: 成功 {success_count}, 失败 {failed_count}")
            
        except Exception as e:
            logger.error(f"处理修改后消息发送时发生异常: {str(e)}", error_type="MODIFIED_PROCESS", recoverable=True)
            return False
            
        return True 