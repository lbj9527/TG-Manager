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

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QDockWidget, 
    QMessageBox, QStackedLayout, QStyle, QSizePolicy,
    QSplitter, QFileDialog, QDialog, QFormLayout, QLineEdit, 
    QDialogButtonBox, QLabel, QCheckBox, QToolBar, QStatusBar,
    QHBoxLayout, QStackedWidget, QScrollArea, QMenu
)
from PySide6.QtCore import Qt, Slot, Signal, QByteArray, QSize, QTimer
from PySide6.QtGui import QAction, QIcon, QResizeEvent, QPixmap


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
        welcome_label = QMessageBox()
        welcome_label.setWindowTitle("欢迎使用")
        welcome_label.setText("<h2>欢迎使用 TG-Manager</h2>"
                            "<p>请从左侧导航树选择功能</p>")
        welcome_label.setIcon(QMessageBox.Information)
        welcome_layout.addWidget(welcome_label)
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
                "app": QStyle.SP_DesktopIcon
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
        
        # 退出动作
        exit_action = QAction("退出", self)
        exit_action.setIcon(self._get_icon("exit"))
        exit_action.setShortcut("Ctrl+Q")
        exit_action.setStatusTip("退出应用程序")
        exit_action.triggered.connect(self.close)
        self.file_menu.addAction(exit_action)
        
        # 配置菜单
        self.config_menu = self.menubar.addMenu("配置")
        
        # 打开设置
        settings_action = QAction("系统设置", self)
        settings_action.setIcon(self._get_icon("settings"))
        settings_action.setShortcut("Ctrl+,")
        settings_action.setStatusTip("打开系统设置")
        settings_action.triggered.connect(self._open_settings)
        self.config_menu.addAction(settings_action)
        
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
        
        # 登录按钮
        self.login_action = QAction("登录", self)
        self.login_action.setIcon(self._get_icon("login"))
        self.login_action.setStatusTip("登录到Telegram账号")
        self.login_action.triggered.connect(self._handle_login)
        self.toolbar.addAction(self.login_action)
        
        # 分隔符
        self.toolbar.addSeparator()
        
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
        self.client_status_label.setStyleSheet("padding: 0 8px; color: #757575;")
        self.client_status_label.setToolTip("Telegram客户端连接状态")
        status_bar.addPermanentWidget(self.client_status_label)
        
        # 3. 网络状态
        self.network_status_label = QLabel("网络: 未知")
        self.network_status_label.setStyleSheet("padding: 0 8px; color: #757575;")
        self.network_status_label.setToolTip("网络连接状态")
        status_bar.addPermanentWidget(self.network_status_label)
        
        # 4. CPU/内存使用率
        self.resource_usage_label = QLabel("CPU: 0% | 内存: 0MB")
        self.resource_usage_label.setStyleSheet("padding: 0 8px; color: #757575;")
        self.resource_usage_label.setToolTip("系统资源使用情况")
        status_bar.addPermanentWidget(self.resource_usage_label)
        
        # 设置定时器，定期更新资源使用率
        self.resource_timer = QTimer(self)
        self.resource_timer.timeout.connect(self._update_resource_usage)
        self.resource_timer.start(2000)  # 每2秒更新一次
        
        # 设置网络状态检查定时器
        self.network_timer = QTimer(self)
        self.network_timer.timeout.connect(self._check_network_status)
        self.network_timer.start(5000)  # 每5秒检查一次
        
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
                
            elif function_name == 'settings':
                from src.ui.views.settings_view import SettingsView
                view = SettingsView(self.config)
                # 连接设置取消信号
                view.settings_cancelled.connect(self._close_settings_view)
                
            elif function_name == 'help':
                from src.ui.views.help_doc_view import HelpDocView
                view = HelpDocView(self.config, self)
                
            elif function_name == 'logs':
                from src.ui.views.log_viewer_view import LogViewerView
                view = LogViewerView(self.config, self)
                
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
        try:
            from src.utils.task_scheduler import get_task_scheduler
            import asyncio
            
            # 获取任务调度器实例
            scheduler = get_task_scheduler()
            
            # 遍历所有任务
            active_tasks = 0
            running_tasks = []
            
            for task_id, task_info in scheduler.get_all_tasks().items():
                if task_info.status == 'RUNNING':
                    running_tasks.append(task_id)
                    active_tasks += 1
            
            if not running_tasks:
                QMessageBox.information(
                    self,
                    "暂停任务",
                    "当前没有正在运行的任务。",
                    QMessageBox.Ok
                )
                return
            
            # 创建异步任务暂停所有任务
            async def pause_all():
                paused_count = 0
                for task_id in running_tasks:
                    if await scheduler.pause_task(task_id):
                        paused_count += 1
                return paused_count
            
            # 执行暂停
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            paused_count = loop.run_until_complete(pause_all())
            loop.close()
            
            # 显示结果
            QMessageBox.information(
                self,
                "暂停任务",
                f"已暂停 {paused_count}/{active_tasks} 个任务。",
                QMessageBox.Ok
            )
            
            # 更新任务概览
            if hasattr(self, 'task_overview') and self.task_overview:
                # 刷新任务概览显示（如果任务概览组件有提供刷新方法）
                if hasattr(self.task_overview, '_refresh_tasks'):
                    self.task_overview._refresh_tasks()
            
        except Exception as e:
            logger.error(f"暂停所有任务失败: {e}")
            QMessageBox.critical(
                self,
                "操作失败",
                f"暂停所有任务失败: {str(e)}",
                QMessageBox.Ok
            )
    
    def _resume_all_tasks(self):
        """恢复所有暂停的任务"""
        try:
            from src.utils.task_scheduler import get_task_scheduler
            import asyncio
            
            # 获取任务调度器实例
            scheduler = get_task_scheduler()
            
            # 遍历所有任务
            paused_tasks = 0
            paused_task_ids = []
            
            for task_id, task_info in scheduler.get_all_tasks().items():
                if task_info.status == 'PAUSED':
                    paused_task_ids.append(task_id)
                    paused_tasks += 1
            
            if not paused_task_ids:
                QMessageBox.information(
                    self,
                    "恢复任务",
                    "当前没有暂停中的任务。",
                    QMessageBox.Ok
                )
                return
            
            # 创建异步任务恢复所有任务
            async def resume_all():
                resumed_count = 0
                for task_id in paused_task_ids:
                    if await scheduler.resume_task(task_id):
                        resumed_count += 1
                return resumed_count
            
            # 执行恢复
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            resumed_count = loop.run_until_complete(resume_all())
            loop.close()
            
            # 显示结果
            QMessageBox.information(
                self,
                "恢复任务",
                f"已恢复 {resumed_count}/{paused_tasks} 个任务。",
                QMessageBox.Ok
            )
            
            # 更新任务概览
            if hasattr(self, 'task_overview') and self.task_overview:
                # 刷新任务概览显示（如果任务概览组件有提供刷新方法）
                if hasattr(self.task_overview, '_refresh_tasks'):
                    self.task_overview._refresh_tasks()
            
        except Exception as e:
            logger.error(f"恢复所有任务失败: {e}")
            QMessageBox.critical(
                self,
                "操作失败",
                f"恢复所有任务失败: {str(e)}",
                QMessageBox.Ok
            )
    
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
                        self.restoreGeometry(QByteArray.fromBase64(geometry.encode()))
                except Exception as e:
                    logger.warning(f"恢复窗口几何形状失败: {e}")
            
            # 加载窗口状态（停靠窗口等）
            if 'window_state' in ui_config:
                try:
                    state = ui_config.get('window_state')
                    if state:
                        self.restoreState(QByteArray.fromBase64(state.encode()))
                except Exception as e:
                    logger.warning(f"恢复窗口状态失败: {e}")
                    
        # 添加缩放策略，使窗口内容能够适应大小变化
        self.central_widget.setSizePolicy(
            QSizePolicy.Expanding, 
            QSizePolicy.Expanding
        )
    
    def _save_window_state(self, state_data):
        """保存窗口状态
        
        Args:
            state_data: 窗口状态数据
        """
        ui_config = self.config.get('UI', {})
        
        # 更新窗口状态数据
        if 'geometry' in state_data:
            ui_config['window_geometry'] = state_data['geometry'].toBase64().data().decode()
        
        if 'state' in state_data:
            ui_config['window_state'] = state_data['state'].toBase64().data().decode()
        
        # 更新配置
        self.config['UI'] = ui_config
        self.config_saved.emit(self.config)
    
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
        if hasattr(self, 'resource_timer') and self.resource_timer.isActive():
            self.resource_timer.stop()
            
        if hasattr(self, 'network_timer') and self.network_timer.isActive():
            self.network_timer.stop()
        
        # 保存窗口状态
        window_state = {
            'geometry': self.saveGeometry(),
            'state': self.saveState()
        }
        self.window_state_changed.emit(window_state)
        
        # 接受关闭事件
        event.accept()
    
    def _handle_login(self):
        """处理登录按钮点击事件"""
        try:
            # 创建登录对话框
            login_dialog = QDialog(self)
            login_dialog.setWindowTitle("登录到Telegram")
            login_dialog.setMinimumWidth(400)
            
            # 创建布局
            main_layout = QVBoxLayout(login_dialog)
            form_layout = QFormLayout()
            
            # 创建表单字段
            api_id_input = QLineEdit()
            api_hash_input = QLineEdit()
            phone_input = QLineEdit()
            
            # 从配置中加载API ID和Hash（如果存在）
            if 'API' in self.config and 'api_id' in self.config['API']:
                api_id_input.setText(str(self.config['API']['api_id']))
            if 'API' in self.config and 'api_hash' in self.config['API']:
                api_hash_input.setText(self.config['API']['api_hash'])
            
            # 添加表单字段
            form_layout.addRow("API ID:", api_id_input)
            form_layout.addRow("API Hash:", api_hash_input)
            form_layout.addRow("手机号码:", phone_input)
            
            # 添加"记住凭据"选项
            remember_checkbox = QCheckBox("记住凭据")
            remember_checkbox.setChecked(True)
            
            # 提示信息
            info_label = QLabel("请输入您的Telegram API凭据和手机号码。如需获取API凭据，请访问 https://my.telegram.org")
            info_label.setWordWrap(True)
            
            # 创建按钮
            button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            button_box.accepted.connect(login_dialog.accept)
            button_box.rejected.connect(login_dialog.reject)
            
            # 组装布局
            main_layout.addWidget(info_label)
            main_layout.addLayout(form_layout)
            main_layout.addWidget(remember_checkbox)
            main_layout.addWidget(button_box)
            
            # 显示对话框
            result = login_dialog.exec_()
            
            # 如果用户点击了"确定"
            if result == QDialog.Accepted:
                api_id = api_id_input.text().strip()
                api_hash = api_hash_input.text().strip()
                phone = phone_input.text().strip()
                
                # 验证输入
                if not api_id or not api_hash or not phone:
                    QMessageBox.warning(
                        self,
                        "输入错误",
                        "请填写所有必填字段。",
                        QMessageBox.Ok
                    )
                    return
                
                # 如果选择了记住凭据，保存到配置中
                if remember_checkbox.isChecked():
                    if 'API' not in self.config:
                        self.config['API'] = {}
                    
                    self.config['API']['api_id'] = int(api_id)
                    self.config['API']['api_hash'] = api_hash
                    self.config['API']['phone'] = phone
                    
                    # 发出配置更新信号
                    self.config_saved.emit(self.config)
                
                # 显示登录成功消息
                QMessageBox.information(
                    self,
                    "登录成功",
                    f"登录信息已保存。手机号: {phone}",
                    QMessageBox.Ok
                )
                
                # 更新状态栏
                self.statusBar().showMessage(f"已登录: {phone}")
                
        except Exception as e:
            logger.error(f"登录处理时出错: {e}")
            QMessageBox.critical(
                self,
                "登录错误",
                f"登录过程中发生错误: {str(e)}",
                QMessageBox.Ok
            )
    
    def _open_settings(self):
        """打开设置界面"""
        # 通过导航树API找到设置项并触发点击
        self.nav_tree.select_item_by_function("settings")
    
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
        # 更新任务计数
        self.task_overview.update_counters(3, 12, 2, 1)
        
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
        self.sidebar_splitter.addWidget(self.nav_tree)
        self.sidebar_splitter.addWidget(self.task_overview)
        
        # 设置初始分割比例 (35% 导航树, 65% 任务概览)
        self.sidebar_splitter.setSizes([350, 650])
        
        # 将分割器添加到停靠窗口
        self.sidebar_dock.setWidget(self.sidebar_splitter)
        
        # 将停靠窗口添加到左侧区域
        self.addDockWidget(Qt.LeftDockWidgetArea, self.sidebar_dock)
    
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
            
            # 调整分割器中导航树和任务概览的比例
            # 只有当窗口高度大于阈值时才调整，防止在极小的窗口尺寸下产生问题
            if current_height > 400:
                # 大约保持 40% 导航树, 60% 任务概览
                self.sidebar_splitter.setSizes([int(current_height * 0.4), int(current_height * 0.6)])
        
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
        
        # 更新任务视图
        if "task_manager" in self.opened_views:
            task_view = self.opened_views["task_manager"]
            if hasattr(task_view, 'tasks') and task_id in task_view.tasks:
                task_data = task_view.tasks[task_id]
                task_data['status'] = "已取消"
                task_view.add_task(task_data)  # 更新任务状态
    
    def _remove_task(self, task_id):
        """移除任务
        
        Args:
            task_id: 任务ID
        """
        logger.info(f"移除任务: {task_id}")
        
        # 确认移除
        reply = QMessageBox.question(
            self,
            "确认移除",
            f"确定要从列表中移除任务 {task_id} 吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # 这里应该调用业务逻辑层的任务移除方法
        # 示例代码：self.task_manager.remove_task(task_id)
        
        # 从任务概览组件中移除
        if hasattr(self, 'task_overview') and self.task_overview:
            self.task_overview.remove_task(task_id)
        
        # 从任务视图中移除
        if "task_manager" in self.opened_views:
            task_view = self.opened_views["task_manager"]
            if hasattr(task_view, 'remove_task'):
                task_view.remove_task(task_id)
    
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
    
    def _update_network_status(self, status="未知", details=None):
        """更新网络连接状态
        
        Args:
            status: 网络状态，如"已连接"、"受限"、"断开"等
            details: 网络详情，如"Wi-Fi"、"以太网"、"4G"等
        """
        # 根据状态设置不同的颜色和文本
        if status == "已连接":
            text = f"网络: {status}" + (f" ({details})" if details else "")
            self.network_status_label.setStyleSheet("padding: 0 8px; color: #4CAF50;")  # 绿色
        elif status == "受限":
            text = f"网络: {status}" + (f" ({details})" if details else "")
            self.network_status_label.setStyleSheet("padding: 0 8px; color: #FF9800;")  # 橙色
        elif status == "断开":
            text = f"网络: {status}"
            self.network_status_label.setStyleSheet("padding: 0 8px; color: #F44336;")  # 红色
        else:
            text = f"网络: {status}"
            self.network_status_label.setStyleSheet("padding: 0 8px; color: #757575;")  # 灰色
        
        self.network_status_label.setText(text)
        
    def _check_network_status(self):
        """检查网络连接状态"""
        # 创建异步任务来执行网络检查
        asyncio.ensure_future(self._check_network_status_async())
    
    async def _check_network_status_async(self):
        """异步检查网络连接状态"""
        try:
            # 使用aiohttp尝试连接到Telegram API服务器
            connector = aiohttp.TCPConnector(ssl=False)  # 关闭SSL验证以加快连接速度
            async with aiohttp.ClientSession(connector=connector) as session:
                # 减少超时时间为1秒，避免等待时间过长
                timeout = aiohttp.ClientTimeout(total=1)
                async with session.get('https://api.telegram.org', timeout=timeout) as response:
                    if response.status == 200:
                        # 连接正常
                        self._update_network_status("已连接", "连接良好")
                    else:
                        # 服务器返回了非200状态码
                        self._update_network_status("已连接", f"状态码: {response.status}")
        
        except asyncio.TimeoutError:
            # 连接超时
            self._update_network_status("超时", "连接缓慢")
            logger.warning("网络连接检查超时")
            
        except aiohttp.ClientConnectorError:
            # 无法连接到服务器
            self._update_network_status("断开", "无法连接")
            logger.warning("无法连接到Telegram服务器")  # 降级为warning，避免频繁error日志
            
        except Exception as e:
            # 其他异常
            self._update_network_status("异常", str(e)[:20])
            logger.warning(f"网络连接检查失败: {e}")  # 降级为warning，避免频繁error日志
    
    def _close_settings_view(self):
        """关闭设置视图并返回到之前的视图"""
        # 找到设置视图并移除
        for view_id, view in list(self.opened_views.items()):
            if hasattr(view, 'settings_cancelled'):  # 检查是否是设置视图
                # 从栈布局中移除
                self.central_layout.removeWidget(view)
                # 从已打开视图中移除
                self.opened_views.pop(view_id, None)
                # 返回到欢迎视图或其他视图
                if self.central_layout.count() > 0:
                    # 如果还有其他视图，则显示第一个
                    self.central_layout.setCurrentIndex(0)
                # 记录日志
                logger.debug(f"已关闭设置视图: {view_id}")
                break 

    def _on_settings_saved(self):
        """处理设置保存信号"""
        # 关闭设置视图
        self.show_status_message("设置已保存")
        self._close_settings_view() 