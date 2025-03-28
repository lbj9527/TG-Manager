# TG Forwarder

TG Forwarder 是一个功能强大的 Telegram 消息转发工具，用于在不同的 Telegram 频道、群组或聊天之间转发消息。

## 功能特点

- **历史消息转发**：将源频道的历史消息按原格式转发到目标频道
- **媒体文件下载**：下载源频道的图片、视频、文件等媒体内容
- **本地文件上传**：将本地文件上传至目标频道，支持媒体组
- **实时消息监听**：监听源频道的新消息并实时转发至目标频道
- **事件通知系统**：提供完善的事件通知机制，支持界面实时更新
- **任务控制**：支持暂停、恢复和取消任务，增强用户交互体验

## 项目结构

项目主要目录结构：

```
TG-Manager/
├── config.json         # 配置文件
├── history/            # 历史记录文件目录
│   ├── download_history.json    # 下载历史记录
│   ├── upload_history.json      # 上传历史记录
│   └── forward_history.json     # 转发历史记录
├── downloads/          # 下载的媒体文件目录
├── uploads/            # 待上传的媒体文件目录
├── tmp/                # 临时文件目录
├── logs/               # 日志文件目录
└── src/                # 源代码目录
    ├── modules/        # 核心功能模块
    ├── utils/          # 工具类和辅助函数
    └── ui/             # 用户界面相关代码
```

## 安装方法

1. 克隆仓库：

```bash
git clone https://github.com/yourusername/tg-forwarder.git
cd tg-forwarder
```

2. 安装依赖：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

3. 配置 `config.json` 文件：
   - 添加您的 Telegram API ID 和 API Hash
   - 配置转发、下载、上传和监听的相关参数

## 使用方法

TG Forwarder 提供四种主要命令：

1. **历史消息转发**：

```bash
python run.py forward
```

2. **媒体文件下载**：

```bash
python run.py download
```

3. **基于关键词的媒体文件下载**：

```bash
python run.py downloadKeywords
```

4. **本地文件上传**：

```bash
python run.py upload
```

5. **实时消息监听**：

```bash
python run.py startmonitor
```

## 配置说明

详细的配置信息请参考 `config.json` 文件，主要包括：

- **通用配置**：API 凭据、代理设置、消息限制等
- **下载配置**：源频道、消息范围、下载路径、并行下载设置等
- **上传配置**：目标频道、本地文件路径等
- **转发配置**：频道映射关系、转发延迟、媒体类型等
- **监听配置**：监听频道、持续时间、转发设置等

## 功能详细说明

### 历史消息转发

支持在不同频道间转发历史消息，可以保留原始格式并设置消息筛选条件。对于禁止转发的频道，会自动采用"下载后上传"的方式完成转发。消息转发按照原始发送顺序进行（从旧到新），确保转发内容按照时间顺序展示，与文件下载顺序保持一致。

#### 配置示例

```json
"FORWARD": {
  "forward_channel_pairs": [
    {
      "source_channel": "https://t.me/channel1",
      "target_channels": ["@target_channel1", "@target_channel2"]
    }
  ],
  "remove_captions": false,
  "hide_author": true,
  "media_types": ["photo", "video", "document", "audio", "animation", "text"],
  "forward_delay": 2,
  "start_id": 1,
  "end_id": 5000,
  "tmp_path": "tmp"
}
```

#### 并行下载上传功能

从 0.5.0 版本开始，TG Forwarder 引入了真正的并行下载和上传功能，特别适用于禁止直接转发的频道：

1. **生产者-消费者模式**：采用高效的生产者-消费者架构，实现媒体组的并行处理

   - 生产者负责下载媒体组消息和文件
   - 消费者负责将下载好的媒体组上传到目标频道
   - 两个过程并行执行，大幅提高转发效率

2. **高效媒体组处理**：

   - 自动检测已转发的媒体组，避免重复转发
   - 智能管理本地文件，成功上传后自动清理
   - 详细的转发状态日志，清晰展示每个媒体组的处理情况

3. **特性与优势**：
   - 显著提高转发速度，尤其对大量媒体文件的处理
   - 减少内存占用，支持更大规模的批量转发
   - 完善的错误处理和重试机制，提高转发成功率
   - 精确的转发历史记录，避免重复操作

### 媒体文件下载

可以下载指定频道的历史消息中包含的媒体文件，支持多种文件类型，并能按源频道分类保存。下载的文件将保存在以"频道标题-频道 ID"命名的文件夹中，使得文件组织更加直观。如果无法获取频道标题，则使用"未知频道"作为默认标题。媒体文件下载按照消息发送的原始时间顺序进行（从旧到新），确保下载的内容保持时间连贯性。

