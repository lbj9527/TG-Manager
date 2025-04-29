"""
媒体组下载结果数据类
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple
from pathlib import Path
from pyrogram.types import Message

@dataclass
class MediaGroupDownload:
    """媒体组下载结果"""
    source_channel: str
    source_id: int
    messages: List[Message]
    download_dir: Path
    downloaded_files: List[Tuple[Path, str]]
    caption: Optional[str] = None 