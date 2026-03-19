import streamlit as st
import json
import os
from datetime import datetime

# 画面全体を広く使う「wide」設定
st.set_page_config(page_title="投資ニュースAIサマリー", page_icon="📈", layout="wide")
st.title("📊 個人専用：投資ニュースAIサマリー (自動更新版) 🚀")
st.write("裏方ロボットが定期的に収集・分析した最新の市場データと経済ニュースをストック表示しています。")

# --- 上段：市場データ・予定（広く3列で表示） ---
st.subheader("📅 本日の市場データ・予定")
SCHEDULE_FILE = "schedule_data.json"

if os.path.exists(SCHEDULE_FILE):
    try:
        with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
            sched_data = json.load(f)
            
        # ここで画面を3つの列（カラム）に分割！
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.info(f"**🗓️ 主な予定**\n\n{sched_data.get('schedule', 'データなし')}")
        with col2:
            st.success(f"**📈 指数ランキング**\n\n{sched_data.get('indices', 'データなし')}")
        with col3:
            st.warning(f"**📰 NEWS（経済指標）**\n\n{sched_data.get('news', 'データなし')}")
            
    except Exception:
        st.error("スケジュールの読み込みに失敗しました。")
else:
    st.write("現在、市場データを収集中です...")

st.divider()

# --- 下段：AIニュース分析 ---
DATA_FILE = "news_data.json"
news_data = []

if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            news_data = json.load(f)
            news_data.sort(key=lambda x: x.get("fetched_at", ""), reverse=True)
        except Exception:
            pass

if not news_data:
    st.warning("⏳ 現在表示できるニュースがありません。")
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
                    
                    try:
                        dt = datetime.fromisoformat(item['fetched_at'])
                        formatted_time = dt.strftime("%Y/%m/%d %H:%M")
                    except Exception:
                        formatted_time = "不明"

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
                        
                    st.caption(f"🏢 配信元: **{source}** | ⏱ 取得日時: {formatted_time} | [🔗 元記事を読む]({link})")
                    st.info(item['summary'])
                    st.divider()
