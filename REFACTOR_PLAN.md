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
9. **简化下载系统**：重构后舍弃并行下载功能，只保留顺序下载器，简化系统复杂度

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

**顺序下载系统**
- **顺序下载器（DownloaderSerial）**：适合稳定网络环境，提供详细的进度跟踪
- **舍弃并行下载**：重构后不再支持并行下载功能，简化系统架构

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

#### 1.3 配置系统设计

**下载配置结构**
```python
DOWNLOAD = {
    "download_path": "downloads",  # 下载根目录
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
- **媒体组分块**：超过10个文件时自动分块上传

**上传历史管理**
- **哈希记录**：使用文件哈希值记录上传历史
- **频道隔离**：不同频道的上传历史独立管理
- **重复跳过**：自动跳过已上传的文件

**最终消息系统**
- **HTML消息支持**：支持发送自定义HTML格式的最终消息
- **网页预览控制**：可配置是否启用网页预览
- **多频道发送**：最终消息发送到所有目标频道
- **重试机制**：最终消息发送失败时自动重试

**网络错误处理**
- **连接状态检查**：网络错误时自动检查连接状态
- **重试机制**：上传失败时自动重试，支持指数退避
- **错误分类**：区分不同类型的错误（网络、媒体、配置等）

**事件系统集成**
- **进度事件**：实时上传进度更新
- **完成事件**：上传完成通知
- **错误事件**：错误状态通知
- **文件事件**：单个文件上传状态
- **最终消息事件**：最终消息发送状态

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
        
        # 事件发射器
        self._listeners = {}
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

**最终消息发送**
```python
async def _send_final_message(self, valid_targets, files_uploaded=False):
    """发送最终消息到所有目标频道"""
    options = self.upload_config.get('options', {})
    send_final_message = bool(options.get('send_final_message', False))
    
    if not send_final_message or not files_uploaded:
        return
    
    # 读取HTML文件
    html_file_path = options.get('final_message_html_file', '')
    if not html_file_path or not os.path.exists(html_file_path):
        return
    
    with open(html_file_path, 'r', encoding='utf-8') as f:
        html_content = f.read().strip()
    
    # 发送到所有目标频道
    for target, target_id, target_info in valid_targets:
        try:
            enable_web_page_preview = bool(options.get('enable_web_page_preview', False))
            message = await self.client.send_message(
                chat_id=target_id,
                text=html_content,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=not enable_web_page_preview
            )
            
            # 发送成功事件
            self.emit("final_message_sent", {
                "chat_id": target_id,
                "chat_info": target_info,
                "message_id": message.id
            })
        except Exception as e:
            # 发送失败事件
            self.emit("final_message_error", {
                "chat_id": target_id,
                "chat_info": target_info,
                "error": str(e)
            })
```

**网络错误处理**
```python
async def _handle_network_error(self, error):
    """处理网络相关错误"""
    logger.error(f"检测到网络错误: {type(error).__name__}: {error}")
    
    # 通知应用程序立即检查连接状态
    if self.app and hasattr(self.app, 'check_connection_status_now'):
        try:
            asyncio.create_task(self.app.check_connection_status_now())
        except Exception as e:
            logger.error(f"触发连接状态检查失败: {e}")
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
        "auto_thumbnail": True,  # 自动生成缩略图
        "enable_web_page_preview": False,  # 启用网页预览
        "final_message_html_file": ""  # 最终消息HTML文件路径
    }
}
```

#### 2.4 事件系统集成

**事件发射器包装**
```python
class EventEmitterUploader(BaseEventEmitter):
    """基于Qt Signal的上传器包装类"""
    
    # 上传器特有的信号定义
    progress_updated = Signal(int, int, int)  # 进度更新信号
    upload_completed = Signal(object)  # 上传完成信号
    media_uploaded = Signal(object)  # 媒体上传信号
    all_uploads_completed = Signal()  # 所有上传完成信号
    file_already_uploaded = Signal(object)  # 文件已上传信号
    final_message_sent = Signal(object)  # 最终消息发送成功信号
    final_message_error = Signal(object)  # 最终消息发送失败信号
    
    def _emit_qt_signal(self, event_type, *args, **kwargs):
        """根据事件类型发射对应的Qt信号"""
        if event_type == "progress":
            progress, idx, total = args[0], args[1], args[2]
            self.progress_updated.emit(progress, idx, total)
        elif event_type == "complete":
            result_data = args[1]
            self.upload_completed.emit(result_data)
            self.all_uploads_completed.emit()
        elif event_type == "media_upload":
            media_data = args[0]
            self.media_uploaded.emit(media_data)
        elif event_type == "file_already_uploaded":
            file_data = args[0]
            self.file_already_uploaded.emit(file_data)
        elif event_type == "final_message_sent":
            message_data = args[0]
            self.final_message_sent.emit(message_data)
        elif event_type == "final_message_error":
            error_data = args[0]
            self.final_message_error.emit(error_data)
```

#### 2.5 重构后的插件化设计

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
    
    async def send_final_message(self, valid_targets, files_uploaded=False):
        """发送最终消息"""
        raise NotImplementedError
```

**智能上传插件**
```python
class SmartUploadPlugin(BaseUploadPlugin):
    """智能上传插件，支持多目标优化和最终消息"""
    
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
        
        # 发送最终消息
        await self.send_final_message(valid_targets, files_uploaded=True)
```

### 3. 转发模块重构

#### 3.1 功能特性分析
基于对原代码的深入分析，转发模块具有以下核心特性：

**智能转发策略**
- **直接转发优化**：源频道允许转发时，优先使用Telegram原生转发功能
- **下载重传策略**：源频道禁止转发时，自动切换到下载-上传模式
- **媒体组处理**：智能识别和重组媒体组，支持部分过滤后的媒体组重组
- **纯文本消息处理**：支持纯文本消息的直接转发和复制转发

**高级过滤系统**
- **关键词过滤**：支持媒体组级别的关键词过滤，媒体组中任何消息包含关键词则整个组通过
- **媒体类型过滤**：支持消息级别的精确过滤，可排除特定媒体类型
- **文本替换功能**：支持批量文本替换，可修改消息标题和文本内容
- **链接过滤**：可配置排除包含链接的消息
- **标题移除**：支持移除媒体说明文字

**消息范围控制**
- **消息ID范围**：支持start_id和end_id范围转发
- **历史记录检查**：自动跳过已转发的消息，避免重复转发
- **优化获取**：预过滤已转发消息ID，减少API调用

**并行处理系统**
- **生产者-消费者模式**：并行下载和上传媒体组
- **队列管理**：使用asyncio.Queue管理媒体组队列
- **任务协调**：下载和上传任务独立运行，提高效率
- **错误恢复**：单个媒体组失败不影响其他媒体组处理

**事件系统集成**
- **进度事件**：实时转发进度更新
- **完成事件**：转发完成通知
- **错误事件**：错误状态通知
- **过滤事件**：消息过滤状态通知
- **媒体组事件**：媒体组处理状态通知
- **文本替换事件**：文本替换操作通知
- **FloodWait事件**：限流检测和处理通知

**网络错误处理**
- **连接状态检查**：网络错误时自动检查连接状态
- **FloodWait处理**：智能等待，进度显示
- **重试机制**：转发失败时自动重试，支持指数退避
- **错误分类**：区分不同类型的错误（网络、权限、媒体等）

**最终消息系统**
- **HTML消息支持**：支持发送自定义HTML格式的最终消息
- **网页预览控制**：可配置是否启用网页预览
- **多频道发送**：最终消息发送到所有目标频道
- **重试机制**：最终消息发送失败时自动重试

#### 3.2 核心组件设计

**Forwarder类（主转发器）**
```python
class Forwarder:
    """转发模块，负责将消息从源频道转发到目标频道"""
    
    def __init__(self, client, ui_config_manager, channel_resolver, history_manager, downloader, uploader, app=None):
        # 消息迭代器，用于获取消息
        self.message_iterator = MessageIterator(self.client, self.channel_resolver, self)
        
        # 消息过滤器，用于筛选需要转发的消息
        self.message_filter = MessageFilter(self.config, self._emit_event)
        
        # 媒体组收集器，用于分组和优化消息获取
        self.media_group_collector = MediaGroupCollector(self.message_iterator, self.message_filter, self._emit_event)
        
        # 直接转发器，用于直接转发消息
        self.direct_forwarder = DirectForwarder(client, history_manager, self.general_config, self._emit_event)
        
        # 并行处理器，用于并行下载和上传
        self.parallel_processor = ParallelProcessor(client, history_manager, self.general_config, self.config, self._emit_event)
```

