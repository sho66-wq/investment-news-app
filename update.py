import os
import json
import time
import random
from datetime import datetime, timedelta, timezone
import feedparser
import google.generativeai as genai

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)

available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
preferred_models = ['models/gemini-2.5-flash', 'models/gemini-1.5-flash', 'models/gemini-1.5-pro']
selected_model = next((pm for pm in preferred_models if pm in available_models), available_models[0] if available_models else None)
model = genai.GenerativeModel(selected_model.replace("models/", ""))

DATA_FILE = "news_data.json"
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        news_data = json.load(f)
else:
    news_data = []

existing_urls = set([item["link"] for item in news_data])

rss_urls = [
    "https://news.yahoo.co.jp/rss/topics/business.xml",
    "https://www.nhk.or.jp/rss/news/cat6.xml",
    "https://news.yahoo.co.jp/rss/media/bloom_st/all.xml",
    "https://media.rakuten-sec.net/list/feed/rss",
    "https://news.google.com/rss/search?q=%E6%8A%95%E8%B3%87+OR+%E6%A0%AA%E5%BC%8F+OR+%E7%82%BA%E6%9B%BF&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=%E5%AE%87%E5%AE%99+OR+%E9%98%B2%E8%A1%9B+OR+%E3%82%B5%E3%82%A4%E3%83%90%E3%83%BC+OR+%E3%83%AC%E3%82%A2%E3%82%A2%E3%83%BC%E3%82%B9+OR+%E3%82%A8%E3%83%8D%E3%83%AB%E3%82%AE%E3%83%BC&hl=ja&gl=JP&ceid=JP:ja"
]

all_entries = []
count_per_site = 15 // len(rss_urls) or 1

for url in rss_urls:
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            if entry.link not in existing_urls:
                all_entries.append(entry)
                if len(all_entries) >= count_per_site * len(rss_urls):
                    break
    except Exception:
        pass

random.shuffle(all_entries)
target_entries = all_entries[:15]

# 新しい実践的なカテゴリ
categories = ["株式・投資信託", "成長テーマ", "マクロ経済・地政学", "為替・金利", "不動産・生活", "その他"]
JST = timezone(timedelta(hours=+9), 'JST')
current_time_str = datetime.now(JST).isoformat()
new_articles = []

for entry in target_entries:
    title = entry.title
    link = entry.link
    
    # プロンプトを詳細化し、AIが迷わないように指示
    prompt = f"""
    あなたはプロの機関投資家です。以下のニュースを分析してください。
    ニュースタイトル: {title}
    
    【指示】
    1. 以下のカテゴリリストから、最も関連性が高いものを1つだけ選び、必ず「【カテゴリ】〇〇」と出力してください。
       - 株式・投資信託 (個別銘柄、投資信託、市場動向など)
       - 成長テーマ (防衛、宇宙、サイバー、AI、エネルギー、レアアースなど)
       - マクロ経済・地政学 (中東情勢、各国の経済指標、インフレなど)
       - 為替・金利 (円高円安、日銀・FRBの政策など)
       - 不動産・生活 (住宅、不動産市場、社会保障、個人の家計など)
       - その他
    2. このニュースが今後の市場や取引材料としてどう影響するか、2〜3行で要約してください。
    """
    
    try:
        response = model.generate_content(prompt)
        ai_text = response.text
        
        # 判定を少し「ゆるく」して、取りこぼしを防ぐ
        detected_category = "その他"
        for cat in categories:
            if cat in ai_text:
                detected_category = cat
                break
        
        new_articles.append({
            "title": title,
            "link": link,
            "summary": ai_text,
            "category": detected_category,
            "fetched_at": current_time_str
        })
    except Exception:
        pass
    time.sleep(2)

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
