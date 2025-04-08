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
    
    def __init__(self, ui_config_manager: UIConfigManager, session_name: str = "tg_manager"):
        """
        初始化客户端管理器
        
        Args:
            ui_config_manager: UI配置管理器实例，用于加载API凭据
            session_name: 会话名称，默认为"tg_manager"
        """
        self.ui_config_manager = ui_config_manager
        self.session_name = session_name
        self.client = None
        self.me = None  # 用户信息
        self.is_authorized = False
        
        # 从配置管理器加载API凭据
        logger.info("从配置管理器加载API凭据")
        # 获取UI配置并转换为字典
        ui_config = self.ui_config_manager.get_ui_config()
        self.config = convert_ui_config_to_dict(ui_config)
        
        # 获取通用配置
        general_config = self.config.get('GENERAL', {})
        
        # 获取API凭据
        self.api_id = general_config.get('api_id')
        self.api_hash = general_config.get('api_hash')
        self.phone_number = general_config.get('phone_number')
        
        # 输出API凭据信息(注意不要输出完整信息，保护安全)
        logger.info(f"从配置中读取到API ID: {self.api_id}")
        if self.api_hash:
            # 只显示API Hash的前4位和后4位
            api_hash_masked = self.api_hash[:4] + '*****' + self.api_hash[-4:] if len(self.api_hash) > 8 else '****'
            logger.info(f"从配置中读取到API Hash: {api_hash_masked}")
        else:
            logger.warning("未能从配置中读取到API Hash")
        
        if self.phone_number:
            # 只显示电话号码的前4位和后2位
            masked_phone = self.phone_number[:4] + '****' + self.phone_number[-2:] if len(self.phone_number) > 6 else "***"
            logger.info(f"从配置中读取到电话号码: {masked_phone}")
        else:
            logger.warning("未能从配置中读取到电话号码")
        
        # 检查API凭据是否有效
        if not self.api_id or not self.api_hash:
            error_msg = "配置中的API凭据无效或缺失，请在设置中配置有效的API凭据"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # 获取代理设置
        self.proxy_settings = get_proxy_settings_from_config(self.config)
        logger.debug(f"代理设置: {self.proxy_settings}")
    
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
            if 'proxy' in proxy_args and 'hostname' in proxy_args['proxy']:
                proxy_info = f"{proxy_args['proxy'].get('scheme', '')}://{proxy_args['proxy'].get('hostname', '')}:{proxy_args['proxy'].get('port', '')}"
                logger.info(f"使用代理: {proxy_info}")
            else:
                logger.debug(f"代理设置: {proxy_args}")
        
        # 再次检查API凭据
        if not self.api_id or not self.api_hash:
            logger.error("API凭据缺失，无法创建客户端")
            raise ValueError("API凭据(api_id和api_hash)是必需的，无法创建客户端")
        
        logger.info(f"创建Pyrogram客户端 (api_id: {self.api_id})")
        
        # 创建客户端
        try:
            self.client = Client(
                name=f"sessions/{self.session_name}",
                api_id=self.api_id,
                api_hash=self.api_hash,
                phone_number=self.phone_number,
                **proxy_args
            )
            logger.info("客户端创建成功")
            return self.client
        except Exception as e:
            logger.error(f"创建客户端时出错: {e}")
            raise
    
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
        
        try:
            # 启动客户端
            logger.info("正在启动客户端...")
            await self.client.start()
            
            # 获取用户信息
            self.me = await self.client.get_me()
            self.is_authorized = True
            
            # 显示用户信息
            user_info = f"{self.me.first_name}"
            if self.me.last_name:
                user_info += f" {self.me.last_name}"
            user_info += f" (@{self.me.username})" if self.me.username else ""
            
            logger.info(f"客户端已启动：{user_info}")
            
            return self.client
            
        except FloodWait as e:
            logger.warning(f"启动客户端时遇到FloodWait，需要等待 {e.x} 秒")
            await asyncio.sleep(e.x)
            # 递归重试
            return await self.start_client()
            
        except Exception as e:
            logger.error(f"启动客户端时出错: {str(e)}")
            raise
    
    async def stop_client(self):
        """
        停止客户端
        
        Returns:
            bool: 是否成功停止
        """
        if self.client:
            try:
                await self.client.stop()
                self.client = None
                self.is_authorized = False
                logger.info("客户端已停止")
                return True
            except Exception as e:
                logger.error(f"停止客户端时出错: {e}")
                return False
        return True
    
    async def restart_client(self):
        """
        重启客户端
        
        Returns:
            Client: 重启后的客户端实例
        """
        await self.stop_client()
        return await self.start_client()
    
    async def send_code(self, phone_number: str = None):
        """
        发送验证码
        
        Args:
            phone_number: 电话号码，可选。如果未提供，则使用配置中的电话号码
            
        Returns:
            str: 手机号，用于确认
            bool: 是否已经发送过验证码
            
        Raises:
            FloodWait: 发送请求过于频繁
        """
        if not self.client:
            await self.create_client()
        
        # 如果提供了新电话号码，使用新号码
        if phone_number:
            self.phone_number = phone_number
            # 更新客户端设置
            self.client.phone_number = phone_number
        
        try:
            sent_code = await self.client.send_code(self.phone_number)
            return self.phone_number, sent_code.type
        except FloodWait as e:
            logger.warning(f"发送验证码遇到FloodWait，需要等待 {e.x} 秒")
            await asyncio.sleep(e.x)
            # 递归重试
            return await self.send_code()
        except Exception as e:
            logger.error(f"发送验证码时出错: {e}")
            raise
    
    async def sign_in(self, code: str, password: str = None):
        """
        使用验证码登录
        
        Args:
            code: 验证码
            password: 两步验证密码，如果启用了两步验证，则需要提供
            
        Returns:
            User: 用户信息
            
        Raises:
            PhoneCodeInvalid: 验证码无效
            PhoneCodeExpired: 验证码已过期
            SessionPasswordNeeded: 需要两步验证密码
        """
        if not self.client:
            await self.create_client()
        
        try:
            # 尝试用验证码登录
            signed_in = await self.client.sign_in(self.phone_number, code)
            # 更新用户信息
            self.me = await self.client.get_me()
            self.is_authorized = True
            
            return signed_in
            
        except SessionPasswordNeeded:
            # 如果启用了两步验证，尝试用密码登录
            if password:
                try:
                    signed_in = await self.client.check_password(password)
                    # 更新用户信息
                    self.me = await self.client.get_me()
                    self.is_authorized = True
                    
                    return signed_in
                except Exception as e:
                    logger.error(f"两步验证密码验证失败: {e}")
                    raise
            else:
                # 没有提供密码但需要两步验证
                logger.warning("需要两步验证密码，但未提供")
                raise SessionPasswordNeeded()
                
        except Exception as e:
            logger.error(f"登录时出错: {e}")
            raise
    
    async def is_client_authorized(self) -> bool:
        """
        检查客户端是否已授权
        
        Returns:
            bool: 是否已授权
        """
        if not self.client:
            return False
        
        try:
            # 尝试获取用户信息
            self.me = await self.client.get_me()
            self.is_authorized = bool(self.me)
            return self.is_authorized
        except Unauthorized:
            self.is_authorized = False
            return False
        except Exception as e:
            logger.error(f"检查授权状态时出错: {e}")
            self.is_authorized = False
            return False 