# TG-Manager

TG-Manager 是一个功能强大的 Telegram 消息管理工具，支持频道监听、消息转发、媒体下载与上传等功能。提供命令行和图形用户界面两种使用方式。

## 近期更新

### 1.9.29 (2025-06-05)

- **上传模块功能增强**：添加了上传完成后发送最后一条消息的功能，支持 HTML 格式文本
- **上传界面优化**：移除了"使用自定义作为说明文字模板"功能，简化了界面设计
- **HTML 消息支持**：新增对表情符号、超链接和富文本格式的支持

### 1.9.25 (2025-05-25)

- **同义关键词配置修复**：修复了同义关键词在配置保存时的问题，确保正确处理"关键词 1-关键词 2-关键词 3"格式的关键词组

### 1.9.24 (2025-05-24)

- **同义关键词支持**：添加了支持同义关键词的功能，使用横杠"-"分隔同义词
- **关键词下载优化**：完善关键词匹配机制，支持多个同义词匹配同一关键词组
- **目录结构灵活性**：同义关键词匹配时自动使用完整同义词组作为目录名

### 1.9.23 (2025-05-22)

- **文件结构优化**：统一了常规下载和关键词下载的目录结构，确保文件始终保存在正确的频道子目录中
- **信息文件简化**：移除了冗余的`channel_info.txt`文件，简化`title.txt`仅保留标题信息
- **目录处理逻辑重构**：优化了目录创建逻辑，确保在所有下载模式下正确创建频道目录
- **变量处理改进**：改进了目录路径变量处理，特别是关键词模式下的路径处理
- **处理逻辑标准化**：统一了媒体组和单独消息的处理逻辑，保持一致的目录结构

### 1.9.20 (2025-05-12)

- **初始化状态界面管理**：添加程序启动过程中的初始化状态管理，在初始化过程中显示状态提示并禁用界面操作
- **错误修复**：解决程序未全部初始化完成时用户点击导航树模块导致的错误问题
- **用户体验改进**：通过状态栏背景颜色变化和文字提示，提供明确的初始化过程视觉反馈
- **界面状态管理优化**：添加统一的界面初始化状态管理方法，提高界面响应稳定性

### 1.9.19 (2025-05-10)

- **应用代码重构**：将大型的`app.py`文件拆分为多个模块化文件，使代码更易于维护
- **架构优化**：通过合理的模块化设计，减少了各组件之间的紧耦合
- **错误修复**：修复了`ThemeManagerWrapper`类中缺少`get_current_theme_name`方法的问题

### 1.9.18 (2025-05-08)

- **登录功能优化**：改进首次登录体验，添加自动引导和友好的指导对话框
- **验证码输入界面增强**：优化验证码输入流程，增加格式限制和智能按钮状态控制
- **登录状态反馈改进**：提供更详细的登录状态反馈，及时更新 UI 界面显示
- **异步登录流程优化**：完善登录过程中的异常处理机制，确保线程安全和 UI 响应性

### 1.9.17 (2025-05-05)

- **数据库锁定错误修复**：解决"database is locked"错误问题，添加自动修复机制和用户提示
- **客户端恢复机制增强**：优化客户端停止和重启流程，减少资源泄漏，提高应用稳定性
- **智能错误处理**：新增错误追踪系统，及时识别并处理持续出现的数据库锁定问题

### 1.9.16 (2025-05-02)

- **状态栏显示问题修复**：彻底解决了代理断开后状态栏客户端状态不更新的问题
- **连接管理机制优化**：增强了代理错误检测能力，添加超时处理，提高网络状态变化响应速度
- **UI 体验改进**：优化了状态栏显示效果，断开连接时使用红色高亮提示，更直观地反映连接状态

### 1.9.15 (2025-04-30)

- **代理连接管理优化**：修复代理断开时状态栏不更新问题，改进代理连接恢复后的自动重连机制
- **网络状态检测增强**：优化网络连接状态检测频率，提高系统对网络变化的响应速度
- **代理配置处理改进**：客户端重启时自动刷新代理配置，确保始终使用最新设置

### 1.9.14 (2025-04-28)

