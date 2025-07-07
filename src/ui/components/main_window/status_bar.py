"""
TG-Manager 主窗口状态栏模块
包含主窗口的状态栏创建和状态信息更新功能
"""

from loguru import logger
import psutil
from PySide6.QtWidgets import QLabel, QStatusBar
from PySide6.QtCore import QTimer
from src.utils.translation_manager import tr, get_translation_manager

class StatusBarMixin:
    """状态栏功能混入类
    
    为MainWindow提供状态栏相关功能
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._client_connected = False
        self._client_info = None
        
    def _create_status_bar(self):
        """创建状态栏"""
        # 获取状态栏对象
        status_bar = self.statusBar()
        
        # 监听语言切换信号
        self.translation_manager = get_translation_manager()
        self.translation_manager.language_changed.connect(self._update_translations)
        
        # 创建状态栏各部分组件
        # 1. 功能提示区域 - 使用默认的临时消息区域
        status_bar.showMessage(tr("ui.status_bar.ready"))
        
        # 2. 客户端状态
        self.client_status_label = QLabel()
        self.client_status_label.setMinimumWidth(150)
        self.client_status_label.setStyleSheet("padding: 0 8px; color: #757575;")
        self.statusBar().addPermanentWidget(self.client_status_label)
        
        # 3. CPU/内存使用率
        self.resource_usage_label = QLabel()
        self.resource_usage_label.setMinimumWidth(200)
        self.resource_usage_label.setStyleSheet("padding: 0 8px; color: #4CAF50;")
        self.statusBar().addPermanentWidget(self.resource_usage_label)
        
        # 设置定时器，定期更新资源使用率
        self.resource_timer = QTimer(self)
        self.resource_timer.timeout.connect(self._update_resource_usage)
        self.resource_timer.start(5000)  # 每5秒更新一次
        
        # 立即更新一次状态
        self._update_resource_usage()
        self._update_translations()
        
        logger.debug("状态栏创建完成")
    
    def _toggle_statusbar(self, checked):
        """切换状态栏的可见性
        
        Args:
            checked: 是否显示
        """
        self.statusBar().setVisible(checked)
    
    def _update_resource_usage(self):
        """更新资源使用情况"""
        try:
            # 使用psutil库获取系统资源使用情况，不使用阻塞的interval参数
            cpu_usage = round(psutil.cpu_percent(interval=None), 1)
            
            # 获取内存使用情况
            memory = psutil.virtual_memory()
            memory_usage = round(memory.used / (1024 * 1024), 1)  # 转换为MB
            memory_total = round(memory.total / (1024 * 1024), 1)  # 转换为MB
            memory_percent = round(memory.percent, 1)
            
            # 格式化显示
            if memory_usage > 1024:
                # 如果超过1GB则显示为GB
                memory_text = f"{memory_usage / 1024:.1f}GB/{memory_total / 1024:.1f}GB ({memory_percent}%)"
            else:
                memory_text = f"{memory_usage:.0f}MB/{memory_total / 1024:.1f}GB ({memory_percent}%)"
            
            # 更新资源使用标签
            self.resource_usage_label.setText(tr("ui.status_bar.resource_usage", cpu=cpu_usage, memory=memory_text))
            
            # 根据使用率设置不同的颜色
            if cpu_usage > 90 or memory_percent > 90:
                self.resource_usage_label.setStyleSheet("padding: 0 8px; color: #F44336;")  # 红色
            elif cpu_usage > 70 or memory_percent > 70:
                self.resource_usage_label.setStyleSheet("padding: 0 8px; color: #FF9800;")  # 橙色
            else:
                self.resource_usage_label.setStyleSheet("padding: 0 8px; color: #4CAF50;")  # 绿色
                
        except ImportError:
            # 如果没有psutil库，使用占位符数据
            self.resource_usage_label.setText(tr("ui.status_bar.resource_usage_placeholder"))
            logger.warning("未找到psutil库，无法获取系统资源使用情况")
            
        except Exception as e:
            # 其他错误情况
            self.resource_usage_label.setText(tr("ui.status_bar.resource_error"))
            logger.error(f"资源监控错误: {e}")
    
    def _update_client_status(self, connected=False, client_info=None):
        """更新客户端连接状态
        
        Args:
            connected: 是否已连接
            client_info: 客户端信息，如用户ID、名称等
        """
        # 保存状态
        self._client_connected = connected
        self._client_info = client_info
        try:
            # 确保在UI线程中执行状态更新
            if connected and client_info:
                # 如果已连接且有客户端信息，显示详细信息
                text = tr("ui.status_bar.client_connected_with_info", info=client_info)
                self.client_status_label.setStyleSheet("padding: 0 8px; font-weight: bold; color: #4CAF50;")  # 绿色加粗
            elif connected:
                # 如果已连接但没有详细信息
                text = tr("ui.status_bar.client_connected")
                self.client_status_label.setStyleSheet("padding: 0 8px; font-weight: bold; color: #4CAF50;")  # 绿色加粗
            else:
                # 未连接状态
                text = tr("ui.status_bar.client_disconnected")
                self.client_status_label.setStyleSheet("padding: 0 8px; font-weight: bold; color: #F44336;")  # 红色加粗
            self.client_status_label.setText(text)
            self.client_status_label.repaint()
            logger.debug(f"状态栏客户端状态已更新: {text}")
        except Exception as e:
            logger.error(f"更新客户端状态标签时出错: {e}")
            try:
                self.client_status_label.setText(tr("ui.status_bar.client_status_error"))
                self.client_status_label.setStyleSheet("padding: 0 8px; color: #F44336;")  # 红色
            except:
                pass

    def _update_translations(self):
        """刷新状态栏所有文本的翻译"""
        self.statusBar().showMessage(tr("ui.status_bar.ready"))
        self._update_client_status(self._client_connected, self._client_info)
        self._update_resource_usage() 