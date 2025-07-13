"""
配置工具函数

提供配置转换、验证、处理等工具函数。
"""

from typing import Any, Dict, List, Optional, Union
from loguru import logger


def convert_ui_config_to_dict(ui_config: Any) -> Dict[str, Any]:
    """
    将UI配置对象转换为字典格式
    
    Args:
        ui_config: UI配置对象
        
    Returns:
        转换后的配置字典
    """
    try:
        if hasattr(ui_config, 'model_dump'):
            # Pydantic v2
            return ui_config.model_dump()
        elif hasattr(ui_config, 'dict'):
            # Pydantic v1
            return ui_config.dict()
        elif isinstance(ui_config, dict):
            # 已经是字典格式
            return ui_config
        else:
            # 尝试转换为字典
            return dict(ui_config)
            
    except Exception as e:
        logger.error(f"转换UI配置失败: {e}")
        return {}


def convert_dict_to_ui_config(config_dict: Dict[str, Any], ui_config_class: Any) -> Any:
    """
    将字典格式转换为UI配置对象
    
    Args:
        config_dict: 配置字典
        ui_config_class: UI配置类
        
    Returns:
        UI配置对象
    """
    try:
        if hasattr(ui_config_class, 'model_validate'):
            # Pydantic v2
            return ui_config_class.model_validate(config_dict)
        elif hasattr(ui_config_class, 'parse_obj'):
            # Pydantic v1
            return ui_config_class.parse_obj(config_dict)
        else:
            # 直接实例化
            return ui_config_class(**config_dict)
            
    except Exception as e:
        logger.error(f"转换字典到UI配置失败: {e}")
        return None


