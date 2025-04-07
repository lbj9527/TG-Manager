# TG-Manager

TG-Manager 是一个功能强大的 Telegram 消息管理工具，支持频道监听、消息转发、媒体下载与上传等功能。提供命令行和图形用户界面两种使用方式。

## 近期更新

### 1.9.1 (2025-04-10)

- **配置管理系统完全统一**：完成所有模块从`ConfigManager`到`UIConfigManager`的迁移，包括上传模块、转发模块和监听模块，确保配置管理的一致性和简洁性
- **模块初始化过程优化**：重构各功能模块的初始化过程，统一配置访问方式，提高代码可维护性

### 1.9.0 (2025-04-09)

- **配置管理系统优化**: 移除了`UIConfigManager`中未使用的兼容方法，统一采用更直接的配置访问模式，简化了配置处理流程。
- **项目集成计划完善**: 更新了`ui_assembly_plan.md`文件中的配置管理系统统一部分，提供了更清晰的配置获取示例代码。

### 1.8.9 版本更新 (2025-04-08)

- **配置管理系统完全统一**: 完成了将所有模块从`ConfigManager`到`UIConfigManager`的迁移工作，包括更新了`downloader.py`模块，并为其他模块准备了迁移方案。
- **项目集成计划文档更新**: 更新了`ui_assembly_plan.md`文件，详细记录了配置管理系统统一的实施过程，添加了每个模块的具体迁移步骤和代码示例。

### 1.8.8 版本更新 (2025-04-07)

- **配置管理系统统一**: 所有模块现在统一使用 `UIConfigManager` 进行配置管理，不再使用 `ConfigManager`。这一变更简化了配置架构，提高了代码可维护性，并确保 UI 界面与核心功能模块之间的配置一致性。
- **配置工具优化**: 新增 `config_utils.py` 工具模块，提供配置转换功能，使各模块能够以统一的方式处理配置数据。

详细更新内容请查看 [CHANGELOG.md](CHANGELOG.md)。

## 主要功能

- **媒体下载**：从 Telegram 频道下载媒体文件，支持多种格式、关键词过滤
- **媒体上传**：将本地媒体文件上传到 Telegram 频道，支持批量处理
- **实时监听**：监听频道和群组的新消息，支持关键词匹配和自动处理
- **任务管理**：支持任务暂停、继续和取消，提供进度追踪
- **消息转发**：在不同频道间智能转发消息和媒体，自动处理权限限制
- **资源管理**：高效管理文件资源，支持锁定和自动清理机制
- **图形界面**：提供基于 PySide6 的图形用户界面，支持所有核心功能
- **用户界面**：清晰的状态更新、进度显示和错误提示，完全分离的业务逻辑和 UI 交互

## 配置说明

TG-Manager 使用 JSON 配置文件来存储应用设置。默认配置文件为项目根目录下的 `config.json`。项目中提供了 `config_example.json` 作为示例配置，您可以复制并根据需要修改。

### 配置文件自动创建

从版本 1.8.4 开始，TG-Manager 支持自动创建默认配置文件。当您首次启动程序或配置文件不存在时，程序会自动创建一个包含所有必要配置项的 `config.json` 文件。默认配置包含示例值和占位符，您可以通过程序的设置界面轻松修改这些值：

1. 启动 TG-Manager
2. 进入设置界面（点击工具栏上的设置图标或在文件菜单中选择"设置"）
3. 在设置界面中填写您的 Telegram API ID 和 API Hash，以及其他必要设置
4. 点击"保存设置"按钮应用更改

自动创建的配置文件包含完整的结构，即使某些配置项具有默认的占位符值，程序仍然可以正常启动，让您能够通过界面配置各项功能。

### 配置文件权限问题

如果程序在启动或运行过程中检测到配置文件(`config.json`)为只读或无法写入，将会显示一个错误对话框，提示权限错误并给出解决建议。您可以尝试以下方法解决：

1. **修改文件权限**：右键点击 `config.json` 文件 -> 属性 -> 取消勾选"只读"属性
2. **以管理员身份运行程序**：右键点击程序图标 -> 以管理员身份运行
3. **移动程序**：将整个程序移动到您有完全访问权限的目录

程序检测到权限问题时会立即退出，您需要修复问题后重新启动程序。

## 配置文件结构

配置文件`config.json`的主要结构如下：

