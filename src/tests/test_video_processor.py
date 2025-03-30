"""
VideoProcessor单元测试模块
"""

import os
import sys
import asyncio
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# 添加项目根目录到PYTHONPATH
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, project_root)

from src.utils.video_processor import VideoProcessor
from src.utils.resource_manager import ResourceManager

# 测试用视频文件路径 (如果存在的话)
TEST_VIDEO_PATH = os.path.join(project_root, "src/tests/resources/test_video.mp4")

class TestVideoProcessor(unittest.TestCase):
    """VideoProcessor类单元测试"""
    
    def setUp(self):
        """测试前准备"""
        # 创建临时目录用于测试
        self.temp_dir = tempfile.TemporaryDirectory()
        self.thumb_dir = os.path.join(self.temp_dir.name, "thumbnails")
        os.makedirs(self.thumb_dir, exist_ok=True)
        
        # 创建资源管理器
        self.resource_manager = ResourceManager(os.path.join(self.temp_dir.name, "resources"))
        
        # 创建两个VideoProcessor实例，一个使用资源管理器，一个不使用
        self.video_processor = VideoProcessor(thumb_dir=self.thumb_dir)
        self.video_processor_with_rm = VideoProcessor(
            resource_manager=self.resource_manager,
            thumb_dir=self.thumb_dir
        )
        
        # 创建测试视频的mock
        self.mock_video_path = os.path.join(self.temp_dir.name, "test_video.mp4")
        with open(self.mock_video_path, 'wb') as f:
            # 写入一些随机字节作为假视频文件
            f.write(b'\x00' * 1024)
    
    def tearDown(self):
        """测试后清理"""
        # 清理临时目录
        self.temp_dir.cleanup()
    
    @patch('src.utils.video_processor.VideoFileClip')
    @patch('src.utils.video_processor.Image')
    def test_extract_thumbnail_basic(self, mock_image, mock_video_clip):
        """测试基本的缩略图提取功能"""
        # 设置模拟对象
        mock_clip_instance = MagicMock()
        mock_clip_instance.get_frame.return_value = MagicMock()
        mock_video_clip.return_value.__enter__.return_value = mock_clip_instance
        
        mock_img = MagicMock()
        mock_img.size = (640, 480)
        mock_image.fromarray.return_value = mock_img
        
        # 调用测试方法
        thumb_path = self.video_processor.extract_thumbnail(self.mock_video_path)
        
        # 验证结果
        self.assertIsNotNone(thumb_path)
        self.assertTrue(os.path.exists(thumb_path))
        self.assertTrue(thumb_path.endswith(".jpg"))
        
        # 验证方法调用
        mock_clip_instance.get_frame.assert_called_with(0)
        mock_img.resize.assert_called()
        mock_img.save.assert_called()
    
    @patch('src.utils.video_processor.VideoFileClip')
    @patch('src.utils.video_processor.Image')
    def test_extract_thumbnail_with_resource_manager(self, mock_image, mock_video_clip):
        """测试使用资源管理器的缩略图提取功能"""
        # 设置模拟对象
        mock_clip_instance = MagicMock()
        mock_clip_instance.get_frame.return_value = MagicMock()
        mock_video_clip.return_value.__enter__.return_value = mock_clip_instance
        
        mock_img = MagicMock()
        mock_img.size = (640, 480)
        mock_image.fromarray.return_value = mock_img
        
        # 调用测试方法
        thumb_path = self.video_processor_with_rm.extract_thumbnail(self.mock_video_path)
        
        # 验证结果
        self.assertIsNotNone(thumb_path)
        self.assertTrue(os.path.exists(thumb_path))
        self.assertTrue(thumb_path.endswith(".jpg"))
        
        # 验证映射
        self.assertTrue(self.mock_video_path in self.video_processor_with_rm._thumb_map)
        self.assertEqual(self.video_processor_with_rm._thumb_map[self.mock_video_path], thumb_path)
        
        # 验证方法调用
        mock_clip_instance.get_frame.assert_called_with(0)
        mock_img.resize.assert_called()
        mock_img.save.assert_called()
    
    def test_delete_thumbnail(self):
        """测试缩略图删除功能"""
        # 创建模拟缩略图文件
        test_thumb_path = os.path.join(self.thumb_dir, "test_thumb.jpg")
        with open(test_thumb_path, 'wb') as f:
            f.write(b'\x00' * 100)  # 写入一些字节作为内容
        
        # 手动添加到映射
        self.video_processor._thumb_map[self.mock_video_path] = test_thumb_path
        
        # 测试使用video_path删除
        result = self.video_processor.delete_thumbnail(video_path=self.mock_video_path)
        self.assertTrue(result)
        self.assertFalse(os.path.exists(test_thumb_path))
        self.assertFalse(self.mock_video_path in self.video_processor._thumb_map)
        
        # 创建另一个缩略图文件
        test_thumb_path2 = os.path.join(self.thumb_dir, "test_thumb2.jpg")
        with open(test_thumb_path2, 'wb') as f:
            f.write(b'\x00' * 100)  # 写入一些字节作为内容
        
        # 测试使用thumb_path删除
        result = self.video_processor.delete_thumbnail(thumb_path=test_thumb_path2)
        self.assertTrue(result)
        self.assertFalse(os.path.exists(test_thumb_path2))
    
    @patch('src.utils.video_processor.VideoFileClip')
    @patch('src.utils.video_processor.Image')
    def test_delete_thumbnail_with_resource_manager(self, mock_image, mock_video_clip):
        """测试使用资源管理器的缩略图删除功能"""
        # 设置模拟对象
        mock_clip_instance = MagicMock()
        mock_clip_instance.get_frame.return_value = MagicMock()
        mock_video_clip.return_value.__enter__.return_value = mock_clip_instance
        
        mock_img = MagicMock()
        mock_img.size = (640, 480)
        mock_image.fromarray.return_value = mock_img
        
        # 提取缩略图
        thumb_path = self.video_processor_with_rm.extract_thumbnail(self.mock_video_path)
        self.assertTrue(os.path.exists(thumb_path))
        
        # 删除缩略图
        result = self.video_processor_with_rm.delete_thumbnail(video_path=self.mock_video_path)
        self.assertTrue(result)
        
        # 由于资源管理器的管理，文件可能已经被删除
        if os.path.exists(thumb_path):
            self.fail("资源管理器未能删除缩略图文件")
    
    def test_clear_all_thumbnails(self):
        """测试清理所有缩略图功能"""
        # 创建多个缩略图文件
        test_files = []
        for i in range(5):
            thumb_path = os.path.join(self.thumb_dir, f"test_thumb_{i}.jpg")
            with open(thumb_path, 'wb') as f:
                f.write(b'\x00' * 100)
            test_files.append(thumb_path)
            # 添加到映射
            self.video_processor._thumb_map[f"video_{i}.mp4"] = thumb_path
        
        # 清理所有缩略图
        count = self.video_processor.clear_all_thumbnails()
        
        # 验证结果
        self.assertEqual(count, 5)
        for path in test_files:
            self.assertFalse(os.path.exists(path))
        self.assertEqual(len(self.video_processor._thumb_map), 0)

