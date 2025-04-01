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
        
        # 使用当前日期获取日志文件
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        today_simple = datetime.datetime.now().strftime('%Y%m%d')
        
        # 检查不同格式的日志文件
        log_paths = [
            f"logs/app_{today}.log",  # UI应用日志
            f"logs/tg_forwarder_{today_simple}.log",  # 转发器日志
            "logs/tg_manager.log",  # 默认名称
            "./tg_manager.log",
            "../logs/tg_manager.log"
        ]
        
        # 尝试查找logs目录下的所有日志文件
        logs_dir = Path("logs")
        if logs_dir.exists() and logs_dir.is_dir():
            # 列出logs目录下的所有日志文件并按修改时间排序
            log_files = sorted(
                [f for f in logs_dir.glob("*.log") if f.is_file()],
                key=lambda x: os.path.getmtime(x),
                reverse=True  # 最新的文件排在前面
            )
            
            if log_files:
                # 如果找到日志文件，返回最新的一个
                logger.debug(f"找到最新的日志文件: {log_files[0]}")
                return str(log_files[0])
        
        # 检查指定路径
        for path in log_paths:
            if os.path.exists(path):
                logger.debug(f"找到日志文件: {path}")
                return path
        
        # 如果找不到，返回默认路径并记录警告
        logger.warning(f"未找到有效的日志文件，将使用默认路径: logs/app_{today}.log")
        return f"logs/app_{today}.log"
    
    def _create_control_panel(self):
        """创建控制面板"""
        # 创建控制面板分组框
        control_group = QGroupBox("日志控制")
        control_layout = QVBoxLayout(control_group)
        
        # 文件路径面板
        path_panel = QHBoxLayout()
        path_panel.addWidget(QLabel("日志文件:"))
        
        self.path_input = QLineEdit(self.log_file_path)
        self.path_input.setReadOnly(True)
        path_panel.addWidget(self.path_input, 1)
        
        browse_button = QPushButton("浏览...")
        browse_button.clicked.connect(self._browse_log_file)
        path_panel.addWidget(browse_button)
        
        refresh_button = QPushButton("刷新")
        refresh_button.clicked.connect(self._refresh_logs)
        path_panel.addWidget(refresh_button)
        
        control_layout.addLayout(path_panel)
        
        # 文件路径状态标签
        self.file_path_label = QLabel(f"当前日志文件: {self.log_file_path}")
        control_layout.addWidget(self.file_path_label)
        
        # 筛选面板
        filter_panel = QHBoxLayout()
        
        # 关键字筛选
        filter_panel.addWidget(QLabel("关键字:"))
        
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("输入关键字筛选日志")
        self.filter_input.textChanged.connect(self._filter_changed)
        filter_panel.addWidget(self.filter_input, 1)
        
        # 日志级别筛选
        filter_panel.addWidget(QLabel("级别:"))
        
        self.level_combo = QComboBox()
        self.level_combo.addItem("所有级别", "ALL")
        self.level_combo.addItem("调试", "DEBUG")
        self.level_combo.addItem("信息", "INFO")
        self.level_combo.addItem("警告", "WARNING")
        self.level_combo.addItem("错误", "ERROR")
        self.level_combo.addItem("严重", "CRITICAL")
        self.level_combo.currentIndexChanged.connect(self._filter_changed)
        filter_panel.addWidget(self.level_combo)
        
        # 自动刷新和滚动
        self.auto_refresh_check = QCheckBox("自动刷新")
        self.auto_refresh_check.setChecked(True)
        self.auto_refresh_check.toggled.connect(self._toggle_auto_refresh)
        filter_panel.addWidget(self.auto_refresh_check)
        
        self.auto_scroll_check = QCheckBox("自动滚动")
        self.auto_scroll_check.setChecked(True)
        self.auto_scroll_check.toggled.connect(self._toggle_auto_scroll)
        filter_panel.addWidget(self.auto_scroll_check)
        
        control_layout.addLayout(filter_panel)
        
        # 导出和清空按钮
        button_panel = QHBoxLayout()
        
        clear_button = QPushButton("清空过滤器")
        clear_button.clicked.connect(self._clear_filters)
        button_panel.addWidget(clear_button)
        
        button_panel.addStretch(1)
        
        export_button = QPushButton("导出日志")
        export_button.clicked.connect(self._export_logs)
        button_panel.addWidget(export_button)
        
        control_layout.addLayout(button_panel)
        
        # 添加到主布局
        self.main_layout.addWidget(control_group)
    
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
                # 更新UI显示空消息
                self.log_table.setRowCount(0)
                if hasattr(self, 'file_path_label'):
                    self.file_path_label.setText(f"日志文件不存在: {self.log_file_path}")
                return
            
            # 检查日志文件大小
            if os.path.getsize(self.log_file_path) == 0:
                logger.warning(f"日志文件为空: {self.log_file_path}")
                # 清空表格
                self.log_table.setRowCount(0)
                if hasattr(self, 'file_path_label'):
                    self.file_path_label.setText(f"日志文件为空: {self.log_file_path}")
                return
            
            # 清空现有日志条目
            self.log_entries = []
            
            # 读取日志文件
            with open(self.log_file_path, 'r', encoding='utf-8') as file:
                log_text = file.read()
            
            # 解析日志条目
            # 使用正则表达式解析日志格式
            # 支持两种日志格式:
            # 1. [YYYY-MM-DD HH:MM:SS] [LEVEL] [SOURCE:LINE] Message
            # 2. YYYY-MM-DD HH:MM:SS | LEVEL    | SOURCE:FUNCTION:LINE - Message
            
            # 尝试匹配第一种格式
            pattern1 = r'\[(.*?)\]\s*\[(.*?)\]\s*\[(.*?):(.*?)\]\s*(.*?)$'
            matches1 = re.findall(pattern1, log_text, re.MULTILINE)
            
            # 尝试匹配第二种格式
            pattern2 = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s*\|\s*(\w+)\s*\|\s*(.*?):(.*?):(.*?)\s*-\s*(.*?)$'
            matches2 = re.findall(pattern2, log_text, re.MULTILINE)
            
            # 根据匹配结果选择解析方式
            if matches1:
                # 解析第一种格式的日志
                for match in matches1:
                    timestamp, level, source, line, message = match
                    entry = {
                        'timestamp': timestamp.strip(),
                        'level': level.strip(),
                        'source': source.strip(),
                        'line': line.strip(),
                        'message': message.strip()
                    }
                    self.log_entries.append(entry)
            elif matches2:
                # 解析第二种格式的日志
                for match in matches2:
                    timestamp, level, source, function, line, message = match
                    entry = {
                        'timestamp': timestamp.strip(),
                        'level': level.strip(),
                        'source': f"{source.strip()}:{function.strip()}",
                        'line': line.strip(),
                        'message': message.strip()
                    }
                    self.log_entries.append(entry)
            else:
                # 无法匹配已知日志格式
                logger.warning(f"无法解析日志文件格式: {self.log_file_path}")
                # 清空表格
                self.log_table.setRowCount(0)
                if hasattr(self, 'file_path_label'):
                    self.file_path_label.setText(f"无法解析日志文件格式: {self.log_file_path}")
                return
            
            # 根据过滤条件显示日志
            self._apply_filters()
            
            # 如果启用了自动滚动，滚动到最新日志
            if self.auto_scroll and self.log_table.rowCount() > 0:
                self.log_table.scrollToBottom()
            
            # 更新文件路径标签
            if hasattr(self, 'file_path_label'):
                self.file_path_label.setText(f"当前日志文件: {self.log_file_path}")
            
        except Exception as e:
            logger.error(f"加载日志失败: {e}")
            # 清空表格
            self.log_table.setRowCount(0)
            if hasattr(self, 'file_path_label'):
                self.file_path_label.setText(f"加载日志失败: {e}")
    
    def _filter_changed(self):
        """当过滤条件变化时调用"""
        self._apply_filters()
        
    def _toggle_auto_refresh(self, enabled):
        """切换自动刷新功能
        
        Args:
            enabled: 是否启用自动刷新
        """
        if enabled:
            self.refresh_timer.start(2000)  # 每2秒刷新一次
        else:
            self.refresh_timer.stop()
            
    def _clear_filters(self):
        """清空所有过滤条件"""
        self.filter_input.clear()
        self.level_combo.setCurrentIndex(0)  # 设置为"所有级别"
        self._apply_filters()
    
    def _apply_filters(self):
        """根据筛选条件显示日志"""
        try:
            self.log_table.setRowCount(0)  # 清空表格
            
            if not self.log_entries:
                return
            
            # 获取筛选条件
            selected_level = self.level_combo.currentData()
            search_text = self.filter_input.text()
            case_sensitive = False  # 默认不区分大小写
            
            # 筛选日志条目
            filtered_entries = []
            for entry in self.log_entries:
                # 级别筛选
                if selected_level != "ALL" and entry['level'] != selected_level:
                    continue
                
                # 关键字筛选
                if search_text:
                    message = entry['message']
                    if not case_sensitive:
                        message = message.lower()
                        search_text = search_text.lower()
                    
                    if search_text not in message:
                        continue
                
                filtered_entries.append(entry)
            
            # 显示筛选后的日志
            for row, entry in enumerate(filtered_entries):
                self.log_table.insertRow(row)
                
                # 设置单元格项
                timestamp_item = QTableWidgetItem(entry['timestamp'])
                level_item = QTableWidgetItem(entry['level'])
                source_item = QTableWidgetItem(entry['source'])
                line_item = QTableWidgetItem(entry['line'])
                message_item = QTableWidgetItem(entry['message'])
                
                # 设置日志级别颜色
                if entry['level'] in self.LOG_COLORS:
                    level_color = self.LOG_COLORS[entry['level']]
                    level_item.setForeground(QBrush(level_color))
                
                # 添加到表格
                self.log_table.setItem(row, 0, timestamp_item)
                self.log_table.setItem(row, 1, level_item)
                self.log_table.setItem(row, 2, source_item)
                self.log_table.setItem(row, 3, line_item)
                self.log_table.setItem(row, 4, message_item)
            
            # 如果启用了自动滚动，滚动到最新日志
            if self.auto_scroll and self.log_table.rowCount() > 0:
                self.log_table.scrollToBottom()
            
        except Exception as e:
            logger.error(f"应用过滤器失败: {e}")
    
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