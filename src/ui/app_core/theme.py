"""
TG-Manager 主题管理模块
负责应用主题的加载和切换
"""

from PySide6.QtCore import QObject, Signal
from loguru import logger


class ThemeManagerWrapper(QObject):
    """主题管理器包装类，提供主题相关功能"""
    
    # 主题变更信号
    theme_changed = Signal(str)
    
    def __init__(self, theme_manager):
        """初始化主题管理器包装类
        
        Args:
            theme_manager: 主题管理器实例
        """
        super().__init__()
        self.theme_manager = theme_manager
    
    def apply_theme_from_config(self, config):
        """从配置中应用主题设置
        
        Args:
            config: 配置字典
        """
        if not config:
            return
        
        ui_config = config.get('UI', {})
        
        # 获取主题名称
        theme_name = ui_config.get('theme', '深色主题')
        logger.debug(f"从配置中加载主题: {theme_name}")
        
        # 应用主题
        if self.theme_manager.apply_theme(theme_name):
            logger.debug(f"成功应用主题 '{theme_name}'")
        else:
            logger.warning(f"应用主题 '{theme_name}' 失败")
    
    def get_current_theme_name(self):
        """获取当前主题名称
        
        Returns:
            str: 当前主题名称
        """
        # 委托给原始主题管理器
        return self.theme_manager.get_current_theme_name()
    
    def on_theme_changed(self, theme_name, config):
        """主题变更处理
        
        Args:
            theme_name: 新主题名称
            config: 配置字典
        """
        # 获取当前主题
        current_theme = self.theme_manager.get_current_theme_name()
        
        # 只有当新主题与当前主题不同时才应用
        if theme_name != current_theme:
            logger.info(f"正在切换主题: 从 {current_theme} 到 {theme_name}")
            
            # 应用主题
            self.theme_manager.apply_theme(theme_name)
            
            # 更新配置中的主题设置
            if 'UI' in config:
                config['UI']['theme'] = theme_name
            else:
                config['UI'] = {'theme': theme_name}
        else:
            logger.debug(f"忽略主题变更请求，当前已是 {theme_name} 主题") 