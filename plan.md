# TG-Manager QtAsyncio 迁移计划

## 目标

将 TG-Manager 应用程序中的所有视图从当前的异步实现方式迁移到使用 QtAsyncio，以实现 Qt 界面和 Python 异步编程的无缝集成。

## 背景

目前，应用程序已经在入口点（`run_ui.py`和`app.py`）尝试使用 QtAsyncio，但大部分视图组件仍在使用传统的 asyncio 方法，可能导致 Qt 事件循环和 asyncio 事件循环冲突。迁移到 QtAsyncio 将解决这些潜在问题，并提供更好的性能和用户体验。

## QtAsyncio 概述

[QtAsyncio](https://doc.qt.io/qtforpython-6/PySide6/QtAsyncio/index.html)是 PySide6 中的一个模块，它提供了 Qt 和 Python 的 asyncio 库之间的桥梁。它通过使用 Qt 事件循环来驱动异步操作，解决了两个事件循环并存的冲突问题。

### 核心特性

- 使用 Qt 的事件循环代替 asyncio 默认事件循环
- 提供与 asyncio 兼容的 API
- 支持异步任务、协程和事件处理
- 保持 Qt 界面响应性同时执行异步任务

## 迁移策略

### 1. 准备阶段

#### 1.1 依赖确认

- 确保 PySide6 版本 >= 6.5.0（包含 QtAsyncio 模块）
- 更新`requirements.txt`文件

```
PySide6>=6.5.0
```

#### 1.2 架构分析

- 标识所有使用 asyncio 的视图组件
- 对异步操作进行分类（网络请求、文件操作、定时任务等）
- 确定各组件之间的依赖关系

### 2. 基础设施升级

#### 2.1 应用入口点修改

- 确认`app.py`中的`run()`方法正确使用 QtAsyncio
- 添加全局异步初始化任务

```python
def run(self):
    """运行应用程序"""
    try:
        # 尝试使用 QtAsyncio 运行应用程序
        try:
            import PySide6.QtAsyncio as QtAsyncio
            logger.info("使用 QtAsyncio 运行应用程序")

            # 可以添加初始化异步任务
            async def init_async_components():
                # 初始化需要的异步组件
                await self._init_async_services()
                logger.info("异步组件初始化完成")

            # QtAsyncio.run() 接管事件循环
            return QtAsyncio.run(init_async_components(), handle_sigint=True)
        except (ImportError, AttributeError) as e:
            logger.info(f"QtAsyncio 不可用 ({e})，使用传统方式运行")
            return self.app.exec()
    except Exception as e:
        logger.error(f"应用程序运行失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1
```

#### 2.2 异步工具类创建

创建公共工具类`async_utils.py`封装常用异步操作，统一接口和错误处理：

```python
"""
异步操作工具模块
提供统一的异步操作接口和错误处理
"""

import asyncio
import PySide6.QtAsyncio as QtAsyncio
from functools import wraps
from typing import Callable, Any, Coroutine, TypeVar
from loguru import logger

T = TypeVar('T')

def create_task(coro: Coroutine) -> asyncio.Task:
    """创建异步任务

    使用QtAsyncio创建异步任务，并添加全局异常处理

    Args:
        coro: 协程对象

    Returns:
        asyncio.Task: 已创建的任务
    """
    task = QtAsyncio.asyncio.create_task(coro)
    task.add_done_callback(_handle_task_exception)
    return task

def _handle_task_exception(task):
    """处理任务异常

    Args:
        task: 异步任务
    """
    try:
        # 检查任务状态
        if task.cancelled():
            return

        # 获取异常（如果有）
        exception = task.exception()
        if exception:
            logger.error(f"异步任务出错: {exception}")
            # 异常详情记录到日志
            import traceback
            formatted_tb = ''.join(traceback.format_exception(
                type(exception), exception, exception.__traceback__))
            logger.debug(f"异常详情:\n{formatted_tb}")
    except asyncio.CancelledError:
        # 忽略取消错误
        pass
    except Exception as e:
        logger.error(f"处理任务异常时出错: {e}")

def qt_connect_async(signal, coro_func: Callable[..., Coroutine[Any, Any, T]]):
    """将Qt信号连接到异步函数

    Args:
        signal: Qt信号
        coro_func: 异步函数

    Returns:
        连接函数
    """
    @wraps(coro_func)
    def slot(*args, **kwargs):
        create_task(coro_func(*args, **kwargs))

    signal.connect(slot)
    return slot

async def safe_sleep(seconds: float) -> None:
    """安全的异步睡眠

    不会在取消时引发异常

    Args:
        seconds: 睡眠秒数
    """
    try:
        await asyncio.sleep(seconds)
    except asyncio.CancelledError:
        # 静默处理取消
        raise

class AsyncTimer:
    """异步定时器

    定期执行异步任务
    """
    def __init__(self, interval: float, callback: Callable[[], Coroutine]):
        self.interval = interval
        self.callback = callback
        self.task = None
        self.running = False

    async def _timer_loop(self):
        """定时器循环"""
        self.running = True
        try:
            while self.running:
                await self.callback()
                await safe_sleep(self.interval)
        except asyncio.CancelledError:
            self.running = False
            raise
        finally:
            self.running = False

    def start(self):
        """启动定时器"""
        if not self.running:
            self.task = create_task(self._timer_loop())

    def stop(self):
        """停止定时器"""
        if self.running and self.task:
            self.running = False
            self.task.cancel()
```

### 3. 组件迁移

#### 3.1 迁移顺序

按以下优先级顺序迁移视图组件：

1. 基础功能组件（首先确保基础设施工作正常）
2. 简单视图（如帮助视图、日志查看器视图）
3. 中等复杂度视图（如任务视图）
4. 复杂的核心功能视图（如下载、上传、转发视图）

#### 3.2 迁移步骤（每个视图）

1. **代码分析**：标识所有使用 asyncio 的位置

   - 查找`asyncio.get_event_loop()`调用
   - 查找`asyncio.create_task()`调用
   - 查找`asyncio.sleep()`、`asyncio.gather()`等

2. **替换 asyncio 导入**：

   ```python
   # 旧代码
   import asyncio

   # 新代码
   import asyncio
   import PySide6.QtAsyncio as QtAsyncio
   from src.utils.async_utils import create_task, qt_connect_async, safe_sleep
   ```

3. **替换事件循环获取和任务创建**：

   ```python
   # 旧代码
   loop = asyncio.get_event_loop()
   task = asyncio.create_task(coroutine())
   # 或
   task = loop.create_task(coroutine())

   # 新代码
   task = create_task(coroutine())
   # 或直接
   task = QtAsyncio.asyncio.create_task(coroutine())
   ```

4. **替换按钮点击连接到异步方法**：

   ```python
   # 旧代码
   self.button.clicked.connect(self._on_button_clicked)

   def _on_button_clicked(self):
       asyncio.create_task(self._async_method())

   # 新代码 - 方式1
   qt_connect_async(self.button.clicked, self._async_method)

   # 新代码 - 方式2
   self.button.clicked.connect(self._on_button_clicked)

   def _on_button_clicked(self):
       create_task(self._async_method())
   ```

5. **异常处理修改**：

   - 确保所有异步任务都有适当的`try/except`块处理`asyncio.CancelledError`
   - 使用`async_utils.py`中的工具函数进行统一的异常处理

6. **信号更新机制**：确保所有 UI 更新通过 Qt 信号机制完成

   ```python
   # 正确做法：使用信号
   self.update_signal.emit(data)

   # 避免直接在异步函数中更新UI
   # 错误做法:
   # await async_operation()
   # self.label.setText("结果")  # 直接更新UI，可能导致问题
   ```

7. **资源清理**：
   - 确保任务在视图关闭时被正确取消
   - 添加清理方法

#### 3.3 具体组件迁移计划

##### 帮助文档视图 (help_doc_view.py)

- 较简单，主要是文档加载和显示
- 预计工作量：低

##### 日志查看器视图 (log_viewer_view.py)

- 处理日志文件异步加载和筛选
- 预计工作量：中

##### 任务视图 (task_view.py)

- 涉及任务管理、统计和控制
- 预计工作量：中

##### 下载视图 (download_view.py)

- 涉及文件下载、进度管理和取消等复杂操作
- 预计工作量：高

##### 上传视图 (upload_view.py)

- 涉及文件上传、队列管理和错误处理
- 预计工作量：高

##### 转发视图 (forward_view.py)

- 涉及消息管理、频道交互和计划任务
- 预计工作量：高

##### 监听视图 (listen_view.py)

- 涉及实时监听、消息过滤和通知
- 预计工作量：高

### 4. 测试与验证

#### 4.1 单元测试

- 为每个迁移的视图创建专门的测试案例
- 测试异步操作是否正确执行
- 测试取消操作和异常处理

#### 4.2 集成测试

- 测试多个视图同时运行时的交互
- 测试应用程序启动和关闭过程

#### 4.3 性能测试

- 比较迁移前后的 UI 响应性能
- 测量任务执行时间和资源使用情况

### 5. 文档与培训

#### 5.1 更新文档

- 更新 README.md，添加 QtAsyncio 相关说明
- 更新开发指南，提供 QtAsyncio 使用的最佳实践

#### 5.2 代码注释

- 为所有迁移的代码添加清晰的注释
- 说明异步流程和注意事项

## 时间表

| 阶段     | 任务                                                | 估计时间  |
| -------- | --------------------------------------------------- | --------- |
| 准备     | 依赖更新和架构分析                                  | 1 天      |
| 基础设施 | 创建 async_utils.py 和修改应用入口                  | 1 天      |
| 迁移     | 简单视图迁移 (help_doc_view.py, log_viewer_view.py) | 2 天      |
| 迁移     | 中等复杂度视图 (task_view.py)                       | 2 天      |
| 迁移     | 复杂视图 (download_view.py, upload_view.py)         | 3 天      |
| 迁移     | 复杂视图 (forward_view.py, listen_view.py)          | 3 天      |
| 测试     | 单元测试、集成测试和修复问题                        | 3 天      |
| 文档     | 更新文档和代码注释                                  | 1 天      |
| **总计** |                                                     | **16 天** |

## 风险与缓解措施

| 风险                             | 可能性 | 影响 | 缓解措施                   |
| -------------------------------- | ------ | ---- | -------------------------- |
| QtAsyncio 不稳定（技术预览状态） | 中     | 高   | 提供备选方案，添加兼容层   |
| 复杂视图迁移困难                 | 中     | 中   | 增量迁移，保留部分传统实现 |
| 性能退化                         | 低     | 高   | 性能测试基准，及时发现问题 |
| 新 bug 引入                      | 中     | 中   | 全面的测试覆盖，回归测试   |
| API 变更                         | 低     | 高   | 使用兼容层隔离核心功能     |

## 成功标准

- 所有视图成功迁移到 QtAsyncio
- 无 UI 冻结或响应延迟
- 所有功能正常工作
- 异步操作可以正确取消
- 应用程序可以干净地关闭并释放资源
- 所有测试通过

## 回滚计划

如果迁移过程中遇到重大问题，我们将采取以下步骤回滚：

1. 保留原始代码分支
2. 维护兼容层，允许逐个组件回滚
3. 记录所有迁移中发现的问题，为未来尝试提供信息
