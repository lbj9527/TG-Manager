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
from src.utils.translation_manager import get_translation_manager, tr

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
        
        # 翻译管理器
        self.translation_manager = get_translation_manager()
        self.translation_manager.language_changed.connect(self._update_translations)
        
        self.config = config or {}
        # 初始化频道对列表
        self.channel_pairs = []
        
        # 初始化转发器实例（稍后由主窗口设置）
        self.forwarder = None
        
        # 状态表格相关数据跟踪
        self.status_table_data = {}  # 存储每行的状态数据
        self.forwarding_status = False  # 当前转发状态
        self.total_message_counts = {}  # 存储每个频道对的总消息数 {(source, target): total_count}
        self.forwarded_message_counts = {}  # 存储每个频道对的已转发消息数 {(source, target): forwarded_count}
        
        # 存储需要翻译的组件引用
        self.translatable_widgets = {}
        
        # 设置布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(2)  # 减小布局间距
        self.main_layout.setContentsMargins(4, 4, 4, 4)  # 减小边距
        self.setLayout(self.main_layout)
        
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
    
    def _update_translations(self):
        """语言切换时更新所有翻译文本"""
        # 更新标签页标题
        if hasattr(self, 'config_tabs'):
            # 更新配置标签页的标题
            for i in range(self.config_tabs.count()):
                if i == 0:  # 频道配置标签页
                    self.config_tabs.setTabText(i, tr("ui.forward.title"))
                elif i == 1:  # 转发选项标签页
                    self.config_tabs.setTabText(i, tr("ui.forward.forward_options"))
                elif i == 2:  # 转发进度标签页
                    self.config_tabs.setTabText(i, tr("ui.forward.progress_tab"))
        
        # 更新表单标签
        if 'source_label' in self.translatable_widgets:
            self.translatable_widgets['source_label'].setText(tr("ui.forward.source_channel"))
        if 'target_label' in self.translatable_widgets:
            self.translatable_widgets['target_label'].setText(tr("ui.forward.target_channels"))
        if 'text_replace_label' in self.translatable_widgets:
            self.translatable_widgets['text_replace_label'].setText(tr("ui.forward.text_replacement"))
        if 'replace_to_label' in self.translatable_widgets:
            self.translatable_widgets['replace_to_label'].setText(tr("ui.forward.replace_to"))
        if 'filter_options_label' in self.translatable_widgets:
            self.translatable_widgets['filter_options_label'].setText(tr("ui.forward.filter_options"))
        if 'keyword_label' in self.translatable_widgets:
            self.translatable_widgets['keyword_label'].setText(tr("ui.forward.keyword_filter"))
        if 'forward_params_label' in self.translatable_widgets:
            self.translatable_widgets['forward_params_label'].setText(tr("ui.forward.forward_params"))
        if 'html_file_label' in self.translatable_widgets:
            self.translatable_widgets['html_file_label'].setText(tr("ui.forward.final_message.html_file"))
        if 'start_id_label' in self.translatable_widgets:
            self.translatable_widgets['start_id_label'].setText(tr("ui.forward.message_range.start_id"))
        if 'end_id_label' in self.translatable_widgets:
            self.translatable_widgets['end_id_label'].setText(tr("ui.forward.message_range.end_id"))
        if 'forward_delay_label' in self.translatable_widgets:
            self.translatable_widgets['forward_delay_label'].setText(tr("ui.forward.forward_delay"))
        if 'tmp_directory_label' in self.translatable_widgets:
            self.translatable_widgets['tmp_directory_label'].setText(tr("ui.forward.tmp_directory"))
        if 'forward_log_label' in self.translatable_widgets:
            self.translatable_widgets['forward_log_label'].setText(tr("ui.forward.forward_log"))
        
        # 更新媒体类型复选框
        if 'text_check' in self.translatable_widgets:
            self.translatable_widgets['text_check'].setText(tr("ui.forward.media_types.text"))
        if 'photo_check' in self.translatable_widgets:
            self.translatable_widgets['photo_check'].setText(tr("ui.forward.media_types.photo"))
        if 'video_check' in self.translatable_widgets:
            self.translatable_widgets['video_check'].setText(tr("ui.forward.media_types.video"))
        if 'document_check' in self.translatable_widgets:
            self.translatable_widgets['document_check'].setText(tr("ui.forward.media_types.document"))
        if 'audio_check' in self.translatable_widgets:
            self.translatable_widgets['audio_check'].setText(tr("ui.forward.media_types.audio"))
        if 'animation_check' in self.translatable_widgets:
            self.translatable_widgets['animation_check'].setText(tr("ui.forward.media_types.animation"))
        
        # 更新转发选项复选框
        if 'remove_captions_check' in self.translatable_widgets:
            self.translatable_widgets['remove_captions_check'].setText(tr("ui.forward.options.remove_captions"))
        if 'hide_author_check' in self.translatable_widgets:
            self.translatable_widgets['hide_author_check'].setText(tr("ui.forward.options.hide_author"))
        if 'send_final_message_check' in self.translatable_widgets:
            self.translatable_widgets['send_final_message_check'].setText(tr("ui.forward.options.send_final_message"))
        if 'exclude_links_check' in self.translatable_widgets:
            self.translatable_widgets['exclude_links_check'].setText(tr("ui.forward.options.exclude_links"))
        if 'enable_web_page_preview_check' in self.translatable_widgets:
            self.translatable_widgets['enable_web_page_preview_check'].setText(tr("ui.forward.options.enable_web_page_preview"))
        
        # 更新按钮
        if 'start_button' in self.translatable_widgets:
            button = self.translatable_widgets['start_button']
            if self.forwarding_status:
                button.setText(tr("ui.forward.stop_forward"))
            else:
                button.setText(tr("ui.forward.start_forward"))
        
        if 'stop_button' in self.translatable_widgets:
            self.translatable_widgets['stop_button'].setText(tr("ui.forward.stop_forward"))
        
        if 'save_button' in self.translatable_widgets:
            self.translatable_widgets['save_button'].setText(tr("ui.common.save"))
        
        if 'add_pair_button' in self.translatable_widgets:
            self.translatable_widgets['add_pair_button'].setText(tr("ui.forward.add_pair"))
        
        if 'remove_pair_button' in self.translatable_widgets:
            self.translatable_widgets['remove_pair_button'].setText(tr("ui.forward.remove_pair"))
        
        if 'browse_html_button' in self.translatable_widgets:
            self.translatable_widgets['browse_html_button'].setText(tr("ui.forward.final_message.browse"))
        
        if 'browse_tmp_button' in self.translatable_widgets:
            self.translatable_widgets['browse_tmp_button'].setText(tr("ui.forward.browse_tmp"))
        
        # 更新状态表格表头
        if hasattr(self, 'status_table'):
            self.status_table.setHorizontalHeaderLabels([
                tr("ui.forward.source_channel").replace(":", ""),  # 移除冒号
                tr("ui.forward.target_channels").replace(":", ""),  # 移除冒号
                tr("ui.forward.forwarded_messages"),
                tr("ui.forward.status_column")
            ])
        
        # 更新输入框占位符
        if hasattr(self, 'source_input'):
            self.source_input.setPlaceholderText(tr("ui.forward.source_placeholder"))
        if hasattr(self, 'target_input'):
            self.target_input.setPlaceholderText(tr("ui.forward.target_placeholder"))
        if hasattr(self, 'original_text_input'):
            self.original_text_input.setPlaceholderText(tr("ui.forward.original_text"))
        if hasattr(self, 'target_text_input'):
            self.target_text_input.setPlaceholderText(tr("ui.forward.target_text_placeholder"))
        if hasattr(self, 'keyword_input'):
            self.keyword_input.setPlaceholderText(tr("ui.forward.keyword_placeholder"))
        if hasattr(self, 'main_final_message_html_file'):
            self.main_final_message_html_file.setPlaceholderText(tr("ui.forward.final_message.html_file_placeholder"))
        if hasattr(self, 'log_display'):
            self.log_display.setPlaceholderText(tr("ui.forward.log_placeholder"))
        
        # 更新SpinBox的特殊值文本
        if hasattr(self, 'start_id'):
            self.start_id.setSpecialValueText(tr("ui.forward.message_range.earliest_message"))
        if hasattr(self, 'end_id'):
            self.end_id.setSpecialValueText(tr("ui.forward.message_range.latest_message"))
        if hasattr(self, 'forward_delay'):
            self.forward_delay.setSuffix(" " + tr("ui.forward.seconds"))
        
        # 更新频道对列表标题
        self._update_pairs_list_title()
        
        # 更新动态内容的翻译
        self._update_dynamic_translations()
    
    def _update_dynamic_translations(self):
        """更新动态内容的翻译（状态表格数据、频道对显示文字、日志等）"""
        # 1. 更新状态表格中的状态值
        if hasattr(self, 'status_table') and self.status_table.rowCount() > 0:
            for row in range(self.status_table.rowCount()):
                status_item = self.status_table.item(row, 3)  # 状态列是第4列（索引3）
                if status_item:
                    current_status = status_item.text()
                    # 根据当前状态更新为对应的翻译
                    if current_status in ["转发中", "Forwarding"]:
                        status_item.setText(tr("ui.forward.status.running"))
                    elif current_status in ["准备中", "Preparing"]:
                        status_item.setText(tr("ui.forward.status.preparing"))
                    elif current_status in ["已完成", "Completed"]:
                        status_item.setText(tr("ui.forward.status.completed"))
                    elif current_status in ["已停止", "Stopped"]:
                        status_item.setText(tr("ui.forward.status.stopped"))
                    elif current_status in ["错误", "Error"]:
                        status_item.setText(tr("ui.forward.status.error"))
                    elif current_status in ["停止中", "Stopping"]:
                        status_item.setText(tr("ui.forward.status.stopping"))
                    elif current_status in ["就绪", "Ready"]:
                        status_item.setText(tr("ui.forward.status.ready"))
        
        # 2. 更新频道对列表中的显示文字
        if hasattr(self, 'pairs_list') and self.pairs_list.count() > 0:
            for i in range(self.pairs_list.count()):
                item = self.pairs_list.item(i)
                if item:
                    channel_pair = item.data(Qt.UserRole)
                    if channel_pair:
                        # 重新生成显示文字
                        self._update_channel_pair_display(item, channel_pair)
        
        # 3. 清空并重新初始化日志显示区域（保留重要的初始化消息）
        if hasattr(self, 'log_display'):
            # 清空现有日志
            self.log_display.clear()
            # 重新添加初始化消息
            self._add_log_message("TG-Manager " + tr("ui.forward.status.ready"), color="#6c757d")
            self._add_log_message(tr("ui.forward.messages.init_instruction"), color="#6c757d")
    
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
        self.source_input.setPlaceholderText(tr("ui.forward.source_placeholder"))
        source_label = QLabel(tr("ui.forward.source_channel"))
        self.translatable_widgets['source_label'] = source_label
        source_form_layout.addRow(source_label, self.source_input)
        config_layout.addLayout(source_form_layout)
        
        # 第二行：目标频道
        target_form_layout = QFormLayout()
        target_form_layout.setSpacing(10)
        target_form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        target_form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        
        self.target_input = QLineEdit()
        self.target_input.setPlaceholderText(tr("ui.forward.target_placeholder"))
        target_label = QLabel(tr("ui.forward.target_channels"))
        self.translatable_widgets['target_label'] = target_label
        target_form_layout.addRow(target_label, self.target_input)
        config_layout.addLayout(target_form_layout)
        
        # 第三行：文本替换
        text_replace_form_layout = QFormLayout()
        text_replace_form_layout.setSpacing(10)
        text_replace_form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        text_replace_form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        
        self.original_text_input = QLineEdit()
        self.original_text_input.setPlaceholderText(tr("ui.forward.original_text"))
        text_replace_label = QLabel(tr("ui.forward.text_replacement"))
        self.translatable_widgets['text_replace_label'] = text_replace_label
        text_replace_form_layout.addRow(text_replace_label, self.original_text_input)
        config_layout.addLayout(text_replace_form_layout)
        
        # 第四行：替换为
        replace_to_form_layout = QFormLayout()
        replace_to_form_layout.setSpacing(10)
        replace_to_form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        replace_to_form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        
        self.target_text_input = QLineEdit()
        self.target_text_input.setPlaceholderText(tr("ui.forward.target_text_placeholder"))
        replace_to_label = QLabel(tr("ui.forward.replace_to"))
        self.translatable_widgets['replace_to_label'] = replace_to_label
        replace_to_form_layout.addRow(replace_to_label, self.target_text_input)
        config_layout.addLayout(replace_to_form_layout)
        
        # 第五行：过滤选项label
        filter_options_label = QLabel(tr("ui.forward.filter_options"))
        filter_options_label.setStyleSheet("font-weight: bold;")
        self.translatable_widgets['filter_options_label'] = filter_options_label
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
        self.keyword_input.setPlaceholderText(tr("ui.forward.keyword_placeholder"))
        keyword_layout.addWidget(self.keyword_input)
        
        keyword_label = QLabel(tr("ui.forward.keyword_filter"))
        self.translatable_widgets['keyword_label'] = keyword_label
        keyword_form_layout.addRow(keyword_label, keyword_layout)
        config_layout.addLayout(keyword_form_layout)
        
        # 第七行：媒体类型
        # 媒体类型复选框布局（移除标签）
        media_types_layout = QHBoxLayout()
        
        self.text_check = QCheckBox(tr("ui.forward.media_types.text"))
        self.text_check.setChecked(True)
        self.translatable_widgets['text_check'] = self.text_check
        media_types_layout.addWidget(self.text_check)
        
        self.photo_check = QCheckBox(tr("ui.forward.media_types.photo"))
        self.photo_check.setChecked(True)
        self.translatable_widgets['photo_check'] = self.photo_check
        media_types_layout.addWidget(self.photo_check)
        
        self.video_check = QCheckBox(tr("ui.forward.media_types.video"))
        self.video_check.setChecked(True)
        self.translatable_widgets['video_check'] = self.video_check
        media_types_layout.addWidget(self.video_check)
        
        self.document_check = QCheckBox(tr("ui.forward.media_types.document"))
        self.document_check.setChecked(True)
        self.translatable_widgets['document_check'] = self.document_check
        media_types_layout.addWidget(self.document_check)
        
        self.audio_check = QCheckBox(tr("ui.forward.media_types.audio"))
        self.audio_check.setChecked(True)
        self.translatable_widgets['audio_check'] = self.audio_check
        media_types_layout.addWidget(self.audio_check)
        
        self.animation_check = QCheckBox(tr("ui.forward.media_types.animation"))
        self.animation_check.setChecked(True)
        self.translatable_widgets['animation_check'] = self.animation_check
        media_types_layout.addWidget(self.animation_check)
        
        media_types_layout.addStretch(1)  # 添加弹性空间，让复选框靠左对齐
        config_layout.addLayout(media_types_layout)
        
        # 第八行：转发参数
        forward_params_label = QLabel(tr("ui.forward.forward_params"))
        forward_params_label.setStyleSheet("font-weight: bold;")
        self.translatable_widgets['forward_params_label'] = forward_params_label
        config_layout.addWidget(forward_params_label)
        
        # 转发参数复选框布局
        forward_params_layout = QHBoxLayout()
        
        self.remove_captions_check = QCheckBox(tr("ui.forward.options.remove_captions"))
        self.remove_captions_check.setChecked(False)
        self.translatable_widgets['remove_captions_check'] = self.remove_captions_check
        forward_params_layout.addWidget(self.remove_captions_check)
        
        self.hide_author_check = QCheckBox(tr("ui.forward.options.hide_author"))
        self.hide_author_check.setChecked(True)
        self.translatable_widgets['hide_author_check'] = self.hide_author_check
        forward_params_layout.addWidget(self.hide_author_check)
        
        self.send_final_message_check = QCheckBox(tr("ui.forward.options.send_final_message"))
        self.send_final_message_check.setChecked(True)
        self.translatable_widgets['send_final_message_check'] = self.send_final_message_check
        forward_params_layout.addWidget(self.send_final_message_check)
        
        self.exclude_links_check = QCheckBox(tr("ui.forward.options.exclude_links"))
        self.exclude_links_check.setChecked(True)  # 默认勾选，方便用户使用
        self.translatable_widgets['exclude_links_check'] = self.exclude_links_check
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
        self.main_final_message_html_file.setPlaceholderText(tr("ui.forward.final_message.html_file_placeholder"))
        self.main_final_message_html_file.setEnabled(True)  # 初始状态启用（因为send_final_message_check默认选中）
        html_file_layout.addWidget(self.main_final_message_html_file)
        
        self.main_browse_html_button = QPushButton(tr("ui.forward.final_message.browse"))
        self.main_browse_html_button.setMinimumWidth(90)
        self.main_browse_html_button.setEnabled(True)  # 初始状态启用（因为send_final_message_check默认选中）
        self.translatable_widgets['browse_html_button'] = self.main_browse_html_button
        html_file_layout.addWidget(self.main_browse_html_button)
        
        # 添加网页预览复选框
        self.main_enable_web_page_preview_check = QCheckBox(tr("ui.forward.options.enable_web_page_preview"))
        self.main_enable_web_page_preview_check.setChecked(False)  # 默认不启用网页预览
        self.main_enable_web_page_preview_check.setEnabled(True)  # 初始状态启用
        self.translatable_widgets['enable_web_page_preview_check'] = self.main_enable_web_page_preview_check
        html_file_layout.addWidget(self.main_enable_web_page_preview_check)
        
        html_file_label = QLabel(tr("ui.forward.final_message.html_file"))
        self.translatable_widgets['html_file_label'] = html_file_label
        html_file_form_layout.addRow(html_file_label, html_file_layout)
        config_layout.addLayout(html_file_form_layout)
        
        # 第十行：起始ID，结束ID，添加频道对按钮，删除所选按钮
        id_and_buttons_layout = QHBoxLayout()
        
        # 起始ID和结束ID
        start_id_label = QLabel(tr("ui.forward.message_range.start_id"))
        self.translatable_widgets['start_id_label'] = start_id_label
        id_and_buttons_layout.addWidget(start_id_label)
        self.start_id = QSpinBox()
        self.start_id.setRange(0, 999999999)
        self.start_id.setValue(0)
        self.start_id.setSpecialValueText(tr("ui.forward.message_range.earliest_message"))
        self.start_id.setFixedWidth(100)
        id_and_buttons_layout.addWidget(self.start_id)
        
        end_id_label = QLabel(tr("ui.forward.message_range.end_id"))
        self.translatable_widgets['end_id_label'] = end_id_label
        id_and_buttons_layout.addWidget(end_id_label)
        self.end_id = QSpinBox()
        self.end_id.setRange(0, 999999999)
        self.end_id.setValue(0)
        self.end_id.setSpecialValueText(tr("ui.forward.message_range.latest_message"))
        self.end_id.setFixedWidth(100)
        id_and_buttons_layout.addWidget(self.end_id)
        
        # 添加一些间距
        id_and_buttons_layout.addSpacing(20)
        
        # 添加频道对和删除按钮
        self.add_pair_button = QPushButton(tr("ui.forward.add_pair"))
        self.add_pair_button.setMinimumHeight(28)
        self.translatable_widgets['add_pair_button'] = self.add_pair_button
        id_and_buttons_layout.addWidget(self.add_pair_button)
        
        self.remove_pair_button = QPushButton(tr("ui.forward.remove_pair"))
        self.remove_pair_button.setMinimumHeight(28)
        self.translatable_widgets['remove_pair_button'] = self.remove_pair_button
        id_and_buttons_layout.addWidget(self.remove_pair_button)
        
        # 添加弹性空间，让控件靠左对齐
        id_and_buttons_layout.addStretch(1)
        
        config_layout.addLayout(id_and_buttons_layout)
        
        # 第十一行到底部：已配置频道对
        # 频道列表标题
        self.pairs_list_label = QLabel()
        self.pairs_list_label.setStyleSheet("font-weight: bold;")
        self.translatable_widgets['pairs_list_label'] = self.pairs_list_label
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
        forward_delay_label = QLabel(tr("ui.forward.forward_delay"))
        self.translatable_widgets['forward_delay_label'] = forward_delay_label
        delay_layout.addWidget(forward_delay_label)
        
        self.forward_delay = QDoubleSpinBox()
        self.forward_delay.setRange(0, 60)
        self.forward_delay.setValue(0)
        self.forward_delay.setDecimals(1)
        self.forward_delay.setSingleStep(0.1)
        self.forward_delay.setSuffix(" " + tr("ui.forward.seconds"))
        delay_layout.addWidget(self.forward_delay)
        delay_layout.addStretch(1)
        
        options_layout.addLayout(delay_layout)
        
        # 临时文件路径
        tmp_layout = QHBoxLayout()
        tmp_directory_label = QLabel(tr("ui.forward.tmp_directory"))
        self.translatable_widgets['tmp_directory_label'] = tmp_directory_label
        tmp_layout.addWidget(tmp_directory_label)
        
        self.tmp_path = QLineEdit("tmp")
        tmp_layout.addWidget(self.tmp_path)
        
        self.browse_tmp_button = QPushButton(tr("ui.forward.browse_tmp"))
        self.browse_tmp_button.setMinimumWidth(90)
        self.translatable_widgets['browse_tmp_button'] = self.browse_tmp_button
        tmp_layout.addWidget(self.browse_tmp_button)
        
        options_layout.addLayout(tmp_layout)
        
        # 添加弹性空间
        options_layout.addStretch(1)
        
        # 将标签页添加到配置面板
        self.config_tabs.addTab(self.channel_tab, tr("ui.forward.title"))
        self.config_tabs.addTab(self.options_tab, tr("ui.forward.forward_options"))  # 可以添加翻译键
    
    def _create_forward_panel(self):
        """创建转发状态面板"""
        # 创建转发进度标签页
        self.progress_tab = QWidget()
        main_layout = QVBoxLayout(self.progress_tab)
        main_layout.setContentsMargins(6, 6, 6, 6)
        
        # 创建垂直分割器，用于分割状态表格和日志显示区域
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # 状态表格容器
        status_widget = QWidget()
        status_layout = QVBoxLayout(status_widget)
        status_layout.setContentsMargins(0, 0, 0, 0)
        
        # 状态表格
        self.status_table = QTableWidget()
        self.status_table.setColumnCount(4)
        self.status_table.setHorizontalHeaderLabels([
            tr("ui.forward.source_channel").replace(":", ""),  # 移除冒号
            tr("ui.forward.target_channels").replace(":", ""),  # 移除冒号
            tr("ui.forward.forwarded_messages"),
            tr("ui.forward.status_column")  # 添加状态翻译
        ])
        self.status_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.status_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.status_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        # 将状态表格添加到状态容器
        status_layout.addWidget(self.status_table)
        
        # 日志显示区域容器
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建日志显示区域标签
        log_label = QLabel(tr("ui.forward.forward_log"))
        log_label.setStyleSheet("font-weight: bold; margin-top: 4px;")
        self.translatable_widgets['forward_log_label'] = log_label
        log_layout.addWidget(log_label)
        
        # 创建日志显示区域
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.document().setMaximumBlockCount(1000)  # 限制最大行数，防止内存占用过多
        self.log_display.setPlaceholderText(tr("ui.forward.log_placeholder"))
        
        # 设置日志显示区域的样式
        self.log_display.setStyleSheet("""
            QTextEdit {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                font-size: 9pt;
                padding: 4px;
            }
        """)
        
        # 将日志显示区域添加到日志容器
        log_layout.addWidget(self.log_display)
        
        # 将状态表格和日志显示区域添加到分割器
        splitter.addWidget(status_widget)
        splitter.addWidget(log_widget)
        
        # 设置分割器的初始大小比例（3:2，即状态表格占3/5，日志显示占2/5）
        splitter.setSizes([300, 200])  # 可以根据需要调整具体数值
        
        # 设置分割器的拉伸因子，使两个区域都能够调整大小
        splitter.setStretchFactor(0, 3)  # 状态表格区域拉伸因子为3
        splitter.setStretchFactor(1, 2)  # 日志显示区域拉伸因子为2
        
        # 设置分割器的样式，使分割条更明显
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #dee2e6;
                height: 3px;
                border-radius: 1px;
            }
            QSplitter::handle:hover {
                background-color: #dc3545;
            }
        """)
        
        # 将分割器添加到主布局
        main_layout.addWidget(splitter)
        
        # 添加转发进度标签页到配置面板
        self.config_tabs.addTab(self.progress_tab, tr("ui.forward.progress_tab"))
    
    def _create_action_buttons(self):
        """创建底部操作按钮"""
        button_layout = QHBoxLayout()
        
        self.start_forward_button = QPushButton(tr("ui.forward.start_forward"))
        self.start_forward_button.setMinimumHeight(40)
        self.translatable_widgets['start_button'] = self.start_forward_button
        
        self.stop_forward_button = QPushButton(tr("ui.forward.stop_forward"))
        self.stop_forward_button.setEnabled(False)
        self.translatable_widgets['stop_button'] = self.stop_forward_button
        
        self.save_config_button = QPushButton(tr("ui.common.save"))
        self.translatable_widgets['save_button'] = self.save_config_button
        
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
        
        # 初始化状态表格
        self._update_status_table()
        
        # 初始化日志显示区域
        if hasattr(self, 'log_display'):
            self._add_log_message("TG-Manager " + tr("ui.forward.status.ready"), color="#6c757d")
            self._add_log_message(tr("ui.forward.messages.init_instruction"), color="#6c757d")
    
    def _update_pairs_list_title(self):
        """更新频道对列表标题"""
        count = self.pairs_list.count()
        pairs_count_text = tr("ui.forward.pairs_count").format(count=count)
        title = f"{tr('ui.forward.configured_pairs')}: {pairs_count_text}"
        self.pairs_list_label.setText(title)
    
    def _update_status_table(self):
        """更新状态表格，根据已启用的频道对填充表格"""
        # 保存当前的转发状态，避免在转发过程中被重置
        current_forwarding_status = getattr(self, 'forwarding_status', False)
        current_status_text = tr("ui.forward.status.running") if current_forwarding_status else tr("ui.forward.status.preparing")
        
        # 清空表格
        self.status_table.setRowCount(0)
        self.status_table_data.clear()
        
        # 遍历所有频道对，只显示已启用的
        row_index = 0
        for pair in self.channel_pairs:
            if not pair.get('enabled', True):
                continue  # 跳过已禁用的频道对
            
            source_channel = pair.get('source_channel', '')
            target_channels = pair.get('target_channels', [])
            
            # 为每个目标频道创建一行
            for target_channel in target_channels:
                self.status_table.insertRow(row_index)
                
                # 创建表格项（直接使用频道标识符）
                source_item = QTableWidgetItem(source_channel)
                target_item = QTableWidgetItem(target_channel)
                
                # 获取或初始化消息计数
                key = (source_channel, target_channel)
                # 从历史记录获取已转发消息数，如果没有则为0
                forwarded_count = self.forwarded_message_counts.get(key, 0)
                total_count = self.total_message_counts.get(key, -1)
                
                # 格式化消息数显示
                if total_count == -1:
                    # 检查是否有end_id为0的情况，如果有则显示"计算中..."，否则显示"--"
                    start_id = pair.get('start_id', 0)
                    end_id = pair.get('end_id', 0)
                    if start_id > 0 and end_id == 0:
                        count_text = f"{forwarded_count}/" + tr("ui.forward.display.calculating")
                    else:
                        count_text = f"{forwarded_count}/--"
                else:
                    count_text = f"{forwarded_count}/{total_count}"
                
                count_item = QTableWidgetItem(count_text)
                # 使用当前的转发状态，而不是硬编码为"准备中"
                status_item = QTableWidgetItem(current_status_text)
                
                # 设置表格项
                self.status_table.setItem(row_index, 0, source_item)
                self.status_table.setItem(row_index, 1, target_item)
                self.status_table.setItem(row_index, 2, count_item)
                self.status_table.setItem(row_index, 3, status_item)
                
                # 保存行数据用于后续更新
                self.status_table_data[key] = {
                    'forwarded': forwarded_count,
                    'total': total_count,
                    'status': current_status_text
                }
                
                row_index += 1
        
        logger.debug(f"状态表格已更新，显示 {row_index} 个转发目标，当前状态: {current_status_text}")
    
    async def _build_channel_id_mapping(self):
        """建立频道ID到状态表格行的映射"""
        if not hasattr(self, 'channel_id_to_table_row'):
            self.channel_id_to_table_row = {}
        self.channel_id_to_table_row.clear()
        
        # 遍历状态表格，为每行建立频道ID映射
        for row in range(self.status_table.rowCount()):
            target_item = self.status_table.item(row, 1)
            if target_item:
                target_channel = target_item.text()
                await self._add_channel_id_mapping(target_channel, row)
        
        logger.debug(f"频道ID映射建立完成: {self.channel_id_to_table_row}")
    
    async def _add_channel_id_mapping(self, target_channel, row_index):
        """异步添加频道ID映射"""
        try:
            if self.forwarder and hasattr(self.forwarder, 'channel_resolver'):
                # 获取频道ID
                channel_id = await self.forwarder.channel_resolver.get_channel_id(target_channel)
                if channel_id:
                    self.channel_id_to_table_row[channel_id] = row_index
                    logger.debug(f"已添加频道ID映射: {channel_id} -> 行{row_index} ({target_channel})")
                else:
                    logger.warning(f"无法获取频道ID: {target_channel}")
        except Exception as e:
            logger.warning(f"添加频道ID映射失败 {target_channel}: {e}")
    
    def _calculate_total_message_count(self, source_channel, start_id, end_id):
        """计算指定范围内的消息总数
        
        Args:
            source_channel: 源频道
            start_id: 起始消息ID
            end_id: 结束消息ID
            
        Returns:
            int: 估算的消息总数，如果无法确定则返回-1
        """
        # 只有当start_id和end_id都是有效的正数时，才能准确计算
        if end_id > 0 and start_id > 0:
            return max(0, end_id - start_id + 1)
        elif start_id == 0 and end_id > 0:
            # start_id为0表示"最早消息"，假设从消息ID 1开始
            return max(0, end_id - 1 + 1)  # 等同于end_id
        elif start_id > 0 and end_id == 0:
            # end_id为0表示"最新消息"，无法确定具体数量
            return -1  # 返回-1表示未知
        else:
            # 两者都为0或都无效，无法计算
            return -1  # 返回-1表示未知

    async def _async_calculate_total_message_count(self, source_channel, start_id, end_id):
        """异步计算指定范围内的消息总数，支持获取最新消息ID
        
        Args:
            source_channel: 源频道
            start_id: 起始消息ID
            end_id: 结束消息ID
            
        Returns:
            int: 估算的消息总数，如果无法确定则返回-1
        """
        try:
            # 只有当start_id和end_id都是有效的正数时，才能准确计算
            if end_id > 0 and start_id > 0:
                return max(0, end_id - start_id + 1)
            elif start_id == 0 and end_id > 0:
                # start_id为0表示"最早消息"，假设从消息ID 1开始
                return max(0, end_id - 1 + 1)  # 等同于end_id
            elif start_id > 0 and end_id == 0:
                # end_id为0表示"最新消息"，需要异步获取最新消息ID
                latest_message_id = await self._get_latest_message_id(source_channel)
                if latest_message_id and latest_message_id > 0:
                    # 成功获取最新消息ID，计算总消息数
                    actual_end_id = latest_message_id
                    total_count = max(0, actual_end_id - start_id + 1)
                    logger.debug(f"频道 {source_channel} 最新消息ID: {latest_message_id}, 计算总消息数: {total_count}")
                    return total_count
                else:
                    # 无法获取最新消息ID
                    logger.warning(f"无法获取频道 {source_channel} 的最新消息ID")
                    return -1
            else:
                # 两者都为0或都无效，无法计算
                return -1
        except Exception as e:
            logger.error(f"异步计算消息总数失败 {source_channel}: {e}")
            return -1

    async def _get_latest_message_id(self, source_channel):
        """获取指定频道的最新消息ID
        
        Args:
            source_channel: 源频道标识符
            
        Returns:
            int: 最新消息ID，失败时返回None
        """
        try:
            # 首先尝试使用forwarder的channel_resolver
            if hasattr(self, 'forwarder') and self.forwarder and hasattr(self.forwarder, 'channel_resolver'):
                # 使用channel_resolver的get_message_range方法来获取最新消息ID
                actual_start_id, actual_end_id = await self.forwarder.channel_resolver.get_message_range(
                    source_channel, 1, 0  # start_id=1, end_id=0表示获取从最早到最新的范围
                )
                if actual_end_id and actual_end_id > 0:
                    logger.debug(f"通过channel_resolver获取频道 {source_channel} 最新消息ID: {actual_end_id}")
                    return actual_end_id
            
            # 备用方法：直接使用客户端获取最新消息
            if hasattr(self, 'forwarder') and self.forwarder and hasattr(self.forwarder, 'client'):
                client = self.forwarder.client
                
                # 获取频道ID
                real_channel_id = source_channel
                if hasattr(self.forwarder, 'channel_resolver'):
                    real_channel_id = await self.forwarder.channel_resolver.get_channel_id(source_channel)
                
                if real_channel_id:
                    # 获取最新的一条消息
                    async for message in client.get_chat_history(real_channel_id, limit=1):
                        latest_id = message.id
                        logger.debug(f"直接通过客户端获取频道 {source_channel} 最新消息ID: {latest_id}")
                        return latest_id
                        
            logger.warning(f"无法获取频道 {source_channel} 的最新消息ID：转发器或客户端不可用")
            return None
            
        except Exception as e:
            logger.error(f"获取频道 {source_channel} 最新消息ID失败: {e}")
            return None

    def _calculate_and_update_total_message_counts(self):
        """计算并更新所有频道对的总消息数"""
        # 异步执行真正的计算逻辑
        asyncio.create_task(self._async_calculate_and_update_total_message_counts())

    async def _async_calculate_and_update_total_message_counts(self):
        """异步计算并更新所有频道对的总消息数和已转发消息数"""
        try:
            self.total_message_counts.clear()
            # 添加已转发消息数存储
            if not hasattr(self, 'forwarded_message_counts'):
                self.forwarded_message_counts = {}
            self.forwarded_message_counts.clear()
            
            for pair in self.channel_pairs:
                if not pair.get('enabled', True):
                    continue  # 跳过已禁用的频道对
                
                source_channel = pair.get('source_channel', '')
                target_channels = pair.get('target_channels', [])
                start_id = pair.get('start_id', 0)
                end_id = pair.get('end_id', 0)
                
                # 异步计算此频道对的总消息数
                total_count = await self._async_calculate_total_message_count(source_channel, start_id, end_id)
                
                # 为每个目标频道存储总消息数和已转发消息数
                for target_channel in target_channels:
                    key = (source_channel, target_channel)
                    self.total_message_counts[key] = total_count
                    
                    # 获取已转发消息数
                    forwarded_count = await self._get_forwarded_message_count(source_channel, target_channel, start_id, end_id)
                    self.forwarded_message_counts[key] = forwarded_count
            
            logger.debug(f"已更新总消息数计算，共 {len(self.total_message_counts)} 个转发目标")
            
            # 更新状态表格显示
            self._update_status_table()
            
        except Exception as e:
            logger.error(f"异步计算总消息数失败: {e}")

    async def _get_forwarded_message_count(self, source_channel: str, target_channel: str, start_id: int, end_id: int) -> int:
        """获取指定范围内已转发的消息数量
        
        Args:
            source_channel: 源频道
            target_channel: 目标频道
            start_id: 起始消息ID
            end_id: 结束消息ID
            
        Returns:
            int: 已转发的消息数量
        """
        try:
            if not hasattr(self, 'forwarder') or not self.forwarder or not hasattr(self.forwarder, 'history_manager'):
                return 0
            
            history_manager = self.forwarder.history_manager
            if not history_manager:
                return 0
            
            # 获取所有已转发的消息ID列表
            forwarded_messages = history_manager.get_forwarded_messages(source_channel, target_channel)
            
            if not forwarded_messages:
                return 0
            
            # 如果有消息ID范围限制，筛选在范围内的消息
            if start_id > 0 or end_id > 0:
                # 获取实际的结束ID（如果end_id为0，需要获取最新消息ID）
                actual_end_id = end_id
                if end_id == 0 and start_id > 0:
                    # 尝试获取最新消息ID
                    latest_id = await self._get_latest_message_id(source_channel)
                    if latest_id and latest_id > 0:
                        actual_end_id = latest_id
                    else:
                        # 如果无法获取最新ID，不过滤消息（计算所有已转发消息）
                        actual_end_id = float('inf')
                
                # 计算在指定范围内的已转发消息数
                if start_id > 0 and actual_end_id > 0:
                    # 有明确范围
                    count = len([msg_id for msg_id in forwarded_messages 
                               if start_id <= msg_id <= actual_end_id])
                elif start_id > 0:
                    # 只有起始ID
                    count = len([msg_id for msg_id in forwarded_messages 
                               if msg_id >= start_id])
                elif actual_end_id > 0 and actual_end_id != float('inf'):
                    # 只有结束ID
                    count = len([msg_id for msg_id in forwarded_messages 
                               if msg_id <= actual_end_id])
                else:
                    # 无范围限制，返回所有已转发消息数
                    count = len(forwarded_messages)
            else:
                # 无范围限制，返回所有已转发消息数
                count = len(forwarded_messages)
            
            logger.debug(f"频道对 {source_channel} -> {target_channel} 在指定范围内已转发 {count} 条消息")
            return count
            
        except Exception as e:
            logger.error(f"获取已转发消息数失败 {source_channel} -> {target_channel}: {e}")
            return 0

    def _add_channel_pair(self):
        """添加频道对"""
        # 获取源频道和目标频道
        source = self.source_input.text().strip()
        if not source:
            QMessageBox.warning(self, tr("ui.common.warning"), tr("ui.forward.messages.source_required"))
            return
        
        target_text = self.target_input.text().strip()
        if not target_text:
            QMessageBox.warning(self, tr("ui.common.warning"), tr("ui.forward.messages.target_required"))
            return
        
        # 分割多个目标频道
        target_channels = [t.strip() for t in target_text.split(',') if t.strip()]
        if not target_channels:
            QMessageBox.warning(self, tr("ui.common.warning"), tr("ui.forward.messages.invalid_target"))
            return
        
        # 获取消息ID范围
        start_id = self.start_id.value()
        end_id = self.end_id.value()
        
        # 获取选中的媒体类型
        media_types = self._get_media_types()
        if not media_types:
            QMessageBox.warning(self, tr("ui.common.warning"), tr("ui.forward.messages.select_media_type"))
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
                'enable_web_page_preview': self.main_enable_web_page_preview_check.isChecked(),
                'text_filter': text_filter,
                'keywords': keywords,
                'exclude_links': self.exclude_links_check.isChecked()
            }
            
            # 添加到列表
            item = QListWidgetItem()
            
            # 创建媒体类型显示文本
            media_types_str = []
            if self._is_media_type_in_list(MediaType.TEXT, media_types):
                media_types_str.append(tr("ui.forward.media_types.text"))
            if self._is_media_type_in_list(MediaType.PHOTO, media_types):
                media_types_str.append(tr("ui.forward.media_types.photo"))
            if self._is_media_type_in_list(MediaType.VIDEO, media_types):
                media_types_str.append(tr("ui.forward.media_types.video"))
            if self._is_media_type_in_list(MediaType.DOCUMENT, media_types):
                media_types_str.append(tr("ui.forward.media_types.document"))
            if self._is_media_type_in_list(MediaType.AUDIO, media_types):
                media_types_str.append(tr("ui.forward.media_types.audio"))
            if self._is_media_type_in_list(MediaType.ANIMATION, media_types):
                media_types_str.append(tr("ui.forward.media_types.animation"))
            
            # 构建ID范围显示文本
            start_id = channel_pair.get('start_id', 0)
            end_id = channel_pair.get('end_id', 0)
            id_range_str = ""
            
            if start_id > 0 or end_id > 0:
                if start_id > 0 and end_id > 0:
                    id_range_str = tr("ui.forward.display.id_range_both").format(start=start_id, end=end_id)
                elif start_id > 0:
                    id_range_str = tr("ui.forward.display.id_range_start").format(start=start_id)
                else:
                    id_range_str = tr("ui.forward.display.id_range_end").format(end=end_id)
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
                    text_filter_str = f" - {tr('ui.forward.messages.text_replacements')}: {', '.join(replacements)}"
            
            # 构建关键词显示文本
            keywords = channel_pair.get('keywords', [])
            keywords_str = ""
            if keywords:
                keywords_str = f" - {tr('ui.forward.messages.keywords')}: {', '.join(keywords)}"
            
            # 构建转发选项显示文本
            options_str = []
            if channel_pair.get('remove_captions', False):
                options_str.append(tr("ui.forward.messages.option_remove_captions"))
            if channel_pair.get('hide_author', False):
                options_str.append(tr("ui.forward.messages.option_hide_author"))
            if channel_pair.get('send_final_message', False):
                options_str.append(tr("ui.forward.messages.option_send_final_message"))
            if channel_pair.get('exclude_links', False):
                options_str.append(tr("ui.forward.messages.option_exclude_links"))
            
            options_display = ""
            if options_str:
                options_display = f" - {tr('ui.forward.display.options')}: {', '.join(options_str)}"
            
            # 构建基础显示文本
            media_text = tr("ui.forward.display.media").format(types=', '.join(media_types_str))
            display_text = f"{channel_pair['source_channel']} → {', '.join(channel_pair['target_channels'])} ({media_text}){id_range_str}{text_filter_str}{keywords_str}{options_display}"
            
            # 添加启用/禁用状态标识
            is_enabled = channel_pair.get('enabled', True)
            if not is_enabled:
                display_text = f"[{tr('ui.forward.display.disabled')}] {display_text}"
            
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
            
            # 更新频道对列表标题
            self._update_pairs_list_title()
            
            # 添加到频道对列表
            self.channel_pairs.append(channel_pair)
            
            # 更新状态表格
            self._update_status_table()
        
        except ValueError as e:
            QMessageBox.warning(self, tr("ui.forward.messages.input_error"), str(e))
    
    def _remove_channel_pairs(self):
        """删除选中的频道对"""
        selected_items = self.pairs_list.selectedItems()
        
        if not selected_items:
            QMessageBox.information(self, tr("ui.common.info"), tr("ui.forward.messages.select_to_remove"))
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
        
        # 更新频道对列表标题
        self._update_pairs_list_title()
        
        # 更新状态表格
        self._update_status_table()
    
    def _browse_tmp_path(self):
        """浏览临时目录"""
        directory = QFileDialog.getExistingDirectory(
            self, 
            tr("ui.forward.tmp_directory"),
            self.tmp_path.text()
        )
        
        if directory:
            self.tmp_path.setText(directory)
    
    def _browse_main_html_file(self):
        """浏览主界面HTML文件"""
        current_path = os.path.dirname(self.main_final_message_html_file.text()) or QDir.homePath()
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            tr("ui.forward.final_message.html_file"),
            current_path,
            tr("ui.forward.file_types.html")
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
        """开始转发"""
        if not self.channel_pairs:
            QMessageBox.warning(self, tr("ui.common.warning"), tr("ui.forward.messages.add_pair_warning"))
            return
        
        # 检查是否有启用的频道对
        enabled_pairs = [pair for pair in self.channel_pairs if pair.get('enabled', True)]
        if not enabled_pairs:
            QMessageBox.warning(self, tr("ui.common.warning"), tr("ui.forward.messages.no_enabled_pairs"))
            return
        
        # 清空日志并记录开始转发
        self._clear_log()
        
        # 记录转发开始信息
        for pair in enabled_pairs:
            source_channel = pair.get('source_channel', '')
            target_channels = pair.get('target_channels', [])
            if source_channel and target_channels:
                self._log_collection_start(source_channel)
                self._log_forward_start(source_channel, target_channels)
        
        # 更新转发状态
        self.forwarding_status = True
        self._update_status_table_forwarding_status(tr("ui.forward.status.running"))
        
        # 按钮状态
        self.start_forward_button.setEnabled(False)
        self.stop_forward_button.setEnabled(True)
        
        # 获取转发配置
        forward_config = self._get_forward_config()
        
        # 发送转发开始信号
        self.forward_started.emit(forward_config)
        
        # 记录开始转发消息到状态消息和日志显示区域
        self._add_status_message(tr("ui.forward.status.starting"))
        self._add_status_message(tr("ui.forward.status.initializing"))
        self._add_info_log_message("========== " + tr("ui.forward.status.task_started") + " ==========")
        
        # 自动跳转到转发进度选项卡，方便用户查看转发状态
        # 转发进度选项卡是第3个标签页，索引为2
        self.config_tabs.setCurrentIndex(2)
        
        # 异步启动转发
        asyncio.create_task(self._async_start_forward())
    
    async def _async_start_forward(self):
        """异步启动转发"""
        try:
            # 检查转发器是否已设置
            if not self.forwarder:
                error_msg = tr("ui.forward.messages.forwarder_not_initialized_start")
                logger.error(error_msg)
                self._add_status_message(error_msg)
                # 恢复按钮状态
                self.start_forward_button.setEnabled(True)
                self.stop_forward_button.setEnabled(False)
                return
            
            self._add_status_message(tr("ui.forward.messages.calculating_history"))
            
            # 在转发开始前重新计算历史记录和总消息数，确保显示最新状态
            await self._async_calculate_and_update_total_message_counts()
            
            self._add_status_message(tr("ui.forward.messages.building_mapping"))
            
            # 建立频道ID到状态表格行的映射
            await self._build_channel_id_mapping()
            
            self._add_status_message(tr("ui.forward.messages.starting_forwarder"))
            await self.forwarder.forward_messages()
            self._add_status_message(tr("ui.forward.messages.forward_completed"))
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
            
            # 输出到日志和控制台
            logger.info(formatted_message)
            print(formatted_message)
            
            # 同时添加到UI日志显示区域
            if hasattr(self, 'log_display'):
                self._add_info_log_message(message)
            
        except Exception as e:
            print(f"添加状态消息失败: {e}")
            logger.error(f"添加状态消息失败: {e}")
            # 如果格式化失败，至少输出原始消息
            logger.info(str(message))
    
    def _stop_forward(self):
        """停止转发"""
        # 更新转发状态
        self.forwarding_status = False
        self._update_status_table_forwarding_status(tr("ui.forward.status.stopping"))
        
        # 按钮状态
        self.start_forward_button.setEnabled(True)
        self.stop_forward_button.setEnabled(False)
        
        # 记录停止转发消息
        self._add_status_message(tr("ui.forward.messages.stopping_forward"))
        
        # 记录到日志显示区域
        if hasattr(self, 'log_display'):
            self._add_warning_log_message(tr("ui.forward.log.user_stop_request"))
        
        # 异步停止转发
        asyncio.create_task(self._async_stop_forward())
    
    async def _async_stop_forward(self):
        """异步停止转发"""
        try:
            # 检查转发器是否已设置
            if not self.forwarder:
                self._add_status_message(tr("ui.forward.messages.forwarder_not_initialized_stop"))
                return
                
            # 如果转发器有停止方法，调用它
            if hasattr(self.forwarder, 'stop_forward'):
                await self.forwarder.stop_forward()
            self._add_status_message("转发已停止")
            
            # 记录到日志显示区域
            if hasattr(self, 'log_display'):
                self._add_warning_log_message(tr("ui.forward.log.forward_manually_stopped"))
                
        except Exception as e:
            logger.error(f"异步停止转发失败: {e}")
            self._add_status_message(f"停止转发失败: {e}")
            
            # 记录到日志显示区域
            if hasattr(self, 'log_display'):
                self._add_error_log_message(tr("ui.forward.log.stop_forward_failed", error=str(e)))

    def _on_forward_complete_ui_update(self):
        """转发完成后的UI更新"""
        # 记录完成状态
        logger.info("转发已完成")
        
        # 记录到日志显示区域
        if hasattr(self, 'log_display'):
            self._add_success_log_message(tr("ui.forward.log.all_tasks_completed"))
        
        # 更新转发状态
        self.forwarding_status = False
        self._update_status_table_forwarding_status(tr("ui.forward.status.completed"))
        
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
        QTimer.singleShot(100, lambda: self._show_completion_dialog(
            tr("ui.forward.messages.forward_complete"),
            tr("ui.forward.messages.all_tasks_complete")
        ))
    
    def _show_completion_dialog(self, title, message):
        """安全地显示完成对话框"""
        try:
            QMessageBox.information(self, title, message)
        except Exception as e:
            logger.error(f"显示完成对话框时出错: {e}")
            # 备用方案：使用日志记录完成信息
            logger.info(f"{message} ({title})")
    
    def _on_forward_error_ui_update(self, error_message):
        """转发出错后的UI更新"""
        # 记录错误状态
        logger.error(f"转发出错: {error_message}")
        
        # 记录到日志显示区域
        if hasattr(self, 'log_display'):
            # 检查是否为API限流错误
            is_rate_limit = any(keyword in error_message.lower() for keyword in 
                              ['rate', 'limit', 'flood', 'too many requests', '429'])
            self._log_message_forward_failed("转发任务", "转发任务", error_message, is_rate_limit)
        
        # 更新转发状态
        self.forwarding_status = False
        self._update_status_table_forwarding_status(tr("ui.forward.status.error"))
        
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
        QTimer.singleShot(100, lambda: self._show_error_dialog_safe(tr("ui.forward.messages.forward_error_title"), tr("ui.forward.messages.forward_error_detail", error=error_message)))
    
    def _show_error_dialog_safe(self, title, message):
        """安全地显示错误对话框"""
        try:
            self._show_error_dialog(title, message)
        except Exception as e:
            logger.error(f"显示错误对话框时出错: {e}")
            # 确保错误信息至少会记录在日志中
            logger.error(f"错误: {message}")
    
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
                    enable_web_page_preview=self.main_enable_web_page_preview_check.isChecked(),  # 添加网页预览字段
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
                        enable_web_page_preview=pair.get('enable_web_page_preview', False),  # 添加网页预览字段
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
            QMessageBox.information(self, tr("ui.common.info"), tr("ui.forward.messages.config_saved"))
            
            # 更新本地配置引用
            self.config = updated_config
            
            logger.debug("配置保存完成，保持当前UI状态不变")
            
            # 计算并更新总消息数
            self._calculate_and_update_total_message_counts()
            
            # 更新状态表格
            self._update_status_table()
            
        except Exception as e:
            QMessageBox.critical(self, tr("ui.common.error"), tr("ui.forward.messages.save_failed") + f": {str(e)}")
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
        key = (source, target)
        
        # 更新内部数据
        if key in self.status_table_data:
            self.status_table_data[key]['forwarded'] = count
            self.status_table_data[key]['status'] = status
            
            row = self.status_table_data[key]['row']
            total_count = self.total_message_counts.get(key, 0)
            
            # 更新表格显示
            if row < self.status_table.rowCount():
                # 格式化消息数显示
                if total_count > 0:
                    count_text = f"{count}/{total_count}"
                elif total_count == -1:
                    count_text = f"{count}/--"
                else:
                    count_text = f"{count}/0"
                
                # 更新消息数
                if self.status_table.item(row, 2):
                    self.status_table.item(row, 2).setText(count_text)
                
                # 更新状态
                if self.status_table.item(row, 3):
                    self.status_table.item(row, 3).setText(status)
        else:
            # 如果key不存在，尝试查找匹配的行
            for row in range(self.status_table.rowCount()):
                if (self.status_table.item(row, 0) and self.status_table.item(row, 1) and
                    self.status_table.item(row, 0).text() == source and
                    self.status_table.item(row, 1).text() == target):
                    
                    total_count = self.total_message_counts.get(key, 0)
                    
                    # 格式化消息数显示
                    if total_count > 0:
                        count_text = f"{count}/{total_count}"
                    elif total_count == -1:
                        count_text = f"{count}/--"
                    else:
                        count_text = f"{count}/0"
                    
                    # 更新消息数
                    if self.status_table.item(row, 2):
                        self.status_table.item(row, 2).setText(count_text)
                    
                    # 更新状态
                    if self.status_table.item(row, 3):
                        self.status_table.item(row, 3).setText(status)
                    
                    # 更新内部数据
                    self.status_table_data[key] = {
                        'row': row,
                        'forwarded': count,
                        'total': total_count,
                        'status': status
                    }
                    break
        
        # 计算并记录总转发消息数
        total_forwarded = sum(data.get('forwarded', 0) for data in self.status_table_data.values())
        logger.info(f"已转发: {total_forwarded} 条消息")
    
    def update_progress(self, value):
        """更新进度
        
        Args:
            value: 进度值 (0-100)
        """
        logger.debug(f"转发进度: {value}%")
    
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
            enable_web_page_preview = pair.get('enable_web_page_preview', False)
            
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
                    'enable_web_page_preview': enable_web_page_preview,
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
        
        # 计算并更新总消息数
        self._calculate_and_update_total_message_counts()
        
        # 更新状态表格
        self._update_status_table()

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
        
        # 连接转发器信号
        self._connect_forwarder_signals()
        
        # 连接应用级别的信号
        self._connect_app_signals()
    
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
            
            # 连接实时转发进度信号
            if hasattr(self.forwarder, 'message_forwarded'):
                self.forwarder.message_forwarded.connect(self._on_message_forwarded)
            
            if hasattr(self.forwarder, 'media_group_forwarded'):
                self.forwarder.media_group_forwarded.connect(self._on_media_group_forwarded)
            
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
                # 添加实时转发事件监听
                self.forwarder.add_event_listener("message_forwarded", self._on_message_forwarded_event)
                self.forwarder.add_event_listener("media_group_forwarded", self._on_media_group_forwarded_event)
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
        logger.info(f"转发状态: {status}")
    
    def _update_progress(self, current, total, message_info=None):
        """更新转发进度
        
        Args:
            current: 当前处理消息索引
            total: 总消息数
            message_info: 消息信息(可选)
        """
        # 计算并记录进度
        if total > 0:
            percentage = min(int((current / total) * 100), 100)
            # 记录进度信息
            if message_info:
                logger.info(f"{message_info} - {percentage}%")
                # 添加到UI日志显示区域
                if hasattr(self, 'log_display'):
                    self._log_message_collected(current, total)
            else:
                logger.info(tr("ui.forward.messages.forwarding_with_progress", percentage=percentage))
                # 添加到UI日志显示区域
                if hasattr(self, 'log_display'):
                    self._log_message_collected(current, total)
        else:
            # 不确定的进度，记录正在转发状态
            if message_info:
                logger.info(f"正在转发: {message_info}")
                # 添加到UI日志显示区域
                if hasattr(self, 'log_display'):
                    self._add_info_log_message(tr("ui.forward.log.processing_message", message_info=message_info))
            else:
                logger.info(tr("ui.forward.messages.forwarding"))
                # 添加到UI日志显示区域
                if hasattr(self, 'log_display'):
                    self._add_info_log_message(tr("ui.forward.messages.processing_messages"))
    
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
        # 构建错误信息
        error_msg = f"转发出错: {error}"
        if message:
            error_msg += f"\n{message}"
            
        # 记录错误状态
        logger.error(error_msg)
        
        # 添加错误日志到UI显示区域
        if hasattr(self, 'log_display'):
            # 检查是否为API限流错误
            is_rate_limit = 'FloodWait' in str(error) or 'Too Many Requests' in str(error) or '429' in str(error)
            self._log_message_forward_failed("未知", "转发任务", str(error), is_rate_limit)
        
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
            toggle_action = context_menu.addAction(tr("ui.forward.context_menu.disable"))
            toggle_action.setToolTip(tr("ui.forward.context_menu.disable_tooltip"))
        else:
            toggle_action = context_menu.addAction(tr("ui.forward.context_menu.enable"))
            toggle_action.setToolTip(tr("ui.forward.context_menu.enable_tooltip"))
        
        context_menu.addSeparator()  # 添加分隔线
        
        # 添加其他菜单项
        edit_action = context_menu.addAction(tr("ui.forward.context_menu.edit"))
        delete_action = context_menu.addAction(tr("ui.forward.context_menu.delete"))
        
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
        edit_dialog.setWindowTitle(tr("ui.forward.edit_dialog.title"))
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
        source_input.setPlaceholderText(tr("ui.forward.source_placeholder"))
        source_form_layout.addRow(tr("ui.forward.source_channel"), source_input)
        dialog_layout.addLayout(source_form_layout)
        
        # 第二行：目标频道
        target_form_layout = QFormLayout()
        target_form_layout.setSpacing(10)
        target_form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        target_form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        
        target_input = QLineEdit(', '.join(channel_pair.get('target_channels', [])))
        target_input.setPlaceholderText(tr("ui.forward.target_placeholder"))
        target_form_layout.addRow(tr("ui.forward.target_channels"), target_input)
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
        original_text_input.setPlaceholderText(tr("ui.forward.original_text"))
        text_replace_form_layout.addRow(tr("ui.forward.text_replacement"), original_text_input)
        dialog_layout.addLayout(text_replace_form_layout)
        
        # 第四行：替换为
        replace_to_form_layout = QFormLayout()
        replace_to_form_layout.setSpacing(10)
        replace_to_form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        replace_to_form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        
        target_text_input = QLineEdit(', '.join(target_texts))
        target_text_input.setPlaceholderText(tr("ui.forward.target_text_placeholder"))
        replace_to_form_layout.addRow(tr("ui.forward.replace_to"), target_text_input)
        dialog_layout.addLayout(replace_to_form_layout)
        
        # 第五行：过滤选项label
        filter_options_label = QLabel(tr("ui.forward.filter_options"))
        filter_options_label.setStyleSheet("font-weight: bold;")
        dialog_layout.addWidget(filter_options_label)
        
        # 第六行：关键词过滤
        keyword_form_layout = QFormLayout()
        keyword_form_layout.setSpacing(10)
        keyword_form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        keyword_form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        
        keywords = channel_pair.get('keywords', [])
        keyword_input = QLineEdit(', '.join(keywords))
        keyword_input.setPlaceholderText(tr("ui.forward.keyword_placeholder"))
        keyword_form_layout.addRow(tr("ui.forward.keyword_filter"), keyword_input)
        dialog_layout.addLayout(keyword_form_layout)
        
        # 第七行：媒体类型
        media_types = channel_pair.get('media_types', [])
        
        # 媒体类型复选框布局（移除标签）
        media_types_layout = QHBoxLayout()
        
        text_check = QCheckBox(tr("ui.forward.media_types.text"))
        text_check.setChecked(self._is_media_type_in_list(MediaType.TEXT, media_types))
        media_types_layout.addWidget(text_check)
        
        photo_check = QCheckBox(tr("ui.forward.media_types.photo"))
        photo_check.setChecked(self._is_media_type_in_list(MediaType.PHOTO, media_types))
        media_types_layout.addWidget(photo_check)
        
        video_check = QCheckBox(tr("ui.forward.media_types.video"))
        video_check.setChecked(self._is_media_type_in_list(MediaType.VIDEO, media_types))
        media_types_layout.addWidget(video_check)
        
        document_check = QCheckBox(tr("ui.forward.media_types.document"))
        document_check.setChecked(self._is_media_type_in_list(MediaType.DOCUMENT, media_types))
        media_types_layout.addWidget(document_check)
        
        audio_check = QCheckBox(tr("ui.forward.media_types.audio"))
        audio_check.setChecked(self._is_media_type_in_list(MediaType.AUDIO, media_types))
        media_types_layout.addWidget(audio_check)
        
        animation_check = QCheckBox(tr("ui.forward.media_types.animation"))
        animation_check.setChecked(self._is_media_type_in_list(MediaType.ANIMATION, media_types))
        media_types_layout.addWidget(animation_check)
        
        media_types_layout.addStretch(1)  # 添加弹性空间，让复选框靠左对齐
        dialog_layout.addLayout(media_types_layout)
        
        # 第八行：转发参数
        forward_params_label = QLabel(tr("ui.forward.forward_params"))
        forward_params_label.setStyleSheet("font-weight: bold;")
        dialog_layout.addWidget(forward_params_label)
        
        # 转发参数复选框布局
        forward_params_layout = QGridLayout()
        forward_params_layout.setSpacing(10)
        
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
        enable_web_page_preview_value = to_bool(channel_pair.get('enable_web_page_preview', False))
        
        # 第一行：移除媒体说明、隐藏原作者
        remove_captions_check = QCheckBox(tr("ui.forward.options.remove_captions"))
        remove_captions_check.setChecked(remove_captions_value)
        forward_params_layout.addWidget(remove_captions_check, 0, 0)
        
        hide_author_check = QCheckBox(tr("ui.forward.options.hide_author"))
        hide_author_check.setChecked(hide_author_value)
        forward_params_layout.addWidget(hide_author_check, 0, 1)
        
        # 第二行：发送最终消息、排除含链接消息
        send_final_message_check = QCheckBox(tr("ui.forward.options.send_final_message"))
        send_final_message_check.setChecked(send_final_message_value)
        forward_params_layout.addWidget(send_final_message_check, 1, 0)
        
        exclude_links_check = QCheckBox(tr("ui.forward.options.exclude_links"))
        exclude_links_check.setChecked(exclude_links_value)
        forward_params_layout.addWidget(exclude_links_check, 1, 1)
        
        # 设置列的拉伸因子，使两列均匀分布
        forward_params_layout.setColumnStretch(0, 1)
        forward_params_layout.setColumnStretch(1, 1)
        
        dialog_layout.addLayout(forward_params_layout)
        
        # 第九行：最终消息HTML文件路径
        html_file_form_layout = QFormLayout()
        html_file_form_layout.setSpacing(10)
        html_file_form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        html_file_form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        
        html_file_layout = QHBoxLayout()
        html_file_input = QLineEdit(channel_pair.get('final_message_html_file', ''))
        html_file_input.setPlaceholderText(tr("ui.forward.final_message.html_file_placeholder"))
        html_file_layout.addWidget(html_file_input)
        
        html_file_browse_btn = QPushButton(tr("ui.forward.final_message.browse"))
        html_file_browse_btn.setMinimumWidth(90)
        html_file_layout.addWidget(html_file_browse_btn)
        
        # 添加网页预览复选框
        enable_web_page_preview_check = QCheckBox(tr("ui.forward.options.enable_web_page_preview"))
        enable_web_page_preview_check.setChecked(enable_web_page_preview_value)  # 使用转换后的布尔值
        html_file_layout.addWidget(enable_web_page_preview_check)
        
        html_file_form_layout.addRow(tr("ui.forward.final_message.html_file"), html_file_layout)
        dialog_layout.addLayout(html_file_form_layout)
        
        # 连接浏览按钮
        def browse_html_file():
            file_path, _ = QFileDialog.getOpenFileName(
                edit_dialog,
                tr("ui.forward.final_message.html_file"),
                "",
                tr("ui.forward.file_types.html")
            )
            if file_path:
                html_file_input.setText(file_path)
        
        html_file_browse_btn.clicked.connect(browse_html_file)
        
        # 第九行：起始ID，结束ID
        id_and_buttons_layout = QHBoxLayout()
        
        # 起始ID和结束ID
        id_and_buttons_layout.addWidget(QLabel(tr("ui.forward.message_range.start_id")))
        start_id_input = QSpinBox()
        start_id_input.setRange(0, 999999999)
        start_id_input.setValue(channel_pair.get('start_id', 0))
        start_id_input.setSpecialValueText(tr("ui.forward.message_range.earliest_message"))
        
        # 结束ID
        end_id_input = QSpinBox()
        end_id_input.setRange(0, 999999999)
        end_id_input.setValue(channel_pair.get('end_id', 0))
        end_id_input.setSpecialValueText(tr("ui.forward.message_range.latest_message"))
        
        id_and_buttons_layout.addWidget(start_id_input)
        id_and_buttons_layout.addWidget(QLabel(tr("ui.forward.message_range.end_id")))
        id_and_buttons_layout.addWidget(end_id_input)
        id_and_buttons_layout.addStretch(1)
        
        dialog_layout.addLayout(id_and_buttons_layout)
        
        # 设置滚动区域的内容
        scroll_area.setWidget(scroll_content_widget)
        main_dialog_layout.addWidget(scroll_area)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        save_button = QPushButton(tr("ui.forward.edit_dialog.save"))
        cancel_button = QPushButton(tr("ui.forward.edit_dialog.cancel"))
        
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
                    raise ValueError(tr("ui.forward.messages.source_required"))
                if not new_targets:
                    raise ValueError(tr("ui.forward.messages.target_required"))
                
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
                    raise ValueError(tr("ui.forward.messages.select_media_type"))
                
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
                    'enable_web_page_preview': enable_web_page_preview_check.isChecked(),
                    'text_filter': text_filter,
                    'keywords': keywords,
                    'exclude_links': exclude_links_check.isChecked()
                }
                
                # 更新列表项和数据
                self._update_channel_pair(row, updated_pair)
                
            except ValueError as e:
                QMessageBox.warning(self, tr("ui.forward.messages.input_error"), str(e))
    
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
                QMessageBox.information(self, tr("ui.forward.messages.status_updated"), tr("ui.forward.messages.update_success"))
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
        status_text = tr("ui.forward.context_menu.enable") if new_enabled else tr("ui.forward.context_menu.disable")
        source_channel = channel_pair.get('source_channel', '未知频道')
        if new_enabled:
            message = tr("ui.forward.messages.pair_enabled").format(channel=source_channel)
        else:
            message = tr("ui.forward.messages.pair_disabled").format(channel=source_channel)
        QMessageBox.information(self, tr("ui.forward.messages.status_updated"), message)
        
        logger.debug(f"频道对 {source_channel} 状态切换为: {'启用' if new_enabled else '禁用'}")
        
        # 更新状态表格
        self._update_status_table()
    
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
            media_types_str.append(tr("ui.forward.media_types.text"))
        if self._is_media_type_in_list(MediaType.PHOTO, media_types):
            media_types_str.append(tr("ui.forward.media_types.photo"))
        if self._is_media_type_in_list(MediaType.VIDEO, media_types):
            media_types_str.append(tr("ui.forward.media_types.video"))
        if self._is_media_type_in_list(MediaType.DOCUMENT, media_types):
            media_types_str.append(tr("ui.forward.media_types.document"))
        if self._is_media_type_in_list(MediaType.AUDIO, media_types):
            media_types_str.append(tr("ui.forward.media_types.audio"))
        if self._is_media_type_in_list(MediaType.ANIMATION, media_types):
            media_types_str.append(tr("ui.forward.media_types.animation"))
        
        # 构建ID范围显示文本
        start_id = channel_pair.get('start_id', 0)
        end_id = channel_pair.get('end_id', 0)
        id_range_str = ""
        
        if start_id > 0 or end_id > 0:
            if start_id > 0 and end_id > 0:
                id_range_str = tr("ui.forward.display.id_range_both").format(start=start_id, end=end_id)
            elif start_id > 0:
                id_range_str = tr("ui.forward.display.id_range_start").format(start=start_id)
            else:
                id_range_str = tr("ui.forward.display.id_range_end").format(end=end_id)
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
                text_filter_str = f" - {tr('ui.forward.messages.text_replacements')}: {', '.join(replacements)}"
        
        # 构建关键词显示文本
        keywords = channel_pair.get('keywords', [])
        keywords_str = ""
        if keywords:
            keywords_str = f" - {tr('ui.forward.messages.keywords')}: {', '.join(keywords)}"
        
        # 构建转发选项显示文本
        options_str = []
        if channel_pair.get('remove_captions', False):
            options_str.append(tr("ui.forward.messages.option_remove_captions"))
        if channel_pair.get('hide_author', False):
            options_str.append(tr("ui.forward.messages.option_hide_author"))
        if channel_pair.get('send_final_message', False):
            options_str.append(tr("ui.forward.messages.option_send_final_message"))
        if channel_pair.get('exclude_links', False):
            options_str.append(tr("ui.forward.messages.option_exclude_links"))
        
        options_display = ""
        if options_str:
            options_display = f" - {tr('ui.forward.display.options')}: {', '.join(options_str)}"
        
        # 构建基础显示文本
        display_text = f"{channel_pair['source_channel']} → {', '.join(channel_pair['target_channels'])} ({tr('ui.forward.display.media', types=', '.join(media_types_str))}){id_range_str}{text_filter_str}{keywords_str}{options_display}"
        
        # 添加启用/禁用状态标识
        is_enabled = channel_pair.get('enabled', True)
        if not is_enabled:
            display_text = f"[{tr('ui.forward.display.disabled')}] {display_text}"
        
        # 更新列表项文本
        item.setText(display_text)
    
    def _update_status_table_forwarding_status(self, status):
        """更新状态表格中所有行的转发状态
        
        Args:
            status: 新的状态文本（如"转发中"、"停止中"、"待转发"等）
        """
        for row in range(self.status_table.rowCount()):
            if self.status_table.item(row, 3):
                self.status_table.item(row, 3).setText(status)
        
        # 更新内部数据
        for key in self.status_table_data:
            self.status_table_data[key]['status'] = status
        
        logger.debug(f"已更新状态表格转发状态为: {status}")
    
    def _on_message_forwarded(self, message_id, target_info):
        """处理单条消息转发信号
        
        Args:
            message_id: 消息ID
            target_info: 目标频道信息（可能包含ID信息）
        """
        try:
            # 直接传递完整的target_info给匹配方法，让它内部处理ID提取和匹配
            # 不再提前提取频道名称，因为这会丢失ID信息
            self._increment_forwarded_count_for_target(target_info)
            
            # 添加转发成功的日志记录
            target_channel_name = self._extract_channel_name_from_info(target_info)
            self._log_message_forward_success(message_id, tr("ui.forward.messages.single_message"), f"→ {target_channel_name}")
            
            logger.debug(f"处理单条消息转发信号: msg_id={message_id}, target_info={target_info}")
        except Exception as e:
            logger.error(f"处理单条消息转发信号时出错: {e}")
    
    def _on_media_group_forwarded(self, message_ids, target_info, count, target_id_str):
        """处理媒体组转发完成信号（PyQt6信号）
        
        Args:
            message_ids: 消息ID列表
            target_info: 目标频道信息
            count: 消息数量
            target_id_str: 目标频道ID字符串
        """
        try:
            logger.debug(f"处理媒体组转发信号: {count}条消息, target={target_info}, target_id={target_id_str}")
            
            # 将字符串ID转换为整数
            target_id = int(target_id_str)
            
            # 添加媒体组转发成功的日志记录
            try:
                if isinstance(message_ids, list) and len(message_ids) > 1:
                    # 多个消息的媒体组
                    message_range = f"{message_ids[0]}-{message_ids[-1]}"
                    target_channel_name = self._extract_channel_name_from_info(target_info)
                    self._log_message_forward_success(message_range, tr("ui.forward.messages.media_group_message"), f"→ {target_channel_name}")
                elif isinstance(message_ids, list) and len(message_ids) == 1:
                    # 单个消息
                    target_channel_name = self._extract_channel_name_from_info(target_info)
                    self._log_message_forward_success(message_ids[0], tr("ui.forward.messages.single_message"), f"→ {target_channel_name}")
                else:
                    # 其他情况
                    target_channel_name = self._extract_channel_name_from_info(target_info)
                    self._log_message_forward_success(str(message_ids), tr("ui.forward.messages.media_group_message"), f"→ {target_channel_name}")
            except Exception as log_error:
                logger.debug(f"添加媒体组转发日志失败: {log_error}")
            
            # 使用频道ID进行精确匹配
            if hasattr(self, 'channel_id_to_table_row') and target_id in self.channel_id_to_table_row:
                row = self.channel_id_to_table_row[target_id]
                source_channel = self.status_table.item(row, 0).text() if self.status_table.item(row, 0) else ""
                target_channel = self.status_table.item(row, 1).text() if self.status_table.item(row, 1) else ""
                
                logger.debug(f"✅ 通过频道ID {target_id} 精确匹配到行 {row}: {source_channel} -> {target_channel}")
                self._update_count_and_ui(source_channel, target_channel, row, count)
                return
            else:
                logger.warning(f"❌ 频道ID {target_id} 在映射表中未找到")
            
            # 回退到名称匹配
            target_channel = self._extract_channel_name_from_info(target_info)
            self._increment_forwarded_count_for_target(target_channel, count)
            
            logger.debug(f"处理媒体组转发信号: {count}条消息, target={target_channel}")
            
        except Exception as e:
            logger.error(f"处理媒体组转发信号失败: {e}")

    def _on_media_group_forwarded_event(self, message_ids, target_info, count, target_id_str):
        """处理媒体组转发完成事件（事件监听器）
        
        Args:
            message_ids: 消息ID列表
            target_info: 目标频道信息
            count: 消息数量
            target_id_str: 目标频道ID字符串
        """
        try:
            # 将字符串ID转换为整数
            target_id = int(target_id_str)
            
            # 使用频道ID进行精确匹配
            if hasattr(self, 'channel_id_to_table_row') and target_id in self.channel_id_to_table_row:
                row = self.channel_id_to_table_row[target_id]
                source_channel = self.status_table.item(row, 0).text() if self.status_table.item(row, 0) else ""
                target_channel = self.status_table.item(row, 1).text() if self.status_table.item(row, 1) else ""
                
                logger.debug(f"✅ 通过频道ID {target_id} 精确匹配到行 {row}: {source_channel} -> {target_channel}")
                self._update_count_and_ui(source_channel, target_channel, row, count)
                return
            
            # 回退到名称匹配
            target_channel = self._extract_channel_name_from_info(target_info)
            self._increment_forwarded_count_for_target(target_channel, count)
            
            logger.debug(f"处理媒体组转发事件: {count}条消息, target={target_channel}")
            
        except Exception as e:
            logger.error(f"处理媒体组转发事件失败: {e}")
    
    def _on_message_forwarded_event(self, message_id, target_info):
        """处理单条消息转发完成事件（事件监听器）
        
        Args:
            message_id: 消息ID  
            target_info: 目标频道信息（可能包含ID信息）
        """
        try:
            # 直接传递完整的target_info给匹配方法，让它内部处理ID提取和匹配
            # 不再提前提取频道名称，因为这会丢失ID信息
            self._increment_forwarded_count_for_target(target_info, 1)
            
            logger.debug(f"处理单条消息转发事件: {message_id}, target_info={target_info}")
            
        except Exception as e:
            logger.error(f"处理单条消息转发事件失败: {e}")
    
    def _extract_channel_name_from_info(self, target_info):
        """从目标频道信息中提取频道名称
        
        Args:
            target_info: 目标频道信息字符串
            
        Returns:
            str: 频道名称
        """
        try:
            # target_info可能的格式：
            # "频道名 (ID: -1002382449514)"
            # "@channel_username"
            # "频道名"
            
            if target_info.startswith('@'):
                # 如果以@开头，直接返回
                return target_info
            elif ' (ID: ' in target_info:
                # 如果包含ID信息，提取频道名部分
                return target_info.split(' (ID: ')[0]
            else:
                # 其他情况直接返回
                return target_info
                
        except Exception as e:
            logger.error(f"提取频道名称时出错: {e}")
            return target_info
    
    def _increment_forwarded_count_for_target(self, target_channel, increment=1):
        """为指定目标频道增加已转发消息数
        
        Args:
            target_channel: 目标频道名称（显示名称）
            increment: 增加的数量，默认为1
        """
        try:
            # 方法1: 通过转发器的频道解析器获取频道ID
            target_channel_id = None
            target_channel_identifier = None
            
            if hasattr(self, 'forwarder') and self.forwarder and hasattr(self.forwarder, 'channel_resolver'):
                try:
                    # 尝试通过频道名称获取频道信息
                    async def get_channel_info():
                        try:
                            channel_info = await self.forwarder.channel_resolver.get_entity(target_channel)
                            if channel_info:
                                return channel_info.id
                        except Exception as e:
                            logger.debug(f"通过名称获取频道信息失败: {e}")
                            return None
                    
                    # 暂时跳过异步调用，使用其他方法
                    pass
                except Exception as e:
                    logger.debug(f"通过转发器获取频道ID失败: {e}")
            
            # 方法2: 从target_channel中提取频道ID（如果包含ID信息）
            if "ID: " in target_channel:
                try:
                    import re
                    match = re.search(r'ID: (-?\d+)', target_channel)
                    if match:
                        target_channel_id = int(match.group(1))
                        logger.debug(f"从target_channel提取到频道ID: {target_channel_id}")
                except Exception as e:
                    logger.debug(f"从target_channel提取ID失败: {e}")
            
            # 方法3: 如果有频道ID映射，尝试使用
            if target_channel_id and hasattr(self, 'channel_id_to_table_row'):
                if target_channel_id in self.channel_id_to_table_row:
                    row = self.channel_id_to_table_row[target_channel_id]
                    logger.debug(f"✅ 通过频道ID {target_channel_id} 匹配到表格行 {row}")
                    
                    # 获取源频道和目标频道标识符
                    source_channel = self.status_table.item(row, 0).text() if self.status_table.item(row, 0) else ""
                    target_channel_identifier = self.status_table.item(row, 1).text() if self.status_table.item(row, 1) else ""
                    
                    # 增加计数并更新UI
                    self._update_count_and_ui(source_channel, target_channel_identifier, row, increment)
                    return
            
            # 方法4: 智能反向查找 - 通过频道映射找到对应的表格行
            if hasattr(self, 'channel_id_to_table_row') and target_channel_id is None:
                # 尝试通过状态表格中的频道标识符反向查找
                logger.debug(f"尝试反向查找目标频道: '{target_channel}'")
                
                # 遍历所有已建立的频道ID映射
                for channel_id, table_row in self.channel_id_to_table_row.items():
                    # 获取表格中对应行的目标频道标识符
                    if table_row < self.status_table.rowCount():
                        target_item = self.status_table.item(table_row, 1)
                        if target_item:
                            table_target_identifier = target_item.text()
                            
                            # 尝试通过转发器解析频道名称
                            if (hasattr(self, 'forwarder') and self.forwarder and 
                                hasattr(self.forwarder, 'channel_resolver')):
                                try:
                                    # 检查这个频道ID对应的频道名称是否匹配
                                    # 这里我们已经知道channel_id对应table_row，且从日志中可以看出这个匹配关系是正确的
                                    logger.debug(f"检查频道ID {channel_id} 对应的表格行 {table_row}")
                                    
                                    # 由于我们无法异步获取频道名称，我们使用其他匹配策略
                                    # 如果只有一个状态表格行，且target_channel不是标识符格式，很可能就是匹配的
                                    if (self.status_table.rowCount() == 1 and 
                                        not target_channel.startswith('@') and 
                                        not target_channel.startswith('+') and 
                                        len(target_channel) > 3):  # 频道名称通常比较长
                                        
                                        logger.debug(f"✅ 通过唯一行匹配成功: {table_target_identifier} ↔ {target_channel}")
                                        source_channel = self.status_table.item(table_row, 0).text() if self.status_table.item(table_row, 0) else ""
                                        self._update_count_and_ui(source_channel, table_target_identifier, table_row, increment)
                                        return
                                        
                                except Exception as e:
                                    logger.debug(f"频道名称匹配检查失败: {e}")
            
            # 方法5: 直接名称匹配（原有逻辑）
            for row in range(self.status_table.rowCount()):
                if (self.status_table.item(row, 1) and 
                    self.status_table.item(row, 1).text() == target_channel):
                    
                    source_channel = self.status_table.item(row, 0).text() if self.status_table.item(row, 0) else ""
                    target_channel_identifier = target_channel
                    
                    logger.debug(f"✅ 通过直接名称匹配成功: {target_channel}")
                    self._update_count_and_ui(source_channel, target_channel_identifier, row, increment)
                    return
            
            # 方法6: 模糊匹配策略
            logger.debug(f"尝试模糊匹配目标频道: '{target_channel}'")
            
            for row in range(self.status_table.rowCount()):
                target_item = self.status_table.item(row, 1)
                if not target_item:
                    continue
                
                table_channel = target_item.text()
                
                # 策略1: 移除@符号后匹配
                table_clean = table_channel.lstrip('@+')
                target_clean = target_channel.lstrip('@+')
                
                if table_clean == target_clean:
                    logger.debug(f"✅ 通过移除符号匹配成功: {table_channel} ↔ {target_channel}")
                    source_channel = self.status_table.item(row, 0).text() if self.status_table.item(row, 0) else ""
                    self._update_count_and_ui(source_channel, table_channel, row, increment)
                    return
                
                # 策略2: 包含关系匹配
                if table_clean in target_clean or target_clean in table_clean:
                    logger.debug(f"✅ 通过包含关系匹配成功: {table_channel} ↔ {target_channel}")
                    source_channel = self.status_table.item(row, 0).text() if self.status_table.item(row, 0) else ""
                    self._update_count_and_ui(source_channel, table_channel, row, increment)
                    return
            
            # 所有匹配策略都失败，提供更详细的调试信息
            logger.warning(f"未找到目标频道的状态表格行: {target_channel}")
            logger.debug("当前状态表格详细信息:")
            for row in range(self.status_table.rowCount()):
                source_item = self.status_table.item(row, 0)
                target_item = self.status_table.item(row, 1)
                source_text = source_item.text() if source_item else "None"
                target_text = target_item.text() if target_item else "None"
                logger.debug(f"  行{row}: 源='{source_text}' 目标='{target_text}'")
            
            if hasattr(self, 'channel_id_to_table_row'):
                logger.debug(f"频道ID映射: {self.channel_id_to_table_row}")
            
            logger.debug(f"尝试匹配的目标频道: '{target_channel}' (长度: {len(target_channel)})")
            
        except Exception as e:
            logger.error(f"增加转发计数时发生错误: {e}")
            import traceback
            logger.debug(f"错误详情:\n{traceback.format_exc()}")

    def _connect_app_signals(self):
        """连接应用级别的信号到UI更新"""
        try:
            # 获取应用实例
            app = None
            if hasattr(self.forwarder, 'app') and self.forwarder.app:
                app = self.forwarder.app
            elif hasattr(self, 'parent') and self.parent() and hasattr(self.parent(), 'app'):
                app = self.parent().app
            
            if not app:
                logger.warning("无法获取应用实例，无法连接应用级别的信号")
                return
                
            # 连接应用的转发信号到UI处理方法
            if hasattr(app, 'message_forwarded'):
                app.message_forwarded.connect(self._on_message_forwarded)
                logger.debug("已连接应用的message_forwarded信号")
                
            if hasattr(app, 'media_group_forwarded'):
                app.media_group_forwarded.connect(self._on_media_group_forwarded)
                logger.debug("已连接应用的media_group_forwarded信号")
                
            if hasattr(app, 'message_filtered'):
                app.message_filtered.connect(self._on_message_filtered)
                logger.debug("已连接应用的message_filtered信号")
                
            if hasattr(app, 'collection_started'):
                app.collection_started.connect(self._on_collection_started)
                logger.debug("已连接应用的collection_started信号")
                
            if hasattr(app, 'collection_progress'):
                app.collection_progress.connect(self._on_collection_progress)
                logger.debug("已连接应用的collection_progress信号")
                
            if hasattr(app, 'collection_completed'):
                app.collection_completed.connect(self._on_collection_completed)
                logger.debug("已连接应用的collection_completed信号")
                
            if hasattr(app, 'collection_error'):
                app.collection_error.connect(self._on_collection_error)
                logger.debug("已连接应用的collection_error信号")
                
            if hasattr(app, 'text_replacement_applied'):
                app.text_replacement_applied.connect(self._on_text_replacement_applied)
                logger.debug("已连接应用的text_replacement_applied信号")
                
            logger.debug("应用级别信号连接成功")
            
        except Exception as e:
            logger.error(f"连接应用级别信号时出错: {e}")
            import traceback
            logger.debug(f"错误详情:\n{traceback.format_exc()}")
    
    def _on_message_filtered(self, message_id, message_type, filter_reason):
        """处理消息过滤信号
        
        Args:
            message_id: 消息ID或范围（字符串）
            message_type: 消息类型（tr("ui.forward.messages.single_message")或tr("ui.forward.messages.media_group_message")）
            filter_reason: 过滤原因
        """
        try:
            # 添加过滤日志到UI显示区域
            if hasattr(self, 'log_display'):
                self._log_message_filtered(message_id, message_type, filter_reason)
                
            logger.debug(f"处理消息过滤信号: {message_type}({message_id}) 过滤原因: {filter_reason}")
        except Exception as e:
            logger.error(f"处理消息过滤信号时出错: {e}")

    def _update_count_and_ui(self, source_channel, target_channel, row, increment):
        """更新计数和UI显示"""
        try:
            # 获取当前计数
            key = (source_channel, target_channel)
            
            # 获取历史记录中的已转发消息数（基础值）
            base_forwarded_count = self.forwarded_message_counts.get(key, 0)
            
            # 获取当前会话的转发计数（从status_table_data中获取，但需要减去基础值以避免重复计算）
            current_session_count = self.status_table_data.get(key, {}).get('forwarded', base_forwarded_count) - base_forwarded_count
            
            # 新的会话计数
            new_session_count = current_session_count + increment
            
            # 总的已转发消息数 = 历史记录 + 当前会话
            total_forwarded_count = base_forwarded_count + new_session_count
            
            total_count = self.total_message_counts.get(key, -1)  # 从total_message_counts获取总消息数
            
            # 更新数据
            if key in self.status_table_data:
                self.status_table_data[key]['forwarded'] = total_forwarded_count
            else:
                # 如果key不存在，创建新的记录
                self.status_table_data[key] = {
                    'forwarded': total_forwarded_count,
                    'total': total_count,
                    'status': tr("ui.forward.status.running")
                }
            
            # 查找对应的频道对配置，判断是否应该显示"计算中..."
            should_show_calculating = False
            for pair in self.channel_pairs:
                if (pair.get('source_channel') == source_channel and 
                    target_channel in pair.get('target_channels', [])):
                    start_id = pair.get('start_id', 0)
                    end_id = pair.get('end_id', 0)
                    if start_id > 0 and end_id == 0:
                        should_show_calculating = True
                    break
            
            # 更新UI显示，正确处理total_count为-1的情况
            if total_count == -1:
                if should_show_calculating:
                    count_text = f"{total_forwarded_count}/" + tr("ui.forward.display.calculating")
                else:
                    count_text = f"{total_forwarded_count}/--"
            elif total_count > 0:
                count_text = f"{total_forwarded_count}/{total_count}"
            else:
                count_text = f"{total_forwarded_count}/0"
                
            if self.status_table.item(row, 2):
                self.status_table.item(row, 2).setText(count_text)
            
            logger.debug(f"✅ 已更新转发计数: {target_channel} +{increment} -> {total_forwarded_count} (历史: {base_forwarded_count}, 本次: {new_session_count}, 总计: {total_count if total_count != -1 else (tr('ui.forward.display.calculating_short') if should_show_calculating else '--')})")
            
        except Exception as e:
            logger.error(f"更新计数和UI时发生错误: {e}")
    
    # ===== 日志显示相关方法 =====
    
    def _add_log_message(self, message, color="#333333"):
        """添加普通日志消息
        
        Args:
            message: 日志消息内容
            color: 文字颜色，默认为深灰色
        """
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            html_message = f'<span style="color: {color};">[{timestamp}] {message}</span>'
            
            # 移动到文档末尾并添加消息
            cursor = self.log_display.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.log_display.setTextCursor(cursor)
            self.log_display.insertHtml(html_message + "<br>")
            
            # 自动滚动到底部
            cursor = self.log_display.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.log_display.setTextCursor(cursor)
            
        except Exception as e:
            logger.error(f"添加日志消息失败: {e}")
    
    def _add_success_log_message(self, message):
        """添加成功日志消息（绿色）
        
        Args:
            message: 成功消息内容
        """
        self._add_log_message(message, color="#28a745")
    
    def _add_error_log_message(self, message):
        """添加错误日志消息（红色）
        
        Args:
            message: 错误消息内容
        """
        self._add_log_message(message, color="#dc3545")
    
    def _add_warning_log_message(self, message):
        """添加警告日志消息（橙色）
        
        Args:
            message: 警告消息内容
        """
        self._add_log_message(message, color="#fd7e14")
    
    def _add_filter_log_message(self, message):
        """添加过滤日志消息（蓝色）
        
        Args:
            message: 过滤消息内容
        """
        self._add_log_message(message, color="#007bff")
    
    def _add_info_log_message(self, message):
        """添加信息日志消息（青色）
        
        Args:
            message: 信息消息内容
        """
        self._add_log_message(message, color="#17a2b8")
    
    def _clear_log(self):
        """清空日志显示区域"""
        try:
            self.log_display.clear()
            self._add_log_message(tr("ui.forward.log.log_cleared"), color="#6c757d")
        except Exception as e:
            logger.error(f"清空日志失败: {e}")
    
    def _log_message_collected(self, count, total=None):
        """记录消息收集过程
        
        Args:
            count: 已收集的消息数量
            total: 总消息数量（可选）
        """
        if total is not None:
            message = tr("ui.forward.messages.collecting_messages", count=count, total=total)
        else:
            message = tr("ui.forward.log.collected_count", count=count)
        self._add_info_log_message(message)
    
    def _log_message_forward_success(self, message_id, message_type=None, additional_info=""):
        """记录消息转发成功
        
        Args:
            message_id: 消息ID或消息ID范围
            message_type: 消息类型（tr("ui.forward.messages.single_message")或tr("ui.forward.messages.media_group_message")）
            additional_info: 附加信息（如文本替换、移除媒体说明等）
        """
        if message_type is None:
            message_type = tr("ui.forward.messages.single_message")
        message = f"{message_type}（{message_id}）{tr('ui.forward.log.forward_success')}"
        if additional_info:
            message += f"：{additional_info}"
        self._add_success_log_message(message)
    
    def _log_message_forward_failed(self, message_id, message_type=None, error_msg="", is_rate_limit=False):
        """记录消息转发失败
        
        Args:
            message_id: 消息ID或消息ID范围
            message_type: 消息类型（"单个消息"或"媒体组消息"）
            error_msg: 错误消息
            is_rate_limit: 是否为API限流错误
        """
        if message_type is None:
            message_type = tr("ui.forward.messages.single_message")
        message = f"{message_type}（{message_id}）{tr('ui.forward.log.forward_failed')}"
        if error_msg:
            message += f"：{error_msg}"
        
        if is_rate_limit:
            # API限流错误用红色高亮显示
            self._add_error_log_message(tr("ui.forward.log.api_flood_limit", message=message))
        else:
            self._add_error_log_message(message)
    
    def _log_message_filtered(self, message_id, message_type=None, filter_reason=""):
        """记录消息过滤
        
        Args:
            message_id: 消息ID或消息ID范围
            message_type: 消息类型（tr("ui.forward.messages.single_message")或tr("ui.forward.messages.media_group_message")）
            filter_reason: 过滤原因
        """
        if message_type is None:
            message_type = tr("ui.forward.messages.single_message")
        message = f"{message_type}（{message_id}）{tr('ui.forward.log.filtered')}"
        if filter_reason:
            message += f"：{filter_reason}"
        self._add_filter_log_message(message)
    
    def _log_collection_start(self, source_channel):
        """记录开始收集消息
        
        Args:
            source_channel: 源频道
        """
        self._add_info_log_message(tr("ui.forward.log.start_collecting_from", source_channel=source_channel))
    
    def _log_collection_complete(self, source_channel, total_count):
        """记录消息收集完成
        
        Args:
            source_channel: 源频道
            total_count: 收集到的消息总数
        """
        self._add_info_log_message(tr("ui.forward.log.collect_completed", source_channel=source_channel, total_count=total_count))
    
    def _log_forward_start(self, source_channel, target_channels):
        """记录开始转发
        
        Args:
            source_channel: 源频道
            target_channels: 目标频道列表
        """
        targets_str = ", ".join(target_channels) if isinstance(target_channels, list) else str(target_channels)
        self._add_info_log_message(tr("ui.forward.log.start_forwarding", source_channel=source_channel, targets_str=targets_str))
    
    def _log_forward_complete(self, source_channel, target_channels):
        """记录转发完成
        
        Args:
            source_channel: 源频道
            target_channels: 目标频道列表
        """
        targets_str = ", ".join(target_channels) if isinstance(target_channels, list) else str(target_channels)
        self._add_success_log_message(tr("ui.forward.log.forward_completed", source_channel=source_channel, targets_str=targets_str))
    
    def _on_collection_started(self, total_count):
        """处理消息收集开始信号
        
        Args:
            total_count: 总消息数
        """
        try:
            if hasattr(self, 'log_display'):
                self._add_info_log_message(tr("ui.forward.log.start_collecting_messages", total_count=total_count))
            logger.debug(f"处理消息收集开始信号: 总数 {total_count}")
        except Exception as e:
            logger.error(f"处理消息收集开始信号时出错: {e}")
    
    def _on_collection_progress(self, current_count, total_count):
        """处理消息收集进度信号
        
        Args:
            current_count: 当前已收集数量
            total_count: 总数量
        """
        try:
            if hasattr(self, 'log_display'):
                # 每10条消息记录一次进度，避免日志过多
                if current_count % 10 == 0 or current_count == total_count:
                    self._log_message_collected(current_count, total_count)
            logger.debug(f"处理消息收集进度信号: {current_count}/{total_count}")
        except Exception as e:
            logger.error(f"处理消息收集进度信号时出错: {e}")
    
    def _on_collection_completed(self, collected_count, total_count):
        """处理消息收集完成信号
        
        Args:
            collected_count: 已收集数量
            total_count: 总数量
        """
        try:
            if hasattr(self, 'log_display'):
                success_rate = (collected_count / total_count * 100) if total_count > 0 else 0
                self._add_success_log_message(tr("ui.forward.log.collect_finished", collected_count=collected_count, total_count=total_count, success_rate=success_rate))
            logger.debug(f"处理消息收集完成信号: {collected_count}/{total_count}")
        except Exception as e:
            logger.error(f"处理消息收集完成信号时出错: {e}")
    
    def _on_collection_error(self, error_message):
        """处理消息收集错误信号
        
        Args:
            error_message: 错误信息
        """
        try:
            if hasattr(self, 'log_display'):
                self._add_error_log_message(tr("ui.forward.log.collect_error", error_message=error_message))
            logger.debug(f"处理消息收集错误信号: {error_message}")
        except Exception as e:
            logger.error(f"处理消息收集错误信号时出错: {e}")
    
    def _on_text_replacement_applied(self, message_desc, original_text, replaced_text):
        """处理文本替换信号
        
        Args:
            message_desc: 消息描述（消息ID或描述信息）
            original_text: 原始文本
            replaced_text: 替换后文本
        """
        try:
            if hasattr(self, 'log_display'):
                # 简化文本显示，避免过长
                original_short = original_text[:20] + "..." if len(original_text) > 20 else original_text
                replaced_short = replaced_text[:20] + "..." if len(replaced_text) > 20 else replaced_text
                self._add_info_log_message(tr("ui.forward.log.text_replace", message_desc=message_desc, original_short=original_short, replaced_short=replaced_short))
            logger.debug(f"处理文本替换信号: {message_desc}, '{original_text}' -> '{replaced_text}'")
        except Exception as e:
            logger.error(f"处理文本替换信号时出错: {e}")