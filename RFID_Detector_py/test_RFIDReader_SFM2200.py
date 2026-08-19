# test_RFIDReader_SFM2200.py
# RFIDReader_SFM2200 独立读写测试程序
import tkinter as tk
from tkinter import ttk
import threading
import time
from datetime import datetime

from RFIDReader_SFM2200 import RFIDReader_SFM2200


class TestApp:
    def __init__(self, root):
        self.root = root
        self.root.title("RFIDReader_SFM2200 读写测试")
        self.root.geometry("900x750")
        self.root.configure(bg='#f5f5f5')

        self.reader = RFIDReader_SFM2200(port='', baudrate=115200, timeout=1.0)
        self.reader.set_callback(self.on_tag_data)

        # 读操作状态
        self.tag_buffer = bytearray()
        self.tag_epc_set = set()      # 去重 EPC
        self.read_count = 0           # 识别次数
        self.current_tid = ""
        self.current_epc = ""
        self.current_userdata = ""

        # 写操作状态
        self.write_count = 0
        self.write_success = 0

        # 测试状态
        self.test_running = False
        self.test_thread = None
        self.test_start_time = None
        self.test_duration = 60  # 默认60秒

        self.build_ui()
        self.update_runtime()

    # ========== UI 构建 ==========
    def build_ui(self):
        # 标题
        title = tk.Label(self.root, text="RFID读写器测试程序",
                         font=("微软雅黑", 16, "bold"), bg='#f5f5f5')
        title.pack(pady=10)

        # 软件设置
        self.setting_frame = tk.LabelFrame(self.root, text=" 软件设置 ",
                                           font=("微软雅黑", 11, "bold"), bg='#f5f5f5')
        self.setting_frame.pack(fill='x', padx=10, pady=5)
        r0 = tk.Frame(self.setting_frame, bg='#f5f5f5')
        r0.pack(fill='x', padx=10, pady=5)

        tk.Label(r0, text="测试运行时间:", font=("微软雅黑", 10), bg='#f5f5f5').pack(side='left')
        self.runtime_label = tk.Label(r0, text="00:00:00", font=("微软雅黑", 10, "bold"), bg='#f5f5f5', fg='#2196F3')
        self.runtime_label.pack(side='left', padx=(0, 20))

        tk.Label(r0, text="测试时长(秒):", font=("微软雅黑", 10), bg='#f5f5f5').pack(side='left')
        self.duration_entry = tk.Entry(r0, width=8, font=("微软雅黑", 10))
        self.duration_entry.insert(0, "60")
        self.duration_entry.pack(side='left', padx=(0, 20))

        tk.Label(r0, text="读写器端口:", font=("微软雅黑", 10), bg='#f5f5f5').pack(side='left')
        self.port_entry = tk.Entry(r0, width=25, font=("微软雅黑", 10))
        self.port_entry.insert(0, "/dev/tty.usbserial-1410")
        self.port_entry.pack(side='left', padx=(0, 20))

        self.connect_btn = tk.Button(r0, text="连接", font=("微软雅黑", 10),
                                     bg='#4CAF50', fg='black', command=self.on_connect)
        self.connect_btn.pack(side='left')

        # 读操作
        self.read_frame = tk.LabelFrame(self.root, text=" 读操作 ",
                                        font=("微软雅黑", 11, "bold"), bg='#f5f5f5')
        self.read_frame.pack(fill='x', padx=10, pady=5)

        grid = tk.Frame(self.read_frame, bg='#f5f5f5')
        grid.pack(fill='x', padx=10, pady=5)
        fields = [
            ("TID:", 'tid_label'),
            ("EPC:", 'epc_label'),
            ("USERDATA:", 'userdata_label'),
        ]
        for i, (label, attr) in enumerate(fields):
            tk.Label(grid, text=label, font=("微软雅黑", 10), bg='#f5f5f5',
                     anchor='e', width=10).grid(row=i, column=0, sticky='e', padx=5, pady=2)
            lbl = tk.Label(grid, text="", font=("微软雅黑", 10), bg='white',
                           relief='solid', bd=1, anchor='w', width=60)
            lbl.grid(row=i, column=1, sticky='ew', padx=5, pady=2)
            setattr(self, attr, lbl)

        # 标签数量和识别次数，同一行纯文本显示
        count_row = tk.Frame(self.read_frame, bg='#f5f5f5')
        count_row.pack(fill='x', padx=10, pady=3)
        tk.Label(count_row, text="标签数量:", font=("微软雅黑", 10), bg='#f5f5f5').pack(side='left')
        self.tag_count_label = tk.Label(count_row, text="0", font=("微软雅黑", 10, "bold"),
                                        bg='#f5f5f5', fg='#2196F3')
        self.tag_count_label.pack(side='left', padx=(0, 40))
        tk.Label(count_row, text="识别次数:", font=("微软雅黑", 10), bg='#f5f5f5').pack(side='left')
        self.read_count_label = tk.Label(count_row, text="0", font=("微软雅黑", 10, "bold"),
                                         bg='#f5f5f5', fg='#2196F3')
        self.read_count_label.pack(side='left')

        self.read_start_btn = tk.Button(self.read_frame, text="启动读操作测试",
                                        font=("微软雅黑", 10), bg='#2196F3', fg='black',
                                        command=self.on_start_read)
        self.read_start_btn.pack(side='right', padx=10, pady=5)

        # 写操作
        self.write_frame = tk.LabelFrame(self.root, text=" 写操作 ",
                                         font=("微软雅黑", 11, "bold"), bg='#f5f5f5')
        self.write_frame.pack(fill='x', padx=10, pady=5)

        w0 = tk.Frame(self.write_frame, bg='#f5f5f5')
        w0.pack(fill='x', padx=10, pady=5)
        tk.Label(w0, text="写入数据:", font=("微软雅黑", 10), bg='#f5f5f5').pack(side='left')
        self.write_data_entry = tk.Entry(w0, width=45, font=("微软雅黑", 10))
        self.write_data_entry.pack(side='left', padx=5)

        w1 = tk.Frame(self.write_frame, bg='#f5f5f5')
        w1.pack(fill='x', padx=10, pady=3)
        tk.Label(w1, text="写入区域:", font=("微软雅黑", 10), bg='#f5f5f5').pack(side='left', padx=(0, 10))
        self.write_region = tk.StringVar(value="USERDATA")
        tk.Radiobutton(w1, text="EPC", variable=self.write_region, value="EPC",
                       font=("微软雅黑", 10), bg='#f5f5f5').pack(side='left', padx=10)
        tk.Radiobutton(w1, text="USERDATA", variable=self.write_region, value="USERDATA",
                       font=("微软雅黑", 10), bg='#f5f5f5').pack(side='left', padx=10)

        w2 = tk.Frame(self.write_frame, bg='#f5f5f5')
        w2.pack(fill='x', padx=10, pady=3)
        tk.Label(w2, text="测试方式:", font=("微软雅黑", 10), bg='#f5f5f5').pack(side='left', padx=(0, 10))
        self.write_mode = tk.StringVar(value="single")
        tk.Radiobutton(w2, text="单写", variable=self.write_mode, value="single",
                       font=("微软雅黑", 10), bg='#f5f5f5').pack(side='left', padx=10)
        tk.Radiobutton(w2, text="读写校验", variable=self.write_mode, value="verify",
                       font=("微软雅黑", 10), bg='#f5f5f5').pack(side='left', padx=10)

        w3 = tk.Frame(self.write_frame, bg='#f5f5f5')
        w3.pack(fill='x', padx=10, pady=3)
        tk.Label(w3, text="执行次数:", font=("微软雅黑", 10), bg='#f5f5f5').pack(side='left')
        self.write_count_label = tk.Label(w3, text="0", font=("微软雅黑", 10, "bold"),
                                          bg='#f5f5f5', fg='#FF9800')
        self.write_count_label.pack(side='left', padx=(0, 40))
        tk.Label(w3, text="成功次数:", font=("微软雅黑", 10), bg='#f5f5f5').pack(side='left')
        self.write_success_label = tk.Label(w3, text="0", font=("微软雅黑", 10, "bold"),
                                            bg='#f5f5f5', fg='#FF9800')
        self.write_success_label.pack(side='left', padx=(0, 20))

        self.write_start_btn = tk.Button(w3, text="启动写操作测试",
                                         font=("微软雅黑", 10), bg='#FF9800', fg='black',
                                         command=self.on_start_write)
        self.write_start_btn.pack(side='right', padx=10)

        # 系统日志
        self.log_frame = tk.LabelFrame(self.root, text=" 系统日志 ",
                                       font=("微软雅黑", 11, "bold"), bg='#f5f5f5')
        self.log_frame.pack(fill='both', expand=True, padx=10, pady=5)
        self.log_text = tk.Text(self.log_frame, font=("Consolas", 9), bg='white', relief='flat')
        self.log_text.pack(fill='both', expand=True, padx=5, pady=5)
        self.log_text.configure(state='disabled')
        self.log_text.tag_config("error", foreground="#f44336")
        self.log_text.tag_config("warn", foreground="#ff9800")
        self.log_text.tag_config("info", foreground="#4CAF50")
        self.log_text.tag_config("debug", foreground="#2196F3")
        self.log_text.tag_config("msg", foreground="#000000")

    # ========== 日志 ==========
    def log(self, message, level="info"):
        ts = time.strftime("%H:%M:%S")
        tag_map = {"error": "ERROR", "warn": "WARN", "info": "INFO", "debug": "DEBUG"}
        self.log_text.configure(state='normal')
        self.log_text.insert('end', f"[{ts}] [{tag_map.get(level, 'INFO')}] ", (level,))
        self.log_text.insert('end', f"{message}\n", ("msg",))
        self.log_text.see('end')
        self.log_text.configure(state='disabled')

    # ========== 连接 ==========
    def on_connect(self):
        port = self.port_entry.get().strip()
        if not port:
            self.log("请先输入读写器端口", "warn")
            return
        self.reader.port = port

        def connect():
            if self.reader.open():
                self.reader.start_firmware()
                self.reader.start_receive_loop()
                self.root.after(0, lambda: self.log(f"连接成功: {port}", "info"))
                self.root.after(0, lambda: self.connect_btn.config(text="已连接", bg='#4CAF50'))
            else:
                self.root.after(0, lambda: self.log(f"连接失败: {port}", "error"))
        threading.Thread(target=connect, daemon=True).start()

    # ========== 标签数据回调 ==========
    def on_tag_data(self, data: bytes):
        self.tag_buffer.extend(data)
        while True:
            tag, consumed = self._try_parse_tid_user(self.tag_buffer)
            if consumed > 0:
                self.tag_buffer = self.tag_buffer[consumed:]
                if tag is not None:
                    self._handle_parsed_tag(tag)
            else:
                break

    def _try_parse_tid_user(self, buf):
        hdr = bytes([0xFF, 0x47, 0xAA])
        hl = len(hdr)
        fi = -1
        for i in range(len(buf) - hl + 1):
            if buf[i] == 0xFF and buf[i + 2] == 0xAA:
                if buf[i + 1] == 0x47:
                    fi = i
                    break
        if fi == -1:
            for i in range(len(buf) - 2):
                if buf[i] == 0xFF and buf[i + 2] == 0xAA:
                    return None, i + 3
            return None, len(buf)
        if fi > 0:
            return None, fi
        si = -1
        for i in range(fi + hl, len(buf) - hl + 1):
            if buf[i] == 0xFF and buf[i + 2] == 0xAA and buf[i + 1] == 0x47:
                si = i
                break
        if si == -1:
            return None, 0
        packet = bytes(buf[fi:si])
        tag = self._parse_tid_user(packet)
        return (tag, si) if tag else (None, hl)

    def _parse_tid_user(self, data):
        if len(data) < 74:
            return None
        return {
            'tid': ' '.join(f'{b:02X}' for b in data[15:31]),
            'user_data': ' '.join(f'{b:02X}' for b in data[31:51]),
            'epc': ''.join(f'{b:02X}' for b in data[54:74]),
        }

    def _handle_parsed_tag(self, tag):
        self.current_tid = tag['tid']
        self.current_epc = tag['epc']
        self.current_userdata = tag['user_data']
        self.read_count += 1
        if tag['epc']:
            self.tag_epc_set.add(tag['epc'])

        def update_ui():
            self.tid_label.config(text=tag['tid'])
            self.epc_label.config(text=tag['epc'])
            self.userdata_label.config(text=tag['user_data'])
            self.tag_count_label.config(text=str(len(self.tag_epc_set)))
            self.read_count_label.config(text=str(self.read_count))
        self.root.after(0, update_ui)

    # ========== 读操作测试 ==========
    def on_start_read(self):
        if self.test_running:
            self.log("测试已在运行中", "warn")
            return
        self._parse_duration()
        self.log(f"启动读操作测试，时长 {self.test_duration} 秒", "info")
        self.reader.startloop_tid_user()
        self._start_test_timer()

    # ========== 写操作测试 ==========
    def on_start_write(self):
        if self.test_running:
            self.log("测试已在运行中", "warn")
            return
        self._parse_duration()

        data_hex = self.write_data_entry.get().strip()
        if not data_hex:
            self.log("请先输入写入数据", "warn")
            return
        write_data = self._hex_to_bytes(data_hex)
        if len(write_data) != 20:
            self.log(f"写入数据需为20字节，当前 {len(write_data)} 字节", "error")
            return

        region = self.write_region.get()
        mode = self.write_mode.get()
        self.log(f"启动写操作测试 区域={region} 方式={mode} 时长={self.test_duration}秒", "info")

        def write_loop():
            while self.test_running:
                self.write_count += 1
                if region == "EPC":
                    ok = self.reader.write_tag_with_epcdata(write_data)
                else:
                    ok = self.reader.write_tag_with_userdata(write_data)

                if mode == "single":
                    if ok:
                        self.write_success += 1
                else:
                    # 读写校验
                    if ok:
                        self.reader.startloop_tid_user()
                        # 等待读回数据
                        time.sleep(0.3)
                        read_back = self.current_epc if region == "EPC" else self.current_userdata.replace(' ', '')
                        written = data_hex.upper()
                        if read_back.upper() == written:
                            self.write_success += 1

                self.root.after(0, lambda: self.write_count_label.config(text=str(self.write_count)))
                self.root.after(0, lambda: self.write_success_label.config(text=str(self.write_success)))
                time.sleep(0.05)

        self.test_running = True
        self.test_start_time = time.time()
        self.test_thread = threading.Thread(target=write_loop, daemon=True)
        self.test_thread.start()
        self._start_timer_check("写操作")

    # ========== 测试计时 ==========
    def _parse_duration(self):
        try:
            self.test_duration = int(self.duration_entry.get().strip())
        except ValueError:
            self.test_duration = 60
        if self.test_duration <= 0:
            self.test_duration = 60

    def _start_test_timer(self):
        self.test_running = True
        self.test_start_time = time.time()

    def _start_timer_check(self, mode):
        def check():
            while self.test_running:
                if time.time() - self.test_start_time >= self.test_duration:
                    self.test_running = False
                    self.reader.stoploop()
                    self._output_report(mode)
                    break
                time.sleep(0.1)
        threading.Thread(target=check, daemon=True).start()

    def _output_report(self, mode):
        elapsed = time.time() - self.test_start_time
        report = (f"===== {mode}测试报告 =====\n"
                  f"测试时长: {elapsed:.1f} 秒\n"
                  f"读操作: 识别次数={self.read_count}, 标签数量={len(self.tag_epc_set)}\n"
                  f"写操作: 执行次数={self.write_count}, 成功次数={self.write_success}\n")
        if self.write_count > 0:
            rate = self.write_success / self.write_count * 100
            report += f"写成功率: {rate:.1f}%\n"
        report += "========================"
        self.log(report, "info")

    # ========== 运行时间显示 ==========
    def update_runtime(self):
        if self.test_running and self.test_start_time:
            elapsed = int(time.time() - self.test_start_time)
            h, rem = divmod(elapsed, 3600)
            m, s = divmod(rem, 60)
            self.runtime_label.config(text=f"{h:02d}:{m:02d}:{s:02d}")
        else:
            self.runtime_label.config(text="00:00:00")
        self.root.after(1000, self.update_runtime)

    # ========== 工具 ==========
    @staticmethod
    def _hex_to_bytes(hex_str):
        clean = hex_str.replace(' ', '').replace('0x', '').replace(',', '')
        if len(clean) % 2 != 0:
            clean = clean[:-1]
        return bytes.fromhex(clean)


if __name__ == "__main__":
    root = tk.Tk()
    app = TestApp(root)
    root.mainloop()
