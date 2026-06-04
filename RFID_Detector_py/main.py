# main.py
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import time
import threading
# from RFIDReader_CNNT import RFIDReader_CNNT
from rfid_tag import RFIDTag
from command import device_command
from mqtt_client import MqttClient
import json
from serial_comm import SerialComm
from barcode_scanner import BarCodeScanner
from TcpSocketServer import TcpSocketServer
from RFIDReader_SFM2200 import RFIDReader_SFM2200

DATA_TYPE_INBOUND = "inbound"
DATA_TYPE_OUTBOUND = "outbound"
# SERIAL_COM_IO = "/dev/tty.usbserial-14240"
# SERIAL_COM_RFID_READER = "/dev/tty.usbserial-1410"
# SERIAL_COM_BARCODE_SCANNER = "/dev/tty.usbserial-14210"
SERIAL_COM_IO = "/dev/ttyS0"
SERIAL_COM_RFID_READER = "/dev/ttysWK3"
SERIAL_COM_BARCODE_SCANNER = "/dev/ttyS1"


class RFIDProductionSystem:
    def __init__(self, root):
        self.root = root
        self.root.title("RFID标签识别系统")
        self.root.geometry("1000x800")
        # self.root.attributes('-zoomed', True)

        # 工业风格配色方案
        self.industrial_colors = {
            'primary_bg': '#2c3e50',  # 深蓝色 - 主背景
            'secondary_bg': '#34495e',  # 稍浅蓝 - 次要背景
            'panel_bg': '#ecf0f1',  # 浅灰色 - 面板背景
            'accent': '#3498db',  # 蓝色 - 强调色
            'success': '#27ae60',  # 绿色 - 成功/正常
            'warning': '#f39c12',  # 橙色 - 警告
            'danger': '#e74c3c',  # 红色 - 危险/错误
            'text_light': '#ffffff',  # 白色 - 浅色文本
            'text_dark': '#2c3e50',  # 深蓝色 - 深色文本
            'border': '#bdc3c7'  # 灰色 - 边框
        }
        self.serial_rfid_buffer = bytearray()

        self.root.configure(bg=self.industrial_colors['primary_bg'])
        self.root.resizable(True, True)

        self.serial_rfid_buffer = bytearray()

        # 创建主容器
        self.main_container = tk.Frame(self.root, bg=self.industrial_colors['primary_bg'])
        self.main_container.pack(fill='both', expand=True)

        # 创建Canvas和滚动条
        self.canvas = tk.Canvas(self.main_container,
                                bg=self.industrial_colors['primary_bg'],
                                highlightthickness=0)
        self.scrollbar = tk.Scrollbar(self.main_container,
                                      orient="vertical",
                                      command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas,
                                         bg=self.industrial_colors['primary_bg'])

        # 配置Canvas
        self.canvas_window = self.canvas.create_window((0, 0),
                                                       window=self.scrollable_frame,
                                                       anchor="nw")

        def configure_scrollregion(event):
            """当内部frame大小变化时更新滚动区域"""
            # 更新Canvas的滚动区域
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            # 设置内部frame的宽度为Canvas的当前宽度
            self.canvas.itemconfig(self.canvas_window, width=self.canvas.winfo_width())

        def configure_canvas_width(event):
            """当Canvas大小变化时调整内部frame宽度"""
            self.canvas.itemconfig(self.canvas_window, width=event.width)

        self.scrollable_frame.bind("<Configure>", configure_scrollregion)
        self.canvas.bind("<Configure>", configure_canvas_width)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # 鼠标滚轮支持
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        # 对Linux和Windows的鼠标滚轮支持
        self.canvas.bind_all("<MouseWheel>", _on_mousewheel)
        # Linux的鼠标滚轮事件
        self.canvas.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))

        # 布局Canvas和滚动条
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # 系统状态变量
        self.is_running = False
        self.current_load = 0
        self.daily_production = 0
        self.inbound_total = 0  # 新增：入库总量
        self.outbound_total = 0  # 新增：出库总量
        self.line_runtime = "20时10分"
        self.error_message = "无异常"

        # 记录软件启动时间
        self.start_time = time.time()

        # 方向标志
        self.direction = 0  # 0无，1入库，2出库
        self.current_status = 0  # 存储当前光栅状态

        # 灯
        self.red_light = 0x00
        self.yellow_light = 0x02
        self.green_light = 0x04
        self.beep_ctrl = 0x06

        # 默认写入标签内容（20字节），TCP未下发时使用
        self.FIXED_USER_DATA = bytes([
            0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88, 0x99, 0x00,
            0xAA, 0xAA, 0xBB, 0xBB, 0xCC, 0xCC, 0xDD, 0xDD, 0xEE, 0xEE
        ])

        # TCP下发的写入数据（优先使用）及实际写入的数据（用于校验对比）
        self.pending_write_data = None
        self.actual_write_data = None

        # 写入状态跟踪
        self.write_done = False
        self.write_in_progress = False

        # RFID标签管理
        self.current_tag = None
        self.tag_history = []
        self.current_tid = ""  # TID占位变量，当前协议无法获取TID
        self.max_history_size = 10000

        # RFID读写器（替换原来的SocketClient）
        # self.rfid_reader = RFIDReader_CNNT('192.168.31.123', 2000)
        # self.setup_rfid_callbacks()
        self.device_id = "RFID-DETECTOR-001"

        # MQTT客户端（新增）
        self.mqtt_client = MqttClient(
            broker='192.168.3.83',  # 根据实际情况修改
            port=1883,
            username='None',  # 根据实际情况修改
            password='None',  # 根据实际情况修改
            client_id=self.device_id
        )
        self.setup_mqtt_callbacks()

        # 串口通信（新增）
        self.serial_comm = SerialComm(SERIAL_COM_IO, 9600)
        # self.serial_comm = SerialComm('/dev/ttyS0', 9600)
        self.serial_reading_active = False  # 串口读取线程状态标志
        self.bar_scanner = None

        # RFID读写器（串口版，新增）
        self.rfid_reader_serial = RFIDReader_SFM2200(
            port=SERIAL_COM_RFID_READER,  # 请根据实际设备修改
            baudrate=115200,  # 根据实际读写器要求修改
            timeout=1.0
        )

        # 将scrollable_frame作为新的根窗口传递
        self.actual_root = self.scrollable_frame

        # 创建界面（调整UI布局顺序）
        self.create_title_section()
        self.create_dashboard_section()  # 新增的数据看板
        self.create_rfid_info_section()  # 标签信息放在中间
        self.create_socket_section()  # RFID读写器连接设置放在最下方

        # 启动时间更新
        self.update_time()

        # 尝试自动连接RFID读写器
        self.auto_connect()

        # 启动 TCP Socket Server
        self.tcp_server = TcpSocketServer(host='0.0.0.0', port=3000)  # 可根据需要修改端口
        self.tcp_server.register_callback(self.on_tcp_message)
        self.start_tcp_server()

    # def setup_rfid_callbacks(self):
    #     """设置RFID读写器回调函数"""
    #     self.rfid_reader.set_callbacks(
    #         receive_callback=self.on_rfid_data_received,
    #         connection_callback=self.on_rfid_connection_changed,
    #         error_callback=self.on_rfid_error
    #     )

    def create_title_section(self):
        """创建标题区域"""
        title_frame = tk.Frame(self.actual_root, bg=self.industrial_colors['primary_bg'], height=50)
        title_frame.pack(fill='x', padx=5, pady=5)
        title_frame.pack_propagate(False)

        title_label = tk.Label(title_frame, text="RFID标签识别系统",
                               font=("微软雅黑", 20, "bold"),
                               bg=self.industrial_colors['primary_bg'],
                               fg=self.industrial_colors['text_light'])
        title_label.pack(pady=10)

        # 添加分隔线
        separator = ttk.Separator(self.root, orient='horizontal')
        separator.pack(fill='x', padx=10, pady=5)

    def create_dashboard_section(self):
        """创建数据看板区域 - 工业风格优化"""
        dashboard_frame = tk.LabelFrame(self.actual_root, text="数据看板",
                                        font=("微软雅黑", 12, "bold"),
                                        bg=self.industrial_colors['panel_bg'],
                                        bd=2,
                                        relief='ridge',
                                        fg=self.industrial_colors['primary_bg'])
        dashboard_frame.pack(fill='x', padx=15, pady=8)

        # 第一行：设备号、工位名称和软件版本
        row1_frame = tk.Frame(dashboard_frame, bg=self.industrial_colors['panel_bg'])
        row1_frame.pack(fill='x', padx=10, pady=5)

        # 设备号
        tk.Label(row1_frame, text="设备号:", font=("微软雅黑", 10, "bold"),
                 bg=self.industrial_colors['panel_bg'],
                 fg=self.industrial_colors['primary_bg']).pack(side='left', padx=(0, 5))
        tk.Label(row1_frame, text=self.device_id, font=("微软雅黑", 10, "bold"),
                 bg=self.industrial_colors['panel_bg'],
                 fg=self.industrial_colors['accent']).pack(side='left', padx=(0, 40))

        # 工位名称（编辑框）
        tk.Label(row1_frame, text="工位名称:", font=("微软雅黑", 10, "bold"),
                 bg=self.industrial_colors['panel_bg'],
                 fg=self.industrial_colors['primary_bg']).pack(side='left', padx=(0, 5))
        self.station_entry = tk.Entry(row1_frame, width=20, font=("微软雅黑", 10),
                                      relief='solid', bd=1, bg='white')
        self.station_entry.insert(0, "通道机-001")
        self.station_entry.pack(side='left', padx=(0, 40))

        # 软件版本（移到第一行右边）
        tk.Label(row1_frame, text="软件版本:", font=("微软雅黑", 10, "bold"),
                 bg=self.industrial_colors['panel_bg'],
                 fg=self.industrial_colors['primary_bg']).pack(side='left', padx=(0, 5))
        tk.Label(row1_frame, text="v1.0.0", font=("微软雅黑", 10, "bold"),
                 bg=self.industrial_colors['panel_bg'],
                 fg=self.industrial_colors['accent']).pack(side='left')

        # 第二行：当前位置、当前时间
        row2_frame = tk.Frame(dashboard_frame, bg=self.industrial_colors['panel_bg'])
        row2_frame.pack(fill='x', padx=10, pady=5)

        # 当前位置
        tk.Label(row2_frame, text="当前位置:", font=("微软雅黑", 10, "bold"),
                 bg=self.industrial_colors['panel_bg'],
                 fg=self.industrial_colors['primary_bg']).pack(side='left', padx=(0, 5))
        tk.Label(row2_frame, text="经度116.3918173°, 纬度39.9797956°",
                 font=("微软雅黑", 10),
                 bg=self.industrial_colors['panel_bg'],
                 fg=self.industrial_colors['text_dark']).pack(side='left', padx=(0, 40))

        # 当前时间
        tk.Label(row2_frame, text="当前时间:", font=("微软雅黑", 10, "bold"),
                 bg=self.industrial_colors['panel_bg'],
                 fg=self.industrial_colors['primary_bg']).pack(side='left', padx=(0, 5))
        self.time_label = tk.Label(row2_frame, text="", font=("微软雅黑", 10),
                                   bg=self.industrial_colors['panel_bg'],
                                   fg=self.industrial_colors['text_dark'])
        self.time_label.pack(side='left')

        # 第三行：软件运行时间、当前托盘装载数量、今日生产总量、入库总量、出库总量
        row3_frame = tk.Frame(dashboard_frame, bg=self.industrial_colors['panel_bg'])
        row3_frame.pack(fill='x', padx=10, pady=5)

        # 软件运行时间
        tk.Label(row3_frame, text="软件运行时间:", font=("微软雅黑", 10, "bold"),
                 bg=self.industrial_colors['panel_bg'],
                 fg=self.industrial_colors['primary_bg']).pack(side='left', padx=(0, 5))

        self.runtime_label = tk.Label(row3_frame, text="00:00:00",
                                      font=("微软雅黑", 10, "bold"),
                                      bg=self.industrial_colors['panel_bg'],
                                      fg=self.industrial_colors['accent'])
        self.runtime_label.pack(side='left', padx=(0, 20))

        # 当前托盘装载数量
        tk.Label(row3_frame, text="当前识别数量:", font=("微软雅黑", 10, "bold"),
                 bg=self.industrial_colors['panel_bg'],
                 fg=self.industrial_colors['primary_bg']).pack(side='left', padx=(0, 5))
        self.current_load_label = tk.Label(row3_frame, text=str(self.current_load),
                                           font=("微软雅黑", 10, "bold"),
                                           bg=self.industrial_colors['panel_bg'],
                                           fg=self.industrial_colors['accent'])
        self.current_load_label.pack(side='left', padx=(0, 20))

        # 今日生产总量
        tk.Label(row3_frame, text="识别总量:", font=("微软雅黑", 10, "bold"),
                 bg=self.industrial_colors['panel_bg'],
                 fg=self.industrial_colors['primary_bg']).pack(side='left', padx=(0, 5))
        self.daily_label = tk.Label(row3_frame, text=str(self.daily_production),
                                    font=("微软雅黑", 10, "bold"),
                                    bg=self.industrial_colors['panel_bg'],
                                    fg=self.industrial_colors['accent'])
        self.daily_label.pack(side='left', padx=(0, 20))

        # 入库总量
        tk.Label(row3_frame, text="入库总量:", font=("微软雅黑", 10, "bold"),
                 bg=self.industrial_colors['panel_bg'],
                 fg=self.industrial_colors['primary_bg']).pack(side='left', padx=(0, 5))
        self.inbound_label = tk.Label(row3_frame, text=str(self.inbound_total),
                                      font=("微软雅黑", 10, "bold"),
                                      bg=self.industrial_colors['panel_bg'],
                                      fg=self.industrial_colors['accent'])
        self.inbound_label.pack(side='left', padx=(0, 20))

        # 出库总量
        tk.Label(row3_frame, text="出库总量:", font=("微软雅黑", 10, "bold"),
                 bg=self.industrial_colors['panel_bg'],
                 fg=self.industrial_colors['primary_bg']).pack(side='left', padx=(0, 5))
        self.outbound_label = tk.Label(row3_frame, text=str(self.outbound_total),
                                       font=("微软雅黑", 10, "bold"),
                                       bg=self.industrial_colors['panel_bg'],
                                       fg=self.industrial_colors['accent'])
        self.outbound_label.pack(side='left')

        # 第四行：当前产线运行状态 + 运行产线按钮
        row4_frame = tk.Frame(dashboard_frame, bg=self.industrial_colors['panel_bg'])
        row4_frame.pack(fill='x', padx=10, pady=8)

        # 左侧状态区域
        status_left_frame = tk.Frame(row4_frame, bg=self.industrial_colors['panel_bg'])
        status_left_frame.pack(side='left', fill='both', expand=True)

        # 状态标题和状态指示器放在同一行
        status_title = tk.Label(status_left_frame, text="当前产线运行状态:",
                                font=("微软雅黑", 11, "bold"),
                                bg=self.industrial_colors['panel_bg'],
                                fg=self.industrial_colors['primary_bg'])
        status_title.pack(side='left', padx=(0, 10))

        # 状态指示器也放在同一行
        self.normal_status = tk.Label(status_left_frame, text="● 正常",
                                      font=("微软雅黑", 12, "bold"),
                                      fg=self.industrial_colors['success'],
                                      bg=self.industrial_colors['panel_bg'])
        self.normal_status.pack(side='left', padx=(0, 10))

        self.abnormal_status = tk.Label(status_left_frame, text="● 异常",
                                        font=("微软雅黑", 12),
                                        fg=self.industrial_colors['border'],
                                        bg=self.industrial_colors['panel_bg'])
        self.abnormal_status.pack(side='left', padx=(0, 10))

        # 右侧运行产线按钮 - 工业风格按钮
        self.run_button = tk.Button(row4_frame, text="手动运行",
                                    font=("微软雅黑", 11, "bold"),
                                    bg=self.industrial_colors['success'],
                                    fg=self.industrial_colors['text_dark'],
                                    activebackground=self.industrial_colors['success'],
                                    activeforeground=self.industrial_colors['text_dark'],
                                    width=12, height=1, bd=2, relief='raised',
                                    command=self.toggle_production)
        self.run_button.pack(side='right', padx=10)

        # 第五行：异常信息 + 紧急制动按钮
        row5_frame = tk.Frame(dashboard_frame, bg=self.industrial_colors['panel_bg'])
        row5_frame.pack(fill='x', padx=10, pady=8)

        # 左侧异常信息 - 修改为同一行显示
        error_left_frame = tk.Frame(row5_frame, bg=self.industrial_colors['panel_bg'])
        error_left_frame.pack(side='left', fill='x', expand=True)

        # 异常信息标题和内容放在同一行
        tk.Label(error_left_frame, text="异常信息:",
                 font=("微软雅黑", 11, "bold"),
                 bg=self.industrial_colors['panel_bg'],
                 fg=self.industrial_colors['primary_bg']).pack(side='left', padx=(0, 10))

        self.error_label = tk.Label(error_left_frame, text=self.error_message,
                                    font=("微软雅黑", 11),
                                    fg=self.industrial_colors['success'],
                                    bg=self.industrial_colors['panel_bg'])
        self.error_label.pack(side='left')

        # 右侧紧急制动按钮 - 工业风格按钮
        self.emergency_button = tk.Button(row5_frame, text="手动停止",
                                          font=("微软雅黑", 11, "bold"),
                                          bg=self.industrial_colors['danger'],
                                          fg=self.industrial_colors['text_dark'],
                                          activebackground=self.industrial_colors['danger'],
                                          activeforeground=self.industrial_colors['text_dark'],
                                          width=12, height=1, bd=2, relief='raised',
                                          command=self.emergency_stop)
        self.emergency_button.pack(side='right', padx=10)

        # 启动软件运行时间更新
        self.update_software_runtime()

    def create_rfid_info_section(self):
        """创建RFID信息区域（放在中间）- 工业风格优化"""
        tray_frame = tk.LabelFrame(self.actual_root, text="标签信息",
                                   font=("微软雅黑", 12, "bold"),
                                   bg=self.industrial_colors['panel_bg'],
                                   bd=2, relief='ridge',
                                   fg=self.industrial_colors['primary_bg'])
        tray_frame.pack(fill='both', expand=True, padx=15, pady=8)

        # 使用grid布局管理器，使内容能够更好地填充空间
        tray_frame.columnconfigure(0, weight=1)
        tray_frame.rowconfigure(1, weight=1)  # 第二行（文本框区域）可扩展

        # 第一行：托盘编号和托盘装载货物数量
        row1_frame = tk.Frame(tray_frame, bg=self.industrial_colors['panel_bg'])
        row1_frame.grid(row=0, column=0, sticky='ew', padx=10, pady=8)
        row1_frame.columnconfigure(1, weight=1)  # 使托盘编号输入框可以扩展

        # 托盘编号
        tk.Label(row1_frame, text="托盘编号:", font=("微软雅黑", 10, "bold"),
                 bg=self.industrial_colors['panel_bg'],
                 fg=self.industrial_colors['primary_bg']).grid(row=0, column=0, sticky='w', padx=(0, 5))
        self.tray_id_entry = tk.Entry(row1_frame, font=("微软雅黑", 10),
                                      relief='solid', bd=1, bg='white')
        self.tray_id_entry.insert(0, "TRAY-2024-001")
        self.tray_id_entry.grid(row=0, column=1, sticky='ew', padx=(0, 20))

        # 托盘装载货物数量
        tk.Label(row1_frame, text="托盘装载货物数量:", font=("微软雅黑", 10, "bold"),
                 bg=self.industrial_colors['panel_bg'],
                 fg=self.industrial_colors['primary_bg']).grid(row=0, column=2, sticky='w', padx=(0, 5))
        self.tray_load_entry = tk.Entry(row1_frame, width=15, font=("微软雅黑", 10),
                                        relief='solid', bd=1, bg='white')
        self.tray_load_entry.insert(0, "32")
        self.tray_load_entry.grid(row=0, column=3, sticky='w')

        # 第二行：取标内容
        row2_frame = tk.Frame(tray_frame, bg=self.industrial_colors['panel_bg'])
        row2_frame.grid(row=1, column=0, sticky='nsew', padx=10, pady=8)

        tk.Label(row2_frame, text="取标内容:", font=("微软雅黑", 10, "bold"),
                 bg=self.industrial_colors['panel_bg'],
                 fg=self.industrial_colors['primary_bg']).pack(anchor='w', pady=(0, 3))

        # 创建带边框的文本区域 - 横向充满
        text_frame = tk.Frame(row2_frame, bg=self.industrial_colors['border'], bd=1, relief='sunken')
        text_frame.pack(fill='both', expand=True)

        self.fetch_text = tk.Text(text_frame, height=8, font=("Consolas", 9),
                                  relief='flat', bd=0, wrap='word', bg='white')
        scrollbar = tk.Scrollbar(text_frame, command=self.fetch_text.yview)
        self.fetch_text.config(yscrollcommand=scrollbar.set)

        self.fetch_text.pack(side='left', fill='both', expand=True, padx=1, pady=1)
        scrollbar.pack(side='right', fill='y')

        self.fetch_text.insert("1.0", "")

        # 控制按钮区域 - 对齐右下角
        control_frame = tk.Frame(tray_frame, bg=self.industrial_colors['panel_bg'])
        control_frame.grid(row=2, column=0, sticky='e', padx=10, pady=5)

        # 清空显示按钮 - 工业风格
        self.clear_button = tk.Button(control_frame, text="清空显示",
                                      font=("微软雅黑", 9),
                                      bg=self.industrial_colors['secondary_bg'],
                                      fg=self.industrial_colors['text_dark'],
                                      activebackground=self.industrial_colors['secondary_bg'],
                                      activeforeground=self.industrial_colors['text_dark'],
                                      width=10, height=1, bd=2, relief='raised',
                                      command=self.clear_display)
        self.clear_button.pack(side='right', padx=5)

        # 导出数据按钮 - 工业风格
        self.export_button = tk.Button(control_frame, text="导出数据",
                                       font=("微软雅黑", 9),
                                       bg=self.industrial_colors['accent'],
                                       fg=self.industrial_colors['text_dark'],
                                       activebackground=self.industrial_colors['accent'],
                                       activeforeground=self.industrial_colors['text_dark'],
                                       width=10, height=1, bd=2, relief='raised',
                                       command=self.export_tag_data)
        self.export_button.pack(side='right', padx=5)

    def create_socket_section(self):
        """创建RFID读写器连接控制区域（放在最下方）- 工业风格优化"""
        socket_frame = tk.LabelFrame(self.actual_root, text="系统日志",
                                     font=("微软雅黑", 11, "bold"),
                                     bg=self.industrial_colors['panel_bg'],
                                     bd=2, relief='ridge',
                                     fg=self.industrial_colors['primary_bg'])
        socket_frame.pack(fill='both', expand=True, padx=15, pady=8)

        # # 服务器配置
        # config_frame = tk.Frame(socket_frame, bg=self.industrial_colors['panel_bg'])
        # config_frame.pack(fill='x', padx=10, pady=5)

        # tk.Label(config_frame, text="RFID读写器地址:", font=("微软雅黑", 9, "bold"),
        #          bg=self.industrial_colors['panel_bg'],
        #          fg=self.industrial_colors['primary_bg']).pack(side='left', padx=(0, 5))

        # self.host_entry = tk.Entry(config_frame, width=15, font=("微软雅黑", 9),
        #                            relief='solid', bd=1, bg='white')
        # self.host_entry.insert(0, "192.168.31.123")
        # self.host_entry.pack(side='left', padx=(0, 15))

        # tk.Label(config_frame, text="端口号:", font=("微软雅黑", 9, "bold"),
        #          bg=self.industrial_colors['panel_bg'],
        #          fg=self.industrial_colors['primary_bg']).pack(side='left', padx=(0, 5))

        # self.port_entry = tk.Entry(config_frame, width=8, font=("微软雅黑", 9),
        #                            relief='solid', bd=1, bg='white')
        # self.port_entry.insert(0, "2000")
        # self.port_entry.pack(side='left', padx=(0, 20))

        # # 连接状态和控制按钮
        # status_frame = tk.Frame(socket_frame, bg=self.industrial_colors['panel_bg'])
        # status_frame.pack(fill='x', padx=10, pady=8)

        # tk.Label(status_frame, text="连接状态:", font=("微软雅黑", 10, "bold"),
        #          bg=self.industrial_colors['panel_bg'],
        #          fg=self.industrial_colors['primary_bg']).pack(side='left', padx=(0, 5))

        # self.socket_status_label = tk.Label(status_frame, text="未连接",
        #                                     font=("微软雅黑", 10, "bold"),
        #                                     bg=self.industrial_colors['panel_bg'],
        #                                     fg=self.industrial_colors['danger'])
        # self.socket_status_label.pack(side='left', padx=(0, 30))

        # # 连接控制按钮
        # button_frame = tk.Frame(status_frame, bg=self.industrial_colors['panel_bg'])
        # button_frame.pack(side='right')

        # # 连接按钮 - 工业风格
        # self.connect_button = tk.Button(button_frame, text="连接RFID读写器",
        #                                 font=("微软雅黑", 9),
        #                                 bg=self.industrial_colors['accent'],
        #                                 fg=self.industrial_colors['text_dark'],
        #                                 activebackground=self.industrial_colors['accent'],
        #                                 activeforeground=self.industrial_colors['text_dark'],
        #                                 width=15, height=1, bd=2, relief='raised',
        #                                 command=self.connect_rfid)
        # self.connect_button.pack(side='left', padx=(0, 10))

        # # 断开按钮 - 工业风格
        # self.disconnect_button = tk.Button(button_frame, text="断开连接",
        #                                    font=("微软雅黑", 9),
        #                                    bg=self.industrial_colors['secondary_bg'],
        #                                    fg=self.industrial_colors['text_dark'],
        #                                    activebackground=self.industrial_colors['secondary_bg'],
        #                                    activeforeground=self.industrial_colors['text_dark'],
        #                                    width=12, height=1, bd=2, relief='raised',
        #                                    command=self.disconnect_rfid,
        #                                    state='disabled')
        # self.disconnect_button.pack(side='left')

        # 消息显示区域
        msg_frame = tk.Frame(socket_frame, bg=self.industrial_colors['panel_bg'])
        msg_frame.pack(fill='both', expand=True, padx=10, pady=5)

        tk.Label(msg_frame, text="通信日志:", font=("微软雅黑", 9, "bold"),
                 bg=self.industrial_colors['panel_bg'],
                 fg=self.industrial_colors['primary_bg']).pack(anchor='w')

        # 创建带边框的消息文本区域
        msg_text_frame = tk.Frame(msg_frame, bg=self.industrial_colors['border'], bd=1, relief='sunken')
        msg_text_frame.pack(fill='both', expand=True, pady=3)

        self.message_text = tk.Text(msg_text_frame, font=("Consolas", 8),
                                    relief='flat', bd=0, wrap='word', bg='white')
        scrollbar = tk.Scrollbar(msg_text_frame, command=self.message_text.yview)
        self.message_text.config(yscrollcommand=scrollbar.set)

        self.message_text.pack(side='left', fill='x', expand=True, padx=1, pady=1)
        scrollbar.pack(side='right', fill='y')

        self.message_text.config(state='disabled')

    def update_time(self):
        """更新当前时间显示"""
        current_time = datetime.now().strftime(" %Y年%m月%d日 %H:%M:%S")
        self.time_label.config(text=current_time)
        self.root.after(1000, self.update_time)

    def toggle_production(self):
        """切换产线运行状态 - 主要修改部分"""
        self.is_running = not self.is_running
        if self.is_running:
            print("running")
            # 发送开始生产指令到RFID读写器
            # if self.rfid_reader.get_connection_status():
            #     if self.rfid_reader.send_single_cmd('CMD_RFID_LOOP_START'):
            #         self.add_message("发送开始生产指令成功")
            #     else:
            #         self.add_message("发送开始生产指令失败")
            # else:
            #     self.add_message("RFID读写器未连接，无法发送指令")
            self.serial_comm.write_register(self.yellow_light, True, timeout=0.5)
            self.serial_comm.write_register(self.green_light, False, timeout=0.5)
            self.rfid_reader_serial.startloop()
            self.add_message("手动运行：黄灯亮，启动RFID读取")
        else:
            print("not running")
            self.rfid_reader_serial.stoploop()
            self.serial_comm.write_register(self.green_light, True, timeout=0.5)
            self.serial_comm.write_register(self.yellow_light, False, timeout=0.5)
            self.add_message("手动停止：绿灯亮，停止RFID读取")
            self._display_tags_in_fetch()

    def emergency_stop(self):
        """紧急制动"""
        self.is_running = False
        # self.run_button.config(text="手动运行", bg=self.industrial_colors['success'])
        # self.normal_status.config(fg=self.industrial_colors['border'])
        # self.abnormal_status.config(fg=self.industrial_colors['danger'])
        # self.error_label.config(text="紧急制动！", fg=self.industrial_colors['danger'])
        # self.add_message("紧急制动！系统已停止")

        # 发送紧急停止指令到RFID读写器
        # if self.rfid_reader.get_connection_status():
        #     if self.rfid_reader.send_single_cmd('CMD_RFID_LOOP_STOP'):
        #         self.add_message("发送紧急停止指令成功")
        #         self.report_rfid_tags_via_mqtt()
        #     else:
        #         self.add_message("发送紧急停止指令失败")
        # else:
        #     self.add_message("RFID读写器未连接，无法发送指令")

        self.rfid_reader_serial.stoploop()
        self.serial_comm.write_register(self.green_light, True, timeout=0.5)
        self.serial_comm.write_register(self.yellow_light, False, timeout=0.5)
        self.add_message("手动停止：绿灯亮，停止RFID读取")
        self._display_tags_in_fetch()
        messagebox.showwarning("手动停止", "数据已经上报！")

    def start_rfid_loop_query(self, b_on):
        print(f"start_rfid_loop_query  === {b_on}")
        if b_on:
            # 入库/出库开始：黄灯亮，清空缓存，不启动RFID读取（等待MIDDLE状态写入后再读取）
            self.serial_comm.write_register(self.yellow_light, True, timeout=0.5)
            self.serial_comm.write_register(self.green_light, False, timeout=0.5)
            self.tag_history.clear()
            self.write_done = False
            self.write_in_progress = False
        else:
            # 入库/出库结束：绿灯亮，停止RFID读取
            self.serial_comm.write_register(self.green_light, True, timeout=0.5)
            self.serial_comm.write_register(self.yellow_light, False, timeout=0.5)
            self.rfid_reader_serial.stoploop()

    # RFID读写器相关方法
    def auto_connect(self):
        """自动连接RFID读写器和MQTT客户端（分别启动）"""
        self.add_message("系统启动，准备连接RFID读写器和MQTT客户端...")

        # def connect_rfid_thread():
        #     """RFID读写器连接线程"""
        #     time.sleep(2)  # 延迟2秒连接，让界面先加载完成
        #     if self.rfid_reader.connect():
        #         self.add_message("自动连接RFID读写器成功")
        #     else:
        #         self.add_message("自动连接RFID读写器失败，请手动连接")

        def connect_mqtt_thread():
            """MQTT客户端连接线程"""
            time.sleep(3)  # 延迟3秒连接，避免同时启动造成资源竞争
            self.start_mqtt_client()

        def connect_serial_thread():
            """串口连接线程"""
            time.sleep(4)  # 延迟4秒连接，避免资源竞争
            self.start_serial_communication()

            # 新增：延迟一段时间后连接条码扫描器
            time.sleep(2)  # 再等待2秒
            self.start_barcode_scanner_communication()

            # 新增：SFM2200
            time.sleep(1)
            self.start_rfid_reader_serial()

        # 分别启动两个线程
        # threading.Thread(target=connect_rfid_thread, daemon=True).start()
        threading.Thread(target=connect_mqtt_thread, daemon=True).start()
        threading.Thread(target=connect_serial_thread, daemon=True).start()

    # def connect_rfid(self):
    #     """连接RFID读写器"""
    #     # 更新RFID读写器配置
    #     try:
    #         host = self.host_entry.get()
    #         port = int(self.port_entry.get())
    #         self.rfid_reader.host = host
    #         self.rfid_reader.port = port
    #     except ValueError:
    #         messagebox.showerror("错误", "端口号必须是数字")
    #         return

    #     def connect_thread():
    #         if self.rfid_reader.connect():
    #             self.add_message(f"手动连接RFID读写器 {host}:{port} 成功")

    #     threading.Thread(target=connect_thread, daemon=True).start()
    #     self.connect_button.config(state='disabled', text="连接中...")
    #     self.add_message(f"正在连接RFID读写器 {host}:{port}...")

    # def disconnect_rfid(self):
    #     """断开RFID读写器连接"""
    #     self.rfid_reader.disconnect()
    #     self.add_message("手动断开RFID读写器连接")

    # # RFID读写器回调函数
    # def on_rfid_data_received(self, data):
    #     """RFID数据接收回调"""

    #     def update_ui():
    #         if isinstance(data, bytes):
    #             # 处理二进制数据
    #             hex_str = ' '.join([f'{b:02X}' for b in data])
    #             self.add_message(f"收到RFID数据: {hex_str}")
    #             self.process_rfid_data(data)
    #         elif isinstance(data, dict):
    #             # 处理JSON数据
    #             self.add_message(f"收到RFID JSON数据: {data}")
    #             self.handle_json_data(data)

    #     self.root.after(0, update_ui)

    # def on_rfid_connection_changed(self, connected, message):
    #     """RFID连接状态回调"""

    #     def update_ui():
    #         if connected:
    #             self.socket_status_label.config(text="● 已连接", fg=self.industrial_colors['success'])
    #             self.connect_button.config(state='disabled', text="已连接")
    #             self.disconnect_button.config(state='normal', bg=self.industrial_colors['danger'])
    #             self.host_entry.config(state='disabled')
    #             self.port_entry.config(state='disabled')
    #         else:
    #             self.socket_status_label.config(text="● 未连接", fg=self.industrial_colors['danger'])
    #             self.connect_button.config(state='normal', text="连接RFID读写器")
    #             self.disconnect_button.config(state='disabled', bg=self.industrial_colors['secondary_bg'])
    #             self.host_entry.config(state='normal')
    #             self.port_entry.config(state='normal')

    #         self.add_message(message)

    #     self.root.after(0, update_ui)

    # def on_rfid_error(self, error_msg):
    #     """RFID错误回调"""

    #     def update_ui():
    #         self.add_message(f"RFID错误: {error_msg}")
    #         # 只在重要错误时显示弹窗 RFID错误弹窗
    #         # if "连接" in error_msg or "断开" in error_msg:
    #         #     messagebox.showerror("RFID错误", error_msg)

    #     self.root.after(0, update_ui)

    def process_rfid_data(self, data: bytes):
        """处理RFID二进制数据"""
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
                self.normal_status.config(fg=self.industrial_colors['success'])
                self.abnormal_status.config(fg=self.industrial_colors['border'])
                if not self.is_running:
                    self.is_running = True
                    self.run_button.config(text="手动停止", bg=self.industrial_colors['warning'])
            else:
                self.normal_status.config(fg=self.industrial_colors['border'])
                self.abnormal_status.config(fg=self.industrial_colors['danger'])
                if self.is_running:
                    self.is_running = False
                    self.run_button.config(text="手动运行", bg=self.industrial_colors['success'])

        if 'error_message' in status_data:
            self.error_message = status_data['error_message']
            self.error_label.config(text=self.error_message)
            if status_data['error_message'] != "无异常":
                self.error_label.config(fg=self.industrial_colors['danger'])
            else:
                self.error_label.config(fg=self.industrial_colors['success'])

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

        return tag

    def update_rfid_data(self, data: bytes):
        """根据二进制数据更新RFID数据（TID去重）"""
        # 使用RFIDTag类解析数据
        tag = self.process_rfid_data_epc_tid_user(data)

        if tag.success:
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

                # 关键修改：移除对每日生产总量的直接更新，只在完成出入库时更新
                # self.daily_production += 1
                # self.daily_label.config(text=str(self.daily_production))

                # 更新界面显示
                # display_text = self._format_tag_list_display(tag)
                # self.update_element_text(self.fetch_text, display_text, clear_first=False)

                # 添加消息
                self.add_message(f"读取到新标签: {tag.product_name} (TID: {tag.tid}, RSSI: {tag.rssi:.1f}dBm)")
            else:
                # TID已存在，只更新当前标签，不添加到历史记录和显示
                self.current_tag = tag
                self.add_message(f"检测到重复标签，TID: {tag.tid} 已存在")
        else:
            self.add_message(f"标签解析失败: {tag.error_message}")

    def _display_tags_in_fetch(self):
        """将当前tag_history中的标签显示在取标内容窗口"""
        if not self.tag_history:
            self.update_element_text(self.fetch_text, "暂无识别到的标签", clear_first=True)
            return

        display_lines = [f"=== 手动停止，识别到 {len(self.tag_history)} 个标签 ==="]
        for i, tag in enumerate(self.tag_history, 1):
            display_lines.append(
                f"{i}. EPC: {tag.epc}  USER: {tag.user_data}  "
                f"RSSI: {tag.rssi:.1f}dBm  天线: {tag.antenna_num}")
        display_text = "\n".join(display_lines)
        self.update_element_text(self.fetch_text, display_text, clear_first=True)

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
                f"天线: {tag.antenna_num}")

    def update_ui_with_reported_tags(self, tag_data, data_type, barcodes=None, validation=None):
        """用上报的标签数据更新UI（含写入校验结果）"""
        if barcodes is None:
            barcodes = []
        if validation is None:
            validation = {}

        self.update_element_text(self.fetch_text, "", clear_first=True)

        if not tag_data and not barcodes:
            return

        display_lines = []
        direction_text = "入库" if data_type == DATA_TYPE_INBOUND else "出库"

        display_lines.append(f"=== 本次{direction_text}完成 ===")

        # 显示写入校验结果
        if self.write_done:
            verified = validation.get('write_verified_count', 0)
            total = validation.get('write_total_count', 0)
            if total > 0 and verified == total:
                display_lines.append(f"写入校验: 通过 ({verified}/{total}个标签USER_DATA匹配)")
            elif total > 0:
                display_lines.append(f"写入校验: 失败 ({verified}/{total}个标签USER_DATA匹配)")
            else:
                display_lines.append("写入校验: 写入成功，未读到标签")
        else:
            display_lines.append("写入校验: 写标签未执行或失败")

        # 数量比对
        if validation.get('errors'):
            for err in validation['errors']:
                display_lines.append(f"异常: {err}")
        elif tag_data and barcodes:
            if len(tag_data) == len(barcodes):
                display_lines.append(f"数量校验: 通过 (标签{len(tag_data)}个 = 条码{len(barcodes)}个)")
            else:
                display_lines.append(
                    f"数量校验: 不一致 (标签{len(tag_data)}个, 条码{len(barcodes)}个)")

        # 显示RFID标签
        if tag_data:
            display_lines.append(f"\nRFID标签 ({len(tag_data)}个):")
            for i, tag in enumerate(tag_data, 1):
                verify_mark = "✓" if tag.get('write_verified', False) else "✗"
                display_lines.append(
                    f"{i}. [{verify_mark}] 产品: {tag['product_name']}  EPC: {tag['epc']}   USER_DATA: {tag['user_data']}")

        # 显示条码
        if barcodes:
            display_lines.append(f"\n条码 ({len(barcodes)}个):")
            for i, barcode in enumerate(barcodes, 1):
                display_lines.append(f"{i}. {barcode}")

        display_text = "\n".join(display_lines)
        self.update_element_text(self.fetch_text, display_text, clear_first=False)

        msg = f"{direction_text}完成"
        if tag_data:
            msg += f"，{len(tag_data)}个标签"
        if barcodes:
            msg += f"，{len(barcodes)}个条码"
        self.add_message(msg)

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
        # 停止条码扫描器
        if hasattr(self, 'bar_scanner') and self.bar_scanner:
            self.bar_scanner.stop_receive_loop()
            self.bar_scanner.close()
            self.add_message("条码扫描器已关闭")
        if hasattr(self, 'rfid_reader'):
            # self.rfid_reader.disconnect()
            pass
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
        # 停止 TCP Server
        if hasattr(self, 'tcp_server'):
            self.tcp_server.stop()
            self.add_message("TCP Server 已关闭")

        # 关闭串口 RFID 读写器
        if hasattr(self, 'rfid_reader_serial'):
            print('close')
            self.rfid_reader_serial.stoploop()  # 发送停止指令
            self.rfid_reader_serial.stop_receive_loop()  # 若启动了接收循环则停止
            self.rfid_reader_serial.close()
            self.add_message("串口 RFID 读写器已关闭")

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

    def send_mqtt_command(self, command, data_type, data=None):
        """发送MQTT命令"""
        if not hasattr(self, 'mqtt_client') or not self.mqtt_client.connected:
            self.add_message("MQTT客户端未连接，无法发送命令")
            return False

        try:
            command_data = {
                "cmd": command,
                "data_type": "inbound" if data_type == DATA_TYPE_INBOUND else "outbound",
                "tag_count": len(data.get('tags', [])) if data and 'tags' in data else 0,
                "barcode_count": len(data.get('barcodes', [])) if data and 'barcodes' in data else 0
            }
            if data:
                command_data.update(data)

            message = json.dumps(command_data)
            self.mqtt_client.publish(self.mqtt_client.command_topic, message)

            self.add_message(f"发送MQTT命令: {command}")
            if command_data.get('tag_count', 0) > 0:
                self.add_message(f"  标签数量: {command_data['tag_count']}个")
            if command_data.get('barcode_count', 0) > 0:
                self.add_message(f"  条码数量: {command_data['barcode_count']}个")

            return True
        except Exception as e:
            self.add_message(f"发送MQTT命令失败: {e}")
            return False

    def _send_tcp_pass_message(self):
        """通过TCP向连接的客户端发送通行完成消息"""
        tag_count = len(self.tag_history)
        msg = json.dumps({"type": "pass", "number": tag_count}, ensure_ascii=False)
        self.tcp_server.send_to_all(msg)

    def _send_tcp_cargo_in_message(self):
        """通过TCP向连接的客户端发送货物进入消息"""
        msg = json.dumps({"type": "cargo_in"}, ensure_ascii=False)
        self.tcp_server.send_to_all(msg)
        self.add_message("TCP发送: cargo_in")

    def _send_tcp_cargo_out_message(self):
        """通过TCP向连接的客户端发送货物离开消息"""
        msg = json.dumps({"type": "cargo_out"}, ensure_ascii=False)
        self.tcp_server.send_to_all(msg)
        self.add_message("TCP发送: cargo_out")

    @staticmethod
    def _hex_str_to_bytes(hex_str: str) -> list:
        """将十六进制字符串(如'C090C000000A4B28'或'30 32 57 ...')转为整数列表"""
        clean = hex_str.replace(' ', '')
        return [int(clean[i:i + 2], 16) for i in range(0, len(clean), 2)]

    def _send_tcp_rfid_data_message(self, tid: str, epc: str, user_data: str, write_result: str):
        """通过TCP向连接的客户端发送RFID标签数据"""
        msg = json.dumps({
            "type": "report_rfid",
            "tid": self._hex_str_to_bytes(tid) if tid else [],
            "epc": self._hex_str_to_bytes(epc) if epc else [],
            "user_data": self._hex_str_to_bytes(user_data) if user_data else [],
            "write_result": write_result
        }, ensure_ascii=False)
        self.tcp_server.send_to_all(msg)
        self.add_message(f"TCP发送: report_rfid write_result={write_result}")

    def report_rfid_tags_via_mqtt(self, data_type=DATA_TYPE_INBOUND, barcodes=None):
        """通过MQTT报告RFID标签（含写入校验结果）"""
        print(f"report_rfid_tags_via_mqtt type={data_type}")
        print(f"当前列表长度: {len(self.tag_history)}")

        if barcodes is None:
            barcodes = []

        if self.tag_history or barcodes:
            recent_tags = self.tag_history[:]
            tag_data = []
            write_match_count = 0
            for tag in recent_tags:
                if tag.success:
                    # 校验读回的 user_data 是否与写入的内容一致
                    read_user_data = tag.user_data.replace(' ', '').upper()
                    if self.actual_write_data:
                        written_user_data = self.actual_write_data.hex().upper()
                    else:
                        written_user_data = self.FIXED_USER_DATA.hex().upper()
                    user_data_match = (read_user_data == written_user_data)
                    if user_data_match:
                        write_match_count += 1

                    # 通过TCP发送RFID标签数据
                    write_result_str = "success" if user_data_match else "fail"
                    self._send_tcp_rfid_data_message(
                        tid=tag.tid,
                        epc=tag.epc,
                        user_data=tag.user_data,
                        write_result=write_result_str
                    )

                    tag_data.append({
                        'epc': tag.epc,
                        'tid': tag.tid,
                        'user_data': tag.user_data,
                        'rssi': tag.rssi,
                        'timestamp': tag.timestamp,
                        'product_name': tag.product_name,
                        'antenna_num': tag.antenna_num,
                        'write_verified': user_data_match
                    })

            if tag_data or barcodes:
                # 根据数据类型更新入库或出库总量
                if data_type == DATA_TYPE_INBOUND:
                    self.inbound_total += len(tag_data)
                    self.inbound_label.config(text=str(self.inbound_total))
                elif data_type == DATA_TYPE_OUTBOUND:
                    self.outbound_total += len(tag_data)
                    self.outbound_label.config(text=str(self.outbound_total))

                self.daily_production = self.inbound_total + self.outbound_total
                self.daily_label.config(text=str(self.daily_production))

                # 校验结果汇总
                validation = {
                    'tag_count': len(tag_data),
                    'barcode_count': len(barcodes),
                    'write_verified_count': write_match_count,
                    'write_total_count': len(tag_data),
                    'tag_barcode_match': len(tag_data) == len(barcodes),
                    'errors': []
                }
                if write_match_count < len(tag_data):
                    validation['errors'].append(
                        f"写入校验失败: {len(tag_data) - write_match_count}个标签USER_DATA不匹配")
                if len(tag_data) != len(barcodes):
                    validation['errors'].append(
                        f"数量不一致: 标签{len(tag_data)}个, 条码{len(barcodes)}个")

                # 构建上报数据
                report_data = {
                    'tags': tag_data,
                    'barcodes': barcodes,
                    'validation': validation,
                    'write_success': self.write_done
                }

                result = self.send_mqtt_command('report_tags', data_type, report_data)
                self.update_ui_with_reported_tags(tag_data, data_type, barcodes, validation)

                self.tag_history.clear()
                self.write_done = False
                self.actual_write_data = None
                return result
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
                self.serial_comm.write_register(self.green_light, True, timeout=0.5)
                self.serial_comm.write_register(self.yellow_light, False, timeout=0.5)
                self.serial_comm.write_register(self.red_light, False, timeout=0.5)
                self.start_serial_reading_loop()
                return True
            else:
                self.add_message("串口连接失败")
                return False
        except Exception as e:
            self.add_message(f"串口连接异常: {e}")
            return False

    def start_serial_reading_loop(self):
        """启动串口读取循环（带状态确认机制，支持不同确认标准）"""

        def read_loop():
            # 状态机定义
            STATE_IDLE = 0
            STATE_INBOUND_START = 1
            STATE_INBOUND_MIDDLE = 2
            STATE_INBOUND_END = 3
            STATE_OUTBOUND_START = 4
            STATE_OUTBOUND_MIDDLE = 5
            STATE_OUTBOUND_END = 6

            # 状态变量
            current_state = STATE_IDLE
            previous_status = 0
            read_interval = 0.05

            # 防重复报告机制
            last_report_time = 0
            report_cooldown = 1.0

            # 超时检测机制
            last_state_change_time = time.time()
            idle_timeout = 10.0
            process_start_time = None

            # 状态确认机制 - 使用不同的标准
            DETECT_ON_COUNT = 1  # 遮挡状态需要连续检测的次数
            DETECT_OFF_COUNT = 2  # 不遮挡状态需要连续检测的次数
            DETECT_INTERVAL = 0.05  # 状态确认检测间隔（秒）

            current_detect_count = 0
            confirmed_status = 0
            target_status = 0
            in_confirmation = False
            last_raw_status = 0
            last_confirm_check_time = 0  # 上次状态确认检查时间

            def get_required_count(status):
                """根据目标状态获取需要的确认次数"""
                if status == 0x00:  # 无遮挡
                    return DETECT_OFF_COUNT
                else:  # 遮挡状态 (0x01, 0x02, 0x03)
                    return DETECT_ON_COUNT

            while self.serial_comm.is_open():
                try:
                    start_time = time.time()
                    data, length = self.serial_comm.read_register(0x02, timeout=0.5)

                    if length > 0 and len(data) >= 4:
                        raw_status = data[3]
                        last_raw_status = raw_status

                        current_time = time.time()

                        # 状态确认逻辑（带间隔控制）
                        if not in_confirmation:
                            # 不在确认状态，立即检查是否需要开始确认
                            if raw_status != confirmed_status:
                                in_confirmation = True
                                target_status = raw_status
                                current_detect_count = 1
                                last_confirm_check_time = current_time
                                required_count = get_required_count(target_status)
                                print(
                                    f"开始状态确认: {confirmed_status:02X}->{target_status:02X} 间隔{DETECT_INTERVAL}s 需{required_count}次")
                        else:
                            # 在确认状态，检查间隔
                            if current_time - last_confirm_check_time >= DETECT_INTERVAL:
                                last_confirm_check_time = current_time

                                if raw_status == target_status:
                                    current_detect_count += 1
                                    required_count = get_required_count(target_status)

                                    if current_detect_count >= required_count:
                                        # 确认完成
                                        old_confirmed_status = confirmed_status
                                        confirmed_status = target_status
                                        in_confirmation = False
                                        current_detect_count = 0

                                        # 状态确认完成，进行状态机处理
                                        current_status = confirmed_status
                                        self.current_status = current_status

                                        print(f"状态确认完成: {old_confirmed_status:02X}->{current_status:02X}, 当前状态: {current_state}")

                                        # 记录状态变化时间
                                        last_state_change_time = time.time()

                                        # 原有的状态机处理逻辑
                                        old_state = current_state

                                        if current_state == STATE_IDLE:
                                            if current_status == 0x01:  # 光栅1遮挡
                                                current_state = STATE_INBOUND_START
                                                self.direction = 1
                                                self.start_rfid_loop_query(True)
                                                process_start_time = time.time()
                                                print("入库开始：光栅1遮挡")

                                                # 新增：清空条码缓存，开始收集入库条码
                                                self.clear_barcode_cache()

                                                # 货物进入通道，执行写标签（覆盖Path1和Path2）
                                                if not self.write_done and not self.write_in_progress:
                                                    self._execute_fixed_write()

                                                self._send_tcp_cargo_in_message()

                                            elif current_status == 0x02:  # 光栅2遮挡
                                                current_state = STATE_OUTBOUND_START
                                                self.direction = 2
                                                self.start_rfid_loop_query(True)
                                                process_start_time = time.time()
                                                print("出库开始：光栅2遮挡")

                                                # 新增：清空条码缓存，开始收集出库条码
                                                self.clear_barcode_cache()

                                                # 货物进入通道，执行写标签（覆盖Path1和Path2）
                                                if not self.write_done and not self.write_in_progress:
                                                    self._execute_fixed_write()

                                                self._send_tcp_cargo_in_message()

                                        elif current_state == STATE_INBOUND_START:
                                            if current_status == 0x03:  # 光栅1+2同时遮挡
                                                current_state = STATE_INBOUND_MIDDLE
                                                print("入库中间：光栅1+2同时遮挡")
                                                if not self.write_done and not self.write_in_progress:
                                                    self._execute_fixed_write()
                                            elif current_status == 0x00:  # 无遮挡
                                                current_state = STATE_INBOUND_END
                                                print("入库路径2：光栅1遮挡后直接无遮挡")
                                            elif current_status == 0x02:  # 光栅2遮挡
                                                current_state = STATE_INBOUND_END
                                                print("入库结束：光栅2遮挡（直接进入）")

                                        elif current_state == STATE_INBOUND_MIDDLE:
                                            if current_status == 0x02:  # 光栅2遮挡
                                                current_state = STATE_INBOUND_END
                                                print("入库结束：光栅2遮挡")
                                            elif current_status == 0x00:  # 无遮挡
                                                if self.write_done:
                                                    # 写入已完成，货物快速通过，视为正常完成
                                                    current_state = STATE_IDLE
                                                    self.direction = 0
                                                    self.start_rfid_loop_query(False)
                                                    process_start_time = None
                                                    if current_time - last_report_time >= report_cooldown:
                                                        current_barcodes = self.get_all_barcodes()
                                                        self._send_tcp_pass_message()
                                                        self._send_tcp_cargo_out_message()
                                                        self.report_rfid_tags_via_mqtt(DATA_TYPE_INBOUND,
                                                                                       barcodes=current_barcodes)
                                                        last_report_time = current_time
                                                        print(f"入库完成（写入后快速通过），包含{len(current_barcodes)}个条码")
                                                else:
                                                    # 入库中断
                                                    self._send_tcp_cargo_out_message()
                                                    current_state = STATE_IDLE
                                                    self.direction = 0
                                                    self.start_rfid_loop_query(False)
                                                    process_start_time = None
                                                    self.tag_history.clear()
                                                    self.clear_barcode_cache()
                                                    print("入库中断：中间状态检测到无遮挡")

                                        elif current_state == STATE_INBOUND_END:
                                            if current_status == 0x02:  # 光栅2遮挡
                                                print("入库结束：检测到光栅2遮挡")
                                            elif current_status == 0x00:  # 无遮挡
                                                # 完成入库
                                                current_state = STATE_IDLE
                                                self.direction = 0
                                                self.start_rfid_loop_query(False)
                                                process_start_time = None

                                                # 防重复报告
                                                if current_time - last_report_time >= report_cooldown:
                                                    # 新增：获取本次入库的所有条码
                                                    current_barcodes = self.get_all_barcodes()
                                                    self._send_tcp_pass_message()
                                                    self._send_tcp_cargo_out_message()
                                                    self.report_rfid_tags_via_mqtt(DATA_TYPE_INBOUND,
                                                                                   barcodes=current_barcodes)
                                                    last_report_time = current_time
                                                    print(f"入库完成，包含{len(current_barcodes)}个条码")
                                                else:
                                                    print("入库完成（跳过重复报告）")
                                            elif current_status == 0x01:  # 又回到光栅1遮挡
                                                # 异常情况
                                                current_state = STATE_IDLE
                                                self.direction = 0
                                                self.start_rfid_loop_query(False)
                                                process_start_time = None
                                                self.tag_history.clear()  # 清空未完成的标签

                                                # 新增：异常时也清空条码缓存
                                                self.clear_barcode_cache()

                                                print("入库异常：结束状态又回到光栅1遮挡")

                                        elif current_state == STATE_OUTBOUND_START:
                                            if current_status == 0x03:  # 光栅1+2同时遮挡
                                                current_state = STATE_OUTBOUND_MIDDLE
                                                print("出库中间：光栅1+2同时遮挡")
                                                if not self.write_done and not self.write_in_progress:
                                                    self._execute_fixed_write()
                                            elif current_status == 0x00:  # 无遮挡
                                                current_state = STATE_OUTBOUND_END
                                                print("出库路径2：光栅2遮挡后直接无遮挡")
                                            elif current_status == 0x01:  # 光栅1遮挡
                                                current_state = STATE_OUTBOUND_END
                                                print("出库结束：光栅1遮挡（直接进入）")

                                        elif current_state == STATE_OUTBOUND_MIDDLE:
                                            if current_status == 0x01:  # 光栅1遮挡
                                                current_state = STATE_OUTBOUND_END
                                                print("出库结束：光栅1遮挡")
                                            elif current_status == 0x00:  # 无遮挡
                                                if self.write_done:
                                                    # 写入已完成，货物快速通过，视为正常完成
                                                    current_state = STATE_IDLE
                                                    self.direction = 0
                                                    self.start_rfid_loop_query(False)
                                                    process_start_time = None
                                                    if current_time - last_report_time >= report_cooldown:
                                                        current_barcodes = self.get_all_barcodes()
                                                        self._send_tcp_pass_message()
                                                        self._send_tcp_cargo_out_message()
                                                        self.report_rfid_tags_via_mqtt(DATA_TYPE_OUTBOUND,
                                                                                       barcodes=current_barcodes)
                                                        last_report_time = current_time
                                                        print(f"出库完成（写入后快速通过），包含{len(current_barcodes)}个条码")
                                                else:
                                                    # 出库中断
                                                    self._send_tcp_cargo_out_message()
                                                    current_state = STATE_IDLE
                                                    self.direction = 0
                                                    self.start_rfid_loop_query(False)
                                                    process_start_time = None
                                                    self.tag_history.clear()
                                                    self.clear_barcode_cache()
                                                    print("出库中断：中间状态检测到无遮挡")

                                        elif current_state == STATE_OUTBOUND_END:
                                            if current_status == 0x01:  # 光栅1遮挡
                                                print("出库结束：检测到光栅1遮挡")
                                            elif current_status == 0x00:  # 无遮挡
                                                # 完成出库
                                                current_state = STATE_IDLE
                                                self.direction = 0
                                                self.start_rfid_loop_query(False)
                                                process_start_time = None

                                                # 防重复报告
                                                if current_time - last_report_time >= report_cooldown:
                                                    # 新增：获取本次出库的所有条码
                                                    current_barcodes = self.get_all_barcodes()
                                                    self._send_tcp_pass_message()
                                                    self._send_tcp_cargo_out_message()
                                                    self.report_rfid_tags_via_mqtt(DATA_TYPE_OUTBOUND,
                                                                                   barcodes=current_barcodes)
                                                    last_report_time = current_time
                                                    print(f"出库完成，包含{len(current_barcodes)}个条码")
                                                else:
                                                    print("出库完成（跳过重复报告）")
                                            elif current_status == 0x02:  # 又回到光栅2遮挡
                                                # 异常情况
                                                current_state = STATE_IDLE
                                                self.direction = 0
                                                self.start_rfid_loop_query(False)
                                                process_start_time = None
                                                self.tag_history.clear()  # 清空未完成的标签

                                                # 新增：异常时也清空条码缓存
                                                self.clear_barcode_cache()

                                                print("出库异常：结束状态又回到光栅2遮挡")

                                        # 处理其他异常状态转换
                                        if current_status == 0x00 and current_state != STATE_IDLE:
                                            if current_state not in [STATE_INBOUND_END, STATE_OUTBOUND_END]:
                                                if (current_state == STATE_INBOUND_START and previous_status == 0x01) or \
                                                        (
                                                                current_state == STATE_OUTBOUND_START and previous_status == 0x02):
                                                    print(f"允许的路径2：状态{current_state}检测到无遮挡")
                                                else:
                                                    print(f"异常中断：状态{current_state}检测到无遮挡，不累积识别总量")
                                                    self._send_tcp_cargo_out_message()
                                                    self.start_rfid_loop_query(False)
                                                    current_state = STATE_IDLE
                                                    self.direction = 0
                                                    process_start_time = None
                                                    self.tag_history.clear()  # 清空未完成的标签记录

                                                    # 新增：异常中断时也清空条码缓存
                                                    self.clear_barcode_cache()

                                        # 如果状态发生变化，更新状态变化时间
                                        if old_state != current_state:
                                            last_state_change_time = time.time()

                                        previous_status = current_status

                                    else:
                                        # 继续确认中
                                        print(
                                            f"确认中: {target_status:02X} {current_detect_count}/{required_count}次 下次{last_confirm_check_time + DETECT_INTERVAL:.2f}s")
                                else:
                                    # 状态变化，重新开始确认
                                    target_status = raw_status
                                    current_detect_count = 1
                                    required_count = get_required_count(target_status)
                                    print(f"确认中断，重新确认: {target_status:02X} 需{required_count}次")

                        # 调试信息
                        # if in_confirmation and current_detect_count < get_required_count(target_status):
                        #     required_count = get_required_count(target_status)
                        #     print(f"状态确认中: {target_status:02X} 连续{current_detect_count}/{required_count}次")

                        self.handle_serial_data(data)

                    # 超时检测
                    current_time = time.time()
                    if current_state != STATE_IDLE and process_start_time is not None:
                        if current_time - last_state_change_time > idle_timeout:
                            print(f"超时检测：状态{current_state}超过{idle_timeout}秒无变化，重置状态")
                            self._send_tcp_cargo_out_message()
                            self.start_rfid_loop_query(False)
                            current_state = STATE_IDLE
                            self.direction = 0
                            process_start_time = None
                            self.tag_history.clear()
                            print("系统已重置：超时保护，不累积识别总量")
                            # 重置确认机制
                            in_confirmation = False
                            confirmed_status = 0
                            target_status = 0
                            current_detect_count = 0
                            previous_status = 0
                            last_confirm_check_time = 0

                            # 新增：超时重置时也清空条码缓存
                            self.clear_barcode_cache()

                    # 控制读取间隔
                    elapsed = time.time() - start_time
                    sleep_time = max(0, read_interval - elapsed)
                    if sleep_time > 0:
                        time.sleep(sleep_time)

                except Exception as e:
                    self.add_message(f"串口读取错误: {e}")
                    time.sleep(0.5)

        threading.Thread(target=read_loop, daemon=True).start()
        self.add_message("串口读取循环已启动（带状态确认机制，支持不同确认标准）")

    def handle_serial_data(self, data):
        """处理串口接收到的数据"""

        def update_ui():
            try:
                # 将字节数据转换为十六进制字符串显示
                hex_data = ' '.join([f'{b:02X}' for b in data])
                # self.add_message(f"串口收到数据: {hex_data}")
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

        except Exception as e:
            self.add_message(f"处理寄存器响应错误: {e}")

    def update_software_runtime(self):
        """更新软件运行时间"""
        current_time = time.time()
        elapsed_time = current_time - self.start_time

        # 将运行时间转换为时:分:秒格式
        hours = int(elapsed_time // 3600)
        minutes = int((elapsed_time % 3600) // 60)
        seconds = int(elapsed_time % 60)

        runtime_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        self.runtime_label.config(text=runtime_str)

        # 每秒更新一次
        self.root.after(1000, self.update_software_runtime)

    def start_barcode_scanner_communication(self):
        """启动条码扫描器通信"""
        try:
            # 初始化条码扫描器
            # 请根据实际情况修改设备路径和波特率
            self.bar_scanner = BarCodeScanner(
                port=SERIAL_COM_BARCODE_SCANNER,  # 条码扫描器设备路径
                baudrate=9600,  # 条码扫描器波特率
                timeout=1.0  # 超时时间
            )

            # 设置回调函数
            self.bar_scanner.set_callback(self.on_barcode_received)

            # 打开串口
            if self.bar_scanner.open():
                self.add_message("条码扫描器串口已连接")

                # 启动接收循环
                if self.bar_scanner.start_receive_loop():
                    self.add_message("条码扫描器接收线程已启动")
                else:
                    self.add_message("条码扫描器接收线程启动失败")
            else:
                self.add_message("条码扫描器串口连接失败")

        except Exception as e:
            self.add_message(f"启动条码扫描器失败: {e}")

    def on_barcode_received(self, barcode):
        """条码接收回调函数"""
        try:
            if not barcode:
                return
            print(barcode)
            # 在主线程中更新UI
            # self.root.after(0, lambda: self._handle_barcode_ui_update(barcode))

        except Exception as e:
            self.add_message(f"处理条码回调错误: {e}")

    def _handle_barcode_ui_update(self, barcode):
        """在主线程中处理条码UI更新"""
        try:
            # 1. 显示条码
            self.update_barcode_display(barcode)

            # 2. 添加到消息区域
            timestamp = time.strftime("%H:%M:%S", time.localtime())
            self.add_message(f"[{timestamp}] 条码: {barcode}")

            # 3. 可以根据业务需求处理条码
            # 例如：与RFID标签关联、更新数据库等
            # self.process_barcode_for_business(barcode)

        except Exception as e:
            self.add_message(f"更新条码UI错误: {e}")

    def update_barcode_display(self, barcode):
        """在UI中显示条码"""
        try:
            # 如果有专门的条码显示控件
            if hasattr(self, 'barcode_display_label'):
                self.barcode_display_label.config(text=f"条码: {barcode}")

            # 或者在现有的文本框中显示
            elif hasattr(self, 'fetch_text'):
                # 在fetch_text中追加显示
                current_text = self.fetch_text.get("1.0", "end-1c")
                if current_text:
                    new_text = f"{current_text}\n条码: {barcode}"
                else:
                    new_text = f"条码: {barcode}"

                self.update_element_text(self.fetch_text, new_text, clear_first=True)

        except Exception as e:
            print(f"更新条码显示错误: {e}")

    def get_barcode(self):
        """获取一个条码"""
        if hasattr(self, 'bar_scanner') and self.bar_scanner:
            return self.bar_scanner.get_barcode()
        return None

    def get_all_barcodes(self):
        """获取所有条码并清空队列"""
        if hasattr(self, 'bar_scanner') and self.bar_scanner:
            return self.bar_scanner.get_all_barcodes()
        return []

    def clear_barcode_cache(self):
        """清空条码缓存"""
        if hasattr(self, 'bar_scanner') and self.bar_scanner:
            with self.bar_scanner.lock:
                self.bar_scanner.barcode_queue.clear()

    def show_barcode_stats(self):
        """显示条码扫描器统计信息"""
        if hasattr(self, 'bar_scanner') and self.bar_scanner:
            stats = self.bar_scanner.get_stats()
            stats_text = f"""
                条码扫描器状态:
                  设备: {stats['port']}
                  波特率: {stats['baudrate']}
                  串口状态: {'已打开' if stats['is_open'] else '未打开'}
                  接收状态: {'运行中' if stats['is_running'] else '已停止'}
                  队列长度: {stats['queue_size']}
                """
            self.add_message(stats_text)

    def start_tcp_server(self):
        """在后台线程中启动 TCP Socket Server"""

        def run_server():
            try:
                self.tcp_server.start()
            except Exception as e:
                self.add_message(f"启动 TCP Server 失败: {e}")
        threading.Thread(target=run_server, daemon=True).start()

    def _parse_tcp_write_data(self, data: bytes):
        """从TCP收到的原始字节解析写入数据（不足20字节补0x00，超出截断）"""
        if len(data) < 20:
            return data + bytes(20 - len(data))
        elif len(data) > 20:
            return data[:20]
        return data

    # def on_tcp_message(self, data: bytes, addr):
    #     """
    #     收到 TCP 客户端消息时的回调
    #     :param data: 原始字节数据
    #     :param addr: 客户端地址 (ip, port)
    #     """
    #     print('on_tcp_message')
    #     # 将数据解码为字符串（假设客户端发送 UTF-8 文本）
    #     try:
    #         msg = data.decode('utf-8').strip()
    #         print(msg)
    #     except UnicodeDecodeError:
    #         msg = data.hex()
    #
    #     # 记录日志（通过 UI 的消息区域显示）
    #     self.add_message(f"TCP 客户端 [{addr[0]}:{addr[1]}] 发来: {msg}")
    #
    #     # 尝试解析 JSON 格式: {"type": "rfid", "data": [48, 50, ...]}
    #     try:
    #         json_data = json.loads(msg)
    #         if isinstance(json_data, dict) and json_data.get("type") == "rfid" and "data" in json_data:
    #             data_bytes = bytes(json_data["data"])
    #             write_data = self._parse_tcp_write_data(data_bytes)
    #             self.pending_write_data = write_data
    #             hex_str = ' '.join(f'{b:02X}' for b in write_data)
    #             self.add_message(f"收到上位机下发写入数据({len(write_data)}字节): {hex_str}")
    #             return
    #     except (json.JSONDecodeError, ValueError, TypeError):
    #         pass
    #
    #     # 可选：根据消息内容执行相应操作（如控制设备）
    #     # 注意：此回调在 TCP 子线程中运行，如需更新 UI 请使用 root.after
    #     # 示例：如果收到 "stop"，则执行紧急制动
    #     if msg.lower() == "stop":
    #         self.root.after(0, self.emergency_stop)
    #     elif msg.lower() == "start":
    #         self.root.after(0, lambda: self.toggle_production() if not self.is_running else None)
    #     elif msg.lower() == "status":
    #         # 回复当前状态
    #         status = f"运行中: {self.is_running}, 当前识别数量: {self.current_load}"
    #         self.tcp_server.send_to_all(status)
    #     else:
    #         # 尝试解析为标签写入数据
    #         write_data = self._parse_tcp_write_data(data)
    #         self.pending_write_data = write_data
    #         hex_str = ' '.join(f'{b:02X}' for b in write_data)
    #         self.add_message(f"收到上位机下发写入数据({len(write_data)}字节): {hex_str}")
    #     # 更多自定义命令可在此扩展

    def on_cmd_write_epc(self, epc_data: bytes):
        """TODO: 处理写EPC指令"""
        print(f"[on_cmd_write_epc] 收到EPC数据: {epc_data.hex().upper()} ({len(epc_data)}字节)")
        hex_str = ' '.join(f'{b:02X}' for b in epc_data)
        self.add_message(f"[TODO] 写EPC指令，数据({len(epc_data)}字节): {hex_str}")

    def on_cmd_write_user(self, user_data: bytes):
        """TODO: 处理写USER_DATA指令"""
        print(f"[on_cmd_write_user] 收到USER_DATA: {user_data.hex().upper()} ({len(user_data)}字节)")
        hex_str = ' '.join(f'{b:02X}' for b in user_data)
        self.add_message(f"[TODO] 写USER_DATA指令，数据({len(user_data)}字节): {hex_str}")

    def on_tcp_message(self, data: bytes, addr):
        """
        收到 TCP 客户端消息时的回调（新）
        支持指令格式:
          {"type": "write_epc",   "epc": [...]}
          {"type": "write_user",  "user_data": [...]}
        :param data: 原始字节数据
        :param addr: 客户端地址 (ip, port)
        """
        print('on_tcp_message')
        try:
            msg = data.decode('utf-8').strip()
            print(msg)
        except UnicodeDecodeError:
            print(f"TCP数据解码失败: {data.hex()}")
            return

        self.add_message(f"TCP 客户端 [{addr[0]}:{addr[1]}] 发来: {msg}")

        # 尝试解析 JSON
        try:
            json_data = json.loads(msg)
        except (json.JSONDecodeError, ValueError, TypeError):
            self.add_message(f"TCP 收到非JSON数据: {msg}")
            return

        if not isinstance(json_data, dict):
            return

        cmd_type = json_data.get("type", "")

        if cmd_type == "write_epc":
            epc_list = json_data.get("epc")
            if epc_list is None:
                self.add_message("write_epc指令缺少 'epc' 字段")
                return
            epc_data = bytes(epc_list)
            self.on_cmd_write_epc(epc_data)

        elif cmd_type == "write_user":
            user_list = json_data.get("user_data")
            if user_list is None:
                self.add_message("write_user指令缺少 'user_data' 字段")
                return
            user_data = bytes(user_list)
            self.on_cmd_write_user(user_data)

        else:
            self.add_message(f"TCP 收到未知指令类型: {cmd_type}")

    def start_rfid_reader_serial(self):
        """启动串口 RFID 读写器"""

        def connect():
            if self.rfid_reader_serial.open():
                self.add_message("串口 RFID 读写器连接成功")
                # 可选：设置数据接收回调
                self.rfid_reader_serial.set_callback(self.on_rfid_serial_data)
                # 如果需要自动接收，可以启动接收循环
                self.rfid_reader_serial.start_receive_loop()
                self.rfid_reader_serial.start_firmware()
                self.rfid_reader_serial.set_write_callback(self.on_rfid_write_result)
                # user_data = bytes([
                #     0x11, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                #     0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x11
                # ])
                # user_data = bytes([
                #     0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88, 0x99, 0x00,
                #     0xaa, 0xaa, 0xbb, 0xbb, 0xcc, 0xcc, 0xdd, 0xdd, 0xee, 0xee
                # ])
                # self.rfid_reader_serial.write_tag_with_userdata(user_data)
                # self.rfid_reader_serial.startloop()
            else:
                self.add_message("串口 RFID 读写器连接失败")

        threading.Thread(target=connect, daemon=True).start()

    def on_rfid_serial_data(self, data: bytes):
        """处理串口 RFID 读写器接收到的数据（支持多包连发）"""
        print(f"[RFID Serial] 收到原始数据 {len(data)} 字节: {data.hex()}")
        self.serial_rfid_buffer.extend(data)

        while True:
            tag, consumed = self._try_parse_one_packet(self.serial_rfid_buffer)
            if consumed > 0:
                # 移除已处理的数据（无论解析是否成功，都清掉已消费的字节）
                self.serial_rfid_buffer = self.serial_rfid_buffer[consumed:]
                if tag is not None:
                    # 在主线程中处理标签
                    self.root.after(0, lambda t=tag: self._add_serial_tag_to_history(t))
            else:
                # 无法继续解析，等待更多数据
                break

    def _try_parse_one_packet(self, buffer: bytearray):
        """
        通过查找特征头边界来提取一个完整包。
        返回 (RFIDTag, consumed_bytes)
        """
        NORMAL_HEADER = bytes([0xFF, 0x2B, 0xAA, 0x00, 0x00, 0x00, 0x96])
        header_len = len(NORMAL_HEADER)

        # 查找第一个特征头位置
        first_idx = -1
        for i in range(len(buffer) - header_len + 1):
            if buffer[i:i + header_len] == NORMAL_HEADER:
                first_idx = i
                break

        if first_idx == -1:
            # 没有找到正常包头，丢弃所有数据（防止缓冲区无限增长）
            consumed = len(buffer)
            print(f"[RFID Serial] 未找到正常包头，丢弃 {consumed} 字节")
            self.add_message(f"未找到正常包头，丢弃 {consumed} 字节")
            return None, consumed

        if first_idx > 0:
            # 跳过包头前的无效数据（异常包或残留数据）
            print(f"[RFID Serial] 跳过包头前无效数据 {first_idx} 字节")
            return None, first_idx

        # 查找第二个特征头位置（用于确定包结束）
        second_idx = -1
        for i in range(first_idx + header_len, len(buffer) - header_len + 1):
            if buffer[i:i + header_len] == NORMAL_HEADER:
                second_idx = i
                break

        if second_idx == -1:
            # 只有一个包，但数据可能不完整，等待更多数据
            return None, 0

        # 提取从 first_idx 到 second_idx 之间的数据作为一个完整包
        packet = bytes(buffer[first_idx:second_idx])
        tag = self._parse_single_serial_packet(packet)

        if tag.success:
            print(f"[RFID Serial] 解析成功: EPC={tag.epc}, RSSI={tag.rssi}dBm")
            # 消耗的字节数包括整个包（从first_idx到second_idx）
            return tag, second_idx
        else:
            print(f"[RFID Serial] 解析失败: {tag.error_message}，跳过当前包头")
            # 跳过当前包头（header_len 字节），继续尝试下一个包头
            return None, header_len

    def _parse_single_serial_packet(self, data: bytes) -> RFIDTag:
        """解析一个完整的数据包（协议格式）"""
        tag = RFIDTag()
        try:
            # 索引对照（0-based）：
            # 0-4: 固定头
            # 5-6: Flags
            # 7: RSSI
            # 8: 天线号
            # 9-12: 时间戳
            # 13-14: Tag Data Length
            # 15-34: User Data (20字节)
            # 35: EPC Length (包含附加数据)
            # 36-37: PC
            # 38开始: EPC 数据 (实际长度 = EPC Length - 4)

            rssi_byte = data[7]
            tag.rssi = rssi_byte if rssi_byte < 128 else rssi_byte - 256
            tag.antenna_num = data[8]

            # User Data (20字节)
            user_bytes = data[15:35]
            tag.user_data = ' '.join(f'{b:02X}' for b in user_bytes)

            # PC
            pc_bytes = data[36:38]
            tag.pc = ' '.join(f'{b:02X}' for b in pc_bytes)

            # EPC 长度（包含尾部附加数据）
            epc_len = data[35]
            real_epc_len = epc_len - 4
            if real_epc_len < 0:
                real_epc_len = 0

            if len(data) < 38 + real_epc_len:
                tag.success = False
                tag.error_message = f"数据长度不足，需要 {38 + real_epc_len} 字节，实际 {len(data)}"
                return tag

            epc_bytes = data[38:38 + real_epc_len]
            tag.epc = ''.join(f'{b:02X}' for b in epc_bytes)
            tag.tid = ""  # 本协议无 TID

            tag.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            tag._parse_product_info()
            tag.success = True
            return tag
        except Exception as e:
            tag.success = False
            tag.error_message = f"解析异常: {str(e)}"
            return tag

    def _add_serial_tag_to_history(self, tag: RFIDTag):
        """将串口 RFID 标签添加到历史记录（基于 EPC 去重，更新 UI）"""
        if not tag.success:
            self.add_message(f"标签无效: {tag.error_message}")
            return

        # 检查 EPC 是否已存在于历史记录中
        epc_exists = any(existing_tag.epc == tag.epc for existing_tag in self.tag_history)

        if not epc_exists:
            # 添加到历史记录
            self.tag_history.append(tag)
            # 限制历史记录大小
            if len(self.tag_history) > self.max_history_size:
                self.tag_history.pop(0)

            # 更新当前装载数量
            self.current_load = len(self.tag_history)
            self.current_load_label.config(text=str(self.current_load))

            # 在取标内容区域追加显示标签信息（可选）
            # display_text = self._format_tag_display(tag)
            # print(display_text)
            # self.update_element_text(self.fetch_text, display_text, clear_first=False)

            # 添加日志消息
            self.add_message(f"串口RFID读取到新标签: {tag.product_name} (EPC: {tag.epc}, RSSI: {tag.rssi:.1f}dBm)")
        else:
            # 写入完成后读回的标签，EPC相同但USER_DATA已更新，覆盖旧数据
            if self.write_done:
                for existing_tag in self.tag_history:
                    if existing_tag.epc == tag.epc:
                        existing_tag.user_data = tag.user_data
                        self.add_message(f"串口RFID更新已写入标签数据，EPC: {tag.epc}")
                        break
            else:
                self.add_message(f"串口RFID检测到重复标签，EPC: {tag.epc} 已存在")

    def _execute_fixed_write(self):
        """同步执行写标签，优先使用TCP下发的数据，写成功后启动验证读取（在状态机线程中调用）"""
        self.write_in_progress = True

        # 优先使用TCP下发的数据，否则使用固定默认数据
        write_data = self.pending_write_data if self.pending_write_data else self.FIXED_USER_DATA
        self.actual_write_data = write_data  # 记录实际写入的数据，用于后续校验
        data_hex = ' '.join(f'{b:02X}' for b in write_data)
        source = "TCP下发" if self.pending_write_data else "默认"
        self.add_message(f"开始写入标签内容({source}): {data_hex}")

        success = self.rfid_reader_serial.write_tag_with_userdata(write_data)
        if success:
            self.write_done = True
            self.write_in_progress = False
            self.add_message("写标签成功，启动验证读取...")
            self.rfid_reader_serial.startloop()
            return True
        else:
            self.add_message("写标签失败，重试中...")
            success = self.rfid_reader_serial.write_tag_with_userdata(write_data)
            if success:
                self.write_done = True
                self.write_in_progress = False
                self.add_message("重试写标签成功，启动验证读取...")
                self.rfid_reader_serial.startloop()
                return True
            else:
                self.write_done = False
                self.write_in_progress = False
                self.add_message("写标签失败（已重试），读取原始标签...")
                self.rfid_reader_serial.startloop()
                return False

    def on_rfid_write_result(self, success: bool):
        """写标签结果回调（不修改灯状态，避免与状态机灯光逻辑冲突）"""
        if success:
            self.add_message("写标签结果: 成功")
        else:
            self.add_message("写标签结果: 失败")

def main():
    root = tk.Tk()
    app = RFIDProductionSystem(root)

    # 设置关闭窗口事件
    root.protocol("WM_DELETE_WINDOW", app.on_closing)

    root.mainloop()


if __name__ == "__main__":
    main()