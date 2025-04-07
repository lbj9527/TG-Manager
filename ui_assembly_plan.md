# TG-Manager UI 集成计划

## 概述

本文档详细说明如何将 TG-Manager 的界面程序与命令行程序集成，使用户仅通过图形界面操作完成所有功能。集成重点包括：配置管理系统的统一、Qt 事件循环与 asyncio 的集成以及登录验证流程的优化。

## 一、配置管理系统统一

### 1.1 分析现有配置系统

当前系统存在两套配置管理：

- `config_manager.py`: 命令行程序使用，基于原始的配置模型
- `ui_config_manager.py`: 界面程序使用，基于 UI 优化的配置模型

### 1.2 迁移步骤

#### 步骤 1: 确保`ui_config_manager.py`包含所有必要功能

检查并确保`UIConfigManager`类提供与`ConfigManager`相同的关键方法：

- `get_general_config()`
- `get_download_config()`
- `get_upload_config()`
- `get_forward_config()`
- `get_monitor_config()`
- `get_proxy_settings()`

如果缺少，添加相应方法：

```python
# 为UIConfigManager添加兼容方法
def get_general_config(self) -> UIGeneralConfig:
    """获取通用配置"""
    return self.ui_config.GENERAL

def get_download_config(self) -> UIDownloadConfig:
    """获取下载配置"""
    return self.ui_config.DOWNLOAD

def get_upload_config(self) -> UIUploadConfig:
    """获取上传配置"""
    return self.ui_config.UPLOAD

def get_forward_config(self) -> UIForwardConfig:
    """获取转发配置"""
    return self.ui_config.FORWARD

def get_monitor_config(self) -> UIMonitorConfig:
    """获取监听配置"""
    return self.ui_config.MONITOR

def get_proxy_settings(self) -> Dict[str, Any]:
    """获取代理设置"""
    general_config = self.get_general_config()
    proxy_settings = {}

    if general_config.proxy_enabled:
        proxy_type = general_config.proxy_type.lower()
        proxy_settings[f"{proxy_type}_hostname"] = general_config.proxy_addr
        proxy_settings[f"{proxy_type}_port"] = general_config.proxy_port

        if general_config.proxy_username:
            proxy_settings[f"{proxy_type}_username"] = general_config.proxy_username
        if general_config.proxy_password:
            proxy_settings[f"{proxy_type}_password"] = general_config.proxy_password

    return proxy_settings
```

#### 步骤 2: 修改 ClientManager 以接受 UIConfigManager

修改`ClientManager`初始化方法，使其同时支持`ConfigManager`和`UIConfigManager`：

```python
def __init__(self, config_manager=None, session_name="tg_forwarder",
             api_id=None, api_hash=None, phone_number=None, **proxy_settings):
    """
    初始化客户端管理器，支持两种初始化方式：
    1. 使用ConfigManager或UIConfigManager
    2. 直接提供API参数

    Args:
        config_manager: 配置管理器实例，可选
        session_name: 会话名称，默认为'tg_forwarder'
        api_id: API ID，当不使用config_manager时必须提供
        api_hash: API Hash，当不使用config_manager时必须提供
        phone_number: 电话号码，可选
        **proxy_settings: 代理设置
    """
    self.session_name = session_name
    self.client = None
    self.phone_number = phone_number

    # 使用配置管理器初始化
    if config_manager:
        self.config_manager = config_manager
        general_config = self.config_manager.get_general_config()
        self.api_id = general_config.api_id
        self.api_hash = general_config.api_hash
        # 获取手机号码(如果存在于配置中)
        if hasattr(general_config, 'phone_number'):
            self.phone_number = general_config.phone_number
        self.proxy_settings = self.config_manager.get_proxy_settings()
        logger.info("使用配置管理器初始化ClientManager")
    # 直接使用传入的参数初始化
    else:
        self.config_manager = None
        self.api_id = api_id
        self.api_hash = api_hash
        self.proxy_settings = proxy_settings
        logger.info("使用直接参数初始化ClientManager")

    if not self.api_id or not self.api_hash:
        raise ValueError("API ID和API Hash不能为空")
```

#### 步骤 3: 为 ClientManager 添加验证码和两步验证处理方法

```python
async def send_code(self, phone_number=None):
    """
    发送验证码

    Args:
        phone_number: 手机号码，如果为None则使用配置中的手机号码

    Returns:
        Dict: 包含sent_code_info信息的字典
    """
    if not self.client:
        self.client = self.create_client()

    phone = phone_number or self.phone_number
    if not phone:
        raise ValueError("没有提供手机号码")

    try:
        logger.info(f"向手机号 {phone} 发送验证码")
        sent_code = await self.client.send_code(phone)
        return sent_code
    except Exception as e:
        logger.error(f"发送验证码失败: {e}")
        raise

async def sign_in(self, phone_code, phone_number=None):
    """
    使用验证码登录

    Args:
        phone_code: 手机验证码
        phone_number: 手机号码，如果为None则使用配置中的手机号码

    Returns:
        User: 登录成功后的用户对象
    """
    if not self.client:
        self.client = self.create_client()

    phone = phone_number or self.phone_number
    if not phone:
        raise ValueError("没有提供手机号码")

    try:
        logger.info(f"使用验证码 {phone_code} 登录账号 {phone}")
        user = await self.client.sign_in(phone, phone_code)
        logger.info(f"登录成功: {user.first_name} (@{user.username})")
        return user
    except Exception as e:
        logger.error(f"登录失败: {e}")
        raise

async def check_password(self, password):
    """
    检查两步验证密码

    Args:
        password: 两步验证密码

    Returns:
        User: 登录成功后的用户对象
    """
    if not self.client:
        raise ValueError("客户端未初始化")

    try:
        logger.info("使用两步验证密码登录")
        user = await self.client.check_password(password)
        logger.info(f"两步验证登录成功: {user.first_name} (@{user.username})")
        return user
    except Exception as e:
        logger.error(f"两步验证登录失败: {e}")
        raise

async def get_me(self):
    """
    获取当前登录用户信息

    Returns:
        User: 当前登录的用户对象，如未登录则返回None
    """
    if not self.client or not self.client.is_connected:
        return None

    try:
        return await self.client.get_me()
    except Exception as e:
        logger.error(f"获取用户信息失败: {e}")
        return None
```

#### 步骤 4: 替换所有项目中对 ConfigManager 的引用

遍历所有模块，使用 UIConfigManager 替换 ConfigManager：

1. 搜索模式: `from src.utils.config_manager import ConfigManager`
2. 替换为: `from src.utils.ui_config_manager import UIConfigManager`
3. 搜索模式: `config_manager = ConfigManager(`
4. 替换为: `config_manager = UIConfigManager(`

注意：对于每个替换，确保根据文件具体情况进行适当调整。

#### 步骤 5: 最终删除 config_manager.py 文件

确认所有替换完成后，删除原始配置管理器：

```bash
rm src/utils/config_manager.py
```

## 二、集成 Qt 事件循环和 asyncio

### 2.1 修改 UI 应用程序入口

修改`run_ui.py`，使其使用 QtAsyncio:

