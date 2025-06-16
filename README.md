# TG-Manager - 专业Telegram消息转发管理器

## 📋 项目简介

TG-Manager 是一个专业的Telegram消息转发和管理工具，基于Python和Pyrogram构建，提供高效、稳定的消息转发服务。

## ✨ 核心特性

### 🚀 v2.1.9 - Pyropatch FloodWait处理器集成 (最新版本)

**专业级FloodWait处理升级**：
- **🔧 Pyropatch集成**: 集成社区成熟的pyropatch库，提供更专业、更稳定的FloodWait处理能力
- **🎯 零配置自动启用**: 客户端创建时自动检测并启用pyropatch FloodWait处理器
- **🔄 智能回退机制**: pyropatch不可用时自动回退到内置FloodWait处理器，确保100%可用性
- **💼 完全向后兼容**: 保持与现有代码的100%兼容性，无需修改任何业务逻辑

**技术亮点**：
```python
# 自动检测并启用最佳FloodWait处理器
if PYROPATCH_AVAILABLE and is_pyropatch_available():
    # 使用pyropatch专业级处理器
    success = setup_pyropatch_for_client(client, max_retries=5)
else:
    # 回退到内置处理器
    enable_global_flood_wait_handling(client, max_retries=5)

# 所有API调用现在都会自动处理FloodWait
await client.send_message("me", "Hello")  # 自动处理FloodWait
await client.download_media(message)      # 自动处理FloodWait
await client.send_media_group(...)        # 自动处理FloodWait
```

**转发模块全面升级**：
- **MessageDownloader**: 优先使用pyropatch进行媒体下载FloodWait处理
- **MediaUploader**: 智能选择最佳FloodWait处理器进行媒体上传
- **MessageIterator**: 消息获取操作的pyropatch支持
- **ParallelProcessor**: 并行处理中的FloodWait处理升级

### 🛡️ v2.1.8 - FloodWait处理终极优化

**100%确保FloodWait处理器生效**：
- **🎯 问题彻底解决**：彻底解决"限流时间大于默认的10秒，还是没有触发flood_wait_handler"的问题
- **🔧 双重保障机制**：全局API拦截 + 方法级显式包装，确保所有FloodWait都被自定义处理器接管
- **📊 完美的进度显示**：长时间等待显示详细进度："FloodWait等待中... 50.0% (9秒剩余)"
- **⚡ 智能处理策略**：短时间直接等待，长时间分段显示，异常安全恢复

### 🛡️ v2.1.7 - 关键稳定性修复 (稳定版本)

**客户端连接问题彻底解决**：
- **✅ 简化客户端配置**：移除复杂参数，使用Pyrogram标准配置，确保100%连接成功
- **✅ 会话管理优化**：删除复杂的锁文件机制，与Pyrogram内置会话管理完全兼容
- **✅ 错误处理简化**：修复QTimer作用域问题，简化异常处理逻辑
- **✅ 稳定性提升**：解决用户报告的"unable to open database file"等连接问题

### 🚀 FloodWait处理技术栈

#### 三层FloodWait处理架构
1. **Pyropatch处理器** (v2.1.9新增，最优选择)
   - 基于社区成熟的pyropatch库
   - 专业级monkey-patch技术
   - 与Pyrogram完美兼容
   - 自动处理所有API调用

2. **内置GlobalPatcher** (v2.1.5引入，备选方案)
   - 自研全局API拦截技术
   - 覆盖17个核心API方法
   - 智能进度显示和重试机制

3. **方法级包装器** (v2.1.2基础方案)
   - execute_with_flood_wait便捷函数
   - handle_flood_wait装饰器
   - FloodWaitHandler处理器类

#### 智能选择机制
```python
# 系统自动选择最佳可用的FloodWait处理器
if pyropatch_available:
    使用pyropatch专业级处理器
elif global_patcher_available:
    使用内置全局拦截器  
else:
    使用方法级包装器
```

### 📡 消息监听与转发
- **实时监听**：支持多个源频道同时监听
- **智能过滤**：基于关键词、消息类型等多维度过滤
- **批量转发**：支持媒体组批量转发，保持原有格式

### 🎯 并行处理架构
- **🔄 完全并行**：下载和上传采用生产者-消费者模式真正并行执行
- **⚡ 流水线处理**：下载第一个媒体组完成后，上传立即开始，同时下载第二个
- **🚀 性能优化**：
  - 缩略图生成最多3个并发FFmpeg进程
  - 队列缓冲机制防止内存溢出
  - 智能任务调度和资源管理
