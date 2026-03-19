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
    prompt = """
あなたはプロの機関投資家です。以下の【ニュース一覧】を全て分析してください。
出力は必ず以下のJSON配列フォーマットにしてください。

[
  {
    "id": 0,
    "category": "株式・投資信託",
    "summary": "2〜3行の要約"
  }
]

【ニュース一覧】
"""
    for i, entry in enumerate(target_entries):
        prompt += f"ID: {i}\nタイトル: {entry.title}\n\n"

    try:
        # JSON出力モードを強制（これで記号のバグを防ぎます）
        response = model.generate_content(
            prompt, 
            safety_settings=safety_settings,
            generation_config={"response_mime_type": "application/json"}
        )
        if response.parts:
            ai_results = json.loads(response.text)
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


# --- 経済指標・主要指数・みんかぶのAIスクレイピング ---
time.sleep(5) 

schedule_result_json = {"schedule": "エラー", "indices": "エラー", "news": "エラー", "contribution": "エラー"}

try:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # ① スケジュールページ
    res_sched = requests.get("https://nikkei225jp.com/schedule/", headers=headers, timeout=15)
    res_sched.encoding = res_sched.apparent_encoding
    soup_sched = BeautifulSoup(res_sched.text, "html.parser")
    for script in soup_sched(["script", "style"]):
        script.extract()
    text_sched = soup_sched.get_text(separator=' ', strip=True)[:15000]

    # ② 【大正解！】リアルタイム主要株価指数（/chart/）のページに変更
    res_chart = requests.get("https://nikkei225jp.com/chart/", headers=headers, timeout=15)
    res_chart.encoding = res_chart.apparent_encoding
    soup_chart = BeautifulSoup(res_chart.text, "html.parser")
    for script in soup_chart(["script", "style"]):
        script.extract()
    text_chart = soup_chart.get_text(separator=' ', strip=True)[:15000]

    # ③ みんかぶページ
    res_min = requests.get("https://fu.minkabu.jp/chart/nikkei225/contribution", headers=headers, timeout=15)
    res_min.encoding = res_min.apparent_encoding
    soup_min = BeautifulSoup(res_min.text, "html.parser")
    for script in soup_min(["script", "style"]):
        script.extract()
    text_min = soup_min.get_text(separator=' ', strip=True)[:15000]

    schedule_prompt = f"""
あなたは優秀な金融アシスタントです。以下の3つのWebページから情報を抽出し、必ず指定のJSON形式で出力してください。
各値（value）は必ず「1つの長い文字列」にしてください。配列やオブジェクトは禁止です。箇条書きは「- 」と改行「\\n」を使ってください。見出しには「### 」をつけてください。

{{
  "schedule": "【ページ1】から「今週の主な予定」と「本日の主な予定」を抜粋（日付は ### で大きく）",
  "indices": "【ページ2】から（日本日経平均、日経先物、日本TOPIX、日本国債10年利回り、ドル円、ユーロ円、米国NYダウ、VIX恐怖指数、日経VI、WTI原油先物、NY金先物、ビットコイン）の最新価格と変動を箇条書きで抽出",
  "news": "【ページ1】から「NEWS（経済指標）」を抜粋（日付は ### で大きく）",
  "contribution": "【ページ3】から日経225の「値上がり銘柄数・値下がり銘柄数」と、「値上がり寄与度上位TOP10」「値下がり寄与度上位TOP10」を箇条書きで"
}}

【ページ1：スケジュール】\n{text_sched}
\n---\n
【ページ2：指数チャート】\n{text_chart}
\n---\n
【ページ3：みんかぶ寄与度】\n{text_min}
"""
    
    # JSON出力を強制する
    schedule_response = model.generate_content(
        schedule_prompt, 
        safety_settings=safety_settings,
        generation_config={"response_mime_type": "application/json"}
    )
    if schedule_response.parts:
        schedule_result_json = json.loads(schedule_response.text)
        
except Exception as e:
    schedule_result_json = {"schedule": f"エラー: {e}", "indices": "エラー", "news": "エラー", "contribution": f"エラー: {e}"}

with open("schedule_data.json", "w", encoding="utf-8") as f:
    json.dump(schedule_result_json, f, ensure_ascii=False, indent=2)
