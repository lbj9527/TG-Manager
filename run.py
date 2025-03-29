#!/usr/bin/env python3
"""
TG Forwarder - 主程序入口
处理命令行参数并启动相应的功能模块
"""

import sys
import asyncio
import argparse
from pathlib import Path

from src.utils.logger import get_logger
from src.utils.config_manager import ConfigManager
from src.utils.channel_resolver import ChannelResolver
from src.utils.history_manager import HistoryManager
from src.utils.client_manager import ClientManager

from src.modules.downloader import Downloader
from src.modules.downloader_serial import DownloaderSerial
from src.modules.uploader import Uploader
from src.modules.forwarder import Forwarder
from src.modules.monitor import Monitor

logger = get_logger()

async def main():
    """主程序入口"""
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="TG Forwarder - Telegram消息转发工具")
    parser.add_argument('command', choices=['forward', 'download', 'downloadKeywords', 'upload', 'startmonitor'],
                        help="执行的命令：forward(转发历史消息), download(下载媒体文件), downloadKeywords(根据关键字下载媒体文件), upload(上传本地文件), startmonitor(监听新消息)")
    
    args = parser.parse_args()
    
    try:
        # 初始化配置
        config_manager = ConfigManager()
        
        # 初始化历史记录管理器
        history_manager = HistoryManager()
        
        # 初始化客户端管理器
        client_manager = ClientManager(config_manager)
        
        # 启动客户端
        client = await client_manager.start_client()
        
        # 初始化频道解析器
        channel_resolver = ChannelResolver(client)
        
        # 初始化下载模块 - 根据配置选择并行或顺序下载
        download_config = config_manager.get_download_config()
        if download_config.parallel_download:
            logger.info("使用并行下载模式")
            # 设置并行下载器实例，并传入最大并发下载数
            downloader = Downloader(client, config_manager, channel_resolver, history_manager)
            downloader.max_concurrent_downloads = download_config.max_concurrent_downloads
        else:
            logger.info("使用顺序下载模式")
            downloader = DownloaderSerial(client, config_manager, channel_resolver, history_manager)
        
        # 初始化上传模块
        uploader = Uploader(client, config_manager, channel_resolver, history_manager)
        
        # 初始化转发模块
        forwarder = Forwarder(client, config_manager, channel_resolver, history_manager, downloader, uploader)
        
        # 根据命令执行相应功能
        if args.command == 'forward':
            logger.info("执行历史消息转发")
            await forwarder.forward_messages()
            
        elif args.command == 'download':
            logger.info("执行媒体文件下载")
            downloader.use_keywords = False
            await downloader.download_media_from_channels()
            
        elif args.command == 'downloadKeywords':
            logger.info("执行根据关键字下载媒体文件")
            downloader.use_keywords = True
            await downloader.download_media_from_channels()
            
        elif args.command == 'upload':
            logger.info("执行本地文件上传")
            await uploader.upload_local_files()
            
        elif args.command == 'startmonitor':
            logger.info("启动消息监听转发")
            # 初始化监听模块，不再传递history_manager参数
            monitor = Monitor(client, config_manager, channel_resolver)
            # 开始监听
            await monitor.start_monitoring()
            
            # 添加键盘中断处理
            try:
                # 持续运行直到用户中断
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                logger.info("用户中断监听，正在停止...")
                await monitor.stop_monitoring()
        
        else:
            logger.error(f"未知命令: {args.command}")
            parser.print_help()
        
        # 关闭客户端
        await client_manager.stop_client()
        
    except KeyboardInterrupt:
        logger.info("用户中断程序")
    except Exception as e:
        logger.error(f"程序运行出错: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        logger.info("程序退出")


if __name__ == "__main__":
    # 使用最新的asyncio API获取事件循环
    try:
        # Python 3.10+推荐的方法
        asyncio.run(main())
    except KeyboardInterrupt:
        pass 