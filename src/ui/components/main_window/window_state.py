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
            
            # 恢复侧边栏几何形状
            if 'sidebar_geometry' in ui_config:
                try:
                    sidebar_geo = ui_config.get('sidebar_geometry')
                    logger.debug(f"读取到的侧边栏几何配置: {sidebar_geo}")
                    if sidebar_geo and isinstance(sidebar_geo, dict):
                        from PySide6.QtCore import QRect
                        
                        # 从配置中读取具体值
                        x = sidebar_geo.get('x', 0)
                        y = sidebar_geo.get('y', 0) 
                        width = sidebar_geo.get('width', 200)
                        height = sidebar_geo.get('height', 600)
                        
                        logger.debug(f"侧边栏几何参数: x={x}, y={y}, width={width}, height={height}")
                        
                        restored_geometry = QRect(x, y, width, height)
                        logger.debug(f"正在恢复侧边栏几何形状: {restored_geometry}")
                        
                        # 延迟恢复侧边栏几何形状，确保侧边栏已创建
                        QTimer.singleShot(100, lambda: self._restore_sidebar_geometry(restored_geometry))
                except Exception as e:
                    logger.warning(f"恢复侧边栏几何形状失败: {e}")
                    import traceback
                    logger.debug(f"恢复侧边栏几何形状错误详情:\n{traceback.format_exc()}")
            
            # 恢复侧边栏完整状态（包括分割器状态）
            if 'sidebar_data' in ui_config:
                try:
                    sidebar_data = ui_config.get('sidebar_data')
                    if sidebar_data and isinstance(sidebar_data, dict):
                        logger.debug(f"正在恢复侧边栏完整状态: {sidebar_data}")
                        
                        # 恢复可见性和浮动状态
                        if 'visible' in sidebar_data:
                            QTimer.singleShot(200, lambda: self._restore_sidebar_visibility(sidebar_data['visible']))
                        if 'floating' in sidebar_data:
                            QTimer.singleShot(250, lambda: self._restore_sidebar_floating(sidebar_data['floating']))
                        
                        # 恢复分割器状态
                        if 'splitter_sizes' in sidebar_data and sidebar_data['splitter_sizes']:
                            splitter_sizes = sidebar_data['splitter_sizes']
                            logger.debug(f"正在恢复分割器状态: {splitter_sizes}")
                            QTimer.singleShot(300, lambda: self._restore_splitter_sizes(splitter_sizes))
                        
                except Exception as e:
                    logger.warning(f"恢复侧边栏完整状态失败: {e}")
        
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
                        logger.debug("窗口状态保存请求过于频繁，跳过本次保存")
                        return
                
                # 更新上次保存时间
                config_manager._last_window_state_save_time = current_time
                
                try:
                    # 更新内存中的窗口状态配置
                    ui_config = self.config.get('UI', {})
                    
                    # 更新窗口状态数据
                    if 'geometry' in state_data:
                        ui_config['window_geometry'] = state_data['geometry'].toBase64().data().decode()
                        logger.debug("保存了窗口几何形状")
                    
                    if 'state' in state_data:
                        ui_config['window_state'] = state_data['state'].toBase64().data().decode()
                        logger.debug("保存了窗口状态，包括工具栏位置")
                    
                    # 保存侧边栏几何形状
                    if 'sidebar_geometry' in state_data:
                        sidebar_geo = state_data['sidebar_geometry']
                        ui_config['sidebar_geometry'] = {
                            'x': sidebar_geo.x(),
                            'y': sidebar_geo.y(),
                            'width': sidebar_geo.width(),
                            'height': sidebar_geo.height()
                        }
                        logger.debug(f"保存了侧边栏几何形状: {ui_config['sidebar_geometry']}")
                    
                    # 保存侧边栏完整状态（包括分割器状态）
                    if 'sidebar_data' in state_data:
                        sidebar_data = state_data['sidebar_data']
                        ui_config['sidebar_data'] = {
                            'floating': sidebar_data.get('floating', False),
                            'visible': sidebar_data.get('visible', True),
                            'splitter_sizes': sidebar_data.get('splitter_sizes', [])
                        }
                        logger.debug(f"保存了侧边栏完整状态: {ui_config['sidebar_data']}")
                    
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
                            logger.debug(f"保存侧边栏几何形状到配置文件: {ui_config['sidebar_geometry']}")
                        
                        # 添加侧边栏完整状态的保存（包括分割器状态）
                        if 'sidebar_data' in ui_config:
                            file_config['UI']['sidebar_data'] = ui_config['sidebar_data']
                            logger.debug(f"保存侧边栏完整状态到配置文件: {ui_config['sidebar_data']}")
                        
                        # 保存回文件
                        with open(config_manager.ui_config_manager.config_path, 'w', encoding='utf-8') as f:
                            json.dump(file_config, f, ensure_ascii=False, indent=2)
                        
                        logger.debug("窗口布局状态已单独保存，未影响其他配置")
                    except PermissionError:
                        logger.warning("保存窗口布局状态时遇到权限问题，将在下次完整保存配置时一并处理")
                    except Exception as e:
                        logger.error(f"保存窗口布局状态失败: {e}")
                        import traceback
                        logger.debug(f"保存窗口布局状态错误详情:\n{traceback.format_exc()}")
                        
                except Exception as e:
                    logger.error(f"获取窗口状态失败: {e}")
                    import traceback
                    logger.debug(f"获取窗口状态错误详情:\n{traceback.format_exc()}")
            else:
                logger.warning("无法访问配置管理器，窗口状态保存失败")
                
        except Exception as e:
            logger.error(f"保存窗口状态失败: {e}")
            import traceback
            logger.debug(f"保存窗口状态错误详情:\n{traceback.format_exc()}")
    
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
            
            # 保存分割器状态
            if hasattr(self, 'sidebar_splitter'):
                sidebar_data['splitter_sizes'] = self.sidebar_splitter.sizes()
                logger.debug(f"保存分割器状态: {sidebar_data['splitter_sizes']}")
            
            window_state['sidebar_geometry'] = sidebar_data['geometry']
            window_state['sidebar_data'] = sidebar_data
            logger.debug(f"保存侧边栏完整状态: {sidebar_data}")
        
        logger.debug("保存窗口布局状态，包括窗口几何信息和工具栏位置")
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
            self._init_splitter_sizes()
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
        logger.debug(f"=== 窗口大小调整完成处理开始 ===")
        logger.debug(f"当前窗口尺寸: {self.width()}x{self.height()}")
        
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
        
        if hasattr(self, 'sidebar_splitter'):
            logger.debug(f"侧边栏分割器存在，当前尺寸: {self.sidebar_splitter.sizes()}")
            
            # 获取当前窗口高度
            current_height = self.height()
            logger.debug(f"当前窗口高度: {current_height}")
            
            # 获取当前分割器尺寸
            current_sizes = self.sidebar_splitter.sizes()
            nav_height = current_sizes[0]  # 导航树当前高度
            logger.debug(f"当前分割器尺寸: {current_sizes}, 导航树高度: {nav_height}")
            
            # 检查是否有用户保存的分割器设置
            has_saved_splitter_sizes = False
            if hasattr(self, 'config') and 'UI' in self.config:
                ui_config = self.config['UI']
                if 'sidebar_data' in ui_config and 'splitter_sizes' in ui_config['sidebar_data']:
                    saved_sizes = ui_config['sidebar_data']['splitter_sizes']
                    if saved_sizes and len(saved_sizes) == 2:
                        has_saved_splitter_sizes = True
                        logger.debug(f"检测到保存的分割器设置: {saved_sizes}")
            
            # 只有当窗口高度大于阈值且没有保存的分割器设置时才调整
            if current_height > 400 and not has_saved_splitter_sizes:
                logger.debug("窗口高度大于400且无保存的分割器设置，使用默认50%分割")
                # 调整为50%导航树，50%任务概览
                new_sizes = [int(current_height * 0.5), int(current_height * 0.5)]
                logger.debug(f"设置新的分割器尺寸: {new_sizes}")
                self.sidebar_splitter.setSizes(new_sizes)
                
                # 验证设置是否成功
                actual_sizes = self.sidebar_splitter.sizes()
                logger.debug(f"设置后的实际分割器尺寸: {actual_sizes}")
            elif has_saved_splitter_sizes:
                logger.debug("检测到保存的分割器设置，保持当前用户配置")
            else:
                logger.debug(f"窗口高度 {current_height} 小于等于400，跳过分割器调整")
        else:
            logger.warning("侧边栏分割器不存在")
        
        # 发出窗口状态变化信号
        window_state = {
            'geometry': self.saveGeometry(),
            'state': self.saveState()
        }
        logger.debug("发出窗口状态变化信号")
        self.window_state_changed.emit(window_state)
        logger.debug("=== 窗口大小调整完成处理结束 ===")
    
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
                logger.info(f"=== 开始恢复侧边栏几何形状 ===")
                logger.info(f"目标几何形状: {geometry}")
                logger.info(f"目标宽度: {geometry.width()}, 目标高度: {geometry.height()}")
                
                # 获取当前几何形状
                current_geometry = self.sidebar_dock.geometry()
                logger.info(f"当前几何形状: {current_geometry}")
                
                # 恢复几何形状
                self.sidebar_dock.setGeometry(geometry)
                
                # 更新保存的几何形状
                self._last_sidebar_geometry = geometry
                
                # 验证恢复是否成功
                actual_geometry = self.sidebar_dock.geometry()
                logger.info(f"恢复后实际几何形状: {actual_geometry}")
                
                if actual_geometry.width() != geometry.width() or actual_geometry.height() != geometry.height():
                    logger.warning(f"侧边栏几何形状恢复不完全匹配: 期望 {geometry}, 实际 {actual_geometry}")
                    
                    # 尝试使用resize方法
                    logger.info("尝试使用resize方法恢复尺寸")
                    self.sidebar_dock.resize(geometry.width(), geometry.height())
                    
                    # 再次验证
                    final_geometry = self.sidebar_dock.geometry()
                    logger.info(f"使用resize后的几何形状: {final_geometry}")
                else:
                    logger.info("侧边栏几何形状恢复成功")
                    
                logger.info(f"=== 侧边栏几何形状恢复完成 ===")
            except Exception as e:
                logger.error(f"恢复侧边栏几何形状时出错: {e}")
                import traceback
                logger.debug(f"恢复侧边栏几何形状错误详情:\n{traceback.format_exc()}")
    
    def _restore_sidebar_visibility(self, visible):
        """恢复侧边栏可见性
        
        Args:
            visible: 是否可见
        """
        if hasattr(self, 'sidebar_dock'):
            try:
                logger.debug(f"恢复侧边栏可见性: {visible}")
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
                logger.debug(f"恢复侧边栏浮动状态: {floating}")
                self.sidebar_dock.setFloating(floating)
            except Exception as e:
                logger.error(f"恢复侧边栏浮动状态时出错: {e}")
    
    def _restore_splitter_sizes(self, sizes):
        """恢复分割器大小
        
        Args:
            sizes: 分割器大小列表
        """
        if hasattr(self, 'sidebar_splitter') and sizes:
            try:
                logger.debug(f"恢复分割器大小: {sizes}")
                self.sidebar_splitter.setSizes(sizes)
                
                # 验证恢复是否成功
                actual_sizes = self.sidebar_splitter.sizes()
                if actual_sizes != sizes:
                    logger.warning(f"分割器大小恢复失败: 期望 {sizes}, 实际 {actual_sizes}")
                else:
                    logger.debug("分割器大小恢复成功")
            except Exception as e:
                logger.error(f"恢复分割器大小时出错: {e}") 