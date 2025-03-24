"""
配置管理模块
负责加载并解析配置文件，提供全局配置数据
"""

import os
import json
import configparser
from typing import Dict, List, Union, Any, Optional
from pathlib import Path
import logging

class ConfigManager:
    """配置管理类，负责加载和解析配置文件"""
    
    def __init__(self, config_path: str = "config.ini"):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径，默认为'config.ini'
        """
        self.config_path = config_path
        self.config = configparser.ConfigParser()
        self.download_history_path = "data/download_history.json"
        self.upload_history_path = "data/upload_history.json"
        self.forward_history_path = "data/forward_history.json"
        
        # 确保数据目录存在
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        
        # 加载配置
        self.load_config()
    
    def load_config(self) -> None:
        """加载配置文件，如果文件不存在则创建默认配置"""
        if not os.path.exists(self.config_path):
            self._create_default_config()
        
        try:
            self.config.read(self.config_path, encoding='utf-8')
            logging.info(f"成功加载配置文件: {self.config_path}")
        except Exception as e:
            logging.error(f"加载配置文件失败: {e}")
            raise
    
    def _create_default_config(self) -> None:
        """创建默认配置文件"""
        self.config['GENERAL'] = {
            'api_id': '请在此填写您的Telegram API ID',
            'api_hash': '请在此填写您的Telegram API Hash',
            'limit': '50',
            'pause_time': '60',
            'timeout': '30',
            'max_retries': '3',
            'proxy_enabled': 'false',
            'proxy_type': 'SOCKS5',
            'proxy_addr': '127.0.0.1',
            'proxy_port': '1080',
            'proxy_username': '',
            'proxy_password': ''
        }
        
        self.config['DOWNLOAD'] = {
            'start_id': '0',
            'end_id': '0',
            'source_channels': '[]',
            'organize_by_chat': 'true',
            'download_path': 'downloads',
            'media_types': '["photo", "video", "document", "audio", "animation"]'
        }
        
        self.config['UPLOAD'] = {
            'target_channels': '[]',
            'directory': 'uploads',
            'caption_template': '{filename}'
        }
        
        self.config['FORWARD'] = {
            'forward_channel_pairs': '[]',
            'remove_captions': 'false',
            'media_types': '["photo", "video", "document", "audio", "animation"]',
            'forward_delay': '3',
            'start_id': '0',
            'end_id': '0',
            'tmp_path': 'tmp'
        }
        
        self.config['MONITOR'] = {
            'monitor_channel_pairs': '[]',
            'remove_captions': 'false',
            'media_types': '["photo", "video", "document", "audio", "animation"]',
            'duration': '',
            'forward_delay': '3'
        }
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            self.config.write(f)
        
        logging.info(f"已创建默认配置文件: {self.config_path}")
    
    def get_value(self, section: str, key: str, fallback: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            section: 配置节名称
            key: 配置键名称
            fallback: 如果键不存在时的默认值
            
        Returns:
            配置值
        """
        try:
            value = self.config.get(section, key, fallback=fallback)
            return value
        except (configparser.NoSectionError, configparser.NoOptionError):
            logging.warning(f"配置项不存在: [{section}] {key}，使用默认值: {fallback}")
            return fallback
    
    def get_int(self, section: str, key: str, fallback: int = 0) -> int:
        """获取整型配置值"""
        try:
            return self.config.getint(section, key, fallback=fallback)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            logging.warning(f"配置项不存在或非整数: [{section}] {key}，使用默认值: {fallback}")
            return fallback
    
    def get_bool(self, section: str, key: str, fallback: bool = False) -> bool:
        """获取布尔型配置值"""
        try:
            return self.config.getboolean(section, key, fallback=fallback)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            logging.warning(f"配置项不存在或非布尔值: [{section}] {key}，使用默认值: {fallback}")
            return fallback
    
    def get_json(self, section: str, key: str, fallback: Any = None) -> Any:
        """获取JSON格式的配置值"""
        try:
            value = self.config.get(section, key)
            return json.loads(value)
        except (configparser.NoSectionError, configparser.NoOptionError, json.JSONDecodeError):
            logging.warning(f"配置项不存在或非有效JSON: [{section}] {key}，使用默认值")
            return fallback if fallback is not None else []
    
    def get_forward_channel_pairs(self) -> List[Dict[str, Union[str, List[str]]]]:
        """获取转发频道配对"""
        return self.get_json('FORWARD', 'forward_channel_pairs', [])
    
    def get_monitor_channel_pairs(self) -> List[Dict[str, Union[str, List[str]]]]:
        """获取监听频道配对"""
        return self.get_json('MONITOR', 'monitor_channel_pairs', [])
    
    def get_proxy_settings(self) -> Optional[Dict[str, Union[str, int]]]:
        """获取代理设置"""
        if not self.get_bool('GENERAL', 'proxy_enabled'):
            return None
        
        return {
            'scheme': self.get_value('GENERAL', 'proxy_type', 'SOCKS5').lower(),
            'hostname': self.get_value('GENERAL', 'proxy_addr', '127.0.0.1'),
            'port': self.get_int('GENERAL', 'proxy_port', 1080),
            'username': self.get_value('GENERAL', 'proxy_username', ''),
            'password': self.get_value('GENERAL', 'proxy_password', '')
        }
    
    def set_value(self, section: str, key: str, value: Any) -> None:
        """
        设置配置值
        
        Args:
            section: 配置节名称
            key: 配置键名称
            value: 配置值
        """
        if section not in self.config:
            self.config[section] = {}
        
        self.config[section][key] = str(value)
        with open(self.config_path, 'w', encoding='utf-8') as f:
            self.config.write(f)
        
        logging.info(f"已更新配置: [{section}] {key} = {value}") 