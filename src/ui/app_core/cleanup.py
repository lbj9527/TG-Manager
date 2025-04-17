"""
TG-Manager 应用程序清理模块
负责在应用程序退出时安全清理资源
"""

import asyncio
import signal
from PySide6.QtCore import QTimer
from loguru import logger
from src.utils.async_utils import get_event_loop


class CleanupManager:
    """应用程序清理管理器，负责安全清理资源"""
    
    def __init__(self, app=None):
        """初始化清理管理器
        
        Args:
            app: TGManagerApp实例
        """
        self.app = app
        self._is_closing = False
    
    def setup_cleanup_handlers(self):
        """设置清理处理器
        
        连接信号处理器以确保应用程序安全退出
        """
        if not self.app:
            logger.warning("应用程序实例未设置，无法设置清理处理器")
            return
            
        # 连接应用程序退出信号
        if hasattr(self.app, 'app') and hasattr(self.app.app, 'aboutToQuit'):
            self.app.app.aboutToQuit.connect(self._cleanup_sync)
            logger.debug("已连接应用程序退出信号到清理处理器")
        
        # 设置系统信号处理器
        try:
            signal.signal(signal.SIGINT, lambda sig, frame: self._cleanup_sync())
            logger.debug("已设置SIGINT信号处理器")
        except (ValueError, AttributeError) as e:
            # 在某些环境下可能无法设置信号处理器
            logger.warning(f"无法设置信号处理器: {e}")
    
    def _cleanup_sync(self):
        """同步清理入口，用于连接Qt信号"""
        # 记录正在关闭的状态，避免重复调用
        if self._is_closing:
            logger.debug("已经在关闭过程中，忽略重复调用")
            return
            
        self._is_closing = True
        logger.info("开始同步清理过程")
        
        # 发出应用程序关闭信号
        if hasattr(self.app, 'app_closing'):
            self.app.app_closing.emit()
        
        # 如果主窗口已创建，发送关闭信号
        if hasattr(self.app, 'main_window'):
            # 停止资源监控计时器
            if hasattr(self.app.main_window, "resource_timer") and self.app.main_window.resource_timer:
                self.app.main_window.resource_timer.stop()
                logger.debug("资源监控计时器已停止")
            
            # 隐藏系统托盘图标
            if hasattr(self.app.main_window, 'tray_icon') and self.app.main_window.tray_icon:
                self.app.main_window.tray_icon.hide()
                logger.debug("系统托盘图标已隐藏")
        
        # 取消所有定时器和任务
        if hasattr(self.app, 'task_manager'):
            logger.debug("取消网络连接检查任务")
            self.app.task_manager.cancel_task("network_connection_check")
            # 取消所有其他任务
            self.app.task_manager.cancel_all_tasks()
            logger.debug("所有任务已取消")
        
        # 创建异步清理任务
        loop = get_event_loop()
        if loop and loop.is_running():
            try:
                # 使用Qt计时器延迟执行异步清理，避免事件循环冲突
                timer = QTimer()
                timer.setSingleShot(True)
                timer.timeout.connect(lambda: self._execute_async_cleanup(loop))
                timer.start(10)  # 10毫秒后执行异步清理
                logger.debug("已安排延迟执行异步清理")
            except Exception as e:
                logger.error(f"创建清理任务时出错: {e}")
                # 如果创建任务失败，尝试直接退出
                if hasattr(self.app, 'app'):
                    self.app.app.quit()
        else:
            # 如果事件循环不存在或未运行，直接退出应用
            logger.warning("事件循环不可用，直接退出应用")
            if hasattr(self.app, 'app'):
                self.app.app.quit()
    
    def _execute_async_cleanup(self, loop):
        """执行异步清理，作为Qt计时器的回调函数
        
        Args:
            loop: 事件循环
        """
        try:
            # 安全创建异步清理任务
            future = asyncio.run_coroutine_threadsafe(self._async_cleanup(), loop)
            logger.debug("已创建异步清理任务")
            
            # 设置回调函数处理完成
            future.add_done_callback(lambda f: self._on_cleanup_done(f))
        except Exception as e:
            logger.error(f"执行异步清理时出错: {e}")
            # 出错时直接退出
            if hasattr(self.app, 'app'):
                self.app.app.quit()
    
    def _on_cleanup_done(self, future):
        """异步清理完成后的回调
        
        Args:
            future: 异步任务Future对象
        """
        try:
            # 尝试获取结果，检查是否有异常
            future.result()
            logger.info("异步清理任务已完成")
        except Exception as e:
            logger.error(f"异步清理任务出错: {e}")
        finally:
            # 无论如何，确保应用退出
            if hasattr(self.app, 'app'):
                self.app.app.quit()
                logger.info("应用程序已请求退出")
    
    async def _async_cleanup(self):
        """真正的异步清理操作
        
        Returns:
            bool: 清理是否成功完成
        """
        try:
            # 重置应用程序初始化状态，避免界面被锁定
            if hasattr(self.app, 'is_initializing'):
                self.app.is_initializing = False
                # 如果主窗口仍然存在，恢复其启用状态
                if hasattr(self.app, 'main_window') and self.app.main_window:
                    self.app.main_window.set_ui_enabled(True)
            
            # 先尝试取消特定的任务
            if hasattr(self.app, 'task_manager'):
                for task_name in ["download_task", "upload_task", "forward_task", "monitor_task", 
                                  "network_connection_check", "global_exception_handler"]:
                    if self.app.task_manager.is_task_running(task_name):
                        self.app.task_manager.cancel_task(task_name)
                        logger.debug(f"取消了特定任务: {task_name}")
                
                # 取消所有其他任务
                self.app.task_manager.cancel_all_tasks()
                logger.debug("已取消任务管理器中的所有任务")
            
            # 停止Telegram客户端
            if hasattr(self.app, 'client_manager') and self.app.client_manager:
                logger.debug("停止Telegram客户端")
                try:
                    await self.app.client_manager.stop_client()
                    logger.debug("Telegram客户端已停止")
                except Exception as e:
                    logger.error(f"停止Telegram客户端时出错: {e}")
            
            # 确保关闭所有视图的资源
            if hasattr(self.app, 'main_window') and self.app.main_window:
                if hasattr(self.app.main_window, 'opened_views'):
                    for view_name, view in self.app.main_window.opened_views.items():
                        if hasattr(view, '_cleanup_resources'):
                            try:
                                view._cleanup_resources()
                                logger.debug(f"已清理视图资源: {view_name}")
                            except Exception as e:
                                logger.error(f"清理视图 {view_name} 资源时出错: {e}")
            
            # 在事件循环中安全地获取和取消任务
            pending_tasks = [t for t in asyncio.all_tasks() 
                          if t is not asyncio.current_task() and not t.done()]
            
            if pending_tasks:
                logger.debug(f"发现 {len(pending_tasks)} 个待处理的异步任务")
                
                for task in pending_tasks:
                    task_name = task.get_name()
                    logger.debug(f"取消任务: {task_name}")
                    task.cancel()
                
                # 等待所有任务处理取消请求
                await asyncio.gather(*pending_tasks, return_exceptions=True)
                logger.debug("已等待所有任务处理取消请求")
            else:
                logger.debug("没有发现待处理的异步任务")
            
            logger.info("异步资源清理完成")
            return True
        except Exception as e:
            logger.error(f"异步清理过程出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    async def cleanup(self):
        """清理所有资源，包括客户端连接
        
        Returns:
            bool: 是否成功清理
        """
        try:
            logger.info("开始异步清理过程")
            
            # 重置应用程序初始化状态，避免界面被锁定
            if hasattr(self.app, 'is_initializing'):
                self.app.is_initializing = False
                # 如果主窗口仍然存在，恢复其启用状态
                if hasattr(self.app, 'main_window') and self.app.main_window:
                    self.app.main_window.set_ui_enabled(True)
            
            # 清理各个功能模块
            return await self._async_cleanup()
        except Exception as e:
            logger.error(f"清理过程出错: {e}")
            return False 