# 禁止转发频道消息转发示例

这个目录包含各种针对 Telegram 频道监听和消息转发的示例程序。

## 禁止转发频道消息转发器（restricted_channel_forwarder.py）

这个示例程序演示了如何监听禁止转发的 Telegram 频道，并将消息转发到另一个目标频道。程序主要特点：

- 支持监听禁止转发的频道
- 使用流式下载上传处理媒体消息
- 支持处理媒体组消息
- 处理各种类型的消息（文本、图片、视频等）
- 支持 SOCKS5 代理
- 支持频道链接解析，可直接使用 t.me 链接或 @username
- 错误处理和重试机制

### 使用方法

1. 修改源代码中的配置信息：

   - API_ID, API_HASH, PHONE_NUMBER（必填）
   - SOURCE_CHANNEL（要监听的频道链接或用户名）
   - TARGET_CHANNEL（要转发到的目标频道链接或用户名）

2. 配置代理（可选）：

   ```python
   USE_PROXY = True                # 是否使用代理
   PROXY_TYPE = "SOCKS5"           # 代理类型，目前仅支持SOCKS5
   PROXY_HOST = "127.0.0.1"        # 代理服务器地址
   PROXY_PORT = 1080               # 代理服务器端口
   PROXY_USERNAME = None           # 代理用户名（如不需要则为None）
   PROXY_PASSWORD = None           # 代理密码（如不需要则为None）
   ```

3. 运行程序：

   ```bash
   python restricted_channel_forwarder.py
   ```

4. 首次运行时，程序会要求您登录 Telegram 账号

   - 输入验证码
   - 如需要，输入两步验证密码

5. 登录成功后，程序将解析频道链接并开始监听转发消息

### 频道链接格式支持

程序支持多种频道标识符格式：

- Telegram 频道链接：`https://t.me/example_channel`
- Telegram 用户名：`@example_channel`
- 频道 ID：`-1001234567890`

频道解析功能会自动从链接中提取用户名，并解析为完整的频道 ID，以便进行监听和转发操作。

### 技术亮点

- 频道解析：自动解析各种格式的频道标识符，获取频道 ID
- 媒体组处理：收集、排序、流式处理和批量发送
- 流式转发：使用 Pyrogram 的 `stream_media` 实现高效传输
- 异步处理：全异步架构提高并发性能
- 代理支持：通过 SOCKS5 代理连接 Telegram 服务器

### 注意事项

- 确保有足够的权限访问源频道和发送消息到目标频道
- 转发大量消息可能会触发 Telegram 的限流机制
- 临时文件保存在 `tmp/restricted_forward` 目录
- 代理服务器必须支持 TCP 连接，并能访问 Telegram 服务器
