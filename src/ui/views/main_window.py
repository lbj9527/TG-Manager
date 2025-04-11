"""
TG-Manager 主窗口
重构：现在从组件化模块导入 MainWindow 类
原始代码保留在文件底部，作为参考
"""

# 从重构后的组件模块导入 MainWindow 类
from src.ui.components.main_window import MainWindow

# 以下是原始代码的注释，现已不再使用
# 原始代码的 MainWindow 类已替换为上面导入的模块化 MainWindow

"""
原始的 MainWindow 类已被移动到组件模块中，并被拆分成多个文件：
- src/ui/components/main_window/base.py: 基础类
- src/ui/components/main_window/menu_bar.py: 菜单栏功能
- src/ui/components/main_window/toolbar.py: 工具栏功能
- src/ui/components/main_window/status_bar.py: 状态栏功能
- src/ui/components/main_window/sidebar.py: 侧边栏功能
- src/ui/components/main_window/system_tray.py: 系统托盘功能
- src/ui/components/main_window/window_state.py: 窗口状态管理
- src/ui/components/main_window/actions.py: 功能操作

所有功能保持不变，只是组织结构更加模块化。
"""