- **移除网络延时显示功能**：从状态栏中移除了网络延时显示功能，保留客户端连接状态功能
- **界面精简**：优化状态栏布局，提供更简洁的用户界面

### 1.9.13 (2025-04-26)

- **任务统计优化**：优化了状态栏中的任务统计显示，提供更直观的任务状态反馈
- **资源监控改进**：改进 CPU 和内存使用率显示，更新更及时

### 1.9.12 (2025-04-25)

- **用户界面简化与优化**：移除任务概览组件中的任务计数器部分，避免与状态栏中的任务统计信息重复，优化任务列表显示区域，为活动任务提供更多展示空间
- **任务组件协同改进**：增强了 TaskView 类中的任务统计功能，实现任务视图和状态栏的实时数据同步，优化了任务添加和移除逻辑，确保 UI 状态一致性

### 1.9.11 (2025-04-22)

- **状态栏信息增强**：新增任务统计信息实时显示功能，在状态栏动态展示运行中、等待中和已完成的任务数量，并根据任务状态自动调整显示颜色，提供更直观的视觉反馈
- **任务状态管理改进**：优化任务操作方法（暂停、恢复、取消），确保操作后状态统计自动更新，并实现了任务状态在多个视图组件间的同步
- **应用关闭优化**：增强应用关闭时的资源清理流程，确保所有定时器和任务得到妥善处理，提高程序稳定性

### 1.9.10 (2025-04-20)

- **视图加载错误修复**：修复主窗口 `get_view` 方法导致的视图加载错误，重构视图获取逻辑，确保延迟加载视图时能正确获取，提高应用在视图尚未创建时的健壮性

### 1.9.8 (2025-04-17)

- **从 QtAsyncio 迁移到 qasync**：移除对 PySide6.QtAsyncio 的依赖，改用 qasync 库实现 Qt 与 asyncio 的集成，修复了网络连接功能（`QAsyncioEventLoop.create_connection()`）未实现的问题
- **重构异步工具模块**：优化`async_utils.py`，提供更稳定的 Qt 和 asyncio 集成，完善事件循环初始化和运行逻辑
- **增强错误处理**：添加更完善的事件循环管理和异常处理机制，确保系统在各种情况下的稳定运行
- **添加测试工具**：提供`test_qasync.py`测试脚本，验证异步任务创建和网络请求功能

### 1.9.7 (2025-04-15)

- **核心服务集成**：将`run.py`中的核心服务（客户端管理、配置系统、日志等）完全集成到图形界面程序中，确保所有核心服务支持 QtAsyncio
- **功能组件集成**：在`TGManagerApp`类中集成了所有核心功能组件，实现了下载、上传、转发和监听模块的完整功能，并将这些功能模块连接到相应的视图组件
- **应用初始化优化**：重构异步运行流程，确保各服务以正确的顺序启动，提高应用稳定性和响应性

### 1.9.2 (2025-04-10)

- **多协程并发演示功能修复**：修复了 QtAsyncio 测试模块中点击"停止演示"后素数计算任务仍在后台运行的问题，完善了任务管理机制，确保所有子任务能够被正确取消
- **应用关闭逻辑优化**：修复了应用程序关闭时出现的"Event loop is already running"错误，优化了事件循环处理逻辑，提高了应用程序关闭过程的稳定性

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

### 2025-04-11

- 修复了拖动工具栏时频繁保存配置的问题，现在拖动过程中不会触发多次保存，只在拖动结束后保存一次
- 添加了防抖功能，避免短时间内重复保存窗口状态，提高应用响应性能
- 优化了 UI 事件处理机制，减少了不必要的配置文件写入操作

### 2025-04-10

- 重构主窗口代码，将单一的大型 MainWindow 类拆分为多个功能模块
- 使用混入类(Mixin)模式提高代码可维护性
- 改进了工具栏和状态栏功能

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

## 安装与运行

### 安装依赖

