"""
强壮Telegram客户端 - 核心客户端类
整合配置管理、连接管理、异常处理、请求队列等所有模块
"""

import asyncio
import os
from typing import Dict, Any, Optional, Callable, Union
from pyrogram import Client
from pyrogram.types import User
from PySide6.QtCore import QObject, Signal

from src.utils.logger import get_logger
from .config_manager import ClientConfigManager, ProxyConfig, ConnectionConfig, ClientConfig
from .connection_manager import ConnectionManager, ConnectionState, ConnectionMetrics
from .exception_handler import RobustExceptionHandler, ExceptionInfo, ExceptionCategory
from .request_queue import RequestQueueManager, RequestPriority, RequestType

logger = get_logger()


class RobustTelegramClient(QObject):
    """强壮的Telegram客户端"""
    
    # Qt信号定义
    connection_status_changed = Signal(bool, object)  # 连接状态，用户信息
    time_sync_error = Signal(str)  # 时间同步错误信号
    authentication_required = Signal(str)  # 需要认证信号
    error_occurred = Signal(str, str)  # 错误信号（类型，消息）
    
    def __init__(self, config_path: str = "config.json"):
        """
        初始化强壮Telegram客户端
        
        Args:
            config_path: 配置文件路径
        """
        super().__init__()
        
        # 初始化配置管理器
        self.config_manager = ClientConfigManager(config_path)
        if not self.config_manager.validate_config():
            raise ValueError("配置验证失败，无法创建客户端")
        
        # 获取各种配置
        self.proxy_config = self.config_manager.get_proxy_config()
        self.connection_config = self.config_manager.get_connection_config()
        self.client_config = self.config_manager.get_client_config()
        
        # 初始化连接管理器
        self.connection_manager = ConnectionManager(self.connection_config)
        self._setup_connection_callbacks()
        
        # 初始化异常处理器
        self.exception_handler = RobustExceptionHandler(
            max_retries=self.connection_config.max_retries
        )
        self._setup_exception_callbacks()
        
        # 初始化请求队列管理器
        self.request_queue = RequestQueueManager(
            max_concurrent_requests=self.client_config.max_concurrent_requests,
            default_timeout=self.connection_config.timeout
        )
        
        # Pyrogram客户端实例
        self.client: Optional[Client] = None
        self.me: Optional[User] = None
        self.is_authorized = False
        
        # 会话信息
        self.session_name = self.client_config.session_name
        self.phone_code_hash: Optional[str] = None
        
        # 控制标志
        self._is_stopping = False
        
        logger.info(f"强壮Telegram客户端已初始化 (会话: {self.session_name})")
        if self.config_manager.is_proxy_enabled():
            logger.info(f"代理已启用: {self.proxy_config.proxy_type.value}://{self.proxy_config.host}:{self.proxy_config.port}")
    
    def _setup_connection_callbacks(self):
        """设置连接管理器回调"""
        self.connection_manager.on_state_changed = self._on_connection_state_changed
        self.connection_manager.on_connection_lost = self._on_connection_lost
        self.connection_manager.on_connection_restored = self._on_connection_restored
    
    def _setup_exception_callbacks(self):
        """设置异常处理器回调"""
        self.exception_handler.on_user_intervention_required = self._on_user_intervention_required
        self.exception_handler.on_reconnection_required = self._on_reconnection_required
    
    def _on_connection_state_changed(self, new_state: ConnectionState):
        """连接状态变化回调"""
        logger.debug(f"连接状态变化: {new_state.value}")
        
        if new_state == ConnectionState.CONNECTED:
            self.connection_status_changed.emit(True, self.me)
        elif new_state == ConnectionState.DISCONNECTED:
            self.connection_status_changed.emit(False, None)
    
    def _on_connection_lost(self, error: Exception):
        """连接丢失回调"""
        logger.warning(f"连接丢失: {error}")
        
        # 如果应该自动重连，启动重连
        if self.connection_config.auto_restart_session and not self._is_stopping:
            asyncio.create_task(self._handle_auto_reconnect())
    
    def _on_connection_restored(self):
        """连接恢复回调"""
        logger.info("连接已恢复")
    
    def _on_user_intervention_required(self, exception_info: ExceptionInfo):
        """用户干预需求回调"""
        if exception_info.category == ExceptionCategory.TIME_SYNC_ERROR:
            self.time_sync_error.emit(exception_info.user_message or "时间同步错误")
        elif exception_info.category == ExceptionCategory.AUTH_ERROR:
            self.authentication_required.emit(exception_info.user_message or "需要重新认证")
        else:
            self.error_occurred.emit(
                exception_info.category.value,
                exception_info.user_message or "需要用户干预"
            )
    
    def _on_reconnection_required(self, exception_info: ExceptionInfo):
        """重连需求回调"""
        if not self._is_stopping:
            asyncio.create_task(self._handle_auto_reconnect())
    
    async def _handle_auto_reconnect(self):
        """处理自动重连"""
        try:
            logger.info("开始自动重连...")
            await self.restart_client()
            logger.info("自动重连成功")
        except Exception as e:
            logger.error(f"自动重连失败: {e}")
    
    async def create_client(self) -> Client:
        """
        创建Pyrogram客户端实例
        
        Returns:
            Client: Pyrogram客户端实例
        """
        if self.client:
            return self.client
        
        # 创建会话目录
        os.makedirs("sessions", exist_ok=True)
        
        # 获取客户端参数
        client_kwargs = self.config_manager.get_pyrogram_client_kwargs()
        
        # 创建客户端
        self.client = Client(**client_kwargs)
        logger.info("Pyrogram客户端已创建")
        
        return self.client
    
    async def start_client(self) -> Client:
        """
        启动客户端
        
        Returns:
            Client: 已启动的客户端实例
        """
        if not self.client:
            await self.create_client()
        
        # 启动请求队列
        await self.request_queue.start()
        
        # 设置连接状态
        self.connection_manager.set_state(ConnectionState.CONNECTING)
        
        try:
            # 使用异常处理执行启动
            await self._execute_with_retry(
                self.client.start,
                context="client_start",
                priority=RequestPriority.CRITICAL,
                request_type=RequestType.AUTH
            )
            
            # 获取用户信息
            self.me = await self._execute_with_retry(
                self.client.get_me,
                context="get_me",
                priority=RequestPriority.CRITICAL,
                request_type=RequestType.USER
            )
            
            self.is_authorized = True
            
            # 通知连接成功
            await self.connection_manager.notify_connection_success()
            
            # 显示用户信息
            user_info = self._format_user_info(self.me)
            logger.info(f"客户端已启动：{user_info}")
            
            return self.client
            
        except Exception as e:
            # 处理启动错误
            await self.exception_handler.handle_exception(e, "client_start")
            self.connection_manager.set_state(ConnectionState.ERROR)
            raise
    
    async def stop_client(self) -> bool:
        """
        停止客户端
        
        Returns:
            bool: 是否成功停止
        """
        self._is_stopping = True
        
        try:
            # 停止连接管理器
            await self.connection_manager.stop()
            
            # 停止请求队列
            await self.request_queue.stop()
            
            # 停止Pyrogram客户端
            if self.client:
                try:
                    if hasattr(self.client, 'is_connected') and self.client.is_connected:
                        await self.client.disconnect()
                    else:
                        await self.client.stop()
                except Exception as e:
                    logger.warning(f"停止客户端时出错: {e}")
                
                self.client = None
            
            # 重置状态
            self.me = None
            self.is_authorized = False
            self.phone_code_hash = None
            
            logger.info("客户端已停止")
            return True
            
        except Exception as e:
            logger.error(f"停止客户端时出错: {e}")
            return False
        finally:
            self._is_stopping = False
    
    async def restart_client(self):
        """重启客户端"""
        logger.info("开始重启客户端...")
        
        # 先停止
        await self.stop_client()
        
        # 重新加载配置
        self.config_manager.load_config()
        
        # 重新启动
        await self.start_client()
        
        logger.info("客户端重启完成")
    
    async def send_code(self, phone_number: str = None) -> tuple:
        """
        发送验证码
        
        Args:
            phone_number: 电话号码，可选
            
        Returns:
            tuple: (电话号码, 验证码类型)
        """
        if not self.client:
            await self.create_client()
        
        if phone_number:
            self.client.phone_number = phone_number
            # 更新配置中的电话号码
            self.config_manager.update_config('GENERAL', 'phone_number', phone_number)
        
        phone = self.client.phone_number or self.client_config.phone_number
        if not phone:
            raise ValueError("未提供电话号码")
        
        try:
            # 确保请求队列已启动
            if not self.request_queue._running:
                await self.request_queue.start()
            
            # 确保客户端已连接
            if not getattr(self.client, 'is_connected', False):
                await self.client.connect()
            
            # 发送验证码
            sent_code = await self._execute_with_retry(
                self.client.send_code,
                phone,
                context="send_code",
                priority=RequestPriority.CRITICAL,
                request_type=RequestType.AUTH
            )
            
            self.phone_code_hash = sent_code.phone_code_hash
            logger.info(f"验证码已发送到: {phone}")
            
            return phone, sent_code.type
            
        except Exception as e:
            logger.error(f"发送验证码失败: {e}")
            await self.exception_handler.handle_exception(e, "send_code")
            raise
    
    async def sign_in(self, code: str, password: str = None) -> User:
        """
        使用验证码登录
        
        Args:
            code: 验证码
            password: 两步验证密码（如果需要）
            
        Returns:
            User: 用户信息
        """
        if not self.client:
            await self.create_client()
        
        if not self.phone_code_hash:
            raise ValueError("缺少phone_code_hash，请先发送验证码")
        
        try:
            # 确保请求队列已启动
            if not self.request_queue._running:
                await self.request_queue.start()
            
            # 确保客户端已连接
            if not getattr(self.client, 'is_connected', False):
                await self.client.connect()
            
            phone = self.client.phone_number or self.client_config.phone_number
            
            # 尝试用验证码登录
            try:
                signed_in = await self._execute_with_retry(
                    self.client.sign_in,
                    phone_number=phone,
                    phone_code_hash=self.phone_code_hash,
                    phone_code=code,
                    context="sign_in",
                    priority=RequestPriority.CRITICAL,
                    request_type=RequestType.AUTH
                )
            except Exception as e:
                # 检查是否需要两步验证
                if "SessionPasswordNeeded" in str(e) or "password" in str(e).lower():
                    if password:
                        signed_in = await self._execute_with_retry(
                            self.client.check_password,
                            password,
                            context="check_password",
                            priority=RequestPriority.CRITICAL,
                            request_type=RequestType.AUTH
                        )
                    else:
                        raise ValueError("需要两步验证密码")
                else:
                    raise
            
            # 清除临时数据
            self.phone_code_hash = None
            
            # 获取用户信息
            self.me = await self._execute_with_retry(
                self.client.get_me,
                context="get_me_after_login",
                priority=RequestPriority.CRITICAL,
                request_type=RequestType.USER
            )
            
            self.is_authorized = True
            
            # 启动请求队列（如果还未启动）
            if not self.request_queue._running:
                await self.request_queue.start()
            
            # 通知连接成功
            await self.connection_manager.notify_connection_success()
            
            user_info = self._format_user_info(self.me)
            logger.info(f"登录成功：{user_info}")
            
            return signed_in
            
        except Exception as e:
            logger.error(f"登录失败: {e}")
            await self.exception_handler.handle_exception(e, "sign_in")
            raise
    
    async def sign_out(self) -> bool:
        """
        注销登录
        
        Returns:
            bool: 是否成功注销
        """
        logout_api_success = False
        
        try:
            # 尝试通过API注销（如果客户端仍然可用）
            if self.client and self.is_authorized:
                try:
                    # 检查客户端是否仍然可用
                    if hasattr(self.client, 'is_connected') and getattr(self.client, 'is_connected', False):
                        # 客户端仍然连接，尝试API注销
                        await self._execute_with_retry(
                            self.client.log_out,
                            context="sign_out",
                            priority=RequestPriority.HIGH,
                            request_type=RequestType.AUTH,
                            max_retries=2,  # 减少重试次数
                            timeout=10.0   # 设置较短的超时
                        )
                        logout_api_success = True
                        logger.info("已通过API成功注销登录")
                    else:
                        logger.info("客户端已断开连接，跳过API注销，直接进行本地清理")
                        
                except Exception as logout_error:
                    # API注销失败，记录错误但继续进行本地清理
                    error_msg = str(logout_error)
                    if "already terminated" in error_msg or "not connected" in error_msg:
                        logger.info("客户端已终止，跳过API注销，继续进行本地清理")
                    else:
                        logger.warning(f"API注销失败，继续进行本地清理: {logout_error}")
            else:
                logger.info("客户端未初始化或未授权，直接进行本地清理")
            
        except Exception as e:
            logger.warning(f"注销过程中出现错误，继续进行清理: {e}")
        
        try:
            # 停止客户端（无论API注销是否成功）
            await self.stop_client()
            
            # 等待一小段时间确保客户端完全停止
            await asyncio.sleep(0.5)
            
            # 删除所有会话相关文件
            session_path = f"sessions/{self.session_name}.session"
            session_files_to_delete = [
                session_path,
                f"{session_path}-wal",
                f"{session_path}-shm"
            ]
            
            deleted_files = []
            for file_path in session_files_to_delete:
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        deleted_files.append(file_path)
                        logger.info(f"已删除会话文件: {file_path}")
                    except Exception as delete_error:
                        logger.warning(f"删除会话文件失败: {file_path}, 错误: {delete_error}")
            
            # 清理内部状态
            self.is_authorized = False
            self.me = None
            
            # 记录注销结果
            if deleted_files:
                if logout_api_success:
                    logger.info(f"注销完全成功，共删除 {len(deleted_files)} 个会话文件")
                else:
                    logger.info(f"本地注销成功，共删除 {len(deleted_files)} 个会话文件（API注销被跳过）")
            else:
                if logout_api_success:
                    logger.info("API注销成功，未发现需要删除的本地会话文件")
                else:
                    logger.info("本地注销成功，未发现需要删除的会话文件（API注销被跳过）")
            
            return True
            
        except Exception as e:
            logger.error(f"本地清理失败: {e}")
            return False
    
    async def check_connection_status(self) -> bool:
        """
        检查连接状态
        
        Returns:
            bool: 是否连接正常
        """
        if not self.client or not self.is_authorized:
            return False
        
        try:
            # 尝试获取用户信息来检查连接
            await self._execute_with_retry(
                self.client.get_me,
                context="connection_check",
                priority=RequestPriority.LOW,
                request_type=RequestType.USER,
                max_retries=1,
                timeout=10.0
            )
            
            if not self.connection_manager.is_connected():
                await self.connection_manager.notify_connection_success()
            
            return True
            
        except Exception as e:
            logger.debug(f"连接检查失败: {e}")
            await self.connection_manager.handle_connection_lost(e)
            return False
    
    async def _execute_with_retry(self, func, *args, context: str = "unknown", 
                                priority: RequestPriority = RequestPriority.NORMAL,
                                request_type: RequestType = RequestType.MESSAGE,
                                max_retries: int = None, timeout: float = None, **kwargs):
        """
        带重试机制执行函数
        
        Args:
            func: 要执行的函数
            *args: 函数参数
            context: 上下文信息
            priority: 请求优先级
            request_type: 请求类型
            max_retries: 最大重试次数
            timeout: 超时时间
            **kwargs: 函数关键字参数
            
        Returns:
            执行结果
        """
        max_retries = max_retries or self.connection_config.max_retries
        timeout = timeout or self.connection_config.timeout
        
        for attempt in range(max_retries + 1):
            try:
                # 通过请求队列执行
                return await self.request_queue.execute_request(
                    func, *args,
                    priority=priority,
                    request_type=request_type,
                    timeout=timeout,
                    max_retries=0,  # 我们在这里处理重试
                    context=context,
                    **kwargs
                )
                
            except Exception as e:
                logger.debug(f"执行失败 (尝试 {attempt + 1}/{max_retries + 1}): {e}")
                
                # 使用异常处理器处理
                should_retry = await self.exception_handler.handle_exception(e, context)
                
                if attempt >= max_retries or not should_retry:
                    raise
                
                # 等待一段时间后重试
                await asyncio.sleep(self.connection_config.retry_delay)
    
    def _format_user_info(self, user: User) -> str:
        """格式化用户信息"""
        if not user:
            return "Unknown"
        
        user_info = user.first_name or ""
        if user.last_name:
            user_info += f" {user.last_name}"
        if user.username:
            user_info += f" (@{user.username})"
        
        return user_info or "Unknown User"
    
    def get_connection_metrics(self) -> ConnectionMetrics:
        """获取连接指标"""
        return self.connection_manager.get_metrics()
    
    def get_exception_stats(self) -> Dict[str, Any]:
        """获取异常统计"""
        return self.exception_handler.get_exception_stats()
    
    def get_queue_status(self) -> Dict[str, Any]:
        """获取请求队列状态"""
        return self.request_queue.get_queue_status()
    
    def get_comprehensive_status(self) -> Dict[str, Any]:
        """获取综合状态信息"""
        return {
            "client_status": {
                "is_authorized": self.is_authorized,
                "connection_state": self.connection_manager.state.value,
                "proxy_enabled": self.config_manager.is_proxy_enabled(),
                "session_name": self.session_name
            },
            "connection_metrics": self.get_connection_metrics().__dict__,
            "exception_stats": self.get_exception_stats(),
            "queue_status": self.get_queue_status()
        } 