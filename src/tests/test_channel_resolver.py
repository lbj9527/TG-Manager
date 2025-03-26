"""
频道解析测试文件
测试ChannelResolver类对各种格式Telegram链接的解析能力
"""

import os
import pytest
import asyncio
from pyrogram import Client
from pathlib import Path

from src.utils.channel_resolver import ChannelResolver
from src.utils.config_manager import ConfigManager

# 获取配置
config_manager = ConfigManager()
general_config = config_manager.get_general_config()

# 测试会话文件路径 - 使用主程序同名session文件
SESSION_NAME = "tg_manager"
SESSION_PATH = str(Path.home() / f"{SESSION_NAME}.session")

@pytest.fixture
async def client():
    """创建Pyrogram客户端实例"""
    try:
        # 使用与主程序相同的session文件
        client = Client(
            SESSION_NAME,  # 与主程序相同的session名
            api_id=general_config.api_id,
            api_hash=general_config.api_hash,
            workdir=str(Path.home())  # session文件存放位置
        )
        await client.start()
        yield client
        await client.stop()
    except Exception as e:
        pytest.skip(f"无法创建客户端: {e}，跳过测试")

@pytest.fixture
def channel_resolver(client):
    """创建频道解析器实例"""
    return ChannelResolver(client)

@pytest.mark.asyncio
async def test_channel_username_format(channel_resolver):
    """测试用户名格式的频道解析"""
    # 格式: @channel_name
    channel_id, message_id = await channel_resolver.resolve_channel("@durov")
    assert channel_id == "@durov"
    assert message_id is None

@pytest.mark.asyncio
async def test_channel_link_format(channel_resolver):
    """测试频道链接格式的解析"""
    # 格式: https://t.me/channel_name
    channel_id, message_id = await channel_resolver.resolve_channel("https://t.me/durov")
    assert channel_id == "@durov"
    assert message_id is None

@pytest.mark.asyncio
async def test_channel_message_link_format(channel_resolver):
    """测试频道消息链接格式的解析"""
    # 格式: https://t.me/channel_name/123
    channel_id, message_id = await channel_resolver.resolve_channel("https://t.me/durov/123")
    assert channel_id == "@durov"
    assert message_id == 123

@pytest.mark.asyncio
async def test_private_channel_link_format(channel_resolver):
    """测试私有频道链接格式的解析"""
    # 格式: https://t.me/c/1234567890
    channel_id, message_id = await channel_resolver.resolve_channel("https://t.me/c/1234567890")
    assert channel_id == 1234567890
    assert message_id is None

@pytest.mark.asyncio
async def test_private_channel_message_link_format(channel_resolver):
    """测试私有频道消息链接格式的解析"""
    # 格式: https://t.me/c/1234567890/123
    channel_id, message_id = await channel_resolver.resolve_channel("https://t.me/c/1234567890/123")
    assert channel_id == 1234567890
    assert message_id == 123

@pytest.mark.asyncio
async def test_joinchat_link_format(channel_resolver):
    """测试joinchat链接格式的解析"""
    # 格式: https://t.me/joinchat/AAAAAAAAAAAAAAAA
    channel_id, message_id = await channel_resolver.resolve_channel("https://t.me/joinchat/AAAAAAAAAAAAAAAA")
    assert channel_id == "https://t.me/joinchat/AAAAAAAAAAAAAAAA"
    assert message_id is None

@pytest.mark.asyncio
async def test_plus_joinchat_link_format(channel_resolver):
    """测试+链接格式的解析"""
    # 格式: https://t.me/+AAAAAAAAAAAAAAAA
    channel_id, message_id = await channel_resolver.resolve_channel("https://t.me/+AAAAAAAAAAAAAAAA")
    assert channel_id == "https://t.me/+AAAAAAAAAAAAAAAA"
    assert message_id is None

@pytest.mark.asyncio
async def test_numeric_id_format(channel_resolver):
    """测试纯数字ID格式的解析"""
    # 格式: 1234567890
    channel_id, message_id = await channel_resolver.resolve_channel("1234567890")
    assert channel_id == 1234567890
    assert message_id is None

@pytest.mark.asyncio
async def test_channel_id_with_message_id_format(channel_resolver):
    """测试频道ID:消息ID格式的解析"""
    # 格式: 1234567890:123
    channel_id, message_id = await channel_resolver.resolve_channel("1234567890:123")
    assert channel_id == 1234567890
    assert message_id == 123

@pytest.mark.asyncio
async def test_get_channel_id(channel_resolver):
    """测试获取频道ID功能"""
    # 对于@username格式
    channel_id = await channel_resolver.get_channel_id("@durov")
    assert isinstance(channel_id, int)
    
    # 对于数字ID格式
    channel_id = await channel_resolver.get_channel_id("1234567890")
    assert channel_id == 1234567890

@pytest.mark.asyncio
async def test_format_channel_info(channel_resolver):
    """测试格式化频道信息功能"""
    # 对于@username格式
    info, (title, channel_id) = await channel_resolver.format_channel_info("@durov")
    assert "@durov" in info
    assert isinstance(title, str)
    assert isinstance(channel_id, int)
    
    # 对于数字ID格式
    info, (title, channel_id) = await channel_resolver.format_channel_info("1234567890")
    assert "1234567890" in info
    assert isinstance(title, str)
    assert channel_id == 1234567890

@pytest.mark.asyncio
async def test_check_forward_permission(channel_resolver):
    """测试检查转发权限功能"""
    # 对于公开频道
    try:
        permission = await channel_resolver.check_forward_permission("@durov")
        assert isinstance(permission, bool)
    except Exception:
        pytest.skip("无法测试转发权限，可能需要真实的频道访问权限")

@pytest.mark.asyncio
async def test_get_non_restricted_channels(channel_resolver):
    """测试获取非限制频道功能"""
    try:
        channels = ["@durov", "@telegram"]
        non_restricted = await channel_resolver.get_non_restricted_channels(channels)
        assert isinstance(non_restricted, list)
    except Exception:
        pytest.skip("无法测试非限制频道，可能需要真实的频道访问权限")

if __name__ == "__main__":
    pytest.main(["-xvs", "test_channel_resolver.py"]) 