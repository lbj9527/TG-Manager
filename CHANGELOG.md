# 更新日志

所有项目的显著更改都将记录在此文件中。

本项目遵循[语义化版本规范](https://semver.org/lang/zh-CN/)。

## [1.0.4] - 2024-05-30

### 修复的问题
- 修复了上传模块中 `UploadConfig` 缺少 `media_types` 属性导致的错误
  - 添加了本地媒体类型扩展名映射，代替依赖配置对象
  - 支持了常见的图片、视频、音频和文档格式
  - 改进了文件类型检测机制的稳定性
- 修复了转发模块中使用不安全文件名创建临时目录的问题
  - 添加了 `_get_safe_path_name` 方法，安全处理包含特殊字符的文件路径
  - 处理URL和路径分隔符，防止非法路径字符导致的错误
  - 添加长路径哈希处理，避免路径过长问题

## [1.0.3] - 2024-05-10

### 新增功能和优化
- 优化了 Forwarder 类，添加了事件系统和任务控制机制
  - Forwarder 类现在继承自 EventEmitter，可以发送各种事件通知
  - 添加了任务控制机制，支持暂停和取消转发任务
  - 完善了错误处理，提供了更详细的错误信息和类型
  - 添加了进度报告功能，可以实时显示转发进度
  - 优化了临时文件管理，确保资源正确释放
  - 增强了并行下载和上传的鲁棒性
- 优化了 Downloader 类，添加了事件系统和任务控制机制
  - Downloader 类现在可以发送各种事件通知，替代直接的日志输出
  - 增加了细粒度的进度报告和状态更新
  - 添加了媒体类型检测和文件名生成的优化
  - 增强了错误处理和恢复机制
- 优化了 Uploader 类，添加了事件系统和任务控制机制
  - Uploader 类现在可以发送上传状态、进度和错误事件
  - 支持取消和暂停上传操作
  - 增强了上传策略和媒体类型处理
  - 改进了错误处理和资源管理
- 添加了通用的事件系统和任务控制机制
  - 新增 EventEmitter 类用于实现组件间的事件通知
  - 新增 CancelToken 类用于取消异步操作
  - 新增 PauseToken 类用于暂停和恢复异步操作
  - 新增 TaskContext 类用于管理任务执行上下文
- 完善了资源管理
  - 优化了临时文件和目录的创建和清理
  - 改进了缩略图处理和资源释放
  - 确保在任务取消或出错时正确释放资源
- 提高了代码质量
  - 完善了类型提示和函数文档
  - 重构了复杂方法，提高可维护性
  - 统一了错误处理和日志记录方式
  - 增强了异步操作控制和安全性

### 修复的问题
- 修复了在转发任务被取消时未能正确清理资源的问题
- 修复了下载失败时未能提供足够错误信息的问题
- 修复了上传重试机制中的逻辑错误
- 改进了FloodWait异常处理，确保正确等待和重试

## [1.0.2] - 2024-05-01

### 改进

- 优化了 Monitor 类，添加了事件系统和任务控制机制
  - Monitor 类现在继承自 EventEmitter，可以发送各种事件通知
  - 添加了任务控制机制，支持暂停和取消监听任务
  - 实现了消息处理过程中的事件通知，包括消息接收、媒体组处理和转发状态
  - 优化了文本替换功能，增加了替换前后的事件通知
  - 增强了消息复制和媒体组转发的错误处理
  - 添加了详细的进度报告，跟踪消息和媒体组转发的完成状态
  - 优化了监听任务的启动和停止流程，支持优雅终止
- 丰富了文档，新增了 Monitor 模块事件系统的使用说明
  - 添加了 Monitor 特有事件类型的详细描述
  - 增加了使用任务控制实现定时监听的示例代码
  - 更新了支持的事件类型列表，包含所有 Monitor 特有事件

## [1.0.1] - 2024-04-02

### 改进

- 优化监听模块的配置结构，将 text_filter 和 remove_captions 移入每个 channel_pair
- 删除历史记录跟踪功能，减少系统资源占用
- 统一使用 copy_message 和 copy_media_group 方法处理消息，保持一致的消息来源隐藏
- 更新媒体组处理逻辑文档，明确说明 media_types 的筛选机制
- 添加详细文档说明媒体组作为整体处理的特性及最佳实践建议

### 变更

- 调整文本替换功能的处理逻辑：
  - 若 original_text 为空，则不进行替换
  - 若 original_text 不为空但 target_text 为空，则替换为空字符串
- 优化 media_types 参数的使用说明，清晰列出所有支持的消息类型
- 完善 forward_delay 参数的使用说明，明确其在消息转发间隔中的作用

## [1.0.0] - 2024-03-31

### 新增

- 实现了监听模块（Monitor），支持实时监听源频道的新消息并转发到目标频道
- 支持配置多组"一个源频道和多个目标频道"的消息映射关系
- 自动检测源频道转发权限，对于非禁止转发频道使用直接转发，对于禁止转发频道使用复制转发
- 支持配置是否去除媒体说明文字（remove_captions）
- 支持隐藏消息来源（hide_author）
- 支持配置消息类型过滤，只转发指定类型的消息
- 实现文本替换功能，可将特定文字替换为配置的内容
- 支持设置监听时间（duration），到期自动停止监听
- 添加`startmonitor`命令，用于启动监听功能

### 改进

- 优化了对 FloodWait 错误的处理逻辑，自动等待后继续
- 增强了消息转发的历史记录管理，避免重复转发
- 改进日志输出，清晰显示监听和转发状态
- 完善错误处理机制，单个频道错误不影响其他频道的监听

## [0.7.5] - 2024-03-30

### 改进

- 优化上传模块的转发逻辑，参考转发模块实现了多目标频道的高效上传
- 为上传模块添加频道权限检测功能，自动识别非禁止转发的频道并优先使用
- 实现先上传到一个非禁止转发频道，然后使用复制转发到其他目标频道的功能
- 添加错误处理机制，当第一个目标频道上传失败时自动尝试下一个频道
- 大幅降低多频道上传的耗时和流量消耗，提高了上传效率

## [0.7.4] - 2024-03-29

### 改进

- 优化上传模块的 caption 逻辑，从使用文件夹名称改为读取 title.txt 文件内容
- 支持单文件上传和媒体组上传从同级目录的 title.txt 读取说明文字
- 添加 title.txt 文件不存在或读取失败时的回退机制，保持与之前行为的兼容性
- 上传单文件时自动跳过 title.txt 文件，避免重复上传

## [0.7.3] - 2024-03-28

### 修复

- 修复了由 auth.ExportAuthorization 导致的 FloodWait 错误处理问题
- 增强了数据中心切换和授权过程中的错误处理机制
- 改进了错误消息解析，准确提取等待时间
- 修复了 current_dc_id 获取方式，正确区分属性和方法调用
- 修复了零大小文件的检测和处理
- 完善了 media 下载过程中的错误处理
- 统一了顺序下载和并行下载模式中的错误处理机制
- 统一了媒体组文本文件的命名，所有文本文件现在统一使用"title.txt"作为文件名

## [0.7.2] - 2023-08-15

### 改进

- 统一普通下载和关键词下载的配置结构，使用相同的配置模式
- 优化配置项管理，提高代码重用性和一致性
- 简化用户配置流程，采用统一的配置方式

### 变更

- 移除了公共配置中的`source_channels`、`start_id`和`end_id`字段，统一使用`downloadSetting`配置
- 无论是普通下载还是关键词下载，均使用`downloadSetting`数组中的配置项
- 关键词下载模式下，使用`downloadSetting`中的`keywords`字段进行筛选
- 普通下载模式下，忽略`downloadSetting`中的`keywords`字段

### 修复

- 解决了普通下载和关键词下载使用不同配置结构导致的潜在问题
- 修复了在某些情况下配置解析不一致的问题

## [0.7.1] - 2023-07-10

### 改进

- 优化本地文件组织结构，按媒体组 ID 进行二级目录分类
- 添加媒体组文本自动保存功能，在每个媒体组文件夹中创建文本文件存储媒体组的文字内容
- 增强普通下载模式和关键词下载模式下的文件结构一致性
- 改进媒体组内文件的组织方式，确保相关文件存放在同一目录中
- 增强用户体验，通过合理文件组织使查找相关媒体更加便捷

## [0.7.0] - 2023-07-05

### 新增

- 添加关键词下载功能，支持根据消息文本中的关键词筛选下载内容
- 新增`downloadKeywords`命令，专用于关键词下载模式
- 实现关键词匹配消息文本和说明文字功能，支持大小写不敏感匹配
- 添加关键词目录组织功能，自动按关键词创建子目录
- 升级配置结构，新增`downloadSetting`数组，支持多频道多关键词配置
- 为每个下载设置项添加单独的源频道、ID 范围、媒体类型和关键词配置

### 改进

- 重构下载模块，支持三种下载模式：顺序下载、并行下载和关键词下载
- 优化目录创建逻辑，根据不同下载模式自动选择合适的目录组织方式
- 增强配置文件结构，保持向后兼容性
- 改进关键词匹配算法，提高匹配准确性和效率
- 优化日志输出，更清晰地显示关键词匹配和下载状态
- 增强下载配置的灵活性，简化多源频道配置流程

### 修复

- 修复关键词下载模式下媒体组处理的逻辑问题，确保当媒体组中任意消息包含关键词时，下载该媒体组中的所有文件
- 优化媒体组关键词匹配算法，提高媒体组下载的完整性和准确性
- 修复 `_iter_messages` 函数在获取消息时可能导致的无限循环问题
- 添加最大尝试次数限制，防止在消息不可获取时陷入死循环
- 改进消息获取算法，使用更高效的方式处理可能不存在的消息 ID
- 实现智能批次调整，当无法获取消息时自动减小批次大小
- 优化日志输出，提供更清晰的消息获取状态和错误信息
- 增强对缺失消息的处理，跳过不存在的消息 ID 而不影响其他消息获取
- 修复媒体组 ID 类型处理问题，避免在处理整数类型的媒体组 ID 时导致的类型错误

## [0.6.1] - 2023-06-25

### 修复

- 修复了 `_iter_messages` 函数在获取消息时可能导致的无限循环问题
- 优化了消息获取逻辑，当特定消息 ID 不存在时能够跳过并继续获取
- 添加了最大尝试次数，防止在消息不可获取时陷入死循环
- 改进了日志输出，提供更清晰的消息获取状态信息
- 增强了错误处理，详细记录无法获取的消息 ID

## [0.6.0] - 2023-06-20

### 新增

- 添加了视频缩略图功能，大幅提升用户体验
- 新增`VideoProcessor`类，专用于视频缩略图的提取和管理
- 实现了智能缩略图生成，自动调整尺寸和质量以符合 Telegram API 要求
- 支持为单个视频文件和媒体组中的视频生成缩略图
- 媒体组中的视频上传现在会自动包含缩略图预览

### 改进

- 优化了缩略图的内存管理，文件处理完成后自动清理缩略图资源
- 增强了视频上传体验，缩略图使视频内容一目了然
- 优化了上传模块中的缩略图清理逻辑，防止内存泄漏
- 遵循 Telegram 官方缩略图规范，确保生成的缩略图尺寸不超过 320x320 像素
- 通过 JPEG 压缩控制，确保缩略图文件大小不超过 200KB

### 修复

- 修复了处理缩略图路径为 None 时可能导致的错误
- 改进了多频道上传时的缩略图管理，确保上传完所有频道后才清理资源
- 修复了缩略图目录不存在时的自动创建功能

## [0.5.0] - 2023-06-15

### 新增

- 实现了真正的生产者-消费者模式，用于媒体组的并行下载和上传
- 新增`MediaGroupDownload`数据类，用于封装媒体组下载结果
- 添加了`_process_parallel_download_upload`方法，支持媒体组的并行处理
- 实现了生产者函数`_producer_download_media_groups_parallel`用于并行下载媒体组
- 实现了消费者函数`_consumer_upload_media_groups`用于并行上传媒体组
- 优化了媒体组路径处理，确保安全的文件系统操作

### 改进

- 添加了媒体组上传完成后自动清理本地文件的功能
- 优化了转发历史判断逻辑，避免重复转发
- 增强了媒体组转发状态的日志信息，包括详细的媒体组 ID、消息 ID 和目标频道信息
- 改进了错误处理，提高了大量媒体组同时处理时的稳定性
- 实现了自动重试机制，处理上传失败的场景

### 修复

- 修复了媒体组 ID 包含非法文件系统字符时创建目录失败的问题
- 解决了媒体组上传部分成功时的状态跟踪问题
- 修复了转发记录不完整导致的重复上传问题
- 改进了队列管理，确保所有任务都能被正确处理

## [0.4.2] - 2023-06-10

### 增强

- 全面优化 FloodWait 处理机制，引入连续触发检测和自适应退避策略
- 添加临时文件写入机制，确保文件写入的原子性和安全性
- 增强文件下载前的媒体内容验证
- 改进文件大小检查，引入百分比进度显示
- 增强对网络错误和 API 限制的智能处理

### 修复

- 修复文件大小为 0 的问题，通过多重检查和验证确保文件完整性
- 解决 PEER_ID_INVALID 错误，增加明确的错误提示
- 修复临时文件处理，防止数据损坏
- 改进频道访问权限错误处理，提供更清晰的错误信息
- 修复 FloodWait 处理中的递归和抖动问题

## [0.4.1] - 2023-05-15

### 增强

- 全面升级 FloodWait 处理机制，实现全局自适应速率限制控制
- 添加下载内容验证系统，自动检测和处理不完整下载
- 优化文件大小计算和显示，解决速度显示错误问题
- 添加重试机制，对下载失败的文件自动进行多次尝试
- 实现指数退避策略，减少 API 连续错误
- 提高下载队列容量，更好地处理大量下载任务

### 修复

- 修复文件大小为 0 的问题，现在会自动检测并重试
- 解决 FloodWait 递归调用导致的栈溢出问题
- 修复下载大文件时速度显示不准确的问题
- 修复文件写入验证，确保磁盘上的文件完整性
- 增加了详细的错误日志，便于问题诊断

## [0.4.0] - 2023-05-10

### 增强

- 彻底重构并行下载机制，解决并发瓶颈问题
- 实现真正并行处理下载任务，而不是之前的伪并行模式
- 引入工作协程池系统，确保最大化利用配置的并发下载限制
- 优化文件写入线程池，显著提高大量小文件的处理速度
- 添加详细的下载性能监控，包括每个下载任务的预计大小、实际大小和速度
- 增加工作协程 ID 显示，使并行任务跟踪更加直观
- 改进日志系统，更清晰地展示当前活跃下载数量和队列状态

### 修复

- 修复首批下载完成后并行下载停滞的问题
- 解决文件写入非并行执行的性能瓶颈
- 优化内存使用，防止大量并行下载时的内存溢出风险
- 修复 FloodWait 异常处理逻辑，确保限速后正确重试

## [0.3.9] - 2023-05-02

### 改进

- 优化了并行下载功能实现，显著提高下载速度
- 引入了文件写入线程池，减少文件 I/O 瓶颈
- 添加了详细的性能统计信息，包括下载速度和文件大小
- 减少了消息获取时的延迟，提高了下载效率
- 优化了日志输出，便于追踪并行下载的实际状态
- 修复了下载任务的进度显示问题

## [0.3.8] - 2023-04-30

### 新增

- 添加了并行下载功能，在`DOWNLOAD`配置中新增`parallel_download`和`max_concurrent_downloads`参数
- 新增`downloader_serial.py`模块，保留原始的顺序下载实现逻辑
- 根据配置自动选择并行或顺序下载模式，提高大量文件下载时的效率
- 使用信号量控制并发下载数量，避免超出 Telegram API 限制

## [0.3.7] - 2023-04-27

### 改进

- 修改了转发模块中的消息获取顺序，从"从新到旧"改为"从旧到新"，使转发按照原始发送顺序进行
- 重构了`Forwarder._iter_messages`方法，现在会先收集所有消息，然后按照 ID 升序排序后再处理
- 转发的消息现在会按照原始顺序（从旧到新）进行转发，与下载顺序保持一致，提供更直观的体验

## [0.3.6] - 2023-04-25

### 改进

- 将上传、下载和转发的三个历史记录 JSON 文件统一移动到根目录下的 history 文件夹中
- 优化了历史记录文件的管理结构，提高了项目的文件组织性

## [0.3.5] - 2023-04-15

### 改进

- 修复了转发历史记录的逻辑，现在只有转发成功才记录转发历史
- 增强了错误处理机制，转发失败时会明确记录错误并跳过，不会记录到转发历史中
- 优化了单条消息和媒体组转发的异常处理，提高了代码的健壮性

## [0.3.4] - 2023-04-12

### 改进

- 优化了媒体组消息的转发方式，现在在隐藏作者模式下使用 `copy_media_group` 方法一次性转发整个媒体组
- 改进了错误处理机制，当媒体组转发失败时会优雅地跳过并继续处理其他消息
- 减少了 API 调用次数，提高了转发效率，避免了因频繁请求导致的速率限制
- 重构了转发历史记录代码，消除了重复代码，提高代码可维护性

## [0.3.3] - 2023-04-10

### 新增

- 添加了隐藏原作者功能，在 `FORWARD` 配置中新增 `hide_author` 选项
- 当 `hide_author` 设置为 `true` 时，使用 `copy_message` 方法转发消息，隐藏原始作者信息
- 当 `hide_author` 设置为 `false` 时，使用 `forward_messages` 方法转发消息，保留原始作者信息

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
