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
from PySide6.QtCore import Qt, Signal, Slot
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
        
        self.use_bot = QCheckBox("使用Bot Token")
        telegram_layout.addRow("", self.use_bot)
        
        self.bot_token = QLineEdit()
        self.bot_token.setEnabled(False)
        telegram_layout.addRow("Bot Token:", self.bot_token)
        
        # 连接复选框状态和Bot Token输入框
        self.use_bot.toggled.connect(self.bot_token.setEnabled)
        
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
        self.proxy_type.addItems(["SOCKS5", "HTTP", "MTProto"])
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
        self.theme = QComboBox()
        # 从主题管理器获取可用主题列表
        self.theme.addItems(self.theme_manager.get_available_themes())
        self.theme.setCurrentText(self.theme_manager.get_current_theme_name())
        self.theme.setToolTip("选择应用程序主题，更改后立即生效")
        # 连接主题变更信号
        self.theme.currentTextChanged.connect(self._on_theme_changed)
        
        theme_layout.addRow("应用主题:", self.theme)
        
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
            if widget != self.theme:  # 主题下拉框已有特殊处理
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
    
    def _save_settings(self):
        """保存设置到配置"""
        try:
            # 从UI收集设置
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
            
            # 显示成功信息
            QMessageBox.information(self, "设置", "设置已成功保存")
        except Exception as e:
            # 直接使用外部定义的 logger
            logger.error(f"保存设置失败: {e}")
            QMessageBox.critical(self, "错误", f"保存设置失败: {e}")
    
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
        self.use_bot.setChecked(False)
        self.bot_token.setText("")
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
        self.theme.setCurrentText("深色主题")
        self.confirm_exit.setChecked(True)
        self.minimize_to_tray.setChecked(True)
        self.start_minimized.setChecked(False)
        self.enable_notifications.setChecked(True)
        self.notification_sound.setChecked(True)
        
        # 标记设置已更改
        self._on_setting_changed()
    
    def _collect_settings(self):
        """收集设置
        
        Returns:
            dict: 设置字典
        """
        # 将代理类型文本转换为ProxyType枚举
        proxy_type_text = self.proxy_type.currentText()
        proxy_type_value = None
        try:
            if proxy_type_text == "SOCKS5":
                proxy_type_value = ProxyType.SOCKS5
            elif proxy_type_text == "HTTP":
                proxy_type_value = ProxyType.HTTP
            elif proxy_type_text == "MTProto":
                proxy_type_value = ProxyType.MTPROTO
            else:
                # 默认为SOCKS5
                proxy_type_value = ProxyType.SOCKS5
        except Exception as e:
            logger.warning(f"代理类型转换失败: {e}，使用默认值SOCKS5")
            proxy_type_value = ProxyType.SOCKS5
        
        settings = {
            'GENERAL': {
                # API设置移动到GENERAL部分
                'api_id': int(self.api_id.text()) if self.api_id.text().strip().isdigit() else 0,
                'api_hash': self.api_hash.text(),
                # 代理设置移动到GENERAL部分
                'proxy_enabled': self.use_proxy.isChecked(),
                'proxy_type': proxy_type_value,  # 使用枚举值
                'proxy_addr': self.proxy_host.text() if self.use_proxy.isChecked() else '',
                'proxy_port': self.proxy_port.value() if self.use_proxy.isChecked() else 0,
                'proxy_username': self.proxy_username.text() if self.use_proxy.isChecked() else '',
                'proxy_password': self.proxy_password.text() if self.use_proxy.isChecked() else ''
            },
            'UI': {
                'theme': self.theme.currentText(),
                'confirm_exit': self.confirm_exit.isChecked(),
                'minimize_to_tray': self.minimize_to_tray.isChecked(),
                'start_minimized': self.start_minimized.isChecked(),
                'enable_notifications': self.enable_notifications.isChecked(),
                'notification_sound': self.notification_sound.isChecked()
            }
        }
        
        return settings
    
    def load_config(self, config):
        """从配置字典加载设置
        
        Args:
            config: 配置字典
        """
        if not config:
            return
            
        logger.debug("加载设置配置")
        
        # 通用设置 - 从顶层GENERAL节点加载
        if 'GENERAL' in config:
            general_config = config.get('GENERAL', {})
            # API设置从GENERAL加载
            self.api_id.setText(str(general_config.get('api_id', '')))
            self.api_hash.setText(general_config.get('api_hash', ''))
            # 代理设置从GENERAL加载
            self.use_proxy.setChecked(general_config.get('proxy_enabled', False))
            self.proxy_type.setCurrentText(general_config.get('proxy_type', 'SOCKS5'))
            self.proxy_host.setText(general_config.get('proxy_addr', ''))
            self.proxy_port.setValue(general_config.get('proxy_port', 1080))
            self.proxy_username.setText(general_config.get('proxy_username', ''))
            self.proxy_password.setText(general_config.get('proxy_password', ''))
        
        # 为了向后兼容，尝试从旧的API和PROXY部分加载数据
        # API 设置 - 尝试从顶层API节点加载（如果GENERAL中没有相关设置）
        if 'API' in config and (not 'api_id' in config.get('GENERAL', {}) or not config['GENERAL']['api_id']):
            api_config = config.get('API', {})
            self.api_id.setText(str(api_config.get('api_id', '')))
            self.api_hash.setText(api_config.get('api_hash', ''))
            self.phone_number.setText(api_config.get('phone_number', ''))
            self.use_bot.setChecked(api_config.get('use_bot', False))
            self.bot_token.setText(api_config.get('bot_token', ''))
            self.session_name.setText(api_config.get('session_name', 'tg_manager_session'))
            self.auto_restart_session.setChecked(api_config.get('auto_restart_session', True))
            
        # 代理设置 - 尝试从顶层PROXY节点加载（如果GENERAL中没有相关设置）
        if 'PROXY' in config and (not 'proxy_enabled' in config.get('GENERAL', {}) or not config['GENERAL']['proxy_enabled']):
            proxy_config = config.get('PROXY', {})
            self.use_proxy.setChecked(proxy_config.get('use_proxy', False))
            self.proxy_type.setCurrentText(proxy_config.get('proxy_type', 'SOCKS5'))
            self.proxy_host.setText(proxy_config.get('proxy_host', ''))
            self.proxy_port.setValue(proxy_config.get('proxy_port', 1080))
            self.proxy_username.setText(proxy_config.get('proxy_username', ''))
            self.proxy_password.setText(proxy_config.get('proxy_password', ''))
            
        # UI设置 - 从UI节点加载
        if 'UI' in config:
            ui_config = config.get('UI', {})
            self.theme.setCurrentText(ui_config.get('theme', '深色主题'))
            self.confirm_exit.setChecked(ui_config.get('confirm_exit', True))
            self.minimize_to_tray.setChecked(ui_config.get('minimize_to_tray', True))
            self.start_minimized.setChecked(ui_config.get('start_minimized', False))
            self.enable_notifications.setChecked(ui_config.get('enable_notifications', True))
            self.notification_sound.setChecked(ui_config.get('notification_sound', True)) 