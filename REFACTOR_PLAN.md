# TG-Manager 插件化重构计划

## 项目概述

本重构计划旨在将现有的TG-Manager项目重构为基于Pyrogram智能插件的模块化架构，同时保持所有原有功能不变。

## 重构目标

1. **完善的客户端管理**：实现完善的用户登录流程，客户端自动重连功能
2. **插件化架构**：使用Pyrogram智能插件系统重构项目，合理封装程序功能
3. **抽象化设计**：将下载和上传功能抽象化，四大业务模块（下载、上传、转发、监听）都基于下载和上传这两个抽象类，特殊功能使用继承和多态
4. **模块化代码**：减少重复代码，消息获取、频道验证都使用统一的文件管理
5. **渐进式重构**：不修改原有代码，在根目录下新建文件夹，所有重构代码、文件、文件夹均放在此目录下
6. **功能一致性**：保证下载、上传、转发、监听等所有本项目的原有功能不变
7. **UI界面一致性**：UI界面保持和原项目一致
8. **测试驱动**：每重构一部分，编写测试，保证与原功能一致

## 目录结构

```
TG-Manager/
├── refactor/                    # 重构代码根目录
│   ├── README.md               # 重构说明文档
│   ├── requirements.txt        # 重构项目依赖
│   ├── main.py                 # 重构项目入口
│   ├── config/                 # 配置管理
│   │   ├── __init__.py
│   │   ├── config_manager.py   # 配置管理器
│   │   ├── plugin_config.py    # 插件配置
│   │   ├── ui_config_manager.py # UI配置管理器
│   │   ├── ui_config_models.py # UI配置模型
│   │   └── config_utils.py     # 配置工具
│   ├── core/                   # 核心模块
│   │   ├── __init__.py
│   │   ├── client_manager.py   # 客户端管理器（完善的登录流程和自动重连）
│   │   ├── plugin_manager.py   # 插件管理器
│   │   ├── event_bus.py        # 事件总线
│   │   └── app_core.py         # 应用核心
│   ├── abstractions/           # 抽象层
│   │   ├── __init__.py
│   │   ├── base_downloader.py  # 下载抽象基类
│   │   ├── base_uploader.py    # 上传抽象基类
│   │   └── base_handler.py     # 处理器抽象基类
│   ├── common/                 # 公共模块
│   │   ├── __init__.py
│   │   ├── message_fetcher.py  # 统一消息获取
│   │   ├── channel_validator.py # 统一频道验证
│   │   ├── flood_wait_handler.py # 统一FloodWait处理
│   │   └── error_handler.py    # 统一错误处理
│   ├── plugins/                # 智能插件目录
│   │   ├── __init__.py
│   │   ├── auth/               # 认证相关插件
│   │   │   ├── __init__.py
│   │   │   ├── login.py        # 登录流程
│   │   │   └── session.py      # 会话管理
│   │   ├── download/           # 下载功能插件
│   │   │   ├── __init__.py
│   │   │   ├── downloader.py   # 下载器
│   │   │   └── media_handler.py
│   │   ├── upload/             # 上传功能插件
│   │   │   ├── __init__.py
│   │   │   ├── uploader.py     # 上传器
│   │   │   └── file_processor.py
│   │   ├── forward/            # 转发功能插件
│   │   │   ├── __init__.py
│   │   │   ├── forwarder.py    # 转发器
│   │   │   ├── media_group_collector.py
│   │   │   └── message_filter.py
│   │   └── monitor/            # 监听功能插件
│   │       ├── __init__.py
│   │       ├── monitor.py      # 监听器
│   │       ├── message_processor.py
│   │       └── restricted_forward_handler.py
│   ├── ui/                     # UI界面
│   │   ├── __init__.py
│   │   ├── app_core/           # UI核心
│   │   │   ├── __init__.py
│   │   │   ├── app.py          # 应用主类
│   │   │   ├── async_services.py # 异步服务
│   │   │   ├── cleanup.py      # 清理服务
│   │   │   ├── client.py       # 客户端管理
│   │   │   ├── config.py       # 配置管理
│   │   │   ├── first_login.py  # 首次登录
│   │   │   └── theme.py        # 主题管理
│   │   ├── app.py              # 应用入口
│   │   ├── components/         # UI组件
│   │   │   ├── dialogs/        # 对话框
│   │   │   ├── main_window/    # 主窗口
│   │   │   │   ├── __init__.py
│   │   │   │   ├── actions.py  # 动作处理
│   │   │   │   ├── base.py     # 基础窗口
│   │   │   │   ├── menu_bar.py # 菜单栏
│   │   │   │   ├── sidebar.py  # 侧边栏
│   │   │   │   ├── status_bar.py # 状态栏
│   │   │   │   ├── system_tray.py # 系统托盘
│   │   │   │   ├── toolbar.py  # 工具栏
│   │   │   │   └── window_state.py # 窗口状态
│   │   │   └── navigation_tree.py # 导航树
│   │   └── views/              # 视图
│   │       ├── download_view.py # 下载视图
│   │       ├── forward_view.py # 转发视图
│   │       ├── help_doc_view.py # 帮助文档视图
│   │       ├── listen_view.py  # 监听视图
│   │       ├── log_viewer_view.py # 日志查看器视图
│   │       ├── main_window.py  # 主窗口视图
│   │       ├── performance_monitor_view.py # 性能监控视图
│   │       ├── settings_view.py # 设置视图
│   │       └── upload_view.py  # 上传视图
│   ├── utils/                  # 工具模块
│   │   ├── __init__.py
│   │   ├── async_utils.py      # 异步工具
│   │   ├── channel_resolver.py # 频道解析器
│   │   ├── event_emitter.py    # 事件发射器
│   │   ├── file_utils.py       # 文件工具
│   │   ├── logger.py           # 日志工具（基于loguru）
│   │   ├── resource_manager.py # 资源管理器（临时文件管理）
│   │   ├── text_utils.py       # 文本工具
│   │   ├── theme_manager.py    # 主题管理器（Material Design）
│   │   ├── translation_manager.py # 翻译管理器（国际化支持）
│   │   ├── video_processor.py  # 视频处理器
│   │   └── database_manager.py # 数据库管理器（SQLite历史记录）
│   ├── tests/                  # 测试目录
│   │   ├── __init__.py
│   │   ├── test_core/          # 核心模块测试
│   │   ├── test_plugins/       # 插件测试
│   │   ├── test_ui/            # UI测试
│   │   └── test_utils/         # 工具模块测试
│   ├── logs/                   # 日志目录
│   ├── sessions/               # 会话目录
│   ├── downloads/              # 下载目录
│   ├── uploads/                # 上传目录
│   ├── tmp/                    # 临时文件目录
│   ├── history/                # 历史记录目录
│   └── translations/           # 翻译文件目录
```