```python
#!/usr/bin/env python3
"""
TG-Manager GUI - 图形界面版本启动入口
"""

import sys
import argparse
from loguru import logger
import os
from pathlib import Path
import datetime
import asyncio

# 导入PySide6相关模块
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Signal, QObject, Slot
import PySide6.QtAsyncio as QtAsyncio

# 导入应用程序类
from src.ui.app import TGManagerApp

# ... 现有代码 ...

async def async_main(app):
    """异步主函数"""
    try:
        # 初始化应用程序并运行
        exit_code = await app.async_run()
        return exit_code
    except Exception as e:
        logger.error(f"程序运行出错: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1

def main():
    """主程序入口"""
    parser = argparse.ArgumentParser(description="TG-Manager GUI - Telegram 消息管理工具图形界面版本")
    parser.add_argument("--debug", action="store_true", help="启用调试模式")
    parser.add_argument("--verbose", action="store_true", help="显示详细日志信息")

    args = parser.parse_args()

    # 设置日志系统
    setup_logger()

    # 设置日志级别
    # ... 现有代码 ...

    # 启动 UI 应用程序
    logger.info("启动 TG-Manager 图形界面")
    if args.verbose:
        logger.debug("已启用详细日志模式")

    try:
        # 创建QApplication实例
        qt_app = QApplication(sys.argv)

        # 创建应用程序实例
        app = TGManagerApp(verbose=args.verbose)

        # 初始化UI
        app.initialize_ui()

        # 使用QtAsyncio运行
        sys.exit(QtAsyncio.run(async_main(app), handle_sigint=True))
    except Exception as e:
        logger.error(f"程序运行出错: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
```

### 2.2 修改 TGManagerApp 类

修改应用程序类，支持异步初始化和运行:

```python
class TGManagerApp(QObject):
    """TG-Manager 应用程序主类"""

    # ... 现有代码 ...

    def initialize_ui(self):
        """初始化UI界面"""
        # 创建主窗口
        self.main_window = MainWindow(self.ui_config_manager)
        self.main_window.show()

    async def async_run(self):
        """异步运行应用程序"""
        # 初始化所需的异步组件
        await self._initialize_async_components()

        # 返回Qt应用程序的退出代码
        return QApplication.instance().exec_()

    async def _initialize_async_components(self):
        """初始化异步组件"""
        try:
            # 这里可以放置需要异步初始化的组件
            # 例如：初始化任务管理器、调度器等
            pass
        except Exception as e:
            logger.error(f"异步组件初始化失败: {e}")
            raise
```

### 2.3 修改 task_manager.py 以支持 QtAsyncio

```python
class TaskManager:
    """任务管理器，负责创建和管理异步任务"""

    def __init__(self):
        """初始化任务管理器"""
        self.tasks = {}
        self.running_tasks = {}
        self.task_completed = Signal(str, object)  # 任务完成信号
        self.task_error = Signal(str, str)         # 任务错误信号

    def create_task(self, task_id, coro, *args, **kwargs):
        """创建异步任务"""
        if task_id in self.tasks:
            raise ValueError(f"任务ID {task_id} 已存在")

        # 创建Task
        task = Task(task_id, coro, *args, **kwargs)
        self.tasks[task_id] = task
        return task

    def start_task(self, task_id):
        """启动任务"""
        if task_id not in self.tasks:
            raise ValueError(f"任务ID {task_id} 不存在")

        task = self.tasks[task_id]

        # 使用QtAsyncio创建任务
        async_task = asyncio.create_task(self._run_task(task))
        self.running_tasks[task_id] = async_task
        return async_task

    async def _run_task(self, task):
        """运行任务并处理结果"""
        try:
            result = await task.run()
            # 使用Qt信号发送完成消息
            QApplication.instance().postEvent(
                self, TaskCompletedEvent(task.task_id, result))
            return result
        except Exception as e:
            # 使用Qt信号发送错误消息
            QApplication.instance().postEvent(
                self, TaskErrorEvent(task.task_id, str(e)))
            raise
```

### 2.4 更新登录处理逻辑

在 MainWindow 中更新\_handle_login 方法：

```python
def _handle_login(self):
    """处理用户登录"""
    try:
        # 创建登录表单对话框
        login_dialog = QDialog(self)
        login_dialog.setWindowTitle("登录Telegram")
        login_dialog.setMinimumWidth(400)

        # 创建布局
        main_layout = QVBoxLayout(login_dialog)

        # 添加说明标签
        info_label = QLabel("以下是您在设置中配置的Telegram API凭据和手机号码信息。点击'确定'开始登录。")
        info_label.setWordWrap(True)
        main_layout.addWidget(info_label)

        # 创建表单布局
        form_layout = QFormLayout()

        # 创建只读信息展示字段
        api_id_label = QLabel()
        api_hash_label = QLabel()
        phone_label = QLabel()

        # 从配置中加载API ID、Hash和手机号码（如果存在）
        if 'GENERAL' in self.config:
            if 'api_id' in self.config['GENERAL']:
                api_id_label.setText(str(self.config['GENERAL']['api_id']))
            if 'api_hash' in self.config['GENERAL']:
                # 只显示API Hash的一部分，保护隐私
                api_hash = self.config['GENERAL']['api_hash']
                masked_hash = api_hash[:6] + "..." + api_hash[-6:] if len(api_hash) > 12 else api_hash
                api_hash_label.setText(masked_hash)
            if 'phone_number' in self.config['GENERAL'] and self.config['GENERAL']['phone_number']:
                phone_label.setText(self.config['GENERAL']['phone_number'])

        # 添加表单字段
        form_layout.addRow("API ID:", api_id_label)
        form_layout.addRow("API Hash:", api_hash_label)
        form_layout.addRow("手机号码:", phone_label)

        # 创建按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(login_dialog.accept)
        button_box.rejected.connect(login_dialog.reject)

        # 组装布局
        main_layout.addLayout(form_layout)
        main_layout.addWidget(button_box)

        # 显示对话框
        result = login_dialog.exec_()

        # 如果用户点击了"确定"
        if result == QDialog.Accepted:
            # 检查配置中是否存在所需信息
            if 'GENERAL' not in self.config or 'api_id' not in self.config['GENERAL'] or \
               'api_hash' not in self.config['GENERAL'] or 'phone_number' not in self.config['GENERAL'] or \
               not self.config['GENERAL']['api_id'] or not self.config['GENERAL']['api_hash'] or \
               not self.config['GENERAL']['phone_number']:
                QMessageBox.warning(
                    self,
                    "配置不完整",
                    "请在设置中完成API凭据和手机号码的配置。",
                    QMessageBox.Ok
                )
                # 打开设置界面
                self._open_settings()
                return

            phone = self.config['GENERAL']['phone_number']

            # 显示登录成功消息
            QMessageBox.information(
                self,
                "登录开始",
                f"正在使用以下手机号登录: {phone}",
                QMessageBox.Ok
            )

            # 更新状态栏
            self.statusBar().showMessage(f"正在连接到Telegram: {phone}")

            # 开始异步登录过程
            asyncio.create_task(self._async_login())

    except Exception as e:
        logger.error(f"登录处理时出错: {e}")
        QMessageBox.critical(
            self,
            "登录错误",
            f"登录过程中发生错误: {str(e)}",
            QMessageBox.Ok
        )

async def _async_login(self):
    """异步登录过程"""
    try:
        # 获取配置信息
        api_id = self.config['GENERAL']['api_id']
        api_hash = self.config['GENERAL']['api_hash']
        phone = self.config['GENERAL']['phone_number']

        # 创建客户端管理器
        client_manager = ClientManager(
            api_id=api_id,
            api_hash=api_hash,
            phone_number=phone
        )

        # 发送验证码
        sent_code = await client_manager.send_code()

        # 显示验证码输入对话框
        code = await self._get_verification_code_async()
        if not code:
            self.statusBar().showMessage("登录取消")
            return

        try:
            # 尝试使用验证码登录
            user = await client_manager.sign_in(code)
            # 登录成功
            self.statusBar().showMessage(f"登录成功: {user.first_name} (@{user.username})")
            self.client_manager = client_manager

            # 这里可以添加登录成功后的逻辑
            # ...

        except SessionPasswordNeeded:
            # 如果需要两步验证
            password = await self._get_2fa_password_async()
            if not password:
                self.statusBar().showMessage("登录取消")
                return

            # 尝试使用两步验证密码登录
            user = await client_manager.check_password(password)
            # 登录成功
            self.statusBar().showMessage(f"登录成功: {user.first_name} (@{user.username})")
            self.client_manager = client_manager

            # 这里可以添加登录成功后的逻辑
            # ...

    except Exception as e:
        logger.error(f"异步登录过程中出错: {e}")
        error_msg = str(e)
        self.statusBar().showMessage(f"登录失败: {error_msg}")

        # 在主线程中显示错误消息
        QApplication.instance().postEvent(
            self,
            ShowMessageEvent("登录错误", f"登录过程中发生错误: {error_msg}")
        )

async def _get_verification_code_async(self):
    """异步获取验证码"""
    # 创建一个future，用于从主线程获取结果
    future = asyncio.Future()

    # 在主线程中显示对话框
    QApplication.instance().postEvent(
        self,
        GetVerificationCodeEvent(future)
    )

    # 等待主线程设置结果
    return await future

def _show_verification_code_dialog(self, future):
    """显示验证码输入对话框"""
    dialog = QDialog(self)
    dialog.setWindowTitle("验证码")
    dialog.setMinimumWidth(300)

    layout = QVBoxLayout(dialog)

    # 添加说明
    info_label = QLabel("Telegram已发送验证码到您的手机，请输入：")
    info_label.setWordWrap(True)
    layout.addWidget(info_label)

    # 添加验证码输入框
    code_input = QLineEdit()
    code_input.setPlaceholderText("验证码")
    layout.addWidget(code_input)

    # 添加按钮
    button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    button_box.accepted.connect(dialog.accept)
    button_box.rejected.connect(dialog.reject)
    layout.addWidget(button_box)

    # 显示对话框
    result = dialog.exec_()

    # 处理结果
    if result == QDialog.Accepted and code_input.text():
        future.set_result(code_input.text().strip())
    else:
        future.set_result(None)
```

