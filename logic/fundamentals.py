class TitanFundamentals:
    # This dictionary is required by main.py for tooltips
    metric_descriptions = {
        "P/E Ratio": "Price-to-Earnings Ratio. Shows how much investors are willing to pay per dollar of earnings. Lower is generally better, but can indicate slower growth.",
        "PEG Ratio": "Price/Earnings to Growth Ratio. Relates P/E to expected earnings growth. A PEG < 1 suggests the stock is undervalued given its growth. Values > 2 typically indicate overvaluation.",
        "ROE %": "Return on Equity. Measures how efficiently a company uses shareholders' investments to generate profit. Higher ROE (e.g., >15-20%) indicates strong management and a competitive advantage.",
        "Profit Margin": "Net Profit Margin. The percentage of revenue left after all expenses, including taxes, have been deducted. Higher margins (e.g., >10-15%) indicate efficient operations and pricing power.",
        "Debt/Equity": "Debt-to-Equity Ratio. Compares a company's total liabilities to its shareholder equity. Lower (e.g., <100%) indicates less reliance on debt and lower financial risk.",
        "Current Ratio": "Current Ratio. Measures a company's ability to pay off its short-term liabilities with its short-term assets. A ratio > 1.0 (ideally > 1.5-2.0) indicates good liquidity.",
        "Free Cash Flow": "Free Cash Flow. Cash generated after accounting for cash outflows to support operations and maintain capital assets. Represents the cash a company can use to repay debt, pay dividends, or invest in growth. Positive and growing FCF is crucial.",
        "Dividend Yield": "Dividend Yield. The annual dividend income per share, expressed as a percentage of the stock's current price. Attractive for income-focused investors, but analyze if it's sustainable."
    }

    @staticmethod
    def calculate_score(info):
        score = 0
        max_score = 0
        flags = []
        breakdown = [] 

        def get(key, default=0):
            val = info.get(key)
            if isinstance(val, (int, float)): return val
            return default

        def add_points(points, reason, description=""):
            nonlocal score, max_score
            max_score += 20 
            if points > 0:
                score += points
                breakdown.append(f"✅ {reason}")
            else:
                breakdown.append(f"⚪ {reason}")

        # 1. ROE
        roe = get('returnOnEquity', 0) * 100
        if roe > 15: add_points(20, f"High ROE ({roe:.1f}%)")
        else: add_points(0, f"Low ROE ({roe:.1f}%)")

        # 2. Margins
        op_margin = get('operatingMargins', 0) * 100
        if op_margin > 15: add_points(20, f"High Margins ({op_margin:.1f}%)")
        else: add_points(0, f"Low Margins ({op_margin:.1f}%)")

        # 3. Debt
        de = get('debtToEquity', 1000)
        if de < 100: add_points(20, f"Safe Debt Level (D/E {de:.0f}%)")
        else: 
            add_points(0, f"High Debt (D/E {de:.0f}%)")
            flags.append("High Debt Risk")

        # 4. Liquidity
        cr = get('currentRatio', 0)
        if cr > 1.2: add_points(20, f"Liquid Balance Sheet (CR {cr:.2f}x)")
        else: 
            add_points(0, f"Low Liquidity (CR {cr:.2f}x)")
            flags.append("Liquidity Risk")

        # 5. Growth (PEG Check)
        pe = get('trailingPE', 0)
        g = get('earningsGrowth', 0)
        peg = get('pegRatio', 0)
        
        if (peg == 0 or peg is None) and g > 0 and pe > 0:
            peg = pe / (g * 100) if g * 100 != 0 else 0
        
        if peg and 0 < peg < 1.5: add_points(20, f"Growth at Fair Price (PEG {peg:.2f})")
        else: add_points(0, f"PEG: Potential Overvaluation ({peg:.2f})")

        final_score = int((score / max_score) * 100) if max_score > 0 else 0
        
        tier = "⚠️ AVOID"
        if final_score >= 80: tier = "💎 ELITE"
        elif final_score >= 60: tier = "🥇 QUALITY"
        elif final_score >= 40: tier = "🥈 OKAY"

        return final_score, tier, flags, breakdown

    @staticmethod
    def calculate_reverse_dcf(price, fcf_per_share, growth_rate, discount_rate, terminal_multiple):
        if fcf_per_share <= 0: return 0
        future_values = []
        current_fcf = fcf_per_share
        for i in range(1, 11):
            current_fcf *= (1 + growth_rate)
            discounted = current_fcf / ((1 + discount_rate) ** i)
            future_values.append(discounted)
        terminal_val = (current_fcf * terminal_multiple) / ((1 + discount_rate) ** 10)
        return sum(future_values) + terminal_val