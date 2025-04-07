# QtAsyncio API 指南与使用示例

## 简介

QtAsyncio 是 PySide6 提供的一个模块，它允许异步编程与 Qt 应用程序无缝集成。利用 QtAsyncio，开发者可以在 Qt 应用中使用 Python 的 asyncio 库，而无需复杂的事件循环集成工作。这使得可以构建响应式 UI 的同时，高效处理耗时操作，避免阻塞主线程。

QtAsyncio 解决了 asyncio 和 Qt 事件循环集成的问题，允许开发者以简单的方式在 Qt 应用中使用 Python 的协程。

## 安装要求

- PySide6（6.5.0 或更高版本）
- Python 3.7+

## 核心功能

QtAsyncio 模块提供了以下核心功能：

1. 将 asyncio 事件循环整合到 Qt 事件循环中
2. 允许 Qt 应用程序中运行异步协程
3. 支持 asyncio 的所有标准功能（如 Tasks、Futures、协程等）
4. 支持信号处理（SIGINT）

## API 参考

### 主要函数

#### `QtAsyncio.run()`

启动 asyncio 事件循环，并将其集成到 Qt 的事件循环中。

**语法：**

```python
QtAsyncio.run(coro=None, *, handle_sigint=False)
```

**参数：**

- `coro` (可选): 要运行的协程。如果未提供，则仅启动事件循环。
- `handle_sigint` (布尔值, 可选): 设置为 True 以启用 SIGINT (Ctrl+C) 处理。默认为 False。

**返回值：**

- 如果提供了协程，则返回协程的运行结果。
- 如果没有提供协程，则 QtAsyncio 会接管 Qt 的事件循环，运行异步任务，直到程序退出。

**例子：**

```python
import PySide6.QtAsyncio as QtAsyncio
import asyncio

async def main():
    # 异步操作
    await asyncio.sleep(1)
    print("Hello from asyncio!")
    return "Result"

# 不返回结果，只运行事件循环
QtAsyncio.run()

# 运行特定协程
result = QtAsyncio.run(main())

# 处理SIGINT（Ctrl+C）
QtAsyncio.run(handle_sigint=True)
```

### 其他常用 asyncio API (可在 QtAsyncio 环境中使用)

QtAsyncio 集成了 asyncio 的标准 API，下面是一些常用功能：

#### `asyncio.create_task()`

**语法：**

```python
asyncio.create_task(coro)
```

**描述：**
创建一个任务，调度协程的执行。返回 Task 对象。

#### `asyncio.ensure_future()`

**语法：**

```python
asyncio.ensure_future(obj)
```

**描述：**
确保对象是一个 Future 或 Task。如果对象是协程，将其包装为一个 Task。

#### `asyncio.sleep()`

**语法：**

```python
await asyncio.sleep(delay)
```

**描述：**
异步延迟执行，单位为秒。

#### `asyncio.gather()`

**语法：**

```python
await asyncio.gather(*coros_or_futures)
```

**描述：**
并发运行多个协程或 Future 对象。

## 与 Qt 信号和槽集成

QtAsyncio 允许将异步协程与 Qt 信号系统集成。下面是几种常见的集成模式：

### 1. 在信号处理器中启动协程

```python
button.clicked.connect(lambda: asyncio.ensure_future(some_coroutine()))
```

### 2. 从协程中发射信号

```python
async def update_ui():
    # 进行一些异步操作
    result = await some_async_operation()
    # 发射信号以更新UI
    window.update_signal.emit(result)
```

## 使用示例

### 基本示例：更新 UI 文本

以下示例展示了如何创建一个简单的应用程序，点击按钮后异步更新标签文本：

```python
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QLabel, QMainWindow, QPushButton,
                               QVBoxLayout, QWidget)
import PySide6.QtAsyncio as QtAsyncio
import asyncio
import sys


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        widget = QWidget()
        self.setCentralWidget(widget)

        layout = QVBoxLayout(widget)

        self.text = QLabel("The answer is 42.")
        layout.addWidget(self.text, alignment=Qt.AlignmentFlag.AlignCenter)

        async_trigger = QPushButton(text="What is the question?")
        async_trigger.clicked.connect(lambda: asyncio.ensure_future(self.set_text()))
        layout.addWidget(async_trigger, alignment=Qt.AlignmentFlag.AlignCenter)

    async def set_text(self):
        await asyncio.sleep(1)
        self.text.setText("What do you get if you multiply six by nine?")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()

    QtAsyncio.run(handle_sigint=True)
```

### 多协程并发示例：埃拉托斯特尼筛法

下面是一个更复杂的例子，使用埃拉托斯特尼筛法查找素数，展示多个协程并发：

