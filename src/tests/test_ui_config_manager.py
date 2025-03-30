"""
UI配置管理器测试模块，测试UI配置模型和UI配置管理器功能
"""

import os
import json
import tempfile
import pytest
from pathlib import Path

from src.utils.ui_config_models import (
    UIConfig, UIGeneralConfig, UIDownloadConfig, UIUploadConfig, 
    UIForwardConfig, UIMonitorConfig, UIChannelPair, UIMonitorChannelPair,
    UIDownloadSettingItem, UITextFilterItem, MediaType, ProxyType,
    create_default_config
)
from src.utils.ui_config_manager import UIConfigManager, create_ui_config_manager
from src.utils.config_manager import ConfigManager


@pytest.fixture
def temp_config_file():
    """创建临时配置文件"""
    # 创建示例配置
    config_data = {
        "GENERAL": {
            "api_id": 12345,
            "api_hash": "abcd1234efgh5678ijkl9012mnop3456",
            "limit": 50,
            "pause_time": 60,
            "timeout": 30,
            "max_retries": 3,
            "proxy_enabled": False,
            "proxy_type": "SOCKS5",
            "proxy_addr": "127.0.0.1",
            "proxy_port": 1080
        },
        "DOWNLOAD": {
            "downloadSetting": [
                {
                    "source_channels": "https://t.me/channel1",
                    "start_id": 1000,
                    "end_id": 2000,
                    "media_types": ["photo", "video", "document"],
                    "keywords": ["测试", "示例"]
                }
            ],
            "download_path": "test_downloads",
            "parallel_download": True,
            "max_concurrent_downloads": 5
        },
        "UPLOAD": {
            "target_channels": ["@target1", "@target2"],
            "directory": "test_uploads",
            "caption_template": "{filename} - {date}",
            "delay_between_uploads": 1.0
        },
        "FORWARD": {
            "forward_channel_pairs": [
                {
                    "source_channel": "@source1",
                    "target_channels": ["@target1", "@target2"]
                }
            ],
            "remove_captions": True,
            "hide_author": True,
            "media_types": ["photo", "video", "document", "audio", "animation"],
            "forward_delay": 0.5,
            "start_id": 1000,
            "end_id": 2000,
            "tmp_path": "test_tmp"
        },
        "MONITOR": {
            "monitor_channel_pairs": [
                {
                    "source_channel": "@source1",
                    "target_channels": ["@target1", "@target2"],
                    "remove_captions": True,
                    "text_filter": [
                        {
                            "original_text": "测试",
                            "target_text": "示例"
                        }
                    ]
                }
            ],
            "media_types": ["photo", "video", "document", "audio", "animation", "sticker"],
            "duration": "2099-12-31",
            "forward_delay": 1.0
        }
    }
    
    # 创建临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode='w', encoding='utf-8') as f:
        json.dump(config_data, f, ensure_ascii=False, indent=2)
        temp_path = f.name
    
    yield temp_path
    
    # 清理临时文件
    try:
        os.unlink(temp_path)
    except:
        pass


def test_create_default_config():
    """测试创建默认配置"""
    config = create_default_config()
    
    # 验证基本结构
    assert isinstance(config, UIConfig)
    assert isinstance(config.GENERAL, UIGeneralConfig)
    assert isinstance(config.DOWNLOAD, UIDownloadConfig)
    assert isinstance(config.UPLOAD, UIUploadConfig)
    assert isinstance(config.FORWARD, UIForwardConfig)
    assert isinstance(config.MONITOR, UIMonitorConfig)
    
    # 验证默认值
    assert config.GENERAL.api_id == 0
    assert config.GENERAL.api_hash == ""
    assert config.GENERAL.limit == 50
    assert config.DOWNLOAD.download_path == "downloads"
    assert config.UPLOAD.caption_template == "{filename}"
    assert config.FORWARD.hide_author is False
    assert config.MONITOR.duration is None


def test_ui_config_manager_load(temp_config_file):
    """测试UI配置管理器加载配置"""
    # 创建UI配置管理器
    ui_config_manager = UIConfigManager(temp_config_file)
    
    # 验证加载的配置
    config = ui_config_manager.get_ui_config()
    
    assert config.GENERAL.api_id == 12345
    assert config.GENERAL.api_hash == "abcd1234efgh5678ijkl9012mnop3456"
    assert config.GENERAL.proxy_type == ProxyType.SOCKS5
    
    assert len(config.DOWNLOAD.downloadSetting) == 1
    assert config.DOWNLOAD.downloadSetting[0].source_channels == "https://t.me/channel1"
    assert config.DOWNLOAD.downloadSetting[0].media_types[0] == MediaType.PHOTO
    assert "测试" in config.DOWNLOAD.downloadSetting[0].keywords
    
    assert len(config.UPLOAD.target_channels) == 2
    assert "@target1" in config.UPLOAD.target_channels
    assert config.UPLOAD.caption_template == "{filename} - {date}"
    
    assert len(config.FORWARD.forward_channel_pairs) == 1
    assert config.FORWARD.forward_channel_pairs[0].source_channel == "@source1"
    assert config.FORWARD.remove_captions is True
    assert config.FORWARD.hide_author is True
    
    assert len(config.MONITOR.monitor_channel_pairs) == 1
    assert len(config.MONITOR.monitor_channel_pairs[0].text_filter) == 1
    assert config.MONITOR.monitor_channel_pairs[0].text_filter[0].original_text == "测试"
    assert config.MONITOR.duration == "2099-12-31"


