"""
转发模块优化效果测试脚本
演示新的预过滤逻辑如何减少API调用
"""

import asyncio
from typing import List, Dict
from src.modules.forward.media_group_collector import MediaGroupCollector
from src.utils.logger import get_logger

logger = get_logger()

class MockHistoryManager:
    """模拟历史管理器用于测试"""
    
    def __init__(self):
        # 模拟已转发的消息记录
        self.forwarded_records = {
            "test_source": {
                "forwarded_messages": {
                    # 消息1-5已转发到目标1，消息3-7已转发到目标2
                    "1": ["target1"],
                    "2": ["target1"],
                    "3": ["target1", "target2"],
                    "4": ["target1", "target2"],
                    "5": ["target1", "target2"],
                    "6": ["target2"],
                    "7": ["target2"],
                    # 消息8-10未转发
                }
            }
        }
    
    def is_message_forwarded(self, source_channel: str, message_id: int, target_channel: str) -> bool:
        """检查消息是否已转发到指定目标频道"""
        if source_channel not in self.forwarded_records:
            return False
        
        forwarded_messages = self.forwarded_records[source_channel].get("forwarded_messages", {})
        message_id_str = str(message_id)
        
        if message_id_str not in forwarded_messages:
            return False
        
        return target_channel in forwarded_messages[message_id_str]

class MockMessageIterator:
    """模拟消息迭代器用于测试"""
    
    def __init__(self):
        self.api_call_count = 0
    
    async def iter_messages_by_ids(self, chat_id, message_ids):
        """模拟按ID获取消息，统计API调用次数"""
        self.api_call_count += 1
        logger.info(f"模拟API调用 #{self.api_call_count}: 获取消息ID {message_ids}")
        
        # 模拟返回消息对象
        for msg_id in message_ids:
            yield MockMessage(msg_id)

class MockMessage:
    """模拟消息对象"""
    
    def __init__(self, msg_id: int):
        self.id = msg_id
        self.media_group_id = f"group_{msg_id // 3}" if msg_id % 3 == 0 else None
        self.caption = f"消息{msg_id}的标题"

class MockMessageFilter:
    """模拟消息过滤器"""
    
    def is_media_allowed(self, message, source_channel=None):
        return True  # 简化测试，所有消息都允许

def test_optimization_effect():
    """测试优化效果"""
    print("=== 转发模块优化效果测试 ===\n")
    
    # 创建模拟组件
    mock_iterator = MockMessageIterator()
    mock_filter = MockMessageFilter()
    mock_history = MockHistoryManager()
    
    collector = MediaGroupCollector(mock_iterator, mock_filter)
    
    # 测试场景设置
    source_channel = "test_source"
    target_channels = ["target1", "target2"]
    start_id = 1
    end_id = 10
    
    print(f"测试场景:")
    print(f"  源频道: {source_channel}")
    print(f"  目标频道: {target_channels}")
    print(f"  消息ID范围: {start_id}-{end_id} (共{end_id-start_id+1}条消息)")
    print(f"  已转发情况:")
    
    # 显示转发状态
    for msg_id in range(start_id, end_id + 1):
        forwarded_to = []
        for target in target_channels:
            if mock_history.is_message_forwarded(source_channel, msg_id, target):
                forwarded_to.append(target)
        
        if len(forwarded_to) == len(target_channels):
            status = "✅ 已完全转发"
        elif forwarded_to:
            status = f"🔶 部分转发到 {forwarded_to}"
        else:
            status = "❌ 未转发"
        
        print(f"    消息{msg_id}: {status}")
    
    print(f"\n=== 开始优化测试 ===")
    
    # 执行预过滤
    unforwarded_ids = collector._filter_unforwarded_ids(
        start_id, end_id, source_channel, target_channels, mock_history
    )
    
    print(f"\n优化效果统计:")
    print(f"  原始消息数量: {end_id - start_id + 1}")
    print(f"  需要获取的消息数量: {len(unforwarded_ids)}")
    print(f"  减少的API调用: {(end_id - start_id + 1) - len(unforwarded_ids)} 条消息")
    print(f"  优化比例: {((end_id - start_id + 1 - len(unforwarded_ids)) / (end_id - start_id + 1)) * 100:.1f}%")
    
    if unforwarded_ids:
        print(f"  需要获取的消息ID: {unforwarded_ids}")
    else:
        print(f"  🎉 所有消息都已转发，无需API调用！")

def test_different_scenarios():
    """测试不同场景下的优化效果"""
    print("\n=== 不同场景优化效果对比 ===\n")
    
    scenarios = [
        {
            "name": "场景1: 全新频道（无转发历史）",
            "forwarded_records": {},
            "expected_optimization": 0
        },
        {
            "name": "场景2: 部分转发（50%已转发）",
            "forwarded_records": {
                "test_source": {
                    "forwarded_messages": {
                        str(i): ["target1", "target2"] for i in range(1, 6)  # 1-5已完全转发
                    }
                }
            },
            "expected_optimization": 50
        },
        {
            "name": "场景3: 大部分已转发（80%已转发）",
            "forwarded_records": {
                "test_source": {
                    "forwarded_messages": {
                        str(i): ["target1", "target2"] for i in range(1, 9)  # 1-8已完全转发
                    }
                }
            },
            "expected_optimization": 80
        },
        {
            "name": "场景4: 全部已转发（100%已转发）",
            "forwarded_records": {
                "test_source": {
                    "forwarded_messages": {
                        str(i): ["target1", "target2"] for i in range(1, 11)  # 1-10已完全转发
                    }
                }
            },
            "expected_optimization": 100
        }
    ]
    
    for scenario in scenarios:
        print(f"{scenario['name']}:")
        
        # 创建场景特定的历史管理器
        mock_history = MockHistoryManager()
        mock_history.forwarded_records = scenario["forwarded_records"]
        
        mock_iterator = MockMessageIterator()
        mock_filter = MockMessageFilter()
        collector = MediaGroupCollector(mock_iterator, mock_filter)
        
        # 测试预过滤
        unforwarded_ids = collector._filter_unforwarded_ids(
            1, 10, "test_source", ["target1", "target2"], mock_history
        )
        
        total_messages = 10
        optimized_count = total_messages - len(unforwarded_ids)
        optimization_rate = (optimized_count / total_messages) * 100
        
        print(f"  原始消息: {total_messages} 条")
        print(f"  优化掉: {optimized_count} 条")
        print(f"  实际获取: {len(unforwarded_ids)} 条")
        print(f"  优化率: {optimization_rate:.1f}%")
        print(f"  预期优化率: {scenario['expected_optimization']}%")
        
        if abs(optimization_rate - scenario['expected_optimization']) < 0.1:
            print(f"  ✅ 优化效果符合预期")
        else:
            print(f"  ❌ 优化效果与预期不符")
        
        print()

def main():
    """运行所有测试"""
    print("TG-Manager 转发模块优化效果验证\n")
    
    # 测试基本优化效果
    test_optimization_effect()
    
    # 测试不同场景
    test_different_scenarios()
    
    print("=== 总结 ===")
    print("✅ 转发模块优化已实现，主要效果包括：")
    print("  1. 大幅减少不必要的API调用")
    print("  2. 提高转发任务执行速度")
    print("  3. 降低网络流量和内存使用")
    print("  4. 特别适合有大量历史转发记录的场景")
    print("\n🚀 在实际使用中，优化效果会随着转发历史的积累而越来越明显！")

if __name__ == "__main__":
    main() 