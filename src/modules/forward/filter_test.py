"""
过滤器功能测试脚本
用于验证文本替换、关键词过滤、媒体类型过滤等功能
"""

import asyncio
from typing import List, Dict
from pyrogram.types import Message
from src.modules.forward.message_filter import MessageFilter
from src.utils.logger import get_logger

logger = get_logger()

class MockMessage:
    """模拟消息对象用于测试"""
    def __init__(self, id: int, caption: str = None, text: str = None, 
                 photo=None, video=None, document=None, audio=None, animation=None,
                 forward_from=None, reply_to_message=None, media_group_id=None):
        self.id = id
        self.caption = caption
        self.text = text
        self.photo = photo
        self.video = video
        self.document = document
        self.audio = audio
        self.animation = animation
        self.sticker = None
        self.voice = None
        self.video_note = None
        self.forward_from = forward_from
        self.reply_to_message = reply_to_message
        self.media_group_id = media_group_id

def test_keyword_filter():
    """测试关键词过滤功能"""
    print("\n=== 测试关键词过滤功能 ===")
    
    filter_obj = MessageFilter()
    
    # 创建测试消息
    messages = [
        MockMessage(1, caption="这是一个包含关键词的消息"),
        MockMessage(2, text="普通文本消息，没有特殊内容"),
        MockMessage(3, caption="另一个关键词消息"),
        MockMessage(4, text="不相关的内容"),
    ]
    
    keywords = ["关键词"]
    
    passed, filtered = filter_obj.apply_keyword_filter(messages, keywords)
    
    print(f"原始消息数: {len(messages)}")
    print(f"通过的消息: {len(passed)} 条")
    print(f"被过滤的消息: {len(filtered)} 条")
    
    for msg in passed:
        print(f"  通过: [ID: {msg.id}] {msg.caption or msg.text}")
    
    for msg in filtered:
        print(f"  过滤: [ID: {msg.id}] {msg.caption or msg.text}")

def test_media_type_filter():
    """测试媒体类型过滤功能"""
    print("\n=== 测试媒体类型过滤功能 ===")
    
    filter_obj = MessageFilter()
    
    # 创建测试消息
    messages = [
        MockMessage(1, caption="照片消息", photo=True),
        MockMessage(2, caption="视频消息", video=True),
        MockMessage(3, caption="文档消息", document=True),
        MockMessage(4, text="纯文本消息"),
        MockMessage(5, caption="音频消息", audio=True),
    ]
    
    allowed_types = ["photo", "video"]
    
    passed, filtered = filter_obj.apply_media_type_filter(messages, allowed_types)
    
    print(f"允许的媒体类型: {allowed_types}")
    print(f"原始消息数: {len(messages)}")
    print(f"通过的消息: {len(passed)} 条")
    print(f"被过滤的消息: {len(filtered)} 条")
    
    for msg in passed:
        media_type = filter_obj._get_message_media_type(msg)
        print(f"  通过: [ID: {msg.id}] {media_type} - {msg.caption or msg.text}")
    
    for msg in filtered:
        media_type = filter_obj._get_message_media_type(msg)
        print(f"  过滤: [ID: {msg.id}] {media_type} - {msg.caption or msg.text}")

def test_text_replacement():
    """测试文本替换功能"""
    print("\n=== 测试文本替换功能 ===")
    
    filter_obj = MessageFilter()
    
    test_texts = [
        "这是原始文本内容",
        "包含旧词汇的句子",
        "需要替换的内容在这里",
        "没有需要替换的内容",
    ]
    
    replacements = {
        "原始": "新的",
        "旧词汇": "新词汇",
        "替换": "修改"
    }
    
    print(f"替换规则: {replacements}")
    
    for text in test_texts:
        new_text, has_replacement = filter_obj.apply_text_replacements(text, replacements)
        status = "✓ 已替换" if has_replacement else "✗ 无替换"
        print(f"  {status}: '{text}' -> '{new_text}'")

def test_general_filters():
    """测试通用过滤规则"""
    print("\n=== 测试通用过滤规则 ===")
    
    filter_obj = MessageFilter()
    
    # 创建测试消息
    messages = [
        MockMessage(1, text="普通消息"),
        MockMessage(2, text="转发消息", forward_from=True),
        MockMessage(3, text="回复消息", reply_to_message=True),
        MockMessage(4, text="包含链接 https://example.com"),
        MockMessage(5, text="纯文本消息（无媒体）"),
        MockMessage(6, caption="媒体消息", photo=True),
    ]
    
    # 测试配置
    pair_configs = [
        {"exclude_forwards": True},
        {"exclude_replies": True},
        {"exclude_links": True},
        {"exclude_text": True},
    ]
    
    for config in pair_configs:
        config_name = ", ".join([k for k, v in config.items() if v])
        print(f"\n过滤规则: {config_name}")
        
        passed, filtered = filter_obj.apply_general_filters(messages, config)
        
        print(f"  通过: {len(passed)} 条，过滤: {len(filtered)} 条")
        for msg in filtered:
            print(f"    过滤: [ID: {msg.id}] {msg.text or msg.caption}")

