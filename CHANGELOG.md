# 更新日志

## [1.2.7] - 2025-07-13

### 🐛 修复问题

#### 监听模块客户端引用更新问题
- **修复监听模块客户端引用更新**: 解决在非首次登录流程中，当登录失败并删除损坏的会话文件后，切换到首次登录模式并手动登录成功时，监听模块无法接收消息的问题
- **完善客户端管理器启动逻辑**: 在`ClientManager.start_client`方法中添加对`_update_all_users_client()`的调用，确保客户端启动后所有注册的使用者都能获得新的客户端引用
- **优化监听模块客户端更新逻辑**: 确保在客户端重新创建时能正确更新所有内部组件的引用
- **改进监听模块消息处理器清理逻辑**: 避免在客户端已销毁时尝试移除处理器导致的错误

#### 客户端引用更新机制完善
- **及时更新机制**: 客户端启动后立即更新所有注册使用者的客户端引用
- **安全清理机制**: 改进消息处理器清理逻辑，增加客户端有效性检查
- **简化重启条件**: 优化监听模块重新启动条件判断，确保在监听模块真正启动时才触发重新启动逻辑

### 🔧 技术改进

#### 客户端管理器优化
- **启动后更新**: 在`start_client`方法中添加对`_update_all_users_client()`的调用
- **创建后更新**: 在`create_client`方法中已存在的`_update_all_users_client()`调用得到确认
- **停止时更新**: 在`stop_client`方法中已存在的`_update_all_users_client()`调用得到确认

#### 监听模块架构优化
- **客户端更新逻辑**: 优化`Monitor.update_client`方法，移除可能导致问题的消息处理器重新注册逻辑
- **处理器清理优化**: 改进`_cleanup_old_handlers`方法，增加客户端有效性检查
- **重启条件简化**: 简化重新启动条件，只检查`is_processing`和`monitored_channels`两个关键标志

#### 错误处理机制改进
- **客户端有效性检查**: 在移除消息处理器前检查客户端是否存在且有效
- **异常捕获增强**: 改进客户端引用更新过程中的异常捕获和处理
- **状态恢复机制**: 确保在异常情况下监听模块能正常恢复

### 📚 文档更新

#### 代码文档
- **客户端引用更新**: 完善客户端引用更新机制的文档说明
- **监听模块更新**: 更新监听模块客户端更新逻辑的文档
- **错误处理**: 更新监听模块更新过程中的错误处理文档

#### 用户文档
- **故障排除**: 更新监听模块故障排除指南
- **常见问题**: 添加监听模块无法监听到消息的解决方案

### 🔍 问题追踪
- **根本原因**: 客户端管理器在启动客户端后未及时更新所有注册使用者的客户端引用
- **解决方案**: 在客户端启动后立即调用`_update_all_users_client()`更新所有使用者引用
- **测试验证**: 确保修复不影响正常的首次登录流程和其他功能

## [1.2.6] - 2024-12-20

### 🐛 修复问题

#### 监听模块自动重新启动逻辑问题
- **修复监听模块自动重新启动逻辑**: 解决客户端引用更新时错误触发重新启动导致发送验证码失败的问题
- **完善重新启动条件检查**: 在`Monitor.update_client`方法中添加更严格的重新启动条件检查
- **修复客户端功能影响**: 确保监听模块的自动重新启动逻辑不会影响客户端的正常功能
- **解决发送验证码失败问题**: 修复非首次登录流程中，客户端引用更新时错误触发重新启动导致的问题

#### 重新启动条件检查完善
- **严格条件检查**: 只有在监听模块真正启动时才触发重新启动
  - 检查 `is_processing` 状态
  - 检查 `current_message_handler` 是否存在
  - 检查 `monitored_channels` 是否已设置
- **避免误触发**: 防止在监听模块未完全初始化时触发重新启动
- **日志记录完善**: 为重新启动条件检查提供详细的日志记录

### 🔧 技术改进

#### 监听模块架构优化
- **智能重新启动机制**: 改进监听模块自动重新启动的条件检查
  - 多重条件验证
  - 避免误触发
  - 详细日志记录
- **客户端功能保护**: 确保监听模块的更新逻辑不会影响客户端正常功能
- **错误处理增强**: 改进重新启动过程中的错误处理和日志记录

#### 错误处理机制改进
- **条件检查失败处理**: 如果条件检查失败，记录调试日志但不影响客户端功能
- **异常捕获增强**: 改进监听模块更新过程中的异常捕获和处理
- **状态恢复机制**: 确保在异常情况下客户端功能能正常工作

