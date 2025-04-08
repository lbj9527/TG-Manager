# 基本示例：更新 UI 文本
# from __future__ import annotations

# from PySide6.QtCore import Qt
# from PySide6.QtWidgets import (QApplication, QLabel, QMainWindow, QPushButton, QVBoxLayout, QWidget)

# import PySide6.QtAsyncio as QtAsyncio

# import asyncio
# import sys


# class MainWindow(QMainWindow):

#     def __init__(self):
#         super().__init__()

#         widget = QWidget()
#         self.setCentralWidget(widget)

#         layout = QVBoxLayout(widget)

#         self.text = QLabel("The answer is 42.")
#         layout.addWidget(self.text, alignment=Qt.AlignmentFlag.AlignCenter)

#         async_trigger = QPushButton(text="What is the question?")
#         async_trigger.clicked.connect(lambda: asyncio.ensure_future(self.set_text()))
#         layout.addWidget(async_trigger, alignment=Qt.AlignmentFlag.AlignCenter)

#     async def set_text(self):
#         await asyncio.sleep(1)
#         self.text.setText("What do you get if you multiply six by nine?")


# if __name__ == "__main__":
#     app = QApplication(sys.argv)
#     main_window = MainWindow()
#     main_window.show()

#     QtAsyncio.run(handle_sigint=True)


#多协程并发示例
from PySide6.QtCore import (Qt, QObject, Signal, Slot)
from PySide6.QtGui import (QColor, QFont, QPalette)
from PySide6.QtWidgets import (QApplication, QGridLayout, QLabel, QMainWindow, 
                              QVBoxLayout, QWidget)
import PySide6.QtAsyncio as QtAsyncio
import asyncio
import sys
from random import randint


class MainWindow(QMainWindow):
    # 定义一个信号，用于在异步线程中更新UI
    # 参数：整数（表示数字索引）和QColor（表示颜色）
    set_num = Signal(int, QColor)

    def __init__(self, rows, cols):
        super().__init__()
        
        # 存储行列数量
        self.rows = rows
        self.cols = cols

        # 创建中央部件
        widget_central = QWidget()
        self.setCentralWidget(widget_central)

        # 创建外层垂直布局
        layout_outer = QVBoxLayout(widget_central)

        # 创建顶部文本标签
        self.widget_outer_text = QLabel()
        font = QFont()
        font.setPointSize(14)  # 设置字体大小
        self.widget_outer_text.setFont(font)
        # 将标签添加到布局中并居中对齐
        layout_outer.addWidget(self.widget_outer_text, alignment=Qt.AlignmentFlag.AlignCenter)

        # 创建网格部件
        widget_inner_grid = QWidget()
        layout_outer.addWidget(widget_inner_grid, alignment=Qt.AlignmentFlag.AlignCenter)

        # 创建网格布局
        self.layout_inner_grid = QGridLayout(widget_inner_grid)
        k = 1
        # 创建行×列的数字标签网格
        for i in range(self.rows):
            for j in range(self.cols):
                box = QLabel(f"{k}")
                self.layout_inner_grid.addWidget(box, i, j, Qt.AlignmentFlag.AlignCenter)
                k += 1

        # 连接信号到槽函数
        self.set_num.connect(self.set_num_handler)

    @Slot(int, QColor)
    def set_num_handler(self, i, color):
        """
        处理设置数字颜色的槽函数
        
        Args:
            i: 数字的索引（从1开始）
            color: 要设置的颜色
        """
        # 计算行列位置
        row = int((i - 1) / self.cols)
        col = (i - 1) - (row * self.cols)
        # 获取对应位置的控件
        widget = self.layout_inner_grid.itemAtPosition(row, col).widget()

        # 设置字体为粗体
        font = QFont()
        font.setWeight(QFont.Bold)
        # 设置文本颜色
        palette = QPalette()
        palette.setColor(QPalette.WindowText, color)
        widget.setFont(font)
        widget.setPalette(palette)


class Eratosthenes(QObject):
    """
    埃拉托斯特尼筛法（Sieve of Eratosthenes）实现类
    用于查找给定范围内的所有素数
    """
    def __init__(self, num, window, tick=0.1):
        """
        初始化埃拉托斯特尼筛法对象
        
        Args:
            num: 要检查的最大数字
            window: 主窗口对象，用于更新UI
            tick: 操作之间的时间间隔（秒）
        """
        super().__init__()
        self.num = num
        self.sieve = [True] * self.num  # 初始假设所有数字都是素数
        self.base = 0  # 当前处理的基数
        self.window = window
        self.tick = tick
        self.coroutines = []  # 跟踪活动协程
        self.done = False  # 标记是否完成
        self.loop = None  # 事件循环引用

    def get_tick(self):
        """获取下一个计时点"""
        return self.loop.time() + self.tick

    async def start(self):
        """
        启动埃拉托斯特尼筛法算法
        这是主协程，会创建多个子协程来并行标记数字
        """
        self.loop = asyncio.get_event_loop()  # 获取当前事件循环
        # 创建更新文本的协程任务
        asyncio.create_task(self.update_text())
        
        # 主循环：找到下一个素数并启动标记任务
        while self.base <= self.num / 2:
            await asyncio.sleep(self.tick)
            # 寻找下一个未被标记的数字（素数）
            for i in range(self.base + 1, self.num):
                if self.sieve[i]:
                    self.base = i
                    break
            # 创建新协程来标记当前素数的倍数
            asyncio.create_task(self.mark_number(self.base + 1))
            
        # 等待所有标记协程完成
        while sum(self.coroutines) > 0:
            await asyncio.sleep(self.tick)
        self.done = True

    async def mark_number(self, base):
        """
        标记某个素数的所有倍数为非素数
        
        Args:
            base: 当前素数值
        """
        # 注册协程ID并标记为活动状态
        id = len(self.coroutines)
        self.coroutines.append(1)
        
        # 为当前素数生成随机颜色
        color = QColor(randint(64, 192), randint(64, 192), randint(64, 192))
        
        # 标记所有base的倍数为非素数
        for i in range(2 * base, self.num + 1, base):
            if self.sieve[i - 1]:
                self.sieve[i - 1] = False
                # 发送信号更新UI
                self.window.set_num.emit(i, color)
            await asyncio.sleep(self.tick)
            
        # 标记协程已完成
        self.coroutines[id] = 0

    async def update_text(self):
        """更新UI显示的文本，创建动画效果"""
        while not self.done:
            await asyncio.sleep(self.tick)
            # 每两秒切换显示的文本，创建动画效果
            if int(self.loop.time() + self.tick) % 2:
                text = "⚙️ ...Calculating prime numbers... ⚙️"
            else:
                text = "👩‍💻 ...Hacking the universe... 👩‍💻"
            self.window.widget_outer_text.setText(text)

        # 计算完成后显示的文本
        self.window.widget_outer_text.setText(
            "🥳 Congratulations! You found all the prime numbers and solved mathematics. 🥳"
        )


if __name__ == "__main__":
    # 设置网格大小
    rows = 40
    cols = 40
    num = rows * cols  # 要处理的数字总量

    # 创建Qt应用
    app = QApplication(sys.argv)
    main_window = MainWindow(rows, cols)
    # 创建埃拉托斯特尼筛法对象
    eratosthenes = Eratosthenes(num, main_window)

    # 显示主窗口
    main_window.show()

    # 通过QtAsyncio运行异步主任务，同时处理中断信号
    QtAsyncio.run(eratosthenes.start(), handle_sigint=True)