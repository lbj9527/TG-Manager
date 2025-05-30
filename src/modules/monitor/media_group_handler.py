"""
媒体组处理器模块，负责处理和转发媒体组消息
"""

import asyncio
import time
import random
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
        
        # 媒体组消息缓存，格式: {channel_id: {media_group_id: {'messages': [Message], 'last_update_time': timestamp}}}
        self.media_group_cache = {}
        # 媒体组处理锁，防止并发处理同一个媒体组
        self.media_group_locks = {}
        # 媒体组超时时间（秒），超过此时间后媒体组将被视为完整并处理
        self.media_group_timeout = 8
        # 媒体组清理任务
        self.media_group_cleanup_task = None
        # 已处理媒体组清理任务
        self.processed_groups_cleanup_task = None
        
        # 频道对应关系配置
        self.channel_pairs = {}
        
        # 停止标志
        self.should_stop = False
        
        # 已处理的媒体组ID集合，用于防止重复处理
        self.processed_media_groups: Set[str] = set()
        # 上次清理已处理媒体组的时间
        self.last_processed_groups_cleanup = time.time()
        
        # 正在获取完整媒体组的ID集合，防止重复调用get_media_group
        self.fetching_media_groups: Set[str] = set()
        # 媒体组API调用的上次时间记录，限制调用频率
        self.last_media_group_fetch: Dict[str, float] = {}
        # 媒体组API调用的最小间隔(秒)
        self.media_group_fetch_interval = 2
        
        # API并发控制
        self.api_semaphore = asyncio.Semaphore(3)  # 限制最多3个并发API请求
        self.global_last_api_call = 0  # 全局最后API调用时间
        self.global_api_interval = 0.5  # 全局API调用最小间隔(秒)
        
        # 媒体组获取优先级队列 - 用于排队处理API请求
        self.api_request_queue = asyncio.Queue()
        self.api_worker_task = None
        
        # 待处理消息队列 - 用于平滑处理大量涌入的消息
        self.message_backlog = {}  # 格式: {channel_id: {media_group_id: (message, pair_config)}}
        self.backlog_processor_task = None
        
        # 高流量保护标志
        self.high_traffic_mode = False
        self.high_traffic_threshold = 10  # 10个以上媒体组同时进入时激活高流量模式
        self.high_traffic_cooldown = 30  # 30秒冷却时间
        self.last_high_traffic_time = 0
        
        # 初始化禁止转发处理器
        self.restricted_handler = RestrictedForwardHandler(client, channel_resolver)
        
        # 事件发射器引用 - 将在Monitor中设置
        self.emit = None
    
    def set_channel_pairs(self, channel_pairs: Dict[int, Dict[str, Any]]):
        """
        设置频道对应关系配置
        
        Args:
            channel_pairs: 频道对应关系配置字典
        """
        self.channel_pairs = channel_pairs
    
    def start_cleanup_task(self):
        """启动媒体组清理任务"""
        if self.media_group_cleanup_task is None:
            self.media_group_cleanup_task = asyncio.create_task(self._cleanup_media_groups())
            logger.debug("媒体组清理任务已启动")
            
        if self.processed_groups_cleanup_task is None:
            self.processed_groups_cleanup_task = asyncio.create_task(self._cleanup_processed_groups())
            logger.debug("已处理媒体组清理任务已启动")
            
        # 启动API请求处理任务
        if self.api_worker_task is None:
            self.api_worker_task = asyncio.create_task(self._api_request_worker())
            logger.debug("API请求处理任务已启动")
            
        # 启动积压消息处理任务
        if self.backlog_processor_task is None:
            self.backlog_processor_task = asyncio.create_task(self._process_message_backlog())
            logger.debug("积压消息处理任务已启动")
    
    async def stop(self):
        """停止媒体组处理器"""
        self.should_stop = True
        
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
            
        # 取消已处理媒体组清理任务
        if self.processed_groups_cleanup_task:
            self.processed_groups_cleanup_task.cancel()
            try:
                await self.processed_groups_cleanup_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"取消已处理媒体组清理任务时异常: {str(e)}", error_type="TASK_CANCEL", recoverable=True)
            
            self.processed_groups_cleanup_task = None
            
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
        if self.backlog_processor_task:
            self.backlog_processor_task.cancel()
            try:
                await self.backlog_processor_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"取消积压消息处理任务时异常: {str(e)}", error_type="TASK_CANCEL", recoverable=True)
                
            self.backlog_processor_task = None
        
        # 清空媒体组缓存
        self.media_group_cache.clear()
        self.media_group_locks.clear()
        self.processed_media_groups.clear()
        self.fetching_media_groups.clear()
        self.last_media_group_fetch.clear()
        self.message_backlog.clear()
        logger.info("已清理所有媒体组缓存")
    
    async def _cleanup_processed_groups(self):
        """定期清理已处理媒体组ID集合，防止集合无限增长"""
        try:
            while not self.should_stop:
                await asyncio.sleep(300)  # 每5分钟清理一次
                
                if self.should_stop:
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
        exclude_media = pair_config.get('exclude_media', False)
        exclude_links = pair_config.get('exclude_links', False)
        
        # 应用过滤逻辑
        if exclude_forwards and message.forward_from:
            logger.debug(f"媒体组消息 [ID: {message.id}] 是转发消息，根据过滤规则跳过")
            return
        
        if exclude_replies and message.reply_to_message:
            logger.debug(f"媒体组消息 [ID: {message.id}] 是回复消息，根据过滤规则跳过")
            return
        
        # 检查是否为媒体消息（媒体组都是媒体消息）
        if exclude_media:
            logger.debug(f"媒体组消息 [ID: {message.id}] 是媒体消息，根据过滤规则跳过")
            return
        
        # 检查是否包含链接
        if exclude_links:
            text_content = message.text or message.caption or ""
            if self._contains_links(text_content) or (message.entities and any(entity.type in ["url", "text_link"] for entity in message.entities)):
                logger.debug(f"媒体组消息 [ID: {message.id}] 包含链接，根据过滤规则跳过")
                return
        
        # 关键词过滤
        if keywords:
            text_content = message.text or message.caption or ""
            if not any(keyword.lower() in text_content.lower() for keyword in keywords):
                logger.debug(f"媒体组消息 [ID: {message.id}] 不包含指定关键词，根据过滤规则跳过")
                return
        
        # 获取该频道对允许的媒体类型
        allowed_media_types = pair_config.get('media_types', [])
        
        # 检查消息的媒体类型是否被允许
        message_media_type = self._get_message_media_type(message)
        if message_media_type and not self._is_media_type_allowed(message_media_type, allowed_media_types):
            logger.debug(f"媒体组消息 [ID: {message.id}] 的媒体类型 {message_media_type.value} 不在允许列表中，跳过处理")
            return
        
        channel_id = message.chat.id
        media_group_id = message.media_group_id
        
        if not media_group_id:
            logger.warning(f"消息 [ID: {message.id}] 不是媒体组消息")
            return
        
        # 检查该媒体组是否已处理
        if media_group_id in self.processed_media_groups:
            logger.debug(f"媒体组 {media_group_id} 已处理，跳过")
            return
            
        # 检查当前流量状态，判断是否处于高流量模式
        now = time.time()
        pending_media_groups_count = len(self.fetching_media_groups) + self.api_request_queue.qsize()
        
        if pending_media_groups_count > self.high_traffic_threshold:
            # 激活高流量模式
            if not self.high_traffic_mode:
                logger.warning(f"检测到高流量: {pending_media_groups_count} 个媒体组待处理，激活高流量保护模式")
                self.high_traffic_mode = True
                self.last_high_traffic_time = now
        elif self.high_traffic_mode and (now - self.last_high_traffic_time) > self.high_traffic_cooldown:
            # 如果已经超过冷却时间，退出高流量模式
            logger.info(f"高流量情况已缓解，退出高流量保护模式")
            self.high_traffic_mode = False
        
        # 获取锁
        lock_key = f"{channel_id}_{media_group_id}"
        if lock_key not in self.media_group_locks:
            self.media_group_locks[lock_key] = asyncio.Lock()
            
        async with self.media_group_locks[lock_key]:
            # 再次检查媒体组是否已处理（可能在获取锁的过程中被其他任务处理）
            if media_group_id in self.processed_media_groups:
                logger.debug(f"媒体组 {media_group_id} 已处理，跳过")
                return
            
            # 首先尝试将消息添加到缓存
            cache_hit = False
            if channel_id in self.media_group_cache and media_group_id in self.media_group_cache[channel_id]:
                cache_hit = True
                
            # 在高流量模式下，首先把消息放入缓存，优先使用超时机制处理完整消息
            if self.high_traffic_mode:
                logger.debug(f"高流量模式: 将媒体组 {media_group_id} 消息 [ID: {message.id}] 添加到缓存")
                await self._add_message_to_cache(message, media_group_id, channel_id, pair_config)
                return
            
            # 检查是否已有其他任务正在获取这个媒体组
            if media_group_id in self.fetching_media_groups:
                logger.debug(f"媒体组 {media_group_id} 正在被其他任务获取，将消息添加到缓存")
                # 将消息添加到缓存后直接返回，避免重复调用API
                await self._add_message_to_cache(message, media_group_id, channel_id, pair_config)
                return
                
            # 检查是否需要调用get_media_group
            # 1. 检查距离上次获取是否已经超过最小时间间隔
            can_fetch = True
            if media_group_id in self.last_media_group_fetch:
                last_fetch_time = self.last_media_group_fetch[media_group_id]
                if now - last_fetch_time < self.media_group_fetch_interval:
                    # 时间间隔太短，不重复调用API
                    logger.debug(f"媒体组 {media_group_id} 距离上次获取时间较短，跳过API调用，等待更多消息收集")
                    can_fetch = False
            
            # 2. 判断是否为首次收到该媒体组的消息
            # 如果是缓存命中的情况，优先将消息添加到缓存，减少不必要的API调用
            if cache_hit:
                # 优先添加到缓存
                await self._add_message_to_cache(message, media_group_id, channel_id, pair_config)
                
                # 根据缓存消息数量决定是否需要API调用
                cached_messages = self.media_group_cache[channel_id][media_group_id].get('messages', [])
                
                # 如果缓存中已经有消息，可以跳过API调用，因为一条消息就能获取整个媒体组
                if len(cached_messages) >= 1:  # 只要有一条消息就跳过API调用
                    logger.info(f"媒体组 {media_group_id} 在缓存中已有 {len(cached_messages)} 条消息，跳过API调用")
                    can_fetch = False
                    
                # 如果消息中包含media_group_count字段，根据已收集比例决定是否需要API调用
                if hasattr(message, 'media_group_count') and message.media_group_count > 0:
                    completion_ratio = len(cached_messages) / message.media_group_count
                    if completion_ratio > 0.7:  # 如果已收集超过70%的消息，不调用API
                        logger.info(f"媒体组 {media_group_id} 已收集 {completion_ratio:.1%} 的消息({len(cached_messages)}/{message.media_group_count})，跳过API调用")
                        can_fetch = False
            else:
                # 如果是首次收到该媒体组的消息，先将消息添加到缓存
                await self._add_message_to_cache(message, media_group_id, channel_id, pair_config)
            
            # 3. 判断当前API请求队列长度，避免队列过长
            queue_size = self.api_request_queue.qsize()
            if queue_size > 6:  # 如果队列中已有超过6个请求，考虑跳过API调用
                # 使用随机概率决定是否跳过，队列越长跳过概率越高
                skip_probability = min(0.8, queue_size / 10)  # 最高80%概率跳过
                if random.random() < skip_probability:
                    logger.debug(f"API请求队列过长 ({queue_size})，随机决定跳过媒体组 {media_group_id} 的API调用")
                    can_fetch = False
            
            if can_fetch:
                # 不是立即调用API，而是将请求加入队列
                logger.debug(f"将媒体组 {media_group_id} 的API请求加入队列")
                await self.api_request_queue.put((channel_id, message.id, media_group_id, message, pair_config))
    
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
            
            # 检查文本替换和标题移除配置
            text_replacements = pair_config.get('text_replacements', {})
            remove_captions = pair_config.get('remove_captions', False)
            
            # 获取媒体组的第一个非空标题
            original_caption = None
            for message in messages:
                if message.caption:
                    original_caption = message.caption
                    break
            
            # 根据配置决定处理方式
            replaced_caption = None
            should_remove_caption = False
            
            if remove_captions:
                # 设置了移除媒体说明：删除说明，文本替换失效
                should_remove_caption = True
                logger.debug(f"媒体组 {media_group_id} 将移除说明文字，文本替换功能失效")
            else:
                # 未设置移除媒体说明：正常应用文本替换
                if original_caption and text_replacements:
                    replaced_caption = original_caption
                    for find_text, replace_text in text_replacements.items():
                        if find_text in replaced_caption:
                            replaced_caption = replaced_caption.replace(find_text, replace_text)
                            
                    if replaced_caption != original_caption:
                        logger.info(f"媒体组 {media_group_id} 已应用文本替换")
            
            # 检查源频道是否允许转发
            source_can_forward = await self.channel_resolver.check_forward_permission(source_id)
            
            if source_can_forward:
                # 源频道允许转发，使用copy_media_group
                await self._forward_media_group(messages, target_channels, replaced_caption, should_remove_caption)
            else:
                # 源频道禁止转发，使用下载上传方式
                logger.info(f"源频道禁止转发，将使用下载后上传的方式处理媒体组")
                
                # 使用禁止转发处理器处理媒体组
                sent_messages = await self.restricted_handler.process_restricted_media_group(
                    messages=messages,
                    source_channel=source_channel,
                    source_id=source_id,
                    target_channels=target_channels,
                    caption=replaced_caption if not should_remove_caption else None,
                    remove_caption=should_remove_caption
                )
                
                if sent_messages:
                    logger.info(f"已使用下载-上传方式成功将媒体组 {media_group_id} 从 {source_title} 发送到所有目标频道")
                    
                    # 发射所有目标频道的转发成功事件
                    if self.emit:
                        # 尝试获取源频道信息
                        try:
                            source_info_str, _ = await self.channel_resolver.format_channel_info(source_id)
                        except Exception:
                            source_info_str = str(source_id)
                        
                        # 获取消息ID列表
                        message_ids = [msg.id for msg in messages]
                        
                        # 为每个目标频道发射转发成功事件
                        for target, target_id, target_info in target_channels:
                            for msg_id in message_ids:
                                self.emit("forward", msg_id, source_info_str, target_info, True, modified=True)
                else:
                    logger.warning(f"使用下载-上传方式处理媒体组 {media_group_id} 失败")
                
        except Exception as e:
            logger.error(f"处理媒体组时发生错误: {str(e)}", error_type="PROCESS_MEDIA_GROUP", recoverable=True)
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"错误详情: {error_details}")
    
    async def _forward_media_group(self, messages: List[Message], target_channels: List[Tuple[str, int, str]], 
                                 replaced_caption: str = None, remove_captions: bool = False):
        """
        转发媒体组到目标频道
        
        Args:
            messages: 媒体组消息列表
            target_channels: 目标频道列表
            replaced_caption: 替换后的标题文本
            remove_captions: 是否移除标题
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
                # 如果需要移除标题
                logger.debug(f"将移除媒体组 {media_group_id} 的标题")
                await self._send_modified_media_group(sorted_messages, None, target_channels)
            elif replaced_caption is not None:
                # 如果有替换后的标题
                logger.debug(f"将使用替换后的标题: '{replaced_caption}'")
                await self._send_modified_media_group(sorted_messages, replaced_caption, target_channels)
            else:
                # 使用原始标题或没有标题
                # 先尝试第一个目标频道
                first_target = target_channels[0]
                success = await self._forward_media_group_to_target(
                    source_chat_id, first_target[1], first_target[2],
                    first_message_id, message_ids, media_group_id, source_title
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
                            
                            # 发射转发成功事件
                            if self.emit:
                                # 尝试获取源频道信息
                                try:
                                    source_info_str, _ = await self.channel_resolver.format_channel_info(first_target[1])
                                except Exception:
                                    source_info_str = str(first_target[1])
                                
                                # 为媒体组中的每个消息发射转发成功事件
                                for msg_id in message_ids:
                                    self.emit("forward", msg_id, source_info_str, target_info, True, modified=False)
                        except Exception as e:
                            logger.error(f"从第一个目标频道复制媒体组到 {target_info} 失败: {str(e)}", 
                                       error_type="COPY_MEDIA_GROUP", recoverable=True)
                        
                        # 添加延迟避免触发限制
                        await asyncio.sleep(0.5)
                else:
                    # 第一个目标频道转发失败，尝试不同的方式
                    logger.warning(f"转发媒体组到第一个目标频道失败，尝试逐个发送到所有目标频道")
                    
                    # 逐个发送到每个目标频道
                    for target, target_id, target_info in target_channels:
                        try:
                            await self._forward_media_group_to_target(
                                source_chat_id, target_id, target_info,
                                first_message_id, message_ids, media_group_id, source_title
                            )
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
            
            # 发射转发失败事件
            if self.emit:
                # 尝试获取源频道信息
                try:
                    source_info_str, _ = await self.channel_resolver.format_channel_info(source_chat_id)
                except Exception:
                    source_info_str = str(source_chat_id)
                
                # 为媒体组中的每个消息发射转发失败事件
                for msg_id in message_ids:
                    self.emit("forward", msg_id, source_info_str, target_info, False)
            
            return False
    
    async def _forward_media_group_to_target(self, source_chat_id: int, target_id: int, target_info: str,
                                          first_message_id: int, message_ids: List[int], 
                                          media_group_id: str, source_title: str) -> bool:
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
                
                # 发射转发成功事件
                if self.emit:
                    # 尝试获取源频道信息
                    try:
                        source_info_str, _ = await self.channel_resolver.format_channel_info(source_chat_id)
                    except Exception:
                        source_info_str = str(source_chat_id)
                    
                    # 为媒体组中的每个消息发射转发成功事件
                    for msg_id in message_ids:
                        self.emit("forward", msg_id, source_info_str, target_info, True, modified=False)
                
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
                    
                    # 发射转发成功事件
                    if self.emit:
                        # 尝试获取源频道信息
                        try:
                            source_info_str, _ = await self.channel_resolver.format_channel_info(source_chat_id)
                        except Exception:
                            source_info_str = str(source_chat_id)
                        
                        # 为媒体组中的每个消息发射转发成功事件
                        for msg_id in message_ids:
                            self.emit("forward", msg_id, source_info_str, target_info, True, modified=False)
                    
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
                    
                    # 发射转发成功事件
                    if self.emit:
                        # 尝试获取源频道信息
                        try:
                            source_info_str, _ = await self.channel_resolver.format_channel_info(source_chat_id)
                        except Exception:
                            source_info_str = str(source_chat_id)
                        
                        # 为媒体组中的每个消息发射转发成功事件
                        for msg_id in message_ids:
                            self.emit("forward", msg_id, source_info_str, target_info, True, modified=False)
                    
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
                first_message_id, message_ids, media_group_id, source_title
            )
            
        except Exception as e:
            logger.error(f"转发媒体组到 {target_info} 失败: {str(e)}", error_type="FORWARD_TO_TARGET", recoverable=True)
            
            # 发射转发失败事件
            if self.emit:
                # 尝试获取源频道信息
                try:
                    source_info_str, _ = await self.channel_resolver.format_channel_info(source_chat_id)
                except Exception:
                    source_info_str = str(source_chat_id)
                
                # 为媒体组中的每个消息发射转发失败事件
                for msg_id in message_ids:
                    self.emit("forward", msg_id, source_info_str, target_info, False)
            
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
        
        # 发射转发成功事件
        if self.emit and success_count > 0:
            # 尝试获取源频道信息
            try:
                source_info_str, _ = await self.channel_resolver.format_channel_info(source_chat_id)
            except Exception:
                source_info_str = str(source_chat_id)
            
            # 获取消息ID列表
            message_ids = [msg.id for msg in messages]
            
            # 为每个成功的目标频道发射转发成功事件
            for target, target_id, target_info in target_channels:
                # 为媒体组中的每个消息发射转发成功事件
                for msg_id in message_ids:
                    self.emit("forward", msg_id, source_info_str, target_info, True, modified=True)
        
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

    async def _api_request_worker(self):
        """API请求队列工作器，负责处理排队的API请求"""
        try:
            while not self.should_stop:
                try:
                    # 从队列获取一个任务
                    request_data = await self.api_request_queue.get()
                    
                    if self.should_stop:
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
                                continue
                                
                            # 检查媒体组是否已处理（可能在等待期间被处理）
                            if media_group_id in self.processed_media_groups:
                                logger.debug(f"媒体组 {media_group_id} 已在等待期间被处理，跳过API请求")
                                self.api_request_queue.task_done()
                                continue
                                
                            # 标记为正在获取
                            self.fetching_media_groups.add(media_group_id)
                            self.last_media_group_fetch[media_group_id] = time.time()
                            
                            logger.info(f"从队列处理媒体组 {media_group_id} 的API请求")
                            complete_media_group = await self.client.get_media_group(channel_id, message_id)
                            
                            if complete_media_group:
                                logger.info(f"成功获取媒体组 {media_group_id} 的所有消息，共 {len(complete_media_group)} 条")
                                # 标记为已处理
                                self.processed_media_groups.add(media_group_id)
                                # 处理完整的媒体组
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
                            # 完成任务并移除获取标记
                            self.api_request_queue.task_done()
                            if media_group_id in self.fetching_media_groups:
                                self.fetching_media_groups.remove(media_group_id)
                
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"API请求处理工作器异常: {str(e)}", error_type="API_WORKER", recoverable=True)
                    await asyncio.sleep(1)
                    
            logger.info("API请求处理工作器已停止")
        except asyncio.CancelledError:
            logger.info("API请求处理工作器任务已取消")
            
    async def _process_message_backlog(self):
        """处理积压消息队列"""
        try:
            while not self.should_stop:
                try:
                    # 每次处理一批积压消息
                    await asyncio.sleep(2)  # 积压消息处理间隔
                    
                    if self.should_stop:
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