#!/usr/bin/env python3
"""
qasync测试脚本 - 验证Qt与asyncio的集成
"""

import sys
import asyncio
from PySide6.QtWidgets import (QApplication, QMainWindow, QPushButton, 
                              QVBoxLayout, QLabel, QWidget, QTextEdit)
from PySide6.QtCore import QTimer, Signal, Slot, QObject
from loguru import logger
import time

# 导入我们实现的qasync工具
from src.utils.async_utils import (
    create_task, safe_sleep, qt_connect_async, run_qt_asyncio, init_qasync_loop
)


class AsyncWorker(QObject):
    """异步工作类，模拟耗时操作"""
    progress_updated = Signal(str)
    work_finished = Signal(str)
    
    def __init__(self):
        super().__init__()
        self.running = False
    
    async def do_work(self, seconds=5):
        """模拟耗时工作"""
        self.running = True
        for i in range(seconds):
            if not self.running:
                break
            self.progress_updated.emit(f"进行中... {i+1}/{seconds}")
            await safe_sleep(1)
        
        self.work_finished.emit(f"工作完成！用时 {seconds} 秒")
        self.running = False
    
    def stop_work(self):
        """停止工作"""
        self.running = False


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("qasync测试")
        self.setGeometry(100, 100, 400, 300)
        
        # 创建中央部件和布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 状态显示
        self.status_label = QLabel("就绪")
        layout.addWidget(self.status_label)
        
        # 日志显示区域
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        layout.addWidget(self.log_area)
        
        # 启动按钮
        self.start_button = QPushButton("启动测试任务")
        self.start_button.clicked.connect(self.on_start_clicked)
        layout.addWidget(self.start_button)
        
        # 网络测试按钮
        self.network_button = QPushButton("测试网络请求")
        self.network_button.clicked.connect(self.on_network_clicked)
        layout.addWidget(self.network_button)
        
        # 停止按钮
        self.stop_button = QPushButton("停止")
        self.stop_button.clicked.connect(self.on_stop_clicked)
        self.stop_button.setEnabled(False)
        layout.addWidget(self.stop_button)
        
        # 创建异步工作器
        self.worker = AsyncWorker()
        self.worker.progress_updated.connect(self.update_status)
        self.worker.work_finished.connect(self.on_work_finished)
        
        # 设置定时器更新时间
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)  # 每秒更新一次
        
        # 添加日志输出
        self.log("应用程序初始化完成")
    
    @Slot()
    def on_start_clicked(self):
        """启动按钮点击处理"""
        self.log("启动测试任务")
        self.start_button.setEnabled(False)
        self.network_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        
        # 使用qt_connect_async连接信号到异步函数
        create_task(self.worker.do_work(10))
    
    @Slot()
    def on_network_clicked(self):
        """网络测试按钮点击处理"""
        self.log("开始网络请求测试")
        self.start_button.setEnabled(False)
        self.network_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        
        create_task(self.test_network_request())
    
    async def test_network_request(self):
        """测试网络请求"""
        self.log("准备发送网络请求...")
        try:
            import aiohttp
            start_time = time.time()
            
            async with aiohttp.ClientSession() as session:
                self.log("正在请求 https://www.example.com")
                async with session.get("https://www.example.com") as response:
                    elapsed = time.time() - start_time
                    status = response.status
                    self.log(f"请求完成，状态码: {status}，耗时: {elapsed:.2f}秒")
                    
                    if status == 200:
                        text = await response.text()
                        self.log(f"接收到 {len(text)} 字节的数据")
        except Exception as e:
            self.log(f"网络请求出错: {e}")
        
        self.start_button.setEnabled(True)
        self.network_button.setEnabled(True)
        self.stop_button.setEnabled(False)
    
    @Slot()
    def on_stop_clicked(self):
        """停止按钮点击处理"""
        self.log("停止任务")
        self.worker.stop_work()
        
        self.start_button.setEnabled(True)
        self.network_button.setEnabled(True)
        self.stop_button.setEnabled(False)
    
    @Slot(str)
    def update_status(self, status):
        """更新状态"""
        self.status_label.setText(status)
        self.log(status)
    
    @Slot(str)
    def on_work_finished(self, message):
        """工作完成处理"""
        self.log(message)
        self.status_label.setText(message)
        
        self.start_button.setEnabled(True)
        self.network_button.setEnabled(True)
        self.stop_button.setEnabled(False)
    
    @Slot()
    def update_time(self):
        """更新时间显示"""
        current_time = time.strftime("%H:%M:%S")
        self.setWindowTitle(f"qasync测试 - {current_time}")
    
    def log(self, message):
        """添加日志"""
        timestamp = time.strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        self.log_area.append(log_message)
        # 滚动到底部
        self.log_area.verticalScrollBar().setValue(
            self.log_area.verticalScrollBar().maximum()
        )
        # 同时使用loguru记录
        logger.info(message)


async def main_async():
    """异步主函数"""
    # 初始化
    logger.info("应用程序启动")
    
    window = MainWindow()
    window.show()
    
    # 保持窗口运行
    while True:
        await safe_sleep(0.1)


def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 使用run_qt_asyncio运行，传递协程函数而不是协程对象
    sys.exit(run_qt_asyncio(app, main_async))


if __name__ == "__main__":
    main() 