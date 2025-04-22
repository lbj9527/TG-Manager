"""
TG-Manager 上传界面
实现本地媒体文件上传到Telegram频道的功能
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QCheckBox, QPushButton,
    QGroupBox, QScrollArea, QSpinBox, QGridLayout,
    QListWidget, QListWidgetItem, QFileDialog, QMessageBox,
    QTextEdit, QSizePolicy, QTabWidget, QDoubleSpinBox
)
from PySide6.QtCore import Qt, Signal, Slot, QSize, QDir
from PySide6.QtGui import QIcon

from pathlib import Path
import os
from src.utils.logger import get_logger
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
        
        # 设置布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(2)  # 减小布局间距
        self.main_layout.setContentsMargins(4, 2, 4, 4)  # 减小上方边距
        self.setLayout(self.main_layout)
        
        # 设置统一的组框样式
        self.setStyleSheet("""
            QGroupBox { 
                font-weight: bold; 
                padding-top: 2px; 
                margin-top: 0.5em; 
            }
            QTabWidget::pane {
                border: 1px solid #444;
                padding: 1px;
            }
            QTabBar::tab {
                padding: 3px 8px;
            }
        """)
        
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
        
        # 如果父窗口有config_saved信号，连接配置保存信号
        if parent and hasattr(parent, 'config_saved'):
            logger.debug("将上传视图的config_saved信号连接到父窗口")
            self.config_saved.connect(parent.config_saved)
        
        # 上传队列
        self.upload_queue = []
        
        # 加载配置
        if self.config:
            self.load_config(self.config)
        
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
        self.channel_input.setPlaceholderText("频道链接或ID (例如: https://t.me/example 或 -1001234567890)")
        form_layout.addRow("目标频道:", self.channel_input)
        
        channel_layout.addLayout(form_layout)
        
        # 添加频道按钮
        button_layout = QHBoxLayout()
        self.add_channel_button = QPushButton("添加频道")
        self.remove_channel_button = QPushButton("删除所选")
        
        button_layout.addWidget(self.add_channel_button)
        button_layout.addWidget(self.remove_channel_button)
        button_layout.addStretch(1)
        
        channel_layout.addLayout(button_layout)
        
        # 频道列表
        channel_list_label = QLabel("已配置目标频道:")
        
        self.channel_list = QListWidget()
        self.channel_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.channel_list.setMinimumHeight(70)  # 调整最小高度以适应新的标签页高度
        
        channel_layout.addWidget(channel_list_label)
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
        self.use_folder_name_check = QCheckBox("使用文件夹名称作为说明文字")
        self.use_folder_name_check.setChecked(True)  # 默认选中
        self.use_folder_name_check.setMinimumHeight(25)
        
        self.read_title_txt_check = QCheckBox("读取title.txt文件作为说明文字")
        self.read_title_txt_check.setChecked(False)
        self.read_title_txt_check.setMinimumHeight(25)
        
        self.use_custom_template_check = QCheckBox("使用自定义作为说明文字模板")
        self.use_custom_template_check.setChecked(False)
        self.use_custom_template_check.setMinimumHeight(25)
        
        # 将说明文字选项添加到网格布局
        caption_options_layout.addWidget(self.use_folder_name_check, 0, 0)
        caption_options_layout.addWidget(self.read_title_txt_check, 1, 0)
        caption_options_layout.addWidget(self.use_custom_template_check, 2, 0)
        
        # 自动生成缩略图选项
        self.auto_thumbnail_check = QCheckBox("自动生成视频缩略图")
        self.auto_thumbnail_check.setChecked(True)
        self.auto_thumbnail_check.setMinimumHeight(30)
        caption_options_layout.addWidget(self.auto_thumbnail_check, 0, 1)
        
        # 上传延迟选项添加到网格布局
        delay_widget = QWidget()
        delay_layout = QHBoxLayout(delay_widget)
        delay_layout.setContentsMargins(0, 0, 0, 0)
        
        delay_label = QLabel("上传延迟:")
        delay_label.setMinimumWidth(60)
        delay_layout.addWidget(delay_label)
        
        self.upload_delay = QDoubleSpinBox()
        self.upload_delay.setRange(0, 60)
        self.upload_delay.setValue(0.5)
        self.upload_delay.setDecimals(1)
        self.upload_delay.setSingleStep(0.1)
        self.upload_delay.setSuffix(" 秒")
        self.upload_delay.setMinimumWidth(70)
        delay_layout.addWidget(self.upload_delay)
        delay_layout.addStretch()
        
        delay_widget.setMinimumHeight(30)
        caption_options_layout.addWidget(delay_widget, 1, 1)
        
        options_layout.addLayout(caption_options_layout)
        
        # 自定义说明文字模板
        caption_template_layout = QVBoxLayout()
        caption_template_layout.setContentsMargins(0, 10, 0, 0)  # 增加顶部间距
        
        caption_template_label = QLabel("自定义说明文字模板:")
        caption_template_label.setStyleSheet("font-weight: bold;")  # 加粗标签文字
        caption_template_label.setMinimumHeight(25)  # 设置标签高度
        caption_template_layout.addWidget(caption_template_label)
        
        self.caption_template = QTextEdit()
        self.caption_template.setPlaceholderText("可用变量:\n{filename} - 文件名\n{foldername} - 文件夹名称\n{datetime} - 当前日期时间\n{index} - 文件序号")
        # 减小高度以适应新的标签页高度
        self.caption_template.setMinimumHeight(85)
        self.caption_template.setMaximumHeight(110)
        # 设置更适合文本编辑的尺寸策略
        self.caption_template.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        
        # 如果未选择自定义模板选项，则禁用编辑区
        self.caption_template.setEnabled(False)
        
        # 设置文本编辑区样式
        self.caption_template.setStyleSheet("""
            QTextEdit {
                border: 1px solid #555;
                border-radius: 3px;
                padding: 5px;
            }
        """)
        
        caption_template_layout.addWidget(self.caption_template)
        options_layout.addLayout(caption_template_layout)
        
        # 将标签页添加到配置面板
        self.config_tabs.addTab(self.channel_tab, "目标频道")
        self.config_tabs.addTab(self.options_tab, "上传选项")
        
        # 修改文件选择器标签页为简单的目录选择
        self.file_selector_tab = QWidget()
        file_selector_layout = QVBoxLayout(self.file_selector_tab)
        file_selector_layout.setContentsMargins(4, 4, 4, 4)
        file_selector_layout.setSpacing(4)
        
        # 设置标签页的固定尺寸策略
        self.file_selector_tab.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        # 添加上传目录选择
        dir_layout = QHBoxLayout()
        
        dir_label = QLabel("上传目录:")
        dir_layout.addWidget(dir_label)
        
        self.path_input = QLineEdit()
        self.path_input.setReadOnly(True)
        self.path_input.setPlaceholderText("请选择上传文件所在目录")
        dir_layout.addWidget(self.path_input, 1)
        
        self.browse_button = QPushButton("浏览...")
        dir_layout.addWidget(self.browse_button)
        
        file_selector_layout.addLayout(dir_layout)
        
        # 添加目录结构说明
        help_label = QLabel(
            "提示: 上传目录中的每个子文件夹将作为一个媒体组上传。\n"
            "如果子文件夹中有多个文件，则作为媒体组发送；如果只有一个文件，则单独发送。\n"
            "每个子文件夹中可以放置名为title.txt的文件作为上传说明文本。\n"
            "如果上传目录没有子文件夹，则所有文件作为单独的消息上传。"
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: #666; font-size: 11px; padding: 10px;")
        
        file_selector_layout.addWidget(help_label)
        
        # 添加一个隐藏的填充部件，确保与其他标签页高度一致
        spacer_widget = QWidget()
        spacer_widget.setMinimumHeight(110)  # 减少高度以适应新的标签页高度
        spacer_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        spacer_widget.setStyleSheet("background: transparent;")  # 确保看不见
        file_selector_layout.addWidget(spacer_widget)
        
        # 添加弹性空间，确保控件不会挤压到一起
        file_selector_layout.addStretch(1)
        
        # 将文件选择标签页添加到配置面板
        self.config_tabs.addTab(self.file_selector_tab, "上传目录")
    
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
        
        queue_title = QLabel("<b>上传队列</b>")
        queue_title.setStyleSheet("font-size: 12px;")
        header_layout.addWidget(queue_title)
        
        self.queue_status_label = QLabel("待上传: 0个文件，共0MB")
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
        
        self.current_file_label = QLabel("当前文件: -")
        self.upload_speed_label = QLabel("速度: - | 剩余时间: -")
        
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
        
        self.start_upload_button = QPushButton("开始上传")
        self.start_upload_button.setMinimumHeight(36)  # 减小按钮高度
        
        self.stop_upload_button = QPushButton("停止上传")
        self.stop_upload_button.setMinimumHeight(36)
        self.stop_upload_button.setEnabled(False)  # 初始状态下禁用
        
        self.save_config_button = QPushButton("保存配置")
        
        button_layout.addWidget(self.start_upload_button)
        button_layout.addWidget(self.stop_upload_button)
        button_layout.addWidget(self.save_config_button)
        
        self.main_layout.addLayout(button_layout)
    
    def _connect_signals(self):
        """连接信号和槽"""
        # 频道管理
        self.add_channel_button.clicked.connect(self._add_channel)
        self.remove_channel_button.clicked.connect(self._remove_channels)
        
        # 说明文字选项互斥处理
        self.use_folder_name_check.clicked.connect(self._handle_caption_option)
        self.read_title_txt_check.clicked.connect(self._handle_caption_option)
        self.use_custom_template_check.clicked.connect(self._handle_caption_option)
        
        # 文件目录选择
        self.browse_button.clicked.connect(self._browse_directory)
        
        # 上传控制
        self.start_upload_button.clicked.connect(self._start_upload)
        self.stop_upload_button.clicked.connect(self._stop_upload)
        self.save_config_button.clicked.connect(self._save_config)
    
    def _handle_caption_option(self):
        """处理说明文字选项的互斥"""
        sender = self.sender()
        
        # 确保至少有一个选项被选中
        if not sender.isChecked():
            sender.setChecked(True)
            return
        
        # 根据点击的选项取消选中其他选项
        if sender == self.use_folder_name_check:
            self.read_title_txt_check.setChecked(False)
            self.use_custom_template_check.setChecked(False)
        elif sender == self.read_title_txt_check:
            self.use_folder_name_check.setChecked(False)
            self.use_custom_template_check.setChecked(False)
        elif sender == self.use_custom_template_check:
            self.use_folder_name_check.setChecked(False)
            self.read_title_txt_check.setChecked(False)
            
        # 如果选择自定义模板，设置焦点到模板编辑区
        if sender == self.use_custom_template_check and sender.isChecked():
            self.caption_template.setFocus()
            
        # 自定义模板编辑区的启用状态
        self.caption_template.setEnabled(self.use_custom_template_check.isChecked())
    
    def _browse_directory(self):
        """浏览文件夹对话框"""
        current_path = self.path_input.text() or QDir.homePath()
        directory = QFileDialog.getExistingDirectory(
            self, 
            "选择上传目录",
            current_path
        )
        
        if directory:
            self.path_input.setText(directory)
            
            # 如果存在配置，更新配置中的目录路径
            if isinstance(self.config, dict) and 'UPLOAD' in self.config:
                self.config['UPLOAD']['directory'] = directory
    
    def _add_channel(self):
        """添加频道到列表"""
        channel = self.channel_input.text().strip()
        
        if not channel:
            QMessageBox.warning(self, "警告", "请输入频道链接或ID")
            return
        
        # 检查是否已存在相同频道
        for i in range(self.channel_list.count()):
            if self.channel_list.item(i).text() == channel:
                QMessageBox.information(self, "提示", "此频道已在列表中")
                return
        
        # 添加到列表
        self.channel_list.addItem(channel)
        
        # 清空输入
        self.channel_input.clear()
    
    def _remove_channels(self):
        """删除选中的频道"""
        selected_items = self.channel_list.selectedItems()
        
        if not selected_items:
            QMessageBox.information(self, "提示", "请先选择要删除的频道")
            return
        
        # 删除选中的频道
        for item in reversed(selected_items):
            row = self.channel_list.row(item)
            self.channel_list.takeItem(row)
    
    def _start_upload(self):
        """开始上传操作"""
        # 检查是否有目标频道
        if self.channel_list.count() == 0:
            QMessageBox.warning(self, "警告", "请至少添加一个目标频道")
            return
        
        # 检查上传目录
        upload_dir = self.path_input.text()
        if not upload_dir or not os.path.exists(upload_dir) or not os.path.isdir(upload_dir):
            QMessageBox.warning(self, "警告", "请选择有效的上传目录")
            return
        
        # 检查是否设置了uploader实例
        if not hasattr(self, 'uploader') or self.uploader is None:
            QMessageBox.warning(self, "警告", "上传器未初始化，请重新启动应用")
            return
        
        # 确保当前选择的上传目录已经保存到配置中
        self._save_config() 
        
        # 更新UI状态
        self.current_file_label.setText("准备上传...")
        self.upload_speed_label.setText("初始化上传...")
        
        # 更新按钮状态
        self.start_upload_button.setEnabled(False)
        self.stop_upload_button.setEnabled(True)
        
        # 清空上传列表
        self.upload_list.clear()
        self.upload_queue = []
        
        # 调用uploader的上传方法
        asyncio.ensure_future(self._run_upload_task())
    
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
        self.current_file_label.setText("上传已停止")
        self.upload_speed_label.setText("速度: - | 剩余时间: -")
        
        # 恢复按钮状态
        self.start_upload_button.setEnabled(True)
        self.stop_upload_button.setEnabled(False)
    
    def _save_config(self):
        """保存当前配置"""
        # 检查是否有目标频道
        if self.channel_list.count() == 0:
            QMessageBox.warning(self, "警告", "请至少添加一个目标频道")
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
            'use_custom_template': self.use_custom_template_check.isChecked(),
            'auto_thumbnail': self.auto_thumbnail_check.isChecked()
        }
        
        # 创建上传配置
        upload_config = {
            'target_channels': target_channels,
            'directory': upload_dir,
            'caption_template': self.caption_template.toPlainText(),
            'delay_between_uploads': round(float(self.upload_delay.value()), 1),  # 四舍五入到一位小数
            'options': upload_options
        }
        
        # 组织完整配置
        updated_config = {}
        if isinstance(self.config, dict):
            updated_config = self.config.copy()  # 复制当前配置
        
        # 更新UPLOAD部分
        updated_config['UPLOAD'] = upload_config
        
        # 发送配置保存信号
        logger.debug("向主窗口发送配置保存信号，更新上传配置")
        self.config_saved.emit(updated_config)
        
        # 显示成功消息
        QMessageBox.information(self, "配置保存", "上传配置已保存")
        
        # 更新本地配置引用
        self.config = updated_config
    
    def _update_queue_status(self):
        """更新队列状态"""
        total_files = len(self.upload_queue)
        total_size = sum(item['size'] for item in self.upload_queue)
        
        self.queue_status_label.setText(f"待上传: {total_files}个文件，共{self._format_size(total_size)}")
    
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
    
    def update_upload_progress(self, file_path, progress, speed, remaining_time):
        """更新上传进度
        
        Args:
            file_path: 文件路径
            progress: 进度 (0-100)
            speed: 上传速度 (bytes/s)
            remaining_time: 剩余时间 (秒)
        """
        # 更新当前文件标签
        self.current_file_label.setText(f"当前文件: {os.path.basename(file_path)}")
        
        # 更新速度和剩余时间
        speed_str = self._format_size(speed) + "/s"
        
        if remaining_time < 60:
            time_str = f"{remaining_time}秒"
        else:
            minutes = remaining_time // 60
            seconds = remaining_time % 60
            time_str = f"{minutes}分{seconds}秒"
        
        self.upload_speed_label.setText(f"速度: {speed_str} | 剩余时间: {time_str}")
        
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
    
    def all_uploads_completed(self):
        """所有上传任务完成"""
        # 重置状态
        self.current_file_label.setText("所有文件上传完成")
        self.upload_speed_label.setText("速度: - | 剩余时间: -")
        
        # 恢复按钮状态
        self.start_upload_button.setEnabled(True)
        self.stop_upload_button.setEnabled(False)
        
        # 显示完成消息
        QMessageBox.information(self, "上传完成", "所有文件上传任务已完成")
    
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
        
        # 加载说明文字模板
        caption_template = upload_config.get('caption_template', '{filename}')
        self.caption_template.setPlainText(caption_template)
        
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
            # 设置说明文字选项
            use_folder_name = options.get('use_folder_name', True)
            read_title_txt = options.get('read_title_txt', False)
            use_custom_template = options.get('use_custom_template', False)
            
            # 确保只有一个选项被选中
            if use_custom_template:
                self.use_custom_template_check.setChecked(True)
                self.use_folder_name_check.setChecked(False)
                self.read_title_txt_check.setChecked(False)
                self.caption_template.setEnabled(True)
            elif read_title_txt:
                self.read_title_txt_check.setChecked(True)
                self.use_folder_name_check.setChecked(False)
                self.use_custom_template_check.setChecked(False)
                self.caption_template.setEnabled(False)
            else:  # 默认使用文件夹名称
                self.use_folder_name_check.setChecked(True)
                self.read_title_txt_check.setChecked(False)
                self.use_custom_template_check.setChecked(False)
                self.caption_template.setEnabled(False)
            
            # 设置自动缩略图选项
            auto_thumbnail = options.get('auto_thumbnail', True)
            self.auto_thumbnail_check.setChecked(auto_thumbnail)
        
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
                
                logger.debug("已成功连接上传器事件")
            
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
            file_path: 文件路径
            success: 是否成功(默认为True)
            **kwargs: 其他参数
        """
        file_name = os.path.basename(file_path)
        
        # 添加到上传列表
        item = QListWidgetItem()
        status = "✓ 成功" if success else "✗ 失败"
        item.setText(f"{file_name} - {status}")
        item.setData(Qt.UserRole, file_path)
        self.upload_list.addItem(item)
        
        # 滚动到底部显示最新项
        self.upload_list.scrollToBottom()
        
        logger.debug(f"文件上传{'成功' if success else '失败'}: {file_name}")

    def _handle_upload_completed(self, success=True, **kwargs):
        """处理所有上传完成事件
        
        Args:
            success: 整体上传是否成功
            **kwargs: 其他参数，可能包含total_files, total_time等
        """
        # 更新UI状态
        status_text = "上传成功" if success else "上传完成但有错误"
        self.current_file_label.setText(status_text)
        
        # 提取上传统计信息
        total_files = kwargs.get('total_files', 0)
        total_time = kwargs.get('total_time', 0)
        
        if total_files > 0 and total_time > 0:
            avg_time = total_time / total_files
            self.upload_speed_label.setText(f"共上传 {total_files} 个文件，耗时 {total_time:.1f} 秒，平均 {avg_time:.1f} 秒/个")
        else:
            self.upload_speed_label.setText("上传完成")
        
        # 恢复按钮状态 - 在异步方法中已经处理，这里不重复处理
        # self.start_upload_button.setEnabled(True)
        # self.stop_upload_button.setEnabled(False)
        
        logger.info(f"所有上传{'成功' if success else '完成但有错误'}，总共 {total_files} 个文件")

    def _handle_upload_error(self, error, **kwargs):
        """处理上传错误事件
        
        Args:
            error: 错误信息
            **kwargs: 其他参数
        """
        error_message = f"上传错误: {error}"
        
        # 更新UI状态
        self.current_file_label.setText("上传出错")
        self.upload_speed_label.setText(error_message)
        
        # 恢复按钮状态 - 在异步方法中已经处理，这里不重复处理
        # self.start_upload_button.setEnabled(True)
        # self.stop_upload_button.setEnabled(False)
        
        logger.error(error_message)

    async def _run_upload_task(self):
        """运行上传任务的异步方法"""
        try:
            # 调用uploader的upload_local_files方法执行上传
            await self.uploader.upload_local_files()
            
            # 上传完成后自动调用all_uploads_completed方法更新UI
            self.all_uploads_completed()
            
        except Exception as e:
            # 捕获并处理可能的异常
            error_message = f"上传过程中发生错误: {str(e)}"
            logger.error(error_message)
            
            # 更新UI状态
            self.current_file_label.setText("上传出错")
            self.upload_speed_label.setText("请检查日志获取详细信息")
            
            # 恢复按钮状态
            self.start_upload_button.setEnabled(True)
            self.stop_upload_button.setEnabled(False)
            
            # 显示错误对话框
            QMessageBox.critical(self, "上传错误", error_message) 