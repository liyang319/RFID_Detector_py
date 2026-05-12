# RFIDReader_SFM2200.py
import serial
import threading
import time
from datetime import datetime


class RFIDReader_SFM2200:
    def __init__(self, port='/dev/ttyUSB0', baudrate=115200, timeout=1.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_port = None
        self.running = False
        self.receive_thread = None
        self.callback = None
        self.lock = threading.Lock()

    def open(self):
        try:
            self.serial_port = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            print(f"RFID读写器串口 {self.port} 已打开，波特率: {self.baudrate}")
            return True
        except Exception as e:
            print(f"打开RFID读写器串口失败: {e}")
            return False

    def close(self):
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            print(f"RFID读写器串口 {self.port} 已关闭")

    def is_open(self):
        return self.serial_port and self.serial_port.is_open

    def send_command(self, data: bytes) -> bool:
        if not self.is_open():
            print("RFID读写器未打开，无法发送指令")
            return False
        try:
            self.serial_port.write(data)
            hex_str = ' '.join(f'{b:02X}' for b in data)
            print(f"发送指令: {hex_str}")
            return True
        except Exception as e:
            print(f"发送指令失败: {e}")
            return False

    def receive_response(self, timeout=0.5):
        """等待设备返回数据，超时则返回已收到的数据"""
        if not self.is_open():
            return b''
        try:
            end_time = time.time() + timeout
            received = bytearray()
            while time.time() < end_time:
                data = self.serial_port.read(256)
                if data:
                    received.extend(data)
                else:
                    time.sleep(0.01)
            if received:
                hex_str = ' '.join(f'{b:02X}' for b in received)
                print(f"收到响应: {hex_str}")
            else:
                print("未收到响应（超时）")
            return bytes(received)
        except Exception as e:
            print(f"接收响应失败: {e}")
            return b''

    # ---------- 新增方法：启动固件 ----------
    def start_firmware(self):
        """发送固件启动指令: FF 00 04 1D 0B"""
        print("调用 RFIDReader_SFM2200.start_firmware()")
        cmd = bytes([0xFF, 0x00, 0x04, 0x1D, 0x0B])
        self.send_command(cmd)
        self.receive_response(timeout=0.5)
        return True

    # ---------- 修改：startloop仅发送长指令 ----------
    def startloop(self):
        """启动循环读取：仅发送长指令"""
        print("调用 RFIDReader_SFM2200.startloop()")
        cmd = bytes([
            0xFF, 0x1F, 0xAA, 0x4D, 0x6F, 0x64, 0x75, 0x6C, 0x65, 0x74, 0x65, 0x63, 0x68,
            0xAA, 0x48, 0x00, 0x96, 0x00, 0x80, 0x04, 0x01, 0x09, 0x28, 0x00, 0x00, 0x00,
            0x03, 0x00, 0x00, 0x00, 0x04, 0x0A, 0x4F, 0xBB, 0xFF, 0x45
        ])
        self.send_command(cmd)
        self.receive_response(timeout=0.5)
        return True

    def stoploop(self):
        """停止循环读取"""
        print("调用 RFIDReader_SFM2200.stoploop()")
        cmd = bytes([
            0xFF, 0x0E, 0xAA, 0x4D, 0x6F, 0x64, 0x75, 0x6C, 0x65, 0x74, 0x65, 0x63, 0x68,
            0xAA, 0x49, 0xF3, 0xBB, 0x03, 0x91
        ])
        self.send_command(cmd)
        self.receive_response(timeout=0.5)
        return True

    # -------------------- 可选：接收数据支持 --------------------
    def set_callback(self, callback_func):
        self.callback = callback_func

    def start_receive_loop(self):
        if not self.is_open():
            print("RFID读写器未打开，无法启动接收循环")
            return False
        if self.running:
            return True
        self.running = True
        self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.receive_thread.start()
        print("RFID读写器接收循环已启动")
        return True

    def stop_receive_loop(self):
        self.running = False
        if self.receive_thread and self.receive_thread.is_alive():
            self.receive_thread.join(timeout=2.0)
        print("RFID读写器接收循环已停止")

    def _receive_loop(self):
        print("进入 RFID 读写器接收循环")
        while self.running:
            try:
                data = self.serial_port.read(1024)
                if data:
                    if self.callback:
                        self.callback(data)
                    else:
                        hex_str = ' '.join(f'{b:02X}' for b in data)
                        print(f"RFID收到数据: {hex_str}")
                else:
                    time.sleep(0.05)
            except Exception as e:
                print(f"RFID读写器接收循环错误: {e}")
                time.sleep(0.5)

    def log_data(self, data_bytes):
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            hex_str = ' '.join(f'{b:02X}' for b in data_bytes)
            with open("rfid_reader_log.txt", "a") as f:
                f.write(f"{timestamp} - {hex_str}\n")
        except Exception as e:
            print(f"记录日志失败: {e}")