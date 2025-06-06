"""
性能监控模块，用于收集和管理监听模块的性能指标
"""

import time
import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import deque
from threading import Lock

from src.utils.logger import get_logger

logger = get_logger()

@dataclass
class PerformanceMetrics:
    """性能指标数据类"""
    total_processed: int = 0
    total_forwarded: int = 0
    total_filtered: int = 0
    total_failed: int = 0
    success_rate: float = 0.0
    avg_processing_time: float = 0.0
    avg_forward_time: float = 0.0
    throughput_per_min: float = 0.0
    current_queue_size: int = 0
    cache_hit_rate: float = 0.0
    memory_usage_mb: float = 0.0
    
    # 时间窗口相关指标
    messages_last_min: int = 0
    messages_last_5min: int = 0
    messages_last_hour: int = 0
    
    # 错误统计
    network_errors: int = 0
    api_errors: int = 0
    other_errors: int = 0
    
    # 延迟统计
    min_processing_time: float = 0.0
    max_processing_time: float = 0.0
    p95_processing_time: float = 0.0
    
@dataclass
class MessageEvent:
    """消息事件记录"""
    timestamp: float
    event_type: str  # 'processed', 'forwarded', 'filtered', 'failed'
    processing_time: Optional[float] = None
    forward_time: Optional[float] = None
    error_type: Optional[str] = None

