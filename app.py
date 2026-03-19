import streamlit as st
import json
import os
from datetime import datetime

st.set_page_config(page_title="投資ニュースAI", page_icon="📈", layout="wide")
st.title("投資ニュースAIまとめ　 (自動更新版)")
st.write("裏方ロボットが定期的に収集・分析した最新の経済ニュースをストック表示しています。（直近3日間を保持）")

DATA_FILE = "news_data.json"
news_data = []

if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            news_data = json.load(f)
            # データを「取得日時」の新しい順に並び替える
            news_data.sort(key=lambda x: x.get("fetched_at", ""), reverse=True)
        except Exception:
            pass

if not news_data:
    st.warning("⏳ 現在表示できるニュースがありません。裏方ロボットが初回のデータ収集を終えるまで数分お待ちください。")
else:
    st.success(f"📈 現在ストックされている有益な記事数: {len(news_data)}件")
    
    categories = ["株式・投資信託", "成長テーマ", "マクロ経済・地政学", "為替・金利", "不動産・生活", "その他"]
    results = {cat: [] for cat in categories}
    
    for item in news_data:
        cat = item.get("category", "その他")
        if cat in results:
            results[cat].append(item)
        else:
            results["その他"].append(item)

    tabs = st.tabs(categories)
    
    for i, cat in enumerate(categories):
        with tabs[i]:
            if len(results[cat]) == 0:
                st.write("このカテゴリのニュースは現在ありません。")
            else:
                for item in results[cat]:
                    st.subheader(f"📰 {item['title']}")
                    
                    # 取得日時のフォーマット
                    try:
                        dt = datetime.fromisoformat(item['fetched_at'])
                        formatted_time = dt.strftime("%Y/%m/%d %H:%M")
                    except Exception:
                        formatted_time = "不明"

                    # 【追加機能】URLから配信元サイトを自動判定する
                    link = item.get('link', '')
                    if 'yahoo.co.jp' in link:
                        source = "Yahoo!ニュース"
                    elif 'nhk.or.jp' in link:
                        source = "NHKニュース"
                    elif 'rakuten-sec.net' in link:
                        source = "トウシル (楽天証券)"
                    elif 'google' in link:
                        source = "Googleニュース"
                    else:
                        source = "外部ニュースサイト"
                        
                    # 配信元（🏢）を追加して表示
                    st.caption(f"🏢 配信元: **{source}** | ⏱ 取得日時: {formatted_time} | [🔗 元記事を読む]({link})")
                    st.info(item['summary'])
                    st.divider()
