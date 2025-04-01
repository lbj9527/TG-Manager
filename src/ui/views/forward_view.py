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
    QProgressBar, QTabWidget, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, Slot, QSize
from PySide6.QtGui import QIcon

from src.utils.logger import get_logger

logger = get_logger()


class ForwardView(QWidget):
    """转发界面，提供Telegram频道间消息转发功能"""
    
    # 转发开始信号
    forward_started = Signal(dict)  # 转发配置
    
    def __init__(self, config=None, parent=None):
        """初始化转发界面
        
        Args:
            config: 配置对象
            parent: 父窗口部件
        """
        super().__init__(parent)
        
        self.config = config or {}
        
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
        
        # 创建上部配置标签页
        self.config_tabs = QTabWidget()
        self.config_tabs.setMaximumHeight(320)  # 设置最大高度
        self.config_tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.main_layout.addWidget(self.config_tabs)
        
        # 创建配置标签页
        self._create_config_panel()
        
        # 创建下部转发规则和状态面板
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
        # 源频道标签页
        self.source_tab = QWidget()
        source_layout = QVBoxLayout(self.source_tab)
        source_layout.setContentsMargins(4, 4, 4, 4)  # 减小边距
        source_layout.setSpacing(4)  # 减小间距
        
        # 源频道输入
        form_layout = QFormLayout()
        
        self.source_input = QLineEdit()
        self.source_input.setPlaceholderText("频道链接或ID (例如: https://t.me/example 或 -1001234567890)")
        form_layout.addRow("源频道:", self.source_input)
        
        source_layout.addLayout(form_layout)
        
        # 添加源频道按钮
        button_layout = QHBoxLayout()
        self.add_source_button = QPushButton("添加源频道")
        self.remove_source_button = QPushButton("删除所选")
        
        button_layout.addWidget(self.add_source_button)
        button_layout.addWidget(self.remove_source_button)
        button_layout.addStretch(1)
        
        source_layout.addLayout(button_layout)
        
        # 源频道列表
        source_list_label = QLabel("已配置源频道:")
        
        self.source_list = QListWidget()
        self.source_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.source_list.setMinimumHeight(160)  # 设置最小高度
        
        source_layout.addWidget(source_list_label)
        source_layout.addWidget(self.source_list, 1)  # 使列表占据所有剩余空间
        
        # 转发选项标签页
        self.options_tab = QWidget()
        options_layout = QVBoxLayout(self.options_tab)
        options_layout.setContentsMargins(4, 4, 4, 4)  # 减小边距
        options_layout.setSpacing(4)  # 减小间距
        
        # 转发选项
        options_grid = QGridLayout()
        
        self.preserve_date_check = QCheckBox("保留原始日期")
        options_grid.addWidget(self.preserve_date_check, 0, 0)
        
        self.disable_notification_check = QCheckBox("静默通知")
        options_grid.addWidget(self.disable_notification_check, 0, 1)
        
        self.remove_caption_check = QCheckBox("移除原始说明文字")
        options_grid.addWidget(self.remove_caption_check, 1, 0)
        
        self.custom_caption_check = QCheckBox("使用自定义说明文字")
        self.custom_caption_check.toggled.connect(lambda checked: self.caption_template.setEnabled(checked))
        options_grid.addWidget(self.custom_caption_check, 1, 1)
        
        self.protect_content_check = QCheckBox("保护内容")
        options_grid.addWidget(self.protect_content_check, 2, 0)
        
        self.schedule_message_check = QCheckBox("定时发送消息")
        options_grid.addWidget(self.schedule_message_check, 2, 1)
        
        options_layout.addLayout(options_grid)
        
        # 说明文字模板
        caption_layout = QVBoxLayout()
        caption_layout.addWidget(QLabel("自定义说明文字模板:"))
        
        self.caption_template = QTextEdit()
        self.caption_template.setPlaceholderText("可用变量:\n{original_text} - 原始说明文字\n{source_channel} - 源频道信息\n{date} - 消息日期")
        self.caption_template.setEnabled(False)
        self.caption_template.setMaximumHeight(80)
        
        caption_layout.addWidget(self.caption_template)
        options_layout.addLayout(caption_layout)
        
        # 转发延迟
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("转发延迟:"))
        
        self.forward_delay = QSpinBox()
        self.forward_delay.setRange(0, 60)
        self.forward_delay.setValue(3)
        self.forward_delay.setSuffix(" 秒")
        
        delay_layout.addWidget(self.forward_delay)
        delay_layout.addStretch()
        
        options_layout.addLayout(delay_layout)
        
        # 转发规则标签页
        self.rules_tab = QWidget()
        rules_layout = QVBoxLayout(self.rules_tab)
        rules_layout.setContentsMargins(4, 4, 4, 4)  # 减小边距
        rules_layout.setSpacing(4)  # 减小间距
        
        # 规则创建表单
        rule_form = QFormLayout()
        
        self.target_input = QLineEdit()
        self.target_input.setPlaceholderText("目标频道链接或ID")
        rule_form.addRow("目标频道:", self.target_input)
        
        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("留空表示不过滤关键词")
        rule_form.addRow("关键词过滤:", self.keyword_input)
        
        self.media_type_combo = QComboBox()
        self.media_type_combo.addItem("所有类型", "all")
        self.media_type_combo.addItem("仅文本", "text")
        self.media_type_combo.addItem("仅照片", "photo")
        self.media_type_combo.addItem("仅视频", "video")
        self.media_type_combo.addItem("仅文件", "document")
        rule_form.addRow("媒体类型:", self.media_type_combo)
        
        rules_layout.addLayout(rule_form)
        
        # 添加规则按钮
        rule_button_layout = QHBoxLayout()
        self.add_rule_button = QPushButton("添加规则")
        rule_button_layout.addWidget(self.add_rule_button)
        rule_button_layout.addStretch(1)
        
        rules_layout.addLayout(rule_button_layout)
        
        # 将标签页添加到配置面板
        self.config_tabs.addTab(self.source_tab, "源频道")
        self.config_tabs.addTab(self.options_tab, "转发选项")
        self.config_tabs.addTab(self.rules_tab, "转发规则")
    
    def _create_forward_panel(self):
        """创建转发规则和状态面板"""
        # 转发规则列表
        rules_group = QGroupBox("转发规则列表")
        rules_layout = QVBoxLayout(rules_group)
        
        # 创建规则表格
        self.rules_table = QTableWidget()
        self.rules_table.setColumnCount(4)
        self.rules_table.setHorizontalHeaderLabels(["源频道", "目标频道", "关键词", "媒体类型"])
        self.rules_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.rules_table.setSelectionMode(QTableWidget.SingleSelection)
        self.rules_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.rules_table.horizontalHeader().setStretchLastSection(True)
        
        rules_layout.addWidget(self.rules_table)
        
        # 添加到主布局
        self.main_layout.addWidget(rules_group, 2)  # 给规则表格更多空间
        
        # 转发状态面板
        self.status_group = QGroupBox("转发状态")
        status_layout = QVBoxLayout(self.status_group)
        
        # 状态表格
        self.status_table = QTableWidget()
        self.status_table.setColumnCount(4)
        self.status_table.setHorizontalHeaderLabels(["源频道", "目标频道", "已转发消息数", "状态"])
        self.status_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.status_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.status_table.horizontalHeader().setStretchLastSection(True)
        
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
        
        # 添加到主布局
        self.main_layout.addWidget(self.status_group, 1)
    
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
        # 源频道管理
        self.add_source_button.clicked.connect(self._add_source)
        self.remove_source_button.clicked.connect(self._remove_sources)
        
        # 转发规则管理
        self.add_rule_button.clicked.connect(self._add_rule)
        
        # 转发控制
        self.start_forward_button.clicked.connect(self._start_forward)
        self.stop_forward_button.clicked.connect(self._stop_forward)
        self.save_config_button.clicked.connect(self._save_config)
        
        # 启用自定义说明文字
        self.custom_caption_check.toggled.connect(self.caption_template.setEnabled)
    
    def _init_state(self):
        """初始化状态"""
        self.forward_rules = []
        self.rules_table.setRowCount(0)
        self.status_table.setRowCount(0)
        self.overall_status_label.setText("等待转发...")
        self.forwarded_count_label.setText("已转发: 0 条消息")
        self.start_forward_button.setEnabled(True)
        self.stop_forward_button.setEnabled(False)
        self.save_config_button.setEnabled(True)
        self.source_input.clear()
        self.target_input.clear()
        self.keyword_input.clear()
        self.media_type_combo.setCurrentIndex(0)
        self.source_list.clear()
        self.caption_template.setEnabled(False)
        self.caption_template.setPlainText("")
        self.forward_delay.setValue(3)
        self.preserve_date_check.setChecked(False)
        self.disable_notification_check.setChecked(False)
        self.remove_caption_check.setChecked(False)
        self.custom_caption_check.setChecked(False)
        self.protect_content_check.setChecked(False)
        self.schedule_message_check.setChecked(False)
    
    def _add_source(self):
        """添加源频道到列表"""
        source = self.source_input.text().strip()
        
        if not source:
            QMessageBox.warning(self, "警告", "请输入源频道链接或ID")
            return
        
        # 检查是否已存在相同频道
        for i in range(self.source_list.count()):
            if self.source_list.item(i).text() == source:
                QMessageBox.information(self, "提示", "此源频道已在列表中")
                return
        
        # 添加到列表
        self.source_list.addItem(source)
        
        # 清空输入
        self.source_input.clear()
    
    def _remove_sources(self):
        """删除选中的源频道"""
        selected_items = self.source_list.selectedItems()
        
        if not selected_items:
            QMessageBox.information(self, "提示", "请先选择要删除的源频道")
            return
        
        # 删除选中的源频道
        for item in reversed(selected_items):
            row = self.source_list.row(item)
            self.source_list.takeItem(row)
    
    def _add_rule(self):
        """添加转发规则"""
        # 检查是否有源频道
        if self.source_list.count() == 0:
            QMessageBox.warning(self, "警告", "请先添加至少一个源频道")
            return
        
        # 获取目标频道
        target = self.target_input.text().strip()
        if not target:
            QMessageBox.warning(self, "警告", "请输入目标频道链接或ID")
            return
        
        # 获取关键字过滤
        keywords = [kw.strip() for kw in self.keyword_input.text().split(",") if kw.strip()]
        
        # 获取媒体类型
        media_type = self.media_type_combo.currentData()
        media_type_text = self.media_type_combo.currentText()
        
        # 创建转发规则
        source_channel = self.source_list.item(0).text()  # 默认使用第一个源频道
        
        # 添加规则到表格
        row_position = self.rules_table.rowCount()
        self.rules_table.insertRow(row_position)
        
        # 设置单元格项
        self.rules_table.setItem(row_position, 0, QTableWidgetItem(source_channel))
        self.rules_table.setItem(row_position, 1, QTableWidgetItem(target))
        self.rules_table.setItem(row_position, 2, QTableWidgetItem(", ".join(keywords) if keywords else "无过滤"))
        self.rules_table.setItem(row_position, 3, QTableWidgetItem(media_type_text))
        
        # 操作按钮
        delete_button = QPushButton("删除")
        delete_button.clicked.connect(lambda: self._delete_rule(row_position))
        self.rules_table.setCellWidget(row_position, 4, delete_button)
        
        # 清空输入
        self.target_input.clear()
        self.keyword_input.clear()
        
        # 添加到规则列表
        self.forward_rules.append({
            'source': source_channel,
            'target': target,
            'keywords': keywords,
            'media_type': media_type
        })
    
    def _delete_rule(self, row):
        """删除指定行的转发规则
        
        Args:
            row: 要删除的行索引
        """
        if 0 <= row < len(self.forward_rules):
            # 从规则列表中删除
            self.forward_rules.pop(row)
            
            # 从表格中删除
            self.rules_table.removeRow(row)
            
            # 更新删除按钮的连接
            for i in range(row, self.rules_table.rowCount()):
                delete_button = QPushButton("删除")
                delete_button.clicked.connect(lambda r=i: self._delete_rule(r))
                self.rules_table.setCellWidget(i, 4, delete_button)
    
    def _start_forward(self):
        """开始转发"""
        # 检查是否有源频道
        if self.source_list.count() == 0:
            QMessageBox.warning(self, "警告", "请先添加至少一个源频道")
            return
        
        # 检查是否有转发规则
        if len(self.forward_rules) == 0:
            QMessageBox.warning(self, "警告", "请至少添加一条转发规则")
            return
        
        # 获取源频道列表
        source_channels = []
        for i in range(self.source_list.count()):
            source_channels.append(self.source_list.item(i).text())
        
        # 收集配置
        config = {
            'source_channels': source_channels,
            'rules': self.forward_rules,
            'options': {
                'preserve_date': self.preserve_date_check.isChecked(),
                'disable_notification': self.disable_notification_check.isChecked(),
                'remove_caption': self.remove_caption_check.isChecked(),
                'custom_caption': {
                    'enabled': self.custom_caption_check.isChecked(),
                    'template': self.caption_template.toPlainText()
                },
                'protect_content': self.protect_content_check.isChecked(),
                'schedule_message': self.schedule_message_check.isChecked(),
                'forward_delay': self.forward_delay.value()
            }
        }
        
        # 发出转发开始信号
        self.forward_started.emit(config)
        
        # 更新状态
        self.overall_status_label.setText("转发进行中...")
        
        # 更新按钮状态
        self.start_forward_button.setEnabled(False)
        self.stop_forward_button.setEnabled(True)
        
        # 初始化状态表格
        self._init_status_table(config)
    
    def _init_status_table(self, config):
        """根据配置初始化状态表格"""
        self.status_table.setRowCount(0)
        
        # 为每个规则添加一行
        for rule in config['rules']:
            row_position = self.status_table.rowCount()
            self.status_table.insertRow(row_position)
            
            self.status_table.setItem(row_position, 0, QTableWidgetItem(rule['source']))
            self.status_table.setItem(row_position, 1, QTableWidgetItem(rule['target']))
            self.status_table.setItem(row_position, 2, QTableWidgetItem("0"))
            self.status_table.setItem(row_position, 3, QTableWidgetItem("等待中"))
    
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
        # 检查是否有源频道
        if self.source_list.count() == 0:
            QMessageBox.warning(self, "警告", "请先添加至少一个源频道")
            return
        
        # 获取源频道列表
        source_channels = []
        for i in range(self.source_list.count()):
            source_channels.append(self.source_list.item(i).text())
        
        # 收集配置
        config = {
            'source_channels': source_channels,
            'rules': self.forward_rules,
            'options': {
                'preserve_date': self.preserve_date_check.isChecked(),
                'disable_notification': self.disable_notification_check.isChecked(),
                'remove_caption': self.remove_caption_check.isChecked(),
                'custom_caption': {
                    'enabled': self.custom_caption_check.isChecked(),
                    'template': self.caption_template.toPlainText()
                },
                'protect_content': self.protect_content_check.isChecked(),
                'schedule_message': self.schedule_message_check.isChecked(),
                'forward_delay': self.forward_delay.value()
            }
        }
        
        # TODO: 在主界面中处理配置保存
        QMessageBox.information(self, "配置保存", "配置已保存")
    
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
    
    def forward_completed(self):
        """所有转发任务完成"""
        # 更新状态
        self.overall_status_label.setText("转发已完成")
        
        # 更新按钮状态
        self.start_forward_button.setEnabled(True)
        self.stop_forward_button.setEnabled(False)
        
        # 显示完成消息
        QMessageBox.information(self, "转发完成", "所有转发任务已完成")
    
    def load_config(self, config):
        """从配置加载UI状态
        
        Args:
            config: 配置字典
        """
        # 清空现有项目
        self.source_list.clear()
        self.rules_table.setRowCount(0)
        self.forward_rules = []
        
        # 加载源频道
        source_channels = config.get('FORWARD', {}).get('source_channels', [])
        for channel in source_channels:
            self.source_list.addItem(channel)
        
        # 加载转发规则
        rules = config.get('FORWARD', {}).get('rules', [])
        for rule in rules:
            # 添加到规则列表
            self.forward_rules.append(rule)
            
            # 添加到表格
            row_position = self.rules_table.rowCount()
            self.rules_table.insertRow(row_position)
            
            # 设置单元格项
            self.rules_table.setItem(row_position, 0, QTableWidgetItem(rule['source']))
            self.rules_table.setItem(row_position, 1, QTableWidgetItem(rule['target']))
            self.rules_table.setItem(row_position, 2, QTableWidgetItem(
                ", ".join(rule['keywords']) if rule.get('keywords') else "无过滤"
            ))
            
            # 获取媒体类型显示文本
            media_type = rule.get('media_type', 'all')
            media_type_text = "所有类型"
            if media_type == 'text':
                media_type_text = "仅文本"
            elif media_type == 'photo':
                media_type_text = "仅照片"
            elif media_type == 'video':
                media_type_text = "仅视频"
            elif media_type == 'document':
                media_type_text = "仅文件"
            
            self.rules_table.setItem(row_position, 3, QTableWidgetItem(media_type_text))
            
            # 操作按钮
            delete_button = QPushButton("删除")
            delete_button.clicked.connect(lambda r=row_position: self._delete_rule(r))
            self.rules_table.setCellWidget(row_position, 4, delete_button)
        
        # 加载选项
        options = config.get('FORWARD', {}).get('options', {})
        if options:
            self.preserve_date_check.setChecked(options.get('preserve_date', False))
            self.disable_notification_check.setChecked(options.get('disable_notification', False))
            self.remove_caption_check.setChecked(options.get('remove_caption', False))
            
            # 自定义说明文字
            custom_caption = options.get('custom_caption', {})
            if custom_caption:
                self.custom_caption_check.setChecked(custom_caption.get('enabled', False))
                self.caption_template.setPlainText(custom_caption.get('template', ''))
            
            self.protect_content_check.setChecked(options.get('protect_content', False))
            self.schedule_message_check.setChecked(options.get('schedule_message', False))
            self.forward_delay.setValue(options.get('forward_delay', 3))
        
        # 初始化状态
        self._init_state()
    
    def _init_state(self):
        """初始化状态"""
        self.forward_rules = []
        self.rules_table.setRowCount(0)
        self.status_table.setRowCount(0)
        self.overall_status_label.setText("等待转发...")
        self.forwarded_count_label.setText("已转发: 0 条消息")
        self.start_forward_button.setEnabled(True)
        self.stop_forward_button.setEnabled(False)
        self.save_config_button.setEnabled(True)
        self.source_input.clear()
        self.target_input.clear()
        self.keyword_input.clear()
        self.media_type_combo.setCurrentIndex(0)
        self.source_list.clear()
        self.caption_template.setEnabled(False)
        self.caption_template.setPlainText("")
        self.forward_delay.setValue(3)
        self.preserve_date_check.setChecked(False)
        self.disable_notification_check.setChecked(False)
        self.remove_caption_check.setChecked(False)
        self.custom_caption_check.setChecked(False)
        self.protect_content_check.setChecked(False)
        self.schedule_message_check.setChecked(False) 