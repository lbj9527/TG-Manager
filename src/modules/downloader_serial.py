"""
下载模块（顺序下载版本），负责按顺序下载历史消息的媒体文件
"""

import os
import time
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Union, Any, Optional, Set

from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait

from src.utils.ui_config_manager import UIConfigManager
from src.utils.config_utils import convert_ui_config_to_dict
from src.utils.channel_resolver import ChannelResolver
from src.utils.history_manager import HistoryManager
from src.utils.logger import get_logger


# 仅用于内部调试，不再用于UI输出
logger = get_logger()

class DownloaderSerial():
    """
    下载模块（顺序版本），负责按顺序下载历史消息的媒体文件
    """
    
    def __init__(self, client: Client, ui_config_manager: UIConfigManager, channel_resolver: ChannelResolver, history_manager: HistoryManager):
        """
        初始化下载模块
        
        Args:
            client: Pyrogram客户端实例
            ui_config_manager: UI配置管理器实例
            channel_resolver: 频道解析器实例
            history_manager: 历史记录管理器实例
        """
        self.client = client
        self.ui_config_manager = ui_config_manager
        self.channel_resolver = channel_resolver
        self.history_manager = history_manager
        
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
        
        # 是否使用关键词下载模式
        self.use_keywords = False
    
    async def download_media_from_channels(self):
        """
        从配置的频道下载媒体文件
        """
        
        logger.info("开始从频道下载媒体文件")
        
        # 获取下载频道列表
        download_settings = self.download_config.get('downloadSetting', [])
        logger.info(f"获取到 {len(download_settings)} 个下载设置")
        
        # 详细打印每个下载设置
        for idx, setting in enumerate(download_settings):
            logger.info(f"下载设置 #{idx+1}: 源频道={setting.get('source_channels', '')}, "
                       f"起始ID={setting.get('start_id', 0)}, 结束ID={setting.get('end_id', 0)}, "
                       f"媒体类型={setting.get('media_types', [])}")
        
        if not download_settings:
            logger.error("未配置下载设置，无法开始下载", error_type="CONFIG", recoverable=False)
            return
        
        # 获取全局限制值
        global_limit = self.general_config.get('limit', 50)
        logger.info(f"全局限制值: {global_limit} 条消息")
        
        # 根据最大并发数和每个频道的下载量计算总下载量
        total_download_count = 0
        for setting in download_settings:
            # 获取该频道的下载数量设置，默认为全局配置
            setting_limit = setting.get('start_id') and setting.get('end_id') and abs(setting.get('end_id') - setting.get('start_id')) or global_limit
            total_download_count += setting_limit if setting_limit > 0 else 1000  # 假设默认最多1000条
        
        logger.info(f"预计总下载消息数: {total_download_count} 条")
        
        # 已完成的下载数量
        completed_count = 0
        
        # 遍历所有下载设置
        for setting in download_settings:
            # 获取下载配置
            channel_name = setting.get('source_channels', '')
            start_id = setting.get('start_id', 0)
            end_id = setting.get('end_id', 0)
            
            logger.info(f"处理频道 {channel_name}, 开始ID: {start_id}, 结束ID: {end_id}")
            
            # 计算限制
            limit = abs(end_id - start_id) if start_id and end_id else global_limit
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
                
                # 创建频道专用下载目录
                channel_download_path = download_path / self._sanitize_filename(channel_title)
                channel_download_path.mkdir(parents=True, exist_ok=True)
                
                logger.info(f"下载目录: {channel_download_path}")
                
                # 获取该频道的历史记录
                downloaded_count = 0
                
                # 获取消息
                async for message in self.client.get_chat_history(real_channel_id, limit=limit):        
                    # 检查消息是否包含媒体，且未下载过
                    if message.media:
                        # 检查是否已经下载过该消息的媒体
                        media_id = message.id
                        if self.history_manager.is_message_downloaded(real_channel_id, media_id):
                            logger.debug(f"消息ID: {media_id} 已下载，跳过")
                            continue
                        
                        # 检查文件类型是否符合允许的媒体类型
                        file_type = self._get_media_type(message)
                        media_types = setting.get('media_types', [])
                        if media_types and file_type not in media_types:
                            logger.debug(f"消息ID: {media_id} 的文件类型 {file_type} 不在允许的媒体类型列表中，跳过")
                            continue
                        
                        # 获取文件名
                        file_name = self._generate_filename(message, channel_title)
                        file_path = channel_download_path / file_name
                        
                        # 检查文件是否已存在
                        if file_path.exists():
                            logger.debug(f"文件已存在: {file_path}，跳过下载")
                            # 标记为已下载
                            self.history_manager.add_download_record(real_channel_id, media_id)
                            continue
                        
                        # 下载媒体
                        logger.info(f"正在下载: {file_name}")
                        try:
                            # 开始时间
                            start_time = time.time()
                            
                            # 下载文件
                            download_path = await self.client.download_media(
                                message,
                                file_name=str(file_path),
                                progress=self._download_progress_callback(media_id, file_name)
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
                                
                                # 标记为已下载
                                self.history_manager.add_download_record(real_channel_id, media_id)
                                
                                # 增加下载计数
                                downloaded_count += 1
                                completed_count += 1
                                
                                # 计算进度百分比
                                progress_percentage = (completed_count / total_download_count) * 100 if total_download_count > 0 else 0
                                logger.info(f"总进度: {completed_count}/{total_download_count} ({progress_percentage:.2f}%)")
                            else:
                                logger.error(f"下载失败: {file_name}", error_type="DOWNLOAD_FAIL", recoverable=True)
                        
                        except FloodWait as e:
                            logger.warning(f"下载受限，等待 {e.x} 秒")
                            await asyncio.sleep(e.x)
                            
                        except Exception as e:
                            logger.error(f"下载异常: {str(e)}", error_type="DOWNLOAD_ERROR", recoverable=True)
                    
                    # 检查是否达到限制
                    if limit > 0 and downloaded_count >= limit:
                        logger.info(f"已达到频道 {channel_info_str} 的下载限制 {limit} 条，停止下载")
                        break
                
                # 完成一个频道的下载
                logger.info(f"完成频道 {channel_info_str} 的下载，共下载 {downloaded_count} 个文件")
                
            except Exception as e:
                logger.error(f"处理频道 {channel_name} 时出错: {str(e)}", error_type="CHANNEL_PROCESS", recoverable=True)
                import traceback
                error_details = traceback.format_exc()
                logger.error(error_details)
        
        # 所有频道处理完成
        logger.info(f"所有下载任务完成，共下载 {completed_count} 个文件")
    
    def _download_progress_callback(self, message_id, file_name):
        """
        创建下载进度回调函数
        
        Args:
            message_id: 消息ID
            file_name: 文件名
            
        Returns:
            下载进度回调函数
        """
        start_time = time.time()
        last_percentage = 0
        
        async def progress(current, total):
            nonlocal start_time, last_percentage           
            # 计算百分比
            if total > 0:
                percentage = int((current / total) * 100)
                
                # 只在百分比变化较大时更新进度
                if percentage - last_percentage >= 5 or percentage == 100:
                    last_percentage = percentage
                    
                    # 计算下载速度
                    elapsed_time = time.time() - start_time
                    if elapsed_time > 0:
                        speed = current / elapsed_time / 1024  # KB/s
                        
                        # 格式化显示
                        if speed < 1024:
                            speed_text = f"{speed:.2f} KB/s"
                        else:
                            speed_text = f"{speed/1024:.2f} MB/s"
                        
                        # 计算剩余时间
                        if current > 0:
                            remaining_time = (total - current) / (current / elapsed_time)
                            mins, secs = divmod(remaining_time, 60)
                            time_text = f"{int(mins)}分{int(secs)}秒"
                        else:
                            time_text = "计算中..."
                        
                        # 日志显示进度
                        logger.debug(
                            f"下载进度: {file_name} - {percentage}% ({current/1024/1024:.2f}MB/{total/1024/1024:.2f}MB) {speed_text} 剩余: {time_text}")
        
        return progress
    
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