"""
TG-Manager 应用程序核心组件
这是 app.py 的模块化重构版本
"""

# 从TGManagerApp类自身导入主类
from src.ui.app_core.app import TGManagerApp

# 构建应用程序所需的所有模块都在各个文件中实现
# 以下是模块结构：
# - src/ui/app_core/app.py: TGManagerApp主类
# - src/ui/app_core/config.py: 配置管理
# - src/ui/app_core/async_services.py: 异步服务和组件初始化
# - src/ui/app_core/network.py: 网络连接检查功能
# - src/ui/app_core/cleanup.py: 资源清理功能
# - src/ui/app_core/theme.py: 主题管理
# - src/ui/app_core/client.py: 客户端管理
# - src/ui/app_core/first_login.py: 首次登录处理 