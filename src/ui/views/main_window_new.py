"""
TG-Manager 主窗口视图
使用重构后的组件化主窗口
"""

from loguru import logger
from src.ui.components.main_window import MainWindow

# 直接使用组件化主窗口，不再需要在这里定义其他内容
# 所有主窗口功能都已经被拆分到各个模块并组合在一起了 