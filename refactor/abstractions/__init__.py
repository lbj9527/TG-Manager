"""
抽象层

提供下载、上传、处理器等功能的抽象基类，为插件系统提供统一接口。
"""

from .base_downloader import BaseDownloader
from .base_uploader import BaseUploader
from .base_handler import BaseHandler

__all__ = [
    'BaseDownloader',
    'BaseUploader',
    'BaseHandler'
] 