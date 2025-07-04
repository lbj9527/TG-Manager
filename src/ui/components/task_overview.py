"""
TG-Manager 任务概览组件
显示当前活动任务的概览信息
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGridLayout, 
    QProgressBar, QPushButton, QScrollArea, QHBoxLayout,
    QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from src.utils.logger import get_logger
from src.utils.translation_manager import get_translation_manager, tr

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
        
        # 获取翻译管理器
        self.translation_manager = get_translation_manager()
        self.translation_manager.language_changed.connect(self._update_translations)
        
        # 设置尺寸策略，允许组件在较小空间中工作
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # 创建布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(3, 3, 3, 3)  # 减小边距
        self.main_layout.setSpacing(4)  # 减小间距
        
        # 创建标题和任务列表部分
        self._create_header()
        self._create_task_list()
        self._create_view_all_button()
        
        # 当前活跃任务ID到任务项小部件的映射
        self.task_widgets = {}
    
    def _create_header(self):
        """创建标题部分"""
        # 创建标题标签，使用较大字体并居中
        self.summary_label = QLabel(tr("ui.tasks.title"))
        self.summary_label.setAlignment(Qt.AlignCenter)
        
        # 设置字体和样式
        font = QFont()
        font.setBold(True)
        font.setPointSize(9)  # 减小字体大小
        self.summary_label.setFont(font)
        self.summary_label.setStyleSheet("color: #2196F3; margin-bottom: 2px;")
        
        # 添加标题下的分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("background-color: #E0E0E0;")
        
        # 添加到主布局
        self.main_layout.addWidget(self.summary_label)
        self.main_layout.addWidget(separator)
    
    def _create_task_list(self):
        """创建任务列表部分"""
        # 创建任务列表滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        #1px solid #E0E0E0
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                border-radius: 4px;
                background-color: #F5F5F5;
            }
        """)
        
        # 创建任务列表容器
        self.tasks_widget = QWidget()
        self.tasks_layout = QVBoxLayout(self.tasks_widget)
        self.tasks_layout.setAlignment(Qt.AlignTop)
        self.tasks_layout.setSpacing(8)
        self.tasks_layout.setContentsMargins(5, 5, 5, 5)
        
        self.scroll_area.setWidget(self.tasks_widget)
        
        # 添加到主布局，并设置为可伸展
        self.main_layout.addWidget(self.scroll_area, 1)  # 添加伸展因子
    
    def _create_view_all_button(self):
        """创建查看所有任务按钮"""
        self.view_all_button = QPushButton(tr("ui.tasks.active_tasks"))
        self.view_all_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 4px;
                font-weight: bold;
                font-size: 8pt;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #0D47A1;
            }
        """)
        self.view_all_button.clicked.connect(self._on_view_all_clicked)
        self.view_all_button.setMaximumHeight(25)  # 减小按钮高度
        
        # 添加到主布局
        self.main_layout.addWidget(self.view_all_button)
    
    def _on_view_all_clicked(self):
        """查看所有任务按钮点击处理"""
        self.view_all_tasks_clicked.emit()
    
    def update_counters(self, active, completed, waiting, failed):
        """更新任务计数 - 保留方法便于兼容，但功能已经迁移到状态栏
        
        Args:
            active: 活跃任务数
            completed: 已完成任务数
            waiting: 等待中任务数
            failed: 失败任务数
        """
        # 该功能已移至状态栏，此处保留方法便于兼容
        pass
    
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
        task_widget.setStyleSheet("""
            QWidget {
                background-color: white;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
            }
            QWidget:hover {
                background-color: #F5F5F5;
                border: 1px solid #BDBDBD;
            }
        """)
        
        task_layout = QVBoxLayout(task_widget)
        task_layout.setContentsMargins(8, 8, 8, 8)
        task_layout.setSpacing(6)
        
        # 任务信息标签
        header_layout = QHBoxLayout()
        type_label = QLabel(task_type)
        type_label.setStyleSheet(f"font-weight: bold; color: #2196F3; background: transparent;")
        
        name_label = QLabel(task_name)
        name_label.setStyleSheet("color: #424242; background: transparent;")
        
        header_layout.addWidget(type_label)
        header_layout.addWidget(QLabel(":"))
        header_layout.addWidget(name_label, 1)  # 让名称标签占据剩余空间
        
        # 状态进度条
        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(progress)
        progress_bar.setFormat(f"{status} %p%")
        progress_bar.setTextVisible(True)
        progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 3px;
                text-align: center;
                background-color: #F5F5F5;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 2px;
            }
        """)
        
        # 将组件添加到布局
        task_layout.addLayout(header_layout)
        task_layout.addWidget(progress_bar)
        
        # 存储小部件引用
        self.task_widgets[task_id] = {
            'widget': task_widget,
            'type_label': type_label,
            'name_label': name_label,
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
            
            # 根据状态设置进度条颜色
            style = task['progress_bar'].styleSheet()
            if "运行中" in status or "处理中" in status:
                color = "#4CAF50"  # 绿色
            elif "等待" in status:
                color = "#FF9800"  # 橙色
            elif "暂停" in status:
                color = "#2196F3"  # 蓝色
            elif "失败" in status or "错误" in status:
                color = "#F44336"  # 红色
            else:
                color = "#4CAF50"  # 默认绿色
                
            style = style.replace("background-color: #4CAF50;", f"background-color: {color};")
            style = style.replace("background-color: #FF9800;", f"background-color: {color};")
            style = style.replace("background-color: #2196F3;", f"background-color: {color};")
            style = style.replace("background-color: #F44336;", f"background-color: {color};")
            
            task['progress_bar'].setStyleSheet(style)
    
    def update_task_status(self, task_id, status):
        """更新任务状态
        
        Args:
            task_id: 任务ID
            status: 新状态，如"运行中"、"已暂停"、"已完成"、"已取消"、"失败"
        """
        if task_id in self.task_widgets:
            task_widget = self.task_widgets[task_id]
            
            # 更新任务状态标签
            if hasattr(task_widget, 'status_label'):
                task_widget.status_label.setText(status)
                
                # 根据状态设置不同颜色
                status_colors = {
                    "运行中": "#4CAF50",    # 绿色
                    "已暂停": "#FF9800",    # 橙色
                    "等待中": "#2196F3",    # 蓝色
                    "已完成": "#9E9E9E",    # 灰色
                    "已取消": "#757575",    # 深灰色
                    "失败": "#F44336"      # 红色
                }
                
                color = status_colors.get(status, "#000000")
                task_widget.status_label.setStyleSheet(f"color: {color}; font-weight: bold;")
    
    def update_task_progress(self, task_id, progress):
        """更新任务进度
        
        Args:
            task_id: 任务ID
            progress: 进度值，0-100的整数
        """
        if task_id in self.task_widgets:
            task_widget = self.task_widgets[task_id]
            
            # 更新进度条
            if hasattr(task_widget, 'progress_bar'):
                task_widget.progress_bar.setValue(progress)
    
    def remove_task(self, task_id):
        """从概览中移除任务
        
        Args:
            task_id: 要移除的任务ID
        """
        if task_id in self.task_widgets:
            # 获取任务部件
            task_widget = self.task_widgets[task_id]
            
            # 从布局中移除
            self.tasks_layout.removeWidget(task_widget)
            
            # 隐藏并删除部件
            task_widget.hide()
            task_widget.deleteLater()
            
            # 从字典中移除
            del self.task_widgets[task_id]
            
            logger.debug(f"从任务概览中移除任务: {task_id}")
    
    def clear_tasks(self):
        """清除所有任务"""
        # 移除所有任务小部件
        for task_id in list(self.task_widgets.keys()):
            self.remove_task(task_id)
    
    def _update_translations(self):
        """更新翻译文本"""
        # 更新标题
        if hasattr(self, 'summary_label'):
            self.summary_label.setText(tr("ui.tasks.title"))
        
        # 更新查看所有任务按钮
        if hasattr(self, 'view_all_button'):
            self.view_all_button.setText(tr("ui.tasks.active_tasks"))
        
        logger.debug("任务概览翻译已更新") 