**DirectForwarder类（直接转发器）**
```python
class DirectForwarder:
    """直接转发器，使用Telegram原生转发功能"""
    
    async def forward_media_group_directly(self, messages, source_channel, source_id, target_channels, hide_author, pair_config):
        """直接转发媒体组到目标频道"""
        # 应用过滤规则
        filtered_messages, _, filter_stats = self.message_filter.apply_all_filters(messages, pair_config)
        
        # 检查是否需要文本替换或重组
        need_text_replacement = bool(text_replacements)
        force_copy_mode = (need_text_replacement or 
                         pair_config.get('remove_captions', False) or 
                         is_regrouped_media)
        
        # 根据条件选择转发方式
        if force_copy_mode:
            # 使用copy_message方式
            await self._forward_with_copy(filtered_messages, target_channels, hide_author, pair_config)
        else:
            # 使用原生转发方式
            await self._forward_natively(filtered_messages, source_id, target_channels, hide_author)
```

**MessageFilter类（消息过滤器）**
```python
class MessageFilter:
    """统一的消息过滤器，支持多种过滤功能"""
    
    def apply_keyword_filter(self, messages, keywords):
        """应用关键词过滤，支持媒体组级别的过滤"""
        # 按媒体组分组
        media_groups = self._group_messages_by_media_group(messages)
        
        # 媒体组中任何一条消息包含关键词，则整个媒体组都通过过滤
        for group_messages in media_groups:
            group_has_keyword = False
            for message in group_messages:
                text_content = message.caption or message.text or ""
                for keyword in keywords:
                    if keyword.lower() in text_content.lower():
                        group_has_keyword = True
                        break
    
    def apply_media_type_filter(self, messages, allowed_media_types):
        """应用媒体类型过滤，支持消息级别的精确过滤"""
        # 对媒体组中的每条消息单独进行媒体类型检查
        for group_messages in media_groups:
            for message in group_messages:
                message_media_type = self._get_message_media_type(message)
                if message_media_type and self._is_media_type_allowed(message_media_type, allowed_media_types):
                    group_passed.append(message)
                else:
                    group_filtered.append(message)
    
    def apply_text_replacements(self, text, text_replacements):
        """应用文本替换规则到文本内容"""
        result_text = text
        has_replacement = False
        
        for find_text, replace_text in text_replacements.items():
            if find_text in result_text:
                result_text = result_text.replace(find_text, replace_text)
                has_replacement = True
                
                # 发射文本替换事件
                if self.emit:
                    self.emit("text_replacement_applied", f"消息文本", find_text, replace_text)
        
        return result_text, has_replacement
    
    def apply_all_filters(self, messages, pair_config):
        """应用所有过滤规则"""
        # 应用关键词过滤
        if pair_config.get('keywords'):
            messages, _ = self.apply_keyword_filter(messages, pair_config['keywords'])
        
        # 应用媒体类型过滤
        if pair_config.get('media_types'):
            messages, _ = self.apply_media_type_filter(messages, pair_config['media_types'])
        
        # 应用链接过滤
        if pair_config.get('exclude_links', False):
            messages, _ = self.apply_link_filter(messages)
        
        # 提取媒体组文本
        media_group_texts = self._extract_media_group_texts(messages)
        
        return messages, [], {
            'media_group_texts': media_group_texts,
            'filter_stats': {
                'keyword_filtered': len(messages),
                'media_type_filtered': len(messages),
                'link_filtered': len(messages)
            }
        }
```

**MessageIterator类（消息迭代器）**
```python
class MessageIterator:
    """消息迭代器，用于高效获取消息"""
    
    def __init__(self, client, channel_resolver, forwarder=None):
        self.client = client
        self.channel_resolver = channel_resolver
        self.forwarder = forwarder  # 用于停止检查
    
    async def iter_messages_by_ids(self, chat_id, message_ids):
        """按消息ID列表迭代获取消息"""
        for message_id in message_ids:
            # 检查停止信号
            if self.forwarder and self.forwarder.should_stop:
                break
            
            try:
                message = await self._get_message_with_flood_wait(chat_id, message_id)
                if message:
                    yield message
            except Exception as e:
                logger.error(f"获取消息 {message_id} 失败: {e}")
    
    async def _get_message_with_flood_wait(self, chat_id, message_id):
        """使用FloodWait处理器获取消息"""
        async def get_message():
            return await self.client.get_messages(chat_id, message_id)
        
        return await execute_with_flood_wait(get_message, max_retries=3)
```

**MediaGroupCollector类（媒体组收集器）**
```python
class MediaGroupCollector:
    """媒体组收集器，用于收集媒体组消息"""
    
    def __init__(self, message_iterator, message_filter, emit=None):
        self.message_iterator = message_iterator
        self.message_filter = message_filter
        self.emit = emit
    
    def _filter_unforwarded_ids(self, start_id, end_id, source_channel, target_channels, history_manager):
        """根据转发历史预过滤未转发的消息ID"""
        unforwarded_ids = []
        
        for msg_id in range(start_id, end_id + 1):
            is_fully_forwarded = True
            
            # 检查是否已转发到所有目标频道
            for target_channel in target_channels:
                if not history_manager.is_message_forwarded(source_channel, msg_id, target_channel):
                    is_fully_forwarded = False
                    break
            
            if not is_fully_forwarded:
                unforwarded_ids.append(msg_id)
        
        return unforwarded_ids
    
    async def get_media_groups_optimized(self, source_id, source_channel, target_channels, pair, history_manager):
        """优化的获取源频道媒体组方法"""
        # 解析消息范围
        start_id, end_id, is_valid = await self._resolve_message_range(source_id, pair)
        
        # 预过滤已转发的消息ID
        unforwarded_ids = self._filter_unforwarded_ids(start_id, end_id, source_channel, target_channels, history_manager)
        
        # 按指定ID列表获取消息
        all_messages = []
        async for message in self.message_iterator.iter_messages_by_ids(source_id, unforwarded_ids):
            all_messages.append(message)
        
        # 应用过滤规则
        if pair and all_messages:
            filtered_messages, _, filter_stats = self.message_filter.apply_all_filters(all_messages, pair)
            media_group_texts = filter_stats.get('media_group_texts', {})
        else:
            filtered_messages = all_messages
            media_group_texts = {}
        
        # 将过滤后的消息按媒体组分组
        media_groups = {}
        for message in filtered_messages:
            group_id = str(message.media_group_id) if message.media_group_id else f"single_{message.id}"
            if group_id not in media_groups:
                media_groups[group_id] = []
            media_groups[group_id].append(message)
        
        return media_groups, media_group_texts
    
    async def get_media_groups_info_optimized(self, source_id, source_channel, target_channels, pair, history_manager):
        """优化的获取媒体组信息方法（仅获取ID，不下载内容）"""
        # 解析消息范围
        start_id, end_id, is_valid = await self._resolve_message_range(source_id, pair)
        
        # 预过滤已转发的消息ID
        unforwarded_ids = self._filter_unforwarded_ids(start_id, end_id, source_channel, target_channels, history_manager)
        
        # 按指定ID列表获取消息（仅获取基本信息）
        all_messages = []
        async for message in self.message_iterator.iter_messages_by_ids(source_id, unforwarded_ids):
            all_messages.append(message)
        
        # 应用过滤规则
        if pair and all_messages:
            filtered_messages, _, filter_stats = self.message_filter.apply_all_filters(all_messages, pair)
            media_group_texts = filter_stats.get('media_group_texts', {})
        else:
            filtered_messages = all_messages
            media_group_texts = {}
        
        # 将过滤后的消息按媒体组分组（仅ID）
        media_groups_info = []
        current_group = []
        current_group_id = None
        
        for message in filtered_messages:
            group_id = str(message.media_group_id) if message.media_group_id else f"single_{message.id}"
            
            if group_id != current_group_id:
                if current_group:
                    media_groups_info.append((current_group_id, current_group))
                current_group = [message.id]
                current_group_id = group_id
            else:
                current_group.append(message.id)
        
        if current_group:
            media_groups_info.append((current_group_id, current_group))
        
        return media_groups_info, media_group_texts
```

