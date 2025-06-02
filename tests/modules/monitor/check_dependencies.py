#!/usr/bin/env python3
"""
测试系统依赖检查脚本
检查运行端到端测试所需的所有文件和模块
"""

import os
import sys
from pathlib import Path
from typing import List, Tuple, Dict

def check_file_exists(file_path: str, base_path: str = "") -> Tuple[bool, str]:
    """检查文件是否存在"""
    full_path = Path(base_path) / file_path if base_path else Path(file_path)
    return full_path.exists(), str(full_path.absolute())

def check_directory_exists(dir_path: str, base_path: str = "") -> Tuple[bool, str]:
    """检查目录是否存在"""
    full_path = Path(base_path) / dir_path if base_path else Path(dir_path)
    return full_path.exists() and full_path.is_dir(), str(full_path.absolute())

def get_file_size(file_path: str) -> str:
    """获取文件大小"""
    try:
        size = os.path.getsize(file_path)
        if size < 1024:
            return f"{size}B"
        elif size < 1024 * 1024:
            return f"{size/1024:.1f}KB"
        else:
            return f"{size/(1024*1024):.1f}MB"
    except:
        return "未知"

def main():
    print("🔍 端到端测试系统依赖检查")
    print("=" * 60)
    
    # 获取项目根目录 - 修正路径逻辑
    current_dir = Path.cwd()
    
    # 如果当前在 tests/modules/monitor 目录
    if current_dir.name == "monitor" and "tests" in str(current_dir):
        project_root = current_dir.parent.parent.parent  # 向上3级到项目根目录
        test_base = current_dir  # 当前就是测试基础目录
    else:
        project_root = Path(".")
        test_base = Path("tests/modules/monitor")
    
    project_root = project_root.resolve()
    test_base = test_base.resolve()
    
    print(f"项目根目录: {project_root}")
    print(f"测试基础目录: {test_base}")
    print()
    
    # 检查结果统计
    required_files_missing = []
    optional_files_missing = []
    
    # 1. 检查核心测试脚本 - 修正为相对于test_base的路径
    print("📋 1. 核心测试脚本")
    print("-" * 30)
    
    test_scripts = [
        "comprehensive_e2e_test.py",
        "test_media_group_scenarios.py", 
        "test_monitor_comprehensive.py"
    ]
    
    for script in test_scripts:
        exists, full_path = check_file_exists(script, test_base)
        status = "✅" if exists else "❌"
        size = get_file_size(full_path) if exists else "N/A"
        print(f"   {status} {script} ({size})")
        
        if not exists:
            required_files_missing.append(script)
    
    # 2. 检查源代码模块 - 使用项目根目录
    print("\n📦 2. 被测试的源代码模块")
    print("-" * 30)
    
    source_modules = [
        "src/modules/monitor/core.py",
        "src/modules/monitor/media_group_handler.py",
        "src/modules/monitor/message_processor.py", 
        "src/modules/monitor/text_filter.py",
        "src/utils/ui_config_models.py",
        "src/utils/channel_resolver.py",
        "src/utils/ui_config_manager.py"
    ]
    
    for module in source_modules:
        exists, full_path = check_file_exists(module, project_root)
        status = "✅" if exists else "❌"
        size = get_file_size(full_path) if exists else "N/A"
        print(f"   {status} {module} ({size})")
        
        if not exists:
            required_files_missing.append(module)
    
    # 3. 检查测试数据目录 - 相对于test_base
    print("\n🗂️ 3. 测试数据目录")
    print("-" * 30)
    
    test_data_dir = "test_data"
    exists, full_path = check_directory_exists(test_data_dir, test_base)
    status = "✅" if exists else "⚠️"
    print(f"   {status} {test_data_dir}/")
    
    if exists:
        # 检查子目录和文件
        test_data_items = [
            ("sample_messages/", True),
            ("sample_messages/text_messages.json", False),
            ("sample_messages/media_messages.json", False),
            ("sample_messages/media_groups.json", False),
            ("sample_configs/", True),
            ("sample_configs/basic_forward.json", False),
            ("sample_configs/keyword_filter.json", False),
            ("realistic_scenarios.json", False)
        ]
        
        test_data_root = test_base / test_data_dir
        
        for item, is_dir in test_data_items:
            item_path = test_data_root / item
            if is_dir:
                exists_item = item_path.exists() and item_path.is_dir()
            else:
                exists_item = item_path.exists() and item_path.is_file()
            
            status = "✅" if exists_item else "⚠️"
            size = get_file_size(str(item_path)) if exists_item and not is_dir else ""
            print(f"      {status} {item} {size}")
            
            if not exists_item:
                optional_files_missing.append(f"{test_data_dir}/{item}")
    else:
        print("      ⚠️ 测试数据目录不存在，将使用内置数据")
    
    # 4. 检查配置文件 - 相对于test_base
    print("\n🔧 4. 配置和支持文件")
    print("-" * 30)
    
    config_files = [
        "pytest.ini",
        "conftest.py",
        "README_TEST_GUIDE.md"
    ]
    
    for config_file in config_files:
        exists, full_path = check_file_exists(config_file, test_base)
        status = "✅" if exists else "⚠️"
        size = get_file_size(full_path) if exists else "N/A"
        print(f"   {status} {config_file} ({size})")
        
        if not exists:
            optional_files_missing.append(config_file)
    
    # 5. 检查Python环境
    print("\n🐍 5. Python环境")
    print("-" * 30)
    
    print(f"   Python版本: {sys.version}")
    
    # 检查关键依赖
    required_packages = ["asyncio", "json", "unittest.mock", "pathlib"]
    optional_packages = ["pytest", "pyrogram"]
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"   ✅ {package}")
        except ImportError:
            print(f"   ❌ {package} (必需)")
            required_files_missing.append(f"Python包: {package}")
    
    for package in optional_packages:
        try:
            __import__(package)
            print(f"   ✅ {package}")
        except ImportError:
            print(f"   ⚠️ {package} (可选)")
    
    # 6. 总结报告
    print("\n📊 依赖检查总结")
    print("=" * 60)
    
    total_required = len(test_scripts) + len(source_modules) + len(required_packages)
    missing_required = len(required_files_missing)
    missing_optional = len(optional_files_missing)
    
    print(f"必需文件: {total_required - missing_required}/{total_required} 存在")
    print(f"可选文件: 缺失 {missing_optional} 个")
    
    if missing_required == 0:
        print("\n🎉 所有必需依赖都已满足！可以运行测试。")
        print("\n运行测试命令:")
        print("   cd tests/modules/monitor")
        print("   python comprehensive_e2e_test.py")
    else:
        print(f"\n❌ 缺失 {missing_required} 个必需文件，无法运行测试")
        print("\n缺失的必需文件:")
        for missing_file in required_files_missing:
            print(f"   - {missing_file}")
    
    if missing_optional > 0:
        print(f"\n⚠️ 缺失 {missing_optional} 个可选文件，可能影响测试体验:")
        for missing_file in optional_files_missing[:5]:  # 只显示前5个
            print(f"   - {missing_file}")
        if len(optional_files_missing) > 5:
            print(f"   ... 还有 {len(optional_files_missing) - 5} 个文件")
    
    print(f"\n📍 当前工作目录: {Path.cwd()}")
    print(f"💾 总检查文件数: {len(test_scripts) + len(source_modules) + len(config_files) + 8}")
    
    return missing_required == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 