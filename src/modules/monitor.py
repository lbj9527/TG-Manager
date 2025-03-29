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

logger = get_logger()


class Monitor:
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
        self.client = client
        self.config_manager = config_manager
        self.channel_resolver = channel_resolver
        
        # 获取监听配置
        self.monitor_config = self.config_manager.get_monitor_config()
        
        # 存储监听任务
        self.monitor_tasks = []
        
        # 停止标志
        self.should_stop = False
        
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
    
    async def start_monitoring(self):
        """
        开始监听所有配置的频道
        """
        logger.info("开始监听源频道的新消息")
        
        # 获取监听频道对
        channel_pairs = self.monitor_config.monitor_channel_pairs
        if not channel_pairs:
            logger.warning("没有配置监听频道对，无法开始监听")
            return
        
        logger.info(f"配置的监听频道对数量: {len(channel_pairs)}")
        
        # 启动定期清理任务
        self.cleanup_task = asyncio.create_task(self._cleanup_processed_messages())
        
        # 创建监听任务
        for pair in channel_pairs:
            source_channel = pair.source_channel
            target_channels = pair.target_channels
            
            if not target_channels:
                logger.warning(f"源频道 {source_channel} 没有配置目标频道，跳过")
                continue
            
            # 启动监听任务
            task = asyncio.create_task(
                self._monitor_channel(pair)
            )
            self.monitor_tasks.append(task)
            
            logger.info(f"开始监听源频道 {source_channel} 的新消息")
        
        # 等待所有监听任务完成
        await asyncio.gather(*self.monitor_tasks, return_exceptions=True)
        
        logger.info("所有监听任务已结束")
    
    async def stop_monitoring(self):
        """
        停止所有监听任务
        """
        logger.info("正在停止所有监听任务...")
        self.should_stop = True
        
        # 取消定期清理任务
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        # 移除所有消息处理器
        for source_id, handler in self.message_handlers.items():
            self.client.remove_handler(handler)
            logger.debug(f"已移除频道 {source_id} 的消息处理器")
        
        # 清空处理器字典
        self.message_handlers.clear()
        
        # 取消所有监听任务
        for task in self.monitor_tasks:
            if not task.done():
                task.cancel()
        
        # 等待所有任务完成
        for task in self.monitor_tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        # 清空任务列表
        self.monitor_tasks.clear()
        self.should_stop = False
        
        # 清空已处理消息集合
        self.processed_messages.clear()
        
        logger.info("所有监听任务已停止")
    
    async def _cleanup_processed_messages(self):
        """
        定期清理已处理的消息ID集合，防止内存无限增长
        """
        try:
            while not self.should_stop:
                # 每小时清理一次
                await asyncio.sleep(3600)
                old_size = len(self.processed_messages)
                if old_size > 10000:  # 如果超过1万条消息记录，进行清理
                    self.processed_messages.clear()
                    logger.debug(f"已清理 {old_size} 条已处理消息记录")
        except asyncio.CancelledError:
            logger.debug("已取消消息清理任务")
        except Exception as e:
            logger.error(f"消息清理任务异常: {e}")
    
    async def _monitor_channel(self, channel_pair: MonitorChannelPair):
        """
        监听单个源频道的新消息
        
        Args:
            channel_pair: 监听频道对配置
        """
        source_channel = channel_pair.source_channel
        target_channels = channel_pair.target_channels
        
        try:
            # 解析源频道ID
            source_id = await self.channel_resolver.get_channel_id(source_channel)
            source_info_str, (source_title, _) = await self.channel_resolver.format_channel_info(source_id)
            logger.info(f"监听源频道: {source_info_str}")
            
            # 检查是否已经为该源频道注册了处理器
            if source_id in self.message_handlers:
                logger.warning(f"源频道 {source_title} 已有消息处理器，跳过重复注册")
                return
            
            # 解析所有目标频道ID
            valid_target_channels = []
            for target in target_channels:
                try:
                    target_id = await self.channel_resolver.get_channel_id(target)
                    target_info_str, (target_title, _) = await self.channel_resolver.format_channel_info(target_id)
                    valid_target_channels.append((target, target_id, target_info_str))
                    logger.info(f"目标频道: {target_info_str}")
                except Exception as e:
                    logger.error(f"解析目标频道 {target} 失败: {e}")
            
            if not valid_target_channels:
                logger.warning(f"源频道 {source_channel} 没有有效的目标频道，停止监听")
                return
            
            # 检查源频道是否允许转发
            source_can_forward = await self.channel_resolver.check_forward_permission(source_id)
            logger.info(f"源频道 {source_title} 允许转发: {source_can_forward}")
            
            # 如果源频道禁止转发，直接报错并跳过
            if not source_can_forward:
                logger.error(f"源频道 {source_title} 禁止转发消息，跳过此频道的监听")
                return
            
            # 获取这个源频道的文本替换规则
            text_replacements = self.channel_text_replacements.get(source_channel, {})
            # 获取这个源频道的移除标题设置
            remove_captions = self.channel_remove_captions.get(source_channel, False)
            
            # 创建 handler 处理函数来监听新消息
            async def new_message_handler(client, message):
                # 检查是否应该停止监听
                if self.should_stop:
                    return
                
                # 检查是否超过监听时间
                if self.end_time and datetime.now() > self.end_time:
                    logger.info(f"监听时间已到 {self.end_time}，停止监听 {source_title}")
                    await self.stop_monitoring()
                    return
                
                # 检查消息是否已处理过，避免重复处理
                message_unique_id = f"{source_id}_{message.id}"
                if message_unique_id in self.processed_messages:
                    logger.debug(f"消息 {message.id} 已处理过，跳过")
                    return
                
                # 将消息标记为已处理
                self.processed_messages.add(message_unique_id)
                
                # 检查消息类型是否在允许列表中
                if not self._is_media_allowed(message):
                    logger.debug(f"消息类型不在允许列表中，跳过: {message.id}")
                    return
                
                # 处理消息组
                if message.media_group_id:
                    # 检查媒体组ID是否已处理过
                    media_group_unique_id = f"{source_id}_{message.media_group_id}"
                    if media_group_unique_id in self.processed_messages:
                        logger.debug(f"媒体组 {message.media_group_id} 已处理过，跳过")
                        return
                    
                    # 将媒体组ID标记为已处理
                    self.processed_messages.add(media_group_unique_id)
                    
                    # 等待一段时间收集媒体组中的所有消息
                    await asyncio.sleep(2)
                    # 处理媒体组消息
                    await self._handle_media_group(message, source_channel, source_id, valid_target_channels, text_replacements, remove_captions)
                    return
                
                # 处理单条消息
                await self._copy_message(message, source_channel, source_id, valid_target_channels, text_replacements, remove_captions)
            
            # 注册消息处理器
            handler = MessageHandler(new_message_handler, filters.chat(source_id))
            self.client.add_handler(handler)
            
            # 存储处理器引用，便于之后移除
            self.message_handlers[source_id] = handler
            logger.debug(f"已为频道 {source_title} 注册消息处理器")
            
            # 保持任务运行，直到停止监听
            while not self.should_stop:
                # 检查是否超过监听时间
                if self.end_time and datetime.now() > self.end_time:
                    logger.info(f"监听时间已到 {self.end_time}，停止监听 {source_title}")
                    await self.stop_monitoring()
                    break
                
                await asyncio.sleep(10)  # 每10秒检查一次状态
                
        except Exception as e:
            logger.error(f"监听源频道 {source_channel} 失败: {e}")
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
            # 获取媒体组ID
            media_group_id = message.media_group_id
            if not media_group_id:
                return
            
            # 获取标题，应用文本替换规则
            caption = message.caption or ""
            modified_caption = self._apply_text_replacements(caption, text_replacements)
            
            # 根据配置决定是否保留标题
            if remove_captions:
                captions = ""
            else:
                captions = modified_caption
            
            # 复制媒体组，使用处理后的标题
            await self._copy_media_group(message.id, source_channel, source_id, target_channels, captions)
                
        except Exception as e:
            logger.error(f"处理媒体组 {message.media_group_id} 失败: {e}")
    
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
        
        for original, replacement in text_replacements.items():
            if original in modified_text:
                old_text = modified_text
                modified_text = modified_text.replace(original, replacement)
                replacement_made = True
                logger.debug(f"文本替换: '{original}' -> '{replacement}'")
        
        if replacement_made:
            logger.info(f"已应用文本替换，原文本: '{text}'，新文本: '{modified_text}'")
        
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
            # 为每个目标频道复制媒体组
            for target, target_id, target_info in target_channels:
                try:
                    # 使用 copy_media_group 方法复制媒体组
                    copied_messages = await self.client.copy_media_group(
                        chat_id=target_id,
                        from_chat_id=source_id,
                        message_id=message_id,
                        captions=captions
                    )
                    
                    logger.info(f"媒体组消息 {message_id} 已成功复制到 {target_info}")
                    
                    # 添加转发延迟
                    await asyncio.sleep(self.monitor_config.forward_delay)
                    
                except FloodWait as e:
                    wait_time = e.x
                    logger.warning(f"复制受限，等待 {wait_time} 秒后继续")
                    await asyncio.sleep(wait_time)
                    # 重试复制
                    try:
                        await self.client.copy_media_group(
                            chat_id=target_id,
                            from_chat_id=source_id,
                            message_id=message_id,
                            captions=captions
                        )
                        logger.info(f"媒体组消息 {message_id} 已成功复制到 {target_info}")
                    except Exception as retry_e:
                        logger.error(f"重试复制媒体组消息 {message_id} 到 {target_info} 失败: {retry_e}")
                
                except ChatForwardsRestricted:
                    logger.error(f"无法复制媒体组到 {target_info}，该频道禁止转发消息，跳过")
                    continue
                
                except Exception as e:
                    logger.error(f"复制媒体组消息 {message_id} 到 {target_info} 失败: {e}")
            
        except Exception as e:
            logger.error(f"复制媒体组消息 {message_id} 失败: {e}")
    
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
        for target, target_id, target_info in target_channels:
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
                    
                    if original_text != modified_text:
                        logger.info(f"消息 {message.id} 已成功替换文本并发送到 {target_info}")
                    else:
                        logger.info(f"消息 {message.id} 已成功发送到 {target_info}")
                    
                else:
                    # 处理媒体消息（带标题）
                    if message.caption:
                        original_caption = message.caption
                        modified_caption = self._apply_text_replacements(original_caption, text_replacements)
                        
                        # 根据配置决定是否保留标题
                        if not remove_captions:
                            caption = modified_caption
                        else:
                            caption = ""  # 空字符串移除标题
                    
                    # 使用copy_message复制媒体消息
                    copied = await self.client.copy_message(
                        chat_id=target_id,
                        from_chat_id=source_id,
                        message_id=message.id,
                        caption=caption
                    )
                    
                    if message.caption and message.caption != caption and caption != "":
                        logger.info(f"消息 {message.id} 已成功替换标题并复制到 {target_info}")
                    else:
                        logger.info(f"消息 {message.id} 已成功复制到 {target_info}")
                
                # 添加转发延迟
                await asyncio.sleep(self.monitor_config.forward_delay)
                
            except FloodWait as e:
                wait_time = e.x
                logger.warning(f"复制受限，等待 {wait_time} 秒后继续")
                await asyncio.sleep(wait_time)
                # 重试复制
                try:
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
                    logger.info(f"消息 {message.id} 已成功重试发送到 {target_info}")
                except Exception as retry_e:
                    logger.error(f"重试发送消息 {message.id} 到 {target_info} 失败: {retry_e}")
            
            except ChatForwardsRestricted:
                logger.error(f"无法复制到 {target_info}，该频道禁止转发消息，跳过")
                continue
            
            except Exception as e:
                logger.error(f"复制消息 {message.id} 到 {target_info} 失败: {e}")
    
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
