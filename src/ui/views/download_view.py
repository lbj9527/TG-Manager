"""
TG-Manager 下载界面
实现媒体文件的下载功能
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QCheckBox, QComboBox, QPushButton,
    QGroupBox, QScrollArea, QSpinBox, QGridLayout,
    QListWidget, QListWidgetItem, QFileDialog, QMessageBox,
    QSizePolicy, QTabWidget, QSplitter
)
from PySide6.QtCore import Qt, Signal, Slot, QSize

from src.utils.logger import get_logger
from src.utils.ui_config_models import MediaType

logger = get_logger()


class DownloadView(QWidget):
    """下载界面，提供媒体下载功能"""
    
    # 下载开始信号
    download_started = Signal(dict)  # 下载配置
    # 配置保存信号
    config_saved = Signal(dict)  # 添加配置保存信号
    
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
                border: 1px solid #444;
                border-radius: 3px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 7px;
                padding: 0 3px;
                background-color: palette(window);
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
        self.config_tabs.setMaximumHeight(360)  # 设置最大高度，从320增加到360，增加40像素
        self.config_tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.main_layout.addWidget(self.config_tabs)
        
        # 创建配置标签页
        self._create_config_panel()
        
        # 创建下部下载状态和列表面板
        self._create_download_panel()
        
        # 创建底部操作按钮
        self._create_action_buttons()
        
        # 连接事件
        self._connect_signals()
        
        # 初始化UI状态
        self._init_ui_state()
        
        # 加载配置
        if self.config:
            self.load_config(self.config)
        
        logger.info("下载界面初始化完成")
    
    def _create_config_panel(self):
        """创建配置标签页"""
        # 频道配置标签页
        self.channel_tab = QWidget()
        channel_layout = QVBoxLayout(self.channel_tab)
        channel_layout.setContentsMargins(4, 4, 4, 4)  # 减小边距
        channel_layout.setSpacing(2)  # 进一步减小间距
        
        # 创建顶部表单面板
        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 0, 0, 2)  # 减小底部间距
        
        # 频道输入
        self.channel_input = QLineEdit()
        self.channel_input.setPlaceholderText("频道链接或ID (例如: https://t.me/example 或 -1001234567890)")
        form_layout.addRow("频道链接:", self.channel_input)
        
        # 先添加表单布局到主布局
        channel_layout.addLayout(form_layout)
        
        # 消息范围 - 创建左对齐的布局
        range_layout = QHBoxLayout()
        range_layout.setContentsMargins(0, 0, 0, 2)  # 减小上下间距
        
        # 从消息ID标签
        id_label = QLabel("从消息ID:")
        id_label.setMinimumWidth(80)  # 设置最小宽度确保对齐
        range_layout.addWidget(id_label)
        
        self.start_id = QSpinBox()
        self.start_id.setRange(1, 999999999)
        self.start_id.setValue(1)
        self.start_id.setMinimumWidth(90)  # 减小宽度
        range_layout.addWidget(self.start_id)
        
        range_layout.addWidget(QLabel("到:"))
        
        self.end_id = QSpinBox()
        self.end_id.setRange(0, 999999999)
        self.end_id.setValue(0)
        self.end_id.setSpecialValueText("最新消息")
        self.end_id.setMinimumWidth(90)  # 减小宽度
        range_layout.addWidget(self.end_id)
        
        # 添加伸展因子，确保控件左对齐
        range_layout.addStretch(1)
        
        # 添加消息范围布局到主布局
        channel_layout.addLayout(range_layout)
        
        # 创建关键词输入行 - 新增的专门布局
        keywords_layout = QHBoxLayout()
        keywords_layout.setContentsMargins(0, 2, 0, 2)  # 减小上下间距
        
        # 添加关键词标签和输入框
        keyword_label = QLabel("关键词:")
        keyword_label.setMinimumWidth(70)  # 设置最小宽度确保对齐
        keywords_layout.addWidget(keyword_label)
        
        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("输入要筛选的关键词，多个用逗号分隔")
        self.keyword_input.setMinimumWidth(300)  # 增加最小宽度
        # 设置尺寸策略为水平方向可扩展
        self.keyword_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        keywords_layout.addWidget(self.keyword_input, 3)  # 设置拉伸因子为3，使其占据更多空间
        
        # 添加频道和删除按钮
        self.add_channel_button = QPushButton("添加频道")
        self.add_channel_button.setMinimumHeight(28)  # 设置按钮高度
        keywords_layout.addWidget(self.add_channel_button, 0)  # 不设置拉伸
        
        self.remove_channel_button = QPushButton("删除所选")
        self.remove_channel_button.setMinimumHeight(28)  # 设置按钮高度
        keywords_layout.addWidget(self.remove_channel_button, 0)  # 不设置拉伸
        
        # 添加伸展因子，确保控件左对齐
        keywords_layout.addStretch(1)
        
        # 添加关键词布局到主布局
        channel_layout.addLayout(keywords_layout)
        
        # 媒体类型选项 - 从下载选项标签页移动到频道配置标签页
        media_layout = QHBoxLayout()
        media_layout.setSpacing(10)
        media_layout.setContentsMargins(0, 2, 0, 2)  # 减小上下间距
        
        media_type_label = QLabel("要下载的媒体类型:")
        media_type_label.setMinimumWidth(110)
        media_layout.addWidget(media_type_label)
        
        self.photo_check = QCheckBox("照片")
        self.photo_check.setChecked(True)
        media_layout.addWidget(self.photo_check)
        
        self.video_check = QCheckBox("视频")
        self.video_check.setChecked(True)
        media_layout.addWidget(self.video_check)
        
        self.document_check = QCheckBox("文档")
        self.document_check.setChecked(True)
        media_layout.addWidget(self.document_check)
        
        self.audio_check = QCheckBox("音频")
        self.audio_check.setChecked(True)
        media_layout.addWidget(self.audio_check)
        
        self.animation_check = QCheckBox("动画")
        self.animation_check.setChecked(True)
        media_layout.addWidget(self.animation_check)
        
        media_layout.addStretch(1) # 添加弹簧，让控件靠左对齐
        channel_layout.addLayout(media_layout)
        
        # 创建频道列表部分 - 使用滚动区域显示
        channel_widget = QWidget()
        channel_widget_layout = QVBoxLayout(channel_widget)
        channel_widget_layout.setContentsMargins(0, 0, 0, 0)
        channel_widget_layout.setSpacing(2)
        
        # 频道列表标题
        self.channel_list_label = QLabel("已配置下载频道:  0个")
        self.channel_list_label.setStyleSheet("font-weight: bold;")  # 加粗标签
        channel_widget_layout.addWidget(self.channel_list_label)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)  # 允许小部件调整大小
        scroll_area.setFixedHeight(100)  # 设置滚动区域的固定高度，从60增加到75
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 创建一个容器部件来包含列表
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(0)
        
        # 频道列表 - 不再设置固定高度，让它在滚动区域内自然扩展
        self.channel_list = QListWidget()
        self.channel_list.setSelectionMode(QListWidget.ExtendedSelection)
        scroll_layout.addWidget(self.channel_list)
        
        # 设置滚动区域的内容
        scroll_area.setWidget(scroll_content)
        channel_widget_layout.addWidget(scroll_area)
        
        # 将频道列表部分添加到主布局
        channel_layout.addWidget(channel_widget, 1)  # 使频道列表占据所有剩余空间
        
        # 下载选项标签页
        self.options_tab = QWidget()
        options_layout = QVBoxLayout(self.options_tab)
        options_layout.setContentsMargins(4, 4, 4, 4)  # 减小边距
        options_layout.setSpacing(4)  # 减小间距
        
        # 并行下载选项 - 调整间距
        parallel_layout = QHBoxLayout()
        parallel_layout.setContentsMargins(0, 8, 0, 0)  # 增加与上方媒体类型的间距
        
        self.parallel_check = QCheckBox("启用并行下载")
        self.parallel_check.toggled.connect(lambda checked: self.max_downloads.setEnabled(checked))
        
        self.max_downloads = QSpinBox()
        self.max_downloads.setRange(1, 20)
        self.max_downloads.setValue(5)
        self.max_downloads.setEnabled(False)
        
        parallel_layout.addWidget(self.parallel_check)
        parallel_layout.addWidget(QLabel("最大并发:"))
        parallel_layout.addWidget(self.max_downloads)
        parallel_layout.addStretch(1)
        
        options_layout.addLayout(parallel_layout)
        
        # 添加一些空间
        options_layout.addSpacing(8)
        
        # 下载路径 - 移到标签卡的下部
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("下载路径:"))
        
        self.download_path = QLineEdit("downloads")
        path_layout.addWidget(self.download_path)
        
        self.browse_path_button = QPushButton("浏览...")
        path_layout.addWidget(self.browse_path_button)
        
        options_layout.addLayout(path_layout)
        
        # 添加弹性空间，使上方内容靠上显示，下方留白
        options_layout.addStretch(1)
        
        # 将标签页添加到配置面板
        self.config_tabs.addTab(self.channel_tab, "频道配置")
        self.config_tabs.addTab(self.options_tab, "下载选项")
    
    def _create_download_panel(self):
        """创建下载状态和列表面板"""
        # 创建标签页控件来容纳下载状态和列表
        self.download_tabs = QTabWidget()
        self.download_tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # 创建下载状态标签页
        self.status_tab = QWidget()
        status_layout = QVBoxLayout(self.status_tab)
        status_layout.setContentsMargins(8, 8, 8, 8)
        status_layout.setSpacing(5)
        
        # 当前下载任务
        status_label = QLabel("当前下载任务:")
        status_label.setStyleSheet("font-weight: bold;")
        status_layout.addWidget(status_label)
        
        self.current_task_label = QLabel("未开始下载")
        self.current_task_label.setStyleSheet("color: #0066cc;")
        status_layout.addWidget(self.current_task_label)
        
        # 整体进度
        self.overall_progress_label = QLabel("总进度: 0/0 (0%)")
        status_layout.addWidget(self.overall_progress_label)
        
        # 添加提示信息
        tips_label = QLabel("提示: 点击\"开始下载\"按钮开始下载任务。下载进度将显示在\"下载列表\"标签页中。")
        tips_label.setStyleSheet("color: #666; margin-top: 10px;")
        tips_label.setWordWrap(True)
        status_layout.addWidget(tips_label)
        
        # 添加伸展因子，使内容靠上对齐
        status_layout.addStretch(1)
        
        # 创建下载列表标签页
        self.list_tab = QWidget()
        list_layout = QVBoxLayout(self.list_tab)
        list_layout.setContentsMargins(8, 8, 8, 8)
        list_layout.setSpacing(5)
        
        # 添加提示信息
        list_tip_label = QLabel("下载进度将显示在此处。下载完成后可以使用\"清空列表\"按钮清除记录。")
        list_tip_label.setStyleSheet("color: #666;")
        list_tip_label.setWordWrap(True)
        list_layout.addWidget(list_tip_label)
        
        # 创建下载列表
        self.download_list = QListWidget()
        self.download_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        list_layout.addWidget(self.download_list)
        
        # 将两个标签页添加到标签页控件
        self.download_tabs.addTab(self.status_tab, "下载状态")
        self.download_tabs.addTab(self.list_tab, "下载列表")
        
        # 连接标签页切换信号，清除星号提示
        self.download_tabs.currentChanged.connect(self._on_tab_changed)
        
        # 添加到主布局
        self.main_layout.addWidget(self.download_tabs, 4)  # 给标签页更多的空间
    
    def _create_action_buttons(self):
        """创建底部操作按钮"""
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 5, 0, 0)  # 增加上边距
        
        self.start_button = QPushButton("开始下载")
        self.start_button.setMinimumHeight(40)
        self.start_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        self.save_config_button = QPushButton("保存配置")
        self.save_config_button.setMinimumHeight(30)
        self.save_config_button.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        
        self.clear_list_button = QPushButton("清空列表")
        self.clear_list_button.setMinimumHeight(30)
        self.clear_list_button.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.save_config_button)
        button_layout.addWidget(self.clear_list_button)
        
        self.main_layout.addLayout(button_layout)
    
    def _connect_signals(self):
        """连接信号和槽"""
        # 频道管理
        self.add_channel_button.clicked.connect(self._add_channel)
        self.remove_channel_button.clicked.connect(self._remove_channels)
        
        # 路径浏览
        self.browse_path_button.clicked.connect(self._browse_download_path)
        
        # 下载控制
        self.start_button.clicked.connect(self._start_download)
        self.save_config_button.clicked.connect(self._save_config)
        self.clear_list_button.clicked.connect(self.clear_download_list)
        
        # 下载标签页切换
        self.download_tabs.currentChanged.connect(self._on_tab_changed)
        
        # 如果有父窗口，尝试连接config_saved信号
        parent = self.parent()
        if parent and hasattr(parent, 'save_config'):
            self.config_saved.connect(parent.save_config)
    
    def _init_ui_state(self):
        """初始化UI状态"""
        # 设置工具提示
        self.channel_input.setToolTip("输入Telegram频道链接或ID")
        self.start_id.setToolTip("起始消息ID (包含)")
        self.end_id.setToolTip("结束消息ID (包含), 0表示最新消息")
        self.browse_path_button.setToolTip("选择下载文件保存位置")
        
        # 关键词输入提示 - 移除对use_keywords的检查
        self.keyword_input.setToolTip("输入要筛选的关键词")
    
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
        
        # 获取关键词
        keywords = []
        keywords_text = self.keyword_input.text().strip()
        if keywords_text:
            keywords = [k.strip() for k in keywords_text.split(',') if k.strip()]
        
        # 获取选中的媒体类型
        media_types = self._get_media_types()
        
        # 创建频道数据
        channel_data = {
            'channel': channel,
            'start_id': self.start_id.value(),
            'end_id': self.end_id.value(),
            'keywords': keywords,
            'media_types': media_types
        }
        
        # 创建列表项并设置文本
        item = QListWidgetItem()
        display_text = f"{channel} (ID范围: {channel_data['start_id']}-{channel_data['end_id'] if channel_data['end_id'] > 0 else '最新'})"
        
        # 如果有关键词，添加到显示文本中
        if keywords:
            keywords_str = '，'.join(keywords)
            display_text += f"（关键词：{keywords_str}）"
        
        # 添加媒体类型到显示文本中
        if media_types:
            media_types_display = {
                "photo": "照片",
                "video": "视频",
                "document": "文档",
                "audio": "音频",
                "animation": "动画"
            }
            media_types_str = '、'.join([media_types_display.get(t, t) for t in media_types])
            display_text += f"（媒体类型：{media_types_str}）"
        
        item.setText(display_text)
        item.setData(Qt.UserRole, channel_data)
        
        # 添加到列表
        self.channel_list.addItem(item)
        
        # 清空输入
        self.channel_input.clear()
        self.keyword_input.clear()
        
        # 更新频道列表标题
        self._update_channel_list_title()
    
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
        
        # 更新频道列表标题
        self._update_channel_list_title()
    
    def _get_media_types(self):
        """获取选中的媒体类型
        
        Returns:
            list: 媒体类型列表
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
        """获取所有频道中配置的关键词列表
        
        Returns:
            list: 关键词列表
        """
        keywords = []
        for i in range(self.channel_list.count()):
            channel_data = self.channel_list.item(i).data(Qt.UserRole)
            if 'keywords' in channel_data and channel_data['keywords']:
                for keyword in channel_data['keywords']:
                    if keyword not in keywords:
                        keywords.append(keyword)
        
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
        
        # 获取关键词列表，不再需要检查是否是关键词模式
        keywords = self._get_keywords()
        
        # 收集配置
        config = {
            'channels': self._get_channels(),
            'media_types': media_types,
            'keywords': keywords,
            'download_path': self.download_path.text(),
            'parallel_download': self.parallel_check.isChecked(),
            'max_concurrent_downloads': self.max_downloads.value() if self.parallel_check.isChecked() else 1,
            'use_keywords': self.use_keywords  # 保留此字段以便后台处理兼容
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
        
        # 从UI收集频道设置
        download_setting = []
        for i in range(self.channel_list.count()):
            channel_data = self.channel_list.item(i).data(Qt.UserRole)
            
            # 收集并转换媒体类型
            media_types = channel_data.get('media_types', ["photo", "video", "document", "audio", "animation"])
            
            # 确保媒体类型是有效的值
            valid_media_types = []
            for mt in media_types:
                try:
                    # 如果已经是字符串，检查是否是有效的MediaType值
                    if isinstance(mt, str) and mt in [e.value for e in MediaType]:
                        valid_media_types.append(mt)
                    elif isinstance(mt, MediaType):
                        # 如果已经是MediaType实例，直接添加其值
                        valid_media_types.append(mt.value)
                except Exception as e:
                    logger.warning(f"跳过无效的媒体类型 {mt}: {e}")
            
            # 如果没有有效的媒体类型，添加默认类型
            if not valid_media_types:
                valid_media_types = ["photo", "video", "document", "audio", "animation"]
            
            setting_item = {
                'source_channels': channel_data.get('channel', ''),
                'start_id': channel_data.get('start_id', 0),
                'end_id': channel_data.get('end_id', 0),
                'keywords': channel_data.get('keywords', []),
                'media_types': valid_media_types
            }
            download_setting.append(setting_item)
        
        # 按照现有配置结构更新DOWNLOAD部分
        download_config = {
            'downloadSetting': download_setting,
            'download_path': self.download_path.text(),
            'parallel_download': self.parallel_check.isChecked(),
            'max_concurrent_downloads': self.max_downloads.value()
        }
        
        # 组织完整配置
        updated_config = {}
        if isinstance(self.config, dict):
            updated_config = self.config.copy()  # 复制当前配置
        
        # 更新DOWNLOAD部分
        updated_config['DOWNLOAD'] = download_config
        
        # 发送配置保存信号
        logger.debug(f"向主窗口发送配置保存信号，更新下载配置")
        self.config_saved.emit(updated_config)
        
        # 显示成功消息
        QMessageBox.information(self, "配置保存", "下载配置已保存")
        
        # 更新本地配置引用
        self.config = updated_config
    
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
            
            # 如果当前不在下载列表标签页，显示提示
            if self.download_tabs.currentIndex() != 1:  # 1是下载列表的索引
                # 切换到下载列表标签页查看详情
                self.download_tabs.setTabText(1, "下载列表 *")  # 添加星号表示有新内容
    
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
        
        # 切换到下载状态标签页
        if self.download_tabs.currentIndex() != 0:  # 0是下载状态的索引
            self.download_tabs.setTabText(0, "下载状态 *")  # 添加星号表示有更新
        
        # 如果已全部完成，启用开始按钮
        if completed >= total and total > 0:
            self.start_button.setEnabled(True)
            # 恢复标签页文本
            self.download_tabs.setTabText(0, "下载状态")
            self.download_tabs.setTabText(1, "下载列表")
    
    def update_current_task(self, task_description):
        """更新当前任务描述
        
        Args:
            task_description: 任务描述文本
        """
        self.current_task_label.setText(task_description)
        
        # 如果不在下载状态标签页，添加提示
        if self.download_tabs.currentIndex() != 0:  # 0是下载状态的索引
            self.download_tabs.setTabText(0, "下载状态 *")  # 添加星号表示有更新
    
    def clear_download_list(self):
        """清空下载列表"""
        self.download_list.clear()
        self.download_tabs.setTabText(1, "下载列表")  # 恢复标签页文本
        
    def load_config(self, config):
        """从配置加载UI状态
        
        Args:
            config: 配置字典
        """
        # 清空现有项目
        self.channel_list.clear()
        
        # 加载频道
        download_settings = config.get('DOWNLOAD', {}).get('downloadSetting', [])
        for setting in download_settings:
            channel_data = {
                'channel': setting.get('source_channels', ''),
                'start_id': setting.get('start_id', 1),
                'end_id': setting.get('end_id', 0),
                'keywords': setting.get('keywords', []),
                'media_types': setting.get('media_types', ["photo", "video", "document", "audio", "animation"])
            }
            
            if channel_data['channel']:
                item = QListWidgetItem()
                display_text = f"{channel_data['channel']} (ID范围: {channel_data['start_id']}-{channel_data['end_id'] if channel_data['end_id'] > 0 else '最新'})"
                
                # 如果有关键词，添加到显示文本中
                if channel_data['keywords']:
                    keywords_str = '，'.join(channel_data['keywords'])
                    display_text += f"（关键词：{keywords_str}）"
                
                # 添加媒体类型到显示文本中
                if channel_data['media_types']:
                    media_types_display = {
                        "photo": "照片",
                        "video": "视频",
                        "document": "文档",
                        "audio": "音频",
                        "animation": "动画"
                    }
                    media_types_str = '、'.join([media_types_display.get(t, t) for t in channel_data['media_types']])
                    display_text += f"（媒体类型：{media_types_str}）"
                
                item.setText(display_text)
                item.setData(Qt.UserRole, channel_data)
                self.channel_list.addItem(item)
        
        # 更新频道列表标题
        self._update_channel_list_title()
        
        # 加载默认媒体类型 - 不再从单一位置加载，而是根据每个频道单独设置
        # 这里只设置默认选中状态
        self.photo_check.setChecked(True)
        self.video_check.setChecked(True)
        self.document_check.setChecked(True)
        self.audio_check.setChecked(True)
        self.animation_check.setChecked(True)
        
        # 加载下载路径
        download_path = config.get('DOWNLOAD', {}).get('download_path', 'downloads')
        self.download_path.setText(download_path)
        
        # 加载并行下载设置
        parallel_download = config.get('DOWNLOAD', {}).get('parallel_download', False)
        self.parallel_check.setChecked(parallel_download)
        
        max_concurrent = config.get('DOWNLOAD', {}).get('max_concurrent_downloads', 5)
        self.max_downloads.setValue(max_concurrent)
    
    def _on_tab_changed(self, index):
        """标签页切换事件处理
        
        Args:
            index: 新的标签页索引
        """
        # 清除当前标签页的星号提示
        current_tab_text = self.download_tabs.tabText(index)
        if current_tab_text.endswith(" *"):
            self.download_tabs.setTabText(index, current_tab_text[:-2]) 
    
    def _update_channel_list_title(self):
        """更新频道列表标题，显示频道数量"""
        channel_count = self.channel_list.count()
        self.channel_list_label.setText(f"已配置下载频道:  {channel_count}个") 