## 技术实现细节

### 1. 客户端管理增强

#### 1.1 完善的登录流程
- **首次登录**：支持手机号验证码登录
- **两步验证**：支持2FA密码验证
- **会话管理**：自动保存和恢复会话状态
- **错误处理**：完善的登录错误处理和重试机制

#### 1.2 自动重连功能
- **连接监控**：定期检查客户端连接状态
- **自动重连**：连接断开时自动尝试重连
- **指数退避**：重连失败时使用指数退避策略
- **数据库修复**：自动修复会话数据库锁定问题

### 2. 配置管理系统

#### 2.1 UI配置模型 (ui_config_models.py)
- **Pydantic验证**：使用Pydantic进行配置数据验证
- **枚举类型**：MediaType、ProxyType等枚举定义
- **嵌套模型**：UIGeneralConfig、UIDownloadConfig等嵌套配置
- **默认值处理**：完善的默认配置生成

#### 2.2 UI配置管理器 (ui_config_manager.py)
- **配置加载**：从JSON文件加载配置
- **配置转换**：UI配置与内部配置的转换
- **配置验证**：配置数据的有效性验证
- **默认配置**：自动生成默认配置文件

### 3. 国际化支持

#### 3.1 翻译管理器 (translation_manager.py)
- **多语言支持**：支持中文、英文等多种语言
- **动态切换**：运行时动态切换语言
- **翻译文件**：JSON格式的翻译文件管理
- **回退机制**：翻译缺失时的回退处理

#### 3.2 翻译文件结构
```json
{
  "ui": {
    "settings": {
      "title": "设置",
      "general": "通用设置"
    }
  }
}
```

### 4. 主题管理系统

#### 4.1 主题管理器 (theme_manager.py)
- **Material Design**：基于qt-material的主题系统
- **主题映射**：界面名称与实际主题文件的映射
- **动态切换**：运行时动态切换主题
- **深色模式**：完善的深色主题支持

#### 4.2 支持的主题
- 浅色主题、深色主题
- 蓝色主题、紫色主题、红色主题
- 绿色主题、琥珀色主题、粉色主题
- 黄色主题、青色主题

### 5. 数据库管理系统

#### 5.1 数据库管理器 (database_manager.py)
- **SQLite数据库**：使用SQLite存储历史记录
- **多表设计**：下载历史、上传历史、转发历史
- **索引优化**：完善的数据库索引设计
- **数据清理**：定期清理过期数据

#### 5.2 数据库表结构
```sql
-- 下载历史表
CREATE TABLE download_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id TEXT NOT NULL,
    message_id INTEGER NOT NULL,
    download_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(channel_id, message_id)
);

-- 上传历史表
CREATE TABLE upload_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_hash TEXT NOT NULL,
    target_channel TEXT NOT NULL,
    upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(file_hash, target_channel)
);

-- 转发历史表
CREATE TABLE forward_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_channel TEXT NOT NULL,
    message_id INTEGER NOT NULL,
    target_channel TEXT NOT NULL,
    forward_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_channel, message_id, target_channel)
);
```

### 6. 资源管理系统

#### 6.1 资源管理器 (resource_manager.py)
- **临时文件管理**：自动创建和清理临时文件
- **会话隔离**：不同会话的资源隔离
- **引用计数**：基于引用计数的资源管理
- **自动清理**：定期清理过期资源

