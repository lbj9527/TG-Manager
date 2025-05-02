#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Pyrogram常量修复工具

该脚本用于自动修复Pyrogram库中的MIN_CHANNEL_ID和MIN_CHAT_ID常量值，
以解决"PEER_ID_INVALID"错误。
"""

import os
import sys
import re
from pathlib import Path
import importlib
import site

# 要修改的常量及其新值
CONSTANTS_TO_FIX = {
    "MIN_CHANNEL_ID": -1007852516352,
    "MIN_CHAT_ID": -999999999999
}

def find_pyrogram_utils():
    """
    查找Pyrogram库中的utils.py文件路径
    
    Returns:
        找到的文件路径，如果未找到则返回None
    """
    # 方法1: 直接通过importlib获取
    try:
        utils_module = importlib.import_module("pyrogram.utils")
        return utils_module.__file__
    except (ImportError, AttributeError):
        print("无法通过importlib定位pyrogram.utils")
    
    # 方法2: 在site-packages中搜索
    try:
        for site_dir in site.getsitepackages():
            search_path = os.path.join(site_dir, "pyrogram")
            if os.path.exists(search_path):
                utils_path = os.path.join(search_path, "utils.py")
                if os.path.exists(utils_path):
                    return utils_path
    except Exception as e:
        print(f"在site-packages中搜索时出错: {e}")
    
    # 方法3: 使用sys.path搜索
    try:
        for path in sys.path:
            search_path = os.path.join(path, "pyrogram")
            if os.path.exists(search_path):
                utils_path = os.path.join(search_path, "utils.py")
                if os.path.exists(utils_path):
                    return utils_path
    except Exception as e:
        print(f"在sys.path中搜索时出错: {e}")
    
    return None

def backup_file(file_path):
    """
    备份文件
    
    Args:
        file_path: 要备份的文件路径
        
    Returns:
        备份文件的路径
    """
    backup_path = f"{file_path}.bak"
    try:
        with open(file_path, "r", encoding="utf-8") as src:
            with open(backup_path, "w", encoding="utf-8") as dst:
                dst.write(src.read())
        print(f"已备份文件: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"备份文件时出错: {e}")
        return None

def fix_constants(file_path):
    """
    修复文件中的常量值
    
    Args:
        file_path: 要修改的文件路径
        
    Returns:
        修改是否成功
    """
    try:
        # 读取文件内容
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        original_content = content
        modified = False
        
        # 修改常量值
        for const_name, new_value in CONSTANTS_TO_FIX.items():
            # 使用正则表达式匹配常量赋值语句
            pattern = r"({}\s*=\s*-?\d+)".format(const_name)
            match = re.search(pattern, content)
            
            if match:
                old_assignment = match.group(1)
                new_assignment = f"{const_name} = {new_value}"
                
                # 替换常量赋值
                content = content.replace(old_assignment, new_assignment)
                print(f"修改常量: {old_assignment} -> {new_assignment}")
                modified = True
        
        # 如果有修改，写回文件
        if modified:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"已修改文件: {file_path}")
            return True
        else:
            print(f"文件中未找到需要修改的常量: {file_path}")
            return False
            
    except Exception as e:
        print(f"修改文件时出错: {e}")
        return False

def main():
    """主函数"""
    print("Pyrogram常量修复工具")
    print("该工具修复MIN_CHANNEL_ID和MIN_CHAT_ID常量以解决PEER_ID_INVALID错误")
    print("-" * 60)
    
    # 查找utils.py文件
    utils_path = find_pyrogram_utils()
    
    if not utils_path:
        print("错误: 无法找到Pyrogram的utils.py文件")
        print("请确认已安装Pyrogram库")
        return 1
    
    print(f"找到Pyrogram utils.py: {utils_path}")
    
    # 询问用户是否继续
    print(f"将修改以下常量:")
    for const_name, new_value in CONSTANTS_TO_FIX.items():
        print(f"  {const_name} = {new_value}")
    
    confirm = input("继续操作? (y/n): ").strip().lower()
    if confirm != 'y':
        print("操作已取消")
        return 0
    
    # 备份文件
    backup_path = backup_file(utils_path)
    if not backup_path:
        print("错误: 无法备份文件，操作已取消")
        return 1
    
    # 修改常量
    if fix_constants(utils_path):
        print("-" * 60)
        print("修复成功!")
        print(f"原始文件已备份为: {backup_path}")
        print("现在可以重启使用Pyrogram的应用程序")
    else:
        print("-" * 60)
        print("修复失败!")
        print("请通过手动编辑文件修改常量值")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 