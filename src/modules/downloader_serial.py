"""
下载模块（顺序下载版本），负责按顺序下载历史消息的媒体文件
"""

import os
import time
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Union, Any, Optional, Set, Tuple

from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait

from src.utils.ui_config_manager import UIConfigManager
from src.utils.config_utils import convert_ui_config_to_dict
from src.utils.channel_resolver import ChannelResolver
from src.utils.database_manager import DatabaseManager
from src.utils.logger import get_logger


# 仅用于内部调试，不再用于UI输出
logger = get_logger()

class DownloaderSerial():
    """
    下载模块（顺序版本），负责按顺序下载历史消息的媒体文件
    """
    
    def __init__(self, client: Client, ui_config_manager: UIConfigManager, channel_resolver: ChannelResolver, history_manager: DatabaseManager, app=None):
        """
        初始化下载模块
        
        Args:
            client: Pyrogram客户端实例
            ui_config_manager: UI配置管理器实例
            channel_resolver: 频道解析器实例
            history_manager: 数据库管理器实例
            app: 应用程序实例，用于网络错误时立即检查连接状态
        """
        super().__init__()
        self.client = client
        self.ui_config_manager = ui_config_manager
        self.channel_resolver = channel_resolver
        self.history_manager = history_manager
        self.app = app  # 保存应用程序实例引用
        
        # 获取UI配置并转换为字典
        ui_config = self.ui_config_manager.get_ui_config()
        self.config = convert_ui_config_to_dict(ui_config)
        
        # 添加详细日志输出，显示整个配置结构
        logger.debug(f"加载的UI配置类型: {type(ui_config)}")
        logger.debug(f"配置字典键: {self.config.keys()}")
        
        # 获取下载配置和通用配置
        self.download_config = self.config.get('DOWNLOAD', {})
        self.general_config = self.config.get('GENERAL', {})
        
        # 详细打印下载配置的结构和内容
        logger.debug(f"下载配置内容: {json.dumps(self.download_config, indent=2, ensure_ascii=False, default=str)}")
        
        # 检查downloadSetting是否存在
        if 'downloadSetting' in self.download_config:
            logger.info(f"发现下载设置，共 {len(self.download_config['downloadSetting'])} 项")
            for idx, setting in enumerate(self.download_config['downloadSetting']):
                logger.debug(f"下载设置 #{idx+1}: {json.dumps(setting, indent=2, ensure_ascii=False, default=str)}")
        else:
            logger.warning("下载配置中不存在downloadSetting字段")
        
        # 创建下载目录
        self.download_path = Path(self.download_config.get('download_path', 'downloads'))
        self.download_path.mkdir(exist_ok=True)
        logger.info(f"下载目录: {self.download_path}")
        
        # 添加下载状态跟踪
        self._current_file = None  # 当前正在下载的文件名
        self._download_progress = (0, 0)  # 当前进度和总进度
        self._is_downloading = False  # 是否正在下载
        self._current_speed = (0, "B/s")  # 当前下载速度 (数值, 单位)
        
        # 初始化队列和状态变量
        self._download_queue = asyncio.Queue()
        self._done = False
        self._is_stopped = False
        
        # 初始化进度追踪变量
        self._last_progress_time = time.time()
        self._last_progress_bytes = 0
    
    def get_current_file(self) -> str:
        """
        获取当前正在下载的文件名
        
        Returns:
            str: 当前文件名，如果没有正在下载的文件则返回None
        """
        return self._current_file
    
    def get_download_progress(self) -> tuple:
        """
        获取当前下载进度
        
        Returns:
            tuple: (当前进度, 总进度)
        """
        return self._download_progress
    
    def get_download_speed(self) -> tuple:
        """
        获取当前下载速度
        
        Returns:
            tuple: (速度值, 单位)
        """
        if hasattr(self, '_current_speed') and self._current_speed is not None:
            # 确保 _current_speed 是数值，不是元组
            if isinstance(self._current_speed, tuple):
                speed = self._current_speed[0]
            else:
                speed = self._current_speed
            
            if speed < 1024 * 1024:  # 小于1MB/s，显示KB/s
                return (speed / 1024, "KB/s")
            else:  # 否则显示MB/s
                return (speed / (1024 * 1024), "MB/s")
        return (0, "KB/s")
    
    def is_downloading(self) -> bool:
        """
        检查是否正在下载
        
        Returns:
            bool: 是否正在下载
        """
        return self._is_downloading
    
    def reset_progress(self):
        """
        重置下载进度计数器
        """
        self._download_progress = (0, 0)
        self._current_speed = 0
        self._last_progress_time = time.time()
        self._last_progress_bytes = 0
        self._is_downloading = False
        self._current_file = None
        logger.info("下载进度计数器已重置")
    
    def _setting_has_keywords(self, setting: Dict[str, Any]) -> bool:
        """
        检查下载设置是否包含有效的关键词配置
        
        Args:
            setting: 下载设置字典
            
        Returns:
            bool: 是否包含有效的关键词配置
        """
        keywords = setting.get('keywords', [])
        return bool(keywords and isinstance(keywords, list) and len(keywords) > 0)
    
    async def download_media_from_channels(self):
        """
        从配置的频道下载媒体文件，自动根据设置是否含有关键词组织下载目录
        """
        
        # 重新获取最新配置
        logger.info("下载前重新获取最新配置...")
        try:
            ui_config = self.ui_config_manager.reload_config()
            self.config = convert_ui_config_to_dict(ui_config)
            
            # 更新下载配置和通用配置
            self.download_config = self.config.get('DOWNLOAD', {})
            self.general_config = self.config.get('GENERAL', {})
            
            # 重新创建下载目录（如果路径已更改）
            self.download_path = Path(self.download_config.get('download_path', 'downloads'))
            self.download_path.mkdir(exist_ok=True)
            
            logger.info(f"配置已更新，下载设置数: {len(self.download_config.get('downloadSetting', []))}")
        except Exception as e:
            logger.error(f"更新配置时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        logger.info(f"开始从频道下载媒体文件")
        self._is_downloading = True
        
        # 获取下载频道列表
        download_settings = self.download_config.get('downloadSetting', [])
        logger.info(f"获取到 {len(download_settings)} 个下载设置")
        
        # 详细打印每个下载设置
        for idx, setting in enumerate(download_settings):
            logger.info(f"下载设置 #{idx+1}: 源频道={setting.get('source_channels', '')}, "
                       f"起始ID={setting.get('start_id', 0)}, 结束ID={setting.get('end_id', 0)}, "
                       f"媒体类型={setting.get('media_types', [])}")
            
            # 检查是否包含关键词
            keywords = setting.get('keywords', [])
            if self._setting_has_keywords(setting):
                logger.info(f"下载设置 #{idx+1} 包含关键词: {keywords}，将按关键词组织下载目录")
            else:
                logger.info(f"下载设置 #{idx+1} 未设置关键词，将使用普通目录结构")
        
        if not download_settings:
            logger.error("未配置下载设置，无法开始下载", error_type="CONFIG", recoverable=False)
            return
        
        # 使用get_estimated_download_count函数获取预估下载总数和全局限制值
        estimated_download_count = self.get_estimated_download_count()
        global_limit = self.general_config.get('limit', 50)
        logger.info(f"全局限制值: {global_limit} 条消息")
        logger.info(f"预计总下载消息数估计: {estimated_download_count} 条（初步估计，将在处理过程中更新）")
        
        # 已完成的下载数量
        completed_count = 0
        
        # 实际待下载的文件总数，将在遍历频道后更新
        total_download_count = 0
        
        # 第一轮：收集所有待下载的媒体信息
        # 保存每个频道的待下载媒体组
        pending_downloads = []
        
        # 遍历所有下载设置
        for setting in download_settings:
            # 获取下载配置
            channel_name = setting.get('source_channels', '')
            start_id = setting.get('start_id', 0)
            end_id = setting.get('end_id', 0)
            
            # 检查设置是否包含关键词
            has_keywords = self._setting_has_keywords(setting)
            keywords = setting.get('keywords', []) if has_keywords else []
            
            directory_mode = "按关键词组织" if has_keywords else "普通目录结构"
            logger.info(f"处理频道 {channel_name} ({directory_mode}), 开始ID: {start_id}, 结束ID: {end_id}")
            
            # 计算限制
            limit = abs(end_id - start_id) + 1 if start_id and end_id else global_limit
            logger.info(f"消息限制: {limit if limit > 0 else '无限制'}")
            
            # 确保下载目录存在
            download_path = Path(self.download_config.get('download_path', 'downloads'))
            download_path.mkdir(parents=True, exist_ok=True)
            
            # 如果设置了限制为0，则跳过
            if limit == 0:
                logger.info(f"频道 {channel_name} 的下载限制为0，跳过")
                continue
            
            # 解析频道ID
            try:              
                # 解析频道标识符，获取纯频道ID（去除消息ID部分）
                channel_id_info, message_id = await self.channel_resolver.resolve_channel(channel_name)
                logger.debug(f"解析频道标识符 {channel_name} 的结果: {channel_id_info}, 消息ID: {message_id}")
                
                # 获取真实的频道ID（数字ID）
                real_channel_id = await self.channel_resolver.get_channel_id(channel_id_info)
                if not real_channel_id:
                    logger.error(f"无法解析频道 {channel_name}", error_type="CHANNEL_RESOLVE", recoverable=True)
                    continue
                
                # 获取频道信息用于显示
                channel_info_str, (channel_title, _) = await self.channel_resolver.format_channel_info(real_channel_id)
                logger.info(f"开始从频道 {channel_info_str} 下载媒体，限制 {limit if limit > 0 else '无'} 条")
                
                # 始终按频道创建主目录
                base_folder_name = f"{channel_title}-{real_channel_id}"
                base_folder_name = self._sanitize_filename(base_folder_name)
                channel_download_path = download_path / base_folder_name
                channel_download_path.mkdir(exist_ok=True)
                
                logger.info(f"下载目录: {channel_download_path}")
                
                # 获取该频道的历史记录，使用原始频道名称作为键
                downloaded_messages = self.history_manager.get_downloaded_messages(channel_name)
                logger.info(f"已下载的消息数量: {len(downloaded_messages)}")
                
                # 如果有关键词，在频道目录下创建关键词目录
                if has_keywords:
                    logger.info(f"使用关键词组织目录: {keywords}")
                    # 在频道目录下创建关键词目录
                    for keyword in keywords:
                        keyword_dir = self._sanitize_filename(keyword)
                        keyword_path = channel_download_path / keyword_dir
                        keyword_path.mkdir(exist_ok=True)
                        logger.debug(f"创建关键词目录: {keyword_path}")
                
                # 收集所有消息
                all_messages = []
                try:
                    # 获取消息，使用_iter_messages按照从旧到新的顺序获取
                    async for message in self._iter_messages(real_channel_id, start_id, end_id, limit):
                        all_messages.append(message)
                except Exception as e:
                    if "PEER_ID_INVALID" in str(e):
                        logger.error(f"无法获取频道 {channel_name} 的消息: 频道ID无效或未加入该频道")
                        continue
                    else:
                        logger.error(f"获取频道 {channel_name} 的消息失败: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                        continue
                
                # 按照媒体组进行分组
                messages_by_group = {}  # 媒体组ID -> 消息列表
                matched_groups = set()  # 匹配关键词的媒体组ID
                matched_keywords = {}   # 媒体组ID -> 匹配的关键词
                                
                # 处理收集到的所有消息
                for message in all_messages:
                    if message.id in downloaded_messages:
                        logger.info(f"消息 {message.id} 已下载，跳过")
                        # 发送文件已下载跳过事件
                        file_name = self._generate_filename(message, channel_title)
                        self.emit("file_already_downloaded", message.id, file_name)
                        continue
                    
                    # 检查消息是否包含媒体
                    if not message.media:
                        continue
                        
                    # 检查文件类型是否符合允许的媒体类型
                    file_type = self._get_media_type(message)
                    media_types = setting.get('media_types', [])
                    if media_types and file_type not in media_types:
                        logger.debug(f"消息ID: {message.id} 的文件类型 {file_type} 不在允许的媒体类型列表中，跳过")
                        continue
                    
                    # 确定媒体组ID
                    group_id = str(message.media_group_id) if message.media_group_id else f"single_{message.id}"
                    
                    # 将消息添加到对应的媒体组
                    if group_id not in messages_by_group:
                        messages_by_group[group_id] = []
                    messages_by_group[group_id].append(message)
                    
                    # 在关键词模式下，检查消息文本是否包含关键词
                    if has_keywords and group_id not in matched_groups:
                        # 获取消息文本（正文或说明文字）
                        text = message.text or message.caption or ""
                        if text:
                            # 检查文本是否包含任何关键词
                            for keyword in keywords:
                                # 检查是否是同义关键词组（包含横杠分隔符）
                                if "-" in keyword:
                                    # 分割同义关键词
                                    synonym_keywords = [k.strip() for k in keyword.split("-") if k.strip()]
                                    # 任一同义词匹配即视为匹配
                                    for syn_keyword in synonym_keywords:
                                        if syn_keyword.lower() in text.lower():
                                            matched_groups.add(group_id)
                                            matched_keywords[group_id] = keyword  # 保存整个同义词组
                                            logger.info(f"媒体组 {group_id} (消息ID: {message.id}) 匹配同义关键词组: {keyword} 中的 {syn_keyword}")
                                            break
                                else:
                                    # 普通关键词匹配
                                    if keyword.lower() in text.lower():
                                        matched_groups.add(group_id)
                                        matched_keywords[group_id] = keyword
                                        logger.info(f"媒体组 {group_id} (消息ID: {message.id}) 匹配关键词: {keyword}")
                                
                                # 如果已匹配，无需继续检查其他关键词
                                if group_id in matched_groups:
                                    break
                
                # 构建实际待下载的媒体项列表
                channel_pending_downloads = []
                
                # 第二轮处理：处理每个媒体组
                for group_id, messages in messages_by_group.items():
                    # 如果是关键词模式且没有匹配关键词，则跳过整个媒体组
                    if has_keywords and group_id not in matched_groups:
                        logger.debug(f"媒体组 {group_id} 不包含任何关键词，跳过")
                        continue
                    
                    # 添加到待下载列表
                    for message in messages:
                        # 检查文件是否已存在
                        file_name = self._generate_filename(message, channel_title)
                        file_path = None  # 实际路径在下载时计算
                        
                        # 将待下载项添加到列表
                        channel_pending_downloads.append({
                            'message': message,
                            'file_name': file_name,
                            'group_id': group_id,
                            'matched_keyword': matched_keywords.get(group_id) if has_keywords and group_id in matched_groups else None
                        })
                
                # 将此频道的待下载项添加到总列表
                if channel_pending_downloads:
                    pending_downloads.append({
                        'channel_name': channel_name,
                        'channel_title': channel_title,
                        'real_channel_id': real_channel_id,
                        'download_path': channel_download_path,
                        'has_keywords': has_keywords,
                        'keywords': keywords,
                        'items': channel_pending_downloads
                    })
                    
                    # 更新待下载总数
                    total_download_count += len(channel_pending_downloads)
                
            except Exception as e:
                logger.error(f"处理频道 {channel_name} 时出错: {str(e)}", error_type="CHANNEL_PROCESS", recoverable=True)
                import traceback
                error_details = traceback.format_exc()
                logger.error(error_details)
        
        # 更新实际待下载总数
        logger.info(f"实际待下载文件总数: {total_download_count} 个文件")
        
        # 立即更新进度计数器
        self._download_progress = (0, total_download_count)
        # 发送进度更新事件，确保UI能即时获取到总文件数
        self.emit("progress", 0, total_download_count, "")
        
        # 第二轮：执行实际下载
        for channel_data in pending_downloads:
            channel_name = channel_data['channel_name']
            channel_title = channel_data['channel_title']
            real_channel_id = channel_data['real_channel_id']
            channel_download_path = channel_data['download_path']
            has_keywords = channel_data['has_keywords']
            
            downloaded_count = 0
            
            # 处理此频道的所有待下载项
            for download_item in channel_data['items']:
                message = download_item['message']
                file_name = download_item['file_name']
                group_id = download_item['group_id']
                matched_keyword = download_item['matched_keyword']
                
                # 确定当前路径
                current_channel_path = channel_download_path
                
                # 如果匹配了关键词，使用关键词目录
                if matched_keyword:
                    keyword_folder = self._sanitize_filename(matched_keyword)
                    keyword_path = channel_download_path / keyword_folder
                    keyword_path.mkdir(exist_ok=True)
                    current_channel_path = keyword_path
                
                # 确定媒体组路径
                if not group_id.startswith("single_"):
                    safe_group_id = self._sanitize_filename(str(group_id))
                    media_group_path = current_channel_path / safe_group_id
                    media_group_path.mkdir(exist_ok=True)
                    logger.debug(f"为媒体组 {group_id} 创建目录: {media_group_path}")
                else:
                    # 对于单条消息，也创建单独的子目录，以消息ID命名
                    message_id = str(message.id)
                    safe_message_id = self._sanitize_filename(message_id)
                    media_group_path = current_channel_path / safe_message_id
                    media_group_path.mkdir(exist_ok=True)
                    logger.debug(f"为单条消息 {message.id} 创建目录: {media_group_path}")
                
                # 获取该媒体组的所有消息
                group_messages = [item['message'] for item in channel_data['items'] if item['group_id'] == group_id]
                
                # 添加回生成title.txt的代码
                # 简化title.txt内容，只保存caption
                try:
                    title_file_path = media_group_path / "title.txt"
                    # 如果文件已经存在，跳过创建
                    if not title_file_path.exists() and group_messages:
                        with open(title_file_path, "w", encoding="utf-8") as f:
                            # 尝试获取包含最多文本的消息
                            best_message = None
                            best_text_length = 0
                            for msg in group_messages:
                                text = msg.text or msg.caption or ""
                                if len(text) > best_text_length:
                                    best_text_length = len(text)
                                    best_message = msg
                            
                            if best_message:
                                text = best_message.text or best_message.caption or ""
                                if text:
                                    f.write(f"{text}\n")
                except Exception as e:
                    logger.error(f"保存标题文件失败: {e}")
                
                # 完整文件路径
                file_path = media_group_path / file_name
                
                # 检查文件是否已存在
                if file_path.exists():
                    logger.debug(f"文件已存在: {file_path}，跳过下载")
                    # 标记为已下载
                    self.history_manager.add_download_record(channel_name, message.id, real_channel_id)
                    # 发送文件已下载跳过事件
                    self.emit("file_already_downloaded", message.id, file_name)
                    continue
                
                # 下载前检查目录大小限制
                exceeded, current_size_mb, limit_mb = await self._check_directory_size_limit()
                if exceeded:
                    logger.warning(f"下载目录大小超出限制: 当前 {current_size_mb}MB, 限制 {limit_mb}MB")
                    # 发送错误事件通知UI
                    error_msg = f"下载目录大小超出限制（当前: {current_size_mb}MB, 限制: {limit_mb}MB）"
                    self.emit("error", error_msg, "下载已自动停止")
                    # 停止下载
                    self._is_downloading = False
                    self._current_file = None
                    return
                
                # 下载媒体
                logger.info(f"正在下载: {file_name}")
                self._current_file = file_name  # 设置当前文件
                try:
                    # 开始时间
                    start_time = time.time()
                    
                    # 下载文件
                    download_path = await self.client.download_media(
                        message,
                        file_name=str(file_path),
                        progress=self._download_progress_callback(self.client, message.id, file_name)
                    )
                    
                    # 计算下载时间
                    download_time = time.time() - start_time
                    
                    if download_path:
                        # 获取文件大小
                        file_stat = os.stat(download_path)
                        file_size_mb = file_stat.st_size / (1024 * 1024)
                        
                        # 下载速度计算
                        speed_mbps = file_size_mb / download_time if download_time > 0 else 0
                        
                        logger.info(
                            f"下载完成: {file_name} ({file_size_mb:.2f}MB, {download_time:.2f}s, {speed_mbps:.2f}MB/s)")
                        
                        # 标记为已下载，使用原始频道名称作为键
                        self.history_manager.add_download_record(channel_name, message.id, real_channel_id)
                        
                        # 发送下载完成事件
                        file_size = int(file_size_mb * 1024 * 1024)  # 转换为字节
                        self.emit("download_complete", message.id, file_name, file_size)
                        
                        # 增加下载计数
                        downloaded_count += 1
                        completed_count += 1
                        
                        # 计算进度百分比
                        progress_percentage = (completed_count / total_download_count) * 100 if total_download_count > 0 else 0
                        logger.info(f"总进度: {completed_count}/{total_download_count} ({progress_percentage:.2f}%)")
                        # 更新下载进度
                        self._download_progress = (completed_count, total_download_count)
                    else:
                        logger.error(f"下载失败: {file_name}", error_type="DOWNLOAD_FAIL", recoverable=True)
                
                except FloodWait as e:
                    logger.warning(f"下载受限，等待 {e.x} 秒")
                    await asyncio.sleep(e.x)
                    
                except Exception as e:
                    logger.error(f"下载异常: {str(e)}", error_type="DOWNLOAD_ERROR", recoverable=True)
                    
                    # 检测网络相关错误
                    error_name = type(e).__name__.lower()
                    if any(net_err in error_name for net_err in ['network', 'connection', 'timeout', 'socket']):
                        # 网络相关错误，通知应用程序检查连接状态
                        await self._handle_network_error(e)
            
            # 完成一个频道的下载
            channel_info_str, _ = await self.channel_resolver.format_channel_info(real_channel_id)
            logger.info(f"完成频道 {channel_info_str} 的下载，共下载 {downloaded_count} 个文件")
        
        # 所有频道处理完成
        logger.info(f"所有下载任务完成，共下载 {completed_count} 个文件")
        self._is_downloading = False
        self._current_file = None
        
        # 发送所有下载完成信号
        self.emit("all_downloads_complete")
    
    def _download_progress_callback(self, client, message_id, filename):
        """下载进度回调函数
        
        Args:
            client: 客户端对象
            message_id: 消息ID
            filename: 文件名
        
        Returns:
            回调函数
        """
        # 返回一个内部的回调函数来处理进度更新
        def callback(current, total):
            try:
                if total == 0:
                    return
                
                # 计算进度百分比
                percentage = 100 * (current / total)
                
                # 计算下载速度
                now = time.time()
                time_diff = now - self._last_progress_time
                
                if time_diff > 0:
                    speed = (current - self._last_progress_bytes) / time_diff
                    self._current_speed = speed  # 保存当前速度供get_download_speed方法使用
                    
                    # 获取格式化后的速度
                    speed_value, speed_unit = self.get_download_speed()
                    speed_str = f"{speed_value:.1f} {speed_unit}"
                    
                    # 计算剩余时间
                    remaining_bytes = total - current
                    if speed > 0:
                        time_remaining = remaining_bytes / speed  # 剩余时间（秒）
                        if time_remaining < 60:
                            time_str = f"{time_remaining:.1f}秒"
                        elif time_remaining < 3600:
                            time_str = f"{time_remaining / 60:.1f}分钟"
                        else:
                            time_str = f"{time_remaining / 3600:.1f}小时"
                    else:
                        time_str = "未知"
                    
                    # 更新最后进度信息
                    self._last_progress_time = now
                    self._last_progress_bytes = current
                    
                    # 打印进度信息
                    logger.info(f"下载进度: {percentage:.2f}% ({current}/{total}) - 速度: {speed_str} - 剩余时间: {time_str} - 文件: {filename}")
                    
                    # 发出进度更新事件
                    self.emit("progress", current, total, filename)
            except Exception as e:
                logger.error(f"计算下载进度时出错: {str(e)}")
            
        return callback
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        清理文件名，去除非法字符
        
        Args:
            filename: 原始文件名
            
        Returns:
            清理后的文件名
        """
        # 替换Windows和Unix下的非法字符
        illegal_chars = r'<>:"/\|?*'
        for char in illegal_chars:
            filename = filename.replace(char, '_')
        
        # 去除前后空格
        filename = filename.strip()
        
        # 如果文件名为空，使用默认名称
        if not filename:
            filename = "untitled"
        
        return filename
    
    def _generate_filename(self, message: Message, channel_title: str) -> str:
        """
        根据消息生成文件名
        
        Args:
            message: 消息对象
            channel_title: 频道标题
            
        Returns:
            生成的文件名
        """
        # 获取消息日期和ID
        date_str = message.date.strftime("%Y%m%d")
        message_id = message.id
        
        # 获取媒体类型和原始文件名
        media_type = self._get_media_type(message)
        original_name = self._get_original_filename(message)
        
        # 如果有原始文件名，使用原始文件名
        if original_name:
            # 分割文件名和扩展名
            name_parts = original_name.rsplit('.', 1)
            if len(name_parts) > 1 and len(name_parts[1]) <= 5:  # 扩展名通常不超过5个字符
                basename = name_parts[0]
                extension = name_parts[1]
            else:
                basename = original_name
                extension = self._get_default_extension(media_type)
            
            # 清理文件名
            basename = self._sanitize_filename(basename)
            
            # 组合新文件名: 日期_ID_频道名_原始文件名.扩展名
            filename = f"{date_str}_{message_id}_{self._sanitize_filename(channel_title)}_{basename}.{extension}"
        else:
            # 没有原始文件名，使用默认格式: 日期_ID_频道名.扩展名
            extension = self._get_default_extension(media_type)
            filename = f"{date_str}_{message_id}_{self._sanitize_filename(channel_title)}.{extension}"
        
        return filename
    
    def _get_media_type(self, message: Message) -> str:
        """
        获取消息的媒体类型
        
        Args:
            message: 消息对象
            
        Returns:
            媒体类型
        """
        if message.photo:
            return "photo"
        elif message.video:
            return "video"
        elif message.document:
            return "document"
        elif message.audio:
            return "audio"
        elif message.voice:
            return "voice"
        elif message.animation:
            return "animation"
        elif message.sticker:
            return "sticker"
        elif message.video_note:
            return "video_note"
        else:
            return "unknown"
    
    def _get_media_size(self, message: Message) -> Optional[int]:
        """
        获取媒体文件大小
        
        Args:
            message: 消息对象
            
        Returns:
            文件大小（字节）
        """
        if message.photo:
            # 照片没有直接的文件大小，返回None
            return None
        elif message.video:
            return message.video.file_size
        elif message.document:
            return message.document.file_size
        elif message.audio:
            return message.audio.file_size
        elif message.voice:
            return message.voice.file_size
        elif message.animation:
            return message.animation.file_size
        elif message.sticker:
            return message.sticker.file_size
        elif message.video_note:
            return message.video_note.file_size
        else:
            return None
    
    def _get_original_filename(self, message: Message) -> Optional[str]:
        """
        获取原始文件名
        
        Args:
            message: 消息对象
            
        Returns:
            原始文件名
        """
        if message.document and message.document.file_name:
            return message.document.file_name
        elif message.video and message.video.file_name:
            return message.video.file_name
        elif message.audio and message.audio.file_name:
            return message.audio.file_name
        elif message.animation and message.animation.file_name:
            return message.animation.file_name
        else:
            return None
    
    def _get_default_extension(self, media_type: str) -> str:
        """
        根据媒体类型获取默认文件扩展名
        
        Args:
            media_type: 媒体类型
            
        Returns:
            默认扩展名
        """
        extension_map = {
            "photo": "jpg",
            "video": "mp4",
            "document": "file",
            "audio": "mp3",
            "voice": "ogg",
            "animation": "mp4",
            "sticker": "webp",
            "video_note": "mp4",
            "unknown": "bin"
        }
        
        return extension_map.get(media_type, "bin")

    async def _iter_messages(self, chat_id: Union[str, int], start_id: int = 0, end_id: int = 0, limit: int = 0):
        """
        迭代获取频道消息，按从旧到新的顺序返回
        
        Args:
            chat_id: 频道ID
            start_id: 起始消息ID
            end_id: 结束消息ID，如果为0则表示获取到最新消息
            limit: 最大消息数量限制
            
        Yields:
            Message: 消息对象，按照从旧到新的顺序
        """
        logger.info(f"调用_iter_messages获取消息: chat_id={chat_id}, start_id={start_id}, end_id={end_id}, limit={limit}")
        
        # 如果start_id有效，但end_id为0，需要获取最新的消息ID
        if start_id > 0 and end_id == 0:
            try:
                # 尝试获取最新的一条消息，以确定最大ID
                async for latest_message in self.client.get_chat_history(chat_id, limit=1):
                    end_id = latest_message.id
                    logger.info(f"已获取最新消息ID: {end_id}，将获取范围设置为 {start_id} 到 {end_id}")
                    break
                
                if end_id == 0:
                    logger.warning(f"无法获取最新消息ID，将仅获取指定限制的消息")
                    # 如果无法获取最新消息ID，使用一个较大的默认值
                    end_id = start_id + (limit if limit > 0 else 1000)
            except Exception as e:
                logger.error(f"获取最新消息ID时出错: {e}")
                if limit <= 0:
                    limit = 50  # 如果没有设置limit，使用一个默认值
        
        # 如果都没设置，使用limit控制获取数量
        if start_id == 0 and end_id == 0 and limit > 0:
            logger.info(f"未指定ID范围，将获取最新的 {limit} 条消息")
            messages = []
            try:
                # 获取最新的消息
                async for message in self.client.get_chat_history(chat_id, limit=limit):
                    messages.append(message)
                
                # 按ID从小到大排序（从旧到新）
                messages.sort(key=lambda msg: msg.id)
                
                logger.info(f"获取到 {len(messages)} 条消息，已按ID从旧到新排序")
                
                # 逐个返回排序后的消息
                for message in messages:
                    yield message
            except Exception as e:
                logger.error(f"获取消息历史时出错: {e}")
            return
        
        # 处理有明确ID范围的情况
        if start_id > 0:
            logger.info(f"按ID范围获取消息: start_id={start_id}, end_id={end_id}")
            
            # 确保start_id小于end_id
            if start_id > end_id and end_id > 0:
                start_id, end_id = end_id, start_id
                logger.info(f"调整ID顺序，现在获取范围为 {start_id} 到 {end_id}")
            
            # 计算需要获取的消息数量
            msg_count = end_id - start_id + 1 if end_id > 0 else (limit if limit > 0 else 1000)
            if limit > 0 and limit < msg_count:
                msg_count = limit
                
            logger.info(f"计划获取约 {msg_count} 条消息")
            
            # 收集所有符合条件的消息
            all_messages = {}  # 使用字典避免重复消息，键为消息ID
            
            # 分批次获取消息，考虑到Telegram API的限制
            batch_size = 100  # 每批次获取的消息数
            
            try:
                # 从最新的消息开始获取，直到获取到start_id
                current_id = end_id + 1 if end_id > 0 else 0
                remaining_attempts = 10  # 最多尝试10次，避免无限循环
                
                while remaining_attempts > 0:
                    batch_messages = []
                    
                    if current_id > 0:
                        logger.info(f"获取小于ID {current_id} 的消息，批次大小 {batch_size}")
                        async for message in self.client.get_chat_history(chat_id, limit=batch_size, offset_id=current_id):
                            batch_messages.append(message)
                    else:
                        logger.info(f"获取最新的 {batch_size} 条消息")
                        async for message in self.client.get_chat_history(chat_id, limit=batch_size):
                            batch_messages.append(message)
                    
                    if not batch_messages:
                        logger.warning(f"未获取到任何消息，可能已到达频道起始位置")
                        break
                    
                    # 找到本批次中最小的消息ID，用于下一次查询
                    min_id_in_batch = min(message.id for message in batch_messages)
                    
                    # 只保留在范围内的消息
                    for message in batch_messages:
                        if start_id <= message.id <= (end_id if end_id > 0 else float('inf')):
                            all_messages[message.id] = message
                    
                    # 判断是否已经获取到足够旧的消息
                    if min_id_in_batch <= start_id:
                        logger.info(f"已获取到起始ID {start_id} 的消息，停止获取")
                        break
                    
                    # 更新下一次获取的起始ID
                    current_id = min_id_in_batch
                    
                    # 检查是否已经获取到足够多的消息（考虑limit限制）
                    if limit > 0 and len(all_messages) >= limit:
                        logger.info(f"已获取到 {len(all_messages)} 条消息，达到限制 {limit}，停止获取")
                        break
                    
                    # 减少尝试次数
                    remaining_attempts -= 1
                    
                    # 添加短暂延迟，避免API限制
                    await asyncio.sleep(0.5)
                
                # 将收集到的消息按ID排序（从旧到新）
                sorted_messages = [all_messages[msg_id] for msg_id in sorted(all_messages.keys())]
                
                # 如果设置了limit，只返回前limit条消息
                if limit > 0 and len(sorted_messages) > limit:
                    sorted_messages = sorted_messages[:limit]
                
                logger.info(f"最终获取到 {len(sorted_messages)} 条消息，ID范围: {sorted_messages[0].id if sorted_messages else 'N/A'} 到 {sorted_messages[-1].id if sorted_messages else 'N/A'}")
                
                # 逐个返回排序后的消息
                for message in sorted_messages:
                    yield message
                    
            except FloodWait as e:
                logger.warning(f"获取消息时触发FloodWait，等待 {e.x} 秒")
                await asyncio.sleep(e.x)
            except Exception as e:
                logger.error(f"获取消息时出错: {e}")
                import traceback
                logger.error(traceback.format_exc()) 

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

    def get_estimated_download_count(self) -> int:
        """
        获取预估的下载文件总数
        
        Returns:
            int: 预估的下载文件总数
        """
        # 获取下载频道列表
        download_settings = self.download_config.get('downloadSetting', [])
        if not download_settings:
            return 0
            
        # 获取全局限制值
        global_limit = self.general_config.get('limit', 50)
        
        # 初始值用于预估，后续会在实际下载过程中更新
        estimated_download_count = 0
        for setting in download_settings:
            start_id = setting.get('start_id', 0)
            end_id = setting.get('end_id', 0)
            
            # 如果指定了start_id但end_id为0，暂时使用全局限制或默认值
            # 实际数量会在下载过程中根据最新消息ID进行调整
            if start_id > 0 and end_id == 0:
                setting_limit = global_limit if global_limit > 0 else 50
            # 如果指定了明确的ID范围
            elif start_id > 0 and end_id > 0:
                setting_limit = abs(end_id - start_id) + 1
                if global_limit > 0 and setting_limit > global_limit:
                    setting_limit = global_limit
            # 没有指定任何ID范围，使用全局限制
            else:
                setting_limit = global_limit if global_limit > 0 else 50
                
            estimated_download_count += setting_limit
        
        logger.info(f"预计总下载消息数估计: {estimated_download_count} 条（初步估计）")
        return estimated_download_count 

    async def _check_directory_size_limit(self) -> Tuple[bool, int, int]:
        """检查下载目录大小是否超过限制
        
        Returns:
            Tuple[bool, int, int]: (是否超过限制, 当前大小(MB), 限制大小(MB))
        """
        try:
            # 获取最新配置
            ui_config = self.ui_config_manager.get_ui_config()
            config = convert_ui_config_to_dict(ui_config)
            download_config = config.get('DOWNLOAD', {})
            
            # 检查是否启用了目录大小限制
            dir_size_limit_enabled = download_config.get('dir_size_limit_enabled', False)
            if not dir_size_limit_enabled:
                return False, 0, 0
                
            # 获取下载路径和大小限制
            download_path = download_config.get('download_path', 'downloads')
            limit_mb = download_config.get('dir_size_limit', 1000)  # 默认1000MB (1GB)
            
            # 计算当前目录大小
            total_size = 0
            path_obj = Path(download_path)
            
            # 检查路径是否存在
            if not path_obj.exists():
                return False, 0, 0
                
            # 遍历目录计算总大小
            for dirpath, dirnames, filenames in os.walk(download_path):
                for filename in filenames:
                    file_path = os.path.join(dirpath, filename)
                    # 跳过符号链接
                    if not os.path.islink(file_path):
                        total_size += os.path.getsize(file_path)
            
            # 转换为MB
            current_size_mb = total_size / (1024 * 1024)
            
            # 检查是否超过限制
            return current_size_mb > limit_mb, int(current_size_mb), limit_mb
        except Exception as e:
            logger.error(f"检查目录大小限制时出错: {e}")
            return False, 0, 0 