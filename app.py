import streamlit as st
import json
import os
from datetime import datetime
import ast

def clean_text(text):
    if not isinstance(text, str): return str(text)
    return text.replace("['", "").replace("']", "").replace("', '", "\n")

st.set_page_config(page_title="投資ニュースAIサマリー", page_icon="📈", layout="wide")
st.title("📊 個人専用：投資ニュースAIサマリー (自動更新版) 🚀")
st.write("裏方ロボットが定期的に収集・分析した最新の市場データと経済ニュースをストック表示しています。")

SCHEDULE_FILE = "schedule_data.json"
if os.path.exists(SCHEDULE_FILE):
    try:
        with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
            sched_data = json.load(f)
            
        st.subheader("📅 本日の市場データ・予定")
        col1, col2, col3 = st.columns([1, 1.2, 1])
        
        with col1:
            with st.container(border=True):
                st.markdown("#### 🗓️ 主な予定")
                st.markdown(clean_text(sched_data.get('schedule', '取得中...')))
                
        with col2:
            with st.container(border=True):
                st.markdown("#### 📈 指定12指数・為替")
                indices_data = sched_data.get('indices', {})
                if isinstance(indices_data, dict):
                    order = ["日本日経平均", "日経先物", "日本TOPIX", "日本国債10年利回り", "為替 ドル円", "為替 ユーロ円", "米国NYダウ", "VIX恐怖指数", "日経VI", "WTI原油先物", "NY金先物", "ビットコイン"]
                    m_cols = st.columns(2)
                    for i, name in enumerate(order):
                        d = indices_data.get(name, {"price": "取得不可", "change": "0.0%"})
                        m_cols[i % 2].metric(label=name, value=d['price'], delta=d['change'])
                
        with col3:
            with st.container(border=True):
                st.markdown("#### 📰 NEWS（経済指標）")
                st.markdown(clean_text(sched_data.get('news', '取得中...')))

        st.subheader("🔍 日経225 内部データ（騰落数・寄与度）")
        with st.container(border=True):
            st.markdown(clean_text(sched_data.get('contribution', '取得中...')))
            st.link_button("📊 みんかぶ（全銘柄寄与度）を開く", "https://fu.minkabu.jp/chart/nikkei225/contribution", use_container_width=True)
            st.link_button("🗺️ 日経平均ヒートマップを開く", "https://nikkei225jp.com/chart/nikkei.php", use_container_width=True)
            
    except: st.error("データの読み込みに失敗しました。ロボットの更新をお待ちください。")

st.divider()
DATA_FILE = "news_data.json"
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        news_data = json.load(f)
        news_data.sort(key=lambda x: x.get("fetched_at", ""), reverse=True)
        st.success(f"📈 現在ストックされている有益な記事数: {len(news_data)}件")
        categories = ["国内株・企業業績", "米国株・海外株", "日米金利・物価・為替", "世界経済・マクロ指標", "世界情勢・地政学", "成長テーマ・新技術", "商品・暗号資産", "不動産・住宅市場", "生活・社会保障", "その他"]
        results = {cat: [] for cat in categories}
        for item in news_data:
            cat = item.get("category", "その他")
            title_sum = item.get("title", "") + item.get("summary", "")
            if any(k in title_sum for k in ["トランプ", "台湾", "ロシア", "プーチン", "イラン", "空爆", "地政学"]): cat = "世界情勢・地政学"
            if cat in results: results[cat].append(item)
            else: results["その他"].append(item)
        tabs = st.tabs(categories)
        for i, cat in enumerate(categories):
            with tabs[i]:
                if not results[cat]: st.write("記事はありません。")
                else:
                    for item in results[cat]:
                        st.subheader(f"📰 {item['title']}")
                        st.caption(f"⏱ {item.get('fetched_at','不明')} | [🔗 元記事]({item['link']})")
                        st.info(item['summary'])
                        st.divider()
