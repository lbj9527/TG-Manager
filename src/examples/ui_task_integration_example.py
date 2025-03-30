"""
UI和任务管理系统集成示例模块，展示如何实现上下文菜单和操作
此示例使用命令行模拟UI界面的操作和菜单
"""

import os
import sys
import asyncio
import time
import random
from typing import Dict, Any, List, Optional, Callable
from enum import Enum, auto

# 添加项目根目录到PYTHONPATH
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, project_root)

from src.utils.logger import get_logger
from src.utils.ui_state import UICallback, UIState, get_ui_callback, get_ui_state
from src.utils.task_manager import Task, TaskInfo, TaskStatus, TaskPriority, TaskGroup
from src.utils.task_scheduler import TaskScheduler, ScheduleMode, get_task_scheduler, init_task_scheduler
from src.utils.controls import TaskContext

# 获取日志记录器
logger = get_logger()


class MenuItem(Enum):
    """菜单项枚举"""
    ADD_TASK = auto()
    PAUSE_TASK = auto()
    RESUME_TASK = auto()
    CANCEL_TASK = auto()
    RETRY_TASK = auto()
    CLEAR_COMPLETED = auto()
    SHOW_DETAILS = auto()
    CHANGE_PRIORITY = auto()
    QUIT = auto()


class ConsoleUISimulator:
    """控制台UI模拟器，模拟图形界面的操作"""
    
    def __init__(self):
        """初始化控制台UI模拟器"""
        self.ui_callback = get_ui_callback()
        self.ui_state = get_ui_state()
        self.scheduler = get_task_scheduler()
        self.running = True
        self.tasks_list: List[str] = []  # 任务ID列表
        self.selected_task_index = -1
        
        # 设置回调
        self._setup_callbacks()
        
        # 设置初始状态
        self.ui_state.set("active_tasks", 0)
        self.ui_state.set("completed_tasks", 0)
        self.ui_state.set("failed_tasks", 0)
        self.ui_state.set("status_message", "就绪")
        
        # 监听状态变化
        self._setup_watchers()
    
    def _setup_callbacks(self):
        """设置UI回调"""
        self.ui_callback.set_status_callback(self._on_status)
        self.ui_callback.set_progress_callback(self._on_progress)
        self.ui_callback.set_error_callback(self._on_error)
        self.ui_callback.set_complete_callback(self._on_complete)
    
    def _setup_watchers(self):
        """设置状态监听器"""
        self.ui_state.watch("active_tasks", self._on_active_tasks_change)
        self.ui_state.watch("status_message", self._on_status_message_change)
    
    def _on_status(self, message: str):
        """状态回调"""
        self.ui_state.set("status_message", message)
        print(f"[状态] {message}")
    
    def _on_progress(self, current: int, total: int, message: str = ""):
        """进度回调"""
        percent = int(current / total * 100)
        bar_length = 30
        filled_length = int(bar_length * current / total)
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        print(f"\r[进度] [{bar}] {percent}% {message}", end="")
        if current == total:
            print()  # 换行
    
    def _on_error(self, title: str, message: str, details: str = "", recoverable: bool = False):
        """错误回调"""
        print(f"\n[错误] {title}: {message}")
        if details:
            print(f"      详情: {details}")
        if recoverable:
            print(f"      该错误可恢复")
    
    def _on_complete(self, success: bool, stats: Dict[str, Any]):
        """完成回调"""
        status = "成功" if success else "失败"
        print(f"[完成] 状态: {status}")
        
        # 更新完成的任务计数
        if success:
            completed = self.ui_state.get("completed_tasks") or 0
            self.ui_state.set("completed_tasks", completed + 1)
        else:
            failed = self.ui_state.get("failed_tasks") or 0
            self.ui_state.set("failed_tasks", failed + 1)
        
        # 更新任务列表
        self._update_tasks_list()
    
    def _on_active_tasks_change(self, value, metadata):
        """活跃任务数变化回调"""
        # 不打印任何内容，避免干扰界面
        pass
    
    def _on_status_message_change(self, value, metadata):
        """状态消息变化回调"""
        # 状态消息已在其他地方处理
        pass
    
    def _draw_ui(self):
        """绘制用户界面"""
        self._clear_screen()
        print("\n" + "=" * 80)
        print(f"  TG-Manager 任务管理器界面模拟")
        print("=" * 80)
        
        # 显示状态信息
        active = self.ui_state.get("active_tasks") or 0
        completed = self.ui_state.get("completed_tasks") or 0
        failed = self.ui_state.get("failed_tasks") or 0
        status = self.ui_state.get("status_message") or "就绪"
        
        print(f"\n状态: {status}")
        print(f"活跃任务: {active} | 已完成: {completed} | 失败: {failed}\n")
        
        # 显示任务列表
        print("当前任务:")
        print("-" * 80)
        print(" ID | 任务名称                 | 状态      | 优先级   | 进度   | 组别")
        print("-" * 80)
        
        for i, task_id in enumerate(self.tasks_list):
            task_info = self.scheduler.get_task_info(task_id)
            if not task_info:
                continue
                
            # 构建任务信息行
            status_text = task_info.status.name
            if task_info.is_paused:
                status_text += " (暂停)"
            
            # 计算进度
            progress_text = "N/A"
            if hasattr(task_info, 'progress') and task_info.progress is not None:
                progress = task_info.progress
                progress_text = f"{int(progress * 100)}%"
            
            # 添加选中标记
            selector = ">" if i == self.selected_task_index else " "
            
            # 截断过长的任务名称
            name = task_info.name[:22] + "..." if len(task_info.name) > 25 else task_info.name.ljust(25)
            
            print(f"{selector}{i:2d} | {name} | {status_text.ljust(9)} | {task_info.priority.name.ljust(8)} | {progress_text.ljust(6)} | {task_info.group.name}")
        
        if not self.tasks_list:
            print("  (无任务)")
        
        print("-" * 80)
        
        # 显示选中任务的详细信息
        if 0 <= self.selected_task_index < len(self.tasks_list):
            task_id = self.tasks_list[self.selected_task_index]
            task_info = self.scheduler.get_task_info(task_id)
            if task_info:
                print("\n选中的任务详情:")
                print(f"  名称: {task_info.name}")
                print(f"  描述: {task_info.description}")
                print(f"  状态: {task_info.status.name}")
                print(f"  创建时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(task_info.created_at))}")
                
                if task_info.started_at:
                    print(f"  开始时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(task_info.started_at))}")
                    
                if task_info.completed_at:
                    print(f"  完成时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(task_info.completed_at))}")
                    duration = task_info.completed_at - task_info.started_at
                    print(f"  执行时间: {duration:.2f}秒")
                
                if hasattr(task_info, 'error') and task_info.error:
                    print(f"  错误: {task_info.error}")
        
        # 显示可用操作
        print("\n可用操作:")
        print(f"  1. 添加任务")
        
        # 基于当前选中的任务状态显示相关操作
        if 0 <= self.selected_task_index < len(self.tasks_list):
            task_id = self.tasks_list[self.selected_task_index]
            task_info = self.scheduler.get_task_info(task_id)
            
            if task_info:
                if task_info.status == TaskStatus.RUNNING and not task_info.is_paused:
                    print(f"  2. 暂停任务")
                    print(f"  3. 取消任务")
                elif task_info.status == TaskStatus.RUNNING and task_info.is_paused:
                    print(f"  2. 恢复任务")
                    print(f"  3. 取消任务") 
                elif task_info.status == TaskStatus.FAILED:
                    print(f"  4. 重试任务")
                
                print(f"  7. 显示任务详情")
                
                if task_info.status == TaskStatus.PENDING or task_info.status == TaskStatus.RUNNING:
                    print(f"  8. 更改优先级")
        
        print(f"  5. 清理已完成任务")
        print(f"  9. 退出程序")
        print("\n选择一个操作 (按数字键)，或按上下键选择任务:")
    
    def _clear_screen(self):
        """清除屏幕"""
        if sys.platform == "win32":
            os.system("cls")
        else:
            os.system("clear")
    
    def _update_tasks_list(self):
        """更新任务列表"""
        # 获取所有任务
        all_tasks = self.scheduler.get_all_tasks()
        self.tasks_list = [task_id for task_id in all_tasks]
        
        # 更新活跃任务计数
        active_tasks = len(self.scheduler.get_tasks_by_status(TaskStatus.RUNNING))
        self.ui_state.set("active_tasks", active_tasks)
    
    def _handle_input(self, choice: str) -> None:
        """处理用户输入"""
        if choice == "":
            return
        
        # 处理数字选择
        if choice.isdigit():
            option = int(choice)
            
            # 处理菜单选项
            if option == 1:
                asyncio.create_task(self._add_new_task())
            elif option == 2 and 0 <= self.selected_task_index < len(self.tasks_list):
                task_id = self.tasks_list[self.selected_task_index]
                task_info = self.scheduler.get_task_info(task_id)
                
                if task_info and task_info.status == TaskStatus.RUNNING:
                    if task_info.is_paused:
                        asyncio.create_task(self._resume_task(task_id))
                    else:
                        asyncio.create_task(self._pause_task(task_id))
            elif option == 3 and 0 <= self.selected_task_index < len(self.tasks_list):
                task_id = self.tasks_list[self.selected_task_index]
                asyncio.create_task(self._cancel_task(task_id))
            elif option == 4 and 0 <= self.selected_task_index < len(self.tasks_list):
                task_id = self.tasks_list[self.selected_task_index]
                task_info = self.scheduler.get_task_info(task_id)
                
                if task_info and task_info.status == TaskStatus.FAILED:
                    asyncio.create_task(self._retry_task(task_id))
            elif option == 5:
                asyncio.create_task(self._clear_completed_tasks())
            elif option == 7 and 0 <= self.selected_task_index < len(self.tasks_list):
                task_id = self.tasks_list[self.selected_task_index]
                asyncio.create_task(self._show_task_details(task_id))
            elif option == 8 and 0 <= self.selected_task_index < len(self.tasks_list):
                task_id = self.tasks_list[self.selected_task_index]
                asyncio.create_task(self._change_task_priority(task_id))
            elif option == 9:
                self.running = False
        
        # 处理上下键 (这里简化为u和d)
        elif choice.lower() == "u" and self.selected_task_index > 0:
            self.selected_task_index -= 1
        elif choice.lower() == "d" and self.selected_task_index < len(self.tasks_list) - 1:
            self.selected_task_index += 1
    
    async def _add_new_task(self):
        """添加新任务"""
        self._clear_screen()
        print("\n添加新任务")
        print("-" * 40)
        
        # 模拟用户输入
        task_type = random.choice(["下载", "上传", "处理"])
        task_name = f"{task_type}任务-{random.randint(1000, 9999)}"
        
        # 随机选择优先级和分组
        priority = random.choice(list(TaskPriority))
        group = random.choice(list(TaskGroup))
        
        print(f"任务名称: {task_name}")
        print(f"优先级: {priority.name}")
        print(f"分组: {group.name}")
        
        # 创建并添加任务
        task_id = self.scheduler.create_task(
            name=task_name,
            coro_factory=lambda: self._simulate_task_execution(task_name),
            priority=priority,
            group=group,
            description=f"{task_name} 的任务描述"
        )
        
        print(f"\n任务已添加，ID: {task_id}")
        await asyncio.sleep(1.5)  # 短暂延迟，让用户看到结果
        
        # 更新任务列表并选中新任务
        self._update_tasks_list()
        if task_id in self.tasks_list:
            self.selected_task_index = self.tasks_list.index(task_id)
    
    async def _pause_task(self, task_id: str):
        """暂停任务"""
        task_info = self.scheduler.get_task_info(task_id)
        if not task_info:
            return
            
        print(f"\n暂停任务: {task_info.name}...")
        await self.scheduler.pause_task(task_id)
        print(f"任务已暂停")
        await asyncio.sleep(1)  # 短暂延迟
        
        # 更新UI
        self._update_tasks_list()
    
    async def _resume_task(self, task_id: str):
        """恢复任务"""
        task_info = self.scheduler.get_task_info(task_id)
        if not task_info:
            return
            
        print(f"\n恢复任务: {task_info.name}...")
        await self.scheduler.resume_task(task_id)
        print(f"任务已恢复")
        await asyncio.sleep(1)  # 短暂延迟
        
        # 更新UI
        self._update_tasks_list()
    
    async def _cancel_task(self, task_id: str):
        """取消任务"""
        task_info = self.scheduler.get_task_info(task_id)
        if not task_info:
            return
            
        print(f"\n取消任务: {task_info.name}...")
        await self.scheduler.cancel_task(task_id)
        print(f"任务已取消")
        await asyncio.sleep(1)  # 短暂延迟
        
        # 更新UI
        self._update_tasks_list()
    
    async def _retry_task(self, task_id: str):
        """重试任务"""
        task_info = self.scheduler.get_task_info(task_id)
        if not task_info or task_info.status != TaskStatus.FAILED:
            return
            
        print(f"\n重试任务: {task_info.name}...")
        
        # 重新创建相同的任务
        new_task_id = self.scheduler.create_task(
            name=task_info.name,
            coro_factory=lambda: self._simulate_task_execution(task_info.name),
            priority=task_info.priority,
            group=task_info.group,
            description=task_info.description
        )
        
        print(f"新任务已创建，ID: {new_task_id}")
        await asyncio.sleep(1)  # 短暂延迟
        
        # 更新UI
        self._update_tasks_list()
        if new_task_id in self.tasks_list:
            self.selected_task_index = self.tasks_list.index(new_task_id)
    
    async def _clear_completed_tasks(self):
        """清理已完成任务"""
        print("\n清理已完成任务...")
        
        completed_count = 0
        failed_count = 0
        
        # 获取所有已完成和失败的任务
        completed_tasks = self.scheduler.get_tasks_by_status(TaskStatus.COMPLETED)
        failed_tasks = self.scheduler.get_tasks_by_status(TaskStatus.FAILED)
        
        # 从调度器中移除任务
        for task_id in completed_tasks:
            self.scheduler.remove_task(task_id)
            completed_count += 1
            
        for task_id in failed_tasks:
            self.scheduler.remove_task(task_id)
            failed_count += 1
        
        print(f"已清理 {completed_count} 个已完成任务和 {failed_count} 个失败任务")
        await asyncio.sleep(1.5)  # 短暂延迟
        
        # 重置计数并更新UI
        self.ui_state.set("completed_tasks", 0)
        self.ui_state.set("failed_tasks", 0)
        self._update_tasks_list()
        
        # 重置选中索引
        if self.selected_task_index >= len(self.tasks_list):
            self.selected_task_index = len(self.tasks_list) - 1 if self.tasks_list else -1
    
    async def _show_task_details(self, task_id: str):
        """显示任务详情"""
        task_info = self.scheduler.get_task_info(task_id)
        if not task_info:
            return
            
        self._clear_screen()
        print("\n任务详细信息")
        print("=" * 60)
        print(f"任务ID: {task_id}")
        print(f"名称: {task_info.name}")
        print(f"描述: {task_info.description}")
        print(f"状态: {task_info.status.name}")
        print(f"优先级: {task_info.priority.name}")
        print(f"分组: {task_info.group.name}")
        print(f"创建时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(task_info.created_at))}")
        
        if task_info.started_at:
            print(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(task_info.started_at))}")
            
        if task_info.completed_at:
            print(f"完成时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(task_info.completed_at))}")
            duration = task_info.completed_at - task_info.started_at
            print(f"执行时间: {duration:.2f}秒")
        
        if hasattr(task_info, 'result') and task_info.result:
            print("\n任务结果:")
            print(f"{task_info.result}")
        
        if hasattr(task_info, 'error') and task_info.error:
            print("\n错误信息:")
            print(f"{task_info.error}")
        
        print("\n按回车键返回...")
        input()  # 等待用户按下回车
    
    async def _change_task_priority(self, task_id: str):
        """更改任务优先级"""
        task_info = self.scheduler.get_task_info(task_id)
        if not task_info or task_info.status not in [TaskStatus.PENDING, TaskStatus.RUNNING]:
            return
            
        self._clear_screen()
        print("\n更改任务优先级")
        print("-" * 40)
        print(f"任务: {task_info.name}")
        print(f"当前优先级: {task_info.priority.name}")
        print("\n可用优先级:")
        
        for i, priority in enumerate(TaskPriority):
            print(f"{i+1}. {priority.name}")
        
        # 模拟用户选择
        new_priority = random.choice(list(TaskPriority))
        while new_priority == task_info.priority:
            new_priority = random.choice(list(TaskPriority))
            
        print(f"\n已选择新优先级: {new_priority.name}")
        
        # 更新任务优先级
        await self.scheduler.update_task_priority(task_id, new_priority)
        print("优先级已更新")
        await asyncio.sleep(1.5)  # 短暂延迟
        
        # 更新UI
        self._update_tasks_list()
    
    async def _simulate_task_execution(self, task_name: str) -> Dict[str, Any]:
        """模拟任务执行"""
        # 获取当前任务的上下文
        task_context = TaskContext.get_current()
        
        # 更新任务信息
        steps = random.randint(5, 15)
        result = {"task_name": task_name, "status": "running", "steps": steps, "steps_completed": 0}
        
        try:
            for step in range(1, steps + 1):
                # 检查取消状态
                if task_context.cancel_token.is_cancelled:
                    self.ui_callback.update_status(f"{task_name} 在步骤 {step}/{steps} 被取消")
                    result["status"] = "cancelled"
                    result["steps_completed"] = step - 1
                    return result
                
                # 等待如果任务暂停
                if task_context.pause_token.is_paused:
                    self.ui_callback.update_status(f"{task_name} 在步骤 {step}/{steps} 被暂停")
                
                await task_context.wait_if_paused()
                
                # 模拟处理延迟
                wait_time = random.uniform(0.5, 1.5)
                self.ui_callback.update_progress(step, steps, f"{task_name}: 步骤 {step}/{steps}")
                
                # 存储进度在任务信息中
                task_context.set_progress(step / steps)
                
                await asyncio.sleep(wait_time)
                
                # 随机抛出错误
                if random.random() < 0.03:  # 3%的概率出错
                    raise RuntimeError(f"{task_name} 在步骤 {step} 时遇到随机错误")
                
                # 更新结果
                result["steps_completed"] = step
            
            # 处理完成
            result["status"] = "completed"
            self.ui_callback.update_status(f"{task_name} 处理完成")
            self.ui_callback.on_complete(True, {"task": task_name, "steps": steps})
            return result
            
        except Exception as e:
            # 处理异常
            self.ui_callback.show_error("任务失败", f"{task_name} 处理失败: {str(e)}")
            result["status"] = "failed"
            result["error"] = str(e)
            return result
    
    async def run(self):
        """运行UI模拟器"""
        print("启动任务调度器...")
        await init_task_scheduler(max_concurrent_tasks=3, schedule_mode=ScheduleMode.PRIORITY)
        self.scheduler = get_task_scheduler()
        
        # 初始化UI
        self._update_tasks_list()
        
        print("启动UI循环...")
        while self.running:
            # 绘制UI
            self._draw_ui()
            
            # 获取用户输入
            choice = input("\n请输入选择 (或按u/d选择任务): ")
            self._handle_input(choice)
            
            # 更新任务列表
            self._update_tasks_list()
            
            # 短暂延迟，减少CPU使用
            await asyncio.sleep(0.1)
        
        # 退出前清理
        await self.scheduler.stop()
        print("UI已关闭，任务调度器已停止")


async def main():
    """主函数"""
    print("UI和任务管理集成示例")
    
    try:
        # 创建并运行UI模拟器
        ui = ConsoleUISimulator()
        await ui.run()
        
    except Exception as e:
        import traceback
        print(f"示例运行出错: {e}")
        print(traceback.format_exc())
    
    print("\n示例程序执行完毕")


if __name__ == "__main__":
    # 运行主函数
    asyncio.run(main()) 