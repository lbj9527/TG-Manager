"""
TG-Manager 导航树组件
实现功能导航和功能分类
"""

from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon

from src.utils.logger import get_logger

logger = get_logger()


class NavigationItem:
    """导航项目类型定义"""
    
    def __init__(self, name, item_id, parent_id=None, item_type='category', data=None):
        """初始化导航项
        
        Args:
            name: 导航项显示名称
            item_id: 导航项唯一标识
            parent_id: 父导航项ID，如果为None则为顶级项
            item_type: 导航项类型，可以是'category'或'function'
            data: 关联的数据，用于存储额外信息
        """
        self.name = name
        self.id = item_id
        self.parent_id = parent_id
        self.type = item_type
        self.data = data if data else {}
        self.children = []


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
        # 定义导航项
        nav_items = [
            # 媒体下载分类
            NavigationItem("媒体下载", "download_category", None, "category"),
            NavigationItem("普通下载", "normal_download", "download_category", "function", {
                "function": "download",
                "description": "从频道批量下载媒体文件"
            }),
            NavigationItem("关键词下载", "keyword_download", "download_category", "function", {
                "function": "download_keywords",
                "description": "使用关键词筛选下载媒体文件"
            }),
            
            # 媒体上传分类
            NavigationItem("媒体上传", "upload_category", None, "category"),
            NavigationItem("本地上传", "local_upload", "upload_category", "function", {
                "function": "upload",
                "description": "将本地媒体文件上传到频道"
            }),
            
            # 消息转发分类
            NavigationItem("消息转发", "forward_category", None, "category"),
            NavigationItem("历史转发", "history_forward", "forward_category", "function", {
                "function": "forward",
                "description": "转发频道历史消息"
            }),
            
            # 消息监听分类
            NavigationItem("消息监听", "monitor_category", None, "category"),
            NavigationItem("实时监听", "real_time_monitor", "monitor_category", "function", {
                "function": "monitor",
                "description": "监听频道实时消息并转发"
            }),
            
            # 任务管理
            NavigationItem("任务管理", "task_management", None, "function", {
                "function": "task_manager",
                "description": "管理所有任务"
            }),
            
            # 系统设置
            NavigationItem("系统设置", "system_settings", None, "function", {
                "function": "settings",
                "description": "配置系统参数"
            }),
        ]
        
        # 构建导航项字典和树形结构
        for item in nav_items:
            self._nav_items[item.id] = item
            if item.parent_id is not None and item.parent_id in self._nav_items:
                parent = self._nav_items[item.parent_id]
                parent.children.append(item)
        
        # 构建树控件项目
        self._build_tree_items()
    
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
                
                # 触发点击事件
                if item_id in self._nav_items:
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
            "tasks": "task_manager",  # 任务菜单项对应task_manager功能
            "listen": "monitor",      # 监听菜单项对应monitor功能
        }
        
        if function_name in function_mappings:
            mapped_function = function_mappings[function_name]
            for item_id, nav_item in self._nav_items.items():
                if nav_item.type == 'function' and nav_item.data.get('function') == mapped_function:
                    return self.select_item(item_id)
        
        return False 