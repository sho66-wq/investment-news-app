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
あなたはプロの機関投資家です。以下の【ニュース一覧】を全て分析し、指定された【JSONフォーマット】で返してください。

【カテゴリの選択肢】
"株式・投資信託", "成長テーマ", "マクロ経済・地政学", "為替・金利", "不動産・生活", "その他"

【JSONフォーマット（この形以外の文字は一切出力しないでください）】
[
  {
    "id": 0,
    "category": "選択したカテゴリ",
    "summary": "今後の市場や取引材料としてどう影響するか、2〜3行の要約"
  }
]

【ニュース一覧】
"""
    for i, entry in enumerate(target_entries):
        prompt += f"ID: {i}\nタイトル: {entry.title}\n\n"

    try:
        response = model.generate_content(prompt, safety_settings=safety_settings)
        if response.parts:
            result_text = response.text.strip()
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]
            
            ai_results = json.loads(result_text.strip())
            
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


# --- 経済指標カレンダー＆主要指数＆みんかぶ寄与度のAIスクレイピング ---
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
    text_sched = soup_sched.get_text(separator='\n')[:6000]

    # ② トップページ（主要12指数用）
    res_top = requests.get("https://nikkei225jp.com/", headers=headers, timeout=15)
    res_top.encoding = res_top.apparent_encoding
    soup_top = BeautifulSoup(res_top.text, "html.parser")
    for script in soup_top(["script", "style"]):
        script.extract()
    text_top = soup_top.get_text(separator='\n')[:6000]

    # ③ みんかぶページ（寄与度・騰落数用）
    res_min = requests.get("https://fu.minkabu.jp/chart/nikkei225/contribution", headers=headers, timeout=15)
    res_min.encoding = res_min.apparent_encoding
    soup_min = BeautifulSoup(res_min.text, "html.parser")
    for script in soup_min(["script", "style"]):
        script.extract()
    # 銘柄名が多いので多めに切り取る
    text_min = soup_min.get_text(separator='\n')[:10000]

    schedule_prompt = f"""
あなたは優秀な金融アシスタントです。以下の3つのWebページデータから情報を抽出し、
必ず以下の【JSONフォーマット】の形のみで出力してください。

【🚨 重要なデザインルール】
見出しや強調したい箇所にはMarkdown（### や **太字**）を使ってください。

【JSONフォーマット】
{{
  "schedule": "【ページ1】から「今週の主な予定」と「本日の主な予定」を見やすく箇条書きで（日付は ### で大きく）",
  "indices": "【ページ2】から以下の12項目の最新値を抽出して箇条書きで（日本日経平均、日経先物、日本TOPIX、日本国債10年利回、為替ドル円、為替 ユーロ円、米国NYダウ、VIX恐怖指数、日経VI、WTI原油先物、NY金先物、ビットコイン）",
  "news": "【ページ1】から「NEWS（経済指標）」を見やすく箇条書きで（日付は ### で大きく）",
  "contribution": "【ページ3】から「日経225銘柄数集計（値上がり数、値下がり数）」と、「値上がり寄与上位」「値下がり寄与上位」をそれぞれ【TOP10銘柄まで】抜粋して箇条書きで見やすく（TOP50だと長すぎるため）"
}}

【ページ1：スケジュール】\n{text_sched}
\n---\n
【ページ2：トップページ】\n{text_top}
\n---\n
【ページ3：みんかぶ寄与度】\n{text_min}
"""
    
    schedule_response = model.generate_content(schedule_prompt, safety_settings=safety_settings)
    if schedule_response.parts:
        res_text = schedule_response.text.strip()
        if res_text.startswith("```json"):
            res_text = res_text[7:]
        if res_text.endswith("```"):
            res_text = res_text[:-3]
        schedule_result_json = json.loads(res_text.strip())
        
except Exception as e:
    schedule_result_json = {"schedule": f"エラー: {e}", "indices": "エラー", "news": "エラー", "contribution": f"エラー: {e}"}

with open("schedule_data.json", "w", encoding="utf-8") as f:
    json.dump(schedule_result_json, f, ensure_ascii=False, indent=2)
