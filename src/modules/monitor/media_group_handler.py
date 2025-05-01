"""
媒体组处理器模块，负责处理和转发媒体组消息
"""

import asyncio
import time
from typing import List, Dict, Any, Tuple

from pyrogram import Client
from pyrogram.types import (
    Message, InputMediaPhoto, InputMediaVideo, 
    InputMediaDocument, InputMediaAudio, InputMediaAnimation
)
from pyrogram.errors import FloodWait, ChatForwardsRestricted

from src.utils.channel_resolver import ChannelResolver
from src.utils.logger import get_logger
from src.modules.monitor.text_filter import TextFilter

# 导入消息处理器，但避免循环导入
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.modules.monitor.message_processor import MessageProcessor

logger = get_logger()

class MediaGroupHandler:
    """
    媒体组处理器，负责处理和转发媒体组消息
    """
    
    def __init__(self, client: Client, channel_resolver: ChannelResolver, message_processor):
        """
        初始化媒体组处理器
        
        Args:
            client: Pyrogram客户端实例
            channel_resolver: 频道解析器实例
            message_processor: 消息处理器实例
        """
        self.client = client
        self.channel_resolver = channel_resolver
        self.message_processor = message_processor
        
        # 媒体组消息缓存，格式: {channel_id: {media_group_id: {'messages': [Message], 'last_update_time': timestamp}}}
        self.media_group_cache = {}
        # 媒体组处理锁，防止并发处理同一个媒体组
        self.media_group_locks = {}
        # 媒体组超时时间（秒），超过此时间后媒体组将被视为完整并处理
        self.media_group_timeout = 10
        # 媒体组清理任务
        self.media_group_cleanup_task = None
        
        # 频道对应关系配置
        self.channel_pairs = {}
        
        # 停止标志
        self.should_stop = False
    
    def set_channel_pairs(self, channel_pairs: Dict[int, Dict[str, Any]]):
        """
        设置频道对应关系配置
        
        Args:
            channel_pairs: 频道对应关系配置字典
        """
        self.channel_pairs = channel_pairs
    
    def start_cleanup_task(self):
        """启动媒体组清理任务"""
        if self.media_group_cleanup_task is None:
            self.media_group_cleanup_task = asyncio.create_task(self._cleanup_media_groups())
            logger.debug("媒体组清理任务已启动")
    
    async def stop(self):
        """停止媒体组处理器"""
        self.should_stop = True
        
        # 取消媒体组清理任务
        if self.media_group_cleanup_task:
            self.media_group_cleanup_task.cancel()
            try:
                await self.media_group_cleanup_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"取消媒体组清理任务时异常: {str(e)}", error_type="TASK_CANCEL", recoverable=True)
            
            self.media_group_cleanup_task = None
        
        # 清空媒体组缓存
        self.media_group_cache.clear()
        self.media_group_locks.clear()
        logger.info("已清理所有媒体组缓存")
        
    async def _cleanup_media_groups(self):
        """定期检查和处理超时的媒体组"""
        try:
            while not self.should_stop:
                # 每秒检查一次
                await asyncio.sleep(1)
                
                now = time.time()
                channels_to_check = list(self.media_group_cache.keys())
                
                for channel_id in channels_to_check:
                    if channel_id not in self.media_group_cache:
                        continue
                        
                    groups_to_check = list(self.media_group_cache[channel_id].keys())
                    
                    for group_id in groups_to_check:
                        if group_id not in self.media_group_cache.get(channel_id, {}):
                            continue
                            
                        group_data = self.media_group_cache[channel_id][group_id]
                        last_update_time = group_data.get('last_update_time', 0)
                        
                        # 如果媒体组已超时，处理并移除它
                        if now - last_update_time > self.media_group_timeout:
                            try:
                                # 获取锁来处理此媒体组
                                lock_key = f"{channel_id}_{group_id}"
                                if lock_key not in self.media_group_locks:
                                    self.media_group_locks[lock_key] = asyncio.Lock()
                                    
                                async with self.media_group_locks[lock_key]:
                                    # 再次检查媒体组是否仍然存在（可能在获取锁的过程中被其他任务处理）
                                    if (channel_id in self.media_group_cache and 
                                        group_id in self.media_group_cache[channel_id]):
                                        # 获取媒体组和目标频道信息
                                        messages = self.media_group_cache[channel_id][group_id].get('messages', [])
                                        pair_config = self.media_group_cache[channel_id][group_id].get('pair_config')
                                        
                                        if messages and pair_config:
                                            # 处理媒体组消息
                                            logger.info(f"处理超时媒体组: {group_id}, 共有 {len(messages)} 条消息")
                                            await self._process_media_group(messages, pair_config)
                                        
                                        # 从缓存中移除此媒体组
                                        del self.media_group_cache[channel_id][group_id]
                                        
                                        # 如果此频道没有更多媒体组，移除整个频道条目
                                        if not self.media_group_cache[channel_id]:
                                            del self.media_group_cache[channel_id]
                                            
                            except Exception as e:
                                logger.error(f"处理超时媒体组 {group_id} 时出错: {str(e)}", error_type="MEDIA_GROUP_TIMEOUT", recoverable=True)
                                # 尽管出错，仍然尝试从缓存中移除
                                try:
                                    if channel_id in self.media_group_cache and group_id in self.media_group_cache[channel_id]:
                                        del self.media_group_cache[channel_id][group_id]
                                except Exception:
                                    pass
                                
        except asyncio.CancelledError:
            logger.info("媒体组清理任务已取消")
        except Exception as e:
            logger.error(f"媒体组清理任务异常: {str(e)}", error_type="MEDIA_GROUP_CLEANUP", recoverable=True)
            
    async def handle_media_group_message(self, message: Message, pair_config: dict):
        """处理媒体组消息
        
        Args:
            message: 媒体组中的一条消息
            pair_config: 频道对配置
        """
        channel_id = message.chat.id
        media_group_id = message.media_group_id
        
        if not media_group_id:
            logger.warning(f"消息 [ID: {message.id}] 不是媒体组消息")
            return
            
        # 确保频道存在于缓存中
        if channel_id not in self.media_group_cache:
            self.media_group_cache[channel_id] = {}
            
        # 获取锁
        lock_key = f"{channel_id}_{media_group_id}"
        if lock_key not in self.media_group_locks:
            self.media_group_locks[lock_key] = asyncio.Lock()
            
        async with self.media_group_locks[lock_key]:
            # 如果媒体组不存在，创建它
            if media_group_id not in self.media_group_cache[channel_id]:
                self.media_group_cache[channel_id][media_group_id] = {
                    'messages': [],
                    'last_update_time': time.time(),
                    'pair_config': pair_config
                }
                
            # 添加消息到媒体组
            group_data = self.media_group_cache[channel_id][media_group_id]
            messages = group_data['messages']
            
            # 检查消息是否已经在缓存中
            if any(m.id == message.id for m in messages):
                logger.debug(f"媒体组消息 [ID: {message.id}] 已在缓存中，跳过")
                return
                
            # 添加消息并更新时间戳
            messages.append(message)
            group_data['last_update_time'] = time.time()
            
            # 排序媒体组消息（按照ID）
            messages.sort(key=lambda m: m.id)
            
            logger.debug(f"添加消息 [ID: {message.id}] 到媒体组 {media_group_id}, 现有 {len(messages)} 条消息")
            
            # 如果我们接收到了整个媒体组（根据media_group_count），处理它
            if hasattr(message, 'media_group_count') and len(messages) >= message.media_group_count:
                logger.info(f"媒体组 {media_group_id} 已完整接收 ({len(messages)}/{message.media_group_count}), 开始处理")
                await self._process_media_group(messages, pair_config)
                
                # 从缓存中删除此媒体组
                del self.media_group_cache[channel_id][media_group_id]
                
                # 如果此频道没有更多媒体组，移除整个频道条目
                if not self.media_group_cache[channel_id]:
                    del self.media_group_cache[channel_id]
                    
    async def _process_media_group(self, messages: List[Message], pair_config: dict):
        """处理完整的媒体组消息
        
        Args:
            messages: 媒体组消息列表
            pair_config: 频道对配置
        """
        if not messages:
            logger.warning("尝试处理空的媒体组")
            return
            
        # 排序消息，确保顺序正确
        messages.sort(key=lambda m: m.id)
        
        # 获取源和目标信息
        source_chat = messages[0].chat
        source_chat_id = source_chat.id
        media_group_id = messages[0].media_group_id
        
        try:
            source_title = source_chat.title
        except:
            source_title = str(source_chat_id)
            
        target_channels = pair_config.get('target_channels', [])
        text_replacements = pair_config.get('text_replacements', {})
        remove_captions = pair_config.get('remove_captions', False)
        
        if not target_channels:
            logger.warning(f"没有有效的目标频道，跳过媒体组 {media_group_id}")
            return
            
        logger.info(f"开始处理媒体组 {media_group_id} 从 {source_title} 到 {len(target_channels)} 个目标频道")
        
        # 获取第一条消息的标题（如果所有消息共用一个标题，通常是这样）
        caption = ""
        for msg in messages:
            if msg.caption:
                caption = msg.caption
                break
                
        # 检查是否需要修改标题或者应用文本替换
        modified_captions = False
        if text_replacements or remove_captions:
            if caption and text_replacements:
                # 使用TextFilter的静态方法进行文本替换
                modified_caption = TextFilter.apply_text_replacements_static(caption, text_replacements)
                if modified_caption != caption:
                    modified_captions = True
                    caption = modified_caption
                    
            # 如果设置了移除标题
            if remove_captions:
                caption = ""
                modified_captions = True
        
        # 如果需要修改标题，使用send_media_group重新发送媒体组
        if modified_captions:
            logger.info(f"媒体组 {media_group_id} 需要修改标题，将使用修改后的媒体组发送")
            await self._send_modified_media_group(messages, caption, target_channels)
            return
        
        # 如果不需要修改标题，直接尝试转发媒体组（将自动处理转发限制情况）
        await self._forward_media_group(messages, target_channels)
        
    async def _forward_media_group(self, messages: List[Message], target_channels: List[Tuple[str, int, str]]):
        """转发媒体组消息
        
        Args:
            messages: 媒体组消息列表
            target_channels: 目标频道列表
        """
        if not messages or not target_channels:
            return
            
        source_chat = messages[0].chat
        source_chat_id = source_chat.id
        media_group_id = messages[0].media_group_id
        
        try:
            source_title = source_chat.title
        except:
            source_title = str(source_chat_id)
            
        message_ids = [msg.id for msg in messages]
        first_message_id = message_ids[0]
        
        logger.info(f"转发媒体组 {media_group_id} (IDs: {message_ids}) 从 {source_title} 到 {len(target_channels)} 个目标频道")
        
        success_count = 0
        failed_count = 0
        
        # 创建并发任务列表
        tasks = []
        for target, target_id, target_info in target_channels:
            if self.should_stop:
                logger.info(f"任务已停止，中断转发过程")
                break
                
            # 为每个目标频道创建一个异步任务
            tasks.append(self._forward_media_group_to_target(
                source_chat_id, target_id, target_info, 
                first_message_id, message_ids, media_group_id, source_title
            ))
        
        # 并发执行所有转发任务
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 统计结果
            for result in results:
                if isinstance(result, Exception):
                    failed_count += 1
                    logger.error(f"转发媒体组时发生异常: {str(result)}", error_type="FORWARD_MEDIA_GROUP", recoverable=True)
                elif result is True:
                    success_count += 1
                else:
                    failed_count += 1
        
        # 统计结果
        logger.info(f"媒体组 {media_group_id} 转发完成: 成功 {success_count}, 失败 {failed_count}")
        return success_count > 0
        
    async def _forward_media_group_to_target(self, source_chat_id: int, target_id: int, target_info: str,
                                           first_message_id: int, message_ids: List[int], 
                                           media_group_id: str, source_title: str) -> bool:
        """转发媒体组消息到单个目标频道
        
        Args:
            source_chat_id: 源频道ID
            target_id: 目标频道ID
            target_info: 目标频道信息字符串
            first_message_id: 媒体组中第一条消息ID
            message_ids: 所有消息ID列表
            media_group_id: 媒体组ID
            source_title: 源频道标题
            
        Returns:
            bool: 是否成功转发
        """
        try:
            # 优先尝试使用copy_media_group转发整个媒体组
            try:
                await self.client.copy_media_group(
                    chat_id=target_id,
                    from_chat_id=source_chat_id,
                    message_id=first_message_id
                )
                logger.info(f"已将媒体组 {media_group_id} 从 {source_title} 复制到 {target_info}")
                return True
            except ChatForwardsRestricted:
                # 如果复制受限，记录日志并继续尝试其他方式
                logger.warning(f"目标频道 {target_info} 禁止复制消息，尝试逐条转发")
                
                # 尝试单独转发媒体组中的每条消息
                all_succeeded = True
                for msg_id in message_ids:
                    try:
                        await self.client.forward_messages(
                            chat_id=target_id,
                            from_chat_id=source_chat_id,
                            message_ids=msg_id
                        )
                        # 减少延迟，但保留最小间隔避免限流
                        await asyncio.sleep(0.1)
                    except ChatForwardsRestricted:
                        all_succeeded = False
                        logger.warning(f"无法转发媒体组消息 ID:{msg_id} 到 {target_info}，将尝试重新上传")
                        break
                    except FloodWait as e:
                        await asyncio.sleep(e.x)
                        try:
                            await self.client.forward_messages(
                                chat_id=target_id,
                                from_chat_id=source_chat_id,
                                message_ids=msg_id
                            )
                        except Exception:
                            all_succeeded = False
                            break
                    except Exception:
                        all_succeeded = False
                        break
                        
                if all_succeeded:
                    logger.info(f"已将媒体组 {media_group_id} 从 {source_title} 逐条转发到 {target_info}")
                    return True
                
                # 如果转发和复制都失败，尝试重新上传
                logger.info(f"尝试重新上传媒体组 {media_group_id} 到 {target_info}")
                messages = []
                for msg_id in message_ids:
                    try:
                        msg = await self.client.get_messages(source_chat_id, msg_id)
                        if msg:
                            messages.append(msg)
                    except Exception as e:
                        logger.error(f"获取源消息失败: {str(e)}")
                
                if messages:
                    await self._send_modified_media_group(
                        messages, 
                        messages[0].caption or "", 
                        [(None, target_id, target_info)]
                    )
                    logger.info(f"成功重新上传媒体组 {media_group_id} 到 {target_info}")
                    return True
                    
            except FloodWait as e:
                logger.warning(f"触发FloodWait，等待 {e.x} 秒后继续")
                await asyncio.sleep(e.x)
                
                # 重试一次
                await self.client.copy_media_group(
                    chat_id=target_id,
                    from_chat_id=source_chat_id,
                    message_id=first_message_id
                )
                logger.info(f"重试成功：已将媒体组 {media_group_id} 从 {source_title} 发送到 {target_info}")
                return True
                
            except Exception as e:
                # 所有方法都失败，记录错误并返回失败
                logger.error(f"转发媒体组 {media_group_id} 到 {target_info} 失败: {str(e)}", error_type="FORWARD", recoverable=True)
                return False
            
        except Exception as e:
            logger.error(f"处理媒体组转发到 {target_info} 时出错: {str(e)}", error_type="FORWARD_MEDIA_GROUP", recoverable=True)
            return False
    
    async def _send_modified_media_group(self, messages: List[Message], caption: str, target_channels: List[Tuple[str, int, str]]):
        """发送修改后的媒体组消息
        
        Args:
            messages: 媒体组消息列表
            caption: 修改后的标题
            target_channels: 目标频道列表
        """
        if not messages or not target_channels:
            return
            
        source_chat = messages[0].chat
        source_chat_id = source_chat.id
        media_group_id = messages[0].media_group_id
        
        try:
            source_title = source_chat.title
        except:
            source_title = str(source_chat_id)
            
        logger.info(f"发送修改后的媒体组 {media_group_id} 从 {source_title} 到 {len(target_channels)} 个目标频道")
        
        # 准备媒体组 - 使用Pyrogram的媒体类型对象
        media_group = []
        for i, msg in enumerate(messages):
            # 只给第一个媒体添加标题
            current_caption = caption if i == 0 and caption else ""
            
            if msg.photo:
                media_group.append(
                    InputMediaPhoto(
                        media=msg.photo.file_id,
                        caption=current_caption
                    )
                )
            elif msg.video:
                media_group.append(
                    InputMediaVideo(
                        media=msg.video.file_id,
                        caption=current_caption,
                        supports_streaming=True
                    )
                )
            elif msg.document:
                media_group.append(
                    InputMediaDocument(
                        media=msg.document.file_id,
                        caption=current_caption
                    )
                )
            elif msg.audio:
                media_group.append(
                    InputMediaAudio(
                        media=msg.audio.file_id,
                        caption=current_caption
                    )
                )
            elif msg.animation:
                media_group.append(
                    InputMediaAnimation(
                        media=msg.animation.file_id,
                        caption=current_caption
                    )
                )
        
        if not media_group:
            logger.warning(f"无法为媒体组 {media_group_id} 准备媒体内容，跳过发送")
            return
            
        success_count = 0
        failed_count = 0
        
        # 创建并发任务列表
        tasks = []
        for target, target_id, target_info in target_channels:
            if self.should_stop:
                logger.info(f"任务已停止，中断发送过程")
                break
                
            # 为每个目标频道创建一个异步任务
            tasks.append(self._send_media_group_to_target(
                target_id, target_info, media_group, media_group_id, source_title
            ))
        
        # 并发执行所有发送任务
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 统计结果
            for result in results:
                if isinstance(result, Exception):
                    failed_count += 1
                    logger.error(f"发送媒体组时发生异常: {str(result)}", error_type="SEND_MEDIA_GROUP", recoverable=True)
                elif result is True:
                    success_count += 1
                else:
                    failed_count += 1
        
        # 统计结果
        logger.info(f"修改后的媒体组 {media_group_id} 发送完成: 成功 {success_count}, 失败 {failed_count}")
        
    async def _send_media_group_to_target(self, target_id: int, target_info: str, 
                                        media_group: List, media_group_id: str, 
                                        source_title: str) -> bool:
        """发送媒体组到单个目标频道
        
        Args:
            target_id: 目标频道ID
            target_info: 目标频道信息字符串
            media_group: 准备好的媒体组
            media_group_id: 媒体组ID
            source_title: 源频道标题
            
        Returns:
            bool: 是否成功发送
        """
        try:
            # 发送媒体组
            await self.client.send_media_group(
                chat_id=target_id,
                media=media_group
            )
            
            logger.info(f"已将修改后的媒体组 {media_group_id} 从 {source_title} 发送到 {target_info}")
            return True
                
        except FloodWait as e:
            logger.warning(f"触发FloodWait，等待 {e.x} 秒后继续")
            try:
                await asyncio.sleep(e.x)
                # 重试发送
                await self.client.send_media_group(
                    chat_id=target_id,
                    media=media_group
                )
                logger.info(f"重试成功：已将修改后的媒体组 {media_group_id} 从 {source_title} 发送到 {target_info}")
                return True
            except Exception as retry_e:
                logger.error(f"重试发送媒体组失败: {str(retry_e)}", error_type="SEND_RETRY", recoverable=True)
                return False
        
        except Exception as e:
            logger.error(f"发送修改后的媒体组 {media_group_id} 到 {target_info} 失败: {str(e)}", error_type="SEND_MODIFIED", recoverable=True)
            return False 