#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
禁止转发频道消息转发示例程序

此示例展示如何实现对禁止转发频道的监听，以及如何将单条消息和媒体组消息转发到目标频道。
对于媒体消息使用流式下载上传，对于非媒体消息使用普通方式转发。
支持SOCKS5代理和频道链接解析。
"""

import os
import re
import asyncio
import logging
from pathlib import Path
from typing import List, Union, Dict, Optional, Tuple
from datetime import datetime
from io import BytesIO  # 添加BytesIO导入

from pyrogram import Client, filters
from pyrogram.types import (
    Message, 
    InputMediaVideo, 
    InputMediaPhoto, 
    InputMediaDocument,
    InputMediaAudio
)
from pyrogram.errors import FloodWait, ChatForwardsRestricted
from pyrogram.enums import ParseMode

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 配置信息
API_ID = 25448404  # 替换为您的 API ID
API_HASH = "0c910748a61fc30bb14e073a31933fb6"  # 替换为您的 API HASH
PHONE_NUMBER = "+1 256 888 8602"  # 替换为您的手机号码

# 代理设置
USE_PROXY = True  # 是否使用代理
PROXY_TYPE = "SOCKS5"  # 代理类型，目前仅支持SOCKS5
PROXY_HOST = "127.0.0.1"  # 代理服务器地址
PROXY_PORT = 7890  # 代理服务器端口
PROXY_USERNAME = None  # 代理用户名，如果不需要认证则为None
PROXY_PASSWORD = None  # 代理密码，如果不需要认证则为None

# 源频道和目标频道配置（可以使用频道链接、用户名或ID）
SOURCE_CHANNEL = "https://t.me/joisiid"  # 替换为您要监听的频道链接
TARGET_CHANNEL = "https://t.me/xgyvcu"   # 替换为您要转发到的目标频道链接

# 临时目录配置
TEMP_DIR = Path("tmp/restricted_forward")


class ChannelResolver:
    """频道解析器，用于解析频道链接并获取频道ID"""
    
    def __init__(self, client: Client):
        """
        初始化频道解析器
        
        Args:
            client: Pyrogram客户端实例
        """
        self.client = client
        # 缓存已解析的频道ID，避免重复解析
        self.channel_cache = {}
    
    async def resolve_channel(self, channel_identifier: str) -> int:
        """
        解析频道标识符获取频道ID
        
        Args:
            channel_identifier: 频道标识符，可以是频道链接、用户名或ID
            
        Returns:
            频道ID
        """
        # 检查缓存
        if channel_identifier in self.channel_cache:
            return self.channel_cache[channel_identifier]
        
        # 如果已经是整数ID
        if isinstance(channel_identifier, int) or (isinstance(channel_identifier, str) and channel_identifier.startswith('-100') and channel_identifier[4:].isdigit()):
            channel_id = int(channel_identifier)
            self.channel_cache[channel_identifier] = channel_id
            return channel_id
        
        # 处理t.me链接
        if 't.me/' in channel_identifier:
            username = channel_identifier.split('t.me/')[1].split('/')[0]
            channel_identifier = '@' + username
        
        # 处理@username格式
        if channel_identifier.startswith('@'):
            username = channel_identifier[1:]
            try:
                chat = await self.client.get_chat(username)
                channel_id = chat.id
                self.channel_cache[channel_identifier] = channel_id
                return channel_id
            except Exception as e:
                logger.error(f"解析频道 {channel_identifier} 失败: {e}")
                raise
        
        # 处理频道链接中可能包含的消息ID
        if 't.me/' in channel_identifier and '/' in channel_identifier.split('t.me/')[1]:
            parts = channel_identifier.split('t.me/')[1].split('/')
            username = parts[0]
            try:
                chat = await self.client.get_chat('@' + username)
                channel_id = chat.id
                self.channel_cache[channel_identifier] = channel_id
                return channel_id
            except Exception as e:
                logger.error(f"解析频道 {channel_identifier} 失败: {e}")
                raise
        
        # 如果无法解析，记录错误并抛出异常
        error_msg = f"无法解析频道标识符: {channel_identifier}"
        logger.error(error_msg)
        raise ValueError(error_msg)


class RestrictedChannelForwarder:
    """禁止转发频道消息转发器"""
    
    def __init__(self, client: Client):
        """
        初始化转发器
        
        Args:
            client: Pyrogram客户端实例
        """
        self.client = client
        self.channel_resolver = ChannelResolver(client)
        
        # 确保临时目录存在
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        
        # 频道ID缓存
        self.source_channel_id = None
        self.target_channel_id = None
        
        # 媒体组缓存
        self.media_group_cache: Dict[str, List[Message]] = {}
        self.media_group_lock = asyncio.Lock()
        self.media_group_timeout = 10  # 媒体组消息收集超时时间（秒）
    
    async def initialize(self):
        """初始化频道ID"""
        logger.info("正在解析频道ID...")
        
        try:
            # 解析源频道ID
            self.source_channel_id = await self.channel_resolver.resolve_channel(SOURCE_CHANNEL)
            logger.info(f"源频道ID: {self.source_channel_id}")
            
            # 解析目标频道ID
            self.target_channel_id = await self.channel_resolver.resolve_channel(TARGET_CHANNEL)
            logger.info(f"目标频道ID: {self.target_channel_id}")
            
        except Exception as e:
            logger.error(f"频道解析失败: {e}")
            raise
    
    async def start(self):
        """启动监听"""
        # 监听新消息
        @self.client.on_message(filters.chat(self.source_channel_id))
        async def on_message(client: Client, message: Message):
            try:
                await self.process_message(message)
            except Exception as e:
                logger.error(f"处理消息时出错: {e}", exc_info=True)
        
        logger.info(f"已连接到 Telegram，开始监听频道: {SOURCE_CHANNEL} (ID: {self.source_channel_id})")
        
        # 保持运行
        await asyncio.Event().wait()
    
    async def process_message(self, message: Message):
        """
        处理接收到的消息
        
        Args:
            message: 收到的消息
        """
        if message.media_group_id:
            # 处理媒体组消息
            await self.handle_media_group_message(message)
        else:
            # 处理单条消息
            await self.handle_single_message(message)
    
    async def handle_single_message(self, message: Message):
        """
        处理单条消息
        
        Args:
            message: 收到的消息
        """
        logger.info(f"收到单条消息: {message.id}")
        
        if self.is_media_message(message):
            # 媒体消息 - 使用流式下载上传
            await self.handle_media_message(message)
        else:
            # 非媒体消息 - 普通方式处理
            await self.handle_text_message(message)
    
    async def handle_media_group_message(self, message: Message):
        """
        处理媒体组消息
        
        Args:
            message: 收到的媒体组中的消息
        """
        if not message.media_group_id:
            return
        
        media_group_id = message.media_group_id
        
        async with self.media_group_lock:
            # 添加到媒体组缓存
            if media_group_id not in self.media_group_cache:
                self.media_group_cache[media_group_id] = []
                # 设置定时器，等待一段时间后处理媒体组
                asyncio.create_task(self.process_media_group_after_timeout(media_group_id))
            
            self.media_group_cache[media_group_id].append(message)
            logger.info(f"收到媒体组消息: {message.id}，添加到组 {media_group_id}，当前组内消息数: {len(self.media_group_cache[media_group_id])}")
    
    async def process_media_group_after_timeout(self, media_group_id: str):
        """
        等待超时后处理媒体组
        
        Args:
            media_group_id: 媒体组ID
        """
        await asyncio.sleep(self.media_group_timeout)
        
        async with self.media_group_lock:
            if media_group_id not in self.media_group_cache:
                return
            
            media_group = self.media_group_cache.pop(media_group_id)
            logger.info(f"媒体组 {media_group_id} 收集完成，共 {len(media_group)} 条消息")
        
        # 处理媒体组
        await self.forward_media_group(media_group)
    
    async def forward_media_group(self, media_group: List[Message]):
        """
        转发媒体组
        
        Args:
            media_group: 媒体组消息列表
        """
        if not media_group:
            return
        
        logger.info(f"开始处理媒体组，共 {len(media_group)} 条消息")
        
        # 按消息ID排序，确保顺序正确
        media_group.sort(key=lambda msg: msg.id)
        
        # 创建临时下载目录
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        temp_subdir = TEMP_DIR / f"group_{timestamp}"
        temp_subdir.mkdir(parents=True, exist_ok=True)
        
        # 构建媒体列表
        media_list = []
        caption = None
        
        # 优先获取第一条消息的说明文字
        for msg in media_group:
            if msg.caption:
                caption = msg.caption
                break
        
        try:
            # 下载所有媒体文件到内存
            for index, message in enumerate(media_group):
                # 流式下载媒体文件到内存
                media_buffer = await self._stream_media(message)
                
                if not media_buffer:
                    logger.error(f"无法流式获取媒体组文件: {message.id}")
                    continue
                
                # 为了与send_media_group兼容，我们需要将内存缓冲区写入临时文件
                file_name = media_buffer.name  # 使用_stream_media设置的文件名
                file_path = temp_subdir / file_name
                with open(file_path, "wb") as f:
                    f.write(media_buffer.getvalue())
                
                # 根据媒体类型构建对应的媒体对象
                if message.video:
                    media_type = InputMediaVideo
                    meta = {
                        "duration": message.video.duration if message.video.duration else None,
                        "width": message.video.width if message.video.width else None,
                        "height": message.video.height if message.video.height else None
                    }
                elif message.photo:
                    media_type = InputMediaPhoto
                    meta = {}
                elif message.document:
                    media_type = InputMediaDocument
                    meta = {}
                elif message.audio:
                    media_type = InputMediaAudio
                    meta = {
                        "duration": message.audio.duration if message.audio.duration else None
                    }
                else:
                    logger.warning(f"不支持的媒体类型: {message}")
                    continue
                
                # 添加到媒体列表
                media_list.append(
                    media_type(
                        media=str(file_path),  # 传递文件路径字符串
                        caption=caption if index == 0 else "",  # 仅第一个媒体保留说明文字
                        parse_mode=ParseMode.HTML,  # 支持HTML格式
                        **meta
                    )
                )
            
            # 批量发送媒体组
            if media_list:
                logger.info("开始发送媒体组...")
                await self.client.send_media_group(
                    chat_id=self.target_channel_id,
                    media=media_list,
                    disable_notification=True
                )
                logger.info("媒体组发送成功")
            else:
                logger.warning("媒体组中没有可发送的媒体")
        except FloodWait as e:
            logger.warning(f"遇到限流，等待 {e.value} 秒")
            await asyncio.sleep(e.value)
            # 重新尝试发送
            await self.forward_media_group(media_group)
        except Exception as e:
            logger.error(f"发送媒体组出错: {e}", exc_info=True)
        finally:
            # 清理临时目录
            await self.clean_directory(temp_subdir)
    
    async def handle_media_message(self, message: Message):
        """
        处理单条媒体消息
        
        Args:
            message: 收到的媒体消息
        """
        logger.info(f"处理单条媒体消息: {message.id}")
        
        # 创建临时下载目录
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        temp_subdir = TEMP_DIR / f"single_{timestamp}"
        temp_subdir.mkdir(parents=True, exist_ok=True)
        
        try:
            # 流式获取媒体到内存
            media_buffer = await self._stream_media(message)
            
            if not media_buffer:
                logger.error(f"无法流式获取媒体文件: {message.id}")
                return
            
            # 根据媒体类型进行处理
            if message.video:
                # 处理视频
                await self.client.send_video(
                    chat_id=self.target_channel_id,
                    video=media_buffer,
                    caption=message.caption,
                    parse_mode=ParseMode.HTML,
                    duration=message.video.duration if message.video.duration else None,
                    width=message.video.width if message.video.width else None,
                    height=message.video.height if message.video.height else None,
                    file_name=media_buffer.name,  # 显式提供文件名
                    disable_notification=True
                )
            elif message.photo:
                # 处理图片 (注意：send_photo 不支持 file_name 参数)
                await self.client.send_photo(
                    chat_id=self.target_channel_id,
                    photo=media_buffer,
                    caption=message.caption,
                    parse_mode=ParseMode.HTML,
                    disable_notification=True
                )
            elif message.document:
                # 处理文档
                await self.client.send_document(
                    chat_id=self.target_channel_id,
                    document=media_buffer,
                    caption=message.caption,
                    file_name=media_buffer.name,  # 显式提供文件名
                    parse_mode=ParseMode.HTML,
                    disable_notification=True
                )
            elif message.audio:
                # 处理音频
                await self.client.send_audio(
                    chat_id=self.target_channel_id,
                    audio=media_buffer,
                    caption=message.caption,
                    file_name=media_buffer.name,  # 显式提供文件名
                    parse_mode=ParseMode.HTML,
                    duration=message.audio.duration if message.audio.duration else None,
                    disable_notification=True
                )
            elif message.sticker:
                # 处理贴纸
                await self.client.send_sticker(
                    chat_id=self.target_channel_id,
                    sticker=media_buffer,
                    disable_notification=True
                )
            elif message.animation:
                # 处理GIF
                await self.client.send_animation(
                    chat_id=self.target_channel_id,
                    animation=media_buffer,
                    caption=message.caption,
                    file_name=media_buffer.name,  # 显式提供文件名
                    parse_mode=ParseMode.HTML,
                    disable_notification=True
                )
            else:
                logger.warning(f"不支持的媒体类型: {message}")
            
            logger.info(f"媒体消息 {message.id} 发送成功")
        except FloodWait as e:
            logger.warning(f"遇到限流，等待 {e.value} 秒")
            await asyncio.sleep(e.value)
            # 重新尝试发送
            await self.handle_media_message(message)
        except Exception as e:
            logger.error(f"发送媒体消息出错: {e}", exc_info=True)
        finally:
            # 清理临时目录
            await self.clean_directory(temp_subdir)
    
    async def handle_text_message(self, message: Message):
        """
        处理文本消息
        
        Args:
            message: 收到的文本消息
        """
        logger.info(f"处理文本消息: {message.id}")
        
        try:
            # 提取消息内容
            text = message.text or message.caption or ""
            
            # 发送文本消息
            await self.client.send_message(
                chat_id=self.target_channel_id,
                text=text,
                parse_mode=ParseMode.HTML,
                disable_notification=True,
                disable_web_page_preview=message.disable_web_page_preview if hasattr(message, "disable_web_page_preview") else None
            )
            logger.info(f"文本消息 {message.id} 发送成功")
        except FloodWait as e:
            logger.warning(f"遇到限流，等待 {e.value} 秒")
            await asyncio.sleep(e.value)
            # 重新尝试发送
            await self.handle_text_message(message)
        except Exception as e:
            logger.error(f"发送文本消息出错: {e}", exc_info=True)
    
    def is_media_message(self, message: Message) -> bool:
        """
        判断是否为媒体消息
        
        Args:
            message: 消息对象
            
        Returns:
            是否为媒体消息
        """
        return bool(
            message.photo or 
            message.video or 
            message.audio or 
            message.document or 
            message.sticker or 
            message.animation or 
            message.voice or 
            message.video_note
        )
    
    async def clean_directory(self, directory: Path):
        """
        清理目录
        
        Args:
            directory: 要清理的目录
        """
        try:
            if directory.exists():
                import shutil
                shutil.rmtree(directory)
                logger.info(f"清理目录成功: {directory}")
        except Exception as e:
            logger.error(f"清理目录出错: {e}", exc_info=True)
    
    async def _stream_media(self, message: Message) -> Optional[BytesIO]:
        """
        使用流式API将媒体文件流式下载到内存
        
        Args:
            message: 媒体消息
            
        Returns:
            内存中的文件对象，如果下载失败则返回None
        """
        try:
            buffer = BytesIO()
            
            # 使用stream_media逐块下载到内存
            downloaded_size = 0
            async for chunk in self.client.stream_media(message):
                buffer.write(chunk)
                downloaded_size += len(chunk)
            
            logger.info(f"媒体文件流式下载成功，大小: {downloaded_size} 字节")
            
            # 将缓冲区指针重置到开头
            buffer.seek(0)
            
            # 根据消息类型推断文件扩展名，并为BytesIO对象添加name属性
            if message.video:
                filename = f"video_{message.id}.mp4"
                buffer.name = filename
            elif message.photo:
                filename = f"photo_{message.id}.jpg"
                buffer.name = filename
            elif message.audio:
                filename = f"audio_{message.id}.mp3"
                buffer.name = filename
            elif message.voice:
                filename = f"voice_{message.id}.ogg"
                buffer.name = filename
            elif message.document:
                # 尝试从原始文件名获取扩展名
                orig_filename = message.document.file_name
                if orig_filename:
                    buffer.name = orig_filename
                else:
                    buffer.name = f"document_{message.id}"
            elif message.sticker:
                if message.sticker.is_animated:
                    buffer.name = f"sticker_{message.id}.tgs"
                elif message.sticker.is_video:
                    buffer.name = f"sticker_{message.id}.webm"
                else:
                    buffer.name = f"sticker_{message.id}.webp"
            elif message.animation:
                buffer.name = f"animation_{message.id}.mp4"
            else:
                buffer.name = f"media_{message.id}"
            
            return buffer
        except Exception as e:
            logger.error(f"流式下载媒体文件失败: {e}", exc_info=True)
            return None


async def main():
    """主函数"""
    # 创建代理配置
    proxy = None
    if USE_PROXY:
        proxy = {
            "scheme": PROXY_TYPE.lower(),  # socks5
            "hostname": PROXY_HOST,
            "port": PROXY_PORT,
            "username": PROXY_USERNAME,
            "password": PROXY_PASSWORD
        }
        logger.info(f"使用代理: {PROXY_TYPE}://{PROXY_HOST}:{PROXY_PORT}")
    
    # 创建 Pyrogram 客户端
    client = Client(
        "restricted_monitor",
        api_id=API_ID,
        api_hash=API_HASH,
        phone_number=PHONE_NUMBER,
        proxy=proxy
    )
    
    # 创建转发器
    forwarder = RestrictedChannelForwarder(client)
    
    try:
        # 先启动客户端
        await client.start()
        logger.info("客户端已启动")
        
        # 初始化频道ID
        await forwarder.initialize()
        
        # 开始监听
        await forwarder.start()
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
    except Exception as e:
        logger.error(f"程序运行出错: {e}", exc_info=True)
    finally:
        # 确保客户端正确停止
        await client.stop()
        logger.info("客户端已停止")


if __name__ == "__main__":
    # 运行主函数
    asyncio.run(main()) 