## 三、登录对话框优化

### 3.1 创建验证码输入对话框类

```python
class VerificationCodeDialog(QDialog):
    """验证码输入对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("验证码")
        self.setMinimumWidth(300)
        self.setup_ui()

    def setup_ui(self):
        """设置UI界面"""
        layout = QVBoxLayout(self)

        # 添加说明
        info_label = QLabel("Telegram已发送验证码到您的手机，请输入：")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # 添加验证码输入框
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("验证码")
        layout.addWidget(self.code_input)

        # 添加按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_code(self):
        """获取用户输入的验证码"""
        if self.result() == QDialog.Accepted:
            return self.code_input.text().strip()
        return None
```

### 3.2 创建两步验证密码输入对话框

```python
class TwoFactorAuthDialog(QDialog):
    """两步验证密码输入对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("两步验证")
        self.setMinimumWidth(300)
        self.setup_ui()

    def setup_ui(self):
        """设置UI界面"""
        layout = QVBoxLayout(self)

        # 添加说明
        info_label = QLabel("该账号已启用两步验证，请输入您的密码：")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # 添加密码输入框
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("两步验证密码")
        self.password_input.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.password_input)

        # 添加按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_password(self):
        """获取用户输入的密码"""
        if self.result() == QDialog.Accepted:
            return self.password_input.text()
        return None
```

## 四、实施时间表

### 第一阶段：准备工作（2 天）

1. 备份当前代码库
2. 详细分析`config_manager.py`和`ui_config_manager.py`的差异
3. 确定需要修改的文件和函数列表

### 第二阶段：配置系统迁移（3 天）

1. 修改`UIConfigManager`，添加兼容方法
2. 更新`ClientManager`，支持多种初始化方式
3. 添加验证码和两步验证处理方法
4. 替换所有模块中对`ConfigManager`的引用

### 第三阶段：异步系统集成（4 天）

1. 修改应用程序入口，使用 QtAsyncio
2. 更新 TGManagerApp 类，支持异步初始化和运行
3. 修改 task_manager.py 和 task_scheduler.py
4. 更新各功能模块中的异步实现

### 第四阶段：登录流程优化（2 天）

1. 创建验证码输入对话框
2. 创建两步验证密码输入对话框
3. 更新登录处理逻辑
4. 测试完整登录流程

### 第五阶段：测试与修复（3 天）

1. 单元测试和集成测试
2. 修复发现的问题
3. 完善错误处理和日志记录

### 第六阶段：清理和完善（1 天）

1. 删除不再使用的文件（如 config_manager.py）
2. 更新文档和注释
3. 进行最终的全面测试

## 五、注意事项

1. 修改过程中确保保留原有功能，不改变现有界面
2. 遵循错误处理最佳实践，提供用户友好的错误消息
3. 特别关注 asyncio 和 Qt 事件循环的集成，避免死锁
4. 确保所有异步操作都在正确的上下文中执行
5. 验证码输入框应当具有良好的用户体验，提供清晰的指导
6. 两步验证密码输入应确保安全性，使用密码掩码

## 六、下载模块集成

### 6.1 分析下载模块

`src/modules/downloader.py`中的`Downloader`类是负责从 Telegram 频道下载媒体文件的核心组件。目前这个模块主要通过命令行程序启动并运行。我们需要将其集成到 UI 界面中，使其能够通过界面配置和操作。

### 6.2 功能分析与界面映射

| 命令行功能   | UI 界面组件    | 集成方式                       |
| ------------ | -------------- | ------------------------------ |
| 配置下载来源 | 下载设置表格   | 使用表格视图展示和编辑下载设置 |
| 配置下载路径 | 路径选择框     | 使用文件对话框选择下载目录     |
| 媒体类型筛选 | 复选框组       | 使用复选框组选择媒体类型       |
| 关键词过滤   | 关键词输入表格 | 使用表格添加/删除关键词        |
| 下载任务管理 | 任务列表视图   | 使用列表视图显示任务状态       |

### 6.3 集成步骤

#### 步骤 1: 将 Downloader 类改造为支持信号-槽机制

```python
class Downloader(QObject, EventEmitter):
    """下载器类，负责从Telegram频道下载媒体"""

    # 定义Qt信号
    download_started = Signal(str)  # 参数：任务ID
    download_progress = Signal(str, int, int)  # 参数：任务ID, 当前进度, 总数
    download_complete = Signal(str, int)  # 参数：任务ID, 下载文件数
    download_error = Signal(str, str)  # 参数：任务ID, 错误信息

    def __init__(self, client_manager, config_manager=None):
        QObject.__init__(self)
        EventEmitter.__init__(self)

        # 初始化属性
        self.client_manager = client_manager
        self.config_manager = config_manager
        # ... 其余初始化代码 ...

        # 将原有的事件回调连接到信号
        self.on("download_started", lambda task_id: self.download_started.emit(task_id))
        self.on("download_progress", lambda task_id, current, total:
                self.download_progress.emit(task_id, current, total))
        self.on("download_complete", lambda task_id, file_count:
                self.download_complete.emit(task_id, file_count))
        self.on("download_error", lambda task_id, error:
                self.download_error.emit(task_id, str(error)))
```

#### 步骤 2: 修改 DownloadView 类，集成下载功能

