import os
import json
import time
import re
from datetime import datetime, timedelta, timezone
import feedparser
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import yfinance as yf

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

JST = timezone(timedelta(hours=+9), 'JST')
current_time_str = datetime.now(JST).isoformat()
SCHEDULE_FILE = "schedule_data.json"

# --- 1. データの保護・読み込み ---
def load_old_data():
    if os.path.exists(SCHEDULE_FILE):
        try:
            with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return {}
    return {}

old_all_data = load_old_data()

# --- 2. ニュース取得と分類 ---
DATA_FILE = "news_data.json"
try:
    with open(DATA_FILE, "r", encoding="utf-8") as f: news_data = json.load(f)
except: news_data = []

rss_urls = [
    "https://news.yahoo.co.jp/rss/topics/business.xml",
    "https://www.nhk.or.jp/rss/news/cat6.xml",
    "https://news.yahoo.co.jp/rss/media/bloom_st/all.xml",
    "https://news.yahoo.co.jp/rss/media/reut/all.xml"
]
existing_urls = set([item.get("link", "") for item in news_data])
all_entries = []
for url in rss_urls:
    feed = feedparser.parse(url)
    for entry in feed.entries[:5]:
        if entry.link not in existing_urls: all_entries.append(entry)

if all_entries:
    prompt = "投資家として以下を分析しJSONで出力せよ。カテゴリ: 国内株・企業業績, 米国株・海外株, 日米金利・物価・為替, 世界経済・マクロ指標, 世界情勢・地政学, 成長テーマ・新技術, 商品・暗号資産, 不動産・住宅市場, 生活・社会保障, その他"
    for i, e in enumerate(all_entries[:15]): prompt += f"\nID:{i} {e.title}"
    try:
        res = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        ai_res = json.loads(res.text)
        for r in ai_res:
            idx = r.get("id")
            if idx is not None and idx < len(all_entries):
                news_data.append({"title": all_entries[idx].title, "link": all_entries[idx].link, "summary": r.get("summary", "要約中"), "category": r.get("category", "その他"), "fetched_at": current_time_str})
    except: pass

with open(DATA_FILE, "w", encoding="utf-8") as f: json.dump(news_data[-200:], f, ensure_ascii=False, indent=2)

# --- 3. 指数の物理抽出エンジン (100点仕様) ---
indices_data = old_all_data.get("indices", {})
if not isinstance(indices_data, dict): indices_data = {}

def get_gf_price(ticker, exchange):
    url = f"https://www.google.com/finance/quote/{ticker}:{exchange}"
    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        soup = BeautifulSoup(r.text, "html.parser")
        price = soup.find(class_="YMlKec fxKbKc").text
        change = soup.find(class_="JwB6zf").text
        return price, change
    except: return None, None

# yfinanceで取れるもの
yf_symbols = {"^N225": "日本日経平均", "NIY=F": "日経先物", "JPY=X": "為替 ドル円", "EURJPY=X": "為替 ユーロ円", "^DJI": "米国NYダウ", "^VIX": "VIX恐怖指数", "CL=F": "WTI原油先物", "GC=F": "NY金先物", "BTC-JPY": "ビットコイン"}
for sym, name in yf_symbols.items():
    try:
        t = yf.Ticker(sym).history(period="2d")
        p = t['Close'].iloc[-1]
        c = ((p - t['Close'].iloc[-2]) / t['Close'].iloc[-2]) * 100
        indices_data[name] = {"price": f"{p:,.2f}", "change": f"{c:+.2f}%"}
    except: pass

# Google Financeで物理的に抜くもの (TOPIX, VI)
for name, tck in [("日本TOPIX", ("TOPIX", "INDEXTKY")), ("日経VI", ("NI225VIX", "INDEXNIK"))]:
    p, c = get_gf_price(tck[0], tck[1])
    if p: indices_data[name] = {"price": p, "change": c}

# 国債
try:
    r = requests.get('https://www.mof.go.jp/jgbs/reference/interest_rate/jgbcm.csv').content.decode('shift_jis')
    lines = [l.split(',') for l in r.strip().split('\n') if l]
    latest = lines[-1]
    val = float(latest[10])
    change = val - float(lines[-2][10])
    indices_data["日本国債10年利回り"] = {"price": f"{val:.3f}%", "change": f"{change:+.3f}pt"}
except: pass

# --- 4. スケジュール取得 (失敗時は古いデータを維持) ---
new_sched = old_all_data.get("schedule", "取得中...")
new_news = old_all_data.get("news", "取得中...")
new_cont = old_all_data.get("contribution", "取得中...")

try:
    s_text = requests.get("https://nikkei225jp.com/schedule/", timeout=10).text
    m_text = requests.get("https://fu.minkabu.jp/chart/nikkei225/contribution", timeout=10).text
    prompt_s = f"以下からJSON出力せよ。{{'s':'予定','n':'指標','c':'寄与度'}}\n{s_text[:5000]}\n{m_text[:5000]}"
    res_s = model.generate_content(prompt_s, generation_config={"response_mime_type": "application/json"})
    ai_s = json.loads(res_s.text)
    new_sched, new_news, new_cont = ai_s.get('s'), ai_s.get('n'), ai_s.get('c')
except: pass

final_save = {"schedule": new_sched, "indices": indices_data, "news": new_news, "contribution": new_cont}
with open(SCHEDULE_FILE, "w", encoding="utf-8") as f: json.dump(final_save, f, ensure_ascii=False, indent=2)
