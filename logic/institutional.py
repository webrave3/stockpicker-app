import yfinance as yf
import pandas as pd
import traceback

class TitanInstitutional:
    @staticmethod
    def analyze(ticker):
        trans_list = []
        net_buy = 0
        
        try:
            stock = yf.Ticker(ticker)
            insiders = stock.insider_transactions
            
            if insiders is None or insiders.empty:
                return {"signal": "No Data", "net_flow": 0, "transactions": [], "has_roles": False}

            has_roles_data = False
            for idx, row in insiders.head(25).iterrows():
                date_val = row.get('Start Date')
                date_str = date_val.strftime('%Y-%m-%d') if hasattr(date_val, 'strftime') else str(date_val)[:10]
                
                shares = row.get('Shares', 0)
                val = row.get('Value', 0)
                text = str(row.get('Text', '')).lower()
                
                # Attempt to get a more specific role
                role = str(row.get('Relation', row.get('Position', 'Unknown'))).replace('_', ' ').title()
                if role == "Unknown" and "officer" in text:
                    role = "Officer"
                elif role == "Unknown" and "director" in text:
                    role = "Director"
                elif role == "Unknown" and "10% owner" in text:
                    role = "Major Shareholder"
                
                if role not in ["Unknown", "N/A", "-"]:
                    has_roles_data = True
                else:
                    role = "-" # Ensure consistency if no specific role is found

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
                    "role": role,
                    "shares": f"{int(shares):,}",
                    "value": f"${int(val):,}" if val > 0 else "-",
                    "price": f"${(val/shares):.2f}" if shares > 0 and val > 0 else "-",
                    "type": t_type
                })

            signal = "Neutral"
            if net_buy > 500000: signal = "🐳 Accumulation"
            elif net_buy < -500000: signal = "📉 Distribution"

            return {"signal": signal, "net_flow": net_buy, "transactions": trans_list, "has_roles": has_roles_data}
        except Exception as e:
            # print(f"Error fetching institutional data for {ticker}: {e}") # For debugging
            return {"signal": "Error", "net_flow": 0, "transactions": [], "has_roles": False}