```python
class DownloadView(QWidget):
    """下载视图类，提供下载功能的UI界面"""

    def __init__(self, ui_config_manager, client_manager=None, parent=None):
        super().__init__(parent)
        self.ui_config_manager = ui_config_manager
        self.client_manager = client_manager
        self.downloader = None
        self.setup_ui()
        self.setup_connections()

        # 初始化下载器
        self._initialize_downloader()

    def _initialize_downloader(self):
        """初始化下载器"""
        if self.client_manager and self.client_manager.client and self.client_manager.client.is_connected:
            self.downloader = Downloader(self.client_manager, self.ui_config_manager)
            self._connect_downloader_signals()
            self.enable_controls(True)
        else:
            self.enable_controls(False)
            QMessageBox.warning(
                self,
                "未登录",
                "请先登录Telegram账号再使用下载功能。",
                QMessageBox.Ok
            )

    def _connect_downloader_signals(self):
        """连接下载器信号"""
        if not self.downloader:
            return

        # 连接信号到槽函数
        self.downloader.download_started.connect(self._on_download_started)
        self.downloader.download_progress.connect(self._on_download_progress)
        self.downloader.download_complete.connect(self._on_download_complete)
        self.downloader.download_error.connect(self._on_download_error)

    def _on_download_started(self, task_id):
        """下载开始处理函数"""
        # 更新UI状态
        self.status_label.setText(f"下载任务 {task_id} 已开始")
        # 添加任务到任务列表
        self._add_task_to_list(task_id, "进行中")

    def _on_download_progress(self, task_id, current, total):
        """下载进度处理函数"""
        # 更新进度条
        percent = int(current / total * 100) if total > 0 else 0
        self._update_task_progress(task_id, percent)
        # 更新状态标签
        self.status_label.setText(f"下载中: {current}/{total} ({percent}%)")

    def _on_download_complete(self, task_id, file_count):
        """下载完成处理函数"""
        # 更新UI状态
        self.status_label.setText(f"下载完成: 已下载 {file_count} 个文件")
        # 更新任务状态
        self._update_task_status(task_id, "已完成")
        # 启用控件
        self.enable_controls(True)

    def _on_download_error(self, task_id, error):
        """下载错误处理函数"""
        # 显示错误消息
        QMessageBox.critical(
            self,
            "下载错误",
            f"下载任务 {task_id} 失败: {error}",
            QMessageBox.Ok
        )
        # 更新任务状态
        self._update_task_status(task_id, f"失败: {error}")
        # 启用控件
        self.enable_controls(True)

    async def start_download(self):
        """启动下载任务"""
        if not self.downloader:
            self._initialize_downloader()
            if not self.downloader:
                return

        # 禁用控件，防止重复操作
        self.enable_controls(False)

        try:
            # 收集下载设置
            settings = self._collect_download_settings()

            # 创建任务ID
            task_id = f"download_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # 使用asyncio.create_task启动异步下载
            asyncio.create_task(self._async_download(task_id, settings))

        except Exception as e:
            logger.error(f"启动下载任务失败: {e}")
            QMessageBox.critical(
                self,
                "启动失败",
                f"启动下载任务失败: {str(e)}",
                QMessageBox.Ok
            )
            self.enable_controls(True)

    async def _async_download(self, task_id, settings):
        """异步执行下载任务"""
        try:
            # 执行下载
            await self.downloader.download_media(**settings, task_id=task_id)
        except Exception as e:
            logger.error(f"下载任务执行失败: {e}")
            # 使用Qt信号处理UI更新
            QApplication.instance().postEvent(
                self,
                DownloadErrorEvent(task_id, str(e))
            )
```

#### 步骤 3: 创建自定义事件类型，用于在异步上下文中更新 UI

```python
class DownloadErrorEvent(QEvent):
    """下载错误事件"""

    EVENT_TYPE = QEvent.Type(QEvent.registerEventType())

    def __init__(self, task_id, error_message):
        super().__init__(self.EVENT_TYPE)
        self.task_id = task_id
        self.error_message = error_message
```

#### 步骤 4: 实现事件处理方法

```python
class DownloadView(QWidget):
    # ... 现有代码 ...

    def event(self, event):
        """处理自定义事件"""
        if event.type() == DownloadErrorEvent.EVENT_TYPE:
            self._on_download_error(event.task_id, event.error_message)
            return True
        return super().event(event)
```

### 6.4 下载设置读取与保存

```python
def _collect_download_settings(self):
    """收集下载设置"""
    settings = {}

    # 获取源频道
    source_channels = []
    for row in range(self.source_table.rowCount()):
        channel = self.source_table.item(row, 0).text()
        if channel:
            source_channels.append(channel)

    if not source_channels:
        raise ValueError("请至少添加一个源频道")

    settings["source_channels"] = source_channels

    # 获取媒体类型
    media_types = []
    if self.photo_check.isChecked():
        media_types.append("photo")
    if self.video_check.isChecked():
        media_types.append("video")
    if self.document_check.isChecked():
        media_types.append("document")
    if self.audio_check.isChecked():
        media_types.append("audio")
    if self.animation_check.isChecked():
        media_types.append("animation")

    if not media_types:
        raise ValueError("请至少选择一种媒体类型")

    settings["media_types"] = media_types

    # 获取关键词
    keywords = []
    for row in range(self.keyword_table.rowCount()):
        keyword = self.keyword_table.item(row, 0).text()
        if keyword:
            keywords.append(keyword)

    settings["keywords"] = keywords

    # 获取下载路径
    download_path = self.path_edit.text()
    if not download_path:
        raise ValueError("请指定下载路径")

    settings["download_path"] = download_path

    # 获取开始和结束消息ID
    try:
        start_id = int(self.start_id_edit.text()) if self.start_id_edit.text() else 0
        end_id = int(self.end_id_edit.text()) if self.end_id_edit.text() else 0

        settings["start_id"] = start_id
        settings["end_id"] = end_id
    except ValueError:
        raise ValueError("消息ID必须是整数")

    # 其他设置
    settings["parallel_download"] = self.parallel_check.isChecked()
    settings["max_concurrent_downloads"] = self.max_concurrent_spin.value()

    return settings
```

## 七、上传模块集成

### 7.1 分析上传模块

`src/modules/uploader.py`中的`Uploader`类是负责将本地媒体文件上传到 Telegram 频道的核心组件。我们需要将其集成到 UI 界面中，让用户能够通过图形界面操作上传功能。

### 7.2 功能分析与界面映射

| 命令行功能   | UI 界面组件  | 集成方式                     |
| ------------ | ------------ | ---------------------------- |
| 配置目标频道 | 频道列表表格 | 使用表格视图编辑目标频道     |
| 配置上传路径 | 路径选择框   | 使用文件对话框选择上传目录   |
| 设置描述模板 | 文本输入框   | 使用文本框编辑描述模板       |
| 上传设置选项 | 复选框组     | 使用复选框组选择各种上传选项 |
| 上传任务管理 | 任务列表视图 | 使用列表视图显示任务状态     |

### 7.3 集成步骤

#### 步骤 1: 将 Uploader 类改造为支持信号-槽机制

```python
class Uploader(QObject, EventEmitter):
    """上传器类，负责将本地媒体上传到Telegram频道"""

    # 定义Qt信号
    upload_started = Signal(str)  # 参数：任务ID
    upload_progress = Signal(str, int, int)  # 参数：任务ID, 当前进度, 总数
    upload_complete = Signal(str, int)  # 参数：任务ID, 上传文件数
    upload_error = Signal(str, str)  # 参数：任务ID, 错误信息

    def __init__(self, client_manager, config_manager=None):
        QObject.__init__(self)
        EventEmitter.__init__(self)

        # 初始化属性
        self.client_manager = client_manager
        self.config_manager = config_manager
        # ... 其余初始化代码 ...

        # 将原有的事件回调连接到信号
        self.on("upload_started", lambda task_id: self.upload_started.emit(task_id))
        self.on("upload_progress", lambda task_id, current, total:
                self.upload_progress.emit(task_id, current, total))
        self.on("upload_complete", lambda task_id, file_count:
                self.upload_complete.emit(task_id, file_count))
        self.on("upload_error", lambda task_id, error:
                self.upload_error.emit(task_id, str(error)))
```

