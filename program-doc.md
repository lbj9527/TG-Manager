# TG Forwarder 程序文档

## 1. 项目概述

TG Forwarder 是一个 Telegram 消息转发工具，用于在不同的 Telegram 频道、群组或聊天之间转发消息。该工具提供多种功能，包括历史消息转发、媒体下载、本地文件上传以及最新消息监听转发。

## 2. 技术架构

### 2.1 模块分层

采用模块化分层设计，结合生产者-消费者模式实现并发处理，通过统一的配置和历史记录管理保证数据一致性。架构分为以下核心层：

- 接口层：处理命令行输入与配置加载。

- 核心功能层：实现转发、下载、上传、监听四大功能模块。

- 服务层：提供频道解析、历史记录管理、错误重试等公共服务。

- 数据层：使用 JSON 文件进行历史记录，使用 config.jsons 记录程序参数配置（记得添加 SOCKS5 代理设置）

### 2.2 模块划分与分层

模块 职责 依赖关系
Main 解析命令行参数，调用对应功能模块（forward/download/upload/startmonitor）。 依赖所有功能模块和 ConfigManager
ConfigManager 加载并解析配置文件，提供全局配置数据（如 limit/timeout/频道映射关系等）。 无
ChannelResolver 解析频道标识符（链接/用户名/ID），验证频道有效性，管理频道状态缓存。 Telegram API、HistoryManager
clientManger 客户端管理 依赖于 Telegram API，ConfigManager
Downloader 下载历史消息的媒体文件，按源频道分类存储，支持断点续传。 ChannelResolver、HistoryManager
Uploader 上传本地文件或下载的临时文件到目标频道，组织媒体组，处理多频道分发。 ChannelResolver、HistoryManager
Forwarder 按顺序转发历史消息，处理禁止频道（下载后上传），维护转发记录。 Downloader、Uploader、ChannelResolver
Monitor 监听源频道的新消息，实时触发转发逻辑。 Forwarder、异步事件框架（如 Pyrogram）
HistoryManager 统一管理 download_history.json/upload_history.json/forward_history.json，提供原子化读写接口。 无
Logger 记录运行日志，支持不同级别（INFO/ERROR/DEBUG）输出。 所有模块
FilterManger 文本过滤，链接过滤、文本替换（预留接口，暂不实现）
MediaManger 媒体文件处理、视频中提取图片、视频打水印、图片打水印（预留接口，暂不实现）

## 3. 功能需求

### 3.1 历史消息转发

- **功能描述**：根据统一设置的消息范围，配置多组"一个源频道和多个目标频道"的消息映射，根据媒体组 ID 顺序串行转发
- **实现方式**：
  (1). 加载配置，初始化频道映射关系，调用 ChannelResolver 频道解析获取每个频道的真实 ID 。
  (2). 遍历每个源频道：
  a. 根据 start_id/end_id 获取消息列表，按媒体组 ID 分类，过滤已转发记录（HistoryManager），
  b. 调用 ChannelResolver 获取每个频道的状态（是否禁止转发）。  
   c. 若源频道非禁止转发：直接转发到目标频道，注意保持原消息格式
  若源频道禁止转发：
  对非禁止转发目标频道排序
  调用 Downloader 下载媒体文件、文本等元数据到临时目录，并记录下载成功的历史记录。
  重组媒体组。
  调用 Uploader 上传到第一个非禁止目标频道，成功后通过 copy 转发到其他目标频道。
  成功将一个媒体组消息，转发到配对的所有目标频道后，删除本地文件  
   更新 forward_history.json（标记消息 ID 和源频道、目标频道）。  
   d. 按 forward_delay 控制速率，避免触发 API 限制。  
   e. 达到 limit 后暂停 pause_time 秒，循环执行。  
  (3).
  - 可配置需转发的文件类型
  - 可设置消息过滤器，过滤特定的文字、链接、表情等（暂不实现，留好接口）
  - 水印功能，暂不实现，预留接口
    (4)使用顺序下载，顺序上传。但使用生产者-消费者模式，下载和上传可以同时进行。具体要求：生产者负责顺序下载媒体组内的每个文件，下载完媒体组内所有图片、视频和文本后；消费者负责重组媒体组，然后使用 send_media_group 发送媒体组、使用 copy_media_group 复制媒体组。生产者和消息者可以同时工作，但消费者需等队列中有生产好的东西，才能工作。

### 3.2 历史消息媒体下载

- **功能描述**：根据统一设置的消息范围，下载视频/图片/文件到指定路径
- **实现方式**：
  - 可按源频道用户名分类保存
  - 可设置下载类型和范围
  - 支持断点续传（跳过已下载文件）
  - 使用顺序下载模式
  - 流程是，第一步获取消息范围，剔除已下载过的消息；第二步，循环下载，循环中检测是否达到 Limit 限制的数量，若达到则暂停，等了等待时间再继续下载，下载完成，记入下载历史。
  - 文件名以频道 ID-消息 ID-原文件名.后缀命名

