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


# --- 【不死身のハイブリッド】指数の取得（Yahoo + Google Finance） ---
display_lines = {}
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

failed_names = []

# まずYahooファイナンスAPIで一気に取得
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
            failed_names.append(name)
    except Exception:
        failed_names.append(name)

# 取得に失敗した指数（TOPIXなど）があれば、Google Financeから強制取得！
if failed_names:
    gf_urls = {
        "日本日経平均": "https://www.google.com/finance/quote/NI225:INDEXNIK",
        "日経先物": "https://www.google.com/finance/quote/NK2251!:OSE",
        "日本TOPIX": "https://www.google.com/finance/quote/TOPIX:INDEXTKY",
        "日本国債10年利回り": "https://www.google.com/finance/quote/JP10Y:BOND",
        "為替 ドル円": "https://www.google.com/finance/quote/USD-JPY",
        "為替 ユーロ円": "https://www.google.com/finance/quote/EUR-JPY",
        "米国NYダウ": "https://www.google.com/finance/quote/DJI:INDEXDJX",
        "VIX恐怖指数": "https://www.google.com/finance/quote/VIX:INDEXCBOE",
        "日経VI": "https://www.google.com/finance/quote/NI225VIX:INDEXNIK",
        "WTI原油先物": "https://www.google.com/finance/quote/CLW00:NYMEX",
        "NY金先物": "https://www.google.com/finance/quote/GCW00:COMEX",
        "ビットコイン": "https://www.google.com/finance/quote/BTC-JPY"
    }
    
    fallback_text = ""
    headers_gf = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

    for name in failed_names:
        url = gf_urls.get(name)
        if url:
            try:
                res = requests.get(url, headers=headers_gf, timeout=10)
                soup = BeautifulSoup(res.text, "html.parser")
                for s in soup(["script", "style"]): s.extract()
                fallback_text += f"【{name}】\n" + soup.get_text(separator=' ', strip=True)[:3000] + "\n\n"
            except:
                pass

    if fallback_text:
        prompt_missing = f"""
あなたはデータ抽出AIです。以下のWebページテキストから、指定された指数の「最新価格」と「前日比（%）」を抽出してください。

テキストデータ:
{fallback_text}

必ず以下のJSONフォーマットで返してください。見つからない場合は空文字 "" にしてください。
{{
"""
        for i, name in enumerate(failed_names):
            prompt_missing += f'  "{name}_price": "価格",\n'
            prompt_missing += f'  "{name}_change": "前日比（例: +1.23% または -0.45%）"'
            if i < len(failed_names) - 1:
                prompt_missing += ",\n"
            else:
                prompt_missing += "\n"
        prompt_missing += "}"

        try:
            response_missing = model.generate_content(
                prompt_missing, 
                safety_settings=safety_settings,
                generation_config={"response_mime_type": "application/json"}
            )
            if response_missing.parts:
                data_m = json.loads(response_missing.text)
                for name in failed_names:
                    tp = data_m.get(f"{name}_price", "")
                    tc = data_m.get(f"{name}_change", "")
                    if tp and tc:
                        arr_t = f":green[↑ {tc}]" if "+" in tc else (f":red[↓ {tc}]" if "-" in tc else f"({tc})")
                        display_lines[name] = f"- **:blue[{name}]**: {tp} ({arr_t})\n"
                    else:
                        display_lines[name] = f"- **:blue[{name}]**: 取得不可\n"
        except:
            for name in failed_names:
                display_lines[name] = f"- **:blue[{name}]**: 取得不可\n"

# 順番通りに並べて、最後に「クリックできる」リンクを追加
order = [
    "日本日経平均", "日経先物", "日本TOPIX", "日本国債10年利回り",
    "為替 ドル円", "為替 ユーロ円", "米国NYダウ", "VIX恐怖指数",
    "日経VI", "WTI原油先物", "NY金先物", "ビットコイン"
]
indices_text = "".join([display_lines.get(k, f"- **:blue[{k}]**: 取得不可\n") for k in order])

# 【修正】マークダウン形式でリンクをクリック可能にしました
indices_text += "\n*(データ取得元: [Yahoo Finance](https://finance.yahoo.com/) / [Google Finance](https://www.google.com/finance/))*\n"


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
