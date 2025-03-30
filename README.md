# TG-Manager

TG-Manager 是一个功能强大的 Telegram 消息管理工具，支持频道监听、消息转发、媒体下载与上传等功能。提供命令行和图形用户界面两种使用方式。

## 主要功能

- **媒体下载**：从 Telegram 频道下载媒体文件，支持多种格式、关键词过滤
- **媒体上传**：将本地媒体文件上传到 Telegram 频道，支持批量处理
- **实时监听**：监听频道和群组的新消息，支持关键词匹配和自动处理
- **任务管理**：支持任务暂停、继续和取消，提供进度追踪
- **消息转发**：在不同频道间智能转发消息和媒体，自动处理权限限制
- **资源管理**：高效管理文件资源，支持锁定和自动清理机制
- **图形界面**：提供基于 PySide6 的图形用户界面，支持所有核心功能
- **用户界面**：清晰的状态更新、进度显示和错误提示，完全分离的业务逻辑和 UI 交互

## 使用方式

### 图形用户界面

TG-Manager 提供直观易用的图形界面，可通过以下命令启动：

```bash
python run_ui.py
```

图形界面提供以下功能模块：

1. **下载界面**：配置频道和媒体类型，从Telegram频道下载媒体
2. **上传界面**：浏览本地文件，上传到指定Telegram频道
3. **转发界面**：设置转发规则，在不同频道之间转发消息
4. **监听界面**：实时监听频道消息，支持条件过滤
5. **任务管理**：查看和管理所有任务，支持暂停/继续操作
6. **设置界面**：配置API凭据、代理设置和全局选项

界面特点：
- 所有配置自动保存和加载
- 实时任务状态和进度显示
- 多任务并行处理
- 统一的错误处理和通知

界面组成：
- **菜单栏**：提供文件、视图、任务和帮助等菜单选项
- **工具栏**：包含登录、设置、任务管理器和日志查看器等快捷按钮
- **导航树**：左侧导航面板，提供功能模块的分类导航
- **任务概览**：左侧任务管理面板，显示任务统计和活跃任务列表，支持任务状态监控和任务管理操作
- **主内容区**：中央区域，根据选择的功能显示对应的界面

### 命令行界面

对于高级用户或自动化脚本，TG-Manager 也提供命令行界面：

```bash
# 下载示例
python -m src.modules.downloader --channel <channel_id> --output ./downloads

# 上传示例
python -m src.modules.uploader --files ./media/* --channel <channel_id>

# 更多命令行选项请参考文档
```

## 项目结构

```
TG-Manager/
├── src/                  # 源代码目录
│   ├── modules/          # 核心功能模块
│   │   ├── components/   # UI组件
│   │   ├── views/        # 功能视图
│   │   └── app.py        # 应用程序主类
│   ├── utils/            # 工具类和辅助函数
│   ├── examples/         # 使用示例
│   └── tests/            # 测试代码
├── config/               # 配置文件目录
├── docs/                 # 文档
├── run_ui.py             # 图形界面启动文件
└── README.md             # 项目说明
```

## 安装

1. 克隆项目并进入目录：
```bash
git clone https://github.com/yourusername/TG-Manager.git
cd TG-Manager
```

2. 安装依赖（推荐使用虚拟环境）：
```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

3. 配置Telegram API：
   - 访问 https://my.telegram.org/apps 获取API ID和API Hash
   - 将获取的凭据填入配置文件或通过设置界面配置

4. 运行应用：
```bash
# 启动图形界面
python run_ui.py

# 或使用命令行模式
python -m src.modules.downloader --help
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

转发管理器负责在不同的Telegram频道之间转发消息。

- 支持多种消息类型转发
- 提供访问权限校验
- 处理媒体文件的无损转发
- 支持定制转发规则

**使用示例**:

```python
from src.modules.forwarder import Forwarder

# 创建转发管理器
forwarder = Forwarder(client, config_manager, channel_resolver)

# 设置回调函数
forwarder.on("status", lambda status: print(f"状态: {status}"))
forwarder.on("forward_complete", lambda msg_id: print(f"转发完成: {msg_id}"))

# 开始转发（异步方法）
async def forward_example():
    # 设置源频道和目标频道
    source_channel = "source_channel_username"
    target_channel = "target_channel_username"
    
    # 转发最近的50条消息
    await forwarder.forward_messages(source_channel, target_channel, limit=50)
```

### 7. 监听器 (Monitor)

监听器用于实时监听Telegram频道和群组的新消息。

- 支持多频道并行监听
- 提供消息过滤和关键词匹配
- 事件驱动架构，支持自定义处理函数

**使用示例**:

```python
from src.modules.monitor import Monitor

# 创建监听器
monitor = Monitor(client, config_manager, channel_resolver)

# 自定义消息处理函数
async def handle_new_message(message):
    print(f"收到新消息: {message.text}")
    # 执行自定义处理逻辑

# 设置回调函数
monitor.on("new_message", handle_new_message)
monitor.on("status", lambda status: print(f"状态: {status}"))

# 开始监听（异步方法）
async def monitor_example():
    # 设置要监听的频道列表
    channels = ["channel1", "channel2", "group3"]
    
    # 开始监听
    await monitor.start_monitoring(channels)
    
    # 停止监听
    # await monitor.stop_monitoring()
```

### 8. UI状态管理器 (UIStateManager)

UI状态管理器用于在业务逻辑和UI之间传递状态。

- 提供状态订阅和更新机制
- 支持进度追踪和错误处理
- 确保UI和业务逻辑的完全分离

**使用示例**:

```python
from src.utils.ui_state_manager import UIStateManager

# 创建UI状态管理器
ui_state_manager = UIStateManager()

# 订阅状态更新
def on_download_progress(progress, total):
    percentage = (progress / total) * 100 if total > 0 else 0
    print(f"下载进度: {percentage:.1f}%")

# 注册回调
ui_state_manager.register("download_progress", on_download_progress)

# 更新状态
ui_state_manager.update("download_progress", 50, 100)  # 触发回调

# 取消订阅
ui_state_manager.unregister("download_progress", on_download_progress)
```

### 9. 图形界面组件

TG-Manager的图形界面基于PySide6开发，主要组件包括：

#### 主窗口 (MainWindow)

- 提供统一的应用程序窗口框架
- 集成导航树和任务概览
- 管理所有功能视图的切换

#### 导航树 (NavigationTree)

- 提供功能模块的层次化导航
- 支持自定义图标和分组
- 处理导航项的选择和激活

#### 功能视图

- **下载视图 (DownloadView)**: 配置和执行媒体下载任务
- **上传视图 (UploadView)**: 浏览和上传本地媒体文件
- **转发视图 (ForwardView)**: 设置和执行消息转发规则
- **监听视图 (ListenView)**: 配置实时频道监听
- **任务视图 (TaskView)**: 查看和管理当前任务
- **设置视图 (SettingsView)**: 配置应用程序设置

## 贡献

欢迎贡献代码或提出问题！请遵循以下步骤：

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## 许可证

该项目采用 MIT 许可证 - 详情请参阅 [LICENSE](LICENSE) 文件。

## 联系方式

如有问题或建议，请通过 [Issues](https://github.com/yourusername/TG-Manager/issues) 或电子邮件联系我们。
