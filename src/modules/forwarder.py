"""
转发模块，负责将消息从源频道转发到目标频道
"""

import os
import time
import asyncio
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Union, Any, Optional, Tuple, Set, NamedTuple
from queue import Queue
from dataclasses import dataclass
import re
import hashlib

from pyrogram import Client
from pyrogram.types import Message, InputMediaPhoto, InputMediaVideo, InputMediaDocument, InputMediaAudio
from pyrogram.errors import FloodWait, ChatForwardsRestricted, ChannelPrivate

from src.utils.ui_config_manager import UIConfigManager
from src.utils.config_utils import convert_ui_config_to_dict
from src.utils.channel_resolver import ChannelResolver
from src.utils.history_manager import HistoryManager
from src.modules.downloader import Downloader
from src.modules.uploader import Uploader
from src.utils.logger import get_logger
from src.utils.video_processor import VideoProcessor

# 仅用于内部调试，不再用于UI输出
_logger = get_logger()

@dataclass
class MediaGroupDownload:
    """媒体组下载结果"""
    source_channel: str
    source_id: int
    messages: List[Message]
    download_dir: Path
    downloaded_files: List[Tuple[Path, str]]
    caption: Optional[str] = None

class Forwarder():
    """
    转发模块，负责将消息从源频道转发到目标频道
    """
    
    def __init__(self, client: Client, ui_config_manager: UIConfigManager, channel_resolver: ChannelResolver, history_manager: HistoryManager, downloader: Downloader, uploader: Uploader, app=None):
        """
        初始化转发模块
        
        Args:
            client: Pyrogram客户端实例
            ui_config_manager: UI配置管理器实例
            channel_resolver: 频道解析器实例
            history_manager: 历史记录管理器实例
            downloader: 下载模块实例
            uploader: 上传模块实例
            app: 应用程序实例，用于网络错误时立即检查连接状态
        """
        # 初始化事件发射器
        super().__init__()
        
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
        
        # 创建下载完成的媒体组队列
        self.media_group_queue = asyncio.Queue()
        
        # 生产者-消费者控制
        self.download_running = False
        self.upload_running = False
        self.producer_task = None
        self.consumer_task = None
        
        # 初始化视频处理器
        self.video_processor = VideoProcessor()
        
        # 任务控制
        self.task_context = None
    
    async def forward_messages(self):
        """
        从源频道转发消息到目标频道
        """
        
        _logger.info("开始转发消息")
        
        # 获取配置的源频道和目标频道
        # source_channels = self.forward_config.source_channels
        # target_channels = self.forward_config.target_channels
        
        # 创建临时会话目录
        temp_dir = self.ensure_temp_dir()
        
        # 获取频道对列表
        channel_pairs = self.forward_config.get('forward_channel_pairs', [])
        info_message = f"配置的频道对数量: {len(channel_pairs)}"
        _logger.info(info_message)
        self.emit("info", info_message)
        
        # 转发计数
        forward_count = 0
        total_forward_count = 0
        
        # 处理每个频道对
        for pair in channel_pairs:
            source_channel = pair.source_channel
            target_channels = pair.target_channels
            
            # 检查是否已取消任务
            if self.task_context.cancel_token.is_cancelled:
                status_message = "转发任务已取消"
                _logger.info(status_message)
                self.emit("status", status_message)
                return
            
            # 等待任务暂停恢复
            await self.task_context.wait_if_paused()
            
            if not target_channels:
                warning_message = f"源频道 {source_channel} 没有配置目标频道，跳过"
                _logger.warning(warning_message)
                self.emit("warning", warning_message)
                continue
            
            info_message = f"准备从 {source_channel} 转发到 {len(target_channels)} 个目标频道"
            _logger.info(info_message)
            self.emit("info", info_message)
            
            try:
                # 解析源频道ID
                source_id = await self.channel_resolver.get_channel_id(source_channel)
                source_info_str, (source_title, _) = await self.channel_resolver.format_channel_info(source_id)
                info_message = f"源频道: {source_info_str}"
                _logger.info(info_message)
                self.emit("info", info_message)
                
                # 检查源频道转发权限
                status_message = "检查源频道转发权限..."
                _logger.info(status_message)
                self.emit("status", status_message)
                
                source_can_forward = await self.channel_resolver.check_forward_permission(source_id)
                info_message = f"源频道转发权限: {source_can_forward}"
                _logger.info(info_message)
                self.emit("info", info_message)
                
                # 获取有效的目标频道
                valid_target_channels = []
                for target in target_channels:
                    # 检查是否已取消任务
                    if self.task_context.cancel_token.is_cancelled:
                        status_message = "转发任务已取消"
                        _logger.info(status_message)
                        self.emit("status", status_message)
                        return
                        
                    try:
                        target_id = await self.channel_resolver.get_channel_id(target)
                        target_info_str, (target_title, _) = await self.channel_resolver.format_channel_info(target_id)
                        valid_target_channels.append((target, target_id, target_info_str))
                        info_message = f"目标频道: {target_info_str}"
                        _logger.info(info_message)
                        self.emit("info", info_message)
                    except Exception as e:
                        error_message = f"解析目标频道 {target} 失败: {e}"
                        _logger.error(error_message)
                        self.emit("error", error_message, error_type="CHANNEL_RESOLVE", recoverable=True)
                
                if not valid_target_channels:
                    warning_message = f"源频道 {source_channel} 没有有效的目标频道，跳过"
                    _logger.warning(warning_message)
                    self.emit("warning", warning_message)
                    continue
                
                if source_can_forward:
                    # 源频道允许转发，直接使用转发功能
                    status_message = "源频道允许直接转发，获取媒体组和消息..."
                    _logger.info(status_message)
                    self.emit("status", status_message)
                    
                    # 获取媒体组和消息
                    media_groups = await self._get_media_groups(source_id)
                    
                    # 发送总媒体组数量
                    total_groups = len(media_groups)
                    info_message = f"找到 {total_groups} 个媒体组/消息"
                    _logger.info(info_message)
                    self.emit("info", info_message)
                    
                    # 添加进度事件
                    group_count = 0
                    
                    # 处理每个媒体组
                    for group_id, messages in media_groups.items():
                        # 检查是否已取消任务
                        if self.task_context.cancel_token.is_cancelled:
                            status_message = "转发任务已取消"
                            _logger.info(status_message)
                            self.emit("status", status_message)
                            return
                        
                        # 等待任务暂停恢复
                        await self.task_context.wait_if_paused()
                        
                        # 更新进度
                        group_count += 1
                        progress_percentage = (group_count / total_groups) * 100
                        self.emit("progress", progress_percentage, group_count, total_groups, "direct_forward")
                        
                        # 转发媒体组
                        success = await self._forward_media_group_directly(messages, source_channel, source_id, valid_target_channels)
                        if success:
                            forward_count += 1
                            total_forward_count += 1
                        
                        # 检查是否达到转发限制
                        if self.general_config.limit > 0 and forward_count >= self.general_config.limit:
                            status_message = f"已达到转发限制 {self.general_config.limit}，暂停 {self.general_config.pause_time} 秒"
                            _logger.info(status_message)
                            self.emit("status", status_message)
                            await asyncio.sleep(self.general_config.pause_time)
                            forward_count = 0
                else:
                    # 源频道不允许转发，需要下载后重新上传
                    status_message = "源频道不允许直接转发，将使用下载后重新上传的方式"
                    _logger.info(status_message)
                    self.emit("status", status_message)
                    
                    # 创建针对此频道对的临时目录 - 使用安全的文件名
                    safe_source_channel = self._get_safe_path_name(source_channel)
                    safe_target_channels = [self._get_safe_path_name(ch) for ch in target_channels]
                    channel_temp_dir = temp_dir / f"{safe_source_channel}_to_{'_'.join(safe_target_channels)}"
                    channel_temp_dir.mkdir(exist_ok=True)
                    
                    status_message = "获取媒体组信息..."
                    _logger.info(status_message)
                    self.emit("status", status_message)
                    
                    # 获取媒体组信息
                    media_groups_info = await self._get_media_groups_info(source_id)
                    total_groups = len(media_groups_info)
                    info_message = f"找到 {total_groups} 个媒体组/消息"
                    _logger.info(info_message)
                    self.emit("info", info_message)
                    
                    # 如果没有媒体组，跳过此频道对
                    if not media_groups_info:
                        warning_message = f"源频道 {source_channel} 没有媒体组/消息，跳过"
                        _logger.warning(warning_message)
                        self.emit("warning", warning_message)
                        continue
                    
                    # 启动下载和上传任务
                    try:
                        # 设置下载和上传标志
                        self.download_running = True
                        self.upload_running = True
                        
                        status_message = "开始并行下载和上传媒体组..."
                        _logger.info(status_message)
                        self.emit("status", status_message)
                        
                        # 创建生产者和消费者任务
                        producer_task = asyncio.create_task(
                            self._producer_download_media_groups_parallel(
                                source_channel, source_id, media_groups_info, channel_temp_dir, valid_target_channels
                            )
                        )
                        consumer_task = asyncio.create_task(
                            self._consumer_upload_media_groups(valid_target_channels)
                        )
                        
                        self.producer_task = producer_task
                        self.consumer_task = consumer_task
                        
                        # 等待生产者和消费者任务完成
                        await producer_task
                        status_message = "下载任务完成，等待所有上传完成..."
                        _logger.info(status_message)
                        self.emit("status", status_message)
                        
                        # 发送结束信号
                        await self.media_group_queue.put(None)
                        
                        # 等待消费者任务完成
                        await consumer_task
                        
                        # 重置任务引用
                        self.producer_task = None
                        self.consumer_task = None
                        
                        status_message = "媒体组下载和上传任务完成"
                        _logger.info(status_message)
                        self.emit("status", status_message)
                        
                        # 记录本组转发的消息数
                        total_forward_count += forward_count
                        info_message = f"从 {source_channel} 已转发 {forward_count} 个媒体组/消息"
                        _logger.info(info_message)
                        self.emit("info", info_message)
                        
                    except Exception as e:
                        error_message = f"下载和上传任务失败: {str(e)}"
                        _logger.error(error_message)
                        import traceback
                        error_details = traceback.format_exc()
                        _logger.error(error_details)
                        self.emit("error", error_message, error_type="DOWNLOAD_UPLOAD", recoverable=False, details=error_details)
                        
                        # 取消所有任务
                        if self.producer_task and not self.producer_task.done():
                            self.producer_task.cancel()
                        if self.consumer_task and not self.consumer_task.done():
                            self.consumer_task.cancel()
                        
                        # 等待任务取消
                        try:
                            if self.producer_task:
                                await self.producer_task
                        except asyncio.CancelledError:
                            pass
                        
                        try:
                            if self.consumer_task:
                                await self.consumer_task
                        except asyncio.CancelledError:
                            pass
                        
                        # 重置任务标志
                        self.download_running = False
                        self.upload_running = False
                        
                        # 清空队列
                        while not self.media_group_queue.empty():
                            try:
                                await self.media_group_queue.get()
                                self.media_group_queue.task_done()
                            except Exception:
                                pass
            
            except Exception as e:
                error_message = f"处理频道对 {source_channel} 失败: {str(e)}"
                _logger.error(error_message)
                import traceback
                error_details = traceback.format_exc()
                _logger.error(error_details)
                self.emit("error", error_message, error_type="CHANNEL_PAIR", recoverable=True, details=error_details)
                continue
        
        # 转发完成
        status_message = f"所有转发任务完成，共转发 {total_forward_count} 个媒体组/消息"
        _logger.info(status_message)
        self.emit("status", status_message)
        self.emit("complete", total_forward_count)
        
        # 清理临时文件
        await self.clean_media_dirs(temp_dir)
        
    async def _process_parallel_download_upload(self, 
                                      source_channel: str, 
                                      source_id: int, 
                                      temp_dir: Path, 
                                      target_channels: List[Tuple[str, int, str]]):
        """
        并行处理媒体组下载和上传
        
        Args:
            source_channel: 源频道标识符
            source_id: 源频道ID
            temp_dir: 临时下载目录
            target_channels: 目标频道列表(频道标识符, 频道ID, 频道信息)
        """
        # 使用生产者-消费者模式处理
        self.download_running = True
        self.upload_running = True
        
        # 清空队列
        while not self.media_group_queue.empty():
            try:
                self.media_group_queue.get_nowait()
                self.media_group_queue.task_done()
            except asyncio.QueueEmpty:
                break
        
        # 获取媒体组信息
        media_groups_info = await self._get_media_groups_info(source_id)
        
        if not media_groups_info:
            _logger.warning("没有找到媒体组，跳过")
            return
        
        _logger.info(f"发现 {len(media_groups_info)} 个媒体组")
        
        # 创建生产者和消费者任务
        producer_task = asyncio.create_task(
            self._producer_download_media_groups_parallel(source_channel, source_id, media_groups_info, temp_dir, target_channels)
        )
        
        consumer_task = asyncio.create_task(
            self._consumer_upload_media_groups(target_channels)
        )
        
        try:
            self.producer_task = producer_task
            self.consumer_task = consumer_task
            
            # 等待生产者完成
            await producer_task
            _logger.info("生产者(下载)任务完成，等待消费者(上传)任务完成...")
            
            # 放入结束标记
            await self.media_group_queue.put(None)
            
            # 等待消费者完成
            await consumer_task
            
            _logger.info("消费者(上传)任务完成")
            
        finally:
            # 重置状态
            self.download_running = False
            self.upload_running = False
            self.producer_task = None
            self.consumer_task = None

    async def _get_media_groups_info(self, source_id: int) -> List[Tuple[str, List[int]]]:
        """
        获取源频道的媒体组基本信息（不下载内容）
        
        Args:
            source_id: 源频道ID
            
        Returns:
            List[Tuple[str, List[int]]]: 媒体组ID与消息ID列表的映射
        """
        media_groups_info = []
        media_groups: Dict[str, List[int]] = {}
        
        # 设置消息范围
        start_id = self.forward_config.start_id
        end_id = self.forward_config.end_id
        
        # 获取消息基本信息
        async for message in self._iter_messages(source_id, start_id, end_id):
            # 筛选媒体类型
            if not self._is_media_allowed(message):
                continue
            
            # 获取媒体组ID
            group_id = str(message.media_group_id) if message.media_group_id else f"single_{message.id}"
            
            # 添加到媒体组信息
            if group_id not in media_groups:
                media_groups[group_id] = []
            
            media_groups[group_id].append(message.id)
        
        # 转换为列表格式，便于顺序处理
        for group_id, message_ids in media_groups.items():
            # 按消息ID排序
            message_ids.sort()
            media_groups_info.append((group_id, message_ids))
        
        # 按第一个消息ID排序，确保从旧到新处理
        media_groups_info.sort(key=lambda x: x[1][0] if x[1] else 0)
        
        return media_groups_info

    async def _producer_download_media_groups_parallel(self, 
                                                 source_channel: str, 
                                                 source_id: int, 
                                                 media_groups_info: List[Tuple[str, List[int]]], 
                                                 temp_dir: Path,
                                                 target_channels: List[Tuple[str, int, str]]):
        """
        生产者：并行下载媒体组
        
        Args:
            source_channel: 源频道标识符
            source_id: 源频道ID
            media_groups_info: 媒体组信息列表[(group_id, [message_ids])]
            temp_dir: 临时下载目录
            target_channels: 目标频道列表，用于检查是否已转发
        """
        try:
            forward_count = 0
            total_groups = len(media_groups_info)
            processed_groups = 0
            
            status_message = f"开始并行下载 {total_groups} 个媒体组"
            _logger.info(status_message)
            self.emit("status", status_message)
            
            for group_id, message_ids in media_groups_info:
                try:
                    # 检查是否已取消任务
                    if self.task_context and self.task_context.cancel_token.is_cancelled:
                        status_message = "媒体组下载任务已取消"
                        _logger.info(status_message)
                        self.emit("status", status_message)
                        return
                    
                    # 等待暂停恢复
                    if self.task_context:
                        await self.task_context.wait_if_paused()
                    
                    # 更新进度
                    processed_groups += 1
                    progress_percentage = (processed_groups / total_groups) * 100
                    self.emit("progress", progress_percentage, processed_groups, total_groups, "download")
                    
                    # 检查是否已全部转发
                    all_forwarded = True
                    forwarded_targets = []
                    not_forwarded_targets = []
                    
                    for target_channel, target_id, target_info in target_channels:
                        target_all_forwarded = True
                        for message_id in message_ids:
                            if not self.history_manager.is_message_forwarded(source_channel, message_id, target_channel):
                                target_all_forwarded = False
                                all_forwarded = False
                                break
                        
                        if target_all_forwarded:
                            forwarded_targets.append(target_info)
                        else:
                            not_forwarded_targets.append(target_info)
                    
                    if all_forwarded:
                        info_message = f"媒体组 {group_id} (消息IDs: {message_ids}) 已转发到所有目标频道，跳过"
                        _logger.info(info_message)
                        self.emit("info", info_message)
                        continue
                    elif forwarded_targets:
                        info_message = f"媒体组 {group_id} (消息IDs: {message_ids}) 已部分转发: 已转发到 {forwarded_targets}, 未转发到 {not_forwarded_targets}"
                        _logger.info(info_message)
                        self.emit("info", info_message)
                    
                    # 检查是否达到限制
                    if self.general_config.limit > 0 and forward_count >= self.general_config.limit:
                        status_message = f"已达到转发限制 {self.general_config.limit}，暂停 {self.general_config.pause_time} 秒"
                        _logger.info(status_message)
                        self.emit("status", status_message)
                        await asyncio.sleep(self.general_config.pause_time)
                        forward_count = 0
                    
                    # 为每个媒体组创建安全的目录名
                    # 将媒体组ID转为字符串，并替换可能的非法路径字符
                    safe_group_id = str(group_id).replace('/', '_').replace('\\', '_').replace(':', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_')
                    
                    # 为每个媒体组创建单独的下载目录
                    group_dir = temp_dir / safe_group_id
                    group_dir.mkdir(exist_ok=True)
                    
                    # 获取完整消息对象
                    messages = []
                    status_message = f"正在获取媒体组 {group_id} 的 {len(message_ids)} 条消息"
                    _logger.info(status_message)
                    self.emit("status", status_message)
                    
                    for message_id in message_ids:
                        try:
                            # 检查是否已取消任务
                            if self.task_context and self.task_context.cancel_token.is_cancelled:
                                status_message = "媒体组下载任务已取消"
                                _logger.info(status_message)
                                self.emit("status", status_message)
                                return
                            
                            message = await self.client.get_messages(source_id, message_id)
                            if message:
                                messages.append(message)
                                self.emit("debug", f"获取消息 {message_id} 成功")
                        except Exception as e:
                            error_message = f"获取消息 {message_id} 失败: {e}"
                            _logger.error(error_message)
                            self.emit("error", error_message, error_type="GET_MESSAGE", recoverable=True)
                    
                    if not messages:
                        warning_message = f"媒体组 {group_id} 没有获取到有效消息，跳过"
                        _logger.warning(warning_message)
                        self.emit("warning", warning_message)
                        continue
                    
                    # 下载媒体文件
                    status_message = f"正在下载媒体组 {group_id} 的 {len(messages)} 条媒体消息"
                    _logger.info(status_message)
                    self.emit("status", status_message)
                    
                    downloaded_files = await self._download_messages(messages, group_dir, source_id)
                    if not downloaded_files:
                        warning_message = f"媒体组 {group_id} 没有媒体文件可下载，跳过"
                        _logger.warning(warning_message)
                        self.emit("warning", warning_message)
                        continue
                    
                    # 获取消息文本
                    caption = None
                    for message in messages:
                        if message.caption or message.text:
                            caption = message.caption or message.text
                            break
                    
                    # 移除原始标题
                    if self.forward_config.remove_captions:
                        caption = None
                    
                    # 创建媒体组下载结果对象
                    media_group_download = MediaGroupDownload(
                        source_channel=source_channel,
                        source_id=source_id,
                        messages=messages,
                        download_dir=group_dir,
                        downloaded_files=downloaded_files,
                        caption=caption
                    )
                    
                    # 将下载完成的媒体组放入队列
                    success_message = f"媒体组 {group_id} 下载完成，放入上传队列: 消息IDs={[m.id for m in messages]}"
                    _logger.info(success_message)
                    self.emit("info", success_message)
                    self.emit("media_group_downloaded", group_id, len(messages), len(downloaded_files))
                    
                    await self.media_group_queue.put(media_group_download)
                    
                    forward_count += 1
                    
                    # 添加适当的延迟，避免API限制
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    error_message = f"处理媒体组 {group_id} 失败: {str(e)}"
                    _logger.error(error_message)
                    import traceback
                    error_details = traceback.format_exc()
                    _logger.error(error_details)
                    self.emit("error", error_message, error_type="DOWNLOAD_MEDIA_GROUP", recoverable=True, details=error_details)
                    continue
                    
        except Exception as e:
            error_message = f"生产者并行下载任务异常: {str(e)}"
            _logger.error(error_message)
            import traceback
            error_details = traceback.format_exc()
            _logger.error(error_details)
            self.emit("error", error_message, error_type="PRODUCER_DOWNLOAD", recoverable=False, details=error_details)
        finally:
            self.download_running = False
            status_message = "生产者(下载)任务结束"
            _logger.info(status_message)
            self.emit("status", status_message)
    
    async def _get_media_groups(self, source_id: int) -> Dict[str, List[Message]]:
        """
        获取源频道的媒体组消息
        
        Args:
            source_id: 源频道ID
            
        Returns:
            Dict[str, List[Message]]: 媒体组ID与消息列表的映射
        """
        media_groups: Dict[str, List[Message]] = {}
        
        # 设置消息范围
        start_id = self.forward_config.start_id
        end_id = self.forward_config.end_id
        
        # 获取消息
        async for message in self._iter_messages(source_id, start_id, end_id):
            # 筛选媒体类型
            if not self._is_media_allowed(message):
                continue
            
            # 获取媒体组ID
            group_id = str(message.media_group_id) if message.media_group_id else f"single_{message.id}"
            
            # 添加到媒体组
            if group_id not in media_groups:
                media_groups[group_id] = []
            
            media_groups[group_id].append(message)
        
        # 按消息ID排序每个媒体组内的消息
        for group_id in media_groups:
            media_groups[group_id].sort(key=lambda x: x.id)
        
        return media_groups
    
    async def _iter_messages(self, chat_id: Union[str, int], start_id: int = 0, end_id: int = 0):
        """
        迭代获取频道消息，按从旧到新的顺序返回
        
        Args:
            chat_id: 频道ID
            start_id: 起始消息ID
            end_id: 结束消息ID
        
        Yields:
            Message: 消息对象，按照从旧到新的顺序
        """
        # 使用channel_resolver获取有效的消息ID范围
        actual_start_id, actual_end_id = await self.channel_resolver.get_message_range(chat_id, start_id, end_id)
        
        # 如果无法获取有效范围，则直接返回
        if actual_start_id is None or actual_end_id is None:
            _logger.error(f"无法获取有效的消息ID范围: chat_id={chat_id}, start_id={start_id}, end_id={end_id}")
            return
        
        # 计算需要获取的消息数量
        total_messages = actual_end_id - actual_start_id + 1
        _logger.info(f"开始获取消息: chat_id={chat_id}, 开始id={actual_start_id}, 结束id={actual_end_id}，共{total_messages}条消息")
        
        try:
            # 收集指定范围内的所有消息
            all_messages = []
            
            # 优化策略：使用更高效的方式获取消息
            # 1. 从较大的批次开始，逐步减小批次大小
            # 2. 跟踪已尝试获取的消息ID，避免重复尝试
            # 3. 设置最大尝试次数，防止无限循环
            
            # 创建要获取的消息ID列表，按从旧到新的顺序排序
            message_ids_to_fetch = list(range(actual_start_id, actual_end_id + 1))
            fetched_messages_map = {}  # 用于存储已获取的消息，键为消息ID
            
            # 每次批量获取的最大消息数量
            max_batch_size = 100
            
            # 获取消息的最大尝试次数，避免无限循环
            max_attempts = 5
            attempt_count = 0
            
            while message_ids_to_fetch and attempt_count < max_attempts:
                attempt_count += 1
                
                # 根据剩余消息数量确定当前批次大小
                batch_size = min(max_batch_size, len(message_ids_to_fetch))
                
                # 计算当前批次的offset_id，以获取小于此ID的消息
                # 由于Telegram API是获取"小于offset_id"的消息，需要加1
                current_offset_id = max(message_ids_to_fetch) + 1
                
                _logger.info(f"尝试获取消息批次 (第{attempt_count}次): chat_id={chat_id}, offset_id={current_offset_id}, 剩余未获取消息数={len(message_ids_to_fetch)}")
                
                # 记录此批次成功获取的消息数
                batch_success_count = 0
                
                # 获取一批消息
                async for message in self.client.get_chat_history(
                    chat_id=chat_id,
                    limit=batch_size,
                    offset_id=current_offset_id
                ):
                    # 检查消息ID是否在我们需要的范围内
                    if message.id in message_ids_to_fetch:
                        fetched_messages_map[message.id] = message
                        message_ids_to_fetch.remove(message.id)
                        batch_success_count += 1
                    
                    # 如果消息ID小于我们要获取的最小ID，可以停止这一批次的获取
                    if message.id < min(message_ids_to_fetch, default=actual_start_id):
                        _logger.debug(f"消息ID {message.id} 小于当前需要获取的最小ID {min(message_ids_to_fetch, default=actual_start_id)}，停止当前批次获取")
                        break
                
                _logger.info(f"已获取 {batch_success_count} 条消息，剩余 {len(message_ids_to_fetch)} 条消息待获取")
                
                # 如果此批次没有获取到任何消息，说明可能有些消息不存在或已被删除
                if batch_success_count == 0:
                    # 检查是否需要缩小获取范围，尝试一条一条地获取
                    if batch_size > 1:
                        _logger.info(f"未获取到任何消息，尝试减小批次大小")
                        max_batch_size = max(1, max_batch_size // 2)
                    else:
                        # 如果已经是最小批次大小，且仍未获取到消息，记录并移除前一部分消息ID
                        # 这些可能是不存在或已删除的消息
                        if message_ids_to_fetch:
                            ids_to_skip = message_ids_to_fetch[:min(10, len(message_ids_to_fetch))]
                            _logger.warning(f"无法获取以下消息ID，可能不存在或已被删除：{ids_to_skip}")
                            for id_to_skip in ids_to_skip:
                                message_ids_to_fetch.remove(id_to_skip)
                
                # 避免频繁请求，休眠一小段时间
                await asyncio.sleep(0.5)
            
            # 检查是否还有未获取的消息
            if message_ids_to_fetch:
                _logger.warning(f"以下消息ID无法获取，将被跳过：{message_ids_to_fetch}")
            
            # 将获取到的消息按ID升序排序（从旧到新）
            all_messages = [fetched_messages_map[msg_id] for msg_id in sorted(fetched_messages_map.keys())]
            _logger.info(f"消息获取完成，共获取{len(all_messages)}/{total_messages}条消息，已按ID升序排序（从旧到新）")
            
            # 逐个返回排序后的消息
            for message in all_messages:
                yield message
        
        except FloodWait as e:
            _logger.warning(f"获取消息时遇到限制，等待 {e.x} 秒")
            await asyncio.sleep(e.x)
        except Exception as e:
            _logger.error(f"获取消息失败: {e}")
            _logger.exception("详细错误信息：")
    
    def _is_media_allowed(self, message: Message) -> bool:
        """
        检查消息媒体类型是否在允许列表中
        
        Args:
            message: 消息对象
            
        Returns:
            bool: 是否允许
        """
        media_types = self.forward_config.media_types
        
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
    
    async def _forward_media_group_directly(self, messages: List[Message], source_channel: str, source_id: int, 
                                          target_channels: List[Tuple[str, int, str]]) -> bool:
        """
        直接转发媒体组到目标频道
        
        Args:
            messages: 消息列表
            source_channel: 源频道标识符
            source_id: 源频道ID
            target_channels: 目标频道列表(频道标识符, 频道ID, 频道信息)
            
        Returns:
            bool: 是否成功转发到至少一个目标频道
        """
        # 检查是否是单条消息
        is_single = len(messages) == 1
        
        # 获取是否隐藏作者配置
        hide_author = self.forward_config.hide_author
        
        # 消息ID列表（用于日志和事件）
        message_ids = [msg.id for msg in messages]
        
        # 媒体组ID（用于事件通知）
        group_id = f"single_{message_ids[0]}" if is_single else f"group_{message_ids[0]}"
        
        # 转发成功计数
        success_count = 0
        
        for target_channel, target_id, target_info in target_channels:
            # 检查是否已取消任务
            if self.task_context and self.task_context.cancel_token.is_cancelled:
                status_message = "转发任务已取消"
                _logger.info(status_message)
                self.emit("status", status_message)
                return success_count > 0
            
            # 等待暂停恢复
            if self.task_context:
                await self.task_context.wait_if_paused()
                
            # 检查是否已转发到此频道
            all_forwarded = True
            for message in messages:
                if not self.history_manager.is_message_forwarded(source_channel, message.id, target_channel):
                    all_forwarded = False
                    break
            
            if all_forwarded:
                debug_message = f"消息已转发到频道 {target_info}，跳过"
                _logger.debug(debug_message)
                self.emit("info", debug_message)
                continue
            
            try:
                info_message = f"转发消息到频道 {target_info}"
                _logger.info(info_message)
                self.emit("status", info_message)
                
                if is_single:
                    # 单条消息转发
                    message = messages[0]
                    
                    try:
                        if hide_author:
                            # 使用copy_message隐藏作者
                            debug_message = f"使用copy_message方法隐藏作者转发消息 {message.id}"
                            _logger.debug(debug_message)
                            self.emit("debug", debug_message)
                            
                            forwarded = await self.client.copy_message(
                                chat_id=target_id,
                                from_chat_id=source_id,
                                message_id=message.id
                            )
                        else:
                            # 使用forward_messages保留作者信息
                            debug_message = f"使用forward_messages方法保留作者转发消息 {message.id}"
                            _logger.debug(debug_message)
                            self.emit("debug", debug_message)
                            
                            forwarded = await self.client.forward_messages(
                                chat_id=target_id,
                                from_chat_id=source_id,
                                message_ids=message.id,
                                disable_notification=True
                            )
                        
                        # 转发成功后才记录历史
                        self.history_manager.add_forward_record(
                            source_channel,
                            message.id,
                            target_channel,
                            source_id
                        )
                        
                        success_message = f"消息 {message.id} 转发到 {target_info} 成功"
                        _logger.info(success_message)
                        self.emit("info", success_message)
                        self.emit("message_forwarded", message.id, target_info)
                        success_count += 1
                    except Exception as e:
                        error_message = f"转发单条消息 {message.id} 到 {target_info} 失败: {e}，跳过"
                        _logger.error(error_message)
                        self.emit("error", error_message, error_type="FORWARD_SINGLE", recoverable=True)
                        continue
                else:
                    # 媒体组转发
                    try:
                        if hide_author:
                            # 使用copy_media_group方法一次性转发整个媒体组
                            debug_message = f"使用copy_media_group方法隐藏作者转发媒体组消息"
                            _logger.debug(debug_message)
                            self.emit("debug", debug_message)
                            
                            # 只需要第一条消息的ID，因为copy_media_group会自动获取同一组的所有消息
                            first_message_id = message_ids[0]
                            forwarded = await self.client.copy_media_group(
                                chat_id=target_id,
                                from_chat_id=source_id,
                                message_id=first_message_id
                            )
                        else:
                            # 使用forward_messages批量转发
                            debug_message = f"使用forward_messages方法保留作者批量转发媒体组消息"
                            _logger.debug(debug_message)
                            self.emit("debug", debug_message)
                            
                            forwarded = await self.client.forward_messages(
                                chat_id=target_id,
                                from_chat_id=source_id,
                                message_ids=message_ids,
                                disable_notification=True
                            )
                        
                        # 转发成功后才记录历史
                        for message in messages:
                            self.history_manager.add_forward_record(
                                source_channel,
                                message.id,
                                target_channel,
                                source_id
                            )
                        
                        success_message = f"媒体组 {message_ids} 转发到 {target_info} 成功"
                        _logger.info(success_message)
                        self.emit("info", success_message)
                        self.emit("media_group_forwarded", message_ids, target_info, len(messages))
                        success_count += 1
                    except Exception as e:
                        error_message = f"转发媒体组 {message_ids} 到 {target_info} 失败: {e}，跳过"
                        _logger.error(error_message)
                        self.emit("error", error_message, error_type="FORWARD_MEDIA_GROUP", recoverable=True)
                        continue
                
                # 转发延迟
                await asyncio.sleep(1)
            
            except FloodWait as e:
                warning_message = f"转发消息时遇到限制，等待 {e.x} 秒"
                _logger.warning(warning_message)
                self.emit("warning", warning_message)
                
                try:
                    await asyncio.sleep(e.x)
                    # 重试此频道
                    retry_result = await self._forward_media_group_directly(messages, source_channel, source_id, [(target_channel, target_id, target_info)])
                    if retry_result:
                        success_count += 1
                except Exception as retry_e:
                    error_message = f"重试转发到频道 {target_info} 失败: {retry_e}"
                    _logger.error(error_message)
                    self.emit("error", error_message, error_type="FORWARD_RETRY", recoverable=True)
            
            except Exception as e:
                error_message = f"转发消息到频道 {target_info} 失败: {e}"
                _logger.error(error_message)
                import traceback
                error_details = traceback.format_exc()
                _logger.error(error_details)
                self.emit("error", error_message, error_type="FORWARD_GENERAL", recoverable=True, details=error_details)
                continue
        
        # 返回是否至少有一个频道转发成功
        return success_count > 0
    
    async def _consumer_upload_media_groups(self, target_channels: List[Tuple[str, int, str]]):
        """
        消费者：上传媒体组到目标频道
        
        Args:
            target_channels: 目标频道列表(频道标识符, 频道ID, 频道信息)
        """
        try:
            # 记录上传计数
            uploaded_count = 0
            failed_count = 0
            
            status_message = "开始上传媒体组到目标频道"
            _logger.info(status_message)
            self.emit("status", status_message)
            
            while True:
                # 检查是否已取消任务
                if self.task_context and self.task_context.cancel_token.is_cancelled:
                    status_message = "媒体组上传任务已取消"
                    _logger.info(status_message)
                    self.emit("status", status_message)
                    break
                
                # 等待暂停恢复
                if self.task_context:
                    await self.task_context.wait_if_paused()
                
                # 从队列获取下一个媒体组
                try:
                    media_group_download = await asyncio.wait_for(
                        self.media_group_queue.get(), 
                        timeout=5.0
                    )
                except asyncio.TimeoutError:
                    # 每5秒检查一次是否应该退出
                    if not self.download_running and self.media_group_queue.empty():
                        status_message = "下载任务已完成且队列为空，上传任务准备退出"
                        _logger.info(status_message)
                        self.emit("status", status_message)
                        break
                    continue
                
                # 检查是否结束信号
                if media_group_download is None:
                    status_message = "收到结束信号，消费者准备退出"
                    _logger.info(status_message)
                    self.emit("status", status_message)
                    break
                
                try:
                    # 记录媒体组的目录，以便上传后删除
                    media_group_dir = media_group_download.download_dir
                    message_ids = [m.id for m in media_group_download.messages]
                    source_channel = media_group_download.source_channel
                    
                    # 记录媒体组信息
                    group_id = "单条消息" if len(message_ids) == 1 else f"媒体组(共{len(message_ids)}条)"
                    status_message = f"开始处理{group_id}: 消息IDs={message_ids}, 来源={source_channel}"
                    _logger.info(status_message)
                    self.emit("status", status_message)
                    
                    # 提前检查哪些频道已经转发过
                    forwarded_targets = []
                    not_forwarded_targets = []
                    
                    for target_channel, _, target_info in target_channels:
                        all_forwarded = True
                        for message in media_group_download.messages:
                            if not self.history_manager.is_message_forwarded(media_group_download.source_channel, message.id, target_channel):
                                all_forwarded = False
                                break
                        
                        if all_forwarded:
                            forwarded_targets.append(target_info)
                        else:
                            not_forwarded_targets.append(target_info)
                    
                    if forwarded_targets:
                        info_message = f"{group_id} {message_ids} 已转发到: {forwarded_targets}"
                        _logger.info(info_message)
                        self.emit("info", info_message)
                    
                    if not not_forwarded_targets:
                        info_message = f"{group_id} {message_ids} 已转发到所有目标频道，跳过上传"
                        _logger.info(info_message)
                        self.emit("info", info_message)
                        # 清理已全部转发的媒体组目录
                        if media_group_dir.exists():
                            try:
                                shutil.rmtree(media_group_dir)
                                debug_message = f"删除已全部转发的媒体组目录: {media_group_dir}"
                                _logger.debug(debug_message)
                                self.emit("debug", debug_message)
                            except Exception as e:
                                error_message = f"删除媒体组目录失败: {str(e)}"
                                _logger.error(error_message)
                                self.emit("error", error_message, error_type="DELETE_DIR", recoverable=True)
                        self.media_group_queue.task_done()
                        continue
                    
                    # 为视频文件生成缩略图
                    thumbnails = {}
                    status_message = f"为媒体组 {group_id} 生成缩略图"
                    _logger.info(status_message)
                    self.emit("status", status_message)
                    
                    for file_path, media_type in media_group_download.downloaded_files:
                        if media_type == "video":
                            try:
                                thumbnail_path = self.video_processor.extract_thumbnail(str(file_path))
                                if thumbnail_path:
                                    thumbnails[str(file_path)] = thumbnail_path
                                    debug_message = f"为视频 {file_path.name} 生成缩略图成功"
                                    _logger.debug(debug_message)
                                    self.emit("debug", debug_message)
                            except Exception as e:
                                warning_message = f"为视频 {file_path.name} 生成缩略图失败: {e}"
                                _logger.warning(warning_message)
                                self.emit("warning", warning_message)
                    
                    # 准备媒体组上传
                    media_group = []
                    file_caption = media_group_download.caption
                    
                    for file_path, media_type in media_group_download.downloaded_files:
                        file_path_str = str(file_path)
                        
                        # 只为第一个文件添加标题
                        if media_group and file_caption:
                            file_caption = None
                        
                        # 根据媒体类型创建不同的InputMedia对象
                        if media_type == "photo":
                            media_group.append(InputMediaPhoto(file_path_str, caption=file_caption))
                        elif media_type == "video":
                            # 获取缩略图路径
                            thumb = None
                            if thumbnails:
                                thumb = thumbnails.get(file_path_str)
                            media_group.append(InputMediaVideo(
                                file_path_str, 
                                caption=file_caption, 
                                supports_streaming=True,
                                thumb=thumb
                            ))
                        elif media_type == "document":
                            media_group.append(InputMediaDocument(file_path_str, caption=file_caption))
                        elif media_type == "audio":
                            media_group.append(InputMediaAudio(file_path_str, caption=file_caption))
                    
                    if not media_group:
                        warning_message = "没有有效的媒体文件可上传，跳过这个媒体组"
                        _logger.warning(warning_message)
                        self.emit("warning", warning_message)
                        # 清理空目录
                        if media_group_dir.exists():
                            try:
                                shutil.rmtree(media_group_dir)
                                debug_message = f"删除空媒体组目录: {media_group_dir}"
                                _logger.debug(debug_message)
                                self.emit("debug", debug_message)
                            except Exception as e:
                                error_message = f"删除空媒体组目录失败: {str(e)}"
                                _logger.error(error_message)
                                self.emit("error", error_message, error_type="DELETE_EMPTY_DIR", recoverable=True)
                        self.media_group_queue.task_done()
                        continue
                    
                    # 标记是否所有目标频道都已上传成功
                    all_targets_uploaded = True
                    remaining_targets = not_forwarded_targets.copy()
                    uploaded_targets = []
                        
                    # 依次上传到需要转发的目标频道
                    first_success_message = None
                    
                    # 计算总目标频道数量，用于进度计算
                    total_targets = len(not_forwarded_targets)
                    current_target = 0
                    
                    for target_channel, target_id, target_info in target_channels:
                        # 检查是否已取消任务
                        if self.task_context and self.task_context.cancel_token.is_cancelled:
                            status_message = "媒体组上传任务已取消"
                            _logger.info(status_message)
                            self.emit("status", status_message)
                            break
                        
                        # 等待暂停恢复
                        if self.task_context:
                            await self.task_context.wait_if_paused()
                        
                        # 检查是否已转发到此频道
                        all_forwarded = True
                        for message in media_group_download.messages:
                            if not self.history_manager.is_message_forwarded(media_group_download.source_channel, message.id, target_channel):
                                all_forwarded = False
                                break
                        
                        if all_forwarded:
                            debug_message = f"{group_id} {message_ids} 已转发到频道 {target_info}，跳过"
                            _logger.debug(debug_message)
                            self.emit("debug", debug_message)
                            continue
                        
                        # 更新当前目标进度
                        current_target += 1
                        progress_percentage = (current_target / total_targets) * 100
                        self.emit("progress", progress_percentage, current_target, total_targets, "upload")
                        
                        try:
                            status_message = f"上传{group_id} {message_ids} 到频道 {target_info}"
                            _logger.info(status_message)
                            self.emit("status", status_message)
                            
                            if len(media_group) == 1:
                                # 单个媒体
                                try:
                                    media_item = media_group[0]
                                    if isinstance(media_item, InputMediaPhoto):
                                        self.emit("debug", f"发送图片到 {target_info}")
                                        sent_message = await self.client.send_photo(
                                            chat_id=target_id,
                                            photo=media_item.media,
                                            caption=media_item.caption
                                        )
                                    elif isinstance(media_item, InputMediaVideo):
                                        # 使用缩略图
                                        thumb = None
                                        if thumbnails:
                                            thumb = thumbnails.get(media_item.media)
                                        self.emit("debug", f"发送视频到 {target_info}")
                                        sent_message = await self.client.send_video(
                                            chat_id=target_id,
                                            video=media_item.media,
                                            caption=media_item.caption,
                                            supports_streaming=True,
                                            thumb=thumb
                                        )
                                    elif isinstance(media_item, InputMediaDocument):
                                        self.emit("debug", f"发送文档到 {target_info}")
                                        sent_message = await self.client.send_document(
                                            chat_id=target_id,
                                            document=media_item.media,
                                            caption=media_item.caption
                                        )
                                    elif isinstance(media_item, InputMediaAudio):
                                        self.emit("debug", f"发送音频到 {target_info}")
                                        sent_message = await self.client.send_audio(
                                            chat_id=target_id,
                                            audio=media_item.media,
                                            caption=media_item.caption
                                        )
                                    else:
                                        warning_message = f"未知媒体类型: {type(media_item)}"
                                        _logger.warning(warning_message)
                                        self.emit("warning", warning_message)
                                        continue
                                    
                                    # 保存第一次成功的消息，用于后续复制
                                    if first_success_message is None:
                                        first_success_message = sent_message
                                except Exception as e:
                                    error_message = f"发送单个媒体失败: {str(e)}"
                                    _logger.error(error_message)
                                    self.emit("error", error_message, error_type="SEND_SINGLE_MEDIA", recoverable=True)
                                    all_targets_uploaded = False
                                    continue
                            else:
                                # 媒体组
                                try:
                                    if first_success_message is not None:
                                        # 如果已有成功消息，使用复制转发
                                        self.emit("debug", f"使用复制方式发送媒体组到 {target_info}")
                                        sent_messages = await self.client.copy_media_group(
                                            chat_id=target_id,
                                            from_chat_id=first_success_message.chat.id,
                                            message_id=first_success_message.id
                                        )
                                    else:
                                        # 首次发送媒体组
                                        self.emit("debug", f"首次发送媒体组到 {target_info}")
                                        sent_messages = await self.client.send_media_group(
                                            chat_id=target_id,
                                            media=media_group
                                        )
                                        
                                        # 保存第一次成功的消息，用于后续复制
                                        if sent_messages and first_success_message is None:
                                            first_success_message = sent_messages[0]
                                except Exception as e:
                                    error_message = f"发送媒体组失败: {str(e)}"
                                    _logger.error(error_message)
                                    self.emit("error", error_message, error_type="SEND_MEDIA_GROUP", recoverable=True)
                                    all_targets_uploaded = False
                                    continue
                            
                            # 记录转发历史
                            for message in media_group_download.messages:
                                self.history_manager.add_forward_record(
                                    media_group_download.source_channel,
                                    message.id,
                                    target_channel,
                                    media_group_download.source_id
                                )
                            
                            success_message = f"{group_id} {message_ids} 上传到 {target_info} 成功"
                            _logger.info(success_message)
                            self.emit("info", success_message)
                            
                            if target_info in remaining_targets:
                                remaining_targets.remove(target_info)
                                uploaded_targets.append(target_info)
                            
                            # 上传成功计数
                            uploaded_count += 1
                            
                            # 上传延迟
                            await asyncio.sleep(1)
                        
                        except FloodWait as e:
                            warning_message = f"上传媒体时遇到限制，等待 {e.x} 秒"
                            _logger.warning(warning_message)
                            self.emit("warning", warning_message)
                            
                            try:
                                await asyncio.sleep(e.x)
                                # 继续尝试上传
                                status_message = f"重试上传{group_id}到 {target_info}"
                                _logger.info(status_message)
                                self.emit("status", status_message)
                                
                                success = await self._upload_media_group_to_channel(
                                    media_group, 
                                    media_group_download, 
                                    target_channel, 
                                    target_id, 
                                    target_info,
                                    thumbnails
                                )
                                if not success:
                                    all_targets_uploaded = False
                                    failed_count += 1
                                else:
                                    uploaded_count += 1
                                    if target_info in remaining_targets:
                                        remaining_targets.remove(target_info)
                                        uploaded_targets.append(target_info)
                            except Exception as retry_e:
                                error_message = f"重试上传到 {target_info} 失败: {retry_e}"
                                _logger.error(error_message)
                                self.emit("error", error_message, error_type="RETRY_UPLOAD", recoverable=True)
                                all_targets_uploaded = False
                                failed_count += 1
                        
                        except Exception as e:
                            error_message = f"上传媒体到频道 {target_info} 失败: {str(e)}"
                            _logger.error(error_message)
                            import traceback
                            error_details = traceback.format_exc()
                            _logger.error(error_details)
                            self.emit("error", error_message, error_type="UPLOAD_MEDIA", recoverable=True, details=error_details)
                            all_targets_uploaded = False
                            failed_count += 1
                            continue
                    
                    # 媒体组上传完成后（无论成功失败），都清理缩略图
                    debug_message = f"{group_id} {message_ids} 已处理完所有目标频道，清理缩略图"
                    _logger.debug(debug_message)
                    self.emit("debug", debug_message)
                    
                    for thumbnail_path in thumbnails.values():
                        self.video_processor.delete_thumbnail(thumbnail_path)
                    
                    # 媒体组上传完成后，清理媒体组的本地文件
                    if all_targets_uploaded:
                        success_message = f"{group_id} {message_ids} 已成功上传到所有目标频道，清理本地文件: {media_group_dir}"
                        _logger.info(success_message)
                        self.emit("info", success_message)
                        
                        try:
                            # 删除媒体组目录及其所有文件
                            if media_group_dir.exists():
                                shutil.rmtree(media_group_dir)
                                debug_message = f"已删除媒体组目录: {media_group_dir}"
                                _logger.debug(debug_message)
                                self.emit("debug", debug_message)
                        except Exception as e:
                            error_message = f"删除媒体组目录失败: {str(e)}"
                            _logger.error(error_message)
                            self.emit("error", error_message, error_type="DELETE_DIR", recoverable=True)
                    else:
                        warning_message = f"{group_id} {message_ids} 未能成功上传到所有目标频道，仍有 {remaining_targets} 未转发完成，保留本地文件: {media_group_dir}"
                        _logger.warning(warning_message)
                        self.emit("warning", warning_message)
                    
                    # 发送上传完成事件
                    self.emit("media_group_uploaded", group_id, message_ids, uploaded_targets, remaining_targets)
                
                except Exception as e:
                    error_message = f"处理媒体组上传失败: {str(e)}"
                    _logger.error(error_message)
                    import traceback
                    error_details = traceback.format_exc()
                    _logger.error(error_details)
                    self.emit("error", error_message, error_type="PROCESS_UPLOAD", recoverable=False, details=error_details)
                finally:
                    # 标记此项为处理完成
                    self.media_group_queue.task_done()
        
        except asyncio.CancelledError:
            warning_message = "消费者任务被取消"
            _logger.warning(warning_message)
            self.emit("warning", warning_message)
        except Exception as e:
            error_message = f"消费者任务异常: {str(e)}"
            _logger.error(error_message)
            import traceback
            error_details = traceback.format_exc()
            _logger.error(error_details)
            self.emit("error", error_message, error_type="CONSUMER_UPLOAD", recoverable=False, details=error_details)
        finally:
            self.upload_running = False
            status_message = f"消费者(上传)任务结束，共上传 {uploaded_count} 个媒体组，失败 {failed_count} 个"
            _logger.info(status_message)
            self.emit("status", status_message)
    
    async def _upload_media_group_to_channel(self, media_group, media_group_download, target_channel, target_id, target_info, thumbnails=None):
        """
        上传媒体组到指定频道，处理重试逻辑
        
        Args:
            media_group: 要上传的媒体组
            media_group_download: 媒体组下载结果
            target_channel: 目标频道标识符
            target_id: 目标频道ID
            target_info: 目标频道信息
            thumbnails: 缩略图字典，键为文件路径，值为缩略图路径
            
        Returns:
            bool: 上传是否成功
        """
        retry_count = 0
        max_retries = self.general_config.max_retries
        
        message_ids = [m.id for m in media_group_download.messages]
        group_id = "单条消息" if len(message_ids) == 1 else f"媒体组(共{len(message_ids)}条)"
        
        while retry_count < max_retries:
            # 检查是否已取消任务
            if self.task_context and self.task_context.cancel_token.is_cancelled:
                status_message = "上传任务已取消"
                _logger.info(status_message)
                self.emit("status", status_message)
                return False
            
            # 等待暂停恢复
            if self.task_context:
                await self.task_context.wait_if_paused()
                
            try:
                if len(media_group) == 1:
                    # 单个媒体
                    media_item = media_group[0]
                    if isinstance(media_item, InputMediaPhoto):
                        debug_message = f"尝试发送照片到 {target_info}"
                        _logger.debug(debug_message)
                        self.emit("debug", debug_message)
                        
                        sent_message = await self.client.send_photo(
                            chat_id=target_id,
                            photo=media_item.media,
                            caption=media_item.caption
                        )
                    elif isinstance(media_item, InputMediaVideo):
                        # 使用缩略图
                        thumb = None
                        if thumbnails:
                            thumb = thumbnails.get(media_item.media)
                        
                        debug_message = f"尝试发送视频到 {target_info}"
                        _logger.debug(debug_message)
                        self.emit("debug", debug_message)
                        
                        sent_message = await self.client.send_video(
                            chat_id=target_id,
                            video=media_item.media,
                            caption=media_item.caption,
                            supports_streaming=True,
                            thumb=thumb
                        )
                    elif isinstance(media_item, InputMediaDocument):
                        debug_message = f"尝试发送文档到 {target_info}"
                        _logger.debug(debug_message)
                        self.emit("debug", debug_message)
                        
                        sent_message = await self.client.send_document(
                            chat_id=target_id,
                            document=media_item.media,
                            caption=media_item.caption
                        )
                    elif isinstance(media_item, InputMediaAudio):
                        debug_message = f"尝试发送音频到 {target_info}"
                        _logger.debug(debug_message)
                        self.emit("debug", debug_message)
                        
                        sent_message = await self.client.send_audio(
                            chat_id=target_id,
                            audio=media_item.media,
                            caption=media_item.caption
                        )
                    else:
                        warning_message = f"未知媒体类型: {type(media_item)}"
                        _logger.warning(warning_message)
                        self.emit("warning", warning_message)
                        return False
                else:
                    # 媒体组
                    debug_message = f"尝试发送媒体组到 {target_info}"
                    _logger.debug(debug_message)
                    self.emit("debug", debug_message)
                    
                    sent_messages = await self.client.send_media_group(
                        chat_id=target_id,
                        media=media_group
                    )
                
                # 记录转发历史
                for message in media_group_download.messages:
                    self.history_manager.add_forward_record(
                        media_group_download.source_channel,
                        message.id,
                        target_channel,
                        media_group_download.source_id
                    )
                
                success_message = f"媒体上传到 {target_info} 成功"
                _logger.info(success_message)
                self.emit("info", success_message)
                return True
            
            except FloodWait as e:
                warning_message = f"上传媒体时遇到限制，等待 {e.x} 秒"
                _logger.warning(warning_message)
                self.emit("warning", warning_message)
                
                try:
                    await asyncio.sleep(e.x)
                except asyncio.CancelledError:
                    warning_message = "上传任务已取消(FloodWait等待期间)"
                    _logger.warning(warning_message)
                    self.emit("warning", warning_message)
                    return False
            
            except Exception as e:
                retry_count += 1
                error_message = f"上传媒体到频道 {target_info} 失败 (尝试 {retry_count}/{max_retries}): {str(e)}"
                _logger.error(error_message)
                self.emit("error", error_message, error_type="UPLOAD_RETRY", recoverable=(retry_count < max_retries))
                
                if retry_count >= max_retries:
                    break
                
                status_message = f"将在 {2 * retry_count} 秒后重试上传 {group_id}"
                _logger.info(status_message)
                self.emit("status", status_message)
                
                # 指数退避
                try:
                    await asyncio.sleep(2 * retry_count)
                except asyncio.CancelledError:
                    warning_message = "上传任务已取消(重试等待期间)"
                    _logger.warning(warning_message)
                    self.emit("warning", warning_message)
                    return False
        
        error_message = f"上传媒体到 {target_info} 失败，已达到最大重试次数 {max_retries}"
        _logger.error(error_message)
        self.emit("error", error_message, error_type="MAX_RETRIES_REACHED", recoverable=False)
        return False

    async def _download_messages(self, messages: List[Message], download_dir: Path, chat_id: int) -> List[Tuple[Path, str]]:
        """
        下载消息中的媒体文件
        
        Args:
            messages: 消息列表
            download_dir: 下载目录
            chat_id: 频道ID
            
        Returns:
            List[Tuple[Path, str]]: 下载的文件路径和媒体类型列表
        """
        downloaded_files = []
        
        for message in messages:
            try:
                if message.photo:
                    # 下载照片
                    file_path = download_dir / f"{chat_id}_{message.id}_photo.jpg"
                    await self.client.download_media(message, file_name=str(file_path))
                    downloaded_files.append((file_path, "photo"))
                    _logger.debug(f"照片下载成功: {file_path}")
                
                elif message.video:
                    # 下载视频
                    file_name = message.video.file_name
                    if not file_name:
                        file_name = f"{chat_id}_{message.id}_video.mp4"
                    file_path = download_dir / file_name
                    await self.client.download_media(message, file_name=str(file_path))
                    downloaded_files.append((file_path, "video"))
                    _logger.debug(f"视频下载成功: {file_path}")
                
                elif message.document:
                    # 下载文档
                    file_name = message.document.file_name
                    if not file_name:
                        file_name = f"{chat_id}_{message.id}_document"
                    file_path = download_dir / file_name
                    await self.client.download_media(message, file_name=str(file_path))
                    downloaded_files.append((file_path, "document"))
                    _logger.debug(f"文档下载成功: {file_path}")
                
                elif message.audio:
                    # 下载音频
                    file_name = message.audio.file_name
                    if not file_name:
                        file_name = f"{chat_id}_{message.id}_audio.mp3"
                    file_path = download_dir / file_name
                    await self.client.download_media(message, file_name=str(file_path))
                    downloaded_files.append((file_path, "audio"))
                    _logger.debug(f"音频下载成功: {file_path}")
                
                elif message.animation:
                    # 下载动画(GIF)
                    file_path = download_dir / f"{chat_id}_{message.id}_animation.mp4"
                    await self.client.download_media(message, file_name=str(file_path))
                    downloaded_files.append((file_path, "video"))  # 作为视频上传
                    _logger.debug(f"动画下载成功: {file_path}")
            
            except FloodWait as e:
                logger.warning(f"下载媒体文件时遇到限制，等待 {e.x} 秒")
                await asyncio.sleep(e.x)
                # 重试下载
                retry_result = await self._retry_download_media(message, download_dir, chat_id)
                if retry_result:
                    downloaded_files.append(retry_result)
            
            except Exception as e:
                logger.error(f"下载消息 {message.id} 的媒体文件失败: {e}")
                continue
        
        return downloaded_files
        
    async def _retry_download_media(self, message: Message, download_dir: Path, chat_id: int) -> Optional[Tuple[Path, str]]:
        """
        重试下载媒体文件
        
        Args:
            message: 消息对象
            download_dir: 下载目录
            chat_id: 频道ID
            
        Returns:
            Optional[Tuple[Path, str]]: 下载成功返回(文件路径, 媒体类型)，失败返回None
        """
        retry_count = 0
        max_retries = self.general_config.max_retries
        
        while retry_count < max_retries:
            try:
                if message.photo:
                    file_path = download_dir / f"{chat_id}_{message.id}_photo.jpg"
                    await self.client.download_media(message, file_name=str(file_path))
                    return (file_path, "photo")
                
                elif message.video:
                    file_name = message.video.file_name
                    if not file_name:
                        file_name = f"{chat_id}_{message.id}_video.mp4"
                    file_path = download_dir / file_name
                    await self.client.download_media(message, file_name=str(file_path))
                    return (file_path, "video")
                
                elif message.document:
                    file_name = message.document.file_name
                    if not file_name:
                        file_name = f"{chat_id}_{message.id}_document"
                    file_path = download_dir / file_name
                    await self.client.download_media(message, file_name=str(file_path))
                    return (file_path, "document")
                
                elif message.audio:
                    file_name = message.audio.file_name
                    if not file_name:
                        file_name = f"{chat_id}_{message.id}_audio.mp3"
                    file_path = download_dir / file_name
                    await self.client.download_media(message, file_name=str(file_path))
                    return (file_path, "audio")
                
                elif message.animation:
                    file_path = download_dir / f"{chat_id}_{message.id}_animation.mp4"
                    await self.client.download_media(message, file_name=str(file_path))
                    return (file_path, "video")
                
                return None
            
            except FloodWait as e:
                logger.warning(f"重试下载时遇到限制，等待 {e.x} 秒")
                await asyncio.sleep(e.x)
            
            except Exception as e:
                retry_count += 1
                logger.error(f"重试下载失败 (尝试 {retry_count}/{max_retries}): {e}")
                if retry_count >= max_retries:
                    break
                await asyncio.sleep(2 * retry_count)  # 指数退避
        
        return None 

    def ensure_temp_dir(self) -> Path:
        """
        确保临时目录存在，如果不存在则创建
        
        Returns:
            Path: 临时目录路径
        """
        # 创建临时目录
        session_dir = self.tmp_path / datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir.mkdir(exist_ok=True, parents=True)
        
        debug_message = f"创建转发会话临时目录: {session_dir}"
        logger.debug(debug_message)
        self.emit("debug", debug_message)
        
        return session_dir
    
    async def clean_media_dirs(self, dir_path: Optional[Path] = None):
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
                                logger.debug(debug_message)
                                self.emit("debug", debug_message)
                            except Exception as e:
                                error_message = f"清理临时目录 {sub_dir} 失败: {e}"
                                logger.error(error_message)
                                self.emit("error", error_message, error_type="CLEAN_DIR", recoverable=True)
            elif dir_path.exists():
                # 清理指定目录
                try:
                    shutil.rmtree(dir_path)
                    debug_message = f"已清理指定目录: {dir_path}"
                    logger.debug(debug_message)
                    self.emit("debug", debug_message)
                except Exception as e:
                    error_message = f"清理指定目录 {dir_path} 失败: {e}"
                    logger.error(error_message)
                    self.emit("error", error_message, error_type="CLEAN_DIR", recoverable=True)
        except Exception as e:
            error_message = f"清理媒体目录失败: {e}"
            logger.error(error_message)
            self.emit("error", error_message, error_type="CLEAN_DIR", recoverable=True) 
    
    def _estimate_media_size(self, message: Message) -> int:
        """
        估计媒体文件大小
        
        Args:
            message: 消息对象
            
        Returns:
            int: 预估的文件大小（字节）
        """
        if hasattr(message, 'photo') and message.photo:
            # 使用最大尺寸的照片
            if isinstance(message.photo, list):
                if len(message.photo) > 0:
                    photo = message.photo[-1]  # 获取最大尺寸
                    return photo.file_size if hasattr(photo, 'file_size') and photo.file_size else 0
            return 0
        elif hasattr(message, 'video') and message.video:
            return message.video.file_size if hasattr(message.video, 'file_size') and message.video.file_size else 0
        elif hasattr(message, 'document') and message.document:
            return message.document.file_size if hasattr(message.document, 'file_size') and message.document.file_size else 0
        elif hasattr(message, 'audio') and message.audio:
            return message.audio.file_size if hasattr(message.audio, 'file_size') and message.audio.file_size else 0
        elif hasattr(message, 'animation') and message.animation:
            return message.animation.file_size if hasattr(message.animation, 'file_size') and message.animation.file_size else 0
        elif hasattr(message, 'voice') and message.voice:
            return message.voice.file_size if hasattr(message.voice, 'file_size') and message.voice.file_size else 0
        elif hasattr(message, 'video_note') and message.video_note:
            return message.video_note.file_size if hasattr(message.video_note, 'file_size') and message.video_note.file_size else 0
        return 0
        
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