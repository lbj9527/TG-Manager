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
from src.utils.channel_resolver import ChannelResolver
from src.utils.history_manager import HistoryManager
from src.utils.client_manager import ClientManager

from src.modules.downloader import Downloader
from src.modules.downloader_serial import DownloaderSerial
from src.modules.uploader import Uploader
from src.modules.forward.forwarder import Forwarder
from src.modules.monitor import Monitor
from src.utils.ui_config_manager import UIConfigManager

import pyrogram

logger = get_logger()

async def main():
    """主程序入口"""
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="TG Forwarder - Telegram消息转发工具")
    parser.add_argument('command', choices=['forward', 'download', 'upload', 'startmonitor'],
                        help="执行的命令：forward(转发历史消息), download(下载媒体文件), upload(上传本地文件), startmonitor(监听新消息)")
    
    args = parser.parse_args()
    
    # 初始化组件变量
    client_manager = None
    client = None
    
    try:
        # 初始化配置
        ui_config_manager = UIConfigManager()
        
        # 初始化历史记录管理器
        history_manager = HistoryManager()
        
        # 初始化客户端管理器
        client_manager = ClientManager(ui_config_manager)
        
        # 启动客户端
        client = await client_manager.start_client()
        
        # 初始化频道解析器
        channel_resolver = ChannelResolver(client)
        
        # 初始化下载模块 - 根据配置选择并行或顺序下载
        download_config = ui_config_manager.get_download_config()
        if download_config.parallel_download:
            logger.info("使用并行下载模式")
            # 设置并行下载器实例，并传入最大并发下载数
            downloader = Downloader(client, ui_config_manager, channel_resolver, history_manager)
            downloader.max_concurrent_downloads = download_config.max_concurrent_downloads
        else:
            logger.info("使用顺序下载模式")
            downloader = DownloaderSerial(client, ui_config_manager, channel_resolver, history_manager)
        
        # 初始化上传模块
        uploader = Uploader(client, ui_config_manager, channel_resolver, history_manager)
        
        # 初始化转发模块
        forwarder = Forwarder(client, ui_config_manager, channel_resolver, history_manager, downloader, uploader)
        
        # 注册全局未捕获的异常处理器
        async def check_uncaught_exceptions():
            while True:
                try:
                    for task in asyncio.all_tasks():
                        if task.done() and not task.cancelled():
                            try:
                                # 尝试获取异常
                                exc = task.exception()
                                if exc:
                                    logger.warning(f"发现未捕获的异常: {type(exc).__name__}: {exc}, 任务名称: {task.get_name()}")
                            except asyncio.CancelledError:
                                pass  # 忽略已取消的任务
                            except asyncio.InvalidStateError:
                                pass  # 忽略还未完成的任务
                    await asyncio.sleep(5)  # 每5秒检查一次
                except asyncio.CancelledError:
                    logger.info("异常检查任务已取消")
                    break
                except Exception as e:
                    logger.error(f"检查未捕获异常时出错: {e}")
                    await asyncio.sleep(5)
                
        # 启动异常检查任务
        exception_checker = asyncio.create_task(check_uncaught_exceptions())
        
        # 根据命令执行相应功能
        if args.command == 'forward':
            logger.info("执行历史消息转发")
            await forwarder.forward_messages()
            
        elif args.command == 'download':
            logger.info("执行媒体文件下载")
            # 删除设置use_keywords标志，将在downloader_serial.py中自动识别
            await downloader.download_media_from_channels()
            
        elif args.command == 'upload':
            logger.info("执行本地文件上传")
            await uploader.upload_local_files()
            
        elif args.command == 'startmonitor':
            logger.info("启动消息监听转发")
            # 初始化监听模块，不再传递history_manager参数
            monitor = Monitor(client, ui_config_manager, channel_resolver)
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
            
        # 取消异常检查任务
        if exception_checker and not exception_checker.done():
            exception_checker.cancel()
            try:
                await exception_checker
            except asyncio.CancelledError:
                pass
        
        # 关闭客户端
        if client_manager:
            await client_manager.stop_client()
        
    except KeyboardInterrupt:
        logger.info("用户中断程序")
    except Exception as e:
        logger.error(f"程序运行出错: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        # 确保清理所有资源
        try:
            # 取消所有未完成的任务
            tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            if tasks:
                logger.info(f"取消 {len(tasks)} 个未完成的任务...")
                for task in tasks:
                    task.cancel()
                
                try:
                    # 等待任务取消，设置超时避免无限等待
                    await asyncio.wait(tasks, timeout=5)
                except Exception as e:
                    logger.error(f"等待任务取消时出错: {e}")
                
            # 确保客户端已关闭
            if client_manager and client_manager.client:
                try:
                    await client_manager.stop_client()
                except Exception as e:
                    logger.error(f"关闭客户端时出错: {e}")
                    
            logger.info("所有资源已清理")
        except Exception as cleanup_error:
            logger.error(f"清理资源时出错: {cleanup_error}")
            
        logger.info("程序退出")


if __name__ == "__main__":
    # 使用最新的asyncio API获取事件循环
    try:
        # Python 3.10+推荐的方法
        asyncio.run(main())
    except KeyboardInterrupt:
        pass 