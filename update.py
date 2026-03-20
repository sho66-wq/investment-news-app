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
    # 【継続】事実と推測を完全に分けて出力させる厳格な指示
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
※summaryの中身は必ず「【事実】」と「【プロの推測】」の2つの見出しを含め、改行（\\n）で分けて出力してください。「要約中」などの手抜きは絶対禁止です。
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

# --- 指数取得 ---
indices_data = {}

# 1. まず yfinance で取れるものを確保
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

# 2. ご指定のサイト (nikkei225jp.com/chart/) からの直接取得にチャレンジ！
try:
    headers = {'User-Agent': 'Mozilla/5.0'}
    res_chart = requests.get("https://nikkei225jp.com/chart/", headers=headers, timeout=10)
    soup_chart = BeautifulSoup(res_chart.text, "html.parser")
    for script in soup_chart(["script", "style"]): script.extract()
    text_chart = soup_chart.get_text(separator=' ', strip=True)

    # 幻覚を防ぐため、非常に厳格なAI抽出プロンプトを使用
    prompt_chart = f"""
    あなたはデータ抽出AIです。以下のテキストはリアルタイム市況サイトの生データです。
    ここから「日本TOPIX」「日経VI」「日本国債10年利回り」の【最新価格】と【前日比】を抽出してください。
    ※重要警告※ サイトの仕様（JavaScript等）により、テキスト内に数字が存在しない場合があります。もしテキスト内に該当する指標の明確な数値がない場合は、絶対に推測せず、必ず "取得不可" と出力してください。日経平均など他の数字と間違えないでください。

    出力形式 (JSON):
    {{
      "日本TOPIX_price": "価格（例: 3609.40 または 取得不可）",
      "日本TOPIX_change": "前日比（例: +2.91% または 取得不可）",
      "日経VI_price": "価格（例: 35.07 または 取得不可）",
      "日経VI_change": "前日比（例: +8.11% または 取得不可）",
      "日本国債10年利回り_price": "価格（例: 2.282 または 取得不可）",
      "日本国債10年利回り_change": "前日比（例: +0.067 または 取得不可）"
    }}

    テキストデータ:
    {text_chart[:6000]}
    """
    response_chart = model.generate_content(prompt_chart, safety_settings=safety_settings, generation_config={"response_mime_type": "application/json"})
    if response_chart.parts:
        c_data = json.loads(response_chart.text)
        
        if c_data.get("日本TOPIX_price") and "取得不可" not in c_data.get("日本TOPIX_price"):
            indices_data["日本TOPIX"] = {"price": c_data["日本TOPIX_price"], "change": c_data.get("日本TOPIX_change", "0.0%")}
            
        if c_data.get("日経VI_price") and "取得不可" not in c_data.get("日経VI_price"):
            indices_data["日経VI"] = {"price": c_data["日経VI_price"], "change": c_data.get("日経VI_change", "0.0%")}
            
        if c_data.get("日本国債10年利回り_price") and "取得不可" not in c_data.get("日本国債10年利回り_price"):
            indices_data["日本国債10年利回り"] = {"price": c_data["日本国債10年利回り_price"], "change": c_data.get("日本国債10年利回り_change", "0.0")}
except: pass

# 3. 万が一、指定サイトがJavaScriptで空っぽだった場合の最強の予備ルート（財務省＆株探）
if "日本国債10年利回り" not in indices_data:
    try:
        res = requests.get('https://www.mof.go.jp/jgbs/reference/interest_rate/jgbcm.csv', timeout=5)
        res.encoding = 'shift_jis'
        lines = [line.split(',') for line in res.text.strip().split('\n') if line]
        valid_lines = [l for l in lines if len(l) >= 11 and l[10].replace('.', '', 1).isdigit()]
        if len(valid_lines) >= 2:
            val = float(valid_lines[-1][10])
            change = val - float(valid_lines[-2][10])
            indices_data["日本国債10年利回り"] = {"price": f"{val:.3f}%", "change": f"{change:.3f}pt"}
    except: pass

if "日本TOPIX" not in indices_data:
    try:
        res_t = requests.get("https://kabutan.jp/stock/?code=0010", headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        soup_t = BeautifulSoup(res_t.text, "html.parser")
        p_topix = soup_t.find(class_="vdt-eq-a").text.strip()
        c_topix = soup_t.find(class_="vdt-cv-a").text.strip()
        if p_topix: indices_data["日本TOPIX"] = {"price": p_topix, "change": c_topix}
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
