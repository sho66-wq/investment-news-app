import os
import json
from datetime import datetime, timedelta, timezone
import feedparser
import google.generativeai as genai

# 日本時間の取得
JST = timezone(timedelta(hours=+9), 'JST')
current_time_str = datetime.now(JST).strftime("%Y/%m/%d %H:%M:%S")

# 診断結果を書き込むためのリスト
diag_log = [f"⏱ 実行日時: {current_time_str}"]

# --- 検査1. APIキーの確認 ---
api_key = os.environ.get("GOOGLE_API_KEY")
if api_key:
    diag_log.append(f"✅ APIキー: 読み込み成功 (長さ: {len(api_key)}文字)")
else:
    diag_log.append("❌ APIキー: 見つかりません（設定エラー）")

# --- 検査2. RSS（ニュースサイト）のブロック確認 ---
rss_urls = [
    "https://www.nhk.or.jp/rss/news/cat6.xml",
    "https://media.rakuten-sec.net/list/feed/rss",
    "https://news.google.com/rss/search?q=%E6%8A%95%E8%B3%87&hl=ja&gl=JP&ceid=JP:ja"
]
for url in rss_urls:
    try:
        feed = feedparser.parse(url)
        entries_count = len(feed.entries)
        domain = url.split("/")[2]
        if entries_count > 0:
            diag_log.append(f"✅ RSS通信 ({domain}): {entries_count}件取得成功")
        else:
            diag_log.append(f"⚠️ RSS通信 ({domain}): 0件（海外サーバーとしてブロックされている可能性大）")
    except Exception as e:
        diag_log.append(f"❌ RSS通信エラー: {e}")

# --- 検査3. AI（Gemini）の生存確認 ---
try:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content("これはテストです。")
    diag_log.append("✅ AI分析: 正常に稼働しています")
except Exception as e:
    diag_log.append(f"❌ AI分析エラー: {type(e).__name__} (制限に引っかかっている可能性あり)")

# --- 診断レポートを「1つのニュース記事」として保存 ---
DATA_FILE = "news_data.json"
diagnostic_article = {
    "title": "🛠️ 【システム診断レポート】現在の状態",
    "link": "https://github.com",
    "summary": "  \n".join(diag_log), # 結果を改行して表示
    "category": "その他",
    "fetched_at": datetime.now(JST).isoformat()
}

with open(DATA_FILE, "w", encoding="utf-8") as f:
    json.dump([diagnostic_article], f, ensure_ascii=False, indent=2)
