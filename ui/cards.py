import customtkinter as ctk

class MetricCard(ctk.CTkFrame):
    def __init__(self, master, label, value, sub_text="", status="neutral"):
        super().__init__(master, fg_color="#1e293b", corner_radius=8, border_width=1, border_color="#334155")
        self.lbl_title = ctk.CTkLabel(self, text=label, font=("Arial", 11, "bold"), text_color="#cbd5e1")
        self.lbl_title.pack(anchor="w", padx=12, pady=(8,0))
        self.lbl_val = ctk.CTkLabel(self, text=value, font=("Consolas", 18, "bold"), text_color="#ffffff")
        self.lbl_val.pack(anchor="w", padx=12, pady=(0, 2))
        self.lbl_sub = ctk.CTkLabel(self, text=sub_text, font=("Arial", 10), text_color="#94a3b8")
        self.lbl_sub.pack(anchor="w", padx=12, pady=(0,8))

    def set_value(self, val, sub_text="", status="neutral"):
        self.lbl_val.configure(text=val)
        if sub_text: self.lbl_sub.configure(text=sub_text)
        bg, border = "#1e293b", "#334155"
        if status == "good": bg, border = "#064e3b", "#10b981"
        elif status == "bad": bg, border = "#450a0a", "#ef4444"
        elif status == "warning": bg, border = "#422006", "#f59e0b"
        self.configure(fg_color=bg, border_color=border)

class ToolTip(object):
    def __init__(self, widget):
        self.widget = widget
        self.tipwindow = None
        self.text = ""

    def showtip(self, text):
        self.text = text
        if self.tipwindow or not self.text: return
        x, y, cx, cy = self.widget.bbox("insert")
        x = x + self.widget.winfo_rootx() + 25
        y = y + self.widget.winfo_rooty() + 25
        self.tipwindow = tw = ctk.CTkToplevel(self.widget)
        tw.wm_overrideredirect(1)
        tw.wm_geometry("+%d+%d" % (x, y))
        frame = ctk.CTkFrame(tw, fg_color="#0f172a", border_width=1, border_color="#38bdf8", corner_radius=6)
        frame.pack()
        label = ctk.CTkLabel(frame, text=self.text, justify='left', font=("Consolas", 11), text_color="#e2e8f0", wraplength=400)
        label.pack(padx=10, pady=10)

    def hidetip(self):
        tw = self.tipwindow
        self.tipwindow = None
        if tw: tw.destroy()

def CreateToolTip(widget, text_func):
    toolTip = ToolTip(widget)
    def enter(event): toolTip.showtip(text_func())
    def leave(event): toolTip.hidetip()
    widget.bind('<Enter>', enter)
    widget.bind('<Leave>', leave)