````python
from PySide6.QtCore import (Qt, QObject, Signal, Slot)
from PySide6.QtGui import (QColor, QFont, QPalette)
from PySide6.QtWidgets import (QApplication, QGridLayout, QLabel, QMainWindow,
                              QVBoxLayout, QWidget)
import PySide6.QtAsyncio as QtAsyncio
import asyncio
import sys
from random import randint


class MainWindow(QMainWindow):

    set_num = Signal(int, QColor)

    def __init__(self, rows, cols):
        super().__init__()

        self.rows = rows
        self.cols = cols

        widget_central = QWidget()
        self.setCentralWidget(widget_central)

        layout_outer = QVBoxLayout(widget_central)

        self.widget_outer_text = QLabel()
        font = QFont()
        font.setPointSize(14)
        self.widget_outer_text.setFont(font)
        layout_outer.addWidget(self.widget_outer_text, alignment=Qt.AlignmentFlag.AlignCenter)

        widget_inner_grid = QWidget()
        layout_outer.addWidget(widget_inner_grid, alignment=Qt.AlignmentFlag.AlignCenter)

        self.layout_inner_grid = QGridLayout(widget_inner_grid)
        k = 1
        for i in range(self.rows):
            for j in range(self.cols):
                box = QLabel(f"{k}")
                self.layout_inner_grid.addWidget(box, i, j, Qt.AlignmentFlag.AlignCenter)
                k += 1

        self.set_num.connect(self.set_num_handler)

    @Slot(int, QColor)
    def set_num_handler(self, i, color):
        row = int((i - 1) / self.cols)
        col = (i - 1) - (row * self.cols)
        widget = self.layout_inner_grid.itemAtPosition(row, col).widget()

        font = QFont()
        font.setWeight(QFont.Bold)
        palette = QPalette()
        palette.setColor(QPalette.WindowText, color)
        widget.setFont(font)
        widget.setPalette(palette)


class Eratosthenes(QObject):
    def __init__(self, num, window, tick=0.1):
        super().__init__()
        self.num = num
        self.sieve = [True] * self.num
        self.base = 0
        self.window = window
        self.tick = tick
        self.coroutines = []
        self.done = False
        self.loop = None

    def get_tick(self):
        return self.loop.time() + self.tick

    async def start(self):
        self.loop = asyncio.get_event_loop()
        asyncio.create_task(self.update_text())
        while self.base <= self.num / 2:
            await asyncio.sleep(self.tick)
            for i in range(self.base + 1, self.num):
                if self.sieve[i]:
                    self.base = i
                    break
            asyncio.create_task(self.mark_number(self.base + 1))
        while sum(self.coroutines) > 0:
            await asyncio.sleep(self.tick)
        self.done = True

    async def mark_number(self, base):
        id = len(self.coroutines)
        self.coroutines.append(1)
        color = QColor(randint(64, 192), randint(64, 192), randint(64, 192))
        for i in range(2 * base, self.num + 1, base):
            if self.sieve[i - 1]:
                self.sieve[i - 1] = False
                self.window.set_num.emit(i, color)
            await asyncio.sleep(self.tick)
        self.coroutines[id] = 0

    async def update_text(self):
        while not self.done:
            await asyncio.sleep(self.tick)
            if int(self.loop.time() + self.tick) % 2:
                text = "⚙️ ...Calculating prime numbers... ⚙️"
            else:
                text = "👩‍💻 ...Hacking the universe... 👩‍💻"
            self.window.widget_outer_text.setText(text)

        self.window.widget_outer_text.setText(
            "🥳 Congratulations! You found all the prime numbers and solved mathematics. 🥳"
        )


if __name__ == "__main__":
    rows = 40
    cols = 40
    num = rows * cols

    app = QApplication(sys.argv)
    main_window = MainWindow(rows, cols)
    eratosthenes = Eratosthenes(num, main_window)

    main_window.show()

    QtAsyncio.run(eratosthenes.start(), handle_sigint=True)

### 埃拉托斯特尼筛法示例分析

这个示例展示了如何在Qt应用程序中使用多个协程并发执行任务，非常适合理解QtAsyncio的强大功能。下面是对这个示例的详细分析：

#### 程序架构

该程序由两个主要组件组成：
1. **MainWindow类** - 负责UI的呈现和响应
2. **Eratosthenes类** - 实现算法逻辑和协程管理

#### 多协程并发的实现方式

程序使用了以下几种协程：

1. **主协程** (`start`方法)
   - 获取事件循环并启动UI更新协程
   - 循环查找素数基数
   - 为每个找到的素数基数启动新的标记协程
   - 等待所有标记协程完成

2. **UI更新协程** (`update_text`方法)
   - 周期性更新UI文本
   - 显示交替的文本动画效果
   - 程序完成时显示结束消息

