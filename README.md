# TG-Manager - 专业Telegram消息转发管理器

**版本**: v2.2.43
**更新日期**: 2024-12-22

一个功能强大的 Telegram 消息转发管理工具，支持多频道消息批量转发、实时监听转发、媒体文件上传下载等功能。基于现代化的 Python Qt 界面设计，提供直观的图形化操作体验。

## 📋 项目简介

TG-Manager 是一个专业的Telegram消息转发和管理工具，基于Python和Pyrogram构建，提供高效、稳定的消息转发服务。

## ✨ 核心特性

### 🌐 多语言支持
- **完整的UI国际化**：支持中文和英文界面，所有用户界面元素都已本地化
- **系统级多语言**：包括转发、上传、下载、监听等所有核心功能模块的消息本地化
- **无硬编码文本**：所有用户可见的文本都通过翻译系统管理，确保完整的多语言体验
- **动态语言切换**：在设置中切换语言后，所有界面元素立即更新为对应语言
- **为国际用户友好**：为全球用户提供本地化的使用体验

### 📋 主要功能
- **消息转发**：支持多频道消息批量转发，实时监听转发，支持媒体组转发
- **媒体下载**：从 Telegram 频道下载媒体文件，支持多种格式、关键词过滤、批量下载
- **文件上传**：批量上传本地文件到 Telegram 频道，支持媒体组上传
- **消息监听**：实时监听频道消息并自动转发到指定频道
- **历史记录**：完整的转发历史记录，防止重复转发
- **任务管理**：统一的任务管理界面，实时查看任务状态和进度

### 🔧 高级功能
- **消息过滤**：支持媒体类型过滤、关键词过滤、链接过滤等
- **文本替换**：批量替换消息中的文本内容
- **定时任务**：支持定时转发和批量处理
- **API限流处理**：智能处理Telegram API限流，避免账号被限制
- **错误恢复**：自动重试失败的操作，提高成功率

### 🎨 用户界面
- **现代化界面**：基于Qt6的现代化桌面应用界面
- **深色主题**：支持多种主题切换，包括深色模式
- **实时日志**：实时显示操作日志，便于监控和调试
- **进度跟踪**：详细的进度显示，实时了解任务执行状态

### 🔒 安全特性
- **会话管理**：安全的Telegram会话管理
- **数据加密**：敏感数据加密存储
- **权限控制**：最小权限原则，确保操作安全

## 变更日志

### v2.2.43 (2024-12-22)
**🔧 监听界面国际化修复**
- 修复监听界面初始化时的`AttributeError`错误
- 添加缺失的`_update_translations`方法实现
- 完善监听界面的动态语言切换功能
- 确保所有UI组件都能正确响应语言变更
- 优化翻译更新的异常处理和日志记录

### v2.2.42 (2024-12-22)
**🌐 监听界面完整国际化**
- 完成监听界面的全面国际化支持：
  - 所有UI组件（标签页、按钮、标签、输入框、复选框）的翻译
  - 所有消息和对话框的多语言支持
  - 编辑对话框的完整翻译
  - 右键菜单的本地化
  - 状态显示和日志消息的翻译
- 新增120+个翻译键，涵盖监听界面的所有文本元素
- 支持带参数的翻译（如消息ID、频道名称、错误信息等）
- 实现动态语言切换，无需重启应用
- 优化翻译文件结构，采用层次化组织
- 完善错误处理和日志记录的多语言支持

### v2.2.41 (2024-12-22)
**🌐 上传界面完整国际化**
- 完成上传界面的全面国际化支持：
  - 所有UI组件（标签页、按钮、标签、输入框、复选框）的翻译
  - 所有消息框和对话框的多语言支持
  - 编辑对话框的完整翻译
  - 右键菜单的本地化
  - 状态显示和进度消息的翻译
- 新增100+个翻译键，涵盖上传界面的所有文本元素
- 支持带参数的翻译（如文件数量、大小、时间等）
- 实现动态语言切换，无需重启应用
- 优化翻译文件结构，采用层次化组织
- 完善错误处理和异常消息的多语言支持