#### 下载模式

支持三种下载方式：

- **顺序下载**：默认模式，按照消息 ID 顺序依次下载文件，适合网络条件较差或需要严格控制带宽占用的场景。
- **并行下载**：通过设置`parallel_download`为`true`启用，可同时下载多个文件，显著提高下载速度。可通过`max_concurrent_downloads`参数控制最大并行下载数量（默认为 10）。
- **关键词下载**：通过命令`python run.py downloadKeywords`启用，仅下载包含指定关键词的消息中的媒体文件，同时将下载的文件按关键词组织存放。

> 自 0.7.2 版本起，普通下载和关键词下载均使用相同的配置结构（`downloadSetting`数组），唯一区别是在关键词下载模式下会使用`keywords`字段进行筛选，而在普通下载模式下则忽略该字段。不再使用顶层的`source_channels`、`start_id`和`end_id`字段。

#### 配置示例

```json
"DOWNLOAD": {
  "downloadSetting": [
    {
      "source_channels": "https://t.me/channel1",
      "start_id": 1000,
      "end_id": 2000,
      "media_types": ["photo", "video", "document"],
      "keywords": ["重要", "公告"]  // 普通下载模式忽略此字段，关键词下载模式使用此字段
    },
    {
      "source_channels": "https://t.me/channel2",
      "start_id": 5000,
      "end_id": 0,  // 0表示下载到最新消息
      "media_types": ["photo", "video", "document", "audio", "animation"],
      "keywords": ["测试", "预览"]
    }
  ],
  "download_path": "downloads",
  "parallel_download": true,
  "max_concurrent_downloads": 10
}
```

#### 并行下载高级功能

并行下载模式提供以下高级功能和优势：

1. **高效工作协程池**：系统会自动创建多个工作协程，确保始终保持指定数量的并发下载任务，大幅提高下载速度。

2. **智能文件写入**：实现了多线程文件写入池，避免文件 I/O 成为性能瓶颈，特别适合大量小文件的下载场景。

3. **自适应性能优化**：

   - 自动检测文件大小并显示预估下载时间
   - 实时计算并显示下载速度
   - 智能处理 Telegram API 速率限制，确保下载连续性

4. **详细性能监控**：

   - 显示每个下载任务的工作协程 ID
   - 跟踪文件大小、下载耗时和速度
   - 监控当前活跃下载数量和队列状态

5. **高级错误处理**：
   - 全局自适应速率限制处理，智能应对 Telegram 的 FloodWait 限制
   - 自动重试机制，对下载失败的文件进行多次尝试
   - 指数退避策略，自动增加重试间隔，避免连续触发限制
   - 下载内容验证，确保每个文件完整下载，防止文件损坏

#### 关键词下载功能

从 0.7.0 版本开始，TG Forwarder 添加了关键词下载功能，支持根据消息文本内容筛选需下载的媒体：

1. **智能关键词匹配**：

   - 自动检测消息文本和说明文字中的关键词
   - 支持设置多个关键词，匹配任一关键词即下载
   - 忽略大小写，提高匹配准确性和灵活性
   - 增强的媒体组处理：当媒体组中任意一条消息匹配关键词时，自动下载整个媒体组所有文件，确保相关媒体内容完整性

2. **目录智能组织**：

   - 按照匹配的关键词自动创建子目录
   - 相同关键词的媒体文件集中存放，便于管理
   - 支持"频道名称/关键词"的层级目录结构

3. **精细化配置**：
   - 通过`downloadSetting`数组为不同频道设置不同的关键词
   - 每个设置项可单独指定消息 ID 范围、媒体类型和关键词列表
   - 实现多频道、多关键词的精确下载策略

#### 媒体组文件夹组织功能

从 0.7.1 版本开始，TG Forwarder 引入了媒体组文件夹组织功能，提供更直观的本地文件结构：

1. **二级目录结构**：

   - 第一级为频道名称目录或关键词目录（根据下载模式自动选择）
   - 第二级为媒体组 ID 目录，每个媒体组的内容存放在独立文件夹中
   - 自动处理文件名中的非法字符，确保在各操作系统上兼容

2. **媒体组文本文件**：

   - 自动为每个媒体组创建文本文件，存储消息的文字内容
   - 文本文件以`title.txt`命名，便于与媒体文件关联
   - 支持 UTF-8 编码，确保多语言文字正确显示

3. **统一的组织逻辑**：

   - 在普通下载和关键词下载模式下使用一致的文件组织逻辑
   - 单条消息也以独立文件夹形式存储，提供统一的访问体验
   - 相关内容集中存放，便于查找和管理

