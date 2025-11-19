import customtkinter as ctk
import yfinance as yf
import threading
import json
import os
import time
import requests
import pandas as pd
from PIL import Image
from io import BytesIO

# --- IMPORTS FROM LOGIC MODULES ---
# Ensure your logic folders/files are named exactly: logic/fundamentals.py, logic/technicals.py, etc.
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

class TitanApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("TITAN QUANT TERMINAL")
        self.geometry("1400x950")
        
        self.watchlist = self.load_json(WATCHLIST_FILE, is_list=True)
        self.cache = self.load_json(CACHE_FILE, is_list=False)
        self.history = ["NVDA", "MSFT", "AAPL"] 
        self.current_data = None
        self.current_logo_tk = None # Keep reference to prevent garbage collection

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # --- SIDEBAR ---
        self.sidebar = ctk.CTkFrame(self, width=280, corner_radius=0, fg_color="#0f172a")
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="ns")
        
        ctk.CTkLabel(self.sidebar, text="TITAN WATCHLIST", font=("Arial", 16, "bold"), text_color="#38bdf8").pack(pady=(30, 10))
        
        self.btn_refresh_all = ctk.CTkButton(self.sidebar, text="↻ REFRESH ALL", fg_color="#475569", command=self.refresh_all_watchlist)
        self.btn_refresh_all.pack(padx=10, pady=(0, 15), fill="x")

        self.scroll_watch = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent")
        self.scroll_watch.pack(fill="both", expand=True, padx=5)
        self.update_watchlist_ui()

        # --- TOP BAR ---
        self.top_bar = ctk.CTkFrame(self, height=60, fg_color="#1e293b", corner_radius=0)
        self.top_bar.grid(row=0, column=1, sticky="ew")
        
        self.search_var = ctk.StringVar()
        self.combo_search = ctk.CTkComboBox(self.top_bar, width=300, variable=self.search_var, values=self.history)
        self.combo_search.pack(side="left", padx=20, pady=15)
        self.combo_search.bind("<Return>", lambda e: self.load_ticker(force_refresh=False))
        
        self.btn_analyze = ctk.CTkButton(self.top_bar, text="SEARCH", width=100, command=lambda: self.load_ticker(force_refresh=False))
        self.btn_analyze.pack(side="left", padx=5)
        
        self.btn_force = ctk.CTkButton(self.top_bar, text="⚡ FORCE UPDATE", width=120, fg_color="#b91c1c", command=lambda: self.load_ticker(force_refresh=True))
        self.btn_force.pack(side="right", padx=20)

        # --- MAIN PANEL ---
        self.main_panel = ctk.CTkFrame(self, fg_color="#020617", corner_radius=0)
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
        self.lbl_price = ctk.CTkLabel(self.title_price_frame, text="$0.00", font=("Consolas", 28), text_color="#38bdf8")
        self.lbl_price.pack(anchor="w")

        # Right: BIG Score Box
        self.score_box = ctk.CTkFrame(self.header_frame, fg_color="#1e293b", corner_radius=12, width=240, height=140)
        self.score_box.pack(side="right", padx=(20,0))
        self.score_box.pack_propagate(False) 
        
        self.lbl_score = ctk.CTkLabel(self.score_box, text="0", font=("Arial", 70, "bold"))
        self.lbl_score.pack(pady=(10,0))
        self.lbl_tier = ctk.CTkLabel(self.score_box, text="NO DATA", font=("Arial", 18, "bold"))
        self.lbl_tier.pack(pady=(0,5))
        # Tooltip for score breakdown
        CreateToolTip(self.score_box, lambda: self.current_data.get('breakdown', "No Analysis Loaded") if self.current_data else "No Analysis Loaded")

        # 2. Action Buttons
        self.action_frame = ctk.CTkFrame(self.main_panel, fg_color="transparent")
        self.action_frame.pack(fill="x", padx=30, pady=(0, 10))
        
        self.btn_add_watch = ctk.CTkButton(self.action_frame, text="⭐ Add to Watchlist", command=self.add_to_watchlist, fg_color="#059669", width=140)
        self.btn_add_watch.pack(side="left", padx=5)
        
        self.btn_del_watch = ctk.CTkButton(self.action_frame, text="❌ Remove", command=self.remove_from_watchlist, fg_color="#ef4444", width=100)
        self.btn_del_watch.pack(side="left", padx=5)

        # 3. Tabs
        self.tabs = ctk.CTkTabview(self.main_panel)
        self.tabs.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.tab_fund = self.tabs.add("Fundamentals")
        self.tab_tech = self.tabs.add("Technicals")
        self.tab_sent = self.tabs.add("Sentiment")
        self.tab_inst = self.tabs.add("Smart Money")
        
        self.create_fund_tab()
        self.create_tech_tab()
        self.create_sent_tab()
        self.create_inst_tab()

    # --- UI CREATION HELPERS ---
    def create_fund_tab(self):
        self.fund_cards = {}
        # Mapping Metric Names to Descriptions for Tooltips
        metrics = [
            ("P/E Ratio", TitanFundamentals.metric_descriptions["P/E Ratio"]), 
            ("PEG Ratio", TitanFundamentals.metric_descriptions["PEG Ratio"]), 
            ("ROE %", TitanFundamentals.metric_descriptions["ROE %"]), 
            ("Profit Margin", TitanFundamentals.metric_descriptions["Profit Margin"]),
            ("Debt/Equity", TitanFundamentals.metric_descriptions["Debt/Equity"]), 
            ("Current Ratio", TitanFundamentals.metric_descriptions["Current Ratio"]), 
            ("Free Cash Flow", TitanFundamentals.metric_descriptions["Free Cash Flow"]), 
            ("Dividend Yield", TitanFundamentals.metric_descriptions["Dividend Yield"])
        ]
        
        grid = ctk.CTkFrame(self.tab_fund, fg_color="transparent")
        grid.pack(fill="both", expand=True, padx=10, pady=10)
        
        for i, (m, desc) in enumerate(metrics):
            c = MetricCard(grid, m, "-")
            c.grid(row=i//4, column=i%4, padx=10, pady=10, sticky="nsew")
            self.fund_cards[m] = c
            # Add Tooltip to the card
            CreateToolTip(c, lambda d=desc: d)
            grid.grid_columnconfigure(i%4, weight=1)
            grid.grid_rowconfigure(i//4, weight=1)

    def create_tech_tab(self):
        split = ctk.CTkFrame(self.tab_tech, fg_color="transparent")
        split.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Metrics Panel (Left)
        left = ctk.CTkFrame(split, fg_color="#1e293b", corner_radius=8)
        left.pack(side="left", fill="both", expand=True, padx=(0,10))
        
        self.tech_metrics = {}
        # Labels with descriptions
        tech_items = [
            ("RSI", "Momentum: >70 Overbought, <30 Oversold"), 
            ("MACD", "Trend: Line above Signal is Bullish"), 
            ("50 SMA", "Short-term Trend Line"), 
            ("200 SMA", "Long-term Trend Line"), 
            ("Upper BB", "Volatility High Band"), 
            ("Lower BB", "Volatility Low Band")
        ]
        
        for i, (label, desc) in enumerate(tech_items):
            row = ctk.CTkFrame(left, fg_color="transparent")
            row.pack(fill="x", pady=8, padx=15)
            
            lbl = ctk.CTkLabel(row, text=label, font=("Arial", 14), text_color="#cbd5e1")
            lbl.pack(side="left")
            CreateToolTip(lbl, lambda d=desc: d)
            
            val = ctk.CTkLabel(row, text="-", font=("Consolas", 16, "bold"), text_color="white")
            val.pack(side="right")
            self.tech_metrics[label] = val

        # Signals Panel (Right) - Scrollable
        self.tech_signal_frame = ctk.CTkScrollableFrame(split, label_text="SIGNALS & ANALYSIS", fg_color="#1e293b", corner_radius=8)
        self.tech_signal_frame.pack(side="right", fill="both", expand=True)

    def create_sent_tab(self):
        # Score Header
        self.sent_lbl = ctk.CTkLabel(self.tab_sent, text="NO DATA", font=("Arial", 24, "bold"))
        self.sent_lbl.pack(pady=10)
        
        # Debug Panel (To fix the "..." issue)
        self.sent_debug_frame = ctk.CTkScrollableFrame(self.tab_sent, label_text="DEBUG LOG", fg_color="#0f172a", height=100)
        self.sent_debug_frame.pack(fill="x", padx=10, pady=(0, 10))
        self.lbl_sent_debug = ctk.CTkLabel(self.sent_debug_frame, text="waiting...", justify="left", wraplength=800, font=("Consolas", 11), text_color="gray")
        self.lbl_sent_debug.pack(anchor="w", padx=5, pady=5)

        # News List
        self.sent_scroll = ctk.CTkScrollableFrame(self.tab_sent, label_text="HEADLINES", fg_color="transparent")
        self.sent_scroll.pack(fill="both", expand=True, padx=10)

    def create_inst_tab(self):
        self.inst_lbl = ctk.CTkLabel(self.tab_inst, text="NO DATA", font=("Arial", 18, "bold"))
        self.inst_lbl.pack(pady=10)
        
        # Debug Panel
        self.inst_debug_frame = ctk.CTkScrollableFrame(self.tab_inst, label_text="DEBUG LOG", fg_color="#0f172a", height=100)
        self.inst_debug_frame.pack(fill="x", padx=10, pady=(0, 10))
        self.lbl_inst_debug = ctk.CTkLabel(self.inst_debug_frame, text="waiting...", justify="left", wraplength=800, font=("Consolas", 11), text_color="gray")
        self.lbl_inst_debug.pack(anchor="w", padx=5, pady=5)
        
        # Table Header
        h = ctk.CTkFrame(self.tab_inst, height=30, fg_color="#334155")
        h.pack(fill="x", padx=10)
        cols = ["Date", "Type", "Insider", "Shares", "Price", "Value"]
        for c in cols: 
            ctk.CTkLabel(h, text=c, width=100, font=("Arial", 12, "bold")).pack(side="left", expand=True, fill="x")
        
        # Table Body
        self.inst_scroll = ctk.CTkScrollableFrame(self.tab_inst, fg_color="transparent")
        self.inst_scroll.pack(fill="both", expand=True, padx=10)

    # --- DATA LOADING LOGIC ---
    def load_ticker(self, force_refresh=False):
        ticker = self.combo_search.get().upper().strip()
        if not ticker: return
        
        # 1. Check Cache first
        if not force_refresh and ticker in self.cache:
            print(f"Loading {ticker} from Cache...")
            self.render_data(self.cache[ticker])
            return

        # 2. Fetch New Data
        self.btn_analyze.configure(state="disabled", text="Loading...")
        self.btn_force.configure(state="disabled")
        threading.Thread(target=self.fetch_data, args=(ticker,), daemon=True).start()

    def fetch_data(self, ticker):
        try:
            print(f"Fetching {ticker} from Web...")
            stock = yf.Ticker(ticker)
            info = stock.info
            
            if not info or ('currentPrice' not in info and 'regularMarketPrice' not in info): 
                raise Exception(f"Could not fetch data for {ticker}")
            
            # Run Logic Modules
            fund_score, fund_tier, flags, breakdown = TitanFundamentals.calculate_score(info)
            tech = TitanTechnicals.analyze(ticker)
            sent = TitanSentiment.analyze(ticker)
            inst = TitanInstitutional.analyze(ticker)
            
            # Calculate PEG manually if missing
            peg = info.get('pegRatio')
            if (not peg or peg == 0):
                pe = info.get('trailingPE', 0)
                g = info.get('earningsGrowth', 0)
                if pe > 0 and g > 0:
                    peg = pe / (g*100)
                else:
                    peg = 0

            data = {
                "ticker": ticker,
                "name": info.get('shortName', 'Unknown'),
                "price": info.get('currentPrice', info.get('regularMarketPrice', 0)),
                "score": fund_score,
                "tier": fund_tier,
                "breakdown": "\n".join(breakdown),
                "metrics": {
                    "P/E Ratio": info.get('trailingPE', 0),
                    "PEG Ratio": peg,
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
            
            # Save to Cache
            self.cache[ticker] = data
            self.save_json(CACHE_FILE, self.cache)
            
            self.after(0, lambda: self.render_data(data))
            
        except Exception as e:
            print(f"Fetch Error: {e}")
            # On error, re-enable buttons
            self.after(0, lambda: self.btn_analyze.configure(state="normal", text="SEARCH"))
            self.after(0, lambda: self.btn_force.configure(state="normal"))

    def render_data(self, data):
        self.current_data = data
        self.btn_analyze.configure(state="normal", text="SEARCH")
        self.btn_force.configure(state="normal")
        
        # 1. Header
        self.lbl_ticker.configure(text=f"{data['ticker']}")
        self.lbl_price.configure(text=f"${data['price']}")
        
        # Load Logo in Thread
        threading.Thread(target=self.load_logo, args=(data['website'],), daemon=True).start()
        
        # Score Colors
        c = "#ef4444"
        if data['score'] >= 80: c = "#22d3ee"
        elif data['score'] >= 60: c = "#4ade80"
        elif data['score'] >= 40: c = "#facc15"
        self.lbl_score.configure(text=str(data['score']), text_color=c)
        self.lbl_tier.configure(text=data['tier'], text_color=c)
        
        # 2. Fundamentals
        m = data['metrics']
        self.fund_cards["P/E Ratio"].set_value(f"{m.get('P/E Ratio',0):.2f}")
        self.fund_cards["PEG Ratio"].set_value(f"{m.get('PEG Ratio',0):.2f}", status="good" if 0 < m.get('PEG Ratio',0) < 1.5 else "neutral")
        self.fund_cards["ROE %"].set_value(f"{m.get('ROE %',0)*100:.1f}%")
        self.fund_cards["Profit Margin"].set_value(f"{m.get('Profit Margin',0)*100:.1f}%")
        self.fund_cards["Debt/Equity"].set_value(f"{m.get('Debt/Equity',0):.0f}%")
        self.fund_cards["Current Ratio"].set_value(f"{m.get('Current Ratio',0):.2f}")
        self.fund_cards["Free Cash Flow"].set_value(self.fmt_num(m.get('Free Cash Flow',0)))
        div = m.get('Dividend Yield', 0)
        self.fund_cards["Dividend Yield"].set_value(f"{div*100:.2f}%" if div else "0%")

        # 3. Technicals
        if data['tech']:
            t = data['tech']
            self.tech_metrics["RSI"].configure(text=f"{t['rsi']:.1f}", text_color="#ef4444" if t['rsi']>70 else "#4ade80" if t['rsi']<30 else "white")
            self.tech_metrics["MACD"].configure(text=f"{t['macd']:.2f}")
            self.tech_metrics["50 SMA"].configure(text=f"{t['sma50']:.2f}")
            self.tech_metrics["200 SMA"].configure(text=f"{t['sma200']:.2f}")
            self.tech_metrics["Upper BB"].configure(text=f"{t['upper_bb']:.2f}")
            self.tech_metrics["Lower BB"].configure(text=f"{t['lower_bb']:.2f}")
            
            # Detailed Signals
            for w in self.tech_signal_frame.winfo_children(): w.destroy()
            
            # Add explanations for signals
            from logic.technicals import TitanTechnicals # Import descriptions
            
            for s in t['signals']:
                frame = ctk.CTkFrame(self.tech_signal_frame, fg_color="transparent")
                frame.pack(fill="x", pady=5)
                
                col = "#ef4444" if "Bear" in s or "Sell" in s or "Death" in s else "#4ade80"
                
                # Signal Name
                ctk.CTkLabel(frame, text=s, text_color=col, font=("Arial", 14, "bold")).pack(anchor="w")
                
                # Investor Implication (if available)
                desc = TitanTechnicals.signal_descriptions.get(s, "Momentum Signal.")
                ctk.CTkLabel(frame, text=f"└ {desc}", text_color="gray", font=("Arial", 11), wraplength=400, justify="left").pack(anchor="w", padx=15)

        # 4. Sentiment
        if data['sentiment']:
            s = data['sentiment']
            col = "#4ade80" if "Bull" in s['rating'] else "#ef4444" if "Bear" in s['rating'] else "white"
            self.sent_lbl.configure(text=f"{s['rating']} (Score: {s['score']:.2f})", text_color=col)
            
            # Debug Text
            self.lbl_sent_debug.configure(text=s.get('debug', 'No debug info.'))
            
            for w in self.sent_scroll.winfo_children(): w.destroy()
            for n in s['headlines']:
                row = ctk.CTkFrame(self.sent_scroll, fg_color="#1e293b")
                row.pack(fill="x", pady=2)
                ctk.CTkLabel(row, text=n['text'], anchor="w", width=500).pack(side="left", padx=5)
                ctk.CTkLabel(row, text=f"{n['score']:.2f}", text_color=n['color'], width=40).pack(side="right")
                
        # 5. Institutional
        if data['institutional']:
            i = data['institutional']
            self.inst_lbl.configure(text=f"{i['signal']} (${i['net_flow']/1e6:.1f}M Net)")
            
            # Debug Text
            self.lbl_inst_debug.configure(text=i.get('debug', 'No debug info.'))

            for w in self.inst_scroll.winfo_children(): w.destroy()
            for tx in i['transactions']:
                row = ctk.CTkFrame(self.inst_scroll, fg_color="transparent")
                row.pack(fill="x", pady=1)
                
                c = "#4ade80" if tx['type'] == "Buy" else "#ef4444"
                
                # Ensure alignment with headers
                vals = [tx['date'], tx['type'], tx['insider'][:15], tx['shares'], tx['price'], tx['value']]
                for v in vals:
                    ctk.CTkLabel(row, text=str(v), width=100, text_color=c if v == tx['type'] else "white").pack(side="left", expand=True, fill="x")

    def load_logo(self, website):
        try:
            if not website: return
            domain = website.replace('https://', '').replace('http://', '').replace('www.', '').split('/')[0]
            url = f"https://logo.clearbit.com/{domain}"
            headers = {'User-Agent': 'Mozilla/5.0'}
            resp = requests.get(url, headers=headers, timeout=2)
            if resp.status_code == 200:
                pil = Image.open(BytesIO(resp.content)).resize((60,60))
                self.current_logo_tk = ctk.CTkImage(pil, size=(60,60)) # Keep ref
                self.lbl_logo.configure(image=self.current_logo_tk, text="")
        except: pass

    # --- WATCHLIST ---
    def add_to_watchlist(self):
        if not self.current_data: return
        ticker = self.current_data['ticker']
        # Avoid duplicates
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
            btn = ctk.CTkButton(self.scroll_watch, text=f"{item['ticker']} ({item.get('score',0)})", 
                                command=lambda t=item['ticker']: self.load_ticker_from_watch(t),
                                fg_color="#1e293b", anchor="w")
            btn.pack(fill="x", pady=1)

    def load_ticker_from_watch(self, ticker):
        self.combo_search.set(ticker)
        self.load_ticker()

    def refresh_all_watchlist(self):
        self.btn_refresh_all.configure(state="disabled", text="Refreshing...")
        threading.Thread(target=self._refresh_thread, daemon=True).start()

    def _refresh_thread(self):
        for item in self.watchlist:
            # Force fetch (bypass cache) for refresh
            try:
                stock = yf.Ticker(item['ticker'])
                info = stock.info
                score, _, _, _ = TitanFundamentals.calculate_score(info)
                item['score'] = score # Update score in watchlist
                time.sleep(0.5)
            except: pass
        
        self.save_json(WATCHLIST_FILE, self.watchlist)
        self.after(0, self.update_watchlist_ui)
        self.after(0, lambda: self.btn_refresh_all.configure(state="normal", text="↻ REFRESH ALL"))

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

if __name__ == "__main__":
    app = TitanApp()
    app.mainloop()