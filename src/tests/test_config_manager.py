"""
配置管理器测试文件
测试ConfigManager类对配置文件的解析能力
"""

import os
import json
import pytest
from pathlib import Path

from src.utils.config_manager import ConfigManager

# 寻找config.json文件
def find_config_file():
    """查找配置文件位置"""
    # 优先查找项目根目录下的config.json
    paths_to_check = [
        Path.cwd() / "config.json",
        Path.cwd() / "src" / "config.json",
        Path.cwd() / "../config.json",
        Path.cwd() / "../src/config.json",
        Path(os.path.expanduser("~")) / "config.json",
        Path(os.path.expanduser("~")) / "tg_manager" / "config.json"
    ]
    
    for path in paths_to_check:
        if path.exists():
            return str(path)
    
    return None

# 创建一个临时配置文件用于测试
@pytest.fixture
def temp_config_file(tmp_path):
    """创建临时配置文件"""
    config = {
        "GENERAL": {
            "api_id": 12345,
            "api_hash": "abcd1234",
            "limit": 50,
            "pause_time": 60,
            "timeout": 30,
            "max_retries": 3,
            "proxy_enabled": False,
            "proxy_type": "socks5",
            "proxy_addr": "127.0.0.1",
            "proxy_port": 1080,
            "proxy_username": "",
            "proxy_password": ""
        },
        "DOWNLOAD": {
            "source_channels": ["@channel1", "@channel2"],
            "organize_by_chat": True,
            "download_path": "downloads",
            "start_id": 0,
            "end_id": 0,
            "media_types": ["photo", "video", "document", "audio", "animation", "sticker"]
        },
        "UPLOAD": {
            "target_channels": ["@channel3", "@channel4"],
            "directory": "uploads",
            "caption_template": "{filename} - {date}"
        },
        "FORWARD": {
            "forward_channel_pairs": [
                {
                    "source_channel": "@source1",
                    "target_channels": ["@target1", "@target2"]
                },
                {
                    "source_channel": "@source2",
                    "target_channels": ["@target3"]
                }
            ],
            "remove_captions": False,
            "forward_delay": 2,
            "start_id": 0,
            "end_id": 0,
            "tmp_path": "tmp",
            "media_types": ["photo", "video", "document", "audio", "animation", "text"]
        },
        "MONITOR": {
            "monitor_channel_pairs": [
                {
                    "source_channel": "@source1",
                    "target_channels": ["@target1", "@target2"]
                }
            ],
            "remove_captions": False,
            "duration": "2023-12-31-23",
            "forward_delay": 1,
            "media_types": ["photo", "video", "document", "audio", "animation", "text"]
        }
    }
    
    config_path = tmp_path / "config.json"
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=4)
    
    return str(config_path)

def test_load_real_config():
    """测试加载真实配置文件"""
    config_path = find_config_file()
    if not config_path:
        pytest.skip("未找到真实的config.json文件，跳过测试")
    
    # 加载真实配置文件
    try:
        config_manager = ConfigManager(config_path)
        # 验证基本配置部分是否存在
        general_config = config_manager.get_general_config()
        assert hasattr(general_config, 'api_id')
        assert hasattr(general_config, 'api_hash')
        
        # 验证下载配置
        download_config = config_manager.get_download_config()
        assert hasattr(download_config, 'source_channels')
        assert hasattr(download_config, 'download_path')
        
        # 验证上传配置
        upload_config = config_manager.get_upload_config()
        assert hasattr(upload_config, 'target_channels')
        assert hasattr(upload_config, 'directory')
        
        # 验证转发配置
        forward_config = config_manager.get_forward_config()
        assert hasattr(forward_config, 'forward_channel_pairs')
        
        # 验证监听配置
        monitor_config = config_manager.get_monitor_config()
        assert hasattr(monitor_config, 'monitor_channel_pairs')
        
        print(f"成功加载并验证真实配置文件: {config_path}")
    except Exception as e:
        pytest.fail(f"加载真实配置文件失败: {e}")

def test_config_manager(temp_config_file):
    """测试配置管理器基本功能"""
    # 使用临时配置文件初始化配置管理器
    config_manager = ConfigManager(temp_config_file)
    
    # 测试通用配置
    general_config = config_manager.get_general_config()
    assert general_config.api_id == 12345
    assert general_config.api_hash == "abcd1234"
    assert general_config.limit == 50
    assert general_config.proxy_enabled is False
    
    # 测试下载配置
    download_config = config_manager.get_download_config()
    assert len(download_config.source_channels) == 2
    assert "@channel1" in download_config.source_channels
    assert download_config.organize_by_chat is True
    assert "photo" in download_config.media_types
    
    # 测试上传配置
    upload_config = config_manager.get_upload_config()
    assert len(upload_config.target_channels) == 2
    assert upload_config.caption_template == "{filename} - {date}"
    
    # 测试转发配置
    forward_config = config_manager.get_forward_config()
    assert len(forward_config.forward_channel_pairs) == 2
    assert forward_config.forward_channel_pairs[0].source_channel == "@source1"
    assert len(forward_config.forward_channel_pairs[0].target_channels) == 2
    assert not forward_config.remove_captions
    assert forward_config.forward_delay == 2
    
    # 测试监听配置
    monitor_config = config_manager.get_monitor_config()
    assert len(monitor_config.monitor_channel_pairs) == 1
    assert monitor_config.duration == "2023-12-31-23"
    assert monitor_config.forward_delay == 1

def test_config_manager_errors():
    """测试配置管理器错误处理"""
    # 测试不存在的配置文件
    with pytest.raises(Exception):
        ConfigManager("nonexistent_config.json")
    
    # 测试创建默认配置
    temp_dir = Path(os.path.expanduser("~")) / "tmp_test_config"
    temp_dir.mkdir(exist_ok=True)
    temp_config = temp_dir / "new_config.json"
    
    try:
        if temp_config.exists():
            temp_config.unlink()
        
        # 创建配置管理器，应该会创建默认配置
        config_manager = ConfigManager(str(temp_config))
        
        # 检查是否创建了配置文件
        assert temp_config.exists()
        
        # 验证默认配置
        general_config = config_manager.get_general_config()
        assert hasattr(general_config, 'api_id')
        assert hasattr(general_config, 'api_hash')
    finally:
        # 清理
        if temp_config.exists():
            temp_config.unlink()
        if temp_dir.exists():
            temp_dir.rmdir()

def test_missing_sections():
    """测试缺少配置部分的情况"""
    # 创建缺少部分配置的临时文件
    temp_dir = Path(os.path.expanduser("~")) / "tmp_test_config"
    temp_dir.mkdir(exist_ok=True)
    temp_config = temp_dir / "partial_config.json"
    
    try:
        # 只包含GENERAL部分的配置
        partial_config = {
            "GENERAL": {
                "api_id": 12345,
                "api_hash": "abcd1234"
            }
        }
        
        with open(temp_config, 'w', encoding='utf-8') as f:
            json.dump(partial_config, f)
        
        # 初始化配置管理器
        config_manager = ConfigManager(str(temp_config))
        
        # 应该能够获取GENERAL配置
        general_config = config_manager.get_general_config()
        assert general_config.api_id == 12345
        
        # 获取缺失的配置部分应该返回默认值
        download_config = config_manager.get_download_config()
        assert hasattr(download_config, 'source_channels')
        assert isinstance(download_config.source_channels, list)
    finally:
        # 清理
        if temp_config.exists():
            temp_config.unlink()
        if temp_dir.exists():
            temp_dir.rmdir()

if __name__ == "__main__":
    pytest.main(["-xvs", "test_config_manager.py"]) 