### 📚 文档更新

#### 代码文档
- **重新启动条件检查**: 完善监听模块重新启动条件检查的文档说明
- **客户端功能保护**: 更新客户端功能保护机制的文档
- **错误处理**: 更新监听模块更新过程中的错误处理文档

#### 用户文档
- **故障排除**: 更新监听模块故障排除指南
- **常见问题**: 添加发送验证码失败问题的解决方案

### 🔍 问题追踪
- **根本原因**: 监听模块自动重新启动逻辑的条件检查不够严格，导致误触发
- **解决方案**: 添加更严格的条件检查，确保只在监听模块真正启动时才重新启动
- **测试验证**: 确保修复不影响客户端正常功能

## [1.2.5] - 2024-12-20

### 🐛 修复问题

#### 监听模块自动重新启动问题
- **修复监听模块自动重新启动**: 解决客户端引用更新后监听模块无法监听到消息的根本问题
- **完善客户端引用更新机制**: 在`Monitor.update_client`方法中添加监听模块自动重新启动逻辑
- **修复消息处理器绑定问题**: 确保监听模块在客户端重新创建后能自动重新启动并正确绑定消息处理器
- **解决监听模块无法监听到消息的最终问题**: 修复非首次登录流程中，登录失败后重新登录时监听模块无法监听到消息的最终问题

#### 监听模块重启机制完善
- **自动重新启动**: 客户端引用更新时，如果监听模块已经启动，自动重新启动以确保消息处理器正确绑定
- **异步重启处理**: 使用异步任务进行监听模块重启，避免阻塞客户端引用更新过程
- **状态一致性保证**: 确保监听模块在客户端重新创建后能正常工作

### 🔧 技术改进

#### 监听模块架构优化
- **自动重新启动机制**: 在客户端引用更新时自动重新启动监听模块
  - 检测监听模块是否已启动
  - 异步停止当前监听
  - 异步重新启动监听
  - 错误处理和日志记录
- **客户端引用更新完善**: 增强客户端引用更新机制，确保所有组件正确更新
- **日志记录完善**: 为监听模块重新启动过程提供详细的日志记录

#### 错误处理机制改进
- **重启失败处理**: 如果重新启动失败，不影响客户端引用更新过程
- **异常捕获增强**: 改进监听模块重新启动过程中的异常捕获和处理
- **状态恢复机制**: 确保在异常情况下监听模块能正常恢复

### 📚 文档更新

#### 代码文档
- **监听模块重新启动**: 完善监听模块重新启动机制的文档说明
- **客户端引用更新**: 更新客户端引用更新机制的文档
- **错误处理**: 更新监听模块重新启动过程中的错误处理文档

#### 用户文档
- **故障排除**: 更新监听模块故障排除指南
- **常见问题**: 添加监听模块无法监听到消息的解决方案

### 🔍 问题追踪
- **根本原因**: 客户端重新创建后，监听模块的消息处理器仍然绑定在旧的客户端实例上
- **解决方案**: 在客户端引用更新时自动重新启动监听模块
- **测试验证**: 确保修复不影响原有业务逻辑功能

## [1.2.4] - 2024-12-20

### 🐛 修复问题

#### 监听模块消息处理器重新注册问题
- **修复监听模块消息处理器重新注册**: 解决客户端引用更新后消息处理器无法监听到消息的问题
- **完善客户端引用更新机制**: 在`Monitor.update_client`方法中添加消息处理器重新注册逻辑
- **修复消息处理器绑定问题**: 确保消息处理器在客户端重新创建后能正确绑定到新的客户端实例
- **解决监听模块无法监听到消息的根本原因**: 修复非首次登录流程中，登录失败后重新登录时监听模块无法监听到消息的最终问题

#### 消息处理器注册机制完善
- **自动重新注册**: 客户端引用更新时自动重新注册消息处理器到新的客户端实例
- **错误处理增强**: 改进消息处理器重新注册过程中的错误处理和日志记录
- **状态一致性保证**: 确保监听模块在客户端重新创建后能正常工作

### 🔧 技术改进

#### 监听模块架构优化
- **消息处理器重新注册**: 在客户端引用更新时自动重新注册消息处理器
  - 从旧客户端移除处理器
  - 重新注册到新客户端
  - 错误处理和回退机制
- **客户端引用更新完善**: 增强客户端引用更新机制，确保所有组件正确更新
- **日志记录完善**: 为消息处理器重新注册过程提供详细的日志记录

