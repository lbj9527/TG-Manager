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
        
        # 设置布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(8)  # 增加主布局的垂直间距
        self.main_layout.setContentsMargins(8, 8, 8, 8)  # 增加主布局边距
        self.setLayout(self.main_layout)
        
        # # 统一设置群组框样式，减小标题高度
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
        
        # 界面组件创建完成后再加载配置
        if self.config:
            self.load_config(self.config)
        
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
        
        # 创建顶部表单面板 - 直接添加到配置布局，移除QGroupBox
        form_layout = QFormLayout()
        form_layout.setSpacing(10)  # 增加表单项间距
        form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)  # 标签右对齐
        form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)  # 字段可扩展
        
        # 源频道
        self.source_channel_input = QLineEdit()
        self.source_channel_input.setPlaceholderText("频道链接或ID (例如: https://t.me/example 或 -1001234567890)")
        form_layout.addRow("源频道:", self.source_channel_input)
        
        # 目标频道
        self.target_channel_input = QLineEdit()
        self.target_channel_input.setPlaceholderText("目标频道链接或ID (多个频道用逗号分隔)")
        form_layout.addRow("目标频道:", self.target_channel_input)
        
        # 文本替换规则
        self.original_text_input = QLineEdit()
        self.original_text_input.setPlaceholderText("要替换的原始文本，多个用逗号分隔如：A,B")
        form_layout.addRow("文本替换:", self.original_text_input)
        
        self.target_text_input = QLineEdit()
        self.target_text_input.setPlaceholderText("替换后的目标文本，多个用逗号分隔如：C,D")
        form_layout.addRow("替换为:", self.target_text_input)
        
        # 将表单直接添加到配置布局
        config_layout.addLayout(form_layout)
        
        # 添加一些间距
        config_layout.addSpacing(6)
        
        # 监听参数 - 将标签和移除媒体说明放在同一行
        monitor_options_layout = QHBoxLayout()
        monitor_options_layout.setSpacing(10)  # 设置合适的间距
        
        # 监听参数标签
        monitor_options_label = QLabel("监听参数:")
        monitor_options_label.setStyleSheet("font-weight: bold;")
        monitor_options_layout.addWidget(monitor_options_label)
        
        # 移除媒体说明复选框
        self.remove_captions_check = QCheckBox("移除媒体说明")
        self.remove_captions_check.setStyleSheet("padding: 4px;")  # 添加内边距
        monitor_options_layout.addWidget(self.remove_captions_check)
        
        # 添加弹性空间，让控件靠左对齐
        monitor_options_layout.addStretch(1)
        
        # 添加到配置布局
        config_layout.addLayout(monitor_options_layout)
        
        # 添加一些间距
        config_layout.addSpacing(6)
        
        # 过滤选项
        filter_options_label = QLabel("过滤选项:")
        filter_options_label.setStyleSheet("font-weight: bold;")
        config_layout.addWidget(filter_options_label)
        
        # 关键词过滤
        filter_layout = QFormLayout()
        filter_layout.setSpacing(8)
        filter_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("输入关键词，多个关键词用逗号分隔")
        filter_layout.addRow("关键词:", self.keyword_input)
        
        # 媒体类型选择 - 移动到过滤选项中
        self.media_types_checkboxes = {}
        
        # 所有媒体类型在同一行
        self.media_types_checkboxes["photo"] = QCheckBox("照片")
        self.media_types_checkboxes["video"] = QCheckBox("视频")
        self.media_types_checkboxes["document"] = QCheckBox("文件")
        self.media_types_checkboxes["audio"] = QCheckBox("音频")
        self.media_types_checkboxes["animation"] = QCheckBox("动画")
        self.media_types_checkboxes["sticker"] = QCheckBox("贴纸")
        self.media_types_checkboxes["voice"] = QCheckBox("语音")
        self.media_types_checkboxes["video_note"] = QCheckBox("视频笔记")
        
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
        filter_layout.addRow("媒体类型:", media_types_layout)
        
        # 过滤复选框 - 将四个复选框放在同一行
        filter_checkboxes_layout = QHBoxLayout()
        
        self.exclude_forwards_check = QCheckBox("排除转发消息")
        self.exclude_replies_check = QCheckBox("排除回复消息")
        self.exclude_media_check = QCheckBox("排除媒体消息")
        self.exclude_links_check = QCheckBox("排除包含链接的消息")
        
        filter_checkboxes_layout.addWidget(self.exclude_forwards_check)
        filter_checkboxes_layout.addWidget(self.exclude_replies_check)
        filter_checkboxes_layout.addWidget(self.exclude_media_check)
        filter_checkboxes_layout.addWidget(self.exclude_links_check)
        filter_checkboxes_layout.addStretch(1)  # 添加弹性空间，让复选框靠左对齐
        
        config_layout.addLayout(filter_layout)
        config_layout.addLayout(filter_checkboxes_layout)
        
        # 添加一些间距
        config_layout.addSpacing(8)
        
        # 频道对操作按钮 - 移动到这里，放在已配置监听频道对标签上方
        channel_action_layout = QHBoxLayout()
        channel_action_layout.setSpacing(8)  # 增加按钮间距
        
        # 添加频道对按钮
        self.add_channel_pair_button = QPushButton("添加频道对")
        self.add_channel_pair_button.setMinimumHeight(28)  # 增加按钮高度
        channel_action_layout.addWidget(self.add_channel_pair_button)
        
        # 删除频道对按钮
        self.remove_channel_pair_button = QPushButton("删除所选")
        self.remove_channel_pair_button.setMinimumHeight(28)  # 增加按钮高度
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
        self.pairs_list_label = QLabel("已配置监听频道对: 0个")
        self.pairs_list_label.setStyleSheet("font-weight: bold;")  # 加粗标签文字
        channel_widget_layout.addWidget(self.pairs_list_label)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)  # 允许小部件调整大小
        scroll_area.setMinimumHeight(120)  # 增加滚动区域的最小高度
        scroll_area.setMaximumHeight(150)  # 设置合理的最大高度
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
        general_config_label = QLabel("通用配置:")
        general_config_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        general_config_layout.addWidget(general_config_label)
        
        # 使用表单布局
        general_form_layout = QFormLayout()
        general_form_layout.setSpacing(10)  # 增加表单项间距
        general_form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)  # 标签右对齐
        
        # 监听截止日期 - 从监听参数移动到这里
        duration_layout = QHBoxLayout()
        
        self.duration_check = QCheckBox("启用监听截止日期")
        self.duration_check.setStyleSheet("padding: 4px;")  # 添加内边距
        duration_layout.addWidget(self.duration_check)
        
        self.duration_date = QDateTimeEdit(QDateTime.currentDateTime().addDays(365))
        self.duration_date.setCalendarPopup(True)
        self.duration_date.setDisplayFormat("yyyy-MM-dd")
        self.duration_date.setEnabled(False)
        self.duration_date.setMinimumHeight(26)  # 增加高度
        duration_layout.addWidget(self.duration_date)
        
        # 添加弹性空间，让控件靠左对齐
        duration_layout.addStretch(1)
        
        general_form_layout.addRow("截止日期:", duration_layout)
        
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
        
        # 主消息面板
        self.main_message_view = QTextEdit()
        self.main_message_view.setReadOnly(True)
        self.main_message_view.setLineWrapMode(QTextEdit.WidgetWidth)
        
        # 按频道分类的消息面板
        self.channel_message_views = {}
        
        # 添加主消息面板
        self.message_tabs.addTab(self.main_message_view, "所有消息")
        
        # 设置消息面板的尺寸策略
        self.message_tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # 设置最小高度，确保消息区域有足够空间显示
        self.message_tabs.setMinimumHeight(180)
        
        # 将消息标签页容器添加到监听日志标签页
        log_layout.addWidget(self.message_tabs, 1)
        
        # 将三个标签页添加到配置标签页部件
        self.config_tabs.addTab(self.config_tab, "频道配置")
        self.config_tabs.addTab(self.general_config_tab, "通用配置")
        self.config_tabs.addTab(self.log_tab, "监听日志")
    
    def _create_action_buttons(self):
        """创建底部操作按钮"""
        # 添加一些垂直间距
        self.main_layout.addSpacing(10)
        
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)  # 增加按钮间距
        button_layout.setContentsMargins(8, 8, 8, 8)  # 添加按钮区域边距
        
        self.start_listen_button = QPushButton("开始监听")
        self.start_listen_button.setMinimumHeight(40)
        self.start_listen_button.setMinimumWidth(100)  # 设置最小宽度
        
        self.stop_listen_button = QPushButton("停止监听")
        self.stop_listen_button.setEnabled(False)
        self.stop_listen_button.setMinimumHeight(40)
        self.stop_listen_button.setMinimumWidth(100)
        
        self.save_config_button = QPushButton("保存配置")
        self.save_config_button.setMinimumHeight(35)  # 稍微增加高度
        self.save_config_button.setMinimumWidth(80)
        
        self.clear_messages_button = QPushButton("清空消息")
        self.clear_messages_button.setMinimumHeight(35)
        self.clear_messages_button.setMinimumWidth(80)
        
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
            return f" - 替换规则：{', '.join(replacements)}"
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
            MediaType.PHOTO: "照片",
            MediaType.VIDEO: "视频", 
            MediaType.DOCUMENT: "文件",
            MediaType.AUDIO: "音频",
            MediaType.ANIMATION: "动画",
            MediaType.STICKER: "贴纸",
            MediaType.VOICE: "语音",
            MediaType.VIDEO_NOTE: "视频笔记"
        }
        
        # 对于字符串类型的媒体类型（从配置文件加载的）
        string_media_type_names = {
            "photo": "照片",
            "video": "视频", 
            "document": "文件",
            "audio": "音频",
            "animation": "动画",
            "sticker": "贴纸",
            "voice": "语音",
            "video_note": "视频笔记"
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
            return " - 媒体类型：全部"
        else:
            return f" - 媒体类型：{', '.join(type_names)}"
    
    def _format_filter_options_display(self, keywords, exclude_forwards, exclude_replies, exclude_media, exclude_links):
        """格式化过滤选项的显示
        
        Args:
            keywords: 关键词列表
            exclude_forwards: 是否排除转发消息
            exclude_replies: 是否排除回复消息
            exclude_media: 是否排除媒体消息
            exclude_links: 是否排除包含链接的消息
            
        Returns:
            str: 格式化后的过滤选项字符串
        """
        filter_options = []
        
        # 关键词过滤
        if keywords:
            keywords_str = ", ".join(keywords)
            filter_options.append(f"关键词({keywords_str})")
        
        # 排除选项
        exclude_options = []
        if exclude_forwards:
            exclude_options.append("转发")
        if exclude_replies:
            exclude_options.append("回复")
        if exclude_media:
            exclude_options.append("媒体")
        if exclude_links:
            exclude_options.append("链接")
        
        if exclude_options:
            filter_options.append(f"排除({', '.join(exclude_options)})")
        
        if filter_options:
            return f" - 过滤：{', '.join(filter_options)}"
        else:
            return ""
    
    def _add_channel_pair(self):
        """添加频道对到监听列表"""
        source_channel = self.source_channel_input.text().strip()
        target_channels = [ch.strip() for ch in self.target_channel_input.text().split(',') if ch.strip()]
        
        if not source_channel:
            QMessageBox.warning(self, "警告", "请输入源频道链接或ID")
            return
        
        if not target_channels:
            QMessageBox.warning(self, "警告", "请输入至少一个目标频道")
            return
        
        # 检查是否已存在相同源频道
        for i in range(self.pairs_list.count()):
            item_text = self.pairs_list.item(i).text()
            if item_text.split(" -> ")[0].strip() == source_channel:
                QMessageBox.information(self, "提示", "已存在相同源频道的监听配置")
                return
        
        # 文本替换规则处理
        text_filter = []
        original_texts = [text.strip() for text in self.original_text_input.text().split(',')]
        target_texts = [text.strip() for text in self.target_text_input.text().split(',')]
        
        # 检查原始文本是否全部为空
        if any(target_texts) and not any(original_texts):
            QMessageBox.warning(
                self, 
                "原始文本错误", 
                "原始文本不能为空。请为每个替换规则指定一个原始文本。"
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
                    "文本替换规则错误", 
                    f"原始文本和替换文本数量不匹配。原始文本有{len(original_texts)}项，替换文本有{len(target_texts)}项。每个原始文本应对应一个替换文本。"
                )
                return
                
            # 检查是否有空的原始文本项
            empty_indexes = [i+1 for i, text in enumerate(original_texts) if not text and i < len(target_texts) and target_texts[i]]
            if empty_indexes:
                positions = ", ".join(map(str, empty_indexes))
                QMessageBox.warning(
                    self, 
                    "原始文本错误", 
                    f"原始文本不能为空。第 {positions} 个替换规则的原始文本为空，请修正。"
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
            "exclude_media": self.exclude_media_check.isChecked(),
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
            self.exclude_media_check.isChecked(),
            self.exclude_links_check.isChecked()
        )
        
        # 添加调试信息
        logger.debug(f"频道对 {source_channel} - 关键词: {keywords}, 排除项: forwards={self.exclude_forwards_check.isChecked()}, replies={self.exclude_replies_check.isChecked()}, media={self.exclude_media_check.isChecked()}, links={self.exclude_links_check.isChecked()}")
        logger.debug(f"频道对 {source_channel} - 过滤选项显示字符串: '{filter_options_str}'")
        
        display_text = f"{source_channel} -> {target_channels_str}{text_filter_str}{media_types_str}{filter_options_str}"
        if self.remove_captions_check.isChecked():
            display_text += " (移除媒体说明)"
        
        logger.debug(f"频道对 {source_channel} - 完整显示文本: '{display_text}'")
        
        item = QListWidgetItem(display_text)
        item.setData(Qt.UserRole, pair_data)
        self.pairs_list.addItem(item)
        
        # 为该频道创建一个消息标签页
        channel_view = QTextEdit()
        channel_view.setReadOnly(True)
        channel_view.setLineWrapMode(QTextEdit.WidgetWidth)
        
        channel_name = source_channel.split('/')[-1] if '/' in source_channel else source_channel
        self.message_tabs.addTab(channel_view, channel_name)
        
        # 保存标签页引用
        self.channel_message_views[source_channel] = channel_view
        
        # 更新频道数量标签
        self.pairs_list_label.setText(f"已配置监听频道对: {self.pairs_list.count()}个")
        
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
        self.exclude_media_check.setChecked(False)
        self.exclude_links_check.setChecked(False)
    
    def _remove_channel_pairs(self):
        """删除选中的监听频道对"""
        selected_items = self.pairs_list.selectedItems()
        
        if not selected_items:
            QMessageBox.information(self, "提示", "请先选择要删除的频道对")
            return
        
        # 删除选中的频道对
        for item in reversed(selected_items):
            data = item.data(Qt.UserRole)
            source_channel = data["source_channel"]
            row = self.pairs_list.row(item)
            self.pairs_list.takeItem(row)
            
            # 找到并删除对应的标签页
            if source_channel in self.channel_message_views:
                view = self.channel_message_views[source_channel]
                index = self.message_tabs.indexOf(view)
                if index != -1:
                    self.message_tabs.removeTab(index)
                
                # 从字典中删除引用
                del self.channel_message_views[source_channel]
        
        # 更新频道数量标签
        self.pairs_list_label.setText(f"已配置监听频道对: {self.pairs_list.count()}个")
    
    def _clear_messages(self):
        """清空所有消息"""
        # 清空主消息面板
        self.main_message_view.clear()
        
        # 清空各频道消息面板
        for view in self.channel_message_views.values():
            view.clear()
    
    def _start_listen(self):
        """开始监听"""
        # 检查是否有监听频道对
        if self.pairs_list.count() == 0:
            QMessageBox.warning(self, "警告", "请先添加至少一个监听频道对")
            return
        
        # 检查是否有监听器实例
        if not hasattr(self, 'monitor') or self.monitor is None:
            QMessageBox.warning(self, "错误", "监听器未初始化，无法启动监听")
            return
        
        # 添加状态消息
        self._add_status_message("开始监听...")
        
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
            self._add_status_message(f"启动监听失败: {e}")
            # 恢复按钮状态
            self.start_listen_button.setEnabled(True)
            self.stop_listen_button.setEnabled(False)
    
    def _stop_listen(self):
        """停止监听"""
        # 检查是否有监听器实例
        if not hasattr(self, 'monitor') or self.monitor is None:
            self._add_status_message("监听器未初始化")
            return
        
        # 添加状态消息
        self._add_status_message("停止监听...")
        
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
            self._add_status_message(f"停止监听失败: {e}")
    
    async def _async_start_monitoring(self):
        """异步启动监听"""
        try:
            self._add_status_message("正在启动监听器...")
            await self.monitor.start_monitoring()
            self._add_status_message("监听器启动成功")
        except Exception as e:
            logger.error(f"异步启动监听失败: {e}")
            self._add_status_message(f"启动监听失败: {e}")
            # 恢复按钮状态
            self.start_listen_button.setEnabled(True)
            self.stop_listen_button.setEnabled(False)
    
    async def _async_stop_monitoring(self):
        """异步停止监听"""
        try:
            await self.monitor.stop_monitoring()
            self._add_status_message("监听器已停止")
        except Exception as e:
            logger.error(f"异步停止监听失败: {e}")
            self._add_status_message(f"停止监听失败: {e}")
    
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
            logger.debug(f"  exclude_media: {data['exclude_media']} (类型: {type(data['exclude_media'])})")
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
            exclude_media = data.get("exclude_media", False)
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
                "exclude_media": exclude_media,
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
            QMessageBox.warning(self, "警告", "请先添加至少一个监听频道对")
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
                exclude_media = pair.get('exclude_media', False)
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
                    exclude_media=exclude_media,
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
            QMessageBox.information(self, "配置保存", "监听配置已保存到文件，监听器将读取最新配置进行监听")
            
            # 更新本地配置引用
            self.config = updated_config
            
        except Exception as e:
            logger.error(f"保存监听配置失败: {e}")
            QMessageBox.warning(self, "配置保存失败", f"保存配置时出错: {e}")
    
    def _add_status_message(self, message):
        """添加状态消息到消息面板
        
        Args:
            message: 状态消息
        """
        time_str = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
        status_msg = f"[{time_str}] [系统] {message}"
        
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
        
        # 清除所有频道标签页
        while self.message_tabs.count() > 1:  # 保留"所有消息"标签页
            self.message_tabs.removeTab(1)
        
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
            exclude_media = pair.get('exclude_media', False)
            exclude_links = pair.get('exclude_links', False)
            
            # 添加详细的原始数据调试信息
            logger.debug(f"频道对 {source_channel} - 从配置读取的原始数据:")
            logger.debug(f"  keywords: {keywords} (类型: {type(keywords)})")
            logger.debug(f"  exclude_forwards: {exclude_forwards} (类型: {type(exclude_forwards)})")
            logger.debug(f"  exclude_replies: {exclude_replies} (类型: {type(exclude_replies)})")
            logger.debug(f"  exclude_media: {exclude_media} (类型: {type(exclude_media)})")
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
                exclude_media,
                exclude_links
            )
            
            # 添加调试信息
            logger.debug(f"频道对 {source_channel} - 关键词: {keywords}, 排除项: forwards={exclude_forwards}, replies={exclude_replies}, media={exclude_media}, links={exclude_links}")
            logger.debug(f"频道对 {source_channel} - 过滤选项显示字符串: '{filter_options_str}'")
            
            display_text = f"{source_channel} -> {target_channels_str}{text_filter_str}{media_types_str}{filter_options_str}"
            if remove_captions:
                display_text += " (移除媒体说明)"
            
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
                "exclude_media": exclude_media,
                "exclude_links": exclude_links
            }
            item.setData(Qt.UserRole, pair_data)
            self.pairs_list.addItem(item)
            
            # 为该频道创建一个消息标签页
            channel_view = QTextEdit()
            channel_view.setReadOnly(True)
            channel_view.setLineWrapMode(QTextEdit.WidgetWidth)
            
            channel_name = source_channel.split('/')[-1] if '/' in source_channel else source_channel
            self.message_tabs.addTab(channel_view, channel_name)
            
            # 保存标签页引用
            self.channel_message_views[source_channel] = channel_view
        
        # 更新频道数量标签
        self.pairs_list_label.setText(f"已配置监听频道对: {self.pairs_list.count()}个")
        
        # 将媒体类型复选框设置为全选状态作为默认
        for checkbox in self.media_types_checkboxes.values():
            checkbox.setChecked(True)
        
        # 注释掉：不在加载配置时重置过滤选项UI，保持为空白状态供用户添加新频道对时使用
        # 将过滤选项UI重置为默认状态（用于添加新频道对时的默认设置）
        # self.keyword_input.clear()
        # self.exclude_forwards_check.setChecked(False)
        # self.exclude_replies_check.setChecked(False)
        # self.exclude_media_check.setChecked(False)
        # self.exclude_links_check.setChecked(False)
        
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
            content = f"收到新消息 [ID: {message_id}]"
            
            # 添加到消息列表 - 使用源信息作为来源
            self._add_message_item(source_info, content)
            
            # 尝试将消息添加到对应的频道标签页
            # 查找匹配的频道标签页
            for source_channel, view in self.channel_message_views.items():
                if source_channel in source_info or str(message_id) in source_info:
                    # 添加到该频道的消息面板
                    time_str = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
                    formatted_msg = f"[{time_str}] {source_info}: {content}"
                    view.append(formatted_msg)
                    view.moveCursor(QTextCursor.End)
                    break
            
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
            content = f"接收到消息 [ID: {message_id}]"
            
            # 添加到消息列表
            self._add_message_item(source_info, content)
            
            logger.debug(f"处理消息接收信号: {message_id} - {source_info}")
        except Exception as e:
            logger.error(f"处理消息接收信号时出错: {e}")
    
    def _on_forward_updated_signal(self, source_message_id, source_chat_id, target_id, success, modified):
        """处理转发更新信号
        
        Args:
            source_message_id: 源消息ID
            source_chat_id: 源频道ID
            target_id: 目标频道ID
            success: 是否成功
            modified: 是否修改
        """
        try:
            # 构建转发信息
            status = "成功" if success else "失败"
            mod_info = " (已修改)" if modified else ""
            forward_info = f"消息ID: {source_message_id}, 从频道: {source_chat_id} 到频道: {target_id} - {status}{mod_info}"
            
            # 添加到转发列表
            self._add_forward_item(forward_info)
            
            logger.debug(f"处理转发更新信号: {forward_info}")
        except Exception as e:
            logger.error(f"处理转发更新信号时出错: {e}")
    
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
        self.main_message_view.append("正在监听中...")
        
        # 禁用开始按钮，启用停止按钮
        self.start_listen_button.setEnabled(False)
        self.stop_listen_button.setEnabled(True)
        
        # 显示正在监听的频道
        if channel_ids:
            channels_str = ", ".join(str(c) for c in channel_ids)
            self.main_message_view.append(f"正在监听: {channels_str}")
        
        logger.info("监听已开始")
    
    def _on_monitoring_stopped(self):
        """监听停止处理"""
        # 更新UI状态
        self.main_message_view.append("监听已停止")
        
        # 启用开始按钮，禁用停止按钮
        self.start_listen_button.setEnabled(True)
        self.stop_listen_button.setEnabled(False)
        
        logger.info("监听已停止")
    
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
        error_msg = f"监听出错: {error}"
        if message:
            error_msg += f"\n{message}"
            
        self.main_message_view.append(error_msg)
        
        # 恢复按钮状态
        self.start_listen_button.setEnabled(True)
        self.stop_listen_button.setEnabled(False)
        
        # 显示错误对话框
        self._show_error_dialog("监听错误", error_msg)
        
        logger.error(f"监听错误: {error}")
        if message:
            logger.debug(f"错误详情: {message}")
    
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
    
    def _add_forward_item(self, forward_info):
        """添加转发项到消息面板
        
        Args:
            forward_info: 转发信息
        """
        # 使用现有的消息显示机制
        time_str = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
        formatted_msg = f"[{time_str}] [转发完成] {forward_info}"
        
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
        edit_action = context_menu.addAction("编辑")
        delete_action = context_menu.addAction("删除")
        
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
        edit_dialog.setWindowTitle("编辑监听频道对")
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
        source_input.setPlaceholderText("频道链接或ID")
        basic_form.addRow("源频道:", source_input)
        
        # 目标频道输入
        target_channels = channel_pair.get('target_channels', [])
        target_input = QLineEdit(', '.join(target_channels))
        target_input.setPlaceholderText("多个频道用逗号分隔")
        basic_form.addRow("目标频道:", target_input)
        
        scroll_layout.addLayout(basic_form)
        
        # 文本替换规则组
        text_filter_group = QGroupBox("文本替换规则")
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
        original_text_input.setPlaceholderText("要替换的原始文本，多个用逗号分隔")
        text_filter_layout.addRow("替换:", original_text_input)
        
        target_text_input = QLineEdit(', '.join(target_texts))
        target_text_input.setPlaceholderText("替换后的目标文本，多个用逗号分隔")
        text_filter_layout.addRow("替换为:", target_text_input)
        
        scroll_layout.addWidget(text_filter_group)
        
        # 媒体类型选择组
        media_group = QGroupBox("媒体类型")
        media_layout = QVBoxLayout(media_group)
        
        # 第一行媒体类型
        media_row1 = QHBoxLayout()
        photo_check = QCheckBox("照片")
        video_check = QCheckBox("视频")
        document_check = QCheckBox("文档")
        audio_check = QCheckBox("音频")
        
        media_row1.addWidget(photo_check)
        media_row1.addWidget(video_check)
        media_row1.addWidget(document_check)
        media_row1.addWidget(audio_check)
        media_row1.addStretch()
        
        # 第二行媒体类型
        media_row2 = QHBoxLayout()
        animation_check = QCheckBox("动画")
        sticker_check = QCheckBox("贴纸")
        voice_check = QCheckBox("语音")
        video_note_check = QCheckBox("视频笔记")
        
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
        filter_group = QGroupBox("过滤选项")
        filter_layout = QVBoxLayout(filter_group)
        
        # 关键词输入
        keywords_layout = QFormLayout()
        keywords = channel_pair.get('keywords', [])
        keywords_input = QLineEdit(', '.join(keywords))
        keywords_input.setPlaceholderText("关键词，多个用逗号分隔")
        keywords_layout.addRow("关键词:", keywords_input)
        filter_layout.addLayout(keywords_layout)
        
        # 排除选项
        exclude_layout = QHBoxLayout()
        
        exclude_forwards_check = QCheckBox("排除转发消息")
        exclude_forwards_check.setChecked(channel_pair.get('exclude_forwards', False))
        exclude_layout.addWidget(exclude_forwards_check)
        
        exclude_replies_check = QCheckBox("排除回复消息")
        exclude_replies_check.setChecked(channel_pair.get('exclude_replies', False))
        exclude_layout.addWidget(exclude_replies_check)
        
        exclude_media_check = QCheckBox("排除媒体消息")
        exclude_media_check.setChecked(channel_pair.get('exclude_media', False))
        exclude_layout.addWidget(exclude_media_check)
        
        exclude_links_check = QCheckBox("排除包含链接的消息")
        exclude_links_check.setChecked(channel_pair.get('exclude_links', False))
        exclude_layout.addWidget(exclude_links_check)
        
        exclude_layout.addStretch()
        filter_layout.addLayout(exclude_layout)
        
        scroll_layout.addWidget(filter_group)
        
        # 其他选项组
        other_group = QGroupBox("其他选项")
        other_layout = QVBoxLayout(other_group)
        
        remove_captions_check = QCheckBox("移除媒体说明")
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
        save_button = QPushButton("保存")
        cancel_button = QPushButton("取消")
        
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
                    raise ValueError("源频道不能为空")
                if not new_targets:
                    raise ValueError("目标频道不能为空")
                
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
                    raise ValueError("至少需要选择一种媒体类型")
                
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
                    'exclude_media': exclude_media_check.isChecked(),
                    'exclude_links': exclude_links_check.isChecked(),
                    'start_id': channel_pair.get('start_id', 0),
                    'end_id': channel_pair.get('end_id', 0)
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
                updated_pair.get('exclude_media', False),
                updated_pair.get('exclude_links', False)
            )
            
            # 构建完整显示文本
            display_text = f"{source_channel} -> {target_channels_str}{text_filter_str}{media_types_str}{filter_options_str}"
            if updated_pair.get('remove_captions', False):
                display_text += " (移除媒体说明)"
            
            # 更新列表项
            item.setText(display_text)
            item.setData(Qt.UserRole, updated_pair)
            
            # 记录日志
            logger.debug(f"频道对已更新: {display_text}")
            
            # 显示成功消息
            QMessageBox.information(self, "更新成功", "频道对已成功更新，请点击保存配置")
            
        except Exception as e:
            logger.error(f"更新频道对时出错: {e}")
            QMessageBox.warning(self, "更新失败", f"更新频道对时出错: {e}") 