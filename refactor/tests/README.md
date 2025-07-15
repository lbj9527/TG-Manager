# TG-Manager 重构项目测试目录

## 目录结构

```
tests/
├── README.md                    # 测试目录说明文档
├── conftest.py                  # pytest配置文件
├── test_abstractions/           # 抽象层测试
│   ├── test_base_message_processor.py
│   ├── test_base_downloader.py
│   ├── test_base_uploader.py
│   └── test_base_handler.py
├── test_common/                 # 公共模块测试
│   ├── test_message_fetcher.py
│   ├── test_channel_validator.py
│   ├── test_flood_wait_handler.py
│   ├── test_error_handler.py
│   ├── test_text_processor.py
│   ├── test_message_filter.py
│   └── test_media_group_processor.py
├── test_config/                 # 配置管理测试
│   ├── test_config_manager.py
│   ├── test_ui_config_manager.py
│   ├── test_plugin_config.py
│   └── test_config_utils.py
├── test_core/                   # 核心模块测试
│   ├── test_client_manager.py
│   ├── test_plugin_manager.py
│   ├── test_event_bus.py
│   └── test_app_core.py
├── test_e2e/                    # 端到端测试
│   ├── README.md                # E2E测试说明
│   ├── e2e_config.py            # E2E测试配置
│   ├── test_client_manager_e2e.py # 客户端E2E测试
│   ├── test_client_e2e_simple.py # 简化E2E测试脚本
│   ├── run_e2e_tests.py         # E2E测试运行器
│   ├── env.e2e.example          # E2E环境变量示例
│   ├── E2E_TEST_SETUP.md        # E2E测试设置文档
│   ├── E2E_TEST_GUIDE.md        # E2E测试运行指南
│   └── E2E_TEST_COMPLETION.md   # E2E测试完成情况
└── test_plugins/                # 插件测试
    ├── test_forward_plugin.py
    ├── test_monitor_plugin.py
    ├── test_download_plugin.py
    └── test_upload_plugin.py
```

## 测试分类

### 1. 单元测试 (Unit Tests)
- **test_abstractions/**: 抽象层接口测试
- **test_common/**: 公共模块功能测试
- **test_config/**: 配置管理测试
- **test_core/**: 核心模块测试
- **test_plugins/**: 插件功能测试

### 2. 端到端测试 (E2E Tests)
- **test_e2e/**: 真实Telegram API测试
  - 客户端登录流程测试
  - 会话管理测试
  - 连接监控测试
  - 错误处理测试
  - 性能测试

## 运行测试

### 运行所有单元测试
```bash
# 在refactor目录下运行
python run_tests.py
```

### 运行特定模块测试
```bash
# 运行核心模块测试
pytest tests/test_core/

# 运行公共模块测试
pytest tests/test_common/

# 运行插件测试
pytest tests/test_plugins/
```

### 运行端到端测试
```bash
# 运行所有E2E测试
cd tests/test_e2e/
python test_client_e2e_simple.py

# 运行特定E2E测试
python test_client_e2e_simple.py test_complete_login_flow
python test_client_e2e_simple.py test_session_restoration
python test_client_e2e_simple.py test_connection_monitoring
python test_client_e2e_simple.py test_error_handling
python test_client_e2e_simple.py test_performance
```

## 测试覆盖率

当前测试覆盖率：
- **总测试用例**: 127个
- **通过率**: 100% (127/127)
- **测试模块**: 8个核心模块

## 测试技术栈

- **pytest**: 测试框架
- **pytest-asyncio**: 异步测试支持
- **unittest.mock**: Mock和Patch
- **端到端测试**: 真实Telegram API测试

## 测试策略

- **单元测试**: 每个模块独立测试，覆盖率100%
- **集成测试**: 模块间协作测试
- **异步测试**: 所有异步方法都有对应测试
- **异常测试**: 错误处理和恢复机制测试
- **Mock测试**: 外部依赖完全Mock，确保测试独立性
- **端到端测试**: 真实Telegram API测试，验证登录、会话管理、自动重连

## 注意事项

1. **E2E测试需要真实配置**: 端到端测试需要有效的Telegram API凭据
2. **代理配置**: 如果使用代理，需要在`.env.e2e`文件中配置
3. **测试隔离**: 每个测试都应该独立运行，不依赖其他测试的状态
4. **资源清理**: 测试完成后会自动清理资源，包括session文件 