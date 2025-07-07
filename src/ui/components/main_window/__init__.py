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

from src.utils.translation_manager import get_translation_manager
import logging

logger = logging.getLogger(__name__)

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
        
        # 获取翻译管理器
        self.translation_manager = get_translation_manager()
        
        # 创建界面组件
        self._create_menu_bar()
        self._create_tool_bar()
        self._create_status_bar()
        
        # 创建停靠面板，但暂时不添加到窗口
        self._create_navigation_tree()

        
        # 创建左侧侧边栏，包含导航树
        self._create_sidebar_splitter()
        
        # 创建系统托盘图标和菜单
        self._create_system_tray()
        
        # 加载窗口状态
        self._load_window_state()
        
        # 连接信号和槽
        self._connect_signals()
        
        # 设置初始语言
        self._initialize_language()
    
    def _connect_signals(self):
        """连接信号和槽"""
        # 窗口状态变化信号
        self.window_state_changed.connect(self._save_window_state)
        
        # 侧边栏导航树信号
        self.nav_tree.item_selected.connect(self._handle_navigation)
        
        # 连接翻译管理器的语言变更信号
        self.translation_manager.language_changed.connect(self._on_language_changed)
    
    def _initialize_language(self):
        """初始化语言设置"""
        # 从配置中读取语言设置
        if isinstance(self.config, dict) and 'UI' in self.config:
            ui_config = self.config.get('UI', {})
            if isinstance(ui_config, dict):
                language = ui_config.get('language', '中文')
            elif hasattr(ui_config, 'language'):
                language = ui_config.language
            else:
                language = '中文'
        else:
            language = '中文'
        
        # 设置翻译管理器的语言
        self.translation_manager.set_language(language)
    
    def _on_language_changed(self, new_language_code):
        """语言变更时的处理"""
        # 更新所有界面组件的翻译
        self._update_all_translations()
    
    def _update_all_translations(self):
        """更新所有组件的翻译"""
        logger.debug("=== 开始更新所有组件翻译 ===")
        
        # 更新基础窗口的翻译
        self.update_translations()
        
        # 更新菜单栏翻译
        if hasattr(self, '_update_menu_bar_translations'):
            self._update_menu_bar_translations()
        
        # 显式更新工具栏和状态栏翻译
        ToolBarMixin._update_translations(self)
        StatusBarMixin._update_translations(self)
        
        # 更新侧边栏翻译
        if hasattr(self, '_update_sidebar_translations'):
            self._update_sidebar_translations()
        
        # 更新当前打开的视图的翻译
        logger.debug(f"当前打开的视图: {list(self.opened_views.keys())}")
        for view_name, view_widget in self.opened_views.items():
            logger.debug(f"更新视图翻译: {view_name}, 类型: {type(view_widget).__name__}")
            if hasattr(view_widget, '_update_translations'):
                logger.debug(f"调用 {view_name} 的 _update_translations 方法")
                view_widget._update_translations()
            elif hasattr(view_widget, 'update_translations'):
                logger.debug(f"调用 {view_name} 的 update_translations 方法")
                view_widget.update_translations()
            else:
                logger.debug(f"视图 {view_name} 没有翻译更新方法")
        
        logger.debug("=== 所有组件翻译更新完成 ===")
    
    def config_saved(self, config):
        """处理配置保存事件
        
        Args:
            config: 保存的配置
        """
        # 更新内部配置
        self.config = config
        
        # 检查语言是否发生变化
        if isinstance(config, dict) and 'UI' in config:
            ui_config = config.get('UI', {})
            if isinstance(ui_config, dict):
                new_language = ui_config.get('language', '中文')
            elif hasattr(ui_config, 'language'):
                new_language = ui_config.language
            else:
                new_language = '中文'
            
            # 如果语言发生变化，更新翻译管理器
            current_language = self.translation_manager.get_current_language_name()
            if new_language != current_language:
                self.translation_manager.set_language(new_language) 