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
あなたはプロの機関投資家です。以下の【ニュース一覧】を全て分析し、以下のJSON配列フォーマットで出力してください。
カテゴリ: "国内株・企業業績", "米国株・海外株", "日米金利・物価・為替", "世界経済・マクロ指標", "世界情勢・地政学", "成長テーマ・新技術", "商品・暗号資産", "不動産・住宅市場", "生活・社会保障", "その他"
[{"id": 0, "category": "選択したカテゴリ", "summary": "要約"}]
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

# --- 指数取得（データ構造として保存） ---
indices_data = {}

# 1. yfinanceから確実に取れるもの
symbols = {
    "^N225": "日本日経平均",
    "NIY=F": "日経先物",
    "JPY=X": "為替 ドル円",
    "EURJPY=X": "為替 ユーロ円",
    "^DJI": "米国NYダウ",
    "^VIX": "VIX恐怖指数",
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

# 2. 国債（財務省）
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

# 3. TOPIXと日経VI（Google Financeから物理スクレイピングで確実取得）
def get_gf(ticker, exch):
    try:
        url = f"https://www.google.com/finance/quote/{ticker}:{exch}"
        html = requests.get(url, timeout=5).text
        soup = BeautifulSoup(html, "html.parser")
        p = soup.find(class_="YMlKec fxKbKc").text.strip()
        c_tag = soup.find(class_="JwB6zf")
        c = c_tag.text.strip() if c_tag else "0.00%"
        return p, c
    except: return None, None

p_topix, c_topix = get_gf("TOPIX", "INDEXTKY")
if p_topix: indices_data["日本TOPIX"] = {"price": p_topix, "change": c_topix}

p_vi, c_vi = get_gf("NI225VIX", "INDEXNIK")
if p_vi: indices_data["日経VI"] = {"price": p_vi, "change": c_vi}

# --- スケジュールとみんかぶ取得 ---
time.sleep(5)
SCHEDULE_FILE = "schedule_data.json"

# エラー上書きを防ぐため、まずは初期値を設定
schedule_result_json = {
    "schedule": "現在データを収集中です...",
    "indices": indices_data,
    "news": "現在データを収集中です...",
    "contribution": "現在データを収集中です..."
}

# もし過去の成功データがあれば引き継ぐ
if os.path.exists(SCHEDULE_FILE):
    try:
        with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
            old_data = json.load(f)
            # エラーの文字が入っていたら引き継がない
            if "エラー" not in old_data.get("schedule", ""):
                schedule_result_json["schedule"] = old_data.get("schedule", schedule_result_json["schedule"])
            if "エラー" not in old_data.get("news", ""):
                schedule_result_json["news"] = old_data.get("news", schedule_result_json["news"])
            if "エラー" not in old_data.get("contribution", ""):
                schedule_result_json["contribution"] = old_data.get("contribution", schedule_result_json["contribution"])
            
            # 取得に失敗した指数があれば前回値を補完する
            old_indices = old_data.get("indices", {})
            if isinstance(old_indices, dict):
                for k, v in old_indices.items():
                    if k not in indices_data:
                        schedule_result_json["indices"][k] = {"price": f"{v.get('price', '')} (※)", "change": v.get('change', '0.0%')}
    except: pass

# 新しいデータの取得にチャレンジ
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

    prompt_s = f"""あなたは金融アシスタントです。以下のWebページから情報を抽出しJSONで出力してください。
{{"schedule": "今週・本日の予定(###で見出し)","news": "経済指標(###で見出し)","contribution": "値上がり・値下がり数と寄与度TOP10"}}
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
