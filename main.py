#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TG-Manager主程序入口
处理命令行参数，初始化和启动应用程序
"""

import os
import sys
import argparse
import asyncio
from pathlib import Path

# 设置Python路径确保能导入tg_manager包
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入tg_manager模块
from tg_manager.run import TGManager
from tg_manager import __version__


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='TG-Manager - Telegram频道管理工具')
    
    parser.add_argument('--version', action='version', version=f'TG-Manager v{__version__}')
    
    # 创建互斥组，确保至少选择一种模式
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument('--download', action='store_true', help='下载模式：从源频道下载媒体')
    mode_group.add_argument('--upload', action='store_true', help='上传模式：将本地文件上传到目标频道')
    mode_group.add_argument('--forward', action='store_true', help='转发模式：在频道之间转发消息')
    mode_group.add_argument('--monitor', action='store_true', help='监控模式：监控源频道新消息并转发')
    
    # 配置文件选项
    parser.add_argument('--config', type=str, default='config.json', help='配置文件路径')
    
    # 可选的ID范围限制
    parser.add_argument('--start-id', type=int, help='起始消息ID')
    parser.add_argument('--end-id', type=int, help='结束消息ID')
    
    # 可选的监控持续时间
    parser.add_argument('--duration', type=str, help='监控持续时间，格式为"年-月-日-时"，如"2025-3-28-1"')
    
    return parser.parse_args()


async def main():
    """主函数"""
    args = parse_arguments()
    
    # 确保至少选择了一种模式
    if not any([args.download, args.upload, args.forward, args.monitor]):
        print("错误: 必须至少选择一种模式 (--download, --upload, --forward, --monitor)")
        print("使用 --help 查看帮助信息")
        return 1
    
    # 初始化TG-Manager
    manager = TGManager(config_path=args.config)
    await manager.initialize()
    
    try:
        # 根据命令行参数选择运行模式
        if args.download:
            start_id = args.start_id if args.start_id is not None else None
            end_id = args.end_id if args.end_id is not None else None
            await manager.run_download(start_id=start_id, end_id=end_id)
        
        elif args.upload:
            await manager.run_upload()
        
        elif args.forward:
            start_id = args.start_id if args.start_id is not None else None
            end_id = args.end_id if args.end_id is not None else None
            await manager.run_forward(start_id=start_id, end_id=end_id)
        
        elif args.monitor:
            duration = args.duration if args.duration is not None else None
            await manager.run_monitor(duration=duration)
    
    except KeyboardInterrupt:
        print("\n程序被用户中断")
        await manager.shutdown()
        return 1
    except Exception as e:
        print(f"发生错误: {e}")
        await manager.shutdown()
        return 1
    finally:
        await manager.shutdown()
    
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n程序被用户中断")
        sys.exit(1) 