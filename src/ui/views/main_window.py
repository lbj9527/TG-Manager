"""
TG-Manager 主窗口
主界面窗口，包含菜单栏、工具栏和中央部件
"""

import logging
from loguru import logger
import os.path
import datetime
import json
from copy import deepcopy
import psutil
import aiohttp
import asyncio
import time

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QDockWidget, 
    QMessageBox, QStackedLayout, QStyle, QSizePolicy,
    QSplitter, QFileDialog, QDialog, QFormLayout, QLineEdit, 
    QDialogButtonBox, QLabel, QCheckBox, QToolBar, QStatusBar,
    QHBoxLayout, QStackedWidget, QScrollArea, QMenu, QSystemTrayIcon
)
from PySide6.QtCore import Qt, Slot, Signal, QByteArray, QSize, QTimer, QRegularExpression
from PySide6.QtGui import QAction, QIcon, QResizeEvent, QPixmap, QRegularExpressionValidator


class MainWindow(QMainWindow):
    """主窗口类
    
    负责创建和管理主窗口界面，包括菜单、工具栏、状态栏和主要视图。
    """
    
    # 定义信号
    config_saved = Signal(dict)
    window_state_changed = Signal(dict)
    
    def __init__(self, config=None):
        """初始化主窗口
        
        Args:
            config: 配置对象
        """
        super().__init__()
        self.config = config or {}
        
        # 初始化UI
        self.setWindowTitle("TG-Manager")
        self.setWindowIcon(self._get_icon("app"))
        self.opened_views = {}  # 跟踪已打开的视图

        # 设置中心窗口部件
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.central_layout = QStackedLayout(self.central_widget)

        # 添加欢迎页
        self.welcome_widget = QWidget()
        welcome_layout = QVBoxLayout(self.welcome_widget)
        
        # 创建水印标签，取代原来的QMessageBox
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

        # 界面元素初始化
        self._create_menu_bar()
        self._create_tool_bar()
        self._create_status_bar()
        
        # 创建停靠面板，但暂时不添加到窗口
        self._create_navigation_tree()
        self._create_task_overview()
        
        # 创建左侧分割器，管理导航树和任务概览
        self._create_sidebar_splitter()
        
        # 创建系统托盘图标和菜单
        self._create_system_tray()
        
        # 加载窗口状态
        self._load_window_state()
        
        # 连接信号和槽
        self._connect_signals()
        
        # 添加示例任务（仅用于UI布局展示）
        self._add_sample_tasks()
        
        logger.info("主窗口初始化完成")
    
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
    
    def _create_menu_bar(self):
        """创建菜单栏"""
        # 主菜单栏
        self.menubar = self.menuBar()
        
        # 文件菜单
        self.file_menu = self.menubar.addMenu("文件")
        
        # 登录动作
        login_action = QAction("登录", self)
        login_action.setIcon(self._get_icon("login"))
        login_action.setShortcut("Ctrl+L")
        login_action.setStatusTip("登录到Telegram账号")
        login_action.triggered.connect(self._handle_login)
        self.file_menu.addAction(login_action)
        
        # 设置动作
        settings_action = QAction("设置", self)
        settings_action.setIcon(self._get_icon("settings"))
        settings_action.setShortcut("Ctrl+,")
        settings_action.setStatusTip("打开系统设置")
        settings_action.triggered.connect(self._open_settings)
        self.file_menu.addAction(settings_action)
        
        # 退出动作
        exit_action = QAction("退出", self)
        exit_action.setIcon(self._get_icon("exit"))
        exit_action.setShortcut("Ctrl+Q")
        exit_action.setStatusTip("退出应用程序")
        exit_action.triggered.connect(self.close)
        self.file_menu.addAction(exit_action)
        
        # 配置菜单
        self.config_menu = self.menubar.addMenu("配置")
        
        # 导入配置
        import_config_action = QAction("导入配置", self)
        import_config_action.setIcon(self._get_icon("import"))
        import_config_action.setShortcut("Ctrl+I")
        import_config_action.setStatusTip("从文件导入配置")
        import_config_action.triggered.connect(self._import_config)
        self.config_menu.addAction(import_config_action)
        
        # 导出配置
        export_config_action = QAction("导出配置", self)
        export_config_action.setIcon(self._get_icon("export"))
        export_config_action.setShortcut("Ctrl+E")
        export_config_action.setStatusTip("导出配置到文件")
        export_config_action.triggered.connect(self._export_config)
        self.config_menu.addAction(export_config_action)
        
        # 工具菜单
        self.tools_menu = self.menubar.addMenu("工具")
        
        # 任务管理器
        task_manager_action = QAction("任务管理器", self)
        task_manager_action.setIcon(self._get_icon("tasks"))
        task_manager_action.setShortcut("Ctrl+T")
        task_manager_action.setStatusTip("打开任务管理器")
        task_manager_action.triggered.connect(self._open_task_manager)
        self.tools_menu.addAction(task_manager_action)
        
        # 日志查看器
        log_viewer_action = QAction("日志查看器", self)
        log_viewer_action.setIcon(self._get_icon("logs"))
        log_viewer_action.setShortcut("Ctrl+G")
        log_viewer_action.setStatusTip("打开日志查看器")
        log_viewer_action.triggered.connect(self._open_log_viewer)
        self.tools_menu.addAction(log_viewer_action)
        
        # 任务分隔线
        self.tools_menu.addSeparator()
        
        # 暂停所有任务
        pause_all_action = QAction("暂停所有任务", self)
        pause_all_action.setIcon(self._get_icon("pause"))
        pause_all_action.setShortcut("Ctrl+P")
        pause_all_action.setStatusTip("暂停所有正在执行的任务")
        pause_all_action.triggered.connect(self._pause_all_tasks)
        self.tools_menu.addAction(pause_all_action)
        
        # 恢复所有任务
        resume_all_action = QAction("恢复所有任务", self)
        resume_all_action.setIcon(self._get_icon("resume"))
        resume_all_action.setShortcut("Ctrl+R")
        resume_all_action.setStatusTip("恢复所有暂停的任务")
        resume_all_action.triggered.connect(self._resume_all_tasks)
        self.tools_menu.addAction(resume_all_action)
        
        # 视图菜单
        self.view_menu = self.menubar.addMenu("视图")
        
        # 显示/隐藏侧边栏
        self.show_sidebar_action = QAction("侧边栏", self)
        self.show_sidebar_action.setIcon(self._get_icon("navigation"))
        self.show_sidebar_action.setShortcut("Ctrl+B")
        self.show_sidebar_action.setStatusTip("显示或隐藏侧边栏")
        self.show_sidebar_action.setCheckable(True)
        self.show_sidebar_action.setChecked(True)
        self.show_sidebar_action.triggered.connect(self._toggle_sidebar)
        self.view_menu.addAction(self.show_sidebar_action)
        
        # 视图分隔线
        self.view_menu.addSeparator()
        
        # 工具栏可见性
        self.show_toolbar_action = QAction("工具栏", self)
        self.show_toolbar_action.setIcon(self._get_icon("toolbar"))
        self.show_toolbar_action.setShortcut("Ctrl+Shift+T")
        self.show_toolbar_action.setStatusTip("显示或隐藏工具栏")
        self.show_toolbar_action.setCheckable(True)
        self.show_toolbar_action.setChecked(True)
        self.show_toolbar_action.triggered.connect(self._toggle_toolbar)
        self.view_menu.addAction(self.show_toolbar_action)
        
        # 状态栏可见性
        self.show_statusbar_action = QAction("状态栏", self)
        self.show_statusbar_action.setIcon(self._get_icon("statusbar"))
        self.show_statusbar_action.setShortcut("Ctrl+Shift+S")
        self.show_statusbar_action.setStatusTip("显示或隐藏状态栏")
        self.show_statusbar_action.setCheckable(True)
        self.show_statusbar_action.setChecked(True)
        self.show_statusbar_action.triggered.connect(self._toggle_statusbar)
        self.view_menu.addAction(self.show_statusbar_action)
        
        # 帮助菜单
        self.help_menu = self.menubar.addMenu("帮助")
        
        # 帮助文档
        help_doc_action = QAction("帮助文档", self)
        help_doc_action.setIcon(self._get_icon("help"))
        help_doc_action.setShortcut("F1")
        help_doc_action.setStatusTip("查看帮助文档")
        help_doc_action.triggered.connect(self._show_help_doc)
        self.help_menu.addAction(help_doc_action)
        
        # 检查更新
        check_update_action = QAction("检查更新", self)
        check_update_action.setIcon(self._get_icon("update"))
        check_update_action.setShortcut("Ctrl+U")
        check_update_action.setStatusTip("检查应用程序更新")
        check_update_action.triggered.connect(self._check_update)
        self.help_menu.addAction(check_update_action)
        
        # 帮助分隔线
        self.help_menu.addSeparator()
        
        # 关于动作
        about_action = QAction("关于", self)
        about_action.setIcon(self._get_icon("about"))
        about_action.setShortcut("Ctrl+Shift+A")
        about_action.setStatusTip("关于本应用程序")
        about_action.triggered.connect(self._show_about)
        self.help_menu.addAction(about_action)
    
    def _create_tool_bar(self):
        """创建工具栏"""
        # 主工具栏
        self.toolbar = self.addToolBar("主工具栏")
        self.toolbar.setObjectName("main_toolbar")
        self.toolbar.setMovable(True)
        self.toolbar.setAllowedAreas(Qt.TopToolBarArea | Qt.LeftToolBarArea | Qt.RightToolBarArea | Qt.BottomToolBarArea)
        
        # 登录按钮
        self.login_action = QAction("登录", self)
        self.login_action.setIcon(self._get_icon("login"))
        self.login_action.setStatusTip("登录到Telegram账号")
        self.login_action.triggered.connect(self._handle_login)
        self.toolbar.addAction(self.login_action)
        
        # 分隔符
        self.toolbar.addSeparator()
        
        # 返回主页按钮
        self.home_action = QAction("返回主页", self)
        self.home_action.setIcon(self._get_icon("home"))
        self.home_action.setStatusTip("返回到欢迎页面")
        self.home_action.triggered.connect(self._return_to_welcome)
        self.toolbar.addAction(self.home_action)
        
        # 设置按钮
        self.settings_action = QAction("设置", self)
        self.settings_action.setIcon(self._get_icon("settings"))
        self.settings_action.setStatusTip("打开设置界面")
        self.settings_action.triggered.connect(self._open_settings)
        self.toolbar.addAction(self.settings_action)
        
        # 任务管理器按钮
        self.task_manager_action = QAction("任务管理器", self)
        self.task_manager_action.setIcon(self._get_icon("tasks"))
        self.task_manager_action.setStatusTip("打开任务管理器")
        self.task_manager_action.triggered.connect(self._open_task_manager)
        self.toolbar.addAction(self.task_manager_action)
        
        # 日志查看器按钮
        self.log_viewer_action = QAction("日志查看器", self)
        self.log_viewer_action.setIcon(self._get_icon("logs"))
        self.log_viewer_action.setStatusTip("打开日志查看器")
        self.log_viewer_action.triggered.connect(self._open_log_viewer)
        self.toolbar.addAction(self.log_viewer_action)
    
    def _create_status_bar(self):
        """创建状态栏"""
        # 获取状态栏对象
        status_bar = self.statusBar()
        
        # 创建状态栏各部分组件
        # 1. 功能提示区域 - 使用默认的临时消息区域
        status_bar.showMessage("就绪")
        
        # 2. 客户端状态
        self.client_status_label = QLabel("客户端: 未连接")
        self.client_status_label.setMinimumWidth(150)
        self.client_status_label.setStyleSheet("padding: 0 8px; color: #757575;")
        self.statusBar().addPermanentWidget(self.client_status_label)
        
        # 3. 网络状态
        self.network_status_label = QLabel("网络：未连接")
        self.network_status_label.setMinimumWidth(150)
        self.network_status_label.setStyleSheet("padding: 0 8px; color: #F44336;")  # 红色
        self.statusBar().addPermanentWidget(self.network_status_label)
        
        # 4. CPU/内存使用率
        self.resource_usage_label = QLabel("CPU: -- | 内存: --")
        self.resource_usage_label.setMinimumWidth(200)
        self.resource_usage_label.setStyleSheet("padding: 0 8px; color: #4CAF50;")
        self.statusBar().addPermanentWidget(self.resource_usage_label)
        
        # 添加任务统计标签
        self.task_stats_label = QLabel("任务: 0 运行中 | 0 等待中 | 0 已完成")
        self.task_stats_label.setMinimumWidth(250)
        self.task_stats_label.setStyleSheet("padding: 0 8px; color: #2196F3;")
        self.statusBar().addPermanentWidget(self.task_stats_label)
        
        # 设置定时器，定期更新资源使用率
        self.resource_timer = QTimer(self)
        self.resource_timer.timeout.connect(self._update_resource_usage)
        self.resource_timer.start(5000)  # 每5秒更新一次
        
        # 设置网络状态检查定时器
        self.network_timer = QTimer(self)
        self.network_timer.timeout.connect(self._check_network_status)
        self.network_timer.start(10000)  # 每10秒检查一次
        
        # 立即更新一次状态
        self._update_resource_usage()
        self._check_network_status()
    
    def _create_navigation_tree(self):
        """创建导航树组件"""
        from src.ui.components.navigation_tree import NavigationTree
        
        # 创建导航树
        self.nav_tree = NavigationTree()
        
        # 创建导航区域停靠窗口（用于独立使用）
        self.nav_dock = QDockWidget("导航", self)
        self.nav_dock.setObjectName("navigation_dock")
        self.nav_dock.setWidget(self.nav_tree)
        self.nav_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.nav_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        
        # 连接导航树的项目选择信号
        self.nav_tree.item_selected.connect(self._handle_navigation)
    
    def _create_task_overview(self):
        """创建任务概览组件"""
        from src.ui.components.task_overview import TaskOverview
        
        # 创建任务概览组件
        self.task_overview = TaskOverview()
        
        # 创建任务概览停靠窗口（用于独立使用）
        self.task_dock = QDockWidget("任务概览", self)
        self.task_dock.setObjectName("task_overview_dock")
        self.task_dock.setWidget(self.task_overview)
        self.task_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)
        self.task_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        
        # 连接任务相关信号
        self.task_overview.view_all_tasks_clicked.connect(self._open_task_manager)
    
    def _connect_signals(self):
        """连接信号和槽"""
        # 窗口状态变化信号
        self.window_state_changed.connect(self._save_window_state)
        
        # 侧边栏导航树信号
        self.nav_tree.item_selected.connect(self._handle_navigation)
        
        # 工具栏移动信号 - 捕获工具栏被移动的事件
        self.toolbar.movableChanged.connect(self._on_toolbar_state_changed)
        self.toolbar.topLevelChanged.connect(self._on_toolbar_state_changed)
        self.toolbar.allowedAreasChanged.connect(self._on_toolbar_state_changed)
        self.toolbar.orientationChanged.connect(self._on_toolbar_state_changed)
        self.toolbar.visibilityChanged.connect(self._on_toolbar_state_changed)
        
        # 在工具栏区域鼠标释放时保存状态，捕获拖动结束事件
        self.toolbar.installEventFilter(self)

    def _on_toolbar_state_changed(self, _=None):
        """工具栏状态改变时触发，保存窗口状态"""
        # 状态改变后延迟保存窗口状态，确保已完成移动
        logger.debug("工具栏状态已改变，准备保存")
        QTimer.singleShot(100, self._save_current_state)
    
    def _save_current_state(self):
        """保存当前窗口状态（只保存窗口几何信息和工具栏位置等布局状态）
        
        注意：此方法只会保存窗口的布局相关配置，不会影响其他配置项如主题设置等。
        这些布局状态没有单独的保存按钮，因此会自动保存，以便在下次启动时恢复布局。
        """
        window_state = {
            'geometry': self.saveGeometry(),
            'state': self.saveState()
        }
        logger.debug("保存窗口布局状态，包括窗口几何信息和工具栏位置")
        self.window_state_changed.emit(window_state)

    def showEvent(self, event):
        """窗口显示事件
        
        Args:
            event: 窗口显示事件
        """
        super().showEvent(event)
        # 保留原本的窗口状态保存，但延长延迟时间，确保布局完全稳定
        QTimer.singleShot(1000, self._save_current_state)
    
    def _toggle_sidebar(self, checked):
        """切换侧边栏的可见性
        
        Args:
            checked: 是否显示
        """
        if hasattr(self, 'sidebar_dock'):
            self.sidebar_dock.setVisible(checked)
    
    def _handle_navigation(self, item_id, item_data):
        """处理导航树项目的点击事件
        
        Args:
            item_id: 树项ID
            item_data: 树项关联数据
        """
        logger.debug(f"处理导航: {item_id} -> {item_data}")
        
        # 视图已经存在，则显示它
        if item_id in self.opened_views:
            self.central_layout.setCurrentWidget(self.opened_views[item_id])
            return
            
        # 获取功能名称
        function_name = item_data.get('function', '')
        
        # 根据功能名称创建对应的视图
        view = None
        
        try:
            if function_name == 'download':
                from src.ui.views.download_view import DownloadView
                view = DownloadView(self.config)
                
            elif function_name == 'upload':
                from src.ui.views.upload_view import UploadView
                view = UploadView(self.config)
                
            elif function_name == 'forward':
                from src.ui.views.forward_view import ForwardView
                view = ForwardView(self.config)
                
            elif function_name == 'monitor':
                from src.ui.views.listen_view import ListenView
                view = ListenView(self.config)
                
            elif function_name == 'task_manager':
                from src.ui.views.task_view import TaskView
                view = TaskView(self.config)
                
            elif function_name == 'help':
                from src.ui.views.help_doc_view import HelpDocView
                view = HelpDocView(self.config, self)
                
            elif function_name == 'logs':
                from src.ui.views.log_viewer_view import LogViewerView
                view = LogViewerView(self.config, self)
                
            elif function_name == 'qt_asyncio_test':
                from src.ui.views.qt_asyncio_test_view import AsyncTestView
                view = AsyncTestView(self.config, self)
                
            else:
                # 未知功能，显示提示信息
                QMessageBox.information(
                    self,
                    "功能未实现",
                    f"功能 '{function_name}' 尚未实现。",
                    QMessageBox.Ok
                )
                return
                
        except ImportError as e:
            # 视图模块导入失败的情况
            logger.error(f"导入视图失败: {e}")
            QMessageBox.warning(
                self,
                "模块加载失败",
                f"无法加载 '{function_name}' 模块，可能尚未实现。\n错误: {str(e)}",
                QMessageBox.Ok
            )
            return
            
        if view:
            # 连接视图的配置保存信号
            if hasattr(view, 'config_saved'):
                view.config_saved.connect(self.config_saved)
                
            # 连接任务相关信号（如适用）
            if function_name in ['download', 'upload', 'forward'] and hasattr(view, 'tasks_updated'):
                view.tasks_updated.connect(self._update_task_statistics)
                logger.debug(f"已连接 {function_name} 视图的任务统计信号")
                
            # 添加视图到中心区域并记录
            self.central_layout.addWidget(view)
            self.opened_views[item_id] = view
            
            # 使新添加的视图可见
            self.central_layout.setCurrentWidget(view)
    
    def _show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self,
            "关于 TG-Manager",
            "<h3>TG-Manager</h3>"
            "<p>版本: 1.7.1</p>"
            "<p>一个功能强大的Telegram频道管理工具</p>"
            "<p>© 2023-2025 TG-Manager Team</p>"
        )
    
    def _pause_all_tasks(self):
        """暂停所有活动任务"""
        logger.info("暂停所有活动任务")
    
    def _resume_all_tasks(self):
        """恢复所有暂停的任务"""
        logger.info("恢复所有暂停的任务")
    
    def _load_window_state(self):
        """加载窗口状态（大小、位置、布局等）"""
        # 默认窗口大小，设置为相对合理的尺寸，适应大多数显示器
        self.resize(1000, 700)
        
        # 设置最小尺寸，确保窗口不会被缩放到过小而导致UI无法使用
        self.setMinimumSize(800, 600)
        
        # 尝试从配置加载窗口状态
        if isinstance(self.config, dict) and 'UI' in self.config:
            ui_config = self.config.get('UI', {})
            
            # 加载窗口几何形状
            if 'window_geometry' in ui_config:
                try:
                    geometry = ui_config.get('window_geometry')
                    if geometry:
                        logger.debug("正在恢复窗口几何形状")
                        self.restoreGeometry(QByteArray.fromBase64(geometry.encode()))
                except Exception as e:
                    logger.warning(f"恢复窗口几何形状失败: {e}")
            
            # 加载窗口状态（停靠窗口、工具栏位置等）
            if 'window_state' in ui_config:
                try:
                    state = ui_config.get('window_state')
                    if state:
                        logger.debug("正在恢复窗口状态，包括工具栏位置")
                        
                        # 尝试恢复窗口状态
                        success = self.restoreState(QByteArray.fromBase64(state.encode()))
                        
                        if not success:
                            logger.warning("恢复窗口状态返回失败，尝试替代方法")
                            # 尝试另一种方法恢复工具栏位置
                            try:
                                # 确保工具栏状态会正确读取
                                toolbar_settings = self.toolbar.saveState()
                                self.toolbar.restoreState(toolbar_settings)
                                logger.debug("已尝试使用替代方法恢复工具栏状态")
                            except Exception as e:
                                logger.warning(f"尝试恢复工具栏状态时出错: {e}")
                        else:
                            logger.debug("成功恢复窗口状态")
                except Exception as e:
                    logger.warning(f"恢复窗口状态失败: {e}")
                    
        # 添加缩放策略，使窗口内容能够适应大小变化
        self.central_widget.setSizePolicy(
            QSizePolicy.Expanding, 
            QSizePolicy.Expanding
        )
        
        # 确保工具栏连接了信号
        if hasattr(self, 'toolbar'):
            # 完全避免先断开连接，直接处理连接信号
            # 保存所有需要连接的工具栏信号和槽函数对，避免重复代码
            toolbar_signals = [
                self.toolbar.topLevelChanged,
                self.toolbar.movableChanged,
                self.toolbar.allowedAreasChanged,
                self.toolbar.orientationChanged,
                self.toolbar.visibilityChanged
            ]
            
            # 使用简单地连接方式，不尝试先断开，这样就不会触发警告
            for signal in toolbar_signals:
                # 在连接前不断开连接，PySide6会处理好重复连接的情况
                # 即使有重复连接也不会有问题，系统会忽略
                try:
                    signal.connect(self._on_toolbar_state_changed)
                    logger.debug(f"连接工具栏信号: {signal.__name__ if hasattr(signal, '__name__') else 'unknown signal'}")
                except Exception as e:
                    # 忽略任何连接过程中的错误
                    logger.debug(f"信号连接异常 (可忽略): {e}")
                    pass
        
        # 确保所有窗口元素正确显示
        self.update()
    
    def _save_window_state(self, state_data):
        """保存窗口状态
        
        Args:
            state_data: 窗口状态数据
        """
        try:
            ui_config = self.config.get('UI', {})
            
            # 更新窗口状态数据
            if 'geometry' in state_data:
                ui_config['window_geometry'] = state_data['geometry'].toBase64().data().decode()
                logger.debug("保存了窗口几何形状")
            
            if 'state' in state_data:
                ui_config['window_state'] = state_data['state'].toBase64().data().decode()
                logger.debug("保存了窗口状态，包括工具栏位置")
            
            # 更新配置
            self.config['UI'] = ui_config
            
            # 发送配置保存信号，传递完整配置字典
            # 注意：我们使用emit而不是直接触发_on_config_saved以避免循环调用
            # TGManagerApp类中的_on_config_saved方法会处理保存逻辑，确保保留主题设置
            self.config_saved.emit(self.config)
            
            logger.debug("窗口状态已成功保存到配置")
        except Exception as e:
            logger.error(f"保存窗口状态失败: {e}")
    
    def closeEvent(self, event):
        """窗口关闭事件处理
        
        Args:
            event: 关闭事件
        """
        # 获取退出前确认选项（如果配置不存在或者无法访问，则默认为True）
        confirm_exit = True
        if isinstance(self.config, dict) and 'UI' in self.config:
            ui_config = self.config.get('UI', {})
            if isinstance(ui_config, dict):
                confirm_exit = ui_config.get('confirm_exit', True)
        
        if confirm_exit:
            # 询问用户是否确认退出
            reply = QMessageBox.question(
                self, 
                "确认退出", 
                "确认要退出TG-Manager吗？\n任何未完成的任务将被中断。",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No
            )
            
            if reply != QMessageBox.Yes:
                # 拒绝关闭事件
                event.ignore()
                return
        
        # 停止所有计时器
        for timer_attr in ['resource_timer', 'network_timer']:
            if hasattr(self, timer_attr):
                timer = getattr(self, timer_attr)
                if timer.isActive():
                    logger.debug(f"停止计时器: {timer_attr}")
                    timer.stop()
        
        # 取消所有运行中的任务
        try:
            # 通知任务管理器停止所有任务
            if "task_manager" in self.opened_views:
                task_view = self.opened_views["task_manager"]
                if hasattr(task_view, 'cancel_all_tasks'):
                    logger.debug("请求任务管理器取消所有任务")
                    task_view.cancel_all_tasks()
        except Exception as e:
            logger.error(f"停止任务时出错: {e}")
        
        # 如果系统托盘图标存在，则隐藏
        if hasattr(self, 'tray_icon'):
            self.tray_icon.hide()
            
        # 接受关闭事件
        event.accept()
    
    def _handle_login(self):
        """处理用户登录"""
        try:
            # 创建登录表单对话框
            login_dialog = QDialog(self)
            login_dialog.setWindowTitle("登录Telegram")
            login_dialog.setMinimumWidth(400)
            
            # 创建布局
            main_layout = QVBoxLayout(login_dialog)
            
            # 添加说明标签
            info_label = QLabel("以下是您在设置中配置的Telegram API凭据和手机号码信息。点击'确定'开始登录。")
            info_label.setWordWrap(True)
            main_layout.addWidget(info_label)
            
            # 创建表单布局
            form_layout = QFormLayout()
            
            # 创建只读信息展示字段
            api_id_label = QLabel()
            api_hash_label = QLabel()
            phone_label = QLabel()
            
            # 从配置中加载API ID、Hash和手机号码（如果存在）
            if 'GENERAL' in self.config:
                if 'api_id' in self.config['GENERAL']:
                    api_id_label.setText(str(self.config['GENERAL']['api_id']))
                if 'api_hash' in self.config['GENERAL']:
                    # 只显示API Hash的一部分，保护隐私
                    api_hash = self.config['GENERAL']['api_hash']
                    masked_hash = api_hash[:6] + "..." + api_hash[-6:] if len(api_hash) > 12 else api_hash
                    api_hash_label.setText(masked_hash)
                if 'phone_number' in self.config['GENERAL'] and self.config['GENERAL']['phone_number']:
                    phone_label.setText(self.config['GENERAL']['phone_number'])
            
            # 添加表单字段
            form_layout.addRow("API ID:", api_id_label)
            form_layout.addRow("API Hash:", api_hash_label)
            form_layout.addRow("手机号码:", phone_label)
            
            # 创建按钮
            button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            button_box.accepted.connect(login_dialog.accept)
            button_box.rejected.connect(login_dialog.reject)
            
            # 组装布局
            main_layout.addLayout(form_layout)
            main_layout.addWidget(button_box)
            
            # 显示对话框
            result = login_dialog.exec_()
            
            # 如果用户点击了"确定"
            if result == QDialog.Accepted:
                # 检查配置中是否存在所需信息
                if 'GENERAL' not in self.config or 'api_id' not in self.config['GENERAL'] or \
                   'api_hash' not in self.config['GENERAL'] or 'phone_number' not in self.config['GENERAL'] or \
                   not self.config['GENERAL']['api_id'] or not self.config['GENERAL']['api_hash'] or \
                   not self.config['GENERAL']['phone_number']:
                    QMessageBox.warning(
                        self,
                        "配置不完整",
                        "请在设置中完成API凭据和手机号码的配置。",
                        QMessageBox.Ok
                    )
                    # 打开设置界面
                    self._open_settings()
                    return
                
                phone = self.config['GENERAL']['phone_number']
                
                # 显示登录进行中的消息
                self.statusBar().showMessage(f"登录中: {phone}")
                
                # 显示验证码输入对话框
                code = self._show_verification_code_dialog()
                
                if code:
                    # 显示登录成功消息，这里只是界面展示，实际登录逻辑后续实现
                    QMessageBox.information(
                        self,
                        "验证码已提交",
                        f"已接收验证码: {code}\n\n实际登录功能将在后续实现。",
                        QMessageBox.Ok
                    )
                else:
                    self.statusBar().showMessage("登录已取消")
                
                # 这里可以添加实际的登录逻辑
                # ...
                
        except Exception as e:
            logger.error(f"登录处理时出错: {e}")
            QMessageBox.critical(
                self,
                "登录错误",
                f"登录过程中发生错误: {str(e)}",
                QMessageBox.Ok
            )
            
    def _show_verification_code_dialog(self):
        """显示验证码输入对话框
        
        Returns:
            str: 用户输入的验证码，如果用户取消则返回None
        """
        try:
            # 创建验证码输入对话框
            code_dialog = QDialog(self)
            code_dialog.setWindowTitle("输入验证码")
            code_dialog.setMinimumWidth(350)
            
            # 创建布局
            layout = QVBoxLayout(code_dialog)
            
            # 添加说明标签
            info_label = QLabel("Telegram已向您的手机或Telegram应用发送了一个验证码，请在下方输入该验证码：")
            info_label.setWordWrap(True)
            layout.addWidget(info_label)
            
            # 创建验证码输入框
            code_input = QLineEdit()
            code_input.setPlaceholderText("请输入验证码")
            code_input.setMaxLength(5)  # 验证码通常为5位数字
            
            # 设置输入验证 - 只允许输入数字
            validator = QRegularExpressionValidator(QRegularExpression("\\d+"))
            code_input.setValidator(validator)
            
            layout.addWidget(code_input)
            
            # 添加验证码提示
            hint_label = QLabel("提示: 验证码通常为5位数字，请检查您的Telegram应用或手机短信。")
            hint_label.setStyleSheet("color: gray; font-size: 10pt;")
            hint_label.setWordWrap(True)
            layout.addWidget(hint_label)
            
            # 创建按钮
            button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            button_box.accepted.connect(code_dialog.accept)
            button_box.rejected.connect(code_dialog.reject)
            layout.addWidget(button_box)
            
            # 设置默认按钮
            ok_button = button_box.button(QDialogButtonBox.Ok)
            ok_button.setDefault(True)
            
            # 禁用OK按钮，直到输入了验证码
            ok_button.setEnabled(False)
            
            # 连接输入变化信号
            def on_text_changed(text):
                ok_button.setEnabled(len(text) > 0)
            
            code_input.textChanged.connect(on_text_changed)
            
            # 显示对话框
            result = code_dialog.exec_()
            
            if result == QDialog.Accepted:
                return code_input.text()
            else:
                return None
                
        except Exception as e:
            logger.error(f"显示验证码对话框时出错: {e}")
            return None
    
    def _open_settings(self):
        """打开设置界面"""
        logger.debug("尝试打开设置视图")
        try:
            # 先检查是否已经打开
            if "settings_view" in self.opened_views:
                logger.debug("设置视图已存在，切换到该视图")
                self.central_layout.setCurrentWidget(self.opened_views["settings_view"])
                return
            
            # 直接创建并显示设置视图
            from src.ui.views.settings_view import SettingsView
            
            # 创建设置视图
            settings_view = SettingsView(self.config, self)
            
            # 添加到中心区域
            self.central_layout.addWidget(settings_view)
            self.opened_views["settings_view"] = settings_view
            
            # 使设置视图可见
            self.central_layout.setCurrentWidget(settings_view)
            
            # 连接设置视图的信号
            if hasattr(settings_view, 'settings_saved'):
                settings_view.settings_saved.connect(self._on_settings_saved)
            
            logger.info("成功打开设置视图")
            
        except Exception as e:
            logger.error(f"打开设置视图失败: {e}", exc_info=True)
            QMessageBox.warning(
                self,
                "模块加载失败",
                f"无法加载设置模块。\n错误: {str(e)}",
                QMessageBox.Ok
            )
    
    def _open_task_manager(self):
        """打开任务管理器"""
        logger.debug("尝试打开任务管理器视图")
        try:
            # 先检查是否已经打开
            if "task_manager" in self.opened_views:
                logger.debug("任务管理器视图已存在，切换到该视图")
                self.central_layout.setCurrentWidget(self.opened_views["task_manager"])
                return
                
            # 通过导航树API找到任务管理项并触发点击
            logger.debug("尝试通过导航树打开任务管理器视图")
            if self.nav_tree.select_item_by_function("task_manager"):
                logger.debug("通过导航树成功打开任务管理器视图")
                return
                
            # 如果通过导航树无法打开，直接创建并显示
            logger.debug("直接创建任务管理器视图")
            from src.ui.views.task_view import TaskView
            
            # 创建任务管理器视图
            task_manager = TaskView(self.config, self)
            
            # 添加到中心区域
            self.central_layout.addWidget(task_manager)
            self.opened_views["task_manager"] = task_manager
            
            # 使任务管理器可见
            self.central_layout.setCurrentWidget(task_manager)
            
            # 连接任务管理器的信号
            if hasattr(task_manager, 'task_pause'):
                task_manager.task_pause.connect(self._pause_task)
            if hasattr(task_manager, 'task_resume'):
                task_manager.task_resume.connect(self._resume_task)
            if hasattr(task_manager, 'task_cancel'):
                task_manager.task_cancel.connect(self._cancel_task)
            if hasattr(task_manager, 'task_remove'):
                task_manager.task_remove.connect(self._remove_task)
            if hasattr(task_manager, 'tasks_updated'):
                task_manager.tasks_updated.connect(self._update_task_statistics)
            
            logger.info("成功打开任务管理器视图")
            
        except Exception as e:
            logger.error(f"打开任务管理器视图失败: {e}", exc_info=True)
            QMessageBox.warning(
                self,
                "模块加载失败",
                f"无法加载任务管理器模块。\n错误: {str(e)}",
                QMessageBox.Ok
            )
    
    def _open_log_viewer(self):
        """打开日志查看器"""
        logger.debug("尝试打开日志查看器视图")
        try:
            # 先检查是否已经打开
            if "log_viewer" in self.opened_views:
                logger.debug("日志查看器视图已存在，切换到该视图")
                self.central_layout.setCurrentWidget(self.opened_views["log_viewer"])
                return
                
            # 通过导航树API找到日志查看器项并触发点击
            logger.debug("尝试通过导航树打开日志查看器视图")
            if self.nav_tree.select_item_by_function("logs") or self.nav_tree.select_item("log_viewer"):
                logger.debug("通过导航树成功打开日志查看器视图")
                return
            
            # 如果通过导航树无法打开，直接创建并显示
            logger.debug("直接创建日志查看器视图")
            from src.ui.views.log_viewer_view import LogViewerView
            
            # 创建日志查看器视图
            log_viewer = LogViewerView(self.config, self)
            
            # 添加到中心区域
            self.central_layout.addWidget(log_viewer)
            self.opened_views["log_viewer"] = log_viewer
            
            # 使日志查看器可见
            self.central_layout.setCurrentWidget(log_viewer)
            
            logger.info("成功打开日志查看器视图")
            
        except Exception as e:
            logger.error(f"打开日志查看器视图失败: {e}", exc_info=True)
            QMessageBox.warning(
                self,
                "模块加载失败",
                f"无法加载日志查看器模块。\n错误: {str(e)}",
                QMessageBox.Ok
            )
    
    def _add_sample_tasks(self):
        """添加示例任务用于展示任务概览布局"""
        # 直接更新状态栏中的任务统计信息
        self._update_task_statistics(3, 2, 12)
        
        # 添加示例任务
        self.task_overview.add_task(
            "task1", "下载", "频道媒体下载", "运行中", 45
        )
        self.task_overview.add_task(
            "task2", "上传", "本地媒体上传", "运行中", 78
        )
        self.task_overview.add_task(
            "task3", "转发", "频道消息转发", "等待中", 0
        )
    
    def _update_task_statistics(self, running=0, waiting=0, completed=0):
        """更新状态栏中的任务统计信息
        
        Args:
            running: 运行中的任务数量
            waiting: 等待中的任务数量
            completed: 已完成的任务数量
        """
        try:
            # 更新任务统计文本
            self.task_stats_label.setText(f"任务: {running} 运行中 | {waiting} 等待中 | {completed} 已完成")
            
            # 根据任务状态设置颜色
            if running > 0:
                # 有运行中的任务，使用蓝色
                self.task_stats_label.setStyleSheet("padding: 0 8px; color: #2196F3;") 
            elif waiting > 0:
                # 有等待中的任务，使用橙色
                self.task_stats_label.setStyleSheet("padding: 0 8px; color: #FF9800;")
            else:
                # 没有活动任务，使用绿色
                self.task_stats_label.setStyleSheet("padding: 0 8px; color: #4CAF50;")
                
            # 同时更新任务概览中的统计信息，如果存在
            if hasattr(self, 'task_overview') and self.task_overview:
                self.task_overview.update_counters(running, completed, waiting, 0)
                
        except Exception as e:
            logger.error(f"更新任务统计信息失败: {e}")
            self.task_stats_label.setText("任务: 统计错误")
            self.task_stats_label.setStyleSheet("padding: 0 8px; color: #F44336;")
    
    def _import_config(self):
        """导入配置文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "导入配置文件",
            "",
            "JSON文件 (*.json);;所有文件 (*.*)"
        )
        
        if not file_path:
            return
            
        try:
            # 读取配置文件
            with open(file_path, 'r', encoding='utf-8') as file:
                imported_config = json.load(file)
            
            # 验证导入的配置文件结构
            if not isinstance(imported_config, dict):
                raise ValueError("导入的配置文件格式无效，应为JSON对象")
            
            # 提示用户确认
            reply = QMessageBox.question(
                self,
                "确认导入",
                "导入此配置文件将覆盖当前配置，是否继续？\n"
                "注意：某些设置可能需要重启应用才能生效。",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply != QMessageBox.Yes:
                return
            
            # 合并配置
            self.config.update(imported_config)
            
            # 发出配置更新信号
            self.config_saved.emit(self.config)
            
            # 显示成功消息
            QMessageBox.information(
                self,
                "导入成功",
                "配置文件已成功导入。\n"
                "某些设置可能需要重启应用才能生效。",
                QMessageBox.Ok
            )
            
        except Exception as e:
            logger.error(f"导入配置文件失败: {e}")
            QMessageBox.critical(
                self,
                "导入失败",
                f"导入配置文件失败: {str(e)}",
                QMessageBox.Ok
            )
    
    def _export_config(self):
        """导出配置文件"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "导出配置文件",
            f"tg_manager_config_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON文件 (*.json);;所有文件 (*.*)"
        )
        
        if not file_path:
            return
            
        try:
            # 创建配置的副本，去除可能无法序列化的内容
            config_copy = deepcopy(self.config)
            
            # 写入配置文件，美化格式
            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump(config_copy, file, ensure_ascii=False, indent=4)
            
            # 显示成功消息
            QMessageBox.information(
                self,
                "导出成功",
                f"配置文件已成功导出到:\n{file_path}",
                QMessageBox.Ok
            )
            
        except Exception as e:
            logger.error(f"导出配置文件失败: {e}")
            QMessageBox.critical(
                self,
                "导出失败",
                f"导出配置文件失败: {str(e)}",
                QMessageBox.Ok
            )
    
    def _toggle_toolbar(self, checked):
        """切换工具栏的可见性
        
        Args:
            checked: 是否显示
        """
        self.toolbar.setVisible(checked)
    
    def _toggle_statusbar(self, checked):
        """切换状态栏的可见性
        
        Args:
            checked: 是否显示
        """
        self.statusBar().setVisible(checked)
    
    def _show_help_doc(self):
        """显示帮助文档"""
        try:
            # 通过导航树API找到帮助文档项并触发点击
            for item_id in ["help_doc", "documentation", "docs"]:
                if hasattr(self.nav_tree, 'select_item') and self.nav_tree.select_item(item_id):
                    return
            
            # 如果导航树中没有找到，直接创建并显示
            from src.ui.views.help_doc_view import HelpDocView
            
            # 创建帮助文档视图
            help_doc = HelpDocView(self.config, self)
            
            # 添加到中心区域
            self.central_layout.addWidget(help_doc)
            self.opened_views["help_doc"] = help_doc
            
            # 使帮助文档可见
            self.central_layout.setCurrentWidget(help_doc)
            
        except ImportError as e:
            logger.error(f"导入帮助文档视图失败: {e}")
            QMessageBox.warning(
                self,
                "模块加载失败",
                f"无法加载帮助文档模块。\n错误: {str(e)}",
                QMessageBox.Ok
            )
    
    def _check_update(self):
        """检查更新"""
        QMessageBox.information(
            self,
            "检查更新",
            "检查更新功能尚未实现。\n当前版本: 1.7.1",
            QMessageBox.Ok
        )
    
    def _create_sidebar_splitter(self):
        """创建左侧分割器，用于管理导航树和任务概览之间的比例"""
        # 移除之前添加的停靠窗口
        self.removeDockWidget(self.nav_dock)
        self.removeDockWidget(self.task_dock)
        
        # 创建新的停靠窗口，包含分割器
        self.sidebar_dock = QDockWidget("导航与任务", self)
        self.sidebar_dock.setObjectName("sidebar_dock")
        self.sidebar_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.sidebar_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        
        # 创建分割器
        self.sidebar_splitter = QSplitter(Qt.Vertical)
        
        # 为QSplitter设置一个固定的子控件大小策略，防止导航树在启动时改变高度
        self.sidebar_splitter.setChildrenCollapsible(False)
        self.sidebar_splitter.setOpaqueResize(True)
        
        # 添加控件到分割器
        self.sidebar_splitter.addWidget(self.nav_tree)
        self.sidebar_splitter.addWidget(self.task_overview)
        
        # 设置初始分割比例，调整为50%导航树，50%任务概览
        self.sidebar_splitter.setSizes([500, 500])
        
        # 在组件完全初始化后锁定尺寸，防止布局计算导致的高度变化
        QTimer.singleShot(0, lambda: self._init_splitter_sizes())
        
        # 将分割器添加到停靠窗口
        self.sidebar_dock.setWidget(self.sidebar_splitter)
        
        # 将停靠窗口添加到左侧区域
        self.addDockWidget(Qt.LeftDockWidgetArea, self.sidebar_dock)
    
    def _init_splitter_sizes(self):
        """初始化分割器尺寸，确保导航树高度稳定"""
        if hasattr(self, 'sidebar_splitter'):
            # 重新设置尺寸一次，以防止初始化过程中的计算误差
            current_sizes = self.sidebar_splitter.sizes()
            self.sidebar_splitter.setSizes(current_sizes)
    
    def resizeEvent(self, event: QResizeEvent):
        """窗口大小改变时的处理函数
        
        Args:
            event: 窗口大小改变事件
        """
        # 调用父类的处理函数
        super().resizeEvent(event)
        
        # 使用非立即触发的状态保存，减少资源消耗
        if hasattr(self, '_resize_timer'):
            # 如果已经有定时器，则重置它
            self._resize_timer.stop()
        else:
            # 创建延迟执行的定时器
            self._resize_timer = QTimer(self)
            self._resize_timer.setSingleShot(True)
            self._resize_timer.timeout.connect(self._handle_resize_completed)
        
        # 500毫秒后执行（只有当调整大小停止时才会触发）
        self._resize_timer.start(500)
    
    def _handle_resize_completed(self):
        """窗口大小调整完成后的处理"""
        if hasattr(self, 'sidebar_splitter'):
            # 获取当前窗口高度
            current_height = self.height()
            
            # 获取当前分割器尺寸
            current_sizes = self.sidebar_splitter.sizes()
            nav_height = current_sizes[0]  # 导航树当前高度
            
            # 只有当窗口高度大于阈值时才调整，防止在极小的窗口尺寸下产生问题
            if current_height > 400:
                # 调整为50%导航树，50%任务概览
                self.sidebar_splitter.setSizes([int(current_height * 0.5), int(current_height * 0.5)])
        
        # 发出窗口状态变化信号
        window_state = {
            'geometry': self.saveGeometry(),
            'state': self.saveState()
        }
        self.window_state_changed.emit(window_state)
    
    def _pause_task(self, task_id):
        """暂停任务
        
        Args:
            task_id: 任务ID
        """
        logger.info(f"暂停任务: {task_id}")
        
        # 这里应该调用业务逻辑层的任务暂停方法
        # 示例代码：self.task_manager.pause_task(task_id)
        
        # 暂时使用任务概览组件更新状态
        if hasattr(self, 'task_overview') and self.task_overview:
            self.task_overview.update_task_status(task_id, "已暂停")
        
        # 更新任务视图
        if "task_manager" in self.opened_views:
            task_view = self.opened_views["task_manager"]
            if hasattr(task_view, 'tasks') and task_id in task_view.tasks:
                task_data = task_view.tasks[task_id]
                task_data['status'] = "已暂停"
                task_view.add_task(task_data)  # 更新任务状态
        
        # 刷新任务统计
        self._refresh_task_statistics()
    
    def _resume_task(self, task_id):
        """恢复任务
        
        Args:
            task_id: 任务ID
        """
        logger.info(f"恢复任务: {task_id}")
        
        # 这里应该调用业务逻辑层的任务恢复方法
        # 示例代码：self.task_manager.resume_task(task_id)
        
        # 暂时使用任务概览组件更新状态
        if hasattr(self, 'task_overview') and self.task_overview:
            self.task_overview.update_task_status(task_id, "运行中")
        
        # 更新任务视图
        if "task_manager" in self.opened_views:
            task_view = self.opened_views["task_manager"]
            if hasattr(task_view, 'tasks') and task_id in task_view.tasks:
                task_data = task_view.tasks[task_id]
                task_data['status'] = "运行中"
                task_view.add_task(task_data)  # 更新任务状态
        
        # 刷新任务统计
        self._refresh_task_statistics()
    
    def _cancel_task(self, task_id):
        """取消任务
        
        Args:
            task_id: 任务ID
        """
        logger.info(f"取消任务: {task_id}")
        
        # 确认取消
        reply = QMessageBox.question(
            self,
            "确认取消",
            f"确定要取消任务 {task_id} 吗？此操作无法撤销。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
            
        # 这里应该调用业务逻辑层的任务取消方法
        # 示例代码：self.task_manager.cancel_task(task_id)
        
        # 暂时使用任务概览组件更新状态
        if hasattr(self, 'task_overview') and self.task_overview:
            self.task_overview.update_task_status(task_id, "已取消")
            # 在短暂延迟后从概览中移除任务
            QTimer.singleShot(3000, lambda: self.task_overview.remove_task(task_id))
        
        # 更新任务视图
        if "task_manager" in self.opened_views:
            task_view = self.opened_views["task_manager"]
            if hasattr(task_view, 'tasks') and task_id in task_view.tasks:
                # 从任务管理器中移除任务
                task_view.remove_task(task_id)
        
        # 刷新任务统计
        self._refresh_task_statistics()
    
    def _remove_task(self, task_id):
        """从界面移除已完成的任务
        
        Args:
            task_id: 任务ID
        """
        logger.info(f"移除任务: {task_id}")
        
        # 暂时使用任务概览组件移除任务
        if hasattr(self, 'task_overview') and self.task_overview:
            self.task_overview.remove_task(task_id)
        
        # 更新任务视图
        if "task_manager" in self.opened_views:
            task_view = self.opened_views["task_manager"]
            if hasattr(task_view, 'tasks') and task_id in task_view.tasks:
                # 从任务管理器中移除任务
                task_view.remove_task(task_id)
        
        # 刷新任务统计
        self._refresh_task_statistics()
    
    def _refresh_task_statistics(self):
        """刷新任务统计信息，从当前打开的视图和任务管理器中获取最新数据"""
        try:
            # 默认初始值
            running = 0
            waiting = 0
            completed = 0
            
            # 从任务管理视图获取数据（如果已打开）
            if "task_manager" in self.opened_views:
                task_view = self.opened_views["task_manager"]
                if hasattr(task_view, 'get_task_statistics'):
                    # 首选：任务管理器提供专门的统计方法
                    running, waiting, completed = task_view.get_task_statistics()
                elif hasattr(task_view, 'tasks'):
                    # 备选：手动统计任务数量
                    tasks = task_view.tasks
                    for task in tasks.values():
                        status = task.get('status', '').lower()
                        if status in ['运行中', 'running']:
                            running += 1
                        elif status in ['等待中', 'waiting', '排队中', 'queued']:
                            waiting += 1
                        elif status in ['已完成', 'completed', 'finished']:
                            completed += 1
            
            # 更新状态栏中的任务统计信息
            self._update_task_statistics(running, waiting, completed)
            
        except Exception as e:
            logger.error(f"刷新任务统计信息失败: {e}")
    
    def _update_resource_usage(self):
        """更新资源使用情况"""
        try:
            # 使用psutil库获取系统资源使用情况，不使用阻塞的interval参数
            cpu_usage = round(psutil.cpu_percent(interval=None), 1)
            
            # 获取内存使用情况
            memory = psutil.virtual_memory()
            memory_usage = round(memory.used / (1024 * 1024), 1)  # 转换为MB
            memory_total = round(memory.total / (1024 * 1024), 1)  # 转换为MB
            memory_percent = round(memory.percent, 1)
            
            # 格式化显示
            if memory_usage > 1024:
                # 如果超过1GB则显示为GB
                memory_text = f"{memory_usage / 1024:.1f}GB/{memory_total / 1024:.1f}GB ({memory_percent}%)"
            else:
                memory_text = f"{memory_usage:.0f}MB/{memory_total / 1024:.1f}GB ({memory_percent}%)"
            
            # 更新资源使用标签
            self.resource_usage_label.setText(f"CPU: {cpu_usage}% | 内存: {memory_text}")
            
            # 根据使用率设置不同的颜色
            if cpu_usage > 90 or memory_percent > 90:
                self.resource_usage_label.setStyleSheet("padding: 0 8px; color: #F44336;")  # 红色
            elif cpu_usage > 70 or memory_percent > 70:
                self.resource_usage_label.setStyleSheet("padding: 0 8px; color: #FF9800;")  # 橙色
            else:
                self.resource_usage_label.setStyleSheet("padding: 0 8px; color: #4CAF50;")  # 绿色
                
        except ImportError:
            # 如果没有psutil库，使用占位符数据
            self.resource_usage_label.setText("CPU: -- | 内存: --")
            logger.warning("未找到psutil库，无法获取系统资源使用情况")
            
        except Exception as e:
            # 其他错误情况
            self.resource_usage_label.setText("资源监控错误")
            logger.error(f"资源监控错误: {e}")
    
    def _update_client_status(self, connected=False, client_info=None):
        """更新客户端连接状态
        
        Args:
            connected: 是否已连接
            client_info: 客户端信息，如用户ID、名称等
        """
        if connected and client_info:
            # 如果已连接且有客户端信息，显示详细信息
            text = f"客户端: 已连接 ({client_info})"
            self.client_status_label.setStyleSheet("padding: 0 8px; color: #4CAF50;")  # 绿色
        elif connected:
            # 如果已连接但没有详细信息
            text = "客户端: 已连接"
            self.client_status_label.setStyleSheet("padding: 0 8px; color: #4CAF50;")  # 绿色
        else:
            # 未连接状态
            text = "客户端: 未连接"
            self.client_status_label.setStyleSheet("padding: 0 8px; color: #757575;")  # 灰色
        
        self.client_status_label.setText(text)
    
    def _check_network_status(self):
        """检查网络连接状态"""
        # 正确导入和使用create_task函数
        from src.utils.async_utils import create_task
        create_task(self._check_network_status_async())
    
    async def _check_network_status_async(self):
        """异步检查网络连接状态和延时"""
        try:
            # 获取代理设置
            proxy_settings = None
            use_proxy = False
            if 'GENERAL' in self.config and self.config['GENERAL'].get('proxy_enabled', False):
                proxy_type = self.config['GENERAL'].get('proxy_type', '')
                proxy_addr = self.config['GENERAL'].get('proxy_addr', '')
                proxy_port = self.config['GENERAL'].get('proxy_port', 0)
                proxy_username = self.config['GENERAL'].get('proxy_username', '')
                proxy_password = self.config['GENERAL'].get('proxy_password', '')
                
                if proxy_addr and proxy_port:
                    use_proxy = True
                    if proxy_type == 'SOCKS5':
                        proxy_url = f"socks5://{proxy_addr}:{proxy_port}"
                        if proxy_username and proxy_password:
                            proxy_url = f"socks5://{proxy_username}:{proxy_password}@{proxy_addr}:{proxy_port}"
                        proxy_settings = proxy_url

            # 优化测试URL选择 - 选择更快的本地测试URL
            test_url = 'http://www.baidu.com'  # 使用HTTP而不是HTTPS可能更快
            fallback_url = 'http://www.qq.com'  # 备用URL
            
            # 如果使用代理，使用特定的测试URL
            if use_proxy:
                # 代理模式下使用特定测试站点
                test_url = 'http://www.google.com'  # 使用谷歌网站进行测试
            
            # 记录开始时间
            start_time = time.time()
            
            # 创建会话但不使用timeout参数，而是在get请求中使用timeout
            connector = aiohttp.TCPConnector(ssl=False)  # 禁用SSL验证以加速
            async with aiohttp.ClientSession(connector=connector) as session:
                request_kwargs = {}
                if proxy_settings:
                    request_kwargs['proxy'] = proxy_settings
                
                # 使用try来处理第一个URL的请求
                try:
                    # 为请求单独设置超时，而不是在会话级别设置
                    request_kwargs['timeout'] = 2.0
                    async with session.get(test_url, **request_kwargs) as response:
                        # 计算请求耗时（毫秒）
                        elapsed_ms = round((time.time() - start_time) * 1000)
                        if response.status == 200:
                            # 连接正常，显示延时
                            self._update_network_status_latency(elapsed_ms)
                            return  # 成功就直接返回
                        else:
                            # 服务器返回了非200状态码
                            self._update_network_status_latency(elapsed_ms, f"状态码: {response.status}")
                            return  # 至少收到响应，也直接返回
                except (aiohttp.ClientConnectorError, asyncio.TimeoutError, aiohttp.ClientError):
                    # 第一个URL失败时尝试备用URL
                    if not use_proxy and test_url != fallback_url:
                        try:
                            # 重置开始时间
                            start_time = time.time()
                            async with session.get(fallback_url, timeout=2.0) as response:
                                elapsed_ms = round((time.time() - start_time) * 1000)
                                if response.status == 200:
                                    self._update_network_status_latency(elapsed_ms, "备用")
                                    return
                                else:
                                    self._update_network_status_latency(elapsed_ms, f"备用 状态码: {response.status}")
                                    return
                        except Exception:
                            # 两个URL都失败，抛出给外层统一处理
                            raise
                    else:
                        # 如果没有备用URL可用，直接抛出
                        raise
        
        except aiohttp.ClientConnectorError:
            # 无法连接到服务器
            self.network_status_label.setText("网络：未连接")
            self.network_status_label.setStyleSheet("padding: 0 8px; color: #F44336;")  # 红色
            logger.warning("无法连接到测试服务器")  # 降级为warning，避免频繁error日志
            
        except asyncio.TimeoutError:
            # 连接超时
            self.network_status_label.setText("网络：超时")
            self.network_status_label.setStyleSheet("padding: 0 8px; color: #F44336;")  # 红色
            logger.warning("网络连接测试超时")
            
        except aiohttp.ClientError as e:
            # aiohttp客户端错误（包括代理错误等）
            self.network_status_label.setText("网络：错误")
            self.network_status_label.setStyleSheet("padding: 0 8px; color: #F44336;")  # 红色
            logger.warning(f"网络请求客户端错误: {e}")
            
        except Exception as e:
            # 其他异常
            self.network_status_label.setText("网络：未连接")
            self.network_status_label.setStyleSheet("padding: 0 8px; color: #F44336;")  # 红色
            logger.warning(f"网络连接检查失败: {e}")  # 降级为warning，避免频繁error日志
    
    def _update_network_status_latency(self, latency_ms, details=None):
        """更新网络延时状态
        
        Args:
            latency_ms: 延时，单位为毫秒
            details: 其他详情信息
        """
        # 根据延时设置不同的颜色
        if latency_ms < 100:
            text = f"网络：{latency_ms}ms"
            self.network_status_label.setStyleSheet("padding: 0 8px; color: #4CAF50;")  # 绿色
        elif latency_ms < 300:
            text = f"网络：{latency_ms}ms"
            self.network_status_label.setStyleSheet("padding: 0 8px; color: #2196F3;")  # 蓝色
        elif latency_ms < 500:
            text = f"网络：{latency_ms}ms"
            self.network_status_label.setStyleSheet("padding: 0 8px; color: #FF9800;")  # 橙色
        else:
            text = f"网络：{latency_ms}ms"
            self.network_status_label.setStyleSheet("padding: 0 8px; color: #F44336;")  # 红色
        
        # 添加额外详情信息
        if details:
            text += f" ({details})"
            
        self.network_status_label.setText(text)
    
    def _return_to_welcome(self):
        """返回欢迎页面"""
        logger.debug("返回欢迎页面")
        # 如果有多个视图，切换到欢迎页面
        if self.central_layout.count() > 0:
            self.central_layout.setCurrentWidget(self.welcome_widget)
    
    def show_status_message(self, message, timeout=3000):
        """在状态栏显示消息
        
        Args:
            message: 显示的消息文本
            timeout: 显示时间(毫秒)，默认3秒
        """
        logger.debug(f"状态栏消息: {message}")
        self.statusBar().showMessage(message, timeout)

    def _close_settings_view(self):
        """关闭设置视图并返回到之前的视图"""
        # 找到设置视图并移除
        for view_id, view in list(self.opened_views.items()):
            if hasattr(view, 'settings_saved'):  # 检查是否是设置视图
                # 从栈布局中移除
                self.central_layout.removeWidget(view)
                # 从已打开视图中移除
                self.opened_views.pop(view_id, None)
                # 返回到欢迎视图
                self.central_layout.setCurrentWidget(self.welcome_widget)
                # 记录日志
                logger.debug(f"已关闭设置视图: {view_id}")
                break 

    def _on_settings_saved(self):
        """处理设置保存信号"""
        # 显示状态消息
        self.statusBar().showMessage("设置已保存", 3000)
        # 不需要关闭设置视图，保持在当前页面 

    def eventFilter(self, obj, event):
        """事件过滤器，用于捕获工具栏的鼠标事件
        
        Args:
            obj: 事件源对象
            event: 事件对象
            
        Returns:
            bool: 是否已处理事件
        """
        # 检查事件是否来自工具栏
        if obj == self.toolbar:
            # 捕获鼠标释放事件，通常是拖动结束
            from PySide6.QtCore import QEvent
            if event.type() == QEvent.MouseButtonRelease:
                logger.debug("检测到工具栏鼠标释放事件，可能是拖动结束")
                # 稍微延迟保存，以确保工具栏状态已完全更新
                QTimer.singleShot(300, self._save_current_state)
            # 捕获移动事件结束
            elif event.type() == QEvent.Move:
                logger.debug("检测到工具栏移动事件")
                QTimer.singleShot(300, self._save_current_state)
            
        # 继续正常事件处理
        return super().eventFilter(obj, event)

    def _create_system_tray(self):
        """创建系统托盘图标和菜单"""
        # 检查系统是否支持系统托盘
        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning("系统不支持系统托盘功能")
            return
            
        # 创建系统托盘图标
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self._get_icon("app"))
        self.tray_icon.setToolTip("TG-Manager")
        
        # 创建系统托盘菜单
        tray_menu = QMenu()
        
        # 添加恢复窗口操作
        restore_action = QAction("显示主窗口", self)
        restore_action.triggered.connect(self.showNormal)
        tray_menu.addAction(restore_action)
        
        # 添加分隔线
        tray_menu.addSeparator()
        
        # 添加退出操作
        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.close)
        tray_menu.addAction(exit_action)
        
        # 设置托盘菜单
        self.tray_icon.setContextMenu(tray_menu)
        
        # 连接托盘图标的激活信号（双击托盘图标时触发）
        self.tray_icon.activated.connect(self._on_tray_icon_activated)
        
        # 托盘图标初始状态为隐藏
        self.tray_icon.hide()
        
        logger.info("系统托盘图标已创建")

    def _on_tray_icon_activated(self, reason):
        """处理托盘图标激活事件
        
        Args:
            reason: 激活原因
        """
        # 双击或点击托盘图标时恢复窗口
        if reason == QSystemTrayIcon.DoubleClick or reason == QSystemTrayIcon.Trigger:
            self.showNormal()
            self.activateWindow()  # 激活窗口，使其获得焦点

    def changeEvent(self, event):
        """处理窗口状态变化事件
        
        Args:
            event: 状态变化事件
        """
        # 调用父类处理
        super().changeEvent(event)
        
        # 处理窗口最小化事件
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.WindowStateChange:
            # 检查窗口是否被最小化
            if self.windowState() & Qt.WindowMinimized:
                logger.debug("窗口被最小化")
                
                # 检查是否启用了最小化到托盘功能
                minimize_to_tray = False
                if isinstance(self.config, dict) and 'UI' in self.config:
                    ui_config = self.config.get('UI', {})
                    if isinstance(ui_config, dict):
                        minimize_to_tray = ui_config.get('minimize_to_tray', False)
                
                # 如果启用了最小化到托盘，则隐藏窗口并显示托盘图标
                if minimize_to_tray and hasattr(self, 'tray_icon'):
                    logger.info("启用了最小化到托盘，隐藏窗口并显示托盘图标")
                    event.accept()
                    self.hide()
                    self.tray_icon.show()
                    
                    # 显示托盘提示
                    self.tray_icon.showMessage(
                        "TG-Manager 已最小化到托盘",
                        "应用程序在后台运行中。点击托盘图标以恢复窗口。",
                        QSystemTrayIcon.Information,
                        2000
                    ) 

    def get_view(self, view_name):
        """获取指定名称的视图组件
        
        Args:
            view_name: 视图名称，可选值: 'download', 'upload', 'forward', 'listen', 'task', 'log', 'help'
            
        Returns:
            视图组件实例，如果不存在则返回None
        """
        # 映射视图名称到 opened_views 中的键
        view_id_map = {
            'download': 'function.download',
            'upload': 'function.upload',
            'forward': 'function.forward',
            'listen': 'function.monitor',
            'task': 'function.task_manager',
            'log': 'function.logs',
            'help': 'function.help',
            'settings': 'settings',
            'qt_asyncio_test': 'function.qt_asyncio_test'
        }
        
        view_id = view_id_map.get(view_name)
        if view_id and view_id in self.opened_views:
            return self.opened_views[view_id]
            
        # 如果视图尚未打开，返回None
        logger.debug(f"视图 '{view_name}' 尚未打开，无法获取引用")
        return None

