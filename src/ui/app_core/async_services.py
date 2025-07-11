"""
TG-Manager 异步服务初始化模块
负责初始化所有异步服务和组件
"""

import asyncio
import os
from loguru import logger
from src.utils.async_utils import safe_sleep, AsyncTaskManager


class AsyncServicesInitializer:
    """异步服务初始化类"""
    
    def __init__(self, app=None):
        """初始化异步服务初始化类
        
        Args:
            app: TGManagerApp实例
        """
        self.app = app
        
    async def init_async_services(self, first_login_handler=None):
        """初始化异步服务
        
        Args:
            first_login_handler: 首次登录处理器实例，可选
            
        Returns:
            bool: 是否成功初始化
        """
        logger.info("正在初始化异步服务...")
        try:
            if self.app is None:
                logger.error("应用程序实例未设置，无法初始化异步服务")
                return False
                
            # 初始化异步任务计划
            if not hasattr(self.app, 'task_manager') or self.app.task_manager is None:
                self.app.task_manager = AsyncTaskManager()
                logger.debug("已创建异步任务管理器")
            
            # 1. 初始化强壮的Telegram客户端
            from src.utils.robust_client import RobustTelegramClient
            self.app.client_manager = RobustTelegramClient()
            logger.debug("已初始化客户端管理器")
            
            # 连接客户端状态信号
            if hasattr(self.app.client_manager, 'connection_status_changed'):
                if hasattr(self.app, 'client_handler'):
                    self.app.client_manager.connection_status_changed.connect(
                        self.app.client_handler.on_client_connection_status_changed)
                    logger.debug("已连接客户端状态变化信号到客户端处理器")
                else:
                    # 兼容性：直接连接到应用程序的回调
                    if hasattr(self.app, '_on_client_connection_status_changed'):
                        self.app.client_manager.connection_status_changed.connect(
                            self.app._on_client_connection_status_changed)
                        logger.debug("已连接客户端状态变化信号到应用程序回调")
            
            # 连接时间同步错误信号
            if hasattr(self.app.client_manager, 'time_sync_error'):
                if hasattr(self.app, 'client_handler'):
                    self.app.client_manager.time_sync_error.connect(
                        self.app.client_handler.on_time_sync_error)
                    logger.debug("已连接时间同步错误信号到客户端处理器")
                else:
                    logger.warning("客户端处理器不存在，无法连接时间同步错误信号")
            
            # 检查会话文件是否存在，判断是否为首次登录
            session_name = self.app.client_manager.session_name
            logger.debug(f"检查首次登录状态，会话名称: {session_name}")
            
            # 使用首次登录处理器检查是否为首次登录
            if first_login_handler:
                logger.debug("使用FirstLoginHandler检查首次登录状态")
                self.app.is_first_login = first_login_handler.check_first_login(session_name)
            else:
                # 兼容性：直接检查会话文件
                session_path = f"sessions/{session_name}.session"
                self.app.is_first_login = not os.path.exists(session_path)
                logger.debug(f"直接检查会话文件: {session_path}, 存在: {os.path.exists(session_path)}")
                if self.app.is_first_login:
                    logger.info(f"检测到首次登录，会话文件不存在: {session_path}")
            
            logger.info(f"首次登录检测结果: {self.app.is_first_login}")
            
            if self.app.is_first_login:
                # 首次登录不自动启动客户端，等待用户点击登录按钮
                
                # 2. 创建channel_resolver (仍然需要创建，但设置client为None)
                from src.utils.channel_resolver import ChannelResolver
                self.app.channel_resolver = ChannelResolver(None)
                logger.info("已创建频道解析器(无客户端)")
                
                # 3. 初始化history_manager
                from src.utils.database_manager import DatabaseManager
                self.app.history_manager = DatabaseManager()
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
                        self.app.client = await self.app.client_manager.start_client()
                        logger.info("客户端启动成功")
                        initialized_components.append('client')
                    except Exception as client_error:
                        logger.error(f"启动客户端失败: {client_error}")
                        failed_components.append('client')
                        raise  # 如果客户端启动失败，重新抛出异常以中止其他初始化
                    
                    # 标记客户端为活动状态
                    self.app.client_manager.connection_active = True
                    
                    # 如果主窗口已初始化，更新状态栏
                    if hasattr(self.app, 'main_window') and self.app.client_manager.me:
                        # 获取用户信息并格式化
                        me = self.app.client_manager.me
                        user_info = f"{me.first_name}"
                        if me.last_name:
                            user_info += f" {me.last_name}"
                        user_info += f" (@{me.username})" if me.username else ""
                        
                        # 更新主窗口状态栏
                        self.app.main_window._update_client_status(True, user_info)
                        logger.debug(f"已更新状态栏客户端状态: {user_info}")
                        
                        # 更新设置界面中的登录按钮状态
                        if hasattr(self.app.main_window, 'opened_views') and 'settings_view' in self.app.main_window.opened_views:
                            settings_view = self.app.main_window.opened_views['settings_view']
                            if hasattr(settings_view, 'update_login_button'):
                                settings_view.update_login_button(True, user_info)
                                logger.debug("已更新设置视图中的登录按钮状态")
                
                except Exception as e:
                    logger.error(f"启动Telegram客户端时出错: {e}")
                    # 显示错误但继续运行，允许用户稍后通过登录按钮登录
                    if hasattr(self.app, 'main_window'):
                        self.app.main_window._update_client_status(False)
                        # 更新设置界面中的登录按钮状态
                        if hasattr(self.app.main_window, 'opened_views') and 'settings_view' in self.app.main_window.opened_views:
                            settings_view = self.app.main_window.opened_views['settings_view']
                            if hasattr(settings_view, 'update_login_button'):
                                settings_view.update_login_button(False)
                    return False  # 如果客户端启动失败，提前返回
                
                # 2. 创建channel_resolver
                logger.info("正在创建频道解析器...")
                try:
                    from src.utils.channel_resolver import ChannelResolver
                    self.app.channel_resolver = ChannelResolver(self.app.client)
                    logger.info("已创建频道解析器")
                    initialized_components.append('channel_resolver')
                except Exception as e:
                    logger.error(f"创建频道解析器时出错: {e}")
                    failed_components.append('channel_resolver')
                
                # 3. 初始化history_manager
                logger.info("正在创建历史管理器...")
                try:
                    from src.utils.database_manager import DatabaseManager
                    self.app.history_manager = DatabaseManager()
                    logger.info("已创建历史管理器")
                    initialized_components.append('history_manager')
                except Exception as e:
                    logger.error(f"创建历史管理器时出错: {e}")
                    failed_components.append('history_manager')
                
                # 4. 初始化下载模块
                logger.info("正在初始化下载模块...")
                try:
                    from src.modules.downloader import Downloader
                    original_downloader = Downloader(self.app.client, self.app.ui_config_manager, 
                                                    self.app.channel_resolver, self.app.history_manager)
                    
                    # 使用事件发射器包装下载器
                    from src.modules.event_emitter_downloader import EventEmitterDownloader
                    self.app.downloader = EventEmitterDownloader(original_downloader)
                    logger.info("已初始化下载模块并添加信号支持")
                    initialized_components.append('downloader')
                except Exception as e:
                    logger.error(f"初始化下载模块时出错: {e}")
                    failed_components.append('downloader')
                
                # 5. 初始化串行下载模块
                logger.info("正在初始化串行下载模块...")
                try:
                    from src.modules.downloader_serial import DownloaderSerial
                    original_downloader_serial = DownloaderSerial(self.app.client, self.app.ui_config_manager, 
                                                                self.app.channel_resolver, self.app.history_manager, self.app)
                    
                    # 使用事件发射器包装串行下载器
                    from src.modules.event_emitter_downloader_serial import EventEmitterDownloaderSerial
                    self.app.downloader_serial = EventEmitterDownloaderSerial(original_downloader_serial)
                    logger.info("已初始化串行下载模块并添加信号支持")
                    initialized_components.append('downloader_serial')
                except Exception as e:
                    logger.error(f"初始化串行下载模块时出错: {e}")
                    failed_components.append('downloader_serial')
                
                # 6. 初始化上传模块
                logger.info("正在初始化上传模块...")
                try:
                    from src.modules.uploader import Uploader
                    original_uploader = Uploader(self.app.client, self.app.ui_config_manager, 
                                                self.app.channel_resolver, self.app.history_manager, self.app)
                    
                    # 使用事件发射器包装上传器
                    from src.modules.event_emitter_uploader import EventEmitterUploader
                    self.app.uploader = EventEmitterUploader(original_uploader)
                    logger.info("已初始化上传模块并添加信号支持")
                    initialized_components.append('uploader')
                except Exception as e:
                    logger.error(f"初始化上传模块时出错: {e}")
                    failed_components.append('uploader')
                
                # 7. 初始化转发模块
                logger.info("正在初始化转发模块...")
                try:
                    # 检查依赖组件
                    logger.debug(f"检查转发器依赖组件:")
                    logger.debug(f"  - client: {hasattr(self.app, 'client')}")
                    logger.debug(f"  - ui_config_manager: {hasattr(self.app, 'ui_config_manager')}")
                    logger.debug(f"  - channel_resolver: {hasattr(self.app, 'channel_resolver')}")
                    logger.debug(f"  - history_manager: {hasattr(self.app, 'history_manager')}")
                    logger.debug(f"  - downloader: {hasattr(self.app, 'downloader')}")
                    logger.debug(f"  - uploader: {hasattr(self.app, 'uploader')}")
                    
                    # 导入转发器类
                    logger.debug("导入Forwarder类...")
                    from src.modules.forward.forwarder import Forwarder
                    
                    # 创建原始转发器实例
                    logger.debug("创建原始转发器实例...")
                    original_forwarder = Forwarder(self.app.client, self.app.ui_config_manager, 
                                                  self.app.channel_resolver, self.app.history_manager, 
                                                  self.app.downloader, self.app.uploader, self.app)
                    logger.debug("原始转发器实例创建成功")
                    
                    # 导入事件发射器包装类
                    logger.debug("导入EventEmitterForwarder类...")
                    from src.modules.event_emitter_forwarder import EventEmitterForwarder
                    
                    # 使用事件发射器包装转发器
                    logger.debug("创建事件发射器包装转发器...")
                    self.app.forwarder = EventEmitterForwarder(original_forwarder)
                    logger.debug("事件发射器包装转发器创建成功")
                    
                    logger.info("已初始化转发模块并添加信号支持")
                    initialized_components.append('forwarder')
                except Exception as e:
                    logger.error(f"初始化转发模块时出错: {e}")
                    logger.error(f"错误类型: {type(e).__name__}")
                    import traceback
                    logger.error(f"完整错误堆栈:\n{traceback.format_exc()}")
                    failed_components.append('forwarder')
                
                # 8. 初始化监听模块
                logger.info("正在初始化监听模块...")
                try:
                    from src.modules.monitor.core import Monitor  # 使用新的监听器架构
                    # 传递强壮客户端管理器而不是原生客户端
                    original_monitor = Monitor(self.app.client_manager, self.app.ui_config_manager, 
                                             self.app.channel_resolver, self.app)
                    
                    # 使用事件发射器包装监听器
                    from src.modules.event_emitter_monitor import EventEmitterMonitor
                    self.app.monitor = EventEmitterMonitor(original_monitor)
                    logger.info("已初始化监听模块并添加信号支持")
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
            return True
        except Exception as e:
            logger.error(f"初始化异步服务时出错: {e}")
            import traceback
            logger.error(f"错误详情:\n{traceback.format_exc()}")
            return False

    def initialize_views(self):
        """初始化所有视图组件，传递功能模块实例
        
        注意：视图采用延迟加载方式，只有在用户点击相应导航项时才会创建
        此方法只是将功能模块实例传递到已存在的视图中，不检查视图是否已加载
        """
        if not hasattr(self.app, 'main_window'):
            logger.warning("主窗口未初始化，无法设置视图组件")
            return
        
        # 获取视图引用并设置功能模块
        try:
            # 【新增】自动加载日志查看器视图
            self._auto_load_log_viewer()
            
            # 下载视图
            download_view = self.app.main_window.get_view("download")
            if download_view and hasattr(self.app, 'downloader'):
                download_view.set_downloader(self.app.downloader)
                logger.info("下载视图已设置下载器实例")
            
            # 上传视图
            upload_view = self.app.main_window.get_view("upload")
            if upload_view and hasattr(self.app, 'uploader'):
                upload_view.set_uploader(self.app.uploader)
                logger.info("上传视图已设置上传器实例")
            
            # 转发视图
            forward_view = self.app.main_window.get_view("forward")
            if forward_view and hasattr(self.app, 'forwarder'):
                forward_view.set_forwarder(self.app.forwarder)
                logger.info("转发视图已设置转发器实例")
            
            # 监听视图
            listen_view = self.app.main_window.get_view("listen")
            if listen_view and hasattr(self.app, 'monitor'):
                listen_view.set_monitor(self.app.monitor)
                logger.info("监听视图已设置监听器实例")
            
            # 任务视图已删除，无需设置任务管理器
            
            logger.info("视图组件初始化设置完成（视图将在用户点击时加载，日志查看器已自动加载）")
        except Exception as e:
            logger.error(f"初始化视图组件时出错: {e}")
            import traceback
            logger.error(f"错误详情:\n{traceback.format_exc()}")

    def _auto_load_log_viewer(self):
        """自动加载日志查看器视图
        
        此方法会在程序启动时自动创建并加载日志查看器视图，
        而其他视图保持延迟加载的模式
        """
        try:
            # 检查日志查看器是否已经加载
            if "log_viewer" in self.app.main_window.opened_views:
                logger.debug("日志查看器视图已存在，跳过自动加载")
                return
            
            logger.info("正在自动加载日志查看器视图...")
            
            # 导入日志查看器视图
            from src.ui.views.log_viewer_view import LogViewerView
            
            # 创建日志查看器视图
            log_viewer = LogViewerView(self.app.config, self.app.main_window)
            
            # 添加到主窗口的中心布局
            self.app.main_window.central_layout.addWidget(log_viewer)
            self.app.main_window.opened_views["log_viewer"] = log_viewer
            
            # 注意：不要自动切换到日志查看器，保持当前显示的视图
            # 这样日志查看器会在后台加载，用户可以通过菜单或导航树访问
            
            logger.info("日志查看器视图已自动加载完成")
            
        except Exception as e:
            logger.error(f"自动加载日志查看器视图失败: {e}")
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
            except Exception as e:
                if isinstance(e, asyncio.CancelledError) or "cancelled" in str(e).lower():
                    logger.info("全局异常处理器已取消")
                    break
                logger.error(f"全局异常处理器出错: {e}")
                await safe_sleep(5)  # 出错后等待5秒再继续 