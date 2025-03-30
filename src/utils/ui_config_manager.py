"""
UI配置管理器模块，负责UI配置的加载、保存和与原配置的转换等功能。
"""

import os
import json
from typing import Dict, Any, Optional, Union, List
from datetime import datetime
import logging

from src.utils.ui_config_models import (
    UIConfig, UIGeneralConfig, UIDownloadConfig, UIUploadConfig, 
    UIForwardConfig, UIMonitorConfig, UIChannelPair, UIMonitorChannelPair,
    UIDownloadSettingItem, UITextFilterItem, MediaType, ProxyType,
    create_default_config
)
from src.utils.config_manager import ConfigManager
from src.utils.logger import get_logger

logger = get_logger()

class UIConfigManager:
    """UI配置管理器，负责处理UI配置的加载、保存和转换"""
    
    def __init__(self, config_path: str = "config.json"):
        """
        初始化UI配置管理器
        
        Args:
            config_path: 配置文件路径，默认为"config.json"
        """
        self.config_path = config_path
        self.ui_config = self._load_or_create_config()
    
    def _load_or_create_config(self) -> UIConfig:
        """
        加载或创建UI配置
        
        如果配置文件存在，则加载现有配置；否则创建默认配置
        
        Returns:
            UIConfig: UI配置对象
        """
        try:
            # 尝试从文件加载配置
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    return self._convert_to_ui_config(config_data)
            
            # 文件不存在，创建默认配置
            logger.info(f"配置文件不存在：{self.config_path}，创建默认配置")
            return create_default_config()
        
        except json.JSONDecodeError:
            logger.error(f"配置文件格式错误：{self.config_path}，创建默认配置")
            return create_default_config()
        
        except Exception as e:
            logger.error(f"加载配置失败：{e}，创建默认配置")
            return create_default_config()
    
    def _convert_to_ui_config(self, config_data: Dict[str, Any]) -> UIConfig:
        """
        将配置字典转换为UI配置对象
        
        Args:
            config_data: 配置字典
        
        Returns:
            UIConfig: UI配置对象
        """
        try:
            # 转换GeneralConfig
            general_config = config_data.get("GENERAL", {})
            if "proxy_type" in general_config:
                try:
                    general_config["proxy_type"] = ProxyType(general_config["proxy_type"])
                except ValueError:
                    general_config["proxy_type"] = ProxyType.SOCKS5
            
            # 转换DownloadConfig
            download_config = config_data.get("DOWNLOAD", {})
            if "downloadSetting" in download_config:
                for item in download_config["downloadSetting"]:
                    if "media_types" in item:
                        item["media_types"] = [
                            MediaType(mt) if mt in [e.value for e in MediaType] else MediaType.PHOTO
                            for mt in item["media_types"]
                        ]
            
            # 转换媒体类型列表
            for section in ["FORWARD", "MONITOR"]:
                if section in config_data and "media_types" in config_data[section]:
                    config_data[section]["media_types"] = [
                        MediaType(mt) if mt in [e.value for e in MediaType] else MediaType.PHOTO
                        for mt in config_data[section]["media_types"]
                    ]
            
            # 创建UI配置对象
            return UIConfig(**config_data)
        
        except Exception as e:
            logger.error(f"转换配置失败：{e}，创建默认配置")
            return create_default_config()
    
    def save_config(self) -> bool:
        """
        保存UI配置到文件
        
        Returns:
            bool: 保存是否成功
        """
        try:
            # 确保配置目录存在
            os.makedirs(os.path.dirname(os.path.abspath(self.config_path)), exist_ok=True)
            
            # 将配置转换为字典并保存
            config_dict = self.ui_config.dict()
            
            # 将枚举值转换为字符串
            self._convert_enums_to_str(config_dict)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, ensure_ascii=False, indent=2)
            
            logger.info(f"配置已保存到：{self.config_path}")
            return True
        
        except Exception as e:
            logger.error(f"保存配置失败：{e}")
            return False
    
    def _convert_enums_to_str(self, config_dict: Dict[str, Any]) -> None:
        """
        将配置字典中的枚举值转换为字符串
        
        Args:
            config_dict: 配置字典
        """
        # 处理GeneralConfig中的proxy_type
        if "GENERAL" in config_dict and "proxy_type" in config_dict["GENERAL"]:
            config_dict["GENERAL"]["proxy_type"] = config_dict["GENERAL"]["proxy_type"].value
        
        # 处理DownloadConfig中的media_types
        if "DOWNLOAD" in config_dict and "downloadSetting" in config_dict["DOWNLOAD"]:
            for item in config_dict["DOWNLOAD"]["downloadSetting"]:
                if "media_types" in item:
                    item["media_types"] = [mt.value for mt in item["media_types"]]
        
        # 处理ForwardConfig和MonitorConfig中的media_types
        for section in ["FORWARD", "MONITOR"]:
            if section in config_dict and "media_types" in config_dict[section]:
                config_dict[section]["media_types"] = [mt.value for mt in config_dict[section]["media_types"]]
    
    def get_ui_config(self) -> UIConfig:
        """
        获取UI配置对象
        
        Returns:
            UIConfig: UI配置对象
        """
        return self.ui_config
    
    def set_ui_config(self, ui_config: UIConfig) -> None:
        """
        设置UI配置对象
        
        Args:
            ui_config: UI配置对象
        """
        self.ui_config = ui_config
    
    def update_from_dict(self, config_dict: Dict[str, Any]) -> bool:
        """
        从字典更新UI配置
        
        Args:
            config_dict: 配置字典
        
        Returns:
            bool: 更新是否成功
        """
        try:
            self.ui_config = UIConfig(**config_dict)
            return True
        except Exception as e:
            logger.error(f"更新配置失败：{e}")
            return False
    
    def create_config_manager(self) -> ConfigManager:
        """
        创建原始ConfigManager实例
        
        将UI配置转换为原始配置并创建ConfigManager实例
        
        Returns:
            ConfigManager: 配置管理器实例
        """
        # 保存UI配置
        self.save_config()
        
        # 创建ConfigManager实例
        return ConfigManager(self.config_path)
    
    def update_from_config_manager(self, config_manager: ConfigManager) -> bool:
        """
        从ConfigManager更新UI配置
        
        Args:
            config_manager: ConfigManager实例
        
        Returns:
            bool: 更新是否成功
        """
        try:
            # 从ConfigManager获取配置并转换为UI配置
            config_data = {
                "GENERAL": config_manager.get_general_config().dict(),
                "DOWNLOAD": config_manager.get_download_config().dict(),
                "UPLOAD": config_manager.get_upload_config().dict(),
                "FORWARD": config_manager.get_forward_config().dict(),
                "MONITOR": config_manager.get_monitor_config().dict()
            }
            
            self.ui_config = self._convert_to_ui_config(config_data)
            return True
        
        except Exception as e:
            logger.error(f"从ConfigManager更新配置失败：{e}")
            return False
    
    def validate_config(self) -> List[str]:
        """
        验证UI配置是否有效
        
        Returns:
            List[str]: 错误消息列表，如果为空则表示配置有效
        """
        errors = []
        
        try:
            # 验证GENERAL配置
            if self.ui_config.GENERAL.api_id <= 0:
                errors.append("API ID必须是正整数")
            
            if not self.ui_config.GENERAL.api_hash:
                errors.append("API Hash不能为空")
            
            # 验证DOWNLOAD配置
            if not self.ui_config.DOWNLOAD.downloadSetting:
                errors.append("至少需要一个下载设置项")
            
            for i, item in enumerate(self.ui_config.DOWNLOAD.downloadSetting):
                if not item.source_channels:
                    errors.append(f"下载设置项[{i}]的源频道不能为空")
            
            # 验证UPLOAD配置
            if not self.ui_config.UPLOAD.target_channels:
                errors.append("上传配置的目标频道列表不能为空")
            
            # 验证FORWARD配置
            if not self.ui_config.FORWARD.forward_channel_pairs:
                errors.append("至少需要一个转发频道对")
            
            for i, pair in enumerate(self.ui_config.FORWARD.forward_channel_pairs):
                if not pair.source_channel:
                    errors.append(f"转发频道对[{i}]的源频道不能为空")
                if not pair.target_channels:
                    errors.append(f"转发频道对[{i}]的目标频道列表不能为空")
            
            # 验证MONITOR配置
            if not self.ui_config.MONITOR.monitor_channel_pairs:
                errors.append("至少需要一个监听频道对")
            
            for i, pair in enumerate(self.ui_config.MONITOR.monitor_channel_pairs):
                if not pair.source_channel:
                    errors.append(f"监听频道对[{i}]的源频道不能为空")
                if not pair.target_channels:
                    errors.append(f"监听频道对[{i}]的目标频道列表不能为空")
        
        except Exception as e:
            errors.append(f"验证配置时发生错误：{e}")
        
        return errors


def create_ui_config_manager(config_path: str = "config.json") -> UIConfigManager:
    """
    创建UI配置管理器实例
    
    Args:
        config_path: 配置文件路径
    
    Returns:
        UIConfigManager: UI配置管理器实例
    """
    return UIConfigManager(config_path) 