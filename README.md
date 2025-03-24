# TG-Manager

TG-Manager 是一个功能强大的 Telegram 频道管理工具，专为内容创作者、频道管理员和媒体收藏者设计。它提供了一系列功能，包括频道内容下载、上传、自动转发和实时监控。

## 功能特点

- **批量下载**：从任意公开或私有（已加入）频道下载所有类型的媒体文件
- **批量上传**：将本地媒体文件批量上传到指定频道
- **消息转发**：在不同频道之间批量转发消息，支持多目标频道
- **实时监控**：监控源频道的新消息并自动转发到多个目标频道
- **媒体过滤**：可选择性地只处理特定类型的媒体（图片、视频、文档等）
- **代理支持**：内置代理功能，确保在各种网络环境下都能正常工作
- **灵活配置**：通过配置文件实现所有功能的精细控制
- **重试机制**：内置智能重试和限速功能，避免触发Telegram API限制

## 安装

### 系统要求

- Python 3.8 或更高版本
- 网络连接以访问 Telegram API
- 足够的磁盘空间用于下载的媒体文件

### 安装步骤

1. **克隆仓库**

```bash
git clone https://github.com/yourusername/TG-Manager.git
cd TG-Manager
```

2. **安装依赖**

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

3. **配置程序**

将 `config.ini.example` 复制为 `config.ini` 并按照注释进行配置：

```bash
cp config.ini.example config.ini
```

然后编辑 `config.ini` 文件，填入您的 Telegram API ID 和 API Hash，可从 [Telegram API开发工具](https://my.telegram.org/apps) 获取。

## 配置说明

配置文件分为几个主要部分：

### GENERAL 部分

```ini
[GENERAL]
api_id = 你的API ID
api_hash = 你的API Hash
```

- `api_id` 和 `api_hash`：您的 Telegram API 凭据
- `limit` 和 `pause_time`：操作限制和暂停时间（秒）
- `timeout` 和 `max_retries`：连接超时和最大重试次数
- `proxy_*`：代理设置（如需使用）

### DOWNLOAD 部分

下载特定频道的消息和媒体：

```ini
[DOWNLOAD]
source_channels = ["@channel_name", "https://t.me/channel_name2"]
```

- `start_id` 和 `end_id`：下载消息的ID范围（0表示从头开始/到最新）
- `source_channels`：源频道列表，支持用户名、链接或ID
- `organize_by_chat`：是否按频道分类保存文件
- `download_path`：下载文件保存路径
- `media_types`：需要下载的媒体类型列表

### UPLOAD 部分

将本地文件上传到频道：

```ini
[UPLOAD]
target_channels = ["@target_channel"]
directory = uploads
```

- `target_channels`：目标频道列表
- `directory`：要上传的本地文件目录
- `caption_template`：上传文件的标题模板

### FORWARD 部分

在频道之间转发消息：

```ini
[FORWARD]
forward_channel_pairs = [
  {"source_channel": "https://t.me/source_channel", 
   "target_channels": ["https://t.me/target1", "https://t.me/target2"]
  }
]
```

- `forward_channel_pairs`：转发频道配对列表
- `remove_captions`：是否移除原始消息的标题
- `media_types`：需要转发的媒体类型
- `forward_delay`：转发延迟（秒）
- `start_id` 和 `end_id`：转发消息的ID范围

### MONITOR 部分

监控频道新消息并实时转发：

```ini
[MONITOR]
monitor_channel_pairs = [
  {"source_channel": "https://t.me/source_channel", 
   "target_channels": ["https://t.me/target1", "https://t.me/target2"]
  }
]
```

- `monitor_channel_pairs`：监控频道配对列表
- `remove_captions`：是否移除原始消息的标题
- `media_types`：需要转发的媒体类型
- `duration`：监控持续时间
- `forward_delay`：转发延迟（秒）

## 使用方法

TG-Manager 提供了多种运行模式：

### 下载模式

从指定频道下载所有媒体：

```bash
python main.py --download
```

### 上传模式

将本地文件上传到指定频道：

```bash
python main.py --upload
```

### 转发模式

在频道之间转发消息：

```bash
python main.py --forward
```

### 监控模式

监控源频道并实时转发新消息：

```bash
python main.py --monitor
```

### 组合模式

可以组合多个模式同时运行：

```bash
python main.py --download --upload
```

## 常见问题

### 登录验证

首次运行时，程序会请求您登录 Telegram 账户。您可以通过以下方式之一进行验证：

1. 手机号验证：输入您的手机号（带国家代码）
2. 验证码：输入发送到您手机上的验证码
3. 两步验证：如果启用了两步验证，则需要输入密码

### FloodWait 错误

如果收到 FloodWait 错误，这表示您已达到 Telegram API 的速率限制。程序会自动等待指定的时间后继续操作。

### 下载文件丢失

请确保您有足够的磁盘空间，并且对下载目录有写入权限。某些媒体可能因为权限限制无法下载。

## 注意事项

- 请负责任地使用此工具，尊重 Telegram 的服务条款和内容政策
- 仅转发您有权转发的内容
- 请勿使用此工具进行垃圾消息发送或滥用
- 大量操作可能会触发 Telegram 的速率限制，请合理设置操作间隔

## 许可证

本项目采用 MIT 许可证 - 详情见 [LICENSE](LICENSE) 文件

## 开发者

- [您的名字/组织] - 初始开发和维护

## 贡献

欢迎贡献！请随时提交 Pull Request 或创建 Issue。