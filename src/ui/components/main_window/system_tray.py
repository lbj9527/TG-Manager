"""
TG-Manager 主窗口系统托盘模块
包含系统托盘图标和菜单的创建和管理
"""

from loguru import logger
from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction

class SystemTrayMixin:
    """系统托盘功能混入类
    
    为MainWindow提供系统托盘相关功能
    """
    
    def _create_system_tray(self):
        """创建系统托盘图标和菜单"""
        # 检查系统是否支持系统托盘
        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning("系统不支持系统托盘功能")
            return
            
        # 创建系统托盘图标
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self._get_icon("app"))
        self.tray_icon.setToolTip("TG-Manager")
        
        # 创建系统托盘菜单
        tray_menu = QMenu()
        
        # 添加恢复窗口操作
        restore_action = QAction("显示主窗口", self)
        restore_action.triggered.connect(self.showNormal)
        tray_menu.addAction(restore_action)
        
        # 添加分隔线
        tray_menu.addSeparator()
        
        # 添加退出操作
        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.close)
        tray_menu.addAction(exit_action)
        
        # 设置托盘菜单
        self.tray_icon.setContextMenu(tray_menu)
        
        # 连接托盘图标的激活信号（双击托盘图标时触发）
        self.tray_icon.activated.connect(self._on_tray_icon_activated)
        
        # 托盘图标初始状态为隐藏
        self.tray_icon.hide()
        
        logger.info("系统托盘图标已创建")
    
    def _on_tray_icon_activated(self, reason):
        """处理托盘图标激活事件
        
        Args:
            reason: 激活原因
        """
        # 双击或点击托盘图标时恢复窗口
        if reason == QSystemTrayIcon.DoubleClick or reason == QSystemTrayIcon.Trigger:
            self.showNormal()
            self.activateWindow()  # 激活窗口，使其获得焦点
    
    def changeEvent(self, event):
        """处理窗口状态变化事件
        
        Args:
            event: 状态变化事件
        """
        # 调用父类处理
        super().changeEvent(event)
        
        # 处理窗口最小化事件
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.WindowStateChange:
            # 检查窗口是否被最小化
            if self.windowState() & Qt.WindowMinimized:
                logger.debug("窗口被最小化")
                
                # 检查是否启用了最小化到托盘功能
                minimize_to_tray = False
                if isinstance(self.config, dict) and 'UI' in self.config:
                    ui_config = self.config.get('UI', {})
                    if isinstance(ui_config, dict):
                        minimize_to_tray = ui_config.get('minimize_to_tray', False)
                
                # 如果启用了最小化到托盘，则隐藏窗口并显示托盘图标
                if minimize_to_tray and hasattr(self, 'tray_icon'):
                    logger.info("启用了最小化到托盘，隐藏窗口并显示托盘图标")
                    event.accept()
                    self.hide()
                    self.tray_icon.show()
                    
                    # 显示托盘提示
                    self.tray_icon.showMessage(
                        "TG-Manager 已最小化到托盘",
                        "应用程序在后台运行中。点击托盘图标以恢复窗口。",
                        QSystemTrayIcon.Information,
                        2000
                    ) 