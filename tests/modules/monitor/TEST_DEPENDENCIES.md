# 端到端测试系统依赖清单

## 📋 测试系统组成

### 🎯 核心测试脚本

#### 1. 主要测试程序
- **`comprehensive_e2e_test.py`** - 全面端到端测试系统 (21KB)
  - 主要入口点，运行所有测试套件
  - 包含基础功能、过滤逻辑、文本替换、边界情况测试
  - 生成详细的测试报告

#### 2. 专项测试模块
- **`test_media_group_scenarios.py`** - 媒体组专项测试 (18KB)
  - 10个媒体组测试场景
  - 验证媒体组聚合、过滤、转发功能
  - 被主测试程序调用

#### 3. 测试数据工厂
- **`test_monitor_comprehensive.py`** - 测试工具和数据工厂 (32KB)
  - `TestDataFactory` 类：创建各种测试消息对象
  - 包含 pytest 单元测试
  - 提供 Mock 对象创建方法

### 🗂️ 测试数据文件

#### 1. 必需的测试数据目录结构
```
test_data/
├── sample_messages/
│   ├── text_messages.json          # 文本消息样本 (5.2KB)
│   ├── media_messages.json         # 媒体消息样本 (7.5KB)
│   └── media_groups.json          # 媒体组样本 (15KB)
├── sample_configs/
│   ├── basic_forward.json          # 基础转发配置
│   ├── keyword_filter.json         # 关键词过滤配置
│   ├── media_only.json            # 媒体类型过滤配置
│   ├── multi_target.json          # 多目标配置
│   ├── advanced_filter.json       # 高级过滤配置
│   └── strict_filter.json         # 严格过滤配置
├── realistic_scenarios.json        # 真实场景数据 (2.7KB)
└── performance_benchmarks.json     # 性能基准数据 (7.7KB)
```

#### 2. 可选支持文件
- **`validate_test_data.py`** - 测试数据验证脚本
- **`generate_test_media.py`** - 生成测试媒体文件
- **`media_files/`** - 媒体文件目录 (可选)
- **`expected_outputs/`** - 预期输出目录 (可选)

### 🔧 配置和支持文件

#### 1. 测试配置
- **`pytest.ini`** - pytest 配置文件 (836B)
- **`conftest.py`** - pytest 配置和夹具 (12KB)

#### 2. 文档
- **`README_TEST_GUIDE.md`** - 测试指南 (10KB)

### 📦 被测试的源代码模块

#### 1. 监听模块核心
```
src/modules/monitor/
├── core.py                     # 监听核心模块
├── media_group_handler.py      # 媒体组处理器 ✅
├── message_processor.py        # 消息处理器
├── text_filter.py             # 文本过滤器
└── restricted_forward_handler.py  # 受限转发处理器
```

#### 2. 工具模块
```
src/utils/
├── ui_config_models.py         # UI配置模型
├── channel_resolver.py         # 频道解析器
├── ui_config_manager.py        # 配置管理器
└── logger.py                   # 日志工具
```

## 🚀 运行方式

### 方式1: 运行完整测试套件
```bash
cd tests/modules/monitor
python comprehensive_e2e_test.py
```

### 方式2: 运行媒体组专项测试
```bash
cd tests/modules/monitor
python test_media_group_scenarios.py
```

### 方式3: 使用pytest运行
```bash
cd tests/modules/monitor
pytest test_monitor_comprehensive.py -v
```

## 📋 依赖检查清单

### ✅ 必需文件 (运行测试前必须存在)

#### 测试脚本
- [ ] `comprehensive_e2e_test.py`
- [ ] `test_media_group_scenarios.py`
- [ ] `test_monitor_comprehensive.py`

#### 源代码模块
- [ ] `src/modules/monitor/media_group_handler.py`
- [ ] `src/modules/monitor/core.py`
- [ ] `src/modules/monitor/message_processor.py`
- [ ] `src/modules/monitor/text_filter.py`
- [ ] `src/utils/ui_config_models.py`
- [ ] `src/utils/channel_resolver.py`

#### 测试数据 (有内置备用数据，但推荐存在)
- [ ] `test_data/sample_messages/text_messages.json`
- [ ] `test_data/sample_configs/basic_forward.json`
- [ ] `test_data/sample_configs/keyword_filter.json`

### ⚠️ 可选文件 (增强测试体验)

#### 完整测试数据
- [ ] `test_data/sample_messages/media_messages.json`
- [ ] `test_data/sample_messages/media_groups.json`
- [ ] `test_data/sample_configs/` 下的所有配置文件
- [ ] `test_data/realistic_scenarios.json`

#### 支持工具
- [ ] `pytest.ini`
- [ ] `conftest.py`
- [ ] `README_TEST_GUIDE.md`

## 🔄 数据流说明

1. **测试启动**: `comprehensive_e2e_test.py` 作为主入口
2. **数据加载**: 优先从 `test_data/` 加载，如果不存在则使用内置数据
3. **专项测试**: 调用 `test_media_group_scenarios.py` 进行媒体组测试
4. **Mock创建**: 使用 `TestDataFactory` 创建测试对象
5. **结果输出**: 生成详细的测试报告和统计

## 💡 最小运行要求

如果只想快速验证核心功能，最少需要：
1. 3个核心测试脚本
2. `src/modules/monitor/media_group_handler.py` (核心被测模块)
3. 基础依赖模块 (`ui_config_models.py`, `channel_resolver.py`)

**注意**: 即使缺少测试数据文件，程序也能运行，因为包含了内置的测试数据生成功能。

## 📊 文件大小统计

| 类型 | 文件数 | 总大小 | 说明 |
|------|--------|--------|------|
| 核心测试脚本 | 3 | ~71KB | 必需 |
| 测试数据 | ~12 | ~45KB | 可选(有内置备用) |
| 源代码模块 | ~6 | ~200KB | 必需 |
| 配置文档 | ~3 | ~25KB | 可选 |
| **总计** | **~24** | **~340KB** | **完整系统** |

---

*最后更新: 2025-06-02*  
*版本: v2.0* 