#### 错误处理机制改进
- **重新注册失败处理**: 如果重新注册失败，清空当前处理器引用，下次启动时重新创建
- **异常捕获增强**: 改进客户端引用更新过程中的异常捕获和处理
- **状态恢复机制**: 确保在异常情况下监听模块能正常恢复

### 📚 文档更新

#### 代码文档
- **消息处理器重新注册**: 完善消息处理器重新注册机制的文档说明
- **客户端引用更新**: 更新客户端引用更新机制的文档
- **错误处理**: 更新消息处理器重新注册过程中的错误处理文档

## [1.2.3] - 2024-12-20

### 🐛 修复问题

#### 监听模块消息处理器重新注册问题
- **修复监听模块消息处理器重新注册**: 解决客户端引用更新后消息处理器无法监听到消息的问题
- **完善客户端引用更新机制**: 在`Monitor.update_client`方法中添加消息处理器重新注册逻辑
- **修复消息处理器绑定问题**: 确保消息处理器在客户端重新创建后能正确绑定到新的客户端实例
- **解决监听模块无法监听到消息的根本原因**: 修复非首次登录流程中，登录失败后重新登录时监听模块无法监听到消息的最终问题

#### 消息处理器注册机制完善
- **自动重新注册**: 客户端引用更新时自动重新注册消息处理器到新的客户端实例
- **错误处理增强**: 改进消息处理器重新注册过程中的错误处理和日志记录
- **状态一致性保证**: 确保监听模块在客户端重新创建后能正常工作

### 🔧 技术改进

#### 监听模块架构优化
- **消息处理器重新注册**: 在客户端引用更新时自动重新注册消息处理器
  - 从旧客户端移除处理器
  - 重新注册到新客户端
  - 错误处理和回退机制
- **客户端引用更新完善**: 增强客户端引用更新机制，确保所有组件正确更新
- **日志记录完善**: 为消息处理器重新注册过程提供详细的日志记录

#### 错误处理机制改进
- **重新注册失败处理**: 如果重新注册失败，清空当前处理器引用，下次启动时重新创建
- **异常捕获增强**: 改进客户端引用更新过程中的异常捕获和处理
- **状态恢复机制**: 确保在异常情况下监听模块能正常恢复

### 📚 文档更新

#### 代码文档
- **消息处理器重新注册**: 完善消息处理器重新注册机制的文档说明
- **客户端引用更新**: 更新客户端引用更新机制的文档
- **错误处理**: 更新消息处理器重新注册过程中的错误处理文档

## [1.2.2] - 2024-12-20

### 🐛 修复问题

#### 监听模块客户端使用者注册问题
- **修复监听模块客户端使用者注册**: 解决监听模块在首次登录流程中未正确注册为客户端使用者的问题
- **完善所有模块的客户端使用者注册**: 确保下载、上传、转发、监听等所有核心模块都正确注册为客户端使用者
- **修复客户端引用更新机制**: 确保所有模块在客户端重新连接时都能正确接收客户端引用更新
- **解决监听模块无法监听到消息的问题**: 修复非首次登录流程中，登录失败后重新登录时监听模块无法监听到消息的根本原因

#### 客户端使用者注册机制完善
- **统一注册机制**: 在`AsyncServicesInitializer`和`ClientHandler`中统一所有模块的客户端使用者注册
- **双重保障**: 确保在正常启动和首次登录两种流程中都能正确注册
- **错误处理增强**: 改进客户端使用者注册过程中的错误处理和日志记录

### 🔧 技术改进

#### 模块初始化流程优化
- **客户端使用者注册**: 为所有核心模块添加客户端使用者注册逻辑
  - `Downloader` - 下载模块
  - `DownloaderSerial` - 串行下载模块  
  - `Uploader` - 上传模块
  - `Forwarder` - 转发模块
  - `Monitor` - 监听模块
- **注册时机优化**: 在模块创建后立即注册为客户端使用者
- **日志记录完善**: 为客户端使用者注册过程提供详细的日志记录

#### 客户端引用更新机制改进
- **全模块覆盖**: 确保所有使用客户端的模块都能接收引用更新
- **状态一致性保证**: 保证所有模块在客户端重新创建后能正常工作
- **错误容错机制**: 单个模块注册失败不影响其他模块的注册

### 📚 文档更新

#### 代码文档
- **客户端使用者注册**: 完善客户端使用者注册机制的文档说明
- **模块初始化流程**: 更新模块初始化流程的文档
- **错误处理**: 更新客户端使用者注册过程中的错误处理文档

