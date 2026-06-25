# RFIDReader_SFM2200.py
import serial
import threading
import time
import queue
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
        self.response_queue = queue.Queue(maxsize=100)
        self.write_callback = None

    # -------------------- 基础串口操作 --------------------
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

    # -------------------- CRC 相关 --------------------
    def calc_crc(self, data: bytes) -> int:
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
        crc = self.calc_crc(data)
        if little_endian:
            crc_bytes = crc.to_bytes(2, 'little')
        else:
            crc_bytes = crc.to_bytes(2, 'big')
        return data + crc_bytes

    # -------------------- 响应队列 --------------------
    def clear_response_queue(self):
        while not self.response_queue.empty():
            try:
                self.response_queue.get_nowait()
            except queue.Empty:
                break

    def receive_response(self, timeout=0.5) -> bytes:
        try:
            data = self.response_queue.get(timeout=timeout)
            if data:
                hex_str = ' '.join(f'{b:02X}' for b in data)
                print(f"收到指令响应: {hex_str}")
                return data
            return b''
        except queue.Empty:
            print("未收到指令响应（超时）")
            return b''

    # -------------------- 标签上报判断（可被子类覆盖） --------------------
    def _is_tag_report(self, data: bytes) -> bool:
        """
        判断数据包是否为标签主动上报。
        默认规则：长度>=3 且 第一个字节==0xFF 且 第三个字节==0xAA。
        您可以根据实际协议在此修改。
        """
        return len(data) >= 3 and data[0] == 0xFF and data[2] == 0xAA

    # -------------------- 接收循环 --------------------
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
        # 用于缓存标签上报数据（FF XX AA 开头）的缓冲区
        tag_buffer = bytearray()
        NORMAL_TAG_HEADER = bytes([0xFF, 0x2B, 0xAA, 0x00, 0x00, 0x00, 0x96])
        header_len = len(NORMAL_TAG_HEADER)

        while self.running:
            try:
                data = self.serial_port.read(1024)
                if not data:
                    time.sleep(0.05)
                    continue

                # 判断是否为标签上报数据（FF XX AA）
                if self._is_tag_report(data):
                    # 追加到标签缓冲区
                    tag_buffer.extend(data)
                    # 尝试从缓冲区中提取完整的正常标签包
                    while True:
                        # 查找正常包头
                        idx = tag_buffer.find(NORMAL_TAG_HEADER)
                        if idx == -1:
                            # 没有正常包头，说明缓冲区中的数据都是异常包（如 FF 17 AA），丢弃全部
                            tag_buffer.clear()
                            break
                        if idx > 0:
                            # 丢弃包头前的无效数据（异常包或半包）
                            tag_buffer = tag_buffer[idx:]
                            continue
                        # 现在 tag_buffer 以正常包头开头，至少需要 36 字节才能读取 EPC 长度
                        if len(tag_buffer) < 36:
                            break
                        epc_len = tag_buffer[35]
                        total_len = 38 + epc_len   # 固定头38字节 + EPC长度(含附加数据)
                        if len(tag_buffer) < total_len:
                            break
                        # 提取完整正常包
                        packet = bytes(tag_buffer[:total_len])
                        tag_buffer = tag_buffer[total_len:]
                        # 通过回调传递正常标签包
                        if self.callback:
                            self.callback(packet)
                else:
                    # 非标签上报数据（指令响应），直接放入响应队列
                    self.response_queue.put(data)

                # 可选：打印接收到的原始数据（避免刷屏可注释）
                hex_str = ' '.join(f'{b:02X}' for b in data)
                print(f"RFID收到数据: {hex_str}")

            except Exception as e:
                print(f"RFID读写器接收循环错误: {e}")
                time.sleep(0.5)

    # -------------------- 高层指令 --------------------
    def start_firmware(self):
        print("调用 RFIDReader_SFM2200.start_firmware()")
        self.clear_response_queue()
        cmd = bytes([0xFF, 0x00, 0x04, 0x1D, 0x0B])
        self.send_command(cmd)
        self.receive_response(timeout=3)
        return True

    def startloop(self):
        print("调用 RFIDReader_SFM2200.startloop()")
        self.clear_response_queue()
        cmd = bytes([
            0xFF, 0x1F, 0xAA, 0x4D, 0x6F, 0x64, 0x75, 0x6C, 0x65, 0x74, 0x65, 0x63, 0x68,
            0xAA, 0x48, 0x00, 0x96, 0x00, 0x80, 0x04, 0x01, 0x09, 0x28, 0x00, 0x00, 0x00,
            0x03, 0x00, 0x00, 0x00, 0x04, 0x0A, 0x4F, 0xBB, 0xFF, 0x45
        ])
        self.send_command(cmd)
        self.receive_response(timeout=3)
        return True

    def startloop_tid_user(self):
        print("调用 RFIDReader_SFM2200.startloop_tid_user()")
        self.clear_response_queue()
        cmd = bytes([
            0xFF, 0x25, 0xAA, 0x4D, 0x6F, 0x64, 0x75, 0x6C, 0x65, 0x74, 0x65, 0x63, 0x68,
            0xAA, 0x48, 0x00, 0x96, 0x00, 0x80, 0x04, 0x02, 0x0F, 0x28, 0x00, 0x00, 0x00,
            0x02, 0x00, 0x00, 0x00, 0x00, 0x08, 0x03, 0x00, 0x00, 0x00, 0x04, 0x0A, 0x60,
            0xBB, 0x23, 0x8A
        ])
        self.send_command(cmd)
        self.receive_response(timeout=3)
        return True

    def stoploop(self):
        print("调用 RFIDReader_SFM2200.stoploop()")
        self.clear_response_queue()
        cmd = bytes([
            0xFF, 0x0E, 0xAA, 0x4D, 0x6F, 0x64, 0x75, 0x6C, 0x65, 0x74, 0x65, 0x63, 0x68,
            0xAA, 0x49, 0xF3, 0xBB, 0x03, 0x91
        ])
        self.send_command(cmd)
        self.receive_response(timeout=3)
        return True

    def set_write_callback(self, callback):
        """设置写标签结果的回调函数，callback 接收一个 bool 参数（成功为 True）"""
        self.write_callback = callback

    def write_tag_with_userdata(self, userdata: bytes) -> bool:
        print('write_tag_with_userdata')
        """
        向 RFID 标签写入用户数据（User Data）。
        :param userdata: 要写入的用户数据，长度必须为 20 字节
        :return: 是否写入成功
        """
        base_template = bytes([
            0xFF, 0x1C, 0x24, 0x03, 0xE8, 0x00, 0x00, 0x00, 0x00, 0x04, 0x03,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
        ])
        if len(userdata) != 20:
            print(f"错误：用户数据长度必须为 20 字节，实际为 {len(userdata)} 字节")
            return False

        cmd = base_template[:11] + userdata
        cmd_with_crc = self.get_cmd_append_crc(cmd, little_endian=False)

        self.clear_response_queue()
        if not self.send_command(cmd_with_crc):
            print("发送指令失败")
            return False

        response = self.receive_response(timeout=3.0)
        print(f"响应数据{response}")
        if not response or len(response) < 5:
            print(f"响应数据无效: {response.hex() if response else '空'}")
            return False

        # 检查响应头是否为 FF 00 24
        if response[0] != 0xFF or response[1] != 0x00 or response[2] != 0x24:
            print(f"响应头异常: {response[0:3].hex()}")
            return False

        # 检查状态字节（索引3、4）是否为 0x00
        success = (response[3] == 0 and response[4] == 0)
        if success:
            print("写入用户数据成功")
        else:
            print(f"写入用户数据失败，状态码: {response[3]:02X}{response[4]:02X}")

        # 调用回调（如果已设置）
        if self.write_callback:
            self.write_callback(success)

        return success

    def write_tag_with_epcdata(self, epcdata: bytes) -> bool:
        print('write_tag_with_epcdata')
        """
        向 RFID 标签写入 EPC 数据。
        :param epcdata: 要写入的 EPC 数据，长度必须为 20 字节
        :return: 是否写入成功
        """
        base_template = bytes([
            0xFF, 0x1C, 0x24, 0x03, 0xE8, 0x00, 0x00, 0x00, 0x00, 0x01, 0x01,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
        ])
        if len(epcdata) != 20:
            print(f"错误：EPC数据长度必须为 20 字节，实际为 {len(epcdata)} 字节")
            return False

        cmd = base_template[:11] + epcdata
        cmd_with_crc = self.get_cmd_append_crc(cmd, little_endian=False)

        self.clear_response_queue()
        if not self.send_command(cmd_with_crc):
            print("发送指令失败")
            return False

        response = self.receive_response(timeout=3.0)
        print(f"响应数据{response}")
        if not response or len(response) < 5:
            print(f"响应数据无效: {response.hex() if response else '空'}")
            return False

        # 检查响应头是否为 FF 00 24
        if response[0] != 0xFF or response[1] != 0x00 or response[2] != 0x24:
            print(f"响应头异常: {response[0:3].hex()}")
            return False

        # 检查状态字节（索引3、4）是否为 0x00
        success = (response[3] == 0 and response[4] == 0)
        if success:
            print("写入EPC数据成功")
        else:
            print(f"写入EPC数据失败，状态码: {response[3]:02X}{response[4]:02X}")

        # 调用回调（如果已设置）
        if self.write_callback:
            self.write_callback(success)

        return success

    def log_data(self, data_bytes):
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            hex_str = ' '.join(f'{b:02X}' for b in data_bytes)
            with open("rfid_reader_log.txt", "a") as f:
                f.write(f"{timestamp} - {hex_str}\n")
        except Exception as e:
            print(f"记录日志失败: {e}")