# TG-Manager 端到端测试指南

## 概述

本指南介绍如何运行TG-Manager重构项目的端到端测试，验证真实的Telegram登录、会话管理和自动重连功能。

## 测试内容

端到端测试包含以下核心功能测试：

### 1. 完整登录流程测试
- 验证Telegram API凭据有效性
- 测试手机号验证码登录流程
- 测试两步验证（2FA）功能
- 验证用户信息获取

### 2. 会话恢复功能测试
- 测试首次登录创建会话文件
- 测试后续登录恢复会话
- 验证用户信息一致性

### 3. 连接监控功能测试
- 测试连接状态检查
- 验证连接监控机制
- 测试连接稳定性

### 4. 错误处理测试
- 测试无效配置处理
- 验证错误恢复机制
- 测试异常情况处理

### 5. 性能测试
- 测试初始化时间
- 测试连接检查响应时间
- 验证性能指标

## 环境准备

### 1. 获取Telegram API凭据

1. 访问 https://my.telegram.org/apps
2. 登录你的Telegram账号
3. 创建一个新的应用
4. 记录以下信息：
   - **API ID**: 数字ID
   - **API Hash**: 32位字符串

### 2. 准备手机号码

- 确保你有可用的手机号码
- 号码格式：`+国家代码手机号码`（如：`+8613800138000`）
- 该号码必须能够接收Telegram验证码

### 3. 两步验证（可选）

如果你的Telegram账号启用了两步验证：
- 准备你的两步验证密码
- 在测试配置中设置 `TWO_FA_PASSWORD`

### 4. 代理设置（可选）

如果你需要使用代理访问Telegram：
- 准备SOCKS5或HTTP代理服务器
- 记录代理服务器地址和端口
- 如果需要认证，准备用户名和密码

## 配置设置

### 1. 复制环境变量配置文件

```bash
cd refactor
cp env.e2e.example .env.e2e
```

### 2. 编辑配置文件

编辑 `.env.e2e` 文件，填写以下信息：

```bash
# Telegram API配置
TELEGRAM_API_ID=你的API_ID
TELEGRAM_API_HASH=你的API_HASH
TELEGRAM_PHONE_NUMBER=你的手机号码（包含国家代码）

# 两步验证（如果启用）
TWO_FA_PASSWORD=你的两步验证密码

# 代理配置（如果需要）
USE_PROXY=false
PROXY_SCHEME=socks5
PROXY_HOST=代理服务器地址
PROXY_PORT=代理服务器端口
PROXY_USERNAME=代理用户名
PROXY_PASSWORD=代理密码

# 测试配置
TELEGRAM_SESSION_NAME=test_session_e2e
TELEGRAM_SESSION_PATH=test_sessions
CODE_TIMEOUT=60
MAX_RECONNECT_ATTEMPTS=3
RECONNECT_DELAY=2.0
MONITOR_INTERVAL=10
TEST_TIMEOUT=300
```

### 3. 验证配置

运行配置验证：

```bash
python test_e2e/e2e_config.py
```

## 运行测试

### 1. 运行所有测试

```bash
cd refactor
python test_client_e2e_simple.py
```

### 2. 运行指定测试

```bash
# 测试完整登录流程
python test_client_e2e_simple.py test_complete_login_flow

# 测试会话恢复功能
python test_client_e2e_simple.py test_session_restoration

# 测试连接监控功能
python test_client_e2e_simple.py test_connection_monitoring

# 测试错误处理
python test_client_e2e_simple.py test_error_handling

# 测试性能
python test_client_e2e_simple.py test_performance
```

### 3. 查看帮助

```bash
python test_client_e2e_simple.py --help
```

## 测试流程

### 首次运行测试

1. **配置验证**: 系统会检查环境变量配置
2. **登录流程**: 如果是首次登录，会要求输入验证码
3. **会话创建**: 登录成功后创建会话文件
4. **功能验证**: 验证各种功能是否正常工作
5. **资源清理**: 测试完成后清理资源

