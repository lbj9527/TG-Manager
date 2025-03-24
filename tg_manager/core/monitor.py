"""
监听器模块
监听源频道的新消息，实时触发转发逻辑
"""

import os
import asyncio
import time
import datetime
from typing import List, Dict, Any, Union, Optional, Set, Tuple
from functools import partial

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.handlers import MessageHandler

from tg_manager.utils.logger import get_logger
from tg_manager.services.channel_resolver import ChannelResolver
from tg_manager.services.history_manager import HistoryManager
from tg_manager.core.forwarder import Forwarder

logger = get_logger("monitor")


class Monitor:
    """
    监听器类，用于监听频道新消息并转发
    """
    
    def __init__(self, 
                 client: Client,
                 channel_resolver: ChannelResolver,
                 forwarder: Forwarder,
                 history_manager: HistoryManager,
                 media_types: List[str] = None,
                 remove_captions: bool = False,
                 forward_delay: float = 3.0,
                 message_filter: Optional[Dict[str, Any]] = None):
        """
        初始化监听器
        
        Args:
            client: Pyrogram客户端实例
            channel_resolver: 频道解析器实例
            forwarder: 转发器实例
            history_manager: 历史记录管理器实例
            media_types: 需要转发的媒体类型列表
            remove_captions: 是否移除原始消息的标题
            forward_delay: 转发延迟（秒）
            message_filter: 消息过滤规则
        """
        self.client = client
        self.channel_resolver = channel_resolver
        self.forwarder = forwarder
        self.history_manager = history_manager
        self.media_types = media_types or ["photo", "video", "document", "audio", "animation"]
        self.remove_captions = remove_captions
        self.forward_delay = forward_delay
        self.message_filter = message_filter
        
        # 活跃的监听任务
        self.active_monitors: Dict[str, Dict[str, Any]] = {}
        
        # 处理中的媒体组
        self.processing_media_groups: Set[str] = set()
        self.media_group_messages: Dict[str, List[Message]] = {}
        self.media_group_locks: Dict[str, asyncio.Lock] = {}
        
        # 用于控制监听任务的事件
        self.stop_events: Dict[str, asyncio.Event] = {}
    
    async def start_monitoring(self, 
                              source_channel: str, 
                              target_channels: List[str],
                              duration: Optional[str] = None) -> Dict[str, Any]:
        """
        开始监听源频道并转发新消息
        
        Args:
            source_channel: 源频道标识符
            target_channels: 目标频道列表
            duration: 监听持续时间，格式为"年-月-日-时"，如"2025-3-28-1"
            
        Returns:
            监听任务信息
        """
        # 检查是否已存在监听任务
        monitor_key = f"{source_channel}_{'-'.join(sorted(target_channels))}"
        if monitor_key in self.active_monitors:
            logger.warning(f"已存在监听任务: {monitor_key}")
            return {
                "status": "already_running",
                "monitor_id": monitor_key,
                "source_channel": source_channel,
                "target_channels": target_channels
            }
        
        # 获取源频道信息
        source_info = await self.channel_resolver.get_channel_info(source_channel)
        if not source_info:
            logger.error(f"无法获取源频道信息: {source_channel}")
            return {"status": "failed", "error": "无法获取源频道信息"}
        
        # 计算结束时间
        end_time = None
        if duration:
            try:
                # 解析持续时间，格式为"年-月-日-时"
                year, month, day, hour = map(int, duration.split("-"))
                end_time = datetime.datetime(year, month, day, hour)
                
                # 检查是否为过去时间
                now = datetime.datetime.now()
                if end_time < now:
                    logger.error(f"监听结束时间 {duration} 已过期")
                    return {"status": "failed", "error": "结束时间已过期"}
            except (ValueError, TypeError) as e:
                logger.error(f"无效的持续时间格式 {duration}: {e}")
                return {"status": "failed", "error": f"无效的持续时间格式: {e}"}
        
        # 创建停止事件
        stop_event = asyncio.Event()
        self.stop_events[monitor_key] = stop_event
        
        # 创建监听处理器
        handler = MessageHandler(
            partial(
                self._on_new_message, 
                source_channel=source_channel, 
                target_channels=target_channels, 
                monitor_key=monitor_key
            ),
            filters.chat(source_info.channel_id)
        )
        
        # 注册处理器
        self.client.add_handler(handler)
        
        # 记录监听任务信息
        self.active_monitors[monitor_key] = {
            "source_channel": source_channel,
            "target_channels": target_channels,
            "start_time": datetime.datetime.now(),
            "end_time": end_time,
            "handler": handler,
            "stats": {
                "total_messages": 0,
                "forwarded": 0,
                "skipped": 0,
                "failed": 0
            }
        }
        
        # 启动监控任务
        asyncio.create_task(self._monitor_task(monitor_key, end_time))
        
        logger.info(f"开始监听源频道 {source_info.title} ({source_info.channel_id}) 的新消息，"
                   f"目标频道: {', '.join(target_channels)}")
        
        return {
            "status": "success",
            "monitor_id": monitor_key,
            "source_channel": source_channel,
            "target_channels": target_channels,
            "start_time": self.active_monitors[monitor_key]["start_time"].isoformat(),
            "end_time": end_time.isoformat() if end_time else None
        }
    
    async def stop_monitoring(self, monitor_id: str) -> Dict[str, Any]:
        """
        停止指定的监听任务
        
        Args:
            monitor_id: 监听任务ID
            
        Returns:
            停止结果信息
        """
        if monitor_id not in self.active_monitors:
            logger.warning(f"监听任务不存在: {monitor_id}")
            return {"status": "failed", "error": "监听任务不存在"}
        
        # 触发停止事件
        self.stop_events[monitor_id].set()
        
        # 等待任务完全停止
        await asyncio.sleep(1)
        
        # 返回停止结果
        return {
            "status": "success",
            "monitor_id": monitor_id,
            "source_channel": self.active_monitors[monitor_id]["source_channel"],
            "target_channels": self.active_monitors[monitor_id]["target_channels"],
            "stats": self.active_monitors[monitor_id]["stats"]
        }
    
    async def stop_all_monitoring(self) -> Dict[str, Any]:
        """
        停止所有监听任务
        
        Returns:
            停止结果信息
        """
        results = {}
        
        for monitor_id in list(self.active_monitors.keys()):
            result = await self.stop_monitoring(monitor_id)
            results[monitor_id] = result
        
        return {
            "status": "success",
            "stopped_monitors": len(results),
            "results": results
        }
    
    async def get_active_monitors(self) -> Dict[str, Any]:
        """
        获取所有活跃的监听任务信息
        
        Returns:
            活跃监听任务信息
        """
        monitors = {}
        
        for monitor_id, info in self.active_monitors.items():
            monitors[monitor_id] = {
                "source_channel": info["source_channel"],
                "target_channels": info["target_channels"],
                "start_time": info["start_time"].isoformat(),
                "end_time": info["end_time"].isoformat() if info["end_time"] else None,
                "running_time": (datetime.datetime.now() - info["start_time"]).total_seconds(),
                "stats": info["stats"]
            }
        
        return {
            "status": "success",
            "count": len(monitors),
            "monitors": monitors
        }
    
    async def _monitor_task(self, monitor_id: str, end_time: Optional[datetime.datetime]) -> None:
        """
        监控任务，处理监听持续时间和停止事件
        
        Args:
            monitor_id: 监听任务ID
            end_time: 结束时间，如果为None则无限期运行
        """
        try:
            while True:
                # 检查停止事件
                if self.stop_events[monitor_id].is_set():
                    logger.info(f"监听任务 {monitor_id} 收到停止事件")
                    break
                
                # 检查结束时间
                if end_time and datetime.datetime.now() >= end_time:
                    logger.info(f"监听任务 {monitor_id} 已达到结束时间: {end_time}")
                    break
                
                # 定期检查
                await asyncio.sleep(60)
        
        except Exception as e:
            logger.error(f"监听任务 {monitor_id} 出错: {e}")
        
        finally:
            # 清理任务资源
            if monitor_id in self.active_monitors:
                # 移除处理器
                handler = self.active_monitors[monitor_id]["handler"]
                self.client.remove_handler(handler)
                
                # 记录统计信息
                logger.info(f"监听任务 {monitor_id} 已完成, 统计信息: {self.active_monitors[monitor_id]['stats']}")
                
                # 移除任务记录
                del self.active_monitors[monitor_id]
                
                # 移除停止事件
                if monitor_id in self.stop_events:
                    del self.stop_events[monitor_id]
    
    async def _on_new_message(self, 
                             client: Client, 
                             message: Message, 
                             source_channel: str, 
                             target_channels: List[str],
                             monitor_key: str) -> None:
        """
        新消息处理函数
        
        Args:
            client: Pyrogram客户端实例
            message: 新消息对象
            source_channel: 源频道标识符
            target_channels: 目标频道列表
            monitor_key: 监听任务ID
        """
        # 更新统计信息
        self.active_monitors[monitor_key]["stats"]["total_messages"] += 1
        
        try:
            # 检查消息类型
            media_type = self._get_media_type(message)
            if media_type not in self.media_types and media_type != "text":
                logger.debug(f"跳过不支持的媒体类型: {media_type}")
                self.active_monitors[monitor_key]["stats"]["skipped"] += 1
                return
            
            # 特殊处理媒体组
            if hasattr(message, 'media_group_id') and message.media_group_id:
                await self._handle_media_group(message, source_channel, target_channels, monitor_key)
            else:
                # 直接转发单条消息
                await self._forward_single_message(message, source_channel, target_channels, monitor_key)
        
        except Exception as e:
            logger.error(f"处理新消息 {message.id} 失败: {e}")
            self.active_monitors[monitor_key]["stats"]["failed"] += 1
    
    async def _handle_media_group(self, 
                                 message: Message, 
                                 source_channel: str, 
                                 target_channels: List[str],
                                 monitor_key: str) -> None:
        """
        处理媒体组消息
        
        Args:
            message: 媒体组中的一条消息
            source_channel: 源频道标识符
            target_channels: 目标频道列表
            monitor_key: 监听任务ID
        """
        media_group_id = message.media_group_id
        
        # 如果是新的媒体组，初始化锁和消息列表
        if media_group_id not in self.media_group_locks:
            self.media_group_locks[media_group_id] = asyncio.Lock()
            self.media_group_messages[media_group_id] = []
        
        # 获取锁，确保并发安全
        async with self.media_group_locks[media_group_id]:
            # 如果媒体组正在处理中，直接返回
            if media_group_id in self.processing_media_groups:
                return
            
            # 添加消息到列表
            self.media_group_messages[media_group_id].append(message)
            
            # 等待收集更多媒体组消息
            await asyncio.sleep(1)
            
            # 标记为处理中
            self.processing_media_groups.add(media_group_id)
        
        try:
            # 根据消息ID排序
            messages = sorted(self.media_group_messages[media_group_id], key=lambda m: m.id)
            
            # 使用转发器处理媒体组
            result = await self.forwarder._download_and_upload_media_group(
                messages, 
                {
                    target: (await self.channel_resolver.get_channel_info(target))
                    for target in target_channels
                    if await self.channel_resolver.get_channel_info(target)
                }
            )
            
            # 更新统计信息
            if result["status"] == "success":
                self.active_monitors[monitor_key]["stats"]["forwarded"] += len(messages)
            else:
                self.active_monitors[monitor_key]["stats"]["failed"] += len(messages)
        
        except Exception as e:
            logger.error(f"处理媒体组 {media_group_id} 失败: {e}")
            self.active_monitors[monitor_key]["stats"]["failed"] += 1
        
        finally:
            # 清理资源
            if media_group_id in self.media_group_messages:
                del self.media_group_messages[media_group_id]
            if media_group_id in self.media_group_locks:
                del self.media_group_locks[media_group_id]
            self.processing_media_groups.discard(media_group_id)
    
    async def _forward_single_message(self, 
                                     message: Message, 
                                     source_channel: str, 
                                     target_channels: List[str],
                                     monitor_key: str) -> None:
        """
        转发单条消息
        
        Args:
            message: 消息对象
            source_channel: 源频道标识符
            target_channels: 目标频道列表
            monitor_key: 监听任务ID
        """
        try:
            # 获取源频道信息
            source_info = await self.channel_resolver.get_channel_info(source_channel)
            if not source_info:
                logger.error(f"无法获取源频道信息: {source_channel}")
                self.active_monitors[monitor_key]["stats"]["failed"] += 1
                return
            
            # 获取目标频道信息
            target_infos = {}
            for target in target_channels:
                target_info = await self.channel_resolver.get_channel_info(target)
                if target_info:
                    target_infos[target] = target_info
            
            if not target_infos:
                logger.error("所有目标频道都无效")
                self.active_monitors[monitor_key]["stats"]["failed"] += 1
                return
            
            # 使用转发器进行转发
            if source_info.can_forward:
                result = await self.forwarder._forward_message_directly(message, target_infos)
            else:
                result = await self.forwarder._download_and_upload_single_message(message, target_infos)
            
            # 更新统计信息
            if result["status"] == "success":
                self.active_monitors[monitor_key]["stats"]["forwarded"] += 1
            else:
                self.active_monitors[monitor_key]["stats"]["failed"] += 1
        
        except Exception as e:
            logger.error(f"转发消息 {message.id} 失败: {e}")
            self.active_monitors[monitor_key]["stats"]["failed"] += 1
    
    def _get_media_type(self, message: Message) -> str:
        """
        获取消息的媒体类型
        
        Args:
            message: Pyrogram消息对象
            
        Returns:
            媒体类型字符串
        """
        if hasattr(message, 'photo') and message.photo:
            return "photo"
        elif hasattr(message, 'video') and message.video:
            return "video"
        elif hasattr(message, 'document') and message.document:
            return "document"
        elif hasattr(message, 'audio') and message.audio:
            return "audio"
        elif hasattr(message, 'animation') and message.animation:
            return "animation"
        elif hasattr(message, 'text') and message.text:
            return "text"
        else:
            return "unknown"
    
    def _should_filter_message(self, message: Message) -> bool:
        """
        检查消息是否应该被过滤
        
        Args:
            message: Pyrogram消息对象
            
        Returns:
            如果消息应该被过滤则返回True，否则返回False
        """
        # 如果没有设置过滤器，则不过滤任何消息
        if not self.message_filter:
            return False
        
        # TODO: 实现消息过滤逻辑
        # 这里可以根据self.message_filter规则检查消息内容、链接、表情等
        
        return False 