### 3.3 本地文件上传

- **功能描述**：上传本地文件到目标频道
- **实现方式**：
  - 通过设置每个媒体组的文件数量及 caption
  - 以媒体组形式 send_media_group，多线程并发上传到多个目标频道
  - 媒体组组织：在 uploads 文件夹中创建子文件夹，文件夹名作为媒体组的 caption，文件夹内文件组成媒体组（最多 10 个文件）
  - 水印功能，暂不实现，预留接口

### 3.4 最新消息监听转发

- **功能描述**：监听源频道的新消息，实时转发到目标频道
- **实现方式**：
  - 配置多组"一个源频道和多个目标频道"的消息映射
  - 每组采用多线程监听转发
  - 保持源频道消息格式
  - 可设置消息过滤器，过滤特定的文字、链接、表情等
  - 设置监听时间（duration），格式为年-月-日-时，到期自动停止监听
  - 如何实现参考 pyrogram 的文档

## 4. 命令行接口

应用提供以下四种命令行参数：

1. `python run.py forward`

   - 按照设置的消息范围，将源频道的历史消息保持原格式转发到目标频道

2. `python run.py download`

   - 按照设置的消息范围，下载源频道的历史消息到配置文件中设置的下载保存路径

3. `python run.py upload`

   - 将本地"上传路径"中的文件上传到目标频道
   - 支持按媒体组设置或单条消息上传

4. `python run.py startmonitor`
   - 监听源频道，检测到新消息就转发到目标频道

## 5. 配置字段说明

### 5.1 通用字段

- `limit`：下载/上传/转发的数量限制，达到数量限制后，程序休眠 pause_time 秒后再启动
- `pause_time`：达到限制后的休眠时间（秒）
- `timeout`：操作超时时间（秒）
- `max_retries`：失败后重试次数

### 5.2 下载配置

- `download_history`：记录各源频道已下载成功的消息 ID，避免重复下载
- `start_id`/`end_id`：下载消息的 ID 范围，end_id 为 0，表示最新消息
- `source_channels`：源频道列表
- `organize_by_chat`：是否按源频道分类保存文件

### 5.3 上传配置

- `upload_history`：记录已上传的本地文件及已上传目标频道，避免重复上传
- `target_channels`：目标频道列表
- `directory`：本地上传文件路径

### 5.4 转发配置

- `forward_history`：记录各源频道已转发的消息 ID，避免重复转发
- `forward_channel_pairs`：源频道与目标频道的映射关系
  - 数据结构为数组形式，每个元素为包含源频道和目标频道列表的对象
  - 每个对象包含 `source_channel` 和 `target_channels` 两个字段
  - `source_channel` 可以是频道链接（如 "https://t.me/channel_name"）或频道用户名（如 "@channel_name"）
  - `target_channels` 为数组格式，可包含多个频道，支持同样的格式（链接或用户名）
  - 示例：
    ```json
    "forward_channel_pairs": [
      {"source_channel": "https://t.me/source_channel",
       "target_channels": ["https://t.me/target1", "https://t.me/target2"]
      }
    ]
    ```
- `remove_captions`：是否移除原始消息的标题，设为 `true` 则发送时不带原始标题
- `media_types`：需转发的媒体类型，如 ["photo", "video", "document", "audio", "animation"]
- `forward_delay`：转发延迟（秒），用于避免触发 Telegram 的速率限制
- `timeout`：转发操作超时时间（秒）
- `max_retries`：转发失败后的最大重试次数
- `message_filter`：消息过滤器（预留接口，暂不实现）
- `add_watermark`：是否添加水印（预留接口，暂不实现）
- `watermark_text`：水印文本（预留接口，暂不实现）
- `start_id`：起始消息 ID，从此 ID 开始转发
- `end_id`：结束消息 ID，转发到此 ID 为止
- `limit`：转发消息数量上限，达到此数量后暂停转发
- `pause_time`：达到限制后的暂停时间（秒）

### 5.5 监听配置

- `monitor_channel_pairs`：源频道与目标频道的映射关系
  - 数据结构与 `forward_channel_pairs` 相同，为数组形式
  - 每个元素为包含 `source_channel` 和 `target_channels` 字段的对象
  - 示例：
    ```json
    "monitor_channel_pairs": [
      {"source_channel": "https://t.me/source_channel",
       "target_channels": ["https://t.me/target1", "https://t.me/target2"]
      }
    ]
    ```
- `remove_captions`：是否移除原始消息的标题
- `media_types`：需转发的媒体类型，如 ["photo", "video", "document", "audio", "animation"]
- `duration`：监听时长，格式为"年-月-日-时"，如"2025-3-28-1"（表示监听截止到 2025 年 3 月 28 日 1 点）
- `forward_delay`：转发延迟（秒）
- `max_retries`：转发失败后的最大重试次数
- `message_filter`：消息过滤器（预留接口，暂不实现）
- `add_watermark`：是否添加水印（预留接口，暂不实现）
- `watermark_text`：水印文本（预留接口，暂不实现）

