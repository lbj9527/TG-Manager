"""
TG-Manager 主窗口功能操作模块
包含各种菜单和按钮的处理函数
"""

import json
import datetime
from copy import deepcopy
from loguru import logger
from PySide6.QtWidgets import (
    QMessageBox, QInputDialog, QDialog, QVBoxLayout, 
    QFormLayout, QLineEdit, QDialogButtonBox, QLabel,
    QFileDialog
)
from PySide6.QtCore import QRegularExpression, QTimer
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
                
                # 显示验证码输入对话框
                code = self._show_verification_code_dialog()
                
                if code:
                    # 显示登录成功消息，这里只是界面展示，实际登录逻辑后续实现
                    QMessageBox.information(
                        self,
                        "验证码已提交",
                        f"已接收验证码: {code}\n\n实际登录功能将在后续实现。",
                        QMessageBox.Ok
                    )
                else:
                    self.statusBar().showMessage("登录已取消")
                
                # 这里可以添加实际的登录逻辑
                # ...
                
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
            
            # 创建验证码输入框
            code_input = QLineEdit()
            code_input.setPlaceholderText("请输入验证码")
            code_input.setMaxLength(5)  # 验证码通常为5位数字
            
            # 设置输入验证 - 只允许输入数字
            validator = QRegularExpressionValidator(QRegularExpression("\\d+"))
            code_input.setValidator(validator)
            
            layout.addWidget(code_input)
            
            # 添加验证码提示
            hint_label = QLabel("提示: 验证码通常为5位数字，请检查您的Telegram应用或手机短信。")
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
            
            # 显示对话框
            result = code_dialog.exec_()
            
            if result == QDialog.Accepted:
                return code_input.text()
            else:
                return None
                
        except Exception as e:
            logger.error(f"显示验证码对话框时出错: {e}")
            return None
    
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
            
            # 添加到中心区域
            self.central_layout.addWidget(settings_view)
            self.opened_views["settings_view"] = settings_view
            
            # 使设置视图可见
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
    
    def _import_config(self):
        """导入配置文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "导入配置文件",
            "",
            "JSON文件 (*.json);;所有文件 (*.*)"
        )
        
        if not file_path:
            return
            
        try:
            # 读取配置文件
            with open(file_path, 'r', encoding='utf-8') as file:
                imported_config = json.load(file)
            
            # 验证导入的配置文件结构
            if not isinstance(imported_config, dict):
                raise ValueError("导入的配置文件格式无效，应为JSON对象")
            
            # 提示用户确认
            reply = QMessageBox.question(
                self,
                "确认导入",
                "导入此配置文件将覆盖当前配置，是否继续？\n"
                "注意：某些设置可能需要重启应用才能生效。",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply != QMessageBox.Yes:
                return
            
            # 合并配置
            self.config.update(imported_config)
            
            # 发出配置更新信号
            self.config_saved.emit(self.config)
            
            # 显示成功消息
            QMessageBox.information(
                self,
                "导入成功",
                "配置文件已成功导入。\n"
                "某些设置可能需要重启应用才能生效。",
                QMessageBox.Ok
            )
            
        except Exception as e:
            logger.error(f"导入配置文件失败: {e}")
            QMessageBox.critical(
                self,
                "导入失败",
                f"导入配置文件失败: {str(e)}",
                QMessageBox.Ok
            )
    
    def _export_config(self):
        """导出配置文件"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "导出配置文件",
            f"tg_manager_config_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON文件 (*.json);;所有文件 (*.*)"
        )
        
        if not file_path:
            return
            
        try:
            # 创建配置的副本，去除可能无法序列化的内容
            config_copy = deepcopy(self.config)
            
            # 写入配置文件，美化格式
            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump(config_copy, file, ensure_ascii=False, indent=4)
            
            # 显示成功消息
            QMessageBox.information(
                self,
                "导出成功",
                f"配置文件已成功导出到:\n{file_path}",
                QMessageBox.Ok
            )
            
        except Exception as e:
            logger.error(f"导出配置文件失败: {e}")
            QMessageBox.critical(
                self,
                "导出失败",
                f"导出配置文件失败: {str(e)}",
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
        """处理设置保存信号"""
        # 显示状态消息
        self.statusBar().showMessage("设置已保存", 3000)
        # 不需要关闭设置视图，保持在当前页面 

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