#### 6.2 资源分类
- **缩略图**：视频缩略图文件
- **下载文件**：临时下载文件
- **上传文件**：临时上传文件
- **媒体组**：媒体组处理文件

### 7. 日志系统

#### 7.1 日志管理器 (logger.py)
- **loguru集成**：基于loguru的日志系统
- **多输出**：控制台和文件双重输出
- **日志轮转**：按日期和大小自动轮转
- **日志级别**：DEBUG、INFO、WARNING、ERROR等级别

#### 7.2 日志文件
- **按日期**：`tg_forwarder_YYYYMMDD.log`
- **固定名称**：`tg_manager.log`
- **保留策略**：30天历史日志保留

## 架构设计

### 1. 抽象层设计

#### 1.1 下载抽象基类 (BaseDownloader)
```python
class BaseDownloader:
    """下载功能抽象基类"""
    
    def __init__(self, client, config):
        self.client = client
        self.config = config
    
    async def download_media(self, message, save_path):
        """下载媒体文件"""
        raise NotImplementedError
    
    async def download_messages(self, chat_id, message_ids):
        """下载消息"""
        raise NotImplementedError
    
    async def get_media_info(self, message):
        """获取媒体信息"""
        raise NotImplementedError
```

#### 1.2 上传抽象基类 (BaseUploader)
```python
class BaseUploader:
    """上传功能抽象基类"""
    
    def __init__(self, client, config):
        self.client = client
        self.config = config
    
    async def upload_media(self, file_path, chat_id, caption=None):
        """上传媒体文件"""
        raise NotImplementedError
    
    async def upload_media_group(self, files, chat_id, caption=None):
        """上传媒体组"""
        raise NotImplementedError
    
    async def copy_message(self, from_chat_id, message_id, to_chat_id):
        """复制消息"""
        raise NotImplementedError
```

### 2. 公共模块设计

#### 2.1 统一消息获取 (MessageFetcher)
```python
class MessageFetcher:
    """统一消息获取器"""
    
    def __init__(self, client):
        self.client = client
    
    async def get_messages(self, chat_id, message_ids):
        """获取指定消息"""
        pass
    
    async def get_chat_history(self, chat_id, limit=100):
        """获取聊天历史"""
        pass
    
    async def search_messages(self, chat_id, query):
        """搜索消息"""
        pass
```

#### 2.2 统一频道验证 (ChannelValidator)
```python
class ChannelValidator:
    """统一频道验证器"""
    
    def __init__(self, client):
        self.client = client
    
    async def validate_channel(self, channel_id):
        """验证频道"""
        pass
    
    async def get_channel_info(self, channel_id):
        """获取频道信息"""
        pass
    
    async def check_permissions(self, channel_id):
        """检查权限"""
        pass
```

### 3. 插件系统设计

#### 3.1 插件管理器 (PluginManager)
```python
class PluginManager:
    """插件管理器"""
    
    def __init__(self, client, config):
        self.client = client
        self.config = config
        self.plugins = {}
        self.event_bus = EventBus()
    
    def load_plugins(self):
        """加载插件"""
        pass
    
    def unload_plugin(self, plugin_name):
        """卸载插件"""
        pass
    
    def get_plugin(self, plugin_name):
        """获取插件"""
        pass
```

#### 3.2 事件总线 (EventBus)
```python
class EventBus:
    """事件总线"""
    
    def __init__(self):
        self.handlers = {}
    
    def emit(self, event_type, *args, **kwargs):
        """发射事件"""
        pass
    
    def on(self, event_type, handler):
        """注册事件处理器"""
        pass
```

## 核心模块重构详解

### 1. 下载模块重构

#### 1.1 功能特性分析
基于对原代码的深入分析，下载模块具有以下核心特性：

**双模式下载系统**
- **并行下载器（Downloader）**：支持高并发下载，使用asyncio.Semaphore控制并发数
- **顺序下载器（DownloaderSerial）**：适合稳定网络环境，提供详细的进度跟踪

**智能过滤系统**
- **关键词过滤**：支持多关键词匹配，按关键词组织下载目录
- **媒体类型过滤**：支持photo、video、document、audio、animation等类型
- **消息ID范围限制**：支持start_id和end_id范围下载
- **全局限制**：支持global_limit限制总下载数量

**目录组织策略**
- **按频道组织**：`{channel_title}-{channel_id}/` 目录结构
- **按关键词组织**：`{channel_title}-{channel_id}/{keyword}/` 目录结构
- **媒体组处理**：`{media_group_id}/` 或 `single_{message_id}/` 目录
- **文件名安全化**：自动处理特殊字符，避免文件系统冲突

**并发控制机制**
- **下载并发控制**：可配置的max_concurrent_downloads（默认10）
- **文件写入线程池**：CPU核心数×2的写入线程池（最大32）
- **内存队列管理**：200容量的下载队列，避免内存溢出
- **FloodWait处理**：集成原生FloodWait处理器，智能重试

**进度监控系统**
- **实时进度跟踪**：当前文件/总文件数，当前字节/总字节数
- **下载速度监控**：实时计算和显示下载速度（KB/s、MB/s）
- **文件大小统计**：累计下载文件数和总字节数
- **状态控制**：支持暂停/恢复、取消操作

