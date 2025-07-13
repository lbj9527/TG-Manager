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
        self.session_path = Path(config.get('session_path', 'sessions'))
        
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
            session_file = self.session_path / f"{self.session_name}.session"
            
            self.client = Client(
                name=str(session_file),
                api_id=self.api_id,
                api_hash=self.api_hash,
                workdir=str(self.session_path),
                no_updates=True
            )
            
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
            
        except Exception as e:
            error_info = self.error_handler.handle_error(e, {
                'operation': 'first_login',
                'session_name': self.session_name
            })
            logger.error(f"首次登录失败: {error_info}")
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
    
    async def _handle_connection_loss(self) -> None:
        """处理连接丢失"""
        logger.warning("检测到连接丢失")
        
        self.is_connected = False
        
        if self.event_bus:
            self.event_bus.emit('client.connection_lost', {
                'timestamp': time.time(),
                'session_name': self.session_name
            })
        
        if self.auto_reconnect:
            await self._attempt_reconnect()
    
    async def _attempt_reconnect(self) -> None:
        """尝试重连"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"重连次数已达上限 ({self.max_reconnect_attempts})")
            return
        
        self.reconnect_attempts += 1
        logger.info(f"尝试重连 ({self.reconnect_attempts}/{self.max_reconnect_attempts})")
        
        try:
            await asyncio.sleep(self.reconnect_delay)
            
            if await self._restore_session():
                logger.info("重连成功")
                self.reconnect_attempts = 0
            else:
                logger.warning("重连失败，将继续尝试")
                
        except Exception as e:
            error_info = self.error_handler.handle_error(e, {
                'operation': 'attempt_reconnect',
                'attempt': self.reconnect_attempts
            })
            logger.error(f"重连过程中出错: {error_info}")
    
    async def check_connection_status_now(self) -> bool:
        """立即检查连接状态"""
        try:
            if not self.client:
                return False
            
            # 尝试获取用户信息来检查连接
            await self.client.get_me()
            
            if not self.is_connected:
                self.is_connected = True
                logger.info("连接已恢复")
                
                if self.event_bus:
                    self.event_bus.emit('client.connection_restored', {
                        'timestamp': time.time(),
                        'session_name': self.session_name
                    })
            
            return True
            
        except Exception as e:
            error_info = self.error_handler.handle_error(e, {
                'operation': 'check_connection_status'
            })
            logger.error(f"检查连接状态失败: {error_info}")
            
            if self.is_connected:
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
            self.is_running = False
            self.is_connected = False
            self.is_authenticated = False
            
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
            self.is_authenticated
        )
    
    def get_status(self) -> Dict[str, Any]:
        """获取客户端状态"""
        user_info = {}
        if self.user:
            user_info = {
                'id': self.user.id,
                'username': self.user.username,
                'first_name': self.user.first_name,
                'last_name': self.user.last_name,
                'phone_number': self.user.phone_number
            }
        
        return {
            'is_connected': self.is_connected,
            'is_authenticated': self.is_authenticated,
            'is_running': self.is_running,
            'auto_reconnect': self.auto_reconnect,
            'reconnect_attempts': self.reconnect_attempts,
            'max_reconnect_attempts': self.max_reconnect_attempts,
            'session_name': self.session_name,
            'user': user_info
        }
    
    async def repair_session_database(self) -> bool:
        """修复会话数据库"""
        try:
            session_file = self.session_path / f"{self.session_name}.session"
            
            if session_file.exists():
                logger.info("删除损坏的会话文件...")
                session_file.unlink()
                return True
            else:
                logger.info("会话文件不存在，无需修复")
                return True
                
        except Exception as e:
            error_info = self.error_handler.handle_error(e, {
                'operation': 'repair_session_database',
                'session_name': self.session_name
            })
            logger.error(f"修复会话数据库失败: {error_info}")
            return False
    
    def set_auto_reconnect(self, enabled: bool) -> None:
        """设置自动重连"""
        self.auto_reconnect = enabled
        logger.info(f"自动重连已{'启用' if enabled else '禁用'}")
    
    def set_max_reconnect_attempts(self, attempts: int) -> None:
        """设置最大重连次数"""
        self.max_reconnect_attempts = attempts
        logger.info(f"最大重连次数设置为: {attempts}")
    
    def set_reconnect_delay(self, delay: float) -> None:
        """设置重连延迟"""
        self.reconnect_delay = delay
        logger.info(f"重连延迟设置为: {delay}秒")
    
    async def cleanup(self) -> None:
        """清理资源"""
        try:
            logger.info("清理客户端管理器资源...")
            
            await self.stop()
            
            logger.info("客户端管理器资源清理完成")
            
        except Exception as e:
            error_info = self.error_handler.handle_error(e, {
                'operation': 'cleanup_client_manager'
            })
            logger.error(f"清理客户端管理器资源失败: {error_info}") 