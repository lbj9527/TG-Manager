"""
强壮Telegram客户端 - 配置管理模块
负责分离和管理代理、连接、客户端配置
"""

import json
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

from src.utils.logger import get_logger

logger = get_logger()


class ProxyType(Enum):
    """代理类型枚举"""
    SOCKS5 = "SOCKS5"
    SOCKS4 = "SOCKS4"
    HTTP = "HTTP"


@dataclass
class ProxyConfig:
    """代理配置"""
    enabled: bool = False
    proxy_type: ProxyType = ProxyType.SOCKS5
    host: str = "127.0.0.1"
    port: int = 1080
    username: Optional[str] = None
    password: Optional[str] = None
    
    def to_pyrogram_dict(self) -> Optional[Dict[str, Any]]:
        """转换为Pyrogram客户端可用的代理字典"""
        if not self.enabled:
            return None
            
        proxy_dict = {
            "scheme": self.proxy_type.value.lower(),
            "hostname": self.host,
            "port": self.port
        }
        
        if self.username:
            proxy_dict["username"] = self.username
        if self.password:
            proxy_dict["password"] = self.password
            
        return {"proxy": proxy_dict}


@dataclass
class ConnectionConfig:
    """连接配置"""
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    max_retry_delay: float = 300.0
    auto_restart_session: bool = True
    connection_check_interval: int = 30
    
    # 指数退避重连配置
    enable_exponential_backoff: bool = True
    backoff_multiplier: float = 2.0
    max_backoff_attempts: int = 5


@dataclass
class ClientConfig:
    """客户端配置"""
    api_id: int
    api_hash: str
    phone_number: str = ""
    session_name: str = "tg_manager"
    sleep_threshold: int = 0  # 禁用Pyrogram内置FloodWait处理
    
    # 并发控制配置
    max_concurrent_requests: int = 10
    request_delay: float = 0.1
    flood_wait_auto_retry: bool = True
    flood_wait_max_retries: int = 5


