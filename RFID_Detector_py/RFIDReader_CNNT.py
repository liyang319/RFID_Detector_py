# RFIDReader_CNNT.py
"""
RFID读写器通信模块
封装Socket通信，提供简化的指令发送接口
"""

import threading
import time
from typing import Callable, Optional, Any
from SocketClient import SocketClient
from command import device_command  # 导入指令字典


class RFIDReader_CNNT:
    """RFID读写器通信类"""

    def __init__(self, host: str = '192.168.1.200', port: int = 2000):
        """
        初始化RFID读写器

        Args:
            host: 服务器地址
            port: 服务器端口
        """
        self.host = host
        self.port = port
        self.socket_client = SocketClient(host, port)
        self.is_connected = False
        self.command_queue = []
        self.loop_thread = None
        self.loop_running = False

        # 回调函数
        self.receive_callback = None
        self.connection_callback = None
        self.error_callback = None

        # 设置Socket客户端的回调
        self.socket_client.set_callbacks(
            receive_callback=self._on_socket_receive,
            connection_callback=self._on_socket_connection,
            error_callback=self._on_socket_error
        )

        print(f"RFID读写器初始化完成 - 服务器: {host}:{port}")

    def set_callbacks(self,
                      receive_callback: Optional[Callable[[bytes], None]] = None,
                      connection_callback: Optional[Callable[[bool, str], None]] = None,
                      error_callback: Optional[Callable[[str], None]] = None):
        """
        设置回调函数

        Args:
            receive_callback: 数据接收回调
            connection_callback: 连接状态回调
            error_callback: 错误回调
        """
        self.receive_callback = receive_callback
        self.connection_callback = connection_callback
        self.error_callback = error_callback

    def connect(self) -> bool:
        """
        连接到RFID读写器

        Returns:
            连接是否成功
        """
        print(f"正在连接RFID读写器 {self.host}:{self.port}...")
        success = self.socket_client.connect()
        if success:
            self.is_connected = True
            print("RFID读写器连接成功")
        else:
            print("RFID读写器连接失败")
        return success

    def disconnect(self):
        """断开与RFID读写器的连接"""
        self.stop_loop_cmd()
        self.socket_client.disconnect()
        self.is_connected = False
        print("RFID读写器已断开连接")

    def send_single_cmd(self, command_name: str) -> bool:
        """
        发送单次指令

        Args:
            command_name: 指令名称，如 'RFID_QUERY', 'PRODUCTION_START'

        Returns:
            发送是否成功
        """
        if not self.is_connected:
            self._call_error_callback("未连接到RFID读写器")
            return False

        if command_name not in device_command:
            self._call_error_callback(f"未知指令: {command_name}")
            return False

        command_bytes = device_command[command_name]
        success = self.socket_client.send_data(command_bytes)

        if success:
            hex_str = ' '.join([f'{b:02X}' for b in command_bytes])
            print(f"发送单次指令: {command_name} -> {hex_str}")
        else:
            self._call_error_callback(f"发送指令失败: {command_name}")

        return success

    def send_loop_cmd(self, command_name: str, interval: float = 5.0):
        """
        开始循环发送指令

        Args:
            command_name: 指令名称
            interval: 发送间隔（秒）
        """
        if not self.is_connected:
            self._call_error_callback("未连接到RFID读写器，无法开始循环发送")
            return

        if command_name not in device_command:
            self._call_error_callback(f"未知指令: {command_name}")
            return

        # 停止之前的循环
        self.stop_loop_cmd()

        # 开始新的循环
        self.loop_running = True
        self.loop_thread = threading.Thread(
            target=self._loop_send,
            args=(command_name, interval),
            daemon=True
        )
        self.loop_thread.start()

        print(f"开始循环发送指令: {command_name}, 间隔: {interval}秒")

    def stop_loop_cmd(self):
        """停止循环发送指令"""
        if self.loop_running:
            self.loop_running = False
            if self.loop_thread and self.loop_thread.is_alive():
                self.loop_thread.join(timeout=2.0)
            print("停止循环发送指令")

    def _loop_send(self, command_name: str, interval: float):
        """循环发送指令的线程函数"""
        command_bytes = device_command[command_name]
        hex_str = ' '.join([f'{b:02X}' for b in command_bytes])

        while self.loop_running and self.is_connected:
            try:
                self.socket_client.send_data(command_bytes)
                print(f"循环发送: {command_name} -> {hex_str}")
                time.sleep(interval)
            except Exception as e:
                self._call_error_callback(f"循环发送错误: {e}")
                break

        self.loop_running = False



    def send_multiple_cmds(self, command_names: list, interval: float = 1.0):
        """
        顺序发送多个指令

        Args:
            command_names: 指令名称列表
            interval: 指令间间隔（秒）
        """
        if not self.is_connected:
            self._call_error_callback("未连接到RFID读写器")
            return

        thread = threading.Thread(
            target=self._send_multiple,
            args=(command_names, interval),
            daemon=True
        )
        thread.start()

    def _send_multiple(self, command_names: list, interval: float):
        """顺序发送多个指令的线程函数"""
        for cmd_name in command_names:
            if not self.loop_running:  # 如果循环发送被停止，则中断
                break

            if cmd_name in device_command:
                self.send_single_cmd(cmd_name)
                time.sleep(interval)

    def get_connection_status(self) -> bool:
        """获取连接状态"""
        return self.is_connected and self.socket_client.is_connected

    def get_available_commands(self) -> list:
        """获取所有可用的指令名称"""
        return list(device_command.keys())

    # Socket回调处理
    def _on_socket_receive(self, data: bytes or dict):
        """Socket数据接收回调"""
        if isinstance(data, bytes):
            # 处理二进制数据
            if self.receive_callback:
                self.receive_callback(data)

            # 显示接收到的数据（调试用）
            hex_str = ' '.join([f'{b:02X}' for b in data])
            # print(f"收到RFID数据: {hex_str}")

        elif isinstance(data, dict):
            # 处理JSON数据
            if self.receive_callback:
                self.receive_callback(data)
            print(f"收到RFID JSON数据: {data}")

    def _on_socket_connection(self, connected: bool, message: str):
        """Socket连接状态回调"""
        self.is_connected = connected

        if self.connection_callback:
            self.connection_callback(connected, message)

        if connected:
            print(f"RFID读写器连接成功: {message}")
        else:
            print(f"RFID读写器连接断开: {message}")
            self.stop_loop_cmd()

    def _on_socket_error(self, error_msg: str):
        """Socket错误回调"""
        if self.error_callback:
            self.error_callback(error_msg)
        print(f"RFID读写器错误: {error_msg}")

    def _call_error_callback(self, error_msg: str):
        """调用错误回调的辅助方法"""
        if self.error_callback:
            self.error_callback(error_msg)
        print(f"RFID读写器错误: {error_msg}")

    def __del__(self):
        """析构函数，确保资源清理"""
        self.disconnect()


# # 使用示例
# if __name__ == "__main__":
#     # 创建RFID读写器实例
#     reader = RFIDReader_CNNT('192.168.1.200', 2000)
#
#
#     # 设置回调函数
#     def on_receive(data):
#         print(f"回调收到数据: {data.hex().upper()}")
#
#
#     def on_connection(connected, message):
#         print(f"连接状态: {connected}, 信息: {message}")
#
#
#     def on_error(error_msg):
#         print(f"错误: {error_msg}")
#
#
#     reader.set_callbacks(
#         receive_callback=on_receive,
#         connection_callback=on_connection,
#         error_callback=on_error
#     )
#
#     # 连接并测试
#     if reader.connect():
#         # 发送单次指令
#         reader.send_single_cmd('RFID_QUERY')
#
#         # 等待2秒后开始循环发送
#         time.sleep(2)
#         reader.send_loop_cmd('DEVICE_STATUS_QUERY', interval=3.0)
#
#         # 运行10秒后停止
#         time.sleep(10)
#         reader.stop_loop_cmd()
#
#         # 断开连接
#         time.sleep(1)
#         reader.disconnect()