# TG Forwarder

TG Forwarder 是一个功能强大的 Telegram 消息转发工具，用于在不同的 Telegram 频道、群组或聊天之间转发消息。

## 功能特点

- **历史消息转发**：将源频道的历史消息按原格式转发到目标频道
- **媒体文件下载**：下载源频道的图片、视频、文件等媒体内容
- **本地文件上传**：将本地文件上传至目标频道，支持媒体组
- **实时消息监听**：监听源频道的新消息并实时转发至目标频道

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

3. **本地文件上传**：

```bash
python run.py upload
```

4. **实时消息监听**：

```bash
python run.py startmonitor
```

## 配置说明

详细的配置信息请参考 `config.json` 文件，主要包括：

- **通用配置**：API 凭据、代理设置、消息限制等
- **下载配置**：源频道、消息范围、下载路径等
- **上传配置**：目标频道、本地文件路径等
- **转发配置**：频道映射关系、转发延迟、媒体类型等
- **监听配置**：监听频道、持续时间、转发设置等

## 功能说明

### 历史消息转发

支持在不同频道间转发历史消息，可以保留原始格式并设置消息筛选条件。对于禁止转发的频道，会自动采用"下载后上传"的方式完成转发。

### 媒体文件下载

可以下载指定频道的历史消息中包含的媒体文件，支持多种文件类型，并能按源频道分类保存。

### 本地文件上传

将本地文件上传到指定频道，支持按文件夹组织媒体组，并可以设置自定义文本。

### 实时消息监听

监听指定频道的新消息，并实时转发到目标频道，支持设置消息过滤条件和监听时长。
