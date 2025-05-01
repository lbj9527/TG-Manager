"""
核心监听模块，负责监听源频道新消息并转发到目标频道
"""

import asyncio
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
        
        # 已处理的消息ID集合，用于防止重复处理同一条消息
        self.processed_messages: Set[int] = set()
        
        # 定期清理已处理消息ID的任务
        self.cleanup_task = None
        
        # 存储所有监听的频道ID
        self.monitored_channels: Set[int] = set()
        
        # 消息处理中
        self.is_processing = False
        
        # 初始化消息处理器和媒体组处理器
        self.message_processor = MessageProcessor(self.client, self.channel_resolver, self._handle_network_error)
        self.media_group_handler = MediaGroupHandler(self.client, self.channel_resolver, self.message_processor)
        
        # 消息处理器字典，用于跟踪每个源频道的消息处理器
        self.message_handlers = []
    
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
                            'text_replacements': self.text_filter.channel_text_replacements.get(source_channel, {}),
                            'remove_captions': self.text_filter.channel_remove_captions.get(source_channel, False)
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
            # 传递频道对配置给媒体组处理器
            self.media_group_handler.set_channel_pairs(channel_pairs)
            
            # 将需要的配置传递给消息处理器
            self.message_processor.set_monitor_config(self.monitor_config)
            
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
                    
                    # 检查关键词过滤
                    if not self.text_filter.check_keywords(message):
                        return
                    
                    # 如果消息ID已经处理过，跳过
                    if message.id in self.processed_messages:
                        logger.debug(f"消息 [ID: {message.id}] 已处理过，跳过")
                        return
                        
                    # 将消息ID添加到已处理集合
                    self.processed_messages.add(message.id)
                    
                    # 检查是否为媒体组消息
                    if message.media_group_id:
                        # 处理媒体组消息
                        await self.media_group_handler.handle_media_group_message(message, pair_config)
                        return
                    
                    # 处理单条消息
                    await self._process_single_message(message, pair_config)
                    
                except Exception as e:
                    logger.error(f"处理消息 [ID: {message.id}] 时发生错误: {str(e)}", error_type="MESSAGE_PROCESS", recoverable=True)
            
            logger.info(f"正在监听 {len(self.monitored_channels)} 个频道的新消息")
            
            # 启动清理任务
            self.cleanup_task = asyncio.create_task(self._cleanup_processed_messages())
            
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
        
        # 停止媒体组处理器
        await self.media_group_handler.stop()
        
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
    
    async def _process_single_message(self, message: Message, pair_config: dict):
        """
        处理单条消息
        
        Args:
            message: Pyrogram消息对象
            pair_config: 频道对配置
        """
        # 检查消息是否有文本
        if not message.text and not message.caption:
            # 无文本消息，直接转发
            await self.message_processor.forward_message(message, pair_config['target_channels'])
            return
        
        # 获取消息文本
        text = message.text or message.caption
        
        # 应用文本替换规则
        text_replacements = pair_config['text_replacements']
        remove_captions = pair_config['remove_captions']
        
        if text_replacements:
            modified_text = self.text_filter.apply_text_replacements(text, text_replacements)
            if modified_text != text:
                # 文本已被修改，需要重新发送
                await self.message_processor.send_modified_message(message, modified_text, pair_config['target_channels'], remove_captions)
                return
        
        # 检查是否需要移除标题
        if remove_captions and message.caption:
            # 需要移除标题，重新发送
            await self.message_processor.send_modified_message(message, "", pair_config['target_channels'], True)
            return
        
        # 正常转发消息
        await self.message_processor.forward_message(message, pair_config['target_channels'])
        
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

    async def get_message_history(self, channel: str, limit: int = 100):
        """
        获取指定频道的历史消息
        
        Args:
            channel: 频道ID或用户名
            limit: 获取消息的数量限制
            
        Returns:
            获取到的消息列表
        """
        from src.modules.monitor.history_fetcher import get_channel_history
        return await get_channel_history(self.client, self.channel_resolver, channel, limit, self.should_stop) 