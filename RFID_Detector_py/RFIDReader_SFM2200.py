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

    def calc_crc(self, data: bytes) -> int:
        """
        计算 CRC-16/CCITT-FALSE，初始值 0xFFFF，多项式 0x1021。
        注意：C 代码从下标 1 开始计算（即忽略 data[0]）。
        :param data: 待计算的字节序列（一般包含指令头及数据，其中第一个字节不参与计算）
        :return: 16 位 CRC 值
        """
        crc = 0xFFFF
        # 从索引 1 开始，跳过第一个字节
        for i in range(1, len(data)):
            byte_val = data[i]
            # 从高位到低位逐位处理
            for bit in range(7, -1, -1):  # 7 到 0
                xor_flag = (crc >> 15) & 1
                crc = (crc << 1) | ((byte_val >> bit) & 1)
                if xor_flag:
                    crc ^= 0x1021
        # 只保留低 16 位
        return crc & 0xFFFF

    def get_cmd_append_crc(self, data: bytes, little_endian: bool = True) -> bytes:
        """
        计算 data 的 CRC，并附加到 data 末尾返回。
        :param data: 原始指令（不含 CRC）
        :param little_endian: True 表示将 CRC 低字节在前，高字节在后；False 表示高字节在前
        :return: 原始指令 + CRC 校验字节（2 字节）
        """
        crc = self.calc_crc(data)
        if little_endian:
            crc_bytes = crc.to_bytes(2, 'little')
        else:
            crc_bytes = crc.to_bytes(2, 'big')
        return data + crc_bytes

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
        # 计算CRC并附加（小端序）
        cmd_with_crc = self.get_cmd_append_crc(cmd, little_endian=False)

        if not self.send_command(cmd_with_crc):
            print("发送指令失败")
            return False

        response = self.receive_response(timeout=10.0)
        if not response or len(response) < 5:
            print(f"响应数据无效: {response.hex() if response else '空'}")
            return False

        # 检查响应头是否为 FF 00 24
        if response[0] != 0xFF or response[1] != 0x00 or response[2] != 0x24:
            print(f"响应头异常: {response[0:3].hex()}")
            return False

        # 检查第4和第5字节（索引3、4）是否为 0x00
        if response[3] == 0 and response[4] == 0:
            print("写入用户数据成功")
            return True
        else:
            print(f"写入用户数据失败，状态码: {response[3]:02X}{response[4]:02X}")
            return False