```json
{
  "GENERAL": {
    "api_id": 123456, // Telegram API ID
    "api_hash": "your_api_hash_here", // Telegram API Hash
    "phone_number": "+123456789", // Telegram账号手机号码
    "limit": 50, // 每次请求的消息限制数
    "pause_time": 60, // 操作间隔时间(秒)
    "timeout": 30, // 请求超时时间(秒)
    "max_retries": 3, // 最大重试次数
    "proxy_enabled": false, // 是否启用代理
    "proxy_type": "SOCKS5", // 代理类型
    "proxy_addr": "127.0.0.1", // 代理地址
    "proxy_port": 1080, // 代理端口
    "proxy_username": null, // 代理用户名(可选)
    "proxy_password": null, // 代理密码(可选)
    "auto_restart_session": true // 会话控制：Telegram会话在意外断开后是否自动重连(默认为true)
  },
  "DOWNLOAD": {
    "downloadSetting": [
      // 下载设置列表
      {
        "source_channels": "@channel1", // 源频道
        "start_id": 0, // 起始消息ID (0表示从最新消息开始)
        "end_id": 0, // 结束消息ID (0表示下载到最早消息)
        "media_types": ["photo", "video", "document", "audio", "animation"], // 要下载的媒体类型
        "keywords": ["关键词1", "关键词2"] // 关键词列表(用于关键词下载模式)
      }
    ],
    "download_path": "downloads", // 下载文件保存路径
    "parallel_download": false, // 是否启用并行下载
    "max_concurrent_downloads": 10 // 最大并发下载数
  },
  "UPLOAD": {
    "target_channels": ["@target_channel1", "@target_channel2"], // 目标频道列表
    "directory": "uploads", // 上传文件目录
    "caption_template": "{filename} - 上传于 {date}", // 说明文字模板
    "delay_between_uploads": 0.5, // 上传间隔时间(秒)
    "options": {
      // 上传选项
      "use_folder_name": true, // 是否使用文件夹名称作为说明文字
      "read_title_txt": false, // 是否读取title.txt文件作为说明文字
      "use_custom_template": false, // 是否使用自定义模板
      "auto_thumbnail": true // 是否自动生成视频缩略图
    }
  },
  "FORWARD": {
    "forward_channel_pairs": [
      // 转发频道对列表
      {
        "source_channel": "@source_channel1", // 源频道
        "target_channels": ["@target_channel1", "@target_channel2"] // 目标频道列表
      }
    ],
    "remove_captions": false, // 是否移除媒体说明文字
    "hide_author": false, // 是否隐藏原作者
    "media_types": ["photo", "video", "document", "audio", "animation"], // 要转发的媒体类型
    "forward_delay": 0.1, // 转发间隔时间(秒)
    "start_id": 0, // 起始消息ID
    "end_id": 0, // 结束消息ID
    "tmp_path": "tmp" // 临时文件路径
  },
  "MONITOR": {
    "monitor_channel_pairs": [
      // 监听频道对列表
      {
        "source_channel": "@source_channel1", // 源频道
        "target_channels": ["@target_channel1", "@target_channel2"], // 目标频道列表
        "remove_captions": false, // 是否移除媒体说明文字
        "text_filter": [
          // 文本替换规则
          {
            "original_text": "要替换的文本",
            "target_text": "替换后的文本"
          }
        ]
      }
    ],
    "media_types": ["photo", "video", "document", "audio", "animation", "sticker", "voice", "video_note"], // 要监听的媒体类型
    "duration": "2099-12-31", // 监听截止日期
    "forward_delay": 1.0 // 转发间隔时间(秒)
  },
  "UI": {
    "theme": "深色主题", // 界面主题
    "confirm_exit": true, // 退出时是否需要确认
    "minimize_to_tray": true, // 是否最小化到系统托盘
    "start_minimized": false, // 是否以最小化状态启动
    "enable_notifications": true, // 是否启用通知
    "notification_sound": true // 是否启用通知声音
  }
}
```

### GENERAL 部分

GENERAL 部分包含应用程序的基本设置，包括：

- Telegram API 凭据：`api_id`和`api_hash`
- 代理设置：`proxy_enabled`、`proxy_type`、`proxy_addr`等
- 基本操作参数：`limit`、`pause_time`、`timeout`等
- 会话控制：`auto_restart_session`控制 Telegram 会话在意外断开后是否自动重连(默认为 true)

### 频道标识格式

TG-Manager 支持以下几种格式的频道标识：

- **用户名格式**：`@username`，例如 `@telegram`
- **链接格式**：`https://t.me/username`，例如 `https://t.me/telegram`
- **ID 格式**：数字 ID，例如 `-1001234567890`
- **对话链接**：`https://t.me/c/1234567890`

### 媒体类型

以下是支持的媒体类型列表：

- `photo`: 图片
- `video`: 视频
- `document`: 文档文件
- `audio`: 音频
- `animation`: 动画 (GIF)
- `sticker`: 贴纸
- `voice`: 语音消息
- `video_note`: 圆形视频消息
- `text`: 纯文本消息

## 使用方式

### 图形用户界面

