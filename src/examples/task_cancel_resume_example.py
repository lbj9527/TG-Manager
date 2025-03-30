"""
任务取消和恢复示例模块，展示如何有效地暂停、恢复和取消任务
"""

import os
import sys
import asyncio
import time
import random
from typing import Dict, Any, List

# 添加项目根目录到PYTHONPATH
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, project_root)

from src.utils.logger import get_logger
from src.utils.task_manager import Task, TaskInfo, TaskStatus, TaskPriority, TaskGroup
from src.utils.task_scheduler import TaskScheduler, ScheduleMode, get_task_scheduler, init_task_scheduler
from src.utils.controls import CancelToken, PauseToken, TaskContext
from src.utils.ui_state import get_ui_callback

# 获取日志记录器
logger = get_logger()

def print_separator(title):
    """打印分隔线和标题"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


async def process_item(item_id: int, task_context: TaskContext = None) -> Dict[str, Any]:
    """模拟处理单个项目的任务，支持暂停和取消"""
    if task_context is None:
        task_context = TaskContext()
        
    # 获取UI回调
    ui_callback = get_ui_callback()
    
    # 通知开始处理
    ui_callback.update_status(f"开始处理项目 {item_id}")
    
    # 模拟处理步骤
    steps = 10
    result = {"item_id": item_id, "status": "processing", "steps_completed": 0}
    
    try:
        for step in range(1, steps + 1):
            # 检查取消状态
            if task_context.cancel_token.is_cancelled:
                ui_callback.update_status(f"项目 {item_id} 处理被取消在步骤 {step}/{steps}")
                result["status"] = "cancelled"
                result["steps_completed"] = step - 1
                return result
            
            # 等待如果任务暂停
            if task_context.pause_token.is_paused:
                ui_callback.update_status(f"项目 {item_id} 处理在步骤 {step}/{steps} 被暂停")
            
            await task_context.wait_if_paused()
            
            # 模拟处理延迟
            wait_time = random.uniform(0.2, 0.8)
            ui_callback.update_progress(step, steps, f"处理项目 {item_id} 步骤 {step}/{steps}")
            await asyncio.sleep(wait_time)
            
            # 随机抛出错误
            if random.random() < 0.05:  # 5%的概率出错
                raise RuntimeError(f"处理项目 {item_id} 在步骤 {step} 时遇到随机错误")
            
            # 更新结果
            result["steps_completed"] = step
            
        # 处理完成
        result["status"] = "completed"
        ui_callback.update_status(f"项目 {item_id} 处理完成")
        return result
        
    except Exception as e:
        # 处理异常
        ui_callback.show_error("处理错误", f"项目 {item_id} 处理失败: {str(e)}")
        result["status"] = "failed"
        result["error"] = str(e)
        return result


async def batch_processor(batch_size: int = 5) -> List[Dict[str, Any]]:
    """批量处理器，同时处理多个项目"""
    print_separator("批量处理器示例")
    
    # 初始化任务调度器
    scheduler = await init_task_scheduler(
        max_concurrent_tasks=3,
        schedule_mode=ScheduleMode.PRIORITY
    )
    
    # 创建任务列表
    task_ids = []
    for i in range(batch_size):
        task_id = scheduler.create_task(
            name=f"处理项目 {i}",
            coro_factory=lambda item=i: process_item(item),
            group=TaskGroup.PROCESSING,
            priority=TaskPriority.NORMAL,
            description=f"处理项目 {i} 的任务"
        )
        task_ids.append(task_id)
        print(f"已创建任务: 处理项目 {i} [任务ID: {task_id}]")
    
    # 等待所有任务完成
    results = []
    active_tasks = task_ids.copy()
    
    try:
        # 在等待的同时，随机暂停和恢复任务
        async def control_tasks():
            # 等待一会儿，让任务有时间开始
            await asyncio.sleep(1.0)
            
            pause_count = 0
            resume_count = 0
            cancel_count = 0
            
            # 最多随机控制3次
            while len(active_tasks) > 0 and (pause_count + cancel_count) < 3:
                if not active_tasks:
                    break
                    
                # 随机选择一个活跃任务
                task_id = random.choice(active_tasks)
                task_info = scheduler.get_task_info(task_id)
                
                if not task_info or not task_info.is_active:
                    active_tasks.remove(task_id)
                    continue
                
                # 随机操作：暂停、恢复或取消
                action = random.choice(["pause", "cancel"] if not task_info.is_paused else ["resume"])
                
                if action == "pause" and not task_info.is_paused:
                    print(f"暂停任务: {task_info.name} [任务ID: {task_id}]")
                    await scheduler.pause_task(task_id)
                    pause_count += 1
                    
                    # 随机稍后恢复
                    await asyncio.sleep(random.uniform(1.0, 2.0))
                    if scheduler.get_task_info(task_id) and scheduler.get_task_info(task_id).is_paused:
                        print(f"恢复任务: {task_info.name} [任务ID: {task_id}]")
                        await scheduler.resume_task(task_id)
                        resume_count += 1
                        
                elif action == "resume" and task_info.is_paused:
                    print(f"恢复任务: {task_info.name} [任务ID: {task_id}]")
                    await scheduler.resume_task(task_id)
                    resume_count += 1
                    
                elif action == "cancel":
                    print(f"取消任务: {task_info.name} [任务ID: {task_id}]")
                    await scheduler.cancel_task(task_id)
                    cancel_count += 1
                    active_tasks.remove(task_id)
                
                await asyncio.sleep(random.uniform(0.5, 1.0))
                
            print(f"\n任务控制统计:")
            print(f"暂停操作: {pause_count}次")
            print(f"恢复操作: {resume_count}次")
            print(f"取消操作: {cancel_count}次")
        
        # 启动任务控制协程
        control_task = asyncio.create_task(control_tasks())
        
        # 等待所有任务完成或被取消
        while active_tasks:
            await asyncio.sleep(0.5)
            
            # 更新活跃任务列表
            for task_id in list(active_tasks):
                task_info = scheduler.get_task_info(task_id)
                
                # 如果任务已完成、失败或取消，则从活跃列表移除
                if not task_info or not task_info.is_active:
                    active_tasks.remove(task_id)
                    
                    # 获取任务结果
                    if task_info and task_info.result is not None:
                        results.append(task_info.result)
        
        # 等待控制任务完成
        await control_task
        
        # 获取最终任务信息
        print("\n最终任务状态:")
        for task_id in task_ids:
            task_info = scheduler.get_task_info(task_id)
            if task_info:
                status_text = f"{task_info.status.name}"
                if task_info.is_paused:
                    status_text += " (已暂停)"
                print(f"任务: {task_info.name} - 状态: {status_text}")
                
                if task_info.result:
                    print(f"  结果: {task_info.result}")
                    results.append(task_info.result)
        
        # 最终任务统计
        print("\n任务调度器统计:")
        print(f"总任务数: {scheduler.stats['total_tasks']}")
        print(f"完成任务数: {scheduler.stats['completed_tasks']}")
        print(f"失败任务数: {scheduler.stats['failed_tasks']}")
        print(f"取消任务数: {scheduler.stats['cancelled_tasks']}")
        
    finally:
        # 停止调度器
        await scheduler.stop()
        print("任务调度器已停止")
    
    return results


async def manual_task_control_demo():
    """手动任务控制演示，展示如何手动管理单个任务的取消与暂停"""
    print_separator("手动任务控制演示")
    
    # 创建取消和暂停令牌
    cancel_token = CancelToken()
    pause_token = PauseToken()
    
    # 创建任务上下文
    context = TaskContext(cancel_token, pause_token)
    
    # 启动任务
    task = asyncio.create_task(process_item(999, context))
    
    # 控制任务的执行
    try:
        # 让任务运行一段时间
        await asyncio.sleep(1.5)
        
        # 暂停任务
        print("正在暂停任务...")
        pause_token.pause()
        
        # 等待一会儿
        await asyncio.sleep(2.0)
        
        # 恢复任务
        print("正在恢复任务...")
        pause_token.resume()
        
        # 再次让任务运行一会儿
        await asyncio.sleep(1.5)
        
        # 是否取消任务 (50% 概率)
        if random.random() < 0.5:
            print("正在取消任务...")
            cancel_token.cancel()
        
        # 等待任务完成
        result = await task
        print(f"任务结果: {result}")
        
    except Exception as e:
        print(f"任务执行出错: {e}")


async def main():
    """主函数"""
    print("任务取消和恢复示例")
    
    try:
        # 运行手动任务控制演示
        await manual_task_control_demo()
        
        # 等待一会儿
        await asyncio.sleep(1.0)
        
        # 运行批量处理器演示
        results = await batch_processor(batch_size=8)
        print(f"\n批量处理完成，收集了 {len(results)} 个结果")
        
    except Exception as e:
        import traceback
        print(f"示例运行出错: {e}")
        print(traceback.format_exc())
    
    print("\n示例程序执行完毕")


if __name__ == "__main__":
    # 运行主函数
    asyncio.run(main()) 