"""
客户端管理器模块，负责创建和管理Pyrogram客户端
"""

import os
import asyncio
from typing import Optional, Dict, Any, Union

from pyrogram import Client
from pyrogram.types import User
from pyrogram.errors import (
    FloodWait, SessionPasswordNeeded,
    PhoneCodeInvalid, PhoneCodeExpired,
    AuthKeyUnregistered, UserDeactivated,
    Unauthorized
)

from src.utils.ui_config_manager import UIConfigManager
from src.utils.config_utils import convert_ui_config_to_dict, get_proxy_settings_from_config
from src.utils.logger import get_logger

logger = get_logger()

class ClientManager:
    """
    Pyrogram客户端管理器
    负责创建、初始化和管理Telegram客户端连接
    """
    
    def __init__(self, ui_config_manager: UIConfigManager = None, session_name: str = "tg_manager", 
                 api_id: int = None, api_hash: str = None, phone_number: str = None):
        """
        初始化客户端管理器
        
        可以通过两种方式初始化：
        1. 提供UIConfigManager实例，从配置中加载API凭据
        2. 直接提供api_id、api_hash和phone_number参数
        
        Args:
            ui_config_manager: UI配置管理器实例，可选
            session_name: 会话名称，默认为"tg_manager"
            api_id: Telegram API ID，可选
            api_hash: Telegram API Hash，可选
            phone_number: 电话号码，可选
        """
        self.ui_config_manager = ui_config_manager
        self.session_name = session_name
        self.client = None
        self.me = None  # 用户信息
        self.is_authorized = False
        
        # 如果直接提供了API凭据，使用直接提供的参数
        if api_id and api_hash:
            self.api_id = api_id
            self.api_hash = api_hash
            self.phone_number = phone_number
        # 否则从配置管理器加载
        elif ui_config_manager:
            # 获取UI配置并转换为字典
            ui_config = self.ui_config_manager.get_ui_config()
            self.config = convert_ui_config_to_dict(ui_config)
            
            # 获取通用配置
            general_config = self.config.get('GENERAL', {})
            
            # 获取API凭据
            self.api_id = general_config.get('api_id')
            self.api_hash = general_config.get('api_hash')
            self.phone_number = general_config.get('phone_number')
            
            # 获取代理设置
            self.proxy_settings = get_proxy_settings_from_config(self.config)
        else:
            raise ValueError("必须提供UIConfigManager实例或直接提供API凭据")
    
    async def create_client(self):
        """
        创建Pyrogram客户端实例
        
        Returns:
            Client: Pyrogram客户端实例
        """
        if self.client:
            return self.client
        
        # 创建工作目录
        os.makedirs("sessions", exist_ok=True)
        
        # 获取代理设置
        proxy_args = {}
        if hasattr(self, 'proxy_settings') and self.proxy_settings:
            proxy_args.update(self.proxy_settings)
        
        # 创建客户端
        self.client = Client(
            name=f"sessions/{self.session_name}",
            api_id=self.api_id,
            api_hash=self.api_hash,
            phone_number=self.phone_number,
            **proxy_args
        )
        
        return self.client
    
    async def start_client(self):
        """
        启动客户端
        
        如果客户端未创建，则先创建客户端
        
        Returns:
            Client: 已启动的客户端实例
            
        Raises:
            FloodWait: 发送请求过于频繁
            AuthKeyUnregistered: 授权密钥未注册
            UserDeactivated: 用户已停用
            Unauthorized: 未授权
        """
        if not self.client:
            await self.create_client()
        
        # 如果客户端已连接，直接返回
        if self.client.is_connected:
            return self.client
        
        try:
            await self.client.start()
            self.me = await self.client.get_me()
            self.is_authorized = True
            logger.info(f"客户端已启动：{self.me.first_name} (@{self.me.username})")
            return self.client
            
        except FloodWait as e:
            logger.warning(f"请求过于频繁，需要等待 {e.value} 秒")
            await asyncio.sleep(e.value)
            return await self.start_client()
            
        except AuthKeyUnregistered:
            logger.error("授权密钥未注册，需要重新登录")
            self.is_authorized = False
            raise
            
        except UserDeactivated:
            logger.error("用户账号已被停用")
            self.is_authorized = False
            raise
            
        except Unauthorized:
            logger.error("未授权，需要登录")
            self.is_authorized = False
            raise
    
    async def stop_client(self):
        """停止客户端"""
        if self.client and self.client.is_connected:
            await self.client.stop()
            logger.info("客户端已停止")
    
    async def restart_client(self):
        """重启客户端"""
        await self.stop_client()
        return await self.start_client()
    
    async def send_code(self):
        """
        发送登录验证码
        
        Returns:
            dict: 发送验证码的结果
            
        Raises:
            FloodWait: 发送请求过于频繁
        """
        if not self.client:
            await self.create_client()
        
        try:
            sent_code = await self.client.send_code(self.phone_number)
            logger.info(f"验证码已发送到 {self.phone_number}")
            return sent_code
        except FloodWait as e:
            logger.warning(f"请求过于频繁，需要等待 {e.value} 秒")
            await asyncio.sleep(e.value)
            return await self.send_code()
    
    async def sign_in(self, phone_code: str):
        """
        使用验证码登录
        
        Args:
            phone_code: 验证码
            
        Returns:
            User: 用户信息
            
        Raises:
            PhoneCodeInvalid: 验证码无效
            PhoneCodeExpired: 验证码已过期
            SessionPasswordNeeded: 需要两步验证密码
        """
        if not self.client:
            raise ValueError("客户端未创建，请先调用send_code")
        
        try:
            self.me = await self.client.sign_in(self.phone_number, phone_code)
            self.is_authorized = True
            logger.info(f"登录成功：{self.me.first_name} (@{self.me.username})")
            return self.me
        except (PhoneCodeInvalid, PhoneCodeExpired) as e:
            logger.error(f"验证码错误：{str(e)}")
            raise
        except SessionPasswordNeeded:
            logger.info("需要两步验证密码")
            raise
    
    async def check_password(self, password: str):
        """
        验证两步验证密码
        
        Args:
            password: 两步验证密码
            
        Returns:
            User: 用户信息
        """
        if not self.client:
            raise ValueError("客户端未创建，请先调用send_code")
        
        try:
            self.me = await self.client.check_password(password)
            self.is_authorized = True
            logger.info(f"密码验证成功：{self.me.first_name} (@{self.me.username})")
            return self.me
        except Exception as e:
            logger.error(f"密码验证失败：{str(e)}")
            raise 