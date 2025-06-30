"""
并行处理器，用于并行下载和上传媒体组
"""

import asyncio
import os
import time
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Any, Optional, Set, AsyncGenerator

from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait

from src.modules.forward.media_group_download import MediaGroupDownload
from src.modules.forward.message_downloader import MessageDownloader
from src.modules.forward.media_uploader import MediaUploader
from src.modules.forward.media_group_collector import MediaGroupCollector
from src.modules.forward.message_filter import MessageFilter
from src.utils.logger import get_logger
from src.utils.flood_wait_handler import FloodWaitHandler, execute_with_flood_wait

_logger = get_logger()

class ParallelProcessor:
    """
    并行处理器，负责并行下载和上传媒体组
    实现生产者-消费者模式
    """
    
    def __init__(self, client: Client, history_manager=None, general_config: Dict[str, Any] = None, config: Dict[str, Any] = None):
        """
        初始化并行处理器
        
        Args:
            client: Pyrogram客户端实例
            history_manager: 历史记录管理器实例
            general_config: 通用配置
            config: 完整配置，用于初始化MessageFilter
        """
        self.client = client
        self.history_manager = history_manager
        self.general_config = general_config or {}
        
        # 初始化消息过滤器
        self.message_filter = MessageFilter(config or {})
        
        # 初始化停止标志
        self.should_stop = False
        
        # 创建媒体组队列
        self.media_group_queue = asyncio.Queue()
        
        # 生产者-消费者控制
        self.download_running = False
        self.upload_running = False
        self.producer_task = None
        self.consumer_task = None
        
        # 初始化下载和上传组件
        self.message_downloader = MessageDownloader(client)
        self.media_uploader = MediaUploader(client, history_manager, general_config)
        self.flood_wait_handler = FloodWaitHandler(max_retries=3, base_delay=1.0)
    
    async def process_parallel_download_upload(self, 
                                       source_channel: str, 
                                       source_id: int, 
                                       media_groups_info: List[Tuple[str, List[int]]], 
                                       temp_dir: Path,
                                       target_channels: List[Tuple[str, int, str]],
                                       pair_config: Dict[str, Any] = None) -> int:
        """
        并行处理媒体组下载和上传
        
        Args:
            source_channel: 源频道标识符
            source_id: 源频道ID
            media_groups_info: 媒体组信息列表[(group_id, [message_ids])]
            temp_dir: 临时下载目录
            target_channels: 目标频道列表，用于检查是否已转发
            pair_config: 频道对配置，包含过滤规则等
            
        Returns:
            int: 实际转发的媒体组数量
        """
        forward_count = 0
        try:
            # 设置下载和上传标志
            self.download_running = True
            self.upload_running = True
            
            _logger.info("开始并行下载和上传媒体组...")
            
            # 创建生产者和消费者任务
            producer_task = asyncio.create_task(
                self._producer_download_media_groups_parallel(
                    source_channel, source_id, media_groups_info, temp_dir, target_channels, pair_config
                )
            )
            consumer_task = asyncio.create_task(
                self._consumer_upload_media_groups(target_channels)
            )
            
            self.producer_task = producer_task
            self.consumer_task = consumer_task
            
            # 等待生产者和消费者任务完成
            producer_result = await producer_task
            _logger.info("下载任务完成，等待所有上传完成...")
            
            # 发送结束信号
            await self.media_group_queue.put(None)
            
            # 等待消费者任务完成
            consumer_result = await consumer_task
            
            # 重置任务引用
            self.producer_task = None
            self.consumer_task = None
            
            # 计算实际转发的数量
            if isinstance(producer_result, int):
                forward_count = producer_result
            
            _logger.info(f"媒体组下载和上传任务完成，共转发 {forward_count} 个媒体组")
            
        except Exception as e:
            _logger.error(f"下载和上传任务失败: {str(e)}")
            import traceback
            error_details = traceback.format_exc()
            _logger.error(error_details)
            
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
            
            raise
        
        return forward_count
    
    async def _get_message_with_flood_wait(self, source_id: int, message_id: int) -> Optional[Message]:
        """
        使用FloodWait处理器获取消息
        
        Args:
            source_id: 源频道ID
            message_id: 消息ID
            
        Returns:
            Optional[Message]: 获取到的消息对象，失败返回None
        """
        async def get_message():
            return await self.client.get_messages(source_id, message_id)
        
        return await execute_with_flood_wait(get_message, max_retries=3)
    
    async def _producer_download_media_groups_parallel(self, 
                                                 source_channel: str, 
                                                 source_id: int, 
                                                 media_groups_info: List[Tuple[str, List[int]]], 
                                                 temp_dir: Path,
                                                 target_channels: List[Tuple[str, int, str]],
                                                 pair_config: Dict[str, Any] = None) -> int:
        """
        生产者：并行下载媒体组
        
        Args:
            source_channel: 源频道标识符
            source_id: 源频道ID
            media_groups_info: 媒体组信息列表[(group_id, [message_ids])]
            temp_dir: 临时下载目录
            target_channels: 目标频道列表，用于检查是否已转发
            pair_config: 频道对配置，包含过滤规则等
            
        Returns:
            int: 实际转发的媒体组数量
        """
        try:
            forward_count = 0
            total_groups = len(media_groups_info)
            processed_groups = 0
            
            _logger.info(f"开始并行下载 {total_groups} 个媒体组")
            
            for group_id, message_ids in media_groups_info:
                # 检查是否收到停止信号
                if self.should_stop or not self.download_running:
                    _logger.info("收到停止信号，终止下载任务")
                    break
                    
                try:   
                    # 更新进度
                    processed_groups += 1
                    progress_percentage = (processed_groups / total_groups) * 100
                    
                    # 检查是否已全部转发
                    all_forwarded = True
                    forwarded_targets = []
                    not_forwarded_targets = []
                    
                    for target_channel, target_id, target_info in target_channels:
                        target_all_forwarded = True
                        for message_id in message_ids:
                            if not self.history_manager or not self.history_manager.is_message_forwarded(source_channel, message_id, target_channel):
                                target_all_forwarded = False
                                all_forwarded = False
                                break
                        
                        if target_all_forwarded:
                            forwarded_targets.append(target_info)
                        else:
                            not_forwarded_targets.append(target_info)
                    
                    if all_forwarded:
                        _logger.info(f"媒体组 {group_id} (消息IDs: {message_ids}) 已转发到所有目标频道，跳过")
                        continue
                    elif forwarded_targets:
                        _logger.info(f"媒体组 {group_id} (消息IDs: {message_ids}) 已部分转发: 已转发到 {forwarded_targets}, 未转发到 {not_forwarded_targets}")
                    
                    # 检查是否达到限制
                    if self.general_config.get('limit', 0) > 0 and forward_count >= self.general_config.get('limit', 0):
                        _logger.info(f"已达到转发限制 {self.general_config.get('limit', 0)}，暂停 {self.general_config.get('pause_time', 60)} 秒")
                        await asyncio.sleep(self.general_config.get('pause_time', 60))
                        forward_count = 0
                    
                    # 为每个媒体组创建安全的目录名
                    # 将媒体组ID转为字符串，并替换可能的非法路径字符
                    safe_group_id = self._get_safe_path_name(str(group_id))
                    
                    # 为每个媒体组创建单独的下载目录
                    group_dir = temp_dir / safe_group_id
                    group_dir.mkdir(exist_ok=True)
                    
                    # 获取完整消息对象
                    messages = []
                    _logger.info(f"正在获取媒体组 {group_id} 的 {len(message_ids)} 条消息")
                    
                    for message_id in message_ids:
                        try:                 
                            message = await self._get_message_with_flood_wait(source_id, message_id)
                            if message:
                                messages.append(message)
                                _logger.debug(f"获取消息 {message_id} 成功")
                        except Exception as e:
                            _logger.error(f"获取消息 {message_id} 失败: {e}")
                    
                    if not messages:
                        _logger.warning(f"媒体组 {group_id} 没有获取到有效消息，跳过")
                        continue
                    
                    # 获取媒体组文本信息（优先使用Forwarder传递的预提取文本）
                    media_group_texts = {}
                    if pair_config and 'media_group_texts' in pair_config:
                        # 优先使用Forwarder传递的媒体组文本信息（避免重复过滤导致文本丢失）
                        media_group_texts = pair_config.get('media_group_texts', {})
                        _logger.debug(f"🔍 ParallelProcessor接收到Forwarder传递的媒体组文本: {len(media_group_texts)} 个")
                        # for group_id, text in media_group_texts.items():
                        #     _logger.debug(f"  媒体组 {group_id}: '{text[:50]}...'")
                    elif pair_config and messages:
                        # 如果没有预传递的文本信息，才重新提取（备用方案）
                        media_group_texts = self.message_filter._extract_media_group_texts(messages)
                        _logger.debug(f"媒体组 {group_id} 重新提取媒体组文本: {len(media_group_texts)} 个")
                    
                    # 使用MediaGroupCollector传入的已过滤消息
                    filtered_messages = messages
                    _logger.debug(f"媒体组 {group_id} 使用已过滤消息: {len(filtered_messages)} 条")
                    
                    # 下载媒体文件（使用过滤后的消息）
                    _logger.info(f"正在下载媒体组 {group_id} 的 {len(filtered_messages)} 条媒体消息")
                    
                    downloaded_files = await self.message_downloader.download_messages(filtered_messages, group_dir, source_id)
                    if not downloaded_files:
                        _logger.warning(f"媒体组 {group_id} 没有媒体文件可下载，跳过")
                        continue
                    
                    # 获取消息文本（优先使用媒体组文本映射）
                    caption = None
                    
                    # 如果有媒体组文本映射，优先使用
                    if media_group_texts:
                        # 尝试多种方式匹配媒体组文本
                        for message in filtered_messages:
                            if message.media_group_id:
                                # 尝试直接使用数字形式的media_group_id
                                if message.media_group_id in media_group_texts:
                                    caption = media_group_texts[message.media_group_id]
                                    _logger.debug(f"✅ 使用预提取的媒体组文本(数字ID): '{caption[:50]}...'")
                                    break
                                # 尝试使用字符串形式的media_group_id
                                elif str(message.media_group_id) in media_group_texts:
                                    caption = media_group_texts[str(message.media_group_id)]
                                    _logger.debug(f"✅ 使用预提取的媒体组文本(字符串ID): '{caption[:50]}...'")
                                    break
                        
                        # 如果单个消息，尝试使用single_格式的ID
                        if not caption and len(filtered_messages) == 1:
                            single_id = f"single_{filtered_messages[0].id}"
                            if single_id in media_group_texts:
                                caption = media_group_texts[single_id]
                                _logger.debug(f"✅ 使用预提取的单条消息文本: '{caption[:50]}...'")
                    
                    # 如果没有找到媒体组文本，回退到原有逻辑
                    if not caption:
                        for message in filtered_messages:
                            if message.caption or message.text:
                                caption = message.caption or message.text
                                _logger.debug(f"⚠️ 未找到预提取文本，使用过滤后消息的文本: '{caption[:50] if caption else 'None'}...'")
                                break
                    
                    # 应用文本替换规则
                    if caption and pair_config:
                        text_replacements = pair_config.get('text_replacements', {})
                        if text_replacements and isinstance(text_replacements, dict):
                            original_caption = caption
                            caption, has_replacement = self.message_filter.apply_text_replacements(caption, text_replacements)
                            if has_replacement:
                                _logger.info(f"媒体组 {group_id} 文本替换: '{original_caption[:30]}...' -> '{caption[:30]}...'")
                    
                    # 检查是否移除标题
                    remove_captions = False
                    if pair_config:
                        remove_captions = pair_config.get('remove_captions', False)
                    else:
                        remove_captions = self.general_config.get('remove_captions', False)
                    
                    if remove_captions:
                        caption = None
                        _logger.debug(f"媒体组 {group_id} 根据配置移除了标题")
                    
                    # 创建媒体组下载结果对象（使用过滤后的消息）
                    media_group_download = MediaGroupDownload(
                        source_channel=source_channel,
                        source_id=source_id,
                        messages=filtered_messages,
                        download_dir=group_dir,
                        downloaded_files=downloaded_files,
                        caption=caption
                    )
                    
                    # 将下载完成的媒体组放入队列
                    _logger.info(f"媒体组 {group_id} 下载完成，放入上传队列: 消息IDs={[m.id for m in filtered_messages]}")
                    
                    await self.media_group_queue.put(media_group_download)
                    
                    forward_count += 1
                    
                    # 添加适当的延迟，避免API限制
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    _logger.error(f"处理媒体组 {group_id} 失败: {str(e)}")
                    import traceback
                    error_details = traceback.format_exc()
                    _logger.error(error_details)
                    continue
                    
        except Exception as e:
            _logger.error(f"生产者并行下载任务异常: {str(e)}")
            import traceback
            error_details = traceback.format_exc()
            _logger.error(error_details)
        finally:
            self.download_running = False
            _logger.info(f"生产者(下载)任务结束，共处理 {forward_count} 个媒体组")
        
        return forward_count
    
    async def _consumer_upload_media_groups(self, target_channels: List[Tuple[str, int, str]]):
        """
        消费者：上传媒体组到目标频道
        
        Args:
            target_channels: 目标频道列表(频道标识符, 频道ID, 频道信息)
        """
        try:
            # 记录上传计数
            uploaded_count = 0
            copied_count = 0
            failed_count = 0
            
            _logger.info("开始上传媒体组到目标频道")
            
            while True:         
                # 检查是否收到停止信号
                if self.should_stop or not self.upload_running:
                    _logger.info("收到停止信号，终止上传任务")
                    break
                    
                # 从队列获取下一个媒体组
                try:
                    media_group_download = await asyncio.wait_for(
                        self.media_group_queue.get(), 
                        timeout=5.0
                    )
                except asyncio.TimeoutError:
                    # 每5秒检查一次是否应该退出
                    if not self.download_running and self.media_group_queue.empty():
                        _logger.info("下载任务已完成且队列为空，上传任务准备退出")
                        break
                    continue
                
                # 检查是否结束信号
                if media_group_download is None:
                    _logger.info("收到结束信号，消费者准备退出")
                    break
                
                try:
                    # 记录媒体组的目录，以便上传后删除
                    media_group_dir = media_group_download.download_dir
                    message_ids = [m.id for m in media_group_download.messages]
                    source_channel = media_group_download.source_channel
                    
                    # 记录媒体组信息
                    group_id = "单条消息" if len(message_ids) == 1 else f"媒体组(共{len(message_ids)}条)"
                    # _logger.info(f"开始处理{group_id}: 消息IDs={message_ids}, 来源={source_channel}")
                    
                    # 提前检查哪些频道已经转发过
                    forwarded_targets = []
                    not_forwarded_targets = []
                    
                    for target_channel, _, target_info in target_channels:
                        all_forwarded = True
                        for message in media_group_download.messages:
                            if not self.history_manager or not self.history_manager.is_message_forwarded(media_group_download.source_channel, message.id, target_channel):
                                all_forwarded = False
                                break
                        
                        if all_forwarded:
                            forwarded_targets.append(target_info)
                        else:
                            not_forwarded_targets.append(target_info)
                    
                    if forwarded_targets:
                        _logger.info(f"{group_id} {message_ids} 已转发到: {forwarded_targets}")
                    
                    if not not_forwarded_targets:
                        _logger.info(f"{group_id} {message_ids} 已转发到所有目标频道，跳过上传")
                        # 清理已全部转发的媒体组目录
                        self.media_uploader.cleanup_media_group_dir(media_group_dir)
                        self.media_group_queue.task_done()
                        continue
                    
                    # 为视频文件生成缩略图
                    thumbnails = await self.media_uploader.generate_thumbnails_parallel(media_group_download)
                    
                    # 准备媒体组上传
                    media_group = await self.media_uploader.prepare_media_group_for_upload_parallel(media_group_download, thumbnails)
                    
                    if not media_group:
                        _logger.warning(f"媒体组 {group_id} {message_ids} 没有有效的媒体文件可上传（可能所有文件都是0字节），跳过这个媒体组")
                        # 清理空目录
                        self.media_uploader.cleanup_media_group_dir(media_group_dir)
                        self.media_group_queue.task_done()
                        continue
                    
                    # 标记是否所有目标频道都已上传成功
                    all_targets_uploaded = True
                    remaining_targets = not_forwarded_targets.copy()
                    uploaded_targets = []
                    
                    # 计算总目标频道数量，用于进度计算
                    total_targets = len(not_forwarded_targets)
                    current_target = 0
                    
                    # 记录第一次上传成功的频道ID和消息IDs，用于后续复制
                    first_upload_channel_id = None
                    first_upload_messages = []  # 存储上传成功的消息对象
                    is_media_group = len(media_group) > 1
                    
                    # 依次上传到需要转发的目标频道
                    for target_channel, target_id, target_info in target_channels:    
                        # 检查是否收到停止信号
                        if self.should_stop or not self.upload_running:
                            _logger.info("收到停止信号，终止目标频道上传")
                            break
                            
                        # 检查是否已转发到此频道
                        all_forwarded = True
                        for message in media_group_download.messages:
                            if not self.history_manager or not self.history_manager.is_message_forwarded(media_group_download.source_channel, message.id, target_channel):
                                all_forwarded = False
                                break
                        
                        if all_forwarded:
                            _logger.debug(f"{group_id} {message_ids} 已转发到频道 {target_info}，跳过")
                            continue
                        
                        # 更新当前目标进度
                        current_target += 1
                        progress_percentage = (current_target / total_targets) * 100
                        
                        # 检查是否可以使用copy方式转发
                        if first_upload_channel_id is not None and first_upload_messages:
                            try:
                                _logger.info(f"尝试从已上传频道复制{group_id} {message_ids} 到 {target_info}")
                                
                                # 使用FloodWait处理器执行复制操作
                                async def copy_operation():
                                    if is_media_group:
                                        # 媒体组使用copy_media_group方法
                                        # 只需要第一条消息的ID，因为copy_media_group会自动找到其他消息
                                        first_message = first_upload_messages[0]
                                        copied_msgs = await self.client.copy_media_group(
                                            chat_id=target_id,
                                            from_chat_id=first_upload_channel_id,
                                            message_id=first_message.id
                                        )
                                        return copied_msgs
                                    else:
                                        # 单条消息使用copy_message方法
                                        first_message = first_upload_messages[0]
                                        copied_msg = await self.client.copy_message(
                                            chat_id=target_id,
                                            from_chat_id=first_upload_channel_id,
                                            message_id=first_message.id
                                        )
                                        return copied_msg
                                
                                copy_result = await execute_with_flood_wait(copy_operation, max_retries=3)
                                
                                if copy_result is not None:
                                    # 记录转发历史
                                    if self.history_manager:
                                        for message in media_group_download.messages:
                                            self.history_manager.add_forward_record(
                                                media_group_download.source_channel,
                                                message.id,
                                                target_channel,
                                                media_group_download.source_id
                                            )
                                    
                                    _logger.info(f"成功从已上传频道复制{group_id}到 {target_info}")
                                    copied_count += 1
                                    
                                    if target_info in remaining_targets:
                                        remaining_targets.remove(target_info)
                                        uploaded_targets.append(target_info)
                                    
                                    # 添加短暂延迟，避免频繁API调用
                                    await asyncio.sleep(0.5)
                                    continue
                                else:
                                    _logger.warning(f"从已上传频道复制失败，将尝试直接上传")
                                
                            except Exception as copy_error:
                                _logger.warning(f"从已上传频道复制失败，将尝试直接上传: {copy_error}")
                                # 复制失败，回退到正常上传流程
                        
                        # 上传到目标频道
                        _logger.info(f"上传{group_id} {message_ids} 到频道 {target_info}")
                        success = False
                        upload_result = await self.media_uploader.upload_media_group_to_channel(
                            media_group, 
                            media_group_download, 
                            target_channel, 
                            target_id, 
                            target_info,
                            thumbnails
                        )
                        
                        # upload_result可能是布尔值或消息对象列表
                        if isinstance(upload_result, list):
                            # 上传成功并返回了消息对象
                            sent_messages = upload_result
                            success = True
                            
                            # 如果这是第一次成功上传，保存频道ID和消息对象用于后续复制
                            if first_upload_channel_id is None:
                                first_upload_channel_id = target_id
                                first_upload_messages = sent_messages
                                _logger.info(f"已保存第一次上传成功的消息，用于后续复制转发")
                        elif upload_result:
                            # 上传成功但没有返回消息对象
                            success = True
                        
                        if success:
                            if target_info in remaining_targets:
                                remaining_targets.remove(target_info)
                                uploaded_targets.append(target_info)
                            uploaded_count += 1
                        else:
                            all_targets_uploaded = False
                            failed_count += 1
                            
                    # 媒体组上传完成后（无论成功失败），都清理缩略图
                    self.media_uploader.cleanup_thumbnails(thumbnails)
                    
                    # 媒体组上传完成后，清理媒体组的本地文件
                    if all_targets_uploaded:
                        _logger.info(f"{group_id} {message_ids} 已成功上传到所有目标频道，清理本地文件: {media_group_dir}")
                        self.media_uploader.cleanup_media_group_dir(media_group_dir)
                    else:
                        _logger.warning(f"{group_id} {message_ids} 未能成功上传到所有目标频道，仍有 {remaining_targets} 未转发完成，保留本地文件: {media_group_dir}")
                
                except Exception as e:
                    _logger.error(f"处理媒体组上传失败: {str(e)}")
                    import traceback
                    error_details = traceback.format_exc()
                    _logger.error(error_details)
                finally:
                    # 标记此项为处理完成
                    self.media_group_queue.task_done()
        
        except asyncio.CancelledError:
            _logger.warning("消费者任务被取消")
        except Exception as e:
            _logger.error(f"消费者任务异常: {str(e)}")
            import traceback
            error_details = traceback.format_exc()
            _logger.error(error_details)
        finally:
            self.upload_running = False
            _logger.info(f"消费者(上传)任务结束，共上传 {uploaded_count} 个媒体组，复制 {copied_count} 个，失败 {failed_count} 个")
    
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