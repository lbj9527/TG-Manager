"""
配置工具模块，提供 UI 配置和字典之间的转换工具
"""

from typing import Dict, Any, Optional

def convert_ui_config_to_dict(ui_config: Any) -> Dict[str, Any]:
    """
    将 UI 配置对象转换为字典格式
    
    Args:
        ui_config: UI 配置对象，通常来自 UIConfigManager.get_ui_config()
        
    Returns:
        Dict[str, Any]: 转换后的配置字典
    """
    config_dict = {}
    
    # 通用配置
    if hasattr(ui_config, 'general'):
        general_dict = {}
        general = ui_config.general
        
        if hasattr(general, 'api_id'):
            general_dict['api_id'] = general.api_id
        if hasattr(general, 'api_hash'):
            general_dict['api_hash'] = general.api_hash
        if hasattr(general, 'phone_number'):
            general_dict['phone_number'] = general.phone_number
        if hasattr(general, 'tmp_path'):
            general_dict['tmp_path'] = general.tmp_path
            
        config_dict['GENERAL'] = general_dict
    
    # 下载配置
    if hasattr(ui_config, 'download'):
        download_dict = {}
        download = ui_config.download
        
        if hasattr(download, 'download_path'):
            download_dict['download_path'] = download.download_path
        if hasattr(download, 'download_media_types'):
            download_dict['media_types'] = download.download_media_types
        if hasattr(download, 'download_channels'):
            download_dict['source_channels'] = download.download_channels
        if hasattr(download, 'download_keywords'):
            download_dict['keywords'] = download.download_keywords
        if hasattr(download, 'download_caption'):
            download_dict['caption'] = download.download_caption
        if hasattr(download, 'download_min_id'):
            download_dict['min_id'] = download.download_min_id
        if hasattr(download, 'download_max_id'):
            download_dict['max_id'] = download.download_max_id
        if hasattr(download, 'download_min_date'):
            download_dict['min_date'] = download.download_min_date
        if hasattr(download, 'download_max_date'):
            download_dict['max_date'] = download.download_max_date
        if hasattr(download, 'download_chat_history'):
            download_dict['chat_history'] = download.download_chat_history
        if hasattr(download, 'download_offset_id'):
            download_dict['offset_id'] = download.download_offset_id
        if hasattr(download, 'download_limit'):
            download_dict['limit'] = download.download_limit
            
        config_dict['DOWNLOAD'] = download_dict
    
    # 上传配置
    if hasattr(ui_config, 'upload'):
        upload_dict = {}
        upload = ui_config.upload
        
        if hasattr(upload, 'upload_source_path'):
            upload_dict['source_path'] = upload.upload_source_path
        if hasattr(upload, 'upload_target_channel'):
            upload_dict['target_channel'] = upload.upload_target_channel
        if hasattr(upload, 'upload_caption'):
            upload_dict['caption'] = upload.upload_caption
        if hasattr(upload, 'upload_media_types'):
            upload_dict['media_types'] = upload.upload_media_types
        if hasattr(upload, 'upload_include_subdirs'):
            upload_dict['include_subdirs'] = upload.upload_include_subdirs
            
        config_dict['UPLOAD'] = upload_dict
    
    # 转发配置
    if hasattr(ui_config, 'forward'):
        forward_dict = {}
        forward = ui_config.forward
        
        if hasattr(forward, 'forward_source_channels'):
            forward_dict['source_channels'] = forward.forward_source_channels
        if hasattr(forward, 'forward_target_channels'):
            forward_dict['target_channels'] = forward.forward_target_channels
        if hasattr(forward, 'forward_keywords'):
            forward_dict['keywords'] = forward.forward_keywords
        if hasattr(forward, 'forward_media_types'):
            forward_dict['media_types'] = forward.forward_media_types
        if hasattr(forward, 'forward_max_id'):
            forward_dict['max_id'] = forward.forward_max_id
        if hasattr(forward, 'forward_min_id'):
            forward_dict['min_id'] = forward.forward_min_id
        if hasattr(forward, 'forward_offset_id'):
            forward_dict['offset_id'] = forward.forward_offset_id
        if hasattr(forward, 'forward_limit'):
            forward_dict['limit'] = forward.forward_limit
        if hasattr(forward, 'forward_tmp_path'):
            forward_dict['tmp_path'] = forward.forward_tmp_path
        if hasattr(forward, 'forward_caption'):
            forward_dict['caption'] = forward.forward_caption
            
        config_dict['FORWARD'] = forward_dict
    
    # 监听配置
    if hasattr(ui_config, 'monitor'):
        monitor_dict = {}
        monitor = ui_config.monitor
        
        if hasattr(monitor, 'monitor_channel_pairs'):
            monitor_dict['monitor_channel_pairs'] = monitor.monitor_channel_pairs
        if hasattr(monitor, 'monitor_keywords'):
            monitor_dict['keywords'] = monitor.monitor_keywords
        if hasattr(monitor, 'monitor_media_types'):
            monitor_dict['media_types'] = monitor.monitor_media_types
        if hasattr(monitor, 'monitor_tmp_path'):
            monitor_dict['tmp_path'] = monitor.monitor_tmp_path
        if hasattr(monitor, 'monitor_caption'):
            monitor_dict['caption'] = monitor.monitor_caption
            
        config_dict['MONITOR'] = monitor_dict
    
    # 代理配置
    if hasattr(ui_config, 'proxy'):
        proxy_dict = {}
        proxy = ui_config.proxy
        
        if hasattr(proxy, 'proxy_enabled'):
            proxy_dict['enabled'] = proxy.proxy_enabled
        if hasattr(proxy, 'proxy_type'):
            proxy_dict['type'] = proxy.proxy_type
        if hasattr(proxy, 'proxy_host'):
            proxy_dict['host'] = proxy.proxy_host
        if hasattr(proxy, 'proxy_port'):
            proxy_dict['port'] = proxy.proxy_port
        if hasattr(proxy, 'proxy_username'):
            proxy_dict['username'] = proxy.proxy_username
        if hasattr(proxy, 'proxy_password'):
            proxy_dict['password'] = proxy.proxy_password
            
        config_dict['PROXY'] = proxy_dict
    
    return config_dict

