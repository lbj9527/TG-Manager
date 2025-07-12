"""
TG-Manager 主窗口状态管理模块
包含窗口几何形状、布局、状态的保存和恢复功能
"""

from loguru import logger
from PySide6.QtCore import QByteArray, QTimer
import time

class WindowStateMixin:
    """窗口状态管理混入类
    
    为MainWindow提供窗口状态管理功能
    """
    
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
            
            # 加载窗口状态（停靠窗口、工具栏位置等）
            if 'window_state' in ui_config:
                try:
                    state = ui_config.get('window_state')
                    if state:

                        
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
                            pass  # 窗口状态恢复成功，无需额外操作
                except Exception as e:
                    logger.warning(f"恢复窗口状态失败: {e}")
            
            # 恢复侧边栏几何形状
            if 'sidebar_geometry' in ui_config:
                try:
                    sidebar_geo = ui_config.get('sidebar_geometry')

                    if sidebar_geo and isinstance(sidebar_geo, dict):
                        from PySide6.QtCore import QRect
                        
                        # 从配置中读取具体值
                        x = sidebar_geo.get('x', 0)
                        y = sidebar_geo.get('y', 0) 
                        width = sidebar_geo.get('width', 200)
                        height = sidebar_geo.get('height', 600)
                        

                        
                        restored_geometry = QRect(x, y, width, height)

                        
                        # 延迟恢复侧边栏几何形状，确保侧边栏已创建
                        QTimer.singleShot(100, lambda: self._restore_sidebar_geometry(restored_geometry))
                except Exception as e:
                    logger.warning(f"恢复侧边栏几何形状失败: {e}")
                    import traceback

            
            # 恢复侧边栏完整状态（包括分割器状态）
            if 'sidebar_data' in ui_config:
                try:
                    sidebar_data = ui_config.get('sidebar_data')
                    if sidebar_data and isinstance(sidebar_data, dict):

                        
                        # 恢复可见性和浮动状态
                        if 'visible' in sidebar_data:
                            QTimer.singleShot(200, lambda: self._restore_sidebar_visibility(sidebar_data['visible']))
                            # 同步菜单按钮状态
                            QTimer.singleShot(200, lambda: self._sync_sidebar_menu_state(sidebar_data['visible']))
                        if 'floating' in sidebar_data:
                            QTimer.singleShot(250, lambda: self._restore_sidebar_floating(sidebar_data['floating']))
                        
                        # 恢复分割器状态
                        if 'splitter_sizes' in sidebar_data and sidebar_data['splitter_sizes']:
                            splitter_sizes = sidebar_data['splitter_sizes']

                            QTimer.singleShot(300, lambda: self._restore_splitter_sizes(splitter_sizes))
                        
                except Exception as e:
                    logger.warning(f"恢复侧边栏完整状态失败: {e}")
        else:
            # 如果没有保存的侧边栏状态，设置默认可见
            # logger.debug("没有保存的侧边栏状态，设置默认可见")
            QTimer.singleShot(200, lambda: self._restore_sidebar_visibility(True))
            QTimer.singleShot(200, lambda: self._sync_sidebar_menu_state(True))
        
        # 确保所有窗口元素正确显示
        self.update()
    
    def _save_window_state(self, state_data):
        """保存窗口状态
        
        Args:
            state_data: 窗口状态数据
        """
        try:
            # 直接调用app的配置管理器来保存窗口状态，避免信号循环
            if hasattr(self, 'app') and hasattr(self.app, 'config_manager'):
                config_manager = self.app.config_manager
                
                # 检查是否在短时间内多次触发保存
                current_time = time.time()
                if hasattr(config_manager, '_last_window_state_save_time'):
                    # 如果上次保存时间距现在不足500毫秒，则跳过本次保存
                    if current_time - config_manager._last_window_state_save_time < 0.5:
                        # logger.debug("窗口状态保存请求过于频繁，跳过本次保存")
                        return
                
                # 更新上次保存时间
                config_manager._last_window_state_save_time = current_time
                
                try:
                    # 更新内存中的窗口状态配置
                    ui_config = self.config.get('UI', {})
                    
                    # 更新窗口状态数据
                    if 'geometry' in state_data:
                        ui_config['window_geometry'] = state_data['geometry'].toBase64().data().decode()
                        # logger.debug("保存了窗口几何形状")
                    
                    if 'state' in state_data:
                        ui_config['window_state'] = state_data['state'].toBase64().data().decode()
                        # logger.debug("保存了窗口状态，包括工具栏位置")
                    
                    # 保存侧边栏几何形状
                    if 'sidebar_geometry' in state_data:
                        sidebar_geo = state_data['sidebar_geometry']
                        ui_config['sidebar_geometry'] = {
                            'x': sidebar_geo.x(),
                            'y': sidebar_geo.y(),
                            'width': sidebar_geo.width(),
                            'height': sidebar_geo.height()
                        }
                        # logger.debug(f"保存了侧边栏几何形状: {ui_config['sidebar_geometry']}")
                    
                    # 保存侧边栏完整状态（包括分割器状态）
                    if 'sidebar_data' in state_data:
                        sidebar_data = state_data['sidebar_data']
                        ui_config['sidebar_data'] = {
                            'floating': sidebar_data.get('floating', False),
                            'visible': sidebar_data.get('visible', True),
                            'splitter_sizes': sidebar_data.get('splitter_sizes', [])
                        }
                        # logger.debug(f"保存了侧边栏完整状态: {ui_config['sidebar_data']}")
                    
                    # 更新配置
                    self.config['UI'] = ui_config
                    config_manager.config['UI'] = ui_config
                    
                    # 仅保存窗口布局相关的配置项，不修改其他配置
                    try:
                        import json
                        # 从文件读取当前配置
                        with open(config_manager.ui_config_manager.config_path, 'r', encoding='utf-8') as f:
                            file_config = json.load(f)
                        
                        # 确保UI部分存在
                        if 'UI' not in file_config:
                            file_config['UI'] = {}
                        
                        # 只更新窗口几何信息和状态，不影响其他配置
                        file_config['UI']['window_geometry'] = ui_config['window_geometry']
                        file_config['UI']['window_state'] = ui_config['window_state']
                        
                        # 添加侧边栏几何形状的保存（修复侧边栏宽度无法保存的问题）
                        if 'sidebar_geometry' in ui_config:
                            file_config['UI']['sidebar_geometry'] = ui_config['sidebar_geometry']
                            # logger.debug(f"保存侧边栏几何形状到配置文件: {ui_config['sidebar_geometry']}")
                        
                        # 添加侧边栏完整状态的保存（包括分割器状态）
                        if 'sidebar_data' in ui_config:
                            file_config['UI']['sidebar_data'] = ui_config['sidebar_data']
                            # logger.debug(f"保存侧边栏完整状态到配置文件: {ui_config['sidebar_data']}")
                        
                        # 保存回文件
                        with open(config_manager.ui_config_manager.config_path, 'w', encoding='utf-8') as f:
                            json.dump(file_config, f, ensure_ascii=False, indent=2)
                        
                        # logger.debug("窗口布局状态已单独保存，未影响其他配置")
                    except PermissionError:
                        logger.warning("保存窗口布局状态时遇到权限问题，将在下次完整保存配置时一并处理")
                    except Exception as e:
                        logger.error(f"保存窗口布局状态失败: {e}")
                        import traceback

                        
                except Exception as e:
                    logger.error(f"获取窗口状态失败: {e}")
                    import traceback

            else:
                logger.warning("无法访问配置管理器，窗口状态保存失败")
                
        except Exception as e:
            logger.error(f"保存窗口状态失败: {e}")
            import traceback

    
    def _save_current_state(self):
        """保存当前窗口状态（只保存窗口几何信息和工具栏位置等布局状态）
        
        注意：此方法只会保存窗口的布局相关配置，不会影响其他配置项如主题设置等。
        这些布局状态没有单独的保存按钮，因此会自动保存，以便在下次启动时恢复布局。
        """
        window_state = {
            'geometry': self.saveGeometry(),
            'state': self.saveState()
        }
        
        # 保存侧边栏几何形状
        if hasattr(self, 'sidebar_dock'):
            sidebar_data = {
                'geometry': self.sidebar_dock.geometry(),
                'floating': self.sidebar_dock.isFloating(),
                'visible': self.sidebar_dock.isVisible()
            }
            
            # 当前实现使用QDockWidget而不是QSplitter，所以不需要保存分割器状态
            # if hasattr(self, 'sidebar_splitter'):
            #     sidebar_data['splitter_sizes'] = self.sidebar_splitter.sizes()
            #     logger.debug(f"保存分割器状态: {sidebar_data['splitter_sizes']}")
            
            window_state['sidebar_geometry'] = sidebar_data['geometry']
            window_state['sidebar_data'] = sidebar_data
            # logger.debug(f"保存侧边栏完整状态: {sidebar_data}")
        
        # logger.debug("保存窗口布局状态，包括窗口几何信息和工具栏位置")
        self.window_state_changed.emit(window_state)
    
    def showEvent(self, event):
        """窗口显示事件处理
        
        当窗口首次显示时，我们需要初始化一些UI元素
        
        Args:
            event: 显示事件对象
        """
        # 调用父类方法
        super().showEvent(event)
        
        # 如果是第一次显示窗口，执行一些初始化
        if not self._is_window_state_loaded and self.isVisible():
            # 移除对不存在方法的调用，因为当前使用QDockWidget而不是QSplitter
            # self._init_splitter_sizes()
            self._is_window_state_loaded = True
        
        # 显示窗口时立即检查网络状态，确保状态栏显示最新信息
        if hasattr(self, '_check_network_status'):
            self._check_network_status()
    
    def resizeEvent(self, event):
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

        
        # 检查是否正在进行语言切换，如果是则跳过分割器尺寸调整
        if hasattr(self, 'translation_manager') and hasattr(self.translation_manager, '_is_language_changing'):
            if self.translation_manager._is_language_changing:
                logger.debug("检测到语言切换，跳过分割器尺寸调整")
                # 发出窗口状态变化信号但不调整分割器
                window_state = {
                    'geometry': self.saveGeometry(),
                    'state': self.saveState()
                }
                self.window_state_changed.emit(window_state)
                return
        
        # 发出窗口状态变化信号
        window_state = {
            'geometry': self.saveGeometry(),
            'state': self.saveState()
        }

        self.window_state_changed.emit(window_state)

    
    def eventFilter(self, obj, event):
        """事件过滤器，用于捕获工具栏的鼠标事件
        
        Args:
            obj: 事件源对象
            event: 事件对象
            
        Returns:
            bool: 是否已处理事件
        """
        # 检查事件是否来自工具栏
        if hasattr(self, 'toolbar') and obj == self.toolbar:
            # 捕获鼠标释放事件，通常是拖动结束
            from PySide6.QtCore import QEvent
            if event.type() == QEvent.MouseButtonRelease:
                logger.debug("检测到工具栏鼠标释放事件，可能是拖动结束")
                # 使用工具栏模块中的状态变化处理器，避免多次保存
                if hasattr(self, '_on_toolbar_state_changed'):
                    self._on_toolbar_state_changed()
            # 注意：移动事件不再单独处理，避免触发过多的保存
            
        # 继续正常事件处理
        return super().eventFilter(obj, event)
    
    def _restore_sidebar_geometry(self, geometry):
        """恢复侧边栏几何形状
        
        Args:
            geometry: 要恢复的几何形状
        """
        if hasattr(self, 'sidebar_dock'):
            try:
                # 恢复几何形状
                self.sidebar_dock.setGeometry(geometry)
                
                # 更新保存的几何形状
                self._last_sidebar_geometry = geometry
                
                # 验证恢复是否成功
                actual_geometry = self.sidebar_dock.geometry()
                
                if actual_geometry.width() != geometry.width() or actual_geometry.height() != geometry.height():
                    logger.warning(f"侧边栏几何形状恢复不完全匹配: 期望 {geometry}, 实际 {actual_geometry}")
                    
                    # 尝试使用resize方法
                    self.sidebar_dock.resize(geometry.width(), geometry.height())
                    
            except Exception as e:
                logger.error(f"恢复侧边栏几何形状时出错: {e}")
                import traceback

    
    def _restore_sidebar_visibility(self, visible):
        """恢复侧边栏可见性
        
        Args:
            visible: 是否可见
        """
        if hasattr(self, 'sidebar_dock'):
            try:
        
                self.sidebar_dock.setVisible(visible)
            except Exception as e:
                logger.error(f"恢复侧边栏可见性时出错: {e}")
    
    def _restore_sidebar_floating(self, floating):
        """恢复侧边栏浮动状态
        
        Args:
            floating: 是否浮动
        """
        if hasattr(self, 'sidebar_dock'):
            try:
        
                self.sidebar_dock.setFloating(floating)
            except Exception as e:
                logger.error(f"恢复侧边栏浮动状态时出错: {e}")
    
    def _restore_splitter_sizes(self, sizes):
        """恢复分割器大小
        
        Args:
            sizes: 分割器大小列表
        """
        # 当前实现使用QDockWidget而不是QSplitter，所以不需要恢复分割器大小
        logger.debug(f"当前实现使用QDockWidget，跳过分割器大小恢复: {sizes}")
        
        # if hasattr(self, 'sidebar_splitter') and sizes:
        #     try:
        #         logger.debug(f"恢复分割器大小: {sizes}")
        #         self.sidebar_splitter.setSizes(sizes)
        #         
        #         # 验证恢复是否成功
        #         actual_sizes = self.sidebar_splitter.sizes()
        #         if actual_sizes != sizes:
        #             logger.warning(f"分割器大小恢复失败: 期望 {sizes}, 实际 {actual_sizes}")
        #         else:
        #             logger.debug("分割器大小恢复成功")
        #     except Exception as e:
        #         logger.error(f"恢复分割器大小时出错: {e}")
    
    def _sync_sidebar_menu_state(self, visible):
        """同步侧边栏菜单按钮状态
        
        Args:
            visible: 侧边栏是否可见
        """
        if hasattr(self, 'show_sidebar_action'):
            try:
        
                self.show_sidebar_action.setChecked(visible)
            except Exception as e:
                logger.error(f"同步侧边栏菜单按钮状态时出错: {e}") 