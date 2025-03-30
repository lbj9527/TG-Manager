# TG-Manager

TG-Manager 是一个功能强大的 Telegram 消息管理工具，支持频道监听、消息转发、媒体下载与上传等功能。

## 主要功能

- **媒体下载**：从 Telegram 频道下载媒体文件，支持多种格式、关键词过滤
- **媒体上传**：将本地媒体文件上传到 Telegram 频道，支持批量处理
- **实时监听**：监听频道和群组的新消息，支持关键词匹配和自动处理
- **任务管理**：支持任务暂停、继续和取消，提供进度追踪
- **消息转发**：在不同频道间智能转发消息和媒体，自动处理权限限制
- **资源管理**：高效管理文件资源，支持锁定和自动清理机制
- **用户界面**：清晰的状态更新、进度显示和错误提示，完全分离的业务逻辑和 UI 交互

## 项目结构

```
TG-Manager/
├── src/                  # 源代码目录
│   ├── modules/          # 核心功能模块
│   ├── utils/            # 工具类和辅助函数
│   ├── examples/         # 使用示例
│   └── tests/            # 测试代码
├── config/               # 配置文件目录
├── docs/                 # 文档
└── README.md             # 项目说明
```

## 核心组件

### 1. 客户端管理器 (ClientManager)

客户端管理器负责初始化和管理 Telegram 客户端实例。

- 自动处理会话认证和令牌管理
- 提供连接状态监控和自动重连
- 支持多账户管理

**使用示例**:

```python
from src.utils.client_manager import ClientManager

# 创建客户端管理器
client_manager = ClientManager()

# 启动客户端（异步方法）
async def start():
    client = await client_manager.start()

    # 使用客户端执行操作
    me = await client.get_me()
    print(f"已登录账号: {me.first_name}")

    # 关闭客户端
    await client_manager.stop()
```

### 2. 配置管理器 (ConfigManager)

配置管理器用于加载、验证和访问应用程序配置。

- 支持多环境配置
- 配置验证和默认值
- 配置热重载

**使用示例**:

```python
from src.utils.config_manager import ConfigManager

# 创建配置管理器
config_manager = ConfigManager("config/config.json")

# 获取配置
general_config = config_manager.get_general_config()
download_config = config_manager.get_download_config()

# 使用配置
print(f"下载路径: {download_config.download_path}")
print(f"下载限制: {general_config.limit}")
```

### 3. 频道解析器 (ChannelResolver)

频道解析器用于解析和验证 Telegram 频道。

- 支持通过 ID、用户名或链接解析频道
- 缓存频道信息，提高性能
- 验证频道权限

**使用示例**:

```python
from src.utils.channel_resolver import ChannelResolver

# 创建频道解析器（需要客户端实例）
channel_resolver = ChannelResolver(client)

# 解析频道
async def resolve_example():
    # 支持多种格式：ID、用户名、链接
    channel_id = await channel_resolver.resolve_channel("telegram")

    # 获取格式化的频道信息
    info_str, (title, username) = await channel_resolver.format_channel_info(channel_id)
    print(f"频道信息: {info_str}")
```

### 4. 下载管理器 (Downloader)

下载管理器负责从 Telegram 频道下载媒体文件。

- 支持多种媒体类型（图片、视频、文档等）
- 关键词过滤和范围限制
- 断点续传和重复检测

**使用示例**:

```python
from src.modules.downloader import Downloader
from src.utils.controls import TaskContext

# 创建下载管理器
downloader = Downloader(client, config_manager, channel_resolver, history_manager)

# 设置回调函数
downloader.on("status", lambda status: print(f"状态: {status}"))
downloader.on("download_complete", lambda msg_id, filename, size: print(f"下载完成: {filename}"))

# 开始下载（异步方法）
async def download_example():
    # 创建任务上下文（支持暂停/取消）
    task_context = TaskContext()

    # 开始下载
    await downloader.download_media_from_channels(task_context)

    # 暂停/继续/取消示例
    task_context.pause_token.pause()  # 暂停
    task_context.pause_token.resume() # 继续
    task_context.cancel_token.cancel() # 取消
```

### 5. 上传管理器 (Uploader)

上传管理器负责将本地媒体文件上传到 Telegram 频道。

- 支持多种媒体类型
- 批量上传和进度追踪
- 自动处理大文件分片

**使用示例**:

```python
from src.modules.uploader import Uploader
from pathlib import Path

# 创建上传管理器
uploader = Uploader(client, config_manager, channel_resolver)

# 设置回调函数
uploader.on("status", lambda status: print(f"状态: {status}"))
uploader.on("upload_complete", lambda file_path, msg_id: print(f"上传完成: {file_path}"))

# 开始上传（异步方法）
async def upload_example():
    # 准备上传文件
    files = [
        Path("path/to/image.jpg"),
        Path("path/to/video.mp4"),
        Path("path/to/document.pdf")
    ]

    # 上传文件
    await uploader.upload_local_files(files)
```

### 6. 转发管理器 (Forwarder)

转发管理器负责在不同频道间转发消息和媒体。