**ParallelProcessor类（并行处理器）**
```python
class ParallelProcessor:
    """并行处理器，负责并行下载和上传媒体组"""
    
    def __init__(self, client, history_manager, general_config, config, emit=None):
        self.client = client
        self.history_manager = history_manager
        self.general_config = general_config
        self.emit = emit
        
        # 创建媒体组队列
        self.media_group_queue = asyncio.Queue()
        
        # 生产者-消费者控制
        self.download_running = False
        self.upload_running = False
        self.should_stop = False
        
        # 初始化组件
        self.message_downloader = MessageDownloader(client)
        self.media_uploader = MediaUploader(client, history_manager, general_config)
        self.flood_wait_handler = FloodWaitHandler(max_retries=3, base_delay=1.0)
    
    async def process_parallel_download_upload(self, source_channel, source_id, media_groups_info, temp_dir, target_channels, pair_config):
        """并行处理媒体组下载和上传"""
        try:
            # 设置下载和上传标志
            self.download_running = True
            self.upload_running = True
            
            # 创建生产者和消费者任务
            producer_task = asyncio.create_task(
                self._producer_download_media_groups_parallel(source_channel, source_id, media_groups_info, temp_dir, target_channels, pair_config)
            )
            consumer_task = asyncio.create_task(
                self._consumer_upload_media_groups(target_channels)
            )
            
            # 等待生产者和消费者任务完成
            producer_result = await producer_task
            await self.media_group_queue.put(None)  # 发送结束信号
            consumer_result = await consumer_task
            
            return producer_result
            
        except Exception as e:
            logger.error(f"并行处理失败: {e}")
            raise
    
    async def _producer_download_media_groups_parallel(self, source_channel, source_id, media_groups_info, temp_dir, target_channels, pair_config):
        """生产者：并行下载媒体组"""
        forward_count = 0
        
        for group_id, message_ids in media_groups_info:
            # 检查是否收到停止信号
            if self.should_stop:
                break
            
            # 检查是否已转发到所有目标频道
            all_forwarded = True
            for target_channel, _, _ in target_channels:
                if not self.history_manager.is_message_forwarded(source_channel, message_ids[0], target_channel):
                    all_forwarded = False
                    break
            
            if all_forwarded:
                continue
            
            # 下载媒体组
            group_dir = temp_dir / self._get_safe_path_name(group_id)
            success = await self._download_media_group(source_id, message_ids, group_dir)
            
            if success:
                # 将下载完成的媒体组放入队列
                await self.media_group_queue.put((group_id, message_ids, group_dir))
                forward_count += 1
                
                # 发射下载完成事件
                if self.emit:
                    self.emit("media_group_downloaded", group_id, len(message_ids), len(list(group_dir.iterdir())))
        
        return forward_count
    
    async def _consumer_upload_media_groups(self, target_channels):
        """消费者：上传媒体组"""
        while True:
            try:
                # 从队列获取媒体组
                item = await self.media_group_queue.get()
                if item is None:  # 结束信号
                    break
                
                group_id, message_ids, group_dir = item
                
                # 上传媒体组到所有目标频道
                uploaded_targets, remaining_targets = await self.media_uploader.upload_media_group_to_channels(
                    group_dir, target_channels, group_id
                )
                
                # 发射上传完成事件
                if self.emit:
                    self.emit("media_group_uploaded", group_id, message_ids, uploaded_targets, remaining_targets)
                
                # 清理临时文件
                if group_dir.exists():
                    shutil.rmtree(group_dir)
                
            except Exception as e:
                logger.error(f"上传媒体组失败: {e}")
            finally:
                self.media_group_queue.task_done()
```

**MediaUploader类（媒体上传器）**
```python
class MediaUploader:
    """媒体上传器，负责上传媒体组到目标频道"""
    
    def __init__(self, client, history_manager, general_config):
        self.client = client
        self.history_manager = history_manager
        self.general_config = general_config
    
    async def upload_media_group_to_channels(self, group_dir, target_channels, group_id):
        """上传媒体组到多个目标频道"""
        uploaded_targets = []
        remaining_targets = []
        
        # 获取媒体组中的文件
        media_files = [f for f in group_dir.iterdir() if f.is_file() and self._is_valid_media_file(f)]
        
        if not media_files:
            return uploaded_targets, target_channels
        
        # 构建媒体组
        media_group = []
        for file in media_files:
            media_type = self._get_media_type(file)
            if media_type == "photo":
                media_group.append(InputMediaPhoto(str(file)))
            elif media_type == "video":
                media_group.append(InputMediaVideo(str(file)))
            elif media_type == "document":
                media_group.append(InputMediaDocument(str(file)))
            elif media_type == "audio":
                media_group.append(InputMediaAudio(str(file)))
            elif media_type == "animation":
                media_group.append(InputMediaAnimation(str(file)))
        
        # 上传到每个目标频道
        for target_channel, target_id, target_info in target_channels:
            try:
                # 检查是否已上传
                if self.history_manager and self.history_manager.is_media_group_uploaded(group_id, target_channel):
                    continue
                
                # 上传媒体组
                result = await self.client.send_media_group(target_id, media_group)
                
                # 记录上传历史
                if self.history_manager:
                    for message in result:
                        self.history_manager.add_upload_record(group_id, target_channel, message.id)
                
                uploaded_targets.append(target_info)
                
            except Exception as e:
                logger.error(f"上传媒体组到 {target_info} 失败: {e}")
                remaining_targets.append(target_info)
        
        return uploaded_targets, remaining_targets
```

#### 3.3 配置系统设计

**转发配置结构**
```python
FORWARD = {
    "forward_channel_pairs": [  # 转发频道对列表
        {
            "source_channel": "channel_name",  # 源频道
            "target_channels": ["target1", "target2"],  # 目标频道列表
            "media_types": ["photo", "video", "document"],  # 媒体类型
            "start_id": 0,  # 起始消息ID
            "end_id": 0,    # 结束消息ID
            "enabled": True,  # 是否启用
            "remove_captions": False,  # 是否移除媒体说明文字
            "hide_author": False,  # 是否隐藏原作者
            "send_final_message": False,  # 是否发送最终消息
            "final_message_html_file": "",  # 最终消息HTML文件路径
            "enable_web_page_preview": False,  # 是否启用网页预览
            "text_filter": [  # 文本替换规则
                {"original_text": "原文", "target_text": "替换文本"}
            ],
            "keywords": ["keyword1", "keyword2"],  # 关键词列表
            "exclude_links": False  # 是否排除含链接的消息
        }
    ],
    "forward_delay": 0.1,  # 转发间隔时间(秒)
    "tmp_path": "tmp"  # 临时文件路径
}
```

#### 3.4 事件系统集成

**事件发射器包装**
```python
class EventEmitterForwarder(BaseEventEmitter):
    """基于Qt Signal的转发器包装类"""
    
    # 转发器特有的信号定义
    progress_updated = Signal(int, int, int, str)  # 进度更新信号
    info_updated = Signal(str)  # 信息更新信号
    warning_updated = Signal(str)  # 警告信号
    debug_updated = Signal(str)  # 调试信息信号
    forward_completed = Signal(int)  # 转发完成信号
    all_forwards_completed = Signal()  # 所有转发完成信号
    message_forwarded = Signal(int, str)  # 消息转发信号
    media_group_forwarded = Signal(List, str, int)  # 媒体组转发信号
    media_group_downloaded = Signal(str, int, int)  # 媒体组下载信号
    media_group_uploaded = Signal(str, List, List, List)  # 媒体组上传信号
    message_filtered = Signal(int, str, str)  # 消息过滤信号
    collection_started = Signal(int)  # 收集开始信号
    collection_progress = Signal(int, int)  # 收集进度信号
    collection_completed = Signal(int, int)  # 收集完成信号
    collection_error = Signal(str)  # 收集错误信号
    text_replacement_applied = Signal(str, str, str)  # 文本替换信号
    flood_wait_detected = Signal(int, str)  # 限流检测信号
    
    def _emit_qt_signal(self, event_type, *args, **kwargs):
        """根据事件类型发射对应的Qt信号"""
        if event_type == "progress":
            progress, current, total, operation_type = args[0], args[1], args[2], args[3]
            self.progress_updated.emit(progress, current, total, operation_type)
        elif event_type == "message_forwarded":
            message_id, target_info = args[0], args[1]
            self.message_forwarded.emit(message_id, target_info)
        elif event_type == "media_group_forwarded":
            message_ids, target_info, count = args[0], args[1], args[2]
            self.media_group_forwarded.emit(message_ids, target_info, count)
        elif event_type == "message_filtered":
            message_id, message_type, filter_reason = args[0], args[1], args[2]
            self.message_filtered.emit(message_id, message_type, filter_reason)
        elif event_type == "text_replacement_applied":
            message_desc, original_text, replaced_text = args[0], args[1], args[2]
            self.text_replacement_applied.emit(message_desc, original_text, replaced_text)
        elif event_type == "flood_wait_detected":
            wait_time, operation_desc = args[0], args[1]
            self.flood_wait_detected.emit(wait_time, operation_desc)
        elif event_type == "collection_started":
            total_count = args[0]
            self.collection_started.emit(total_count)
        elif event_type == "collection_progress":
            current_count, total_count = args[0], args[1]
            self.collection_progress.emit(current_count, total_count)
        elif event_type == "collection_completed":
            collected_count, total_count = args[0], args[1]
            self.collection_completed.emit(collected_count, total_count)
        elif event_type == "collection_error":
            error_message = args[0]
            self.collection_error.emit(error_message)
```

