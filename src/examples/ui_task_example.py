"""
UI状态管理和任务管理系统示例模块，展示如何使用这两个系统分离业务逻辑与界面
"""

import os
import sys
import asyncio
import time
import random
from pathlib import Path
from typing import Dict, List, Any

# 添加项目根目录到PYTHONPATH
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, project_root)

from src.utils.logger import get_logger
from src.utils.ui_state import UICallback, UIState, EventToUIAdapter, get_ui_callback, get_ui_state
from src.utils.task_manager import Task, TaskInfo, TaskStatus, TaskPriority, TaskGroup
from src.utils.task_scheduler import TaskScheduler, ScheduleMode, get_task_scheduler, init_task_scheduler
from src.utils.controls import TaskContext
from src.utils.events import EventEmitter

# 获取日志记录器
logger = get_logger()

def print_separator(title):
    """打印分隔线和标题"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


class MockDownloader(EventEmitter):
    """模拟下载器，演示业务逻辑与界面分离"""
    
    def __init__(self):
        super().__init__()
        self.downloads = {}
        self.ui_callback = get_ui_callback()
        
        # 将事件适配到UI回调
        self.adapter = EventToUIAdapter(self.ui_callback)
        self.adapter.adapt(self)
    
    async def download_file(self, file_name: str, size: int, task_context: TaskContext = None) -> str:
        """模拟文件下载"""
        if not task_context:
            task_context = TaskContext()
            
        # 通知状态
        self.emit("status", f"开始下载文件: {file_name}")
        
        # 创建下载路径
        path = f"downloads/{file_name}"
        self.downloads[file_name] = {
            "path": path,
            "size": size,
            "downloaded": 0
        }
        
        # 模拟下载过程
        chunks = 10
        chunk_size = size // chunks
        
        for i in range(chunks):
            # 检查取消
            if task_context.cancel_token.is_cancelled:
                self.emit("error", f"下载 {file_name} 已取消", "DOWNLOAD_CANCELLED", False)
                return None
                
            # 等待暂停恢复
            await task_context.wait_if_paused()
            
            # 模拟下载延迟
            await asyncio.sleep(0.5)
            
            # 更新进度
            downloaded = (i + 1) * chunk_size
            self.downloads[file_name]["downloaded"] = downloaded
            progress = (i + 1) / chunks
            
            # 发送进度事件
            self.emit("progress", i + 1, chunks, f"下载 {file_name}: {int(progress * 100)}%")
            
            # 发送媒体下载事件
            self.emit("media_download", {
                "file_name": file_name,
                "size": size,
                "downloaded": downloaded
            }, path, size)
        
        # 下载完成
        self.emit("status", f"文件 {file_name} 下载完成")
        self.emit("complete", True, {"file": file_name, "path": path, "size": size})
        
        return path


class MockUploader(EventEmitter):
    """模拟上传器，演示业务逻辑与界面分离"""
    
    def __init__(self):
        super().__init__()
        self.uploads = {}
        self.ui_callback = get_ui_callback()
        
        # 将事件适配到UI回调
        self.adapter = EventToUIAdapter(self.ui_callback)
        self.adapter.adapt(self)
    
    async def upload_file(self, file_path: str, target: str, task_context: TaskContext = None) -> bool:
        """模拟文件上传"""
        if not task_context:
            task_context = TaskContext()
            
        # 通知状态
        self.emit("status", f"开始上传文件: {file_path} 到 {target}")
        
        # 模拟文件大小
        size = random.randint(1024, 10240)
        
        self.uploads[file_path] = {
            "target": target,
            "size": size,
            "uploaded": 0
        }
        
        # 模拟上传过程
        chunks = 5
        chunk_size = size // chunks
        
        for i in range(chunks):
            # 检查取消
            if task_context.cancel_token.is_cancelled:
                self.emit("error", f"上传 {file_path} 已取消", "UPLOAD_CANCELLED", False)
                return False
                
            # 等待暂停恢复
            await task_context.wait_if_paused()
            
            # 模拟上传延迟
            await asyncio.sleep(0.8)
            
            # 随机模拟上传错误
            if random.random() < 0.1:
                self.emit("error", f"上传 {file_path} 失败: 网络错误", "NETWORK_ERROR", True)
                return False
            
            # 更新进度
            uploaded = (i + 1) * chunk_size
            self.uploads[file_path]["uploaded"] = uploaded
            progress = (i + 1) / chunks
            
            # 发送进度事件
            self.emit("progress", i + 1, chunks, f"上传 {file_path}: {int(progress * 100)}%")
            
            # 发送媒体上传事件
            self.emit("media_upload", {
                "file_path": file_path,
                "target": target,
                "size": size,
                "uploaded": uploaded
            }, target, {"status": "uploading", "progress": progress})
        
        # 上传完成
        self.emit("status", f"文件 {file_path} 上传完成")
        self.emit("complete", True, {"file": file_path, "target": target, "size": size})
        
        # 发送媒体上传完成事件
        self.emit("media_upload", {
            "file_path": file_path,
            "target": target,
            "size": size,
            "uploaded": size
        }, target, {"status": "completed"})
        
        return True


class ConsolePrinter:
    """控制台打印器，用于显示业务逻辑的输出"""
    
    def __init__(self):
        """初始化控制台打印器"""
        self.ui_callback = get_ui_callback()
        self.ui_state = get_ui_state()
        
        # 设置回调
        self._setup_callbacks()
        
        # 监听状态变化
        self._watch_states()
    
    def _setup_callbacks(self):
        """设置UI回调"""
        self.ui_callback.set_status_callback(self._on_status)
        self.ui_callback.set_progress_callback(self._on_progress)
        self.ui_callback.set_info_callback(self._on_info)
        self.ui_callback.set_warning_callback(self._on_warning)
        self.ui_callback.set_error_callback(self._on_error)
        self.ui_callback.set_media_callback(self._on_media)
        self.ui_callback.set_complete_callback(self._on_complete)
    
    def _watch_states(self):
        """监听状态变化"""
        def on_active_task_change(value, metadata):
            print(f"[状态变化] 活跃任务数: {value}")
        
        # 监听活跃任务数
        self.ui_state.watch("active_tasks", on_active_task_change)
    
    def _on_status(self, message: str):
        """状态回调"""
        print(f"[状态] {message}")
    
    def _on_progress(self, current: int, total: int, message: str = ""):
        """进度回调"""
        percent = int(current / total * 100)
        bar_length = 30
        filled_length = int(bar_length * current / total)
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        print(f"\r[进度] [{bar}] {percent}% {message}", end="")
        if current == total:
            print()  # 进度完成时换行
    
    def _on_info(self, message: str):
        """信息回调"""
        print(f"[信息] {message}")
    
    def _on_warning(self, message: str):
        """警告回调"""
        print(f"[警告] {message}")
    
    def _on_error(self, title: str, message: str, details: str = "", recoverable: bool = False):
        """错误回调"""
        print(f"[错误] {title}: {message}")
        if details:
            print(f"      详情: {details}")
        if recoverable:
            print(f"      该错误可恢复")
    
    def _on_media(self, operation: str, media_data: Any, extra_info: Dict[str, Any]):
        """媒体回调"""
        print(f"[媒体操作] {operation}: {media_data}")
        if extra_info:
            print(f"      附加信息: {extra_info}")
    
    def _on_complete(self, success: bool, stats: Dict[str, Any]):
        """完成回调"""
        status = "成功" if success else "失败"
        print(f"[完成] 状态: {status}, 统计: {stats}")


async def ui_state_demo():
    """UI状态管理示例"""
    print_separator("UI状态管理示例")
    
    # 获取UI状态实例
    ui_state = get_ui_state()
    
    # 设置一些状态
    ui_state.set("current_user", "TestUser", {"login_time": time.time()})
    ui_state.set("session_id", "12345")
    ui_state.set("downloads_count", 0)
    
    # 获取状态
    user = ui_state.get("current_user")
    session = ui_state.get("session_id")
    
    print(f"当前用户: {user}")
    print(f"会话ID: {session}")
    
    # 监视状态变化
    def on_downloads_change(value, metadata):
        print(f"下载计数更新: {value} {metadata if metadata else ''}")
    
    # 添加监视
    ui_state.watch("downloads_count", on_downloads_change)
    
    # 更新状态几次
    for i in range(1, 6):
        ui_state.set("downloads_count", i, {"last_update": time.time()})
        await asyncio.sleep(0.5)
    
    # 清理监视
    ui_state.unwatch("downloads_count")
    
    print("UI状态管理示例完成")


async def task_management_demo():
    """任务管理演示"""
    print_separator("任务管理示例")
    
    # 创建并启动任务调度器
    scheduler = await init_task_scheduler(max_concurrent_tasks=3, schedule_mode=ScheduleMode.PRIORITY)
    
    # 创建控制台打印器
    printer = ConsolePrinter()
    
    # 创建下载器和上传器
    downloader = MockDownloader()
    uploader = MockUploader()
    
    # 创建几个下载任务
    download_tasks = []
    for i in range(5):
        file_name = f"file_{i}.dat"
        file_size = random.randint(1024, 5120)
        
        # 创建下载任务
        task_id = scheduler.create_task(
            name=f"下载{file_name}",
            coro_factory=lambda fn=file_name, fs=file_size: downloader.download_file(fn, fs),
            group=TaskGroup.DOWNLOAD,
            priority=random.choice(list(TaskPriority)),
            description=f"下载文件 {file_name} ({file_size} 字节)"
        )
        download_tasks.append(task_id)
        
        print(f"已创建下载任务: {file_name} [{task_id}]")
    
    # 等待一会，让一些任务开始
    await asyncio.sleep(2)
    
    # 更新UI状态中的活跃任务数
    ui_state = get_ui_state()
    ui_state.set("active_tasks", len(scheduler.get_tasks_by_status(TaskStatus.RUNNING)))
    
    # 随机暂停一个任务
    pause_task_id = random.choice(download_tasks)
    task_info = scheduler.get_task_info(pause_task_id)
    if task_info and task_info.status == TaskStatus.RUNNING:
        print(f"暂停任务: {task_info.name} [{pause_task_id}]")
        await scheduler.pause_task(pause_task_id)
        
        # 等待一会儿再恢复
        await asyncio.sleep(2)
        print(f"恢复任务: {task_info.name} [{pause_task_id}]")
        await scheduler.resume_task(pause_task_id)
    
    # 随机取消一个任务
    cancel_task_id = random.choice(download_tasks)
    if cancel_task_id != pause_task_id:  # 不取消刚才暂停的任务
        task_info = scheduler.get_task_info(cancel_task_id)
        if task_info and task_info.is_active:
            print(f"取消任务: {task_info.name} [{cancel_task_id}]")
            await scheduler.cancel_task(cancel_task_id)
    
    # 等待剩余下载任务完成
    pending_count = len([t for t in download_tasks if 
                        scheduler.get_task_info(t) and 
                        scheduler.get_task_info(t).is_active])
    
    while pending_count > 0:
        await asyncio.sleep(1)
        pending_count = len([t for t in download_tasks if 
                            scheduler.get_task_info(t) and 
                            scheduler.get_task_info(t).is_active])
        ui_state.set("active_tasks", pending_count)
    
    print("\n所有下载任务已完成，开始上传任务")
    
    # 创建上传任务
    upload_tasks = []
    for i in range(3):
        file_path = f"downloads/file_{i}.dat"
        target = f"channel_{random.randint(1, 5)}"
        
        # 创建上传任务
        task_id = scheduler.create_task(
            name=f"上传{file_path}",
            coro_factory=lambda fp=file_path, tg=target: uploader.upload_file(fp, tg),
            group=TaskGroup.UPLOAD,
            priority=TaskPriority.HIGH,
            description=f"上传文件 {file_path} 到 {target}"
        )
        upload_tasks.append(task_id)
        
        print(f"已创建上传任务: {file_path} [{task_id}]")
    
    # 等待所有上传任务完成
    pending_count = len(upload_tasks)
    
    while pending_count > 0:
        await asyncio.sleep(1)
        pending_count = len([t for t in upload_tasks if 
                            scheduler.get_task_info(t) and 
                            scheduler.get_task_info(t).is_active])
        ui_state.set("active_tasks", pending_count)
    
    # 显示任务统计
    print("\n任务统计:")
    print(f"总任务数: {scheduler.stats['total_tasks']}")
    print(f"完成任务数: {scheduler.stats['completed_tasks']}")
    print(f"失败任务数: {scheduler.stats['failed_tasks']}")
    print(f"取消任务数: {scheduler.stats['cancelled_tasks']}")
    
    # 停止调度器
    await scheduler.stop()
    print("任务调度器已停止")


async def main():
    """主函数"""
    print("UI状态管理和任务管理系统示例")
    
    try:
        # 运行UI状态管理示例
        await ui_state_demo()
        
        # 运行任务管理示例
        await task_management_demo()
        
    except Exception as e:
        import traceback
        print(f"示例运行出错: {e}")
        print(traceback.format_exc())
    
    print("\n示例程序执行完毕")


if __name__ == "__main__":
    # 运行主函数
    asyncio.run(main()) 