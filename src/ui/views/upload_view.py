"""
TG-Manager 上传界面
实现本地媒体文件上传到Telegram频道的功能
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QCheckBox, QPushButton,
    QGroupBox, QScrollArea, QSpinBox, QGridLayout,
    QListWidget, QListWidgetItem, QFileDialog, QMessageBox,
    QFileSystemModel, QTreeView, QSplitter, QTextEdit, QSizePolicy,
    QTabWidget, QDoubleSpinBox
)
from PySide6.QtCore import Qt, Signal, Slot, QSize, QDir, QModelIndex
from PySide6.QtGui import QIcon

from pathlib import Path
import os
from src.utils.logger import get_logger

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
        self.main_layout.setContentsMargins(4, 4, 4, 4)  # 减小边距
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
        self.config_tabs.setMaximumHeight(360)  # 增加最大高度，从320增加到360
        self.config_tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
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
        channel_layout.setContentsMargins(4, 4, 4, 4)  # 减小边距
        channel_layout.setSpacing(4)  # 减小间距
        
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
        self.channel_list.setMinimumHeight(85)  # 设置最小高度以显示约3行
        
        channel_layout.addWidget(channel_list_label)
        channel_layout.addWidget(self.channel_list, 1)  # 使列表占据所有剩余空间
        
        # 上传选项标签页
        self.options_tab = QWidget()
        options_layout = QVBoxLayout(self.options_tab)
        options_layout.setContentsMargins(4, 4, 4, 4)  # 减小边距
        options_layout.setSpacing(4)  # 减小间距
        
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
        # 减小高度，从120px减少到100px，从160px减少到140px
        self.caption_template.setMinimumHeight(100)  # 设置最小高度
        self.caption_template.setMaximumHeight(140)  # 减小最大高度
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
        
        # 文件选择器标签页
        self.file_selector_tab = QWidget()
        file_selector_layout = QVBoxLayout(self.file_selector_tab)
        file_selector_layout.setContentsMargins(4, 4, 4, 4)  # 减小边距
        file_selector_layout.setSpacing(4)  # 减小间距
        
        # 文件系统导航
        file_nav_layout = QHBoxLayout()
        
        self.current_path_label = QLabel("当前路径:")
        file_nav_layout.addWidget(self.current_path_label)
        
        self.path_input = QLineEdit()
        self.path_input.setReadOnly(True)
        file_nav_layout.addWidget(self.path_input)
        
        self.browse_button = QPushButton("浏览...")
        file_nav_layout.addWidget(self.browse_button)
        
        file_selector_layout.addLayout(file_nav_layout)
        
        # 文件系统模型和视图
        self.fs_model = QFileSystemModel()
        self.fs_model.setRootPath(QDir.rootPath())
        self.fs_model.setFilter(QDir.AllDirs | QDir.Files | QDir.NoDotAndDotDot)
        
        self.file_tree = QTreeView()
        self.file_tree.setModel(self.fs_model)
        self.file_tree.setRootIndex(self.fs_model.index(QDir.homePath()))
        self.file_tree.setSelectionMode(QTreeView.ExtendedSelection)
        self.file_tree.setColumnWidth(0, 250)  # 名称列宽
        self.path_input.setText(QDir.homePath())
        
        file_selector_layout.addWidget(self.file_tree)
        
        # 文件选择按钮
        file_selection_layout = QHBoxLayout()
        
        self.select_all_button = QPushButton("全选")
        self.clear_selection_button = QPushButton("取消选择")
        self.add_to_queue_button = QPushButton("添加到上传队列")
        
        file_selection_layout.addWidget(self.select_all_button)
        file_selection_layout.addWidget(self.clear_selection_button)
        file_selection_layout.addWidget(self.add_to_queue_button)
        
        file_selector_layout.addLayout(file_selection_layout)
        
        # 将标签页添加到配置面板
        self.config_tabs.addTab(self.channel_tab, "目标频道")
        self.config_tabs.addTab(self.options_tab, "上传选项")
        self.config_tabs.addTab(self.file_selector_tab, "文件选择")
    
    def _create_upload_panel(self):
        """创建上传状态面板"""
        # 创建下部区域的容器
        upload_container = QWidget()
        upload_container_layout = QVBoxLayout(upload_container)
        upload_container_layout.setContentsMargins(0, 0, 0, 0)  # 移除容器的边距
        upload_container_layout.setSpacing(2)  # 减小间距
        
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
        self.upload_list.setMinimumHeight(120)  # 确保列表有足够的高度
        upload_container_layout.addWidget(self.upload_list)
        
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
        
        # 添加到主布局，增加下方区域的比例
        self.main_layout.addWidget(upload_container, 2)  # 从1增加到2，增大下方区域比例
    
    def _create_action_buttons(self):
        """创建底部操作按钮"""
        button_layout = QHBoxLayout()
        
        self.start_upload_button = QPushButton("开始上传")
        self.start_upload_button.setMinimumHeight(40)
        
        self.save_config_button = QPushButton("保存配置")
        self.clear_queue_button = QPushButton("清空队列")
        self.remove_selected_button = QPushButton("移除所选")
        
        button_layout.addWidget(self.start_upload_button)
        button_layout.addWidget(self.save_config_button)
        button_layout.addWidget(self.clear_queue_button)
        button_layout.addWidget(self.remove_selected_button)
        
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
        
        # 文件选择
        self.browse_button.clicked.connect(self._browse_directory)
        self.file_tree.doubleClicked.connect(self._on_file_double_clicked)
        
        # 文件操作
        self.select_all_button.clicked.connect(self._select_all_files)
        self.clear_selection_button.clicked.connect(self._clear_selection)
        self.add_to_queue_button.clicked.connect(self._add_to_queue)
        
        # 队列管理
        self.clear_queue_button.clicked.connect(self._clear_queue)
        self.remove_selected_button.clicked.connect(self._remove_selected_files)
        
        # 上传控制
        self.start_upload_button.clicked.connect(self._start_upload)
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
        directory = QFileDialog.getExistingDirectory(
            self, 
            "选择文件夹",
            self.path_input.text()
        )
        
        if directory:
            self.path_input.setText(directory)
            self.file_tree.setRootIndex(self.fs_model.index(directory))
    
    def _on_file_double_clicked(self, index):
        """文件树双击处理
        
        Args:
            index: 被双击的项的索引
        """
        # 更新当前路径
        path = self.fs_model.filePath(index)
        self.path_input.setText(path)
    
    def _select_all_files(self):
        """全选文件"""
        self.file_tree.selectAll()
    
    def _clear_selection(self):
        """取消文件选择"""
        self.file_tree.clearSelection()
    
    def _add_to_queue(self):
        """添加选中的文件到上传队列"""
        # 获取选中的文件
        selected_indexes = self.file_tree.selectedIndexes()
        selected_files = []
        
        # 筛选出文件列中的索引，避免重复
        for index in selected_indexes:
            if index.column() == 0:  # 名称列
                file_path = self.fs_model.filePath(index)
                # 只添加文件，不添加目录
                if os.path.isfile(file_path):
                    selected_files.append(file_path)
        
        if not selected_files:
            QMessageBox.information(self, "提示", "请选择至少一个文件")
            return
        
        # 添加到上传队列
        total_size = 0
        for file_path in selected_files:
            # 检查是否已经在队列中
            exists = False
            for i in range(self.upload_list.count()):
                if self.upload_list.item(i).data(Qt.UserRole) == file_path:
                    exists = True
                    break
            
            if not exists:
                file_size = os.path.getsize(file_path)
                total_size += file_size
                
                # 创建列表项
                item = QListWidgetItem()
                item.setText(f"{os.path.basename(file_path)} - {self._format_size(file_size)}")
                item.setData(Qt.UserRole, file_path)
                
                # 添加到列表
                self.upload_list.addItem(item)
                self.upload_queue.append({
                    'path': file_path,
                    'size': file_size
                })
        
        # 更新队列状态
        self._update_queue_status()
    
    def _clear_queue(self):
        """清空上传队列"""
        self.upload_list.clear()
        self.upload_queue = []
        self._update_queue_status()
    
    def _remove_selected_files(self):
        """从队列中移除选中的项目"""
        selected_items = self.upload_list.selectedItems()
        
        if not selected_items:
            QMessageBox.information(self, "提示", "请先选择要从队列中移除的文件")
            return
        
        # 从队列和列表中移除选中的项目
        for item in reversed(selected_items):
            file_path = item.data(Qt.UserRole)
            row = self.upload_list.row(item)
            self.upload_list.takeItem(row)
            
            # 从上传队列中移除
            for i, queue_item in enumerate(self.upload_queue):
                if queue_item['path'] == file_path:
                    self.upload_queue.pop(i)
                    break
        
        # 更新队列状态
        self._update_queue_status()
    
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
        """开始上传"""
        # 检查目标频道
        if self.channel_list.count() == 0:
            QMessageBox.warning(self, "警告", "请至少添加一个目标频道")
            return
        
        # 检查上传队列
        if len(self.upload_queue) == 0:
            QMessageBox.warning(self, "警告", "上传队列为空，请先添加文件")
            return
        
        # 收集上传配置
        target_channels = []
        for i in range(self.channel_list.count()):
            target_channels.append(self.channel_list.item(i).text())
        
        config = {
            'target_channels': target_channels,
            'files': self.upload_queue,
            'options': {
                'use_folder_name': self.use_folder_name_check.isChecked(),
                'read_title_txt': self.read_title_txt_check.isChecked(),
                'use_custom_template': self.use_custom_template_check.isChecked(),
                'caption_template': self.caption_template.toPlainText(),
                'auto_thumbnail': self.auto_thumbnail_check.isChecked(),
                'upload_delay': round(float(self.upload_delay.value()), 1)
            }
        }
        
        # 发出上传开始信号
        self.upload_started.emit(config)
        
        # 更新状态
        self.current_file_label.setText("准备上传...")
        
        # 禁用开始按钮
        self.start_upload_button.setEnabled(False)
    
    def _save_config(self):
        """保存当前配置"""
        # 检查是否有目标频道
        if self.channel_list.count() == 0:
            QMessageBox.warning(self, "警告", "请至少添加一个目标频道")
            return
        
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
            'directory': self.path_input.text() or 'uploads',  # 使用当前选择的目录路径
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
        
        # 启用开始按钮
        self.start_upload_button.setEnabled(True)
        
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
        if os.path.exists(directory):
            self.path_input.setText(directory)
            self.file_tree.setRootIndex(self.fs_model.index(directory))
        
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
            elif read_title_txt:
                self.read_title_txt_check.setChecked(True)
                self.use_folder_name_check.setChecked(False)
                self.use_custom_template_check.setChecked(False)
            else:  # 默认使用文件夹名称
                self.use_folder_name_check.setChecked(True)
                self.read_title_txt_check.setChecked(False)
                self.use_custom_template_check.setChecked(False)
                
            # 更新模板编辑区启用状态
            self.caption_template.setEnabled(self.use_custom_template_check.isChecked())
            
            # 自动缩略图选项
            self.auto_thumbnail_check.setChecked(options.get('auto_thumbnail', True))
            
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
            # 状态更新事件
            self.uploader.on("status", self._update_status)
            
            # 上传进度事件
            self.uploader.on("progress", self._update_progress)
            
            # 上传完成事件
            self.uploader.on("upload_complete", self._on_upload_complete)
            
            # 所有上传完成事件
            self.uploader.on("all_uploads_complete", self._on_all_uploads_complete)
            
            # 错误事件
            self.uploader.on("error", self._on_upload_error)
            
            logger.debug("上传器信号连接成功")
        except Exception as e:
            logger.error(f"连接上传器信号时出错: {e}")
            import traceback
            logger.debug(f"错误详情:\n{traceback.format_exc()}")
    
    def _update_status(self, status):
        """更新状态信息
        
        Args:
            status: 状态信息
        """
        self.status_label.setText(status)
        logger.debug(f"上传状态更新: {status}")
    
    def _update_progress(self, current, total, filename=None, speed=None, estimated_time=None):
        """更新上传进度
        
        Args:
            current: 当前进度(字节)
            total: 总大小(字节)
            filename: 文件名(可选)
            speed: 上传速度(字节/秒，可选)
            estimated_time: 预计剩余时间(秒，可选)
        """
        # 更新进度条
        if total > 0:
            percentage = min(int((current / total) * 100), 100)
            self.progress_bar.setValue(percentage)
            
            # 格式化显示
            progress_text = f"上传进度: {percentage}%"
            
            if filename:
                progress_text = f"上传中: {filename} - {percentage}%"
            
            # 如果有速度信息，添加到显示中
            if speed is not None:
                speed_str = self._format_speed(speed)
                progress_text += f" • 速度: {speed_str}"
            
            # 如果有预计时间，添加到显示中
            if estimated_time is not None:
                time_str = self._format_time(estimated_time)
                progress_text += f" • 剩余: {time_str}"
                
            self.progress_label.setText(progress_text)
        else:
            # 不确定的进度，使用循环进度条
            self.progress_bar.setRange(0, 0)
            if filename:
                self.progress_label.setText(f"正在上传: {filename}")
            else:
                self.progress_label.setText("正在上传...")
    
    def _on_upload_complete(self, file_path, message_id):
        """上传完成处理
        
        Args:
            file_path: 文件路径
            message_id: 消息ID
        """
        # 更新上传完成列表
        import os
        filename = os.path.basename(file_path)
        self._add_uploaded_item(filename)
        
        # 重置进度条
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_label.setText("准备上传下一个文件...")
        
        logger.debug(f"文件上传完成: {filename}, 消息ID: {message_id}")
    
    def _on_all_uploads_complete(self):
        """所有上传完成处理"""
        # 更新UI状态
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.progress_label.setText("所有上传已完成")
        self.status_label.setText("上传任务已完成")
        
        # 恢复按钮状态
        self.upload_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        
        # 显示提示消息
        self._show_completion_message("上传完成", "所有文件已上传完成")
        
        logger.info("所有文件上传完成")
    
    def _on_upload_error(self, error, message=None):
        """上传错误处理
        
        Args:
            error: 错误信息
            message: 额外的消息(可选)
        """
        # 更新UI状态
        error_msg = f"上传出错: {error}"
        if message:
            error_msg += f"\n{message}"
            
        self.status_label.setText(error_msg)
        self.progress_label.setText("上传过程中出现错误")
        
        # 恢复进度条状态
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        
        # 恢复按钮状态
        self.upload_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        
        # 显示错误对话框
        self._show_error_dialog("上传错误", error_msg)
        
        logger.error(f"上传错误: {error}")
        if message:
            logger.debug(f"错误详情: {message}")
    
    def _add_uploaded_item(self, filename):
        """添加上传完成项目到列表
        
        Args:
            filename: 文件名
        """
        from PySide6.QtWidgets import QListWidgetItem
        item = QListWidgetItem(filename)
        
        # 添加到已完成列表
        self.uploaded_list.addItem(item)
        
        # 保持最新项可见
        self.uploaded_list.scrollToBottom()
    
    def _format_speed(self, bytes_per_sec):
        """格式化上传速度
        
        Args:
            bytes_per_sec: 每秒字节数
            
        Returns:
            str: 格式化后的速度
        """
        # 速度单位
        units = ['B/s', 'KB/s', 'MB/s', 'GB/s']
        
        # 计算合适的单位
        i = 0
        speed = float(bytes_per_sec)
        while speed >= 1024 and i < len(units) - 1:
            speed /= 1024
            i += 1
        
        # 格式化输出
        return f"{speed:.2f} {units[i]}"
    
    def _format_time(self, seconds):
        """格式化时间
        
        Args:
            seconds: 时间(秒)
            
        Returns:
            str: 格式化后的时间
        """
        if seconds < 60:
            return f"{seconds:.0f}秒"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}分钟"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}小时"
    
    def _show_completion_message(self, title, message):
        """显示完成提示消息
        
        Args:
            title: 标题
            message: 消息内容
        """
        from PySide6.QtWidgets import QMessageBox
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.exec()
    
    def _show_error_dialog(self, title, message):
        """显示错误对话框
        
        Args:
            title: 对话框标题
            message: 错误消息
        """
        from PySide6.QtWidgets import QMessageBox
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.exec() 