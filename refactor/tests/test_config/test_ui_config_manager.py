"""
UI配置管理器测试

测试UI配置管理器的核心功能。
"""

import pytest
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
from typing import Dict, Any

from config.ui_config_manager import UIConfigManager
from config.ui_config_models import UIConfig


class TestUIConfigManager:
    """UI配置管理器测试"""
    
    @pytest.fixture
    def temp_config_file(self):
        """临时配置文件"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_data = {
                "GENERAL": {
                    "language": "zh",
                    "theme": "light_blue",
                    "auto_start": False,
                    "minimize_to_tray": True
                },
                "DOWNLOAD": {
                    "download_path": "downloads",
                    "downloadSetting": [
                        {
                            "source_channels": "@testchannel",
                            "start_id": 1,
                            "end_id": 100,
                            "media_types": ["photo", "video"],
                            "keywords": ["test"],
                            "global_limit": 50
                        }
                    ]
                },
                "UPLOAD": {
                    "directory": "uploads",
                    "target_channels": ["@target1", "@target2"],
                    "options": {
                        "use_folder_name": True,
                        "read_title_txt": False,
                        "send_final_message": False
                    }
                },
                "FORWARD": {
                    "forward_channel_pairs": [
                        {
                            "source_channel": "@source",
                            "target_channels": ["@target1"],
                            "media_types": ["photo", "video"],
                            "start_id": 1,
                            "end_id": 100,
                            "enabled": True
                        }
                    ]
                },
                "MONITOR": {
                    "monitor_channel_pairs": [
                        {
                            "source_channel": "@source",
                            "target_channels": ["@target1"],
                            "media_types": ["photo", "video"],
                            "enabled": True
                        }
                    ]
                }
            }
            json.dump(config_data, f, indent=2)
            temp_file = f.name
        
        yield temp_file
        
        # 清理
        if os.path.exists(temp_file):
            os.unlink(temp_file)
    
    @pytest.fixture
    def ui_config_manager(self, temp_config_file):
        """UI配置管理器实例"""
        return UIConfigManager(temp_config_file)
    
    @pytest.fixture
    def sample_ui_config(self):
        """示例UI配置"""
        return UIConfig(
            GENERAL={
                "api_id": "12345",
                "api_hash": "test_hash",
                "language": "zh",
                "theme": "light_blue",
                "auto_start": False,
                "minimize_to_tray": True
            },
            DOWNLOAD={
                "download_path": "downloads",
                "downloadSetting": [
                    {
                        "source_channels": "@testchannel",
                        "start_id": 1,
                        "end_id": 100,
                        "media_types": ["photo", "video"],
                        "keywords": ["test"],
                        "global_limit": 50
                    }
                ]
            },
            UPLOAD={
                "directory": "uploads",
                "target_channels": ["@target1", "@target2"],
                "options": {
                    "use_folder_name": True,
                    "read_title_txt": False,
                    "send_final_message": False
                }
            },
            FORWARD={
                "forward_channel_pairs": [
                    {
                        "source_channel": "@source",
                        "target_channels": ["@target1"],
                        "media_types": ["photo", "video"],
                        "start_id": 1,
                        "end_id": 100,
                        "enabled": True
                    }
                ]
            },
            MONITOR={
                "monitor_channel_pairs": [
                    {
                        "source_channel": "@source",
                        "target_channels": ["@target1"],
                        "media_types": ["photo", "video"],
                        "enabled": True
                    }
                ]
            }
        )
    
    def test_initialization(self, temp_config_file):
        """测试初始化"""
        manager = UIConfigManager(temp_config_file)
        assert manager.config_path == temp_config_file
        assert manager.config is not None
    
    def test_load_config_success(self, ui_config_manager):
        """测试成功加载配置"""
        config = ui_config_manager.load_config()
        
        assert config is not None
        assert hasattr(config, 'GENERAL')
        assert hasattr(config, 'DOWNLOAD')
        assert hasattr(config, 'UPLOAD')
        assert hasattr(config, 'FORWARD')
        assert hasattr(config, 'MONITOR')
        
        # 验证GENERAL配置
        assert config.GENERAL.language == "zh"
        assert config.GENERAL.theme == "light_blue"
        assert config.GENERAL.auto_start is False
        assert config.GENERAL.minimize_to_tray is True
    
    def test_load_config_file_not_found(self):
        """测试加载不存在的配置文件"""
        manager = UIConfigManager("nonexistent.json")
        config = manager.load_config()
        
        # 应该返回默认配置
        assert config is not None
        assert hasattr(config, 'GENERAL')
    
    def test_load_config_invalid_json(self):
        """测试加载无效的JSON配置"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content")
            temp_file = f.name
        
        try:
            manager = UIConfigManager(temp_file)
            config = manager.load_config()
            
            # 应该返回默认配置
            assert config is not None
            assert hasattr(config, 'GENERAL')
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    def test_save_config_success(self, ui_config_manager, sample_ui_config):
        """测试成功保存配置"""
        # 保存配置
        success = ui_config_manager.save_config(sample_ui_config)
        
        assert success is True
        
        # 重新加载验证
        loaded_config = ui_config_manager.load_config()
        assert loaded_config.GENERAL.language == "zh"
        assert loaded_config.GENERAL.theme == "light_blue"
    
    def test_save_config_io_error(self, ui_config_manager, sample_ui_config):
        """测试保存配置时IO错误"""
        # 模拟文件写入错误
        with patch('builtins.open', side_effect=IOError("Permission denied")):
            success = ui_config_manager.save_config(sample_ui_config)
            assert success is False
    
    def test_reload_config(self, ui_config_manager):
        """测试重新加载配置"""
        # 初始加载
        config1 = ui_config_manager.load_config()
        
        # 修改配置文件
        with open(ui_config_manager.config_path, 'r') as f:
            data = json.load(f)
        
        data['GENERAL']['language'] = 'en'
        
        with open(ui_config_manager.config_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        # 重新加载
        config2 = ui_config_manager.reload_config()
        
        # 验证配置已更新
        assert config2.GENERAL.language == 'en'
        assert config1.GENERAL.language != config2.GENERAL.language
    
    def test_get_config(self, ui_config_manager):
        """测试获取配置"""
        config = ui_config_manager.get_config()
        
        assert config is not None
        assert hasattr(config, 'GENERAL')
        assert hasattr(config, 'DOWNLOAD')
    
    def test_update_config(self, ui_config_manager):
        """测试更新配置"""
        # 获取当前配置
        current_config = ui_config_manager.get_config()
        
        # 更新配置
        current_config.GENERAL.language = 'en'
        current_config.GENERAL.theme = 'dark_blue'
        
        # 保存更新
        success = ui_config_manager.update_config(current_config)
        
        assert success is True
        
        # 验证更新
        updated_config = ui_config_manager.get_config()
        assert updated_config.GENERAL.language == 'en'
        assert updated_config.GENERAL.theme == 'dark_blue'
    
    def test_get_default_config(self, ui_config_manager):
        """测试获取默认配置"""
        default_config = ui_config_manager.get_default_config()
        
        assert default_config is not None
        assert hasattr(default_config, 'GENERAL')
        assert hasattr(default_config, 'DOWNLOAD')
        assert hasattr(default_config, 'UPLOAD')
        assert hasattr(default_config, 'FORWARD')
        assert hasattr(default_config, 'MONITOR')
    
    def test_validate_config_success(self, ui_config_manager, sample_ui_config):
        """测试成功验证配置"""
        is_valid, errors = ui_config_manager.validate_config(sample_ui_config)
        
        assert is_valid is True
        assert len(errors) == 0
    
    def test_validate_config_with_errors(self, ui_config_manager):
        """测试验证有错误的配置"""
        # 创建无效配置
        invalid_config = UIConfig(
            GENERAL={
                "api_id": "12345",
                "api_hash": "test_hash",
                "language": "invalid_language",  # 无效语言
                "theme": "invalid_theme",  # 无效主题
                "auto_start": "not_boolean",  # 无效布尔值
                "minimize_to_tray": True
            },
            DOWNLOAD={
                "download_path": "",  # 空路径
                "downloadSetting": []
            },
            UPLOAD={
                "directory": "",
                "target_channels": [],
                "options": {}
            },
            FORWARD={
                "forward_channel_pairs": []
            },
            MONITOR={
                "monitor_channel_pairs": []
            }
        )
        
        is_valid, errors = ui_config_manager.validate_config(invalid_config)
        
        assert is_valid is False
        assert len(errors) > 0
    
    def test_backup_config(self, ui_config_manager):
        """测试备份配置"""
        backup_file = ui_config_manager.backup_config()
        
        assert backup_file is not None
        assert os.path.exists(backup_file)
        
        # 验证备份文件内容
        with open(backup_file, 'r') as f:
            backup_data = json.load(f)
        
        assert 'GENERAL' in backup_data
        assert 'DOWNLOAD' in backup_data
        
        # 清理备份文件
        if os.path.exists(backup_file):
            os.unlink(backup_file)
    
    def test_restore_config_from_backup(self, ui_config_manager):
        """测试从备份恢复配置"""
        # 创建备份
        backup_file = ui_config_manager.backup_config()
        
        try:
            # 修改当前配置
            current_config = ui_config_manager.get_config()
            current_config.GENERAL.language = 'en'
            ui_config_manager.save_config(current_config)
            
            # 从备份恢复
            success = ui_config_manager.restore_config_from_backup(backup_file)
            
            assert success is True
            
            # 验证已恢复
            restored_config = ui_config_manager.get_config()
            assert restored_config.GENERAL.language == 'zh'  # 原始值
        
        finally:
            # 清理备份文件
            if os.path.exists(backup_file):
                os.unlink(backup_file)
    
    def test_restore_config_from_invalid_backup(self, ui_config_manager):
        """测试从无效备份恢复配置"""
        # 创建无效备份文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json")
            invalid_backup = f.name
        
        try:
            success = ui_config_manager.restore_config_from_backup(invalid_backup)
            assert success is False
        finally:
            if os.path.exists(invalid_backup):
                os.unlink(invalid_backup)
    
    def test_get_config_diff(self, ui_config_manager):
        """测试获取配置差异"""
        # 获取当前配置
        config1 = ui_config_manager.get_config()
        
        # 创建修改后的配置
        config2 = ui_config_manager.get_config()
        config2.GENERAL.language = 'en'
        config2.GENERAL.theme = 'dark_blue'
        
        # 获取差异
        diff = ui_config_manager.get_config_diff(config1, config2)
        
        assert len(diff) > 0
        assert 'GENERAL.language' in diff
        assert 'GENERAL.theme' in diff
    
    def test_merge_configs(self, ui_config_manager):
        """测试合并配置"""
        # 基础配置
        base_config = ui_config_manager.get_config()
        
        # 部分配置
        partial_config = UIConfig(
            GENERAL={
                "api_id": "12345",
                "api_hash": "test_hash",
                "language": "en",
                "theme": "dark_blue"
            }
        )
        
        # 合并配置
        merged_config = ui_config_manager.merge_configs(base_config, partial_config)
        
        assert merged_config.GENERAL.language == 'en'
        assert merged_config.GENERAL.theme == 'dark_blue'
        # 其他配置应该保持不变
        assert merged_config.DOWNLOAD.download_path == base_config.DOWNLOAD.download_path
    
    def test_export_config(self, ui_config_manager):
        """测试导出配置"""
        export_file = ui_config_manager.export_config()
        
        assert export_file is not None
        assert os.path.exists(export_file)
        
        # 验证导出文件内容
        with open(export_file, 'r') as f:
            export_data = json.load(f)
        
        assert 'GENERAL' in export_data
        assert 'DOWNLOAD' in export_data
        
        # 清理导出文件
        if os.path.exists(export_file):
            os.unlink(export_file)
    
    def test_import_config(self, ui_config_manager):
        """测试导入配置"""
        # 创建导入文件
        import_data = {
            "GENERAL": {
                "language": "en",
                "theme": "dark_blue",
                "auto_start": True,
                "minimize_to_tray": False
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(import_data, f, indent=2)
            import_file = f.name
        
        try:
            # 导入配置
            success = ui_config_manager.import_config(import_file)
            
            assert success is True
            
            # 验证导入
            imported_config = ui_config_manager.get_config()
            assert imported_config.GENERAL.language == 'en'
            assert imported_config.GENERAL.theme == 'dark_blue'
            assert imported_config.GENERAL.auto_start is True
            assert imported_config.GENERAL.minimize_to_tray is False
        
        finally:
            if os.path.exists(import_file):
                os.unlink(import_file)
    
    def test_import_invalid_config(self, ui_config_manager):
        """测试导入无效配置"""
        # 创建无效导入文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json")
            invalid_import = f.name
        
        try:
            success = ui_config_manager.import_config(invalid_import)
            assert success is False
        finally:
            if os.path.exists(invalid_import):
                os.unlink(invalid_import)
    
    def test_get_config_schema(self, ui_config_manager):
        """测试获取配置模式"""
        schema = ui_config_manager.get_config_schema()
        
        assert schema is not None
        assert 'type' in schema
        assert 'properties' in schema
    
    def test_validate_config_against_schema(self, ui_config_manager, sample_ui_config):
        """测试根据模式验证配置"""
        is_valid, errors = ui_config_manager.validate_config_against_schema(sample_ui_config)
        
        assert is_valid is True
        assert len(errors) == 0
    
    def test_get_config_statistics(self, ui_config_manager):
        """测试获取配置统计"""
        stats = ui_config_manager.get_config_statistics()
        
        assert stats is not None
        assert 'total_settings' in stats
        assert 'sections' in stats
        assert 'last_modified' in stats
    
    def test_reset_to_defaults(self, ui_config_manager):
        """测试重置为默认配置"""
        # 修改当前配置
        current_config = ui_config_manager.get_config()
        current_config.GENERAL.language = 'en'
        ui_config_manager.save_config(current_config)
        
        # 重置为默认配置
        success = ui_config_manager.reset_to_defaults()
        
        assert success is True
        
        # 验证已重置
        reset_config = ui_config_manager.get_config()
        assert reset_config.GENERAL.language == 'zh'  # 默认值 