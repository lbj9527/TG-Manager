"""
资源管理器模块，负责管理临时文件和资源的生命周期
"""

import os
import shutil
import asyncio
import tempfile
import atexit
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple, Any, Callable
from datetime import datetime, timedelta
import threading
import weakref

from src.utils.logger import get_logger
from src.utils.controls import TaskContext

logger = get_logger()

class ResourceManager:
    """
    资源管理器类，负责管理临时文件和资源的生命周期
    
    主要功能:
    1. 临时文件和目录的创建与自动清理
    2. 资源追踪与引用计数
    3. 会话级别资源隔离
    4. 定期清理过期资源
    5. 应用退出时的资源释放
    """
    
    def __init__(self, base_temp_dir: str = "tmp"):
        """
        初始化资源管理器
        
        Args:
            base_temp_dir: 基础临时目录路径
        """
        # 基础临时目录
        self.base_temp_dir = Path(base_temp_dir)
        self.base_temp_dir.mkdir(exist_ok=True, parents=True)
        
        # 会话目录映射，格式：{会话ID: 目录路径}
        self._sessions: Dict[str, Path] = {}
        
        # 资源追踪，格式：{资源路径: {"refs": 引用计数, "created": 创建时间, "session": 会话ID}}
        self._resources: Dict[str, Dict[str, Any]] = {}
        
        # 资源清理回调，格式：{资源路径: 清理回调函数}
        self._cleanup_callbacks: Dict[str, Callable] = {}
        
        # 用于锁定资源字典的互斥锁
        self._lock = threading.RLock()
        
        # 创建分类子目录
        self.thumb_dir = self._create_category_dir("thumbnails")
        self.download_dir = self._create_category_dir("downloads")
        self.upload_dir = self._create_category_dir("uploads")
        self.media_group_dir = self._create_category_dir("media_groups")
        
        # 设置定期清理计划
        self._cleanup_task = None
        self._cleanup_interval = 30 * 60  # 30分钟清理一次
        self._resource_ttl = 24 * 60 * 60  # 资源存活时间，单位秒
        
        # 注册应用退出时的清理函数
        atexit.register(self._cleanup_on_exit)
        
        # 弱引用映射，用于避免循环引用
        self._resource_objects = weakref.WeakValueDictionary()
        
        logger.info(f"资源管理器初始化完成，基础临时目录: {self.base_temp_dir}")
    
    def _create_category_dir(self, category: str) -> Path:
        """
        创建分类子目录
        
        Args:
            category: 目录分类名
            
        Returns:
            Path: 分类目录路径
        """
        path = self.base_temp_dir / category
        path.mkdir(exist_ok=True, parents=True)
        return path
    
    def create_session(self, prefix: str = "") -> str:
        """
        创建新的资源会话
        
        Args:
            prefix: 会话目录前缀
            
        Returns:
            str: 会话ID
        """
        # 生成会话ID和目录名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_id = f"{prefix}_{timestamp}" if prefix else timestamp
        
        # 创建会话目录
        session_dir = self.base_temp_dir / "sessions" / session_id
        session_dir.mkdir(exist_ok=True, parents=True)
        
        # 记录会话
        with self._lock:
            self._sessions[session_id] = session_dir
        
        logger.debug(f"创建资源会话: {session_id}, 目录: {session_dir}")
        return session_id
    
    def get_session_dir(self, session_id: str) -> Optional[Path]:
        """
        获取会话目录路径
        
        Args:
            session_id: 会话ID
            
        Returns:
            Optional[Path]: 会话目录路径，如果会话不存在则返回None
        """
        with self._lock:
            return self._sessions.get(session_id)
    
    def create_temp_file(self, extension: str = "", 
                        category: str = "general", 
                        session_id: Optional[str] = None) -> Tuple[Path, str]:
        """
        创建临时文件
        
        Args:
            extension: 文件扩展名，例如 ".jpg"
            category: 文件分类
            session_id: 会话ID，如果为None则使用通用目录
            
        Returns:
            Tuple[Path, str]: (文件路径, 资源ID)
        """
        # 确定目录
        if session_id and session_id in self._sessions:
            parent_dir = self._sessions[session_id]
        else:
            parent_dir = self.base_temp_dir / category
            parent_dir.mkdir(exist_ok=True, parents=True)
        
        # 创建临时文件
        temp_filename = f"temp_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}{extension}"
        temp_path = parent_dir / temp_filename
        
        # 注册资源
        resource_id = self._register_resource(str(temp_path), session_id)
        
        return temp_path, resource_id
    
    def create_temp_dir(self, 
                      name: Optional[str] = None, 
                      category: str = "general", 
                      session_id: Optional[str] = None) -> Tuple[Path, str]:
        """
        创建临时目录
        
        Args:
            name: 目录名，如果为None则自动生成
            category: 目录分类
            session_id: 会话ID，如果为None则使用通用目录
            
        Returns:
            Tuple[Path, str]: (目录路径, 资源ID)
        """
        # 确定父目录
        if session_id and session_id in self._sessions:
            parent_dir = self._sessions[session_id]
        else:
            parent_dir = self.base_temp_dir / category
            parent_dir.mkdir(exist_ok=True, parents=True)
        
        # 创建目录名
        if name is None:
            dir_name = f"dir_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        else:
            # 确保名称安全
            dir_name = self._get_safe_path_name(name)
        
        # 创建目录
        temp_dir = parent_dir / dir_name
        temp_dir.mkdir(exist_ok=True)
        
        # 注册资源
        resource_id = self._register_resource(str(temp_dir), session_id, is_directory=True)
        
        return temp_dir, resource_id
    
    def register_resource(self, resource_path: str, 
                        session_id: Optional[str] = None, 
                        cleanup_callback: Optional[Callable] = None,
                        resource_obj: Any = None) -> str:
        """
        注册已存在的资源
        
        Args:
            resource_path: 资源路径
            session_id: 会话ID
            cleanup_callback: 资源清理回调函数
            resource_obj: 资源对象，用于弱引用追踪
            
        Returns:
            str: 资源ID
        """
        resource_id = self._register_resource(resource_path, session_id)
        
        if cleanup_callback:
            with self._lock:
                self._cleanup_callbacks[resource_path] = cleanup_callback
        
        if resource_obj:
            self._resource_objects[resource_path] = resource_obj
        
        return resource_id
    
    def _register_resource(self, resource_path: str, 
                         session_id: Optional[str] = None, 
                         is_directory: bool = False) -> str:
        """
        内部方法：注册资源到追踪系统
        
        Args:
            resource_path: 资源路径
            session_id: 会话ID
            is_directory: 是否为目录
            
        Returns:
            str: 资源ID (通常就是资源路径)
        """
        with self._lock:
            # 检查资源是否已存在
            if resource_path in self._resources:
                # 增加引用计数
                self._resources[resource_path]["refs"] += 1
                logger.debug(f"增加资源引用计数: {resource_path}, 当前计数: {self._resources[resource_path]['refs']}")
            else:
                # 新增资源记录
                self._resources[resource_path] = {
                    "refs": 1,
                    "created": datetime.now(),
                    "session": session_id,
                    "is_directory": is_directory
                }
                logger.debug(f"注册新资源: {resource_path}, 会话: {session_id}")
        
        return resource_path
    
    def release_resource(self, resource_id: str, force_delete: bool = False) -> bool:
        """
        释放资源引用，当引用计数为0时删除资源
        
        Args:
            resource_id: 资源ID
            force_delete: 是否强制删除，无视引用计数
            
        Returns:
            bool: 操作是否成功
        """
        if not resource_id:
            return False
        
        with self._lock:
            if resource_id not in self._resources:
                logger.warning(f"尝试释放未注册的资源: {resource_id}")
                return False
            
            # 减少引用计数
            if not force_delete:
                self._resources[resource_id]["refs"] -= 1
                
            # 如果引用计数为0或强制删除，则删除资源
            if force_delete or self._resources[resource_id]["refs"] <= 0:
                return self._delete_resource(resource_id)
            else:
                logger.debug(f"减少资源引用计数: {resource_id}, 剩余计数: {self._resources[resource_id]['refs']}")
                return True
    
    def _delete_resource(self, resource_path: str) -> bool:
        """
        内部方法：删除资源并清理记录
        
        Args:
            resource_path: 资源路径
            
        Returns:
            bool: 操作是否成功
        """
        success = True
        
        try:
            # 调用自定义清理回调
            if resource_path in self._cleanup_callbacks:
                try:
                    self._cleanup_callbacks[resource_path](resource_path)
                except Exception as e:
                    logger.error(f"执行资源清理回调失败: {resource_path}, 错误: {e}")
                    success = False
                finally:
                    # 删除回调引用
                    del self._cleanup_callbacks[resource_path]
            
            # 检查是否为目录
            is_directory = self._resources[resource_path].get("is_directory", False)
            
            # 检查资源是否存在
            path = Path(resource_path)
            if path.exists():
                try:
                    if is_directory or path.is_dir():
                        shutil.rmtree(path)
                        logger.debug(f"删除目录资源: {resource_path}")
                    else:
                        path.unlink()
                        logger.debug(f"删除文件资源: {resource_path}")
                except Exception as e:
                    logger.error(f"删除资源文件失败: {resource_path}, 错误: {e}")
                    success = False
            
            # 删除资源记录
            del self._resources[resource_path]
            
            # 从弱引用字典中移除
            if resource_path in self._resource_objects:
                del self._resource_objects[resource_path]
            
        except Exception as e:
            logger.error(f"删除资源记录失败: {resource_path}, 错误: {e}")
            success = False
        
        return success
    
    def cleanup_session(self, session_id: str) -> bool:
        """
        清理整个会话的资源
        
        Args:
            session_id: 会话ID
            
        Returns:
            bool: 操作是否成功
        """
        if session_id not in self._sessions:
            logger.warning(f"尝试清理不存在的会话: {session_id}")
            return False
        
        success = True
        
        # 找出所有属于该会话的资源
        with self._lock:
            session_resources = [
                res_path for res_path, info in self._resources.items()
                if info.get("session") == session_id
            ]
            
            # 依次强制释放所有资源
            for resource_path in session_resources:
                if not self.release_resource(resource_path, force_delete=True):
                    success = False
            
            # 删除会话目录
            try:
                session_dir = self._sessions[session_id]
                if session_dir.exists():
                    shutil.rmtree(session_dir)
                    logger.debug(f"删除会话目录: {session_dir}")
            except Exception as e:
                logger.error(f"删除会话目录失败: {session_dir}, 错误: {e}")
                success = False
            
            # 删除会话记录
            del self._sessions[session_id]
            logger.info(f"清理会话完成: {session_id}")
        
        return success
    
    async def cleanup_expired_resources(self, max_age_seconds: Optional[int] = None) -> int:
        """
        清理过期资源
        
        Args:
            max_age_seconds: 资源最大存活时间(秒)，如果为None则使用默认值
            
        Returns:
            int: 清理的资源数量
        """
        if max_age_seconds is None:
            max_age_seconds = self._resource_ttl
        
        now = datetime.now()
        expired_time = now - timedelta(seconds=max_age_seconds)
        cleanup_count = 0
        
        # 找出所有过期资源
        with self._lock:
            expired_resources = [
                res_path for res_path, info in self._resources.items()
                if info.get("created", now) < expired_time and info.get("refs", 0) <= 0
            ]
        
        # 依次释放过期资源
        for resource_path in expired_resources:
            if self.release_resource(resource_path, force_delete=True):
                cleanup_count += 1
        
        # 清理空会话目录
        with self._lock:
            for session_id, session_dir in list(self._sessions.items()):
                # 检查是否有该会话的资源
                has_resources = any(
                    info.get("session") == session_id
                    for info in self._resources.values()
                )
                
                # 如果没有资源且目录存在，则删除会话
                if not has_resources and session_dir.exists():
                    try:
                        # 检查目录是否为空
                        if not any(session_dir.iterdir()):
                            shutil.rmtree(session_dir)
                            del self._sessions[session_id]
                            logger.debug(f"删除空会话目录: {session_dir}")
                            cleanup_count += 1
                    except Exception as e:
                        logger.error(f"删除空会话目录失败: {session_dir}, 错误: {e}")
        
        logger.info(f"过期资源清理完成，共清理 {cleanup_count} 项")
        return cleanup_count
    
    async def start_cleanup_task(self, task_context: Optional[TaskContext] = None):
        """
        启动定期清理任务
        
        Args:
            task_context: 任务上下文，用于控制任务停止
        """
        if self._cleanup_task is not None:
            logger.warning("清理任务已在运行")
            return
        
        logger.info(f"启动资源定期清理任务，间隔: {self._cleanup_interval}秒")
        
        async def cleanup_loop():
            try:
                while True:
                    # 检查是否应该停止
                    if task_context and task_context.cancel_token.is_cancelled:
                        logger.info("资源清理任务被取消")
                        break
                    
                    # 执行清理
                    await self.cleanup_expired_resources()
                    
                    # 等待下一次清理
                    for _ in range(self._cleanup_interval):
                        # 每秒检查一次是否取消
                        if task_context and task_context.cancel_token.is_cancelled:
                            break
                        await asyncio.sleep(1)
                    
                    if task_context and task_context.cancel_token.is_cancelled:
                        break
            except Exception as e:
                logger.error(f"资源清理任务异常: {e}")
            finally:
                self._cleanup_task = None
                logger.info("资源清理任务已停止")
        
        self._cleanup_task = asyncio.create_task(cleanup_loop())
    
    async def stop_cleanup_task(self):
        """
        停止定期清理任务
        """
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("已停止资源清理任务")
    
    def get_resource_info(self, resource_id: str) -> Optional[Dict[str, Any]]:
        """
        获取资源信息
        
        Args:
            resource_id: 资源ID
            
        Returns:
            Optional[Dict[str, Any]]: 资源信息字典，如果资源不存在则返回None
        """
        with self._lock:
            if resource_id in self._resources:
                # 返回资源信息的副本
                info = self._resources[resource_id].copy()
                # 转换datetime为ISO格式字符串，避免序列化问题
                if "created" in info and isinstance(info["created"], datetime):
                    info["created"] = info["created"].isoformat()
                return info
            return None
    
    def list_resources(self, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        列出资源
        
        Args:
            session_id: 会话ID，如果提供则只列出该会话的资源
            
        Returns:
            List[Dict[str, Any]]: 资源信息列表
        """
        result = []
        
        with self._lock:
            for resource_id, info in self._resources.items():
                if session_id is None or info.get("session") == session_id:
                    # 创建资源信息副本
                    resource_info = {
                        "resource_id": resource_id,
                        **info.copy()
                    }
                    # 转换datetime为ISO格式字符串
                    if "created" in resource_info and isinstance(resource_info["created"], datetime):
                        resource_info["created"] = resource_info["created"].isoformat()
                    
                    result.append(resource_info)
        
        return result
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """
        列出所有会话
        
        Returns:
            List[Dict[str, Any]]: 会话信息列表
        """
        result = []
        
        with self._lock:
            for session_id, session_dir in self._sessions.items():
                # 计算会话中的资源数量
                resource_count = sum(
                    1 for info in self._resources.values()
                    if info.get("session") == session_id
                )
                
                result.append({
                    "session_id": session_id,
                    "directory": str(session_dir),
                    "resource_count": resource_count
                })
        
        return result
    
    def _cleanup_on_exit(self):
        """
        应用退出时的清理函数
        """
        logger.info("应用退出，清理所有资源...")
        
        # 获取所有资源路径
        with self._lock:
            all_resources = list(self._resources.keys())
        
        # 强制删除所有资源
        for resource_path in all_resources:
            try:
                self.release_resource(resource_path, force_delete=True)
            except Exception as e:
                # 不抛出异常，仅记录错误
                logger.error(f"应用退出时删除资源失败: {resource_path}, 错误: {e}")
        
        # 清理所有会话目录
        with self._lock:
            for session_id, session_dir in list(self._sessions.items()):
                try:
                    if session_dir.exists():
                        shutil.rmtree(session_dir)
                        logger.debug(f"删除会话目录: {session_dir}")
                except Exception as e:
                    logger.error(f"删除会话目录失败: {session_dir}, 错误: {e}")
        
        # 确保基础临时目录为空
        try:
            # 删除所有子目录
            for subdir in self.base_temp_dir.iterdir():
                if subdir.is_dir():
                    try:
                        shutil.rmtree(subdir)
                    except:
                        pass
                else:
                    try:
                        subdir.unlink()
                    except:
                        pass
        except Exception as e:
            logger.error(f"清理基础临时目录失败: {e}")
    
    async def __aenter__(self):
        """
        异步上下文管理器入口
        """
        # 创建默认会话
        self.default_session = self.create_session("default")
        await self.start_cleanup_task()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        异步上下文管理器退出
        """
        await self.stop_cleanup_task()
        self.cleanup_session(self.default_session)
    
    def _get_safe_path_name(self, path_str: str) -> str:
        """
        将路径字符串转换为安全的文件名，移除无效字符
        
        Args:
            path_str: 原始路径字符串
            
        Returns:
            str: 处理后的安全路径字符串
        """
        # 替换URL分隔符
        safe_str = path_str.replace('://', '_').replace(':', '_')
        
        # 替换路径分隔符
        safe_str = safe_str.replace('\\', '_').replace('/', '_')
        
        # 替换其他不安全的文件名字符
        unsafe_chars = '<>:"|?*'
        for char in unsafe_chars:
            safe_str = safe_str.replace(char, '_')
            
        # 如果结果太长，取MD5哈希值
        if len(safe_str) > 100:
            import hashlib
            safe_str = hashlib.md5(path_str.encode()).hexdigest()
            
        return safe_str


# 创建标准上下文管理器包装类

class TempFile:
    """
    临时文件上下文管理器
    
    用法:
    ```python
    async with TempFile(resource_manager, ".jpg") as temp_file:
        # 使用临时文件
        with open(temp_file.path, 'wb') as f:
            f.write(data)
        # 无需手动删除，退出上下文后自动清理
    ```
    """
    
    def __init__(self, 
               resource_manager: ResourceManager, 
               extension: str = "", 
               category: str = "general", 
               session_id: Optional[str] = None):
        """
        初始化临时文件上下文管理器
        
        Args:
            resource_manager: 资源管理器实例
            extension: 文件扩展名
            category: 文件分类
            session_id: 会话ID
        """
        self.resource_manager = resource_manager
        self.extension = extension
        self.category = category
        self.session_id = session_id
        self.path = None
        self.resource_id = None
    
    async def __aenter__(self):
        """
        异步上下文管理器入口
        """
        self.path, self.resource_id = self.resource_manager.create_temp_file(
            self.extension, self.category, self.session_id
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        异步上下文管理器退出
        """
        if self.resource_id:
            self.resource_manager.release_resource(self.resource_id)


class TempDir:
    """
    临时目录上下文管理器
    
    用法:
    ```python
    async with TempDir(resource_manager, "media_group") as temp_dir:
        # 使用临时目录
        file_path = temp_dir.path / "file.jpg"
        with open(file_path, 'wb') as f:
            f.write(data)
        # 无需手动删除，退出上下文后自动清理
    ```
    """
    
    def __init__(self, 
               resource_manager: ResourceManager, 
               name: Optional[str] = None, 
               category: str = "general", 
               session_id: Optional[str] = None):
        """
        初始化临时目录上下文管理器
        
        Args:
            resource_manager: 资源管理器实例
            name: 目录名
            category: 目录分类
            session_id: 会话ID
        """
        self.resource_manager = resource_manager
        self.name = name
        self.category = category
        self.session_id = session_id
        self.path = None
        self.resource_id = None
    
    async def __aenter__(self):
        """
        异步上下文管理器入口
        """
        self.path, self.resource_id = self.resource_manager.create_temp_dir(
            self.name, self.category, self.session_id
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        异步上下文管理器退出
        """
        if self.resource_id:
            self.resource_manager.release_resource(self.resource_id)


class ResourceSession:
    """
    资源会话上下文管理器
    
    用法:
    ```python
    async with ResourceSession(resource_manager, "task1") as session:
        # session.id 包含会话ID
        # 在会话中创建资源
        temp_file_path, file_id = resource_manager.create_temp_file(
            extension=".jpg", session_id=session.id
        )
        # 所有会话资源将在退出上下文后自动清理
    ```
    """
    
    def __init__(self, resource_manager: ResourceManager, prefix: str = ""):
        """
        初始化资源会话上下文管理器
        
        Args:
            resource_manager: 资源管理器实例
            prefix: 会话前缀
        """
        self.resource_manager = resource_manager
        self.prefix = prefix
        self.id = None
    
    async def __aenter__(self):
        """
        异步上下文管理器入口
        """
        self.id = self.resource_manager.create_session(self.prefix)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        异步上下文管理器退出
        """
        if self.id:
            self.resource_manager.cleanup_session(self.id) 