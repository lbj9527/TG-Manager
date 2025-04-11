"""
TG-Manager 主窗口状态栏模块
包含主窗口的状态栏创建和状态信息更新功能
"""

from loguru import logger
import psutil
from PySide6.QtWidgets import QLabel, QStatusBar
from PySide6.QtCore import QTimer

class StatusBarMixin:
    """状态栏功能混入类
    
    为MainWindow提供状态栏相关功能
    """
    
    def _create_status_bar(self):
        """创建状态栏"""
        # 获取状态栏对象
        status_bar = self.statusBar()
        
        # 创建状态栏各部分组件
        # 1. 功能提示区域 - 使用默认的临时消息区域
        status_bar.showMessage("就绪")
        
        # 2. 客户端状态
        self.client_status_label = QLabel("客户端: 未连接")
        self.client_status_label.setMinimumWidth(150)
        self.client_status_label.setStyleSheet("padding: 0 8px; color: #757575;")
        self.statusBar().addPermanentWidget(self.client_status_label)
        
        # 3. CPU/内存使用率
        self.resource_usage_label = QLabel("CPU: -- | 内存: --")
        self.resource_usage_label.setMinimumWidth(200)
        self.resource_usage_label.setStyleSheet("padding: 0 8px; color: #4CAF50;")
        self.statusBar().addPermanentWidget(self.resource_usage_label)
        
        # 添加任务统计标签
        self.task_stats_label = QLabel("任务: 0 运行中 | 0 等待中 | 0 已完成")
        self.task_stats_label.setMinimumWidth(250)
        self.task_stats_label.setStyleSheet("padding: 0 8px; color: #2196F3;")
        self.statusBar().addPermanentWidget(self.task_stats_label)
        
        # 设置定时器，定期更新资源使用率
        self.resource_timer = QTimer(self)
        self.resource_timer.timeout.connect(self._update_resource_usage)
        self.resource_timer.start(5000)  # 每5秒更新一次
        
        # 立即更新一次状态
        self._update_resource_usage()
        
        logger.debug("状态栏创建完成")
    
    def _toggle_statusbar(self, checked):
        """切换状态栏的可见性
        
        Args:
            checked: 是否显示
        """
        self.statusBar().setVisible(checked)
    
    def _update_resource_usage(self):
        """更新资源使用情况"""
        try:
            # 使用psutil库获取系统资源使用情况，不使用阻塞的interval参数
            cpu_usage = round(psutil.cpu_percent(interval=None), 1)
            
            # 获取内存使用情况
            memory = psutil.virtual_memory()
            memory_usage = round(memory.used / (1024 * 1024), 1)  # 转换为MB
            memory_total = round(memory.total / (1024 * 1024), 1)  # 转换为MB
            memory_percent = round(memory.percent, 1)
            
            # 格式化显示
            if memory_usage > 1024:
                # 如果超过1GB则显示为GB
                memory_text = f"{memory_usage / 1024:.1f}GB/{memory_total / 1024:.1f}GB ({memory_percent}%)"
            else:
                memory_text = f"{memory_usage:.0f}MB/{memory_total / 1024:.1f}GB ({memory_percent}%)"
            
            # 更新资源使用标签
            self.resource_usage_label.setText(f"CPU: {cpu_usage}% | 内存: {memory_text}")
            
            # 根据使用率设置不同的颜色
            if cpu_usage > 90 or memory_percent > 90:
                self.resource_usage_label.setStyleSheet("padding: 0 8px; color: #F44336;")  # 红色
            elif cpu_usage > 70 or memory_percent > 70:
                self.resource_usage_label.setStyleSheet("padding: 0 8px; color: #FF9800;")  # 橙色
            else:
                self.resource_usage_label.setStyleSheet("padding: 0 8px; color: #4CAF50;")  # 绿色
                
        except ImportError:
            # 如果没有psutil库，使用占位符数据
            self.resource_usage_label.setText("CPU: -- | 内存: --")
            logger.warning("未找到psutil库，无法获取系统资源使用情况")
            
        except Exception as e:
            # 其他错误情况
            self.resource_usage_label.setText("资源监控错误")
            logger.error(f"资源监控错误: {e}")
    
    def _update_client_status(self, connected=False, client_info=None):
        """更新客户端连接状态
        
        Args:
            connected: 是否已连接
            client_info: 客户端信息，如用户ID、名称等
        """
        try:
            # 确保在UI线程中执行状态更新
            if connected and client_info:
                # 如果已连接且有客户端信息，显示详细信息
                text = f"客户端: 已连接 ({client_info})"
                self.client_status_label.setStyleSheet("padding: 0 8px; font-weight: bold; color: #4CAF50;")  # 绿色加粗
            elif connected:
                # 如果已连接但没有详细信息
                text = "客户端: 已连接"
                self.client_status_label.setStyleSheet("padding: 0 8px; font-weight: bold; color: #4CAF50;")  # 绿色加粗
            else:
                # 未连接状态
                text = "客户端: 未连接"
                self.client_status_label.setStyleSheet("padding: 0 8px; font-weight: bold; color: #F44336;")  # 红色加粗
            
            self.client_status_label.setText(text)
            
            # 立即更新界面
            self.client_status_label.repaint()
            
            # 记录状态更新日志
            logger.debug(f"状态栏客户端状态已更新: {text}")
        except Exception as e:
            logger.error(f"更新客户端状态标签时出错: {e}")
            # 尝试恢复显示
            try:
                self.client_status_label.setText("客户端: 状态更新错误")
                self.client_status_label.setStyleSheet("padding: 0 8px; color: #F44336;")  # 红色
            except:
                pass
    
    def _update_task_statistics(self, running=0, waiting=0, completed=0):
        """更新状态栏中的任务统计信息
        
        Args:
            running: 运行中的任务数量
            waiting: 等待中的任务数量
            completed: 已完成的任务数量
        """
        try:
            # 更新任务统计文本
            self.task_stats_label.setText(f"任务: {running} 运行中 | {waiting} 等待中 | {completed} 已完成")
            
            # 根据任务状态设置颜色
            if running > 0:
                # 有运行中的任务，使用蓝色
                self.task_stats_label.setStyleSheet("padding: 0 8px; color: #2196F3;") 
            elif waiting > 0:
                # 有等待中的任务，使用橙色
                self.task_stats_label.setStyleSheet("padding: 0 8px; color: #FF9800;")
            else:
                # 没有活动任务，使用绿色
                self.task_stats_label.setStyleSheet("padding: 0 8px; color: #4CAF50;")
                
            # 同时更新任务概览中的统计信息，如果存在
            if hasattr(self, 'task_overview') and self.task_overview:
                self.task_overview.update_counters(running, completed, waiting, 0)
                
        except Exception as e:
            logger.error(f"更新任务统计信息失败: {e}")
            self.task_stats_label.setText("任务: 统计错误")
            self.task_stats_label.setStyleSheet("padding: 0 8px; color: #F44336;")
    
    def _refresh_task_statistics(self):
        """刷新任务统计信息，从当前打开的视图和任务管理器中获取最新数据"""
        try:
            # 默认初始值
            running = 0
            waiting = 0
            completed = 0
            
            # 从任务管理视图获取数据（如果已打开）
            if "task_manager" in self.opened_views:
                task_view = self.opened_views["task_manager"]
                if hasattr(task_view, 'get_task_statistics'):
                    # 首选：任务管理器提供专门的统计方法
                    running, waiting, completed = task_view.get_task_statistics()
                elif hasattr(task_view, 'tasks'):
                    # 备选：手动统计任务数量
                    tasks = task_view.tasks
                    for task in tasks.values():
                        status = task.get('status', '').lower()
                        if status in ['运行中', 'running']:
                            running += 1
                        elif status in ['等待中', 'waiting', '排队中', 'queued']:
                            waiting += 1
                        elif status in ['已完成', 'completed', 'finished']:
                            completed += 1
            
            # 更新状态栏中的任务统计信息
            self._update_task_statistics(running, waiting, completed)
            
        except Exception as e:
            logger.error(f"刷新任务统计信息失败: {e}")
    
    def _check_network_status(self):
        """检查网络连接状态"""
        # 该方法已移除，网络延时显示功能已禁用
        pass 