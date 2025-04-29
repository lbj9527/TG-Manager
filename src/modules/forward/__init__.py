"""
转发模块包
负责将消息从源频道转发到目标频道
"""

# 导出主要类以方便导入
from src.modules.forward.forwarder import Forwarder
from src.modules.forward.media_group_download import MediaGroupDownload

# 版本信息
__version__ = "1.0.0" 