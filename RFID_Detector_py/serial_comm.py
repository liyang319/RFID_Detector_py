import serial
import time
import select
import struct


class SerialComm:
    def __init__(self, port, baudrate=9600, timeout=3):
        """初始化串口设置"""
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_port = None

    def open(self):
        """打开串口"""
        try:
            self.serial_port = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            print(f"串口 {self.port} 已打开，波特率: {self.baudrate}")
            return True
        except serial.SerialException as e:
            print(f"打开串口失败: {e}")
            return False

    def close(self):
        """关闭串口"""
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            print(f"串口 {self.port} 已关闭")

    def send(self, data):
        """发送数据到串口"""
        if self.serial_port and self.serial_port.is_open:
            try:
                if isinstance(data, list):
                    # 将数组中的十六进制数转换为字节
                    byte_data = bytearray(data)
                    bytes_written = self.serial_port.write(byte_data)
                    return bytes_written
                else:
                    print("数据必须是一个整数列表")
                    return -1
            except Exception as e:
                print(f"发送数据失败: {e}")
                return -1
        else:
            print("串口未打开，无法发送数据")
            return -1

    def receive(self, max_length=100, timeout=0.5):
        """接收数据（优化版本，减少超时等待）"""
        received_data = bytearray()
        start_time = time.time()

        while len(received_data) < max_length:
            # 检查是否超时
            if time.time() - start_time > timeout:
                break

            # 使用更短的超时时间
            ready, _, _ = select.select([self.serial_port], [], [], 0.1)  # 100ms超时

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

        return received_data

    def read_register(self, cmd, timeout=1.0):
        """
        读取寄存器数据（优化版本）

        Args:
            cmd: 命令字节
            timeout: 总超时时间（秒）

        Returns:
            tuple: (data, length) - 接收到的数据和长度
        """
        if not self.serial_port or not self.serial_port.is_open:
            return bytearray(), -1

        start_time = time.time()

        # 准备发送缓冲区
        buffer = [0xFE, cmd, 0x00, 0x00, 0x00, 0x08]
        crc_value = self.crc16(buffer, 6)
        buffer.append(crc_value & 0xFF)
        buffer.append((crc_value >> 8) & 0xFF)

        # 清空输入缓冲区，避免旧数据干扰
        self.serial_port.reset_input_buffer()
        print([hex(b) for b in buffer])
        # 发送数据
        bytes_sent = self.send(buffer)
        if bytes_sent < 0:
            return bytearray(), -1

        # 接收数据（使用更短的超时）
        rx_data = self.receive(100, timeout=0.3)  # 接收超时300ms

        # 如果收到数据但长度不够，可能是数据还在传输中，再等待一下
        if 0 < len(rx_data) < 8:  # 假设完整帧至少8字节
            remaining_time = timeout - (time.time() - start_time)
            if remaining_time > 0:
                # 继续接收剩余数据
                additional_data = self.receive(100 - len(rx_data), timeout=min(0.2, remaining_time))
                rx_data.extend(additional_data)

        return rx_data, len(rx_data)

    def crc16(self, data, length):
        """
        CRC16校验计算（对应C++的crc16方法）

        Args:
            data: 数据列表
            length: 数据长度

        Returns:
            int: CRC16校验值
        """
        crc = 0xFFFF
        for i in range(length):
            crc ^= data[i]
            for j in range(8):
                if crc & 1:
                    crc >>= 1
                    crc ^= 0xA001
                else:
                    crc >>= 1
        return crc

    def read_data_from_port(self, data_buffer, max_length):
        """
        对应C++的readDataFromPort方法
        """
        received_data = self.receive(max_length)
        length = len(received_data)

        # 将数据复制到缓冲区（模拟C++的std::copy）
        if length > 0:
            # 清空或初始化数据缓冲区
            if hasattr(data_buffer, 'clear'):
                data_buffer.clear()
            # 将接收到的数据添加到缓冲区
            data_buffer.extend(received_data)

        return length

    def write_data_to_port(self, data, length):
        """
        对应C++的writeDataToPort方法

        Args:
            data: 数据列表或字节数组
            length: 数据长度

        Returns:
            int: 实际发送的字节数
        """
        if isinstance(data, list):
            # 如果数据是列表，直接发送前length个字节
            return self.send(data[:length])
        else:
            # 如果是其他类型，转换为列表
            data_list = list(data[:length]) if hasattr(data, '__getitem__') else []
            return self.send(data_list)

    # 为了方便使用，添加一些辅助方法
    def is_open(self):
        """检查串口是否打开"""
        return self.serial_port and self.serial_port.is_open

    def flush_input(self):
        """清空输入缓冲区"""
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.reset_input_buffer()

    def flush_output(self):
        """清空输出缓冲区"""
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.reset_output_buffer()
