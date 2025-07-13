"""
UI配置管理器

负责UI配置的加载、保存、验证等功能。
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional
from loguru import logger

from config.ui_config_models import UIConfig

class UIConfigManager:
    """UI配置管理器"""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path("config.json")
        self.config: Optional[UIConfig] = None
    
    def load_config(self) -> Optional[UIConfig]:
        """加载配置"""
        try:
            if not self.config_path.exists():
                logger.warning(f"配置文件不存在: {self.config_path}")
                return None
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.config = UIConfig(**data)
            logger.info(f"配置加载成功: {self.config_path}")
            return self.config
            
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            return None
    
    def save_config(self, config: UIConfig) -> bool:
        """保存配置"""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config.model_dump(), f, indent=2, ensure_ascii=False)
            
            self.config = config
            logger.info(f"配置保存成功: {self.config_path}")
            return True
            
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            return False
    
    def get_config(self) -> Optional[UIConfig]:
        """获取当前配置"""
        return self.config
    
    def reload_config(self) -> Optional[UIConfig]:
        """重新加载配置"""
        return self.load_config() 