## [1.2.1] - 2024-12-20

### 🐛 修复问题

#### 监听模块客户端引用问题
- **修复监听模块客户端引用更新**: 解决非首次登录流程中，登录失败后重新登录时监听模块无法监听到消息的问题
- **完善客户端引用更新机制**: 增强`ClientManager`的`_update_user_client`方法，支持监听模块内部组件的客户端引用更新
- **添加监听模块专用更新方法**: 为`Monitor`类添加`update_client`方法，提供精确的客户端引用更新控制
- **修复消息处理器注册问题**: 确保监听模块的消息处理器正确绑定到新的客户端实例上

#### 客户端引用更新机制改进
- **递归更新内部组件**: 支持更新监听模块内部所有组件的客户端引用
  - `message_processor.client`
  - `media_group_handler.client`
  - `restricted_handler.client`
  - `channel_resolver.client`
- **专用更新方法支持**: 支持调用模块的专用客户端更新方法（如果存在）
- **错误处理增强**: 改进客户端引用更新过程中的错误处理和日志记录

### 🔧 技术改进

#### 客户端管理器优化
- **智能组件检测**: 自动检测和更新不同类型组件的客户端引用
- **错误容错机制**: 单个组件更新失败不影响其他组件的更新
- **详细日志记录**: 为客户端引用更新过程提供详细的日志记录

#### 监听模块架构优化
- **模块化客户端更新**: 将客户端更新逻辑封装为独立方法
- **内部组件同步**: 确保监听模块所有内部组件使用相同的客户端实例
- **状态一致性保证**: 保证监听模块在客户端重新创建后能正常工作

### 📚 文档更新

#### 代码文档
- **客户端引用更新**: 完善客户端引用更新机制的文档说明
- **监听模块更新**: 添加监听模块客户端更新方法的文档
- **错误处理**: 更新客户端引用更新过程中的错误处理文档

## [1.2.0] - 2024-12-19

### ✨ 新增功能

#### 统一客户端实例管理
- **单一客户端架构**: 实现所有模块共享同一个Pyrogram客户端实例
- **自动客户端更新**: 客户端重新连接时自动更新所有模块的客户端引用
- **连接一致性保证**: 确保所有操作使用相同的连接状态
- **官方推荐方式**: 遵循Pyrogram官方推荐的客户端创建方式
- **使用者注册机制**: 提供客户端使用者注册和注销功能

#### 智能错误处理系统
- **统一错误处理器**: 创建`ErrorHandler`类提供统一的错误处理
- **错误自动分类**: 自动识别和分类不同类型的错误（频道、权限、网络等）
- **友好错误提示**: 提供用户友好的错误信息和解决建议
- **频道信息提取**: 从错误信息中自动提取频道相关信息
- **批量错误处理**: 支持批量错误显示和处理
- **上下文感知**: 根据操作类型提供相应的错误处理

#### 频道验证机制
- **启动前验证**: 在开始监听、转发、下载、上传前验证频道有效性
- **实时频道检测**: 检测频道是否存在、是否可访问、是否有权限
- **错误阻止机制**: 发现无效频道时阻止操作执行并显示错误弹窗
- **详细错误反馈**: 提供具体的错误原因和解决建议

### 🔧 改进功能

#### 错误处理改进
- **监听模块**: 添加频道验证和错误弹窗
- **转发模块**: 添加频道验证和错误弹窗
- **下载模块**: 添加频道验证和错误弹窗
- **上传模块**: 添加频道验证和错误弹窗
- **错误分类**: 支持频道无效、权限不足、网络错误等多种错误类型

#### 客户端管理改进
- **客户端管理器**: 增强`ClientManager`类，支持使用者注册和自动更新
- **异步服务初始化**: 改进组件初始化流程，自动注册为客户端使用者
- **连接状态管理**: 改进连接状态变化时的处理逻辑

### 🐛 修复问题

#### 客户端连接问题
- **修复客户端重新连接**: 解决客户端重新连接后监听和转发模块无法使用的问题
- **修复客户端实例不一致**: 确保所有模块使用同一个客户端实例
- **修复模块初始化**: 解决首次登录后核心组件初始化不完整的问题

#### 错误处理问题
- **修复无效频道处理**: 解决无效频道未弹窗提醒的问题
- **修复错误提示**: 改进错误提示的友好性和准确性
- **修复错误分类**: 完善错误分类和提示信息

