"""
翻译管理器模块，负责多语言支持和文本翻译
"""

import os
import json
from typing import Dict, Any, Optional, Union
from PySide6.QtCore import QObject, Signal, QTimer

from src.utils.logger import get_logger

logger = get_logger()


class TranslationManager(QObject):
    """翻译管理器，负责多语言支持"""
    
    # 语言变更信号
    language_changed = Signal(str)  # 新语言代码
    
    def __init__(self, translations_dir: str = "translations"):
        """初始化翻译管理器
        
        Args:
            translations_dir: 翻译文件目录路径
        """
        super().__init__()
        
        self.translations_dir = translations_dir
        self.translations = {}  # 存储所有语言的翻译数据
        self.current_language = "zh"  # 默认语言
        self.fallback_language = "zh"  # 回退语言
        
        # 语言切换状态标志
        self._is_language_changing = False
        
        # 语言映射表
        self.language_mapping = {
            "中文": "zh",
            "English": "en"
        }
        
        # 语言代码到名称的映射
        self.code_to_name = {
            "zh": "中文",
            "en": "English"
        }
        
        # 加载所有翻译文件
        self._load_all_translations()
    
    def _load_all_translations(self):
        """加载所有可用的翻译文件"""
        try:
            if not os.path.exists(self.translations_dir):
                logger.warning(f"翻译目录不存在: {self.translations_dir}")
                return
            
            # 扫描翻译文件
            for filename in os.listdir(self.translations_dir):
                if filename.endswith('.json'):
                    lang_code = filename[:-5]  # 移除.json扩展名
                    self._load_translation(lang_code)
            
            logger.info(f"已加载 {len(self.translations)} 种语言的翻译")
            
        except Exception as e:
            logger.error(f"加载翻译文件时出错: {e}")
    
    def _load_translation(self, lang_code: str) -> bool:
        """加载指定语言的翻译文件
        
        Args:
            lang_code: 语言代码
            
        Returns:
            bool: 是否加载成功
        """
        try:
            file_path = os.path.join(self.translations_dir, f"{lang_code}.json")
            
            if not os.path.exists(file_path):
                logger.warning(f"翻译文件不存在: {file_path}")
                return False
            
            with open(file_path, 'r', encoding='utf-8') as f:
                self.translations[lang_code] = json.load(f)
            
            logger.debug(f"已加载语言翻译: {lang_code}")
            return True
            
        except Exception as e:
            logger.error(f"加载翻译文件 {lang_code}.json 失败: {e}")
            return False
    
    def set_language(self, language: Union[str, None]) -> bool:
        """设置当前语言
        
        Args:
            language: 语言名称或语言代码
            
        Returns:
            bool: 设置是否成功
        """
        if not language:
            return False
        
        # 如果是语言名称，转换为语言代码
        lang_code = language
        if language in self.language_mapping:
            lang_code = self.language_mapping[language]
        
        # 如果是已支持的语言代码
        if lang_code in self.code_to_name:
            # 确保翻译文件已加载
            if lang_code not in self.translations:
                if not self._load_translation(lang_code):
                    logger.error(f"无法加载语言 {lang_code} 的翻译文件")
                    return False
            
            old_language = self.current_language
            self.current_language = lang_code
            
            # 设置语言切换标志
            self._is_language_changing = True
            
            logger.info(f"语言已切换: {old_language} -> {lang_code}")
            
            # 发出语言变更信号
            self.language_changed.emit(lang_code)
            
            # 延迟清除语言切换标志，确保所有UI更新完成
            QTimer.singleShot(100, lambda: setattr(self, '_is_language_changing', False))
            
            return True
        
        logger.warning(f"不支持的语言: {language}")
        return False
    
    def get_current_language(self) -> str:
        """获取当前语言代码
        
        Returns:
            str: 当前语言代码
        """
        return self.current_language
    
    def get_current_language_name(self) -> str:
        """获取当前语言名称
        
        Returns:
            str: 当前语言名称
        """
        return self.code_to_name.get(self.current_language, "中文")
    
    def get_available_languages(self) -> list[str]:
        """获取可用的语言列表（语言名称）
        
        Returns:
            list[str]: 可用语言名称列表
        """
        return list(self.language_mapping.keys())
    
    def get_available_language_codes(self) -> list[str]:
        """获取可用的语言代码列表
        
        Returns:
            list[str]: 可用语言代码列表
        """
        return list(self.language_mapping.values())
    
    def tr(self, key: str, **kwargs) -> str:
        """翻译指定的键
        
        Args:
            key: 翻译键，支持嵌套键如 "ui.settings.title"
            **kwargs: 占位符参数
            
        Returns:
            str: 翻译后的文本
        """
        # 获取当前语言的翻译
        translation = self._get_translation(key, self.current_language)
        
        # 如果当前语言没有找到，尝试回退语言
        if translation is None and self.current_language != self.fallback_language:
            translation = self._get_translation(key, self.fallback_language)
        
        # 如果还是没有找到，返回键本身
        if translation is None:
            logger.debug(f"未找到翻译键: {key}")
            translation = key
        
        # 处理占位符
        if kwargs and isinstance(translation, str):
            try:
                translation = translation.format(**kwargs)
            except Exception as e:
                logger.warning(f"格式化翻译文本失败: {key}, {e}")
        
        return str(translation)
    
    def _get_translation(self, key: str, lang_code: str) -> Optional[str]:
        """从指定语言获取翻译
        
        Args:
            key: 翻译键
            lang_code: 语言代码
            
        Returns:
            Optional[str]: 翻译文本，如果未找到返回None
        """
        if lang_code not in self.translations:
            return None
        
        # 支持嵌套键，如 "ui.settings.title"
        keys = key.split('.')
        current = self.translations[lang_code]
        
        try:
            for k in keys:
                current = current[k]
            return current
        except (KeyError, TypeError):
            return None
    
    def reload_translations(self):
        """重新加载所有翻译文件"""
        self.translations.clear()
        self._load_all_translations()
        logger.info("翻译文件已重新加载")
    
    def is_language_available(self, language: Union[str, None]) -> bool:
        """检查指定语言是否可用
        
        Args:
            language: 语言名称或语言代码
            
        Returns:
            bool: 是否可用
        """
        if not language:
            return False
        
        # 检查语言名称
        if language in self.language_mapping:
            return True
        
        # 检查语言代码
        if language in self.code_to_name:
            return True
        
        return False


# 全局翻译管理器实例
_translation_manager = None


def get_translation_manager() -> TranslationManager:
    """获取全局翻译管理器实例
    
    Returns:
        TranslationManager: 翻译管理器实例
    """
    global _translation_manager
    if _translation_manager is None:
        _translation_manager = TranslationManager()
    return _translation_manager


def tr(key: str, **kwargs) -> str:
    """全局翻译函数，快捷方式
    
    Args:
        key: 翻译键
        **kwargs: 占位符参数
        
    Returns:
        str: 翻译后的文本
    """
    return get_translation_manager().tr(key, **kwargs)


def set_language(language: Union[str, None]) -> bool:
    """设置全局语言
    
    Args:
        language: 语言名称或语言代码
        
    Returns:
        bool: 设置是否成功
    """
    return get_translation_manager().set_language(language)


def get_current_language() -> str:
    """获取当前语言代码
    
    Returns:
        str: 当前语言代码
    """
    return get_translation_manager().get_current_language()


def get_current_language_name() -> str:
    """获取当前语言名称
    
    Returns:
        str: 当前语言名称
    """
    return get_translation_manager().get_current_language_name() 