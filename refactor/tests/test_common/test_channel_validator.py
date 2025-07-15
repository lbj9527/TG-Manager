"""
频道验证器测试

测试频道验证器的核心功能。
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

from common.channel_validator import ChannelValidator


# 自定义异常类，用于测试
class ChatNotFound(Exception):
    """模拟ChatNotFound异常"""
    pass


class TestChannelValidator:
    """频道验证器测试"""
    
    @pytest.fixture
    def mock_client(self):
        """模拟客户端"""
        client = Mock()
        client.get_chat = AsyncMock()
        client.get_chat_member = AsyncMock()
        return client
    
    @pytest.fixture
    def channel_validator(self, mock_client):
        """频道验证器实例"""
        return ChannelValidator(mock_client)
    
    @pytest.fixture
    def mock_chat(self):
        """模拟聊天对象"""
        chat = Mock()
        chat.id = -1001234567890
        chat.title = "Test Channel"
        chat.username = "testchannel"
        chat.type = Mock()
        chat.type.value = "channel"
        chat.first_name = None
        chat.last_name = None
        chat.members_count = 1000
        chat.description = "Test channel description"
        chat.is_verified = False
        chat.is_restricted = False
        chat.is_scam = False
        chat.is_fake = False
        return chat
    
    @pytest.fixture
    def mock_user(self):
        """模拟用户对象"""
        user = Mock()
        user.id = 123456789
        user.first_name = "Test User"
        user.username = "testuser"
        return user
    
    @pytest.fixture
    def mock_chat_member(self):
        """模拟聊天成员对象"""
        member = Mock()
        member.status = Mock()
        member.status.value = "member"
        member.privileges = Mock()
        member.privileges.can_post_messages = True
        member.privileges.can_edit_messages = True
        member.privileges.can_delete_messages = False
        member.privileges.can_restrict_members = False
        member.privileges.can_promote_members = False
        member.privileges.can_change_info = False
        member.privileges.can_invite_users = False
        member.privileges.can_pin_messages = False
        member.privileges.can_manage_chat = False
        member.privileges.can_manage_video_chats = False
        member.privileges.can_post_stories = False
        member.privileges.can_edit_stories = False
        member.privileges.can_delete_stories = False
        member.can_send_messages = True
        member.can_send_media_messages = True
        member.can_send_other_messages = True
        member.can_add_web_page_previews = True
        return member
    
    @pytest.mark.asyncio
    async def test_validate_channel_success(self, channel_validator, mock_client, mock_chat):
        """测试成功验证频道"""
        mock_client.get_chat.return_value = mock_chat
        
        result = await channel_validator.validate_channel("@testchannel")
        
        assert result is True
        mock_client.get_chat.assert_called_once_with("@testchannel")
    
    @pytest.mark.asyncio
    async def test_validate_channel_not_found(self, channel_validator, mock_client):
        """测试验证不存在的频道"""
        mock_client.get_chat.side_effect = ChatNotFound()
        
        result = await channel_validator.validate_channel("@nonexistent")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_channel_private(self, channel_validator, mock_client):
        """测试验证私有频道"""
        from pyrogram.errors import ChannelPrivate
        mock_client.get_chat.side_effect = ChannelPrivate()
        
        result = await channel_validator.validate_channel("@privatechannel")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_channel_other_error(self, channel_validator, mock_client):
        """测试验证频道时其他错误"""
        mock_client.get_chat.side_effect = Exception("Network error")
        
        result = await channel_validator.validate_channel("@errorchannel")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_get_channel_info_success(self, channel_validator, mock_client, mock_chat):
        """测试成功获取频道信息"""
        mock_client.get_chat.return_value = mock_chat
        
        info = await channel_validator.get_channel_info("@testchannel")
        
        assert info is not None
        assert info['id'] == mock_chat.id
        assert info['title'] == mock_chat.title
        assert info['username'] == mock_chat.username
        assert info['type'] == mock_chat.type.value
    
    @pytest.mark.asyncio
    async def test_get_channel_info_not_found(self, channel_validator, mock_client):
        """测试获取不存在频道的信息"""
        mock_client.get_chat.side_effect = ChatNotFound()
        
        info = await channel_validator.get_channel_info("@nonexistent")
        
        assert info is None
    
    @pytest.mark.asyncio
    async def test_get_channel_info_private(self, channel_validator, mock_client):
        """测试获取私有频道信息"""
        from pyrogram.errors import ChannelPrivate
        mock_client.get_chat.side_effect = ChannelPrivate()
        
        info = await channel_validator.get_channel_info("@privatechannel")
        
        assert info is None
    
    @pytest.mark.asyncio
    async def test_check_permissions_success(self, channel_validator, mock_client, mock_chat_member, mock_user):
        """测试成功检查权限"""
        mock_client.get_me.return_value = mock_user
        mock_client.get_chat_member.return_value = mock_chat_member
        
        permissions = await channel_validator.check_permissions("@testchannel")
        
        assert permissions is not None
        assert permissions['permissions']['can_post_messages'] is True
        assert permissions['permissions']['can_edit_messages'] is True
        assert permissions['permissions']['can_delete_messages'] is False
    
    @pytest.mark.asyncio
    async def test_check_permissions_not_member(self, channel_validator, mock_client):
        """测试检查非成员权限"""
        from pyrogram.errors import UserNotParticipant
        mock_client.get_chat_member.side_effect = UserNotParticipant()
        
        permissions = await channel_validator.check_permissions("@testchannel")
        
        assert permissions is not None
        assert permissions['can_access'] is False
    
    @pytest.mark.asyncio
    async def test_check_permissions_private(self, channel_validator, mock_client):
        """测试检查私有频道权限"""
        from pyrogram.errors import ChannelPrivate
        mock_client.get_chat_member.side_effect = ChannelPrivate()
        
        permissions = await channel_validator.check_permissions("@privatechannel")
        
        assert permissions is not None
        assert permissions['can_access'] is False
    
    @pytest.mark.asyncio
    async def test_check_forward_permission_success(self, channel_validator, mock_client, mock_chat_member, mock_user):
        """测试成功检查转发权限"""
        mock_chat_member.privileges.can_post_messages = True
        mock_client.get_me.return_value = mock_user
        mock_client.get_chat_member.return_value = mock_chat_member
        
        can_forward = await channel_validator.check_forward_permission("@testchannel")
        
        assert can_forward is True
    
    @pytest.mark.asyncio
    async def test_check_forward_permission_no_post(self, channel_validator, mock_client, mock_chat_member):
        """测试检查无发布权限的频道"""
        mock_chat_member.privileges.can_post_messages = False
        mock_client.get_chat_member.return_value = mock_chat_member
        
        can_forward = await channel_validator.check_forward_permission("@testchannel")
        
        assert can_forward is False
    
    @pytest.mark.asyncio
    async def test_check_forward_permission_not_member(self, channel_validator, mock_client):
        """测试检查非成员转发权限"""
        from pyrogram.errors import UserNotParticipant
        mock_client.get_chat_member.side_effect = UserNotParticipant()
        
        can_forward = await channel_validator.check_forward_permission("@testchannel")
        
        assert can_forward is False
    
    @pytest.mark.asyncio
    async def test_resolve_channel_id_username(self, channel_validator, mock_client, mock_chat):
        """测试解析用户名频道ID"""
        mock_client.get_chat.return_value = mock_chat
        
        channel_id = await channel_validator.resolve_channel_id("@testchannel")
        
        assert channel_id == mock_chat.id
    
    @pytest.mark.asyncio
    async def test_resolve_channel_id_numeric(self, channel_validator, mock_client, mock_chat):
        """测试解析数字频道ID"""
        mock_client.get_chat.return_value = mock_chat
        
        channel_id = await channel_validator.resolve_channel_id("-1001234567890")
        
        assert channel_id == mock_chat.id
    
    @pytest.mark.asyncio
    async def test_resolve_channel_id_invalid(self, channel_validator, mock_client):
        """测试解析无效频道ID"""
        mock_client.get_chat.side_effect = ChatNotFound()
        
        channel_id = await channel_validator.resolve_channel_id("@invalid")
        
        assert channel_id is None
    
    @pytest.mark.asyncio
    async def test_get_channel_members_count_success(self, channel_validator, mock_client, mock_chat):
        """测试成功获取频道成员数"""
        mock_chat.members_count = 1000
        mock_client.get_chat.return_value = mock_chat
        
        count = await channel_validator.get_channel_members_count("@testchannel")
        
        assert count == 1000
        mock_client.get_chat.assert_called_once_with("@testchannel")
    
    @pytest.mark.asyncio
    async def test_get_channel_members_count_error(self, channel_validator, mock_client):
        """测试获取频道成员数错误"""
        mock_client.get_chat.side_effect = ChatNotFound()
        
        count = await channel_validator.get_channel_members_count("@testchannel")
        
        assert count is None
    
    @pytest.mark.asyncio
    async def test_is_channel_public_success(self, channel_validator, mock_client, mock_chat):
        """测试成功检查频道是否公开"""
        mock_chat.username = "publicchannel"
        mock_client.get_chat.return_value = mock_chat
        
        is_public = await channel_validator.is_channel_public("@publicchannel")
        
        assert is_public is True
    
    @pytest.mark.asyncio
    async def test_is_channel_public_private(self, channel_validator, mock_client, mock_chat):
        """测试检查私有频道"""
        mock_chat.username = None
        mock_client.get_chat.return_value = mock_chat
        
        is_public = await channel_validator.is_channel_public("@privatechannel")
        
        assert is_public is False
    
    @pytest.mark.asyncio
    async def test_is_channel_public_error(self, channel_validator, mock_client):
        """测试检查频道公开性时错误"""
        mock_client.get_chat.side_effect = ChatNotFound()
        
        is_public = await channel_validator.is_channel_public("@testchannel")
        
        assert is_public is None
    
    @pytest.mark.asyncio
    async def test_validate_multiple_channels(self, channel_validator, mock_client, mock_chat):
        """测试验证多个频道"""
        mock_client.get_chat.return_value = mock_chat
        
        channels = ["@channel1", "@channel2", "@channel3"]
        results = await channel_validator.validate_multiple_channels(channels)
        
        assert len(results) == 3
        assert all(results.values()), "所有频道都应该验证成功"
    
    @pytest.mark.asyncio
    async def test_validate_multiple_channels_partial_failure(self, channel_validator, mock_client, mock_chat):
        """测试验证多个频道部分失败"""
        def get_chat_side_effect(chat_id):
            if chat_id == "@invalid":
                raise ChatNotFound()
            return mock_chat
        
        mock_client.get_chat.side_effect = get_chat_side_effect
        
        channels = ["@valid1", "@invalid", "@valid2"]
        results = await channel_validator.validate_multiple_channels(channels)
        
        assert len(results) == 3
        assert results["@valid1"] is True
        assert results["@invalid"] is False
        assert results["@valid2"] is True
    
    @pytest.mark.asyncio
    async def test_get_channels_info_batch(self, channel_validator, mock_client, mock_chat):
        """测试批量获取频道信息"""
        mock_client.get_chat.return_value = mock_chat
        
        channels = ["@channel1", "@channel2"]
        infos = await channel_validator.get_channels_info_batch(channels)
        
        assert len(infos) == 2
        for info in infos.values():
            assert info is not None
            assert info['id'] == mock_chat.id
            assert info['title'] == mock_chat.title
    
    @pytest.mark.asyncio
    async def test_cache_functionality(self, channel_validator, mock_client, mock_chat):
        """测试缓存功能"""
        mock_client.get_chat.return_value = mock_chat
        
        # 第一次调用
        info1 = await channel_validator.get_channel_info("@testchannel")
        
        # 第二次调用（应该使用缓存）
        info2 = await channel_validator.get_channel_info("@testchannel")
        
        # 验证结果一致
        assert info1 == info2
        
        # 验证只调用了一次API
        assert mock_client.get_chat.call_count == 1
    
    @pytest.mark.asyncio
    async def test_cache_expiration(self, channel_validator, mock_client, mock_chat):
        """测试缓存过期"""
        mock_client.get_chat.return_value = mock_chat
        
        # 第一次调用
        await channel_validator.get_channel_info("@testchannel")
        
        # 手动设置缓存为过期状态
        cache_key = "@testchannel"
        channel_validator.channel_cache[cache_key]['timestamp'] = 0  # 设置为很久以前的时间
        
        # 第二次调用（应该重新调用API）
        await channel_validator.get_channel_info("@testchannel")
        
        # 验证调用了两次API
        assert mock_client.get_chat.call_count == 2
    
    def test_set_cache_ttl(self, channel_validator):
        """测试设置缓存TTL"""
        channel_validator.set_cache_ttl(300)  # 5分钟
        assert channel_validator.cache_ttl == 300
    
    def test_clear_cache(self, channel_validator):
        """测试清除缓存"""
        # 添加一些缓存数据
        channel_validator.channel_cache["@testchannel"] = {
            'valid': True,
            'chat_info': {'id': 123},
            'timestamp': 1000
        }
        
        # 清除缓存
        channel_validator.clear_cache()
        
        # 验证缓存已清空
        assert len(channel_validator.channel_cache) == 0
        assert len(channel_validator.permission_cache) == 0
    
    def test_get_cache_stats(self, channel_validator):
        """测试获取缓存统计"""
        # 添加一些缓存数据
        channel_validator.channel_cache["@test1"] = {'valid': True, 'chat_info': {}, 'timestamp': 1000}
        channel_validator.channel_cache["@test2"] = {'valid': True, 'chat_info': {}, 'timestamp': 1000}
        
        stats = channel_validator.get_cache_stats()
        
        assert stats['channel_cache_count'] == 2
        assert stats['enabled'] == channel_validator.cache_enabled 