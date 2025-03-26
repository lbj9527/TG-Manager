# 更新日志

所有项目的显著更改都将记录在此文件中。

本项目遵循[语义化版本规范](https://semver.org/lang/zh-CN/)。

## [0.2.0] - 2023-03-30

### 改进

- 改进了下载模块中的目录命名方式，现在使用"频道标题-频道 ID"作为文件夹名称，而不是仅使用频道 ID
- 修改了`ChannelResolver.format_channel_info`方法，现在返回更丰富的信息（格式化字符串和频道标题、ID 元组）
- 在所有相关模块中更新了对`format_channel_info`返回值的处理方式，包括：
  - Downloader 模块
  - Forwarder 模块
  - Monitor 模块
  - 测试文件
- 添加了文件名清理功能，确保生成的文件夹名称在各操作系统上都有效

## [0.1.0] - 2023-03-25

### 新增

- 初始项目结构设置
- 基础功能模块：ConfigManager、Logger、ChannelResolver、HistoryManager、ClientManager
- 核心功能模块：Downloader、Uploader、Forwarder、Monitor
- 命令行接口：forward、download、upload、startmonitor
- 配置文件读取与验证
- 添加 README.md 和 CHANGELOG.md
