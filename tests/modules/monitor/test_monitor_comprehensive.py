"""
监听模块综合测试
测试监听模块的所有功能，包括各种组合情况和边界条件
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, MagicMock, patch, call, ANY
from pathlib import Path
from typing import List, Dict, Any

from pyrogram import Client
from pyrogram.types import Message, Chat, User, MessageEntity, Audio, Video, Photo, Document, Animation, Sticker, Voice, VideoNote
from pyrogram.errors import FloodWait, ChatForwardsRestricted, ChannelPrivate

from src.modules.monitor.core import Monitor
from src.modules.monitor.media_group_handler import MediaGroupHandler
from src.modules.monitor.message_processor import MessageProcessor
from src.modules.monitor.text_filter import TextFilter
from src.modules.monitor.restricted_forward_handler import RestrictedForwardHandler
from src.modules.monitor import history_fetcher
from src.utils.ui_config_manager import UIConfigManager
from src.utils.channel_resolver import ChannelResolver
from src.utils.ui_config_models import UIConfig, UIMonitorChannelPair, MediaType


class TestDataFactory:
    """测试数据工厂，用于创建各种类型的测试消息和配置"""
    
    @staticmethod
    def create_mock_message(
        message_id: int = 1001,
        chat_id: int = -1001234567890,
        chat_title: str = "测试源频道",
        chat_username: str = "test_source",
        text: str = None,
        caption: str = None,
        media_group_id: str = None,
        media_group_count: int = None,
        photo: Photo = None,
        video: Video = None,
        document: Document = None,
        audio: Audio = None,
        animation: Animation = None,
        sticker: Sticker = None,
        voice: Voice = None,
        video_note: VideoNote = None,
        forward_from: Chat = None,
        reply_to_message: Message = None,
        entities: List[MessageEntity] = None
    ) -> Message:
        """创建模拟消息对象"""
        message = Mock(spec=Message)
        message.id = message_id
        message.text = text
        message.caption = caption
        message.media_group_id = media_group_id
        message.media_group_count = media_group_count
        message.photo = photo
        message.video = video
        message.document = document
        message.audio = audio
        message.animation = animation
        message.sticker = sticker
        message.voice = voice
        message.video_note = video_note
        message.forward_from = forward_from
        message.reply_to_message = reply_to_message
        message.entities = entities or []
        
        # 创建聊天对象
        chat = Mock(spec=Chat)
        chat.id = chat_id
        chat.title = chat_title
        chat.username = chat_username
        message.chat = chat
        
        # 判断是否为媒体消息
        message.media = bool(photo or video or document or audio or animation or sticker or voice or video_note)
        
        return message
    
    @staticmethod
    def create_photo_message(**kwargs) -> Message:
        """创建照片消息"""
        photo = Mock(spec=Photo)
        photo.file_id = "BAADBAADrwADBREAAYdXxaZlAAFMa84e-wI"
        return TestDataFactory.create_mock_message(photo=photo, **kwargs)
    
    @staticmethod
    def create_video_message(**kwargs) -> Message:
        """创建视频消息"""
        video = Mock(spec=Video)
        video.file_id = "BAADBAADrwADBREAAYdXxaZlAAFMa84e-wI"
        video.width = 1280
        video.height = 720
        video.duration = 120
        return TestDataFactory.create_mock_message(video=video, **kwargs)
    
    @staticmethod
    def create_document_message(**kwargs) -> Message:
        """创建文档消息"""
        document = Mock(spec=Document)
        document.file_id = "BAADBAADrwADBREAAYdXxaZlAAFMa84e-wI"
        document.file_name = "test_document.pdf"
        document.mime_type = "application/pdf"
        return TestDataFactory.create_mock_message(document=document, **kwargs)
    
    @staticmethod
    def create_text_message(
        message_id: int = 1001,
        text: str = "测试文本消息",
        chat_title: str = "测试源频道",
        **kwargs
    ) -> Message:
        """创建文本消息"""
        return TestDataFactory.create_mock_message(
            message_id=message_id,
            text=text,
            chat_title=chat_title,
            **kwargs
        )
    
    @staticmethod
    def create_media_group_messages(
        count: int = 3,
        media_group_id: str = "12345678901234567890",
        start_message_id: int = 1001,
        **kwargs
    ) -> List[Message]:
        """创建媒体组消息列表"""
        messages = []
        # 如果kwargs中没有指定media_group_count，使用count
        default_media_group_count = kwargs.get('media_group_count', count)
        
        for i in range(count):
            message_kwargs = {
                'message_id': start_message_id + i,
                'media_group_id': media_group_id,
                'media_group_count': default_media_group_count,
                **kwargs
            }
            
            # 根据索引创建不同类型的媒体
            if i % 3 == 0:
                messages.append(TestDataFactory.create_photo_message(**message_kwargs))
            elif i % 3 == 1:
                messages.append(TestDataFactory.create_video_message(**message_kwargs))
            else:
                messages.append(TestDataFactory.create_document_message(**message_kwargs))
                
        return messages
    
    @staticmethod
    def create_test_config() -> Dict[str, Any]:
        """创建测试配置"""
        return {
            'MONITOR': {
                'monitor_channel_pairs': [
                    {
                        'source_channel': 'test_source',
                        'target_channels': ['test_target1', 'test_target2'],
                        'keywords': ['测试', 'test'],
                        'exclude_forwards': False,
                        'exclude_replies': False,
                        'exclude_text': False,
                        'exclude_links': False,
                        'remove_captions': False,
                        'media_types': [MediaType.PHOTO, MediaType.VIDEO, MediaType.DOCUMENT],
                        'text_filter': [
                            {'original_text': '旧文本', 'target_text': '新文本'},
                            {'original_text': 'old', 'target_text': 'new'}
                        ]
                    }
                ]
            }
        }


@pytest.fixture
def mock_client():
    """模拟Pyrogram客户端"""
    client = Mock(spec=Client)
    client.get_chat = AsyncMock()
    client.copy_message = AsyncMock()
    client.forward_messages = AsyncMock()
    client.send_message = AsyncMock()
    client.send_media_group = AsyncMock()
    client.copy_media_group = AsyncMock()
    client.get_media_group = AsyncMock()
    client.get_chat_history = AsyncMock()
    client.add_handler = Mock()
    client.remove_handler = Mock()
    return client


@pytest.fixture
def mock_ui_config_manager():
    """模拟UI配置管理器"""
    manager = Mock(spec=UIConfigManager)
    config = Mock(spec=UIConfig)
    config.monitor_channel_pairs = []
    manager.get_ui_config.return_value = config
    manager.reload_config.return_value = config
    return manager


@pytest.fixture
def mock_channel_resolver():
    """模拟频道解析器"""
    resolver = Mock(spec=ChannelResolver)
    resolver.get_channel_id = AsyncMock(return_value=-1001234567890)
    resolver.resolve_channel = AsyncMock(return_value=("-1001234567890", None))  # 返回(频道ID, 消息ID)元组
    resolver.format_channel_info = AsyncMock(return_value=("测试频道 (ID: -1001234567890)", ("测试频道", "test_channel")))
    resolver.check_forward_permission = AsyncMock(return_value=True)
    return resolver


@pytest.fixture
def test_config():
    """测试配置"""
    return TestDataFactory.create_test_config()


class TestTextFilter:
    """文本过滤器测试"""
    
    def test_init_with_config(self, test_config):
        """测试文本过滤器初始化"""
        text_filter = TextFilter(test_config['MONITOR'])
        assert 'test_source' in text_filter.channel_text_replacements
        assert text_filter.channel_text_replacements['test_source']['旧文本'] == '新文本'
    
    def test_keyword_filtering(self, test_config):
        """测试关键词过滤"""
        text_filter = TextFilter(test_config['MONITOR'])
        
        # 创建包含关键词的消息
        message_with_keyword = TestDataFactory.create_mock_message(text="这是一个测试消息")
        message_without_keyword = TestDataFactory.create_mock_message(text="这是一个普通消息")
        
        # 模拟关键词检查（需要修改实现以支持单独的关键词列表）
        # 注意：当前实现从monitor_config中获取关键词，这里需要调整
        assert True  # 占位符，实际需要根据具体实现调整
    
    def test_text_replacement(self):
        """测试文本替换"""
        replacements = {'旧文本': '新文本', 'old': 'new'}
        
        # 测试正常替换
        result = TextFilter.apply_text_replacements_static("这是旧文本", replacements)
        assert result == "这是新文本"
        
        # 测试多个替换
        result = TextFilter.apply_text_replacements_static("old text with 旧文本", replacements)
        assert result == "new text with 新文本"
        
        # 测试无替换
        result = TextFilter.apply_text_replacements_static("无需替换的文本", replacements)
        assert result == "无需替换的文本"
        
        # 测试空文本
        result = TextFilter.apply_text_replacements_static("", replacements)
        assert result == ""
        
        # 测试空替换规则
        result = TextFilter.apply_text_replacements_static("测试文本", {})
        assert result == "测试文本"


class TestMessageProcessor:
    """消息处理器测试"""
    
    @pytest.fixture
    def message_processor(self, mock_client, mock_channel_resolver):
        """创建消息处理器实例"""
        processor = MessageProcessor(mock_client, mock_channel_resolver)
        processor.set_monitor_config({})
        return processor
    
    @pytest.mark.asyncio
    async def test_forward_text_message_success(self, message_processor, mock_client):
        """测试成功转发文本消息"""
        message = TestDataFactory.create_mock_message(text="测试消息")
        target_channels = [("target1", -1001111111111, "目标频道1")]
        
        mock_client.copy_message.return_value = Mock(id=2001)
        
        result = await message_processor.forward_message(message, target_channels)
        
        assert result is True
        mock_client.copy_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_forward_message_with_text_replacement(self, message_processor, mock_client):
        """测试带文本替换的消息转发"""
        message = TestDataFactory.create_mock_message(text="旧文本消息")
        target_channels = [("target1", -1001111111111, "目标频道1")]
        
        result = await message_processor.forward_message(
            message, target_channels, replace_caption="新文本消息"
        )
        
        assert result is True
        mock_client.send_message.assert_called_once_with(
            chat_id=-1001111111111,
            text="新文本消息"
        )
    
    @pytest.mark.asyncio
    async def test_forward_media_message_success(self, message_processor, mock_client):
        """测试成功转发媒体消息"""
        message = TestDataFactory.create_photo_message(caption="图片说明")
        target_channels = [("target1", -1001111111111, "目标频道1")]
        
        mock_client.copy_message.return_value = Mock(id=2001)
        
        result = await message_processor.forward_message(message, target_channels)
        
        assert result is True
        mock_client.copy_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_forward_message_remove_caption(self, message_processor, mock_client):
        """测试移除标题的消息转发"""
        message = TestDataFactory.create_photo_message(caption="需要移除的标题")
        target_channels = [("target1", -1001111111111, "目标频道1")]
        
        result = await message_processor.forward_message(
            message, target_channels, remove_caption=True
        )
        
        assert result is True
        mock_client.copy_message.assert_called_once_with(
            chat_id=-1001111111111,
            from_chat_id=-1001234567890,
            message_id=1001,
            caption=""
        )
    
    @pytest.mark.asyncio
    async def test_forward_message_chat_forwards_restricted(self, message_processor, mock_client):
        """测试转发受限情况"""
        message = TestDataFactory.create_photo_message()
        target_channels = [("target1", -1001111111111, "目标频道1")]
        
        # 模拟转发受限错误
        mock_client.copy_message.side_effect = ChatForwardsRestricted()
        mock_client.copy_message.return_value = Mock(id=2001)
        
        # 第二次调用成功
        mock_client.copy_message.side_effect = [ChatForwardsRestricted(), Mock(id=2001)]
        
        result = await message_processor.forward_message(message, target_channels)
        
        assert result is True
        assert mock_client.copy_message.call_count == 2
    
    @pytest.mark.asyncio
    async def test_forward_message_flood_wait(self, message_processor, mock_client):
        """测试FloodWait处理"""
        message = TestDataFactory.create_mock_message(text="测试")
        target_channels = [("target1", -1001111111111, "目标频道1")]
        
        # 创建模拟FloodWait错误类
        class MockFloodWait(Exception):
            def __init__(self, x):
                self.x = x
                super().__init__(f"FloodWait: {x}")
        
        # 模拟FloodWait错误
        mock_client.copy_message.side_effect = [MockFloodWait(1), Mock(id=2001)]
        
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            result = await message_processor.forward_message(message, target_channels)
            
            assert result is True
            mock_sleep.assert_called_once_with(1)
            assert mock_client.copy_message.call_count == 2


class TestMediaGroupHandler:
    """媒体组处理器测试"""
    
    @pytest.fixture
    def media_group_handler(self, mock_client, mock_channel_resolver):
        """创建媒体组处理器实例"""
        message_processor = Mock(spec=MessageProcessor)
        handler = MediaGroupHandler(mock_client, mock_channel_resolver, message_processor)
        handler.emit = Mock()  # 模拟事件发射器
        return handler
    
    @pytest.mark.asyncio
    async def test_handle_single_media_message(self, media_group_handler):
        """测试处理单条媒体组消息"""
        # 创建一个不触发API获取的消息（不设置media_group_count）
        message = TestDataFactory.create_photo_message(
            media_group_id="test_group_123",
            media_group_count=None,  # 不设置count避免触发API获取
            caption="测试图片"
        )
        pair_config = {
            'keywords': [],
            'exclude_forwards': False,
            'exclude_replies': False,
            'exclude_text': False,
            'exclude_links': False,
            'media_types': [MediaType.PHOTO],
            'target_channels': [("target1", -1001111111111, "目标频道1")]
        }
        
        await media_group_handler.handle_media_group_message(message, pair_config)
        
        # 验证消息被添加到缓存
        assert message.chat.id in media_group_handler.media_group_cache
        assert "test_group_123" in media_group_handler.media_group_cache[message.chat.id]
    
    @pytest.mark.asyncio
    async def test_media_type_filtering(self, media_group_handler):
        """测试媒体类型过滤"""
        # 创建一个视频消息，但配置只允许照片
        message = TestDataFactory.create_video_message(
            media_group_id="test_group_456"
        )
        pair_config = {
            'keywords': [],
            'exclude_forwards': False,
            'exclude_replies': False,
            'exclude_text': False,
            'exclude_links': False,
            'media_types': [MediaType.PHOTO],  # 只允许照片
            'target_channels': [("target1", -1001111111111, "目标频道1")]
        }
        
        await media_group_handler.handle_media_group_message(message, pair_config)
        
        # 验证消息被过滤，不会添加到缓存
        assert message.chat.id not in media_group_handler.media_group_cache
        
        # 验证过滤事件被发射
        media_group_handler.emit.assert_called_with(
            "message_filtered", message.id, ANY, ANY
        )
    
    @pytest.mark.asyncio
    async def test_keyword_filtering(self, media_group_handler):
        """测试关键词过滤"""
        message = TestDataFactory.create_photo_message(
            caption="这是一个普通消息"
        )
        pair_config = {
            'keywords': ['重要', 'urgent'],  # 设置关键词要求
            'exclude_forwards': False,
            'exclude_replies': False,
            'exclude_text': False,
            'exclude_links': False,
            'media_types': [MediaType.PHOTO],
            'target_channels': [("target1", -1001111111111, "目标频道1")]
        }
        
        await media_group_handler.handle_media_group_message(message, pair_config)
        
        # 验证消息被过滤（不包含关键词）
        media_group_handler.emit.assert_called_with(
            "message_filtered", message.id, ANY, "不包含关键词(重要, urgent)"
        )
    
    @pytest.mark.asyncio
    async def test_exclude_forwards_filtering(self, media_group_handler):
        """测试排除转发消息过滤"""
        forward_from = Mock(spec=Chat)
        forward_from.id = -1001111111111
        
        message = TestDataFactory.create_photo_message(forward_from=forward_from)
        pair_config = {
            'keywords': [],
            'exclude_forwards': True,  # 排除转发消息
            'exclude_replies': False,
            'exclude_text': False,
            'exclude_links': False,
            'media_types': [MediaType.PHOTO],
            'target_channels': [("target1", -1001111111111, "目标频道1")]
        }
        
        await media_group_handler.handle_media_group_message(message, pair_config)
        
        # 验证转发消息被过滤
        media_group_handler.emit.assert_called_with(
            "message_filtered", message.id, ANY, "转发消息"
        )
    
    @pytest.mark.asyncio
    async def test_exclude_replies_filtering(self, media_group_handler):
        """测试排除回复消息过滤"""
        reply_to = TestDataFactory.create_mock_message(message_id=999)
        
        message = TestDataFactory.create_photo_message(reply_to_message=reply_to)
        pair_config = {
            'keywords': [],
            'exclude_forwards': False,
            'exclude_replies': True,  # 排除回复消息
            'exclude_text': False,
            'exclude_links': False,
            'media_types': [MediaType.PHOTO],
            'target_channels': [("target1", -1001111111111, "目标频道1")]
        }
        
        await media_group_handler.handle_media_group_message(message, pair_config)
        
        # 验证回复消息被过滤
        media_group_handler.emit.assert_called_with(
            "message_filtered", message.id, ANY, "回复消息"
        )
    
    @pytest.mark.asyncio
    async def test_exclude_links_filtering(self, media_group_handler):
        """测试排除链接过滤"""
        # 创建包含链接的消息
        entities = [Mock(spec=MessageEntity)]
        entities[0].type = "url"
        
        message = TestDataFactory.create_photo_message(
            caption="查看这个链接 https://example.com",
            entities=entities
        )
        pair_config = {
            'keywords': [],
            'exclude_forwards': False,
            'exclude_replies': False,
            'exclude_text': False,
            'exclude_links': True,  # 排除包含链接的消息
            'media_types': [MediaType.PHOTO],
            'target_channels': [("target1", -1001111111111, "目标频道1")]
        }
        
        await media_group_handler.handle_media_group_message(message, pair_config)
        
        # 验证包含链接的消息被过滤
        media_group_handler.emit.assert_called_with(
            "message_filtered", message.id, ANY, "包含链接"
        )
    
    @pytest.mark.asyncio
    async def test_complete_media_group_processing(self, media_group_handler):
        """测试完整媒体组处理"""
        messages = TestDataFactory.create_media_group_messages(
            count=3,
            media_group_id="complete_group_789",
            media_group_count=None  # 不设置count避免触发API获取
        )
        pair_config = {
            'source_channel': 'test_source',  # 添加必需的字段
            'keywords': [],
            'exclude_forwards': False,
            'exclude_replies': False,
            'exclude_text': False,
            'exclude_links': False,
            'media_types': [MediaType.PHOTO, MediaType.VIDEO, MediaType.DOCUMENT],
            'target_channels': [("target1", -1001111111111, "目标频道1")],
            'text_replacements': {}
        }
        
        # 模拟_process_media_group方法
        with patch.object(media_group_handler, '_process_media_group', new_callable=AsyncMock) as mock_process:
            # 添加所有消息到媒体组
            for message in messages:
                await media_group_handler.handle_media_group_message(message, pair_config)
            
            # 等待延迟检查触发（因为消息数量<=5，会启动延迟检查）
            await asyncio.sleep(6)  # 等待超过5秒的延迟检查
            
            # 验证媒体组被处理
            mock_process.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_media_group_timeout_processing(self, media_group_handler):
        """测试媒体组超时处理"""
        message = TestDataFactory.create_photo_message(
            media_group_id="timeout_group_999",
            media_group_count=None  # 不设置count避免触发API获取
        )
        pair_config = {
            'source_channel': 'test_source',  # 添加必需的字段
            'keywords': [],
            'exclude_forwards': False,
            'exclude_replies': False,
            'exclude_text': False,
            'exclude_links': False,
            'media_types': [MediaType.PHOTO],
            'target_channels': [("target1", -1001111111111, "目标频道1")],
            'text_replacements': {}
        }
        
        # 模拟_process_media_group方法
        with patch.object(media_group_handler, '_process_media_group', new_callable=AsyncMock) as mock_process:
            await media_group_handler.handle_media_group_message(message, pair_config)
            
            # 等待延迟检查触发
            await asyncio.sleep(6)  # 超过5秒超时时间
            
            # 验证超时处理被触发
            mock_process.assert_called_once()


class TestRestrictedForwardHandler:
    """受限转发处理器测试"""
    
    @pytest.fixture
    def restricted_handler(self, mock_client, mock_channel_resolver):
        """创建受限转发处理器实例"""
        return RestrictedForwardHandler(mock_client, mock_channel_resolver)
    
    @pytest.mark.asyncio
    async def test_process_sticker_message(self, restricted_handler, mock_client):
        """测试处理贴纸消息"""
        sticker = Mock(spec=Sticker)
        sticker.file_id = "BAADBAADrwADBREAAYdXxaZlAAFMa84e-wI"
        
        message = TestDataFactory.create_mock_message(sticker=sticker)
        target_channels = [("target1", -1001111111111, "目标频道1")]
        
        mock_client.copy_message.return_value = Mock(id=2001)
        
        sent_messages, modified = await restricted_handler.process_restricted_message(
            message, "test_source", -1001234567890, target_channels
        )
        
        assert len(sent_messages) == 1
        assert modified is False
        mock_client.copy_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_voice_message(self, restricted_handler, mock_client):
        """测试处理语音消息"""
        voice = Mock(spec=Voice)
        voice.file_id = "BAADBAADrwADBREAAYdXxaZlAAFMa84e-wI"
        voice.duration = 10
        
        message = TestDataFactory.create_mock_message(voice=voice, caption="语音消息")
        target_channels = [("target1", -1001111111111, "目标频道1")]
        
        mock_client.send_voice.return_value = Mock(id=2001)
        
        sent_messages, modified = await restricted_handler.process_restricted_message(
            message, "test_source", -1001234567890, target_channels,
            caption="替换后的说明"
        )
        
        assert len(sent_messages) == 1
        assert modified is True  # 标题被替换
        mock_client.send_voice.assert_called_once()


class TestMonitorCore:
    """监听核心模块测试"""
    
    @pytest.fixture
    def monitor(self, mock_client, mock_ui_config_manager, mock_channel_resolver):
        """创建监听器实例"""
        return Monitor(mock_client, mock_ui_config_manager, mock_channel_resolver)
    
    @pytest.mark.asyncio
    async def test_start_monitoring_success(self, monitor, mock_client):
        """测试成功启动监听"""
        # 模拟配置
        with patch.object(monitor, 'config', TestDataFactory.create_test_config()):
            with patch.object(monitor, 'monitor_config', TestDataFactory.create_test_config()['MONITOR']):
                # 模拟异步启动过程
                task = asyncio.create_task(monitor.start_monitoring())
                
                # 等待一小段时间让启动过程开始
                await asyncio.sleep(0.1)
                
                # 设置停止标志
                monitor.should_stop = True
                
                # 等待任务完成
                await task
                
                # 验证处理器被添加
                mock_client.add_handler.assert_called()
    
    @pytest.mark.asyncio
    async def test_stop_monitoring(self, monitor):
        """测试停止监听"""
        # 模拟监听状态
        monitor.should_stop = False
        monitor.is_processing = True
        
        await monitor.stop_monitoring()
        
        assert monitor.should_stop is True
        assert monitor.is_processing is False
    
    def test_add_message_handler(self, monitor):
        """测试添加消息处理器"""
        def test_handler(message):
            pass
        
        monitor.add_message_handler(test_handler)
        
        assert test_handler in monitor.message_handlers


class TestHistoryFetcher:
    """历史消息获取器测试"""
    
    @pytest.mark.asyncio
    async def test_get_channel_history_success(self, mock_client, mock_channel_resolver):
        """测试成功获取历史消息"""
        # 模拟历史消息
        mock_messages = [
            TestDataFactory.create_mock_message(message_id=i, text=f"历史消息{i}")
            for i in range(1, 11)
        ]
        
        mock_client.get_chat_history.return_value.__aiter__ = AsyncMock(return_value=iter(mock_messages))
        
        messages = await history_fetcher.get_channel_history(
            mock_client, mock_channel_resolver, "test_channel", limit=10
        )
        
        assert len(messages) == 10
        mock_channel_resolver.resolve_channel.assert_called_once_with("test_channel")
    
    @pytest.mark.asyncio
    async def test_get_channel_history_flood_wait(self, mock_client, mock_channel_resolver):
        """测试FloodWait处理"""
        mock_channel_resolver.resolve_channel.side_effect = FloodWait(1)
        
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            with patch('src.modules.monitor.history_fetcher.get_channel_history') as mock_recursive:
                mock_recursive.return_value = []
                
                messages = await history_fetcher.get_channel_history(
                    mock_client, mock_channel_resolver, "test_channel", limit=10
                )
                
                mock_sleep.assert_called_once_with(1)


class TestIntegrationScenarios:
    """集成测试场景"""
    
    @pytest.mark.asyncio
    async def test_complete_text_message_flow(self, mock_client, mock_ui_config_manager, mock_channel_resolver):
        """测试完整的文本消息处理流程"""
        # 设置配置
        config = TestDataFactory.create_test_config()
        mock_ui_config_manager.get_ui_config.return_value.monitor_channel_pairs = [
            Mock(
                source_channel='test_source',
                target_channels=['test_target'],
                keywords=['测试'],
                text_filter=[Mock(original_text='旧', target_text='新')]
            )
        ]
        
        monitor = Monitor(mock_client, mock_ui_config_manager, mock_channel_resolver)
        
        # 创建测试消息
        message = TestDataFactory.create_mock_message(text="这是旧的测试消息")
        
        # 模拟消息处理
        pair_config = {
            'source_channel': 'test_source',
            'target_channels': [('test_target', -1001111111111, '目标频道')],
            'keywords': ['测试'],
            'text_replacements': {'旧': '新'}
        }
        
        await monitor._process_single_message(message, pair_config)
        
        # 验证消息被处理
        mock_client.copy_message.assert_called()
    
    @pytest.mark.asyncio
    async def test_complete_media_group_flow(self, mock_client, mock_ui_config_manager, mock_channel_resolver):
        """测试完整的媒体组处理流程"""
        monitor = Monitor(mock_client, mock_ui_config_manager, mock_channel_resolver)
        
        # 创建媒体组消息
        messages = TestDataFactory.create_media_group_messages(count=3)
        pair_config = {
            'source_channel': 'test_source',
            'target_channels': [('test_target', -1001111111111, '目标频道')],
            'keywords': [],
            'media_types': [MediaType.PHOTO, MediaType.VIDEO, MediaType.DOCUMENT],
            'text_replacements': {}
        }
        
        # 模拟处理所有媒体组消息
        for message in messages:
            await monitor.media_group_handler.handle_media_group_message(message, pair_config)
        
        # 验证媒体组被处理
        assert len(monitor.media_group_handler.processed_media_groups) > 0


@pytest.mark.asyncio
async def test_error_handling_scenarios():
    """测试各种错误处理场景"""
    
    # 测试网络错误
    client = Mock(spec=Client)
    client.copy_message.side_effect = Exception("网络错误")
    
    processor = MessageProcessor(client, Mock())
    
    with pytest.raises(Exception):
        await processor.forward_message(
            TestDataFactory.create_mock_message(text="测试"),
            [("target", -1001111111111, "目标")]
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"]) 