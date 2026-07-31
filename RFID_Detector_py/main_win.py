# main_win.py
# tkinter 界面 + 完整业务逻辑（与main.py相同）
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import time
import threading
import json
import urllib.request
from datetime import datetime

from rfid_tag import RFIDTag
from mqtt_client import MqttClient
from serial_comm import SerialComm
from barcode_scanner import BarCodeScanner
from TcpSocketServer import TcpSocketServer
from RFIDReader_SFM2200 import RFIDReader_SFM2200
from product_info_def import (get_product_name, get_manufacturer_name,
                               get_license_number, get_package_name)

DATA_TYPE_INBOUND = "inbound"
DATA_TYPE_OUTBOUND = "outbound"
SERIAL_COM_IO = "/dev/tty.usbserial-14240"
SERIAL_COM_RFID_READER = "/dev/tty.usbserial-1410"
SERIAL_COM_BARCODE_SCANNER = "/dev/tty.usbserial-14210"
REPORT_USE_MQTT = False
REPORT_TO_SERVER = True
API_BASE_URL = "http://127.0.0.1:8000"

ENTRY_WIDTH = 18
LABEL_WIDTH = 12


class MainWindow:
    """主窗口 — UI + 全部业务逻辑"""

    def __init__(self, root=None):
        if root is None:
            self.root = tk.Tk()
            self._owns_root = True
        else:
            self.root = root
            self._owns_root = False

        self.root.title("北斗+RFID系统集成设备")
        self.root.geometry("1000x800")
        self.root.configure(bg='white')
        self.c = {'bg': 'white', 'fg': '#2c3e50', 'accent': '#4CAF50'}

        # ========== 业务变量 ==========
        self.serial_rfid_buffer = bytearray()
        self.is_running = False
        self.current_load = 0
        self.inbound_total = 0
        self.outbound_total = 0
        self.start_time = time.time()
        self.direction = 0
        self.current_status = 0
        self.red_light = 0x00
        self.yellow_light = 0x02
        self.green_light = 0x04
        self.beep_ctrl = 0x06
        self.FIXED_DEFAULT_DATA = bytes([
            0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88, 0x99, 0x00,
            0xAA, 0xAA, 0xBB, 0xBB, 0xCC, 0xCC, 0xDD, 0xDD, 0xEE, 0xEE
        ])
        self.pending_write_data = None
        self.actual_write_data = None
        self.write_done = False
        self.write_in_progress = False
        self.b_write_epc = False
        self.current_tag = None
        self.tag_history = []
        self.max_history_size = 10000
        self.device_id = "RFID-DETECTOR-001"
        self.current_tid = ""
        self.bar_scanner = None
        self.barcode_reported = False

        # 后端服务
        self.mqtt_client = MqttClient(broker='192.168.3.83', port=1883,
                                       username='None', password='None', client_id=self.device_id)
        self.serial_comm = SerialComm(SERIAL_COM_IO, 9600)
        self.serial_reading_active = False
        self.rfid_reader_serial = RFIDReader_SFM2200(port=SERIAL_COM_RFID_READER, baudrate=115200, timeout=1.0)

        # ===== 构建UI =====
        self._build_ui()
        self.update_runtime_display()
        self.auto_connect()
        self.tcp_server = TcpSocketServer(host='0.0.0.0', port=3000)
        self.tcp_server.register_callback(self.on_tcp_message)
        self.start_tcp_server()

    # ===================================================================
    #  UI 构建（全部）
    # ===================================================================
    def _build_ui(self):
        title_frame = tk.Frame(self.root, bg='white')
        title_frame.pack(fill='x', padx=15, pady=(15, 5))
        tk.Label(title_frame, text="北斗+RFID系统集成设备",
                 font=("Microsoft YaHei", 16, "bold"),
                 bg='white', fg='#2c3e50').pack()

        main = tk.Frame(self.root, bg='white')
        main.pack(fill='both', expand=True, padx=15, pady=5)
        main.columnconfigure(0, weight=1, uniform='col')
        main.columnconfigure(1, weight=1, uniform='col')
        main.rowconfigure(0, weight=1)

        left_col = tk.Frame(main, bg='white')
        left_col.grid(row=0, column=0, sticky='nsew', padx=(0, 8))
        right_col = tk.Frame(main, bg='white')
        right_col.grid(row=0, column=1, sticky='nsew', padx=(8, 0))

        self._build_production_group(left_col)
        # 弹性空白，将集成设备信息推至底部
        tk.Frame(left_col, bg='white', height=1).pack(fill='both', expand=True)
        self._build_device_info_group(left_col)

        self._build_beidou_group(right_col)
        self._build_rfid_group(right_col)
        self._build_debug_group(right_col)

    def _labelframe(self, parent, text):
        return tk.LabelFrame(parent, text=f" {text} ", font=("Microsoft YaHei", 11, "bold"),
                             bg='white', fg='#2c3e50', relief='ridge', bd=2, labelanchor='n')

    def _entry(self, parent, readonly=False, **kw):
        e = tk.Entry(parent, font=("Microsoft YaHei", 10), relief='solid', bd=1,
                     bg='white', highlightthickness=0, width=ENTRY_WIDTH, **kw)
        if readonly:
            e.configure(state='readonly', readonlybackground='#f0f0f0')
        return e

    def _label(self, parent, text):
        return tk.Label(parent, text=text, font=("Microsoft YaHei", 10),
                        bg='white', fg=self.c['fg'], anchor='w', width=LABEL_WIDTH)

    def _label_value(self, parent, text, fg=None):
        return tk.Label(parent, text=text, font=("Microsoft YaHei", 10, "bold"),
                        bg='white', fg=fg or self.c['accent'], anchor='w')

    def _grid_row_full(self, frame, row, label, attr, readonly=False):
        self._label(frame, label).grid(row=row, column=0, sticky='e', padx=(10, 3), pady=4)
        e = self._entry(frame, readonly=readonly)
        e.grid(row=row, column=1, sticky='ew', padx=(0, 10), pady=4)
        setattr(self, attr, e)

    def _build_production_group(self, parent):
        frame = self._labelframe(parent, "生产线信息")
        frame.pack(fill='x', pady=(0, 10))
        frame.columnconfigure(0, weight=0)
        frame.columnconfigure(1, weight=1)

        fields = [
            ("产品种类：", 'product_type'),
            ("生产企业：", 'manufacturer_edit'),
            ("生产许可证编号：", 'license_number'),
            ("规格型号：", 'type_box'),
            ("净质量：", 'weight_box'),
            ("生产日期：", 'production_date'),
            ("生产批号：", 'batch_number'),
            ("生产袋/箱号：", 'package_number'),
            ("生产线信息代码：", 'production_line_code'),
        ]
        for i, f in enumerate(fields):
            label, attr = f[0], f[1]
            self._grid_row_full(frame, i, label, attr, readonly=True)

        ri = len(fields)
        pkg_frame = self._labelframe(frame, "包装方式")
        pkg_frame.grid(row=ri, column=0, columnspan=2, sticky='ew', padx=10, pady=4)
        pkg_inner = tk.Frame(pkg_frame, bg='white')
        pkg_inner.pack(fill='x', padx=10, pady=4)
        pkg_inner.columnconfigure(0, weight=1)
        pkg_inner.columnconfigure(1, weight=1)
        self.pkg_var = tk.StringVar(value="bag")
        tk.Radiobutton(pkg_inner, text="箱  装", variable=self.pkg_var, value="box",
                       font=("Microsoft YaHei", 10), bg='white').grid(row=0, column=0, padx=10)
        tk.Radiobutton(pkg_inner, text="袋  装", variable=self.pkg_var, value="bag",
                       font=("Microsoft YaHei", 10), bg='white').grid(row=0, column=1, padx=10)

        ri += 1
        state_frame = self._labelframe(frame, "生产状态")
        state_frame.grid(row=ri, column=0, columnspan=2, sticky='ew', padx=10, pady=4)
        state_inner = tk.Frame(state_frame, bg='white')
        state_inner.pack(fill='x', padx=10, pady=4)
        state_inner.columnconfigure(0, weight=1)
        state_inner.columnconfigure(1, weight=1)
        self.state_var = tk.StringVar(value="idle")
        tk.Radiobutton(state_inner, text="产 品 进 入", variable=self.state_var, value="cargo_in",
                       font=("Microsoft YaHei", 10), bg='white', state='disabled').grid(row=0, column=0, padx=10)
        tk.Radiobutton(state_inner, text="产 品 通 过", variable=self.state_var, value="cargo_out",
                       font=("Microsoft YaHei", 10), bg='white', state='disabled').grid(row=0, column=1, padx=10)

        self.production_date.insert(0, datetime.now().strftime("%Y%m%d"))

    def _build_device_info_group(self, parent):
        frame = self._labelframe(parent, "集成设备信息")
        frame.pack(fill='x', pady=(0, 10))
        frame.columnconfigure(0, weight=0)
        frame.columnconfigure(1, weight=1)

        rows = [
            ("条形码：", 'barcode_edit'),
            ("待写入代码：", 'pending_code_edit'),
            ("TID：", 'tid_edit'),
            ("EPC：", 'epc_edit'),
        ]
        for i, (label, attr) in enumerate(rows):
            self._label(frame, label).grid(row=i, column=0, sticky='e', padx=(10, 3), pady=4)
            e = self._entry(frame, readonly=True)
            e.grid(row=i, column=1, sticky='ew', padx=(0, 10), pady=4)
            setattr(self, attr, e)

        val_rows = [
            ("产线运行时间：", "00时00分", 'runtime_label'),
            ("当前识别数量：", "0", 'current_load_label'),
            ("识别总量：", "0", 'total_label'),
        ]
        for i, (label, val, attr) in enumerate(val_rows):
            r = i + len(rows)
            self._label(frame, label).grid(row=r, column=0, sticky='e', padx=(10, 3), pady=4)
            lb = self._label_value(frame, val)
            lb.grid(row=r, column=1, sticky='w', padx=(0, 10), pady=4)
            setattr(self, attr, lb)

    def _build_beidou_group(self, parent):
        frame = self._labelframe(parent, "北斗信息")
        frame.pack(fill='x', pady=(0, 10))
        frame.columnconfigure(0, weight=0)
        frame.columnconfigure(1, weight=1)
        for i, (label, attr) in enumerate([("北斗ID：", 'beidou_id'), ("当前北斗时间：", 'beidou_time'), ("北斗位置：", 'beidou_location')]):
            self._label(frame, label).grid(row=i, column=0, sticky='e', padx=(10, 3), pady=4)
            e = self._entry(frame, readonly=True)
            e.grid(row=i, column=1, sticky='ew', padx=(0, 10), pady=4)
            setattr(self, attr, e)

    def _build_rfid_group(self, parent):
        frame = self._labelframe(parent, "RFID控制")
        frame.pack(fill='x', pady=(0, 10))
        frame.columnconfigure(0, weight=0)
        frame.columnconfigure(1, weight=1)
        for i, (label, attr) in enumerate([("天线号：", 'antenna_edit'), ("读功率(dBm)：", 'read_power_edit'), ("写功率(dBm)：", 'write_power_edit'), ("频点：", 'frequency_edit')]):
            self._label(frame, label).grid(row=i, column=0, sticky='e', padx=(10, 3), pady=4)
            e = self._entry(frame)
            e.grid(row=i, column=1, sticky='ew', padx=(0, 10), pady=4)
            setattr(self, attr, e)
        btn_outer = self._labelframe(frame, "控制按钮")
        btn_outer.grid(row=4, column=0, columnspan=2, sticky='ew', padx=10, pady=4)
        btn_frame = tk.Frame(btn_outer, bg='white')
        btn_frame.pack(fill='x', padx=10, pady=4)
        style = ttk.Style()
        style.theme_use('clam')  # clam主题支持按钮背景色
        for color, name in [('#4CAF50', 'GreenBtn'), ('#FF9800', 'OrangeBtn'), ('#F44336', 'RedBtn')]:
            style.configure(f'{name}.TButton', background=color, foreground='white',
                            font=("Microsoft YaHei", 9, "bold"), borderwidth=0, relief='flat')
            style.map(f'{name}.TButton', background=[('active', color), ('!active', color)])
        for i in range(3):
            btn_frame.columnconfigure(i, weight=1)
        self.read_params_btn = ttk.Button(btn_frame, text='读取参数', style='GreenBtn.TButton',
                                           command=self.on_read_rfid_params)
        self.read_params_btn.grid(row=0, column=0, padx=5, sticky='ew')
        self.set_params_btn = ttk.Button(btn_frame, text='设置参数', style='OrangeBtn.TButton',
                                          command=self.on_set_rfid_params)
        self.set_params_btn.grid(row=0, column=1, padx=5, sticky='ew')
        self.reset_rfid_btn = ttk.Button(btn_frame, text='重启RFID', style='RedBtn.TButton',
                                          command=self.on_reset_rfid)
        self.reset_rfid_btn.grid(row=0, column=2, padx=5, sticky='ew')

    def on_read_rfid_params(self):
        """读取RFID参数"""
        self.log("读取RFID参数", "INFO")
        # 查询使能天线
        enabled = self.rfid_reader_serial.check_enabled_antenna()
        if enabled:
            antenna_text = ', '.join(enabled)
            self.antenna_edit.delete(0, 'end')
            self.antenna_edit.insert(0, antenna_text)
            self.log(f"使能天线: {antenna_text}", "INFO")
        else:
            self.log("未检测到使能天线", "WARN")
            return

        # 查询天线功率
        powers = self.rfid_reader_serial.get_antenna_power()
        if powers:
            read_pwrs = []
            write_pwrs = []
            for ant in enabled:
                if ant in powers:
                    read_pwrs.append(str(powers[ant]['read']))
                    write_pwrs.append(str(powers[ant]['write']))
            self.read_power_edit.delete(0, 'end')
            self.read_power_edit.insert(0, ', '.join(read_pwrs))
            self.write_power_edit.delete(0, 'end')
            self.write_power_edit.insert(0, ', '.join(write_pwrs))
            self.log(f"读功率: {', '.join(read_pwrs)} 写功率: {', '.join(write_pwrs)}", "INFO")

    def on_set_rfid_params(self):
        """设置RFID参数"""
        params = self.get_rfid_params()
        self.log(f"设置RFID参数: 天线={params['antenna']} 读功率={params['read_power']} 写功率={params['write_power']} 频点={params['frequency']}", "INFO")

        # 解析天线列表和功率值
        ants = [a.strip() for a in params['antenna'].split(',') if a.strip()]
        read_pwrs = [int(p.strip()) for p in params['read_power'].split(',') if p.strip() and p.strip().isdigit()]
        write_pwrs = [int(p.strip()) for p in params['write_power'].split(',') if p.strip() and p.strip().isdigit()]

        if ants and read_pwrs and write_pwrs:
            success = self.rfid_reader_serial.set_antenna_power(ants, read_pwrs, write_pwrs)
            self.log(f"天线功率设置{'成功' if success else '失败'}", "INFO" if success else "ERROR")

    def on_reset_rfid(self):
        """重启RFID"""
        self.log("重启RFID设备", "WARN")

    def _build_debug_group(self, parent):
        frame = self._labelframe(parent, "调试信息")
        frame.pack(fill='both', expand=True)
        self.debug_text = tk.Text(frame, font=("Consolas", 9), relief='solid', bd=1, bg='white', wrap='word', highlightthickness=0)
        self.debug_text.pack(fill='both', expand=True, padx=5, pady=5)
        self.debug_text.configure(state='disabled')
        for t in ["ERROR", "WARN", "INFO", "DEBUG"]:
            self.debug_text.tag_config(t, foreground={"ERROR": "#f44336", "WARN": "#ff9800", "INFO": "#4CAF50", "DEBUG": "#2196F3"}[t])
        self.debug_text.tag_config("msg", foreground="#000000")

    # ===================================================================
    #  UI 辅助
    # ===================================================================
    def _set_entry(self, attr, text):
        e = getattr(self, attr, None)
        if e:
            e.configure(state='normal')
            e.delete(0, 'end')
            e.insert(0, str(text))
            e.configure(state='readonly')

    def _set_editable_entry(self, attr, text):
        e = getattr(self, attr, None)
        if e:
            e.configure(state='normal')
            e.delete(0, 'end')
            e.insert(0, str(text))
            e.configure(state='readonly')

    def add_message(self, msg: str): self.log(msg, "INFO")
    def log(self, message: str, level: str = "INFO"):
        ts = time.strftime("%H:%M:%S")
        self.debug_text.configure(state='normal')
        self.debug_text.insert('end', f"[{ts}] [{level}] ", (level,))
        self.debug_text.insert('end', f"{message}\n", ("msg",))
        self.debug_text.see('end')
        self.debug_text.configure(state='disabled')
        if int(self.debug_text.index('end-1c').split('.')[0]) > 500:
            self.debug_text.delete('1.0', '100.0')

    def update_runtime_display(self):
        elapsed = int(time.time() - self.start_time)
        h, rem = divmod(elapsed, 3600)
        m, s = divmod(rem, 60)
        self.runtime_label.configure(text=f"{h:02d}时{m:02d}分{s:02d}秒")
        self.root.after(1000, self.update_runtime_display)

    def update_barcode(self, text): self._set_entry('barcode_edit', text)
    def update_tid(self, text): self._set_entry('tid_edit', text.replace(' ', ''))
    def update_epc(self, text): self._set_entry('epc_edit', text.replace(' ', ''))
    def update_pending_code(self, text): self._set_entry('pending_code_edit', text.replace(' ', ''))
    def get_rfid_params(self):
        return {'antenna': self.antenna_edit.get(),
                'read_power': self.read_power_edit.get(),
                'write_power': self.write_power_edit.get(),
                'frequency': self.frequency_edit.get()}

    # ===================================================================
    #  parse_product_info 预留
    # ===================================================================
    def parse_product_info(self, data: bytes):
        """解析20字节编码数据并填写生产线信息"""
        self.log(f"parse_product_info 收到数据 ({len(data)}字节): {data.hex().upper()}", "DEBUG")
        if len(data) < 20:
            self.log(f"parse_product_info 数据长度不足: {len(data)}", "WARN")
            return

        # 编码规则（0-based，共20字节）：
        # 0:     0x00 (字对齐填充)
        # 1-3:   产品种类代码 ASCII (3字节)
        # 4-5:   生产企业代码 ASCII (2字节)
        # 6-7:   生产许可证编号 hex (2字节)
        # 8-9:   规格型号 hex (2字节)
        # 10:    包装方式 ASCII (1字节)
        # 11-12: 净质量 hex (2字节)
        # 13:    生产日期-年 hex
        # 14:    生产日期-月 hex
        # 15:    生产日期-日 hex
        # 16-17: 生产批号 hex (2字节)
        # 18-19: 袋/箱号 hex (2字节)

        # 产品种类代码 (bytes 1-3, ASCII)
        product_bytes = data[1:4]
        product_code = product_bytes.decode('ascii', errors='replace')
        self.log(f"  产品种类: {product_bytes.hex().upper()} -> '{product_code}'", "DEBUG")
        product_name = get_product_name(product_code)
        self._set_editable_entry('product_type', product_name)

        # 生产企业代码 (bytes 4-5, ASCII)
        manu_bytes = data[4:6]
        manu_code = manu_bytes.decode('ascii', errors='replace')
        self.log(f"  生产企业: {manu_bytes.hex().upper()} -> '{manu_code}'", "DEBUG")
        manu_name = get_manufacturer_name(manu_code)
        self._set_editable_entry('manufacturer_edit', manu_name)

        # 生产许可证编号 (bytes 6-7, big-endian)
        license_num = int.from_bytes(data[6:8], 'big')
        self.log(f"  许可证号: {data[6:8].hex().upper()} -> {license_num:04d}", "DEBUG")
        self._set_editable_entry('license_number', f"{license_num:04d}")

        # 规格型号 (bytes 8-9, big-endian)
        spec_val = int.from_bytes(data[8:10], 'big')
        self.log(f"  规格型号: {data[8:10].hex().upper()} -> {spec_val}", "DEBUG")
        self._set_editable_entry('type_box', f"{spec_val}")

        # 包装方式 (byte 10, ASCII)
        pkg_byte = data[10]
        pkg_char = chr(pkg_byte) if 0x20 <= pkg_byte < 0x7F else '?'
        self.log(f"  包装方式: {pkg_byte:02X} -> '{pkg_char}'", "DEBUG")
        pkg_name = get_package_name(pkg_byte)
        if pkg_name == "袋装":
            self.pkg_var.set("bag")
        else:
            self.pkg_var.set("box")

        # 净质量 (bytes 11-12, big-endian)
        weight_val = int.from_bytes(data[11:13], 'big')
        self.log(f"  净质量: {data[11:13].hex().upper()} -> {weight_val}", "DEBUG")
        self._set_editable_entry('weight_box', f"{weight_val}")

        # 生产日期 (bytes 13-15: yy, mm, dd)
        yy = data[13]
        mm = data[14]
        dd = data[15]
        self.log(f"  生产日期: {yy:02X} {mm:02X} {dd:02X} -> 20{yy:02d}-{mm:02d}-{dd:02d}", "DEBUG")
        self._set_editable_entry('production_date', f"{yy:02d}{mm:02d}{dd:02d}")

        # 生产批号 (bytes 16-17, big-endian)
        batch_val = int.from_bytes(data[16:18], 'big')
        self.log(f"  生产批号: {data[16:18].hex().upper()} -> {batch_val:04d}", "DEBUG")
        self._set_editable_entry('batch_number', f"{batch_val:04d}")

        # 生产袋/箱号 (bytes 18-19, big-endian)
        box_val = int.from_bytes(data[18:20], 'big')
        self.log(f"  袋/箱号: {data[18:20].hex().upper()} -> {box_val:04d}", "DEBUG")
        self._set_editable_entry('package_number', f"{box_val:04d}")

        # 信息代码
        self._set_editable_entry('production_line_code', data.hex().upper())

        self.log(f"产品信息已解析: 产品={product_name}, 企业={manu_name}, 日期=20{yy:02d}-{mm:02d}-{dd:02d}", "INFO")

    # ===================================================================
    #  网络 / MQTT / 串口 启动
    # ===================================================================
    def start_tcp_server(self):
        """启动TCP Socket Server"""
        def run_server():
            try:
                self.tcp_server.start()
            except Exception as e:
                self.log(f"启动 TCP Server 失败: {e}", "ERROR")
        threading.Thread(target=run_server, daemon=True).start()

    def auto_connect(self):
        """自动连接RFID读写器和MQTT客户端（分别启动）"""
        self.add_message("系统启动，准备连接RFID读写器和MQTT客户端...")

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
        threading.Thread(target=connect_mqtt_thread, daemon=True).start()
        threading.Thread(target=connect_serial_thread, daemon=True).start()

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
                self.log(f"MQTT客户端启动失败: {e}", "ERROR")
        threading.Thread(target=connect_thread, daemon=True).start()

    def start_serial_communication(self):
        """启动串口通信（在UI线程中安全调用）"""
        def connect_serial():
            if self.setup_serial_communication():
                self.add_message("串口通信启动成功")
            else:
                self.log("串口通信启动失败，请检查串口连接", "ERROR")
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
                self.log("串口连接失败", "ERROR")
                return False
        except Exception as e:
            self.log(f"串口连接异常: {e}", "ERROR")
            return False

    def start_barcode_scanner_communication(self):
        """启动条码扫描器通信"""
        try:
            self.bar_scanner = BarCodeScanner(
                port=SERIAL_COM_BARCODE_SCANNER,
                baudrate=9600,
                timeout=1.0
            )
            self.bar_scanner.set_callback(self.on_barcode_received)
            if self.bar_scanner.open():
                self.add_message("条码扫描器串口已连接")
                if self.bar_scanner.start_receive_loop():
                    self.add_message("条码扫描器接收线程已启动")
                else:
                    self.log("条码扫描器接收线程启动失败", "ERROR")
            else:
                self.log("条码扫描器串口连接失败", "ERROR")
        except Exception as e:
            self.log(f"启动条码扫描器失败: {e}", "ERROR")

    def start_rfid_reader_serial(self):
        """启动串口 RFID 读写器"""
        def connect():
            if self.rfid_reader_serial.open():
                self.add_message("串口 RFID 读写器连接成功")
                self.rfid_reader_serial.set_callback(self.on_rfid_serial_data)
                self.rfid_reader_serial.start_receive_loop()
                self.rfid_reader_serial.start_firmware()
                self.rfid_reader_serial.set_write_callback(self.on_rfid_write_result)
                # user_data = bytes([
                #     0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88, 0x99, 0x00,
                #     0xaa, 0xaa, 0xbb, 0xbb, 0xcc, 0xcc, 0xdd, 0xdd, 0xee, 0xee
                # ])
                # self.rfid_reader_serial.write_tag_with_epcdata(user_data)
                # self.rfid_reader_serial.startloop_tid_user()
            else:
                self.log("串口 RFID 读写器连接失败", "ERROR")
        threading.Thread(target=connect, daemon=True).start()

    # ===================================================================
    #  状态机
    # ===================================================================
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
                                                self._send_tcp_cargo_in_message()

                                                # 新增：清空条码缓存，开始收集入库条码
                                                self.clear_barcode_cache()

                                                # # 货物进入通道，执行写标签（覆盖Path1和Path2）
                                                # if not self.write_done and not self.write_in_progress:
                                                #     self._execute_fixed_write()

                                            elif current_status == 0x02:  # 光栅2遮挡
                                                current_state = STATE_OUTBOUND_START
                                                self.direction = 2
                                                self.start_rfid_loop_query(True)
                                                process_start_time = time.time()
                                                print("出库开始：光栅2遮挡")
                                                self._send_tcp_cargo_in_message()

                                                # 新增：清空条码缓存，开始收集出库条码
                                                self.clear_barcode_cache()

                                                # # 货物进入通道，执行写标签（覆盖Path1和Path2）
                                                # if not self.write_done and not self.write_in_progress:
                                                #     self._execute_fixed_write()

                                        elif current_state == STATE_INBOUND_START:
                                            if current_status == 0x03:  # 光栅1+2同时遮挡
                                                current_state = STATE_INBOUND_MIDDLE
                                                print("入库中间：光栅1+2同时遮挡")
                                                # if not self.write_done and not self.write_in_progress:
                                                #     self._execute_fixed_write()
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
                                                        # self._send_tcp_pass_message()
                                                        self.report_rfid_tags_via_tcp()
                                                        self._send_tcp_cargo_out_message()
                                                        self.report_rfid_tags_to_server(DATA_TYPE_INBOUND,
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
                                                    # self._send_tcp_pass_message()
                                                    self.report_rfid_tags_via_tcp()
                                                    self._send_tcp_cargo_out_message()
                                                    self.report_rfid_tags_to_server(DATA_TYPE_INBOUND,
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
                                                # if not self.write_done and not self.write_in_progress:
                                                #     self._execute_fixed_write()
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
                                                        # self._send_tcp_pass_message()
                                                        self.report_rfid_tags_via_tcp()
                                                        self._send_tcp_cargo_out_message()
                                                        self.report_rfid_tags_to_server(DATA_TYPE_OUTBOUND,
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
                                                    # self._send_tcp_pass_message()
                                                    self.report_rfid_tags_via_tcp()
                                                    self._send_tcp_cargo_out_message()
                                                    self.report_rfid_tags_to_server(DATA_TYPE_OUTBOUND,
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
                    self.log(f"串口读取错误: {e}", "ERROR")
                    time.sleep(0.5)

        threading.Thread(target=read_loop, daemon=True).start()
        self.add_message("串口读取循环已启动（带状态确认机制，支持不同确认标准）")

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

    def _finish(self, data_type, current_state, process_start_time, last_report_time, report_cooldown):
        self.start_rfid_loop_query(False)
        self._send_tcp_cargo_out_message()
        barcodes = self.get_all_barcodes()
        self.report_rfid_tags_via_tcp()
        self.report_rfid_tags_to_server(data_type, barcodes=barcodes)
        # 完成后显示最后标签的TID/EPC
        if self.tag_history:
            last = self.tag_history[-1]
            self.root.after(0, lambda: self._show_last_tag(last))

    def _abort(self):
        self._send_tcp_cargo_out_message()
        self.start_rfid_loop_query(False)
        self.tag_history.clear()
        self.clear_barcode_cache()

    def _show_last_tag(self, tag):
        self.update_tid(tag.tid)
        self.update_epc(tag.epc)
        self.current_load_label.configure(text="0")
        self.total_label.configure(text=str(self.inbound_total + self.outbound_total))

    # ===================================================================
    #  RFID数据解析
    # ===================================================================
    def handle_serial_data(self, data):
        """处理串口接收到的数据"""
        def update_ui():
            try:
                hex_data = ' '.join([f'{b:02X}' for b in data])
                self.parse_serial_data(data)
            except Exception as e:
                self.log(f"处理串口数据错误: {e}", "ERROR")
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
            self.log(f"解析串口数据错误: {e}", "ERROR")

    def handle_register_response(self, data):
        """处理寄存器响应数据"""
        try:
            if len(data) >= 6:
                register_value = (data[3] << 8) | data[4]
                self.add_message(f"寄存器值: {register_value}")
        except Exception as e:
            self.log(f"处理寄存器响应错误: {e}", "ERROR")

    def on_rfid_serial_data(self, data: bytes):
        self.serial_rfid_buffer.extend(data)
        while True:
            tag, consumed = self._try_parse_one_packet_tid_user(self.serial_rfid_buffer)
            if consumed > 0:
                self.serial_rfid_buffer = self.serial_rfid_buffer[consumed:]
                if tag: self.root.after(0, lambda t=tag: self._add_serial_tag_to_history(t))
            else: break

    def _try_parse_one_packet_tid_user(self, buffer: bytearray):
        """
        通过查找 FF 47 AA 特征头边界来提取一个完整包（TID+USER格式）。
        处理正常包（FF 47 AA）和异常包（FF XX AA, XX≠47）混合的情况。
        返回 (RFIDTag, consumed_bytes)
        """
        TID_USER_HEADER = bytes([0xFF, 0x47, 0xAA])
        header_len = len(TID_USER_HEADER)

        # 查找第一个有效包头位置（FF 47 AA）
        first_idx = -1
        for i in range(len(buffer) - header_len + 1):
            if buffer[i] == 0xFF and buffer[i + 2] == 0xAA:
                if buffer[i + 1] == 0x47:
                    first_idx = i
                    break
                else:
                    # 异常包（FF XX AA, XX≠47），跳过前3字节继续搜索
                    pass

        if first_idx == -1:
            # 检查缓冲区中是否有任何 FF xx AA 开头的数据
            has_any = False
            for i in range(len(buffer) - 2):
                if buffer[i] == 0xFF and buffer[i + 2] == 0xAA:
                    # 找到异常包头，跳过前3字节
                    print(f"[RFID Serial TID] 跳过异常包头 FF {buffer[i+1]:02X} AA，丢弃3字节")
                    return None, i + 3
                    # has_any = True — actually, we break above
            # 没有找到任何 FF xx AA，丢弃所有数据
            consumed = len(buffer)
            print(f"[RFID Serial TID] 未找到有效包头，丢弃 {consumed} 字节")
            return None, consumed

        if first_idx > 0:
            # 跳过包头前的无效数据（异常包或残留数据）
            print(f"[RFID Serial TID] 跳过包头前无效数据 {first_idx} 字节")
            return None, first_idx

        # 查找第二个有效包头位置（用于确定包结束）
        second_idx = -1
        for i in range(first_idx + header_len, len(buffer) - header_len + 1):
            if buffer[i] == 0xFF and buffer[i + 2] == 0xAA and buffer[i + 1] == 0x47:
                second_idx = i
                break

        if second_idx == -1:
            # 只有一个包，但数据可能不完整，等待更多数据
            return None, 0

        # 提取从 first_idx 到 second_idx 之间的数据作为一个完整包
        packet = bytes(buffer[first_idx:second_idx])
        tag = self._parse_single_serial_packet_tid_user(packet)

        if tag.success:
            print(f"[RFID Serial TID] 解析成功: TID={tag.tid}, EPC={tag.epc}, USER_DATA={tag.user_data}")
            return tag, second_idx
        else:
            print(f"[RFID Serial TID] 解析失败: {tag.error_message}，跳过当前包头")
            return None, header_len

    def _parse_single_serial_packet_tid_user(self, data: bytes) -> RFIDTag:
        """解析一个完整的 TID+USER 格式数据包"""
        tag = RFIDTag()
        try:
            # 协议格式（0-based索引）：
            # 0-2:   固定头 FF 47 AA
            # 15-34:  TID 数据 (20字节)
            # 31-50:  USER_DATA 数据 (20字节)
            # 54-73:  EPC 数据 (20字节)

            if len(data) < 74:
                tag.success = False
                tag.error_message = f"数据长度不足，需要至少74字节，实际 {len(data)}"
                return tag

            # TID (20字节)
            tid_bytes = data[15:31]
            tag.tid = ''.join(f'{b:02X}' for b in tid_bytes)

            # USER_DATA (20字节)
            user_bytes = data[31:51]
            tag.user_data = ''.join(f'{b:02X}' for b in user_bytes)

            # EPC (20字节)
            epc_bytes = data[54:74]
            tag.epc = ''.join(f'{b:02X}' for b in epc_bytes)

            # RSSI (尝试从data[7]读取)
            rssi_byte = data[7]
            tag.rssi = rssi_byte if rssi_byte < 128 else rssi_byte - 256

            # 天线号 (尝试从data[8]读取)
            tag.antenna_num = data[8] if len(data) > 8 else 0

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
            self.log(f"标签无效: {tag.error_message}", "WARN")
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
            # 写入完成后读回的标签，根据写入类型覆盖对应字段
            if self.write_done:
                for existing_tag in self.tag_history:
                    if existing_tag.epc == tag.epc:
                        if self.b_write_epc:
                            existing_tag.epc = tag.epc
                        existing_tag.user_data = tag.user_data
                        self.add_message(f"串口RFID更新已写入标签数据，EPC: {tag.epc}")
                        break
            else:
                self.add_message(f"串口RFID检测到重复标签，EPC: {tag.epc} 已存在")
    def on_barcode_received(self, barcode):
        if not barcode: return
        self.root.after(0, lambda: self.update_barcode(barcode))
        if self.direction != 0 and not self.barcode_reported:
            self.barcode_reported = True
            self._send_tcp_report_barcode_message(barcode)

    def clear_barcode_cache(self):
        self.barcode_reported = False
        if self.bar_scanner:
            with self.bar_scanner.lock: self.bar_scanner.barcode_queue.clear()

    def get_all_barcodes(self):
        return self.bar_scanner.get_all_barcodes() if self.bar_scanner else []

    # ===================================================================
    #  写标签
    # ===================================================================
    def _execute_fixed_write(self, b_write_epc=False):
        """
        同步执行写标签，优先使用TCP下发的数据，写成功后启动验证读取。
        :param b_write_epc: True=写EPC, False=写USER_DATA
        """
        self.write_in_progress = True
        self.b_write_epc = b_write_epc

        # 优先使用TCP下发的数据，否则使用固定默认数据
        write_data = self.pending_write_data if self.pending_write_data else self.FIXED_DEFAULT_DATA
        self.actual_write_data = write_data  # 记录实际写入的数据，用于后续校验
        data_hex = ' '.join(f'{b:02X}' for b in write_data)
        source = "TCP下发" if self.pending_write_data else "默认"
        write_type = "EPC" if b_write_epc else "USER_DATA"
        self.add_message(f"开始写入标签{write_type}({source}): {data_hex}")

        # 根据类型调用不同的写方法
        write_func = self.rfid_reader_serial.write_tag_with_epcdata if b_write_epc else self.rfid_reader_serial.write_tag_with_userdata
        success = write_func(write_data)
        if success:
            self.write_done = True
            self.write_in_progress = False
            self.add_message(f"写标签{write_type}成功，启动验证读取...")
            self.rfid_reader_serial.startloop_tid_user()
            return True
        else:
            self.log(f"写标签{write_type}失败，重试中...", "WARN")
            success = write_func(write_data)
            if success:
                self.write_done = True
                self.write_in_progress = False
                self.add_message(f"重试写标签{write_type}成功，启动验证读取...")
                self.rfid_reader_serial.startloop_tid_user()
                return True
            else:
                self.write_done = False
                self.write_in_progress = False
                self.log(f"写标签{write_type}失败（已重试），读取原始标签...", "ERROR")
                self.rfid_reader_serial.startloop_tid_user()
                return False

    def on_rfid_write_result(self, success):
        self.log(f"写标签结果: {'成功' if success else '失败'}", "INFO" if success else "WARN")

    # ===================================================================
    #  TCP指令
    # ===================================================================
    def _parse_tcp_write_data(self, data: bytes):
        if len(data) < 20: return data + bytes(20 - len(data))
        return data[:20]

    def on_cmd_write_epc(self, epc_data: bytes):
        write_data = self._parse_tcp_write_data(epc_data)
        self.pending_write_data = write_data
        data_hex = ' '.join(f'{b:02X}' for b in write_data)
        self.log(f"TCP写EPC({len(write_data)}字节): {data_hex}", "INFO")
        # 显示在待写入代码
        self.root.after(0, lambda: self.update_pending_code(data_hex))
        # 调用parse_product_info
        self.root.after(0, lambda: self.parse_product_info(write_data))
        if self.direction == 0:
            self.log("TCP写EPC忽略：不在出入库过程中", "WARN"); return
        if not self.write_done and not self.write_in_progress:
            self.root.after(0, lambda: self._execute_fixed_write(b_write_epc=True))

    def on_cmd_write_user(self, user_data: bytes):
        write_data = self._parse_tcp_write_data(user_data)
        self.pending_write_data = write_data
        self.log(f"TCP写USER_DATA({len(write_data)}字节): {' '.join(f'{b:02X}' for b in write_data)}", "INFO")
        if self.direction == 0:
            self.log("TCP写USER_DATA忽略：不在出入库过程中", "WARN"); return
        if not self.write_done and not self.write_in_progress:
            self.root.after(0, lambda: self._execute_fixed_write(b_write_epc=False))

    def on_cmd_beidou_info(self, beidou_id: str, beidou_time: str, beidou_location: str):
        """处理北斗信息指令，填入北斗信息区域"""
        self.log(f"北斗信息: id={beidou_id} time={beidou_time} location={beidou_location}", "INFO")
        self.root.after(0, lambda: self.update_beidou_id(beidou_id))
        self.root.after(0, lambda: self.update_beidou_time(beidou_time))
        self.root.after(0, lambda: self.update_beidou_location(beidou_location))

    def update_beidou_id(self, text: str):
        self._set_entry('beidou_id', text)

    def update_beidou_time(self, text: str):
        self._set_entry('beidou_time', text)

    def update_beidou_location(self, text: str):
        self._set_entry('beidou_location', text)

    def on_tcp_message(self, data: bytes, addr):
        """
        收到 TCP 客户端消息时的回调（新）
        支持指令格式:
          {"type": "write_epc",   "epc": [...]}
          {"type": "write_user",  "user_data": [...]}
          {"cmd":  "beidou_info", "id": "...", "time": "...", "location": "..."}
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

        elif json_data.get("cmd") == "beidou_info":
            beidou_id = json_data.get("id", "")
            beidou_time = json_data.get("time", "")
            beidou_location = json_data.get("location", "")
            self.on_cmd_beidou_info(beidou_id, beidou_time, beidou_location)

        else:
            self.add_message(f"TCP 收到未知指令类型: {cmd_type}")

    # ===================================================================
    #  TCP发送
    # ===================================================================
    def send_mqtt_command(self, command, data_type, data=None):
        """发送MQTT命令"""
        if not hasattr(self, 'mqtt_client') or not self.mqtt_client.connected:
            self.log("MQTT客户端未连接，无法发送命令", "WARN")
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
            return True
        except Exception as e:
            self.log(f"发送MQTT命令失败: {e}", "ERROR")
            return False

    def _send_tcp_pass_message(self):
        """通过TCP向连接的客户端发送通行完成消息"""
        tag_count = len(self.tag_history)
        msg = json.dumps({"type": "pass", "number": tag_count}, ensure_ascii=False)
        self.tcp_server.send_to_all(msg)

    def _send_tcp_cargo_in_message(self):
        self.tcp_server.send_to_all(json.dumps({"type": "cargo_in"}, ensure_ascii=False))
        self.add_message("TCP发送: cargo_in")

    def _send_tcp_cargo_out_message(self):
        self.tcp_server.send_to_all(json.dumps({"type": "cargo_out"}, ensure_ascii=False))
        self.add_message("TCP发送: cargo_out")

    def _send_tcp_report_barcode_message(self, barcode):
        self.tcp_server.send_to_all(json.dumps({"type": "report_barcode", "barcode": barcode}, ensure_ascii=False))
        self.add_message(f"TCP发送: report_barcode {barcode}")

    @staticmethod
    def _hex_str_to_bytes(hex_str):
        c = hex_str.replace(' ', '')
        return [int(c[i:i + 2], 16) for i in range(0, len(c), 2)]

    def _send_tcp_rfid_data_message(self, tid, epc, user_data, write_result):
        self.tcp_server.send_to_all(json.dumps({
            "type": "report_rfid", "tid": self._hex_str_to_bytes(tid) if tid else [],
            "epc": self._hex_str_to_bytes(epc) if epc else [],
            "user_data": self._hex_str_to_bytes(user_data) if user_data else [],
            "write_result": write_result
        }, ensure_ascii=False))
        self.add_message(f"TCP发送: report_rfid write_result={write_result}")

    def report_rfid_tags_via_tcp(self):
        for tag in self.tag_history:
            if not tag.success:
                continue
            read_data = tag.epc.replace(' ', '').upper() if self.b_write_epc else tag.user_data.replace(' ', '').upper()
            written_data = self.actual_write_data.hex().upper() if self.actual_write_data else self.FIXED_DEFAULT_DATA.hex().upper()
            self._send_tcp_rfid_data_message(tag.tid, tag.epc, tag.user_data, "success" if read_data == written_data else "fail")

    # ===================================================================
    #  上报服务端
    # ===================================================================
    def report_rfid_tags_to_server(self, data_type=DATA_TYPE_INBOUND, barcodes=None):
        if not REPORT_TO_SERVER:
            self.log("REPORT_TO_SERVER=False, 跳过上报", "DEBUG")
            return False
        if barcodes is None:
            barcodes = []
        if not (self.tag_history or barcodes):
            return False
        tag_data = []
        write_match_count = 0
        for tag in self.tag_history:
            if not tag.success:
                continue
            read_data = tag.epc.replace(' ', '').upper() if self.b_write_epc else tag.user_data.replace(' ', '').upper()
            written_data = self.actual_write_data.hex().upper() if self.actual_write_data else self.FIXED_DEFAULT_DATA.hex().upper()
            data_match = (read_data == written_data)
            if data_match:
                    write_match_count += 1
            tag_data.append({'epc': tag.epc, 'tid': tag.tid, 'user_data': tag.user_data, 'rssi': tag.rssi,
                             'timestamp': tag.timestamp, 'product_name': tag.product_name,
                             'antenna_num': tag.antenna_num, 'write_verified': data_match})
        if tag_data:
            if data_type == DATA_TYPE_INBOUND: self.inbound_total += len(tag_data)
            else: self.outbound_total += len(tag_data)
            self.root.after(0, lambda: self.total_label.configure(text=str(self.inbound_total + self.outbound_total)))
            if REPORT_USE_MQTT:
                self.send_mqtt_command('report_tags', data_type, {
                    'tags': tag_data, 'barcodes': barcodes,
                    'validation': {'write_verified_count': write_match_count, 'write_total_count': len(tag_data)},
                    'write_success': self.write_done
                })
            else:
                for td in tag_data:
                    wr = "success" if td['write_verified'] else "fail"
                    body = {"type": "report_rfid", "device_id": self.device_id,
                            "tid": self._hex_str_to_bytes(td['tid']) if td['tid'] else [],
                            "epc": self._hex_str_to_bytes(td['epc']) if td['epc'] else [],
                            "user_data": self._hex_str_to_bytes(td['user_data']) if td['user_data'] else [],
                            "write_result": wr}
                    try:
                        req = urllib.request.Request(f"{API_BASE_URL}/api/report-rfid/",
                                                     json.dumps(body, ensure_ascii=False).encode('utf-8'),
                                                     {'Content-Type': 'application/json'}, method='POST')
                        with urllib.request.urlopen(req, timeout=5) as r:
                            self.log(f"HTTP上报 OK EPC={td['epc']}", "INFO")
                    except Exception as e:
                        self.log(f"HTTP上报失败: {e}", "ERROR")
            # 完成后将最后标签的TID/EPC填入集成设备信息
            if self.tag_history:
                last = self.tag_history[-1]
                self.root.after(0, lambda: (self.update_tid(last.tid), self.update_epc(last.epc)))
            self.tag_history.clear()
            self.write_done = False
            self.actual_write_data = None
        return True

    # ===================================================================
    #  入口
    # ===================================================================
    def show(self):
        if self._owns_root: self.root.mainloop()

    def run(self):
        self.show()


if __name__ == "__main__":
    MainWindow().run()
