# barcode_scanner.py
import serial
import time
import select
import threading
from datetime import datetime


class BarCodeScanner:
    def __init__(self, port, baudrate=9600, timeout=1.0):
        """初始化条码扫描器"""
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_port = None
        self.running = False
        self.barcode_queue = []
        self.lock = threading.Lock()
        self.callback = None

    def open(self):
        """打开串口"""
        try:
            self.serial_port = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            print(f"条码扫描器串口 {self.port} 已打开，波特率: {self.baudrate}")
            return True
        except serial.SerialException as e:
            print(f"打开条码扫描器串口失败: {e}")
            return False
        except Exception as e:
            print(f"条码扫描器初始化异常: {e}")
            return False

    def close(self):
        """关闭串口"""
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            print(f"条码扫描器串口 {self.port} 已关闭")

    def is_open(self):
        """检查串口是否打开"""
        return self.serial_port and self.serial_port.is_open

    def receive_data(self, max_length=100, timeout=0.1):
        """
        接收串口数据

        返回: (data_bytes, data_length)
        """
        if not self.is_open():
            return None, 0

        try:
            received_data = bytearray()
            start_time = time.time()

            while len(received_data) < max_length:
                # 检查是否超时
                if time.time() - start_time > timeout:
                    break

                # 使用更短的超时时间
                ready, _, _ = select.select([self.serial_port], [], [], 0.05)  # 50ms超时

                if ready:
                    # 一次性读取所有可用数据
                    available = self.serial_port.in_waiting
                    if available > 0:
                        chunk = self.serial_port.read(min(available, max_length - len(received_data)))
                        received_data.extend(chunk)
                else:
                    # 如果没有数据，检查是否应该继续等待
                    if len(received_data) > 0:
                        # 如果已经有部分数据，立即返回
                        break

            return received_data, len(received_data)

        except Exception as e:
            print(f"条码扫描器接收数据错误: {e}")
            return None, 0

    def process_received_data(self, data_bytes, data_length):
        """
        处理接收到的条码数据

        返回: 处理后的条码字符串 或 None
        """
        if not data_bytes or data_length == 0:
            return None

        try:
            # 1. 将字节数据转换为字符串
            # 条码扫描器通常发送ASCII码
            barcode_str = data_bytes.decode('ascii', errors='ignore').strip()

            if not barcode_str:
                return None

            # 2. 清理字符串
            # 移除控制字符
            barcode_str = ''.join(char for char in barcode_str if char.isprintable())

            # 3. 检查条码格式
            # 假设条码至少3位，最多50位
            if len(barcode_str) < 3 or len(barcode_str) > 50:
                print(f"条码长度异常: {barcode_str} (长度: {len(barcode_str)})")
                return None

            # 4. 记录日志
            self.log_barcode(barcode_str)

            return barcode_str

        except UnicodeDecodeError as e:
            print(f"条码数据解码错误: {e}")
            return None
        except Exception as e:
            print(f"处理条码数据异常: {e}")
            return None

    def add_barcode(self, barcode):
        """添加条码到队列"""
        with self.lock:
            if barcode and barcode not in self.barcode_queue:
                self.barcode_queue.append(barcode)
                # 限制队列大小
                if len(self.barcode_queue) > 1000:
                    self.barcode_queue.pop(0)

    def get_barcode(self):
        """获取一个条码"""
        with self.lock:
            if self.barcode_queue:
                return self.barcode_queue.pop(0)
        return None

    def get_all_barcodes(self):
        """获取所有条码"""
        with self.lock:
            barcodes = self.barcode_queue.copy()
            self.barcode_queue.clear()
            return barcodes

    def set_callback(self, callback_func):
        """设置条码接收回调函数"""
        self.callback = callback_func

    def start_receive_loop(self):
        """启动接收循环"""
        if not self.is_open():
            print("条码扫描器未打开，无法启动接收循环")
            return False

        self.running = True
        self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.receive_thread.start()
        print("条码扫描器接收循环已启动")
        return True

    def stop_receive_loop(self):
        """停止接收循环"""
        self.running = False
        if hasattr(self, 'receive_thread') and self.receive_thread.is_alive():
            self.receive_thread.join(timeout=2.0)
        print("条码扫描器接收循环已停止")

    def _receive_loop(self):
        """内部接收循环"""
        print("进入条码扫描器接收循环")

        while self.running:
            try:
                # 接收数据
                data, length = self.receive_data(max_length=100, timeout=0.1)

                if data and length > 0:
                    # 处理条码数据
                    barcode = self.process_received_data(data, length)

                    if barcode:
                        # 添加到队列
                        self.add_barcode(barcode)

                        # 调用回调函数
                        if self.callback:
                            self.callback(barcode)

                        print(f"[BarcodeScanner] 接收到条码: {barcode}")

            except Exception as e:
                print(f"条码扫描器接收循环错误: {e}")
                time.sleep(1)  # 错误时稍作等待

    def log_barcode(self, barcode):
        """记录条码到日志文件"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"{timestamp},{barcode}\n"

            # 保存到文件
            log_file = f"barcode_log_{datetime.now().strftime('%Y%m%d')}.csv"
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)

        except Exception as e:
            print(f"记录条码日志错误: {e}")

    def get_stats(self):
        """获取统计信息"""
        with self.lock:
            return {
                'queue_size': len(self.barcode_queue),
                'port': self.port,
                'baudrate': self.baudrate,
                'is_open': self.is_open(),
                'is_running': self.running
            }