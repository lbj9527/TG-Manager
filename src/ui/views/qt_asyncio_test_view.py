"""
TG-Manager QtAsyncio测试模块
用于验证QtAsyncio与界面程序的集成
"""

import asyncio
import random
from loguru import logger
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QGridLayout, QTabWidget, QScrollArea, QSizePolicy,
    QSpacerItem, QProgressBar
)
from PySide6.QtCore import Qt, Signal, QSize, QObject
from PySide6.QtGui import QColor, QFont, QPalette

# 移除对不存在的task_panel模块的导入
# from src.ui.components.task_panel import TaskPanel
import PySide6.QtAsyncio as QtAsyncio


class AsyncTestView(QWidget):
    """QtAsyncio测试视图"""
    
    # 定义信号
    set_num = Signal(int, QColor)  # 用于埃拉托斯特尼筛法示例

    def __init__(self, config=None, parent=None):
        """初始化视图
        
        Args:
            config: 配置对象
            parent: 父窗口
        """
        super().__init__(parent)
        self.config = config or {}
        
        # 设置布局
        self.main_layout = QVBoxLayout(self)
        
        # 创建标题标签
        self.title_label = QLabel("QtAsyncio 测试模块")
        self.title_label.setAlignment(Qt.AlignCenter)
        font = self.title_label.font()
        font.setPointSize(font.pointSize() + 4)
        font.setBold(True)
        self.title_label.setFont(font)
        self.main_layout.addWidget(self.title_label)
        
        # 创建说明标签
        self.desc_label = QLabel(
            "此模块用于测试QtAsyncio与界面程序的集成。"
            "展示了如何在Qt界面中使用Python异步编程功能，"
            "实现非阻塞UI操作和高性能后台处理。"
        )
        self.desc_label.setWordWrap(True)
        self.desc_label.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(self.desc_label)
        
        # 创建选项卡控件
        self.tab_widget = QTabWidget()
        self.main_layout.addWidget(self.tab_widget)
        
        # 创建基础UI更新测试选项卡
        self.basic_tab = self._create_basic_update_tab()
        self.tab_widget.addTab(self.basic_tab, "基础UI更新")
        
        # 创建多协程并发测试选项卡
        self.concurrent_tab = self._create_concurrent_tab()
        self.tab_widget.addTab(self.concurrent_tab, "多协程并发演示")
        
        # 运行状态变量
        self.is_eratosthenes_running = False
        self.current_tasks = []
        
        # 连接信号
        self.set_num.connect(self._set_num_handler)
        
        logger.info("QtAsyncio测试视图初始化完成")
    
    def _create_basic_update_tab(self):
        """创建基础UI更新测试选项卡
        
        返回:
            QWidget: 选项卡控件
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 添加说明
        info_label = QLabel(
            "点击按钮后，系统将启动一个异步任务，该任务会在短暂延迟后更新下方文本。"
            "在任务执行期间，UI保持完全响应，这展示了QtAsyncio如何避免UI阻塞。"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # 添加显示文本的标签
        self.text_label = QLabel("等待更新...")
        self.text_label.setAlignment(Qt.AlignCenter)
        font = self.text_label.font()
        font.setPointSize(font.pointSize() + 8)
        self.text_label.setFont(font)
        self.text_label.setStyleSheet("background-color: #f0f0f0; padding: 20px; border-radius: 5px;")
        self.text_label.setMinimumHeight(100)
        layout.addWidget(self.text_label)
        
        # 添加按钮
        button_layout = QHBoxLayout()
        
        self.update_button = QPushButton("更新文本")
        self.update_button.clicked.connect(self._on_update_button_clicked)
        button_layout.addWidget(self.update_button)
        
        self.multiple_update_button = QPushButton("多次更新文本")
        self.multiple_update_button.clicked.connect(self._on_multiple_update_button_clicked)
        button_layout.addWidget(self.multiple_update_button)
        
        layout.addLayout(button_layout)
        
        # 添加状态标签
        self.status_label = QLabel("就绪")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        
        return tab
    
    def _create_concurrent_tab(self):
        """创建多协程并发测试选项卡
        
        返回:
            QWidget: 选项卡控件
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 添加说明
        info_label = QLabel(
            "本测试使用埃拉托斯特尼筛法算法查找素数，展示了多个协程如何并发工作。"
            "每个数字的倍数由单独的协程处理，使用不同颜色标记。"
            "这演示了如何在UI应用中使用复杂的异步并发模型。"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # 添加状态标签
        self.prime_status_label = QLabel("准备就绪")
        self.prime_status_label.setAlignment(Qt.AlignCenter)
        font = self.prime_status_label.font()
        font.setPointSize(font.pointSize() + 2)
        self.prime_status_label.setFont(font)
        layout.addWidget(self.prime_status_label)
        
        # 创建数字网格的滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)
        
        # 创建网格容器
        grid_container = QWidget()
        scroll_area.setWidget(grid_container)
        
        # 创建网格布局
        self.grid_layout = QGridLayout(grid_container)
        self.grid_layout.setSpacing(2)
        
        # 设置网格大小
        self.rows = 20
        self.cols = 20
        self.num = self.rows * self.cols
        
        # 创建数字标签
        k = 1
        for i in range(self.rows):
            for j in range(self.cols):
                box = QLabel(f"{k}")
                box.setAlignment(Qt.AlignCenter)
                box.setMinimumSize(30, 30)
                box.setStyleSheet("border: 1px solid #ddd; background-color: #f8f8f8;")
                self.grid_layout.addWidget(box, i, j, Qt.AlignCenter)
                k += 1
        
        # 添加控制按钮
        button_layout = QHBoxLayout()
        
        self.start_prime_button = QPushButton("开始演示")
        self.start_prime_button.clicked.connect(self._on_start_prime_button_clicked)
        button_layout.addWidget(self.start_prime_button)
        
        self.stop_prime_button = QPushButton("停止演示")
        self.stop_prime_button.clicked.connect(self._on_stop_prime_button_clicked)
        self.stop_prime_button.setEnabled(False)
        button_layout.addWidget(self.stop_prime_button)
        
        layout.addLayout(button_layout)
        
        return tab
    
    def _on_update_button_clicked(self):
        """处理更新按钮点击事件"""
        self.update_button.setEnabled(False)
        self.status_label.setText("任务执行中...")
        
        # 修改异步任务创建方式，避免"no running event loop"错误
        try:
            # 获取或创建事件循环
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                # 如果没有运行中的事件循环，使用现有的全局事件循环
                loop = asyncio.get_event_loop_policy().get_event_loop()
            
            # 使用create_task创建任务
            task = loop.create_task(self._async_update_text())
        except Exception as e:
            logger.error(f"创建异步任务失败: {e}")
            self.status_label.setText(f"任务创建失败: {str(e)}")
            self.update_button.setEnabled(True)
    
    def _on_multiple_update_button_clicked(self):
        """处理多次更新按钮点击事件"""
        self.multiple_update_button.setEnabled(False)
        self.status_label.setText("任务执行中...")
        
        # 修改异步任务创建方式，避免"no running event loop"错误
        try:
            # 获取或创建事件循环
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                # 如果没有运行中的事件循环，使用现有的全局事件循环
                loop = asyncio.get_event_loop_policy().get_event_loop()
            
            # 使用create_task创建任务
            task = loop.create_task(self._async_multiple_updates())
        except Exception as e:
            logger.error(f"创建异步任务失败: {e}")
            self.status_label.setText(f"任务创建失败: {str(e)}")
            self.multiple_update_button.setEnabled(True)
    
    def _on_start_prime_button_clicked(self):
        """处理开始素数演示按钮点击事件"""
        if not self.is_eratosthenes_running:
            self.is_eratosthenes_running = True
            self.start_prime_button.setEnabled(False)
            self.stop_prime_button.setEnabled(True)
            
            # 重置UI状态
            self._reset_grid()
            
            # 修改异步任务创建方式，避免"no running event loop"错误
            try:
                # 获取或创建事件循环
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    # 如果没有运行中的事件循环，使用现有的全局事件循环
                    loop = asyncio.get_event_loop_policy().get_event_loop()
                
                # 创建并启动埃拉托斯特尼筛法实例
                eratosthenes = Eratosthenes(self.num, self, tick=0.1)
                task = loop.create_task(eratosthenes.start())
                self.current_tasks.append(task)
            except Exception as e:
                logger.error(f"创建素数演示任务失败: {e}")
                self.prime_status_label.setText(f"任务创建失败: {str(e)}")
                self.is_eratosthenes_running = False
                self.start_prime_button.setEnabled(True)
                self.stop_prime_button.setEnabled(False)
    
    def _on_stop_prime_button_clicked(self):
        """处理停止素数演示按钮点击事件"""
        if self.is_eratosthenes_running:
            logger.info("停止素数演示...")
            
            # 首先获取所有任务
            all_tasks = set()
            
            # 获取事件循环
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.get_event_loop_policy().get_event_loop()
            
            # 收集所有未完成的任务
            try:
                all_tasks = {t for t in asyncio.all_tasks(loop) if not t.done()}
                logger.debug(f"找到 {len(all_tasks)} 个正在运行的任务")
            except Exception as e:
                logger.error(f"获取所有异步任务时出错: {e}")
            
            # 取消记录的主任务
            for task in self.current_tasks:
                try:
                    if not task.done() and not task.cancelled():
                        logger.debug(f"取消主任务: {task}")
                        task.cancel()
                except Exception as e:
                    logger.error(f"取消主任务时出错: {e}")
            
            # 短暂等待，确保取消信号已传播
            try:
                loop.call_later(0.1, lambda: None)
            except Exception as e:
                logger.error(f"设置延迟回调时出错: {e}")
            
            # 清空任务列表
            self.current_tasks.clear()
            
            # 重置状态
            self.is_eratosthenes_running = False
            self.start_prime_button.setEnabled(True)
            self.stop_prime_button.setEnabled(False)
            self.prime_status_label.setText("演示已停止")
            
            logger.info("素数演示已停止")
    
    def _reset_grid(self):
        """重置网格显示"""
        for i in range(self.rows):
            for j in range(self.cols):
                widget = self.grid_layout.itemAtPosition(i, j).widget()
                widget.setStyleSheet("border: 1px solid #ddd; background-color: #f8f8f8;")
                # 重置字体
                font = widget.font()
                font.setBold(False)
                widget.setFont(font)
                # 重置调色板
                widget.setPalette(QPalette())
    
    def _set_num_handler(self, i, color):
        """设置数字颜色处理函数
        
        Args:
            i: 数字索引 (1-based)
            color: 要设置的颜色
        """
        row = (i - 1) // self.cols
        col = (i - 1) % self.cols
        
        try:
            widget = self.grid_layout.itemAtPosition(row, col).widget()
            if widget:
                # 设置粗体
                font = widget.font()
                font.setBold(True)
                widget.setFont(font)
                
                # 设置文本颜色
                palette = QPalette()
                palette.setColor(QPalette.WindowText, color)
                widget.setPalette(palette)
                
                # 更改背景色为略微暗淡的颜色
                bg_color = QColor(color)
                bg_color.setAlpha(40)  # 设置透明度
                widget.setStyleSheet(f"border: 1px solid #ddd; background-color: {bg_color.name(QColor.HexArgb)};")
        except Exception as e:
            logger.error(f"设置网格单元格样式时出错: {e}")
    
    async def _async_update_text(self):
        """异步更新文本任务"""
        try:
            # 更新状态
            self.status_label.setText("正在执行异步任务...")
            
            # 模拟耗时操作
            await asyncio.sleep(1)
            
            # 更新UI
            self.text_label.setText("文本已异步更新！")
            self.status_label.setText("任务已完成")
            
            # 延迟后重置按钮
            await asyncio.sleep(0.5)
            self.update_button.setEnabled(True)
            
        except asyncio.CancelledError:
            logger.info("异步更新文本任务被取消")
            self.status_label.setText("任务被取消")
            self.update_button.setEnabled(True)
        except Exception as e:
            logger.error(f"异步更新文本任务出错: {e}")
            self.status_label.setText(f"任务出错: {str(e)}")
            self.update_button.setEnabled(True)
    
    async def _async_multiple_updates(self):
        """异步多次更新文本任务"""
        try:
            # 执行多次更新
            for i in range(10):
                # 更新状态
                self.status_label.setText(f"异步更新中 ({i+1}/10)...")
                
                # 更新文本
                self.text_label.setText(f"更新次数：{i+1}")
                
                # 等待短暂时间
                await asyncio.sleep(0.5)
            
            # 完成后显示结果
            self.text_label.setText("多次更新完成！")
            self.status_label.setText("全部任务已完成")
            
            # 重置按钮状态
            self.multiple_update_button.setEnabled(True)
            
        except asyncio.CancelledError:
            logger.info("多次更新文本任务被取消")
            self.status_label.setText("任务被取消")
            self.multiple_update_button.setEnabled(True)
        except Exception as e:
            logger.error(f"多次更新文本任务出错: {e}")
            self.status_label.setText(f"任务出错: {str(e)}")
            self.multiple_update_button.setEnabled(True)


class Eratosthenes(QObject):
    """埃拉托斯特尼筛法类"""
    
    def __init__(self, num, window, tick=0.1):
        """初始化
        
        Args:
            num: 数字范围 (1-num)
            window: 主窗口引用，用于更新UI
            tick: 协程切换间隔
        """
        super().__init__()
        self.num = num
        # 标记数组：索引对应数字-1，即sieve[0]表示数字1，sieve[1]表示数字2
        self.sieve = [True] * self.num  # 标记数组
        # 设置1不是素数 (索引0)
        self.sieve[0] = False
        self.base = 1  # 从数字2开始处理（索引1）
        self.window = window  # 窗口引用
        self.tick = tick  # 协程切换间隔
        self.coroutines = []  # 协程计数
        self.done = False  # 完成标志
        self.loop = None  # 事件循环引用
        self.tasks = []   # 存储所有创建的任务
        self.cancelled = False  # 取消标志
    
    def get_tick(self):
        """获取当前tick时间"""
        return self.loop.time() + self.tick
    
    def cancel_all_tasks(self):
        """取消所有任务"""
        self.cancelled = True
        for task in self.tasks:
            if not task.done() and not task.cancelled():
                logger.debug(f"取消Eratosthenes子任务: {task}")
                task.cancel()
        self.tasks.clear()
    
    async def start(self):
        """开始执行筛法算法"""
        try:
            self.loop = asyncio.get_event_loop()
            
            # 获取事件循环的方法
            def get_loop():
                try:
                    return asyncio.get_running_loop()
                except RuntimeError:
                    return self.loop
            
            # 创建更新文本的任务
            text_task = get_loop().create_task(self.update_text())
            self.tasks.append(text_task)
            
            # 主循环 - 找到素数并启动标记任务
            while self.base <= self.num // 2 and not self.cancelled:
                await asyncio.sleep(self.tick)
                
                # 检查是否被取消
                if self.cancelled or asyncio.current_task().cancelled():
                    raise asyncio.CancelledError()
                
                # 查找下一个素数
                next_prime_found = False
                for i in range(self.base + 1, self.num + 1):  # 从base+1到num的数字
                    # 转换为索引（减1）
                    idx = i - 1
                    if self.sieve[idx]:  # 如果未被标记为非素数
                        # 找到下一个素数，记录它的数值（而非索引）
                        prime_number = i
                        self.base = i  # 更新base为当前找到的素数值
                        next_prime_found = True
                        break
                
                # 如果找不到下一个素数，退出循环
                if not next_prime_found:
                    break
                    
                # 创建并启动标记任务，传入实际的素数值
                mark_task = get_loop().create_task(self.mark_number(prime_number))
                self.tasks.append(mark_task)
            
            # 等待所有标记任务完成
            while sum(self.coroutines) > 0 and not self.cancelled:
                await asyncio.sleep(self.tick)
                
                # 检查是否被取消
                if self.cancelled or asyncio.current_task().cancelled():
                    raise asyncio.CancelledError()
            
            # 设置完成标志
            self.done = True
            
            # 确保文本更新任务有机会显示最终消息
            await asyncio.sleep(self.tick * 2)
            
            # 高亮显示所有未被标记的数字（素数）
            if not self.cancelled:
                await self.highlight_primes()
            
            # 重置UI状态
            self.window.is_eratosthenes_running = False
            self.window.start_prime_button.setEnabled(True)
            self.window.stop_prime_button.setEnabled(False)
            
        except asyncio.CancelledError:
            logger.info("埃拉托斯特尼筛法演示被取消")
            # 取消所有子任务
            self.cancel_all_tasks()
            
            # 重置UI状态
            self.window.is_eratosthenes_running = False
            self.window.start_prime_button.setEnabled(True)
            self.window.stop_prime_button.setEnabled(False)
            self.window.prime_status_label.setText("演示已停止")
            
            # 重新抛出异常，确保调用者知道任务被取消
            raise
        finally:
            # 确保任务列表被清空
            self.tasks.clear()
    
    async def mark_number(self, prime):
        """标记特定素数的所有倍数
        
        Args:
            prime: 素数值（不是索引）
        """
        # 注册协程
        id = len(self.coroutines)
        self.coroutines.append(1)
        
        try:
            # 为每个协程生成一个不同的颜色
            color = QColor(
                random.randint(64, 192), 
                random.randint(64, 192), 
                random.randint(64, 192)
            )
            
            # 标记该素数的所有倍数为非素数，从2*prime开始
            for i in range(2 * prime, self.num + 1, prime):
                # 检查是否被取消
                if self.cancelled or asyncio.current_task().cancelled():
                    raise asyncio.CancelledError()
                
                # 获取数字i的索引
                idx = i - 1
                
                if self.sieve[idx]:  # 如果还没被标记为非素数
                    self.sieve[idx] = False  # 标记为非素数
                    # 使用信号更新UI，传入实际数字值（非索引）
                    self.window.set_num.emit(i, color)
                
                # 让出控制权，避免长时间占用
                await asyncio.sleep(self.tick)
                
        except asyncio.CancelledError:
            logger.info(f"标记数字 {prime} 的倍数任务被取消")
            raise
        finally:
            # 标记协程完成
            if id < len(self.coroutines):
                self.coroutines[id] = 0
    
    async def highlight_primes(self):
        """在算法完成后，高亮显示所有素数"""
        # 使用特殊颜色显示素数
        prime_color = QColor(0, 120, 215)  # 蓝色
        
        # 遍历所有数字
        for i in range(2, self.num + 1):  # 从2开始
            # 检查是否被取消
            if self.cancelled:
                break
                
            # 获取索引
            idx = i - 1
            
            # 如果是素数（未被标记为非素数）
            if self.sieve[idx]:
                # 高亮显示
                self.window.set_num.emit(i, prime_color)
                
                # 短暂等待，使视觉效果更明显
                await asyncio.sleep(self.tick / 5)  # 使用更短的等待时间
    
    async def update_text(self):
        """更新UI文本"""
        try:
            while not self.done and not self.cancelled:
                # 检查是否被取消
                if asyncio.current_task().cancelled():
                    raise asyncio.CancelledError()
                
                # 交替显示不同的文本，产生动画效果
                if int(self.loop.time() + self.tick) % 2:
                    text = "⚙️ ...计算素数中... ⚙️"
                else:
                    text = "👩‍💻 ...分析数据中... 👩‍💻"
                
                self.window.prime_status_label.setText(text)
                await asyncio.sleep(self.tick)
            
            # 当算法完成时，显示结束消息
            if not self.cancelled:
                self.window.prime_status_label.setText(
                    "🎉 计算完成！蓝色数字为素数 🎉"
                )
        
        except asyncio.CancelledError:
            self.window.prime_status_label.setText("演示已取消")
            raise 