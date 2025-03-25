"""
转发器模块
按顺序转发历史消息，处理禁止频道（下载后上传），维护转发记录
"""

import os
import asyncio
import time
import tempfile
import shutil
from typing import List, Dict, Any, Union, Optional, Tuple, Set
from pathlib import Path

from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait, ChatForwardsRestricted

from tg_manager.utils.logger import get_logger
from tg_manager.utils.retry_manager import RetryManager
from tg_manager.services.channel_resolver import ChannelResolver
from tg_manager.services.history_manager import HistoryManager
from tg_manager.core.downloader import Downloader
from tg_manager.core.uploader import Uploader

logger = get_logger("forwarder")


class Forwarder:
    """
    转发器类，用于转发Telegram频道的消息
    """
    
    def __init__(self, 
                 client: Client,
                 channel_resolver: ChannelResolver,
                 history_manager: HistoryManager,
                 downloader: Downloader,
                 uploader: Uploader,
                 tmp_path: str = "tmp",
                 media_types: List[str] = None,
                 remove_captions: bool = False,
                 forward_delay: float = 3.0,
                 max_retries: int = 3,
                 timeout: int = 30):
        """
        初始化转发器
        
        Args:
            client: Pyrogram客户端实例
            channel_resolver: 频道解析器实例
            history_manager: 历史记录管理器实例
            downloader: 下载器实例
            uploader: 上传器实例
            tmp_path: 临时文件存储路径
            media_types: 需要转发的媒体类型列表
            remove_captions: 是否移除原始消息的标题
            forward_delay: 转发延迟（秒）
            max_retries: 转发失败后的最大重试次数
            timeout: 转发超时时间（秒）
        """
        self.client = client
        self.channel_resolver = channel_resolver
        self.history_manager = history_manager
        self.downloader = downloader
        self.uploader = uploader
        self.tmp_path = tmp_path
        self.media_types = media_types or ["photo", "video", "document", "audio", "animation"]
        self.remove_captions = remove_captions
        self.forward_delay = forward_delay
        self.retry_manager = RetryManager(max_retries=max_retries, timeout=timeout)
        
        # 确保临时目录存在
        os.makedirs(tmp_path, exist_ok=True)
    
    async def forward_messages(self, 
                              source_channel: str, 
                              target_channels: List[str],
                              start_id: int = 0, 
                              end_id: int = 0,
                              limit: int = 0) -> Dict[str, Any]:
        """
        转发指定频道的消息到目标频道
        
        Args:
            source_channel: 源频道标识符
            target_channels: 目标频道列表
            start_id: 起始消息ID，0表示从最早的消息开始
            end_id: 结束消息ID，0表示一直转发到最新消息
            limit: 转发消息数量限制，0表示无限制
            
        Returns:
            转发结果统计信息
        """
        logger.info(f"开始从 {source_channel} 转发消息到 {', '.join(target_channels)}, "
                   f"范围: {start_id} - {end_id}, 限制: {limit}")
        
        # 获取源频道信息
        source_info = await self.channel_resolver.get_channel_info(source_channel)
        if not source_info:
            logger.error(f"无法获取源频道信息: {source_channel}")
            return {"status": "failed", "error": "无法获取源频道信息", "forwarded": 0}
        
        # 获取目标频道信息并检查转发权限
        target_infos = {}
        for target in target_channels:
            target_info = await self.channel_resolver.get_channel_info(target)
            if not target_info:
                logger.warning(f"无法获取目标频道信息: {target}，将跳过该频道")
                continue
            target_infos[target] = target_info
        
        if not target_infos:
            logger.error("所有目标频道都无效")
            return {"status": "failed", "error": "所有目标频道都无效", "forwarded": 0}
        
        # 检查源频道是否允许转发
        source_can_forward = source_info.can_forward
        
        # 分类目标频道
        forwardable_targets = []
        non_forwardable_targets = []
        
        for target, info in target_infos.items():
            if info.can_forward:
                forwardable_targets.append(target)
            else:
                non_forwardable_targets.append(target)
        
        logger.info(f"源频道 {source_info.title} ({source_info.channel_id}) 是否允许转发: {source_can_forward}")
        logger.info(f"可转发目标频道: {len(forwardable_targets)}, 不可转发目标频道: {len(non_forwardable_targets)}")
        
        # 转发统计信息
        stats = {
            "total_messages": 0,
            "forwarded": 0,
            "downloaded_then_uploaded": 0,
            "skipped": 0,
            "failed": 0,
            "channels": {}
        }
        
        # 初始化各频道的统计信息
        for target in target_channels:
            if target in target_infos:
                stats["channels"][target] = {
                    "forwarded": 0,
                    "downloaded_then_uploaded": 0,
                    "skipped": 0,
                    "failed": 0
                }
        
        # 已处理的媒体组ID集合，用于跟踪和避免重复处理同一媒体组
        processed_media_groups = set()
        
        # 迭代消息
        try:
            async for message in self.client.get_chat_history(
                source_info.channel_id,
                offset_id=end_id if end_id > 0 else None,
                limit=limit if limit > 0 else None
            ):
                stats["total_messages"] += 1
                
                # 如果设置了起始ID，检查消息ID是否大于等于起始ID
                if start_id > 0 and message.id < start_id:
                    stats["skipped"] += 1
                    continue
                    
                # 如果设置了结束ID，检查消息ID是否小于等于结束ID
                if end_id > 0 and message.id > end_id:
                    stats["skipped"] += 1
                    continue
                
                # 检查媒体类型是否需要转发
                media_type = self._get_media_type(message)
                if media_type not in self.media_types and media_type != "text":
                    logger.debug(f"跳过不支持的媒体类型: {media_type}")
                    stats["skipped"] += 1
                    continue
                
                # 检查媒体组，避免重复处理
                if hasattr(message, 'media_group_id') and message.media_group_id:
                    if message.media_group_id in processed_media_groups:
                        logger.debug(f"跳过已处理的媒体组: {message.media_group_id}")
                        stats["skipped"] += 1
                        continue
                    processed_media_groups.add(message.media_group_id)
                
                # 根据源频道和目标频道的转发权限选择不同的处理方式
                try:
                    # 源频道允许转发，直接转发到目标频道
                    if source_can_forward:
                        await self._forward_message_directly(message, target_infos)
                        stats["forwarded"] += 1
                    
                    # 源频道不允许转发，需要先下载再上传
                    else:
                        # 对于媒体组，获取整个媒体组
                        if hasattr(message, 'media_group_id') and message.media_group_id:
                            media_group_messages = await self._get_media_group_messages(
                                source_info.channel_id, 
                                message.media_group_id
                            )
                            result = await self._download_and_upload_media_group(
                                media_group_messages, 
                                target_infos
                            )
                        else:
                            result = await self._download_and_upload_single_message(
                                message, 
                                target_infos
                            )
                        
                        if result["status"] == "success":
                            stats["downloaded_then_uploaded"] += 1
                        else:
                            stats["failed"] += 1
                    
                    # 更新各频道统计信息
                    for target, target_stats in result.get("channel_stats", {}).items():
                        if target in stats["channels"]:
                            for key, value in target_stats.items():
                                stats["channels"][target][key] += value
                
                except Exception as e:
                    logger.error(f"转发消息 {message.id} 失败: {e}")
                    stats["failed"] += 1
                
                # 添加延迟，避免触发速率限制
                await asyncio.sleep(self.forward_delay)
        
        except Exception as e:
            logger.error(f"获取源频道消息时出错: {e}")
            return {"status": "failed", "error": str(e), "stats": stats}
        
        logger.info(f"转发完成，总计: {stats['total_messages']}, "
                   f"直接转发: {stats['forwarded']}, "
                   f"下载后上传: {stats['downloaded_then_uploaded']}, "
                   f"跳过: {stats['skipped']}, "
                   f"失败: {stats['failed']}")
        
        return {
            "status": "success",
            "source_channel": source_channel,
            "target_channels": target_channels,
            "stats": stats
        }
    
    async def _forward_message_directly(self, 
                                       message: Message, 
                                       target_infos: Dict[str, Any]) -> Dict[str, Any]:
        """
        直接转发消息到目标频道
        
        Args:
            message: Pyrogram消息对象
            target_infos: 目标频道信息字典
            
        Returns:
            转发结果信息
        """
        # 使用实例方法进行重试
        async def forward_message_directly_with_retry():
            result = {
                "status": "success",
                "channel_stats": {}
            }
            
            for target, info in target_infos.items():
                # 检查是否已转发
                if self.history_manager.is_message_forwarded(message.chat.id, message.id, target):
                    logger.debug(f"消息 {message.id} 已转发到 {target}")
                    result["channel_stats"][target] = {"skipped": 1}
                    continue
                
                try:
                    # 处理标题移除选项
                    if self.remove_captions and hasattr(message, 'caption'):
                        # 创建消息副本，移除标题
                        await message.copy(info.channel_id, caption="")
                    else:
                        # 直接转发，保留原标题
                        while True:
                            try:
                                await message.forward(info.channel_id)
                                break
                            except FloodWait as e:
                                logger.warning(f"触发FloodWait，等待 {e.x} 秒")
                                await asyncio.sleep(e.x)
                    
                    # 更新转发历史记录
                    self.history_manager.add_forwarded_message(
                        message.chat.id, 
                        message.id, 
                        target, 
                        real_channel_id=message.chat.id
                    )
                    
                    logger.info(f"成功转发消息 {message.id} 到 {target}")
                    result["channel_stats"][target] = {"forwarded": 1}
                
                except ChatForwardsRestricted:
                    logger.warning(f"频道 {target} 禁止转发，尝试下载后上传")
                    
                    # 更新频道信息缓存
                    info.can_forward = False
                    
                    # 尝试下载后上传
                    if hasattr(message, 'media_group_id') and message.media_group_id:
                        media_group_messages = await self._get_media_group_messages(
                            message.chat.id, 
                            message.media_group_id
                        )
                        single_result = await self._download_and_upload_media_group(
                            media_group_messages, 
                            {target: info}
                        )
                    else:
                        single_result = await self._download_and_upload_single_message(
                            message, 
                            {target: info}
                        )
                    
                    if target in single_result.get("channel_stats", {}):
                        result["channel_stats"][target] = single_result["channel_stats"][target]
                    else:
                        result["channel_stats"][target] = {"failed": 1}
                
                except Exception as e:
                    logger.error(f"转发消息 {message.id} 到 {target} 失败: {e}")
                    result["channel_stats"][target] = {"failed": 1}
            
            return result
            
        # 使用重试管理器执行转发
        try:
            return await self.retry_manager.retry_async(forward_message_directly_with_retry)
        except Exception as e:
            logger.error(f"重试转发消息失败: {e}", exc_info=True)
            return {"status": "failed", "error": str(e), "channel_stats": {}}
    
    async def _get_media_group_messages(self, 
                                       chat_id: int, 
                                       media_group_id: str) -> List[Message]:
        """
        获取媒体组中的所有消息
        
        Args:
            chat_id: 聊天ID
            media_group_id: 媒体组ID
            
        Returns:
            媒体组消息列表
        """
        messages = []
        
        async for msg in self.client.get_chat_history(chat_id, limit=100):
            if (hasattr(msg, 'media_group_id') and 
                msg.media_group_id == media_group_id):
                messages.append(msg)
                
                # 通常媒体组大小不会超过10个消息，如果已收集10个可以停止
                if len(messages) >= 10:
                    break
        
        # 按消息ID排序
        messages.sort(key=lambda m: m.id)
        return messages
    
    async def _download_and_upload_single_message(self, 
                                                message: Message, 
                                                target_infos: Dict[str, Any]) -> Dict[str, Any]:
        """
        下载消息媒体文件后上传到目标频道
        
        Args:
            message: Pyrogram消息对象
            target_infos: 目标频道信息字典
            
        Returns:
            处理结果信息
        """
        result = {
            "status": "success",
            "channel_stats": {}
        }
        
        # 为每个源消息创建临时目录
        temp_dir = os.path.join(self.tmp_path, f"msg_{message.chat.id}_{message.id}")
        os.makedirs(temp_dir, exist_ok=True)
        
        try:
            # 下载媒体文件
            media_type = self._get_media_type(message)
            downloaded_file = None
            
            if media_type != "text":
                # 下载到临时目录
                download_path = await message.download(
                    file_name=os.path.join(temp_dir, f"media_{message.id}")
                )
                downloaded_file = download_path
            
            # 处理各个目标频道
            for target, info in target_infos.items():
                # 检查是否已转发
                if self.history_manager.is_message_forwarded(message.chat.id, message.id, target):
                    logger.debug(f"消息 {message.id} 已转发到 {target}")
                    result["channel_stats"][target] = {"skipped": 1}
                    continue
                
                try:
                    # 根据消息类型上传
                    if media_type == "text":
                        # 发送文本消息
                        await self.client.send_message(
                            info.channel_id, 
                            message.text if hasattr(message, 'text') else ""
                        )
                    
                    elif downloaded_file:
                        # 处理标题
                        caption = None
                        if not self.remove_captions and hasattr(message, 'caption'):
                            caption = message.caption
                        
                        # 上传媒体文件
                        if media_type == "photo":
                            await self.client.send_photo(
                                info.channel_id, 
                                downloaded_file, 
                                caption=caption
                            )
                        
                        elif media_type == "video":
                            await self.client.send_video(
                                info.channel_id, 
                                downloaded_file, 
                                caption=caption
                            )
                        
                        elif media_type == "document":
                            await self.client.send_document(
                                info.channel_id, 
                                downloaded_file, 
                                caption=caption
                            )
                        
                        elif media_type == "audio":
                            await self.client.send_audio(
                                info.channel_id, 
                                downloaded_file, 
                                caption=caption
                            )
                        
                        elif media_type == "animation":
                            await self.client.send_animation(
                                info.channel_id, 
                                downloaded_file, 
                                caption=caption
                            )
                    
                    # 更新转发历史记录
                    self.history_manager.add_forwarded_message(
                        message.chat.id, 
                        message.id, 
                        target, 
                        real_channel_id=message.chat.id
                    )
                    
                    logger.info(f"成功下载并上传消息 {message.id} 到 {target}")
                    result["channel_stats"][target] = {"downloaded_then_uploaded": 1}
                
                except Exception as e:
                    logger.error(f"上传消息 {message.id} 到 {target} 失败: {e}")
                    result["channel_stats"][target] = {"failed": 1}
        
        except Exception as e:
            logger.error(f"下载消息 {message.id} 失败: {e}")
            for target in target_infos:
                result["channel_stats"][target] = {"failed": 1}
            result["status"] = "failed"
        
        finally:
            # 清理临时文件
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                logger.warning(f"清理临时目录失败: {e}")
        
        return result
    
    async def _download_and_upload_media_group(self, 
                                             messages: List[Message], 
                                             target_infos: Dict[str, Any]) -> Dict[str, Any]:
        """
        下载媒体组后上传到目标频道
        
        Args:
            messages: 媒体组消息列表
            target_infos: 目标频道信息字典
            
        Returns:
            处理结果信息
        """
        if not messages:
            return {"status": "failed", "error": "空媒体组", "channel_stats": {}}
        
        result = {
            "status": "success",
            "channel_stats": {}
        }
        
        # 获取媒体组ID
        media_group_id = messages[0].media_group_id if hasattr(messages[0], 'media_group_id') else None
        if not media_group_id:
            logger.warning("无效的媒体组，尝试作为单条消息处理")
            return await self._download_and_upload_single_message(messages[0], target_infos)
        
        # 为媒体组创建临时目录
        temp_dir = os.path.join(self.tmp_path, f"group_{media_group_id}")
        os.makedirs(temp_dir, exist_ok=True)
        
        try:
            # 下载媒体组中的所有文件
            downloaded_files = []
            group_caption = None
            
            for msg in messages:
                # 获取第一个消息的标题作为媒体组标题
                if group_caption is None and hasattr(msg, 'caption') and msg.caption:
                    group_caption = msg.caption
                
                # 下载媒体文件
                download_path = await msg.download(
                    file_name=os.path.join(temp_dir, f"media_{msg.id}")
                )
                
                media_type = self._get_media_type(msg)
                downloaded_files.append({
                    "path": download_path,
                    "type": media_type,
                    "message_id": msg.id
                })
            
            # 处理各个目标频道
            for target, info in target_infos.items():
                # 检查是否已全部转发
                all_forwarded = True
                for msg in messages:
                    if not self.history_manager.is_message_forwarded(msg.chat.id, msg.id, target):
                        all_forwarded = False
                        break
                
                if all_forwarded:
                    logger.debug(f"媒体组 {media_group_id} 已转发到 {target}")
                    result["channel_stats"][target] = {"skipped": len(messages)}
                    continue
                
                try:
                    # 处理标题
                    caption = None if self.remove_captions else group_caption
                    
                    # 准备媒体组
                    media = []
                    for file_info in downloaded_files:
                        file_path = file_info["path"]
                        media_type = file_info["type"]
                        
                        if media_type == "photo":
                            media.append(InputMediaPhoto(file_path))
                        elif media_type == "video":
                            media.append(InputMediaVideo(file_path))
                        elif media_type == "audio":
                            media.append(InputMediaAudio(file_path))
                        else:
                            media.append(InputMediaDocument(file_path))
                    
                    # 为第一个媒体添加标题
                    if media and caption:
                        media[0].caption = caption
                    
                    # 发送媒体组
                    while True:
                        try:
                            await self.client.send_media_group(info.channel_id, media)
                            break
                        except FloodWait as e:
                            logger.warning(f"触发FloodWait，等待 {e.x} 秒")
                            await asyncio.sleep(e.x)
                    
                    # 更新所有消息的转发历史记录
                    for msg in messages:
                        self.history_manager.add_forwarded_message(
                            msg.chat.id, 
                            msg.id, 
                            target, 
                            real_channel_id=msg.chat.id
                        )
                    
                    logger.info(f"成功下载并上传媒体组 {media_group_id} 到 {target}")
                    result["channel_stats"][target] = {"downloaded_then_uploaded": len(messages)}
                
                except Exception as e:
                    logger.error(f"上传媒体组 {media_group_id} 到 {target} 失败: {e}")
                    result["channel_stats"][target] = {"failed": len(messages)}
        
        except Exception as e:
            logger.error(f"下载媒体组 {media_group_id} 失败: {e}")
            for target in target_infos:
                result["channel_stats"][target] = {"failed": len(messages)}
            result["status"] = "failed"
        
        finally:
            # 清理临时文件
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                logger.warning(f"清理临时目录失败: {e}")
        
        return result
    
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
        elif hasattr(message, 'text') and message.text:
            return "text"
        else:
            return "unknown" 