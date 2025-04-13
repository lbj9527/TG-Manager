"""
TG-Manager 主应用程序
负责初始化应用程序、加载配置和管理主界面
"""

import sys
import json
import asyncio
import signal
import os
import time
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject, Signal, QSettings, QTimer, QMetaObject, Qt
from PySide6.QtWidgets import QSystemTrayIcon

from src.utils.logger import get_logger
from src.utils.theme_manager import get_theme_manager
from src.utils.ui_config_manager import UIConfigManager
from src.utils.ui_config_models import UIConfig
from src.utils.channel_resolver import ChannelResolver
from src.utils.history_manager import HistoryManager
from src.utils.client_manager import ClientManager
from src.utils.async_utils import create_task, safe_sleep, AsyncTaskManager, init_qasync_loop, get_event_loop

# 导入功能模块
from src.modules.downloader import Downloader
from src.modules.downloader_serial import DownloaderSerial
from src.modules.uploader import Uploader
from src.modules.forwarder import Forwarder
from src.modules.monitor import Monitor

# 导入主窗口
from src.ui.views.main_window import MainWindow


logger = get_logger()


class TGManagerApp(QObject):
    """TG-Manager 应用程序主类"""
    
    # 信号定义
    config_loaded = Signal(dict)
    config_saved = Signal()
    app_closing = Signal()
    theme_changed = Signal(str)  # 新增：主题变更信号
    
    def __init__(self, verbose=False):
        super().__init__()
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("TG-Manager")
        self.app.setOrganizationName("TG-Manager")
        self.app.setOrganizationDomain("tg-manager.org")
        self.verbose = verbose
        
        # 添加首次登录标志
        self.is_first_login = False
        
        # 添加标志，用于跟踪是否已显示权限错误对话框
        self._permission_error_shown = False
        
        if self.verbose:
            logger.debug("初始化应用程序，应用样式...")
        
        # 初始化主题管理器
        self.theme_manager = get_theme_manager()
        self.theme_manager.initialize(self.app)
        
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
            from src.utils.ui_config_models import create_default_config
            self.ui_config_manager = UIConfigManager()
            self.ui_config_manager.ui_config = create_default_config()
            logger.info("已创建默认UI配置")
        
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
            self.load_config()
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
            self._apply_theme_from_config()
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
        self.uploader = None
        self.forwarder = None
        self.monitor = None
        
        # 初始化主窗口
        try:
            self.main_window = MainWindow(self.config, self)
            self.main_window.config_saved.connect(self._on_config_saved)
            
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
                self._show_permission_error_and_exit()
                
        except Exception as e:
            logger.error(f"初始化主窗口失败: {e}")
            # 显示错误对话框
            from PySide6.QtWidgets import QMessageBox
            error_box = QMessageBox()
            error_box.setIcon(QMessageBox.Critical)
            error_box.setWindowTitle("初始化错误")
            error_box.setText("应用程序初始化失败，请检查配置文件")
            error_box.setDetailedText(f"错误详情: {e}")
            error_box.exec()
            # 退出应用
            sys.exit(1)
        
        # 设置退出处理
        self.app.aboutToQuit.connect(self._cleanup_sync)
        signal.signal(signal.SIGINT, lambda sig, frame: self._cleanup_sync())
        
        # 连接主题变更信号
        self.theme_changed.connect(self._on_theme_changed)
    
    async def async_run(self):
        """异步运行应用程序"""
        try:
            # 初始化异步服务
            await self._init_async_services()
            
            # 将功能模块传递给可能已加载的视图组件（注意：视图采用延迟加载，多数视图可能尚未创建）
            self._initialize_views()
            
            # 启动全局异常处理器
            self.task_manager.add_task("global_exception_handler", self.global_exception_handler())
            
            # 如果是首次登录，在初始化完成后自动打开设置界面
            if self.is_first_login and hasattr(self, 'main_window'):
                # 使用计时器延迟执行，确保主窗口已完全初始化
                logger.info("检测到首次登录，将自动打开设置界面引导用户登录")
                QTimer.singleShot(1000, self._open_settings_for_first_login)
            
            # 不需要在这里执行Qt事件循环，qasync会处理
            # 只需要保持协程运行
            while True:
                await safe_sleep(0.5)  # 保持协程运行
        except Exception as e:
            logger.error(f"异步运行出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return 1
    
    async def _init_async_services(self):
        """初始化异步服务"""
        logger.info("正在初始化异步服务...")
        try:
            # 初始化异步任务计划
            if not hasattr(self, 'task_manager') or self.task_manager is None:
                self.task_manager = AsyncTaskManager()
                logger.debug("已创建异步任务管理器")
            
            # 1. 初始化client_manager
            self.client_manager = ClientManager(self.ui_config_manager)
            logger.debug("已初始化客户端管理器")
            
            # 连接客户端状态信号
            if hasattr(self.client_manager, 'connection_status_changed'):
                self.client_manager.connection_status_changed.connect(self._on_client_connection_status_changed)
                logger.debug("已连接客户端状态变化信号")
            
            # 检查会话文件是否存在，判断是否为首次登录
            session_name = self.client_manager.session_name
            session_path = f"sessions/{session_name}.session"
            self.is_first_login = not os.path.exists(session_path)
            
            if self.is_first_login:
                logger.info(f"检测到首次登录，会话文件不存在: {session_path}")
                # 首次登录不自动启动客户端，等待用户点击登录按钮
                
                # 2. 创建channel_resolver (仍然需要创建，但设置client为None)
                self.channel_resolver = ChannelResolver(None)
                logger.info("已创建频道解析器(无客户端)")
                
                # 3. 初始化history_manager
                self.history_manager = HistoryManager()
                logger.info("已创建历史管理器")
                
                # 4-8. 不初始化其他核心组件，等待用户登录后再初始化
                logger.info("首次登录模式，核心组件将在用户登录后初始化")
            else:
                # 非首次登录，正常启动客户端和初始化所有组件
                logger.info("正在启动Telegram客户端...")
                # 用于追踪组件初始化状态
                initialized_components = []
                failed_components = []
                
                try:
                    # 启动客户端
                    logger.info("正在启动客户端...")
                    try:
                        self.client = await self.client_manager.start_client()
                        logger.info("客户端启动成功")
                        initialized_components.append('client')
                    except Exception as client_error:
                        logger.error(f"启动客户端失败: {client_error}")
                        failed_components.append('client')
                        raise  # 如果客户端启动失败，重新抛出异常以中止其他初始化
                    
                    # 标记客户端为活动状态
                    self.client_manager.connection_active = True
                    
                    # 不再在此处启动网络连接检查任务，统一在_on_client_connection_status_changed处理
                    
                    # 如果主窗口已初始化，更新状态栏
                    if hasattr(self, 'main_window') and self.client_manager.me:
                        # 获取用户信息并格式化
                        me = self.client_manager.me
                        user_info = f"{me.first_name}"
                        if me.last_name:
                            user_info += f" {me.last_name}"
                        user_info += f" (@{me.username})" if me.username else ""
                        
                        # 更新主窗口状态栏
                        self.main_window._update_client_status(True, user_info)
                        logger.debug(f"已更新状态栏客户端状态: {user_info}")
                        
                        # 更新设置界面中的登录按钮状态
                        if hasattr(self.main_window, 'opened_views') and 'settings_view' in self.main_window.opened_views:
                            settings_view = self.main_window.opened_views['settings_view']
                            if hasattr(settings_view, 'update_login_button'):
                                settings_view.update_login_button(True, user_info)
                                logger.debug("已更新设置视图中的登录按钮状态")
                
                except Exception as e:
                    logger.error(f"启动Telegram客户端时出错: {e}")
                    # 显示错误但继续运行，允许用户稍后通过登录按钮登录
                    if hasattr(self, 'main_window'):
                        self.main_window._update_client_status(False)
                        # 更新设置界面中的登录按钮状态
                        if hasattr(self.main_window, 'opened_views') and 'settings_view' in self.main_window.opened_views:
                            settings_view = self.main_window.opened_views['settings_view']
                            if hasattr(settings_view, 'update_login_button'):
                                settings_view.update_login_button(False)
                    return  # 如果客户端启动失败，提前返回
                
                # 2. 创建channel_resolver
                logger.info("正在创建频道解析器...")
                try:
                    self.channel_resolver = ChannelResolver(self.client)
                    logger.info("已创建频道解析器")
                    initialized_components.append('channel_resolver')
                except Exception as e:
                    logger.error(f"创建频道解析器时出错: {e}")
                    failed_components.append('channel_resolver')
                
                # 3. 初始化history_manager
                logger.info("正在创建历史管理器...")
                try:
                    self.history_manager = HistoryManager()
                    logger.info("已创建历史管理器")
                    initialized_components.append('history_manager')
                except Exception as e:
                    logger.error(f"创建历史管理器时出错: {e}")
                    failed_components.append('history_manager')
                
                # 4. 初始化下载模块
                logger.info("正在初始化下载模块...")
                try:
                    self.downloader = Downloader(self.client, self.ui_config_manager, self.channel_resolver, self.history_manager)
                    logger.info("已初始化下载模块")
                    initialized_components.append('downloader')
                except Exception as e:
                    logger.error(f"初始化下载模块时出错: {e}")
                    failed_components.append('downloader')
                
                # 5. 初始化串行下载模块
                logger.info("正在初始化串行下载模块...")
                try:
                    self.downloader_serial = DownloaderSerial(self.client, self.ui_config_manager, self.channel_resolver, self.history_manager)
                    logger.info("已初始化串行下载模块")
                    initialized_components.append('downloader_serial')
                except Exception as e:
                    logger.error(f"初始化串行下载模块时出错: {e}")
                    failed_components.append('downloader_serial')
                
                # 6. 初始化上传模块
                logger.info("正在初始化上传模块...")
                try:
                    self.uploader = Uploader(self.client, self.ui_config_manager, self.channel_resolver, self.history_manager, self)
                    logger.info("已初始化上传模块")
                    initialized_components.append('uploader')
                except Exception as e:
                    logger.error(f"初始化上传模块时出错: {e}")
                    failed_components.append('uploader')
                
                # 7. 初始化转发模块
                logger.info("正在初始化转发模块...")
                try:
                    self.forwarder = Forwarder(self.client, self.ui_config_manager, self.channel_resolver, 
                                            self.history_manager, self.downloader, self.uploader, self)
                    logger.info("已初始化转发模块")
                    initialized_components.append('forwarder')
                except Exception as e:
                    logger.error(f"初始化转发模块时出错: {e}")
                    failed_components.append('forwarder')
                
                # 8. 初始化监听模块
                logger.info("正在初始化监听模块...")
                try:
                    self.monitor = Monitor(self.client, self.ui_config_manager, self.channel_resolver, 
                                         self.history_manager, self)
                    logger.info("已初始化监听模块")
                    initialized_components.append('monitor')
                except Exception as e:
                    logger.error(f"初始化监听模块时出错: {e}")
                    failed_components.append('monitor')
                
                # 检查必需组件是否全部初始化
                required_components = ['client', 'channel_resolver', 'history_manager', 
                                    'downloader', 'downloader_serial',
                                    'uploader', 'forwarder', 'monitor']
                
                missing_components = [comp for comp in required_components 
                                    if comp not in initialized_components]
                
                if missing_components:
                    logger.warning(f"以下必需组件未初始化: {', '.join(missing_components)}")
                
                if failed_components:
                    logger.error(f"以下组件初始化失败: {', '.join(failed_components)}")
                    
                # 组件初始化总结
                logger.info(f"非首次登录组件初始化总结: 成功={len(initialized_components)}, 失败={len(failed_components)}, 缺失={len(missing_components)}")
                logger.info(f"已初始化的组件: {', '.join(initialized_components)}")
            
            logger.info("异步服务初始化完成")
        except Exception as e:
            logger.error(f"初始化异步服务时出错: {e}")
            import traceback
            logger.error(f"错误详情:\n{traceback.format_exc()}")
            raise  # 重新抛出异常以便上层处理
    
    def _initialize_views(self):
        """初始化所有视图组件，传递功能模块实例
        
        注意：视图采用延迟加载方式，只有在用户点击相应导航项时才会创建
        此方法只是将功能模块实例传递到已存在的视图中，不检查视图是否已加载
        """
        if not hasattr(self, 'main_window'):
            logger.warning("主窗口未初始化，无法设置视图组件")
            return
        
        # 获取视图引用并设置功能模块
        try:
            # 下载视图
            download_view = self.main_window.get_view("download")
            if download_view and hasattr(self, 'downloader'):
                download_view.set_downloader(self.downloader)
                logger.info("下载视图已设置下载器实例")
            
            # 上传视图
            upload_view = self.main_window.get_view("upload")
            if upload_view and hasattr(self, 'uploader'):
                upload_view.set_uploader(self.uploader)
                logger.info("上传视图已设置上传器实例")
            
            # 转发视图
            forward_view = self.main_window.get_view("forward")
            if forward_view and hasattr(self, 'forwarder'):
                forward_view.set_forwarder(self.forwarder)
                logger.info("转发视图已设置转发器实例")
            
            # 监听视图
            listen_view = self.main_window.get_view("listen")
            if listen_view and hasattr(self, 'monitor'):
                listen_view.set_monitor(self.monitor)
                logger.info("监听视图已设置监听器实例")
            
            # 任务视图 - 将任务管理器传递给任务视图
            task_view = self.main_window.get_view("task")
            if task_view and hasattr(self, 'task_manager'):
                task_view.set_task_manager(self.task_manager)
                logger.info("任务视图已设置任务管理器实例")
            
            logger.info("视图组件初始化设置完成（视图将在用户点击时加载）")
        except Exception as e:
            logger.error(f"初始化视图组件时出错: {e}")
            import traceback
            logger.error(f"错误详情:\n{traceback.format_exc()}")
    
    async def global_exception_handler(self):
        """全局异常处理函数"""
        while True:
            try:
                for task in asyncio.all_tasks():
                    if task.done() and not task.cancelled():
                        try:
                            # 尝试获取异常
                            exc = task.exception()
                            if exc:
                                logger.warning(f"发现未捕获的异常: {type(exc).__name__}: {exc}, 任务名称: {task.get_name()}")
                        except (asyncio.CancelledError, asyncio.InvalidStateError):
                            pass  # 忽略已取消的任务和无效状态
                await safe_sleep(5)  # 每5秒检查一次
            except asyncio.CancelledError:
                logger.info("全局异常处理器已取消")
                break
            except Exception as e:
                logger.error(f"全局异常处理器出错: {e}")
                await safe_sleep(5)  # 出错后等待5秒再继续

    def _apply_theme_from_config(self):
        """从配置中应用主题设置"""
        if not self.config:
            return
        
        ui_config = self.config.get('UI', {})
        
        # 获取主题名称
        theme_name = ui_config.get('theme', '深色主题')
        logger.debug(f"从配置中加载主题: {theme_name}")
        
        # 应用主题
        theme_manager = self.theme_manager
        if theme_manager.apply_theme(theme_name):
            logger.debug(f"成功应用主题 '{theme_name}'")
        else:
            logger.warning(f"应用主题 '{theme_name}' 失败")
    
    def load_config(self):
        """读取配置文件"""
        try:
            # 从UI配置管理器获取配置
            ui_config = self.ui_config_manager.get_ui_config()
            
            # 转换为字典以供界面使用
            self.config = {
                'GENERAL': ui_config.GENERAL.dict(),
                'DOWNLOAD': ui_config.DOWNLOAD.dict(),
                'UPLOAD': ui_config.UPLOAD.dict(),
                'FORWARD': ui_config.FORWARD.dict(),
                'MONITOR': ui_config.MONITOR.dict(),
                'UI': ui_config.UI.dict(),  # 添加UI配置，从Pydantic模型获取
            }
            
            # 处理下载配置中的嵌套对象
            try:
                download_settings = []
                for item in ui_config.DOWNLOAD.downloadSetting:
                    item_dict = item.dict()
                    # 将MediaType枚举转换为字符串值
                    if 'media_types' in item_dict:
                        item_dict['media_types'] = [mt.value for mt in item.media_types]
                    download_settings.append(item_dict)
                self.config["DOWNLOAD"]["downloadSetting"] = download_settings
            except Exception as e:
                logger.error(f"处理下载配置时出错: {e}")
                # 使用默认下载设置
                self.config["DOWNLOAD"]["downloadSetting"] = []
            
            # 处理转发配置中的嵌套对象
            try:
                forward_pairs = []
                for pair in ui_config.FORWARD.forward_channel_pairs:
                    forward_pairs.append(pair.dict())
                self.config["FORWARD"]["forward_channel_pairs"] = forward_pairs
            except Exception as e:
                logger.error(f"处理转发配置时出错: {e}")
                # 使用默认转发设置
                self.config["FORWARD"]["forward_channel_pairs"] = []
            
            # 处理监听配置中的嵌套对象
            try:
                monitor_pairs = []
                for pair in ui_config.MONITOR.monitor_channel_pairs:
                    pair_dict = pair.dict()
                    # 处理文本过滤器
                    text_filters = []
                    for filter_item in pair.text_filter:
                        text_filters.append(filter_item.dict())
                    pair_dict["text_filter"] = text_filters
                    monitor_pairs.append(pair_dict)
                self.config["MONITOR"]["monitor_channel_pairs"] = monitor_pairs
            except Exception as e:
                logger.error(f"处理监听配置时出错: {e}")
                # 使用默认监听设置
                self.config["MONITOR"]["monitor_channel_pairs"] = []
            
            logger.info("已加载配置文件")
            
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            import traceback
            logger.debug(f"加载配置错误详情:\n{traceback.format_exc()}")
            
            # 使用默认配置
            default_config = self.ui_config_manager.ui_config.dict()
            self.config = {
                'GENERAL': default_config.get('GENERAL', {}),
                'DOWNLOAD': default_config.get('DOWNLOAD', {}),
                'UPLOAD': default_config.get('UPLOAD', {}),
                'FORWARD': default_config.get('FORWARD', {}),
                'MONITOR': default_config.get('MONITOR', {}),
                'UI': default_config.get('UI', {})
            }
            logger.info("已使用默认配置")
    
    def save_config(self, save_theme=True):
        """
        保存应用程序配置到文件
        
        Args:
            save_theme: 是否保存主题设置，默认为True
            
        Returns:
            dict: 保存的配置，如果保存失败则返回空字典
            
        Raises:
            PermissionError: 当没有权限写入配置文件时抛出
        """
        try:
            # 如果不保存主题设置，临时保存当前主题
            current_theme = None
            if not save_theme and 'UI' in self.config and 'theme' in self.config['UI']:
                current_theme = self.config['UI']['theme']
                logger.debug(f"临时保存当前主题: {current_theme}")
            
            # 使用UI配置管理器更新并保存配置
            self.ui_config_manager.update_from_dict(self.config)
            try:
                save_success = self.ui_config_manager.save_config()
            except PermissionError:
                # 权限错误直接向上传递
                logger.warning(f"save_config: 保存配置时遇到权限问题，将错误向上传递")
                raise
            
            # 如果不保存主题设置，恢复原来的主题
            if not save_theme and current_theme and save_success:
                try:
                    # 尝试从文件重新读取配置并修改主题
                    with open(self.ui_config_manager.config_path, 'r', encoding='utf-8') as f:
                        file_config = json.load(f)
                        if 'UI' in file_config:
                            file_config['UI']['theme'] = current_theme
                            logger.debug(f"恢复配置文件中的主题: {current_theme}")
                            
                            # 重新保存文件
                            with open(self.ui_config_manager.config_path, 'w', encoding='utf-8') as f:
                                json.dump(file_config, f, ensure_ascii=False, indent=2)
                except PermissionError:
                    # 恢复主题时的权限错误同样向上传递
                    logger.warning(f"恢复主题时遇到权限问题，将错误向上传递")
                    raise
                except Exception as e:
                    # 恢复主题的其他错误则只记录日志，不影响返回结果
                    logger.error(f"恢复主题时出错: {e}")
            
            if save_success:
                if save_theme:
                    current_theme = self.config.get('UI', {}).get('theme', "深色主题")
                    logger.info(f"已保存配置文件，主题: {current_theme}")
                else:
                    logger.info("已保存配置文件（不包含主题设置）")
                return self.config
            else:
                logger.error("保存配置文件失败")
                return {}
        except PermissionError:
            # 权限错误直接向上传递，让调用者处理
            logger.warning("在save_config中捕获到权限错误，重新抛出")
            raise
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            import traceback
            logger.debug(f"保存配置错误详情:\n{traceback.format_exc()}")
            return {}
    
    def update_config(self, section, key, value):
        """更新配置项
        
        Args:
            section: 配置部分名称 (GENERAL, DOWNLOAD 等)
            key: 配置项键名
            value: 配置项值
        """
        if section in self.config:
            self.config[section][key] = value
        else:
            self.config[section] = {key: value}
    
    def get_config(self, section=None, key=None):
        """获取配置项
        
        Args:
            section: 配置部分名称，如果为None则返回整个配置
            key: 配置项键名，如果为None则返回整个部分
            
        Returns:
            请求的配置项值
        """
        if section is None:
            return self.config
        
        if section not in self.config:
            return None
            
        if key is None:
            return self.config[section]
            
        if key in self.config[section]:
            return self.config[section][key]
            
        return None
    
    def run(self):
        """运行应用程序"""
        logger.info("开始运行应用程序")
        
        # 设置信号处理
        if hasattr(signal, 'SIGINT'):
            signal.signal(signal.SIGINT, lambda sig, frame: self._cleanup_sync())
        
        # 使用Qt的原生事件循环
        return self.app.exec()
    
    def _cleanup_sync(self):
        """同步清理入口，用于连接Qt信号"""
        # 记录正在关闭的状态，避免重复调用
        if hasattr(self, '_is_closing') and self._is_closing:
            logger.debug("已经在关闭过程中，忽略重复调用")
            return
            
        self._is_closing = True
        logger.info("开始同步清理过程")
        
        # 发出应用程序关闭信号
        self.app_closing.emit()
        
        # 如果主窗口已创建，发送关闭信号
        if hasattr(self, 'main_window'):
            # 停止资源监控计时器
            if hasattr(self.main_window, "resource_timer") and self.main_window.resource_timer:
                self.main_window.resource_timer.stop()
                logger.debug("资源监控计时器已停止")
            
            # 隐藏系统托盘图标
            if hasattr(self.main_window, 'tray_icon') and self.main_window.tray_icon:
                self.main_window.tray_icon.hide()
                logger.debug("系统托盘图标已隐藏")
        
        # 取消所有定时器和任务
        if hasattr(self, 'task_manager'):
            logger.debug("取消网络连接检查任务")
            self.task_manager.cancel_task("network_connection_check")
            # 取消所有其他任务
            self.task_manager.cancel_all_tasks()
            logger.debug("所有任务已取消")
        
        # 创建异步清理任务
        loop = get_event_loop()
        if loop and loop.is_running():
            try:
                # 使用Qt计时器延迟执行异步清理，避免事件循环冲突
                from PySide6.QtCore import QTimer
                timer = QTimer()
                timer.setSingleShot(True)
                timer.timeout.connect(lambda: self._execute_async_cleanup(loop))
                timer.start(10)  # 10毫秒后执行异步清理
                logger.debug("已安排延迟执行异步清理")
            except Exception as e:
                logger.error(f"创建清理任务时出错: {e}")
                # 如果创建任务失败，尝试直接退出
                self.app.quit()
        else:
            # 如果事件循环不存在或未运行，直接退出应用
            logger.warning("事件循环不可用，直接退出应用")
            self.app.quit()
    
    def _execute_async_cleanup(self, loop):
        """执行异步清理，作为Qt计时器的回调函数"""
        try:
            # 安全创建异步清理任务
            future = asyncio.run_coroutine_threadsafe(self._async_cleanup(), loop)
            logger.debug("已创建异步清理任务")
            
            # 设置回调函数处理完成
            future.add_done_callback(lambda f: self._on_cleanup_done(f))
        except Exception as e:
            logger.error(f"执行异步清理时出错: {e}")
            # 出错时直接退出
            self.app.quit()
    
    def _on_cleanup_done(self, future):
        """异步清理完成后的回调"""
        try:
            # 尝试获取结果，检查是否有异常
            future.result()
            logger.info("异步清理任务已完成")
        except Exception as e:
            logger.error(f"异步清理任务出错: {e}")
        finally:
            # 无论如何，确保应用退出
            self.app.quit()
            logger.info("应用程序已请求退出")
    
    async def _async_cleanup(self):
        """真正的异步清理操作"""
        try:
            # 停止Telegram客户端
            if hasattr(self, 'client_manager') and self.client_manager:
                logger.debug("停止Telegram客户端")
                try:
                    await self.client_manager.stop_client()
                    logger.debug("Telegram客户端已停止")
                except Exception as e:
                    logger.error(f"停止Telegram客户端时出错: {e}")
            
            # 在事件循环中安全地获取和取消任务
            for task in [t for t in asyncio.all_tasks() 
                      if t is not asyncio.current_task() and not t.done()]:
                logger.debug(f"取消任务: {task.get_name()}")
                task.cancel()
            
            logger.info("异步资源清理完成")
            return True
        except Exception as e:
            logger.error(f"异步清理过程出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    async def cleanup(self):
        """原有的异步清理方法，保持向后兼容
        
        注意：此方法已被新的清理流程替代，但保留以维持兼容性
        """
        logger.warning("使用了已弃用的cleanup方法，应该使用_cleanup_sync")
        return await self._async_cleanup()

    def _on_config_saved(self, updated_config=None):
        """处理配置保存信号"""
        try:
            # 如果接收到更新后的配置，先更新内存中的配置
            if isinstance(updated_config, dict):
                logger.debug(f"接收到更新后的配置数据，准备保存")
                
                # 备份当前主题设置（如果有的话）
                current_theme = None
                if 'UI' in self.config and 'theme' in self.config['UI']:
                    current_theme = self.config['UI'].get('theme')
                    logger.debug(f"备份当前主题设置: {current_theme}")
                
                # 更新内存中的配置
                for section, section_data in updated_config.items():
                    self.config[section] = section_data
                
                # 如果更新的配置中没有主题设置但之前有，则恢复
                if current_theme and ('UI' not in updated_config or 'theme' not in updated_config.get('UI', {})):
                    if 'UI' not in self.config:
                        self.config['UI'] = {}
                    logger.debug(f"恢复主题设置: {current_theme}")
                    self.config['UI']['theme'] = current_theme
                
                # 使用UI配置管理器更新和保存
                logger.debug("通过UIConfigManager更新配置")
                try:
                    self.ui_config_manager.update_from_dict(self.config)
                    save_success = self.ui_config_manager.save_config()
                    
                    if save_success:
                        logger.info("配置已通过UIConfigManager成功保存")
                        
                        # 检查主题是否变更
                        ui_config = self.config.get('UI', {})
                        saved_theme = ui_config.get('theme', '')
                        current_theme = self.theme_manager.get_current_theme_name()
                        
                        # 如果主题发生变化，触发主题更改信号
                        if saved_theme and saved_theme != current_theme:
                            logger.info(f"主题发生变化，从 '{current_theme}' 变更为 '{saved_theme}'")
                            self.theme_changed.emit(saved_theme)
                        
                        # 发送配置保存成功信号
                        self.config_saved.emit()
                    else:
                        logger.error("UIConfigManager保存配置失败")
                except PermissionError as pe:
                    logger.warning(f"保存配置时遇到权限问题: {pe}")
                    
                    # 调用显示权限错误并退出的方法，确保程序立即退出
                    self._show_permission_error_and_exit()
                except Exception as e:
                    logger.error(f"通过UIConfigManager更新配置失败: {e}")
                    import traceback
                    logger.debug(f"保存配置错误详情:\n{traceback.format_exc()}")
                    
                    # 回退到原始保存方法
                    try:
                        self.save_config(save_theme=True)
                        self.config_saved.emit()
                    except PermissionError:
                        # 如果原始保存方法也遇到权限问题，显示错误对话框
                        self._show_permission_error_and_exit()
                
                return
            
            # 如果是窗口状态变化，仅保存窗口状态（不保存整个配置）
            if hasattr(self.main_window, 'window_state_changed'):
                # 检查是否在短时间内多次触发保存
                current_time = time.time()
                if hasattr(self, '_last_window_state_save_time'):
                    # 如果上次保存时间距现在不足500毫秒，则跳过本次保存
                    if current_time - self._last_window_state_save_time < 0.5:
                        logger.debug("窗口状态保存请求过于频繁，跳过本次保存")
                        return
                
                # 更新上次保存时间
                self._last_window_state_save_time = current_time
                
                try:
                    # 获取当前窗口状态
                    window_state = {
                        'geometry': self.main_window.saveGeometry(),
                        'state': self.main_window.saveState()
                    }
                    
                    # 更新内存中的窗口状态配置
                    if 'UI' not in self.config:
                        self.config['UI'] = {}
                    
                    # 更新内存中的UI配置
                    self.config['UI']['window_geometry'] = window_state['geometry'].toBase64().data().decode()
                    self.config['UI']['window_state'] = window_state['state'].toBase64().data().decode()
                    
                    # 仅保存窗口布局相关的配置项，不修改其他配置
                    try:
                        # 从文件读取当前配置
                        with open(self.ui_config_manager.config_path, 'r', encoding='utf-8') as f:
                            file_config = json.load(f)
                        
                        # 确保UI部分存在
                        if 'UI' not in file_config:
                            file_config['UI'] = {}
                        
                        # 只更新窗口几何信息和状态
                        file_config['UI']['window_geometry'] = self.config['UI']['window_geometry']
                        file_config['UI']['window_state'] = self.config['UI']['window_state']
                        
                        # 保存回文件
                        with open(self.ui_config_manager.config_path, 'w', encoding='utf-8') as f:
                            json.dump(file_config, f, ensure_ascii=False, indent=2)
                        
                        logger.debug("窗口布局状态已单独保存")
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
                
                return
            
            # 如果是来自设置界面的普通保存请求
            try:
                self.save_config(save_theme=True)
                self.config_saved.emit()
            except PermissionError as pe:
                logger.warning(f"普通保存配置时遇到权限问题: {pe}")
                # 显示错误对话框并立即退出程序
                self._show_permission_error_and_exit()
            
        except Exception as e:
            logger.error(f"处理配置保存信号失败: {e}")
            import traceback
            logger.debug(f"处理配置保存信号错误详情:\n{traceback.format_exc()}")
    
    def _show_permission_error_and_exit(self):
        """显示权限错误对话框并退出程序"""
        # 如果已经显示过错误对话框，则直接返回
        if self._permission_error_shown:
            logger.debug("已经显示过权限错误对话框，不再重复显示")
            return
            
        from PySide6.QtWidgets import QMessageBox
        
        # 设置标志，表示已显示错误对话框
        self._permission_error_shown = True
        
        # 在主窗口中显示权限错误信息
        config_path = os.path.abspath(self.ui_config_manager.config_path)
        error_msg = (
            f"无法写入配置文件 '{config_path}'，因为该文件为只读状态或您没有写入权限。\n\n"
            f"请退出程序，修改文件权限后重新启动。\n\n"
            f"您可以尝试：\n"
            f"1. 右键点击文件 -> 属性 -> 取消勾选'只读'属性\n"
            f"2. 以管理员身份运行程序\n"
            f"3. 将程序移动到有写入权限的目录"
        )
        
        QMessageBox.critical(
            self.main_window,
            "配置文件权限错误",
            error_msg,
            QMessageBox.Ok
        )
        
        # 用户点击确定后，立即关闭程序
        logger.info("因配置文件权限问题，应用程序立即退出")
        # 先执行清理操作
        self.cleanup()
        # 直接退出进程
        sys.exit(1)
    
    def _on_theme_changed(self, theme_name):
        """主题变更处理
        
        Args:
            theme_name: 新主题名称
        """
        # 获取当前主题
        current_theme = self.theme_manager.get_current_theme_name()
        
        # 只有当新主题与当前主题不同时才应用
        if theme_name != current_theme:
            logger.info(f"正在切换主题: 从 {current_theme} 到 {theme_name}")
            
            # 应用主题
            self.theme_manager.apply_theme(theme_name)
            
            # 更新配置中的主题设置
            if 'UI' in self.config:
                self.config['UI']['theme'] = theme_name
            else:
                self.config['UI'] = {'theme': theme_name}
        else:
            logger.debug(f"忽略主题变更请求，当前已是 {theme_name} 主题")

    def _on_client_connection_status_changed(self, connected, user_obj):
        """处理客户端连接状态变化信号
        
        Args:
            connected: 是否已连接
            user_obj: Pyrogram用户对象
        """
        if not hasattr(self, 'main_window'):
            logger.warning("主窗口未初始化，无法更新客户端状态")
            return
            
        if connected and user_obj:
            # 获取用户信息并格式化
            user_info = f"{user_obj.first_name}"
            if user_obj.last_name:
                user_info += f" {user_obj.last_name}"
            user_info += f" (@{user_obj.username})" if user_obj.username else ""
            
            logger.info(f"客户端已连接：{user_info}")
            # 更新主窗口状态栏
            self.main_window._update_client_status(True, user_info)
            
            # 如果设置视图已打开，更新登录按钮状态
            if hasattr(self.main_window, 'opened_views') and 'settings_view' in self.main_window.opened_views:
                settings_view = self.main_window.opened_views['settings_view']
                if hasattr(settings_view, 'update_login_button'):
                    settings_view.update_login_button(True, user_info)
            
            # 首次登录模式且登录成功后，初始化剩余的核心组件
            if self.is_first_login:
                logger.info("首次登录成功，开始初始化剩余核心组件")
                
                # 用于追踪组件初始化状态
                initialized_components = []
                failed_components = []
                
                # 更新client引用
                if hasattr(self.client_manager, 'client'):
                    self.client = self.client_manager.client
                    logger.info("已更新客户端引用")
                    initialized_components.append('client')
                else:
                    logger.warning("无法获取客户端引用")
                    failed_components.append('client')
                    return
                    
                try:
                    # 不再在此处启动网络连接检查，而是延后启动
                    
                    # 更新channel_resolver的client引用
                    if hasattr(self, 'channel_resolver'):
                        self.channel_resolver.client = self.client
                        logger.info("已更新频道解析器的客户端引用")
                        initialized_components.append('channel_resolver(更新)')
                    else:
                        # 如果channel_resolver不存在，创建它
                        logger.info("正在创建频道解析器...")
                        try:
                            from src.utils.channel_resolver import ChannelResolver
                            self.channel_resolver = ChannelResolver(self.client)
                            logger.info("已创建频道解析器")
                            initialized_components.append('channel_resolver(新建)')
                        except Exception as e:
                            logger.error(f"创建频道解析器时出错: {e}")
                            failed_components.append('channel_resolver')
                    
                    # 确保history_manager已初始化
                    if not hasattr(self, 'history_manager'):
                        logger.info("正在创建历史管理器...")
                        try:
                            from src.utils.history_manager import HistoryManager
                            self.history_manager = HistoryManager()
                            logger.info("已创建历史管理器")
                            initialized_components.append('history_manager')
                        except Exception as e:
                            logger.error(f"创建历史管理器时出错: {e}")
                            failed_components.append('history_manager')
                    else:
                        logger.info("历史管理器已存在")
                        initialized_components.append('history_manager(已存在)')
                    
                    # 4. 初始化下载模块
                    logger.info("正在初始化下载模块...")
                    try:
                        from src.modules.downloader import Downloader
                        self.downloader = Downloader(self.client, self.ui_config_manager, 
                                                    self.channel_resolver, self.history_manager)
                        logger.info("已初始化下载模块")
                        initialized_components.append('downloader')
                    except Exception as e:
                        logger.error(f"初始化下载模块时出错: {e}")
                        failed_components.append('downloader')
                    
                    # 5. 初始化串行下载模块
                        logger.info("正在初始化串行下载模块...")
                    try:
                        from src.modules.downloader_serial import DownloaderSerial
                        self.downloader_serial = DownloaderSerial(self.client, self.ui_config_manager, 
                                                                self.channel_resolver, self.history_manager)
                        logger.info("已初始化串行下载模块")
                        initialized_components.append('downloader_serial')
                    except Exception as e:
                        logger.error(f"初始化串行下载模块时出错: {e}")
                        failed_components.append('downloader_serial')
                    
                    # 6. 初始化上传模块
                    logger.info("正在初始化上传模块...")
                    try:
                        from src.modules.uploader import Uploader
                        self.uploader = Uploader(self.client, self.ui_config_manager, 
                                                self.channel_resolver, self.history_manager, self)
                        logger.info("已初始化上传模块")
                        initialized_components.append('uploader')
                    except Exception as e:
                        logger.error(f"初始化上传模块时出错: {e}")
                        failed_components.append('uploader')
                    
                    # 7. 初始化转发模块
                    logger.info("正在初始化转发模块...")
                    try:
                        from src.modules.forwarder import Forwarder
                        self.forwarder = Forwarder(self.client, self.ui_config_manager, 
                                                    self.channel_resolver, self.history_manager, 
                                                    self.downloader, self.uploader, self)
                        logger.info("已初始化转发模块")
                        initialized_components.append('forwarder')
                    except Exception as e:
                        logger.error(f"初始化转发模块时出错: {e}")
                        failed_components.append('forwarder')
                    
                    # 8. 初始化监听模块
                    logger.info("正在初始化监听模块...")
                    try:
                        from src.modules.monitor import Monitor
                        self.monitor = Monitor(self.client, self.ui_config_manager, 
                                                self.channel_resolver, self.history_manager, self)
                        logger.info("已初始化监听模块")
                        initialized_components.append('monitor')
                    except Exception as e:
                        logger.error(f"初始化监听模块时出错: {e}")
                        failed_components.append('monitor')
                    
                    # 检查必需组件是否全部初始化
                    required_components = ['client', 'channel_resolver', 'history_manager', 
                                          'downloader', 'downloader_serial',
                                          'uploader', 'forwarder', 'monitor']
                    
                    missing_components = [comp for comp in required_components 
                                        if not any(comp in init_comp for init_comp in initialized_components)]
                    
                    if missing_components:
                        logger.warning(f"以下必需组件未初始化: {', '.join(missing_components)}")
                    
                    if failed_components:
                        logger.error(f"以下组件初始化失败: {', '.join(failed_components)}")
                        
                    # 组件初始化总结
                    logger.info(f"首次登录组件初始化总结: 成功={len(initialized_components)}, 失败={len(failed_components)}, 缺失={len(missing_components)}")
                    logger.info(f"已初始化的组件: {', '.join(initialized_components)}")
                    
                    # 首次登录模式标志重置
                    self.is_first_login = False
                    logger.info("首次登录模式已完成，所有核心组件已初始化")
                    
                    # 将功能模块传递给已加载的视图组件（注意：视图采用延迟加载，可能还未创建）
                    self._initialize_views()
                except Exception as e:
                    logger.error(f"首次登录后初始化核心组件时出错: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
            
            # 确保信息被实时处理
            QApplication.processEvents()
            
            # 重置数据库锁定错误计数器
            self._db_lock_error_count = 0
            
            # 启动网络连接检查任务
            # 使用异步任务启动网络检查，确保在登录处理完成后启动
            if hasattr(self, 'task_manager'):
                self.task_manager.add_task("start_network_check", self._start_network_check())
                logger.debug("已安排启动网络连接检查")
        else:
            logger.info("客户端已断开连接")
            # 更新主窗口状态栏为断开状态
            self.main_window._update_client_status(False)
            
            # 如果设置视图已打开，更新登录按钮状态
            if hasattr(self.main_window, 'opened_views') and 'settings_view' in self.main_window.opened_views:
                settings_view = self.main_window.opened_views['settings_view']
                if hasattr(settings_view, 'update_login_button'):
                    settings_view.update_login_button(False)
            
            # 确保信息被实时处理
            QApplication.processEvents()

    async def _start_network_check(self):
        """启动网络连接状态检查任务
        
        此方法确保网络连接检查任务在登录过程完成后启动，以避免任务冲突
        """
        # 检查是否已存在网络检查任务
        if hasattr(self, 'task_manager') and self.task_manager.is_task_running("network_connection_check"):
            logger.debug("网络连接检查任务已在运行，无需重复启动")
            return
            
        # 等待短暂延迟，确保登录过程完全结束
        await safe_sleep(2)
        
        # 启动网络连接检查任务
        if hasattr(self, 'task_manager'):
            self.task_manager.add_task("network_connection_check", self._check_network_connection_periodically())
            logger.info("已启动网络连接状态检查定时任务")
        else:
            logger.warning("任务管理器不存在，无法启动网络连接检查")

    async def _check_network_connection_periodically(self):
        """定期检查网络连接状态"""
        while True:
            try:
                # 已经关闭应用则停止检查
                if not hasattr(self, 'client_manager') or not self.client_manager:
                    logger.debug("客户端管理器不存在，停止网络连接检查")
                    break
                
                # 执行连接检查
                connection_status = await self.client_manager.check_connection_status()
                
                # 根据连接状态调整检查频率
                if connection_status:
                    # 连接正常时，每5秒检查一次
                    await safe_sleep(5)
                else:
                    # 连接异常时，每2秒检查一次，更快发现代理恢复
                    await safe_sleep(2)
                
            except asyncio.CancelledError:
                logger.info("网络连接检查任务已取消")
                break
            except Exception as e:
                logger.error(f"网络连接检查出错: {e}")
                # 出错后减少等待时间，更快重试
                await safe_sleep(2)
                
    async def check_connection_status_now(self):
        """立即检查网络连接状态，用于响应网络错误事件"""
        try:
            if not hasattr(self, 'client_manager') or not self.client_manager:
                logger.debug("客户端管理器不存在，无法检查连接状态")
                return False
            
            # 立即执行连接检查
            connection_status = await self.client_manager.check_connection_status()
            
            # 检查是否存在数据库锁定的持续错误
            if not connection_status:
                # 初始化计数器（如果不存在）
                if not hasattr(self, '_db_lock_error_count'):
                    self._db_lock_error_count = 0
                    
                # 检查最近的错误日志
                recent_errors = getattr(self.client_manager, 'recent_errors', [])
                has_db_lock_error = any("database is locked" in str(err).lower() for err in recent_errors)
                
                if has_db_lock_error:
                    self._db_lock_error_count += 1
                    
                    # 连续3次以上数据库锁定错误，显示提示
                    if self._db_lock_error_count >= 3 and hasattr(self, 'main_window'):
                        from PySide6.QtWidgets import QMessageBox
                        # 提前导入QMetaObject
                        from PySide6.QtCore import QMetaObject, Qt
                        
                        # 只在主线程中显示对话框
                        def show_db_lock_warning():
                            if not hasattr(self, '_db_lock_warning_shown'):
                                self._db_lock_warning_shown = True
                                QMessageBox.warning(
                                    self.main_window,
                                    "数据库锁定错误",
                                    "检测到会话数据库锁定问题，自动修复失败。\n\n"
                                    "建议操作：\n"
                                    "1. 保存您的工作\n"
                                    "2. 关闭TG-Manager\n"
                                    "3. 确保没有其他TG-Manager实例运行\n"
                                    "4. 重新启动应用\n\n"
                                    "如果问题持续存在，您可能需要手动删除sessions目录中的会话文件。"
                                )
                                # 重置标志，5分钟后允许再次显示
                                def reset_warning_flag():
                                    self._db_lock_warning_shown = False
                                # 5分钟后允许再次显示
                                QTimer.singleShot(300000, reset_warning_flag)
                                
                        # 检查是否已显示警告
                        if not hasattr(self, '_db_lock_warning_shown') or not self._db_lock_warning_shown:
                            # 使用Qt的线程安全方式调用
                            # 修改为使用方法名称字符串
                            setattr(self.main_window, "_temp_show_db_lock_warning", show_db_lock_warning)
                            QMetaObject.invokeMethod(self.main_window, "_temp_show_db_lock_warning", Qt.ConnectionType.QueuedConnection)
                else:
                    # 如果不是数据库锁定错误，重置计数器
                    self._db_lock_error_count = 0
                
            return connection_status
        except Exception as e:
            logger.error(f"立即检查连接状态出错: {e}")
            return False

    def _open_settings_for_first_login(self):
        """为首次登录打开设置界面并显示指导信息"""
        logger.info("执行首次登录引导流程")
        
        try:
            if not hasattr(self, 'main_window'):
                logger.warning("应用程序没有主窗口实例，无法打开设置界面")
                return
                
            # 使用Qt的线程安全方式调用打开设置界面
            # 提前导入所需模块，避免在回调中导入
            from PySide6.QtCore import QMetaObject, Qt
            # 使用方法名称字符串调用
            QMetaObject.invokeMethod(self.main_window, "_open_settings", Qt.ConnectionType.QueuedConnection)
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
            if not hasattr(self, 'main_window'):
                return
                
            from PySide6.QtWidgets import QMessageBox
            logger.info("显示首次登录提示对话框")
            
            QMessageBox.information(
                self.main_window,
                "首次使用提示",
                """欢迎使用TG-Manager！

检测到这是您首次使用本程序，请在API设置中填写您的Telegram API凭据并点击登录按钮完成登录。

如果您还没有API ID和API Hash，请访问 https://my.telegram.org 申请。

填写完成后，请点击"登录"按钮完成账号验证。""",
                QMessageBox.Ok
            )
        except Exception as e:
            logger.error(f"显示首次登录对话框时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())


def main():
    """应用程序入口函数"""
    app = TGManagerApp()
    sys.exit(app.run())


if __name__ == "__main__":
    main() 