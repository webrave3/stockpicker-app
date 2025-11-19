import yfinance as yf
import pandas as pd
import numpy as np

class TitanTechnicals:
    # This dictionary is required by main.py for signal descriptions
    signal_descriptions = {
        "🔥 RSI Overbought (>70)": "RSI above 70 suggests the stock may be overbought and due for a pullback. Investors might consider trimming positions or waiting for a better entry.",
        "🧊 RSI Oversold (<30)": "RSI below 30 suggests the stock may be oversold and due for a rebound. This could indicate a potential buying opportunity for contrarian investors.",
        "📈 Bullish Trend (>200 SMA)": "Price trading above the 200-day Simple Moving Average indicates a strong long-term uptrend. This often signals a healthy, growing company.",
        "📉 Bearish Trend (<200 SMA)": "Price trading below the 200-day Simple Moving Average indicates a long-term downtrend. Investors should exercise caution as the stock lacks upward momentum.",
        "✨ Golden Cross Active": "The 50-day SMA crossing above the 200-day SMA. A strong bullish signal often indicating the start of a new long-term uptrend.",
        "☠️ Death Cross Active": "The 50-day SMA crossing below the 200-day SMA. A strong bearish signal often indicating the start of a new long-term downtrend.",
        "⚠️ Price above Upper Band (Stretch)": "Price trading above the upper Bollinger Band. This can indicate that the stock is becoming overextended and might pull back towards the mean.",
        "✅ Price below Lower Band (Dip)": "Price trading below the lower Bollinger Band. This can indicate that the stock is oversold and might bounce back towards the mean.",
        "🟢 MACD Buy Signal": "MACD line crossing above the Signal line. A bullish crossover often used as a buy signal, indicating increasing upward momentum.",
        "🔴 MACD Sell Signal": "MACD line crossing below the Signal line. A bearish crossover often used as a sell signal, indicating increasing downward momentum."
    }

    @staticmethod
    def calculate_rsi(series, period=14):
        delta = series.diff(1)
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def analyze(ticker_symbol):
        try:
            stock = yf.Ticker(ticker_symbol)
            df = stock.history(period="1y")
            if df.empty or len(df) < 200: return None
            
            close = df['Close']

            # --- 1. Indicators ---
            rsi = TitanTechnicals.calculate_rsi(close, 14).iloc[-1]
            sma50 = close.rolling(window=50).mean().iloc[-1]
            sma200 = close.rolling(window=200).mean().iloc[-1]
            
            # Bollinger Bands (20, 2)
            sma20 = close.rolling(window=20).mean()
            std20 = close.rolling(window=20).std()
            upper_bb = (sma20 + (std20 * 2)).iloc[-1]
            lower_bb = (sma20 - (std20 * 2)).iloc[-1]
            
            # MACD (12, 26, 9)
            ema12 = close.ewm(span=12, adjust=False).mean()
            ema26 = close.ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            macd_val = macd_line.iloc[-1]
            signal_val = signal_line.iloc[-1]

            current_price = close.iloc[-1]

            # --- 2. Logic & Signals ---
            signals = []
            
            # RSI
            if rsi > 70: signals.append("🔥 RSI Overbought (>70)")
            elif rsi < 30: signals.append("🧊 RSI Oversold (<30)")

            # Trend (SMA)
            if current_price > sma200: signals.append("📈 Bullish Trend (>200 SMA)")
            else: signals.append("📉 Bearish Trend (<200 SMA)")
            
            # Crosses
            if sma50 > sma200: signals.append("✨ Golden Cross Active")
            elif sma50 < sma200: signals.append("☠️ Death Cross Active")

            # Bollinger
            if current_price > upper_bb: signals.append("⚠️ Price above Upper Band (Stretch)")
            elif current_price < lower_bb: signals.append("✅ Price below Lower Band (Dip)")

            # MACD
            if macd_val > signal_val: signals.append("🟢 MACD Buy Signal")
            else: signals.append("🔴 MACD Sell Signal")

            # Overall Status
            bull_score = sum([1 for s in signals if "Bullish" in s or "Buy" in s or "Golden" in s or "Oversold" in s or "Dip" in s])
            bear_score = sum([1 for s in signals if "Bearish" in s or "Sell" in s or "Death" in s or "Overbought" in s or "Stretch" in s])
            
            status = "Neutral"
            if bull_score > bear_score: status = "Bullish"
            elif bear_score > bull_score: status = "Bearish"

            return {
                "price": current_price,
                "rsi": rsi,
                "sma50": sma50,
                "sma200": sma200,
                "upper_bb": upper_bb,
                "lower_bb": lower_bb,
                "macd": macd_val,
                "macd_signal": signal_val,
                "signals": signals,
                "status": status
            }
        except Exception as e:
            print(f"Tech Error: {e}")
            return None