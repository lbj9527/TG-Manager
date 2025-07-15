# TG-Manager 端到端测试配置指南

## 📋 概述

端到端测试用于验证TG-Manager重构项目的真实Telegram登录、会话管理和自动重连功能。这些测试需要真实的Telegram API凭据和手机号码。

## 🔧 配置步骤

### 步骤 1: 获取 Telegram API 凭据

#### 1.1 访问 Telegram 开发者页面
1. 打开浏览器，访问：https://my.telegram.org/apps
2. 使用你的 Telegram 账号登录

#### 1.2 创建应用
1. 点击 "Create new application"
2. 填写应用信息：
   - **App title**: `TG-Manager E2E Test`
   - **Short name**: `tgmanager_e2e`
   - **Platform**: 选择 "Desktop"
   - **Description**: `TG-Manager 端到端测试应用`

#### 1.3 获取 API 凭据
创建完成后，你会看到：
- **api_id**: 一串数字（如：12345678）
- **api_hash**: 32位字符串（如：abcdef1234567890abcdef1234567890）

### 步骤 2: 创建配置文件

#### 2.1 复制配置文件模板
```bash
cd refactor
cp env.e2e.example .env.e2e
```

#### 2.2 编辑配置文件
打开 `.env.e2e` 文件，填写你的实际配置：

```env
# Telegram API 配置
TELEGRAM_API_ID=你的实际API_ID数字
TELEGRAM_API_HASH=你的实际API_Hash字符串

# 用户登录配置
# 你的Telegram手机号码（包含国家代码，如：+8613800138000）
TELEGRAM_PHONE_NUMBER=你的手机号码

# 会话配置
TELEGRAM_SESSION_NAME=test_session_e2e
TELEGRAM_SESSION_PATH=test_sessions

# 代理配置（可选）
USE_PROXY=false

# 代理服务器配置（仅在 USE_PROXY=true 时需要）
PROXY_SCHEME=socks5
PROXY_HOST=127.0.0.1
PROXY_PORT=1080
PROXY_USERNAME=
PROXY_PASSWORD=

# 测试配置
TEST_TIMEOUT=300
MONITOR_INTERVAL=10
MAX_RECONNECT_ATTEMPTS=3
RECONNECT_DELAY=2.0

# 登录配置
CODE_TIMEOUT=60
# 两步验证密码（如果启用了2FA）
TWO_FA_PASSWORD=
```

### 步骤 3: 配置代理（可选）

#### 3.1 不使用代理
```env
USE_PROXY=false
```

#### 3.2 使用 SOCKS5 代理
```env
USE_PROXY=true
PROXY_SCHEME=socks5
PROXY_HOST=127.0.0.1
PROXY_PORT=1080
PROXY_USERNAME=你的代理用户名
PROXY_PASSWORD=你的代理密码
```

#### 3.3 使用 HTTP 代理
```env
USE_PROXY=true
PROXY_SCHEME=http
PROXY_HOST=proxy.example.com
PROXY_PORT=8080
PROXY_USERNAME=你的代理用户名
PROXY_PASSWORD=你的代理密码
```

## 🧪 运行测试

### 运行所有测试
```bash
cd refactor
python run_e2e_tests.py
```

### 运行单个测试
```bash
# 运行登录流程测试
python run_e2e_tests.py test_complete_login_flow

# 运行会话恢复测试
python run_e2e_tests.py test_session_restoration

# 运行连接监控测试
python run_e2e_tests.py test_connection_monitoring

# 运行自动重连测试
python run_e2e_tests.py test_auto_reconnect
```

### 查看帮助
```bash
python run_e2e_tests.py --help
```

## 📊 测试内容

### 1. 完整登录流程测试 (`test_complete_login_flow`)
- 验证首次登录功能
- 检查用户认证状态
- 验证用户信息获取
- 测试客户端状态管理

### 2. 会话恢复测试 (`test_session_restoration`)
- 测试会话文件创建
- 验证会话恢复功能
- 检查用户信息一致性

