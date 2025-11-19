import customtkinter as ctk
import yfinance as yf
import threading
import json
import os
import sys
import traceback
import webbrowser
import pandas as pd
import numpy as np
import requests
from PIL import Image
from io import BytesIO

# --- Configuration ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

DATA_FILE = "titan_watchlist.json"

# --- Scoring & Logic Engine ---
class TitanLogic:
    @staticmethod
    def calculate_score(info):
        score = 0
        max_score = 0
        flags = []
        breakdown = [] 

        def get(key, default=0):
            val = info.get(key)
            return val if val is not None else default

        def add_points(category, points, reason, description=""):
            nonlocal score, max_score
            max_score += category
            if points > 0:
                score += points
                # CK3 Style: Icon, Title, Description
                breakdown.append(f"✅ {reason} (+{points})\n    └ {description}")
            else:
                breakdown.append(f"⚪ {reason} (0)\n    └ {description}")

        # --- 1. QUALITY (Moat & Efficiency) ---
        breakdown.append("--- 🛡️ MOAT & QUALITY ---")
        
        roe = get('returnOnEquity', 0) * 100
        if roe > 20: add_points(20, 20, "Elite ROE", f"Return on Equity is {roe:.1f}%, showing elite capital efficiency.")
        elif roe > 12: add_points(20, 12, "Solid ROE", f"ROE is {roe:.1f}%, which is respectable.")
        else: add_points(20, 0, "Weak ROE", f"ROE of {roe:.1f}% suggests inefficient use of capital.")
        
        op_margin = get('operatingMargins', 0) * 100
        if op_margin > 20: add_points(10, 10, "High Margins", f"Operating Margin of {op_margin:.1f}% indicates pricing power.")
        elif op_margin > 10: add_points(10, 5, "Decent Margins", f"Operating Margin is {op_margin:.1f}%.")
        else: add_points(10, 0, "Low Margins", f"Razor thin margins of {op_margin:.1f}%.")

        # --- 2. SAFETY (Fortress) ---
        breakdown.append("\n--- 🏰 FINANCIAL FORTRESS ---")
        
        debt_eq = get('debtToEquity', 1000)
        if debt_eq < 50: add_points(15, 15, "Fortress Balance Sheet", f"Debt/Equity is only {debt_eq:.0f}%. Minimal leverage.")
        elif debt_eq < 100: add_points(15, 10, "Manageable Debt", f"Debt/Equity is {debt_eq:.0f}%. Standard leverage.")
        else: 
            add_points(15, 0, "High Leverage", f"Debt/Equity is {debt_eq:.0f}%. Risk in high rate environments.")
            if debt_eq > 200: flags.append(f"High Debt/Eq ({debt_eq:.0f}%)")

        current_ratio = get('currentRatio', 0)
        if current_ratio > 1.5: add_points(15, 15, "High Liquidity", f"Current Ratio {current_ratio:.2f}x. Can pay short term debts easily.")
        elif current_ratio > 1.0: add_points(15, 10, "Safe Liquidity", f"Current Ratio {current_ratio:.2f}x.")
        else: 
            add_points(15, 0, "Liquidity Crunch", f"Current Ratio {current_ratio:.2f}x. Liabilities exceed assets.")
            if current_ratio < 0.8: flags.append(f"Liquidity Risk ({current_ratio:.2f}x)")

        # --- 3. VALUATION ---
        breakdown.append("\n--- ⚡ VALUATION ---")
        
        # Manual PEG Fallback
        peg = get('pegRatio', 0)
        if peg == 0 or peg is None: 
            pe = get('trailingPE', 0)
            growth = get('earningsGrowth', 0)
            if pe > 0 and growth > 0: peg = pe / (growth * 100)
        
        if 0 < peg < 1.0: add_points(20, 20, "Undervalued Growth", f"PEG {peg:.2f} implies growth is cheap.")
        elif 0 < peg < 1.5: add_points(20, 15, "Fair Value", f"PEG {peg:.2f} is reasonable.")
        elif peg < 2.5: add_points(20, 5, "Premium Pricing", f"PEG {peg:.2f} is expensive.")
        else: 
            add_points(20, 0, "Overvalued", f"PEG {peg:.2f} is very high.")
            if peg > 4.0: flags.append(f"Extreme Valuation (PEG {peg:.2f})")

        # --- 4. MOMENTUM ---
        breakdown.append("\n--- 📈 MOMENTUM ---")
        
        price = get('currentPrice', 0)
        high52 = get('fiftyTwoWeekHigh', price)
        if high52:
            dist = price / high52
            if dist > 0.85: add_points(20, 20, "Strong Trend", "Trading near 52-week highs.")
            elif dist > 0.70: add_points(20, 10, "Consolidating", "Trading within 30% of highs.")
            else: 
                add_points(20, 0, "Downtrend", "Trading >30% below highs (Falling Knife?).")
                flags.append("Weak Momentum")

        final_score = int((score / max_score) * 100) if max_score > 0 else 0
        
        tier = "Speculative"
        if final_score >= 85: tier = "💎 ELITE GEM"
        elif final_score >= 70: tier = "🥇 High Quality"
        elif final_score >= 55: tier = "🥈 Investable"
        elif final_score >= 40: tier = "🥉 Average"
        else: tier = "⚠️ AVOID"

        return final_score, tier, flags, breakdown

    @staticmethod
    def calculate_reverse_dcf(price, fcf_per_share, growth_rate=0.0, discount_rate=0.10, terminal_multiple=15, years=10):
        if fcf_per_share <= 0: return 0
        
        future_values = []
        current_fcf = fcf_per_share
        
        for i in range(1, years + 1):
            current_fcf *= (1 + growth_rate)
            discounted = current_fcf / ((1 + discount_rate) ** i)
            future_values.append(discounted)
        
        # Terminal Value
        terminal_val = (current_fcf * terminal_multiple) / ((1 + discount_rate) ** years)
        intrinsic_value = sum(future_values) + terminal_val
        return intrinsic_value

