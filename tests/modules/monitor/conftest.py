"""
监听模块测试配置
提供共享的测试夹具、配置和工具函数
"""

import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any, List

from pyrogram import Client
from pyrogram.types import Message, Chat, User

# 测试配置常量
TEST_SOURCE_CHANNEL_ID = -1001234567890
TEST_TARGET_CHANNEL_ID = -1001111111111
TEST_SOURCE_USERNAME = "test_source"
TEST_TARGET_USERNAME = "test_target"


@pytest.fixture(scope="session")
def event_loop():
    """提供事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir():
    """创建临时目录"""
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def mock_telegram_files():
    """模拟Telegram文件数据"""
    return {
        'photo': {
            'file_id': 'BAADBAADPhoto-FileID',
            'file_unique_id': 'photo_unique_id',
            'width': 1280,
            'height': 720,
            'file_size': 512000
        },
        'video': {
            'file_id': 'BAADBAADVideo-FileID',
            'file_unique_id': 'video_unique_id',
            'width': 1920,
            'height': 1080,
            'duration': 120,
            'file_size': 5120000
        },
        'document': {
            'file_id': 'BAADBAADDocument-FileID',
            'file_unique_id': 'document_unique_id',
            'file_name': 'test_document.pdf',
            'mime_type': 'application/pdf',
            'file_size': 1024000
        },
        'audio': {
            'file_id': 'BAADBAADAudio-FileID',
            'file_unique_id': 'audio_unique_id',
            'duration': 180,
            'title': 'Test Audio',
            'performer': 'Test Artist',
            'file_size': 3072000
        },
        'voice': {
            'file_id': 'BAADBAADVoice-FileID',
            'file_unique_id': 'voice_unique_id',
            'duration': 30,
            'file_size': 256000
        },
        'sticker': {
            'file_id': 'BAADBAADSticker-FileID',
            'file_unique_id': 'sticker_unique_id',
            'width': 512,
            'height': 512,
            'file_size': 128000
        }
    }


@pytest.fixture
def sample_test_messages():
    """提供各种类型的测试消息数据"""
    return {
        'text_messages': [
            "简单的文本消息",
            "包含关键词的测试消息",
            "这是一条包含链接的消息 https://example.com",
            "这是包含@用户名的消息 @username",
            "包含#标签的消息 #测试",
            "包含emoji的消息 🎉🚀💯",
            "多行消息\n第二行内容\n第三行内容",
            "包含特殊字符的消息 !@#$%^&*()",
        ],
        'captions': [
            "图片描述文本",
            "包含旧文本需要替换的描述",
            "视频说明：这是一个测试视频",
            "文档描述：重要文件",
            None,  # 无描述
            "",    # 空描述
        ],
        'keywords': [
            ["测试", "关键词"],
            ["重要", "urgent", "紧急"],
            ["通知", "announcement"],
            ["更新", "update", "升级"],
            [],  # 无关键词限制
        ],
        'text_replacements': [
            {"旧文本": "新文本", "old": "new"},
            {"测试": "正式", "beta": "release"},
            {"临时": "正式", "temp": "final"},
            {},  # 无替换规则
        ]
    }


@pytest.fixture
def test_scenarios_config():
    """提供各种测试场景的配置"""
    return {
        # 基础转发场景
        'basic_forward': {
            'source_channel': TEST_SOURCE_USERNAME,
            'target_channels': [TEST_TARGET_USERNAME],
            'keywords': [],
            'exclude_forwards': False,
            'exclude_replies': False,
            'exclude_text': False,
            'exclude_links': False,
            'remove_captions': False,
            'media_types': ['photo', 'video', 'document', 'audio', 'animation', 'sticker', 'voice', 'video_note'],
            'text_filter': []
        },
        
        # 关键词过滤场景
        'keyword_filter': {
            'source_channel': TEST_SOURCE_USERNAME,
            'target_channels': [TEST_TARGET_USERNAME],
            'keywords': ['重要', '紧急', 'urgent'],
            'exclude_forwards': False,
            'exclude_replies': False,
            'exclude_text': False,
            'exclude_links': False,
            'remove_captions': False,
            'media_types': ['photo', 'video', 'document'],
            'text_filter': []
        },
        
        # 严格过滤场景
        'strict_filter': {
            'source_channel': TEST_SOURCE_USERNAME,
            'target_channels': [TEST_TARGET_USERNAME],
            'keywords': [],
            'exclude_forwards': True,
            'exclude_replies': True,
            'exclude_text': True,
            'exclude_links': True,
            'remove_captions': False,
            'media_types': ['photo', 'video'],
            'text_filter': []
        },
        
        # 文本替换场景
        'text_replacement': {
            'source_channel': TEST_SOURCE_USERNAME,
            'target_channels': [TEST_TARGET_USERNAME],
            'keywords': [],
            'exclude_forwards': False,
            'exclude_replies': False,
            'exclude_text': False,
            'exclude_links': False,
            'remove_captions': False,
            'media_types': ['photo', 'video', 'document'],
            'text_filter': [
                {'original_text': '旧版本', 'target_text': '新版本'},
                {'original_text': 'beta', 'target_text': 'release'}
            ]
        },
        
        # 移除标题场景
        'remove_captions': {
            'source_channel': TEST_SOURCE_USERNAME,
            'target_channels': [TEST_TARGET_USERNAME],
            'keywords': [],
            'exclude_forwards': False,
            'exclude_replies': False,
            'exclude_text': False,
            'exclude_links': False,
            'remove_captions': True,
            'media_types': ['photo', 'video', 'document'],
            'text_filter': []
        },
        
        # 多目标频道场景
        'multi_target': {
            'source_channel': TEST_SOURCE_USERNAME,
            'target_channels': ['target1', 'target2', 'target3'],
            'keywords': [],
            'exclude_forwards': False,
            'exclude_replies': False,
            'exclude_text': False,
            'exclude_links': False,
            'remove_captions': False,
            'media_types': ['photo', 'video', 'document'],
            'text_filter': []
        }
    }


@pytest.fixture
def error_scenarios():
    """提供各种错误场景的配置"""
    return {
        'network_errors': [
            'ConnectionError',
            'TimeoutError',
            'NetworkUnreachable'
        ],
        'telegram_errors': [
            'FloodWait',
            'ChatForwardsRestricted', 
            'ChannelPrivate',
            'UserDeactivated',
            'ChatAdminRequired'
        ],
        'permission_errors': [
            'Forbidden',
            'Unauthorized',
            'InsufficientRights'
        ]
    }


class MockedAPIResponses:
    """模拟API响应数据"""
    
    @staticmethod
    def get_chat_success():
        """成功获取聊天信息的响应"""
        return {
            'id': TEST_SOURCE_CHANNEL_ID,
            'type': 'channel',
            'title': '测试源频道',
            'username': TEST_SOURCE_USERNAME,
            'description': '这是一个测试频道',
            'member_count': 1000
        }
    
    @staticmethod
    def copy_message_success():
        """成功复制消息的响应"""
        return Mock(id=2001)
    
    @staticmethod
    def send_media_group_success(count=3):
        """成功发送媒体组的响应"""
        return [Mock(id=2001 + i) for i in range(count)]
    
    @staticmethod
    def get_media_group_success(count=3, media_group_id="test_group"):
        """成功获取媒体组的响应"""
        from tests.modules.monitor.test_monitor_comprehensive import TestDataFactory
        return TestDataFactory.create_media_group_messages(
            count=count, 
            media_group_id=media_group_id
        )


def create_test_environment_config():
    """创建测试环境配置"""
    return {
        'API_ID': 12345,
        'API_HASH': 'test_api_hash',
        'BOT_TOKEN': 'test_bot_token',
        'SESSION_STRING': 'test_session_string',
        'TEST_MODE': True,
        'LOG_LEVEL': 'DEBUG',
        'MAX_RETRIES': 3,
        'TIMEOUT': 30,
        'TEMP_DIR': '/tmp/tg_manager_test'
    }


@pytest.fixture
def performance_benchmarks():
    """性能基准配置"""
    return {
        'message_processing_time': 0.1,  # 单条消息处理时间上限（秒）
        'media_group_processing_time': 0.5,  # 媒体组处理时间上限（秒）
        'api_call_timeout': 30,  # API调用超时时间（秒）
        'memory_usage_limit': 100 * 1024 * 1024,  # 内存使用上限（100MB）
        'max_concurrent_operations': 10,  # 最大并发操作数
    }


# 测试工具函数
def assert_message_filtered(mock_emit, message_id: int, reason: str):
    """断言消息被正确过滤"""
    mock_emit.assert_called_with("message_filtered", message_id, mock.ANY, reason)


def assert_message_forwarded(mock_emit, message_id: int, source: str, target: str, success: bool):
    """断言消息被正确转发"""
    mock_emit.assert_called_with("forward", message_id, source, target, success)


def create_realistic_test_data():
    """创建真实场景的测试数据"""
    return {
        'channels': {
            'news_channel': {
                'id': -1001111111111,
                'username': 'news_updates',
                'title': '新闻更新频道',
                'message_types': ['text', 'photo', 'video', 'document']
            },
            'tech_channel': {
                'id': -1002222222222,
                'username': 'tech_news',
                'title': '科技新闻',
                'message_types': ['text', 'photo', 'document', 'animation']
            },
            'media_channel': {
                'id': -1003333333333,
                'username': 'media_share',
                'title': '媒体分享',
                'message_types': ['photo', 'video', 'audio', 'document']
            }
        },
        'realistic_messages': [
            {
                'type': 'text',
                'content': '🚀 重要更新：我们的新功能已经发布！',
                'has_entities': True,
                'entities': ['emoji']
            },
            {
                'type': 'photo',
                'caption': '查看这张精美的图片 📸',
                'has_media': True,
                'media_type': 'photo'
            },
            {
                'type': 'media_group',
                'count': 4,
                'caption': '活动现场照片集锦',
                'media_types': ['photo', 'photo', 'video', 'photo']
            },
            {
                'type': 'forward',
                'original_source': '@original_channel',
                'content': '转发：这是一条重要通知'
            }
        ]
    } 