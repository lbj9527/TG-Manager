"""
TG-Manager 主窗口侧边栏模块
包含导航树和任务概览相关功能
"""

from loguru import logger
from PySide6.QtWidgets import (
    QDockWidget, QSplitter, QMessageBox, 
    QWidget, QVBoxLayout, QLabel, QHBoxLayout
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
    

    
    def _create_sidebar_splitter(self):
        """创建左侧侧边栏，包含导航树"""

        
        # 移除之前添加的停靠窗口
        if hasattr(self, 'nav_dock'):
    
            self.removeDockWidget(self.nav_dock)
        
        # 创建新的停靠窗口，包含导航树
        from src.utils.translation_manager import tr
        sidebar_title = tr("ui.sidebar.title") if hasattr(self, 'translation_manager') else "导航"

        
        self.sidebar_dock = QDockWidget("", self)  # 标题留空，使用自定义标题栏
        self.sidebar_dock.setObjectName("sidebar_dock")
        self.sidebar_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.sidebar_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        
        # 直接将导航树添加到停靠窗口，不使用分割器

        self.sidebar_dock.setWidget(self.nav_tree)
        
        # 将停靠窗口添加到左侧区域

        self.addDockWidget(Qt.LeftDockWidgetArea, self.sidebar_dock)
        
        # 连接停靠窗口状态变化信号，确保位置变化时能保存状态
        self.sidebar_dock.dockLocationChanged.connect(self._on_sidebar_dock_changed)
        self.sidebar_dock.topLevelChanged.connect(self._on_sidebar_dock_changed)
        self.sidebar_dock.visibilityChanged.connect(self._on_sidebar_dock_changed)

        
        # 安装事件过滤器来监听停靠窗口的调整大小事件
        self.sidebar_dock.installEventFilter(self)

        
        # 记录停靠窗口的最终状态

        
        # 保存初始几何形状用于恢复
        self._last_sidebar_geometry = self.sidebar_dock.geometry()

        
        # 设置自定义多行标题栏
        self._set_sidebar_title(sidebar_title)
        

    

    

    
    def _on_sidebar_dock_changed(self, *args):
        """处理侧边栏停靠窗口状态变化事件
        
        当停靠窗口位置改变、浮动状态改变或可见性改变时触发
        
        Args:
            *args: 信号参数（不同信号参数不同）
        """

        
        # 使用延迟保存机制，避免状态变化过程中频繁保存
        if not hasattr(self, '_dock_save_timer'):
            from PySide6.QtCore import QTimer
            self._dock_save_timer = QTimer(self)
            self._dock_save_timer.setSingleShot(True)
            self._dock_save_timer.timeout.connect(self._save_current_state)
        
        # 重新开始定时器
        self._dock_save_timer.stop()
        self._dock_save_timer.start(500)  # 500毫秒后保存
    
    def _set_sidebar_title(self, text: str):
        """自定义侧边栏标题栏，支持多行显示"""
        if not hasattr(self, '_sidebar_title_label'):
            # 创建自定义标题栏
            title_widget = QWidget()
            layout = QHBoxLayout(title_widget)
            layout.setContentsMargins(6, 0, 0, 0)
            label = QLabel()
            label.setWordWrap(True)
            label.setStyleSheet("font-weight: bold;")
            layout.addWidget(label)
            self.sidebar_dock.setTitleBarWidget(title_widget)
            self._sidebar_title_label = label
        self._sidebar_title_label.setText(text)
    
    def _update_sidebar_translations(self):
        """更新侧边栏的翻译文本"""

        
        if hasattr(self, 'sidebar_dock'):
            from src.utils.translation_manager import tr
            new_title = tr("ui.sidebar.title")

            
            # 使用自定义多行标题栏
            self._set_sidebar_title(new_title)
            
            # 保存当前停靠窗口的状态
            current_geometry = self.sidebar_dock.geometry()
            current_size = self.sidebar_dock.size()
            
            # 验证状态是否保持
            new_geometry = self.sidebar_dock.geometry()
            new_size = self.sidebar_dock.size()
            
            # 如果尺寸发生变化，使用强制恢复机制
            if current_size != new_size:
                
                # 方法1: 直接恢复尺寸
                self.sidebar_dock.resize(current_size)
                
                # 方法2: 如果直接恢复失败，使用setFixedSize强制设置
                QTimer.singleShot(10, lambda: self._force_restore_sidebar_size(current_size))
                
                # 方法3: 延迟验证和再次恢复
                QTimer.singleShot(50, lambda: self._verify_and_restore_sidebar_size(current_size, None))
        
        # 更新导航树翻译
        if hasattr(self, 'nav_tree') and hasattr(self.nav_tree, '_update_translations'):
            self.nav_tree._update_translations()
        

        

    
    def eventFilter(self, obj, event):
        """事件过滤器，监听侧边栏停靠窗口的调整大小事件
        
        Args:
            obj: 事件源对象
            event: 事件对象
            
        Returns:
            bool: 是否已处理事件
        """
        # 检查事件是否来自侧边栏停靠窗口
        if hasattr(self, 'sidebar_dock') and obj == self.sidebar_dock:
            from PySide6.QtCore import QEvent
            if event.type() == QEvent.Resize:          
                # 使用延迟保存机制，避免调整过程中频繁保存
                if not hasattr(self, '_dock_resize_timer'):
                    from PySide6.QtCore import QTimer
                    self._dock_resize_timer = QTimer(self)
                    self._dock_resize_timer.setSingleShot(True)
                    self._dock_resize_timer.timeout.connect(self._save_current_state)
        
                
                # 重新开始定时器
                self._dock_resize_timer.stop()
                self._dock_resize_timer.start(500)  # 500毫秒后保存

        
        # 继续正常事件处理
        return super().eventFilter(obj, event)
    
    def _force_restore_sidebar_size(self, target_size):
        """强制恢复侧边栏尺寸
        
        Args:
            target_size: 目标尺寸
        """
        if hasattr(self, 'sidebar_dock'):
            current_size = self.sidebar_dock.size()
            if current_size != target_size:
                logger.debug(f"强制恢复侧边栏尺寸: {current_size} -> {target_size}")
                
                # 临时设置固定尺寸
                self.sidebar_dock.setFixedSize(target_size)
                
                # 延迟恢复为可调整尺寸
                QTimer.singleShot(100, lambda: self.sidebar_dock.setFixedSize(0, 0))
    
    def _verify_and_restore_sidebar_size(self, target_size, target_sizes):
        """验证并恢复侧边栏尺寸
        
        Args:
            target_size: 目标尺寸
            target_sizes: 目标分割器尺寸（已不使用）
        """
        if hasattr(self, 'sidebar_dock'):
            current_size = self.sidebar_dock.size()
            
            logger.debug(f"验证侧边栏尺寸 - 当前: {current_size}, 目标: {target_size}")
            
            # 如果尺寸仍然不正确，再次尝试恢复
            if current_size != target_size:
                logger.warning(f"侧边栏尺寸仍未恢复，再次尝试: {current_size} -> {target_size}")
                self.sidebar_dock.resize(target_size)
                
                # 使用几何形状恢复作为最后手段
                if hasattr(self, '_last_sidebar_geometry'):
                    self.sidebar_dock.setGeometry(self._last_sidebar_geometry)
    
    def _toggle_sidebar(self, checked):
        """切换侧边栏的可见性
        
        Args:
            checked: 是否显示
        """
        if hasattr(self, 'sidebar_dock'):
    
            self.sidebar_dock.setVisible(checked)
            
            # 保存当前状态
            if hasattr(self, '_save_current_state'):
                self._save_current_state()
    

    
    def _handle_navigation(self, item_id, item_data):
        """处理导航树项目的点击事件
        
        Args:
            item_id: 树项ID
            item_data: 树项关联数据
        """
        logger.debug(f"处理导航: {item_id} -> {item_data}")
        
        # 检查应用程序是否正在初始化
        if hasattr(self, 'app') and hasattr(self.app, 'is_initializing') and self.app.is_initializing:
            self.show_status_message("系统正在初始化中，请稍等...", 3000)
            logger.warning(f"用户尝试在初始化完成前访问功能: {item_id}")
            return
            
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
            if function_name == 'download':
                if hasattr(view, 'set_downloader'):
                    # 读取配置文件中的parallel_download设置
                    parallel_download = False
                    try:
                        if hasattr(app, 'ui_config_manager'):
                            download_config = app.ui_config_manager.get_download_config()
                            parallel_download = download_config.parallel_download
                            logger.info(f"从配置读取parallel_download设置: {parallel_download}")
                    except Exception as config_error:
                        logger.error(f"读取parallel_download配置时出错: {config_error}")
                    
                    # 根据parallel_download设置选择下载器
                    if parallel_download and hasattr(app, 'downloader'):
                        view.set_downloader(app.downloader)
                        logger.info("下载视图已设置并行下载器实例")
                    elif not parallel_download and hasattr(app, 'downloader_serial'):
                        view.set_downloader(app.downloader_serial)
                        logger.info("下载视图已设置串行下载器实例")
                    else:
                        # 回退到可用的下载器
                        if hasattr(app, 'downloader'):
                            view.set_downloader(app.downloader)
                            logger.info("下载视图已设置并行下载器实例(回退选择)")
                        elif hasattr(app, 'downloader_serial'):
                            view.set_downloader(app.downloader_serial)
                            logger.info("下载视图已设置串行下载器实例(回退选择)")
                        else:
                            logger.warning("没有可用的下载器实例")
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
                    

            
        except Exception as e:
            logger.error(f"连接{function_name}视图到功能模块时出错: {e}")
            import traceback
            logger.error(f"错误详情:\n{traceback.format_exc()}") 