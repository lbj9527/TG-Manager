"""
TG-Manager 主窗口菜单栏模块
包含主窗口的菜单栏创建和菜单功能实现
"""

from loguru import logger
from PySide6.QtWidgets import QMenu
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from src.utils.translation_manager import tr

class MenuBarMixin:
    """菜单栏功能混入类
    
    为MainWindow提供菜单栏相关功能
    """
    
    def _create_menu_bar(self):
        """创建菜单栏"""
        # 主菜单栏
        self.menubar = self.menuBar()
        
        # 创建各个子菜单
        self._create_file_menu()
        self._create_function_menu()
        self._create_tools_menu()
        self._create_view_menu()
        self._create_help_menu()
    
    def _update_menu_bar_translations(self):
        """更新菜单栏翻译"""
        try:
            # 更新文件菜单
            self.file_menu.setTitle(tr("ui.menu_bar.file"))
            
            # 更新功能菜单
            self.function_menu.setTitle(tr("ui.menu_bar.function"))
            
            # 更新工具菜单
            self.tools_menu.setTitle(tr("ui.menu_bar.tools"))
            
            # 更新视图菜单
            self.view_menu.setTitle(tr("ui.menu_bar.view"))
            
            # 更新帮助菜单
            self.help_menu.setTitle(tr("ui.menu_bar.help"))
            
            # 更新菜单项文本和提示
            self._update_menu_items_translations()
            
            logger.debug("菜单栏翻译更新完成")
        except Exception as e:
            logger.error(f"更新菜单栏翻译失败: {e}")
    
    def _update_menu_items_translations(self):
        """更新菜单项翻译"""
        try:
            # 更新文件菜单项
            for action in self.file_menu.actions():
                if action.objectName() == "settings_action":
                    action.setText(tr("ui.menu_bar.file_menu.settings"))
                    action.setStatusTip(tr("ui.menu_bar.file_menu.settings_tooltip"))
                elif action.objectName() == "exit_action":
                    action.setText(tr("ui.menu_bar.file_menu.exit"))
                    action.setStatusTip(tr("ui.menu_bar.file_menu.exit_tooltip"))
            
            # 更新功能菜单项
            for action in self.function_menu.actions():
                if action.objectName() == "home_action":
                    action.setText(tr("ui.menu_bar.function_menu.home"))
                    action.setStatusTip(tr("ui.menu_bar.function_menu.home_tooltip"))
                elif action.objectName() == "download_action":
                    action.setText(tr("ui.menu_bar.function_menu.download"))
                    action.setStatusTip(tr("ui.menu_bar.function_menu.download_tooltip"))
                elif action.objectName() == "upload_action":
                    action.setText(tr("ui.menu_bar.function_menu.upload"))
                    action.setStatusTip(tr("ui.menu_bar.function_menu.upload_tooltip"))
                elif action.objectName() == "forward_action":
                    action.setText(tr("ui.menu_bar.function_menu.forward"))
                    action.setStatusTip(tr("ui.menu_bar.function_menu.forward_tooltip"))
                elif action.objectName() == "monitor_action":
                    action.setText(tr("ui.menu_bar.function_menu.monitor"))
                    action.setStatusTip(tr("ui.menu_bar.function_menu.monitor_tooltip"))
            
            # 更新工具菜单项
            for action in self.tools_menu.actions():
                if action.objectName() == "log_viewer_action":
                    action.setText(tr("ui.menu_bar.tools_menu.log_viewer"))
                    action.setStatusTip(tr("ui.menu_bar.tools_menu.log_viewer_tooltip"))
            
            # 更新视图菜单项
            for action in self.view_menu.actions():
                if action.objectName() == "show_sidebar_action":
                    action.setText(tr("ui.menu_bar.view_menu.sidebar"))
                    action.setStatusTip(tr("ui.menu_bar.view_menu.sidebar_tooltip"))
                elif action.objectName() == "show_toolbar_action":
                    action.setText(tr("ui.menu_bar.view_menu.toolbar"))
                    action.setStatusTip(tr("ui.menu_bar.view_menu.toolbar_tooltip"))
                elif action.objectName() == "show_statusbar_action":
                    action.setText(tr("ui.menu_bar.view_menu.statusbar"))
                    action.setStatusTip(tr("ui.menu_bar.view_menu.statusbar_tooltip"))
            
            # 更新帮助菜单项
            for action in self.help_menu.actions():
                if action.objectName() == "help_doc_action":
                    action.setText(tr("ui.menu_bar.help_menu.help_doc"))
                    action.setStatusTip(tr("ui.menu_bar.help_menu.help_doc_tooltip"))
                elif action.objectName() == "check_update_action":
                    action.setText(tr("ui.menu_bar.help_menu.check_update"))
                    action.setStatusTip(tr("ui.menu_bar.help_menu.check_update_tooltip"))
                elif action.objectName() == "about_action":
                    action.setText(tr("ui.menu_bar.help_menu.about"))
                    action.setStatusTip(tr("ui.menu_bar.help_menu.about_tooltip"))
            
        except Exception as e:
            logger.error(f"更新菜单项翻译失败: {e}")
    
    def _create_file_menu(self):
        """创建文件菜单"""
        # 文件菜单
        self.file_menu = self.menubar.addMenu(tr("ui.menu_bar.file"))
        
        # 设置动作
        settings_action = QAction(tr("ui.menu_bar.file_menu.settings"), self)
        settings_action.setObjectName("settings_action")
        settings_action.setIcon(self._get_icon("settings"))
        settings_action.setShortcut("Ctrl+,")
        settings_action.setStatusTip(tr("ui.menu_bar.file_menu.settings_tooltip"))
        settings_action.triggered.connect(self._open_settings)
        self.file_menu.addAction(settings_action)
        
        # 退出动作
        exit_action = QAction(tr("ui.menu_bar.file_menu.exit"), self)
        exit_action.setObjectName("exit_action")
        exit_action.setIcon(self._get_icon("exit"))
        exit_action.setShortcut("Ctrl+Q")
        exit_action.setStatusTip(tr("ui.menu_bar.file_menu.exit_tooltip"))
        exit_action.triggered.connect(self.close)
        self.file_menu.addAction(exit_action)
    
    def _create_function_menu(self):
        """创建功能菜单"""
        # 功能菜单
        self.function_menu = self.menubar.addMenu(tr("ui.menu_bar.function"))
        
        # 回到主界面
        home_action = QAction(tr("ui.menu_bar.function_menu.home"), self)
        home_action.setObjectName("home_action")
        home_action.setIcon(self._get_icon("home"))
        home_action.setShortcut("Ctrl+0")
        home_action.setStatusTip(tr("ui.menu_bar.function_menu.home_tooltip"))
        home_action.triggered.connect(self._return_to_welcome)
        self.function_menu.addAction(home_action)
        
        # 分隔线
        self.function_menu.addSeparator()
        
        # 媒体下载
        download_action = QAction(tr("ui.menu_bar.function_menu.download"), self)
        download_action.setObjectName("download_action")
        download_action.setIcon(self._get_icon("download"))
        download_action.setShortcut("Ctrl+1")
        download_action.setStatusTip(tr("ui.menu_bar.function_menu.download_tooltip"))
        download_action.triggered.connect(lambda: self._open_function_view("download"))
        self.function_menu.addAction(download_action)
        
        # 媒体上传
        upload_action = QAction(tr("ui.menu_bar.function_menu.upload"), self)
        upload_action.setObjectName("upload_action")
        upload_action.setIcon(self._get_icon("upload"))
        upload_action.setShortcut("Ctrl+2")
        upload_action.setStatusTip(tr("ui.menu_bar.function_menu.upload_tooltip"))
        upload_action.triggered.connect(lambda: self._open_function_view("upload"))
        self.function_menu.addAction(upload_action)
        
        # 消息转发
        forward_action = QAction(tr("ui.menu_bar.function_menu.forward"), self)
        forward_action.setObjectName("forward_action")
        forward_action.setIcon(self._get_icon("forward"))
        forward_action.setShortcut("Ctrl+3")
        forward_action.setStatusTip(tr("ui.menu_bar.function_menu.forward_tooltip"))
        forward_action.triggered.connect(lambda: self._open_function_view("forward"))
        self.function_menu.addAction(forward_action)
        
        # 实时监听
        monitor_action = QAction(tr("ui.menu_bar.function_menu.monitor"), self)
        monitor_action.setObjectName("monitor_action")
        monitor_action.setIcon(self._get_icon("monitor"))
        monitor_action.setShortcut("Ctrl+4")
        monitor_action.setStatusTip(tr("ui.menu_bar.function_menu.monitor_tooltip"))
        monitor_action.triggered.connect(lambda: self._open_function_view("monitor"))
        self.function_menu.addAction(monitor_action)
    
    def _create_tools_menu(self):
        """创建工具菜单"""
        # 工具菜单
        self.tools_menu = self.menubar.addMenu(tr("ui.menu_bar.tools"))
        

        
        # 日志查看器
        log_viewer_action = QAction(tr("ui.menu_bar.tools_menu.log_viewer"), self)
        log_viewer_action.setObjectName("log_viewer_action")
        log_viewer_action.setIcon(self._get_icon("logs"))
        log_viewer_action.setShortcut("Ctrl+G")
        log_viewer_action.setStatusTip(tr("ui.menu_bar.tools_menu.log_viewer_tooltip"))
        log_viewer_action.triggered.connect(self._open_log_viewer)
        self.tools_menu.addAction(log_viewer_action)
    
    def _create_view_menu(self):
        """创建视图菜单"""
        # 视图菜单
        self.view_menu = self.menubar.addMenu(tr("ui.menu_bar.view"))
        
        # 显示/隐藏侧边栏
        self.show_sidebar_action = QAction(tr("ui.menu_bar.view_menu.sidebar"), self)
        self.show_sidebar_action.setObjectName("show_sidebar_action")
        self.show_sidebar_action.setIcon(self._get_icon("navigation"))
        self.show_sidebar_action.setShortcut("Ctrl+B")
        self.show_sidebar_action.setStatusTip(tr("ui.menu_bar.view_menu.sidebar_tooltip"))
        self.show_sidebar_action.setCheckable(True)
        # 初始状态将在窗口状态加载后设置，避免与保存的状态冲突
        self.show_sidebar_action.triggered.connect(self._toggle_sidebar)
        self.view_menu.addAction(self.show_sidebar_action)
        
        # 视图分隔线
        self.view_menu.addSeparator()
        
        # 工具栏可见性
        self.show_toolbar_action = QAction(tr("ui.menu_bar.view_menu.toolbar"), self)
        self.show_toolbar_action.setObjectName("show_toolbar_action")
        self.show_toolbar_action.setIcon(self._get_icon("toolbar"))
        self.show_toolbar_action.setShortcut("Ctrl+Shift+T")
        self.show_toolbar_action.setStatusTip(tr("ui.menu_bar.view_menu.toolbar_tooltip"))
        self.show_toolbar_action.setCheckable(True)
        self.show_toolbar_action.setChecked(True)
        self.show_toolbar_action.triggered.connect(self._toggle_toolbar)
        self.view_menu.addAction(self.show_toolbar_action)
        
        # 状态栏可见性
        self.show_statusbar_action = QAction(tr("ui.menu_bar.view_menu.statusbar"), self)
        self.show_statusbar_action.setObjectName("show_statusbar_action")
        self.show_statusbar_action.setIcon(self._get_icon("statusbar"))
        self.show_statusbar_action.setShortcut("Ctrl+Shift+S")
        self.show_statusbar_action.setStatusTip(tr("ui.menu_bar.view_menu.statusbar_tooltip"))
        self.show_statusbar_action.setCheckable(True)
        self.show_statusbar_action.setChecked(True)
        self.show_statusbar_action.triggered.connect(self._toggle_statusbar)
        self.view_menu.addAction(self.show_statusbar_action)
    
    def _create_help_menu(self):
        """创建帮助菜单"""
        # 帮助菜单
        self.help_menu = self.menubar.addMenu(tr("ui.menu_bar.help"))
        
        # 帮助文档
        help_doc_action = QAction(tr("ui.menu_bar.help_menu.help_doc"), self)
        help_doc_action.setObjectName("help_doc_action")
        help_doc_action.setIcon(self._get_icon("help"))
        help_doc_action.setShortcut("F1")
        help_doc_action.setStatusTip(tr("ui.menu_bar.help_menu.help_doc_tooltip"))
        help_doc_action.triggered.connect(self._show_help_doc)
        self.help_menu.addAction(help_doc_action)
        
        # 检查更新
        check_update_action = QAction(tr("ui.menu_bar.help_menu.check_update"), self)
        check_update_action.setObjectName("check_update_action")
        check_update_action.setIcon(self._get_icon("update"))
        check_update_action.setShortcut("Ctrl+U")
        check_update_action.setStatusTip(tr("ui.menu_bar.help_menu.check_update_tooltip"))
        check_update_action.triggered.connect(self._check_update)
        self.help_menu.addAction(check_update_action)
        
        # 帮助分隔线
        self.help_menu.addSeparator()
        
        # 关于动作
        about_action = QAction(tr("ui.menu_bar.help_menu.about"), self)
        about_action.setObjectName("about_action")
        about_action.setIcon(self._get_icon("about"))
        about_action.setShortcut("Ctrl+Shift+A")
        about_action.setStatusTip(tr("ui.menu_bar.help_menu.about_tooltip"))
        about_action.triggered.connect(self._show_about)
        self.help_menu.addAction(about_action) 