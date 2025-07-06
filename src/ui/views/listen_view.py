"""
TG-Manager 消息监听界面
实现对Telegram频道消息的实时监听功能
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QCheckBox, QPushButton,
    QGroupBox, QScrollArea, QComboBox,
    QListWidget, QListWidgetItem, QMessageBox,
    QTextEdit, QSplitter, QTabWidget, QDateTimeEdit,
    QSizePolicy, QDoubleSpinBox, QDialog, QMenu, QSpinBox
)
from PySide6.QtCore import Qt, Signal, Slot, QDateTime, QPoint
from PySide6.QtGui import QIcon, QTextCursor, QCursor
from datetime import datetime

from src.utils.logger import get_logger
from src.utils.ui_config_models import UIMonitorConfig, UIMonitorChannelPair, MediaType
from src.utils.translation_manager import get_translation_manager, tr

# 添加性能监控视图导入
from src.ui.views.performance_monitor_view import PerformanceMonitorView

logger = get_logger()


class ListenView(QWidget):
    """监听界面，提供对Telegram频道消息的实时监听功能"""
    
    # 监听开始信号
    listen_started = Signal(dict)
    # 配置保存信号
    config_saved = Signal(dict)
    
    def __init__(self, config=None, parent=None):
        """初始化监听界面
        
        Args:
            config: 配置对象
            parent: 父窗口部件
        """
        super().__init__(parent)
        
        self.config = config or {}
        
        # 初始化翻译管理器
        self.translation_manager = get_translation_manager()
        
        # 存储需要翻译的UI组件
        self.translatable_widgets = {
            'labels': {},
            'buttons': {},
            'checkboxes': {},
            'inputs': {},
            'tabs': {},
            'groups': {}
        }
        
        # 设置布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(8)  # 增加主布局的垂直间距
        self.main_layout.setContentsMargins(8, 8, 8, 8)  # 增加主布局边距
        self.setLayout(self.main_layout)
        
        # 创建配置标签页
        self.config_tabs = QTabWidget()
        # 移除高度限制，让配置区域可以自由扩展
        self.config_tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.main_layout.addWidget(self.config_tabs, 1)  # 添加伸展因子，让标签页占据主要空间
        
        # 创建配置标签页
        self._create_config_panel()
        
        # 创建底部操作按钮
        self._create_action_buttons()
        
        # 连接信号
        self._connect_signals()
        
        # 监听配置列表
        self.listen_configs = []
        
        # 连接语言变更信号
        self.translation_manager.language_changed.connect(self._update_translations)
        
        # 界面组件创建完成后再加载配置
        if self.config:
            self.load_config(self.config)
        
        # 初始化翻译更新
        self._update_translations()
        
        logger.info("监听界面初始化完成")
    
    def _create_config_panel(self):
        """创建配置标签页"""
        # 监听配置标签页
        self.config_tab = QWidget()
        # 创建主布局，只包含滚动区域
        main_config_layout = QVBoxLayout(self.config_tab)
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
        
        # 创建顶部表单面板 - 源频道和目标频道使用简单的表单布局
        basic_form_layout = QFormLayout()
        basic_form_layout.setSpacing(10)  # 增加表单项间距
        basic_form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)  # 标签右对齐
        basic_form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)  # 字段可扩展
        
        # 源频道
        self.source_channel_input = QLineEdit()
        self.source_channel_input.setPlaceholderText(tr("ui.listen.channel_config.source_placeholder"))
        self.source_channel_label = QLabel(tr("ui.listen.channel_config.source_channel"))
        self.translatable_widgets['labels']['source_channel'] = self.source_channel_label
        self.translatable_widgets['inputs']['source_channel'] = self.source_channel_input
        basic_form_layout.addRow(self.source_channel_label, self.source_channel_input)
        
        # 目标频道
        self.target_channel_input = QLineEdit()
        self.target_channel_input.setPlaceholderText(tr("ui.listen.channel_config.target_placeholder"))
        self.target_channel_label = QLabel(tr("ui.listen.channel_config.target_channels"))
        self.translatable_widgets['labels']['target_channels'] = self.target_channel_label
        self.translatable_widgets['inputs']['target_channels'] = self.target_channel_input
        basic_form_layout.addRow(self.target_channel_label, self.target_channel_input)
        
        # 将基本表单添加到配置布局
        config_layout.addLayout(basic_form_layout)
        
        # 创建文本替换规则表单
        form_layout = QFormLayout()
        form_layout.setSpacing(10)  # 增加表单项间距
        form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)  # 标签右对齐
        form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)  # 字段可扩展
        
        # 文本替换规则
        self.original_text_input = QLineEdit()
        self.original_text_input.setPlaceholderText(tr("ui.listen.channel_config.original_text"))
        self.original_text_label = QLabel(tr("ui.listen.channel_config.text_replacement"))
        self.translatable_widgets['labels']['text_replacement'] = self.original_text_label
        self.translatable_widgets['inputs']['original_text'] = self.original_text_input
        form_layout.addRow(self.original_text_label, self.original_text_input)
        
        self.target_text_input = QLineEdit()
        self.target_text_input.setPlaceholderText(tr("ui.listen.channel_config.target_text_placeholder"))
        self.target_text_label = QLabel(tr("ui.listen.channel_config.target_text"))
        self.translatable_widgets['labels']['target_text'] = self.target_text_label
        self.translatable_widgets['inputs']['target_text'] = self.target_text_input
        form_layout.addRow(self.target_text_label, self.target_text_input)
        
        # 将表单直接添加到配置布局
        config_layout.addLayout(form_layout)
        
        # 添加一些间距
        config_layout.addSpacing(6)
        
        # 过滤选项
        filter_options_label = QLabel(tr("ui.listen.channel_config.filter_options"))
        filter_options_label.setStyleSheet("font-weight: bold;")
        self.translatable_widgets['labels']['filter_options'] = filter_options_label
        config_layout.addWidget(filter_options_label)
        
        # 过滤复选框 - 将四个复选框放在同一行，移动到过滤选项标签下方
        filter_checkboxes_layout = QHBoxLayout()
        
        self.exclude_forwards_check = QCheckBox(tr("ui.listen.channel_config.exclude_forwards"))
        self.exclude_replies_check = QCheckBox(tr("ui.listen.channel_config.exclude_replies"))
        self.exclude_text_check = QCheckBox(tr("ui.listen.channel_config.exclude_text"))
        self.exclude_links_check = QCheckBox(tr("ui.listen.channel_config.exclude_links"))
        
        # 存储复选框以便翻译
        self.translatable_widgets['checkboxes']['exclude_forwards'] = self.exclude_forwards_check
        self.translatable_widgets['checkboxes']['exclude_replies'] = self.exclude_replies_check
        self.translatable_widgets['checkboxes']['exclude_text'] = self.exclude_text_check
        self.translatable_widgets['checkboxes']['exclude_links'] = self.exclude_links_check
        
        filter_checkboxes_layout.addWidget(self.exclude_forwards_check)
        filter_checkboxes_layout.addWidget(self.exclude_replies_check)
        filter_checkboxes_layout.addWidget(self.exclude_text_check)
        filter_checkboxes_layout.addWidget(self.exclude_links_check)
        filter_checkboxes_layout.addStretch(1)  # 添加弹性空间，让复选框靠左对齐
        
        config_layout.addLayout(filter_checkboxes_layout)
        
        # 添加一些间距
        config_layout.addSpacing(6)
        
        # 关键词过滤
        filter_layout = QFormLayout()
        filter_layout.setSpacing(8)
        filter_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        filter_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)  # 设置字段可扩展增长
        
        # 关键词输入框和备注布局
        keyword_layout = QHBoxLayout()
        keyword_layout.setSpacing(8)
        
        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText(tr("ui.listen.channel_config.keywords_placeholder"))
        self.keyword_input.setMinimumWidth(540)  # 设置最小宽度为540像素
        self.keyword_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)  # 设置水平可扩展，垂直固定
        self.translatable_widgets['inputs']['keywords'] = self.keyword_input
        keyword_layout.addWidget(self.keyword_input)
        
        self.keywords_label = QLabel(tr("ui.listen.channel_config.keywords"))
        self.translatable_widgets['labels']['keywords'] = self.keywords_label
        filter_layout.addRow(self.keywords_label, keyword_layout)
        
        # 媒体类型选择 - 移动到过滤选项中
        self.media_types_checkboxes = {}
        
        # 所有媒体类型在同一行
        self.media_types_checkboxes["photo"] = QCheckBox(tr("ui.listen.channel_config.media_types_photo"))
        self.media_types_checkboxes["video"] = QCheckBox(tr("ui.listen.channel_config.media_types_video"))
        self.media_types_checkboxes["document"] = QCheckBox(tr("ui.listen.channel_config.media_types_document"))
        self.media_types_checkboxes["audio"] = QCheckBox(tr("ui.listen.channel_config.media_types_audio"))
        self.media_types_checkboxes["animation"] = QCheckBox(tr("ui.listen.channel_config.media_types_animation"))
        self.media_types_checkboxes["sticker"] = QCheckBox(tr("ui.listen.channel_config.media_types_sticker"))
        self.media_types_checkboxes["voice"] = QCheckBox(tr("ui.listen.channel_config.media_types_voice"))
        self.media_types_checkboxes["video_note"] = QCheckBox(tr("ui.listen.channel_config.media_types_video_note"))
        
        # 存储媒体类型复选框以便翻译
        self.translatable_widgets['checkboxes']['media_photo'] = self.media_types_checkboxes["photo"]
        self.translatable_widgets['checkboxes']['media_video'] = self.media_types_checkboxes["video"]
        self.translatable_widgets['checkboxes']['media_document'] = self.media_types_checkboxes["document"]
        self.translatable_widgets['checkboxes']['media_audio'] = self.media_types_checkboxes["audio"]
        self.translatable_widgets['checkboxes']['media_animation'] = self.media_types_checkboxes["animation"]
        self.translatable_widgets['checkboxes']['media_sticker'] = self.media_types_checkboxes["sticker"]
        self.translatable_widgets['checkboxes']['media_voice'] = self.media_types_checkboxes["voice"]
        self.translatable_widgets['checkboxes']['media_video_note'] = self.media_types_checkboxes["video_note"]
        
        # 媒体类型复选框布局 - 将所有8个类型放在同一行
        media_types_layout = QHBoxLayout()
        media_types_layout.addWidget(self.media_types_checkboxes["photo"])
        media_types_layout.addWidget(self.media_types_checkboxes["video"])
        media_types_layout.addWidget(self.media_types_checkboxes["document"])
        media_types_layout.addWidget(self.media_types_checkboxes["audio"])
        media_types_layout.addWidget(self.media_types_checkboxes["animation"])
        media_types_layout.addWidget(self.media_types_checkboxes["sticker"])
        media_types_layout.addWidget(self.media_types_checkboxes["voice"])
        media_types_layout.addWidget(self.media_types_checkboxes["video_note"])
        media_types_layout.addStretch(1)  # 添加弹性空间，让复选框靠左对齐
        
        # 默认选中所有媒体类型
        for checkbox in self.media_types_checkboxes.values():
            checkbox.setChecked(True)
        
        # 添加媒体类型行到表单布局
        self.media_types_label = QLabel(tr("ui.listen.channel_config.media_types"))
        self.translatable_widgets['labels']['media_types'] = self.media_types_label
        filter_layout.addRow(self.media_types_label, media_types_layout)
        
        config_layout.addLayout(filter_layout)
        
        # 添加一些间距
        config_layout.addSpacing(4)
        
        # 监听参数 - 移动到这里，放在排除复选框下方，添加频道对按钮上方
        monitor_options_layout = QHBoxLayout()
        monitor_options_layout.setSpacing(10)  # 设置合适的间距
        
        # 监听参数标签
        monitor_options_label = QLabel(tr("ui.listen.channel_config.monitor_params"))
        monitor_options_label.setStyleSheet("font-weight: bold;")
        self.translatable_widgets['labels']['monitor_params'] = monitor_options_label
        monitor_options_layout.addWidget(monitor_options_label)
        
        # 移除媒体说明复选框
        self.remove_captions_check = QCheckBox(tr("ui.listen.channel_config.remove_captions"))
        self.remove_captions_check.setStyleSheet("padding: 4px;")  # 添加内边距
        self.translatable_widgets['checkboxes']['remove_captions'] = self.remove_captions_check
        monitor_options_layout.addWidget(self.remove_captions_check)
        
        # 添加弹性空间，让控件靠左对齐
        monitor_options_layout.addStretch(1)
        
        # 添加到配置布局
        config_layout.addLayout(monitor_options_layout)
        
        # 添加一些间距
        config_layout.addSpacing(4)
        
        # 频道对操作按钮 - 移动到这里，放在已配置监听频道对标签上方
        channel_action_layout = QHBoxLayout()
        channel_action_layout.setSpacing(8)  # 增加按钮间距
        
        # 添加频道对按钮
        self.add_channel_pair_button = QPushButton(tr("ui.listen.channel_config.add_channel_pair"))
        self.add_channel_pair_button.setMinimumHeight(28)  # 增加按钮高度
        self.translatable_widgets['buttons']['add_channel_pair'] = self.add_channel_pair_button
        channel_action_layout.addWidget(self.add_channel_pair_button)
        
        # 删除频道对按钮
        self.remove_channel_pair_button = QPushButton(tr("ui.listen.channel_config.remove_selected"))
        self.remove_channel_pair_button.setMinimumHeight(28)  # 增加按钮高度
        self.translatable_widgets['buttons']['remove_selected'] = self.remove_channel_pair_button
        channel_action_layout.addWidget(self.remove_channel_pair_button)
        
        # 添加弹性空间，让按钮靠左对齐
        channel_action_layout.addStretch(1)
        
        # 添加按钮布局到配置布局
        config_layout.addLayout(channel_action_layout)
        
        # 添加一些间距
        config_layout.addSpacing(8)
        
        # 创建频道列表部分 - 使用滚动区域显示
        channel_widget = QWidget()
        channel_widget_layout = QVBoxLayout(channel_widget)
        channel_widget_layout.setContentsMargins(0, 0, 0, 0)
        channel_widget_layout.setSpacing(2)
        
        # 已配置监听频道对标签 - 使用与下载界面一致的样式
        self.pairs_list_label = QLabel(tr("ui.listen.channel_config.configured_pairs", count=0))
        self.pairs_list_label.setStyleSheet("font-weight: bold;")  # 加粗标签文字
        self.translatable_widgets['labels']['configured_pairs'] = self.pairs_list_label
        channel_widget_layout.addWidget(self.pairs_list_label)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)  # 允许小部件调整大小
        scroll_area.setMinimumHeight(240)  # 将滚动区域的最小高度加倍（从120增加到240）
        scroll_area.setMaximumHeight(300)  # 将滚动区域的最大高度加倍（从150增加到300）
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
        self.pairs_list.setContextMenuPolicy(Qt.CustomContextMenu)  # 设置自定义右键菜单
        self.pairs_list.customContextMenuRequested.connect(self._show_context_menu)  # 连接右键菜单事件
        scroll_layout.addWidget(self.pairs_list)
        
        # 设置滚动区域的内容
        scroll_area.setWidget(scroll_content)
        channel_widget_layout.addWidget(scroll_area)
        
        # 直接添加到配置布局
        config_layout.addWidget(channel_widget, 1)  # 添加伸展系数
        
        # 设置滚动区域的内容
        config_scroll_area.setWidget(scroll_content_widget)
        
        # 将滚动区域添加到主配置布局
        main_config_layout.addWidget(config_scroll_area)
        
        # 通用配置标签页 - 新增的选项卡
        self.general_config_tab = QWidget()
        general_config_layout = QVBoxLayout(self.general_config_tab)
        general_config_layout.setContentsMargins(12, 12, 12, 12)  # 增加边距
        general_config_layout.setSpacing(15)  # 增加间距
        
        # 通用配置标题
        general_config_label = QLabel(tr("ui.listen.general_config.title"))
        general_config_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.translatable_widgets['labels']['general_config_title'] = general_config_label
        general_config_layout.addWidget(general_config_label)
        
        # 使用表单布局
        general_form_layout = QFormLayout()
        general_form_layout.setSpacing(10)  # 增加表单项间距
        general_form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)  # 标签右对齐
        
        # 监听截止日期 - 从监听参数移动到这里
        duration_layout = QHBoxLayout()
        
        self.duration_check = QCheckBox(tr("ui.listen.general_config.enable_duration"))
        self.duration_check.setStyleSheet("padding: 4px;")  # 添加内边距
        self.translatable_widgets['checkboxes']['enable_duration'] = self.duration_check
        duration_layout.addWidget(self.duration_check)
        
        self.duration_date = QDateTimeEdit(QDateTime.currentDateTime().addDays(365))
        self.duration_date.setCalendarPopup(True)
        self.duration_date.setDisplayFormat("yyyy-MM-dd")
        self.duration_date.setEnabled(False)
        self.duration_date.setMinimumHeight(26)  # 增加高度
        duration_layout.addWidget(self.duration_date)
        
        # 添加弹性空间，让控件靠左对齐
        duration_layout.addStretch(1)
        
        self.duration_label = QLabel(tr("ui.listen.general_config.duration_label"))
        self.translatable_widgets['labels']['duration'] = self.duration_label
        general_form_layout.addRow(self.duration_label, duration_layout)
        
        # 连接时间过滤复选框和日期选择器的启用状态
        self.duration_check.toggled.connect(self.duration_date.setEnabled)
        
        # 添加表单布局到通用配置布局
        general_config_layout.addLayout(general_form_layout)
        
        # 添加弹性空间，让内容靠顶部对齐
        general_config_layout.addStretch(1)
        
        # 监听日志标签页
        self.log_tab = QWidget()
        log_layout = QVBoxLayout(self.log_tab)
        log_layout.setContentsMargins(8, 8, 8, 8)  # 增加边距
        log_layout.setSpacing(8)  # 增加间距
        
        # 创建消息标签页容器
        self.message_tabs = QTabWidget()
        
        # 启用标签卡关闭按钮功能
        self.message_tabs.setTabsClosable(True)
        # 连接标签卡关闭信号
        self.message_tabs.tabCloseRequested.connect(self._close_channel_tab)
        
        # 设置标签卡样式，减小关闭按钮大小
        self.message_tabs.setStyleSheet("""
            QTabBar::close-button {
                width: 12px;
                height: 12px;
                padding: 2px;
                margin: 2px;
                border-radius: 6px;
                background-color: transparent;
            }
            QTabBar::close-button:hover {
                background-color: #ff6b6b;
                color: white;
            }
            QTabBar::close-button:pressed {
                background-color: #e55555;
            }
        """)
        
        # 主消息面板
        self.main_message_view = QTextEdit()
        self.main_message_view.setReadOnly(True)
        self.main_message_view.setLineWrapMode(QTextEdit.WidgetWidth)
        
        # 按频道分类的消息面板
        self.channel_message_views = {}
        
        # 添加主消息面板
        self.message_tabs.addTab(self.main_message_view, tr("ui.listen.monitor_log.all_messages"))
        
        # 为"所有消息"标签卡隐藏关闭按钮
        # 通过设置标签栏按钮为None来隐藏关闭按钮
        from PySide6.QtWidgets import QTabBar
        self.message_tabs.tabBar().setTabButton(0, QTabBar.RightSide, None)
        self.message_tabs.tabBar().setTabButton(0, QTabBar.LeftSide, None)
        
        # 设置消息面板的尺寸策略
        self.message_tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # 设置最小高度，确保消息区域有足够空间显示
        self.message_tabs.setMinimumHeight(180)
        
        # 将消息标签页容器添加到监听日志标签页
        log_layout.addWidget(self.message_tabs, 1)
        
        # 创建性能监控标签页
        self.performance_tab = PerformanceMonitorView(self)
        
        # 将四个标签页添加到配置标签页部件
        self.config_tabs.addTab(self.config_tab, tr("ui.listen.tabs.channel_config"))
        self.config_tabs.addTab(self.general_config_tab, tr("ui.listen.tabs.general_config"))
        self.config_tabs.addTab(self.log_tab, tr("ui.listen.tabs.monitor_log"))
        self.config_tabs.addTab(self.performance_tab, tr("ui.listen.tabs.performance"))
        
        # 存储标签页以便翻译
        self.translatable_widgets['tabs']['channel_config'] = 0
        self.translatable_widgets['tabs']['general_config'] = 1
        self.translatable_widgets['tabs']['monitor_log'] = 2
        self.translatable_widgets['tabs']['performance'] = 3
    
    def _create_action_buttons(self):
        """创建底部操作按钮"""
        # 添加一些垂直间距
        self.main_layout.addSpacing(10)
        
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)  # 增加按钮间距
        button_layout.setContentsMargins(8, 8, 8, 8)  # 添加按钮区域边距
        
        self.start_listen_button = QPushButton(tr("ui.listen.buttons.start_listen"))
        self.start_listen_button.setMinimumHeight(40)
        self.start_listen_button.setMinimumWidth(100)  # 设置最小宽度
        self.translatable_widgets['buttons']['start_listen'] = self.start_listen_button
        
        self.stop_listen_button = QPushButton(tr("ui.listen.buttons.stop_listen"))
        self.stop_listen_button.setEnabled(False)
        self.stop_listen_button.setMinimumHeight(40)
        self.stop_listen_button.setMinimumWidth(100)
        self.translatable_widgets['buttons']['stop_listen'] = self.stop_listen_button
        
        self.save_config_button = QPushButton(tr("ui.listen.buttons.save_config"))
        self.save_config_button.setMinimumHeight(35)  # 稍微增加高度
        self.save_config_button.setMinimumWidth(80)
        self.translatable_widgets['buttons']['save_config'] = self.save_config_button
        
        self.clear_messages_button = QPushButton(tr("ui.listen.buttons.clear_messages"))
        self.clear_messages_button.setMinimumHeight(35)
        self.clear_messages_button.setMinimumWidth(80)
        self.translatable_widgets['buttons']['clear_messages'] = self.clear_messages_button
        
        # 确保按钮大小合理
        for button in [self.start_listen_button, self.stop_listen_button, 
                      self.save_config_button, self.clear_messages_button]:
            button.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        
        button_layout.addWidget(self.start_listen_button)
        button_layout.addWidget(self.stop_listen_button)
        button_layout.addStretch(1)  # 添加弹性空间分隔主要按钮和辅助按钮
        button_layout.addWidget(self.save_config_button)
        button_layout.addWidget(self.clear_messages_button)
        
        # 将按钮布局添加到主布局，不使用伸展因子确保按钮固定在底部
        self.main_layout.addLayout(button_layout)
    
    def _connect_signals(self):
        """连接信号和槽"""
        # 频道管理
        self.add_channel_pair_button.clicked.connect(self._add_channel_pair)
        self.remove_channel_pair_button.clicked.connect(self._remove_channel_pairs)
        
        # 消息操作
        self.clear_messages_button.clicked.connect(self._clear_messages)
        
        # 监听控制
        self.start_listen_button.clicked.connect(self._start_listen)
        self.stop_listen_button.clicked.connect(self._stop_listen)
        self.save_config_button.clicked.connect(self._save_config)
        
        # 如果有父窗口，尝试连接config_saved信号
        parent = self.parent()
        if parent and hasattr(parent, 'config_saved'):
            logger.debug("连接ListenView的config_saved信号到父窗口")
            self.config_saved.connect(parent.config_saved)
    
    def _format_text_filter_display(self, text_filter):
        """格式化文本替换规则的显示
        
        Args:
            text_filter: 文本替换规则列表
            
        Returns:
            str: 格式化后的文本替换规则字符串
        """
        if not text_filter:
            return ""
            
        replacements = []
        for rule in text_filter:
            original = rule.get("original_text", "")
            target = rule.get("target_text", "")
            if original or target:  # 只显示非空的规则
                replacements.append(f"{original}->{target}")
        
        if replacements:
            return tr("ui.listen.display.replacement_rules", rules=', '.join(replacements))
        else:
            return ""
    
    def _format_media_types_display(self, media_types):
        """格式化媒体类型的显示
        
        Args:
            media_types: 媒体类型列表
            
        Returns:
            str: 格式化后的媒体类型字符串
        """
        if not media_types:
            return ""
        
        # 媒体类型中文名映射
        media_type_names = {
            MediaType.PHOTO: tr("ui.listen.channel_config.media_types_photo"),
            MediaType.VIDEO: tr("ui.listen.channel_config.media_types_video"), 
            MediaType.DOCUMENT: tr("ui.listen.channel_config.media_types_document"),
            MediaType.AUDIO: tr("ui.listen.channel_config.media_types_audio"),
            MediaType.ANIMATION: tr("ui.listen.channel_config.media_types_animation"),
            MediaType.STICKER: tr("ui.listen.channel_config.media_types_sticker"),
            MediaType.VOICE: tr("ui.listen.channel_config.media_types_voice"),
            MediaType.VIDEO_NOTE: tr("ui.listen.channel_config.media_types_video_note")
        }
        
        # 对于字符串类型的媒体类型（从配置文件加载的）
        string_media_type_names = {
            "photo": tr("ui.listen.channel_config.media_types_photo"),
            "video": tr("ui.listen.channel_config.media_types_video"), 
            "document": tr("ui.listen.channel_config.media_types_document"),
            "audio": tr("ui.listen.channel_config.media_types_audio"),
            "animation": tr("ui.listen.channel_config.media_types_animation"),
            "sticker": tr("ui.listen.channel_config.media_types_sticker"),
            "voice": tr("ui.listen.channel_config.media_types_voice"),
            "video_note": tr("ui.listen.channel_config.media_types_video_note")
        }
        
        # 转换媒体类型为中文名称
        type_names = []
        for mt in media_types:
            if isinstance(mt, MediaType):
                name = media_type_names.get(mt, str(mt))
            elif isinstance(mt, str):
                name = string_media_type_names.get(mt, mt)
            else:
                name = str(mt)
            type_names.append(name)
        
        # 如果包含所有8种类型，显示"全部"
        all_types = {MediaType.PHOTO, MediaType.VIDEO, MediaType.DOCUMENT, MediaType.AUDIO, 
                    MediaType.ANIMATION, MediaType.STICKER, MediaType.VOICE, MediaType.VIDEO_NOTE}
        
        # 检查是否包含所有类型（考虑字符串和枚举两种格式）
        current_types = set()
        for mt in media_types:
            if isinstance(mt, MediaType):
                current_types.add(mt)
            elif isinstance(mt, str):
                try:
                    current_types.add(MediaType(mt))
                except ValueError:
                    pass
        
        if current_types == all_types:
            return tr("ui.listen.display.media_types", types=tr("ui.listen.display.media_types_all"))
        else:
            return tr("ui.listen.display.media_types", types=', '.join(type_names))
    
    def _format_filter_options_display(self, keywords, exclude_forwards, exclude_replies, exclude_text, exclude_links):
        """格式化过滤选项的显示
        
        Args:
            keywords: 关键词列表
            exclude_forwards: 是否排除转发消息
            exclude_replies: 是否排除回复消息
            exclude_text: 是否排除纯文本消息
            exclude_links: 是否排除包含链接的消息
            
        Returns:
            str: 格式化后的过滤选项字符串
        """
        filter_options = []
        
        # 关键词过滤
        if keywords:
            keywords_str = ", ".join(keywords)
            filter_options.append(tr("ui.listen.display.filter_keywords", keywords=keywords_str))
        
        # 排除选项
        exclude_options = []
        if exclude_forwards:
            exclude_options.append(tr("ui.listen.display.filter_forwards"))
        if exclude_replies:
            exclude_options.append(tr("ui.listen.display.filter_replies"))
        if exclude_text:
            exclude_options.append(tr("ui.listen.display.filter_text"))
        if exclude_links:
            exclude_options.append(tr("ui.listen.display.filter_links"))
        
        if exclude_options:
            filter_options.append(tr("ui.listen.display.filter_exclude", options=', '.join(exclude_options)))
        
        if filter_options:
            return tr("ui.listen.display.filter_options", options=', '.join(filter_options))
        else:
            return ""
    
    def _add_channel_pair(self):
        """添加频道对到监听列表"""
        source_channel = self.source_channel_input.text().strip()
        target_channels = [ch.strip() for ch in self.target_channel_input.text().split(',') if ch.strip()]
        
        if not source_channel:
            QMessageBox.warning(self, tr("ui.listen.messages.warning"), tr("ui.listen.messages.source_required"))
            return
        
        if not target_channels:
            QMessageBox.warning(self, tr("ui.listen.messages.warning"), tr("ui.listen.messages.target_required"))
            return
        
        # 检查是否已存在相同源频道
        for i in range(self.pairs_list.count()):
            item_text = self.pairs_list.item(i).text()
            if item_text.split(" -> ")[0].strip() == source_channel:
                QMessageBox.information(self, tr("ui.listen.messages.info"), tr("ui.listen.messages.channel_exists"))
                return
        
        # 文本替换规则处理
        text_filter = []
        original_texts = [text.strip() for text in self.original_text_input.text().split(',')]
        target_texts = [text.strip() for text in self.target_text_input.text().split(',')]
        
        # 检查原始文本是否全部为空
        if any(target_texts) and not any(original_texts):
            QMessageBox.warning(
                self, 
                tr("ui.listen.messages.original_text_error"), 
                tr("ui.listen.messages.original_text_empty")
            )
            return
            
        # 如果原始文本和替换文本都为空，添加一个默认空项
        if not any(original_texts) and not any(target_texts):
            text_filter.append({
                "original_text": "",
                "target_text": ""
            })
            logger.debug("用户未输入文本替换内容，添加空的text_filter项")
        else:
            # 检查原始文本和替换文本数量是否匹配
            if len(original_texts) != len(target_texts) and len(original_texts) > 0 and len(target_texts) > 0:
                # 显示警告对话框
                QMessageBox.warning(
                    self, 
                    tr("ui.listen.messages.original_text_error"), 
                    tr("ui.listen.messages.text_replacement_mismatch", 
                       original_count=len(original_texts), 
                       target_count=len(target_texts))
                )
                return
                
            # 检查是否有空的原始文本项
            empty_indexes = [i+1 for i, text in enumerate(original_texts) if not text and i < len(target_texts) and target_texts[i]]
            if empty_indexes:
                positions = ", ".join(map(str, empty_indexes))
                QMessageBox.warning(
                    self, 
                    tr("ui.listen.messages.original_text_error"), 
                    tr("ui.listen.messages.original_text_empty_position", positions=positions)
                )
                return
            
            # 创建文本替换规则项
            for i, orig in enumerate(original_texts):
                # 如果原始文本为空且对应的替换文本不为空，跳过（这种情况已在上面处理过）
                if not orig and i < len(target_texts) and target_texts[i]:
                    continue
                    
                # 如果替换文本列表较短，则对应位置使用空字符串
                target = target_texts[i] if i < len(target_texts) else ""
                text_filter.append({
                    "original_text": orig,
                    "target_text": target
                })
        
        # 获取选中的媒体类型
        selected_media_types = []
        for media_type, checkbox in self.media_types_checkboxes.items():
            if checkbox.isChecked():
                if media_type == "photo":
                    selected_media_types.append(MediaType.PHOTO)
                elif media_type == "video":
                    selected_media_types.append(MediaType.VIDEO)
                elif media_type == "document":
                    selected_media_types.append(MediaType.DOCUMENT)
                elif media_type == "audio":
                    selected_media_types.append(MediaType.AUDIO)
                elif media_type == "animation":
                    selected_media_types.append(MediaType.ANIMATION)
                elif media_type == "sticker":
                    selected_media_types.append(MediaType.STICKER)
                elif media_type == "voice":
                    selected_media_types.append(MediaType.VOICE)
                elif media_type == "video_note":
                    selected_media_types.append(MediaType.VIDEO_NOTE)
        
        # 如果没有选择任何媒体类型，使用默认的所有类型
        if not selected_media_types:
            selected_media_types = [
                MediaType.PHOTO, MediaType.VIDEO, MediaType.DOCUMENT, 
                MediaType.AUDIO, MediaType.ANIMATION, MediaType.STICKER,
                MediaType.VOICE, MediaType.VIDEO_NOTE
            ]
        
        # 获取过滤选项
        keywords = [kw.strip() for kw in self.keyword_input.text().split(',') if kw.strip()]
        
        # 存储完整数据，包括媒体类型
        pair_data = {
            "source_channel": source_channel,
            "target_channels": target_channels,
            "remove_captions": self.remove_captions_check.isChecked(),
            "text_filter": text_filter,
            "media_types": selected_media_types,
            "keywords": keywords,
            "exclude_forwards": self.exclude_forwards_check.isChecked(),
            "exclude_replies": self.exclude_replies_check.isChecked(),
            "exclude_text": self.exclude_text_check.isChecked(),
            "exclude_links": self.exclude_links_check.isChecked()
        }
        
        # 添加到列表，采用与下载界面类似的样式
        target_channels_str = ", ".join(target_channels)
        text_filter_str = self._format_text_filter_display(text_filter)
        media_types_str = self._format_media_types_display(selected_media_types)
        
        # 添加过滤选项显示
        filter_options_str = self._format_filter_options_display(
            keywords,
            self.exclude_forwards_check.isChecked(),
            self.exclude_replies_check.isChecked(),
            self.exclude_text_check.isChecked(),
            self.exclude_links_check.isChecked()
        )
        
        # 添加调试信息
        logger.debug(f"频道对 {source_channel} - 关键词: {keywords}, 排除项: forwards={self.exclude_forwards_check.isChecked()}, replies={self.exclude_replies_check.isChecked()}, media={self.exclude_text_check.isChecked()}, links={self.exclude_links_check.isChecked()}")
        logger.debug(f"频道对 {source_channel} - 过滤选项显示字符串: '{filter_options_str}'")
        
        display_text = f"{source_channel} -> {target_channels_str}{text_filter_str}{media_types_str}{filter_options_str}"
        if self.remove_captions_check.isChecked():
            display_text += tr("ui.listen.display.remove_captions_suffix")
        
        logger.debug(f"频道对 {source_channel} - 完整显示文本: '{display_text}'")
        
        item = QListWidgetItem(display_text)
        item.setData(Qt.UserRole, pair_data)
        self.pairs_list.addItem(item)
        
        # 更新频道数量标签
        self.pairs_list_label.setText(tr("ui.listen.channel_config.configured_pairs", count=self.pairs_list.count()))
        
        # 清空输入
        self.source_channel_input.clear()
        self.target_channel_input.clear()
        self.original_text_input.clear()
        self.target_text_input.clear()
        self.remove_captions_check.setChecked(False)
        
        # 将媒体类型复选框设置为全选状态作为默认
        for checkbox in self.media_types_checkboxes.values():
            checkbox.setChecked(True)
        
        # 将过滤选项UI重置为默认状态（用于添加新频道对时的默认设置）
        self.keyword_input.clear()
        self.exclude_forwards_check.setChecked(False)
        self.exclude_replies_check.setChecked(False)
        self.exclude_text_check.setChecked(False)
        self.exclude_links_check.setChecked(False)
    
    def _remove_channel_pairs(self):
        """删除选中的监听频道对"""
        selected_items = self.pairs_list.selectedItems()
        
        if not selected_items:
            QMessageBox.information(self, tr("ui.listen.messages.info"), tr("ui.listen.messages.select_to_remove"))
            return
        
        # 删除选中的频道对
        for item in reversed(selected_items):
            data = item.data(Qt.UserRole)
            source_channel = data["source_channel"]
            row = self.pairs_list.row(item)
            self.pairs_list.takeItem(row)
            
            # 注意：不再自动删除对应的标签页，因为标签页现在是动态创建的
            # 用户可能希望保留标签页中的历史消息记录
            logger.debug(f"已删除频道对: {source_channel}，保留对应的消息标签页")
        
        # 更新频道数量标签
        self.pairs_list_label.setText(tr("ui.listen.channel_config.configured_pairs", count=self.pairs_list.count()))
    
    def _clear_messages(self):
        """清空所有消息"""
        # 清空主消息面板
        self.main_message_view.clear()
        
        # 清空各频道消息面板
        for view in self.channel_message_views.values():
            view.clear()
    
    def _close_channel_tab(self, index):
        """关闭指定索引的频道标签卡
        
        Args:
            index (int): 要关闭的标签卡索引
        """
        try:
            # 检查索引是否有效
            if index < 0 or index >= self.message_tabs.count():
                logger.warning(f"尝试关闭无效的标签卡索引: {index}")
                return
            
            # 获取标签卡文本
            tab_text = self.message_tabs.tabText(index)
            
            # 不允许关闭"所有消息"标签卡（索引0）
            all_messages_text = tr("ui.listen.monitor_log.all_messages")
            if index == 0 or tab_text == all_messages_text:
                logger.info("无法关闭'所有消息'标签卡")
                return
            
            # 获取要关闭的标签卡widget
            widget_to_remove = self.message_tabs.widget(index)
            
            # 从channel_message_views字典中移除对应的视图
            channel_key_to_remove = None
            for channel_key, view in self.channel_message_views.items():
                if view == widget_to_remove:
                    channel_key_to_remove = channel_key
                    break
            
            if channel_key_to_remove is not None:
                del self.channel_message_views[channel_key_to_remove]
                logger.info(f"已从频道消息视图字典中移除频道: {channel_key_to_remove}")
            
            # 从标签卡中移除
            self.message_tabs.removeTab(index)
            
            # 删除widget（Qt会自动处理内存释放）
            if widget_to_remove:
                widget_to_remove.deleteLater()
            
            logger.info(f"已关闭频道标签卡: {tab_text} (索引: {index})")
            
            # 如果关闭后只剩下"所有消息"标签卡，自动切换到它
            if self.message_tabs.count() == 1:
                self.message_tabs.setCurrentIndex(0)
                logger.info("只剩下'所有消息'标签卡，已自动切换")
            
        except Exception as e:
            logger.error(f"关闭标签卡时发生错误: {e}")
            self._show_error_dialog(tr("ui.listen.messages.error"), f"关闭标签卡时发生错误：{str(e)}")
    
    def _disable_close_button_for_all_messages_tab(self):
        """为'所有消息'标签卡禁用关闭按钮
        
        注意：这是一个辅助方法，但PySide6的QTabWidget没有直接禁用单个标签卡关闭按钮的API
        我们通过在_close_channel_tab方法中检查索引来实现相同的效果
        """
        # 这个方法保留作为文档说明，实际的禁用逻辑在_close_channel_tab中实现
        pass
    
    def _start_listen(self):
        """开始监听"""
        # 检查是否有监听频道对
        if self.pairs_list.count() == 0:
            QMessageBox.warning(self, tr("ui.listen.messages.warning"), tr("ui.listen.messages.no_pairs"))
            return
        
        # 检查是否有监听器实例
        if not hasattr(self, 'monitor') or self.monitor is None:
            QMessageBox.warning(self, tr("ui.listen.messages.error"), tr("ui.listen.messages.monitor_not_initialized"))
            return
        
        # 添加状态消息
        self._add_status_message(tr("ui.listen.messages.start_listening"))
        
        # 自动切换到监听日志选项卡
        self.config_tabs.setCurrentIndex(2)  # 监听日志选项卡是第3个（索引为2）
        
        # 更新按钮状态
        self.start_listen_button.setEnabled(False)
        self.stop_listen_button.setEnabled(True)
        
        # 异步启动监听
        import asyncio
        try:
            # 创建启动监听的任务
            loop = asyncio.get_event_loop()
            loop.create_task(self._async_start_monitoring())
        except Exception as e:
            logger.error(f"启动监听时出错: {e}")
            self._add_status_message(tr("ui.listen.messages.monitor_error", error=str(e)))
            # 恢复按钮状态
            self.start_listen_button.setEnabled(True)
            self.stop_listen_button.setEnabled(False)
    
    def _stop_listen(self):
        """停止监听"""
        # 检查是否有监听器实例
        if not hasattr(self, 'monitor') or self.monitor is None:
            self._add_status_message(tr("ui.listen.messages.monitor_not_initialized"))
            return
        
        # 添加状态消息
        self._add_status_message(tr("ui.listen.messages.stop_listening"))
        
        # 更新按钮状态
        self.start_listen_button.setEnabled(True)
        self.stop_listen_button.setEnabled(False)
        
        # 异步停止监听
        import asyncio
        try:
            # 创建停止监听的任务
            loop = asyncio.get_event_loop()
            loop.create_task(self._async_stop_monitoring())
        except Exception as e:
            logger.error(f"停止监听时出错: {e}")
            self._add_status_message(tr("ui.listen.messages.monitor_error", error=str(e)))
    
    async def _async_start_monitoring(self):
        """异步启动监听"""
        try:
            self._add_status_message(tr("ui.listen.status.preparing"))
            await self.monitor.start_monitoring()
            self._add_status_message(tr("ui.listen.messages.listening_started"))
        except Exception as e:
            logger.error(f"异步启动监听失败: {e}")
            self._add_status_message(tr("ui.listen.messages.monitor_error", error=str(e)))
            # 恢复按钮状态
            self.start_listen_button.setEnabled(True)
            self.stop_listen_button.setEnabled(False)
    
    async def _async_stop_monitoring(self):
        """异步停止监听"""
        try:
            await self.monitor.stop_monitoring()
            self._add_status_message(tr("ui.listen.messages.listening_stopped"))
        except Exception as e:
            logger.error(f"异步停止监听失败: {e}")
            self._add_status_message(tr("ui.listen.messages.monitor_error", error=str(e)))
    
    def _get_monitor_config(self):
        """获取当前监听配置
        
        Returns:
            dict: 监听配置字典
        """
        # 获取频道对列表
        monitor_channel_pairs = []
        for i in range(self.pairs_list.count()):
            item = self.pairs_list.item(i)
            data = item.data(Qt.UserRole)
            text_filter = data.get("text_filter", [])
            
            # 添加详细的原始数据调试信息
            logger.debug(f"频道对 {data['source_channel']} - 从配置读取的原始数据:")
            logger.debug(f"  keywords: {data['keywords']} (类型: {type(data['keywords'])})")
            logger.debug(f"  exclude_forwards: {data['exclude_forwards']} (类型: {type(data['exclude_forwards'])})")
            logger.debug(f"  exclude_replies: {data['exclude_replies']} (类型: {type(data['exclude_replies'])})")
            logger.debug(f"  exclude_text: {data['exclude_text']} (类型: {type(data['exclude_text'])})")
            logger.debug(f"  exclude_links: {data['exclude_links']} (类型: {type(data['exclude_links'])})")
            logger.debug(f"  完整配置项: {data}")
            
            # 确保text_filter至少有一项，即使是空的
            if not text_filter:
                text_filter = [{"original_text": "", "target_text": ""}]
                logger.debug(f"获取监听配置时，频道对 {data['source_channel']} 的text_filter为空，添加默认空项")
            
            # 获取该频道对的媒体类型
            media_types = data.get("media_types", [])
            # 如果没有媒体类型，使用默认的所有类型
            if not media_types:
                media_types = [
                    MediaType.PHOTO, MediaType.VIDEO, MediaType.DOCUMENT, 
                    MediaType.AUDIO, MediaType.ANIMATION, MediaType.STICKER,
                    MediaType.VOICE, MediaType.VIDEO_NOTE
                ]
            else:
                # 确保媒体类型是MediaType枚举而不是字符串
                converted_media_types = []
                for mt in media_types:
                    if isinstance(mt, str):
                        try:
                            converted_media_types.append(MediaType(mt))
                        except ValueError:
                            logger.warning(f"无效的媒体类型字符串: {mt}")
                    elif isinstance(mt, MediaType):
                        converted_media_types.append(mt)
                    else:
                        logger.warning(f"未知的媒体类型格式: {mt} (类型: {type(mt)})")
                
                # 如果转换后没有有效的媒体类型，使用默认值
                if converted_media_types:
                    media_types = converted_media_types
                else:
                    logger.warning("转换后没有有效的媒体类型，使用默认值")
                    media_types = [
                        MediaType.PHOTO, MediaType.VIDEO, MediaType.DOCUMENT, 
                        MediaType.AUDIO, MediaType.ANIMATION, MediaType.STICKER,
                        MediaType.VOICE, MediaType.VIDEO_NOTE
                    ]
            
            # 获取该频道对的过滤选项
            keywords = data.get("keywords", [])
            exclude_forwards = data.get("exclude_forwards", False)
            exclude_replies = data.get("exclude_replies", False)
            exclude_text = data.get("exclude_text", False)
            exclude_links = data.get("exclude_links", False)
            
            monitor_channel_pairs.append({
                "source_channel": data["source_channel"],
                "target_channels": data["target_channels"],
                "remove_captions": data["remove_captions"],
                "text_filter": text_filter,
                "media_types": media_types,
                "keywords": keywords,
                "exclude_forwards": exclude_forwards,
                "exclude_replies": exclude_replies,
                "exclude_text": exclude_text,
                "exclude_links": exclude_links
            })
        
        # 获取监听截止日期
        duration = None
        if self.duration_check.isChecked():
            duration = self.duration_date.date().toString("yyyy-MM-dd")
        
        # 收集监听配置 - 移除全局media_types字段
        monitor_config = {
            'monitor_channel_pairs': monitor_channel_pairs,
            'duration': duration
        }
        
        return monitor_config
    
    def _save_config(self):
        """保存当前配置"""
        # 检查是否有监听频道对
        if self.pairs_list.count() == 0:
            QMessageBox.warning(self, tr("ui.listen.messages.warning"), tr("ui.listen.messages.no_pairs"))
            return
        
        # 获取监听配置
        monitor_config = self._get_monitor_config()
        
        try:
            # 格式化数据以匹配UIMonitorConfig期望的结构
            monitor_channel_pairs = []
            for pair in monitor_config['monitor_channel_pairs']:
                # 确保text_filter至少有一项
                text_filter = pair.get('text_filter', [])
                if not text_filter:
                    text_filter = [{"original_text": "", "target_text": ""}]
                    logger.debug(f"保存配置时，频道对 {pair['source_channel']} 的text_filter为空，添加默认空项")
                
                # 获取该频道对的媒体类型
                media_types = pair.get('media_types', [])
                if not media_types:
                    media_types = [
                        MediaType.PHOTO, MediaType.VIDEO, MediaType.DOCUMENT, 
                        MediaType.AUDIO, MediaType.ANIMATION, MediaType.STICKER,
                        MediaType.VOICE, MediaType.VIDEO_NOTE
                    ]
                
                # 获取该频道对的过滤选项
                keywords = pair.get('keywords', [])
                exclude_forwards = pair.get('exclude_forwards', False)
                exclude_replies = pair.get('exclude_replies', False)
                exclude_text = pair.get('exclude_text', False)
                exclude_links = pair.get('exclude_links', False)
                
                # 创建UIMonitorChannelPair对象
                monitor_channel_pairs.append(UIMonitorChannelPair(
                    source_channel=pair['source_channel'],
                    target_channels=pair['target_channels'],
                    remove_captions=pair['remove_captions'],
                    text_filter=text_filter,
                    media_types=media_types,
                    keywords=keywords,
                    exclude_forwards=exclude_forwards,
                    exclude_replies=exclude_replies,
                    exclude_text=exclude_text,
                    exclude_links=exclude_links
                ))
            
            # 创建UIMonitorConfig对象
            ui_monitor_config = UIMonitorConfig(
                monitor_channel_pairs=monitor_channel_pairs,
                duration=monitor_config['duration']
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
            updated_config['MONITOR'] = ui_monitor_config.dict()
            
            # 移除原有的全局LISTEN过滤配置（如果存在）
            if 'LISTEN' in updated_config:
                del updated_config['LISTEN']
            
            # 发送配置保存信号
            logger.debug(f"向主窗口发送配置保存信号，更新监听配置")
            self.config_saved.emit(updated_config)
            
            # 显示成功消息
            QMessageBox.information(self, tr("ui.listen.messages.success"), tr("ui.listen.messages.config_saved"))
            
            # 更新本地配置引用
            self.config = updated_config
            
        except Exception as e:
            logger.error(f"保存监听配置失败: {e}")
            QMessageBox.warning(self, tr("ui.listen.messages.error"), tr("ui.listen.messages.save_failed", error=str(e)))
    
    def _add_status_message(self, message):
        """添加状态消息到消息面板
        
        Args:
            message: 状态消息
        """
        time_str = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
        status_msg = f"[{time_str}] [{tr('ui.listen.messages.system')}] {message}"
        
        # 添加到主消息面板
        self.main_message_view.append(status_msg)
        
        # 自动滚动到底部
        self.main_message_view.moveCursor(QTextCursor.End)
    
    def add_message(self, channel, message_data):
        """添加新消息到消息面板
        
        Args:
            channel: 频道ID或链接
            message_data: 消息数据字典
        """
        # 格式化消息
        time_str = message_data.get('time', QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss"))
        sender = message_data.get('sender', 'Unknown')
        text = message_data.get('text', '')
        media_type = message_data.get('media_type', None)
        
        # 媒体类型标记
        media_tag = ""
        if media_type:
            media_tag = f"[{media_type}]"
        
        # 构建消息文本
        formatted_msg = f"[{time_str}] [{sender}] {media_tag} {text}"
        
        # 添加到主消息面板
        self.main_message_view.append(formatted_msg)
        
        # 添加到频道特定的消息面板
        if channel in self.channel_message_views:
            self.channel_message_views[channel].append(formatted_msg)
        
        # 自动滚动到底部
        self.main_message_view.moveCursor(QTextCursor.End)
        if channel in self.channel_message_views:
            self.channel_message_views[channel].moveCursor(QTextCursor.End)
        
        # 限制消息数量 - 固定200条
        max_messages = 200
        
        # 删除超出限制的消息
        doc = self.main_message_view.document()
        if doc.blockCount() > max_messages:
            cursor = QTextCursor(doc)
            cursor.movePosition(QTextCursor.Start)
            cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            cursor.removeSelectedText()
            cursor.deleteChar()  # 删除换行符
        
        # 同样处理频道特定的消息面板
        if channel in self.channel_message_views:
            doc = self.channel_message_views[channel].document()
            if doc.blockCount() > max_messages:
                cursor = QTextCursor(doc)
                cursor.movePosition(QTextCursor.Start)
                cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
                cursor.removeSelectedText()
                cursor.deleteChar()  # 删除换行符
    
    def load_config(self, config):
        """从配置加载UI状态
        
        Args:
            config: 配置字典
        """
        logger.info(f"监听界面开始加载配置，配置数据: {type(config)}")
        logger.debug(f"配置内容: {config}")
        
        # 清空现有项目
        self.pairs_list.clear()
        
        # 清除所有频道标签页（保留"所有消息"标签页）
        while self.message_tabs.count() > 1:  # 保留"所有消息"标签页
            self.message_tabs.removeTab(1)
        
        # 清空频道消息视图字典（现在标签页是动态创建的）
        self.channel_message_views = {}
        
        # 从配置加载监听配置
        monitor_config = config.get('MONITOR', {})
        
        if not monitor_config:
            logger.warning("配置中没有监听配置")
            return
        
        # 加载监听频道对
        monitor_channel_pairs = monitor_config.get('monitor_channel_pairs', [])
        
        for pair in monitor_channel_pairs:
            source_channel = pair.get('source_channel', '')
            target_channels = pair.get('target_channels', [])
            remove_captions = pair.get('remove_captions', False)
            text_filter = pair.get('text_filter', [])
            media_types = pair.get('media_types', [])
            
            # 加载过滤选项
            keywords = pair.get('keywords', [])
            exclude_forwards = pair.get('exclude_forwards', False)
            exclude_replies = pair.get('exclude_replies', False)
            # 兼容性处理：先尝试读取exclude_text，如果没有则从exclude_media转换
            exclude_text = pair.get('exclude_text', pair.get('exclude_media', False))
            exclude_links = pair.get('exclude_links', False)
            
            # 添加详细的原始数据调试信息
            logger.debug(f"频道对 {source_channel} - 从配置读取的原始数据:")
            logger.debug(f"  keywords: {keywords} (类型: {type(keywords)})")
            logger.debug(f"  exclude_forwards: {exclude_forwards} (类型: {type(exclude_forwards)})")
            logger.debug(f"  exclude_replies: {exclude_replies} (类型: {type(exclude_replies)})")
            logger.debug(f"  exclude_text: {exclude_text} (类型: {type(exclude_text)})")
            logger.debug(f"  exclude_links: {exclude_links} (类型: {type(exclude_links)})")
            logger.debug(f"  完整配置项: {pair}")
            
            # 确保text_filter至少有一项，即使是空的
            if not text_filter:
                text_filter = [{"original_text": "", "target_text": ""}]
                logger.debug(f"频道对 {source_channel} 的text_filter为空，添加默认空项")
            
            # 如果没有媒体类型，使用默认的所有类型
            if not media_types:
                media_types = [
                    MediaType.PHOTO, MediaType.VIDEO, MediaType.DOCUMENT, 
                    MediaType.AUDIO, MediaType.ANIMATION, MediaType.STICKER,
                    MediaType.VOICE, MediaType.VIDEO_NOTE
                ]
            else:
                # 确保媒体类型是MediaType枚举而不是字符串
                converted_media_types = []
                for mt in media_types:
                    if isinstance(mt, str):
                        try:
                            converted_media_types.append(MediaType(mt))
                        except ValueError:
                            logger.warning(f"无效的媒体类型字符串: {mt}")
                    elif isinstance(mt, MediaType):
                        converted_media_types.append(mt)
                    else:
                        logger.warning(f"未知的媒体类型格式: {mt} (类型: {type(mt)})")
                
                # 如果转换后没有有效的媒体类型，使用默认值
                if converted_media_types:
                    media_types = converted_media_types
                else:
                    logger.warning("转换后没有有效的媒体类型，使用默认值")
                    media_types = [
                        MediaType.PHOTO, MediaType.VIDEO, MediaType.DOCUMENT, 
                        MediaType.AUDIO, MediaType.ANIMATION, MediaType.STICKER,
                        MediaType.VOICE, MediaType.VIDEO_NOTE
                    ]
            
            if not source_channel or not target_channels:
                continue
            
            # 添加到列表，采用与下载界面类似的样式
            target_channels_str = ", ".join(target_channels)
            text_filter_str = self._format_text_filter_display(text_filter)
            media_types_str = self._format_media_types_display(media_types)
            
            # 添加过滤选项显示
            filter_options_str = self._format_filter_options_display(
                keywords,
                exclude_forwards,
                exclude_replies,
                exclude_text,
                exclude_links
            )
            
            # 添加调试信息
            logger.debug(f"频道对 {source_channel} - 关键词: {keywords}, 排除项: forwards={exclude_forwards}, replies={exclude_replies}, text={exclude_text}, links={exclude_links}")
            logger.debug(f"频道对 {source_channel} - 过滤选项显示字符串: '{filter_options_str}'")
            
            display_text = f"{source_channel} -> {target_channels_str}{text_filter_str}{media_types_str}{filter_options_str}"
            if remove_captions:
                display_text += tr("ui.listen.display.remove_captions_suffix")
            
            logger.debug(f"频道对 {source_channel} - 完整显示文本: '{display_text}'")
            
            item = QListWidgetItem(display_text)
            # 存储完整数据，包括媒体类型
            pair_data = {
                "source_channel": source_channel,
                "target_channels": target_channels,
                "remove_captions": remove_captions,
                "text_filter": text_filter,
                "media_types": media_types,
                "keywords": keywords,
                "exclude_forwards": exclude_forwards,
                "exclude_replies": exclude_replies,
                "exclude_text": exclude_text,
                "exclude_links": exclude_links
            }
            item.setData(Qt.UserRole, pair_data)
            self.pairs_list.addItem(item)
            
            # 注意：不再预先创建标签页，现在标签页是在收到消息时动态创建的
            logger.debug(f"已加载频道对: {source_channel}，标签页将在收到消息时自动创建")
        
        # 更新频道数量标签
        self.pairs_list_label.setText(tr("ui.listen.channel_config.configured_pairs", count=self.pairs_list.count()))
        
        # 将媒体类型复选框设置为全选状态作为默认
        for checkbox in self.media_types_checkboxes.values():
            checkbox.setChecked(True)
        
        # 加载监听截止日期
        duration = monitor_config.get('duration')
        if duration:
            self.duration_check.setChecked(True)
            try:
                date = datetime.strptime(duration, "%Y-%m-%d")
                self.duration_date.setDate(QDateTime.fromString(duration, "yyyy-MM-dd").date())
            except ValueError:
                logger.error(f"监听截止日期格式错误: {duration}")
                self.duration_check.setChecked(False)
        else:
            self.duration_check.setChecked(False)
    
    def set_monitor(self, monitor):
        """设置监听器实例
        
        Args:
            monitor: 监听器实例
        """
        if not monitor:
            logger.warning("监听器实例为空，无法设置")
            return
            
        self.monitor = monitor
        logger.debug("监听视图已接收监听器实例")
        
        # 设置性能监控器
        if hasattr(monitor, 'performance_monitor') and monitor.performance_monitor:
            self.performance_tab.set_performance_monitor(monitor.performance_monitor)
            logger.debug("性能监控器已连接到UI")
        
        # 连接信号
        self._connect_monitor_signals()
    
    def _connect_monitor_signals(self):
        """连接监听器信号到UI更新"""
        if not hasattr(self, 'monitor') or self.monitor is None:
            logger.warning("监听器不存在，无法连接信号")
            return
            
        # 连接监听器事件处理器
        try:
            # 检查monitor是否有信号属性并连接
            if hasattr(self.monitor, 'status_updated'):
                self.monitor.status_updated.connect(self._update_status)
                logger.debug("已连接status_updated信号")
            
            # 连接新消息信号 - 使用正确的信号名称
            if hasattr(self.monitor, 'new_message_updated'):
                self.monitor.new_message_updated.connect(self._on_new_message_signal)
                logger.debug("已连接new_message_updated信号")
            
            # 连接消息接收信号
            if hasattr(self.monitor, 'message_received'):
                self.monitor.message_received.connect(self._on_message_received_signal)
                logger.debug("已连接message_received信号")
            
            # 连接监听开始/停止信号
            if hasattr(self.monitor, 'monitoring_started'):
                self.monitor.monitoring_started.connect(self._on_monitoring_started)
                logger.debug("已连接monitoring_started信号")
            
            if hasattr(self.monitor, 'monitoring_stopped'):
                self.monitor.monitoring_stopped.connect(self._on_monitoring_stopped)
                logger.debug("已连接monitoring_stopped信号")
            
            # 连接转发完成信号
            if hasattr(self.monitor, 'forward_updated'):
                self.monitor.forward_updated.connect(self._on_forward_updated_signal)
                logger.debug("已连接forward_updated信号")
            
            # 连接错误信号
            if hasattr(self.monitor, 'error_occurred'):
                self.monitor.error_occurred.connect(self._on_monitor_error)
                logger.debug("已连接error_occurred信号")
            
            # 连接过滤消息信号
            if hasattr(self.monitor, 'message_filtered'):
                self.monitor.message_filtered.connect(self._on_message_filtered)
                logger.debug("已连接message_filtered信号")
            
            logger.debug("监听器信号连接成功")
            
        except Exception as e:
            logger.error(f"连接监听器信号时出错: {e}")
            import traceback
            logger.debug(f"错误详情:\n{traceback.format_exc()}")
    
    def _on_new_message_signal(self, message_id, source_info):
        """处理新消息信号
        
        Args:
            message_id: 消息ID
            source_info: 源信息
        """
        try:
            # 构建消息显示内容
            content = tr("ui.listen.log.received_message", message_id=message_id)
            
            # 添加到主消息面板（所有消息）
            self._add_message_item(source_info, content)
            
            # 添加到对应的频道标签页
            matched_channel = None
            for source_channel, view in self.channel_message_views.items():
                # 使用改进的匹配逻辑
                if self._is_channel_match(source_channel, source_info):
                    time_str = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
                    formatted_msg = f"[{time_str}] [{tr('ui.listen.messages.new_message')}] {source_info}: {content}"
                    view.append(formatted_msg)
                    view.moveCursor(QTextCursor.End)
                    
                    # 限制消息数量
                    max_messages = 200
                    doc = view.document()
                    if doc.blockCount() > max_messages:
                        cursor = QTextCursor(doc)
                        cursor.movePosition(QTextCursor.Start)
                        cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
                        cursor.removeSelectedText()
                        cursor.deleteChar()  # 删除换行符
                    
                    logger.debug(f"新消息已添加到频道标签页: {source_channel}")
                    matched_channel = source_channel
                    break
            
            # 如果没有匹配的标签页，尝试创建新的标签页
            if not matched_channel:
                logger.info(f"未找到匹配的频道标签页，为新消息创建标签页: {source_info}")
                try:
                    # 从源信息中提取ID
                    import re
                    display_id = None
                    id_match = re.search(r'\(ID:\s*(-?\d+)\)', source_info)
                    if id_match:
                        display_id = id_match.group(1)
                        logger.info(f"从源信息提取的ID: {display_id}")
                        
                        # 直接为这个ID创建标签页
                        if display_id and display_id not in self.channel_message_views:
                            logger.info(f"为频道ID {display_id} 创建新的标签页")
                            channel_view = QTextEdit()
                            channel_view.setReadOnly(True)
                            channel_view.setLineWrapMode(QTextEdit.WidgetWidth)
                            
                            # 从源信息中提取频道名称作为标签页标题
                            channel_title = self._extract_channel_title_from_source_info(source_info)
                            
                            self.message_tabs.addTab(channel_view, channel_title)
                            self.channel_message_views[display_id] = channel_view
                            
                            logger.info(f"成功创建标签页: {channel_title} -> {display_id}")
                            
                        # 添加消息到标签页
                        if display_id and display_id in self.channel_message_views:
                            view = self.channel_message_views[display_id]
                            time_str = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
                            formatted_msg = f"[{time_str}] [{tr('ui.listen.messages.new_message')}] {source_info}: {content}"
                            view.append(formatted_msg)
                            view.moveCursor(QTextCursor.End)
                            
                            # 限制消息数量
                            max_messages = 200
                            doc = view.document()
                            if doc.blockCount() > max_messages:
                                cursor = QTextCursor(doc)
                                cursor.movePosition(QTextCursor.Start)
                                cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
                                cursor.removeSelectedText()
                                cursor.deleteChar()  # 删除换行符
                            
                            logger.info(f"成功在标签页 {display_id} 中添加新消息")
                            matched_channel = display_id
                    else:
                        logger.info("无法从源信息中提取ID，使用完整源信息作为key")
                        # 如果无法提取ID，直接使用源信息作为key
                        if source_info not in self.channel_message_views:
                            logger.info(f"为源信息 '{source_info}' 创建新的标签页")
                            channel_view = QTextEdit()
                            channel_view.setReadOnly(True)
                            channel_view.setLineWrapMode(QTextEdit.WidgetWidth)
                            
                            # 使用智能提取的频道名称作为标签页标题
                            channel_title = self._extract_channel_title_from_source_info(source_info)
                            
                            self.message_tabs.addTab(channel_view, channel_title)
                            self.channel_message_views[source_info] = channel_view
                            
                            logger.info(f"成功创建标签页: {channel_title} -> {source_info}")
                            
                        # 添加消息到标签页
                        view = self.channel_message_views[source_info]
                        time_str = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
                        formatted_msg = f"[{time_str}] [{tr('ui.listen.messages.new_message')}] {source_info}: {content}"
                        view.append(formatted_msg)
                        view.moveCursor(QTextCursor.End)
                        
                        logger.info(f"成功在标签页 '{source_info}' 中添加新消息")
                        matched_channel = source_info
                        
                except Exception as e:
                    logger.error(f"为新消息创建标签页时发生错误: {e}")
            
            logger.debug(f"处理新消息信号: {message_id} - {source_info}")
        except Exception as e:
            logger.error(f"处理新消息信号时出错: {e}")
    
    def _on_message_received_signal(self, message_id, source_info):
        """处理消息接收信号
        
        Args:
            message_id: 消息ID
            source_info: 源信息
        """
        try:
            # 构建消息显示内容
            content = tr("ui.listen.log.message_received", message_id=message_id)
            
            # 添加到消息列表
            self._add_message_item(source_info, content)
            
            logger.debug(f"处理消息接收信号: {message_id} - {source_info}")
        except Exception as e:
            logger.error(f"处理消息接收信号时出错: {e}")
    
    def _on_forward_updated_signal(self, source_message_id, source_display_name, target_display_name, success, modified):
        """处理转发更新信号
        
        Args:
            source_message_id: 源消息ID（字符串类型，可能是数字ID或媒体组显示ID格式）
            source_display_name: 源频道显示名称
            target_display_name: 目标频道显示名称
            success: 是否成功
            modified: 是否修改
        """
        try:
            # 构建转发信息
            status = tr("ui.listen.messages.forward_success") if success else tr("ui.listen.messages.forward_failed")
            mod_info = tr("ui.listen.log.title_modified") if modified else ""
            
            # 检查是否是媒体组格式的ID
            if isinstance(source_message_id, str) and source_message_id.startswith("媒体组"):
                # 媒体组格式：显示"媒体组发送成功"
                forward_info = tr("ui.listen.log.media_group_forward", 
                                media_group=source_message_id,
                                source=source_display_name,
                                target=target_display_name,
                                status=status,
                                modified=mod_info)
            else:
                # 单条消息格式：使用传统的"消息[ID]"格式
                if success:
                    forward_info = tr("ui.listen.log.forward_success",
                                    message_id=source_message_id,
                                    source=source_display_name,
                                    target=target_display_name,
                                    modified=mod_info)
                else:
                    forward_info = tr("ui.listen.log.forward_failed",
                                    message_id=source_message_id,
                                    source=source_display_name,
                                    target=target_display_name,
                                    modified=mod_info)
            
            # 添加到主消息面板（所有消息）
            self._add_forward_item(forward_info, success)
            
            # 添加到对应源频道的标签页
            logger.debug(f"尝试为源频道匹配标签页: source_display_name='{source_display_name}'")
            logger.debug(f"可用的频道标签页: {list(self.channel_message_views.keys())}")
            
            # 添加详细的匹配调试信息
            for i, (source_channel, view) in enumerate(self.channel_message_views.items()):
                logger.debug(f"频道标签页 {i+1}: key='{source_channel}', type={type(source_channel)}")
            
            matched_channel = None
            for source_channel, view in self.channel_message_views.items():
                # 调试每个匹配尝试
                logger.debug(f"尝试匹配: source_channel='{source_channel}' vs source_display_name='{source_display_name}'")
                
                # 改进的匹配逻辑
                if self._is_channel_match(source_channel, source_display_name):
                    matched_channel = source_channel
                    time_str = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
                    status_text = tr("ui.listen.messages.forward_success") if success else tr("ui.listen.messages.forward_failed")
                    formatted_msg = f"[{time_str}] [{tr('ui.listen.messages.forward')}{status_text}] {forward_info}"
                    view.append(formatted_msg)
                    
                    # 如果转发成功，添加分割线
                    if success:
                        separator = tr("ui.listen.log.separator")
                        view.append(separator)
                    
                    view.moveCursor(QTextCursor.End)
                    
                    # 限制消息数量
                    max_messages = 200
                    doc = view.document()
                    if doc.blockCount() > max_messages:
                        cursor = QTextCursor(doc)
                        cursor.movePosition(QTextCursor.Start)
                        cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
                        cursor.removeSelectedText()
                        cursor.deleteChar()  # 删除换行符
                    
                    logger.debug(f"成功匹配到频道标签页: {source_channel}")
                    break
            
            if not matched_channel:
                logger.warning(f"未找到匹配的频道标签页，source_display_name: {source_display_name}")
                
                # 直接为接收到的频道创建标签页
                logger.info("开始为新频道创建标签页...")
                try:
                    # 从显示名称中提取ID
                    import re
                    display_id = None
                    id_match = re.search(r'\(ID:\s*(-?\d+)\)', source_display_name)
                    if id_match:
                        display_id = id_match.group(1)
                        logger.info(f"从显示名称提取的ID: {display_id}")
                        
                        # 直接为这个ID创建标签页
                        if display_id and display_id not in self.channel_message_views:
                            logger.info(f"为频道ID {display_id} 创建新的标签页")
                            channel_view = QTextEdit()
                            channel_view.setReadOnly(True)
                            channel_view.setLineWrapMode(QTextEdit.WidgetWidth)
                            
                            # 从显示名称中提取频道名称作为标签页标题
                            channel_title = self._extract_channel_title_from_source_info(source_display_name)
                            
                            self.message_tabs.addTab(channel_view, channel_title)
                            self.channel_message_views[display_id] = channel_view
                            
                            logger.info(f"成功创建标签页: {channel_title} -> {display_id}")
                            
                        # 添加消息到标签页
                        if display_id and display_id in self.channel_message_views:
                            view = self.channel_message_views[display_id]
                            time_str = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
                            status_text = tr("ui.listen.messages.forward_success") if success else tr("ui.listen.messages.forward_failed")
                            formatted_msg = f"[{time_str}] [{tr('ui.listen.messages.forward')}{status_text}] {forward_info}"
                            view.append(formatted_msg)
                            
                            # 如果转发成功，添加分割线
                            if success:
                                separator = tr("ui.listen.log.separator")
                                view.append(separator)
                            
                            view.moveCursor(QTextCursor.End)
                            
                            # 限制消息数量
                            max_messages = 200
                            doc = view.document()
                            if doc.blockCount() > max_messages:
                                cursor = QTextCursor(doc)
                                cursor.movePosition(QTextCursor.Start)
                                cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
                                cursor.removeSelectedText()
                                cursor.deleteChar()  # 删除换行符
                            
                            logger.info(f"成功在标签页 {display_id} 中添加转发消息")
                            matched_channel = display_id
                        else:
                            logger.warning(f"无法找到或创建频道ID {display_id} 的标签页")
                    else:
                        logger.info("无法从显示名称中提取ID，尝试使用完整显示名称作为key")
                        # 如果无法提取ID，直接使用显示名称作为key
                        if source_display_name not in self.channel_message_views:
                            logger.info(f"为显示名称 '{source_display_name}' 创建新的标签页")
                            channel_view = QTextEdit()
                            channel_view.setReadOnly(True)
                            channel_view.setLineWrapMode(QTextEdit.WidgetWidth)
                            
                            # 使用智能提取的频道名称作为标签页标题
                            channel_title = self._extract_channel_title_from_source_info(source_display_name)
                            
                            self.message_tabs.addTab(channel_view, channel_title)
                            self.channel_message_views[source_display_name] = channel_view
                            
                            logger.info(f"成功创建标签页: {channel_title} -> {source_display_name}")
                            
                        # 添加消息到标签页
                        view = self.channel_message_views[source_display_name]
                        time_str = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
                        status_text = tr("ui.listen.messages.forward_success") if success else tr("ui.listen.messages.forward_failed")
                        formatted_msg = f"[{time_str}] [{tr('ui.listen.messages.forward')}{status_text}] {forward_info}"
                        view.append(formatted_msg)
                        
                        # 如果转发成功，添加分割线
                        if success:
                            separator = tr("ui.listen.log.separator")
                            view.append(separator)
                        
                        view.moveCursor(QTextCursor.End)
                        
                        logger.info(f"成功在标签页 '{source_display_name}' 中添加转发消息")
                        matched_channel = source_display_name
                        
                except Exception as e:
                    logger.error(f"创建新标签页时发生错误: {e}")
            
            logger.debug(f"处理转发更新信号: {forward_info}")
        except Exception as e:
            logger.error(f"处理转发更新信号时出错: {e}")
    
    def _add_forward_item(self, forward_info, success=True):
        """添加转发项到消息面板
        
        Args:
            forward_info: 转发信息
            success: 是否成功转发
        """
        # 使用现有的消息显示机制
        time_str = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
        formatted_msg = f"[{time_str}] [{tr('ui.listen.messages.forward')}] {forward_info}"
        
        # 添加到主消息面板
        self.main_message_view.append(formatted_msg)
        
        # 如果转发成功，添加分割线
        if success:
            separator = tr("ui.listen.log.separator")
            self.main_message_view.append(separator)
        
        # 自动滚动到底部
        self.main_message_view.moveCursor(QTextCursor.End)
        
        # 限制消息数量
        max_messages = 200
        doc = self.main_message_view.document()
        if doc.blockCount() > max_messages:
            cursor = QTextCursor(doc)
            cursor.movePosition(QTextCursor.Start)
            cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            cursor.removeSelectedText()
            cursor.deleteChar()  # 删除换行符
    
    def _is_channel_match(self, source_channel, source_display_name):
        """检查源频道是否匹配显示名称
        
        Args:
            source_channel: 配置中的源频道（可能是ID、链接等）
            source_display_name: 显示名称（格式化后的频道信息）
            
        Returns:
            bool: 是否匹配
        """
        logger.debug(f"    开始匹配: source_channel='{source_channel}' (类型: {type(source_channel)}) vs source_display_name='{source_display_name}' (类型: {type(source_display_name)})")
        
        # 1. 直接匹配
        if source_channel == source_display_name:
            logger.debug(f"    ✓ 直接匹配成功")
            return True
        logger.debug(f"    ✗ 直接匹配失败")
        
        # 2. 互相包含匹配
        if (source_channel in source_display_name or 
            source_display_name in source_channel):
            logger.debug(f"    ✓ 包含匹配成功")
            return True
        logger.debug(f"    ✗ 包含匹配失败")
        
        # 3. 去除@符号的匹配
        clean_source = source_channel.replace('@', '')
        clean_display = source_display_name.replace('@', '')
        if (clean_source in clean_display or 
            clean_display in clean_source):
            logger.debug(f"    ✓ 清理@后匹配成功: '{clean_source}' vs '{clean_display}'")
            return True
        logger.debug(f"    ✗ 清理@后匹配失败: '{clean_source}' vs '{clean_display}'")
        
        # 4. 提取ID进行匹配（处理类似"-1002382449514"的ID）
        import re
        
        # 从source_channel提取ID
        source_id = None
        if source_channel.startswith('-') and source_channel[1:].isdigit():
            source_id = source_channel
        elif source_channel.isdigit():
            source_id = source_channel
        elif 't.me/' in source_channel:
            # 从链接中提取用户名或ID
            parts = source_channel.split('/')
            if parts:
                last_part = parts[-1]
                if last_part.startswith('-') and last_part[1:].isdigit():
                    source_id = last_part
        
        logger.debug(f"    提取的source_id: '{source_id}'")
        
        # 从source_display_name提取ID (格式如 "频道名 (ID: -1002382449514)")
        display_id = None
        id_match = re.search(r'\(ID:\s*(-?\d+)\)', source_display_name)
        if id_match:
            display_id = id_match.group(1)
        
        logger.debug(f"    提取的display_id: '{display_id}'")
        
        # ID匹配
        if source_id and display_id and source_id == display_id:
            logger.debug(f"    ✓ ID匹配成功: {source_id} == {display_id}")
            return True
        logger.debug(f"    ✗ ID匹配失败: {source_id} != {display_id}")
        
        # 5. 反向ID匹配：如果display_name中有ID，但source_channel没有ID，
        #    可能是用户界面中使用ID作为source_channel，但显示时转换为了友好名称
        if display_id and not source_id:
            # 检查是否source_channel可能是这个ID的其他表示形式
            # 比如用户在界面上输入"-1002382449514"，然后在运行时显示为"频道名 (ID: -1002382449514)"
            logger.debug(f"    尝试反向ID匹配: display_id='{display_id}' vs source_channel='{source_channel}'")
            
            # 检查source_channel是否是display_id去掉前缀
            if display_id.startswith('-100') and source_channel == display_id[4:]:
                logger.debug(f"    ✓ 反向ID匹配成功: {source_channel} == {display_id[4:]}")
                return True
        
        # 6. 特殊情况：如果source_channel看起来像是一个纯数字ID，尝试添加-100前缀匹配
        if source_channel.isdigit() and display_id:
            full_id = f"-100{source_channel}"
            if full_id == display_id:
                logger.debug(f"    ✓ 完整ID匹配成功: {full_id} == {display_id}")
                return True
        
        # 7. 频道用户名匹配（处理@username格式）
        source_username = None
        if source_channel.startswith('@'):
            source_username = source_channel[1:]
        elif 't.me/' in source_channel and not source_channel.split('/')[-1].startswith('-'):
            source_username = source_channel.split('/')[-1]
        
        logger.debug(f"    提取的source_username: '{source_username}'")
        
        if source_username:
            # 检查显示名称中是否包含用户名
            if f"@{source_username}" in source_display_name:
                logger.debug(f"    ✓ 用户名匹配成功: @{source_username}")
                return True
            # 检查显示名称中的链接
            if f"t.me/{source_username}" in source_display_name:
                logger.debug(f"    ✓ 链接匹配成功: t.me/{source_username}")
                return True
        logger.debug(f"    ✗ 用户名匹配失败")
        
        # 8. 频道标题匹配（从显示名称中提取标题部分）
        display_title = source_display_name
        if ' (ID:' in source_display_name:
            display_title = source_display_name.split(' (ID:')[0]
        
        logger.debug(f"    提取的display_title: '{display_title}'")
        
        # 检查source_channel是否就是频道标题
        if source_channel == display_title:
            logger.debug(f"    ✓ 标题匹配成功: {display_title}")
            return True
        logger.debug(f"    ✗ 标题匹配失败: '{source_channel}' != '{display_title}'")
        
        logger.debug(f"    ✗ 所有匹配方式都失败")
        return False
    
    def _update_status(self, status):
        """更新状态信息
        
        Args:
            status: 状态信息
        """
        self.main_message_view.append(status)
        logger.debug(f"监听状态更新: {status}")
    
    def _on_monitoring_started(self, channel_ids=None):
        """监听开始处理
        
        Args:
            channel_ids: 监听的频道ID列表(可选)
        """
        # 更新UI状态
        self.main_message_view.append(tr("ui.listen.status.listening"))
        
        # 禁用开始按钮，启用停止按钮
        self.start_listen_button.setEnabled(False)
        self.stop_listen_button.setEnabled(True)
        
        # 显示正在监听的频道
        if channel_ids:
            channels_str = ", ".join(str(c) for c in channel_ids)
            self.main_message_view.append(tr("ui.listen.messages.listening_channels", channels=channels_str))
        
        logger.info(tr("ui.listen.messages.listening_started"))
    
    def _on_monitoring_stopped(self):
        """监听停止处理"""
        # 更新UI状态
        self.main_message_view.append(tr("ui.listen.status.stopped"))
        
        # 启用开始按钮，禁用停止按钮
        self.start_listen_button.setEnabled(True)
        self.stop_listen_button.setEnabled(False)
        
        logger.info(tr("ui.listen.messages.listening_stopped"))
    
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
        
        # 添加到转发列表
        self._add_forward_item(forward_info)
        
        logger.debug(f"消息转发完成: {forward_info}")
    
    def _on_monitor_error(self, error, message=None):
        """监听错误处理
        
        Args:
            error: 错误信息
            message: 额外的消息(可选)
        """
        # 更新UI状态
        error_msg = tr("ui.listen.messages.monitor_error", error=str(error))
        if message:
            error_msg += f"\n{message}"
            
        self.main_message_view.append(error_msg)
        
        # 恢复按钮状态
        self.start_listen_button.setEnabled(True)
        self.stop_listen_button.setEnabled(False)
        
        # 显示错误对话框
        self._show_error_dialog(tr("ui.listen.messages.monitor_error_title"), error_msg)
        
        logger.error(f"监听错误: {error}")
        if message:
            logger.debug(f"错误详情: {message}")
    
    def _on_message_filtered(self, message_id, source_info, filter_reason):
        """处理被过滤的消息信号
        
        Args:
            message_id: 消息ID
            source_info: 源频道信息
            filter_reason: 过滤原因
        """
        try:
            # 构建过滤消息显示内容
            filter_content = tr("ui.listen.log.message_filtered", message_id=message_id, reason=filter_reason)
            
            # 添加到主消息面板
            time_str = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
            formatted_msg = f"[{time_str}] [{tr('ui.listen.messages.filtered')}] {source_info}: {filter_content}"
            
            self.main_message_view.append(formatted_msg)
            
            # 添加50个星号作为分隔符
            separator = "*" * 50
            self.main_message_view.append(separator)
            
            self.main_message_view.moveCursor(QTextCursor.End)
            
            # 添加到对应的频道标签页
            matched_channel = None
            for source_channel, view in self.channel_message_views.items():
                # 使用改进的匹配逻辑
                if self._is_channel_match(source_channel, source_info):
                    view.append(formatted_msg)
                    # 在频道标签页中也添加星号分隔符
                    view.append(separator)
                    view.moveCursor(QTextCursor.End)
                    
                    # 限制消息数量
                    max_messages = 200
                    doc = view.document()
                    if doc.blockCount() > max_messages:
                        cursor = QTextCursor(doc)
                        cursor.movePosition(QTextCursor.Start)
                        cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
                        cursor.removeSelectedText()
                        cursor.deleteChar()  # 删除换行符
                    
                    logger.debug(f"过滤消息已添加到频道标签页: {source_channel}")
                    matched_channel = source_channel
                    break
            
            # 如果没有匹配的标签页，创建新标签页
            if not matched_channel:
                self._create_channel_tab_for_filtered_message(source_info, formatted_msg, separator)
            
            # 限制主消息面板的消息数量
            max_messages = 200
            doc = self.main_message_view.document()
            if doc.blockCount() > max_messages:
                cursor = QTextCursor(doc)
                cursor.movePosition(QTextCursor.Start)
                cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
                cursor.removeSelectedText()
                cursor.deleteChar()  # 删除换行符
            
            logger.debug(f"处理过滤消息信号: {message_id} - {source_info} - {filter_reason}")
        except Exception as e:
            logger.error(f"处理过滤消息信号时出错: {e}")
    
    def _create_channel_tab_for_filtered_message(self, source_info, formatted_msg, separator):
        """为过滤消息创建频道标签页
        
        Args:
            source_info: 源频道信息
            formatted_msg: 格式化的消息
            separator: 星号分隔符
        """
        try:
            import re
            display_id = None
            id_match = re.search(r'\(ID:\s*(-?\d+)\)', source_info)
            if id_match:
                display_id = id_match.group(1)
                logger.info(f"从源信息提取的ID: {display_id}")
                
                # 直接为这个ID创建标签页
                if display_id and display_id not in self.channel_message_views:
                    logger.info(f"为频道ID {display_id} 创建新的标签页")
                    channel_view = QTextEdit()
                    channel_view.setReadOnly(True)
                    channel_view.setLineWrapMode(QTextEdit.WidgetWidth)
                    
                    # 从源信息中提取频道名称作为标签页标题
                    channel_title = self._extract_channel_title_from_source_info(source_info)
                    
                    self.message_tabs.addTab(channel_view, channel_title)
                    self.channel_message_views[display_id] = channel_view
                    
                    logger.info(f"成功创建标签页: {channel_title} -> {display_id}")
                    
                # 添加消息到标签页
                if display_id and display_id in self.channel_message_views:
                    view = self.channel_message_views[display_id]
                    view.append(formatted_msg)
                    # 在频道标签页中也添加星号分隔符
                    view.append(separator)
                    view.moveCursor(QTextCursor.End)
                    
                    # 限制消息数量
                    max_messages = 200
                    doc = view.document()
                    if doc.blockCount() > max_messages:
                        cursor = QTextCursor(doc)
                        cursor.movePosition(QTextCursor.Start)
                        cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
                        cursor.removeSelectedText()
                        cursor.deleteChar()  # 删除换行符
                    
                    logger.info(f"成功在标签页 {display_id} 中添加过滤消息")
            else:
                logger.info("无法从源信息中提取ID，使用完整源信息作为key")
                # 如果无法提取ID，直接使用源信息作为key
                if source_info not in self.channel_message_views:
                    logger.info(f"为源信息 '{source_info}' 创建新的标签页")
                    channel_view = QTextEdit()
                    channel_view.setReadOnly(True)
                    channel_view.setLineWrapMode(QTextEdit.WidgetWidth)
                    
                    # 使用智能提取的频道名称作为标签页标题
                    channel_title = self._extract_channel_title_from_source_info(source_info)
                    
                    self.message_tabs.addTab(channel_view, channel_title)
                    self.channel_message_views[source_info] = channel_view
                    
                    logger.info(f"成功创建标签页: {channel_title} -> {source_info}")
                    
                # 添加消息到标签页
                view = self.channel_message_views[source_info]
                view.append(formatted_msg)
                # 在频道标签页中也添加星号分隔符
                view.append(separator)
                view.moveCursor(QTextCursor.End)
                
                logger.info(f"成功在标签页 '{source_info}' 中添加过滤消息")
                
        except Exception as e:
            logger.error(f"为过滤消息创建标签页时发生错误: {e}")
    
    def _add_message_item(self, from_info, content):
        """添加消息项到消息面板
        
        Args:
            from_info: 来源信息
            content: 消息内容
        """
        # 使用现有的消息显示机制
        time_str = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
        formatted_msg = f"[{time_str}] {from_info}: {content}"
        
        # 添加到主消息面板
        self.main_message_view.append(formatted_msg)
        
        # 自动滚动到底部
        self.main_message_view.moveCursor(QTextCursor.End)
        
        # 限制消息数量
        max_messages = 200
        doc = self.main_message_view.document()
        if doc.blockCount() > max_messages:
            cursor = QTextCursor(doc)
            cursor.movePosition(QTextCursor.Start)
            cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            cursor.removeSelectedText()
            cursor.deleteChar()  # 删除换行符
    
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

    def _show_context_menu(self, pos):
        """显示右键菜单
        
        Args:
            pos: 鼠标位置
        """
        # 确保有选中的项目
        current_item = self.pairs_list.itemAt(pos)
        if not current_item:
            return
        
        # 创建菜单
        context_menu = QMenu(self)
        
        # 添加菜单项
        edit_action = context_menu.addAction(tr("ui.listen.context_menu.edit"))
        delete_action = context_menu.addAction(tr("ui.listen.context_menu.delete"))
        
        # 显示菜单并获取用户选择的操作
        action = context_menu.exec(QCursor.pos())
        
        # 处理用户选择
        if action == edit_action:
            self._edit_channel_pair(current_item)
        elif action == delete_action:
            # 删除操作直接调用已有的删除方法
            self._remove_channel_pairs()
    
    def _edit_channel_pair(self, item):
        """编辑监听频道对
        
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
        edit_dialog.setWindowTitle(tr("ui.listen.edit_dialog.title"))
        edit_dialog.setMinimumWidth(600)
        edit_dialog.setMinimumHeight(400)  # 降低最小高度，允许更小的窗口
        edit_dialog.resize(650, 700)  # 设置默认大小
        
        # 主布局 - 只包含滚动区域和按钮
        main_layout = QVBoxLayout(edit_dialog)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        
        # 创建滚动内容容器
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(15, 15, 15, 15)
        scroll_layout.setSpacing(15)
        
        # 基本信息表单
        basic_form = QFormLayout()
        basic_form.setSpacing(10)
        basic_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        # 源频道输入
        source_input = QLineEdit(channel_pair.get('source_channel', ''))
        source_input.setPlaceholderText(tr("ui.listen.channel_config.source_placeholder"))
        basic_form.addRow(tr("ui.listen.edit_dialog.source_channel"), source_input)
        
        # 目标频道输入
        target_channels = channel_pair.get('target_channels', [])
        target_input = QLineEdit(', '.join(target_channels))
        target_input.setPlaceholderText(tr("ui.listen.channel_config.target_placeholder"))
        basic_form.addRow(tr("ui.listen.edit_dialog.target_channels"), target_input)
        
        scroll_layout.addLayout(basic_form)
        
        # 文本替换规则组
        text_filter_group = QGroupBox(tr("ui.listen.edit_dialog.text_replacement_rules"))
        text_filter_layout = QFormLayout(text_filter_group)
        text_filter_layout.setSpacing(8)
        
        # 获取文本替换规则
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
        original_text_input.setPlaceholderText(tr("ui.listen.channel_config.original_text"))
        text_filter_layout.addRow(tr("ui.listen.edit_dialog.replace"), original_text_input)
        
        target_text_input = QLineEdit(', '.join(target_texts))
        target_text_input.setPlaceholderText(tr("ui.listen.channel_config.target_text"))
        text_filter_layout.addRow(tr("ui.listen.edit_dialog.replace_to"), target_text_input)
        
        scroll_layout.addWidget(text_filter_group)
        
        # 媒体类型选择组
        media_group = QGroupBox(tr("ui.listen.edit_dialog.media_types"))
        media_layout = QVBoxLayout(media_group)
        
        # 第一行媒体类型
        media_row1 = QHBoxLayout()
        photo_check = QCheckBox(tr("ui.listen.channel_config.media_types_photo"))
        video_check = QCheckBox(tr("ui.listen.channel_config.media_types_video"))
        document_check = QCheckBox(tr("ui.listen.channel_config.media_types_document"))
        audio_check = QCheckBox(tr("ui.listen.channel_config.media_types_audio"))
        
        media_row1.addWidget(photo_check)
        media_row1.addWidget(video_check)
        media_row1.addWidget(document_check)
        media_row1.addWidget(audio_check)
        media_row1.addStretch()
        
        # 第二行媒体类型
        media_row2 = QHBoxLayout()
        animation_check = QCheckBox(tr("ui.listen.channel_config.media_types_animation"))
        sticker_check = QCheckBox(tr("ui.listen.channel_config.media_types_sticker"))
        voice_check = QCheckBox(tr("ui.listen.channel_config.media_types_voice"))
        video_note_check = QCheckBox(tr("ui.listen.channel_config.media_types_video_note"))
        
        media_row2.addWidget(animation_check)
        media_row2.addWidget(sticker_check)
        media_row2.addWidget(voice_check)
        media_row2.addWidget(video_note_check)
        media_row2.addStretch()
        
        media_layout.addLayout(media_row1)
        media_layout.addLayout(media_row2)
        
        # 设置当前媒体类型
        media_types = channel_pair.get('media_types', [])
        media_types_str = [str(t) for t in media_types]
        
        photo_check.setChecked(MediaType.PHOTO in media_types_str)
        video_check.setChecked(MediaType.VIDEO in media_types_str)
        document_check.setChecked(MediaType.DOCUMENT in media_types_str)
        audio_check.setChecked(MediaType.AUDIO in media_types_str)
        animation_check.setChecked(MediaType.ANIMATION in media_types_str)
        sticker_check.setChecked(MediaType.STICKER in media_types_str)
        voice_check.setChecked(MediaType.VOICE in media_types_str)
        video_note_check.setChecked(MediaType.VIDEO_NOTE in media_types_str)
        
        scroll_layout.addWidget(media_group)
        
        # 过滤选项组
        filter_group = QGroupBox(tr("ui.listen.edit_dialog.filter_options"))
        filter_layout = QVBoxLayout(filter_group)
        
        # 关键词输入
        keywords_layout = QFormLayout()
        keywords = channel_pair.get('keywords', [])
        
        # 关键词输入框和备注布局
        keywords_input_layout = QHBoxLayout()
        keywords_input_layout.setSpacing(8)
        
        keywords_input = QLineEdit(', '.join(keywords))
        keywords_input.setPlaceholderText(tr("ui.listen.edit_dialog.keywords_placeholder"))
        keywords_input.setMinimumWidth(400)  # 设置最小宽度为400像素
        keywords_input_layout.addWidget(keywords_input)
        
        # 添加弹性空间，让备注文字靠近输入框
        keywords_input_layout.addStretch(1)
        
        keywords_layout.addRow(tr("ui.listen.edit_dialog.keywords"), keywords_input_layout)
        filter_layout.addLayout(keywords_layout)
        
        # 排除选项
        exclude_layout = QHBoxLayout()
        
        exclude_forwards_check = QCheckBox(tr("ui.listen.channel_config.exclude_forwards"))
        exclude_forwards_check.setChecked(channel_pair.get('exclude_forwards', False))
        exclude_layout.addWidget(exclude_forwards_check)
        
        exclude_replies_check = QCheckBox(tr("ui.listen.channel_config.exclude_replies"))
        exclude_replies_check.setChecked(channel_pair.get('exclude_replies', False))
        exclude_layout.addWidget(exclude_replies_check)
        
        exclude_text_check = QCheckBox(tr("ui.listen.channel_config.exclude_text"))
        # 兼容性处理：先尝试读取exclude_text，如果没有则从exclude_media转换
        exclude_text_value = channel_pair.get('exclude_text', channel_pair.get('exclude_media', False))
        exclude_text_check.setChecked(exclude_text_value)
        exclude_layout.addWidget(exclude_text_check)
        
        exclude_links_check = QCheckBox(tr("ui.listen.channel_config.exclude_links"))
        exclude_links_check.setChecked(channel_pair.get('exclude_links', False))
        exclude_layout.addWidget(exclude_links_check)
        
        exclude_layout.addStretch()
        filter_layout.addLayout(exclude_layout)
        
        scroll_layout.addWidget(filter_group)
        
        # 其他选项组
        other_group = QGroupBox(tr("ui.listen.edit_dialog.other_options"))
        other_layout = QVBoxLayout(other_group)
        
        remove_captions_check = QCheckBox(tr("ui.listen.edit_dialog.remove_captions"))
        remove_captions_check.setChecked(channel_pair.get('remove_captions', False))
        other_layout.addWidget(remove_captions_check)
        
        scroll_layout.addWidget(other_group)
        
        # 添加弹性空间，确保内容顶部对齐
        scroll_layout.addStretch()
        
        # 设置滚动区域的内容
        scroll_area.setWidget(scroll_content)
        
        # 将滚动区域添加到主布局
        main_layout.addWidget(scroll_area, 1)  # 使用伸展因子让滚动区域占据主要空间
        
        # 按钮布局 - 固定在底部，不在滚动区域内
        button_layout = QHBoxLayout()
        save_button = QPushButton(tr("ui.listen.edit_dialog.save"))
        cancel_button = QPushButton(tr("ui.listen.edit_dialog.cancel"))
        
        save_button.setMinimumHeight(35)
        cancel_button.setMinimumHeight(35)
        save_button.setMinimumWidth(80)
        cancel_button.setMinimumWidth(80)
        
        button_layout.addStretch(1)
        button_layout.addWidget(save_button)
        button_layout.addSpacing(10)
        button_layout.addWidget(cancel_button)
        
        # 将按钮布局添加到主布局，不使用伸展因子，固定在底部
        main_layout.addLayout(button_layout)
        
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
                    raise ValueError(tr("ui.listen.edit_dialog.source_empty"))
                if not new_targets:
                    raise ValueError(tr("ui.listen.edit_dialog.target_empty"))
                
                # 收集媒体类型
                new_media_types = []
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
                if sticker_check.isChecked():
                    new_media_types.append(MediaType.STICKER)
                if voice_check.isChecked():
                    new_media_types.append(MediaType.VOICE)
                if video_note_check.isChecked():
                    new_media_types.append(MediaType.VIDEO_NOTE)
                
                if not new_media_types:
                    raise ValueError(tr("ui.listen.edit_dialog.media_type_required"))
                
                # 收集文本替换规则
                original_texts = [t.strip() for t in original_text_input.text().split(',') if t.strip()]
                target_texts = [t.strip() for t in target_text_input.text().split(',') if t.strip()]
                
                new_text_filter = []
                # 确保原始文本和目标文本数量匹配
                max_len = max(len(original_texts), len(target_texts))
                for i in range(max_len):
                    original = original_texts[i] if i < len(original_texts) else ""
                    target = target_texts[i] if i < len(target_texts) else ""
                    if original or target:
                        new_text_filter.append({
                            "original_text": original,
                            "target_text": target
                        })
                
                # 如果没有文本替换规则，添加一个空的
                if not new_text_filter:
                    new_text_filter = [{"original_text": "", "target_text": ""}]
                
                # 收集关键词
                keywords_text = keywords_input.text().strip()
                new_keywords = [k.strip() for k in keywords_text.split(',') if k.strip()] if keywords_text else []
                
                # 使用UIMonitorChannelPair进行验证
                from src.utils.ui_config_models import UIChannelPair
                validated_source = UIChannelPair.validate_channel_id(new_source, "源频道")
                validated_targets = [UIChannelPair.validate_channel_id(t, f"目标频道 {i+1}") 
                                    for i, t in enumerate(new_targets)]
                
                # 创建更新后的频道对
                updated_pair = {
                    'source_channel': validated_source,
                    'target_channels': validated_targets,
                    'remove_captions': remove_captions_check.isChecked(),
                    'text_filter': new_text_filter,
                    'media_types': new_media_types,
                    'keywords': new_keywords,
                    'exclude_forwards': exclude_forwards_check.isChecked(),
                    'exclude_replies': exclude_replies_check.isChecked(),
                    'exclude_text': exclude_text_check.isChecked(),
                    'exclude_links': exclude_links_check.isChecked(),
                    'start_id': channel_pair.get('start_id', 0),
                    'end_id': channel_pair.get('end_id', 0)
                }
                
                # 更新列表项和数据
                self._update_channel_pair(row, updated_pair)
                
            except ValueError as e:
                QMessageBox.warning(self, tr("ui.listen.messages.input_error"), str(e))
    
    def _update_channel_pair(self, row, updated_pair):
        """更新频道对
        
        Args:
            row: 行索引
            updated_pair: 更新后的频道对数据
        """
        try:
            # 获取要更新的列表项
            item = self.pairs_list.item(row)
            if not item:
                logger.error(f"无法找到行索引为 {row} 的列表项")
                return
            
            # 构建显示文本
            source_channel = updated_pair['source_channel']
            target_channels = updated_pair['target_channels']
            target_channels_str = ', '.join(target_channels)
            
            # 格式化文本替换规则显示
            text_filter_str = self._format_text_filter_display(updated_pair.get('text_filter', []))
            
            # 格式化媒体类型显示
            media_types_str = self._format_media_types_display(updated_pair.get('media_types', []))
            
            # 格式化过滤选项显示
            filter_options_str = self._format_filter_options_display(
                updated_pair.get('keywords', []),
                updated_pair.get('exclude_forwards', False),
                updated_pair.get('exclude_replies', False),
                updated_pair.get('exclude_text', False),
                updated_pair.get('exclude_links', False)
            )
            
            # 构建完整显示文本
            display_text = f"{source_channel} -> {target_channels_str}{text_filter_str}{media_types_str}{filter_options_str}"
            if updated_pair.get('remove_captions', False):
                display_text += tr("ui.listen.display.remove_captions_suffix")
            
            # 更新列表项
            item.setText(display_text)
            item.setData(Qt.UserRole, updated_pair)
            
            # 记录日志
            logger.debug(f"频道对已更新: {display_text}")
            
            # 显示成功消息
            QMessageBox.information(self, tr("ui.listen.messages.success"), tr("ui.listen.edit_dialog.update_success"))
            
        except Exception as e:
            logger.error(f"更新频道对时出错: {e}")
            QMessageBox.warning(self, tr("ui.listen.messages.error"), tr("ui.listen.edit_dialog.update_failed", error=str(e)))
    
    def _extract_channel_title_from_source_info(self, source_info: str) -> str:
        """从源信息中智能提取频道名称作为标签页标题
        
        Args:
            source_info: 源信息字符串，可能的格式：
                - "频道名称 (ID: -1001234567890)"
                - "@username (ID: -1001234567890)"
                - "-1001234567890"
                - "@username"
                - "https://t.me/username"
                
        Returns:
            str: 提取的频道名称，适合作为标签页标题
        """
        if not source_info:
            return tr("ui.listen.display.unknown_channel")
            
        # 去除首尾空格
        source_info = source_info.strip()
        
        # 情况1: 标准格式 "频道名称 (ID: -1001234567890)"
        if ' (ID:' in source_info:
            channel_title = source_info.split(' (ID:')[0].strip()
            if channel_title and not channel_title.isdigit() and not (channel_title.startswith('-') and channel_title[1:].isdigit()):
                # 限制标签页标题长度，避免过长
                if len(channel_title) > 20:
                    return channel_title[:20] + "..."
                return channel_title
        
        # 情况2: 纯数字ID "-1001234567890"
        if source_info.isdigit() or (source_info.startswith('-') and source_info[1:].isdigit()):
            return tr("ui.listen.display.channel_prefix", id=source_info)
        
        # 情况3: @username格式
        if source_info.startswith('@'):
            username = source_info[1:]  # 去掉@符号
            if len(username) > 20:
                return f"@{username[:17]}..."
            return source_info
        
        # 情况4: https://t.me/username格式
        if source_info.startswith('https://t.me/'):
            import re
            match = re.search(r'https://t\.me/([^/\s]+)', source_info)
            if match:
                username = match.group(1)
                if len(username) > 20:
                    return f"@{username[:17]}..."
                return f"@{username}"
        
        # 情况5: 其他格式，直接使用但限制长度
        if len(source_info) > 20:
            return source_info[:20] + "..."
        
        return source_info
    
    def _update_translations(self):
        """更新所有翻译文本，支持动态语言切换"""
        try:
            # 正确刷新四个主Tab标题
            if hasattr(self, 'config_tabs') and self.config_tabs:
                self.config_tabs.setTabText(0, tr("ui.listen.tabs.channel_config"))
                self.config_tabs.setTabText(1, tr("ui.listen.tabs.general_config"))
                self.config_tabs.setTabText(2, tr("ui.listen.tabs.monitor_log"))
                if self.config_tabs.count() > 3:
                    self.config_tabs.setTabText(3, tr("ui.listen.tabs.performance"))
            # 通用配置选项卡标题和表单label
            if hasattr(self, 'translatable_widgets') and 'labels' in self.translatable_widgets:
                if 'general_config_title' in self.translatable_widgets['labels']:
                    self.translatable_widgets['labels']['general_config_title'].setText(tr("ui.listen.general_config.title"))
                if 'duration' in self.translatable_widgets['labels']:
                    self.translatable_widgets['labels']['duration'].setText(tr("ui.listen.general_config.duration_label"))
            # 监听日志 ALL messages 标签
            if hasattr(self, 'message_tabs') and self.message_tabs:
                if self.message_tabs.count() > 0:
                    self.message_tabs.setTabText(0, tr("ui.listen.monitor_log.all_messages"))
            # 性能监控子标题刷新
            if hasattr(self, 'performance_tab') and hasattr(self.performance_tab, '_update_translations'):
                self.performance_tab._update_translations()
            # 更新标签文本
            if hasattr(self, 'translatable_widgets'):
                # 更新按钮
                for button_name, button in self.translatable_widgets.get('buttons', {}).items():
                    if button_name == 'add_channel_pair':
                        button.setText(tr("ui.listen.channel_config.add_channel_pair"))
                    elif button_name == 'remove_selected':
                        button.setText(tr("ui.listen.channel_config.remove_selected"))
                    elif button_name == 'start_listen':
                        button.setText(tr("ui.listen.buttons.start_listen"))
                    elif button_name == 'stop_listen':
                        button.setText(tr("ui.listen.buttons.stop_listen"))
                    elif button_name == 'save_config':
                        button.setText(tr("ui.listen.buttons.save_config"))
                    elif button_name == 'clear_messages':
                        button.setText(tr("ui.listen.buttons.clear_messages"))
                
                # 更新标签文本
                for label_name, label in self.translatable_widgets.get('labels', {}).items():
                    if label_name == 'source_channel':
                        label.setText(tr("ui.listen.channel_config.source_channel"))
                    elif label_name == 'target_channels':
                        label.setText(tr("ui.listen.channel_config.target_channels"))
                    elif label_name == 'original_text':
                        label.setText(tr("ui.listen.channel_config.original_text"))
                    elif label_name == 'target_text':
                        label.setText(tr("ui.listen.channel_config.target_text"))
                    elif label_name == 'filter_options':
                        label.setText(tr("ui.listen.channel_config.filter_options"))
                    elif label_name == 'keywords':
                        label.setText(tr("ui.listen.channel_config.keywords"))
                    elif label_name == 'media_types':
                        label.setText(tr("ui.listen.channel_config.media_types"))
                    elif label_name == 'monitor_params':
                        label.setText(tr("ui.listen.channel_config.monitor_params"))
                    elif label_name == 'configured_pairs':
                        label.setText(tr("ui.listen.channel_config.configured_pairs", count=self.pairs_list.count()))
                    elif label_name == 'general_config':
                        label.setText(tr("ui.listen.general_config.title"))
                    elif label_name == 'enable_duration':
                        label.setText(tr("ui.listen.general_config.enable_duration"))
                    elif label_name == 'duration_label':
                        label.setText(tr("ui.listen.general_config.duration_label"))
                    elif label_name == 'monitor_log':
                        label.setText(tr("ui.listen.monitor_log.title"))
                
                # 更新输入框占位符
                for input_name, input_widget in self.translatable_widgets.get('inputs', {}).items():
                    if input_name == 'source_channel':
                        input_widget.setPlaceholderText(tr("ui.listen.channel_config.source_placeholder"))
                    elif input_name == 'target_channels':
                        input_widget.setPlaceholderText(tr("ui.listen.channel_config.target_placeholder"))
                    elif input_name == 'original_text':
                        input_widget.setPlaceholderText(tr("ui.listen.channel_config.original_text"))
                    elif input_name == 'target_text':
                        input_widget.setPlaceholderText(tr("ui.listen.channel_config.target_text_placeholder"))
                    elif input_name == 'keywords':
                        input_widget.setPlaceholderText(tr("ui.listen.channel_config.keywords_placeholder"))
                
                # 更新复选框文本
                for checkbox_name, checkbox in self.translatable_widgets.get('checkboxes', {}).items():
                    if checkbox_name == 'exclude_forwards':
                        checkbox.setText(tr("ui.listen.channel_config.exclude_forwards"))
                    elif checkbox_name == 'exclude_replies':
                        checkbox.setText(tr("ui.listen.channel_config.exclude_replies"))
                    elif checkbox_name == 'exclude_text':
                        checkbox.setText(tr("ui.listen.channel_config.exclude_text"))
                    elif checkbox_name == 'exclude_links':
                        checkbox.setText(tr("ui.listen.channel_config.exclude_links"))
                    elif checkbox_name == 'remove_captions':
                        checkbox.setText(tr("ui.listen.channel_config.remove_captions"))
                    elif checkbox_name == 'enable_duration':
                        checkbox.setText(tr("ui.listen.general_config.enable_duration"))
                    elif checkbox_name.startswith('media_'):
                        media_type = checkbox_name.replace('media_', '')
                        checkbox.setText(tr(f"ui.listen.channel_config.media_types_{media_type}"))
                
                # 更新标签页容器文本
                for tab_name, tab_widget in self.translatable_widgets.get('tabs', {}).items():
                    if hasattr(tab_widget, 'setTitle'):
                        if tab_name == 'all_messages':
                            tab_widget.setTitle(tr("ui.listen.monitor_log.all_messages"))
            
            # 更新状态显示
            if hasattr(self, 'status_label') and self.status_label:
                current_text = self.status_label.text()
                if "监听中" in current_text or "Monitoring" in current_text:
                    self.status_label.setText(tr("ui.listen.status.listening"))
                elif "已停止" in current_text or "Stopped" in current_text:
                    self.status_label.setText(tr("ui.listen.status.stopped"))
                elif "准备中" in current_text or "Preparing" in current_text:
                    self.status_label.setText(tr("ui.listen.status.preparing"))
                elif "就绪" in current_text or "Ready" in current_text:
                    self.status_label.setText(tr("ui.listen.status.ready"))
                elif "错误" in current_text or "Error" in current_text:
                    self.status_label.setText(tr("ui.listen.status.error"))
            
            logger.debug("监听界面翻译已更新")
            
            # 新增：刷新已配置频道对列表内容
            for i in range(self.pairs_list.count()):
                item = self.pairs_list.item(i)
                data = item.data(Qt.UserRole)
                source_channel = data.get('source_channel', '')
                target_channels = data.get('target_channels', [])
                target_channels_str = ', '.join(target_channels)
                text_filter_str = self._format_text_filter_display(data.get('text_filter', []))
                media_types_str = self._format_media_types_display(data.get('media_types', []))
                filter_options_str = self._format_filter_options_display(
                    data.get('keywords', []),
                    data.get('exclude_forwards', False),
                    data.get('exclude_replies', False),
                    data.get('exclude_text', False),
                    data.get('exclude_links', False)
                )
                display_text = f"{source_channel} -> {target_channels_str}{text_filter_str}{media_types_str}{filter_options_str}"
                if data.get('remove_captions', False):
                    display_text += tr("ui.listen.display.remove_captions_suffix")
                item.setText(display_text)
            
            # 修正"文本替换"label
            if hasattr(self, 'original_text_label'):
                self.original_text_label.setText(tr("ui.listen.channel_config.text_replacement"))
            # 性能监控主标题和分组刷新
            if hasattr(self, 'performance_tab') and hasattr(self.performance_tab, '_update_translations'):
                self.performance_tab._update_translations()
            # 性能监控Tab标签栏
            if hasattr(self, 'config_tabs') and self.config_tabs.count() > 3:
                self.config_tabs.setTabText(3, tr("ui.listen.tabs.performance"))
            # 性能监控内容区主标题
            if hasattr(self, 'performance_tab') and hasattr(self.performance_tab, 'title_label'):
                self.performance_tab.title_label.setText(tr("ui.listen.tabs.performance"))
            # 详细统计分组QGroupBox
            if hasattr(self, 'performance_tab') and hasattr(self.performance_tab, 'main_layout'):
                item = self.performance_tab.main_layout.itemAt(5)
                if item and item.widget():
                    item.widget().setTitle(tr("ui.performance_monitor.details"))
            # 详细统计分组内QLabel
            if hasattr(self, 'performance_tab') and hasattr(self.performance_tab, 'details_title_label'):
                self.performance_tab.details_title_label.setText(tr("ui.performance_monitor.details"))
        except Exception as e:
            logger.error(f"更新监听界面翻译时出错: {e}")
            logger.debug(f"翻译更新异常详情: {e}", exc_info=True)