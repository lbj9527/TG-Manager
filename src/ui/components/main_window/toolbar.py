"""
TG-Manager 主窗口工具栏模块
包含主窗口的工具栏创建和工具按钮功能实现
"""

from loguru import logger
from PySide6.QtWidgets import QToolBar
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction
from src.utils.translation_manager import tr

class ToolBarMixin:
    """工具栏功能混入类
    
    为MainWindow提供工具栏相关功能
    """
    
    def _create_tool_bar(self):
        """创建工具栏"""
        # 主工具栏
        self.toolbar = self.addToolBar(tr("ui.toolbar.main"))
        self.toolbar.setObjectName("main_toolbar")
        self.toolbar.setMovable(True)
        self.toolbar.setAllowedAreas(Qt.TopToolBarArea | Qt.LeftToolBarArea | Qt.RightToolBarArea | Qt.BottomToolBarArea)
        
        # 为状态改变防抖创建计时器
        self._toolbar_state_timer = QTimer(self)
        self._toolbar_state_timer.setSingleShot(True)
        self._toolbar_state_timer.setInterval(500)  # 500ms防抖延迟
        self._toolbar_state_timer.timeout.connect(self._save_current_state)
        
        # 返回主页按钮
        self.home_action = QAction(tr("ui.toolbar.home"), self)
        self.home_action.setIcon(self._get_icon("home"))
        self.home_action.setStatusTip(tr("ui.toolbar.home_tip"))
        self.home_action.triggered.connect(self._return_to_welcome)
        self.toolbar.addAction(self.home_action)
        
        # 设置按钮
        self.settings_action = QAction(tr("ui.toolbar.settings"), self)
        self.settings_action.setIcon(self._get_icon("settings"))
        self.settings_action.setStatusTip(tr("ui.toolbar.settings_tip"))
        self.settings_action.triggered.connect(self._open_settings)
        self.toolbar.addAction(self.settings_action)
        

        
        # 日志查看器按钮
        self.log_viewer_action = QAction(tr("ui.toolbar.log_viewer"), self)
        self.log_viewer_action.setIcon(self._get_icon("logs"))
        self.log_viewer_action.setStatusTip(tr("ui.toolbar.log_viewer_tip"))
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
        """工具栏状态改变时触发，使用防抖延迟保存窗口状态"""
        # 如果定时器已经在运行，重置它
        if self._toolbar_state_timer.isActive():
            self._toolbar_state_timer.stop()
        
        # 重新启动定时器，延迟500ms后保存状态
        logger.debug("工具栏状态已改变，计划500ms后保存")
        self._toolbar_state_timer.start()
    
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
    
    def _update_translations(self):
        """刷新工具栏所有文本的翻译"""
        self.toolbar.setWindowTitle(tr("ui.toolbar.main"))
        self.home_action.setText(tr("ui.toolbar.home"))
        self.home_action.setStatusTip(tr("ui.toolbar.home_tip"))
        self.settings_action.setText(tr("ui.toolbar.settings"))
        self.settings_action.setStatusTip(tr("ui.toolbar.settings_tip"))

        self.log_viewer_action.setText(tr("ui.toolbar.log_viewer"))
        self.log_viewer_action.setStatusTip(tr("ui.toolbar.log_viewer_tip")) 