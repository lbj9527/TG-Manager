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
        self.media_group_keyword_filter = {}  # 媒体组关键词过滤状态 {media_group_id: {'keywords_passed': bool, 'checked': bool}}
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
        
        # 频道信息缓存引用（由Monitor模块设置）
        self.channel_info_cache = None
        
        # 性能监控器引用（由Monitor模块设置）
        self.performance_monitor = None
        
        # Monitor引用（用于统一过滤）
        self.monitor = None
        
        # 启动后台任务
        self.cleanup_task = None
        self.backlog_task = None
        
        logger.debug("MediaGroupHandler 初始化完成")
    
    def set_monitor(self, monitor):
        """
        设置Monitor实例的引用
        
        Args:
            monitor: Monitor实例
        """
        self.monitor = monitor
    
    def set_channel_pairs(self, channel_pairs: Dict[int, Dict[str, Any]]):
        """
        设置频道对应关系配置
        
        Args:
            channel_pairs: 频道对应关系配置字典
        """
        self.channel_pairs = channel_pairs
    
    def set_channel_info_cache(self, cache_dict: dict):
        """
        设置频道信息缓存的引用
        
        Args:
            cache_dict: 频道信息缓存字典
        """
        self.channel_info_cache = cache_dict
    
    def set_performance_monitor(self, performance_monitor):
        """
        设置性能监控器
        
        Args:
            performance_monitor: 性能监控器实例
        """
        self.performance_monitor = performance_monitor
    
    def get_cached_channel_info(self, channel_id: int) -> str:
        """
        获取缓存的频道信息，避免重复API调用
        
        Args:
            channel_id: 频道ID
            
        Returns:
            str: 频道信息字符串
        """
        if self.channel_info_cache:
            cached_info = self.channel_info_cache.get_channel_info(channel_id)
            if cached_info:
                return cached_info[0]  # 返回display_name
        
        # 如果没有缓存，返回简单格式
        return f"频道 (ID: {channel_id})"
    
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
        
        # 取消所有延迟检查任务
        if self.pending_delay_tasks:
            logger.info(f"正在取消 {len(self.pending_delay_tasks)} 个延迟检查任务")
            cancelled_count = 0
            for media_group_id, delay_task in list(self.pending_delay_tasks.items()):
                try:
                    if not delay_task.done():
                        delay_task.cancel()
                        cancelled_count += 1
                        logger.debug(f"已取消媒体组 {media_group_id} 的延迟检查任务")
                except Exception as e:
                    logger.error(f"取消媒体组 {media_group_id} 延迟任务时异常: {str(e)}")
            
            logger.info(f"已取消 {cancelled_count} 个延迟检查任务")
        
        # 清理RestrictedForwardHandler的临时目录
        if hasattr(self, '_restricted_handler') and self._restricted_handler:
            try:
                self._restricted_handler.cleanup_temp_dirs()
                logger.debug("已清理RestrictedForwardHandler的临时目录")
            except Exception as e:
                logger.error(f"清理RestrictedForwardHandler临时目录失败: {e}")
        
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
        self.media_group_keyword_filter.clear()
        self.channel_pairs.clear()
        self.pending_delay_tasks.clear()
        self.message_backlog.clear()
        self.media_group_locks.clear()
        self.last_media_group_fetch.clear()
        logger.info("已清理所有媒体组缓存和任务")
    
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
        # 【调试】记录接收到的配置
        logger.debug(f"【调试】handle_media_group_message接收到的pair_config: {pair_config}")
        
        # 获取该频道对的过滤选项
        keywords = pair_config.get('keywords', [])
        exclude_links = pair_config.get('exclude_links', False)
        
        # 【修复】媒体组级别的链接检测和关键词检测
        # 检查该媒体组是否已经进行过检测
        if message.media_group_id not in self.media_group_keyword_filter:
            # 首次检查该媒体组，需要获取媒体组的完整文本
            media_group_text = await self._get_media_group_text(message.media_group_id, message.chat.id)
            
            # 链接检测
            links_passed = True
            if exclude_links and media_group_text:
                from src.utils.text_utils import contains_links
                if contains_links(media_group_text):
                    links_passed = False
                    logger.info(f"媒体组 {message.media_group_id} 包含链接，过滤整个媒体组")
            
            # 关键词检测
            keywords_passed = True
            if keywords and media_group_text:
                keywords_passed = any(keyword.lower() in media_group_text.lower() for keyword in keywords)
                if not keywords_passed:
                    logger.info(f"媒体组 {message.media_group_id} 不包含关键词({', '.join(keywords)})，过滤整个媒体组")
            elif keywords and not media_group_text:
                # 如果没有文本但有关键词要求，算作不通过
                keywords_passed = False
                logger.info(f"媒体组 {message.media_group_id} 没有文本且要求关键词，过滤整个媒体组")
            
            # 记录该媒体组的检测结果
            self.media_group_keyword_filter[message.media_group_id] = {
                'keywords_passed': keywords_passed,
                'links_passed': links_passed,
                'checked': True,
                'ui_notified': False
            }
            
            # 如果检测不通过，发送UI通知并返回
            if not links_passed or not keywords_passed:
                # 添加小延迟确保UI事件处理顺序正确
                await asyncio.sleep(0.05)  # 50ms延迟，确保new_message事件先被UI处理
                
                if not links_passed:
                    filter_reason = f"媒体组[{message.media_group_id}]包含链接，过滤规则跳过"
                else:
                    filter_reason = f"媒体组[{message.media_group_id}]不包含关键词({', '.join(keywords)})，过滤规则跳过"
                
                logger.info(f"媒体组消息 [ID: {message.id}] {filter_reason}")
                self._emit_message_filtered(message, filter_reason)
                # 标记已通知UI
                self.media_group_keyword_filter[message.media_group_id]['ui_notified'] = True
                return
        
        # 根据已记录的检测结果决定是否过滤（后续消息直接使用缓存结果）
        filter_result = self.media_group_keyword_filter[message.media_group_id]
        if not filter_result['keywords_passed'] or not filter_result['links_passed']:
            # 直接返回，不再发送UI通知
            return
        
        # 【优化】媒体类型过滤 - 恢复早期过滤以提高性能
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
            logger.debug(f"【关键】保存媒体组 {media_group_id} 的原始标题: '{message.caption}'")
            logger.debug(f"【关键】当前消息ID: {message.id}, 媒体类型: {self._get_message_media_type(message)}")
        
        # 更新统计：总接收数
        self.media_group_filter_stats[media_group_id]['total_received'] += 1
        
        # 添加详细的过滤前调试信息
        message_media_type = self._get_message_media_type(message)
        logger.debug(f"【关键】检查消息 {message.id} 媒体类型: type='{message_media_type}', allowed={allowed_media_types}")
        
        # 【优化】恢复媒体类型过滤，但只在有明确配置时进行
        if allowed_media_types and message_media_type and not self._is_media_type_allowed(message_media_type, allowed_media_types):
            media_type_names = {
                "photo": "照片", "video": "视频", "document": "文件", "audio": "音频",
                "animation": "动画", "sticker": "贴纸", "voice": "语音", "video_note": "视频笔记"
            }
            media_type_name = media_type_names.get(message_media_type.value, message_media_type.value)
            filter_reason = f"媒体类型({media_type_name})不在允许列表中"
            
            # 添加关键调试信息
            logger.debug(f"【关键】消息 {message.id} 被过滤: {filter_reason}")
            logger.debug(f"【关键】过滤时media_group_filter_stats状态: {self.media_group_filter_stats.get(media_group_id, 'NOT_FOUND')}")
            
            # 【新增debug日志】记录被早期过滤的消息详情
            logger.debug(f"【早期过滤】消息ID: {message.id}, 媒体组ID: {media_group_id}, 媒体类型: {message_media_type}, 允许类型: {allowed_media_types}")
            
            logger.info(f"媒体组消息 [ID: {message.id}] 的{filter_reason}，跳过处理")
            
            # 更新统计：过滤数
            self.media_group_filter_stats[media_group_id]['filtered_count'] += 1
            
            # 【新增debug日志】记录过滤后的统计状态
            filter_stats = self.media_group_filter_stats[media_group_id]
            logger.debug(f"【早期过滤统计】媒体组 {media_group_id}: 总接收={filter_stats['total_received']}, 已过滤={filter_stats['filtered_count']}")
            
            # 添加小延迟确保UI事件处理顺序正确
            await asyncio.sleep(0.05)  # 50ms延迟，确保new_message事件先被UI处理
            self._emit_message_filtered(message, filter_reason)
            
            # 检查是否需要触发媒体组处理：如果已经收到了预期数量的消息，或者超时
            should_trigger_processing = False
            filter_stats = self.media_group_filter_stats[media_group_id]
            
            # 如果有预期数量且已达到预期数量
            if expected_count and filter_stats['total_received'] >= expected_count:
                should_trigger_processing = True
                logger.info(f"媒体组 {media_group_id} 已收到预期的所有消息 ({filter_stats['total_received']}/{expected_count})，触发处理检查")
            
            # 如果需要触发处理，检查缓存中是否有消息需要处理
            if should_trigger_processing:
                # 检查缓存中是否有该媒体组的消息
                channel_id = message.chat.id
                if (channel_id in self.media_group_cache and 
                    media_group_id in self.media_group_cache[channel_id]):
                    
                    group_data = self.media_group_cache[channel_id][media_group_id]
                    cached_messages = group_data['messages']
                    pair_config_cached = group_data['pair_config']
                    
                    if cached_messages:
                        logger.info(f"媒体组 {media_group_id} 收到预期数量的消息，开始处理缓存中的 {len(cached_messages)} 条消息")
                        
                        # 标记为已处理
                        self.processed_media_groups.add(media_group_id)
                        
                        # 清理缓存
                        del self.media_group_cache[channel_id][media_group_id]
                        
                        # 处理媒体组
                        await self._process_media_group(cached_messages, pair_config_cached)
            
            return
        
        # 【修复】现在所有通过检测的消息都会添加到缓存，媒体类型过滤将在最终处理时进行
        logger.debug(f"【修复】消息 [ID: {message.id}] 通过检测，将添加到缓存 (媒体类型: {message_media_type})")
        
        # 只有通过了所有过滤的消息才会添加到缓存
        channel_id = message.chat.id
        
        # 检查媒体组是否已被处理
        if media_group_id in self.processed_media_groups:
            # 检查是否是最近处理的媒体组（允许5秒内的延迟消息）
            # 这里我们暂时放宽限制，允许延迟消息继续添加
            logger.debug(f"媒体组 {media_group_id} 已被处理，但允许延迟消息 [ID: {message.id}] 添加")
            # 不立即返回，继续处理延迟消息
        
        # 检查是否已有相同媒体组在获取中
        if media_group_id in self.fetching_media_groups:
            # 如果已经在获取中，添加到缓存
            await self._add_message_to_cache(message, media_group_id, channel_id, pair_config)
            return
            
        # 检查缓存中是否已有此媒体组的消息，或者创建新的媒体组缓存
        if (channel_id in self.media_group_cache and 
            media_group_id in self.media_group_cache[channel_id]):
            # 添加到现有缓存
            await self._add_message_to_cache(message, media_group_id, channel_id, pair_config)
            return
        elif media_group_id in self.processed_media_groups:
            # 如果媒体组已被处理但缓存已清理，为延迟消息创建临时缓存
            logger.info(f"为已处理媒体组 {media_group_id} 的延迟消息创建临时缓存")
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
            
            # 如果缓存的消息数量已经达到预期，直接处理
            if cached_count >= message_count_in_group:
                logger.info(f"媒体组 {media_group_id} 缓存消息数量已满足预期，直接处理")
                await self._add_message_to_cache(message, media_group_id, channel_id, pair_config)
                return
            
            # 记录获取时间
            self.last_media_group_fetch[media_group_id] = current_time
            
            # 尝试使用API获取完整媒体组
            try:
                # 将当前消息添加到缓存
                await self._add_message_to_cache(message, media_group_id, channel_id, pair_config)
                
                # 标记为正在获取
                self.fetching_media_groups.add(media_group_id)
                
                # 创建API获取任务
                asyncio.create_task(self._fetch_media_group_via_api(
                    media_group_id, channel_id, message_count_in_group, pair_config
                ))
                
                return
                
            except Exception as e:
                logger.error(f"API获取媒体组 {media_group_id} 失败: {str(e)}")
                # 移除获取标记
                self.fetching_media_groups.discard(media_group_id)
        
        # 如果不需要API获取或API获取失败，直接添加到缓存
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
        
        # 【新增debug日志】记录缓存状态
        logger.debug(f"【缓存添加】添加消息 [ID: {message.id}] 到媒体组 {media_group_id}, 媒体类型: {self._get_message_media_type(message)}")
        logger.debug(f"【缓存状态】媒体组 {media_group_id} 现有 {len(messages)} 条消息，消息ID: {[msg.id for msg in messages]}")
        
        logger.debug(f"添加消息 [ID: {message.id}] 到媒体组 {media_group_id}, 现有 {len(messages)} 条消息")
        
        # 注意：不在此处发射new_message事件，因为该事件已经在Monitor.handle_new_message中发射了
        # 这样确保不会重复发射事件，保持UI显示的一致性
        
        # 检查是否应该处理媒体组
        should_process = False
        process_reason = ""
        
        # 如果缓存的消息数量达到10条或更多，立即处理（避免缓存过大）
        if len(messages) >= 10:
            should_process = True
            process_reason = f"已收集到 {len(messages)} 条消息，达到处理阈值"
        # 如果距离第一条消息超过15秒，强制处理
        elif time.time() - group_data['first_message_time'] > 15.0:
            should_process = True  
            process_reason = f"距离第一条消息已超过15秒，强制处理避免超时"
        # 如果有media_group_count信息且消息数量已达到，立即处理
        elif hasattr(message, 'media_group_count') and message.media_group_count and len(messages) >= message.media_group_count:
            should_process = True
            process_reason = f"媒体组消息已收集完整({len(messages)}/{message.media_group_count})"
        
        if should_process:
            logger.info(f"媒体组 {media_group_id} {process_reason}，开始处理")
            # 标记为已处理
            self.processed_media_groups.add(media_group_id)
            
            # 先清理延迟任务引用，避免在处理过程中延迟任务访问已清理的数据
            if media_group_id in self.pending_delay_tasks:
                # 取消正在等待的延迟任务
                delay_task = self.pending_delay_tasks[media_group_id]
                if not delay_task.done():
                    delay_task.cancel()
                    logger.debug(f"已取消媒体组 {media_group_id} 的延迟检查任务")
                del self.pending_delay_tasks[media_group_id]
            
            # 从缓存中删除此媒体组
            del self.media_group_cache[channel_id][media_group_id]
            
            # 如果此频道没有更多媒体组，移除整个频道条目
            if not self.media_group_cache[channel_id]:
                del self.media_group_cache[channel_id]
                
            # 移除获取标记，如果存在的话
            if media_group_id in self.fetching_media_groups:
                self.fetching_media_groups.remove(media_group_id)
            
            # 处理完整的媒体组
            await self._process_media_group(messages, pair_config)
        else:
            # 如果当前消息较少，安排一个延迟检查任务
            # 优化：减少延迟时间，加快媒体组转发速度
            if len(messages) <= 8:  # 从5增加到8，确保更多情况下有延迟检查
                # 避免为同一个媒体组重复创建延迟任务
                if media_group_id not in self.pending_delay_tasks:
                    # 优化：将延迟从8秒缩短到3秒，加快转发速度
                    delay_task = asyncio.create_task(self._delayed_media_group_check(media_group_id, channel_id, 3.0))
                    self.pending_delay_tasks[media_group_id] = delay_task
                    logger.debug(f"为媒体组 {media_group_id} 创建延迟检查任务")
    
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
                logger.debug(f"延迟检查: 媒体组 {media_group_id} 已被处理，跳过")
                return
            
            # 检查媒体组是否还在缓存中
            if (channel_id not in self.media_group_cache or 
                media_group_id not in self.media_group_cache[channel_id]):
                logger.debug(f"延迟检查: 媒体组 {media_group_id} 不在缓存中，可能已被处理")
                return
            
            group_data = self.media_group_cache[channel_id][media_group_id]
            messages = group_data['messages']
            pair_config = group_data['pair_config']
            
            # 修复：使用last_update_time而不是first_message_time来判断是否超时
            # 这样确保最后一条消息收到后有足够的等待时间
            time_since_last_update = time.time() - group_data['last_update_time']
            time_since_first_message = time.time() - group_data['first_message_time']
            
            # 优化延迟检查的处理条件，加快转发速度：
            # 1. 如果距离最后更新已经超过2秒（从5秒优化到2秒），且消息数量大于0，则处理
            # 2. 如果距离第一条消息超过10秒（从20秒优化到10秒），且消息数量大于0，则强制处理
            should_process = (
                (time_since_last_update > 2.0 and len(messages) > 0) or
                (time_since_first_message > 10.0 and len(messages) > 0)
            )
            
            if should_process:
                logger.info(f"延迟检查: 媒体组 {media_group_id} 收集到 {len(messages)} 条消息，"
                           f"距离最后更新 {time_since_last_update:.1f}s，距离第一条消息 {time_since_first_message:.1f}s，开始处理（优化后延迟更短）")
                
                # 标记为已处理
                self.processed_media_groups.add(media_group_id)
                
                # 先清理延迟任务引用和缓存，再处理媒体组
                # 这样可以避免在处理过程中其他延迟任务访问已清理的数据
                if media_group_id in self.pending_delay_tasks:
                    del self.pending_delay_tasks[media_group_id]
                
                # 从缓存中删除此媒体组
                del self.media_group_cache[channel_id][media_group_id]
                
                # 如果此频道没有更多媒体组，移除整个频道条目
                if not self.media_group_cache[channel_id]:
                    del self.media_group_cache[channel_id]
                    
                # 移除获取标记，如果存在的话
                if media_group_id in self.fetching_media_groups:
                    self.fetching_media_groups.remove(media_group_id)
                
                # 最后处理媒体组
                await self._process_media_group(messages, pair_config)
            else:
                logger.debug(f"延迟检查: 媒体组 {media_group_id} 还需要等待更多消息或时间")
            
        except Exception as e:
            # 改进错误日志，提供更详细的信息
            logger.error(f"延迟检查媒体组 {media_group_id} (频道: {channel_id}) 时出错: {type(e).__name__}: {str(e)}")
            import traceback
            logger.error(f"延迟检查错误详情: {traceback.format_exc()}")
        finally:
            # 清理延迟任务引用，无论是否成功处理
            if media_group_id in self.pending_delay_tasks:
                del self.pending_delay_tasks[media_group_id]
                logger.debug(f"已清理媒体组 {media_group_id} 的延迟任务引用")
    
    async def _process_media_group(self, messages: List[Message], pair_config: dict):
        """处理媒体组
        
        Args:
            messages: 媒体组消息列表（可能是过滤后的）
            pair_config: 频道对配置
        """
        try:
            # 获取源频道信息
            source_id = messages[0].chat.id
            source_title = messages[0].chat.title or "未知频道"
            media_group_id = messages[0].media_group_id
            
            # 【修复1】增强媒体类型过滤配置获取和调试
            logger.debug(f"【调试】原始pair_config结构: {pair_config}")
            logger.debug(f"【调试】源频道ID: {source_id}, 媒体组ID: {media_group_id}")
            
            # 尝试多种方式获取媒体类型配置
            allowed_media_types = None
            
            # 方式1：直接从pair_config获取
            if 'media_types' in pair_config:
                allowed_media_types = pair_config.get('media_types', [])
                logger.debug(f"【调试】从pair_config直接获取到media_types: {allowed_media_types}")
            
            # 方式2：从nested结构获取（如果配置是嵌套的）
            elif 'filter_config' in pair_config and 'media_types' in pair_config['filter_config']:
                allowed_media_types = pair_config['filter_config']['media_types']
                logger.debug(f"【调试】从filter_config获取到media_types: {allowed_media_types}")
            
            # 方式3：兜底 - 从channel_pairs获取
            else:
                logger.debug(f"【调试】pair_config中没有media_types，尝试从channel_pairs获取")
                logger.debug(f"【调试】当前channel_pairs keys: {list(self.channel_pairs.keys())}")
                for channel_id, stored_config in self.channel_pairs.items():
                    if channel_id == source_id:
                        allowed_media_types = stored_config.get('media_types', [])
                        logger.debug(f"【调试】从channel_pairs获取到media_types: {allowed_media_types}")
                        break
                
                if allowed_media_types is None:
                    logger.debug(f"【调试】在channel_pairs中也未找到源频道{source_id}的配置")
            
            # 确保是列表格式并验证配置
            if allowed_media_types is None:
                allowed_media_types = []
                logger.debug(f"【调试】media_types配置为None，设置为空列表")
            
            # 验证配置有效性
            allowed_media_types = self._validate_media_types_config(allowed_media_types)
            logger.info(f"【关键】媒体组处理使用的媒体类型过滤配置: {allowed_media_types}")
            
            # 添加调试日志，记录core.py中构建的text_replacements字典，而不是text_filter列表
            logger.debug(f"MediaGroupHandler接收到的pair_config:")
            logger.debug(f"  source_id: {source_id}")
            logger.debug(f"  remove_captions: {pair_config.get('remove_captions', False)}")
            logger.debug(f"  text_replacements: {pair_config.get('text_replacements', {})}")
            logger.debug(f"  media_types: {pair_config.get('media_types', [])}")
            logger.debug(f"  target_channels: {pair_config.get('target_channels', [])}")
            
            # 【关键修复】从media_group_filter_stats恢复原始媒体组说明
            original_caption = None
            filtered_message_ids = set()  # 【新增】获取被过滤的消息ID列表
            logger.debug(f"【关键】检查media_group_filter_stats中是否有媒体组 {media_group_id}")
            logger.debug(f"【关键】当前media_group_filter_stats keys: {list(self.media_group_filter_stats.keys())}")
            
            if media_group_id in self.media_group_filter_stats:
                filter_stats = self.media_group_filter_stats[media_group_id]
                original_caption = filter_stats.get('original_caption')
                # 【修复】安全获取filtered_message_ids字段
                filtered_message_ids = filter_stats.get('filtered_message_ids', set())  # 【新增】获取被过滤的消息ID
                logger.debug(f"【关键】从media_group_filter_stats恢复原始说明: '{original_caption}'")
                logger.debug(f"【关键】获取到被过滤的消息ID列表: {filtered_message_ids}")
                logger.debug(f"【关键】完整的filter_stats数据: {filter_stats}")
                # 清理已使用的统计数据
                del self.media_group_filter_stats[media_group_id]
                logger.debug(f"【关键】已清理media_group_filter_stats中的数据")
            else:
                logger.debug(f"【关键】media_group_filter_stats中没有找到媒体组 {media_group_id} 的数据")
            
            # 【严格防护】排除被早期过滤的消息
            if filtered_message_ids:
                original_message_count = len(messages)
                messages = [msg for msg in messages if msg.id not in filtered_message_ids]
                filtered_count = original_message_count - len(messages)
                logger.info(f"【严格防护】从媒体组 {media_group_id} 中排除了 {filtered_count} 条早期过滤的消息")
                logger.debug(f"【严格防护】被排除的消息ID: {filtered_message_ids}")
                logger.debug(f"【严格防护】剩余消息数量: {len(messages)}")
                
                # 如果所有消息都被过滤了，直接返回
                if not messages:
                    logger.info(f"【严格防护】媒体组 {media_group_id} 的所有消息都已被过滤，跳过处理")
                    return False
            
            # 如果从过滤后的消息中也找不到说明，检查是否还有其他来源
            if not original_caption:
                for msg in messages:
                    if msg.caption and msg.caption.strip():
                        original_caption = msg.caption.strip()
                        logger.debug(f"【关键】从过滤后的消息中找到说明: '{original_caption}'")
                        break
                if not original_caption:
                    logger.debug(f"【关键】过滤后的消息中也没有找到说明")
            
            # 获取配置参数
            remove_captions = pair_config.get('remove_captions', False)
            # 直接使用core.py中构建的text_replacements字典，而不是text_filter列表
            text_replacements = pair_config.get('text_replacements', {})
            
            # 解析目标频道
            target_channels = []
            for target_channel_config in pair_config.get('target_channels', []):
                try:
                    # 检查target_channel_config的类型
                    if isinstance(target_channel_config, tuple) and len(target_channel_config) >= 3:
                        # 如果已经是包含频道信息的元组，直接使用
                        target_channels.append(target_channel_config)
                        logger.debug(f"使用已解析的目标频道: {target_channel_config[2]}")
                    elif isinstance(target_channel_config, (str, int)):
                        # 如果是字符串或整数，需要解析
                        # 先调用resolve_channel获得标准化的频道ID
                        resolved_channel_id, _ = await self.channel_resolver.resolve_channel(str(target_channel_config))
                        # 然后获得数字ID
                        numeric_id = await self.channel_resolver.get_channel_id(resolved_channel_id)
                        # 最后获得频道信息
                        channel_info_str, _ = await self.channel_resolver.format_channel_info(numeric_id)
                        if numeric_id:
                            target_channels.append((str(target_channel_config), numeric_id, channel_info_str))
                            logger.debug(f"解析目标频道: {target_channel_config} -> {channel_info_str}")
                    else:
                        logger.warning(f"无法识别的目标频道配置类型: {type(target_channel_config)}, 值: {target_channel_config}")
                        continue
                except Exception as e:
                    logger.error(f"解析目标频道失败 {target_channel_config}: {str(e)}")
                    continue
            
            if not target_channels:
                logger.warning(f"没有有效的目标频道，跳过媒体组处理")
                return False
        
            logger.info(f"开始转发媒体组 [ID: {media_group_id}] 从 {source_title} 到 {len(target_channels)} 个目标频道")
            
            # 【新增】区分禁止转发和非禁止转发频道
            direct_forward_channels = []  # 非禁止转发频道
            restricted_channels = []      # 禁止转发频道
            
            # 检测每个目标频道是否支持直接转发
            for target_channel, target_id, target_info in target_channels:
                try:
                    # 更安全的检测方法：尝试获取频道信息来判断转发限制
                    # 我们可以通过尝试使用forward_messages API调用来检测，但不实际发送
                    # 或者根据频道类型和权限来判断
                    
                    # 方法1：尝试检查频道权限
                    try:
                        chat_info = await self.client.get_chat(target_id)
                        # 如果是私人频道且有特定限制，可能禁止转发
                        # 但这个检测不够准确，我们使用另一种方法
                    except Exception:
                        pass
                    
                    # 方法2：使用已知的禁止转发频道列表或配置
                    # 如果配置中明确标记了某些频道禁止转发，优先使用配置
                    
                    # 方法3：基于经验的简单检测 - 假设大部分频道支持直接转发
                    # 只有在实际转发失败时才切换到下载上传方式
                    # 为了避免副作用，我们先假设都支持直接转发，失败时再切换
                    
                    direct_forward_channels.append((target_channel, target_id, target_info))
                    logger.debug(f"假设频道 {target_info} 支持直接转发，将尝试直接转发")
                        
                except Exception as e:
                    # 如果获取频道信息失败，保守地使用下载上传方式
                    restricted_channels.append((target_channel, target_id, target_info))
                    logger.debug(f"无法确定频道 {target_info} 的转发支持状态，使用下载上传方式: {str(e)}")
            
            success_count = 0
            
            # 【修复2】处理非禁止转发频道（使用直接转发）- 确保正确传递allowed_media_types
            if direct_forward_channels:
                logger.info(f"尝试使用直接转发方式处理 {len(direct_forward_channels)} 个频道")
                logger.debug(f"【关键】传递给_process_direct_forward_media_group的allowed_media_types: {allowed_media_types}")
                
                direct_success, fallback_channels = await self._process_direct_forward_media_group(
                    messages=messages,
                    source_id=source_id,
                    target_channels=direct_forward_channels,
                    original_caption=original_caption,
                    remove_captions=remove_captions,
                    text_replacements=text_replacements,
                    media_group_id=media_group_id,
                    allowed_media_types=allowed_media_types  # 确保传递验证后的配置
                )
                if direct_success:
                    success_count += len(direct_forward_channels) - len(fallback_channels)
                
                # 如果有频道直接转发失败，添加到禁止转发频道列表中
                if fallback_channels:
                    logger.info(f"有 {len(fallback_channels)} 个频道直接转发失败，将使用下载上传方式")
                    restricted_channels.extend(fallback_channels)
            
            # 【保持原有】处理禁止转发频道（使用下载上传）
            if restricted_channels:
                logger.info(f"使用下载上传方式处理 {len(restricted_channels)} 个禁止转发频道")
                
                # 创建RestrictedForwardHandler实例
                if not hasattr(self, '_restricted_handler') or self._restricted_handler is None:
                    self._restricted_handler = RestrictedForwardHandler(self.client, self.channel_resolver)
                    logger.debug("创建了新的RestrictedForwardHandler实例")
                
                # 【关键修复】如果有原始说明，传递给RestrictedForwardHandler
                caption_to_pass = original_caption if original_caption else None
                logger.debug(f"【关键】传递给RestrictedForwardHandler的说明: '{caption_to_pass}'")
                
                # 使用增强的RestrictedForwardHandler统一处理方法处理禁止转发频道
                restricted_success = await self._restricted_handler.process_restricted_media_group_to_multiple_targets(
                    messages=messages,
                    source_channel=str(source_id),
                    source_id=source_id,
                    target_channels=restricted_channels,
                    caption=caption_to_pass,  # 传递原始说明，让RestrictedForwardHandler处理文本替换
                    remove_caption=remove_captions,
                    allowed_media_types=allowed_media_types,  # 传递媒体类型过滤配置
                    text_replacements=text_replacements,      # 传递文本替换配置
                    event_emitter=self.emit,
                    message_type="媒体组"
                )
                
                if restricted_success:
                    success_count += len(restricted_channels)
            
            total_success = success_count == len(target_channels)
            
            if total_success:
                logger.info(f"成功处理媒体组 {media_group_id} 到所有目标频道")
            else:
                logger.warning(f"媒体组 {media_group_id} 部分处理失败，成功: {success_count}/{len(target_channels)}")
            
            return total_success
            
        except Exception as e:
            logger.error(f"处理媒体组时异常: {str(e)}", error_type="MEDIA_GROUP_PROCESS", recoverable=True)
            import traceback
            logger.debug(f"错误详情:\n{traceback.format_exc()}")
            return False
    
    async def _process_direct_forward_media_group(self, messages: List[Message], source_id: int, 
                                                 target_channels: List[Tuple[str, int, str]], 
                                                 original_caption: str, remove_captions: bool, 
                                                 text_replacements: Dict[str, str], media_group_id: str,
                                                 allowed_media_types: List = None) -> Tuple[bool, List[Tuple[str, int, str]]]:
        """
        处理非禁止转发频道的媒体组直接转发
        
        Args:
            messages: 媒体组消息列表
            source_id: 源频道ID  
            target_channels: 非禁止转发的目标频道列表
            original_caption: 原始说明文字
            remove_captions: 是否移除说明
            text_replacements: 文本替换规则
            media_group_id: 媒体组ID
            allowed_media_types: 允许的媒体类型列表（可选）
            
        Returns:
            Tuple[bool, List]: (是否有频道处理成功, 需要回退到下载上传的频道列表)
        """
        try:
            # 【新增debug日志】记录进入函数时的消息详情
            logger.debug(f"【直接转发开始】媒体组 {media_group_id} 进入_process_direct_forward_media_group")
            logger.debug(f"【直接转发开始】接收到的消息数量: {len(messages)}")
            logger.debug(f"【直接转发开始】接收到的消息ID: {[msg.id for msg in messages]}")
            logger.debug(f"【直接转发开始】接收到的消息媒体类型: {[self._get_message_media_type(msg) for msg in messages]}")
            logger.debug(f"【直接转发开始】允许的媒体类型: {allowed_media_types}")
            
            # 【严格防护】在处理前检查，确保没有被早期过滤的消息
            if hasattr(self, 'media_group_filter_stats') and media_group_id in self.media_group_filter_stats:
                early_filtered_ids = self.media_group_filter_stats[media_group_id].get('filtered_message_ids', set())
                if early_filtered_ids:
                    # 再次过滤被早期过滤的消息
                    pre_filter_count = len(messages)
                    messages = [msg for msg in messages if msg.id not in early_filtered_ids]
                    early_filtered_count = pre_filter_count - len(messages)
                    
                    if early_filtered_count > 0:
                        logger.warning(f"【二次防护】在直接转发处理中发现并排除了 {early_filtered_count} 条早期被过滤的消息")
                        logger.debug(f"【二次防护】被排除的消息ID: {early_filtered_ids}")
                        
                        # 如果所有消息都被早期过滤了，直接返回
                        if not messages:
                            logger.warning(f"【二次防护】媒体组 {media_group_id} 的所有消息都被早期过滤，停止处理")
                            return False, []
            
            success_count = 0
            fallback_channels = []  # 需要回退到下载上传方式的频道
            
            # 【修复1】增强媒体类型配置获取和调试
            logger.debug(f"【调试】接收到的allowed_media_types参数: {allowed_media_types}")
            logger.debug(f"【调试】当前source_id: {source_id}")
            logger.debug(f"【调试】当前channel_pairs keys: {list(self.channel_pairs.keys())}")
            
            # 确保allowed_media_types不为None
            if allowed_media_types is None:
                allowed_media_types = []
                logger.debug(f"【调试】allowed_media_types为None，设置为空列表")
            
            # 【修复2】增强媒体类型过滤逻辑
            filtered_messages = messages
            original_message_count = len(messages)
            
            logger.debug(f"【调试】开始媒体类型过滤检查:")
            logger.debug(f"  - 原始消息数量: {original_message_count}")
            logger.debug(f"  - 允许的媒体类型: {allowed_media_types}")
            logger.debug(f"  - 是否需要过滤: {bool(allowed_media_types)}")
            
            if allowed_media_types:  # 只有当列表不为空时才进行过滤
                logger.info(f"对媒体组 {media_group_id} 应用媒体类型过滤，允许类型: {allowed_media_types}")
                
                # 先保存原始媒体说明
                if not original_caption:
                    for msg in messages:
                        if msg.caption and msg.caption.strip():
                            original_caption = msg.caption.strip()
                            logger.debug(f"从消息 [ID: {msg.id}] 获取原始媒体说明: '{original_caption}'")
                            break
                
                # 执行媒体类型过滤
                filtered_messages = []
                filtered_out_count = 0
                
                for msg in messages:
                    msg_media_type = self._get_message_media_type(msg)
                    logger.debug(f"  消息 [ID: {msg.id}] 媒体类型: {msg_media_type}")
                    
                    # 【新增debug日志】记录每条消息的过滤检查
                    logger.debug(f"【过滤检查】消息 [ID: {msg.id}] 媒体类型: {msg_media_type}, 是否在允许列表中: {msg_media_type in allowed_media_types if msg_media_type else 'N/A'}")
                    
                    # 【修复3】修复媒体类型检查逻辑
                    if msg_media_type:
                        # 处理enum类型和字符串类型
                        if hasattr(msg_media_type, 'value'):
                            media_type_str = msg_media_type.value
                        else:
                            media_type_str = str(msg_media_type)
                        
                        # 检查是否在允许列表中（allowed_media_types已经是字符串列表）
                        is_allowed = media_type_str in allowed_media_types
                        
                        logger.debug(f"    媒体类型 {media_type_str} 是否允许: {is_allowed}")
                        
                        if is_allowed:
                            filtered_messages.append(msg)
                        else:
                            filtered_out_count += 1
                            # 发送过滤事件
                            media_type_names = {
                                "photo": "照片", "video": "视频", "document": "文件", "audio": "音频",
                                "animation": "动画", "sticker": "贴纸", "voice": "语音", "video_note": "视频笔记"
                            }
                            media_type_name = media_type_names.get(media_type_str, media_type_str)
                            filter_reason = f"媒体类型({media_type_name})不在允许列表中"
                            logger.info(f"媒体组消息 [ID: {msg.id}] 的{filter_reason}，从转发中移除")
                            
                            # 发送过滤消息事件到UI
                            if self.emit:
                                try:
                                    source_info_str = self.get_cached_channel_info(source_id)
                                    self.emit("message_filtered", msg.id, source_info_str, filter_reason)
                                except Exception as e:
                                    logger.error(f"发送过滤事件失败: {e}")
                    else:
                        # 无媒体类型的消息（如纯文本）
                        logger.debug(f"    消息 [ID: {msg.id}] 无媒体类型，跳过过滤")
                        filtered_messages.append(msg)  # 纯文本消息通常允许通过
                
                # 检查过滤结果
                if not filtered_messages:
                    logger.info(f"【过滤完成】媒体组 {media_group_id} 的所有消息都被媒体类型过滤器排除，跳过转发")
                    # 发送统计事件
                    if hasattr(self, 'monitor') and self.monitor:
                        self.monitor._emit_signal('media_group_processed', {
                            'media_group_id': media_group_id,
                            'total_messages': original_message_count,
                            'forwarded_messages': 0,
                            'filtered_messages': original_message_count,
                            'source_channel': self.get_cached_channel_info(source_id),
                            'target_channels': len(target_channels),
                            'status': 'all_filtered'
                        })
                    return True, []  # 全部过滤也算"成功"，不需要fallback
                
                # 【新增debug日志】记录过滤完成后的结果
                logger.debug(f"【过滤完成】媒体组 {media_group_id} 过滤结果: 原始={original_message_count}条, 剩余={len(filtered_messages)}条, 被过滤={filtered_out_count}条")
                logger.debug(f"【过滤完成】剩余消息ID: {[msg.id for msg in filtered_messages]}")
                logger.debug(f"【过滤完成】剩余消息媒体类型: {[self._get_message_media_type(msg) for msg in filtered_messages]}")
                
                logger.info(f"【过滤完成】媒体组 {media_group_id} 媒体类型过滤：{original_message_count} -> {len(filtered_messages)} 条消息")
            
            # 【关键修复】正确判断是否发生了过滤
            # 如果配置了媒体类型过滤，就认为发生了过滤（无论是早期过滤还是当前过滤）
            # 因为早期过滤可能已经在handle_media_group_message阶段过滤了一些消息
            messages_were_filtered = bool(allowed_media_types)
            if messages_were_filtered:
                logger.debug(f"【关键修复】检测到媒体类型过滤配置: {allowed_media_types}，将使用send_media_group重组媒体组")
            
            # 如果在当前阶段也发生了进一步过滤，记录日志
            current_stage_filtered = len(filtered_messages) != original_message_count
            if current_stage_filtered:
                logger.debug(f"【当前阶段过滤】在_process_direct_forward_media_group中进一步过滤了 {original_message_count - len(filtered_messages)} 条消息")
            
            # 确定最终的说明文字和处理方式
            final_caption = None
            actually_modified = False
            use_copy_media_group = False  # 是否需要使用copy_media_group
            
            # 【修复】改进移除媒体说明的逻辑 - 优先级：移除媒体说明 > 文本替换
            if remove_captions:
                # 移除说明 - 最高优先级，忽略文本替换
                final_caption = ""  # 空字符串表示移除说明
                actually_modified = bool(original_caption)
                use_copy_media_group = True
                logger.debug(f"移除媒体组说明，原始说明: '{original_caption}'，忽略文本替换")
            else:
                # 不移除媒体说明时，才考虑文本替换
                if text_replacements and original_caption:
                    # 应用文本替换
                    replaced_caption = original_caption
                    for find_text, replace_text in text_replacements.items():
                        if find_text in replaced_caption:
                            replaced_caption = replaced_caption.replace(find_text, replace_text)
                            actually_modified = True
                            logger.debug(f"应用文本替换: '{find_text}' -> '{replace_text}'")
                    
                    final_caption = replaced_caption
                    use_copy_media_group = True
                    logger.debug(f"文本替换后的说明: '{final_caption}'")
                else:
                    # 使用原始说明或None（保持原始）
                    final_caption = None  # None表示保持原始说明
                    # 【关键】如果进行了媒体类型过滤，即使没有文本替换也需要使用copy_media_group重组
                    if messages_were_filtered:
                        use_copy_media_group = True
                        final_caption = original_caption if original_caption else ""
                        logger.debug(f"媒体组被过滤需要重组，保持原始说明: '{original_caption}'")
                    else:
                        logger.debug(f"保持原始媒体组说明: '{original_caption}'")
            
            # 准备要转发的消息ID
            message_ids = [msg.id for msg in filtered_messages]
            
            # 对每个非禁止转发频道进行转发
            for target_channel, target_id, target_info in target_channels:
                try:
                    # 【新增debug日志】记录使用的转发方式
                    logger.debug(f"【转发方式选择】媒体组 {media_group_id} -> {target_info}: use_copy_media_group={use_copy_media_group}, messages_were_filtered={messages_were_filtered}")
                    
                    if use_copy_media_group:
                        # 检查是否需要媒体类型过滤
                        if messages_were_filtered:
                            # 【关键修复】当存在媒体类型过滤时，使用send_media_group重组媒体组
                            logger.debug(f"存在媒体类型过滤，使用send_media_group重组 {len(filtered_messages)} 条过滤后的消息到 {target_info}")
                            
                            # 构建InputMedia对象列表
                            input_media_list = []
                            for i, msg in enumerate(filtered_messages):
                                try:
                                    # 准备说明文字：只有第一条消息设置说明
                                    caption = None
                                    if i == 0:
                                        if final_caption == "":
                                            caption = ""  # 移除说明
                                        elif final_caption:
                                            caption = final_caption  # 设置替换后的说明
                                        else:
                                            caption = original_caption or ""  # 保持原始说明
                                    
                                    # 根据消息类型创建InputMedia对象
                                    input_media = await self._create_input_media_from_message(msg, caption)
                                    if input_media:
                                        input_media_list.append(input_media)
                                    else:
                                        logger.warning(f"无法为消息 {msg.id} 创建InputMedia对象")
                                        
                                except Exception as media_error:
                                    logger.error(f"创建InputMedia对象失败，消息ID: {msg.id}, 错误: {str(media_error)}")
                                    continue
                            
                            if input_media_list:
                                # 使用send_media_group发送重组的媒体组
                                sent_messages = await self.client.send_media_group(
                                    chat_id=target_id,
                                    media=input_media_list,
                                    disable_notification=True
                                )
                                logger.info(f"成功使用send_media_group重组 {len(sent_messages)} 条过滤后的消息到 {target_info}")
                            else:
                                logger.error(f"没有有效的InputMedia对象，跳过发送到 {target_info}")
                                continue
                        
                        else:
                            # 【保持原有逻辑】没有媒体类型过滤时使用copy_media_group
                            logger.debug(f"无媒体类型过滤，使用copy_media_group转发完整媒体组到 {target_info}，说明: '{final_caption}'")
                            
                            if final_caption == "":
                                # 空字符串表示移除说明
                                await self.client.copy_media_group(
                                    chat_id=target_id,
                                    from_chat_id=source_id,
                                    message_id=message_ids[0],  # 重组媒体组的第一条消息ID
                                    captions="",  # 空字符串移除说明
                                    disable_notification=True
                                )
                            elif final_caption:
                                # 有具体的替换说明或保持原始说明
                                await self.client.copy_media_group(
                                    chat_id=target_id,
                                    from_chat_id=source_id,
                                    message_id=message_ids[0],  # 重组媒体组的第一条消息ID
                                    captions=final_caption,  # 设置说明
                                    disable_notification=True
                                )
                            else:
                                # None或空说明，不设置captions参数（保持原始说明）
                                await self.client.copy_media_group(
                                    chat_id=target_id,
                                    from_chat_id=source_id,
                                    message_id=message_ids[0],  # 重组媒体组的第一条消息ID
                                    disable_notification=True
                                )
                    else:
                        # 方式3: forward_messages (保留原始信息，无过滤无修改)
                        logger.debug(f"使用forward_messages转发原始媒体组到 {target_info}，保留原始说明")
                        logger.debug(f"【forward_messages】转发消息ID列表: {message_ids}")
                        await self.client.forward_messages(
                            chat_id=target_id,
                            from_chat_id=source_id,
                            message_ids=message_ids,
                            disable_notification=True
                        )
                    
                    logger.info(f"成功直接转发媒体组 {media_group_id} 到 {target_info}")
                    success_count += 1
                    
                    # 发射转发成功事件（为整个媒体组发射一次事件，而不是每条消息）
                    if self.emit:
                        try:
                            source_info_str, _ = await self.channel_resolver.format_channel_info(source_id)
                        except Exception:
                            source_info_str = str(source_id)
                        
                        # 生成媒体组的显示ID
                        message_ids = [msg.id for msg in filtered_messages]
                        display_id = self._generate_media_group_display_id(message_ids, media_group_id)
                        
                        # 为整个媒体组发射一次事件
                        self.emit("forward", display_id, source_info_str, target_info, True, modified=actually_modified)
                    
                except Exception as e:
                    # 检查是否是禁止转发错误
                    error_str = str(e).lower()
                    if any(keyword in error_str for keyword in ['forward', 'restricted', 'forbidden', 'not allowed']):
                        logger.info(f"频道 {target_info} 禁止转发，将回退到下载上传方式: {str(e)}")
                        fallback_channels.append((target_channel, target_id, target_info))
                    else:
                        logger.error(f"直接转发媒体组到 {target_info} 失败: {str(e)}")
                        
                        # 发射转发失败事件（为整个媒体组发射一次事件，而不是每条消息）
                        if self.emit:
                            try:
                                source_info_str, _ = await self.channel_resolver.format_channel_info(source_id)
                            except Exception:
                                source_info_str = str(source_id)
                            
                            # 生成媒体组的显示ID
                            message_ids = [msg.id for msg in filtered_messages]
                            display_id = self._generate_media_group_display_id(message_ids, media_group_id)
                            
                            # 为整个媒体组发射一次失败事件
                            self.emit("forward", display_id, source_info_str, target_info, False, modified=actually_modified)
                
                # 添加延迟避免触发限制
                await asyncio.sleep(0.15)
            
            # 返回是否有成功的频道，以及需要回退的频道列表
            has_success = success_count > 0
            return has_success, fallback_channels
            
        except Exception as e:
            logger.error(f"处理非禁止转发频道媒体组时异常: {str(e)}")
            import traceback
            logger.debug(f"错误详情:\n{traceback.format_exc()}")
            # 发生异常时，将所有频道都标记为需要回退
            return False, target_channels
    
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
                                
                                # 首先应用关键词过滤 - API路径
                                keywords = pair_config.get('keywords', [])
                                if keywords:
                                    # 检查该媒体组是否已经进行过关键词检查
                                    if media_group_id not in self.media_group_keyword_filter:
                                        # 首次检查该媒体组，需要获取媒体组的说明文字
                                        media_group_caption = None
                                        
                                        # 从API获取的消息中寻找说明
                                        for msg in complete_media_group:
                                            if msg.caption:
                                                media_group_caption = msg.caption
                                                logger.debug(f"从API获取的媒体组 {media_group_id} 中找到说明: '{media_group_caption}'")
                                                break
                                        
                                        # 检查媒体组说明是否包含关键词
                                        keywords_passed = False
                                        if media_group_caption:
                                            keywords_passed = any(keyword.lower() in media_group_caption.lower() for keyword in keywords)
                                            if keywords_passed:
                                                logger.info(f"API获取的媒体组 {media_group_id} 的说明包含关键词({', '.join(keywords)})，允许转发")
                                            else:
                                                logger.info(f"API获取的媒体组 {media_group_id} 的说明不包含关键词({', '.join(keywords)})，过滤整个媒体组")
                                        else:
                                            logger.info(f"API获取的媒体组 {media_group_id} 没有说明文字，算作不含关键词，过滤整个媒体组")
                                        
                                        # 记录该媒体组的关键词检查结果
                                        self.media_group_keyword_filter[media_group_id] = {
                                            'keywords_passed': keywords_passed,
                                            'checked': True,
                                            'ui_notified': False  # 添加UI通知标记
                                        }
                                        
                                        # 如果首次检查发现不通过关键词过滤，发送UI通知
                                        if not keywords_passed:
                                            # 添加小延迟确保UI事件处理顺序正确
                                            await asyncio.sleep(0.05)  # 50ms延迟，确保new_message事件先被UI处理
                                            filter_reason = f"媒体组[{message.media_group_id}]不包含关键词({', '.join(keywords)})，过滤规则跳过"
                                            logger.info(f"媒体组消息 [ID: {message.id}] {filter_reason}")
                                            self._emit_message_filtered(message, filter_reason)
                                            # 标记已通知UI
                                            self.media_group_keyword_filter[message.media_group_id]['ui_notified'] = True
                                            return
                                    
                                    # 根据关键词检查结果决定是否处理
                                    if not self.media_group_keyword_filter[media_group_id]['keywords_passed']:
                                        logger.info(f"API获取的媒体组 {media_group_id} 被关键词过滤，跳过转发")
                                        # 标记为已处理（即使没有转发）
                                        self.processed_media_groups.add(media_group_id)
                                        
                                        # 清理过滤统计
                                        if media_group_id in self.media_group_filter_stats:
                                            del self.media_group_filter_stats[media_group_id]
                                        # 清理媒体组关键词过滤状态
                                        if media_group_id in self.media_group_keyword_filter:
                                            del self.media_group_keyword_filter[media_group_id]
                                        
                                        # 清理缓存
                                        if channel_id in self.media_group_cache and media_group_id in self.media_group_cache[channel_id]:
                                            del self.media_group_cache[channel_id][media_group_id]
                                            if not self.media_group_cache[channel_id]:
                                                del self.media_group_cache[channel_id]
                                        continue
                                
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
                                        # 清理媒体组关键词过滤状态
                                        if media_group_id in self.media_group_keyword_filter:
                                            del self.media_group_keyword_filter[media_group_id]
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
        已废弃：请统一使用 src.utils.text_utils.is_media_type_allowed
        """
        from src.utils.text_utils import is_media_type_allowed
        return is_media_type_allowed(message_media_type, allowed_media_types)
    
    def _contains_links(self, text: str) -> bool:
        """
        检查文本中是否包含链接
        
        Args:
            text: 要检查的文本
            
        Returns:
            bool: 是否包含链接
        """
        from src.utils.text_utils import contains_links
        return contains_links(text) 

    def _generate_media_group_display_id(self, message_ids: List[int], media_group_id: str) -> str:
        """生成安全的媒体组显示ID，用于UI显示
        
        Args:
            message_ids: 消息ID列表
            media_group_id: 媒体组ID
            
        Returns:
            str: 安全的显示ID
        """
        try:
            if not message_ids:
                import time
                timestamp = int(time.time())
                return f"媒体组[0个文件]-{timestamp}"
            
            message_count = len(message_ids)
            min_message_id = min(message_ids)
            
            if min_message_id <= 0:
                import time
                timestamp = int(time.time())
                return f"媒体组[{message_count}个文件]-{timestamp}"
            
            return f"媒体组[{message_count}个文件]-{min_message_id}"
            
        except Exception as e:
            logger.error(f"生成媒体组显示ID时出错: {e}")
            import time
            timestamp = int(time.time())
            return f"媒体组[未知]-{timestamp}"

    def _save_media_group_original_caption(self, media_group_id: str, caption: str):
        """保存媒体组的原始说明
        
        Args:
            media_group_id: 媒体组ID
            caption: 原始说明文本
        """
        # 【修复】确保media_group_filter_stats中有这个媒体组的记录，包含所有必需字段
        if media_group_id not in self.media_group_filter_stats:
            self.media_group_filter_stats[media_group_id] = {
                'total_expected': 0,
                'filtered_count': 0,
                'total_received': 0,
                'original_caption': None,
                'filtered_message_ids': set()  # 【修复】添加缺失的字段
            }
        
        # 只在还没有保存过原始说明时才保存（避免覆盖）
        if not self.media_group_filter_stats[media_group_id]['original_caption']:
            self.media_group_filter_stats[media_group_id]['original_caption'] = caption
            logger.debug(f"【关键】_save_media_group_original_caption: 为媒体组 {media_group_id} 保存原始说明: '{caption}'")
    
    def _emit_message_filtered(self, message: Message, filter_reason: str):
        """发送消息过滤事件到UI
        
        Args:
            message: 被过滤的消息
            filter_reason: 过滤原因
        """
        if hasattr(self, 'emit') and self.emit:
            # 使用缓存的频道信息，避免重复API调用
            source_info_str = self.get_cached_channel_info(message.chat.id)
            self.emit("message_filtered", message.id, source_info_str, filter_reason)

    async def _send_filtered_media_group(self, filtered_messages: List[Message], pair_config: dict, target_channels: List[Tuple[str, int, str]]):
        """发送过滤后重组的媒体组
        
        Args:
            filtered_messages: 过滤后的消息列表
            pair_config: 频道对配置
            target_channels: 目标频道列表
        """
        try:
            # 输入验证
            if not filtered_messages:
                logger.warning("过滤后的消息列表为空，无法发送重组媒体组")
                return
                
            if not target_channels:
                logger.warning("目标频道列表为空，无法发送重组媒体组") 
                return
            
            # 再次验证消息的有效性
            valid_messages = []
            for msg in filtered_messages:
                if msg and hasattr(msg, 'id') and hasattr(msg, 'chat'):
                    valid_messages.append(msg)
                else:
                    logger.warning(f"发现无效的消息对象，跳过: {msg}")
            
            if not valid_messages:
                logger.warning("没有有效的消息对象，无法发送重组媒体组")
                return
                
            filtered_messages = valid_messages
            logger.info(f"开始发送过滤后重组的媒体组，包含 {len(filtered_messages)} 条有效消息")
            
            # 获取源频道信息
            source_chat_id = filtered_messages[0].chat.id
            media_group_id = filtered_messages[0].media_group_id
            
            try:
                source_title = filtered_messages[0].chat.title
            except:
                source_title = str(source_chat_id)
            
            logger.info(f"开始发送过滤后重组的媒体组 [原ID: {media_group_id}] 从 {source_title} 到 {len(target_channels)} 个目标频道")
            
            # 获取配置参数
            remove_captions = pair_config.get('remove_captions', False)
            # 直接使用core.py中构建的text_replacements字典，而不是text_filter列表
            text_replacements = pair_config.get('text_replacements', {})
            allowed_media_types = pair_config.get('media_types', [])
            
            # 统一使用RestrictedForwardHandler处理重组媒体组
            source_channel = str(source_chat_id)
            
            # 创建RestrictedForwardHandler实例
            if not hasattr(self, '_restricted_handler') or self._restricted_handler is None:
                self._restricted_handler = RestrictedForwardHandler(self.client, self.channel_resolver)
                logger.debug("创建了新的RestrictedForwardHandler实例")
            
            logger.info(f"使用RestrictedForwardHandler统一处理重组媒体组 {media_group_id}")
            
            # 注意：不在这里处理文本替换，让RestrictedForwardHandler统一处理
            # 使用RestrictedForwardHandler的统一处理方法
            success = await self._restricted_handler.process_restricted_media_group_to_multiple_targets(
                messages=filtered_messages,
                source_channel=source_channel,
                source_id=source_chat_id,
                target_channels=target_channels,
                caption=None,  # 不传递预处理的标题，让RestrictedForwardHandler自己处理
                remove_caption=remove_captions,
                text_replacements=text_replacements,  # 传递文本替换配置
                event_emitter=self.emit,
                message_type="重组媒体组"
            )
            
            if success:
                logger.info(f"成功发送过滤后重组的媒体组 {media_group_id}")
            else:
                logger.warning(f"发送过滤后重组的媒体组失败: {media_group_id}")
            
            # 清理媒体组过滤统计，防止内存泄漏
            if media_group_id in self.media_group_filter_stats:
                del self.media_group_filter_stats[media_group_id]
                logger.debug(f"清理媒体组 {media_group_id} 的过滤统计信息")
            # 清理媒体组关键词过滤状态
            if media_group_id in self.media_group_keyword_filter:
                del self.media_group_keyword_filter[media_group_id]
                logger.debug(f"清理媒体组 {media_group_id} 的关键词过滤状态")
                
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
                if media_group_id and media_group_id in self.media_group_keyword_filter:
                    del self.media_group_keyword_filter[media_group_id]
                    logger.debug(f"异常清理媒体组 {media_group_id} 的关键词过滤状态")
            except Exception:
                pass  # 忽略清理过程中的异常

    def _validate_media_types_config(self, allowed_media_types):
        """
        验证媒体类型配置的有效性
        
        Args:
            allowed_media_types: 媒体类型配置列表
            
        Returns:
            list: 验证后的有效媒体类型列表
        """
        if not allowed_media_types:
            return []
        
        valid_types = []
        valid_type_names = ['photo', 'video', 'document', 'audio', 'animation', 'sticker', 'voice', 'video_note']
        
        for media_type in allowed_media_types:
            type_value = None
            
            # 处理不同类型的配置值
            if hasattr(media_type, 'value'):
                # 处理枚举类型
                type_value = media_type.value
            elif isinstance(media_type, str):
                # 处理字符串类型
                type_value = media_type
            else:
                # 处理其他类型，尝试转换为字符串
                type_value = str(media_type)
            
            # 验证是否为有效的媒体类型
            if type_value in valid_type_names:
                if type_value not in valid_types:  # 避免重复
                    valid_types.append(type_value)
            else:
                logger.warning(f"无效的媒体类型配置: {media_type} (值: {type_value}), 已忽略")
        
        logger.debug(f"验证后的媒体类型配置: {valid_types}")
        return valid_types

    def _record_filtered_message(self, media_group_id: str, message_id: int, filter_reason: str):
        """记录被过滤的消息信息"""
        if media_group_id not in self.media_group_filter_stats:
            self.media_group_filter_stats[media_group_id] = {
                'filtered_messages': [],
                'filter_reasons': [],
                'original_caption': None
            }
            
        self.media_group_filter_stats[media_group_id]['filtered_messages'].append(message_id)
        self.media_group_filter_stats[media_group_id]['filter_reasons'].append(filter_reason)
        
        logger.debug(f"记录过滤消息 - 媒体组: {media_group_id}, 消息ID: {message_id}, 原因: {filter_reason}")
    
    async def _create_input_media_from_message(self, message: Message, caption: str = None):
        """
        从消息对象创建InputMedia对象，用于send_media_group
        
        Args:
            message: Pyrogram消息对象
            caption: 可选的说明文字
            
        Returns:
            InputMedia对象或None（如果消息类型不支持）
        """
        try:
            if message.photo:
                # 处理照片
                return InputMediaPhoto(
                    media=message.photo.file_id,
                    caption=caption
                )
            elif message.video:
                # 处理视频
                return InputMediaVideo(
                    media=message.video.file_id,
                    caption=caption,
                    duration=getattr(message.video, 'duration', None),
                    width=getattr(message.video, 'width', None),
                    height=getattr(message.video, 'height', None),
                    supports_streaming=getattr(message.video, 'supports_streaming', None)
                )
            elif message.document:
                # 处理文档
                return InputMediaDocument(
                    media=message.document.file_id,
                    caption=caption
                )
            elif message.audio:
                # 处理音频
                return InputMediaAudio(
                    media=message.audio.file_id,
                    caption=caption,
                    duration=getattr(message.audio, 'duration', None),
                    performer=getattr(message.audio, 'performer', None),
                    title=getattr(message.audio, 'title', None)
                )
            elif message.animation:
                # 处理动画(GIF)
                return InputMediaAnimation(
                    media=message.animation.file_id,
                    caption=caption,
                    duration=getattr(message.animation, 'duration', None),
                    width=getattr(message.animation, 'width', None),
                    height=getattr(message.animation, 'height', None)
                )
            else:
                logger.warning(f"不支持的媒体类型，消息ID: {message.id}")
                return None
                
        except Exception as e:
            logger.error(f"创建InputMedia对象失败，消息ID: {message.id}, 错误: {str(e)}")
            return None

    async def _get_media_group_text(self, media_group_id: str, channel_id: int) -> str:
        """
        获取媒体组的完整文本，遍历所有消息获取第一个文本
        
        Args:
            media_group_id: 媒体组ID
            channel_id: 频道ID
            
        Returns:
            str: 媒体组的文本内容，如果没有找到则返回空字符串
        """
        try:
            # 首先检查缓存中是否已有该媒体组的消息
            if (channel_id in self.media_group_cache and 
                media_group_id in self.media_group_cache[channel_id]):
                cached_messages = self.media_group_cache[channel_id][media_group_id]['messages']
                
                # 遍历缓存的消息，查找第一个有文本的消息
                for msg in cached_messages:
                    text = msg.text or msg.caption or ""
                    if text.strip():
                        logger.debug(f"从缓存消息 [ID: {msg.id}] 获取媒体组 {media_group_id} 的文本: '{text[:50]}...'")
                        return text.strip()
            
            # 如果缓存中没有找到，尝试从API获取
            try:
                # 获取媒体组的所有消息
                messages = []
                async for msg in self.client.get_chat_history(channel_id, limit=100):
                    if msg.media_group_id == media_group_id:
                        messages.append(msg)
                        # 如果找到有文本的消息，立即返回
                        text = msg.text or msg.caption or ""
                        if text.strip():
                            logger.debug(f"从API消息 [ID: {msg.id}] 获取媒体组 {media_group_id} 的文本: '{text[:50]}...'")
                            return text.strip()
                
                # 如果遍历完所有消息都没有找到文本
                logger.debug(f"媒体组 {media_group_id} 没有找到任何文本内容")
                return ""
                
            except Exception as e:
                logger.error(f"通过API获取媒体组 {media_group_id} 文本失败: {str(e)}")
                return ""
                
        except Exception as e:
            logger.error(f"获取媒体组 {media_group_id} 文本时发生错误: {str(e)}")
            return ""

    async def _fetch_media_group_via_api(self, media_group_id: str, channel_id: int, expected_count: int, pair_config: dict):
        """
        通过API获取完整的媒体组消息
        
        Args:
            media_group_id: 媒体组ID
            channel_id: 频道ID
            expected_count: 预期的消息数量
            pair_config: 频道对配置
        """
        try:
            logger.info(f"开始通过API获取媒体组 {media_group_id} 的完整消息")
            
            # 获取媒体组的所有消息
            messages = []
            async for msg in self.client.get_chat_history(channel_id, limit=100):
                if msg.media_group_id == media_group_id:
                    messages.append(msg)
                    # 如果已经获取到足够多的消息，停止获取
                    if len(messages) >= expected_count:
                        break
            
            logger.info(f"API获取到媒体组 {media_group_id} 的 {len(messages)} 条消息")
            
            # 将获取到的消息添加到缓存
            for msg in messages:
                await self._add_message_to_cache(msg, media_group_id, channel_id, pair_config)
            
            # 移除获取标记
            self.fetching_media_groups.discard(media_group_id)
            
        except Exception as e:
            logger.error(f"通过API获取媒体组 {media_group_id} 失败: {str(e)}")
            # 移除获取标记
            self.fetching_media_groups.discard(media_group_id)