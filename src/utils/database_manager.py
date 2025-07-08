"""
数据库管理器模块，使用SQLite数据库管理下载、上传和转发的历史记录
替换原有的JSON文件存储方式，提供更好的性能和数据管理能力
"""

import sqlite3
import os
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Union, Optional, Set, Any, Tuple
from contextlib import contextmanager

from src.utils.logger import get_logger

logger = get_logger()

class DatabaseManager:
    """数据库管理器，使用SQLite统一管理下载、上传和转发历史记录"""
    
    def __init__(self, db_path: str = "history/history.db"):
        """
        初始化数据库管理器
        
        Args:
            db_path: 数据库文件路径
        """
        # 确保history文件夹存在
        history_dir = Path(db_path).parent
        history_dir.mkdir(exist_ok=True)
        
        self.db_path = db_path
        self._lock = threading.RLock()  # 可重入锁，支持嵌套调用
        
        # 初始化数据库
        self._init_database()
        
        logger.info(f"数据库管理器初始化完成: {db_path}")
    
    def _init_database(self):
        """初始化数据库表结构"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 创建下载历史表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS download_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id TEXT NOT NULL,
                    real_channel_id INTEGER,
                    message_id INTEGER NOT NULL,
                    download_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(channel_id, message_id)
                )
            ''')
            
            # 创建上传历史表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS upload_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_hash TEXT NOT NULL,
                    file_path TEXT,
                    target_channel TEXT NOT NULL,
                    file_size INTEGER,
                    media_type TEXT,
                    upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(file_hash, target_channel)
                )
            ''')
            
            # 创建转发历史表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS forward_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_channel TEXT NOT NULL,
                    real_source_id INTEGER,
                    message_id INTEGER NOT NULL,
                    target_channel TEXT NOT NULL,
                    forward_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(source_channel, message_id, target_channel)
                )
            ''')
            
            # 创建索引以提高查询性能
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_download_channel ON download_history(channel_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_download_message ON download_history(message_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_upload_hash ON upload_history(file_hash)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_upload_channel ON upload_history(target_channel)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_forward_source ON forward_history(source_channel)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_forward_message ON forward_history(message_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_forward_target ON forward_history(target_channel)')
            
            # 创建时间索引用于数据清理
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_download_time ON download_history(download_time)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_upload_time ON upload_history(upload_time)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_forward_time ON forward_history(forward_time)')
            
            conn.commit()
            
        logger.info("数据库表结构初始化完成")
    
    @contextmanager
    def _get_connection(self):
        """获取数据库连接的上下文管理器"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row  # 使结果可以通过列名访问
            yield conn
        except Exception as e:
            logger.error(f"数据库连接错误: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()
    
    # ==================== 下载历史记录方法 ====================
    
    def is_message_downloaded(self, channel_id: str, message_id: int) -> bool:
        """
        检查消息是否已下载
        
        Args:
            channel_id: 频道ID或用户名
            message_id: 消息ID
            
        Returns:
            bool: 是否已下载
        """
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT 1 FROM download_history WHERE channel_id = ? AND message_id = ?',
                    (channel_id, message_id)
                )
                return cursor.fetchone() is not None
    
    def add_download_record(self, channel_id: str, message_id: int, real_channel_id: Optional[int] = None):
        """
        添加下载记录
        
        Args:
            channel_id: 频道ID或用户名
            message_id: 消息ID
            real_channel_id: 真实频道ID（数字形式）
        """
        with self._lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        '''INSERT OR IGNORE INTO download_history 
                           (channel_id, real_channel_id, message_id) 
                           VALUES (?, ?, ?)''',
                        (channel_id, real_channel_id, message_id)
                    )
                    conn.commit()
                    
                    if cursor.rowcount > 0:
                        logger.debug(f"添加下载记录：频道 {channel_id}, 消息ID {message_id}")
            except Exception as e:
                logger.error(f"添加下载记录失败: {e}")
    
    def get_downloaded_messages(self, channel_id: str) -> List[int]:
        """
        获取频道已下载的消息ID列表
        
        Args:
            channel_id: 频道ID或用户名
            
        Returns:
            List[int]: 已下载的消息ID列表
        """
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT message_id FROM download_history WHERE channel_id = ? ORDER BY message_id',
                    (channel_id,)
                )
                return [row['message_id'] for row in cursor.fetchall()]
    
    # 为了兼容性添加别名
    def is_downloaded(self, channel_id: str, message_id: int) -> bool:
        """
        检查消息是否已下载，是is_message_downloaded的别名
        
        Args:
            channel_id: 频道ID或用户名
            message_id: 消息ID
            
        Returns:
            bool: 是否已下载
        """
        return self.is_message_downloaded(channel_id, message_id)
    
    # ==================== 上传历史记录方法 ====================
    
    def is_file_uploaded(self, file_path: str, target_channel: str) -> bool:
        """
        检查文件是否已上传到指定频道
        
        Args:
            file_path: 文件路径
            target_channel: 目标频道
            
        Returns:
            bool: 是否已上传
        """
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT 1 FROM upload_history WHERE file_path = ? AND target_channel = ?',
                    (file_path, target_channel)
                )
                return cursor.fetchone() is not None
    
    def add_upload_record(self, file_path: str, target_channel: str, file_size: int, media_type: str):
        """
        添加上传记录
        
        Args:
            file_path: 文件路径
            target_channel: 目标频道
            file_size: 文件大小（字节）
            media_type: 媒体类型
        """
        with self._lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        '''INSERT OR IGNORE INTO upload_history 
                           (file_path, target_channel, file_size, media_type) 
                           VALUES (?, ?, ?, ?)''',
                        (file_path, target_channel, file_size, media_type)
                    )
                    conn.commit()
                    
                    if cursor.rowcount > 0:
                        logger.debug(f"添加上传记录：文件 {file_path} 到频道 {target_channel}")
            except Exception as e:
                logger.error(f"添加上传记录失败: {e}")
    
    def get_uploaded_files(self, target_channel: Optional[str] = None) -> List[str]:
        """
        获取已上传到指定频道的文件列表
        
        Args:
            target_channel: 目标频道，为None则获取所有已上传文件
            
        Returns:
            List[str]: 已上传的文件路径列表
        """
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if target_channel is None:
                    cursor.execute('SELECT DISTINCT file_path FROM upload_history ORDER BY file_path')
                else:
                    cursor.execute(
                        'SELECT DISTINCT file_path FROM upload_history WHERE target_channel = ? ORDER BY file_path',
                        (target_channel,)
                    )
                return [row['file_path'] for row in cursor.fetchall()]
    
    def is_file_hash_uploaded(self, file_hash: str, target_channel: str) -> bool:
        """
        检查文件哈希是否已上传到目标频道
        
        Args:
            file_hash: 文件哈希值
            target_channel: 目标频道
            
        Returns:
            bool: 是否已上传
        """
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT 1 FROM upload_history WHERE file_hash = ? AND target_channel = ?',
                    (file_hash, target_channel)
                )
                return cursor.fetchone() is not None
    
    def add_upload_record_by_hash(self, file_hash: str, file_path: str, target_channel: str, file_size: int, media_type: str):
        """
        使用文件哈希添加上传记录
        
        Args:
            file_hash: 文件哈希值
            file_path: 文件原始路径（仅作为参考信息存储）
            target_channel: 目标频道
            file_size: 文件大小（字节）
            media_type: 媒体类型
        """
        with self._lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        '''INSERT OR IGNORE INTO upload_history 
                           (file_hash, file_path, target_channel, file_size, media_type) 
                           VALUES (?, ?, ?, ?, ?)''',
                        (file_hash, file_path, target_channel, file_size, media_type)
                    )
                    conn.commit()
                    
                    if cursor.rowcount > 0:
                        logger.debug(f"添加上传记录：文件哈希 {file_hash} (路径: {file_path}) 到频道 {target_channel}")
            except Exception as e:
                logger.error(f"添加上传记录失败: {e}")
    
    # ==================== 转发历史记录方法 ====================
    
    def is_message_forwarded(self, source_channel: str, message_id: int, target_channel: str) -> bool:
        """
        检查消息是否已转发到指定目标频道
        
        Args:
            source_channel: 源频道
            message_id: 消息ID
            target_channel: 目标频道
            
        Returns:
            bool: 是否已转发
        """
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''SELECT 1 FROM forward_history 
                       WHERE source_channel = ? AND message_id = ? AND target_channel = ?''',
                    (source_channel, message_id, target_channel)
                )
                return cursor.fetchone() is not None
    
    def add_forward_record(self, source_channel: str, message_id: int, target_channel: str, real_source_id: Optional[int] = None):
        """
        添加转发记录
        
        Args:
            source_channel: 源频道
            message_id: 消息ID
            target_channel: 目标频道
            real_source_id: 真实源频道ID（数字形式）
        """
        with self._lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        '''INSERT OR IGNORE INTO forward_history 
                           (source_channel, real_source_id, message_id, target_channel) 
                           VALUES (?, ?, ?, ?)''',
                        (source_channel, real_source_id, message_id, target_channel)
                    )
                    conn.commit()
                    
                    if cursor.rowcount > 0:
                        logger.debug(f"添加转发记录：源频道 {source_channel} 的消息ID {message_id} 到目标频道 {target_channel}")
            except Exception as e:
                logger.error(f"添加转发记录失败: {e}")
    
    def get_forwarded_messages(self, source_channel: str, target_channel: Optional[str] = None) -> List[int]:
        """
        获取从源频道已转发到目标频道的消息ID列表
        
        Args:
            source_channel: 源频道
            target_channel: 目标频道，为None则获取所有已转发消息
            
        Returns:
            List[int]: 已转发的消息ID列表
        """
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if target_channel is None:
                    cursor.execute(
                        'SELECT DISTINCT message_id FROM forward_history WHERE source_channel = ? ORDER BY message_id',
                        (source_channel,)
                    )
                else:
                    cursor.execute(
                        '''SELECT DISTINCT message_id FROM forward_history 
                           WHERE source_channel = ? AND target_channel = ? ORDER BY message_id''',
                        (source_channel, target_channel)
                    )
                return [row['message_id'] for row in cursor.fetchall()]
    
    # ==================== 数据管理方法 ====================
    
    def cleanup_old_records(self, days: int = 30):
        """
        清理指定天数前的历史记录
        
        Args:
            days: 保留天数，默认30天
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_timestamp = cutoff_date.isoformat()
        
        with self._lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # 清理下载历史
                    cursor.execute(
                        'DELETE FROM download_history WHERE download_time < ?',
                        (cutoff_timestamp,)
                    )
                    download_deleted = cursor.rowcount
                    
                    # 清理上传历史
                    cursor.execute(
                        'DELETE FROM upload_history WHERE upload_time < ?',
                        (cutoff_timestamp,)
                    )
                    upload_deleted = cursor.rowcount
                    
                    # 清理转发历史
                    cursor.execute(
                        'DELETE FROM forward_history WHERE forward_time < ?',
                        (cutoff_timestamp,)
                    )
                    forward_deleted = cursor.rowcount
                    
                    conn.commit()
                    
                    logger.info(f"数据清理完成：删除下载记录 {download_deleted} 条，上传记录 {upload_deleted} 条，转发记录 {forward_deleted} 条")
                    
            except Exception as e:
                logger.error(f"数据清理失败: {e}")
    
    def get_database_stats(self) -> Dict[str, Any]:
        """
        获取数据库统计信息
        
        Returns:
            Dict[str, Any]: 数据库统计信息
        """
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 获取各表记录数
                cursor.execute('SELECT COUNT(*) FROM download_history')
                download_count = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM upload_history')
                upload_count = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM forward_history')
                forward_count = cursor.fetchone()[0]
                
                # 获取数据库文件大小
                db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
                
                return {
                    'download_records': download_count,
                    'upload_records': upload_count,
                    'forward_records': forward_count,
                    'database_size_mb': round(db_size / (1024 * 1024), 2),
                    'database_path': self.db_path
                }
    
    def optimize_database(self):
        """优化数据库性能"""
        with self._lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # 重建索引
                    cursor.execute('REINDEX')
                    
                    # 清理数据库文件
                    cursor.execute('VACUUM')
                    
                    conn.commit()
                    
                    logger.info("数据库优化完成")
                    
            except Exception as e:
                logger.error(f"数据库优化失败: {e}")
    
    def backup_database(self, backup_path: str):
        """
        备份数据库
        
        Args:
            backup_path: 备份文件路径
        """
        with self._lock:
            try:
                import shutil
                shutil.copy2(self.db_path, backup_path)
                logger.info(f"数据库备份完成: {backup_path}")
            except Exception as e:
                logger.error(f"数据库备份失败: {e}") 