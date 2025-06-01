"""
监听模块性能测试
测试监听模块在各种负载下的性能表现
"""

import pytest
import asyncio
import time
import psutil
import threading
from unittest.mock import Mock, AsyncMock, patch
from typing import List, Dict, Any

from tests.modules.monitor.test_monitor_comprehensive import TestDataFactory
from src.modules.monitor.media_group_handler import MediaGroupHandler
from src.modules.monitor.message_processor import MessageProcessor


class PerformanceTestSuite:
    """性能测试套件"""
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_single_message_processing_speed(self, mock_client, mock_channel_resolver, performance_benchmarks):
        """测试单条消息处理速度"""
        processor = MessageProcessor(mock_client, mock_channel_resolver)
        processor.set_monitor_config({})
        
        message = TestDataFactory.create_mock_message(text="性能测试消息")
        target_channels = [("target", -1001111111111, "目标频道")]
        
        # 测试单次处理时间
        start_time = time.time()
        await processor.forward_message(message, target_channels)
        processing_time = time.time() - start_time
        
        # 验证处理时间在基准范围内
        assert processing_time < performance_benchmarks['message_processing_time'], \
            f"消息处理时间 {processing_time:.3f}s 超过基准 {performance_benchmarks['message_processing_time']}s"
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_media_group_processing_speed(self, mock_client, mock_channel_resolver, performance_benchmarks):
        """测试媒体组处理速度"""
        message_processor = Mock()
        handler = MediaGroupHandler(mock_client, mock_channel_resolver, message_processor)
        
        # 创建包含多条消息的媒体组
        messages = TestDataFactory.create_media_group_messages(count=5)
        pair_config = {
            'keywords': [],
            'exclude_forwards': False,
            'exclude_replies': False,
            'exclude_text': False,
            'exclude_links': False,
            'media_types': ['photo', 'video', 'document'],
            'target_channels': [("target", -1001111111111, "目标频道")],
            'text_replacements': {}
        }
        
        # 模拟处理方法
        with patch.object(handler, '_process_media_group', new_callable=AsyncMock) as mock_process:
            start_time = time.time()
            
            # 处理所有消息
            for message in messages:
                await handler.handle_media_group_message(message, pair_config)
            
            processing_time = time.time() - start_time
            
            # 验证处理时间
            assert processing_time < performance_benchmarks['media_group_processing_time'], \
                f"媒体组处理时间 {processing_time:.3f}s 超过基准 {performance_benchmarks['media_group_processing_time']}s"
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_concurrent_message_processing(self, mock_client, mock_channel_resolver, performance_benchmarks):
        """测试并发消息处理性能"""
        processor = MessageProcessor(mock_client, mock_channel_resolver)
        processor.set_monitor_config({})
        
        # 创建多条测试消息
        messages = [
            TestDataFactory.create_mock_message(message_id=i, text=f"并发测试消息 {i}")
            for i in range(performance_benchmarks['max_concurrent_operations'])
        ]
        target_channels = [("target", -1001111111111, "目标频道")]
        
        # 并发处理消息
        start_time = time.time()
        tasks = [
            processor.forward_message(message, target_channels)
            for message in messages
        ]
        await asyncio.gather(*tasks)
        processing_time = time.time() - start_time
        
        # 验证并发处理效率
        avg_time_per_message = processing_time / len(messages)
        assert avg_time_per_message < performance_benchmarks['message_processing_time'], \
            f"并发处理平均时间 {avg_time_per_message:.3f}s 超过基准"
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_memory_usage_during_processing(self, mock_client, mock_channel_resolver, performance_benchmarks):
        """测试处理过程中的内存使用"""
        handler = MediaGroupHandler(mock_client, mock_channel_resolver, Mock())
        
        # 记录初始内存使用
        process = psutil.Process()
        initial_memory = process.memory_info().rss
        
        # 模拟大量媒体组处理
        for i in range(50):  # 处理50个媒体组
            messages = TestDataFactory.create_media_group_messages(
                count=3, 
                media_group_id=f"group_{i}"
            )
            pair_config = {
                'keywords': [],
                'exclude_forwards': False,
                'exclude_replies': False,
                'exclude_text': False,
                'exclude_links': False,
                'media_types': ['photo', 'video', 'document'],
                'target_channels': [("target", -1001111111111, "目标频道")],
                'text_replacements': {}
            }
            
            for message in messages:
                await handler.handle_media_group_message(message, pair_config)
        
        # 检查内存使用增长
        final_memory = process.memory_info().rss
        memory_growth = final_memory - initial_memory
        
        assert memory_growth < performance_benchmarks['memory_usage_limit'], \
            f"内存增长 {memory_growth / 1024 / 1024:.2f}MB 超过限制"
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_cache_efficiency(self, mock_client, mock_channel_resolver):
        """测试缓存效率"""
        handler = MediaGroupHandler(mock_client, mock_channel_resolver, Mock())
        
        media_group_id = "cache_test_group"
        messages = TestDataFactory.create_media_group_messages(
            count=10, 
            media_group_id=media_group_id
        )
        pair_config = {
            'keywords': [],
            'exclude_forwards': False,
            'exclude_replies': False,
            'exclude_text': False,
            'exclude_links': False,
            'media_types': ['photo', 'video', 'document'],
            'target_channels': [("target", -1001111111111, "目标频道")],
            'text_replacements': {}
        }
        
        # 测试缓存命中率
        cache_hits = 0
        for message in messages:
            # 第一次添加
            await handler.handle_media_group_message(message, pair_config)
            
            # 第二次添加同样的消息（应该被缓存机制忽略）
            initial_cache_size = len(handler.media_group_cache.get(message.chat.id, {}).get(media_group_id, {}).get('messages', []))
            await handler.handle_media_group_message(message, pair_config)
            final_cache_size = len(handler.media_group_cache.get(message.chat.id, {}).get(media_group_id, {}).get('messages', []))
            
            if initial_cache_size == final_cache_size:
                cache_hits += 1
        
        # 验证缓存效率
        cache_hit_rate = cache_hits / len(messages)
        assert cache_hit_rate > 0.8, f"缓存命中率 {cache_hit_rate:.2f} 低于期望值 0.8"
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_api_call_rate_limiting(self, mock_client, mock_channel_resolver):
        """测试API调用频率限制"""
        handler = MediaGroupHandler(mock_client, mock_channel_resolver, Mock())
        
        # 模拟API调用频率限制
        api_calls = []
        
        def track_api_call(*args, **kwargs):
            api_calls.append(time.time())
            return AsyncMock()()
        
        mock_client.get_media_group.side_effect = track_api_call
        
        # 快速连续创建多个媒体组请求
        for i in range(10):
            message = TestDataFactory.create_photo_message(
                media_group_id=f"rate_limit_test_{i}",
                media_group_count=5
            )
            pair_config = {
                'keywords': [],
                'exclude_forwards': False,
                'exclude_replies': False,
                'exclude_text': False,
                'exclude_links': False,
                'media_types': ['photo'],
                'target_channels': [("target", -1001111111111, "目标频道")]
            }
            
            await handler.handle_media_group_message(message, pair_config)
        
        # 等待API请求处理
        await asyncio.sleep(2)
        
        # 验证API调用间隔
        if len(api_calls) > 1:
            intervals = [api_calls[i] - api_calls[i-1] for i in range(1, len(api_calls))]
            avg_interval = sum(intervals) / len(intervals)
            
            # 验证平均间隔符合限制要求
            assert avg_interval >= 0.1, f"API调用间隔 {avg_interval:.3f}s 过于频繁"
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_large_media_group_handling(self, mock_client, mock_channel_resolver):
        """测试大型媒体组处理"""
        handler = MediaGroupHandler(mock_client, mock_channel_resolver, Mock())
        
        # 创建大型媒体组（20条消息）
        large_media_group = TestDataFactory.create_media_group_messages(
            count=20,
            media_group_id="large_group_test"
        )
        pair_config = {
            'keywords': [],
            'exclude_forwards': False,
            'exclude_replies': False,
            'exclude_text': False,
            'exclude_links': False,
            'media_types': ['photo', 'video', 'document'],
            'target_channels': [("target", -1001111111111, "目标频道")],
            'text_replacements': {}
        }
        
        # 测试处理时间
        start_time = time.time()
        
        with patch.object(handler, '_process_media_group', new_callable=AsyncMock) as mock_process:
            for message in large_media_group:
                await handler.handle_media_group_message(message, pair_config)
        
        processing_time = time.time() - start_time
        
        # 验证大型媒体组处理时间合理
        assert processing_time < 2.0, f"大型媒体组处理时间 {processing_time:.3f}s 过长"
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_text_replacement_performance(self):
        """测试文本替换性能"""
        from src.modules.monitor.text_filter import TextFilter
        
        # 创建大量替换规则
        replacements = {f"text_{i}": f"replaced_{i}" for i in range(1000)}
        
        # 创建包含多个需要替换文本的长文本
        test_text = " ".join([f"text_{i}" for i in range(0, 1000, 10)]) * 10
        
        # 测试替换性能
        start_time = time.time()
        result = TextFilter.apply_text_replacements_static(test_text, replacements)
        processing_time = time.time() - start_time
        
        # 验证替换性能
        assert processing_time < 0.1, f"文本替换时间 {processing_time:.3f}s 过长"
        assert "replaced_" in result, "文本替换未正常工作"
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_cleanup_task_efficiency(self, mock_client, mock_channel_resolver):
        """测试清理任务效率"""
        handler = MediaGroupHandler(mock_client, mock_channel_resolver, Mock())
        
        # 添加大量过期数据
        for i in range(100):
            handler.processed_media_groups.add(f"group_{i}")
            handler.last_media_group_fetch[f"group_{i}"] = time.time() - 3600  # 1小时前
        
        # 记录初始数据量
        initial_processed_count = len(handler.processed_media_groups)
        initial_fetch_count = len(handler.last_media_group_fetch)
        
        # 触发清理
        handler.last_processed_groups_cleanup = time.time() - 3601  # 超过1小时
        
        # 模拟清理过程
        start_time = time.time()
        await handler._cleanup_processed_groups()
        cleanup_time = time.time() - start_time
        
        # 验证清理效率和效果
        assert cleanup_time < 0.5, f"清理任务时间 {cleanup_time:.3f}s 过长"
        
        # 验证清理效果（如果数据量超过阈值应该被清理）
        if initial_processed_count > 1000:
            assert len(handler.processed_media_groups) == 0, "清理任务未正常工作"


