"""
循环缓冲区模块，用于管理已处理消息ID，避免内存无限增长
"""

import time
import threading
from typing import Set, Any, Optional
from collections import deque

from src.utils.logger import get_logger

logger = get_logger()

class CircularBuffer:
    """
    循环缓冲区，用于存储有限数量的数据项，当达到最大容量时自动淘汰最旧的项
    """
    
    def __init__(self, max_size: int = 50000):
        """
        初始化循环缓冲区
        
        Args:
            max_size: 最大容量
        """
        self.max_size = max_size
        self.buffer = {}  # 用于快速查找
        self.order = deque(maxlen=max_size)  # 用于维护顺序
        self.lock = threading.RLock()
        
        # 统计信息
        self.total_added = 0
        self.total_evicted = 0
        
        logger.debug(f"循环缓冲区初始化完成，最大容量: {max_size}")
    
    def add(self, item: Any) -> bool:
        """
        添加项目到缓冲区
        
        Args:
            item: 要添加的项目
            
        Returns:
            bool: 是否成功添加（如果项目已存在则返回False）
        """
        with self.lock:
            if item in self.buffer:
                return False
            
            # 如果缓冲区已满，移除最旧的项目
            if len(self.order) >= self.max_size:
                oldest_item = self.order[0]
                if oldest_item in self.buffer:
                    del self.buffer[oldest_item]
                    self.total_evicted += 1
            
            # 添加新项目
            self.buffer[item] = time.time()
            self.order.append(item)
            self.total_added += 1
            
            return True
    
    def contains(self, item: Any) -> bool:
        """
        检查缓冲区是否包含指定项目
        
        Args:
            item: 要检查的项目
            
        Returns:
            bool: 是否包含该项目
        """
        with self.lock:
            return item in self.buffer
    
    def remove(self, item: Any) -> bool:
        """
        从缓冲区移除指定项目
        
        Args:
            item: 要移除的项目
            
        Returns:
            bool: 是否成功移除
        """
        with self.lock:
            if item in self.buffer:
                del self.buffer[item]
                try:
                    self.order.remove(item)
                except ValueError:
                    pass
                return True
            return False
    
    def clear(self):
        """清空缓冲区"""
        with self.lock:
            self.buffer.clear()
            self.order.clear()
            logger.debug("循环缓冲区已清空")
    
    def size(self) -> int:
        """
        获取当前缓冲区大小
        
        Returns:
            int: 当前项目数量
        """
        with self.lock:
            return len(self.buffer)
    
    def cleanup_expired(self, max_age_seconds: int = 86400) -> int:
        """
        清理过期项目（默认24小时）
        
        Args:
            max_age_seconds: 最大存活时间（秒）
            
        Returns:
            int: 清理的项目数量
        """
        with self.lock:
            current_time = time.time()
            expired_items = []
            
            for item, add_time in self.buffer.items():
                if current_time - add_time > max_age_seconds:
                    expired_items.append(item)
            
            for item in expired_items:
                self.remove(item)
            
            return len(expired_items)
    
    def get_stats(self) -> dict:
        """
        获取缓冲区统计信息
        
        Returns:
            dict: 统计信息
        """
        with self.lock:
            return {
                'current_size': len(self.buffer),
                'max_size': self.max_size,
                'total_added': self.total_added,
                'total_evicted': self.total_evicted,
                'usage_ratio': len(self.buffer) / self.max_size if self.max_size > 0 else 0
            }


class MessageIdBuffer:
    """
    专门用于管理已处理消息ID的缓冲区
    """
    
    def __init__(self, max_size: int = 50000):
        """
        初始化消息ID缓冲区
        
        Args:
            max_size: 最大容量
        """
        self.buffer = CircularBuffer(max_size)
        logger.debug(f"消息ID缓冲区初始化完成，最大容量: {max_size}")
    
    def mark_message_processed(self, message_id: int) -> bool:
        """
        标记消息为已处理
        
        Args:
            message_id: 消息ID
            
        Returns:
            bool: 是否为新消息（首次标记）
        """
        return self.buffer.add(message_id)
    
    def is_message_processed(self, message_id: int) -> bool:
        """
        检查消息是否已被处理
        
        Args:
            message_id: 消息ID
            
        Returns:
            bool: 是否已处理
        """
        return self.buffer.contains(message_id)
    
    def remove_message(self, message_id: int) -> bool:
        """
        从已处理列表中移除消息ID
        
        Args:
            message_id: 消息ID
            
        Returns:
            bool: 是否成功移除
        """
        return self.buffer.remove(message_id)
    
    def clear(self):
        """清空所有已处理消息ID"""
        self.buffer.clear()
    
    def size(self) -> int:
        """
        获取已处理消息数量
        
        Returns:
            int: 已处理消息数量
        """
        return self.buffer.size()
    
    def cleanup_expired(self, max_age_seconds: int = 86400) -> int:
        """
        清理过期的消息ID记录
        
        Args:
            max_age_seconds: 最大存活时间（秒，默认24小时）
            
        Returns:
            int: 清理的记录数量
        """
        return self.buffer.cleanup_expired(max_age_seconds)
    
    def get_stats(self) -> dict:
        """
        获取消息缓冲区统计信息
        
        Returns:
            dict: 统计信息
        """
        return self.buffer.get_stats() 