TG-Manager 提供直观易用的图形界面，可通过以下命令启动：

```bash
python run_ui.py
```

图形界面提供以下功能模块：

1. **下载界面**：配置频道和媒体类型，从 Telegram 频道下载媒体
2. **上传界面**：浏览本地文件，上传到指定 Telegram 频道
   - 支持选择上传目录：可以通过界面浏览按钮选择上传文件所在的目录
   - 目录路径持久化：用户选择的上传目录会保存在配置中，下次启动时自动加载
   - 文件浏览器：基于选定目录显示文件列表，可以选择多个文件添加到上传队列
   - 上传选项：支持设置说明文字模板、上传延迟和自动生成视频缩略图等功能
   - 实时进度跟踪：上传过程中显示当前文件进度、速度和剩余时间
3. **历史转发界面**：设置频道对，在不同频道之间转发消息
   - 频道配置：配置源频道和目标频道对，支持多个目标频道
   - 转发选项：设置是否移除说明文字、隐藏原作者，选择媒体类型等
   - 消息 ID 范围：支持设置起始 ID 和结束 ID，精确控制转发范围
   - 实时状态跟踪：显示每个频道对的转发状态和进度
   - 配置持久化：自动保存在 config.json 的 FORWARD 部分
4. **监听界面**：实时监听频道消息，支持条件过滤
   - 频道配置：添加源频道和目标频道对，支持多个目标频道
   - 文本替换：为每个频道对配置文本替换规则，自动替换消息中的特定文本
   - 监听选项：配置媒体类型、转发延迟和监听截止日期
   - 消息展示：按频道分组显示消息，自动限制最大显示消息数
   - 界面优化：采用标签页布局，与历史转发界面保持一致的设计风格
   - 配置持久化：自动保存在 config.json 的 MONITOR 部分，完全符合 UIMonitorConfig 结构
5. **任务管理**：查看和管理所有任务，支持暂停/继续操作
6. **设置界面**：配置 API 凭据、代理设置和全局选项

界面特点：

- 所有配置自动保存和加载
- 实时任务状态和进度显示
- 多任务并行处理
- 统一的错误处理和通知

界面组成：

- **菜单栏**：提供文件（包含登录、设置和退出）、配置（包含导入和导出）、工具和视图等菜单选项
- **工具栏**：包含登录、返回主页、设置、任务管理器和日志查看器等快捷按钮
- **导航树**：左侧导航面板，提供功能模块的分类导航，包括媒体下载、媒体上传、消息转发、消息监听、任务管理和系统工具（日志查看器、帮助文档）
- **任务概览**：左侧任务管理面板，显示任务统计和活跃任务列表，支持任务状态监控和任务管理操作
- **主内容区**：中央区域，根据选择的功能显示对应的界面

#### 系统托盘功能

TG-Manager 支持系统托盘操作，可以在不占用任务栏空间的情况下在后台运行。系统托盘功能包括：

- **最小化到托盘**：在设置界面启用后，最小化窗口时会自动隐藏到系统托盘
- **启动时最小化**：在设置界面启用后，程序启动时会自动以托盘图标形式运行，不显示主窗口
  - 注意：此功能需要同时启用"最小化到托盘"选项才能生效
  - 适用场景：服务器自启动、开机自启、需要在后台长期运行的场景
- **托盘操作**：右键点击托盘图标可以打开菜单，包含"显示主窗口"和"退出"选项
- **快速恢复**：双击托盘图标可以快速显示主窗口

要启用这些功能，请前往：设置 -> 界面 -> 行为设置，勾选对应选项。

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

3. 配置 Telegram API：

   - 访问 https://my.telegram.org/apps 获取 API ID 和 API Hash
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

转发管理器负责在不同的 Telegram 频道之间转发消息。

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

监听器用于实时监听 Telegram 频道和群组的新消息。

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

### 8. UI 状态管理器 (UIStateManager)

UI 状态管理器用于在业务逻辑和 UI 之间传递状态。

- 提供状态订阅和更新机制
- 支持进度追踪和错误处理
- 确保 UI 和业务逻辑的完全分离

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

TG-Manager 的图形界面基于 PySide6 开发，主要组件包括：

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
- **设置视图 (SettingsView)**: 提供应用程序配置管理界面，包含以下选项卡：
  - **API 设置**：配置 Telegram API ID 和 API Hash 等凭证信息
  - **网络代理**：配置网络代理设置，仅支持 SOCKS5 代理类型
  - **界面**：配置应用程序界面主题、行为和通知设置

每个功能模块（下载、上传、转发等）的专有设置都集成在各自的功能界面中，以提供更直接和上下文相关的设置体验。设置视图支持实时主题预览，但仅在点击"保存设置"按钮后才会永久应用主题更改。

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
