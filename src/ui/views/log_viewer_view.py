"""
TG-Manager 当日日志查看器
严格只显示当日日志文件，支持筛选、搜索功能，最多显示2000行记录。
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QCheckBox, QComboBox, QPushButton,
    QGroupBox, QTextEdit, QSplitter, QToolBar, QFrame,
    QFileDialog, QMessageBox, QSizePolicy, QTableWidget,
    QTableWidgetItem, QHeaderView, QApplication, QMenu
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
from src.utils.translation_manager import tr, get_translation_manager

logger = get_logger()


class LogViewerView(QWidget):
    """当日日志查看器视图，严格只显示当日日志文件的最新2000行记录，提供过滤和搜索功能"""
    
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
        
        # 存储可翻译的UI组件
        self.translatable_widgets = {}
        
        # 获取翻译管理器并连接语言变化信号
        self.translation_manager = get_translation_manager()
        self.translation_manager.language_changed.connect(self._update_translations)
        
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
        
        logger.info("当日日志查看器视图初始化完成")
    
    def _get_log_file_path(self):
        """获取当前日志文件路径（严格只加载当日日志）
        
        Returns:
            str: 当前日志文件路径
        """
        # 首先从配置中获取
        if isinstance(self.config, dict) and 'LOGGING' in self.config:
            log_config = self.config.get('LOGGING', {})
            log_file = log_config.get('log_file')
            if log_file and os.path.exists(log_file):
                return log_file
        
        # 获取当前日期（支持两种格式）
        today_dash = datetime.datetime.now().strftime('%Y-%m-%d')  # 2025-07-05
        today_simple = datetime.datetime.now().strftime('%Y%m%d')  # 20250705
        
        # 严格按优先级检查当日日志文件（只加载当日日志）
        today_log_paths = [
            f"logs/app_{today_dash}.log",              # 当日UI应用日志（优先）
            f"logs/tg_forwarder_{today_simple}.log",   # 当日转发器日志
        ]
        
        # 检查当日日志文件
        for path in today_log_paths:
            if os.path.exists(path):
                logger.debug(f"使用当日日志文件: {path}")
                return path
        
        # 如果当日日志文件都不存在，返回默认的当日日志文件路径（UI应用日志优先）
        # 不再使用固定名称的后备文件，严格只使用当日日志
        default_path = f"logs/app_{today_dash}.log"
        logger.debug(f"使用默认当日日志文件路径: {default_path}")
        return default_path
    
    def _create_control_panel(self):
        """创建控制面板"""
        # 创建控制面板分组框
        self.control_group = QGroupBox(tr("ui.log_viewer.title"))
        control_layout = QVBoxLayout(self.control_group)
        
        # 文件路径状态标签 - 仅显示当日日志文件路径
        self.file_path_label = QLabel(tr("ui.log_viewer.file_path").format(path=self.log_file_path))
        control_layout.addWidget(self.file_path_label)
        
        # 筛选面板
        filter_panel = QHBoxLayout()
        
        # 关键字筛选
        self.keyword_label = QLabel(tr("ui.log_viewer.keyword_label"))
        filter_panel.addWidget(self.keyword_label)
        
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText(tr("ui.log_viewer.keyword_placeholder"))
        self.filter_input.textChanged.connect(self._filter_changed)
        filter_panel.addWidget(self.filter_input, 1)
        
        # 日志级别筛选
        self.level_label = QLabel(tr("ui.log_viewer.level_label"))
        filter_panel.addWidget(self.level_label)
        
        self.level_combo = QComboBox()
        self.level_combo.addItem(tr("ui.log_viewer.level_all"), "ALL")
        self.level_combo.addItem(tr("ui.log_viewer.level_debug"), "DEBUG")
        self.level_combo.addItem(tr("ui.log_viewer.level_info"), "INFO")
        self.level_combo.addItem(tr("ui.log_viewer.level_warning"), "WARNING")
        self.level_combo.addItem(tr("ui.log_viewer.level_error"), "ERROR")
        self.level_combo.addItem(tr("ui.log_viewer.level_critical"), "CRITICAL")
        # 设置默认显示INFO级别（索引2，即"信息"级别）
        self.level_combo.setCurrentIndex(2)
        self.level_combo.currentIndexChanged.connect(self._filter_changed)
        filter_panel.addWidget(self.level_combo)
        
        control_layout.addLayout(filter_panel)
        
        # 清空按钮
        button_panel = QHBoxLayout()
        
        self.clear_button = QPushButton(tr("ui.log_viewer.clear_filters"))
        self.clear_button.clicked.connect(self._clear_filters)
        # 添加测试连接，确保按钮正常工作
        self.clear_button.clicked.connect(lambda: logger.debug("清空过滤器按钮点击事件已触发"))
        button_panel.addWidget(self.clear_button)
        
        # 添加自动刷新控制
        self.auto_refresh_checkbox = QCheckBox(tr("ui.log_viewer.auto_refresh"))
        self.auto_refresh_checkbox.setChecked(True)  # 默认启用
        self.auto_refresh_checkbox.toggled.connect(self._on_auto_refresh_toggled)
        button_panel.addWidget(self.auto_refresh_checkbox)
        
        # 添加空白占位符
        button_panel.addStretch(1)
        
        control_layout.addLayout(button_panel)
        
        # 添加到主布局
        self.main_layout.addWidget(self.control_group)
    
    def _create_log_display(self):
        """创建日志显示区域"""
        # 创建日志表格
        self.log_table = QTableWidget()
        # 减少列数从5到3，移除"来源"和"行号"列
        self.log_table.setColumnCount(3)
        self.log_table.setHorizontalHeaderLabels([
            tr("ui.log_viewer.table_headers.time"),
            tr("ui.log_viewer.table_headers.level"),
            tr("ui.log_viewer.table_headers.message")
        ])
        
        # 设置表格列宽
        header = self.log_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 时间
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # 级别
        header.setSectionResizeMode(2, QHeaderView.Stretch)           # 消息
        
        # 启用右键菜单
        self.log_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.log_table.customContextMenuRequested.connect(self._show_context_menu)
        
        # 添加到主布局
        self.main_layout.addWidget(self.log_table, 1)  # 1为拉伸系数
    
    async def _async_load_logs(self):
        """异步加载日志文件内容（限制最多2000行）"""
        try:
            if self.is_loading:
                logger.debug("日志已在加载中，跳过此次加载")
                return
                
            self.is_loading = True
            # 在首次加载时显示加载消息
            if not hasattr(self, '_initial_load_done'):
                self.status_update_signal.emit(tr("ui.log_viewer.status.loading"))
            
            # 检查日志文件是否存在
            if not os.path.exists(self.log_file_path):
                logger.warning(f"当日日志文件不存在: {self.log_file_path}")
                self.status_update_signal.emit(tr("ui.log_viewer.status.file_not_found").format(path=self.log_file_path))
                self.logs_loaded_signal.emit([])
                self.is_loading = False
                return
            
            # 检查日志文件大小
            if os.path.getsize(self.log_file_path) == 0:
                logger.warning(f"当日日志文件为空: {self.log_file_path}")
                self.status_update_signal.emit(tr("ui.log_viewer.status.file_empty").format(path=self.log_file_path))
                self.logs_loaded_signal.emit([])
                self.is_loading = False
                return
            
            # 在事件循环中运行IO操作
            loop = get_event_loop()
            
            # 读取文件的最后2000行
            def read_last_lines(file_path, max_lines=2000):
                """读取文件的最后N行"""
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        # 只保留最后2000行
                        if len(lines) > max_lines:
                            lines = lines[-max_lines:]
                        return ''.join(lines)
                except Exception as e:
                    logger.error(f"读取日志文件失败: {e}")
                    return ""
            
            # 使用协程执行文件读取操作
            log_text = await loop.run_in_executor(
                None, 
                read_last_lines,
                self.log_file_path,
                2000
            )
            
            # 解析日志条目
            log_entries = []
            
            # 在异步任务中解析日志
            # 使用正则表达式解析日志格式
            # 支持多种日志格式:
            # 1. [YYYY-MM-DD HH:MM:SS] [LEVEL] [SOURCE:LINE] Message
            # 2. YYYY-MM-DD HH:MM:SS | LEVEL    | SOURCE:FUNCTION:LINE - Message (当前使用的格式)
            # 3. 其他可能的格式变体
            
            # 尝试匹配第一种格式 (旧格式)
            pattern1 = r'\[(.*?)\]\s*\[(.*?)\]\s*\[(.*?):(.*?)\]\s*(.*?)$'
            matches1 = re.findall(pattern1, log_text, re.MULTILINE)
            
            # 尝试匹配第二种格式 (当前格式) - 修复正则表达式
            # 格式：2025-06-11 09:43:29.363 | INFO     | __main__:main:106 - 启动 TG-Manager 图形界面
            pattern2 = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d{3})?)\s*\|\s*(\w+)\s*\|\s*([^:]+):([^:]+):(\d+)\s*-\s*(.*)'
            matches2 = re.findall(pattern2, log_text, re.MULTILINE)
            
            # 尝试匹配简化格式（如果其他格式都失败）
            # 格式：YYYY-MM-DD HH:MM:SS.mmm | LEVEL | ... - Message
            pattern3 = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d{3})?)\s*\|\s*(\w+)\s*\|\s*.*?\s*-\s*(.*)'
            matches3 = re.findall(pattern3, log_text, re.MULTILINE)
            
            # 根据匹配结果选择解析方式
            if matches1:
                # 解析第一种格式的日志 (旧格式)
                # 移除调试日志，避免循环显示
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
                # 解析第二种格式的日志 (当前格式)
                # 移除调试日志，避免循环显示
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
            elif matches3:
                # 解析简化格式的日志 (后备格式)
                # 移除调试日志，避免循环显示
                for match in matches3:
                    timestamp, level, message = match
                    entry = {
                        'timestamp': timestamp.strip(),
                        'level': level.strip(),
                        'source': 'unknown',
                        'line': '0',
                        'message': message.strip()
                    }
                    log_entries.append(entry)
            else:
                # 如果所有正则表达式都不匹配，尝试按行解析
                # 只在解析失败时记录一次警告，避免重复日志
                if not hasattr(self, '_parse_warning_logged'):
                    logger.warning("日志格式无法识别，尝试按行解析")
                    self._parse_warning_logged = True
                    
                lines = log_text.split('\n')
                for line_num, line in enumerate(lines):
                    line = line.strip()
                    if line:  # 跳过空行
                        # 简单的时间戳检测 - 支持毫秒格式
                        if re.match(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d{3})?', line):
                            # 尝试提取基本信息
                            parts = line.split('|', 2)
                            if len(parts) >= 3:
                                timestamp = parts[0].strip()
                                level = parts[1].strip()
                                message = parts[2].strip()
                                # 如果消息以 " - " 开头，去掉这个前缀
                                if message.startswith(' - '):
                                    message = message[3:]
                                entry = {
                                    'timestamp': timestamp,
                                    'level': level,
                                    'source': 'unknown',
                                    'line': str(line_num + 1),
                                    'message': message
                                }
                                log_entries.append(entry)
                            else:
                                # 完全无法解析的行，当作普通消息
                                entry = {
                                    'timestamp': 'unknown',
                                    'level': 'INFO',
                                    'source': 'unknown',
                                    'line': str(line_num + 1),
                                    'message': line
                                }
                                log_entries.append(entry)
            
            # 确保日志条目数量不超过2000条
            if len(log_entries) > 2000:
                log_entries = log_entries[-2000:]
            
            # 发送解析完成的信号
            self.logs_loaded_signal.emit(log_entries)
            
        except Exception as e:
            logger.error(f"异步加载日志失败: {e}")
            self.status_update_signal.emit(tr("ui.log_viewer.status.load_failed").format(error=str(e)))
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
            self.file_path_label.setText(tr("ui.log_viewer.file_path").format(path=self.log_file_path))
        
        # 根据过滤条件显示日志
        self._apply_filters()
        
        # 更新加载状态消息
        # 仅在首次加载时显示状态信息，且只在状态栏显示，不记录到日志
        if not hasattr(self, '_initial_load_done'):
            self._initial_load_done = True
            if log_entries:
                # 只在状态栏显示，不写入日志文件
                total_entries = len(log_entries)
                if total_entries >= 2000:
                    self.status_update_signal.emit(tr("ui.log_viewer.status.loaded_count").format(count=total_entries))
                else:
                    self.status_update_signal.emit(tr("ui.log_viewer.status.loaded_count_simple").format(count=total_entries))
            else:
                # 只在状态栏显示，不写入日志文件
                self.status_update_signal.emit(tr("ui.log_viewer.status.no_records"))
    
    @Slot(str)
    def _on_status_update(self, message):
        """状态更新槽函数
        
        Args:
            message: 状态消息
        """
        self._update_status_message(message)
    
    def _filter_changed(self):
        """当过滤条件变化时调用"""
        # 检查事件循环是否可用，如果不可用则使用同步版本
        try:
            loop = get_event_loop()
            if loop and loop.is_running():
                # 使用异步处理筛选，避免大量日志时UI卡顿
                create_task(self._async_apply_filters())
            else:
                # 事件循环不可用，使用同步版本
                self._apply_filters()
        except Exception as e:
            logger.warning(f"异步筛选失败，使用同步版本: {e}")
            self._apply_filters()
    
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
                # 过滤掉日志查看器自身的内部日志，避免循环显示
                if (entry.get('source', '').startswith('src.ui.views.log_viewer_view') and 
                    any(keyword in entry.get('message', '') for keyword in [
                        '解析日志', '匹配到', '条记录', '按行解析', '加载了', '日志记录'
                    ])):
                    continue
                
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
        logger.debug("清空过滤器按钮被点击")
        
        # 清空关键字输入框
        self.filter_input.clear()
        logger.debug("已清空关键字输入框")
        
        # 清空过滤器时设置为INFO级别，而不是所有级别
        self.level_combo.setCurrentIndex(2)  # 设置为"信息"级别
        logger.debug("已设置级别为INFO")
        
        # 重新应用筛选条件 - 使用同步版本避免事件循环问题
        self._apply_filters()
        logger.debug("已触发筛选应用")
    
    def _test_clear_button(self):
        """测试清空按钮功能"""
        logger.debug("测试清空按钮功能")
        self._clear_filters()
    
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
    
    def _update_translations(self):
        """更新所有UI文本的翻译"""
        # 更新控制面板
        if hasattr(self, 'control_group'):
            self.control_group.setTitle(tr("ui.log_viewer.title"))
        
        # 更新文件路径标签
        if hasattr(self, 'file_path_label'):
            self.file_path_label.setText(tr("ui.log_viewer.file_path").format(path=self.log_file_path))
        
        # 更新关键字标签
        if hasattr(self, 'keyword_label'):
            self.keyword_label.setText(tr("ui.log_viewer.keyword_label"))
        
        # 更新关键字输入框占位符
        if hasattr(self, 'filter_input'):
            self.filter_input.setPlaceholderText(tr("ui.log_viewer.keyword_placeholder"))
        
        # 更新级别标签
        if hasattr(self, 'level_label'):
            self.level_label.setText(tr("ui.log_viewer.level_label"))
        
        # 更新级别下拉框
        if hasattr(self, 'level_combo'):
            # 保存当前选中的索引
            current_index = self.level_combo.currentIndex()
            
            # 临时断开信号连接，避免在更新过程中触发筛选
            try:
                self.level_combo.currentIndexChanged.disconnect()
            except TypeError:
                # 信号可能已经断开，忽略错误
                pass
            
            # 清空并重新添加翻译后的项目
            self.level_combo.clear()
            self.level_combo.addItem(tr("ui.log_viewer.level_all"), "ALL")
            self.level_combo.addItem(tr("ui.log_viewer.level_debug"), "DEBUG")
            self.level_combo.addItem(tr("ui.log_viewer.level_info"), "INFO")
            self.level_combo.addItem(tr("ui.log_viewer.level_warning"), "WARNING")
            self.level_combo.addItem(tr("ui.log_viewer.level_error"), "ERROR")
            self.level_combo.addItem(tr("ui.log_viewer.level_critical"), "CRITICAL")
            
            # 恢复选中的索引（如果有效）
            if 0 <= current_index < self.level_combo.count():
                self.level_combo.setCurrentIndex(current_index)
            else:
                # 默认设置为INFO级别
                self.level_combo.setCurrentIndex(2)
            
            # 重新连接信号
            self.level_combo.currentIndexChanged.connect(self._filter_changed)
        
        # 更新清空过滤器按钮
        if hasattr(self, 'clear_button'):
            self.clear_button.setText(tr("ui.log_viewer.clear_filters"))
        
        # 更新自动刷新控制
        if hasattr(self, 'auto_refresh_checkbox'):
            self.auto_refresh_checkbox.setText(tr("ui.log_viewer.auto_refresh"))
        
        # 更新表格头部
        if hasattr(self, 'log_table'):
            self.log_table.setHorizontalHeaderLabels([
                tr("ui.log_viewer.table_headers.time"),
                tr("ui.log_viewer.table_headers.level"),
                tr("ui.log_viewer.table_headers.message")
            ])
    
    def _on_auto_refresh_toggled(self, checked):
        """当自动刷新控制选项变化时调用"""
        if checked:
            # 启用自动刷新
            if hasattr(self, 'refresh_timer'):
                self.refresh_timer.start()
                logger.debug("自动刷新已启用")
        else:
            # 禁用自动刷新
            if hasattr(self, 'refresh_timer'):
                self.refresh_timer.stop()
                logger.debug("自动刷新已禁用")

    def _show_context_menu(self, position):
        """显示右键菜单"""
        menu = QMenu()
        
        # 获取点击位置的行
        index = self.log_table.indexAt(position)
        if index.isValid():
            # 如果点击在有效行上，添加复制单行选项
            copy_row_action = menu.addAction(tr("ui.log_viewer.context_menu.copy"))
            copy_row_action.triggered.connect(lambda: self._copy_row(index.row()))
            menu.addSeparator()
        
        # 添加复制所有日志选项
        copy_all_action = menu.addAction(tr("ui.log_viewer.context_menu.copy_all"))
        copy_all_action.triggered.connect(self._copy_all_logs)
        
        # 显示菜单
        menu.exec(self.log_table.viewport().mapToGlobal(position))
    
    def _copy_row(self, row):
        """复制指定行的日志
        
        Args:
            row: 行索引
        """
        try:
            # 获取该行的所有列数据
            time_item = self.log_table.item(row, 0)
            level_item = self.log_table.item(row, 1)
            message_item = self.log_table.item(row, 2)
            
            if time_item and level_item and message_item:
                # 格式化为标准日志格式
                log_text = f"{time_item.text()} | {level_item.text()} | {message_item.text()}"
                
                # 复制到剪贴板
                clipboard = QApplication.clipboard()
                clipboard.setText(log_text)
                
                # 显示成功消息
                self.status_update_signal.emit(tr("ui.log_viewer.status.copied"))
                logger.debug(f"已复制日志行 {row}: {log_text}")
            else:
                self.status_update_signal.emit(tr("ui.log_viewer.status.copy_failed"))
        except Exception as e:
            logger.error(f"复制日志行失败: {e}")
            self.status_update_signal.emit(tr("ui.log_viewer.status.copy_failed"))
    
    def _copy_all_logs(self):
        """复制所有显示的日志"""
        try:
            if self.log_table.rowCount() == 0:
                self.status_update_signal.emit(tr("ui.log_viewer.status.copy_failed"))
                return
            
            # 复制所有行
            log_texts = []
            for row in range(self.log_table.rowCount()):
                time_item = self.log_table.item(row, 0)
                level_item = self.log_table.item(row, 1)
                message_item = self.log_table.item(row, 2)
                
                if time_item and level_item and message_item:
                    log_text = f"{time_item.text()} | {level_item.text()} | {message_item.text()}"
                    log_texts.append(log_text)
            
            if log_texts:
                # 复制到剪贴板
                clipboard = QApplication.clipboard()
                clipboard.setText("\n".join(log_texts))
                
                # 显示成功消息
                self.status_update_signal.emit(tr("ui.log_viewer.status.copied"))
                logger.debug(f"已复制所有 {len(log_texts)} 行日志")
            else:
                self.status_update_signal.emit(tr("ui.log_viewer.status.copy_failed"))
        except Exception as e:
            logger.error(f"复制所有日志失败: {e}")
            self.status_update_signal.emit(tr("ui.log_viewer.status.copy_failed")) 