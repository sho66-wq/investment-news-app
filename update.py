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
        with open(DATA_FILE, "r", encoding="utf-8") as f: news_data = json.load(f)
    else: news_data = []
except: news_data = []

if len(news_data) < 10: news_data = []
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
                if count >= 8: break
    except: pass

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
    # 【改善】要約のフォーマットを厳格化し、事実と推測を完全に分離
    prompt = """
あなたはプロの機関投資家です。以下の【ニュース一覧】を全て分析し、以下のJSON配列フォーマットで出力してください。
カテゴリ: "国内株・企業業績", "米国株・海外株", "日米金利・物価・為替", "世界経済・マクロ指標", "世界情勢・地政学", "成長テーマ・新技術", "商品・暗号資産", "不動産・住宅市場", "生活・社会保障", "その他"
[
  {
    "id": 0, 
    "category": "選択したカテゴリ", 
    "summary": "【事実】記事で報道されている確定した事実を1〜2行で簡潔に記載。\\n【プロの推測】その事実を元に、プロの投資家として背景や今後の市場・関連銘柄への具体的な影響を推測・深読みした内容を2〜3行で記載。"
  }
]
※summaryの中身は必ず上記の「【事実】」と「【プロの推測】」の2つの見出しを含め、改行（\\n）で分けて出力してください。「要約中」などの手抜きは絶対禁止です。
"""
    for i, entry in enumerate(target_entries):
        prompt += f"ID: {i}\nタイトル: {entry.title}\n\n"
    try:
        response = model.generate_content(prompt, safety_settings=safety_settings, generation_config={"response_mime_type": "application/json"})
        if response.parts:
            ai_results = json.loads(response.text)
            for res in ai_results:
                idx = res.get("id")
                if idx is not None and 0 <= idx < len(target_entries):
                    entry = target_entries[idx]
                    new_articles.append({"title": entry.title, "link": entry.link, "summary": res.get("summary", "要約なし"), "category": res.get("category", "その他"), "fetched_at": current_time_str})
    except: pass

news_data.extend(new_articles)
filtered_news_data = []
now = datetime.now(JST)
for item in news_data:
    try:
        fetched_time = datetime.fromisoformat(item["fetched_at"])
        if (now - fetched_time).days <= 3: filtered_news_data.append(item)
    except: pass
with open(DATA_FILE, "w", encoding="utf-8") as f:
    json.dump(filtered_news_data, f, ensure_ascii=False, indent=2)

# --- 指数取得（TOPIXと日経VIは安定ルート） ---
indices_data = {}