#### 步骤 2: 修改 UploadView 类，集成上传功能

```python
class UploadView(QWidget):
    """上传视图类，提供上传功能的UI界面"""

    def __init__(self, ui_config_manager, client_manager=None, parent=None):
        super().__init__(parent)
        self.ui_config_manager = ui_config_manager
        self.client_manager = client_manager
        self.uploader = None
        self.setup_ui()
        self.setup_connections()

        # 初始化上传器
        self._initialize_uploader()

    def _initialize_uploader(self):
        """初始化上传器"""
        if self.client_manager and self.client_manager.client and self.client_manager.client.is_connected:
            self.uploader = Uploader(self.client_manager, self.ui_config_manager)
            self._connect_uploader_signals()
            self.enable_controls(True)
        else:
            self.enable_controls(False)
            QMessageBox.warning(
                self,
                "未登录",
                "请先登录Telegram账号再使用上传功能。",
                QMessageBox.Ok
            )

    def _connect_uploader_signals(self):
        """连接上传器信号"""
        if not self.uploader:
            return

        # 连接信号到槽函数
        self.uploader.upload_started.connect(self._on_upload_started)
        self.uploader.upload_progress.connect(self._on_upload_progress)
        self.uploader.upload_complete.connect(self._on_upload_complete)
        self.uploader.upload_error.connect(self._on_upload_error)

    def _on_upload_started(self, task_id):
        """上传开始处理函数"""
        # 更新UI状态
        self.status_label.setText(f"上传任务 {task_id} 已开始")
        # 添加任务到任务列表
        self._add_task_to_list(task_id, "进行中")

    def _on_upload_progress(self, task_id, current, total):
        """上传进度处理函数"""
        # 更新进度条
        percent = int(current / total * 100) if total > 0 else 0
        self._update_task_progress(task_id, percent)
        # 更新状态标签
        self.status_label.setText(f"上传中: {current}/{total} ({percent}%)")

    def _on_upload_complete(self, task_id, file_count):
        """上传完成处理函数"""
        # 更新UI状态
        self.status_label.setText(f"上传完成: 已上传 {file_count} 个文件")
        # 更新任务状态
        self._update_task_status(task_id, "已完成")
        # 启用控件
        self.enable_controls(True)

    def _on_upload_error(self, task_id, error):
        """上传错误处理函数"""
        # 显示错误消息
        QMessageBox.critical(
            self,
            "上传错误",
            f"上传任务 {task_id} 失败: {error}",
            QMessageBox.Ok
        )
        # 更新任务状态
        self._update_task_status(task_id, f"失败: {error}")
        # 启用控件
        self.enable_controls(True)

    async def start_upload(self):
        """启动上传任务"""
        if not self.uploader:
            self._initialize_uploader()
            if not self.uploader:
                return

        # 禁用控件，防止重复操作
        self.enable_controls(False)

        try:
            # 收集上传设置
            settings = self._collect_upload_settings()

            # 创建任务ID
            task_id = f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # 使用asyncio.create_task启动异步上传
            asyncio.create_task(self._async_upload(task_id, settings))

        except Exception as e:
            logger.error(f"启动上传任务失败: {e}")
            QMessageBox.critical(
                self,
                "启动失败",
                f"启动上传任务失败: {str(e)}",
                QMessageBox.Ok
            )
            self.enable_controls(True)

    async def _async_upload(self, task_id, settings):
        """异步执行上传任务"""
        try:
            # 执行上传
            await self.uploader.upload_media(**settings, task_id=task_id)
        except Exception as e:
            logger.error(f"上传任务执行失败: {e}")
            # 使用Qt信号处理UI更新
            QApplication.instance().postEvent(
                self,
                UploadErrorEvent(task_id, str(e))
            )
```

#### 步骤 3: 创建自定义事件类型，用于在异步上下文中更新 UI

```python
class UploadErrorEvent(QEvent):
    """上传错误事件"""

    EVENT_TYPE = QEvent.Type(QEvent.registerEventType())

    def __init__(self, task_id, error_message):
        super().__init__(self.EVENT_TYPE)
        self.task_id = task_id
        self.error_message = error_message
```

#### 步骤 4: 实现事件处理方法

```python
class UploadView(QWidget):
    # ... 现有代码 ...

    def event(self, event):
        """处理自定义事件"""
        if event.type() == UploadErrorEvent.EVENT_TYPE:
            self._on_upload_error(event.task_id, event.error_message)
            return True
        return super().event(event)
```

### 7.4 上传设置读取与保存

```python
def _collect_upload_settings(self):
    """收集上传设置"""
    settings = {}

    # 获取目标频道
    target_channels = []
    for row in range(self.targets_table.rowCount()):
        channel = self.targets_table.item(row, 0).text()
        if channel:
            target_channels.append(channel)

    if not target_channels:
        raise ValueError("请至少添加一个目标频道")

    settings["target_channels"] = target_channels

    # 获取上传目录
    directory = self.directory_edit.text()
    if not directory:
        raise ValueError("请指定上传目录")

    if not os.path.exists(directory):
        raise ValueError(f"上传目录不存在: {directory}")

    settings["directory"] = directory

    # 获取描述模板
    caption_template = self.caption_template_edit.text()
    settings["caption_template"] = caption_template

    # 获取上传选项
    settings["options"] = {
        "use_folder_name": self.use_folder_name_check.isChecked(),
        "read_title_txt": self.read_title_txt_check.isChecked(),
        "use_custom_template": self.use_custom_template_check.isChecked(),
        "auto_thumbnail": self.auto_thumbnail_check.isChecked()
    }

    # 上传延迟
    delay_between_uploads = self.delay_spin.value()
    settings["delay_between_uploads"] = delay_between_uploads

    return settings
```

## 八、转发模块集成

### 8.1 分析转发模块

`src/modules/forwarder.py`中的`Forwarder`类是负责消息转发的核心组件。我们需要将其集成到 UI 界面中，让用户能够通过图形界面配置和操作转发功能。

### 8.2 功能分析与界面映射

| 命令行功能           | UI 界面组件 | 集成方式                                   |
| -------------------- | ----------- | ------------------------------------------ |
| 配置源频道和目标频道 | 频道对表格  | 使用表格视图编辑源频道和目标频道           |
| 设置媒体类型         | 复选框组    | 使用复选框组选择要转发的媒体类型           |
| 转发选项             | 复选框      | 使用复选框选择转发选项(隐藏作者、移除描述) |
| 消息 ID 范围         | 数字输入框  | 使用数字输入框设置开始和结束消息 ID        |
| 转发延迟             | 滑动条      | 使用滑动条设置转发延迟                     |
| 临时文件路径         | 路径选择框  | 使用文件对话框选择临时文件路径             |

### 8.3 集成步骤

#### 步骤 1: 将 Forwarder 类改造为支持信号-槽机制

