"""
TG-Manager 客户端管理模块
负责处理Telegram客户端的连接状态变化
"""

from PySide6.QtCore import QTimer, QMetaObject, Qt
from PySide6.QtWidgets import QMessageBox
from loguru import logger
from src.utils.async_utils import safe_sleep


class ClientHandler:
    """客户端处理类，管理客户端连接状态变化"""
    
    def __init__(self, app=None):
        """初始化客户端处理类
        
        Args:
            app: TGManagerApp实例
        """
        self.app = app
        self._db_lock_error_count = 0
        self._db_lock_warning_shown = False
    
    def on_client_connection_status_changed(self, connected, user_obj, main_window=None):
        """处理客户端连接状态变化信号
        
        Args:
            connected: 是否已连接
            user_obj: Pyrogram用户对象
            main_window: 主窗口实例
        """
        if main_window is None and self.app and hasattr(self.app, 'main_window'):
            main_window = self.app.main_window
            
        if main_window is None:
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
            main_window._update_client_status(True, user_info)
            
            # 如果设置视图已打开，更新登录按钮状态
            if hasattr(main_window, 'opened_views') and 'settings_view' in main_window.opened_views:
                settings_view = main_window.opened_views['settings_view']
                if hasattr(settings_view, 'update_login_button'):
                    settings_view.update_login_button(True, user_info)
            
            # 首次登录模式且登录成功后，初始化剩余的核心组件
            if self.app and hasattr(self.app, 'is_first_login') and self.app.is_first_login:
                self._handle_first_login_success()
            
            # 确保信息被实时处理
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()
            
            # 重置数据库锁定错误计数器
            self._db_lock_error_count = 0
            
            # 启动网络连接检查任务
            if self.app and hasattr(self.app, 'task_manager'):
                self.app.task_manager.add_task("start_network_check", self._start_network_check())
                logger.debug("已安排启动网络连接检查")
        else:
            logger.info("客户端已断开连接")
            # 更新主窗口状态栏为断开状态
            main_window._update_client_status(False)
            
            # 如果设置视图已打开，更新登录按钮状态
            if hasattr(main_window, 'opened_views') and 'settings_view' in main_window.opened_views:
                settings_view = main_window.opened_views['settings_view']
                if hasattr(settings_view, 'update_login_button'):
                    settings_view.update_login_button(False)
            
            # 确保信息被实时处理
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()
    
    async def _start_network_check(self):
        """启动网络连接状态检查任务
        
        此方法确保网络连接检查任务在登录过程完成后启动，以避免任务冲突
        """
        # 检查是否已存在网络检查任务
        if hasattr(self.app, 'task_manager') and self.app.task_manager.is_task_running("network_connection_check"):
            logger.debug("网络连接检查任务已在运行，无需重复启动")
            return
            
        # 等待短暂延迟，确保登录过程完全结束
        await safe_sleep(2)
        
        # 启动网络连接检查任务
        if hasattr(self.app, 'task_manager'):
            self.app.task_manager.add_task("network_connection_check", self._check_network_connection_periodically())
            logger.info("已启动网络连接状态检查定时任务")
        else:
            logger.warning("任务管理器不存在，无法启动网络连接检查")

    async def _check_network_connection_periodically(self):
        """定期检查网络连接状态"""
        while True:
            try:
                # 已经关闭应用则停止检查
                if not hasattr(self.app, 'client_manager') or not self.app.client_manager:
                    logger.debug("客户端管理器不存在，停止网络连接检查")
                    break
                
                # 执行连接检查
                connection_status = await self.app.client_manager.check_connection_status()
                
                # 减少检查频率，避免频繁API调用
                if connection_status:
                    # 连接正常时，每30秒检查一次（从5秒增加到30秒）
                    await safe_sleep(30)
                else:
                    # 连接异常时，每10秒检查一次（从2秒增加到10秒）
                    await safe_sleep(10)
                
            except Exception as e:
                if isinstance(e, KeyboardInterrupt) or "cancelled" in str(e).lower():
                    logger.info("网络连接检查任务已取消")
                    break
                logger.error(f"网络连接检查出错: {e}")
                # 出错后也减少等待时间，避免过于频繁的重试
                await safe_sleep(10)
                
    async def check_connection_status_now(self):
        """立即检查网络连接状态，用于响应网络错误事件"""
        try:
            if not hasattr(self.app, 'client_manager') or not self.app.client_manager:
                logger.debug("客户端管理器不存在，无法检查连接状态")
                return False
            
            # 立即执行连接检查
            connection_status = await self.app.client_manager.check_connection_status()
            
            # 检查是否存在数据库锁定的持续错误
            if not connection_status:
                # 初始化计数器（如果不存在）
                if not hasattr(self, '_db_lock_error_count'):
                    self._db_lock_error_count = 0
                    
                # 检查最近的错误日志
                recent_errors = getattr(self.app.client_manager, 'recent_errors', [])
                has_db_lock_error = any("database is locked" in str(err).lower() for err in recent_errors)
                
                if has_db_lock_error:
                    self._db_lock_error_count += 1
                    
                    # 连续3次以上数据库锁定错误，显示提示
                    if self._db_lock_error_count >= 3 and hasattr(self.app, 'main_window'):
                        # 只在主线程中显示对话框
                        def show_db_lock_warning():
                            if not hasattr(self, '_db_lock_warning_shown') or not self._db_lock_warning_shown:
                                self._db_lock_warning_shown = True
                                QMessageBox.warning(
                                    self.app.main_window,
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
                            setattr(self.app.main_window, "_temp_show_db_lock_warning", show_db_lock_warning)
                            QMetaObject.invokeMethod(self.app.main_window, "_temp_show_db_lock_warning", 
                                                    Qt.ConnectionType.QueuedConnection)
                else:
                    # 如果不是数据库锁定错误，重置计数器
                    self._db_lock_error_count = 0
                
            return connection_status
        except Exception as e:
            logger.error(f"立即检查连接状态出错: {e}")
            return False
            
    def _handle_first_login_success(self):
        """处理首次登录成功后的核心组件初始化"""
        if not self.app:
            return
            
        logger.info("首次登录成功，开始初始化剩余核心组件")
        
        # 用于追踪组件初始化状态
        initialized_components = []
        failed_components = []
        
        # 更新client引用
        if hasattr(self.app.client_manager, 'client'):
            self.app.client = self.app.client_manager.client
            logger.info("已更新客户端引用")
            initialized_components.append('client')
        else:
            logger.warning("无法获取客户端引用")
            failed_components.append('client')
            return
            
        try:
            # 更新channel_resolver的client引用
            if hasattr(self.app, 'channel_resolver'):
                self.app.channel_resolver.client = self.app.client
                logger.info("已更新频道解析器的客户端引用")
                initialized_components.append('channel_resolver(更新)')
            else:
                # 如果channel_resolver不存在，创建它
                logger.info("正在创建频道解析器...")
                try:
                    from src.utils.channel_resolver import ChannelResolver
                    self.app.channel_resolver = ChannelResolver(self.app.client)
                    logger.info("已创建频道解析器")
                    initialized_components.append('channel_resolver(新建)')
                except Exception as e:
                    logger.error(f"创建频道解析器时出错: {e}")
                    failed_components.append('channel_resolver')
            
            # 确保history_manager已初始化
            if not hasattr(self.app, 'history_manager'):
                logger.info("正在创建历史管理器...")
                try:
                    from src.utils.database_manager import DatabaseManager
                    self.app.history_manager = DatabaseManager()
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
                from src.modules.forward.forwarder import Forwarder
                original_forwarder = Forwarder(self.app.client, self.app.ui_config_manager, 
                                            self.app.channel_resolver, self.app.history_manager, 
                                            self.app.downloader, self.app.uploader, self.app)
                                    
                # 使用事件发射器包装转发器
                from src.modules.event_emitter_forwarder import EventEmitterForwarder
                self.app.forwarder = EventEmitterForwarder(original_forwarder)
                logger.info("已初始化转发模块并添加信号支持")
                initialized_components.append('forwarder')
            except Exception as e:
                logger.error(f"初始化转发模块时出错: {e}")
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
                                if not any(comp in init_comp for init_comp in initialized_components)]
            
            if missing_components:
                logger.warning(f"以下必需组件未初始化: {', '.join(missing_components)}")
            
            if failed_components:
                logger.error(f"以下组件初始化失败: {', '.join(failed_components)}")
                
            # 组件初始化总结
            logger.info(f"首次登录组件初始化总结: 成功={len(initialized_components)}, 失败={len(failed_components)}, 缺失={len(missing_components)}")
            logger.info(f"已初始化的组件: {', '.join(initialized_components)}")
            
            # 首次登录模式标志重置
            self.app.is_first_login = False
            logger.info("首次登录模式已完成，所有核心组件已初始化")
            
            # 将功能模块传递给已加载的视图组件（注意：视图采用延迟加载，可能还未创建）
            if hasattr(self.app, '_initialize_views'):
                self.app._initialize_views()
        except Exception as e:
            logger.error(f"首次登录后初始化核心组件时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def on_time_sync_error(self, error_message):
        """处理时间同步错误
        
        Args:
            error_message: 错误消息
        """
        logger.error(f"收到时间同步错误信号: {error_message}")
        
        # 在主线程中显示错误对话框
        def show_time_sync_dialog():
            from PySide6.QtWidgets import QMessageBox
            from PySide6.QtCore import Qt
            
            # 创建错误对话框
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setWindowTitle("系统时间同步错误")
            msg_box.setText("检测到系统时间与服务器时间不同步")
            msg_box.setDetailedText(error_message)
            msg_box.setStandardButtons(QMessageBox.Ok)
            
            # 设置对话框为模态
            msg_box.setModal(True)
            
            # 显示对话框并等待用户点击
            result = msg_box.exec()
            
            # 用户点击确定后关闭程序
            if result == QMessageBox.Ok:
                logger.info("用户确认时间同步错误对话框，程序即将关闭")
                # 关闭应用程序
                if self.app and hasattr(self.app, 'app'):
                    self.app.app.quit()
        
        # 使用QTimer在主线程中延迟执行
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, show_time_sync_dialog) 