**错误处理机制**
- **网络错误处理**：自动重试，指数退避策略
- **文件写入错误**：临时文件写入，原子性重命名
- **数据库错误**：会话数据库锁定自动修复
- **FloodWait处理**：智能等待，进度显示

#### 1.2 核心组件设计

**Downloader类（并行下载器）**
```python
class Downloader:
    """并行下载器，支持高并发下载"""
    
    def __init__(self, client, ui_config_manager, channel_resolver, history_manager):
        # 并发控制
        self.max_concurrent_downloads = 10
        self.download_semaphore = asyncio.Semaphore(self.max_concurrent_downloads)
        self.active_downloads = 0
        
        # 文件写入系统
        self.download_queue = queue.Queue(maxsize=200)
        self.writer_pool_size = min(32, os.cpu_count() * 2)
        self.file_writer_thread = None
        
        # 进度跟踪
        self.download_count = 0
        self.total_downloaded_bytes = 0
        
        # FloodWait处理
        self.flood_wait_lock = asyncio.Lock()
        self.adaptive_delay = 0.5
```

**DownloaderSerial类（顺序下载器）**
```python
class DownloaderSerial:
    """顺序下载器，提供详细进度跟踪"""
    
    def __init__(self, client, ui_config_manager, channel_resolver, history_manager):
        # 进度跟踪
        self._current_file = None
        self._download_progress = (0, 0)
        self._current_speed = (0, "B/s")
        self._is_downloading = False
        
        # 下载队列
        self._download_queue = asyncio.Queue()
        self._is_stopped = False
```

**文件写入系统**
```python
def _file_writer_worker(self):
    """文件写入线程，从队列中取出内存中的媒体数据并写入文件"""
    with concurrent.futures.ThreadPoolExecutor(max_workers=self.writer_pool_size) as executor:
        futures = []
        while self.is_running or not self.download_queue.empty():
            # 从队列获取数据
            file_path, data, message_id, channel_id, media_type = item
            # 提交写入任务到线程池
            future = executor.submit(self._write_file, file_path, data, message_id, channel_id, media_type)
            futures.append(future)
```

#### 1.3 配置系统设计

**下载配置结构**
```python
DOWNLOAD = {
    "download_path": "downloads",  # 下载根目录
    "max_concurrent_downloads": 10,  # 最大并行下载数
    "downloadSetting": [  # 下载设置数组
        {
            "source_channels": "channel_name",  # 源频道
            "start_id": 0,  # 起始消息ID
            "end_id": 0,    # 结束消息ID
            "media_types": ["photo", "video", "document"],  # 媒体类型
            "keywords": ["keyword1", "keyword2"],  # 关键词（可选）
            "global_limit": 1000  # 全局限制
        }
    ]
}
```

**目录组织逻辑**
```python
def _process_channel_for_download(self, channel, start_id, end_id, media_types, keywords, all_download_tasks):
    """处理单个频道的下载过程"""
    # 解析频道ID
    real_channel_id = await self.channel_resolver.get_channel_id(channel)
    
    # 确定目录组织方式
    has_keywords = bool(keywords and len(keywords) > 0)
    organize_by_keywords = has_keywords
    
    # 创建主下载目录
    channel_path = self.download_path / channel_folder_name
    
    # 按关键词组织目录
    if organize_by_keywords and keywords:
        for keyword in keywords:
            keyword_folder = self._sanitize_filename(keyword)
            keyword_path = channel_path / keyword_folder
            keyword_path.mkdir(exist_ok=True)
```

#### 1.4 事件系统集成

**事件发射器包装**
```python
class EventEmitterDownloader(BaseEventEmitter):
    """基于Qt Signal的下载器包装类"""
    
    # 下载器特有的信号定义
    progress_updated = Signal(int, int, str)  # 进度更新信号
    download_completed = Signal(int, str, int)  # 下载完成信号
    all_downloads_completed = Signal()  # 所有下载完成信号
    
    def _emit_qt_signal(self, event_type, *args, **kwargs):
        """根据事件类型发射对应的Qt信号"""
        if event_type == "progress":
            current, total, filename = args[0], args[1], args[2]
            self.progress_updated.emit(current, total, filename)
        elif event_type == "download_complete":
            message_id, filename, file_size = args[0], args[1], args[2]
            self.download_completed.emit(message_id, filename, file_size)
```

#### 1.5 重构后的插件化设计

**下载插件基类**
```python
class BaseDownloadPlugin(Plugin):
    """下载插件基类"""
    
    def __init__(self, client, config):
        super().__init__(client, config)
        self.download_path = Path(config.get('download_path', 'downloads'))
        self.max_concurrent_downloads = config.get('max_concurrent_downloads', 10)
    
    async def download_media(self, message, save_path):
        """下载媒体文件"""
        raise NotImplementedError
    
    async def download_messages(self, chat_id, message_ids):
        """下载消息"""
        raise NotImplementedError
    
    async def get_media_info(self, message):
        """获取媒体信息"""
        raise NotImplementedError
```

