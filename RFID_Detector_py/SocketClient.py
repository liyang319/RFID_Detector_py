# SocketClient.py
import socket
import threading
import queue
import json
from typing import Callable, Any, Optional


class SocketClient:
    """Socket通信客户端类"""

    def __init__(self, host='192.168.1.200', port=2000):
        self.host = host
        self.port = port
        self.socket = None
        self.is_connected = False
        self.receive_thread = None
        self.send_queue = queue.Queue()

        # 回调函数
        self.receive_callback = None
        self.connection_callback = None
        self.error_callback = None

    def set_callbacks(self,
                      receive_callback: Optional[Callable[[bytes or dict], None]] = None,
                      connection_callback: Optional[Callable[[bool, str], None]] = None,
                      error_callback: Optional[Callable[[str], None]] = None):
        """设置回调函数"""
        self.receive_callback = receive_callback
        self.connection_callback = connection_callback
        self.error_callback = error_callback

    def connect(self) -> bool:
        """连接服务器"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5)
            self.socket.connect((self.host, self.port))
            self.is_connected = True

            # 启动接收线程
            self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.receive_thread.start()

            # 启动发送线程
            send_thread = threading.Thread(target=self._send_loop, daemon=True)
            send_thread.start()

            if self.connection_callback:
                self.connection_callback(True, f"成功连接到服务器 {self.host}:{self.port}")

            return True

        except Exception as e:
            self.is_connected = False
            error_msg = f"连接失败: {str(e)}"
            if self.connection_callback:
                self.connection_callback(False, error_msg)
            if self.error_callback:
                self.error_callback(error_msg)
            return False

    def disconnect(self):
        """断开连接"""
        self.is_connected = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None

    def send_data(self, data: dict or str or bytes) -> bool:
        """发送数据到队列"""
        if self.is_connected:
            self.send_queue.put(data)
            return True
        return False

    def _send_loop(self):
        """发送循环 - 直接发送原始数据"""
        print('_send_loop start')
        while self.is_connected:
            try:
                data = self.send_queue.get(timeout=1)
                if data and self.socket:
                    if isinstance(data, dict):
                        data = json.dumps(data, ensure_ascii=False).encode('utf-8')
                    elif isinstance(data, str):
                        data = data.encode('utf-8')
                    elif isinstance(data, bytes):
                        # 如果是字节数组，直接使用
                        pass
                    else:
                        # 其他类型转换为字符串
                        data = str(data).encode('utf-8')

                    # 直接发送数据，不添加任何前缀
                    self.socket.sendall(data)
                    print(f"发送数据: {data.hex().upper()}")  # 调试用

            except queue.Empty:
                continue
            except Exception as e:
                if self.is_connected and self.error_callback:
                    self.error_callback(f"发送数据错误: {e}")
                break

    def _receive_loop(self):
        """接收循环 - 直接接收原始数据"""
        print('_receive_loop start')
        while self.is_connected:
            try:
                # 直接接收数据，不处理任何头部
                received_data = self.socket.recv(1024)  # 接收最多1024字节
                if not received_data:
                    break

                # 处理接收到的数据
                self._process_received_data(received_data)

            except socket.timeout:
                continue
            except Exception as e:
                if self.is_connected and self.error_callback:
                    self.error_callback(f"接收数据错误: {e}")
                break

        self.is_connected = False
        if self.connection_callback:
            self.connection_callback(False, "与服务器连接断开")

    def _process_received_data(self, data: bytes):
        """处理接收到的数据"""
        try:
            # 首先尝试解码为UTF-8文本（JSON格式）
            try:
                data_str = data.decode('utf-8')
                data_dict = json.loads(data_str)
                if self.receive_callback:
                    self.receive_callback(data_dict)
                print(f"接收到JSON数据: {data_dict}")
                return
            except (UnicodeDecodeError, json.JSONDecodeError):
                # 如果不是UTF-8文本或JSON格式，作为二进制数据处理
                pass

            # 作为二进制数据处理
            if self.receive_callback:
                self.receive_callback(data)

            # 调试信息
            hex_data = data.hex().upper()
            formatted_hex = ' '.join([hex_data[i:i + 2] for i in range(0, len(hex_data), 2)])
            print(f"接收到二进制数据: {formatted_hex}")
            print(f"数据长度: {len(data)}字节")

        except Exception as e:
            if self.error_callback:
                self.error_callback(f"数据处理错误: {e}")

    def get_connection_status(self) -> bool:
        """获取连接状态"""
        return self.is_connected