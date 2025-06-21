"""
UI配置管理器模块，负责UI配置的加载、保存和与原配置的转换等功能。
"""

import os
import json
import re
from typing import Dict, Any, Optional, Union, List
from datetime import datetime
import logging

from src.utils.ui_config_models import (
    UIConfig, UIGeneralConfig, UIDownloadConfig, UIUploadConfig, 
    UIForwardConfig, UIMonitorConfig, UIChannelPair, UIMonitorChannelPair,
    UIDownloadSettingItem, UITextFilterItem, MediaType, ProxyType,
    create_default_config
)

from src.utils.logger import get_logger
from src.utils.config_utils import convert_ui_config_to_dict, get_proxy_settings_from_config

logger = get_logger()

class UIConfigManager:
    """UI配置管理器，负责处理UI配置的加载、保存和转换"""
    
    def __init__(self, config_path: str = "config.json"):
        """
        初始化UI配置管理器
        
        Args:
            config_path: 配置文件路径，默认为"config.json"
        """
        self.config_path = config_path
        self.ui_config = self._load_or_create_config()
    
    def _load_or_create_config(self) -> UIConfig:
        """
        加载或创建UI配置
        
        如果配置文件存在，则加载现有配置；否则创建默认配置并保存到文件
        
        Returns:
            UIConfig: UI配置对象
        """
        try:
            # 尝试从文件加载配置
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    return self._convert_to_ui_config(config_data)
            
            # 文件不存在，创建默认配置
            logger.info(f"配置文件不存在：{self.config_path}，创建默认配置")
            default_config = create_default_config()
            
            # 保存默认配置到文件
            try:
                # 确保目录存在
                os.makedirs(os.path.dirname(os.path.abspath(self.config_path)), exist_ok=True)
                
                # 将配置转换为字典
                config_dict = default_config.dict()
                
                # 将枚举值转换为字符串
                self._convert_enums_to_str(config_dict)
                
                # 写入配置文件
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump(config_dict, f, ensure_ascii=False, indent=2)
                
                logger.info(f"默认配置已保存到：{self.config_path}")
            except Exception as e:
                logger.warning(f"保存默认配置时出错：{e}")
            
            return default_config
        
        except json.JSONDecodeError:
            logger.error(f"配置文件格式错误：{self.config_path}，创建默认配置")
            return create_default_config()
        
        except Exception as e:
            logger.error(f"加载配置失败：{e}，创建默认配置")
            return create_default_config()
    
    def _convert_to_ui_config(self, config_data: Dict[str, Any]) -> UIConfig:
        """
        将配置字典转换为UI配置对象
        
        Args:
            config_data: 配置字典
        
        Returns:
            UIConfig: UI配置对象
        """
        try:
            # 确保必要的部分存在
            sections = ["GENERAL", "DOWNLOAD", "UPLOAD", "FORWARD", "MONITOR"]
            for section in sections:
                if section not in config_data:
                    config_data[section] = {}
            
            # 修复 GENERAL 部分
            general_config = config_data.get("GENERAL", {})
            
            # 确保 api_id 是有效的正整数
            if "api_id" not in general_config or not isinstance(general_config["api_id"], int) or general_config["api_id"] <= 0:
                general_config["api_id"] = 12345678  # 使用占位符，用户需要在运行前提供正确的值
                logger.warning("配置文件中的api_id无效，已替换为占位符")
            
            # 确保 api_hash 是有效的字符串
            if "api_hash" not in general_config or not re.match(r'^[a-f0-9]{32}$', str(general_config.get("api_hash", "")).lower()):
                general_config["api_hash"] = "0123456789abcdef0123456789abcdef"  # 使用占位符
                logger.warning("配置文件中的api_hash无效，已替换为占位符")
                
            # 确保phone_number字段存在
            if "phone_number" not in general_config:
                general_config["phone_number"] = None
            
            # 修复代理类型
            if "proxy_type" in general_config:
                try:
                    general_config["proxy_type"] = ProxyType(general_config["proxy_type"])
                except ValueError:
                    general_config["proxy_type"] = ProxyType.SOCKS5
                    logger.warning("配置文件中的proxy_type无效，已重置为SOCKS5")
            
            # 修复代理地址和端口
            if "proxy_enabled" in general_config:
                proxy_enabled = general_config.get("proxy_enabled", False)
                # 如果禁用代理，确保代理地址和端口有默认值
                if not proxy_enabled:
                    if not general_config.get("proxy_addr") or general_config.get("proxy_addr") == "":
                        general_config["proxy_addr"] = "127.0.0.1"
                    if not general_config.get("proxy_port") or general_config.get("proxy_port") < 1:
                        general_config["proxy_port"] = 1080
                # 如果启用代理，确保代理地址非空
                elif proxy_enabled and (not general_config.get("proxy_addr") or general_config.get("proxy_addr") == ""):
                    logger.warning("启用代理但代理地址为空，设置为默认值127.0.0.1")
                    general_config["proxy_addr"] = "127.0.0.1"
            
            # 更新General部分
            config_data["GENERAL"] = general_config
            
            # 修复 DOWNLOAD 部分
            download_config = config_data.get("DOWNLOAD", {})
            if "downloadSetting" in download_config:
                valid_download_settings = []
                for item in download_config["downloadSetting"]:
                  try:
                      # 转换媒体类型
                      if "media_types" in item:
                          media_types = []
                          for mt in item["media_types"]:
                              try:
                                  if mt in [e.value for e in MediaType]:
                                      media_types.append(MediaType(mt))
                                  else:
                                      logger.warning(f"无效的媒体类型: {mt}，已跳过")
                              except Exception:
                                  logger.warning(f"无效的媒体类型: {mt}，已跳过")
                          
                          # 如果没有有效的媒体类型，使用默认值
                          if not media_types:
                              media_types = [MediaType.PHOTO, MediaType.VIDEO, MediaType.DOCUMENT]
                              logger.warning("媒体类型列表为空，已使用默认值")
                          
                          item["media_types"] = media_types
                      
                      # 确保source_channels有效
                      if "source_channels" not in item or not item["source_channels"]:
                          continue  # 跳过无效的下载设置项
                      
                      # 修复source_channels
                      try:
                          source_channel = UIChannelPair.validate_channel_id(item["source_channels"], "源频道")
                          item["source_channels"] = source_channel
                      except ValueError as e:
                          logger.warning(f"无效的源频道: {item.get('source_channels')}, {e}")
                          continue  # 跳过无效项
                      
                      # 确保关键词是字符串列表而不是嵌套列表
                      if "keywords" in item and isinstance(item["keywords"], list):
                          # 确保每个关键词都是字符串
                          item["keywords"] = [str(kw) for kw in item["keywords"]]
                      
                      valid_download_settings.append(item)
                  except Exception as e:
                      logger.warning(f"处理下载设置项时出错: {e}")
                
                # 如果没有有效的下载设置项，添加一个空的设置项
                if not valid_download_settings:
                    valid_download_settings = [{
                        "source_channels": "",
                        "start_id": 0,
                        "end_id": 0,
                        "media_types": [MediaType.PHOTO, MediaType.VIDEO, MediaType.DOCUMENT],
                        "keywords": []
                    }]
                    logger.warning("下载设置列表为空，已添加默认项")
                
                download_config["downloadSetting"] = valid_download_settings
            
            # 修复 FORWARD 部分
            forward_config = config_data.get("FORWARD", {})
            
            # 转换媒体类型
            if "media_types" in forward_config:
                media_types = []
                for mt in forward_config["media_types"]:
                    try:
                        if mt in [e.value for e in MediaType]:
                            media_types.append(MediaType(mt))
                    except Exception:
                        pass
                
                # 如果没有有效的媒体类型，使用默认值
                if not media_types:
                    media_types = [MediaType.PHOTO, MediaType.VIDEO, MediaType.DOCUMENT]
                    logger.warning("转发媒体类型列表为空，已使用默认值")
                
                forward_config["media_types"] = media_types
            
            # 修复frequency_channel_pairs
            if "forward_channel_pairs" in forward_config:
                valid_pairs = []
                for pair in forward_config["forward_channel_pairs"]:
                    try:
                        source_channel = pair.get("source_channel", "")
                        target_channels = pair.get("target_channels", [])
                        
                        # 跳过无效的源频道
                        if not source_channel:
                            continue
                        
                        # 修复源频道
                        try:
                            source_channel = UIChannelPair.validate_channel_id(source_channel, "源频道")
                        except ValueError:
                            continue  # 跳过无效项
                        
                        # 修复目标频道
                        valid_targets = []
                        for target in target_channels:
                            try:
                                valid_target = UIChannelPair.validate_channel_id(target, "目标频道")
                                valid_targets.append(valid_target)
                            except ValueError:
                                pass  # 跳过无效目标
                        
                        # 如果没有有效的目标频道，跳过这一对
                        if not valid_targets:
                            continue
                        
                        # 创建有效频道对，并保留原始的start_id和end_id值
                        valid_pair = {
                            "source_channel": source_channel,
                            "target_channels": valid_targets,
                            "start_id": pair.get("start_id", 0),  # 保留原始的start_id
                            "end_id": pair.get("end_id", 0),      # 保留原始的end_id
                            # 添加转发选项布尔字段
                            "remove_captions": pair.get("remove_captions", False),
                            "hide_author": pair.get("hide_author", False),  
                            "send_final_message": pair.get("send_final_message", False),
                            # 添加最终消息HTML文件路径字段
                            "final_message_html_file": pair.get("final_message_html_file", "")
                        }
                        
                        # 处理文本替换规则
                        if "text_filter" in pair:
                            try:
                                text_filter = []
                                for item in pair["text_filter"]:
                                    if isinstance(item, dict):
                                        text_filter.append({
                                            "original_text": item.get("original_text", ""),
                                            "target_text": item.get("target_text", "")
                                        })
                                
                                # 确保至少有一个空的文本替换规则
                                if not text_filter:
                                    text_filter = [{"original_text": "", "target_text": ""}]
                                
                                valid_pair["text_filter"] = text_filter
                            except Exception as e:
                                logger.warning(f"处理转发频道对文本替换规则时出错: {e}")
                                valid_pair["text_filter"] = [{"original_text": "", "target_text": ""}]
                        else:
                            valid_pair["text_filter"] = [{"original_text": "", "target_text": ""}]
                        
                        # 处理关键词设置
                        keywords = pair.get("keywords", [])
                        if isinstance(keywords, list):
                            # 确保每个关键词都是字符串并过滤空值
                            valid_keywords = []
                            for keyword in keywords:
                                if keyword and isinstance(keyword, str) and keyword.strip():
                                    valid_keywords.append(keyword.strip())
                            valid_pair["keywords"] = valid_keywords
                        else:
                            valid_pair["keywords"] = []
                        
                        # 保留媒体类型设置如果存在
                        if "media_types" in pair:
                            try:
                                media_types = []
                                for mt in pair["media_types"]:
                                    if mt in [e.value for e in MediaType]:
                                        media_types.append(MediaType(mt))
                                if media_types:
                                    valid_pair["media_types"] = media_types
                            except Exception as e:
                                logger.warning(f"处理转发频道对媒体类型时出错: {e}")
                        
                        valid_pairs.append(valid_pair)
                    except Exception as e:
                        logger.warning(f"处理转发频道对时出错: {e}")
                
                # 如果没有有效的转发频道对，添加一个空的
                if not valid_pairs:
                    valid_pairs = [{
                        "source_channel": "",
                        "target_channels": [""],
                        "start_id": 0,
                        "end_id": 0,
                        "remove_captions": False,
                        "hide_author": False,
                        "send_final_message": False,
                        "final_message_html_file": "",
                        "text_filter": [{"original_text": "", "target_text": ""}],
                        "keywords": []
                    }]
                    logger.warning("转发频道对列表为空，已添加默认项")
                
                forward_config["forward_channel_pairs"] = valid_pairs
            
            # 修复 MONITOR 部分
            monitor_config = config_data.get("MONITOR", {})
            if not monitor_config:
                # 如果没有监听配置，创建默认的
                monitor_config = {
                    "monitor_channel_pairs": [],
                    "duration": None
                }
            
            # 确保 duration 字段存在且有效
            if "duration" in monitor_config:
                current_date = datetime.now()
                future_date = current_date.replace(year=current_date.year + 1)
                future_date_str = future_date.strftime("%Y-%m-%d")
                
                try:
                    # 尝试解析日期，如果无效或已过期，则使用未来日期
                    if not monitor_config["duration"] or datetime.strptime(monitor_config["duration"], "%Y-%m-%d") < current_date:
                        monitor_config["duration"] = future_date_str
                        logger.warning(f"监听截止日期无效或已过期，已设置为未来日期: {future_date_str}")
                except Exception:
                    monitor_config["duration"] = future_date_str
                    logger.warning(f"无效的监听截止日期，已设置为未来日期: {future_date_str}")
            
            # 修复监听频道对
            if "monitor_channel_pairs" in monitor_config:
                valid_pairs = []
                for pair in monitor_config["monitor_channel_pairs"]:
                    try:
                        # 验证源频道
                        source_channel = pair.get("source_channel", "")
                        if not source_channel:
                            continue
                        
                        try:
                            source_channel = UIChannelPair.validate_channel_id(source_channel, "源频道")
                        except ValueError as e:
                            logger.warning(f"无效的源频道: {source_channel}, {e}")
                            continue
                        
                        # 验证目标频道
                        target_channels = pair.get("target_channels", [])
                        if not target_channels:
                            continue
                        
                        valid_targets = []
                        for target in target_channels:
                            try:
                                target_channel = UIChannelPair.validate_channel_id(target, "目标频道")
                                valid_targets.append(target_channel)
                            except ValueError as e:
                                logger.warning(f"无效的目标频道: {target}, {e}")
                        
                        # 如果没有有效的目标频道，跳过这一对
                        if not valid_targets:
                            continue
                        
                        # 构建有效的配置项
                        valid_pair = {
                            "source_channel": source_channel,
                            "target_channels": valid_targets,
                            "remove_captions": pair.get("remove_captions", False),
                            "start_id": pair.get("start_id", 0),  # 保留原始的start_id
                            "end_id": pair.get("end_id", 0),      # 保留原始的end_id
                            # 添加转发选项布尔字段
                            "hide_author": pair.get("hide_author", False),  
                            "send_final_message": pair.get("send_final_message", False)
                        }
                        
                        # 处理文本替换规则
                        if "text_filter" in pair:
                            try:
                                text_filter = []
                                for item in pair["text_filter"]:
                                    if isinstance(item, dict):
                                        text_filter.append({
                                            "original_text": item.get("original_text", ""),
                                            "target_text": item.get("target_text", "")
                                        })
                                
                                # 确保至少有一个空的文本替换规则
                                if not text_filter:
                                    text_filter = [{"original_text": "", "target_text": ""}]
                                
                                valid_pair["text_filter"] = text_filter
                            except Exception as e:
                                logger.warning(f"处理监听频道对文本替换规则时出错: {e}")
                                valid_pair["text_filter"] = [{"original_text": "", "target_text": ""}]
                        else:
                            valid_pair["text_filter"] = [{"original_text": "", "target_text": ""}]
                        
                        # 处理媒体类型设置
                        if "media_types" in pair:
                            try:
                                media_types = []
                                for mt in pair["media_types"]:
                                    if mt in [e.value for e in MediaType]:
                                        media_types.append(MediaType(mt))
                                # 如果没有有效的媒体类型，使用默认值
                                if not media_types:
                                    media_types = [
                                        MediaType.PHOTO, MediaType.VIDEO, MediaType.DOCUMENT, 
                                        MediaType.AUDIO, MediaType.ANIMATION, MediaType.STICKER,
                                        MediaType.VOICE, MediaType.VIDEO_NOTE
                                    ]
                                valid_pair["media_types"] = media_types
                            except Exception as e:
                                logger.warning(f"处理监听频道对媒体类型时出错: {e}")
                                # 使用默认媒体类型
                                valid_pair["media_types"] = [
                                    MediaType.PHOTO, MediaType.VIDEO, MediaType.DOCUMENT, 
                                    MediaType.AUDIO, MediaType.ANIMATION, MediaType.STICKER,
                                    MediaType.VOICE, MediaType.VIDEO_NOTE
                                ]
                        else:
                            # 如果配置中没有媒体类型，使用默认值
                            valid_pair["media_types"] = [
                                MediaType.PHOTO, MediaType.VIDEO, MediaType.DOCUMENT, 
                                MediaType.AUDIO, MediaType.ANIMATION, MediaType.STICKER,
                                MediaType.VOICE, MediaType.VIDEO_NOTE
                            ]
                        
                        # 处理关键词设置
                        keywords = pair.get("keywords", [])
                        if isinstance(keywords, list):
                            # 确保每个关键词都是字符串并过滤空值
                            valid_keywords = []
                            for keyword in keywords:
                                if keyword and isinstance(keyword, str) and keyword.strip():
                                    valid_keywords.append(keyword.strip())
                            valid_pair["keywords"] = valid_keywords
                        else:
                            valid_pair["keywords"] = []
                        
                        # 处理排除项设置
                        valid_pair["exclude_forwards"] = bool(pair.get("exclude_forwards", False))
                        valid_pair["exclude_replies"] = bool(pair.get("exclude_replies", False))
                        # 兼容性处理：先尝试读取exclude_text，如果没有则从exclude_media转换
                        valid_pair["exclude_text"] = bool(pair.get("exclude_text", pair.get("exclude_media", False)))
                        valid_pair["exclude_links"] = bool(pair.get("exclude_links", False))
                        
                        valid_pairs.append(valid_pair)
                    except Exception as e:
                        logger.warning(f"处理监听频道对时出错: {e}")
                
                # 如果没有有效的监听频道对，添加一个默认的
                if not valid_pairs:
                    valid_pairs = [{
                        "source_channel": "@example_source",
                        "target_channels": ["@example_target"],
                        "remove_captions": False,
                        "text_filter": [{"original_text": "", "target_text": ""}],
                        "media_types": [
                            MediaType.PHOTO, MediaType.VIDEO, MediaType.DOCUMENT, 
                            MediaType.AUDIO, MediaType.ANIMATION, MediaType.STICKER,
                            MediaType.VOICE, MediaType.VIDEO_NOTE
                        ]
                    }]
                    logger.warning("监听频道对列表为空，已添加默认项")
                
                monitor_config["monitor_channel_pairs"] = valid_pairs
            
            # 修复UPLOAD部分
            upload_config = config_data.get("UPLOAD", {})
            
            # 修复target_channels
            if "target_channels" in upload_config:
                valid_targets = []
                for target in upload_config["target_channels"]:
                    try:
                        valid_target = UIChannelPair.validate_channel_id(target, "目标频道")
                        valid_targets.append(valid_target)
                    except ValueError:
                        # 尝试修复无效链接
                        if target.startswith('https://t.me/+'):
                            valid_target = '+' + target.split('/+')[1]
                            valid_targets.append(valid_target)
                            logger.warning(f"已尝试修复不规范的私有链接: {target} -> {valid_target}")
                        else:
                            logger.warning(f"无效的目标频道: {target}，已跳过")
                
                # 如果没有有效的目标频道，添加一个空的
                if not valid_targets:
                    valid_targets = [""]
                    logger.warning("上传目标频道列表为空，已添加默认项")
                
                upload_config["target_channels"] = valid_targets
            
            # 修复UI部分
            ui_config = config_data.get("UI", {})
            if not ui_config:
                ui_config = {
                    'theme': "深色主题",
                    'confirm_exit': True,
                    'minimize_to_tray': True,
                    'start_minimized': False,
                    'enable_notifications': True,
                    'notification_sound': True,
                    'window_geometry': None,
                    'window_state': None
                }
                logger.warning("UI配置为空，使用默认值")

            # 确保theme是有效值
            valid_themes = ["浅色主题", "深色主题", "蓝色主题", "紫色主题", "红色主题", "绿色主题", "琥珀色主题", "粉色主题", "黄色主题", "青色主题"]
            if "theme" not in ui_config or ui_config["theme"] not in valid_themes:
                ui_config["theme"] = "深色主题"
                logger.warning(f"UI主题无效，重置为深色主题")

            # 修复window_geometry和window_state
            for field in ["window_geometry", "window_state"]:
                if field in ui_config and not isinstance(ui_config[field], str):
                    ui_config[field] = None
                    logger.warning(f"UI {field} 类型无效，设置为None")

            # 确保布尔值字段正确
            bool_fields = ["confirm_exit", "minimize_to_tray", "start_minimized", "enable_notifications", "notification_sound"]
            for field in bool_fields:
                if field not in ui_config or not isinstance(ui_config[field], bool):
                    ui_config[field] = True  # 默认都是启用的
                    logger.warning(f"UI {field} 类型无效，设置为True")

            config_data["UI"] = ui_config
            
            # 创建UI配置对象
            return UIConfig(**config_data)
        
        except Exception as e:
            logger.error(f"转换配置失败：{e}，创建默认配置")
            # 输出更详细的错误信息，便于调试
            import traceback
            logger.debug(f"转换配置错误详情：\n{traceback.format_exc()}")
            return create_default_config()
    
    def save_config(self) -> bool:
        """
        保存UI配置到文件
        
        Returns:
            bool: 保存是否成功
            
        Raises:
            PermissionError: 当没有写入配置文件权限时抛出
        """
        try:
            # 确保配置目录存在
            os.makedirs(os.path.dirname(os.path.abspath(self.config_path)), exist_ok=True)
            
            # 将配置转换为字典并准备保存
            config_dict = self.ui_config.dict()
            
            # 将枚举值转换为字符串
            self._convert_enums_to_str(config_dict)
            
            # 检查文件是否存在且是否可写
            if os.path.exists(self.config_path):
                if not os.access(self.config_path, os.W_OK):
                    logger.warning(f"配置文件 {self.config_path} 不可写")
                    raise PermissionError(f"没有权限写入配置文件: {self.config_path}")
            
            # 尝试写入配置文件
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, ensure_ascii=False, indent=2)
            
            logger.info(f"配置已保存到：{self.config_path}")
            return True
            
        except PermissionError as pe:
            # 当遇到权限错误时，直接抛出，不做处理
            logger.warning(f"保存配置时遇到权限错误：{pe}")
            raise
        except Exception as e:
            # 其他错误则记录并返回False
            logger.error(f"保存配置失败：{e}")
            return False
    
    def _convert_enums_to_str(self, config_dict: Dict[str, Any]) -> None:
        """
        将配置字典中的枚举值转换为字符串
        
        Args:
            config_dict: 配置字典
        """
        # 处理GeneralConfig中的proxy_type
        if "GENERAL" in config_dict and "proxy_type" in config_dict["GENERAL"]:
            config_dict["GENERAL"]["proxy_type"] = config_dict["GENERAL"]["proxy_type"].value
        
        # 处理DownloadConfig中的media_types和keywords
        if "DOWNLOAD" in config_dict and "downloadSetting" in config_dict["DOWNLOAD"]:
            for item in config_dict["DOWNLOAD"]["downloadSetting"]:
                # 处理媒体类型
                if "media_types" in item:
                    item["media_types"] = [mt.value for mt in item["media_types"]]
                
                # 确保关键词是字符串列表而不是嵌套列表
                if "keywords" in item and isinstance(item["keywords"], list):
                    # 确保每个关键词都是字符串
                    item["keywords"] = [str(kw) for kw in item["keywords"]]
        
        # 处理ForwardConfig和MonitorConfig中的media_types
        for section in ["FORWARD", "MONITOR"]:
            if section in config_dict and "media_types" in config_dict[section]:
                config_dict[section]["media_types"] = [mt.value for mt in config_dict[section]["media_types"]]
        
        # 处理MonitorConfig中的monitor_channel_pairs
        if "MONITOR" in config_dict and "monitor_channel_pairs" in config_dict["MONITOR"]:
            for pair in config_dict["MONITOR"]["monitor_channel_pairs"]:
                # 处理媒体类型
                if "media_types" in pair:
                    pair["media_types"] = [mt.value for mt in pair["media_types"]]
                
                # 确保关键词是字符串列表
                if "keywords" in pair and isinstance(pair["keywords"], list):
                    pair["keywords"] = [str(kw) for kw in pair["keywords"]]
                
                # 确保排除项是布尔值
                for exclude_field in ["exclude_forwards", "exclude_replies", "exclude_text", "exclude_links"]:
                    if exclude_field in pair:
                        pair[exclude_field] = bool(pair[exclude_field])
    
    def get_ui_config(self) -> UIConfig:
        """
        获取UI配置对象
        
        如果内部配置无效，则创建一个默认配置
        
        Returns:
            UIConfig: UI配置对象
        """
        if self.ui_config is None:
            logger.warning("UI配置对象为空，创建默认配置")
            self.ui_config = create_default_config()
        return self.ui_config
    
    def reload_config(self) -> UIConfig:
        """
        强制从配置文件重新加载配置，更新内存中的缓存
        
        Returns:
            UIConfig: 重新加载的UI配置对象
        """
        logger.debug("强制从配置文件重新加载配置")
        self.ui_config = self._load_or_create_config()
        return self.ui_config
    
    def get_download_config(self) -> UIDownloadConfig:
        """
        获取下载配置对象
        
        Returns:
            UIDownloadConfig: 下载配置对象
        """
        if self.ui_config is None:
            logger.warning("UI配置对象为空，创建默认配置")
            self.ui_config = create_default_config()
        return self.ui_config.DOWNLOAD
    
    def get_upload_config(self) -> UIUploadConfig:
        """
        获取上传配置对象
        
        Returns:
            UIUploadConfig: 上传配置对象
        """
        if self.ui_config is None:
            logger.warning("UI配置对象为空，创建默认配置")
            self.ui_config = create_default_config()
        return self.ui_config.UPLOAD
    
    def get_forward_config(self) -> UIForwardConfig:
        """
        获取转发配置对象
        
        Returns:
            UIForwardConfig: 转发配置对象
        """
        if self.ui_config is None:
            logger.warning("UI配置对象为空，创建默认配置")
            self.ui_config = create_default_config()
        return self.ui_config.FORWARD
    
    def get_monitor_config(self) -> UIMonitorConfig:
        """
        获取监听配置对象
        
        Returns:
            UIMonitorConfig: 监听配置对象
        """
        if self.ui_config is None:
            logger.warning("UI配置对象为空，创建默认配置")
            self.ui_config = create_default_config()
        return self.ui_config.MONITOR
    
    def set_ui_config(self, ui_config: UIConfig) -> None:
        """
        设置UI配置对象
        
        Args:
            ui_config: UI配置对象
        """
        self.ui_config = ui_config
    
    def update_from_dict(self, config_dict: Dict[str, Any]) -> bool:
        """
        从字典更新UI配置
        
        Args:
            config_dict: 配置字典
        
        Returns:
            bool: 更新是否成功
        """
        try:
            # 尝试根据配置字典创建新的UIConfig对象
            self.ui_config = UIConfig(**config_dict)
            return True
        except Exception as e:
            # 增强错误日志，输出详细的验证错误信息
            from pydantic import ValidationError
            if isinstance(e, ValidationError):
                # 输出每个验证错误的详细信息
                for error in e.errors():
                    error_loc = " -> ".join(str(loc) for loc in error.get('loc', []))
                    error_msg = error.get('msg', '未知错误')
                    error_type = error.get('type', '未知类型')
                    logger.error(f"更新配置失败：1 validation error for {error_loc}")
                    logger.error(f"更新配置失败：{error_loc}")
                    logger.error(f"  {error_msg} (type={error_type})")
            else:
                # 其他类型的错误
                logger.error(f"更新配置失败：{e}")
            
            # 输出更详细的错误信息用于调试
            import traceback
            logger.debug(f"配置更新错误详情：\n{traceback.format_exc()}")
            
            return False
    
    
    def validate_config(self) -> List[str]:
        """
        验证UI配置是否有效
        
        Returns:
            List[str]: 错误消息列表，如果为空则表示配置有效
        """
        errors = []
        
        try:
            # 验证GENERAL配置
            if self.ui_config.GENERAL.api_id <= 0:
                errors.append("API ID必须是正整数")
            
            if not self.ui_config.GENERAL.api_hash:
                errors.append("API Hash不能为空")
            
            # 验证DOWNLOAD配置
            if not self.ui_config.DOWNLOAD.downloadSetting:
                errors.append("至少需要一个下载设置项")
            
            for i, item in enumerate(self.ui_config.DOWNLOAD.downloadSetting):
                if not item.source_channels:
                    errors.append(f"下载设置项[{i}]的源频道不能为空")
            
            # 验证UPLOAD配置
            if not self.ui_config.UPLOAD.target_channels:
                errors.append("上传配置的目标频道列表不能为空")
            
            # 验证FORWARD配置
            if not self.ui_config.FORWARD.forward_channel_pairs:
                errors.append("至少需要一个转发频道对")
            
            for i, pair in enumerate(self.ui_config.FORWARD.forward_channel_pairs):
                if not pair.source_channel:
                    errors.append(f"转发频道对[{i}]的源频道不能为空")
                if not pair.target_channels:
                    errors.append(f"转发频道对[{i}]的目标频道列表不能为空")
            
            # 验证MONITOR配置
            if not self.ui_config.MONITOR.monitor_channel_pairs:
                errors.append("至少需要一个监听频道对")
            
            for i, pair in enumerate(self.ui_config.MONITOR.monitor_channel_pairs):
                if not pair.source_channel:
                    errors.append(f"监听频道对[{i}]的源频道不能为空")
                if not pair.target_channels:
                    errors.append(f"监听频道对[{i}]的目标频道列表不能为空")
        
        except Exception as e:
            errors.append(f"验证配置时发生错误：{e}")
        
        return errors
