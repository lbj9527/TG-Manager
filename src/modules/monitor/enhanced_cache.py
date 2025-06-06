"""
增强的缓存模块，支持TTL过期、LRU淘汰和性能监控
"""

import time
import threading
from typing import Any, Optional, Dict, Tuple
from collections import OrderedDict

from src.utils.logger import get_logger

logger = get_logger()

class EnhancedCache:
    """
    增强的缓存类，支持TTL过期、LRU淘汰和性能监控
    """
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        """
        初始化增强缓存
        
        Args:
            max_size: 缓存最大条目数
            default_ttl: 默认TTL时间（秒）
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: OrderedDict[str, Tuple[Any, float]] = OrderedDict()  # key -> (value, expire_time)
        self.lock = threading.RLock()
        
        # 性能监控相关
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.expired_items = 0
        
        logger.debug(f"增强缓存初始化完成，最大大小: {max_size}, 默认TTL: {default_ttl}秒")
    
    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值
        
        Args:
            key: 缓存键
            
        Returns:
            Optional[Any]: 缓存值，如果不存在或已过期返回None
        """
        with self.lock:
            current_time = time.time()
            
            if key in self.cache:
                value, expire_time = self.cache[key]
                
                # 检查是否过期
                if current_time <= expire_time:
                    # 未过期，移动到末尾（LRU）
                    self.cache.move_to_end(key)
                    self.hits += 1
                    return value
                else:
                    # 已过期，删除
                    del self.cache[key]
                    self.expired_items += 1
                    logger.debug(f"缓存项已过期并删除: {key}")
            
            self.misses += 1
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: 生存时间（秒），如果为None使用默认TTL
        """
        with self.lock:
            current_time = time.time()
            expire_time = current_time + (ttl or self.default_ttl)
            
            # 如果键已存在，更新值并移动到末尾
            if key in self.cache:
                self.cache[key] = (value, expire_time)
                self.cache.move_to_end(key)
            else:
                # 新键，检查是否需要淘汰旧项
                if len(self.cache) >= self.max_size:
                    # 淘汰最旧的项
                    oldest_key = next(iter(self.cache))
                    del self.cache[oldest_key]
                    self.evictions += 1
                    logger.debug(f"缓存已满，淘汰最旧项: {oldest_key}")
                
                self.cache[key] = (value, expire_time)
            
            logger.debug(f"缓存已设置: {key}, TTL: {ttl or self.default_ttl}秒")
    
    def delete(self, key: str) -> bool:
        """
        删除缓存项
        
        Args:
            key: 缓存键
            
        Returns:
            bool: 是否成功删除
        """
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                logger.debug(f"缓存项已删除: {key}")
                return True
            return False
    
    def clear(self):
        """清空所有缓存"""
        with self.lock:
            cache_size = len(self.cache)
            self.cache.clear()
            logger.info(f"缓存已清空，共清理 {cache_size} 个条目")
    
    def cleanup_expired(self) -> int:
        """
        清理过期的缓存项
        
        Returns:
            int: 清理的过期项数量
        """
        with self.lock:
            current_time = time.time()
            expired_keys = []
            
            for key, (value, expire_time) in self.cache.items():
                if current_time > expire_time:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self.cache[key]
                self.expired_items += 1
            
            if expired_keys:
                logger.debug(f"清理了 {len(expired_keys)} 个过期缓存项")
            
            return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            Dict[str, Any]: 缓存统计信息
        """
        with self.lock:
            total_requests = self.hits + self.misses
            hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0.0
            
            return {
                "size": len(self.cache),
                "max_size": self.max_size,
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": hit_rate,
                "evictions": self.evictions,
                "expired_items": self.expired_items,
                "usage_percentage": (len(self.cache) / self.max_size * 100) if self.max_size > 0 else 0.0
            }
    
    def reset_stats(self):
        """重置统计信息"""
        with self.lock:
            self.hits = 0
            self.misses = 0
            self.evictions = 0
            self.expired_items = 0
            logger.debug("缓存统计信息已重置")
    
    def contains(self, key: str) -> bool:
        """
        检查缓存中是否包含指定键（不影响LRU顺序）
        
        Args:
            key: 缓存键
            
        Returns:
            bool: 是否包含该键且未过期
        """
        with self.lock:
            if key not in self.cache:
                return False
            
            value, expire_time = self.cache[key]
            current_time = time.time()
            
            if current_time <= expire_time:
                return True
            else:
                # 过期了，删除并返回False
                del self.cache[key]
                self.expired_items += 1
                return False
    
    def get_or_set(self, key: str, factory_func, ttl: Optional[int] = None) -> Any:
        """
        获取缓存值，如果不存在则使用工厂函数创建并缓存
        
        Args:
            key: 缓存键
            factory_func: 用于创建值的工厂函数
            ttl: 生存时间（秒）
            
        Returns:
            Any: 缓存值
        """
        # 先尝试获取
        value = self.get(key)
        if value is not None:
            return value
        
        # 不存在，使用工厂函数创建
        try:
            new_value = factory_func()
            self.set(key, new_value, ttl)
            return new_value
        except Exception as e:
            logger.error(f"工厂函数执行失败: {e}")
            raise
    
    def keys(self):
        """
        获取所有有效的缓存键
        
        Returns:
            List[str]: 有效的缓存键列表
        """
        with self.lock:
            current_time = time.time()
            valid_keys = []
            
            for key, (value, expire_time) in self.cache.items():
                if current_time <= expire_time:
                    valid_keys.append(key)
            
            return valid_keys
    
    def size(self) -> int:
        """
        获取当前缓存大小
        
        Returns:
            int: 当前缓存条目数
        """
        with self.lock:
            return len(self.cache)


class ChannelInfoCache:
    """
    专门用于频道信息的缓存
    """
    
    def __init__(self, max_size: int = 500, default_ttl: int = 3600):
        """
        初始化频道信息缓存
        
        Args:
            max_size: 最大缓存条目数
            default_ttl: 默认TTL时间（秒）
        """
        self.cache = EnhancedCache(max_size, default_ttl)
        logger.debug(f"频道信息缓存初始化完成，最大容量: {max_size}")
    
    def get_channel_info(self, channel_id: int) -> Optional[tuple]:
        """
        获取频道信息
        
        Args:
            channel_id: 频道ID
            
        Returns:
            tuple: (display_name, title) 或 None
        """
        info = self.cache.get(str(channel_id))
        if info:
            return info
        return None
    
    def set_channel_info(self, channel_id: int, display_name: str, title: str, ttl: Optional[int] = None):
        """
        设置频道信息
        
        Args:
            channel_id: 频道ID
            display_name: 显示名称
            title: 频道标题
            ttl: 可选的TTL时间
        """
        self.cache.set(str(channel_id), (display_name, title), ttl)
    
    def remove_channel_info(self, channel_id: int) -> bool:
        """
        移除频道信息
        
        Args:
            channel_id: 频道ID
            
        Returns:
            bool: 是否成功移除
        """
        return self.cache.delete(str(channel_id))
    
    def clear(self):
        """清空所有缓存"""
        self.cache.clear()
    
    def size(self) -> int:
        """
        获取当前缓存大小
        
        Returns:
            int: 缓存条目数量
        """
        return self.cache.size()
    
    def cleanup_expired(self) -> int:
        """
        清理过期缓存项
        
        Returns:
            int: 清理的项目数量
        """
        return self.cache.cleanup_expired()
    
    def get_stats(self) -> dict:
        """
        获取缓存统计信息
        
        Returns:
            dict: 统计信息
        """
        return self.cache.get_stats() 