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
from src.utils.translation_manager import get_translation_manager, tr
from src.utils.ui_config_models import ProxyType

logger = get_logger()


class SettingsView(QWidget):
    """设置界面，提供应用程序配置管理"""
    
    # 设置保存信号
    settings_saved = Signal(dict)  # 带参数的信号
    settings_cancelled = Signal()  # 设置取消信号
    login_requested = Signal()     # 添加登录请求信号
    
    # 主题标识符到翻译键的映射
    THEME_TRANSLATION_MAP = {
        "浅色主题": "ui.settings.ui.theme.themes.light_theme",
        "深色主题": "ui.settings.ui.theme.themes.dark_theme",
        "蓝色主题": "ui.settings.ui.theme.themes.blue_theme",
        "紫色主题": "ui.settings.ui.theme.themes.purple_theme",
        "红色主题": "ui.settings.ui.theme.themes.red_theme",
        "绿色主题": "ui.settings.ui.theme.themes.green_theme",
        "琥珀色主题": "ui.settings.ui.theme.themes.amber_theme",
        "粉色主题": "ui.settings.ui.theme.themes.pink_theme",
        "黄色主题": "ui.settings.ui.theme.themes.yellow_theme",
        "青色主题": "ui.settings.ui.theme.themes.cyan_theme"
    }
    
    # 反向映射：从翻译后的显示文本找回原始主题标识符
    _reverse_theme_map = {}
    
    def __init__(self, config=None, parent=None):
        """初始化设置界面
        
        Args:
            config: 配置对象
            parent: 父窗口部件
        """
        super().__init__(parent)
        
        self.config = config or {}
        
        # 获取主题管理器和翻译管理器
        self.theme_manager = get_theme_manager()
        self.translation_manager = get_translation_manager()
        
        # 添加临时主题存储
        self.original_theme = self.theme_manager.get_current_theme_name()
        self.temp_theme = self.original_theme
        
        # 跟踪设置是否已更改
        self.settings_changed = False
        
        # 存储所有需要翻译的组件
        self.translatable_widgets = {}
        
        # 设置布局
        self.main_layout = QVBoxLayout(self)
        self.setLayout(self.main_layout)
        
        # 创建设置选项卡
        self._create_settings_tabs()
        
        # 创建底部按钮
        self._create_buttons()
        
        # 连接信号
        self._connect_signals()
        
        # 连接语言变更信号
        self.translation_manager.language_changed.connect(self._update_translations)
        
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
        
        # 初始化翻译
        self._update_translations()
        
        # 设置初始化完成标志
        self._initialization_complete = True
        
        logger.info("设置界面初始化完成")
    
    def _create_settings_tabs(self):
        """创建设置选项卡"""
        self.settings_tabs = QTabWidget()
        
        # 创建API设置选项卡
        self.api_tab = self._create_api_tab()
        self.settings_tabs.addTab(self.api_tab, tr("ui.settings.tabs.api"))
        
        # 创建代理设置选项卡
        self.proxy_tab = self._create_proxy_tab()
        self.settings_tabs.addTab(self.proxy_tab, tr("ui.settings.tabs.proxy"))
        
        # 创建界面设置选项卡
        self.ui_tab = self._create_ui_tab()
        self.settings_tabs.addTab(self.ui_tab, tr("ui.settings.tabs.ui"))
        
        # 添加到主布局
        self.main_layout.addWidget(self.settings_tabs)
        
        # 存储选项卡引用以便翻译更新
        self.translatable_widgets['tabs'] = {
            'api': (self.settings_tabs, 0),
            'proxy': (self.settings_tabs, 1),
            'ui': (self.settings_tabs, 2)
        }
    
    def _create_api_tab(self):
        """创建API设置选项卡
        
        Returns:
            QWidget: API设置面板
        """
        api_widget = QWidget()
        api_layout = QVBoxLayout(api_widget)
        
        # 创建Telegram API设置组
        self.telegram_group = QGroupBox(tr("ui.settings.api.title"))
        telegram_layout = QFormLayout()
        
        self.api_id = QLineEdit()
        self.api_id_label = QLabel(tr("ui.settings.api.api_id"))
        telegram_layout.addRow(self.api_id_label, self.api_id)
        
        self.api_hash = QLineEdit()
        self.api_hash_label = QLabel(tr("ui.settings.api.api_hash"))
        telegram_layout.addRow(self.api_hash_label, self.api_hash)
        
        self.phone_number = QLineEdit()
        self.phone_number_label = QLabel(tr("ui.settings.api.phone_number"))
        telegram_layout.addRow(self.phone_number_label, self.phone_number)
        
        # 添加登录按钮
        self.login_button = QPushButton(tr("ui.settings.api.login"))
        self.login_button.setMinimumWidth(120)
        self.login_button.clicked.connect(self._handle_login)
        # 设置默认颜色，添加无边框样式
        self.login_button.setStyleSheet("background-color: #2196F3; color: white; border: none; border-radius: 3px;")
        telegram_layout.addRow("", self.login_button)
        
        # 添加登录提示标签
        self.login_tip = QLabel(tr("ui.settings.api.login_tip"))
        self.login_tip.setWordWrap(True)
        self.login_tip.setTextFormat(Qt.RichText)
        self.login_tip.setOpenExternalLinks(True)
        self.login_tip.setStyleSheet("font-size: 9pt;")
        telegram_layout.addRow("", self.login_tip)
        
        self.telegram_group.setLayout(telegram_layout)
        api_layout.addWidget(self.telegram_group)
        
        # 创建会话设置组
        self.session_group = QGroupBox(tr("ui.settings.api.session.title"))
        session_layout = QFormLayout()
        
        self.session_name = QLineEdit("tg_manager_session")
        self.session_name_label = QLabel(tr("ui.settings.api.session.session_name"))
        session_layout.addRow(self.session_name_label, self.session_name)
        
        self.auto_restart_session = QCheckBox(tr("ui.settings.api.session.auto_restart"))
        self.auto_restart_session.setChecked(True)
        session_layout.addRow("", self.auto_restart_session)
        
        self.session_group.setLayout(session_layout)
        api_layout.addWidget(self.session_group)
        
        # 添加伸展以填充空白区域
        api_layout.addStretch()
        
        # 存储API设置页面的组件引用
        self.translatable_widgets['api'] = {
            'telegram_group': self.telegram_group,
            'session_group': self.session_group,
            'api_id_label': self.api_id_label,
            'api_hash_label': self.api_hash_label,
            'phone_number_label': self.phone_number_label,
            'session_name_label': self.session_name_label,
            'login_button': self.login_button,
            'login_tip': self.login_tip,
            'auto_restart_session': self.auto_restart_session
        }
        
        return api_widget
    
    def _create_proxy_tab(self):
        """创建代理设置选项卡
        
        Returns:
            QWidget: 代理设置面板
        """
        proxy_widget = QWidget()
        proxy_layout = QVBoxLayout(proxy_widget)
        
        # 创建代理设置组
        self.proxy_group = QGroupBox(tr("ui.settings.proxy.title"))
        proxy_form = QFormLayout()
        
        self.use_proxy = QCheckBox(tr("ui.settings.proxy.use_proxy"))
        proxy_form.addRow("", self.use_proxy)
        
        self.proxy_type = QComboBox()
        self.proxy_type.addItems(["SOCKS5"])
        self.proxy_type.setEnabled(False)
        self.proxy_type_label = QLabel(tr("ui.settings.proxy.proxy_type"))
        proxy_form.addRow(self.proxy_type_label, self.proxy_type)
        
        self.proxy_host = QLineEdit()
        self.proxy_host.setEnabled(False)
        self.proxy_host_label = QLabel(tr("ui.settings.proxy.proxy_host"))
        proxy_form.addRow(self.proxy_host_label, self.proxy_host)
        
        self.proxy_port = QSpinBox()
        self.proxy_port.setRange(1, 65535)
        self.proxy_port.setValue(1080)
        self.proxy_port.setEnabled(False)
        self.proxy_port_label = QLabel(tr("ui.settings.proxy.proxy_port"))
        proxy_form.addRow(self.proxy_port_label, self.proxy_port)
        
        self.proxy_username = QLineEdit()
        self.proxy_username.setEnabled(False)
        self.proxy_username_label = QLabel(tr("ui.settings.proxy.proxy_username"))
        proxy_form.addRow(self.proxy_username_label, self.proxy_username)
        
        self.proxy_password = QLineEdit()
        self.proxy_password.setEchoMode(QLineEdit.Password)
        self.proxy_password.setEnabled(False)
        self.proxy_password_label = QLabel(tr("ui.settings.proxy.proxy_password"))
        proxy_form.addRow(self.proxy_password_label, self.proxy_password)
        
        # 连接复选框状态和代理设置输入框
        self.use_proxy.toggled.connect(self.proxy_type.setEnabled)
        self.use_proxy.toggled.connect(self.proxy_host.setEnabled)
        self.use_proxy.toggled.connect(self.proxy_port.setEnabled)
        self.use_proxy.toggled.connect(self.proxy_username.setEnabled)
        self.use_proxy.toggled.connect(self.proxy_password.setEnabled)
        
        self.proxy_group.setLayout(proxy_form)
        proxy_layout.addWidget(self.proxy_group)
        
        # 添加伸展以填充空白区域
        proxy_layout.addStretch()
        
        # 存储代理设置页面的组件引用
        self.translatable_widgets['proxy'] = {
            'proxy_group': self.proxy_group,
            'use_proxy': self.use_proxy,
            'proxy_type_label': self.proxy_type_label,
            'proxy_host_label': self.proxy_host_label,
            'proxy_port_label': self.proxy_port_label,
            'proxy_username_label': self.proxy_username_label,
            'proxy_password_label': self.proxy_password_label
        }
        
        return proxy_widget
    
    def _create_ui_tab(self):
        """创建界面设置选项卡
        
        Returns:
            QWidget: 界面设置面板
        """
        ui_widget = QWidget()
        ui_layout = QVBoxLayout(ui_widget)
        
        # 创建主题设置组
        self.theme_group = QGroupBox(tr("ui.settings.ui.theme.title"))
        theme_layout = QFormLayout()
        
        # 主题选择部分
        self.theme_selector = QComboBox()
        # 使用翻译后的主题名称
        self._populate_theme_selector()
        self.theme_selector.setToolTip(tr("ui.settings.ui.theme.theme_tooltip"))
        # 连接主题变更信号
        self.theme_selector.currentTextChanged.connect(self._on_theme_changed)
        
        self.app_theme_label = QLabel(tr("ui.settings.ui.theme.app_theme"))
        theme_layout.addRow(self.app_theme_label, self.theme_selector)
        
        # 语言选择部分
        self.language_selector = QComboBox()
        # 添加支持的语言选项
        self.language_selector.addItems(["中文", "English", "Español", "Français", "Deutsch", "Русский", "日本語", "한국어"])
        self.language_selector.setCurrentText("中文")  # 默认选中中文
        self.language_selector.setToolTip(tr("ui.settings.ui.theme.language_tooltip"))
        # 连接语言变更信号
        self.language_selector.currentTextChanged.connect(self._on_language_changed)
        
        self.language_label = QLabel(tr("ui.settings.ui.theme.language"))
        theme_layout.addRow(self.language_label, self.language_selector)
        
        self.theme_group.setLayout(theme_layout)
        ui_layout.addWidget(self.theme_group)
        
        # 创建行为设置组
        self.behavior_group = QGroupBox(tr("ui.settings.ui.behavior.title"))
        behavior_layout = QFormLayout()
        
        self.confirm_exit = QCheckBox(tr("ui.settings.ui.behavior.confirm_exit"))
        self.confirm_exit.setChecked(True)
        behavior_layout.addRow("", self.confirm_exit)
        
        self.minimize_to_tray = QCheckBox(tr("ui.settings.ui.behavior.minimize_to_tray"))
        self.minimize_to_tray.setChecked(True)
        behavior_layout.addRow("", self.minimize_to_tray)
        
        self.start_minimized = QCheckBox(tr("ui.settings.ui.behavior.start_minimized"))
        # 默认不选中
        self.start_minimized.setChecked(False)
        # 添加提示说明
        self.start_minimized.setToolTip(tr("ui.settings.ui.behavior.start_minimized_tooltip"))
        behavior_layout.addRow("", self.start_minimized)
        
        self.behavior_group.setLayout(behavior_layout)
        ui_layout.addWidget(self.behavior_group)
        
        # 创建通知设置组
        self.notification_group = QGroupBox(tr("ui.settings.ui.notifications.title"))
        notification_layout = QFormLayout()
        
        self.enable_notifications = QCheckBox(tr("ui.settings.ui.notifications.enable_notifications"))
        self.enable_notifications.setChecked(True)
        notification_layout.addRow("", self.enable_notifications)
        
        self.notification_sound = QCheckBox(tr("ui.settings.ui.notifications.notification_sound"))
        self.notification_sound.setChecked(True)
        notification_layout.addRow("", self.notification_sound)
        
        self.notification_group.setLayout(notification_layout)
        ui_layout.addWidget(self.notification_group)
        
        # 添加伸展以填充空白区域
        ui_layout.addStretch()
        
        # 存储界面设置页面的组件引用
        self.translatable_widgets['ui'] = {
            'theme_group': self.theme_group,
            'behavior_group': self.behavior_group,
            'notification_group': self.notification_group,
            'app_theme_label': self.app_theme_label,
            'language_label': self.language_label,
            'confirm_exit': self.confirm_exit,
            'minimize_to_tray': self.minimize_to_tray,
            'start_minimized': self.start_minimized,
            'enable_notifications': self.enable_notifications,
            'notification_sound': self.notification_sound
        }
        
        return ui_widget
    
    def _create_buttons(self):
        """创建底部按钮"""
        button_layout = QHBoxLayout()
        
        self.reset_button = QPushButton(tr("ui.settings.buttons.reset"))
        self.save_button = QPushButton(tr("ui.settings.buttons.save"))
        
        button_layout.addWidget(self.save_button)
        button_layout.addStretch()
        button_layout.addWidget(self.reset_button)
        
        self.main_layout.addLayout(button_layout)
        
        # 存储按钮引用
        self.translatable_widgets['buttons'] = {
            'save_button': self.save_button,
            'reset_button': self.reset_button
        }
    
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
            if widget != self.theme_selector and widget != self.language_selector:  # 主题和语言下拉框已有特殊处理
                widget.currentTextChanged.connect(self._on_setting_changed)
        
        # 数字输入框
        for widget in self.findChildren(QSpinBox):
            widget.valueChanged.connect(self._on_setting_changed)
    
    def _on_theme_changed(self, theme_name):
        """主题变更处理
        
        Args:
            theme_name: 新主题名称（可能是翻译后的）
        """
        # 从反向映射中获取原始主题标识符
        original_theme_name = self._reverse_theme_map.get(theme_name, theme_name)
        
        # 获取当前临时主题
        current_theme = self.temp_theme
        
        # 只有当新主题与当前临时主题不同时才应用
        if original_theme_name != current_theme:
            # 实时应用主题变更，但只作为临时预览
            logger.debug(f"设置界面中临时预览新主题: 从 {current_theme} 到 {original_theme_name} (显示: {theme_name})")
            
            # 应用主题
            success = self.theme_manager.apply_theme(original_theme_name)
            
            if success:
                # 更新临时主题记录
                self.temp_theme = original_theme_name
                
                # 标记设置已更改
                self._on_setting_changed()
                
                # 强制重绘整个界面
                self.repaint()
                
                # 通知父窗口也需要刷新
                if self.parent():
                    self.parent().repaint()
        else:
            logger.debug(f"忽略主题变更请求，当前已是 {original_theme_name} 主题")
    
    def _on_language_changed(self, language_name):
        """语言变更处理
        
        Args:
            language_name: 新语言名称
        """
        # 设置翻译管理器的语言
        success = self.translation_manager.set_language(language_name)
        
        if success:
            # 标记设置已更改
            self._on_setting_changed()
            
            logger.info(f"语言已切换到: {language_name}")
        else:
            logger.warning(f"语言切换失败: {language_name}")
    
    def _update_translations(self):
        """更新所有界面文本的翻译"""
        # 更新选项卡标题
        if 'tabs' in self.translatable_widgets:
            tabs_data = self.translatable_widgets['tabs']
            self.settings_tabs.setTabText(tabs_data['api'][1], tr("ui.settings.tabs.api"))
            self.settings_tabs.setTabText(tabs_data['proxy'][1], tr("ui.settings.tabs.proxy"))
            self.settings_tabs.setTabText(tabs_data['ui'][1], tr("ui.settings.tabs.ui"))
        
        # 更新API设置页面
        if 'api' in self.translatable_widgets:
            api_widgets = self.translatable_widgets['api']
            api_widgets['telegram_group'].setTitle(tr("ui.settings.api.title"))
            api_widgets['session_group'].setTitle(tr("ui.settings.api.session.title"))
            api_widgets['api_id_label'].setText(tr("ui.settings.api.api_id"))
            api_widgets['api_hash_label'].setText(tr("ui.settings.api.api_hash"))
            api_widgets['phone_number_label'].setText(tr("ui.settings.api.phone_number"))
            api_widgets['session_name_label'].setText(tr("ui.settings.api.session.session_name"))
            api_widgets['auto_restart_session'].setText(tr("ui.settings.api.session.auto_restart"))
            api_widgets['login_tip'].setText(tr("ui.settings.api.login_tip"))
            
            # 更新登录按钮文本（需要保持当前状态）
            if api_widgets['login_button'].isEnabled():
                api_widgets['login_button'].setText(tr("ui.settings.api.login"))
            else:
                api_widgets['login_button'].setText(tr("ui.settings.api.logged_in"))
        
        # 更新代理设置页面
        if 'proxy' in self.translatable_widgets:
            proxy_widgets = self.translatable_widgets['proxy']
            proxy_widgets['proxy_group'].setTitle(tr("ui.settings.proxy.title"))
            proxy_widgets['use_proxy'].setText(tr("ui.settings.proxy.use_proxy"))
            proxy_widgets['proxy_type_label'].setText(tr("ui.settings.proxy.proxy_type"))
            proxy_widgets['proxy_host_label'].setText(tr("ui.settings.proxy.proxy_host"))
            proxy_widgets['proxy_port_label'].setText(tr("ui.settings.proxy.proxy_port"))
            proxy_widgets['proxy_username_label'].setText(tr("ui.settings.proxy.proxy_username"))
            proxy_widgets['proxy_password_label'].setText(tr("ui.settings.proxy.proxy_password"))
        
        # 更新界面设置页面
        if 'ui' in self.translatable_widgets:
            ui_widgets = self.translatable_widgets['ui']
            ui_widgets['theme_group'].setTitle(tr("ui.settings.ui.theme.title"))
            ui_widgets['behavior_group'].setTitle(tr("ui.settings.ui.behavior.title"))
            ui_widgets['notification_group'].setTitle(tr("ui.settings.ui.notifications.title"))
            ui_widgets['app_theme_label'].setText(tr("ui.settings.ui.theme.app_theme"))
            ui_widgets['language_label'].setText(tr("ui.settings.ui.theme.language"))
            ui_widgets['confirm_exit'].setText(tr("ui.settings.ui.behavior.confirm_exit"))
            ui_widgets['minimize_to_tray'].setText(tr("ui.settings.ui.behavior.minimize_to_tray"))
            ui_widgets['start_minimized'].setText(tr("ui.settings.ui.behavior.start_minimized"))
            ui_widgets['enable_notifications'].setText(tr("ui.settings.ui.notifications.enable_notifications"))
            ui_widgets['notification_sound'].setText(tr("ui.settings.ui.notifications.notification_sound"))
            
            # 更新工具提示
            self.theme_selector.setToolTip(tr("ui.settings.ui.theme.theme_tooltip"))
            self.language_selector.setToolTip(tr("ui.settings.ui.theme.language_tooltip"))
            ui_widgets['start_minimized'].setToolTip(tr("ui.settings.ui.behavior.start_minimized_tooltip"))
            
            # 重新填充主题选择器以更新翻译（仅在不是初始化阶段时）
            if hasattr(self, '_initialization_complete') and self._initialization_complete:
                self._populate_theme_selector()
        
        # 更新按钮
        if 'buttons' in self.translatable_widgets:
            button_widgets = self.translatable_widgets['buttons']
            button_widgets['save_button'].setText(tr("ui.settings.buttons.save"))
            button_widgets['reset_button'].setText(tr("ui.settings.buttons.reset"))
        
        logger.debug("设置界面翻译已更新")
    
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
                return False, tr("errors.validation.proxy_addr_required")
        
        # 验证API ID
        api_id = self.api_id.text().strip()
        if api_id:
            try:
                int(api_id)  # 确保是有效的整数
            except ValueError:
                return False, tr("errors.validation.api_id_required")
        
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
                QMessageBox.warning(self, tr("ui.common.warning"), message, QMessageBox.Ok)
                # 如果是代理错误，切换到代理设置选项卡
                if "代理" in message or "proxy" in message.lower():
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
                QMessageBox.information(self, tr("ui.settings.title"), tr("ui.dialogs.settings_saved.message"))
        except Exception as e:
            # 直接使用外部定义的 logger
            logger.error(f"保存设置失败: {e}")
            
            # 根据错误类型提供更具体的错误消息
            error_msg = f"保存设置失败: {e}"
            if "proxy_addr" in str(e).lower():
                error_msg = tr("errors.validation.proxy_addr_required")
            elif "proxy_port" in str(e).lower():
                error_msg = tr("errors.validation.proxy_port_invalid")
            elif "api_id" in str(e).lower():
                error_msg = tr("errors.validation.api_id_required")
            elif "api_hash" in str(e).lower():
                error_msg = tr("errors.validation.api_hash_required")
            
            QMessageBox.critical(self, tr("ui.common.error"), error_msg)
    
    def _reset_settings(self):
        """重置为默认设置"""
        # 询问用户是否确认
        reply = QMessageBox.question(
            self, 
            tr("ui.dialogs.reset_settings.title"), 
            tr("ui.dialogs.reset_settings.message"),
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
        # 获取深色主题的翻译名称
        default_theme_translated = tr("ui.settings.ui.theme.themes.dark_theme")
        index = self.theme_selector.findText(default_theme_translated)
        if index >= 0:
            self.theme_selector.setCurrentIndex(index)
        else:
            # 如果找不到翻译，回退到硬编码
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
        current_theme_text = self.theme_selector.currentText()
        # 从反向映射中获取原始主题标识符
        original_theme = self._reverse_theme_map.get(current_theme_text, current_theme_text)
        
        settings["UI"] = {
            "theme": original_theme,
            "language": self.language_selector.currentText(),
            "confirm_exit": self.confirm_exit.isChecked(),
            "minimize_to_tray": self.minimize_to_tray.isChecked(),
            "start_minimized": self.start_minimized.isChecked(),
            "enable_notifications": self.enable_notifications.isChecked(),
            "notification_sound": self.notification_sound.isChecked()
        }
        
        # 保留现有的窗口布局相关配置，避免在保存设置时丢失侧边栏等布局配置
        if self.config and 'UI' in self.config:
            existing_ui = self.config['UI']
            layout_config_keys = [
                'window_geometry',     # 窗口几何形状
                'window_state',        # 窗口状态（工具栏位置等）
                'sidebar_geometry',    # 侧边栏几何形状
                'sidebar_data'         # 侧边栏完整状态（分割器状态等）
            ]
            
            for key in layout_config_keys:
                if key in existing_ui:
                    settings["UI"][key] = existing_ui[key]
                    logger.debug(f"保留现有窗口布局配置项: {key}")
        
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
                # 查找对应的翻译后显示文本
                original_theme = ui["theme"]
                if original_theme in self.THEME_TRANSLATION_MAP:
                    translated_theme = tr(self.THEME_TRANSLATION_MAP[original_theme])
                    index = self.theme_selector.findText(translated_theme)
                    if index >= 0:
                        self.theme_selector.setCurrentIndex(index)
                        # 应用临时主题（仅在初始化完成后）
                        self.temp_theme = original_theme
                        if hasattr(self, '_initialization_complete') and self._initialization_complete:
                            self._on_theme_changed(translated_theme)
                else:
                    # 如果找不到映射，直接使用原始名称
                    index = self.theme_selector.findText(original_theme)
                    if index >= 0:
                        self.theme_selector.setCurrentIndex(index)
                        self.temp_theme = original_theme
                        if hasattr(self, '_initialization_complete') and self._initialization_complete:
                            self._on_theme_changed(original_theme)
            if "language" in ui:
                index = self.language_selector.findText(ui["language"])
                if index >= 0:
                    self.language_selector.setCurrentIndex(index)
                    # 设置翻译管理器的语言
                    self.translation_manager.set_language(ui["language"])
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
            self.login_button.setText(tr("ui.settings.api.logged_in"))
            self.login_button.setStyleSheet("background-color: #F44336; color: white; border: none; border-radius: 3px;")  # 红色背景，无边框
            self.login_button.setEnabled(False)  # 禁用按钮
            if user_info:
                self.login_button.setToolTip(f"当前登录用户: {user_info}")
            else:
                self.login_button.setToolTip("当前已登录")
        else:
            self.login_button.setText(tr("ui.settings.api.login"))
            self.login_button.setStyleSheet("background-color: #2196F3; color: white; border: none; border-radius: 3px;")  # 蓝色背景，无边框
            self.login_button.setEnabled(True)  # 启用按钮
            self.login_button.setToolTip("点击登录到Telegram账号")
    
    def _handle_login(self):
        """处理登录按钮点击事件"""
        # 首先保存当前设置，确保使用最新的API凭据
        self._save_settings(silent=True)
        
        # 发出登录请求信号
        self.login_requested.emit() 

    def _populate_theme_selector(self):
        """填充主题选择器，使用翻译后的主题名称"""
        # 临时断开信号连接，避免在填充过程中触发主题变更
        try:
            self.theme_selector.currentTextChanged.disconnect()
        except TypeError:
            # 信号可能已经断开或不存在，忽略错误
            pass
        
        # 清空现有项目
        self.theme_selector.clear()
        
        # 构建反向映射
        self._reverse_theme_map.clear()
        
        # 获取原始主题列表
        original_themes = self.theme_manager.get_available_themes()
        
        # 添加翻译后的主题名称
        for original_theme in original_themes:
            if original_theme in self.THEME_TRANSLATION_MAP:
                # 获取翻译键
                translation_key = self.THEME_TRANSLATION_MAP[original_theme]
                # 获取翻译后的文本
                translated_name = tr(translation_key)
                # 添加到选择器
                self.theme_selector.addItem(translated_name)
                # 构建反向映射
                self._reverse_theme_map[translated_name] = original_theme
        
        # 设置当前选中的主题
        current_theme = self.theme_manager.get_current_theme_name()
        if current_theme in self.THEME_TRANSLATION_MAP:
            translated_current = tr(self.THEME_TRANSLATION_MAP[current_theme])
            index = self.theme_selector.findText(translated_current)
            if index >= 0:
                self.theme_selector.setCurrentIndex(index)
        
        # 重新连接信号
        self.theme_selector.currentTextChanged.connect(self._on_theme_changed) 