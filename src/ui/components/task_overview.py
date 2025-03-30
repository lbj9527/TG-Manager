"""
TG-Manager 任务概览组件
显示当前活动任务的概览信息
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGridLayout, 
    QProgressBar, QPushButton, QScrollArea
)
from PySide6.QtCore import Qt, Signal

from src.utils.logger import get_logger

logger = get_logger()


class TaskOverview(QWidget):
    """任务概览组件，显示当前活动任务摘要"""
    
    # 查看所有任务按钮点击信号
    view_all_tasks_clicked = Signal()
    # 任务项点击信号
    task_selected = Signal(str)  # task_id
    
    def __init__(self, parent=None):
        """初始化任务概览组件
        
        Args:
            parent: 父窗口部件
        """
        super().__init__(parent)
        
        # 创建布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        
        # 创建概览标签
        self.summary_label = QLabel("当前任务概览")
        self.summary_label.setAlignment(Qt.AlignCenter)
        self.summary_label.setStyleSheet("font-weight: bold;")
        
        # 创建计数器标签
        self.counters_layout = QGridLayout()
        
        self.active_label = QLabel("活跃任务:")
        self.active_count = QLabel("0")
        self.counters_layout.addWidget(self.active_label, 0, 0)
        self.counters_layout.addWidget(self.active_count, 0, 1)
        
        self.completed_label = QLabel("已完成:")
        self.completed_count = QLabel("0")
        self.counters_layout.addWidget(self.completed_label, 1, 0)
        self.counters_layout.addWidget(self.completed_count, 1, 1)
        
        self.waiting_label = QLabel("等待中:")
        self.waiting_count = QLabel("0")
        self.counters_layout.addWidget(self.waiting_label, 2, 0)
        self.counters_layout.addWidget(self.waiting_count, 2, 1)
        
        self.failed_label = QLabel("失败:")
        self.failed_count = QLabel("0")
        self.counters_layout.addWidget(self.failed_label, 3, 0)
        self.counters_layout.addWidget(self.failed_count, 3, 1)
        
        # 创建任务列表滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.tasks_widget = QWidget()
        self.tasks_layout = QVBoxLayout(self.tasks_widget)
        self.tasks_layout.setAlignment(Qt.AlignTop)
        self.tasks_layout.setSpacing(5)
        
        self.scroll_area.setWidget(self.tasks_widget)
        
        # 创建查看所有任务按钮
        self.view_all_button = QPushButton("查看所有任务")
        self.view_all_button.clicked.connect(self._on_view_all_clicked)
        
        # 添加组件到主布局
        self.main_layout.addWidget(self.summary_label)
        self.main_layout.addLayout(self.counters_layout)
        self.main_layout.addWidget(QLabel("活跃任务列表:"))
        self.main_layout.addWidget(self.scroll_area)
        self.main_layout.addWidget(self.view_all_button)
        
        # 当前活跃任务ID到任务项小部件的映射
        self.task_widgets = {}
    
    def _on_view_all_clicked(self):
        """查看所有任务按钮点击处理"""
        self.view_all_tasks_clicked.emit()
    
    def update_counters(self, active, completed, waiting, failed):
        """更新任务计数
        
        Args:
            active: 活跃任务数
            completed: 已完成任务数
            waiting: 等待中任务数
            failed: 失败任务数
        """
        self.active_count.setText(str(active))
        self.completed_count.setText(str(completed))
        self.waiting_count.setText(str(waiting))
        self.failed_count.setText(str(failed))
    
    def add_task(self, task_id, task_type, task_name, status, progress=0):
        """添加任务到概览
        
        Args:
            task_id: 任务ID
            task_type: 任务类型
            task_name: 任务名称
            status: 任务状态
            progress: 任务进度 (0-100)
        """
        # 如果任务已存在，则更新
        if task_id in self.task_widgets:
            self.update_task(task_id, status, progress)
            return
        
        # 创建任务项小部件
        task_widget = QWidget()
        task_layout = QVBoxLayout(task_widget)
        task_layout.setContentsMargins(3, 3, 3, 3)
        
        # 任务信息标签
        info_label = QLabel(f"{task_type}: {task_name}")
        info_label.setToolTip(f"任务ID: {task_id}\n类型: {task_type}\n名称: {task_name}")
        
        # 状态进度条
        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(progress)
        progress_bar.setFormat(f"{status} %p%")
        progress_bar.setTextVisible(True)
        
        # 将组件添加到布局
        task_layout.addWidget(info_label)
        task_layout.addWidget(progress_bar)
        
        # 存储小部件引用
        self.task_widgets[task_id] = {
            'widget': task_widget,
            'info_label': info_label,
            'progress_bar': progress_bar
        }
        
        # 添加到任务列表
        self.tasks_layout.addWidget(task_widget)
        
        # 设置点击处理
        task_widget.mousePressEvent = lambda event, tid=task_id: self.task_selected.emit(tid)
    
    def update_task(self, task_id, status, progress):
        """更新任务状态和进度
        
        Args:
            task_id: 任务ID
            status: 新状态
            progress: 新进度 (0-100)
        """
        if task_id in self.task_widgets:
            task = self.task_widgets[task_id]
            task['progress_bar'].setValue(progress)
            task['progress_bar'].setFormat(f"{status} %p%")
    
    def remove_task(self, task_id):
        """从概览中移除任务
        
        Args:
            task_id: 要移除的任务ID
        """
        if task_id in self.task_widgets:
            # 从布局中移除小部件
            self.tasks_layout.removeWidget(self.task_widgets[task_id]['widget'])
            # 删除小部件
            self.task_widgets[task_id]['widget'].deleteLater()
            # 从字典中移除
            del self.task_widgets[task_id]
    
    def clear_tasks(self):
        """清除所有任务"""
        # 移除所有任务小部件
        for task_id in list(self.task_widgets.keys()):
            self.remove_task(task_id) 