# 监听模块测试指南

## 📋 测试概述

本测试套件为监听模块提供了全面的测试覆盖，包括：

- **功能测试**：验证所有功能的正确性
- **性能测试**：验证性能指标和内存使用
- **集成测试**：验证模块间的协作
- **边界测试**：验证异常情况和边界条件

## 🗂️ 测试文件结构

```
tests/modules/monitor/
├── conftest.py                     # 测试配置和夹具
├── test_monitor_comprehensive.py   # 综合功能测试
├── test_performance.py            # 性能和负载测试
├── pytest.ini                     # pytest配置
├── README_TEST_GUIDE.md           # 本测试指南
└── test_data/                     # 测试数据目录
    ├── sample_messages/           # 示例消息数据
    ├── sample_configs/            # 示例配置文件
    ├── media_files/              # 测试媒体文件
    └── expected_outputs/          # 预期输出结果
```

## 🧪 测试数据组织

### 1. 示例消息数据 (`test_data/sample_messages/`)

创建各种类型的测试消息JSON文件：

#### 📝 文本消息示例 (`text_messages.json`)
```json
{
  "simple_text": {
    "text": "这是一条简单的文本消息",
    "message_id": 1001,
    "chat_id": -1001234567890
  },
  "text_with_keywords": {
    "text": "这是包含重要关键词的测试消息",
    "message_id": 1002,
    "chat_id": -1001234567890
  },
  "text_with_links": {
    "text": "查看这个链接 https://example.com",
    "message_id": 1003,
    "chat_id": -1001234567890,
    "entities": [{"type": "url", "offset": 5, "length": 20}]
  },
  "multiline_text": {
    "text": "第一行内容\n第二行内容\n第三行内容",
    "message_id": 1004,
    "chat_id": -1001234567890
  }
}
```

#### 🖼️ 媒体消息示例 (`media_messages.json`)
```json
{
  "photo_with_caption": {
    "message_id": 2001,
    "chat_id": -1001234567890,
    "photo": {
      "file_id": "BAADBAADPhoto-TestFileID",
      "width": 1280,
      "height": 720
    },
    "caption": "这是一张测试图片"
  },
  "video_message": {
    "message_id": 2002,
    "chat_id": -1001234567890,
    "video": {
      "file_id": "BAADBAADVideo-TestFileID",
      "width": 1920,
      "height": 1080,
      "duration": 120
    },
    "caption": "测试视频"
  }
}
```

#### 📦 媒体组示例 (`media_groups.json`)
```json
{
  "photo_album": {
    "media_group_id": "12345678901234567890",
    "messages": [
      {
        "message_id": 3001,
        "media_group_count": 3,
        "photo": {"file_id": "Photo1-FileID"},
        "caption": "相册第一张"
      },
      {
        "message_id": 3002,
        "media_group_count": 3,
        "photo": {"file_id": "Photo2-FileID"}
      },
      {
        "message_id": 3003,
        "media_group_count": 3,
        "video": {"file_id": "Video1-FileID"}
      }
    ]
  }
}
```

### 2. 配置文件示例 (`test_data/sample_configs/`)

#### 基础转发配置 (`basic_forward.json`)
```json
{
  "source_channel": "test_source",
  "target_channels": ["test_target1", "test_target2"],
  "keywords": [],
  "exclude_forwards": false,
  "exclude_replies": false,
  "exclude_text": false,
  "exclude_links": false,
  "remove_captions": false,
  "media_types": ["photo", "video", "document"],
  "text_filter": []
}
```

#### 高级过滤配置 (`advanced_filter.json`)
```json
{
  "source_channel": "news_channel",
  "target_channels": ["filtered_news"],
  "keywords": ["重要", "紧急", "通知"],
  "exclude_forwards": true,
  "exclude_replies": true,
  "exclude_text": false,
  "exclude_links": true,
  "remove_captions": false,
  "media_types": ["photo", "video"],
  "text_filter": [
    {"original_text": "测试版", "target_text": "正式版"},
    {"original_text": "beta", "target_text": "release"}
  ]
}
```

### 3. 测试媒体文件 (`test_data/media_files/`)

创建小的测试媒体文件：

```bash
# 创建测试图片（1KB PNG）
touch test_photo.png

# 创建测试视频（小MP4文件）
touch test_video.mp4

# 创建测试文档
echo "测试文档内容" > test_document.txt

# 创建测试音频
touch test_audio.mp3
```

### 4. 预期输出 (`test_data/expected_outputs/`)

存储各种测试场景的预期结果：

#### 文本替换结果 (`text_replacements.json`)
```json
{
  "simple_replacement": {
    "input": "这是旧版本的消息",
    "rules": {"旧版本": "新版本"},
    "expected": "这是新版本的消息"
  },
  "multiple_replacements": {
    "input": "测试版beta功能",
    "rules": {"测试版": "正式版", "beta": "release"},
    "expected": "正式版release功能"
  }
}
```

## 🚀 运行测试

### 1. 安装依赖

```bash
# 安装基础测试依赖
pip install pytest pytest-asyncio pytest-cov pytest-xdist

# 安装性能测试依赖
pip install psutil memory-profiler

# 安装Mock相关
pip install pytest-mock
```

### 2. 基础测试命令

