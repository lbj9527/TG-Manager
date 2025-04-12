"""
TG-Manager 主窗口组件包
将拆分的各个模块组织成一个完整的窗口组件
"""

from .base import MainWindowBase
from .menu_bar import MenuBarMixin
from .toolbar import ToolBarMixin
from .status_bar import StatusBarMixin
from .sidebar import SidebarMixin
from .system_tray import SystemTrayMixin
from .window_state import WindowStateMixin
from .actions import ActionsMixin

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
    """主窗口类
    
    综合各个功能混入类，形成完整的主窗口，处理用户交互
    """
    
    def __init__(self, config=None, app=None):
        """初始化主窗口
        
        Args:
            config: 配置对象
            app: 应用程序实例
        """
        # 初始化基类
        super().__init__(config)
        
        # 保存app实例
        self.app = app
        
        # 创建界面组件
        self._create_menu_bar()
        self._create_tool_bar()
        self._create_status_bar()
        
        # 创建停靠面板，但暂时不添加到窗口
        self._create_navigation_tree()
        self._create_task_overview()
        
        # 创建左侧分割器，管理导航树和任务概览
        self._create_sidebar_splitter()
        
        # 创建系统托盘图标和菜单
        self._create_system_tray()
        
        # 加载窗口状态
        self._load_window_state()
        
        # 连接信号和槽
        self._connect_signals()
        
        # 添加示例任务（仅用于UI布局展示）
        self._add_sample_tasks()
    
    def _connect_signals(self):
        """连接信号和槽"""
        # 窗口状态变化信号
        self.window_state_changed.connect(self._save_window_state)
        
        # 侧边栏导航树信号
        self.nav_tree.item_selected.connect(self._handle_navigation) 