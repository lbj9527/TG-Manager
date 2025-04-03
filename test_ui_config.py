"""
测试UI配置管理器
"""

import json
import sys
from pathlib import Path

# 添加项目根目录到Python路径，确保能导入模块
sys.path.append(str(Path(__file__).parent))

from src.utils.ui_config_manager import UIConfigManager
from src.utils.ui_config_models import create_default_config

def main():
    """测试UI配置管理器"""
    print("=== 测试UI配置管理器 ===")
    
    config_path = "config.json"
    print(f"配置文件路径: {config_path}")
    
    # 创建UI配置管理器
    uicm = UIConfigManager(config_path)
    print("UI配置管理器创建成功")
    
    # 加载配置
    ui_config = uicm.get_ui_config()
    print("配置加载成功")
    
    # 打印主题信息
    print(f"UI主题: {ui_config.UI.theme}")
    print(f"窗口几何信息是否存在: {'是' if ui_config.UI.window_geometry else '否'}")
    print(f"窗口状态信息是否存在: {'是' if ui_config.UI.window_state else '否'}")
    
    # 打印完整配置结构
    print("\n配置结构:")
    for section in ["GENERAL", "DOWNLOAD", "UPLOAD", "FORWARD", "MONITOR", "UI"]:
        if hasattr(ui_config, section):
            section_data = getattr(ui_config, section)
            print(f"  {section}: {type(section_data).__name__}")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    main() 