def test_all_filters():
    """测试综合过滤功能"""
    print("\n=== 测试综合过滤功能 ===")
    
    filter_obj = MessageFilter()
    
    # 创建测试消息
    messages = [
        MockMessage(1, caption="包含关键词的照片", photo=True),
        MockMessage(2, caption="普通视频内容", video=True),
        MockMessage(3, caption="包含关键词的文档", document=True),
        MockMessage(4, text="纯文本关键词消息"),
        MockMessage(5, caption="不相关的照片", photo=True),
        MockMessage(6, text="转发消息内容", forward_from=True),
    ]
    
    # 综合配置
    pair_config = {
        "keywords": ["关键词"],
        "media_types": ["photo", "video"],
        "exclude_forwards": True,
        "exclude_text": True,
    }
    
    print(f"综合配置: {pair_config}")
    
    passed, filtered, stats = filter_obj.apply_all_filters(messages, pair_config)
    
    print(f"过滤统计: {stats}")
    print(f"最终通过: {len(passed)} 条")
    
    for msg in passed:
        media_type = filter_obj._get_message_media_type(msg) or "text"
        print(f"  通过: [ID: {msg.id}] {media_type} - {msg.caption or msg.text}")

def test_media_group_keyword_filter():
    """测试媒体组级别的关键词过滤"""
    print("=== 测试媒体组级别的关键词过滤 ===")
    
    from src.modules.forward.message_filter import MessageFilter
    
    # 创建过滤器
    filter_obj = MessageFilter()
    
    # 创建模拟的媒体组消息
    media_group_id = "test_media_group_123"
    
    # 媒体组1：包含关键词的媒体组
    message1 = MockMessage(id=101, caption="这是一个双马尾美女的照片", media_group_id=media_group_id)
    message2 = MockMessage(id=102, caption="第二张照片", media_group_id=media_group_id)
    message3 = MockMessage(id=103, caption="第三张照片", media_group_id=media_group_id)
    
    # 媒体组2：不包含关键词的媒体组
    media_group_id2 = "test_media_group_456"
    message4 = MockMessage(id=201, caption="普通照片1", media_group_id=media_group_id2)
    message5 = MockMessage(id=202, caption="普通照片2", media_group_id=media_group_id2)
    
    # 单独消息：包含关键词
    message6 = MockMessage(id=301, caption="另一个双马尾美女视频")
    
    # 单独消息：不包含关键词
    message7 = MockMessage(id=401, caption="不相关的内容")
    
    # 测试消息列表
    test_messages = [message1, message2, message3, message4, message5, message6, message7]
    keywords = ["双马尾美女"]
    
    print(f"测试消息: {len(test_messages)} 条")
    print(f"媒体组1 (包含关键词): [ID: 101, 102, 103] - '{message1.caption}', '{message2.caption}', '{message3.caption}'")
    print(f"媒体组2 (不含关键词): [ID: 201, 202] - '{message4.caption}', '{message5.caption}'")
    print(f"单独消息 (包含关键词): [ID: 301] - '{message6.caption}'")
    print(f"单独消息 (不含关键词): [ID: 401] - '{message7.caption}'")
    print(f"关键词: {keywords}")
    
    # 应用关键词过滤
    passed_messages, filtered_messages = filter_obj.apply_keyword_filter(test_messages, keywords)
    
    print(f"\n结果:")
    print(f"通过的消息: {len(passed_messages)} 条")
    passed_ids = [msg.id for msg in passed_messages]
    print(f"通过的消息ID: {passed_ids}")
    
    print(f"被过滤的消息: {len(filtered_messages)} 条")
    filtered_ids = [msg.id for msg in filtered_messages]
    print(f"被过滤的消息ID: {filtered_ids}")
    
    # 验证结果
    expected_passed = [101, 102, 103, 301]  # 媒体组1整体通过 + 单独消息通过
    expected_filtered = [201, 202, 401]     # 媒体组2整体被过滤 + 单独消息被过滤
    
    if set(passed_ids) == set(expected_passed) and set(filtered_ids) == set(expected_filtered):
        print("✅ 媒体组级别关键词过滤测试通过！")
        print("   - 包含关键词的媒体组整体通过")
        print("   - 不含关键词的媒体组整体被过滤")
        print("   - 单独消息按关键词正确过滤")
    else:
        print("❌ 媒体组级别关键词过滤测试失败！")
        print(f"   预期通过: {expected_passed}")
        print(f"   实际通过: {passed_ids}")
        print(f"   预期过滤: {expected_filtered}")
        print(f"   实际过滤: {filtered_ids}")
    
    print()

def main():
    """运行过滤器测试"""
    print("=== TG-Manager 消息过滤器测试 ===\n")
    
    # 测试关键词过滤功能
    test_keyword_filter()
    
    # 测试媒体组级别的关键词过滤
    test_media_group_keyword_filter()
    
    # 测试媒体类型过滤功能
    test_media_type_filter()
    
    # 测试文本替换功能
    test_text_replacement()
    
    # 测试通用过滤功能
    test_general_filters()
    
    # 测试综合过滤功能
    test_all_filters()
    
    print("=== 所有测试完成 ===")

def test_keyword_configuration():
    """测试关键词配置的诊断工具"""
    print("=== 关键词过滤配置诊断 ===")
    
    # 模拟用户配置检查
    test_configs = [
        {
            "name": "无关键词配置",
            "config": {},
            "expected": "应该显示：未设置关键词过滤"
        },
        {
            "name": "空关键词列表",
            "config": {"keywords": []},
            "expected": "应该显示：未设置关键词过滤"
        },
        {
            "name": "正确关键词配置",
            "config": {"keywords": ["测试", "关键词"]},
            "expected": "应该显示：已设置关键词过滤"
        }
    ]
    
    for test in test_configs:
        print(f"\n测试场景: {test['name']}")
        keywords = test['config'].get('keywords', [])
        if keywords:
            print(f"✅ 已设置关键词过滤: {keywords}")
        else:
            print(f"❌ 未设置关键词过滤，将转发所有消息")
        print(f"预期结果: {test['expected']}")

if __name__ == "__main__":
    main()
    # 运行关键词配置诊断
    test_keyword_configuration() 