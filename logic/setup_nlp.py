import nltk
import textblob

print("Downloading NLTK data...")
try:
    nltk.download('punkt')
    nltk.download('brown')
    nltk.download('punkt_tab')
    print("✅ Success! NLP data installed.")
except Exception as e:
    print(f"Error: {e}")