4. **目录结构示例**：
   ```
   downloads/
   ├── 频道名称-123456/                # 频道目录
   │   ├── 1234567890/                # 媒体组ID目录
   │   │   ├── title.txt           # 媒体组文本文件
   │   │   ├── 123456-100-photo.jpg   # 媒体文件1
   │   │   └── 123456-101-video.mp4   # 媒体文件2
   │   └── single_102/                # 单条消息目录
   │       ├── title.txt           # 消息文本文件
   │       └── 123456-102-photo.jpg   # 媒体文件
   └── 关键词/                        # 关键词目录（关键词下载模式）
       └── 7654321098/                # 媒体组ID目录
           ├── title.txt           # 媒体组文本文件
           ├── 654321-200-photo.jpg   # 媒体文件1
           └── 654321-201-video.mp4   # 媒体文件2
   ```

### 本地文件上传

将本地文件上传到指定频道，支持按文件夹组织媒体组，并可以设置自定义文本。

#### 配置示例

```json
"UPLOAD": {
  "target_channels": ["@target_channel1", "@target_channel2"],
  "directory": "uploads",
  "caption_template": "{filename}"
}
```

#### 多频道智能上传功能

从 0.7.5 版本开始，TG Forwarder 实现了智能多频道上传策略，大幅提高上传效率：

1. **智能频道排序**：

   - 自动检测非禁止转发的频道，并将其优先排序
   - 先上传到非禁止转发频道，然后通过复制转发到其他频道
   - 大幅减少上传流量和时间消耗，特别是对于大型媒体文件

2. **容错机制**：

   - 当首选频道上传失败时，自动尝试下一个非禁止转发频道
   - 多级失败回退，确保即使部分频道不可用，也能完成上传
   - 详细的错误日志，清晰展示每个频道的上传状态

3. **兼容现有功能**：
   - 与媒体组标题功能无缝集成，保留从 title.txt 读取说明文字的能力
   - 继续支持视频缩略图功能，保持良好的视频预览体验
   - 向后兼容单频道上传场景，无需额外配置

#### 媒体组标题功能

从 0.7.4 版本开始，TG Forwarder 支持从文件夹中的 title.txt 文件读取内容作为媒体组或单个文件的说明文字（caption）：

1. **智能标题读取**：

   - 自动从媒体组文件夹中的 title.txt 读取内容作为上传时的说明文字
   - 支持单个文件上传和媒体组上传
   - 如果 title.txt 不存在或读取失败，自动回退到使用文件夹名称或默认模板

2. **使用方式**：
   - 在需要上传的文件夹中创建一个名为 title.txt 的文本文件
   - 在文件中编写需要显示的说明文字
   - 系统会自动读取该文件内容，并将其作为上传文件时的 caption
   - 上传时会自动跳过 title.txt 文件本身，只上传其他媒体文件

#### 视频缩略图功能

从 0.6.0 版本开始，TG Forwarder 支持为视频文件自动生成和上传缩略图：

1. **智能缩略图生成**：

   - 自动从视频中提取第一帧作为缩略图
   - 智能调整尺寸，确保符合 Telegram API 要求（不超过 320×320 像素）
   - 自动压缩图片质量，保证缩略图大小在 200KB 以内

2. **增强视频上传体验**：
   - 单个视频文件和媒体组中的视频都支持缩略图
   - 上传完成后自动清理缩略图资源，避免占用存储空间
   - 为多频道上传优化，确保所有频道都能看到缩略图预览

### 实时消息监听

监听模块（Monitor）负责实时监听源频道的新消息并转发到目标频道。支持高度可定制的转发行为，包括消息类型过滤、文本替换、媒体处理等。

#### 配置示例

```json
"MONITOR": {
  "monitor_channel_pairs": [
    {
      "source_channel": "https://t.me/channel1",
      "target_channels": ["https://t.me/target1", "https://t.me/target2"],
      "remove_captions": false,
      "text_filter": [
        {
          "original_text": "敏感词",
          "target_text": "替换词"
        },
        {
          "original_text": "广告词",
          "target_text": ""  // 替换为空字符串
        }
      ]
    }
  ],
  "media_types": ["photo", "video", "document", "audio", "animation", "sticker", "voice", "video_note", "text"],
  "duration": "2024-12-31",  // 监听截止日期，格式为 yyyy-mm-dd
  "forward_delay": 3  // 转发间隔时间（秒）
}
```

#### 支持的消息类型

`media_types` 参数用于配置需要转发的消息类型。支持以下类型：

