"""
下载器模块
负责下载历史消息的媒体文件，按源频道分类存储，支持断点续传
"""

import os
import asyncio
import time
from typing import List, Dict, Any, Union, Optional, Set
from pathlib import Path

from pyrogram import Client
from pyrogram.types import Message

from tg_manager.utils.logger import get_logger
from tg_manager.utils.retry_manager import RetryManager
from tg_manager.services.channel_resolver import ChannelResolver
from tg_manager.services.history_manager import HistoryManager

logger = get_logger("downloader")


class Downloader:
    """
    下载器类，用于下载Telegram频道的媒体文件
    """
    
    def __init__(self, 
                 client: Client,
                 channel_resolver: ChannelResolver,
                 history_manager: HistoryManager,
                 download_path: str = "downloads",
                 organize_by_chat: bool = True,
                 media_types: List[str] = None,
                 max_retries: int = 3,
                 timeout: int = 300):
        """
        初始化下载器
        
        Args:
            client: Pyrogram客户端实例
            channel_resolver: 频道解析器实例
            history_manager: 历史记录管理器实例
            download_path: 下载文件保存路径
            organize_by_chat: 是否按频道分类保存文件
            media_types: 需要下载的媒体类型列表
            max_retries: 下载失败后的最大重试次数
            timeout: 下载超时时间（秒）
        """
        self.client = client
        self.channel_resolver = channel_resolver
        self.history_manager = history_manager
        self.download_path = download_path
        self.organize_by_chat = organize_by_chat
        self.media_types = media_types or ["photo", "video", "document", "audio", "animation"]
        self.retry_manager = RetryManager(max_retries=max_retries, timeout=timeout)
        
        # 确保下载目录存在
        os.makedirs(download_path, exist_ok=True)
    
    async def download_messages(self, 
                               source_channel: str, 
                               start_id: int = 0, 
                               end_id: int = 0,
                               limit: int = 0,
                               stop_event: Optional[asyncio.Event] = None) -> Dict[str, Any]:
        """
        下载指定频道的消息媒体文件
        
        Args:
            source_channel: 源频道标识符
            start_id: 起始消息ID，0表示从最早的消息开始
            end_id: 结束消息ID，0表示一直下载到最新消息
            limit: 下载消息数量限制，0表示无限制
            stop_event: 停止事件，用于中断下载过程
            
        Returns:
            下载结果统计信息
        """
        logger.info(f"开始从 {source_channel} 下载消息，范围: {start_id} - {end_id}, 限制: {limit}")
        
        try:
            # 获取频道信息
            channel_info = await self.channel_resolver.get_channel_info(source_channel)
            if not channel_info:
                logger.error(f"无法获取频道信息: {source_channel}")
                return {"status": "failed", "error": "无法获取频道信息", "downloaded": 0}
            
            # 创建频道专属下载目录
            chat_download_path = self._get_chat_download_path(channel_info.channel_id, channel_info.username or channel_info.title)
            # 获取已下载的消息ID列表
            downloaded_messages = self.history_manager.get_downloaded_messages(source_channel)
            
            # 下载统计信息
            stats = {
                "total_messages": 0,
                "downloaded": 0,
                "skipped": 0,
                "failed": 0,
                "types": {}
            }
            
            # 准备get_chat_history参数
            history_kwargs = {
                "chat_id": channel_info.channel_id,
                "limit": limit if limit > 0 else None
            }
            
            # 只有当end_id大于0时才添加offset_id参数
            if end_id > 0:
                history_kwargs["offset_id"] = end_id
            
            logger.debug(f"调用get_chat_history，参数: {history_kwargs}")
            message_count = 0
            # 迭代消息
            try:
                async for message in self.client.get_chat_history(**history_kwargs):
                    # 检查是否需要停止
                    if stop_event and stop_event.is_set():
                        logger.info("收到停止信号，中断下载过程")
                        break
                        
                    message_count += 1
                    logger.debug(f"处理第 {message_count} 条消息，ID: {message.id}")
                    stats["total_messages"] += 1
                    
                    # 如果设置了起始ID，检查消息ID是否大于等于起始ID
                    if start_id > 0 and message.id < start_id:
                        stats["skipped"] += 1
                        logger.debug(f"消息ID {message.id} 小于起始ID {start_id}，跳过")
                        continue
                        
                    # 如果设置了结束ID，检查消息ID是否小于等于结束ID
                    if end_id > 0 and message.id > end_id:
                        stats["skipped"] += 1
                        logger.debug(f"消息ID {message.id} 大于结束ID {end_id}，跳过")
                        continue
                    
                    # 检查是否已下载
                    if self.history_manager.is_message_downloaded(source_channel, message.id):
                        logger.debug(f"消息已下载，跳过: {message.id}")
                        stats["skipped"] += 1
                        continue
                    
                    # 下载消息媒体
                    try:
                        # 再次检查停止事件
                        if stop_event and stop_event.is_set():
                            logger.info("收到停止信号，中断下载过程")
                            break
                            
                        logger.debug(f"开始下载消息 {message.id} 的媒体")
                        download_result = await self._download_message_media(message, chat_download_path, stop_event)
                        logger.debug(f"媒体下载结果: {download_result}")
                        
                        if download_result["status"] == "success":
                            # 更新下载历史记录
                            self.history_manager.add_downloaded_message(
                                source_channel, 
                                message.id, 
                                real_channel_id=channel_info.channel_id
                            )
                            stats["downloaded"] += 1
                            logger.info(f"成功下载消息 {message.id}")
                            
                            # 更新媒体类型统计
                            media_type = download_result.get("media_type", "unknown")
                            if media_type in stats["types"]:
                                stats["types"][media_type] += 1
                            else:
                                stats["types"][media_type] = 1
                        else:
                            stats["failed"] += 1
                            logger.warning(f"下载消息 {message.id} 的媒体失败: {download_result.get('reason', '未知原因')}")
                    except Exception as e:
                        logger.error(f"下载消息 {message.id} 失败: {e}", exc_info=True)
                        stats["failed"] += 1
                
                logger.debug(f"消息迭代完成，共处理 {message_count} 条消息")
            except Exception as e:
                logger.error(f"迭代消息时出错: {e}", exc_info=True)
                return {"status": "failed", "error": str(e), "downloaded": stats["downloaded"]}
            
            logger.info(f"下载完成，总计: {stats['total_messages']}, 下载: {stats['downloaded']}, "
                       f"跳过: {stats['skipped']}, 失败: {stats['failed']}")
            
            result = {
                "status": "success",
                "channel": source_channel,
                "stats": stats
            }
            logger.debug(f"返回结果: {result}")
            return result
        except Exception as e:
            logger.error(f"下载消息时发生未处理的异常: {e}", exc_info=True)
            return {"status": "failed", "error": str(e), "downloaded": 0}
    
    async def _download_message_media(self, 
                                     message: Message, 
                                     download_path: str,
                                     stop_event: Optional[asyncio.Event] = None) -> Dict[str, Any]:
        """
        下载消息中的媒体文件
        
        Args:
            message: Pyrogram消息对象
            download_path: 下载文件保存路径
            stop_event: 停止事件，用于中断下载过程
            
        Returns:
            下载结果信息
        """
        # 使用实例方法进行重试
        async def download_media_with_retry():
            # 检查是否需要停止
            if stop_event and stop_event.is_set():
                return {"status": "cancelled", "reason": "user_interrupted"}
            
            # 检查消息是否包含媒体
            if not hasattr(message, 'media') or not message.media:
                return {"status": "skipped", "reason": "no_media"}
            
            media_type = self._get_media_type(message)
            
            # 检查是否是需要下载的媒体类型
            if media_type not in self.media_types:
                return {"status": "skipped", "reason": "media_type_not_in_filter", "media_type": media_type}
            
            # 生成文件名前缀
            prefix = f"{message.id}_"
            
            # 根据媒体类型处理下载
            try:
                if media_type == "photo":
                    # 下载照片
                    file_path = await message.download(
                        file_name=os.path.join(download_path, f"{prefix}photo.jpg")
                    )
                    return {
                        "status": "success",
                        "media_type": "photo",
                        "file_path": file_path,
                        "message_id": message.id
                    }
                
                elif media_type == "video":
                    # 下载视频
                    file_path = await message.download(
                        file_name=os.path.join(download_path, f"{prefix}video.mp4")
                    )
                    return {
                        "status": "success",
                        "media_type": "video",
                        "file_path": file_path,
                        "message_id": message.id
                    }
                
                elif media_type == "document":
                    # 获取原始文件名
                    if hasattr(message.document, 'file_name') and message.document.file_name:
                        filename = message.document.file_name
                        # 确保文件名不包含非法字符
                        filename = self._sanitize_filename(filename)
                        file_path = await message.download(
                            file_name=os.path.join(download_path, f"{prefix}{filename}")
                        )
                    else:
                        file_path = await message.download(
                            file_name=os.path.join(download_path, f"{prefix}document")
                        )
                    
                    return {
                        "status": "success",
                        "media_type": "document",
                        "file_path": file_path,
                        "message_id": message.id
                    }
                
                elif media_type == "audio":
                    # 下载音频
                    if hasattr(message.audio, 'file_name') and message.audio.file_name:
                        filename = message.audio.file_name
                        filename = self._sanitize_filename(filename)
                        file_path = await message.download(
                            file_name=os.path.join(download_path, f"{prefix}{filename}")
                        )
                    else:
                        file_path = await message.download(
                            file_name=os.path.join(download_path, f"{prefix}audio.mp3")
                        )
                    
                    return {
                        "status": "success",
                        "media_type": "audio",
                        "file_path": file_path,
                        "message_id": message.id
                    }
                
                elif media_type == "animation":
                    # 下载GIF/动画
                    file_path = await message.download(
                        file_name=os.path.join(download_path, f"{prefix}animation.mp4")
                    )
                    return {
                        "status": "success",
                        "media_type": "animation",
                        "file_path": file_path,
                        "message_id": message.id
                    }
                
                else:
                    return {"status": "skipped", "reason": "unsupported_media_type", "media_type": media_type}
            
            except Exception as e:
                logger.error(f"下载媒体失败: {e}", exc_info=True)
                return {"status": "failed", "error": str(e), "media_type": media_type}
                
        # 使用重试管理器执行下载
        try:
            return await self.retry_manager.retry_async(download_media_with_retry, stop_event=stop_event)
        except asyncio.CancelledError:
            logger.info("下载操作被取消")
            return {"status": "cancelled", "reason": "operation_cancelled"}
        except Exception as e:
            logger.error(f"重试下载媒体失败: {e}", exc_info=True)
            return {"status": "failed", "error": str(e)}
    
    def _get_media_type(self, message: Message) -> str:
        """
        获取消息的媒体类型
        
        Args:
            message: Pyrogram消息对象
            
        Returns:
            媒体类型字符串
        """
        if hasattr(message, 'photo') and message.photo:
            return "photo"
        elif hasattr(message, 'video') and message.video:
            return "video"
        elif hasattr(message, 'document') and message.document:
            return "document"
        elif hasattr(message, 'audio') and message.audio:
            return "audio"
        elif hasattr(message, 'animation') and message.animation:
            return "animation"
        else:
            return "unknown"
    
    def _get_chat_download_path(self, chat_id: int, chat_name: Optional[str] = None) -> str:
        """
        获取频道的下载路径
        
        Args:
            chat_id: 频道ID
            chat_name: 频道名称，用于创建更易读的目录名
            
        Returns:
            下载路径字符串
        """
        if not self.organize_by_chat:
            return self.download_path
        
        # 使用频道名称或ID创建子目录
        if chat_name:
            # 清理频道名称，确保是有效的文件夹名
            chat_name = self._sanitize_filename(chat_name)
            dir_name = f"{chat_id}_{chat_name}"
        else:
            dir_name = str(chat_id)
        
        chat_path = os.path.join(self.download_path, dir_name)
        os.makedirs(chat_path, exist_ok=True)
        
        return chat_path
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        清理文件名，移除非法字符
        
        Args:
            filename: 原始文件名
            
        Returns:
            清理后的文件名
        """
        # 移除文件名中的非法字符
        illegal_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
        for char in illegal_chars:
            filename = filename.replace(char, '_')
        
        # 限制文件名长度
        if len(filename) > 100:
            name, ext = os.path.splitext(filename)
            filename = name[:100] + ext
        
        return filename 