"""
监听模块，负责监听源频道新消息并转发到目标频道
"""

import asyncio
import threading
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Union, Set, Callable, Any
import re

from pyrogram import Client, filters
from pyrogram.types import (
    Message, InputMediaPhoto, InputMediaVideo, 
    InputMediaDocument, InputMediaAudio, InputMediaAnimation
)
from pyrogram.errors import FloodWait, ChatForwardsRestricted, ChannelPrivate, MediaEmpty, MediaInvalid
from pyrogram.handlers import MessageHandler

from src.utils.ui_config_manager import UIConfigManager
from src.utils.ui_config_models import UIMonitorChannelPair
from src.utils.config_utils import convert_ui_config_to_dict
from src.utils.channel_resolver import ChannelResolver
from src.utils.logger import get_logger
from src.utils.history_manager import HistoryManager

# 仅用于内部调试，不再用于UI输出
logger = get_logger()

class Monitor():
    """
    监听模块，监听源频道的新消息，并实时转发到目标频道
    """
    
    def __init__(self, client: Client, ui_config_manager: UIConfigManager, channel_resolver: ChannelResolver, history_manager: Optional[HistoryManager] = None, app=None):
        """
        初始化监听模块
        
        Args:
            client: Pyrogram客户端实例
            ui_config_manager: UI配置管理器实例
            channel_resolver: 频道解析器实例
            history_manager: 历史记录管理器实例，可选
            app: 应用程序实例，用于网络错误时立即检查连接状态
        """
        # 初始化
        self.client = client
        self.ui_config_manager = ui_config_manager
        self.channel_resolver = channel_resolver
        self.history_manager = history_manager
        self.app = app  # 保存应用程序实例引用
        
        # 获取UI配置并转换为字典
        ui_config = self.ui_config_manager.get_ui_config()
        self.config = convert_ui_config_to_dict(ui_config)
        
        # 获取监听配置
        self.monitor_config = self.config.get('MONITOR', {})
        
        # 控制变量
        self.should_stop = False
        self.monitor_tasks = []
        
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
        
        # 消息处理器字典，用于跟踪每个源频道的消息处理器
        self.message_handlers = []
        
        # 已处理的消息ID集合，用于防止重复处理同一条消息
        self.processed_messages = set()
        
        # 定期清理已处理消息ID的任务
        self.cleanup_task = None
        
        # 存储所有监听的频道ID
        self.monitored_channels: Set[int] = set()
        
        # 消息处理中
        self.is_processing = False
        
        # 媒体组消息缓存，格式: {channel_id: {media_group_id: {'messages': [Message], 'last_update_time': timestamp}}}
        self.media_group_cache = {}
        # 媒体组处理锁，防止并发处理同一个媒体组
        self.media_group_locks = {}
        # 媒体组超时时间（秒），超过此时间后媒体组将被视为完整并处理
        self.media_group_timeout = 10
        # 媒体组清理任务
        self.media_group_cleanup_task = None
    
    def add_message_handler(self, handler_func: Callable[[Message], Any]) -> None:
        """
        添加消息处理器
        
        Args:
            handler_func: 消息处理函数，接收Message对象作为参数
        """
        self.message_handlers.append(handler_func)
        logger.info(f"添加了新的消息处理器: {handler_func.__name__}")
    
    async def start_monitoring(self):
        """
        开始监听所有配置的频道
        """
        
        logger.info("开始监听源频道的新消息")
        
        # 解析监听频道ID
        self.monitored_channels = set()
        
        # 解析所有源频道及其目标频道
        channel_pairs = {}
        
        for pair in self.monitor_config.get('monitor_channel_pairs', []):
            source_channel = pair.get('source_channel', '')
            target_channels = pair.get('target_channels', [])
            try:
                channel_id = await self.channel_resolver.get_channel_id(source_channel)
                if channel_id:
                    self.monitored_channels.add(channel_id)
                    source_info_str, (source_title, _) = await self.channel_resolver.format_channel_info(channel_id)
                    logger.info(f"将监听频道: {source_info_str}")
                    
                    # 解析所有目标频道ID
                    valid_target_channels = []
                    for target in target_channels:
                        try:
                            target_id = await self.channel_resolver.get_channel_id(target)
                            target_info_str, (target_title, _) = await self.channel_resolver.format_channel_info(target_id)
                            valid_target_channels.append((target, target_id, target_info_str))
                            logger.info(f"目标频道: {target_info_str}")
                        except Exception as e:
                            logger.error(f"解析目标频道 {target} 失败: {e}", error_type="CHANNEL_RESOLVE", recoverable=True)
                    
                    if valid_target_channels:
                        # 存储源频道-目标频道对应关系
                        channel_pairs[channel_id] = {
                            'source_channel': source_channel,
                            'source_id': channel_id,
                            'source_title': source_title,
                            'target_channels': valid_target_channels,
                            'text_replacements': self.channel_text_replacements.get(source_channel, {}),
                            'remove_captions': self.channel_remove_captions.get(source_channel, False)
                        }
                    else:
                        logger.warning(f"源频道 {source_channel} 没有有效的目标频道，跳过")
                        # 安全地移除频道ID
                        if channel_id in self.monitored_channels:
                            self.monitored_channels.remove(channel_id)
                else:
                    logger.warning(f"无法解析频道: {source_channel}")
            except Exception as e:
                logger.error(f"解析频道 {source_channel} 失败: {str(e)}", error_type="CHANNEL_RESOLVE", recoverable=True)
        
        if not self.monitored_channels:
            logger.error("没有有效的监听频道，监听任务无法启动", error_type="NO_CHANNELS", recoverable=False)
            return
        
        # 设置处理中标志
        self.is_processing = True
        
        try:
            # 注册消息处理函数
            @self.client.on_message(filters.chat(list(self.monitored_channels)))
            async def handle_new_message(client: Client, message: Message):
                if not self.is_processing:
                    return
                
                try:
                    # 获取来源频道信息
                    source_id = message.chat.id
                    
                    # 获取该源频道的配置
                    if source_id not in channel_pairs:
                        logger.warning(f"收到来自未配置目标的频道 {source_id} 的消息，忽略")
                        return
                        
                    pair_config = channel_pairs[source_id]
                    source_info_str, (source_title, source_username) = await self.channel_resolver.format_channel_info(source_id)
                    
                    # 日志记录消息接收
                    logger.info(f"收到来自 {source_info_str} 的新消息 [ID: {message.id}]")
                    
                    # 发射新消息事件给UI
                    if hasattr(self, 'emit'):
                        self.emit("new_message", message.id, source_info_str)
                    
                    # 检查关键词过滤
                    if self.monitor_config.get('keywords', []) and not any(re.search(keyword, message.text or "", re.IGNORECASE) for keyword in self.monitor_config.get('keywords', [])):
                        logger.debug(f"消息 [ID: {message.id}] 不包含任何关键词，忽略")
                        return
                    
                    # 如果包含关键词，记录
                    if self.monitor_config.get('keywords', []):
                        matched_keywords = [keyword for keyword in self.monitor_config.get('keywords', []) if re.search(keyword, message.text or "", re.IGNORECASE)]
                        if matched_keywords:
                            keywords_str = ", ".join(matched_keywords)
                            logger.info(f"消息 [ID: {message.id}] 匹配关键词: {keywords_str}")
                            # 发射关键词匹配事件
                            if hasattr(self, 'emit'):
                                self.emit("keyword_matched", message.id, keywords_str)
                    
                    # 如果消息ID已经处理过，跳过
                    if message.id in self.processed_messages:
                        logger.debug(f"消息 [ID: {message.id}] 已处理过，跳过")
                        return
                        
                    # 将消息ID添加到已处理集合
                    self.processed_messages.add(message.id)
                    
                    # 检查是否为媒体组消息
                    if message.media_group_id:
                        # 处理媒体组消息
                        await self._handle_media_group_message(message, pair_config)
                        return
                    
                    # 处理单条消息
                    # 检查消息是否有文本
                    if not message.text and not message.caption:
                        # 无文本消息，直接转发
                        await self._forward_message(message, pair_config['target_channels'])
                        return
                    
                    # 获取消息文本
                    text = message.text or message.caption
                    
                    # 应用文本替换规则
                    text_replacements = pair_config['text_replacements']
                    remove_captions = pair_config['remove_captions']
                    
                    if text_replacements:
                        modified_text = self._apply_text_replacements(text, text_replacements)
                        if modified_text != text:
                            # 文本已被修改，需要重新发送
                            await self._send_modified_message(message, modified_text, pair_config['target_channels'], remove_captions)
                            return
                    
                    # 检查是否需要移除标题
                    if remove_captions and message.caption:
                        # 需要移除标题，重新发送
                        await self._send_modified_message(message, "", pair_config['target_channels'], True)
                        return
                    
                    # 正常转发消息
                    await self._forward_message(message, pair_config['target_channels'])
                    
                    # 调用所有注册的消息处理器
                    for handler in self.message_handlers:
                        try:
                            # 如果消息处理器是协程函数，异步调用它
                            if asyncio.iscoroutinefunction(handler):
                                await handler(message)
                            else:
                                handler(message)
                                
                        except Exception as handler_error:
                            logger.error(f"消息处理器 {handler.__name__} 处理消息 [ID: {message.id}] 失败: {str(handler_error)}", 
                                          error_type="HANDLER_ERROR", recoverable=True)
                    
                    # 日志记录消息处理完成
                    logger.debug(f"消息 [ID: {message.id}] 处理完成")
                    
                    # 发射消息处理完成事件
                    if hasattr(self, 'emit'):
                        self.emit("message_processed", message.id)
                    
                except Exception as e:
                    logger.error(f"处理消息 [ID: {message.id}] 时发生错误: {str(e)}", error_type="MESSAGE_PROCESS", recoverable=True)
            
            logger.info(f"正在监听 {len(self.monitored_channels)} 个频道的新消息")
            
            # 启动清理任务
            self.cleanup_task = asyncio.create_task(self._cleanup_processed_messages())
            
            # 启动媒体组清理任务
            self.media_group_cleanup_task = asyncio.create_task(self._cleanup_media_groups())
            
            # 等待直到应该停止
            while not self.should_stop:
                await asyncio.sleep(1)
                
            logger.info("监听任务已取消")
            
        except Exception as e:
            logger.error(f"监听任务发生异常: {str(e)}", error_type="MONITOR_TASK", recoverable=False)
        finally:
            # 重置处理中标志
            self.is_processing = False
    
    async def stop_monitoring(self):
        """
        停止监听所有频道
        """
        logger.info("正在停止所有监听任务...")
        
        # 设置停止标志
        self.should_stop = True
        
        # 取消清理任务
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"取消清理任务时异常: {str(e)}", error_type="TASK_CANCEL", recoverable=True)
            
            self.cleanup_task = None
        
        # 取消媒体组清理任务
        if self.media_group_cleanup_task:
            self.media_group_cleanup_task.cancel()
            try:
                await self.media_group_cleanup_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"取消媒体组清理任务时异常: {str(e)}", error_type="TASK_CANCEL", recoverable=True)
            
            self.media_group_cleanup_task = None
        
        # 移除消息处理器
        try:
            # 移除所有注册的处理器
            for handler in self.message_handlers:
                try:
                    self.client.remove_handler(handler)
                except Exception as e:
                    logger.error(f"移除消息处理器时异常: {str(e)}", error_type="HANDLER_REMOVE", recoverable=True)
            
            # 清空处理器列表
            self.message_handlers.clear()
            logger.debug(f"已清理所有消息处理器")
        except Exception as e:
            logger.error(f"清理消息处理器时异常: {str(e)}", error_type="HANDLER_CLEANUP", recoverable=True)
        
        # 清空已处理消息集合
        previous_count = len(self.processed_messages)
        self.processed_messages.clear()
        logger.info(f"已清理 {previous_count} 条已处理消息记录")
        
        # 清空媒体组缓存
        self.media_group_cache.clear()
        self.media_group_locks.clear()
        logger.info("已清理所有媒体组缓存")
        
        logger.info("所有监听任务已停止")
    
    async def _cleanup_processed_messages(self):
        """
        定期清理已处理消息ID集合，防止集合无限增长
        """
        try:
            while not self.should_stop:
                await asyncio.sleep(3600)  # 每小时清理一次
                
                if self.should_stop:
                    break
                    
                now = datetime.now()
                cutoff_time = now - timedelta(days=1)  # 仅保留24小时内的消息
                
                # 由于消息ID集合是简单的int，没有时间信息，这里简单地清空集合
                previous_count = len(self.processed_messages)
                if previous_count > 10000:  # 如果超过10000条消息，则清空
                    self.processed_messages.clear()
                    logger.info(f"已清理 {previous_count} 条已处理消息记录")
        except asyncio.CancelledError:
            # 任务被取消，正常退出
            pass
        except Exception as e:
            logger.error(f"清理已处理消息时异常: {str(e)}", error_type="CLEANUP", recoverable=True)
    
    async def _forward_message(self, message: Message, target_channels: List[Tuple[str, int, str]]):
        """
        转发消息到所有目标频道
        
        Args:
            message: 要转发的消息
            target_channels: 目标频道列表 (channel_id_or_username, resolved_id, display_name)
        """
        if not target_channels:
            logger.warning(f"没有有效的目标频道，跳过转发消息 [ID: {message.id}]")
            return
            
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
                    # 检查是否已取消任务
                    if self.should_stop:
                        logger.info(f"任务已停止，中断转发过程")
                        return
                    
                    # 转发消息
                    await self.client.forward_messages(
                        chat_id=target_id,
                        from_chat_id=source_chat_id,
                        message_ids=source_message_id
                    )
                    
                    success_count += 1
                    logger.info(f"已将消息 {source_message_id} 从 {source_title} 转发到 {target_info}")
                    
                    # 发射转发成功事件
                    if hasattr(self, 'emit'):
                        self.emit("forward", source_message_id, source_chat_id, target_id, True)
                    
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
                        
                        # 发射转发成功事件（使用复制方式）
                        if hasattr(self, 'emit'):
                            self.emit("forward", source_message_id, source_chat_id, target_id, True, modified=True)
                    except Exception as copy_e:
                        failed_count += 1
                        logger.error(f"复制消息失败: {str(copy_e)}", error_type="COPY_MESSAGE", recoverable=True)
                        
                        # 发射转发失败事件（复制失败）
                        if hasattr(self, 'emit'):
                            self.emit("forward", source_message_id, source_chat_id, target_id, False)
                        
                        # 尝试重新发送修改后的消息
                        try:
                            # 获取原始消息的文本或标题
                            text = message.text or message.caption or ""
                            await self._send_modified_message(message, text, [(target, target_id, target_info)])
                            success_count += 1
                            logger.info(f"已使用修改方式将消息 {source_message_id} 从 {source_title} 发送到 {target_info}")
                            
                            # 发射转发成功事件（使用修改方式）
                            if hasattr(self, 'emit'):
                                self.emit("forward", source_message_id, source_chat_id, target_id, True, modified=True)
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
                            
                            # 发射转发成功事件（重试成功）
                            if hasattr(self, 'emit'):
                                self.emit("forward", source_message_id, source_chat_id, target_id, True, modified=True)
                        except Exception as retry_e:
                            failed_count += 1
                            logger.error(f"重试转发失败: {str(retry_e)}", error_type="FORWARD_RETRY", recoverable=True)
                            
                            # 发射转发失败事件
                            if hasattr(self, 'emit'):
                                self.emit("forward", source_message_id, source_chat_id, target_id, False)
                    
                except ChannelPrivate:
                    failed_count += 1
                    logger.error(f"无法访问目标频道 {target_info}，可能是私有频道或未加入", error_type="CHANNEL_PRIVATE", recoverable=True)
                    
                    # 发射转发失败事件
                    if hasattr(self, 'emit'):
                        self.emit("forward", source_message_id, source_chat_id, target_id, False)
                    
                except Exception as e:
                    failed_count += 1
                    logger.error(f"转发消息 {source_message_id} 到 {target_info} 失败: {str(e)}", error_type="FORWARD", recoverable=True)
                    
                    # 发射转发失败事件
                    if hasattr(self, 'emit'):
                        self.emit("forward", source_message_id, source_chat_id, target_id, False)
                
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
                await self._handle_network_error(e)
                
            return False
        
        return True
    
    async def _send_modified_message(self, original_message: Message, new_text: str, target_channels: List[Tuple[str, int, str]], remove_caption: bool = False):
        """
        发送修改后的消息到所有目标频道
        
        Args:
            original_message: 原始消息
            new_text: 新的文本内容
            target_channels: 目标频道列表
            remove_caption: 是否移除标题
        """
        if not target_channels:
            logger.warning(f"没有有效的目标频道，跳过发送修改后的消息 [ID: {original_message.id}]")
            return
            
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
                    # 检查是否已取消任务
                    if self.should_stop:
                        logger.info(f"任务已停止，中断发送过程")
                        return
                    
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
                        
                        # 发射转发成功事件（使用修改方式）
                        if hasattr(self, 'emit'):
                            self.emit("forward", source_message_id, source_chat_id, target_id, True, modified=True)
                    
                except FloodWait as e:
                    logger.warning(f"触发FloodWait，等待 {e.x} 秒后继续")
                    await asyncio.sleep(e.x)
                    # 重试发送不再实现，以简化代码
                    failed_count += 1
                    
                except Exception as e:
                    failed_count += 1
                    logger.error(f"发送修改后的消息到 {target_info} 失败: {str(e)}", error_type="SEND_MODIFIED", recoverable=True)
                    
                    # 发射转发失败事件
                    if hasattr(self, 'emit'):
                        self.emit("forward", source_message_id, source_chat_id, target_id, False)
                
                # 发送间隔
                await asyncio.sleep(0.5)
            
            # 统计结果
            logger.info(f"消息 [ID: {source_message_id}] 修改后发送完成: 成功 {success_count}, 失败 {failed_count}")
            
        except Exception as e:
            logger.error(f"处理修改后消息发送时发生异常: {str(e)}", error_type="MODIFIED_PROCESS", recoverable=True)
            return False
            
        return True
    
    def _apply_text_replacements(self, text: str, text_replacements: Dict[str, str]) -> str:
        """
        应用文本替换规则
        
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

    async def get_message_history(self, channel: str, limit: int = 100) -> List[Message]:
        """
        获取指定频道的历史消息
        
        Args:
            channel: 频道ID或用户名
            limit: 获取消息的数量限制
            
        Returns:
            获取到的消息列表
        """
        logger.info(f"正在获取频道 {channel} 的历史消息")
        
        try:
            channel_id = await self.channel_resolver.resolve_channel(channel)
            if not channel_id:
                logger.error(f"无法解析频道: {channel}", error_type="CHANNEL_RESOLVE", recoverable=False)
                return []
                
            channel_info_str, _ = await self.channel_resolver.format_channel_info(channel_id)
            logger.info(f"获取 {channel_info_str} 的历史消息，限制 {limit} 条")
            
            messages = []
            async for message in self.client.get_chat_history(channel_id, limit=limit):
                if self.should_stop:
                    logger.warning("历史消息获取任务已取消")
                    break
                    
                messages.append(message)
                
                # 每20条消息记录日志
                if len(messages) % 20 == 0:
                    logger.debug(f"已获取 {len(messages)} 条消息")
                    
            logger.info(f"完成获取 {channel_info_str} 的历史消息，共 {len(messages)} 条")
            return messages
            
        except FloodWait as e:
            logger.warning(f"获取历史消息时遇到限制，需要等待 {e.x} 秒")
            await asyncio.sleep(e.x)
            # 递归重试
            return await self.get_message_history(channel, limit)
            
        except Exception as e:
            logger.error(f"获取历史消息失败: {str(e)}", error_type="GET_HISTORY", recoverable=True)
            return []

    async def _handle_network_error(self, error):
        """
        处理网络相关错误
        
        当检测到网络错误时，通知主应用程序立即检查连接状态
        
        Args:
            error: 错误对象
        """
        logger.error(f"检测到网络错误: {type(error).__name__}: {error}")
        
        # 如果有应用程序引用，通知应用程序立即检查连接状态
        if self.app and hasattr(self.app, 'check_connection_status_now'):
            try:
                logger.info("正在触发立即检查连接状态")
                asyncio.create_task(self.app.check_connection_status_now())
            except Exception as e:
                logger.error(f"触发连接状态检查失败: {e}")

    async def _cleanup_media_groups(self):
        """定期检查和处理超时的媒体组"""
        try:
            while not self.should_stop:
                # 每秒检查一次
                await asyncio.sleep(1)
                
                now = time.time()
                channels_to_check = list(self.media_group_cache.keys())
                
                for channel_id in channels_to_check:
                    if channel_id not in self.media_group_cache:
                        continue
                        
                    groups_to_check = list(self.media_group_cache[channel_id].keys())
                    
                    for group_id in groups_to_check:
                        if group_id not in self.media_group_cache.get(channel_id, {}):
                            continue
                            
                        group_data = self.media_group_cache[channel_id][group_id]
                        last_update_time = group_data.get('last_update_time', 0)
                        
                        # 如果媒体组已超时，处理并移除它
                        if now - last_update_time > self.media_group_timeout:
                            try:
                                # 获取锁来处理此媒体组
                                lock_key = f"{channel_id}_{group_id}"
                                if lock_key not in self.media_group_locks:
                                    self.media_group_locks[lock_key] = asyncio.Lock()
                                    
                                async with self.media_group_locks[lock_key]:
                                    # 再次检查媒体组是否仍然存在（可能在获取锁的过程中被其他任务处理）
                                    if (channel_id in self.media_group_cache and 
                                        group_id in self.media_group_cache[channel_id]):
                                        # 获取媒体组和目标频道信息
                                        messages = self.media_group_cache[channel_id][group_id].get('messages', [])
                                        pair_config = self.media_group_cache[channel_id][group_id].get('pair_config')
                                        
                                        if messages and pair_config:
                                            # 处理媒体组消息
                                            logger.info(f"处理超时媒体组: {group_id}, 共有 {len(messages)} 条消息")
                                            await self._process_media_group(messages, pair_config)
                                        
                                        # 从缓存中移除此媒体组
                                        del self.media_group_cache[channel_id][group_id]
                                        
                                        # 如果此频道没有更多媒体组，移除整个频道条目
                                        if not self.media_group_cache[channel_id]:
                                            del self.media_group_cache[channel_id]
                                            
                            except Exception as e:
                                logger.error(f"处理超时媒体组 {group_id} 时出错: {str(e)}", error_type="MEDIA_GROUP_TIMEOUT", recoverable=True)
                                # 尽管出错，仍然尝试从缓存中移除
                                try:
                                    if channel_id in self.media_group_cache and group_id in self.media_group_cache[channel_id]:
                                        del self.media_group_cache[channel_id][group_id]
                                except Exception:
                                    pass
                                
        except asyncio.CancelledError:
            logger.info("媒体组清理任务已取消")
        except Exception as e:
            logger.error(f"媒体组清理任务异常: {str(e)}", error_type="MEDIA_GROUP_CLEANUP", recoverable=True)

    async def _handle_media_group_message(self, message: Message, pair_config: dict):
        """处理媒体组消息
        
        Args:
            message: 媒体组中的一条消息
            pair_config: 频道对配置
        """
        channel_id = message.chat.id
        media_group_id = message.media_group_id
        
        if not media_group_id:
            logger.warning(f"消息 [ID: {message.id}] 不是媒体组消息")
            return
            
        # 确保频道存在于缓存中
        if channel_id not in self.media_group_cache:
            self.media_group_cache[channel_id] = {}
            
        # 获取锁
        lock_key = f"{channel_id}_{media_group_id}"
        if lock_key not in self.media_group_locks:
            self.media_group_locks[lock_key] = asyncio.Lock()
            
        async with self.media_group_locks[lock_key]:
            # 如果媒体组不存在，创建它
            if media_group_id not in self.media_group_cache[channel_id]:
                self.media_group_cache[channel_id][media_group_id] = {
                    'messages': [],
                    'last_update_time': time.time(),
                    'pair_config': pair_config
                }
                
            # 添加消息到媒体组
            group_data = self.media_group_cache[channel_id][media_group_id]
            messages = group_data['messages']
            
            # 检查消息是否已经在缓存中
            if any(m.id == message.id for m in messages):
                logger.debug(f"媒体组消息 [ID: {message.id}] 已在缓存中，跳过")
                return
                
            # 添加消息并更新时间戳
            messages.append(message)
            group_data['last_update_time'] = time.time()
            
            # 排序媒体组消息（按照ID）
            messages.sort(key=lambda m: m.id)
            
            logger.debug(f"添加消息 [ID: {message.id}] 到媒体组 {media_group_id}, 现有 {len(messages)} 条消息")
            
            # 如果我们接收到了整个媒体组（根据media_group_count），处理它
            if hasattr(message, 'media_group_count') and len(messages) >= message.media_group_count:
                logger.info(f"媒体组 {media_group_id} 已完整接收 ({len(messages)}/{message.media_group_count}), 开始处理")
                await self._process_media_group(messages, pair_config)
                
                # 从缓存中删除此媒体组
                del self.media_group_cache[channel_id][media_group_id]
                
                # 如果此频道没有更多媒体组，移除整个频道条目
                if not self.media_group_cache[channel_id]:
                    del self.media_group_cache[channel_id]
    
    async def _process_media_group(self, messages: List[Message], pair_config: dict):
        """处理完整的媒体组消息
        
        Args:
            messages: 媒体组消息列表
            pair_config: 频道对配置
        """
        if not messages:
            logger.warning("尝试处理空的媒体组")
            return
            
        # 排序消息，确保顺序正确
        messages.sort(key=lambda m: m.id)
        
        # 获取源和目标信息
        source_chat = messages[0].chat
        source_chat_id = source_chat.id
        media_group_id = messages[0].media_group_id
        
        try:
            source_title = source_chat.title
        except:
            source_title = str(source_chat_id)
            
        target_channels = pair_config['target_channels']
        text_replacements = pair_config['text_replacements']
        remove_captions = pair_config['remove_captions']
        
        if not target_channels:
            logger.warning(f"没有有效的目标频道，跳过媒体组 {media_group_id}")
            return
            
        logger.info(f"开始处理媒体组 {media_group_id} 从 {source_title} 到 {len(target_channels)} 个目标频道")
        
        # 获取第一条消息的标题（如果所有消息共用一个标题，通常是这样）
        caption = ""
        for msg in messages:
            if msg.caption:
                caption = msg.caption
                break
                
        # 检查是否需要修改标题或者应用文本替换
        modified_captions = False
        if text_replacements or remove_captions:
            if caption and text_replacements:
                # 应用文本替换规则
                modified_caption = self._apply_text_replacements(caption, text_replacements)
                if modified_caption != caption:
                    modified_captions = True
                    # 使用修改后的标题
                    caption = modified_caption
                    
            # 如果设置了移除标题
            if remove_captions:
                caption = ""
                modified_captions = True
        
        # 如果需要修改标题，使用send_media_group重新发送媒体组
        if modified_captions:
            logger.info(f"媒体组 {media_group_id} 需要修改标题，将使用修改后的媒体组发送")
            await self._send_modified_media_group(messages, caption, target_channels)
            return
        
        # 如果不需要修改标题，直接尝试转发媒体组（将自动处理转发限制情况）
        await self._forward_media_group(messages, target_channels)
        
    async def _forward_media_group(self, messages: List[Message], target_channels: List[Tuple[str, int, str]]):
        """转发媒体组消息
        
        Args:
            messages: 媒体组消息列表
            target_channels: 目标频道列表
        """
        if not messages or not target_channels:
            return
            
        source_chat = messages[0].chat
        source_chat_id = source_chat.id
        media_group_id = messages[0].media_group_id
        
        try:
            source_title = source_chat.title
        except:
            source_title = str(source_chat_id)
            
        message_ids = [msg.id for msg in messages]
        first_message_id = message_ids[0]
        
        logger.info(f"转发媒体组 {media_group_id} (IDs: {message_ids}) 从 {source_title} 到 {len(target_channels)} 个目标频道")
        
        success_count = 0
        failed_count = 0
        
        # 创建并发任务列表
        tasks = []
        for target, target_id, target_info in target_channels:
            if self.should_stop:
                logger.info(f"任务已停止，中断转发过程")
                break
                
            # 为每个目标频道创建一个异步任务
            tasks.append(self._forward_media_group_to_target(
                source_chat_id, target_id, target_info, 
                first_message_id, message_ids, media_group_id, source_title
            ))
        
        # 并发执行所有转发任务
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 统计结果
            for result in results:
                if isinstance(result, Exception):
                    failed_count += 1
                    logger.error(f"转发媒体组时发生异常: {str(result)}", error_type="FORWARD_MEDIA_GROUP", recoverable=True)
                elif result is True:
                    success_count += 1
                else:
                    failed_count += 1
        
        # 统计结果
        logger.info(f"媒体组 {media_group_id} 转发完成: 成功 {success_count}, 失败 {failed_count}")
        return success_count > 0
        
    async def _forward_media_group_to_target(self, source_chat_id: int, target_id: int, target_info: str,
                                           first_message_id: int, message_ids: List[int], 
                                           media_group_id: str, source_title: str) -> bool:
        """转发媒体组消息到单个目标频道
        
        Args:
            source_chat_id: 源频道ID
            target_id: 目标频道ID
            target_info: 目标频道信息字符串
            first_message_id: 媒体组中第一条消息ID
            message_ids: 所有消息ID列表
            media_group_id: 媒体组ID
            source_title: 源频道标题
            
        Returns:
            bool: 是否成功转发
        """
        try:
            # 优先尝试使用copy_media_group转发整个媒体组
            try:
                await self.client.copy_media_group(
                    chat_id=target_id,
                    from_chat_id=source_chat_id,
                    message_id=first_message_id
                )
                logger.info(f"已将媒体组 {media_group_id} 从 {source_title} 复制到 {target_info}")
                return True
            except ChatForwardsRestricted:
                # 如果复制受限，记录日志并继续尝试其他方式
                logger.warning(f"目标频道 {target_info} 禁止复制消息，尝试逐条转发")
                
                # 尝试单独转发媒体组中的每条消息
                all_succeeded = True
                for msg_id in message_ids:
                    try:
                        await self.client.forward_messages(
                            chat_id=target_id,
                            from_chat_id=source_chat_id,
                            message_ids=msg_id
                        )
                        # 减少延迟，但保留最小间隔避免限流
                        await asyncio.sleep(0.1)
                    except ChatForwardsRestricted:
                        all_succeeded = False
                        logger.warning(f"无法转发媒体组消息 ID:{msg_id} 到 {target_info}，将尝试重新上传")
                        break
                    except FloodWait as e:
                        await asyncio.sleep(e.x)
                        try:
                            await self.client.forward_messages(
                                chat_id=target_id,
                                from_chat_id=source_chat_id,
                                message_ids=msg_id
                            )
                        except Exception:
                            all_succeeded = False
                            break
                    except Exception:
                        all_succeeded = False
                        break
                        
                if all_succeeded:
                    logger.info(f"已将媒体组 {media_group_id} 从 {source_title} 逐条转发到 {target_info}")
                    return True
                
                # 如果转发和复制都失败，尝试重新上传
                logger.info(f"尝试重新上传媒体组 {media_group_id} 到 {target_info}")
                messages = []
                for msg_id in message_ids:
                    try:
                        msg = await self.client.get_messages(source_chat_id, msg_id)
                        if msg:
                            messages.append(msg)
                    except Exception as e:
                        logger.error(f"获取源消息失败: {str(e)}")
                
                if messages:
                    await self._send_modified_media_group(
                        messages, 
                        messages[0].caption or "", 
                        [(None, target_id, target_info)]
                    )
                    logger.info(f"成功重新上传媒体组 {media_group_id} 到 {target_info}")
                    return True
                    
            except FloodWait as e:
                logger.warning(f"触发FloodWait，等待 {e.x} 秒后继续")
                await asyncio.sleep(e.x)
                
                # 重试一次
                await self.client.copy_media_group(
                    chat_id=target_id,
                    from_chat_id=source_chat_id,
                    message_id=first_message_id
                )
                logger.info(f"重试成功：已将媒体组 {media_group_id} 从 {source_title} 发送到 {target_info}")
                return True
                
            except Exception as e:
                # 所有方法都失败，记录错误并返回失败
                logger.error(f"转发媒体组 {media_group_id} 到 {target_info} 失败: {str(e)}", error_type="FORWARD", recoverable=True)
                return False
            
        except Exception as e:
            logger.error(f"处理媒体组转发到 {target_info} 时出错: {str(e)}", error_type="FORWARD_MEDIA_GROUP", recoverable=True)
            return False
    
    async def _send_modified_media_group(self, messages: List[Message], caption: str, target_channels: List[Tuple[str, int, str]]):
        """发送修改后的媒体组消息
        
        Args:
            messages: 媒体组消息列表
            caption: 修改后的标题
            target_channels: 目标频道列表
        """
        if not messages or not target_channels:
            return
            
        source_chat = messages[0].chat
        source_chat_id = source_chat.id
        media_group_id = messages[0].media_group_id
        
        try:
            source_title = source_chat.title
        except:
            source_title = str(source_chat_id)
            
        logger.info(f"发送修改后的媒体组 {media_group_id} 从 {source_title} 到 {len(target_channels)} 个目标频道")
        
        # 准备媒体组 - 使用Pyrogram的媒体类型对象
        media_group = []
        for i, msg in enumerate(messages):
            # 只给第一个媒体添加标题
            current_caption = caption if i == 0 and caption else ""
            
            if msg.photo:
                media_group.append(
                    InputMediaPhoto(
                        media=msg.photo.file_id,
                        caption=current_caption
                    )
                )
            elif msg.video:
                media_group.append(
                    InputMediaVideo(
                        media=msg.video.file_id,
                        caption=current_caption,
                        supports_streaming=True
                    )
                )
            elif msg.document:
                media_group.append(
                    InputMediaDocument(
                        media=msg.document.file_id,
                        caption=current_caption
                    )
                )
            elif msg.audio:
                media_group.append(
                    InputMediaAudio(
                        media=msg.audio.file_id,
                        caption=current_caption
                    )
                )
            elif msg.animation:
                media_group.append(
                    InputMediaAnimation(
                        media=msg.animation.file_id,
                        caption=current_caption
                    )
                )
        
        if not media_group:
            logger.warning(f"无法为媒体组 {media_group_id} 准备媒体内容，跳过发送")
            return
            
        success_count = 0
        failed_count = 0
        
        # 创建并发任务列表
        tasks = []
        for target, target_id, target_info in target_channels:
            if self.should_stop:
                logger.info(f"任务已停止，中断发送过程")
                break
                
            # 为每个目标频道创建一个异步任务
            tasks.append(self._send_media_group_to_target(
                target_id, target_info, media_group, media_group_id, source_title
            ))
        
        # 并发执行所有发送任务
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 统计结果
            for result in results:
                if isinstance(result, Exception):
                    failed_count += 1
                    logger.error(f"发送媒体组时发生异常: {str(result)}", error_type="SEND_MEDIA_GROUP", recoverable=True)
                elif result is True:
                    success_count += 1
                else:
                    failed_count += 1
        
        # 统计结果
        logger.info(f"修改后的媒体组 {media_group_id} 发送完成: 成功 {success_count}, 失败 {failed_count}")
        
    async def _send_media_group_to_target(self, target_id: int, target_info: str, 
                                        media_group: List, media_group_id: str, 
                                        source_title: str) -> bool:
        """发送媒体组到单个目标频道
        
        Args:
            target_id: 目标频道ID
            target_info: 目标频道信息字符串
            media_group: 准备好的媒体组
            media_group_id: 媒体组ID
            source_title: 源频道标题
            
        Returns:
            bool: 是否成功发送
        """
        try:
            # 发送媒体组
            await self.client.send_media_group(
                chat_id=target_id,
                media=media_group
            )
            
            logger.info(f"已将修改后的媒体组 {media_group_id} 从 {source_title} 发送到 {target_info}")
            return True
                
        except FloodWait as e:
            logger.warning(f"触发FloodWait，等待 {e.x} 秒后继续")
            try:
                await asyncio.sleep(e.x)
                # 重试发送
                await self.client.send_media_group(
                    chat_id=target_id,
                    media=media_group
                )
                logger.info(f"重试成功：已将修改后的媒体组 {media_group_id} 从 {source_title} 发送到 {target_info}")
                return True
            except Exception as retry_e:
                logger.error(f"重试发送媒体组失败: {str(retry_e)}", error_type="SEND_RETRY", recoverable=True)
                return False
        
        except Exception as e:
            logger.error(f"发送修改后的媒体组 {media_group_id} 到 {target_info} 失败: {str(e)}", error_type="SEND_MODIFIED", recoverable=True)
            return False
