"""
强壮Telegram客户端 - 连接管理模块
负责状态跟踪、自动重连和指数退避策略
"""

import asyncio
import time
from typing import Optional, Callable, Any
from enum import Enum
from dataclasses import dataclass

from src.utils.logger import get_logger
from .config_manager import ConnectionConfig

logger = get_logger()


class ConnectionState(Enum):
    """连接状态枚举"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"
    STOPPING = "stopping"


@dataclass
class ConnectionMetrics:
    """连接指标"""
    connection_count: int = 0
    reconnection_count: int = 0
    total_downtime: float = 0.0
    last_connected_time: Optional[float] = None
    last_disconnected_time: Optional[float] = None
    consecutive_failures: int = 0
    
    def reset_failure_count(self):
        """重置连续失败次数"""
        self.consecutive_failures = 0
    
    def increment_failure_count(self):
        """增加连续失败次数"""
        self.consecutive_failures += 1


class ExponentialBackoff:
    """指数退避算法"""
    
    def __init__(self, base_delay: float = 1.0, max_delay: float = 300.0, multiplier: float = 2.0):
        """
        初始化指数退避
        
        Args:
            base_delay: 基础延迟时间（秒）
            max_delay: 最大延迟时间（秒）
            multiplier: 退避倍数
        """
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.multiplier = multiplier
        self.current_attempt = 0
    
    def get_delay(self) -> float:
        """
        获取当前尝试的延迟时间
        
        Returns:
            float: 延迟时间（秒）
        """
        delay = self.base_delay * (self.multiplier ** self.current_attempt)
        return min(delay, self.max_delay)
    
    def next_attempt(self) -> float:
        """
        移动到下一次尝试并返回延迟时间
        
        Returns:
            float: 延迟时间（秒）
        """
        delay = self.get_delay()
        self.current_attempt += 1
        return delay
    
    def reset(self):
        """重置退避状态"""
        self.current_attempt = 0


class ConnectionManager:
    """连接管理器"""
    
    def __init__(self, config: ConnectionConfig):
        """
        初始化连接管理器
        
        Args:
            config: 连接配置
        """
        self.config = config
        self.state = ConnectionState.DISCONNECTED
        self.metrics = ConnectionMetrics()
        self.backoff = ExponentialBackoff(
            base_delay=config.retry_delay,
            max_delay=config.max_retry_delay,
            multiplier=config.backoff_multiplier if config.enable_exponential_backoff else 1.0
        )
        
        # 回调函数
        self.on_state_changed: Optional[Callable[[ConnectionState], None]] = None
        self.on_connection_lost: Optional[Callable[[Exception], None]] = None
        self.on_connection_restored: Optional[Callable[[], None]] = None
        
        # 控制标志
        self._should_reconnect = True
        self._reconnect_task: Optional[asyncio.Task] = None
        self._connection_check_task: Optional[asyncio.Task] = None
        self._is_stopping = False
        
        logger.info("连接管理器已初始化")
    
    def set_state(self, new_state: ConnectionState):
        """
        设置连接状态
        
        Args:
            new_state: 新的连接状态
        """
        if self.state != new_state:
            old_state = self.state
            self.state = new_state
            
            logger.info(f"连接状态变化: {old_state.value} → {new_state.value}")
            
            # 更新指标
            current_time = time.time()
            if new_state == ConnectionState.CONNECTED:
                self.metrics.last_connected_time = current_time
                self.metrics.connection_count += 1
                self.metrics.reset_failure_count()
                self.backoff.reset()
            elif old_state == ConnectionState.CONNECTED and new_state == ConnectionState.DISCONNECTED:
                self.metrics.last_disconnected_time = current_time
                if self.metrics.last_connected_time:
                    uptime = current_time - self.metrics.last_connected_time
                    logger.debug(f"连接持续时间: {uptime:.2f}秒")
            
            # 调用状态变化回调
            if self.on_state_changed:
                try:
                    self.on_state_changed(new_state)
                except Exception as e:
                    logger.error(f"状态变化回调执行失败: {e}")
    
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.state == ConnectionState.CONNECTED
    
    def is_connecting(self) -> bool:
        """检查是否正在连接"""
        return self.state in (ConnectionState.CONNECTING, ConnectionState.RECONNECTING)
    
    def should_reconnect(self) -> bool:
        """检查是否应该重连"""
        return (
            self._should_reconnect 
            and not self._is_stopping
            and self.config.auto_restart_session
            and self.metrics.consecutive_failures < self.config.max_backoff_attempts
        )
    
    async def handle_connection_lost(self, error: Exception):
        """
        处理连接丢失
        
        Args:
            error: 导致连接丢失的异常
        """
        logger.warning(f"连接丢失: {error}")
        
        # 更新状态和指标
        self.set_state(ConnectionState.DISCONNECTED)
        self.metrics.increment_failure_count()
        
        # 调用连接丢失回调
        if self.on_connection_lost:
            try:
                self.on_connection_lost(error)
            except Exception as callback_error:
                logger.error(f"连接丢失回调执行失败: {callback_error}")
        
        # 如果应该重连，启动重连逻辑
        if self.should_reconnect():
            await self.start_reconnection()
    
    async def start_reconnection(self):
        """启动重连逻辑"""
        if self._reconnect_task and not self._reconnect_task.done():
            logger.debug("重连任务已在运行")
            return
        
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())
        logger.info("已启动重连任务")
    
    async def _reconnect_loop(self):
        """重连循环"""
        while self.should_reconnect():
            try:
                # 计算延迟时间
                delay = self.backoff.next_attempt()
                logger.info(f"将在 {delay:.2f} 秒后尝试重连 (尝试次数: {self.backoff.current_attempt})")
                
                # 等待延迟时间
                await asyncio.sleep(delay)
                
                if not self.should_reconnect():
                    break
                
                # 设置重连状态
                self.set_state(ConnectionState.RECONNECTING)
                self.metrics.reconnection_count += 1
                
                # 这里应该调用外部提供的重连函数
                # 由于这是连接管理器，实际的重连逻辑应该由客户端提供
                logger.info("准备执行重连操作...")
                
                # 等待外部重连完成的信号
                # 这将由 RobustTelegramClient 来处理
                break
                
            except asyncio.CancelledError:
                logger.info("重连任务已取消")
                break
            except Exception as e:
                logger.error(f"重连过程中出错: {e}")
                self.metrics.increment_failure_count()
                
                # 如果达到最大重试次数，停止重连
                if self.metrics.consecutive_failures >= self.config.max_backoff_attempts:
                    logger.error(f"重连失败次数过多 ({self.metrics.consecutive_failures})，停止重连")
                    self.set_state(ConnectionState.ERROR)
                    break
    
    async def notify_connection_success(self):
        """通知连接成功"""
        self.set_state(ConnectionState.CONNECTED)
        
        # 调用连接恢复回调
        if self.on_connection_restored:
            try:
                self.on_connection_restored()
            except Exception as e:
                logger.error(f"连接恢复回调执行失败: {e}")
        
        # 启动连接检查任务
        if self.config.connection_check_interval > 0:
            await self.start_connection_check()
    
    async def start_connection_check(self):
        """启动连接检查任务"""
        if self._connection_check_task and not self._connection_check_task.done():
            return
        
        self._connection_check_task = asyncio.create_task(self._connection_check_loop())
        logger.debug("已启动连接检查任务")
    
    async def _connection_check_loop(self):
        """连接检查循环"""
        while self.is_connected() and not self._is_stopping:
            try:
                await asyncio.sleep(self.config.connection_check_interval)
                
                if not self.is_connected() or self._is_stopping:
                    break
                
                # 这里应该调用外部提供的连接检查函数
                # 实际的检查逻辑由 RobustTelegramClient 提供
                logger.debug("执行连接状态检查")
                
            except asyncio.CancelledError:
                logger.debug("连接检查任务已取消")
                break
            except Exception as e:
                logger.error(f"连接检查过程中出错: {e}")
                await self.handle_connection_lost(e)
                break
    
    async def stop(self):
        """停止连接管理器"""
        self._is_stopping = True
        self._should_reconnect = False
        
        self.set_state(ConnectionState.STOPPING)
        
        # 取消所有任务
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
        
        if self._connection_check_task and not self._connection_check_task.done():
            self._connection_check_task.cancel()
            try:
                await self._connection_check_task
            except asyncio.CancelledError:
                pass
        
        self.set_state(ConnectionState.DISCONNECTED)
        logger.info("连接管理器已停止")
    
    def get_metrics(self) -> ConnectionMetrics:
        """获取连接指标"""
        return self.metrics
    
    def reset_metrics(self):
        """重置连接指标"""
        self.metrics = ConnectionMetrics()
        logger.debug("连接指标已重置")
    
    def enable_reconnection(self):
        """启用重连"""
        self._should_reconnect = True
        logger.debug("已启用自动重连")
    
    def disable_reconnection(self):
        """禁用重连"""
        self._should_reconnect = False
        logger.debug("已禁用自动重连") 