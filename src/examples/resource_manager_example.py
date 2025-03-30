"""
资源管理器示例模块，展示如何使用ResourceManager管理临时文件和资源
"""

import os
import sys
import asyncio
import time
from pathlib import Path

# 添加项目根目录到PYTHONPATH
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, project_root)

from src.utils.logger import get_logger
from src.utils.resource_manager import ResourceManager, TempFile, TempDir, ResourceSession
from src.utils.controls import TaskContext, CancelToken

logger = get_logger()

def print_separator(title):
    """打印分隔线和标题"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

async def basic_usage_example():
    """基本用法示例"""
    print_separator("基本用法示例")
    
    # 创建资源管理器
    resource_manager = ResourceManager("tmp/example")
    print(f"资源管理器已创建，基础临时目录: {resource_manager.base_temp_dir}")
    
    # 创建临时文件
    temp_path, resource_id = resource_manager.create_temp_file(".txt", "documents")
    print(f"临时文件已创建: {temp_path}, 资源ID: {resource_id}")
    
    # 写入一些内容
    with open(temp_path, 'w', encoding='utf-8') as f:
        f.write("这是一个测试文件内容")
    
    # 创建临时目录
    dir_path, dir_id = resource_manager.create_temp_dir(name="test_dir", category="test_files")
    print(f"临时目录已创建: {dir_path}, 资源ID: {dir_id}")
    
    # 在临时目录中创建一个文件
    test_file = dir_path / "test.txt"
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write("临时目录中的测试文件")
    
    # 显示已注册的资源
    resources = resource_manager.list_resources()
    print("\n已注册的资源:")
    for res in resources:
        print(f"  - {res['resource_id']} (引用计数: {res['refs']})")
    
    # 释放临时文件资源
    print("\n释放临时文件资源...")
    resource_manager.release_resource(resource_id)
    
    # 显示资源状态
    if os.path.exists(temp_path):
        print(f"  文件 {temp_path} 仍然存在，因为资源管理器已将其删除")
    else:
        print(f"  文件 {temp_path} 已被删除")
    
    # 强制删除临时目录资源
    print("\n强制删除临时目录资源...")
    resource_manager.release_resource(dir_id, force_delete=True)
    
    if os.path.exists(dir_path):
        print(f"  目录 {dir_path} 仍然存在")
    else:
        print(f"  目录 {dir_path} 已被删除")
    
    # 清理函数将在程序退出时自动调用
    print("\n资源管理器将在程序退出时自动清理剩余资源")

async def context_manager_example():
    """上下文管理器用法示例"""
    print_separator("上下文管理器用法示例")
    
    resource_manager = ResourceManager("tmp/example")
    
    # 使用临时文件上下文管理器
    print("使用临时文件上下文管理器...")
    async with TempFile(resource_manager, ".log", "logs") as temp_file:
        print(f"创建临时文件: {temp_file.path}")
        # 写入一些内容
        with open(temp_file.path, 'w', encoding='utf-8') as f:
            f.write("这是一个日志文件内容")
        
        # 读取内容
        with open(temp_file.path, 'r', encoding='utf-8') as f:
            content = f.read()
            print(f"文件内容: {content}")
    
    # 检查文件是否已被删除
    if os.path.exists(temp_file.path):
        print(f"文件 {temp_file.path} 仍然存在")
    else:
        print(f"文件 {temp_file.path} 已被自动删除")
    
    # 使用临时目录上下文管理器
    print("\n使用临时目录上下文管理器...")
    async with TempDir(resource_manager, "test_dir", "temp_dirs") as temp_dir:
        print(f"创建临时目录: {temp_dir.path}")
        
        # 在临时目录中创建一些文件
        for i in range(3):
            file_path = temp_dir.path / f"file_{i}.txt"
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"这是临时文件 {i} 的内容")
            print(f"创建文件: {file_path}")
    
    # 检查目录是否已被删除
    if os.path.exists(temp_dir.path):
        print(f"目录 {temp_dir.path} 仍然存在")
    else:
        print(f"目录 {temp_dir.path} 已被自动删除")

async def session_management_example():
    """会话管理示例"""
    print_separator("会话管理示例")
    
    resource_manager = ResourceManager("tmp/example")
    
    # 使用资源会话上下文管理器
    print("使用资源会话上下文管理器...")
    async with ResourceSession(resource_manager, "task1") as session:
        print(f"创建会话: {session.id}")
        
        # 在会话中创建多个资源
        files = []
        for i in range(5):
            file_path, file_id = resource_manager.create_temp_file(
                extension=f".part{i}", 
                category="chunks", 
                session_id=session.id
            )
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"这是会话 {session.id} 中的临时文件 {i}")
            files.append((file_path, file_id))
            print(f"创建临时文件: {file_path}")
        
        # 创建一个会话内的目录
        dir_path, dir_id = resource_manager.create_temp_dir(
            name="session_dir",
            category="session_dirs",
            session_id=session.id
        )
        print(f"创建会话目录: {dir_path}")
        
        # 显示会话信息
        sessions = resource_manager.list_sessions()
        print("\n当前会话信息:")
        for s in sessions:
            print(f"  - 会话ID: {s['session_id']}, 目录: {s['directory']}, 资源数量: {s['resource_count']}")
        
        # 显示该会话中的资源
        session_resources = resource_manager.list_resources(session.id)
        print(f"\n会话 {session.id} 中的资源:")
        for res in session_resources:
            print(f"  - {res['resource_id']}")
    
    # 检查会话目录和资源是否已被删除
    print("\n检查会话资源清理情况...")
    for file_path, _ in files:
        if os.path.exists(file_path):
            print(f"文件 {file_path} 仍然存在")
        else:
            print(f"文件 {file_path} 已被自动删除")
    
    if os.path.exists(dir_path):
        print(f"目录 {dir_path} 仍然存在")
    else:
        print(f"目录 {dir_path} 已被自动删除")
    
    # 检查会话是否已被删除
    sessions = resource_manager.list_sessions()
    if any(s['session_id'] == session.id for s in sessions):
        print(f"会话 {session.id} 仍然存在")
    else:
        print(f"会话 {session.id} 已被自动删除")

async def cleanup_task_example():
    """定期清理任务示例"""
    print_separator("定期清理任务示例")
    
    resource_manager = ResourceManager("tmp/example")
    
    # 修改清理间隔为测试用途
    resource_manager._cleanup_interval = 10  # 10秒清理一次
    resource_manager._resource_ttl = 5  # 5秒过期
    
    # 创建任务上下文
    cancel_token = CancelToken()
    task_context = TaskContext(cancel_token=cancel_token)
    
    # 启动清理任务
    print("启动定期清理任务...")
    await resource_manager.start_cleanup_task(task_context)
    
    # 创建一些资源
    print("创建一些资源...")
    for i in range(5):
        file_path, file_id = resource_manager.create_temp_file(f".tmp{i}")
        print(f"创建临时文件: {file_path}")
        # 立即释放资源引用，但不强制删除
        resource_manager.release_resource(file_id)
    
    # 等待一段时间，让清理任务有机会运行
    print("等待10秒，让清理任务运行...")
    for i in range(10):
        print(f"  倒计时: {10-i} 秒")
        await asyncio.sleep(1)
    
    # 停止清理任务
    print("停止清理任务...")
    await resource_manager.stop_cleanup_task()
    
    # 取消任务上下文
    cancel_token.cancel()
    
    print("定期清理任务示例完成")

async def resource_callback_example():
    """资源回调示例"""
    print_separator("资源回调示例")
    
    resource_manager = ResourceManager("tmp/example")
    
    # 创建一个临时文件
    temp_path, _ = resource_manager.create_temp_file(".bin")
    with open(temp_path, 'wb') as f:
        f.write(b'\x00' * 1024)  # 写入1KB的零字节
    
    # 定义一个自定义清理回调
    def custom_cleanup(path):
        print(f"自定义清理回调被调用: {path}")
        # 这里可以添加特殊的清理逻辑
        # 例如删除相关联的其他文件，更新数据库记录等
    
    # 使用自定义回调注册资源
    resource_id = resource_manager.register_resource(
        str(temp_path),
        cleanup_callback=custom_cleanup
    )
    print(f"带自定义回调的资源已注册: {resource_id}")
    
    # 释放资源，触发回调
    print("释放资源，将触发自定义回调...")
    resource_manager.release_resource(resource_id)

async def main():
    """主函数"""
    print("资源管理器示例程序")
    print("这个示例展示了如何使用ResourceManager管理临时文件和资源")
    
    # 确保示例目录存在
    os.makedirs("tmp/example", exist_ok=True)
    
    try:
        # 运行基本用法示例
        await basic_usage_example()
        
        # 运行上下文管理器示例
        await context_manager_example()
        
        # 运行会话管理示例
        await session_management_example()
        
        # 运行资源回调示例
        await resource_callback_example()
        
        # 运行定期清理任务示例
        await cleanup_task_example()
        
    except Exception as e:
        import traceback
        print(f"示例运行过程中发生错误: {e}")
        print(traceback.format_exc())
    
    print("\n示例程序执行完毕")

if __name__ == "__main__":
    asyncio.run(main()) 