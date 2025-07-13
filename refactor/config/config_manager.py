"""
配置管理器

负责配置的加载、保存、验证、热重载等功能。
"""

import asyncio
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from loguru import logger

from config.config_utils import convert_ui_config_to_dict


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.config_file = Path(config.get('config_file', 'config.json'))
        self.backup_dir = Path(config.get('backup_dir', 'config_backups'))
        self.auto_backup = config.get('auto_backup', True)
        self.max_backups = config.get('max_backups', 10)
        
        # 确保备份目录存在
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    async def initialize(self) -> bool:
        """初始化配置管理器"""
        try:
            logger.info("初始化配置管理器...")
            
            # 检查配置文件是否存在
            if not self.config_file.exists():
                logger.info(f"配置文件不存在: {self.config_file}")
                return await self._create_default_config()
            
            # 加载配置文件
            if not await self.load_config():
                logger.error("加载配置文件失败")
                return False
            
            logger.info("配置管理器初始化成功")
            return True
            
        except Exception as e:
            logger.error(f"初始化配置管理器失败: {e}")
            return False
    
    async def load_config(self) -> bool:
        """加载配置文件"""
        try:
            logger.info(f"加载配置文件: {self.config_file}")
            
            if not self.config_file.exists():
                logger.error(f"配置文件不存在: {self.config_file}")
                return False
            
            # 读取配置文件
            with open(self.config_file, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
            
            # 验证配置
            if not self._validate_config(loaded_config):
                logger.error("配置文件验证失败")
                return False
            
            # 更新配置
            self.config.update(loaded_config)
            
            logger.info("配置文件加载成功")
            return True
            
        except json.JSONDecodeError as e:
            logger.error(f"配置文件JSON格式错误: {e}")
            return False
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return False
    
    async def save_config(self) -> bool:
        """保存配置文件"""
        try:
            logger.info(f"保存配置文件: {self.config_file}")
            
            # 创建备份
            if self.auto_backup:
                await self._create_backup()
            
            # 确保目录存在
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 保存配置文件
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            
            logger.info("配置文件保存成功")
            return True
            
        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")
            return False
    
    async def reload(self) -> bool:
        """重新加载配置"""
        try:
            logger.info("重新加载配置...")
            
            # 加载配置文件
            if not await self.load_config():
                return False
            
            logger.info("配置重新加载成功")
            return True
            
        except Exception as e:
            logger.error(f"重新加载配置失败: {e}")
            return False
    
    async def update_config(self, new_config: Dict[str, Any]) -> bool:
        """更新配置"""
        try:
            logger.info("更新配置...")
            
            # 验证新配置
            if not self._validate_config(new_config):
                logger.error("新配置验证失败")
                return False
            
            # 更新配置
            self.config.update(new_config)
            
            # 保存配置
            if not await self.save_config():
                logger.error("保存更新后的配置失败")
                return False
            
            logger.info("配置更新成功")
            return True
            
        except Exception as e:
            logger.error(f"更新配置失败: {e}")
            return False
    
    async def reset_config(self) -> bool:
        """重置配置为默认值"""
        try:
            logger.info("重置配置...")
            
            # 创建默认配置
            default_config = self._get_default_config()
            
            # 更新配置
            self.config.clear()
            self.config.update(default_config)
            
            # 保存配置
            if not await self.save_config():
                logger.error("保存重置后的配置失败")
                return False
            
            logger.info("配置重置成功")
            return True
            
        except Exception as e:
            logger.error(f"重置配置失败: {e}")
            return False
    
    def get_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return self.config.copy()
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        return self.config.get(key, default)
    
    def set_config_value(self, key: str, value: Any) -> None:
        """设置配置值"""
        self.config[key] = value
    
    def get_status(self) -> Dict[str, Any]:
        """获取配置管理器状态"""
        return {
            'config_file': str(self.config_file),
            'config_exists': self.config_file.exists(),
            'auto_backup': self.auto_backup,
            'backup_count': len(list(self.backup_dir.glob('*.json'))),
            'config_size': self.config_file.stat().st_size if self.config_file.exists() else 0
        }
    
    async def _create_default_config(self) -> bool:
        """创建默认配置文件"""
        try:
            logger.info("创建默认配置文件...")
            
            # 获取默认配置
            default_config = self._get_default_config()
            
            # 更新配置
            self.config.update(default_config)
            
            # 保存配置
            if not await self.save_config():
                logger.error("保存默认配置失败")
                return False
            
            logger.info("默认配置文件创建成功")
            return True
            
        except Exception as e:
            logger.error(f"创建默认配置文件失败: {e}")
            return False
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            'GENERAL': {
                'session_name': 'tg_manager',
                'api_id': '',
                'api_hash': '',
                'session_path': 'sessions',
                'download_path': 'downloads',
                'upload_path': 'uploads',
                'tmp_path': 'tmp',
                'log_path': 'logs',
                'history_path': 'history'
            },
            'DOWNLOAD': {
                'download_path': 'downloads',
                'downloadSetting': []
            },
            'UPLOAD': {
                'directory': 'uploads',
                'target_channels': [],
                'options': {
                    'use_folder_name': True,
                    'read_title_txt': False,
                    'send_final_message': False,
                    'auto_thumbnail': True,
                    'enable_web_page_preview': False,
                    'final_message_html_file': ''
                }
            },
            'FORWARD': {
                'forward_channel_pairs': [],
                'forward_delay': 0.1,
                'tmp_path': 'tmp'
            },
            'MONITOR': {
                'monitor_channel_pairs': [],
                'duration': '2024-12-31'
            },
            'UI': {
                'theme': 'light_blue.xml',
                'language': 'zh_CN',
                'window_size': [1200, 800],
                'window_position': [100, 100],
                'auto_start': False,
                'minimize_to_tray': True
            }
        }
    
    def _validate_config(self, config: Dict[str, Any]) -> bool:
        """验证配置"""
        try:
            # 检查必需的配置项
            required_sections = ['GENERAL', 'DOWNLOAD', 'UPLOAD', 'FORWARD', 'MONITOR', 'UI']
            
            for section in required_sections:
                if section not in config:
                    logger.error(f"缺少必需的配置节: {section}")
                    return False
            
            # 检查GENERAL配置
            general = config.get('GENERAL', {})
            if not general.get('session_name'):
                logger.error("缺少session_name配置")
                return False
            
            # 检查路径配置
            paths = [
                general.get('session_path'),
                general.get('download_path'),
                general.get('upload_path'),
                general.get('tmp_path'),
                general.get('log_path'),
                general.get('history_path')
            ]
            
            for path in paths:
                if path and not self._is_valid_path(path):
                    logger.error(f"无效的路径配置: {path}")
                    return False
            
            logger.info("配置验证通过")
            return True
            
        except Exception as e:
            logger.error(f"配置验证失败: {e}")
            return False
    
    def _is_valid_path(self, path: str) -> bool:
        """检查路径是否有效"""
        try:
            # 检查路径是否包含非法字符
            invalid_chars = ['<', '>', ':', '"', '|', '?', '*']
            for char in invalid_chars:
                if char in path:
                    return False
            
            # 检查路径长度
            if len(path) > 260:  # Windows路径长度限制
                return False
            
            return True
            
        except Exception:
            return False
    
    async def _create_backup(self) -> None:
        """创建配置备份"""
        try:
            if not self.config_file.exists():
                return
            
            # 生成备份文件名
            import time
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            backup_file = self.backup_dir / f"config_backup_{timestamp}.json"
            
            # 复制配置文件
            import shutil
            shutil.copy2(self.config_file, backup_file)
            
            # 清理旧备份
            await self._cleanup_old_backups()
            
            logger.info(f"配置备份已创建: {backup_file}")
            
        except Exception as e:
            logger.error(f"创建配置备份失败: {e}")
    
    async def _cleanup_old_backups(self) -> None:
        """清理旧备份"""
        try:
            backup_files = list(self.backup_dir.glob('*.json'))
            
            if len(backup_files) <= self.max_backups:
                return
            
            # 按修改时间排序
            backup_files.sort(key=lambda f: f.stat().st_mtime)
            
            # 删除最旧的备份
            files_to_delete = backup_files[:-self.max_backups]
            for file in files_to_delete:
                file.unlink()
                logger.info(f"删除旧备份: {file}")
            
        except Exception as e:
            logger.error(f"清理旧备份失败: {e}")
    
    async def restore_backup(self, backup_file: str) -> bool:
        """从备份恢复配置"""
        try:
            backup_path = self.backup_dir / backup_file
            
            if not backup_path.exists():
                logger.error(f"备份文件不存在: {backup_path}")
                return False
            
            # 验证备份文件
            with open(backup_path, 'r', encoding='utf-8') as f:
                backup_config = json.load(f)
            
            if not self._validate_config(backup_config):
                logger.error("备份文件配置验证失败")
                return False
            
            # 恢复配置
            self.config.clear()
            self.config.update(backup_config)
            
            # 保存配置
            if not await self.save_config():
                logger.error("保存恢复的配置失败")
                return False
            
            logger.info(f"配置已从备份恢复: {backup_file}")
            return True
            
        except Exception as e:
            logger.error(f"从备份恢复配置失败: {e}")
            return False
    
    def get_backup_list(self) -> list:
        """获取备份文件列表"""
        try:
            backup_files = []
            for file in self.backup_dir.glob('*.json'):
                stat = file.stat()
                backup_files.append({
                    'filename': file.name,
                    'size': stat.st_size,
                    'modified': stat.st_mtime,
                    'path': str(file)
                })
            
            # 按修改时间排序（最新的在前）
            backup_files.sort(key=lambda f: f['modified'], reverse=True)
            return backup_files
            
        except Exception as e:
            logger.error(f"获取备份列表失败: {e}")
            return []
    
    async def cleanup(self) -> None:
        """清理资源"""
        try:
            logger.info("清理配置管理器...")
            
            # 保存当前配置
            await self.save_config()
            
            logger.info("配置管理器清理完成")
            
        except Exception as e:
            logger.error(f"清理配置管理器失败: {e}") 