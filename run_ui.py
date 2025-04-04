#!/usr/bin/env python3
"""
TG-Manager GUI - 图形界面版本启动入口
"""

import sys
import argparse
from loguru import logger
import os
from pathlib import Path
import datetime

# 导入应用程序类
from src.ui.app import TGManagerApp


def setup_logger():
    """设置日志系统"""
    # 确保日志目录存在
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # 移除默认处理器
    logger.remove()
    
    # 添加控制台处理器
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO"
    )
    
    # 添加日期文件处理器
    logger.add(
        "logs/app_{time:YYYY-MM-DD}.log",
        rotation="00:00",  # 每天轮换
        retention="30 days",  # 保留30天
        compression="zip",  # 压缩旧文件
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG"
    )
    
    # 添加固定名称的日志文件处理器
    logger.add(
        "logs/tg_manager.log",
        rotation="10 MB",  # 每10MB轮换
        retention=3,  # 保留3个备份
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG"
    )
    
    # 同步设置src/utils/logger.py中的日志文件名
    try:
        # 创建符号链接或复制最新的日志文件
        latest_log = max([f for f in log_dir.glob("app_*.log") if f.is_file()], 
                        key=os.path.getmtime, default=None)
        
        if latest_log:
            # 如果找到最新的日志文件，确保tg_manager.log存在
            tg_manager_log = log_dir / "tg_manager.log"
            if not tg_manager_log.exists():
                with open(tg_manager_log, "w") as f:
                    f.write(f"日志文件初始化于 {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"请查看 {latest_log.name} 获取最新日志内容\n")
    except Exception as e:
        print(f"警告: 同步日志文件时出错: {e}")


def main():
    """主程序入口"""
    parser = argparse.ArgumentParser(description="TG-Manager GUI - Telegram 消息管理工具图形界面版本")
    parser.add_argument("--debug", action="store_true", help="启用调试模式")
    parser.add_argument("--verbose", action="store_true", help="显示详细日志信息")
    
    args = parser.parse_args()
    
    # 设置日志系统
    setup_logger()
    
    # 设置日志级别
    if args.debug or args.verbose:
        logger.remove()
        logger.add(
            sys.stderr,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level="DEBUG"
        )
        logger.add(
            "logs/app_{time:YYYY-MM-DD}.log",
            rotation="00:00",
            retention="30 days",
            compression="zip",
            level="DEBUG"
        )
    
    # 启动 UI 应用程序
    logger.info("启动 TG-Manager 图形界面")
    if args.verbose:
        logger.debug("已启用详细日志模式")
    
    try:
        app = TGManagerApp(verbose=args.verbose)
        sys.exit(app.run())
    except Exception as e:
        logger.error(f"程序运行出错: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main() 