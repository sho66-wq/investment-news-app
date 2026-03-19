import streamlit as st
import json, os

st.set_page_config(page_title="投資ニュースAIサマリー", page_icon="📈", layout="wide")
st.title("📊 個人専用：投資ニュースAIサマリー (100点完成版) 🚀")

SCHEDULE_FILE = "schedule_data.json"
if os.path.exists(SCHEDULE_FILE):
    with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
        d = json.load(f)
    
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col1:
        with st.container(border=True):
            st.markdown("#### 🗓️ 主な予定")
            st.write(d.get('schedule', '☕ データ準備中...'))
    with col2:
        with st.container(border=True):
            st.markdown("#### 📈 指定12指数・為替")
            idx = d.get('indices', {})
            if isinstance(idx, dict):
                m_cols = st.columns(2)
                order = ["日本日経平均", "日経先物", "日本TOPIX", "日本国債10年利回り", "為替 ドル円", "為替 ユーロ円", "米国NYダウ", "VIX恐怖指数", "日経VI", "WTI原油先物", "NY金先物", "ビットコイン"]
                for i, name in enumerate(order):
                    item = idx.get(name, {"price": "取得中", "change": "0.0%"})
                    m_cols[i % 2].metric(label=name, value=item['price'], delta=item['change'])
    with col3:
        with st.container(border=True):
            st.markdown("#### 📰 NEWS（経済指標）")
            st.write(d.get('news', '☕ データ準備中...'))

    st.subheader("🔍 日経225 内部データ")
    with st.container(border=True):
        st.write(d.get('contribution', '☕ データ準備中...'))
        st.link_button("📊 寄与度詳細", "https://fu.minkabu.jp/chart/nikkei225/contribution", use_container_width=True)

st.divider()
DATA_FILE = "news_data.json"
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        news = json.load(f)[::-1]
        cats = ["国内株・企業業績", "米国株・海外株", "日米金利・物価・為替", "世界経済・マクロ指標", "世界情勢・地政学", "成長テーマ・新技術", "商品・暗号資産", "不動産・住宅市場", "生活・社会保障", "その他"]
        res = {c: [] for c in cats}
        for n in news:
            c = n.get("category", "その他")
            if c in res: res[c].append(n)
        tabs = st.tabs(cats)
        for i, c in enumerate(cats):
            with tabs[i]:
                for n in res[c]:
                    st.subheader(n['title'])
                    st.caption(f"{n.get('fetched_at','')} | [🔗記事]({n['link']})")
                    st.info(n['summary'])
