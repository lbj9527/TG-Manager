#!/usr/bin/env python3
"""
媒体组处理场景专项测试
专门测试媒体组在各种配置组合下的处理逻辑
"""

import asyncio
import sys
import os
import time
from typing import Dict, List, Any
from unittest.mock import Mock, AsyncMock

# 添加项目根目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../'))

from src.modules.monitor.media_group_handler import MediaGroupHandler
from src.modules.monitor.message_processor import MessageProcessor
from src.utils.channel_resolver import ChannelResolver
from src.utils.ui_config_models import MediaType

# 导入测试数据工厂
sys.path.append(os.path.dirname(__file__))
from test_monitor_comprehensive import TestDataFactory


class MediaGroupScenarioTester:
    """媒体组场景测试器"""
    
    def __init__(self):
        self.test_results = []
        self.api_calls = []
        
    def setup_mocks(self):
        """设置Mock对象"""
        # 创建客户端Mock
        client = Mock()
        client.copy_media_group = AsyncMock(side_effect=self._mock_copy_media_group)
        client.send_media_group = AsyncMock(side_effect=self._mock_send_media_group)
        client.forward_messages = AsyncMock(side_effect=self._mock_forward_messages)
        client.get_media_group = AsyncMock(side_effect=self._mock_get_media_group)
        
        # 创建频道解析器Mock
        channel_resolver = Mock(spec=ChannelResolver)
        channel_resolver.format_channel_info = AsyncMock(
            return_value=("测试频道 (ID: -1001234567890)", ("测试频道", "test_channel"))
        )
        
        return client, channel_resolver
    
    async def _mock_copy_media_group(self, chat_id, from_chat_id, message_id, **kwargs):
        """模拟复制媒体组"""
        self.api_calls.append(('copy_media_group', chat_id, from_chat_id, message_id))
        return [Mock(id=5000 + i) for i in range(3)]
    
    async def _mock_send_media_group(self, chat_id, media, **kwargs):
        """模拟发送媒体组"""
        self.api_calls.append(('send_media_group', chat_id, len(media)))
        return [Mock(id=6000 + i) for i in range(len(media))]
    
    async def _mock_forward_messages(self, chat_id, from_chat_id, message_ids, **kwargs):
        """模拟转发消息"""
        self.api_calls.append(('forward_messages', chat_id, from_chat_id, message_ids))
        return [Mock(id=7000 + i) for i in range(len(message_ids))]
    
    async def _mock_get_media_group(self, chat_id, message_id):
        """模拟获取媒体组"""
        self.api_calls.append(('get_media_group', chat_id, message_id))
        # 返回3条消息的媒体组
        messages = []
        for i in range(3):
            if i == 0:
                msg = TestDataFactory.create_photo_message(
                    message_id=message_id + i,
                    chat_id=chat_id,
                    media_group_id=f"group_{message_id}",
                    caption="媒体组标题"
                )
            else:
                msg = TestDataFactory.create_video_message(
                    message_id=message_id + i,
                    chat_id=chat_id,
                    media_group_id=f"group_{message_id}"
                )
            messages.append(msg)
        return messages
    
    def create_test_config(self, **overrides) -> Dict[str, Any]:
        """创建测试配置"""
        config = {
            'source_channel': 'test_source',
            'target_channels': [
                ('test_target1', -1002000000001, '目标频道1'),
                ('test_target2', -1002000000002, '目标频道2')
            ],
            'keywords': [],
            'exclude_forwards': False,
            'exclude_replies': False,
            'exclude_text': False,
            'exclude_links': False,
            'remove_captions': False,
            'media_types': [MediaType.PHOTO, MediaType.VIDEO, MediaType.DOCUMENT],
            'text_replacements': {}
        }
        config.update(overrides)
        return config
    
    async def test_scenario(self, scenario_name: str, messages: List[Mock], config: Dict[str, Any]) -> Dict[str, Any]:
        """测试单个场景"""
        print(f"🧪 测试场景: {scenario_name}")
        
        # 重置API调用记录
        self.api_calls.clear()
        
        # 设置Mock
        client, channel_resolver = self.setup_mocks()
        
        # 创建处理器
        message_processor = MessageProcessor(client, channel_resolver)
        media_group_handler = MediaGroupHandler(client, channel_resolver, message_processor)
        
        # 启动清理任务
        media_group_handler.start_cleanup_task()
        
        start_time = time.time()
        
        try:
            # 逐个处理消息，模拟真实的消息接收
            for message in messages:
                await media_group_handler.handle_media_group_message(message, config)
                # 短暂延迟，模拟消息间隔
                await asyncio.sleep(0.01)
            
            # 等待可能的延迟处理
            await asyncio.sleep(0.2)
            
            execution_time = time.time() - start_time
            
            result = {
                'scenario': scenario_name,
                'success': True,
                'execution_time': execution_time,
                'api_calls': len(self.api_calls),
                'api_call_types': [call[0] for call in self.api_calls],
                'messages_processed': len(messages),
                'details': f"处理了 {len(messages)} 条消息，产生 {len(self.api_calls)} 次API调用"
            }
            
            print(f"   ✅ 成功 - {result['details']}")
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            result = {
                'scenario': scenario_name,
                'success': False,
                'execution_time': execution_time,
                'error': str(e),
                'api_calls': len(self.api_calls),
                'messages_processed': len(messages),
                'details': f"执行异常: {str(e)}"
            }
            
            print(f"   ❌ 失败 - {result['details']}")
            return result
        
        finally:
            # 停止处理器
            await media_group_handler.stop()
    
    async def run_all_scenarios(self):
        """运行所有媒体组测试场景"""
        print("🚀 开始媒体组场景测试...")
        
        scenarios = [
            await self.test_basic_media_group(),
            await self.test_filtered_media_group(),
            await self.test_text_replacement(),
            await self.test_caption_removal(),
            await self.test_partial_filtering(),
            await self.test_keyword_filtering(),
            await self.test_media_type_filtering(),
            await self.test_large_media_group(),
            await self.test_single_message_in_group(),
            await self.test_mixed_media_types()
        ]
        
        self.test_results.extend(scenarios)
        self.print_summary()
    
    async def test_basic_media_group(self):
        """测试基础媒体组转发"""
        messages = [
            TestDataFactory.create_photo_message(
                message_id=1001, 
                media_group_id="group_basic",
                media_group_count=3,
                caption="基础媒体组测试"
            ),
            TestDataFactory.create_video_message(
                message_id=1002, 
                media_group_id="group_basic",
                media_group_count=3
            ),
            TestDataFactory.create_photo_message(
                message_id=1003, 
                media_group_id="group_basic",
                media_group_count=3
            )
        ]
        
        config = self.create_test_config()
        return await self.test_scenario("基础媒体组转发", messages, config)
    
    async def test_filtered_media_group(self):
        """测试媒体组部分过滤"""
        messages = [
            TestDataFactory.create_photo_message(
                message_id=2001, 
                media_group_id="group_filtered",
                media_group_count=4,
                caption="允许的照片"
            ),
            TestDataFactory.create_video_message(
                message_id=2002, 
                media_group_id="group_filtered",
                media_group_count=4
            ),
            TestDataFactory.create_document_message(
                message_id=2003, 
                media_group_id="group_filtered",
                media_group_count=4
            ),
            TestDataFactory.create_document_message(  # 改为文档消息
                message_id=2004, 
                media_group_id="group_filtered",
                media_group_count=4
            )
        ]
        
        config = self.create_test_config(
            media_types=[MediaType.PHOTO, MediaType.VIDEO]  # 只允许照片和视频，文档会被过滤
        )
        return await self.test_scenario("媒体组部分过滤", messages, config)
    
    async def test_text_replacement(self):
        """测试文本替换"""
        messages = [
            TestDataFactory.create_photo_message(
                message_id=3001, 
                media_group_id="group_replace",
                media_group_count=2,
                caption="这是旧版本的标题"
            ),
            TestDataFactory.create_video_message(
                message_id=3002, 
                media_group_id="group_replace",
                media_group_count=2
            )
        ]
        
        config = self.create_test_config(
            text_replacements={'旧版本': '新版本'}
        )
        return await self.test_scenario("文本替换", messages, config)
    
    async def test_caption_removal(self):
        """测试标题移除"""
        messages = [
            TestDataFactory.create_photo_message(
                message_id=4001, 
                media_group_id="group_no_caption",
                media_group_count=2,
                caption="需要移除的标题"
            ),
            TestDataFactory.create_video_message(
                message_id=4002, 
                media_group_id="group_no_caption",
                media_group_count=2
            )
        ]
        
        config = self.create_test_config(
            remove_captions=True
        )
        return await self.test_scenario("标题移除", messages, config)
    
    async def test_partial_filtering(self):
        """测试部分消息被过滤的情况"""
        messages = [
            TestDataFactory.create_photo_message(
                message_id=5001, 
                media_group_id="group_partial",
                media_group_count=3,
                caption="包含关键词"
            ),
            TestDataFactory.create_video_message(
                message_id=5002, 
                media_group_id="group_partial",
                media_group_count=3,
                caption="不包含目标词汇"
            ),
            TestDataFactory.create_photo_message(
                message_id=5003, 
                media_group_id="group_partial",
                media_group_count=3,
                caption="包含关键词"
            )
        ]
        
        config = self.create_test_config(
            keywords=['关键词']
        )
        return await self.test_scenario("部分消息过滤", messages, config)
    
    async def test_keyword_filtering(self):
        """测试关键词过滤"""
        messages = [
            TestDataFactory.create_photo_message(
                message_id=6001, 
                media_group_id="group_keyword",
                media_group_count=2,
                caption="普通消息内容"
            ),
            TestDataFactory.create_video_message(
                message_id=6002, 
                media_group_id="group_keyword",
                media_group_count=2,
                caption="不相关内容"
            )
        ]
        
        config = self.create_test_config(
            keywords=['重要', '紧急']  # 消息中没有这些关键词
        )
        return await self.test_scenario("关键词过滤", messages, config)
    
    async def test_media_type_filtering(self):
        """测试媒体类型过滤"""
        messages = [
            TestDataFactory.create_photo_message(
                message_id=7001, 
                media_group_id="group_media_filter",
                media_group_count=3
            ),
            TestDataFactory.create_video_message(
                message_id=7002, 
                media_group_id="group_media_filter",
                media_group_count=3
            ),
            TestDataFactory.create_document_message(
                message_id=7003, 
                media_group_id="group_media_filter",
                media_group_count=3
            )
        ]
        
        config = self.create_test_config(
            media_types=[MediaType.PHOTO]  # 只允许照片
        )
        return await self.test_scenario("媒体类型过滤", messages, config)
    
    async def test_large_media_group(self):
        """测试大型媒体组"""
        messages = []
        for i in range(10):
            if i % 2 == 0:
                msg = TestDataFactory.create_photo_message(
                    message_id=8001 + i, 
                    media_group_id="group_large",
                    media_group_count=10,
                    caption=f"照片 {i+1}" if i == 0 else None
                )
            else:
                msg = TestDataFactory.create_video_message(
                    message_id=8001 + i, 
                    media_group_id="group_large",
                    media_group_count=10
                )
            messages.append(msg)
        
        config = self.create_test_config()
        return await self.test_scenario("大型媒体组", messages, config)
    
    async def test_single_message_in_group(self):
        """测试媒体组中的单条消息"""
        messages = [
            TestDataFactory.create_photo_message(
                message_id=9001, 
                media_group_id="group_single",
                media_group_count=1,
                caption="单条消息的媒体组"
            )
        ]
        
        config = self.create_test_config()
        return await self.test_scenario("单条消息媒体组", messages, config)
    
    async def test_mixed_media_types(self):
        """测试混合媒体类型"""
        messages = [
            TestDataFactory.create_photo_message(
                message_id=10001, 
                media_group_id="group_mixed",
                media_group_count=4,
                caption="混合媒体组"
            ),
            TestDataFactory.create_video_message(
                message_id=10002, 
                media_group_id="group_mixed",
                media_group_count=4
            ),
            TestDataFactory.create_document_message(
                message_id=10003, 
                media_group_id="group_mixed",
                media_group_count=4
            ),
            TestDataFactory.create_document_message(  # 改为文档消息
                message_id=10004, 
                media_group_id="group_mixed",
                media_group_count=4
            )
        ]
        
        config = self.create_test_config()
        return await self.test_scenario("混合媒体类型", messages, config)
    
    def print_summary(self):
        """打印测试摘要"""
        total_tests = len(self.test_results)
        successful_tests = sum(1 for result in self.test_results if result['success'])
        failed_tests = total_tests - successful_tests
        
        print(f"\n" + "="*60)
        print(f"📊 媒体组场景测试摘要")
        print(f"="*60)
        
        print(f"\n🎯 总体结果:")
        print(f"   总测试数: {total_tests}")
        print(f"   成功: {successful_tests} ✅")
        print(f"   失败: {failed_tests} ❌")
        print(f"   成功率: {(successful_tests/total_tests*100):.1f}%")
        
        # 性能统计
        execution_times = [r['execution_time'] for r in self.test_results]
        avg_time = sum(execution_times) / len(execution_times) if execution_times else 0
        total_api_calls = sum(r['api_calls'] for r in self.test_results)
        
        print(f"\n⚡ 性能统计:")
        print(f"   平均执行时间: {avg_time:.3f}秒")
        print(f"   总API调用: {total_api_calls}")
        print(f"   平均API调用/测试: {total_api_calls/total_tests:.1f}")
        
        print(f"\n📋 详细结果:")
        for result in self.test_results:
            status = "✅" if result['success'] else "❌"
            print(f"   {status} {result['scenario']}: {result['details']}")
            if not result['success']:
                print(f"      错误: {result.get('error', '未知错误')}")
        
        if successful_tests == total_tests:
            print(f"\n🎉 所有媒体组测试场景都通过了！")
        else:
            print(f"\n⚠️ 有 {failed_tests} 个测试场景需要修复。")


async def main():
    """主函数"""
    tester = MediaGroupScenarioTester()
    await tester.run_all_scenarios()


if __name__ == "__main__":
    asyncio.run(main()) 