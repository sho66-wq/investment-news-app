import os
import json
import time
import random
from datetime import datetime, timedelta, timezone
import feedparser
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import yfinance as yf

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
        pass

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


# --- 【最強ツール yfinance】12指数を確実に取得して美しく色付けする ---
indices_text = ""
symbols = {
    "^N225": "日本日経平均",
    "NIY=F": "日経先物",
    "^TOPX": "日本TOPIX",
    "^JN09T": "日本国債10年利回り",
    "JPY=X": "為替 ドル円",
    "EURJPY=X": "為替 ユーロ円",
    "^DJI": "米国NYダウ",
    "^VIX": "VIX恐怖指数",
    "^JNIV": "日経VI",
    "CL=F": "WTI原油先物",
    "GC=F": "NY金先物",
    "BTC-JPY": "ビットコイン"
}

for sym, name in symbols.items():
    try:
        ticker = yf.Ticker(sym)
        # 過去5日分を取得し、最新の2日分を比較する（休日対策）
        hist = ticker.history(period="5d")
        if len(hist) >= 2:
            prev_close = hist['Close'].iloc[-2]
            current = hist['Close'].iloc[-1]
            change = current - prev_close
            change_pct = (change / prev_close) * 100
            
            # 矢印と色の設定
            if change_pct > 0:
                arrow = f":green[↑ +{change_pct:.2f}%]"
            elif change_pct < 0:
                arrow = f":red[↓ {change_pct:.2f}%]"
            else:
                arrow = "±0.00%"
                
            # 見やすくカンマを入れる
            if current < 1000:
                price_str = f"{current:.2f}"
            else:
                price_str = f"{current:,.2f}"
                
            # 銘柄名を【青色】にする
            indices_text += f"- **:blue[{name}]**: {price_str} ({arrow})\n"
        else:
            indices_text += f"- **:blue[{name}]**: 取得不可\n"
    except Exception as e:
        indices_text += f"- **:blue[{name}]**: 取得不可\n"

# ご要望のURLを一番下に追加！
indices_text += "\n*(データ取得元: [Yahoo Finance](https://finance.yahoo.co.jp/))*"


# --- スケジュールとみんかぶのAIスクレイピング ---
time.sleep(5) 
schedule_result_json = {"schedule": "エラー", "indices": indices_text, "news": "エラー", "contribution": "エラー"}

try:
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    res_sched = requests.get("https://nikkei225jp.com/schedule/", headers=headers, timeout=15)
    res_sched.encoding = res_sched.apparent_encoding
    soup_sched = BeautifulSoup(res_sched.text, "html.parser")
    for script in soup_sched(["script", "style"]):
        script.extract()
    text_sched = soup_sched.get_text(separator=' ', strip=True)[:15000]

    res_min = requests.get("https://fu.minkabu.jp/chart/nikkei225/contribution", headers=headers, timeout=15)
    res_min.encoding = res_min.apparent_encoding
    soup_min = BeautifulSoup(res_min.text, "html.parser")
    for script in soup_min(["script", "style"]):
        script.extract()
    text_min = soup_min.get_text(separator=' ', strip=True)[:15000]

    schedule_prompt = f"""
あなたは金融アシスタントです。以下の2つのWebページから情報を抽出し、必ず指定のJSON形式で出力してください。
各値は配列や辞書にせず、必ず1つの長い文字列にしてください。箇条書きは「- 」と改行「\\n」を使ってください。

{{
  "schedule": "【ページ1】から今週と本日の主な予定を抜粋（日付は ### で大きく）",
  "news": "【ページ1】からNEWS（経済指標）を抜粋（日付は ### で大きく）",
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
        schedule_result_json["schedule"] = ai_data.get("schedule", "取得エラー")
        schedule_result_json["news"] = ai_data.get("news", "取得エラー")
        schedule_result_json["contribution"] = ai_data.get("contribution", "取得エラー")
        
except Exception as e:
    pass

with open("schedule_data.json", "w", encoding="utf-8") as f:
    json.dump(schedule_result_json, f, ensure_ascii=False, indent=2)
