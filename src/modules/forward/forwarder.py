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
        self.message_filter = MessageFilter(self.config)
        self.media_uploader = MediaUploader(self.client, self.history_manager, self.general_config)
        self.parallel_processor = ParallelProcessor(self.client, self.history_manager, self.general_config)
        
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
        
        # 处理每个频道对
        for pair in channel_pairs:
            source_channel = pair.get("source_channel", "")
            target_channels = pair.get("target_channels", [])
            
            # 添加调试信息，显示频道对配置的详细内容
            _logger.debug(f"完整频道对配置: {pair}")
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
                    media_groups = await self.media_group_collector.get_media_groups_optimized(
                        source_id, source_channel, target_channel_list, pair, self.history_manager
                    )
                    
                    # 发送总媒体组数量
                    total_groups = len(media_groups)
                    
                    # 添加进度事件
                    group_count = 0
                    
                    # 获取是否隐藏作者配置
                    hide_author = self.forward_config.get('hide_author', False)
                    
                    # 如果没有媒体组，跳过此频道对
                    if not media_groups:
                        _logger.info(f"源频道 {source_channel} 没有未转发的媒体组/消息，跳过")
                        continue
                    
                    # 遍历每个媒体组并转发
                    for group_id, messages in media_groups.items():
                        # 更新进度
                        group_count += 1
                        
                        # 转发媒体组到所有目标频道
                        success = await self.direct_forwarder.forward_media_group_directly(
                            messages, source_channel, source_id, valid_target_channels, hide_author, pair
                        )
                        
                        if success:
                            forward_count += 1
                            total_forward_count += 1
                        
                        # 简短的延迟，避免请求过于频繁
                        await asyncio.sleep(0.5)
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
                    media_groups_info = await self.media_group_collector.get_media_groups_info_optimized(
                        source_id, source_channel, target_channel_list, pair, self.history_manager
                    )
                    total_groups = len(media_groups_info)
                    
                    # 如果没有媒体组，跳过此频道对
                    if not media_groups_info:
                        _logger.info(f"源频道 {source_channel} 没有未转发的媒体组/消息，跳过")
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
        status_message = f"🎉 转发任务完成，成功转发 {total_forward_count} 个媒体组/消息"
        _logger.info(status_message)
        
        # 发送最终消息
        if self.forward_config.get('send_final_message', False) and all_target_channels:
            await self._send_final_message(all_target_channels)
        
        # 清理临时文件
        await self._clean_media_dirs(temp_dir)
    
    async def _send_final_message(self, target_channels: List[Tuple[str, int, str]]):
        """
        发送最终消息到所有目标频道
        
        Args:
            target_channels: 目标频道列表，每个元素为 (channel_string, channel_id, channel_info_str)
        """
        # 检查是否启用了发送最终消息功能
        if not self.forward_config.get('send_final_message', False):
            return
        
        # 获取HTML文件路径
        html_file_path = self.forward_config.get('final_message_html_file', '')
        if not html_file_path:
            _logger.warning("未指定最终消息HTML文件路径，跳过发送最终消息")
            return
        
        html_path = Path(html_file_path)
        if not html_path.exists() or not html_path.is_file():
            _logger.error(f"最终消息HTML文件不存在或不是文件: {html_file_path}")
            return
        
        try:
            # 读取HTML文件内容
            with open(html_path, 'r', encoding='utf-8') as f:
                html_content = f.read().strip()
            
            if not html_content:
                _logger.warning("最终消息HTML文件内容为空，跳过发送最终消息")
                return
            
            _logger.info(f"准备发送最终消息到 {len(target_channels)} 个目标频道")
            
            # 使用HTML解析模式发送消息
            from pyrogram import enums
            
            # 发送到每个目标频道
            for channel_string, channel_id, channel_info in target_channels:
                try:
                    # 使用Pyrogram的HTML支持发送消息
                    await self.client.send_message(
                        chat_id=channel_id,
                        text=html_content,
                        parse_mode=enums.ParseMode.HTML,
                        disable_web_page_preview=False  # 允许网页预览
                    )
                    _logger.info(f"已发送最终消息到 {channel_info}")
                    
                    # 添加短暂延迟避免速率限制
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    _logger.error(f"向 {channel_info} 发送最终消息失败: {e}")
                    continue
                
            _logger.info("所有最终消息发送完成")
            
        except Exception as e:
            _logger.error(f"处理最终消息失败: {e}")
    
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
        
        # 设置停止标志（如果有的话）
        if hasattr(self, 'should_stop'):
            self.should_stop = True
        
        # 停止并行处理器
        if hasattr(self, 'parallel_processor') and self.parallel_processor:
            if hasattr(self.parallel_processor, 'download_running'):
                self.parallel_processor.download_running = False
            if hasattr(self.parallel_processor, 'upload_running'):
                self.parallel_processor.upload_running = False
        
        # 停止直接转发器
        if hasattr(self, 'direct_forwarder') and self.direct_forwarder:
            if hasattr(self.direct_forwarder, 'should_stop'):
                self.direct_forwarder.should_stop = True
        
        _logger.info("转发器已停止") 