**并行下载插件**
```python
class ParallelDownloadPlugin(BaseDownloadPlugin):
    """并行下载插件"""
    
    def __init__(self, client, config):
        super().__init__(client, config)
        self.download_semaphore = asyncio.Semaphore(self.max_concurrent_downloads)
        self.download_queue = queue.Queue(maxsize=200)
        self.writer_pool_size = min(32, os.cpu_count() * 2)
    
    async def download_media_from_channels(self):
        """从配置的源频道下载媒体文件"""
        # 启动文件写入线程
        self._start_file_writer()
        
        # 创建工作协程
        workers = []
        for i in range(self.max_concurrent_downloads):
            worker = asyncio.create_task(self._download_worker(i, work_queue))
            workers.append(worker)
        
        # 等待所有工作协程完成
        await asyncio.gather(*workers)
```

**顺序下载插件**
```python
class SerialDownloadPlugin(BaseDownloadPlugin):
    """顺序下载插件"""
    
    def __init__(self, client, config):
        super().__init__(client, config)
        self._current_file = None
        self._download_progress = (0, 0)
        self._current_speed = (0, "B/s")
    
    async def download_media_from_channels(self):
        """从配置的频道下载媒体文件"""
        self._is_downloading = True
        
        for setting in self.download_settings:
            await self._process_channel_setting(setting)
            
            # 更新进度
            self._update_progress()
            
            # 检查取消状态
            if self._is_stopped:
                break
```

### 2. 上传模块重构

#### 2.1 功能特性分析
基于对原代码的深入分析，上传模块具有以下核心特性：

**多目标上传优化**
- **智能复制策略**：首先上传到第一个目标频道，然后使用copy_message复制到其他频道
- **回退机制**：如果第一个频道上传失败，其他频道使用原方法直接上传
- **批量处理**：支持媒体组批量上传，最多10个文件一组

**文件管理系统**
- **文件哈希检查**：使用SHA256哈希值检查重复文件
- **文件类型识别**：自动识别照片、视频、文档、音频类型
- **缩略图生成**：视频文件自动生成缩略图
- **文件大小统计**：记录上传文件大小和上传时间

**媒体组处理**
- **媒体组识别**：自动识别和分组媒体文件
- **标题处理**：支持使用文件夹名称或读取title.txt作为标题
- **批量上传**：媒体组作为整体上传，保持顺序

**上传历史管理**
- **哈希记录**：使用文件哈希值记录上传历史
- **频道隔离**：不同频道的上传历史独立管理
- **重复跳过**：自动跳过已上传的文件

#### 2.2 核心组件设计

**Uploader类**
```python
class Uploader:
    """上传模块，负责将本地文件上传到目标频道"""
    
    def __init__(self, client, ui_config_manager, channel_resolver, history_manager):
        # 文件哈希缓存
        self.file_hash_cache = {}
        
        # 视频处理器
        self.video_processor = VideoProcessor()
        
        # 上传配置
        self.upload_config = self.config.get('UPLOAD', {})
        self.general_config = self.config.get('GENERAL', {})
```

**多目标上传优化**
```python
async def _upload_files_to_channels_with_copy(self, files, targets):
    """将文件上传到多个目标频道（使用消息复制优化）"""
    if len(targets) < 2:
        return await self._upload_files_to_channels(files, targets)
    
    first_target, first_target_id, first_target_info = targets[0]
    other_targets = targets[1:]
    
    for file in files:
        # 先上传到第一个目标频道
        success, actually_uploaded, message = await self._upload_single_file_with_message(file, first_target_id)
        
        # 如果上传成功并且是新文件，尝试复制到其他频道
        if success and actually_uploaded and message:
            for target_channel, target_id, target_info in other_targets:
                try:
                    await self.client.copy_message(
                        chat_id=target_id,
                        from_chat_id=first_target_id,
                        message_id=message.id
                    )
                except Exception as e:
                    logger.error(f"复制消息失败: {e}")
```

**媒体组上传**
```python
async def _upload_media_group_chunk(self, files, chat_id, caption=None):
    """上传一个媒体组块（最多10个文件）"""
    # 过滤已上传的文件
    filtered_files = []
    for file in files:
        file_hash = calculate_file_hash(file)
        if not self.history_manager.is_file_hash_uploaded(file_hash, chat_id_str):
            filtered_files.append(file)
    
    if not filtered_files:
        return True, False  # 所有文件都已上传
    
    # 构建媒体组
    media_group = []
    for file in filtered_files:
        media_type = self._get_media_type(file)
        if media_type == "photo":
            media_group.append(InputMediaPhoto(str(file)))
        elif media_type == "video":
            media_group.append(InputMediaVideo(str(file)))
        # ... 其他媒体类型
    
    # 上传媒体组
    result = await self.client.send_media_group(chat_id, media_group)
    return True, True
```

#### 2.3 配置系统设计

**上传配置结构**
```python
UPLOAD = {
    "directory": "uploads",  # 上传目录
    "target_channels": ["channel1", "channel2"],  # 目标频道
    "options": {
        "use_folder_name": True,  # 使用文件夹名称作为标题
        "read_title_txt": False,  # 读取title.txt作为标题
        "send_final_message": False,  # 发送最终消息
        "auto_thumbnail": True  # 自动生成缩略图
    }
}
```

