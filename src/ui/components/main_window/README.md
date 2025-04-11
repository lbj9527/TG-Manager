# TG-Manager 主窗口组件

这个目录包含 TG-Manager 主窗口的模块化组件，用于替代原来的单文件实现。

## 重构目标

对原来的 `src/ui/views/main_window.py` 文件进行重构，目标是：

1. 提高代码的可维护性
2. 降低单个文件的复杂度
3. 支持更好的功能扩展
4. 保持所有原有功能不变

## 目录结构

```
main_window/
  ├── __init__.py         # 将所有组件集成到一个 MainWindow 类
  ├── base.py             # 基础窗口类，包含基本结构和初始化
  ├── menu_bar.py         # 菜单栏功能
  ├── toolbar.py          # 工具栏功能
  ├── status_bar.py       # 状态栏功能
  ├── sidebar.py          # 侧边栏功能，包括导航树和任务概览
  ├── system_tray.py      # 系统托盘功能
  ├── window_state.py     # 窗口状态管理功能
  ├── actions.py          # 各种菜单和按钮的处理函数
  └── README.md           # 本文档
```

## 使用方法

只需要导入 `MainWindow` 类即可：

```python
from src.ui.components.main_window import MainWindow

# 创建主窗口实例
window = MainWindow(config)
window.show()
```

## 设计模式

本重构采用了混入类（Mixin）模式，将不同功能放在不同的混入类中，然后在 `__init__.py` 中通过多重继承将它们组合起来。

主窗口类的继承顺序为：

```python
class MainWindow(
    MenuBarMixin,
    ToolBarMixin,
    StatusBarMixin,
    SidebarMixin,
    SystemTrayMixin,
    WindowStateMixin,
    ActionsMixin,
    MainWindowBase
):
    # ...
```

## 功能扩展

如果需要添加新功能，可以：

1. 在现有的混入类中添加方法
2. 创建新的混入类，并在 `__init__.py` 中将其加入继承列表
3. 直接在 `MainWindow` 类中添加方法

## 不同组件的职责

- **MainWindowBase**: 基础窗口结构，包括中心部件和欢迎页
- **MenuBarMixin**: 菜单栏创建和各个菜单项的定义
- **ToolBarMixin**: 工具栏创建和工具按钮的定义
- **StatusBarMixin**: 状态栏创建和状态信息更新
- **SidebarMixin**: 侧边栏创建，包括导航树和任务概览
- **SystemTrayMixin**: 系统托盘图标和菜单的创建和管理
- **WindowStateMixin**: 窗口状态（大小、位置、布局）的保存和恢复
- **ActionsMixin**: 各种功能操作，如登录、任务管理、配置导入导出等

## 注意事项

在使用 QAction 时，请注意正确的导入路径：

- QAction 位于`PySide6.QtGui`模块中，而不是`PySide6.QtWidgets`中
- 正确导入示例：`from PySide6.QtGui import QAction`

以下文件中使用了 QAction：

- menu_bar.py
- toolbar.py
- system_tray.py
- actions.py
