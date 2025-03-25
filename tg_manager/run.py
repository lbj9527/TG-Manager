"""
主程序入口
解析命令行参数，调用对应功能模块
"""

import os
import sys
import argparse
import asyncio
import signal
from typing import Dict, List, Any, Optional

from pyrogram import Client

from tg_manager.utils.logger import get_logger
from tg_manager.utils.config_manager import ConfigManager
from tg_manager.services.channel_resolver import ChannelResolver
from tg_manager.services.history_manager import HistoryManager
from tg_manager.core.downloader import Downloader
from tg_manager.core.uploader import Uploader
from tg_manager.core.forwarder import Forwarder
from tg_manager.core.monitor import Monitor

logger = get_logger()


class TGManager:
    """TG-Manager主类，用于处理命令行参数并调用相应的功能模块"""
    
    def __init__(self, config_path: str = 'config.json'):
        """
        初始化TG-Manager
        
        Args:
            config_path: 配置文件路径
        """
        self.config_manager = ConfigManager(config_path)
        self.client = None
        self.channel_resolver = None
        self.history_manager = None
        self.downloader = None
        self.uploader = None
        self.forwarder = None
        self.monitor = None
        
        # 用于控制程序终止
        self.stop_event = asyncio.Event()
    
    async def _init_client(self) -> None:
        """初始化Pyrogram客户端"""
        api_id = self.config_manager.get_value('GENERAL', 'api_id')
        api_hash = self.config_manager.get_value('GENERAL', 'api_hash')
        
        if not api_id or api_id == '请在此填写您的Telegram API ID':
            logger.error("请在配置文件中设置有效的api_id")
            sys.exit(1)
        
        if not api_hash or api_hash == '请在此填写您的Telegram API Hash':
            logger.error("请在配置文件中设置有效的api_hash")
            sys.exit(1)
        
        # 创建客户端实例
        self.client = Client(
            "tg_manager_session",
            api_id=api_id,
            api_hash=api_hash,
            proxy=self.config_manager.get_proxy_settings()
        )
        
        # 设置信号处理器，处理程序终止
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self._signal_handler)
        
        # 启动客户端
        await self.client.start()
        logger.info("Telegram客户端已连接")
        
        # 获取并打印当前账号信息
        try:
            me = await self.client.get_me()
            if me:
                logger.info(f"已登录账号: {me.first_name} {me.last_name or ''} (@{me.username or '无用户名'}) [ID: {me.id}]")
            else:
                logger.warning("无法获取当前账号信息")
        except Exception as e:
            logger.error(f"获取账号信息时出错: {e}")
        
        # 初始化服务和核心组件
        self._init_components()
    
    async def initialize(self) -> None:
        """初始化TG-Manager，包括连接Telegram客户端"""
        await self._init_client()
    
    def _init_components(self) -> None:
        """初始化各个服务和核心组件"""
        self.history_manager = HistoryManager(
            download_history_path=self.config_manager.download_history_path,
            upload_history_path=self.config_manager.upload_history_path,
            forward_history_path=self.config_manager.forward_history_path
        )
        
        self.channel_resolver = ChannelResolver(
            client=self.client,
            cache_timeout=3600  # 缓存有效期1小时
        )
        
        self.downloader = Downloader(
            client=self.client,
            channel_resolver=self.channel_resolver,
            history_manager=self.history_manager,
            download_path=self.config_manager.get_value('DOWNLOAD', 'download_path', 'downloads'),
            organize_by_chat=self.config_manager.get_bool('DOWNLOAD', 'organize_by_chat', True),
            media_types=self.config_manager.get_json('DOWNLOAD', 'media_types'),
            max_retries=self.config_manager.get_int('GENERAL', 'max_retries', 3),
            timeout=self.config_manager.get_int('GENERAL', 'timeout', 300)
        )
        
        self.uploader = Uploader(
            client=self.client,
            channel_resolver=self.channel_resolver,
            history_manager=self.history_manager,
            max_retries=self.config_manager.get_int('GENERAL', 'max_retries', 3),
            timeout=self.config_manager.get_int('GENERAL', 'timeout', 300),
            caption_template=self.config_manager.get_value('UPLOAD', 'caption_template', '{filename}')
        )
        
        self.forwarder = Forwarder(
            client=self.client,
            channel_resolver=self.channel_resolver,
            history_manager=self.history_manager,
            downloader=self.downloader,
            uploader=self.uploader,
            tmp_path=self.config_manager.get_value('FORWARD', 'tmp_path', 'tmp'),
            media_types=self.config_manager.get_json('FORWARD', 'media_types'),
            remove_captions=self.config_manager.get_bool('FORWARD', 'remove_captions', False),
            forward_delay=self.config_manager.get_int('FORWARD', 'forward_delay', 3),
            max_retries=self.config_manager.get_int('GENERAL', 'max_retries', 3),
            timeout=self.config_manager.get_int('GENERAL', 'timeout', 30)
        )
        
        self.monitor = Monitor(
            client=self.client,
            channel_resolver=self.channel_resolver,
            forwarder=self.forwarder,
            history_manager=self.history_manager,
            media_types=self.config_manager.get_json('MONITOR', 'media_types'),
            remove_captions=self.config_manager.get_bool('MONITOR', 'remove_captions', False),
            forward_delay=self.config_manager.get_int('MONITOR', 'forward_delay', 3)
        )
    
    def _signal_handler(self, sig, frame) -> None:
        """处理终止信号"""
        logger.info(f"收到信号 {sig}，正在优雅关闭...")
        self.stop_event.set()
    
    async def start_forward(self) -> None:
        """启动转发功能"""
        logger.info("开始执行转发任务")
        
        # 获取配置中的转发频道配对
        forward_channel_pairs = self.config_manager.get_forward_channel_pairs()
        if not forward_channel_pairs:
            logger.error("配置中没有设置转发频道配对，请检查配置文件")
            return
        
        start_id = self.config_manager.get_int('FORWARD', 'start_id', 0)
        end_id = self.config_manager.get_int('FORWARD', 'end_id', 0)
        limit = self.config_manager.get_int('GENERAL', 'limit', 50)
        pause_time = self.config_manager.get_int('GENERAL', 'pause_time', 60)
        
        # 计数器
        total_forwarded = 0
        
        # 处理每个频道配对
        for pair in forward_channel_pairs:
            source_channel = pair.get('source_channel')
            target_channels = pair.get('target_channels', [])
            
            if not source_channel or not target_channels:
                logger.warning(f"无效的频道配对: {pair}")
                continue
            
            logger.info(f"转发: {source_channel} -> {', '.join(target_channels)}")
            
            # 调用转发器
            result = await self.forwarder.forward_messages(
                source_channel=source_channel,
                target_channels=target_channels,
                start_id=start_id,
                end_id=end_id,
                limit=limit
            )
            
            if result['status'] == 'success':
                forwarded = result['stats']['forwarded'] + result['stats']['downloaded_then_uploaded']
                total_forwarded += forwarded
                logger.info(f"从 {source_channel} 成功转发了 {forwarded} 条消息")
            else:
                logger.error(f"从 {source_channel} 转发失败: {result.get('error', '未知错误')}")
            
            # 检查是否达到限制
            if limit > 0 and total_forwarded >= limit:
                logger.info(f"已达到转发限制 {limit}，暂停 {pause_time} 秒")
                try:
                    # 等待暂停时间，或者收到停止信号
                    await asyncio.wait_for(self.stop_event.wait(), timeout=pause_time)
                    if self.stop_event.is_set():
                        logger.info("收到停止信号，结束转发任务")
                        break
                except asyncio.TimeoutError:
                    # 暂停时间结束，重置计数器
                    total_forwarded = 0
    
    async def start_download(self) -> None:
        """启动下载功能"""
        logger.info("开始执行下载任务")
        
        # 获取配置中的源频道列表
        source_channels = self.config_manager.get_json('DOWNLOAD', 'source_channels')
        if not source_channels:
            logger.error("配置中没有设置源频道，请检查配置文件")
            return
        
        start_id = self.config_manager.get_int('DOWNLOAD', 'start_id', 0)
        end_id = self.config_manager.get_int('DOWNLOAD', 'end_id', 0)
        limit = self.config_manager.get_int('GENERAL', 'limit', 50)
        pause_time = self.config_manager.get_int('GENERAL', 'pause_time', 60)
        
        # 计数器
        total_downloaded = 0
        
        # 处理每个源频道
        for source_channel in source_channels:
            logger.info(f"下载: {source_channel}")
            
            # 调用下载器
            result = await self.downloader.download_messages(
                source_channel=source_channel,
                start_id=start_id,
                end_id=end_id,
                limit=limit
            )
            
            if result['status'] == 'success':
                total_downloaded += result['stats']['downloaded']
                logger.info(f"从 {source_channel} 成功下载了 {result['stats']['downloaded']} 个文件")
            else:
                logger.error(f"从 {source_channel} 下载失败: {result.get('error', '未知错误')}")
            
            # 检查是否达到限制
            if limit > 0 and total_downloaded >= limit:
                logger.info(f"已达到下载限制 {limit}，暂停 {pause_time} 秒")
                try:
                    # 等待暂停时间，或者收到停止信号
                    await asyncio.wait_for(self.stop_event.wait(), timeout=pause_time)
                    if self.stop_event.is_set():
                        logger.info("收到停止信号，结束下载任务")
                        break
                except asyncio.TimeoutError:
                    # 暂停时间结束，重置计数器
                    total_downloaded = 0
    
    async def start_upload(self) -> None:
        """启动上传功能"""
        logger.info("开始执行上传任务")
        
        # 获取配置中的目标频道列表
        target_channels = self.config_manager.get_json('UPLOAD', 'target_channels')
        directory = self.config_manager.get_value('UPLOAD', 'directory', 'uploads')
        
        if not target_channels:
            logger.error("配置中没有设置目标频道，请检查配置文件")
            return
        
        if not os.path.exists(directory) or not os.path.isdir(directory):
            logger.error(f"上传目录 {directory} 不存在或不是有效目录")
            return
        
        # 调用上传器
        result = await self.uploader.upload_directory(
            directory=directory,
            target_channels=target_channels
        )
        
        if result['status'] == 'success':
            logger.info(f"成功上传了 {result['stats']['uploaded_files']} 个文件到 {len(target_channels)} 个频道")
        else:
            logger.error(f"上传失败: {result.get('error', '未知错误')}")
    
    async def start_monitor(self, duration: Optional[str] = None) -> None:
        """启动监听功能"""
        logger.info("开始执行监听任务")
        
        # 获取配置中的监听频道配对
        monitor_channel_pairs = self.config_manager.get_json('MONITOR', 'monitor_channel_pairs')
        if not monitor_channel_pairs:
            logger.error("配置中没有设置监听频道配对，请检查配置文件")
            return
        
        # 如果未指定参数，使用配置中的值
        if duration is None:
            duration = self.config_manager.get_value('MONITOR', 'duration', '')
        
        # 启动每个监听任务
        monitors = []
        for pair in monitor_channel_pairs:
            source_channel = pair.get('source_channel')
            target_channels = pair.get('target_channels', [])
            
            if not source_channel or not target_channels:
                logger.warning(f"无效的频道配对: {pair}")
                continue
            
            logger.info(f"监听: {source_channel} -> {', '.join(target_channels)}")
            
            # 启动监听
            result = await self.monitor.start_monitoring(
                source_channel=source_channel,
                target_channels=target_channels,
                duration=duration
            )
            
            if result['status'] in ['success', 'already_running']:
                monitors.append(result)
                logger.info(f"已启动监听任务: {result['monitor_id']}")
            else:
                logger.error(f"启动监听任务失败: {result.get('error', '未知错误')}")
        
        if not monitors:
            logger.warning("没有成功启动任何监听任务")
            return
        
        logger.info(f"正在监听 {len(monitors)} 个频道配对")
        
        # 等待停止事件或手动中断
        try:
            while not self.stop_event.is_set():
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            # 停止所有监听任务
            logger.info("正在停止所有监听任务")
            await self.monitor.stop_all_monitoring()
    
    async def run(self) -> None:
        """主程序入口"""
        # 解析命令行参数
        parser = argparse.ArgumentParser(description='TG-Manager: Telegram消息管理工具')
        parser.add_argument('command', choices=['forward', 'download', 'upload', 'startmonitor'],
                            help='要执行的命令: forward (转发), download (下载), upload (上传), startmonitor (开始监听)')
        args = parser.parse_args()
        
        # 初始化客户端
        await self._init_client()
        
        try:
            # 根据命令执行相应功能
            if args.command == 'forward':
                await self.start_forward()
            elif args.command == 'download':
                await self.start_download()
            elif args.command == 'upload':
                await self.start_upload()
            elif args.command == 'startmonitor':
                await self.start_monitor()
            else:
                logger.error(f"未知命令: {args.command}")
        finally:
            # 关闭客户端
            await self.client.stop()
            logger.info("程序已结束")

    async def shutdown(self) -> None:
        """关闭TG-Manager，断开Telegram客户端连接"""
        if self.client:
            await self.client.stop()
            logger.info("Telegram客户端已断开连接")

    async def run_download(self, start_id: Optional[int] = None, end_id: Optional[int] = None) -> None:
        """
        执行下载任务
        
        Args:
            start_id: 起始消息ID，为None时使用配置文件中的值
            end_id: 结束消息ID，为None时使用配置文件中的值
        """
        # 如果未指定参数，使用配置中的值
        if start_id is None:
            start_id = self.config_manager.get_int('DOWNLOAD', 'start_id', 0)
        if end_id is None:
            end_id = self.config_manager.get_int('DOWNLOAD', 'end_id', 0)
            
        await self.start_download()
            
    async def run_upload(self) -> None:
        """执行上传任务"""
        await self.start_upload()
        
    async def run_forward(self, start_id: Optional[int] = None, end_id: Optional[int] = None) -> None:
        """
        执行转发任务
        
        Args:
            start_id: 起始消息ID，为None时使用配置文件中的值
            end_id: 结束消息ID，为None时使用配置文件中的值
        """
        # 如果未指定参数，使用配置中的值
        if start_id is None:
            start_id = self.config_manager.get_int('FORWARD', 'start_id', 0)
        if end_id is None:
            end_id = self.config_manager.get_int('FORWARD', 'end_id', 0)
            
        await self.start_forward()
        
    async def run_monitor(self, duration: Optional[str] = None) -> None:
        """
        执行监控任务
        
        Args:
            duration: 监控持续时间，为None时使用配置文件中的值
        """
        # 如果未指定参数，使用配置中的值
        if duration is None:
            duration = self.config_manager.get_value('MONITOR', 'duration', '')
            
        await self.start_monitor(duration)


def main():
    """程序入口点"""
    tg_manager = TGManager()
    asyncio.run(tg_manager.run())


if __name__ == "__main__":
    main() 