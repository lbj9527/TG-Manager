"""
TG-Manager 主窗口工具栏模块
包含主窗口的工具栏创建和工具按钮功能实现
"""

from loguru import logger
from PySide6.QtWidgets import QToolBar
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction

class ToolBarMixin:
    """工具栏功能混入类
    
    为MainWindow提供工具栏相关功能
    """
    
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
        
        # 安装事件过滤器，用于跟踪工具栏状态变化
        self.toolbar.installEventFilter(self)
        
        # 连接信号
        self._connect_toolbar_signals()
        
        logger.debug("主工具栏创建完成")
    
    def _connect_toolbar_signals(self):
        """连接工具栏相关信号"""
        # 工具栏移动信号 - 捕获工具栏被移动的事件
        self.toolbar.movableChanged.connect(self._on_toolbar_state_changed)
        self.toolbar.topLevelChanged.connect(self._on_toolbar_state_changed)
        self.toolbar.allowedAreasChanged.connect(self._on_toolbar_state_changed)
        self.toolbar.orientationChanged.connect(self._on_toolbar_state_changed)
        self.toolbar.visibilityChanged.connect(self._on_toolbar_state_changed)
    
    def _on_toolbar_state_changed(self, _=None):
        """工具栏状态改变时触发，保存窗口状态"""
        # 状态改变后延迟保存窗口状态，确保已完成移动
        logger.debug("工具栏状态已改变，准备保存")
        QTimer.singleShot(100, self._save_current_state)
    
    def _toggle_toolbar(self, checked):
        """切换工具栏的可见性
        
        Args:
            checked: 是否显示
        """
        self.toolbar.setVisible(checked)
    
    def _return_to_welcome(self):
        """返回欢迎页面"""
        logger.debug("返回欢迎页面")
        # 如果有多个视图，切换到欢迎页面
        if hasattr(self, 'central_layout') and hasattr(self, 'welcome_widget'):
            self.central_layout.setCurrentWidget(self.welcome_widget) 