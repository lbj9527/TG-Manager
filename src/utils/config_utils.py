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
    
    # 检查配置对象是否已经是字典
    if isinstance(ui_config, dict):
        return ui_config
    
    # 检查是否有新结构的配置对象（大写部分名称）
    if hasattr(ui_config, 'GENERAL'):
        # 使用新结构转换
        # 通用配置
        general_dict = {}
        
        if hasattr(ui_config.GENERAL, 'api_id'):
            general_dict['api_id'] = ui_config.GENERAL.api_id
        if hasattr(ui_config.GENERAL, 'api_hash'):
            general_dict['api_hash'] = ui_config.GENERAL.api_hash
        if hasattr(ui_config.GENERAL, 'phone_number'):
            general_dict['phone_number'] = ui_config.GENERAL.phone_number
        if hasattr(ui_config.GENERAL, 'limit'):
            general_dict['limit'] = ui_config.GENERAL.limit
        if hasattr(ui_config.GENERAL, 'pause_time'):
            general_dict['pause_time'] = ui_config.GENERAL.pause_time
        if hasattr(ui_config.GENERAL, 'timeout'):
            general_dict['timeout'] = ui_config.GENERAL.timeout
        if hasattr(ui_config.GENERAL, 'max_retries'):
            general_dict['max_retries'] = ui_config.GENERAL.max_retries
        if hasattr(ui_config.GENERAL, 'proxy_enabled'):
            general_dict['proxy_enabled'] = ui_config.GENERAL.proxy_enabled
        if hasattr(ui_config.GENERAL, 'proxy_type'):
            # 处理枚举类型
            if hasattr(ui_config.GENERAL.proxy_type, 'value'):
                general_dict['proxy_type'] = ui_config.GENERAL.proxy_type.value
            else:
                general_dict['proxy_type'] = ui_config.GENERAL.proxy_type
        if hasattr(ui_config.GENERAL, 'proxy_addr'):
            general_dict['proxy_addr'] = ui_config.GENERAL.proxy_addr
        if hasattr(ui_config.GENERAL, 'proxy_port'):
            general_dict['proxy_port'] = ui_config.GENERAL.proxy_port
        if hasattr(ui_config.GENERAL, 'proxy_username'):
            general_dict['proxy_username'] = ui_config.GENERAL.proxy_username
        if hasattr(ui_config.GENERAL, 'proxy_password'):
            general_dict['proxy_password'] = ui_config.GENERAL.proxy_password
        if hasattr(ui_config.GENERAL, 'auto_restart_session'):
            general_dict['auto_restart_session'] = ui_config.GENERAL.auto_restart_session
            
        config_dict['GENERAL'] = general_dict
        
        # 添加下载配置的处理
        if hasattr(ui_config, 'DOWNLOAD'):
            download_dict = {}
            
            # 处理基本属性
            for field in ["download_path", "parallel_download", "max_concurrent_downloads"]:
                if hasattr(ui_config.DOWNLOAD, field):
                    download_dict[field] = getattr(ui_config.DOWNLOAD, field)
            
            # 处理downloadSetting字段
            if hasattr(ui_config.DOWNLOAD, 'downloadSetting'):
                download_settings = []
                
                for item in ui_config.DOWNLOAD.downloadSetting:
                    setting_dict = {}
                    
                    # 提取基本属性
                    if hasattr(item, 'source_channels'):
                        setting_dict['source_channels'] = item.source_channels
                    if hasattr(item, 'start_id'):
                        setting_dict['start_id'] = item.start_id
                    if hasattr(item, 'end_id'):
                        setting_dict['end_id'] = item.end_id
                    if hasattr(item, 'keywords'):
                        setting_dict['keywords'] = item.keywords
                    
                    # 处理媒体类型，转换枚举为字符串
                    if hasattr(item, 'media_types'):
                        media_types = []
                        for media_type in item.media_types:
                            if hasattr(media_type, 'value'):
                                media_types.append(media_type.value)
                            else:
                                media_types.append(media_type)
                        setting_dict['media_types'] = media_types
                    
                    download_settings.append(setting_dict)
                
                download_dict['downloadSetting'] = download_settings
            
            config_dict['DOWNLOAD'] = download_dict
        
        # 添加上传配置的处理
        if hasattr(ui_config, 'UPLOAD'):
            upload_dict = {}
            upload = ui_config.UPLOAD
            
            # 添加基本字段
            for field in ["directory", "caption_template", "delay_between_uploads"]:
                if hasattr(upload, field):
                    upload_dict[field] = getattr(upload, field)
            
            # 处理target_channels字段，保留字符串格式
            if hasattr(upload, 'target_channels'):
                upload_dict['target_channels'] = upload.target_channels
            
            # 处理options字段
            if hasattr(upload, 'options'):
                # options是一个字典类型，直接复制
                if isinstance(upload.options, dict):
                    upload_dict['options'] = upload.options.copy()
                else:
                    # 如果不是字典（可能是Pydantic模型），尝试使用字段访问
                    options = {}
                    for option_field in ["auto_thumbnail", "read_title_txt", "use_custom_template", "use_folder_name"]:
                        if hasattr(upload.options, option_field):
                            options[option_field] = getattr(upload.options, option_field)
                    upload_dict['options'] = options
            
            config_dict['UPLOAD'] = upload_dict
        
        # 添加转发配置的处理
        if hasattr(ui_config, 'FORWARD'):
            forward_dict = {}
            forward = ui_config.FORWARD
            
            # 添加基本字段
            for field in ["remove_captions", "hide_author", "forward_delay", "tmp_path", "send_final_message", "final_message_html_file"]:
                if hasattr(forward, field):
                    forward_dict[field] = getattr(forward, field)
            
            # 处理media_types字段，转换枚举为字符串
            if hasattr(forward, 'media_types'):
                media_types = []
                for media_type in forward.media_types:
                    if hasattr(media_type, 'value'):
                        media_types.append(media_type.value)
                    else:
                        media_types.append(media_type)
                forward_dict['media_types'] = media_types
            
            # 处理forward_channel_pairs字段
            if hasattr(forward, 'forward_channel_pairs'):
                channel_pairs = []
                for pair in forward.forward_channel_pairs:
                    pair_dict = {}
                    if hasattr(pair, 'source_channel'):
                        pair_dict['source_channel'] = pair.source_channel
                    if hasattr(pair, 'target_channels'):
                        pair_dict['target_channels'] = pair.target_channels
                    # 添加start_id和end_id到每个频道对配置中
                    if hasattr(pair, 'start_id'):
                        pair_dict['start_id'] = pair.start_id
                    if hasattr(pair, 'end_id'):
                        pair_dict['end_id'] = pair.end_id
                    # 添加媒体类型到每个频道对配置中
                    if hasattr(pair, 'media_types'):
                        media_types = []
                        for media_type in pair.media_types:
                            if hasattr(media_type, 'value'):
                                media_types.append(media_type.value)
                            else:
                                media_types.append(media_type)
                        pair_dict['media_types'] = media_types
                    
                    # 添加关键词到每个频道对配置中
                    if hasattr(pair, 'keywords'):
                        pair_dict['keywords'] = pair.keywords
                    
                    # 添加其他过滤选项到每个频道对配置中
                    for filter_field in ["exclude_forwards", "exclude_replies", "exclude_text", "exclude_links", "remove_captions", "hide_author", "send_final_message", "enabled"]:
                        if hasattr(pair, filter_field):
                            pair_dict[filter_field] = getattr(pair, filter_field)
                    
                    # 添加最终消息HTML文件路径
                    if hasattr(pair, 'final_message_html_file'):
                        pair_dict['final_message_html_file'] = pair.final_message_html_file
                    
                    # 添加文本替换规则
                    text_replacements = {}
                    if hasattr(pair, 'text_filter') and pair.text_filter:
                        for rule in pair.text_filter:
                            original = rule.get("original_text", "")
                            target = rule.get("target_text", "")
                            if original:  # 只添加非空的原文
                                text_replacements[original] = target
                    pair_dict['text_filter'] = getattr(pair, 'text_filter', [])  # UI格式
                    pair_dict['text_replacements'] = text_replacements  # 内部处理格式
                    channel_pairs.append(pair_dict)
                forward_dict['forward_channel_pairs'] = channel_pairs
            
            config_dict['FORWARD'] = forward_dict
        
        # 添加监听配置的处理
        if hasattr(ui_config, 'MONITOR'):
            monitor_dict = {}
            monitor = ui_config.MONITOR
            
            # 添加基本字段
            for field in ["duration"]:
                if hasattr(monitor, field):
                    monitor_dict[field] = getattr(monitor, field)
            
            # 处理monitor_channel_pairs字段
            if hasattr(monitor, 'monitor_channel_pairs'):
                monitor_channel_pairs = []
                for pair in monitor.monitor_channel_pairs:
                    pair_dict = {}
                    
                    # 处理基本字段
                    for field in ["source_channel", "target_channels", "remove_captions"]:
                        if hasattr(pair, field):
                            pair_dict[field] = getattr(pair, field)
                    
                    # 处理关键字段 - 新增
                    for field in ["keywords", "exclude_forwards", "exclude_replies", "exclude_text", "exclude_links"]:
                        if hasattr(pair, field):
                            pair_dict[field] = getattr(pair, field)
                    
                    # 处理text_filter字段
                    if hasattr(pair, 'text_filter'):
                        text_filter = []
                        for filter_item in pair.text_filter:
                            if isinstance(filter_item, dict):
                                text_filter.append(filter_item)
                            elif hasattr(filter_item, 'dict'):
                                text_filter.append(filter_item.dict())
                            else:
                                # 如果是其他格式，尝试转换
                                text_filter.append({
                                    "original_text": getattr(filter_item, 'original_text', ''),
                                    "target_text": getattr(filter_item, 'target_text', '')
                                })
                        pair_dict['text_filter'] = text_filter
                    
                    # 处理media_types字段，转换枚举为字符串
                    if hasattr(pair, 'media_types'):
                        media_types = []
                        for media_type in pair.media_types:
                            if hasattr(media_type, 'value'):
                                media_types.append(media_type.value)
                            else:
                                media_types.append(media_type)
                        pair_dict['media_types'] = media_types
                    
                    monitor_channel_pairs.append(pair_dict)
                
                monitor_dict['monitor_channel_pairs'] = monitor_channel_pairs
            
            # 将监听配置添加到结果字典
            config_dict['MONITOR'] = monitor_dict
        
        # 添加UI配置的处理
        if hasattr(ui_config, 'UI'):
            ui_dict = {}
            ui = ui_config.UI
            
            # 添加所有UI配置字段
            for field in ["theme", "confirm_exit", "minimize_to_tray", "start_minimized", 
                         "enable_notifications", "notification_sound", "window_geometry", "window_state"]:
                if hasattr(ui, field):
                    ui_dict[field] = getattr(ui, field)
            
            config_dict['UI'] = ui_dict
        
        return config_dict
    
    # 旧结构的配置转换逻辑（保留以兼容旧代码）
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
        # 添加最终消息相关配置
        if hasattr(forward, 'send_final_message'):
            forward_dict['send_final_message'] = forward.send_final_message
        if hasattr(forward, 'final_message_html_file'):
            forward_dict['final_message_html_file'] = forward.final_message_html_file
            
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
    
    # 检查新版配置结构中的代理设置（GENERAL部分）
    general_config = config.get('GENERAL', {})
    if general_config:
        proxy_enabled = general_config.get('proxy_enabled', False)
        if proxy_enabled:
            proxy_type = general_config.get('proxy_type', '').upper()
            proxy_addr = general_config.get('proxy_addr', '')
            proxy_port = general_config.get('proxy_port', 0)
            proxy_username = general_config.get('proxy_username', '')
            proxy_password = general_config.get('proxy_password', '')
            
            if proxy_addr and proxy_port:
                if proxy_type == 'SOCKS5' or proxy_type == 'SOCKS4':
                    proxy_settings['proxy'] = {
                        'scheme': proxy_type.lower(),
                        'hostname': proxy_addr,
                        'port': int(proxy_port)
                    }
                    
                    if proxy_username and proxy_password:
                        proxy_settings['proxy']['username'] = proxy_username
                        proxy_settings['proxy']['password'] = proxy_password
                elif proxy_type == 'HTTP' or proxy_type == 'HTTPS':
                    proxy_settings['proxy'] = {
                        'scheme': proxy_type.lower(),
                        'hostname': proxy_addr,
                        'port': int(proxy_port)
                    }
                    
                    if proxy_username and proxy_password:
                        proxy_settings['proxy']['username'] = proxy_username
                        proxy_settings['proxy']['password'] = proxy_password
                
                return proxy_settings
    
    # 检查旧版配置结构中的代理设置（PROXY部分）
    proxy_config = config.get('PROXY', {})
    if proxy_config and proxy_config.get('enabled', False):
        proxy_type = proxy_config.get('type', 'SOCKS5').upper()
        proxy_host = proxy_config.get('host', '')
        proxy_port = proxy_config.get('port', 0)
        proxy_username = proxy_config.get('username', '')
        proxy_password = proxy_config.get('password', '')
        
        if proxy_host and proxy_port:
            if proxy_type == 'SOCKS5' or proxy_type == 'SOCKS4':
                proxy_settings['proxy'] = {
                    'scheme': proxy_type.lower(),
                    'hostname': proxy_host,
                    'port': int(proxy_port)
                }
                
                if proxy_username and proxy_password:
                    proxy_settings['proxy']['username'] = proxy_username
                    proxy_settings['proxy']['password'] = proxy_password
            elif proxy_type == 'HTTP' or proxy_type == 'HTTPS':
                proxy_settings['proxy'] = {
                    'scheme': proxy_type.lower(),
                    'hostname': proxy_host,
                    'port': int(proxy_port)
                }
                
                if proxy_username and proxy_password:
                    proxy_settings['proxy']['username'] = proxy_username
                    proxy_settings['proxy']['password'] = proxy_password
    
    return proxy_settings