#### 2.4 重构后的插件化设计

**上传插件基类**
```python
class BaseUploadPlugin(Plugin):
    """上传插件基类"""
    
    def __init__(self, client, config):
        super().__init__(client, config)
        self.upload_path = Path(config.get('directory', 'uploads'))
        self.target_channels = config.get('target_channels', [])
        self.options = config.get('options', {})
    
    async def upload_media(self, file_path, chat_id, caption=None):
        """上传媒体文件"""
        raise NotImplementedError
    
    async def upload_media_group(self, files, chat_id, caption=None):
        """上传媒体组"""
        raise NotImplementedError
    
    async def copy_message(self, from_chat_id, message_id, to_chat_id):
        """复制消息"""
        raise NotImplementedError
```

**智能上传插件**
```python
class SmartUploadPlugin(BaseUploadPlugin):
    """智能上传插件，支持多目标优化"""
    
    def __init__(self, client, config):
        super().__init__(client, config)
        self.file_hash_cache = {}
        self.video_processor = VideoProcessor()
    
    async def upload_local_files(self):
        """上传本地文件到目标频道"""
        # 获取媒体组列表
        media_groups = [d for d in self.upload_path.iterdir() if d.is_dir()]
        
        for group_dir in media_groups:
            # 获取媒体组中的文件
            media_files = [f for f in group_dir.iterdir() if f.is_file() and self._is_valid_media_file(f)]
            
            if len(media_files) == 1:
                # 单个文件，直接上传
                await self._upload_single_file(media_files[0], target_id, caption)
            else:
                # 多个文件，作为媒体组上传
                await self._upload_media_group(media_files, target_id, caption)
```

## 实施计划

### 第一阶段：整体框架 (1-2周)

#### 1.1 创建基础目录结构
- [ ] 创建refactor目录
- [ ] 创建基础目录结构
- [ ] 创建基础配置文件
- [ ] 复制原有配置文件到重构目录

#### 1.2 实现核心模块
- [ ] 实现ClientManager（完善的登录流程和自动重连）
- [ ] 实现PluginManager
- [ ] 实现EventBus
- [ ] 实现配置管理器

#### 1.3 实现抽象层
- [ ] 实现BaseDownloader（下载功能抽象基类）
- [ ] 实现BaseUploader（上传功能抽象基类）
- [ ] 实现BaseHandler（处理器抽象基类）

#### 1.4 实现公共模块
- [ ] 实现MessageFetcher（统一消息获取）
- [ ] 实现ChannelValidator（统一频道验证）
- [ ] 实现FloodWaitHandler（统一FloodWait处理）
- [ ] 实现ErrorHandler（统一错误处理）

#### 1.5 编写第一阶段测试
- [ ] 测试核心模块功能
- [ ] 测试抽象层接口
- [ ] 测试公共模块功能
- [ ] 对比原有功能验证一致性

### 第二阶段：核心部分完善 (2-3周)

#### 2.1 认证插件
- [ ] 实现登录功能（完善用户登录流程）
- [ ] 实现会话管理
- [ ] 实现自动重连功能
- [ ] 编写认证插件测试

#### 2.2 下载插件
- [ ] 继承BaseDownloader，实现历史消息下载
- [ ] 实现媒体文件下载（保持原有功能）
- [ ] 实现下载进度跟踪
- [ ] 实现关键词过滤和媒体类型过滤
- [ ] 编写下载插件测试，对比原有功能

#### 2.3 上传插件
- [ ] 继承BaseUploader，实现文件上传
- [ ] 实现媒体组上传（保持原有功能）
- [ ] 实现上传进度跟踪
- [ ] 实现文件哈希检查和重复文件跳过
- [ ] 编写上传插件测试，对比原有功能

#### 2.4 转发插件
- [ ] 使用BaseDownloader和BaseUploader
- [ ] 实现消息转发（直接转发和复制转发）
- [ ] 实现媒体组转发
- [ ] 实现转发过滤和文本替换
- [ ] 编写转发插件测试，对比原有功能

#### 2.5 监听插件
- [ ] 使用BaseDownloader和BaseUploader
- [ ] 实现消息监听（实时监听）
- [ ] 实现媒体组处理
- [ ] 实现自动转发
- [ ] 编写监听插件测试，对比原有功能

### 第三阶段：各个插件完善 (1-2周)

#### 3.1 UI界面适配
- [ ] 保持UI界面和原项目一致
- [ ] 适配新的插件架构
- [ ] 实现插件状态显示
- [ ] 实现插件配置界面
- [ ] 编写UI适配测试

#### 3.2 插件功能完善
- [ ] 完善下载插件的所有功能
- [ ] 完善上传插件的所有功能
- [ ] 完善转发插件的所有功能
- [ ] 完善监听插件的所有功能
- [ ] 编写插件功能测试