- 智能处理权限限制
- 支持媒体组转发
- 提供转发历史记录

**使用示例**:

```python
from src.modules.forwarder import Forwarder

# 创建转发管理器
forwarder = Forwarder(
    client, config_manager, channel_resolver,
    history_manager, downloader, uploader
)

# 设置回调函数
forwarder.on("status", lambda status: print(f"状态: {status}"))
forwarder.on("message_forwarded", lambda msg_id, target: print(f"消息已转发: {msg_id} -> {target}"))

# 开始转发（异步方法）
async def forward_example():
    # 开始转发
    await forwarder.forward_messages()
```

### 7. 消息监听系统 (Monitor)

消息监听系统负责监听指定频道和群组的新消息。

- 实时消息监听和处理
- 消息过滤（关键词、类型等）
- 自动响应和转发
- 基于事件的架构
- 媒体处理和下载
- 消息统计和分析

**使用示例**:

```python
from src.modules.monitor import Monitor

# 创建监听管理器
monitor = Monitor(client, config_manager, channel_resolver)

# 添加消息处理器
async def handle_new_message(message):
    print(f"收到新消息，ID: {message.id}")
    if "测试" in (message.text or ""):
        print("检测到测试关键词!")

monitor.add_message_handler(handle_new_message)

# 开始监听（异步方法）
async def monitor_example():
    # 开始监听
    await monitor.start_monitoring()

    # 停止监听
    # monitor.stop_monitoring()
```

### 8. UI 状态管理系统 (UIStateManager)

UI 状态管理系统负责处理用户界面状态和更新，完全分离业务逻辑和界面交互。

- 基于事件的状态更新机制
- 统一的回调参数结构
- 支持进度、状态和错误处理
- 适配多种界面类型（控制台、GUI）

**使用示例**:

```python
from src.utils.ui_state import UICallback, StatusLevel

# 创建UI回调处理器
class MyUIHandler:
    def handle_update(self, data):
        # 根据状态级别处理不同类型的更新
        if data.level == StatusLevel.INFO:
            print(f"信息: {data.message}")
        elif data.level == StatusLevel.PROGRESS:
            print(f"进度: {data.progress:.1f}% - {data.message}")
        elif data.level == StatusLevel.ERROR:
            print(f"错误: {data.message} (类型: {data.error_type})")

# 创建回调实例
ui_callback = UICallback(MyUIHandler().handle_update)

# 在业务逻辑中使用
def process_task():
    # 发送状态更新
    ui_callback.info("开始处理任务")

    # 发送进度更新
    for i in range(10):
        ui_callback.progress(i * 10, f"处理第 {i+1} 步")

    # 发送完成或错误通知
    if success:
        ui_callback.success("任务完成")
    else:
        ui_callback.error("处理失败", error_type="PROCESS_ERROR")
```

### 9. 任务管理系统 (TaskManager)

任务管理系统提供对长时间运行任务的控制机制。

- 任务暂停/继续/取消
- 任务上下文和状态追踪
- 并发任务管理
- 与 UI 状态系统集成

**使用示例**:

```python
from src.utils.controls import TaskContext, PauseToken, CancelToken

# 创建任务上下文
task_context = TaskContext()

# 在异步函数中使用
async def long_running_task():
    # 执行任务的主循环
    for i in range(100):
        # 检查取消请求
        if task_context.cancel_token.is_cancelled:
            print("任务已取消")
            return

        # 处理暂停请求
        await task_context.wait_if_paused()

        # 执行实际工作
        print(f"步骤 {i}")
        await asyncio.sleep(0.1)

# 控制任务执行
async def control_task():
    # 启动任务
    task = asyncio.create_task(long_running_task())

    # 暂停任务
    task_context.pause_token.pause()
    print("任务已暂停")
    await asyncio.sleep(2)

    # 继续任务
    task_context.pause_token.resume()
    print("任务已继续")
    await asyncio.sleep(1)

    # 取消任务
    task_context.cancel_token.cancel()
    print("已请求取消任务")

    # 等待任务结束
    await task
```

### 10. 日志事件适配器 (LoggerEventAdapter)

日志事件适配器统一连接日志系统和事件系统，实现业务逻辑与界面输出的完全分离。

- 支持不同日志级别的事件发射
- 保留内部调试日志而不影响用户界面
- 统一的错误处理和报告机制
- 为 GUI 和 CLI 提供一致的接口

**使用示例**:

```python
from src.utils.events import EventEmitter
from src.utils.logger_event_adapter import LoggerEventAdapter

# 创建一个模块类，继承EventEmitter
class MyModule(EventEmitter):
    def __init__(self):
        super().__init__()
        # 创建日志事件适配器
        self.log = LoggerEventAdapter(self)

    async def process_task(self):
        # 发送状态更新（会同时记录日志并发射事件）
        self.log.status("开始处理任务")

        try:
            # 处理过程中的信息日志
            self.log.info("处理中间步骤")

            # 调试信息（只记录日志，不发送UI事件）
            self.log.debug("这是调试信息，不会显示在界面上")

            # 完成处理
            self.log.status("任务处理完成")

        except Exception as e:
            # 错误处理（带有错误类型和可恢复性信息）
            self.log.error(f"处理失败: {str(e)}",
                          error_type="PROCESS_ERROR",
                          recoverable=True)

# 使用模块
async def example():
    module = MyModule()

    # 注册事件监听器
    module.on("status", lambda msg: print(f"状态: {msg}"))
    module.on("info", lambda msg: print(f"信息: {msg}"))
    module.on("error", lambda msg, **kwargs: print(f"错误: {msg} (类型: {kwargs['error_type']})"))

    # 运行处理任务
    await module.process_task()
```

