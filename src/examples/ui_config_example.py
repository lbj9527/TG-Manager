"""
UI配置模型使用示例

本示例展示如何使用UI配置模型和UI配置管理器来处理配置。
"""

import os
import sys
import json
from typing import Dict, Any, List, Union
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# 导入配置模型和配置管理器
from src.utils.ui_config_models import (
    create_default_config, MediaType, ProxyType,
    UIConfig, UIGeneralConfig, UITextFilterItem, UIChannelPair, UIMonitorChannelPair
)
from src.utils.ui_config_manager import UIConfigManager


def print_separator(title: str):
    """打印分隔线"""
    print("\n" + "=" * 50)
    print(f" {title} ".center(50, "="))
    print("=" * 50 + "\n")


def create_and_validate_config():
    """创建和验证配置示例"""
    print_separator("创建和验证配置")
    
    # 创建默认配置
    config = create_default_config()
    
    # 修改配置
    config.GENERAL.api_id = 12345
    config.GENERAL.api_hash = "abcd1234efgh5678ijkl9012mnop3456"
    config.GENERAL.proxy_enabled = True
    config.GENERAL.proxy_type = ProxyType.SOCKS5
    
    # 设置下载配置
    config.DOWNLOAD.downloadSetting[0].source_channels = "@channel1"
    config.DOWNLOAD.downloadSetting[0].media_types = [MediaType.PHOTO, MediaType.VIDEO]
    config.DOWNLOAD.downloadSetting[0].keywords = ["测试", "示例"]
    config.DOWNLOAD.parallel_download = True
    
    # 设置上传配置
    config.UPLOAD.target_channels = ["@target1", "@target2"]
    config.UPLOAD.caption_template = "{filename} - 上传于{date}"
    
    # 设置转发配置
    config.FORWARD.forward_channel_pairs = [
        UIChannelPair(
            source_channel="@source1",
            target_channels=["@target1", "@target2"]
        ),
        UIChannelPair(
            source_channel="https://t.me/channel2",
            target_channels=["@target3"]
        )
    ]
    config.FORWARD.hide_author = True
    
    # 设置监听配置
    config.MONITOR.monitor_channel_pairs = [
        UIMonitorChannelPair(
            source_channel="@source1",
            target_channels=["@target1", "@target2"],
            remove_captions=True,
            text_filter=[
                UITextFilterItem(original_text="敏感词", target_text="替换词"),
                UITextFilterItem(original_text="广告", target_text="")
            ]
        )
    ]
    config.MONITOR.duration = "2099-12-31"
    
    # 将配置转换为字典并打印
    config_dict = config.dict()
    print("配置字典:")
    print(json.dumps(convert_enums_to_str(config_dict), indent=2, ensure_ascii=False))
    
    # 测试配置验证
    try:
        # 修改配置使其无效
        config.GENERAL.api_id = -1  # 无效的API ID
        
        # 手动调用验证
        config.GENERAL.validate_api_id(config.GENERAL.api_id)
    except Exception as e:
        print(f"\n验证错误: {e}")


