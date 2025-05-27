"""
TG-Manager 主窗口功能操作模块
包含各种菜单和按钮的处理函数
"""

import json
import datetime
from loguru import logger
from PySide6.QtWidgets import (
    QMessageBox, QInputDialog, QDialog, QVBoxLayout, 
    QFormLayout, QLineEdit, QDialogButtonBox, QLabel
)
from PySide6.QtCore import QRegularExpression, QTimer, Signal, Qt
from PySide6.QtGui import QRegularExpressionValidator, QAction

class ActionsMixin:
    """功能操作混入类
    
    为MainWindow提供各种功能操作的处理方法
    """
    
    def _show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self,
            "关于 TG-Manager",
            "<h3>TG-Manager</h3>"
            "<p>版本: 1.7.2</p>"
            "<p>一个功能强大的Telegram频道管理工具</p>"
            "<p>© 2023-2025 TG-Manager Team</p>"
        )
    
    def _pause_all_tasks(self):
        """暂停所有活动任务"""
        logger.info("暂停所有活动任务")
    
    def _resume_all_tasks(self):
        """恢复所有暂停的任务"""
        logger.info("恢复所有暂停的任务")
    
    def _pause_task(self, task_id):
        """暂停任务
        
        Args:
            task_id: 任务ID
        """
        logger.info(f"暂停任务: {task_id}")
        
        # 这里应该调用业务逻辑层的任务暂停方法
        # 示例代码：self.task_manager.pause_task(task_id)
        
        # 暂时使用任务概览组件更新状态
        if hasattr(self, 'task_overview') and self.task_overview:
            self.task_overview.update_task_status(task_id, "已暂停")
        
        # 更新任务视图
        if "task_manager" in self.opened_views:
            task_view = self.opened_views["task_manager"]
            if hasattr(task_view, 'tasks') and task_id in task_view.tasks:
                task_data = task_view.tasks[task_id]
                task_data['status'] = "已暂停"
                task_view.add_task(task_data)  # 更新任务状态
        
        # 刷新任务统计
        self._refresh_task_statistics()
    
    def _resume_task(self, task_id):
        """恢复任务
        
        Args:
            task_id: 任务ID
        """
        logger.info(f"恢复任务: {task_id}")
        
        # 这里应该调用业务逻辑层的任务恢复方法
        # 示例代码：self.task_manager.resume_task(task_id)
        
        # 暂时使用任务概览组件更新状态
        if hasattr(self, 'task_overview') and self.task_overview:
            self.task_overview.update_task_status(task_id, "运行中")
        
        # 更新任务视图
        if "task_manager" in self.opened_views:
            task_view = self.opened_views["task_manager"]
            if hasattr(task_view, 'tasks') and task_id in task_view.tasks:
                task_data = task_view.tasks[task_id]
                task_data['status'] = "运行中"
                task_view.add_task(task_data)  # 更新任务状态
        
        # 刷新任务统计
        self._refresh_task_statistics()
    
    def _cancel_task(self, task_id):
        """取消任务
        
        Args:
            task_id: 任务ID
        """
        logger.info(f"取消任务: {task_id}")
        
        # 确认取消
        reply = QMessageBox.question(
            self,
            "确认取消",
            f"确定要取消任务 {task_id} 吗？此操作无法撤销。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
            
        # 这里应该调用业务逻辑层的任务取消方法
        # 示例代码：self.task_manager.cancel_task(task_id)
        
        # 暂时使用任务概览组件更新状态
        if hasattr(self, 'task_overview') and self.task_overview:
            self.task_overview.update_task_status(task_id, "已取消")
            # 在短暂延迟后从概览中移除任务
            QTimer.singleShot(3000, lambda: self.task_overview.remove_task(task_id))
        
        # 更新任务视图
        if "task_manager" in self.opened_views:
            task_view = self.opened_views["task_manager"]
            if hasattr(task_view, 'tasks') and task_id in task_view.tasks:
                # 从任务管理器中移除任务
                task_view.remove_task(task_id)
        
        # 刷新任务统计
        self._refresh_task_statistics()
    
    def _remove_task(self, task_id):
        """从界面移除已完成的任务
        
        Args:
            task_id: 任务ID
        """
        logger.info(f"移除任务: {task_id}")
        
        # 暂时使用任务概览组件移除任务
        if hasattr(self, 'task_overview') and self.task_overview:
            self.task_overview.remove_task(task_id)
        
        # 更新任务视图
        if "task_manager" in self.opened_views:
            task_view = self.opened_views["task_manager"]
            if hasattr(task_view, 'tasks') and task_id in task_view.tasks:
                # 从任务管理器中移除任务
                task_view.remove_task(task_id)
        
        # 刷新任务统计
        self._refresh_task_statistics()
    
    def _handle_login(self):
        """处理用户登录"""
        try:
            # 创建登录表单对话框
            login_dialog = QDialog(self)
            login_dialog.setWindowTitle("登录Telegram")
            login_dialog.setMinimumWidth(400)
            
            # 创建布局
            main_layout = QVBoxLayout(login_dialog)
            
            # 添加说明标签
            info_label = QLabel("以下是您在设置中配置的Telegram API凭据和手机号码信息。点击'确定'开始登录。")
            info_label.setWordWrap(True)
            main_layout.addWidget(info_label)
            
            # 创建表单布局
            form_layout = QFormLayout()
            
            # 创建只读信息展示字段
            api_id_label = QLabel()
            api_hash_label = QLabel()
            phone_label = QLabel()
            
            # 从配置中加载API ID、Hash和手机号码（如果存在）
            if 'GENERAL' in self.config:
                if 'api_id' in self.config['GENERAL']:
                    api_id_label.setText(str(self.config['GENERAL']['api_id']))
                if 'api_hash' in self.config['GENERAL']:
                    # 只显示API Hash的一部分，保护隐私
                    api_hash = self.config['GENERAL']['api_hash']
                    masked_hash = api_hash[:6] + "..." + api_hash[-6:] if len(api_hash) > 12 else api_hash
                    api_hash_label.setText(masked_hash)
                if 'phone_number' in self.config['GENERAL'] and self.config['GENERAL']['phone_number']:
                    phone_label.setText(self.config['GENERAL']['phone_number'])
            
            # 添加表单字段
            form_layout.addRow("API ID:", api_id_label)
            form_layout.addRow("API Hash:", api_hash_label)
            form_layout.addRow("手机号码:", phone_label)
            
            # 创建按钮
            button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            button_box.accepted.connect(login_dialog.accept)
            button_box.rejected.connect(login_dialog.reject)
            
            # 组装布局
            main_layout.addLayout(form_layout)
            main_layout.addWidget(button_box)
            
            # 显示对话框
            result = login_dialog.exec_()
            
            # 如果用户点击了"确定"
            if result == QDialog.Accepted:
                # 检查配置中是否存在所需信息
                if 'GENERAL' not in self.config or 'api_id' not in self.config['GENERAL'] or \
                   'api_hash' not in self.config['GENERAL'] or 'phone_number' not in self.config['GENERAL'] or \
                   not self.config['GENERAL']['api_id'] or not self.config['GENERAL']['api_hash'] or \
                   not self.config['GENERAL']['phone_number']:
                    QMessageBox.warning(
                        self,
                        "配置不完整",
                        "请在设置中完成API凭据和手机号码的配置。",
                        QMessageBox.Ok
                    )
                    # 打开设置界面
                    self._open_settings()
                    return
                
                phone = self.config['GENERAL']['phone_number']
                
                # 显示登录进行中的消息
                self.statusBar().showMessage(f"登录中: {phone}")
                
                # 获取app实例和client_manager
                if not hasattr(self, 'app') or not hasattr(self.app, 'client_manager'):
                    QMessageBox.warning(
                        self,
                        "无法登录",
                        "客户端管理器未初始化，无法完成登录。",
                        QMessageBox.Ok
                    )
                    return
                
                # 创建异步任务执行登录过程
                # 提前导入需要的模块，避免在异步函数中导入
                from PySide6.QtCore import QMetaObject, Qt
                from PySide6.QtWidgets import QMessageBox
                
                async def login_process():
                    try:
                        # 导入需要的模块，确保在异步函数中可以使用
                        import asyncio
                        
                        # 发送验证码
                        await self.app.client_manager.send_code(phone)
                        
                        # 在主线程中显示验证码输入对话框
                        code_result = [None]  # 使用列表存储结果，以便在嵌套函数中修改
                        
                        # 改为使用Qt信号在主线程显示对话框，更可靠
                        from PySide6.QtCore import Signal, QTimer
                        
                        # 使用计时器在主线程中执行代码获取
                        def show_dialog_in_main_thread():
                            try:
                                result = self._show_verification_code_dialog()
                                code_result[0] = result
                                logger.debug(f"验证码输入结果: {result}")
                            except Exception as dialog_error:
                                logger.error(f"显示验证码对话框时出错: {dialog_error}")
                        
                        # 使用单次计时器在主线程中执行
                        timer = QTimer()
                        timer.setSingleShot(True)
                        timer.timeout.connect(show_dialog_in_main_thread)
                        timer.start(100)  # 100毫秒后执行
                        
                        # 等待用户输入验证码
                        max_wait_time = 180  # 最多等待3分钟
                        wait_time = 0
                        while code_result[0] is None and wait_time < max_wait_time:
                            await asyncio.sleep(0.5)
                            wait_time += 0.5
                        
                        code = code_result[0]
                        if not code:
                            self.statusBar().showMessage("登录已取消")
                            return
                        
                        # 使用验证码登录
                        user = await self.app.client_manager.sign_in(code)
                        
                        # 登录成功后更新状态栏
                        if user:
                            user_info = f"{user.first_name}"
                            if user.last_name:
                                user_info += f" {user.last_name}"
                            if user.username:
                                user_info += f" (@{user.username})"
                            
                            self.statusBar().showMessage(f"已登录: {user_info}", 5000)
                            
                            # 更新设置视图中的登录按钮
                            if "settings_view" in self.opened_views:
                                settings_view = self.opened_views["settings_view"]
                                if hasattr(settings_view, 'update_login_button'):
                                    settings_view.update_login_button(True, user_info)
                        else:
                            self.statusBar().showMessage("登录失败", 5000)
                    
                    except Exception as e:
                        logger.error(f"登录过程中出错: {e}")
                        # 在主线程中显示错误消息
                        error_msg = str(e)
                        self.statusBar().showMessage(f"登录错误: {error_msg}", 5000)
                        
                        # 使用计时器在主线程中显示错误对话框
                        def show_error_in_main_thread():
                            self._show_login_error(error_msg)
                            
                        QTimer.singleShot(100, show_error_in_main_thread)
                
                # 启动登录任务
                if hasattr(self.app, 'task_manager'):
                    self.app.task_manager.add_task("user_login", login_process())
                else:
                    import asyncio
                    asyncio.create_task(login_process())
        
        except Exception as e:
            logger.error(f"登录处理时出错: {e}")
            QMessageBox.critical(
                self,
                "登录错误",
                f"登录过程中发生错误: {str(e)}",
                QMessageBox.Ok
            )
            
    def _show_verification_code_dialog(self):
        """显示验证码输入对话框
        
        Returns:
            str: 用户输入的验证码，如果用户取消则返回None
        """
        try:
            # 创建验证码输入对话框
            code_dialog = QDialog(self)
            code_dialog.setWindowTitle("输入验证码")
            code_dialog.setMinimumWidth(350)
            
            # 创建布局
            layout = QVBoxLayout(code_dialog)
            
            # 添加说明标签
            info_label = QLabel("Telegram已向您的手机或Telegram应用发送了一个验证码，请在下方输入该验证码：")
            info_label.setWordWrap(True)
            layout.addWidget(info_label)
            
            # 创建验证码输入框 - Telegram现在使用5位或更长的验证码
            code_input = QLineEdit()
            code_input.setPlaceholderText("请输入验证码")
            code_input.setMaxLength(10)  # 允许更长的验证码
            
            # 设置输入验证 - 只允许输入数字
            validator = QRegularExpressionValidator(QRegularExpression("\\d+"))
            code_input.setValidator(validator)
            
            # 设置较大的字体
            font = code_input.font()
            font.setPointSize(font.pointSize() + 2)
            code_input.setFont(font)
            
            # 设置焦点
            code_input.setFocus()
            
            layout.addWidget(code_input)
            
            # 添加验证码提示
            hint_label = QLabel("提示: 验证码通常为5位数字，会发送到您的Telegram应用。\n如果未收到验证码，可能需要检查您绑定的Telegram是否可用。")
            hint_label.setStyleSheet("color: gray; font-size: 10pt;")
            hint_label.setWordWrap(True)
            layout.addWidget(hint_label)
            
            # 创建按钮
            button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            button_box.accepted.connect(code_dialog.accept)
            button_box.rejected.connect(code_dialog.reject)
            layout.addWidget(button_box)
            
            # 设置默认按钮
            ok_button = button_box.button(QDialogButtonBox.Ok)
            ok_button.setDefault(True)
            
            # 禁用OK按钮，直到输入了验证码
            ok_button.setEnabled(False)
            
            # 连接输入变化信号
            def on_text_changed(text):
                ok_button.setEnabled(len(text) > 0)
            
            code_input.textChanged.connect(on_text_changed)
            
            # 为输入框添加回车响应
            def handle_return_pressed():
                if ok_button.isEnabled():
                    code_dialog.accept()
                    
            code_input.returnPressed.connect(handle_return_pressed)
            
            # 显示对话框并置于最前
            code_dialog.setWindowFlags(code_dialog.windowFlags() | Qt.WindowStaysOnTopHint)
            result = code_dialog.exec_()
            
            if result == QDialog.Accepted:
                entered_code = code_input.text().strip()
                logger.info(f"用户输入了验证码（长度：{len(entered_code)}）")
                return entered_code
            else:
                logger.info("用户取消了验证码输入")
                return None
                
        except Exception as e:
            logger.error(f"显示验证码对话框时出错: {e}")
            return None
    
    def _show_login_error(self, error_msg):
        """显示登录错误对话框
        
        Args:
            error_msg: 错误信息
        """
        try:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                "登录错误",
                f"登录过程中出错: {error_msg}",
                QMessageBox.Ok
            )
            logger.debug(f"已显示登录错误对话框: {error_msg}")
        except Exception as e:
            logger.error(f"显示登录错误对话框时出错: {e}")
            
    def _open_settings(self):
        """打开设置界面"""
        logger.debug("尝试打开设置视图")
        try:
            # 先检查是否已经打开
            if "settings_view" in self.opened_views:
                logger.debug("设置视图已存在，切换到该视图")
                self.central_layout.setCurrentWidget(self.opened_views["settings_view"])
                return
            
            # 直接创建并显示设置视图
            from src.ui.views.settings_view import SettingsView
            
            # 创建设置视图
            settings_view = SettingsView(self.config, self)
            
            # 连接登录请求信号
            settings_view.login_requested.connect(self._handle_login)
            
            # 添加到中心区域
            self.central_layout.addWidget(settings_view)
            self.opened_views["settings_view"] = settings_view
            
            # 设置当前客户端状态
            if hasattr(self, 'app') and hasattr(self.app, 'client_manager'):
                is_connected = self.app.client_manager.is_authorized
                user_info = None
                if is_connected and self.app.client_manager.me:
                    user_obj = self.app.client_manager.me
                    user_info = f"{user_obj.first_name}"
                    if user_obj.last_name:
                        user_info += f" {user_obj.last_name}"
                    if user_obj.username:
                        user_info += f" (@{user_obj.username})"
                
                logger.debug(f"更新设置视图登录按钮状态: 已连接={is_connected}, 用户信息={user_info}")
                settings_view.update_login_button(is_connected, user_info)
            else:
                logger.debug("无法获取客户端状态，未更新登录按钮")
            
            # 切换到设置视图
            self.central_layout.setCurrentWidget(settings_view)
            
            # 连接设置视图的信号
            if hasattr(settings_view, 'settings_saved'):
                settings_view.settings_saved.connect(self._on_settings_saved)
            
            logger.info("成功打开设置视图")
            
        except Exception as e:
            logger.error(f"打开设置视图失败: {e}", exc_info=True)
            QMessageBox.warning(
                self,
                "模块加载失败",
                f"无法加载设置模块。\n错误: {str(e)}",
                QMessageBox.Ok
            )
    
    def _open_task_manager(self):
        """打开任务管理器"""
        logger.debug("尝试打开任务管理器视图")
        try:
            # 先检查是否已经打开
            if "task_manager" in self.opened_views:
                logger.debug("任务管理器视图已存在，切换到该视图")
                self.central_layout.setCurrentWidget(self.opened_views["task_manager"])
                return
                
            # 通过导航树API找到任务管理项并触发点击
            logger.debug("尝试通过导航树打开任务管理器视图")
            if self.nav_tree.select_item_by_function("task_manager"):
                logger.debug("通过导航树成功打开任务管理器视图")
                return
                
            # 如果通过导航树无法打开，直接创建并显示
            logger.debug("直接创建任务管理器视图")
            from src.ui.views.task_view import TaskView
            
            # 创建任务管理器视图
            task_manager = TaskView(self.config, self)
            
            # 添加到中心区域
            self.central_layout.addWidget(task_manager)
            self.opened_views["task_manager"] = task_manager
            
            # 使任务管理器可见
            self.central_layout.setCurrentWidget(task_manager)
            
            # 连接任务管理器的信号
            if hasattr(task_manager, 'task_pause'):
                task_manager.task_pause.connect(self._pause_task)
            if hasattr(task_manager, 'task_resume'):
                task_manager.task_resume.connect(self._resume_task)
            if hasattr(task_manager, 'task_cancel'):
                task_manager.task_cancel.connect(self._cancel_task)
            if hasattr(task_manager, 'task_remove'):
                task_manager.task_remove.connect(self._remove_task)
            if hasattr(task_manager, 'tasks_updated'):
                task_manager.tasks_updated.connect(self._update_task_statistics)
            
            logger.info("成功打开任务管理器视图")
            
        except Exception as e:
            logger.error(f"打开任务管理器视图失败: {e}", exc_info=True)
            QMessageBox.warning(
                self,
                "模块加载失败",
                f"无法加载任务管理器模块。\n错误: {str(e)}",
                QMessageBox.Ok
            )
    
    def _open_log_viewer(self):
        """打开日志查看器"""
        logger.debug("尝试打开日志查看器视图")
        try:
            # 先检查是否已经打开
            if "log_viewer" in self.opened_views:
                logger.debug("日志查看器视图已存在，切换到该视图")
                self.central_layout.setCurrentWidget(self.opened_views["log_viewer"])
                return
                
            # 通过导航树API找到日志查看器项并触发点击
            logger.debug("尝试通过导航树打开日志查看器视图")
            if self.nav_tree.select_item_by_function("logs") or self.nav_tree.select_item("log_viewer"):
                logger.debug("通过导航树成功打开日志查看器视图")
                return
            
            # 如果通过导航树无法打开，直接创建并显示
            logger.debug("直接创建日志查看器视图")
            from src.ui.views.log_viewer_view import LogViewerView
            
            # 创建日志查看器视图
            log_viewer = LogViewerView(self.config, self)
            
            # 添加到中心区域
            self.central_layout.addWidget(log_viewer)
            self.opened_views["log_viewer"] = log_viewer
            
            # 使日志查看器可见
            self.central_layout.setCurrentWidget(log_viewer)
            
            logger.info("成功打开日志查看器视图")
            
        except Exception as e:
            logger.error(f"打开日志查看器视图失败: {e}", exc_info=True)
            QMessageBox.warning(
                self,
                "模块加载失败",
                f"无法加载日志查看器模块。\n错误: {str(e)}",
                QMessageBox.Ok
            )
    
    def _show_help_doc(self):
        """显示帮助文档"""
        try:
            # 通过导航树API找到帮助文档项并触发点击
            for item_id in ["help_doc", "documentation", "docs"]:
                if hasattr(self.nav_tree, 'select_item') and self.nav_tree.select_item(item_id):
                    return
            
            # 如果导航树中没有找到，直接创建并显示
            from src.ui.views.help_doc_view import HelpDocView
            
            # 创建帮助文档视图
            help_doc = HelpDocView(self.config, self)
            
            # 添加到中心区域
            self.central_layout.addWidget(help_doc)
            self.opened_views["help_doc"] = help_doc
            
            # 使帮助文档可见
            self.central_layout.setCurrentWidget(help_doc)
            
        except ImportError as e:
            logger.error(f"导入帮助文档视图失败: {e}")
            QMessageBox.warning(
                self,
                "模块加载失败",
                f"无法加载帮助文档模块。\n错误: {str(e)}",
                QMessageBox.Ok
            )
    
    def _check_update(self):
        """检查更新"""
        QMessageBox.information(
            self,
            "检查更新",
            "检查更新功能尚未实现。\n当前版本: 1.7.1",
            QMessageBox.Ok
        )
    
    def _close_settings_view(self):
        """关闭设置视图并返回到之前的视图"""
        # 找到设置视图并移除
        for view_id, view in list(self.opened_views.items()):
            if hasattr(view, 'settings_saved'):  # 检查是否是设置视图
                # 从栈布局中移除
                self.central_layout.removeWidget(view)
                # 从已打开视图中移除
                self.opened_views.pop(view_id, None)
                # 返回到欢迎视图
                self.central_layout.setCurrentWidget(self.welcome_widget)
                # 记录日志
                logger.debug(f"已关闭设置视图: {view_id}")
                break 

    def _on_settings_saved(self):
        """设置保存后的处理"""
        # 从设置视图移除焦点
        pass

    def _open_function_view(self, function_name):
        """从功能菜单打开对应的功能视图
        
        Args:
            function_name: 功能名称，如'download', 'upload', 'forward', 'monitor'
        """
        logger.debug(f"从功能菜单打开视图: {function_name}")
        
        try:
            # 检查应用程序是否正在初始化
            if hasattr(self, 'app') and hasattr(self.app, 'is_initializing') and self.app.is_initializing:
                self.show_status_message("系统正在初始化中，请稍等...", 3000)
                logger.warning(f"用户尝试在初始化完成前访问功能: {function_name}")
                return
            
            # 使用导航树的方法来选择并打开对应的功能
            if hasattr(self, 'nav_tree') and self.nav_tree:
                # 先尝试通过导航树API打开功能
                if self.nav_tree.select_item_by_function(function_name):
                    logger.debug(f"通过导航树成功打开 {function_name} 视图")
                    return
            
            # 如果导航树方法失败，直接处理各种功能
            if function_name == "download":
                self._direct_open_view("download", "普通下载")
            elif function_name == "upload":
                self._direct_open_view("upload", "本地上传")
            elif function_name == "forward":
                self._direct_open_view("forward", "历史转发")
            elif function_name == "monitor":
                self._direct_open_view("monitor", "实时监听")
            else:
                logger.warning(f"未知的功能名称: {function_name}")
                QMessageBox.information(
                    self,
                    "功能未实现",
                    f"功能 '{function_name}' 尚未实现。",
                    QMessageBox.Ok
                )
                
        except Exception as e:
            logger.error(f"打开功能视图失败: {function_name}, 错误: {e}")
            QMessageBox.warning(
                self,
                "打开视图失败",
                f"无法打开 '{function_name}' 视图。\n错误: {str(e)}",
                QMessageBox.Ok
            )
    
    def _direct_open_view(self, function_name, display_name):
        """直接打开指定功能的视图
        
        Args:
            function_name: 功能名称
            display_name: 显示名称
        """
        try:
            # 生成一个唯一的视图ID
            view_id = f"menu_{function_name}"
            
            # 检查视图是否已经存在
            if view_id in self.opened_views:
                self.central_layout.setCurrentWidget(self.opened_views[view_id])
                logger.debug(f"{display_name}视图已存在，切换到该视图")
                return
            
            # 创建对应的视图
            view = None
            if function_name == 'download':
                from src.ui.views.download_view import DownloadView
                view = DownloadView(self.config)
                
            elif function_name == 'upload':
                from src.ui.views.upload_view import UploadView
                view = UploadView(self.config)
                
            elif function_name == 'forward':
                from src.ui.views.forward_view import ForwardView
                view = ForwardView(self.config)
                
            elif function_name == 'monitor':
                from src.ui.views.listen_view import ListenView
                view = ListenView(self.config)
            
            if view:
                # 连接视图的配置保存信号
                if hasattr(view, 'config_saved'):
                    view.config_saved.connect(self.config_saved)
                
                # 连接任务相关信号（如适用）
                if function_name in ['download', 'upload', 'forward'] and hasattr(view, 'tasks_updated'):
                    view.tasks_updated.connect(self._update_task_statistics)
                    logger.debug(f"已连接 {function_name} 视图的任务统计信号")
                
                # 添加视图到中心区域并记录
                self.central_layout.addWidget(view)
                self.opened_views[view_id] = view
                
                # 使新添加的视图可见
                self.central_layout.setCurrentWidget(view)
                
                # 连接功能模块
                if hasattr(self, '_connect_view_to_modules'):
                    self._connect_view_to_modules(function_name, view)
                
                logger.info(f"成功打开{display_name}视图")
            else:
                logger.error(f"无法创建{display_name}视图")
                
        except ImportError as e:
            logger.error(f"导入{display_name}视图失败: {e}")
            QMessageBox.warning(
                self,
                "模块加载失败",
                f"无法加载 '{display_name}' 模块。\n错误: {str(e)}",
                QMessageBox.Ok
            )

    def get_view(self, view_name):
        """获取指定名称的视图组件
        
        Args:
            view_name: 视图名称，可选值: 'download', 'upload', 'forward', 'listen', 'task', 'log', 'help'
            
        Returns:
            视图组件实例，如果不存在则返回None
        """
        # 映射视图名称到 opened_views 中的键
        view_id_map = {
            'download': 'function.download',
            'upload': 'function.upload',
            'forward': 'function.forward',
            'listen': 'function.monitor',
            'task': 'function.task_manager',
            'log': 'function.logs',
            'help': 'function.help',
            'settings': 'settings_view',
            'qt_asyncio_test': 'function.qt_asyncio_test'
        }
        
        view_id = view_id_map.get(view_name)
        if view_id and view_id in self.opened_views:
            return self.opened_views[view_id]
            
        # 如果视图尚未打开，返回None
        logger.debug(f"视图 '{view_name}' 尚未打开，无法获取引用")
        return None 