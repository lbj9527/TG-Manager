"""
TG-Manager 下载界面
实现媒体文件的下载功能
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QCheckBox, QComboBox, QPushButton,
    QGroupBox, QScrollArea, QSpinBox, QGridLayout,
    QListWidget, QListWidgetItem, QFileDialog, QMessageBox,
    QSizePolicy
)
from PySide6.QtCore import Qt, Signal, Slot, QSize

from src.utils.logger import get_logger

logger = get_logger()


class DownloadView(QWidget):
    """下载界面，提供媒体下载功能"""
    
    # 下载开始信号
    download_started = Signal(dict)  # 下载配置
    
    def __init__(self, config=None, parent=None, use_keywords=False):
        """初始化下载界面
        
        Args:
            config: 配置对象
            parent: 父窗口部件
            use_keywords: 是否使用关键词模式
        """
        super().__init__(parent)
        
        self.config = config or {}
        self.use_keywords = use_keywords
        
        # 设置布局
        self.main_layout = QHBoxLayout(self)
        self.setLayout(self.main_layout)
        
        # 创建左侧面板-配置选项
        self._create_left_panel()
        
        # 创建右侧面板-下载列表和状态
        self._create_right_panel()
        
        # 连接事件
        self._connect_signals()
        
        # 初始化UI状态
        self._init_ui_state()
        
        # 加载配置
        if self.config:
            self.load_config(self.config)
        
        logger.info(f"{'关键词' if self.use_keywords else '普通'}下载界面初始化完成")
    
    def _create_left_panel(self):
        """创建左侧面板"""
        # 创建左侧容器
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMinimumWidth(300)  # 减小最小宽度
        left_panel.setMaximumWidth(450)  # 适当减小最大宽度
        
        # 设置尺寸策略，允许更灵活的缩放
        left_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        
        # ===== 频道配置组 =====
        channel_group = QGroupBox("频道配置")
        channel_layout = QVBoxLayout()
        
        # 频道链接
        form_layout = QFormLayout()
        
        self.channel_input = QLineEdit()
        self.channel_input.setPlaceholderText("频道链接或ID (例如: https://t.me/example 或 -1001234567890)")
        form_layout.addRow("源频道:", self.channel_input)
        
        id_layout = QHBoxLayout()
        
        self.start_id = QSpinBox()
        self.start_id.setRange(1, 999999999)
        self.start_id.setValue(1)
        
        self.end_id = QSpinBox()
        self.end_id.setRange(0, 999999999)
        self.end_id.setValue(100)
        self.end_id.setSpecialValueText("最新消息")
        
        id_layout.addWidget(QLabel("开始ID:"))
        id_layout.addWidget(self.start_id)
        id_layout.addWidget(QLabel("结束ID:"))
        id_layout.addWidget(self.end_id)
        
        channel_layout.addLayout(form_layout)
        channel_layout.addLayout(id_layout)
        
        # 添加和删除频道按钮
        channel_button_layout = QHBoxLayout()
        
        self.add_channel_button = QPushButton("添加频道")
        self.remove_channel_button = QPushButton("删除所选")
        
        channel_button_layout.addWidget(self.add_channel_button)
        channel_button_layout.addWidget(self.remove_channel_button)
        
        channel_layout.addLayout(channel_button_layout)
        
        # 频道列表
        self.channel_list = QListWidget()
        self.channel_list.setSelectionMode(QListWidget.ExtendedSelection)
        
        channel_layout.addWidget(QLabel("已配置频道:"))
        channel_layout.addWidget(self.channel_list)
        
        channel_group.setLayout(channel_layout)
        
        # ===== 下载选项组 =====
        options_group = QGroupBox("下载选项")
        options_layout = QVBoxLayout()
        
        # 媒体类型选择
        media_label = QLabel("媒体类型:")
        
        media_layout = QGridLayout()
        
        self.photo_check = QCheckBox("照片")
        self.photo_check.setChecked(True)
        media_layout.addWidget(self.photo_check, 0, 0)
        
        self.video_check = QCheckBox("视频")
        self.video_check.setChecked(True)
        media_layout.addWidget(self.video_check, 0, 1)
        
        self.document_check = QCheckBox("文档")
        self.document_check.setChecked(True)
        media_layout.addWidget(self.document_check, 1, 0)
        
        self.audio_check = QCheckBox("音频")
        self.audio_check.setChecked(True)
        media_layout.addWidget(self.audio_check, 1, 1)
        
        self.animation_check = QCheckBox("动画")
        self.animation_check.setChecked(True)
        media_layout.addWidget(self.animation_check, 2, 0)
        
        options_layout.addWidget(media_label)
        options_layout.addLayout(media_layout)
        
        # 关键词过滤
        if self.use_keywords:
            keywords_layout = QVBoxLayout()
            keywords_label = QLabel("关键词过滤:")
            
            self.keywords_input = QLineEdit()
            self.keywords_input.setPlaceholderText("输入关键词，用逗号分隔多个关键词")
            
            keywords_layout.addWidget(keywords_label)
            keywords_layout.addWidget(self.keywords_input)
            
            # 添加和删除关键词按钮
            keywords_button_layout = QHBoxLayout()
            
            self.add_keyword_button = QPushButton("添加关键词")
            self.remove_keyword_button = QPushButton("删除所选")
            
            keywords_button_layout.addWidget(self.add_keyword_button)
            keywords_button_layout.addWidget(self.remove_keyword_button)
            
            keywords_layout.addLayout(keywords_button_layout)
            
            # 关键词列表
            self.keywords_list = QListWidget()
            self.keywords_list.setSelectionMode(QListWidget.ExtendedSelection)
            
            keywords_layout.addWidget(QLabel("已添加关键词:"))
            keywords_layout.addWidget(self.keywords_list)
            
            options_layout.addLayout(keywords_layout)
        
        # 下载路径
        path_layout = QHBoxLayout()
        
        self.download_path = QLineEdit()
        self.download_path.setReadOnly(True)
        self.download_path.setText("downloads")
        
        self.browse_button = QPushButton("浏览...")
        
        path_layout.addWidget(QLabel("下载路径:"))
        path_layout.addWidget(self.download_path)
        path_layout.addWidget(self.browse_button)
        
        options_layout.addLayout(path_layout)
        
        # 并行下载设置
        parallel_layout = QHBoxLayout()
        
        self.parallel_check = QCheckBox("启用并行下载")
        
        self.max_downloads = QSpinBox()
        self.max_downloads.setRange(1, 20)
        self.max_downloads.setValue(5)
        self.max_downloads.setEnabled(False)
        
        parallel_layout.addWidget(self.parallel_check)
        parallel_layout.addWidget(QLabel("最大并发:"))
        parallel_layout.addWidget(self.max_downloads)
        
        options_layout.addLayout(parallel_layout)
        
        options_group.setLayout(options_layout)
        
        # ===== 操作按钮 =====
        button_layout = QHBoxLayout()
        
        self.start_button = QPushButton("开始下载")
        self.start_button.setMinimumHeight(40)
        
        self.save_config_button = QPushButton("保存配置")
        
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.save_config_button)
        
        # 将组件添加到左侧面板
        left_layout.addWidget(channel_group)
        left_layout.addWidget(options_group)
        left_layout.addLayout(button_layout)
        
        self.main_layout.addWidget(left_panel)
    
    def _create_right_panel(self):
        """创建右侧面板"""
        # 创建右侧容器
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # ===== 下载状态组 =====
        status_group = QGroupBox("下载状态")
        status_layout = QVBoxLayout()
        
        # 当前下载任务
        status_layout.addWidget(QLabel("当前下载任务:"))
        
        self.current_task_label = QLabel("未开始下载")
        self.current_task_label.setStyleSheet("font-weight: bold;")
        status_layout.addWidget(self.current_task_label)
        
        # 整体进度
        self.overall_progress_label = QLabel("总进度: 0/0 (0%)")
        status_layout.addWidget(self.overall_progress_label)
        
        status_group.setLayout(status_layout)
        
        # ===== 下载列表组 =====
        download_list_group = QGroupBox("下载列表")
        download_list_layout = QVBoxLayout()
        
        # 创建下载列表滚动区域
        self.download_list = QListWidget()
        
        download_list_layout.addWidget(self.download_list)
        
        download_list_group.setLayout(download_list_layout)
        
        # 添加组件到右侧面板
        right_layout.addWidget(status_group)
        right_layout.addWidget(download_list_group, 1)  # 1 表示伸展因子
        
        self.main_layout.addWidget(right_panel, 1)  # 1 表示伸展因子
    
    def _connect_signals(self):
        """连接信号和槽"""
        # 并行下载复选框状态改变时
        self.parallel_check.stateChanged.connect(self._on_parallel_state_changed)
        
        # 浏览按钮点击
        self.browse_button.clicked.connect(self._browse_download_path)
        
        # 添加频道按钮点击
        self.add_channel_button.clicked.connect(self._add_channel)
        
        # 删除频道按钮点击
        self.remove_channel_button.clicked.connect(self._remove_channels)
        
        # 开始下载按钮点击
        self.start_button.clicked.connect(self._start_download)
        
        # 保存配置按钮点击
        self.save_config_button.clicked.connect(self._save_config)
        
        # 如果是关键词模式，连接关键词相关信号
        if self.use_keywords:
            self.add_keyword_button.clicked.connect(self._add_keyword)
            self.remove_keyword_button.clicked.connect(self._remove_keywords)
    
    def _init_ui_state(self):
        """初始化UI状态"""
        # 设置工具提示
        self.channel_input.setToolTip("输入Telegram频道链接或ID")
        self.start_id.setToolTip("起始消息ID (包含)")
        self.end_id.setToolTip("结束消息ID (包含), 0表示最新消息")
        self.browse_button.setToolTip("选择下载文件保存位置")
        
        if self.use_keywords:
            self.keywords_input.setToolTip("输入关键词，多个关键词用逗号分隔")
    
    @Slot(int)
    def _on_parallel_state_changed(self, state):
        """并行下载复选框状态改变处理
        
        Args:
            state: 复选框状态
        """
        self.max_downloads.setEnabled(state == Qt.Checked)
    
    def _browse_download_path(self):
        """浏览下载路径对话框"""
        path = QFileDialog.getExistingDirectory(
            self, 
            "选择下载文件保存位置",
            self.download_path.text()
        )
        
        if path:
            self.download_path.setText(path)
    
    def _add_channel(self):
        """添加频道到列表"""
        channel = self.channel_input.text().strip()
        
        if not channel:
            QMessageBox.warning(self, "警告", "请输入频道链接或ID")
            return
        
        # 检查是否已存在相同频道
        for i in range(self.channel_list.count()):
            item_data = self.channel_list.item(i).data(Qt.UserRole)
            if item_data.get('channel') == channel:
                QMessageBox.information(self, "提示", "此频道已在列表中")
                return
        
        # 创建频道数据
        channel_data = {
            'channel': channel,
            'start_id': self.start_id.value(),
            'end_id': self.end_id.value(),
        }
        
        # 创建列表项
        item = QListWidgetItem()
        item.setText(f"{channel} (ID范围: {channel_data['start_id']}-{channel_data['end_id'] if channel_data['end_id'] > 0 else '最新'})")
        item.setData(Qt.UserRole, channel_data)
        
        # 添加到列表
        self.channel_list.addItem(item)
        
        # 清空输入
        self.channel_input.clear()
    
    def _remove_channels(self):
        """删除选中的频道"""
        # 获取所有选中项
        selected_items = self.channel_list.selectedItems()
        
        if not selected_items:
            QMessageBox.information(self, "提示", "请先选择要删除的频道")
            return
        
        # 逆序删除，避免索引变化问题
        for item in reversed(selected_items):
            row = self.channel_list.row(item)
            self.channel_list.takeItem(row)
    
    def _add_keyword(self):
        """添加关键词到列表"""
        if not self.use_keywords:
            return
            
        keywords_text = self.keywords_input.text().strip()
        
        if not keywords_text:
            QMessageBox.warning(self, "警告", "请输入关键词")
            return
        
        # 分割关键词
        keywords = [k.strip() for k in keywords_text.split(',') if k.strip()]
        
        # 添加到列表，忽略重复项
        for keyword in keywords:
            # 检查是否已存在
            exists = False
            for i in range(self.keywords_list.count()):
                if self.keywords_list.item(i).text() == keyword:
                    exists = True
                    break
            
            if not exists:
                self.keywords_list.addItem(keyword)
        
        # 清空输入
        self.keywords_input.clear()
    
    def _remove_keywords(self):
        """删除选中的关键词"""
        if not self.use_keywords:
            return
            
        # 获取所有选中项
        selected_items = self.keywords_list.selectedItems()
        
        if not selected_items:
            QMessageBox.information(self, "提示", "请先选择要删除的关键词")
            return
        
        # 逆序删除，避免索引变化问题
        for item in reversed(selected_items):
            row = self.keywords_list.row(item)
            self.keywords_list.takeItem(row)
    
    def _get_media_types(self):
        """获取选中的媒体类型
        
        Returns:
            list: 选中的媒体类型列表
        """
        media_types = []
        
        if self.photo_check.isChecked():
            media_types.append("photo")
        
        if self.video_check.isChecked():
            media_types.append("video")
        
        if self.document_check.isChecked():
            media_types.append("document")
        
        if self.audio_check.isChecked():
            media_types.append("audio")
        
        if self.animation_check.isChecked():
            media_types.append("animation")
        
        return media_types
    
    def _get_keywords(self):
        """获取关键词列表
        
        Returns:
            list: 关键词列表
        """
        if not self.use_keywords:
            return []
            
        keywords = []
        for i in range(self.keywords_list.count()):
            keywords.append(self.keywords_list.item(i).text())
        
        return keywords
    
    def _get_channels(self):
        """获取频道配置列表
        
        Returns:
            list: 频道配置列表
        """
        channels = []
        for i in range(self.channel_list.count()):
            channels.append(self.channel_list.item(i).data(Qt.UserRole))
        
        return channels
    
    def _start_download(self):
        """开始下载"""
        # 检查频道列表
        if self.channel_list.count() == 0:
            QMessageBox.warning(self, "警告", "请至少添加一个频道")
            return
        
        # 检查媒体类型
        media_types = self._get_media_types()
        if not media_types:
            QMessageBox.warning(self, "警告", "请至少选择一种媒体类型")
            return
        
        # 如果是关键词模式，检查关键词
        if self.use_keywords and self.keywords_list.count() == 0:
            QMessageBox.warning(self, "警告", "请至少添加一个关键词")
            return
        
        # 收集配置
        config = {
            'channels': self._get_channels(),
            'media_types': media_types,
            'keywords': self._get_keywords() if self.use_keywords else [],
            'download_path': self.download_path.text(),
            'parallel_download': self.parallel_check.isChecked(),
            'max_concurrent_downloads': self.max_downloads.value() if self.parallel_check.isChecked() else 1,
            'use_keywords': self.use_keywords
        }
        
        # 发出下载开始信号
        self.download_started.emit(config)
        
        # 更新状态
        self.current_task_label.setText("下载准备中...")
        self.overall_progress_label.setText("总进度: 0/0 (0%)")
        
        # 禁用开始按钮
        self.start_button.setEnabled(False)
    
    def _save_config(self):
        """保存当前配置"""
        # 检查频道列表
        if self.channel_list.count() == 0:
            QMessageBox.warning(self, "警告", "请至少添加一个频道")
            return
        
        # 配置将在主界面中处理保存
        config = {
            'channels': self._get_channels(),
            'media_types': self._get_media_types(),
            'keywords': self._get_keywords() if self.use_keywords else [],
            'download_path': self.download_path.text(),
            'parallel_download': self.parallel_check.isChecked(),
            'max_concurrent_downloads': self.max_downloads.value() if self.parallel_check.isChecked() else 1
        }
        
        # TODO: 在主界面中处理配置保存
        QMessageBox.information(self, "配置保存", "配置已保存")
    
    def update_download_progress(self, task_id, filename, progress, status):
        """更新下载进度
        
        Args:
            task_id: 任务ID
            filename: 文件名
            progress: 进度 (0-100)
            status: 状态说明
        """
        # 查找现有项目
        found = False
        for i in range(self.download_list.count()):
            item = self.download_list.item(i)
            if item.data(Qt.UserRole) == task_id:
                item.setText(f"{filename} - {status} [{progress}%]")
                found = True
                break
        
        # 没找到则添加新项目
        if not found:
            item = QListWidgetItem(f"{filename} - {status} [{progress}%]")
            item.setData(Qt.UserRole, task_id)
            self.download_list.addItem(item)
            # 滚动到最新项目
            self.download_list.scrollToBottom()
    
    def update_overall_progress(self, completed, total):
        """更新总体进度
        
        Args:
            completed: 已完成数量
            total: 总数量
        """
        percent = 0
        if total > 0:
            percent = int(completed / total * 100)
        
        self.overall_progress_label.setText(f"总进度: {completed}/{total} ({percent}%)")
        
        # 如果已全部完成，启用开始按钮
        if completed >= total and total > 0:
            self.start_button.setEnabled(True)
    
    def update_current_task(self, task_description):
        """更新当前任务描述
        
        Args:
            task_description: 任务描述文本
        """
        self.current_task_label.setText(task_description)
    
    def clear_download_list(self):
        """清空下载列表"""
        self.download_list.clear()
        
    def load_config(self, config):
        """从配置加载UI状态
        
        Args:
            config: 配置字典
        """
        # 清空现有项目
        self.channel_list.clear()
        if self.use_keywords:
            self.keywords_list.clear()
        
        # 加载频道
        download_settings = config.get('DOWNLOAD', {}).get('downloadSetting', [])
        for setting in download_settings:
            channel_data = {
                'channel': setting.get('source_channels', ''),
                'start_id': setting.get('start_id', 1),
                'end_id': setting.get('end_id', 0)
            }
            
            if channel_data['channel']:
                item = QListWidgetItem()
                item.setText(f"{channel_data['channel']} (ID范围: {channel_data['start_id']}-{channel_data['end_id'] if channel_data['end_id'] > 0 else '最新'})")
                item.setData(Qt.UserRole, channel_data)
                self.channel_list.addItem(item)
            
            # 如果是关键词模式，加载关键词
            if self.use_keywords and 'keywords' in setting:
                for keyword in setting.get('keywords', []):
                    if keyword and self.keywords_list.findItems(keyword, Qt.MatchExactly) == []:
                        self.keywords_list.addItem(keyword)
        
        # 加载媒体类型
        if download_settings and 'media_types' in download_settings[0]:
            media_types = download_settings[0].get('media_types', [])
            self.photo_check.setChecked("photo" in media_types)
            self.video_check.setChecked("video" in media_types)
            self.document_check.setChecked("document" in media_types)
            self.audio_check.setChecked("audio" in media_types)
            self.animation_check.setChecked("animation" in media_types)
        
        # 加载下载路径
        download_path = config.get('DOWNLOAD', {}).get('download_path', 'downloads')
        self.download_path.setText(download_path)
        
        # 加载并行下载设置
        parallel_download = config.get('DOWNLOAD', {}).get('parallel_download', False)
        self.parallel_check.setChecked(parallel_download)
        
        max_concurrent = config.get('DOWNLOAD', {}).get('max_concurrent_downloads', 5)
        self.max_downloads.setValue(max_concurrent) 