# --- CUSTOM TOOLTIP (CK3 Style) ---
class ToolTip(object):
    def __init__(self, widget):
        self.widget = widget
        self.tipwindow = None
        self.text = ""

    def showtip(self, text):
        self.text = text
        if self.tipwindow or not self.text:
            return
        x, y, cx, cy = self.widget.bbox("insert")
        x = x + self.widget.winfo_rootx() + 25
        y = y + self.widget.winfo_rooty() + 25
        
        self.tipwindow = tw = ctk.CTkToplevel(self.widget)
        tw.wm_overrideredirect(1) 
        tw.wm_geometry("+%d+%d" % (x, y))
        
        frame = ctk.CTkFrame(tw, fg_color="#0f172a", border_width=1, border_color="#38bdf8", corner_radius=6)
        frame.pack()
        
        label = ctk.CTkLabel(frame, text=self.text, justify='left',
                           font=("Consolas", 11), text_color="#e2e8f0", wraplength=400)
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

# --- UI Components ---
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

class TitanApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("TITAN QUANT TERMINAL")
        self.geometry("1200x700") # Lowered height
        
        self.watchlist = self.load_watchlist()
        self.history = ["NVDA", "MSFT", "AAPL", "TSLA", "GOOG", "AMZN", "META"]
        self.current_ticker = None
        self.current_info = None
        self.breakdown_text = "No Analysis Loaded"
        self.logo_image = None

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # --- SIDEBAR ---
        self.sidebar = ctk.CTkFrame(self, width=260, corner_radius=0, fg_color="#0f172a")
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="ns")
        ctk.CTkLabel(self.sidebar, text="TITAN WATCHLIST", font=("Arial", 14, "bold"), text_color="#38bdf8").pack(pady=(20, 10))
        self.scroll_watch = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent")
        self.scroll_watch.pack(fill="both", expand=True, padx=5)
        self.refresh_watchlist_ui()

        # --- TOP BAR ---
        self.top_bar = ctk.CTkFrame(self, height=60, fg_color="#1e293b", corner_radius=0)
        self.top_bar.grid(row=0, column=1, sticky="ew")
        self.search_var = ctk.StringVar()
        self.combo_search = ctk.CTkComboBox(self.top_bar, width=300, variable=self.search_var, values=self.history)
        self.combo_search.pack(side="left", padx=20, pady=15)
        self.combo_search.bind("<Return>", lambda e: self.start_analysis())
        self.btn_analyze = ctk.CTkButton(self.top_bar, text="ANALYZE", width=100, command=self.start_analysis, fg_color="#2563eb", hover_color="#1d4ed8")
        self.btn_analyze.pack(side="left", padx=5)
        self.btn_verify = ctk.CTkButton(self.top_bar, text="Verify Data ↗", width=100, fg_color="#334155", command=self.open_verification)
        self.btn_verify.pack(side="right", padx=20)

        # --- MAIN DASHBOARD ---
        self.main_panel = ctk.CTkFrame(self, fg_color="#020617", corner_radius=0)
        self.main_panel.grid(row=1, column=1, sticky="nsew")
        
        # Header Info
        self.info_frame = ctk.CTkFrame(self.main_panel, fg_color="transparent")
        self.info_frame.pack(fill="x", padx=30, pady=15)
        
        # Logo & Ticker
        self.header_left = ctk.CTkFrame(self.info_frame, fg_color="transparent")
        self.header_left.pack(side="left")
        
        self.lbl_logo = ctk.CTkLabel(self.header_left, text="")
        self.lbl_logo.pack(side="left", padx=(0, 15))
        
        self.title_box = ctk.CTkFrame(self.header_left, fg_color="transparent")
        self.title_box.pack(side="left")
        self.lbl_ticker = ctk.CTkLabel(self.title_box, text="---", font=("Arial", 32, "bold"))
        self.lbl_ticker.pack(anchor="w")
        self.lbl_price = ctk.CTkLabel(self.title_box, text="$0.00", font=("Consolas", 24), text_color="#38bdf8")
        self.lbl_price.pack(anchor="w")

        # Score Container
        self.score_container = ctk.CTkFrame(self.info_frame, fg_color="#1e293b", corner_radius=10, height=80, width=250)
        self.score_container.pack(side="right")
        self.score_container.pack_propagate(False) 
        self.lbl_score = ctk.CTkLabel(self.score_container, text="0", font=("Arial", 40, "bold"))
        self.lbl_score.place(relx=0.3, rely=0.5, anchor="center")
        self.lbl_tier = ctk.CTkLabel(self.score_container, text="NO DATA", font=("Arial", 14, "bold"), text_color="gray")
        self.lbl_tier.place(relx=0.7, rely=0.5, anchor="center")
        
        CreateToolTip(self.score_container, lambda: self.breakdown_text)
        CreateToolTip(self.lbl_score, lambda: self.breakdown_text)

        self.btn_save = ctk.CTkButton(self.info_frame, text="Add to Watchlist", command=self.add_to_watchlist, state="disabled", fg_color="#059669", width=120)
        self.btn_save.place(relx=1.0, rely=1.2, anchor="ne") # Floating button

        # Tabs
        self.tabs = ctk.CTkTabview(self.main_panel, fg_color="transparent", border_width=0, text_color="#94a3b8", segmented_button_selected_color="#2563eb")
        self.tabs.pack(fill="both", expand=True, padx=20, pady=0)
        self.tab_overview = self.tabs.add("Overview")
        self.tab_deep = self.tabs.add("Deep Dive")
        self.tab_vs = self.tabs.add("VS Mode")
        self.tab_dcf = self.tabs.add("Reverse DCF")
        self.tab_insiders = self.tabs.add("Insiders")

        self.cards = {}
        self.create_overview_tab()
        self.create_deep_dive_tab()
        self.create_vs_tab()
        self.create_dcf_tab()
        self.create_insiders_tab()
        
        self.lbl_flags = ctk.CTkLabel(self.main_panel, text="", text_color="#ef4444", font=("Arial", 12))
        self.lbl_flags.pack(anchor="w", padx=30, pady=5)

    # --- TAB CREATORS ---
    def create_overview_tab(self):
        metrics = [
            "P/E Ratio", "PEG Ratio", "Forward P/E", "Price/Book",
            "ROE %", "Rev Growth", "Debt/Equity", "Free Cash Flow",
            "Div Yield", "Payout Ratio", "Profit Margin", "Beta"
        ]
        self.create_grid(self.tab_overview, metrics)

    def create_deep_dive_tab(self):
        self.trend_scroll = ctk.CTkScrollableFrame(self.tab_deep, fg_color="transparent")
        self.trend_scroll.pack(fill="both", expand=True)
        self.trend_container = ctk.CTkFrame(self.trend_scroll, fg_color="transparent")
        self.trend_container.pack(fill="x", padx=10)

    def create_vs_tab(self):
        f = ctk.CTkFrame(self.tab_vs, fg_color="transparent")
        f.pack(fill="x", pady=10)
        self.entry_vs = ctk.CTkEntry(f, placeholder_text="Competitors (e.g. AMD, INTC, QCOM)", width=300)
        self.entry_vs.pack(side="left", padx=10)
        self.btn_vs = ctk.CTkButton(f, text="COMPARE ALL", command=self.run_comparison, fg_color="#7c3aed")
        self.btn_vs.pack(side="left")
        self.vs_scroll = ctk.CTkScrollableFrame(self.tab_vs, fg_color="#1e293b", orientation="horizontal")
        self.vs_scroll.pack(fill="both", expand=True, padx=10, pady=10)
        self.vs_container = ctk.CTkFrame(self.vs_scroll, fg_color="transparent")
        self.vs_container.pack(fill="both", expand=True)

    def create_dcf_tab(self):
        f = ctk.CTkFrame(self.tab_dcf, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=20, pady=20)
        ctk.CTkLabel(f, text="Intrinsic Value Calculator", font=("Arial", 20, "bold")).pack(anchor="w", pady=10)
        ctk.CTkLabel(f, text="Defaults are auto-filled based on company financials.", text_color="gray").pack(anchor="w", pady=(0,20))
        self.dcf_inputs = {}
        input_frame = ctk.CTkFrame(f, fg_color="#0f172a")
        input_frame.pack(fill="x", pady=10)
        
        labels = [("Expected Growth %", "10"), ("Discount Rate %", "10"), ("Terminal Multiple", "15")]
        for l, default in labels:
            row = ctk.CTkFrame(input_frame, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=5)
            ctk.CTkLabel(row, text=l, width=150, anchor="w").pack(side="left")
            entry = ctk.CTkEntry(row, width=100)
            entry.insert(0, default)
            entry.pack(side="right")
            self.dcf_inputs[l] = entry

        self.btn_calc_dcf = ctk.CTkButton(f, text="CALCULATE VALUE", command=self.run_dcf, fg_color="#059669", height=40)
        self.btn_calc_dcf.pack(fill="x", pady=20)
        self.lbl_dcf_result = ctk.CTkLabel(f, text="---", font=("Arial", 24, "bold"))
        self.lbl_dcf_result.pack()

    def create_insiders_tab(self):
        # Header Row
        header = ctk.CTkFrame(self.tab_insiders, fg_color="#1e293b", height=30)
        header.pack(fill="x", padx=10, pady=5)
        cols = ["Date", "Insider", "Shares", "Value", "Type"]
        weights = [1, 2, 1, 1, 1]
        for i, c in enumerate(cols):
            lbl = ctk.CTkLabel(header, text=c, font=("Arial", 12, "bold"), text_color="#94a3b8")
            lbl.pack(side="left", expand=True, fill="x")
            
        self.insider_scroll = ctk.CTkScrollableFrame(self.tab_insiders, fg_color="transparent")
        self.insider_scroll.pack(fill="both", expand=True, padx=10)

    def create_grid(self, parent, labels):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="both", expand=True)
        cols = 4
        for i, label in enumerate(labels):
            card = MetricCard(frame, label, "-")
            card.grid(row=i//cols, column=i%cols, padx=8, pady=8, sticky="ew")
            self.cards[label] = card
            frame.grid_columnconfigure(i%cols, weight=1)

    # --- CORE LOGIC ---
    def start_analysis(self, ticker=None):
        if not ticker: ticker = self.combo_search.get().upper().strip()
        if not ticker: return
        if ticker not in self.history:
            self.history.insert(0, ticker)
            self.combo_search.configure(values=self.history)

        self.current_ticker = ticker
        self.btn_analyze.configure(state="disabled", text="Loading...")
        threading.Thread(target=self.fetch_data, args=(ticker,), daemon=True).start()

    def fetch_data(self, ticker):
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            self.current_info = info
            if not info or ('regularMarketPrice' not in info and 'currentPrice' not in info):
                raise Exception("No data found")

            score, tier, flags, breakdown = TitanLogic.calculate_score(info)
            self.breakdown_text = "\n".join(breakdown)
            
            # PEG Fix
            peg_ratio = info.get('pegRatio')
            if not peg_ratio or peg_ratio == 0:
                pe = info.get('trailingPE', 0)
                growth = info.get('earningsGrowth', 0)
                if pe > 0 and growth > 0: peg_ratio = pe / (growth * 100)
                else: peg_ratio = 0

            metrics = {
                "P/E Ratio": f"{info.get('trailingPE', 0):.2f}",
                "PEG Ratio": f"{peg_ratio:.2f}",
                "Forward P/E": f"{info.get('forwardPE', 0):.2f}",
                "Price/Book": f"{info.get('priceToBook', 0):.2f}",
                "ROE %": f"{info.get('returnOnEquity', 0)*100:.1f}%",
                "Rev Growth": f"{info.get('revenueGrowth', 0)*100:.1f}%",
                "Debt/Equity": f"{info.get('debtToEquity', 0):.2f}",
                "Free Cash Flow": self.fmt_num(info.get('freeCashflow', 0)),
                "Div Yield": f"{info.get('dividendYield', 0)*100:.2f}%" if info.get('dividendYield') else "0%",
                "Payout Ratio": f"{info.get('payoutRatio', 0)*100:.1f}%" if info.get('payoutRatio') else "0%",
                "Profit Margin": f"{info.get('profitMargins', 0)*100:.1f}%",
                "Beta": f"{info.get('beta', 0):.2f}"
            }
            
            # Financial Trends
            trends_data = {}
            try:
                fin = stock.financials
                bal = stock.balance_sheet
                cf = stock.cashflow
                if not fin.empty:
                    trends_data['net_income'] = fin.loc['Net Income'].head(3).tolist()[::-1]
                    trends_data['revenue'] = fin.loc['Total Revenue'].head(3).tolist()[::-1]
                if not cf.empty:
                    # Use Free Cash Flow if available, else Op Cash Flow
                    if 'Free Cash Flow' in cf.index:
                        trends_data['fcf'] = cf.loc['Free Cash Flow'].head(3).tolist()[::-1]
                    elif 'Operating Cash Flow' in cf.index:
                        trends_data['fcf'] = cf.loc['Operating Cash Flow'].head(3).tolist()[::-1]
            except: pass

            # Insiders
            insiders_data = []
            try:
                ins = stock.insider_transactions
                if ins is not None and not ins.empty:
                    for index, row in ins.head(15).iterrows():
                        insiders_data.append({
                            "date": str(row['Start Date'].date()) if hasattr(row['Start Date'], 'date') else str(row['Start Date'])[:10],
                            "name": row['Insider'],
                            "shares": f"{int(row['Shares']):,}".replace(",", " "),
                            "value": f"{int(row['Value']):,}".replace(",", " ") if not pd.isna(row['Value']) else "-",
                            "type": row['Text'][:20]
                        })
            except: pass

            # Defaults for DCF
            dcf_defaults = {
                "growth": info.get('earningsGrowth', 0.10) * 100,
                "discount": 10,
                "terminal": min(info.get('trailingPE', 15), 25) # Cap terminal at 25
            }
            if dcf_defaults['growth'] > 20: dcf_defaults['growth'] = 20 # Cap auto-growth
            if dcf_defaults['growth'] < 0: dcf_defaults['growth'] = 5

            # Logo
            logo_img = None
            try:
                domain = info.get('website', '').replace('https://', '').replace('http://', '').replace('www.', '').split('/')[0]
                if domain:
                    url = f"https://logo.clearbit.com/{domain}"
                    resp = requests.get(url, timeout=2)
                    if resp.status_code == 200:
                        pil_img = Image.open(BytesIO(resp.content))
                        pil_img = pil_img.resize((50, 50), Image.Resampling.LANCZOS)
                        logo_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(50, 50))
            except: pass

            data = {
                "ticker": ticker,
                "name": info.get('shortName', 'Unknown'),
                "price": info.get('currentPrice', 0),
                "score": score, "tier": tier, "flags": flags,
                "metrics": metrics,
                "trends": trends_data,
                "insiders": insiders_data,
                "dcf_defaults": dcf_defaults,
                "logo": logo_img
            }
            self.after(0, lambda: self.update_ui(data))
        except Exception:
            print(traceback.format_exc())
            self.after(0, lambda: self.btn_analyze.configure(state="normal", text="ANALYZE"))

    def update_ui(self, data):
        self.current_data = data
        self.btn_analyze.configure(state="normal", text="ANALYZE")
        self.btn_save.configure(state="normal")
        
        self.lbl_ticker.configure(text=f"{data['ticker']} - {data['name']}")
        self.lbl_price.configure(text=f"${data['price']}")
        
        # Logo
        if data['logo']:
            self.lbl_logo.configure(image=data['logo'])
        else:
            self.lbl_logo.configure(image=None, text="")

        # Score
        color = "#ef4444"
        if data['score'] >= 80: color = "#22d3ee"
        elif data['score'] >= 60: color = "#4ade80"
        elif data['score'] >= 40: color = "#facc15"
        self.lbl_score.configure(text=str(data['score']), text_color=color)
        self.lbl_tier.configure(text=data['tier'], text_color=color)
        
        flag_text = " ⚠️ ".join(data['flags']) if data['flags'] else "No Critical Flags Detected"
        self.lbl_flags.configure(text=flag_text)

        # Cards
        for key, val in data['metrics'].items():
            if key in self.cards:
                status = "neutral"
                try:
                    num = float(val.replace('%','').replace(',','').replace('M','').replace('B','').replace('T','').replace('$','').strip())
                    if "PEG" in key:
                        if 0 < num < 1.5: status = "good"
                        elif num > 3: status = "bad"
                    elif "Profit Margin" in key or "ROE" in key:
                        if num > 15: status = "good"
                        elif num < 5: status = "bad"
                    elif "Debt/Equity" in key:
                        if num < 100: status = "good"
                        elif num > 200: status = "bad"
                except: pass
                self.cards[key].set_value(val, status=status)

        # Trends (Expanded Deep Dive)
        for w in self.trend_container.winfo_children(): w.destroy()
        if data['trends']:
            for title, values in data['trends'].items():
                if not values: continue
                row = ctk.CTkFrame(self.trend_container, fg_color="#1e293b")
                row.pack(fill="x", pady=5)
                
                t_map = {'net_income': "Net Income", 'revenue': "Revenue", 'fcf': "Free Cash Flow"}
                display_title = t_map.get(title, title.title())
                
                ctk.CTkLabel(row, text=display_title, width=120, font=("Arial", 12, "bold")).pack(side="left", padx=10)
                
                for v in values:
                    val_str = self.fmt_num(v)
                    ctk.CTkLabel(row, text=val_str, width=100, font=("Consolas", 12)).pack(side="left", padx=5)
                
                # Arrow
                if len(values) > 1:
                    arrow = "↗" if values[-1] > values[0] else "↘"
                    color = "#4ade80" if values[-1] > values[0] else "#ef4444"
                    ctk.CTkLabel(row, text=arrow, text_color=color, font=("Arial", 16, "bold")).pack(side="left", padx=10)
        else:
            ctk.CTkLabel(self.trend_container, text="No trend data available.").pack()

        # Insiders (Formatted)
        for w in self.insider_scroll.winfo_children(): w.destroy()
        if data['insiders']:
            for row_data in data['insiders']:
                row = ctk.CTkFrame(self.insider_scroll, fg_color="transparent")
                row.pack(fill="x", pady=2)
                
                # Grid layout for columns
                ctk.CTkLabel(row, text=row_data['date'], width=80, anchor="w", text_color="gray").pack(side="left", expand=True, fill="x")
                ctk.CTkLabel(row, text=row_data['name'][:20], width=120, anchor="w").pack(side="left", expand=True, fill="x")
                ctk.CTkLabel(row, text=row_data['shares'], width=80, anchor="e", font=("Consolas", 12)).pack(side="left", expand=True, fill="x")
                
                # Value Color
                v_col = "#4ade80" if "Buy" in row_data['type'] or "Award" in row_data['type'] else "#ef4444"
                ctk.CTkLabel(row, text=row_data['value'], width=80, anchor="e", text_color=v_col, font=("Consolas", 12)).pack(side="left", expand=True, fill="x")
                ctk.CTkLabel(row, text=row_data['type'][:15], width=100, anchor="w", text_color="gray").pack(side="left", expand=True, fill="x")

        # DCF Defaults
        defs = data['dcf_defaults']
        self.dcf_inputs["Expected Growth %"].delete(0, "end")
        self.dcf_inputs["Expected Growth %"].insert(0, f"{defs['growth']:.1f}")
        self.dcf_inputs["Terminal Multiple"].delete(0, "end")
        self.dcf_inputs["Terminal Multiple"].insert(0, f"{defs['terminal']:.1f}")

    # --- VS MODE ---
    def run_comparison(self):
        comp_input = self.entry_vs.get().upper()
        if not comp_input or not self.current_ticker: return
        tickers = [t.strip() for t in comp_input.split(',')]
        if self.current_ticker not in tickers: tickers.insert(0, self.current_ticker)
        self.btn_vs.configure(text="Loading...", state="disabled")
        threading.Thread(target=self.fetch_comparison, args=(tickers,), daemon=True).start()

    def fetch_comparison(self, tickers):
        try:
            results = []
            for t in tickers:
                try:
                    info = yf.Ticker(t).info
                    peg = info.get('pegRatio')
                    if not peg:
                         pe = info.get('trailingPE', 0)
                         g = info.get('earningsGrowth', 0)
                         peg = (pe / (g*100)) if g > 0 else 0
                    info['manualPEG'] = peg
                    results.append((t, info))
                except: pass
            
            metrics = [
                ("Market Cap", 'marketCap', True, True),
                ("P/E Ratio", 'trailingPE', False, False),
                ("PEG Ratio", 'manualPEG', False, False),
                ("ROE", 'returnOnEquity', True, False),
                ("Gross Margin", 'grossMargins', True, False),
                ("Rev Growth", 'revenueGrowth', True, False),
                ("Debt/Equity", 'debtToEquity', False, False)
            ]
            self.after(0, lambda: self.render_comparison(results, metrics))
        except:
            print(traceback.format_exc())
        finally:
            self.after(0, lambda: self.btn_vs.configure(text="COMPARE ALL", state="normal"))

    def render_comparison(self, results, metrics):
        for w in self.vs_container.winfo_children(): w.destroy()
        
        # Header Row
        h_frame = ctk.CTkFrame(self.vs_container, fg_color="transparent")
        h_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(h_frame, text="METRIC", width=120, font=("Arial", 12, "bold")).pack(side="left")
        for t, _ in results:
             ctk.CTkLabel(h_frame, text=t, width=100, font=("Arial", 12, "bold"), text_color="#38bdf8").pack(side="left", padx=5)

        for label, key, higher_better, is_large_num in metrics:
            row = ctk.CTkFrame(self.vs_container, fg_color="#0f172a")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=label, width=120, anchor="w", text_color="gray").pack(side="left", padx=10)
            
            vals = []
            for _, info in results: vals.append(info.get(key, 0) or 0)
            best_val = max(vals) if higher_better else min([v for v in vals if v > 0] or [0])

            for i, val in enumerate(vals):
                color = "white"
                if val == best_val and val != 0: color = "#4ade80"
                fmt_val = self.fmt_num(val) if is_large_num else f"{val:.2f}"
                if "ROE" in label or "Margin" in label or "Growth" in label:
                     fmt_val = f"{val*100:.1f}%" if not is_large_num else fmt_val
                ctk.CTkLabel(row, text=fmt_val, width=100, text_color=color, font=("Consolas", 12)).pack(side="left", padx=5)

    def run_dcf(self):
        try:
            if not self.current_info: return
            fcf = self.current_info.get('freeCashflow')
            shares = self.current_info.get('sharesOutstanding')
            if not fcf or not shares:
                self.lbl_dcf_result.configure(text="Missing FCF Data", text_color="red")
                return
            fcf_per_share = fcf / shares
            price = self.current_info.get('currentPrice', 0)
            
            g = float(self.dcf_inputs["Expected Growth %"].get()) / 100
            r = float(self.dcf_inputs["Discount Rate %"].get()) / 100
            term = float(self.dcf_inputs["Terminal Multiple"].get())
            
            val = TitanLogic.calculate_reverse_dcf(price, fcf_per_share, g, r, term)
            if val == 0:
                self.lbl_dcf_result.configure(text="Negative FCF - Cannot Calc", text_color="red")
                return

            upside = ((val - price) / price) * 100
            color = "#4ade80" if val > price else "#ef4444"
            self.lbl_dcf_result.configure(text=f"Intrinsic Value: ${val:.2f} ({upside:+.1f}%)", text_color=color)
        except: self.lbl_dcf_result.configure(text="Error in Calculation", text_color="red")

    def fmt_num(self, num):
        if not num: return "-"
        if num > 1e12: return f"${num/1e12:.2f}T"
        if num > 1e9: return f"${num/1e9:.2f}B"
        if num > 1e6: return f"${num/1e6:.2f}M"
        return f"{num:.0f}"

    def add_to_watchlist(self):
        if not self.current_data: return
        if any(x['ticker'] == self.current_data['ticker'] for x in self.watchlist): return
        self.watchlist.append({"ticker": self.current_data['ticker'], "score": self.current_data['score'], "tier": self.current_data['tier']})
        self.save_watchlist()
        self.refresh_watchlist_ui()

    def refresh_watchlist_ui(self):
        for w in self.scroll_watch.winfo_children(): w.destroy()
        for item in self.watchlist:
            f = ctk.CTkFrame(self.scroll_watch, fg_color="#1e293b")
            f.pack(fill="x", pady=2)
            btn = ctk.CTkButton(f, text=f"{item['ticker']}   {item['score']}", font=("Arial", 12, "bold"), fg_color="transparent", anchor="w", command=lambda t=item['ticker']: self.start_analysis(t))
            btn.pack(side="left", fill="x", expand=True)
            ctk.CTkButton(f, text="×", width=25, fg_color="#ef4444", command=lambda t=item['ticker']: self.del_watchlist(t)).pack(side="right", padx=5)

    def load_watchlist(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r') as f: return json.load(f)
            except: return []
        return []
    def save_watchlist(self):
        with open(DATA_FILE, 'w') as f: json.dump(self.watchlist, f)
    def del_watchlist(self, ticker):
        self.watchlist = [x for x in self.watchlist if x['ticker'] != ticker]
        self.save_watchlist()
        self.refresh_watchlist_ui()
    def open_verification(self):
        if self.current_ticker: webbrowser.open(f"https://finance.yahoo.com/quote/{self.current_ticker}")

if __name__ == "__main__":
    app = TitanApp()
    app.mainloop()