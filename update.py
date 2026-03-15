import os
import json
import random
from datetime import datetime, timedelta, timezone
import feedparser
import google.generativeai as genai

# アクセス拒否対策
feedparser.USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)

# 最新モデルを指定
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

if len(news_data) < 5:
    news_data = []

existing_urls = set([item.get("link", "") for item in news_data])

rss_urls = [
    "https://www.nhk.or.jp/rss/news/cat6.xml",
    "https://news.google.com/rss/search?q=%E6%8A%95%E8%B3%87+OR+%E7%B5%8C%E6%B8%88+OR+%E7%82%BA%E6%9B%BF&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=%E6%A0%AA%E5%BC%8F%E4%BC%9A%E7%A4%BE+OR+%E6%A5%AD%E7%B8%BE+OR+%E6%B1%BA%E7%AE%97&hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/search?q=%E5%AE%87%E5%AE%99+OR+%E9%98%B2%E8%A1%9B+OR+%E3%82%B5%E3%82%A4%E3%83%90%E3%83%BC+OR+%E3%83%AC%E3%82%A2%E3%82%A2%E3%83%BC%E3%82%B9&hl=ja&gl=JP&ceid=JP:ja"
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
                if count >= 6:
                    break
    except Exception:
        pass

random.shuffle(all_entries)
# 1回の処理で最大15件を「まとめ買い」
target_entries = all_entries[:15]

JST = timezone(timedelta(hours=+9), 'JST')
current_time_str = datetime.now(JST).isoformat()
new_articles = []

if target_entries:
    # 15件のニュースを1つのプロンプトにまとめる（API枠の節約）
    prompt = "あなたはプロの機関投資家です。以下の複数のニュースを分析し、指定されたJSON形式で出力してください。\n\n"
    for i, entry in enumerate(target_entries):
        prompt += f"[{i}] タイトル: {entry.title}\n"
        
    prompt += """
【指示】
それぞれのニュースについて、以下の6つのカテゴリから最も関連性が高いものを1つ選び、今後の市場や取引材料としてどう影響するか2〜3行で要約してください。
カテゴリ: [株式・投資信託, 成長テーマ, マクロ経済・地政学, 為替・金利, 不動産・生活, その他]

【出力フォーマット（必ず以下の厳密なJSON配列のみを出力してください。バッククォートなどの装飾は不要です）】
[
  {
    "id": 0,
    "category": "カテゴリ名",
    "summary": "要約テキスト"
  },
  {
    "id": 1,
    "category": "カテゴリ名",
    "summary": "要約テキスト"
  }
]
"""
    try:
        # 1日20回の貴重な枠を「1回」だけ使って、全員分を一気に分析させる
        response = model.generate_content(prompt)
        ai_text = response.text
        
        # Markdownの装飾が含まれていた場合は除去する
        if "```json" in ai_text:
            ai_text = ai_text.split("```json")[1].split("```")[0]
        elif "```" in ai_text:
            ai_text = ai_text.split("```")[1].split("```")[0]
            
        results = json.loads(ai_text.strip())
        
        # 分析結果と元のURLを結合
        for res in results:
            idx = res.get("id")
            if idx is not None and 0 <= idx < len(target_entries):
                entry = target_entries[idx]
                new_articles.append({
                    "title": entry.title,
                    "link": entry.link,
                    "summary": res.get("summary", "要約に失敗しました。"),
                    "category": res.get("category", "その他"),
                    "fetched_at": current_time_str
                })
    except Exception as e:
        # 枠がまだ回復していない場合はここに入ります
        new_articles.append({
            "title": "🚨 AI分析エラー（容量制限の可能性）",
            "link": "https://github.com",
            "summary": f"APIの無料枠制限、または出力エラーが発生しました。\n詳細: {str(e)}",
            "category": "その他",
            "fetched_at": current_time_str
        })

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
