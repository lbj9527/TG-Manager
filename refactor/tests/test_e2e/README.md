# TG-Manager 端到端测试 (E2E Tests)

## 概述

端到端测试用于验证TG-Manager重构项目与真实Telegram API的集成，确保客户端管理器的核心功能正常工作。

## 测试内容

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

## 文件说明

- **e2e_config.py**: E2E测试配置管理
- **test_client_manager_e2e.py**: 基于pytest的客户端E2E测试
- **test_client_e2e_simple.py**: 用户友好的简化E2E测试脚本
- **run_e2e_tests.py**: E2E测试运行器
- **env.e2e.example**: E2E环境变量示例文件
- **E2E_TEST_SETUP.md**: E2E测试设置详细指南
- **E2E_TEST_GUIDE.md**: E2E测试运行指南
- **E2E_TEST_COMPLETION.md**: E2E测试完成情况总结

## 环境准备

### 1. 获取Telegram API凭据
1. 访问 https://my.telegram.org/apps
2. 登录你的Telegram账号
3. 创建一个新的应用
4. 记录API ID和API Hash

### 2. 配置环境变量
```bash
# 复制示例文件
cp env.e2e.example .env.e2e

# 编辑配置文件，填入你的真实凭据
# TELEGRAM_API_ID=你的API ID
# TELEGRAM_API_HASH=你的API Hash
# TELEGRAM_PHONE_NUMBER=你的手机号码
```

### 3. 代理设置（可选）
如果需要使用代理，在`.env.e2e`中配置：
```bash
USE_PROXY=true
PROXY_SCHEME=socks5
PROXY_HOST=127.0.0.1
PROXY_PORT=7890
```

## 运行测试

### 运行所有E2E测试
```bash
python test_client_e2e_simple.py
```

### 运行特定测试
```bash
# 完整登录流程测试
python test_client_e2e_simple.py test_complete_login_flow

# 会话恢复功能测试
python test_client_e2e_simple.py test_session_restoration

# 连接监控功能测试
python test_client_e2e_simple.py test_connection_monitoring

# 错误处理测试
python test_client_e2e_simple.py test_error_handling

# 性能测试
python test_client_e2e_simple.py test_performance
```

### 使用pytest运行
```bash
# 运行基于pytest的E2E测试
pytest test_client_manager_e2e.py -v

# 运行所有E2E测试
python run_e2e_tests.py
```

## 测试结果

当前E2E测试状态：
- ✅ **完整登录流程测试**: 通过
- ✅ **会话恢复功能测试**: 通过
- ✅ **连接监控功能测试**: 通过
- ✅ **错误处理测试**: 通过
- ✅ **性能测试**: 通过

**总体成功率**: 100% (5/5)

## 注意事项

1. **首次运行**: 首次运行需要输入Telegram验证码
2. **会话文件**: 测试会创建`test_session_e2e.session`文件
3. **代理要求**: 确保代理服务器正常运行
4. **网络连接**: 需要稳定的网络连接
5. **API限制**: 遵守Telegram API的速率限制

## 故障排除

### 常见问题

1. **验证码问题**
   - 确保手机号码格式正确（包含国家代码）
   - 检查Telegram应用是否收到验证码

2. **代理问题**
   - 验证代理服务器是否正常运行
   - 检查代理配置是否正确

3. **API凭据问题**
   - 确认API ID和API Hash正确
   - 检查应用是否在Telegram中正确创建

4. **网络问题**
   - 检查网络连接是否稳定
   - 确认可以访问Telegram服务器

### 日志查看
测试运行时会显示详细的日志信息，包括：
- 配置加载状态
- 客户端初始化过程
- 登录流程状态
- 错误信息详情

## 测试报告

详细的测试报告请参考：
- [E2E_TEST_COMPLETION.md](E2E_TEST_COMPLETION.md) - 测试完成情况
- [E2E_TEST_GUIDE.md](E2E_TEST_GUIDE.md) - 详细运行指南
- [E2E_TEST_SETUP.md](E2E_TEST_SETUP.md) - 环境设置指南 