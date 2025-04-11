"""
TG-Manager 主窗口状态管理模块
包含窗口几何形状、布局、状态的保存和恢复功能
"""

from loguru import logger
from PySide6.QtCore import QByteArray, QTimer

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
        
        # 确保所有窗口元素正确显示
        self.update()
    
    def _save_window_state(self, state_data):
        """保存窗口状态
        
        Args:
            state_data: 窗口状态数据
        """
        try:
            ui_config = self.config.get('UI', {})
            
            # 更新窗口状态数据
            if 'geometry' in state_data:
                ui_config['window_geometry'] = state_data['geometry'].toBase64().data().decode()
                logger.debug("保存了窗口几何形状")
            
            if 'state' in state_data:
                ui_config['window_state'] = state_data['state'].toBase64().data().decode()
                logger.debug("保存了窗口状态，包括工具栏位置")
            
            # 更新配置
            self.config['UI'] = ui_config
            
            # 发送配置保存信号，传递完整配置字典
            self.config_saved.emit(self.config)
            
            logger.debug("窗口状态已成功保存到配置")
        except Exception as e:
            logger.error(f"保存窗口状态失败: {e}")
    
    def _save_current_state(self):
        """保存当前窗口状态（只保存窗口几何信息和工具栏位置等布局状态）
        
        注意：此方法只会保存窗口的布局相关配置，不会影响其他配置项如主题设置等。
        这些布局状态没有单独的保存按钮，因此会自动保存，以便在下次启动时恢复布局。
        """
        window_state = {
            'geometry': self.saveGeometry(),
            'state': self.saveState()
        }
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
        if hasattr(self, 'sidebar_splitter'):
            # 获取当前窗口高度
            current_height = self.height()
            
            # 获取当前分割器尺寸
            current_sizes = self.sidebar_splitter.sizes()
            nav_height = current_sizes[0]  # 导航树当前高度
            
            # 只有当窗口高度大于阈值时才调整，防止在极小的窗口尺寸下产生问题
            if current_height > 400:
                # 调整为50%导航树，50%任务概览
                self.sidebar_splitter.setSizes([int(current_height * 0.5), int(current_height * 0.5)])
        
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
                # 稍微延迟保存，以确保工具栏状态已完全更新
                QTimer.singleShot(300, self._save_current_state)
            # 捕获移动事件结束
            elif event.type() == QEvent.Move:
                logger.debug("检测到工具栏移动事件")
                QTimer.singleShot(300, self._save_current_state)
            
        # 继续正常事件处理
        return super().eventFilter(obj, event) 