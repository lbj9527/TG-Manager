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
from src.utils.ui_config_manager import UIConfigManager
from src.utils.ui_config_models import UIConfig

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
        
        # 初始化UI配置管理器
        try:
            self.ui_config_manager = UIConfigManager("config.json")
            logger.info("UI配置管理器初始化成功")
        except Exception as e:
            logger.error(f"UI配置管理器初始化失败: {e}")
            # 提供更友好的错误消息
            import traceback
            logger.debug(f"UI配置管理器初始化错误详情:\n{traceback.format_exc()}")
            # 使用默认空配置
            from src.utils.ui_config_models import create_default_config
            self.ui_config_manager = UIConfigManager()
            self.ui_config_manager.ui_config = create_default_config()
            logger.info("已创建默认UI配置")
        
        # 设置事件循环
        self.event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.event_loop)
        
        # 加载配置
        try:
            self.load_config()
            logger.info("已成功加载配置")
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            # 提供更详细的错误跟踪
            import traceback
            logger.debug(f"加载配置错误详情:\n{traceback.format_exc()}")
            # 使用默认空配置
            self.config = {
                'GENERAL': {
                    'api_id': 12345678,  # 占位符
                    'api_hash': '0123456789abcdef0123456789abcdef',  # 占位符
                    'proxy_enabled': False,
                },
                'DOWNLOAD': {},
                'UPLOAD': {},
                'FORWARD': {},
                'MONITOR': {},
                'UI': {
                    'theme': '深色主题',
                    'confirm_exit': True,
                    'minimize_to_tray': True,
                    'start_minimized': False,
                    'enable_notifications': True,
                    'notification_sound': True
                }
            }
            logger.info("已使用默认配置")
        
        # 应用主题
        try:
            self._apply_theme_from_config()
        except Exception as e:
            logger.error(f"应用主题失败: {e}")
            # 使用默认主题
            self.theme_manager.apply_theme("深色主题")
        
        # 初始化主窗口
        try:
            self.main_window = MainWindow(self.config)
            self.main_window.config_saved.connect(self._on_config_saved)
            self.main_window.show()
        except Exception as e:
            logger.error(f"初始化主窗口失败: {e}")
            # 显示错误对话框
            from PySide6.QtWidgets import QMessageBox
            error_box = QMessageBox()
            error_box.setIcon(QMessageBox.Critical)
            error_box.setWindowTitle("初始化错误")
            error_box.setText("应用程序初始化失败，请检查配置文件")
            error_box.setDetailedText(f"错误详情: {e}")
            error_box.exec()
            # 退出应用
            sys.exit(1)
        
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
            # 从UI配置管理器获取配置
            ui_config = self.ui_config_manager.get_ui_config()
            
            # 转换为字典以供界面使用
            self.config = {
                'GENERAL': ui_config.GENERAL.dict(),
                'DOWNLOAD': ui_config.DOWNLOAD.dict(),
                'UPLOAD': ui_config.UPLOAD.dict(),
                'FORWARD': ui_config.FORWARD.dict(),
                'MONITOR': ui_config.MONITOR.dict(),
                'UI': ui_config.UI.dict(),  # 添加UI配置，从Pydantic模型获取
            }
            
            # 处理下载配置中的嵌套对象
            try:
                download_settings = []
                for item in ui_config.DOWNLOAD.downloadSetting:
                    item_dict = item.dict()
                    # 将MediaType枚举转换为字符串值
                    if 'media_types' in item_dict:
                        item_dict['media_types'] = [mt.value for mt in item.media_types]
                    download_settings.append(item_dict)
                self.config["DOWNLOAD"]["downloadSetting"] = download_settings
            except Exception as e:
                logger.error(f"处理下载配置时出错: {e}")
                # 使用默认下载设置
                self.config["DOWNLOAD"]["downloadSetting"] = []
            
            # 处理转发配置中的嵌套对象
            try:
                forward_pairs = []
                for pair in ui_config.FORWARD.forward_channel_pairs:
                    forward_pairs.append(pair.dict())
                self.config["FORWARD"]["forward_channel_pairs"] = forward_pairs
            except Exception as e:
                logger.error(f"处理转发配置时出错: {e}")
                # 使用默认转发设置
                self.config["FORWARD"]["forward_channel_pairs"] = []
            
            # 处理监听配置中的嵌套对象
            try:
                monitor_pairs = []
                for pair in ui_config.MONITOR.monitor_channel_pairs:
                    pair_dict = pair.dict()
                    # 处理文本过滤器
                    text_filters = []
                    for filter_item in pair.text_filter:
                        text_filters.append(filter_item.dict())
                    pair_dict["text_filter"] = text_filters
                    monitor_pairs.append(pair_dict)
                self.config["MONITOR"]["monitor_channel_pairs"] = monitor_pairs
            except Exception as e:
                logger.error(f"处理监听配置时出错: {e}")
                # 使用默认监听设置
                self.config["MONITOR"]["monitor_channel_pairs"] = []
            
            logger.info("已加载配置文件")
            
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            import traceback
            logger.debug(f"加载配置错误详情:\n{traceback.format_exc()}")
            
            # 使用默认配置
            default_config = self.ui_config_manager.ui_config.dict()
            self.config = {
                'GENERAL': default_config.get('GENERAL', {}),
                'DOWNLOAD': default_config.get('DOWNLOAD', {}),
                'UPLOAD': default_config.get('UPLOAD', {}),
                'FORWARD': default_config.get('FORWARD', {}),
                'MONITOR': default_config.get('MONITOR', {}),
                'UI': default_config.get('UI', {})
            }
            logger.info("已使用默认配置")
    
    def save_config(self, save_theme=True):
        """
        保存应用程序配置到文件
        
        Args:
            save_theme: 是否保存主题设置，默认为True
        """
        try:
            # 如果不保存主题设置，临时保存当前主题
            current_theme = None
            if not save_theme and 'UI' in self.config and 'theme' in self.config['UI']:
                current_theme = self.config['UI']['theme']
                logger.debug(f"临时保存当前主题: {current_theme}")
            
            # 使用UI配置管理器更新并保存配置
            self.ui_config_manager.update_from_dict(self.config)
            save_success = self.ui_config_manager.save_config()
            
            # 如果不保存主题设置，恢复原来的主题
            if not save_theme and current_theme:
                # 暂时不改变内存中的配置，仅在下次保存时更新
                with open(self.config_manager.config_path, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                    if current_theme and 'UI' in file_config:
                        file_config['UI']['theme'] = current_theme
                        logger.debug(f"恢复配置文件中的主题: {current_theme}")
                        
                        # 重新保存文件
                        with open(self.config_manager.config_path, 'w', encoding='utf-8') as f:
                            json.dump(file_config, f, ensure_ascii=False, indent=2)
            
            if save_success:
                if save_theme:
                    current_theme = self.config.get('UI', {}).get('theme', "深色主题")
                    logger.info(f"已保存配置文件，主题: {current_theme}")
                else:
                    logger.info("已保存配置文件（不包含主题设置）")
                return self.config
            else:
                logger.error("保存配置文件失败")
                return {}
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            import traceback
            logger.debug(f"保存配置错误详情:\n{traceback.format_exc()}")
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
        
        # 发送应用程序关闭信号
        self.app_closing.emit()
        
        # 关闭事件循环
        if self.event_loop and self.event_loop.is_running():
            self.event_loop.stop()

    def _on_config_saved(self, updated_config=None):
        """处理配置保存信号"""
        try:
            # 如果接收到更新后的配置，先更新内存中的配置
            if isinstance(updated_config, dict):
                logger.debug(f"接收到更新后的配置数据，准备保存")
                
                # 备份当前主题设置（如果有的话）
                current_theme = None
                if 'UI' in self.config and 'theme' in self.config['UI']:
                    current_theme = self.config['UI'].get('theme')
                    logger.debug(f"备份当前主题设置: {current_theme}")
                
                # 更新内存中的配置
                for section, section_data in updated_config.items():
                    self.config[section] = section_data
                
                # 如果更新的配置中没有主题设置但之前有，则恢复
                if current_theme and ('UI' not in updated_config or 'theme' not in updated_config.get('UI', {})):
                    if 'UI' not in self.config:
                        self.config['UI'] = {}
                    logger.debug(f"恢复主题设置: {current_theme}")
                    self.config['UI']['theme'] = current_theme
                
                # 使用UI配置管理器更新和保存
                logger.debug("通过UIConfigManager更新配置")
                try:
                    self.ui_config_manager.update_from_dict(self.config)
                    save_success = self.ui_config_manager.save_config()
                    
                    if save_success:
                        logger.info("配置已通过UIConfigManager成功保存")
                        
                        # 检查主题是否变更
                        ui_config = self.config.get('UI', {})
                        saved_theme = ui_config.get('theme', '')
                        current_theme = self.theme_manager.get_current_theme_name()
                        
                        # 如果主题发生变化，触发主题更改信号
                        if saved_theme and saved_theme != current_theme:
                            logger.info(f"主题发生变化，从 '{current_theme}' 变更为 '{saved_theme}'")
                            self.theme_changed.emit(saved_theme)
                        
                        # 发送配置保存成功信号
                        self.config_saved.emit()
                    else:
                        logger.error("UIConfigManager保存配置失败")
                except Exception as e:
                    logger.error(f"通过UIConfigManager更新配置失败: {e}")
                    import traceback
                    logger.debug(f"保存配置错误详情:\n{traceback.format_exc()}")
                    
                    # 回退到原始保存方法
                    self.save_config(save_theme=True)
                    self.config_saved.emit()
                
                return
            
            # 如果是窗口状态变化，仅保存窗口状态（不保存整个配置）
            if hasattr(self.main_window, 'window_state_changed'):
                try:
                    # 获取当前窗口状态
                    window_state = {
                        'geometry': self.main_window.saveGeometry(),
                        'state': self.main_window.saveState()
                    }
                    
                    # 更新内存中的窗口状态配置
                    if 'UI' not in self.config:
                        self.config['UI'] = {}
                    
                    # 更新内存中的UI配置
                    self.config['UI']['window_geometry'] = window_state['geometry'].toBase64().data().decode()
                    self.config['UI']['window_state'] = window_state['state'].toBase64().data().decode()
                    
                    # 仅保存窗口布局相关的配置项，不修改其他配置
                    try:
                        # 从文件读取当前配置
                        with open(self.config_manager.config_path, 'r', encoding='utf-8') as f:
                            file_config = json.load(f)
                        
                        # 确保UI部分存在
                        if 'UI' not in file_config:
                            file_config['UI'] = {}
                        
                        # 只更新窗口几何信息和状态
                        file_config['UI']['window_geometry'] = self.config['UI']['window_geometry']
                        file_config['UI']['window_state'] = self.config['UI']['window_state']
                        
                        # 保存回文件
                        with open(self.config_manager.config_path, 'w', encoding='utf-8') as f:
                            json.dump(file_config, f, ensure_ascii=False, indent=2)
                        
                        logger.debug("窗口布局状态已单独保存")
                    except Exception as e:
                        logger.error(f"保存窗口布局状态失败: {e}")
                        import traceback
                        logger.debug(f"保存窗口布局状态错误详情:\n{traceback.format_exc()}")
                except Exception as e:
                    logger.error(f"获取窗口状态失败: {e}")
                    import traceback
                    logger.debug(f"获取窗口状态错误详情:\n{traceback.format_exc()}")
                
                return
            
            # 如果是来自设置界面的普通保存请求
            self.save_config(save_theme=True)
            self.config_saved.emit()
            
        except Exception as e:
            logger.error(f"处理配置保存信号失败: {e}")
            import traceback
            logger.debug(f"处理配置保存信号错误详情:\n{traceback.format_exc()}")
    
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