import os
import json
import time
import random
from datetime import datetime, timedelta, timezone
import feedparser
import google.generativeai as genai

# アクセス拒否対策
feedparser.USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)

# 【真犯人解決】ログで確認できた最新のモデルを正確に指定
model = genai.GenerativeModel("gemini-2.5-flash")

DATA_FILE = "news_data.json"
try:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            news_data = json.load(f)
    else:
        news_data = []
except:
    news_data = []

# 古いゴーストデータや診断レポートをリセット
if len(news_data) < 5:
    news_data = []

existing_urls = set([item.get("link", "") for item in news_data])

rss_urls = [
    "https://www.nhk.or.jp/rss/news/cat6.xml",
    "https://news.google.com/rss/search?q=%E6%8A%95%E8%B3%87+OR+%E7%B5%8C%E6%B8%88+OR+%E7%82%BA%E6%9B%BF&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=%E6%A0%AA%E5%BC%8F%E4%BC%9A%E7%A4%BE+OR+%E6%A5%AD%E7%B8%BE+OR+%E6%B1%BA%E7%AE%97&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=%E5%AE%87%E5%AE%99+OR+%E9%98%B2%E8%A1%9B+OR+%E3%82%B5%E3%82%A4%E3%83%90%E3%83%BC+OR+%E3%83%AC%E3%82%A2%E3%82%A2%E3%83%BC%E3%82%B9&hl=ja&gl=JP&ceid=JP:ja"
]

all_entries = []
for url in rss_urls:
    try:
        feed = feedparser.parse(url)
        count = 0
        for entry in feed.entries:
            if entry.link not in existing_urls:
                all_entries.append(entry)
                count += 1
                if count >= 8:
                    break
    except Exception:
        pass

random.shuffle(all_entries)
target_entries = all_entries[:30]

JST = timezone(timedelta(hours=+9), 'JST')
current_time_str = datetime.now(JST).isoformat()
new_articles = []

for entry in target_entries:
    title = entry.title
    link = entry.link
    
    prompt = f"""
    あなたはプロの機関投資家です。以下のニュースを分析してください。
    ニュースタイトル: {title}
    
    【指示】
    1. 以下の6つのカテゴリから最も関連性が高いものを1つ選び、「【カテゴリ】〇〇」と出力してください。
       [株式・投資信託, 成長テーマ, マクロ経済・地政学, 為替・金利, 不動産・生活, その他]
    2. このニュースが今後の市場や取引材料としてどう影響するか、2〜3行で要約してください。
    """
    
    try:
        response = model.generate_content(prompt)
        ai_text = response.text
        
        detected_category = "その他"
        if "株式" in ai_text or "投資" in ai_text:
            detected_category = "株式・投資信託"
        elif "成長" in ai_text or "防衛" in ai_text or "宇宙" in ai_text or "サイバー" in ai_text or "レアアース" in ai_text:
            detected_category = "成長テーマ"
        elif "マクロ" in ai_text or "地政学" in ai_text or "中東" in ai_text:
            detected_category = "マクロ経済・地政学"
        elif "為替" in ai_text or "金利" in ai_text or "円高" in ai_text or "円安" in ai_text:
            detected_category = "為替・金利"
        elif "不動産" in ai_text or "生活" in ai_text or "住宅" in ai_text:
            detected_category = "不動産・生活"
        
        new_articles.append({
            "title": title,
            "link": link,
            "summary": ai_text,
            "category": detected_category,
            "fetched_at": current_time_str
        })
        time.sleep(5) 
        
    except Exception as e:
        # 万が一のエラー時は10秒待機して再開を試みる
        time.sleep(10)

news_data.extend(new_articles)
filtered_news_data = []
now = datetime.now(JST)

for item in news_data:
    try:
        fetched_time = datetime.fromisoformat(item["fetched_at"])
        if (now - fetched_time).days <= 3:
            filtered_news_data.append(item)
    except Exception:
        pass

with open(DATA_FILE, "w", encoding="utf-8") as f:
    json.dump(filtered_news_data, f, ensure_ascii=False, indent=2)
