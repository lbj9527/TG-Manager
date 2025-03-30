"""
TG-Manager 日志查看器
显示应用程序日志，支持筛选、搜索和导出日志。
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QCheckBox, QComboBox, QPushButton,
    QGroupBox, QTextEdit, QSplitter, QToolBar, QFrame,
    QFileDialog, QMessageBox, QSizePolicy, QTableWidget,
    QTableWidgetItem, QHeaderView, QApplication
)
from PySide6.QtCore import Qt, Signal, Slot, QSize, QTimer, QDateTime
from PySide6.QtGui import QColor, QTextCharFormat, QBrush, QIcon, QFont

import os
import re
import datetime
from pathlib import Path

from src.utils.logger import get_logger

logger = get_logger()


class LogViewerView(QWidget):
    """日志查看器视图，提供日志显示、过滤和搜索功能"""
    
    # 定义日志级别颜色
    LOG_COLORS = {
        "DEBUG": QColor("#607D8B"),    # 蓝灰
        "INFO": QColor("#2196F3"),     # 蓝色
        "WARNING": QColor("#FF9800"),  # 橙色
        "ERROR": QColor("#F44336"),    # 红色
        "CRITICAL": QColor("#9C27B0")  # 紫色
    }
    
    def __init__(self, config=None, parent=None):
        """初始化日志查看器视图
        
        Args:
            config: 配置对象
            parent: 父窗口部件
        """
        super().__init__(parent)
        
        self.config = config or {}
        self.log_file_path = self._get_log_file_path()
        self.current_filter = ""
        self.auto_scroll = True
        self.log_entries = []
        self.parent_window = parent
        
        # 设置布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self.setLayout(self.main_layout)
        
        # 创建控制面板
        self._create_control_panel()
        
        # 创建日志显示区域
        self._create_log_display()
        
        # 加载日志
        self._load_logs()
        
        # 设置自动刷新
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh_logs)
        self.refresh_timer.start(2000)  # 每2秒刷新一次
        
        logger.info("日志查看器视图初始化完成")
    
    def _get_log_file_path(self):
        """获取日志文件路径
        
        Returns:
            str: 日志文件路径
        """
        # 首先从配置中获取
        if isinstance(self.config, dict) and 'LOGGING' in self.config:
            log_config = self.config.get('LOGGING', {})
            log_file = log_config.get('log_file')
            if log_file and os.path.exists(log_file):
                return log_file
        
        # 默认位置
        default_paths = [
            "logs/tg_manager.log",
            "./tg_manager.log",
            "../logs/tg_manager.log"
        ]
        
        for path in default_paths:
            if os.path.exists(path):
                return path
        
        # 如果找不到，返回默认路径
        return "logs/tg_manager.log"
    
    def _create_control_panel(self):
        """创建控制面板"""
        control_panel = QGroupBox("日志控制")
        control_layout = QVBoxLayout(control_panel)
        
        # 第一行：日志级别筛选和路径
        filter_layout = QHBoxLayout()
        
        # 日志级别选择
        level_layout = QHBoxLayout()
        level_layout.addWidget(QLabel("日志级别:"))
        
        self.level_combo = QComboBox()
        self.level_combo.addItem("全部", "ALL")
        self.level_combo.addItem("调试", "DEBUG")
        self.level_combo.addItem("信息", "INFO")
        self.level_combo.addItem("警告", "WARNING")
        self.level_combo.addItem("错误", "ERROR")
        self.level_combo.addItem("严重", "CRITICAL")
        self.level_combo.setCurrentIndex(0)
        self.level_combo.currentIndexChanged.connect(self._apply_filters)
        
        level_layout.addWidget(self.level_combo)
        filter_layout.addLayout(level_layout)
        
        filter_layout.addStretch()
        
        # 日志文件路径
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("日志文件:"))
        
        self.path_input = QLineEdit()
        self.path_input.setText(self.log_file_path)
        self.path_input.setReadOnly(True)
        
        self.browse_button = QPushButton("浏览...")
        self.browse_button.clicked.connect(self._browse_log_file)
        
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(self.browse_button)
        
        filter_layout.addLayout(path_layout)
        
        control_layout.addLayout(filter_layout)
        
        # 第二行：关键词搜索和控制按钮
        search_layout = QHBoxLayout()
        
        # 关键词搜索
        search_layout.addWidget(QLabel("搜索:"))
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入关键词进行搜索...")
        self.search_input.textChanged.connect(self._apply_filters)
        
        search_layout.addWidget(self.search_input)
        
        # 大小写敏感
        self.case_sensitive = QCheckBox("区分大小写")
        self.case_sensitive.setChecked(False)
        self.case_sensitive.stateChanged.connect(self._apply_filters)
        
        search_layout.addWidget(self.case_sensitive)
        
        # 控制按钮
        self.refresh_button = QPushButton("刷新")
        self.refresh_button.clicked.connect(self._refresh_logs)
        
        self.auto_scroll_check = QCheckBox("自动滚动")
        self.auto_scroll_check.setChecked(self.auto_scroll)
        self.auto_scroll_check.stateChanged.connect(self._toggle_auto_scroll)
        
        self.clear_button = QPushButton("清空显示")
        self.clear_button.clicked.connect(self._clear_display)
        
        self.export_button = QPushButton("导出日志")
        self.export_button.clicked.connect(self._export_logs)
        
        search_layout.addWidget(self.refresh_button)
        search_layout.addWidget(self.auto_scroll_check)
        search_layout.addWidget(self.clear_button)
        search_layout.addWidget(self.export_button)
        
        control_layout.addLayout(search_layout)
        
        # 添加到主布局
        self.main_layout.addWidget(control_panel)
    
    def _create_log_display(self):
        """创建日志显示区域"""
        # 创建日志表格
        self.log_table = QTableWidget()
        self.log_table.setColumnCount(5)
        self.log_table.setHorizontalHeaderLabels(["时间", "级别", "来源", "行号", "消息"])
        
        # 设置表格列宽
        header = self.log_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 时间
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # 级别
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # 来源
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # 行号
        header.setSectionResizeMode(4, QHeaderView.Stretch)           # 消息
        
        # 添加到主布局
        self.main_layout.addWidget(self.log_table, 1)  # 1为拉伸系数
    
    def _browse_log_file(self):
        """浏览日志文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择日志文件",
            os.path.dirname(self.log_file_path),
            "日志文件 (*.log);;所有文件 (*.*)"
        )
        
        if file_path:
            self.log_file_path = file_path
            self.path_input.setText(file_path)
            self._load_logs()
    
    def _load_logs(self):
        """加载日志文件内容"""
        try:
            # 检查日志文件是否存在
            if not os.path.exists(self.log_file_path):
                logger.warning(f"日志文件不存在: {self.log_file_path}")
                return
            
            # 清空现有日志条目
            self.log_entries = []
            
            # 读取日志文件
            with open(self.log_file_path, 'r', encoding='utf-8') as file:
                log_text = file.read()
            
            # 解析日志条目
            # 使用正则表达式解析日志格式
            # 假设格式为: [YYYY-MM-DD HH:MM:SS] [LEVEL] [SOURCE:LINE] Message
            pattern = r'\[(.*?)\]\s*\[(.*?)\]\s*\[(.*?):(.*?)\]\s*(.*?)$'
            
            for line in log_text.splitlines():
                if not line.strip():
                    continue
                    
                match = re.match(pattern, line, re.MULTILINE)
                if match:
                    timestamp, level, source, line_num, message = match.groups()
                    entry = {
                        'timestamp': timestamp.strip(),
                        'level': level.strip(),
                        'source': source.strip(),
                        'line': line_num.strip(),
                        'message': message.strip()
                    }
                    self.log_entries.append(entry)
                else:
                    # 如果无法解析，将整行作为消息添加
                    # 尝试提取时间戳和级别
                    simple_pattern = r'\[(.*?)\]\s*\[(.*?)\]'
                    simple_match = re.match(simple_pattern, line)
                    
                    if simple_match:
                        timestamp, level = simple_match.groups()
                        remaining = re.sub(simple_pattern, '', line).strip()
                        entry = {
                            'timestamp': timestamp.strip(),
                            'level': level.strip(),
                            'source': '-',
                            'line': '-',
                            'message': remaining
                        }
                    else:
                        # 如果连时间戳和级别都无法提取，将整行作为消息
                        entry = {
                            'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'level': 'INFO',
                            'source': '-',
                            'line': '-',
                            'message': line.strip()
                        }
                    
                    self.log_entries.append(entry)
            
            # 应用过滤器并显示
            self._apply_filters()
            
        except Exception as e:
            logger.error(f"加载日志文件失败: {e}")
            QMessageBox.critical(
                self,
                "错误",
                f"加载日志文件失败: {e}",
                QMessageBox.Ok
            )
    
    def _apply_filters(self):
        """应用过滤器并更新显示"""
        # 获取筛选条件
        selected_level = self.level_combo.currentData()
        search_text = self.search_input.text()
        case_sensitive = self.case_sensitive.isChecked()
        
        # 构建正则表达式对象
        if search_text:
            if case_sensitive:
                pattern = re.compile(re.escape(search_text))
            else:
                pattern = re.compile(re.escape(search_text), re.IGNORECASE)
        else:
            pattern = None
        
        # 清空表格
        self.log_table.setRowCount(0)
        
        # 记录匹配的条目数
        matched_count = 0
        
        # 过滤并显示日志
        for entry in self.log_entries:
            # 检查日志级别筛选
            if selected_level != "ALL" and entry['level'] != selected_level:
                continue
            
            # 检查搜索文本
            if pattern and not (
                pattern.search(entry['message']) or 
                pattern.search(entry['source']) or
                pattern.search(entry['level'])
            ):
                continue
            
            # 添加到表格
            row = self.log_table.rowCount()
            self.log_table.insertRow(row)
            
            # 设置单元格内容
            self.log_table.setItem(row, 0, QTableWidgetItem(entry['timestamp']))
            
            level_item = QTableWidgetItem(entry['level'])
            level_color = self.LOG_COLORS.get(entry['level'], QColor("#000000"))
            level_item.setForeground(QBrush(level_color))
            level_item.setFont(QFont("", -1, QFont.Bold))
            self.log_table.setItem(row, 1, level_item)
            
            self.log_table.setItem(row, 2, QTableWidgetItem(entry['source']))
            self.log_table.setItem(row, 3, QTableWidgetItem(entry['line']))
            self.log_table.setItem(row, 4, QTableWidgetItem(entry['message']))
            
            matched_count += 1
        
        # 如果启用了自动滚动，滚动到最后一行
        if self.auto_scroll and matched_count > 0:
            self.log_table.scrollToBottom()
        
        # 更新状态栏信息
        self._update_status_message(f"显示 {matched_count} / {len(self.log_entries)} 条日志记录")
    
    def _refresh_logs(self):
        """刷新日志"""
        # 记住当前滚动位置
        scroll_position = None
        if not self.auto_scroll:
            scroll_bar = self.log_table.verticalScrollBar()
            scroll_position = scroll_bar.value()
        
        # 重新加载日志
        self._load_logs()
        
        # 恢复滚动位置
        if scroll_position is not None and not self.auto_scroll:
            scroll_bar = self.log_table.verticalScrollBar()
            scroll_bar.setValue(scroll_position)
    
    def _toggle_auto_scroll(self, state):
        """切换自动滚动
        
        Args:
            state: 复选框状态
        """
        self.auto_scroll = (state == Qt.Checked)
        if self.auto_scroll:
            self.log_table.scrollToBottom()
    
    def _clear_display(self):
        """清空日志显示"""
        self.log_table.setRowCount(0)
        self._update_status_message("日志显示已清空")
    
    def _export_logs(self):
        """导出日志"""
        # 获取当前筛选后的日志
        filtered_logs = []
        for row in range(self.log_table.rowCount()):
            entry = {
                'timestamp': self.log_table.item(row, 0).text(),
                'level': self.log_table.item(row, 1).text(),
                'source': self.log_table.item(row, 2).text(),
                'line': self.log_table.item(row, 3).text(),
                'message': self.log_table.item(row, 4).text()
            }
            filtered_logs.append(entry)
        
        if not filtered_logs:
            QMessageBox.information(
                self,
                "导出日志",
                "没有日志记录可导出。",
                QMessageBox.Ok
            )
            return
        
        # 获取导出文件路径
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出日志",
            f"logs_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
            "日志文件 (*.log);;文本文件 (*.txt);;所有文件 (*.*)"
        )
        
        if not file_path:
            return
        
        try:
            # 写入日志
            with open(file_path, 'w', encoding='utf-8') as file:
                for entry in filtered_logs:
                    file.write(f"[{entry['timestamp']}] [{entry['level']}] [{entry['source']}:{entry['line']}] {entry['message']}\n")
            
            QMessageBox.information(
                self,
                "导出成功",
                f"日志成功导出到: {file_path}",
                QMessageBox.Ok
            )
            
        except Exception as e:
            logger.error(f"导出日志失败: {e}")
            QMessageBox.critical(
                self,
                "导出失败",
                f"导出日志失败: {e}",
                QMessageBox.Ok
            )
    
    def closeEvent(self, event):
        """关闭事件处理
        
        Args:
            event: 关闭事件
        """
        # 停止刷新定时器
        if self.refresh_timer.isActive():
            self.refresh_timer.stop()
        
        # 接受关闭事件
        event.accept()
    
    def _update_status_message(self, message):
        """安全地更新状态栏消息
        
        Args:
            message: 要显示的消息
        """
        # 尝试查找MainWindow父窗口
        parent = self.parent()
        while parent:
            if hasattr(parent, 'statusBar') and callable(parent.statusBar):
                parent.statusBar().showMessage(message)
                return
            parent = parent.parent()
        
        # 如果找不到有状态栏的父窗口，只记录消息
        logger.debug(f"状态消息: {message}") 