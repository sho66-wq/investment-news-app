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
        for entry in feed.entries:
            if entry.link not in existing_urls:
                all_entries.append(entry)
                if len(all_entries) >= 15: break
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
    prompt = """
あなたはプロの機関投資家です。以下の【ニュース一覧】を全て分析し、以下のJSON配列フォーマットで出力してください。
カテゴリ: "国内株・企業業績", "米国株・海外株", "日米金利・物価・為替", "世界経済・マクロ指標", "世界情勢・地政学", "成長テーマ・新技術", "商品・暗号資産", "不動産・住宅市場", "生活・社会保障", "その他"
[
  {
    "id": 0, 
    "category": "選択したカテゴリ", 
    "summary": "【事実】報道されている確定した事実を1〜2行で簡潔に記載。\\n【プロの推測】その事実を元に、プロとして今後の市場への影響を推測した内容を2〜3行で記載。"
  }
]
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
                    new_articles.append({"title": entry.title, "link": entry.link, "summary": res.get("summary", ""), "category": res.get("category", "その他"), "fetched_at": current_time_str})
    except: pass

news_data.extend(new_articles)
filtered_news_data = [item for item in news_data if (datetime.now(JST) - datetime.fromisoformat(item["fetched_at"])).days <= 3]
with open(DATA_FILE, "w", encoding="utf-8") as f:
    json.dump(filtered_news_data, f, ensure_ascii=False, indent=2)


# --- 指数取得（ETF代替ルート実装） ---
indices_data = {}

# 1. 基本の yfinance
symbols = {
    "^N225": "日本日経平均", 
    "NIY=F": "日経先物", 
    "^TOPX": "日本TOPIX",    # まずは本物のTOPIXに挑戦
    "JPY=X": "為替 ドル円",
    "EURJPY=X": "為替 ユーロ円", 
    "^DJI": "米国NYダウ", 
    "^VIX": "VIX恐怖指数",
    "^JNIV": "日経VI",       # まずは本物の日経VIに挑戦
    "CL=F": "WTI原油先物", 
    "GC=F": "NY金先物", 
    "BTC-JPY": "ビットコイン"
}

for sym, name in symbols.items():
    try:
        hist = yf.Ticker(sym).history(period="5d")
        if len(hist) >= 2:
            prev, curr = hist['Close'].iloc[-2], hist['Close'].iloc[-1]
            change_pct = ((curr - prev) / prev) * 100
            indices_data[name] = {"price": f"{curr:,.2f}", "change": f"{change_pct:.2f}%"}
    except: pass

# 2. 国債（財務省）
try:
    res = requests.get('https://www.mof.go.jp/jgbs/reference/interest_rate/jgbcm.csv', timeout=5)
    res.encoding = 'shift_jis'
    valid_lines = [l.split(',') for l in res.text.strip().split('\n') if l and len(l.split(',')) >= 11 and l.split(',')[10].replace('.', '', 1).isdigit()]
    if len(valid_lines) >= 2:
        val = float(valid_lines[-1][10])
        change = val - float(valid_lines[-2][10])
        indices_data["日本国債10年利回り"] = {"price": f"{val:.3f}%", "change": f"{change:.3f}pt"}
except: pass

# 3. 【超強力裏技】日本TOPIXがブロックされた場合の「ETF代替（1306.T）」ルート
if "日本TOPIX" not in indices_data:
    try:
        hist_etf = yf.Ticker("1306.T").history(period="5d")
        if len(hist_etf) >= 2:
            prev, curr = hist_etf['Close'].iloc[-2], hist_etf['Close'].iloc[-1]
            change_pct = ((curr - prev) / prev) * 100
            # ユーザーが混乱しないよう (ETF代替) と明記
            indices_data["日本TOPIX"] = {"price": f"{curr:,.2f} (ETF代替)", "change": f"{change_pct:.2f}%"}
    except: pass

# 4. 日経VIが yfinance で取れなかった場合の日経公式スクレイピングルート
if "日経VI" not in indices_data:
    try:
        url = "https://indexes.nikkei.co.jp/nkave/index/profile?idx=nk225vi"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        p_vi = soup.find("div", class_="index-value").text.strip()
        c_text = soup.find("div", class_="index-diff").text.strip()
        c_vi = c_text.split("(")[1].replace(")", "").strip() if "(" in c_text else c_text
        if p_vi: indices_data["日経VI"] = {"price": p_vi, "change": c_vi}
    except: pass


# --- スケジュール等取得 ---
SCHEDULE_FILE = "schedule_data.json"
schedule_result_json = {"schedule": "取得中...", "indices": indices_data, "news": "取得中...", "contribution": "取得中..."}

if os.path.exists(SCHEDULE_FILE):
    try:
        with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
            old_data = json.load(f)
            for k in ["schedule", "news", "contribution"]:
                if "エラー" not in old_data.get(k, ""): schedule_result_json[k] = old_data.get(k, schedule_result_json[k])
            
            old_idx = old_data.get("indices", {})
            for k, v in old_idx.items():
                if k not in indices_data:
                    schedule_result_json["indices"][k] = {"price": f"{v.get('price', '')} (※)", "change": v.get('change', '0.0%')}
    except: pass

try:
    headers = {'User-Agent': 'Mozilla/5.0'}
    res_sched = requests.get("https://nikkei225jp.com/schedule/", headers=headers, timeout=10)
    res_sched.encoding = res_sched.apparent_encoding
    text_sched = BeautifulSoup(res_sched.text, "html.parser").get_text(separator=' ', strip=True)[:15000]

    res_min = requests.get("https://fu.minkabu.jp/chart/nikkei225/contribution", headers=headers, timeout=10)
    res_min.encoding = res_min.apparent_encoding
    text_min = BeautifulSoup(res_min.text, "html.parser").get_text(separator=' ', strip=True)[:15000]

    prompt_s = f"""以下のWebページから情報を抽出しJSONで出力してください。
    【重要】必ず `- ` を使ったMarkdownの箇条書きにし、JSONの記号は値の中に含めないでください。
    {{"schedule": "予定を箇条書きで","news": "経済指標を箇条書きで","contribution": "寄与度を箇条書きで"}}
    【データ】\n{text_sched}\n{text_min}"""
    response_s = model.generate_content(prompt_s, safety_settings=safety_settings, generation_config={"response_mime_type": "application/json"})
    if response_s.parts:
        ai_data = json.loads(response_s.text)
        for k in ["schedule", "news", "contribution"]:
            schedule_result_json[k] = ai_data.get(k, schedule_result_json[k])
except: pass

with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
    json.dump(schedule_result_json, f, ensure_ascii=False, indent=2)
