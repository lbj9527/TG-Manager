"""
TG-Manager 主应用程序
负责初始化应用程序、加载配置和管理主界面
"""

import sys
import json
import asyncio
import signal
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject, Signal, QSettings
from qt_material import apply_stylesheet

from src.utils.logger import get_logger
from src.utils.config_manager import ConfigManager

# 导入主窗口
from src.ui.views.main_window import MainWindow


logger = get_logger()


class TGManagerApp(QObject):
    """TG-Manager 应用程序主类"""
    
    # 信号定义
    config_loaded = Signal(dict)
    config_saved = Signal()
    app_closing = Signal()
    
    def __init__(self, verbose=False):
        super().__init__()
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("TG-Manager")
        self.app.setOrganizationName("TG-Manager")
        self.app.setOrganizationDomain("tg-manager.org")
        self.verbose = verbose
        
        if self.verbose:
            logger.debug("初始化应用程序，应用样式...")
        
        # 设置应用样式
        apply_stylesheet(self.app, theme='dark_teal.xml')
        
        if self.verbose:
            logger.debug("已应用基础样式表: dark_teal.xml")
        
        # 修复深色主题下文本框文字颜色问题
        extra_styles = """
        QLineEdit {
            color: #FFFFFF;
        }
        QSpinBox, QDoubleSpinBox {
            color: #FFFFFF;
        }
        QComboBox {
            color: #FFFFFF;
        }
        QTextEdit, QPlainTextEdit {
            color: #FFFFFF;
        }
        """
        self.app.setStyleSheet(self.app.styleSheet() + extra_styles)
        
        if self.verbose:
            logger.debug("已应用额外的样式表修复：输入控件文本颜色")
            logger.debug(f"额外样式内容：\n{extra_styles}")
        
        # 初始化配置管理器
        self.config_manager = ConfigManager()
        self.config = {}
        
        # 设置事件循环
        self.event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.event_loop)
        
        # 加载配置
        self.load_config()
        
        # 初始化主窗口
        self.main_window = MainWindow(self.config)
        self.main_window.config_saved.connect(self._on_config_saved)
        self.main_window.show()
        
        # 设置退出处理
        self.app.aboutToQuit.connect(self.cleanup)
        signal.signal(signal.SIGINT, lambda sig, frame: self.cleanup())
    
    def load_config(self):
        """加载应用程序配置"""
        try:
            # 从配置管理器获取各配置部分，组合成完整配置
            config = {
                "GENERAL": vars(self.config_manager.get_general_config()),
                "DOWNLOAD": vars(self.config_manager.get_download_config()),
                "UPLOAD": vars(self.config_manager.get_upload_config()),
                "FORWARD": vars(self.config_manager.get_forward_config()),
                "MONITOR": vars(self.config_manager.get_monitor_config())
            }
            
            # 处理嵌套模型
            # 处理下载配置中的嵌套列表
            download_settings = []
            for item in self.config_manager.get_download_config().downloadSetting:
                download_settings.append(vars(item))
            config["DOWNLOAD"]["downloadSetting"] = download_settings
            
            # 处理转发配置中的嵌套列表
            forward_pairs = []
            for pair in self.config_manager.get_forward_config().forward_channel_pairs:
                forward_pairs.append(vars(pair))
            config["FORWARD"]["forward_channel_pairs"] = forward_pairs
            
            # 处理监听配置中的嵌套列表
            monitor_pairs = []
            for pair in self.config_manager.get_monitor_config().monitor_channel_pairs:
                pair_dict = vars(pair)
                # 处理文本过滤器
                text_filters = []
                for filter_item in pair.text_filter:
                    text_filters.append(vars(filter_item))
                pair_dict["text_filter"] = text_filters
                monitor_pairs.append(pair_dict)
            config["MONITOR"]["monitor_channel_pairs"] = monitor_pairs
            
            self.config = config
            logger.info("已加载配置文件")
            self.config_loaded.emit(self.config)
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
    
    def save_config(self):
        """保存应用程序配置"""
        try:
            # 将当前配置保存到文件
            config_path = Path("config.json")
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            
            logger.info("已保存配置文件")
            self.config_saved.emit()
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
    
    def update_config(self, section, key, value):
        """更新配置项
        
        Args:
            section: 配置部分名称 (GENERAL, DOWNLOAD 等)
            key: 配置项键名
            value: 配置项值
        """
        if section in self.config:
            self.config[section][key] = value
        else:
            self.config[section] = {key: value}
    
    def get_config(self, section=None, key=None):
        """获取配置项
        
        Args:
            section: 配置部分名称，如果为None则返回整个配置
            key: 配置项键名，如果为None则返回整个部分
            
        Returns:
            请求的配置项值
        """
        if section is None:
            return self.config
        
        if section not in self.config:
            return None
            
        if key is None:
            return self.config[section]
            
        if key in self.config[section]:
            return self.config[section][key]
            
        return None
    
    def run(self):
        """运行应用程序
        
        Returns:
            int: 应用程序退出代码
        """
        if self.verbose:
            logger.debug("正在启动事件循环")
        
        # 启动应用程序事件循环
        return self.app.exec()
        
    def cleanup(self):
        """清理资源"""
        logger.info("正在关闭应用程序...")
        self.save_config()
        self.app_closing.emit()
        
        # 关闭事件循环
        if self.event_loop and self.event_loop.is_running():
            self.event_loop.stop()

    def _on_config_saved(self, config):
        """配置保存处理
        
        Args:
            config: 更新后的配置
        """
        self.config = config
        self.save_config()


def main():
    """应用程序入口函数"""
    app = TGManagerApp()
    sys.exit(app.run())


if __name__ == "__main__":
    main() 