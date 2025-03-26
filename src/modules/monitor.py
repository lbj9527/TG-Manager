"""
监听模块，负责监听源频道的新消息并实时转发
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple, Set, Union

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait

from src.utils.config_manager import ConfigManager
from src.utils.channel_resolver import ChannelResolver
from src.utils.history_manager import HistoryManager
from src.modules.forwarder import Forwarder
from src.utils.logger import get_logger

logger = get_logger()

class Monitor:
    """
    监听模块，负责监听源频道的新消息并实时转发
    """
    
    def __init__(self, client: Client, config_manager: ConfigManager, channel_resolver: ChannelResolver, history_manager: HistoryManager, forwarder: Forwarder):
        """
        初始化监听模块
        
        Args:
            client: Pyrogram客户端实例
            config_manager: 配置管理器实例
            channel_resolver: 频道解析器实例
            history_manager: 历史记录管理器实例
            forwarder: 转发模块实例
        """
        self.client = client
        self.config_manager = config_manager
        self.channel_resolver = channel_resolver
        self.history_manager = history_manager
        self.forwarder = forwarder
        
        # 获取监听配置
        self.monitor_config = self.config_manager.get_monitor_config()
        
        # 监听频道映射
        self.channel_mapping = {}
        self.source_channels = []
        
        # 停止事件
        self.stop_event = asyncio.Event()
        
        # 监听结束时间
        self.end_time = None
        if self.monitor_config.duration:
            self._parse_duration()
    
    def _parse_duration(self):
        """
        解析监听持续时间
        """
        try:
            # 解析格式为"年-月-日-时"的时间
            duration_str = self.monitor_config.duration
            if not duration_str:
                return
            
            parts = duration_str.split('-')
            if len(parts) != 4:
                logger.error(f"监听持续时间格式错误: {duration_str}，应为'年-月-日-时'")
                return
            
            year, month, day, hour = map(int, parts)
            self.end_time = datetime(year, month, day, hour)
            
            logger.info(f"监听将于 {self.end_time} 结束")
        except Exception as e:
            logger.error(f"解析监听持续时间失败: {e}")
    
    async def initialize_channels(self):
        """
        初始化监听频道映射关系
        """
        channel_pairs = self.monitor_config.monitor_channel_pairs
        
        for pair in channel_pairs:
            source_channel = pair.source_channel
            target_channels = pair.target_channels
            
            if not target_channels:
                logger.warning(f"源频道 {source_channel} 没有配置目标频道，跳过")
                continue
            
            try:
                # 解析源频道ID
                source_id = await self.channel_resolver.get_channel_id(source_channel)
                source_info_str, (source_title, _) = await self.channel_resolver.format_channel_info(source_channel)
                
                # 获取有效的目标频道
                valid_target_channels = []
                for target in target_channels:
                    try:
                        target_id = await self.channel_resolver.get_channel_id(target)
                        target_info_str, (target_title, _) = await self.channel_resolver.format_channel_info(target)
                        valid_target_channels.append((target, target_id, target_info_str))
                    except Exception as e:
                        logger.error(f"解析目标频道 {target} 失败: {e}")
                
                if not valid_target_channels:
                    logger.warning(f"源频道 {source_channel} 没有有效的目标频道，跳过")
                    continue
                
                # 添加到映射
                self.channel_mapping[source_id] = {
                    'source_channel': source_channel,
                    'source_info': source_info_str,
                    'target_channels': valid_target_channels
                }
                
                # 记录源频道ID
                self.source_channels.append(source_id)
                
                logger.info(f"添加监听: {source_info_str} -> {[t[2] for t in valid_target_channels]}")
            
            except Exception as e:
                logger.error(f"初始化频道 {source_channel} 失败: {e}")
    
    async def start_monitoring(self):
        """
        开始监听源频道的新消息
        """
        if not self.source_channels:
            logger.warning("没有有效的源频道，无法启动监听")
            return
        
        logger.info(f"开始监听 {len(self.source_channels)} 个频道")
        
        # 注册消息处理函数
        @self.client.on_message(filters.chat(self.source_channels) & ~filters.edited)
        async def message_handler(client, message):
            await self._process_new_message(message)
        
        # 启动检查线程
        asyncio.create_task(self._check_monitor_duration())
        
        # 启动客户端监听
        await self.client.idle(stop_signals=None)
    
    async def stop_monitoring(self):
        """
        停止监听
        """
        self.stop_event.set()
        
        # 移除所有处理函数
        self.client.remove_handler(filters.chat(self.source_channels) & ~filters.edited)
        
        logger.info("停止监听")
    
    async def _check_monitor_duration(self):
        """
        检查监听是否超过持续时间
        """
        while not self.stop_event.is_set():
            if self.end_time and datetime.now() >= self.end_time:
                logger.info(f"已达到监听结束时间: {self.end_time}")
                await self.stop_monitoring()
                break
            
            await asyncio.sleep(60)  # 每分钟检查一次
    
    async def _process_new_message(self, message: Message):
        """
        处理新消息
        
        Args:
            message: 消息对象
        """
        chat_id = message.chat.id
        
        # 获取频道映射
        if chat_id not in self.channel_mapping:
            return
        
        mapping = self.channel_mapping[chat_id]
        source_channel = mapping['source_channel']
        source_info = mapping['source_info']
        target_channels = mapping['target_channels']
        
        logger.info(f"收到来自 {source_info} 的新消息 {message.id}")
        
        # 检查媒体类型
        if not self._is_media_allowed(message):
            logger.debug(f"消息 {message.id} 的媒体类型不在允许列表中，跳过")
            return
        
        # 检查是否属于媒体组
        if message.media_group_id:
            # 媒体组消息需要特殊处理，等待所有消息到达
            logger.debug(f"消息 {message.id} 属于媒体组 {message.media_group_id}，等待收集完整")
            await asyncio.sleep(2)  # 等待媒体组所有消息到达
            
            # 获取完整的媒体组
            try:
                media_group = await self.client.get_media_group(chat_id, message.id)
                logger.info(f"获取媒体组 {message.media_group_id}，共 {len(media_group)} 条消息")
                await self._forward_messages(source_channel, media_group, target_channels)
            except Exception as e:
                logger.error(f"获取媒体组失败: {e}")
                # 尝试单独转发此条消息
                await self._forward_messages(source_channel, [message], target_channels)
        else:
            # 单条消息直接转发
            await self._forward_messages(source_channel, [message], target_channels)
    
    async def _forward_messages(self, source_channel: str, messages: List[Message], 
                              target_channels: List[Tuple[str, int, str]]):
        """
        转发消息到目标频道
        
        Args:
            source_channel: 源频道标识符
            messages: 消息列表
            target_channels: 目标频道列表(频道标识符, 频道ID, 频道信息)
        """
        # 检查源频道转发权限
        source_can_forward = await self.channel_resolver.check_forward_permission(source_channel)
        
        # 根据转发权限选择转发方式
        if source_can_forward:
            # 直接转发
            await self.forwarder._forward_media_group_directly(messages, source_channel, messages[0].chat.id, target_channels)
        else:
            # 下载后上传
            await self.forwarder._forward_media_group_via_download(messages, source_channel, messages[0].chat.id, target_channels)
        
        # 添加延迟
        await asyncio.sleep(self.monitor_config.forward_delay)
    
    def _is_media_allowed(self, message: Message) -> bool:
        """
        检查消息媒体类型是否在允许列表中
        
        Args:
            message: 消息对象
            
        Returns:
            bool: 是否允许
        """
        media_types = self.monitor_config.media_types
        
        if message.photo and "photo" in media_types:
            return True
        elif message.video and "video" in media_types:
            return True
        elif message.document and "document" in media_types:
            return True
        elif message.audio and "audio" in media_types:
            return True
        elif message.animation and "animation" in media_types:
            return True
        elif (message.text or message.caption) and "text" in media_types:
            return True
        
        return False 