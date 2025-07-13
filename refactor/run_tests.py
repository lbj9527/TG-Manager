#!/usr/bin/env python3
"""
测试运行器

自动添加项目根目录到 sys.path，解决模块导入问题。
"""

import sys
import os
from pathlib import Path

# 获取项目根目录
project_root = Path(__file__).parent.absolute()

# 添加项目根目录到 Python 路径
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 设置包结构
os.environ['PYTHONPATH'] = str(project_root)

def main():
    """主函数"""
    import pytest
    
    # 运行测试
    pytest.main([
        'tests',
        '-v',
        '--tb=short',
        '--strict-markers',
        '--disable-warnings'
    ])

if __name__ == '__main__':
    main() 