- **📊 效率提升**：相比串行处理，性能提升3-5倍

### 🎨 现代化UI界面
- **基于PySide6**：现代化的桌面应用界面
- **Material Design**：采用Material Design设计风格
- **响应式布局**：支持窗口大小调整，适配不同分辨率
- **实时状态显示**：连接状态、转发进度实时更新

### 🔐 安全与稳定性
- **安全认证**：支持两步验证(2FA)登录
- **代理支持**：支持HTTP/SOCKS代理配置
- **错误恢复**：完善的错误处理和自动重连机制
- **会话管理**：安全的会话文件管理和加密存储

### 🧹 资源管理与清理
- **启动时自动清理**：程序启动时自动清理临时下载目录，释放磁盘空间
- **智能空间管理**：自动统计和清理临时文件，显示释放的存储空间
- **安全删除机制**：安全删除临时文件和目录，避免数据残留
- **资源使用监控**：实时监控磁盘使用情况，及时清理无用文件

## 🚀 快速开始

### 1. 环境要求
- Python 3.8+
- 有效的Telegram API凭据 (api_id, api_hash)

### 2. 安装依赖

使用清华大学镜像源加速安装：
```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**重要依赖说明**：
- **pyropatch**: 专业级FloodWait处理器（推荐）
- **pyrogram**: Telegram客户端核心库
- **PySide6**: 现代化UI框架

### 3. 配置设置
1. 启动程序后，进入设置页面
2. 填入Telegram API凭据
3. 配置代理（如需要）
4. 设置转发规则和过滤条件

### 4. 开始使用
1. 点击登录，完成Telegram认证
2. 添加监听频道和目标频道
3. 启动监听，开始自动转发

## 📁 项目结构

```
TG-Manager/
├── src/
│   ├── modules/           # 功能模块
│   │   ├── forward/      # 转发模块（下载、上传、并行处理）
│   │   ├── monitor/      # 监听模块
│   │   └── downloader.py # 批量下载器
│   ├── ui/               # 用户界面
│   │   ├── views/        # 各种视图页面
│   │   └── components/   # UI组件
│   ├── utils/            # 工具模块
│   │   ├── pyropatch_flood_handler.py    # Pyropatch FloodWait处理器
│   │   ├── flood_wait_handler.py         # 内置FloodWait处理器
│   │   ├── client_manager.py             # 客户端管理
│   │   └── config_utils.py               # 配置管理
│   └── config/           # 配置文件
├── sessions/             # 会话文件目录
├── downloads/            # 下载文件目录
└── requirements.txt      # 依赖列表
```

## 🔧 核心模块说明

### Pyropatch FloodWait处理器 (`src/utils/pyropatch_flood_handler.py`)
- **PyropatchFloodWaitManager**: 基于pyropatch的专业级FloodWait管理器
- **setup_pyropatch_for_client**: 为客户端启用pyropatch FloodWait处理
- **execute_with_pyropatch_flood_wait**: 便捷的执行函数
- **智能回退机制**: pyropatch不可用时自动使用内置处理器

### 内置FloodWait处理器 (`src/utils/flood_wait_handler.py`)
- **FloodWaitHandler类**：核心处理器，提供智能等待和重试机制
- **execute_with_flood_wait**：便捷函数，适用于大多数场景
- **handle_flood_wait装饰器**：装饰器方式，适用于函数定义
- **GlobalFloodWaitPatcher**：全局补丁器，为所有API调用提供保护

### 转发模块 (`src/modules/forward/`)
- **MessageDownloader**：消息下载器，集成pyropatch FloodWait处理
- **MediaUploader**：媒体上传器，支持批量上传和格式转换
- **ParallelProcessor**：并行处理器，实现真正的并行下载上传

### 监听模块 (`src/modules/monitor/`)
- **Monitor**：核心监听器，实时监听消息并触发转发
- **MediaGroupHandler**：媒体组处理器，处理图片、视频等媒体组合

## ⚙️ 配置说明

### API配置
```json
{
  "GENERAL": {
    "api_id": "your_api_id",
    "api_hash": "your_api_hash",
    "phone_number": "your_phone_number"
  }
}
```

### 监听配置
```json
{
  "MONITOR": {
    "channel_pairs": {
      "source_channel_id": {
        "target_channel": "target_channel_id",
        "filters": ["keyword1", "keyword2"]
      }
    }
  }
}
```

## 🎯 使用场景

### 1. 内容聚合
- 从多个新闻频道聚合内容到统一频道
- 按主题分类转发不同类型的内容

### 2. 媒体备份
- 自动备份重要频道的媒体文件
- 批量下载历史消息和媒体

### 3. 社群管理
- 在多个相关群组间同步消息
- 筛选并转发优质内容

### 4. 内容分发
- 将内容从私人频道分发到公开频道
- 根据不同受众定制转发规则

## 🛠️ FloodWait处理使用指南

### 自动启用（推荐）
程序启动时自动检测并启用最佳FloodWait处理器：
```python
# 无需额外配置，系统自动处理
client = await client_manager.create_client()
# 自动启用pyropatch或内置处理器
```

### 手动选择处理器
```python
# 1. 优先使用pyropatch处理器
from src.utils.pyropatch_flood_handler import setup_pyropatch_for_client
success = setup_pyropatch_for_client(client, max_retries=5)

