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
        try:
            news_data = json.load(f)
        except:
            news_data = []
else:
    news_data = []

# 【新機能】もしストックが10件未満なら、初回ブーストとして過去データをリセットして大量取得する
if len(news_data) < 10:
    news_data = []

existing_urls = set([item["link"] for item in news_data])

rss_urls = [
    "https://news.yahoo.co.jp/rss/topics/business.xml",
    "https://www.nhk.or.jp/rss/news/cat6.xml",
    "https://news.yahoo.co.jp/rss/media/bloom_st/all.xml",
    "https://news.yahoo.co.jp/rss/media/reut/all.xml",
    "https://news.yahoo.co.jp/rss/topics/world.xml",
    "https://media.rakuten-sec.net/list/feed/rss",
    "https://news.google.com/rss/search?q=%E6%8A%95%E8%B3%87+OR+%E6%A0%AA%E5%BC%8F+OR+%E7%82%BA%E6%9B%BF&hl=ja&gl=JP&ceid=JP:ja"
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
                if count >= 8: # 1サイトあたりの取得上限を引き上げ
                    break
    except Exception:
        pass

random.shuffle(all_entries)
# 今回は一気に40件の取得に挑戦します
target_entries = all_entries[:40]

categories = ["株式・投資信託", "成長テーマ", "マクロ経済・地政学", "為替・金利", "不動産・生活", "その他"]
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
        
        # 【重要】APIのスピード違反（1分間15回制限）を防ぐため、確実に5秒待機する
        time.sleep(5) 
        
    except Exception as e:
        # 万が一制限に引っかかった場合は、エラーを無視せず10秒休んで回復を待つ
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