@pytest.mark.performance
class TestLoadTesting:
    """负载测试"""
    
    @pytest.mark.asyncio
    async def test_high_frequency_message_processing(self, mock_client, mock_channel_resolver):
        """测试高频消息处理"""
        processor = MessageProcessor(mock_client, mock_channel_resolver)
        processor.set_monitor_config({})
        
        target_channels = [("target", -1001111111111, "目标频道")]
        message_count = 100
        
        # 模拟高频消息
        start_time = time.time()
        tasks = []
        
        for i in range(message_count):
            message = TestDataFactory.create_mock_message(
                message_id=i,
                text=f"高频测试消息 {i}"
            )
            task = processor.forward_message(message, target_channels)
            tasks.append(task)
        
        # 执行所有任务
        await asyncio.gather(*tasks, return_exceptions=True)
        
        total_time = time.time() - start_time
        messages_per_second = message_count / total_time
        
        # 验证处理速度
        assert messages_per_second > 10, f"消息处理速度 {messages_per_second:.2f} msg/s 过低"
    
    @pytest.mark.asyncio
    async def test_memory_stability_under_load(self, mock_client, mock_channel_resolver):
        """测试负载下的内存稳定性"""
        handler = MediaGroupHandler(mock_client, mock_channel_resolver, Mock())
        
        process = psutil.Process()
        memory_samples = []
        
        # 持续处理消息并监控内存
        for batch in range(20):  # 20批次
            # 记录内存使用
            memory_samples.append(process.memory_info().rss)
            
            # 处理一批消息
            for i in range(10):  # 每批10条消息
                message = TestDataFactory.create_photo_message(
                    message_id=batch * 10 + i,
                    media_group_id=f"load_test_group_{batch}_{i}"
                )
                pair_config = {
                    'keywords': [],
                    'exclude_forwards': False,
                    'exclude_replies': False,
                    'exclude_text': False,
                    'exclude_links': False,
                    'media_types': ['photo'],
                    'target_channels': [("target", -1001111111111, "目标频道")],
                    'text_replacements': {}
                }
                
                await handler.handle_media_group_message(message, pair_config)
            
            # 短暂等待
            await asyncio.sleep(0.1)
        
        # 分析内存趋势
        memory_growth = memory_samples[-1] - memory_samples[0]
        max_memory = max(memory_samples)
        
        # 验证内存稳定性
        assert memory_growth < 50 * 1024 * 1024, f"内存增长 {memory_growth / 1024 / 1024:.2f}MB 过大"
        assert max_memory < 200 * 1024 * 1024, f"峰值内存 {max_memory / 1024 / 1024:.2f}MB 过高"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "performance"]) 