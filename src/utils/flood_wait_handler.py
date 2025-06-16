"""
Telegram FloodWait 专业级限流处理器

提供智能的FloodWait错误处理，包括：
- 自动重试机制
- 智能等待进度显示
- 多种使用方式（装饰器、便捷函数、处理器类）
- 异常安全处理
- Pyrogram客户端全局集成支持
"""

import asyncio
import functools
from typing import Any, Callable, Optional, TypeVar, Awaitable
from pyrogram.errors import FloodWait
from loguru import logger

T = TypeVar('T')

class FloodWaitHandler:
    """
    专业级FloodWait处理器
    
    提供智能的等待机制和进度显示，支持自动重试
    """
    
    def __init__(self, max_retries: int = 3, base_delay: float = 0.5):
        """
        初始化FloodWait处理器
        
        Args:
            max_retries: 最大重试次数，默认3次
            base_delay: 基础延迟时间（秒），默认0.5秒
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        
    async def handle_flood_wait(self, func: Callable[..., Awaitable[T]], *args, **kwargs) -> Optional[T]:
        """
        处理带有FloodWait错误的异步函数调用
        
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

    def with_flood_wait_handling(self, max_retries: Optional[int] = None):
        """
        装饰器工厂，为函数添加FloodWait处理功能
        
        Args:
            max_retries: 最大重试次数，None使用实例默认值
            
        Returns:
            装饰器函数
        """
        def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[Optional[T]]]:
            @functools.wraps(func)
            async def wrapper(*args, **kwargs) -> Optional[T]:
                # 使用传入的重试次数或实例默认值
                handler = FloodWaitHandler(
                    max_retries=max_retries if max_retries is not None else self.max_retries,
                    base_delay=self.base_delay
                )
                return await handler.handle_flood_wait(func, *args, **kwargs)
            return wrapper
        return decorator


# 便捷函数
async def execute_with_flood_wait(
    func: Callable[..., Awaitable[T]], 
    *args, 
    max_retries: int = 3, 
    base_delay: float = 0.5,
    **kwargs
) -> Optional[T]:
    """
    便捷函数：执行带有FloodWait处理的异步函数
    
    Args:
        func: 要执行的异步函数
        *args: 函数的位置参数
        max_retries: 最大重试次数，默认3次
        base_delay: 基础延迟时间（秒），默认0.5秒
        **kwargs: 函数的关键字参数
        
    Returns:
        函数的返回值，失败时返回None
        
    Example:
        result = await execute_with_flood_wait(client.send_message, "me", "Hello")
    """
    handler = FloodWaitHandler(max_retries=max_retries, base_delay=base_delay)
    return await handler.handle_flood_wait(func, *args, **kwargs)


