"""
TG-Manager 任务管理界面
实现对各类任务的管理功能，包括创建、查看、暂停和恢复任务
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QCheckBox, QPushButton,
    QGroupBox, QScrollArea, QSpinBox, QGridLayout,
    QListWidget, QListWidgetItem, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QProgressBar, QMenu, QTabWidget,
    QAbstractItemView
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QIcon, QAction

from src.utils.logger import get_logger

logger = get_logger()


class TaskView(QWidget):
    """任务管理界面，提供对上传、下载和转发任务的管理功能"""
    
    # 任务操作信号
    task_pause = Signal(str)  # 任务ID
    task_resume = Signal(str)  # 任务ID
    task_cancel = Signal(str)  # 任务ID
    task_remove = Signal(str)  # 任务ID
    
    def __init__(self, config=None, parent=None):
        """初始化任务管理界面
        
        Args:
            config: 配置对象
            parent: 父窗口部件
        """
        super().__init__(parent)
        
        self.config = config or {}
        
        # 设置布局
        self.main_layout = QVBoxLayout(self)
        self.setLayout(self.main_layout)
        
        # 创建任务管理选项卡
        self._create_task_tabs()
        
        # 连接信号
        self._connect_signals()
        
        # 加载配置
        if self.config:
            self.load_config(self.config)
        
        # 任务列表
        self.tasks = {}  # 任务ID -> 任务数据
        
        # 定时刷新
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh_task_stats)
        self.refresh_timer.start(1000)  # 每秒刷新一次
        
        logger.info("任务管理界面初始化完成")
    
    def _create_task_tabs(self):
        """创建任务管理选项卡"""
        self.task_tabs = QTabWidget()
        
        # 创建激活任务标签页
        self.active_tasks_widget = self._create_task_table()
        self.task_tabs.addTab(self.active_tasks_widget, "激活任务")
        
        # 创建已完成任务标签页
        self.completed_tasks_widget = self._create_task_table()
        self.task_tabs.addTab(self.completed_tasks_widget, "已完成任务")
        
        # 创建失败任务标签页
        self.failed_tasks_widget = self._create_task_table()
        self.task_tabs.addTab(self.failed_tasks_widget, "失败任务")
        
        # 添加选项卡到主布局
        self.main_layout.addWidget(self.task_tabs)
        
        # 全局操作按钮
        button_layout = QHBoxLayout()
        
        self.pause_all_button = QPushButton("暂停所有")
        self.resume_all_button = QPushButton("恢复所有")
        self.clear_completed_button = QPushButton("清除已完成")
        self.clear_failed_button = QPushButton("清除失败")
        self.export_tasks_button = QPushButton("导出任务")
        
        button_layout.addWidget(self.pause_all_button)
        button_layout.addWidget(self.resume_all_button)
        button_layout.addWidget(self.clear_completed_button)
        button_layout.addWidget(self.clear_failed_button)
        button_layout.addWidget(self.export_tasks_button)
        
        self.main_layout.addLayout(button_layout)
    
    def _create_task_table(self):
        """创建任务表格控件
        
        Returns:
            QTableWidget: 任务表格控件
        """
        task_table = QTableWidget()
        
        # 设置列
        task_table.setColumnCount(7)
        task_table.setHorizontalHeaderLabels([
            "ID", "类型", "状态", "进度", "目标", "创建时间", "操作"
        ])
        
        # 设置列宽
        task_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        task_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)  # ID列
        task_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)  # 类型列
        task_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)  # 状态列
        task_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)  # 进度列
        task_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)  # 操作列
        
        # 设置选择行为
        task_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        task_table.setSelectionMode(QAbstractItemView.SingleSelection)
        
        # 在表格中添加右键菜单
        task_table.setContextMenuPolicy(Qt.CustomContextMenu)
        task_table.customContextMenuRequested.connect(
            lambda pos, table=task_table: self._show_context_menu(pos, table)
        )
        
        return task_table
    
    def _connect_signals(self):
        """连接信号和槽"""
        # 全局按钮
        self.pause_all_button.clicked.connect(self._pause_all_tasks)
        self.resume_all_button.clicked.connect(self._resume_all_tasks)
        self.clear_completed_button.clicked.connect(self._clear_completed_tasks)
        self.clear_failed_button.clicked.connect(self._clear_failed_tasks)
        self.export_tasks_button.clicked.connect(self._export_tasks)
    
    def _show_context_menu(self, pos, table):
        """显示右键菜单
        
        Args:
            pos: 右键点击位置
            table: 任务表格
        """
        # 获取选中的行
        row = table.rowAt(pos.y())
        if row == -1:
            return
        
        # 获取任务ID和状态
        task_id = table.item(row, 0).text()
        status = table.item(row, 2).text()
        
        # 创建右键菜单
        menu = QMenu(self)
        
        # 根据状态添加菜单项
        if status == "运行中":
            pause_action = QAction("暂停", self)
            pause_action.triggered.connect(lambda: self.task_pause.emit(task_id))
            menu.addAction(pause_action)
        
        elif status == "暂停":
            resume_action = QAction("恢复", self)
            resume_action.triggered.connect(lambda: self.task_resume.emit(task_id))
            menu.addAction(resume_action)
        
        if status != "已完成" and status != "失败":
            cancel_action = QAction("取消", self)
            cancel_action.triggered.connect(lambda: self.task_cancel.emit(task_id))
            menu.addAction(cancel_action)
        
        # 所有状态都有删除选项
        remove_action = QAction("删除", self)
        remove_action.triggered.connect(lambda: self.task_remove.emit(task_id))
        menu.addAction(remove_action)
        
        # 显示任务详情
        details_action = QAction("查看详情", self)
        details_action.triggered.connect(lambda: self._show_task_details(task_id))
        menu.addAction(details_action)
        
        # 显示菜单
        menu.exec_(table.mapToGlobal(pos))
    
    def _show_task_details(self, task_id):
        """显示任务详情
        
        Args:
            task_id: 任务ID
        """
        if task_id in self.tasks:
            task = self.tasks[task_id]
            
            # 格式化任务详情
            details = ""
            details += f"任务ID: {task_id}\n"
            details += f"类型: {task['type']}\n"
            details += f"状态: {task['status']}\n"
            details += f"进度: {task['progress']}%\n"
            details += f"目标: {task['target']}\n"
            details += f"创建时间: {task['create_time']}\n"
            
            if task.get('start_time'):
                details += f"开始时间: {task['start_time']}\n"
            
            if task.get('end_time'):
                details += f"结束时间: {task['end_time']}\n"
            
            if task.get('error'):
                details += f"错误信息: {task['error']}\n"
            
            details += "\n任务配置:\n"
            for key, value in task.get('config', {}).items():
                details += f"{key}: {value}\n"
            
            # 显示消息框
            QMessageBox.information(self, "任务详情", details)
    
    def _pause_all_tasks(self):
        """暂停所有活动任务"""
        # 遍历所有活动任务
        for task_id, task in self.tasks.items():
            if task['status'] == "运行中":
                # 发出暂停信号
                self.task_pause.emit(task_id)
    
    def _resume_all_tasks(self):
        """恢复所有暂停的任务"""
        # 遍历所有暂停任务
        for task_id, task in self.tasks.items():
            if task['status'] == "暂停":
                # 发出恢复信号
                self.task_resume.emit(task_id)
    
    def _clear_completed_tasks(self):
        """清除所有已完成任务"""
        # 询问用户是否确认
        reply = QMessageBox.question(
            self, 
            "清除确认", 
            "确认要清除所有已完成任务吗？",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 找出所有已完成任务
            completed_tasks = []
            for task_id, task in self.tasks.items():
                if task['status'] == "已完成":
                    completed_tasks.append(task_id)
            
            # 发出删除信号
            for task_id in completed_tasks:
                self.task_remove.emit(task_id)
    
    def _clear_failed_tasks(self):
        """清除所有失败任务"""
        # 询问用户是否确认
        reply = QMessageBox.question(
            self, 
            "清除确认", 
            "确认要清除所有失败任务吗？",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 找出所有失败任务
            failed_tasks = []
            for task_id, task in self.tasks.items():
                if task['status'] == "失败":
                    failed_tasks.append(task_id)
            
            # 发出删除信号
            for task_id in failed_tasks:
                self.task_remove.emit(task_id)
    
    def _export_tasks(self):
        """导出任务列表"""
        # TODO: 实现任务导出功能
        QMessageBox.information(self, "提示", "导出功能尚未实现")
    
    def _refresh_task_stats(self):
        """刷新任务统计信息"""
        active_count = sum(1 for task in self.tasks.values() 
                         if task['status'] in ["运行中", "暂停", "等待中"])
        
        completed_count = sum(1 for task in self.tasks.values() 
                            if task['status'] == "已完成")
        
        failed_count = sum(1 for task in self.tasks.values() 
                         if task['status'] == "失败")
        
        # 更新标签页标题
        self.task_tabs.setTabText(0, f"激活任务 ({active_count})")
        self.task_tabs.setTabText(1, f"已完成任务 ({completed_count})")
        self.task_tabs.setTabText(2, f"失败任务 ({failed_count})")
    
    def add_task(self, task_data):
        """添加新任务或更新现有任务
        
        Args:
            task_data: 任务数据字典，必须包含 id, type, status, progress, target, create_time 字段
        """
        task_id = task_data['id']
        
        # 获取旧的任务状态（如果存在）
        old_status = self.tasks.get(task_id, {}).get('status')
        
        # 保存任务数据
        self.tasks[task_id] = task_data
        
        # 根据状态确定应该添加到哪个表格
        if task_data['status'] in ["运行中", "暂停", "等待中"]:
            table = self.active_tasks_widget
            self._remove_task_from_table(task_id, self.completed_tasks_widget)
            self._remove_task_from_table(task_id, self.failed_tasks_widget)
        elif task_data['status'] == "已完成":
            table = self.completed_tasks_widget
            self._remove_task_from_table(task_id, self.active_tasks_widget)
            self._remove_task_from_table(task_id, self.failed_tasks_widget)
        else:  # 失败状态
            table = self.failed_tasks_widget
            self._remove_task_from_table(task_id, self.active_tasks_widget)
            self._remove_task_from_table(task_id, self.completed_tasks_widget)
        
        # 检查任务是否已经在表格中
        row = self._get_task_row(task_id, table)
        
        if row != -1:
            # 更新现有行
            self._update_task_row(row, task_data, table)
        else:
            # 添加新行
            self._add_task_row(task_data, table)
    
    def _get_task_row(self, task_id, table):
        """获取任务在表格中的行索引
        
        Args:
            task_id: 任务ID
            table: 任务表格
            
        Returns:
            int: 行索引，如果任务不在表格中则返回-1
        """
        for row in range(table.rowCount()):
            if table.item(row, 0).text() == task_id:
                return row
        
        return -1
    
    def _add_task_row(self, task_data, table):
        """向表格添加任务行
        
        Args:
            task_data: 任务数据
            table: 任务表格
        """
        row_position = table.rowCount()
        table.insertRow(row_position)
        
        # 设置单元格项
        task_id = task_data['id']
        task_type = task_data['type']
        status = task_data['status']
        target = task_data['target']
        create_time = task_data['create_time']
        
        # ID列
        id_item = QTableWidgetItem(task_id)
        id_item.setFlags(id_item.flags() & ~Qt.ItemIsEditable)  # 设为只读
        table.setItem(row_position, 0, id_item)
        
        # 类型列
        type_item = QTableWidgetItem(task_type)
        type_item.setFlags(type_item.flags() & ~Qt.ItemIsEditable)
        table.setItem(row_position, 1, type_item)
        
        # 状态列
        status_item = QTableWidgetItem(status)
        status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
        table.setItem(row_position, 2, status_item)
        
        # 进度列 - 使用进度条
        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(task_data['progress'])
        progress_bar.setTextVisible(True)
        table.setCellWidget(row_position, 3, progress_bar)
        
        # 目标列
        target_item = QTableWidgetItem(target)
        target_item.setFlags(target_item.flags() & ~Qt.ItemIsEditable)
        table.setItem(row_position, 4, target_item)
        
        # 创建时间列
        time_item = QTableWidgetItem(create_time)
        time_item.setFlags(time_item.flags() & ~Qt.ItemIsEditable)
        table.setItem(row_position, 5, time_item)
        
        # 操作列 - 添加操作按钮
        if status == "运行中":
            action_button = QPushButton("暂停")
            action_button.clicked.connect(lambda: self.task_pause.emit(task_id))
        elif status == "暂停":
            action_button = QPushButton("恢复")
            action_button.clicked.connect(lambda: self.task_resume.emit(task_id))
        elif status in ["已完成", "失败"]:
            action_button = QPushButton("删除")
            action_button.clicked.connect(lambda: self.task_remove.emit(task_id))
        else:
            action_button = QPushButton("取消")
            action_button.clicked.connect(lambda: self.task_cancel.emit(task_id))
        
        table.setCellWidget(row_position, 6, action_button)
    
    def _update_task_row(self, row, task_data, table):
        """更新表格中的任务行
        
        Args:
            row: 行索引
            task_data: 任务数据
            table: 任务表格
        """
        status = task_data['status']
        
        # 更新状态
        status_item = QTableWidgetItem(status)
        status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
        table.setItem(row, 2, status_item)
        
        # 更新进度条
        progress_bar = table.cellWidget(row, 3)
        if isinstance(progress_bar, QProgressBar):
            progress_bar.setValue(task_data['progress'])
        else:
            # 如果不是进度条，创建一个新的
            progress_bar = QProgressBar()
            progress_bar.setRange(0, 100)
            progress_bar.setValue(task_data['progress'])
            progress_bar.setTextVisible(True)
            table.setCellWidget(row, 3, progress_bar)
        
        # 更新操作按钮
        task_id = task_data['id']
        if status == "运行中":
            action_button = QPushButton("暂停")
            action_button.clicked.connect(lambda: self.task_pause.emit(task_id))
        elif status == "暂停":
            action_button = QPushButton("恢复")
            action_button.clicked.connect(lambda: self.task_resume.emit(task_id))
        elif status in ["已完成", "失败"]:
            action_button = QPushButton("删除")
            action_button.clicked.connect(lambda: self.task_remove.emit(task_id))
        else:
            action_button = QPushButton("取消")
            action_button.clicked.connect(lambda: self.task_cancel.emit(task_id))
        
        table.setCellWidget(row, 6, action_button)
    
    def _remove_task_from_table(self, task_id, table):
        """从表格中删除任务
        
        Args:
            task_id: 任务ID
            table: 任务表格
        """
        row = self._get_task_row(task_id, table)
        if row != -1:
            table.removeRow(row)
    
    def remove_task(self, task_id):
        """从所有表格中删除任务
        
        Args:
            task_id: 任务ID
        """
        # 从任务列表中删除
        if task_id in self.tasks:
            del self.tasks[task_id]
        
        # 从各个表格中删除
        self._remove_task_from_table(task_id, self.active_tasks_widget)
        self._remove_task_from_table(task_id, self.completed_tasks_widget)
        self._remove_task_from_table(task_id, self.failed_tasks_widget)
    
    def load_tasks(self, tasks_data):
        """加载任务列表
        
        Args:
            tasks_data: 任务数据列表
        """
        # 清空现有任务
        self.tasks = {}
        self.active_tasks_widget.setRowCount(0)
        self.completed_tasks_widget.setRowCount(0)
        self.failed_tasks_widget.setRowCount(0)
        
        # 添加新任务
        for task_data in tasks_data:
            self.add_task(task_data)
    
    def show_task_error(self, task_id, error_message):
        """显示任务错误信息
        
        Args:
            task_id: 任务ID
            error_message: 错误信息
        """
        QMessageBox.critical(self, f"任务 {task_id} 错误", error_message)
    
    def clear_all_tasks(self):
        """清空所有任务"""
        # 询问用户是否确认
        reply = QMessageBox.question(
            self, 
            "清除确认", 
            "确认要清除所有任务吗？",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 清空任务列表
            self.tasks = {}
            
            # 清空表格
            self.active_tasks_widget.setRowCount(0)
            self.completed_tasks_widget.setRowCount(0)
            self.failed_tasks_widget.setRowCount(0)
    
    def load_config(self, config):
        """从配置字典加载任务设置
        
        Args:
            config: 配置字典
        """
        if not config:
            return
            
        logger.debug("加载任务管理配置")
        
        # 任务相关设置
        if 'Tasks' in config:
            tasks_config = config.get('Tasks', {})
            self.auto_retry_check.setChecked(tasks_config.get('auto_retry', True))
            self.max_retries_input.setValue(tasks_config.get('max_retries', 3))
            self.retry_delay_input.setValue(tasks_config.get('retry_delay', 5))
            
            # 显示模式设置
            show_mode = tasks_config.get('show_mode', 'all')
            index = self.view_mode_combo.findText(show_mode, Qt.MatchFixedString)
            if index >= 0:
                self.view_mode_combo.setCurrentIndex(index) 
    
    def set_task_manager(self, task_manager):
        """设置任务管理器实例
        
        Args:
            task_manager: 任务管理器实例
        """
        if not task_manager:
            logger.warning("任务管理器实例为空，无法设置")
            return
            
        self.task_manager = task_manager
        logger.debug("任务视图已接收任务管理器实例")
        
        # 设置任务监控定时器
        self._setup_task_monitor() 