### v2.2.40 (2024-12-22)
**🔧 修复和改进**
- 修复转发日志中"过滤"文本的硬编码问题
- 添加翻译键`ui.forward.log.filtered`支持"过滤"文本的多语言显示
- 确保所有用户界面元素都支持完整的多语言切换
- 优化日志显示的一致性和可读性

### v2.2.39 (2024-12-22)
**🌐 系统级多语言支持完善**
- 完成TG-Manager项目的系统级多语言支持
- 修复所有模块中的硬编码中文消息：
  - 消息过滤模块：单个消息、媒体组消息、媒体类型过滤等
  - 并行处理模块：媒体组描述和格式化
  - 媒体上传模块：媒体组文件描述
  - 文件上传模块：媒体组上传事件
  - 下载模块：下载停止提示
- 新增9个翻译键，支持参数化翻译
- 修复各模块的错误导入语句
- 所有UI显示消息现在都支持中英文切换
- 为国际用户提供完全本地化的使用体验

### v2.2.38 (2024-12-21)
**🔧 系统优化和错误修复**
- 修复转发模块中的硬编码中文消息问题
- 新增翻译键支持媒体组转发的多语言显示
- 改进转发日志的用户体验
- 优化转发状态显示的一致性

### v2.2.37 (2024-12-21)
**🎨 界面优化**
- 改进转发界面的布局和用户体验
- 优化媒体组转发的显示效果
- 增强转发日志的可读性

### v2.2.36 (2024-12-20)
**🔧 稳定性改进**
- 优化API限流处理机制
- 改进媒体文件处理流程
- 增强错误恢复能力

### v2.2.35 (2024-12-19)
**🌐 多语言支持**
- 实现完整的UI多语言支持
- 支持中文和英文界面切换
- 优化翻译系统架构

### v2.2.34 (2024-12-18)
**🔧 核心功能优化**
- 改进消息转发算法
- 优化媒体组处理逻辑
- 增强系统稳定性

### v2.2.33 (2024-12-17)
**🎨 用户界面改进**
- 优化主界面布局
- 改进任务管理界面
- 增强用户交互体验

### v2.2.32 (2024-12-16)
**🔧 性能优化**
- 优化媒体文件处理性能
- 改进内存使用效率
- 增强并发处理能力

### v2.2.31 (2024-12-15)
**🌐 国际化支持**
- 添加多语言支持框架
- 实现界面元素的本地化
- 为国际用户提供更好的体验

### 2024-xx-xx v2.2.44
- 修正监听界面"替换为"字段，label为"替换为"，placeholder为详细说明，支持多语言切换。
- 详细说明请见 CHANGELOG.md。

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

### 转发配置
```json
{
  "FORWARD": {
    "forward_channel_pairs": [
      {
        "source_channel": "@source_channel",
        "target_channels": ["@target1", "@target2"],
        "media_types": ["text", "photo", "video", "document", "audio", "animation"],
        "send_final_message": true,
        "final_message_html_file": "/path/to/custom_message.html",
        "text_filter": [
          {"original_text": "原文", "target_text": "替换文"}
        ],
        "keywords": ["关键词1", "关键词2"],
        "remove_captions": false,
        "hide_author": true
      }
    ],
    "forward_delay": 0.5,
    "tmp_path": "tmp"
  }
}
```

#### 最终消息配置说明
- **`send_final_message`**: 是否在转发完成后发送最终消息
- **`final_message_html_file`**: 最终消息HTML文件路径（支持富文本、表情、超链接）
- **频道对级别配置**: 每个频道对可以配置不同的最终消息内容
- **灵活应用场景**: 
  - 营销频道：发送购买链接和优惠信息
  - 新闻频道：发送内容总结和相关链接
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

## 转发功能
转发功能允许您将消息从源频道转发到目标频道，支持多种过滤条件和自定义选项。

### 配置最终消息
可以为每个频道对配置在转发完成后自动发送的最终消息：

```json
{
  "source_channel": "@source",
  "target_channels": ["@target1", "@target2"],
  "enabled": true,
  "send_final_message": true,
  "final_message_html_file": "path/to/message.html"
}
```

