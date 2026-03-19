import streamlit as st
import json
import os
from datetime import datetime

st.set_page_config(page_title="投資ニュースAIサマリー", page_icon="📈", layout="wide")
st.title("📊 個人専用：投資ニュースAIサマリー (自動更新版) 🚀")
st.write("裏方ロボットが定期的に収集・分析した最新の市場データと経済ニュースをストック表示しています。")

# --- 上段：市場データ・予定（広く、見やすい枠線デザイン） ---
st.subheader("📅 本日の市場データ・予定")
SCHEDULE_FILE = "schedule_data.json"

if os.path.exists(SCHEDULE_FILE):
    try:
        with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
            sched_data = json.load(f)
            
        # 3列のレイアウト
        col1, col2, col3 = st.columns(3)
        
        with col1:
            with st.container(border=True):
                st.markdown("#### 🗓️ 主な予定")
                st.markdown(sched_data.get('schedule', 'データなし'))
                
        with col2:
            with st.container(border=True):
                st.markdown("#### 📈 指定12指数・為替")
                st.markdown(sched_data.get('indices', 'データなし'))
                
        with col3:
            with st.container(border=True):
                st.markdown("#### 📰 NEWS（経済指標）")
                st.markdown(sched_data.get('news', 'データなし'))

        # --- 新設：日経225内部データ（騰落・寄与度） ---
        st.subheader("🔍 日経225 内部データ（騰落数・寄与度）")
        with st.container(border=True):
            st.markdown(sched_data.get('contribution', '現在データ収集中です...'))
            
            # ヒートマップへの導線ボタン
            st.caption("※TOP50銘柄や、ヒートマップ（面積グラフ）などのさらに詳細な情報は以下のリンクから確認できます。")
            st.link_button("📊 みんかぶ（全銘柄寄与度）を開く", "https://fu.minkabu.jp/chart/nikkei225/contribution", use_container_width=True)
            st.link_button("🗺️ 日経平均ヒートマップを開く", "https://nikkei225jp.com/chart/nikkei.php", use_container_width=True)
            
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