class PerformanceMonitor:
    """
    性能监控器，收集和分析监听模块的性能数据
    """
    
    def __init__(self, max_events: int = 10000):
        """
        初始化性能监控器
        
        Args:
            max_events: 最大事件记录数
        """
        self.max_events = max_events
        self.events = deque(maxlen=max_events)
        self.metrics = PerformanceMetrics()
        self.lock = Lock()
        
        # 时间窗口统计
        self.processing_times = deque(maxlen=1000)  # 最近1000次处理时间
        self.forward_times = deque(maxlen=1000)     # 最近1000次转发时间
        
        # 缓存统计
        self.cache_hits = 0
        self.cache_misses = 0
        
        # 队列大小监控
        self.current_queue_size = 0
        
        # 开始时间
        self.start_time = time.time()
        
        logger.debug("性能监控器初始化完成")
    
    def record_message_processed(self, processing_time: float):
        """
        记录消息处理事件
        
        Args:
            processing_time: 处理时间（秒）
        """
        with self.lock:
            event = MessageEvent(
                timestamp=time.time(),
                event_type='processed',
                processing_time=processing_time
            )
            self.events.append(event)
            self.processing_times.append(processing_time)
            self.metrics.total_processed += 1
            
            # 更新平均处理时间
            if self.processing_times:
                self.metrics.avg_processing_time = sum(self.processing_times) / len(self.processing_times)
                self.metrics.min_processing_time = min(self.processing_times)
                self.metrics.max_processing_time = max(self.processing_times)
                # 计算P95延迟
                sorted_times = sorted(self.processing_times)
                p95_index = int(len(sorted_times) * 0.95)
                self.metrics.p95_processing_time = sorted_times[p95_index] if sorted_times else 0.0
    
    def record_message_forwarded(self, forward_time: float, success: bool = True):
        """
        记录消息转发事件
        
        Args:
            forward_time: 转发耗时（秒）
            success: 是否成功
        """
        with self.lock:
            event = MessageEvent(
                timestamp=time.time(),
                event_type='forwarded' if success else 'failed',
                forward_time=forward_time
            )
            self.events.append(event)
            
            if success:
                self.forward_times.append(forward_time)
                self.metrics.total_forwarded += 1
                
                # 更新平均转发时间
                if self.forward_times:
                    self.metrics.avg_forward_time = sum(self.forward_times) / len(self.forward_times)
            else:
                self.metrics.total_failed += 1
            
            # 更新成功率
            total_attempts = self.metrics.total_forwarded + self.metrics.total_failed
            if total_attempts > 0:
                self.metrics.success_rate = (self.metrics.total_forwarded / total_attempts) * 100
    
    def record_forwarding_time(self, forward_time: float, success: bool = True):
        """
        记录转发时间（简化版本，兼容旧代码）
        
        Args:
            forward_time: 转发耗时（秒）
            success: 是否成功
        """
        self.record_message_forwarded(forward_time, success)
    
    def record_message_filtered(self, filter_reason: str):
        """
        记录消息过滤事件
        
        Args:
            filter_reason: 过滤原因
        """
        with self.lock:
            event = MessageEvent(
                timestamp=time.time(),
                event_type='filtered'
            )
            self.events.append(event)
            self.metrics.total_filtered += 1
    
    def record_error(self, error_type: str):
        """
        记录错误事件
        
        Args:
            error_type: 错误类型 ('network', 'api', 'other')
        """
        with self.lock:
            event = MessageEvent(
                timestamp=time.time(),
                event_type='failed',
                error_type=error_type
            )
            self.events.append(event)
            
            if error_type == 'network':
                self.metrics.network_errors += 1
            elif error_type == 'api':
                self.metrics.api_errors += 1
            else:
                self.metrics.other_errors += 1
    
    def record_cache_hit(self):
        """记录缓存命中"""
        with self.lock:
            self.cache_hits += 1
            self._update_cache_hit_rate()
    
    def record_cache_miss(self):
        """记录缓存未命中"""
        with self.lock:
            self.cache_misses += 1
            self._update_cache_hit_rate()
    
    def _update_cache_hit_rate(self):
        """更新缓存命中率"""
        total_requests = self.cache_hits + self.cache_misses
        if total_requests > 0:
            self.metrics.cache_hit_rate = (self.cache_hits / total_requests) * 100
    
    def update_queue_size(self, size: int):
        """
        更新当前队列大小
        
        Args:
            size: 队列大小
        """
        with self.lock:
            self.metrics.current_queue_size = size
    
    def update_memory_usage(self, usage_mb: float):
        """
        更新内存使用量
        
        Args:
            usage_mb: 内存使用量（MB）
        """
        with self.lock:
            self.metrics.memory_usage_mb = usage_mb
    
    def get_metrics(self) -> PerformanceMetrics:
        """
        获取当前性能指标
        
        Returns:
            PerformanceMetrics: 性能指标对象
        """
        with self.lock:
            # 更新时间窗口统计
            self._update_time_window_stats()
            
            # 更新吞吐量
            elapsed_time = time.time() - self.start_time
            if elapsed_time > 0:
                self.metrics.throughput_per_min = (self.metrics.total_processed / elapsed_time) * 60
            
            # 返回指标副本
            return PerformanceMetrics(
                total_processed=self.metrics.total_processed,
                total_forwarded=self.metrics.total_forwarded,
                total_filtered=self.metrics.total_filtered,
                total_failed=self.metrics.total_failed,
                success_rate=self.metrics.success_rate,
                avg_processing_time=self.metrics.avg_processing_time,
                avg_forward_time=self.metrics.avg_forward_time,
                throughput_per_min=self.metrics.throughput_per_min,
                current_queue_size=self.metrics.current_queue_size,
                cache_hit_rate=self.metrics.cache_hit_rate,
                memory_usage_mb=self.metrics.memory_usage_mb,
                messages_last_min=self.metrics.messages_last_min,
                messages_last_5min=self.metrics.messages_last_5min,
                messages_last_hour=self.metrics.messages_last_hour,
                network_errors=self.metrics.network_errors,
                api_errors=self.metrics.api_errors,
                other_errors=self.metrics.other_errors,
                min_processing_time=self.metrics.min_processing_time,
                max_processing_time=self.metrics.max_processing_time,
                p95_processing_time=self.metrics.p95_processing_time
            )
    
    def _update_time_window_stats(self):
        """更新时间窗口统计"""
        current_time = time.time()
        
        # 统计不同时间窗口内的消息数量
        self.metrics.messages_last_min = sum(
            1 for event in self.events 
            if event.event_type == 'processed' and current_time - event.timestamp <= 60
        )
        
        self.metrics.messages_last_5min = sum(
            1 for event in self.events 
            if event.event_type == 'processed' and current_time - event.timestamp <= 300
        )
        
        self.metrics.messages_last_hour = sum(
            1 for event in self.events 
            if event.event_type == 'processed' and current_time - event.timestamp <= 3600
        )
    
    def get_recent_events(self, limit: int = 100) -> List[MessageEvent]:
        """
        获取最近的事件记录
        
        Args:
            limit: 返回事件数量限制
            
        Returns:
            List[MessageEvent]: 最近的事件列表
        """
        with self.lock:
            return list(self.events)[-limit:]
    
    def reset_metrics(self):
        """重置所有性能指标"""
        with self.lock:
            self.events.clear()
            self.metrics = PerformanceMetrics()
            self.processing_times.clear()
            self.forward_times.clear()
            self.cache_hits = 0
            self.cache_misses = 0
            self.current_queue_size = 0
            self.start_time = time.time()
            
        logger.info("性能监控器指标已重置")
    
    def get_performance_report(self) -> Dict[str, Any]:
        """
        获取详细的性能报告
        
        Returns:
            Dict[str, Any]: 性能报告字典
        """
        metrics = self.get_metrics()
        
        return {
            "basic_stats": {
                "total_processed": metrics.total_processed,
                "total_forwarded": metrics.total_forwarded,
                "total_filtered": metrics.total_filtered,
                "total_failed": metrics.total_failed,
                "success_rate": f"{metrics.success_rate:.2f}%"
            },
            "performance": {
                "avg_processing_time": f"{metrics.avg_processing_time:.3f}s",
                "avg_forward_time": f"{metrics.avg_forward_time:.3f}s",
                "throughput_per_min": f"{metrics.throughput_per_min:.2f}",
                "min_processing_time": f"{metrics.min_processing_time:.3f}s",
                "max_processing_time": f"{metrics.max_processing_time:.3f}s",
                "p95_processing_time": f"{metrics.p95_processing_time:.3f}s"
            },
            "system": {
                "current_queue_size": metrics.current_queue_size,
                "cache_hit_rate": f"{metrics.cache_hit_rate:.2f}%",
                "memory_usage_mb": f"{metrics.memory_usage_mb:.2f}MB"
            },
            "time_windows": {
                "messages_last_min": metrics.messages_last_min,
                "messages_last_5min": metrics.messages_last_5min,
                "messages_last_hour": metrics.messages_last_hour
            },
            "errors": {
                "network_errors": metrics.network_errors,
                "api_errors": metrics.api_errors,
                "other_errors": metrics.other_errors
            }
        } 