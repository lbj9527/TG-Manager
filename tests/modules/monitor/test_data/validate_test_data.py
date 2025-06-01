 #!/usr/bin/env python3
"""
测试数据验证脚本
检查测试数据的完整性和有效性
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

class TestDataValidator:
    """测试数据验证器"""
    
    def __init__(self, test_data_dir: Path):
        self.test_data_dir = test_data_dir
        self.errors = []
        self.warnings = []
        
    def validate_json_file(self, filepath: Path) -> Optional[Dict[str, Any]]:
        """验证JSON文件格式"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        except json.JSONDecodeError as e:
            self.errors.append(f"JSON格式错误 {filepath}: {e}")
            return None
        except FileNotFoundError:
            self.errors.append(f"文件不存在: {filepath}")
            return None
        except Exception as e:
            self.errors.append(f"读取文件错误 {filepath}: {e}")
            return None
    
    def validate_message_structure(self, message: Dict[str, Any], context: str) -> bool:
        """验证消息结构"""
        required_fields = ['message_id', 'chat_id', 'chat_title', 'chat_username']
        valid = True
        
        for field in required_fields:
            if field not in message:
                self.errors.append(f"{context}: 缺少必需字段 '{field}'")
                valid = False
        
        # 检查message_id是否为正整数
        if 'message_id' in message:
            if not isinstance(message['message_id'], int) or message['message_id'] <= 0:
                self.errors.append(f"{context}: message_id必须为正整数")
                valid = False
        
        # 检查chat_id格式（Telegram频道ID通常是负数）
        if 'chat_id' in message:
            if not isinstance(message['chat_id'], int):
                self.errors.append(f"{context}: chat_id必须为整数")
                valid = False
        
        return valid
    
    def validate_config_structure(self, config: Dict[str, Any], context: str) -> bool:
        """验证配置结构"""
        required_fields = [
            'source_channel', 'target_channels', 'keywords',
            'exclude_forwards', 'exclude_replies', 'exclude_text',
            'exclude_links', 'remove_captions', 'media_types', 'text_filter'
        ]
        valid = True
        
        for field in required_fields:
            if field not in config:
                self.errors.append(f"{context}: 缺少必需字段 '{field}'")
                valid = False
        
        # 验证布尔字段
        bool_fields = ['exclude_forwards', 'exclude_replies', 'exclude_text', 
                      'exclude_links', 'remove_captions']
        for field in bool_fields:
            if field in config and not isinstance(config[field], bool):
                self.errors.append(f"{context}: {field}必须为布尔值")
                valid = False
        
        # 验证列表字段
        list_fields = ['target_channels', 'keywords', 'media_types', 'text_filter']
        for field in list_fields:
            if field in config and not isinstance(config[field], list):
                self.errors.append(f"{context}: {field}必须为列表")
                valid = False
        
        # 验证文本过滤规则结构
        if 'text_filter' in config:
            for i, rule in enumerate(config['text_filter']):
                if not isinstance(rule, dict):
                    self.errors.append(f"{context}: text_filter[{i}]必须为字典")
                    valid = False
                    continue
                
                if 'original_text' not in rule or 'target_text' not in rule:
                    self.errors.append(f"{context}: text_filter[{i}]缺少required字段")
                    valid = False
        
        return valid
    
    def validate_text_messages(self) -> bool:
        """验证文本消息数据"""
        filepath = self.test_data_dir / "sample_messages" / "text_messages.json"
        data = self.validate_json_file(filepath)
        if not data:
            return False
        
        valid = True
        for key, message in data.items():
            context = f"text_messages.{key}"
            if not self.validate_message_structure(message, context):
                valid = False
            
            # 验证文本消息特定字段
            if 'text' not in message:
                self.errors.append(f"{context}: 文本消息必须包含'text'字段")
                valid = False
            
            # 验证entities结构
            if 'entities' in message:
                if not isinstance(message['entities'], list):
                    self.errors.append(f"{context}: entities必须为列表")
                    valid = False
                else:
                    for i, entity in enumerate(message['entities']):
                        if not isinstance(entity, dict):
                            self.errors.append(f"{context}: entities[{i}]必须为字典")
                            valid = False
                            continue
                        
                        required_entity_fields = ['type', 'offset', 'length']
                        for field in required_entity_fields:
                            if field not in entity:
                                self.errors.append(f"{context}: entities[{i}]缺少'{field}'字段")
                                valid = False
        
        if valid:
            print(f"✅ text_messages.json 验证通过")
        
        return valid
    
    def validate_media_messages(self) -> bool:
        """验证媒体消息数据"""
        filepath = self.test_data_dir / "sample_messages" / "media_messages.json"
        data = self.validate_json_file(filepath)
        if not data:
            return False
        
        valid = True
        for key, message in data.items():
            context = f"media_messages.{key}"
            if not self.validate_message_structure(message, context):
                valid = False
            
            # 检查是否包含媒体字段
            media_fields = ['photo', 'video', 'document', 'audio', 'voice', 'sticker', 'animation', 'video_note']
            has_media = any(field in message for field in media_fields)
            
            if not has_media:
                self.errors.append(f"{context}: 媒体消息必须包含至少一个媒体字段")
                valid = False
        
        if valid:
            print(f"✅ media_messages.json 验证通过")
        
        return valid
    
    def validate_media_groups(self) -> bool:
        """验证媒体组数据"""
        filepath = self.test_data_dir / "sample_messages" / "media_groups.json"
        data = self.validate_json_file(filepath)
        if not data:
            return False
        
        valid = True
        for key, group in data.items():
            context = f"media_groups.{key}"
            
            if 'media_group_id' not in group:
                self.errors.append(f"{context}: 缺少'media_group_id'字段")
                valid = False
            
            if 'messages' not in group:
                self.errors.append(f"{context}: 缺少'messages'字段")
                valid = False
                continue
            
            if not isinstance(group['messages'], list):
                self.errors.append(f"{context}: messages必须为列表")
                valid = False
                continue
            
            if len(group['messages']) == 0:
                self.warnings.append(f"{context}: 媒体组为空")
            
            # 验证组内每条消息
            for i, message in enumerate(group['messages']):
                msg_context = f"{context}.messages[{i}]"
                if not self.validate_message_structure(message, msg_context):
                    valid = False
                
                # 检查media_group_count一致性
                if 'media_group_count' in message:
                    if message['media_group_count'] != len(group['messages']):
                        self.warnings.append(f"{msg_context}: media_group_count与实际消息数量不符")
        
        if valid:
            print(f"✅ media_groups.json 验证通过")
        
        return valid
    
    def validate_configs(self) -> bool:
        """验证配置文件"""
        config_files = [
            "basic_forward.json",
            "advanced_filter.json", 
            "media_only.json",
            "keyword_filter.json",
            "strict_filter.json",
            "multi_target.json"
        ]
        
        valid = True
        for filename in config_files:
            filepath = self.test_data_dir / "sample_configs" / filename
            data = self.validate_json_file(filepath)
            if not data:
                valid = False
                continue
            
            if not self.validate_config_structure(data, f"configs.{filename}"):
                valid = False
            else:
                print(f"✅ {filename} 验证通过")
        
        return valid
    
    def validate_expected_outputs(self) -> bool:
        """验证预期输出数据"""
        output_files = [
            "text_replacements.json",
            "filter_results.json",
            "forward_results.json"
        ]
        
        valid = True
        for filename in output_files:
            filepath = self.test_data_dir / "expected_outputs" / filename
            data = self.validate_json_file(filepath)
            if not data:
                valid = False
                continue
            
            print(f"✅ {filename} 验证通过")
        
        return valid
    
    def validate_scenarios(self) -> bool:
        """验证场景数据"""
        filepath = self.test_data_dir / "realistic_scenarios.json"
        data = self.validate_json_file(filepath)
        if not data:
            return False
        
        valid = True
        for scenario_name, scenario in data.items():
            context = f"scenarios.{scenario_name}"
            
            required_fields = ['description', 'source_channel', 'target_channels', 'config']
            for field in required_fields:
                if field not in scenario:
                    self.errors.append(f"{context}: 缺少'{field}'字段")
                    valid = False
        
        if valid:
            print(f"✅ realistic_scenarios.json 验证通过")
        
        return valid
    
    def validate_benchmarks(self) -> bool:
        """验证性能基准数据"""
        filepath = self.test_data_dir / "performance_benchmarks.json"
        data = self.validate_json_file(filepath)
        if not data:
            return False
        
        valid = True
        required_sections = [
            'baseline_metrics',
            'load_testing_scenarios', 
            'message_type_benchmarks',
            'filtering_performance'
        ]
        
        for section in required_sections:
            if section not in data:
                self.errors.append(f"benchmarks: 缺少'{section}'部分")
                valid = False
        
        if valid:
            print(f"✅ performance_benchmarks.json 验证通过")
        
        return valid
    
    def check_file_structure(self) -> bool:
        """检查文件结构完整性"""
        expected_structure = {
            "sample_messages": ["text_messages.json", "media_messages.json", "media_groups.json"],
            "sample_configs": ["basic_forward.json", "advanced_filter.json", "media_only.json", 
                             "keyword_filter.json", "strict_filter.json", "multi_target.json"],
            "expected_outputs": ["text_replacements.json", "filter_results.json", "forward_results.json"],
            "media_files": [".gitkeep"]
        }
        
        missing_files = []
        for directory, files in expected_structure.items():
            dir_path = self.test_data_dir / directory
            if not dir_path.exists():
                self.errors.append(f"目录不存在: {directory}")
                continue
            
            for filename in files:
                file_path = dir_path / filename
                if not file_path.exists():
                    missing_files.append(f"{directory}/{filename}")
        
        # 检查根目录文件
        root_files = ["realistic_scenarios.json", "performance_benchmarks.json"]
        for filename in root_files:
            file_path = self.test_data_dir / filename
            if not file_path.exists():
                missing_files.append(filename)
        
        if missing_files:
            self.errors.append(f"缺失文件: {', '.join(missing_files)}")
            return False
        
        print("✅ 文件结构完整")
        return True
    
    def run_validation(self) -> bool:
        """运行完整验证"""
        print("🔍 开始验证测试数据...")
        
        all_valid = True
        
        # 检查文件结构
        if not self.check_file_structure():
            all_valid = False
        
        # 验证各类数据文件
        validations = [
            self.validate_text_messages,
            self.validate_media_messages,
            self.validate_media_groups,
            self.validate_configs,
            self.validate_expected_outputs,
            self.validate_scenarios,
            self.validate_benchmarks
        ]
        
        for validation_func in validations:
            try:
                if not validation_func():
                    all_valid = False
            except Exception as e:
                self.errors.append(f"验证过程出错: {validation_func.__name__}: {e}")
                all_valid = False
        
        return all_valid
    
    def print_report(self):
        """打印验证报告"""
        print("\n" + "="*60)
        print("📋 测试数据验证报告")
        print("="*60)
        
        if self.errors:
            print(f"\n❌ 发现 {len(self.errors)} 个错误:")
            for i, error in enumerate(self.errors, 1):
                print(f"  {i}. {error}")
        
        if self.warnings:
            print(f"\n⚠️  发现 {len(self.warnings)} 个警告:")
            for i, warning in enumerate(self.warnings, 1):
                print(f"  {i}. {warning}")
        
        if not self.errors and not self.warnings:
            print("\n🎉 所有测试数据验证通过！")
        elif not self.errors:
            print("\n✅ 验证通过，但有一些警告需要注意")
        else:
            print("\n❌ 验证失败，请修复上述错误")

def main():
    """主函数"""
    test_data_dir = Path(__file__).parent
    validator = TestDataValidator(test_data_dir)
    
    success = validator.run_validation()
    validator.print_report()
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())