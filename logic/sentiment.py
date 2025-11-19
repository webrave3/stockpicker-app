import yfinance as yf
from textblob import TextBlob
import feedparser
import traceback
import time

class TitanSentiment:
    @staticmethod
    def analyze(ticker):
        headlines = []
        score = 0
        count = 0
        
        try:
            # Yahoo Finance RSS
            rss_url = f"https://finance.yahoo.com/rss/headline?s={ticker}"
            feed = feedparser.parse(rss_url)
            
            for entry in feed.entries[:15]: # Get a few more headlines
                title = entry.title
                link = entry.link
                
                # Extract source and author from common fields
                source = entry.get('source', {}).get('title', 'Yahoo Finance')
                if not source: source = "Yahoo Finance" # Fallback if empty
                
                author = entry.get('author', 'N/A')
                # Clean up author field if it's an email or generic
                if "@" in author or "yahoo" in author.lower() or "finance" in author.lower():
                    author = "N/A"
                
                published_time = entry.get('published_parsed')
                if published_time:
                    # Format time nicely
                    published = time.strftime('%Y-%m-%d %H:%M', published_time)
                else:
                    published = 'N/A'

                blob = TextBlob(title)
                pol = blob.sentiment.polarity
                
                score += pol
                count += 1
                
                color = "#94a3b8" # Default gray
                if pol > 0.1: color = "#4ade80" # Green
                elif pol < -0.1: color = "#ef4444" # Red
                
                headlines.append({
                    "text": title,
                    "score": pol,
                    "color": color,
                    "link": link,
                    "source": source,
                    "date": published,
                    "author": author
                })
                
        except Exception as e:
            # print(f"Error fetching sentiment for {ticker}: {e}") # For debugging
            pass

        avg = score / count if count > 0 else 0
        rating = "Neutral"
        if avg > 0.1: rating = "🐂 Bullish"
        elif avg < -0.1: rating = "🐻 Bearish"
        
        return {"rating": rating, "score": avg, "headlines": headlines}