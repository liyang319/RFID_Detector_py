# main.py
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import time
import threading
from RFIDReader_CNNT import RFIDReader_CNNT
from rfid_tag import RFIDTag
from command import device_command
from mqtt_client import MqttClient
import json
from serial_comm import SerialComm

DATA_TYPE_INBOUND = "inbound"
DATA_TYPE_OUTBOUND = "outbound"
class RFIDProductionSystem:
    def __init__(self, root):
        self.root = root
        self.root.title("RFID检测系统")
        self.root.geometry("1000x800")
        self.root.configure(bg='#f0f0f0')
        self.root.resizable(True, True)

        # 系统状态变量
        self.is_running = False
        self.current_load = 0
        self.daily_production = 0
        self.line_runtime = "20时10分"
        self.error_message = "无异常"

        #方向标志
        self.direction = 0  # 0无，1入库，2出库
        self.current_status = 0  # 存储当前光栅状态

        # RFID标签管理
        self.current_tag = None
        self.tag_history = []
        self.max_history_size = 10000

        # RFID读写器（替换原来的SocketClient）
        self.rfid_reader = RFIDReader_CNNT('192.168.1.200', 2000)
        self.setup_rfid_callbacks()

        # MQTT客户端（新增）
        self.mqtt_client = MqttClient(
            broker='192.168.1.100',  # 根据实际情况修改
            port=1883,
            username='None',  # 根据实际情况修改
            password='None',  # 根据实际情况修改
            client_id='RFID_DETECTOR_SYSTEM'
        )
        self.setup_mqtt_callbacks()

        # 串口通信（新增）
        self.serial_comm = SerialComm('/dev/tty.usbserial-1410', 9600)
        self.serial_reading_active = False  # 串口读取线程状态标志

        # 创建界面（保持原有UI不变）
        self.create_title_section()
        self.create_socket_section()  # 这个section现在用于RFID读写器连接
        self.create_device_info_section()
        self.create_rfid_info_section()
        self.create_production_stats_section()
        self.create_status_control_section()

        # 启动时间更新
        self.update_time()

        # 尝试自动连接RFID读写器
        self.auto_connect()

    def setup_rfid_callbacks(self):
        """设置RFID读写器回调函数"""
        self.rfid_reader.set_callbacks(
            receive_callback=self.on_rfid_data_received,
            connection_callback=self.on_rfid_connection_changed,
            error_callback=self.on_rfid_error
        )

    def create_title_section(self):
        """创建标题区域"""
        title_frame = tk.Frame(self.root, bg='#2c3e50', height=70)
        title_frame.pack(fill='x', padx=5, pady=5)
        title_frame.pack_propagate(False)

        title_label = tk.Label(title_frame, text="RFID检测系统",
                               font=("微软雅黑", 20, "bold"),
                               bg='#2c3e50', fg='white')
        title_label.pack(pady=20)

    def create_socket_section(self):
        """创建RFID读写器连接控制区域（保持原有UI结构）"""
        socket_frame = tk.LabelFrame(self.root, text="RFID读写器连接设置",
                                     font=("微软雅黑", 11, "bold"),
                                     bg='white', bd=2, relief='groove',
                                     fg='#2c3e50')
        socket_frame.pack(fill='x', padx=15, pady=5)

        # 服务器配置
        config_frame = tk.Frame(socket_frame, bg='white')
        config_frame.pack(fill='x', padx=10, pady=8)

        tk.Label(config_frame, text="RFID读写器地址:", font=("微软雅黑", 9),
                 bg='white').pack(side='left', padx=(0, 5))

        self.host_entry = tk.Entry(config_frame, width=15, font=("微软雅黑", 9),
                                   relief='solid', bd=1)
        self.host_entry.insert(0, "192.168.1.200")
        self.host_entry.pack(side='left', padx=(0, 15))

        tk.Label(config_frame, text="端口号:", font=("微软雅黑", 9),
                 bg='white').pack(side='left', padx=(0, 5))

        self.port_entry = tk.Entry(config_frame, width=8, font=("微软雅黑", 9),
                                   relief='solid', bd=1)
        self.port_entry.insert(0, "2000")
        self.port_entry.pack(side='left', padx=(0, 20))

        # 连接状态和控制按钮
        status_frame = tk.Frame(socket_frame, bg='white')
        status_frame.pack(fill='x', padx=10, pady=8)

        tk.Label(status_frame, text="连接状态:", font=("微软雅黑", 10),
                 bg='white').pack(side='left', padx=(0, 5))

        self.socket_status_label = tk.Label(status_frame, text="未连接",
                                            font=("微软雅黑", 10, "bold"),
                                            bg='white', fg='#e74c3c')
        self.socket_status_label.pack(side='left', padx=(0, 30))

        # 连接控制按钮
        button_frame = tk.Frame(status_frame, bg='white')
        button_frame.pack(side='right')

        self.connect_button = tk.Button(button_frame, text="连接RFID读写器",
                                        font=("微软雅黑", 9), bg='#3498db', fg='black',
                                        width=15, height=1,
                                        command=self.connect_rfid)
        self.connect_button.pack(side='left', padx=(0, 10))

        self.disconnect_button = tk.Button(button_frame, text="断开连接",
                                           font=("微软雅黑", 9), bg='#95a5a6', fg='black',
                                           width=12, height=1,
                                           command=self.disconnect_rfid,
                                           state='disabled')
        self.disconnect_button.pack(side='left')

        # 消息显示区域
        msg_frame = tk.Frame(socket_frame, bg='white')
        msg_frame.pack(fill='x', padx=10, pady=5)

        tk.Label(msg_frame, text="通信日志:", font=("微软雅黑", 9),
                 bg='white').pack(anchor='w')

        msg_text_frame = tk.Frame(msg_frame, bg='white')
        msg_text_frame.pack(fill='x', pady=5)

        self.message_text = tk.Text(msg_text_frame, height=4, font=("Consolas", 8),
                                    relief='solid', bd=1, wrap='word')
        scrollbar = tk.Scrollbar(msg_text_frame, command=self.message_text.yview)
        self.message_text.config(yscrollcommand=scrollbar.set)

        self.message_text.pack(side='left', fill='x', expand=True)
        scrollbar.pack(side='right', fill='y')

        self.message_text.config(state='disabled')

    def create_device_info_section(self):
        """创建设备信息区域（保持不变）"""
        info_frame = tk.Frame(self.root, bg='white', relief='groove', bd=1)
        info_frame.pack(fill='x', padx=15, pady=5)

        # 第一行信息
        row1_frame = tk.Frame(info_frame, bg='white')
        row1_frame.pack(fill='x', padx=10, pady=5)

        # 设备号
        tk.Label(row1_frame, text="设备号:", font=("微软雅黑", 10),
                 bg='white').pack(side='left', padx=(0, 5))
        tk.Label(row1_frame, text="RFID-PROD-001", font=("微软雅黑", 10, "bold"),
                 bg='white', fg='#2c3e50').pack(side='left', padx=(0, 40))

        # 软件版本
        tk.Label(row1_frame, text="软件版本:", font=("微软雅黑", 10),
                 bg='white').pack(side='left', padx=(0, 5))
        tk.Label(row1_frame, text="v2.0.1", font=("微软雅黑", 10, "bold"),
                 bg='white', fg='#2c3e50').pack(side='left')

        # 第二行信息
        row2_frame = tk.Frame(info_frame, bg='white')
        row2_frame.pack(fill='x', padx=10, pady=5)

        # 当前位置
        tk.Label(row2_frame, text="当前位置:", font=("微软雅黑", 10),
                 bg='white').pack(side='left', padx=(0, 5))
        tk.Label(row2_frame, text="经度116.3918173°, 纬度39.9797956°",
                 font=("微软雅黑", 10), bg='white', fg='#2c3e50').pack(side='left', padx=(0, 40))

        self.time_label = tk.Label(row2_frame, text="", font=("微软雅黑", 10),
                                   bg='white', fg='#2c3e50')
        self.time_label.pack(side='left')

    def create_rfid_info_section(self):
        """创建RFID信息区域（保持不变）"""
        tray_frame = tk.LabelFrame(self.root, text="标签信息",
                                   font=("微软雅黑", 12, "bold"),
                                   bg='white', bd=2, relief='groove',
                                   fg='#2c3e50')
        tray_frame.pack(fill='both', expand=True, padx=15, pady=10)

        # 第一行：托盘编号和托盘装载货物数量
        row1_frame = tk.Frame(tray_frame, bg='white')
        row1_frame.grid(row=0, column=0, columnspan=2, sticky='w', padx=10, pady=15)

        # 托盘编号
        tk.Label(row1_frame, text="托盘编号:", font=("微软雅黑", 10),
                 bg='white').pack(side='left', padx=(0, 5))
        self.tray_id_entry = tk.Entry(row1_frame, width=30, font=("微软雅黑", 10),
                                      relief='solid', bd=1)
        self.tray_id_entry.insert(0, "TRAY-2024-001")
        self.tray_id_entry.pack(side='left', padx=(0, 40))

        # 托盘装载货物数量
        tk.Label(row1_frame, text="托盘装载货物数量:", font=("微软雅黑", 10),
                 bg='white').pack(side='left', padx=(0, 5))
        self.tray_load_entry = tk.Entry(row1_frame, width=15, font=("微软雅黑", 10),
                                        relief='solid', bd=1)
        self.tray_load_entry.insert(0, "32")
        self.tray_load_entry.pack(side='left')

        # 第二行：取标内容和贴标后内容放在同一行
        row2_frame = tk.Frame(tray_frame, bg='white')
        row2_frame.grid(row=1, column=0, columnspan=2, sticky='nsew', padx=10, pady=10)
        tray_frame.rowconfigure(1, weight=1)  # 设置行权重

        # 取标内容（左侧）
        fetch_frame = tk.Frame(row2_frame, bg='white')
        fetch_frame.pack(side='left', fill='both', expand=False, padx=(0, 10))

        tk.Label(fetch_frame, text="取标内容:", font=("微软雅黑", 10),
                 bg='white').pack(anchor='w', pady=(0, 5))
        self.fetch_text = tk.Text(fetch_frame, height=4, width=120, font=("微软雅黑", 10),
                                  relief='solid', bd=1, wrap='word')
        self.fetch_text.insert("1.0", "")
        self.fetch_text.pack(fill='both', expand=True)

        # 控制按钮区域
        control_frame = tk.Frame(tray_frame, bg='white')
        control_frame.grid(row=2, column=0, columnspan=2, sticky='e', padx=10, pady=5)

        # 清空显示按钮
        self.clear_button = tk.Button(control_frame, text="清空显示",
                                      font=("微软雅黑", 9), bg='#95a5a6', fg='black',
                                      width=10, height=1,
                                      command=self.clear_display)
        self.clear_button.pack(side='right', padx=5)

        # 导出数据按钮
        self.export_button = tk.Button(control_frame, text="导出数据",
                                       font=("微软雅黑", 9), bg='#3498db', fg='black',
                                       width=10, height=1,
                                       command=self.export_tag_data)
        self.export_button.pack(side='right', padx=5)

    def create_production_stats_section(self):
        """创建生产统计区域（保持不变）"""
        stats_frame = tk.Frame(self.root, bg='#f8f9fa', relief='groove', bd=1)
        stats_frame.pack(fill='x', padx=15, pady=10)

        # 产线运行时间
        tk.Label(stats_frame, text="产线运行时间:", font=("微软雅黑", 10, "bold"),
                 bg='#f8f9fa').grid(row=0, column=0, sticky='w', padx=20, pady=15)
        self.runtime_label = tk.Label(stats_frame, text=self.line_runtime,
                                      font=("微软雅黑", 10), bg='#f8f9fa', fg='#e74c3c')
        self.runtime_label.grid(row=0, column=1, sticky='w', padx=5, pady=15)

        # 当前托盘装载数量
        tk.Label(stats_frame, text="当前托盘装载数量:", font=("微软雅黑", 10, "bold"),
                 bg='#f8f9fa').grid(row=0, column=2, sticky='w', padx=20, pady=15)
        self.current_load_label = tk.Label(stats_frame, text=str(self.current_load),
                                           font=("微软雅黑", 10), bg='#f8f9fa', fg='#e74c3c')
        self.current_load_label.grid(row=0, column=3, sticky='w', padx=5, pady=15)

        # 今日生产总量
        tk.Label(stats_frame, text="今日生产总量:", font=("微软雅黑", 10, "bold"),
                 bg='#f8f9fa').grid(row=0, column=4, sticky='w', padx=20, pady=15)
        self.daily_label = tk.Label(stats_frame, text=str(self.daily_production),
                                    font=("微软雅黑", 10), bg='#f8f9fa', fg='#e74c3c')
        self.daily_label.grid(row=0, column=5, sticky='w', padx=5, pady=15)

    def create_status_control_section(self):
        """创建状态和控制区域（保持不变）"""
        bottom_frame = tk.Frame(self.root, bg='#f0f0f0')
        bottom_frame.pack(fill='x', padx=15, pady=10)

        # 左侧状态区域
        status_frame = tk.Frame(bottom_frame, bg='#f0f0f0')
        status_frame.pack(side='left', fill='both', expand=True)

        # 产线运行状态
        status_title = tk.Label(status_frame, text="当前产线运行状态:",
                                font=("微软雅黑", 11, "bold"), bg='#f0f0f0')
        status_title.pack(anchor='w')

        status_indicators = tk.Frame(status_frame, bg='#f0f0f0')
        status_indicators.pack(anchor='w', pady=5)

        self.normal_status = tk.Label(status_indicators, text="● 正常",
                                      font=("微软雅黑", 12, "bold"),
                                      fg='#27ae60', bg='#f0f0f0')
        self.normal_status.pack(side='left', padx=10)

        self.abnormal_status = tk.Label(status_indicators, text="● 异常",
                                        font=("微软雅黑", 12),
                                        fg='#bdc3c7', bg='#f0f0f0')
        self.abnormal_status.pack(side='left', padx=10)

        # 异常信息
        error_title = tk.Label(status_frame, text="异常信息:",
                               font=("微软雅黑", 11, "bold"), bg='#f0f0f0')
        error_title.pack(anchor='w', pady=(10, 0))

        self.error_label = tk.Label(status_frame, text=self.error_message,
                                    font=("微软雅黑", 11), fg='#27ae60', bg='#f0f0f0')
        self.error_label.pack(anchor='w')

        # 右侧控制按钮区域
        control_frame = tk.Frame(bottom_frame, bg='#f0f0f0')
        control_frame.pack(side='right')

        # 运行产线按钮
        self.run_button = tk.Button(control_frame, text="运行产线",
                                    font=("微软雅黑", 12, "bold"),
                                    bg='#27ae60', fg='black',
                                    width=12, height=2,
                                    command=self.toggle_production)
        self.run_button.pack(pady=5)

        # 紧急制动按钮
        self.emergency_button = tk.Button(control_frame, text="紧急制动",
                                          font=("微软雅黑", 12, "bold"),
                                          bg='#e74c3c', fg='black',
                                          width=12, height=2,
                                          command=self.emergency_stop)
        self.emergency_button.pack(pady=5)

    def update_time(self):
        """更新当前时间显示"""
        current_time = datetime.now().strftime("当前时间: %Y年%m月%d日 %H:%M:%S")
        self.time_label.config(text=current_time)
        self.root.after(1000, self.update_time)

    def toggle_production(self):
        """切换产线运行状态 - 主要修改部分"""
        self.is_running = not self.is_running
        if self.is_running:
            # self.run_button.config(text="停止产线", bg='#f39c12')
            # self.normal_status.config(fg='#27ae60')
            # self.abnormal_status.config(fg='#bdc3c7')
            # self.error_label.config(text="运行中", fg='#27ae60')
            # self.add_message("产线开始运行")

            # 发送开始生产指令到RFID读写器
            if self.rfid_reader.get_connection_status():
                if self.rfid_reader.send_single_cmd('CMD_RFID_LOOP_START'):
                    self.add_message("发送开始生产指令成功")
                else:
                    self.add_message("发送开始生产指令失败")
            else:
                self.add_message("RFID读写器未连接，无法发送指令")

        # else:
        #     self.run_button.config(text="运行产线", bg='#27ae60')
        #     self.normal_status.config(fg='#bdc3c7')
        #     self.abnormal_status.config(fg='#bdc3c7')
        #     self.error_label.config(text="已停止", fg='#95a5a6')
        #     self.add_message("产线已停止")
        #
        #     # 发送停止生产指令到RFID读写器
        #     if self.rfid_reader.get_connection_status():
        #         if self.rfid_reader.send_single_cmd('PRODUCTION_STOP'):
        #             self.add_message("发送停止生产指令成功")
        #         else:
        #             self.add_message("发送停止生产指令失败")
        #     else:
        #         self.add_message("RFID读写器未连接，无法发送指令")

    def emergency_stop(self):
        """紧急制动"""
        self.is_running = False
        self.run_button.config(text="运行产线", bg='#27ae60')
        self.normal_status.config(fg='#bdc3c7')
        self.abnormal_status.config(fg='#e74c3c')
        self.error_label.config(text="紧急制动！", fg='#e74c3c')
        self.add_message("紧急制动！系统已停止")

        # 发送紧急停止指令到RFID读写器
        if self.rfid_reader.get_connection_status():
            if self.rfid_reader.send_single_cmd('CMD_RFID_LOOP_STOP'):
                self.add_message("发送紧急停止指令成功")
                self.report_rfid_tags_via_mqtt()
            else:
                self.add_message("发送紧急停止指令失败")
        else:
            self.add_message("RFID读写器未连接，无法发送指令")

        messagebox.showwarning("紧急制动", "系统已紧急停止！")

    def start_rfid_loop_query(self, b_on):
        print(f"start_rfid_loop_query  === {b_on}")
        if b_on:
            # 发送开始生产指令到RFID读写器
            self.tag_history.clear()
            if self.rfid_reader.get_connection_status():
                if self.rfid_reader.send_single_cmd('CMD_RFID_LOOP_START'):
                    self.add_message("发送开始生产指令成功")
                else:
                    self.add_message("发送开始生产指令失败")
            else:
                self.add_message("RFID读写器未连接，无法发送指令")
        else:
            # 发送紧急停止指令到RFID读写器
            if self.rfid_reader.get_connection_status():
                if self.rfid_reader.send_single_cmd('CMD_RFID_LOOP_STOP'):
                    self.add_message("发送紧急停止指令成功")
                    # self.report_rfid_tags_via_mqtt()
                else:
                    self.add_message("发送紧急停止指令失败")
            else:
                self.add_message("RFID读写器未连接，无法发送指令")

    # RFID读写器相关方法
    def auto_connect(self):
        """自动连接RFID读写器和MQTT客户端（分别启动）"""
        self.add_message("系统启动，准备连接RFID读写器和MQTT客户端...")

        def connect_rfid_thread():
            """RFID读写器连接线程"""
            time.sleep(2)  # 延迟2秒连接，让界面先加载完成
            if self.rfid_reader.connect():
                self.add_message("自动连接RFID读写器成功")
            else:
                self.add_message("自动连接RFID读写器失败，请手动连接")

        def connect_mqtt_thread():
            """MQTT客户端连接线程"""
            time.sleep(3)  # 延迟3秒连接，避免同时启动造成资源竞争
            self.start_mqtt_client()

        def connect_serial_thread():
            """串口连接线程"""
            time.sleep(4)  # 延迟4秒连接，避免资源竞争
            self.start_serial_communication()

        # 分别启动两个线程
        threading.Thread(target=connect_rfid_thread, daemon=True).start()
        threading.Thread(target=connect_mqtt_thread, daemon=True).start()
        threading.Thread(target=connect_serial_thread, daemon=True).start()

    def connect_rfid(self):
        """连接RFID读写器"""
        # 更新RFID读写器配置
        try:
            host = self.host_entry.get()
            port = int(self.port_entry.get())
            self.rfid_reader.host = host
            self.rfid_reader.port = port
        except ValueError:
            messagebox.showerror("错误", "端口号必须是数字")
            return

        def connect_thread():
            if self.rfid_reader.connect():
                self.add_message(f"手动连接RFID读写器 {host}:{port} 成功")

        threading.Thread(target=connect_thread, daemon=True).start()
        self.connect_button.config(state='disabled', text="连接中...")
        self.add_message(f"正在连接RFID读写器 {host}:{port}...")

    def disconnect_rfid(self):
        """断开RFID读写器连接"""
        self.rfid_reader.disconnect()
        self.add_message("手动断开RFID读写器连接")

    # RFID读写器回调函数
    def on_rfid_data_received(self, data):
        """RFID数据接收回调"""

        def update_ui():
            if isinstance(data, bytes):
                # 处理二进制数据
                hex_str = ' '.join([f'{b:02X}' for b in data])
                self.add_message(f"收到RFID数据: {hex_str}")
                self.process_rfid_data(data)
            elif isinstance(data, dict):
                # 处理JSON数据
                self.add_message(f"收到RFID JSON数据: {data}")
                self.handle_json_data(data)

        self.root.after(0, update_ui)

    def on_rfid_connection_changed(self, connected, message):
        """RFID连接状态回调"""

        def update_ui():
            if connected:
                self.socket_status_label.config(text="● 已连接", fg='#27ae60')
                self.connect_button.config(state='disabled', text="已连接")
                self.disconnect_button.config(state='normal', bg='#e74c3c')
                self.host_entry.config(state='disabled')
                self.port_entry.config(state='disabled')
            else:
                self.socket_status_label.config(text="● 未连接", fg='#e74c3c')
                self.connect_button.config(state='normal', text="连接RFID读写器")
                self.disconnect_button.config(state='disabled', bg='#95a5a6')
                self.host_entry.config(state='normal')
                self.port_entry.config(state='normal')

            self.add_message(message)

        self.root.after(0, update_ui)

    def on_rfid_error(self, error_msg):
        """RFID错误回调"""

        def update_ui():
            self.add_message(f"RFID错误: {error_msg}")
            # 只在重要错误时显示弹窗
            if "连接" in error_msg or "断开" in error_msg:
                messagebox.showerror("RFID错误", error_msg)

        self.root.after(0, update_ui)

    def process_rfid_data(self, data: bytes):
        """处理RFID二进制数据"""
        # print('process_rfid_data')
        # 根据你的协议解析数据并更新界面
        if len(data) >= 8:
            # 示例解析逻辑
            if data[0] == 0xA5 and data[1] == 0x5A:
                self.parse_protocol_a55a(data)

    def parse_protocol_a55a(self, data: bytes):
        """解析 A5 5A 协议格式"""
        try:
            command = data[4]  # 命令字
            self.add_message(f"解析协议: 长度={len(data)}, 命令=0x{command:02X}")

            # 根据命令类型更新界面
            if command == 0x83:  # loop应答
                self.update_rfid_data(data)
            elif command == 0x8D:  # loop停止应答
                self.update_production_status(data)

        except Exception as e:
            self.add_message(f"协议解析错误: {e}")

    def handle_json_data(self, data: dict):
        """处理JSON数据"""
        msg_type = data.get('type', '')
        if msg_type == 'production_data':
            self.handle_production_data(data)
        elif msg_type == 'status_update':
            self.handle_status_update(data)
        elif msg_type == 'rfid_data':
            self.handle_rfid_data(data)
        else:
            self.add_message(f"收到JSON数据: {data}")

    def handle_production_data(self, data):
        """处理生产数据"""
        production_data = data.get('data', {})

        if 'daily_production' in production_data:
            self.daily_production = production_data['daily_production']
            self.daily_label.config(text=str(self.daily_production))

        if 'current_load' in production_data:
            self.current_load = production_data['current_load']
            self.current_load_label.config(text=str(self.current_load))
            self.tray_load_entry.delete(0, tk.END)
            self.tray_load_entry.insert(0, str(self.current_load))

        if 'line_runtime' in production_data:
            self.line_runtime = production_data['line_runtime']
            self.runtime_label.config(text=self.line_runtime)

        self.add_message("生产数据已更新")

    def handle_status_update(self, data):
        """处理状态更新"""
        status_data = data.get('data', {})

        if 'line_status' in status_data:
            status = status_data['line_status']
            if status == 'normal':
                self.normal_status.config(fg='#27ae60')
                self.abnormal_status.config(fg='#bdc3c7')
                if not self.is_running:
                    self.is_running = True
                    self.run_button.config(text="停止产线", bg='#f39c12')
            else:
                self.normal_status.config(fg='#bdc3c7')
                self.abnormal_status.config(fg='#e74c3c')
                if self.is_running:
                    self.is_running = False
                    self.run_button.config(text="运行产线", bg='#27ae60')

        if 'error_message' in status_data:
            self.error_message = status_data['error_message']
            self.error_label.config(text=self.error_message)
            if status_data['error_message'] != "无异常":
                self.error_label.config(fg='#e74c3c')
            else:
                self.error_label.config(fg='#27ae60')

        self.add_message("设备状态已更新")

    def handle_rfid_data(self, data):
        """处理RFID数据"""
        rfid_data = data.get('data', {})

        if 'tray_id' in rfid_data:
            self.tray_id_entry.delete(0, tk.END)
            self.tray_id_entry.insert(0, rfid_data['tray_id'])

        if 'fetch_content' in rfid_data:
            self.fetch_text.delete('1.0', tk.END)
            self.fetch_text.insert('1.0', rfid_data['fetch_content'])

        # if 'after_content' in rfid_data:
        #     self.after_text.delete('1.0', tk.END)
        #     self.after_text.insert('1.0', rfid_data['after_content'])

        if 'load_count' in rfid_data:
            self.tray_load_entry.delete(0, tk.END)
            self.tray_load_entry.insert(0, str(rfid_data['load_count']))

        self.add_message("RFID标签数据已更新")

    def update_production_status(self, data: bytes):
        """根据二进制数据更新生产状态"""
        # 根据你的实际协议实现
        pass

    def process_rfid_data_epc_tid_user(self, data: bytes) -> RFIDTag:
        """
        解析RFID数据并返回RFIDTag对象

        Args:
            data: 接收到的完整数据包

        Returns:
            RFIDTag: 包含解析结果的标签对象
        """
        tag = RFIDTag()
        success = tag.from_bytes(data)

        if success:
            self.current_tag = tag
            # 添加到历史记录
            # self.tag_history.append(tag)
            # # 限制历史记录大小
            # if len(self.tag_history) > self.max_history_size:
            #     self.tag_history.pop(0)

        return tag

    def update_rfid_data(self, data: bytes):
        """根据二进制数据更新RFID数据（TID去重）"""
        # print('update_rfid_data')
        # 使用RFIDTag类解析数据
        tag = self.process_rfid_data_epc_tid_user(data)

        if tag.success:
            # 调试：打印TID值
            # print(f"解析到的TID: '{tag.tid}'")
            # print(f"历史记录中的TID数量: {len(self.tag_history)}")
            # 检查TID是否已存在
            tid_exists = any(existing_tag.tid == tag.tid for existing_tag in self.tag_history)

            if not tid_exists:
                # TID不存在，添加到历史记录并更新显示
                self.current_tag = tag
                # 添加到历史记录
                self.tag_history.append(tag)
                # 限制历史记录大小
                if len(self.tag_history) > self.max_history_size:
                    self.tag_history.pop(0)

                # 更新当前装载数量
                self.current_load = len(self.tag_history)
                self.current_load_label.config(text=str(self.current_load))

                # 更新今日生产总量
                self.daily_production += 1
                self.daily_label.config(text=str(self.daily_production))

                # 更新界面显示
                display_text = self._format_tag_list_display(tag)
                self.update_element_text(self.fetch_text, display_text, clear_first=False)

                # 添加消息
                self.add_message(f"读取到新标签: {tag.product_name} (TID: {tag.tid}, RSSI: {tag.rssi:.1f}dBm)")
            else:
                # TID已存在，只更新当前标签，不添加到历史记录和显示
                self.current_tag = tag
                self.add_message(f"检测到重复标签，TID: {tag.tid} 已存在")
        else:
            self.add_message(f"标签解析失败: {tag.error_message}")

    def _format_tag_display(self, tag: RFIDTag) -> str:
        """格式化标签信息用于显示"""
        return (f"EPC: {tag.epc}\n"
                f"TID: {tag.tid}\n"
                f"USER: {tag.user_data}\n"
                f"RSSI: {tag.rssi:.1f} dBm\n"
                f"天线: {tag.antenna_num}\n"
                f"产品: {tag.product_name}\n"
                f"生产企业: {tag.manufacturer}\n"
                f"许可证: {tag.license_number}\n"
                f"生产日期: {tag.production_date}\n"
                f"批号: {tag.batch_number}\n"
                f"包装: {tag.package_spec} {tag.package_method}\n"
                f"数量: {tag.quantity}\n"
                f"位置: {tag.longitude:.6f}°, {tag.latitude:.6f}°\n"
                f"时间: {tag.timestamp}\n"
                "=" * 50 + "\n")

    def _format_tag_list_display(self, tag: RFIDTag) -> str:
        """格式化标签信息用于显示"""
        return (f"EPC: {tag.epc} "
                f"TID: {tag.tid} "
                f"USER: {tag.user_data} "
                f"RSSI: {tag.rssi:.1f}dBm "
                f"天线: {tag.antenna_num}\n")

    def clear_display(self):
        """清空显示内容"""
        self.fetch_text.delete('1.0', tk.END)
        # 清空标签历史记录
        self.tag_history.clear()

        # 重置当前标签
        self.current_tag = None

        self.current_load = len(self.tag_history)
        self.current_load_label.config(text=str(self.current_load))

        self.add_message("显示内容和标签历史已清空")

    def export_tag_data(self):
        """导出标签数据到文件"""
        if not self.tag_history:
            messagebox.showinfo("导出数据", "没有可导出的标签数据")
            return

        try:
            filename = f"rfid_tags_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            self.export_tags_to_csv(filename)
            messagebox.showinfo("导出成功", f"数据已导出到: {filename}")
        except Exception as e:
            messagebox.showerror("导出失败", f"导出数据时出错: {str(e)}")

    def export_tags_to_csv(self, filename: str):
        """导出标签历史到CSV文件"""
        import csv

        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['timestamp', 'epc', 'tid', 'user_data', 'rssi', 'antenna_num',
                              'product_name', 'manufacturer', 'license_number', 'production_date',
                              'batch_number', 'package_spec', 'package_method', 'quantity',
                              'longitude', 'latitude']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                writer.writeheader()
                for tag in self.tag_history:
                    if tag.success:
                        writer.writerow({
                            'timestamp': tag.timestamp,
                            'epc': tag.epc,
                            'tid': tag.tid,
                            'user_data': tag.user_data,
                            'rssi': tag.rssi,
                            'antenna_num': tag.antenna_num,
                            'product_name': tag.product_name,
                            'manufacturer': tag.manufacturer,
                            'license_number': tag.license_number,
                            'production_date': tag.production_date,
                            'batch_number': tag.batch_number,
                            'package_spec': tag.package_spec,
                            'package_method': tag.package_method,
                            'quantity': tag.quantity,
                            'longitude': tag.longitude,
                            'latitude': tag.latitude
                        })

            self.add_message(f"标签数据已导出到: {filename}")

        except Exception as e:
            self.add_message(f"导出失败: {e}")
            raise

    def add_message(self, message):
        """添加消息到消息框"""

        def _add_message():
            self.message_text.config(state='normal')
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.message_text.insert(tk.END, f"[{timestamp}] {message}\n")
            self.message_text.see(tk.END)
            self.message_text.config(state='disabled')

            # 限制消息数量
            lines = int(self.message_text.index('end-1c').split('.')[0])
            if lines > 100:  # 保留最近100条消息
                self.message_text.delete('1.0', '2.0')

        self.root.after(0, _add_message)

    def on_closing(self):
        """程序关闭时的清理工作"""
        if hasattr(self, 'rfid_reader'):
            self.rfid_reader.disconnect()
        # 断开MQTT连接
        if hasattr(self, 'mqtt_client'):
            try:
                self.mqtt_client.disconnect()
                self.add_message("MQTT客户端已断开")
            except:
                pass
        # 关闭串口通信
        if hasattr(self, 'serial_comm'):
            try:
                self.close_serial_communication()
                self.add_message("串口通信已关闭")
            except:
                pass
        self.root.destroy()

    def update_element_text(self, element, text: str, **kwargs) -> bool:
        """
        增强版：更新界面元素的文本内容

        Args:
            element: 要更新的控件
            text: 要设置的文本
            **kwargs: 额外参数
                - clear_first: bool = True 是否先清空内容
                - scroll_to_end: bool = True 是否滚动到底部（Text控件）
                - format_str: str = None 格式化字符串
                - max_length: int = None 最大长度限制
                - prefix: str = "" 前缀
                - suffix: str = "" 后缀

        Returns:
            bool: 更新是否成功
        """
        if element is None:
            return False

        # 处理参数
        clear_first = kwargs.get('clear_first', False)
        scroll_to_end = kwargs.get('scroll_to_end', True)
        format_str = kwargs.get('format_str')
        max_length = kwargs.get('max_length')
        prefix = kwargs.get('prefix', '')
        suffix = kwargs.get('suffix', '')

        # 格式化文本
        formatted_text = str(text)
        if format_str:
            try:
                formatted_text = format_str.format(text)
            except:
                pass

        # 添加前后缀
        formatted_text = prefix + formatted_text + suffix

        # 长度限制
        if max_length and len(formatted_text) > max_length:
            formatted_text = formatted_text[:max_length - 3] + '...'

        def _update():
            try:
                if isinstance(element, (tk.Label, tk.Button, tk.Checkbutton, tk.Radiobutton)):
                    element.config(text=formatted_text)

                elif isinstance(element, tk.Entry):
                    if clear_first:
                        element.delete(0, tk.END)
                    element.insert(0, formatted_text)

                elif isinstance(element, tk.Text):
                    if clear_first:
                        element.delete('1.0', tk.END)
                    element.insert(tk.END, formatted_text)
                    if scroll_to_end:
                        element.see(tk.END)

                elif isinstance(element, tk.LabelFrame):
                    element.config(text=formatted_text)

                elif hasattr(element, 'set'):  # StringVar等
                    element.set(formatted_text)

                else:
                    if hasattr(element, 'config') and 'text' in element.config():
                        element.config(text=formatted_text)
                    else:
                        return False

                return True

            except Exception as e:
                print(f"更新控件文本失败: {e}")
                return False

        self.root.after(0, _update)
        return True

    def setup_mqtt_callbacks(self):
        """设置完整的MQTT回调函数"""
        # 需要在文件顶部添加导入：import paho.mqtt.client as mqtt
        self.mqtt_client.client.on_connect = self._on_mqtt_connect
        self.mqtt_client.client.on_disconnect = self._on_mqtt_disconnect
        self.mqtt_client.client.on_message = self._on_mqtt_message

    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """MQTT连接回调"""
        def update_ui():
            if rc == 0:
                self.add_message("MQTT连接成功")
                # 连接成功后订阅主题
                try:
                    self.mqtt_client.connected = True
                    self.mqtt_client.subscribe(self.mqtt_client.data_topic)
                    self.mqtt_client.subscribe(self.mqtt_client.response_topic)
                    self.add_message(f"已订阅主题: {self.mqtt_client.data_topic}, {self.mqtt_client.response_topic}")
                except Exception as e:
                    self.add_message(f"订阅主题失败: {e}")
            else:
                self.add_message(f"MQTT连接失败，返回码: {rc}")

        self.root.after(0, update_ui)

    def _on_mqtt_disconnect(self, client, userdata, rc):
        """MQTT断开连接回调"""

        def update_ui():
            self.add_message("MQTT连接已断开")

        self.root.after(0, update_ui)

    def _on_mqtt_message(self, client, userdata, msg):
        """MQTT消息接收回调（直接在回调中处理）"""

        def process_message():
            try:
                message = msg.payload.decode('utf-8')
                self.add_message(f"收到MQTT消息: 主题={msg.topic}, 内容={message}")

                # 根据主题类型处理消息
                # if msg.topic == self.mqtt_client.data_topic:
                #     self.handle_mqtt_data_message(message)
                # elif msg.topic == self.mqtt_client.response_topic:
                #     self.handle_mqtt_response_message(message)
                # elif msg.topic == self.mqtt_client.command_topic:
                #     self.handle_mqtt_command_message(message)
                # else:
                #     self.add_message(f"未知MQTT主题: {msg.topic}")

            except Exception as e:
                self.add_message(f"处理MQTT消息出错: {e}")

        # 在UI线程中安全处理
        self.root.after(0, process_message)

    def start_mqtt_client(self):
        """启动MQTT客户端连接"""

        def connect_thread():
            try:
                self.mqtt_client.connect()
                # 订阅必要的主题
                self.mqtt_client.subscribe(self.mqtt_client.data_topic)
                self.mqtt_client.subscribe(self.mqtt_client.response_topic)
                self.add_message("MQTT客户端启动成功")
            except Exception as e:
                self.add_message(f"MQTT客户端启动失败: {e}")

        threading.Thread(target=connect_thread, daemon=True).start()

    def send_mqtt_command(self, command_type, data_type, data=None):
        """发送MQTT命令"""
        print('send_mqtt_command')
        # print(f"mqtt_client: {hasattr(self, 'mqtt_client')}")
        # print(f"connected: {self.mqtt_client.connected}")
        if not hasattr(self, 'mqtt_client') or not self.mqtt_client.connected:
            self.add_message("MQTT客户端未连接，无法发送命令")
            return False

        try:
            command_data = {
                "cmd": command_type,
                "number": len(self.tag_history),
                "data_type": data_type
            }
            if data:
                command_data.update(data)

            message = json.dumps([command_data])
            self.mqtt_client.publish(self.mqtt_client.command_topic, message)
            self.add_message(f"发送MQTT命令: {command_type}")
            return True
        except Exception as e:
            self.add_message(f"发送MQTT命令失败: {e}")
            return False

    def report_rfid_tags_via_mqtt(self, data_type=DATA_TYPE_INBOUND):
        """通过MQTT报告RFID标签"""
        print(f"report_rfid_tags_via_mqtt type={data_type}")
        print(f"当前列表长度: {len(self.tag_history)}")
        if self.tag_history:
            # 可以发送最近的标签信息
            recent_tags = self.tag_history[-10:]  # 发送最近10个标签
            # print(f"取出列表长度: {len(recent_tags)}")
            tag_data = []
            for tag in recent_tags:
                # print(f"tag状态: {tag.success}")
                if tag.success:
                    tag_data.append({
                        'epc': tag.epc,
                        'tid': tag.tid,
                        'rssi': tag.rssi,
                        'timestamp': tag.timestamp,
                        'product_name': tag.product_name
                    })

            if tag_data:
                return self.send_mqtt_command('report_tags', data_type, {'tags': tag_data})
                self.tag_history.clear()
        else:
            self.add_message("没有可报告的RFID标签数据")
            return False

    def start_serial_communication(self):
        """启动串口通信（在UI线程中安全调用）"""
        def connect_serial():
            if self.setup_serial_communication():
                self.add_message("串口通信启动成功")
            else:
                self.add_message("串口通信启动失败，请检查串口连接")

        # 在UI线程中安全执行
        self.root.after(0, connect_serial)

    def setup_serial_communication(self):
        """设置串口通信"""
        try:
            if self.serial_comm.open():
                self.add_message("串口连接成功")
                # 直接启动串口读取循环
                self.start_serial_reading_loop()
                return True
            else:
                self.add_message("串口连接失败")
                return False
        except Exception as e:
            self.add_message(f"串口连接异常: {e}")
            return False

    def start_serial_reading_loop(self):
        """启动串口读取循环（支持灵活路径和超时检测的状态机）"""

        def read_loop():
            # 状态机定义
            STATE_IDLE = 0  # 空闲状态
            STATE_INBOUND_START = 1  # 入库开始（光栅1遮挡）
            STATE_INBOUND_MIDDLE = 2  # 入库中间（光栅1+2同时遮挡）
            STATE_INBOUND_END = 3  # 入库结束（光栅2遮挡）
            STATE_OUTBOUND_START = 4  # 出库开始（光栅2遮挡）
            STATE_OUTBOUND_MIDDLE = 5  # 出库中间（光栅1+2同时遮挡）
            STATE_OUTBOUND_END = 6  # 出库结束（光栅1遮挡）

            current_state = STATE_IDLE
            previous_status = 0
            read_interval = 0.05
            # 防重复报告机制
            last_report_time = 0
            report_cooldown = 1.0  # 1秒冷却时间

            # 超时检测机制
            last_state_change_time = time.time()
            idle_timeout = 10.0  # 10秒超时
            process_start_time = None  # 流程开始时间

            while self.serial_comm.is_open():
                try:
                    start_time = time.time()
                    data, length = self.serial_comm.read_register(0x02, timeout=0.5)

                    if length > 0 and len(data) >= 4:
                        current_status = data[3]
                        self.current_status = current_status

                        if current_status != previous_status:
                            print(f"状态变化: {previous_status:02X}->{current_status:02X}, 当前状态: {current_state}")

                            # 记录状态变化时间
                            last_state_change_time = time.time()

                            # 状态机处理
                            old_state = current_state

                            if current_state == STATE_IDLE:
                                if current_status == 0x01:  # 光栅1遮挡
                                    # 开始入库流程
                                    current_state = STATE_INBOUND_START
                                    self.direction = 1
                                    self.start_rfid_loop_query(True)
                                    process_start_time = time.time()  # 记录流程开始时间
                                    print("入库开始：光栅1遮挡")

                                elif current_status == 0x02:  # 光栅2遮挡
                                    # 开始出库流程
                                    current_state = STATE_OUTBOUND_START
                                    self.direction = 2
                                    self.start_rfid_loop_query(True)
                                    process_start_time = time.time()  # 记录流程开始时间
                                    print("出库开始：光栅2遮挡")

                            elif current_state == STATE_INBOUND_START:
                                if current_status == 0x03:  # 光栅1+2同时遮挡
                                    # 路径1：有同时遮挡
                                    current_state = STATE_INBOUND_MIDDLE
                                    print("入库中间：光栅1+2同时遮挡（路径1）")
                                elif current_status == 0x00:  # 无遮挡
                                    # 路径2：无同时遮挡，允许直接进入无遮挡状态
                                    current_state = STATE_INBOUND_END  # 直接进入结束状态等待光栅2遮挡
                                    print("入库路径2：光栅1遮挡后直接无遮挡")
                                elif current_status == 0x02:  # 光栅2遮挡（直接进入结束状态）
                                    # 直接进入结束状态
                                    current_state = STATE_INBOUND_END
                                    print("入库结束：光栅2遮挡（直接进入）")

                            elif current_state == STATE_INBOUND_MIDDLE:
                                if current_status == 0x02:  # 光栅2遮挡
                                    # 进入结束状态
                                    current_state = STATE_INBOUND_END
                                    print("入库结束：光栅2遮挡")
                                elif current_status == 0x00:  # 无遮挡（异常情况）
                                    # 重置状态
                                    current_state = STATE_IDLE
                                    self.direction = 0
                                    self.start_rfid_loop_query(False)
                                    process_start_time = None
                                    print("入库中断：中间状态检测到无遮挡")

                            elif current_state == STATE_INBOUND_END:
                                if current_status == 0x02:  # 光栅2遮挡（路径2：从无遮挡进入光栅2遮挡）
                                    # 保持结束状态，等待无遮挡
                                    print("入库结束：检测到光栅2遮挡")
                                elif current_status == 0x00:  # 无遮挡
                                    # 完成入库
                                    current_state = STATE_IDLE
                                    self.direction = 0
                                    self.start_rfid_loop_query(False)
                                    process_start_time = None
                                    # 防重复报告
                                    current_time = time.time()
                                    if current_time - last_report_time >= report_cooldown:
                                        self.report_rfid_tags_via_mqtt(DATA_TYPE_INBOUND)
                                        last_report_time = current_time
                                        print("入库完成")
                                    else:
                                        print("入库完成（跳过重复报告）")
                                elif current_status == 0x01:  # 又回到光栅1遮挡（异常）
                                    # 重置状态
                                    current_state = STATE_IDLE
                                    self.direction = 0
                                    self.start_rfid_loop_query(False)
                                    process_start_time = None
                                    print("入库异常：结束状态又回到光栅1遮挡")

                            elif current_state == STATE_OUTBOUND_START:
                                if current_status == 0x03:  # 光栅1+2同时遮挡
                                    # 路径1：有同时遮挡
                                    current_state = STATE_OUTBOUND_MIDDLE
                                    print("出库中间：光栅1+2同时遮挡（路径1）")
                                elif current_status == 0x00:  # 无遮挡
                                    # 路径2：无同时遮挡，允许直接进入无遮挡状态
                                    current_state = STATE_OUTBOUND_END  # 直接进入结束状态等待光栅1遮挡
                                    print("出库路径2：光栅2遮挡后直接无遮挡")
                                elif current_status == 0x01:  # 光栅1遮挡（直接进入结束状态）
                                    # 直接进入结束状态
                                    current_state = STATE_OUTBOUND_END
                                    print("出库结束：光栅1遮挡（直接进入）")

                            elif current_state == STATE_OUTBOUND_MIDDLE:
                                if current_status == 0x01:  # 光栅1遮挡
                                    # 进入结束状态
                                    current_state = STATE_OUTBOUND_END
                                    print("出库结束：光栅1遮挡")
                                elif current_status == 0x00:  # 无遮挡（异常情况）
                                    # 重置状态
                                    current_state = STATE_IDLE
                                    self.direction = 0
                                    self.start_rfid_loop_query(False)
                                    process_start_time = None
                                    print("出库中断：中间状态检测到无遮挡")

                            elif current_state == STATE_OUTBOUND_END:
                                if current_status == 0x01:  # 光栅1遮挡（路径2：从无遮挡进入光栅1遮挡）
                                    # 保持结束状态，等待无遮挡
                                    print("出库结束：检测到光栅1遮挡")
                                elif current_status == 0x00:  # 无遮挡
                                    # 完成出库
                                    current_state = STATE_IDLE
                                    self.direction = 0
                                    self.start_rfid_loop_query(False)
                                    process_start_time = None
                                    # 防重复报告
                                    current_time = time.time()
                                    if current_time - last_report_time >= report_cooldown:
                                        self.report_rfid_tags_via_mqtt(DATA_TYPE_OUTBOUND)
                                        last_report_time = current_time
                                        print("出库完成")
                                    else:
                                        print("出库完成（跳过重复报告）")
                                elif current_status == 0x02:  # 又回到光栅2遮挡（异常）
                                    # 重置状态
                                    current_state = STATE_IDLE
                                    self.direction = 0
                                    self.start_rfid_loop_query(False)
                                    process_start_time = None
                                    print("出库异常：结束状态又回到光栅2遮挡")

                            # 处理其他异常状态转换
                            if current_status == 0x00 and current_state != STATE_IDLE:
                                # 如果在非结束状态检测到无遮挡，检查是否允许该转换
                                if current_state not in [STATE_INBOUND_END, STATE_OUTBOUND_END]:
                                    # 检查是否为允许的路径
                                    if (current_state == STATE_INBOUND_START and previous_status == 0x01) or \
                                            (current_state == STATE_OUTBOUND_START and previous_status == 0x02):
                                        # 这是允许的路径2，不重置状态
                                        print(f"允许的路径2：状态{current_state}检测到无遮挡")
                                    else:
                                        # 其他情况重置状态
                                        print(f"异常中断：状态{current_state}检测到无遮挡")
                                        self.start_rfid_loop_query(False)
                                        current_state = STATE_IDLE
                                        self.direction = 0
                                        process_start_time = None

                            # 如果状态发生变化，更新状态变化时间
                            if old_state != current_state:
                                last_state_change_time = time.time()

                            previous_status = current_status

                        self.handle_serial_data(data)

                    # 超时检测
                    current_time = time.time()
                    if current_state != STATE_IDLE and process_start_time is not None:
                        # 检查是否超时（10秒内无状态变化）
                        if current_time - last_state_change_time > idle_timeout:
                            print(f"超时检测：状态{current_state}超过{idle_timeout}秒无变化，重置状态")
                            self.start_rfid_loop_query(False)
                            current_state = STATE_IDLE
                            self.direction = 0
                            process_start_time = None
                            print("系统已重置：超时保护")

                    # 控制读取间隔
                    elapsed = time.time() - start_time
                    sleep_time = max(0, read_interval - elapsed)
                    if sleep_time > 0:
                        time.sleep(sleep_time)

                except Exception as e:
                    self.add_message(f"串口读取错误: {e}")
                    time.sleep(0.5)

        threading.Thread(target=read_loop, daemon=True).start()
        self.add_message("串口读取循环已启动（带超时检测版本）")

    def handle_serial_data(self, data):
        """处理串口接收到的数据"""
        def update_ui():
            try:
                # 将字节数据转换为十六进制字符串显示
                hex_data = ' '.join([f'{b:02X}' for b in data])
                self.add_message(f"串口收到数据: {hex_data}")
                # 解析数据
                self.parse_serial_data(data)

            except Exception as e:
                self.add_message(f"处理串口数据错误: {e}")
        # 在UI线程中安全处理
        self.root.after(0, update_ui)

    def parse_serial_data(self, data):
        """解析串口数据"""
        try:
            if len(data) >= 8:  # 基本长度检查
                # 示例解析逻辑
                if data[0] == 0xFE:  # 设备地址
                    cmd = data[1]  # 命令字
                    self.add_message(f"收到串口命令响应: 0x{cmd:02X}")

                    # 根据命令类型处理
                    if cmd == 0x01:
                        self.handle_register_response(data)
                    else:
                        self.add_message(f"未知串口命令响应: 0x{cmd:02X}")

        except Exception as e:
            self.add_message(f"解析串口数据错误: {e}")

    def handle_register_response(self, data):
        """处理寄存器响应数据"""
        try:
            # 示例：解析寄存器值
            if len(data) >= 6:
                # 假设数据在3-4字节
                register_value = (data[3] << 8) | data[4]
                self.add_message(f"寄存器值: {register_value}")

                # 可以在这里更新界面或执行其他操作
                # self.update_serial_display(register_value)

        except Exception as e:
            self.add_message(f"处理寄存器响应错误: {e}")


def main():
    root = tk.Tk()
    app = RFIDProductionSystem(root)

    # 设置关闭窗口事件
    root.protocol("WM_DELETE_WINDOW", app.on_closing)

    root.mainloop()


if __name__ == "__main__":
    main()