"""
TG-Manager 主窗口基础框架
定义主窗口的基本结构和初始化流程
"""

import logging
from loguru import logger
import os.path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QStyle, QSizePolicy,
    QStackedLayout, QLabel
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QResizeEvent, QPixmap

class MainWindowBase(QMainWindow):
    """主窗口基础类
    
    负责创建主窗口的基本框架和共用属性
    """
    
    # 定义信号
    config_saved = Signal(dict)
    window_state_changed = Signal(dict)
    
    def __init__(self, config=None):
        """初始化主窗口基础类
        
        Args:
            config: 配置对象
        """
        super().__init__()
        self.config = config or {}
        
        # 初始化UI
        self.setWindowTitle("TG-Manager")
        self.setWindowIcon(self._get_icon("app"))
        self.opened_views = {}  # 跟踪已打开的视图
        
        # 添加_is_window_state_loaded属性，用于跟踪窗口状态是否已加载
        self._is_window_state_loaded = False

        # 设置中心窗口部件
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.central_layout = QStackedLayout(self.central_widget)

        # 添加欢迎页
        self._create_welcome_widget()
        
        # 添加缩放策略，使窗口内容能够适应大小变化
        self.central_widget.setSizePolicy(
            QSizePolicy.Expanding, 
            QSizePolicy.Expanding
        )
        
        logger.info("主窗口基础框架初始化完成")
    
    def _create_welcome_widget(self):
        """创建欢迎页面"""
        self.welcome_widget = QWidget()
        welcome_layout = QVBoxLayout(self.welcome_widget)
        
        # 创建水印标签
        welcome_label = QLabel("<h1 style='color: rgba(120, 120, 120, 60%); margin: 20px;'>欢迎使用 TG-Manager</h1>"
                              "<p style='color: rgba(120, 120, 120, 60%); font-size: 16px;'>请从左侧导航树选择功能</p>")
        welcome_label.setAlignment(Qt.AlignCenter)
        welcome_label.setStyleSheet("""
            background-color: transparent;
            color: rgba(120, 120, 120, 60%);
        """)
        # 使用更大的字号
        font = welcome_label.font()
        font.setPointSize(font.pointSize() + 6)
        welcome_label.setFont(font)
        
        welcome_layout.addStretch(2)  # 顶部弹性空间
        welcome_layout.addWidget(welcome_label, 0, Qt.AlignCenter)  # 居中显示
        welcome_layout.addStretch(3)  # 底部弹性空间
        
        self.central_layout.addWidget(self.welcome_widget)
    
    def _get_icon(self, icon_name):
        """获取图标，如果找不到则使用默认图标
        
        Args:
            icon_name: 图标文件名称
            
        Returns:
            QIcon对象
        """
        icon_path = f"assets/icons/{icon_name}.png"
        if os.path.exists(icon_path):
            return QIcon(icon_path)
        else:
            # 如果找不到指定图标，尝试使用系统提供的标准图标
            standard_icons = {
                "login": QStyle.SP_DialogOpenButton,
                "exit": QStyle.SP_DialogCloseButton,
                "settings": QStyle.SP_FileDialogDetailedView,
                "import": QStyle.SP_FileDialogStart,
                "export": QStyle.SP_FileLinkIcon,
                "tasks": QStyle.SP_FileDialogListView,
                "logs": QStyle.SP_FileDialogInfoView,
                "pause": QStyle.SP_MediaPause,
                "resume": QStyle.SP_MediaPlay,
                "navigation": QStyle.SP_DirIcon,
                "task_overview": QStyle.SP_FileDialogListView,
                "toolbar": QStyle.SP_TitleBarMenuButton,
                "statusbar": QStyle.SP_TitleBarMinButton,
                "help": QStyle.SP_MessageBoxQuestion,
                "update": QStyle.SP_BrowserReload,
                "about": QStyle.SP_MessageBoxInformation,
                "app": QStyle.SP_DesktopIcon,
                "home": QStyle.SP_ArrowBack
            }
            
            if icon_name in standard_icons:
                return self.style().standardIcon(standard_icons[icon_name])
            
            # 如果没有匹配的标准图标，返回空图标
            return QIcon()
    
    def show_status_message(self, message, timeout=3000):
        """在状态栏显示消息
        
        Args:
            message: 显示的消息文本
            timeout: 显示时间(毫秒)，默认3秒
        """
        logger.debug(f"状态栏消息: {message}")
        self.statusBar().showMessage(message, timeout)
    
    def set_initialization_state(self, is_initializing=True):
        """设置应用程序初始化状态
        
        Args:
            is_initializing: 是否正在初始化
        """
        if is_initializing:
            # 显示初始化状态
            self.show_status_message("初始化中，请稍等...", 0)  # 0表示不自动清除
            # 禁用界面操作
            self.set_ui_enabled(False)
        else:
            # 清除初始化状态
            self.show_status_message("初始化完成", 3000)
            # 启用界面操作
            self.set_ui_enabled(True)
            
    def set_ui_enabled(self, enabled=True):
        """启用或禁用界面操作
        
        Args:
            enabled: 是否启用界面
        """
        # 设置中心窗口部件的启用状态
        self.central_widget.setEnabled(enabled)
        
        # 如果有侧边栏，设置侧边栏的启用状态
        if hasattr(self, 'sidebar_dock'):
            self.sidebar_dock.setEnabled(enabled)
            
        # 如果有菜单栏，设置菜单栏的启用状态
        if hasattr(self, 'menuBar'):
            menu_bar = self.menuBar()
            if menu_bar:
                menu_bar.setEnabled(enabled)
                
        # 如果有工具栏，设置工具栏的启用状态
        if hasattr(self, 'toolbar'):
            self.toolbar.setEnabled(enabled)
            
        # 更新状态栏的样式以提供视觉反馈
        if not enabled:
            self.statusBar().setStyleSheet("background-color: #FFEBEE;")  # 淡红色背景
        else:
            self.statusBar().setStyleSheet("")  # 恢复默认样式 