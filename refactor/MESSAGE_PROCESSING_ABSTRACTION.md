# 消息处理抽象层设计

## 概述

基于对转发模块和监听模块的深入分析，发现两个模块在消息处理方面具有大量相似功能。为了减少重复代码、提高维护性和确保功能一致性，设计了统一的消息处理抽象层。

## 问题分析

### 重复代码识别

1. **文本替换功能**
   - 转发模块：`MessageFilter.apply_text_replacements()`
   - 监听模块：`TextFilter.apply_text_replacements()`
   - 功能完全相同，但实现分散

2. **过滤规则系统**
   - 转发模块：`MessageFilter.apply_keyword_filter()`, `apply_media_type_filter()`
   - 监听模块：`TextFilter.check_keywords()`, `apply_universal_filters()`
   - 过滤逻辑几乎完全相同

3. **配置处理**
   - 两个模块都有相同的频道对配置结构
   - 文本替换规则、关键词、媒体类型等配置项相同
   - 配置验证和处理逻辑重复

4. **事件系统**
   - 过滤事件、文本替换事件、处理状态事件等
   - 事件格式和内容相同，但实现分散

## 抽象层设计

### 1. 消息处理抽象基类

```python
class BaseMessageProcessor:
    """消息处理抽象基类，提供通用的消息处理功能"""
    
    def __init__(self, client, channel_resolver, emit=None):
        self.client = client
        self.channel_resolver = channel_resolver
        self.emit = emit
        
        # 初始化通用组件
        self.text_processor = TextProcessor()
        self.message_filter = MessageFilter()
        self.media_group_processor = MediaGroupProcessor()
    
    async def process_message(self, message, pair_config):
        """处理单条消息的通用流程"""
        # 1. 应用通用过滤规则
        should_filter, filter_reason = self.message_filter.apply_universal_filters(message, pair_config)
        if should_filter:
            if self.emit:
                self.emit("message_filtered", message.id, "通用过滤", filter_reason)
            return False
        
        # 2. 应用关键词过滤
        if not self.message_filter.apply_keyword_filter(message, pair_config):
            if self.emit:
                self.emit("message_filtered", message.id, "关键词过滤", "不包含关键词")
            return False
        
        # 3. 应用媒体类型过滤
        if not self.message_filter.apply_media_type_filter(message, pair_config):
            if self.emit:
                self.emit("message_filtered", message.id, "媒体类型过滤", "媒体类型不匹配")
            return False
        
        # 4. 处理文本替换
        processed_text, has_replacement = self.text_processor.process_message_text(message, pair_config)
        if has_replacement and self.emit:
            self.emit("text_replacement_applied", "消息文本", message.text, processed_text)
        
        # 5. 子类实现具体的转发逻辑
        return await self._forward_message(message, pair_config, processed_text)
    
    async def _forward_message(self, message, pair_config, processed_text):
        """子类需要实现的转发逻辑"""
        raise NotImplementedError
```

### 2. 文本处理器

```python
class TextProcessor:
    """统一的文本处理器，处理文本替换和文本相关操作"""
    
    def __init__(self):
        self.logger = get_logger()
    
    def process_message_text(self, message, pair_config):
        """处理消息文本，包括文本替换和标题移除"""
        # 获取原始文本
        text = self._extract_text_from_message(message)
        if not text:
            return None, False
        
        # 应用文本替换
        text_replacements = self._build_text_replacements(pair_config)
        processed_text, has_replacement = self.apply_text_replacements(text, text_replacements)
        
        # 处理标题移除
        should_remove_caption = pair_config.get('remove_captions', False)
        if should_remove_caption and self._is_media_message(message):
            processed_text = None
            has_replacement = True
        
        return processed_text, has_replacement
    
    def apply_text_replacements(self, text, text_replacements):
        """应用文本替换规则"""
        if not text or not text_replacements:
            return text, False
        
        result_text = text
        has_replacement = False
        
        for find_text, replace_text in text_replacements.items():
            if find_text and find_text in result_text:
                result_text = result_text.replace(find_text, replace_text)
                has_replacement = True
                self.logger.debug(f"文本替换: '{find_text}' -> '{replace_text}'")
        
        return result_text, has_replacement
    
    def _extract_text_from_message(self, message):
        """从消息中提取文本内容"""
        return message.text or message.caption or ""
    
    def _build_text_replacements(self, pair_config):
        """构建文本替换规则字典"""
        text_replacements = {}
        text_filter_list = pair_config.get('text_filter', [])
        
        for rule in text_filter_list:
            if isinstance(rule, dict):
                original_text = rule.get('original_text', '')
                target_text = rule.get('target_text', '')
                if original_text:  # 只添加非空的原文
                    text_replacements[original_text] = target_text
        
        return text_replacements
    
    def _is_media_message(self, message):
        """检查是否为媒体消息"""
        return bool(message.media)
```

