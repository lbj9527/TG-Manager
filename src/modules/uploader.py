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
from src.utils.file_utils import calculate_file_hash, get_file_size

# 仅用于内部调试，不再用于UI输出
logger = get_logger()

class Uploader():
    """
    上传模块，负责将本地文件上传到目标频道
    """
    
    def __init__(self, client: Client, ui_config_manager: UIConfigManager, channel_resolver: ChannelResolver, history_manager: HistoryManager, app=None):
        """
        初始化上传模块
        
        Args:
            client: Pyrogram客户端实例
            ui_config_manager: UI配置管理器实例
            channel_resolver: 频道解析器实例
            history_manager: 历史记录管理器实例
            app: 应用程序实例，用于网络错误时立即检查连接状态
        """
        # 初始化事件发射器
        super().__init__()
        
        self.client = client
        self.ui_config_manager = ui_config_manager
        self.channel_resolver = channel_resolver
        self.history_manager = history_manager
        self.app = app  # 保存应用程序实例引用
        
        # 获取UI配置并转换为字典
        ui_config = self.ui_config_manager.get_ui_config()
        self.config = convert_ui_config_to_dict(ui_config)
        
        # 获取上传配置和通用配置
        self.upload_config = self.config.get('UPLOAD', {})
        self.general_config = self.config.get('GENERAL', {})
        
        # 添加详细的配置日志
        logger.debug(f"初始化时的upload_config: {self.upload_config}")
        options = self.upload_config.get('options', {})
        logger.debug(f"初始化时的上传配置选项: {options}")
        
        # 初始化MIME类型
        mimetypes.init()
        
        # 初始化视频处理器
        self.video_processor = VideoProcessor()
        
        # 文件哈希缓存
        self.file_hash_cache = {}
    
    async def upload_local_files(self):
        """
        上传本地文件到目标频道
        """   
        status_message = "开始上传本地文件到目标频道"
        logger.info(status_message)
        
        # 重新获取最新的UI配置
        ui_config = self.ui_config_manager.get_ui_config()
        self.config = convert_ui_config_to_dict(ui_config)
        self.upload_config = self.config.get('UPLOAD', {})
        logger.debug("已刷新上传配置")
        logger.debug(f"完整的上传配置: {self.upload_config}")
        
        # 添加更详细的调试日志
        options = self.upload_config.get('options', {})
        logger.info(f"详细的上传配置选项: {options}")
        logger.info(f"配置的文件夹名称选项: {options.get('use_folder_name', '未设置')}")
        logger.info(f"配置的读取title.txt选项: {options.get('read_title_txt', '未设置')}")
        
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
            
            # 检查是否有多个目标频道
            if len(valid_targets) > 1:
                # 有多个目标频道，使用优化逻辑
                # 创建一个新的上传方法，实现首先上传到第一个频道，然后复制到其他频道
                start_time = time.time()
                uploaded_count = await self._upload_files_to_channels_with_copy(files, valid_targets)
                end_time = time.time()
            else:
                # 只有一个目标频道，使用原方法
                start_time = time.time()
                uploaded_count = await self._upload_files_to_channels(files, valid_targets)
                end_time = time.time()
            
            if uploaded_count > 0:
                upload_time = end_time - start_time
                logger.info(f"上传完成: 成功上传 {uploaded_count} 个文件，耗时 {upload_time:.2f} 秒")
                
                # 处理最终消息
                await self._send_final_message(valid_targets, True)
                
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
            
            # 从upload_config中获取caption相关参数
            options = self.upload_config.get('options', {})
            logger.debug(f"上传配置选项: {options}")
            
            # 检查options是否为空，如果为空则使用默认值
            if not options:
                logger.warning("上传配置options为空，使用默认值")
                options = {
                    "use_folder_name": True,
                    "read_title_txt": False,
                    "send_final_message": False,
                    "auto_thumbnail": True
                }
            
            # 明确转换为布尔值，避免字符串或其他类型的问题
            use_folder_name = bool(options.get('use_folder_name', True))
            read_title_txt = bool(options.get('read_title_txt', False))
            
            # 确保互斥性：如果两个选项都为true，优先使用read_title_txt
            if use_folder_name and read_title_txt:
                logger.warning("检测到use_folder_name和read_title_txt同时为true，将优先使用read_title_txt")
                use_folder_name = False
            
            # 兼容性处理：如果read_title_txt为"true"字符串，确保转换为布尔值
            if isinstance(read_title_txt, str) and read_title_txt.lower() == "true":
                read_title_txt = True
            # 同样处理use_folder_name
            if isinstance(use_folder_name, str) and use_folder_name.lower() == "false":
                use_folder_name = False
            
            logger.info(f"caption相关参数: use_folder_name={use_folder_name}, read_title_txt={read_title_txt}")
            
            caption = None
            
            # 根据配置决定如何设置caption
            if read_title_txt:
                # 检查是否有title.txt文件
                caption_file = group_dir / "title.txt"
                if caption_file.exists():
                    try:
                        with open(caption_file, 'r', encoding='utf-8') as f:
                            caption = f.read().strip()
                        logger.info(f"已读取媒体组 {group_name} 的说明文本，长度：{len(caption)} 字符")
                    except Exception as e:
                        logger.error(f"读取说明文本文件失败: {e}", error_type="FILE_READ", recoverable=True)
            elif use_folder_name:
                # 使用文件夹名称作为说明文字
                caption = group_name
                logger.info(f"使用文件夹名称 '{group_name}' 作为说明文本")
            
            # 上传到所有目标频道
            if len(valid_targets) > 1:
                # 有多个目标频道，使用优化逻辑
                first_target, first_target_id, first_target_info = valid_targets[0]
                other_targets = valid_targets[1:]
                
                # 先上传到第一个目标频道
                logger.info(f"上传媒体组 [{group_name}] 到第一个目标频道 {first_target_info}")
                
                # 上传媒体组
                if len(media_files) == 1:
                    # 单个文件，直接上传
                    success, actually_uploaded, message = await self._upload_single_file_with_message(media_files[0], first_target_id, caption)
                    if success:
                        if actually_uploaded:
                            total_files += 1
                            upload_count += 1
                            
                            # 如果上传成功并且有消息对象，复制到其他频道
                            if message:
                                for target, target_id, target_info in other_targets:
                                    try:
                                        logger.info(f"复制消息到频道: {target_info}")
                                        
                                        # 使用copy_message复制消息
                                        await self.client.copy_message(
                                            chat_id=target_id,
                                            from_chat_id=first_target_id,
                                            message_id=message.id
                                        )
                                        
                                        logger.info(f"成功复制消息到频道: {target_info}")
                                        total_files += 1  # 增加文件计数（每个频道算一次）
                                        
                                        # 记录上传历史 - 添加复制的消息记录
                                        file_str = str(media_files[0])
                                        file_hash = self.file_hash_cache.get(file_str)
                                        if not file_hash:
                                            file_hash = calculate_file_hash(media_files[0])
                                            if file_hash:
                                                self.file_hash_cache[file_str] = file_hash
                                        
                                        if file_hash:
                                            target_id_str = str(target_id)
                                            file_size = get_file_size(media_files[0])
                                            media_type = self._get_media_type(media_files[0])
                                            
                                            # 添加到历史记录
                                            self.history_manager.add_upload_record_by_hash(
                                                file_hash=file_hash,
                                                file_path=file_str,
                                                target_channel=target_id_str,
                                                file_size=file_size,
                                                media_type=media_type
                                            )
                                            
                                            logger.info(f"已记录文件 {media_files[0].name} 复制到 {target_info} 的历史记录")
                                    
                                    except Exception as e:
                                        logger.error(f"复制消息到频道 {target_info} 失败: {e}")
                                        # 如果复制失败，尝试直接上传
                                        logger.info(f"尝试直接上传文件 [{media_files[0].name}] 到频道 {target_info}")
                                        direct_success, direct_uploaded = await self._upload_single_file(media_files[0], target_id, caption)
                                        if direct_success and direct_uploaded:
                                            total_files += 1  # 增加文件计数（直接上传成功）
                                    
                                    # 简单的速率限制
                                    await asyncio.sleep(1)
                        else:
                            logger.info(f"文件 {media_files[0].name} 已存在于目标频道，不计入上传统计")
                    else:
                        # 第一个频道上传失败，尝试直接上传到其他频道
                        logger.warning(f"上传文件 [{media_files[0].name}] 到第一个目标频道失败，将直接上传到其他频道")
                        
                        for target, target_id, target_info in other_targets:
                            logger.info(f"上传文件 [{media_files[0].name}] 到 {target_info}")
                            direct_success, direct_uploaded = await self._upload_single_file(media_files[0], target_id, caption)
                            if direct_success and direct_uploaded:
                                total_files += 1
                                upload_count += 1
                            
                            # 简单的速率限制
                            await asyncio.sleep(1)
                else:
                    # 多个文件，作为媒体组上传
                    success, actually_uploaded, messages = await self._upload_media_group_with_messages(media_files, first_target_id, caption)
                    if success:
                        if actually_uploaded:
                            # 只有在实际上传时才增加计数
                            total_files += len(media_files)
                            upload_count += 1
                            
                            # 如果上传成功并且有消息对象，复制到其他频道
                            if messages and len(messages) > 0:
                                # 获取媒体组的第一个消息的ID
                                first_message_id = messages[0].id
                                logger.info(f"媒体组第一条消息ID: {first_message_id}")
                                
                                # 媒体组消息是连续的，计算消息ID范围
                                message_count = len(messages)
                                
                                for target, target_id, target_info in other_targets:
                                    try:
                                        logger.info(f"复制媒体组到频道: {target_info}")
                                        
                                        # 尝试使用forward_messages转发媒体组（更稳定）
                                        forwarded = await self.client.forward_messages(
                                            chat_id=target_id,
                                            from_chat_id=first_target_id,
                                            message_ids=list(range(first_message_id, first_message_id + message_count))
                                        )
                                        
                                        if forwarded:
                                            logger.info(f"成功转发媒体组到频道: {target_info}")
                                            total_files += len(media_files)  # 增加文件计数（每个频道算一次）
                                            
                                            # 记录所有文件的上传历史
                                            for media_file in media_files:
                                                file_str = str(media_file)
                                                file_hash = self.file_hash_cache.get(file_str)
                                                if not file_hash:
                                                    file_hash = calculate_file_hash(media_file)
                                                    if file_hash:
                                                        self.file_hash_cache[file_str] = file_hash
                                                
                                                if file_hash:
                                                    target_id_str = str(target_id)
                                                    file_size = get_file_size(media_file)
                                                    media_type = self._get_media_type(media_file)
                                                    
                                                    # 添加到历史记录
                                                    self.history_manager.add_upload_record_by_hash(
                                                        file_hash=file_hash,
                                                        file_path=file_str,
                                                        target_channel=target_id_str,
                                                        file_size=file_size,
                                                        media_type=media_type
                                                    )
                                                    
                                                    logger.debug(f"已记录文件 {media_file.name} 的复制历史到频道 {target_info}")
                                            
                                            logger.info(f"已记录媒体组 {group_name} 的所有文件复制到 {target_info} 的历史记录，共 {len(media_files)} 个文件")
                                        else:
                                            logger.warning(f"转发媒体组返回空结果，可能失败")
                                            raise Exception("转发媒体组返回空结果")
                                    
                                    except Exception as e:
                                        logger.error(f"复制媒体组到频道 {target_info} 失败: {e}")
                                        # 如果复制失败，尝试直接上传
                                        logger.info(f"尝试直接上传媒体组到频道 {target_info}")
                                        direct_success, direct_uploaded = await self._upload_media_group(media_files, target_id, caption)
                                        if direct_success and direct_uploaded:
                                            total_files += len(media_files)  # 增加文件计数（直接上传成功）
                                    
                                    # 简单的速率限制
                                    await asyncio.sleep(2)
                        else:
                            logger.info(f"媒体组 {group_name} 的所有文件都已存在于目标频道，不计入上传统计")
                    else:
                        # 第一个频道上传失败，尝试直接上传到其他频道
                        logger.warning(f"上传媒体组 [{group_name}] 到第一个目标频道失败，将直接上传到其他频道")
                        
                        for target, target_id, target_info in other_targets:
                            logger.info(f"上传媒体组 [{group_name}] 到 {target_info}")
                            direct_success, direct_uploaded = await self._upload_media_group(media_files, target_id, caption)
                            if direct_success and direct_uploaded:
                                total_files += len(media_files)
                                upload_count += 1
                            
                            # 简单的速率限制
                            await asyncio.sleep(2)
            else:
                # 只有一个目标频道，使用原有逻辑
                target, target_id, target_info = valid_targets[0]                         
                logger.info(f"上传媒体组 [{group_name}] 到 {target_info}")
                
                # 上传媒体组
                if len(media_files) == 1:
                    # 单个文件，直接上传
                    success, actually_uploaded = await self._upload_single_file(media_files[0], target_id, caption)
                    if success:
                        if actually_uploaded:
                            total_files += 1
                            upload_count += 1
                        else:
                            logger.info(f"文件 {media_files[0].name} 已存在于目标频道，不计入上传统计")
                else:
                    # 多个文件，作为媒体组上传
                    success, actually_uploaded = await self._upload_media_group(media_files, target_id, caption)
                    if success:
                        if actually_uploaded:
                            # 只有在实际上传时才增加计数
                            total_files += len(media_files)
                            upload_count += 1
                        else:
                            logger.info(f"媒体组 {group_name} 的所有文件都已存在于目标频道，不计入上传统计")
            
            # 简单的速率限制，防止过快发送请求
            await asyncio.sleep(2)
        
        # 上传完成后，发送最终消息
        await self._send_final_message(valid_targets, upload_count > 0)
        
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
        
        # 忽略title.txt文件
        if file_path.name.lower() == 'title.txt':
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
    
    async def _upload_media_group(self, files: List[Path], chat_id: int, caption: Optional[str] = None) -> Tuple[bool, bool]:
        """
        将多个文件作为媒体组上传
        
        Args:
            files: 文件路径列表
            chat_id: 目标聊天ID
            caption: 说明文本，仅会应用到第一个媒体
            
        Returns:
            Tuple[bool, bool]: (是否成功, 是否实际上传)第一个元素表示操作是否成功，第二个元素表示是否实际上传了文件
        """
        # 最多支持10个媒体文件作为一个组
        if len(files) > 10:
            # 分组上传
            logger.warning(f"媒体组包含 {len(files)} 个文件，超过最大限制(10)，将分批上传")
            chunks = [files[i:i+10] for i in range(0, len(files), 10)]
            success = True
            actually_uploaded = False
            for i, chunk in enumerate(chunks):
                chunk_success, chunk_uploaded = await self._upload_media_group_chunk(chunk, chat_id, caption if i == 0 else None)
                if not chunk_success:
                    success = False
                if chunk_uploaded:
                    actually_uploaded = True
                # 批次间隔
                await asyncio.sleep(3)
            return success, actually_uploaded
        else:
            # 直接上传这组文件
            return await self._upload_media_group_chunk(files, chat_id, caption)
    
    async def _upload_media_group_chunk(self, files: List[Path], chat_id: int, caption: Optional[str] = None) -> Tuple[bool, bool]:
        """
        上传一个媒体组块（最多10个文件）
        
        Returns:
            Tuple[bool, bool]: (是否成功, 是否实际上传)第一个元素表示操作是否成功，第二个元素表示是否实际上传了文件
        """
        if not files:
            return False, False
        
        chat_id_str = str(chat_id)
        
        # 过滤已上传的文件
        filtered_files = []
        file_hashes = {}  # 存储文件哈希值
        
        for file in files:
            file_str = str(file)
            # 计算文件哈希
            if file_str in self.file_hash_cache:
                file_hash = self.file_hash_cache[file_str]
            else:
                file_hash = calculate_file_hash(file)
                if file_hash:
                    self.file_hash_cache[file_str] = file_hash
                else:
                    logger.warning(f"无法计算文件哈希值: {file}")
                    continue
            
            # 检查是否已上传
            if self.history_manager.is_file_hash_uploaded(file_hash, chat_id_str):
                logger.info(f"文件 {file.name} (哈希: {file_hash[:8]}...) 已上传到频道 {chat_id_str}，从媒体组中跳过")
                
                # 发送文件已上传事件
                self.emit("file_already_uploaded", {
                    "chat_id": chat_id,
                    "file_name": file.name,
                    "file_path": file_str,
                    "file_hash": file_hash,
                    "media_type": self._get_media_type(file)
                })
            else:
                filtered_files.append(file)
                file_hashes[file_str] = file_hash
        
        # 如果所有文件都已上传过，直接返回成功
        if not filtered_files:
            logger.info(f"媒体组中的所有文件都已上传到频道 {chat_id_str}，跳过整个媒体组")
            return True, False  # 成功但没有实际上传新文件
        
        # 如果过滤后只剩一个文件，作为单个文件上传
        if len(filtered_files) == 1:
            logger.info(f"媒体组中只有一个文件需要上传，转为单文件上传")
            return await self._upload_single_file(filtered_files[0], chat_id, caption)
        
        # 准备媒体组
        media_group = []
        thumbnails = []  # 记录生成的缩略图文件以便清理
        
        try:
            for i, file in enumerate(filtered_files):
                file_caption = caption if i == 0 else None
                media_type = self._get_media_type(file)
                
                if media_type == "photo":
                    media = InputMediaPhoto(
                        media=str(file),
                        caption=file_caption
                    )
                    media_group.append(media)
                
                elif media_type == "video":
                    # 生成缩略图和获取视频尺寸
                    thumbnail = None
                    width = height = None
                    try:
                        result = await self.video_processor.extract_thumbnail_async(str(file))
                        if result:
                            if isinstance(result, tuple) and len(result) == 3:
                                thumbnail, width, height = result
                            else:
                                thumbnail = result
                            
                            thumbnails.append(thumbnail)
                            if width and height:
                                logger.debug(f"已生成视频缩略图: {thumbnail}, 尺寸: {width}x{height}")
                            else:
                                logger.debug(f"已生成视频缩略图: {thumbnail}")
                    except Exception as e:
                        logger.warning(f"生成视频缩略图失败: {e}")
                    
                    # 创建媒体对象，包含宽度和高度
                    media = InputMediaVideo(
                        media=str(file),
                        caption=file_caption,
                        thumb=thumbnail,
                        supports_streaming=True,
                        width=width,
                        height=height
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
                return False, False
            
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
                        # 获取文件路径和大小
                        if hasattr(msg, 'file') and hasattr(msg.file, 'size'):
                            file_size = msg.file.size
                        else:
                            file_size = 0
                        
                        # 确定媒体类型
                        if msg.photo:
                            file_media_type = "photo"
                        elif msg.video:
                            file_media_type = "video"
                        elif msg.document:
                            file_media_type = "document"
                        elif msg.audio:
                            file_media_type = "audio"
                        else:
                            file_media_type = "unknown"
                        
                        # 用消息ID确定对应的媒体文件
                        # 由于PyroGram不提供足够的信息来确定哪个消息对应哪个文件
                        # 我们假设消息顺序与文件顺序相同
                        idx = min(result.index(msg), len(filtered_files) - 1)
                        file_path = str(filtered_files[idx])
                        file_hash = file_hashes.get(file_path)
                        
                        if file_hash:
                            # 记录上传
                            self.history_manager.add_upload_record_by_hash(
                                file_hash=file_hash,
                                file_path=file_path,
                                target_channel=chat_id_str,
                                file_size=file_size,
                                media_type=file_media_type
                            )
                    
                    # 发送上传成功事件
                    media_group_info = {
                        "chat_id": chat_id,
                        "media_count": len(media_group),
                        "upload_time": upload_time,
                        "is_group": True,
                        "files": [str(f) for f in filtered_files]
                    }
                    self.emit("media_upload", media_group_info)
                    
                    # 同时为媒体组发送file_uploaded事件
                    self.emit("file_uploaded", f"媒体组({len(media_group)}个文件)", True)
                    
                    return True, True  # 成功且实际上传了新文件
                    
                except FloodWait as e:
                    logger.warning(f"触发FloodWait，等待 {e.x} 秒")
                    await asyncio.sleep(e.x)
                except (MediaEmpty, MediaInvalid) as e:
                    logger.error(f"媒体无效: {e}", error_type="MEDIA", recoverable=True)
                    return False, False
                except Exception as e:
                    if retry < max_retries - 1:
                        logger.warning(f"上传失败，将在 {(retry + 1) * 2} 秒后重试: {e}")
                        await asyncio.sleep((retry + 1) * 2)
                    else:
                        logger.error(f"上传媒体组失败，已达到最大重试次数: {e}", error_type="UPLOAD", recoverable=True)
                        return False, False
            
            return False, False
            
        finally:
            # 清理缩略图
            for thumb in thumbnails:
                try:
                    if os.path.exists(thumb):
                        os.remove(thumb)
                        logger.debug(f"已删除缩略图: {thumb}")
                except Exception as e:
                    logger.warning(f"删除缩略图失败: {e}")
    
    async def _upload_single_file(self, file: Path, chat_id: int, caption: Optional[str] = None) -> Tuple[bool, bool]:
        """
        上传单个文件
        
        Args:
            file: 文件路径
            chat_id: 目标聊天ID
            caption: 说明文本
            
        Returns:
            Tuple[bool, bool]: (是否成功, 是否实际上传)第一个元素表示操作是否成功，第二个元素表示是否实际上传了文件
        """
        media_type = self._get_media_type(file)
        
        if not media_type:
            logger.warning(f"不支持的媒体类型: {file}")
            return False, False
        
        # 计算文件哈希
        file_str = str(file)
        if file_str in self.file_hash_cache:
            file_hash = self.file_hash_cache[file_str]
        else:
            file_hash = calculate_file_hash(file)
            if file_hash:
                self.file_hash_cache[file_str] = file_hash
            else:
                logger.warning(f"无法计算文件哈希值: {file}")
                return False, False
        
        # 检查文件是否已上传到目标频道
        chat_id_str = str(chat_id)
        if self.history_manager.is_file_hash_uploaded(file_hash, chat_id_str):
            logger.info(f"文件 {file.name} (哈希: {file_hash[:8]}...) 已上传到频道 {chat_id_str}，跳过上传")
            
            # 发送文件已上传事件
            self.emit("file_already_uploaded", {
                "chat_id": chat_id,
                "file_name": file.name,
                "file_path": file_str,
                "file_hash": file_hash,
                "media_type": media_type
            })
            
            return True, False  # 返回成功，但实际未上传新文件
        
        # 缩略图文件路径和视频尺寸
        thumbnail = None
        width = height = None
        
        try:
            # 处理视频缩略图和获取尺寸
            if media_type == "video":
                try:
                    result = await self.video_processor.extract_thumbnail_async(str(file))
                    if result:
                        if isinstance(result, tuple) and len(result) == 3:
                            thumbnail, width, height = result
                        else:
                            thumbnail = result
                        
                        if width and height:
                            logger.debug(f"已生成视频缩略图: {thumbnail}, 尺寸: {width}x{height}")
                        else:
                            logger.debug(f"已生成视频缩略图: {thumbnail}")
                except Exception as e:
                    logger.warning(f"生成视频缩略图失败: {e}")
            
            # 上传文件
            max_retries = 3
            for retry in range(max_retries):
                try:
                    logger.info(f"上传文件: {file.name} (哈希: {file_hash[:8]}...)...")
                    
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
                            supports_streaming=True,
                            width=width,
                            height=height
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
                        return False, False
                    
                    end_time = time.time()
                    upload_time = end_time - start_time
                    
                    logger.info(f"文件 {file.name} 上传成功，耗时 {upload_time:.2f} 秒")
                    
                    # 保存上传历史记录
                    if result:
                        # 获取文件大小
                        if hasattr(result, 'file') and hasattr(result.file, 'size'):
                            file_size = result.file.size
                        else:
                            file_size = get_file_size(file)
                        
                        # 使用文件哈希记录上传
                        self.history_manager.add_upload_record_by_hash(
                            file_hash=file_hash,
                            file_path=file_str,
                            target_channel=chat_id_str,
                            file_size=file_size,
                            media_type=media_type
                        )
                    
                    # 发送上传成功事件
                    self.emit("media_upload", {
                        "chat_id": chat_id,
                        "file_name": file.name,
                        "file_path": file_str,
                        "file_hash": file_hash,
                        "media_type": media_type,
                        "upload_time": upload_time,
                        "file_size": file_size if 'file_size' in locals() else get_file_size(file)
                    })
                    
                    # 同时发送file_uploaded事件，确保向下兼容
                    self.emit("file_uploaded", str(file), True)
                    
                    return True, True  # 上传成功且实际上传了新文件
                    
                except FloodWait as e:
                    logger.warning(f"触发FloodWait，等待 {e.x} 秒")
                    await asyncio.sleep(e.x)
                except (MediaEmpty, MediaInvalid) as e:
                    logger.error(f"媒体无效: {e}", error_type="MEDIA", recoverable=True)
                    return False, False
                except Exception as e:
                    if retry < max_retries - 1:
                        logger.warning(f"上传失败，将在 {(retry + 1) * 2} 秒后重试: {e}")
                        await asyncio.sleep((retry + 1) * 2)
                    else:
                        logger.error(f"上传文件 {file.name} 失败: {e}")
                        
                        # 检测网络相关错误
                        error_name = type(e).__name__.lower()
                        if any(net_err in error_name for net_err in ['network', 'connection', 'timeout', 'socket']):
                            # 网络相关错误，通知应用程序检查连接状态
                            await self._handle_network_error(e)
                        
                        return False, False
            
            return False, False
            
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
        
        优化逻辑：首先上传到第一个目标频道，如果成功，则使用copy_message/copy_media_group将消息复制到其他频道
        如果第一个频道上传失败，则其他频道使用原方法直接上传
        
        Args:
            files: 文件路径列表
            targets: 目标频道列表，元组(channel_id, channel_name, channel_info)
            
        Returns:
            int: 成功上传的文件数量（实际上传的新文件，不包括已经存在的）
        """
        if not files or not targets:
            logger.warning("没有文件或目标频道，无法上传")
            return 0

        upload_count = 0
        total_files = len(files)
        
        # 复制第一个目标频道的信息，其他频道用于消息复制
        first_target = targets[0]
        other_targets = targets[1:] if len(targets) > 1 else []
        
        for idx, file in enumerate(files):                      
            # 更新进度
            progress = (idx / total_files) * 100
            self.emit("progress", progress, idx, total_files)
            
            logger.info(f"上传文件 [{file.name}] ({idx+1}/{total_files})")
            
            # 先上传到第一个目标频道
            first_target_id = first_target[1]
            first_target_info = first_target[2]
            
            logger.info(f"上传文件 [{file.name}] 到第一个目标频道 {first_target_info}")
            
            # 上传文件，并获取消息对象（成功时）
            success, actually_uploaded, message = await self._upload_single_file_with_message(file, first_target_id)
            file_uploaded = success and actually_uploaded
            
            # 如果第一个频道上传成功，使用copy_message复制到其他频道
            if success and message:
                logger.info(f"文件 [{file.name}] 成功上传到第一个目标频道，将复制消息到其他频道")
                
                for target, target_id, target_info in other_targets:
                    try:
                        logger.info(f"复制消息到频道: {target_info}")
                        
                        # 使用copy_message复制消息
                        await self.client.copy_message(
                            chat_id=target_id,
                            from_chat_id=first_target_id,
                            message_id=message.id
                        )
                        
                        logger.info(f"成功复制消息到频道: {target_info}")
                        
                        # 简单的速率限制
                        await asyncio.sleep(1)
                        
                    except Exception as e:
                        logger.error(f"复制消息到频道 {target_info} 失败: {e}")
                        # 如果复制失败，尝试直接上传
                        logger.info(f"尝试直接上传文件 [{file.name}] 到频道 {target_info}")
                        direct_success, direct_uploaded = await self._upload_single_file(file, target_id)
                        # 不更改file_uploaded状态，只依赖第一个频道的上传结果
            
            # 如果第一个频道上传失败，使用原方法上传到其他频道
            elif not success:
                logger.warning(f"文件 [{file.name}] 上传到第一个目标频道失败，将直接上传到其他频道")
                
                # 遍历其他目标频道，直接上传
                for target, target_id, target_info in other_targets:
                    logger.info(f"上传文件 [{file.name}] 到 {target_info}")
                    
                    # 上传文件
                    direct_success, direct_uploaded = await self._upload_single_file(file, target_id)
                    if direct_success and direct_uploaded:
                        file_uploaded = True
                    
                    # 简单的速率限制
                    await asyncio.sleep(1)
            
            if file_uploaded:
                upload_count += 1
            
            # 间隔时间
            await asyncio.sleep(0.5)
        
        return upload_count

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

    async def _send_final_message(self, valid_targets, files_uploaded=False):
        """
        发送最终消息到所有目标频道
        
        如果配置中启用了send_final_message选项且提供了final_message_html_file路径，
        则读取该HTML文件并发送到所有目标频道。
        
        Args:
            valid_targets: 有效的目标频道列表，格式为 [(target, target_id, target_info), ...]
            files_uploaded: 是否有文件实际被上传，默认为False
        """
        # 从配置中获取选项
        options = self.upload_config.get('options', {})
        send_final_message = bool(options.get('send_final_message', False))
        
        # 如果未启用最终消息，直接返回
        if not send_final_message:
            logger.debug("未启用发送最终消息功能，跳过")
            return
            
        # 如果没有文件被实际上传，不发送最终消息
        if not files_uploaded:
            logger.info("没有文件被实际上传，跳过发送最终消息")
            return
        
        # 获取HTML文件路径
        html_file_path = options.get('final_message_html_file', '')
        if not html_file_path:
            logger.warning("启用了发送最终消息功能，但未指定HTML文件路径，跳过")
            return
        
        # 检查文件是否存在
        if not os.path.exists(html_file_path) or not os.path.isfile(html_file_path):
            logger.error(f"最终消息HTML文件不存在或不是文件: {html_file_path}")
            return
        
        # 读取HTML文件内容
        try:
            with open(html_file_path, 'r', encoding='utf-8') as f:
                html_content = f.read().strip()
            
            if not html_content:
                logger.warning(f"最终消息HTML文件内容为空: {html_file_path}")
                return
            
            logger.info(f"已读取最终消息HTML文件，长度: {len(html_content)} 字符")
            
            # 发送到所有目标频道
            for target, target_id, target_info in valid_targets:
                try:
                    logger.info(f"发送最终消息到频道: {target_info}")
                    
                    # 使用HTML解析模式发送消息
                    from pyrogram import enums
                    
                    # 捕捉超时和网络错误
                    max_retries = 3
                    for retry in range(max_retries):
                        try:
                            message = await self.client.send_message(
                                chat_id=target_id,
                                text=html_content,
                                parse_mode=enums.ParseMode.HTML,
                                disable_web_page_preview=False  # 允许链接预览
                            )
                            
                            logger.info(f"最终消息发送成功，消息ID: {message.id}")
                            
                            # 发送成功事件
                            self.emit("final_message_sent", {
                                "chat_id": target_id,
                                "chat_info": target_info,
                                "message_id": message.id
                            })
                            
                            break  # 发送成功，跳出重试循环
                            
                        except Exception as e:
                            if retry < max_retries - 1:
                                logger.warning(f"发送最终消息失败，将在 {(retry + 1) * 2} 秒后重试: {e}")
                                await asyncio.sleep((retry + 1) * 2)
                            else:
                                logger.error(f"发送最终消息到频道 {target_info} 失败，已达到最大重试次数: {e}")
                                # 发送失败事件
                                self.emit("final_message_error", {
                                    "chat_id": target_id,
                                    "chat_info": target_info,
                                    "error": str(e)
                                })
                    
                    # 添加延迟以避免触发频率限制
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"发送最终消息到频道 {target_info} 时出错: {e}")
        
        except Exception as e:
            logger.error(f"读取或处理最终消息HTML文件时出错: {e}") 

    async def _upload_single_file_with_message(self, file: Path, chat_id: int, caption: Optional[str] = None) -> Tuple[bool, bool, Optional[Message]]:
        """
        上传单个文件并返回消息对象
        
        这个方法是对_upload_single_file的扩展，增加了返回上传后的消息对象，用于消息复制功能
        
        Args:
            file: 文件路径
            chat_id: 目标聊天ID
            caption: 说明文本
            
        Returns:
            Tuple[bool, bool, Optional[Message]]: (是否成功, 是否实际上传, 消息对象)
            第一个元素表示操作是否成功，第二个元素表示是否实际上传了文件，第三个是消息对象（成功时）
        """
        media_type = self._get_media_type(file)
        
        if not media_type:
            logger.warning(f"不支持的媒体类型: {file}")
            return False, False, None
        
        # 计算文件哈希
        file_str = str(file)
        if file_str in self.file_hash_cache:
            file_hash = self.file_hash_cache[file_str]
        else:
            file_hash = calculate_file_hash(file)
            if file_hash:
                self.file_hash_cache[file_str] = file_hash
            else:
                logger.warning(f"无法计算文件哈希值: {file}")
                return False, False, None
        
        # 检查文件是否已上传到目标频道
        chat_id_str = str(chat_id)
        if self.history_manager.is_file_hash_uploaded(file_hash, chat_id_str):
            logger.info(f"文件 {file.name} (哈希: {file_hash[:8]}...) 已上传到频道 {chat_id_str}，跳过上传")
            
            # 发送文件已上传事件
            self.emit("file_already_uploaded", {
                "chat_id": chat_id,
                "file_name": file.name,
                "file_path": file_str,
                "file_hash": file_hash,
                "media_type": media_type
            })
            
            return True, False, None  # 返回成功，但实际未上传新文件，消息对象为None
        
        # 缩略图文件路径和视频尺寸
        thumbnail = None
        width = height = None
        
        try:
            # 处理视频缩略图和获取尺寸
            if media_type == "video":
                try:
                    result = await self.video_processor.extract_thumbnail_async(str(file))
                    if result:
                        if isinstance(result, tuple) and len(result) == 3:
                            thumbnail, width, height = result
                        else:
                            thumbnail = result
                        
                        if width and height:
                            logger.debug(f"已生成视频缩略图: {thumbnail}, 尺寸: {width}x{height}")
                        else:
                            logger.debug(f"已生成视频缩略图: {thumbnail}")
                except Exception as e:
                    logger.warning(f"生成视频缩略图失败: {e}")
            
            # 上传文件
            max_retries = 3
            for retry in range(max_retries):
                try:
                    logger.info(f"上传文件: {file.name} (哈希: {file_hash[:8]}...)...")
                    
                    start_time = time.time()
                    
                    if media_type == "photo":
                        message = await self.client.send_photo(
                            chat_id=chat_id,
                            photo=str(file),
                            caption=caption
                        )
                    elif media_type == "video":
                        message = await self.client.send_video(
                            chat_id=chat_id,
                            video=str(file),
                            caption=caption,
                            thumb=thumbnail,
                            supports_streaming=True,
                            width=width,
                            height=height
                        )
                    elif media_type == "document":
                        message = await self.client.send_document(
                            chat_id=chat_id,
                            document=str(file),
                            caption=caption
                        )
                    elif media_type == "audio":
                        message = await self.client.send_audio(
                            chat_id=chat_id,
                            audio=str(file),
                            caption=caption
                        )
                    else:
                        logger.warning(f"不支持的媒体类型: {media_type}")
                        return False, False, None
                    
                    end_time = time.time()
                    upload_time = end_time - start_time
                    
                    logger.info(f"文件 {file.name} 上传成功，耗时 {upload_time:.2f} 秒")
                    
                    # 保存上传历史记录
                    if message:
                        # 获取文件大小
                        if hasattr(message, 'file') and hasattr(message.file, 'size'):
                            file_size = message.file.size
                        else:
                            file_size = get_file_size(file)
                        
                        # 使用文件哈希记录上传
                        self.history_manager.add_upload_record_by_hash(
                            file_hash=file_hash,
                            file_path=file_str,
                            target_channel=chat_id_str,
                            file_size=file_size,
                            media_type=media_type
                        )
                    
                    # 发送上传成功事件
                    self.emit("media_upload", {
                        "chat_id": chat_id,
                        "file_name": file.name,
                        "file_path": file_str,
                        "file_hash": file_hash,
                        "media_type": media_type,
                        "upload_time": upload_time,
                        "file_size": file_size if 'file_size' in locals() else get_file_size(file)
                    })
                    
                    # 同时发送file_uploaded事件，确保向下兼容
                    self.emit("file_uploaded", str(file), True)
                    
                    return True, True, message  # 上传成功且实际上传了新文件，返回消息对象
                    
                except FloodWait as e:
                    logger.warning(f"触发FloodWait，等待 {e.x} 秒")
                    await asyncio.sleep(e.x)
                except (MediaEmpty, MediaInvalid) as e:
                    logger.error(f"媒体无效: {e}", error_type="MEDIA", recoverable=True)
                    return False, False, None
                except Exception as e:
                    if retry < max_retries - 1:
                        logger.warning(f"上传失败，将在 {(retry + 1) * 2} 秒后重试: {e}")
                        await asyncio.sleep((retry + 1) * 2)
                    else:
                        logger.error(f"上传文件 {file.name} 失败: {e}")
                        
                        # 检测网络相关错误
                        error_name = type(e).__name__.lower()
                        if any(net_err in error_name for net_err in ['network', 'connection', 'timeout', 'socket']):
                            # 网络相关错误，通知应用程序检查连接状态
                            await self._handle_network_error(e)
                        
                        return False, False, None
            
            return False, False, None
            
        finally:
            # 清理缩略图
            if thumbnail and os.path.exists(thumbnail):
                try:
                    os.remove(thumbnail)
                    logger.debug(f"已删除缩略图: {thumbnail}")
                except Exception as e:
                    logger.warning(f"删除缩略图失败: {e}")
    
    async def _upload_media_group_with_messages(self, files: List[Path], chat_id: int, caption: Optional[str] = None) -> Tuple[bool, bool, Optional[List[Message]]]:
        """
        将多个文件作为媒体组上传并返回消息对象列表
        
        这个方法是对_upload_media_group的扩展，增加了返回上传后的消息对象列表，用于消息复制功能
        
        Args:
            files: 文件路径列表
            chat_id: 目标聊天ID
            caption: 说明文本，仅会应用到第一个媒体
            
        Returns:
            Tuple[bool, bool, Optional[List[Message]]]: (是否成功, 是否实际上传, 消息对象列表)
            第一个元素表示操作是否成功，第二个元素表示是否实际上传了文件，第三个是消息对象列表（成功时）
        """
        # 最多支持10个媒体文件作为一个组
        if len(files) > 10:
            # 分组上传
            logger.warning(f"媒体组包含 {len(files)} 个文件，超过最大限制(10)，将分批上传")
            chunks = [files[i:i+10] for i in range(0, len(files), 10)]
            success = True
            actually_uploaded = False
            all_messages = []
            
            for i, chunk in enumerate(chunks):
                chunk_success, chunk_uploaded, chunk_messages = await self._upload_media_group_chunk_with_messages(
                    chunk, chat_id, caption if i == 0 else None
                )
                
                if not chunk_success:
                    success = False
                if chunk_uploaded:
                    actually_uploaded = True
                
                # 收集所有消息对象
                if chunk_messages:
                    all_messages.extend(chunk_messages)
                    
                # 批次间隔
                await asyncio.sleep(3)
                
            return success, actually_uploaded, all_messages if all_messages else None
        else:
            # 直接上传这组文件
            return await self._upload_media_group_chunk_with_messages(files, chat_id, caption)

    async def _upload_media_group_chunk_with_messages(self, files: List[Path], chat_id: int, caption: Optional[str] = None) -> Tuple[bool, bool, Optional[List[Message]]]:
        """
        上传一个媒体组块并返回消息对象列表
        
        Returns:
            Tuple[bool, bool, Optional[List[Message]]]: (是否成功, 是否实际上传, 消息对象列表)
        """
        if not files:
            return False, False, None
        
        chat_id_str = str(chat_id)
        
        # 过滤已上传的文件
        filtered_files = []
        file_hashes = {}  # 存储文件哈希值
        
        for file in files:
            file_str = str(file)
            # 计算文件哈希
            if file_str in self.file_hash_cache:
                file_hash = self.file_hash_cache[file_str]
            else:
                file_hash = calculate_file_hash(file)
                if file_hash:
                    self.file_hash_cache[file_str] = file_hash
                else:
                    logger.warning(f"无法计算文件哈希值: {file}")
                    continue
            
            # 检查是否已上传
            if self.history_manager.is_file_hash_uploaded(file_hash, chat_id_str):
                logger.info(f"文件 {file.name} (哈希: {file_hash[:8]}...) 已上传到频道 {chat_id_str}，从媒体组中跳过")
                
                # 发送文件已上传事件
                self.emit("file_already_uploaded", {
                    "chat_id": chat_id,
                    "file_name": file.name,
                    "file_path": file_str,
                    "file_hash": file_hash,
                    "media_type": self._get_media_type(file)
                })
            else:
                filtered_files.append(file)
                file_hashes[file_str] = file_hash
        
        # 如果所有文件都已上传过，直接返回成功
        if not filtered_files:
            logger.info(f"媒体组中的所有文件都已上传到频道 {chat_id_str}，跳过整个媒体组")
            return True, False, None  # 成功但没有实际上传新文件
        
        # 如果过滤后只剩一个文件，作为单个文件上传
        if len(filtered_files) == 1:
            logger.info(f"媒体组中只有一个文件需要上传，转为单文件上传")
            success, actually_uploaded, message = await self._upload_single_file_with_message(filtered_files[0], chat_id, caption)
            return success, actually_uploaded, [message] if message else None
        
        # 准备媒体组
        media_group = []
        thumbnails = []  # 记录生成的缩略图文件以便清理
        
        try:
            for i, file in enumerate(filtered_files):
                file_caption = caption if i == 0 else None
                media_type = self._get_media_type(file)
                
                if media_type == "photo":
                    media = InputMediaPhoto(
                        media=str(file),
                        caption=file_caption
                    )
                    media_group.append(media)
                
                elif media_type == "video":
                    # 生成缩略图和获取视频尺寸
                    thumbnail = None
                    width = height = None
                    try:
                        result = await self.video_processor.extract_thumbnail_async(str(file))
                        if result:
                            if isinstance(result, tuple) and len(result) == 3:
                                thumbnail, width, height = result
                            else:
                                thumbnail = result
                            
                            thumbnails.append(thumbnail)
                            if width and height:
                                logger.debug(f"已生成视频缩略图: {thumbnail}, 尺寸: {width}x{height}")
                            else:
                                logger.debug(f"已生成视频缩略图: {thumbnail}")
                    except Exception as e:
                        logger.warning(f"生成视频缩略图失败: {e}")
                    
                    # 创建媒体对象，包含宽度和高度
                    media = InputMediaVideo(
                        media=str(file),
                        caption=file_caption,
                        thumb=thumbnail,
                        supports_streaming=True,
                        width=width,
                        height=height
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
                return False, False, None
            
            # 上传媒体组
            max_retries = 3
            for retry in range(max_retries):
                try:
                    # 捕获任何上传问题
                    logger.info(f"上传媒体组 ({len(media_group)} 个文件)...")
                    
                    start_time = time.time()
                    messages = await self.client.send_media_group(
                        chat_id=chat_id,
                        media=media_group
                    )
                    end_time = time.time()
                    
                    upload_time = end_time - start_time
                    logger.info(f"媒体组上传成功，耗时 {upload_time:.2f} 秒")
                    
                    # 保存上传历史记录
                    for msg in messages:
                        # 获取文件路径和大小
                        if hasattr(msg, 'file') and hasattr(msg.file, 'size'):
                            file_size = msg.file.size
                        else:
                            file_size = 0
                        
                        # 确定媒体类型
                        if msg.photo:
                            file_media_type = "photo"
                        elif msg.video:
                            file_media_type = "video"
                        elif msg.document:
                            file_media_type = "document"
                        elif msg.audio:
                            file_media_type = "audio"
                        else:
                            file_media_type = "unknown"
                        
                        # 用消息ID确定对应的媒体文件
                        # 由于PyroGram不提供足够的信息来确定哪个消息对应哪个文件
                        # 我们假设消息顺序与文件顺序相同
                        idx = min(messages.index(msg), len(filtered_files) - 1)
                        file_path = str(filtered_files[idx])
                        file_hash = file_hashes.get(file_path)
                        
                        if file_hash:
                            # 记录上传
                            self.history_manager.add_upload_record_by_hash(
                                file_hash=file_hash,
                                file_path=file_path,
                                target_channel=chat_id_str,
                                file_size=file_size,
                                media_type=file_media_type
                            )
                    
                    # 发送上传成功事件
                    media_group_info = {
                        "chat_id": chat_id,
                        "media_count": len(media_group),
                        "upload_time": upload_time,
                        "is_group": True,
                        "files": [str(f) for f in filtered_files]
                    }
                    self.emit("media_upload", media_group_info)
                    
                    # 同时为媒体组发送file_uploaded事件
                    self.emit("file_uploaded", f"媒体组({len(media_group)}个文件)", True)
                    
                    return True, True, messages  # 成功且实际上传了新文件，返回消息对象列表
                    
                except FloodWait as e:
                    logger.warning(f"触发FloodWait，等待 {e.x} 秒")
                    await asyncio.sleep(e.x)
                except (MediaEmpty, MediaInvalid) as e:
                    logger.error(f"媒体无效: {e}", error_type="MEDIA", recoverable=True)
                    return False, False, None
                except Exception as e:
                    if retry < max_retries - 1:
                        logger.warning(f"上传失败，将在 {(retry + 1) * 2} 秒后重试: {e}")
                        await asyncio.sleep((retry + 1) * 2)
                    else:
                        logger.error(f"上传媒体组失败，已达到最大重试次数: {e}", error_type="UPLOAD", recoverable=True)
                        return False, False, None
            
            return False, False, None
            
        finally:
            # 清理缩略图
            for thumb in thumbnails:
                try:
                    if os.path.exists(thumb):
                        os.remove(thumb)
                        logger.debug(f"已删除缩略图: {thumb}")
                except Exception as e:
                    logger.warning(f"删除缩略图失败: {e}") 

    async def _upload_files_to_channels_with_copy(self, files: List[Path], targets: List[Tuple[str, int, str]]) -> int:
        """
        将文件上传到多个目标频道（使用消息复制优化）
        
        首先上传到第一个目标频道，如果成功，则使用copy_message复制到其他频道
        如果第一个频道上传失败，则退回到原方法直接上传
        
        Args:
            files: 文件路径列表
            targets: 目标频道列表，元组(channel_id, channel_name, channel_info)
            
        Returns:
            int: 成功上传的文件数量（实际上传的新文件，不包括已经存在的）
        """
        if not files or len(targets) < 2:
            # 如果没有文件或者目标频道少于2个，使用原方法
            return await self._upload_files_to_channels(files, targets)
            
        upload_count = 0
        total_files = len(files)
        
        # 获取第一个目标频道和其他频道
        first_target, first_target_id, first_target_info = targets[0]
        other_targets = targets[1:]
        
        for idx, file in enumerate(files):                      
            # 更新进度
            progress = (idx / total_files) * 100
            self.emit("progress", progress, idx, total_files)
            
            logger.info(f"上传文件 [{file.name}] ({idx+1}/{total_files})")
            
            # 先上传到第一个目标频道
            logger.info(f"上传文件 [{file.name}] 到第一个目标频道 {first_target_info}")
            
            # 上传单个文件并获取消息对象
            success, actually_uploaded, message = await self._upload_single_file_with_message(file, first_target_id)
            
            # 如果上传成功并且是新文件，尝试复制到其他频道
            if success and actually_uploaded and message:
                file_uploaded = True
                
                logger.info(f"文件 [{file.name}] 成功上传到第一个目标频道，将复制消息到其他频道")
                
                # 复制到其他频道
                for target, target_id, target_info in other_targets:
                    try:
                        logger.info(f"复制消息到频道: {target_info}")
                        
                        # 使用copy_message复制消息
                        copied_msg = await self.client.copy_message(
                            chat_id=target_id,
                            from_chat_id=first_target_id,
                            message_id=message.id
                        )
                        
                        logger.info(f"成功复制消息到频道: {target_info}，消息ID: {copied_msg.id if copied_msg else '未知'}")
                        
                        # 如果复制成功，记录上传历史（与直接上传相同）
                        if copied_msg:
                            # 计算文件哈希（复用缓存）
                            file_str = str(file)
                            if file_str in self.file_hash_cache:
                                file_hash = self.file_hash_cache[file_str]
                            else:
                                file_hash = calculate_file_hash(file)
                                if file_hash:
                                    self.file_hash_cache[file_str] = file_hash
                            
                            if file_hash:
                                # 获取文件大小
                                if hasattr(copied_msg, 'file') and hasattr(copied_msg.file, 'size'):
                                    file_size = copied_msg.file.size
                                else:
                                    file_size = get_file_size(file)
                                
                                # 确定媒体类型
                                if copied_msg.photo:
                                    media_type = "photo"
                                elif copied_msg.video:
                                    media_type = "video"
                                elif copied_msg.document:
                                    media_type = "document"
                                elif copied_msg.audio:
                                    media_type = "audio"
                                else:
                                    media_type = self._get_media_type(file)
                                
                                # 记录上传历史
                                self.history_manager.add_upload_record_by_hash(
                                    file_hash=file_hash,
                                    file_path=file_str,
                                    target_channel=str(target_id),
                                    file_size=file_size,
                                    media_type=media_type
                                )
                                
                                # 发送上传成功事件
                                self.emit("media_upload", {
                                    "chat_id": target_id,
                                    "file_name": file.name,
                                    "file_path": file_str,
                                    "file_hash": file_hash,
                                    "media_type": media_type,
                                    "is_copied": True
                                })
                                
                                # 添加明确的日志记录
                                logger.info(f"已记录文件 {file.name} 复制到 {target_info} 的历史记录")
                        
                    except Exception as e:
                        logger.error(f"复制消息到频道 {target_info} 失败: {e}")
                        # 如果复制失败，尝试直接上传
                        logger.info(f"尝试直接上传文件 [{file.name}] 到频道 {target_info}")
                        direct_success, direct_uploaded = await self._upload_single_file(file, target_id)
                        # 直接上传不改变file_uploaded状态
                    
                    # 简单的速率限制
                    await asyncio.sleep(1)
                
                if file_uploaded:
                    upload_count += 1
                
            # 如果第一个频道上传失败/跳过（文件已存在），或者没有消息对象
            elif not success or not message:
                logger.warning(f"文件 [{file.name}] 上传到第一个目标频道失败或跳过，将直接上传到其他频道")
                
                # 尝试直接上传到其他频道
                file_uploaded = False
                for target, target_id, target_info in other_targets:
                    logger.info(f"上传文件 [{file.name}] 到 {target_info}")
                    direct_success, direct_uploaded = await self._upload_single_file(file, target_id)
                    if direct_success and direct_uploaded:
                        file_uploaded = True
                    
                    # 简单的速率限制
                    await asyncio.sleep(1)
                
                if file_uploaded:
                    upload_count += 1
            
            # 如果上传成功但文件已存在
            elif success and not actually_uploaded:
                logger.info(f"文件 {file.name} 已存在于第一个目标频道，检查其他频道")
                
                # 检查其他频道是否也已上传
                file_str = str(file)
                file_hash = self.file_hash_cache.get(file_str)
                if not file_hash:
                    file_hash = calculate_file_hash(file)
                    if file_hash:
                        self.file_hash_cache[file_str] = file_hash
                
                if file_hash:
                    for target, target_id, target_info in other_targets:
                        target_id_str = str(target_id)
                        if not self.history_manager.is_file_hash_uploaded(file_hash, target_id_str):
                            logger.info(f"文件 {file.name} 在频道 {target_info} 中不存在，尝试直接上传")
                            direct_success, direct_uploaded = await self._upload_single_file(file, target_id)
                            # 这种情况下不增加upload_count，因为文件在第一个频道已经存在
                        else:
                            logger.info(f"文件 {file.name} 在频道 {target_info} 中已存在，跳过")
                        
                        # 简单的速率限制
                        await asyncio.sleep(1)
            
            # 间隔时间
            await asyncio.sleep(0.5)
        
        return upload_count 