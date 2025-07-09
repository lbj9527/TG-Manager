# Monitor 模块

## 介绍

Monitor 模块负责监听源频道的新消息，并实时转发到目标频道。该模块已经进行了重构，采用了更加模块化的设计，将不同功能拆分到各个子模块中，以提高代码的可维护性和可扩展性。

## 模块结构

重构后的 Monitor 模块包含以下文件：

- **\_\_init\_\_.py**: 模块入口，导出 Monitor 类
- **core.py**: 核心监控类，提供外部接口并协调各个功能模块
- **text_filter.py**: 文本过滤器，处理关键词过滤和文本替换
- **message_processor.py**: 消息处理器，负责处理和转发单条消息
- **media_group_handler.py**: 媒体组处理器，负责处理和转发媒体组消息

## 功能说明

### core.py (Monitor 类)

Monitor 类是监听模块的主要入口点，负责初始化各个子模块并协调它们的工作。主要功能包括：

- 启动和停止监听
- 解析源频道和目标频道配置
- 注册消息处理函数
- 管理已处理消息的集合
- 协调各个子模块的工作

### text_filter.py (TextFilter 类)

TextFilter 类负责处理消息的文本过滤和替换，主要功能包括：

- 加载和管理文本替换规则
- 检查消息是否包含关键词
- 应用文本替换规则

### message_processor.py (MessageProcessor 类)

MessageProcessor 类负责处理和转发单条消息，主要功能包括：

- 转发消息到目标频道
- 处理转发限制情况
- 发送修改后的消息

### media_group_handler.py (MediaGroupHandler 类)

MediaGroupHandler 类负责处理和转发媒体组消息，主要功能包括：

- 缓存和管理媒体组消息
- 判断媒体组是否完整
- 转发媒体组消息
- 处理媒体组转发限制情况
- 发送修改后的媒体组消息

## 使用方法

Monitor 模块的使用方法与重构前保持一致，示例如下：

```python
from src.modules.monitor import Monitor

# 初始化监听模块
monitor = Monitor(client, ui_config_manager, channel_resolver, history_manager)

# 开始监听
await monitor.start_monitoring()

# 停止监听
await monitor.stop_monitoring()
```

通过这种模块化设计，监听模块的代码更加清晰，各个功能之间的边界更加明确，便于后续维护和扩展。