# 2. 使用内置全局处理器
from src.utils.flood_wait_handler import enable_global_flood_wait_handling  
enable_global_flood_wait_handling(client, max_retries=5)

# 3. 使用便捷函数
from src.utils.pyropatch_flood_handler import execute_with_pyropatch_flood_wait
result = await execute_with_pyropatch_flood_wait(
    client.get_messages, "channel", limit=100
)
```

### FloodWait处理器对比

| 特性 | Pyropatch处理器 | 内置处理器 | 方法级包装器 |
|------|-----------------|------------|--------------|
| 成熟度 | 社区成熟方案 | 自研方案 | 基础方案 |
| 兼容性 | 优秀 | 良好 | 良好 |
| 性能 | 最佳 | 良好 | 一般 |
| 自动化程度 | 全自动 | 全自动 | 手动 |
| 维护成本 | 最低 | 中等 | 较高 |

## 📝 开发指南

### 代码规范
- 遵循PEP 8编码规范
- 使用类型提示(Type Hints)
- 完整的文档字符串(Docstring)

### 测试
```bash
# 运行单元测试
pytest tests/

# 运行FloodWait处理器测试
pytest tests/test_pyropatch_flood_handler.py
```

### 贡献
1. Fork项目
2. 创建功能分支
3. 提交更改
4. 发起Pull Request

## 📄 许可证

本项目采用MIT许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🤝 支持

- 📧 邮箱支持：[your-email@example.com]
- 💬 问题反馈：[GitHub Issues](https://github.com/your-username/TG-Manager/issues)
- 📚 文档：[项目Wiki](https://github.com/your-username/TG-Manager/wiki)

## 🙏 致谢

感谢以下开源项目的贡献：
- [Pyrogram](https://github.com/pyrogram/pyrogram) - Telegram客户端库
- [Pyropatch](https://github.com/rahulps1000/pyropatch) - 专业级Pyrogram monkey-patch库
- [PySide6](https://doc.qt.io/qtforpython/) - 跨平台GUI框架
- [loguru](https://github.com/Delgan/loguru) - 现代化日志库

## 🚨 防止长时间FloodWait的重要提示

### auth.ExportAuthorization FloodWait预防

如果您遇到`auth.ExportAuthorization`引起的长时间FloodWait（如3000+秒），这通常是由以下原因引起的：

#### 🔍 **问题原因**
- **数据中心授权冲突**：多个进程同时使用相同会话文件
- **频繁的客户端重启**：短时间内多次启动/停止客户端
- **会话文件损坏**：不完整或损坏的会话文件导致重复授权

#### 🛡️ **预防措施**
1. **确保单一进程**：同一时间只运行一个TG-Manager实例
2. **稳定的网络连接**：避免频繁的网络中断导致重连
3. **正确关闭程序**：使用程序的退出功能，避免强制终止

#### 🔧 **遇到问题时的解决方案**
```bash
# 1. 完全关闭程序
# 2. 删除会话锁文件（如果存在）
rm sessions/tg_manager.lock

# 3. 如果问题持续，考虑重新登录
# 删除会话文件（需要重新登录）
rm sessions/tg_manager.session*

# 4. 重新启动程序
```

#### ⚡ **v2.1.9增强保护**
- **Pyropatch专业处理**：使用社区成熟的FloodWait处理方案
- **智能回退机制**：多重处理器保障，确保FloodWait始终被正确处理
- **自动检测启用**：无需手动配置，系统自动选择最佳处理器

---

**⭐ 如果这个项目对您有帮助，请给我们一个Star！**