### 📚 文档更新

#### 翻译文件更新
- **错误处理翻译**: 添加完整的错误处理相关翻译
- **错误提示翻译**: 添加各种错误类型的友好提示翻译
- **频道验证翻译**: 添加频道验证相关的翻译

#### 代码文档更新
- **客户端管理器**: 完善`ClientManager`类的文档说明
- **错误处理器**: 添加`ErrorHandler`类的完整文档
- **模块初始化**: 更新异步服务初始化器的文档

### 🔧 技术改进

#### 代码架构优化
- **模块解耦**: 改进模块间的依赖关系
- **错误处理统一**: 统一所有模块的错误处理方式
- **客户端管理优化**: 优化客户端实例的管理机制

#### 性能优化
- **连接复用**: 通过统一客户端实例减少连接开销
- **错误处理效率**: 优化错误处理的性能和准确性

## [1.1.0] - 2024-12-18

### ✨ 新增功能

#### 会话管理改进
- **会话名称配置**: 支持自定义会话名称，默认为"tg_manager"
- **会话名称保存**: 会话名称配置自动保存到配置文件
- **会话名称读取**: 启动时自动读取配置文件中的会话名称
- **会话名称验证**: 添加会话名称格式验证

#### 智能会话检测
- **会话文件检测**: 启动时自动检测会话文件是否存在
- **自动登录尝试**: 会话文件存在时自动尝试登录
- **登录失败处理**: 登录失败时自动删除损坏的会话文件
- **API设置跳转**: 登录失败时自动跳转到API设置界面
- **登录对话框**: 自动弹出登录对话框提示用户重新登录

#### 代理配置支持
- **代理启用开关**: 支持启用/禁用代理功能
- **动态代理配置**: 根据配置动态决定是否使用代理
- **代理参数传递**: 登录时根据配置决定是否传递代理参数
- **代理设置验证**: 添加代理设置的验证和错误处理

### 🔧 改进功能

#### 配置管理
- **配置重新加载**: 登录时自动重新加载最新配置
- **配置转换优化**: 改进UI配置到内部配置的转换逻辑
- **配置验证增强**: 增强配置验证的准确性和完整性

#### 用户界面
- **登录按钮状态**: 改进登录按钮状态的更新逻辑
- **设置界面优化**: 优化设置界面的用户体验
- **错误提示改进**: 改进错误提示的友好性和准确性

### 🐛 修复问题

#### 配置问题
- **修复配置丢失**: 解决配置在运行时丢失的问题
- **修复配置转换**: 解决UI配置转换不完整的问题
- **修复配置验证**: 解决配置验证不准确的问题

#### 登录问题
- **修复登录状态**: 解决登录状态更新不正确的问题
- **修复会话处理**: 解决会话文件处理不正确的问题
- **修复代理配置**: 解决代理配置应用不正确的问题

### 📚 文档更新

#### 翻译文件
- **会话管理翻译**: 添加会话管理相关的翻译
- **代理配置翻译**: 添加代理配置相关的翻译
- **错误提示翻译**: 添加更多错误提示的翻译

#### 代码文档
- **配置管理**: 完善配置管理相关的文档
- **客户端管理**: 更新客户端管理器的文档
- **会话处理**: 添加会话处理相关的文档

## [1.0.0] - 2024-12-17

### 🎉 首次发布

#### 核心功能
- **消息转发**: 支持Telegram频道间消息的批量转发
- **实时监听**: 支持实时监听频道消息并自动转发
- **媒体下载**: 支持从频道批量下载媒体文件
- **文件上传**: 支持将本地文件上传到Telegram频道

#### 基础功能
- **配置管理**: 完整的配置保存和加载功能
- **多语言支持**: 支持中文和英文界面
- **主题切换**: 支持多种界面主题
- **日志系统**: 完整的日志记录和查看功能

#### 技术特性
- **Pyrogram集成**: 基于Pyrogram的Telegram客户端
- **Qt6界面**: 使用PySide6构建现代化界面
- **异步处理**: 支持异步操作和并发处理
- **事件驱动**: 基于事件驱动的架构设计

---

## 版本说明

### 版本号规则
- **主版本号**: 不兼容的API修改
- **次版本号**: 向后兼容的功能性新增
- **修订号**: 向后兼容的问题修正

### 更新类型
- ✨ 新增功能
- 🔧 改进功能
- 🐛 修复问题
- 📚 文档更新
- 🚀 性能优化
- 🔒 安全更新