### 3. 统一消息过滤器

```python
class MessageFilter:
    """统一的消息过滤器，提供所有过滤功能"""
    
    def __init__(self):
        self.logger = get_logger()
    
    def apply_universal_filters(self, message, pair_config):
        """应用通用过滤规则（最高优先级）"""
        # 排除转发消息
        if pair_config.get('exclude_forwards', False) and (message.forward_from or message.forward_from_chat):
            return True, "转发消息"
        
        # 排除回复消息
        if pair_config.get('exclude_replies', False) and message.reply_to_message:
            return True, "回复消息"
        
        # 排除纯文本消息
        if pair_config.get('exclude_text', False) and not message.media:
            return True, "纯文本消息"
        
        # 排除包含链接的消息
        if pair_config.get('exclude_links', False) and self._contains_links(message):
            return True, "包含链接"
        
        return False, ""
    
    def apply_keyword_filter(self, message, pair_config):
        """应用关键词过滤"""
        keywords = pair_config.get('keywords', [])
        if not keywords:
            return True
        
        text = message.text or message.caption or ""
        if not text:
            return False
        
        # 检查是否包含关键词
        for keyword in keywords:
            if keyword.lower() in text.lower():
                self.logger.info(f"消息 [ID: {message.id}] 匹配关键词: {keyword}")
                return True
        
        return False
    
    def apply_media_type_filter(self, message, pair_config):
        """应用媒体类型过滤"""
        allowed_media_types = pair_config.get('media_types', [])
        if not allowed_media_types:
            return True
        
        message_media_type = self._get_message_media_type(message)
        if not message_media_type:
            return True  # 纯文本消息，如果没有明确排除则通过
        
        return message_media_type in allowed_media_types
    
    def _contains_links(self, message):
        """检查消息是否包含链接"""
        text = message.text or message.caption or ""
        if not text:
            return False
        
        # 检查文本中的链接模式
        link_patterns = [
            r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
            r'www\.(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
            r't\.me/[a-zA-Z0-9_]+',
            r'telegram\.me/[a-zA-Z0-9_]+'
        ]
        
        for pattern in link_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        # 检查消息实体中的链接
        entities = getattr(message, 'entities', []) or []
        for entity in entities:
            if entity.type in ['url', 'text_link']:
                return True
        
        return False
    
    def _get_message_media_type(self, message):
        """获取消息的媒体类型"""
        if not message.media:
            return None
        
        media_type_map = {
            'photo': 'photo',
            'video': 'video',
            'document': 'document',
            'audio': 'audio',
            'animation': 'animation',
            'sticker': 'sticker',
            'voice': 'voice',
            'video_note': 'video_note'
        }
        
        return media_type_map.get(message.media.value, None)
```

### 4. 媒体组处理器

