"""
转发模块，负责将消息从源频道转发到目标频道
"""

import os
import time
import asyncio
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Union, Any, Optional, Tuple, Set

from pyrogram import Client
from pyrogram.errors import FloodWait, ChatForwardsRestricted, ChannelPrivate

from src.utils.ui_config_manager import UIConfigManager
from src.utils.config_utils import convert_ui_config_to_dict
from src.utils.channel_resolver import ChannelResolver
from src.utils.database_manager import DatabaseManager
from src.modules.downloader import Downloader
from src.modules.uploader import Uploader
from src.utils.logger import get_logger
from src.utils.video_processor import VideoProcessor

# 导入重构后的组件
from src.modules.forward.message_filter import MessageFilter
from src.modules.forward.message_iterator import MessageIterator
from src.modules.forward.message_downloader import MessageDownloader
from src.modules.forward.direct_forwarder import DirectForwarder
from src.modules.forward.media_uploader import MediaUploader
from src.modules.forward.media_group_collector import MediaGroupCollector
from src.modules.forward.parallel_processor import ParallelProcessor

_logger = get_logger()

class Forwarder():
    """
    转发模块，负责将消息从源频道转发到目标频道
    """
    
    def __init__(self, client: Client, ui_config_manager: UIConfigManager, channel_resolver: ChannelResolver, history_manager: DatabaseManager, downloader: Downloader, uploader: Uploader, app=None):
        """
        初始化转发模块
        
        Args:
            client: Pyrogram客户端实例
            ui_config_manager: UI配置管理器实例
            channel_resolver: 频道解析器实例
            history_manager: 数据库管理器实例
            downloader: 下载模块实例
            uploader: 上传模块实例
            app: 应用程序实例，用于网络错误时立即检查连接状态
        """
        self.client = client
        self.ui_config_manager = ui_config_manager
        self.channel_resolver = channel_resolver
        self.history_manager = history_manager
        self.downloader = downloader
        self.uploader = uploader
        self.app = app  # 保存应用程序实例引用
        
        # 获取UI配置并转换为字典
        ui_config = self.ui_config_manager.get_ui_config()
        self.config = convert_ui_config_to_dict(ui_config)
        
        # 获取转发配置和通用配置
        self.forward_config = self.config.get('FORWARD', {})
        self.general_config = self.config.get('GENERAL', {})
        
        # 创建临时目录
        self.tmp_path = Path(self.forward_config.get('tmp_path', 'tmp'))
        self.tmp_path.mkdir(exist_ok=True)
        
        # 创建消息迭代器，用于获取消息
        self.message_iterator = MessageIterator(self.client, self.channel_resolver, self)
        
        # 创建消息过滤器，用于筛选需要转发的消息
        self.message_filter = MessageFilter(self.config, self._emit_event)
        
        # 创建媒体组收集器，用于分组和优化消息获取
        self.media_group_collector = MediaGroupCollector(self.message_iterator, self.message_filter, self._emit_event)
        
        # 初始化重构后的组件
        self.message_downloader = MessageDownloader(client)
        self.direct_forwarder = DirectForwarder(client, history_manager, self.general_config, self._emit_event)
        self.media_uploader = MediaUploader(client, history_manager, self.general_config)
        self.parallel_processor = ParallelProcessor(client, history_manager, self.general_config, self.config, self._emit_event)
        
        # 设置MessageIterator的转发器引用，用于停止检查
        self.message_iterator.set_forwarder(self)
        
        # 初始化视频处理器
        self.video_processor = VideoProcessor()
        
        # 初始化停止标志
        self.should_stop = False
    
    def _emit_event(self, event_type: str, *args):
        """发射事件到应用层
        
        Args:
            event_type: 事件类型
            *args: 事件参数
        """
        try:
            if self.app:
                if event_type == "message_forwarded" and len(args) >= 2:
                    message_id, target_info = args[0], args[1]
                    self.app.message_forwarded.emit(message_id, target_info)
                    _logger.debug(f"发射message_forwarded信号: 消息{message_id} -> {target_info}")
                
                elif event_type == "media_group_forwarded" and len(args) >= 4:
                    message_ids, target_info, count, target_id = args[0], args[1], args[2], args[3]
                    # 将频道ID转换为字符串，避免64位整数溢出
                    target_id_str = str(target_id)
                    self.app.media_group_forwarded.emit(message_ids, target_info, count, target_id_str)
                    _logger.debug(f"发射media_group_forwarded信号: {len(message_ids)}条消息 -> {target_info} (ID: {target_id_str})")
                
                elif event_type == "message_filtered" and len(args) >= 3:
                    message_id, message_type, filter_reason = args[0], args[1], args[2]
                    # 发射过滤事件到应用
                    if hasattr(self.app, 'message_filtered'):
                        self.app.message_filtered.emit(message_id, message_type, filter_reason)
                        #_logger.debug(f"发射message_filtered信号: {message_type}({message_id}) 过滤原因: {filter_reason}")
                
                elif event_type == "collection_started" and len(args) >= 1:
                    total_count = args[0]
                    # 发射收集开始事件到应用
                    if hasattr(self.app, 'collection_started'):
                        self.app.collection_started.emit(total_count)
                        _logger.debug(f"发射collection_started信号: 总数 {total_count}")
                
                elif event_type == "collection_progress" and len(args) >= 2:
                    current_count, total_count = args[0], args[1]
                    # 发射收集进度事件到应用
                    if hasattr(self.app, 'collection_progress'):
                        self.app.collection_progress.emit(current_count, total_count)
                        _logger.debug(f"发射collection_progress信号: {current_count}/{total_count}")
                
                elif event_type == "collection_completed" and len(args) >= 2:
                    collected_count, total_count = args[0], args[1]
                    # 发射收集完成事件到应用
                    if hasattr(self.app, 'collection_completed'):
                        self.app.collection_completed.emit(collected_count, total_count)
                        _logger.debug(f"发射collection_completed信号: 收集了 {collected_count}/{total_count}")
                
                elif event_type == "collection_error" and len(args) >= 1:
                    error_message = args[0]
                    # 发射收集错误事件到应用
                    if hasattr(self.app, 'collection_error'):
                        self.app.collection_error.emit(error_message)
                        _logger.debug(f"发射collection_error信号: {error_message}")
                
                elif event_type == "text_replacement_applied" and len(args) >= 3:
                    message_desc, original_text, replaced_text = args[0], args[1], args[2]
                    # 发射文本替换信号到UI
                    if hasattr(self.app, 'text_replacement_applied'):
                        self.app.text_replacement_applied.emit(message_desc, original_text, replaced_text)
                        _logger.debug(f"发射text_replacement_applied信号: {message_desc} 原始文本: '{original_text[:30]}...' 替换后文本: '{replaced_text[:30]}...'")
                
                elif event_type == "flood_wait_detected" and len(args) >= 2:
                    wait_time, operation_desc = args[0], args[1]
                    # 发射限流检测信号到UI
                    if hasattr(self.app, 'flood_wait_detected'):
                        self.app.flood_wait_detected.emit(wait_time, operation_desc)
                        _logger.debug(f"发射flood_wait_detected信号: 等待时间 {wait_time}秒, 操作: {operation_desc}")
                
                else:
                    _logger.warning(f"未知事件类型或参数不足: {event_type}, args: {args}")
            else:
                _logger.warning("应用实例为空，无法发射事件")
            
        except Exception as e:
            _logger.error(f"处理DirectForwarder事件失败: {e}")
            _logger.debug(f"事件详情: type={event_type}, args={args}", exc_info=True)
    
    async def forward_messages(self):
        """
        从源频道转发消息到目标频道
        """
        
        _logger.info("开始转发消息")
        
        # 重置停止标志，确保重新开始转发时能正常工作
        self.should_stop = False
        if hasattr(self, 'parallel_processor') and self.parallel_processor:
            self.parallel_processor.should_stop = False
            self.parallel_processor.download_running = False
            self.parallel_processor.upload_running = False
        if hasattr(self, 'direct_forwarder') and self.direct_forwarder:
            self.direct_forwarder.should_stop = False
        
        # 重新从配置文件读取最新配置
        _logger.info("重新从配置文件读取最新转发配置")
        ui_config = self.ui_config_manager.reload_config()
        self.config = convert_ui_config_to_dict(ui_config)
        self.forward_config = self.config.get('FORWARD', {})
        self.general_config = self.config.get('GENERAL', {})
        
        # 更新临时目录路径
        self.tmp_path = Path(self.forward_config.get('tmp_path', 'tmp'))
        self.tmp_path.mkdir(exist_ok=True)
        
        # 重新初始化组件配置
        self.message_filter = MessageFilter(self.config, self._emit_event)
        self.media_uploader = MediaUploader(self.client, self.history_manager, self.general_config)
        self.parallel_processor = ParallelProcessor(self.client, self.history_manager, self.general_config, self.config, self._emit_event)
        
        # 重新设置MessageIterator的转发器引用，用于停止检查
        self.message_iterator.set_forwarder(self)
        
        # 重新创建MediaGroupCollector实例，确保基于最新配置和无状态残留
        self.media_group_collector = MediaGroupCollector(self.message_iterator, self.message_filter, self._emit_event)
        
        # 更新DirectForwarder使用新的MessageFilter实例
        self.direct_forwarder.message_filter = self.message_filter
        
        # 创建临时会话目录
        temp_dir = self._ensure_temp_dir()
        
        # 获取频道对列表
        channel_pairs = self.forward_config.get('forward_channel_pairs', [])
        info_message = f"配置的频道对数量: {len(channel_pairs)}"
        _logger.info(info_message)
        
        if not channel_pairs:
            _logger.warning("没有有效的频道对配置，无法启动转发")
            return
        
        # 转发计数
        forward_count = 0
        total_forward_count = 0
        
        # 收集所有目标频道用于最终消息发送
        all_target_channels = []
        
        # 跟踪实际转发了消息的频道对
        forwarded_pairs = []
        
        # 处理每个频道对
        for pair in channel_pairs:
            # 检查是否收到停止信号
            if self.should_stop:
                _logger.info("收到停止信号，终止转发任务")
                break
                
            source_channel = pair.get("source_channel", "")
            target_channels = pair.get("target_channels", [])
            
            # 检查频道对是否启用
            is_enabled = pair.get("enabled", True)
            if not is_enabled:
                _logger.info(f"跳过已禁用的频道对: {source_channel}")
                continue
            
            # 添加调试信息，显示频道对配置的详细内容
            _logger.debug(f"频道对配置: {pair}")
            _logger.debug(f"关键词配置: {pair.get('keywords', [])} (类型: {type(pair.get('keywords', []))})")
            _logger.debug(f"媒体类型配置: {pair.get('media_types', [])}")
            _logger.debug(f"文本替换配置: {pair.get('text_filter', [])}")
            
            # 显示关键词配置状态
            keywords_in_config = pair.get('keywords', [])
            if keywords_in_config:
                _logger.info(f"🔍 频道对 [{source_channel}] 关键词过滤: {', '.join(keywords_in_config)}")
            else:
                _logger.info(f"📢 频道对 [{source_channel}] 无关键词过滤，转发所有类型的消息")
            
            if not source_channel:
                warning_message = "源频道不能为空，跳过"
                _logger.warning(warning_message)
                continue
            
            if not target_channels:
                warning_message = f"源频道 {source_channel} 没有配置目标频道，跳过"
                _logger.warning(warning_message)
                continue
            
            info_message = f"准备从 {source_channel} 转发到 {len(target_channels)} 个目标频道"
            _logger.info(info_message)
            
            # 记录本频道对的转发计数
            pair_forward_count = 0
            
            try:
                # 解析源频道ID
                source_id = await self.channel_resolver.get_channel_id(source_channel)
                source_info_str, (source_title, _) = await self.channel_resolver.format_channel_info(source_id)
                info_message = f"源频道: {source_info_str}"
                _logger.info(info_message)
                
                source_can_forward = await self.channel_resolver.check_forward_permission(source_id)
                
                # 获取有效的目标频道
                valid_target_channels = []
                for target in target_channels:        
                    try:
                        target_id = await self.channel_resolver.get_channel_id(target)
                        target_info_str, (target_title, _) = await self.channel_resolver.format_channel_info(target_id)
                        valid_target_channels.append((target, target_id, target_info_str))
                        all_target_channels.append((target, target_id, target_info_str))
                        info_message = f"目标频道: {target_info_str}"
                        _logger.info(info_message)
                    except Exception as e:
                        error_message = f"解析目标频道 {target} 失败: {e}"
                        _logger.error(error_message)
                
                if not valid_target_channels:
                    warning_message = f"源频道 {source_channel} 没有有效的目标频道，跳过"
                    _logger.warning(warning_message)
                    continue
                
                if source_can_forward:
                    # 源频道允许转发，直接使用转发功能
                    status_message = "源频道允许直接转发，获取媒体组和消息..."
                    _logger.info(status_message)
                    
                    # 获取目标频道列表（用于历史检查）
                    target_channel_list = [target[0] for target in valid_target_channels]
                    
                    # 使用优化的媒体组获取方法，先过滤已转发的消息ID
                    media_groups, media_group_texts = await self.media_group_collector.get_media_groups_optimized(
                        source_id, source_channel, target_channel_list, pair, self.history_manager
                    )
                    
                    # 发送总媒体组数量
                    total_groups = len(media_groups)
                    
                    # 添加进度事件
                    group_count = 0
                    
                    # 获取当前频道对的隐藏作者配置
                    hide_author = pair.get('hide_author', False)
                    _logger.debug(f"频道对 [{source_channel}] hide_author 配置: {hide_author}")
                    
                    # 如果没有媒体组，跳过此频道对
                    if not media_groups:
                        _logger.info(f"源频道 {source_channel} 没有未转发的媒体组/消息，跳过")
                        continue
                    
                    # 遍历每个媒体组并转发
                    for group_id, messages in media_groups.items():
                        # 检查是否收到停止信号
                        if self.should_stop:
                            _logger.info("收到停止信号，终止媒体组转发")
                            break
                            
                        # 更新进度
                        group_count += 1
                        
                        # 将媒体组文本信息添加到频道对配置中，以便DirectForwarder使用
                        enhanced_pair_config = pair.copy()
                        enhanced_pair_config['media_group_texts'] = media_group_texts
                        
                        # 转发媒体组到所有目标频道
                        success = await self.direct_forwarder.forward_media_group_directly(
                            messages, source_channel, source_id, valid_target_channels, hide_author, enhanced_pair_config
                        )
                        
                        if success:
                            forward_count += 1
                            total_forward_count += 1
                            pair_forward_count += 1
                        
                        # 简短的延迟，避免请求过于频繁
                        await asyncio.sleep(0.5)
                    
                    # 如果收到停止信号，跳出频道对循环
                    if self.should_stop:
                        break
                else:
                    # 源频道不允许转发，需要下载后重新上传
                    status_message = "源频道不允许直接转发，将使用下载后重新上传的方式"
                    _logger.info(status_message)
                    
                    # 创建针对此频道对的临时目录 - 使用安全的文件名
                    safe_source_channel = self._get_safe_path_name(source_channel)
                    safe_target_channels = [self._get_safe_path_name(ch) for ch in target_channels]
                    channel_temp_dir = temp_dir / f"{safe_source_channel}_to_{'_'.join(safe_target_channels)}"
                    channel_temp_dir.mkdir(exist_ok=True)
                    
                    status_message = "获取媒体组信息..."
                    _logger.info(status_message)
                    
                    # 获取目标频道列表（用于历史检查）
                    target_channel_list = [target[0] for target in valid_target_channels]
                    
                    # 使用优化的媒体组信息获取方法，先过滤已转发的消息ID
                    media_groups_info, media_group_texts = await self.media_group_collector.get_media_groups_info_optimized(
                        source_id, source_channel, target_channel_list, pair, self.history_manager
                    )
                    total_groups = len(media_groups_info)
                    
                    # 如果没有媒体组，跳过此频道对
                    if not media_groups_info:
                        _logger.info(f"源频道 {source_channel} 没有未转发的媒体组/消息，跳过")
                        continue
                    
                    # 将媒体组文本信息添加到频道对配置中，传递给ParallelProcessor
                    pair_with_texts = pair.copy()
                    pair_with_texts['media_group_texts'] = media_group_texts
                    if media_group_texts:
                        _logger.debug(f"🔍 Forwarder向ParallelProcessor传递媒体组文本: {len(media_group_texts)} 个")
                    
                    # 检查是否启用纯文本转发并预处理纯文本消息
                    allowed_media_types = pair.get('media_types', [])
                    hide_author = pair.get('hide_author', False)
                    text_forward_count = 0
                    
                    if 'text' in allowed_media_types:
                        _logger.info(f"用户启用了纯文本转发，开始预处理纯文本消息")
                        
                        # 收集所有纯文本消息ID，用于后续从media_groups_info中移除
                        processed_text_message_ids = set()
                        
                        # 遍历媒体组信息，查找纯文本消息
                        for group_id, message_ids in media_groups_info:
                            # 获取消息对象
                            for message_id in message_ids:
                                try:
                                    message = await self._get_message_with_flood_wait(source_id, message_id)
                                    if message and message.text and not message.media:
                                        # 这是纯文本消息，进行转发处理
                                        _logger.debug(f"发现纯文本消息 {message_id}: '{message.text[:50]}...'")
                                        
                                        # 应用链接过滤检查
                                        exclude_links = pair.get('exclude_links', False)
                                        if exclude_links:
                                            message_entities = getattr(message, 'entities', None)
                                            if self.message_filter._contains_links(message.text, message_entities):
                                                _logger.info(f"纯文本消息 {message_id} 包含链接，根据exclude_links配置被过滤")
                                                processed_text_message_ids.add(message_id)
                                                continue
                                        
                                        # 应用文本替换
                                        text_content = message.text
                                        text_replacements = pair.get('text_replacements', {})
                                        if text_replacements:
                                            original_text = text_content
                                            text_content, has_replacement = self.message_filter.apply_text_replacements(text_content, text_replacements)
                                            # 发射文本替换信号到UI
                                            if has_replacement:
                                                self._emit_event("text_replacement_applied", f"消息{message_id}", original_text, text_content)
                                        
                                        # 检查是否移除标题
                                        if pair.get('remove_captions', False):
                                            continue  # 跳过此消息
                                        
                                        # 转发到所有目标频道
                                        for target_channel, target_id, target_info in valid_target_channels:
                                            # 检查是否已转发
                                            if self.history_manager and self.history_manager.is_message_forwarded(source_channel, message_id, target_channel):
                                                _logger.debug(f"纯文本消息 {message_id} 已转发到 {target_info}，跳过")
                                                continue
                                            
                                            try:
                                                if hide_author:
                                                    # 隐藏作者，使用send_message
                                                    sent_message = await self.client.send_message(
                                                        chat_id=target_id,
                                                        text=text_content,
                                                        disable_web_page_preview=True
                                                    )
                                                    _logger.info(f"✅ 使用send_message转发纯文本消息 {message_id} 到 {target_info}")
                                                else:
                                                    # 保留作者，使用forward_messages
                                                    forwarded_messages = await self.client.forward_messages(
                                                        chat_id=target_id,
                                                        from_chat_id=source_id,
                                                        message_ids=message_id,
                                                        disable_notification=True
                                                    )
                                                    _logger.info(f"✅ 使用forward_messages转发纯文本消息 {message_id} 到 {target_info}")
                                                
                                                # 记录转发历史
                                                if self.history_manager:
                                                    self.history_manager.add_forward_record(source_channel, message_id, target_channel, source_id)
                                                
                                                # 发送转发完成信号到UI
                                                self._emit_event("message_forwarded", message_id, target_info)
                                                
                                                text_forward_count += 1
                                                
                                            except Exception as e:
                                                _logger.error(f"转发纯文本消息 {message_id} 到 {target_info} 失败: {e}")
                                        
                                        # 标记为已处理
                                        processed_text_message_ids.add(message_id)
                                        
                                except Exception as e:
                                    _logger.error(f"获取消息 {message_id} 失败: {e}")
                        
                        # 从media_groups_info中移除已处理的纯文本消息
                        if processed_text_message_ids:
                            filtered_media_groups_info = []
                            for group_id, message_ids in media_groups_info:
                                # 过滤掉已处理的纯文本消息ID
                                remaining_ids = [mid for mid in message_ids if mid not in processed_text_message_ids]
                                if remaining_ids:  # 如果还有剩余消息，保留这个媒体组
                                    filtered_media_groups_info.append((group_id, remaining_ids))
                            
                            media_groups_info = filtered_media_groups_info
                            _logger.info(f"已处理 {len(processed_text_message_ids)} 条纯文本消息，剩余 {len(media_groups_info)} 个媒体组待处理")
                    
                    # 更新转发计数
                    pair_forward_count += text_forward_count
                    total_forward_count += text_forward_count
                    
                    # 如果还有媒体组需要处理，使用ParallelProcessor
                    if media_groups_info:
                        # 启动下载和上传任务
                        try:
                            # 使用并行处理器处理此频道对
                            forward_count = await self.parallel_processor.process_parallel_download_upload(
                                source_channel,
                                source_id,
                                media_groups_info,
                                channel_temp_dir,
                                valid_target_channels,
                                pair_with_texts  # 传递包含媒体组文本的配置
                            )
                            
                            # 记录本组转发的消息数
                            total_forward_count += forward_count
                            pair_forward_count += forward_count
                            info_message = f"从 {source_channel} 已转发 {forward_count} 个媒体组/消息"
                            _logger.info(info_message)
                            
                        except Exception as e:
                            error_message = f"下载和上传任务失败: {str(e)}"
                            _logger.error(error_message)
                            import traceback
                            error_details = traceback.format_exc()
                            _logger.error(error_details)
                            continue
                    else:
                        _logger.info(f"所有消息已通过纯文本方式处理，无需使用ParallelProcessor")
                
                # 如果这个频道对实际转发了消息，记录到forwarded_pairs
                if pair_forward_count > 0:
                    forwarded_pairs.append(pair)
                    _logger.debug(f"频道对 [{source_channel}] 成功转发了 {pair_forward_count} 条消息，将发送最终消息")
                else:
                    _logger.debug(f"频道对 [{source_channel}] 没有转发任何消息，不发送最终消息")
            
            except Exception as e:
                error_message = f"处理频道对 {source_channel} 失败: {str(e)}"
                _logger.error(error_message)
                import traceback
                error_details = traceback.format_exc()
                _logger.error(error_details)
                continue
        
        # 转发完成
        status_message = f"🎉 转发任务完成，成功转发 {total_forward_count} 个媒体组/消息"
        _logger.info(status_message)
        
        # 只为实际转发了消息的频道对发送最终消息
        if forwarded_pairs:
            _logger.info(f"转发任务完成，准备为 {len(forwarded_pairs)} 个已转发的频道对检查并发送最终消息...")
            try:
                await self._send_final_messages_by_pairs(forwarded_pairs)
                _logger.info("最终消息发送流程已完成")
            except Exception as e:
                _logger.error(f"发送最终消息时发生错误: {e}")
                import traceback
                _logger.error(f"错误详情: {traceback.format_exc()}")
        else:
            _logger.info("没有频道对转发任何消息，跳过最终消息发送")
        
        # 清理临时文件
        await self._clean_media_dirs(temp_dir)
    
    async def _send_final_messages_by_pairs(self, forwarded_pairs: List[Dict[str, Union[str, List[str]]]]):
        """
        发送最终消息到每个启用了最终消息且实际转发了消息的频道对
        
        Args:
            forwarded_pairs: 实际转发了消息的频道对列表，每个频道对是一个字典，包含'source_channel'和'target_channels'
        """
        _logger.info(f"开始检查最终消息发送配置，共有 {len(forwarded_pairs)} 个已转发的频道对")
        
        for pair in forwarded_pairs:
            source_channel = pair.get("source_channel", "")
            target_channels = pair.get("target_channels", [])
            
            _logger.debug(f"检查频道对 [{source_channel}] 的最终消息配置")
            
            # 检查频道对是否启用（双重检查，虽然forwarded_pairs应该只包含启用的频道对）
            is_enabled = pair.get("enabled", True)
            if not is_enabled:
                _logger.debug(f"频道对 [{source_channel}] 已禁用，跳过最终消息发送")
                continue
            
            # 检查是否启用了发送最终消息功能
            send_final_message = pair.get('send_final_message', False)
            _logger.debug(f"频道对 [{source_channel}] send_final_message: {send_final_message}")
            
            if not send_final_message:
                _logger.debug(f"频道对 [{source_channel}] 未启用发送最终消息功能，跳过")
                continue
            
            _logger.info(f"✅ 频道对 [{source_channel}] 启用了最终消息发送功能")
            
            # 获取HTML文件路径
            html_file_path = pair.get('final_message_html_file', '')
            _logger.debug(f"频道对 [{source_channel}] HTML文件路径: {html_file_path}")
            
            if not html_file_path:
                _logger.warning(f"频道对 [{source_channel}] 未指定最终消息HTML文件路径，跳过发送最终消息")
                continue
            
            html_path = Path(html_file_path)
            if not html_path.exists() or not html_path.is_file():
                _logger.error(f"频道对 [{source_channel}] 最终消息HTML文件不存在或不是文件: {html_file_path}")
                continue
            
            _logger.debug(f"✅ 频道对 [{source_channel}] HTML文件验证通过")
            
            try:
                # 读取HTML文件内容
                with open(html_path, 'r', encoding='utf-8') as f:
                    html_content = f.read().strip()
                
                if not html_content:
                    _logger.warning(f"频道对 [{source_channel}] 最终消息HTML文件内容为空，跳过发送最终消息")
                    continue
                
                _logger.debug(f"✅ 频道对 [{source_channel}] HTML内容读取成功，长度: {len(html_content)} 字符")
                
                # 使用HTML解析模式发送消息
                from pyrogram import enums
                
                # 发送到每个目标频道
                for target in target_channels:
                    try:
                        target_id = await self.channel_resolver.get_channel_id(target)
                        target_info_str, (target_title, _) = await self.channel_resolver.format_channel_info(target_id)
                        
                        message = await self.client.send_message(
                            chat_id=target_id,
                            text=html_content,
                            parse_mode=enums.ParseMode.HTML,
                            disable_web_page_preview=not pair.get('enable_web_page_preview', False)  # 根据配置控制网页预览
                        )
                        
                        _logger.info(f"✅ 最终消息发送成功! 目标: {target_info_str}, 消息ID: {message.id}")
                        
                        # 添加短暂延迟避免速率限制
                        await asyncio.sleep(0.5)
                        
                    except Exception as e:
                        _logger.error(f"❌ 向 {target} 发送最终消息失败: {e}")
                        import traceback
                        _logger.error(f"详细错误信息: {traceback.format_exc()}")
                        continue
                
                _logger.info(f"✅ 频道对 [{source_channel}] 最终消息发送流程完成")
                
            except Exception as e:
                _logger.error(f"❌ 处理频道对 [{source_channel}] 最终消息失败: {e}")
                import traceback
                _logger.error(f"详细错误信息: {traceback.format_exc()}")
        
        _logger.info(f"最终消息发送检查完成")
    
    def _ensure_temp_dir(self) -> Path:
        """
        确保临时目录存在，如果不存在则创建
        
        Returns:
            Path: 临时目录路径
        """
        # 创建临时目录
        session_dir = self.tmp_path / datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir.mkdir(exist_ok=True, parents=True)
        
        debug_message = f"创建转发会话临时目录: {session_dir}"
        _logger.debug(debug_message)
        
        return session_dir
    
    async def _clean_media_dirs(self, dir_path: Optional[Path] = None):
        """
        清理媒体目录
        
        Args:
            dir_path: 要清理的目录路径，如果为None，则清理所有临时目录
        """
        try:
            if dir_path is None:
                # 清理所有临时目录
                if self.tmp_path.exists():
                    # 列出tmp_path下的所有目录
                    for sub_dir in self.tmp_path.iterdir():
                        if sub_dir.is_dir():
                            try:
                                shutil.rmtree(sub_dir)
                                debug_message = f"已清理临时目录: {sub_dir}"
                                _logger.debug(debug_message)
                            except Exception as e:
                                error_message = f"清理临时目录 {sub_dir} 失败: {e}"
                                _logger.error(error_message)
            elif dir_path.exists():
                # 清理指定目录
                try:
                    shutil.rmtree(dir_path)
                    debug_message = f"已清理指定目录: {dir_path}"
                    _logger.debug(debug_message)
                except Exception as e:
                    error_message = f"清理指定目录 {dir_path} 失败: {e}"
                    _logger.error(error_message)
        except Exception as e:
            error_message = f"清理媒体目录失败: {e}"
            _logger.error(error_message)
    
    def _get_safe_path_name(self, path_str: str) -> str:
        """
        将路径字符串转换为安全的文件名，移除无效字符
        
        Args:
            path_str: 原始路径字符串
            
        Returns:
            str: 处理后的安全路径字符串
        """
        # 替换URL分隔符
        safe_str = path_str.replace('://', '_').replace(':', '_')
        
        # 替换路径分隔符
        safe_str = safe_str.replace('\\', '_').replace('/', '_')
        
        # 替换其他不安全的文件名字符
        unsafe_chars = '<>:"|?*'
        for char in unsafe_chars:
            safe_str = safe_str.replace(char, '_')
            
        # 如果结果太长，取MD5哈希值
        if len(safe_str) > 100:
            import hashlib
            safe_str = hashlib.md5(path_str.encode()).hexdigest()
            
        return safe_str
    
    async def _handle_network_error(self, error):
        """
        处理网络相关错误
        
        当检测到网络错误时，通知主应用程序立即检查连接状态
        
        Args:
            error: 错误对象
        """
        _logger.error(f"检测到网络错误: {type(error).__name__}: {error}")
        
        # 如果有应用程序引用，通知应用程序立即检查连接状态
        if self.app and hasattr(self.app, 'check_connection_status_now'):
            try:
                _logger.info("正在触发立即检查连接状态")
                asyncio.create_task(self.app.check_connection_status_now())
            except Exception as e:
                _logger.error(f"触发连接状态检查失败: {e}") 

    async def stop_forward(self):
        """
        停止转发操作
        """
        _logger.info("收到停止转发信号")
        
        # 设置停止标志
        self.should_stop = True
        
        # 停止并行处理器
        if hasattr(self, 'parallel_processor') and self.parallel_processor:
            if hasattr(self.parallel_processor, 'download_running'):
                self.parallel_processor.download_running = False
            if hasattr(self.parallel_processor, 'upload_running'):
                self.parallel_processor.upload_running = False
            if hasattr(self.parallel_processor, 'should_stop'):
                self.parallel_processor.should_stop = True
        
        # 停止直接转发器
        if hasattr(self, 'direct_forwarder') and self.direct_forwarder:
            if hasattr(self.direct_forwarder, 'should_stop'):
                self.direct_forwarder.should_stop = True
        
        _logger.info("转发器已停止") 

    async def _get_message_with_flood_wait(self, source_id, message_id):
        """
        获取消息对象，并处理可能的FloodWait
        
        Args:
            source_id: 源频道ID
            message_id: 消息ID
            
        Returns:
            Message: 获取的消息对象
        """
        try:
            message = await self.client.get_messages(source_id, message_id)
            return message
        except FloodWait as e:
            _logger.info(f"收到FloodWait，等待 {e.x} 秒后重试")
            await asyncio.sleep(e.x)
            return await self._get_message_with_flood_wait(source_id, message_id)
        except Exception as e:
            _logger.error(f"获取消息 {message_id} 失败: {e}")
            return None 