```bash
# 运行所有测试
pytest tests/modules/monitor/

# 运行特定测试文件
pytest tests/modules/monitor/test_monitor_comprehensive.py

# 运行特定测试类
pytest tests/modules/monitor/test_monitor_comprehensive.py::TestTextFilter

# 运行特定测试方法
pytest tests/modules/monitor/test_monitor_comprehensive.py::TestTextFilter::test_text_replacement
```

### 3. 按标记运行测试

```bash
# 只运行单元测试
pytest -m unit

# 只运行性能测试
pytest -m performance

# 只运行集成测试
pytest -m integration

# 排除慢速测试
pytest -m "not slow"

# 运行冒烟测试
pytest -m smoke
```

### 4. 高级测试选项

```bash
# 并行运行测试（需要pytest-xdist）
pytest -n auto

# 生成覆盖率报告
pytest --cov=src/modules/monitor --cov-report=html

# 详细输出
pytest -v -s

# 只运行失败的测试
pytest --lf

# 调试模式
pytest --pdb

# 性能分析
pytest --durations=10
```

## 📊 测试场景组合

### 1. 消息类型 × 过滤规则

测试所有消息类型与所有过滤规则的组合：

```python
MESSAGE_TYPES = ['text', 'photo', 'video', 'document', 'audio', 'sticker', 'voice']
FILTER_RULES = [
    'keywords', 'exclude_forwards', 'exclude_replies', 
    'exclude_text', 'exclude_links', 'media_types'
]
```

### 2. 转发策略 × 错误情况

测试所有转发策略在各种错误情况下的表现：

```python
FORWARD_STRATEGIES = ['copy_message', 'forward_messages', 'send_media_group']
ERROR_SCENARIOS = ['FloodWait', 'ChatForwardsRestricted', 'NetworkError']
```

### 3. 媒体组大小 × 处理策略

测试不同大小的媒体组在各种处理策略下的性能：

```python
MEDIA_GROUP_SIZES = [1, 3, 5, 10, 20]
PROCESSING_STRATEGIES = ['immediate', 'delayed', 'api_fetch']
```

## 🎯 测试覆盖目标

### 功能覆盖率目标
- **核心功能**: 100%
- **边界情况**: 95%
- **错误处理**: 90%
- **性能路径**: 85%

### 代码覆盖率目标
- **行覆盖率**: ≥90%
- **分支覆盖率**: ≥85%
- **函数覆盖率**: ≥95%

### 性能基准
- **单条消息处理**: <100ms
- **媒体组处理**: <500ms
- **内存使用增长**: <100MB
- **并发处理**: ≥10 msg/s

## 🔧 自定义测试数据

### 创建真实场景数据

```python
# 在conftest.py中添加真实数据生成器
@pytest.fixture
def real_world_messages():
    return [
        {
            'type': 'news_update',
            'text': '🔥 重要新闻：科技公司发布新产品',
            'has_media': True,
            'forwarded': False
        },
        {
            'type': 'media_share',
            'caption': '精美图片分享 📸',
            'media_group_size': 4,
            'has_links': False
        }
    ]
```

### 模拟网络条件

```python
@pytest.fixture
def network_conditions():
    return {
        'normal': {'delay': 0, 'error_rate': 0},
        'slow': {'delay': 1.0, 'error_rate': 0.1},
        'unstable': {'delay': 0.5, 'error_rate': 0.2}
    }
```

## 📈 测试结果分析

### 生成测试报告

```bash
# HTML覆盖率报告
pytest --cov=src/modules/monitor --cov-report=html
open htmlcov/index.html

# JSON格式报告
pytest --json-report --json-report-file=test_report.json

# JUnit XML报告（CI/CD集成）
pytest --junitxml=test_results.xml
```

### 性能基准比较

```bash
# 运行性能测试并保存结果
pytest -m performance --benchmark-json=benchmark.json

# 与之前的基准比较
pytest-benchmark compare benchmark.json
```

## 🚨 调试失败测试

### 1. 详细日志输出

```bash
# 启用详细日志
pytest -v -s --log-cli-level=DEBUG

# 捕获输出
pytest --capture=no
```

### 2. 交互式调试

```bash
# 在失败时进入调试器
pytest --pdb

# 在异常时进入调试器
pytest --pdbcls=IPython.terminal.debugger:Pdb
```

### 3. 重现问题

```python
# 添加重现步骤到测试中
def test_reproduce_issue():
    # 步骤1: 设置特定条件
    # 步骤2: 触发问题
    # 步骤3: 验证预期行为
    pass
```

## 📝 贡献测试

### 添加新测试

1. **识别测试需求**：确定需要测试的新功能或场景
2. **创建测试数据**：准备必要的测试输入和预期输出
3. **编写测试用例**：遵循现有的测试模式和命名约定
4. **验证测试质量**：确保测试稳定、可重复且有意义
5. **更新文档**：更新本指南以反映新的测试内容

### 测试最佳实践

- **独立性**：每个测试应该独立运行，不依赖其他测试
- **确定性**：测试结果应该可重复，避免随机性
- **清晰性**：测试名称和结构应该清楚地表达测试意图
- **效率性**：避免不必要的复杂性和重复代码
- **覆盖性**：关注边界条件和异常情况

通过遵循这个测试指南，你可以有效地测试监听模块的所有功能，确保其稳定性和性能。 