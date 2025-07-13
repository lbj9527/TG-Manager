"""
事件总线测试

测试事件总线的各种功能。
"""

import asyncio
import pytest
from unittest.mock import Mock

from core.event_bus import EventBus


class TestEventBus:
    """事件总线测试类。"""
    
    def setup_method(self):
        """每个测试方法前的设置。"""
        self.event_bus = EventBus()
        self.mock_handler = Mock()
        self.mock_async_handler = Mock()
    
    def test_register_sync_handler(self):
        """测试注册同步事件处理器。"""
        self.event_bus.on("test_event", self.mock_handler)
        
        assert "test_event" in self.event_bus._handlers
        assert self.mock_handler in self.event_bus._handlers["test_event"]
        assert len(self.event_bus._handlers["test_event"]) == 1
    
    def test_register_async_handler(self):
        """测试注册异步事件处理器。"""
        async def async_handler():
            pass
        
        self.event_bus.on("test_event", async_handler)
        
        assert "test_event" in self.event_bus._async_handlers
        assert async_handler in self.event_bus._async_handlers["test_event"]
        assert len(self.event_bus._async_handlers["test_event"]) == 1
    
    def test_emit_sync_event(self):
        """测试发射同步事件。"""
        self.event_bus.on("test_event", self.mock_handler)
        self.event_bus.emit("test_event", "arg1", "arg2", kwarg1="value1")
        
        self.mock_handler.assert_called_once_with("arg1", "arg2", kwarg1="value1")
    
    @pytest.mark.asyncio
    async def test_emit_async_event(self):
        """测试发射异步事件。"""
        async def async_handler(arg1, arg2, kwarg1=None):
            self.mock_async_handler(arg1, arg2, kwarg1)
        
        self.event_bus.on("test_event", async_handler)
        
        # 使用异步发射方法
        await self.event_bus.emit_async("test_event", "arg1", "arg2", kwarg1="value1")
        
        self.mock_async_handler.assert_called_once_with("arg1", "arg2", "value1")
    
    def test_emit_nonexistent_event(self):
        """测试发射不存在的事件。"""
        # 不应该抛出异常
        self.event_bus.emit("nonexistent_event", "arg1")
    
    def test_remove_handler(self):
        """测试移除事件处理器。"""
        self.event_bus.on("test_event", self.mock_handler)
        self.event_bus.off("test_event", self.mock_handler)
        
        assert "test_event" not in self.event_bus._handlers
    
    def test_remove_all_handlers(self):
        """测试移除所有事件处理器。"""
        self.event_bus.on("test_event", self.mock_handler)
        self.event_bus.off("test_event")
        
        assert "test_event" not in self.event_bus._handlers
    
    def test_has_handlers(self):
        """测试检查是否有事件处理器。"""
        assert not self.event_bus.has_handlers("test_event")
        
        self.event_bus.on("test_event", self.mock_handler)
        assert self.event_bus.has_handlers("test_event")
    
    def test_get_handler_count(self):
        """测试获取事件处理器数量。"""
        assert self.event_bus.get_handler_count("test_event") == 0
        
        self.event_bus.on("test_event", self.mock_handler)
        assert self.event_bus.get_handler_count("test_event") == 1
        
        # 添加另一个处理器
        another_handler = Mock()
        self.event_bus.on("test_event", another_handler)
        assert self.event_bus.get_handler_count("test_event") == 2
    
    def test_clear(self):
        """测试清空所有事件处理器。"""
        self.event_bus.on("test_event1", self.mock_handler)
        self.event_bus.on("test_event2", self.mock_handler)
        
        self.event_bus.clear()
        
        assert len(self.event_bus._handlers) == 0
        assert len(self.event_bus._async_handlers) == 0
    
    def test_get_registered_events(self):
        """测试获取已注册的事件类型。"""
        assert len(self.event_bus.get_registered_events()) == 0
        
        self.event_bus.on("test_event1", self.mock_handler)
        self.event_bus.on("test_event2", self.mock_handler)
        
        events = self.event_bus.get_registered_events()
        assert "test_event1" in events
        assert "test_event2" in events
        assert len(events) == 2
    
    def test_handler_exception(self):
        """测试事件处理器异常处理。"""
        def failing_handler():
            raise ValueError("Test error")
        
        self.event_bus.on("test_event", failing_handler)
        
        # 不应该抛出异常
        self.event_bus.emit("test_event")
    
    def test_async_handler_exception(self):
        """测试异步事件处理器异常处理。"""
        async def failing_async_handler():
            raise ValueError("Test async error")
        
        self.event_bus.on("test_event", failing_async_handler)
        
        # 创建事件循环并运行
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # 不应该抛出异常
            self.event_bus.emit("test_event")
            
            # 等待异步任务完成
            loop.run_until_complete(asyncio.sleep(0.1))
        finally:
            loop.close()
    
    @pytest.mark.asyncio
    async def test_emit_async_method(self):
        """测试异步发射事件方法。"""
        async def async_handler(arg1, arg2):
            self.mock_async_handler(arg1, arg2)
        
        self.event_bus.on("test_event", async_handler)
        
        await self.event_bus.emit_async("test_event", "arg1", "arg2")
        
        self.mock_async_handler.assert_called_once_with("arg1", "arg2")
    
    def test_multiple_handlers_same_event(self):
        """测试同一事件的多个处理器。"""
        handler1 = Mock()
        handler2 = Mock()
        
        self.event_bus.on("test_event", handler1)
        self.event_bus.on("test_event", handler2)
        
        self.event_bus.emit("test_event", "arg1")
        
        handler1.assert_called_once_with("arg1")
        handler2.assert_called_once_with("arg1")
    
    @pytest.mark.asyncio
    async def test_mixed_sync_async_handlers(self):
        """测试混合同步和异步处理器。"""
        async def async_handler(arg1):
            self.mock_async_handler(arg1)
        
        self.event_bus.on("test_event", self.mock_handler)
        self.event_bus.on("test_event", async_handler)
        
        # 使用异步发射方法
        await self.event_bus.emit_async("test_event", "arg1")
        
        self.mock_handler.assert_called_once_with("arg1")
        self.mock_async_handler.assert_called_once_with("arg1") 