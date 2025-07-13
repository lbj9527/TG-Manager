"""
pytest 配置文件

提供全局配置和路径设置，确保测试能正确导入模块。
"""

import sys
import os
import asyncio
import pytest
from pathlib import Path
from unittest.mock import Mock

# 获取项目根目录
project_root = Path(__file__).parent.parent.absolute()

# 添加项目根目录到 Python 路径
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 设置包结构
os.environ['PYTHONPATH'] = str(project_root)

# pytest 配置
def pytest_configure(config):
    """pytest 配置"""
    # 添加自定义标记
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )

def pytest_collection_modifyitems(config, items):
    """修改测试项"""
    for item in items:
        # 为异步测试添加 asyncio 标记
        if asyncio.iscoroutinefunction(item.function):
            item.add_marker(pytest.mark.asyncio)

@pytest.fixture
def event_loop():
    """创建事件循环fixture。"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()

@pytest.fixture
def mock_client():
    """创建模拟的Telegram客户端。"""
    client = Mock()
    client.get_chat = Mock()
    client.get_messages = Mock()
    client.send_message = Mock()
    client.send_media_group = Mock()
    client.copy_message = Mock()
    return client

@pytest.fixture
def mock_config():
    """创建模拟的配置。"""
    return {
        'GENERAL': {
            'api_id': '12345',
            'api_hash': 'test_hash',
            'session_name': 'test_session'
        },
        'DOWNLOAD': {
            'download_path': 'downloads',
            'downloadSetting': []
        },
        'UPLOAD': {
            'directory': 'uploads',
            'target_channels': [],
            'options': {}
        },
        'FORWARD': {
            'forward_channel_pairs': []
        },
        'MONITOR': {
            'monitor_channel_pairs': []
        }
    } 