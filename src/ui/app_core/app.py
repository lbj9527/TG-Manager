"""
TG-Manager 主应用程序
负责初始化应用程序、加载配置和管理主界面
此模块整合了从app.py拆分出的各个功能模块
"""

import sys
import os
import asyncio
import signal
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon
from PySide6.QtCore import QObject, Signal, QSettings, QTimer, QMetaObject, Qt
from loguru import logger

from src.utils.logger import get_logger
from src.utils.theme_manager import get_theme_manager
from src.utils.ui_config_manager import UIConfigManager
from src.utils.ui_config_models import UIConfig, create_default_config
from src.utils.async_utils import create_task, safe_sleep, AsyncTaskManager, init_qasync_loop, get_event_loop

# 导入拆分出的各个功能模块
from src.ui.app_core.config import ConfigManager
from src.ui.app_core.theme import ThemeManagerWrapper
from src.ui.app_core.client import ClientHandler
from src.ui.app_core.first_login import FirstLoginHandler
from src.ui.app_core.async_services import AsyncServicesInitializer
from src.ui.app_core.cleanup import CleanupManager

# 导入主窗口
from src.ui.views.main_window import MainWindow

logger = get_logger()


class TGManagerApp(QObject):
    """TG-Manager 应用程序主类"""
    
    # 信号定义
    config_loaded = Signal(dict)
    config_saved = Signal()
    app_closing = Signal()
    theme_changed = Signal(str)  # 主题变更信号
    
    def __init__(self, verbose=False):
        super().__init__()
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("TG-Manager")
        self.app.setOrganizationName("TG-Manager")
        self.app.setOrganizationDomain("tg-manager.org")
        self.verbose = verbose
        
        # 添加首次登录标志
        self.is_first_login = False
        
        # 添加初始化状态标志
        self.is_initializing = True
        
        if self.verbose:
            logger.debug("初始化应用程序，应用样式...")
        
        # 初始化主题管理器
        self.theme_manager = get_theme_manager()
        self.theme_manager.initialize(self.app)
        
        # 初始化主题管理器包装类
        self.theme_manager_wrapper = ThemeManagerWrapper(self.theme_manager)
        
        # 初始化配置
        self.config = {}
        
        # 初始化UI配置管理器
        try:
            # 检查配置文件是否存在
            config_path = "config.json"
            if os.path.exists(config_path) and not os.access(config_path, os.W_OK):
                logger.warning(f"配置文件 {config_path} 存在但不可写")
                # 将在main_window初始化后显示错误
            
            self.ui_config_manager = UIConfigManager(config_path)
            logger.info("UI配置管理器初始化成功")
        except Exception as e:
            logger.error(f"UI配置管理器初始化失败: {e}")
            # 提供更友好的错误消息
            import traceback
            logger.debug(f"UI配置管理器初始化错误详情:\n{traceback.format_exc()}")
            # 使用默认空配置
            self.ui_config_manager = UIConfigManager()
            self.ui_config_manager.ui_config = create_default_config()
            logger.info("已创建默认UI配置")
        
        # 初始化配置管理器
        self.config_manager = ConfigManager(self.ui_config_manager)
        
        # 初始化客户端处理器
        self.client_handler = ClientHandler(self)
        
        # 初始化首次登录处理器
        self.first_login_handler = FirstLoginHandler(self)
        
        # 初始化异步服务初始化器
        self.async_services_initializer = AsyncServicesInitializer(self)
        
        # 初始化清理管理器
        self.cleanup_manager = CleanupManager(self)
        
        # 初始化qasync事件循环
        try:
            self.event_loop = init_qasync_loop()
            logger.info("qasync事件循环初始化成功")
        except Exception as e:
            logger.error(f"qasync事件循环初始化失败: {e}")
            # 如果qasync初始化失败，退回到标准asyncio
            self.event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.event_loop)
            logger.info("已退回到标准asyncio事件循环")
        
        # 加载配置
        try:
            self.config_manager.load_config()
            # 将配置管理器的配置引用到app
            self.config = self.config_manager.config
            logger.info("已成功加载配置")
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            # 提供更详细的错误跟踪
            import traceback
            logger.debug(f"加载配置错误详情:\n{traceback.format_exc()}")
            # 使用默认空配置
            self.config = {
                'GENERAL': {
                    'api_id': 12345678,  # 占位符
                    'api_hash': '0123456789abcdef0123456789abcdef',  # 占位符
                    'proxy_enabled': False,
                    'auto_restart_session': True,  # 默认启用自动重连
                },
                'DOWNLOAD': {},
                'UPLOAD': {},
                'FORWARD': {},
                'MONITOR': {},
                'UI': {
                    'theme': '深色主题',
                    'confirm_exit': True,
                    'minimize_to_tray': True,
                    'start_minimized': False,
                    'enable_notifications': True,
                    'notification_sound': True
                }
            }
            logger.info("已使用默认配置")
        
        # 应用主题
        try:
            self.theme_manager_wrapper.apply_theme_from_config(self.config)
        except Exception as e:
            logger.error(f"应用主题失败: {e}")
            # 使用默认主题
            self.theme_manager.apply_theme("深色主题")
        
        # 初始化任务管理器
        self.task_manager = AsyncTaskManager()
        
        # 实例化功能模块变量
        self.client = None
        self.client_manager = None
        self.channel_resolver = None
        self.history_manager = None
        self.downloader = None
        self.downloader_serial = None
        self.uploader = None
        self.forwarder = None
        self.monitor = None
        
        # 初始化主窗口
        try:
            self.main_window = MainWindow(self.config, self)
            self.main_window.config_saved.connect(self._on_config_saved)
            
            # 设置初始化状态
            self.main_window.set_initialization_state(True)
            
            # 将窗口居中显示在屏幕上
            screen = self.app.primaryScreen()
            screen_geometry = screen.availableGeometry()
            window_geometry = self.main_window.frameGeometry()
            center_point = screen_geometry.center()
            window_geometry.moveCenter(center_point)
            self.main_window.move(window_geometry.topLeft())
            
            # 检查是否启用了"启动时最小化"功能
            start_minimized = False
            if 'UI' in self.config and isinstance(self.config['UI'], dict):
                start_minimized = self.config['UI'].get('start_minimized', False)
            
            # 如果启用了系统托盘和启动时最小化功能
            if start_minimized and 'UI' in self.config and self.config['UI'].get('minimize_to_tray', False):
                logger.info("启用了启动时最小化功能，应用程序将最小化到系统托盘")
                # 先确保系统托盘可用
                if hasattr(self.main_window, '_create_system_tray'):
                    # 确保系统托盘已创建
                    if not hasattr(self.main_window, 'tray_icon'):
                        self.main_window._create_system_tray()
                    
                    # 显示托盘图标，但不显示主窗口
                    if hasattr(self.main_window, 'tray_icon'):
                        self.main_window.tray_icon.show()
                        # 显示通知
                        self.main_window.tray_icon.showMessage(
                            "TG-Manager 已启动",
                            "应用程序在后台运行中。点击托盘图标以显示窗口。",
                            QSystemTrayIcon.Information,
                            2000
                        )
                    else:
                        # 如果托盘创建失败，仍然显示窗口
                        logger.warning("系统托盘创建失败，将显示主窗口")
                        self.main_window.show()
                else:
                    # 如果没有实现托盘功能，仍然显示窗口
                    logger.warning("系统托盘功能不可用，将显示主窗口")
                    self.main_window.show()
            else:
                # 正常显示窗口
                self.main_window.show()
            
            # 初始化完成后检查配置文件是否可写
            if os.path.exists(config_path) and not os.access(config_path, os.W_OK):
                # 主窗口已创建，显示权限错误对话框
                self.config_manager._show_permission_error_and_exit(self.main_window)
                
        except Exception as e:
            logger.error(f"初始化主窗口失败: {e}")
            # 显示错误对话框
            error_box = QMessageBox()
            error_box.setIcon(QMessageBox.Critical)
            error_box.setWindowTitle("初始化错误")
            error_box.setText("应用程序初始化失败，请检查配置文件")
            error_box.setDetailedText(f"错误详情: {e}")
            error_box.exec()
            # 退出应用
            sys.exit(1)
        
        # 设置清理处理器
        self.cleanup_manager.setup_cleanup_handlers()
        
        # 启动时清理临时目录
        self._cleanup_temp_directories_on_startup()
        
        # 连接信号
        self._connect_signals()
    
    def _cleanup_temp_directories_on_startup(self):
        """启动时清理临时目录"""
        try:
            import shutil
            from pathlib import Path
            
            logger.info("程序启动，开始清理临时目录...")
            
            # 定义需要清理的临时目录列表
            temp_dirs = [
                "tmp",                      # 通用临时目录
                "temp",                     # 临时处理目录
                Path("tmp") / "downloads",  # 临时下载目录
                Path("tmp") / "uploads",    # 临时上传目录
                Path("temp") / "restricted_forward",  # 禁止转发内容处理临时目录
            ]
            
            cleaned_count = 0
            total_size_cleaned = 0
            
            for temp_dir in temp_dirs:
                temp_path = Path(temp_dir)
                
                if temp_path.exists() and temp_path.is_dir():
                    try:
                        # 计算目录大小（用于日志记录）
                        dir_size = self._calculate_directory_size(temp_path)
                        
                        # 清理目录内容，但保留目录本身
                        for item in temp_path.iterdir():
                            if item.is_file():
                                item.unlink()
                                logger.debug(f"已删除临时文件: {item}")
                            elif item.is_dir():
                                shutil.rmtree(item)
                                logger.debug(f"已删除临时目录: {item}")
                        
                        if dir_size > 0:
                            cleaned_count += 1
                            total_size_cleaned += dir_size
                            logger.info(f"已清理临时目录: {temp_path} (释放 {dir_size / 1024 / 1024:.2f} MB)")
                        
                    except Exception as e:
                        logger.warning(f"清理临时目录 {temp_path} 时出错: {e}")
                        continue
            
            if cleaned_count > 0:
                logger.info(f"启动清理完成，共清理 {cleaned_count} 个目录，释放 {total_size_cleaned / 1024 / 1024:.2f} MB 空间")
            else:
                logger.debug("启动清理完成，没有找到需要清理的临时文件")
                
        except Exception as e:
            logger.error(f"启动时清理临时目录失败: {e}")
            import traceback
            logger.debug(f"启动清理错误详情:\n{traceback.format_exc()}")
    
    def _calculate_directory_size(self, directory_path: Path) -> int:
        """计算目录总大小（字节）
        
        Args:
            directory_path: 目录路径
            
        Returns:
            int: 目录总大小（字节）
        """
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(directory_path):
                for filename in filenames:
                    file_path = os.path.join(dirpath, filename)
                    # 跳过符号链接避免重复计算
                    if not os.path.islink(file_path):
                        try:
                            total_size += os.path.getsize(file_path)
                        except OSError:
                            # 文件可能在计算过程中被删除
                            pass
        except Exception as e:
            logger.debug(f"计算目录大小时出错: {e}")
        
        return total_size
    
    def _connect_signals(self):
        """连接各种信号"""
        # 连接主题变更信号
        self.theme_changed.connect(
            lambda theme_name: self.theme_manager_wrapper.on_theme_changed(theme_name, self.config))
        
        # 从theme_manager_wrapper的信号连接到app的信号
        self.theme_manager_wrapper.theme_changed.connect(self.theme_changed)
        
        # 连接配置管理器的信号
        self.config_manager.config_saved.connect(self.config_saved)
    
    async def async_run(self):
        """异步运行应用程序"""
        try:
            # 设置主窗口初始化状态，禁用界面
            if hasattr(self, 'main_window'):
                self.main_window.set_initialization_state(True)
            
            # 初始化异步服务
            await self.async_services_initializer.init_async_services(self.first_login_handler)
            
            # 将功能模块传递给可能已加载的视图组件
            self.async_services_initializer.initialize_views()
            
            # 更新初始化状态
            self.is_initializing = False
            
            # 更新主窗口初始化状态，启用界面
            if hasattr(self, 'main_window'):
                self.main_window.set_initialization_state(False)
                logger.info("初始化完成，界面已启用")
            
            # 启动全局异常处理器
            self.task_manager.add_task("global_exception_handler", 
                                      self.async_services_initializer.global_exception_handler())
            
            # 如果是首次登录，在初始化完成后自动打开设置界面
            if self.is_first_login:
                # 使用计时器延迟执行，确保主窗口已完全初始化
                logger.info("检测到首次登录，将自动打开设置界面引导用户登录")
                QTimer.singleShot(1000, self.first_login_handler.open_settings_for_first_login)
            
            # 不需要在这里执行Qt事件循环，qasync会处理
            # 只需要保持协程运行
            while True:
                await safe_sleep(0.5)  # 保持协程运行
        except Exception as e:
            logger.error(f"异步运行出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return 1
    
    def run(self):
        """运行应用程序"""
        logger.info("开始运行应用程序")
        
        # 使用Qt的原生事件循环
        return self.app.exec()
    
    # 以下是兼容原始app.py的方法
    
    def _on_config_saved(self, updated_config=None):
        """处理配置保存信号"""
        self.config_manager.on_config_saved(
            updated_config=updated_config, 
            main_window=self.main_window,
            theme_manager=self.theme_manager_wrapper
        )
    
    def _on_client_connection_status_changed(self, connected, user_obj):
        """处理客户端连接状态变化信号的兼容方法"""
        self.client_handler.on_client_connection_status_changed(connected, user_obj, self.main_window)
    
    async def check_connection_status_now(self):
        """立即检查网络连接状态的兼容方法"""
        return await self.client_handler.check_connection_status_now()
        
    def save_config(self, save_theme=True):
        """保存配置的兼容方法"""
        return self.config_manager.save_config(save_theme)
        
    def update_config(self, section, key, value):
        """更新配置项的兼容方法"""
        return self.config_manager.update_config(section, key, value)
        
    def get_config(self, section=None, key=None):
        """获取配置项的兼容方法"""
        return self.config_manager.get_config(section, key)
        
    def _initialize_views(self):
        """初始化视图组件的兼容方法"""
        return self.async_services_initializer.initialize_views()
        
    async def cleanup(self):
        """清理资源的兼容方法"""
        return await self.cleanup_manager.cleanup()
        

def main():
    """应用程序入口函数"""
    app = TGManagerApp()
    sys.exit(app.run())


if __name__ == "__main__":
    main() 