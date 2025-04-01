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
    QTabWidget
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
        
        self.use_folder_name_check = QCheckBox("使用文件夹名称作为说明文字")
        self.use_folder_name_check.setChecked(True)
        self.use_folder_name_check.setMinimumHeight(30)  # 增加高度
        caption_options_layout.addWidget(self.use_folder_name_check, 0, 0)
        
        self.read_title_txt_check = QCheckBox("读取title.txt文件作为说明文字")
        self.read_title_txt_check.setChecked(True)
        self.read_title_txt_check.setMinimumHeight(30)  # 增加高度
        caption_options_layout.addWidget(self.read_title_txt_check, 0, 1)
        
        # 媒体组设置 - 放到水平布局中
        self.keep_media_groups_check = QCheckBox("保持原始文件组合为媒体组")
        self.keep_media_groups_check.setChecked(True)
        self.keep_media_groups_check.setMinimumHeight(30)  # 增加高度
        caption_options_layout.addWidget(self.keep_media_groups_check, 1, 0)
        
        self.auto_thumbnail_check = QCheckBox("自动生成视频缩略图")
        self.auto_thumbnail_check.setChecked(True)
        self.auto_thumbnail_check.setMinimumHeight(30)  # 增加高度
        caption_options_layout.addWidget(self.auto_thumbnail_check, 1, 1)
        
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
        # 增加最大高度，从80px增加到160px，以显示更多内容
        self.caption_template.setMinimumHeight(120)  # 设置最小高度
        self.caption_template.setMaximumHeight(160)  # 增加最大高度
        # 设置更适合文本编辑的尺寸策略
        self.caption_template.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        
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
        
        # 上传延迟
        delay_layout = QHBoxLayout()
        delay_layout.setContentsMargins(0, 8, 0, 0)  # 增加顶部间距
        
        delay_label = QLabel("上传延迟:")
        delay_label.setMinimumWidth(80)  # 设置标签最小宽度
        delay_layout.addWidget(delay_label)
        
        self.upload_delay = QSpinBox()
        self.upload_delay.setRange(0, 60)
        self.upload_delay.setValue(2)
        self.upload_delay.setSuffix(" 秒")
        self.upload_delay.setMinimumWidth(100)  # 设置控件最小宽度
        
        delay_layout.addWidget(self.upload_delay)
        delay_layout.addStretch()
        
        options_layout.addLayout(delay_layout)
        
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
                'caption_template': self.caption_template.toPlainText(),
                'keep_media_groups': self.keep_media_groups_check.isChecked(),
                'auto_thumbnail': self.auto_thumbnail_check.isChecked(),
                'upload_delay': self.upload_delay.value()
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
        
        # 收集配置
        target_channels = []
        for i in range(self.channel_list.count()):
            target_channels.append(self.channel_list.item(i).text())
        
        config = {
            'target_channels': target_channels,
            'options': {
                'use_folder_name': self.use_folder_name_check.isChecked(),
                'read_title_txt': self.read_title_txt_check.isChecked(),
                'caption_template': self.caption_template.toPlainText(),
                'keep_media_groups': self.keep_media_groups_check.isChecked(),
                'auto_thumbnail': self.auto_thumbnail_check.isChecked(),
                'upload_delay': self.upload_delay.value()
            }
        }
        
        # TODO: 在主界面中处理配置保存
        QMessageBox.information(self, "配置保存", "配置已保存")
    
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
        # 清空现有项目
        self.channel_list.clear()
        
        # 加载目标频道
        target_channels = config.get('UPLOAD', {}).get('target_channels', [])
        for channel in target_channels:
            self.channel_list.addItem(channel)
        
        # 加载上传选项
        caption_template = config.get('UPLOAD', {}).get('caption_template', '{filename}')
        self.caption_template.setPlainText(caption_template)
        
        # 加载其他选项（如果存在的话）
        upload_options = config.get('UPLOAD', {}).get('options', {})
        if upload_options:
            self.use_folder_name_check.setChecked(upload_options.get('use_folder_name', True))
            self.read_title_txt_check.setChecked(upload_options.get('read_title_txt', True))
            self.keep_media_groups_check.setChecked(upload_options.get('keep_media_groups', True))
            self.auto_thumbnail_check.setChecked(upload_options.get('auto_thumbnail', True))
            self.upload_delay.setValue(upload_options.get('upload_delay', 2)) 