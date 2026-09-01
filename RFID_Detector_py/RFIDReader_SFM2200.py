# RFIDReader_SFM2200.py
import serial
import socket
import threading
import time
import queue
from datetime import datetime


class RFIDReader_SFM2200:
    def __init__(self, port='/dev/ttyUSB0', baudrate=115200, timeout=1.0,
                 transport='serial', host='192.168.1.100', tcp_port=8080):
        """
        :param transport: 传输方式 'serial'=串口, 'tcp'=网口(作为客户端连接RFID设备的TCP Server)
        :param port: 串口设备路径（transport='serial'时使用）
        :param baudrate: 串口波特率
        :param host: RFID设备IP地址（transport='tcp'时使用）
        :param tcp_port: RFID设备端口号（transport='tcp'时使用）
        """
        self.transport = transport
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.host = host
        self.tcp_port = tcp_port
        self.serial_port = None      # 串口对象（transport='serial'时使用）
        self.socket = None          # socket对象（transport='tcp'时使用）
        self._tcp_connected = False # TCP连接状态
        self.running = False
        self.receive_thread = None
        self.callback = None
        self.lock = threading.Lock()
        self.response_queue = queue.Queue(maxsize=100)
        self.write_callback = None

    # -------------------- 底层传输读写（串口/网口统一） --------------------
    def _write(self, data: bytes):
        """统一写接口：根据传输方式分派到串口或socket"""
        if self.transport == 'tcp':
            self.socket.sendall(data)
        else:
            self.serial_port.write(data)

    def _read(self, n: int) -> bytes:
        """统一读接口：根据传输方式分派到串口或socket"""
        if self.transport == 'tcp':
            try:
                return self.socket.recv(n)
            except (socket.timeout, TimeoutError):
                return b''
            except OSError:
                return b''
        else:
            return self.serial_port.read(n)

    # -------------------- 基础连接操作 --------------------
    def open(self):
        try:
            if self.transport == 'tcp':
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.settimeout(self.timeout)
                self.socket.connect((self.host, self.tcp_port))
                self._tcp_connected = True
                print(f"RFID读写器网口 {self.host}:{self.tcp_port} 已连接")
            else:
                self.serial_port = serial.Serial(
                    port=self.port,
                    baudrate=self.baudrate,
                    timeout=self.timeout
                )
                print(f"RFID读写器串口 {self.port} 已打开，波特率: {self.baudrate}")
            return True
        except Exception as e:
            self._tcp_connected = False
            print(f"打开RFID读写器失败: {e}")
            return False

    def close(self):
        if self.transport == 'tcp':
            if self.socket:
                try:
                    self.socket.close()
                except Exception:
                    pass
                self.socket = None
            self._tcp_connected = False
            print(f"RFID读写器网口 {self.host}:{self.tcp_port} 已断开")
        else:
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
                print(f"RFID读写器串口 {self.port} 已关闭")

    def is_open(self):
        if self.transport == 'tcp':
            return self._tcp_connected and self.socket is not None
        return self.serial_port and self.serial_port.is_open

    def send_command(self, data: bytes) -> bool:
        if not self.is_open():
            print("RFID读写器未打开，无法发送指令")
            return False
        try:
            self._write(data)
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
        self.receive_thread = threading.Thread(target=self._receive_loop_tid_user, daemon=True)
        self.receive_thread.start()
        print("RFID读写器接收循环已启动（TID+USER格式）")
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
                data = self._read(1024)
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

    def _receive_loop_tid_user(self):
        """TID+USER格式接收循环，缓冲数据并正确分发标签数据和指令响应"""
        print("进入 RFID 读写器接收循环（TID+USER格式）")
        buffer = bytearray()
        while self.running:
            try:
                data = self._read(1024)
                if not data:
                    time.sleep(0.05)
                    continue

                buffer.extend(data)

                # 可选：打印接收到的原始数据（避免刷屏可注释）
                hex_str = ' '.join(f'{b:02X}' for b in data)
                print(f"RFID收到数据: {hex_str}")

                # 处理缓冲区：标签数据（FF xx AA）透传给回调，指令响应放入响应队列
                while len(buffer) >= 3:
                    if buffer[0] != 0xFF:
                        # 数据块从包中间开始（残留数据），丢弃直到找到 FF
                        idx = buffer.find(b'\xFF')
                        if idx == -1:
                            buffer.clear()
                            break
                        del buffer[:idx]
                        continue

                    if self._is_tag_report(buffer):
                        # 标签上报数据：透传给回调，由上层解析
                        if self.callback:
                            self.callback(bytes(buffer))
                        buffer.clear()
                        break
                    else:
                        # 指令响应：放入响应队列
                        self.response_queue.put(bytes(buffer))
                        buffer.clear()
                        break

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

    def check_enabled_antenna(self):
        """查询已使能的天线，返回天线名称列表，如 ['ant1', 'ant2']"""
        print("调用 RFIDReader_SFM2200.check_enabled_antenna()")
        self.clear_response_queue()
        cmd = bytes([0xFF, 0x01, 0x61, 0x05, 0xBD, 0xB8])
        self.send_command(cmd)
        response = self.receive_response(timeout=3)
        if not response or len(response) < 15:
            print(f"check_enabled_antenna 响应数据无效: {response.hex() if response else '空'}")
            return []

        # 响应格式: FF 09 61 00 00 05 [ant_id1] [enabled1] [ant_id2] [enabled2] ...
        # ant_id: 0x01=ant1, 0x02=ant2, 0x03=ant3, 0x04=ant4
        # enabled: 0x01=使能, 0x00=禁用
        ant_map = {0x01: 'ant1', 0x02: 'ant2', 0x03: 'ant3', 0x04: 'ant4'}
        enabled = []
        for i in range(6, len(response) - 1, 2):
            ant_id = response[i]
            ant_enabled = response[i + 1]
            print(f"天线ID: {ant_id}, 使能状态: {ant_enabled}")
            if ant_id in ant_map and ant_enabled == 0x01:
                enabled.append(ant_map[ant_id])
        print(f"使能天线: {enabled}")
        return enabled

    def get_antenna_power(self):
        """查询天线读写功率，返回 {'ant1': {'read': 3300, 'write': 3300}, ...}"""
        print("调用 RFIDReader_SFM2200.get_antenna_power()")
        self.clear_response_queue()
        cmd = bytes([0xFF, 0x01, 0x61, 0x03, 0xBD, 0xBE])
        self.send_command(cmd)
        response = self.receive_response(timeout=3)
        if not response or len(response) < 27:
            print(f"get_antenna_power 响应数据无效: {response.hex() if response else '空'}")
            return {}

        # 响应格式: FF 15 61 00 00 03 [ant_id 1B][read_pwr 2B][write_pwr 2B] ×4 [CRC 2B]
        ant_map = {0x01: 'ant1', 0x02: 'ant2', 0x03: 'ant3', 0x04: 'ant4'}
        result = {}
        for i in range(6, len(response) - 2, 5):
            ant_id = response[i]
            if ant_id not in ant_map:
                continue
            read_pwr = int.from_bytes(response[i + 1:i + 3], 'big')
            write_pwr = int.from_bytes(response[i + 3:i + 5], 'big')
            result[ant_map[ant_id]] = {'read': read_pwr, 'write': write_pwr}
        print(f"天线功率: {result}")
        return result

    def set_antenna_power(self, ants, read_powers, write_powers):
        """设置天线读写功率
        :param ants: 天线名称列表，如 ['ant1', 'ant2']
        :param read_powers: 读功率列表，如 [3300, 3300]
        :param write_powers: 写功率列表，如 [3300, 3300]
        :return: 是否设置成功
        """
        print(f"调用 RFIDReader_SFM2200.set_antenna_power(ants={ants}, read={read_powers}, write={write_powers})")
        n = len(ants)
        if len(read_powers) != n or len(write_powers) != n:
            print(f"参数错误：天线数组长度不一致 ants={n} read={len(read_powers)} write={len(write_powers)}")
            return False

        ant_map = {'ant1': 0x01, 'ant2': 0x02, 'ant3': 0x03, 'ant4': 0x04}

        # 构建数据: FF [data_len] 91 [data(03 + 每根天线5字节)]
        data = bytes([0x03])  # 子功能码
        for ant_name, rpwr, wpwr in zip(ants, read_powers, write_powers):
            data += bytes([ant_map[ant_name]])
            data += rpwr.to_bytes(2, 'big')
            data += wpwr.to_bytes(2, 'big')

        cmd = bytes([0xFF, len(data), 0x91]) + data
        cmd_with_crc = self.get_cmd_append_crc(cmd, little_endian=False)

        self.clear_response_queue()
        if not self.send_command(cmd_with_crc):
            print("发送指令失败")
            return False

        response = self.receive_response(timeout=3)
        if not response or len(response) < 3:
            print(f"响应数据无效: {response.hex() if response else '空'}")
            return False

        success = (response[0] == 0xFF and response[1] == 0x00 and response[2] == 0x91)
        if success:
            print("设置天线功率成功")
        else:
            print(f"设置天线功率失败，响应: {response.hex().upper()}")
        return success

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