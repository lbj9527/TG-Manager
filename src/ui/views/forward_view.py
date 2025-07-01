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
    QDoubleSpinBox, QDialog, QMenu
)
from PySide6.QtCore import Qt, Signal, Slot, QSize, QTimer, QMetaObject, Q_ARG, QPoint, QDir
from PySide6.QtGui import QIcon, QCursor

import asyncio
import time
import os
from pathlib import Path
from datetime import datetime

from src.utils.logger import get_logger
from src.utils.ui_config_models import MediaType, UIChannelPair, UIForwardConfig
from src.utils.async_utils import run_async_task

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
        # 移除最大高度限制，让标签页可以占用更多空间
        self.config_tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.main_layout.addWidget(self.config_tabs, 1)  # 使标签页可以自动拉伸
        
        # 创建配置标签页
        self._create_config_panel()
        
        # 创建转发进度标签页
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
        # 频道配置标签页（改为滚动区域）
        self.channel_tab = QWidget()
        # 创建主布局，只包含滚动区域
        main_config_layout = QVBoxLayout(self.channel_tab)
        main_config_layout.setContentsMargins(0, 0, 0, 0)  # 移除主布局边距
        main_config_layout.setSpacing(0)  # 移除主布局间距
        
        # 创建滚动区域
        config_scroll_area = QScrollArea()
        config_scroll_area.setWidgetResizable(True)  # 允许小部件调整大小
        config_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        config_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        config_scroll_area.setFrameShape(QScrollArea.NoFrame)  # 移除边框，使界面更简洁
        
        # 创建滚动内容容器
        scroll_content_widget = QWidget()
        config_layout = QVBoxLayout(scroll_content_widget)
        config_layout.setContentsMargins(12, 12, 12, 12)  # 增加滚动内容边距
        config_layout.setSpacing(15)  # 增加间距，使界面更舒适
        
        # 第一行：源频道
        source_form_layout = QFormLayout()
        source_form_layout.setSpacing(10)
        source_form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        source_form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        
        self.source_input = QLineEdit()
        self.source_input.setPlaceholderText("频道链接或ID (例如: https://t.me/example 或 -1001234567890)")
        source_form_layout.addRow("源频道:", self.source_input)
        config_layout.addLayout(source_form_layout)
        
        # 第二行：目标频道
        target_form_layout = QFormLayout()
        target_form_layout.setSpacing(10)
        target_form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        target_form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        
        self.target_input = QLineEdit()
        self.target_input.setPlaceholderText("目标频道，多个用英文逗号分隔 (例如: @channel1, @channel2)")
        target_form_layout.addRow("目标频道:", self.target_input)
        config_layout.addLayout(target_form_layout)
        
        # 第三行：文本替换
        text_replace_form_layout = QFormLayout()
        text_replace_form_layout.setSpacing(10)
        text_replace_form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        text_replace_form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        
        self.original_text_input = QLineEdit()
        self.original_text_input.setPlaceholderText("要替换的原始文本，多个用英文逗号分隔如：A,B")
        text_replace_form_layout.addRow("文本替换:", self.original_text_input)
        config_layout.addLayout(text_replace_form_layout)
        
        # 第四行：替换为
        replace_to_form_layout = QFormLayout()
        replace_to_form_layout.setSpacing(10)
        replace_to_form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        replace_to_form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        
        self.target_text_input = QLineEdit()
        self.target_text_input.setPlaceholderText("替换后的目标文本，多个用英文逗号分隔如：C,D")
        replace_to_form_layout.addRow("替换为:", self.target_text_input)
        config_layout.addLayout(replace_to_form_layout)
        
        # 第五行：过滤选项label
        filter_options_label = QLabel("过滤选项:")
        filter_options_label.setStyleSheet("font-weight: bold;")
        config_layout.addWidget(filter_options_label)
        
        # 第六行：关键词过滤
        keyword_form_layout = QFormLayout()
        keyword_form_layout.setSpacing(10)
        keyword_form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        keyword_form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        
        # 关键词输入框和说明布局
        keyword_layout = QHBoxLayout()
        keyword_layout.setSpacing(8)
        
        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("关键词，多个用英文逗号分隔，只转发包含关键词的消息")
        keyword_layout.addWidget(self.keyword_input)
        
        keyword_form_layout.addRow("关键词过滤:", keyword_layout)
        config_layout.addLayout(keyword_form_layout)
        
        # 第七行：媒体类型
        # 媒体类型复选框布局（移除标签）
        media_types_layout = QHBoxLayout()
        
        self.text_check = QCheckBox("纯文本")
        self.text_check.setChecked(True)
        media_types_layout.addWidget(self.text_check)
        
        self.photo_check = QCheckBox("照片")
        self.photo_check.setChecked(True)
        media_types_layout.addWidget(self.photo_check)
        
        self.video_check = QCheckBox("视频")
        self.video_check.setChecked(True)
        media_types_layout.addWidget(self.video_check)
        
        self.document_check = QCheckBox("文档")
        self.document_check.setChecked(True)
        media_types_layout.addWidget(self.document_check)
        
        self.audio_check = QCheckBox("音频")
        self.audio_check.setChecked(True)
        media_types_layout.addWidget(self.audio_check)
        
        self.animation_check = QCheckBox("动画")
        self.animation_check.setChecked(True)
        media_types_layout.addWidget(self.animation_check)
        
        media_types_layout.addStretch(1)  # 添加弹性空间，让复选框靠左对齐
        config_layout.addLayout(media_types_layout)
        
        # 第八行：转发参数
        forward_params_label = QLabel("转发参数:")
        forward_params_label.setStyleSheet("font-weight: bold;")
        config_layout.addWidget(forward_params_label)
        
        # 转发参数复选框布局
        forward_params_layout = QHBoxLayout()
        
        self.remove_captions_check = QCheckBox("移除媒体说明")
        self.remove_captions_check.setChecked(False)
        forward_params_layout.addWidget(self.remove_captions_check)
        
        self.hide_author_check = QCheckBox("隐藏原作者")
        self.hide_author_check.setChecked(True)
        forward_params_layout.addWidget(self.hide_author_check)
        
        self.send_final_message_check = QCheckBox("转发完成发送最后一条消息")
        self.send_final_message_check.setChecked(True)
        forward_params_layout.addWidget(self.send_final_message_check)
        
        self.exclude_links_check = QCheckBox("排除含链接消息")
        self.exclude_links_check.setChecked(True)  # 默认勾选，方便用户使用
        forward_params_layout.addWidget(self.exclude_links_check)
        
        forward_params_layout.addStretch(1)  # 添加弹性空间，让复选框靠左对齐
        config_layout.addLayout(forward_params_layout)
        
        # 第九行：最终消息HTML文件路径
        html_file_form_layout = QFormLayout()
        html_file_form_layout.setSpacing(10)
        html_file_form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        html_file_form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        
        html_file_layout = QHBoxLayout()
        self.main_final_message_html_file = QLineEdit()
        self.main_final_message_html_file.setPlaceholderText("选择最终消息HTML文件")
        self.main_final_message_html_file.setEnabled(True)  # 初始状态启用（因为send_final_message_check默认选中）
        html_file_layout.addWidget(self.main_final_message_html_file)
        
        self.main_browse_html_button = QPushButton("浏览")
        self.main_browse_html_button.setMaximumWidth(60)
        self.main_browse_html_button.setEnabled(True)  # 初始状态启用（因为send_final_message_check默认选中）
        html_file_layout.addWidget(self.main_browse_html_button)
        
        html_file_form_layout.addRow("最终消息HTML文件:", html_file_layout)
        config_layout.addLayout(html_file_form_layout)
        
        # 第十行：起始ID，结束ID，添加频道对按钮，删除所选按钮
        id_and_buttons_layout = QHBoxLayout()
        
        # 起始ID和结束ID
        id_and_buttons_layout.addWidget(QLabel("起始ID:"))
        self.start_id = QSpinBox()
        self.start_id.setRange(0, 999999999)
        self.start_id.setValue(0)
        self.start_id.setSpecialValueText("最早消息")
        self.start_id.setFixedWidth(100)
        id_and_buttons_layout.addWidget(self.start_id)
        
        id_and_buttons_layout.addWidget(QLabel("结束ID:"))
        self.end_id = QSpinBox()
        self.end_id.setRange(0, 999999999)
        self.end_id.setValue(0)
        self.end_id.setSpecialValueText("最新消息")
        self.end_id.setFixedWidth(100)
        id_and_buttons_layout.addWidget(self.end_id)
        
        # 添加一些间距
        id_and_buttons_layout.addSpacing(20)
        
        # 添加频道对和删除按钮
        self.add_pair_button = QPushButton("添加频道对")
        self.add_pair_button.setMinimumHeight(28)
        id_and_buttons_layout.addWidget(self.add_pair_button)
        
        self.remove_pair_button = QPushButton("删除所选")
        self.remove_pair_button.setMinimumHeight(28)
        id_and_buttons_layout.addWidget(self.remove_pair_button)
        
        # 添加弹性空间，让控件靠左对齐
        id_and_buttons_layout.addStretch(1)
        
        config_layout.addLayout(id_and_buttons_layout)
        
        # 第十一行到底部：已配置频道对
        # 频道列表标题
        self.pairs_list_label = QLabel("已配置频道对:  0对")
        self.pairs_list_label.setStyleSheet("font-weight: bold;")
        config_layout.addWidget(self.pairs_list_label)
        
        # 创建频道对列表滚动区域
        pairs_scroll_area = QScrollArea()
        pairs_scroll_area.setWidgetResizable(True)
        pairs_scroll_area.setMinimumHeight(240)
        pairs_scroll_area.setMaximumHeight(300)
        pairs_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        pairs_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 创建频道对列表容器
        pairs_scroll_content = QWidget()
        pairs_scroll_layout = QVBoxLayout(pairs_scroll_content)
        pairs_scroll_layout.setContentsMargins(0, 0, 0, 0)
        pairs_scroll_layout.setSpacing(0)
        
        # 频道对列表
        self.pairs_list = QListWidget()
        self.pairs_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.pairs_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pairs_list.customContextMenuRequested.connect(self._show_context_menu)
        pairs_scroll_layout.addWidget(self.pairs_list)
        
        # 设置频道对列表滚动区域的内容
        pairs_scroll_area.setWidget(pairs_scroll_content)
        config_layout.addWidget(pairs_scroll_area, 1)  # 添加伸展系数
        
        # 设置主滚动区域的内容
        config_scroll_area.setWidget(scroll_content_widget)
        main_config_layout.addWidget(config_scroll_area)
        
        # 转发选项标签页
        self.options_tab = QWidget()
        options_layout = QVBoxLayout(self.options_tab)
        options_layout.setContentsMargins(5, 5, 5, 5)
        
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
        # 创建转发进度标签页
        self.progress_tab = QWidget()
        status_layout = QVBoxLayout(self.progress_tab)
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
        
        # 添加转发进度标签页到配置面板
        self.config_tabs.addTab(self.progress_tab, "转发进度")
    
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
        
        # 主界面HTML文件浏览
        self.main_browse_html_button.clicked.connect(self._browse_main_html_file)
        
        # 自定义文字尾巴设置状态控制
        self.send_final_message_check.toggled.connect(self._handle_final_message_option)
        
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
        
        # 获取文本替换规则
        original_texts = [t.strip() for t in self.original_text_input.text().split(',') if t.strip()]
        target_texts = [t.strip() for t in self.target_text_input.text().split(',') if t.strip()]
        
        # 构建文本替换规则
        text_filter = []
        max_len = max(len(original_texts), len(target_texts)) if original_texts or target_texts else 0
        for i in range(max_len):
            original = original_texts[i] if i < len(original_texts) else ""
            target = target_texts[i] if i < len(target_texts) else ""
            if original or target:  # 只添加非空的规则
                text_filter.append({"original_text": original, "target_text": target})
        
        # 如果没有文本替换规则，添加一个空的默认规则
        if not text_filter:
            text_filter = [{"original_text": "", "target_text": ""}]
        
        # 获取关键词
        keywords = [k.strip() for k in self.keyword_input.text().split(',') if k.strip()]
        
        try:
            # 使用UIChannelPair进行验证
            channel_pair = {
                'source_channel': UIChannelPair.validate_channel_id(source, "源频道"),
                'target_channels': [UIChannelPair.validate_channel_id(t, f"目标频道 {i+1}") 
                                   for i, t in enumerate(target_channels)],
                'media_types': media_types,
                'start_id': start_id,
                'end_id': end_id,
                'enabled': True,  # 新添加的频道对默认启用
                'remove_captions': self.remove_captions_check.isChecked(),
                'hide_author': self.hide_author_check.isChecked(),
                'send_final_message': self.send_final_message_check.isChecked(),
                'final_message_html_file': self.main_final_message_html_file.text().strip(),
                'text_filter': text_filter,
                'keywords': keywords,
                'exclude_links': self.exclude_links_check.isChecked()
            }
            
            # 添加到列表
            item = QListWidgetItem()
            
            # 创建媒体类型显示文本
            media_types_str = []
            if self._is_media_type_in_list(MediaType.TEXT, media_types):
                media_types_str.append("纯文本")
            if self._is_media_type_in_list(MediaType.PHOTO, media_types):
                media_types_str.append("照片")
            if self._is_media_type_in_list(MediaType.VIDEO, media_types):
                media_types_str.append("视频")
            if self._is_media_type_in_list(MediaType.DOCUMENT, media_types):
                media_types_str.append("文档")
            if self._is_media_type_in_list(MediaType.AUDIO, media_types):
                media_types_str.append("音频")
            if self._is_media_type_in_list(MediaType.ANIMATION, media_types):
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
            
            # 构建文本替换显示文本
            text_filter_str = ""
            if text_filter and any(rule.get("original_text") or rule.get("target_text") for rule in text_filter):
                replacements = []
                for rule in text_filter:
                    original = rule.get("original_text", "")
                    target = rule.get("target_text", "")
                    if original or target:
                        replacements.append(f"{original}->{target}")
                if replacements:
                    text_filter_str = f" - 替换: {', '.join(replacements)}"
            
            # 构建关键词显示文本
            keywords_str = ""
            if keywords:
                keywords_str = f" - 关键词: {', '.join(keywords)}"
            
            # 构建转发选项显示文本
            options_str = []
            if channel_pair['remove_captions']:
                options_str.append("移除说明")
            if channel_pair['hide_author']:
                options_str.append("隐藏作者")
            if channel_pair['send_final_message']:
                options_str.append("发送完成消息")
            if channel_pair['exclude_links']:
                options_str.append("排除链接")
            
            options_display = ""
            if options_str:
                options_display = f" - 选项: {', '.join(options_str)}"
            
            # 构建显示文本
            display_text = f"{channel_pair['source_channel']} → {', '.join(channel_pair['target_channels'])} (媒体：{', '.join(media_types_str)}){id_range_str}{text_filter_str}{keywords_str}{options_display}"
            
            item.setText(display_text)
            item.setData(Qt.UserRole, channel_pair)
            self.pairs_list.addItem(item)
            
            # 清空输入框
            self.source_input.clear()
            self.target_input.clear()
            self.original_text_input.clear()
            self.target_text_input.clear()
            self.keyword_input.clear()
            self.main_final_message_html_file.clear()
            
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
        """浏览临时目录"""
        directory = QFileDialog.getExistingDirectory(
            self, 
            "选择临时文件目录",
            self.tmp_path.text()
        )
        
        if directory:
            self.tmp_path.setText(directory)
    
    def _browse_main_html_file(self):
        """浏览主界面HTML文件"""
        current_path = os.path.dirname(self.main_final_message_html_file.text()) or QDir.homePath()
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "选择最终消息HTML文件",
            current_path,
            "HTML文件 (*.html);;所有文件 (*.*)"
        )
        
        if file_path:
            self.main_final_message_html_file.setText(file_path)
    
    def _handle_final_message_option(self, checked):
        """处理自定义文字尾巴选项的启用/禁用"""
        self.main_final_message_html_file.setEnabled(checked)
        self.main_browse_html_button.setEnabled(checked)
    
    def _is_media_type_in_list(self, media_type, media_types_list):
        """检查媒体类型是否在列表中
        
        Args:
            media_type: 要检查的媒体类型枚举
            media_types_list: 媒体类型列表（可能包含字符串或枚举）
            
        Returns:
            bool: 是否在列表中
        """
        if not media_types_list:
            return False
        
        # 获取媒体类型的字符串值
        target_value = media_type.value if isinstance(media_type, MediaType) else str(media_type)
        
        for mt in media_types_list:
            # 统一比较字符串值
            if isinstance(mt, MediaType):
                if mt.value == target_value:
                    return True
            elif isinstance(mt, str):
                if mt == target_value:
                    return True
            elif str(mt) == target_value:
                return True
        
        return False
    
    def _get_media_types(self):
        """获取选中的媒体类型
        
        Returns:
            list: 媒体类型列表
        """
        media_types = []
        
        if self.text_check.isChecked():
            media_types.append(MediaType.TEXT)
        
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
        """开始转发操作"""
        # 检查是否有转发器实例
        if not hasattr(self, 'forwarder') or self.forwarder is None:
            QMessageBox.warning(self, "错误", "转发器未初始化，无法启动转发")
            return

        # 添加状态消息
        self._add_status_message("开始转发...")
        
        # 自动切换到转发进度选项卡
        self.config_tabs.setCurrentIndex(2)  # 转发进度选项卡是第3个（索引为2）
        
        # 更新按钮状态
        self.start_forward_button.setEnabled(False)
        self.stop_forward_button.setEnabled(True)

        # 异步启动转发
        import asyncio
        try:
            # 创建启动转发的任务
            loop = asyncio.get_event_loop()
            loop.create_task(self._async_start_forward())
        except Exception as e:
            logger.error(f"启动转发时出错: {e}")
            self._add_status_message(f"启动转发失败: {e}")
            # 恢复按钮状态
            self.start_forward_button.setEnabled(True)
            self.stop_forward_button.setEnabled(False)
    
    async def _async_start_forward(self):
        """异步启动转发"""
        try:
            self._add_status_message("正在启动转发器...")
            await self.forwarder.forward_messages()
            self._add_status_message("转发完成")
        except Exception as e:
            logger.error(f"异步启动转发失败: {e}")
            self._add_status_message(f"启动转发失败: {e}")
            # 恢复按钮状态
            self.start_forward_button.setEnabled(True)
            self.stop_forward_button.setEnabled(False)

    def _add_status_message(self, message):
        """添加状态消息到界面显示
        
        Args:
            message: 要显示的状态消息
        """
        try:
            # 格式化消息，添加时间戳
            from datetime import datetime
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted_message = f"[{timestamp}] {message}"
            
            # 显示在总体状态标签中
            if hasattr(self, 'overall_status_label'):
                self.overall_status_label.setText(formatted_message)
            
            # 同时在控制台输出
            print(formatted_message)
            
        except Exception as e:
            print(f"添加状态消息失败: {e}")
            # 如果格式化失败，至少显示原始消息
            if hasattr(self, 'overall_status_label'):
                self.overall_status_label.setText(str(message))
    
    def _stop_forward(self):
        """停止转发"""
        # 检查是否有转发器实例
        if not hasattr(self, 'forwarder') or self.forwarder is None:
            self._add_status_message("转发器未初始化")
            return
        
        # 添加状态消息
        self._add_status_message("停止转发...")
        
        # 更新按钮状态
        self.start_forward_button.setEnabled(True)
        self.stop_forward_button.setEnabled(False)
        
        # 异步停止转发
        import asyncio
        try:
            # 创建停止转发的任务
            loop = asyncio.get_event_loop()
            loop.create_task(self._async_stop_forward())
        except Exception as e:
            logger.error(f"停止转发时出错: {e}")
            self._add_status_message(f"停止转发失败: {e}")
    
    async def _async_stop_forward(self):
        """异步停止转发"""
        try:
            # 如果转发器有停止方法，调用它
            if hasattr(self.forwarder, 'stop_forward'):
                await self.forwarder.stop_forward()
            self._add_status_message("转发已停止")
        except Exception as e:
            logger.error(f"异步停止转发失败: {e}")
            self._add_status_message(f"停止转发失败: {e}")

    def _on_forward_complete_ui_update(self):
        """转发完成后的UI更新"""
        # 更新状态
        self.overall_status_label.setText("转发已完成")
        
        # 更新进度条
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("所有转发已完成")
        
        # 恢复按钮状态
        self.start_forward_button.setEnabled(True)
        self.stop_forward_button.setEnabled(False)
        
        # 清理任务引用，避免内存泄漏
        if hasattr(self, 'forward_task') and self.forward_task is not None:
            # 移除回调以避免循环引用
            try:
                if hasattr(self.forward_task, '_callbacks') and self.forward_task._callbacks:
                    self.forward_task.remove_done_callback(
                        next((cb for cb in self.forward_task._callbacks), lambda _: None)
                    )
            except Exception as e:
                logger.debug(f"移除任务回调时出错: {e}")
            
            self.forward_task = None
        
        # 记录完成事件
        logger.info("所有消息转发完成")
        
        # 延迟显示完成消息，避免UI阻塞
        QTimer.singleShot(100, lambda: self._show_completion_dialog("转发完成", "所有转发任务已完成"))
    
    def _show_completion_dialog(self, title, message):
        """安全地显示完成对话框"""
        try:
            QMessageBox.information(self, title, message)
        except Exception as e:
            logger.error(f"显示完成对话框时出错: {e}")
            # 备用方案：使用状态标签显示完成信息
            self.overall_status_label.setText(f"{message} ({title})")
    
    def _on_forward_error_ui_update(self, error_message):
        """转发出错后的UI更新"""
        # 更新状态
        self.overall_status_label.setText(f"转发出错: {error_message}")
        
        # 更新进度条状态
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("转发失败")
        
        # 恢复按钮状态
        self.start_forward_button.setEnabled(True)
        self.stop_forward_button.setEnabled(False)
        
        # 清理任务引用，避免内存泄漏
        if hasattr(self, 'forward_task') and self.forward_task is not None:
            # 尝试移除回调以避免循环引用
            try:
                if hasattr(self.forward_task, '_callbacks') and self.forward_task._callbacks:
                    self.forward_task.remove_done_callback(
                        next((cb for cb in self.forward_task._callbacks), lambda _: None)
                    )
            except Exception as e:
                logger.debug(f"移除任务回调时出错: {e}")
            
            self.forward_task = None
        
        # 记录错误事件
        logger.error(f"转发错误: {error_message}")
        
        # 使用延迟显示错误对话框
        QTimer.singleShot(100, lambda: self._show_error_dialog_safe("转发错误", f"转发过程中发生错误:\n{error_message}"))
    
    def _show_error_dialog_safe(self, title, message):
        """安全地显示错误对话框"""
        try:
            self._show_error_dialog(title, message)
        except Exception as e:
            logger.error(f"显示错误对话框时出错: {e}")
            # 确保错误信息至少会显示在状态标签中
            self.overall_status_label.setText(f"错误: {message}")
    
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
                    end_id=self.end_id.value(),
                    remove_captions=self.remove_captions_check.isChecked(),
                    hide_author=self.hide_author_check.isChecked(),
                    send_final_message=self.send_final_message_check.isChecked(),
                    final_message_html_file=self.main_final_message_html_file.text().strip(),
                    # 添加text_filter和keywords字段
                    text_filter=[{"original_text": "", "target_text": ""}],
                    keywords=[],
                    exclude_links=self.exclude_links_check.isChecked()
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
                        end_id=pair.get('end_id', 0),
                        enabled=pair.get('enabled', True),  # 确保enabled字段被保存
                        remove_captions=pair.get('remove_captions', False),
                        hide_author=pair.get('hide_author', False),
                        send_final_message=pair.get('send_final_message', False),
                        final_message_html_file=pair.get('final_message_html_file', ''),
                        # 添加text_filter和keywords字段
                        text_filter=pair.get('text_filter', [{"original_text": "", "target_text": ""}]),
                        keywords=pair.get('keywords', []),
                        exclude_links=pair.get('exclude_links', False)
                    ))
            
            # 创建UIForwardConfig对象（移除final_message_html_file参数）
            forward_config = UIForwardConfig(
                forward_channel_pairs=ui_channel_pairs,
                forward_delay=round(float(self.forward_delay.value()), 1),  # 四舍五入到一位小数，解决精度问题
                tmp_path=self.tmp_path.text()
            )
            
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
            
            # 使用模型的dict()方法将对象转换为字典
            updated_config['FORWARD'] = forward_config.dict()
            
            # 发送配置保存信号
            logger.debug(f"向主窗口发送配置保存信号，更新转发配置")
            self.config_saved.emit(updated_config)
            
            # 显示成功消息
            QMessageBox.information(self, "配置保存", "转发配置已保存")
            
            # 更新本地配置引用
            self.config = updated_config
            
            logger.debug("配置保存完成，保持当前UI状态不变")
            
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
        # 使用QTimer安全地在主线程中调用UI更新方法
        QTimer.singleShot(0, self._on_forward_complete_ui_update)
    
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
        
        # 初始化变量用于保存第一个频道对的ID设置和转发参数
        first_pair_start_id = 0
        first_pair_end_id = 0
        first_pair_exclude_links = True  # 默认值为True
        
        # 添加频道对到列表
        for i, pair in enumerate(channel_pairs):
            source_channel = pair.get('source_channel')
            target_channels = pair.get('target_channels', [])
            media_types = pair.get('media_types', [MediaType.TEXT, MediaType.PHOTO, MediaType.VIDEO, MediaType.DOCUMENT, MediaType.AUDIO, MediaType.ANIMATION])
            
            # 确保优先从频道对中获取消息ID范围
            start_id = pair.get('start_id', 0)
            end_id = pair.get('end_id', 0)
            
            # 获取转发选项参数
            remove_captions = pair.get('remove_captions', False)
            hide_author = pair.get('hide_author', False)
            send_final_message = pair.get('send_final_message', False)
            exclude_links = pair.get('exclude_links', False)
            
            # 获取新增字段
            text_filter = pair.get('text_filter', [])
            keywords = pair.get('keywords', [])
            final_message_html_file = pair.get('final_message_html_file', '')
            
            if source_channel and target_channels:
                # 保存第一个频道对的ID设置和exclude_links状态，用于设置默认值
                if i == 0:
                    first_pair_start_id = start_id
                    first_pair_end_id = end_id
                    first_pair_exclude_links = exclude_links
                
                # 创建频道对数据
                channel_pair = {
                    'source_channel': source_channel,
                    'target_channels': target_channels,
                    'media_types': media_types,
                    'start_id': start_id,
                    'end_id': end_id,
                    'enabled': pair.get('enabled', True),  # 默认启用，兼容旧配置
                    'remove_captions': remove_captions,
                    'hide_author': hide_author,
                    'send_final_message': send_final_message,
                    'final_message_html_file': final_message_html_file,
                    'text_filter': text_filter,
                    'keywords': keywords,
                    'exclude_links': exclude_links
                }
                
                # 添加到列表
                self.channel_pairs.append(channel_pair)
                
                # 创建列表项
                item = QListWidgetItem()
                item.setData(Qt.UserRole, channel_pair)
                
                # 使用统一的显示更新方法
                self._update_channel_pair_display(item, channel_pair)
                
                self.pairs_list.addItem(item)
        
        # 更新频道对列表标题
        self._update_pairs_list_title()
        
        # 加载消息ID设置（使用第一个频道对的ID设置）
        self.start_id.setValue(first_pair_start_id)
        self.end_id.setValue(first_pair_end_id)
        
        # 主界面的文本替换和关键词输入框保持默认为空，不从配置文件加载
        # 只有右键编辑菜单中才会从配置加载这些字段的值
        
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
                # 连接到新的UI更新方法
                self.forwarder.all_forwards_completed.connect(self._on_forward_complete_ui_update)
            
            if hasattr(self.forwarder, 'error_occurred'):
                self.forwarder.error_occurred.connect(self._on_forward_error)
            
            logger.debug("转发器信号连接成功")
            
            # 如果转发器没有这些信号属性，我们需要手动添加事件监听
            # 这是为了兼容不同版本的转发器实现
            if not hasattr(self.forwarder, 'status_updated') and hasattr(self.forwarder, 'add_event_listener'):
                self.forwarder.add_event_listener("status", self._update_status)
                self.forwarder.add_event_listener("progress", self._update_progress)
                self.forwarder.add_event_listener("forward_complete", self._on_forward_complete)
                # 添加all_forwards_complete事件监听
                self.forwarder.add_event_listener("all_forwards_complete", self._on_forward_complete_ui_update)
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
    
    def _get_forward_config(self):
        """收集转发配置信息（已弃用）
        
        此方法已被弃用，转发配置现在直接从配置文件实时读取
        
        Returns:
            None: 此方法不再返回配置，仅保留以防止兼容性问题
        """
        # 此方法已被弃用，转发配置现在在forwarder中实时从配置文件读取
        logger.warning("_get_forward_config方法已被弃用，配置现在从配置文件实时读取")
        return None

    def _show_context_menu(self, pos):
        """显示右键菜单
        
        Args:
            pos: 鼠标位置
        """
        # 确保有选中的项目
        current_item = self.pairs_list.itemAt(pos)
        if not current_item:
            return
        
        # 获取频道对数据，检查启用状态
        channel_pair = current_item.data(Qt.UserRole)
        is_enabled = channel_pair.get('enabled', True) if channel_pair else True
        
        # 创建菜单
        context_menu = QMenu(self)
        
        # 添加禁用/启用菜单项
        if is_enabled:
            toggle_action = context_menu.addAction("禁用")
            toggle_action.setToolTip("禁用此频道对，转发时将跳过")
        else:
            toggle_action = context_menu.addAction("启用")
            toggle_action.setToolTip("启用此频道对，转发时将包含")
        
        context_menu.addSeparator()  # 添加分隔线
        
        # 添加其他菜单项
        edit_action = context_menu.addAction("编辑")
        delete_action = context_menu.addAction("删除")
        
        # 显示菜单并获取用户选择的操作
        action = context_menu.exec(QCursor.pos())
        
        # 处理用户选择
        if action == toggle_action:
            self._toggle_channel_pair_enabled(current_item)
        elif action == edit_action:
            self._edit_channel_pair(current_item)
        elif action == delete_action:
            # 删除操作直接调用已有的删除方法
            self._remove_channel_pairs()
    
    def _edit_channel_pair(self, item):
        """编辑频道对
        
        Args:
            item: 要编辑的列表项
        """
        # 获取项目索引
        row = self.pairs_list.row(item)
        
        # 获取频道对数据
        channel_pair = item.data(Qt.UserRole)
        if not channel_pair:
            return
        
        # 创建编辑对话框
        edit_dialog = QDialog(self)
        edit_dialog.setWindowTitle("编辑频道对")
        edit_dialog.setMinimumWidth(650)  # 增加宽度以容纳更多字段
        edit_dialog.setMinimumHeight(650)  # 增加高度以容纳更多字段
        
        # 创建主布局，只包含滚动区域
        main_dialog_layout = QVBoxLayout(edit_dialog)
        main_dialog_layout.setContentsMargins(0, 0, 0, 0)
        main_dialog_layout.setSpacing(0)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        
        # 创建滚动内容容器
        scroll_content_widget = QWidget()
        dialog_layout = QVBoxLayout(scroll_content_widget)
        dialog_layout.setContentsMargins(15, 15, 15, 15)
        dialog_layout.setSpacing(15)
        
        # 第一行：源频道
        source_form_layout = QFormLayout()
        source_form_layout.setSpacing(10)
        source_form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        source_form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        
        source_input = QLineEdit(channel_pair.get('source_channel', ''))
        source_input.setPlaceholderText("频道链接或ID (例如: https://t.me/example 或 -1001234567890)")
        source_form_layout.addRow("源频道:", source_input)
        dialog_layout.addLayout(source_form_layout)
        
        # 第二行：目标频道
        target_form_layout = QFormLayout()
        target_form_layout.setSpacing(10)
        target_form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        target_form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        
        target_input = QLineEdit(', '.join(channel_pair.get('target_channels', [])))
        target_input.setPlaceholderText("目标频道，多个用英文逗号分隔 (例如: @channel1, @channel2)")
        target_form_layout.addRow("目标频道:", target_input)
        dialog_layout.addLayout(target_form_layout)
        
        # 第三行：文本替换
        text_replace_form_layout = QFormLayout()
        text_replace_form_layout.setSpacing(10)
        text_replace_form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        text_replace_form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        
        # 解析文本替换规则
        text_filter = channel_pair.get('text_filter', [])
        original_texts = []
        target_texts = []
        
        for rule in text_filter:
            if isinstance(rule, dict):
                original_text = rule.get('original_text', '')
                target_text = rule.get('target_text', '')
                if original_text or target_text:
                    original_texts.append(original_text)
                    target_texts.append(target_text)
        
        original_text_input = QLineEdit(', '.join(original_texts))
        original_text_input.setPlaceholderText("要替换的原始文本，多个用英文逗号分隔")
        text_replace_form_layout.addRow("文本替换:", original_text_input)
        dialog_layout.addLayout(text_replace_form_layout)
        
        # 第四行：替换为
        replace_to_form_layout = QFormLayout()
        replace_to_form_layout.setSpacing(10)
        replace_to_form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        replace_to_form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        
        target_text_input = QLineEdit(', '.join(target_texts))
        target_text_input.setPlaceholderText("替换后的目标文本，多个用英文逗号分隔如：C,D")
        replace_to_form_layout.addRow("替换为:", target_text_input)
        dialog_layout.addLayout(replace_to_form_layout)
        
        # 第五行：过滤选项label
        filter_options_label = QLabel("过滤选项:")
        filter_options_label.setStyleSheet("font-weight: bold;")
        dialog_layout.addWidget(filter_options_label)
        
        # 第六行：关键词过滤
        keyword_form_layout = QFormLayout()
        keyword_form_layout.setSpacing(10)
        keyword_form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        keyword_form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        
        keywords = channel_pair.get('keywords', [])
        keyword_input = QLineEdit(', '.join(keywords))
        keyword_input.setPlaceholderText("关键词，多个用英文逗号分隔，只转发含关键词的消息")
        keyword_form_layout.addRow("关键词过滤:", keyword_input)
        dialog_layout.addLayout(keyword_form_layout)
        
        # 第七行：媒体类型
        media_types = channel_pair.get('media_types', [])
        
        # 媒体类型复选框布局（移除标签）
        media_types_layout = QHBoxLayout()
        
        text_check = QCheckBox("纯文本")
        text_check.setChecked(self._is_media_type_in_list(MediaType.TEXT, media_types))
        media_types_layout.addWidget(text_check)
        
        photo_check = QCheckBox("照片")
        photo_check.setChecked(self._is_media_type_in_list(MediaType.PHOTO, media_types))
        media_types_layout.addWidget(photo_check)
        
        video_check = QCheckBox("视频")
        video_check.setChecked(self._is_media_type_in_list(MediaType.VIDEO, media_types))
        media_types_layout.addWidget(video_check)
        
        document_check = QCheckBox("文档")
        document_check.setChecked(self._is_media_type_in_list(MediaType.DOCUMENT, media_types))
        media_types_layout.addWidget(document_check)
        
        audio_check = QCheckBox("音频")
        audio_check.setChecked(self._is_media_type_in_list(MediaType.AUDIO, media_types))
        media_types_layout.addWidget(audio_check)
        
        animation_check = QCheckBox("动画")
        animation_check.setChecked(self._is_media_type_in_list(MediaType.ANIMATION, media_types))
        media_types_layout.addWidget(animation_check)
        
        media_types_layout.addStretch(1)  # 添加弹性空间，让复选框靠左对齐
        dialog_layout.addLayout(media_types_layout)
        
        # 第八行：转发参数
        forward_params_label = QLabel("转发参数:")
        forward_params_label.setStyleSheet("font-weight: bold;")
        dialog_layout.addWidget(forward_params_label)
        
        # 转发参数复选框布局
        forward_params_layout = QHBoxLayout()
        
        # 确保布尔值转换（处理JSON中的true/false或其他类型）
        def to_bool(value):
            if isinstance(value, bool):
                return value
            elif isinstance(value, str):
                return value.lower() in ('true', '1', 'yes', 'on')
            elif isinstance(value, (int, float)):
                return bool(value)
            else:
                return bool(value)
        
        remove_captions_value = to_bool(channel_pair.get('remove_captions', False))
        hide_author_value = to_bool(channel_pair.get('hide_author', False))
        send_final_message_value = to_bool(channel_pair.get('send_final_message', False))
        exclude_links_value = to_bool(channel_pair.get('exclude_links', False))
        
        remove_captions_check = QCheckBox("移除媒体说明")
        remove_captions_check.setChecked(remove_captions_value)
        forward_params_layout.addWidget(remove_captions_check)
        
        hide_author_check = QCheckBox("隐藏原作者")
        hide_author_check.setChecked(hide_author_value)
        forward_params_layout.addWidget(hide_author_check)
        
        send_final_message_check = QCheckBox("转发完成发送最后一条消息")
        send_final_message_check.setChecked(send_final_message_value)
        forward_params_layout.addWidget(send_final_message_check)
        
        exclude_links_check = QCheckBox("排除含链接消息")
        exclude_links_check.setChecked(exclude_links_value)
        forward_params_layout.addWidget(exclude_links_check)
        
        forward_params_layout.addStretch(1)  # 添加弹性空间，让复选框靠左对齐
        dialog_layout.addLayout(forward_params_layout)
        
        # 第九行：最终消息HTML文件路径
        html_file_form_layout = QFormLayout()
        html_file_form_layout.setSpacing(10)
        html_file_form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        html_file_form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        
        html_file_layout = QHBoxLayout()
        html_file_input = QLineEdit(channel_pair.get('final_message_html_file', ''))
        html_file_input.setPlaceholderText("选择最终消息HTML文件")
        html_file_layout.addWidget(html_file_input)
        
        html_file_browse_btn = QPushButton("浏览")
        html_file_browse_btn.setMaximumWidth(60)
        html_file_layout.addWidget(html_file_browse_btn)
        
        html_file_form_layout.addRow("最终消息HTML文件:", html_file_layout)
        dialog_layout.addLayout(html_file_form_layout)
        
        # 连接浏览按钮
        def browse_html_file():
            file_path, _ = QFileDialog.getOpenFileName(
                edit_dialog,
                "选择最终消息HTML文件",
                "",
                "HTML文件 (*.html);;所有文件 (*)"
            )
            if file_path:
                html_file_input.setText(file_path)
        
        html_file_browse_btn.clicked.connect(browse_html_file)
        
        # 第九行：起始ID，结束ID
        id_and_buttons_layout = QHBoxLayout()
        
        # 起始ID和结束ID
        id_and_buttons_layout.addWidget(QLabel("起始ID:"))
        start_id_input = QSpinBox()
        start_id_input.setRange(0, 999999999)
        start_id_input.setValue(channel_pair.get('start_id', 0))
        start_id_input.setSpecialValueText("最早消息")
        
        # 结束ID
        end_id_input = QSpinBox()
        end_id_input.setRange(0, 999999999)
        end_id_input.setValue(channel_pair.get('end_id', 0))
        end_id_input.setSpecialValueText("最新消息")
        
        id_and_buttons_layout.addWidget(start_id_input)
        id_and_buttons_layout.addWidget(QLabel("结束ID:"))
        id_and_buttons_layout.addWidget(end_id_input)
        id_and_buttons_layout.addStretch(1)
        
        dialog_layout.addLayout(id_and_buttons_layout)
        
        # 设置滚动区域的内容
        scroll_area.setWidget(scroll_content_widget)
        main_dialog_layout.addWidget(scroll_area)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        save_button = QPushButton("保存")
        cancel_button = QPushButton("取消")
        
        button_layout.addStretch(1)
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        
        main_dialog_layout.addLayout(button_layout)
        
        # 连接按钮信号
        save_button.clicked.connect(edit_dialog.accept)
        cancel_button.clicked.connect(edit_dialog.reject)
        
        # 显示对话框并处理结果
        if edit_dialog.exec() == QDialog.Accepted:
            try:
                # 收集编辑后的数据
                new_source = source_input.text().strip()
                new_target_text = target_input.text().strip()
                new_targets = [t.strip() for t in new_target_text.split(',') if t.strip()]
                
                # 验证输入
                if not new_source:
                    raise ValueError("源频道不能为空")
                if not new_targets:
                    raise ValueError("目标频道不能为空")
                
                # 收集媒体类型
                new_media_types = []
                if text_check.isChecked():
                    new_media_types.append(MediaType.TEXT)
                if photo_check.isChecked():
                    new_media_types.append(MediaType.PHOTO)
                if video_check.isChecked():
                    new_media_types.append(MediaType.VIDEO)
                if document_check.isChecked():
                    new_media_types.append(MediaType.DOCUMENT)
                if audio_check.isChecked():
                    new_media_types.append(MediaType.AUDIO)
                if animation_check.isChecked():
                    new_media_types.append(MediaType.ANIMATION)
                
                if not new_media_types:
                    raise ValueError("至少需要选择一种媒体类型")
                
                # 获取文本替换规则
                original_texts = [t.strip() for t in original_text_input.text().split(',') if t.strip()]
                target_texts = [t.strip() for t in target_text_input.text().split(',') if t.strip()]
                
                # 构建文本替换规则
                text_filter = []
                max_len = max(len(original_texts), len(target_texts)) if original_texts or target_texts else 0
                for i in range(max_len):
                    original = original_texts[i] if i < len(original_texts) else ""
                    target = target_texts[i] if i < len(target_texts) else ""
                    if original or target:  # 只添加非空的规则
                        text_filter.append({"original_text": original, "target_text": target})
                
                # 如果没有文本替换规则，添加一个空的默认规则
                if not text_filter:
                    text_filter = [{"original_text": "", "target_text": ""}]
                
                # 获取关键词
                keywords = [k.strip() for k in keyword_input.text().split(',') if k.strip()]
                
                # 使用UIChannelPair进行验证
                validated_source = UIChannelPair.validate_channel_id(new_source, "源频道")
                validated_targets = [UIChannelPair.validate_channel_id(t, f"目标频道 {i+1}") 
                                    for i, t in enumerate(new_targets)]
                
                # 创建更新后的频道对
                updated_pair = {
                    'source_channel': validated_source,
                    'target_channels': validated_targets,
                    'media_types': new_media_types,
                    'start_id': start_id_input.value(),
                    'end_id': end_id_input.value(),
                    'enabled': channel_pair.get('enabled', True),  # 保留原来的启用状态
                    'remove_captions': remove_captions_check.isChecked(),
                    'hide_author': hide_author_check.isChecked(),
                    'send_final_message': send_final_message_check.isChecked(),
                    'final_message_html_file': html_file_input.text().strip(),
                    'text_filter': text_filter,
                    'keywords': keywords,
                    'exclude_links': exclude_links_check.isChecked()
                }
                
                # 更新列表项和数据
                self._update_channel_pair(row, updated_pair)
                
            except ValueError as e:
                QMessageBox.warning(self, "输入错误", str(e))
    
    def _update_channel_pair(self, row, updated_pair):
        """更新频道对
        
        Args:
            row: 行索引
            updated_pair: 更新后的频道对数据
        """
        # 更新channel_pairs列表
        if 0 <= row < len(self.channel_pairs):
            self.channel_pairs[row] = updated_pair
            
            # 更新列表项显示
            item = self.pairs_list.item(row)
            if item:
                # 更新列表项数据
                item.setData(Qt.UserRole, updated_pair)
                
                # 使用统一的显示更新方法
                self._update_channel_pair_display(item, updated_pair)
                
                # 记录日志
                logger.debug(f"频道对已更新: {updated_pair['source_channel']}")
                
                # 显示成功消息
                QMessageBox.information(self, "更新成功", "频道对已成功更新，请点击保存配置")
        else:
            logger.error(f"无法更新频道对，行索引无效: {row}")
    
    def _toggle_channel_pair_enabled(self, item):
        """切换频道对的启用/禁用状态
        
        Args:
            item: 要切换状态的列表项
        """
        # 获取项目索引
        row = self.pairs_list.row(item)
        
        # 获取频道对数据
        channel_pair = item.data(Qt.UserRole)
        if not channel_pair:
            return
        
        # 切换启用状态
        current_enabled = channel_pair.get('enabled', True)
        new_enabled = not current_enabled
        channel_pair['enabled'] = new_enabled
        
        # 更新 channel_pairs 列表中的数据
        if 0 <= row < len(self.channel_pairs):
            self.channel_pairs[row]['enabled'] = new_enabled
        
        # 更新列表项数据
        item.setData(Qt.UserRole, channel_pair)
        
        # 更新显示文本，添加禁用状态标识
        self._update_channel_pair_display(item, channel_pair)
        
        # 显示状态切换消息
        status_text = "启用" if new_enabled else "禁用"
        source_channel = channel_pair.get('source_channel', '未知频道')
        QMessageBox.information(self, "状态更新", f"频道对 {source_channel} 已{status_text}，请保存配置使更改生效")
        
        logger.debug(f"频道对 {source_channel} 状态切换为: {'启用' if new_enabled else '禁用'}")
    
    def _update_channel_pair_display(self, item, channel_pair):
        """更新频道对的显示文本
        
        Args:
            item: 列表项
            channel_pair: 频道对数据
        """
        # 创建媒体类型显示文本
        media_types = channel_pair.get('media_types', [])
        media_types_str = []
        
        if self._is_media_type_in_list(MediaType.TEXT, media_types):
            media_types_str.append("纯文本")
        if self._is_media_type_in_list(MediaType.PHOTO, media_types):
            media_types_str.append("照片")
        if self._is_media_type_in_list(MediaType.VIDEO, media_types):
            media_types_str.append("视频")
        if self._is_media_type_in_list(MediaType.DOCUMENT, media_types):
            media_types_str.append("文档")
        if self._is_media_type_in_list(MediaType.AUDIO, media_types):
            media_types_str.append("音频")
        if self._is_media_type_in_list(MediaType.ANIMATION, media_types):
            media_types_str.append("动画")
        
        # 构建ID范围显示文本
        start_id = channel_pair.get('start_id', 0)
        end_id = channel_pair.get('end_id', 0)
        id_range_str = ""
        
        if start_id > 0 or end_id > 0:
            if start_id > 0 and end_id > 0:
                id_range_str = f"ID范围: {start_id}-{end_id}"
            elif start_id > 0:
                id_range_str = f"ID范围: {start_id}+"
            else:
                id_range_str = f"ID范围: 最早-{end_id}"
            id_range_str = " - " + id_range_str
        
        # 构建文本替换显示文本
        text_filter = channel_pair.get('text_filter', [])
        text_filter_str = ""
        if text_filter and any(rule.get("original_text") or rule.get("target_text") for rule in text_filter):
            replacements = []
            for rule in text_filter:
                original = rule.get("original_text", "")
                target = rule.get("target_text", "")
                if original or target:
                    replacements.append(f"{original}->{target}")
            if replacements:
                text_filter_str = f" - 替换: {', '.join(replacements)}"
        
        # 构建关键词显示文本
        keywords = channel_pair.get('keywords', [])
        keywords_str = ""
        if keywords:
            keywords_str = f" - 关键词: {', '.join(keywords)}"
        
        # 构建转发选项显示文本
        options_str = []
        if channel_pair.get('remove_captions', False):
            options_str.append("移除说明")
        if channel_pair.get('hide_author', False):
            options_str.append("隐藏作者")
        if channel_pair.get('send_final_message', False):
            options_str.append("发送完成消息")
        if channel_pair.get('exclude_links', False):
            options_str.append("排除链接")
        
        options_display = ""
        if options_str:
            options_display = f" - 选项: {', '.join(options_str)}"
        
        # 构建基础显示文本
        display_text = f"{channel_pair['source_channel']} → {', '.join(channel_pair['target_channels'])} (媒体：{', '.join(media_types_str)}){id_range_str}{text_filter_str}{keywords_str}{options_display}"
        
        # 添加启用/禁用状态标识
        is_enabled = channel_pair.get('enabled', True)
        if not is_enabled:
            display_text = f"[已禁用] {display_text}"
        
        # 更新列表项文本
        item.setText(display_text)