class TestVideoProcessorAsync(unittest.IsolatedAsyncioTestCase):
    """VideoProcessor异步方法单元测试"""
    
    async def asyncSetUp(self):
        """异步测试前准备"""
        # 创建临时目录用于测试
        self.temp_dir = tempfile.TemporaryDirectory()
        self.thumb_dir = os.path.join(self.temp_dir.name, "thumbnails")
        os.makedirs(self.thumb_dir, exist_ok=True)
        
        # 创建资源管理器
        self.resource_manager = ResourceManager(os.path.join(self.temp_dir.name, "resources"))
        
        # 创建两个VideoProcessor实例，一个使用资源管理器，一个不使用
        self.video_processor = VideoProcessor(thumb_dir=self.thumb_dir)
        self.video_processor_with_rm = VideoProcessor(
            resource_manager=self.resource_manager,
            thumb_dir=self.thumb_dir
        )
        
        # 创建测试视频的mock
        self.mock_video_path = os.path.join(self.temp_dir.name, "test_video.mp4")
        with open(self.mock_video_path, 'wb') as f:
            # 写入一些随机字节作为假视频文件
            f.write(b'\x00' * 1024)
    
    async def asyncTearDown(self):
        """异步测试后清理"""
        # 清理临时目录
        self.temp_dir.cleanup()
    
    @patch('src.utils.video_processor.VideoFileClip')
    @patch('src.utils.video_processor.Image')
    async def test_extract_thumbnail_async(self, mock_image, mock_video_clip):
        """测试异步缩略图提取功能"""
        # 设置模拟对象
        mock_clip_instance = MagicMock()
        mock_clip_instance.get_frame.return_value = MagicMock()
        mock_video_clip.return_value.__enter__.return_value = mock_clip_instance
        
        mock_img = MagicMock()
        mock_img.size = (640, 480)
        mock_image.fromarray.return_value = mock_img
        
        # 调用测试方法
        thumb_path = await self.video_processor.extract_thumbnail_async(self.mock_video_path)
        
        # 验证结果
        self.assertIsNotNone(thumb_path)
        self.assertTrue(os.path.exists(thumb_path))
        self.assertTrue(thumb_path.endswith(".jpg"))
        
        # 验证方法调用
        mock_clip_instance.get_frame.assert_called_with(0)
        mock_img.resize.assert_called()
        mock_img.save.assert_called()
    
    @patch('src.utils.video_processor.VideoFileClip')
    @patch('src.utils.video_processor.Image')
    async def test_extract_thumbnail_async_with_resource_manager(self, mock_image, mock_video_clip):
        """测试使用资源管理器的异步缩略图提取功能"""
        # 设置模拟对象
        mock_clip_instance = MagicMock()
        mock_clip_instance.get_frame.return_value = MagicMock()
        mock_video_clip.return_value.__enter__.return_value = mock_clip_instance
        
        mock_img = MagicMock()
        mock_img.size = (640, 480)
        mock_image.fromarray.return_value = mock_img
        
        # 调用测试方法
        thumb_path = await self.video_processor_with_rm.extract_thumbnail_async(self.mock_video_path)
        
        # 验证结果
        self.assertIsNotNone(thumb_path)
        self.assertTrue(os.path.exists(thumb_path))
        self.assertTrue(thumb_path.endswith(".jpg"))
        
        # 验证映射
        self.assertTrue(self.mock_video_path in self.video_processor_with_rm._thumb_map)
        self.assertEqual(self.video_processor_with_rm._thumb_map[self.mock_video_path], thumb_path)
        
        # 验证方法调用
        mock_clip_instance.get_frame.assert_called_with(0)
        mock_img.resize.assert_called()
        mock_img.save.assert_called()

if __name__ == '__main__':
    unittest.main() 