- **`text`**: 纯文本消息
- **`photo`**: 图片消息
- **`video`**: 视频消息
- **`document`**: 文档/文件消息
- **`audio`**: 音频消息
- **`animation`**: 动画/GIF 消息
- **`sticker`**: 贴纸消息
- **`voice`**: 语音消息
- **`video_note`**: 圆形视频消息（视频留言）

#### 媒体组处理机制

在监听模块中，媒体组（多个媒体文件组成的一组消息）有以下处理特点：

1. **整体处理原则**：

   - 媒体组作为一个整体被处理，而非单独处理每个媒体项
   - 媒体组的处理由第一个被监听到的消息触发
   - 系统会根据第一个接收到的消息判断是否处理整个媒体组

2. **消息类型筛选**：

   - 如果媒体组中首个被接收到的消息类型不在 `media_types` 列表中，则整个媒体组都不会被处理
   - 如果媒体组中首个被接收到的消息类型在 `media_types` 列表中，则整个媒体组都会被处理
   - **重要**：筛选仅发生在媒体组第一个消息，不会单独筛选媒体组中的各个媒体项

3. **实际效果**：

   - 当 `media_types` 设置为 `["video"]` 时，如果媒体组中第一个接收到的消息是视频，整个媒体组（包括图片等其他媒体）都会被转发
   - 相反，如果媒体组中第一个接收到的消息不是视频，则整个媒体组都不会被转发
   - 不支持仅转发媒体组中的特定类型媒体（如只转发媒体组中的视频部分）

4. **最佳实践**：
   - 如果需要处理包含多种媒体类型的媒体组，建议将所有可能的媒体类型都加入 `media_types` 列表

#### 消息转发配置

1. **单条消息和媒体组处理**：

   - **所有消息隐藏来源**：系统使用 `copy_message` 方法处理单条消息，使用 `copy_media_group` 方法处理媒体组
   - **转发延迟**：通过 `forward_delay` 参数配置每次转发之间的延迟时间（秒）

2. **文本替换功能**：
   - **替换规则**：通过 `text_filter` 配置替换规则
   - **替换逻辑**：
     - 如果 `original_text` 为空，则不进行替换
     - 如果 `original_text` 不为空但 `target_text` 为空，则替换为空字符串
     - 支持对消息标题和文本内容进行替换

## 事件系统使用

TG-Forwarder 实现了完善的事件系统，可以监听各种操作的进度和状态：

```python
from src.modules.forwarder import Forwarder
from src.utils.controls import TaskContext

# 创建一个 Forwarder 实例
forwarder = Forwarder(client, config_manager, channel_resolver, history_manager, downloader, uploader)

# 注册事件监听器
forwarder.on("status", lambda status: print(f"状态更新: {status}"))
forwarder.on("progress", lambda percent, current, total, task_type: print(f"进度: {percent:.2f}%, {current}/{total} ({task_type})"))
forwarder.on("error", lambda msg, error_type, recoverable, **kwargs: print(f"错误: {msg} (类型: {error_type}, 可恢复: {recoverable})"))
forwarder.on("complete", lambda total_forwarded: print(f"转发完成，共转发 {total_forwarded} 个媒体组/消息"))

# 创建任务上下文
task_context = TaskContext()

# 开始转发任务
await forwarder.forward_messages(task_context)

# 在其他线程或异步函数中控制任务
def pause_task():
    # 暂停任务
    task_context.pause_token.pause()
    
def resume_task():
    # 恢复任务
    task_context.pause_token.resume()

def cancel_task():
    # 取消任务
    task_context.cancel_token.cancel()
```

### Monitor 模块事件系统

Monitor 模块（消息监听器）也实现了完整的事件系统，可以实时监控消息监听状态：

```python
from src.modules.monitor import Monitor
from src.utils.controls import TaskContext

# 创建一个 Monitor 实例
monitor = Monitor(client, config_manager, channel_resolver)

# 注册事件监听器
monitor.on("status", lambda status: print(f"监听状态: {status}"))
monitor.on("message_received", lambda message_id, channel_info: print(f"收到新消息: {message_id} 从 {channel_info}"))
monitor.on("media_group_received", lambda group_id, channel_info: print(f"收到新媒体组: {group_id} 从 {channel_info}"))
monitor.on("text_replaced", lambda old_text, new_text, replacements: print(f"文本已替换: '{old_text}' -> '{new_text}'"))
monitor.on("progress", lambda current, total, message: print(f"进度: {current}/{total}, {message}"))
monitor.on("error", lambda msg, error_type, recoverable, **kwargs: print(f"错误: {msg} (类型: {error_type}, 可恢复: {recoverable})"))

# 创建任务上下文
task_context = TaskContext()

# 开始监听
await monitor.start_monitoring(task_context)

# 停止监听
await monitor.stop_monitoring()
```

