"""
TG-Manager 转发界面
实现Telegram频道间消息转发功能
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QCheckBox, QPushButton,
    QGroupBox, QScrollArea, QSpinBox, QGridLayout,
    QListWidget, QListWidgetItem, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QTextEdit, QSplitter, QAbstractItemView,
    QProgressBar, QTabWidget, QSizePolicy, QFileDialog,
    QDoubleSpinBox
)
from PySide6.QtCore import Qt, Signal, Slot, QSize
from PySide6.QtGui import QIcon

from src.utils.logger import get_logger
from src.utils.ui_config_models import MediaType, UIChannelPair, UIForwardConfig

logger = get_logger()


class ForwardView(QWidget):
    """转发界面，提供Telegram频道间消息转发功能"""
    
    # 转发开始信号
    forward_started = Signal(dict)  # 转发配置
    # 配置保存信号
    config_saved = Signal(dict)  # 添加配置保存信号
    
    def __init__(self, config=None, parent=None):
        """初始化转发界面
        
        Args:
            config: 配置对象
            parent: 父窗口部件
        """
        super().__init__(parent)
        
        self.config = config or {}
        # 初始化频道对列表
        self.channel_pairs = []
        
        # 设置布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(2)  # 减小布局间距
        self.main_layout.setContentsMargins(4, 4, 4, 4)  # 减小边距
        self.setLayout(self.main_layout)
        
        # 设置统一的组框样式
        # self.setStyleSheet("""
        #     QGroupBox { 
        #         font-weight: bold; 
        #         padding-top: 2px; 
        #         margin-top: 0.4em; 
        #     }
        #     QTabWidget::pane {
        #         border: 1px solid #444;
        #         padding: 1px;
        #     }
        #     QTabBar::tab {
        #         padding: 3px 8px;
        #     }
        #     QListWidget {
        #         alternate-background-color: rgba(60, 60, 60, 0.2);
        #     }
        #     QListWidget::item {
        #         border-bottom: 1px solid rgba(100, 100, 100, 0.1);
        #         padding: 4px 2px;
        #     }
        #     QListWidget::item:selected {
        #         background-color: rgba(0, 120, 215, 0.6);
        #     }
        # """)
        
        # 创建上部配置标签页
        self.config_tabs = QTabWidget()
        self.config_tabs.setMaximumHeight(320)  # 设置最大高度
        self.config_tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.main_layout.addWidget(self.config_tabs)
        
        # 创建配置标签页
        self._create_config_panel()
        
        # 创建下部转发状态面板
        self._create_forward_panel()
        
        # 创建底部操作按钮
        self._create_action_buttons()
        
        # 连接信号
        self._connect_signals()
        
        # 初始化状态
        self._init_state()
        
        # 加载配置
        if self.config:
            self.load_config(self.config)
        
        logger.info("转发界面初始化完成")
    
    def _create_config_panel(self):
        """创建配置标签页"""
        # 频道配置标签页（原源频道标签页）
        self.channel_tab = QWidget()
        channel_layout = QVBoxLayout(self.channel_tab)
        channel_layout.setContentsMargins(4, 4, 4, 4)  # 减小边距
        channel_layout.setSpacing(4)  # 减小间距
        
        # 源频道和目标频道输入表单
        form_layout = QFormLayout()
        
        self.source_input = QLineEdit()
        self.source_input.setPlaceholderText("频道链接或ID (例如: https://t.me/example 或 -1001234567890)")
        form_layout.addRow("源频道:", self.source_input)
        
        self.target_input = QLineEdit()
        self.target_input.setPlaceholderText("目标频道，多个用逗号分隔 (例如: @channel1, @channel2)")
        form_layout.addRow("目标频道:", self.target_input)
        
        channel_layout.addLayout(form_layout)
        
        # 添加频道对按钮和消息ID范围放在同一行
        button_layout = QHBoxLayout()
        
        # 消息ID范围放在左边
        button_layout.addWidget(QLabel("起始ID:"))
        self.start_id = QSpinBox()
        self.start_id.setRange(0, 999999999)
        self.start_id.setValue(0)
        self.start_id.setSpecialValueText("最早消息")  # 当值为0时显示为"最早消息"
        self.start_id.setFixedWidth(100)
        button_layout.addWidget(self.start_id)
        
        button_layout.addWidget(QLabel("结束ID:"))
        self.end_id = QSpinBox()
        self.end_id.setRange(0, 999999999)
        self.end_id.setValue(0)
        self.end_id.setSpecialValueText("最新消息")  # 当值为0时显示为"最新消息"
        self.end_id.setFixedWidth(100)
        button_layout.addWidget(self.end_id)
        
        # 添加弹性空间，将按钮推到右边
        button_layout.addStretch(1)
        
        # "添加频道对"和"删除所选"按钮放在右边
        self.add_pair_button = QPushButton("添加频道对")
        self.remove_pair_button = QPushButton("删除所选")
        
        button_layout.addWidget(self.add_pair_button)
        button_layout.addWidget(self.remove_pair_button)
        
        channel_layout.addLayout(button_layout)
        
        # 要转发的媒体类型
        media_layout = QHBoxLayout()
        media_layout.setContentsMargins(0, 8, 0, 0)  # 增加上边距
        
        media_layout.addWidget(QLabel("要转发的媒体类型:"))
        
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
        
        media_layout.addStretch(1)  # 添加弹簧，让控件靠左对齐
        channel_layout.addLayout(media_layout)
        
        # 创建频道列表部分
        # 频道列表标题
        self.pairs_list_label = QLabel("已配置频道对:  0对")
        self.pairs_list_label.setStyleSheet("font-weight: bold;")  # 加粗标签
        channel_layout.addWidget(self.pairs_list_label)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)  # 允许小部件调整大小
        scroll_area.setFixedHeight(100)  # 设置滚动区域的固定高度
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 创建一个容器部件来包含列表
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(0)
        
        # 频道对列表
        self.pairs_list = QListWidget()
        self.pairs_list.setSelectionMode(QListWidget.ExtendedSelection)
        scroll_layout.addWidget(self.pairs_list)
        
        # 设置滚动区域的内容
        scroll_area.setWidget(scroll_content)
        channel_layout.addWidget(scroll_area)
        
        # 转发选项标签页
        self.options_tab = QWidget()
        options_layout = QVBoxLayout(self.options_tab)
        options_layout.setContentsMargins(5, 5, 5, 5)
        
        # 移除说明文字选项
        self.remove_captions_check = QCheckBox("移除媒体说明文字")
        options_layout.addWidget(self.remove_captions_check)
        
        # 隐藏原作者选项
        self.hide_author_check = QCheckBox("隐藏原作者")
        options_layout.addWidget(self.hide_author_check)
        
        # 转发延迟
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("转发延迟:"))
        
        self.forward_delay = QDoubleSpinBox()
        self.forward_delay.setRange(0, 60)
        self.forward_delay.setValue(0)
        self.forward_delay.setDecimals(1)
        self.forward_delay.setSingleStep(0.1)
        self.forward_delay.setSuffix(" 秒")
        delay_layout.addWidget(self.forward_delay)
        delay_layout.addStretch(1)
        
        options_layout.addLayout(delay_layout)
        
        # 临时文件路径
        tmp_layout = QHBoxLayout()
        tmp_layout.addWidget(QLabel("临时目录:"))
        
        self.tmp_path = QLineEdit("tmp")
        tmp_layout.addWidget(self.tmp_path)
        
        self.browse_tmp_button = QPushButton("浏览...")
        tmp_layout.addWidget(self.browse_tmp_button)
        
        options_layout.addLayout(tmp_layout)
        
        # 添加弹性空间
        options_layout.addStretch(1)
        
        # 将标签页添加到配置面板
        self.config_tabs.addTab(self.channel_tab, "频道配置")
        self.config_tabs.addTab(self.options_tab, "转发选项")
    
    def _create_forward_panel(self):
        """创建转发状态面板"""
        # 创建底部容器
        self.status_container = QWidget()
        self.status_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        status_layout = QVBoxLayout(self.status_container)
        status_layout.setContentsMargins(6, 6, 6, 6)
        
        # 状态表格
        self.status_table = QTableWidget()
        self.status_table.setColumnCount(4)
        self.status_table.setHorizontalHeaderLabels(["源频道", "目标频道", "已转发消息数", "状态"])
        self.status_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.status_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.status_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        status_layout.addWidget(self.status_table)
        
        # 状态信息布局
        status_info_layout = QHBoxLayout()
        
        self.overall_status_label = QLabel("等待转发...")
        self.forwarded_count_label = QLabel("已转发: 0 条消息")
        
        status_info_layout.addWidget(self.overall_status_label)
        status_info_layout.addStretch()
        status_info_layout.addWidget(self.forwarded_count_label)
        
        status_layout.addLayout(status_info_layout)
        
        # 进度指示器
        progress_layout = QVBoxLayout()
        
        progress_label = QLabel("总体进度:")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        
        progress_layout.addWidget(progress_label)
        progress_layout.addWidget(self.progress_bar)
        
        status_layout.addLayout(progress_layout)
        
        # 添加状态容器到主布局
        self.main_layout.addWidget(self.status_container, 1)
    
    def _create_action_buttons(self):
        """创建底部操作按钮"""
        button_layout = QHBoxLayout()
        
        self.start_forward_button = QPushButton("开始转发")
        self.start_forward_button.setMinimumHeight(40)
        
        self.stop_forward_button = QPushButton("停止转发")
        self.stop_forward_button.setEnabled(False)
        
        self.save_config_button = QPushButton("保存配置")
        
        button_layout.addWidget(self.start_forward_button)
        button_layout.addWidget(self.stop_forward_button)
        button_layout.addWidget(self.save_config_button)
        
        self.main_layout.addLayout(button_layout)
    
    def _connect_signals(self):
        """连接信号和槽"""
        # 频道对管理
        self.add_pair_button.clicked.connect(self._add_channel_pair)
        self.remove_pair_button.clicked.connect(self._remove_channel_pairs)
        
        # 临时目录浏览
        self.browse_tmp_button.clicked.connect(self._browse_tmp_path)
        
        # 转发控制
        self.start_forward_button.clicked.connect(self._start_forward)
        self.stop_forward_button.clicked.connect(self._stop_forward)
        self.save_config_button.clicked.connect(self._save_config)
        
        # 如果有父窗口，尝试连接config_saved信号
        parent = self.parent()
        if parent and hasattr(parent, 'save_config'):
            self.config_saved.connect(parent.save_config)
    
    def _init_state(self):
        """初始化状态"""
        # 更新频道对列表标题
        self._update_pairs_list_title()
        
    def _update_pairs_list_title(self):
        """更新频道对列表标题"""
        count = self.pairs_list.count()
        self.pairs_list_label.setText(f"已配置频道对:  {count}对")
    
    def _add_channel_pair(self):
        """添加频道对"""
        # 获取源频道和目标频道
        source = self.source_input.text().strip()
        if not source:
            QMessageBox.warning(self, "警告", "请输入源频道链接或ID")
            return
        
        target_text = self.target_input.text().strip()
        if not target_text:
            QMessageBox.warning(self, "警告", "请输入目标频道链接或ID")
            return
        
        # 分割多个目标频道
        target_channels = [t.strip() for t in target_text.split(',') if t.strip()]
        if not target_channels:
            QMessageBox.warning(self, "警告", "无效的目标频道")
            return
        
        # 获取消息ID范围
        start_id = self.start_id.value()
        end_id = self.end_id.value()
        
        # 获取选中的媒体类型
        media_types = self._get_media_types()
        if not media_types:
            QMessageBox.warning(self, "警告", "请至少选择一种媒体类型")
            return
        
        try:
            # 使用UIChannelPair进行验证
            channel_pair = {
                'source_channel': UIChannelPair.validate_channel_id(source, "源频道"),
                'target_channels': [UIChannelPair.validate_channel_id(t, f"目标频道 {i+1}") 
                                   for i, t in enumerate(target_channels)],
                'media_types': media_types,
                'start_id': start_id,
                'end_id': end_id
            }
            
            # 添加到列表中
            item = QListWidgetItem()
            
            # 创建媒体类型显示文本
            media_types_str = []
            if MediaType.PHOTO in media_types:
                media_types_str.append("照片")
            if MediaType.VIDEO in media_types:
                media_types_str.append("视频")
            if MediaType.DOCUMENT in media_types:
                media_types_str.append("文档")
            if MediaType.AUDIO in media_types:
                media_types_str.append("音频")
            if MediaType.ANIMATION in media_types:
                media_types_str.append("动画")
            
            # 构建ID范围显示文本
            id_range_str = ""
            if start_id > 0 or end_id > 0:
                if start_id > 0 and end_id > 0:
                    id_range_str = f"ID范围: {start_id}-{end_id}"
                elif start_id > 0:
                    id_range_str = f"ID范围: {start_id}+"
                else:
                    id_range_str = f"ID范围: 最早-{end_id}"
                id_range_str = " - " + id_range_str
            
            # 构建显示文本
            display_text = f"{channel_pair['source_channel']} → {', '.join(channel_pair['target_channels'])} (媒体类型：{', '.join(media_types_str)}){id_range_str}"
            
            item.setText(display_text)
            item.setData(Qt.UserRole, channel_pair)
            self.pairs_list.addItem(item)
            
            # 清空输入框
            self.source_input.clear()
            self.target_input.clear()
            
            # 更新标题
            self._update_pairs_list_title()
            
            # 添加到频道对列表
            self.channel_pairs.append(channel_pair)
        
        except ValueError as e:
            QMessageBox.warning(self, "输入错误", str(e))
    
    def _remove_channel_pairs(self):
        """删除选中的频道对"""
        selected_items = self.pairs_list.selectedItems()
        
        if not selected_items:
            QMessageBox.information(self, "提示", "请先选择要删除的频道对")
            return
        
        # 获取所有选中项的数据和索引
        items_to_remove = []
        for item in selected_items:
            row = self.pairs_list.row(item)
            items_to_remove.append((row, item))
        
        # 按行号倒序排序，确保从后向前删除，避免索引变化导致错误
        items_to_remove.sort(reverse=True, key=lambda x: x[0])
        
        # 删除选中的频道对
        for row, item in items_to_remove:
            # 同时从channel_pairs和list widget中删除
            if 0 <= row < len(self.channel_pairs):
                self.channel_pairs.pop(row)
            self.pairs_list.takeItem(row)
        
        # 更新标题
        self._update_pairs_list_title()
    
    def _browse_tmp_path(self):
        """浏览临时目录路径"""
        current_path = self.tmp_path.text()
        path = QFileDialog.getExistingDirectory(self, "选择临时文件目录", current_path)
        if path:
            self.tmp_path.setText(path)
    
    def _get_media_types(self):
        """获取选中的媒体类型
        
        Returns:
            list: 媒体类型列表
        """
        media_types = []
        
        if self.photo_check.isChecked():
            media_types.append(MediaType.PHOTO)
        
        if self.video_check.isChecked():
            media_types.append(MediaType.VIDEO)
        
        if self.document_check.isChecked():
            media_types.append(MediaType.DOCUMENT)
        
        if self.audio_check.isChecked():
            media_types.append(MediaType.AUDIO)
        
        if self.animation_check.isChecked():
            media_types.append(MediaType.ANIMATION)
        
        return media_types
    
    def _start_forward(self):
        """开始转发"""
        # 频道对列表
        channel_pairs = []
        
        # 检查是否有频道对
        if len(self.channel_pairs) == 0:
            # 提示用户
            response = QMessageBox.question(self, "无转发频道对", 
                "转发列表中没有配置频道对，是否使用默认频道对(@username → @username)？\n"
                "可以在开始转发后修改API配置中的具体频道信息。",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            
            if response == QMessageBox.No:
                return
            
            # 创建默认频道对
            default_pair = {
                'source_channel': "@username",
                'target_channels': ["@username"],
                'media_types': self._get_media_types(),
                'start_id': self.start_id.value(),
                'end_id': self.end_id.value()
            }
            channel_pairs.append(default_pair)
            logger.debug("使用默认频道对进行转发")
        else:
            channel_pairs = self.channel_pairs
            # 确保每个频道对都有媒体类型
            for pair in channel_pairs:
                if not pair.get('media_types'):
                    pair['media_types'] = self._get_media_types()
        
        # 收集配置
        forward_config = {
            'forward_channel_pairs': channel_pairs,
            'remove_captions': self.remove_captions_check.isChecked(),
            'hide_author': self.hide_author_check.isChecked(),
            'forward_delay': self.forward_delay.value(),
            'tmp_path': self.tmp_path.text()
        }
        
        # 准备状态表格
        self.status_table.setRowCount(0)
        row_count = 0
        
        # 为每个频道对添加一行
        for channel_pair in channel_pairs:
            source = channel_pair['source_channel']
            for target in channel_pair['target_channels']:
                self.status_table.insertRow(row_count)
                self.status_table.setItem(row_count, 0, QTableWidgetItem(source))
                self.status_table.setItem(row_count, 1, QTableWidgetItem(target))
                self.status_table.setItem(row_count, 2, QTableWidgetItem("0"))
                self.status_table.setItem(row_count, 3, QTableWidgetItem("等待中"))
                row_count += 1
        
        # 更新状态
        self.overall_status_label.setText("转发开始...")
        self.forwarded_count_label.setText("已转发: 0 条消息")
        
        # 更新按钮状态
        self.start_forward_button.setEnabled(False)
        self.stop_forward_button.setEnabled(True)
        
        # 发出转发开始信号
        self.forward_started.emit(forward_config)
    
    def _stop_forward(self):
        """停止转发"""
        # TODO: 实现停止转发功能
        
        # 更新状态
        self.overall_status_label.setText("转发已停止")
        
        # 更新按钮状态
        self.start_forward_button.setEnabled(True)
        self.stop_forward_button.setEnabled(False)
    
    def _save_config(self):
        """保存当前配置"""
        try:
            # 创建UIChannelPair对象列表
            ui_channel_pairs = []
            
            # 如果列表为空，使用默认频道对
            if len(self.channel_pairs) == 0:
                # 使用当前设置的媒体类型和消息ID，创建一个默认频道对
                default_channel_pair = UIChannelPair(
                    source_channel="@username",  # 使用占位符频道名
                    target_channels=["@username"],  # 使用占位符频道名
                    media_types=self._get_media_types(),
                    start_id=self.start_id.value(),
                    end_id=self.end_id.value()
                )
                ui_channel_pairs.append(default_channel_pair)
                logger.debug("使用默认频道对替代空列表")
            else:
                # 使用已有的频道对
                for pair in self.channel_pairs:
                    ui_channel_pairs.append(UIChannelPair(
                        source_channel=pair['source_channel'],
                        target_channels=pair['target_channels'],
                        media_types=pair.get('media_types', self._get_media_types()),
                        start_id=pair.get('start_id', 0),
                        end_id=pair.get('end_id', 0)
                    ))
            
            # 创建UIForwardConfig对象
            forward_config = UIForwardConfig(
                forward_channel_pairs=ui_channel_pairs,
                remove_captions=self.remove_captions_check.isChecked(),
                hide_author=self.hide_author_check.isChecked(),
                forward_delay=round(float(self.forward_delay.value()), 1),  # 四舍五入到一位小数，解决精度问题
                tmp_path=self.tmp_path.text()
            )
            
            # 组织完整配置
            updated_config = {}
            if isinstance(self.config, dict):
                updated_config = self.config.copy()  # 复制当前配置
            
            # 使用模型的dict()方法将对象转换为字典
            updated_config['FORWARD'] = forward_config.dict()
            
            # 发送配置保存信号
            logger.debug(f"向主窗口发送配置保存信号，更新转发配置")
            self.config_saved.emit(updated_config)
            
            # 显示成功消息
            QMessageBox.information(self, "配置保存", "转发配置已保存")
            
            # 更新本地配置引用
            self.config = updated_config
            
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"配置保存失败: {str(e)}")
            logger.error(f"保存配置失败: {e}")
            import traceback
            logger.debug(f"错误详情:\n{traceback.format_exc()}")
    
    def update_forward_status(self, source, target, count, status):
        """更新转发状态
        
        Args:
            source: 源频道
            target: 目标频道
            count: 转发消息数
            status: 状态文本
        """
        # 查找对应的行
        for row in range(self.status_table.rowCount()):
            if (self.status_table.item(row, 0).text() == source and
                self.status_table.item(row, 1).text() == target):
                
                # 更新消息数
                self.status_table.item(row, 2).setText(str(count))
                
                # 更新状态
                self.status_table.item(row, 3).setText(status)
                
                # 更新总转发消息数
                total_forwarded = sum(int(self.status_table.item(r, 2).text()) 
                                   for r in range(self.status_table.rowCount()))
                self.forwarded_count_label.setText(f"已转发: {total_forwarded} 条消息")
                
                break
    
    def update_progress(self, value):
        """更新进度条
        
        Args:
            value: 进度值 (0-100)
        """
        self.progress_bar.setValue(value)
    
    def forward_completed(self):
        """所有转发任务完成"""
        # 更新状态
        self.overall_status_label.setText("转发已完成")
        
        # 更新按钮状态
        self.start_forward_button.setEnabled(True)
        self.stop_forward_button.setEnabled(False)
    
    def load_config(self, config):
        """从配置加载UI状态
        
        Args:
            config: 配置字典
        """
        # 清空现有项目
        self.pairs_list.clear()
        self.channel_pairs.clear()
        
        # 加载配置中的频道对
        forward_config = config.get('FORWARD', {})
        channel_pairs = forward_config.get('forward_channel_pairs', [])
        
        # 记录第一个频道对的媒体类型和ID范围，用于设置控件初始状态
        first_pair_media_types = []
        first_pair_start_id = 0
        first_pair_end_id = 0
        
        # 添加频道对到列表
        for pair in channel_pairs:
            source_channel = pair.get('source_channel')
            target_channels = pair.get('target_channels', [])
            media_types = pair.get('media_types', [MediaType.PHOTO, MediaType.VIDEO, MediaType.DOCUMENT, MediaType.AUDIO, MediaType.ANIMATION])
            
            # 确保优先从频道对中获取消息ID范围
            start_id = pair.get('start_id', 0)
            end_id = pair.get('end_id', 0)
            
            if source_channel and target_channels:
                # 保存第一个频道对的设置，用于设置默认值
                if not first_pair_media_types:
                    first_pair_media_types = media_types
                    first_pair_start_id = start_id
                    first_pair_end_id = end_id
                
                # 创建频道对数据
                channel_pair = {
                    'source_channel': source_channel,
                    'target_channels': target_channels,
                    'media_types': media_types,
                    'start_id': start_id,
                    'end_id': end_id
                }
                
                # 添加到列表
                self.channel_pairs.append(channel_pair)
                
                # 创建媒体类型显示文本
                media_types_str = []
                if MediaType.PHOTO in media_types:
                    media_types_str.append("照片")
                if MediaType.VIDEO in media_types:
                    media_types_str.append("视频")
                if MediaType.DOCUMENT in media_types:
                    media_types_str.append("文档")
                if MediaType.AUDIO in media_types:
                    media_types_str.append("音频")
                if MediaType.ANIMATION in media_types:
                    media_types_str.append("动画")
                
                # 构建ID范围显示文本
                id_range_str = ""
                if start_id > 0 or end_id > 0:
                    if start_id > 0 and end_id > 0:
                        id_range_str = f"ID范围: {start_id}-{end_id}"
                    elif start_id > 0:
                        id_range_str = f"ID范围: {start_id}+"
                    else:
                        id_range_str = f"ID范围: 最早-{end_id}"
                    id_range_str = " - " + id_range_str
                
                # 创建列表项
                item = QListWidgetItem()
                display_text = f"{source_channel} → {', '.join(target_channels)} (媒体类型：{', '.join(media_types_str)}){id_range_str}"
                item.setText(display_text)
                item.setData(Qt.UserRole, channel_pair)
                self.pairs_list.addItem(item)
        
        # 更新频道对列表标题
        self._update_pairs_list_title()
        
        # 加载其他转发选项
        self.remove_captions_check.setChecked(forward_config.get('remove_captions', False))
        self.hide_author_check.setChecked(forward_config.get('hide_author', False))
        
        # 加载媒体类型复选框
        media_types = first_pair_media_types or forward_config.get('media_types', [])
        media_types_str = [str(t) for t in media_types]  # 确保类型为字符串
        
        self.photo_check.setChecked(MediaType.PHOTO in media_types_str)
        self.video_check.setChecked(MediaType.VIDEO in media_types_str)
        self.document_check.setChecked(MediaType.DOCUMENT in media_types_str) 
        self.audio_check.setChecked(MediaType.AUDIO in media_types_str)
        self.animation_check.setChecked(MediaType.ANIMATION in media_types_str)
        
        # 加载消息ID设置（使用第一个频道对的ID设置）
        self.start_id.setValue(first_pair_start_id)
        self.end_id.setValue(first_pair_end_id)
        
        # 加载其他设置
        forward_delay = forward_config.get('forward_delay', 0)
        # 确保转发延迟能以小数形式加载
        if isinstance(forward_delay, (int, float)):
            self.forward_delay.setValue(float(forward_delay))
        else:
            try:
                self.forward_delay.setValue(float(forward_delay))
            except (ValueError, TypeError):
                self.forward_delay.setValue(0.0)
                
        self.tmp_path.setText(forward_config.get('tmp_path', 'tmp'))

    def set_forwarder(self, forwarder):
        """设置转发器实例
        
        Args:
            forwarder: 转发器实例
        """
        if not forwarder:
            logger.warning("转发器实例为空，无法设置")
            return
            
        self.forwarder = forwarder
        logger.debug("转发视图已接收转发器实例")
        
        # 连接信号
        self._connect_forwarder_signals()
    
    def _connect_forwarder_signals(self):
        """连接转发器信号到UI更新"""
        if not hasattr(self, 'forwarder') or self.forwarder is None:
            logger.warning("转发器不存在，无法连接信号")
            return
            
        # 连接转发器事件处理器
        try:
            # 检查forwarder是否有信号属性并连接
            if hasattr(self.forwarder, 'status_updated'):
                self.forwarder.status_updated.connect(self._update_status)
            
            if hasattr(self.forwarder, 'progress_updated'):
                self.forwarder.progress_updated.connect(self._update_progress)
            
            if hasattr(self.forwarder, 'forward_completed'):
                self.forwarder.forward_completed.connect(self._on_forward_complete)
            
            if hasattr(self.forwarder, 'all_forwards_completed'):
                self.forwarder.all_forwards_completed.connect(self._on_all_forwards_complete)
            
            if hasattr(self.forwarder, 'error_occurred'):
                self.forwarder.error_occurred.connect(self._on_forward_error)
            
            logger.debug("转发器信号连接成功")
            
            # 如果转发器没有这些信号属性，我们需要手动添加事件监听
            # 这是为了兼容不同版本的转发器实现
            if not hasattr(self.forwarder, 'status_updated') and hasattr(self.forwarder, 'add_event_listener'):
                self.forwarder.add_event_listener("status", self._update_status)
                self.forwarder.add_event_listener("progress", self._update_progress)
                self.forwarder.add_event_listener("forward_complete", self._on_forward_complete)
                self.forwarder.add_event_listener("all_forwards_complete", self._on_all_forwards_complete)
                self.forwarder.add_event_listener("error", self._on_forward_error)
                logger.debug("使用事件监听器连接转发器事件")
            
        except Exception as e:
            logger.error(f"连接转发器信号时出错: {e}")
            import traceback
            logger.debug(f"错误详情:\n{traceback.format_exc()}")
    
    def _update_status(self, status):
        """更新状态信息
        
        Args:
            status: 状态信息
        """
        self.overall_status_label.setText(status)
        logger.debug(f"转发状态更新: {status}")
    
    def _update_progress(self, current, total, message_info=None):
        """更新转发进度
        
        Args:
            current: 当前处理消息索引
            total: 总消息数
            message_info: 消息信息(可选)
        """
        # 更新进度条
        if total > 0:
            percentage = min(int((current / total) * 100), 100)
            self.progress_bar.setValue(percentage)
            
            # 更新进度文本
            if message_info:
                self.progress_bar.setFormat(f"{message_info} - {percentage}%")
            else:
                self.progress_bar.setFormat("正在转发...")
        else:
            # 不确定的进度，使用循环进度条
            self.progress_bar.setRange(0, 0)
            if message_info:
                self.progress_bar.setFormat(f"正在转发: {message_info}")
            else:
                self.progress_bar.setFormat("正在转发...")
    
    def _on_forward_complete(self, msg_id, source_channel=None, target_channel=None):
        """转发完成处理
        
        Args:
            msg_id: 消息ID
            source_channel: 源频道(可选)
            target_channel: 目标频道(可选)
        """
        # 构建转发信息
        forward_info = f"消息ID: {msg_id}"
        if source_channel and target_channel:
            forward_info = f"消息ID: {msg_id}, 从 {source_channel} 到 {target_channel}"
        elif source_channel:
            forward_info = f"消息ID: {msg_id}, 来自 {source_channel}"
        elif target_channel:
            forward_info = f"消息ID: {msg_id}, 转发到 {target_channel}"
        
        # 添加到列表
        self._add_forwarded_item(forward_info)
        
        logger.debug(f"消息转发完成: {forward_info}")
    
    def _on_all_forwards_complete(self):
        """所有转发完成处理"""
        # 更新UI状态
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("所有转发已完成")
        self.overall_status_label.setText("转发任务已完成")
        
        # 恢复按钮状态
        self.start_forward_button.setEnabled(True)
        self.stop_forward_button.setEnabled(False)
        
        # 显示提示消息
        self._show_completion_message("转发完成", "所有消息已转发完成")
        
        logger.info("所有消息转发完成")
    
    def _on_forward_error(self, error, message=None):
        """转发错误处理
        
        Args:
            error: 错误信息
            message: 额外的消息(可选)
        """
        # 更新UI状态
        error_msg = f"转发出错: {error}"
        if message:
            error_msg += f"\n{message}"
            
        self.overall_status_label.setText(error_msg)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        
        # 恢复按钮状态
        self.start_forward_button.setEnabled(True)
        self.stop_forward_button.setEnabled(False)
        
        # 显示错误对话框
        self._show_error_dialog("转发错误", error_msg)
        
        logger.error(f"转发错误: {error}")
        if message:
            logger.debug(f"错误详情: {message}")
    
    def _add_forwarded_item(self, forward_info):
        """添加转发完成项目到列表
        
        Args:
            forward_info: 转发信息
        """
        # 转发状态信息不应该添加到频道配置列表中
        # 这里需要创建一个单独的转发状态列表
        # TODO: 创建一个单独的转发状态列表窗口
        
        logger.debug(f"消息转发完成: {forward_info}")
        # 临时解决方案：不再向频道对列表添加转发状态
        # from PySide6.QtWidgets import QListWidgetItem
        # item = QListWidgetItem(forward_info)
        # 
        # # 添加到已完成列表
        # self.pairs_list.addItem(item)
        # 
        # # 保持最新项可见
        # self.pairs_list.scrollToBottom()
    
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