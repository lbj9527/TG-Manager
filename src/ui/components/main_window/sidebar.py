"""
TG-Manager 主窗口侧边栏模块
包含导航树和任务概览相关功能
"""

from loguru import logger
from PySide6.QtWidgets import (
    QDockWidget, QSplitter, QMessageBox, 
    QWidget, QVBoxLayout
)
from PySide6.QtCore import Qt, QTimer

class SidebarMixin:
    """侧边栏功能混入类
    
    为MainWindow提供侧边栏相关功能，包括导航树和任务概览
    """
    
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
        
        logger.debug("侧边栏创建完成")
    
    def _init_splitter_sizes(self):
        """初始化分割器尺寸，确保导航树高度稳定"""
        if hasattr(self, 'sidebar_splitter'):
            # 重新设置尺寸一次，以防止初始化过程中的计算误差
            current_sizes = self.sidebar_splitter.sizes()
            self.sidebar_splitter.setSizes(current_sizes)
    
    def _toggle_sidebar(self, checked):
        """切换侧边栏的可见性
        
        Args:
            checked: 是否显示
        """
        if hasattr(self, 'sidebar_dock'):
            self.sidebar_dock.setVisible(checked)
    
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
            
            # 在视图创建后立即连接功能模块
            self._connect_view_to_modules(function_name, view)
    
    def _connect_view_to_modules(self, function_name, view):
        """将视图连接到相应的功能模块
        
        Args:
            function_name: 功能名称
            view: 视图实例
        """
        # 检查是否有app属性
        if not hasattr(self, 'app'):
            logger.warning(f"无法将{function_name}视图连接到功能模块：MainWindow缺少app属性")
            return
            
        app = self.app
        
        try:
            if function_name == 'download' and hasattr(app, 'downloader'):
                if hasattr(view, 'set_downloader'):
                    view.set_downloader(app.downloader)
                    logger.info("下载视图已设置下载器实例")
                else:
                    logger.warning("下载视图缺少set_downloader方法")
                    
            elif function_name == 'upload' and hasattr(app, 'uploader'):
                if hasattr(view, 'set_uploader'):
                    view.set_uploader(app.uploader)
                    logger.info("上传视图已设置上传器实例")
                else:
                    logger.warning("上传视图缺少set_uploader方法")
                    
            elif function_name == 'forward' and hasattr(app, 'forwarder'):
                if hasattr(view, 'set_forwarder'):
                    view.set_forwarder(app.forwarder)
                    logger.info("转发视图已设置转发器实例")
                else:
                    logger.warning("转发视图缺少set_forwarder方法")
                    
            elif function_name == 'monitor' and hasattr(app, 'monitor'):
                if hasattr(view, 'set_monitor'):
                    view.set_monitor(app.monitor)
                    logger.info("监听视图已设置监听器实例")
                else:
                    logger.warning("监听视图缺少set_monitor方法")
                    
            elif function_name == 'task_manager' and hasattr(app, 'task_manager'):
                if hasattr(view, 'set_task_manager'):
                    view.set_task_manager(app.task_manager)
                    logger.info("任务视图已设置任务管理器实例")
                else:
                    logger.warning("任务视图缺少set_task_manager方法")
            
        except Exception as e:
            logger.error(f"连接{function_name}视图到功能模块时出错: {e}")
            import traceback
            logger.error(f"错误详情:\n{traceback.format_exc()}") 