#### 3.5 重构后的插件化设计

**转发插件基类**
```python
class BaseForwardPlugin(Plugin):
    """转发插件基类"""
    
    def __init__(self, client, config):
        super().__init__(client, config)
        self.forward_config = config.get('FORWARD', {})
        self.general_config = config.get('GENERAL', {})
    
    async def forward_messages(self):
        """转发消息"""
        raise NotImplementedError
    
    async def stop_forward(self):
        """停止转发"""
        raise NotImplementedError
```

**智能转发插件**
```python
class SmartForwardPlugin(BaseForwardPlugin):
    """智能转发插件，支持多种转发策略"""
    
    def __init__(self, client, config):
        super().__init__(client, config)
        self.message_filter = MessageFilter(config)
        self.media_group_collector = MediaGroupCollector(self.message_iterator, self.message_filter, self.emit)
        self.direct_forwarder = DirectForwarder(client, self.history_manager, self.general_config, self.emit)
        self.parallel_processor = ParallelProcessor(client, self.history_manager, self.general_config, config, self.emit)
    
    async def forward_messages(self):
        """从源频道转发消息到目标频道"""
        # 获取频道对列表
        channel_pairs = self.forward_config.get('forward_channel_pairs', [])
        
        for pair in channel_pairs:
            # 检查是否启用
            if not pair.get('enabled', True):
                continue
            
            source_channel = pair.get('source_channel', '')
            target_channels = pair.get('target_channels', [])
            
            # 解析频道ID
            source_id = await self.channel_resolver.get_channel_id(source_channel)
            source_can_forward = await self.channel_resolver.check_forward_permission(source_id)
            
            if source_can_forward:
                # 直接转发模式
                await self._forward_directly(source_id, source_channel, target_channels, pair)
            else:
                # 下载重传模式
                await self._forward_with_download_upload(source_id, source_channel, target_channels, pair)
        
        # 发送最终消息
        await self._send_final_messages(channel_pairs)
    
    async def _forward_directly(self, source_id, source_channel, target_channels, pair):
        """直接转发模式"""
        # 获取媒体组
        media_groups, media_group_texts = await self.media_group_collector.get_media_groups_optimized(
            source_id, source_channel, target_channels, pair, self.history_manager
        )
        
        # 直接转发每个媒体组
        for group_id, messages in media_groups.items():
            await self.direct_forwarder.forward_media_group_directly(
                messages, source_channel, source_id, target_channels, 
                pair.get('hide_author', False), pair
            )
    
    async def _forward_with_download_upload(self, source_id, source_channel, target_channels, pair):
        """下载重传模式"""
        # 获取媒体组信息
        media_groups_info, media_group_texts = await self.media_group_collector.get_media_groups_info_optimized(
            source_id, source_channel, target_channels, pair, self.history_manager
        )
        
        # 创建临时目录
        temp_dir = self._ensure_temp_dir()
        
        # 并行处理下载和上传
        await self.parallel_processor.process_parallel_download_upload(
            source_channel, source_id, media_groups_info, temp_dir, target_channels, pair
        )
    
    async def _send_final_messages(self, channel_pairs):
        """发送最终消息"""
        for pair in channel_pairs:
            if not pair.get('send_final_message', False):
                continue
            
            html_file_path = pair.get('final_message_html_file', '')
            if not html_file_path or not os.path.exists(html_file_path):
                continue
            
            # 读取HTML内容
            with open(html_file_path, 'r', encoding='utf-8') as f:
                html_content = f.read().strip()
            
            # 发送到所有目标频道
            target_channels = pair.get('target_channels', [])
            for target_channel in target_channels:
                try:
                    target_id = await self.channel_resolver.get_channel_id(target_channel)
                    enable_web_page_preview = pair.get('enable_web_page_preview', False)
                    
                    await self.client.send_message(
                        chat_id=target_id,
                        text=html_content,
                        parse_mode=enums.ParseMode.HTML,
                        disable_web_page_preview=not enable_web_page_preview
                    )
                except Exception as e:
                    logger.error(f"发送最终消息到 {target_channel} 失败: {e}")
```

### 4. 监听模块重构

#### 4.1 功能特性分析
基于对原代码的深入分析，监听模块具有以下核心特性：

**实时监听与转发**
- **实时监听**：实时监听多个源频道的新消息，自动转发到目标频道
- **媒体组处理**：支持媒体组的完整收集、缓存、补全与原子性转发，保证媒体组消息的完整性
- **转发限制处理**：支持单条消息和媒体组的转发限制处理（如禁止转发频道的特殊处理）

**高级过滤系统**
- **关键词过滤**：支持关键词过滤，只转发包含指定关键词的消息
- **媒体类型过滤**：支持媒体类型过滤，可排除特定媒体类型
- **文本替换功能**：支持批量文本替换，可修改消息标题和文本内容
- **排除选项**：支持排除转发消息、回复消息、纯文本消息、含链接消息等
- **标题移除**：支持移除媒体说明文字（caption）

**性能与资源管理**
- **性能监控**：内置性能监控（内存占用、处理耗时、消息速率等）
- **消息ID缓冲区**：使用高效的消息ID缓冲区，防止重复处理
- **媒体组缓存**：支持媒体组缓存，定期清理，优化内存使用
- **定期清理**：定期清理已处理消息ID和媒体组缓存

**事件系统集成**
- **监听状态事件**：监听开始/停止、状态更新等事件
- **消息处理事件**：消息接收、消息过滤、关键词命中、消息处理完成等
- **转发状态事件**：转发状态更新、转发成功/失败等
- **文本处理事件**：文本替换、文本过滤等
- **性能监控事件**：内存使用、处理速率、错误统计等
- **历史进度事件**：历史消息获取进度、完成状态等

**配置与动态更新**
- **动态热更新**：支持监听配置的动态热更新，运行时自动应用新配置
- **独立配置**：每个监听频道对可独立配置过滤、文本替换、目标频道等参数
- **配置验证**：完善的配置验证和错误处理

**错误处理与网络管理**
- **网络错误处理**：网络错误、FloodWait、API异常等自动处理与重试
- **错误分级**：详细的错误分级与日志记录
- **连接状态检查**：网络错误时自动检查连接状态

#### 4.2 核心组件设计

**Monitor类（监听主控）**
```python
class Monitor:
    """监听模块，监听源频道的新消息，并实时转发到目标频道"""
    
    def __init__(self, client, ui_config_manager, channel_resolver, app=None):
        # 初始化性能监控器
        self.performance_monitor = PerformanceMonitor()
        
        # 初始化增强缓存（替换原来的简单字典缓存）
        self.channel_info_cache = ChannelInfoCache(max_size=500, default_ttl=1800)  # 30分钟TTL
        
        # 初始化消息ID缓冲区（替换原来的简单集合）
        self.processed_messages = MessageIdBuffer(max_size=50000)
        
        # 初始化消息处理器和媒体组处理器
        self.message_processor = MessageProcessor(self.client, self.channel_resolver, self._handle_network_error)
        self.media_group_handler = MediaGroupHandler(self.client, self.channel_resolver, self.message_processor)
        
        # 存储所有监听的频道ID
        self.monitored_channels = set()
        
        # 定期清理任务
        self.cleanup_task = None
        self.memory_monitor_task = None
    
    async def start_monitoring(self):
        """开始监听所有配置的频道"""
        # 重新从配置文件读取最新配置
        ui_config = self.ui_config_manager.reload_config()
        self.config = convert_ui_config_to_dict(ui_config)
        self.monitor_config = self.config.get('MONITOR', {})
        
        # 解析所有源频道及其目标频道
        channel_pairs = {}
        for pair in self.monitor_config.get('monitor_channel_pairs', []):
            source_channel = pair.get('source_channel', '')
            if source_channel:
                source_id = await self.channel_resolver.get_channel_id(source_channel)
                self.monitored_channels.add(source_id)
                channel_pairs[source_id] = pair
        
        # 注册消息处理器
        handler = MessageHandler(self._handle_new_message, filters.chat(list(self.monitored_channels)))
        self.client.add_handler(handler)
        
        # 启动清理任务
        self.cleanup_task = asyncio.create_task(self._cleanup_processed_messages())
        self.memory_monitor_task = asyncio.create_task(self._monitor_memory_usage())
        
        # 启动媒体组清理任务
        self.media_group_handler.start_cleanup_task()
```

**MediaGroupHandler类（媒体组处理器）**
```python
class MediaGroupHandler:
    """媒体组处理器，负责处理和转发媒体组消息"""
    
    def __init__(self, client, channel_resolver, message_processor):
        self.client = client
        self.channel_resolver = channel_resolver
        self.message_processor = message_processor
        
        # 媒体组缓存
        self.media_group_cache = {}
        self.cleanup_task = None
    
    async def handle_media_group_message(self, message, pair_config):
        """处理媒体组消息"""
        media_group_id = message.media_group_id
        
        if media_group_id:
            # 添加到媒体组缓存
            if media_group_id not in self.media_group_cache:
                self.media_group_cache[media_group_id] = {
                    'messages': [],
                    'timestamp': time.time(),
                    'config': pair_config
                }
            
            self.media_group_cache[media_group_id]['messages'].append(message)
            
            # 检查媒体组是否完整
            if await self._is_media_group_complete(media_group_id):
                await self._forward_media_group(media_group_id)
        else:
            # 单条消息，直接处理
            await self.message_processor.forward_message(message, pair_config)
    
    async def _is_media_group_complete(self, media_group_id):
        """检查媒体组是否完整"""
        # 实现媒体组完整性检查逻辑
        pass
    
    async def _forward_media_group(self, media_group_id):
        """转发完整的媒体组"""
        group_data = self.media_group_cache.get(media_group_id)
        if not group_data:
            return
        
        messages = group_data['messages']
        config = group_data['config']
        
        # 转发媒体组
        await self.message_processor.forward_media_group(messages, config)
        
        # 清理缓存
        del self.media_group_cache[media_group_id]
```

**MessageProcessor类（消息处理器）**
```python
class MessageProcessor:
    """消息处理器，负责处理和转发单条消息"""
    
    def __init__(self, client, channel_resolver, network_error_handler=None):
        self.client = client
        self.channel_resolver = channel_resolver
        self.network_error_handler = network_error_handler
        
        # 创建禁止转发处理器
        self.restricted_handler = RestrictedForwardHandler(self.client, self.channel_resolver)
    
    async def forward_message(self, message, pair_config):
        """转发消息到多个目标频道"""
        # 应用过滤规则
        if not self._should_forward_message(message, pair_config):
            return False
        
        # 获取目标频道
        target_channels = await self._get_target_channels(pair_config)
        
        # 检查源频道转发权限
        source_can_forward = await self.channel_resolver.check_forward_permission(message.chat.id)
        
        if source_can_forward:
            # 直接转发
            await self._forward_directly(message, target_channels, pair_config)
        else:
            # 使用禁止转发处理器
            await self.restricted_handler.handle_restricted_forward(message, target_channels, pair_config)
    
    def _should_forward_message(self, message, pair_config):
        """检查是否应该转发消息"""
        # 检查关键词过滤
        if pair_config.get('keywords'):
            if not self._contains_keywords(message, pair_config['keywords']):
                return False
        
        # 检查媒体类型过滤
        if pair_config.get('media_types'):
            if not self._is_media_type_allowed(message, pair_config['media_types']):
                return False
        
        # 检查排除选项
        if pair_config.get('exclude_forwards') and message.forward_from:
            return False
        
        if pair_config.get('exclude_replies') and message.reply_to_message:
            return False
        
        if pair_config.get('exclude_text') and not message.media:
            return False
        
        if pair_config.get('exclude_links') and self._contains_links(message):
            return False
        
        return True
```

**TextFilter类（文本过滤器）**
```python
class TextFilter:
    """文本过滤器，处理关键词过滤和文本替换"""
    
    def __init__(self, monitor_config):
        self.monitor_config = monitor_config
    
    def apply_text_replacements(self, text, text_filter):
        """应用文本替换规则"""
        if not text or not text_filter:
            return text
        
        result_text = text
        for rule in text_filter:
            original_text = rule.get('original_text', '')
            target_text = rule.get('target_text', '')
            
            if original_text and original_text in result_text:
                result_text = result_text.replace(original_text, target_text)
        
        return result_text
    
    def contains_keywords(self, text, keywords):
        """检查文本是否包含关键词"""
        if not text or not keywords:
            return False
        
        text_lower = text.lower()
        for keyword in keywords:
            if keyword.lower() in text_lower:
                return True
        
        return False
```

**性能监控与资源管理**
```python
class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self.memory_usage = []
        self.processing_times = []
        self.error_counts = {'network': 0, 'api': 0, 'other': 0}
    
    def record_memory_usage(self, usage_mb):
        """记录内存使用情况"""
        self.memory_usage.append((time.time(), usage_mb))
        
        # 保持最近1000条记录
        if len(self.memory_usage) > 1000:
            self.memory_usage = self.memory_usage[-1000:]
    
    def record_processing_time(self, duration):
        """记录处理耗时"""
        self.processing_times.append(duration)
        
        # 保持最近1000条记录
        if len(self.processing_times) > 1000:
            self.processing_times = self.processing_times[-1000:]
    
    def record_error(self, error_type):
        """记录错误"""
        if error_type in self.error_counts:
            self.error_counts[error_type] += 1

class ChannelInfoCache:
    """频道信息缓存"""
    
    def __init__(self, max_size=500, default_ttl=1800):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache = {}
    
    def get(self, channel_id):
        """获取频道信息"""
        if channel_id in self.cache:
            info, timestamp = self.cache[channel_id]
            if time.time() - timestamp < self.default_ttl:
                return info
            else:
                del self.cache[channel_id]
        return None
    
    def set(self, channel_id, info):
        """设置频道信息"""
        if len(self.cache) >= self.max_size:
            # 删除最旧的条目
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k][1])
            del self.cache[oldest_key]
        
        self.cache[channel_id] = (info, time.time())

class MessageIdBuffer:
    """消息ID缓冲区"""
    
    def __init__(self, max_size=50000):
        self.max_size = max_size
        self.processed_ids = set()
    
    def add(self, message_id):
        """添加已处理的消息ID"""
        if len(self.processed_ids) >= self.max_size:
            # 清空缓冲区
            self.processed_ids.clear()
        
        self.processed_ids.add(message_id)
    
    def contains(self, message_id):
        """检查消息ID是否已处理"""
        return message_id in self.processed_ids
```

#### 4.3 配置系统设计

**监听配置结构**
```python
MONITOR = {
    "monitor_channel_pairs": [  # 监听频道对列表
        {
            "source_channel": "source_channel_id",  # 源频道
            "target_channels": ["target1", "target2"],  # 目标频道列表
            "media_types": ["photo", "video", "document", "audio", "animation", "sticker", "voice", "video_note"],  # 媒体类型
            "keywords": ["keyword1", "keyword2"],  # 关键词列表
            "text_filter": [  # 文本替换规则
                {"original_text": "A", "target_text": "B"}
            ],
            "exclude_forwards": False,  # 是否排除转发消息
            "exclude_replies": False,   # 是否排除回复消息
            "exclude_text": False,      # 是否排除纯文本消息
            "exclude_links": False,     # 是否排除包含链接的消息
            "remove_captions": False,   # 是否移除媒体说明
            "enabled": True             # 是否启用此频道对监听
        }
    ],
    "duration": "2024-12-31"  # 监听截止日期 (格式: YYYY-MM-DD)
}
```

#### 4.4 事件系统集成

**事件发射器包装**
```python
class EventEmitterMonitor(BaseEventEmitter):
    """基于Qt Signal的监听器包装类"""
    
    # 监听器特有的信号定义
    monitoring_started = Signal()  # 监听开始信号
    monitoring_stopped = Signal()  # 监听停止信号
    new_message_updated = Signal(int, str)  # 新消息更新信号 (消息ID, 来源信息)
    message_received = Signal(int, str)  # 消息接收信号 (消息ID, 来源信息)
    message_filtered = Signal(int, str, str)  # 消息过滤信号 (消息ID, 来源信息, 过滤原因)
    keyword_matched = Signal(int, str)  # 关键词匹配信号 (消息ID, 关键词)
    message_processed = Signal(int)  # 消息处理完成信号 (消息ID)
    forward_updated = Signal(str, str, str, bool, bool)  # 转发状态更新信号 (源消息ID或媒体组显示ID, 源频道显示名, 目标频道显示名, 成功标志, 修改标志)
    text_replaced = Signal(str, str, List)  # 文本替换信号 (原文本, 修改后文本, 替换规则)
    history_progress = Signal(int, int)  # 历史消息获取进度信号 (已获取消息数, 限制数)
    history_complete = Signal(int)  # 历史消息获取完成信号 (总消息数)
    status_updated = Signal(str)  # 状态更新信号
    error_occurred = Signal(str, str)  # 错误信号
    
    def _emit_qt_signal(self, event_type, *args, **kwargs):
        """根据事件类型发射对应的Qt信号"""
        if event_type == "monitoring_started":
            self.monitoring_started.emit()
        elif event_type == "monitoring_stopped":
            self.monitoring_stopped.emit()
        elif event_type == "new_message_updated":
            message_id, source_info = args[0], args[1]
            self.new_message_updated.emit(message_id, source_info)
        elif event_type == "message_received":
            message_id, source_info = args[0], args[1]
            self.message_received.emit(message_id, source_info)
        elif event_type == "message_filtered":
            message_id, source_info, filter_reason = args[0], args[1], args[2]
            self.message_filtered.emit(message_id, source_info, filter_reason)
        elif event_type == "keyword_matched":
            message_id, keyword = args[0], args[1]
            self.keyword_matched.emit(message_id, keyword)
        elif event_type == "message_processed":
            message_id = args[0]
            self.message_processed.emit(message_id)
        elif event_type == "forward_updated":
            source_id, source_name, target_name, success, modified = args[0], args[1], args[2], args[3], args[4]
            self.forward_updated.emit(source_id, source_name, target_name, success, modified)
        elif event_type == "text_replaced":
            original_text, replaced_text, rules = args[0], args[1], args[2]
            self.text_replaced.emit(original_text, replaced_text, rules)
        elif event_type == "history_progress":
            current_count, total_count = args[0], args[1]
            self.history_progress.emit(current_count, total_count)
        elif event_type == "history_complete":
            total_count = args[0]
            self.history_complete.emit(total_count)
        elif event_type == "status_updated":
            status = args[0]
            self.status_updated.emit(status)
        elif event_type == "error_occurred":
            error_message, error_type = args[0], args[1]
            self.error_occurred.emit(error_message, error_type)
```

#### 4.5 错误与性能管理

**网络错误处理**
```python
async def _handle_network_error(self, error):
    """处理网络相关错误"""
    logger.error(f"检测到网络错误: {type(error).__name__}: {error}")
    
    # 记录错误统计
    if self.performance_monitor:
        error_name = type(error).__name__.lower()
        if any(net_err in error_name for net_err in ['network', 'connection', 'timeout', 'socket']):
            self.performance_monitor.record_error('network')
        elif 'api' in error_name or 'telegram' in error_name:
            self.performance_monitor.record_error('api')
        else:
            self.performance_monitor.record_error('other')
    
    # 通知应用程序立即检查连接状态
    if self.app and hasattr(self.app, 'check_connection_status_now'):
        try:
            asyncio.create_task(self.app.check_connection_status_now())
        except Exception as e:
            logger.error(f"触发连接状态检查失败: {e}")
```

**性能监控任务**
```python
async def _monitor_memory_usage(self):
    """监控内存使用情况"""
    while not self.should_stop:
        try:
            # 获取当前内存使用情况
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            
            # 记录内存使用
            if self.performance_monitor:
                self.performance_monitor.record_memory_usage(memory_mb)
            
            # 发射内存使用事件
            if self.emit:
                self.emit("memory_usage", memory_mb)
            
            await asyncio.sleep(60)  # 每分钟检查一次
            
        except Exception as e:
            logger.error(f"内存监控失败: {e}")
            await asyncio.sleep(60)

async def _cleanup_processed_messages(self):
    """清理已处理的消息ID"""
    while not self.should_stop:
        try:
            # 清理过期的消息ID
            if hasattr(self.processed_messages, 'cleanup'):
                self.processed_messages.cleanup()
            
            # 清理过期的媒体组缓存
            if hasattr(self.media_group_handler, 'cleanup_expired_groups'):
                await self.media_group_handler.cleanup_expired_groups()
            
            await asyncio.sleep(300)  # 每5分钟清理一次
            
        except Exception as e:
            logger.error(f"清理任务失败: {e}")
            await asyncio.sleep(300)
```

#### 4.6 重构后的插件化设计

**监听插件基类**
```python
class BaseMonitorPlugin(Plugin):
    """监听插件基类"""
    
    def __init__(self, client, config):
        super().__init__(client, config)
        self.monitor_config = config.get('MONITOR', {})
        self.general_config = config.get('GENERAL', {})
    
    async def start_monitoring(self):
        """开始监听"""
        raise NotImplementedError
    
    async def stop_monitoring(self):
        """停止监听"""
        raise NotImplementedError
```

**智能监听插件**
```python
class SmartMonitorPlugin(BaseMonitorPlugin):
    """智能监听插件，支持多种监听策略"""
    
    def __init__(self, client, config):
        super().__init__(client, config)
        
        # 初始化性能监控器
        self.performance_monitor = PerformanceMonitor()
        
        # 初始化缓存和缓冲区
        self.channel_info_cache = ChannelInfoCache(max_size=500, default_ttl=1800)
        self.processed_messages = MessageIdBuffer(max_size=50000)
        
        # 初始化处理器
        self.message_processor = MessageProcessor(client, self.channel_resolver, self._handle_network_error)
        self.media_group_handler = MediaGroupHandler(client, self.channel_resolver, self.message_processor)
        self.text_filter = TextFilter(self.monitor_config)
        
        # 设置事件发射器
        self.media_group_handler.emit = self.emit
        self.message_processor.emit = self.emit
    
    async def start_monitoring(self):
        """开始监听所有配置的频道"""
        # 重新从配置文件读取最新配置
        ui_config = self.ui_config_manager.reload_config()
        self.config = convert_ui_config_to_dict(ui_config)
        self.monitor_config = self.config.get('MONITOR', {})
        
        # 解析所有源频道
        monitored_channels = set()
        channel_pairs = {}
        
        for pair in self.monitor_config.get('monitor_channel_pairs', []):
            if not pair.get('enabled', True):
                continue
            
            source_channel = pair.get('source_channel', '')
            if source_channel:
                source_id = await self.channel_resolver.get_channel_id(source_channel)
                monitored_channels.add(source_id)
                channel_pairs[source_id] = pair
        
        # 注册消息处理器
        handler = MessageHandler(self._handle_new_message, filters.chat(list(monitored_channels)))
        self.client.add_handler(handler)
        
        # 启动监控任务
        self.cleanup_task = asyncio.create_task(self._cleanup_processed_messages())
        self.memory_monitor_task = asyncio.create_task(self._monitor_memory_usage())
        self.media_group_handler.start_cleanup_task()
        
        # 发射监听开始事件
        if self.emit:
            self.emit("monitoring_started")
    
    async def _handle_new_message(self, client, message):
        """处理新消息"""
        try:
            # 检查是否已处理
            if self.processed_messages.contains(message.id):
                return
            
            # 标记为已处理
            self.processed_messages.add(message.id)
            
            # 获取频道对配置
            pair_config = self._get_pair_config(message.chat.id)
            if not pair_config:
                return
            
            # 检查是否应该转发
            if not self._should_forward_message(message, pair_config):
                return
            
            # 处理消息
            if message.media_group_id:
                # 媒体组消息
                await self.media_group_handler.handle_media_group_message(message, pair_config)
            else:
                # 单条消息
                await self.message_processor.forward_message(message, pair_config)
            
            # 发射消息处理完成事件
            if self.emit:
                self.emit("message_processed", message.id)
                
        except Exception as e:
            logger.error(f"处理消息失败: {e}")
            if self.emit:
                self.emit("error_occurred", str(e), "message_processing")
    
    def _should_forward_message(self, message, pair_config):
        """检查是否应该转发消息"""
        # 应用所有过滤规则
        if not self.text_filter.should_forward_message(message, pair_config):
            return False
        
        return True
    
    def _get_pair_config(self, chat_id):
        """获取频道对配置"""
        # 根据chat_id查找对应的配置
        for pair in self.monitor_config.get('monitor_channel_pairs', []):
            if pair.get('enabled', True):
                source_channel = pair.get('source_channel', '')
                if source_channel:
                    # 这里需要实现频道ID匹配逻辑
                    pass
        return None
```

### 4. 消息处理抽象层重构

#### 4.1 功能特性分析
基于对原代码的深入分析，转发模块和监听模块在消息处理方面具有大量相似功能：

**共同功能识别**
- **文本替换系统**：两个模块都有完全相同的文本替换逻辑
- **过滤规则系统**：关键词过滤、媒体类型过滤、链接过滤等规则完全一致
- **消息处理流程**：消息接收、过滤、处理、转发的流程高度相似
- **配置结构**：频道对配置、过滤选项、文本替换规则等配置项相同
- **事件系统**：过滤事件、文本替换事件、处理状态事件等事件类型相同

**重复代码问题**
- **TextFilter类**：监听模块有独立的TextFilter类，转发模块有MessageFilter类，功能重复
- **过滤逻辑**：两个模块的过滤逻辑几乎完全相同，但实现分散
- **文本替换**：文本替换逻辑在两个模块中重复实现
- **配置处理**：频道对配置的处理逻辑重复

#### 4.2 抽象层设计

**消息处理抽象基类 (BaseMessageProcessor)**
```python
class BaseMessageProcessor:
    """消息处理抽象基类，提供通用的消息处理功能"""
    
    def __init__(self, client, channel_resolver, emit=None):
        self.client = client
        self.channel_resolver = channel_resolver
        self.emit = emit
        
        # 初始化通用组件
        self.text_processor = TextProcessor()
        self.message_filter = MessageFilter()
        self.media_group_processor = MediaGroupProcessor()
    
    async def process_message(self, message, pair_config):
        """处理单条消息的通用流程"""
        # 1. 应用通用过滤规则
        should_filter, filter_reason = self.message_filter.apply_universal_filters(message, pair_config)
        if should_filter:
            if self.emit:
                self.emit("message_filtered", message.id, "通用过滤", filter_reason)
            return False
        
        # 2. 应用关键词过滤
        if not self.message_filter.apply_keyword_filter(message, pair_config):
            if self.emit:
                self.emit("message_filtered", message.id, "关键词过滤", "不包含关键词")
            return False
        
        # 3. 应用媒体类型过滤
        if not self.message_filter.apply_media_type_filter(message, pair_config):
            if self.emit:
                self.emit("message_filtered", message.id, "媒体类型过滤", "媒体类型不匹配")
            return False
        
        # 4. 处理文本替换
        processed_text, has_replacement = self.text_processor.process_message_text(message, pair_config)
        if has_replacement and self.emit:
            self.emit("text_replacement_applied", "消息文本", message.text, processed_text)
        
        # 5. 子类实现具体的转发逻辑
        return await self._forward_message(message, pair_config, processed_text)
    
    async def _forward_message(self, message, pair_config, processed_text):
        """子类需要实现的转发逻辑"""
        raise NotImplementedError
```

**文本处理器 (TextProcessor)**
```python
class TextProcessor:
    """统一的文本处理器，处理文本替换和文本相关操作"""
    
    def __init__(self):
        self.logger = get_logger()
    
    def process_message_text(self, message, pair_config):
        """处理消息文本，包括文本替换和标题移除"""
        # 获取原始文本
        text = self._extract_text_from_message(message)
        if not text:
            return None, False
        
        # 应用文本替换
        text_replacements = self._build_text_replacements(pair_config)
        processed_text, has_replacement = self.apply_text_replacements(text, text_replacements)
        
        # 处理标题移除
        should_remove_caption = pair_config.get('remove_captions', False)
        if should_remove_caption and self._is_media_message(message):
            processed_text = None
            has_replacement = True
        
        return processed_text, has_replacement
    
    def apply_text_replacements(self, text, text_replacements):
        """应用文本替换规则"""
        if not text or not text_replacements:
            return text, False
        
        result_text = text
        has_replacement = False
        
        for find_text, replace_text in text_replacements.items():
            if find_text and find_text in result_text:
                result_text = result_text.replace(find_text, replace_text)
                has_replacement = True
                self.logger.debug(f"文本替换: '{find_text}' -> '{replace_text}'")
        
        return result_text, has_replacement
    
    def _extract_text_from_message(self, message):
        """从消息中提取文本内容"""
        return message.text or message.caption or ""
    
    def _build_text_replacements(self, pair_config):
        """构建文本替换规则字典"""
        text_replacements = {}
        text_filter_list = pair_config.get('text_filter', [])
        
        for rule in text_filter_list:
            if isinstance(rule, dict):
                original_text = rule.get('original_text', '')
                target_text = rule.get('target_text', '')
                if original_text:  # 只添加非空的原文
                    text_replacements[original_text] = target_text
        
        return text_replacements
    
    def _is_media_message(self, message):
        """检查是否为媒体消息"""
        return bool(message.media)
```

**统一消息过滤器 (MessageFilter)**
```python
class MessageFilter:
    """统一的消息过滤器，提供所有过滤功能"""
    
    def __init__(self):
        self.logger = get_logger()
    
    def apply_universal_filters(self, message, pair_config):
        """应用通用过滤规则（最高优先级）"""
        # 排除转发消息
        if pair_config.get('exclude_forwards', False) and (message.forward_from or message.forward_from_chat):
            return True, "转发消息"
        
        # 排除回复消息
        if pair_config.get('exclude_replies', False) and message.reply_to_message:
            return True, "回复消息"
        
        # 排除纯文本消息
        if pair_config.get('exclude_text', False) and not message.media:
            return True, "纯文本消息"
        
        # 排除包含链接的消息
        if pair_config.get('exclude_links', False) and self._contains_links(message):
            return True, "包含链接"
        
        return False, ""
    
    def apply_keyword_filter(self, message, pair_config):
        """应用关键词过滤"""
        keywords = pair_config.get('keywords', [])
        if not keywords:
            return True
        
        text = message.text or message.caption or ""
        if not text:
            return False
        
        # 检查是否包含关键词
        for keyword in keywords:
            if keyword.lower() in text.lower():
                self.logger.info(f"消息 [ID: {message.id}] 匹配关键词: {keyword}")
                return True
        
        return False
    
    def apply_media_type_filter(self, message, pair_config):
        """应用媒体类型过滤"""
        allowed_media_types = pair_config.get('media_types', [])
        if not allowed_media_types:
            return True
        
        message_media_type = self._get_message_media_type(message)
        if not message_media_type:
            return True  # 纯文本消息，如果没有明确排除则通过
        
        return message_media_type in allowed_media_types
    
    def _contains_links(self, message):
        """检查消息是否包含链接"""
        text = message.text or message.caption or ""
        if not text:
            return False
        
        # 检查文本中的链接模式
        link_patterns = [
            r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
            r'www\.(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
            r't\.me/[a-zA-Z0-9_]+',
            r'telegram\.me/[a-zA-Z0-9_]+'
        ]
        
        for pattern in link_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        # 检查消息实体中的链接
        entities = getattr(message, 'entities', []) or []
        for entity in entities:
            if entity.type in ['url', 'text_link']:
                return True
        
        return False
    
    def _get_message_media_type(self, message):
        """获取消息的媒体类型"""
        if not message.media:
            return None
        
        media_type_map = {
            'photo': 'photo',
            'video': 'video',
            'document': 'document',
            'audio': 'audio',
            'animation': 'animation',
            'sticker': 'sticker',
            'voice': 'voice',
            'video_note': 'video_note'
        }
        
        return media_type_map.get(message.media.value, None)
```