class ClientConfigManager:
    """客户端配置管理器"""
    
    def __init__(self, config_path: str = "config.json"):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self._raw_config: Dict[str, Any] = {}
        self._proxy_config: Optional[ProxyConfig] = None
        self._connection_config: Optional[ConnectionConfig] = None
        self._client_config: Optional[ClientConfig] = None
        
        self.load_config()
    
    def load_config(self) -> bool:
        """
        加载配置文件
        
        Returns:
            bool: 是否成功加载
        """
        try:
            if not os.path.exists(self.config_path):
                logger.warning(f"配置文件不存在: {self.config_path}")
                self._create_default_config()
                return False
                
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._raw_config = json.load(f)
                
            self._parse_config()
            logger.info(f"成功加载配置文件: {self.config_path}")
            return True
            
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            self._create_default_config()
            return False
    
    def _parse_config(self):
        """解析配置并创建各种配置对象"""
        general_config = self._raw_config.get('GENERAL', {})
        
        # 解析代理配置
        self._proxy_config = ProxyConfig(
            enabled=general_config.get('proxy_enabled', False),
            proxy_type=ProxyType(general_config.get('proxy_type', 'SOCKS5')),
            host=general_config.get('proxy_addr', '127.0.0.1'),
            port=general_config.get('proxy_port', 1080),
            username=general_config.get('proxy_username') or None,
            password=general_config.get('proxy_password') or None
        )
        
        # 解析连接配置
        self._connection_config = ConnectionConfig(
            timeout=general_config.get('timeout', 30),
            max_retries=general_config.get('max_retries', 3),
            auto_restart_session=general_config.get('auto_restart_session', True),
            retry_delay=general_config.get('retry_delay', 1.0),
            max_retry_delay=general_config.get('max_retry_delay', 300.0),
            connection_check_interval=general_config.get('connection_check_interval', 30)
        )
        
        # 解析客户端配置
        api_id = general_config.get('api_id')
        api_hash = general_config.get('api_hash')
        
        if not api_id or not api_hash:
            raise ValueError("API ID 和 API Hash 是必需的")
            
        self._client_config = ClientConfig(
            api_id=api_id,
            api_hash=api_hash,
            phone_number=general_config.get('phone_number', ''),
            session_name=general_config.get('session_name', 'tg_manager'),
            max_concurrent_requests=general_config.get('max_concurrent_requests', 10),
            request_delay=general_config.get('request_delay', 0.1),
            flood_wait_max_retries=general_config.get('flood_wait_max_retries', 5)
        )
    
    def _create_default_config(self):
        """创建默认配置"""
        self._proxy_config = ProxyConfig()
        self._connection_config = ConnectionConfig()
        self._client_config = ClientConfig(
            api_id=0,  # 需要用户配置
            api_hash="",  # 需要用户配置
            phone_number=""
        )
        logger.info("已创建默认配置")
    
    def get_proxy_config(self) -> ProxyConfig:
        """获取代理配置"""
        return self._proxy_config
    
    def get_connection_config(self) -> ConnectionConfig:
        """获取连接配置"""
        return self._connection_config
    
    def get_client_config(self) -> ClientConfig:
        """获取客户端配置"""
        return self._client_config
    
    def get_raw_config(self) -> Dict[str, Any]:
        """获取原始配置字典"""
        return self._raw_config.copy()
    
    def is_proxy_enabled(self) -> bool:
        """检查是否启用代理"""
        return self._proxy_config.enabled if self._proxy_config else False
    
    def get_pyrogram_client_kwargs(self) -> Dict[str, Any]:
        """
        获取创建Pyrogram客户端所需的参数
        
        Returns:
            Dict[str, Any]: 客户端参数字典
        """
        if not self._client_config:
            raise ValueError("客户端配置未初始化")
            
        kwargs = {
            "name": f"sessions/{self._client_config.session_name}",
            "api_id": self._client_config.api_id,
            "api_hash": self._client_config.api_hash,
            "phone_number": self._client_config.phone_number,
            "sleep_threshold": self._client_config.sleep_threshold
        }
        
        # 添加代理配置（如果启用）
        if self.is_proxy_enabled():
            proxy_dict = self._proxy_config.to_pyrogram_dict()
            if proxy_dict:
                kwargs.update(proxy_dict)
                logger.info(f"启用代理: {self._proxy_config.proxy_type.value}://{self._proxy_config.host}:{self._proxy_config.port}")
        
        return kwargs
    
    def validate_config(self) -> bool:
        """
        验证配置有效性
        
        Returns:
            bool: 配置是否有效
        """
        try:
            if not self._client_config:
                logger.error("客户端配置缺失")
                return False
                
            if not self._client_config.api_id or not self._client_config.api_hash:
                logger.error("API ID 和 API Hash 不能为空")
                return False
                
            if self.is_proxy_enabled():
                if not self._proxy_config.host or not self._proxy_config.port:
                    logger.error("代理配置不完整")
                    return False
                    
            logger.info("配置验证通过")
            return True
            
        except Exception as e:
            logger.error(f"配置验证失败: {e}")
            return False
    
    def update_config(self, section: str, key: str, value: Any):
        """
        更新配置项
        
        Args:
            section: 配置节名称
            key: 配置键名
            value: 配置值
        """
        if section not in self._raw_config:
            self._raw_config[section] = {}
            
        self._raw_config[section][key] = value
        
        # 重新解析配置
        self._parse_config()
        logger.debug(f"更新配置: {section}.{key} = {value}")
    
    def save_config(self) -> bool:
        """
        保存配置到文件
        
        Returns:
            bool: 是否成功保存
        """
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self._raw_config, f, indent=2, ensure_ascii=False)
                
            logger.info(f"配置已保存到: {self.config_path}")
            return True
            
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            return False 