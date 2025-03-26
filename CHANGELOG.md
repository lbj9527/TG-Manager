# 更新日志

所有项目的显著更改都将记录在此文件中。

本项目遵循[语义化版本规范](https://semver.org/lang/zh-CN/)。

## [0.3.2] - 2023-04-08

### 修复

- 修复了`check_forward_permission`方法中的 Pyrogram API 兼容性问题，将`get_messages`替换为`get_chat_history`
- 更新了主程序中的 asyncio 事件循环处理方式，使用`asyncio.run()`替代旧的获取循环方法，消除 deprecation 警告

## [0.3.0] - 2023-04-05

### 改进

- 修改了消息获取顺序，从"从新到旧"改为"从旧到新"，使得下载和处理消息按照时间顺序进行
- 重构了`_iter_messages`方法，现在会先收集所有消息，然后按照 ID 升序排序后再处理
- 下载的媒体文件现在会按照原始发送顺序（从旧到新）进行下载，提供更直观的下载体验

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
