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
from src.modules.uploader import Uploader
from src.modules.forwarder import Forwarder
from src.modules.monitor import Monitor

logger = get_logger()

async def main():
    """主程序入口"""
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="TG Forwarder - Telegram消息转发工具")
    parser.add_argument('command', choices=['forward', 'download', 'upload', 'startmonitor'],
                        help="执行的命令：forward(转发历史消息), download(下载媒体文件), upload(上传本地文件), startmonitor(监听新消息)")
    
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
        
        # 初始化下载模块
        downloader = Downloader(client, config_manager, channel_resolver, history_manager)
        
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
            await downloader.download_media_from_channels()
            
        elif args.command == 'upload':
            logger.info("执行本地文件上传")
            await uploader.upload_local_files()
            
        elif args.command == 'startmonitor':
            logger.info("启动消息监听转发")
            # 初始化监听模块
            monitor = Monitor(client, config_manager, channel_resolver, history_manager, forwarder)
            # 初始化频道映射
            await monitor.initialize_channels()
            # 开始监听
            await monitor.start_monitoring()
        
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
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close() 