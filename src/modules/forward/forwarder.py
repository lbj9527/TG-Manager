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
from src.utils.history_manager import HistoryManager
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
        
        # 初始化重构后的组件
        self.message_filter = MessageFilter(self.config)
        self.message_iterator = MessageIterator(client, channel_resolver)
        self.message_downloader = MessageDownloader(client)
        self.direct_forwarder = DirectForwarder(client, history_manager)
        self.media_uploader = MediaUploader(client, history_manager, self.general_config)
        self.media_group_collector = MediaGroupCollector(self.message_iterator, self.message_filter)
        self.parallel_processor = ParallelProcessor(client, history_manager, self.general_config)
        
        # 初始化视频处理器
        self.video_processor = VideoProcessor()
    
    async def forward_messages(self):
        """
        从源频道转发消息到目标频道
        """
        
        _logger.info("开始转发消息")
        
        # 创建临时会话目录
        temp_dir = self._ensure_temp_dir()
        
        # 获取频道对列表
        channel_pairs = self.forward_config.get('forward_channel_pairs', [])
        info_message = f"配置的频道对数量: {len(channel_pairs)}"
        _logger.info(info_message)
        
        # 遍历频道对，检查和打印配置
        for i, pair in enumerate(channel_pairs):
            _logger.info(f"检查频道对 {i+1}: source_channel={pair.get('source_channel')}, "
                         f"target_channels={pair.get('target_channels')}, "
                         f"start_id={pair.get('start_id')}, end_id={pair.get('end_id')}")
        
        # 转发计数
        forward_count = 0
        total_forward_count = 0
        
        # 处理每个频道对
        for pair in channel_pairs:
            source_channel = pair["source_channel"]
            target_channels = pair["target_channels"]
            
            if not target_channels:
                warning_message = f"源频道 {source_channel} 没有配置目标频道，跳过"
                _logger.warning(warning_message)
                continue
            
            info_message = f"准备从 {source_channel} 转发到 {len(target_channels)} 个目标频道"
            _logger.info(info_message)
            
            try:
                # 解析源频道ID
                source_id = await self.channel_resolver.get_channel_id(source_channel)
                source_info_str, (source_title, _) = await self.channel_resolver.format_channel_info(source_id)
                info_message = f"源频道: {source_info_str}"
                _logger.info(info_message)
                
                # 检查源频道转发权限
                status_message = "检查源频道转发权限..."
                _logger.info(status_message)
                
                source_can_forward = await self.channel_resolver.check_forward_permission(source_id)
                info_message = f"源频道转发权限: {source_can_forward}"
                _logger.info(info_message)
                
                # 获取有效的目标频道
                valid_target_channels = []
                for target in target_channels:        
                    try:
                        target_id = await self.channel_resolver.get_channel_id(target)
                        target_info_str, (target_title, _) = await self.channel_resolver.format_channel_info(target_id)
                        valid_target_channels.append((target, target_id, target_info_str))
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
                    
                    # 获取媒体组和消息，传入当前频道对配置
                    media_groups = await self.media_group_collector.get_media_groups(source_id, source_channel, pair)
                    
                    # 发送总媒体组数量
                    total_groups = len(media_groups)
                    info_message = f"找到 {total_groups} 个媒体组/消息"
                    _logger.info(info_message)
                    
                    # 添加进度事件
                    group_count = 0
                    
                    # 获取是否隐藏作者配置
                    hide_author = self.forward_config.get('hide_author', False)
                    
                    # 处理每个媒体组
                    for group_id, messages in media_groups.items():
                        # 更新进度
                        group_count += 1
                        progress_percentage = (group_count / total_groups) * 100
                        
                        # 转发媒体组
                        success = await self.direct_forwarder.forward_media_group_directly(
                            messages, 
                            source_channel, 
                            source_id, 
                            valid_target_channels,
                            hide_author
                        )
                        
                        if success:
                            forward_count += 1
                            total_forward_count += 1
                        
                        # 检查是否达到转发限制
                        if self.general_config.get('limit', 0) > 0 and forward_count >= self.general_config.get('limit', 0):
                            status_message = f"已达到转发限制 {self.general_config.get('limit', 0)}，暂停 {self.general_config.get('pause_time', 60)} 秒"
                            _logger.info(status_message)
                            await asyncio.sleep(self.general_config.get('pause_time', 60))
                            forward_count = 0
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
                    
                    # 获取媒体组信息，传入当前频道对配置
                    media_groups_info = await self.media_group_collector.get_media_groups_info(source_id, pair)
                    total_groups = len(media_groups_info)
                    info_message = f"找到 {total_groups} 个媒体组/消息"
                    _logger.info(info_message)
                    
                    # 如果没有媒体组，跳过此频道对
                    if not media_groups_info:
                        warning_message = f"源频道 {source_channel} 没有媒体组/消息，跳过"
                        _logger.warning(warning_message)
                        continue
                    
                    # 启动下载和上传任务
                    try:
                        # 使用并行处理器处理此频道对
                        await self.parallel_processor.process_parallel_download_upload(
                            source_channel,
                            source_id,
                            media_groups_info,
                            channel_temp_dir,
                            valid_target_channels
                        )
                        
                        # 记录本组转发的消息数
                        total_forward_count += forward_count
                        info_message = f"从 {source_channel} 已转发 {forward_count} 个媒体组/消息"
                        _logger.info(info_message)
                        
                    except Exception as e:
                        error_message = f"下载和上传任务失败: {str(e)}"
                        _logger.error(error_message)
                        import traceback
                        error_details = traceback.format_exc()
                        _logger.error(error_details)
                        continue
            
            except Exception as e:
                error_message = f"处理频道对 {source_channel} 失败: {str(e)}"
                _logger.error(error_message)
                import traceback
                error_details = traceback.format_exc()
                _logger.error(error_details)
                continue
        
        # 转发完成
        status_message = f"所有转发任务完成，共转发 {total_forward_count} 个媒体组/消息"
        _logger.info(status_message)
        
        # 清理临时文件
        await self._clean_media_dirs(temp_dir)
    
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