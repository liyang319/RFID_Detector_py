# TcpSocketServer.py
import socket
import threading
import logging

# 配置基本日志（可按需调整）
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TcpSocketServer:
    """
    多线程 TCP Socket 服务器
    支持多个客户端并发连接，收到数据时回调注册的函数，并可向所有客户端广播消息
    """
    def __init__(self, host='0.0.0.0', port=8888):
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False
        self.clients = []           # 已连接的客户端 socket 列表
        self.clients_lock = threading.Lock()
        self.callback = None        # 消息回调函数: callback(data, addr)
        self.server_thread = None

    def register_callback(self, callback):
        """
        注册消息接收回调
        :param callback: 函数，签名为 callback(data: bytes, addr: tuple)
        """
        self.callback = callback

    def start(self):
        """启动服务器（非阻塞，在后台线程中运行）"""
        if self.running:
            logging.warning("TCP Server 已经在运行中")
            return

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.running = True
            self.server_thread = threading.Thread(target=self._accept_loop, daemon=True)
            self.server_thread.start()
            print("TCP Socket Server 已启动")
            logging.info(f"TCP Socket Server 已启动，监听 {self.host}:{self.port}")
        except Exception as e:
            logging.error(f"启动 TCP Server 失败: {e}")
            self.running = False
            raise

    def stop(self):
        """停止服务器，关闭所有连接"""
        self.running = False
        # 关闭监听 socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        # 关闭所有客户端连接
        with self.clients_lock:
            for client in self.clients:
                try:
                    client.close()
                except:
                    pass
            self.clients.clear()
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=2)
        logging.info("TCP Socket Server 已停止")

    def send_to_all(self, message):
        """
        向所有已连接的客户端发送消息
        :param message: 字符串或字节串
        """
        if isinstance(message, str):
            message = message.encode('utf-8')
        with self.clients_lock:
            # 遍历副本，避免在发送过程中因异常导致修改迭代器
            for client in self.clients[:]:
                try:
                    client.sendall(message)
                except Exception as e:
                    logging.error(f"发送消息给客户端失败: {e}")
                    self._remove_client(client)

    def _accept_loop(self):
        """接受新连接的主循环（在后台线程中运行）"""
        while self.running:
            try:
                client_socket, addr = self.server_socket.accept()
                logging.info(f"新 TCP 客户端连接: {addr}")
                # 为每个客户端创建一个独立线程处理收发
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, addr),
                    daemon=True
                )
                client_thread.start()
                with self.clients_lock:
                    self.clients.append(client_socket)
            except Exception as e:
                if self.running:
                    logging.error(f"接受连接时出错: {e}")

    def _handle_client(self, client_socket, addr):
        """处理单个客户端的消息接收"""
        while self.running:
            try:
                data = client_socket.recv(4096)
                if not data:
                    break
                # 调用回调函数（注意：回调中应避免耗时操作，或自行处理线程安全）
                if self.callback:
                    self.callback(data, addr)
            except Exception as e:
                logging.error(f"处理客户端 {addr} 消息时出错: {e}")
                break
        self._remove_client(client_socket)
        client_socket.close()
        logging.info(f"TCP 客户端断开连接: {addr}")

    def _remove_client(self, client_socket):
        """从客户端列表中移除指定 socket"""
        with self.clients_lock:
            if client_socket in self.clients:
                self.clients.remove(client_socket)