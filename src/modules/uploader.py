"""
上传模块，负责将本地文件上传到目标频道
"""

import os
import time
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Union, Any, Optional, Tuple
import mimetypes

from pyrogram import Client
from pyrogram.types import InputMediaPhoto, InputMediaVideo, InputMediaDocument, InputMediaAudio, Message
from pyrogram.errors import FloodWait, MediaEmpty, MediaInvalid

from src.utils.ui_config_manager import UIConfigManager
from src.utils.config_utils import convert_ui_config_to_dict
from src.utils.channel_resolver import ChannelResolver
from src.utils.history_manager import HistoryManager
from src.utils.logger import get_logger
from src.utils.video_processor import VideoProcessor

# 仅用于内部调试，不再用于UI输出
logger = get_logger()

class Uploader():
    """
    上传模块，负责将本地文件上传到目标频道
    """
    
    def __init__(self, client: Client, ui_config_manager: UIConfigManager, channel_resolver: ChannelResolver, history_manager: HistoryManager):
        """
        初始化上传模块
        
        Args:
            client: Pyrogram客户端实例
            ui_config_manager: UI配置管理器实例
            channel_resolver: 频道解析器实例
            history_manager: 历史记录管理器实例
        """
        # 初始化事件发射器
        super().__init__()
        
        self.client = client
        self.ui_config_manager = ui_config_manager
        self.channel_resolver = channel_resolver
        self.history_manager = history_manager
        
        # 获取UI配置并转换为字典
        ui_config = self.ui_config_manager.get_ui_config()
        self.config = convert_ui_config_to_dict(ui_config)
        
        # 获取上传配置和通用配置
        self.upload_config = self.config.get('UPLOAD', {})
        self.general_config = self.config.get('GENERAL', {})
        
        # 初始化MIME类型
        mimetypes.init()
        
        # 初始化视频处理器
        self.video_processor = VideoProcessor()
        
        # 任务控制 - 移除TaskContext类型的引用
        self.is_cancelled = False
        self.is_paused = False
    
    async def upload_local_files(self, task_context=None):
        """
        上传本地文件到目标频道
        
        Args:
            task_context: 移除了任务上下文参数类型
        """
        # 初始化状态
        self.is_cancelled = False
        self.is_paused = False
        
        status_message = "开始上传本地文件到目标频道"
        logger.info(status_message)
        
        # 获取目标频道列表
        target_channels = self.upload_config.get('target_channels', [])
        if not target_channels:
            logger.error("未配置目标频道，无法上传文件", error_type="CONFIG", recoverable=False)
            return
        
        logger.info(f"配置的目标频道数量: {len(target_channels)}")
        
        # 获取上传目录
        upload_dir = Path(self.upload_config.get('directory', 'uploads'))
        if not upload_dir.exists() or not upload_dir.is_dir():
            logger.error(f"上传目录不存在或不是目录: {upload_dir}", error_type="DIRECTORY", recoverable=False)
            return
        
        # 上传计数
        upload_count = 0
        total_uploaded = 0
        
        # 获取媒体组列表（每个子文件夹作为一个媒体组）
        media_groups = [d for d in upload_dir.iterdir() if d.is_dir()]
        
        if not media_groups:
            logger.warning(f"上传目录中没有子文件夹: {upload_dir}")
            logger.info("将上传目录下的所有文件作为单独的消息")
            
            # 如果没有子文件夹，将上传目录下的文件直接上传
            files = [f for f in upload_dir.iterdir() if f.is_file() and self._is_valid_media_file(f)]
            if not files:
                logger.warning(f"上传目录中没有有效的媒体文件: {upload_dir}")
                return
            
            logger.info(f"找到 {len(files)} 个文件准备上传")
            
            # 验证目标频道
            valid_targets = []
            for target in target_channels:
                try:
                    target_id = await self.channel_resolver.get_channel_id(target)
                    channel_info, (target_title, _) = await self.channel_resolver.format_channel_info(target_id)
                    valid_targets.append((target, target_id, channel_info))
                    logger.info(f"目标频道: {channel_info}")
                except Exception as e:
                    logger.error(f"解析目标频道 {target} 失败: {e}", error_type="CHANNEL_RESOLVE", recoverable=True)
            
            if not valid_targets:
                logger.error("没有有效的目标频道，无法上传文件", error_type="CHANNEL", recoverable=False)
                return
            
            # 开始上传
            logger.info(f"开始上传 {len(files)} 个文件...")
            
            # 使用批量上传
            start_time = time.time()
            uploaded_count = await self._upload_files_to_channels(files, valid_targets)
            end_time = time.time()
            
            if uploaded_count > 0:
                upload_time = end_time - start_time
                logger.info(f"上传完成: 成功上传 {uploaded_count} 个文件，耗时 {upload_time:.2f} 秒")
                self.emit("complete", True, {
                    "total_files": uploaded_count,
                    "total_time": upload_time
                })
            else:
                logger.warning("没有文件被成功上传")
            
            return
            
        # 处理子文件夹作为媒体组的情况
        logger.info(f"找到 {len(media_groups)} 个媒体组文件夹")
        
        # 验证目标频道
        valid_targets = []
        for target in target_channels:
            try:
                target_id = await self.channel_resolver.get_channel_id(target)
                channel_info, (target_title, _) = await self.channel_resolver.format_channel_info(target_id)
                valid_targets.append((target, target_id, channel_info))
                logger.info(f"目标频道: {channel_info}")
            except Exception as e:
                logger.error(f"解析目标频道 {target} 失败: {e}", error_type="CHANNEL_RESOLVE", recoverable=True)
        
        if not valid_targets:
            logger.error("没有有效的目标频道，无法上传文件", error_type="CHANNEL", recoverable=False)
            return
        
        # 开始上传
        start_time = time.time()
        total_files = 0
        total_media_groups = len(media_groups)
        
        for idx, group_dir in enumerate(media_groups):
            # 检查任务是否已取消
            if self.is_cancelled:
                logger.info("上传任务已取消")
                break
                
            # 等待暂停恢复
            while self.is_paused and not self.is_cancelled:
                await asyncio.sleep(0.5)
            
            # 更新进度
            progress = (idx / total_media_groups) * 100
            self.emit("progress", progress, idx, total_media_groups)
            
            group_name = group_dir.name
            logger.info(f"处理媒体组 [{group_name}] ({idx+1}/{total_media_groups})")
            
            # 获取媒体组中的文件
            media_files = [f for f in group_dir.iterdir() if f.is_file() and self._is_valid_media_file(f)]
            
            if not media_files:
                logger.warning(f"媒体组文件夹 {group_name} 中没有有效的媒体文件")
                continue
            
            logger.info(f"媒体组 {group_name} 包含 {len(media_files)} 个文件")
            
            # 检查是否有caption.txt文件
            caption_file = group_dir / "caption.txt"
            caption = None
            if caption_file.exists():
                try:
                    with open(caption_file, 'r', encoding='utf-8') as f:
                        caption = f.read().strip()
                    logger.info(f"已读取媒体组 {group_name} 的说明文本，长度：{len(caption)} 字符")
                except Exception as e:
                    logger.error(f"读取说明文本文件失败: {e}", error_type="FILE_READ", recoverable=True)
            
            # 上传到所有目标频道
            for target, target_id, target_info in valid_targets:
                # 检查任务是否已取消
                if self.is_cancelled:
                    logger.info("上传任务已取消")
                    break
                    
                # 等待暂停恢复
                while self.is_paused and not self.is_cancelled:
                    await asyncio.sleep(0.5)
                
                logger.info(f"上传媒体组 [{group_name}] 到 {target_info}")
                
                # 上传媒体组
                if len(media_files) == 1:
                    # 单个文件，直接上传
                    uploaded = await self._upload_single_file(media_files[0], target_id, caption)
                    if uploaded:
                        total_files += 1
                        upload_count += 1
                else:
                    # 多个文件，作为媒体组上传
                    uploaded = await self._upload_media_group(media_files, target_id, caption)
                    if uploaded:
                        total_files += len(media_files)
                        upload_count += 1
                
                # 简单的速率限制，防止过快发送请求
                await asyncio.sleep(2)
        
        # 上传完成统计
        end_time = time.time()
        upload_time = end_time - start_time
        
        if upload_count > 0:
            logger.info(f"上传完成: 成功上传 {upload_count} 个媒体组，共 {total_files} 个文件，耗时 {upload_time:.2f} 秒")
            self.emit("complete", True, {
                "total_groups": upload_count,
                "total_files": total_files,
                "total_time": upload_time
            })
        else:
            logger.warning("没有媒体组被成功上传")
        
        logger.info("所有媒体文件上传完成")
    
    def _is_valid_media_file(self, file_path: Path) -> bool:
        """
        检查文件是否为有效的媒体文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 是否为有效的媒体文件
        """
        if not file_path.is_file():
            return False
        
        # 忽略.DS_Store等隐藏文件
        if file_path.name.startswith('.'):
            return False
        
        # 忽略caption.txt文件
        if file_path.name.lower() == 'caption.txt':
            return False
        
        # 获取文件类型
        mime_type, _ = mimetypes.guess_type(file_path)
        
        if mime_type is None:
            # 尝试通过扩展名判断
            ext = file_path.suffix.lower()
            if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.mp4', '.mov', '.avi', '.mkv', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.mp3', '.m4a', '.ogg', '.wav']:
                return True
            return False
        
        # 检查是否为支持的媒体类型
        if mime_type.startswith(('image/', 'video/', 'audio/')):
            return True
        if mime_type.startswith(('application/pdf', 'application/msword', 'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument')):
            return True
        
        return False
    
    async def _upload_media_group(self, files: List[Path], chat_id: int, caption: Optional[str] = None) -> bool:
        """
        将多个文件作为媒体组上传
        
        Args:
            files: 文件路径列表
            chat_id: 目标聊天ID
            caption: 说明文本，仅会应用到第一个媒体
            
        Returns:
            bool: 上传是否成功
        """
        # 最多支持10个媒体文件作为一个组
        if len(files) > 10:
            # 分组上传
            logger.warning(f"媒体组包含 {len(files)} 个文件，超过最大限制(10)，将分批上传")
            chunks = [files[i:i+10] for i in range(0, len(files), 10)]
            success = True
            for i, chunk in enumerate(chunks):
                chunk_success = await self._upload_media_group_chunk(chunk, chat_id, caption if i == 0 else None)
                if not chunk_success:
                    success = False
                # 批次间隔
                await asyncio.sleep(3)
            return success
        else:
            # 直接上传这组文件
            return await self._upload_media_group_chunk(files, chat_id, caption)
    
    async def _upload_media_group_chunk(self, files: List[Path], chat_id: int, caption: Optional[str] = None) -> bool:
        """
        上传一个媒体组块（最多10个文件）
        """
        if not files:
            return False
        
        # 准备媒体组
        media_group = []
        thumbnails = []  # 记录生成的缩略图文件以便清理
        
        try:
            for i, file in enumerate(files):
                file_caption = caption if i == 0 else None
                media_type = self._get_media_type(file)
                
                if media_type == "photo":
                    media = InputMediaPhoto(
                        media=str(file),
                        caption=file_caption
                    )
                    media_group.append(media)
                
                elif media_type == "video":
                    # 生成缩略图
                    thumbnail = None
                    try:
                        thumbnail = await self.video_processor.extract_thumbnail(str(file))
                        if thumbnail:
                            thumbnails.append(thumbnail)
                            logger.debug(f"已生成视频缩略图: {thumbnail}")
                    except Exception as e:
                        logger.warning(f"生成视频缩略图失败: {e}")
                    
                    media = InputMediaVideo(
                        media=str(file),
                        caption=file_caption,
                        thumb=thumbnail,
                        supports_streaming=True
                    )
                    media_group.append(media)
                
                elif media_type == "document":
                    media = InputMediaDocument(
                        media=str(file),
                        caption=file_caption
                    )
                    media_group.append(media)
                
                elif media_type == "audio":
                    media = InputMediaAudio(
                        media=str(file),
                        caption=file_caption
                    )
                    media_group.append(media)
                
                else:
                    logger.warning(f"不支持的媒体类型: {file}")
                    continue
            
            if not media_group:
                logger.warning("没有有效的媒体文件可以上传")
                return False
            
            # 上传媒体组
            max_retries = 3
            for retry in range(max_retries):
                try:
                    # 捕获任何上传问题
                    logger.info(f"上传媒体组 ({len(media_group)} 个文件)...")
                    
                    start_time = time.time()
                    result = await self.client.send_media_group(
                        chat_id=chat_id,
                        media=media_group
                    )
                    end_time = time.time()
                    
                    upload_time = end_time - start_time
                    logger.info(f"媒体组上传成功，耗时 {upload_time:.2f} 秒")
                    
                    # 保存上传历史记录
                    for msg in result:
                        self.history_manager.add_upload_record(chat_id, msg.id, chat_id)
                    
                    # 发送上传成功事件
                    self.emit("media_upload", {
                        "chat_id": chat_id,
                        "media_count": len(media_group),
                        "upload_time": upload_time
                    })
                    
                    return True
                    
                except FloodWait as e:
                    logger.warning(f"触发FloodWait，等待 {e.x} 秒")
                    await asyncio.sleep(e.x)
                except (MediaEmpty, MediaInvalid) as e:
                    logger.error(f"媒体无效: {e}", error_type="MEDIA", recoverable=True)
                    return False
                except Exception as e:
                    if retry < max_retries - 1:
                        logger.warning(f"上传失败，将在 {(retry + 1) * 2} 秒后重试: {e}")
                        await asyncio.sleep((retry + 1) * 2)
                    else:
                        logger.error(f"上传媒体组失败，已达到最大重试次数: {e}", error_type="UPLOAD", recoverable=True)
                        return False
            
            return False
            
        finally:
            # 清理缩略图
            for thumb in thumbnails:
                try:
                    if os.path.exists(thumb):
                        os.remove(thumb)
                        logger.debug(f"已删除缩略图: {thumb}")
                except Exception as e:
                    logger.warning(f"删除缩略图失败: {e}")
    
    async def _upload_single_file(self, file: Path, chat_id: int, caption: Optional[str] = None) -> bool:
        """
        上传单个文件
        
        Args:
            file: 文件路径
            chat_id: 目标聊天ID
            caption: 说明文本
            
        Returns:
            bool: 上传是否成功
        """
        media_type = self._get_media_type(file)
        
        if not media_type:
            logger.warning(f"不支持的媒体类型: {file}")
            return False
        
        # 缩略图文件路径
        thumbnail = None
        
        try:
            # 处理视频缩略图
            if media_type == "video":
                try:
                    thumbnail = await self.video_processor.extract_thumbnail(str(file))
                    if thumbnail:
                        logger.debug(f"已生成视频缩略图: {thumbnail}")
                except Exception as e:
                    logger.warning(f"生成视频缩略图失败: {e}")
            
            # 上传文件
            max_retries = 3
            for retry in range(max_retries):
                try:
                    logger.info(f"上传文件: {file.name}...")
                    
                    start_time = time.time()
                    
                    if media_type == "photo":
                        result = await self.client.send_photo(
                            chat_id=chat_id,
                            photo=str(file),
                            caption=caption
                        )
                    elif media_type == "video":
                        result = await self.client.send_video(
                            chat_id=chat_id,
                            video=str(file),
                            caption=caption,
                            thumb=thumbnail,
                            supports_streaming=True
                        )
                    elif media_type == "document":
                        result = await self.client.send_document(
                            chat_id=chat_id,
                            document=str(file),
                            caption=caption
                        )
                    elif media_type == "audio":
                        result = await self.client.send_audio(
                            chat_id=chat_id,
                            audio=str(file),
                            caption=caption
                        )
                    else:
                        logger.warning(f"不支持的媒体类型: {media_type}")
                        return False
                    
                    end_time = time.time()
                    upload_time = end_time - start_time
                    
                    logger.info(f"文件 {file.name} 上传成功，耗时 {upload_time:.2f} 秒")
                    
                    # 保存上传历史记录
                    if result:
                        self.history_manager.add_upload_record(chat_id, result.id, chat_id)
                    
                    # 发送上传成功事件
                    self.emit("media_upload", {
                        "chat_id": chat_id,
                        "file_name": file.name,
                        "media_type": media_type,
                        "upload_time": upload_time
                    })
                    
                    return True
                    
                except FloodWait as e:
                    logger.warning(f"触发FloodWait，等待 {e.x} 秒")
                    await asyncio.sleep(e.x)
                except (MediaEmpty, MediaInvalid) as e:
                    logger.error(f"媒体无效: {e}", error_type="MEDIA", recoverable=True)
                    return False
                except Exception as e:
                    if retry < max_retries - 1:
                        logger.warning(f"上传失败，将在 {(retry + 1) * 2} 秒后重试: {e}")
                        await asyncio.sleep((retry + 1) * 2)
                    else:
                        logger.error(f"上传 {file.name} 失败，已达到最大重试次数: {e}", error_type="UPLOAD", recoverable=True)
                        return False
            
            return False
            
        finally:
            # 清理缩略图
            if thumbnail and os.path.exists(thumbnail):
                try:
                    os.remove(thumbnail)
                    logger.debug(f"已删除缩略图: {thumbnail}")
                except Exception as e:
                    logger.warning(f"删除缩略图失败: {e}")
    
    def _get_media_type(self, file_path: Path) -> Optional[str]:
        """
        根据文件确定媒体类型
        
        Args:
            file_path: 文件路径
            
        Returns:
            Optional[str]: 媒体类型（photo, video, document, audio）
        """
        # 获取MIME类型
        mime_type, _ = mimetypes.guess_type(str(file_path))
        ext = file_path.suffix.lower()
        
        # 根据MIME类型确定媒体类型
        if mime_type:
            if mime_type.startswith('image/'):
                return "photo"
            elif mime_type.startswith('video/'):
                return "video"
            elif mime_type.startswith('audio/'):
                return "audio"
            else:
                return "document"
        else:
            # 通过扩展名确定类型
            if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                return "photo"
            elif ext in ['.mp4', '.mov', '.avi', '.mkv']:
                return "video"
            elif ext in ['.mp3', '.m4a', '.ogg', '.wav']:
                return "audio"
            elif ext:  # 只要有扩展名的，都当作文档处理
                return "document"
        
        return None
    
    async def _upload_files_to_channels(self, files: List[Path], targets: List[Tuple[str, int, str]]) -> int:
        """
        将文件上传到多个目标频道
        
        Args:
            files: 文件路径列表
            targets: 目标频道列表，元组(channel_id, channel_name, channel_info)
            
        Returns:
            int: 成功上传的文件数量
        """
        upload_count = 0
        total_files = len(files)
        
        for idx, file in enumerate(files):
            # 检查任务是否已取消
            if self.is_cancelled:
                logger.info("上传任务已取消")
                break
                
            # 等待暂停恢复
            while self.is_paused and not self.is_cancelled:
                await asyncio.sleep(0.5)
            
            # 更新进度
            progress = (idx / total_files) * 100
            self.emit("progress", progress, idx, total_files)
            
            logger.info(f"上传文件 [{file.name}] ({idx+1}/{total_files})")
            
            # 上传到所有目标频道
            file_uploaded = False
            for target, target_id, target_info in targets:
                # 检查任务是否已取消
                if self.is_cancelled:
                    logger.info("上传任务已取消")
                    break
                    
                # 等待暂停恢复
                while self.is_paused and not self.is_cancelled:
                    await asyncio.sleep(0.5)
                
                logger.info(f"上传文件 [{file.name}] 到 {target_info}")
                
                # 上传文件
                if await self._upload_single_file(file, target_id):
                    file_uploaded = True
                
                # 简单的速率限制，防止过快发送请求
                await asyncio.sleep(1)
            
            if file_uploaded:
                upload_count += 1
            
            # 间隔时间
            await asyncio.sleep(0.5)
        
        return upload_count 