symbols = {
    "^N225": "日本日経平均",
    "NIY=F": "日経先物",
    "^TOPX": "日本TOPIX",
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
        hist = ticker.history(period="5d")
        if len(hist) >= 2:
            prev_close = hist['Close'].iloc[-2]
            current = hist['Close'].iloc[-1]
            change_pct = ((current - prev_close) / prev_close) * 100
            price_str = f"{current:.2f}" if current < 1000 else f"{current:,.2f}"
            indices_data[name] = {"price": price_str, "change": f"{change_pct:.2f}%"}
    except: pass

# 国債（財務省）
try:
    res = requests.get('https://www.mof.go.jp/jgbs/reference/interest_rate/jgbcm.csv', timeout=10)
    res.encoding = 'shift_jis'
    lines = [line.split(',') for line in res.text.strip().split('\n') if line]
    valid_lines = [l for l in lines if len(l) >= 11 and l[10].replace('.', '', 1).isdigit()]
    if len(valid_lines) >= 2:
        val = float(valid_lines[-1][10])
        change = val - float(valid_lines[-2][10])
        indices_data["日本国債10年利回り"] = {"price": f"{val:.3f}%", "change": f"{change:.3f}pt"}
except: pass


# 取得に失敗した場合の保険（日経公式からの日経VI直接取得）
if "日経VI" not in indices_data or "取得不可" in indices_data["日経VI"].get("price", "取得不可"):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res_vi = requests.get("https://indexes.nikkei.co.jp/nkave/index/profile?idx=nk225vi", headers=headers, timeout=5)
        soup_vi = BeautifulSoup(res_vi.text, "html.parser")
        p_vi = soup_vi.find("div", class_="index-value").text.strip()
        c_vi_text = soup_vi.find("div", class_="index-diff").text.strip()
        if "(" in c_vi_text:
            c_vi = c_vi_text.split("(")[1].replace(")", "").strip()
        else:
            c_vi = c_vi_text
        if p_vi: indices_data["日経VI"] = {"price": p_vi, "change": c_vi}
    except: pass


# --- スケジュールとみんかぶ取得 ---
time.sleep(5)
SCHEDULE_FILE = "schedule_data.json"

schedule_result_json = {
    "schedule": "現在データを収集中です...",
    "indices": indices_data,
    "news": "現在データを収集中です...",
    "contribution": "現在データを収集中です..."
}

if os.path.exists(SCHEDULE_FILE):
    try:
        with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
            old_data = json.load(f)
            if "エラー" not in old_data.get("schedule", ""): schedule_result_json["schedule"] = old_data.get("schedule", schedule_result_json["schedule"])
            if "エラー" not in old_data.get("news", ""): schedule_result_json["news"] = old_data.get("news", schedule_result_json["news"])
            if "エラー" not in old_data.get("contribution", ""): schedule_result_json["contribution"] = old_data.get("contribution", schedule_result_json["contribution"])
            
            old_indices = old_data.get("indices", {})
            if isinstance(old_indices, dict):
                for k, v in old_indices.items():
                    if k not in indices_data:
                        schedule_result_json["indices"][k] = {"price": f"{v.get('price', '')} (※)", "change": v.get('change', '0.0%')}
    except: pass

try:
    headers = {'User-Agent': 'Mozilla/5.0'}
    res_sched = requests.get("https://nikkei225jp.com/schedule/", headers=headers, timeout=15)
    res_sched.encoding = res_sched.apparent_encoding
    soup_sched = BeautifulSoup(res_sched.text, "html.parser")
    for script in soup_sched(["script", "style"]): script.extract()
    text_sched = soup_sched.get_text(separator=' ', strip=True)[:15000]

    res_min = requests.get("https://fu.minkabu.jp/chart/nikkei225/contribution", headers=headers, timeout=15)
    res_min.encoding = res_min.apparent_encoding
    soup_min = BeautifulSoup(res_min.text, "html.parser")
    for script in soup_min(["script", "style"]): script.extract()
    text_min = soup_min.get_text(separator=' ', strip=True)[:15000]

    prompt_s = f"""
あなたは金融アシスタントです。以下のWebページから情報を抽出し、指定のJSON形式で出力してください。
【重要ルール】
出力する文字列は、そのまま画面に表示して美しく見えるように、Markdown形式（箇条書き `- ` や見出し `### `）を必ず使ってください。改行には `\\n` を使用してください。
各値の中身には `{{` や `[` 、`"` などのプログラム用の記号を「絶対に」含めず、純粋な箇条書きのテキスト(`- `)と改行(`\\n`)のみを使ってください。

{{
  "schedule": "今週・本日の予定を、日付ごとに箇条書き（- ）で整理し、見やすく階層化したMarkdownテキスト",
  "news": "主要経済指標（結果と予想など）を、日付ごとに箇条書き（- ）で整理し見やすくまとめたMarkdownテキスト",
  "contribution": "値上がり・値下がり数と、寄与度上位・下位を箇条書き（- ）で見やすくまとめたMarkdownテキスト"
}}

【スケジュール】\n{text_sched}\n【みんかぶ】\n{text_min}"""
    
    response_s = model.generate_content(prompt_s, safety_settings=safety_settings, generation_config={"response_mime_type": "application/json"})
    if response_s.parts:
        ai_data = json.loads(response_s.text)
        schedule_result_json["schedule"] = ai_data.get("schedule", schedule_result_json["schedule"])
        schedule_result_json["news"] = ai_data.get("news", schedule_result_json["news"])
        schedule_result_json["contribution"] = ai_data.get("contribution", schedule_result_json["contribution"])
except: pass

with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
    json.dump(schedule_result_json, f, ensure_ascii=False, indent=2)
