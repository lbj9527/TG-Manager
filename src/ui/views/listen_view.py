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
    QSizePolicy, QDoubleSpinBox
)
from PySide6.QtCore import Qt, Signal, Slot, QDateTime
from PySide6.QtGui import QIcon, QTextCursor
from datetime import datetime

from src.utils.logger import get_logger
from src.utils.ui_config_models import UIMonitorConfig, UIMonitorChannelPair, MediaType

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
        
        # 创建配置标签页
        self.config_tabs = QTabWidget()
        # 增加配置区域的高度，确保控件显示清晰
        self.config_tabs.setMaximumHeight(420)
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
        
        # 创建顶部表单面板 - 直接添加到配置布局，移除QGroupBox
        form_layout = QFormLayout()
        form_layout.setSpacing(6)  # 增加表单项间距
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
        
        # 创建复选框 - 移除媒体说明
        self.remove_captions_check = QCheckBox("移除媒体说明文字")
        form_layout.addRow("", self.remove_captions_check)
        
        # 文本替换规则
        self.original_text_input = QLineEdit()
        self.original_text_input.setPlaceholderText("要替换的原始文本")
        form_layout.addRow("文本替换:", self.original_text_input)
        
        self.target_text_input = QLineEdit()
        self.target_text_input.setPlaceholderText("替换后的目标文本")
        form_layout.addRow("替换为:", self.target_text_input)
        
        # 将表单直接添加到配置布局
        config_layout.addLayout(form_layout)
        
        # 创建水平布局存放添加按钮和频道列表
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
        
        # 直接添加到配置布局
        config_layout.addLayout(channel_action_layout)
        
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
        channel_widget_layout.addWidget(scroll_area)
        
        # 直接添加到配置布局
        config_layout.addWidget(channel_widget, 1)  # 添加伸展系数
        
        # 监听选项标签页
        self.options_tab = QWidget()
        options_layout = QVBoxLayout(self.options_tab)
        options_layout.setContentsMargins(4, 4, 4, 4)  # 减小外边距
        options_layout.setSpacing(8)  # 增加垂直间距
        
        # 媒体类型选择 - 直接添加到选项布局，移除QGroupBox
        media_types_label = QLabel("要转发的媒体类型:")
        media_types_label.setStyleSheet("font-weight: bold;")
        options_layout.addWidget(media_types_label)
        
        # 媒体类型复选框
        media_types_row1 = QHBoxLayout()
        media_types_row2 = QHBoxLayout()
        
        self.media_types_checkboxes = {}
        
        # 第一行
        self.media_types_checkboxes["photo"] = QCheckBox("照片")
        self.media_types_checkboxes["video"] = QCheckBox("视频")
        self.media_types_checkboxes["document"] = QCheckBox("文件")
        self.media_types_checkboxes["audio"] = QCheckBox("音频")
        
        media_types_row1.addWidget(self.media_types_checkboxes["photo"])
        media_types_row1.addWidget(self.media_types_checkboxes["video"])
        media_types_row1.addWidget(self.media_types_checkboxes["document"])
        media_types_row1.addWidget(self.media_types_checkboxes["audio"])
        media_types_row1.addStretch(1)
        
        # 第二行
        self.media_types_checkboxes["animation"] = QCheckBox("动画")
        self.media_types_checkboxes["sticker"] = QCheckBox("贴纸")
        self.media_types_checkboxes["voice"] = QCheckBox("语音")
        self.media_types_checkboxes["video_note"] = QCheckBox("视频笔记")
        
        media_types_row2.addWidget(self.media_types_checkboxes["animation"])
        media_types_row2.addWidget(self.media_types_checkboxes["sticker"])
        media_types_row2.addWidget(self.media_types_checkboxes["voice"])
        media_types_row2.addWidget(self.media_types_checkboxes["video_note"])
        media_types_row2.addStretch(1)
        
        # 默认选中所有媒体类型
        for checkbox in self.media_types_checkboxes.values():
            checkbox.setChecked(True)
            checkbox.setStyleSheet("padding: 4px;")  # 添加内边距，使复选框更大
        
        # 直接添加到选项布局
        options_layout.addLayout(media_types_row1)
        options_layout.addLayout(media_types_row2)
        
        # 添加一些间距
        options_layout.addSpacing(10)
        
        # 监听参数 - 直接添加到选项布局，移除QGroupBox
        monitor_options_label = QLabel("监听参数:")
        monitor_options_label.setStyleSheet("font-weight: bold;")
        options_layout.addWidget(monitor_options_label)
        
        # 使用表单布局直接添加到选项布局
        monitor_options_layout = QFormLayout()
        monitor_options_layout.setSpacing(8)  # 增加表单项间距
        monitor_options_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)  # 标签右对齐
        
        # 转发延迟
        self.forward_delay = QDoubleSpinBox()
        self.forward_delay.setRange(0, 60)
        self.forward_delay.setValue(1.0)
        self.forward_delay.setDecimals(1)
        self.forward_delay.setSingleStep(0.1)
        self.forward_delay.setSuffix(" 秒")
        self.forward_delay.setMinimumHeight(26)  # 增加高度
        monitor_options_layout.addRow("转发延迟:", self.forward_delay)
        
        # 监听截止日期
        self.duration_check = QCheckBox("启用监听截止日期")
        self.duration_check.setStyleSheet("padding: 4px;")  # 添加内边距
        monitor_options_layout.addRow("", self.duration_check)
        
        self.duration_date = QDateTimeEdit(QDateTime.currentDateTime().addDays(365))
        self.duration_date.setCalendarPopup(True)
        self.duration_date.setDisplayFormat("yyyy-MM-dd")
        self.duration_date.setEnabled(False)
        self.duration_date.setMinimumHeight(26)  # 增加高度
        monitor_options_layout.addRow("截止日期:", self.duration_date)
        
        # 连接时间过滤复选框和日期选择器的启用状态
        self.duration_check.toggled.connect(self.duration_date.setEnabled)
        
        # 直接添加到选项布局
        options_layout.addLayout(monitor_options_layout)
        
        # 添加弹性空间，使内容靠上对齐
        options_layout.addStretch(1)
        
        # 将标签页添加到配置标签页部件
        self.config_tabs.addTab(self.config_tab, "频道配置")
        self.config_tabs.addTab(self.options_tab, "媒体和参数")
    
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
        
        # 设置消息面板的尺寸策略，让它能够占据可用空间但不要太大
        self.message_tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # 设置最小高度，确保消息区域有足够空间显示
        self.message_tabs.setMinimumHeight(180)
        
        # 将消息标签页直接添加到主布局，占据剩余空间
        self.main_layout.addWidget(self.message_tabs, 1)  # 使用较小的伸展因子，让配置面板占据更多空间
    
    def _create_action_buttons(self):
        """创建底部操作按钮"""
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)  # 增加按钮间距
        
        self.start_listen_button = QPushButton("开始监听")
        self.start_listen_button.setMinimumHeight(40)
        
        self.stop_listen_button = QPushButton("停止监听")
        self.stop_listen_button.setEnabled(False)
        self.stop_listen_button.setMinimumHeight(40)
        
        self.save_config_button = QPushButton("保存配置")
        self.save_config_button.setMinimumHeight(30)  # 稍微降低其他按钮的高度，与主按钮区分
        
        self.clear_messages_button = QPushButton("清空消息")
        self.clear_messages_button.setMinimumHeight(30)
        
        self.export_messages_button = QPushButton("导出消息")
        self.export_messages_button.setMinimumHeight(30)
        
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
        self.add_channel_pair_button.clicked.connect(self._add_channel_pair)
        self.remove_channel_pair_button.clicked.connect(self._remove_channel_pairs)
        
        # 消息操作
        self.clear_messages_button.clicked.connect(self._clear_messages)
        self.export_messages_button.clicked.connect(self._export_messages)
        
        # 监听控制
        self.start_listen_button.clicked.connect(self._start_listen)
        self.stop_listen_button.clicked.connect(self._stop_listen)
        self.save_config_button.clicked.connect(self._save_config)
    
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
        
        # 文本替换规则
        text_filter = []
        original_text = self.original_text_input.text().strip()
        target_text = self.target_text_input.text().strip()
        if original_text and target_text:
            text_filter.append({
                "original_text": original_text,
                "target_text": target_text
            })
        
        # 存储完整数据
        pair_data = {
            "source_channel": source_channel,
            "target_channels": target_channels,
            "remove_captions": self.remove_captions_check.isChecked(),
            "text_filter": text_filter
        }
        
        # 添加到列表，采用与下载界面类似的样式
        target_channels_str = ", ".join(target_channels)
        text_filter_str = ""
        if text_filter:
            text_filter_str = f" - 替换规则: {len(text_filter)}条"
        
        display_text = f"{source_channel} -> {target_channels_str}{text_filter_str}"
        if self.remove_captions_check.isChecked():
            display_text += " (移除媒体说明)"
        
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
    
    def _export_messages(self):
        """导出消息"""
        # TODO: 实现消息导出功能
        QMessageBox.information(self, "提示", "导出功能尚未实现")
    
    def _start_listen(self):
        """开始监听"""
        # 检查是否有监听频道对
        if self.pairs_list.count() == 0:
            QMessageBox.warning(self, "警告", "请先添加至少一个监听频道对")
            return
        
        # 获取监听配置
        monitor_config = self._get_monitor_config()
        
        # 发出监听开始信号
        self.listen_started.emit(monitor_config)
        
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
            monitor_channel_pairs.append({
                "source_channel": data["source_channel"],
                "target_channels": data["target_channels"],
                "remove_captions": data["remove_captions"],
                "text_filter": data.get("text_filter", [])
            })
        
        # 获取媒体类型
        media_types = []
        for media_type, checkbox in self.media_types_checkboxes.items():
            if checkbox.isChecked():
                media_types.append(media_type)
        
        # 获取监听截止日期
        duration = None
        if self.duration_check.isChecked():
            duration = self.duration_date.date().toString("yyyy-MM-dd")
        
        # 获取转发延迟
        forward_delay = round(float(self.forward_delay.value()), 1)
        
        # 收集监听配置 - 只保留UIMonitorConfig所需的字段
        monitor_config = {
            'monitor_channel_pairs': monitor_channel_pairs,
            'media_types': media_types,
            'duration': duration,
            'forward_delay': forward_delay
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
        
        # 创建UIMonitorConfig对象
        try:
            # 格式化数据以匹配UIMonitorConfig期望的结构
            monitor_channel_pairs = []
            for pair in monitor_config['monitor_channel_pairs']:
                # 创建UIMonitorChannelPair对象
                monitor_channel_pairs.append(UIMonitorChannelPair(
                    source_channel=pair['source_channel'],
                    target_channels=pair['target_channels'],
                    remove_captions=pair['remove_captions'],
                    text_filter=pair.get('text_filter', [])
                ))
            
            ui_monitor_config = UIMonitorConfig(
                monitor_channel_pairs=monitor_channel_pairs,
                media_types=monitor_config['media_types'],
                duration=monitor_config['duration'],
                forward_delay=monitor_config['forward_delay']
            )
            
            # 更新配置
            if 'MONITOR' in self.config:
                self.config['MONITOR'] = ui_monitor_config.dict()
            else:
                self.config.update({'MONITOR': ui_monitor_config.dict()})
            
            QMessageBox.information(self, "配置保存", "监听配置已保存")
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
        
        # 添加到主消息面板
        self.main_message_view.append(formatted_msg)
        
        # 添加到频道特定的消息面板
        if channel in self.channel_message_views:
            self.channel_message_views[channel].append(formatted_msg)
        
        # 自动滚动到底部
            self.main_message_view.moveCursor(QTextCursor.End)
            if channel in self.channel_message_views:
                self.channel_message_views[channel].moveCursor(QTextCursor.End)
        
        # 限制消息数量 - 使用固定值200条
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
            
            if not source_channel or not target_channels:
                continue
            
            # 添加到列表，采用与下载界面类似的样式
            target_channels_str = ", ".join(target_channels)
            text_filter_str = ""
            if text_filter:
                text_filter_str = f" - 替换规则: {len(text_filter)}条"
            
            display_text = f"{source_channel} -> {target_channels_str}{text_filter_str}"
            if remove_captions:
                display_text += " (移除媒体说明)"
            
            item = QListWidgetItem(display_text)
            # 存储完整数据
            pair_data = {
                "source_channel": source_channel,
                "target_channels": target_channels,
                "remove_captions": remove_captions,
                "text_filter": text_filter
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
        
        # 加载媒体类型
        media_types = monitor_config.get('media_types', [])
        
        # 先取消选中所有复选框
        for checkbox in self.media_types_checkboxes.values():
            checkbox.setChecked(False)
        
        # 选中配置中指定的媒体类型
        for media_type in media_types:
            if media_type in self.media_types_checkboxes:
                self.media_types_checkboxes[media_type].setChecked(True)
        
        # 加载转发延迟
        forward_delay = monitor_config.get('forward_delay', 1.0)
        if isinstance(forward_delay, (int, float)):
            self.forward_delay.setValue(float(forward_delay))
        
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
        
        # 加载过滤选项
        # 注意：现在过滤选项存储在配置的filters字段中，而不是直接在MONITOR中
        # 由于结构变化，我们需要适应旧配置格式和新格式
        filters = {}
        
        # 首先检查是否有新格式的filters字段
        if 'LISTEN' in config and 'filters' in config['LISTEN']:
            filters = config['LISTEN'].get('filters', {})
        
        if filters:
            # 关键字
            keywords = filters.get('keywords', [])
            self.keyword_input.setText(", ".join(keywords))
            
            # 其他过滤选项
            self.exclude_forwards_check.setChecked(filters.get('exclude_forwards', False))
            self.exclude_replies_check.setChecked(filters.get('exclude_replies', False))
            self.exclude_media_check.setChecked(filters.get('exclude_media', False))
            self.exclude_links_check.setChecked(filters.get('exclude_links', False))
            
        # 加载通知选项
        # 同样，注意结构变化
        notifications = {}
        
        if 'LISTEN' in config and 'notifications' in config['LISTEN']:
            notifications = config['LISTEN'].get('notifications', {})
        
        if notifications:
            self.desktop_notify_check.setChecked(notifications.get('desktop_notify', True))
            self.sound_notify_check.setChecked(notifications.get('sound_notify', False))
            self.highlight_check.setChecked(notifications.get('highlight', True))
            self.auto_scroll_check.setChecked(notifications.get('auto_scroll', True))
            
            # 最大消息数
            max_messages = notifications.get('max_messages', 200)
            self.max_messages.setValue(max_messages) 