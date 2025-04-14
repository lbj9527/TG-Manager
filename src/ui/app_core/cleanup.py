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
            # 停止Telegram客户端
            if hasattr(self.app, 'client_manager') and self.app.client_manager:
                logger.debug("停止Telegram客户端")
                try:
                    await self.app.client_manager.stop_client()
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
    
    # 以下方法用于兼容旧的接口
    async def cleanup(self):
        """原有的异步清理方法，保持向后兼容
        
        注意：此方法已被新的清理流程替代，但保留以维持兼容性
        
        Returns:
            bool: 清理是否成功完成
        """
        logger.warning("使用了已弃用的cleanup方法，应该使用_cleanup_sync")
        return await self._async_cleanup() 