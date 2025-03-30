"""
UI相关异常类，用于处理UI界面中可能发生的错误
"""

from typing import List, Dict, Any, Optional, Union


class BaseUIException(Exception):
    """UI异常基类"""
    
    def __init__(self, message: str, details: Optional[str] = None, 
                 suggestion: Optional[str] = None, error_code: Optional[str] = None):
        """
        初始化UI异常
        
        Args:
            message: 错误消息
            details: 详细错误信息
            suggestion: 解决建议
            error_code: 错误代码
        """
        self.message = message
        self.details = details
        self.suggestion = suggestion
        self.error_code = error_code
        super().__init__(message)
    
    def __str__(self) -> str:
        """返回格式化的错误信息"""
        error_str = self.message
        if self.details:
            error_str += f"\n详情: {self.details}"
        if self.suggestion:
            error_str += f"\n建议: {self.suggestion}"
        if self.error_code:
            error_str += f"\n错误代码: {self.error_code}"
        return error_str
    
    def to_dict(self) -> Dict[str, Any]:
        """将异常转换为字典格式，方便序列化和日志记录"""
        return {
            "type": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
            "suggestion": self.suggestion,
            "error_code": self.error_code
        }


class ConfigError(BaseUIException):
    """配置错误，当配置文件格式错误或缺少必要字段时抛出"""
    
    def __init__(self, message: str, details: Optional[str] = None, 
                 suggestion: Optional[str] = None, error_code: Optional[str] = None):
        super().__init__(
            message, 
            details, 
            suggestion or "请检查配置文件的格式和必要字段",
            error_code or "CONFIG_ERROR"
        )


class ConfigValidationError(ConfigError):
    """配置验证错误，当配置字段验证失败时抛出"""
    
    def __init__(self, message: str, field: Optional[str] = None, 
                 errors: List[str] = None, suggestion: Optional[str] = None):
        details = f"字段 '{field}' 验证失败" if field else None
        if errors:
            if details:
                details += ": " + ", ".join(errors)
            else:
                details = "验证错误: " + ", ".join(errors)
        
        super().__init__(
            message,
            details,
            suggestion or "请根据错误提示修正配置字段值",
            "CONFIG_VALIDATION_ERROR"
        )
        self.field = field
        self.errors = errors or []


class ConfigFileError(ConfigError):
    """配置文件错误，当配置文件不存在、无法读取或格式错误时抛出"""
    
    def __init__(self, message: str, file_path: str, 
                 details: Optional[str] = None, suggestion: Optional[str] = None):
        super().__init__(
            message,
            details or f"配置文件路径: {file_path}",
            suggestion or "请确保配置文件存在且格式正确",
            "CONFIG_FILE_ERROR"
        )
        self.file_path = file_path


class UIRenderError(BaseUIException):
    """UI渲染错误，当界面组件渲染失败时抛出"""
    
    def __init__(self, message: str, component: Optional[str] = None, 
                 details: Optional[str] = None, suggestion: Optional[str] = None):
        super().__init__(
            message,
            details or (f"组件: {component}" if component else None),
            suggestion or "请检查组件属性和数据格式",
            "UI_RENDER_ERROR"
        )
        self.component = component


class UIDataBindingError(BaseUIException):
    """UI数据绑定错误，当UI组件与数据绑定失败时抛出"""
    
    def __init__(self, message: str, field: Optional[str] = None, 
                 component: Optional[str] = None, suggestion: Optional[str] = None):
        details = None
        if field and component:
            details = f"字段 '{field}' 无法绑定到组件 '{component}'"
        elif field:
            details = f"字段 '{field}' 绑定失败"
        elif component:
            details = f"组件 '{component}' 绑定失败"
        
        super().__init__(
            message,
            details,
            suggestion or "请检查数据类型和组件属性是否匹配",
            "UI_DATA_BINDING_ERROR"
        )
        self.field = field
        self.component = component 