# RFIDReader_SFM2200.py
import serial
import threading
import time
from datetime import datetime


class RFIDReader_SFM2200:
    """
    基于串口的 SFM2200 RFID 读写器类
    提供打开/关闭串口、发送指令、启动/停止循环读取等功能
    """

    def __init__(self, port='/dev/ttyUSB0', baudrate=115200, timeout=1.0):
        """
        初始化 RFID 读写器
        :param port: 串口设备路径（例如 '/dev/ttyUSB0' 或 'COM3'）
        :param baudrate: 波特率
        :param timeout: 串口超时时间（秒）
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_port = None
        self.running = False          # 接收循环运行标志
        self.receive_thread = None
        self.callback = None          # 数据接收回调函数
        self.lock = threading.Lock()

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

    def send_command(self, cmd: str) -> bool:
        """
        发送字符串指令（自动添加换行符，可根据实际协议修改）
        :param cmd: 要发送的指令字符串
        :return: 是否发送成功
        """
        if not self.is_open():
            print("RFID读写器未打开，无法发送指令")
            return False
        try:
            # 根据设备要求，可能需要在末尾加 \r\n 或 \n
            self.serial_port.write((cmd + '\r\n').encode('utf-8'))
            print(f"发送指令: {cmd}")
            return True
        except Exception as e:
            print(f"发送指令失败: {e}")
            return False

    # -------------------- 核心方法 --------------------
    def startloop(self):
        """
        发送启动循环读取指令（测试指令）
        """
        print("调用 RFIDReader_SFM2200.startloop()")
        # 发送测试指令，例如 "START_LOOP"
        self.send_command("START_LOOP")
        # 注意：如果需要持续读取标签，可以在此启动接收线程（可选）
        # 若需要自动接收标签数据，可调用 start_receive_loop()
        # 这里根据需求，只发送指令，不启动接收线程的自动处理
        # 若需要接收数据，可以取消下面注释
        # if not self.running:
        #     self.start_receive_loop()
        return True

    def stoploop(self):
        """
        发送停止循环读取指令（测试指令）
        """
        print("调用 RFIDReader_SFM2200.stoploop()")
        self.send_command("STOP_LOOP")
        # 若启动了接收线程，可以停止
        # if self.running:
        #     self.stop_receive_loop()
        return True

    # -------------------- 可选：接收数据支持 --------------------
    def set_callback(self, callback_func):
        """设置数据接收回调函数"""
        self.callback = callback_func

    def start_receive_loop(self):
        """启动后台接收线程（可选）"""
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
        """内部接收循环（参考 BarCodeScanner）"""
        print("进入 RFID 读写器接收循环")
        while self.running:
            try:
                # 读取最多 1024 字节，超时 0.5 秒
                data = self.serial_port.read(1024)
                if data:
                    # 处理接收到的数据（可调用回调）
                    if self.callback:
                        self.callback(data)
                    else:
                        # 默认打印十六进制
                        hex_str = ' '.join(f'{b:02X}' for b in data)
                        print(f"RFID收到数据: {hex_str}")
                else:
                    # 无数据时短暂休眠，避免空转
                    time.sleep(0.05)
            except Exception as e:
                print(f"RFID读写器接收循环错误: {e}")
                time.sleep(0.5)

    # -------------------- 其他辅助 --------------------
    def log_data(self, data_bytes):
        """记录接收到的原始数据到日志（可选）"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            hex_str = ' '.join(f'{b:02X}' for b in data_bytes)
            with open("rfid_reader_log.txt", "a") as f:
                f.write(f"{timestamp} - {hex_str}\n")
        except Exception as e:
            print(f"记录日志失败: {e}")