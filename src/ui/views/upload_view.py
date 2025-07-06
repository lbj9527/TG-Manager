"""
TG-Manager 上传界面
实现本地媒体文件上传到Telegram频道的功能
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QCheckBox, QPushButton,
    QGroupBox, QScrollArea, QSpinBox, QGridLayout,
    QListWidget, QListWidgetItem, QFileDialog, QMessageBox,
    QTextEdit, QSizePolicy, QTabWidget, QDoubleSpinBox,
    QProgressBar, QDialog, QMenu
)
from PySide6.QtCore import Qt, Signal, Slot, QSize, QDir, QMetaObject, Q_ARG, QTimer
from PySide6.QtGui import QIcon, QCursor

from pathlib import Path
import os
from src.utils.logger import get_logger
from src.utils.translation_manager import get_translation_manager, tr
import asyncio

logger = get_logger()


class UploadView(QWidget):
    """上传界面，提供本地媒体文件上传到Telegram频道的功能"""
    
    # 上传开始信号
    upload_started = Signal(dict)  # 上传配置
    config_saved = Signal(dict)    # 配置保存信号
    
    def __init__(self, config=None, parent=None):
        """初始化上传界面
        
        Args:
            config: 配置对象
            parent: 父窗口部件
        """
        super().__init__(parent)
        
        self.config = config or {}
        
        # 获取翻译管理器
        self.translation_manager = get_translation_manager()
        
        # 存储所有需要翻译的组件
        self.translatable_widgets = {}
        
        # 设置布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(2)  # 减小布局间距
        self.main_layout.setContentsMargins(4, 2, 4, 4)  # 减小上方边距
        self.setLayout(self.main_layout)
        
        # 创建上部配置标签页
        self.config_tabs = QTabWidget()
        self.config_tabs.setMaximumHeight(320)  # 减小最大高度
        self.config_tabs.setMinimumHeight(290)  # 减小最小高度
        self.config_tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)  # 固定高度策略
        self.main_layout.addWidget(self.config_tabs)
        
        # 创建配置标签页
        self._create_config_panel()
        
        # 创建下部上传状态面板
        self._create_upload_panel()
        
        # 创建底部操作按钮
        self._create_action_buttons()
        
        # 连接信号
        self._connect_signals()
        
        # 连接翻译管理器信号
        self.translation_manager.language_changed.connect(self._update_translations)
        
        # 如果父窗口有config_saved信号，连接配置保存信号
        if parent and hasattr(parent, 'config_saved'):
            logger.debug("将上传视图的config_saved信号连接到父窗口")
            self.config_saved.connect(parent.config_saved)
        
        # 上传队列
        self.upload_queue = []
        
        # 加载配置
        if self.config:
            self.load_config(self.config)
        
        # 初始化翻译
        self._update_translations()
        
        logger.info("上传界面初始化完成")
    
    def _create_config_panel(self):
        """创建配置标签页"""
        # 目标频道标签页
        self.channel_tab = QWidget()
        channel_layout = QVBoxLayout(self.channel_tab)
        channel_layout.setContentsMargins(4, 4, 4, 4)
        channel_layout.setSpacing(4)
        
        # 设置标签页的固定尺寸策略
        self.channel_tab.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        # 频道输入
        form_layout = QFormLayout()
        
        self.channel_input = QLineEdit()
        self.channel_input.setPlaceholderText(tr("ui.upload.channels.input_placeholder"))
        form_layout.addRow(tr("ui.upload.channels.input_label"), self.channel_input)
        
        channel_layout.addLayout(form_layout)
        
        # 添加频道按钮
        button_layout = QHBoxLayout()
        self.add_channel_button = QPushButton(tr("ui.upload.channels.add_button"))
        self.remove_channel_button = QPushButton(tr("ui.upload.channels.remove_button"))
        
        button_layout.addWidget(self.add_channel_button)
        button_layout.addWidget(self.remove_channel_button)
        button_layout.addStretch(1)
        
        channel_layout.addLayout(button_layout)
        
        # 频道列表
        self.channel_list_label = QLabel(tr("ui.upload.channels.configured_title"))
        
        self.channel_list = QListWidget()
        self.channel_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.channel_list.setMinimumHeight(70)  # 调整最小高度以适应新的标签页高度
        self.channel_list.setContextMenuPolicy(Qt.CustomContextMenu)  # 设置自定义右键菜单
        self.channel_list.customContextMenuRequested.connect(self._show_context_menu)  # 连接右键菜单事件
        
        channel_layout.addWidget(self.channel_list_label)
        channel_layout.addWidget(self.channel_list, 1)  # 使列表占据所有剩余空间
        
        # 上传选项标签页
        self.options_tab = QWidget()
        options_layout = QVBoxLayout(self.options_tab)
        options_layout.setContentsMargins(4, 4, 4, 4)
        options_layout.setSpacing(4)
        
        # 设置标签页的固定尺寸策略
        self.options_tab.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        # 说明文字选项 - 改为水平布局
        caption_options_layout = QGridLayout()
        caption_options_layout.setHorizontalSpacing(20)  # 增加水平间距
        caption_options_layout.setVerticalSpacing(10)    # 增加垂直间距
        caption_options_layout.setContentsMargins(0, 5, 0, 5)  # 增加上下边距
        
        # 创建互斥的单选选项
        self.use_folder_name_check = QCheckBox(tr("ui.upload.options.use_folder_name"))
        self.use_folder_name_check.setChecked(True)  # 默认选中
        self.use_folder_name_check.setMinimumHeight(25)
        
        self.read_title_txt_check = QCheckBox(tr("ui.upload.options.read_title_txt"))
        self.read_title_txt_check.setChecked(False)
        self.read_title_txt_check.setMinimumHeight(25)
        
        self.send_final_message_check = QCheckBox(tr("ui.upload.options.send_final_message"))
        self.send_final_message_check.setChecked(False)
        self.send_final_message_check.setMinimumHeight(25)
        
        # 将说明文字选项添加到网格布局
        caption_options_layout.addWidget(self.use_folder_name_check, 0, 0)
        caption_options_layout.addWidget(self.read_title_txt_check, 1, 0)
        caption_options_layout.addWidget(self.send_final_message_check, 2, 0)
        
        # 自动生成缩略图选项
        self.auto_thumbnail_check = QCheckBox(tr("ui.upload.options.auto_thumbnail"))
        self.auto_thumbnail_check.setChecked(True)
        self.auto_thumbnail_check.setMinimumHeight(30)
        caption_options_layout.addWidget(self.auto_thumbnail_check, 0, 1)
        
        # 上传延迟选项添加到网格布局
        delay_widget = QWidget()
        delay_layout = QHBoxLayout(delay_widget)
        delay_layout.setContentsMargins(0, 0, 0, 0)
        
        self.delay_label = QLabel(tr("ui.upload.options.upload_delay"))
        self.delay_label.setMinimumWidth(60)
        delay_layout.addWidget(self.delay_label)
        
        self.upload_delay = QDoubleSpinBox()
        self.upload_delay.setRange(0, 60)
        self.upload_delay.setValue(0.5)
        self.upload_delay.setDecimals(1)
        self.upload_delay.setSingleStep(0.1)
        self.upload_delay.setSuffix(f" {tr('ui.upload.options.upload_delay_unit')}")
        self.upload_delay.setMinimumWidth(70)
        delay_layout.addWidget(self.upload_delay)
        delay_layout.addStretch()
        
        delay_widget.setMinimumHeight(30)
        caption_options_layout.addWidget(delay_widget, 1, 1)
        
        # 最后消息HTML文件选择
        final_message_widget = QWidget()
        final_message_layout = QHBoxLayout(final_message_widget)
        final_message_layout.setContentsMargins(0, 0, 0, 0)
        
        self.final_message_html_file = QLineEdit()
        self.final_message_html_file.setReadOnly(True)
        self.final_message_html_file.setPlaceholderText(tr("ui.upload.options.final_message_placeholder"))
        self.final_message_html_file.setEnabled(False)  # 初始状态禁用
        
        self.browse_html_button = QPushButton(tr("ui.upload.options.browse_html"))
        self.browse_html_button.setEnabled(False)  # 初始状态禁用
        
        # 添加网页预览复选框
        self.enable_web_page_preview_check = QCheckBox(tr("ui.upload.options.enable_web_preview"))
        self.enable_web_page_preview_check.setChecked(False)  # 默认不启用
        self.enable_web_page_preview_check.setEnabled(False)  # 初始状态禁用
        
        final_message_layout.addWidget(self.final_message_html_file)
        final_message_layout.addWidget(self.browse_html_button)
        final_message_layout.addWidget(self.enable_web_page_preview_check)
        
        final_message_widget.setMinimumHeight(30)
        caption_options_layout.addWidget(final_message_widget, 2, 1)
        
        options_layout.addLayout(caption_options_layout)
        
        # 自定义说明文字模板部分已移除，保留布局用于说明信息
        caption_info_layout = QVBoxLayout()
        caption_info_layout.setContentsMargins(0, 0, 0, 0)  # 增加顶部间距
        
        self.info_text = QLabel(tr("ui.upload.options.info_text"))
        self.info_text.setWordWrap(True)
        self.info_text.setStyleSheet("font-size: 12px;")
        self.info_text.setMinimumHeight(85)
        self.info_text.setMaximumHeight(110)
        
        caption_info_layout.addWidget(self.info_text)
        options_layout.addLayout(caption_info_layout)
        
        # 将标签页添加到配置面板
        self.config_tabs.addTab(self.channel_tab, tr("ui.upload.tabs.channels"))
        self.config_tabs.addTab(self.options_tab, tr("ui.upload.tabs.options"))
        
        # 修改文件选择器标签页为简单的目录选择
        self.file_selector_tab = QWidget()
        file_selector_layout = QVBoxLayout(self.file_selector_tab)
        file_selector_layout.setContentsMargins(4, 4, 4, 4)
        file_selector_layout.setSpacing(4)
        
        # 设置标签页的固定尺寸策略
        self.file_selector_tab.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        # 添加上传目录选择
        dir_layout = QHBoxLayout()
        
        self.dir_label = QLabel(tr("ui.upload.files.directory_label"))
        dir_layout.addWidget(self.dir_label)
        
        self.path_input = QLineEdit()
        self.path_input.setReadOnly(True)
        self.path_input.setPlaceholderText(tr("ui.upload.files.directory_placeholder"))
        dir_layout.addWidget(self.path_input, 1)
        
        self.browse_button = QPushButton(tr("ui.upload.files.browse_button"))
        dir_layout.addWidget(self.browse_button)
        
        file_selector_layout.addLayout(dir_layout)
        
        # 添加目录结构说明
        self.help_label = QLabel(tr("ui.upload.files.help_text"))
        self.help_label.setWordWrap(True)
        self.help_label.setStyleSheet("font-size: 13px; padding: 10px;")
        
        file_selector_layout.addWidget(self.help_label)
        
        # 添加一个隐藏的填充部件，确保与其他标签页高度一致
        spacer_widget = QWidget()
        spacer_widget.setMinimumHeight(110)  # 减少高度以适应新的标签页高度
        spacer_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        spacer_widget.setStyleSheet("background: transparent;")  # 确保看不见
        file_selector_layout.addWidget(spacer_widget)
        
        # 添加弹性空间，确保控件不会挤压到一起
        file_selector_layout.addStretch(1)
        
        # 将文件选择标签页添加到配置面板
        self.config_tabs.addTab(self.file_selector_tab, tr("ui.upload.tabs.files"))
    
    def _create_upload_panel(self):
        """创建上传状态面板"""
        # 创建下部区域的容器
        upload_container = QWidget()
        upload_container_layout = QVBoxLayout(upload_container)
        upload_container_layout.setContentsMargins(0, 0, 0, 0)  # 移除容器的边距
        upload_container_layout.setSpacing(2)  # 减小间距
        
        # 设置上传容器固定高度和尺寸策略，避免标签页切换时改变高度
        upload_container.setMinimumHeight(230)  # 增加最小高度
        upload_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # 允许垂直扩展
        
        # 上传队列标题和状态
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        self.queue_title = QLabel(f"<b>{tr('ui.upload.queue.title')}</b>")
        self.queue_title.setStyleSheet("font-size: 12px;")
        header_layout.addWidget(self.queue_title)
        
        self.queue_status_label = QLabel(tr("ui.upload.queue.status_waiting", count=0, size="0MB"))
        header_layout.addWidget(self.queue_status_label)
        header_layout.addStretch(1)
        
        upload_container_layout.addLayout(header_layout)
        
        # 上传队列列表
        self.upload_list = QListWidget()
        self.upload_list.setMinimumHeight(170)  # 增加列表最小高度
        upload_container_layout.addWidget(self.upload_list, 1)  # 添加拉伸因子，使其填充可用空间
        
        # 当前进度信息
        progress_layout = QHBoxLayout()
        progress_layout.setContentsMargins(0, 2, 0, 0)
        
        progress_info_layout = QVBoxLayout()
        progress_info_layout.setSpacing(1)
        
        self.current_file_label = QLabel(tr("ui.upload.queue.current_file_none"))
        self.upload_speed_label = QLabel(tr("ui.upload.queue.speed_info_none"))
        
        progress_info_layout.addWidget(self.current_file_label)
        progress_info_layout.addWidget(self.upload_speed_label)
        
        progress_layout.addLayout(progress_info_layout)
        progress_layout.addStretch(1)
        
        upload_container_layout.addLayout(progress_layout)
        
        # 添加到主布局，设置拉伸因子为1，允许队列区域占据更多空间
        self.main_layout.addWidget(upload_container, 1)
    
    def _create_action_buttons(self):
        """创建底部操作按钮"""
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 4, 0, 0)  # 增加与上方组件的间距
        
        self.start_button = QPushButton(tr("ui.upload.buttons.start_upload"))
        self.start_button.setMinimumHeight(36)  # 减小按钮高度
        
        self.stop_button = QPushButton(tr("ui.upload.buttons.stop_upload"))
        self.stop_button.setMinimumHeight(36)
        self.stop_button.setEnabled(False)  # 初始状态下禁用
        
        self.save_config_button = QPushButton(tr("ui.upload.buttons.save_config"))
        
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addWidget(self.save_config_button)
        
        self.main_layout.addLayout(button_layout)
    
    def _connect_signals(self):
        """连接信号和槽"""
        # 连接信号
        self.browse_button.clicked.connect(self._browse_directory)
        self.browse_html_button.clicked.connect(self._browse_html_file)
        self.add_channel_button.clicked.connect(self._add_channel)
        self.remove_channel_button.clicked.connect(self._remove_channels)
        
        # 说明文字选项互斥逻辑
        self.use_folder_name_check.clicked.connect(self._handle_caption_option)
        self.read_title_txt_check.clicked.connect(self._handle_caption_option)
        self.send_final_message_check.clicked.connect(self._handle_caption_option)
        
        # 上传控制按钮
        self.start_button.clicked.connect(self._start_upload)
        self.stop_button.clicked.connect(self._stop_upload)
        self.save_config_button.clicked.connect(self._save_config)
        
        # 如果有父窗口，尝试连接config_saved信号
        parent = self.parent()
        if parent and hasattr(parent, 'save_config'):
            self.config_saved.connect(parent.save_config)
    
    def _handle_caption_option(self):
        """处理说明文字选项的互斥和启用/禁用HTML文件选择器"""
        sender = self.sender()
        
        # 处理use_folder_name和read_title_txt的互斥关系
        if sender in [self.use_folder_name_check, self.read_title_txt_check]:
            # 确保至少有一个选项被选中
            if not sender.isChecked():
                sender.setChecked(True)
                return
                
            # 根据点击的选项取消选中另一个选项，但不影响send_final_message_check
            if sender == self.use_folder_name_check and sender.isChecked():
                self.read_title_txt_check.setChecked(False)
            elif sender == self.read_title_txt_check and sender.isChecked():
                self.use_folder_name_check.setChecked(False)
        
        # 单独处理send_final_message_check的启用/禁用HTML文件选择器
        elif sender == self.send_final_message_check:
            # 只处理HTML文件选择器的启用/禁用
            if sender.isChecked():
                self.final_message_html_file.setFocus()
            
        # 最后消息HTML文件选择框和浏览按钮的启用状态
        is_enabled = self.send_final_message_check.isChecked()
        self.final_message_html_file.setEnabled(is_enabled)
        self.browse_html_button.setEnabled(is_enabled)
        self.enable_web_page_preview_check.setEnabled(is_enabled)
    
    def _browse_directory(self):
        """浏览文件夹对话框"""
        current_path = self.path_input.text() or QDir.homePath()
        directory = QFileDialog.getExistingDirectory(
            self, 
            tr("ui.upload.directory_dialog.title"),
            current_path
        )
        
        if directory:
            self.path_input.setText(directory)
            
            # 如果存在配置，更新配置中的目录路径
            if isinstance(self.config, dict) and 'UPLOAD' in self.config:
                self.config['UPLOAD']['directory'] = directory
    
    def _browse_html_file(self):
        """浏览HTML文件选择对话框"""
        current_path = os.path.dirname(self.final_message_html_file.text()) or QDir.homePath()
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            tr("ui.upload.options.final_message_file"),
            current_path,
            tr("ui.upload.file_types.html")
        )
        
        if file_path:
            self.final_message_html_file.setText(file_path)
            
            # 如果存在配置，更新配置中的HTML文件路径
            if isinstance(self.config, dict) and 'UPLOAD' in self.config:
                if 'options' not in self.config['UPLOAD']:
                    self.config['UPLOAD']['options'] = {}
                self.config['UPLOAD']['options']['final_message_html_file'] = file_path
    
    def _add_channel(self):
        """添加频道到列表"""
        channel = self.channel_input.text().strip()
        
        if not channel:
            QMessageBox.warning(self, tr("ui.upload.messages.warning"), 
                              tr("ui.upload.messages.no_channels"))
            return
        
        # 检查是否已存在相同频道
        for i in range(self.channel_list.count()):
            if self.channel_list.item(i).text() == channel:
                QMessageBox.information(self, tr("ui.upload.messages.info"), 
                                      tr("ui.upload.messages.channel_exists"))
                return
        
        # 添加到列表
        self.channel_list.addItem(channel)
        
        # 清空输入
        self.channel_input.clear()
    
    def _remove_channels(self):
        """删除选中的频道"""
        selected_items = self.channel_list.selectedItems()
        
        if not selected_items:
            QMessageBox.information(self, tr("ui.upload.messages.info"), 
                                  tr("ui.upload.messages.select_channels_to_remove"))
            return
        
        # 删除选中的频道
        for item in reversed(selected_items):
            row = self.channel_list.row(item)
            self.channel_list.takeItem(row)
    
    def _start_upload(self):
        """开始上传操作"""
        # 检查是否有目标频道
        if self.channel_list.count() == 0:
            QMessageBox.warning(self, tr("ui.upload.messages.warning"), 
                              tr("ui.upload.messages.no_channels"))
            return
        
        # 检查上传目录
        upload_dir = self.path_input.text()
        if not upload_dir or not os.path.exists(upload_dir) or not os.path.isdir(upload_dir):
            QMessageBox.warning(self, tr("ui.upload.messages.warning"), 
                              tr("ui.upload.messages.invalid_directory"))
            return
        
        # 检查是否设置了uploader实例
        if not hasattr(self, 'uploader') or self.uploader is None:
            QMessageBox.warning(self, tr("ui.upload.messages.warning"), 
                              tr("ui.upload.messages.uploader_not_initialized"))
            return
        
        # 更新UI状态
        self.current_file_label.setText(tr("ui.upload.status.preparing"))
        self.upload_speed_label.setText(tr("ui.upload.status.initializing"))
        
        # 更新按钮状态
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        
        # 清空上传列表
        self.upload_list.clear()
        self.upload_queue = []
        
        # 创建一个新的事件循环运行器来执行上传任务
        from src.utils.async_utils import run_async_task
        run_async_task(self._run_upload_task())
    
    def _stop_upload(self):
        """停止上传操作"""
        if hasattr(self, 'uploader') and self.uploader:
            # 如果存在uploader实例，调用其停止方法
            if hasattr(self.uploader, 'stop') and callable(self.uploader.stop):
                self.uploader.stop()
                logger.info("上传操作已停止")
            elif hasattr(self.uploader, 'cancel') and callable(self.uploader.cancel):
                self.uploader.cancel()
                logger.info("上传操作已取消")
        
        # 更新UI状态
        self.current_file_label.setText(tr("ui.upload.status.stopped"))
        self.upload_speed_label.setText(tr("ui.upload.queue.speed_info_none"))
        
        # 恢复按钮状态
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
    
    def _save_config(self):
        """保存当前配置"""
        # 检查是否有目标频道
        if self.channel_list.count() == 0:
            QMessageBox.warning(self, tr("ui.upload.messages.warning"), 
                              tr("ui.upload.messages.no_channels"))
            return
        
        # 检查上传目录
        upload_dir = self.path_input.text()
        if not upload_dir:
            upload_dir = 'uploads'  # 使用默认目录
        
        # 收集目标频道
        target_channels = []
        for i in range(self.channel_list.count()):
            target_channels.append(self.channel_list.item(i).text())
        
        # 收集上传选项
        upload_options = {
            'use_folder_name': self.use_folder_name_check.isChecked(),
            'read_title_txt': self.read_title_txt_check.isChecked(),
            'send_final_message': self.send_final_message_check.isChecked(),
            'auto_thumbnail': self.auto_thumbnail_check.isChecked(),
            'final_message_html_file': self.final_message_html_file.text(),
            'enable_web_page_preview': self.enable_web_page_preview_check.isChecked()
        }
        
        # 创建上传配置
        upload_config = {
            'target_channels': target_channels,
            'directory': upload_dir,
            'caption_template': '{filename}',  # 保持默认模板
            'delay_between_uploads': round(float(self.upload_delay.value()), 1),  # 四舍五入到一位小数
            'options': upload_options
        }
        
        # 组织完整配置，确保保留现有的其他配置项（特别是主题设置）
        updated_config = {}
        if isinstance(self.config, dict):
            updated_config = self.config.copy()  # 复制当前配置
        
        # 获取主题管理器，确保保留当前主题设置
        try:
            from src.utils.theme_manager import get_theme_manager
            theme_manager = get_theme_manager()
            current_theme = theme_manager.get_current_theme_name()
            
            # 确保UI配置部分存在，并保留当前主题
            if 'UI' not in updated_config:
                updated_config['UI'] = {}
            
            # 保留当前应用的主题设置，防止被覆盖
            updated_config['UI']['theme'] = current_theme
            logger.debug(f"保存配置时保留当前主题设置: {current_theme}")
            
        except Exception as e:
            logger.warning(f"获取当前主题设置时出错: {e}")
        
        # 更新UPLOAD部分
        updated_config['UPLOAD'] = upload_config
        
        # 发送配置保存信号
        logger.debug("向主窗口发送配置保存信号，更新上传配置")
        self.config_saved.emit(updated_config)
        
        # 显示成功消息
        QMessageBox.information(self, tr("ui.upload.messages.info"), 
                              tr("ui.upload.messages.config_saved"))
        
        # 更新本地配置引用
        self.config = updated_config
    
    def _update_queue_status(self):
        """更新队列状态"""
        total_files = len(self.upload_queue)
        total_size = sum(item['size'] for item in self.upload_queue)
        
        self.queue_status_label.setText(tr("ui.upload.queue.status_waiting", 
                                          count=total_files, 
                                          size=self._format_size(total_size)))
    
    def _format_size(self, size_bytes):
        """格式化文件大小
        
        Args:
            size_bytes: 文件大小（字节）
            
        Returns:
            str: 格式化后的大小字符串
        """
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f}KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f}MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f}GB"
    
    def _format_time(self, seconds):
        """格式化时间
        
        Args:
            seconds: 秒数
            
        Returns:
            str: 格式化后的时间字符串
        """
        if seconds < 60:
            return f"{seconds:.0f}秒"
        elif seconds < 3600:
            minutes = seconds // 60
            seconds = seconds % 60
            return f"{minutes:.0f}分{seconds:.0f}秒"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            seconds = seconds % 60
            return f"{hours:.0f}时{minutes:.0f}分{seconds:.0f}秒"
    
    def update_upload_progress(self, file_path, progress, speed, remaining_time):
        """更新上传进度
        
        Args:
            file_path: 文件路径
            progress: 进度 (0-100)
            speed: 上传速度 (bytes/s)
            remaining_time: 剩余时间 (秒)
        """
        # 更新当前文件标签
        self.current_file_label.setText(tr("ui.upload.queue.current_file", 
                                          filename=os.path.basename(file_path)))
        
        # 更新速度和剩余时间
        speed_str = self._format_size(speed) + "/s"
        time_str = self._format_time(remaining_time)
        
        self.upload_speed_label.setText(tr("ui.upload.queue.speed_info", 
                                         speed=speed_str, time=time_str))
        
        # 更新列表项进度
        for i in range(self.upload_list.count()):
            item = self.upload_list.item(i)
            if item.data(Qt.UserRole) == file_path:
                current_text = item.text().split(" - ")[0] + " - " + item.text().split(" - ")[1]
                item.setText(f"{current_text} - {progress}%")
                break
    
    def upload_completed(self, file_path, success):
        """文件上传完成
        
        Args:
            file_path: 文件路径
            success: 是否成功
        """
        # 更新列表项状态
        for i in range(self.upload_list.count()):
            item = self.upload_list.item(i)
            if item.data(Qt.UserRole) == file_path:
                current_text = item.text().split(" - ")[0] + " - " + item.text().split(" - ")[1]
                status = "✓ 成功" if success else "✗ 失败"
                item.setText(f"{current_text} - {status}")
                break
    
    @Slot()
    def all_uploads_completed(self):
        """所有上传任务完成"""
        # 重置状态
        self.current_file_label.setText(tr("ui.upload.status.all_completed"))
        self.upload_speed_label.setText(tr("ui.upload.queue.speed_info_none"))
        
        # 恢复按钮状态
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        
        # 显示完成消息
        QMessageBox.information(self, tr("ui.upload.messages.upload_completed"), 
                              tr("ui.upload.status.all_completed"))
    
    def load_config(self, config):
        """从配置加载UI状态
        
        Args:
            config: 配置字典
        """
        # 保存配置引用
        self.config = config
        
        # 清空现有项目
        self.channel_list.clear()
        
        # 检查上传配置是否存在
        if 'UPLOAD' not in config:
            logger.warning("配置中不存在UPLOAD部分")
            return
            
        upload_config = config['UPLOAD']
        
        # 加载目标频道
        target_channels = upload_config.get('target_channels', [])
        for channel in target_channels:
            self.channel_list.addItem(channel)
        
        # 加载上传目录路径
        directory = upload_config.get('directory', 'uploads')
        self.path_input.setText(directory)
        
        # 加载上传延迟
        delay_between_uploads = upload_config.get('delay_between_uploads', 0.5)
        # 确保上传延迟能以小数形式加载
        if isinstance(delay_between_uploads, (int, float)):
            self.upload_delay.setValue(float(delay_between_uploads))
        else:
            try:
                self.upload_delay.setValue(float(delay_between_uploads))
            except (ValueError, TypeError):
                self.upload_delay.setValue(0.5)
        
        # 加载其他选项
        options = upload_config.get('options', {})
        if options:
            # 加载说明文字选项 - 先重置所有复选框
            self.use_folder_name_check.setChecked(False)
            self.read_title_txt_check.setChecked(False)
            
            # 明确转换为布尔值，防止字符串类型影响判断
            use_folder_name = bool(options.get('use_folder_name', True))
            read_title_txt = bool(options.get('read_title_txt', False))
            
            # 根据配置设置说明文字复选框状态，保持互斥性
            if read_title_txt:
                self.read_title_txt_check.setChecked(True)
            elif use_folder_name:
                self.use_folder_name_check.setChecked(True)
            else:
                # 默认至少选中一个
                self.use_folder_name_check.setChecked(True)
            
            # 单独处理发送最终消息选项，它不应该与其他选项互斥
            send_final_message = bool(options.get('send_final_message', False))
            self.send_final_message_check.setChecked(send_final_message)
            
            # 处理HTML文件选择框和浏览按钮的启用状态
            self.final_message_html_file.setEnabled(send_final_message)
            self.browse_html_button.setEnabled(send_final_message)
            self.enable_web_page_preview_check.setEnabled(send_final_message)
            
            # 加载HTML文件路径
            html_file_path = options.get('final_message_html_file', '')
            # 始终设置HTML文件路径，即使send_final_message为False
            if html_file_path:
                self.final_message_html_file.setText(html_file_path)
            else:
                self.final_message_html_file.setText("")
            
            # 加载网页预览设置
            enable_web_page_preview = bool(options.get('enable_web_page_preview', False))
            self.enable_web_page_preview_check.setChecked(enable_web_page_preview)
            
            # 设置自动缩略图选项
            auto_thumbnail = options.get('auto_thumbnail', True)
            self.auto_thumbnail_check.setChecked(auto_thumbnail)
            
            # 记录日志
            logger.debug(f"已从配置加载选项: use_folder_name={use_folder_name}, read_title_txt={read_title_txt}, send_final_message={send_final_message}, enable_web_page_preview={enable_web_page_preview}")
        
        logger.debug("上传配置已成功加载")

    def set_uploader(self, uploader):
        """设置上传器实例
        
        Args:
            uploader: 上传器实例
        """
        if not uploader:
            logger.warning("上传器实例为空，无法设置")
            return
            
        self.uploader = uploader
        logger.debug("上传视图已接收上传器实例")
        
        # 连接信号
        self._connect_uploader_signals()
    
    def _connect_uploader_signals(self):
        """连接上传器信号到UI更新"""
        if not hasattr(self, 'uploader') or self.uploader is None:
            logger.warning("上传器不存在，无法连接信号")
            return
            
        # 连接上传器事件处理器
        try:
            # 如果uploader实现了事件发射器接口
            if hasattr(self.uploader, 'add_event_listener'):
                # 连接进度更新事件
                self.uploader.add_event_listener("progress", self._handle_progress_update)
                # 连接文件上传完成事件
                self.uploader.add_event_listener("file_uploaded", self._handle_file_uploaded)
                # 连接全部上传完成事件
                self.uploader.add_event_listener("complete", self._handle_upload_completed)
                # 连接错误事件
                self.uploader.add_event_listener("error", self._handle_upload_error)
                # 连接文件已上传事件
                self.uploader.add_event_listener("file_already_uploaded", self._handle_file_already_uploaded)
                
                logger.debug("已成功连接上传器事件")
            
            # 如果uploader直接实现了Qt信号
            elif hasattr(self.uploader, 'progress_updated'):
                self.uploader.progress_updated.connect(self._handle_progress_update)
                self.uploader.media_uploaded.connect(self._handle_file_uploaded)
                self.uploader.all_uploads_completed.connect(self.all_uploads_completed)
                self.uploader.error_occurred.connect(self._handle_upload_error)
                
                # 检查是否有file_already_uploaded信号
                if hasattr(self.uploader, 'file_already_uploaded'):
                    self.uploader.file_already_uploaded.connect(self._handle_file_already_uploaded)
                
                logger.debug("已成功连接上传器Qt信号")
        
        except Exception as e:
            logger.error(f"连接上传器信号时出错: {e}")
            import traceback
            logger.debug(f"错误详情:\n{traceback.format_exc()}")
    
    def _handle_progress_update(self, progress, current=None, total=None, **kwargs):
        """处理上传进度更新事件
        
        Args:
            progress: 进度百分比或进度信息
            current: 当前处理的索引(可选)
            total: 总数(可选)
            **kwargs: 其他参数
        """
        # 更新进度信息
        if current is not None and total is not None:
            self.queue_status_label.setText(f"上传进度: {current+1}/{total} ({int(progress)}%)")
        else:
            self.queue_status_label.setText(f"上传进度: {int(progress)}%")
        
        # 如果有文件名信息，更新当前处理的文件
        if 'file_path' in kwargs:
            file_name = os.path.basename(kwargs['file_path'])
            self.current_file_label.setText(f"当前文件: {file_name}")
        
        # 如果有速度信息，更新速度显示
        if 'speed' in kwargs and 'remaining_time' in kwargs:
            speed = self._format_size(kwargs['speed']) + "/s" if kwargs['speed'] > 0 else "- B/s"
            time_left = self._format_time(kwargs['remaining_time']) if kwargs['remaining_time'] > 0 else "-"
            self.upload_speed_label.setText(f"速度: {speed} | 剩余时间: {time_left}")

    def _handle_file_uploaded(self, file_path, success=True, **kwargs):
        """处理单个文件上传完成事件
        
        Args:
            file_path: 文件路径或包含文件信息的字典
            success: 是否成功(默认为True)
            **kwargs: 其他参数
        """
        try:
            # 判断参数类型并提取文件名
            if isinstance(file_path, dict):
                # 如果是字典，从字典中获取文件名
                if 'file_name' in file_path:
                    file_name = file_path['file_name']
                else:
                    # 尝试从字典中其他可能的键获取文件名
                    if 'chat_id' in file_path and 'media_count' in file_path:
                        file_name = tr("ui.upload.progress.media_group", count=file_path['media_count'])
                    else:
                        file_name = tr("ui.upload.progress.unknown_file")
                
                # 记录更详细的日志，帮助调试
                logger.debug(f"从字典中提取文件名: {file_name}, 字典内容: {file_path}")
            else:
                # 如果是字符串路径，直接获取文件名
                file_name = os.path.basename(file_path)
            
            # 添加到上传列表
            item = QListWidgetItem()
            status = tr("ui.upload.status.success") if success else tr("ui.upload.status.error")
            item.setText(f"{file_name} - {status}")
            item.setData(Qt.UserRole, file_path)
            self.upload_list.addItem(item)
            
            # 滚动到底部显示最新项
            self.upload_list.scrollToBottom()
            
            logger.debug(f"文件上传{'成功' if success else '失败'}: {file_name}")
        except Exception as e:
            # 捕获并记录任何错误，确保不会中断上传过程
            logger.error(f"处理文件上传完成事件时出错: {str(e)}")
            logger.debug(f"错误详情: file_path类型={type(file_path)}, 内容={file_path}")

    def _handle_upload_completed(self, success=True, **kwargs):
        """处理所有上传完成事件
        
        Args:
            success: 整体上传是否成功
            **kwargs: 其他参数，可能包含total_files, total_time等
        """
        # 更新UI状态
        status_text = tr("ui.upload.status.upload_success") if success else tr("ui.upload.status.upload_error")
        self.current_file_label.setText(status_text)
        
        # 提取上传统计信息
        total_files = kwargs.get('total_files', 0)
        total_time = kwargs.get('total_time', 0)
        
        if total_files > 0 and total_time > 0:
            avg_time = total_time / total_files
            self.upload_speed_label.setText(tr("ui.upload.progress.files_uploaded", 
                                             count=total_files, time=total_time, avg=avg_time))
        else:
            self.upload_speed_label.setText(tr("ui.upload.progress.upload_complete"))
        
        # 恢复按钮状态 - 在异步方法中已经处理，这里不重复处理
        # self.start_button.setEnabled(True)
        # self.stop_button.setEnabled(False)
        
        logger.info(f"所有上传{'成功' if success else '完成但有错误'}，总共 {total_files} 个文件")

    def _handle_upload_error(self, error, **kwargs):
        """处理上传错误事件
        
        Args:
            error: 错误信息
            **kwargs: 其他参数
        """
        error_message = tr("ui.upload.messages.upload_error_detail", error=str(error))
        
        # 更新UI状态
        self.current_file_label.setText(tr("ui.upload.status.upload_error"))
        self.upload_speed_label.setText(error_message)
        
        # 恢复按钮状态 - 在异步方法中已经处理，这里不重复处理
        # self.start_button.setEnabled(True)
        # self.stop_button.setEnabled(False)
        
        logger.error(error_message)

    def _handle_file_already_uploaded(self, file_data):
        """处理文件已上传事件
        
        Args:
            file_data: 文件数据字典，包含file_name, file_path, file_hash等信息
        """
        try:
            # 提取文件信息
            if isinstance(file_data, dict):
                file_name = file_data.get('file_name', tr("ui.upload.progress.unknown_file"))
                file_hash = file_data.get('file_hash', '')
                
                # 格式化文件哈希显示
                hash_display = f"(哈希: {file_hash[:8]}...)" if file_hash else ""
                
                # 添加到上传列表，标记为已存在
                item = QListWidgetItem()
                item.setText(f"{file_name} {hash_display} - {tr('ui.upload.status.exists')}")
                if 'file_path' in file_data:
                    item.setData(Qt.UserRole, file_data['file_path'])
                self.upload_list.addItem(item)
                
                # 滚动到底部显示最新项
                self.upload_list.scrollToBottom()
                
                logger.debug(f"文件已存在，跳过上传: {file_name}")
            else:
                logger.warning(f"收到非字典类型的文件已上传事件数据: {type(file_data)}")
        
        except Exception as e:
            # 捕获并记录任何错误，确保不会中断上传过程
            logger.error(f"处理文件已上传事件时出错: {str(e)}")
            logger.debug(f"错误详情: file_data类型={type(file_data)}, 内容={file_data}")

    async def _run_upload_task(self):
        """运行上传任务的异步方法"""
        try:
            # 确保上传器能读取到最新配置
            self.uploader.config = self.config.copy() if isinstance(self.config, dict) else {}
            self.uploader.upload_config = self.uploader.config.get('UPLOAD', {})
            
            # 调用uploader的upload_local_files方法执行上传
            await self.uploader.upload_local_files()
            
            # 上传完成后使用Qt信号更新UI，而不是直接调用
            # 通过Qt的信号/槽机制安全地在主线程更新UI
            QMetaObject.invokeMethod(self, "all_uploads_completed", Qt.QueuedConnection)
            
        except Exception as e:
            # 捕获并处理可能的异常
            error_message = tr("ui.upload.messages.upload_error_detail", error=str(e))
            logger.error(error_message)
            
            # 使用Qt信号在主线程中更新UI
            # 避免在异步任务中直接操作UI
            QMetaObject.invokeMethod(
                self, 
                "_update_error_ui", 
                Qt.QueuedConnection,
                Q_ARG(str, error_message)
            )
    
    @Slot(str)
    def _update_error_ui(self, error_message):
        """在主线程中更新UI显示错误信息
        
        Args:
            error_message: 错误信息
        """
        # 更新UI状态
        self.current_file_label.setText(tr("ui.upload.status.upload_error"))
        self.upload_speed_label.setText("请检查日志获取详细信息")
        
        # 恢复按钮状态
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        
        # 显示错误对话框
        QMessageBox.critical(self, tr("ui.upload.messages.upload_error"), error_message)

    def _show_context_menu(self, pos):
        """显示右键菜单
        
        Args:
            pos: 鼠标位置
        """
        # 确保有选中的项目
        current_item = self.channel_list.itemAt(pos)
        if not current_item:
            return
        
        # 创建菜单
        context_menu = QMenu(self)
        
        # 添加菜单项
        edit_action = context_menu.addAction(tr("ui.upload.context_menu.edit"))
        delete_action = context_menu.addAction(tr("ui.upload.context_menu.delete"))
        
        # 显示菜单并获取用户选择的操作
        action = context_menu.exec(QCursor.pos())
        
        # 处理用户选择
        if action == edit_action:
            self._edit_channel(current_item)
        elif action == delete_action:
            # 删除操作直接调用已有的删除方法
            self._remove_channels()

    def _edit_channel(self, item):
        """编辑频道
        
        Args:
            item: 要编辑的列表项
        """
        # 获取项目索引
        row = self.channel_list.row(item)
        
        # 获取频道数据
        channel_text = item.text()
        
        # 创建编辑对话框
        edit_dialog = QDialog(self)
        edit_dialog.setWindowTitle(tr("ui.upload.edit_dialog.title"))
        edit_dialog.setMinimumWidth(400)
        
        # 对话框布局
        dialog_layout = QVBoxLayout(edit_dialog)
        
        # 表单布局
        form_layout = QFormLayout()
        
        # 频道输入
        channel_input = QLineEdit(channel_text)
        form_layout.addRow(tr("ui.upload.edit_dialog.channel_label"), channel_input)
        
        # 添加表单布局到对话框
        dialog_layout.addLayout(form_layout)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        save_button = QPushButton(tr("ui.upload.edit_dialog.save"))
        cancel_button = QPushButton(tr("ui.upload.edit_dialog.cancel"))
        
        button_layout.addStretch(1)
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        
        dialog_layout.addLayout(button_layout)
        
        # 连接按钮信号
        save_button.clicked.connect(edit_dialog.accept)
        cancel_button.clicked.connect(edit_dialog.reject)
        
        # 显示对话框并处理结果
        if edit_dialog.exec() == QDialog.Accepted:
            try:
                # 收集编辑后的数据
                new_channel = channel_input.text().strip()
                
                # 验证输入
                if not new_channel:
                    raise ValueError(tr("ui.upload.edit_dialog.empty_channel"))
                
                # 检查是否已存在相同频道（排除当前项）
                for i in range(self.channel_list.count()):
                    if i != row and self.channel_list.item(i).text() == new_channel:
                        raise ValueError(tr("ui.upload.edit_dialog.channel_exists"))
                
                # 更新列表项
                item.setText(new_channel)
                
            except ValueError as e:
                QMessageBox.warning(self, tr("ui.upload.edit_dialog.input_error"), str(e))

    def _update_translations(self):
        """更新界面翻译"""
        try:
            # 更新标签页标题
            self.config_tabs.setTabText(0, tr("ui.upload.tabs.channels"))
            self.config_tabs.setTabText(1, tr("ui.upload.tabs.options"))
            self.config_tabs.setTabText(2, tr("ui.upload.tabs.files"))
            
            # 更新频道标签页
            self.channel_input.setPlaceholderText(tr("ui.upload.channels.input_placeholder"))
            self.add_channel_button.setText(tr("ui.upload.channels.add_button"))
            self.remove_channel_button.setText(tr("ui.upload.channels.remove_button"))
            self.channel_list_label.setText(tr("ui.upload.channels.configured_title"))
            
            # 更新选项标签页
            self.use_folder_name_check.setText(tr("ui.upload.options.use_folder_name"))
            self.read_title_txt_check.setText(tr("ui.upload.options.read_title_txt"))
            self.send_final_message_check.setText(tr("ui.upload.options.send_final_message"))
            self.auto_thumbnail_check.setText(tr("ui.upload.options.auto_thumbnail"))
            self.delay_label.setText(tr("ui.upload.options.upload_delay"))
            self.upload_delay.setSuffix(f" {tr('ui.upload.options.upload_delay_unit')}")
            self.final_message_html_file.setPlaceholderText(tr("ui.upload.options.final_message_placeholder"))
            self.browse_html_button.setText(tr("ui.upload.options.browse_html"))
            self.enable_web_page_preview_check.setText(tr("ui.upload.options.enable_web_preview"))
            self.info_text.setText(tr("ui.upload.options.info_text"))
            
            # 更新文件标签页
            self.dir_label.setText(tr("ui.upload.files.directory_label"))
            self.path_input.setPlaceholderText(tr("ui.upload.files.directory_placeholder"))
            self.browse_button.setText(tr("ui.upload.files.browse_button"))
            self.help_label.setText(tr("ui.upload.files.help_text"))
            
            # 更新上传队列标题
            self.queue_title.setText(f"<b>{tr('ui.upload.queue.title')}</b>")
            
            # 更新按钮
            self.start_button.setText(tr("ui.upload.buttons.start_upload"))
            self.stop_button.setText(tr("ui.upload.buttons.stop_upload"))
            self.save_config_button.setText(tr("ui.upload.buttons.save_config"))
            
            # 更新队列状态
            self._update_queue_status()
            
            # 更新当前状态显示
            if hasattr(self, 'current_file_label') and self.current_file_label.text() == "当前文件: -":
                self.current_file_label.setText(tr("ui.upload.queue.current_file_none"))
            if hasattr(self, 'upload_speed_label') and self.upload_speed_label.text() == "速度: - | 剩余时间: -":
                self.upload_speed_label.setText(tr("ui.upload.queue.speed_info_none"))
            
            logger.debug("上传界面翻译已更新")
            
        except Exception as e:
            logger.error(f"更新上传界面翻译时出错: {e}")
            import traceback
            logger.debug(f"错误详情:\n{traceback.format_exc()}") 