#### 3.3 集成测试
- [ ] 测试插件间通信
- [ ] 测试错误处理
- [ ] 测试性能表现
- [ ] 测试功能一致性
- [ ] 对比原有功能进行全面验证

### 第四阶段：测试优化和部署 (1周)

#### 4.1 全面测试
- [ ] 单元测试（每个模块）
- [ ] 集成测试（完整流程）
- [ ] 功能一致性测试（对比原有功能）
- [ ] 性能测试（确保性能不下降）
- [ ] UI界面测试（确保界面一致）

#### 4.2 性能优化
- [ ] 优化插件加载性能
- [ ] 优化内存使用
- [ ] 优化错误恢复机制
- [ ] 优化并发处理

#### 4.3 文档和部署
- [ ] 编写架构文档
- [ ] 编写API文档
- [ ] 编写迁移指南
- [ ] 准备部署脚本和配置文件

## 代码规范

### 1. 命名规范
- 类名使用PascalCase
- 函数名使用snake_case
- 常量使用UPPER_SNAKE_CASE
- 私有方法使用下划线前缀

### 2. 文档规范
- 所有公共方法必须有docstring
- 使用Google风格的docstring
- 包含参数说明、返回值说明、异常说明

### 3. 错误处理规范
- 使用统一的错误处理机制
- 所有异常必须被捕获并记录
- 提供有意义的错误信息

### 4. 测试规范
- 每个模块必须有对应的测试
- 测试覆盖率不低于80%
- 使用pytest进行测试

## 功能映射

### 原有功能到新架构的映射

| 原有模块 | 新架构位置 | 实现方式 | 功能保持 |
|---------|-----------|---------|---------|
| downloader.py | plugins/download/downloader.py | 继承BaseDownloader | 历史消息下载、媒体文件下载、关键词过滤 |
| downloader_serial.py | plugins/download/downloader.py | 继承BaseDownloader | 顺序下载、进度跟踪 |
| uploader.py | plugins/upload/uploader.py | 继承BaseUploader | 文件上传、媒体组上传、哈希检查 |
| forward/ | plugins/forward/ | 使用BaseDownloader和BaseUploader | 消息转发、媒体组转发、文本替换 |
| monitor/ | plugins/monitor/ | 使用BaseDownloader和BaseUploader | 实时监听、自动转发、性能监控 |
| client_manager.py | core/client_manager.py | 重构增强 | 完善登录流程、自动重连 |
| ui_config_models.py | config/ui_config_models.py | 保持原有 | UI配置模型、数据验证 |
| ui_config_manager.py | config/ui_config_manager.py | 保持原有 | UI配置管理、配置转换 |
| translation_manager.py | utils/translation_manager.py | 保持原有 | 国际化支持、多语言切换 |
| theme_manager.py | utils/theme_manager.py | 保持原有 | Material Design主题管理 |
| database_manager.py | utils/database_manager.py | 保持原有 | SQLite历史记录管理 |
| resource_manager.py | utils/resource_manager.py | 保持原有 | 临时文件管理、资源清理 |
| logger.py | utils/logger.py | 保持原有 | 基于loguru的日志系统 |
| UI界面 | ui/ | 保持原有 | 完全一致的UI界面和交互 |

### 新增功能模块

| 新模块 | 位置 | 功能说明 |
|--------|------|----------|
| BaseDownloader | abstractions/base_downloader.py | 下载功能抽象基类 |
| BaseUploader | abstractions/base_uploader.py | 上传功能抽象基类 |
| MessageFetcher | common/message_fetcher.py | 统一消息获取 |
| ChannelValidator | common/channel_validator.py | 统一频道验证 |
| PluginManager | core/plugin_manager.py | Pyrogram智能插件管理 |
| EventBus | core/event_bus.py | 事件总线系统 |

### 功能一致性检查清单

#### 下载功能
- [ ] 历史消息下载
- [ ] 媒体文件下载
- [ ] 下载进度跟踪
- [ ] 下载历史管理
- [ ] 关键词过滤
- [ ] 媒体类型过滤
- [ ] 目录组织方式

#### 上传功能
- [ ] 本地文件上传
- [ ] 媒体组上传
- [ ] 上传进度跟踪
- [ ] 文件哈希检查
- [ ] 重复文件跳过
- [ ] 缩略图生成
- [ ] 最终消息发送

#### 转发功能
- [ ] 直接转发
- [ ] 复制转发
- [ ] 媒体组转发
- [ ] 转发过滤
- [ ] 文本替换
- [ ] 转发历史管理
- [ ] 禁止转发处理

#### 监听功能
- [ ] 实时消息监听
- [ ] 媒体组处理
- [ ] 消息过滤
- [ ] 自动转发
- [ ] 性能监控
- [ ] 错误处理
- [ ] 状态管理

## 测试策略

### 1. 单元测试
- 测试每个抽象类的方法
- 测试每个插件的核心功能
- 测试公共模块的功能
- 测试错误处理机制
- 测试客户端管理功能

### 2. 集成测试
- 测试插件间通信
- 测试完整的工作流程
- 测试错误恢复机制
- 测试性能表现
- 测试UI界面交互