```bash
# 使用清华大学镜像源加速下载
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 运行 GUI 版本

```bash
python run_ui.py
```

### 运行 qasync 测试

如果需要测试 qasync 与 Qt 的集成情况，可以运行：

```bash
python test_qasync.py
```

这将启动一个简单的测试窗口，可以验证 Qt 与 asyncio 事件循环的集成情况，以及测试网络请求是否能正常工作。

### 重要更新说明

本项目已从使用 QtAsyncio 迁移到 qasync，主要原因是 QtAsyncio 没有完全实现网络连接功能（`QAsyncioEventLoop.create_connection()`未实现）。qasync 库提供了更完整的 Qt 与 asyncio 集成支持。

更新内容包括：

1. 将所有 QtAsyncio 引用替换为 qasync
2. 重构异步工具模块，提供更稳定的 Qt 和 asyncio 集成
3. 优化事件循环初始化和运行逻辑
4. 增强错误处理和回退机制

如果您在使用过程中遇到任何问题，请参考测试脚本或查阅 qasync 文档。

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

## 下载模块

### 下载器组件

- `Downloader`: 原始下载器类，负责从 Telegram 频道下载媒体文件
- `EventEmitterDownloader`: 下载器包装类，提供 Qt Signal 支持，兼容 UI 层的信号槽机制
  - 包装了原始的 Downloader 类
  - 提供了以下信号:
    - `status_updated(str)`: 状态更新信号
    - `progress_updated(int, int, str)`: 进度更新信号 (当前, 总数, 文件名)
    - `download_completed(int, str, int)`: 下载完成信号 (消息 ID, 文件名, 文件大小)
    - `all_downloads_completed()`: 所有下载完成信号
    - `error_occurred(str, str)`: 错误信号 (错误信息, 错误详情)
  - 自动转发所有方法调用到原始下载器
  - 兼容 emit 和事件监听器接口

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

## 项目架构

TG-Manager 使用模块化设计，由以下几个核心组件组成：

### 事件处理基础设施

- `BaseEventEmitter`: 所有事件发射器的基类，提供 Qt Signal 支持的基础设施
  - 定义了基本信号如`status_updated`和`error_occurred`
  - 提供了与原始模块的集成机制
  - 实现了事件类型到信号名称的自动映射

### 核心功能模块

- **下载模块**:

  - `Downloader`: 原始下载器类，负责从 Telegram 频道下载媒体文件
  - `EventEmitterDownloader`: 下载器包装类，提供 Qt Signal 支持
    - 信号: `status_updated`, `progress_updated`, `download_completed`, `all_downloads_completed`, `error_occurred`

- **上传模块**:

  - `Uploader`: 原始上传器类，负责将本地文件上传到 Telegram 频道
  - `EventEmitterUploader`: 上传器包装类，提供 Qt Signal 支持
    - 信号: `status_updated`, `progress_updated`, `upload_completed`, `media_uploaded`, `error_occurred`

- **转发模块**:

  - `Forwarder`: 原始转发器类，负责转发消息从源频道到目标频道
  - `EventEmitterForwarder`: 转发器包装类，提供 Qt Signal 支持
    - 信号: `status_updated`, `progress_updated`, `info_updated`, `warning_updated`, `debug_updated`, `forward_completed`, `message_forwarded`, `media_group_forwarded`, `error_occurred`等

- **监听模块**:
  - `Monitor`: 原始监听器类，负责监听频道消息和实时转发
  - `EventEmitterMonitor`: 监听器包装类，提供 Qt Signal 支持
    - 信号: `status_updated`, `message_received`, `keyword_matched`, `message_processed`, `monitoring_started`, `monitoring_stopped`, `error_occurred`等

### UI 组件

各个 UI 组件通过信号和槽连接到对应的功能模块，实现交互和状态更新：

- **下载视图** (`DownloadView`): 下载历史消息中的媒体文件
- **上传视图** (`UploadView`): 将本地文件上传到目标频道
- **转发视图** (`ForwardView`): 在不同频道间转发消息和媒体
- **监听视图** (`ListenView`): 实时监听并转发新消息

## 设计模式

TG-Manager 实现采用了多种设计模式：

- **装饰器模式**: 使用事件发射器类包装原始功能模块，增强其功能而不修改原始代码
- **观察者模式**: 通过 Qt 的信号槽机制实现 UI 和核心模块的松耦合
- **工厂模式**: 在初始化过程中创建和配置各种组件
- **命令模式**: 使用任务上下文管理长时间运行的操作
