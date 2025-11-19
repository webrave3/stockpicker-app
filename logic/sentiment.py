import yfinance as yf
from textblob import TextBlob
import feedparser
import traceback

class TitanSentiment:
    @staticmethod
    def analyze(ticker):
        headlines = []
        score = 0
        count = 0
        debug_output = []
        
        try:
            debug_output.append(f"Attempting to fetch news for {ticker}...")
            # Try RSS Feed
            rss_url = f"https://finance.yahoo.com/rss/headline?s={ticker}"
            feed = feedparser.parse(rss_url)
            
            if not feed.entries:
                debug_output.append(f"No RSS entries found for {ticker}.")
            
            for entry in feed.entries[:8]: # Limit to top 8 to avoid UI overload
                title = entry.title
                link = entry.link
                
                debug_output.append(f"Processing: {title[:50]}...")
                blob = TextBlob(title)
                pol = blob.sentiment.polarity
                
                score += pol
                count += 1
                
                color = "white"
                if pol > 0.1: color = "#4ade80"
                elif pol < -0.1: color = "#ef4444"
                
                headlines.append({
                    "text": title,
                    "score": pol,
                    "color": color,
                    "link": link # Add link for potential future clickability
                })
                
        except Exception as e:
            debug_output.append(f"Sentiment Error: {e}")
            debug_output.append(traceback.format_exc()) # Full traceback for debugging

        avg = score / count if count > 0 else 0
        rating = "Neutral"
        if avg > 0.1: rating = "🐂 Bullish"
        elif avg < -0.1: rating = "🐻 Bearish"
        
        return {"rating": rating, "score": avg, "headlines": headlines, "debug": "\n".join(debug_output)}