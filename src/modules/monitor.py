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
from pyrogram.types import Message
from pyrogram.errors import FloodWait, ChatForwardsRestricted, ChannelPrivate
from pyrogram.handlers import MessageHandler

from src.utils.config_manager import MonitorChannelPair
from src.utils.ui_config_manager import UIConfigManager
from src.utils.config_utils import convert_ui_config_to_dict
from src.utils.channel_resolver import ChannelResolver
from src.utils.logger import get_logger
from src.utils.events import EventEmitter
from src.utils.controls import CancelToken, PauseToken, TaskContext
from src.utils.logger_event_adapter import LoggerEventAdapter
from src.utils.history_manager import HistoryManager

# 仅用于内部调试，不再用于UI输出
_logger = get_logger()

class Monitor(EventEmitter):
    """
    监听模块，监听源频道的新消息，并实时转发到目标频道
    """
    
    def __init__(self, client: Client, ui_config_manager: UIConfigManager, channel_resolver: ChannelResolver, history_manager: Optional[HistoryManager] = None):
        """
        初始化监听模块
        
        Args:
            client: Pyrogram客户端实例
            ui_config_manager: UI配置管理器实例
            channel_resolver: 频道解析器实例
            history_manager: 历史记录管理器实例，可选
        """
        # 初始化事件发射器
        super().__init__()
        
        self.client = client
        self.ui_config_manager = ui_config_manager
        self.channel_resolver = channel_resolver
        self.history_manager = history_manager
        
        # 创建日志事件适配器
        self.log = LoggerEventAdapter(self)
        
        # 获取UI配置并转换为字典
        ui_config = self.ui_config_manager.get_ui_config()
        self.config = convert_ui_config_to_dict(ui_config)
        
        # 获取监听配置
        self.monitor_config = self.config.get('MONITOR', {})
        
        # 控制变量
        self.should_stop = False
        self.monitor_tasks = []
        self.task_context = None
        
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
                self.log.debug(f"频道 {source_channel} 已加载 {len(text_replacements)} 条文本替换规则")
        
        self.log.info(f"总共加载 {total_text_filter_rules} 条文本替换规则")
        
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
    
    def add_message_handler(self, handler_func: Callable[[Message], Any]) -> None:
        """
        添加消息处理器
        
        Args:
            handler_func: 消息处理函数，接收Message对象作为参数
        """
        self.message_handlers.append(handler_func)
        self.log.info(f"添加了新的消息处理器: {handler_func.__name__}")
    
    async def start_monitoring(self, task_context: Optional[TaskContext] = None):
        """
        开始监听所有配置的频道
        
        Args:
            task_context: 任务上下文，用于控制任务执行
        """
        # 初始化任务上下文
        self.task_context = task_context or TaskContext()
        
        self.log.status("开始监听源频道的新消息")
        
        # 解析监听频道ID
        self.monitored_channels = set()
        
        for pair in self.monitor_config.get('monitor_channel_pairs', []):
            source_channel = pair.get('source_channel', '')
            try:
                channel_id = await self.channel_resolver.get_channel_id(source_channel)
                if channel_id:
                    self.monitored_channels.add(channel_id)
                    source_info_str, (source_title, _) = await self.channel_resolver.format_channel_info(channel_id)
                    self.log.info(f"将监听频道: {source_info_str}")
                else:
                    self.log.warning(f"无法解析频道: {source_channel}")
            except Exception as e:
                self.log.error(f"解析频道 {source_channel} 失败: {str(e)}", error_type="CHANNEL_RESOLVE", recoverable=True)
        
        if not self.monitored_channels:
            self.log.error("没有有效的监听频道，监听任务无法启动", error_type="NO_CHANNELS", recoverable=False)
            return
        
        # 设置处理中标志
        self.is_processing = True
        
        try:
            # 注册消息处理函数
            @self.client.on_message(filters.chat(list(self.monitored_channels)) & ~filters.edited)
            async def handle_new_message(client: Client, message: Message):
                if not self.is_processing or self.task_context.cancel_token.is_cancelled:
                    return
                
                try:
                    # 获取来源频道信息
                    source_id = message.chat.id
                    source_info_str, (source_title, source_username) = await self.channel_resolver.format_channel_info(source_id)
                    
                    # 发送消息接收事件
                    self.log.info(f"收到来自 {source_info_str} 的新消息 [ID: {message.id}]")
                    self.emit("message_received", message.id, source_info_str)
                    
                    # 检查关键词过滤
                    if self.monitor_config.get('keywords', []) and not any(re.search(keyword, message.text or "", re.IGNORECASE) for keyword in self.monitor_config.get('keywords', [])):
                        self.log.debug(f"消息 [ID: {message.id}] 不包含任何关键词，忽略")
                        return
                    
                    # 如果包含关键词，记录并发送事件
                    if self.monitor_config.get('keywords', []):
                        matched_keywords = [keyword for keyword in self.monitor_config.get('keywords', []) if re.search(keyword, message.text or "", re.IGNORECASE)]
                        if matched_keywords:
                            keywords_str = ", ".join(matched_keywords)
                            self.log.info(f"消息 [ID: {message.id}] 匹配关键词: {keywords_str}")
                            self.emit("keyword_matched", message.id, keywords_str)
                    
                    # 调用所有注册的消息处理器
                    for handler in self.message_handlers:
                        if self.task_context.cancel_token.is_cancelled:
                            break
                            
                        try:
                            # 如果消息处理器是协程函数，异步调用它
                            if asyncio.iscoroutinefunction(handler):
                                await handler(message)
                            else:
                                handler(message)
                                
                        except Exception as handler_error:
                            self.log.error(f"消息处理器 {handler.__name__} 处理消息 [ID: {message.id}] 失败: {str(handler_error)}", 
                                          error_type="HANDLER_ERROR", recoverable=True)
                    
                    # 发送消息处理完成事件
                    self.log.debug(f"消息 [ID: {message.id}] 处理完成")
                    self.emit("message_processed", message.id)
                    
                except Exception as e:
                    self.log.error(f"处理消息 [ID: {message.id}] 时发生错误: {str(e)}", error_type="MESSAGE_PROCESS", recoverable=True)
            
            self.log.status(f"正在监听 {len(self.monitored_channels)} 个频道的新消息")
            
            # 等待取消信号
            while not self.task_context.cancel_token.is_cancelled:
                await asyncio.sleep(1)
                
            self.log.status("监听任务已取消")
            
        except Exception as e:
            self.log.error(f"监听任务发生异常: {str(e)}", error_type="MONITOR_TASK", recoverable=False)
        finally:
            # 重置处理中标志
            self.is_processing = False
    
    async def stop_monitoring(self):
        """
        停止监听所有频道
        """
        self.log.status("正在停止所有监听任务...")
        
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
                self.log.error(f"取消清理任务时异常: {str(e)}", error_type="TASK_CANCEL", recoverable=True)
            
            self.cleanup_task = None
        
        # 移除所有消息处理器
        for source_id in self.monitored_channels:
            try:
                self.client.remove_handler(self.message_handlers[source_id])
                self.log.debug(f"已移除频道 {source_id} 的消息处理器")
            except Exception as e:
                self.log.error(f"移除频道 {source_id} 的消息处理器时异常: {str(e)}", error_type="HANDLER_REMOVE", recoverable=True)
        
        # 清空处理器字典
        self.message_handlers.clear()
        
        # 清空已处理消息集合
        previous_count = len(self.processed_messages)
        self.processed_messages.clear()
        self.log.info(f"已清理 {previous_count} 条已处理消息记录")
        
        self.log.status("所有监听任务已停止")
    
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
                    self.log.info(f"已清理 {previous_count} 条已处理消息记录")
        except asyncio.CancelledError:
            # 任务被取消，正常退出
            pass
        except Exception as e:
            self.log.error(f"清理已处理消息时异常: {str(e)}", error_type="CLEANUP", recoverable=True)
    
    async def _monitor_channel(self, channel_pair: MonitorChannelPair):
        """
        监听单个频道的消息
        
        Args:
            channel_pair: 频道对配置
        """
        source_channel = channel_pair.source_channel
        target_channels = channel_pair.target_channels
        
        self.log.status(f"开始监听源频道: {source_channel}")
        
        try:
            # 解析源频道ID
            source_id = await self.channel_resolver.get_channel_id(source_channel)
            source_info_str, (source_title, _) = await self.channel_resolver.format_channel_info(source_id)
            
            self.log.info(f"源频道: {source_info_str}")
            
            # 解析所有目标频道ID
            valid_target_channels = []
            
            for target in target_channels:
                try:
                    # 检查是否已取消任务
                    if self.task_context and self.task_context.cancel_token.is_cancelled:
                        self.log.debug(f"解析目标频道时任务已取消")
                        return
                    
                    # 等待暂停恢复
                    if self.task_context:
                        await self.task_context.wait_if_paused()
                    
                    target_id = await self.channel_resolver.get_channel_id(target)
                    target_info_str, (target_title, _) = await self.channel_resolver.format_channel_info(target_id)
                    valid_target_channels.append((target, target_id, target_info_str))
                    self.log.info(f"目标频道: {target_info_str}")
                except Exception as e:
                    self.log.error(f"解析目标频道 {target} 失败: {e}", error_type="CHANNEL_RESOLVE", recoverable=True)
            
            if not valid_target_channels:
                self.log.warning(f"源频道 {source_channel} 没有有效的目标频道，停止监听")
                return
            
            # 检查源频道是否允许转发
            self.log.status(f"检查源频道 {source_title} 转发权限...")
            
            source_can_forward = await self.channel_resolver.check_forward_permission(source_id)
            
            self.log.info(f"源频道 {source_title} 允许转发: {source_can_forward}")
            
            # 如果源频道禁止转发，直接报错并跳过
            if not source_can_forward:
                self.log.error(f"源频道 {source_title} 禁止转发消息，跳过此频道的监听", error_type="CHANNEL_FORBID_FORWARD", recoverable=False)
                return
            
            # 获取这个源频道的文本替换规则
            text_replacements = self.channel_text_replacements.get(source_channel, {})
            # 获取这个源频道的移除标题设置
            remove_captions = self.channel_remove_captions.get(source_channel, False)
            
            if text_replacements:
                self.log.info(f"源频道 {source_title} 启用了 {len(text_replacements)} 条文本替换规则")
            
            if remove_captions:
                self.log.info(f"源频道 {source_title} 启用了移除标题功能")
            
            # 定义消息处理函数
            async def message_handler(client, message):
                # 检查是否已取消任务
                if self.should_stop or (self.task_context and self.task_context.cancel_token.is_cancelled):
                    return
                
                # 如果消息ID已经处理过，跳过
                if message.id in self.processed_messages:
                    return
                    
                # 将消息ID添加到已处理集合
                self.processed_messages.add(message.id)
                
                # 检查消息是否有文本
                if not message.text and not message.caption:
                    # 无文本消息，直接转发
                    await self._forward_message(message, valid_target_channels)
                    return
                
                # 获取消息文本
                text = message.text or message.caption
                
                # 应用文本替换规则
                if text_replacements:
                    modified_text = self._apply_text_replacements(text, text_replacements)
                    if modified_text != text:
                        # 文本已被修改，需要重新发送
                        await self._send_modified_message(message, modified_text, valid_target_channels, remove_captions)
                        return
                
                # 检查是否需要移除标题
                if remove_captions and message.caption:
                    # 需要移除标题，重新发送
                    await self._send_modified_message(message, "", valid_target_channels, True)
                    return
                
                # 正常转发消息
                await self._forward_message(message, valid_target_channels)
            
            # 注册消息处理器
            handler = self.client.add_handler(
                MessageHandler(
                    message_handler,
                    filters.chat(source_id)
                )
            )
            
            # 存储处理器引用以便后续移除
            self.message_handlers.append(handler)
            
            self.log.status(f"成功注册源频道 {source_title} 的消息处理器，开始监听新消息")
            
            # 等待直到应该停止
            while not self.should_stop:
                if self.task_context and self.task_context.cancel_token.is_cancelled:
                    self.log.status(f"监听源频道 {source_title} 的任务已取消")
                    break
                
                # 等待暂停恢复
                if self.task_context:
                    await self.task_context.wait_if_paused()
                
                await asyncio.sleep(1)
            
            # 停止监听
            try:
                # 尝试移除消息处理器
                self.message_handlers.remove(handler)
                self.log.debug(f"已清理频道 {source_title} 的消息处理器")
            except Exception as e:
                self.log.error(f"清理频道 {source_title} 的消息处理器时异常: {str(e)}", error_type="HANDLER_REMOVE", recoverable=True)
                
        except Exception as e:
            self.log.error(f"监听源频道 {source_channel} 失败: {str(e)}", error_type="MONITOR_CHANNEL", recoverable=False)
            import traceback
            error_details = traceback.format_exc()
            self.log.error(f"详细错误: {error_details}", error_type="MONITOR_CHANNEL", recoverable=False, details=error_details)
            
            # 尝试清理注册的处理器
            if handler in self.message_handlers:
                self.message_handlers.remove(handler)
    
    async def _forward_message(self, message: Message, target_channels: List[Tuple[str, int, str]]):
        """
        转发消息到所有目标频道
        
        Args:
            message: 要转发的消息
            target_channels: 目标频道列表 (channel_id_or_username, resolved_id, display_name)
        """
        try:
            source_chat = message.chat
            source_chat_id = source_chat.id
            source_message_id = message.id
            
            # 尝试获取频道信息
            try:
                source_title = source_chat.title
            except:
                source_title = str(source_chat_id)
            
            # 转发到所有目标频道
            for target, target_id, target_info in target_channels:
                try:
                    # 检查是否已取消任务
                    if self.should_stop or (self.task_context and self.task_context.cancel_token.is_cancelled):
                        return
                    
                    # 等待暂停恢复
                    if self.task_context:
                        await self.task_context.wait_if_paused()
                    
                    # 转发消息
                    await self.client.forward_messages(
                        chat_id=target_id,
                        from_chat_id=source_chat_id,
                        message_ids=source_message_id
                    )
                    
                    self.log.debug(f"已将消息 {source_message_id} 从 {source_title} 转发到 {target_info}")
                    self.emit("forward", source_message_id, source_chat_id, target_id, True)
                    
                except FloodWait as e:
                    self.log.warning(f"触发FloodWait，等待 {e.x} 秒后继续")
                    await asyncio.sleep(e.x)
                    # 重试转发
                    try:
                        await self.client.forward_messages(
                            chat_id=target_id,
                            from_chat_id=source_chat_id,
                            message_ids=source_message_id
                        )
                        self.log.debug(f"重试成功：已将消息 {source_message_id} 从 {source_title} 转发到 {target_info}")
                        self.emit("forward", source_message_id, source_chat_id, target_id, True)
                    except Exception as retry_e:
                        self.log.error(f"重试转发失败: {str(retry_e)}", error_type="FORWARD_RETRY", recoverable=True)
                        self.emit("forward", source_message_id, source_chat_id, target_id, False)
                        
                except ChatForwardsRestricted:
                    self.log.error(f"目标频道 {target_info} 禁止转发消息", error_type="FORWARD_RESTRICTED", recoverable=True)
                    self.emit("forward", source_message_id, source_chat_id, target_id, False)
                    
                except ChannelPrivate:
                    self.log.error(f"无法访问目标频道 {target_info}，可能是私有频道或未加入", error_type="CHANNEL_PRIVATE", recoverable=True)
                    self.emit("forward", source_message_id, source_chat_id, target_id, False)
                    
                except Exception as e:
                    self.log.error(f"转发消息 {source_message_id} 到 {target_info} 失败: {str(e)}", error_type="FORWARD", recoverable=True)
                    self.emit("forward", source_message_id, source_chat_id, target_id, False)
                
                # 转发间隔
                await asyncio.sleep(0.5)
                
        except Exception as e:
            self.log.error(f"处理消息转发时发生异常: {str(e)}", error_type="FORWARD_PROCESS", recoverable=True)
    
    async def _send_modified_message(self, original_message: Message, new_text: str, target_channels: List[Tuple[str, int, str]], remove_caption: bool = False):
        """
        发送修改后的消息到所有目标频道
        
        Args:
            original_message: 原始消息
            new_text: 新的文本内容
            target_channels: 目标频道列表
            remove_caption: 是否移除标题
        """
        try:
            source_chat = original_message.chat
            source_chat_id = source_chat.id
            source_message_id = original_message.id
            
            # 尝试获取频道信息
            try:
                source_title = source_chat.title
            except:
                source_title = str(source_chat_id)
            
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
            else:
                # 使用新文本
                caption_to_use = new_text
            
            # 发送到所有目标频道
            for target, target_id, target_info in target_channels:
                try:
                    # 检查是否已取消任务
                    if self.should_stop or (self.task_context and self.task_context.cancel_token.is_cancelled):
                        return
                    
                    # 等待暂停恢复
                    if self.task_context:
                        await self.task_context.wait_if_paused()
                    
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
                        self.log.debug(f"已将修改后的消息从 {source_title} 发送到 {target_info}")
                        self.emit("forward", source_message_id, source_chat_id, target_id, True, modified=True)
                    
                except FloodWait as e:
                    self.log.warning(f"触发FloodWait，等待 {e.x} 秒后继续")
                    await asyncio.sleep(e.x)
                    # 重试发送不再实现，以简化代码
                    
                except Exception as e:
                    self.log.error(f"发送修改后的消息到 {target_info} 失败: {str(e)}", error_type="SEND_MODIFIED", recoverable=True)
                    self.emit("forward", source_message_id, source_chat_id, target_id, False, modified=True)
                
                # 发送间隔
                await asyncio.sleep(0.5)
                
        except Exception as e:
            self.log.error(f"处理修改后消息发送时发生异常: {str(e)}", error_type="MODIFIED_PROCESS", recoverable=True)
    
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
                    self.log.debug(f"文本替换: '{original}' -> '{replacement}'")
        
        if replacement_made:
            self.log.info(f"已应用文本替换，原文本: '{text}'，新文本: '{modified_text}'")
            self.emit("text_replaced", text, modified_text, replacements)
        
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
        self.log.status(f"正在获取频道 {channel} 的历史消息")
        
        try:
            channel_id = await self.channel_resolver.resolve_channel(channel)
            if not channel_id:
                self.log.error(f"无法解析频道: {channel}", error_type="CHANNEL_RESOLVE", recoverable=False)
                return []
                
            channel_info_str, _ = await self.channel_resolver.format_channel_info(channel_id)
            self.log.info(f"获取 {channel_info_str} 的历史消息，限制 {limit} 条")
            
            messages = []
            async for message in self.client.get_chat_history(channel_id, limit=limit):
                if self.task_context.cancel_token.is_cancelled:
                    self.log.warning("历史消息获取任务已取消")
                    break
                    
                messages.append(message)
                
                # 每20条消息发出一次进度事件
                if len(messages) % 20 == 0:
                    self.log.debug(f"已获取 {len(messages)} 条消息")
                    self.emit("history_progress", len(messages), limit)
                    
            self.log.status(f"完成获取 {channel_info_str} 的历史消息，共 {len(messages)} 条")
            self.emit("history_complete", len(messages))
            return messages
            
        except FloodWait as e:
            self.log.warning(f"获取历史消息时遇到限制，需要等待 {e.x} 秒")
            await asyncio.sleep(e.x)
            # 递归重试
            return await self.get_message_history(channel, limit)
            
        except Exception as e:
            self.log.error(f"获取历史消息失败: {str(e)}", error_type="GET_HISTORY", recoverable=True)
            return []
