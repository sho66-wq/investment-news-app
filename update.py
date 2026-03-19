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

【カテゴリの選択肢と分類の絶対基準】
1. "国内株・企業業績": 日本企業の決算、個別銘柄の動向
2. "米国株・海外株": 米国など海外企業の動向
3. "日米金利・物価・為替": FRB・日銀の金融政策、物価変動、ドル円などの為替動向
4. "世界経済・マクロ指標": 各国の景気動向、雇用、原油高などによる世界経済全体への影響
5. "世界情勢・地政学": トランプ大統領などの要人発言、台湾情勢、米中関係、ロシア・ウクライナ問題、経済制裁、安全保障リスク
6. "成長テーマ・新技術": AI、サイバーセキュリティ、宇宙開発、防衛関連、レアアースなど
7. "商品・暗号資産": 原油先物市場の価格変動、金、ビットコイン
8. "不動産・住宅市場": 持ち家と賃貸の比較、マイホーム購入動向、住宅ローン金利など
9. "生活・社会保障": 家計（食費等）、税金、年金、社会保障制度、ポイント経済など
10. "その他": 上記に当てはまらない一般的なニュース

[
  {
    "id": 0,
    "category": "選択したカテゴリ",
    "summary": "今後の市場や生活にどう影響するか、2〜3行の要約"
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


# --- 【二刀流ハイブリッド】指数の取得 ---
display_lines = {}
symbols = {
    "^N225": "日本日経平均",
    "NIY=F": "日経先物",
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
            change = current - prev_close
            change_pct = (change / prev_close) * 100
            
            if change_pct > 0:
                arrow = f":green[↑ +{change_pct:.2f}%]"
            elif change_pct < 0:
                arrow = f":red[↓ {change_pct:.2f}%]"
            else:
                arrow = "±0.00%"
                
            price_str = f"{current:.2f}" if current < 1000 else f"{current:,.2f}"
            display_lines[name] = f"- **:blue[{name}]**: {price_str} ({arrow})\n"
        else:
            display_lines[name] = f"- **:blue[{name}]**: 取得不可\n"
    except Exception:
        display_lines[name] = f"- **:blue[{name}]**: 取得不可\n"

try:
    url_topix = "https://finance.yahoo.co.jp/quote/998405.O"
    url_jgb = "https://finance.yahoo.co.jp/quote/035240069.FX"
    headers_yf = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    
    res_t = requests.get(url_topix, headers=headers_yf, timeout=10)
    soup_t = BeautifulSoup(res_t.text, "html.parser")
    for s in soup_t(["script", "style"]): s.extract()
    text_t = soup_t.get_text(separator=' ', strip=True)[:3000]
    
    res_j = requests.get(url_jgb, headers=headers_yf, timeout=10)
    soup_j = BeautifulSoup(res_j.text, "html.parser")
    for s in soup_j(["script", "style"]): s.extract()
    text_j = soup_j.get_text(separator=' ', strip=True)[:3000]

    prompt_missing = f"""
    あなたはデータ抽出AIです。以下の2つのWebページから、TOPIXと日本国債10年利回りの「最新価格」と「前日比」を抽出してください。
    【ページ1（TOPIX）】\n{text_t}
    【ページ2（日本国債）】\n{text_j}
    必ず以下のJSONフォーマットで返してください。
    {{
      "topix_price": "価格の数字のみ",
      "topix_change": "前日比の数字のみ（例: +10.50）",
      "jgb_price": "利回りの数字のみ（例: 0.750）",
      "jgb_change": "前日比の数字のみ（例: -0.010）"
    }}
    """
    response_missing = model.generate_content(
        prompt_missing, 
        safety_settings=safety_settings,
        generation_config={"response_mime_type": "application/json"}
    )
    if response_missing.parts:
        data_m = json.loads(response_missing.text)
        
        tp = data_m.get("topix_price", "")
        tc = data_m.get("topix_change", "")
        if tp and tc and "取得" not in tp:
            arr_t = f":green[↑ {tc}]" if "+" in tc else (f":red[↓ {tc}]" if "-" in tc else "±0")
            display_lines["日本TOPIX"] = f"- **:blue[日本TOPIX]**: {tp} ({arr_t})\n"
        else:
            display_lines["日本TOPIX"] = f"- **:blue[日本TOPIX]**: 取得不可\n"
            
        jp = data_m.get("jgb_price", "")
        jc = data_m.get("jgb_change", "")
        if jp and jc and "取得" not in jp:
            arr_j = f":green[↑ {jc}%]" if "+" in jc else (f":red[↓ {jc}%]" if "-" in jc else "±0%")
            if "%" not in jp: jp += "%"
            display_lines["日本国債10年利回り"] = f"- **:blue[日本国債10年利回り]**: {jp} ({arr_j})\n"
        else:
            display_lines["日本国債10年利回り"] = f"- **:blue[日本国債10年利回り]**: 取得不可\n"
except Exception as e:
    display_lines["日本TOPIX"] = f"- **:blue[日本TOPIX]**: 取得不可\n"
    display_lines["日本国債10年利回り"] = f"- **:blue[日本国債10年利回り]**: 取得不可\n"

order = [
    "日本日経平均", "日経先物", "日本TOPIX", "日本国債10年利回り",
    "為替 ドル円", "為替 ユーロ円", "米国NYダウ", "VIX恐怖指数",
    "日経VI", "WTI原油先物", "NY金先物", "ビットコイン"
]
indices_text = "".join([display_lines.get(k, f"- **:blue[{k}]**: 取得不可\n") for k in order])
indices_text += "\n*(データ取得元: Yahoo Finance / Yahoo!ファイナンス)*\n"


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
各値は配列や辞書にせず、1つの長い文字列にしてください。箇条書きは「- 」と改行「\\n」を使ってください。

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