def handle_flood_wait(max_retries: int = 3, base_delay: float = 0.5):
    """
    装饰器：为异步函数添加FloodWait处理功能
    
    Args:
        max_retries: 最大重试次数，默认3次
        base_delay: 基础延迟时间（秒），默认0.5秒
        
    Returns:
        装饰器函数
        
    Example:
        @handle_flood_wait(max_retries=5)
        async def my_api_call():
            return await client.get_messages("channel", limit=100)
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[Optional[T]]]:
        handler = FloodWaitHandler(max_retries=max_retries, base_delay=base_delay)
        return handler.with_flood_wait_handling(max_retries)(func)
    return decorator


class GlobalFloodWaitPatcher:
    """
    全局FloodWait处理器补丁类
    
    可以monkey-patch Pyrogram Client的所有API方法，
    让所有API调用都自动应用FloodWait处理
    """
    
    def __init__(self, max_retries: int = 3, base_delay: float = 0.5):
        """
        初始化全局FloodWait补丁器
        
        Args:
            max_retries: 最大重试次数，默认3次
            base_delay: 基础延迟时间（秒），默认0.5秒
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.handler = FloodWaitHandler(max_retries=max_retries, base_delay=base_delay)
        self._original_methods = {}
        self._patched_clients = set()
        
    def patch_client(self, client):
        """
        为指定的Pyrogram客户端打补丁
        
        Args:
            client: Pyrogram Client实例
        """
        # 避免重复打补丁
        if id(client) in self._patched_clients:
            logger.debug(f"客户端 {id(client)} 已经打过FloodWait补丁，跳过")
            return
            
        logger.info("正在为Pyrogram客户端应用全局FloodWait处理补丁...")
        
        # 需要打补丁的核心API方法（排除返回异步生成器的方法）
        api_methods = [
            'invoke', 'send', 'get_messages',
            # 'get_chat_history',  # 这个方法返回异步生成器，不应该被包装
            'download_media', 'send_message', 'send_media_group',
            'copy_message', 'copy_media_group', 'forward_messages',
            'send_photo', 'send_video', 'send_document', 'send_audio',
            'get_chat', 'get_me', 'get_users', 'send_code', 'sign_in'
        ]
        
        patched_count = 0
        
        for method_name in api_methods:
            if hasattr(client, method_name):
                original_method = getattr(client, method_name)
                
                # 确保是可调用的方法
                if callable(original_method):
                    # 保存原始方法
                    self._original_methods[f"{id(client)}_{method_name}"] = original_method
                    
                    # 创建包装方法
                    wrapped_method = self._create_wrapped_method(original_method, method_name)
                    
                    # 替换客户端方法
                    setattr(client, method_name, wrapped_method)
                    patched_count += 1
        
        # 记录已打补丁的客户端
        self._patched_clients.add(id(client))
        
        logger.success(f"成功为客户端打补丁，共处理 {patched_count} 个API方法")
    
    def _create_wrapped_method(self, original_method, method_name: str):
        """
        创建包装后的方法
        
        Args:
            original_method: 原始方法
            method_name: 方法名称
            
        Returns:
            包装后的方法
        """
        @functools.wraps(original_method)
        async def wrapped_method(*args, **kwargs):
            # 使用FloodWait处理器执行原始方法
            return await self.handler.handle_flood_wait(original_method, *args, **kwargs)
        
        # 保持方法名称用于日志
        wrapped_method.__name__ = method_name
        return wrapped_method
    
    def unpatch_client(self, client):
        """
        移除客户端的FloodWait补丁
        
        Args:
            client: Pyrogram Client实例
        """
        client_id = id(client)
        
        if client_id not in self._patched_clients:
            logger.debug(f"客户端 {client_id} 没有FloodWait补丁，无需移除")
            return
        
        logger.info("正在移除客户端的FloodWait处理补丁...")
        
        # 恢复所有原始方法
        restored_count = 0
        for key, original_method in list(self._original_methods.items()):
            if key.startswith(f"{client_id}_"):
                method_name = key.split("_", 1)[1]
                setattr(client, method_name, original_method)
                del self._original_methods[key]
                restored_count += 1
        
        # 从已打补丁集合中移除
        self._patched_clients.discard(client_id)
        
        logger.success(f"成功移除客户端补丁，共恢复 {restored_count} 个API方法")


# 全局补丁器实例
_global_patcher = None

def enable_global_flood_wait_handling(client, max_retries: int = 3, base_delay: float = 0.5):
    """
    为Pyrogram客户端启用全局FloodWait处理
    
    Args:
        client: Pyrogram Client实例
        max_retries: 最大重试次数，默认3次
        base_delay: 基础延迟时间（秒），默认0.5秒
        
    Example:
        from pyrogram import Client
        from src.utils.flood_wait_handler import enable_global_flood_wait_handling
        
        app = Client("my_account")
        enable_global_flood_wait_handling(app, max_retries=5)
        
        # 现在所有API调用都会自动处理FloodWait
        await app.start()
        messages = await app.get_messages("channel", limit=100)  # 自动处理FloodWait
    """
    global _global_patcher
    
    if _global_patcher is None:
        _global_patcher = GlobalFloodWaitPatcher(max_retries=max_retries, base_delay=base_delay)
    
    _global_patcher.patch_client(client)

def disable_global_flood_wait_handling(client):
    """
    为Pyrogram客户端禁用全局FloodWait处理
    
    Args:
        client: Pyrogram Client实例
    """
    global _global_patcher
    
    if _global_patcher is not None:
        _global_patcher.unpatch_client(client) 