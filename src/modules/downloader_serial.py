"""
下载模块（顺序下载版本），负责按顺序下载历史消息的媒体文件
"""

import os
import time
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Union, Any, Optional, Set

from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait

from src.utils.config_manager import ConfigManager
from src.utils.channel_resolver import ChannelResolver
from src.utils.history_manager import HistoryManager
from src.utils.logger import get_logger

logger = get_logger()

class DownloaderSerial:
    """
    下载模块（顺序版本），负责按顺序下载历史消息的媒体文件
    """
    
    def __init__(self, client: Client, config_manager: ConfigManager, channel_resolver: ChannelResolver, history_manager: HistoryManager):
        """
        初始化下载模块
        
        Args:
            client: Pyrogram客户端实例
            config_manager: 配置管理器实例
            channel_resolver: 频道解析器实例
            history_manager: 历史记录管理器实例
        """
        self.client = client
        self.config_manager = config_manager
        self.channel_resolver = channel_resolver
        self.history_manager = history_manager
        
        # 获取下载配置
        self.download_config = self.config_manager.get_download_config()
        self.general_config = self.config_manager.get_general_config()
        
        # 创建下载目录
        self.download_path = Path(self.download_config.download_path)
        self.download_path.mkdir(exist_ok=True)
        
        # 是否使用关键词下载模式
        self.use_keywords = False
    
    async def download_media_from_channels(self):
        """
        从配置的源频道下载媒体文件
        """
        mode = "关键词下载" if self.use_keywords else "普通下载"
        logger.info(f"开始从频道下载媒体文件（顺序下载模式 - {mode}）")
        
        # 下载计数
        download_count = 0
        
        # 获取下载设置列表
        download_settings = self.download_config.downloadSetting
        
        if len(download_settings) == 0:
            logger.warning("未配置任何下载设置，请在config.json的DOWNLOAD.downloadSetting数组中添加配置")
            return
            
        logger.info(f"配置的下载设置数量: {len(download_settings)}")
        
        # 遍历每个下载设置
        for setting in download_settings:
            source_channel = setting.source_channels
            start_id = setting.start_id
            end_id = setting.end_id
            media_types = setting.media_types
            keywords = setting.keywords if self.use_keywords else []
            
            if self.use_keywords:
                logger.info(f"准备从频道 {source_channel} 下载媒体文件，关键词: {keywords}")
            else:
                logger.info(f"准备从频道 {source_channel} 下载媒体文件")
            
            download_count = await self._process_channel_for_download(source_channel, start_id, end_id, media_types, keywords, download_count)
        
        logger.info("所有频道的媒体文件下载完成")
    
    async def _process_channel_for_download(self, channel, start_id, end_id, media_types, keywords, download_count):
        """
        处理单个频道的下载流程
        
        Args:
            channel: 频道标识
            start_id: 起始消息ID
            end_id: 结束消息ID
            media_types: 媒体类型列表
            keywords: 关键词列表
            download_count: 当前下载计数
            
        Returns:
            int: 更新后的下载计数
        """
        try:
            # 解析频道ID
            real_channel_id = await self.channel_resolver.get_channel_id(channel)
            # 获取频道信息（现在返回字符串和(标题,ID)元组）
            channel_info, (channel_title, _) = await self.channel_resolver.format_channel_info(real_channel_id)
            logger.info(f"解析频道: {channel_info}")
            
            # 确定目录组织方式
            organize_by_chat = not self.use_keywords
            organize_by_keywords = self.use_keywords
            
            # 确定文件夹名称
            base_folder_name = None
            
            if organize_by_chat:
                # 使用"频道标题-频道ID"格式创建目录
                base_folder_name = f"{channel_title}-{real_channel_id}"
                # 确保文件夹名称有效（移除非法字符）
                base_folder_name = self._sanitize_filename(base_folder_name)
                channel_path = self.download_path / base_folder_name
                channel_path.mkdir(exist_ok=True)
            else:
                # 在关键词模式下，暂时使用下载根目录，后续会根据关键词创建子目录
                channel_path = self.download_path
            
            # 获取已下载的消息ID列表
            downloaded_messages = self.history_manager.get_downloaded_messages(channel)
            logger.info(f"已下载的消息数量: {len(downloaded_messages)}")
            
            # 如果是关键词下载模式，需要先收集所有消息并按媒体组分组
            if self.use_keywords and keywords:
                # 收集所有消息
                all_messages = []
                try:
                    async for message in self._iter_messages(real_channel_id, start_id, end_id):
                        if message.id in downloaded_messages:
                            logger.info(f"消息 {message.id} 已下载，跳过")
                            continue
                        all_messages.append(message)
                except Exception as e:
                    if "PEER_ID_INVALID" in str(e):
                        logger.error(f"无法获取频道 {channel} 的消息: 频道ID无效或未加入该频道")
                        return download_count
                    else:
                        logger.error(f"获取频道 {channel} 的消息失败: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                        return download_count
                
                # 按媒体组分组
                messages_by_group = {}  # 媒体组ID -> 消息列表
                matched_groups = set()  # 匹配关键词的媒体组ID
                matched_keywords = {}   # 媒体组ID -> 匹配的关键词
                
                # 处理收集到的所有消息
                for message in all_messages:
                    # 确定媒体组ID，并确保其为字符串类型
                    group_id = str(message.media_group_id) if message.media_group_id else f"single_{message.id}"
                    
                    # 将消息添加到对应的媒体组
                    if group_id not in messages_by_group:
                        messages_by_group[group_id] = []
                    messages_by_group[group_id].append(message)
                    
                    # 检查消息文本是否包含关键词
                    if group_id not in matched_groups:
                        # 获取消息文本（正文或说明文字）
                        text = message.text or message.caption or ""
                        if text:
                            # 检查文本是否包含任何关键词
                            for keyword in keywords:
                                if keyword.lower() in text.lower():
                                    matched_groups.add(group_id)
                                    matched_keywords[group_id] = keyword
                                    logger.info(f"媒体组 {group_id} (消息ID: {message.id}) 匹配关键词: {keyword}")
                                    break
                
                # 处理每个媒体组
                for group_id, messages in messages_by_group.items():
                    # 如果没有匹配关键词，则跳过整个媒体组
                    if group_id not in matched_groups:
                        logger.debug(f"媒体组 {group_id} 不包含任何关键词，跳过")
                        continue
                    
                    current_channel_path = channel_path
                    
                    # 为该媒体组设置关键词目录
                    if organize_by_keywords and group_id in matched_groups:
                        matched_keyword = matched_keywords[group_id]
                        keyword_folder = self._sanitize_filename(matched_keyword)
                        
                        # 根据频道信息和关键词创建完整路径
                        if base_folder_name:
                            # 如果有频道名称，使用"频道/关键词"的目录结构
                            keyword_path = self.download_path / base_folder_name / keyword_folder
                        else:
                            # 否则直接使用"关键词"目录
                            keyword_path = self.download_path / keyword_folder
                        
                        # 创建关键词目录
                        keyword_path.mkdir(exist_ok=True, parents=True)
                        
                        # 更新当前媒体组的下载路径为关键词目录
                        current_channel_path = keyword_path
                    
                    # 记录日志
                    if group_id.startswith("single_"):
                        logger.info(f"准备下载单条消息: ID={messages[0].id}")
                    else:
                        logger.info(f"准备下载媒体组 {group_id}: 包含 {len(messages)} 条消息, IDs={[m.id for m in messages]}")
                    
                    # 下载媒体组中的所有消息
                    for message in messages:
                        # 检查是否达到限制
                        if self.general_config.limit > 0 and download_count >= self.general_config.limit:
                            logger.info(f"已达到下载限制 {self.general_config.limit}，暂停 {self.general_config.pause_time} 秒")
                            await asyncio.sleep(self.general_config.pause_time)
                            download_count = 0
                        
                        # 下载媒体文件
                        if await self._download_message_media(message, current_channel_path, real_channel_id, media_types):
                            # 添加下载记录
                            self.history_manager.add_download_record(channel, message.id, real_channel_id)
                            download_count += 1
                            
                            # 下载延迟
                            await asyncio.sleep(0.5)
                
                return download_count
            
            else:
                # 普通下载模式，按顺序处理每条消息
                async for message in self._iter_messages(real_channel_id, start_id, end_id):
                    # 检查是否达到限制
                    if self.general_config.limit > 0 and download_count >= self.general_config.limit:
                        logger.info(f"已达到下载限制 {self.general_config.limit}，暂停 {self.general_config.pause_time} 秒")
                        await asyncio.sleep(self.general_config.pause_time)
                        download_count = 0
                    
                    # 检查消息ID是否已下载
                    if message.id in downloaded_messages:
                        logger.info(f"消息 {message.id} 已下载，跳过")
                        continue
                    
                    # 下载媒体文件
                    if await self._download_message_media(message, channel_path, real_channel_id, media_types):
                        # 添加下载记录
                        self.history_manager.add_download_record(channel, message.id, real_channel_id)
                        download_count += 1
                        
                        # 下载延迟
                        await asyncio.sleep(0.5)
                
                return download_count
        
        except Exception as e:
            logger.error(f"处理频道 {channel} 下载失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return download_count
    
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
            logger.error(f"无法获取有效的消息ID范围: chat_id={chat_id}, start_id={start_id}, end_id={end_id}")
            return
            
        # 计算需要获取的消息数量
        total_messages = actual_end_id - actual_start_id + 1
        logger.info(f"开始获取消息: chat_id={chat_id}, 开始id={actual_start_id}, 结束id={actual_end_id}，共{total_messages}条消息")
        
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
                
                logger.info(f"尝试获取消息批次 (第{attempt_count}次): chat_id={chat_id}, offset_id={current_offset_id}, 剩余未获取消息数={len(message_ids_to_fetch)}")
                
                # 记录此批次成功获取的消息数
                batch_success_count = 0
                
                try:
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
                            logger.debug(f"消息ID {message.id} 小于当前需要获取的最小ID {min(message_ids_to_fetch, default=actual_start_id)}，停止当前批次获取")
                            break
                except FloodWait as e:
                    logger.warning(f"获取消息时遇到限制，等待 {e.x} 秒")
                    await asyncio.sleep(e.x)
                    continue
                
                logger.info(f"已获取 {batch_success_count} 条消息，剩余 {len(message_ids_to_fetch)} 条消息待获取")
                
                # 如果此批次没有获取到任何消息，说明可能有些消息不存在或已被删除
                if batch_success_count == 0:
                    # 检查是否需要缩小获取范围，尝试一条一条地获取
                    if batch_size > 1:
                        logger.info(f"未获取到任何消息，尝试减小批次大小")
                        max_batch_size = max(1, max_batch_size // 2)
                    else:
                        # 如果已经是最小批次大小，且仍未获取到消息，记录并移除前一部分消息ID
                        # 这些可能是不存在或已删除的消息
                        if message_ids_to_fetch:
                            ids_to_skip = message_ids_to_fetch[:min(10, len(message_ids_to_fetch))]
                            logger.warning(f"无法获取以下消息ID，可能不存在或已被删除：{ids_to_skip}")
                            for id_to_skip in ids_to_skip:
                                message_ids_to_fetch.remove(id_to_skip)
                
                # 避免频繁请求，休眠一小段时间
                await asyncio.sleep(0.5)
            
            # 检查是否还有未获取的消息
            if message_ids_to_fetch:
                logger.warning(f"以下消息ID无法获取，将被跳过：{message_ids_to_fetch}")
            
            # 将获取到的消息按ID升序排序（从旧到新）
            all_messages = [fetched_messages_map[msg_id] for msg_id in sorted(fetched_messages_map.keys())]
            logger.info(f"消息获取完成，共获取{len(all_messages)}/{total_messages}条消息，已按ID升序排序（从旧到新）")
            
            # 逐个返回排序后的消息
            for message in all_messages:
                yield message
        
        except FloodWait as e:
            logger.warning(f"获取消息时遇到限制，等待 {e.x} 秒")
            await asyncio.sleep(e.x)
        except Exception as e:
            logger.error(f"获取消息失败: {e}")
            logger.exception("详细错误信息")
    
    async def _download_message_media(self, message: Message, download_path: Path, chat_id: int, media_types: List[str]) -> bool:
        """
        下载消息中的媒体文件
        
        Args:
            message: 消息对象
            download_path: 下载路径
            chat_id: 频道ID
            media_types: 媒体类型列表
        
        Returns:
            bool: 是否成功下载
        """
        try:
            # 创建媒体组目录
            media_group_id = str(message.media_group_id) if message.media_group_id else f"single_{message.id}"
            media_group_path = download_path / self._sanitize_filename(media_group_id)
            media_group_path.mkdir(exist_ok=True)
            
            # 保存消息文本到txt文件
            text_content = message.text or message.caption or ""
            if text_content:
                text_file_path = media_group_path / f"{media_group_id}_text.txt"
                # 只有当文件不存在时才写入，避免重复写入相同内容
                if not text_file_path.exists():
                    with open(text_file_path, "w", encoding="utf-8") as f:
                        f.write(text_content)
                    logger.info(f"保存媒体组 {media_group_id} 的文本内容到 {text_file_path}")
            
            if message.photo and "photo" in media_types:
                # 下载照片
                file_path = media_group_path / f"{chat_id}-{message.id}-photo.jpg"
                await self.client.download_media(message, file_name=str(file_path))
                logger.info(f"下载照片成功: {file_path}")
                return True
            
            elif message.video and "video" in media_types:
                # 下载视频
                file_name = message.video.file_name
                if not file_name:
                    file_name = f"{chat_id}-{message.id}-video.mp4"
                file_path = media_group_path / f"{chat_id}-{message.id}-{file_name}"
                await self.client.download_media(message, file_name=str(file_path))
                logger.info(f"下载视频成功: {file_path}")
                return True
            
            elif message.document and "document" in media_types:
                # 下载文档
                file_name = message.document.file_name
                if not file_name:
                    file_name = f"{chat_id}-{message.id}-document"
                file_path = media_group_path / f"{chat_id}-{message.id}-{file_name}"
                await self.client.download_media(message, file_name=str(file_path))
                logger.info(f"下载文档成功: {file_path}")
                return True
            
            elif message.audio and "audio" in media_types:
                # 下载音频
                file_name = message.audio.file_name
                if not file_name:
                    file_name = f"{chat_id}-{message.id}-audio.mp3"
                file_path = media_group_path / f"{chat_id}-{message.id}-{file_name}"
                await self.client.download_media(message, file_name=str(file_path))
                logger.info(f"下载音频成功: {file_path}")
                return True
            
            elif message.animation and "animation" in media_types:
                # 下载动画(GIF)
                file_path = media_group_path / f"{chat_id}-{message.id}-animation.mp4"
                await self.client.download_media(message, file_name=str(file_path))
                logger.info(f"下载动画成功: {file_path}")
                return True
            
            elif message.sticker and "sticker" in media_types:
                # 下载贴纸
                file_path = media_group_path / f"{chat_id}-{message.id}-sticker.webp"
                await self.client.download_media(message, file_name=str(file_path))
                logger.info(f"下载贴纸成功: {file_path}")
                return True
            
            return False
        
        except FloodWait as e:
            logger.warning(f"下载媒体文件时遇到限制，等待 {e.x} 秒")
            await asyncio.sleep(e.x)
            return await self._download_message_media(message, download_path, chat_id, media_types)
        
        except Exception as e:
            logger.error(f"下载消息 {message.id} 的媒体文件失败: {e}")
            return False

    def _sanitize_filename(self, filename: str) -> str:
        """
        清理文件名，移除非法字符
        
        Args:
            filename: 原始文件名
            
        Returns:
            str: 清理后的文件名
        """
        # 替换Windows和UNIX系统中的非法字符
        invalid_chars = r'<>:"/\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename 