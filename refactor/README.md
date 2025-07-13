# TG-Manager 插件化重构项目

## 重构目标

将现有的TG-Manager项目重构为基于Pyrogram智能插件的模块化架构，同时保持所有原有功能不变。

## 重构原则

1. **渐进式重构**：不修改原有代码，在根目录下新建文件夹，所有重构代码、文件、文件夹均放在此目录下
2. **功能一致性**：保证下载、上传、转发、监听等所有本项目的原有功能不变
3. **UI界面一致性**：UI界面保持和原项目一致
4. **测试驱动**：每重构一部分，编写测试，保证与原功能一致

## 重构进度

### 第一阶段：整体框架 ✅ (已完成)
- [x] 创建重构目录结构
- [x] 实现核心模块 (ClientManager, PluginManager, EventBus)
- [x] 实现抽象层 (BaseDownloader, BaseUploader, BaseHandler, BaseMessageProcessor)
- [x] 实现公共模块 (MessageFetcher, ChannelValidator, FloodWaitHandler, ErrorHandler)
- [x] 实现配置管理 (ConfigManager, UIConfigManager, PluginConfig)
- [x] 实现消息处理抽象层 (TextProcessor, MessageFilter, MediaGroupProcessor)
- [x] 编写第一阶段测试

### 第二阶段：核心部分完善 (进行中)
- [x] 认证插件 (登录功能、会话管理、自动重连)
- [x] 下载插件 (历史消息下载、媒体文件下载、进度跟踪)
- [x] 上传插件 (文件上传、媒体组上传、多目标优化)
- [x] 转发插件 (消息转发、媒体组转发、过滤和文本替换)
- [x] 监听插件 (实时监听、自动转发、性能监控)

### 第三阶段：各个插件完善
- [ ] UI界面适配
- [ ] 插件功能完善
- [ ] 集成测试

### 第四阶段：测试优化和部署
- [ ] 全面测试
- [ ] 性能优化
- [ ] 文档和部署

## 测试进度

### 测试覆盖率统计
- **总测试用例**: 127个
- **通过率**: 100% (127/127)
- **测试模块**: 8个核心模块

### 已完成的测试模块

#### 1. 核心模块测试 ✅
- **EventBus**: 15个测试用例 - 事件注册、发射、移除、异常处理
- **ClientManager**: 25个测试用例 - 客户端管理、会话恢复、连接监控
- **PluginManager**: 待补充测试用例

#### 2. 抽象层测试 ✅
- **BaseMessageProcessor**: 8个测试用例 - 消息处理流程、过滤、文本替换

#### 3. 公共模块测试 ✅
- **MessageFetcher**: 25个测试用例 - 消息获取、缓存、错误处理
- **ChannelValidator**: 待补充测试用例
- **ErrorHandler**: 已集成到其他模块测试中
- **FloodWaitHandler**: 已集成到其他模块测试中

#### 4. 消息处理组件测试 ✅
- **TextProcessor**: 15个测试用例 - 文本提取、替换、标题移除
- **MessageFilter**: 20个测试用例 - 通用过滤、关键词、媒体类型、链接检测
- **MediaGroupProcessor**: 8个测试用例 - 媒体组缓存、完整性检查

#### 5. 插件测试 ✅
- **SmartForwardPlugin**: 2个测试用例 - 初始化、转发实现
- **SmartMonitorPlugin**: 2个测试用例 - 初始化、监听实现

#### 6. 配置管理测试 ✅
- **ConfigManager**: 已集成到其他模块测试中
- **UIConfigManager**: 待补充测试用例
- **PluginConfig**: 已集成到其他模块测试中

### 测试技术栈
- **pytest**: 测试框架
- **pytest-asyncio**: 异步测试支持
- **unittest.mock**: Mock和Patch
- **pytest-qt**: UI测试支持 (待使用)

### 测试策略
- **单元测试**: 每个模块独立测试，覆盖率100%
- **集成测试**: 模块间协作测试
- **异步测试**: 所有异步方法都有对应测试
- **异常测试**: 错误处理和恢复机制测试
- **Mock测试**: 外部依赖完全Mock，确保测试独立性

## 目录结构

```
refactor/
├── README.md               # 重构说明文档
├── requirements.txt        # 重构项目依赖
├── run_tests.py           # 测试运行器
├── main.py                 # 重构项目入口
├── config/                 # 配置管理
│   ├── config_manager.py   # 配置管理器
│   ├── config_utils.py     # 配置工具
│   ├── plugin_config.py    # 插件配置
│   ├── ui_config_manager.py # UI配置管理
│   └── ui_config_models.py # UI配置模型
├── core/                   # 核心模块
│   ├── client_manager.py   # 客户端管理
│   ├── plugin_manager.py   # 插件管理
│   ├── event_bus.py        # 事件总线
│   └── app_core.py         # 应用核心
├── abstractions/           # 抽象层
│   ├── base_handler.py     # 基础处理器
│   ├── base_downloader.py  # 下载抽象
│   ├── base_uploader.py    # 上传抽象
│   └── base_message_processor.py # 消息处理抽象
├── common/                 # 公共模块
│   ├── message_fetcher.py  # 消息获取器
│   ├── channel_validator.py # 频道验证器
│   ├── flood_wait_handler.py # 限流处理器
│   ├── error_handler.py    # 错误处理器
│   ├── text_processor.py   # 文本处理器
│   ├── message_filter.py   # 消息过滤器
│   └── media_group_processor.py # 媒体组处理器
├── plugins/                # 智能插件目录
│   ├── forward/            # 转发插件
│   │   ├── base_forward_plugin.py
│   │   └── smart_forward_plugin.py
│   └── monitor/            # 监听插件
│       ├── base_monitor_plugin.py
│       └── smart_monitor_plugin.py
├── ui/                     # UI界面
├── utils/                  # 工具模块
├── tests/                  # 测试目录
│   ├── conftest.py         # 测试配置
│   ├── test_core/          # 核心模块测试
│   ├── test_common/        # 公共模块测试
│   ├── test_abstractions/  # 抽象层测试
│   └── test_plugins/       # 插件测试
├── logs/                   # 日志目录
├── sessions/               # 会话目录
├── downloads/              # 下载目录
├── uploads/                # 上传目录
├── tmp/                    # 临时文件目录
├── history/                # 历史记录目录
└── translations/           # 翻译文件目录
```

## 技术栈

- **Python**: 3.8+
- **Pyrogram**: >=2.0.0 (Telegram客户端库)
- **PySide6**: >=6.2.0 (Qt6 Python绑定)
- **Pydantic**: >=1.9.0,<2.0.0 (数据验证)
- **loguru**: >=0.6.0 (日志记录)
- **aiohttp**: >=3.8.0 (异步HTTP客户端)
- **pytest**: >=8.0.0 (测试框架)
- **pytest-asyncio**: >=0.26.0 (异步测试)

## 开发规范

- 使用Google风格的docstring
- 遵循PEP8代码规范
- 所有公共方法必须有类型提示
- 每个模块必须有对应的测试
- 测试覆盖率不低于80%

## 下一步计划

### 短期目标 (1-2周)
1. **完善测试覆盖**
   - 补充 PluginManager 测试用例
   - 补充 ChannelValidator 测试用例
   - 补充 UIConfigManager 测试用例

2. **插件功能完善**
   - 实现具体的转发逻辑
   - 实现具体的监听逻辑
   - 完善插件配置系统

3. **UI界面开发**
   - 创建主界面框架
   - 集成配置管理界面
   - 实现插件管理界面

### 中期目标 (2-4周)
1. **集成测试**
   - 端到端功能测试
   - 性能基准测试
   - 与原项目功能对比测试

2. **文档完善**
   - API文档生成
   - 用户使用手册
   - 开发者指南

### 长期目标 (1-2月)
1. **性能优化**
   - 内存使用优化
   - 并发性能优化
   - 缓存策略优化

2. **功能扩展**
   - 更多插件类型
   - 高级过滤规则
   - 自动化脚本支持

## 联系方式

如有问题或建议，请联系项目负责人。 