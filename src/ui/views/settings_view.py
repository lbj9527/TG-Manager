"""
TG-Manager 设置界面
实现应用程序配置管理
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QCheckBox, QPushButton,
    QGroupBox, QScrollArea, QSpinBox, QTabWidget,
    QComboBox, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt, Signal, Slot

from src.utils.logger import get_logger

logger = get_logger()


class SettingsView(QWidget):
    """设置界面，提供应用程序配置管理"""
    
    # 设置保存信号
    settings_saved = Signal(dict)  # 配置字典
    
    def __init__(self, config=None, parent=None):
        """初始化设置界面
        
        Args:
            config: 配置对象
            parent: 父窗口部件
        """
        super().__init__(parent)
        
        self.config = config or {}
        
        # 设置布局
        self.main_layout = QVBoxLayout(self)
        self.setLayout(self.main_layout)
        
        # 创建设置选项卡
        self._create_settings_tabs()
        
        # 创建底部按钮
        self._create_buttons()
        
        # 连接信号
        self._connect_signals()
        
        # 加载配置
        if self.config:
            self.load_config(self.config)
        
        logger.info("设置界面初始化完成")
    
    def _create_settings_tabs(self):
        """创建设置选项卡"""
        self.settings_tabs = QTabWidget()
        
        # 创建通用设置选项卡
        self.general_tab = self._create_general_tab()
        self.settings_tabs.addTab(self.general_tab, "通用")
        
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
    
    def _create_general_tab(self):
        """创建通用设置选项卡
        
        Returns:
            QWidget: 通用设置面板
        """
        general_widget = QWidget()
        general_layout = QVBoxLayout(general_widget)
        
        # 创建下载设置组
        download_group = QGroupBox("下载设置")
        download_layout = QFormLayout()
        
        self.download_path = QLineEdit()
        download_path_layout = QHBoxLayout()
        download_path_layout.addWidget(self.download_path)
        
        self.browse_download_button = QPushButton("浏览...")
        download_path_layout.addWidget(self.browse_download_button)
        
        download_layout.addRow("默认下载路径:", download_path_layout)
        
        self.max_concurrent_downloads = QSpinBox()
        self.max_concurrent_downloads.setRange(1, 10)
        self.max_concurrent_downloads.setValue(3)
        download_layout.addRow("最大同时下载数:", self.max_concurrent_downloads)
        
        self.auto_retry_downloads = QCheckBox("下载失败自动重试")
        self.auto_retry_downloads.setChecked(True)
        download_layout.addRow("", self.auto_retry_downloads)
        
        self.retry_count = QSpinBox()
        self.retry_count.setRange(1, 5)
        self.retry_count.setValue(3)
        download_layout.addRow("重试次数:", self.retry_count)
        
        download_group.setLayout(download_layout)
        general_layout.addWidget(download_group)
        
        # 创建上传设置组
        upload_group = QGroupBox("上传设置")
        upload_layout = QFormLayout()
        
        self.max_concurrent_uploads = QSpinBox()
        self.max_concurrent_uploads.setRange(1, 10)
        self.max_concurrent_uploads.setValue(2)
        upload_layout.addRow("最大同时上传数:", self.max_concurrent_uploads)
        
        self.default_caption_template = QLineEdit()
        self.default_caption_template.setPlaceholderText("{filename}")
        upload_layout.addRow("默认说明文字模板:", self.default_caption_template)
        
        upload_group.setLayout(upload_layout)
        general_layout.addWidget(upload_group)
        
        # 创建转发设置组
        forward_group = QGroupBox("转发设置")
        forward_layout = QFormLayout()
        
        self.default_forward_delay = QSpinBox()
        self.default_forward_delay.setRange(0, 60)
        self.default_forward_delay.setValue(3)
        self.default_forward_delay.setSuffix(" 秒")
        forward_layout.addRow("默认转发延迟:", self.default_forward_delay)
        
        self.preserve_date_default = QCheckBox("默认保留原始日期")
        forward_layout.addRow("", self.preserve_date_default)
        
        forward_group.setLayout(forward_layout)
        general_layout.addWidget(forward_group)
        
        # 添加伸展以填充空白区域
        general_layout.addStretch()
        
        return general_widget
    
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
        
        self.theme = QComboBox()
        self.theme.addItems(["浅色主题", "深色主题", "跟随系统"])
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
        
        self.save_button = QPushButton("保存设置")
        self.cancel_button = QPushButton("取消")
        self.reset_button = QPushButton("重置为默认")
        
        button_layout.addWidget(self.reset_button)
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.save_button)
        
        self.main_layout.addLayout(button_layout)
    
    def _connect_signals(self):
        """连接信号和槽"""
        # 浏览按钮
        self.browse_download_button.clicked.connect(self._browse_download_path)
        
        # 底部按钮
        self.save_button.clicked.connect(self._save_settings)
        self.cancel_button.clicked.connect(self._cancel_settings)
        self.reset_button.clicked.connect(self._reset_settings)
    
    def _browse_download_path(self):
        """浏览下载路径"""
        directory = QFileDialog.getExistingDirectory(
            self, 
            "选择下载目录",
            self.download_path.text() or ""
        )
        
        if directory:
            self.download_path.setText(directory)
    
    def _save_settings(self):
        """保存设置"""
        # 收集设置
        settings = self._collect_settings()
        
        # 发出设置保存信号
        self.settings_saved.emit(settings)
        
        # 显示保存成功消息
        QMessageBox.information(self, "设置保存", "设置已成功保存")
    
    def _cancel_settings(self):
        """取消设置"""
        # 如果在单独窗口中，关闭窗口
        if self.parent() and hasattr(self.parent(), 'close'):
            self.parent().close()
    
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
        
        # 重置通用设置
        self.download_path.setText("")
        self.max_concurrent_downloads.setValue(3)
        self.auto_retry_downloads.setChecked(True)
        self.retry_count.setValue(3)
        self.max_concurrent_uploads.setValue(2)
        self.default_caption_template.setText("")
        self.default_forward_delay.setValue(3)
        self.preserve_date_default.setChecked(False)
        
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
        self.theme.setCurrentIndex(2)
        self.confirm_exit.setChecked(True)
        self.minimize_to_tray.setChecked(True)
        self.start_minimized.setChecked(False)
        self.enable_notifications.setChecked(True)
        self.notification_sound.setChecked(True)
    
    def _collect_settings(self):
        """收集设置
        
        Returns:
            dict: 设置字典
        """
        settings = {
            'GENERAL': {
                'download_path': self.download_path.text(),
                'max_concurrent_downloads': self.max_concurrent_downloads.value(),
                'auto_retry_downloads': self.auto_retry_downloads.isChecked(),
                'retry_count': self.retry_count.value(),
                'max_concurrent_uploads': self.max_concurrent_uploads.value(),
                'default_caption_template': self.default_caption_template.text(),
                'default_forward_delay': self.default_forward_delay.value(),
                'preserve_date_default': self.preserve_date_default.isChecked()
            },
            'API': {
                'api_id': self.api_id.text(),
                'api_hash': self.api_hash.text(),
                'phone_number': self.phone_number.text(),
                'use_bot': self.use_bot.isChecked(),
                'bot_token': self.bot_token.text() if self.use_bot.isChecked() else '',
                'session_name': self.session_name.text(),
                'auto_restart_session': self.auto_restart_session.isChecked()
            },
            'PROXY': {
                'use_proxy': self.use_proxy.isChecked(),
                'proxy_type': self.proxy_type.currentText() if self.use_proxy.isChecked() else '',
                'proxy_host': self.proxy_host.text() if self.use_proxy.isChecked() else '',
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
        
        # API 设置
        if 'API' in config:
            api_config = config.get('API', {})
            self.api_id.setText(str(api_config.get('api_id', '')))
            self.api_hash.setText(api_config.get('api_hash', ''))
            self.phone_number.setText(api_config.get('phone_number', ''))
            self.use_bot.setChecked(api_config.get('use_bot', False))
            self.bot_token.setText(api_config.get('bot_token', ''))
            self.session_name.setText(api_config.get('session_name', 'tg_manager'))
            
        # 代理设置
        if 'Proxy' in config:
            proxy_config = config.get('Proxy', {})
            self.use_proxy.setChecked(proxy_config.get('enabled', False))
            self.proxy_type.setCurrentText(proxy_config.get('type', 'SOCKS5'))
            self.proxy_host.setText(proxy_config.get('host', ''))
            self.proxy_port.setValue(proxy_config.get('port', 1080))
            self.proxy_username.setText(proxy_config.get('username', ''))
            self.proxy_password.setText(proxy_config.get('password', ''))
            
        # 下载设置
        if 'Download' in config:
            download_config = config.get('Download', {})
            self.download_path.setText(download_config.get('default_path', 'downloads'))
            self.max_concurrent_downloads.setValue(download_config.get('concurrent_downloads', 3))
            self.auto_retry_downloads.setChecked(download_config.get('auto_retry_downloads', True))
            self.retry_count.setValue(download_config.get('retry_count', 3))
            
        # 上传设置
        if 'Upload' in config:
            upload_config = config.get('Upload', {})
            self.max_concurrent_uploads.setValue(upload_config.get('concurrent_uploads', 2))
            self.default_caption_template.setText(upload_config.get('default_caption_template', '{filename}'))
            
        # UI设置
        if 'UI' in config:
            ui_config = config.get('UI', {})
            self.theme.setCurrentText(ui_config.get('theme', '跟随系统'))
            self.confirm_exit.setChecked(ui_config.get('confirm_exit', True))
            self.minimize_to_tray.setChecked(ui_config.get('minimize_to_tray', True))
            self.start_minimized.setChecked(ui_config.get('start_minimized', False))
            self.enable_notifications.setChecked(ui_config.get('enable_notifications', True))
            self.notification_sound.setChecked(ui_config.get('notification_sound', True)) 