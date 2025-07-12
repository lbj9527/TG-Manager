"""
TG-Manager 配置管理模块
负责配置的加载、保存和更新
"""

import json
import os
import time
from pathlib import Path
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QObject, Signal
from loguru import logger


class ConfigManager(QObject):
    """配置管理类，处理配置的加载、保存和更新"""
    
    # 信号定义
    config_loaded = Signal(dict)
    config_saved = Signal()
    
    def __init__(self, ui_config_manager):
        """初始化配置管理器
        
        Args:
            ui_config_manager: UI配置管理器实例
        """
        super().__init__()
        self.ui_config_manager = ui_config_manager
        self.config = {}
        self._permission_error_shown = False
        self._last_window_state_save_time = 0
        
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
            
            # 处理监听配置
            try:
                monitor_pairs = []
                for pair in self.config["MONITOR"]["monitor_channel_pairs"]:
                    # 检查pair是否已经是字典格式
                    if isinstance(pair, dict):
                        pair_dict = pair.copy()
                        # 处理文本过滤器
                        text_filters = []
                        text_filter = pair_dict.get("text_filter", [])
                        for filter_item in text_filter:
                            if isinstance(filter_item, dict):
                                text_filters.append(filter_item)
                            elif hasattr(filter_item, 'dict'):
                                text_filters.append(filter_item.dict())
                            else:
                                # 如果是其他格式，尝试转换
                                text_filters.append({
                                    "original_text": getattr(filter_item, 'original_text', ''),
                                    "target_text": getattr(filter_item, 'target_text', '')
                                })
                        pair_dict["text_filter"] = text_filters
                        monitor_pairs.append(pair_dict)
                    elif hasattr(pair, 'dict'):
                        # 如果是模型对象，使用dict()方法
                        pair_dict = pair.dict()
                        # 处理文本过滤器
                        text_filters = []
                        for filter_item in pair.text_filter:
                            text_filters.append(filter_item.dict())
                        pair_dict["text_filter"] = text_filters
                        monitor_pairs.append(pair_dict)
                    else:
                        logger.warning(f"未知的监听频道对格式: {type(pair)}")
                
                self.config["MONITOR"]["monitor_channel_pairs"] = monitor_pairs
            except Exception as e:
                logger.error(f"处理监听配置时出错: {e}")
                # 保持原有的监听配置，不要清空
                if "MONITOR" not in self.config:
                    self.config["MONITOR"] = {}
                if "monitor_channel_pairs" not in self.config["MONITOR"]:
                    self.config["MONITOR"]["monitor_channel_pairs"] = []
                logger.warning("保持原有监听配置不变")
            
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
            
        Returns:
            dict: 保存的配置，如果保存失败则返回空字典
            
        Raises:
            PermissionError: 当没有权限写入配置文件时抛出
        """
        try:
            # 如果不保存主题设置，临时保存当前主题
            current_theme = None
            if not save_theme and 'UI' in self.config and 'theme' in self.config['UI']:
                current_theme = self.config['UI']['theme']
                logger.debug(f"临时保存当前主题: {current_theme}")
            
            # 使用UI配置管理器更新并保存配置
            self.ui_config_manager.update_from_dict(self.config)
            try:
                save_success = self.ui_config_manager.save_config()
            except PermissionError:
                # 权限错误直接向上传递
                logger.warning(f"save_config: 保存配置时遇到权限问题，将错误向上传递")
                raise
            
            # 如果不保存主题设置，恢复原来的主题
            if not save_theme and current_theme and save_success:
                try:
                    # 尝试从文件重新读取配置并修改主题
                    with open(self.ui_config_manager.config_path, 'r', encoding='utf-8') as f:
                        file_config = json.load(f)
                        if 'UI' in file_config:
                            file_config['UI']['theme'] = current_theme
                            logger.debug(f"恢复配置文件中的主题: {current_theme}")
                            
                            # 重新保存文件
                            with open(self.ui_config_manager.config_path, 'w', encoding='utf-8') as f:
                                json.dump(file_config, f, ensure_ascii=False, indent=2)
                except PermissionError:
                    # 恢复主题时的权限错误同样向上传递
                    logger.warning(f"恢复主题时遇到权限问题，将错误向上传递")
                    raise
                except Exception as e:
                    # 恢复主题的其他错误则只记录日志，不影响返回结果
                    logger.error(f"恢复主题时出错: {e}")
            
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
        except PermissionError:
            # 权限错误直接向上传递，让调用者处理
            logger.warning("在save_config中捕获到权限错误，重新抛出")
            raise
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
        
    def on_config_saved(self, updated_config=None, main_window=None, theme_manager=None):
        """处理配置保存信号
        
        Args:
            updated_config: 更新后的配置字典
            main_window: 主窗口实例，用于显示错误对话框
            theme_manager: 主题管理器，用于处理主题变更
        """
        try:
            # 如果接收到更新后的配置，先更新内存中的配置
            if isinstance(updated_config, dict):
        
                
                # 备份当前主题设置（如果有的话）
                current_theme = None
                if 'UI' in self.config and 'theme' in self.config['UI']:
                    current_theme = self.config['UI'].get('theme')
    
                
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

                try:
                    self.ui_config_manager.update_from_dict(self.config)
                    save_success = self.ui_config_manager.save_config()
                    
                    if save_success:
                        logger.info("配置已通过UIConfigManager成功保存")
                        
                        # 检查主题是否变更
                        if theme_manager:
                            ui_config = self.config.get('UI', {})
                            saved_theme = ui_config.get('theme', '')
                            current_theme = theme_manager.get_current_theme_name()
                            
                            # 如果主题发生变化，触发主题更改信号
                            if saved_theme and saved_theme != current_theme:
                                logger.info(f"主题发生变化，从 '{current_theme}' 变更为 '{saved_theme}'")
                                if hasattr(theme_manager, 'theme_changed'):
                                    theme_manager.theme_changed.emit(saved_theme)
                        
                        # 发送配置保存成功信号
                        self.config_saved.emit()
                    else:
                        logger.error("UIConfigManager保存配置失败")
                except PermissionError as pe:
                    logger.warning(f"保存配置时遇到权限问题: {pe}")
                    
                    # 如果有主窗口实例，显示权限错误
                    if main_window:
                        self._show_permission_error_and_exit(main_window)
                    else:
                        raise pe
                except Exception as e:
                    logger.error(f"通过UIConfigManager更新配置失败: {e}")
                    import traceback
                    logger.debug(f"保存配置错误详情:\n{traceback.format_exc()}")
                    
                    # 回退到原始保存方法
                    try:
                        self.save_config(save_theme=True)
                        self.config_saved.emit()
                    except PermissionError:
                        # 如果原始保存方法也遇到权限问题，显示错误对话框
                        if main_window:
                            self._show_permission_error_and_exit(main_window)
                        else:
                            raise
                
                return
            
            # 如果是窗口状态变化，仅保存窗口状态（不保存整个配置）
            if main_window and hasattr(main_window, 'window_state_changed'):
                # 检查是否在短时间内多次触发保存
                current_time = time.time()
                if hasattr(self, '_last_window_state_save_time'):
                    # 如果上次保存时间距现在不足500毫秒，则跳过本次保存
                    if current_time - self._last_window_state_save_time < 0.5:
                        logger.debug("窗口状态保存请求过于频繁，跳过本次保存")
                        return
                
                # 更新上次保存时间
                self._last_window_state_save_time = current_time
                
                try:
                    # 获取当前窗口状态
                    window_state = {
                        'geometry': main_window.saveGeometry(),
                        'state': main_window.saveState()
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
                        with open(self.ui_config_manager.config_path, 'r', encoding='utf-8') as f:
                            file_config = json.load(f)
                        
                        # 确保UI部分存在
                        if 'UI' not in file_config:
                            file_config['UI'] = {}
                        
                        # 只更新窗口几何信息和状态
                        file_config['UI']['window_geometry'] = self.config['UI']['window_geometry']
                        file_config['UI']['window_state'] = self.config['UI']['window_state']
                        
                        # 保存回文件
                        with open(self.ui_config_manager.config_path, 'w', encoding='utf-8') as f:
                            json.dump(file_config, f, ensure_ascii=False, indent=2)
                        
                        logger.debug("窗口布局状态已单独保存")
                    except PermissionError:
                        logger.warning("保存窗口布局状态时遇到权限问题，将在下次完整保存配置时一并处理")
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
            try:
                self.save_config(save_theme=True)
                self.config_saved.emit()
            except PermissionError as pe:
                logger.warning(f"普通保存配置时遇到权限问题: {pe}")
                # 显示错误对话框并立即退出程序
                if main_window:
                    self._show_permission_error_and_exit(main_window)
                else:
                    raise pe
            
        except Exception as e:
            logger.error(f"处理配置保存信号失败: {e}")
            import traceback
            logger.debug(f"处理配置保存信号错误详情:\n{traceback.format_exc()}")
    
    def _show_permission_error_and_exit(self, main_window):
        """显示权限错误对话框并退出程序
        
        Args:
            main_window: 主窗口实例，用于显示错误对话框
        """
        # 如果已经显示过错误对话框，则直接返回
        if self._permission_error_shown:
            logger.debug("已经显示过权限错误对话框，不再重复显示")
            return
            
        # 设置标志，表示已显示错误对话框
        self._permission_error_shown = True
        
        # 在主窗口中显示权限错误信息
        config_path = os.path.abspath(self.ui_config_manager.config_path)
        error_msg = (
            f"无法写入配置文件 '{config_path}'，因为该文件为只读状态或您没有写入权限。\n\n"
            f"请退出程序，修改文件权限后重新启动。\n\n"
            f"您可以尝试：\n"
            f"1. 右键点击文件 -> 属性 -> 取消勾选'只读'属性\n"
            f"2. 以管理员身份运行程序\n"
            f"3. 将程序移动到有写入权限的目录"
        )
        
        QMessageBox.critical(
            main_window,
            "配置文件权限错误",
            error_msg,
            QMessageBox.Ok
        )
        
        # 用户点击确定后，立即关闭程序
        logger.info("因配置文件权限问题，应用程序立即退出")
        import sys
        # 退出进程
        sys.exit(1) 