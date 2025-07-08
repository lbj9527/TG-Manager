"""
TG-Manager 导航树组件
实现功能导航和功能分类
"""

from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon

from src.utils.logger import get_logger
from src.utils.translation_manager import get_translation_manager, tr

logger = get_logger()


class NavigationItem:
    """导航项目类型定义"""
    
    def __init__(self, name_key, item_id, parent_id=None, item_type='category', data=None):
        """初始化导航项
        
        Args:
            name_key: 导航项显示名称的翻译键
            item_id: 导航项唯一标识
            parent_id: 父导航项ID，如果为None则为顶级项
            item_type: 导航项类型，可以是'category'或'function'
            data: 关联的数据，用于存储额外信息
        """
        self.name_key = name_key
        self.id = item_id
        self.parent_id = parent_id
        self.type = item_type
        self.data = data if data else {}
        self.children = []
    
    @property
    def name(self):
        """获取翻译后的名称"""
        return tr(self.name_key)


class NavigationTree(QWidget):
    """功能导航树组件"""
    
    # 导航项被选中的信号
    item_selected = Signal(str, object)  # item_id, item_data
    
    def __init__(self, parent=None):
        """初始化导航树
        
        Args:
            parent: 父窗口部件
        """
        super().__init__(parent)
        
        # 获取翻译管理器
        self.translation_manager = get_translation_manager()
        self.translation_manager.language_changed.connect(self._update_translations)
        
        # 创建布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建树控件
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setExpandsOnDoubleClick(True)
        self.tree.setAnimated(True)
        
        # 连接信号
        self.tree.itemClicked.connect(self._on_item_clicked)
        
        layout.addWidget(self.tree)
        
        # 导航项列表
        self._nav_items = {}
        
        # 初始化导航结构
        self._init_navigation()
    
    def _init_navigation(self):
        """初始化导航结构"""
        # 定义导航项（使用翻译键）
        nav_items = [
            # 媒体下载分类
            NavigationItem("ui.tabs.download", "download_category", None, "category"),
            NavigationItem("ui.navigation.media_download", "normal_download", "download_category", "function", {
                "function": "download",
                "description": "从频道批量下载媒体文件"
            }),
            
            # 媒体上传分类
            NavigationItem("ui.tabs.upload", "upload_category", None, "category"),
            NavigationItem("ui.navigation.local_upload", "local_upload", "upload_category", "function", {
                "function": "upload",
                "description": "将本地媒体文件上传到频道"
            }),
            
            # 消息转发分类
            NavigationItem("ui.tabs.forward", "forward_category", None, "category"),
            NavigationItem("ui.navigation.history_forward", "history_forward", "forward_category", "function", {
                "function": "forward",
                "description": "转发频道历史消息"
            }),
            
            # 消息监听分类
            NavigationItem("ui.tabs.monitor", "monitor_category", None, "category"),
            NavigationItem("ui.navigation.real_time_monitor", "real_time_monitor", "monitor_category", "function", {
                "function": "monitor",
                "description": "监听频道实时消息并转发"
            }),
            
            # 开发工具分类
            NavigationItem("ui.menu.tools", "dev_tools_category", None, "category"),
        ]
        
        # 构建导航项字典和树形结构
        for item in nav_items:
            self._nav_items[item.id] = item
            if item.parent_id is not None and item.parent_id in self._nav_items:
                parent = self._nav_items[item.parent_id]
                parent.children.append(item)
        
        # 构建树控件项目
        self._build_tree_items()
    
    def _update_translations(self):
        """更新翻译，保持当前的展开状态和选择状态"""
        # 保存当前的展开状态
        expanded_items = {}
        current_item = self.tree.currentItem()
        current_item_id = None
        
        if current_item:
            current_item_id = current_item.data(0, Qt.UserRole)
        
        # 遍历所有项目保存展开状态
        def save_expanded_state(item, item_dict):
            if item:
                item_id = item.data(0, Qt.UserRole)
                if item_id:
                    item_dict[item_id] = item.isExpanded()
                for i in range(item.childCount()):
                    save_expanded_state(item.child(i), item_dict)
        
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            save_expanded_state(root.child(i), expanded_items)
        
        # 重新构建树项目
        self._build_tree_items()
        
        # 恢复展开状态
        def restore_expanded_state(item, item_dict):
            if item:
                item_id = item.data(0, Qt.UserRole)
                if item_id and item_id in item_dict:
                    item.setExpanded(item_dict[item_id])
                for i in range(item.childCount()):
                    restore_expanded_state(item.child(i), item_dict)
        
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            restore_expanded_state(root.child(i), expanded_items)
        
        # 恢复选择状态
        if current_item_id:
            self._select_item_silently(current_item_id)
        
        logger.debug("导航树翻译已更新")
    
    def _build_tree_items(self):
        """构建树控件项目"""
        self.tree.clear()
        
        # 仅获取顶级项目
        root_items = [item for item in self._nav_items.values() if item.parent_id is None]
        
        # 递归构建树
        for item in root_items:
            tree_item = self._create_tree_item(item)
            self.tree.addTopLevelItem(tree_item)
            
            # 如果是分类，默认展开
            if item.type == 'category':
                tree_item.setExpanded(True)
    
    def _create_tree_item(self, nav_item):
        """创建树控件项目
        
        Args:
            nav_item: NavigationItem实例
            
        Returns:
            QTreeWidgetItem实例
        """
        tree_item = QTreeWidgetItem([nav_item.name])
        tree_item.setData(0, Qt.UserRole, nav_item.id)
        
        # 设置图标和字体样式，区分分类和功能
        if nav_item.type == 'category':
            # 加粗分类标题
            font = tree_item.font(0)
            font.setBold(True)
            tree_item.setFont(0, font)
        else:
            # 为功能项添加缩进
            tree_item.setData(0, Qt.DisplayRole, f"  {nav_item.name}")
        
        # 添加子项目
        for child in nav_item.children:
            child_item = self._create_tree_item(child)
            tree_item.addChild(child_item)
        
        return tree_item
    
    def _on_item_clicked(self, item, column):
        """树项目点击处理
        
        Args:
            item: 被点击的QTreeWidgetItem
            column: 被点击的列索引
        """
        item_id = item.data(0, Qt.UserRole)
        if item_id in self._nav_items:
            nav_item = self._nav_items[item_id]
            
            # 只有功能项才发出信号
            if nav_item.type == 'function':
                logger.debug(f"导航项被选中: {nav_item.name} (ID: {nav_item.id})")
                self.item_selected.emit(nav_item.id, nav_item.data)
    
    def select_item(self, item_id):
        """根据ID选择导航项
        
        Args:
            item_id: 要选择的导航项ID
            
        Returns:
            bool: 是否成功选择
        """
        return self._select_item_internal(item_id, emit_signal=True)
    
    def _select_item_silently(self, item_id):
        """根据ID静默选择导航项（不触发信号）
        
        Args:
            item_id: 要选择的导航项ID
            
        Returns:
            bool: 是否成功选择
        """
        return self._select_item_internal(item_id, emit_signal=False)
    
    def _select_item_internal(self, item_id, emit_signal=True):
        """内部选择导航项的实现
        
        Args:
            item_id: 要选择的导航项ID
            emit_signal: 是否触发信号
            
        Returns:
            bool: 是否成功选择
        """
        # 查找并选择指定ID的导航项
        items = self.tree.findItems(
            "", 
            Qt.MatchContains | Qt.MatchRecursive,
            0
        )
        
        for item in items:
            if item.data(0, Qt.UserRole) == item_id:
                # 展开父项
                parent = item.parent()
                while parent:
                    parent.setExpanded(True)
                    parent = parent.parent()
                
                # 选择项目
                self.tree.setCurrentItem(item)
                
                # 根据参数决定是否触发点击事件
                if emit_signal and item_id in self._nav_items:
                    nav_item = self._nav_items[item_id]
                    if nav_item.type == 'function':
                        self.item_selected.emit(nav_item.id, nav_item.data)
                
                return True
        
        return False
        
    def select_item_by_function(self, function_name):
        """根据功能名称选择导航项
        
        Args:
            function_name: 要选择的功能名称，如"download"、"upload"、"settings"等
            
        Returns:
            bool: 是否成功选择
        """
        # 查找包含指定功能名称的导航项
        for item_id, nav_item in self._nav_items.items():
            if nav_item.type == 'function' and nav_item.data.get('function') == function_name:
                return self.select_item(item_id)
                
        # 根据部分名称匹配处理特殊情况
        function_mappings = {
            "listen": "monitor",      # 监听菜单项对应monitor功能
        }
        
        if function_name in function_mappings:
            mapped_function = function_mappings[function_name]
            for item_id, nav_item in self._nav_items.items():
                if nav_item.type == 'function' and nav_item.data.get('function') == mapped_function:
                    return self.select_item(item_id)
        
        return False 