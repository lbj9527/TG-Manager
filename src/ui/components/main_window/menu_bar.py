"""
TG-Manager 主窗口菜单栏模块
包含主窗口的菜单栏创建和菜单功能实现
"""

from loguru import logger
from PySide6.QtWidgets import QMenu
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction

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
        self._create_config_menu()
        self._create_tools_menu()
        self._create_view_menu()
        self._create_help_menu()
        
        logger.debug("主菜单栏创建完成")
    
    def _create_file_menu(self):
        """创建文件菜单"""
        # 文件菜单
        self.file_menu = self.menubar.addMenu("文件")
        
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
    
    def _create_config_menu(self):
        """创建配置菜单"""
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
    
    def _create_tools_menu(self):
        """创建工具菜单"""
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
    
    def _create_view_menu(self):
        """创建视图菜单"""
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
    
    def _create_help_menu(self):
        """创建帮助菜单"""
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