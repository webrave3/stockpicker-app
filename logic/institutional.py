import yfinance as yf
import pandas as pd
import traceback

class TitanInstitutional:
    @staticmethod
    def analyze(ticker):
        trans_list = []
        net_buy = 0
        debug_output = []

        try:
            debug_output.append(f"Fetching insider transactions for {ticker}...")
            stock = yf.Ticker(ticker)
            insiders = stock.insider_transactions
            
            if insiders is None or insiders.empty:
                debug_output.append(f"No insider transactions found for {ticker}.")
                return {"signal": "No Data", "net_flow": 0, "transactions": [], "debug": "\n".join(debug_output)}

            # Take top 15 most recent
            for idx, row in insiders.head(20).iterrows(): # Process more, show top 15
                date_val = row.get('Start Date')
                date_str = date_val.strftime('%Y-%m-%d') if hasattr(date_val, 'strftime') else str(date_val)[:10]
                
                shares = row.get('Shares', 0)
                val = row.get('Value', 0)
                text = str(row.get('Text', '')).lower()
                
                if pd.isna(val): val = 0
                if pd.isna(shares): shares = 0

                t_type = "Sell"
                if "buy" in text or "purchase" in text or "grant" in text or "award" in text:
                    t_type = "Buy"
                    net_buy += val
                else:
                    net_buy -= val

                trans_list.append({
                    "date": date_str,
                    "insider": str(row.get('Insider', 'Unknown')),
                    "shares": f"{int(shares):,}",
                    "value": f"${int(val):,}" if val > 0 else "-",
                    "price": f"${(val/shares):.2f}" if shares > 0 and val > 0 else "-",
                    "type": t_type
                })
            debug_output.append(f"Found {len(trans_list)} recent transactions.")

            signal = "Neutral"
            if net_buy > 500000: signal = "🐳 Accumulation"
            elif net_buy < -500000: signal = "📉 Distribution"

            return {"signal": signal, "net_flow": net_buy, "transactions": trans_list, "debug": "\n".join(debug_output)}
        except Exception as e:
            debug_output.append(f"Institutional Error: {e}")
            debug_output.append(traceback.format_exc())
            return {"signal": "Error", "net_flow": 0, "transactions": [], "debug": "\n".join(debug_output)}