### 后续运行测试

1. **会话恢复**: 自动恢复之前的会话
2. **功能验证**: 验证各种功能是否正常工作
3. **资源清理**: 测试完成后清理资源

## 验证码输入

在首次登录时，系统会要求输入验证码：

1. 检查你的手机，接收Telegram发送的验证码
2. 在测试输出中看到验证码输入提示
3. 输入收到的验证码
4. 如果启用了两步验证，还需要输入两步验证密码

## 测试结果解读

### 成功结果

```
✅ 客户端管理器初始化成功 - 耗时: 5.23秒
✅ 用户认证成功
✅ 客户端连接成功
✅ 用户信息获取成功: 张三 (@zhangsan)
   手机号码: +8613800138000
   用户ID: 123456789
✅ 客户端状态: {...}
```

### 失败结果

```
❌ 客户端管理器初始化失败 - 耗时: 30.15秒
❌ 用户认证失败
❌ 客户端连接失败
❌ 无法获取用户信息
```

## 常见问题

### 1. 配置错误

**问题**: `错误: 缺少 TELEGRAM_API_ID 环境变量`

**解决方案**:
- 检查 `.env.e2e` 文件是否存在
- 确认 `TELEGRAM_API_ID` 和 `TELEGRAM_API_HASH` 已正确设置
- 确认 `TELEGRAM_PHONE_NUMBER` 格式正确

### 2. 验证码问题

**问题**: `验证码无效，请检查验证码`

**解决方案**:
- 确认手机号码正确
- 检查是否收到验证码短信
- 确认验证码输入正确
- 验证码有时效性，请及时输入

### 3. 两步验证问题

**问题**: `需要两步验证密码，但配置中未提供`

**解决方案**:
- 在 `.env.e2e` 文件中设置 `TWO_FA_PASSWORD`
- 确认两步验证密码正确

### 4. 网络连接问题

**问题**: `连接超时` 或 `网络错误`

**解决方案**:
- 检查网络连接
- 如果在中国大陆，可能需要配置代理
- 在 `.env.e2e` 文件中启用代理配置

### 5. API限制问题

**问题**: `FloodWait` 或 `API限制`

**解决方案**:
- 等待一段时间后重试
- 检查API使用频率
- 确认API凭据正确

## 性能基准

### 正常性能指标

- **初始化时间**: < 30秒
- **连接检查时间**: < 5秒
- **会话恢复时间**: < 10秒
- **内存使用**: < 100MB

### 性能优化建议

- 使用稳定的网络连接
- 配置合适的代理服务器
- 避免频繁运行测试
- 定期清理会话文件

## 安全注意事项

### 1. 凭据安全

- 不要将 `.env.e2e` 文件提交到版本控制系统
- 定期更换API凭据
- 不要在公共环境中运行测试

### 2. 会话安全

- 测试会话文件包含敏感信息
- 定期清理测试会话文件
- 不要在共享环境中运行测试

### 3. 隐私保护

- 测试过程中会获取用户信息
- 确保测试环境安全
- 不要泄露测试日志

## 故障排除

### 1. 查看详细日志

```bash
# 启用详细日志
export LOG_LEVEL=DEBUG
python test_client_e2e_simple.py
```

### 2. 清理测试环境

```bash
# 清理测试会话文件
rm -rf test_sessions/
```

### 3. 重置配置

```bash
# 重新配置环境变量
cp env.e2e.example .env.e2e
# 编辑 .env.e2e 文件
```

## 联系支持

如果在运行测试过程中遇到问题：

1. 查看本文档的常见问题部分
2. 检查测试日志输出
3. 确认环境配置正确
4. 联系项目维护者

---

**注意**: 端到端测试需要真实的Telegram API凭据和网络连接，请确保在安全的环境中运行测试。 