# TG-Manager - 专业Telegram消息转发管理器

## 📋 项目简介

TG-Manager 是一个专业的Telegram消息转发和管理工具，基于Python和Pyrogram构建，提供高效、稳定的消息转发服务。

## ✨ 核心特性

### ✨ v2.2.14 - 转发进度自动跳转功能 (最新版本)

**智能界面切换**：
- **🎯 自动跳转到转发进度**：点击"开始转发"按钮后自动切换到"转发进度"选项卡
- **📊 即时状态显示**：转发开始后立即显示转发状态表格和实时进度信息
- **⚡ 操作简化**：无需手动切换标签页，系统自动导航到最相关的界面
- **👁️ 实时监控**：转发过程中的消息数变化、状态更新都能及时查看

**技术实现**：
```python
# 转发开始时的智能跳转
def _start_forward(self):
    # ... 转发准备逻辑 ...
    
    # 自动跳转到转发进度选项卡，方便用户查看转发状态
    # 转发进度选项卡是第3个标签页，索引为2
    self.config_tabs.setCurrentIndex(2)
    
    # 开始异步转发...
```

**用户体验提升**：
- **🎯 即时反馈**: 转发开始后立即看到状态表格和进度信息
- **📈 直观监控**: 已转发消息数、总消息数、转发状态一目了然
- **🔧 减少操作**: 不用手动切换标签页即可查看转发进度
- **⚙️ 智能导航**: 系统自动引导用户到最需要关注的界面

### 🐛 v2.2.13 - 转发计数实时更新修复

**重要Bug修复**：
- **🔧 转发计数同步问题**：修复了历史记录统计后，新转发消息不更新计数的关键问题
- **📊 实时进度显示**：现在转发进行时UI能正确从"44/60"更新为"47/60"，真正反映转发进度
- **🎯 精确频道匹配**：改进频道匹配逻辑，通过ID精确匹配而不是依赖名称匹配，提高准确性
- **⚡ 多重备用策略**：实现6种不同的频道匹配方法，确保各种场景下都能正确识别目标频道

**技术优化**：
```python
# 修复前：丢失频道ID信息
target_channel = extract_name(target_info)  # "我的测试群组"
❌ 无法匹配状态表格中的 "+Y1S0HPZnmqcxNjFh"

# 修复后：保留完整信息进行匹配
target_info = "我的测试群组 (ID: -1002265953141)"  
✅ 通过ID精确匹配到正确的表格行
```

**用户体验提升**：
- **🎯 状态准确性**: 转发进度与实际情况完全同步，无延迟无误差
- **📈 反馈即时性**: 每条消息转发成功后立即更新计数显示
- **🔧 系统稳定性**: 多重匹配策略确保各种频道类型都能正确处理

### 🚀 v2.2.12 - 历史转发记录智能统计

**历史转发记录完整集成**：
- **📊 真实进度显示**: 转发状态表格现在显示包含历史记录的真实进度，而不是从0开始
- **🎯 精确范围统计**: 根据配置的起始ID和结束ID范围，精确统计范围内的已转发消息数量
- **⚡ 程序启动即显示**: 程序启动后立即显示正确的转发进度，如"48/60"而不是"0/60"
- **🔄 智能计数累加**: 实现智能累加机制：显示计数 = 历史记录 + 当前会话增量

**技术特性**：
```python
# 支持不同消息ID范围的历史统计
✅ 指定范围统计      # 起始ID=37300, 结束ID=37360
✅ 开放式范围统计    # 起始ID=37300, 结束ID=0(最新)  
✅ 全历史统计        # 起始ID=0, 结束ID=0(所有)
✅ 实时状态更新      # 转发进行时动态更新计数
```

**用户体验升级**：
- **🎯 状态持续性**: 程序重启后仍能正确显示之前的转发进度
- **📈 完整反馈**: 转发前就能看到历史进度，合理评估剩余工作量
- **⚙️ 无缝集成**: 历史记录统计与实时转发进度完美融合
- **🔧 自动更新**: 转发开始前自动刷新历史统计，确保数据最新

### 🚀 v2.2.0 - 禁止转发频道统一过滤功能

**禁止转发频道功能全面升级**：
- **🎯 功能统一化**: 禁止转发频道现已支持与非禁止转发频道完全相同的过滤和处理功能
- **🔧 代码复用优化**: 重构并行处理器，使用`apply_all_filters`统一过滤逻辑，消除代码重复
- **📦 架构改进**: 提升维护性和功能一致性，所有频道享有统一的过滤体验

**新增功能完整支持**：
```python
# 禁止转发频道现在完全支持以下功能
✅ 关键词过滤          # 媒体组级别智能过滤
✅ 媒体类型过滤        # 消息级别精确控制  
✅ 文本替换功能        # 标题和内容替换
✅ 排除含链接消息      # 自动过滤推广链接
✅ 移除标题功能        # 根据配置移除标题
✅ 媒体组文本重组      # 智能文本保留机制
✅ 发送最终消息        # 转发完成提醒
```

**技术架构升级**：
- **MessageFilter集成**: 并行处理器现在包含完整的消息过滤器
- **预提取文本机制**: 在过滤前预先提取媒体组文本，防止内容丢失
- **智能回退逻辑**: 多层次的文本获取策略，确保内容完整性
- **返回值优化**: 准确的转发数量统计和状态反馈

**用户体验提升**：
- **功能一致性**: 无论源频道是否禁止转发，都享有相同的过滤功能
- **配置统一性**: 所有频道对配置在任何模式下都能正常工作  
- **行为可预期**: 用户配置的过滤规则表现完全一致
- **平滑升级**: 100%向后兼容，无需修改任何配置

### 🚀 v2.1.9 - Pyropatch FloodWait处理器集成

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
- **完整媒体类型支持**：支持6种媒体类型转发
  - 📝 **纯文本**：文字消息和说明文字
  - 🖼️ **照片**：图片文件和相册
  - 🎬 **视频**：视频文件和动画
  - 📄 **文档**：各种文档格式
  - 🎵 **音频**：音乐和语音文件
  - 🎭 **动画**：GIF动画文件
- **灵活的最终消息配置**：
  - 🎯 **频道对级别配置**：每个频道对可以配置独立的最终消息
  - 📄 **HTML文件支持**：支持富文本、表情和超链接
  - 🔄 **多样化内容**：不同频道对可发送不同的营销信息或总结
  - ⚙️ **独立开关**：每个频道对可单独启用或禁用最终消息

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