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


# --- 【最強機能】12指数のデータをYahoo APIから直接取得（色付け付き） ---
indices_text = ""
symbols = "^N225,NIY=F,^TOPX,^JN09T,JPY=X,EURJPY=X,^DJI,^VIX,^VN225,CL=F,GC=F,BTC-JPY"
names = {
    "^N225": "日本日経平均",
    "NIY=F": "日経先物",
    "^TOPX": "日本TOPIX",
    "^JN09T": "日本国債10年利回",
    "JPY=X": "為替 ドル円",
    "EURJPY=X": "為替 ユーロ円",
    "^DJI": "米国NYダウ",
    "^VIX": "VIX恐怖指数",
    "^VN225": "日経VI",
    "CL=F": "WTI原油先物",
    "GC=F": "NY金先物",
    "BTC-JPY": "ビットコイン"
}

try:
    yf_url = f"https://query2.finance.yahoo.com/v7/finance/quote?symbols={symbols}"
    yf_res = requests.get(yf_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}, timeout=10)
    data = yf_res.json()
    results = data.get("quoteResponse", {}).get("result", [])
    fetched_data = {res["symbol"]: res for res in results}
    
    for sym, name in names.items():
        if sym in fetched_data:
            price = fetched_data[sym].get("regularMarketPrice", 0)
            change = fetched_data[sym].get("regularMarketChangePercent", 0)
            
            # 色と矢印のフォーマット
            if change > 0:
                arrow = f":green[↑ +{change:.2f}%]"
            elif change < 0:
                arrow = f":red[↓ {change:.2f}%]"
            else:
                arrow = "±0.00%"
                
            price_str = f"{price:,.2f}" if price > 1000 else f"{price:.2f}"
            
            # 指数名を【青色】にして目立たせる
            indices_text += f"- **:blue[{name}]**: {price_str} ({arrow})\n"
        else:
            indices_text += f"- **:gray[{name}]**: 取得不可\n"
except Exception as e:
    indices_text = "指数の取得に失敗しました。"


# --- スケジュールとみんかぶのAIスクレイピング ---
time.sleep(5) 
schedule_result_json = {"schedule": "エラー", "indices": indices_text, "news": "エラー", "contribution": "エラー"}

try:
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # スケジュールページ
    res_sched = requests.get("https://nikkei225jp.com/schedule/", headers=headers, timeout=15)
    res_sched.encoding = res_sched.apparent_encoding
    soup_sched = BeautifulSoup(res_sched.text, "html.parser")
    for script in soup_sched(["script", "style"]):
        script.extract()
    text_sched = soup_sched.get_text(separator=' ', strip=True)[:15000]

    # みんかぶページ
    res_min = requests.get("https://fu.minkabu.jp/chart/nikkei225/contribution", headers=headers, timeout=15)
    res_min.encoding = res_min.apparent_encoding
    soup_min = BeautifulSoup(res_min.text, "html.parser")
    for script in soup_min(["script", "style"]):
        script.extract()
    text_min = soup_min.get_text(separator=' ', strip=True)[:15000]

    schedule_prompt = f"""
あなたは金融アシスタントです。以下の2つのWebページから情報を抽出し、必ず指定のJSON形式で出力してください。

【🚨 超絶対ルール】
1. 各値（value）の中身は、必ず「ただの1つの長い文字列」にしてください。
2. 値の中に、辞書 {{}} や配列 [] を書き込むことは絶対に禁止です。
3. 箇条書きは「- 」と改行「\\n」を使ってください。

{{
  "schedule": "【ページ1】から「今週と本日の主な予定」を抜粋（日付は ### で大きく）",
  "news": "【ページ1】から「NEWS（経済指標）」を抜粋（日付は ### で大きく）",
  "contribution": "【ページ2】から日経225の値上がり数・値下がり数、および寄与度上位・下位TOP10を箇条書きで"
}}

【ページ1：スケジュール】\n{text_sched}
\n---\n
【ページ2：みんかぶ寄与度】\n{text_min}
"""
    
    schedule_response = model.generate_content(
        schedule_prompt, 
        safety_settings=safety_settings,
        generation_config={"response_mime_type": "application/json"}
    )
    if schedule_response.parts:
        ai_data = json.loads(schedule_response.text)
        # AIの結果と、さっき取得した指数(indices_text)を合体させる
        schedule_result_json["schedule"] = ai_data.get("schedule", "取得エラー")
        schedule_result_json["news"] = ai_data.get("news", "取得エラー")
        schedule_result_json["contribution"] = ai_data.get("contribution", "取得エラー")
        
except Exception as e:
    pass

with open("schedule_data.json", "w", encoding="utf-8") as f:
    json.dump(schedule_result_json, f, ensure_ascii=False, indent=2)
