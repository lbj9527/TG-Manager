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
import asyncio
import datetime
from pathlib import Path

from src.utils.logger import get_logger
from src.utils.async_utils import (
    create_task, qt_connect_async, AsyncTimer, as_task,
    get_event_loop
)

logger = get_logger()


class LogViewerView(QWidget):
    """日志查看器视图，提供日志显示、过滤和搜索功能"""
    
    # 定义信号
    logs_loaded_signal = Signal(list)  # 日志加载完成信号
    status_update_signal = Signal(str)  # 状态更新信号
    
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
        self.auto_scroll = True  # 始终启用自动滚动
        self.log_entries = []
        self.parent_window = parent
        self.is_loading = False  # 添加加载状态标志
        
        # 连接信号
        self.logs_loaded_signal.connect(self._on_logs_loaded)
        self.status_update_signal.connect(self._on_status_update)
        
        # 设置布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self.setLayout(self.main_layout)
        
        # 创建控制面板
        self._create_control_panel()
        
        # 创建日志显示区域
        self._create_log_display()
        
        # 初始加载日志（异步）
        create_task(self._async_load_logs())
        
        # 设置自动刷新（使用AsyncTimer替代QTimer）- 始终自动刷新
        self.refresh_timer = AsyncTimer(2.0, self._async_refresh_logs)
        self.refresh_timer.start()
        
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
        
        # 文件路径状态标签 - 仅显示当前日志文件路径，移除文件选择相关控件
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
        # 设置默认显示INFO级别（索引2）
        self.level_combo.setCurrentIndex(2)
        self.level_combo.currentIndexChanged.connect(self._filter_changed)
        filter_panel.addWidget(self.level_combo)
        
        control_layout.addLayout(filter_panel)
        
        # 清空按钮
        button_panel = QHBoxLayout()
        
        clear_button = QPushButton("清空过滤器")
        clear_button.clicked.connect(self._clear_filters)
        button_panel.addWidget(clear_button)
        
        # 添加空白占位符
        button_panel.addStretch(1)
        
        control_layout.addLayout(button_panel)
        
        # 添加到主布局
        self.main_layout.addWidget(control_group)
    
    def _create_log_display(self):
        """创建日志显示区域"""
        # 创建日志表格
        self.log_table = QTableWidget()
        # 减少列数从5到3，移除"来源"和"行号"列
        self.log_table.setColumnCount(3)
        self.log_table.setHorizontalHeaderLabels(["时间", "级别", "消息"])
        
        # 设置表格列宽
        header = self.log_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 时间
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # 级别
        header.setSectionResizeMode(2, QHeaderView.Stretch)           # 消息
        
        # 添加到主布局
        self.main_layout.addWidget(self.log_table, 1)  # 1为拉伸系数
    
    async def _async_load_logs(self):
        """异步加载日志文件内容"""
        try:
            if self.is_loading:
                logger.debug("日志已在加载中，跳过此次加载")
                return
                
            self.is_loading = True
            # 在首次加载时显示加载消息
            if not hasattr(self, '_initial_load_done'):
                self.status_update_signal.emit("正在加载日志...")
            
            # 检查日志文件是否存在
            if not os.path.exists(self.log_file_path):
                logger.warning(f"日志文件不存在: {self.log_file_path}")
                self.status_update_signal.emit(f"日志文件不存在: {self.log_file_path}")
                self.logs_loaded_signal.emit([])
                self.is_loading = False
                return
            
            # 检查日志文件大小
            if os.path.getsize(self.log_file_path) == 0:
                logger.warning(f"日志文件为空: {self.log_file_path}")
                self.status_update_signal.emit(f"日志文件为空: {self.log_file_path}")
                self.logs_loaded_signal.emit([])
                self.is_loading = False
                return
            
            # 在事件循环中运行IO操作
            loop = get_event_loop()
            
            # 使用协程执行文件读取操作
            log_text = await loop.run_in_executor(
                None, 
                lambda: open(self.log_file_path, 'r', encoding='utf-8').read()
            )
            
            # 解析日志条目
            log_entries = []
            
            # 在异步任务中解析日志
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
                    log_entries.append(entry)
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
                    log_entries.append(entry)
            
            # 发送解析完成的信号
            self.logs_loaded_signal.emit(log_entries)
            
        except Exception as e:
            logger.error(f"异步加载日志失败: {e}")
            self.status_update_signal.emit(f"加载日志失败: {e}")
            self.logs_loaded_signal.emit([])
        finally:
            self.is_loading = False
    
    @Slot(list)
    def _on_logs_loaded(self, log_entries):
        """日志加载完成的槽函数
        
        Args:
            log_entries: 解析后的日志条目
        """
        self.log_entries = log_entries
        # 更新文件路径标签
        if hasattr(self, 'file_path_label'):
            self.file_path_label.setText(f"当前日志文件: {self.log_file_path}")
        
        # 根据过滤条件显示日志
        self._apply_filters()
        
        # 更新加载状态消息
        # 仅在首次加载时显示状态信息
        if not hasattr(self, '_initial_load_done'):
            self._initial_load_done = True
            if log_entries:
                self.status_update_signal.emit(f"加载了 {len(log_entries)} 条日志记录")
            else:
                self.status_update_signal.emit("未找到日志记录")
    
    @Slot(str)
    def _on_status_update(self, message):
        """状态更新槽函数
        
        Args:
            message: 状态消息
        """
        self._update_status_message(message)
    
    def _filter_changed(self):
        """当过滤条件变化时调用"""
        # 使用异步处理筛选，避免大量日志时UI卡顿
        create_task(self._async_apply_filters())
        
    async def _async_apply_filters(self):
        """异步应用筛选条件"""
        # 获取筛选条件
        selected_level = self.level_combo.currentData()
        search_text = self.filter_input.text()
        case_sensitive = False  # 默认不区分大小写
        
        # 异步筛选日志条目
        loop = get_event_loop()
        
        def filter_entries():
            filtered = []
            for entry in self.log_entries:
                # 级别筛选
                if selected_level != "ALL" and entry['level'] != selected_level:
                    continue
                
                # 关键字筛选
                if search_text:
                    message = entry['message']
                    if not case_sensitive:
                        message = message.lower()
                        search = search_text.lower()
                    else:
                        search = search_text
                    
                    if search not in message:
                        continue
                
                filtered.append(entry)
            return filtered
        
        # 在事件循环的执行器中运行筛选操作
        filtered_entries = await loop.run_in_executor(None, filter_entries)
        
        # 在主线程中更新UI
        self._update_table_with_filtered_entries(filtered_entries)
        
    def _update_table_with_filtered_entries(self, filtered_entries):
        """用筛选后的条目更新表格
        
        Args:
            filtered_entries: 筛选后的日志条目
        """
        self.log_table.setRowCount(0)  # 清空表格
        
        # 显示筛选后的日志
        for row, entry in enumerate(filtered_entries):
            self.log_table.insertRow(row)
            
            # 设置单元格项
            timestamp_item = QTableWidgetItem(entry['timestamp'])
            level_item = QTableWidgetItem(entry['level'])
            # 直接使用消息，不再显示来源和行号
            message_item = QTableWidgetItem(entry['message'])
            
            # 设置日志级别颜色
            if entry['level'] in self.LOG_COLORS:
                level_color = self.LOG_COLORS[entry['level']]
                level_item.setForeground(QBrush(level_color))
            
            # 添加到表格 - 仅添加3列，不再包括来源和行号
            self.log_table.setItem(row, 0, timestamp_item)
            self.log_table.setItem(row, 1, level_item)
            self.log_table.setItem(row, 2, message_item)
        
        # 如果启用了自动滚动，滚动到最新日志
        if self.auto_scroll and self.log_table.rowCount() > 0:
            self.log_table.scrollToBottom()
        
    def _clear_filters(self):
        """清空所有过滤条件"""
        self.filter_input.clear()
        # 清空过滤器时设置为INFO级别，而不是所有级别
        self.level_combo.setCurrentIndex(2)  # 设置为"信息"级别
        create_task(self._async_apply_filters())
    
    def _apply_filters(self):
        """同步应用筛选条件（保留向后兼容性）"""
        create_task(self._async_apply_filters())
    
    async def _async_refresh_logs(self):
        """异步刷新日志"""
        if self.is_loading:
            return
            
        # 异步重新加载日志
        await self._async_load_logs()
        
        # 自动滚动到底部（已在_update_table_with_filtered_entries中处理）
    
    def _refresh_logs(self):
        """同步版本的刷新日志（保留向后兼容性）"""
        create_task(self._async_refresh_logs())
    
    def closeEvent(self, event):
        """关闭事件处理
        
        Args:
            event: 关闭事件
        """
        # 停止刷新定时器
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