"""
媒体组处理器模块，负责处理和转发媒体组消息
"""

import asyncio
import time
import random
from pathlib import Path
from typing import List, Dict, Any, Tuple, Set
from datetime import datetime, timedelta

from pyrogram import Client
from pyrogram.types import (
    Message, InputMediaPhoto, InputMediaVideo, 
    InputMediaDocument, InputMediaAudio, InputMediaAnimation
)
from pyrogram.errors import FloodWait, ChatForwardsRestricted

from src.utils.channel_resolver import ChannelResolver
from src.utils.logger import get_logger
from src.modules.monitor.text_filter import TextFilter
from src.modules.monitor.restricted_forward_handler import RestrictedForwardHandler
from src.modules.forward.parallel_processor import ParallelProcessor

# 导入消息处理器，但避免循环导入
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.modules.monitor.message_processor import MessageProcessor

logger = get_logger()

class MediaGroupHandler:
    """
    媒体组处理器，负责处理和转发媒体组消息
    """
    
    def __init__(self, client: Client, channel_resolver: ChannelResolver, message_processor):
        """
        初始化媒体组处理器
        
        Args:
            client: Pyrogram客户端实例
            channel_resolver: 频道解析器实例
            message_processor: 消息处理器实例
        """
        self.client = client
        self.channel_resolver = channel_resolver
        self.message_processor = message_processor
        
        # 媒体组相关缓存
        self.media_group_cache = {}  # {channel_id: {media_group_id: {'messages': [], 'first_message_time': float, 'last_update_time': float, 'pair_config': dict}}}
        self.processed_media_groups = set()  # 已处理的媒体组ID集合
        self.fetching_media_groups = set()  # 正在获取的媒体组ID集合
        self.media_group_filter_stats = {}  # 媒体组过滤统计 {media_group_id: {'total_expected': int, 'filtered_count': int, 'total_received': int, 'original_caption': str}}
        self.channel_pairs = {}  # 频道对配置
        self.is_stopping = False  # 停止标志
        
        # 添加延迟检查任务跟踪，避免重复创建任务
        self.pending_delay_tasks = {}  # {media_group_id: asyncio.Task}
        
        # 媒体组处理相关配置
        self.media_group_timeout = 30  # 媒体组超时时间（秒）
        self.media_group_locks = {}  # 媒体组锁字典 {lock_key: asyncio.Lock}
        
        # 清理任务相关
        self.last_processed_groups_cleanup = time.time()  # 上次清理已处理媒体组的时间
        self.last_media_group_fetch = {}  # 媒体组获取时间记录
        
        # 消息积压处理
        self.message_backlog = {}  # 消息积压队列，改为字典结构 {channel_id: {media_group_id: (message, pair_config)}}
        self.is_processing_backlog = False  # 是否正在处理积压
        
        # API请求队列
        self.api_request_queue = asyncio.Queue()
        self.api_worker_task = None
        
        # API频率控制
        self.global_last_api_call = 0
        self.global_api_interval = 0.1  # 全局API调用间隔
        self.api_semaphore = asyncio.Semaphore(3)  # 最多3个并发API请求
        
        # 事件发射器
        self.emit = getattr(message_processor, 'emit', None)
        
        # 启动后台任务
        self.cleanup_task = None
        self.backlog_task = None
        
        logger.debug("MediaGroupHandler 初始化完成")
    
    def set_channel_pairs(self, channel_pairs: Dict[int, Dict[str, Any]]):
        """
        设置频道对应关系配置
        
        Args:
            channel_pairs: 频道对应关系配置字典
        """
        self.channel_pairs = channel_pairs
    
    def start_cleanup_task(self):
        """启动媒体组清理任务"""
        if self.cleanup_task is None:
            self.cleanup_task = asyncio.create_task(self._cleanup_media_groups())
            logger.debug("媒体组清理任务已启动")
            
        if self.backlog_task is None:
            self.backlog_task = asyncio.create_task(self._process_message_backlog())
            logger.debug("积压消息处理任务已启动")
    
    async def stop(self):
        """停止媒体组处理器"""
        self.is_stopping = True
        
        # 取消媒体组清理任务
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"取消媒体组清理任务时异常: {str(e)}", error_type="TASK_CANCEL", recoverable=True)
            
            self.cleanup_task = None
            
        # 取消已处理媒体组清理任务
        if self.backlog_task:
            self.backlog_task.cancel()
            try:
                await self.backlog_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"取消已处理媒体组清理任务时异常: {str(e)}", error_type="TASK_CANCEL", recoverable=True)
            
            self.backlog_task = None
            
        # 取消API请求处理任务
        if self.api_worker_task:
            self.api_worker_task.cancel()
            try:
                await self.api_worker_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"取消API请求处理任务时异常: {str(e)}", error_type="TASK_CANCEL", recoverable=True)
                
            self.api_worker_task = None
            
        # 取消积压消息处理任务
        if self.backlog_task:
            self.backlog_task.cancel()
            try:
                await self.backlog_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"取消积压消息处理任务时异常: {str(e)}", error_type="TASK_CANCEL", recoverable=True)
                
            self.backlog_task = None
        
        # 清空媒体组缓存
        self.media_group_cache.clear()
        self.processed_media_groups.clear()
        self.fetching_media_groups.clear()
        self.media_group_filter_stats.clear()
        self.channel_pairs.clear()
        self.pending_delay_tasks.clear()
        self.message_backlog.clear()
        self.media_group_locks.clear()
        self.last_media_group_fetch.clear()
        logger.info("已清理所有媒体组缓存")
    
    async def _cleanup_processed_groups(self):
        """定期清理已处理媒体组ID集合，防止集合无限增长"""
        try:
            while not self.is_stopping:
                await asyncio.sleep(300)  # 每5分钟清理一次
                
                if self.is_stopping:
                    break
                
                now = time.time()
                # 每小时清理一次已处理媒体组集合
                if now - self.last_processed_groups_cleanup > 3600:
                    previous_count = len(self.processed_media_groups)
                    if previous_count > 1000:
                        logger.info(f"清理已处理媒体组记录，当前数量: {previous_count}")
                        self.processed_media_groups.clear()
                        logger.info(f"已清理 {previous_count} 条已处理媒体组记录")
                    
                    # 同时清理媒体组获取时间记录
                    old_fetch_time_count = len(self.last_media_group_fetch)
                    if old_fetch_time_count > 0:
                        self.last_media_group_fetch.clear()
                        logger.debug(f"已清理 {old_fetch_time_count} 条媒体组获取时间记录")
                    
                    # 清理可能残留的获取标记
                    if self.fetching_media_groups:
                        old_fetch_count = len(self.fetching_media_groups)
                        self.fetching_media_groups.clear()
                        logger.debug(f"已清理 {old_fetch_count} 条媒体组获取标记")
                        
                    self.last_processed_groups_cleanup = now
                    
        except asyncio.CancelledError:
            logger.info("已处理媒体组清理任务已取消")
        except Exception as e:
            logger.error(f"清理已处理媒体组时异常: {str(e)}", error_type="CLEANUP", recoverable=True)
        
    async def _cleanup_media_groups(self):
        """定期检查和处理超时的媒体组（作为备用机制）"""
        try:
            while not self.is_stopping:
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
                                            # 检查媒体组是否已处理
                                            if group_id in self.processed_media_groups:
                                                logger.debug(f"媒体组 {group_id} 已被处理，跳过超时处理")
                                            else:
                                                # 处理媒体组消息
                                                logger.info(f"处理超时媒体组: {group_id}, 共有 {len(messages)} 条消息")
                                                await self._process_media_group(messages, pair_config)
                                                # 标记为已处理
                                                self.processed_media_groups.add(group_id)
                                        
                                        # 从缓存中移除此媒体组
                                        del self.media_group_cache[channel_id][group_id]
                                        
                                        # 如果此频道没有更多媒体组，移除整个频道条目
                                        if not self.media_group_cache[channel_id]:
                                            del self.media_group_cache[channel_id]
                                            
                                # 移除获取标记，如果存在的话
                                if group_id in self.fetching_media_groups:
                                    self.fetching_media_groups.remove(group_id)
                                            
                            except Exception as e:
                                logger.error(f"处理超时媒体组 {group_id} 时出错: {str(e)}", error_type="MEDIA_GROUP_TIMEOUT", recoverable=True)
                                # 尽管出错，仍然尝试从缓存中移除
                                try:
                                    if channel_id in self.media_group_cache and group_id in self.media_group_cache[channel_id]:
                                        del self.media_group_cache[channel_id][group_id]
                                except Exception:
                                    pass
                                
                                # 移除获取标记，如果存在的话
                                try:
                                    if group_id in self.fetching_media_groups:
                                        self.fetching_media_groups.remove(group_id)
                                except Exception:
                                    pass
                                
        except asyncio.CancelledError:
            logger.info("媒体组清理任务已取消")
        except Exception as e:
            logger.error(f"媒体组清理任务异常: {str(e)}", error_type="MEDIA_GROUP_CLEANUP", recoverable=True)
            
    async def handle_media_group_message(self, message: Message, pair_config: dict):
        """处理媒体组消息
        
        Args:
            message: 媒体组中的一条消息
            pair_config: 频道对配置
        """
        # 获取该频道对的过滤选项
        keywords = pair_config.get('keywords', [])
        exclude_forwards = pair_config.get('exclude_forwards', False)
        exclude_replies = pair_config.get('exclude_replies', False)
        # 兼容性处理：先尝试读取exclude_text，如果没有则从exclude_media转换
        exclude_text = pair_config.get('exclude_text', pair_config.get('exclude_media', False))
        exclude_links = pair_config.get('exclude_links', False)
        
        # 应用过滤逻辑
        if exclude_forwards and message.forward_from:
            filter_reason = "转发消息"
            logger.info(f"媒体组消息 [ID: {message.id}] 是{filter_reason}，根据过滤规则跳过")
            self._emit_message_filtered(message, filter_reason)
            return
        
        if exclude_replies and message.reply_to_message:
            filter_reason = "回复消息"
            logger.info(f"媒体组消息 [ID: {message.id}] 是{filter_reason}，根据过滤规则跳过")
            self._emit_message_filtered(message, filter_reason)
            return
        
        # 检查是否为媒体消息
        is_media_message = bool(message.photo or message.video or message.document or 
                              message.audio or message.animation or message.sticker or 
                              message.voice or message.video_note)
        
        # 检查是否为纯文本消息（非媒体消息）
        is_text_message = not is_media_message
        
        if exclude_text and is_text_message:
            filter_reason = "纯文本消息"
            logger.info(f"媒体组消息 [ID: {message.id}] 是{filter_reason}，根据过滤规则跳过")
            self._emit_message_filtered(message, filter_reason)
            return
        
        if exclude_links:
            text_content = message.text or message.caption or ""
            if self._contains_links(text_content) or (message.entities and any(entity.type in ["url", "text_link"] for entity in message.entities)):
                filter_reason = "包含链接"
                logger.info(f"媒体组消息 [ID: {message.id}] {filter_reason}，根据过滤规则跳过")
                self._emit_message_filtered(message, filter_reason)
                return
        
        # 关键词过滤
        if keywords:
            text_content = message.text or message.caption or ""
            if not any(keyword.lower() in text_content.lower() for keyword in keywords):
                filter_reason = f"不包含关键词({', '.join(keywords)})"
                logger.info(f"媒体组消息 [ID: {message.id}] {filter_reason}，根据过滤规则跳过")
                self._emit_message_filtered(message, filter_reason)
                return
        
        # 媒体类型过滤 - 这里是关键的修改
        allowed_media_types = pair_config.get('media_types', [])
        message_media_type = self._get_message_media_type(message)
        
        # 获取媒体组ID和预期消息数量
        media_group_id = message.media_group_id
        expected_count = getattr(message, 'media_group_count', None)
        
        # 初始化媒体组过滤统计
        if media_group_id not in self.media_group_filter_stats:
            self.media_group_filter_stats[media_group_id] = {
                'total_expected': expected_count or 0,
                'filtered_count': 0,
                'total_received': 0,
                'original_caption': None  # 保存原始媒体组标题
            }
            
        # 保存原始标题（如果当前消息有标题且还没有保存过）
        if message.caption and not self.media_group_filter_stats[media_group_id]['original_caption']:
            self.media_group_filter_stats[media_group_id]['original_caption'] = message.caption
            logger.debug(f"保存媒体组 {media_group_id} 的原始标题: '{message.caption}'")
        
        # 更新统计：总接收数
        self.media_group_filter_stats[media_group_id]['total_received'] += 1
        
        if message_media_type and not self._is_media_type_allowed(message_media_type, allowed_media_types):
            media_type_names = {
                "photo": "照片", "video": "视频", "document": "文件", "audio": "音频",
                "animation": "动画", "sticker": "贴纸", "voice": "语音", "video_note": "视频笔记"
            }
            media_type_name = media_type_names.get(message_media_type.value, message_media_type.value)
            filter_reason = f"媒体类型({media_type_name})不在允许列表中"
            logger.info(f"媒体组消息 [ID: {message.id}] 的{filter_reason}，跳过处理")
            
            # 更新统计：过滤数
            self.media_group_filter_stats[media_group_id]['filtered_count'] += 1
            
            self._emit_message_filtered(message, filter_reason)
            return  # 直接返回，不添加到缓存
        
        # 只有通过了所有过滤的消息才会添加到缓存
        channel_id = message.chat.id
        
        # 检查媒体组是否已被处理
        if media_group_id in self.processed_media_groups:
            logger.debug(f"媒体组 {media_group_id} 已被处理，跳过消息 [ID: {message.id}]")
            return
            
        # 检查是否已有相同媒体组在获取中
        if media_group_id in self.fetching_media_groups:
            # 如果已经在获取中，添加到缓存
            await self._add_message_to_cache(message, media_group_id, channel_id, pair_config)
            return
            
        # 检查缓存中是否已有此媒体组的消息
        if (channel_id in self.media_group_cache and 
            media_group_id in self.media_group_cache[channel_id]):
            # 添加到现有缓存
            await self._add_message_to_cache(message, media_group_id, channel_id, pair_config)
            return
                
        # 新的媒体组，检查是否应该使用API获取完整媒体组
        message_count_in_group = getattr(message, 'media_group_count', None)
        
        if message_count_in_group and message_count_in_group > 1:
            # 尝试使用API获取完整媒体组
            logger.info(f"媒体组 {media_group_id} 包含 {message_count_in_group} 条消息，尝试API获取")
            
            # 检查API调用频率限制
            current_time = time.time()
            last_fetch_time = self.last_media_group_fetch.get(media_group_id, 0)
            
            if current_time - last_fetch_time < 1.0:  # 1秒内不重复获取
                logger.debug(f"媒体组 {media_group_id} 最近已获取过，跳过API调用")
                await self._add_message_to_cache(message, media_group_id, channel_id, pair_config)
                return
            
            # 检查当前缓存的消息数量
            cached_count = 0
            if (channel_id in self.media_group_cache and 
                media_group_id in self.media_group_cache[channel_id]):
                cached_count = len(self.media_group_cache[channel_id][media_group_id]['messages'])
            
            # 如果缓存中已有足够多的消息，跳过API调用
            if cached_count >= 8:
                logger.info(f"媒体组 {media_group_id} 在缓存中已有 {cached_count} 条消息，跳过API调用")
                await self._add_message_to_cache(message, media_group_id, channel_id, pair_config)
                return
            
            # 将请求加入队列
            try:
                self.api_request_queue.put_nowait((channel_id, message.id, media_group_id, message, pair_config))
                logger.debug(f"已将媒体组 {media_group_id} 的API请求加入队列")
            except asyncio.QueueFull:
                logger.warning(f"API请求队列已满，直接处理媒体组 {media_group_id}")
                await self._add_message_to_cache(message, media_group_id, channel_id, pair_config)
        else:
            # 单条消息或无法获取计数，直接添加到缓存
            await self._add_message_to_cache(message, media_group_id, channel_id, pair_config)
    
    async def _add_message_to_cache(self, message: Message, media_group_id: str, channel_id: int, pair_config: dict):
        """将消息添加到媒体组缓存
        
        Args:
            message: 媒体组消息
            media_group_id: 媒体组ID
            channel_id: 频道ID
            pair_config: 频道对配置
        """
        # 确保频道存在于缓存中
        if channel_id not in self.media_group_cache:
            self.media_group_cache[channel_id] = {}
            
        # 如果媒体组不存在，创建它
        if media_group_id not in self.media_group_cache[channel_id]:
            self.media_group_cache[channel_id][media_group_id] = {
                'messages': [],
                'first_message_time': time.time(),  # 记录第一条消息的时间
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
        
        # 检查是否应该处理媒体组
        should_process = False
        process_reason = ""
        
        # 1. 如果我们接收到了整个媒体组（根据media_group_count），处理它
        if (hasattr(message, 'media_group_count') and 
            message.media_group_count is not None and 
            len(messages) >= message.media_group_count):
            should_process = True
            process_reason = f"已完整接收 ({len(messages)}/{message.media_group_count})"
        # 2. 如果从第一条消息开始已经超过5秒，强制处理避免永远等待
        elif time.time() - group_data['first_message_time'] > 5:
            should_process = True
            process_reason = f"等待超时 ({len(messages)} 条消息，等待 {time.time() - group_data['first_message_time']:.1f}s)"
        # 3. 如果消息数量达到阈值（10条），强制处理避免内存占用
        elif len(messages) >= 10:
            should_process = True
            process_reason = f"消息数量达到阈值 ({len(messages)} 条消息)"
        
        if should_process:
            logger.info(f"媒体组 {media_group_id} {process_reason}，开始处理")
            # 标记为已处理
            self.processed_media_groups.add(media_group_id)
            # 处理完整的媒体组
            await self._process_media_group(messages, pair_config)
            
            # 从缓存中删除此媒体组
            del self.media_group_cache[channel_id][media_group_id]
            
            # 如果此频道没有更多媒体组，移除整个频道条目
            if not self.media_group_cache[channel_id]:
                del self.media_group_cache[channel_id]
                
            # 移除获取标记，如果存在的话
            if media_group_id in self.fetching_media_groups:
                self.fetching_media_groups.remove(media_group_id)
                
            # 清理延迟任务引用，如果存在的话
            if media_group_id in self.pending_delay_tasks:
                # 取消正在等待的延迟任务
                delay_task = self.pending_delay_tasks[media_group_id]
                if not delay_task.done():
                    delay_task.cancel()
                del self.pending_delay_tasks[media_group_id]
        else:
            # 如果当前消息较少，安排一个延迟检查任务
            # 修改：增加延迟检查的触发条件，确保及时处理媒体组
            if len(messages) <= 5:  # 从3增加到5，确保更多情况下有延迟检查
                # 避免为同一个媒体组重复创建延迟任务
                if media_group_id not in self.pending_delay_tasks:
                    # 延迟5秒后检查是否需要处理，给更多时间收集消息
                    delay_task = asyncio.create_task(self._delayed_media_group_check(media_group_id, channel_id, 5.0))
                    self.pending_delay_tasks[media_group_id] = delay_task
    
    async def _delayed_media_group_check(self, media_group_id: str, channel_id: int, delay: float):
        """延迟检查媒体组是否需要处理
        
        Args:
            media_group_id: 媒体组ID
            channel_id: 频道ID  
            delay: 延迟时间(秒)
        """
        try:
            await asyncio.sleep(delay)
            
            # 检查媒体组是否已被处理
            if media_group_id in self.processed_media_groups:
                return
            
            # 检查媒体组是否还在缓存中
            if (channel_id not in self.media_group_cache or 
                media_group_id not in self.media_group_cache[channel_id]):
                return
            
            group_data = self.media_group_cache[channel_id][media_group_id]
            messages = group_data['messages']
            pair_config = group_data['pair_config']
            
            # 修复：使用last_update_time而不是first_message_time来判断是否超时
            # 这样确保最后一条消息收到后有足够的等待时间
            time_since_last_update = time.time() - group_data['last_update_time']
            time_since_first_message = time.time() - group_data['first_message_time']
            
            # 如果距离最后更新已经超过3秒，或者距离第一条消息超过10秒，且消息数量大于0，则强制处理
            should_process = (
                (time_since_last_update > 3.0 and len(messages) > 0) or
                (time_since_first_message > 10.0 and len(messages) > 0)
            )
            
            if should_process:
                logger.info(f"延迟检查: 媒体组 {media_group_id} 收集到 {len(messages)} 条消息，"
                           f"距离最后更新 {time_since_last_update:.1f}s，距离第一条消息 {time_since_first_message:.1f}s，强制处理避免丢失")
                
                # 标记为已处理
                self.processed_media_groups.add(media_group_id)
                # 处理媒体组
                await self._process_media_group(messages, pair_config)
                
                # 从缓存中删除此媒体组
                del self.media_group_cache[channel_id][media_group_id]
                
                # 如果此频道没有更多媒体组，移除整个频道条目
                if not self.media_group_cache[channel_id]:
                    del self.media_group_cache[channel_id]
                    
                # 移除获取标记，如果存在的话
                if media_group_id in self.fetching_media_groups:
                    self.fetching_media_groups.remove(media_group_id)
                
                # 清理延迟任务引用，如果存在的话
                if media_group_id in self.pending_delay_tasks:
                    # 取消正在等待的延迟任务
                    delay_task = self.pending_delay_tasks[media_group_id]
                    if not delay_task.done():
                        delay_task.cancel()
                    del self.pending_delay_tasks[media_group_id]
            
        except Exception as e:
            logger.error(f"延迟检查媒体组 {media_group_id} 时出错: {str(e)}")
        finally:
            # 清理延迟任务引用，无论是否成功处理
            if media_group_id in self.pending_delay_tasks:
                del self.pending_delay_tasks[media_group_id]
    
    async def _process_media_group(self, messages: List[Message], pair_config: dict):
        """
        处理媒体组消息
        
        Args:
            messages: 媒体组消息列表
            pair_config: 频道对配置
        """
        if not messages:
            return
            
        try:
            # 获取源频道信息
            source_id = messages[0].chat.id
            source_channel = pair_config['source_channel']
            source_title = pair_config.get('source_title', str(source_id))
            
            # 获取目标频道列表
            target_channels = pair_config.get('target_channels', [])
            if not target_channels:
                logger.warning(f"没有有效的目标频道，跳过媒体组处理")
                return
                
            # 获取媒体组ID
            media_group_id = messages[0].media_group_id
            
            # 获取媒体组过滤统计
            filter_stats = self.media_group_filter_stats.get(media_group_id, {
                'total_expected': 0,
                'filtered_count': 0,
                'total_received': 0
            })
            
            # 计算实际情况
            total_received = filter_stats['total_received']
            filtered_count = filter_stats['filtered_count']
            in_cache_count = len(messages)  # 当前缓存中的消息数（都是通过过滤的）
            
            logger.info(f"媒体组 {media_group_id} 统计: 总接收={total_received}, 已过滤={filtered_count}, 缓存中={in_cache_count}")
            
            # 检查是否有消息被过滤
            has_filtered_messages = filtered_count > 0
            
            # 检查是否需要重组媒体组
            if has_filtered_messages and in_cache_count > 1:
                # 有消息被过滤且剩余消息>1，需要重组媒体组发送
                logger.info(f"媒体组 {media_group_id} 有 {filtered_count} 条消息被过滤，剩余 {in_cache_count} 条消息，将重组发送")
                await self._send_filtered_media_group(messages, pair_config, target_channels)
                
                # 清理过滤统计
                if media_group_id in self.media_group_filter_stats:
                    del self.media_group_filter_stats[media_group_id]
                return
            elif has_filtered_messages and in_cache_count == 1:
                # 只剩一条消息，作为单条消息发送
                logger.info(f"媒体组 {media_group_id} 有 {filtered_count} 条消息被过滤，只剩 1 条消息，将作为单条消息发送")
                single_message = messages[0]
                # 这里需要调用单条消息的转发逻辑
                # 由于这是媒体组处理器，我们暂时跳过单条消息处理
                # 可以通过消息处理器来处理单条消息
                if hasattr(self, 'message_processor') and self.message_processor:
                    # 获取目标频道列表
                    target_channels = pair_config.get('target_channels', [])
                    text_filter = pair_config.get('text_filter', [])
                    remove_captions = pair_config.get('remove_captions', False)
                    
                    # 应用文本替换规则（如果有）
                    replaced_caption = None
                    if single_message.caption:
                        # 优先使用已经构建好的text_replacements，如果没有则从text_filter构建
                        text_replacements = pair_config.get('text_replacements', {})
                        if not text_replacements:
                            # 如果没有预构建的text_replacements，从text_filter构建
                            text_filter = pair_config.get('text_filter', [])
                            text_replacements = {}
                            for rule in text_filter:
                                original_text = rule.get('original_text', '')
                                target_text = rule.get('target_text', '')
                                if original_text:
                                    text_replacements[original_text] = target_text
                        
                        # 使用静态方法应用文本替换
                        if text_replacements:
                            from src.modules.monitor.text_filter import TextFilter
                            replaced_caption = TextFilter.apply_text_replacements_static(single_message.caption, text_replacements)
                            logger.info(f"单条消息 [ID: {single_message.id}] 应用文本替换：'{single_message.caption}' -> '{replaced_caption}'")
                        else:
                            replaced_caption = single_message.caption
                    # 如果消息没有标题，replaced_caption保持为None
                    else:
                        replaced_caption = None
                
                    # 使用消息处理器的forward_message方法转发单条消息
                    if replaced_caption is not None:
                        # 有标题（原始或替换后的），传递replace_caption参数
                        await self.message_processor.forward_message(
                            message=single_message,
                            target_channels=target_channels,
                            use_copy=True,
                            replace_caption=replaced_caption,
                            remove_caption=remove_captions
                        )
                    else:
                        # 没有标题，不传递replace_caption参数
                        await self.message_processor.forward_message(
                            message=single_message,
                            target_channels=target_channels,
                            use_copy=True,
                            remove_caption=remove_captions
                        )
                
                # 清理过滤统计
                if media_group_id in self.media_group_filter_stats:
                    del self.media_group_filter_stats[media_group_id]
                return
            elif has_filtered_messages and in_cache_count == 0:
                # 所有消息都被过滤
                logger.info(f"媒体组 {media_group_id} 中的所有消息都被过滤，跳过转发")
                    
                # 清理过滤统计
                if media_group_id in self.media_group_filter_stats:
                    del self.media_group_filter_stats[media_group_id]
                return
            
            # 如果没有被过滤，使用原有逻辑
            logger.info(f"媒体组 {media_group_id} 未被过滤，使用原有转发逻辑")
                        
            # 清理过滤统计
            if media_group_id in self.media_group_filter_stats:
                del self.media_group_filter_stats[media_group_id]
            
            # 获取文本替换处理后的标题
            replaced_caption = None
            caption_modified = False
            
            # 检查第一条消息是否有标题需要处理
            first_message = messages[0]
            if first_message.caption:
                # 优先使用已经构建好的text_replacements，如果没有则从text_filter构建
                text_replacements = pair_config.get('text_replacements', {})
                if not text_replacements:
                    # 如果没有预构建的text_replacements，从text_filter构建
                    text_filter = pair_config.get('text_filter', [])
                    text_replacements = {}
                    for rule in text_filter:
                        original_text = rule.get('original_text', '')
                        target_text = rule.get('target_text', '')
                        if original_text:
                            text_replacements[original_text] = target_text
                
                # 使用静态方法应用文本替换
                if text_replacements:
                    from src.modules.monitor.text_filter import TextFilter
                    replaced_caption = TextFilter.apply_text_replacements_static(first_message.caption, text_replacements)
                    caption_modified = replaced_caption != first_message.caption
                else:
                    replaced_caption = first_message.caption
                    caption_modified = False
            else:
                replaced_caption = None
                caption_modified = False
            
            # 获取移除媒体说明的设置
            remove_captions = pair_config.get('remove_captions', False)
            
            # 使用原有的转发逻辑，messages参数中的消息都已经通过过滤
            await self._forward_media_group(
                messages, 
                target_channels, 
                replaced_caption, 
                remove_captions, 
                caption_modified
            )
                
        except Exception as e:
            logger.error(f"处理媒体组时发生错误: {str(e)}", error_type="PROCESS_MEDIA_GROUP", recoverable=True)
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"错误详情: {error_details}")
    
    async def _forward_media_group(self, messages: List[Message], target_channels: List[Tuple[str, int, str]], 
                                 replaced_caption: str = None, remove_captions: bool = False, caption_modified: bool = False):
        """
        转发媒体组到目标频道
        
        Args:
            messages: 媒体组消息列表
            target_channels: 目标频道列表
            replaced_caption: 替换后的标题文本
            remove_captions: 是否移除标题
            caption_modified: 是否修改了标题
        """
        if not messages or not target_channels:
            return
            
        try:
            source_chat = messages[0].chat
            source_chat_id = source_chat.id
            media_group_id = messages[0].media_group_id
            
            # 尝试获取频道信息
            try:
                source_title = source_chat.title
            except:
                source_title = str(source_chat_id)
                
            # 排序消息，确保顺序一致
            sorted_messages = sorted(messages, key=lambda m: m.id)
            first_message_id = sorted_messages[0].id
            message_ids = [msg.id for msg in sorted_messages]
            
            logger.info(f"开始转发媒体组 [ID: {media_group_id}] 从 {source_title} 到 {len(target_channels)} 个目标频道")
            
            # 标题处理
            if remove_captions:
                # 移除媒体说明
                logger.debug(f"将移除媒体组的说明文字")
                await self._send_modified_media_group(sorted_messages, None, target_channels, caption_modified)
            elif replaced_caption is not None:
                # 如果有替换后的标题
                logger.debug(f"将使用替换后的标题: '{replaced_caption}'")
                await self._send_modified_media_group(sorted_messages, replaced_caption, target_channels, caption_modified)
            else:
                # 使用原始标题或没有标题
                # 先尝试第一个目标频道
                first_target = target_channels[0]
                success = await self._forward_media_group_to_target(
                    source_chat_id, first_target[1], first_target[2],
                    first_message_id, message_ids, media_group_id, source_title, caption_modified
                )
                
                if success and len(target_channels) > 1:
                    # 成功转发到第一个目标频道，从第一个目标频道复制到其余目标频道
                    other_targets = target_channels[1:]
                    logger.info(f"将从第一个目标频道复制媒体组到其他 {len(other_targets)} 个目标频道")
                    
                    for target, target_id, target_info in other_targets:
                        try:
                            # 使用copy_media_group从第一个目标频道复制
                            await self.client.copy_media_group(
                                chat_id=target_id,
                                from_chat_id=first_target[1],
                                message_id=first_message_id
                            )
                            logger.info(f"已将媒体组复制到 {target_info}")
                            
                            # 发射媒体组转发成功事件 - 只发射一次整体事件
                            if self.emit:
                                # 尝试获取源频道信息
                                try:
                                    source_info_str, _ = await self.channel_resolver.format_channel_info(source_chat_id)
                                except Exception:
                                    source_info_str = str(source_chat_id)
                                
                                # 生成媒体组显示ID
                                media_group_display_id = self._generate_media_group_display_id(message_ids)
                                
                                # 只发射一次媒体组整体的转发成功事件
                                self.emit("forward", media_group_display_id, source_info_str, target_info, True, modified=caption_modified)
                        except Exception as e:
                            logger.error(f"从第一个目标频道复制媒体组到 {target_info} 失败: {str(e)}", 
                                       error_type="COPY_MEDIA_GROUP", recoverable=True)
                        
                        # 添加延迟避免触发限制
                        await asyncio.sleep(0.5)
                elif not success:
                    # 第一个目标频道转发失败，尝试逐个发送到所有目标频道
                    logger.warning(f"转发媒体组到第一个目标频道失败，尝试逐个发送到所有目标频道")
                    
                    # 逐个发送到每个目标频道（包括第一个，因为它失败了）
                    for target, target_id, target_info in target_channels:
                        try:
                            success = await self._forward_media_group_to_target(
                                source_chat_id, target_id, target_info,
                                first_message_id, message_ids, media_group_id, source_title, caption_modified
                            )
                            if success:
                                logger.info(f"逐个发送模式下成功转发媒体组到 {target_info}")
                            else:
                                logger.warning(f"逐个发送模式下转发媒体组到 {target_info} 失败")
                        except Exception as e:
                            logger.error(f"转发媒体组到 {target_info} 失败: {str(e)}", 
                                       error_type="FORWARD_MEDIA_GROUP", recoverable=True)
                        
                        # 添加延迟避免触发限制
                        await asyncio.sleep(0.5)
                        
        except Exception as e:
            logger.error(f"转发媒体组失败: {str(e)}", error_type="FORWARD_MEDIA_GROUP", recoverable=True)
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"错误详情: {error_details}")
            
            # 发射转发失败事件 - 只发射一次整体事件
            if self.emit:
                # 尝试获取源频道信息
                try:
                    source_info_str, _ = await self.channel_resolver.format_channel_info(source_chat_id)
                except Exception:
                    source_info_str = str(source_chat_id)
                
                # 生成媒体组显示ID
                media_group_display_id = self._generate_media_group_display_id(message_ids)
                
                # 为每个目标频道发射一次媒体组整体的转发失败事件
                for target, target_id, target_info in target_channels:
                    self.emit("forward", media_group_display_id, source_info_str, target_info, False)
            
            return False
    
    async def _forward_media_group_to_target(self, source_chat_id: int, target_id: int, target_info: str,
                                          first_message_id: int, message_ids: List[int], 
                                          media_group_id: str, source_title: str, caption_modified: bool) -> bool:
        """
        转发媒体组到指定目标频道
        
        Args:
            source_chat_id: 源频道ID
            target_id: 目标频道ID
            target_info: 目标频道信息
            first_message_id: 第一条消息ID
            message_ids: 所有消息ID列表
            media_group_id: 媒体组ID
            source_title: 源频道标题
            caption_modified: 是否修改了标题
            
        Returns:
            bool: 是否成功转发
        """
        try:
            logger.info(f"转发媒体组 {media_group_id} 到 {target_info}")
            
            # 优先使用copy_media_group
            try:
                await self.client.copy_media_group(
                    chat_id=target_id,
                    from_chat_id=source_chat_id,
                    message_id=first_message_id
                )
                logger.info(f"已使用copy_media_group成功转发媒体组到 {target_info}")
                
                # 发射媒体组转发成功事件 - 只发射一次整体事件
                if self.emit:
                    # 尝试获取源频道信息
                    try:
                        source_info_str, _ = await self.channel_resolver.format_channel_info(source_chat_id)
                    except Exception:
                        source_info_str = str(source_chat_id)
                    
                    # 生成媒体组显示ID
                    media_group_display_id = self._generate_media_group_display_id(message_ids)
                    
                    # 只发射一次媒体组整体的转发成功事件
                    self.emit("forward", media_group_display_id, source_info_str, target_info, True, modified=caption_modified)
                
                return True
            except ChatForwardsRestricted:
                logger.warning(f"目标频道 {target_info} 禁止转发，尝试使用forward_messages")
                # 如果禁止转发，尝试使用forward_messages
                try:
                    # 尝试直接转发
                    await self.client.forward_messages(
                        chat_id=target_id,
                        from_chat_id=source_chat_id,
                        message_ids=message_ids
                    )
                    logger.info(f"已使用forward_messages成功转发媒体组到 {target_info}")
                    
                    # 发射媒体组转发成功事件 - 只发射一次整体事件
                    if self.emit:
                        # 尝试获取源频道信息
                        try:
                            source_info_str, _ = await self.channel_resolver.format_channel_info(source_chat_id)
                        except Exception:
                            source_info_str = str(source_chat_id)
                        
                        # 生成媒体组显示ID
                        media_group_display_id = self._generate_media_group_display_id(message_ids)
                        
                        # 只发射一次媒体组整体的转发成功事件
                        self.emit("forward", media_group_display_id, source_info_str, target_info, True, modified=caption_modified)
                    
                    return True
                except Exception as forward_e:
                    logger.warning(f"使用forward_messages失败: {str(forward_e)}，尝试单条发送")
                    return False
            except Exception as copy_e:
                logger.warning(f"使用copy_media_group失败: {str(copy_e)}，尝试使用forward_messages")
                # 尝试使用forward_messages
                try:
                    await self.client.forward_messages(
                        chat_id=target_id,
                        from_chat_id=source_chat_id,
                        message_ids=message_ids
                    )
                    logger.info(f"已使用forward_messages成功转发媒体组到 {target_info}")
                    
                    # 发射媒体组转发成功事件 - 只发射一次整体事件
                    if self.emit:
                        # 尝试获取源频道信息
                        try:
                            source_info_str, _ = await self.channel_resolver.format_channel_info(source_chat_id)
                        except Exception:
                            source_info_str = str(source_chat_id)
                        
                        # 生成媒体组显示ID
                        media_group_display_id = self._generate_media_group_display_id(message_ids)
                        
                        # 只发射一次媒体组整体的转发成功事件
                        self.emit("forward", media_group_display_id, source_info_str, target_info, True, modified=caption_modified)
                    
                    return True
                except Exception as forward_e:
                    logger.warning(f"使用forward_messages失败: {str(forward_e)}，尝试单条发送")
                    return False
                
        except FloodWait as e:
            logger.warning(f"触发FloodWait，等待 {e.x} 秒后继续")
            await asyncio.sleep(e.x)
            # 递归重试
            return await self._forward_media_group_to_target(
                source_chat_id, target_id, target_info,
                first_message_id, message_ids, media_group_id, source_title, caption_modified
            )
            
        except Exception as e:
            logger.error(f"转发媒体组到 {target_info} 失败: {str(e)}", error_type="FORWARD_TO_TARGET", recoverable=True)
            
            # 发射转发失败事件 - 只发射一次整体事件
            if self.emit:
                # 尝试获取源频道信息
                try:
                    source_info_str, _ = await self.channel_resolver.format_channel_info(source_chat_id)
                except Exception:
                    source_info_str = str(source_chat_id)
                
                # 生成媒体组显示ID
                media_group_display_id = self._generate_media_group_display_id(message_ids)
                
                # 为每个目标频道发射一次媒体组整体的转发失败事件
                for target, target_id, target_info in target_channels:
                    self.emit("forward", media_group_display_id, source_info_str, target_info, False)
            
            return False
    
    async def _send_modified_media_group(self, messages: List[Message], caption: str, target_channels: List[Tuple[str, int, str]], caption_modified: bool):
        """发送修改后的媒体组到多个目标频道
        
        Args:
            messages: 媒体组消息列表
            caption: 修改后的标题
            target_channels: 目标频道列表 [(channel_name, channel_id, channel_info), ...]
            caption_modified: 是否修改了标题
        """
        if not messages:
            logger.warning("没有消息可发送")
            return

        media_group_id = messages[0].media_group_id
        source_title = messages[0].chat.title or "未知频道"
        
        # 构建媒体组
        media_group = []
        for message in messages:
            media_item = None
            caption_text = caption if message == messages[0] else ""
            
            if message.photo:
                media_item = InputMediaPhoto(
                    media=message.photo.file_id,
                    caption=caption_text
                )
            elif message.video:
                media_item = InputMediaVideo(
                    media=message.video.file_id,
                    caption=caption_text
                )
            elif message.document:
                media_item = InputMediaDocument(
                    media=message.document.file_id,
                    caption=caption_text
                )
            elif message.audio:
                media_item = InputMediaAudio(
                    media=message.audio.file_id,
                    caption=caption_text
                )
            elif message.animation:
                media_item = InputMediaAnimation(
                    media=message.animation.file_id,
                    caption=caption_text
                )
            
            if media_item:
                media_group.append(media_item)

        if not media_group:
            logger.warning(f"媒体组 {media_group_id} 没有有效的媒体项目可发送")
            return

        logger.info(f"媒体组 {media_group_id} 准备了 {len(media_group)} 个媒体项目进行发送")

        # 分别处理正常频道和禁止转发频道
        normal_targets = []
        restricted_targets = []
        
        # 首先尝试正常转发，识别哪些频道禁止转发
        for target, target_id, target_info in target_channels:
            if self.is_stopping:
                logger.info(f"任务已停止，中断发送过程")
                break
                
            try:
                # 尝试正常发送
                await self.client.send_media_group(
                    chat_id=target_id,
                    media=media_group
                )
                
                logger.info(f"已将修改后的媒体组 {media_group_id} 发送到 {target_info}")
                normal_targets.append((target, target_id, target_info))
                
            except ChatForwardsRestricted:
                logger.warning(f"目标频道 {target_info} 禁止转发，将使用下载上传方式处理")
                restricted_targets.append((target, target_id, target_info))
                
            except Exception as e:
                logger.error(f"发送修改后的媒体组 {media_group_id} 到 {target_info} 失败: {str(e)}")

        # 处理禁止转发的频道
        if restricted_targets:
            await self._handle_restricted_targets(messages, media_group_id, source_title, restricted_targets)

        success_count = len(normal_targets) + (len(restricted_targets) if restricted_targets else 0)
        total_count = len(target_channels)
        
        logger.info(f"修改后的媒体组 {media_group_id} 发送完成: 成功 {success_count}, 失败 {total_count - success_count}")
    
    async def _handle_restricted_targets(self, messages: List[Message], media_group_id: str, source_title: str, restricted_targets: List[Tuple[str, int, str]]):
        """处理禁止转发的目标频道
        
        Args:
            messages: 原始消息列表
            media_group_id: 媒体组ID
            source_title: 源频道标题
            restricted_targets: 禁止转发的目标频道列表
        """
        if not restricted_targets:
            return
            
        # 第一个目标频道：使用下载上传方式
        first_target = restricted_targets[0]
        _, first_target_id, first_target_info = first_target
        
        logger.info(f"对第一个禁止转发频道 {first_target_info} 使用下载上传方式处理媒体组 {media_group_id}")
        
        # 使用ParallelProcessor处理第一个频道
        success = await self._handle_restricted_media_group(first_target_id, first_target_info, media_group_id, source_title, messages)
        
        if not success:
            logger.error(f"第一个禁止转发频道 {first_target_info} 处理失败，其他频道也将失败")
            return
            
        # 其他频道：从第一个频道复制转发
        if len(restricted_targets) > 1:
            logger.info(f"第一个频道成功，开始从 {first_target_info} 复制转发到其他 {len(restricted_targets)-1} 个禁止转发频道")
            await self._copy_from_first_target(first_target_id, restricted_targets[1:], media_group_id)

    async def _copy_from_first_target(self, source_target_id: int, remaining_targets: List[Tuple[str, int, str]], media_group_id: str):
        """从第一个成功上传的目标频道复制转发到其他频道
        
        Args:
            source_target_id: 第一个成功的目标频道ID
            remaining_targets: 剩余的目标频道列表
            media_group_id: 媒体组ID
        """
        try:
            # 获取第一个频道的最新媒体组消息
            # 由于我们刚刚上传，最新的几条消息应该就是我们要的媒体组
            async for message in self.client.get_chat_history(source_target_id, limit=20):
                if message.media_group_id:
                    # 找到媒体组的第一条消息
                    media_group_messages = []
                    target_media_group_id = message.media_group_id
                    
                    # 收集整个媒体组
                    async for msg in self.client.get_chat_history(source_target_id, limit=50):
                        if msg.media_group_id == target_media_group_id:
                            media_group_messages.append(msg)
                        elif media_group_messages:  # 如果已经开始收集了但ID不匹配，说明收集完了
                            break
                    
                    # 按消息ID排序确保顺序正确
                    media_group_messages.sort(key=lambda x: x.id)
                    
                    if media_group_messages:
                        logger.info(f"找到第一个频道的媒体组，包含 {len(media_group_messages)} 条消息，开始复制转发")
                        
                        # 复制到其他频道
                        for target, target_id, target_info in remaining_targets:
                            try:
                                # 转发媒体组
                                await self.client.forward_messages(
                                    chat_id=target_id,
                                    from_chat_id=source_target_id,
                                    message_ids=[msg.id for msg in media_group_messages]
                                )
                                logger.info(f"成功从第一个频道复制媒体组到 {target_info}")
                                
                            except Exception as e:
                                logger.error(f"复制媒体组到 {target_info} 失败: {str(e)}")
                        
                        return  # 成功处理后退出
                    
            logger.warning(f"未能在第一个频道找到刚上传的媒体组 {media_group_id}")
            
        except Exception as e:
            logger.error(f"从第一个频道复制转发时出错: {str(e)}")
    
    async def _api_request_worker(self):
        """API请求队列工作器，负责处理排队的API请求"""
        try:
            while not self.is_stopping:
                try:
                    # 从队列获取一个任务
                    request_data = await self.api_request_queue.get()
                    
                    if self.is_stopping:
                        self.api_request_queue.task_done()  # 确保在退出前完成任务
                        break
                        
                    channel_id, message_id, media_group_id, message, pair_config = request_data
                    
                    # 再次检查该媒体组是否已处理
                    if media_group_id in self.processed_media_groups:
                        self.api_request_queue.task_done()
                        continue
                        
                    # 随机延迟一小段时间，分散API请求
                    jitter = random.uniform(0.1, 0.5)
                    await asyncio.sleep(jitter)
                    
                    # 控制全局API调用频率
                    now = time.time()
                    time_since_last_call = now - self.global_last_api_call
                    if time_since_last_call < self.global_api_interval:
                        await asyncio.sleep(self.global_api_interval - time_since_last_call + jitter)
                    
                    # 标记为正在处理，防止重复处理
                    task_completed = False
                    
                    # 使用信号量限制并发API请求数量
                    async with self.api_semaphore:
                        # 更新全局API调用时间
                        self.global_last_api_call = time.time()
                        
                        # 尝试使用get_media_group获取完整媒体组
                        try:
                            # 检查媒体组是否仍在获取中
                            if media_group_id in self.fetching_media_groups:
                                logger.debug(f"媒体组 {media_group_id} 仍在被其他任务获取，跳过API请求")
                                self.api_request_queue.task_done()
                                task_completed = True
                                continue
                                
                            # 检查媒体组是否已处理（可能在等待期间被处理）
                            if media_group_id in self.processed_media_groups:
                                logger.debug(f"媒体组 {media_group_id} 已在等待期间被处理，跳过API请求")
                                self.api_request_queue.task_done()
                                task_completed = True
                                continue
                                
                            # 标记为正在获取
                            self.fetching_media_groups.add(media_group_id)
                            self.last_media_group_fetch[media_group_id] = time.time()
                            
                            logger.info(f"从队列处理媒体组 {media_group_id} 的API请求")
                            complete_media_group = await self.client.get_media_group(channel_id, message_id)
                            
                            if complete_media_group:
                                logger.info(f"成功获取媒体组 {media_group_id} 的所有消息，共 {len(complete_media_group)} 条")
                                
                                # 在处理前先应用媒体类型过滤
                                allowed_media_types = pair_config.get('media_types', [])
                                if allowed_media_types:
                                    # 过滤媒体组消息，只保留允许的媒体类型
                                    filtered_complete_messages = []
                                    filtered_out_count = 0
                                    
                                    # 更新媒体组过滤统计 - API路径
                                    if media_group_id not in self.media_group_filter_stats:
                                        self.media_group_filter_stats[media_group_id] = {
                                            'total_expected': len(complete_media_group),
                                            'filtered_count': 0,
                                            'total_received': len(complete_media_group)
                                        }
                                    
                                    for msg in complete_media_group:
                                        msg_media_type = self._get_message_media_type(msg)
                                        if msg_media_type and self._is_media_type_allowed(msg_media_type, allowed_media_types):
                                            filtered_complete_messages.append(msg)
                                        else:
                                            filtered_out_count += 1
                                            # 更新过滤统计
                                            self.media_group_filter_stats[media_group_id]['filtered_count'] += 1
                                            
                                            # 记录被过滤的消息
                                            if msg_media_type:
                                                media_type_names = {
                                                    "photo": "照片", "video": "视频", "document": "文件", "audio": "音频",
                                                    "animation": "动画", "sticker": "贴纸", "voice": "语音", "video_note": "视频笔记"
                                                }
                                                media_type_name = media_type_names.get(msg_media_type.value, msg_media_type.value)
                                                filter_reason = f"媒体类型({media_type_name})不在允许列表中"
                                                logger.info(f"API获取的媒体组中的消息 [ID: {msg.id}] 的{filter_reason}，从媒体组中移除")
                                                
                                                # 发送过滤消息事件到UI
                                                if hasattr(self, 'emit') and self.emit:
                                                    try:
                                                        source_info_str, _ = await self.channel_resolver.format_channel_info(msg.chat.id)
                                                    except Exception:
                                                        source_info_str = str(msg.chat.id)
                                                    self.emit("message_filtered", msg.id, source_info_str, filter_reason)
                                    
                                    # 如果所有消息都被过滤，跳过处理
                                    if not filtered_complete_messages:
                                        logger.info(f"API获取的媒体组 {media_group_id} 中的所有消息都被过滤，跳过转发")
                                        # 标记为已处理（即使没有转发）
                                        self.processed_media_groups.add(media_group_id)
                                        
                                        # 清理过滤统计
                                        if media_group_id in self.media_group_filter_stats:
                                            del self.media_group_filter_stats[media_group_id]
                                        
                                        # 如果缓存中有该媒体组，清理它
                                        if channel_id in self.media_group_cache and media_group_id in self.media_group_cache[channel_id]:
                                            del self.media_group_cache[channel_id][media_group_id]
                                            if not self.media_group_cache[channel_id]:
                                                del self.media_group_cache[channel_id]
                                        continue
                                    
                                    logger.info(f"API获取的媒体组 {media_group_id} 原始消息数：{len(complete_media_group)}，过滤后消息数：{len(filtered_complete_messages)}，被过滤：{filtered_out_count}")
                                    complete_media_group = filtered_complete_messages
                                else:
                                    # 如果没有媒体类型过滤，初始化统计但不过滤
                                    if media_group_id not in self.media_group_filter_stats:
                                        self.media_group_filter_stats[media_group_id] = {
                                            'total_expected': len(complete_media_group),
                                            'filtered_count': 0,
                                            'total_received': len(complete_media_group)
                                        }
                                
                                # 标记为已处理
                                self.processed_media_groups.add(media_group_id)
                                # 处理完整的媒体组（现在已经过滤）
                                asyncio.create_task(self._process_media_group(complete_media_group, pair_config))
                                
                                # 如果缓存中有该媒体组，清理它
                                if channel_id in self.media_group_cache and media_group_id in self.media_group_cache[channel_id]:
                                    del self.media_group_cache[channel_id][media_group_id]
                                    # 如果此频道没有更多媒体组，移除整个频道条目
                                    if not self.media_group_cache[channel_id]:
                                        del self.media_group_cache[channel_id]
                            else:
                                logger.warning(f"无法获取媒体组 {media_group_id} 的完整消息，添加到积压队列")
                                self._add_to_backlog(message, media_group_id, channel_id, pair_config)
                                
                        except Exception as e:
                            logger.warning(f"处理媒体组 {media_group_id} 的API请求失败: {str(e)}")
                            self._add_to_backlog(message, media_group_id, channel_id, pair_config)
                        finally:
                            # 移除获取标记
                            if media_group_id in self.fetching_media_groups:
                                self.fetching_media_groups.remove(media_group_id)
                            
                            # 只在未完成任务时调用task_done
                            if not task_completed:
                                self.api_request_queue.task_done()
                
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"API请求处理工作器异常: {str(e)}", error_type="API_WORKER", recoverable=True)
                    # 确保在异常情况下也完成任务
                    try:
                        self.api_request_queue.task_done()
                    except ValueError:
                        pass  # 忽略task_done()重复调用的错误
                    await asyncio.sleep(1)
                    
            logger.info("API请求处理工作器已停止")
        except asyncio.CancelledError:
            logger.info("API请求处理工作器任务已取消")
            
    async def _process_message_backlog(self):
        """处理积压消息队列"""
        try:
            while not self.is_stopping:
                try:
                    # 每次处理一批积压消息
                    await asyncio.sleep(2)  # 积压消息处理间隔
                    
                    if self.is_stopping:
                        break
                        
                    active_channels = list(self.message_backlog.keys())
                    if not active_channels:
                        continue
                        
                    # 随机选择一个频道进行处理，避免所有频道同时处理
                    channel_id = random.choice(active_channels)
                    active_groups = list(self.message_backlog[channel_id].keys())
                    
                    if not active_groups:
                        if channel_id in self.message_backlog:
                            del self.message_backlog[channel_id]
                        continue
                    
                    # 随机选择一个媒体组进行处理
                    media_group_id = random.choice(active_groups)
                    
                    # 检查是否已经处理
                    if media_group_id in self.processed_media_groups:
                        if media_group_id in self.message_backlog[channel_id]:
                            del self.message_backlog[channel_id][media_group_id]
                        if not self.message_backlog[channel_id]:
                            del self.message_backlog[channel_id]
                        continue
                    
                    # 获取消息和配置
                    message, pair_config = self.message_backlog[channel_id][media_group_id]
                    
                    # 将消息添加到缓存中并继续正常处理流程
                    await self._add_message_to_cache(message, media_group_id, channel_id, pair_config)
                    
                    # 从积压队列中移除已处理的消息
                    del self.message_backlog[channel_id][media_group_id]
                    if not self.message_backlog[channel_id]:
                        del self.message_backlog[channel_id]
                    
                except Exception as e:
                    logger.error(f"处理积压消息异常: {str(e)}", error_type="BACKLOG_PROCESSOR", recoverable=True)
                    await asyncio.sleep(1)
                    
            logger.info("积压消息处理任务已停止")
        except asyncio.CancelledError:
            logger.info("积压消息处理任务已取消")
    
    def _add_to_backlog(self, message: Message, media_group_id: str, channel_id: int, pair_config: dict):
        """
        将消息添加到积压队列
        
        Args:
            message: 媒体组消息
            media_group_id: 媒体组ID
            channel_id: 频道ID
            pair_config: 频道对配置
        """
        if channel_id not in self.message_backlog:
            self.message_backlog[channel_id] = {}
            
        self.message_backlog[channel_id][media_group_id] = (message, pair_config)
        logger.debug(f"媒体组消息 [ID: {message.id}] 已添加到积压队列")
    
    def _get_message_media_type(self, message: Message):
        """
        获取消息的媒体类型
        
        Args:
            message: 消息对象
            
        Returns:
            MediaType: 媒体类型枚举，如果是纯文本消息则返回None
        """
        from src.utils.ui_config_models import MediaType
        
        if message.photo:
            return MediaType.PHOTO
        elif message.video:
            return MediaType.VIDEO
        elif message.document:
            return MediaType.DOCUMENT
        elif message.audio:
            return MediaType.AUDIO
        elif message.animation:
            return MediaType.ANIMATION
        elif message.sticker:
            return MediaType.STICKER
        elif message.voice:
            return MediaType.VOICE
        elif message.video_note:
            return MediaType.VIDEO_NOTE
        else:
            # 纯文本消息，不需要媒体类型过滤
            return None
    
    def _is_media_type_allowed(self, message_media_type, allowed_media_types):
        """
        检查消息的媒体类型是否在允许列表中
        
        Args:
            message_media_type: 消息的媒体类型
            allowed_media_types: 允许的媒体类型列表
            
        Returns:
            bool: 是否允许该媒体类型
        """
        if not allowed_media_types:
            # 如果没有配置允许的媒体类型，默认允许所有类型
            return True
        
        # 检查媒体类型是否在允许列表中
        for allowed_type in allowed_media_types:
            # 处理字符串和枚举类型的兼容性
            if hasattr(allowed_type, 'value'):
                allowed_value = allowed_type.value
            else:
                allowed_value = allowed_type
                
            if hasattr(message_media_type, 'value'):
                message_value = message_media_type.value
            else:
                message_value = message_media_type
                
            if allowed_value == message_value:
                return True
        
        return False
    
    def _contains_links(self, text: str) -> bool:
        """
        检查文本中是否包含链接
        
        Args:
            text: 要检查的文本
            
        Returns:
            bool: 是否包含链接
        """
        import re
        
        if not text:
            return False
        
        # 简单的URL正则匹配
        url_patterns = [
            r'https?://[^\s]+',  # http或https链接
            r'www\.[^\s]+',      # www链接
            r't\.me/[^\s]+',     # Telegram链接
            r'[^\s]+\.[a-z]{2,}[^\s]*'  # 一般域名
        ]
        
        for pattern in url_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        return False 

    def _generate_media_group_display_id(self, message_ids: List[int]) -> str:
        """生成安全的媒体组显示ID，用于UI显示
        
        Args:
            message_ids: 消息ID列表
            
        Returns:
            str: 格式化的媒体组显示ID，格式为"媒体组[N个文件]-最小消息ID"
        """
        try:
            if not message_ids:
                # 如果消息列表为空，使用时间戳生成备用ID
                import time
                timestamp = int(time.time())
                logger.warning("消息ID列表为空，使用时间戳生成媒体组显示ID")
                return f"媒体组[0个文件]-{timestamp}"
            
            # 获取消息数量和最小ID
            message_count = len(message_ids)
            min_message_id = min(message_ids)
            
            # 确保消息ID是有效的
            if min_message_id <= 0:
                # 如果最小消息ID无效，使用时间戳
                import time
                timestamp = int(time.time())
                logger.warning(f"检测到无效的消息ID {min_message_id}，使用时间戳生成媒体组显示ID")
                return f"媒体组[{message_count}个文件]-{timestamp}"
            
            # 生成标准格式的媒体组显示ID
            display_id = f"媒体组[{message_count}个文件]-{min_message_id}"
            logger.debug(f"生成媒体组显示ID: {display_id} (消息IDs: {message_ids})")
            
            return display_id
            
        except Exception as e:
            # 出错时使用时间戳作为备用
            logger.error(f"生成媒体组显示ID时出错: {e}")
            import time
            timestamp = int(time.time())
            fallback_id = f"媒体组[未知]-{timestamp}"
            logger.warning(f"使用备用媒体组显示ID: {fallback_id}")
            return fallback_id 

    def _emit_message_filtered(self, message: Message, filter_reason: str):
        """发送消息过滤事件到UI
        
        Args:
            message: 被过滤的消息
            filter_reason: 过滤原因
        """
        if hasattr(self, 'emit') and self.emit:
            try:
                # 使用异步方法获取源信息，但这里是同步调用，所以用简化版本
                source_info_str = f"频道 (ID: {message.chat.id})"
                if hasattr(message.chat, 'title') and message.chat.title:
                    source_info_str = f"{message.chat.title} (ID: {message.chat.id})"
                elif hasattr(message.chat, 'username') and message.chat.username:
                    source_info_str = f"@{message.chat.username} (ID: {message.chat.id})"
            except Exception:
                source_info_str = str(message.chat.id)
            self.emit("message_filtered", message.id, source_info_str, filter_reason)

    async def _send_filtered_media_group(self, filtered_messages: List[Message], pair_config: dict, target_channels: List[Tuple[str, int, str]]):
        """发送过滤后重组的媒体组
        
        Args:
            filtered_messages: 过滤后的消息列表
            pair_config: 频道对配置
            target_channels: 目标频道列表
        """
        if not filtered_messages or not target_channels:
            return
            
        try:
            # 获取源信息
            source_chat = filtered_messages[0].chat
            source_chat_id = source_chat.id
            media_group_id = filtered_messages[0].media_group_id
            
            try:
                source_title = source_chat.title
            except:
                source_title = str(source_chat_id)
            
            logger.info(f"开始发送过滤后重组的媒体组 [原ID: {media_group_id}] 从 {source_title} 到 {len(target_channels)} 个目标频道")
            
            # 检查文本替换和标题移除配置
            remove_captions = pair_config.get('remove_captions', False)
            
            # 优先使用已经构建好的text_replacements，如果没有则从text_filter构建
            text_replacements = pair_config.get('text_replacements', {})
            if not text_replacements:
                # 如果没有预构建的text_replacements，从text_filter构建
                text_filter = pair_config.get('text_filter', [])
                text_replacements = {}
                if text_filter:
                    for rule in text_filter:
                        original_text = rule.get('original_text', '')
                        target_text = rule.get('target_text', '')
                        if original_text:
                            text_replacements[original_text] = target_text
            
            # 获取媒体组的原始标题（从过滤统计中获取，而不是从过滤后的消息中）
            original_caption = None
            media_group_id = filtered_messages[0].media_group_id
            
            # 尝试从过滤统计中获取原始标题
            if media_group_id in self.media_group_filter_stats:
                original_caption = self.media_group_filter_stats[media_group_id].get('original_caption')
                logger.debug(f"从过滤统计中获取媒体组 {media_group_id} 的原始标题: '{original_caption}'")
            
            # 如果过滤统计中没有，再从过滤后的消息中寻找（兜底方案）
            if not original_caption:
                for message in filtered_messages:
                    if message.caption:
                        original_caption = message.caption
                        logger.debug(f"从过滤后消息中获取媒体组 {media_group_id} 的标题: '{original_caption}'")
                        break
            
            # 根据配置决定处理方式
            replaced_caption = None
            caption_modified = False
            
            if remove_captions:
                # 设置了移除媒体说明：删除说明，文本替换失效
                if original_caption:  # 只有原本有标题时，移除才算修改
                    caption_modified = True
                logger.debug(f"重组媒体组将移除说明文字，文本替换功能失效")
            else:
                # 未设置移除媒体说明：正常应用文本替换
                if original_caption:
                    if text_replacements:
                        # 应用文本替换
                        replaced_caption = original_caption
                        for find_text, replace_text in text_replacements.items():
                            if find_text in replaced_caption:
                                replaced_caption = replaced_caption.replace(find_text, replace_text)
                                
                        if replaced_caption != original_caption:
                            caption_modified = True
                            logger.info(f"重组媒体组已应用文本替换：'{original_caption}' -> '{replaced_caption}'")
                        else:
                            # 没有替换成功，使用原始标题
                            replaced_caption = original_caption
                    else:
                        # 没有文本替换规则，使用原始标题
                        replaced_caption = original_caption
                else:
                    # 没有原始标题，不添加标题
                    replaced_caption = None
            
            # 准备InputMedia列表用于send_media_group
            media_list = []
            message_ids_for_display = []
            
            for i, message in enumerate(filtered_messages):
                message_ids_for_display.append(message.id)
                
                # 确定当前消息的标题
                current_caption = None
                if i == 0:  # 只在第一条消息上添加标题
                    if remove_captions:
                        current_caption = None  # 移除标题
                    elif replaced_caption:
                        current_caption = replaced_caption  # 使用替换后的标题
                    elif message.caption:
                        current_caption = message.caption  # 使用原始标题
                
                # 根据消息类型创建InputMedia
                if message.photo:
                    media_list.append(InputMediaPhoto(
                        media=message.photo.file_id,
                        caption=current_caption
                    ))
                elif message.video:
                    media_list.append(InputMediaVideo(
                        media=message.video.file_id,
                        caption=current_caption
                    ))
                elif message.document:
                    media_list.append(InputMediaDocument(
                        media=message.document.file_id,
                        caption=current_caption
                    ))
                elif message.audio:
                    media_list.append(InputMediaAudio(
                        media=message.audio.file_id,
                        caption=current_caption
                    ))
                elif message.animation:
                    media_list.append(InputMediaAnimation(
                        media=message.animation.file_id,
                        caption=current_caption
                    ))
                else:
                    logger.warning(f"不支持的媒体类型，跳过消息 [ID: {message.id}]")
                    continue
            
            if not media_list:
                logger.warning("没有可发送的媒体，跳过重组媒体组发送")
                return
            
            # 逐个发送到目标频道
            for target, target_id, target_info in target_channels:
                try:
                    # 使用send_media_group发送重组的媒体组
                    sent_messages = await self.client.send_media_group(
                        chat_id=target_id,
                        media=media_list
                    )
                    
                    logger.info(f"已成功发送重组媒体组到 {target_info}，包含 {len(sent_messages)} 条消息")
                    
                    # 发射转发成功事件
                    if self.emit:
                        # 尝试获取源频道信息
                        try:
                            source_info_str, _ = await self.channel_resolver.format_channel_info(source_chat_id)
                        except Exception:
                            source_info_str = str(source_chat_id)
                        
                        # 生成媒体组显示ID
                        media_group_display_id = self._generate_media_group_display_id(message_ids_for_display)
                        
                        # 发射转发成功事件
                        self.emit("forward", f"重组{media_group_display_id}", source_info_str, target_info, True, modified=caption_modified)
                    
                except Exception as e:
                    logger.error(f"发送重组媒体组到 {target_info} 失败: {str(e)}", error_type="SEND_FILTERED_MEDIA_GROUP", recoverable=True)
                    
                    # 发射转发失败事件
                    if self.emit:
                        try:
                            source_info_str, _ = await self.channel_resolver.format_channel_info(source_chat_id)
                        except Exception:
                            source_info_str = str(source_chat_id)
                        
                        media_group_display_id = self._generate_media_group_display_id(message_ids_for_display)
                        self.emit("forward", f"重组{media_group_display_id}", source_info_str, target_info, False)
                
                # 添加延迟避免触发限制
                await asyncio.sleep(0.5)
            
            # 清理媒体组过滤统计，防止内存泄漏
            if media_group_id in self.media_group_filter_stats:
                del self.media_group_filter_stats[media_group_id]
                logger.debug(f"清理媒体组 {media_group_id} 的过滤统计信息")
                
        except Exception as e:
            logger.error(f"处理过滤后媒体组重组时出错: {str(e)}", error_type="FILTERED_MEDIA_GROUP", recoverable=True)
            import traceback
            logger.debug(f"错误详情:\n{traceback.format_exc()}")
            
            # 确保在异常情况下也清理统计信息
            try:
                media_group_id = filtered_messages[0].media_group_id if filtered_messages else None
                if media_group_id and media_group_id in self.media_group_filter_stats:
                    del self.media_group_filter_stats[media_group_id]
                    logger.debug(f"异常清理媒体组 {media_group_id} 的过滤统计信息")
            except Exception:
                pass  # 忽略清理过程中的异常

    async def _handle_restricted_media_group(self, target_id: int, target_info: str, 
                                           media_group_id: str, source_title: str, 
                                           original_messages: List) -> bool:
        """处理禁止转发的媒体组，使用下载上传方式
        
        Args:
            target_id: 目标频道ID
            target_info: 目标频道信息字符串
            media_group_id: 媒体组ID
            source_title: 源频道标题
            original_messages: 原始消息列表
            
        Returns:
            bool: 是否成功处理
        """
        try:
            if not original_messages:
                logger.error(f"无法找到媒体组 {media_group_id} 的原始消息，无法处理禁止转发")
                return False
                
            # 获取源频道信息
            source_chat_id = original_messages[0].chat.id
            source_channel = str(source_chat_id)
            
            # 创建临时目录
            temp_dir = Path("tmp") / "restricted_forward" / f"{media_group_id}_{int(time.time())}"
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            try:
                # 使用ParallelProcessor处理媒体组
                processor = ParallelProcessor(
                    client=self.client,
                    history_manager=None,  # 监听模块通常不需要历史管理
                    general_config={}
                )
                
                # 准备媒体组信息（转换为ParallelProcessor期望的格式）
                message_ids = [msg.id for msg in original_messages]
                media_groups_info = [(media_group_id, message_ids)]
                
                # 准备目标频道信息（转换为ParallelProcessor期望的格式）
                target_channels = [(str(target_id), target_id, target_info)]
                
                logger.info(f"使用ParallelProcessor处理禁止转发的媒体组 {media_group_id}，包含 {len(message_ids)} 条消息")
                
                # 执行并行下载上传
                await processor.process_parallel_download_upload(
                    source_channel=source_channel,
                    source_id=source_chat_id,
                    media_groups_info=media_groups_info,
                    temp_dir=temp_dir,
                    target_channels=target_channels
                )
                
                logger.info(f"成功使用下载上传方式处理禁止转发的媒体组 {media_group_id} 到 {target_info}")
                return True
                
            finally:
                # 清理临时目录
                try:
                    import shutil
                    if temp_dir.exists():
                        shutil.rmtree(temp_dir)
                        logger.debug(f"清理临时目录: {temp_dir}")
                except Exception as cleanup_e:
                    logger.warning(f"清理临时目录失败: {cleanup_e}")
            
        except Exception as e:
            logger.error(f"处理禁止转发媒体组时发生错误: {str(e)}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")
            return False