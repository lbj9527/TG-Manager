"""
TG-Manager 主题管理器
负责管理应用程序的主题样式和切换
"""

from PySide6.QtWidgets import QApplication
from qt_material import apply_stylesheet, list_themes

from src.utils.logger import get_logger

logger = get_logger()


class ThemeManager:
    """主题管理器，负责应用程序主题的切换和管理"""
    
    # 主题名称映射，用于在界面显示的名称和实际主题文件之间进行转换
    THEME_MAP = {
        "浅色主题": "light_cyan.xml",
        "深色主题": "dark_teal.xml",
        "蓝色主题": "light_blue.xml",
        "紫色主题": "dark_purple.xml",
        "红色主题": "light_red.xml",
        "绿色主题": "dark_lightgreen.xml",
        "琥珀色主题": "light_amber.xml",
        "粉色主题": "dark_pink.xml",
        "黄色主题": "light_yellow.xml",
        "青色主题": "dark_cyan.xml"
    }
    
    # 反向映射，用于从实际主题文件获取界面显示的名称
    REVERSE_THEME_MAP = {v: k for k, v in THEME_MAP.items()}
    
    def __init__(self):
        """初始化主题管理器"""
        self.current_theme = None
        self.app = None
    
    def initialize(self, app):
        """初始化主题管理器
        
        Args:
            app: QApplication实例
        """
        self.app = app
        logger.debug("主题管理器初始化完成")
    
    def get_available_themes(self):
        """获取所有可用的主题名称
        
        Returns:
            list: 可用主题名称列表
        """
        return list(self.THEME_MAP.keys())
    
    def get_raw_theme_list(self):
        """获取原始主题文件列表
        
        Returns:
            list: 原始主题文件列表
        """
        return list_themes()
    
    def apply_theme(self, theme_name):
        """应用指定的主题
        
        Args:
            theme_name (str): 主题名称，必须是可用主题之一
        """
        if not self.app:
            logger.error("主题管理器未初始化")
            return False
            
        try:
            # 检查是否是用户界面主题名称并转换为实际主题文件名
            if theme_name in self.THEME_MAP:
                theme_file = self.THEME_MAP[theme_name]
            else:
                # 检查是否是原始主题文件名
                if theme_name in self.REVERSE_THEME_MAP:
                    theme_file = theme_name
                else:
                    # 如果都不是，默认使用深色主题
                    logger.warning(f"未知主题名称: {theme_name}，将使用默认深色主题")
                    theme_file = "dark_teal.xml"
                    theme_name = self.REVERSE_THEME_MAP.get(theme_file, "深色主题")
            
            logger.info(f"正在应用主题: {theme_name} ({theme_file})")
            
            # 应用Material主题
            apply_stylesheet(
                app=QApplication.instance(), 
                theme=theme_file,
                invert_secondary=self._should_invert_secondary(theme_file)
            )
            
            # 修复深色主题下文本框文字颜色问题
            if theme_file.startswith("dark_"):
                extra_styles = """
                QLineEdit {
                    color: #FFFFFF;
                }
                QSpinBox, QDoubleSpinBox {
                    color: #FFFFFF;
                }
                QComboBox {
                    color: #FFFFFF;
                }
                QTextEdit, QPlainTextEdit {
                    color: #FFFFFF;
                }
                """
                QApplication.instance().setStyleSheet(QApplication.instance().styleSheet() + extra_styles)
                logger.debug("已应用深色主题文本颜色修复")
            
            # 保存当前主题名称
            self.current_theme = theme_file
            return True
        except Exception as e:
            logger.error(f"应用主题失败: {e}")
            return False
    
    def _should_invert_secondary(self, theme_file):
        """判断是否应该反转次要颜色
        
        某些主题可能需要反转次要颜色以获得更好的对比度
        
        Args:
            theme_file: 主题文件名
            
        Returns:
            bool: 是否应该反转次要颜色
        """
        # 为深色主题反转次要颜色
        return theme_file.startswith("dark_")
    
    def get_current_theme_name(self):
        """获取当前主题的显示名称
        
        Returns:
            str: 当前主题的显示名称
        """
        if not self.current_theme:
            return "深色主题"
        
        return self.REVERSE_THEME_MAP.get(self.current_theme, "深色主题")
    
    def get_current_theme_file(self):
        """获取当前主题的文件名
        
        Returns:
            str: 当前主题的文件名
        """
        return self.current_theme or "dark_teal.xml"


# 单例实例
_instance = None

def get_theme_manager():
    """获取主题管理器单例实例
    
    Returns:
        ThemeManager: 主题管理器实例
    """
    global _instance
    if _instance is None:
        _instance = ThemeManager()
    return _instance 