def test_ui_config_manager_save(tmpdir):
    """测试UI配置管理器保存配置"""
    # 创建临时配置文件路径
    temp_path = str(tmpdir.join("test_config.json"))
    
    # 创建UI配置管理器
    ui_config_manager = UIConfigManager(temp_path)
    
    # 修改配置
    config = ui_config_manager.get_ui_config()
    config.GENERAL.api_id = 67890
    config.GENERAL.api_hash = "abcdef1234567890"
    config.DOWNLOAD.download_path = "custom_downloads"
    
    # 保存配置
    result = ui_config_manager.save_config()
    assert result is True
    
    # 验证文件是否已创建
    assert os.path.exists(temp_path)
    
    # 读取保存的配置
    with open(temp_path, 'r', encoding='utf-8') as f:
        saved_config = json.load(f)
    
    # 验证保存的配置
    assert saved_config["GENERAL"]["api_id"] == 67890
    assert saved_config["GENERAL"]["api_hash"] == "abcdef1234567890"
    assert saved_config["DOWNLOAD"]["download_path"] == "custom_downloads"


def test_ui_config_validation():
    """测试UI配置验证"""
    # 创建无效配置
    invalid_config = create_default_config()
    invalid_config.GENERAL.api_id = -1  # 无效的API ID
    
    # 创建UI配置管理器
    ui_config_manager = UIConfigManager()
    ui_config_manager.set_ui_config(invalid_config)
    
    # 验证配置
    errors = ui_config_manager.validate_config()
    assert len(errors) > 0
    assert any("API ID" in error for error in errors)


def test_ui_config_update_from_dict():
    """测试从字典更新UI配置"""
    # 创建UI配置管理器
    ui_config_manager = UIConfigManager()
    
    # 准备更新字典
    update_dict = {
        "GENERAL": {
            "api_id": 54321,
            "api_hash": "updated_hash_12345",
            "limit": 100,
            "proxy_enabled": True,
            "proxy_type": "HTTP",
            "proxy_addr": "localhost",
            "proxy_port": 8080,
            "pause_time": 30,
            "timeout": 60,
            "max_retries": 5,
            "proxy_username": "user",
            "proxy_password": "pass"
        },
        "DOWNLOAD": {
            "downloadSetting": [
                {
                    "source_channels": "@updated_channel",
                    "start_id": 5000,
                    "end_id": 6000,
                    "media_types": ["photo", "video"],
                    "keywords": ["更新", "测试"]
                }
            ],
            "download_path": "updated_downloads",
            "parallel_download": True,
            "max_concurrent_downloads": 8
        },
        "UPLOAD": {
            "target_channels": ["@updated_target"],
            "directory": "updated_uploads",
            "caption_template": "Updated: {filename}",
            "delay_between_uploads": 2.0
        },
        "FORWARD": {
            "forward_channel_pairs": [
                {
                    "source_channel": "@updated_source",
                    "target_channels": ["@updated_target1", "@updated_target2"]
                }
            ],
            "remove_captions": False,
            "hide_author": True,
            "media_types": ["photo", "video"],
            "forward_delay": 1.5,
            "start_id": 5000,
            "end_id": 6000,
            "tmp_path": "updated_tmp"
        },
        "MONITOR": {
            "monitor_channel_pairs": [
                {
                    "source_channel": "@updated_source",
                    "target_channels": ["@updated_target1", "@updated_target2"],
                    "remove_captions": False,
                    "text_filter": [
                        {
                            "original_text": "更新",
                            "target_text": "已更新"
                        }
                    ]
                }
            ],
            "media_types": ["photo", "video"],
            "duration": "2099-10-10",
            "forward_delay": 2.0
        }
    }
    
    # 更新配置
    result = ui_config_manager.update_from_dict(update_dict)
    assert result is True
    
    # 验证更新后的配置
    config = ui_config_manager.get_ui_config()
    assert config.GENERAL.api_id == 54321
    assert config.GENERAL.api_hash == "updated_hash_12345"
    assert config.GENERAL.proxy_type == ProxyType.HTTP
    
    assert config.DOWNLOAD.downloadSetting[0].source_channels == "@updated_channel"
    assert "更新" in config.DOWNLOAD.downloadSetting[0].keywords
    
    assert config.UPLOAD.target_channels[0] == "@updated_target"
    assert config.UPLOAD.caption_template == "Updated: {filename}"
    
    assert config.FORWARD.forward_channel_pairs[0].source_channel == "@updated_source"
    assert config.FORWARD.forward_delay == 1.5
    
    assert config.MONITOR.monitor_channel_pairs[0].text_filter[0].original_text == "更新"
    assert config.MONITOR.duration == "2099-10-10"