**媒体组处理器 (MediaGroupProcessor)**
```python
class MediaGroupProcessor:
    """统一的媒体组处理器，处理媒体组相关操作"""
    
    def __init__(self):
        self.logger = get_logger()
        self.media_group_cache = {}
    
    def process_media_group_message(self, message, pair_config):
        """处理媒体组消息"""
        media_group_id = message.media_group_id
        
        if media_group_id:
            # 添加到媒体组缓存
            if media_group_id not in self.media_group_cache:
                self.media_group_cache[media_group_id] = {
                    'messages': [],
                    'timestamp': time.time(),
                    'config': pair_config
                }
            
            self.media_group_cache[media_group_id]['messages'].append(message)
            
            # 检查媒体组是否完整
            if self._is_media_group_complete(media_group_id):
                return self._get_complete_media_group(media_group_id)
        
        return None  # 单条消息或媒体组不完整
    
    def _is_media_group_complete(self, media_group_id):
        """检查媒体组是否完整"""
        # 实现媒体组完整性检查逻辑
        # 这里可以根据实际需求实现更复杂的检查
        return True
    
    def _get_complete_media_group(self, media_group_id):
        """获取完整的媒体组"""
        group_data = self.media_group_cache.get(media_group_id)
        if not group_data:
            return None
        
        messages = group_data['messages']
        config = group_data['config']
        
        # 清理缓存
        del self.media_group_cache[media_group_id]
        
        return messages, config
```

#### 4.3 重构后的插件化设计

**转发插件重构**
```python
class SmartForwardPlugin(BaseForwardPlugin):
    """智能转发插件，使用消息处理抽象层"""
    
    def __init__(self, client, config):
        super().__init__(client, config)
        
        # 使用抽象层的消息处理器
        self.message_processor = BaseMessageProcessor(client, self.channel_resolver, self.emit)
        
        # 重写消息处理器以适配转发逻辑
        self.message_processor._forward_message = self._forward_message_implementation
    
    async def _forward_message_implementation(self, message, pair_config, processed_text):
        """实现转发逻辑"""
        # 获取目标频道
        target_channels = await self._get_target_channels(pair_config)
        
        # 检查源频道转发权限
        source_can_forward = await self.channel_resolver.check_forward_permission(message.chat.id)
        
        if source_can_forward:
            # 直接转发
            await self._forward_directly(message, target_channels, pair_config, processed_text)
        else:
            # 使用禁止转发处理器
            await self.restricted_handler.handle_restricted_forward(message, target_channels, pair_config, processed_text)
        
        return True
```

**监听插件重构**
```python
class SmartMonitorPlugin(BaseMonitorPlugin):
    """智能监听插件，使用消息处理抽象层"""
    
    def __init__(self, client, config):
        super().__init__(self, client, config)
        
        # 使用抽象层的消息处理器
        self.message_processor = BaseMessageProcessor(client, self.channel_resolver, self.emit)
        
        # 重写消息处理器以适配监听逻辑
        self.message_processor._forward_message = self._forward_message_implementation
    
    async def _forward_message_implementation(self, message, pair_config, processed_text):
        """实现监听转发逻辑"""
        # 获取目标频道
        target_channels = await self._get_target_channels(pair_config)
        
        # 检查源频道转发权限
        source_can_forward = await self.channel_resolver.check_forward_permission(message.chat.id)
        
        if source_can_forward:
            # 直接转发
            await self._forward_directly(message, target_channels, pair_config, processed_text)
        else:
            # 使用禁止转发处理器
            await self.restricted_handler.handle_restricted_forward(message, target_channels, pair_config, processed_text)
        
        return True
```

#### 4.4 配置系统统一

**统一配置模型**
```python
class UnifiedChannelPairConfig:
    """统一的频道对配置模型"""
    
    def __init__(self, config_dict):
        self.source_channel = config_dict.get('source_channel', '')
        self.target_channels = config_dict.get('target_channels', [])
        self.media_types = config_dict.get('media_types', [])
        self.keywords = config_dict.get('keywords', [])
        self.text_filter = config_dict.get('text_filter', [])
        self.exclude_forwards = config_dict.get('exclude_forwards', False)
        self.exclude_replies = config_dict.get('exclude_replies', False)
        self.exclude_text = config_dict.get('exclude_text', False)
        self.exclude_links = config_dict.get('exclude_links', False)
        self.remove_captions = config_dict.get('remove_captions', False)
        self.enabled = config_dict.get('enabled', True)
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            'source_channel': self.source_channel,
            'target_channels': self.target_channels,
            'media_types': self.media_types,
            'keywords': self.keywords,
            'text_filter': self.text_filter,
            'exclude_forwards': self.exclude_forwards,
            'exclude_replies': self.exclude_replies,
            'exclude_text': self.exclude_text,
            'exclude_links': self.exclude_links,
            'remove_captions': self.remove_captions,
            'enabled': self.enabled
        }
```

#### 4.5 事件系统统一

**统一事件发射器**
```python
class UnifiedEventEmitter:
    """统一的事件发射器，提供标准的事件接口"""
    
    def __init__(self, emit_function=None):
        self.emit = emit_function
    
    def emit_message_filtered(self, message_id, filter_type, filter_reason):
        """发射消息过滤事件"""
        if self.emit:
            self.emit("message_filtered", message_id, filter_type, filter_reason)
    
    def emit_text_replacement_applied(self, message_desc, original_text, replaced_text):
        """发射文本替换事件"""
        if self.emit:
            self.emit("text_replacement_applied", message_desc, original_text, replaced_text)
    
    def emit_message_processed(self, message_id):
        """发射消息处理完成事件"""
        if self.emit:
            self.emit("message_processed", message_id)
    
    def emit_forward_completed(self, message_id, target_info, success):
        """发射转发完成事件"""
        if self.emit:
            self.emit("forward_completed", message_id, target_info, success)
```

#### 4.6 重构收益

**代码重复减少**
- **文本替换逻辑**：从2个独立实现减少到1个统一实现
- **过滤规则逻辑**：从2个独立实现减少到1个统一实现
- **配置处理逻辑**：从2个独立实现减少到1个统一实现
- **事件处理逻辑**：从2个独立实现减少到1个统一实现

**维护性提升**
- **单一职责**：每个抽象类只负责一个特定功能
- **易于测试**：抽象层可以独立测试，提高测试覆盖率
- **易于扩展**：新功能可以通过继承抽象类实现
- **配置统一**：统一的配置模型减少配置错误

**功能一致性**
- **过滤行为一致**：转发和监听的过滤行为完全一致
- **文本替换一致**：文本替换逻辑和行为完全一致
- **事件格式一致**：事件格式和内容完全一致
- **错误处理一致**：错误处理和日志记录完全一致

### 5. 监听模块重构

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
- [ ] 实现多目标上传优化（消息复制策略）
- [ ] 实现最终消息发送功能（HTML支持）
- [ ] 实现网络错误处理和重试机制
- [ ] 实现事件系统集成（进度、完成、错误事件）
- [ ] 实现视频缩略图自动生成
- [ ] 实现媒体组分块上传（超过10个文件）
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
- [ ] 顺序下载（舍弃并行下载）

#### 上传功能
- [ ] 本地文件上传
- [ ] 媒体组上传
- [ ] 上传进度跟踪
- [ ] 文件哈希检查
- [ ] 重复文件跳过
- [ ] 缩略图生成
- [ ] 最终消息发送
- [ ] 多目标上传优化（消息复制策略）
- [ ] 网络错误处理和重试机制
- [ ] 事件系统集成（进度、完成、错误事件）
- [ ] 媒体组分块上传（超过10个文件）
- [ ] HTML最终消息支持
- [ ] 网页预览控制
- [ ] 文件类型自动识别
- [ ] 上传历史管理

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
- **下载功能简化**：只保留顺序下载，舍弃并行下载功能
- **上传功能完善**：保持所有上传功能，包括多目标优化、最终消息、事件系统等

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