"""
TG-Manager 主窗口
主界面窗口，包含菜单栏、工具栏和中央部件
"""

import logging
from loguru import logger
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QDockWidget, 
    QMessageBox, QStackedLayout
)
from PySide6.QtCore import Qt, Slot, Signal, QByteArray
from PySide6.QtGui import QAction, QIcon


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
        self.setWindowIcon(QIcon("assets/icons/app.png"))
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
        self._create_status_bar()
        self._create_navigation_tree()
        self._create_task_overview()
        
        # 加载窗口状态
        self._load_window_state()
        
        # 连接信号和槽
        self._connect_signals()
        
        logger.info("主窗口初始化完成")
    
    def _create_menu_bar(self):
        """创建菜单栏"""
        # 主菜单栏
        self.menubar = self.menuBar()
        
        # 文件菜单
        self.file_menu = self.menubar.addMenu("文件")
        
        # 退出动作
        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.close)
        self.file_menu.addAction(exit_action)
        
        # 视图菜单
        self.view_menu = self.menubar.addMenu("视图")
        
        # 显示/隐藏导航树
        self.show_nav_action = QAction("导航面板", self)
        self.show_nav_action.setCheckable(True)
        self.show_nav_action.setChecked(True)
        self.show_nav_action.triggered.connect(self._toggle_navigation)
        self.view_menu.addAction(self.show_nav_action)
        
        # 显示/隐藏任务概览
        self.show_tasks_action = QAction("任务概览", self)
        self.show_tasks_action.setCheckable(True)
        self.show_tasks_action.setChecked(True)
        self.show_tasks_action.triggered.connect(self._toggle_task_overview)
        self.view_menu.addAction(self.show_tasks_action)
        
        # 任务菜单
        self.task_menu = self.menubar.addMenu("任务")
        
        # 暂停所有任务
        self.pause_all_action = QAction("暂停所有任务", self)
        self.pause_all_action.triggered.connect(self._pause_all_tasks)
        self.task_menu.addAction(self.pause_all_action)
        
        # 恢复所有任务
        self.resume_all_action = QAction("恢复所有任务", self)
        self.resume_all_action.triggered.connect(self._resume_all_tasks)
        self.task_menu.addAction(self.resume_all_action)
        
        # 帮助菜单
        self.help_menu = self.menubar.addMenu("帮助")
        
        # 关于动作
        about_action = QAction("关于", self)
        about_action.triggered.connect(self._show_about)
        self.help_menu.addAction(about_action)
    
    def _create_status_bar(self):
        """创建状态栏"""
        self.statusBar().showMessage("就绪")
    
    def _create_navigation_tree(self):
        """创建导航树组件"""
        from src.ui.components.navigation_tree import NavigationTree
        
        # 创建导航树
        self.nav_tree = NavigationTree()
        
        # 创建导航区域停靠窗口
        self.nav_dock = QDockWidget("导航", self)
        self.nav_dock.setObjectName("navigation_dock")
        self.nav_dock.setWidget(self.nav_tree)
        self.nav_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.nav_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        
        # 将导航树添加到左侧停靠区域
        self.addDockWidget(Qt.LeftDockWidgetArea, self.nav_dock)
        
        # 连接导航树的项目选择信号
        self.nav_tree.item_selected.connect(self._handle_navigation)
    
    def _create_task_overview(self):
        """创建任务概览组件"""
        from src.ui.components.task_overview import TaskOverview
        
        # 创建任务概览组件
        self.task_overview = TaskOverview()
        
        # 创建任务概览停靠窗口
        self.task_dock = QDockWidget("任务概览", self)
        self.task_dock.setObjectName("task_overview_dock")
        self.task_dock.setWidget(self.task_overview)
        self.task_dock.setAllowedAreas(Qt.TopDockWidgetArea | Qt.BottomDockWidgetArea)
        self.task_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        
        # 将任务概览添加到底部停靠区域
        self.addDockWidget(Qt.BottomDockWidgetArea, self.task_dock)
    
    def _connect_signals(self):
        """连接信号和槽"""
        # 窗口状态变化信号
        self.window_state_changed.connect(self._save_window_state)
    
    def _toggle_navigation(self, checked):
        """切换导航树的可见性
        
        Args:
            checked: 是否显示
        """
        self.nav_dock.setVisible(checked)
    
    def _toggle_task_overview(self, checked):
        """切换任务概览的可见性
        
        Args:
            checked: 是否显示
        """
        self.task_dock.setVisible(checked)
    
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
                
            elif function_name == 'listen':
                from src.ui.views.listen_view import ListenView
                view = ListenView(self.config)
                
            elif function_name == 'tasks':
                from src.ui.views.task_view import TaskView
                view = TaskView(self.config)
                
            elif function_name == 'settings':
                from src.ui.views.settings_view import SettingsView
                view = SettingsView(self.config)
                
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
            "<p>版本: 0.1.0</p>"
            "<p>一个功能强大的Telegram频道管理工具</p>"
            "<p>© 2023 TG-Manager Team</p>"
        )
    
    def _pause_all_tasks(self):
        """暂停所有活动任务"""
        # TODO: 实现暂停所有任务的功能
        QMessageBox.information(
            self,
            "功能未实现",
            "暂停所有任务功能尚未实现。",
            QMessageBox.Ok
        )
    
    def _resume_all_tasks(self):
        """恢复所有暂停的任务"""
        # TODO: 实现恢复所有任务的功能
        QMessageBox.information(
            self,
            "功能未实现",
            "恢复所有任务功能尚未实现。",
            QMessageBox.Ok
        )
    
    def _load_window_state(self):
        """加载窗口状态（大小、位置、布局等）"""
        # 默认窗口大小
        self.resize(1200, 800)
        
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
        
        # 保存窗口状态
        window_state = {
            'geometry': self.saveGeometry(),
            'state': self.saveState()
        }
        self.window_state_changed.emit(window_state)
        
        # 接受关闭事件
        event.accept() 