def test_enums_conversion():
    """测试枚举值转换"""
    # 创建UI配置管理器
    ui_config_manager = UIConfigManager()
    
    # 获取配置并修改枚举值
    config = ui_config_manager.get_ui_config()
    config.GENERAL.proxy_type = ProxyType.HTTP
    config.DOWNLOAD.downloadSetting[0].media_types = [MediaType.PHOTO, MediaType.VIDEO]
    config.FORWARD.media_types = [MediaType.DOCUMENT, MediaType.AUDIO]
    config.MONITOR.media_types = [MediaType.STICKER, MediaType.VOICE]
    
    # 将配置转换为字典
    config_dict = config.dict()
    
    # 转换枚举值为字符串
    ui_config_manager._convert_enums_to_str(config_dict)
    
    # 验证转换结果
    assert config_dict["GENERAL"]["proxy_type"] == "HTTP"
    assert config_dict["DOWNLOAD"]["downloadSetting"][0]["media_types"] == ["photo", "video"]
    assert config_dict["FORWARD"]["media_types"] == ["document", "audio"]
    assert config_dict["MONITOR"]["media_types"] == ["sticker", "voice"]


def test_create_ui_config_manager_factory():
    """测试UI配置管理器工厂函数"""
    # 使用工厂函数创建UI配置管理器
    ui_config_manager = create_ui_config_manager("custom_path.json")
    
    # 验证创建的实例
    assert isinstance(ui_config_manager, UIConfigManager)
    assert ui_config_manager.config_path == "custom_path.json"


def test_channel_id_validation():
    """测试频道ID验证"""
    # 测试有效的频道ID
    valid_ids = [
        "https://t.me/channel1",
        "https://t.me/joinchat/abcdef123456",
        "@channel1",
        "-1001234567890",
        "+abcdef123456"
    ]
    
    for channel_id in valid_ids:
        result = UIChannelPair.validate_channel_id(channel_id, "测试")
        assert result == channel_id
    
    # 测试无效的频道ID
    invalid_ids = [
        "",  # 空字符串
        "invalid_channel",  # 没有@前缀的用户名
        "http://telegram.org/channel1",  # 非t.me链接
        "https://t.me/a",  # 用户名太短
        "@a",  # 用户名太短
        "@123user"  # 用户名不能以数字开头
    ]
    
    for channel_id in invalid_ids:
        with pytest.raises(ValueError):
            UIChannelPair.validate_channel_id(channel_id, "测试")


def test_date_validation():
    """测试日期验证"""
    # 创建config对象
    config = create_default_config()
    
    # 测试有效的日期
    valid_date = "2099-12-31"
    config.MONITOR.duration = valid_date
    
    # 验证结果
    try:
        config_dict = config.dict()
        assert config_dict["MONITOR"]["duration"] == valid_date
    except Exception as e:
        pytest.fail(f"有效日期验证失败: {e}")
    
    # 测试无效日期格式
    invalid_formats = [
        "20991231",  # 没有分隔符
        "2099/12/31",  # 错误的分隔符
        "31-12-2099",  # 错误的顺序
        "2099-13-31",  # 无效的月份
        "2099-12-32"   # 无效的日期
    ]
    
    for invalid_date in invalid_formats:
        config.MONITOR.duration = invalid_date
        with pytest.raises(ValueError):
            config.dict(exclude_unset=True)


def test_config_manager_integration(temp_config_file):
    """测试UI配置管理器与原始ConfigManager的集成"""
    # 创建UI配置管理器
    ui_config_manager = UIConfigManager(temp_config_file)
    
    # 创建原始ConfigManager
    config_manager = ui_config_manager.create_config_manager()
    
    # 验证创建的ConfigManager
    assert isinstance(config_manager, ConfigManager)
    
    # 验证ConfigManager加载的配置
    general_config = config_manager.get_general_config()
    assert general_config.api_id == 12345
    assert general_config.api_hash == "abcd1234efgh5678ijkl9012mnop3456"
    
    download_config = config_manager.get_download_config()
    assert download_config.download_path == "test_downloads"
    
    # 测试从ConfigManager更新UI配置
    updated = ui_config_manager.update_from_config_manager(config_manager)
    assert updated is True 