```python
class MediaGroupProcessor:
    """统一的媒体组处理器，处理媒体组相关操作"""
    
    def __init__(self):
        self.logger = get_logger()
        self.media_group_cache = {}
    
    def process_media_group_message(self, message, pair_config):
        """处理媒体组消息"""
        media_group_id = message.media_group_id
        
        if media_group_id:
            # 添加到媒体组缓存
            if media_group_id not in self.media_group_cache:
                self.media_group_cache[media_group_id] = {
                    'messages': [],
                    'timestamp': time.time(),
                    'config': pair_config
                }
            
            self.media_group_cache[media_group_id]['messages'].append(message)
            
            # 检查媒体组是否完整
            if self._is_media_group_complete(media_group_id):
                return self._get_complete_media_group(media_group_id)
        
        return None  # 单条消息或媒体组不完整
    
    def _is_media_group_complete(self, media_group_id):
        """检查媒体组是否完整"""
        # 实现媒体组完整性检查逻辑
        # 这里可以根据实际需求实现更复杂的检查
        return True
    
    def _get_complete_media_group(self, media_group_id):
        """获取完整的媒体组"""
        group_data = self.media_group_cache.get(media_group_id)
        if not group_data:
            return None
        
        messages = group_data['messages']
        config = group_data['config']
        
        # 清理缓存
        del self.media_group_cache[media_group_id]
        
        return messages, config
```

## 插件化重构

### 1. 转发插件重构

```python
class SmartForwardPlugin(BaseForwardPlugin):
    """智能转发插件，使用消息处理抽象层"""
    
    def __init__(self, client, config):
        super().__init__(client, config)
        
        # 使用抽象层的消息处理器
        self.message_processor = BaseMessageProcessor(client, self.channel_resolver, self.emit)
        
        # 重写消息处理器以适配转发逻辑
        self.message_processor._forward_message = self._forward_message_implementation
    
    async def _forward_message_implementation(self, message, pair_config, processed_text):
        """实现转发逻辑"""
        # 获取目标频道
        target_channels = await self._get_target_channels(pair_config)
        
        # 检查源频道转发权限
        source_can_forward = await self.channel_resolver.check_forward_permission(message.chat.id)
        
        if source_can_forward:
            # 直接转发
            await self._forward_directly(message, target_channels, pair_config, processed_text)
        else:
            # 使用禁止转发处理器
            await self.restricted_handler.handle_restricted_forward(message, target_channels, pair_config, processed_text)
        
        return True
```

### 2. 监听插件重构

```python
class SmartMonitorPlugin(BaseMonitorPlugin):
    """智能监听插件，使用消息处理抽象层"""
    
    def __init__(self, client, config):
        super().__init__(self, client, config)
        
        # 使用抽象层的消息处理器
        self.message_processor = BaseMessageProcessor(client, self.channel_resolver, self.emit)
        
        # 重写消息处理器以适配监听逻辑
        self.message_processor._forward_message = self._forward_message_implementation
    
    async def _forward_message_implementation(self, message, pair_config, processed_text):
        """实现监听转发逻辑"""
        # 获取目标频道
        target_channels = await self._get_target_channels(pair_config)
        
        # 检查源频道转发权限
        source_can_forward = await self.channel_resolver.check_forward_permission(message.chat.id)
        
        if source_can_forward:
            # 直接转发
            await self._forward_directly(message, target_channels, pair_config, processed_text)
        else:
            # 使用禁止转发处理器
            await self.restricted_handler.handle_restricted_forward(message, target_channels, pair_config, processed_text)
        
        return True
```

## 配置系统统一

### 统一配置模型

```python
class UnifiedChannelPairConfig:
    """统一的频道对配置模型"""
    
    def __init__(self, config_dict):
        self.source_channel = config_dict.get('source_channel', '')
        self.target_channels = config_dict.get('target_channels', [])
        self.media_types = config_dict.get('media_types', [])
        self.keywords = config_dict.get('keywords', [])
        self.text_filter = config_dict.get('text_filter', [])
        self.exclude_forwards = config_dict.get('exclude_forwards', False)
        self.exclude_replies = config_dict.get('exclude_replies', False)
        self.exclude_text = config_dict.get('exclude_text', False)
        self.exclude_links = config_dict.get('exclude_links', False)
        self.remove_captions = config_dict.get('remove_captions', False)
        self.enabled = config_dict.get('enabled', True)
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            'source_channel': self.source_channel,
            'target_channels': self.target_channels,
            'media_types': self.media_types,
            'keywords': self.keywords,
            'text_filter': self.text_filter,
            'exclude_forwards': self.exclude_forwards,
            'exclude_replies': self.exclude_replies,
            'exclude_text': self.exclude_text,
            'exclude_links': self.exclude_links,
            'remove_captions': self.remove_captions,
            'enabled': self.enabled
        }
```

