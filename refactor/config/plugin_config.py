"""
插件配置模块

定义插件配置相关的类和函数。
"""

from typing import Any, Dict, Optional
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class PluginConfig:
    """插件配置类"""
    name: str
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)
    path: Optional[Path] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'name': self.name,
            'enabled': self.enabled,
            'config': self.config,
            'path': str(self.path) if self.path else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PluginConfig':
        """从字典创建实例"""
        return cls(
            name=data.get('name', ''),
            enabled=data.get('enabled', True),
            config=data.get('config', {}),
            path=Path(data['path']) if data.get('path') else None
        )

def load_plugin_config(config_path: Path) -> Dict[str, PluginConfig]:
    """加载插件配置"""
    # TODO: 实现插件配置加载逻辑
    return {}

def save_plugin_config(config_path: Path, plugins: Dict[str, PluginConfig]) -> bool:
    """保存插件配置"""
    # TODO: 实现插件配置保存逻辑
    return True 