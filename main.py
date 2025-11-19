import customtkinter as ctk
import yfinance as yf
import threading
import json
import os
import time
import requests
import pandas as pd
import concurrent.futures
import webbrowser
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from PIL import Image
from io import BytesIO
import re

# --- IMPORTS FROM LOGIC MODULES ---
from logic.fundamentals import TitanFundamentals
from logic.technicals import TitanTechnicals
from logic.sentiment import TitanSentiment
from logic.institutional import TitanInstitutional
from ui.cards import MetricCard, CreateToolTip

# --- CONFIGURATION ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

CACHE_FILE = "titan_cache.json"
WATCHLIST_FILE = "titan_watchlist.json"

# --- COLOR PALETTE ---
C_BG = "#020617"        # Main Background
C_SIDEBAR = "#0f172a"   # Sidebar
C_CARD = "#1e293b"      # Card Background
C_TEXT_MAIN = "#ffffff"
C_TEXT_SUB = "#94a3b8"
C_ACCENT = "#38bdf8"    # Cyan/Blue Accent
C_GREEN = "#4ade80"
C_RED = "#ef4444"
C_YELLOW = "#facc15"

class TitanApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("TITAN QUANT TERMINAL")
        self.geometry("1400x850")
        
        self.watchlist = self.load_json(WATCHLIST_FILE, is_list=True)
        self.cache = self.load_json(CACHE_FILE, is_list=False)
        self.history = ["NVDA", "MSFT", "AAPL", "TSLA", "GOOG"] 
        self.current_data = None
        self.current_logo_tk = None
        self.chart_figure = None

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # --- SIDEBAR ---
        self.sidebar = ctk.CTkFrame(self, width=280, corner_radius=0, fg_color=C_SIDEBAR)
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="ns")
        
        ctk.CTkLabel(self.sidebar, text="TITAN WATCHLIST", font=("Arial", 16, "bold"), text_color=C_ACCENT).pack(pady=(30, 10))
        
        self.btn_refresh_all = ctk.CTkButton(self.sidebar, text="↻ REFRESH ALL", fg_color="#475569", hover_color="#334155", command=self.refresh_all_watchlist)
        self.btn_refresh_all.pack(padx=10, pady=(0, 15), fill="x")

        self.scroll_watch = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent")
        self.scroll_watch.pack(fill="both", expand=True, padx=5)
        self.update_watchlist_ui()

        # --- TOP BAR ---
        self.top_bar = ctk.CTkFrame(self, height=60, fg_color=C_CARD, corner_radius=0)
        self.top_bar.grid(row=0, column=1, sticky="ew")
        
        self.search_var = ctk.StringVar()
        self.combo_search = ctk.CTkComboBox(self.top_bar, width=300, variable=self.search_var, values=self.history, font=("Arial", 14))
        self.combo_search.pack(side="left", padx=20, pady=15)
        self.combo_search.bind("<Return>", lambda e: self.load_ticker(force_refresh=False))
        
        self.btn_analyze = ctk.CTkButton(self.top_bar, text="SEARCH", width=100, command=lambda: self.load_ticker(force_refresh=False), font=("Arial", 12, "bold"))
        self.btn_analyze.pack(side="left", padx=5)
        
        self.btn_force = ctk.CTkButton(self.top_bar, text="⚡ FORCE", width=100, fg_color="#b91c1c", hover_color="#991b1b", command=lambda: self.load_ticker(force_refresh=True))
        self.btn_force.pack(side="right", padx=20)

        self.progress = ctk.CTkProgressBar(self.top_bar, width=200, mode="indeterminate", progress_color=C_ACCENT)
        self.progress.pack(side="left", padx=20)
        self.progress.pack_forget()

        # --- MAIN PANEL ---
        self.main_panel = ctk.CTkFrame(self, fg_color=C_BG, corner_radius=0)
        self.main_panel.grid(row=1, column=1, sticky="nsew")
        
        self.setup_dashboard()
        
    def setup_dashboard(self):
        # 1. Header Area
        self.header_frame = ctk.CTkFrame(self.main_panel, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=30, pady=20)
        
        # Left: Logo & Ticker
        self.comp_info_frame = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.comp_info_frame.pack(side="left", fill="y")

        self.lbl_logo = ctk.CTkLabel(self.comp_info_frame, text="", width=60, height=60) 
        self.lbl_logo.pack(side="left", padx=(0, 20))
        
        self.title_price_frame = ctk.CTkFrame(self.comp_info_frame, fg_color="transparent")
        self.title_price_frame.pack(side="left", anchor="center")
        
        self.lbl_ticker = ctk.CTkLabel(self.title_price_frame, text="---", font=("Arial", 40, "bold"))
        self.lbl_ticker.pack(anchor="w")
        
        # Price Row (Price + Change)
        self.price_row = ctk.CTkFrame(self.title_price_frame, fg_color="transparent")
        self.price_row.pack(anchor="w")
        
        self.lbl_price = ctk.CTkLabel(self.price_row, text="$0.00", font=("Consolas", 28), text_color=C_ACCENT)
        self.lbl_price.pack(side="left")
        
        self.lbl_price_change = ctk.CTkLabel(self.price_row, text="", font=("Consolas", 18, "bold"), padx=15)
        self.lbl_price_change.pack(side="left")

        # Center: Day's Range Widget
        self.range_frame = ctk.CTkFrame(self.header_frame, fg_color=C_CARD, corner_radius=8, height=60)
        self.range_frame.pack(side="left", fill="x", expand=True, padx=40)
        
        ctk.CTkLabel(self.range_frame, text="DAY'S RANGE", font=("Arial", 10, "bold"), text_color="gray").pack(pady=(5,0))
        self.range_bar_frame = ctk.CTkFrame(self.range_frame, fg_color="transparent")
        self.range_bar_frame.pack(fill="x", padx=20, pady=5)
        
        self.lbl_low = ctk.CTkLabel(self.range_bar_frame, text="L: -", font=("Consolas", 12), text_color="#ef4444")
        self.lbl_low.pack(side="left")
        
        self.range_progress = ctk.CTkProgressBar(self.range_bar_frame, height=8, progress_color=C_ACCENT)
        self.range_progress.pack(side="left", fill="x", expand=True, padx=10)
        self.range_progress.set(0.5)
        
        self.lbl_high = ctk.CTkLabel(self.range_bar_frame, text="H: -", font=("Consolas", 12), text_color="#4ade80")
        self.lbl_high.pack(side="left")

        # Right: Score Box
        self.score_box = ctk.CTkFrame(self.header_frame, fg_color=C_CARD, corner_radius=12, width=240, height=140)
        self.score_box.pack(side="right", padx=(20,0))
        self.score_box.pack_propagate(False) 
        
        self.lbl_score = ctk.CTkLabel(self.score_box, text="0", font=("Arial", 70, "bold"))
        self.lbl_score.pack(pady=(10,0))
        self.lbl_tier = ctk.CTkLabel(self.score_box, text="NO DATA", font=("Arial", 18, "bold"))
        self.lbl_tier.pack(pady=(0,5))
        CreateToolTip(self.score_box, lambda: self.current_data.get('breakdown', "No Analysis Loaded") if self.current_data else "No Analysis Loaded")

        # 2. Action Buttons
        self.action_frame = ctk.CTkFrame(self.main_panel, fg_color="transparent")
        self.action_frame.pack(fill="x", padx=30, pady=(0, 10))
        
        self.btn_add_watch = ctk.CTkButton(self.action_frame, text="⭐ Add to Watchlist", command=self.add_to_watchlist, fg_color="#059669", hover_color="#047857", width=140)
        self.btn_add_watch.pack(side="left", padx=5)
        
        self.btn_del_watch = ctk.CTkButton(self.action_frame, text="❌ Remove", command=self.remove_from_watchlist, fg_color=C_RED, hover_color="#b91c1c", width=100)
        self.btn_del_watch.pack(side="left", padx=5)

        # 3. Tabs
        self.tabs = ctk.CTkTabview(self.main_panel, text_color=C_TEXT_SUB, segmented_button_selected_color=C_ACCENT, segmented_button_unselected_color=C_CARD)
        self.tabs.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.tab_chart = self.tabs.add("Chart")
        self.tab_fund = self.tabs.add("Fundamentals")
        self.tab_tech = self.tabs.add("Technicals")
        self.tab_sent = self.tabs.add("Sentiment")
        self.tab_inst = self.tabs.add("Smart Money")
        
        self.create_chart_tab()
        self.create_fund_tab()
        self.create_tech_tab()
        self.create_sent_tab()
        self.create_inst_tab()

    # --- UI CREATORS ---
    def create_chart_tab(self):
        ctrl = ctk.CTkFrame(self.tab_chart, fg_color="transparent")
        ctrl.pack(fill="x", pady=10, padx=10)
        ctk.CTkLabel(ctrl, text="Timescale:", text_color="gray").pack(side="left", padx=5)
        
        periods = [("1D", "1d"), ("5D", "5d"), ("1M", "1mo"), ("3M", "3mo"), ("6M", "6mo"), ("1Y", "1y"), ("2Y", "2y"), ("5Y", "5y"), ("MAX", "max")]
        for label, period in periods:
            ctk.CTkButton(ctrl, text=label, width=50, fg_color=C_CARD, hover_color=C_ACCENT, 
                          command=lambda t=period: self.update_chart(t)).pack(side="left", padx=5)

        self.chart_frame = ctk.CTkFrame(self.tab_chart, fg_color=C_BG)
        self.chart_frame.pack(fill="both", expand=True, padx=10, pady=10)

    def create_fund_tab(self):
        self.fund_cards = {}
        metrics = [
            ("P/E Ratio", "Price to Earnings Ratio. \nHigh > 25: Growth/Expensive\nLow < 15: Value/Cheap"), 
            ("Forward P/E", "Predicted P/E for next 12 months. If lower than trailing P/E, earnings are expected to grow."),
            ("PEG Ratio", "Price/Earnings to Growth. \n< 1.0: Undervalued\n> 2.0: Overvalued"), 
            ("Price/Book", "Stock Price vs Book Value (Net Assets). \n< 1.0: Potentially undervalued."),
            ("Beta", "Volatility measure. \n> 1.0: More volatile than market\n< 1.0: Less volatile/Defensive"),
            ("ROE %", "Return on Equity. \n> 15%: Efficient management"), 
            ("Profit Margin", "Percentage of revenue kept as profit. Higher is better."),
            ("Debt/Equity", "Leverage Ratio. \n< 100%: Generally safe\n> 200%: High risk"), 
            ("Current Ratio", "Short term liquidity. \n> 1.5: Safe\n< 1.0: Liquidity risk"), 
            ("Free Cash Flow", "Cash left after expenses. Crucial for dividends and buybacks."), 
            ("Dividend Yield", "Annual dividend payout as percentage of price.")
        ]
        
        grid = ctk.CTkFrame(self.tab_fund, fg_color="transparent")
        grid.pack(fill="both", expand=True, padx=10, pady=10)
        
        for i, (m, desc) in enumerate(metrics):
            c = MetricCard(grid, m, "-")
            c.grid(row=i//4, column=i%4, padx=10, pady=10, sticky="nsew")
            self.fund_cards[m] = c
            CreateToolTip(c, lambda d=desc: d)
            grid.grid_columnconfigure(i%4, weight=1)
            grid.grid_rowconfigure(i//4, weight=1)

    def create_tech_tab(self):
        split = ctk.CTkFrame(self.tab_tech, fg_color="transparent")
        split.pack(fill="both", expand=True, padx=10, pady=10)
        
        left = ctk.CTkFrame(split, fg_color=C_CARD, corner_radius=8)
        left.pack(side="left", fill="both", expand=True, padx=(0,10))
        
        self.tech_metrics = {}
        tech_items = [
            ("RSI", "Relative Strength Index (14). \n> 70: Overbought (Sell signal)\n< 30: Oversold (Buy signal)"), 
            ("MACD", "Moving Average Convergence Divergence. \nLine > Signal: Bullish\nLine < Signal: Bearish"), 
            ("50 SMA", "50-Day Moving Average. Short-term trend baseline."), 
            ("200 SMA", "200-Day Moving Average. Long-term trend baseline. Price above is Bullish."), 
            ("Upper BB", "Bollinger Band Upper. Price touching this often recoils down."), 
            ("Lower BB", "Bollinger Band Lower. Price touching this often bounces up.")
        ]
        
        for i, (label, desc) in enumerate(tech_items):
            row = ctk.CTkFrame(left, fg_color="transparent")
            row.pack(fill="x", pady=8, padx=15)
            lbl = ctk.CTkLabel(row, text=label, font=("Arial", 14), text_color=C_TEXT_SUB)
            lbl.pack(side="left")
            CreateToolTip(lbl, lambda d=desc: d)
            val = ctk.CTkLabel(row, text="-", font=("Consolas", 16, "bold"), text_color="white")
            val.pack(side="right")
            self.tech_metrics[label] = val

        self.tech_signal_frame = ctk.CTkScrollableFrame(split, label_text="SIGNALS & ANALYSIS", label_font=("Arial", 12, "bold"), fg_color=C_CARD, corner_radius=8)
        self.tech_signal_frame.pack(side="right", fill="both", expand=True)

    def create_sent_tab(self):
        self.sent_header_frame = ctk.CTkFrame(self.tab_sent, fg_color="transparent")
        self.sent_header_frame.pack(fill="x", pady=10)
        self.sent_lbl = ctk.CTkLabel(self.sent_header_frame, text="NO DATA", font=("Arial", 24, "bold"))
        self.sent_lbl.pack()
        self.sent_scroll = ctk.CTkScrollableFrame(self.tab_sent, label_text="LATEST HEADLINES (Click to Read)", label_font=("Arial", 12, "bold"), fg_color="transparent")
        self.sent_scroll.pack(fill="both", expand=True, padx=10, pady=5)

    def create_inst_tab(self):
        self.inst_lbl = ctk.CTkLabel(self.tab_inst, text="NO DATA", font=("Arial", 18, "bold"))
        self.inst_lbl.pack(pady=10)
        self.inst_table_frame = ctk.CTkFrame(self.tab_inst, fg_color="transparent")
        self.inst_table_frame.pack(fill="both", expand=True, padx=10)

    # --- LOGIC ---
    def load_ticker(self, force_refresh=False):
        # Sanitization: Upper case, strip whitespace, remove quotes
        raw_input = self.combo_search.get()
        ticker = raw_input.upper().strip().replace("'", "").replace('"', "")
        
        if not ticker: return
        
        if ticker not in self.history:
            self.history.insert(0, ticker)
            self.combo_search.configure(values=self.history)
        
        self.start_loading()
        
        # Cache Validation
        if not force_refresh and ticker in self.cache:
            data = self.cache[ticker]
            # Critical check: Does this cached data have the new fields?
            if 'change' in data and 'day_low' in data:
                print(f"Loading {ticker} from Cache...")
                self.render_data(data)
                self.update_chart("1y")
                self.stop_loading()
                return
            else:
                print(f"Cache invalid for {ticker} (missing new fields). Refreshing...")
        
        threading.Thread(target=self.fetch_data, args=(ticker,), daemon=True).start()

    def start_loading(self):
        self.btn_analyze.configure(state="disabled", text="...")
        self.btn_force.configure(state="disabled")
        self.progress.pack(side="left", padx=20)
        self.progress.start()

    def stop_loading(self):
        self.btn_analyze.configure(state="normal", text="SEARCH")
        self.btn_force.configure(state="normal")
        self.progress.stop()
        self.progress.pack_forget()

    def fetch_data(self, ticker):
        try:
            print(f"Fetching {ticker}...")
            stock = yf.Ticker(ticker)
            
            # Parallel Fetching
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future_info = executor.submit(lambda: stock.info)
                future_tech = executor.submit(TitanTechnicals.analyze, ticker)
                future_sent = executor.submit(TitanSentiment.analyze, ticker)
                future_inst = executor.submit(TitanInstitutional.analyze, ticker)
                
                info = future_info.result()
                # Robust check for data existence
                if not info or ('regularMarketPrice' not in info and 'currentPrice' not in info): 
                    raise Exception(f"No data found for {ticker}")
                
                fund_score, fund_tier, flags, breakdown = TitanFundamentals.calculate_score(info)
                tech = future_tech.result()
                sent = future_sent.result()
                inst = future_inst.result()
            
            # Price & Change Calculation
            current = info.get('currentPrice', info.get('regularMarketPrice', 0))
            prev_close = info.get('previousClose', current)
            
            # Safety defaults
            if current is None: current = 0
            if prev_close is None: prev_close = current
            
            change = current - prev_close
            pct_change = (change / prev_close) * 100 if prev_close != 0 else 0
            
            # Day Range
            day_low = info.get('dayLow', current)
            day_high = info.get('dayHigh', current)

            # PEG Fix
            peg = info.get('pegRatio')
            if (not peg or peg == 0):
                pe = info.get('trailingPE', 0)
                g = info.get('earningsGrowth', 0)
                peg = pe / (g*100) if (g and g!=0) else 0

            data = {
                "ticker": ticker,
                "name": info.get('shortName', 'Unknown'),
                "price": current,
                "change": change,
                "pct_change": pct_change,
                "day_low": day_low,
                "day_high": day_high,
                "score": fund_score,
                "tier": fund_tier,
                "breakdown": "\n".join(breakdown),
                "metrics": {
                    "P/E Ratio": info.get('trailingPE', 0),
                    "Forward P/E": info.get('forwardPE', 0),
                    "PEG Ratio": peg,
                    "Price/Book": info.get('priceToBook', 0),
                    "Beta": info.get('beta', 0),
                    "ROE %": info.get('returnOnEquity', 0),
                    "Profit Margin": info.get('profitMargins', 0),
                    "Debt/Equity": info.get('debtToEquity', 0),
                    "Current Ratio": info.get('currentRatio', 0),
                    "Free Cash Flow": info.get('freeCashflow', 0),
                    "Dividend Yield": info.get('dividendYield', 0)
                },
                "tech": tech,
                "sentiment": sent,
                "institutional": inst,
                "website": info.get('website', '')
            }
            
            self.cache[ticker] = data
            self.save_json(CACHE_FILE, self.cache)
            
            self.after(0, lambda: self.render_data(data))
            self.after(0, lambda: self.update_chart("1y"))
            
        except Exception as e:
            print(f"Fetch Error: {e}")
            self.after(0, lambda: ctk.CTkMessagebox(title="Error", message=f"Could not fetch data for {ticker}.\nDetails: {e}", icon="cancel") if 'CTkMessagebox' in globals() else None)
        finally:
            self.after(0, self.stop_loading)

    def render_data(self, data):
        try:
            self.current_data = data
            
            # Header
            self.lbl_ticker.configure(text=f"{data['ticker']}")
            self.lbl_price.configure(text=f"${data['price']:.2f}")
            
            # Price Change Color
            # Use .get() to be safe against old cache files, though fetch_data guarantees keys
            chg = data.get('change', 0)
            pct = data.get('pct_change', 0)
            
            c_chg = C_GREEN if chg >= 0 else C_RED
            sign = "+" if chg >= 0 else ""
            self.lbl_price_change.configure(text=f"{sign}{chg:.2f} ({sign}{pct:.2f}%)", text_color=c_chg)

            # Day Range Bar
            d_low = data.get('day_low', data['price'])
            d_high = data.get('day_high', data['price'])
            
            self.lbl_low.configure(text=f"L: ${d_low:.2f}")
            self.lbl_high.configure(text=f"H: ${d_high:.2f}")
            
            if d_high > d_low:
                progress = (data['price'] - d_low) / (d_high - d_low)
                self.range_progress.set(max(0, min(1, progress)))
            else:
                self.range_progress.set(0.5)

            # Logo
            threading.Thread(target=self.load_logo, args=(data['website'],), daemon=True).start()
            
            # Score
            c_score = C_RED
            if data['score'] >= 80: c_score = "#22d3ee"
            elif data['score'] >= 60: c_score = C_GREEN
            elif data['score'] >= 40: c_score = C_YELLOW
            self.lbl_score.configure(text=str(data['score']), text_color=c_score)
            self.lbl_tier.configure(text=data['tier'], text_color=c_score)
            
            # Fundamentals
            m = data['metrics']
            self.fund_cards["P/E Ratio"].set_value(f"{m.get('P/E Ratio',0):.2f}")
            self.fund_cards["Forward P/E"].set_value(f"{m.get('Forward P/E',0):.2f}")
            self.fund_cards["PEG Ratio"].set_value(f"{m.get('PEG Ratio',0):.2f}", status="good" if 0 < m.get('PEG Ratio',0) < 1.5 else "neutral")
            self.fund_cards["Price/Book"].set_value(f"{m.get('Price/Book',0):.2f}")
            self.fund_cards["Beta"].set_value(f"{m.get('Beta',0):.2f}")
            self.fund_cards["ROE %"].set_value(f"{m.get('ROE %',0)*100:.1f}%")
            self.fund_cards["Profit Margin"].set_value(f"{m.get('Profit Margin',0)*100:.1f}%")
            self.fund_cards["Debt/Equity"].set_value(f"{m.get('Debt/Equity',0):.0f}%")
            self.fund_cards["Current Ratio"].set_value(f"{m.get('Current Ratio',0):.2f}")
            self.fund_cards["Free Cash Flow"].set_value(self.fmt_num(m.get('Free Cash Flow',0)))
            
            d = m.get('Dividend Yield', 0)
            d_val = d if d and d > 0.5 else d * 100 if d else 0
            self.fund_cards["Dividend Yield"].set_value(f"{d_val:.2f}%")

            # Technicals
            if data['tech']:
                t = data['tech']
                self.tech_metrics["RSI"].configure(text=f"{t['rsi']:.1f}", text_color=C_RED if t['rsi']>70 else C_GREEN if t['rsi']<30 else "white")
                self.tech_metrics["MACD"].configure(text=f"{t['macd']:.2f}")
                self.tech_metrics["50 SMA"].configure(text=f"{t['sma50']:.2f}")
                self.tech_metrics["200 SMA"].configure(text=f"{t['sma200']:.2f}")
                self.tech_metrics["Upper BB"].configure(text=f"{t['upper_bb']:.2f}")
                self.tech_metrics["Lower BB"].configure(text=f"{t['lower_bb']:.2f}")
                
                for w in self.tech_signal_frame.winfo_children(): w.destroy()
                from logic.technicals import TitanTechnicals
                for s in t['signals']:
                    frame = ctk.CTkFrame(self.tech_signal_frame, fg_color="transparent")
                    frame.pack(fill="x", pady=5)
                    col = C_RED if "Bear" in s or "Sell" in s or "Death" in s else C_GREEN
                    ctk.CTkLabel(frame, text=s, text_color=col, font=("Arial", 14, "bold")).pack(anchor="w")
                    desc = TitanTechnicals.signal_descriptions.get(s, "Technical signal detected.")
                    ctk.CTkLabel(frame, text=f"└ {desc}", text_color="gray", font=("Arial", 11), wraplength=400, justify="left").pack(anchor="w", padx=15)

            # Sentiment
            if data['sentiment']:
                s = data['sentiment']
                col = C_GREEN if "Bull" in s['rating'] else C_RED if "Bear" in s['rating'] else "white"
                self.sent_lbl.configure(text=f"{s['rating']} (Score: {s['score']:.2f})", text_color=col)
                
                for w in self.sent_scroll.winfo_children(): w.destroy()
                for n in s['headlines']:
                    row = ctk.CTkFrame(self.sent_scroll, fg_color=C_CARD, border_width=1, border_color=n['color'])
                    row.pack(fill="x", pady=4, padx=5)
                    meta = f"{n.get('source', 'News')} • {n.get('date', '')}"
                    if n.get('author') and n.get('author') != "N/A": meta += f" • {n.get('author')}"
                    ctk.CTkLabel(row, text=meta, font=("Arial", 10), text_color="gray").pack(anchor="w", padx=10, pady=(5,0))
                    lbl_t = ctk.CTkLabel(row, text=n['text'], anchor="w", font=("Arial", 12, "bold"), wraplength=650, cursor="hand2")
                    lbl_t.pack(fill="x", padx=10, pady=(0,5))
                    if n.get('link'):
                        lbl_t.bind("<Button-1>", lambda e, url=n['link']: webbrowser.open(url))
                        CreateToolTip(lbl_t, lambda: f"Open: {n['link']}")

            # Institutional
            if data['institutional']:
                i = data['institutional']
                self.inst_lbl.configure(text=f"{i['signal']} (${i['net_flow']/1e6:.1f}M Net)")
                
                for w in self.inst_table_frame.winfo_children(): w.destroy()
                
                show_role = i.get('has_roles', False)
                cols = ["Date", "Type", "Insider", "Shares", "Price", "Value"]
                if show_role: cols.insert(3, "Role")
                
                h_frame = ctk.CTkFrame(self.inst_table_frame, height=30, fg_color="#334155", corner_radius=4)
                h_frame.pack(fill="x", pady=(0,5))
                
                for idx, c in enumerate(cols):
                    ctk.CTkLabel(h_frame, text=c, font=("Arial", 12, "bold"), text_color="white").grid(row=0, column=idx, sticky="ew", padx=2, pady=5)
                    h_frame.grid_columnconfigure(idx, weight=1)
                
                scroll = ctk.CTkScrollableFrame(self.inst_table_frame, fg_color="transparent")
                scroll.pack(fill="both", expand=True)
                
                for r_idx, tx in enumerate(i['transactions']):
                    bg = C_CARD if r_idx % 2 == 0 else "#252f45"
                    row = ctk.CTkFrame(scroll, fg_color=bg, corner_radius=0)
                    row.pack(fill="x")
                    c_val = C_GREEN if tx['type'] == "Buy" else C_RED
                    
                    vals = [tx['date'], tx['type'], tx['insider'][:18]]
                    if show_role: vals.append(tx.get('role', '-')[:15])
                    vals.extend([tx['shares'], tx['price'], tx['value']])
                    
                    for c_idx, val in enumerate(vals):
                        txt_col = c_val if cols[c_idx] == "Type" else "#e2e8f0"
                        ctk.CTkLabel(row, text=str(val), font=("Consolas", 11), text_color=txt_col).grid(row=0, column=c_idx, sticky="ew", padx=2, pady=5)
                        row.grid_columnconfigure(c_idx, weight=1)
        
        except Exception as e:
            print(f"Render Error: {e}")
            import traceback
            traceback.print_exc()

    def load_logo(self, website):
        try:
            if not website: return
            domain = website.replace('https://', '').replace('http://', '').replace('www.', '').split('/')[0]
            url = f"https://logo.clearbit.com/{domain}"
            headers = {'User-Agent': 'Mozilla/5.0'}
            resp = requests.get(url, headers=headers, timeout=2)
            if resp.status_code == 200:
                pil = Image.open(BytesIO(resp.content)).resize((60,60))
                self.current_logo_tk = ctk.CTkImage(pil, size=(60,60)) 
                self.lbl_logo.configure(image=self.current_logo_tk, text="")
        except: pass

    def update_chart(self, period):
        ticker = self.combo_search.get().upper().strip().replace("'", "").replace('"', "")
        if not ticker: return
        
        def _plot():
            try:
                for widget in self.chart_frame.winfo_children(): widget.destroy()
                if self.chart_figure: plt.close(self.chart_figure)

                interval = "1d"
                if period in ["1d", "5d"]: interval = "15m"
                elif period in ["1mo", "3mo"]: interval = "1d"
                elif period in ["6mo", "1y", "2y"]: interval = "1d"
                else: interval = "1wk"

                data = yf.Ticker(ticker).history(period=period, interval=interval)
                if data.empty: 
                    ctk.CTkLabel(self.chart_frame, text=f"No Data for {period}").pack(expand=True)
                    return

                fig = plt.Figure(figsize=(5, 4), dpi=100, facecolor=C_BG)
                ax = fig.add_subplot(111)
                ax.set_facecolor(C_BG)
                
                ax.plot(data.index, data['Close'], color=C_ACCENT, linewidth=1.5)
                ax.fill_between(data.index, data['Close'], alpha=0.1, color=C_ACCENT)
                
                ax.grid(True, color="#334155", linestyle='--', alpha=0.3)
                ax.tick_params(axis='x', colors='gray', rotation=0, labelsize=8)
                ax.tick_params(axis='y', colors='gray', labelsize=8)
                for spine in ax.spines.values(): spine.set_visible(False)

                canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
                canvas.draw()
                canvas.get_tk_widget().pack(fill="both", expand=True)
                self.chart_figure = fig

            except Exception as e: print(f"Chart Error: {e}")

        threading.Thread(target=_plot, daemon=True).start()

    # --- UTILS ---
    def load_json(self, filename, is_list=True):
        if os.path.exists(filename):
            try: 
                with open(filename, 'r') as f: return json.load(f)
            except: pass
        return [] if is_list else {}

    def save_json(self, filename, data):
        with open(filename, 'w') as f: json.dump(data, f)

    def fmt_num(self, num):
        if not num: return "-"
        if num > 1e9: return f"${num/1e9:.2f}B"
        return f"${num/1e6:.0f}M"

    # Watchlist Wrappers
    def add_to_watchlist(self):
        if not self.current_data: return
        ticker = self.current_data['ticker']
        if any(x['ticker'] == ticker for x in self.watchlist): return
        self.watchlist.append({"ticker": ticker, "score": self.current_data['score']})
        self.save_json(WATCHLIST_FILE, self.watchlist)
        self.update_watchlist_ui()

    def remove_from_watchlist(self):
        if not self.current_data: return
        ticker = self.current_data['ticker']
        self.watchlist = [x for x in self.watchlist if x['ticker'] != ticker]
        self.save_json(WATCHLIST_FILE, self.watchlist)
        self.update_watchlist_ui()

    def update_watchlist_ui(self):
        for w in self.scroll_watch.winfo_children(): w.destroy()
        for item in self.watchlist:
            sc = item.get('score', 0)
            col = C_GREEN if sc >= 60 else C_RED if sc < 40 else C_YELLOW
            f = ctk.CTkFrame(self.scroll_watch, fg_color="transparent")
            f.pack(fill="x", pady=1)
            btn = ctk.CTkButton(f, text=f"{item['ticker']}", command=lambda t=item['ticker']: self.load_ticker_from_watch(t), fg_color=C_CARD, anchor="w", height=35, font=("Arial", 12, "bold"))
            btn.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(f, text=str(sc), width=30, fg_color=col, text_color="black", corner_radius=4).pack(side="right", padx=(5,0))

    def load_ticker_from_watch(self, ticker):
        self.combo_search.set(ticker)
        self.load_ticker()

    def refresh_all_watchlist(self):
        self.btn_refresh_all.configure(state="disabled", text="Refreshing...")
        threading.Thread(target=self._refresh_thread, daemon=True).start()

    def _refresh_thread(self):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {executor.submit(self._fetch_score_only, item['ticker']): item for item in self.watchlist}
            for future in concurrent.futures.as_completed(futures):
                try:
                    res = future.result()
                    if res: futures[future]['score'] = res
                except: pass
        self.save_json(WATCHLIST_FILE, self.watchlist)
        self.after(0, self.update_watchlist_ui)
        self.after(0, lambda: self.btn_refresh_all.configure(state="normal", text="↻ REFRESH ALL"))

    def _fetch_score_only(self, ticker):
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            score, _, _, _ = TitanFundamentals.calculate_score(info)
            return score
        except: return None

if __name__ == "__main__":
    app = TitanApp()
    app.mainloop()