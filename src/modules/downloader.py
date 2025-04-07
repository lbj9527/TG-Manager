"""
下载模块，负责下载历史消息的媒体文件
"""

import os
import time
import asyncio
import threading
import queue
import concurrent.futures
import random
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Union, Any, Optional, Set, Tuple, Callable

from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait

from src.utils.ui_config_manager import UIConfigManager
from src.utils.config_utils import convert_ui_config_to_dict
from src.utils.channel_resolver import ChannelResolver
from src.utils.history_manager import HistoryManager
from src.utils.logger import get_logger
from src.utils.events import EventEmitter
from src.utils.controls import CancelToken, PauseToken, TaskContext
from src.utils.logger_event_adapter import LoggerEventAdapter

# 仅用于内部调试，不再用于UI输出
_logger = get_logger()

class Downloader(EventEmitter):
    """
    下载模块，负责下载历史消息的媒体文件
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
        # 初始化事件发射器
        super().__init__()
        
        self.client = client
        self.ui_config_manager = ui_config_manager
        self.channel_resolver = channel_resolver
        self.history_manager = history_manager
        
        # 创建日志事件适配器
        self.log = LoggerEventAdapter(self)
        
        # 获取UI配置并转换为字典
        ui_config = self.ui_config_manager.get_ui_config()
        self.config = convert_ui_config_to_dict(ui_config)
        
        # 获取下载配置
        self.download_config = self.config.get('DOWNLOAD', {})
        self.general_config = self.config.get('GENERAL', {})
        
        # 创建下载目录
        self.download_path = Path(self.download_config.get('download_path', 'downloads'))
        self.download_path.mkdir(exist_ok=True)
        
        # 创建下载队列和线程
        self.download_queue = queue.Queue(maxsize=200)  # 增大队列容量
        self.is_running = False
        self.file_writer_thread = None
        self.writer_threads = []
        
        # 创建文件写入线程池
        self.writer_pool_size = min(32, os.cpu_count() * 2)  # 写入线程池大小：CPU核心数的2倍，最大32
        
        # 设置并行下载数量
        self.max_concurrent_downloads = self.download_config.get('max_concurrent_downloads', 10)  # 从配置读取最大并行下载数
        self.active_downloads = 0  # 当前活跃下载数
        self.download_semaphore = asyncio.Semaphore(self.max_concurrent_downloads)
        
        # 统计信息
        self.download_start_time = None
        self.download_count = 0
        self.total_downloaded_bytes = 0
        
        # FloodWait处理
        self.flood_wait_lock = asyncio.Lock()
        self.last_flood_wait_time = 0
        self.last_flood_wait_time_stamp = 0
        self.flood_wait_count = 0
        self.consecutive_floods = 0
        # 初始自适应延迟时间，单位秒
        self.adaptive_delay = 0.5
        # API错误统计
        self.api_errors = {}
        
        # 是否使用关键词下载模式
        self.use_keywords = False
        
        # 任务控制
        self.task_context = None
    
    async def download_media_from_channels(self, task_context: Optional[TaskContext] = None):
        """
        从配置的源频道下载媒体文件
        
        Args:
            task_context: 任务上下文，用于控制任务执行
        """
        # 初始化任务上下文
        self.task_context = task_context or TaskContext()
        
        mode = "关键词下载" if self.use_keywords else "普通下载"
        status_message = f"开始从频道下载媒体文件（并行下载模式 - {mode}）"
        self.log.status(status_message)
        
        info_message = f"最大并行下载数: {self.max_concurrent_downloads}, 写入线程数: {self.writer_pool_size}"
        self.log.info(info_message)
        
        # 重置统计信息
        self.download_start_time = time.time()
        self.download_count = 0
        self.total_downloaded_bytes = 0
        
        # 重置FloodWait计数器
        self.flood_wait_count = 0
        self.last_flood_wait_time = 0
        self.last_flood_wait_time_stamp = 0
        self.consecutive_floods = 0
        self.adaptive_delay = 0.5
        self.api_errors = {}
        
        try:
            # 启动文件写入线程
            self.is_running = True
            self.file_writer_thread = threading.Thread(target=self._file_writer_worker)
            self.file_writer_thread.daemon = True
            self.file_writer_thread.start()
            
            # 获取下载设置列表
            download_settings = self.download_config.get('downloadSetting', [])
            
            if len(download_settings) == 0:
                self.log.warning("未配置任何下载设置，请在config.json的DOWNLOAD.downloadSetting数组中添加配置")
                return
                
            self.log.info(f"配置的下载设置数量: {len(download_settings)}")
            
            # 创建所有下载任务的集合
            all_download_tasks = []
            
            # 遍历每个下载设置
            for setting in download_settings:
                # 检查是否已取消
                if not await self.task_context.check_continue():
                    self.log.status("下载任务已取消")
                    return
                
                source_channel = setting.get('source_channels', [])
                start_id = setting.get('start_id', 0)
                end_id = setting.get('end_id', 0)
                media_types = setting.get('media_types', [])
                keywords = setting.get('keywords', []) if self.use_keywords else []
                
                if self.use_keywords:
                    self.log.info(f"准备从频道 {source_channel} 下载媒体文件，关键词: {keywords}")
                else:
                    self.log.info(f"准备从频道 {source_channel} 下载媒体文件")
                
                await self._process_channel_for_download(source_channel, start_id, end_id, media_types, keywords, all_download_tasks)
            
            # 使用批量处理的方式并行下载
            total_messages = len(all_download_tasks)
            if total_messages == 0:
                self.log.info("没有符合条件的消息需要下载")
                return
            
            self.log.status(f"开始下载 {total_messages} 条消息中的媒体文件")
            
            # 创建下载工作者协程
            num_workers = min(self.max_concurrent_downloads, total_messages)
            downloads_per_worker = total_messages // num_workers
            
            # 创建工作队列
            work_queue = asyncio.Queue()
            
            # 将所有任务放入队列
            for task in all_download_tasks:
                await work_queue.put(task)
            
            # 创建工作协程
            workers = []
            for i in range(num_workers):
                worker = asyncio.create_task(self._download_worker(i, work_queue))
                workers.append(worker)
                
            # 等待所有工作协程完成
            await asyncio.gather(*workers)
            
            # 等待队列中的所有文件写入完成
            while not self.download_queue.empty():
                self.log.info(f"队列中还有 {self.download_queue.qsize()} 个文件等待写入")
                self.emit("progress", -1, self.download_count, total_messages, remaining=self.download_queue.qsize())
                await asyncio.sleep(1)
                
            # 停止文件写入线程
            self.is_running = False
            if self.file_writer_thread:
                self.file_writer_thread.join(timeout=60)
                
            # 计算总体统计信息
            total_time = time.time() - self.download_start_time
            avg_speed_kb = self.total_downloaded_bytes / (total_time * 1024) if total_time > 0 else 0
            summary = f"下载完成 | 总文件: {self.download_count}个 | 总大小: {self.total_downloaded_bytes/1024/1024:.2f}MB | 总耗时: {total_time:.2f}秒 | 平均速度: {avg_speed_kb:.2f}KB/s"
            self.log.info(summary)
            self.emit("complete", True, {
                "total_files": self.download_count,
                "total_size": self.total_downloaded_bytes,
                "total_time": total_time,
                "avg_speed": avg_speed_kb
            })
            self.log.status("所有频道的媒体文件下载完成")
            
        except Exception as e:
            self.log.error(f"下载过程中发生错误: {e}")
            import traceback
            error_details = traceback.format_exc()
            _logger.error(error_details)  # 记录到内部日志
            self.log.error(str(e), error_type="DOWNLOAD", recoverable=False, details=error_details)
            self.is_running = False
    
    async def _download_worker(self, worker_id: int, queue: asyncio.Queue):
        """
        下载工作协程，从队列获取任务并下载
        
        Args:
            worker_id: 工作协程ID
            queue: 下载任务队列
        """
        worker_info = f"下载工作协程-{worker_id}"
        self.log.info(f"{worker_info} 启动")
        
        while True:
            # 检查是否已取消
            if self.task_context and self.task_context.cancel_token.is_cancelled:
                self.log.info(f"{worker_info} 检测到取消信号，退出")
                break
                
            # 等待暂停恢复
            if self.task_context:
                await self.task_context.wait_if_paused()
            
            try:
                # 获取下一个下载任务
                message, save_path, channel_id, channel = await queue.get()
                
                try:
                    # 获取媒体类型
                    media_type = self._get_media_type(message)
                    if not media_type:
                        self.log.warning(f"{worker_info} 消息没有支持的媒体类型: {message.id}")
                        queue.task_done()
                        continue
                    
                    # 获取媒体组ID
                    group_id = str(message.media_group_id) if message.media_group_id else f"single_{message.id}"
                    
                    async with self.download_semaphore:
                        self.active_downloads += 1
                        
                        worker_status = f"{worker_info} 开始下载: {media_type} - {message.id}"
                        self.log.debug(worker_status)
                        
                        # 下载文件
                        download_start_time = time.time()
                        estimated_size = self._estimate_media_size(message)
                        
                        # 发射媒体下载开始事件
                        self.emit("media_download_start", message.id, media_type, str(save_path), estimated_size)
                        
                        try:
                            # 设置超时机制
                            download_timeout = 90  # 90秒超时
                            try:
                                # 使用超时控制下载文件操作
                                file_path = await asyncio.wait_for(
                                    self._download_media_file(message, str(save_path), worker_id),
                                    timeout=download_timeout
                                )
                                
                                if file_path:
                                    # 计算下载耗时和速度
                                    download_time = time.time() - download_start_time
                                    file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
                                    speed_kb = (file_size / download_time / 1024) if download_time > 0 else 0
                                    
                                    log_msg = f"{worker_info} 下载完成: {file_path} | 大小: {file_size/1024:.2f}KB | 耗时: {download_time:.2f}秒 | 速度: {speed_kb:.2f}KB/s"
                                    self.log.debug(log_msg)
                                    
                                    # 发射媒体下载完成事件
                                    self.emit("media_download", message.id, media_type, file_path, file_size, download_time, speed_kb)
                                    
                                    # 更新下载历史
                                    self.history_manager.add_download_record(channel, message.id, channel_id)
                                else:
                                    self.log.warning(f"{worker_info} 下载失败或无需下载: message_id={message.id}")
                                    self.emit("media_download_failed", message.id, media_type, "下载失败或无需下载")
                                    
                            except asyncio.TimeoutError:
                                self.log.error(f"{worker_info} 下载超时: message_id={message.id}，超过{download_timeout}秒")
                                self.emit("media_download_failed", message.id, media_type, "下载超时")
                            except Exception as e:
                                self.log.error(f"{worker_info} 下载出错: {e}")
                                self.emit("error", str(e), error_type="DOWNLOAD", recoverable=True, message_id=message.id)
                            
                        except FloodWait as e:
                            self.log.warning(f"触发FloodWait，等待 {e.x} 秒")
                            self.emit("error", f"触发FloodWait，等待 {e.x} 秒", error_type="FLOOD_WAIT", recoverable=True, wait_time=e.x)
                            await self._handle_flood_wait(e.x)
                            continue
                            
                        finally:
                            self.active_downloads -= 1
                            
                except Exception as e:
                    self.log.error(f"{worker_info} 处理消息时出错: {e}")
                    self.emit("error", str(e), error_type="MESSAGE_PROCESSING", recoverable=True)
                    
                finally:
                    # 标记任务完成
                    queue.task_done()
                    
            except asyncio.CancelledError:
                # 协程被取消
                self.log.info(f"{worker_info} 协程被取消")
                break
                
            except Exception as e:
                self.log.error(f"{worker_info} 发生未预期错误: {e}")
                self.emit("error", str(e), error_type="WORKER", recoverable=True)
                # 继续循环，尝试下一个任务
                
        self.log.info(f"{worker_info} 退出")

    def _file_writer_worker(self):
        """
        文件写入线程，从队列中取出内存中的媒体数据并写入文件
        """
        self.log.status("文件写入线程启动")
        
        # 创建写入线程池
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.writer_pool_size) as executor:
            futures = []
            
            while self.is_running or not self.download_queue.empty():
                try:
                    # 非阻塞模式从队列获取数据，超时时间0.5秒
                    try:
                        item = self.download_queue.get(timeout=0.5)
                    except queue.Empty:
                        continue
                    
                    # 解包队列项
                    file_path, data, message_id, channel_id, media_type = item
                    
                    # 提交写入任务到线程池
                    future = executor.submit(
                        self._write_file, file_path, data, message_id, channel_id, media_type
                    )
                    futures.append(future)
                    
                    # 移除已完成的future
                    futures = [f for f in futures if not f.done()]
                    
                except Exception as e:
                    self.log.error(f"文件写入线程处理队列项时出错: {e}", error_type="FILE_WRITER", recoverable=True)
            
            # 等待所有未完成的任务
            self.log.status(f"等待 {len(futures)} 个文件写入任务完成...")
            concurrent.futures.wait(futures)
        
        self.log.status("文件写入线程退出")
    
    def _write_file(self, file_path, data, message_id, channel_id, media_type):
        """
        将数据写入文件
        
        Args:
            file_path: 文件路径
            data: 文件数据
            message_id: 消息ID
            channel_id: 频道ID
            media_type: 媒体类型
        """
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # 写入临时文件
            temp_path = f"{file_path}.tmp"
            with open(temp_path, 'wb') as f:
                # 检查media_data类型，处理BytesIO对象
                if hasattr(data, 'getvalue'):
                    # 如果是BytesIO或类似IO对象，获取其值
                    f.write(data.getvalue())
                    _logger.debug(f"处理BytesIO对象并写入文件 {temp_path}")
                else:
                    # 如果已经是bytes对象，直接写入
                    f.write(data)
                    _logger.debug(f"直接写入bytes数据到文件 {temp_path}")
                
            # 重命名为最终文件名
            if os.path.exists(file_path):
                os.remove(file_path)
            os.rename(temp_path, file_path)
            
            # 增加下载计数和总字节数
            file_size = len(data)
            self.download_count += 1
            self.total_downloaded_bytes += file_size
            
            _logger.debug(f"文件写入成功: {file_path} (大小: {file_size/1024:.2f}KB)")
            self.emit("file_written", file_path, file_size, message_id, channel_id, media_type)
            
            # 更新下载历史
            self.history_manager.add_download_record(channel_id, message_id, channel_id)
            
        except Exception as e:
            self.log.error(f"写入文件失败: {file_path} - {e}", error_type="FILE_WRITE", recoverable=True, file_path=file_path)

    async def _download_message_media_to_memory(self, message: Message, download_path: Path, chat_id: int, channel: str) -> bool:
        """
        下载消息媒体到内存
        
        Args:
            message: 消息对象
            download_path: 下载目录路径
            chat_id: 聊天ID
            channel: 频道名称
            
        Returns:
            bool: 是否成功下载
        """
        # 检查是否已取消
        if self.task_context and self.task_context.cancel_token.is_cancelled:
            return False
            
        # 等待暂停恢复
        if self.task_context:
            await self.task_context.wait_if_paused()
        
        try:
            # 检查消息类型
            media_type = self._get_media_type(message)
            if not media_type:
                return False
                
            # 检查是否已经下载过该消息
            if self.history_manager.is_downloaded(chat_id, message.id):
                self.log.debug(f"消息已下载过: {channel} {message.id}")
                self.emit("media_skipped", message.id, media_type, "already_downloaded")
                return False
                
            # 获取媒体文件名
            file_name = self._get_media_file_name(message, media_type)
            if not file_name:
                return False
                
            # 构建媒体组目录路径
            media_group_id = getattr(message, 'media_group_id', None)
            if media_group_id:
                # 确保media_group_id是安全的文件夹名
                safe_group_id = self._get_safe_filename(str(media_group_id))
                media_path = download_path / safe_group_id
            else:
                # 单条消息使用message_id作为目录
                media_path = download_path / f"single_{message.id}"
                
            # 创建消息文本文件
            caption = message.caption or message.text or ""
            if caption:
                # 确保目录存在
                media_path.mkdir(exist_ok=True, parents=True)
                # 保存消息文本为title.txt
                try:
                    with open(media_path / "title.txt", "w", encoding="utf-8") as f:
                        f.write(caption)
                except Exception as e:
                    self.log.error(f"保存消息文本失败: {e}")
                    self.emit("error", str(e), error_type="FILE_WRITE", recoverable=True)
            
            # 构建完整的文件路径
            file_path = media_path / file_name
            
            # 发出媒体发现事件
            self.emit("media_found", message.id, media_type, str(file_path), media_group_id)
            
            # 尝试下载媒体
            start_time = time.time()
            
            try:
                # 从消息下载媒体文件
                download_result = await self._download_media_to_memory(message, media_type)
                if not download_result:
                    self.log.warning(f"下载失败: {channel} {message.id} - {file_name}")
                    self.emit("media_download_failed", message.id, media_type, "download_failed")
                    return False
                
                media_data, file_id = download_result
                
                # 计算下载耗时
                download_time = time.time() - start_time
                file_size = len(media_data) if media_data else 0
                
                # 验证文件大小
                if not media_data or file_size == 0:
                    self.log.warning(f"下载的媒体文件大小为0: {channel} {message.id} - {file_name}")
                    self.emit("media_download_failed", message.id, media_type, "zero_size")
                    return False
                
                # 放入文件写入队列
                self.download_queue.put((str(file_path), media_data, message.id, chat_id, media_type))
                
                # 计算下载速度
                speed = file_size / (download_time * 1024) if download_time > 0 else 0  # KB/s
                self.log.debug(f"下载成功: {file_name} | 大小: {file_size/1024:.2f}KB | 耗时: {download_time:.2f}秒 | 速度: {speed:.2f}KB/s")
                
                return True
                
            except FloodWait as e:
                self.log.warning(f"触发FloodWait，等待 {e.x} 秒")
                self.emit("error", f"触发FloodWait，等待 {e.x} 秒", error_type="FLOOD_WAIT", recoverable=True, wait_time=e.x)
                await self._handle_flood_wait(e.x)
                return False
                
            except Exception as e:
                self.log.error(f"下载媒体文件时出错: {e}")
                self.emit("error", str(e), error_type="DOWNLOAD", recoverable=True, message_id=message.id)
                return False
                
        except Exception as e:
            self.log.error(f"处理媒体消息时出错: {e}")
            self.emit("error", str(e), error_type="MESSAGE_PROCESSING", recoverable=True, message_id=message.id)
            return False

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
            self.log.error(f"无法获取有效的消息ID范围: chat_id={chat_id}, start_id={start_id}, end_id={end_id}")
            return
            
        # 计算需要获取的消息数量
        total_messages = actual_end_id - actual_start_id + 1
        self.log.info(f"开始获取消息: chat_id={chat_id}, 开始id={actual_start_id}, 结束id={actual_end_id}，共{total_messages}条消息")
        
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
                
                self.log.info(f"尝试获取消息批次 (第{attempt_count}次): chat_id={chat_id}, offset_id={current_offset_id}, 剩余未获取消息数={len(message_ids_to_fetch)}")
                
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
                            self.log.debug(f"消息ID {message.id} 小于当前需要获取的最小ID {min(message_ids_to_fetch, default=actual_start_id)}，停止当前批次获取")
                            break
                except FloodWait as e:
                    # 使用全局FloodWait处理机制
                    self.log.warning(f"获取消息批次时遇到FloodWait, offset_id={current_offset_id}, limit={batch_size}")
                    await self._handle_flood_wait(e.x)
                    continue
                
                self.log.info(f"已获取 {batch_success_count} 条消息，剩余 {len(message_ids_to_fetch)} 条消息待获取")
                
                # 如果此批次没有获取到任何消息，说明可能有些消息不存在或已被删除
                if batch_success_count == 0:
                    # 检查是否需要缩小获取范围，尝试一条一条地获取
                    if batch_size > 1:
                        self.log.info(f"未获取到任何消息，尝试减小批次大小")
                        max_batch_size = max(1, max_batch_size // 2)
                    else:
                        # 如果已经是最小批次大小，且仍未获取到消息，记录并移除前一部分消息ID
                        # 这些可能是不存在或已删除的消息
                        if message_ids_to_fetch:
                            ids_to_skip = message_ids_to_fetch[:min(10, len(message_ids_to_fetch))]
                            self.log.warning(f"无法获取以下消息ID，可能不存在或已被删除：{ids_to_skip}")
                            for id_to_skip in ids_to_skip:
                                message_ids_to_fetch.remove(id_to_skip)
                
                # 避免频繁请求，休眠一小段时间
                await asyncio.sleep(0.5)
            
            # 检查是否还有未获取的消息
            if message_ids_to_fetch:
                self.log.warning(f"以下消息ID无法获取，将被跳过：{message_ids_to_fetch}")
            
            # 将获取到的消息按ID升序排序（从旧到新）
            all_messages = [fetched_messages_map[msg_id] for msg_id in sorted(fetched_messages_map.keys())]
            self.log.info(f"消息获取完成，共获取{len(all_messages)}/{total_messages}条消息，已按ID升序排序（从旧到新）")
            
            # 逐个返回排序后的消息
            for message in all_messages:
                yield message
        
        except FloodWait as e:
            # 使用全局FloodWait处理机制
            await self._handle_flood_wait(e.x)
        except Exception as e:
            self.log.error(f"获取消息失败: {e}")
            self.log.exception("详细错误信息")
    
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

    async def _handle_flood_wait(self, wait_time, message_id=None):
        """
        处理FloodWait异常，实现全局等待和自适应延迟
        
        Args:
            wait_time: 需要等待的秒数
            message_id: 触发FloodWait的消息ID，用于日志
        """
        async with self.flood_wait_lock:
            self.flood_wait_count += 1
            current_time = time.time()
            
            # 计算与上次FloodWait的时间间隔
            time_since_last = current_time - (self.last_flood_wait_time_stamp if hasattr(self, 'last_flood_wait_time_stamp') else 0)
            self.last_flood_wait_time = wait_time
            self.last_flood_wait_time_stamp = current_time
            
            # 动态调整自适应延迟
            if not hasattr(self, 'consecutive_floods'):
                self.consecutive_floods = 0
                
            # 如果短时间内（30秒内）再次触发FloodWait，视为连续触发
            if time_since_last < 30:
                self.consecutive_floods += 1
            else:
                self.consecutive_floods = 1  # 重置连续计数
            
            # 根据连续触发次数和请求的等待时间动态调整延迟
            if self.consecutive_floods > 1:
                # 连续触发，大幅增加延迟
                self.adaptive_delay = min(5.0, self.adaptive_delay * 2.0)
                self.log.warning(f"连续触发FloodWait ({self.consecutive_floods}次)，将全局延迟增加至 {self.adaptive_delay:.1f}秒")
            elif wait_time > 5:
                # 长时间的FloodWait表示较严重的限制，增加延迟
                self.adaptive_delay = min(3.0, self.adaptive_delay * 1.5)
                self.log.warning(f"收到长时间FloodWait ({wait_time}秒)，将全局延迟增加至 {self.adaptive_delay:.1f}秒")
            elif self.flood_wait_count > 5:
                # 触发次数过多，逐渐增加延迟
                self.adaptive_delay = min(2.0, self.adaptive_delay * 1.2)
                self.log.warning(f"已触发 {self.flood_wait_count} 次FloodWait，将全局延迟增加至 {self.adaptive_delay:.1f}秒")
                
            # 每50次FloodWait，记录一次统计信息
            if self.flood_wait_count % 50 == 0:
                self.log.warning(f"FloodWait统计: 总计{self.flood_wait_count}次，当前全局延迟{self.adaptive_delay:.1f}秒")
            
            # 记录详细日志
            info = f"消息ID: {message_id}" if message_id else ""
            self.log.warning(f"触发Telegram速率限制，等待 {wait_time} 秒 {info} (第{self.flood_wait_count}次)")
        
        # 等待Telegram要求的时间
        await asyncio.sleep(wait_time)
        
        # 添加自适应延迟，抖动范围与自适应延迟成比例
        jitter = random.uniform(0, self.adaptive_delay * 0.3)
        await asyncio.sleep(self.adaptive_delay + jitter)
        
        return True  # 返回True表示FloodWait已处理完成 

    async def _process_channel_for_download(self, channel, start_id, end_id, media_types, keywords, all_download_tasks):
        """
        处理单个频道的下载流程
        
        Args:
            channel: 频道标识
            start_id: 起始消息ID
            end_id: 结束消息ID
            media_types: 媒体类型列表
            keywords: 关键词列表
            all_download_tasks: 下载任务列表
        """
        try:
            # 解析频道ID
            real_channel_id = await self.channel_resolver.get_channel_id(channel)
            # 获取频道信息
            channel_info, (channel_title, _) = await self.channel_resolver.format_channel_info(real_channel_id)
            self.log.info(f"解析频道: {channel_info}")
            
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
            self.log.info(f"已下载的消息数量: {len(downloaded_messages)}")
            
            # 先整理所有消息，按照媒体组进行分组
            messages_by_group = {}  # 媒体组ID -> 消息列表
            matched_groups = set()  # 匹配关键词的媒体组ID
            matched_keywords = {}   # 媒体组ID -> 匹配的关键词
            
            all_messages = []
            try:
                # 第一轮遍历：收集所有消息并按媒体组分组
                async for message in self._iter_messages(real_channel_id, start_id, end_id):
                    all_messages.append(message)
            except Exception as e:
                if "PEER_ID_INVALID" in str(e):
                    self.log.error(f"无法获取频道 {channel} 的消息: 频道ID无效或未加入该频道")
                    return
                else:
                    self.log.error(f"获取频道 {channel} 的消息失败: {e}")
                    import traceback
                    self.log.error(traceback.format_exc())
                    return
            
            # 处理收集到的所有消息
            for message in all_messages:
                if message.id in downloaded_messages:
                    self.log.info(f"消息 {message.id} 已下载，跳过")
                    continue
                
                # 确定媒体组ID
                group_id = str(message.media_group_id) if message.media_group_id else f"single_{message.id}"
                
                # 将消息添加到对应的媒体组
                if group_id not in messages_by_group:
                    messages_by_group[group_id] = []
                messages_by_group[group_id].append(message)
                
                # 在关键词模式下，检查消息文本是否包含关键词
                if self.use_keywords and keywords and group_id not in matched_groups:
                    # 获取消息文本（正文或说明文字）
                    text = message.text or message.caption or ""
                    if text:
                        # 检查文本是否包含任何关键词
                        for keyword in keywords:
                            if keyword.lower() in text.lower():
                                matched_groups.add(group_id)
                                matched_keywords[group_id] = keyword
                                self.log.info(f"媒体组 {group_id} (消息ID: {message.id}) 匹配关键词: {keyword}")
                                break
            
            # 准备下载任务
            messages_to_download = []
            
            # 第二轮处理：处理每个媒体组
            for group_id, messages in messages_by_group.items():
                # 如果是关键词模式且没有匹配关键词，则跳过整个媒体组
                if self.use_keywords and keywords and group_id not in matched_groups:
                    self.log.debug(f"媒体组 {group_id} 不包含任何关键词，跳过")
                    continue
                
                current_channel_path = channel_path
                
                # 如果匹配了关键词，为该媒体组设置关键词目录
                if self.use_keywords and organize_by_keywords and group_id in matched_groups:
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
                
                # 将媒体组中的所有消息添加到下载列表
                for message in messages:
                    messages_to_download.append((message, current_channel_path, real_channel_id, channel))
                
                # 如果是媒体组，记录日志
                if group_id.startswith("single_"):
                    self.log.info(f"准备下载单条消息: ID={messages[0].id}")
                else:
                    self.log.info(f"准备下载媒体组 {group_id}: 包含 {len(messages)} 条消息, IDs={[m.id for m in messages]}")
            
            self.log.info(f"找到 {len(messages_to_download)} 条需要下载的消息")
            all_download_tasks.extend(messages_to_download)
            
        except Exception as e:
            self.log.error(f"处理频道 {channel} 下载失败: {e}")
            import traceback
            self.log.error(traceback.format_exc()) 

    def _get_media_type(self, message: Message) -> Optional[str]:
        """
        获取消息的媒体类型
        
        Args:
            message: 消息对象
            
        Returns:
            Optional[str]: 媒体类型，如果没有支持的媒体类型则返回None
        """
        media_types = self.download_config.get('media_types', [])
        
        if message.photo and "photo" in media_types:
            return "photo"
        elif message.video and "video" in media_types:
            return "video"
        elif message.document and "document" in media_types:
            return "document"
        elif message.audio and "audio" in media_types:
            return "audio"
        elif message.animation and "animation" in media_types:
            return "animation"
        elif message.sticker and "sticker" in media_types:
            return "sticker"
        elif message.voice and "voice" in media_types:
            return "voice"
        elif message.video_note and "video_note" in media_types:
            return "video_note"
        
        return None
    
    def _get_media_file_name(self, message: Message, media_type: str) -> Optional[str]:
        """
        获取媒体文件名
        
        Args:
            message: 消息对象
            media_type: 媒体类型
            
        Returns:
            Optional[str]: 文件名，如果无法确定则返回None
        """
        chat_id = message.chat.id
        message_id = message.id
        
        if media_type == "photo":
            return f"{chat_id}-{message_id}-photo.jpg"
        elif media_type == "video":
            file_name = getattr(message.video, "file_name", None)
            return f"{chat_id}-{message_id}-{file_name}" if file_name else f"{chat_id}-{message_id}-video.mp4"
        elif media_type == "document":
            file_name = getattr(message.document, "file_name", None)
            return f"{chat_id}-{message_id}-{file_name}" if file_name else f"{chat_id}-{message_id}-document"
        elif media_type == "audio":
            file_name = getattr(message.audio, "file_name", None)
            return f"{chat_id}-{message_id}-{file_name}" if file_name else f"{chat_id}-{message_id}-audio.mp3"
        elif media_type == "animation":
            return f"{chat_id}-{message_id}-animation.mp4"
        elif media_type == "sticker":
            return f"{chat_id}-{message_id}-sticker.webp"
        elif media_type == "voice":
            return f"{chat_id}-{message_id}-voice.ogg"
        elif media_type == "video_note":
            return f"{chat_id}-{message_id}-video_note.mp4"
        
        return None
    
    def _get_safe_filename(self, filename: str) -> str:
        """
        获取安全的文件名，移除不允许的字符
        
        Args:
            filename: 原始文件名
            
        Returns:
            str: 安全的文件名
        """
        # 替换Windows和Unix系统不允许的文件名字符
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # 替换控制字符
        filename = ''.join(c if ord(c) >= 32 else '_' for c in filename)
        
        # 处理特殊文件名
        if filename in {'.', '..', '', ' '}:
            filename = '_' + filename
            
        # 限制长度
        if len(filename) > 255:
            filename = filename[:250] + '...'
            
        return filename
    
    def _estimate_media_size(self, message: Message) -> int:
        """
        估计媒体文件大小
        
        Args:
            message: 消息对象
            
        Returns:
            int: 预估的文件大小（字节）
        """
        if message.photo:
            # 选择最大尺寸的照片
            photo = message.photo
            if isinstance(photo, list) and photo:
                photo = photo[-1]  # 获取最高质量的照片
                return photo.file_size if hasattr(photo, 'file_size') and photo.file_size else 0
        elif message.video:
            return message.video.file_size if hasattr(message.video, 'file_size') and message.video.file_size else 0
        elif message.document:
            return message.document.file_size if hasattr(message.document, 'file_size') and message.document.file_size else 0
        elif message.audio:
            return message.audio.file_size if hasattr(message.audio, 'file_size') and message.audio.file_size else 0
        elif message.animation:
            return message.animation.file_size if hasattr(message.animation, 'file_size') and message.animation.file_size else 0
        elif message.sticker:
            return message.sticker.file_size if hasattr(message.sticker, 'file_size') and message.sticker.file_size else 0
        elif message.voice:
            return message.voice.file_size if hasattr(message.voice, 'file_size') and message.voice.file_size else 0
        elif message.video_note:
            return message.video_note.file_size if hasattr(message.video_note, 'file_size') and message.video_note.file_size else 0
        
        return 0
    
    async def _download_media_to_memory(self, message: Message, media_type: str) -> Optional[Tuple[bytes, str]]:
        """
        下载媒体到内存
        
        Args:
            message: 消息对象
            media_type: 媒体类型
            
        Returns:
            Optional[Tuple[bytes, str]]: (媒体数据, 文件ID)元组，如果下载失败则返回None
        """
        max_retries = 3
        retry_count = 0
        
        while retry_count <= max_retries:
            try:
                # 检查取消和暂停
                if self.task_context:
                    if self.task_context.cancel_token.is_cancelled:
                        return None
                    await self.task_context.wait_if_paused()
                
                # 执行下载
                file_id = None
                if media_type == "photo":
                    # 选择最大尺寸的照片
                    photo = message.photo
                    self.log.debug(f"Photo对象类型: {type(photo)}, 值: {photo}")
                    
                    # 修复photo处理逻辑
                    if photo:
                        if isinstance(photo, list):
                            # 如果是列表，选择最后一个（最高质量）
                            photo_obj = photo[-1]
                            file_id = photo_obj.file_id
                            self.log.debug(f"从列表中获取photo file_id: {file_id}")
                        else:
                            # 如果不是列表，可能是单个对象
                            file_id = getattr(photo, 'file_id', None)
                            self.log.debug(f"从非列表对象获取photo file_id: {file_id}")
                            
                            # 如果无法获取file_id，直接使用photo本身作为file_id
                            if not file_id and isinstance(photo, str):
                                file_id = photo
                                self.log.debug(f"直接使用photo字符串作为file_id: {file_id}")
                elif media_type == "video":
                    file_id = message.video.file_id
                elif media_type == "document":
                    file_id = message.document.file_id
                elif media_type == "audio":
                    file_id = message.audio.file_id
                elif media_type == "animation":
                    file_id = message.animation.file_id
                elif media_type == "sticker":
                    file_id = message.sticker.file_id
                elif media_type == "voice":
                    file_id = message.voice.file_id
                elif media_type == "video_note":
                    file_id = message.video_note.file_id
                
                if not file_id:
                    self.log.warning(f"无法获取文件ID: {message.id} - {media_type}")
                    return None
                
                # 下载媒体文件
                try:
                    self.log.debug(f"尝试下载媒体，file_id: {file_id}")
                    file_data = await self.client.download_media(file_id, in_memory=True)
                except Exception as e:
                    self.log.error(f"下载媒体file_id={file_id}时出错: {e}")
                    if retry_count < max_retries:
                        retry_count += 1
                        wait_time = 2 ** retry_count
                        self.log.info(f"重试下载 {message.id}，第 {retry_count}/{max_retries} 次，等待 {wait_time}秒")
                        await asyncio.sleep(wait_time)
                        continue
                    return None
                
                # 验证文件数据
                if not file_data:
                    self.log.warning(f"下载返回空数据: {message.id} - {media_type}")
                    if retry_count < max_retries:
                        retry_count += 1
                        wait_time = 2 ** retry_count  # 指数退避
                        self.log.info(f"重试下载 {message.id}，第 {retry_count}/{max_retries} 次，等待 {wait_time}秒")
                        await asyncio.sleep(wait_time)
                        continue
                    return None

                return file_data, file_id
                
            except FloodWait as e:
                self.log.warning(f"触发FloodWait，等待 {e.x} 秒")
                await self._handle_flood_wait(e.x)
                # FloodWait不计入重试次数
                continue
                
            except Exception as e:
                self.log.error(f"下载媒体时出错: {message.id} - {media_type} - {e}")
                if retry_count < max_retries:
                    retry_count += 1
                    wait_time = 2 ** retry_count  # 指数退避
                    self.log.info(f"重试下载 {message.id}，第 {retry_count}/{max_retries} 次，等待 {wait_time}秒")
                    await asyncio.sleep(wait_time)
                else:
                    self.log.error(f"下载失败，已达到最大重试次数: {message.id}")
                    return None
        
        return None 

    async def _download_media_file(self, message: Message, save_path: str, worker_id: int) -> Optional[str]:
        """
        下载消息中的媒体文件到指定路径
        
        Args:
            message: 消息对象
            save_path: 保存路径
            worker_id: 工作协程ID
            
        Returns:
            Optional[str]: 下载成功时返回文件路径，失败时返回None
        """
        # 获取媒体类型
        media_type = self._get_media_type(message)
        if not media_type:
            return None
            
        # 获取文件名
        file_name = self._get_media_file_name(message, media_type)
        if not file_name:
            return None
            
        # 创建保存目录
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        # 构建完整文件路径
        file_path = os.path.join(save_path, file_name)
        
        try:
            # 从消息中下载媒体
            download_result = await self._download_media_to_memory(message, media_type)
            if not download_result:
                return None
                
            media_data, file_id = download_result
            
            # 写入临时文件
            temp_path = f"{file_path}.tmp"
            with open(temp_path, 'wb') as f:
                # 检查media_data类型，处理BytesIO对象
                if hasattr(media_data, 'getvalue'):
                    # 如果是BytesIO或类似IO对象，获取其值
                    f.write(media_data.getvalue())
                    self.log.debug(f"处理BytesIO对象并写入文件 {temp_path}")
                else:
                    # 如果已经是bytes对象，直接写入
                    f.write(media_data)
                    self.log.debug(f"直接写入bytes数据到文件 {temp_path}")
                
            # 重命名为最终文件名
            if os.path.exists(file_path):
                os.remove(file_path)
            os.rename(temp_path, file_path)
            
            # 返回文件路径
            return file_path
            
        except Exception as e:
            self.log.error(f"下载文件失败: {e}")
            self.emit("error", str(e), error_type="FILE_DOWNLOAD", recoverable=True, file_path=file_path)
            return None 