### 3. 连接监控测试 (`test_connection_monitoring`)
- 验证连接状态检查
- 测试连接监控功能
- 检查连接稳定性

### 4. 自动重连测试 (`test_auto_reconnect`)
- 模拟连接丢失
- 测试自动重连机制
- 验证重连后状态恢复

### 5. 错误处理测试 (`test_error_handling`)
- 测试无效配置处理
- 验证错误恢复机制

### 6. 配置验证测试 (`test_config_validation`)
- 验证必需配置检查
- 测试配置完整性

### 7. 会话管理测试 (`test_session_management`)
- 测试会话数据库修复
- 验证状态获取功能

### 8. 性能测试 (`test_performance`)
- 测试初始化性能
- 验证连接检查性能

## 🔍 配置验证

### 验证配置是否正确
```bash
cd refactor
python tests/test_e2e/e2e_config.py
```

如果配置正确，你会看到类似输出：
```
=== 端到端测试配置信息 ===
Telegram API ID: 12345678...
Telegram API Hash: abcdef12...
Phone Number: +8613800138000
Session Name: test_session_e2e
Session Path: test_sessions
Code Timeout: 60秒
2FA Password: 未设置
代理配置: 未启用
==========================
```

## ⚠️ 注意事项

### 安全注意事项
1. **保护 API 凭据**：不要将 `.env.e2e` 文件提交到版本控制系统
2. **不要分享凭据**：API 凭据是敏感信息，不要与他人分享
3. **定期更换凭据**：建议定期更换 API 凭据以提高安全性

### 测试注意事项
1. **网络环境**：确保网络连接稳定，能够访问 Telegram 服务器
2. **手机号码格式**：手机号码必须包含国家代码（如：+86）
3. **两步验证**：如果启用了两步验证，必须在配置中提供密码
4. **测试频率**：避免频繁运行测试，以免触发 Telegram 的限制

### 代理注意事项
1. **代理稳定性**：确保代理服务器稳定可靠
2. **代理类型**：支持 SOCKS5、HTTP、HTTPS 代理
3. **代理认证**：如果代理需要认证，请提供正确的用户名和密码

## 🐛 常见问题

### Q1: 配置验证失败
**问题**：运行配置验证时显示错误
**解决**：
1. 检查 `.env.e2e` 文件是否存在
2. 确认所有必需字段都已填写
3. 验证 API ID 和 API Hash 是否正确

### Q2: 登录失败
**问题**：测试时登录失败
**解决**：
1. 检查手机号码格式是否正确（包含国家代码）
2. 确认 API ID 和 API Hash 有效
3. 如果启用了两步验证，检查密码是否正确
4. 检查网络连接是否正常

### Q3: 代理连接失败
**问题**：使用代理时连接失败
**解决**：
1. 检查代理服务器是否正常运行
2. 验证代理地址和端口是否正确
3. 确认代理用户名和密码是否正确
4. 检查防火墙设置

### Q4: 验证码超时
**问题**：验证码输入超时
**解决**：
1. 增加 `CODE_TIMEOUT` 的值（默认60秒）
2. 确保手机能够及时收到验证码
3. 检查网络连接是否稳定

### Q5: 会话文件权限错误
**问题**：无法创建或访问会话文件
**解决**：
1. 确保 `test_sessions` 目录存在且有写权限
2. 检查磁盘空间是否充足
3. 确认当前用户有足够的权限

## 📞 技术支持

如果在配置或运行测试过程中遇到问题，请：

1. 检查本文档的常见问题部分
2. 查看测试输出的详细错误信息
3. 确认所有配置项都已正确填写
4. 验证网络连接和代理设置

## 🔄 更新日志

- **v1.0.0**: 初始版本，支持基本的登录和会话管理测试
- **v1.1.0**: 添加了电话号码和两步验证支持
- **v1.2.0**: 增强了错误处理和配置验证
- **v1.3.0**: 添加了性能测试和详细的配置指南 