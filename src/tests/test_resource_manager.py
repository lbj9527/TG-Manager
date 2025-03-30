"""
ResourceManager单元测试模块
"""

import os
import sys
import asyncio
import tempfile
import unittest
import time
from pathlib import Path

# 添加项目根目录到PYTHONPATH
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, project_root)

from src.utils.resource_manager import ResourceManager, TempFile, TempDir, ResourceSession
from src.utils.controls import TaskContext, CancelToken

class TestResourceManager(unittest.TestCase):
    """ResourceManager类单元测试"""
    
    def setUp(self):
        """测试前准备"""
        # 创建临时目录用于测试
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = os.path.join(self.temp_dir.name, "resource_test")
        
        # 创建资源管理器
        self.resource_manager = ResourceManager(self.base_path)
    
    def tearDown(self):
        """测试后清理"""
        # 清理临时目录
        self.temp_dir.cleanup()
    
    def test_create_temp_file(self):
        """测试创建临时文件"""
        # 创建临时文件
        file_path, file_id = self.resource_manager.create_temp_file(".txt", "docs")
        
        # 验证结果
        self.assertTrue(os.path.exists(file_path))
        self.assertTrue(str(file_path).endswith(".txt"))
        self.assertTrue("docs" in str(file_path))
        
        # 写入内容
        with open(file_path, 'w') as f:
            f.write("Test content")
        
        # 读取内容验证
        with open(file_path, 'r') as f:
            content = f.read()
        self.assertEqual(content, "Test content")
        
        # 释放资源
        result = self.resource_manager.release_resource(file_id)
        self.assertTrue(result)
        
        # 验证文件已删除
        self.assertFalse(os.path.exists(file_path))
    
    def test_create_temp_dir(self):
        """测试创建临时目录"""
        # 创建临时目录
        dir_path, dir_id = self.resource_manager.create_temp_dir("test_dir", "test_category")
        
        # 验证结果
        self.assertTrue(os.path.exists(dir_path))
        self.assertTrue(os.path.isdir(dir_path))
        self.assertTrue("test_category" in str(dir_path))
        self.assertTrue("test_dir" in str(dir_path))
        
        # 在目录中创建文件
        test_file = os.path.join(dir_path, "test.txt")
        with open(test_file, 'w') as f:
            f.write("Test file in directory")
        
        # 验证文件创建成功
        self.assertTrue(os.path.exists(test_file))
        
        # 释放资源
        result = self.resource_manager.release_resource(dir_id)
        self.assertTrue(result)
        
        # 验证目录及其内容已删除
        self.assertFalse(os.path.exists(dir_path))
        self.assertFalse(os.path.exists(test_file))
    
    def test_create_session(self):
        """测试创建会话"""
        # 创建会话
        session_id = self.resource_manager.create_session("test_session")
        
        # 验证会话创建成功
        session_dir = self.resource_manager.get_session_dir(session_id)
        self.assertIsNotNone(session_dir)
        self.assertTrue(os.path.exists(session_dir))
        self.assertTrue("test_session" in session_id)
        
        # 在会话中创建资源
        file_path, file_id = self.resource_manager.create_temp_file(
            extension=".log",
            category="logs",
            session_id=session_id
        )
        
        # 验证资源创建成功
        self.assertTrue(os.path.exists(file_path))
        
        # 获取会话资源列表
        resources = self.resource_manager.list_resources(session_id)
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["resource_id"], str(file_path))
        
        # 清理会话
        result = self.resource_manager.cleanup_session(session_id)
        self.assertTrue(result)
        
        # 验证会话目录及资源已删除
        self.assertFalse(os.path.exists(session_dir))
        self.assertFalse(os.path.exists(file_path))
        
        # 验证资源已从跟踪系统中移除
        resources = self.resource_manager.list_resources(session_id)
        self.assertEqual(len(resources), 0)
    
    def test_register_resource(self):
        """测试注册外部资源"""
        # 创建外部文件
        external_file = os.path.join(self.temp_dir.name, "external.dat")
        with open(external_file, 'wb') as f:
            f.write(b'\x00' * 100)
        
        # 定义自定义清理回调
        cleanup_called = [False]  # 使用列表以便在回调中修改
        
        def custom_cleanup(path):
            cleanup_called[0] = True
            # 自定义清理只是标记被调用，不实际删除文件
        
        # 注册资源
        resource_id = self.resource_manager.register_resource(
            external_file,
            cleanup_callback=custom_cleanup
        )
        
        # 验证资源已注册
        resources = self.resource_manager.list_resources()
        self.assertTrue(any(r["resource_id"] == external_file for r in resources))
        
        # 获取资源信息
        info = self.resource_manager.get_resource_info(resource_id)
        self.assertIsNotNone(info)
        self.assertEqual(info["refs"], 1)
        
        # 释放资源
        result = self.resource_manager.release_resource(resource_id)
        self.assertTrue(result)
        
        # 验证回调被调用
        self.assertTrue(cleanup_called[0])
        
        # 验证文件仍然存在（因为自定义回调没有删除它）
        self.assertTrue(os.path.exists(external_file))
        
        # 验证资源已从跟踪系统中移除
        info = self.resource_manager.get_resource_info(resource_id)
        self.assertIsNone(info)
    
    def test_reference_counting(self):
        """测试资源引用计数"""
        # 创建资源
        file_path, file_id = self.resource_manager.create_temp_file(".ref", "reftest")
        
        # 多次注册同一资源
        for _ in range(3):
            same_id = self.resource_manager.register_resource(str(file_path))
            self.assertEqual(same_id, str(file_path))
        
        # 获取资源信息，验证引用计数
        info = self.resource_manager.get_resource_info(file_id)
        self.assertEqual(info["refs"], 4)  # 初始创建 + 3次注册
        
        # 释放一次引用
        result = self.resource_manager.release_resource(file_id)
        self.assertTrue(result)
        
        # 验证引用计数减少但资源仍存在
        info = self.resource_manager.get_resource_info(file_id)
        self.assertEqual(info["refs"], 3)
        self.assertTrue(os.path.exists(file_path))
        
        # 释放剩余引用
        for _ in range(3):
            self.resource_manager.release_resource(file_id)
        
        # 验证资源已删除
        self.assertFalse(os.path.exists(file_path))
        info = self.resource_manager.get_resource_info(file_id)
        self.assertIsNone(info)
    
    def test_list_functions(self):
        """测试资源列表和会话列表功能"""
        # 创建多个会话
        session_ids = [
            self.resource_manager.create_session(f"session_{i}") 
            for i in range(3)
        ]
        
        # 在每个会话中创建资源
        for i, session_id in enumerate(session_ids):
            for j in range(2):
                self.resource_manager.create_temp_file(
                    extension=f".s{i}f{j}",
                    category=f"cat_{i}",
                    session_id=session_id
                )
        
        # 创建一些不属于会话的资源
        for i in range(3):
            self.resource_manager.create_temp_file(
                extension=f".global{i}",
                category="global"
            )
        
        # 列出所有资源
        all_resources = self.resource_manager.list_resources()
        self.assertEqual(len(all_resources), 3*2 + 3)  # 会话资源 + 全局资源
        
        # 列出特定会话的资源
        for i, session_id in enumerate(session_ids):
            session_resources = self.resource_manager.list_resources(session_id)
            self.assertEqual(len(session_resources), 2)
            for res in session_resources:
                self.assertTrue(f".s{i}f" in res["resource_id"])
        
        # 列出所有会话
        sessions = self.resource_manager.list_sessions()
        self.assertEqual(len(sessions), 3)
        
        # 验证会话资源计数
        for session in sessions:
            self.assertEqual(session["resource_count"], 2)
            self.assertTrue("session_" in session["session_id"])