### 3. 功能一致性测试
- 对比原有功能和重构后功能
- 验证所有配置选项
- 验证所有输出结果
- 验证错误处理行为
- 验证UI界面一致性

### 4. 测试驱动开发
- 每重构一部分，立即编写对应测试
- 测试用例覆盖原有功能的所有场景
- 确保重构前后功能完全一致
- 持续集成测试，及时发现问题

## 风险评估

### 1. 技术风险
- **风险**：Pyrogram智能插件系统兼容性问题
- **缓解**：充分测试插件系统，准备回退方案

### 2. 功能风险
- **风险**：重构过程中功能丢失
- **缓解**：详细的功能映射和测试

### 3. 性能风险
- **风险**：插件化架构性能下降
- **缓解**：性能测试和优化

### 4. 时间风险
- **风险**：重构时间超出预期
- **缓解**：分阶段实施，及时调整计划

## 成功标准

### 1. 功能标准
- 所有原有功能正常工作（下载、上传、转发、监听）
- 所有配置选项有效
- 所有输出结果一致
- 错误处理行为一致
- UI界面和原项目完全一致

### 2. 性能标准
- 启动时间不超过原有系统的120%
- 内存使用不超过原有系统的110%
- 功能执行时间不超过原有系统的115%
- 客户端自动重连响应时间不超过5秒

### 3. 代码标准
- 代码覆盖率不低于80%
- 所有公共API有完整文档
- 代码符合PEP8规范
- 没有重复代码
- 抽象层设计合理，四大业务模块基于下载和上传抽象类

### 4. 可维护性标准
- 模块间耦合度低
- 插件可以独立开发
- 配置可以独立管理
- 错误可以快速定位
- 消息获取和频道验证使用统一管理

### 5. 重构标准
- 不修改原有代码
- 重构代码放在独立目录
- 每重构一部分都有对应测试
- 重构前后功能完全一致

## 时间安排

| 阶段 | 时间 | 主要任务 |
|------|------|----------|
| 第一阶段 | 1-2周 | 基础框架搭建 |
| 第二阶段 | 2-3周 | 插件开发 |
| 第三阶段 | 1-2周 | 测试和优化 |
| 第四阶段 | 1周 | 文档和部署 |
| **总计** | **5-8周** | **完整重构** |

## 团队分工

### 核心开发
- 负责基础框架开发
- 负责抽象层设计（BaseDownloader、BaseUploader）
- 负责公共模块实现（MessageFetcher、ChannelValidator）
- 负责客户端管理（登录流程、自动重连）

### 插件开发
- 负责各个插件实现（下载、上传、转发、监听）
- 负责功能测试
- 负责文档编写
- 负责UI界面适配

### 测试验证
- 负责测试用例编写
- 负责功能一致性验证（对比原有功能）
- 负责性能测试
- 负责UI界面测试

## 依赖管理

### 1. 核心依赖

#### 1.1 Pyrogram相关
```txt
pyrogram>=2.0.0          # Telegram客户端库
TgCrypto>=1.2.0          # 加密加速库
```

#### 1.2 UI框架
```txt
PySide6>=6.2.0           # Qt6 Python绑定
qt-material>=2.8.0       # Material Design主题
```

#### 1.3 数据处理
```txt
pydantic>=1.9.0,<2.0.0   # 数据验证和设置管理
loguru>=0.6.0            # 日志记录
```

#### 1.4 异步处理
```txt
aiohttp>=3.8.0           # 异步HTTP客户端
qasync>=0.24.0           # Qt与asyncio集成
```

### 2. 开发依赖

#### 2.1 测试框架
```txt
pytest>=7.0.0            # 测试框架
pytest-asyncio>=0.18.0   # 异步测试支持
pytest-qt>=4.0.0         # Qt测试支持
```

#### 2.2 代码质量
```txt
mypy>=0.910              # 静态类型检查
black>=22.0.0            # 代码格式化
flake8>=4.0.0            # 代码检查
```

#### 2.3 文档生成
```txt
sphinx>=5.0.0            # 文档生成
sphinx-rtd-theme>=1.0.0  # ReadTheDocs主题
```

### 3. 可选依赖

#### 3.1 媒体处理
```txt
moviepy>=1.0.3           # 视频处理
Pillow>=9.0.0            # 图像处理
```

#### 3.2 性能优化
```txt
uvloop>=0.16.0           # 事件循环优化（仅Linux/macOS）
```

## 环境配置

### 1. Python版本要求
- **最低版本**：Python 3.8
- **推荐版本**：Python 3.9+
- **最高版本**：Python 3.11

### 2. 系统要求
- **操作系统**：Windows 10+, macOS 10.14+, Ubuntu 18.04+
- **内存**：最少4GB，推荐8GB+
- **存储**：最少1GB可用空间

### 3. 网络要求
- **代理支持**：SOCKS5、HTTP代理
- **网络连接**：稳定的互联网连接
- **API限制**：遵守Telegram API限制

## 联系方式

如有问题或建议，请联系项目负责人。

---

**注意**：本重构计划将严格按照时间安排执行，每个阶段完成后都会进行评审和测试，确保重构质量和进度。 