### 5.6 存储配置

- `tmp_path`：用于禁止转发频道下载上传文件的临时文件目录，系统将在此目录中存储从禁止转发频道下载的媒体文件，以便于后续上传

## 6. 技术实现注意事项

1. 本地文件上传组织：

   - 在 uploads 文件夹中，创建多个子文件夹
   - 文件夹名即为媒体组的 caption
   - 文件夹内文件组成媒体组，一个媒体组最多 10 个文件

2. 消息过滤器功能：

   - 预留接口
   - 主要功能包括过滤消息文本中的特定文字、特定格式的链接等

3. 统一使用 JSON 文件存储历史记录：

   - 下载历史记录（download_history.json）：

     ```json
     {
       "channels": {
         "@channel_name1": {
           "channel_id": -100123456789,
           "downloaded_messages": [12345, 12346, 12347]
         },
         "https://t.me/channel_name2": {
           "channel_id": -100987654321,
           "downloaded_messages": [56789, 56790]
         }
       },
       "last_updated": "2023-06-15T08:30:45.123Z"
     }
     ```

   - 上传历史记录（upload_history.json）：

     ```json
     {
       "files": {
         "C:/path/to/file1.jpg": {
           "uploaded_to": ["@target_channel1", "https://t.me/target_channel2"],
           "upload_time": "2023-06-15T09:15:30.456Z",
           "file_size": 1024567,
           "media_type": "photo"
         },
         "C:/path/to/file2.mp4": {
           "uploaded_to": ["@target_channel1"],
           "upload_time": "2023-06-15T09:20:45.789Z",
           "file_size": 25678912,
           "media_type": "video"
         }
       },
       "last_updated": "2023-06-15T09:20:45.789Z"
     }
     ```

   - 转发历史记录（forward_history.json）：
     ```json
     {
       "channels": {
         "@source_channel1": {
           "channel_id": -100123456789,
           "forwarded_messages": {
             "12345": ["@target_channel1", "https://t.me/target_channel2"],
             "12346": ["@target_channel1"]
           }
         },
         "https://t.me/source_channel2": {
           "channel_id": -100987654321,
           "forwarded_messages": {
             "56789": ["@target_channel1", "@target_channel3"]
           }
         }
       },
       "last_updated": "2023-06-15T10:05:12.345Z"
     }
     ```

4. 转发模式处理：
   - 对于禁止转发的频道，采用先下载后上传的方式
   - 对于多目标频道，先上传到第一个非禁止转发频道，再转发到其他目标频道

## 8. 频道解析功能

### 8.1 功能描述

频道解析功能是整个应用的基础功能之一，主要负责解析各种格式的 Telegram 频道链接或标识符，将其转换为程序内部可处理的标准格式，并提供频道有效性验证、频道状态管理等核心功能。

### 8.2 支持的频道标识符格式

- **公有频道/群组**:

  - 用户名格式: `@channel_name`
  - 纯用户名格式: `channel_name`
  - 链接格式: `https://t.me/channel_name`
  - 消息链接格式: `https://t.me/channel_name/123`

- **私有频道/群组**:
  - 数字 ID 格式: `1234567890`
  - 链接格式: `https://t.me/c/1234567890`
  - 消息链接格式: `https://t.me/c/1234567890/123`
  - 邀请链接格式: `https://t.me/+abcdefghijk`
  - 纯邀请码格式: `+abcdefghijk`
  - 带前缀的邀请链接: `@https://t.me/+abcdefghijk`

### 8.3 核心功能

- **链接解析**: 将各种格式的频道标识符解析为标准化的(频道 ID/用户名, 消息 ID)元组
- **获取频道实例**：根据真实 ID 或用户名，返回频道实体
- **状态缓存**: 缓存频道转发状态，减少 API 请求

### 8.4 频道状态管理

- **转发状态缓存**: 缓存频道的转发权限状态，避免重复验证
- **缓存过期策略**: 设置缓存有效期，确保数据的时效性
- **状态判断**: 判断频道是否允许转发内容
- **频道排序**: 根据转发状态对频道列表进行优先级排序

### 8.5 技术实现关键点

- **严格错误处理**: 对各种格式的解析错误提供详细的错误信息
- **实时验证**: 通过 Telegram API 实时验证频道状态
- **ID 转换**: 支持将用户名转换为内部频道 ID，便于程序处理
- **缓存机制**: 使用内存缓存减少 API 调用次数，提高性能
- **友好显示**: 为不同类型的频道提供人类可读的格式化显示

通过频道解析功能，应用能够统一处理各种格式的频道标识符，简化用户输入，并为转发、下载和上传操作提供必要的频道信息支持。

## 9. 单元测试

为每个模块实现在本目录下的 tests 文件夹内，添加独立运行的测试文件，客户端连接统一使用主程序的 session 文件

## 10. 注意

### 10.1 本程序不要使用异步的方式写代码