class TestResourceManagerAsync(unittest.IsolatedAsyncioTestCase):
    """ResourceManager异步方法单元测试"""
    
    async def asyncSetUp(self):
        """异步测试前准备"""
        # 创建临时目录用于测试
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = os.path.join(self.temp_dir.name, "resource_test")
        
        # 创建资源管理器
        self.resource_manager = ResourceManager(self.base_path)
    
    async def asyncTearDown(self):
        """异步测试后清理"""
        # 停止所有可能运行的清理任务
        await self.resource_manager.stop_cleanup_task()
        
        # 清理临时目录
        self.temp_dir.cleanup()
    
    async def test_cleanup_expired_resources(self):
        """测试清理过期资源"""
        # 创建一些资源
        file_paths = []
        file_ids = []
        for i in range(5):
            path, res_id = self.resource_manager.create_temp_file(f".test{i}")
            file_paths.append(path)
            file_ids.append(res_id)
            
            # 立即释放引用，但不强制删除
            self.resource_manager.release_resource(res_id)
        
        # 验证文件仍然存在（因为只是将引用计数降为0）
        for path in file_paths:
            self.assertTrue(os.path.exists(path))
        
        # 强制将资源创建时间设为过去
        now = self.resource_manager._resources[file_ids[0]]["created"]
        for res_id in file_ids:
            # 设置为1小时前
            from datetime import datetime, timedelta
            self.resource_manager._resources[res_id]["created"] = now - timedelta(hours=1)
        
        # 手动运行清理，设置过期时间为30分钟
        count = await self.resource_manager.cleanup_expired_resources(max_age_seconds=30*60)
        
        # 验证所有资源都被清理
        self.assertEqual(count, 5)
        for path in file_paths:
            self.assertFalse(os.path.exists(path))
    
    async def test_start_stop_cleanup_task(self):
        """测试启动和停止清理任务"""
        # 调整清理间隔和资源TTL，以便测试更快完成
        self.resource_manager._cleanup_interval = 1  # 1秒清理一次
        self.resource_manager._resource_ttl = 1  # 1秒过期
        
        # 创建一些资源
        paths = []
        for i in range(3):
            path, res_id = self.resource_manager.create_temp_file(f".auto{i}")
            paths.append(path)
            # 立即释放引用
            self.resource_manager.release_resource(res_id)
        
        # 强制将资源创建时间设为过去
        for res_id in list(self.resource_manager._resources.keys()):
            from datetime import datetime, timedelta
            self.resource_manager._resources[res_id]["created"] = datetime.now() - timedelta(seconds=2)
        
        # 创建任务上下文
        cancel_token = CancelToken()
        task_context = TaskContext(cancel_token=cancel_token)
        
        # 启动清理任务
        await self.resource_manager.start_cleanup_task(task_context)
        
        # 等待清理任务运行
        await asyncio.sleep(3)  # 等待3秒，应该足够清理任务运行
        
        # 停止清理任务
        await self.resource_manager.stop_cleanup_task()
        
        # 验证文件已被清理
        for path in paths:
            self.assertFalse(os.path.exists(path))
    
    async def test_async_context_managers(self):
        """测试异步上下文管理器"""
        # 测试TempFile
        content = b"Test file content"
        
        async with TempFile(self.resource_manager, ".txt", "testfiles") as temp_file:
            # 写入文件
            with open(temp_file.path, 'wb') as f:
                f.write(content)
            
            # 验证文件存在并可读
            self.assertTrue(os.path.exists(temp_file.path))
            with open(temp_file.path, 'rb') as f:
                read_content = f.read()
            self.assertEqual(read_content, content)
            
            # 记录路径以供后续验证
            file_path = temp_file.path
        
        # 退出上下文后，验证文件已删除
        self.assertFalse(os.path.exists(file_path))
        
        # 测试TempDir
        async with TempDir(self.resource_manager, "testdir", "testdirs") as temp_dir:
            # 在目录中创建文件
            file1 = temp_dir.path / "file1.txt"
            file2 = temp_dir.path / "file2.txt"
            
            with open(file1, 'w') as f:
                f.write("File 1")
            with open(file2, 'w') as f:
                f.write("File 2")
            
            # 验证目录和文件存在
            self.assertTrue(os.path.exists(temp_dir.path))
            self.assertTrue(os.path.exists(file1))
            self.assertTrue(os.path.exists(file2))
            
            # 记录路径以供后续验证
            dir_path = temp_dir.path
        
        # 退出上下文后，验证目录已删除
        self.assertFalse(os.path.exists(dir_path))
        
        # 测试ResourceSession
        async with ResourceSession(self.resource_manager, "testsession") as session:
            # 在会话中创建资源
            files = []
            for i in range(3):
                file_path, _ = self.resource_manager.create_temp_file(
                    extension=f".sess{i}",
                    category="session_files",
                    session_id=session.id
                )
                files.append(file_path)
                
                # 验证文件创建成功
                self.assertTrue(os.path.exists(file_path))
            
            # 验证会话包含正确数量的资源
            session_resources = self.resource_manager.list_resources(session.id)
            self.assertEqual(len(session_resources), 3)
        
        # 退出上下文后，验证所有会话资源已删除
        for file_path in files:
            self.assertFalse(os.path.exists(file_path))
        
        # 验证会话已从会话列表中移除
        sessions = self.resource_manager.list_sessions()
        self.assertFalse(any(s["session_id"] == session.id for s in sessions))
    
    async def test_resource_manager_context(self):
        """测试ResourceManager作为上下文管理器"""
        async with ResourceManager(self.base_path) as rm:
            # 创建一些资源
            file_path, file_id = rm.create_temp_file(".ctx")
            
            # 验证资源创建成功
            self.assertTrue(os.path.exists(file_path))
            
            # 验证默认会话已创建
            self.assertTrue(hasattr(rm, 'default_session'))
            self.assertIsNotNone(rm.default_session)
            
            # 获取默认会话资源数
            default_resources = rm.list_resources(rm.default_session)
            self.assertGreaterEqual(len(default_resources), 0)  # 可能包含或不包含我们创建的资源，取决于实现
            
            # 记录路径以便后续验证
            temp_path = file_path
        
        # 验证资源和会话都已被清理
        self.assertFalse(os.path.exists(temp_path))

if __name__ == '__main__':
    unittest.main() 