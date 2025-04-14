"""
TG-Manager 主应用程序
负责初始化应用程序、加载配置和管理主界面

重构：现在从模块化实现中导入TGManagerApp类
原始代码已被拆分到src/ui/app_core/目录下的多个文件中
"""

# 从重构后的模块化实现中导入 TGManagerApp 类
from src.ui.app_core import TGManagerApp

# 保留原始的main函数，以保持兼容性
def main():
    """应用程序入口函数"""
    app = TGManagerApp()
    import sys
    sys.exit(app.run())

if __name__ == "__main__":
    main()

"""
原始的 TGManagerApp 类已被移动到app_core目录中，并被拆分成多个文件：
- src/ui/app_core/app.py: 应用程序主类
- src/ui/app_core/config.py: 配置管理
- src/ui/app_core/async_services.py: 异步服务和组件初始化 
- src/ui/app_core/cleanup.py: 资源清理功能
- src/ui/app_core/theme.py: 主题管理
- src/ui/app_core/client.py: 客户端管理
- src/ui/app_core/first_login.py: 首次登录处理

所有功能保持不变，只是组织结构更加模块化。
""" 