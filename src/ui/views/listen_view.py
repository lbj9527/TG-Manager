"""
TG-Manager 消息监听界面
实现对Telegram频道消息的实时监听功能
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QCheckBox, QPushButton,
    QGroupBox, QScrollArea, QSpinBox, QComboBox,
    QListWidget, QListWidgetItem, QMessageBox,
    QTextEdit, QSplitter, QTabWidget, QDateTimeEdit,
    QSizePolicy
)
from PySide6.QtCore import Qt, Signal, Slot, QDateTime
from PySide6.QtGui import QIcon, QTextCursor

from src.utils.logger import get_logger

logger = get_logger()


class ListenView(QWidget):
    """监听界面，提供对Telegram频道消息的实时监听功能"""
    
    # 监听开始信号
    listen_started = Signal(dict)  # 监听配置
    
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
        self.main_layout.setSpacing(2)  # 进一步减小主布局的垂直间距
        self.main_layout.setContentsMargins(4, 4, 4, 4)  # 进一步减小主布局边距
        self.setLayout(self.main_layout)
        
        # 统一设置群组框样式，减小标题高度
        self.setStyleSheet("""
            QGroupBox { 
                font-weight: bold; 
                padding-top: 2px; 
                margin-top: 0.4em; 
            }
            QTabWidget::pane {
                border: 1px solid #444;
                padding: 1px;
            }
            QTabBar::tab {
                padding: 3px 8px;
            }
        """)
        
        # 创建配置标签页
        self.config_tabs = QTabWidget()
        # 设置配置区域的最大高度，确保消息区域有足够空间
        self.config_tabs.setMaximumHeight(320)  # 再增加最大高度
        self.config_tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.main_layout.addWidget(self.config_tabs)
        
        # 创建配置标签页
        self._create_config_panel()
        
        # 创建中间消息显示面板（直接添加到主布局）
        self._create_message_panel()
        
        # 创建底部操作按钮
        self._create_action_buttons()
        
        # 连接信号
        self._connect_signals()
        
        # 加载配置
        if self.config:
            self.load_config(self.config)
        
        # 监听配置列表
        self.listen_configs = []
        
        logger.info("监听界面初始化完成")
    
    def _create_config_panel(self):
        """创建配置标签页"""
        # 监听配置标签页
        self.config_tab = QWidget()
        config_layout = QVBoxLayout(self.config_tab)
        config_layout.setContentsMargins(4, 4, 4, 4)  # 减小外边距
        config_layout.setSpacing(4)  # 减小间距
        
        # 创建顶部表单面板
        form_layout = QFormLayout()
        
        # 监听频道
        self.channel_input = QLineEdit()
        self.channel_input.setPlaceholderText("频道链接或ID (例如: https://t.me/example 或 -1001234567890)")
        form_layout.addRow("监听频道:", self.channel_input)
        
        # 创建水平布局存放添加按钮和频道列表
        channel_action_layout = QHBoxLayout()
        
        # 添加频道按钮
        self.add_channel_button = QPushButton("添加频道")
        channel_action_layout.addWidget(self.add_channel_button)
        
        # 删除频道按钮
        self.remove_channel_button = QPushButton("删除所选")
        channel_action_layout.addWidget(self.remove_channel_button)
        
        # 添加弹性空间，让按钮靠左对齐
        channel_action_layout.addStretch(1)
        
        # 频道列表部分
        channel_list_label = QLabel("已配置监听频道:")
        
        self.channel_list = QListWidget()
        self.channel_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.channel_list.setMinimumHeight(240)  # 进一步增加频道列表高度
        self.channel_list.setSelectionMode(QListWidget.ExtendedSelection)
        
        # 添加表单、按钮和列表到布局
        config_layout.addLayout(form_layout)
        config_layout.addLayout(channel_action_layout)
        config_layout.addWidget(channel_list_label)
        # 给频道列表更大的空间比例
        config_layout.addWidget(self.channel_list, 1)  # 添加伸展系数
        
        # 消息过滤标签页
        self.filter_tab = QWidget()
        filter_layout = QVBoxLayout(self.filter_tab)
        filter_layout.setContentsMargins(4, 4, 4, 4)  # 减小外边距
        filter_layout.setSpacing(4)  # 减小间距
        
        # 过滤选项表单
        filter_form = QFormLayout()
        
        # 关键字过滤
        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("多个关键字用逗号分隔，留空不过滤")
        filter_form.addRow("关键字过滤:", self.keyword_input)
        
        # 媒体类型过滤
        self.media_type_combo = QComboBox()
        self.media_type_combo.addItem("所有类型", "all")
        self.media_type_combo.addItem("仅文本", "text")
        self.media_type_combo.addItem("仅照片", "photo")
        self.media_type_combo.addItem("仅视频", "video")
        self.media_type_combo.addItem("仅文件", "document")
        self.media_type_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        filter_form.addRow("媒体类型:", self.media_type_combo)
        
        filter_layout.addLayout(filter_form)
        
        # 过滤选项复选框 - 使用流式布局
        filter_checkboxes = QVBoxLayout()
        
        # 第一行复选框
        filter_row1 = QHBoxLayout()
        self.exclude_forwards_check = QCheckBox("排除转发消息")
        self.exclude_replies_check = QCheckBox("排除回复消息")
        filter_row1.addWidget(self.exclude_forwards_check)
        filter_row1.addWidget(self.exclude_replies_check)
        filter_row1.addStretch(1)
        
        # 第二行复选框
        filter_row2 = QHBoxLayout()
        self.exclude_media_check = QCheckBox("排除媒体消息")
        self.exclude_links_check = QCheckBox("排除带链接消息")
        filter_row2.addWidget(self.exclude_media_check)
        filter_row2.addWidget(self.exclude_links_check)
        filter_row2.addStretch(1)
        
        filter_checkboxes.addLayout(filter_row1)
        filter_checkboxes.addLayout(filter_row2)
        
        filter_layout.addLayout(filter_checkboxes)
        
        # 时间过滤
        time_filter_layout = QVBoxLayout()
        time_header = QHBoxLayout()
        
        self.time_filter_check = QCheckBox("启用时间过滤")
        time_header.addWidget(self.time_filter_check)
        time_header.addStretch(1)
        
        time_inputs = QHBoxLayout()
        time_inputs.addWidget(QLabel("从:"))
        self.start_time = QDateTimeEdit(QDateTime.currentDateTime().addDays(-1))
        self.start_time.setCalendarPopup(True)
        self.start_time.setEnabled(False)
        self.start_time.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        time_inputs.addWidget(self.start_time)
        
        time_inputs.addWidget(QLabel("至:"))
        self.end_time = QDateTimeEdit(QDateTime.currentDateTime())
        self.end_time.setCalendarPopup(True)
        self.end_time.setEnabled(False)
        self.end_time.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        time_inputs.addWidget(self.end_time)
        
        # 连接时间过滤复选框和日期选择器的启用状态
        self.time_filter_check.toggled.connect(self.start_time.setEnabled)
        self.time_filter_check.toggled.connect(self.end_time.setEnabled)
        
        time_filter_layout.addLayout(time_header)
        time_filter_layout.addLayout(time_inputs)
        
        filter_layout.addLayout(time_filter_layout)
        
        # 通知配置标签页
        self.notify_tab = QWidget()
        notify_layout = QVBoxLayout(self.notify_tab)
        notify_layout.setContentsMargins(4, 4, 4, 4)  # 减小外边距
        notify_layout.setSpacing(4)  # 减小间距
        
        # 第一行复选框
        notify_row1 = QHBoxLayout()
        self.desktop_notify_check = QCheckBox("桌面通知")
        self.desktop_notify_check.setChecked(True)
        self.sound_notify_check = QCheckBox("声音提醒")
        notify_row1.addWidget(self.desktop_notify_check)
        notify_row1.addWidget(self.sound_notify_check)
        notify_row1.addStretch(1)
        
        # 第二行复选框
        notify_row2 = QHBoxLayout()
        self.highlight_check = QCheckBox("高亮关键字")
        self.highlight_check.setChecked(True)
        self.auto_scroll_check = QCheckBox("自动滚动到新消息")
        self.auto_scroll_check.setChecked(True)
        notify_row2.addWidget(self.highlight_check)
        notify_row2.addWidget(self.auto_scroll_check)
        notify_row2.addStretch(1)
        
        notify_layout.addLayout(notify_row1)
        notify_layout.addLayout(notify_row2)
        
        # 最大显示消息数
        max_messages_layout = QHBoxLayout()
        
        max_messages_layout.addWidget(QLabel("最大显示消息数:"))
        
        self.max_messages = QSpinBox()
        self.max_messages.setRange(50, 1000)
        self.max_messages.setValue(200)
        self.max_messages.setSingleStep(50)
        self.max_messages.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        max_messages_layout.addWidget(self.max_messages)
        max_messages_layout.addStretch(1)
        
        notify_layout.addLayout(max_messages_layout)
        
        # 将标签页添加到配置标签页部件
        self.config_tabs.addTab(self.config_tab, "监听配置")
        self.config_tabs.addTab(self.filter_tab, "消息过滤")
        self.config_tabs.addTab(self.notify_tab, "通知配置")
    
    def _create_message_panel(self):
        """创建中间消息显示面板"""
        # 直接创建消息标签页容器，不使用GroupBox
        self.message_tabs = QTabWidget()
        
        # 主消息面板
        self.main_message_view = QTextEdit()
        self.main_message_view.setReadOnly(True)
        self.main_message_view.setLineWrapMode(QTextEdit.WidgetWidth)
        
        # 按频道分类的消息面板
        self.channel_message_views = {}
        
        # 添加主消息面板
        self.message_tabs.addTab(self.main_message_view, "所有消息")
        
        # 设置消息面板的尺寸策略，让它能够占据大部分空间
        self.message_tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # 将消息标签页直接添加到主布局，占据更多空间
        self.main_layout.addWidget(self.message_tabs, 5)  # 增加伸展系数，使消息面板占用更多空间
    
    def _create_action_buttons(self):
        """创建底部操作按钮"""
        button_layout = QHBoxLayout()
        
        self.start_listen_button = QPushButton("开始监听")
        self.start_listen_button.setMinimumHeight(40)
        
        self.stop_listen_button = QPushButton("停止监听")
        self.stop_listen_button.setEnabled(False)
        self.stop_listen_button.setMinimumHeight(40)
        
        self.save_config_button = QPushButton("保存配置")
        self.clear_messages_button = QPushButton("清空消息")
        self.export_messages_button = QPushButton("导出消息")
        
        # 确保按钮大小合理
        for button in [self.save_config_button, self.clear_messages_button, self.export_messages_button]:
            button.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        
        button_layout.addWidget(self.start_listen_button)
        button_layout.addWidget(self.stop_listen_button)
        button_layout.addWidget(self.save_config_button)
        button_layout.addWidget(self.clear_messages_button)
        button_layout.addWidget(self.export_messages_button)
        
        self.main_layout.addLayout(button_layout)
    
    def _connect_signals(self):
        """连接信号和槽"""
        # 频道管理
        self.add_channel_button.clicked.connect(self._add_channel)
        self.remove_channel_button.clicked.connect(self._remove_channels)
        
        # 消息操作
        self.clear_messages_button.clicked.connect(self._clear_messages)
        self.export_messages_button.clicked.connect(self._export_messages)
        
        # 监听控制
        self.start_listen_button.clicked.connect(self._start_listen)
        self.stop_listen_button.clicked.connect(self._stop_listen)
        self.save_config_button.clicked.connect(self._save_config)
    
    def _add_channel(self):
        """添加频道到监听列表"""
        channel = self.channel_input.text().strip()
        
        if not channel:
            QMessageBox.warning(self, "警告", "请输入频道链接或ID")
            return
        
        # 检查是否已存在相同频道
        for i in range(self.channel_list.count()):
            if self.channel_list.item(i).text() == channel:
                QMessageBox.information(self, "提示", "此频道已在监听列表中")
                return
        
        # 添加到列表
        self.channel_list.addItem(channel)
        
        # 为该频道创建一个消息标签页
        channel_view = QTextEdit()
        channel_view.setReadOnly(True)
        channel_view.setLineWrapMode(QTextEdit.WidgetWidth)
        
        channel_name = channel.split('/')[-1] if '/' in channel else channel
        self.message_tabs.addTab(channel_view, channel_name)
        
        # 保存标签页引用
        self.channel_message_views[channel] = channel_view
        
        # 清空输入
        self.channel_input.clear()
    
    def _remove_channels(self):
        """删除选中的监听频道"""
        selected_items = self.channel_list.selectedItems()
        
        if not selected_items:
            QMessageBox.information(self, "提示", "请先选择要删除的频道")
            return
        
        # 删除选中的频道
        for item in reversed(selected_items):
            channel = item.text()
            row = self.channel_list.row(item)
            self.channel_list.takeItem(row)
            
            # 找到并删除对应的标签页
            if channel in self.channel_message_views:
                view = self.channel_message_views[channel]
                index = self.message_tabs.indexOf(view)
                if index != -1:
                    self.message_tabs.removeTab(index)
                
                # 从字典中删除引用
                del self.channel_message_views[channel]
    
    def _clear_messages(self):
        """清空所有消息"""
        # 清空主消息面板
        self.main_message_view.clear()
        
        # 清空各频道消息面板
        for view in self.channel_message_views.values():
            view.clear()
    
    def _export_messages(self):
        """导出消息"""
        # TODO: 实现消息导出功能
        QMessageBox.information(self, "提示", "导出功能尚未实现")
    
    def _start_listen(self):
        """开始监听"""
        # 检查是否有监听频道
        if self.channel_list.count() == 0:
            QMessageBox.warning(self, "警告", "请先添加至少一个监听频道")
            return
        
        # 获取频道列表
        channels = []
        for i in range(self.channel_list.count()):
            channels.append(self.channel_list.item(i).text())
        
        # 获取关键字
        keywords = [kw.strip() for kw in self.keyword_input.text().split(",") if kw.strip()]
        
        # 收集配置
        config = {
            'channels': channels,
            'filters': {
                'keywords': keywords,
                'media_type': self.media_type_combo.currentData(),
                'exclude_forwards': self.exclude_forwards_check.isChecked(),
                'exclude_replies': self.exclude_replies_check.isChecked(),
                'exclude_media': self.exclude_media_check.isChecked(),
                'exclude_links': self.exclude_links_check.isChecked(),
                'time_filter': {
                    'enabled': self.time_filter_check.isChecked(),
                    'start_time': self.start_time.dateTime().toString(Qt.ISODate) if self.time_filter_check.isChecked() else None,
                    'end_time': self.end_time.dateTime().toString(Qt.ISODate) if self.time_filter_check.isChecked() else None
                }
            },
            'notifications': {
                'desktop_notify': self.desktop_notify_check.isChecked(),
                'sound_notify': self.sound_notify_check.isChecked(),
                'highlight': self.highlight_check.isChecked(),
                'auto_scroll': self.auto_scroll_check.isChecked(),
                'max_messages': self.max_messages.value()
            }
        }
        
        # 发出监听开始信号
        self.listen_started.emit(config)
        
        # 添加状态消息
        self._add_status_message("开始监听...")
        
        # 更新按钮状态
        self.start_listen_button.setEnabled(False)
        self.stop_listen_button.setEnabled(True)
    
    def _stop_listen(self):
        """停止监听"""
        # TODO: 实现停止监听功能
        
        # 添加状态消息
        self._add_status_message("停止监听")
        
        # 更新按钮状态
        self.start_listen_button.setEnabled(True)
        self.stop_listen_button.setEnabled(False)
    
    def _save_config(self):
        """保存当前配置"""
        # 检查是否有监听频道
        if self.channel_list.count() == 0:
            QMessageBox.warning(self, "警告", "请先添加至少一个监听频道")
            return
        
        # 获取频道列表
        channels = []
        for i in range(self.channel_list.count()):
            channels.append(self.channel_list.item(i).text())
        
        # 获取关键字
        keywords = [kw.strip() for kw in self.keyword_input.text().split(",") if kw.strip()]
        
        # 收集配置
        config = {
            'channels': channels,
            'filters': {
                'keywords': keywords,
                'media_type': self.media_type_combo.currentData(),
                'exclude_forwards': self.exclude_forwards_check.isChecked(),
                'exclude_replies': self.exclude_replies_check.isChecked(),
                'exclude_media': self.exclude_media_check.isChecked(),
                'exclude_links': self.exclude_links_check.isChecked(),
                'time_filter': {
                    'enabled': self.time_filter_check.isChecked(),
                    'start_time': self.start_time.dateTime().toString(Qt.ISODate) if self.time_filter_check.isChecked() else None,
                    'end_time': self.end_time.dateTime().toString(Qt.ISODate) if self.time_filter_check.isChecked() else None
                }
            },
            'notifications': {
                'desktop_notify': self.desktop_notify_check.isChecked(),
                'sound_notify': self.sound_notify_check.isChecked(),
                'highlight': self.highlight_check.isChecked(),
                'auto_scroll': self.auto_scroll_check.isChecked(),
                'max_messages': self.max_messages.value()
            }
        }
        
        # TODO: 在主界面中处理配置保存
        QMessageBox.information(self, "配置保存", "配置已保存")
    
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
        if self.auto_scroll_check.isChecked():
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
        
        # 高亮关键字
        if self.highlight_check.isChecked() and self.keyword_input.text():
            keywords = [kw.strip() for kw in self.keyword_input.text().split(",") if kw.strip()]
            for keyword in keywords:
                if keyword in formatted_msg:
                    # 简单实现，实际应用中可能需要更复杂的富文本处理
                    formatted_msg = formatted_msg.replace(
                        keyword, f"<span style='background-color: yellow;'>{keyword}</span>"
                    )
        
        # 添加到主消息面板
        self.main_message_view.append(formatted_msg)
        
        # 添加到频道特定的消息面板
        if channel in self.channel_message_views:
            self.channel_message_views[channel].append(formatted_msg)
        
        # 自动滚动到底部
        if self.auto_scroll_check.isChecked():
            self.main_message_view.moveCursor(QTextCursor.End)
            if channel in self.channel_message_views:
                self.channel_message_views[channel].moveCursor(QTextCursor.End)
        
        # 限制消息数量
        max_messages = self.max_messages.value()
        
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
        # 清空现有项目
        self.channel_list.clear()
        
        # 清除所有频道标签页
        while self.message_tabs.count() > 1:  # 保留"所有消息"标签页
            self.message_tabs.removeTab(1)
        
        self.channel_message_views = {}
        
        # 加载监听频道
        channels = config.get('LISTEN', {}).get('channels', [])
        for channel in channels:
            # 添加到列表
            self.channel_list.addItem(channel)
            
            # 为该频道创建一个消息标签页
            channel_view = QTextEdit()
            channel_view.setReadOnly(True)
            channel_view.setLineWrapMode(QTextEdit.WidgetWidth)
            
            channel_name = channel.split('/')[-1] if '/' in channel else channel
            self.message_tabs.addTab(channel_view, channel_name)
            
            # 保存标签页引用
            self.channel_message_views[channel] = channel_view
        
        # 加载过滤选项
        filters = config.get('LISTEN', {}).get('filters', {})
        if filters:
            # 关键字
            keywords = filters.get('keywords', [])
            self.keyword_input.setText(", ".join(keywords))
            
            # 媒体类型
            media_type = filters.get('media_type', 'all')
            index = self.media_type_combo.findData(media_type)
            if index != -1:
                self.media_type_combo.setCurrentIndex(index)
            
            # 其他过滤选项
            self.exclude_forwards_check.setChecked(filters.get('exclude_forwards', False))
            self.exclude_replies_check.setChecked(filters.get('exclude_replies', False))
            self.exclude_media_check.setChecked(filters.get('exclude_media', False))
            self.exclude_links_check.setChecked(filters.get('exclude_links', False))
            
            # 时间过滤
            time_filter = filters.get('time_filter', {})
            if time_filter:
                self.time_filter_check.setChecked(time_filter.get('enabled', False))
                
                if time_filter.get('start_time'):
                    start_time = QDateTime.fromString(time_filter['start_time'], Qt.ISODate)
                    self.start_time.setDateTime(start_time)
                
                if time_filter.get('end_time'):
                    end_time = QDateTime.fromString(time_filter['end_time'], Qt.ISODate)
                    self.end_time.setDateTime(end_time)
        
        # 加载通知选项
        notifications = config.get('LISTEN', {}).get('notifications', {})
        if notifications:
            self.desktop_notify_check.setChecked(notifications.get('desktop_notify', True))
            self.sound_notify_check.setChecked(notifications.get('sound_notify', False))
            self.highlight_check.setChecked(notifications.get('highlight', True))
            self.auto_scroll_check.setChecked(notifications.get('auto_scroll', True))
            
            # 最大消息数
            max_messages = notifications.get('max_messages', 200)
            self.max_messages.setValue(max_messages) 