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

# 唯一無料で動く「2.5」を指定します
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
target_entries = all_entries[:15]

JST = timezone(timedelta(hours=+9), 'JST')
current_time_str = datetime.now(JST).isoformat()

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
]

new_articles = []

if target_entries:
    # --- 【最強の解決策】15件のニュースを「1回の質問」にまとめてAIに投げる ---
    prompt = """
あなたはプロの機関投資家です。以下の【ニュース一覧】を全て分析し、指定された【JSONフォーマット】で返してください。

【カテゴリの選択肢】
"株式・投資信託", "成長テーマ", "マクロ経済・地政学", "為替・金利", "不動産・生活", "その他"

【JSONフォーマット（この形以外の文字は一切出力しないでください）】
[
  {
    "id": 0,
    "category": "選択したカテゴリ",
    "summary": "今後の市場や取引材料としてどう影響するか、2〜3行の要約"
  }
]

【ニュース一覧】
"""
    for i, entry in enumerate(target_entries):
        prompt += f"ID: {i}\nタイトル: {entry.title}\n\n"

    try:
        response = model.generate_content(prompt, safety_settings=safety_settings)
        if response.parts:
            # AIが返した文字列を整理して読み込む
            result_text = response.text.strip()
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]
            
            ai_results = json.loads(result_text.strip())
            
            # 元のニュースとAIの分析を合体
            for res in ai_results:
                idx = res.get("id")
                if idx is not None and 0 <= idx < len(target_entries):
                    entry = target_entries[idx]
                    new_articles.append({
                        "title": entry.title,
                        "link": entry.link,
                        "summary": res.get("summary", "要約なし"),
                        "category": res.get("category", "その他"),
                        "fetched_at": current_time_str
                    })
    except Exception as e:
        print(f"Batch AI Error: {e}")

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

# --- 経済指標カレンダーの取得 ---
time.sleep(5) 

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
「本日の主な予定」と「NEWS（経済指標）」に関する情報を抽出し、投資家向けに見やすく箇条書きでまとめてください。
余計な挨拶や説明は不要です。情報が見つからない場合は「本日の重要な予定はありません」と出力してください。

【Webページのテキスト】
{page_text_short}
"""
    
    schedule_response = model.generate_content(schedule_prompt, safety_settings=safety_settings)
    if schedule_response.parts:
        schedule_result = schedule_response.text
    else:
        schedule_result = "⚠️ AIが安全フィルターによりブロックしました。"
        
except Exception as e:
    schedule_result = f"⚠️ サイト読み込みエラー: {e}"

with open("schedule_data.txt", "w", encoding="utf-8") as f:
    f.write(schedule_result)