```python
class Forwarder(QObject, EventEmitter):
    """转发器类，负责在Telegram频道间转发消息"""

    # 定义Qt信号
    forward_started = Signal(str)  # 参数：任务ID
    forward_progress = Signal(str, int, int)  # 参数：任务ID, 当前进度, 总数
    forward_complete = Signal(str, int)  # 参数：任务ID, 转发消息数
    forward_error = Signal(str, str)  # 参数：任务ID, 错误信息

    def __init__(self, client_manager, config_manager=None):
        QObject.__init__(self)
        EventEmitter.__init__(self)

        # 初始化属性
        self.client_manager = client_manager
        self.config_manager = config_manager
        # ... 其余初始化代码 ...

        # 将原有的事件回调连接到信号
        self.on("forward_started", lambda task_id: self.forward_started.emit(task_id))
        self.on("forward_progress", lambda task_id, current, total:
                self.forward_progress.emit(task_id, current, total))
        self.on("forward_complete", lambda task_id, message_count:
                self.forward_complete.emit(task_id, message_count))
        self.on("forward_error", lambda task_id, error:
                self.forward_error.emit(task_id, str(error)))
```

#### 步骤 2: 修改 ForwardView 类，集成转发功能

```python
class ForwardView(QWidget):
    """转发视图类，提供转发功能的UI界面"""

    def __init__(self, ui_config_manager, client_manager=None, parent=None):
        super().__init__(parent)
        self.ui_config_manager = ui_config_manager
        self.client_manager = client_manager
        self.forwarder = None
        self.setup_ui()
        self.setup_connections()

        # 初始化转发器
        self._initialize_forwarder()

    def _initialize_forwarder(self):
        """初始化转发器"""
        if self.client_manager and self.client_manager.client and self.client_manager.client.is_connected:
            self.forwarder = Forwarder(self.client_manager, self.ui_config_manager)
            self._connect_forwarder_signals()
            self.enable_controls(True)
        else:
            self.enable_controls(False)
            QMessageBox.warning(
                self,
                "未登录",
                "请先登录Telegram账号再使用转发功能。",
                QMessageBox.Ok
            )

    def _connect_forwarder_signals(self):
        """连接转发器信号"""
        if not self.forwarder:
            return

        # 连接信号到槽函数
        self.forwarder.forward_started.connect(self._on_forward_started)
        self.forwarder.forward_progress.connect(self._on_forward_progress)
        self.forwarder.forward_complete.connect(self._on_forward_complete)
        self.forwarder.forward_error.connect(self._on_forward_error)

    def _on_forward_started(self, task_id):
        """转发开始处理函数"""
        # 更新UI状态
        self.status_label.setText(f"转发任务 {task_id} 已开始")
        # 添加任务到任务列表
        self._add_task_to_list(task_id, "进行中")

    def _on_forward_progress(self, task_id, current, total):
        """转发进度处理函数"""
        # 更新进度条
        percent = int(current / total * 100) if total > 0 else 0
        self._update_task_progress(task_id, percent)
        # 更新状态标签
        self.status_label.setText(f"转发中: {current}/{total} ({percent}%)")

    def _on_forward_complete(self, task_id, message_count):
        """转发完成处理函数"""
        # 更新UI状态
        self.status_label.setText(f"转发完成: 已转发 {message_count} 条消息")
        # 更新任务状态
        self._update_task_status(task_id, "已完成")
        # 启用控件
        self.enable_controls(True)

    def _on_forward_error(self, task_id, error):
        """转发错误处理函数"""
        # 显示错误消息
        QMessageBox.critical(
            self,
            "转发错误",
            f"转发任务 {task_id} 失败: {error}",
            QMessageBox.Ok
        )
        # 更新任务状态
        self._update_task_status(task_id, f"失败: {error}")
        # 启用控件
        self.enable_controls(True)

    async def start_forward(self):
        """启动转发任务"""
        if not self.forwarder:
            self._initialize_forwarder()
            if not self.forwarder:
                return

        # 禁用控件，防止重复操作
        self.enable_controls(False)

        try:
            # 收集转发设置
            settings = self._collect_forward_settings()

            # 创建任务ID
            task_id = f"forward_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # 使用asyncio.create_task启动异步转发
            asyncio.create_task(self._async_forward(task_id, settings))

        except Exception as e:
            logger.error(f"启动转发任务失败: {e}")
            QMessageBox.critical(
                self,
                "启动失败",
                f"启动转发任务失败: {str(e)}",
                QMessageBox.Ok
            )
            self.enable_controls(True)

    async def _async_forward(self, task_id, settings):
        """异步执行转发任务"""
        try:
            # 执行转发
            await self.forwarder.forward_messages(**settings, task_id=task_id)
        except Exception as e:
            logger.error(f"转发任务执行失败: {e}")
            # 使用Qt信号处理UI更新
            QApplication.instance().postEvent(
                self,
                ForwardErrorEvent(task_id, str(e))
            )
```

#### 步骤 3: 创建自定义事件类型，用于在异步上下文中更新 UI

```python
class ForwardErrorEvent(QEvent):
    """转发错误事件"""

    EVENT_TYPE = QEvent.Type(QEvent.registerEventType())

    def __init__(self, task_id, error_message):
        super().__init__(self.EVENT_TYPE)
        self.task_id = task_id
        self.error_message = error_message
```

#### 步骤 4: 实现事件处理方法

```python
class ForwardView(QWidget):
    # ... 现有代码 ...

    def event(self, event):
        """处理自定义事件"""
        if event.type() == ForwardErrorEvent.EVENT_TYPE:
            self._on_forward_error(event.task_id, event.error_message)
            return True
        return super().event(event)
```

### 8.4 转发设置读取与保存

```python
def _collect_forward_settings(self):
    """收集转发设置"""
    settings = {}

    # 获取频道对
    channel_pairs = []
    for row in range(self.channel_pairs_table.rowCount()):
        source = self.channel_pairs_table.item(row, 0).text()
        targets_str = self.channel_pairs_table.item(row, 1).text()

        if source and targets_str:
            targets = [t.strip() for t in targets_str.split(',')]
            channel_pairs.append({
                "source_channel": source,
                "target_channels": targets
            })

    if not channel_pairs:
        raise ValueError("请至少添加一个频道对")

    settings["channel_pairs"] = channel_pairs

    # 获取媒体类型
    media_types = []
    if self.photo_check.isChecked():
        media_types.append("photo")
    if self.video_check.isChecked():
        media_types.append("video")
    if self.document_check.isChecked():
        media_types.append("document")
    if self.audio_check.isChecked():
        media_types.append("audio")
    if self.animation_check.isChecked():
        media_types.append("animation")

    if not media_types:
        raise ValueError("请至少选择一种媒体类型")

    settings["media_types"] = media_types

    # 获取转发选项
    settings["remove_captions"] = self.remove_captions_check.isChecked()
    settings["hide_author"] = self.hide_author_check.isChecked()

    # 获取消息ID范围
    try:
        start_id = int(self.start_id_edit.text()) if self.start_id_edit.text() else 0
        end_id = int(self.end_id_edit.text()) if self.end_id_edit.text() else 0

        settings["start_id"] = start_id
        settings["end_id"] = end_id
    except ValueError:
        raise ValueError("消息ID必须是整数")

    # 获取转发延迟
    settings["forward_delay"] = self.delay_spin.value()

    # 获取临时路径
    tmp_path = self.tmp_path_edit.text()
    if not tmp_path:
        tmp_path = "tmp"

    settings["tmp_path"] = tmp_path

    return settings
```

## 九、监听模块集成

### 9.1 分析监听模块

`src/modules/monitor.py`中的`Monitor`类是负责实时监听 Telegram 频道消息并自动转发的核心组件。我们需要将其集成到 UI 界面中，让用户能够通过图形界面配置和启动监听功能。

### 9.2 功能分析与界面映射

