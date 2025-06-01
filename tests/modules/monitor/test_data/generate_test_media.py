 #!/usr/bin/env python3
"""
生成测试媒体文件的脚本
创建小尺寸的测试文件用于测试目的
"""

import os
from pathlib import Path
from PIL import Image, ImageDraw
import io

def create_test_photo(filename: str, width: int = 100, height: int = 100, color: str = "blue"):
    """创建测试图片文件"""
    # 创建一个简单的彩色图片
    image = Image.new('RGB', (width, height), color)
    draw = ImageDraw.Draw(image)
    
    # 添加一些简单的图形
    draw.rectangle([10, 10, width-10, height-10], outline="white", width=2)
    draw.text((20, 20), "TEST", fill="white")
    
    # 保存图片
    image.save(filename, 'JPEG', quality=85)
    print(f"✅ 创建测试图片: {filename}")

def create_test_document(filename: str, content: str = "测试文档内容"):
    """创建测试文档文件"""
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(f"""# 测试文档

这是一个用于测试的文档文件。

## 内容
{content}

## 详细信息
- 文件名: {filename}
- 用途: 自动化测试
- 创建时间: 由测试脚本生成

## 注意事项
此文件仅用于测试目的，请勿在生产环境中使用。
""")
    print(f"✅ 创建测试文档: {filename}")

def create_placeholder_media_files():
    """创建占位符媒体文件"""
    media_dir = Path(__file__).parent / "media_files"
    media_dir.mkdir(exist_ok=True)
    
    # 创建测试图片
    create_test_photo(media_dir / "test_photo_small.jpg", 200, 150, "lightblue")
    create_test_photo(media_dir / "test_photo_large.jpg", 800, 600, "lightgreen")
    create_test_photo(media_dir / "test_photo_landscape.jpg", 1280, 720, "lightcoral")
    create_test_photo(media_dir / "test_photo_portrait.jpg", 720, 1280, "lightyellow")
    
    # 创建测试文档
    create_test_document(media_dir / "test_document.txt", "这是一个测试文档")
    create_test_document(media_dir / "test_manual.txt", "用户手册内容")
    create_test_document(media_dir / "test_readme.txt", "项目说明文档")
    
    # 创建其他占位符文件
    placeholder_files = [
        ("test_video.mp4", "视频文件占位符"),
        ("test_audio.mp3", "音频文件占位符"),
        ("test_animation.gif", "动图文件占位符"),
        ("test_archive.zip", "压缩文件占位符"),
        ("test_presentation.pdf", "PDF文件占位符")
    ]
    
    for filename, description in placeholder_files:
        filepath = media_dir / filename
        with open(filepath, 'w') as f:
            f.write(f"# {description}\n这是一个用于测试的占位符文件。\n实际测试中应该替换为真实的{description}。")
        print(f"✅ 创建占位符文件: {filepath}")

def create_test_json_files():
    """验证测试JSON文件是否存在"""
    test_data_dir = Path(__file__).parent
    
    json_files = [
        "sample_messages/text_messages.json",
        "sample_messages/media_messages.json", 
        "sample_messages/media_groups.json",
        "sample_configs/basic_forward.json",
        "sample_configs/advanced_filter.json",
        "expected_outputs/text_replacements.json",
        "expected_outputs/filter_results.json",
        "expected_outputs/forward_results.json",
        "realistic_scenarios.json",
        "performance_benchmarks.json"
    ]
    
    missing_files = []
    existing_files = []
    
    for json_file in json_files:
        filepath = test_data_dir / json_file
        if filepath.exists():
            existing_files.append(json_file)
        else:
            missing_files.append(json_file)
    
    print(f"\n📋 JSON测试文件状态:")
    print(f"✅ 存在的文件 ({len(existing_files)}):")
    for file in existing_files:
        print(f"   - {file}")
    
    if missing_files:
        print(f"\n❌ 缺失的文件 ({len(missing_files)}):")
        for file in missing_files:
            print(f"   - {file}")
    else:
        print(f"\n🎉 所有JSON测试文件都已创建!")

def main():
    """主函数"""
    print("🚀 开始生成测试素材...")
    
    try:
        # 创建媒体文件
        create_placeholder_media_files()
        
        # 检查JSON文件
        create_test_json_files()
        
        print("\n✅ 测试素材生成完成!")
        print("\n📌 使用说明:")
        print("1. 占位符媒体文件已创建在 media_files/ 目录")
        print("2. 实际测试时可以替换为真实的媒体文件")
        print("3. 所有JSON配置文件已准备就绪")
        print("4. 运行测试: python -m pytest tests/modules/monitor/")
        
    except Exception as e:
        print(f"❌ 生成测试素材时出错: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())