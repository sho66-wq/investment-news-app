import os
import json
import time
import random
from datetime import datetime, timedelta, timezone
import feedparser
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)

available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
preferred_models = ['models/gemini-2.5-flash', 'models/gemini-2.0-flash', 'models/gemini-1.5-flash']
selected_model = next((pm for pm in preferred_models if pm in available_models), available_models[0] if available_models else None)
model = genai.GenerativeModel(selected_model.replace("models/", ""))

DATA_FILE = "news_data.json"
try:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            news_data = json.load(f)
    else:
        news_data = []
except:
    news_data = []

if len(news_data) < 10:
    news_data = []

existing_urls = set([item.get("link", "") for item in news_data])

rss_urls = [
    "https://news.yahoo.co.jp/rss/topics/business.xml",
    "https://www.nhk.or.jp/rss/news/cat6.xml",
    "https://news.yahoo.co.jp/rss/media/bloom_st/all.xml",
    "https://news.yahoo.co.jp/rss/media/reut/all.xml",
    "https://news.yahoo.co.jp/rss/topics/world.xml",
    "https://media.rakuten-sec.net/list/feed/rss"
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
# 【修正ポイント】1回の取得を15件に減らし、APIの制限を回避
target_entries = all_entries[:15]

JST = timezone(timedelta(hours=+9), 'JST')
current_time_str = datetime.now(JST).isoformat()
new_articles = []

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
]

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
        response = model.generate_content(prompt, safety_settings=safety_settings)
        if not response.parts:
            continue
            
        ai_text = response.text
        
        detected_category = "その他"
        if "株式" in ai_text or "投資" in ai_text:
            detected_category = "株式・投資信託"
        elif "成長" in ai_text or "防衛" in ai_text or "宇宙" in ai_text or "サイバー" in ai_text or "レア" in ai_text:
            detected_category = "成長テーマ"
        elif "マクロ" in ai_text or "地政学" in ai_text or "中東" in ai_text:
            detected_category = "マクロ経済・地政学"
        elif "為替" in ai_text or "金利" in ai_text or "円高" in ai_text or "円安" in ai_text or "日銀" in ai_text or "FRB" in ai_text:
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
        
        # 【修正ポイント】1件ごとに「10秒」の深呼吸をさせてスピード違反を防ぐ
        time.sleep(10) 
        
    except Exception as e:
        time.sleep(15)

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


# --- 【追加任務】経済指標カレンダーのAIスクレイピング ---

# 【修正ポイント】ニュース分析で疲れたAIを「20秒」休ませて制限をリセット
time.sleep(20) 

schedule_result = "⚠️ データの取得に失敗しました。"

try:
    schedule_url = "https://nikkei225jp.com/schedule/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    res = requests.get(schedule_url, headers=headers, timeout=15)
    res.encoding = res.apparent_encoding
    soup = BeautifulSoup(res.text, "html.parser")
    
    for script in soup(["script", "style"]):
        script.extract()
    page_text = soup.get_text(separator='\n')
    page_text_short = page_text[:8000]

    schedule_prompt = f"""
    あなたは優秀な金融アシスタントです。以下のWebページのテキストデータから、
    「本日の主な予定」と「NEWS（経済指標）」に関する情報を抽出し、
    投資家向けに見やすく箇条書きでまとめてください。
    余計な挨拶や説明は不要です。情報が見つからない場合は「本日の重要な予定はありません」と出力してください。
    
    【Webページのテキスト】
    {page_text_short}
    """
    
    schedule_response = model.generate_content(schedule_prompt, safety_settings=safety_settings)
    if schedule_response.parts:
        schedule_result = schedule_response.text
    else:
        schedule_result = "⚠️ AIが安全フィルターによりテキスト生成をブロックしました。"
        
except Exception as e:
    schedule_result = f"⚠️ サイトの読み込みエラーが発生しました。理由: {e}"

with open("schedule_data.txt", "w", encoding="utf-8") as f:
    f.write(schedule_result)
