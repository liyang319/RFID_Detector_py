# main_win.py
# tkinter 界面 — 参考 pythonProject main_ui 右侧两列布局
import tkinter as tk
from tkinter import ttk
import time
from datetime import datetime


ENTRY_WIDTH = 18  # 编辑框统一宽度
LABEL_WIDTH = 12  # 标签统一宽度(字符)


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

        # 配色
        self.c = {'bg': 'white', 'fg': '#2c3e50', 'accent': '#4CAF50'}

        # 顶栏 — 标题
        title_frame = tk.Frame(self.root, bg='white')
        title_frame.pack(fill='x', padx=15, pady=(15, 5))
        tk.Label(title_frame, text="北斗+RFID系统集成设备",
                 font=("Microsoft YaHei", 16, "bold"),
                 bg='white', fg='#2c3e50').pack(side='left')

        # 主体 — 双列
        main = tk.Frame(self.root, bg='white')
        main.pack(fill='both', expand=True, padx=15, pady=5)
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
    #  工具方法
    # ===================================================================
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
                        bg='white', fg=self.c['fg'], anchor='e', width=LABEL_WIDTH)

    def _label_value(self, parent, text, fg=None):
        return tk.Label(parent, text=text, font=("Microsoft YaHei", 10, "bold"),
                        bg='white', fg=fg or self.c['accent'], anchor='w')

    def _grid_row_2col(self, frame, row, label1, attr1, label2, attr2, readonly1=False, readonly2=False):
        """两列模式行: label1 | entry1 | label2 | entry2"""
        lbl1 = self._label(frame, label1)
        lbl1.grid(row=row, column=0, sticky='e', padx=(10, 3), pady=2)
        e1 = self._entry(frame, readonly=readonly1)
        e1.grid(row=row, column=1, sticky='ew', padx=(0, 12), pady=2)
        setattr(self, attr1, e1)

        lbl2 = self._label(frame, label2)
        lbl2.grid(row=row, column=2, sticky='e', padx=(0, 3), pady=2)
        e2 = self._entry(frame, readonly=readonly2)
        e2.grid(row=row, column=3, sticky='ew', padx=(0, 10), pady=2)
        setattr(self, attr2, e2)

    def _grid_row_1col(self, frame, row, label, attr, readonly=False, span=3):
        """单列模式行: label | entry (跨多列)"""
        lbl = self._label(frame, label)
        lbl.grid(row=row, column=0, sticky='e', padx=(10, 3), pady=2)
        e = self._entry(frame, readonly=readonly)
        e.grid(row=row, column=1, columnspan=span, sticky='ew', padx=(0, 10), pady=2)
        setattr(self, attr, e)

    # ===================================================================
    #  生产线信息
    # ===================================================================
    def build_production_group(self, parent):
        frame = self._labelframe(parent, "生产线信息")
        frame.pack(fill='x', pady=(0, 10))
        # 4列: label | entry | label | entry
        for i in range(4):
            frame.columnconfigure(i, weight=1 if i % 2 == 1 else 0)

        self._grid_row_2col(frame, 0, "生产企业：", 'manufacturer_edit',
                             "生产许可证编号：", 'license_number', readonly2=True)
        self._grid_row_2col(frame, 1, "产品种类：", 'product_type',
                             "规格型号：", 'type_box')
        self._grid_row_2col(frame, 2, "净质量：", 'weight_box',
                             "生产日期：", 'production_date')
        self._grid_row_2col(frame, 3, "生产批号：", 'batch_number',
                             "袋/箱号：", 'package_number')

        # 信息代码 — 单列跨3格
        self._grid_row_1col(frame, 4, "信息代码：", 'production_line_code', readonly=True, span=3)

        # 包装方式 + 生产状态
        r5 = tk.Frame(frame, bg='white')
        r5.grid(row=5, column=0, columnspan=4, sticky='ew', padx=10, pady=5)

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

        # 初始化生产日期
        self.production_date.insert(0, datetime.now().strftime("%Y%m%d"))

    # ===================================================================
    #  集成设备信息
    # ===================================================================
    def build_device_info_group(self, parent):
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
            lbl = self._label(frame, label)
            lbl.grid(row=i, column=0, sticky='e', padx=(10, 3), pady=2)
            e = self._entry(frame, readonly=True)
            e.grid(row=i, column=1, sticky='ew', padx=(0, 10), pady=2)
            setattr(self, attr, e)

        # 数值行
        val_rows = [
            ("产线运行时间：", "00时00分", 'runtime_label'),
            ("当前识别数量：", "0", 'current_load_label'),
            ("识别总量：", "0", 'total_label'),
        ]
        for i, (label, val, attr) in enumerate(val_rows):
            r = i + len(rows)
            self._label(frame, label).grid(row=r, column=0, sticky='e', padx=(10, 3), pady=2)
            lb = self._label_value(frame, val)
            lb.grid(row=r, column=1, sticky='w', padx=(0, 10), pady=2)
            setattr(self, attr, lb)

        # 生产总量 — 绿色
        r = len(rows) + len(val_rows)
        self._label(frame, "生产总量：").grid(row=r, column=0, sticky='e', padx=(10, 3), pady=2)
        self.production_total_label = self._label_value(frame, "0", fg='#27ae60')
        self.production_total_label.grid(row=r, column=1, sticky='w', padx=(0, 10), pady=2)

    # ===================================================================
    #  北斗信息
    # ===================================================================
    def build_beidou_group(self, parent):
        frame = self._labelframe(parent, "北斗信息")
        frame.pack(fill='x', pady=(0, 10))
        frame.columnconfigure(0, weight=0)
        frame.columnconfigure(1, weight=1)

        rows = [
            ("北斗ID：", 'beidou_id'),
            ("当前北斗时间：", 'beidou_time'),
            ("北斗位置：", 'beidou_location'),
        ]
        for i, (label, attr) in enumerate(rows):
            self._label(frame, label).grid(row=i, column=0, sticky='e', padx=(10, 3), pady=2)
            e = self._entry(frame, readonly=True)
            e.grid(row=i, column=1, sticky='ew', padx=(0, 10), pady=2)
            setattr(self, attr, e)

    # ===================================================================
    #  RFID控制
    # ===================================================================
    def build_rfid_group(self, parent):
        frame = self._labelframe(parent, "RFID控制")
        frame.pack(fill='x', pady=(0, 10))
        frame.columnconfigure(0, weight=0)
        frame.columnconfigure(1, weight=1)

        rows = [
            ("天线号：", 'antenna_edit'),
            ("功率(dBm)：", 'power_edit'),
            ("频点：", 'frequency_edit'),
        ]
        for i, (label, attr) in enumerate(rows):
            self._label(frame, label).grid(row=i, column=0, sticky='e', padx=(10, 3), pady=2)
            e = self._entry(frame)
            e.grid(row=i, column=1, sticky='ew', padx=(0, 10), pady=2)
            setattr(self, attr, e)

        # 控制按钮
        btn_frame = tk.Frame(frame, bg='white')
        btn_frame.grid(row=len(rows), column=0, columnspan=2, sticky='ew', padx=10, pady=8)

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
        self.debug_text.tag_config("error", foreground="#f44336")
        self.debug_text.tag_config("warning", foreground="#ff9800")
        self.debug_text.tag_config("info", foreground="#4CAF50")
        self.debug_text.tag_config("debug", foreground="#2196F3")

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

    def log(self, message: str, level: str = "info"):
        timestamp = time.strftime("%H:%M:%S")
        self.debug_text.configure(state='normal')
        self.debug_text.insert('end', f"[{timestamp}] [{level.upper()}] ", ())
        self.debug_text.insert('end', f"{message}\n", (level,))
        self.debug_text.see('end')
        self.debug_text.configure(state='disabled')
        lines = int(self.debug_text.index('end-1c').split('.')[0])
        if lines > 500:
            self.debug_text.delete('1.0', '100.0')

    def update_barcode(self, text): self._set_entry('barcode_edit', text)
    def update_tid(self, text): self._set_entry('tid_edit', text)
    def update_epc(self, text): self._set_entry('epc_edit', text)
    def update_pending_code(self, text): self._set_entry('pending_code_edit', text)
    def update_license(self, text): self._set_entry('license_number', text)
    def update_production_code(self, text): self._set_entry('production_line_code', text)
    def update_beidou_time(self, text): self._set_entry('beidou_time', text)
    def update_beidou_location(self, text): self._set_entry('beidou_location', text)

    def update_runtime(self, text): self.runtime_label.configure(text=text)
    def update_current_load(self, count): self.current_load_label.configure(text=str(count))
    def update_total_identified(self, count): self.total_label.configure(text=str(count))
    def update_production_total(self, count): self.production_total_label.configure(text=str(count))

    def set_cargo_in(self): self.state_var.set("cargo_in")
    def set_cargo_out(self): self.state_var.set("cargo_out")

    def _set_editable_entry(self, attr, text):
        e = getattr(self, attr, None)
        if e: e.delete(0, 'end'); e.insert(0, str(text))

    def set_product_types(self, names): pass  # tkinter Entry, not Combo
    def set_manufacturers(self, names): pass
    def set_type_box_items(self, items): pass
    def set_weight_items(self, items): pass

    def get_manufacturer_name(self): return self.manufacturer_edit.get()
    def get_product_name(self): return self.product_type.get()
    def get_production_date(self): return self.production_date.get()
    def get_batch_number(self): return self.batch_number.get()
    def get_package_number(self): return self.package_number.get()
    def is_box_package(self): return self.pkg_var.get() == "box"
    def get_type_box(self): return self.type_box.get()
    def get_weight(self): return self.weight_box.get()

    def get_rfid_params(self):
        return {'antenna': self.antenna_edit.get(),
                'power': self.power_edit.get(),
                'frequency': self.frequency_edit.get()}

    def set_rfid_params(self, antenna, power, frequency):
        self._set_editable_entry('antenna_edit', antenna)
        self._set_editable_entry('power_edit', power)
        self._set_editable_entry('frequency_edit', frequency)

    def show(self):
        if self._owns_root:
            self.root.mainloop()
    def run(self): self.show()


# ===================== 测试入口 =====================
if __name__ == "__main__":
    win = MainWindow()
    win._set_editable_entry('manufacturer_edit', "XX化工有限公司")
    win._set_editable_entry('product_type', "乳化炸药")
    win._set_editable_entry('type_box', "Φ32mm×200g")
    win._set_editable_entry('weight_box', "200g")
    win._set_editable_entry('batch_number', "B001")
    win._set_editable_entry('package_number', "0001")
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
