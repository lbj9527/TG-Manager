"""
基于Pyropatch的专业级FloodWait处理器

集成pyropatch的flood_handler功能，为TG-Manager转发模块
提供更专业、更稳定的FloodWait处理能力。
"""

import asyncio
import functools
from typing import Any, Callable, Optional, TypeVar, Awaitable, Union
from pathlib import Path

from pyrogram import Client
from pyrogram.errors import FloodWait
from loguru import logger

# 导入pyropatch模块
try:
    from pyropatch.flood_handler import patch as flood_handler_patch
    PYROPATCH_AVAILABLE = True
    logger.info("Pyropatch flood_handler 已导入，将使用高级FloodWait处理")
except ImportError as e:
    PYROPATCH_AVAILABLE = False
    logger.warning(f"Pyropatch 导入失败: {e}，将使用内置FloodWait处理器")

T = TypeVar('T')

class PyropatchFloodWaitManager:
    """
    基于Pyropatch的FloodWait管理器
    
    提供与现有TG-Manager代码兼容的API接口，
    同时利用pyropatch的专业级FloodWait处理能力。
    """
    
    def __init__(self, max_retries: int = 3, base_delay: float = 0.5):
        """
        初始化Pyropatch FloodWait管理器
        
        Args:
            max_retries: 最大重试次数，默认3次
            base_delay: 基础延迟时间（秒），默认0.5秒
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self._patched_clients = set()
        
    def enable_for_client(self, client: Client) -> bool:
        """
        为Pyrogram客户端启用pyropatch的FloodWait处理
        
        Args:
            client: Pyrogram客户端实例
            
        Returns:
            bool: 是否成功启用
        """
        if not PYROPATCH_AVAILABLE:
            logger.warning("Pyropatch不可用，无法启用高级FloodWait处理")
            return False
            
        try:
            # 检查客户端是否已经被补丁
            if id(client) in self._patched_clients:
                logger.debug("客户端已经启用pyropatch FloodWait处理")
                return True
            
            # 应用pyropatch的flood_handler
            flood_handler_patch(client)
            
            # 记录已补丁的客户端
            self._patched_clients.add(id(client))
            
            logger.success(f"已为客户端启用pyropatch FloodWait处理 (max_retries={self.max_retries})")
            return True
            
        except Exception as e:
            logger.error(f"启用pyropatch FloodWait处理失败: {e}")
            return False
    
    def disable_for_client(self, client: Client) -> bool:
        """
        为客户端禁用pyropatch的FloodWait处理
        
        Args:
            client: Pyrogram客户端实例
            
        Returns:
            bool: 是否成功禁用
        """
        try:
            # 移除客户端记录
            client_id = id(client)
            if client_id in self._patched_clients:
                self._patched_clients.remove(client_id)
                logger.info("已禁用客户端的pyropatch FloodWait处理")
                return True
            else:
                logger.debug("客户端未启用pyropatch FloodWait处理")
                return True
                
        except Exception as e:
            logger.error(f"禁用pyropatch FloodWait处理失败: {e}")
            return False
    
    async def execute_with_flood_wait(
        self, 
        func: Callable[..., Awaitable[T]], 
        *args, 
        **kwargs
    ) -> Optional[T]:
        """
        执行带有FloodWait处理的异步函数
        
        如果pyropatch可用，使用其处理机制；
        否则回退到内置处理器。
        
        Args:
            func: 要执行的异步函数
            *args: 函数的位置参数
            **kwargs: 函数的关键字参数
            
        Returns:
            函数的返回值，失败时返回None
        """
        if PYROPATCH_AVAILABLE:
            # 使用pyropatch的自动处理
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                logger.error(f"执行函数 {func.__name__} 时出错: {e}")
                return None
        else:
            # 回退到内置FloodWait处理器
            return await self._fallback_flood_wait_handler(func, *args, **kwargs)
    
    async def _fallback_flood_wait_handler(
        self, 
        func: Callable[..., Awaitable[T]], 
        *args, 
        **kwargs
    ) -> Optional[T]:
        """
        内置FloodWait处理器，作为pyropatch不可用时的备选方案
        
        Args:
            func: 要执行的异步函数
            *args: 函数的位置参数
            **kwargs: 函数的关键字参数
            
        Returns:
            函数的返回值，失败时返回None
        """
        retry_count = 0
        
        while retry_count <= self.max_retries:
            try:
                # 执行函数
                result = await func(*args, **kwargs)
                
                # 如果成功，返回结果
                if retry_count > 0:
                    logger.success(f"重试成功！函数 {func.__name__} 执行完成")
                
                return result
                
            except FloodWait as e:
                wait_time = e.value if hasattr(e, 'value') else (e.x if hasattr(e, 'x') else 60)
                
                if retry_count >= self.max_retries:
                    logger.error(f"达到最大重试次数 ({self.max_retries})，FloodWait错误: 需要等待 {wait_time} 秒")
                    raise e
                
                retry_count += 1
                logger.warning(f"遇到FloodWait错误，需要等待 {wait_time} 秒 (重试 {retry_count}/{self.max_retries})")
                
                # 智能等待
                await self._wait_with_progress(wait_time)
                
                # 添加额外的基础延迟
                if self.base_delay > 0:
                    await asyncio.sleep(self.base_delay)
                
            except asyncio.CancelledError:
                logger.info(f"任务被取消: {func.__name__}")
                raise
                
            except Exception as e:
                # 其他异常不重试，直接抛出
                logger.error(f"函数 {func.__name__} 执行时遇到非FloodWait错误: {type(e).__name__}: {e}")
                raise e
        
        return None
    
    async def _wait_with_progress(self, wait_time: float):
        """
        智能等待，长时间等待时显示进度
        
        Args:
            wait_time: 等待时间（秒）
        """
        if wait_time <= 10:
            # 短时间等待，直接等待
            logger.info(f"FloodWait等待: {wait_time:.1f}秒")
            await asyncio.sleep(wait_time)
        else:
            # 长时间等待，分段显示进度
            logger.info(f"FloodWait长时间等待: {wait_time:.1f}秒，将显示进度...")
            
            # 分成20个进度段
            segments = 20
            segment_time = wait_time / segments
            
            for i in range(segments):
                progress = (i + 1) / segments * 100
                remaining = wait_time - (i + 1) * segment_time
                logger.info(f"FloodWait等待中... {progress:.1f}% ({remaining:.0f}秒剩余)")
                
                try:
                    await asyncio.sleep(segment_time)
                except asyncio.CancelledError:
                    logger.info("FloodWait等待被取消")
                    raise
            
            logger.success("FloodWait等待完成，继续执行...")


# 全局管理器实例
_global_manager = PyropatchFloodWaitManager()

def setup_pyropatch_for_client(
    client: Client, 
    max_retries: int = 3, 
    base_delay: float = 0.5
) -> bool:
    """
    为客户端设置pyropatch FloodWait处理
    
    Args:
        client: Pyrogram客户端实例
        max_retries: 最大重试次数，默认3次
        base_delay: 基础延迟时间（秒），默认0.5秒
        
    Returns:
        bool: 是否成功设置
        
    Example:
        client = Client("my_session")
        success = setup_pyropatch_for_client(client, max_retries=5)
        if success:
            # 现在所有API调用都会自动处理FloodWait
            await client.send_message("me", "Hello")
    """
    global _global_manager
    _global_manager.max_retries = max_retries
    _global_manager.base_delay = base_delay
    return _global_manager.enable_for_client(client)

def cleanup_pyropatch_for_client(client: Client) -> bool:
    """
    清理客户端的pyropatch FloodWait处理
    
    Args:
        client: Pyrogram客户端实例
        
    Returns:
        bool: 是否成功清理
    """
    global _global_manager
    return _global_manager.disable_for_client(client)

async def execute_with_pyropatch_flood_wait(
    func: Callable[..., Awaitable[T]], 
    *args, 
    max_retries: int = 3,
    base_delay: float = 0.5,
    **kwargs
) -> Optional[T]:
    """
    便捷函数：使用pyropatch FloodWait处理执行异步函数
    
    Args:
        func: 要执行的异步函数
        *args: 函数的位置参数
        max_retries: 最大重试次数，默认3次
        base_delay: 基础延迟时间（秒），默认0.5秒
        **kwargs: 函数的关键字参数
        
    Returns:
        函数的返回值，失败时返回None
        
    Example:
        result = await execute_with_pyropatch_flood_wait(
            client.get_messages, "channel", limit=100
        )
    """
    manager = PyropatchFloodWaitManager(max_retries=max_retries, base_delay=base_delay)
    return await manager.execute_with_flood_wait(func, *args, **kwargs)

def pyropatch_flood_wait_decorator(max_retries: int = 3, base_delay: float = 0.5):
    """
    装饰器：为异步函数添加pyropatch FloodWait处理功能
    
    Args:
        max_retries: 最大重试次数，默认3次
        base_delay: 基础延迟时间（秒），默认0.5秒
        
    Returns:
        装饰器函数
        
    Example:
        @pyropatch_flood_wait_decorator(max_retries=5)
        async def my_api_call():
            return await client.get_messages("channel", limit=100)
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[Optional[T]]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Optional[T]:
            return await execute_with_pyropatch_flood_wait(
                func, *args, max_retries=max_retries, base_delay=base_delay, **kwargs
            )
        return wrapper
    return decorator

# 兼容性别名，保持与现有代码的兼容性
PyropatchHandler = PyropatchFloodWaitManager
setup_flood_wait_handling = setup_pyropatch_for_client
execute_with_flood_wait_pyropatch = execute_with_pyropatch_flood_wait

# 状态检查函数
def is_pyropatch_available() -> bool:
    """
    检查pyropatch是否可用
    
    Returns:
        bool: pyropatch是否可用
    """
    return PYROPATCH_AVAILABLE

def get_pyropatch_status() -> dict:
    """
    获取pyropatch状态信息
    
    Returns:
        dict: 包含pyropatch状态的字典
    """
    return {
        "available": PYROPATCH_AVAILABLE,
        "patched_clients": len(_global_manager._patched_clients),
        "max_retries": _global_manager.max_retries,
        "base_delay": _global_manager.base_delay
    } 