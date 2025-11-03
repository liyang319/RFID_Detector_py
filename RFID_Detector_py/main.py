# main.py
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import time
import threading
from RFIDReader_CNNT import RFIDReader_CNNT
from command import device_command


class RFIDProductionSystem:
    def __init__(self, root):
        self.root = root
        self.root.title("RFID贴标生产系统")
        self.root.geometry("1000x800")
        self.root.configure(bg='#f0f0f0')
        self.root.resizable(True, True)

        # 系统状态变量
        self.is_running = False
        self.current_load = 20
        self.daily_production = 199999
        self.line_runtime = "20时10分"
        self.error_message = "无异常"

        # RFID读写器（替换原来的SocketClient）
        self.rfid_reader = RFIDReader_CNNT('192.168.1.200', 2000)
        self.setup_rfid_callbacks()

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

        title_label = tk.Label(title_frame, text="RFID贴标生产系统",
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
        self.fetch_text = tk.Text(fetch_frame, height=4, width=65, font=("微软雅黑", 10),
                                  relief='solid', bd=1, wrap='word')
        self.fetch_text.insert("1.0", "")
        self.fetch_text.pack(fill='both', expand=True)

        # 贴标后内容（右侧）
        after_frame = tk.Frame(row2_frame, bg='white')
        after_frame.pack(side='right', fill='both', expand=False, padx=(10, 0))

        tk.Label(after_frame, text="贴标后内容:", font=("微软雅黑", 10),
                 bg='white').pack(anchor='w', pady=(0, 5))
        self.after_text = tk.Text(after_frame, height=4, width=65, font=("微软雅黑", 10),
                                  relief='solid', bd=1, wrap='word')
        self.after_text.insert("1.0", "")
        self.after_text.pack(fill='both', expand=True)

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
            self.run_button.config(text="停止产线", bg='#f39c12')
            self.normal_status.config(fg='#27ae60')
            self.abnormal_status.config(fg='#bdc3c7')
            self.error_label.config(text="运行中", fg='#27ae60')
            self.add_message("产线开始运行")

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
            else:
                self.add_message("发送紧急停止指令失败")
        else:
            self.add_message("RFID读写器未连接，无法发送指令")

        messagebox.showwarning("紧急制动", "系统已紧急停止！")

    # RFID读写器相关方法
    def auto_connect(self):
        """自动连接RFID读写器"""
        self.add_message("系统启动，准备连接RFID读写器...")

        def connect_thread():
            time.sleep(2)  # 延迟2秒连接，让界面先加载完成
            if self.rfid_reader.connect():
                self.add_message("自动连接RFID读写器成功")
            else:
                self.add_message("自动连接失败，请手动连接")

        threading.Thread(target=connect_thread, daemon=True).start()

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
        print('process_rfid_data')
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

        if 'after_content' in rfid_data:
            self.after_text.delete('1.0', tk.END)
            self.after_text.insert('1.0', rfid_data['after_content'])

        if 'load_count' in rfid_data:
            self.tray_load_entry.delete(0, tk.END)
            self.tray_load_entry.insert(0, str(rfid_data['load_count']))

        self.add_message("RFID标签数据已更新")

    def update_production_status(self, data: bytes):
        """根据二进制数据更新生产状态"""
        # 根据你的实际协议实现
        pass

    def process_rfid_data_epc_tid_user(self, data: bytes) -> dict:
        """
        解析RFID数据中的PC、EPC、TID、USER、RSSI和天线号数据

        Args:
            data: 接收到的完整数据包

        Returns:
            dict: 包含解析结果的字典
            {
                'pc': '30 00',           # 字节5-6
                'epc': 'E2 82 78 83 00 00 00 00 00 88 00 00',  # 字节8-19
                'tid': 'E2 82 78 83 20 00 00 00 00 88 3A CC',   # 字节20-31
                'user': '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00',  # 字节32-47
                'rssi': -65.7,           # 实际RSSI值（dBm）
                'rssi_hex': 'FD6F',      # RSSI原始十六进制
                'ant_num': 1,            # 天线号（字节50）
                'ant_num_hex': '01',     # 天线号十六进制
                'success': True/False,
                'error': '错误信息'
            }
        """
        result = {
            'pc': '',
            'epc': '',
            'tid': '',
            'user': '',
            'rssi': 0.0,
            'rssi_hex': '',
            'ant_num': 0,
            'ant_num_hex': '',
            'success': False,
            'error': ''
        }

        try:
            # 检查数据长度
            if len(data) < 51:  # 需要至少51字节（包含天线号）
                result['error'] = f'数据长度不足，需要至少51字节，实际收到{len(data)}字节'
                return result

            # 解析PC数据 (字节5-6，共2字节)
            pc_data = data[5:7]
            result['pc'] = ' '.join([f'{b:02X}' for b in pc_data])

            # 解析EPC数据 (字节8-19，共12字节)
            epc_data = data[7:19]
            result['epc'] = ' '.join([f'{b:02X}' for b in epc_data])

            # 解析TID数据 (字节20-31，共12字节)
            tid_data = data[19:31]
            result['tid'] = ' '.join([f'{b:02X}' for b in tid_data])

            # 解析USER数据 (字节32-47，共16字节)
            user_data = data[31:47]
            result['user'] = ' '.join([f'{b:02X}' for b in user_data])

            # 解析RSSI数据 (字节47-48，共2字节)
            rssi_data = data[47:49]
            result['rssi_hex'] = rssi_data.hex().upper()
            result['rssi'] = self._parse_rssi(rssi_data)

            # 解析天线号 (字节50，第51个字节)
            ant_num_byte = data[49]
            result['ant_num'] = ant_num_byte
            result['ant_num_hex'] = f'{ant_num_byte:02X}'

            result['success'] = True

        except Exception as e:
            result['error'] = f'解析RFID数据失败: {str(e)}'

        return result

    def _parse_rssi(self, rssi_bytes: bytes) -> float:
        """
        解析RSSI值（16位补码，实际值×10）
        Args:
            rssi_bytes: 2字节的RSSI数据
        Returns:
            float: 实际的RSSI值（dBm）
        """
        if len(rssi_bytes) < 2:
            return 0.0
        # 将2字节转换为有符号整数（补码）
        rssi_int = int.from_bytes(rssi_bytes, byteorder='big', signed=True)
        # 转换为实际值（除以10）
        rssi_actual = rssi_int / 10.0
        return rssi_actual

    def update_rfid_data(self, data: bytes):
        """根据二进制数据更新RFID数据"""
        print('update_rfid_data')
        # 根据你的实际协议实现
        if len(data) >= 53:
            # 更新文本框内容
            # 解析RFID数据
            result = self.process_rfid_data_epc_tid_user(data)
            display_text = f"EPC: {result['epc']}\nTID: {result['tid']}\nUSER: {result['user']}\nRSSI: {result['rssi']}\nPC: {result['pc']}\nant_num: {result['ant_num']}"
            if result['ant_num'] == 1:
                self.update_element_text(self.fetch_text, display_text)
            elif result['ant_num'] == 2:
                # self.update_element_text(self.after_text, f"收到数据: {data.hex()}")
                self.update_element_text(self.after_text, display_text)
        pass

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
        clear_first = kwargs.get('clear_first', True)
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


def main():
    root = tk.Tk()
    app = RFIDProductionSystem(root)

    # 设置关闭窗口事件
    root.protocol("WM_DELETE_WINDOW", app.on_closing)

    root.mainloop()


if __name__ == "__main__":
    main()