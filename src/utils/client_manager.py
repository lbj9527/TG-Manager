"""
客户端管理器模块，负责创建和管理Pyrogram客户端
"""

import os
from typing import Optional, Dict, Any

from pyrogram import Client
from pyrogram.errors import FloodWait, AuthKeyUnregistered
import time

from src.utils.config_manager import ConfigManager
from src.utils.logger import get_logger

logger = get_logger()

class ClientManager:
    """
    Pyrogram客户端管理器
    负责创建、初始化和管理Telegram客户端连接
    """
    
    def __init__(self, config_manager: ConfigManager, session_name: str = "tg_forwarder"):
        """
        初始化客户端管理器
        
        Args:
            config_manager: 配置管理器实例
            session_name: 会话名称，默认为'tg_forwarder'
        """
        self.config_manager = config_manager
        self.session_name = session_name
        self.client: Optional[Client] = None
        
        # 获取API凭据和代理设置
        general_config = self.config_manager.get_general_config()
        self.api_id = general_config.api_id
        self.api_hash = general_config.api_hash
        self.proxy_settings = self.config_manager.get_proxy_settings()
    
    def create_client(self) -> Client:
        """
        创建Pyrogram客户端实例
        
        Returns:
            Client: Pyrogram客户端实例
        """
        logger.info(f"创建Pyrogram客户端，会话名称：{self.session_name}")
        
        # 创建客户端
        client = Client(
            self.session_name,
            api_id=self.api_id,
            api_hash=self.api_hash,
            **self.proxy_settings
        )
        
        return client
    
    async def start_client(self) -> Client:
        """
        启动Pyrogram客户端
        
        Returns:
            Client: 已启动的Pyrogram客户端实例
        """
        if self.client is not None and self.client.is_connected:
            logger.info("客户端已连接，无需重新启动")
            return self.client
        
        # 创建客户端
        self.client = self.create_client()
        
        # 启动客户端
        try:
            await self.client.start()
            logger.info("客户端启动成功")
            
            # 打印当前用户信息
            me = await self.client.get_me()
            logger.info(f"已登录账户：{me.first_name} (@{me.username})")
            
            return self.client
        except FloodWait as e:
            logger.warning(f"启动客户端时遇到限制，等待 {e.x} 秒")
            time.sleep(e.x)
            return await self.start_client()
        except AuthKeyUnregistered:
            logger.error("会话已失效，请重新登录")
            # 删除会话文件
            session_file = f"{self.session_name}.session"
            if os.path.exists(session_file):
                os.remove(session_file)
            # 重新创建会话
            self.client = self.create_client()
            await self.client.start()
            logger.info("客户端重新登录成功")
            return self.client
        except Exception as e:
            logger.error(f"启动客户端失败：{e}")
            raise
    
    async def stop_client(self):
        """
        停止Pyrogram客户端
        """
        if self.client and self.client.is_connected:
            await self.client.stop()
            logger.info("客户端已停止")
            self.client = None 