## 事件系统统一

### 统一事件发射器

```python
class UnifiedEventEmitter:
    """统一的事件发射器，提供标准的事件接口"""
    
    def __init__(self, emit_function=None):
        self.emit = emit_function
    
    def emit_message_filtered(self, message_id, filter_type, filter_reason):
        """发射消息过滤事件"""
        if self.emit:
            self.emit("message_filtered", message_id, filter_type, filter_reason)
    
    def emit_text_replacement_applied(self, message_desc, original_text, replaced_text):
        """发射文本替换事件"""
        if self.emit:
            self.emit("text_replacement_applied", message_desc, original_text, replaced_text)
    
    def emit_message_processed(self, message_id):
        """发射消息处理完成事件"""
        if self.emit:
            self.emit("message_processed", message_id)
    
    def emit_forward_completed(self, message_id, target_info, success):
        """发射转发完成事件"""
        if self.emit:
            self.emit("forward_completed", message_id, target_info, success)
```

## 重构收益

### 1. 代码重复减少

- **文本替换逻辑**：从2个独立实现减少到1个统一实现
- **过滤规则逻辑**：从2个独立实现减少到1个统一实现
- **配置处理逻辑**：从2个独立实现减少到1个统一实现
- **事件处理逻辑**：从2个独立实现减少到1个统一实现

### 2. 维护性提升

- **单一职责**：每个抽象类只负责一个特定功能
- **易于测试**：抽象层可以独立测试，提高测试覆盖率
- **易于扩展**：新功能可以通过继承抽象类实现
- **配置统一**：统一的配置模型减少配置错误

### 3. 功能一致性

- **过滤行为一致**：转发和监听的过滤行为完全一致
- **文本替换一致**：文本替换逻辑和行为完全一致
- **事件格式一致**：事件格式和内容完全一致
- **错误处理一致**：错误处理和日志记录完全一致

### 4. 性能优化

- **缓存复用**：媒体组缓存等可以跨模块复用
- **内存优化**：减少重复对象创建
- **处理效率**：统一的处理流程提高效率

## 实施计划

### 第一阶段：抽象层开发

1. **创建抽象层基础类**
   - BaseMessageProcessor
   - TextProcessor
   - MessageFilter
   - MediaGroupProcessor

2. **实现统一配置模型**
   - UnifiedChannelPairConfig
   - 配置验证和转换

3. **实现统一事件系统**
   - UnifiedEventEmitter
   - 标准事件接口

### 第二阶段：插件重构

1. **转发插件重构**
   - 继承BaseMessageProcessor
   - 实现转发特定逻辑

2. **监听插件重构**
   - 继承BaseMessageProcessor
   - 实现监听特定逻辑

### 第三阶段：测试验证

1. **功能测试**
   - 验证过滤功能一致性
   - 验证文本替换一致性
   - 验证事件系统一致性

2. **性能测试**
   - 对比重构前后性能
   - 验证内存使用优化

3. **集成测试**
   - 测试插件间协作
   - 测试配置系统统一性

## 总结

通过消息处理抽象层的设计，成功解决了转发模块和监听模块之间的重复代码问题，提高了代码的可维护性和一致性。抽象层提供了统一的接口和实现，使得两个模块可以共享相同的核心功能，同时保持各自的特定逻辑。

这种设计符合SOLID原则中的单一职责原则和开闭原则，为未来的功能扩展提供了良好的基础。 