### 频道对管理功能
- **禁用/启用功能**：**仅**可通过右键点击频道对选择"禁用"或"启用"
  - 禁用的频道对在转发时会被跳过
  - 禁用状态会在列表中显示为 `[已禁用]` 前缀
  - 可以随时重新启用禁用的频道对
  - 默认所有频道对都是启用状态（`enabled: true`）
  - **注意**：编辑对话框中不再包含启用/禁用选项，避免操作混淆
- **编辑功能**：右键点击可以编辑频道对的其他配置（不包括启用/禁用状态）
- **删除功能**：右键点击可以删除不需要的频道对
- **批量操作**：可以同时选择多个频道对进行删除

### 最终消息调试
如果最终消息未发送，请检查日志中的以下调试信息：

1. **配置加载调试信息**：确认配置是否正确读取
   ```
   === 配置加载调试信息 ===
   加载的 forward_channel_pairs 数量: 1
   加载的频道对 #1 配置:
     - send_final_message: true (类型: <class 'bool'>)
     - final_message_html_file: path/to/file.html
   ```

2. **最终消息发送检查**：确认处理流程
   ```
   === 开始最终消息发送检查 ===
   频道对 #1 详细配置:
     - send_final_message: true (类型: <class 'bool'>)
     - final_message_html_file: path/to/file.html
   ```

3. **文件验证**：确认HTML文件存在且可读取
   ```
   ✅ 频道对 [源频道] HTML文件验证通过
   ✅ 频道对 [源频道] HTML内容读取成功
   ```

4. **发送成功确认**：确认消息发送到目标频道
   ```
   ✅ 最终消息发送成功! 目标: 频道名, 消息ID: 12345
   ```

### 常见问题排查
- **配置未生效**：检查 `send_final_message` 是否为 `true`（布尔值）
- **文件路径问题**：确保 `final_message_html_file` 路径正确且文件存在
- **HTML内容为空**：检查HTML文件是否包含有效内容
- **发送失败**：查看详细错误信息和目标频道权限

## 开发注意事项

### ⚠️ 配置转换重要提醒
当在UI模型中添加新的配置字段时，**必须**同时在 `src/utils/config_utils.py` 的 `convert_ui_config_to_dict` 函数中添加对应的转换逻辑：

1. **频道对配置字段**：需要在 `filter_field` 列表中添加新字段
   ```python
   for filter_field in ["exclude_forwards", "exclude_replies", "exclude_text", "exclude_links", "remove_captions", "hide_author", "send_final_message"]:
       if hasattr(pair, filter_field):
           pair_dict[filter_field] = getattr(pair, filter_field)
   ```

2. **特殊字段处理**：如文件路径等需要单独处理
   ```python
   if hasattr(pair, 'final_message_html_file'):
       pair_dict['final_message_html_file'] = pair.final_message_html_file
   ```

3. **常见遗漏问题**：
   - ❌ 只在UI模型中添加字段，忘记配置转换
   - ❌ 配置在UI中显示正确，但转发时丢失
   - ✅ UI模型 + 配置转换 + 功能实现 三步都要完成

**记住这个教训**：UI配置 → 内部配置的转换是必须的步骤，遗漏会导致配置在运行时丢失！

### 架构设计

## 版本历史 (Version History)

### 最新版本 (Latest Version)

- **v2.2.22** (2025-07-02) - 🐛 **根本问题修复**：彻底解决运行时配置修改导致媒体组文本丢失的根本原因；修复预过滤机制，确保媒体说明完整保留
- **v2.2.21** (2025-07-02) - 🐛 **精准Bug修复**：修复运行时配置修改导致媒体组文本丢失的问题；确保每次转发都重新初始化MediaGroupCollector
- **v2.2.20** (2025-07-02) - 🐛 **重要Bug修复**：修复运行时配置修改导致媒体组文本丢失的问题；增强过滤后验证机制，确保媒体说明完整保留
- **v2.2.19** (2025-07-02) - 🐛 **链接检测修复**：改进pyrogram实体类型处理，修复exclude_links配置对隐式超链接的检测问题

- 性能监控界面主标题和详细统计分组标题现已支持多语言切换即时刷新，无需重启。