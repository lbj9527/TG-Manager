"""
TG-Manager 帮助文档
提供应用程序帮助文档的浏览功能
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, 
    QTextBrowser, QTreeWidget, QTreeWidgetItem, 
    QSplitter, QGroupBox, QPushButton
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QIcon, QDesktopServices

from src.utils.logger import get_logger

logger = get_logger()


class HelpDocView(QWidget):
    """帮助文档视图，提供帮助文档浏览功能"""
    
    def __init__(self, config=None, parent=None):
        """初始化帮助文档视图
        
        Args:
            config: 配置对象
            parent: 父窗口部件
        """
        super().__init__(parent)
        
        self.config = config or {}
        
        # 设置布局
        self.main_layout = QVBoxLayout(self)
        self.setLayout(self.main_layout)
        
        # 创建分割器
        self.splitter = QSplitter(Qt.Horizontal)
        
        # 创建目录树
        self._create_toc_tree()
        
        # 创建内容浏览器
        self._create_content_browser()
        
        # 添加到分割器
        self.splitter.addWidget(self.toc_group)
        self.splitter.addWidget(self.content_browser)
        self.splitter.setSizes([250, 750])  # 默认比例
        
        # 按钮区域
        self._create_buttons()
        
        # 添加到主布局
        self.main_layout.addWidget(self.splitter)
        self.main_layout.addLayout(self.buttons_layout)
        
        # 加载初始文档
        self._load_initial_doc()
        
        logger.info("帮助文档视图初始化完成")
    
    def _create_toc_tree(self):
        """创建目录树"""
        self.toc_group = QGroupBox("目录")
        toc_layout = QVBoxLayout()
        
        self.toc_tree = QTreeWidget()
        self.toc_tree.setHeaderHidden(True)
        self.toc_tree.setColumnCount(1)
        
        # 添加目录项
        self._add_toc_items()
        
        # 连接信号
        self.toc_tree.itemClicked.connect(self._on_toc_item_clicked)
        
        toc_layout.addWidget(self.toc_tree)
        self.toc_group.setLayout(toc_layout)
    
    def _add_toc_items(self):
        """添加目录项"""
        # 根节点
        intro = QTreeWidgetItem(["介绍"])
        self.toc_tree.addTopLevelItem(intro)
        intro.addChild(QTreeWidgetItem(["欢迎使用"]))
        intro.addChild(QTreeWidgetItem(["系统要求"]))
        intro.addChild(QTreeWidgetItem(["版本历史"]))
        
        # 功能模块
        features = QTreeWidgetItem(["功能模块"])
        self.toc_tree.addTopLevelItem(features)
        features.addChild(QTreeWidgetItem(["下载模块"]))
        features.addChild(QTreeWidgetItem(["上传模块"]))
        features.addChild(QTreeWidgetItem(["转发模块"]))
        features.addChild(QTreeWidgetItem(["监听模块"]))
        features.addChild(QTreeWidgetItem(["任务管理"]))
        
        # 配置说明
        config = QTreeWidgetItem(["配置说明"])
        self.toc_tree.addTopLevelItem(config)
        config.addChild(QTreeWidgetItem(["系统设置"]))
        config.addChild(QTreeWidgetItem(["日志设置"]))
        config.addChild(QTreeWidgetItem(["网络设置"]))
        
        # 高级功能
        advanced = QTreeWidgetItem(["高级功能"])
        self.toc_tree.addTopLevelItem(advanced)
        advanced.addChild(QTreeWidgetItem(["自动任务"]))
        advanced.addChild(QTreeWidgetItem(["API扩展"]))
        advanced.addChild(QTreeWidgetItem(["插件系统"]))
        
        # 疑难解答
        troubleshooting = QTreeWidgetItem(["疑难解答"])
        self.toc_tree.addTopLevelItem(troubleshooting)
        troubleshooting.addChild(QTreeWidgetItem(["常见问题"]))
        troubleshooting.addChild(QTreeWidgetItem(["错误代码"]))
        troubleshooting.addChild(QTreeWidgetItem(["联系支持"]))
        
        # 展开所有顶级节点
        for i in range(self.toc_tree.topLevelItemCount()):
            self.toc_tree.topLevelItem(i).setExpanded(True)
    
    def _create_content_browser(self):
        """创建内容浏览器"""
        self.content_browser = QTextBrowser()
        self.content_browser.setOpenExternalLinks(True)
        
        # 设置基本样式
        self.content_browser.setStyleSheet("""
            QTextBrowser {
                background-color: #FFFFFF;
                font-family: "Microsoft YaHei", Arial, sans-serif;
                font-size: 14px;
                line-height: 1.6;
            }
        """)
    
    def _create_buttons(self):
        """创建按钮区域"""
        self.buttons_layout = QHBoxLayout()
        
        # 主页按钮
        self.home_button = QPushButton("首页")
        self.home_button.clicked.connect(self._load_initial_doc)
        
        # 返回按钮
        self.back_button = QPushButton("后退")
        self.back_button.clicked.connect(self.content_browser.backward)
        
        # 前进按钮
        self.forward_button = QPushButton("前进")
        self.forward_button.clicked.connect(self.content_browser.forward)
        
        # 项目网站按钮
        self.website_button = QPushButton("项目网站")
        self.website_button.clicked.connect(self._open_project_website)
        
        # 添加按钮
        self.buttons_layout.addWidget(self.home_button)
        self.buttons_layout.addWidget(self.back_button)
        self.buttons_layout.addWidget(self.forward_button)
        self.buttons_layout.addStretch(1)
        self.buttons_layout.addWidget(self.website_button)
    
    def _load_initial_doc(self):
        """加载初始文档"""
        welcome_html = """
        <html>
        <head>
            <style>
                body {
                    font-family: "Microsoft YaHei", Arial, sans-serif;
                    margin: 20px;
                    color: #333;
                }
                h1 {
                    color: #2196F3;
                    border-bottom: 1px solid #eee;
                    padding-bottom: 10px;
                }
                h2 {
                    color: #0D47A1;
                    margin-top: 20px;
                }
                p {
                    line-height: 1.6;
                }
                .feature {
                    background-color: #f5f5f5;
                    border-left: 4px solid #2196F3;
                    padding: 10px;
                    margin: 15px 0;
                }
            </style>
        </head>
        <body>
            <h1>欢迎使用 TG-Manager</h1>
            
            <p>TG-Manager 是一个功能强大的 Telegram 消息管理工具，支持频道监听、消息转发、媒体下载与上传等功能。</p>
            
            <h2>主要功能</h2>
            
            <div class="feature">
                <strong>媒体下载</strong>: 从 Telegram 频道下载媒体文件，支持多种格式、关键词过滤
            </div>
            
            <div class="feature">
                <strong>媒体上传</strong>: 将本地媒体文件上传到 Telegram 频道，支持批量处理
            </div>
            
            <div class="feature">
                <strong>消息转发</strong>: 在不同频道间智能转发消息和媒体，自动处理权限限制
            </div>
            
            <div class="feature">
                <strong>实时监听</strong>: 监听频道和群组的新消息，支持关键词匹配和自动处理
            </div>
            
            <div class="feature">
                <strong>任务管理</strong>: 支持任务暂停、继续和取消，提供进度追踪
            </div>
            
            <h2>快速开始</h2>
            
            <p>点击左侧目录树，浏览相关功能的详细文档和使用说明。</p>
            
            <p>如需查看完整文档，请访问<a href="https://github.com/yourusername/TG-Manager">项目官网</a>。</p>
        </body>
        </html>
        """
        
        self.content_browser.setHtml(welcome_html)
    
    def _on_toc_item_clicked(self, item, column):
        """目录项点击处理
        
        Args:
            item: 被点击的树项
            column: 被点击的列
        """
        title = item.text(0)
        
        # 根据不同的文档标题加载不同的内容
        if title == "欢迎使用":
            self._load_initial_doc()
            return
            
        # 如果没有实现的文档，显示通用页面
        self._load_generic_doc(title)
    
    def _load_generic_doc(self, title):
        """加载通用文档页面
        
        Args:
            title: 文档标题
        """
        generic_html = f"""
        <html>
        <head>
            <style>
                body {{
                    font-family: "Microsoft YaHei", Arial, sans-serif;
                    margin: 20px;
                    color: #333;
                }}
                h1 {{
                    color: #2196F3;
                    border-bottom: 1px solid #eee;
                    padding-bottom: 10px;
                }}
                .notice {{
                    background-color: #fff8e1;
                    border-left: 4px solid #ffc107;
                    padding: 15px;
                    margin: 20px 0;
                }}
            </style>
        </head>
        <body>
            <h1>{title}</h1>
            
            <div class="notice">
                <p>该文档页面正在建设中，敬请期待。</p>
                <p>您可以通过以下方式获取帮助：</p>
                <ul>
                    <li>查看项目 README 文件了解基本使用方法</li>
                    <li>访问<a href="https://github.com/yourusername/TG-Manager">项目官网</a>获取最新文档</li>
                    <li>提交 Issue 报告问题或请求帮助</li>
                </ul>
            </div>
        </body>
        </html>
        """
        
        self.content_browser.setHtml(generic_html)
    
    def _open_project_website(self):
        """打开项目网站"""
        QDesktopServices.openUrl(QUrl("https://github.com/yourusername/TG-Manager")) 