def get_proxy_settings_from_config(config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    从配置字典中提取代理设置
    
    Args:
        config: 配置字典，通常来自 convert_ui_config_to_dict 函数
        
    Returns:
        Optional[Dict[str, Any]]: 代理设置字典，如果未启用代理则返回空字典
    """
    proxy_settings = {}
    
    # 获取代理配置
    proxy_config = config.get('PROXY', {})
    
    # 检查代理是否启用
    if not proxy_config.get('enabled', False):
        return proxy_settings
    
    # 获取代理类型
    proxy_type = proxy_config.get('type', '').lower()
    if not proxy_type:
        return proxy_settings
    
    # 获取代理主机和端口
    proxy_host = proxy_config.get('host', '')
    proxy_port = proxy_config.get('port')
    
    if not proxy_host or not proxy_port:
        return proxy_settings
    
    # 构建代理参数
    if proxy_type == 'socks4':
        proxy_settings['proxy'] = {
            'scheme': 'socks4',
            'hostname': proxy_host,
            'port': int(proxy_port)
        }
    elif proxy_type == 'socks5':
        proxy_settings['proxy'] = {
            'scheme': 'socks5',
            'hostname': proxy_host,
            'port': int(proxy_port)
        }
        
        # 检查是否有用户名和密码
        username = proxy_config.get('username', '')
        password = proxy_config.get('password', '')
        
        if username and password:
            proxy_settings['proxy']['username'] = username
            proxy_settings['proxy']['password'] = password
    elif proxy_type == 'http':
        proxy_settings['proxy'] = {
            'scheme': 'http',
            'hostname': proxy_host,
            'port': int(proxy_port)
        }
        
        # 检查是否有用户名和密码
        username = proxy_config.get('username', '')
        password = proxy_config.get('password', '')
        
        if username and password:
            proxy_settings['proxy']['username'] = username
            proxy_settings['proxy']['password'] = password
    
    return proxy_settings 