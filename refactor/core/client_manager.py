"""
客户端管理器

提供完善的Telegram客户端管理功能，包括登录流程、自动重连、会话管理等。
"""

import asyncio
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union
from loguru import logger

from pyrogram import Client
from pyrogram.errors import (
    FloodWait, SessionPasswordNeeded, PhoneCodeInvalid, 
    PhoneNumberInvalid, ApiIdInvalid, AuthKeyUnregistered
)
from pyrogram.types import User

from common.flood_wait_handler import FloodWaitHandler
from common.error_handler import ErrorHandler, ErrorType, ErrorSeverity


class ClientManager:
    """Telegram客户端管理器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client: Optional[Client] = None
        self.user: Optional[User] = None
        self.is_connected = False
        self.is_authenticated = False
        self.is_running = False
        self.should_stop = False
        
        # 配置参数
        self.session_name = config.get('session_name', 'tg_manager')
        self.api_id = config.get('api_id', '')
        self.api_hash = config.get('api_hash', '')
        self.phone_number = config.get('phone_number', '')
        self.session_path = Path(config.get('session_path', 'sessions'))
        
        # 登录配置
        self.code_timeout = config.get('code_timeout', 60)
        self.two_fa_password = config.get('two_fa_password', '')
        
        # 代理配置
        self.proxy = config.get('proxy', None)
        
        # 重连配置
        self.auto_reconnect = config.get('auto_reconnect', True)
        self.max_reconnect_attempts = config.get('max_reconnect_attempts', 5)
        self.reconnect_delay = config.get('reconnect_delay', 1.0)
        self.reconnect_attempts = 0
        
        # 连接监控
        self.connection_monitor_task: Optional[asyncio.Task] = None
        self.monitor_interval = config.get('monitor_interval', 30)
        
        # 错误处理
        self.flood_wait_handler = FloodWaitHandler()
        self.error_handler = ErrorHandler()
        
        # 事件总线
        self.event_bus = None
        
        # 确保会话目录存在
        self.session_path.mkdir(parents=True, exist_ok=True)
        
        # 初始化客户端
        self._init_client()
    
    def set_event_bus(self, event_bus) -> None:
        """设置事件总线"""
        self.event_bus = event_bus
        self.flood_wait_handler.set_event_bus(event_bus)
        self.error_handler.set_event_bus(event_bus)
    
    def _init_client(self) -> None:
        """初始化客户端"""
        try:
            # 确保session目录存在
            self.session_path.mkdir(parents=True, exist_ok=True)
            
            # 构建客户端参数
            client_params = {
                'name': self.session_name,
                'api_id': self.api_id,
                'api_hash': self.api_hash,
                'phone_number': self.phone_number,
                'workdir': str(self.session_path),
                'no_updates': True
            }
            
            # 添加代理配置
            if hasattr(self, 'proxy') and self.proxy:
                client_params['proxy'] = self.proxy
                logger.info(f"使用代理: {self.proxy['scheme']}://{self.proxy['hostname']}:{self.proxy['port']}")
            
            self.client = Client(**client_params)
            
            logger.info(f"客户端初始化成功: {self.session_name}")
            
        except Exception as e:
            error_info = self.error_handler.handle_error(e, {
                'operation': 'init_client',
                'session_name': self.session_name
            })
            logger.error(f"客户端初始化失败: {error_info}")
    
    async def initialize(self) -> bool:
        """初始化客户端管理器"""
        try:
            logger.info("初始化客户端管理器...")
            
            # 检查会话文件是否存在
            session_file = self.session_path / f"{self.session_name}.session"
            
            if session_file.exists():
                logger.info("发现现有会话文件，尝试恢复会话...")
                return await self._restore_session()
            else:
                logger.info("未发现会话文件，执行首次登录...")
                return await self._perform_first_login()
                
        except Exception as e:
            error_info = self.error_handler.handle_error(e, {
                'operation': 'initialize_client_manager'
            })
            logger.error(f"初始化客户端管理器失败: {error_info}")
            return False
    
    async def _restore_session(self) -> bool:
        """恢复现有会话"""
        try:
            logger.info("恢复现有会话...")
            
            # 启动客户端
            await self.client.start()
            
            # 获取用户信息
            self.user = await self.client.get_me()
            
            # 更新状态
            self.is_authenticated = True
            self.is_connected = True
            
            # 启动连接监控
            await self._start_connection_monitor()
            
            logger.info(f"会话恢复成功: {self.user.first_name} (@{self.user.username})")
            return True
            
        except Exception as e:
            error_info = self.error_handler.handle_error(e, {
                'operation': 'restore_session',
                'session_name': self.session_name
            })
            logger.error(f"恢复会话失败: {error_info}")
            return False
    
    async def _perform_first_login(self) -> bool:
        """执行首次登录"""
        try:
            logger.info("执行首次登录...")
            
            # 启动客户端（会触发登录流程）
            await self.client.start()
            
            # 获取用户信息
            self.user = await self.client.get_me()
            
            # 更新状态
            self.is_authenticated = True
            self.is_connected = True
            
            # 启动连接监控
            await self._start_connection_monitor()
            
            logger.info(f"首次登录成功: {self.user.first_name} (@{self.user.username})")
            return True
            
        except SessionPasswordNeeded:
            logger.info("需要两步验证密码...")
            return await self._handle_two_factor_auth()
        except PhoneCodeInvalid:
            logger.error("验证码无效，请检查验证码")
            return False
        except PhoneNumberInvalid:
            logger.error("手机号码无效，请检查手机号码格式")
            return False
        except ApiIdInvalid:
            logger.error("API ID或API Hash无效，请检查配置")
            return False
        except Exception as e:
            error_info = self.error_handler.handle_error(e, {
                'operation': 'first_login',
                'session_name': self.session_name
            })
            logger.error(f"首次登录失败: {error_info}")
            return False
    
    async def _handle_two_factor_auth(self) -> bool:
        """处理两步验证"""
        try:
            if not self.two_fa_password:
                logger.error("需要两步验证密码，但配置中未提供")
                return False
            
            logger.info("使用配置的两步验证密码...")
            
            # 使用配置的密码进行两步验证
            await self.client.check_password(self.two_fa_password)
            
            # 获取用户信息
            self.user = await self.client.get_me()
            
            # 更新状态
            self.is_authenticated = True
            self.is_connected = True
            
            # 启动连接监控
            await self._start_connection_monitor()
            
            logger.info(f"两步验证成功: {self.user.first_name} (@{self.user.username})")
            return True
            
        except Exception as e:
            error_info = self.error_handler.handle_error(e, {
                'operation': 'two_factor_auth',
                'session_name': self.session_name
            })
            logger.error(f"两步验证失败: {error_info}")
            return False
    
    async def _start_connection_monitor(self) -> None:
        """启动连接监控"""
        if not self.auto_reconnect:
            return
        
        if self.connection_monitor_task and not self.connection_monitor_task.done():
            self.connection_monitor_task.cancel()
        
        self.connection_monitor_task = asyncio.create_task(self._connection_monitor())
        logger.info("连接监控已启动")
    
    async def _connection_monitor(self) -> None:
        """连接监控循环"""
        while not self.should_stop:
            try:
                await asyncio.sleep(self.monitor_interval)
                
                if not self.should_stop:
                    await self.check_connection_status_now()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                error_info = self.error_handler.handle_error(e, {
                    'operation': 'connection_monitor'
                })
                logger.error(f"连接监控错误: {error_info}")
                await asyncio.sleep(5)  # 错误后短暂等待
    
    async def _handle_connection_loss(self) -> None:
        """处理连接丢失"""
        logger.warning("检测到连接丢失，尝试重连...")
        
        if self.event_bus:
            self.event_bus.emit("connection_lost", {
                'session_name': self.session_name,
                'timestamp': time.time()
            })
        
        await self._attempt_reconnect()
    
    async def _attempt_reconnect(self) -> None:
        """尝试重连"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"重连失败，已达到最大重试次数: {self.max_reconnect_attempts}")
            return
        
        self.reconnect_attempts += 1
        logger.info(f"尝试重连 ({self.reconnect_attempts}/{self.max_reconnect_attempts})...")
        
        try:
            # 停止当前客户端
            if self.client:
                await self.client.stop()
            
            # 重新初始化客户端
            self._init_client()
            
            # 尝试重新连接
            await self.client.start()
            
            # 验证连接
            self.user = await self.client.get_me()
            
            # 更新状态
            self.is_connected = True
            self.is_authenticated = True
            self.reconnect_attempts = 0
            
            logger.info(f"重连成功: {self.user.first_name} (@{self.user.username})")
            
            if self.event_bus:
                self.event_bus.emit("connection_restored", {
                    'session_name': self.session_name,
                    'user': self.user,
                    'timestamp': time.time()
                })
                
        except Exception as e:
            error_info = self.error_handler.handle_error(e, {
                'operation': 'reconnect',
                'attempt': self.reconnect_attempts
            })
            logger.error(f"重连失败: {error_info}")
            
            # 指数退避
            delay = self.reconnect_delay * (2 ** (self.reconnect_attempts - 1))
            await asyncio.sleep(delay)
    
    async def check_connection_status_now(self) -> bool:
        """立即检查连接状态"""
        try:
            if not self.client or not self.is_connected:
                await self._handle_connection_loss()
                return False
            
            # 尝试获取用户信息来验证连接
            user = await self.client.get_me()
            
            if user and user.id == (self.user.id if self.user else None):
                # 连接正常
                if not self.is_connected:
                    self.is_connected = True
                    logger.info("连接状态已恢复")
                return True
            else:
                # 连接异常
                await self._handle_connection_loss()
                return False
                
        except Exception as e:
            error_info = self.error_handler.handle_error(e, {
                'operation': 'check_connection_status'
            })
            logger.error(f"检查连接状态失败: {error_info}")
            await self._handle_connection_loss()
            return False
    
    async def stop(self) -> None:
        """停止客户端管理器"""
        try:
            logger.info("停止客户端管理器...")
            
            self.should_stop = True
            
            # 停止连接监控
            if self.connection_monitor_task and not self.connection_monitor_task.done():
                self.connection_monitor_task.cancel()
                try:
                    await self.connection_monitor_task
                except asyncio.CancelledError:
                    pass
            
            # 停止客户端
            if self.client:
                await self.client.stop()
            
            # 更新状态
            self.is_connected = False
            self.is_authenticated = False
            self.is_running = False
            
            logger.info("客户端管理器已停止")
            
        except Exception as e:
            error_info = self.error_handler.handle_error(e, {
                'operation': 'stop_client_manager'
            })
            logger.error(f"停止客户端管理器失败: {error_info}")
    
    def get_client(self) -> Optional[Client]:
        """获取客户端实例"""
        return self.client
    
    def get_user(self) -> Optional[User]:
        """获取用户信息"""
        return self.user
    
    def is_ready(self) -> bool:
        """检查客户端是否准备就绪"""
        return (
            self.client is not None and
            self.is_connected and
            self.is_authenticated and
            self.user is not None
        )
    
    def get_status(self) -> Dict[str, Any]:
        """获取客户端状态"""
        return {
            'is_connected': self.is_connected,
            'is_authenticated': self.is_authenticated,
            'is_running': self.is_running,
            'session_name': self.session_name,
            'user': {
                'id': self.user.id if self.user else None,
                'first_name': self.user.first_name if self.user else None,
                'username': self.user.username if self.user else None,
                'phone_number': self.user.phone_number if self.user else None
            } if self.user else None,
            'reconnect_attempts': self.reconnect_attempts,
            'max_reconnect_attempts': self.max_reconnect_attempts,
            'auto_reconnect': self.auto_reconnect,
            'monitor_interval': self.monitor_interval
        }
    
    async def repair_session_database(self) -> bool:
        """修复会话数据库"""
        try:
            session_file = self.session_path / f"{self.session_name}.session"
            
            if not session_file.exists():
                logger.info("会话文件不存在，无需修复")
                return True
            
            # 尝试修复SQLite数据库
            conn = sqlite3.connect(str(session_file))
            conn.execute("PRAGMA integrity_check")
            conn.close()
            
            logger.info("会话数据库修复完成")
            return True
            
        except Exception as e:
            error_info = self.error_handler.handle_error(e, {
                'operation': 'repair_session_database',
                'session_file': str(session_file)
            })
            logger.error(f"修复会话数据库失败: {error_info}")
            return False
    
    def set_auto_reconnect(self, enabled: bool) -> None:
        """设置自动重连"""
        self.auto_reconnect = enabled
        logger.info(f"自动重连已{'启用' if enabled else '禁用'}")
    
    def set_max_reconnect_attempts(self, attempts: int) -> None:
        """设置最大重连尝试次数"""
        self.max_reconnect_attempts = attempts
        logger.info(f"最大重连尝试次数设置为: {attempts}")
    
    def set_reconnect_delay(self, delay: float) -> None:
        """设置重连延迟"""
        self.reconnect_delay = delay
        logger.info(f"重连延迟设置为: {delay}秒")
    
    async def cleanup(self) -> None:
        """清理资源"""
        try:
            await self.stop()
            
            # 清理临时文件
            temp_files = self.session_path.glob(f"{self.session_name}.*")
            for temp_file in temp_files:
                if temp_file.suffix != '.session':
                    temp_file.unlink()
            
            logger.info("资源清理完成")
            
        except Exception as e:
            error_info = self.error_handler.handle_error(e, {
                'operation': 'cleanup'
            })
            logger.error(f"资源清理失败: {error_info}") 