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
    
    def __init__(self, config_path: str = "config.json"):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径，默认为'config.json'
        """
        self.config_path = config_path
        self.config = {}
        self.config_parser = configparser.ConfigParser()
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
            # 根据文件扩展名决定如何加载
            if self.config_path.endswith('.json'):
                self._load_json_config()
            else:
                self._load_ini_config()
            
            logging.info(f"成功加载配置文件: {self.config_path}")
        except Exception as e:
            logging.error(f"加载配置文件失败: {e}")
            raise
    
    def _load_json_config(self) -> None:
        """加载JSON格式的配置文件"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
    
    def _load_ini_config(self) -> None:
        """加载INI格式的配置文件"""
        self.config_parser.read(self.config_path, encoding='utf-8')
        # 将INI配置转换为字典
        self.config = {}
        for section in self.config_parser.sections():
            self.config[section] = {}
            for key, value in self.config_parser[section].items():
                self.config[section][key] = value
    
    def _create_default_config(self) -> None:
        """创建默认配置文件"""
        default_config = {
            'GENERAL': {
                'api_id': '请在此填写您的Telegram API ID',
                'api_hash': '请在此填写您的Telegram API Hash',
                'limit': 50,
                'pause_time': 60,
                'timeout': 30,
                'max_retries': 3,
                'proxy_enabled': False,
                'proxy_type': 'SOCKS5',
                'proxy_addr': '127.0.0.1',
                'proxy_port': 1080,
                'proxy_username': '',
                'proxy_password': ''
            },
            'DOWNLOAD': {
                'start_id': 0,
                'end_id': 0,
                'source_channels': ["https://t.me/telegram", "@durov"],
                'organize_by_chat': True,
                'download_path': 'downloads',
                'media_types': ["photo", "video", "document", "audio", "animation"]
            },
            'UPLOAD': {
                'target_channels': [],
                'directory': 'uploads',
                'caption_template': '{filename}'
            },
            'FORWARD': {
                'forward_channel_pairs': [],
                'remove_captions': False,
                'media_types': ["photo", "video", "document", "audio", "animation"],
                'forward_delay': 3,
                'start_id': 0,
                'end_id': 0,
                'tmp_path': 'tmp'
            },
            'MONITOR': {
                'monitor_channel_pairs': [],
                'remove_captions': False,
                'media_types': ["photo", "video", "document", "audio", "animation"],
                'duration': '',
                'forward_delay': 3
            }
        }
        
        # 根据文件扩展名决定保存格式
        if self.config_path.endswith('.json'):
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=4, ensure_ascii=False)
            self.config = default_config
        else:
            self.config_parser = configparser.ConfigParser()
            for section, values in default_config.items():
                self.config_parser[section] = {}
                for key, value in values.items():
                    self.config_parser[section][key] = str(value)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                self.config_parser.write(f)
            
            self._load_ini_config()
        
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
            if section in self.config and key in self.config[section]:
                return self.config[section][key]
            return fallback
        except Exception:
            logging.warning(f"配置项不存在: [{section}] {key}，使用默认值: {fallback}")
            return fallback
    
    def get_int(self, section: str, key: str, fallback: int = 0) -> int:
        """获取整型配置值"""
        try:
            value = self.get_value(section, key)
            if value is not None:
                return int(value)
            return fallback
        except (ValueError, TypeError):
            logging.warning(f"配置项不存在或非整数: [{section}] {key}，使用默认值: {fallback}")
            return fallback
    
    def get_bool(self, section: str, key: str, fallback: bool = False) -> bool:
        """获取布尔型配置值"""
        try:
            value = self.get_value(section, key)
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ('true', 'yes', '1', 'on')
            return bool(value)
        except (ValueError, TypeError):
            logging.warning(f"配置项不存在或非布尔值: [{section}] {key}，使用默认值: {fallback}")
            return fallback
    
    def get_json(self, section: str, key: str, fallback: Any = None) -> Any:
        """获取JSON格式的配置值"""
        try:
            value = self.get_value(section, key)
            # 如果已经是列表或字典，直接返回
            if isinstance(value, (list, dict)):
                return value
            # 否则尝试解析JSON
            if value is not None:
                return json.loads(value)
            return fallback if fallback is not None else []
        except (json.JSONDecodeError, TypeError):
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
            json.dump(self.config, f, indent=4, ensure_ascii=False)
        
        logging.info(f"已更新配置: [{section}] {key} = {value}") 