"""
TG-Manager 下载界面
实现媒体文件的下载功能
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QCheckBox, QComboBox, QPushButton,
    QGroupBox, QScrollArea, QSpinBox, QGridLayout,
    QListWidget, QListWidgetItem, QFileDialog, QMessageBox,
    QSizePolicy, QTabWidget, QSplitter, QProgressBar,
    QDialog, QMenu
)
from PySide6.QtCore import Qt, Signal, Slot, QSize, QTimer
from PySide6.QtGui import QColor, QCursor

from src.utils.logger import get_logger
from src.utils.ui_config_models import MediaType
from src.utils.translation_manager import tr

import os
import time
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any, Union
import re

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
        
        # 注释掉直接的翻译信号连接，依赖主窗口的翻译更新机制
        # # 获取翻译管理器并连接语言变更信号
        # from src.utils.translation_manager import get_translation_manager
        # self.translation_manager = get_translation_manager()
        # self.translation_manager.language_changed.connect(self._update_translations)
        # logger.debug("下载视图已连接语言变更信号")
        
        # 初始化下载计数器
        self.completed_downloads = 0
        self.total_downloads = 0
        
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
        #         margin-top: 0.5em; 
        #         border: 1px solid #444;
        #         border-radius: 3px;
        #     }
        #     QGroupBox::title {
        #         subcontrol-origin: margin;
        #         subcontrol-position: top left;
        #         left: 7px;
        #         padding: 0 3px;
        #         background-color: palette(window);
        #     }
        #     QTabWidget::pane {
        #         border: 1px solid #444;
        #         padding: 1px;
        #     }
        #     QTabBar::tab {
        #         padding: 3px 8px;
        #     }
        # """)
        
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
            
        # 启动时检查下载目录大小
        QTimer.singleShot(1000, self._check_directory_size_limit_on_startup)
        
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
        self.channel_input.setPlaceholderText(tr("ui.download.source_channel_placeholder"))
        self.channel_label = QLabel(tr("ui.download.source_channel"))
        form_layout.addRow(self.channel_label, self.channel_input)
        
        # 先添加表单布局到主布局
        channel_layout.addLayout(form_layout)
        
        # 消息范围 - 创建左对齐的布局
        range_layout = QHBoxLayout()
        range_layout.setContentsMargins(0, 0, 0, 2)  # 减小上下间距
        
        # 从消息ID标签
        self.id_label = QLabel(tr("ui.download.message_range.start_id"))
        self.id_label.setMinimumWidth(80)  # 设置最小宽度确保对齐
        range_layout.addWidget(self.id_label)
        
        self.start_id = QSpinBox()
        self.start_id.setRange(1, 999999999)
        self.start_id.setValue(1)
        self.start_id.setMinimumWidth(90)  # 减小宽度
        range_layout.addWidget(self.start_id)
        
        self.to_label = QLabel(tr("ui.download.message_range.to"))
        range_layout.addWidget(self.to_label)
        
        self.end_id = QSpinBox()
        self.end_id.setRange(0, 999999999)
        self.end_id.setValue(0)
        self.end_id.setSpecialValueText(tr("ui.download.message_range.latest_message"))
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
        self.keyword_label = QLabel(tr("ui.download.keyword_filter"))
        self.keyword_label.setMinimumWidth(70)  # 设置最小宽度确保对齐
        keywords_layout.addWidget(self.keyword_label)
        
        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText(tr("ui.download.keyword_placeholder"))
        self.keyword_input.setMinimumWidth(300)  # 增加最小宽度
        # 设置尺寸策略为水平方向可扩展
        self.keyword_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        keywords_layout.addWidget(self.keyword_input, 3)  # 设置拉伸因子为3，使其占据更多空间
        
        # 添加频道和删除按钮
        self.add_channel_button = QPushButton(tr("ui.download.add_pair"))
        self.add_channel_button.setMinimumHeight(28)  # 设置按钮高度
        keywords_layout.addWidget(self.add_channel_button, 0)  # 不设置拉伸
        
        self.remove_channel_button = QPushButton(tr("ui.download.remove_pair"))
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
        
        self.media_type_label = QLabel(tr("ui.download.file_types"))
        self.media_type_label.setMinimumWidth(110)
        media_layout.addWidget(self.media_type_label)
        
        self.photo_check = QCheckBox(tr("ui.forward.media_types.photo"))
        self.photo_check.setChecked(True)
        media_layout.addWidget(self.photo_check)
        
        self.video_check = QCheckBox(tr("ui.forward.media_types.video"))
        self.video_check.setChecked(True)
        media_layout.addWidget(self.video_check)
        
        self.document_check = QCheckBox(tr("ui.forward.media_types.document"))
        self.document_check.setChecked(True)
        media_layout.addWidget(self.document_check)
        
        self.audio_check = QCheckBox(tr("ui.forward.media_types.audio"))
        self.audio_check.setChecked(True)
        media_layout.addWidget(self.audio_check)
        
        self.animation_check = QCheckBox(tr("ui.forward.media_types.animation"))
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
        self.channel_list_label = QLabel(tr("ui.download.configured_pairs", count=0))
        # self.channel_list_label.setStyleSheet("font-weight: bold;")  # 加粗标签
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
        
        # 频道列表
        self.channel_list = QListWidget()
        self.channel_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.channel_list.setContextMenuPolicy(Qt.CustomContextMenu)  # 设置自定义右键菜单
        self.channel_list.customContextMenuRequested.connect(self._show_context_menu)  # 连接右键菜单事件
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
        
        self.parallel_check = QCheckBox(tr("ui.download.parallel_download"))
        self.parallel_check.toggled.connect(lambda checked: self.max_downloads.setEnabled(checked))
        
        self.max_downloads = QSpinBox()
        self.max_downloads.setRange(1, 20)
        self.max_downloads.setValue(5)
        self.max_downloads.setEnabled(False)
        self.max_downloads.setSuffix("")
        self.max_concurrent_label = QLabel(tr("ui.download.max_concurrent"))
        parallel_layout.addWidget(self.parallel_check)
        parallel_layout.addWidget(self.max_concurrent_label)
        parallel_layout.addWidget(self.max_downloads)
        # 添加空白区域
        parallel_layout.addSpacing(20)
        # restart_note放在末尾
        self.restart_note = QLabel(tr("ui.download.restart_note"))
        self.restart_note.setObjectName("restart_note")
        self.restart_note.setStyleSheet("font-size: 12px;")
        parallel_layout.addWidget(self.restart_note)
        parallel_layout.addStretch(1)
        options_layout.addLayout(parallel_layout)
        
        # 添加一些空间
        options_layout.addSpacing(8)
        
        # 下载目录大小限制
        dir_size_limit_layout = QHBoxLayout()
        self.dir_size_limit_check = QCheckBox(tr("ui.download.dir_size_limit_check"))
        self.dir_size_limit_check.toggled.connect(lambda checked: self.dir_size_limit.setEnabled(checked))
        dir_size_limit_layout.addWidget(self.dir_size_limit_check)
        
        self.dir_size_limit = QSpinBox()
        self.dir_size_limit.setRange(1, 100000)  # 1MB到100GB
        self.dir_size_limit.setValue(1000)  # 默认1000MB (1GB)
        self.dir_size_limit.setEnabled(False)
        self.dir_size_limit.setSuffix(" MB")
        dir_size_limit_layout.addWidget(self.dir_size_limit)
        
        # 添加检查目录大小按钮
        self.check_dir_size_button = QPushButton(tr("ui.download.check_dir_size"))
        self.check_dir_size_button.clicked.connect(self._check_and_show_directory_size)
        dir_size_limit_layout.addWidget(self.check_dir_size_button)
        
        dir_size_limit_layout.addStretch(1)
        options_layout.addLayout(dir_size_limit_layout)
        
        # 添加一些空间
        options_layout.addSpacing(8)
        
        # 下载路径 - 移到标签卡的下部
        path_layout = QHBoxLayout()
        self.download_path_label = QLabel(tr("ui.download.download_path"))
        path_layout.addWidget(self.download_path_label)
        
        self.download_path = QLineEdit("downloads")
        self.download_path.setPlaceholderText(tr("ui.download.download_path"))
        path_layout.addWidget(self.download_path)
        
        self.browse_path_button = QPushButton(tr("ui.download.browse"))
        path_layout.addWidget(self.browse_path_button)
        
        options_layout.addLayout(path_layout)
        
        # 添加弹性空间，使上方内容靠上显示，下方留白
        options_layout.addStretch(1)
        
        # 将标签页添加到配置面板
        self.config_tabs.addTab(self.channel_tab, tr("ui.download.channel_tab"))
        self.config_tabs.addTab(self.options_tab, tr("ui.download.options_tab"))
    
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
        self.status_label = QLabel(tr("ui.download.status.current_task"))
        self.status_label.setStyleSheet("font-weight: bold;")
        status_layout.addWidget(self.status_label)
        
        self.current_task_label = QLabel(tr("ui.download.status.not_started"))
        status_layout.addWidget(self.current_task_label)
        
        # 添加进度条和进度文本
        progress_layout = QVBoxLayout()
        self.progress_label = QLabel(tr("ui.download.status.progress", percent=0))
        progress_layout.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1000)  # 使用更高的分辨率增加平滑度
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%v/%m (%p%)")  # 显示当前值、最大值和百分比
        progress_layout.addWidget(self.progress_bar)
        
        status_layout.addLayout(progress_layout)
        
        # 整体进度
        self.overall_progress_label = QLabel(tr("ui.download.status.overall_progress", completed=0, total=0, percent=0))
        status_layout.addWidget(self.overall_progress_label)
        
        # 添加伸展因子，使内容靠上对齐
        status_layout.addStretch(1)
        
        # 创建下载列表标签页
        self.list_tab = QWidget()
        list_layout = QVBoxLayout(self.list_tab)
        list_layout.setContentsMargins(8, 8, 8, 8)
        list_layout.setSpacing(5)
        
        # 创建下载列表
        self.download_list = QListWidget()
        self.download_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        list_layout.addWidget(self.download_list)
        
        # 将两个标签页添加到标签页控件
        self.download_tabs.addTab(self.status_tab, tr("ui.download.status_tab"))
        self.download_tabs.addTab(self.list_tab, tr("ui.download.list_tab"))
        
        # 连接标签页切换信号，清除星号提示
        self.download_tabs.currentChanged.connect(self._on_tab_changed)
        
        # 添加到主布局
        self.main_layout.addWidget(self.download_tabs, 4)  # 给标签页更多的空间
    
    def _create_action_buttons(self):
        """创建底部操作按钮"""
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 5, 0, 0)  # 增加上边距
        
        self.start_button = QPushButton(tr("ui.download.start_download"))
        self.start_button.setMinimumHeight(40)
        self.start_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        self.stop_button = QPushButton(tr("ui.download.stop_download"))
        self.stop_button.setMinimumHeight(40)
        self.stop_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.stop_button.setEnabled(False)  # 初始状态为禁用
        
        self.save_config_button = QPushButton(tr("ui.common.save"))
        self.save_config_button.setMinimumHeight(30)
        self.save_config_button.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        
        self.clear_list_button = QPushButton(tr("ui.common.clear"))
        self.clear_list_button.setMinimumHeight(30)
        self.clear_list_button.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
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
        self.stop_button.clicked.connect(self._stop_download)
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
        self.channel_input.setToolTip(tr("ui.download.source_channel_placeholder"))
        self.start_id.setToolTip(tr("ui.download.message_range.start_id"))
        self.end_id.setToolTip(tr("ui.download.message_range.end_id"))
        self.browse_path_button.setToolTip(tr("ui.download.browse_title"))
        self.keyword_input.setToolTip(tr("ui.download.keyword_placeholder"))
    
    def _browse_download_path(self):
        """浏览下载路径对话框"""
        path = QFileDialog.getExistingDirectory(
            self, 
            tr("ui.download.browse_title"),
            self.download_path.text()
        )
        
        if path:
            self.download_path.setText(path)
    
    def _add_channel(self):
        """添加频道到列表"""
        channel = self.channel_input.text().strip()
        
        if not channel:
            QMessageBox.warning(self, tr("ui.common.warning"), tr("ui.forward.messages.add_pair_warning"))
            return
        
        # 检查是否已存在相同频道
        for i in range(self.channel_list.count()):
            item_data = self.channel_list.item(i).data(Qt.UserRole)
            if item_data.get('channel') == channel:
                QMessageBox.information(self, tr("ui.common.info"), tr("ui.download.messages.already_in_list"))
                return
        
        # 获取关键词
        keywords = []
        keywords_text = self.keyword_input.text().strip()
        if keywords_text:
            # 以逗号分隔不同的关键词或同义关键词组
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
        display_text = f"{channel} (" + tr("ui.download.display.id_range_both", start=channel_data['start_id'], end=(channel_data['end_id'] if channel_data['end_id'] > 0 else tr('ui.download.message_range.latest_message'))) + ")"
        # 如果有关键词，添加到显示文本中
        if keywords:
            keywords_str = ', '.join(keywords)
            display_text += f"（{tr('ui.download.display.keywords')}: {keywords_str}）"
        # 添加媒体类型到显示文本中
        if media_types:
            media_types_display = {
                "photo": tr("ui.forward.media_types.photo"),
                "video": tr("ui.forward.media_types.video"),
                "document": tr("ui.forward.media_types.document"),
                "audio": tr("ui.forward.media_types.audio"),
                "animation": tr("ui.forward.media_types.animation")
            }
            media_types_str = ', '.join([media_types_display.get(t, t) for t in media_types])
            display_text += f"（{tr('ui.download.display.media', types=media_types_str)}）"
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
            QMessageBox.information(self, tr("ui.common.info"), tr("ui.download.messages.select_to_remove"))
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
    
    def _get_directory_size(self, path: str) -> int:
        """获取目录总大小（以字节为单位）
        
        Args:
            path: 目录路径
            
        Returns:
            int: 目录大小（字节）
        """
        try:
            total_size = 0
            path_obj = Path(path)
            
            # 检查路径是否存在
            if not path_obj.exists():
                return 0
                
            # 如果是文件，直接返回文件大小
            if path_obj.is_file():
                return path_obj.stat().st_size
                
            # 遍历目录计算总大小
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    file_path = os.path.join(dirpath, filename)
                    # 跳过符号链接
                    if not os.path.islink(file_path):
                        total_size += os.path.getsize(file_path)
                        
            return total_size
        except Exception as e:
            logger.error(f"计算目录大小时出错: {e}")
            return 0
            
    def _check_directory_size_limit(self) -> Tuple[bool, int, int]:
        """检查下载目录大小是否超过限制
        
        Returns:
            Tuple[bool, int, int]: (是否超过限制, 当前大小(MB), 限制大小(MB))
        """
        # 如果未启用目录大小限制，直接返回False
        if not self.dir_size_limit_check.isChecked():
            return False, 0, 0
            
        # 获取下载路径和大小限制
        download_path = self.download_path.text()
        limit_mb = self.dir_size_limit.value()
        
        # 获取当前目录大小（字节）
        current_size_bytes = self._get_directory_size(download_path)
        # 转换为MB
        current_size_mb = current_size_bytes / (1024 * 1024)
        
        # 检查是否超过限制
        return current_size_mb > limit_mb, int(current_size_mb), limit_mb
        
    def _show_directory_size_limit_dialog(self, current_size_mb: int, limit_mb: int):
        """显示目录大小超出限制的警告对话框，带5秒倒计时自动关闭
        
        Args:
            current_size_mb: 当前目录大小(MB)
            limit_mb: 限制大小(MB)
        """
        # 创建对话框
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setWindowTitle(tr("ui.download.dir_exceed_title"))
        msg_box.setText(tr("ui.download.dir_exceed_text", current=current_size_mb, limit=limit_mb))
        msg_box.setStandardButtons(QMessageBox.Ok)
        
        # 创建倒计时标签
        countdown_label = QLabel(tr("ui.download.dir_exceed_countdown", seconds=5))
        msg_box.setInformativeText(countdown_label.text())
        
        # 显示对话框（不阻塞）
        msg_box.show()
        
        # 倒计时处理
        countdown = 5
        
        def update_countdown():
            nonlocal countdown
            countdown -= 1
            if countdown > 0:
                msg_box.setInformativeText(tr("ui.download.dir_exceed_countdown", seconds=countdown))
                timer.start(1000)  # 继续倒计时
            else:
                msg_box.close()  # 关闭对话框
                timer.stop()
                timer.deleteLater()
        
        # 创建定时器
        timer = QTimer()
        timer.timeout.connect(update_countdown)
        timer.start(1000)  # 每秒触发一次
    
    def _start_download(self):
        """开始下载"""
        # 检查频道列表
        if self.channel_list.count() == 0:
            QMessageBox.warning(self, tr("ui.common.warning"), tr("ui.forward.messages.add_pair_warning"))
            return
        
        # 检查媒体类型
        media_types = self._get_media_types()
        if not media_types:
            QMessageBox.warning(self, tr("ui.common.warning"), tr("ui.download.file_types"))
            return
        
        # 检查下载器是否已设置
        if not hasattr(self, 'downloader') or self.downloader is None:
            QMessageBox.warning(self, tr("ui.common.error"), tr("ui.download.error_downloader_not_init"))
            logger.error("尝试开始下载，但下载器未初始化")
            return
            
        # 检查下载目录大小是否超过限制
        exceeded, current_size_mb, limit_mb = self._check_directory_size_limit()
        if exceeded:
            logger.warning(f"下载目录大小超出限制: 当前 {current_size_mb}MB, 限制 {limit_mb}MB")
            self._show_directory_size_limit_dialog(current_size_mb, limit_mb)
            return
        
        # 在开始下载前，重置下载器的进度计数
        if hasattr(self.downloader, '_reset_progress'):
            self.downloader._reset_progress()
        elif hasattr(self.downloader, 'reset_progress'):
            self.downloader.reset_progress()
        
        # 准备开始下载，更新按钮状态
        self.start_button.setText(tr("ui.download.start_download"))
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)  # 启用停止按钮
        
        # 清空下载列表
        self.download_list.clear()
        
        # 重置计数器和进度显示
        self.completed_downloads = 0
        self.total_downloads = 0
        self.progress_bar.setValue(0)
        self.progress_label.setText(tr("ui.download.status.progress", percent=0))
        self.overall_progress_label.setText(tr("ui.download.status.overall_progress", completed=0, total=0, percent=0))
        self.current_task_label.setText(tr("ui.download.status.not_started"))
        
        # 重置强制更新总数标志
        self._need_update_total = True
        
        # 更新状态
        self.current_task_label.setText(tr("ui.download.status.preparing"))
        
        # 使用异步任务执行下载
        try:
            # 获取主应用实例
            app = None
            parent = self.parent()
            while parent:
                if hasattr(parent, 'app'):
                    app = parent.app
                    break
                parent = parent.parent()
            
            logger.info("创建串行下载任务")
            
            if app and hasattr(app, 'task_manager'):
                # 使用应用的任务管理器
                download_task = app.task_manager.add_task(
                    "download_task", 
                    self.downloader.download_media_from_channels()
                )
                logger.info("使用应用任务管理器创建下载任务")
            else:
                # 直接使用create_task
                from src.utils.async_utils import create_task
                download_task = create_task(self.downloader.download_media_from_channels())
                logger.info("使用create_task创建下载任务")
            
            # 记录任务已启动
            logger.info("串行下载任务已启动")
            
            # 确保下载完成后恢复按钮状态
            # 这部分依赖下载器的信号系统
            # 在_on_all_downloads_complete方法中已经处理了按钮状态的恢复
        except Exception as e:
            # 处理启动下载任务时的错误
            logger.error(f"启动下载任务失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            # 恢复按钮状态
            self.start_button.setText(tr("ui.download.start_download"))
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            
            # 显示错误消息
            QMessageBox.critical(self, tr("ui.common.error"), tr("ui.download.error_start_failed", error=str(e)))
    
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
            
            # 确保关键词是列表而非字符串
            keywords = channel_data.get('keywords', [])
            
            setting_item = {
                'source_channels': channel_data.get('channel', ''),
                'start_id': channel_data.get('start_id', 0),
                'end_id': channel_data.get('end_id', 0),
                'keywords': keywords,
                'media_types': valid_media_types
            }
            download_setting.append(setting_item)
        
        # 按照现有配置结构更新DOWNLOAD部分
        download_config = {
            'downloadSetting': download_setting,
            'download_path': self.download_path.text(),
            'parallel_download': self.parallel_check.isChecked(),
            'max_concurrent_downloads': self.max_downloads.value(),
            'dir_size_limit_enabled': self.dir_size_limit_check.isChecked(),
            'dir_size_limit': self.dir_size_limit.value()
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
        
        # 更新DOWNLOAD部分
        updated_config['DOWNLOAD'] = download_config
        
        # 发送配置保存信号
        logger.debug(f"向主窗口发送配置保存信号，更新下载配置")
        self.config_saved.emit(updated_config)
        
        # 重置下载计数器和进度显示
        self.completed_downloads = 0
        self.total_downloads = 0
        self.progress_bar.setValue(0)
        self.progress_label.setText(tr("ui.download.status.progress", percent=0))
        self.overall_progress_label.setText(tr("ui.download.status.overall_progress", completed=0, total=0, percent=0))
        self.current_task_label.setText("未开始下载")
        
        # 重置强制更新总数标志
        self._need_update_total = True
        
        # 显示成功消息
        QMessageBox.information(self, tr("ui.common.info"), tr("ui.download.messages.config_saved"))
        
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
                self.download_tabs.setTabText(1, tr("ui.download.list_tab") + " *")  # 添加星号表示有新内容
    
    def update_overall_progress(self, completed, total):
        """更新总体进度
        
        Args:
            completed: 已完成数量
            total: 总数量
        """
        # 使用当前实际的总数或传入的总数，取较大值
        actual_total = max(self.total_downloads, total)
        
        if actual_total > 0:
            percentage = min(int((completed / actual_total) * 100), 100)
            self.overall_progress_label.setText(tr("ui.download.status.overall_progress", completed=completed, total=actual_total, percent=percentage))
            
            # 如果有进度条，也更新进度条，使用高精度的1000分比
            if hasattr(self, 'progress_bar'):
                # 只有在总数发生变化时才重新设置范围，避免闪烁
                if self.progress_bar.maximum() != 1000:
                    self.progress_bar.setRange(0, 1000)
                # 计算高精度的进度值
                progress_value = min(int((completed / actual_total) * 1000), 1000)
                self.progress_bar.setValue(progress_value)
        else:
            self.overall_progress_label.setText(tr("ui.download.status.preparing"))
        
        # 切换到下载状态标签页
        if self.download_tabs.currentIndex() != 0:  # 0是下载状态的索引
            self.download_tabs.setTabText(0, tr("ui.download.status_tab") + " *")  # 添加星号表示有更新
        
        # 如果已全部完成，启用开始按钮
        if completed >= actual_total and actual_total > 0:
            self.start_button.setEnabled(True)
            # 恢复标签页文本
            self.download_tabs.setTabText(0, tr("ui.download.status_tab"))
            self.download_tabs.setTabText(1, tr("ui.download.list_tab"))
    
    def update_current_task(self, task_description):
        """更新当前任务描述
        
        Args:
            task_description: 任务描述文本
        """
        self.current_task_label.setText(task_description)
    
    def _update_status(self, status):
        """更新状态信息
        
        Args:
            status: 状态信息
        """
        try:
            logger.debug(f"下载状态更新: {status}")
        except Exception as e:
            logger.error(f"更新状态信息时出错: {e}")
    
    def _update_progress(self, current, total, filename=None, speed=None):
        """更新下载进度
        
        Args:
            current: 当前进度
            total: 总进度
            filename: 文件名(可选)
            speed: 下载速度元组 (值, 单位) (可选)
        """
        try:
            # 更新进度条，使用更高的精度以平滑显示
            if total > 0:
                # 将进度转换为千分比以提高进度条的平滑度
                progress_value = min(int((current / total) * 1000), 1000)
                self.progress_bar.setRange(0, 1000)
                self.progress_bar.setValue(progress_value)
                
                # 计算整数百分比
                percentage = int((current / total) * 100)
                
                # 更新进度文本和当前下载任务标签
                if filename:
                    self.progress_label.setText(tr("ui.download.status.progress", percent=percentage))
                    self.current_task_label.setText(tr("ui.download.status.current_task") + f" {filename}")
                else:
                    self.progress_label.setText(tr("ui.download.status.progress", percent=percentage))
                
                # 如果有速度信息，添加到显示中
                if speed and isinstance(speed, tuple) and len(speed) == 2:
                    speed_value, speed_unit = speed
                    self.progress_label.setText(tr("ui.download.status.progress", percent=percentage) + f" - {tr('ui.download.speed', speed=f'{speed_value:.1f}', unit=speed_unit)}")
            else:
                # 不确定的进度，使用循环进度条
                self.progress_bar.setRange(0, 0)
                
                # 更新进度文本和当前下载任务标签
                if filename:
                    self.progress_label.setText(tr("ui.download.status.progress", percent=0))
                    self.current_task_label.setText(tr("ui.download.status.current_task") + f" {filename}")
                else:
                    self.progress_label.setText(tr("ui.download.status.progress", percent=0))
                
                # 如果有速度信息，添加到显示中
                if speed and isinstance(speed, tuple) and len(speed) == 2:
                    speed_value, speed_unit = speed
                    self.progress_label.setText(tr("ui.download.status.progress", percent=0) + f" - {tr('ui.download.speed', speed=f'{speed_value:.1f}', unit=speed_unit)}")
        except Exception as e:
            logger.error(f"更新进度时出错: {e}")
    
    def _on_download_complete(self, message_id, filename, file_size):
        """处理下载完成事件
        
        Args:
            message_id: 消息ID
            filename: 文件名
            file_size: 文件大小
        """
        try:
            # 检查下载目录大小是否超过限制
            exceeded, current_size_mb, limit_mb = self._check_directory_size_limit()
            if exceeded:
                logger.warning(f"下载完成后检测到目录大小超出限制: 当前 {current_size_mb}MB, 限制 {limit_mb}MB")
                self._stop_download()  # 停止下载
                self._show_directory_size_limit_dialog(current_size_mb, limit_mb)
                return
            
            # 增加下载完成计数
            self.completed_downloads += 1
            
            # 格式化文件大小
            readable_size = self._format_size(file_size)
            
            # 创建列表项
            item = QListWidgetItem(f"{filename} ({readable_size}) - {tr('ui.download.status.completed')}")
            
            # 添加到下载列表
            self.download_list.addItem(item)
            
            # 保持最新项可见
            self.download_list.scrollToBottom()
            
            # 如果当前不在下载列表标签页，显示提示
            if self.download_tabs.currentIndex() != 1:  # 1是下载列表的索引
                # 切换到下载列表标签页查看详情
                self.download_tabs.setTabText(1, tr("ui.download.list_tab") + " *")  # 添加星号表示有新内容
            
            # 获取最新的总文件数
            total_items = self.total_downloads
            if hasattr(self.downloader, 'get_download_progress'):
                _, total_from_downloader = self.downloader.get_download_progress()
                if total_from_downloader > 0:
                    # 如果下载器报告的总数有变化，更新总数
                    if total_from_downloader != self._last_total:
                        logger.info(f"文件完成后检测到总数变化: {self._last_total} -> {total_from_downloader}")
                        self.total_downloads = total_from_downloader
                        self._last_total = total_from_downloader
                    total_items = total_from_downloader
            
            # 确保总数至少为已完成的数量
            total_items = max(total_items, self.completed_downloads)
            
            # 更新整体进度
            self.update_overall_progress(self.completed_downloads, total_items)
            
            logger.info(f"文件下载完成: {filename}, 大小: {file_size} 字节, 进度: {self.completed_downloads}/{total_items}")
        except Exception as e:
            logger.error(f"处理下载完成时出错: {e}")
    
    def _on_all_downloads_complete(self):
        """所有下载完成处理"""
        try:
            # 更新UI状态
            self.progress_bar.setRange(0, 1000)  # 保持高精度范围
            self.progress_bar.setValue(1000)  # 设置为完成状态
            self.progress_label.setText(tr("ui.download.status.completed"))
            self.overall_progress_label.setText(tr("ui.download.status.completed"))
            
            # 恢复按钮状态
            self.start_button.setText(tr("ui.download.start_download"))
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            
            # 停止进度检查定时器
            if hasattr(self, '_progress_checker') and self._progress_checker.isActive():
                self._progress_checker.stop()
            
            # 重置强制更新总数标志，为下一次下载做准备
            self._need_update_total = True
            
            # 移除弹窗提示，仅在日志中记录
            # self._show_completion_message("下载完成", "所有文件已下载完成")
            
            logger.info("所有文件下载完成")
        except Exception as e:
            logger.error(f"处理所有下载完成时出错: {e}")
    
    def _on_download_error(self, error, message=None):
        """下载错误处理
        
        Args:
            error: 错误信息
            message: 额外的消息(可选)
        """
        try:
            # 更新UI状态
            error_msg = tr("ui.download.status.error", error=error)
            if message:
                error_msg += f"\n{message}"
            self.progress_label.setText(tr("ui.download.status.error_label"))
            # 恢复进度条状态
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            # 恢复按钮状态
            self.start_button.setText(tr("ui.download.start_download"))
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            # 显示错误对话框
            self._show_error_dialog(tr("ui.common.error"), error_msg)
            logger.error(f"下载错误: {error}")
            if message:
                logger.debug(f"错误详情: {message}")
        except Exception as e:
            logger.error(f"处理下载错误时出错: {e}")
    
    def _format_size(self, size_bytes):
        """格式化文件大小
        
        Args:
            size_bytes: 文件大小(字节)
            
        Returns:
            str: 格式化后的大小
        """
        # 文件大小单位
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        
        # 计算合适的单位
        i = 0
        size = float(size_bytes)
        while size >= 1024 and i < len(units) - 1:
            size /= 1024
            i += 1
        
        # 格式化输出
        return f"{size:.2f} {units[i]}"
    
    def _show_completion_message(self, title, message):
        """显示完成提示消息
        
        Args:
            title: 标题
            message: 消息内容
        """
        try:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setWindowTitle(title)
            msg_box.setText(message)
            msg_box.exec()
        except Exception as e:
            logger.error(f"显示完成消息时出错: {e}")

    def _show_error_dialog(self, title, message):
        """显示错误对话框
        
        Args:
            title: 对话框标题
            message: 错误消息
        """
        try:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setWindowTitle(title)
            msg_box.setText(message)
            msg_box.exec()
        except Exception as e:
            logger.error(f"显示错误对话框时出错: {e}")
    
    def clear_download_list(self):
        """清空下载列表"""
        self.download_list.clear()
        self.download_tabs.setTabText(1, tr("ui.download.list_tab"))  # 恢复标签页文本
        
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
            # 确保关键词是列表
            keywords = setting.get('keywords', [])
            if isinstance(keywords, str):
                # 如果关键词被错误地保存为字符串，将其转换为列表
                keywords = [keywords] if keywords else []
            
            channel_data = {
                'channel': setting.get('source_channels', ''),
                'start_id': setting.get('start_id', 1),
                'end_id': setting.get('end_id', 0),
                'keywords': keywords,
                'media_types': setting.get('media_types', ["photo", "video", "document", "audio", "animation"])
            }
            
            if channel_data['channel']:
                item = QListWidgetItem()
                display_text = f"{channel_data['channel']} (" + tr("ui.download.display.id_range_both", start=channel_data['start_id'], end=(channel_data['end_id'] if channel_data['end_id'] > 0 else tr('ui.download.message_range.latest_message'))) + ")"
                # 如果有关键词，添加到显示文本中
                if channel_data['keywords']:
                    keywords_str = ', '.join(channel_data['keywords'])
                    display_text += f"（{tr('ui.download.display.keywords')}: {keywords_str}）"
                # 添加媒体类型到显示文本中
                if channel_data['media_types']:
                    media_types_display = {
                        "photo": tr("ui.forward.media_types.photo"),
                        "video": tr("ui.forward.media_types.video"),
                        "document": tr("ui.forward.media_types.document"),
                        "audio": tr("ui.forward.media_types.audio"),
                        "animation": tr("ui.forward.media_types.animation")
                    }
                    media_types_str = ', '.join([media_types_display.get(t, t) for t in channel_data['media_types']])
                    display_text += f"（{tr('ui.download.display.media', types=media_types_str)}）"
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
        
        # 加载目录大小限制设置
        dir_size_limit_enabled = config.get('DOWNLOAD', {}).get('dir_size_limit_enabled', False)
        self.dir_size_limit_check.setChecked(dir_size_limit_enabled)
        
        dir_size_limit = config.get('DOWNLOAD', {}).get('dir_size_limit', 1000)
        self.dir_size_limit.setValue(dir_size_limit)
    
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
        self.channel_list_label.setText(tr("ui.download.configured_pairs", count=channel_count)) 

    def set_downloader(self, downloader):
        """设置下载器实例
        
        Args:
            downloader: 下载器实例
        """
        self.downloader = downloader
        logger.info(f"下载视图已设置下载器实例: {type(downloader).__name__}")
        
        # 重置下载状态变量
        self.completed_downloads = 0
        self.total_downloads = 0
        self._last_total = 0
        self._need_update_total = True
        
        # 连接下载器信号
        self._connect_downloader_signals()
    
    def _connect_downloader_signals(self):
        """连接下载器的信号"""
        if not self.downloader:
            logger.warning("无法连接下载器信号：下载器实例不存在")
            return
        
        try:
            # 下载完成信号
            logger.info("连接下载完成信号")
            self.downloader.download_completed.connect(self._on_download_complete)
            
            # 所有下载完成信号
            logger.info("连接所有下载完成信号")
            self.downloader.all_downloads_completed.connect(self._on_all_downloads_complete)
            
            # 错误信号
            logger.info("连接错误信号")
            self.downloader.error_occurred.connect(self._on_download_error)
            
            # 进度更新信号
            logger.info("连接进度更新信号")
            self.downloader.progress_updated.connect(self._on_progress_updated)
            
            # 文件已下载跳过信号
            logger.info("连接文件已下载跳过信号")
            self.downloader.file_already_downloaded.connect(self._on_file_already_downloaded)
            
        except Exception as e:
            logger.error(f"连接下载器信号时出错: {e}")
    
    def _handle_task_progress(self, task_id, progress, status):
        """处理任务进度更新
        
        Args:
            task_id: 任务ID
            progress: 进度值 (0-100)
            status: 状态信息
        """
        if task_id == "download_task" and progress is not None:
            # 更新进度条
            self.progress_bar.setValue(progress)
            self.progress_label.setText(f"下载进度: {progress}%")
            # self.status_label.setText(status)
    
    def _check_download_progress(self):
        """检查日志中的下载进度信息"""
        # 此方法通过定时器定期调用，检查日志中是否有新的下载进度信息
        
        # 如果下载任务正在运行，获取当前正在下载的文件和进度
        if hasattr(self, 'downloader') and self.downloader:
            # 获取当前文件（只有当UI中没有显示当前文件时才更新）
            if hasattr(self.downloader, 'get_current_file'):
                current_file = self.downloader.get_current_file()
                if current_file and (self.current_task_label.text() == "未开始下载" or "下载准备中" in self.current_task_label.text()):
                    self.current_task_label.setText(f"当前下载: {current_file}")
            
            # 获取下载进度（总体进度）
            current = 0
            total = 0
            if hasattr(self.downloader, 'get_download_progress'):
                current, total = self.downloader.get_download_progress()
                
                # 记录上一次的总数，用于检测变化
                last_total = getattr(self, '_last_total', 0)
                
                # 检查总数是否有效（大于0）
                if total > 0:
                    # 如果总数发生变化或者标记为需要强制更新
                    if total != last_total or (hasattr(self, '_need_update_total') and self._need_update_total):
                        logger.info(f"更新总下载文件数: 从 {self.total_downloads} 到 {total} (上一次: {last_total})")
                        self.total_downloads = total
                        self._last_total = total  # 记录当前总数
                        self._need_update_total = False  # 重置标志
                
                # 更新UI显示的总进度
                self.update_overall_progress(current, total)
                
                # 检查下载是否已完成，如果完成则更新按钮状态
                if current == total and total > 0 and not self.start_button.isEnabled():
                    self._on_all_downloads_complete()
            
            # 更新当前文件的下载进度
            # 注意：此部分可能已经通过直接的signal更新，所以只在需要时才更新
            if hasattr(self.downloader, 'is_downloading') and self.downloader.is_downloading():
                current_file = self.downloader.get_current_file()
                speed = None
                if hasattr(self.downloader, 'get_download_speed'):
                    speed = self.downloader.get_download_speed()
                
                # 如果正在下载但没有显示文件名或速度，才主动更新UI
                speed_label = tr('ui.download.speed', speed='', unit='')
                if current_file and (tr("ui.download.status.not_started") in self.current_task_label.text() or 
                                     tr("ui.download.status.preparing") in self.current_task_label.text() or
                                     not speed_label.split(':')[0].strip() in self.progress_label.text()):
                    self._update_progress(current, total, current_file, speed)
    
    def _on_progress_updated(self, current, total, filename):
        """处理进度更新信号
        
        Args:
            current: 当前进度
            total: 总进度
            filename: 文件名
        """
        # 获取速度信息
        speed = None
        if hasattr(self.downloader, 'get_download_speed'):
            speed = self.downloader.get_download_speed()
        
        # 更新进度显示
        self._update_progress(current, total, filename, speed)
    
    def _on_file_already_downloaded(self, message_id, filename):
        """处理文件已下载跳过事件
        
        Args:
            message_id: 消息ID
            filename: 文件名
        """
        try:
            # 添加到下载列表
            item = QListWidgetItem(tr("ui.download.file_already_downloaded", message_id=message_id, filename=filename))
            item.setForeground(QColor(128, 128, 128))  # 使用灰色文本
            self.download_list.addItem(item)
            
            # 保持最新项可见
            self.download_list.scrollToBottom()
            
            # 如果当前不在下载列表标签页，显示提示
            if self.download_tabs.currentIndex() != 1:  # 1是下载列表的索引
                # 切换到下载列表标签页查看详情
                self.download_tabs.setTabText(1, tr("ui.download.list_tab") + " *")  # 添加星号表示有新内容
                
            logger.debug(f"显示已下载跳过消息: ID={message_id}, 文件={filename}")
        except Exception as e:
            logger.error(f"处理文件已下载跳过事件时出错: {e}")
    
    def _stop_download(self):
        """停止下载任务"""
        logger.info("用户请求停止下载")
        
        # 检查下载器是否已设置
        if not hasattr(self, 'downloader') or self.downloader is None:
            logger.warning("下载器未初始化，无法停止下载")
            return
            
        try:
            # 首先尝试使用应用的任务管理器
            app = None
            parent = self.parent()
            while parent:
                if hasattr(parent, 'app'):
                    app = parent.app
                    break
                parent = parent.parent()
            
            task_cancelled = False
            
            # 使用任务管理器取消任务
            if app and hasattr(app, 'task_manager'):
                if app.task_manager.is_task_running("download_task"):
                    app.task_manager.cancel_task("download_task")
                    logger.info("已通过任务管理器取消下载任务")
                    task_cancelled = True
            
            # 如果没有通过任务管理器取消成功，尝试其他方法
            if not task_cancelled:
                # 尝试取消正在进行的下载任务
                if hasattr(self.downloader, 'cancel_downloads'):
                    # 如果下载器直接支持取消操作
                    self.downloader.cancel_downloads()
                    logger.info("已请求取消下载任务")
                    task_cancelled = True
                elif hasattr(self.downloader, 'emit') and hasattr(self.downloader, 'cancel_requested'):
                    # 如果下载器支持发送信号
                    self.downloader.emit('cancel_requested')
                    logger.info("已发送取消下载请求信号")
                    task_cancelled = True
                
                # 如果上述方法都不成功，尝试找到运行中的任务并取消
                if not task_cancelled:
                    import asyncio
                    for task in asyncio.all_tasks():
                        if (task.get_name() == "download_task" or 
                            "download_media_from_channels" in str(task)) and not task.done():
                            task.cancel()
                            logger.info("已找到并取消下载任务")
                            task_cancelled = True
                            break
            
            if not task_cancelled:
                logger.warning("未找到正在运行的下载任务")
            
            # 重置强制更新总数标志
            self._need_update_total = True
            
            # 由于任务取消是异步的，等待任务实际停止
            # 在部分情况下可能需要直接恢复按钮状态
            self.start_button.setText("开始下载")
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            
        except Exception as e:
            logger.error(f"停止下载时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            # 显示错误消息
            QMessageBox.warning(self, "错误", f"停止下载时出错: {str(e)}")
            
            # 无论如何也要恢复按钮状态
            self.start_button.setText("开始下载")
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False) 

    def closeEvent(self, event):
        """处理窗口关闭事件，确保清理资源
        
        Args:
            event: 关闭事件
        """
        self._cleanup_resources()
        super().closeEvent(event)
        
    def _cleanup_resources(self):
        """清理资源，避免任务泄漏"""
        try:
            # 停止进度检查定时器
            if hasattr(self, '_progress_checker') and self._progress_checker.isActive():
                self._progress_checker.stop()
                self._progress_checker.deleteLater()
                logger.debug("已停止下载进度检查定时器")
                
            # 尝试停止下载任务
            self._stop_download()
            
            # 断开信号连接
            if hasattr(self, 'downloader') and self.downloader is not None:
                if hasattr(self.downloader, 'download_completed'):
                    try:
                        self.downloader.download_completed.disconnect(self._on_download_complete)
                    except:
                        pass
                
                if hasattr(self.downloader, 'all_downloads_completed'):
                    try:
                        self.downloader.all_downloads_completed.disconnect(self._on_all_downloads_complete)
                    except:
                        pass
                
                if hasattr(self.downloader, 'error_occurred'):
                    try:
                        self.downloader.error_occurred.disconnect(self._on_download_error)
                    except:
                        pass
                        
                logger.debug("已断开下载器信号连接")
                
            # 获取app实例并查找任务管理器
            app = None
            parent = self.parent()
            while parent:
                if hasattr(parent, 'app'):
                    app = parent.app
                    break
                parent = parent.parent()
                
            # 确保任务被正确取消
            if app and hasattr(app, 'task_manager'):
                if app.task_manager.is_task_running("download_task"):
                    app.task_manager.cancel_task("download_task")
                    logger.info("在清理时取消了运行中的下载任务")
            
            logger.debug("下载视图资源清理完成")
        except Exception as e:
            logger.error(f"清理资源时出错: {e}")
            import traceback
            logger.error(traceback.format_exc()) 

    def _check_directory_size_limit_on_startup(self):
        """启动时检查下载目录大小，如果超过限制则显示警告"""
        # 检查下载目录大小是否超过限制
        exceeded, current_size_mb, limit_mb = self._check_directory_size_limit()
        if exceeded:
            logger.warning(f"启动时检测到下载目录大小超出限制: 当前 {current_size_mb}MB, 限制 {limit_mb}MB")
            QMessageBox.warning(
                self, 
                "下载目录大小超出限制", 
                f"下载目录大小已超出设置的限制!\n\n当前大小: {current_size_mb} MB\n限制大小: {limit_mb} MB\n\n请注意，启动新的下载任务前需要清理目录或增加限制值。"
            ) 

    def _check_and_show_directory_size(self):
        """检查并显示当前下载目录大小"""
        try:
            # 获取下载路径
            download_path = self.download_path.text()
            
            # 如果路径不存在，创建它
            path_obj = Path(download_path)
            if not path_obj.exists():
                path_obj.mkdir(parents=True, exist_ok=True)
                QMessageBox.information(self, tr("ui.download.dir_info_title"), tr("ui.download.dir_created", path=download_path))
                return
            
            # 计算目录大小
            total_size_bytes = self._get_directory_size(download_path)
            
            # 格式化大小显示
            if total_size_bytes < 1024 * 1024:  # 小于1MB
                size_str = tr("ui.download.size_kb", size=f"{total_size_bytes / 1024:.2f}")
            elif total_size_bytes < 1024 * 1024 * 1024:  # 小于1GB
                size_str = tr("ui.download.size_mb", size=f"{total_size_bytes / (1024 * 1024):.2f}")
            else:  # GB或更大
                size_str = tr("ui.download.size_gb", size=f"{total_size_bytes / (1024 * 1024 * 1024):.2f}")
            
            # 检查是否接近或超过限制
            limit_message = ""
            if self.dir_size_limit_check.isChecked():
                limit_mb = self.dir_size_limit.value()
                current_mb = total_size_bytes / (1024 * 1024)
                
                if current_mb > limit_mb:
                    limit_message = "\n\n" + tr("ui.download.dir_exceed_limit", limit=limit_mb)
                elif current_mb > limit_mb * 0.9:  # 接近限制（90%以上）
                    limit_message = "\n\n" + tr("ui.download.dir_near_limit", limit=limit_mb)
            
            # 显示目录大小信息
            QMessageBox.information(
                self,
                tr("ui.download.dir_info_title"),
                tr("ui.download.dir_info", path=download_path, size=size_str) + limit_message
            )
        except Exception as e:
            logger.error(f"检查目录大小时出错: {e}")
            QMessageBox.warning(self, tr("ui.common.error"), tr("ui.download.dir_check_error", error=str(e)))
    
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
        edit_action = context_menu.addAction(tr("ui.download.edit"))
        delete_action = context_menu.addAction(tr("ui.download.delete"))
        
        # 显示菜单并获取用户选择的操作
        action = context_menu.exec(QCursor.pos())
        
        # 处理用户选择
        if action == edit_action:
            self._edit_channel(current_item)
        elif action == delete_action:
            # 删除操作直接调用已有的删除方法
            self._remove_channels()

    def _edit_channel(self, item):
        """编辑频道配置
        
        Args:
            item: 要编辑的列表项
        """
        # 获取项目索引
        row = self.channel_list.row(item)
        
        # 获取频道数据
        channel_data = item.data(Qt.UserRole)
        if not channel_data:
            return
        
        # 创建编辑对话框
        edit_dialog = QDialog(self)
        edit_dialog.setWindowTitle(tr("ui.download.edit"))
        edit_dialog.setMinimumWidth(400)
        
        # 对话框布局
        dialog_layout = QVBoxLayout(edit_dialog)
        
        # 表单布局
        form_layout = QFormLayout()
        
        # 频道输入
        channel_input = QLineEdit(channel_data.get('channel', ''))
        form_layout.addRow(tr("ui.download.source_channel"), channel_input)
        
        # 添加表单布局到对话框
        dialog_layout.addLayout(form_layout)
        
        # 消息ID范围
        id_layout = QHBoxLayout()
        
        # 起始ID
        start_id_input = QSpinBox()
        start_id_input.setRange(1, 999999999)
        start_id_input.setValue(channel_data.get('start_id', 1))
        
        # 结束ID
        end_id_input = QSpinBox()
        end_id_input.setRange(0, 999999999)
        end_id_input.setValue(channel_data.get('end_id', 0))
        end_id_input.setSpecialValueText(tr("ui.download.message_range.latest_message"))
        
        id_layout.addWidget(QLabel(tr("ui.download.message_range.start_id")))
        id_layout.addWidget(start_id_input)
        id_layout.addWidget(QLabel(tr("ui.download.message_range.end_id")))
        id_layout.addWidget(end_id_input)
        
        # 添加ID范围布局
        dialog_layout.addLayout(id_layout)
        
        # 关键词输入
        keywords_layout = QHBoxLayout()
        keywords_layout.addWidget(QLabel(tr("ui.download.keyword_filter")))
        
        keywords_input = QLineEdit()
        keywords_input.setPlaceholderText(tr("ui.download.keyword_placeholder"))
        keywords_str = ','.join(channel_data.get('keywords', []))
        keywords_input.setText(keywords_str)
        
        keywords_layout.addWidget(keywords_input)
        dialog_layout.addLayout(keywords_layout)
        
        # 媒体类型选择
        media_types = channel_data.get('media_types', [])
        
        media_group = QGroupBox(tr("ui.download.file_types"))
        media_layout = QHBoxLayout(media_group)
        
        photo_check = QCheckBox(tr("ui.forward.media_types.photo"))
        photo_check.setChecked("photo" in media_types)
        media_layout.addWidget(photo_check)
        
        video_check = QCheckBox(tr("ui.forward.media_types.video"))
        video_check.setChecked("video" in media_types)
        media_layout.addWidget(video_check)
        
        document_check = QCheckBox(tr("ui.forward.media_types.document"))
        document_check.setChecked("document" in media_types)
        media_layout.addWidget(document_check)
        
        audio_check = QCheckBox(tr("ui.forward.media_types.audio"))
        audio_check.setChecked("audio" in media_types)
        media_layout.addWidget(audio_check)
        
        animation_check = QCheckBox(tr("ui.forward.media_types.animation"))
        animation_check.setChecked("animation" in media_types)
        media_layout.addWidget(animation_check)
        
        # 添加媒体类型组
        dialog_layout.addWidget(media_group)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        save_button = QPushButton(tr("ui.common.save"))
        cancel_button = QPushButton(tr("ui.common.cancel"))
        
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
                    raise ValueError(tr("ui.download.source_required"))
                
                # 收集关键词
                new_keywords = []
                keywords_text = keywords_input.text().strip()
                if keywords_text:
                    new_keywords = [k.strip() for k in keywords_text.split(',') if k.strip()]
                
                # 收集媒体类型
                new_media_types = []
                if photo_check.isChecked():
                    new_media_types.append("photo")
                if video_check.isChecked():
                    new_media_types.append("video")
                if document_check.isChecked():
                    new_media_types.append("document")
                if audio_check.isChecked():
                    new_media_types.append("audio")
                if animation_check.isChecked():
                    new_media_types.append("animation")
                
                if not new_media_types:
                    raise ValueError(tr("ui.download.file_types"))
                
                # 创建更新后的频道数据
                updated_data = {
                    'channel': new_channel,
                    'start_id': start_id_input.value(),
                    'end_id': end_id_input.value(),
                    'keywords': new_keywords,
                    'media_types': new_media_types
                }
                
                # 更新列表项和数据
                self._update_channel(row, updated_data)
                
            except ValueError as e:
                QMessageBox.warning(self, tr("ui.common.warning"), str(e))

    def _update_channel(self, row, updated_data):
        """更新频道数据
        
        Args:
            row: 行索引
            updated_data: 更新后的频道数据
        """
        # 更新列表项
        if 0 <= row < self.channel_list.count():
            item = self.channel_list.item(row)
            if item:
                display_text = f"{updated_data['channel']} (" + tr("ui.download.display.id_range_both", start=updated_data['start_id'], end=(updated_data['end_id'] if updated_data['end_id'] > 0 else tr('ui.download.message_range.latest_message'))) + ")"
                if updated_data.get('keywords'):
                    keywords_str = ', '.join(updated_data['keywords'])
                    display_text += f"（{tr('ui.download.display.keywords')}: {keywords_str}）"
                if updated_data.get('media_types'):
                    media_types_display = {
                        "photo": tr("ui.forward.media_types.photo"),
                        "video": tr("ui.forward.media_types.video"),
                        "document": tr("ui.forward.media_types.document"),
                        "audio": tr("ui.forward.media_types.audio"),
                        "animation": tr("ui.forward.media_types.animation")
                    }
                    media_types_str = ', '.join([media_types_display.get(t, t) for t in updated_data['media_types']])
                    display_text += f"（{tr('ui.download.display.media', types=media_types_str)}）"
                item.setText(display_text)
                item.setData(Qt.UserRole, updated_data) 

    def _update_translations(self):
        # 防止递归调用
        if hasattr(self, '_updating_translations') and self._updating_translations:
            return
            
        self._updating_translations = True
        try:
            logger.debug("=== 开始更新下载视图翻译 ===")
            
            # 更新所有静态文本
            self.channel_label.setText(tr("ui.download.source_channel"))
            self.channel_input.setPlaceholderText(tr("ui.download.source_channel_placeholder"))
            self.id_label.setText(tr("ui.download.message_range.start_id"))
            self.to_label.setText(tr("ui.download.message_range.to"))
            self.end_id.setSpecialValueText(tr("ui.download.message_range.latest_message"))
            self.keyword_label.setText(tr("ui.download.keyword_filter"))
            self.keyword_input.setPlaceholderText(tr("ui.download.keyword_placeholder"))
            self.add_channel_button.setText(tr("ui.download.add_pair"))
            self.remove_channel_button.setText(tr("ui.download.remove_pair"))
            self.media_type_label.setText(tr("ui.download.file_types"))
            self.photo_check.setText(tr("ui.forward.media_types.photo"))
            self.video_check.setText(tr("ui.forward.media_types.video"))
            self.document_check.setText(tr("ui.forward.media_types.document"))
            self.audio_check.setText(tr("ui.forward.media_types.audio"))
            self.animation_check.setText(tr("ui.forward.media_types.animation"))
            self.channel_list_label.setText(tr("ui.download.configured_pairs", count=self.channel_list.count()))
            self.config_tabs.setTabText(0, tr("ui.download.channel_tab"))
            self.config_tabs.setTabText(1, tr("ui.download.options_tab"))
            self.parallel_check.setText(tr("ui.download.parallel_download"))
            self.max_concurrent_label.setText(tr("ui.download.max_concurrent"))
            self.restart_note.setText(tr("ui.download.restart_note"))
            self.dir_size_limit_check.setText(tr("ui.download.dir_size_limit_check"))
            self.check_dir_size_button.setText(tr("ui.download.check_dir_size"))
            self.download_path_label.setText(tr("ui.download.download_path"))
            self.download_path.setPlaceholderText(tr("ui.download.download_path"))
            self.browse_path_button.setText(tr("ui.download.browse"))
            self.start_button.setText(tr("ui.download.start_download"))
            self.stop_button.setText(tr("ui.download.stop_download"))
            self.save_config_button.setText(tr("ui.common.save"))
            self.clear_list_button.setText(tr("ui.common.clear"))
            
            # 更新工具提示
            self.start_button.setToolTip(tr("ui.download.start_download"))
            self.stop_button.setToolTip(tr("ui.download.stop_download"))
            self.save_config_button.setToolTip(tr("ui.common.save"))
            self.clear_list_button.setToolTip(tr("ui.common.clear"))
            self.channel_input.setToolTip(tr("ui.download.source_channel_placeholder"))
            self.start_id.setToolTip(tr("ui.download.message_range.start_id"))
            self.end_id.setToolTip(tr("ui.download.message_range.end_id"))
            self.browse_path_button.setToolTip(tr("ui.download.browse_title"))
            self.keyword_input.setToolTip(tr("ui.download.keyword_placeholder"))
            
            # 更新标签页文本
            self.download_tabs.setTabText(0, tr("ui.download.status_tab"))
            self.download_tabs.setTabText(1, tr("ui.download.list_tab"))
            
            # 更新状态标签
            self.status_label.setText(tr("ui.download.status.current_task"))
            
            # 动态刷新频道列表项文本
            for i in range(self.channel_list.count()):
                item = self.channel_list.item(i)
                data = item.data(Qt.UserRole)
                if data:
                    display_text = f"{data['channel']} (" + tr("ui.download.display.id_range_both", start=data['start_id'], end=(data['end_id'] if data['end_id'] > 0 else tr('ui.download.message_range.latest_message'))) + ")"
                    if data.get('keywords'):
                        keywords_str = ', '.join(data['keywords'])
                        display_text += f"（{tr('ui.download.display.keywords')}: {keywords_str}）"
                    if data.get('media_types'):
                        media_types_display = {
                            "photo": tr("ui.forward.media_types.photo"),
                            "video": tr("ui.forward.media_types.video"),
                            "document": tr("ui.forward.media_types.document"),
                            "audio": tr("ui.forward.media_types.audio"),
                            "animation": tr("ui.forward.media_types.animation")
                        }
                        media_types_str = ', '.join([media_types_display.get(t, t) for t in data['media_types']])
                        display_text += f"（{tr('ui.download.display.media', types=media_types_str)}）"
                    item.setText(display_text)
            
            # 更新下载列表中的项目
            import re
            for i in range(self.download_list.count()):
                item = self.download_list.item(i)
                if item:
                    item_text = item.text()
                    
                    # 检查是否是"已下载跳过"项目
                    if any(keyword in item_text.lower() for keyword in ["already downloaded", "skipped", "已下载", "跳过"]):
                        # 尝试提取消息ID和文件名
                        msg_match = re.search(r"(?:Message|消息)\s*\[(\d+)\].*?(?:skipped|跳过)[:：]?\s*(.+?)(?:\s*\(|$)", item_text, re.IGNORECASE)
                        if msg_match:
                            message_id, filename = msg_match.groups()
                            filename = filename.strip()
                            new_text = tr("ui.download.file_already_downloaded", message_id=message_id, filename=filename)
                            item.setText(new_text)
                            # 保持灰色文本
                            from PySide6.QtGui import QColor
                            item.setForeground(QColor(128, 128, 128))
                    
                    # 检查是否是"已完成"项目
                    elif any(keyword in item_text.lower() for keyword in ["completed", "已完成", "完成"]):
                        # 尝试提取文件名和大小信息
                        completed_match = re.search(r"(.+?)\s*\(([^)]+)\)\s*-\s*(?:completed|已完成)", item_text, re.IGNORECASE)
                        if completed_match:
                            filename, size_info = completed_match.groups()
                            new_text = f"{filename.strip()} ({size_info.strip()}) - {tr('ui.download.status.completed')}"
                            item.setText(new_text)
            
            # === 最关键的部分：更新进度标签和总进度标签 ===
            # 暂时断开信号连接，避免在更新过程中触发其他更新
            progress_text = self.progress_label.text()
            overall_text = self.overall_progress_label.text()
            
            logger.debug(f"准备更新进度标签: '{progress_text}' -> 检测状态")
            logger.debug(f"准备更新总进度标签: '{overall_text}' -> 检测状态")
            
            # 更新进度标签
            if progress_text:
                # 提取百分比
                progress_match = re.search(r"(\d+)%", progress_text)
                if progress_match:
                    percent = int(progress_match.group(1))
                    new_text = tr("ui.download.status.progress", percent=percent)
                    self.progress_label.setText(new_text)
                    logger.debug(f"进度标签更新为: '{new_text}'")
                elif any(keyword in progress_text.lower() for keyword in ["completed", "完成", "已完成", "all downloads completed", "所有下载已完成"]):
                    new_text = tr("ui.download.status.completed")
                    self.progress_label.setText(new_text)
                    logger.debug(f"进度标签更新为完成状态: '{new_text}'")
                elif any(keyword in progress_text.lower() for keyword in ["error", "错误"]):
                    new_text = tr("ui.download.status.error_label")
                    self.progress_label.setText(new_text)
                    logger.debug(f"进度标签更新为错误状态: '{new_text}'")
                elif any(keyword in progress_text.lower() for keyword in ["preparing", "准备"]):
                    new_text = tr("ui.download.status.preparing")
                    self.progress_label.setText(new_text)
                    logger.debug(f"进度标签更新为准备状态: '{new_text}'")
            
            # 更新总进度标签
            if overall_text:
                # 提取数字信息
                overall_match = re.search(r"(\d+)[^\d]+(\d+).*?(\d+)%", overall_text)
                if overall_match:
                    completed, total, percent = overall_match.groups()
                    new_text = tr("ui.download.status.overall_progress", completed=int(completed), total=int(total), percent=int(percent))
                    self.overall_progress_label.setText(new_text)
                    logger.debug(f"总进度标签更新为: '{new_text}'")
                elif any(keyword in overall_text.lower() for keyword in ["completed", "完成", "已完成", "all downloads completed", "所有下载已完成"]):
                    new_text = tr("ui.download.status.completed")
                    self.overall_progress_label.setText(new_text)
                    logger.debug(f"总进度标签更新为完成状态: '{new_text}'")
                elif any(keyword in overall_text.lower() for keyword in ["preparing", "准备"]):
                    new_text = tr("ui.download.status.preparing")
                    self.overall_progress_label.setText(new_text)
                    logger.debug(f"总进度标签更新为准备状态: '{new_text}'")
                elif any(keyword in overall_text.lower() for keyword in ["not started", "未开始"]):
                    new_text = tr("ui.download.status.not_started")
                    self.overall_progress_label.setText(new_text)
                    logger.debug(f"总进度标签更新为未开始状态: '{new_text}'")
            
            # 更新当前任务标签
            current_text = self.current_task_label.text()
            if current_text:
                not_started_patterns = ["未开始下载", "not started", "Not started"]
                preparing_patterns = ["下载准备中", "preparing download", "Preparing download"]
                completed_patterns = ["所有下载已完成", "all downloads completed", "All downloads completed"]
                
                if any(pattern in current_text for pattern in not_started_patterns):
                    self.current_task_label.setText(tr("ui.download.status.not_started"))
                elif any(pattern in current_text for pattern in preparing_patterns):
                    self.current_task_label.setText(tr("ui.download.status.preparing"))
                elif any(pattern in current_text for pattern in completed_patterns):
                    self.current_task_label.setText(tr("ui.download.status.completed"))
                elif ":" in current_text:
                    # 如果包含冒号，可能是"当前下载: 文件名"格式
                    parts = current_text.split(":", 1)
                    if len(parts) == 2:
                        filename = parts[1].strip()
                        self.current_task_label.setText(tr("ui.download.status.current_task") + f": {filename}")
            
            logger.debug("=== 下载视图翻译更新完成 ===")
            
        finally:
            self._updating_translations = False