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

from src.utils.logger import get_logger
from src.utils.translation_manager import get_translation_manager, tr

logger = get_logger()

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
        
        # 任务概览已移除，不再需要更新状态
        
        # 任务视图已删除，无需更新任务状态
        
        # 任务统计功能已移除，无需刷新
    
    def _resume_task(self, task_id):
        """恢复任务
        
        Args:
            task_id: 任务ID
        """
        logger.info(f"恢复任务: {task_id}")
        
        # 这里应该调用业务逻辑层的任务恢复方法
        # 示例代码：self.task_manager.resume_task(task_id)
        
        # 任务概览已移除，不再需要更新状态
        
        # 任务视图已删除，无需更新任务状态
        
        # 任务统计功能已移除，无需刷新
    
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
        
        # 任务概览已移除，不再需要更新状态
        
        # 任务视图已删除，无需更新任务状态
        
        # 任务统计功能已移除，无需刷新
    
    def _remove_task(self, task_id):
        """从界面移除已完成的任务
        
        Args:
            task_id: 任务ID
        """
        logger.info(f"移除任务: {task_id}")
        
        # 任务概览已移除，不再需要移除任务
        
        # 任务视图已删除，无需更新任务状态
        
        # 任务统计功能已移除，无需刷新
    
    def _handle_login(self):
        """处理用户登录"""
        try:
            # 创建登录表单对话框
            login_dialog = QDialog(self)
            login_dialog.setWindowTitle(tr("ui.login.dialog.title"))
            login_dialog.setMinimumWidth(400)
            
            # 创建布局
            main_layout = QVBoxLayout(login_dialog)
            
            # 添加说明标签
            info_label = QLabel(tr("ui.login.dialog.info"))
            info_label.setWordWrap(True)
            main_layout.addWidget(info_label)
            
            # 创建表单布局
            form_layout = QFormLayout()
            
            # 创建只读信息展示字段
            api_id_label = QLabel()
            api_hash_label = QLabel()
            phone_label = QLabel()
            
            # 从最新配置中加载API ID、Hash和手机号码（如果存在）
            try:
                # 从UI配置管理器获取最新配置
                ui_config = self.app.ui_config_manager.get_ui_config()
                from src.utils.config_utils import convert_ui_config_to_dict
                latest_config = convert_ui_config_to_dict(ui_config)
                
                if 'GENERAL' in latest_config:
                    if 'api_id' in latest_config['GENERAL']:
                        api_id_label.setText(str(latest_config['GENERAL']['api_id']))
                    if 'api_hash' in latest_config['GENERAL']:
                        # 只显示API Hash的一部分，保护隐私
                        api_hash = latest_config['GENERAL']['api_hash']
                        masked_hash = api_hash[:6] + "..." + api_hash[-6:] if len(api_hash) > 12 else api_hash
                        api_hash_label.setText(masked_hash)
                    if 'phone_number' in latest_config['GENERAL'] and latest_config['GENERAL']['phone_number']:
                        phone_label.setText(latest_config['GENERAL']['phone_number'])
            except Exception as config_error:
                logger.error(f"加载最新配置显示失败: {config_error}")
                # 如果加载最新配置失败，使用当前配置
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
            form_layout.addRow(tr("ui.login.dialog.api_id"), api_id_label)
            form_layout.addRow(tr("ui.login.dialog.api_hash"), api_hash_label)
            form_layout.addRow(tr("ui.login.dialog.phone_number"), phone_label)
            
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
                # 重新加载最新配置，确保使用最新的API凭据
                logger.info("登录前重新加载最新配置")
                try:
                    # 从UI配置管理器获取最新配置
                    ui_config = self.app.ui_config_manager.get_ui_config()
                    from src.utils.config_utils import convert_ui_config_to_dict
                    latest_config = convert_ui_config_to_dict(ui_config)
                    
                    # 检查最新配置中是否存在所需信息
                    if 'GENERAL' not in latest_config or 'api_id' not in latest_config['GENERAL'] or \
                       'api_hash' not in latest_config['GENERAL'] or 'phone_number' not in latest_config['GENERAL'] or \
                       not latest_config['GENERAL']['api_id'] or not latest_config['GENERAL']['api_hash'] or \
                       not latest_config['GENERAL']['phone_number']:
                        QMessageBox.warning(
                            self,
                            tr("ui.login.errors.incomplete_config_title"),
                            tr("ui.login.errors.incomplete_config_msg"),
                            QMessageBox.Ok
                        )
                        # 打开设置界面
                        self._open_settings()
                        return
                    
                    phone = latest_config['GENERAL']['phone_number']
                    logger.info(f"使用最新配置中的电话号码: {phone[:4]}****{phone[-2:]}")
                    
                except Exception as config_error:
                    logger.error(f"重新加载配置失败: {config_error}")
                    # 如果重新加载失败，使用当前配置
                    if 'GENERAL' not in self.config or 'api_id' not in self.config['GENERAL'] or \
                       'api_hash' not in self.config['GENERAL'] or 'phone_number' not in self.config['GENERAL'] or \
                       not self.config['GENERAL']['api_id'] or not self.config['GENERAL']['api_hash'] or \
                       not self.config['GENERAL']['phone_number']:
                        QMessageBox.warning(
                            self,
                            tr("ui.login.errors.incomplete_config_title"),
                            tr("ui.login.errors.incomplete_config_msg"),
                            QMessageBox.Ok
                        )
                        # 打开设置界面
                        self._open_settings()
                        return
                    
                    phone = self.config['GENERAL']['phone_number']
                
                # 显示登录进行中的消息
                self.statusBar().showMessage(tr("ui.login.status.logging_in").format(phone=phone))
                
                # 获取app实例和client_manager
                if not hasattr(self, 'app') or not hasattr(self.app, 'client_manager'):
                    QMessageBox.warning(
                        self,
                        tr("ui.login.errors.login_failed_title"),
                        tr("ui.login.errors.login_failed_msg"),
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
                            self.statusBar().showMessage(tr("ui.login.status.cancelled"))
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
                            
                            self.statusBar().showMessage(tr("ui.login.status.logged_in").format(user=user_info), 5000)
                            
                            # 更新设置视图中的登录按钮
                            if "settings_view" in self.opened_views:
                                settings_view = self.opened_views["settings_view"]
                                if hasattr(settings_view, 'update_login_button'):
                                    settings_view.update_login_button(True, user_info)
                        else:
                            self.statusBar().showMessage(tr("ui.login.status.failed"), 5000)
                    
                    except Exception as e:
                        logger.error(f"登录过程中出错: {e}")
                        # 在主线程中显示错误消息
                        error_msg = str(e)
                        self.statusBar().showMessage(tr("ui.login.status.error").format(error=error_msg), 5000)
                
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
                tr("ui.login.errors.login_error_title"),
                tr("ui.login.errors.login_error_msg").format(error=str(e)),
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
            code_dialog.setWindowTitle(tr("ui.login.verification.title"))
            code_dialog.setMinimumWidth(350)
            
            # 创建布局
            layout = QVBoxLayout(code_dialog)
            
            # 添加说明标签
            info_label = QLabel(tr("ui.login.verification.info"))
            info_label.setWordWrap(True)
            layout.addWidget(info_label)
            
            # 创建验证码输入框 - Telegram现在使用5位或更长的验证码
            code_input = QLineEdit()
            code_input.setPlaceholderText(tr("ui.login.verification.placeholder"))
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
            hint_label = QLabel(tr("ui.login.verification.hint"))
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
                tr("ui.login.errors.login_error_title"),
                tr("ui.login.errors.login_error_msg").format(error=error_msg),
                QMessageBox.Ok
            )
            logger.debug(f"已显示登录错误对话框: {error_msg}")
        except Exception as e:
            logger.error(f"显示登录错误对话框时出错: {e}")
            
    def _open_settings(self):
        """打开设置界面"""

        try:
            # 先检查是否已经打开
            if "settings_view" in self.opened_views:

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
                tr("ui.login.errors.module_load_failed_title"),
                tr("ui.login.errors.module_load_failed_msg").format(error=str(e)),
                QMessageBox.Ok
            )
    

    
    def _open_log_viewer(self):
        """打开日志查看器"""

        try:
            # 【修复】先检查自动加载的日志查看器是否已经存在
            if "log_viewer" in self.opened_views:

                self.central_layout.setCurrentWidget(self.opened_views["log_viewer"])
                return
                
            # 检查通过导航树加载的日志查看器是否已经存在
            if "function.logs" in self.opened_views:

                self.central_layout.setCurrentWidget(self.opened_views["function.logs"])
                return
                
            # 通过导航树API找到日志查看器项并触发点击
            
            if self.nav_tree.select_item_by_function("logs") or self.nav_tree.select_item("log_viewer"):

                return
            
            # 如果通过导航树无法打开，直接创建并显示
            
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
                
                # 任务统计功能已移除，无需连接相关信号
                
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
            'settings': 'settings_view'
            # QtAsyncio测试已移除
        }
        
        view_id = view_id_map.get(view_name)
        if view_id and view_id in self.opened_views:
            return self.opened_views[view_id]
            
        # 【修复】特殊处理日志查看器，支持自动加载的"log_viewer"键
        if view_name == 'log' and 'log_viewer' in self.opened_views:
            return self.opened_views['log_viewer']
            
        # 如果视图尚未打开，返回None

        return None 