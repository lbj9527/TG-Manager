"""
核心监听模块，负责监听源频道新消息并转发到目标频道
"""

import asyncio
import time
import psutil  # 用于内存监控
from typing import Optional, Set, Callable, Any

from pyrogram import Client, filters
from pyrogram.types import Message

from src.utils.ui_config_manager import UIConfigManager
from src.utils.config_utils import convert_ui_config_to_dict
from src.utils.channel_resolver import ChannelResolver
from src.utils.logger import get_logger

from src.modules.monitor.media_group_handler import MediaGroupHandler
from src.modules.monitor.message_processor import MessageProcessor
from src.modules.monitor.text_filter import TextFilter

# 导入性能优化模块
from src.modules.monitor.performance_monitor import PerformanceMonitor
from src.modules.monitor.enhanced_cache import ChannelInfoCache
from src.modules.monitor.circular_buffer import MessageIdBuffer

# 仅用于内部调试，不再用于UI输出
logger = get_logger()

class Monitor:
    """
    监听模块，监听源频道的新消息，并实时转发到目标频道
    """
    
    def __init__(self, client: Client, ui_config_manager: UIConfigManager, channel_resolver: ChannelResolver, app=None):
        """
        初始化监听模块
        
        Args:
            client: Pyrogram客户端实例
            ui_config_manager: UI配置管理器实例
            channel_resolver: 频道解析器实例
            app: 应用程序实例，用于网络错误时立即检查连接状态
        """
        # 初始化
        super().__init__()
        
        self.client = client
        self.ui_config_manager = ui_config_manager
        self.channel_resolver = channel_resolver
        self.app = app  # 保存应用程序实例引用
        
        # 获取UI配置并转换为字典
        ui_config = self.ui_config_manager.get_ui_config()
        self.config = convert_ui_config_to_dict(ui_config)
        
        # 获取监听配置
        self.monitor_config = self.config.get('MONITOR', {})
        
        # 初始化文本过滤器
        self.text_filter = TextFilter(self.monitor_config)
        
        # 控制变量
        self.should_stop = False
        self.monitor_tasks = []
        
        # 初始化性能监控器
        self.performance_monitor = PerformanceMonitor()
        
        # 初始化增强缓存（替换原来的简单字典缓存）
        self.channel_info_cache = ChannelInfoCache(max_size=500, default_ttl=1800)  # 30分钟TTL
        
        # 初始化消息ID缓冲区（替换原来的简单集合）
        self.processed_messages = MessageIdBuffer(max_size=50000)  # MessageIdBuffer不需要TTL参数
        
        # 定期清理已处理消息ID的任务
        self.cleanup_task = None
        
        # 定期更新内存使用量的任务
        self.memory_monitor_task = None
        
        # 存储所有监听的频道ID
        self.monitored_channels: Set[int] = set()
        
        # 消息处理中
        self.is_processing = False
        
        # 初始化消息处理器和媒体组处理器
        self.message_processor = MessageProcessor(self.client, self.channel_resolver, self._handle_network_error)
        self.media_group_handler = MediaGroupHandler(self.client, self.channel_resolver, self.message_processor)
        
        # 消息处理器列表，用于跟踪注册的处理器
        self.message_handlers = []
        
        # 当前活跃的消息处理器，用于正确清理
        self.current_message_handler = None
    
        # 连接emit信号
        self.media_group_handler.emit = self._emit_signal
        self.message_processor.emit = self._emit_signal
        
        # 设置MediaGroupHandler的monitor引用，用于统一过滤
        self.media_group_handler.set_monitor(self)
        
        # 设置频道信息缓存和性能监控器引用
        self.media_group_handler.set_channel_info_cache(self.channel_info_cache)
        self.media_group_handler.set_performance_monitor(self.performance_monitor)
    
    def _emit_signal(self, signal_type: str, *args, **kwargs):
        """
        统一处理emit信号
        
        Args:
            signal_type: 信号类型
            *args: 信号参数
            **kwargs: 信号关键字参数
        """
        if hasattr(self, 'emit') and self.emit:
            self.emit(signal_type, *args, **kwargs)
    
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
        
        # 在启动新监听之前，先清理旧的处理器和状态
        await self._cleanup_old_handlers()
        
        # 重置停止标志，确保监听器可以正常启动
        self.should_stop = False
        
        # 重置媒体组处理器的停止标志，确保媒体组转发可以正常进行
        if hasattr(self, 'media_group_handler') and self.media_group_handler:
            self.media_group_handler.is_stopping = False
            logger.debug("已重置媒体组处理器的停止标志")
        
        # 重新从配置文件读取最新配置
        logger.info("重新从配置文件读取最新监听配置")
        ui_config = self.ui_config_manager.reload_config()
        self.config = convert_ui_config_to_dict(ui_config)
        self.monitor_config = self.config.get('MONITOR', {})
        
        # 重新初始化文本过滤器
        self.text_filter = TextFilter(self.monitor_config)
        logger.debug("文本过滤器已使用最新配置重新初始化")
        
        # 清空并重新解析监听频道ID
        self.monitored_channels = set()
        
        # 解析所有源频道及其目标频道
        channel_pairs = {}
        
        logger.debug(f"从配置文件读取到 {len(self.monitor_config.get('monitor_channel_pairs', []))} 个频道对:")
        for pair in self.monitor_config.get('monitor_channel_pairs', []):
            source_channel = pair.get('source_channel', '')
            target_channels = pair.get('target_channels', [])
            
            if not source_channel or not target_channels:
                logger.warning(f"跳过无效的频道对配置: source={source_channel}, targets={target_channels}")
                continue
            
            # 解析源频道ID
            try:
                source_id = await self.channel_resolver.get_channel_id(source_channel)
                # 预先获取并缓存源频道信息
                cached_info = self.channel_info_cache.get_channel_info(source_id)
                if cached_info:
                    source_info_str = cached_info[0]
                    source_title = cached_info[1]
                    self.performance_monitor.record_cache_hit()
                else:
                    # 如果缓存中没有，则获取并缓存（兜底方案）
                    try:
                        source_info_str, source_info_tuple = await self.channel_resolver.format_channel_info(source_id)
                        self.channel_info_cache.set_channel_info(source_id, source_info_str, source_info_tuple[0])
                        self.performance_monitor.record_cache_miss()
                        source_title = source_info_tuple[0]
                    except Exception:
                        source_info_str = f"频道 (ID: {source_id})"
                        source_title = f"频道{source_id}"
            except Exception as e:
                logger.warning(f"无法解析源频道 {source_channel}，错误: {e}")
                self.performance_monitor.record_error('api')
                continue
            
            # 解析目标频道ID
            resolved_targets = []
            for target_channel in target_channels:
                try:
                    target_id = await self.channel_resolver.get_channel_id(target_channel)
                    target_info_str, target_info_tuple = await self.channel_resolver.format_channel_info(target_id)
                    # 缓存目标频道信息
                    self.channel_info_cache.set_channel_info(target_id, target_info_str, target_info_tuple[0])
                    self.performance_monitor.record_cache_miss()  # 首次加载记录为miss
                    resolved_targets.append((target_channel, target_id, target_info_str))
                    logger.debug(f"已缓存目标频道信息: {target_info_str}")
                except Exception as e:
                    logger.warning(f"无法解析目标频道 {target_channel}，错误: {e}")
                    self.performance_monitor.record_error('api')
            
            if not resolved_targets:
                logger.warning(f"源频道 {source_channel} 没有有效的目标频道，跳过")
                continue
            
            # 处理文本替换规则
            text_replacements = {}
            text_filter_list = pair.get('text_filter', [])
            for filter_item in text_filter_list:
                original_text = filter_item.get('original_text', '')
                target_text = filter_item.get('target_text', '')
                if original_text:  # 只有当原始文本不为空时才添加替换规则
                    text_replacements[original_text] = target_text
            
            # 获取移除媒体说明配置
            remove_captions = pair.get('remove_captions', False)
            
            # 获取该频道对的媒体类型设置
            media_types = pair.get('media_types', [])
            # 如果没有配置媒体类型，使用默认的所有类型
            if not media_types:
                from src.utils.ui_config_models import MediaType
                media_types = [
                    MediaType.PHOTO, MediaType.VIDEO, MediaType.DOCUMENT, 
                    MediaType.AUDIO, MediaType.ANIMATION, MediaType.STICKER,
                    MediaType.VOICE, MediaType.VIDEO_NOTE
                ]
            
            # 获取该频道对的过滤选项
            keywords = pair.get('keywords', [])
            exclude_forwards = pair.get('exclude_forwards', False)
            exclude_replies = pair.get('exclude_replies', False)
            exclude_text = pair.get('exclude_text', pair.get('exclude_media', False))
            exclude_links = pair.get('exclude_links', False)
            
            # 添加调试日志，显示过滤配置
            logger.debug(f"    过滤配置: forwards={exclude_forwards}, replies={exclude_replies}, text={exclude_text}, links={exclude_links}")
            
            # 存储频道对配置
            channel_pairs[source_id] = {
                'source_channel': source_channel,
                'target_channels': resolved_targets,
                'text_replacements': text_replacements,
                'remove_captions': remove_captions,
                'media_types': media_types,
                'keywords': keywords,
                'exclude_forwards': exclude_forwards,
                'exclude_replies': exclude_replies,
                'exclude_text': exclude_text,
                'exclude_links': exclude_links
            }
            
            # 添加到监听频道集合
            self.monitored_channels.add(source_id)
            
            logger.debug(f"  - 源频道: {source_channel} (ID: {source_id})")
            logger.debug(f"    目标频道: {[t[0] for t in resolved_targets]}")
            logger.debug(f"    文本替换规则: {len(text_replacements)} 条")
            logger.debug(f"    移除媒体说明: {remove_captions}")
        
        if not channel_pairs:
            logger.warning("没有有效的频道对配置，无法启动监听")
            return
        
        # 设置处理中标志
        self.is_processing = True
        
        try:
            # 传递频道对配置给媒体组处理器
            self.media_group_handler.set_channel_pairs(channel_pairs)
            
            # 将需要的配置传递给消息处理器
            self.message_processor.set_monitor_config(self.monitor_config)
            
            # 设置频道信息缓存引用，减少API调用
            self.message_processor.set_channel_info_cache(self.channel_info_cache)
            self.media_group_handler.set_channel_info_cache(self.channel_info_cache)
            
            # 设置性能监控器引用
            self.message_processor.set_performance_monitor(self.performance_monitor)
            self.media_group_handler.set_performance_monitor(self.performance_monitor)
            
            # 重新确保emit信号连接（防止在EventEmitterMonitor包装后丢失连接）
            self.media_group_handler.emit = self._emit_signal
            self.message_processor.emit = self._emit_signal
            
            # 创建并注册消息处理函数
            from pyrogram.handlers import MessageHandler
            
            async def handle_new_message(client: Client, message: Message):
                if not self.is_processing:
                    return
                
                # 记录消息处理开始时间
                start_time = time.time()
                
                try:
                    # 获取来源频道信息
                    source_id = message.chat.id
                    
                    # 获取该源频道的配置
                    if source_id not in channel_pairs:
                        logger.warning(f"收到来自未配置目标的频道 {source_id} 的消息，忽略")
                        return
                        
                    pair_config = channel_pairs[source_id]
                    
                    # 使用缓存的频道信息，避免重复API调用
                    cached_info = self.channel_info_cache.get_channel_info(source_id)
                    if cached_info:
                        source_info_str = cached_info[0]
                        source_title = cached_info[1]
                        self.performance_monitor.record_cache_hit()
                    else:
                        # 如果缓存中没有，则获取并缓存（兜底方案）
                        try:
                            source_info_str, source_info_tuple = await self.channel_resolver.format_channel_info(source_id)
                            self.channel_info_cache.set_channel_info(source_id, source_info_str, source_info_tuple[0])
                            self.performance_monitor.record_cache_miss()
                            source_title = source_info_tuple[0]
                        except Exception:
                            source_info_str = f"频道 (ID: {source_id})"
                            source_title = f"频道{source_id}"
                    
                    # 日志记录消息接收
                    logger.info(f"收到来自 {source_info_str} 的新消息 [ID: {message.id}]")

                    # 注意：暂时不发射新消息事件给UI，等待过滤检查完成后再发射
                    # 这样确保只有通过所有过滤的消息才会在UI中显示

                    # 检查关键词过滤
                    if not self.text_filter.check_keywords(message):
                        return

                    # 如果消息ID已经处理过，跳过
                    if self.processed_messages.is_message_processed(message.id):
                        logger.debug(f"消息 [ID: {message.id}] 已处理过，跳过")
                        return
                        
                    # 将消息ID添加到已处理集合
                    self.processed_messages.mark_message_processed(message.id)

                    # 检查是否为媒体组消息
                    if message.media_group_id:
                        # 【修复】媒体组消息的过滤逻辑
                        # 1. 首先应用通用过滤（转发、回复、纯文本、链接）
                        is_filtered, filter_reason = self.text_filter.apply_universal_filters(message, pair_config)
                        if is_filtered:
                            logger.info(f"媒体组消息 [ID: {message.id}] 被通用过滤规则过滤: {filter_reason}")
                            # 发送过滤消息事件到UI
                            if hasattr(self, 'emit') and self.emit:
                                self.emit("message_filtered", message.id, source_info_str, filter_reason)
                            return

                        # 2. 发射new_message事件给UI（媒体组消息会在media_group_handler中进行链接和关键词检测）
                        if hasattr(self, 'emit') and self.emit:
                            self.emit("new_message", message.id, source_info_str)
                        
                        # 3. 处理媒体组消息（内部会进行链接检测、关键词检测、媒体类型过滤等）
                        await self.media_group_handler.handle_media_group_message(message, pair_config)
                        
                        # 记录处理时间
                        processing_time = time.time() - start_time
                        self.performance_monitor.record_message_processed(processing_time)
                        return

                    # 对于单条消息，在_process_single_message中进行完整过滤检查后再发射事件
                    # 先检查是否会被过滤
                    will_be_filtered, filter_reason = self.text_filter.apply_universal_filters(message, pair_config)
                    if will_be_filtered:
                        # 消息将被过滤，不发射new_message事件
                        logger.info(f"单条消息 [ID: {message.id}] {filter_reason}，根据过滤规则跳过")
                        # 发送过滤消息事件到UI
                        if hasattr(self, 'emit') and self.emit:
                            self.emit("message_filtered", message.id, source_info_str, filter_reason)
                        return

                    # 应用其他过滤条件（关键词、媒体类型等）
                    is_filtered, filter_reason = await self._check_single_message_filters(message, pair_config, source_info_str)
                    if is_filtered:
                        # 消息将被过滤，不发射new_message事件
                        logger.info(f"单条消息 [ID: {message.id}] {filter_reason}，根据过滤规则跳过")
                        return

                    # 如果消息不会被过滤，发射新消息事件给UI
                    if hasattr(self, 'emit') and self.emit:
                        self.emit("new_message", message.id, source_info_str)

                    # 处理单条消息
                    await self._process_single_message(message, pair_config)
                    
                    # 记录处理时间
                    processing_time = time.time() - start_time
                    self.performance_monitor.record_message_processed(processing_time)
                    
                    # 发射消息处理完成事件
                    if hasattr(self, 'emit') and self.emit:
                        self.emit("message_processed", message.id)
                    
                except Exception as e:
                    # 记录错误
                    error_name = type(e).__name__.lower()
                    if any(net_err in error_name for net_err in ['network', 'connection', 'timeout', 'socket']):
                        self.performance_monitor.record_error('network')
                    elif 'api' in error_name or 'telegram' in error_name:
                        self.performance_monitor.record_error('api')
                    else:
                        self.performance_monitor.record_error('other')
                    
                    logger.error(f"处理消息 [ID: {message.id}] 时发生错误: {str(e)}", error_type="MESSAGE_PROCESS", recoverable=True)
            
            # 创建处理器并注册
            handler = MessageHandler(handle_new_message, filters.chat(list(self.monitored_channels)))
            self.client.add_handler(handler)
            
            # 保存当前处理器引用以便后续清理
            self.current_message_handler = handler
            
            logger.info(f"正在监听 {len(self.monitored_channels)} 个频道的新消息")
            logger.debug(f"监听的频道ID列表: {list(self.monitored_channels)}")
            
            # 启动清理任务
            self.cleanup_task = asyncio.create_task(self._cleanup_processed_messages())
            
            # 启动内存监控任务
            self.memory_monitor_task = asyncio.create_task(self._monitor_memory_usage())
            
            # 启动媒体组清理任务
            self.media_group_handler.start_cleanup_task()
            
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
        
        # 清理消息处理器
        await self._cleanup_old_handlers()
        
        # 给正在进行的媒体组转发任务一些时间完成
        # 检查是否有正在进行的媒体组转发
        if hasattr(self, 'media_group_handler') and self.media_group_handler:
            # 等待一小段时间让正在进行的转发任务完成
            if (hasattr(self.media_group_handler, 'media_group_cache') and 
                self.media_group_handler.media_group_cache):
                logger.debug("检测到正在处理的媒体组，等待2秒让转发完成")
                await asyncio.sleep(2)
        
        # 停止媒体组处理器
        await self.media_group_handler.stop()
        
        # 清理RestrictedForwardHandler的临时目录
        if hasattr(self.message_processor, 'restricted_handler') and self.message_processor.restricted_handler:
            try:
                self.message_processor.restricted_handler.cleanup_temp_dirs()
                logger.debug("已清理RestrictedForwardHandler的临时目录")
            except Exception as e:
                logger.error(f"清理RestrictedForwardHandler临时目录失败: {e}")
        
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
        
        # 取消内存监控任务
        if self.memory_monitor_task:
            self.memory_monitor_task.cancel()
            try:
                await self.memory_monitor_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"取消内存监控任务时异常: {str(e)}", error_type="TASK_CANCEL", recoverable=True)
            
            self.memory_monitor_task = None
        
        # 清空已处理消息集合
        previous_count = self.processed_messages.size()
        self.processed_messages.clear()
        logger.info(f"已清理 {previous_count} 条已处理消息记录")
        
        # 清理频道信息缓存
        if hasattr(self, 'channel_info_cache'):
            cache_count = self.channel_info_cache.size()
            self.channel_info_cache.clear()
            logger.debug(f"已清理 {cache_count} 条频道信息缓存")
        
        logger.info("所有监听任务已停止")
    
    async def _cleanup_old_handlers(self):
        """
        清理旧的消息处理器
        """
        try:
            # 移除当前活跃的处理器
            if self.current_message_handler:
                try:
                    self.client.remove_handler(self.current_message_handler)
                    logger.debug("已移除当前消息处理器")
                except Exception as e:
                    logger.error(f"移除当前消息处理器时异常: {str(e)}")
                finally:
                    self.current_message_handler = None
            
            # 移除所有注册的处理器（兼容旧代码）
            for handler in self.message_handlers:
                try:
                    self.client.remove_handler(handler)
                except Exception as e:
                    logger.error(f"移除消息处理器时异常: {str(e)}", error_type="HANDLER_REMOVE", recoverable=True)
            
            # 清空处理器列表
            self.message_handlers.clear()
            
            # 重置处理状态
            self.is_processing = False
            
            # 注意：不清空 monitored_channels，它会在 start_monitoring 中重新构建
            
            logger.debug("已清理所有消息处理器和相关状态")
        except Exception as e:
            logger.error(f"清理消息处理器时异常: {str(e)}", error_type="HANDLER_CLEANUP", recoverable=True)
    
    async def _cleanup_processed_messages(self):
        """
        定期清理已处理消息ID集合和缓存，防止内存无限增长
        """
        try:
            while not self.should_stop:
                await asyncio.sleep(1800)  # 每30分钟清理一次
                
                if self.should_stop:
                    break
                
                # 清理过期的消息ID
                expired_messages = self.processed_messages.cleanup_expired()
                if expired_messages > 0:
                    logger.info(f"已清理 {expired_messages} 条过期的消息记录")
                
                # 清理过期的缓存项
                expired_cache = self.channel_info_cache.cleanup_expired()
                if expired_cache > 0:
                    logger.debug(f"已清理 {expired_cache} 条过期的缓存项")
                    
        except asyncio.CancelledError:
            # 任务被取消，正常退出
            pass
        except Exception as e:
            logger.error(f"清理已处理消息时异常: {str(e)}", error_type="CLEANUP", recoverable=True)
    
    async def _process_single_message(self, message: Message, pair_config: dict):
        """
        处理单条消息
        
        Args:
            message: 消息对象
            pair_config: 频道对配置
        """
        try:
            # 【修复】过滤逻辑已经在handle_new_message中完成，这里只处理转发逻辑
            
            # 获取目标频道列表
            target_channels = pair_config.get('target_channels', [])
            
            if not target_channels:
                logger.warning("没有配置目标频道，跳过单条消息处理")
                return
                
            # 获取文本替换和标题移除配置
            text_replacements = pair_config.get('text_replacements', {})
            remove_captions = pair_config.get('remove_captions', False)
            
            # 检查是否为媒体消息
            from src.utils.text_utils import is_media_message
            is_media = is_media_message(message)
            
            # 获取原始文本
            from src.utils.text_utils import extract_text_from_message
            text = extract_text_from_message(message)
            replaced_text = None
            should_remove_caption = False
            
            # 【优化】改进文本替换逻辑
            if text and text_replacements:
                # 先应用文本替换
                replaced_text = text
                for find_text, replace_text in text_replacements.items():
                    if find_text in replaced_text:
                        replaced_text = replaced_text.replace(find_text, replace_text)
                
                if replaced_text != text:
                    logger.info(f"消息 [ID: {message.id}] 已应用文本替换")
            
            # 【修复】改进移除媒体说明的逻辑 - 优先级：移除媒体说明 > 文本替换
            if remove_captions:
                if is_media:
                    # 媒体消息：移除说明文字，忽略文本替换的结果
                    should_remove_caption = True
                    replaced_text = None  # 强制清空文本替换结果
                    logger.debug(f"媒体消息 [ID: {message.id}] 将移除说明文字，忽略文本替换结果")
                else:
                    # 纯文本消息：移除媒体说明无效，但文本替换依然有效
                    if replaced_text and replaced_text != text:
                        logger.debug(f"纯文本消息 [ID: {message.id}] 移除媒体说明无效，但文本替换已应用")
                    else:
                        logger.debug(f"纯文本消息 [ID: {message.id}] 移除媒体说明无效")
            else:
                # 不移除媒体说明时，使用文本替换的结果
                should_remove_caption = False
            
            # 转发消息
            await self.message_processor.forward_message(
                message=message, 
                target_channels=target_channels,
                use_copy=True,  # 使用copy_message方式以支持文本替换
                replace_caption=replaced_text,
                remove_caption=should_remove_caption,
                text_replacements=text_replacements  # 【修复】传递文本替换规则给禁止转发处理器
            )
            
        except Exception as e:
            logger.error(f"处理单条消息时发生错误: {str(e)}", error_type="PROCESS_SINGLE_MESSAGE", recoverable=True)
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"错误详情: {error_details}")
    
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

    def get_cached_channel_info(self, channel_id: int) -> str:
        """
        获取缓存的频道信息，避免重复API调用
        
        Args:
            channel_id: 频道ID
            
        Returns:
            str: 频道信息字符串
        """
        if hasattr(self, 'channel_info_cache') and self.channel_info_cache:
            cached_info = self.channel_info_cache.get_channel_info(channel_id)
            if cached_info:
                self.performance_monitor.record_cache_hit()
                return cached_info[0]
            else:
                self.performance_monitor.record_cache_miss()
                return f"频道 (ID: {channel_id})"
        else:
            # 如果没有缓存，返回简单格式
            return f"频道 (ID: {channel_id})"

    async def _monitor_memory_usage(self):
        """
        定期监控内存使用量
        """
        try:
            while not self.should_stop:
                await asyncio.sleep(60)  # 每分钟检查一次
                
                if self.should_stop:
                    break
                
                try:
                    # 获取当前进程的内存使用量
                    process = psutil.Process()
                    memory_info = process.memory_info()
                    memory_mb = memory_info.rss / 1024 / 1024  # 转换为MB
                    
                    # 更新性能监控器中的内存使用量
                    self.performance_monitor.update_memory_usage(memory_mb)
                    
                    # 如果内存使用过高，触发主动清理
                    if memory_mb > 500:  # 超过500MB时进行主动清理
                        logger.warning(f"内存使用量较高: {memory_mb:.2f}MB，执行主动清理")
                        
                        # 清理过期项
                        expired_messages = self.processed_messages.cleanup_expired()
                        expired_cache = self.channel_info_cache.cleanup_expired()
                        
                        if expired_messages > 0 or expired_cache > 0:
                            logger.info(f"主动清理完成：消息记录 {expired_messages} 条，缓存项 {expired_cache} 条")
                    
                except Exception as mem_e:
                    logger.debug(f"获取内存信息失败: {mem_e}")
                    
        except asyncio.CancelledError:
            # 任务被取消，正常退出
            pass
        except Exception as e:
            logger.error(f"内存监控异常: {str(e)}", error_type="MEMORY_MONITOR", recoverable=True) 

    async def _check_single_message_filters(self, message: Message, pair_config: dict, source_info_str: str) -> tuple[bool, str]:
        """
        检查单条消息的其他过滤条件（关键词、媒体类型等）
        
        注意：四个排除条件（转发、回复、纯文本、链接）已在TextFilter.apply_universal_filters中处理
        
        Args:
            message: 消息对象
            pair_config: 频道对配置
            source_info_str: 源频道信息字符串
            
        Returns:
            tuple[bool, str]: (是否被过滤, 过滤原因)
        """
        try:
            # 获取该频道对的过滤选项
            keywords = pair_config.get('keywords', [])
            
            # 关键词过滤
            if keywords:
                from src.utils.text_utils import extract_text_from_message
                text_to_check = extract_text_from_message(message).lower()
                keywords_passed = any(keyword.lower() in text_to_check for keyword in keywords)
                if not keywords_passed:
                    filter_reason = f"不包含关键词({', '.join(keywords)})"
                    # 发送过滤消息事件到UI
                    if hasattr(self, 'emit') and self.emit:
                        self.emit("message_filtered", message.id, source_info_str, filter_reason)
                    return True, filter_reason

            # 媒体类型过滤
            allowed_media_types = pair_config.get('media_types', [])
            if allowed_media_types:
                message_media_type = self._get_message_media_type(message)
                if message_media_type and not self._is_media_type_allowed(message_media_type, allowed_media_types):
                    media_type_names = {
                        "photo": "照片", "video": "视频", "document": "文件", "audio": "音频",
                        "animation": "动画", "sticker": "贴纸", "voice": "语音", "video_note": "视频笔记"
                    }
                    media_type_name = media_type_names.get(message_media_type.value, message_media_type.value)
                    filter_reason = f"媒体类型({media_type_name})不在允许列表中"
                    # 发送过滤消息事件到UI
                    if hasattr(self, 'emit') and self.emit:
                        self.emit("message_filtered", message.id, source_info_str, filter_reason)
                    return True, filter_reason

            # 所有过滤检查都通过
            return False, ""
            
        except Exception as e:
            logger.error(f"检查单条消息过滤时发生错误: {str(e)}")
            # 发生错误时认为消息不被过滤，让后续处理决定
            return False, "" 