def convert_enums_to_str(config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """将配置字典中的枚举值转换为字符串"""
    # 创建配置副本
    result = dict(config_dict)
    
    # 处理GeneralConfig中的proxy_type
    if "GENERAL" in result and "proxy_type" in result["GENERAL"]:
        result["GENERAL"]["proxy_type"] = result["GENERAL"]["proxy_type"].value
    
    # 处理DownloadConfig中的media_types
    if "DOWNLOAD" in result and "downloadSetting" in result["DOWNLOAD"]:
        for item in result["DOWNLOAD"]["downloadSetting"]:
            if "media_types" in item:
                item["media_types"] = [mt.value for mt in item["media_types"]]
    
    # 处理ForwardConfig和MonitorConfig中的media_types
    for section in ["FORWARD", "MONITOR"]:
        if section in result and "media_types" in result[section]:
            result[section]["media_types"] = [mt.value for mt in result[section]["media_types"]]
    
    return result


def use_ui_config_manager():
    """使用UI配置管理器示例"""
    print_separator("使用UI配置管理器")
    
    # 创建临时配置文件路径
    temp_config_path = "temp_config.json"
    
    try:
        # 创建UI配置管理器
        ui_config_manager = UIConfigManager(temp_config_path)
        
        # 获取当前配置
        config = ui_config_manager.get_ui_config()
        
        # 修改配置
        config.GENERAL.api_id = 67890
        config.GENERAL.api_hash = "fedcba9876543210"
        config.DOWNLOAD.parallel_download = True
        config.DOWNLOAD.max_concurrent_downloads = 8
        
        # 添加一个下载设置项
        if not config.DOWNLOAD.downloadSetting:
            from src.utils.ui_config_models import UIDownloadSettingItem
            config.DOWNLOAD.downloadSetting.append(
                UIDownloadSettingItem(
                    source_channels="@example_channel",
                    start_id=1000,
                    end_id=2000,
                    media_types=[MediaType.PHOTO, MediaType.VIDEO, MediaType.DOCUMENT],
                    keywords=["重要", "公告"]
                )
            )
        
        # 保存配置
        ui_config_manager.save_config()
        print(f"配置已保存到: {temp_config_path}")
        
        # 验证配置
        errors = ui_config_manager.validate_config()
        if errors:
            print("配置错误:")
            for error in errors:
                print(f" - {error}")
        else:
            print("配置验证通过")
        
        # 从文件重新加载配置
        new_ui_config_manager = UIConfigManager(temp_config_path)
        new_config = new_ui_config_manager.get_ui_config()
        
        # 检查加载的配置是否与保存的一致
        print(f"\n重新加载的配置:")
        print(f"API ID: {new_config.GENERAL.api_id}")
        print(f"API Hash: {new_config.GENERAL.api_hash}")
        print(f"并行下载: {new_config.DOWNLOAD.parallel_download}")
        print(f"最大并发下载数: {new_config.DOWNLOAD.max_concurrent_downloads}")
        
        if new_config.DOWNLOAD.downloadSetting:
            print("\n下载设置项:")
            for i, item in enumerate(new_config.DOWNLOAD.downloadSetting):
                print(f"  设置项 {i+1}:")
                print(f"    源频道: {item.source_channels}")
                print(f"    起始ID: {item.start_id}")
                print(f"    结束ID: {item.end_id}")
                print(f"    媒体类型: {[mt.value for mt in item.media_types]}")
                print(f"    关键词: {item.keywords}")
    
    finally:
        # 清理临时文件
        if os.path.exists(temp_config_path):
            os.remove(temp_config_path)
            print(f"\n临时配置文件 {temp_config_path} 已删除")


def simulate_config_errors():
    """模拟配置错误并捕获详细的错误信息"""
    print_separator("模拟配置错误")
    
    # 创建一些无效配置并测试验证
    invalid_configs = [
        # 无效的API ID
        {"type": "API ID", "config": {"GENERAL": {"api_id": -1, "api_hash": "abcd"}}},
        # 无效的API Hash
        {"type": "API Hash", "config": {"GENERAL": {"api_id": 12345, "api_hash": "123"}}},
        # 无效的频道ID
        {"type": "频道ID", "config": {"UPLOAD": {"target_channels": ["invalid_channel"]}}},
        # 无效的日期格式
        {"type": "日期格式", "config": {"MONITOR": {"duration": "2023/12/31"}}},
        # 结束ID小于起始ID
        {"type": "消息ID范围", "config": {"DOWNLOAD": {"downloadSetting": [{"source_channels": "@channel", "start_id": 2000, "end_id": 1000}]}}},
    ]
    
    for invalid_config in invalid_configs:
        config_type = invalid_config["type"]
        config_data = invalid_config["config"]
        
        print(f"\n测试无效配置: {config_type}")
        try:
            # 创建默认配置
            config = create_default_config()
            
            # 修改为无效配置
            if "GENERAL" in config_data:
                for key, value in config_data["GENERAL"].items():
                    setattr(config.GENERAL, key, value)
            
            if "UPLOAD" in config_data:
                for key, value in config_data["UPLOAD"].items():
                    setattr(config.UPLOAD, key, value)
            
            if "MONITOR" in config_data:
                for key, value in config_data["MONITOR"].items():
                    setattr(config.MONITOR, key, value)
            
            if "DOWNLOAD" in config_data:
                for key, value in config_data["DOWNLOAD"].items():
                    if key == "downloadSetting":
                        from src.utils.ui_config_models import UIDownloadSettingItem
                        settings = []
                        for item in value:
                            settings.append(UIDownloadSettingItem(**item))
                        config.DOWNLOAD.downloadSetting = settings
                    else:
                        setattr(config.DOWNLOAD, key, value)
            
            # 转换为字典以触发验证
            config_dict = config.dict()
            print("  配置有效")
        except Exception as e:
            print(f"  配置错误: {e}")


if __name__ == "__main__":
    # 运行示例
    create_and_validate_config()
    use_ui_config_manager()
    simulate_config_errors()
    
    print("\n示例运行完成") 