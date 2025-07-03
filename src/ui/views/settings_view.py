"""
TG-Manager 设置界面
实现应用程序配置管理
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QCheckBox, QPushButton,
    QGroupBox, QScrollArea, QSpinBox, QTabWidget,
    QComboBox, QFileDialog, QMessageBox,
    QSizePolicy
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer
import json

from src.utils.logger import get_logger
from src.utils.theme_manager import get_theme_manager
from src.utils.ui_config_models import ProxyType

logger = get_logger()


class SettingsView(QWidget):
    """设置界面，提供应用程序配置管理"""
    
    # 设置保存信号
    settings_saved = Signal(dict)  # 带参数的信号
    settings_cancelled = Signal()  # 设置取消信号
    login_requested = Signal()     # 添加登录请求信号
    
    def __init__(self, config=None, parent=None):
        """初始化设置界面
        
        Args:
            config: 配置对象
            parent: 父窗口部件
        """
        super().__init__(parent)
        
        self.config = config or {}
        
        # 获取主题管理器
        self.theme_manager = get_theme_manager()
        
        # 添加临时主题存储
        self.original_theme = self.theme_manager.get_current_theme_name()
        self.temp_theme = self.original_theme
        
        # 跟踪设置是否已更改
        self.settings_changed = False
        
        # 设置布局
        self.main_layout = QVBoxLayout(self)
        self.setLayout(self.main_layout)
        
        # 创建设置选项卡
        self._create_settings_tabs()
        
        # 创建底部按钮
        self._create_buttons()
        
        # 连接信号
        self._connect_signals()
        
        # 如果父窗口有config_saved方法，连接信号
        if parent and hasattr(parent, 'config_saved'):
            logger.debug("将设置视图的config_saved信号连接到父窗口")
            self.settings_saved.connect(parent.config_saved)
        
        # 检查父窗口是否有app属性，并且app有client_manager，如果有就更新登录按钮状态
        if parent and hasattr(parent, 'app') and hasattr(parent.app, 'client_manager'):
            client_manager = parent.app.client_manager
            if hasattr(client_manager, 'is_authorized') and hasattr(client_manager, 'me'):
                is_logged_in = client_manager.is_authorized
                user_info = None
                if is_logged_in and client_manager.me:
                    user_obj = client_manager.me
                    user_info = f"{user_obj.first_name}"
                    if user_obj.last_name:
                        user_info += f" {user_obj.last_name}"
                    if user_obj.username:
                        user_info += f" (@{user_obj.username})"
                
                # 在界面完全创建后更新登录按钮状态
                QTimer.singleShot(100, lambda: self.update_login_button(is_logged_in, user_info))
                logger.debug(f"设置界面初始化时检测到登录状态: {is_logged_in}, 用户: {user_info}")
        
        # 加载配置
        if self.config:
            self.load_config(self.config)
        
        # 初始状态下禁用保存按钮
        self.save_button.setEnabled(False)
        
        logger.info("设置界面初始化完成")
    
    def _create_settings_tabs(self):
        """创建设置选项卡"""
        self.settings_tabs = QTabWidget()
        
        # 创建API设置选项卡
        self.api_tab = self._create_api_tab()
        self.settings_tabs.addTab(self.api_tab, "API设置")
        
        # 创建代理设置选项卡
        self.proxy_tab = self._create_proxy_tab()
        self.settings_tabs.addTab(self.proxy_tab, "网络代理")
        
        # 创建界面设置选项卡
        self.ui_tab = self._create_ui_tab()
        self.settings_tabs.addTab(self.ui_tab, "界面")
        
        # 添加到主布局
        self.main_layout.addWidget(self.settings_tabs)
    
    def _create_api_tab(self):
        """创建API设置选项卡
        
        Returns:
            QWidget: API设置面板
        """
        api_widget = QWidget()
        api_layout = QVBoxLayout(api_widget)
        
        # 创建Telegram API设置组
        telegram_group = QGroupBox("Telegram API设置")
        telegram_layout = QFormLayout()
        
        self.api_id = QLineEdit()
        telegram_layout.addRow("API ID:", self.api_id)
        
        self.api_hash = QLineEdit()
        telegram_layout.addRow("API Hash:", self.api_hash)
        
        self.phone_number = QLineEdit()
        telegram_layout.addRow("手机号码:", self.phone_number)
        
        # 添加登录按钮
        self.login_button = QPushButton("登录")
        self.login_button.setMinimumWidth(120)
        self.login_button.clicked.connect(self._handle_login)
        # 设置默认颜色，添加无边框样式
        self.login_button.setStyleSheet("background-color: #2196F3; color: white; border: none; border-radius: 3px;")
        telegram_layout.addRow("", self.login_button)
        
        # 添加登录提示标签
        login_tip = QLabel(
            "请填写您的Telegram API ID、API Hash和手机号码后点击登录按钮。\n"
            "如未申请API凭据，请访问 <a href='https://my.telegram.org'>https://my.telegram.org</a> 申请。\n"
            "手机号码格式应为国际格式，例如：+86 12345678901"
        )
        login_tip.setWordWrap(True)
        login_tip.setTextFormat(Qt.RichText)
        login_tip.setOpenExternalLinks(True)
        login_tip.setStyleSheet("font-size: 9pt;")
        telegram_layout.addRow("", login_tip)
        
        telegram_group.setLayout(telegram_layout)
        api_layout.addWidget(telegram_group)
        
        # 创建会话设置组
        session_group = QGroupBox("会话设置")
        session_layout = QFormLayout()
        
        self.session_name = QLineEdit("tg_manager_session")
        session_layout.addRow("会话名称:", self.session_name)
        
        self.auto_restart_session = QCheckBox("连接断开后自动重连")
        self.auto_restart_session.setChecked(True)
        session_layout.addRow("", self.auto_restart_session)
        
        session_group.setLayout(session_layout)
        api_layout.addWidget(session_group)
        
        # 添加伸展以填充空白区域
        api_layout.addStretch()
        
        return api_widget
    
    def _create_proxy_tab(self):
        """创建代理设置选项卡
        
        Returns:
            QWidget: 代理设置面板
        """
        proxy_widget = QWidget()
        proxy_layout = QVBoxLayout(proxy_widget)
        
        # 创建代理设置组
        proxy_group = QGroupBox("代理设置")
        proxy_form = QFormLayout()
        
        self.use_proxy = QCheckBox("使用代理")
        proxy_form.addRow("", self.use_proxy)
        
        self.proxy_type = QComboBox()
        self.proxy_type.addItems(["SOCKS5"])
        self.proxy_type.setEnabled(False)
        proxy_form.addRow("代理类型:", self.proxy_type)
        
        self.proxy_host = QLineEdit()
        self.proxy_host.setEnabled(False)
        proxy_form.addRow("代理主机:", self.proxy_host)
        
        self.proxy_port = QSpinBox()
        self.proxy_port.setRange(1, 65535)
        self.proxy_port.setValue(1080)
        self.proxy_port.setEnabled(False)
        proxy_form.addRow("代理端口:", self.proxy_port)
        
        self.proxy_username = QLineEdit()
        self.proxy_username.setEnabled(False)
        proxy_form.addRow("用户名(可选):", self.proxy_username)
        
        self.proxy_password = QLineEdit()
        self.proxy_password.setEchoMode(QLineEdit.Password)
        self.proxy_password.setEnabled(False)
        proxy_form.addRow("密码(可选):", self.proxy_password)
        
        # 连接复选框状态和代理设置输入框
        self.use_proxy.toggled.connect(self.proxy_type.setEnabled)
        self.use_proxy.toggled.connect(self.proxy_host.setEnabled)
        self.use_proxy.toggled.connect(self.proxy_port.setEnabled)
        self.use_proxy.toggled.connect(self.proxy_username.setEnabled)
        self.use_proxy.toggled.connect(self.proxy_password.setEnabled)
        
        proxy_group.setLayout(proxy_form)
        proxy_layout.addWidget(proxy_group)
        
        # 添加伸展以填充空白区域
        proxy_layout.addStretch()
        
        return proxy_widget
    
    def _create_ui_tab(self):
        """创建界面设置选项卡
        
        Returns:
            QWidget: 界面设置面板
        """
        ui_widget = QWidget()
        ui_layout = QVBoxLayout(ui_widget)
        
        # 创建主题设置组
        theme_group = QGroupBox("主题设置")
        theme_layout = QFormLayout()
        
        # 主题选择部分
        self.theme_selector = QComboBox()
        # 从主题管理器获取可用主题列表
        self.theme_selector.addItems(self.theme_manager.get_available_themes())
        self.theme_selector.setCurrentText(self.theme_manager.get_current_theme_name())
        self.theme_selector.setToolTip("选择应用程序主题，更改后立即生效")
        # 连接主题变更信号
        self.theme_selector.currentTextChanged.connect(self._on_theme_changed)
        
        theme_layout.addRow("应用主题:", self.theme_selector)
        
        # 语言选择部分
        self.language_selector = QComboBox()
        # 添加支持的语言选项
        self.language_selector.addItems(["中文", "English", "Español", "Français", "Deutsch", "Русский", "日本語", "한국어"])
        self.language_selector.setCurrentText("中文")  # 默认选中中文
        self.language_selector.setToolTip("选择应用程序界面语言，重启应用后生效")
        # 连接语言变更信号
        self.language_selector.currentTextChanged.connect(self._on_setting_changed)
        
        theme_layout.addRow("界面语言:", self.language_selector)
        
        theme_group.setLayout(theme_layout)
        ui_layout.addWidget(theme_group)
        
        # 创建行为设置组
        behavior_group = QGroupBox("行为设置")
        behavior_layout = QFormLayout()
        
        self.confirm_exit = QCheckBox("退出前确认")
        self.confirm_exit.setChecked(True)
        behavior_layout.addRow("", self.confirm_exit)
        
        self.minimize_to_tray = QCheckBox("最小化到系统托盘")
        self.minimize_to_tray.setChecked(True)
        behavior_layout.addRow("", self.minimize_to_tray)
        
        self.start_minimized = QCheckBox("启动时最小化")
        # 默认不选中
        self.start_minimized.setChecked(False)
        # 添加提示说明
        self.start_minimized.setToolTip("启用后程序启动时将自动最小化到系统托盘，需要同时启用'最小化到系统托盘'选项")
        behavior_layout.addRow("", self.start_minimized)
        
        behavior_group.setLayout(behavior_layout)
        ui_layout.addWidget(behavior_group)
        
        # 创建通知设置组
        notification_group = QGroupBox("通知设置")
        notification_layout = QFormLayout()
        
        self.enable_notifications = QCheckBox("启用桌面通知")
        self.enable_notifications.setChecked(True)
        notification_layout.addRow("", self.enable_notifications)
        
        self.notification_sound = QCheckBox("通知声音")
        self.notification_sound.setChecked(True)
        notification_layout.addRow("", self.notification_sound)
        
        notification_group.setLayout(notification_layout)
        ui_layout.addWidget(notification_group)
        
        # 添加伸展以填充空白区域
        ui_layout.addStretch()
        
        return ui_widget
    
    def _create_buttons(self):
        """创建底部按钮"""
        button_layout = QHBoxLayout()
        
        self.reset_button = QPushButton("重置为默认")
        self.save_button = QPushButton("保存设置")
        
        button_layout.addWidget(self.save_button)
        button_layout.addStretch()
        button_layout.addWidget(self.reset_button)
        
        self.main_layout.addLayout(button_layout)
    
    def _connect_signals(self):
        """连接信号和槽"""
        # 底部按钮
        self.save_button.clicked.connect(self._save_settings)
        self.reset_button.clicked.connect(self._reset_settings)
        
        # 连接各个控件的值变更信号，以跟踪设置变化
        # 一般文本输入框
        for widget in self.findChildren(QLineEdit):
            widget.textChanged.connect(self._on_setting_changed)
        
        # 单选框、复选框
        for widget in self.findChildren(QCheckBox):
            widget.toggled.connect(self._on_setting_changed)
        
        # 下拉列表
        for widget in self.findChildren(QComboBox):
            if widget != self.theme_selector:  # 主题下拉框已有特殊处理
                widget.currentTextChanged.connect(self._on_setting_changed)
        
        # 数字输入框
        for widget in self.findChildren(QSpinBox):
            widget.valueChanged.connect(self._on_setting_changed)
    
    def _on_theme_changed(self, theme_name):
        """主题变更处理
        
        Args:
            theme_name: 新主题名称
        """
        # 获取当前临时主题
        current_theme = self.temp_theme
        
        # 只有当新主题与当前临时主题不同时才应用
        if theme_name != current_theme:
            # 实时应用主题变更，但只作为临时预览
            logger.debug(f"设置界面中临时预览新主题: 从 {current_theme} 到 {theme_name}")
            
            # 应用主题
            success = self.theme_manager.apply_theme(theme_name)
            
            if success:
                # 更新临时主题记录
                self.temp_theme = theme_name
                
                # 标记设置已更改
                self._on_setting_changed()
                
                # 强制重绘整个界面
                self.repaint()
                
                # 通知父窗口也需要刷新
                if self.parent():
                    self.parent().repaint()
        else:
            logger.debug(f"忽略主题变更请求，当前已是 {theme_name} 主题")
    
    def _on_setting_changed(self):
        """当任何设置值变更时调用此方法，启用保存按钮"""
        self.settings_changed = True
        self.save_button.setEnabled(True)
    
    def _validate_settings(self):
        """验证设置
        
        Returns:
            tuple: (是否有效, 错误信息)
        """
        # 验证代理设置
        if self.use_proxy.isChecked():
            proxy_addr = self.proxy_host.text().strip()
            if not proxy_addr:
                return False, "启用代理时，代理地址不能为空。请输入有效的代理服务器地址。"
        
        # 验证API ID
        api_id = self.api_id.text().strip()
        if api_id:
            try:
                int(api_id)  # 确保是有效的整数
            except ValueError:
                return False, "API ID必须是正整数"
        
        # 这里可以添加其他验证逻辑
        
        return True, ""
    
    def _save_settings(self, silent=False):
        """保存设置
        
        Args:
            silent: 是否静默保存（不显示成功消息）
        """
        try:
            # 验证设置
            valid, message = self._validate_settings()
            if not valid:
                QMessageBox.warning(self, "验证错误", message, QMessageBox.Ok)
                # 如果是代理错误，切换到代理设置选项卡
                if "代理" in message:
                    self.settings_tabs.setCurrentWidget(self.proxy_tab)
                return
            
            # 收集设置
            collected_settings = self._collect_settings()
            
            # 创建更新后的配置副本
            updated_config = {}
            if isinstance(self.config, dict):
                updated_config = self.config.copy()  # 复制当前配置
            
            # 更新GENERAL和UI部分
            if 'GENERAL' in collected_settings:
                if 'GENERAL' not in updated_config:
                    updated_config['GENERAL'] = {}
                updated_config['GENERAL'].update(collected_settings['GENERAL'])
            
            if 'UI' in collected_settings:
                if 'UI' not in updated_config:
                    updated_config['UI'] = {}
                updated_config['UI'].update(collected_settings['UI'])
            
            # 保存主题设置
            self.original_theme = self.temp_theme
            
            # 发送配置保存信号
            logger.debug("向主窗口发送配置保存信号，更新设置")
            self.settings_saved.emit(updated_config)
            
            # 重置设置变更状态
            self.settings_changed = False
            
            # 禁用保存按钮
            self.save_button.setEnabled(False)
            
            # 显示成功消息（如果不是静默模式）
            if not silent:
                QMessageBox.information(self, "设置", "设置已成功保存")
        except Exception as e:
            # 直接使用外部定义的 logger
            logger.error(f"保存设置失败: {e}")
            
            # 根据错误类型提供更具体的错误消息
            error_msg = f"保存设置失败: {e}"
            if "proxy_addr" in str(e).lower():
                error_msg = "代理设置错误: 启用代理时，代理地址不能为空"
            elif "proxy_port" in str(e).lower():
                error_msg = "代理设置错误: 代理端口必须是1-65535之间的有效数字"
            elif "api_id" in str(e).lower():
                error_msg = "API设置错误: API ID必须是正整数"
            elif "api_hash" in str(e).lower():
                error_msg = "API设置错误: API Hash格式不正确"
            
            QMessageBox.critical(self, "错误", error_msg)
    
    def _reset_settings(self):
        """重置为默认设置"""
        # 询问用户是否确认
        reply = QMessageBox.question(
            self, 
            "重置确认", 
            "确认要将所有设置重置为默认值吗？",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # 重置API设置
        self.api_id.setText("")
        self.api_hash.setText("")
        self.phone_number.setText("")
        self.session_name.setText("tg_manager_session")
        self.auto_restart_session.setChecked(True)
        
        # 重置代理设置
        self.use_proxy.setChecked(False)
        self.proxy_type.setCurrentIndex(0)
        self.proxy_host.setText("")
        self.proxy_port.setValue(1080)
        self.proxy_username.setText("")
        self.proxy_password.setText("")
        
        # 重置界面设置
        self.theme_selector.setCurrentText("深色主题")
        self.language_selector.setCurrentText("中文")
        self.confirm_exit.setChecked(True)
        self.minimize_to_tray.setChecked(True)
        self.start_minimized.setChecked(False)
        self.enable_notifications.setChecked(True)
        self.notification_sound.setChecked(True)
        
        # 标记设置已更改
        self._on_setting_changed()
    
    def _collect_settings(self):
        """收集设置，构建配置字典
        
        Returns:
            dict: 配置字典
        """
        settings = {}
        
        # 收集API设置
        settings["GENERAL"] = {
            "api_id": int(self.api_id.text()) if self.api_id.text().strip() else 0,
            "api_hash": self.api_hash.text().strip(),
            "phone_number": self.phone_number.text().strip(),
            "auto_restart_session": self.auto_restart_session.isChecked()
        }
        
        # 收集代理设置
        settings["GENERAL"].update({
            "proxy_enabled": self.use_proxy.isChecked(),
            "proxy_type": self.proxy_type.currentText(),
            "proxy_addr": self.proxy_host.text().strip(),
            "proxy_port": self.proxy_port.value(),
            "proxy_username": self.proxy_username.text().strip() or None,
            "proxy_password": self.proxy_password.text().strip() or None
        })
        
        # 收集UI设置
        settings["UI"] = {
            "theme": self.theme_selector.currentText(),
            "language": self.language_selector.currentText(),
            "confirm_exit": self.confirm_exit.isChecked(),
            "minimize_to_tray": self.minimize_to_tray.isChecked(),
            "start_minimized": self.start_minimized.isChecked(),
            "enable_notifications": self.enable_notifications.isChecked(),
            "notification_sound": self.notification_sound.isChecked()
        }
        
        # 合并现有配置
        merged_settings = self.config.copy() if self.config else {}
        
        # 更新设置
        for section in settings:
            if section not in merged_settings:
                merged_settings[section] = {}
            merged_settings[section].update(settings[section])
        
        return merged_settings
    
    def load_config(self, config):
        """从配置加载设置
        
        Args:
            config: 配置字典
        """
        if not config:
            return
        
        # 加载API设置
        if "GENERAL" in config:
            general = config["GENERAL"]
            if "api_id" in general:
                self.api_id.setText(str(general["api_id"]))
            if "api_hash" in general:
                self.api_hash.setText(general["api_hash"])
            if "phone_number" in general and general["phone_number"]:
                self.phone_number.setText(general["phone_number"])
            if "auto_restart_session" in general:
                self.auto_restart_session.setChecked(general["auto_restart_session"])
            
            # 加载代理设置
            if "proxy_enabled" in general:
                self.use_proxy.setChecked(general["proxy_enabled"])
            if "proxy_type" in general and general["proxy_type"] in ["SOCKS5"]:
                index = self.proxy_type.findText(general["proxy_type"])
                if index >= 0:
                    self.proxy_type.setCurrentIndex(index)
            if "proxy_addr" in general:
                self.proxy_host.setText(general["proxy_addr"])
            if "proxy_port" in general:
                self.proxy_port.setValue(general["proxy_port"])
            if "proxy_username" in general and general["proxy_username"]:
                self.proxy_username.setText(general["proxy_username"])
            if "proxy_password" in general and general["proxy_password"]:
                self.proxy_password.setText(general["proxy_password"])
        
        # 加载UI设置
        if "UI" in config:
            ui = config["UI"]
            if "theme" in ui:
                index = self.theme_selector.findText(ui["theme"])
                if index >= 0:
                    self.theme_selector.setCurrentIndex(index)
                    # 应用临时主题
                    self.temp_theme = ui["theme"]
                    self._on_theme_changed(ui["theme"])
            if "language" in ui:
                index = self.language_selector.findText(ui["language"])
                if index >= 0:
                    self.language_selector.setCurrentIndex(index)
            if "confirm_exit" in ui:
                self.confirm_exit.setChecked(ui["confirm_exit"])
            if "minimize_to_tray" in ui:
                self.minimize_to_tray.setChecked(ui["minimize_to_tray"])
            if "start_minimized" in ui:
                self.start_minimized.setChecked(ui["start_minimized"])
            if "enable_notifications" in ui:
                self.enable_notifications.setChecked(ui["enable_notifications"])
            if "notification_sound" in ui:
                self.notification_sound.setChecked(ui["notification_sound"])
    
    def update_login_button(self, is_logged_in, user_info=None):
        """更新登录按钮状态
        
        Args:
            is_logged_in: 是否已登录
            user_info: 用户信息（可选）
        """
        if not hasattr(self, 'login_button'):
            return
            
        if is_logged_in:
            self.login_button.setText("已登录")
            self.login_button.setStyleSheet("background-color: #F44336; color: white; border: none; border-radius: 3px;")  # 红色背景，无边框
            self.login_button.setEnabled(False)  # 禁用按钮
            if user_info:
                self.login_button.setToolTip(f"当前登录用户: {user_info}")
            else:
                self.login_button.setToolTip("当前已登录")
        else:
            self.login_button.setText("登录")
            self.login_button.setStyleSheet("background-color: #2196F3; color: white; border: none; border-radius: 3px;")  # 蓝色背景，无边框
            self.login_button.setEnabled(True)  # 启用按钮
            self.login_button.setToolTip("点击登录到Telegram账号")
    
    def _handle_login(self):
        """处理登录按钮点击事件"""
        # 首先保存当前设置，确保使用最新的API凭据
        self._save_settings(silent=True)
        
        # 发出登录请求信号
        self.login_requested.emit() 