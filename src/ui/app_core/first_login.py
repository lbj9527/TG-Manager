"""
TG-Manager 首次登录处理模块
负责首次登录时的用户引导和界面交互
"""

from PySide6.QtCore import QTimer, QMetaObject, Qt
from PySide6.QtWidgets import QMessageBox
from loguru import logger

from src.utils.translation_manager import get_translation_manager, tr


class FirstLoginHandler:
    """首次登录处理类"""
    
    def __init__(self, app=None):
        """初始化首次登录处理类
        
        Args:
            app: TGManagerApp实例
        """
        self.app = app
    
    def check_first_login(self, session_name):
        """检查是否为首次登录
        
        Args:
            session_name: 会话名称
            
        Returns:
            bool: 是否为首次登录
        """
        import os
        session_path = f"sessions/{session_name}.session"
        is_first_login = not os.path.exists(session_path)
        
        if is_first_login:
            logger.info(f"检测到首次登录，会话文件不存在: {session_path}")
        
        return is_first_login
        
    def open_settings_for_first_login(self):
        """为首次登录打开设置界面并显示指导信息"""
        logger.info("执行首次登录引导流程")
        
        try:
            if not self.app or not hasattr(self.app, 'main_window'):
                logger.warning("应用程序没有主窗口实例，无法打开设置界面")
                return
                
            # 使用Qt的线程安全方式调用打开设置界面
            QMetaObject.invokeMethod(self.app.main_window, "_open_settings", Qt.ConnectionType.QueuedConnection)
            logger.debug("已安排在主线程中打开设置界面")
            
            # 使用延迟显示首次登录提示对话框，确保设置界面已显示
            QTimer.singleShot(1500, self._show_first_login_dialog)
        except Exception as e:
            logger.error(f"打开首次登录设置界面时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _show_first_login_dialog(self):
        """显示首次登录提示对话框"""
        try:
            if not self.app or not hasattr(self.app, 'main_window'):
                return
                
            logger.info("显示首次登录提示对话框")
            
            QMessageBox.information(
                self.app.main_window,
                tr("ui.login.first_time.title"),
                tr("ui.login.first_time.message"),
                QMessageBox.Ok
            )
        except Exception as e:
            logger.error(f"显示首次登录对话框时出错: {e}")
            import traceback
            logger.error(traceback.format_exc()) 