"""
错误处理工具模块
提供统一的错误处理和友好的错误弹窗功能
"""

import re
from typing import Optional, Dict, Any, List, Tuple
from PySide6.QtWidgets import QMessageBox, QWidget
from PySide6.QtCore import QObject

from src.utils.logger import get_logger
from src.utils.translation_manager import get_translation_manager, tr

logger = get_logger()


class ErrorHandler(QObject):
    """统一的错误处理工具类"""
    
    # 错误类型映射
    ERROR_TYPE_MAP = {
        # 频道相关错误
        'PEER_ID_INVALID': 'channel_invalid',
        'CHANNEL_PRIVATE': 'channel_private', 
        'USER_NOT_PARTICIPANT': 'channel_not_joined',
        'CHANNEL_INVALID': 'channel_invalid',
        'CHAT_NOT_FOUND': 'channel_not_found',
        'USERNAME_NOT_OCCUPIED': 'channel_not_found',
        'USERNAME_INVALID': 'channel_invalid',
        
        # 权限相关错误
        'FORBIDDEN': 'permission_denied',
        'CHAT_WRITE_FORBIDDEN': 'permission_denied',
        'CHAT_SEND_MEDIA_FORBIDDEN': 'permission_denied',
        'CHAT_SEND_MESSAGES_FORBIDDEN': 'permission_denied',
        'CHAT_RESTRICTED': 'permission_denied',
        'USER_RESTRICTED': 'permission_denied',
        'USER_DEACTIVATED': 'permission_denied',
        'USER_PRIVACY_RESTRICTED': 'permission_denied',
        
        # 媒体相关错误
        'MEDIA_EMPTY': 'media_error',
        'MEDIA_INVALID': 'media_error',
        'FILE_REFERENCE_EXPIRED': 'media_error',
        'FILE_REFERENCE_INVALID': 'media_error',
        
        # 网络相关错误
        'NETWORK_ERROR': 'network_error',
        'CONNECTION_ERROR': 'network_error',
        'TIMEOUT_ERROR': 'network_error',
        'SOCKET_ERROR': 'network_error',
        
        # API限制错误
        'FLOOD_WAIT': 'rate_limit',
        'TOO_MANY_REQUESTS': 'rate_limit',
        '429': 'rate_limit',
        
        # 认证相关错误
        'UNAUTHORIZED': 'auth_error',
        'AUTH_KEY_UNREGISTERED': 'auth_error',
        'SESSION_PASSWORD_NEEDED': 'auth_error',
        'PHONE_CODE_INVALID': 'auth_error',
        'PHONE_CODE_EXPIRED': 'auth_error',
        
        # 其他错误
        'DATABASE_LOCKED': 'system_error',
        'INTERNAL_SERVER_ERROR': 'system_error',
        'SERVICE_UNAVAILABLE': 'system_error'
    }
    
    # 错误消息模板
    ERROR_MESSAGES = {
        'channel_invalid': {
            'title': 'ui.settings.errors.channel_invalid.title',
            'message': 'ui.settings.errors.channel_invalid.message',
            'suggestion': 'ui.settings.errors.channel_invalid.suggestion'
        },
        'channel_private': {
            'title': 'ui.settings.errors.channel_private.title', 
            'message': 'ui.settings.errors.channel_private.message',
            'suggestion': 'ui.settings.errors.channel_private.suggestion'
        },
        'channel_not_joined': {
            'title': 'ui.settings.errors.channel_not_joined.title',
            'message': 'ui.settings.errors.channel_not_joined.message', 
            'suggestion': 'ui.settings.errors.channel_not_joined.suggestion'
        },
        'channel_not_found': {
            'title': 'ui.settings.errors.channel_not_found.title',
            'message': 'ui.settings.errors.channel_not_found.message',
            'suggestion': 'ui.settings.errors.channel_not_found.suggestion'
        },
        'permission_denied': {
            'title': 'ui.settings.errors.permission_denied.title',
            'message': 'ui.settings.errors.permission_denied.message',
            'suggestion': 'ui.settings.errors.permission_denied.suggestion'
        },
        'media_error': {
            'title': 'ui.settings.errors.media_error.title',
            'message': 'ui.settings.errors.media_error.message',
            'suggestion': 'ui.settings.errors.media_error.suggestion'
        },
        'network_error': {
            'title': 'ui.settings.errors.network_error.title',
            'message': 'ui.settings.errors.network_error.message',
            'suggestion': 'ui.settings.errors.network_error.suggestion'
        },
        'rate_limit': {
            'title': 'ui.settings.errors.rate_limit.title',
            'message': 'ui.settings.errors.rate_limit.message',
            'suggestion': 'ui.settings.errors.rate_limit.suggestion'
        },
        'auth_error': {
            'title': 'ui.settings.errors.auth_error.title',
            'message': 'ui.settings.errors.auth_error.message',
            'suggestion': 'ui.settings.errors.auth_error.suggestion'
        },
        'system_error': {
            'title': 'ui.settings.errors.system_error.title',
            'message': 'ui.settings.errors.system_error.message',
            'suggestion': 'ui.settings.errors.system_error.suggestion'
        },
        'unknown_error': {
            'title': 'ui.settings.errors.unknown_error.title',
            'message': 'ui.settings.errors.unknown_error.message',
            'suggestion': 'ui.settings.errors.unknown_error.suggestion'
        }
    }
    
    def __init__(self):
        """初始化错误处理器"""
        super().__init__()
        self.translation_manager = get_translation_manager()
    
    def classify_error(self, error: Exception) -> str:
        """
        分类错误类型
        
        Args:
            error: 异常对象
            
        Returns:
            str: 错误类型标识符
        """
        error_str = str(error).upper()
        error_type = type(error).__name__.upper()
        
        # 检查错误类型映射
        for pattern, error_category in self.ERROR_TYPE_MAP.items():
            if pattern in error_str or pattern in error_type:
                return error_category
        
        # 检查特殊模式
        if re.search(r'PEER_ID_INVALID|CHANNEL.*INVALID|USERNAME.*INVALID', error_str):
            return 'channel_invalid'
        elif re.search(r'CHANNEL.*PRIVATE|USER.*NOT.*PARTICIPANT', error_str):
            return 'channel_private'
        elif re.search(r'FORBIDDEN|RESTRICTED|WRITE.*FORBIDDEN', error_str):
            return 'permission_denied'
        elif re.search(r'MEDIA.*EMPTY|MEDIA.*INVALID|FILE.*REFERENCE', error_str):
            return 'media_error'
        elif re.search(r'NETWORK|CONNECTION|TIMEOUT|SOCKET', error_str):
            return 'network_error'
        elif re.search(r'FLOOD.*WAIT|TOO.*MANY.*REQUESTS|429', error_str):
            return 'rate_limit'
        elif re.search(r'UNAUTHORIZED|AUTH.*KEY|SESSION.*PASSWORD|PHONE.*CODE', error_str):
            return 'auth_error'
        elif re.search(r'DATABASE.*LOCKED|INTERNAL.*SERVER|SERVICE.*UNAVAILABLE', error_str):
            return 'system_error'
        
        return 'unknown_error'
    
    def extract_channel_info(self, error: Exception) -> Optional[str]:
        """
        从错误信息中提取频道信息
        
        Args:
            error: 异常对象
            
        Returns:
            Optional[str]: 频道信息，如果无法提取则返回None
        """
        error_str = str(error)
        
        # 尝试提取频道ID或用户名
        patterns = [
            r'PEER_ID_INVALID.*?(\d+)',
            r'CHANNEL.*?(\d+)',
            r'@(\w+)',
            r'https://t\.me/(\w+)',
            r'频道.*?(\d+)',
            r'频道.*?(@\w+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, error_str, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def show_error_dialog(self, parent: QWidget, error: Exception, 
                         context: str = "", additional_info: str = "") -> None:
        """
        显示友好的错误对话框
        
        Args:
            parent: 父窗口部件
            error: 异常对象
            context: 错误发生的上下文（如"监听"、"转发"、"下载"、"上传"）
            additional_info: 额外的错误信息
        """
        try:
            # 分类错误
            error_type = self.classify_error(error)
            
            # 获取错误消息模板
            error_template = self.ERROR_MESSAGES.get(error_type, self.ERROR_MESSAGES['unknown_error'])
            
            # 提取频道信息
            channel_info = self.extract_channel_info(error)
            
            # 构建错误消息
            title = tr(error_template['title'])
            message = tr(error_template['message'])
            suggestion = tr(error_template['suggestion'])
            
            # 如果有上下文信息，添加到标题
            if context:
                title = f"{context} - {title}"
            
            # 构建完整的错误消息
            full_message = message
            
            # 如果有频道信息，添加到消息中
            if channel_info:
                full_message += f"\n\n频道信息: {channel_info}"
            
            # 如果有额外信息，添加到消息中
            if additional_info:
                full_message += f"\n\n详细信息: {additional_info}"
            
            # 添加建议
            full_message += f"\n\n{suggestion}"
            
            # 显示错误对话框
            msg_box = QMessageBox(parent)
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setWindowTitle(title)
            msg_box.setText(full_message)
            msg_box.setStandardButtons(QMessageBox.Ok)
            
            # 设置详细文本（包含原始错误信息）
            msg_box.setDetailedText(f"原始错误信息:\n{str(error)}")
            
            msg_box.exec()
            
            logger.error(f"显示错误对话框: {error_type} - {str(error)}")
            
        except Exception as e:
            # 如果错误处理本身出错，显示简单的错误对话框
            logger.error(f"错误处理失败: {e}")
            QMessageBox.critical(parent, "错误", f"发生错误: {str(error)}")
    
    def show_channel_validation_error(self, parent: QWidget, channel_name: str, 
                                    error_type: str, context: str = "") -> None:
        """
        显示频道验证错误对话框
        
        Args:
            parent: 父窗口部件
            channel_name: 频道名称
            error_type: 错误类型
            context: 错误发生的上下文
        """
        try:
            # 获取错误消息模板
            error_template = self.ERROR_MESSAGES.get(error_type, self.ERROR_MESSAGES['unknown_error'])
            
            # 构建错误消息
            title = tr(error_template['title'])
            message = tr(error_template['message'])
            suggestion = tr(error_template['suggestion'])
            
            # 如果有上下文信息，添加到标题
            if context:
                title = f"{context} - {title}"
            
            # 构建完整的错误消息
            full_message = message.format(channel=channel_name)
            full_message += f"\n\n{suggestion}"
            
            # 显示错误对话框
            msg_box = QMessageBox(parent)
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setWindowTitle(title)
            msg_box.setText(full_message)
            msg_box.setStandardButtons(QMessageBox.Ok)
            
            msg_box.exec()
            
            logger.warning(f"频道验证错误: {error_type} - 频道: {channel_name}")
            
        except Exception as e:
            logger.error(f"频道验证错误处理失败: {e}")
            QMessageBox.warning(parent, "频道错误", f"频道 {channel_name} 验证失败: {error_type}")
    
    def show_batch_errors_dialog(self, parent: QWidget, errors: List[Tuple[str, Exception]], 
                                context: str = "") -> None:
        """
        显示批量错误对话框
        
        Args:
            parent: 父窗口部件
            errors: 错误列表，每个元素为(频道名, 异常)的元组
            context: 错误发生的上下文
        """
        try:
            if not errors:
                return
            
            # 按错误类型分组
            error_groups = {}
            for channel_name, error in errors:
                error_type = self.classify_error(error)
                if error_type not in error_groups:
                    error_groups[error_type] = []
                error_groups[error_type].append((channel_name, error))
            
            # 构建错误消息
            title = f"{context} - 批量错误" if context else "批量错误"
            message = f"发现 {len(errors)} 个错误:\n\n"
            
            for error_type, group_errors in error_groups.items():
                error_template = self.ERROR_MESSAGES.get(error_type, self.ERROR_MESSAGES['unknown_error'])
                error_title = tr(error_template['title'])
                message += f"• {error_title} ({len(group_errors)} 个频道):\n"
                
                for channel_name, error in group_errors:
                    message += f"  - {channel_name}: {str(error)[:100]}...\n"
                
                message += "\n"
            
            # 添加通用建议
            message += "建议:\n"
            message += "1. 检查频道名称是否正确\n"
            message += "2. 确保已加入相关频道\n"
            message += "3. 检查是否有发送消息的权限\n"
            message += "4. 验证网络连接是否正常\n"
            
            # 显示错误对话框
            msg_box = QMessageBox(parent)
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setWindowTitle(title)
            msg_box.setText(message)
            msg_box.setStandardButtons(QMessageBox.Ok)
            
            # 设置详细文本
            detailed_text = "详细错误信息:\n\n"
            for channel_name, error in errors:
                detailed_text += f"{channel_name}: {str(error)}\n\n"
            msg_box.setDetailedText(detailed_text)
            
            msg_box.exec()
            
            logger.warning(f"批量错误: {len(errors)} 个错误")
            
        except Exception as e:
            logger.error(f"批量错误处理失败: {e}")
            QMessageBox.warning(parent, "批量错误", f"处理 {len(errors)} 个错误时出现问题")


# 全局错误处理器实例
_error_handler = None

def get_error_handler() -> ErrorHandler:
    """获取全局错误处理器实例"""
    global _error_handler
    if _error_handler is None:
        _error_handler = ErrorHandler()
    return _error_handler 