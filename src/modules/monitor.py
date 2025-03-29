"""
监听模块，负责监听源频道新消息并转发到目标频道
"""

import asyncio
import threading
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Union, Set
import re

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait, ChatForwardsRestricted, ChannelPrivate
from pyrogram.handlers import MessageHandler

from src.utils.config_manager import ConfigManager, MonitorChannelPair
from src.utils.channel_resolver import ChannelResolver
from src.utils.logger import get_logger
from src.utils.events import EventEmitter
from src.utils.controls import CancelToken, PauseToken, TaskContext

logger = get_logger()


class Monitor(EventEmitter):
    """
    监听模块，监听源频道的新消息，并实时转发到目标频道
    """
    
    def __init__(self, client: Client, config_manager: ConfigManager, channel_resolver: ChannelResolver):
        """
        初始化监听模块
        
        Args:
            client: Pyrogram客户端实例
            config_manager: 配置管理器实例
            channel_resolver: 频道解析器实例
        """
        # 初始化事件发射器
        super().__init__()
        
        self.client = client
        self.config_manager = config_manager
        self.channel_resolver = channel_resolver
        
        # 获取监听配置
        self.monitor_config = self.config_manager.get_monitor_config()
        
        # 存储监听任务
        self.monitor_tasks = []
        
        # 停止标志
        self.should_stop = False
        
        # 任务控制
        self.task_context = None
        
        # 计算监听截止时间
        self.end_time = None
        if self.monitor_config.duration:
            try:
                end_date = datetime.strptime(self.monitor_config.duration, "%Y-%m-%d")
                self.end_time = end_date
                logger.info(f"监听将在 {self.end_time} 结束")
            except ValueError:
                logger.error(f"监听时间格式错误: {self.monitor_config.duration}，应为 'yyyy-mm-dd'")
        
        # 每个频道对的文本替换映射
        self.channel_text_replacements = {}
        # 每个频道对的移除标题设置
        self.channel_remove_captions = {}
        
        # 加载每个频道对的配置
        total_text_filter_rules = 0
        for pair in self.monitor_config.monitor_channel_pairs:
            source_channel = pair.source_channel
            
            # 加载文本替换规则
            text_replacements = {}
            if pair.text_filter:
                for item in pair.text_filter:
                    # 只有当original_text不为空时才添加替换规则
                    if item.original_text:
                        text_replacements[item.original_text] = item.target_text
                        total_text_filter_rules += 1
            
            # 存储每个源频道的配置
            self.channel_text_replacements[source_channel] = text_replacements
            self.channel_remove_captions[source_channel] = pair.remove_captions
            
            if text_replacements:
                logger.debug(f"频道 {source_channel} 已加载 {len(text_replacements)} 条文本替换规则")
        
        logger.info(f"总共加载 {total_text_filter_rules} 条文本替换规则")
        
        # 消息处理器字典，用于跟踪每个源频道的消息处理器
        self.message_handlers = {}
        
        # 已处理的消息ID集合，用于防止重复处理同一条消息
        self.processed_messages = set()
        
        # 定期清理已处理消息ID的任务
        self.cleanup_task = None
    
    async def start_monitoring(self, task_context: Optional[TaskContext] = None):
        """
        开始监听所有配置的频道
        
        Args:
            task_context: 任务上下文，用于控制任务执行
        """
        # 初始化任务上下文
        self.task_context = task_context or TaskContext()
        
        status_message = "开始监听源频道的新消息"
        logger.info(status_message)
        self.emit("status", status_message)
        
        # 获取监听频道对
        channel_pairs = self.monitor_config.monitor_channel_pairs
        if not channel_pairs:
            warning_message = "没有配置监听频道对，无法开始监听"
            logger.warning(warning_message)
            self.emit("warning", warning_message)
            return
        
        info_message = f"配置的监听频道对数量: {len(channel_pairs)}"
        logger.info(info_message)
        self.emit("info", info_message)
        
        # 启动定期清理任务
        self.cleanup_task = asyncio.create_task(self._cleanup_processed_messages())
        
        # 创建监听任务
        for pair in channel_pairs:
            source_channel = pair.source_channel
            target_channels = pair.target_channels
            
            # 检查是否已取消任务
            if self.task_context.cancel_token.is_cancelled:
                status_message = "监听任务已取消"
                logger.info(status_message)
                self.emit("status", status_message)
                return
            
            # 等待暂停恢复
            await self.task_context.wait_if_paused()
            
            if not target_channels:
                warning_message = f"源频道 {source_channel} 没有配置目标频道，跳过"
                logger.warning(warning_message)
                self.emit("warning", warning_message)
                continue
            
            # 启动监听任务
            task = asyncio.create_task(
                self._monitor_channel(pair)
            )
            self.monitor_tasks.append(task)
            
            status_message = f"开始监听源频道 {source_channel} 的新消息"
            logger.info(status_message)
            self.emit("status", status_message)
        
        try:
            # 等待所有监听任务完成
            await asyncio.gather(*self.monitor_tasks, return_exceptions=True)
            
            complete_message = "所有监听任务已结束"
            logger.info(complete_message)
            self.emit("complete", {"status": "completed"})
        except Exception as e:
            error_message = f"监听任务异常: {str(e)}"
            logger.error(error_message)
            import traceback
            error_details = traceback.format_exc()
            logger.error(error_details)
            self.emit("error", error_message, error_type="MONITOR_TASK", recoverable=False, details=error_details)
    
    async def stop_monitoring(self):
        """
        停止所有监听任务
        """
        status_message = "正在停止所有监听任务..."
        logger.info(status_message)
        self.emit("status", status_message)
        
        self.should_stop = True
        
        # 如果有任务上下文，则标记为取消
        if self.task_context:
            self.task_context.cancel_token.cancel()
        
        # 取消定期清理任务
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                debug_message = "已取消消息清理任务"
                logger.debug(debug_message)
                self.emit("debug", debug_message)
            except Exception as e:
                error_message = f"取消清理任务时出错: {str(e)}"
                logger.error(error_message)
                self.emit("error", error_message, error_type="CLEANUP_CANCEL", recoverable=True)
        
        # 移除所有消息处理器
        for source_id, handler in self.message_handlers.items():
            self.client.remove_handler(handler)
            debug_message = f"已移除频道 {source_id} 的消息处理器"
            logger.debug(debug_message)
            self.emit("debug", debug_message)
        
        # 清空处理器字典
        self.message_handlers.clear()
        
        # 取消所有监听任务
        for idx, task in enumerate(self.monitor_tasks):
            if not task.done():
                task.cancel()
                progress_message = f"已取消监听任务 {idx+1}/{len(self.monitor_tasks)}"
                logger.debug(progress_message)
                self.emit("progress", ((idx+1) / len(self.monitor_tasks)) * 100, idx+1, len(self.monitor_tasks), "stop")
        
        # 等待所有任务完成
        for task in self.monitor_tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                error_message = f"取消监听任务时异常: {str(e)}"
                logger.error(error_message)
                self.emit("error", error_message, error_type="TASK_CANCEL", recoverable=True)
        
        # 清空任务列表
        self.monitor_tasks.clear()
        self.should_stop = False
        
        # 清空已处理消息集合
        previous_count = len(self.processed_messages)
        self.processed_messages.clear()
        info_message = f"已清理 {previous_count} 条已处理消息记录"
        logger.info(info_message)
        self.emit("info", info_message)
        
        status_message = "所有监听任务已停止"
        logger.info(status_message)
        self.emit("status", status_message)
    
    async def _cleanup_processed_messages(self):
        """
        定期清理已处理的消息ID集合，防止内存无限增长
        """
        try:
            while not self.should_stop:
                # 检查是否已取消任务
                if self.task_context and self.task_context.cancel_token.is_cancelled:
                    debug_message = "清理任务已取消"
                    logger.debug(debug_message)
                    self.emit("debug", debug_message)
                    break
                
                # 每小时清理一次
                await asyncio.sleep(3600)
                
                # 检查是否已取消任务
                if self.task_context and self.task_context.cancel_token.is_cancelled:
                    break
                
                old_size = len(self.processed_messages)
                if old_size > 10000:  # 如果超过1万条消息记录，进行清理
                    self.processed_messages.clear()
                    debug_message = f"已清理 {old_size} 条已处理消息记录"
                    logger.debug(debug_message)
                    self.emit("debug", debug_message)
        except asyncio.CancelledError:
            debug_message = "已取消消息清理任务"
            logger.debug(debug_message)
            self.emit("debug", debug_message)
        except Exception as e:
            error_message = f"消息清理任务异常: {e}"
            logger.error(error_message)
            self.emit("error", error_message, error_type="CLEANUP_TASK", recoverable=True)
    
    async def _monitor_channel(self, channel_pair: MonitorChannelPair):
        """
        监听单个源频道的新消息
        
        Args:
            channel_pair: 监听频道对配置
        """
        source_channel = channel_pair.source_channel
        target_channels = channel_pair.target_channels
        
        try:
            # 检查是否已取消任务
            if self.task_context and self.task_context.cancel_token.is_cancelled:
                debug_message = f"频道 {source_channel} 的监听任务已取消"
                logger.debug(debug_message)
                self.emit("debug", debug_message)
                return
            
            # 等待暂停恢复
            if self.task_context:
                await self.task_context.wait_if_paused()
            
            # 解析源频道ID
            source_id = await self.channel_resolver.get_channel_id(source_channel)
            source_info_str, (source_title, _) = await self.channel_resolver.format_channel_info(source_id)
            info_message = f"监听源频道: {source_info_str}"
            logger.info(info_message)
            self.emit("info", info_message)
            
            # 检查是否已经为该源频道注册了处理器
            if source_id in self.message_handlers:
                warning_message = f"源频道 {source_title} 已有消息处理器，跳过重复注册"
                logger.warning(warning_message)
                self.emit("warning", warning_message)
                return
            
            # 解析所有目标频道ID
            valid_target_channels = []
            for target in target_channels:
                try:
                    # 检查是否已取消任务
                    if self.task_context and self.task_context.cancel_token.is_cancelled:
                        debug_message = f"解析目标频道时任务已取消"
                        logger.debug(debug_message)
                        self.emit("debug", debug_message)
                        return
                    
                    # 等待暂停恢复
                    if self.task_context:
                        await self.task_context.wait_if_paused()
                    
                    target_id = await self.channel_resolver.get_channel_id(target)
                    target_info_str, (target_title, _) = await self.channel_resolver.format_channel_info(target_id)
                    valid_target_channels.append((target, target_id, target_info_str))
                    info_message = f"目标频道: {target_info_str}"
                    logger.info(info_message)
                    self.emit("info", info_message)
                except Exception as e:
                    error_message = f"解析目标频道 {target} 失败: {e}"
                    logger.error(error_message)
                    self.emit("error", error_message, error_type="CHANNEL_RESOLVE", recoverable=True)
            
            if not valid_target_channels:
                warning_message = f"源频道 {source_channel} 没有有效的目标频道，停止监听"
                logger.warning(warning_message)
                self.emit("warning", warning_message)
                return
            
            # 检查源频道是否允许转发
            status_message = f"检查源频道 {source_title} 转发权限..."
            logger.info(status_message)
            self.emit("status", status_message)
            
            source_can_forward = await self.channel_resolver.check_forward_permission(source_id)
            info_message = f"源频道 {source_title} 允许转发: {source_can_forward}"
            logger.info(info_message)
            self.emit("info", info_message)
            
            # 如果源频道禁止转发，直接报错并跳过
            if not source_can_forward:
                error_message = f"源频道 {source_title} 禁止转发消息，跳过此频道的监听"
                logger.error(error_message)
                self.emit("error", error_message, error_type="CHANNEL_FORBID_FORWARD", recoverable=False)
                return
            
            # 获取这个源频道的文本替换规则
            text_replacements = self.channel_text_replacements.get(source_channel, {})
            # 获取这个源频道的移除标题设置
            remove_captions = self.channel_remove_captions.get(source_channel, False)
            
            if text_replacements:
                info_message = f"源频道 {source_title} 启用了 {len(text_replacements)} 条文本替换规则"
                logger.info(info_message)
                self.emit("info", info_message)
            
            if remove_captions:
                info_message = f"源频道 {source_title} 启用了移除标题功能"
                logger.info(info_message)
                self.emit("info", info_message)
            
            # 创建 handler 处理函数来监听新消息
            async def new_message_handler(client, message):
                # 检查是否应该停止监听
                if self.should_stop or (self.task_context and self.task_context.cancel_token.is_cancelled):
                    return
                
                # 等待暂停恢复
                if self.task_context:
                    await self.task_context.wait_if_paused()
                
                # 检查是否超过监听时间
                if self.end_time and datetime.now() > self.end_time:
                    status_message = f"监听时间已到 {self.end_time}，停止监听 {source_title}"
                    logger.info(status_message)
                    self.emit("status", status_message)
                    await self.stop_monitoring()
                    return
                
                # 检查消息是否已处理过，避免重复处理
                message_unique_id = f"{source_id}_{message.id}"
                if message_unique_id in self.processed_messages:
                    debug_message = f"消息 {message.id} 已处理过，跳过"
                    logger.debug(debug_message)
                    self.emit("debug", debug_message)
                    return
                
                # 将消息标记为已处理
                self.processed_messages.add(message_unique_id)
                
                # 检查消息类型是否在允许列表中
                if not self._is_media_allowed(message):
                    debug_message = f"消息类型不在允许列表中，跳过: {message.id}"
                    logger.debug(debug_message)
                    self.emit("debug", debug_message)
                    return
                
                # 处理消息组
                if message.media_group_id:
                    # 检查媒体组ID是否已处理过
                    media_group_unique_id = f"{source_id}_{message.media_group_id}"
                    if media_group_unique_id in self.processed_messages:
                        debug_message = f"媒体组 {message.media_group_id} 已处理过，跳过"
                        logger.debug(debug_message)
                        self.emit("debug", debug_message)
                        return
                    
                    # 将媒体组ID标记为已处理
                    self.processed_messages.add(media_group_unique_id)
                    
                    # 发射新媒体组事件
                    self.emit("media_group_received", message.media_group_id, source_info_str)
                    
                    # 等待一段时间收集媒体组中的所有消息
                    status_message = f"收到新媒体组 {message.media_group_id}，等待收集完整媒体组..."
                    logger.info(status_message)
                    self.emit("status", status_message)
                    
                    await asyncio.sleep(2)
                    
                    # 处理媒体组消息
                    status_message = f"开始处理媒体组 {message.media_group_id}"
                    logger.info(status_message)
                    self.emit("status", status_message)
                    
                    await self._handle_media_group(message, source_channel, source_id, valid_target_channels, text_replacements, remove_captions)
                    return
                
                # 处理单条消息
                info_message = f"收到新消息 {message.id} 来自 {source_title}"
                logger.info(info_message)
                self.emit("message_received", message.id, source_info_str)
                
                await self._copy_message(message, source_channel, source_id, valid_target_channels, text_replacements, remove_captions)
            
            # 注册消息处理器
            handler = MessageHandler(new_message_handler, filters.chat(source_id))
            self.client.add_handler(handler)
            
            # 存储处理器引用，便于之后移除
            self.message_handlers[source_id] = handler
            debug_message = f"已为频道 {source_title} 注册消息处理器"
            logger.debug(debug_message)
            self.emit("debug", debug_message)
            
            # 保持任务运行，直到停止监听
            status_message = f"开始监听频道 {source_title} 的新消息"
            logger.info(status_message)
            self.emit("status", status_message)
            
            try:
                while not self.should_stop:
                    # 检查是否已取消任务
                    if self.task_context and self.task_context.cancel_token.is_cancelled:
                        status_message = f"频道 {source_title} 的监听任务已取消"
                        logger.info(status_message)
                        self.emit("status", status_message)
                        break
                    
                    # 等待暂停恢复
                    if self.task_context:
                        await self.task_context.wait_if_paused()
                    
                    # 检查是否超过监听时间
                    if self.end_time and datetime.now() > self.end_time:
                        status_message = f"监听时间已到 {self.end_time}，停止监听 {source_title}"
                        logger.info(status_message)
                        self.emit("status", status_message)
                        await self.stop_monitoring()
                        break
                    
                    await asyncio.sleep(10)  # 每10秒检查一次状态
                
                status_message = f"频道 {source_title} 的监听任务已结束"
                logger.info(status_message)
                self.emit("status", status_message)
                
            except Exception as e:
                error_message = f"监听频道 {source_title} 时异常: {str(e)}"
                logger.error(error_message)
                import traceback
                error_details = traceback.format_exc()
                logger.error(error_details)
                self.emit("error", error_message, error_type="MONITOR_LOOP", recoverable=True, details=error_details)
            finally:
                # 尝试清理注册的处理器
                if source_id in self.message_handlers:
                    self.client.remove_handler(self.message_handlers[source_id])
                    del self.message_handlers[source_id]
                    debug_message = f"已清理频道 {source_title} 的消息处理器"
                    logger.debug(debug_message)
                    self.emit("debug", debug_message)
                
        except Exception as e:
            error_message = f"监听源频道 {source_channel} 失败: {str(e)}"
            logger.error(error_message)
            import traceback
            error_details = traceback.format_exc()
            logger.error(error_details)
            self.emit("error", error_message, error_type="MONITOR_CHANNEL", recoverable=False, details=error_details)
            
            # 尝试清理注册的处理器
            if source_id in self.message_handlers:
                self.client.remove_handler(self.message_handlers[source_id])
                del self.message_handlers[source_id]
    
    async def _handle_media_group(self, message: Message, source_channel: str, source_id: int, target_channels: List[Tuple[str, int, str]], text_replacements: Dict[str, str], remove_captions: bool):
        """
        处理媒体组消息
        
        Args:
            message: 媒体组中的一条消息
            source_channel: 源频道
            source_id: 源频道ID
            target_channels: 目标频道列表 (channel_str, channel_id, channel_info)
            text_replacements: 该频道的文本替换规则
            remove_captions: 该频道的移除标题设置
        """
        try:
            # 检查任务是否已取消
            if self.task_context and self.task_context.cancel_token.is_cancelled:
                debug_message = f"处理媒体组 {message.media_group_id} 任务已取消"
                logger.debug(debug_message)
                self.emit("debug", debug_message)
                return
            
            # 等待暂停恢复
            if self.task_context:
                await self.task_context.wait_if_paused()
            
            # 获取媒体组ID
            media_group_id = message.media_group_id
            if not media_group_id:
                debug_message = "消息不属于媒体组，跳过处理"
                logger.debug(debug_message)
                self.emit("debug", debug_message)
                return
            
            # 获取标题，应用文本替换规则
            caption = message.caption or ""
            modified_caption = self._apply_text_replacements(caption, text_replacements)
            
            # 根据配置决定是否保留标题
            if remove_captions:
                captions = ""
                if caption:
                    info_message = f"移除媒体组 {media_group_id} 的标题"
                    logger.info(info_message)
                    self.emit("status", info_message)
            else:
                captions = modified_caption
                if caption != modified_caption:
                    info_message = f"媒体组 {media_group_id} 的标题已修改"
                    logger.info(info_message)
                    self.emit("status", info_message)
            
            # 复制媒体组，使用处理后的标题
            status_message = f"开始复制媒体组 {media_group_id} 到 {len(target_channels)} 个目标频道"
            logger.info(status_message)
            self.emit("status", status_message)
            
            await self._copy_media_group(message.id, source_channel, source_id, target_channels, captions)
            
            complete_message = f"媒体组 {media_group_id} 处理完成"
            logger.info(complete_message)
            self.emit("status", complete_message)
                
        except Exception as e:
            error_message = f"处理媒体组 {message.media_group_id} 失败: {str(e)}"
            logger.error(error_message)
            import traceback
            error_details = traceback.format_exc()
            logger.error(error_details)
            self.emit("error", error_message, error_type="MEDIA_GROUP", recoverable=True, details=error_details)
    
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
                    debug_message = f"文本替换: '{original}' -> '{replacement}'"
                    logger.debug(debug_message)
                    self.emit("debug", debug_message)
        
        if replacement_made:
            info_message = f"已应用文本替换，原文本: '{text}'，新文本: '{modified_text}'"
            logger.info(info_message)
            self.emit("text_replaced", text, modified_text, replacements)
        
        return modified_text
    
    async def _copy_media_group(self, message_id: int, source_channel: str, source_id: int, target_channels: List[Tuple[str, int, str]], captions=None):
        """
        复制媒体组
        
        Args:
            message_id: 消息ID
            source_channel: 源频道
            source_id: 源频道ID
            target_channels: 目标频道列表 (channel_str, channel_id, channel_info)
            captions: 可选，自定义标题文本
        """
        try:
            total_targets = len(target_channels)
            successful_copies = 0
            skipped_targets = 0
            
            # 为每个目标频道复制媒体组
            for i, (target, target_id, target_info) in enumerate(target_channels, 1):
                # 检查任务是否已取消
                if self.task_context and self.task_context.cancel_token.is_cancelled:
                    debug_message = f"复制媒体组 {message_id} 到剩余目标频道的任务已取消"
                    logger.debug(debug_message)
                    self.emit("debug", debug_message)
                    break
                
                # 等待暂停恢复
                if self.task_context:
                    await self.task_context.wait_if_paused()
                
                # 发送进度通知
                progress_message = f"复制媒体组 {message_id} 到目标频道 {i}/{total_targets}: {target_info}"
                logger.info(progress_message)
                self.emit("progress", i, total_targets, progress_message)
                
                try:
                    # 使用 copy_media_group 方法复制媒体组
                    copied_messages = await self.client.copy_media_group(
                        chat_id=target_id,
                        from_chat_id=source_id,
                        message_id=message_id,
                        captions=captions
                    )
                    
                    successful_copies += 1
                    success_message = f"媒体组消息 {message_id} 已成功复制到 {target_info}"
                    logger.info(success_message)
                    self.emit("status", success_message)
                    
                    # 添加转发延迟
                    delay_message = f"等待 {self.monitor_config.forward_delay} 秒后继续下一个转发"
                    logger.debug(delay_message)
                    self.emit("debug", delay_message)
                    await asyncio.sleep(self.monitor_config.forward_delay)
                    
                except FloodWait as e:
                    wait_time = e.x
                    flood_message = f"复制受限，等待 {wait_time} 秒后继续"
                    logger.warning(flood_message)
                    self.emit("warning", flood_message)
                    
                    # 等待限制时间
                    await asyncio.sleep(wait_time)
                    
                    # 检查任务是否在等待期间被取消
                    if self.task_context and self.task_context.cancel_token.is_cancelled:
                        debug_message = f"等待期间任务已取消，不再重试"
                        logger.debug(debug_message)
                        self.emit("debug", debug_message)
                        break
                    
                    # 重试复制
                    try:
                        retry_message = f"重试复制媒体组消息 {message_id} 到 {target_info}"
                        logger.info(retry_message)
                        self.emit("status", retry_message)
                        
                        await self.client.copy_media_group(
                            chat_id=target_id,
                            from_chat_id=source_id,
                            message_id=message_id,
                            captions=captions
                        )
                        
                        successful_copies += 1
                        success_message = f"媒体组消息 {message_id} 已成功重试复制到 {target_info}"
                        logger.info(success_message)
                        self.emit("status", success_message)
                    except Exception as retry_e:
                        error_message = f"重试复制媒体组消息 {message_id} 到 {target_info} 失败: {str(retry_e)}"
                        logger.error(error_message)
                        self.emit("error", error_message, error_type="MEDIA_GROUP_RETRY", recoverable=True)
                
                except ChatForwardsRestricted:
                    skipped_targets += 1
                    error_message = f"无法复制媒体组到 {target_info}，该频道禁止转发消息，跳过"
                    logger.error(error_message)
                    self.emit("error", error_message, error_type="FORWARDS_RESTRICTED", recoverable=False)
                    continue
                
                except Exception as e:
                    error_message = f"复制媒体组消息 {message_id} 到 {target_info} 失败: {str(e)}"
                    logger.error(error_message)
                    import traceback
                    error_details = traceback.format_exc()
                    logger.error(error_details)
                    self.emit("error", error_message, error_type="MEDIA_GROUP_COPY", recoverable=True, details=error_details)
            
            # 完成复制后发送总结
            summary_message = f"媒体组消息 {message_id} 转发完成：成功 {successful_copies}/{total_targets} 个目标频道, 跳过 {skipped_targets} 个"
            logger.info(summary_message)
            self.emit("status", summary_message)
            
        except Exception as e:
            error_message = f"复制媒体组消息 {message_id} 失败: {str(e)}"
            logger.error(error_message)
            import traceback
            error_details = traceback.format_exc()
            logger.error(error_details)
            self.emit("error", error_message, error_type="MEDIA_GROUP_COPY_ALL", recoverable=False, details=error_details)
    
    async def _copy_message(self, message: Message, source_channel: str, source_id: int, target_channels: List[Tuple[str, int, str]], text_replacements: Dict[str, str], remove_captions: bool):
        """
        复制消息到目标频道
        
        Args:
            message: 要复制的消息
            source_channel: 源频道
            source_id: 源频道ID
            target_channels: 目标频道列表 (channel_str, channel_id, channel_info)
            text_replacements: 该频道的文本替换规则
            remove_captions: 该频道的移除标题设置
        """
        try:
            total_targets = len(target_channels)
            successful_copies = 0
            skipped_targets = 0
            
            status_message = f"开始复制消息 {message.id} 到 {total_targets} 个目标频道"
            logger.info(status_message)
            self.emit("status", status_message)
            
            for i, (target, target_id, target_info) in enumerate(target_channels, 1):
                # 检查任务是否已取消
                if self.task_context and self.task_context.cancel_token.is_cancelled:
                    debug_message = f"复制消息 {message.id} 到剩余目标频道的任务已取消"
                    logger.debug(debug_message)
                    self.emit("debug", debug_message)
                    break
                
                # 等待暂停恢复
                if self.task_context:
                    await self.task_context.wait_if_paused()
                
                # 发送进度通知
                progress_message = f"复制消息 {message.id} 到目标频道 {i}/{total_targets}: {target_info}"
                logger.info(progress_message)
                self.emit("progress", i, total_targets, progress_message)
                
                try:
                    caption = None
                    text = None
                    
                    # 根据消息类型处理文本
                    if message.text:
                        # 处理纯文本消息
                        original_text = message.text
                        modified_text = self._apply_text_replacements(original_text, text_replacements)
                        
                        # 使用client.send_message发送文本消息
                        sent = await self.client.send_message(
                            chat_id=target_id,
                            text=modified_text
                        )
                        
                        successful_copies += 1
                        if original_text != modified_text:
                            success_message = f"消息 {message.id} 已成功替换文本并发送到 {target_info}"
                            logger.info(success_message)
                            self.emit("status", success_message)
                        else:
                            success_message = f"消息 {message.id} 已成功发送到 {target_info}"
                            logger.info(success_message)
                            self.emit("status", success_message)
                        
                    else:
                        # 处理媒体消息（带标题）
                        if message.caption:
                            original_caption = message.caption
                            modified_caption = self._apply_text_replacements(original_caption, text_replacements)
                            
                            # 根据配置决定是否保留标题
                            if not remove_captions:
                                caption = modified_caption
                                if original_caption != modified_caption:
                                    caption_message = f"已修改消息 {message.id} 的标题"
                                    logger.info(caption_message)
                                    self.emit("debug", caption_message)
                            else:
                                caption = ""  # 空字符串移除标题
                                if original_caption:
                                    caption_message = f"已移除消息 {message.id} 的标题"
                                    logger.info(caption_message)
                                    self.emit("debug", caption_message)
                        
                        # 使用copy_message复制媒体消息
                        copied = await self.client.copy_message(
                            chat_id=target_id,
                            from_chat_id=source_id,
                            message_id=message.id,
                            caption=caption
                        )
                        
                        successful_copies += 1
                        if message.caption and message.caption != caption and caption != "":
                            success_message = f"消息 {message.id} 已成功替换标题并复制到 {target_info}"
                            logger.info(success_message)
                            self.emit("status", success_message)
                        else:
                            success_message = f"消息 {message.id} 已成功复制到 {target_info}"
                            logger.info(success_message)
                            self.emit("status", success_message)
                    
                    # 添加转发延迟
                    delay_message = f"等待 {self.monitor_config.forward_delay} 秒后继续下一个转发"
                    logger.debug(delay_message)
                    self.emit("debug", delay_message)
                    await asyncio.sleep(self.monitor_config.forward_delay)
                    
                except FloodWait as e:
                    wait_time = e.x
                    flood_message = f"复制受限，等待 {wait_time} 秒后继续"
                    logger.warning(flood_message)
                    self.emit("warning", flood_message)
                    
                    # 等待限制时间
                    await asyncio.sleep(wait_time)
                    
                    # 检查任务是否在等待期间被取消
                    if self.task_context and self.task_context.cancel_token.is_cancelled:
                        debug_message = f"等待期间任务已取消，不再重试"
                        logger.debug(debug_message)
                        self.emit("debug", debug_message)
                        break
                    
                    # 重试复制
                    try:
                        retry_message = f"重试发送消息 {message.id} 到 {target_info}"
                        logger.info(retry_message)
                        self.emit("status", retry_message)
                        
                        if message.text:
                            await self.client.send_message(
                                chat_id=target_id,
                                text=modified_text
                            )
                        else:
                            await self.client.copy_message(
                                chat_id=target_id,
                                from_chat_id=source_id,
                                message_id=message.id,
                                caption=caption
                            )
                            
                        successful_copies += 1
                        success_message = f"消息 {message.id} 已成功重试发送到 {target_info}"
                        logger.info(success_message)
                        self.emit("status", success_message)
                    except Exception as retry_e:
                        error_message = f"重试发送消息 {message.id} 到 {target_info} 失败: {str(retry_e)}"
                        logger.error(error_message)
                        self.emit("error", error_message, error_type="MESSAGE_RETRY", recoverable=True)
                
                except ChatForwardsRestricted:
                    skipped_targets += 1
                    error_message = f"无法复制到 {target_info}，该频道禁止转发消息，跳过"
                    logger.error(error_message)
                    self.emit("error", error_message, error_type="FORWARDS_RESTRICTED", recoverable=False)
                    continue
                
                except Exception as e:
                    error_message = f"复制消息 {message.id} 到 {target_info} 失败: {str(e)}"
                    logger.error(error_message)
                    import traceback
                    error_details = traceback.format_exc()
                    logger.error(error_details)
                    self.emit("error", error_message, error_type="MESSAGE_COPY", recoverable=True, details=error_details)
            
            # 完成复制后发送总结
            summary_message = f"消息 {message.id} 转发完成：成功 {successful_copies}/{total_targets} 个目标频道, 跳过 {skipped_targets} 个"
            logger.info(summary_message)
            self.emit("status", summary_message)
            
        except Exception as e:
            error_message = f"复制消息 {message.id} 失败: {str(e)}"
            logger.error(error_message)
            import traceback
            error_details = traceback.format_exc()
            logger.error(error_details)
            self.emit("error", error_message, error_type="MESSAGE_COPY_ALL", recoverable=False, details=error_details)
    
    def _is_media_allowed(self, message: Message) -> bool:
        """
        检查消息类型是否在允许列表中
        
        Args:
            message: 消息对象
            
        Returns:
            bool: 是否允许
        """
        allowed_types = self.monitor_config.media_types
        
        if "text" in allowed_types and message.text:
            return True
        
        if "photo" in allowed_types and message.photo:
            return True
        
        if "video" in allowed_types and message.video:
            return True
        
        if "document" in allowed_types and message.document:
            return True
        
        if "audio" in allowed_types and message.audio:
            return True
        
        if "animation" in allowed_types and message.animation:
            return True
        
        if "sticker" in allowed_types and message.sticker:
            return True
        
        if "voice" in allowed_types and message.voice:
            return True
        
        if "video_note" in allowed_types and message.video_note:
            return True
        
        return False