3. **标记协程** (`mark_number`方法)
   - 每个素数基数创建一个独立协程
   - 使用不同颜色标记非素数
   - 通过Qt信号与UI通信

#### 协程间通信机制

该示例展示了三种关键的协程间通信方式：

1. **Qt信号-槽机制**
   ```python
   self.window.set_num.emit(i, color)  # 从协程发送UI更新
````

2. **共享状态**

   - `self.sieve` - 记录哪些数字已被标记
   - `self.coroutines` - 跟踪活动协程数量
   - `self.done` - 标记算法完成

3. **协程计数与等待**
   ```python
   while sum(self.coroutines) > 0:
       await asyncio.sleep(self.tick)
   ```

#### 非阻塞 UI 更新

所有协程定期使用`await asyncio.sleep(self.tick)`让出控制权，确保：

- UI 保持响应性
- 多个协程能公平共享 CPU 时间
- 动画效果平滑流畅

#### 多协程并发的优势

相比传统多线程方法，这种基于协程的实现有以下优势：

1. **简化的同步** - 不需要互斥锁、信号量等同步原语
2. **自然的错误处理** - 异常在协程内正常传播
3. **线性代码流程** - 避免回调地狱，代码更易于理解
4. **高效** - 协程切换比线程切换开销小
5. **固有的线程安全** - 通过信号机制保证 UI 更新的线程安全

#### 应用场景

这种多协程并发模式特别适合：

- **I/O 密集型任务** - 网络请求、文件操作等
- **需要频繁 UI 更新的长时间运算**
- **多任务协作的场景**
- **动画效果**
- **后台处理与 UI 交互**

在实际应用中，您可以使用类似模式来实现：文件下载管理器、数据同步工具、实时数据可视化、响应式 UI 等功能。

## 与 Trio 库的比较

与 Trio 库相比，QtAsyncio 在与 Qt 集成方面更为简洁。如果使用 Trio，您需要编写额外的代码来实现事件循环集成，例如：

```python
class AsyncHelper(QObject):
    # 复杂的管道机制
    ...

# 启动 Trio 作为 Qt 的"客户"
trio.lowlevel.start_guest_run(...)
```

而使用 QtAsyncio，只需一行即可：

```python
QtAsyncio.run(coro, handle_sigint=True)
```

## 最佳实践

1. **避免 UI 阻塞**：将耗时操作移至异步协程中。
2. **合理使用 asyncio.create_task()**：当您不需要立即等待结果时，使用 create_task 创建后台任务。

3. **异常处理**：在异步函数中使用 try/except 处理异常，防止未捕获的异常导致应用崩溃。

   ```python
   async def safe_operation():
       try:
           await risky_operation()
       except Exception as e:
           print(f"Error occurred: {e}")
   ```

4. **取消任务**：在退出或不再需要时取消异步任务。

   ```python
   task = asyncio.create_task(some_coro())
   # 稍后取消
   task.cancel()
   ```

5. **避免同步阻塞**：异步函数中不要使用同步的阻塞操作（如 time.sleep()），而应使用 asyncio.sleep()。

## 限制与注意事项

1. QtAsyncio 是 Qt 事件循环和 asyncio 事件循环的集成，不是替代品。某些 asyncio 的高级特性可能需要额外配置。

2. 与其他异步框架的集成（如 Trio）需要额外工作。

3. 虽然 QtAsyncio 允许在 Qt 应用中使用异步编程，但仍然需要遵循 Qt 应用的最佳实践，例如在 UI 相关操作中遵循线程安全原则。

## 常见问题解决

### 问题：Qt 信号无法连接到异步函数

**解决方案**：使用 lambda 函数包装异步调用：

```python
button.clicked.connect(lambda: asyncio.ensure_future(async_function()))
```

### 问题：应用程序冻结

**解决方案**：确保耗时操作是异步的，且使用了 await 关键字：

```python
# 错误 - 会阻塞UI
async def long_operation():
    time.sleep(5)  # 同步阻塞

# 正确 - 不会阻塞UI
async def long_operation():
    await asyncio.sleep(5)  # 异步非阻塞
```

### 问题：异步函数未执行

**解决方案**：确保已使用 `asyncio.ensure_future()` 或 `asyncio.create_task()` 调度了异步函数，并且启动了事件循环：

```python
# 创建任务
asyncio.create_task(my_coroutine())

# 确保事件循环已启动
QtAsyncio.run(handle_sigint=True)
```

## 参考资料

- [PySide6 官方文档](https://doc.qt.io/qtforpython-6/)
- [Python asyncio 官方文档](https://docs.python.org/3/library/asyncio.html)
- [Qt 异步编程指南](https://doc.qt.io/qt-6/qtquick-threading.html)