def validate_channel_pair_config(pair_config: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    验证频道对配置
    
    Args:
        pair_config: 频道对配置
        
    Returns:
        (是否有效, 错误信息)
    """
    try:
        # 检查必需字段
        required_fields = ['source_channel', 'target_channels']
        for field in required_fields:
            if field not in pair_config:
                return False, f"缺少必需字段: {field}"
        
        # 检查源频道
        source_channel = pair_config.get('source_channel', '')
        if not source_channel:
            return False, "源频道不能为空"
        
        # 检查目标频道
        target_channels = pair_config.get('target_channels', [])
        if not target_channels:
            return False, "目标频道列表不能为空"
        
        if not isinstance(target_channels, list):
            return False, "目标频道必须是列表格式"
        
        # 检查媒体类型
        media_types = pair_config.get('media_types', [])
        if media_types and not isinstance(media_types, list):
            return False, "媒体类型必须是列表格式"
        
        # 检查关键词
        keywords = pair_config.get('keywords', [])
        if keywords and not isinstance(keywords, list):
            return False, "关键词必须是列表格式"
        
        # 检查文本替换规则
        text_filter = pair_config.get('text_filter', [])
        if text_filter and not isinstance(text_filter, list):
            return False, "文本替换规则必须是列表格式"
        
        # 验证文本替换规则格式
        for rule in text_filter:
            if not isinstance(rule, dict):
                return False, "文本替换规则必须是字典格式"
            
            if 'original_text' not in rule or 'target_text' not in rule:
                return False, "文本替换规则必须包含original_text和target_text字段"
        
        return True, None
        
    except Exception as e:
        return False, f"验证配置时出错: {e}"


def validate_download_config(download_config: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    验证下载配置
    
    Args:
        download_config: 下载配置
        
    Returns:
        (是否有效, 错误信息)
    """
    try:
        # 检查下载路径
        download_path = download_config.get('download_path', '')
        if not download_path:
            return False, "下载路径不能为空"
        
        # 检查下载设置
        download_settings = download_config.get('downloadSetting', [])
        if not isinstance(download_settings, list):
            return False, "下载设置必须是列表格式"
        
        # 验证每个下载设置
        for i, setting in enumerate(download_settings):
            if not isinstance(setting, dict):
                return False, f"下载设置 {i} 必须是字典格式"
            
            # 检查源频道
            source_channels = setting.get('source_channels', '')
            if not source_channels:
                return False, f"下载设置 {i} 缺少源频道"
            
            # 检查媒体类型
            media_types = setting.get('media_types', [])
            if media_types and not isinstance(media_types, list):
                return False, f"下载设置 {i} 媒体类型必须是列表格式"
            
            # 检查关键词
            keywords = setting.get('keywords', [])
            if keywords and not isinstance(keywords, list):
                return False, f"下载设置 {i} 关键词必须是列表格式"
            
            # 检查ID范围
            start_id = setting.get('start_id', 0)
            end_id = setting.get('end_id', 0)
            if not isinstance(start_id, int) or not isinstance(end_id, int):
                return False, f"下载设置 {i} ID范围必须是整数"
            
            if start_id > end_id and end_id != 0:
                return False, f"下载设置 {i} 起始ID不能大于结束ID"
            
            # 检查全局限制
            global_limit = setting.get('global_limit', 0)
            if not isinstance(global_limit, int) or global_limit < 0:
                return False, f"下载设置 {i} 全局限制必须是非负整数"
        
        return True, None
        
    except Exception as e:
        return False, f"验证下载配置时出错: {e}"


def validate_upload_config(upload_config: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    验证上传配置
    
    Args:
        upload_config: 上传配置
        
    Returns:
        (是否有效, 错误信息)
    """
    try:
        # 检查上传目录
        directory = upload_config.get('directory', '')
        if not directory:
            return False, "上传目录不能为空"
        
        # 检查目标频道
        target_channels = upload_config.get('target_channels', [])
        if not target_channels:
            return False, "目标频道列表不能为空"
        
        if not isinstance(target_channels, list):
            return False, "目标频道必须是列表格式"
        
        # 检查选项
        options = upload_config.get('options', {})
        if not isinstance(options, dict):
            return False, "上传选项必须是字典格式"
        
        # 验证选项字段
        option_fields = [
            'use_folder_name', 'read_title_txt', 'send_final_message',
            'auto_thumbnail', 'enable_web_page_preview', 'final_message_html_file'
        ]
        
        for field in option_fields:
            if field in options and not isinstance(options[field], (bool, str)):
                return False, f"上传选项 {field} 类型错误"
        
        return True, None
        
    except Exception as e:
        return False, f"验证上传配置时出错: {e}"


def validate_monitor_config(monitor_config: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    验证监听配置
    
    Args:
        monitor_config: 监听配置
        
    Returns:
        (是否有效, 错误信息)
    """
    try:
        # 检查监听频道对
        monitor_pairs = monitor_config.get('monitor_channel_pairs', [])
        if not isinstance(monitor_pairs, list):
            return False, "监听频道对必须是列表格式"
        
        # 验证每个频道对
        for i, pair in enumerate(monitor_pairs):
            is_valid, error = validate_channel_pair_config(pair)
            if not is_valid:
                return False, f"监听频道对 {i}: {error}"
        
        # 检查监听截止日期
        duration = monitor_config.get('duration', '')
        if duration and not _is_valid_date_format(duration):
            return False, "监听截止日期格式错误，应为YYYY-MM-DD"
        
        return True, None
        
    except Exception as e:
        return False, f"验证监听配置时出错: {e}"


def validate_forward_config(forward_config: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    验证转发配置
    
    Args:
        forward_config: 转发配置
        
    Returns:
        (是否有效, 错误信息)
    """
    try:
        # 检查转发频道对
        forward_pairs = forward_config.get('forward_channel_pairs', [])
        if not isinstance(forward_pairs, list):
            return False, "转发频道对必须是列表格式"
        
        # 验证每个频道对
        for i, pair in enumerate(forward_pairs):
            is_valid, error = validate_channel_pair_config(pair)
            if not is_valid:
                return False, f"转发频道对 {i}: {error}"
        
        # 检查转发延迟
        forward_delay = forward_config.get('forward_delay', 0.1)
        if not isinstance(forward_delay, (int, float)) or forward_delay < 0:
            return False, "转发延迟必须是非负数"
        
        # 检查临时路径
        tmp_path = forward_config.get('tmp_path', '')
        if not tmp_path:
            return False, "临时路径不能为空"
        
        return True, None
        
    except Exception as e:
        return False, f"验证转发配置时出错: {e}"


def merge_configs(base_config: Dict[str, Any], override_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    合并配置
    
    Args:
        base_config: 基础配置
        override_config: 覆盖配置
        
    Returns:
        合并后的配置
    """
    try:
        merged = base_config.copy()
        
        for key, value in override_config.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                # 递归合并字典
                merged[key] = merge_configs(merged[key], value)
            else:
                # 直接覆盖
                merged[key] = value
        
        return merged
        
    except Exception as e:
        logger.error(f"合并配置失败: {e}")
        return base_config


def filter_config_by_section(config: Dict[str, Any], section: str) -> Dict[str, Any]:
    """
    根据节名过滤配置
    
    Args:
        config: 完整配置
        section: 节名
        
    Returns:
        过滤后的配置
    """
    try:
        if section in config:
            return {section: config[section]}
        else:
            return {}
            
    except Exception as e:
        logger.error(f"过滤配置失败: {e}")
        return {}


def extract_channel_pairs(config: Dict[str, Any], section: str) -> List[Dict[str, Any]]:
    """
    提取频道对配置
    
    Args:
        config: 完整配置
        section: 节名（FORWARD或MONITOR）
        
    Returns:
        频道对列表
    """
    try:
        section_config = config.get(section, {})
        
        if section == 'FORWARD':
            return section_config.get('forward_channel_pairs', [])
        elif section == 'MONITOR':
            return section_config.get('monitor_channel_pairs', [])
        else:
            return []
            
    except Exception as e:
        logger.error(f"提取频道对配置失败: {e}")
        return []


def _is_valid_date_format(date_str: str) -> bool:
    """检查日期格式是否有效"""
    try:
        import datetime
        datetime.datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False


def sanitize_config_value(value: Any) -> Any:
    """
    清理配置值
    
    Args:
        value: 原始值
        
    Returns:
        清理后的值
    """
    try:
        if isinstance(value, str):
            # 清理字符串
            return value.strip()
        elif isinstance(value, list):
            # 清理列表中的字符串
            return [sanitize_config_value(item) for item in value]
        elif isinstance(value, dict):
            # 递归清理字典
            return {k: sanitize_config_value(v) for k, v in value.items()}
        else:
            return value
            
    except Exception as e:
        logger.error(f"清理配置值失败: {e}")
        return value


def validate_file_path(path: str) -> tuple[bool, Optional[str]]:
    """
    验证文件路径
    
    Args:
        path: 文件路径
        
    Returns:
        (是否有效, 错误信息)
    """
    try:
        if not path:
            return False, "路径不能为空"
        
        # 检查非法字符
        invalid_chars = ['<', '>', ':', '"', '|', '?', '*']
        for char in invalid_chars:
            if char in path:
                return False, f"路径包含非法字符: {char}"
        
        # 检查路径长度
        if len(path) > 260:  # Windows路径长度限制
            return False, "路径长度超过限制"
        
        return True, None
        
    except Exception as e:
        return False, f"验证路径时出错: {e}"


def normalize_config_paths(config: Dict[str, Any], base_path: str = '') -> Dict[str, Any]:
    """
    标准化配置中的路径
    
    Args:
        config: 配置字典
        base_path: 基础路径
        
    Returns:
        标准化后的配置
    """
    try:
        from pathlib import Path
        
        normalized = config.copy()
        
        # 需要标准化的路径字段
        path_fields = [
            'session_path', 'download_path', 'upload_path', 'tmp_path',
            'log_path', 'history_path', 'directory', 'final_message_html_file'
        ]
        
        for section, section_config in normalized.items():
            if isinstance(section_config, dict):
                for field, value in section_config.items():
                    if field in path_fields and isinstance(value, str) and value:
                        # 标准化路径
                        if base_path:
                            normalized_path = Path(base_path) / value
                        else:
                            normalized_path = Path(value)
                        
                        normalized[section][field] = str(normalized_path.absolute())
        
        return normalized
        
    except Exception as e:
        logger.error(f"标准化配置路径失败: {e}")
        return config 