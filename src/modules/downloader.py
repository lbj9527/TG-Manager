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
from typing import List, Dict, Union, Any, Optional, Set, Tuple

from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait

from src.utils.config_manager import ConfigManager
from src.utils.channel_resolver import ChannelResolver
from src.utils.history_manager import HistoryManager
from src.utils.logger import get_logger

logger = get_logger()

class Downloader:
    """
    下载模块，负责下载历史消息的媒体文件
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
        
        # 创建下载队列和线程
        self.download_queue = queue.Queue(maxsize=200)  # 增大队列容量
        self.is_running = False
        self.file_writer_thread = None
        self.writer_threads = []
        
        # 创建文件写入线程池
        self.writer_pool_size = min(32, os.cpu_count() * 2)  # 写入线程池大小：CPU核心数的2倍，最大32
        
        # 设置并行下载数量
        self.max_concurrent_downloads = self.download_config.max_concurrent_downloads  # 从配置读取最大并行下载数
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
    
    async def download_media_from_channels(self):
        """
        从配置的源频道下载媒体文件
        """
        logger.info("开始从频道下载媒体文件（并行下载模式）")
        logger.info(f"最大并行下载数: {self.max_concurrent_downloads}, 写入线程数: {self.writer_pool_size}")
        
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
        
        # 启动文件写入线程
        self.is_running = True
        self.file_writer_thread = threading.Thread(target=self._file_writer_worker)
        self.file_writer_thread.daemon = True
        self.file_writer_thread.start()
        
        try:
            # 获取源频道列表
            source_channels = self.download_config.source_channels
            logger.info(f"配置的源频道数量: {len(source_channels)}")
            
            # 创建任务列表，收集所有需要下载的消息
            all_download_tasks = []
            
            # 遍历每个源频道
            for channel in source_channels:
                logger.info(f"准备从频道 {channel} 下载媒体文件")
                
                try:
                    # 解析频道ID
                    real_channel_id = await self.channel_resolver.get_channel_id(channel)
                    # 获取频道信息
                    channel_info, (channel_title, _) = await self.channel_resolver.format_channel_info(real_channel_id)
                    logger.info(f"解析频道: {channel_info}")
                    
                    # 创建频道目录
                    if self.download_config.organize_by_chat:
                        # 使用"频道标题-频道ID"格式创建目录
                        folder_name = f"{channel_title}-{real_channel_id}"
                        # 确保文件夹名称有效（移除非法字符）
                        folder_name = self._sanitize_filename(folder_name)
                        channel_path = self.download_path / folder_name
                        channel_path.mkdir(exist_ok=True)
                    else:
                        channel_path = self.download_path
                    
                    # 获取已下载的消息ID列表
                    downloaded_messages = self.history_manager.get_downloaded_messages(channel)
                    logger.info(f"已下载的消息数量: {len(downloaded_messages)}")
                    
                    # 设置消息范围
                    start_id = self.download_config.start_id
                    end_id = self.download_config.end_id
                    
                    # 获取所有消息
                    messages_to_download = []
                    try:
                        async for message in self._iter_messages(real_channel_id, start_id, end_id):
                            if message.id not in downloaded_messages:
                                messages_to_download.append((message, channel_path, real_channel_id, channel))
                    except Exception as e:
                        if "PEER_ID_INVALID" in str(e):
                            logger.error(f"无法获取频道 {channel} 的消息: 频道ID无效或未加入该频道")
                            continue
                        else:
                            logger.error(f"获取频道 {channel} 的消息失败: {e}")
                            import traceback
                            logger.error(traceback.format_exc())
                            continue
                    
                    logger.info(f"找到 {len(messages_to_download)} 条需要下载的消息")
                    all_download_tasks.extend(messages_to_download)
                
                except Exception as e:
                    logger.error(f"获取频道 {channel} 的消息失败: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    continue
            
            # 使用批量处理的方式并行下载
            total_messages = len(all_download_tasks)
            if total_messages > 0:
                logger.info(f"共有 {total_messages} 条消息需要下载，使用并行下载")
                
                # 创建下载协程队列系统
                download_queue = asyncio.Queue()
                for task in all_download_tasks:
                    await download_queue.put(task)
                
                # 创建固定数量的下载工作协程
                workers = []
                for i in range(self.max_concurrent_downloads):
                    workers.append(asyncio.create_task(
                        self._download_worker(i, download_queue)
                    ))
                
                # 等待所有消息都被放入队列
                await download_queue.join()
                
                # 取消所有工作协程
                for worker in workers:
                    worker.cancel()
                
                # 等待工作协程被取消
                await asyncio.gather(*workers, return_exceptions=True)
                
                logger.info("所有下载任务已完成")
            
            # 等待队列清空
            logger.info("等待所有文件写入完成...")
            while not self.download_queue.empty():
                logger.info(f"队列中还有 {self.download_queue.qsize()} 个文件等待写入")
                await asyncio.sleep(1)
                
            # 停止文件写入线程
            self.is_running = False
            if self.file_writer_thread:
                self.file_writer_thread.join(timeout=60)
                
            # 计算总体统计信息
            total_time = time.time() - self.download_start_time
            avg_speed_kb = self.total_downloaded_bytes / (total_time * 1024) if total_time > 0 else 0
            logger.info(f"下载完成 | 总文件: {self.download_count}个 | 总大小: {self.total_downloaded_bytes/1024/1024:.2f}MB | 总耗时: {total_time:.2f}秒 | 平均速度: {avg_speed_kb:.2f}KB/s")
            logger.info("所有频道的媒体文件下载完成")
            
        except Exception as e:
            logger.error(f"下载过程中发生错误: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.is_running = False
    
    async def _download_worker(self, worker_id: int, queue: asyncio.Queue):
        """
        下载工作协程，从队列获取任务并下载
        
        Args:
            worker_id: 工作协程ID
            queue: 下载任务队列
        """
        logger.info(f"下载工作协程 {worker_id} 启动")
        while True:
            try:
                # 从队列获取任务
                message, channel_path, real_channel_id, channel = await queue.get()
                
                try:
                    # 下载消息媒体
                    logger.info(f"工作协程 {worker_id} 开始下载消息 {message.id}")
                    result = await self._download_message_media_to_memory(message, channel_path, real_channel_id, channel)
                    if not result:
                        logger.warning(f"工作协程 {worker_id} 下载消息 {message.id} 失败或不包含媒体")
                except Exception as e:
                    logger.error(f"工作协程 {worker_id} 下载消息 {message.id} 时发生错误: {e}")
                finally:
                    # 标记任务完成
                    queue.task_done()
            except asyncio.CancelledError:
                logger.info(f"下载工作协程 {worker_id} 被取消")
                break
            except Exception as e:
                logger.error(f"下载工作协程 {worker_id} 发生错误: {e}")
                # 即使发生错误也要标记任务完成，避免卡住队列
                try:
                    queue.task_done()
                except:
                    pass
    
    def _file_writer_worker(self):
        """
        文件写入工作线程，从队列中获取下载的数据并写入文件
        """
        logger.info(f"文件写入主线程已启动，使用 {self.writer_pool_size} 个写入线程")
        
        # 创建写入线程池
        writer_pool = concurrent.futures.ThreadPoolExecutor(max_workers=self.writer_pool_size)
        active_futures = []
        
        try:
            while self.is_running or not self.download_queue.empty() or active_futures:
                # 清理已完成的任务
                active_futures = [f for f in active_futures if not f.done()]
                
                # 尝试获取新的写入任务
                try:
                    while len(active_futures) < self.writer_pool_size and not self.download_queue.empty():
                        file_info = self.download_queue.get(block=False)
                        future = writer_pool.submit(self._write_file_task, *file_info)
                        active_futures.append(future)
                except queue.Empty:
                    pass
                
                # 检查是否有任务完成或发生异常
                done_futures = [f for f in active_futures if f.done()]
                for future in done_futures:
                    active_futures.remove(future)
                    try:
                        future.result()  # 获取结果，如果有异常会抛出
                    except Exception as e:
                        logger.error(f"文件写入任务异常: {e}")
                
                # 短暂休眠，避免CPU过载
                time.sleep(0.05)
        finally:
            # 等待所有写入任务完成
            for future in active_futures:
                try:
                    future.result(timeout=30)  # 给30秒时间完成
                except Exception as e:
                    logger.error(f"等待文件写入完成时发生异常: {e}")
            
            writer_pool.shutdown(wait=True)
            logger.info("文件写入线程池已关闭")
    
    def _write_file_task(self, file_path, file_data, message_id, channel, real_channel_id):
        """
        单个文件写入任务
        
        Args:
            file_path: 文件路径
            file_data: 文件数据
            message_id: 消息ID
            channel: 频道
            real_channel_id: 真实频道ID
        """
        try:
            start_time = time.time()
            thread_id = threading.get_ident()
            
            # 确保目录存在
            file_path.parent.mkdir(exist_ok=True, parents=True)
            
            # 从BytesIO对象中读取数据并验证
            if hasattr(file_data, 'getvalue'):  # 检查是否为BytesIO对象
                file_data.seek(0)  # 重置读取位置
                bytes_data = file_data.getvalue()
            else:
                bytes_data = file_data  # 已经是字节数据则直接使用
            
            # 如果是空数据，跳过写入
            if bytes_data is None:
                logger.error(f"无法写入文件 {file_path.name}: 数据为None")
                self.download_queue.task_done()
                return
            
            file_size = len(bytes_data)
            
            # 验证文件大小
            if file_size == 0:
                logger.error(f"无法写入文件 {file_path.name}: 文件大小为0")
                self.download_queue.task_done()
                return
            
            # 先写入临时文件，成功后再重命名
            temp_path = file_path.with_suffix(f'.temp{random.randint(1000, 9999)}')
            
            # 写入文件（使用缓冲写入提高性能）
            try:
                with open(temp_path, 'wb', buffering=1024*1024) as f:  # 1MB缓冲区
                    f.write(bytes_data)
                
                # 验证写入后的文件
                if os.path.getsize(temp_path) != file_size:
                    logger.error(f"文件 {file_path.name} 写入验证失败: 预期大小 {file_size} 字节, 实际大小 {os.path.getsize(temp_path)} 字节")
                    # 删除不完整文件
                    try:
                        os.remove(temp_path)
                        logger.info(f"已删除不完整文件: {temp_path.name}")
                    except Exception as e:
                        logger.error(f"删除不完整文件 {temp_path.name} 失败: {e}")
                    
                    self.download_queue.task_done()
                    return
                
                # 重命名临时文件为最终文件名
                try:
                    # 先检查目标文件是否已存在，如果存在则先删除
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    
                    # 重命名临时文件
                    os.rename(temp_path, file_path)
                except Exception as e:
                    logger.error(f"重命名临时文件 {temp_path} 到 {file_path} 失败: {e}")
                    try:
                        # 如果重命名失败，尝试直接复制内容
                        with open(file_path, 'wb') as f:
                            f.write(bytes_data)
                        # 删除临时文件
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                    except Exception as copy_error:
                        logger.error(f"复制文件内容到 {file_path} 失败: {copy_error}")
                        self.download_queue.task_done()
                        return
                
            except (IOError, OSError) as e:
                logger.error(f"文件 {file_path.name} 写入时发生I/O错误: {e}")
                # 清理临时文件
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except:
                        pass
                self.download_queue.task_done()
                return
            
            # 记录下载历史
            self.history_manager.add_download_record(channel, message_id, real_channel_id)
            
            # 更新统计信息（使用锁保证线程安全）
            with threading.Lock():
                self.download_count += 1
                self.total_downloaded_bytes += file_size
            
            elapsed = time.time() - start_time
            
            # 计算平均速度和当前速度
            if self.download_start_time:
                total_elapsed = time.time() - self.download_start_time
                avg_speed = self.total_downloaded_bytes / (total_elapsed * 1024) if total_elapsed > 0 else 0  # KB/s
                current_speed = file_size / (elapsed * 1024) if elapsed > 0 else 0  # KB/s
                
                # 增加当前进度的百分比显示
                progress_pct = self.download_count / (self.download_queue.qsize() + self.download_count) * 100
                
                logger.info(f"写入文件 {file_path.name} 成功 | 线程: {thread_id % 1000} | 大小: {file_size/1024:.1f}KB | 耗时: {elapsed:.2f}秒 | 速度: {current_speed:.1f}KB/s | 平均: {avg_speed:.1f}KB/s | 进度: {progress_pct:.1f}% ({self.download_count}/{self.download_queue.qsize() + self.download_count})")
            else:
                logger.info(f"写入文件 {file_path.name} 成功 | 线程: {thread_id % 1000} | 大小: {file_size/1024:.1f}KB | 耗时: {elapsed:.2f}秒")
            
            # 标记任务完成
            self.download_queue.task_done()
            
        except Exception as e:
            logger.error(f"写入文件 {file_path} 时发生错误: {e}")
            import traceback
            logger.error(traceback.format_exc())
            try:
                self.download_queue.task_done()
            except:
                pass
    
    async def _download_message_media_to_memory(self, message: Message, download_path: Path, chat_id: int, channel: str) -> bool:
        """
        将消息中的媒体下载到内存中，然后加入写入队列
        
        Args:
            message: 消息对象
            download_path: 下载路径
            chat_id: 频道ID
            channel: 原始频道标识符
        
        Returns:
            bool: 是否成功加入下载队列
        """
        media_types = self.download_config.media_types
        max_retries = 5  # 最大重试次数
        retry_count = 0
        
        while retry_count <= max_retries:
            try:
                file_data = None
                file_path = None
                media_type = None
                media_size = 0
                start_time = time.time()
                worker_id = id(asyncio.current_task()) % 1000  # 获取当前任务ID的简短版本
                
                # 检查消息是否有媒体内容
                if not hasattr(message, 'media') or message.media is None:
                    logger.debug(f"消息 {message.id} 不包含媒体内容")
                    return False
                
                # 检查媒体类型并获取估计大小
                if message.photo and "photo" in media_types:
                    file_path = download_path / f"{chat_id}-{message.id}-photo.jpg"
                    media_type = "照片"
                    # 选择最大尺寸的照片
                    photo = message.photo
                    if isinstance(photo, list) and photo:
                        photo = photo[-1]  # 获取最高质量的照片
                        media_size = photo.file_size if hasattr(photo, 'file_size') and photo.file_size else 0
                    logger.info(f"工作协程-{worker_id} 开始下载 {media_type} {message.id} | 预计大小: {media_size/1024:.1f}KB | 尝试 #{retry_count+1}")
                    file_data = await self.client.download_media(message, in_memory=True, file_name=str(file_path.name))
                    
                elif message.video and "video" in media_types:
                    file_name = message.video.file_name
                    if not file_name:
                        file_name = f"{chat_id}-{message.id}-video.mp4"
                    file_path = download_path / f"{chat_id}-{message.id}-{file_name}"
                    media_type = "视频"
                    media_size = message.video.file_size if hasattr(message.video, 'file_size') and message.video.file_size else 0
                    logger.info(f"工作协程-{worker_id} 开始下载 {media_type} {message.id} | 预计大小: {media_size/1024:.1f}KB | 尝试 #{retry_count+1}")
                    file_data = await self.client.download_media(message, in_memory=True, file_name=str(file_path.name))
                    
                elif message.document and "document" in media_types:
                    file_name = message.document.file_name
                    if not file_name:
                        file_name = f"{chat_id}-{message.id}-document"
                    file_path = download_path / f"{chat_id}-{message.id}-{file_name}"
                    media_type = "文档"
                    media_size = message.document.file_size if hasattr(message.document, 'file_size') and message.document.file_size else 0
                    logger.info(f"工作协程-{worker_id} 开始下载 {media_type} {message.id} | 预计大小: {media_size/1024:.1f}KB | 尝试 #{retry_count+1}")
                    file_data = await self.client.download_media(message, in_memory=True, file_name=str(file_path.name))
                
                elif message.audio and "audio" in media_types:
                    file_name = message.audio.file_name
                    if not file_name:
                        file_name = f"{chat_id}-{message.id}-audio.mp3"
                    file_path = download_path / f"{chat_id}-{message.id}-{file_name}"
                    media_type = "音频"
                    media_size = message.audio.file_size if hasattr(message.audio, 'file_size') and message.audio.file_size else 0
                    logger.info(f"工作协程-{worker_id} 开始下载 {media_type} {message.id} | 预计大小: {media_size/1024:.1f}KB | 尝试 #{retry_count+1}")
                    file_data = await self.client.download_media(message, in_memory=True, file_name=str(file_path.name))
                
                elif message.animation and "animation" in media_types:
                    file_path = download_path / f"{chat_id}-{message.id}-animation.mp4"
                    media_type = "动画"
                    media_size = message.animation.file_size if hasattr(message.animation, 'file_size') and message.animation.file_size else 0
                    logger.info(f"工作协程-{worker_id} 开始下载 {media_type} {message.id} | 预计大小: {media_size/1024:.1f}KB | 尝试 #{retry_count+1}")
                    file_data = await self.client.download_media(message, in_memory=True, file_name=str(file_path.name))
                
                elif message.sticker and "sticker" in media_types:
                    file_path = download_path / f"{chat_id}-{message.id}-sticker.webp"
                    media_type = "贴纸"
                    media_size = message.sticker.file_size if hasattr(message.sticker, 'file_size') and message.sticker.file_size else 0
                    logger.info(f"工作协程-{worker_id} 开始下载 {media_type} {message.id} | 预计大小: {media_size/1024:.1f}KB | 尝试 #{retry_count+1}")
                    file_data = await self.client.download_media(message, in_memory=True, file_name=str(file_path.name))
                
                # 验证下载的内容是否有效
                if file_data is None:
                    logger.error(f"工作协程-{worker_id} {media_type} {message.id} 下载失败: API返回空数据")
                    if retry_count < max_retries:
                        retry_count += 1
                        wait_time = 2 ** retry_count  # 指数退避策略
                        logger.info(f"尝试重新下载 {message.id}，第 {retry_count} 次重试，等待 {wait_time} 秒")
                        await asyncio.sleep(wait_time)
                        continue
                    return False
                    
                if file_data and file_path:
                    # 检查文件数据是否为空或无效
                    file_size = 0
                    if hasattr(file_data, 'getvalue'):
                        file_bytes = file_data.getvalue()
                        file_size = len(file_bytes)
                    
                    # 文件大小检查 - 如果小于预期的80%且媒体大小大于0，可能是下载不完整
                    if media_size > 0 and file_size > 0 and file_size < media_size * 0.8:
                        logger.warning(f"工作协程-{worker_id} {media_type} {message.id} 下载不完整: 预计大小 {media_size/1024:.1f}KB，实际大小 {file_size/1024:.1f}KB")
                        if retry_count < max_retries:
                            retry_count += 1
                            wait_time = 2 ** retry_count  # 指数退避策略
                            logger.info(f"尝试重新下载 {message.id}，第 {retry_count} 次重试，等待 {wait_time} 秒")
                            await asyncio.sleep(wait_time)
                            continue
                    
                    # 文件大小为0，下载失败
                    if file_size == 0:
                        logger.error(f"工作协程-{worker_id} {media_type} {message.id} 下载失败: 文件大小为0")
                        if retry_count < max_retries:
                            retry_count += 1
                            wait_time = 2 ** retry_count  # 指数退避策略
                            logger.info(f"尝试重新下载 {message.id}，第 {retry_count} 次重试，等待 {wait_time} 秒")
                            await asyncio.sleep(wait_time)
                            continue
                        return False
                    
                    # 计算下载时间
                    download_time = time.time() - start_time
                    speed = file_size / (download_time * 1024) if download_time > 0 else 0  # KB/s
                    
                    logger.info(f"工作协程-{worker_id} {media_type} {message.id} 下载完成 | 大小: {file_size/1024:.1f}KB | 耗时: {download_time:.2f}秒 | 速度: {speed:.1f}KB/s | 队列大小: {self.download_queue.qsize()}")
                    
                    # 放入队列，包含文件路径、文件数据、消息ID、频道标识符和频道ID
                    self.download_queue.put((file_path, file_data, message.id, channel, chat_id))
                    return True
                
                if not media_type:
                    logger.debug(f"消息 {message.id} 不包含支持的媒体类型或媒体类型不在配置中")
                return False
            
            except FloodWait as e:
                # 使用全局FloodWait处理机制
                await self._handle_flood_wait(e.x, message.id)
                # 不增加retry_count，FloodWait是正常的限制机制，不应计入错误重试次数
                continue
            
            except (TimeoutError, ConnectionError) as e:
                # 网络超时和连接错误处理
                logger.error(f"下载消息 {message.id} 时发生网络错误: {e}")
                if retry_count < max_retries:
                    retry_count += 1
                    wait_time = 2 ** retry_count  # 指数退避策略
                    logger.info(f"网络错误，尝试重新下载 {message.id}，第 {retry_count} 次重试，等待 {wait_time} 秒")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"下载 {message.id} 失败，网络错误达到最大重试次数 {max_retries}")
                    return False
            
            except Exception as e:
                logger.error(f"下载消息 {message.id} 的媒体文件失败: {e}")
                import traceback
                logger.error(traceback.format_exc())
                
                if "PEER_ID_INVALID" in str(e):
                    logger.error(f"下载 {message.id} 失败，频道ID无效或未加入频道")
                    return False
                
                if retry_count < max_retries:
                    retry_count += 1
                    wait_time = 2 ** retry_count  # 指数退避策略
                    logger.info(f"尝试重新下载 {message.id}，第 {retry_count} 次重试，等待 {wait_time} 秒")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"下载 {message.id} 失败，已达到最大重试次数 {max_retries}")
                    return False
        
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
            logger.error(f"无法获取有效的消息ID范围: chat_id={chat_id}, start_id={start_id}, end_id={end_id}")
            return
            
        # 计算需要获取的消息数量
        total_messages = actual_end_id - actual_start_id + 1
        logger.info(f"开始获取消息: chat_id={chat_id}, 开始id={actual_start_id}, 结束id={actual_end_id}，共{total_messages}条消息")
        
        # Telegram的get_chat_history按消息ID降序返回（从新到旧）
        # 我们需要先收集所有消息，然后按照ID升序排序，以便按照从旧到新的顺序处理
        
        try:
            # 收集指定范围内的所有消息
            all_messages = []
            offset_id = actual_end_id + 1
            fetched_count = 0
            
            while fetched_count < total_messages:
                limit = min(100, total_messages - fetched_count)  # 最多获取100条，但不超过剩余所需数量
                #logger.info(f"获取消息批次: chat_id={chat_id}, offset_id={offset_id}, limit={limit}, 已获取={fetched_count}/{total_messages}")
                
                batch_count = 0
                batch_messages = []
                
                try:
                    # 获取一批消息
                    async for message in self.client.get_chat_history(
                        chat_id=chat_id,
                        limit=limit,  # 限制每批次的消息数量
                        offset_id=offset_id  # 获取ID小于此值的消息
                    ):
                        batch_count += 1
                        
                        # 只处理在范围内的消息
                        if message.id >= actual_start_id and message.id <= actual_end_id:
                            fetched_count += 1
                            batch_messages.append(message)
                        
                        # 更新下一轮请求的offset_id
                        offset_id = message.id
                        
                        # 如果已经达到或低于开始ID，则停止获取
                        if message.id < actual_start_id:
                            logger.info(f"已达到最小ID {actual_start_id}，停止获取")
                            break
                except FloodWait as e:
                    # 使用全局FloodWait处理机制
                    logger.warning(f"获取消息批次时遇到FloodWait, offset_id={offset_id}, limit={limit}")
                    await self._handle_flood_wait(e.x)
                    continue
                
                # 将这批消息添加到总消息列表
                all_messages.extend(batch_messages)
                
                # 如果这批次没有获取到任何消息，则退出循环
                if batch_count == 0:
                    logger.info("没有更多消息可获取")
                    break
                
                # 避免频繁请求，但不要暂停太久
                await asyncio.sleep(0.2)
            
            # 按消息ID升序排序（从旧到新）
            all_messages.sort(key=lambda x: x.id)
            logger.info(f"消息获取完成，共获取{len(all_messages)}条消息，已按ID升序排序（从旧到新）")
            
            # 逐个返回排序后的消息
            for message in all_messages:
                yield message
        
        except FloodWait as e:
            # 使用全局FloodWait处理机制
            await self._handle_flood_wait(e.x)
        except Exception as e:
            logger.error(f"获取消息失败: {e}")
            logger.exception("详细错误信息")
    
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
                logger.warning(f"连续触发FloodWait ({self.consecutive_floods}次)，将全局延迟增加至 {self.adaptive_delay:.1f}秒")
            elif wait_time > 5:
                # 长时间的FloodWait表示较严重的限制，增加延迟
                self.adaptive_delay = min(3.0, self.adaptive_delay * 1.5)
                logger.warning(f"收到长时间FloodWait ({wait_time}秒)，将全局延迟增加至 {self.adaptive_delay:.1f}秒")
            elif self.flood_wait_count > 5:
                # 触发次数过多，逐渐增加延迟
                self.adaptive_delay = min(2.0, self.adaptive_delay * 1.2)
                logger.warning(f"已触发 {self.flood_wait_count} 次FloodWait，将全局延迟增加至 {self.adaptive_delay:.1f}秒")
                
            # 每50次FloodWait，记录一次统计信息
            if self.flood_wait_count % 50 == 0:
                logger.warning(f"FloodWait统计: 总计{self.flood_wait_count}次，当前全局延迟{self.adaptive_delay:.1f}秒")
            
            # 记录详细日志
            info = f"消息ID: {message_id}" if message_id else ""
            logger.warning(f"触发Telegram速率限制，等待 {wait_time} 秒 {info} (第{self.flood_wait_count}次)")
        
        # 等待Telegram要求的时间
        await asyncio.sleep(wait_time)
        
        # 添加自适应延迟，抖动范围与自适应延迟成比例
        jitter = random.uniform(0, self.adaptive_delay * 0.3)
        await asyncio.sleep(self.adaptive_delay + jitter)
        
        return True  # 返回True表示FloodWait已处理完成 