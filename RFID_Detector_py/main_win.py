# main_win.py
# tkinter 界面 — 参考 pythonProject main_ui 右侧两列布局
import tkinter as tk
from tkinter import ttk
import time
from datetime import datetime


class MainWindow:
    """主窗口 — 生产线信息 / 集成设备信息 / 北斗信息 / RFID控制 / 调试信息"""

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

        # 配色（参考 PyQt 原版风格）
        self.c = {
            'bg': 'white',
            'fg': '#2c3e50',
            'accent': '#4CAF50',
            'entry_border': '#cccccc',
        }

        # 顶栏 — 标题
        title_frame = tk.Frame(self.root, bg='white')
        title_frame.pack(fill='x', padx=15, pady=(15, 5))
        tk.Label(title_frame, text="北斗+RFID系统集成设备",
                 font=("Microsoft YaHei", 16, "bold"),
                 bg='white', fg='#2c3e50').pack(side='left')

        # 主体 — 双列
        main = tk.Frame(self.root, bg='white')
        main.pack(fill='both', expand=True, padx=15, pady=5)

        # 列权重: 左2 右1
        main.columnconfigure(0, weight=2)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        left_col = tk.Frame(main, bg='white')
        left_col.grid(row=0, column=0, sticky='nsew', padx=(0, 8))
        right_col = tk.Frame(main, bg='white')
        right_col.grid(row=0, column=1, sticky='nsew', padx=(8, 0))

        self.build_production_group(left_col)
        self.build_device_info_group(left_col)

        self.build_beidou_group(right_col)
        self.build_rfid_group(right_col)
        self.build_debug_group(right_col)

    # ===================================================================
    #  生产线信息
    # ===================================================================
    def build_production_group(self, parent):
        frame = self._labelframe(parent, "生产线信息")
        frame.pack(fill='x', pady=(0, 10))

        fs = {'font': ("Microsoft YaHei", 10), 'bg': 'white', 'fg': self.c['fg']}
        entry_opts = {'font': ("Microsoft YaHei", 10), 'relief': 'solid', 'bd': 1,
                      'bg': 'white', 'highlightthickness': 0}

        # 行0 — 生产企业 & 许可证号
        r0 = tk.Frame(frame, bg='white')
        r0.pack(fill='x', padx=10, pady=3)
        tk.Label(r0, text="生产企业：", **fs).pack(side='left')
        self.manufacturer_combo = ttk.Combobox(r0, font=("Microsoft YaHei", 10), width=18)
        self.manufacturer_combo.pack(side='left', padx=(0, 20))
        tk.Label(r0, text="生产许可证编号：", **fs).pack(side='left')
        self.license_number = tk.Entry(r0, width=22, **entry_opts)
        self.license_number.configure(state='readonly', readonlybackground='#f0f0f0')
        self.license_number.pack(side='left')

        # 行1 — 产品种类 & 规格型号
        r1 = tk.Frame(frame, bg='white')
        r1.pack(fill='x', padx=10, pady=3)
        tk.Label(r1, text="产品种类：", **fs).pack(side='left')
        self.product_type = ttk.Combobox(r1, font=("Microsoft YaHei", 10), width=18)
        self.product_type.bind('<<ComboboxSelected>>', self._on_product_type_changed)
        self.product_type.pack(side='left', padx=(0, 20))
        tk.Label(r1, text="规格型号：", **fs).pack(side='left')
        self.type_box = ttk.Combobox(r1, font=("Microsoft YaHei", 10), width=20)
        self.type_box.pack(side='left')

        # 行2 — 净质量 & 生产日期
        r2 = tk.Frame(frame, bg='white')
        r2.pack(fill='x', padx=10, pady=3)
        tk.Label(r2, text="净质量：", **fs).pack(side='left')
        self.weight_box = ttk.Combobox(r2, font=("Microsoft YaHei", 10), width=18)
        self.weight_box.pack(side='left', padx=(0, 20))
        tk.Label(r2, text="生产日期：", **fs).pack(side='left')
        self.production_date = tk.Entry(r2, width=22, **entry_opts)
        self.production_date.insert(0, datetime.now().strftime("%Y%m%d"))
        self.production_date.pack(side='left')

        # 行3 — 批号 & 袋/箱号
        r3 = tk.Frame(frame, bg='white')
        r3.pack(fill='x', padx=10, pady=3)
        tk.Label(r3, text="生产批号：", **fs).pack(side='left')
        self.batch_number = tk.Entry(r3, width=18, **entry_opts)
        self.batch_number.pack(side='left', padx=(0, 20))
        tk.Label(r3, text="袋/箱号：", **fs).pack(side='left')
        self.package_number = tk.Entry(r3, width=20, **entry_opts)
        self.package_number.pack(side='left')

        # 行4 — 生产线信息代码
        r4 = tk.Frame(frame, bg='white')
        r4.pack(fill='x', padx=10, pady=3)
        tk.Label(r4, text="信息代码：", **fs).pack(side='left')
        self.production_line_code = tk.Entry(r4, **entry_opts)
        self.production_line_code.configure(state='readonly', readonlybackground='#f0f0f0')
        self.production_line_code.pack(side='left', fill='x', expand=True)

        # 行5 — 包装方式 + 生产状态
        r5 = tk.Frame(frame, bg='white')
        r5.pack(fill='x', padx=10, pady=5)

        pkg_frame = self._labelframe(r5, "包装方式")
        pkg_frame.pack(side='left', padx=(0, 15))
        pkg_inner = tk.Frame(pkg_frame, bg='white')
        pkg_inner.pack(padx=20, pady=3)
        self.pkg_var = tk.StringVar(value="bag")
        tk.Radiobutton(pkg_inner, text="箱  装", variable=self.pkg_var, value="box",
                       font=("Microsoft YaHei", 10), bg='white').pack(side='left', padx=10)
        tk.Radiobutton(pkg_inner, text="袋  装", variable=self.pkg_var, value="bag",
                       font=("Microsoft YaHei", 10), bg='white').pack(side='left', padx=10)

        state_frame = self._labelframe(r5, "生产状态")
        state_frame.pack(side='left')
        state_inner = tk.Frame(state_frame, bg='white')
        state_inner.pack(padx=20, pady=3)
        self.state_var = tk.StringVar(value="idle")
        tk.Radiobutton(state_inner, text="产 品 进 入", variable=self.state_var, value="cargo_in",
                       font=("Microsoft YaHei", 10), bg='white', state='disabled').pack(side='left', padx=10)
        tk.Radiobutton(state_inner, text="产 品 通 过", variable=self.state_var, value="cargo_out",
                       font=("Microsoft YaHei", 10), bg='white', state='disabled').pack(side='left', padx=10)

    # ===================================================================
    #  集成设备信息
    # ===================================================================
    def build_device_info_group(self, parent):
        frame = self._labelframe(parent, "集成设备信息")
        frame.pack(fill='x', pady=(0, 10))

        fs = {'font': ("Microsoft YaHei", 10), 'bg': 'white', 'fg': self.c['fg']}
        entry_opts = {'font': ("Microsoft YaHei", 10), 'relief': 'solid', 'bd': 1,
                      'bg': 'white', 'highlightthickness': 0,
                      'readonlybackground': '#f0f0f0'}
        val_opts = {'font': ("Microsoft YaHei", 10, "bold"), 'bg': 'white', 'fg': self.c['accent']}

        # 条形码
        self._info_row(frame, "条形码：", entry_opts, 'barcode_edit', readonly=True)
        # 待写入代码
        self._info_row(frame, "待写入代码：", entry_opts, 'pending_code_edit', readonly=True)
        # TID
        self._info_row(frame, "TID：", entry_opts, 'tid_edit', readonly=True)
        # EPC
        self._info_row(frame, "EPC：", entry_opts, 'epc_edit', readonly=True)
        # 产线运行时间
        self._label_row(frame, "产线运行时间：", "00时00分", 'runtime_label')
        # 当前识别数量
        self._label_row(frame, "当前识别数量：", "0", 'current_load_label')
        # 识别总量
        self._label_row(frame, "识别总量：", "0", 'total_label')
        # 生产总量
        self._label_row(frame, "生产总量：", "0", 'production_total_label', fg='#27ae60')

    def _info_row(self, parent, label_text, entry_opts, attr, readonly=False):
        r = tk.Frame(parent, bg='white')
        r.pack(fill='x', padx=10, pady=2)
        tk.Label(r, text=label_text, font=("Microsoft YaHei", 10),
                 bg='white', fg=self.c['fg']).pack(side='left')
        e = tk.Entry(r, **entry_opts)
        if readonly:
            e.configure(state='readonly')
        e.pack(side='left', fill='x', expand=True, padx=(5, 0))
        setattr(self, attr, e)

    def _label_row(self, parent, label_text, value, attr, fg=None):
        r = tk.Frame(parent, bg='white')
        r.pack(fill='x', padx=10, pady=2)
        tk.Label(r, text=label_text, font=("Microsoft YaHei", 10),
                 bg='white', fg=self.c['fg']).pack(side='left')
        lbl = tk.Label(r, text=value, font=("Microsoft YaHei", 10, "bold"),
                       bg='white', fg=fg or self.c['accent'])
        lbl.pack(side='left', padx=(5, 0))
        setattr(self, attr, lbl)

    # ===================================================================
    #  北斗信息
    # ===================================================================
    def build_beidou_group(self, parent):
        frame = self._labelframe(parent, "北斗信息")
        frame.pack(fill='x', pady=(0, 10))

        entry_opts = {'font': ("Microsoft YaHei", 10), 'relief': 'solid', 'bd': 1,
                      'bg': 'white', 'highlightthickness': 0, 'readonlybackground': '#f0f0f0'}

        self._info_row(frame, "北斗ID：", entry_opts, 'beidou_id', readonly=True)
        self._info_row(frame, "当前北斗时间：", entry_opts, 'beidou_time', readonly=True)
        self._info_row(frame, "北斗位置：", entry_opts, 'beidou_location', readonly=True)

    # ===================================================================
    #  RFID控制
    # ===================================================================
    def build_rfid_group(self, parent):
        frame = self._labelframe(parent, "RFID控制")
        frame.pack(fill='x', pady=(0, 10))

        entry_opts = {'font': ("Microsoft YaHei", 10), 'relief': 'solid', 'bd': 1,
                      'bg': 'white', 'highlightthickness': 0}

        # 天线号
        self._info_row(frame, "天线号：", entry_opts, 'antenna_edit')
        # 功率
        self._info_row(frame, "功率(dBm)：", entry_opts, 'power_edit')
        # 频点
        self._info_row(frame, "频点：", entry_opts, 'frequency_edit')

        # 控制按钮
        btn_frame = tk.Frame(frame, bg='white')
        btn_frame.pack(fill='x', padx=10, pady=8)

        btn_green = {'font': ("Microsoft YaHei", 9, "bold"), 'bg': '#4CAF50', 'fg': 'white',
                     'activebackground': '#45a049', 'activeforeground': 'white',
                     'relief': 'flat', 'bd': 0, 'padx': 12, 'pady': 4}
        btn_orange = {**btn_green, 'bg': '#FF9800', 'activebackground': '#F57C00'}
        btn_red = {**btn_green, 'bg': '#F44336', 'activebackground': '#D32F2F'}

        self.read_params_btn = tk.Button(btn_frame, text="读取参数", **btn_green)
        self.read_params_btn.pack(side='left', padx=3)
        self.set_params_btn = tk.Button(btn_frame, text="设置参数", **btn_orange)
        self.set_params_btn.pack(side='left', padx=3)
        self.reset_rfid_btn = tk.Button(btn_frame, text="重启RFID", **btn_red)
        self.reset_rfid_btn.pack(side='left', padx=3)

    # ===================================================================
    #  调试信息
    # ===================================================================
    def build_debug_group(self, parent):
        frame = self._labelframe(parent, "调试信息")
        frame.pack(fill='both', expand=True)

        self.debug_text = tk.Text(frame, font=("Consolas", 9), relief='solid', bd=1,
                                  bg='white', wrap='word', highlightthickness=0)
        self.debug_text.pack(fill='both', expand=True, padx=5, pady=5)
        self.debug_text.configure(state='disabled')

        # 颜色tag
        self.debug_text.tag_config("error", foreground="#f44336")
        self.debug_text.tag_config("warning", foreground="#ff9800")
        self.debug_text.tag_config("info", foreground="#4CAF50")
        self.debug_text.tag_config("debug", foreground="#2196F3")

    # ===================================================================
    #  工具
    # ===================================================================
    def _labelframe(self, parent, text):
        """模拟 PyQt QGroupBox 风格的 LabelFrame"""
        f = tk.LabelFrame(parent, text=f" {text} ", font=("Microsoft YaHei", 11, "bold"),
                          bg='white', fg='#2c3e50', relief='ridge', bd=2,
                          labelanchor='n')
        return f

    # ===================================================================
    #  回调
    # ===================================================================
    def _on_product_type_changed(self, event=None):
        pass  # 子类可重写

    # ===================================================================
    #  UI更新方法
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
            e.delete(0, 'end')
            e.insert(0, str(text))

    def log(self, message: str, level: str = "info"):
        timestamp = time.strftime("%H:%M:%S")
        self.debug_text.configure(state='normal')
        self.debug_text.insert('end', f"[{timestamp}] [{level.upper()}] ", ())
        self.debug_text.insert('end', f"{message}\n", (level,))
        self.debug_text.see('end')
        self.debug_text.configure(state='disabled')
        # 限制行数
        lines = int(self.debug_text.index('end-1c').split('.')[0])
        if lines > 500:
            self.debug_text.delete('1.0', '100.0')

    def update_barcode(self, text: str):
        self._set_entry('barcode_edit', text)

    def update_tid(self, text: str):
        self._set_entry('tid_edit', text)

    def update_epc(self, text: str):
        self._set_entry('epc_edit', text)

    def update_pending_code(self, text: str):
        self._set_entry('pending_code_edit', text)

    def update_license(self, text: str):
        self._set_entry('license_number', text)

    def update_production_code(self, text: str):
        self._set_entry('production_line_code', text)

    def update_beidou_time(self, text: str):
        self._set_entry('beidou_time', text)

    def update_beidou_location(self, text: str):
        self._set_entry('beidou_location', text)

    def update_runtime(self, text: str):
        self.runtime_label.configure(text=text)

    def update_current_load(self, count: int):
        self.current_load_label.configure(text=str(count))

    def update_total_identified(self, count: int):
        self.total_label.configure(text=str(count))

    def update_production_total(self, count: int):
        self.production_total_label.configure(text=str(count))

    def set_cargo_in(self):
        self.state_var.set("cargo_in")

    def set_cargo_out(self):
        self.state_var.set("cargo_out")

    def set_product_types(self, names: list):
        self.product_type['values'] = list(names)
        if names:
            self.product_type.current(0)

    def set_manufacturers(self, names: list):
        self.manufacturer_combo['values'] = list(names)
        if names:
            self.manufacturer_combo.current(0)

    def set_type_box_items(self, items: list):
        self.type_box['values'] = list(items)
        if items:
            self.type_box.current(0)

    def set_weight_items(self, items: list):
        self.weight_box['values'] = list(items)
        if items:
            self.weight_box.current(0)

    # --- getters ---
    def get_manufacturer_name(self) -> str:
        return self.manufacturer_combo.get()

    def get_product_name(self) -> str:
        return self.product_type.get()

    def get_production_date(self) -> str:
        return self.production_date.get()

    def get_batch_number(self) -> str:
        return self.batch_number.get()

    def get_package_number(self) -> str:
        return self.package_number.get()

    def is_box_package(self) -> bool:
        return self.pkg_var.get() == "box"

    def get_type_box(self) -> str:
        return self.type_box.get()

    def get_weight(self) -> str:
        return self.weight_box.get()

    def get_rfid_params(self) -> dict:
        return {
            'antenna': self.antenna_edit.get(),
            'power': self.power_edit.get(),
            'frequency': self.frequency_edit.get()
        }

    def set_rfid_params(self, antenna: str, power: str, frequency: str):
        self.antenna_edit.delete(0, 'end')
        self.antenna_edit.insert(0, antenna)
        self.power_edit.delete(0, 'end')
        self.power_edit.insert(0, power)
        self.frequency_edit.delete(0, 'end')
        self.frequency_edit.insert(0, frequency)

    # --- 事件循环 ---
    def show(self):
        if self._owns_root:
            self.root.mainloop()

    def run(self):
        self.show()


# ===================== 测试入口 =====================
if __name__ == "__main__":
    win = MainWindow()
    win.set_product_types(["乳化炸药", "铵油炸药"])
    win.set_manufacturers(["XX化工有限公司", "YY民爆公司"])
    win.set_type_box_items(["Φ32mm×200g", "Φ70mm×3kg"])
    win.set_weight_items(["200g", "500g", "3kg"])
    win.log("系统启动完成", "info")
    win.log("RFID读写器连接成功", "info")
    win.log("标签写入失败，重试中...", "warning")
    win.update_tid("C090C000000F62FC01000000000009C5")
    win.update_epc("3032574436000B001858000C1A01010064000000")
    win.update_barcode("6923456789012")
    win.update_beidou_time("2026-07-10 15:30:00")
    win.update_beidou_location("37.8691°N 112.5594°E")
    win.update_runtime("03时25分")
    win.update_current_load(1)
    win.update_total_identified(1)
    win.update_production_total(128)
    win.log("终端设备连接正常", "debug")
    win.run()
