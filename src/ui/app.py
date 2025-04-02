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

from src.utils.logger import get_logger
from src.utils.config_manager import ConfigManager
from src.utils.theme_manager import get_theme_manager

# 导入主窗口
from src.ui.views.main_window import MainWindow


logger = get_logger()


class TGManagerApp(QObject):
    """TG-Manager 应用程序主类"""
    
    # 信号定义
    config_loaded = Signal(dict)
    config_saved = Signal()
    app_closing = Signal()
    theme_changed = Signal(str)  # 新增：主题变更信号
    
    def __init__(self, verbose=False):
        super().__init__()
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("TG-Manager")
        self.app.setOrganizationName("TG-Manager")
        self.app.setOrganizationDomain("tg-manager.org")
        self.verbose = verbose
        
        if self.verbose:
            logger.debug("初始化应用程序，应用样式...")
        
        # 初始化主题管理器
        self.theme_manager = get_theme_manager()
        self.theme_manager.initialize(self.app)
        
        # 初始化配置管理器
        self.config_manager = ConfigManager()
        self.config = {}
        
        # 设置事件循环
        self.event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.event_loop)
        
        # 加载配置
        self.load_config()
        
        # 应用主题
        self._apply_theme_from_config()
        
        # 初始化主窗口
        self.main_window = MainWindow(self.config)
        self.main_window.config_saved.connect(self._on_config_saved)
        self.main_window.show()
        
        # 设置退出处理
        self.app.aboutToQuit.connect(self.cleanup)
        signal.signal(signal.SIGINT, lambda sig, frame: self.cleanup())
        
        # 连接主题变更信号
        self.theme_changed.connect(self._on_theme_changed)
    
    def _apply_theme_from_config(self):
        """从配置中应用主题设置"""
        if not self.config:
            return
        
        ui_config = self.config.get('UI', {})
        
        # 获取主题名称
        theme_name = ui_config.get('theme', '深色主题')
        logger.debug(f"从配置中加载主题: {theme_name}")
        
        # 应用主题
        theme_manager = self.theme_manager
        if theme_manager.apply_theme(theme_name):
            logger.debug(f"成功应用主题 '{theme_name}'")
        else:
            logger.warning(f"应用主题 '{theme_name}' 失败")
    
    def load_config(self):
        """读取配置文件"""
        try:
            # 通过配置管理器加载各组件配置
            if self.config_manager:
                # 创建一个空配置字典
                self.config = {}
                
                # 加载各部分配置
                self.config['GENERAL'] = self.config_manager.get_general_config().dict()
                self.config['DOWNLOAD'] = self.config_manager.get_download_config().dict()
                self.config['UPLOAD'] = self.config_manager.get_upload_config().dict()
                self.config['FORWARD'] = self.config_manager.get_forward_config().dict()
                self.config['MONITOR'] = self.config_manager.get_monitor_config().dict()
                
                # 处理下载配置中的嵌套对象
                download_settings = []
                for item in self.config_manager.get_download_config().downloadSetting:
                    download_settings.append(item.dict())
                self.config["DOWNLOAD"]["downloadSetting"] = download_settings
                
                # 处理转发配置中的嵌套对象
                forward_pairs = []
                for pair in self.config_manager.get_forward_config().forward_channel_pairs:
                    forward_pairs.append(pair.dict())
                self.config["FORWARD"]["forward_channel_pairs"] = forward_pairs
                
                # 处理监听配置中的嵌套对象
                monitor_pairs = []
                for pair in self.config_manager.get_monitor_config().monitor_channel_pairs:
                    pair_dict = pair.dict()
                    # 处理文本过滤器
                    text_filters = []
                    for filter_item in pair.text_filter:
                        text_filters.append(filter_item.dict())
                    pair_dict["text_filter"] = text_filters
                    monitor_pairs.append(pair_dict)
                self.config["MONITOR"]["monitor_channel_pairs"] = monitor_pairs
                
                # 加载UI配置，这部分直接从配置文件读取
                try:
                    with open(self.config_manager.config_path, 'r', encoding='utf-8') as f:
                        file_config = json.load(f)
                        if 'UI' in file_config:
                            self.config['UI'] = file_config['UI']
                        else:
                            # 创建默认UI配置
                            self.config['UI'] = {
                                'theme': "深色主题",
                                'confirm_exit': True,
                                'minimize_to_tray': True,
                                'start_minimized': False,
                                'enable_notifications': True,
                                'notification_sound': True
                            }
                except Exception as e:
                    logger.warning(f"加载UI配置失败: {e}，使用默认配置")
                    self.config['UI'] = {
                        'theme': "深色主题",
                        'confirm_exit': True,
                        'minimize_to_tray': True,
                        'start_minimized': False,
                        'enable_notifications': True,
                        'notification_sound': True
                    }
                
                logger.info("已加载配置文件")
                
                # 注意：仅在初始化时应用主题，在其他情况下不要再次应用
                # 这里不再调用 self._apply_theme_from_config()
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            self.config = {}  # 设置为空字典作为默认配置
    
    def save_config(self):
        """
        保存应用程序配置到文件
        """
        try:
            # 读取配置文件
            with open(self.config_manager.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 确保UI部分和主题设置存在
            if 'UI' not in config:
                config['UI'] = {
                    'theme': self.theme_manager.get_current_theme_name(),
                    'confirm_exit': True,
                    'minimize_to_tray': True,
                    'start_minimized': False,
                    'enable_notifications': True,
                    'notification_sound': True
                }
                logger.warning("配置中缺少UI部分，已创建默认UI配置")
            
            # 如果主题设置缺失，添加当前主题
            if 'theme' not in config['UI']:
                config['UI']['theme'] = self.theme_manager.get_current_theme_name()
                logger.warning("配置中缺少theme属性，已添加当前主题")
            
            # 保存配置到文件
            with open(self.config_manager.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            current_theme = config['UI'].get('theme', "深色主题")
            logger.info(f"已保存配置文件，主题: {current_theme}")
            
            return config
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            return {}
    
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

    def _on_config_saved(self):
        """处理配置保存信号"""
        # 判断是否是设置界面发出的信号，是否应该应用主题
        # 如果是主窗口的窗口状态变化触发的保存，则不要重新应用主题
        ui_config = self.config.get('UI', {})
        saved_theme = ui_config.get('theme', '')
        current_theme = self.theme_manager.get_current_theme_name()
        
        # 保存窗口状态到配置
        if hasattr(self.main_window, 'window_state_changed'):
            # 注意：这里主动获取当前窗口状态，确保工具栏状态也被保存
            window_state = {
                'geometry': self.main_window.saveGeometry(),
                'state': self.main_window.saveState()
            }
            
            # 更新配置
            if 'UI' not in self.config:
                self.config['UI'] = {}
            
            ui_config = self.config['UI'] 
            ui_config['window_geometry'] = window_state['geometry'].toBase64().data().decode()
            ui_config['window_state'] = window_state['state'].toBase64().data().decode()
            self.config['UI'] = ui_config
        
        # 只有当主题发生变化时才应用新主题
        if saved_theme and saved_theme != current_theme:
            logger.info(f"设置中主题发生变化，从 '{current_theme}' 变更为 '{saved_theme}'")
            self.theme_changed.emit(saved_theme)
        
        # 保存配置到文件
        self.save_config()
        
        # 发送配置保存信号
        self.config_saved.emit()
    
    def _on_theme_changed(self, theme_name):
        """主题变更处理
        
        Args:
            theme_name: 新主题名称
        """
        # 获取当前主题
        current_theme = self.theme_manager.get_current_theme_name()
        
        # 只有当新主题与当前主题不同时才应用
        if theme_name != current_theme:
            logger.info(f"正在切换主题: 从 {current_theme} 到 {theme_name}")
            
            # 应用主题
            self.theme_manager.apply_theme(theme_name)
            
            # 更新配置中的主题设置
            if 'UI' in self.config:
                self.config['UI']['theme'] = theme_name
            else:
                self.config['UI'] = {'theme': theme_name}
        else:
            logger.debug(f"忽略主题变更请求，当前已是 {theme_name} 主题")


def main():
    """应用程序入口函数"""
    app = TGManagerApp()
    sys.exit(app.run())


if __name__ == "__main__":
    main() 