| 命令行功能     | UI 界面组件    | 集成方式                             |
| -------------- | -------------- | ------------------------------------ |
| 配置监听频道对 | 监听频道对表格 | 使用表格视图编辑监听源频道和目标频道 |
| 设置媒体类型   | 复选框组       | 使用复选框组选择要监听的媒体类型     |
| 文本替换规则   | 文本替换表格   | 使用表格添加和编辑文本替换规则       |
| 设置监听时长   | 时间选择器     | 使用时间选择器设置监听持续时间       |
| 转发延迟       | 滑动条         | 使用滑动条设置转发延迟               |
| 移除描述选项   | 复选框         | 使用复选框选择是否移除描述           |

### 9.3 集成步骤

#### 步骤 1: 将 Monitor 类改造为支持信号-槽机制

```python
class Monitor(QObject, EventEmitter):
    """监听器类，负责实时监听Telegram频道消息并转发"""

    # 定义Qt信号
    monitor_started = Signal(str)  # 参数：任务ID
    monitor_message_received = Signal(str, str, int)  # 参数：任务ID, 频道名, 消息ID
    monitor_message_forwarded = Signal(str, str, int, list)  # 参数：任务ID, 源频道, 消息ID, 目标频道列表
    monitor_stopped = Signal(str, bool, str)  # 参数：任务ID, 是否成功完成, 停止原因
    monitor_error = Signal(str, str)  # 参数：任务ID, 错误信息

    def __init__(self, client_manager, config_manager=None):
        QObject.__init__(self)
        EventEmitter.__init__(self)

        # 初始化属性
        self.client_manager = client_manager
        self.config_manager = config_manager
        self.running = False
        self.monitoring_tasks = {}
        # ... 其余初始化代码 ...

        # 将原有的事件回调连接到信号
        self.on("monitor_started", lambda task_id: self.monitor_started.emit(task_id))
        self.on("monitor_message_received", lambda task_id, channel, msg_id:
                self.monitor_message_received.emit(task_id, channel, msg_id))
        self.on("monitor_message_forwarded", lambda task_id, source, msg_id, targets:
                self.monitor_message_forwarded.emit(task_id, source, msg_id, targets))
        self.on("monitor_stopped", lambda task_id, success, reason:
                self.monitor_stopped.emit(task_id, success, reason))
        self.on("monitor_error", lambda task_id, error:
                self.monitor_error.emit(task_id, str(error)))
```

#### 步骤 2: 修改 ListenView 类，集成监听功能

```python
class ListenView(QWidget):
    """监听视图类，提供消息监听功能的UI界面"""

    def __init__(self, ui_config_manager, client_manager=None, parent=None):
        super().__init__(parent)
        self.ui_config_manager = ui_config_manager
        self.client_manager = client_manager
        self.monitor = None
        self.current_task_id = None
        self.setup_ui()
        self.setup_connections()

        # 初始化监听器
        self._initialize_monitor()

    def _initialize_monitor(self):
        """初始化监听器"""
        if self.client_manager and self.client_manager.client and self.client_manager.client.is_connected:
            self.monitor = Monitor(self.client_manager, self.ui_config_manager)
            self._connect_monitor_signals()
            self.enable_controls(True)
        else:
            self.enable_controls(False)
            QMessageBox.warning(
                self,
                "未登录",
                "请先登录Telegram账号再使用监听功能。",
                QMessageBox.Ok
            )

    def _connect_monitor_signals(self):
        """连接监听器信号"""
        if not self.monitor:
            return

        # 连接信号到槽函数
        self.monitor.monitor_started.connect(self._on_monitor_started)
        self.monitor.monitor_message_received.connect(self._on_message_received)
        self.monitor.monitor_message_forwarded.connect(self._on_message_forwarded)
        self.monitor.monitor_stopped.connect(self._on_monitor_stopped)
        self.monitor.monitor_error.connect(self._on_monitor_error)

    def _on_monitor_started(self, task_id):
        """监听开始处理函数"""
        self.current_task_id = task_id
        # 更新UI状态
        self.status_label.setText(f"监听任务 {task_id} 已开始")
        self.start_button.setText("停止监听")
        self.start_button.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        # 添加日志
        self._add_log_entry(f"开始监听", "info")

    def _on_message_received(self, task_id, channel, msg_id):
        """消息接收处理函数"""
        # 更新UI状态
        self.status_label.setText(f"收到新消息: 来自 {channel}, 消息ID: {msg_id}")
        # 添加日志
        self._add_log_entry(f"收到消息: {channel} [ID: {msg_id}]", "received")

    def _on_message_forwarded(self, task_id, source, msg_id, targets):
        """消息转发处理函数"""
        targets_str = ", ".join(targets)
        # 更新UI状态
        self.status_label.setText(f"已转发消息: 从 {source} 到 {targets_str}")
        # 添加日志
        self._add_log_entry(f"转发成功: {source} [ID: {msg_id}] → {targets_str}", "forwarded")

    def _on_monitor_stopped(self, task_id, success, reason):
        """监听停止处理函数"""
        self.current_task_id = None
        # 更新UI状态
        if success:
            status_text = f"监听任务 {task_id} 已完成: {reason}"
            self._add_log_entry(f"监听完成: {reason}", "info")
        else:
            status_text = f"监听任务 {task_id} 已停止: {reason}"
            self._add_log_entry(f"监听停止: {reason}", "warning")

        self.status_label.setText(status_text)
        self.start_button.setText("开始监听")
        self.start_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        # 启用控件
        self.enable_controls(True)

    def _on_monitor_error(self, task_id, error):
        """监听错误处理函数"""
        # 显示错误消息
        QMessageBox.critical(
            self,
            "监听错误",
            f"监听任务 {task_id} 出错: {error}",
            QMessageBox.Ok
        )
        # 添加日志
        self._add_log_entry(f"监听错误: {error}", "error")
        # 更新UI状态
        self.status_label.setText(f"监听出错: {error}")
        self.start_button.setText("开始监听")
        self.start_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        # 启用控件
        self.enable_controls(True)
        self.current_task_id = None

    def start_or_stop_monitor(self):
        """开始或停止监听"""
        # 如果已经在监听，则停止
        if self.current_task_id:
            self._stop_monitor()
            return

        # 否则开始新的监听
        self._start_monitor()

    def _start_monitor(self):
        """开始监听"""
        if not self.monitor:
            self._initialize_monitor()
            if not self.monitor:
                return

        # 禁用设置控件，防止重复操作
        self.enable_controls(False, keep_start_button=True)

        try:
            # 收集监听设置
            settings = self._collect_monitor_settings()

            # 创建任务ID
            task_id = f"monitor_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # 使用asyncio.create_task启动异步监听
            asyncio.create_task(self._async_monitor(task_id, settings))

        except Exception as e:
            logger.error(f"启动监听任务失败: {e}")
            QMessageBox.critical(
                self,
                "启动失败",
                f"启动监听任务失败: {str(e)}",
                QMessageBox.Ok
            )
            self.enable_controls(True)

    def _stop_monitor(self):
        """停止监听"""
        if not self.current_task_id:
            return

        try:
            # 调用监听器的停止方法
            if self.monitor:
                self.monitor.stop(self.current_task_id, "用户手动停止")
                self.status_label.setText("正在停止监听...")
        except Exception as e:
            logger.error(f"停止监听任务失败: {e}")
            QMessageBox.critical(
                self,
                "停止失败",
                f"停止监听任务失败: {str(e)}",
                QMessageBox.Ok
            )

    async def _async_monitor(self, task_id, settings):
        """异步执行监听任务"""
        try:
            # 执行监听
            await self.monitor.start_monitoring(**settings, task_id=task_id)
        except Exception as e:
            logger.error(f"监听任务执行失败: {e}")
            # 使用Qt信号处理UI更新
            QApplication.instance().postEvent(
                self,
                MonitorErrorEvent(task_id, str(e))
            )
```

#### 步骤 3: 创建自定义事件类型，用于在异步上下文中更新 UI

