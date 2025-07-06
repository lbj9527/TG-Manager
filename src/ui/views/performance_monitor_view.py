"""
TG-Manager 性能监控界面
显示监听模块的实时性能指标和统计数据
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QGroupBox, QScrollArea,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QProgressBar, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QSize
from PySide6.QtGui import QFont, QColor, QPalette
from datetime import datetime

from src.utils.logger import get_logger
from src.utils.translation_manager import tr, get_translation_manager

logger = get_logger()


class MetricWidget(QFrame):
    """单个指标显示组件"""
    
    def __init__(self, title: str, value: str = "0", unit: str = "", color: str = "#2196F3"):
        super().__init__()
        self.setFrameStyle(QFrame.Box)
        self.setLineWidth(1)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)
        
        # 标题
        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(8)
        self.title_label.setFont(font)
        self.title_label.setStyleSheet("color: #666666;")
        layout.addWidget(self.title_label)
        
        # 值
        self.value_label = QLabel(value)
        self.value_label.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        self.value_label.setFont(font)
        self.value_label.setStyleSheet(f"color: {color};")
        layout.addWidget(self.value_label)
        
        # 单位
        if unit:
            self.unit_label = QLabel(unit)
            self.unit_label.setAlignment(Qt.AlignCenter)
            font = QFont()
            font.setPointSize(7)
            self.unit_label.setFont(font)
            self.unit_label.setStyleSheet("color: #888888;")
            layout.addWidget(self.unit_label)
        
        self.setMaximumHeight(70)
        self.setMinimumWidth(100)
        self.setMaximumWidth(150)
    
    def update_value(self, value: str):
        """更新指标值"""
        self.value_label.setText(value)


class PerformanceMonitorView(QWidget):
    """性能监控界面"""
    
    # 信号定义
    reset_metrics_requested = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.performance_monitor = None  # 将由Monitor设置
        self.translation_manager = get_translation_manager()
        self.translation_manager.language_changed.connect(self._update_translations)
        
        # 创建主滚动区域
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameStyle(QFrame.NoFrame)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 创建滚动内容容器
        scroll_content = QWidget()
        scroll_area.setWidget(scroll_content)
        
        # 设置主布局 
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll_area)
        
        # 设置滚动内容布局
        self.main_layout = QVBoxLayout(scroll_content)
        self.main_layout.setContentsMargins(8, 8, 8, 8)
        self.main_layout.setSpacing(6)
        
        # 创建界面组件
        self._create_header()
        self._create_overview_metrics()
        self._create_performance_metrics()
        self._create_system_metrics()
        self._create_error_metrics()
        self._create_time_window_metrics()
        self._create_detailed_table()
        
        # 在最后添加弹性空间
        self.main_layout.addStretch()
        
        # 设置定时器更新数据
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_all_metrics)
        self.update_timer.start(2000)  # 每2秒更新一次
        
        self._update_translations()
        
        logger.debug("性能监控界面初始化完成")
    
    def _create_header(self):
        """创建标题栏"""
        header_layout = QHBoxLayout()
        
        # 标题
        self.title_label = QLabel(tr("ui.listen.tabs.performance"))
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        self.title_label.setFont(font)
        header_layout.addWidget(self.title_label)
        
        header_layout.addStretch()
        
        # 重置按钮
        self.reset_button = QPushButton(tr("ui.performance_monitor.reset_metrics"))
        self.reset_button.clicked.connect(self._reset_metrics)
        header_layout.addWidget(self.reset_button)
        
        # 刷新按钮
        self.refresh_button = QPushButton(tr("ui.performance_monitor.refresh_now"))
        self.refresh_button.clicked.connect(self._update_all_metrics)
        header_layout.addWidget(self.refresh_button)
        
        self.main_layout.addLayout(header_layout)
    
    def _create_overview_metrics(self):
        """创建概览指标"""
        group = QGroupBox(tr("ui.performance_monitor.overview"))
        layout = QHBoxLayout(group)
        
        self.total_processed_widget = MetricWidget(tr("ui.performance_monitor.total_processed"), "0", tr("ui.performance_monitor.unit_count"), "#2196F3")
        self.total_forwarded_widget = MetricWidget(tr("ui.performance_monitor.total_forwarded"), "0", tr("ui.performance_monitor.unit_count"), "#4CAF50")
        self.total_filtered_widget = MetricWidget(tr("ui.performance_monitor.total_filtered"), "0", tr("ui.performance_monitor.unit_count"), "#FF9800")
        self.success_rate_widget = MetricWidget(tr("ui.performance_monitor.success_rate"), "0%", "", "#4CAF50")
        
        layout.addWidget(self.total_processed_widget)
        layout.addWidget(self.total_forwarded_widget)
        layout.addWidget(self.total_filtered_widget)
        layout.addWidget(self.success_rate_widget)
        layout.addStretch()
        
        self.main_layout.addWidget(group)
    
    def _create_performance_metrics(self):
        """创建性能指标"""
        group = QGroupBox(tr("ui.performance_monitor.performance"))
        layout = QHBoxLayout(group)
        
        self.avg_processing_time_widget = MetricWidget(tr("ui.performance_monitor.avg_processing_time"), "0.000", tr("ui.performance_monitor.unit_sec"), "#9C27B0")
        self.avg_forward_time_widget = MetricWidget(tr("ui.performance_monitor.avg_forward_time"), "0.000", tr("ui.performance_monitor.unit_sec"), "#9C27B0")
        self.throughput_widget = MetricWidget(tr("ui.performance_monitor.throughput"), "0.00", tr("ui.performance_monitor.unit_per_min"), "#00BCD4")
        self.p95_processing_time_widget = MetricWidget(tr("ui.performance_monitor.p95_processing_time"), "0.000", tr("ui.performance_monitor.unit_sec"), "#E91E63")
        
        layout.addWidget(self.avg_processing_time_widget)
        layout.addWidget(self.avg_forward_time_widget)
        layout.addWidget(self.throughput_widget)
        layout.addWidget(self.p95_processing_time_widget)
        layout.addStretch()
        
        self.main_layout.addWidget(group)
    
    def _create_system_metrics(self):
        """创建系统指标"""
        group = QGroupBox(tr("ui.performance_monitor.system"))
        layout = QHBoxLayout(group)
        
        self.cache_hit_rate_widget = MetricWidget(tr("ui.performance_monitor.cache_hit_rate"), "0%", "", "#FF5722")
        self.queue_size_widget = MetricWidget(tr("ui.performance_monitor.queue_size"), "0", tr("ui.performance_monitor.unit_count"), "#795548")
        self.memory_usage_widget = MetricWidget(tr("ui.performance_monitor.memory_usage"), "0.00", "MB", "#607D8B")
        
        layout.addWidget(self.cache_hit_rate_widget)
        layout.addWidget(self.queue_size_widget)
        layout.addWidget(self.memory_usage_widget)
        layout.addStretch()
        
        self.main_layout.addWidget(group)
    
    def _create_error_metrics(self):
        """创建错误统计"""
        group = QGroupBox(tr("ui.performance_monitor.error"))
        layout = QHBoxLayout(group)
        
        self.network_errors_widget = MetricWidget(tr("ui.performance_monitor.network_errors"), "0", tr("ui.performance_monitor.unit_times"), "#F44336")
        self.api_errors_widget = MetricWidget(tr("ui.performance_monitor.api_errors"), "0", tr("ui.performance_monitor.unit_times"), "#F44336")
        self.other_errors_widget = MetricWidget(tr("ui.performance_monitor.other_errors"), "0", tr("ui.performance_monitor.unit_times"), "#F44336")
        
        layout.addWidget(self.network_errors_widget)
        layout.addWidget(self.api_errors_widget)
        layout.addWidget(self.other_errors_widget)
        layout.addStretch()
        
        self.main_layout.addWidget(group)
    
    def _create_time_window_metrics(self):
        """创建时间窗口统计"""
        group = QGroupBox(tr("ui.performance_monitor.time_window"))
        layout = QHBoxLayout(group)
        
        self.messages_last_min_widget = MetricWidget(tr("ui.performance_monitor.last_1min"), "0", tr("ui.performance_monitor.unit_count"), "#3F51B5")
        self.messages_last_5min_widget = MetricWidget(tr("ui.performance_monitor.last_5min"), "0", tr("ui.performance_monitor.unit_count"), "#3F51B5")
        self.messages_last_hour_widget = MetricWidget(tr("ui.performance_monitor.last_1hour"), "0", tr("ui.performance_monitor.unit_count"), "#3F51B5")
        
        layout.addWidget(self.messages_last_min_widget)
        layout.addWidget(self.messages_last_5min_widget)
        layout.addWidget(self.messages_last_hour_widget)
        layout.addStretch()
        
        self.main_layout.addWidget(group)
    
    def _create_detailed_table(self):
        """创建详细信息表格"""
        self.details_group = QGroupBox(tr("ui.performance_monitor.details"))
        layout = QVBoxLayout(self.details_group)
        
        # 创建表格
        self.details_table = QTableWidget()
        self.details_table.setColumnCount(2)
        self.details_table.setHorizontalHeaderLabels([tr("ui.performance_monitor.detail_metric"), tr("ui.performance_monitor.detail_value")])
        
        # 设置表格样式
        header = self.details_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setStretchLastSection(True)  # 确保最后一列拉伸填充
        
        # 设置垂直表头（行号）不可见
        self.details_table.verticalHeader().setVisible(False)
        
        # 设置表格选择行为
        self.details_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.details_table.setSelectionMode(QTableWidget.SingleSelection)
        
        # 设置表格外观
        self.details_table.setAlternatingRowColors(True)
        self.details_table.setShowGrid(True)
        self.details_table.setGridStyle(Qt.SolidLine)
        
        # 设置表格高度以适应内容（7行数据 + 表头）
        # 使用更保险的高度值确保完全显示
        required_height = 300  # 直接设置300px高度
        
        # 设置更大的高度确保完全显示
        self.details_table.setMinimumHeight(required_height)
        self.details_table.setMaximumHeight(320)  # 最大320px
        
        # 禁用垂直滚动条，因为我们已经设置了合适的高度
        self.details_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.details_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 设置表格大小策略
        self.details_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        layout.addWidget(self.details_table)
        
        # 最后更新时间区域
        update_layout = QHBoxLayout()
        update_layout.addStretch()
        
        # 最后更新时间
        self.last_update_label = QLabel(tr("ui.performance_monitor.last_update_never"))
        self.last_update_label.setStyleSheet("color: #666666; font-size: 9px;")
        update_layout.addWidget(self.last_update_label)
        
        layout.addLayout(update_layout)
        
        self.main_layout.addWidget(self.details_group)
    
    def set_performance_monitor(self, monitor):
        """设置性能监控器实例"""
        self.performance_monitor = monitor
        logger.debug("性能监控器实例已设置")
    
    @Slot()
    def _update_all_metrics(self):
        """更新所有指标"""
        if not self.performance_monitor:
            return
        
        try:
            # 获取性能指标
            metrics = self.performance_monitor.get_metrics()
            
            # 更新概览指标
            self.total_processed_widget.update_value(str(metrics.total_processed))
            self.total_forwarded_widget.update_value(str(metrics.total_forwarded))
            self.total_filtered_widget.update_value(str(metrics.total_filtered))
            self.success_rate_widget.update_value(f"{metrics.success_rate:.1f}%")
            
            # 更新性能指标
            self.avg_processing_time_widget.update_value(f"{metrics.avg_processing_time:.3f}")
            self.avg_forward_time_widget.update_value(f"{metrics.avg_forward_time:.3f}")
            self.throughput_widget.update_value(f"{metrics.throughput_per_min:.2f}")
            self.p95_processing_time_widget.update_value(f"{metrics.p95_processing_time:.3f}")
            
            # 更新系统指标
            self.cache_hit_rate_widget.update_value(f"{metrics.cache_hit_rate:.1f}%")
            self.queue_size_widget.update_value(str(metrics.current_queue_size))
            self.memory_usage_widget.update_value(f"{metrics.memory_usage_mb:.2f}")
            
            # 更新错误统计
            self.network_errors_widget.update_value(str(metrics.network_errors))
            self.api_errors_widget.update_value(str(metrics.api_errors))
            self.other_errors_widget.update_value(str(metrics.other_errors))
            
            # 更新时间窗口统计
            self.messages_last_min_widget.update_value(str(metrics.messages_last_min))
            self.messages_last_5min_widget.update_value(str(metrics.messages_last_5min))
            self.messages_last_hour_widget.update_value(str(metrics.messages_last_hour))
            
            # 更新详细表格
            self._update_details_table(metrics)
            
            # 更新最后更新时间
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.last_update_label.setText(tr("ui.performance_monitor.last_update", time=current_time))
            
        except Exception as e:
            logger.error(f"更新性能指标时出错: {e}")
    
    def _update_details_table(self, metrics):
        """更新详细信息表格"""
        # 准备详细数据
        details = [
            (tr("ui.performance_monitor.total_failed"), str(metrics.total_failed)),
            (tr("ui.performance_monitor.min_processing_time"), f"{metrics.min_processing_time:.3f}" + tr("ui.performance_monitor.unit_sec")),
            (tr("ui.performance_monitor.max_processing_time"), f"{metrics.max_processing_time:.3f}" + tr("ui.performance_monitor.unit_sec")),
            (tr("ui.performance_monitor.p95_processing_time"), f"{metrics.p95_processing_time:.3f}" + tr("ui.performance_monitor.unit_sec")),
            (tr("ui.performance_monitor.network_errors"), str(metrics.network_errors)),
            (tr("ui.performance_monitor.api_errors"), str(metrics.api_errors)),
            (tr("ui.performance_monitor.other_errors"), str(metrics.other_errors)),
        ]
        
        # 设置表格行数
        self.details_table.setRowCount(len(details))
        
        # 填充数据
        for row, (key, value) in enumerate(details):
            self.details_table.setItem(row, 0, QTableWidgetItem(key))
            self.details_table.setItem(row, 1, QTableWidgetItem(value))
        
        # 设置更大的行高确保内容完全可见
        for row in range(len(details)):
            self.details_table.setRowHeight(row, 35)  # 每行35px高度
        
        # 确保表格头部可见
        header = self.details_table.horizontalHeader()
        header.setVisible(True)
        header.setMinimumHeight(30)  # 设置表头最小高度
    
    @Slot()
    def _reset_metrics(self):
        """重置性能指标"""
        if self.performance_monitor:
            self.performance_monitor.reset_metrics()
            self._update_all_metrics()  # 立即更新显示
            logger.info("性能指标已重置")
        
        # 发射信号通知其他组件
        self.reset_metrics_requested.emit()
    
    def cleanup(self):
        """清理资源"""
        if self.update_timer:
            self.update_timer.stop()
        logger.debug("性能监控界面资源已清理")
    
    def _update_translations(self):
        """刷新所有UI文本，支持动态语言切换"""
        # 主标题
        if hasattr(self, 'title_label'):
            self.title_label.setText(tr("ui.listen.tabs.performance"))
        # 分组标题（用itemAt保证一定能刷新）
        if hasattr(self, 'main_layout'):
            group_titles = [
                "ui.performance_monitor.overview",
                "ui.performance_monitor.performance",
                "ui.performance_monitor.system",
                "ui.performance_monitor.error",
                "ui.performance_monitor.time_window"
            ]
            for i, key in enumerate(group_titles):
                item = self.main_layout.itemAt(i)
                if item and item.widget():
                    item.widget().setTitle(tr(key))
        # 详细统计分组标题
        if hasattr(self, 'details_group'):
            self.details_group.setTitle(tr("ui.performance_monitor.details"))
        # 详细统计表头
        if hasattr(self, 'details_table'):
            self.details_table.setHorizontalHeaderLabels([
                tr("ui.performance_monitor.detail_metric"),
                tr("ui.performance_monitor.detail_value")
            ])
        # 按钮
        if hasattr(self, 'reset_button'):
            self.reset_button.setText(tr("ui.performance_monitor.reset_metrics"))
        if hasattr(self, 'refresh_button'):
            self.refresh_button.setText(tr("ui.performance_monitor.refresh_now"))
        # 最后更新时间
        if hasattr(self, 'last_update_label'):
            self.last_update_label.setText(tr("ui.performance_monitor.last_update_never"))
        # ... 其它指标label/unit同理 ... 