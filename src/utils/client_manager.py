"""
客户端管理器模块，负责创建和管理Pyrogram客户端
"""

import os
import asyncio
import time
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

# 导入原生的 FloodWait 处理器
try:
    from src.utils.flood_wait_handler import enable_global_flood_wait_handling
    FLOOD_WAIT_HANDLER_AVAILABLE = True
except ImportError:
    FLOOD_WAIT_HANDLER_AVAILABLE = False

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
        
        # 获取会话名称，如果配置中没有则使用默认值
        self.session_name = general_config.get('session_name', session_name)
        
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
        
        # 输出会话名称信息
        logger.info(f"从配置中读取到会话名称: {self.session_name}")
        
        # 检查API凭据是否有效
        if not self.api_id or not self.api_hash:
            error_msg = "配置中的API凭据无效或缺失，请在设置中配置有效的API凭据"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # 获取代理设置
        self.proxy_settings = get_proxy_settings_from_config(self.config)
        logger.debug(f"代理设置: {self.proxy_settings}")
        
        # 初始化FloodWait处理器状态
        self._flood_wait_handler_enabled = False
        self._check_flood_wait_handlers()
    
    def _check_flood_wait_handlers(self):
        """检查可用的FloodWait处理器"""
        if FLOOD_WAIT_HANDLER_AVAILABLE:
            logger.info("使用原生FloodWait处理器")
        else:
            logger.warning("未检测到任何FloodWait处理器，可能影响限流处理能力")
    
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
    
    def _enable_flood_wait_handling(self, client: Client) -> bool:
        """
        为客户端启用FloodWait处理
        
        Args:
            client: Pyrogram客户端实例
            
        Returns:
            bool: 是否成功启用
        """
        success = False
        
        # 使用原生FloodWait处理器
        if FLOOD_WAIT_HANDLER_AVAILABLE:
            try:
                enable_global_flood_wait_handling(client, max_retries=5, base_delay=0.5)
                logger.info("已启用原生FloodWait处理器")
                self._flood_wait_handler_enabled = True
                success = True
            except Exception as e:
                logger.error(f"启用原生FloodWait处理器失败: {e}")
        
        if not success:
            logger.warning("未能启用FloodWait处理器，API调用可能受到限流影响")
        
        return success
    
    def _disable_flood_wait_handling(self, client: Client):
        """
        为客户端禁用FloodWait处理
        
        Args:
            client: Pyrogram客户端实例
        """
        if self._flood_wait_handler_enabled:
            try:
                # 原生处理器暂时没有禁用方法，记录日志即可
                logger.info("原生FloodWait处理器已禁用")
                self._flood_wait_handler_enabled = False
            except Exception as e:
                logger.error(f"禁用FloodWait处理器失败: {e}")

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
                **proxy_args,
                sleep_threshold=0  # 完全禁用Pyrogram内置FloodWait处理，全部交给我们的处理器
            )
            logger.info("客户端创建成功")
            
            # 启用FloodWait处理
            self._enable_flood_wait_handling(self.client)
            
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
            
            # 创建一个启动超时任务
            start_time = time.time()
            timeout_seconds = 15  # 启动超时时间
            

            try:
                # 使用asyncio.wait_for为启动过程添加超时
                await asyncio.wait_for(self.client.start(), timeout=timeout_seconds)
            except asyncio.TimeoutError:
                # 启动超时
                logger.error(f"客户端启动超时 ({timeout_seconds}秒)")
                raise
            except Exception as start_error:
                logger.error(f"客户端启动过程中发生错误: {type(start_error).__name__}: {str(start_error)}")
                raise start_error
            
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
            # 记录错误
            self._record_error(e)
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
                
                # 首先禁用FloodWait处理器
                try:
                    self._disable_flood_wait_handling(self.client)
                except Exception as flood_wait_cleanup_error:
                    logger.warning(f"清理FloodWait处理器时出错: {flood_wait_cleanup_error}")
                
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
                    if self.client:
                        # 先尝试检查客户端是否处于已连接状态
                        is_connected = False
                        try:
                            # 使用hasattr和getattr更安全地检查属性
                            is_connected = getattr(self.client, 'is_connected', False)
                        except Exception as attr_error:
                            logger.debug(f"检查客户端is_connected属性时出错: {attr_error}")
                        
                        if is_connected:
                            # 使用try-except包装断开操作，防止由于disconnect方法内部问题导致的错误
                            try:
                                logger.info("正在断开客户端连接...")
                                await self.client.disconnect()
                                logger.info("客户端已断开连接")
                            except Exception as disconnect_error:
                                logger.warning(f"断开客户端连接时遇到错误 (将忽略): {disconnect_error}")
                        else:
                            # 如果客户端未连接，尝试直接停止客户端
                            logger.info("客户端未连接，尝试直接停止")
                            try:
                                await self.client.stop()
                                logger.info("客户端已停止")
                            except Exception as stop_error:
                                logger.warning(f"停止客户端时遇到错误 (将忽略): {stop_error}")
                except Exception as e:
                    logger.error(f"处理客户端断开连接时出错: {e}")
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
                        # 首先尝试清理FloodWait处理器
                        try:
                            self._disable_flood_wait_handling(self.client)
                        except Exception:
                            pass  # 忽略清理错误
                        
                        # 直接将客户端设为None，不再尝试调用可能导致错误的disconnect方法
                        logger.info("强制重置客户端")
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
            # 确保客户端已经启动
            if not getattr(self.client, 'is_connected', False):
                logger.info("客户端未启动，先启动客户端")
                await self.client.connect()
                logger.info("客户端已连接，准备发送验证码")
            
            sent_code = await self.client.send_code(self.phone_number)
            # 保存phone_code_hash用于后续登录
            self.phone_code_hash = sent_code.phone_code_hash
            logger.info(f"已获取phone_code_hash: {self.phone_code_hash[:4]}...{self.phone_code_hash[-4:]}")
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
            # 确保客户端已经连接
            if not getattr(self.client, 'is_connected', False):
                logger.info("登录前确保客户端已连接")
                await self.client.connect()
                logger.info("客户端已连接，准备登录")
            
            # 检查是否有phone_code_hash
            if not hasattr(self, 'phone_code_hash') or not self.phone_code_hash:
                logger.error("登录错误：缺少phone_code_hash，请先发送验证码")
                raise ValueError("缺少phone_code_hash，请先发送验证码")
            
            # 尝试用验证码登录
            logger.info(f"正在使用验证码登录：{self.phone_number}")
            signed_in = await self.client.sign_in(
                phone_number=self.phone_number, 
                phone_code_hash=self.phone_code_hash, 
                phone_code=code
            )
            logger.info("验证码验证成功")
            
            # 清除临时存储的phone_code_hash
            self.phone_code_hash = None
            
            # 更新用户信息
            self.me = await self.client.get_me()
            self.is_authorized = True
            
            # 显示用户信息
            user_info = f"{self.me.first_name}"
            if self.me.last_name:
                user_info += f" {self.me.last_name}"
            user_info += f" (@{self.me.username})" if self.me.username else ""
            logger.info(f"登录成功：{user_info}")
            
            # 发出信号
            self.connection_status_changed.emit(True, self.me)
            
            return signed_in
            
        except SessionPasswordNeeded:
            # 如果启用了两步验证，尝试用密码登录
            logger.info("检测到需要两步验证密码")
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
        
        # 尝试发送一个简单的API请求来检查连接状态，添加重试机制
        max_retries = 2
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                # 增加超时时间到10秒，给网络更多时间
                me = await asyncio.wait_for(self.client.get_me(), timeout=10.0)
                
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
                last_error = e
                if attempt < max_retries:
                    logger.debug(f"连接检查失败，正在重试 ({attempt + 1}/{max_retries}): {e}")
                    await asyncio.sleep(1)  # 短暂等待后重试
                    continue
                else:
                    # 所有重试都失败，跳出循环处理错误
                    break
        
        # 所有重试都失败，处理连接断开
        # 记录错误到历史
        if last_error:
            self._record_error(last_error)
        
        # 连接错误，记录日志
        error_name = type(last_error).__name__ if last_error else "Unknown"
        error_detail = str(last_error) if last_error else "连接检查失败"
        
        if self.connection_active:
            # 状态从已连接变为未连接，需要更新UI
            logger.error(f"客户端连接检查失败: {error_name}: {error_detail}")
            
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
                if not hasattr(self, '_last_error_str') or self._last_error_str != str(last_error):
                    logger.error(f"客户端连接已断开，尝试重新连接: {error_detail}")
                    # 记录当前错误，用于后续比较
                    self._last_error_str = str(last_error)
                
                # 尝试重连
                await self.reconnect_if_needed()
        
        return False 