```python
class MonitorErrorEvent(QEvent):
    """监听错误事件"""

    EVENT_TYPE = QEvent.Type(QEvent.registerEventType())

    def __init__(self, task_id, error_message):
        super().__init__(self.EVENT_TYPE)
        self.task_id = task_id
        self.error_message = error_message
```

#### 步骤 4: 实现事件处理方法

```python
class ListenView(QWidget):
    # ... 现有代码 ...

    def event(self, event):
        """处理自定义事件"""
        if event.type() == MonitorErrorEvent.EVENT_TYPE:
            self._on_monitor_error(event.task_id, event.error_message)
            return True
        return super().event(event)
```

### 9.4 监听设置读取与保存

```python
def _collect_monitor_settings(self):
    """收集监听设置"""
    settings = {}

    # 获取监听频道对
    channel_pairs = []
    for row in range(self.channel_pairs_table.rowCount()):
        source = self.channel_pairs_table.item(row, 0).text()
        targets_str = self.channel_pairs_table.item(row, 1).text()

        if source and targets_str:
            targets = [t.strip() for t in targets_str.split(',')]
            remove_captions = False

            # 检查是否有移除描述选项
            if row < self.channel_pairs_table.rowCount() and self.channel_pairs_table.cellWidget(row, 2):
                remove_captions_check = self.channel_pairs_table.cellWidget(row, 2).findChild(QCheckBox)
                if remove_captions_check:
                    remove_captions = remove_captions_check.isChecked()

            # 获取文本替换规则
            text_filter = []
            # 这里需要实现从文本替换表格中获取规则的代码
            # ...

            channel_pairs.append({
                "source_channel": source,
                "target_channels": targets,
                "remove_captions": remove_captions,
                "text_filter": text_filter
            })

    if not channel_pairs:
        raise ValueError("请至少添加一个监听频道对")

    settings["channel_pairs"] = channel_pairs

    # 获取媒体类型
    media_types = []
    if self.photo_check.isChecked():
        media_types.append("photo")
    if self.video_check.isChecked():
        media_types.append("video")
    if self.document_check.isChecked():
        media_types.append("document")
    if self.audio_check.isChecked():
        media_types.append("audio")
    if self.animation_check.isChecked():
        media_types.append("animation")

    if not media_types:
        raise ValueError("请至少选择一种媒体类型")

    settings["media_types"] = media_types

    # 获取监听时长
    if self.duration_combo.currentIndex() > 0:  # 不是"无限制"
        hours = self.hours_spin.value()
        minutes = self.minutes_spin.value()
        if hours > 0 or minutes > 0:
            settings["duration"] = f"{hours}h{minutes}m"
    else:
        settings["duration"] = None

    # 获取转发延迟
    settings["forward_delay"] = self.delay_spin.value()

    return settings
```

## 十、命令行代码移除方案

### 10.1 移除策略

完成 UI 界面的全部功能集成后，我们将按照以下策略移除命令行程序代码：

1. 保留所有核心逻辑和功能模块（如 `downloader.py`, `uploader.py`, `forwarder.py`, `monitor.py` 等）
2. 保留所有辅助工具类和函数（如 `utils` 目录下的各个工具类）
3. 移除命令行参数解析和入口函数
4. 移除命令行特有的配置管理和命令行界面代码

### 10.2 需要移除的文件

以下文件将被完全移除：

1. `run.py`：命令行程序的入口点
2. `src/utils/config_manager.py`：命令行配置管理器
3. `src/cli/*`：命令行界面相关代码
4. 其他仅用于命令行程序的文件

### 10.3 需要保留但修改的文件

以下文件将被保留但需要修改：

1. `src/modules/*.py`：修改为仅依赖 `ui_config_manager.py`，删除对 `config_manager.py` 的引用
2. `src/utils/task_manager.py`：修改为支持 QtAsyncio 和 UI 界面集成
3. `src/utils/resource_manager.py`：更新资源管理逻辑，确保与 UI 界面兼容

### 10.4 实施步骤

#### 步骤 1: 确认 UI 功能完整性

在开始移除命令行代码前，确保所有功能已完全集成到 UI 界面，并通过全面测试：

- 所有模块功能正常工作
- 所有界面操作可以成功完成
- 所有异步操作能够与 UI 正确集成
- 错误处理和异常情况已测试

#### 步骤 2: 创建代码备份

```bash
# 创建备份目录
mkdir -p backups/$(date +%Y%m%d)

# 复制当前代码到备份目录
cp -r src run.py config.json backups/$(date +%Y%m%d)/
```

#### 步骤 3: 移除命令行程序入口

```bash
# 移动run.py到备份目录(如果之前没有备份)
mv run.py backups/$(date +%Y%m%d)/

# 或者直接删除
rm run.py
```

#### 步骤 4: 移除 config_manager.py

```bash
# 移动config_manager.py到备份目录
mv src/utils/config_manager.py backups/$(date +%Y%m%d)/

# 或者直接删除
rm src/utils/config_manager.py
```

#### 步骤 5: 移除其他命令行特有文件

```bash
# 如果存在CLI目录，移动到备份或删除
if [ -d "src/cli" ]; then
    mkdir -p backups/$(date +%Y%m%d)/src/
    mv src/cli backups/$(date +%Y%m%d)/src/
    # 或者直接删除
    # rm -rf src/cli
fi
```

#### 步骤 6: 更新 README.md

修改项目 README.md，移除命令行用法说明，更新为 UI 界面的使用指南：

````markdown
# TG-Manager

TG-Manager 是一个用于管理 Telegram 消息的图形界面工具，提供下载、上传、转发和监听等功能。

## 安装

```bash
pip install -r requirements.txt
```
````

## 启动方式

```bash
python run_ui.py
```

## 使用方法

1. 启动应用程序后，首先在设置中配置 API 凭据和手机号码
2. 通过"登录"按钮登录到 Telegram 账号
3. 使用各功能模块（下载、上传、转发、监听）进行操作

## 功能模块

### 下载模块

...

### 上传模块

...

### 转发模块

...

### 监听模块

...

```

### 10.5 项目结构调整

完成命令行代码删除后，项目的最终结构应如下：

```

TG-Manager/
├── run_ui.py # UI 程序入口点
├── config.json # 配置文件
├── README.md # 项目说明文档
├── requirements.txt # 依赖包列表
├── src/
│ ├── modules/ # 功能模块
│ │ ├── downloader.py # 下载模块
│ │ ├── uploader.py # 上传模块
│ │ ├── forwarder.py # 转发模块
│ │ └── monitor.py # 监听模块
│ ├── ui/ # UI 界面
│ │ ├── app.py # 应用程序类
│ │ ├── resources/ # UI 资源文件
│ │ └── views/ # UI 视图
│ │ ├── main_window.py # 主窗口
│ │ ├── download_view.py # 下载视图
│ │ ├── upload_view.py # 上传视图
│ │ ├── forward_view.py # 转发视图
│ │ ├── listen_view.py # 监听视图
│ │ └── settings_view.py # 设置视图
│ └── utils/ # 工具类
│ ├── ui_config_manager.py # UI 配置管理器
│ ├── ui_config_models.py # UI 配置模型
│ ├── client_manager.py # 客户端管理器
│ ├── task_manager.py # 任务管理器
│ ├── logger.py # 日志工具
│ ├── error_handler.py # 错误处理器
│ └── resource_manager.py # 资源管理器
├── logs/ # 日志目录
├── downloads/ # 下载目录
├── uploads/ # 上传目录
└── tmp/ # 临时文件目录

```

以上结构确保项目完全面向UI界面，同时保留了所有核心功能模块。
```
