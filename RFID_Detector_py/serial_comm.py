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

    def receive(self, max_length=100):
        """接收数据，直到达到最大长度或没有更多数据"""
        received_data = bytearray()  # 使用 bytearray 以便于拼接字节

        while len(received_data) < max_length:
            # 使用 select 监视串口
            ready, _, _ = select.select([self.serial_port], [], [], self.serial_port.timeout)

            if ready:  # 如果有数据可读
                byte = self.serial_port.read(1)  # 读取1字节数据
                if byte:  # 如果读取到数据
                    received_data.extend(byte)  # 将数据添加到 received_data
                else:
                    break  # 读取到空数据，退出循环
            else:
                # 超时，没有数据可读，退出循环
                break

        return received_data

    def read_register(self, cmd):
        """
        读取寄存器数据（对应C++的readRegister方法）

        Args:
            cmd: 命令字节

        Returns:
            tuple: (data, length) - 接收到的数据和长度
        """
        if not self.serial_port or not self.serial_port.is_open:
            print("串口未打开")
            return bytearray(), -1

        # 准备发送缓冲区（对应C++的buffer[8]）
        buffer = [0xFE, cmd, 0x00, 0x00, 0x00, 0x08]

        # 计算CRC16校验码
        crc_value = self.crc16(buffer, 6)

        # 添加CRC校验码到缓冲区
        buffer.append(crc_value & 0xFF)  # 低字节
        buffer.append((crc_value >> 8) & 0xFF)  # 高字节
        print([hex(b) for b in buffer])
        # 串口发送（对应writeDataToPort）
        bytes_sent = self.send(buffer)
        if bytes_sent < 0:
            print("写入错误!")
            return bytearray(), -1

        # 接收寄存器数据（对应readDataFromPort）
        rx_data = self.receive(100)  # 最大接收100字节

        if len(rx_data) == 0:
            print("读取错误!")
            return bytearray(), -1

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
