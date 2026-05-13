# RFIDReader_SFM2200.py
import serial
import threading
import time
import queue
from datetime import datetime


class RFIDReader_SFM2200:
    """
    基于串口的 SFM2200 RFID 读写器类
    提供基础串口操作、CRC计算、指令封装、标签读写等功能
    """

    def __init__(self, port='/dev/ttyUSB0', baudrate=115200, timeout=1.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_port = None
        self.running = False          # 接收循环运行标志
        self.receive_thread = None
        self.callback = None          # 异步数据接收回调函数
        self.lock = threading.Lock()
        self.response_queue = queue.Queue(maxsize=100)   # 响应队列

    # -------------------- 基础串口操作 --------------------
    def open(self):
        """打开串口"""
        try:
            self.serial_port = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            print(f"RFID读写器串口 {self.port} 已打开，波特率: {self.baudrate}")
            return True
        except serial.SerialException as e:
            print(f"打开RFID读写器串口失败: {e}")
            return False
        except Exception as e:
            print(f"RFID读写器初始化异常: {e}")
            return False

    def close(self):
        """关闭串口"""
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            print(f"RFID读写器串口 {self.port} 已关闭")

    def is_open(self):
        """检查串口是否打开"""
        return self.serial_port and self.serial_port.is_open

    def send_command(self, data: bytes) -> bool:
        """发送二进制指令"""
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

    # -------------------- CRC 相关 --------------------
    def calc_crc(self, data: bytes) -> int:
        """
        计算 CRC-16/CCITT-FALSE，初始值 0xFFFF，多项式 0x1021。
        从下标 1 开始计算（忽略 data[0]）。
        """
        crc = 0xFFFF
        for i in range(1, len(data)):
            byte_val = data[i]
            for bit in range(7, -1, -1):
                xor_flag = (crc >> 15) & 1
                crc = (crc << 1) | ((byte_val >> bit) & 1)
                if xor_flag:
                    crc ^= 0x1021
        return crc & 0xFFFF

    def get_cmd_append_crc(self, data: bytes, little_endian: bool = False) -> bytes:
        """
        计算 data 的 CRC，并附加到 data 末尾返回。
        :param data: 原始指令（不含 CRC）
        :param little_endian: True 表示 CRC 低字节在前，False 表示高字节在前（默认大端）
        """
        crc = self.calc_crc(data)
        if little_endian:
            crc_bytes = crc.to_bytes(2, 'little')
        else:
            crc_bytes = crc.to_bytes(2, 'big')
        return data + crc_bytes

    # -------------------- 响应处理（基于队列，避免与接收循环冲突） --------------------
    def clear_response_queue(self):
        """清空响应队列（丢弃残留数据）"""
        while not self.response_queue.empty():
            try:
                self.response_queue.get_nowait()
            except queue.Empty:
                break

    def receive_response(self, timeout=0.5) -> bytes:
        """
        从队列中获取一个响应数据包（超时返回空字节串）
        """
        try:
            data = self.response_queue.get(timeout=timeout)
            if data:
                hex_str = ' '.join(f'{b:02X}' for b in data)
                print(f"收到响应: {hex_str}")
                return data
            else:
                return b''
        except queue.Empty:
            print("未收到响应（超时）")
            return b''

    # -------------------- 接收循环（后台线程） --------------------
    def set_callback(self, callback_func):
        """设置异步数据接收回调函数"""
        self.callback = callback_func

    def start_receive_loop(self):
        """启动后台接收线程"""
        if not self.is_open():
            print("RFID读写器未打开，无法启动接收循环")
            return False
        if self.running:
            print("接收循环已在运行")
            return True
        self.running = True
        self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.receive_thread.start()
        print("RFID读写器接收循环已启动")
        return True

    def stop_receive_loop(self):
        """停止接收循环"""
        self.running = False
        if self.receive_thread and self.receive_thread.is_alive():
            self.receive_thread.join(timeout=2.0)
        print("RFID读写器接收循环已停止")

    def _receive_loop(self):
        """内部接收循环，将数据放入队列并调用回调"""
        print("进入 RFID 读写器接收循环")
        while self.running:
            try:
                data = self.serial_port.read(1024)
                if data:
                    # 放入队列
                    self.response_queue.put(data)
                    # 调用回调（如果设置）
                    if self.callback:
                        self.callback(data)
                else:
                    time.sleep(0.05)
            except Exception as e:
                print(f"RFID读写器接收循环错误: {e}")
                time.sleep(0.5)

    # -------------------- 高层指令 --------------------
    def start_firmware(self):
        """发送固件启动指令: FF 00 04 1D 0B"""
        print("调用 RFIDReader_SFM2200.start_firmware()")
        self.clear_response_queue()
        cmd = bytes([0xFF, 0x00, 0x04, 0x1D, 0x0B])
        self.send_command(cmd)
        self.receive_response(timeout=5)
        return True

    def startloop(self):
        """启动循环读取：发送长指令"""
        print("调用 RFIDReader_SFM2200.startloop()")
        self.clear_response_queue()
        cmd = bytes([
            0xFF, 0x1F, 0xAA, 0x4D, 0x6F, 0x64, 0x75, 0x6C, 0x65, 0x74, 0x65, 0x63, 0x68,
            0xAA, 0x48, 0x00, 0x96, 0x00, 0x80, 0x04, 0x01, 0x09, 0x28, 0x00, 0x00, 0x00,
            0x03, 0x00, 0x00, 0x00, 0x04, 0x0A, 0x4F, 0xBB, 0xFF, 0x45
        ])
        self.send_command(cmd)
        self.receive_response(timeout=0.5)
        return True

    def stoploop(self):
        """发送停止循环读取指令"""
        print("调用 RFIDReader_SFM2200.stoploop()")
        self.clear_response_queue()
        cmd = bytes([
            0xFF, 0x0E, 0xAA, 0x4D, 0x6F, 0x64, 0x75, 0x6C, 0x65, 0x74, 0x65, 0x63, 0x68,
            0xAA, 0x49, 0xF3, 0xBB, 0x03, 0x91
        ])
        self.send_command(cmd)
        self.receive_response(timeout=0.5)
        return True

    def write_tag_with_userdata(self, userdata: bytes) -> bool:
        """
        向 RFID 标签写入用户数据（User Data）。
        :param userdata: 要写入的用户数据，长度必须为 20 字节
        :return: 是否写入成功
        """
        # 指令模板：前11字节固定 + 20字节用户数据占位符
        base_template = bytes([
            0xFF, 0x1C, 0x24, 0x03, 0xE8, 0x00, 0x00, 0x00, 0x00, 0x04, 0x03,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
        ])

        if len(userdata) != 20:
            print(f"错误：用户数据长度必须为 20 字节，实际为 {len(userdata)} 字节")
            return False

        # 构建完整命令：前11字节 + 用户数据20字节
        cmd = base_template[:11] + userdata
        # 计算CRC并附加（大端序，高字节在前）
        cmd_with_crc = self.get_cmd_append_crc(cmd, little_endian=False)

        # 发送前清空队列，避免读到旧数据
        self.clear_response_queue()
        if not self.send_command(cmd_with_crc):
            print("发送指令失败")
            return False

        response = self.receive_response(timeout=2.0)
        if not response or len(response) < 5:
            print(f"响应数据无效: {response.hex() if response else '空'}")
            return False

        # 检查响应头：FF 00 24
        if response[0] != 0xFF or response[1] != 0x00 or response[2] != 0x24:
            print(f"响应头异常: {response[0:3].hex()}")
            return False

        # 检查状态字节（索引3、4）是否为 0x00
        if response[3] == 0 and response[4] == 0:
            print("写入用户数据成功")
            return True
        else:
            print(f"写入用户数据失败，状态码: {response[3]:02X}{response[4]:02X}")
            return False

    # -------------------- 日志辅助 --------------------
    def log_data(self, data_bytes):
        """记录接收到的原始数据到日志文件"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            hex_str = ' '.join(f'{b:02X}' for b in data_bytes)
            with open("rfid_reader_log.txt", "a") as f:
                f.write(f"{timestamp} - {hex_str}\n")
        except Exception as e:
            print(f"记录日志失败: {e}")