## 系统架构特点

### 业务逻辑与界面分离

TG-Manager 采用了严格的业务逻辑与界面分离设计，这使得系统既可以作为命令行工具使用，也可以轻松集成到各种图形界面中。这种分离是通过以下几个关键组件实现的：

#### 1. 事件驱动架构

- **EventEmitter 基类**：所有核心模块都继承自 `EventEmitter`，通过事件机制而非直接输出与外界交互
- **统一事件类型**：标准化的事件类型如 `status`、`progress`、`error`、`complete` 等，确保一致的通信方式
- **事件监听和处理**：任何组件都可以监听和响应事件，无需直接依赖

#### 2. 日志与界面消息分离

- **LoggerEventAdapter**：连接日志系统和事件系统的适配器，实现同一消息的双重处理
- **消息分级处理**：
  - `debug` 级别消息仅用于内部调试，不发送到界面
  - `info`、`status`、`warning`、`error` 等消息同时发送到日志系统和事件系统
- **统一的错误报告**：详细的错误类型、可恢复性指示和上下文信息

#### 3. UI 回调系统

- **UICallback 接口**：提供标准化的界面更新方法，无论前端是什么类型
- **UIState 管理**：集中式状态管理，支持组件间的状态共享和变化通知
- **EventToUIAdapter**：自动将事件系统的消息转发到 UI 回调系统

#### 4. 任务控制机制

- **TaskContext**：封装任务执行上下文，包括取消和暂停控制
- **CancelToken 与 PauseToken**：提供细粒度的任务控制，支持外部中断
- **TaskManager 与 TaskScheduler**：高级任务管理系统，支持优先级和资源控制

#### 5. 实现示例

下图展示了系统中业务逻辑与界面交互的分离流程：

```
┌────────────────┐    事件发射     ┌────────────────┐
│                │───────────────> │                │
│  业务逻辑模块   │                 │   EventEmitter  │
│ (Downloader等) │ <───────────────│                │
└────────────────┘    状态更新     └────────────────┘
         │                                   │
         │ 发出事件                          │ 传递事件
         ▼                                   ▼
┌────────────────┐                 ┌────────────────┐
│                │                 │                │
│LoggerEventAdapter│───────────────> │ EventToUIAdapter │
│                │                 │                │
└────────────────┘                 └────────────────┘
         │                                   │
         │ 记录日志                          │ 更新UI
         ▼                                   ▼
┌────────────────┐                 ┌────────────────┐
│                │                 │                │
│   日志系统      │                 │  UI回调系统    │
│                │                 │                │
└────────────────┘                 └────────────────┘
                                            │
                                            │
                                            ▼
                                   ┌────────────────┐
                                   │                │
                                   │ 用户界面(CLI/GUI)│
                                   │                │
                                   └────────────────┘
```

#### 6. 迁移到图形界面的路径

基于当前架构，开发图形界面只需以下几个步骤：

1. 选择合适的 UI 框架（PyQt、PySide 等）
2. 实现 `UICallback` 接口，连接 UI 控件
3. 连接事件系统到 UI 更新逻辑
4. 设计并实现各功能模块对应的界面组件
5. 构建任务控制界面，连接到任务管理系统

这种架构确保无论界面如何变化，核心业务逻辑保持稳定，同时提供了高度的灵活性和可扩展性。

## 安装和配置

1. 克隆项目仓库

```bash
git clone https://github.com/yourusername/TG-Manager.git
cd TG-Manager
```

2. 安装依赖

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

3. 配置应用

创建 `config/config.json` 文件，填入必要配置：

```json
{
  "GENERAL": {
    "api_id": "YOUR_API_ID",
    "api_hash": "YOUR_API_HASH",
    "limit": 20,
    "pause_time": 5
  },
  "DOWNLOAD": {
    "download_path": "downloads",
    "limit": 100,
    "download_delay": 1,
    "max_file_size": 100,
    "exclude_types": ["voice"]
  },
  "UPLOAD": {
    "target_channels": ["channel_username"],
    "caption_template": "{filename}"
  },
  "FORWARD": {
    "source_channels": ["source_channel"],
    "target_channels": ["target_channel"],
    "tmp_path": "temp"
  },
  "MONITOR": {
    "channels": ["channel_to_monitor"],
    "keywords": ["关键词1", "关键词2"]
  }
}
```

4. 运行示例

```bash
python -m src.examples.download_example
```

## 高级用法

请参阅 `docs/` 目录下的详细文档。
