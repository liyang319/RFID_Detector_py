import serial
import time
import select


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
        except serial.SerialException as e:
            print(f"打开串口失败: {e}")

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
                    self.serial_port.write(byte_data)
                    # print(f"发送数据: {data}")
                else:
                    print("数据必须是一个整数列表")
            except Exception as e:
                print(f"发送数据失败: {e}")
        else:
            print("串口未打开，无法发送数据")

    def receive(self):
        """接收数据，直到达到最大长度或没有更多数据"""
        received_data = bytearray()  # 使用 bytearray 以便于拼接字节
        # timeout = 2  # 设置超时时间为200毫秒
        while len(received_data) < 100:
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