### Monitor 特有事件类型

| 事件名称 | 参数 | 说明 |
|---------|------|-----|
| message_received | message_id, channel_info | 收到新消息事件 |
| media_group_received | group_id, channel_info | 收到新媒体组事件 |
| text_replaced | old_text, new_text, replacements | 文本替换事件，包含原文本、新文本和替换规则列表 |

### 使用任务控制实现定时监听

Monitor 模块支持通过任务控制机制实现定时监听功能：

```python
import asyncio
from datetime import datetime, timedelta
from src.modules.monitor import Monitor
from src.utils.controls import TaskContext

async def scheduled_monitoring(duration_hours=1):
    # 创建 Monitor 实例
    monitor = Monitor(client, config_manager, channel_resolver)
    
    # 创建任务上下文
    task_context = TaskContext()
    
    # 设置监听结束时间
    end_time = datetime.now() + timedelta(hours=duration_hours)
    print(f"开始监听，将在 {end_time} 结束")
    
    # 启动监听任务
    monitor_task = asyncio.create_task(monitor.start_monitoring(task_context))
    
    try:
        # 等待直到结束时间
        while datetime.now() < end_time:
            if task_context.cancel_token.is_cancelled:
                break
            await asyncio.sleep(10)  # 每10秒检查一次
        
        # 时间到，取消任务
        task_context.cancel_token.cancel()
        await monitor.stop_monitoring()
        
    except asyncio.CancelledError:
        # 手动取消
        await monitor.stop_monitoring()
    
    await monitor_task
    print("监听任务已结束")
```

### 支持的事件类型

| 事件名称 | 参数 | 说明 |
|---------|------|-----|
| status | message | 状态更新消息 |
| info | message | 信息性消息 |
| warning | message | 警告消息 |
| error | message, error_type, recoverable, details? | 错误信息，包含错误类型和是否可恢复 |
| debug | message | 调试消息 |
| progress | percentage, current, total, task_type | 进度更新，包含百分比、当前进度、总数量和任务类型 |
| complete | total_forwarded | 任务完成事件，包含总转发数量 |
| media_found | media_type, media_id, channel_info | 发现媒体文件事件 |
| media_download_started | media_id, media_type, size | 开始下载媒体文件事件 |
| media_download_success | media_id, file_path, size | 媒体下载成功事件 |
| media_download_failed | media_id, error | 媒体下载失败事件 |
| media_group_downloaded | group_id, message_count, file_count | 媒体组下载完成事件 |
| media_group_forwarded | message_ids, channel_info, count | 媒体组转发成功事件 |
| message_forwarded | message_id, channel_info | 消息转发成功事件 |
| media_group_uploaded | group_id, message_ids, success_targets, failed_targets | 媒体组上传完成事件 |
| message_received | message_id, channel_info | 收到新消息事件 |
| media_group_received | group_id, channel_info | 收到新媒体组事件 |
| text_replaced | old_text, new_text, replacements | 文本替换事件，包含原文本、新文本和替换规则列表 |

## 任务控制使用

TG-Forwarder 支持对长时间运行的任务进行控制，实现暂停、恢复和取消功能：

```python
from src.utils.controls import TaskContext, CancelToken, PauseToken

# 创建任务控制对象
cancel_token = CancelToken()
pause_token = PauseToken()
task_context = TaskContext(cancel_token, pause_token)

# 传递给任务执行函数
await downloader.download_message_media(message, download_dir, task_context)

# 在其他地方控制任务
# 暂停任务
pause_token.pause()

# 恢复任务
pause_token.resume()

# 取消任务
cancel_token.cancel()
```

### 在异步代码中使用

```python
async def some_function():
    # 等待任务如果被暂停
    if task_context:
        await task_context.wait_if_paused()
        
    # 检查是否已取消
    if task_context and task_context.cancel_token.is_cancelled:
        return
```

## 错误处理

TG-Forwarder 提供了详细的错误类型和恢复信息，可以通过监听 error 事件获取：

```python
def handle_error(error_message, error_type, recoverable, details=None):
    print(f"错误: {error_message}")
    print(f"错误类型: {error_type}")
    print(f"是否可恢复: {recoverable}")
    if details:
        print(f"详细信息: {details}")

forwarder.on("error", handle_error)
```

## 贡献

欢迎提交问题和功能请求！如果您想贡献代码，请先提交一个 issue 描述您的更改。
