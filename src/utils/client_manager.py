"""
客户端管理器模块，负责创建和管理Pyrogram客户端
"""

import os
import asyncio
from typing import Optional, Dict, Any, Union
from PySide6.QtCore import QObject, Signal

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

class ClientManager(QObject):
    """
    Pyrogram客户端管理器
    负责创建、初始化和管理Telegram客户端连接
    """
    
    # 添加信号
    connection_status_changed = Signal(bool, object)  # 连接状态，用户信息
    
    def __init__(self, ui_config_manager: UIConfigManager, session_name: str = "tg_manager"):
        """
        初始化客户端管理器
        
        Args:
            ui_config_manager: UI配置管理器实例，用于加载API凭据
            session_name: 会话名称，默认为"tg_manager"
        """
        super().__init__()  # 调用QObject的初始化
        self.ui_config_manager = ui_config_manager
        self.session_name = session_name
        self.client = None
        self.me = None  # 用户信息
        self.is_authorized = False
        self.connection_active = False
        
        # 添加错误追踪列表，记录最近的10个错误
        self.recent_errors = []
        self.max_error_history = 10
        
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
    
    def _record_error(self, error):
        """
        记录错误到最近错误列表
        
        Args:
            error: 错误对象
        """
        # 将新错误添加到列表开头
        self.recent_errors.insert(0, error)
        
        # 如果列表超过最大长度，移除最旧的错误
        if len(self.recent_errors) > self.max_error_history:
            self.recent_errors.pop()
        
        # 记录到日志
        logger.debug(f"错误已记录到历史: {error}")
    
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
        
        # 获取最新的代理设置
        if not hasattr(self, 'proxy_settings') or self.proxy_settings is None:
            # 如果没有代理设置或需要刷新，重新加载配置
            ui_config = self.ui_config_manager.get_ui_config()
            self.config = convert_ui_config_to_dict(ui_config)
            self.proxy_settings = get_proxy_settings_from_config(self.config)
        
        # 设置代理参数
        proxy_args = {}
        if self.proxy_settings:
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
            
            # 发出信号
            self.connection_status_changed.emit(True, self.me)
            
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
                logger.info("正在停止客户端...")
                
                # 安全获取当前任务
                try:
                    # 获取当前任务
                    current_task = asyncio.current_task()
                    
                    # 安全地获取所有任务
                    try:
                        all_tasks = asyncio.all_tasks()
                    except RuntimeError:
                        # 如果无法获取所有任务，使用空列表
                        logger.warning("无法获取所有任务，跳过任务取消")
                        all_tasks = []
                    
                    # 尝试停止客户端的所有相关任务
                    for task in all_tasks:
                        if task is current_task:
                            continue
                            
                        task_name = task.get_name()
                        # 寻找与pyrogram相关的任务
                        if ('pyrogram' in task_name.lower() or 'client' in task_name.lower()) and not task.done() and not task.cancelled():
                            logger.info(f"尝试取消未完成的客户端任务: {task_name}")
                            task.cancel()
                except RuntimeError as e:
                    logger.warning(f"获取任务时遇到事件循环错误: {e}")
                except Exception as e:
                    logger.warning(f"取消客户端任务时出错: {e}")
                
                # 直接调用客户端的disconnect方法，而不使用stop
                # 这避免了客户端内部的asyncio.gather调用
                try:
                    if hasattr(self.client, 'disconnect'):
                        await self.client.disconnect()
                        logger.info("客户端已断开连接")
                    else:
                        # 如果没有disconnect方法，尝试使用stop
                        await self.client.stop()
                        logger.info("客户端已停止")
                except Exception as e:
                    logger.error(f"停止客户端时出错: {e}")
                    # 客户端可能已经断开，继续执行
                
                # 释放对客户端的引用
                old_client = self.client
                self.client = None
                self.is_authorized = False
                self.connection_active = False
                
                # 额外步骤：尝试关闭会话数据库连接
                try:
                    if hasattr(old_client, 'storage') and hasattr(old_client.storage, 'conn'):
                        if old_client.storage.conn:
                            old_client.storage.conn.close()
                            logger.info("会话数据库连接已关闭")
                            
                    # 显式设置为None以帮助垃圾回收
                    old_client = None
                    # 强制垃圾回收
                    import gc
                    gc.collect()
                except Exception as db_error:
                    logger.warning(f"关闭会话数据库连接时出错: {db_error}")
                
                logger.info("客户端连接状态已重置")
                
                # 发出信号
                self.connection_status_changed.emit(False, None)
                
                return True
            except Exception as e:
                logger.error(f"停止客户端时出错: {e}")
                # 尝试强制停止客户端
                try:
                    if self.client:
                        if hasattr(self.client, 'disconnect'):
                            await self.client.disconnect()
                        self.client = None
                        self.is_authorized = False
                        self.connection_active = False
                        logger.info("客户端已强制断开连接")
                        
                        # 发出信号
                        self.connection_status_changed.emit(False, None)
                except Exception as forced_stop_error:
                    logger.error(f"强制停止客户端时出错: {forced_stop_error}")
                return False
        return True
    
    async def restart_client(self):
        """
        重启客户端
        
        Returns:
            Client: 重启后的客户端实例
        """
        logger.info("开始重启客户端...")
        
        # 先发送未连接状态信号，确保UI立即更新
        self.connection_active = False
        self.connection_status_changed.emit(False, None)
        
        # 停止当前客户端
        await self.stop_client()
        
        # 重新加载配置，以获取最新的代理设置
        ui_config = self.ui_config_manager.get_ui_config()
        self.config = convert_ui_config_to_dict(ui_config)
        self.proxy_settings = get_proxy_settings_from_config(self.config)
        
        # 获取代理信息用于日志
        if self.proxy_settings and 'proxy' in self.proxy_settings and 'hostname' in self.proxy_settings['proxy']:
            proxy_info = f"{self.proxy_settings['proxy'].get('scheme', '')}://{self.proxy_settings['proxy'].get('hostname', '')}:{self.proxy_settings['proxy'].get('port', '')}"
            logger.info(f"重启客户端使用代理: {proxy_info}")
        
        try:
            # 启动新的客户端
            client = await self.start_client()
            return client
        except Exception as e:
            # 检查是否是数据库锁定错误
            if "database is locked" in str(e).lower():
                logger.error(f"重启客户端失败，数据库被锁定: {e}")
                
                # 尝试修复数据库锁定问题
                if await self._fix_locked_session():
                    # 再次尝试启动客户端
                    logger.info("会话数据库已重置，重新尝试启动客户端...")
                    try:
                        client = await self.start_client()
                        return client
                    except Exception as retry_error:
                        logger.error(f"修复数据库后重启客户端仍然失败: {retry_error}")
            
            # 如果启动失败，确保发送未连接状态信号
            self.connection_active = False
            self.connection_status_changed.emit(False, None)
            logger.error(f"重启客户端失败: {e}")
            raise
    
    async def _fix_locked_session(self):
        """
        尝试修复被锁定的会话数据库
        
        Returns:
            bool: 是否成功修复
        """
        import os
        import shutil
        import time
        
        session_path = f"sessions/{self.session_name}.session"
        if not os.path.exists(session_path):
            logger.warning(f"会话文件不存在: {session_path}")
            return False
        
        try:
            # 创建备份目录
            backup_dir = "sessions/backups"
            os.makedirs(backup_dir, exist_ok=True)
            
            # 创建带时间戳的备份文件名
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_path = f"{backup_dir}/{self.session_name}_{timestamp}.session.bak"
            
            # 备份当前会话文件
            shutil.copy2(session_path, backup_path)
            logger.info(f"已备份会话文件: {backup_path}")
            
            # 删除当前会话文件
            os.remove(session_path)
            logger.info(f"已删除被锁定的会话文件: {session_path}")
            
            # 可能的-wal和-shm文件也需要删除
            for ext in ['-wal', '-shm']:
                wal_path = f"{session_path}{ext}"
                if os.path.exists(wal_path):
                    os.remove(wal_path)
                    logger.info(f"已删除会话相关文件: {wal_path}")
            
            # 强制执行垃圾回收
            import gc
            gc.collect()
            
            # 暂停一下，给系统时间释放文件锁
            await asyncio.sleep(1)
            
            return True
        except Exception as e:
            logger.error(f"修复会话数据库时出错: {e}")
            return False
    
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
            
            # 发出信号
            self.connection_status_changed.emit(True, self.me)
            
            return signed_in
            
        except SessionPasswordNeeded:
            # 如果启用了两步验证，尝试用密码登录
            if password:
                try:
                    signed_in = await self.client.check_password(password)
                    # 更新用户信息
                    self.me = await self.client.get_me()
                    self.is_authorized = True
                    
                    # 发出信号
                    self.connection_status_changed.emit(True, self.me)
                    
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
    
    async def reconnect_if_needed(self):
        """
        如果需要重连且冷却期已过，执行重连操作
        
        Returns:
            bool: 重连是否成功
        """
        # 检查是否可以尝试重连
        current_time = asyncio.get_event_loop().time()
        next_reconnect_time = getattr(self, '_next_reconnect_time', 0)
        
        # 如果还在冷却期内，直接返回
        if current_time < next_reconnect_time:
            cooldown_left = int(next_reconnect_time - current_time)
            logger.debug(f"重连冷却中，剩余 {cooldown_left} 秒")
            return False
        
        # 正在重连中，避免重复重连
        if getattr(self, '_reconnecting', False):
            logger.debug("重连已在进行中，跳过此次重连")
            return False
        
        # 标记正在重连
        self._reconnecting = True
        
        try:
            logger.info("开始执行自动重连...")
            
            # 如果是数据库锁定问题，尝试修复
            is_db_locked = any("database is locked" in str(err).lower() for err in self.recent_errors)
            if is_db_locked and not getattr(self, '_db_fix_attempted', False):
                # 标记已尝试修复，避免反复修复
                self._db_fix_attempted = True
                if await self._fix_locked_session():
                    logger.info("会话数据库已重置，将重新启动客户端")
            
            # 重新从配置中获取代理设置
            ui_config = self.ui_config_manager.get_ui_config()
            self.config = convert_ui_config_to_dict(ui_config)
            self.proxy_settings = get_proxy_settings_from_config(self.config)
            
            # 重新启动客户端
            await self.restart_client()
            
            # 重置标记
            self._db_fix_attempted = False
            self._reconnecting = False
            
            # 重新计算下次重连时间（如果再次断开）
            # 重置重连尝试次数
            self._reconnect_attempts = 0
            
            logger.info("客户端自动重连成功")
            return True
        except Exception as reconnect_error:
            # 记录重连错误
            self._record_error(reconnect_error)
            
            # 更新下次重连时间
            cooldown = min(300, 30 * (2 ** (getattr(self, '_reconnect_attempts', 1))))
            self._next_reconnect_time = asyncio.get_event_loop().time() + cooldown
            
            # 重置标记
            self._reconnecting = False
            
            if "database is locked" in str(reconnect_error).lower():
                logger.error(f"客户端自动重连失败 (数据库锁定)，将在 {cooldown} 秒后重试: {reconnect_error}")
            else:
                logger.error(f"客户端自动重连失败，将在 {cooldown} 秒后重试: {reconnect_error}")
            
            return False
            
    async def check_connection_status(self) -> bool:
        """
        检查客户端连接状态
        
        Returns:
            bool: 是否连接正常
        """
        # 如果客户端为None，肯定是未连接状态
        if not self.client:
            if self.connection_active:
                self.connection_active = False
                # 如果之前是连接状态，发出断开连接信号
                self.connection_status_changed.emit(False, None)
                logger.info("检测到客户端已断开连接")
            elif self.config.get('GENERAL', {}).get('auto_restart_session', True):
                # 尝试重连
                await self.reconnect_if_needed()
            return False
        
        # 尝试发送一个简单的API请求来检查连接状态
        try:
            # 使用get_me()方法测试连接，但添加超时限制避免阻塞
            # 使用asyncio.wait_for为get_me操作添加3秒超时
            try:
                me = await asyncio.wait_for(self.client.get_me(), timeout=3.0)
            except asyncio.TimeoutError:
                # 如果超时，视为连接已断开
                raise ConnectionError("连接检查超时，可能是代理问题或网络不畅")
            
            # 连接正常
            if not self.connection_active:
                # 只有状态变化时才发出信号
                self.connection_active = True
                self.connection_status_changed.emit(True, me)
                # 只有当状态从未连接变为已连接时，才输出日志
                logger.info("检测到客户端已连接")
                
                # 重置重连计数和冷却时间
                if hasattr(self, '_reconnect_attempts'):
                    self._reconnect_attempts = 0
                if hasattr(self, '_reconnect_cooldown'):
                    self._reconnect_cooldown = 0
            # 如果已经是连接状态，只是更新成功，不输出日志，保持静默
            return True
        except Exception as e:
            # 记录错误到历史
            self._record_error(e)
            
            # 连接错误，记录日志
            error_name = type(e).__name__
            error_detail = str(e)
            
            # 检查是否是数据库锁定错误
            is_db_locked = "database is locked" in str(e).lower()
            
            # 检查是否是代理连接问题
            is_proxy_error = any(keyword in str(e).lower() for keyword in ['proxy', 'sock', 'connect', 'network', 'timeout', '拒绝', 'refuse', 'reset', 'error'])
            
            if self.connection_active:
                # 状态从已连接变为未连接，需要更新UI
                # 记录所有错误类型，包括网络错误、连接错误、API错误等
                if is_db_locked:
                    logger.error(f"检测到会话数据库锁定: {error_name}: {error_detail}")
                elif is_proxy_error:
                    logger.error(f"检测到代理连接问题: {error_name}: {error_detail}")
                else:
                    logger.error(f"Telegram客户端连接检查失败: {error_name}: {error_detail}")
                
                # 发出断开连接信号
                self.connection_active = False
                self.connection_status_changed.emit(False, None)
                logger.info("检测到客户端已断开连接")
                
                # 检查是否需要自动重连
                if self.config.get('GENERAL', {}).get('auto_restart_session', True):
                    # 初始化重连尝试次数
                    if not hasattr(self, '_reconnect_attempts'):
                        self._reconnect_attempts = 0
                    
                    # 增加重连尝试次数
                    self._reconnect_attempts += 1
                    
                    # 根据重连次数增加冷却时间（指数退避）
                    cooldown = min(300, 30 * (2 ** (self._reconnect_attempts - 1)))  # 最大5分钟
                    
                    # 记录下次可以重连的时间
                    current_time = asyncio.get_event_loop().time()
                    self._next_reconnect_time = current_time + cooldown
                    
                    logger.info(f"将在 {cooldown} 秒后尝试自动重连 (尝试次数: {self._reconnect_attempts})")
            else:
                # 已经是断开状态，尝试重连
                if self.config.get('GENERAL', {}).get('auto_restart_session', True):
                    # 避免在日志中重复报告相同的错误
                    if not hasattr(self, '_last_error_str') or self._last_error_str != str(e):
                        if is_db_locked:
                            logger.error(f"会话数据库锁定，尝试重新连接: {error_detail}")
                        elif is_proxy_error:
                            logger.error(f"代理连接问题，尝试重新连接: {error_detail}")
                        else:
                            logger.error(f"客户端连接已断开，尝试重新连接: {error_detail}")
                        # 记录当前错误，用于后续比较
                        self._last_error_str = str(e)
                    
                    # 尝试重连
                    await self.reconnect_if_needed()
            
            return False 