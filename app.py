import streamlit as st
import json
import os
from datetime import datetime

st.set_page_config(page_title="投資ニュースAIサマリー", page_icon="📈", layout="wide")

# スタイルの調整：コンテナ間の余白を詰める
st.markdown("""
<style>
div[data-testid="stMetricValue"] { font-size: 1.5rem; }
</style>
""", unsafe_allow_html=True)

st.title("📊 個人専用：投資ニュースAIサマリー (自動更新版)")
st.write("裏方ロボットが定期的に収集・分析した最新の市場データと経済ニュースをストック表示しています。")

SCHEDULE_FILE = "schedule_data.json"
sched_data = {}
if os.path.exists(SCHEDULE_FILE):
    try:
        with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
            sched_data = json.load(f)
    except: pass

# --- nikkei225jp 風レイアウト (左 1 : 右 2.5) ---
col_left, col_right = st.columns([1, 2.5])

with col_left:
    st.subheader("📈 リアルタイム市況")
    with st.container(border=True):
        indices_data = sched_data.get('indices', {})
        if isinstance(indices_data, dict) and indices_data:
            order = ["日本日経平均", "日経先物", "日本TOPIX", "日本国債10年利回り", "為替 ドル円", "為替 ユーロ円", "米国NYダウ", "VIX恐怖指数", "日経VI", "WTI原油先物", "NY金先物", "ビットコイン"]
            for name in order:
                d = indices_data.get(name, {"price": "取得不可", "change": "0.0%"})
                # 縦一列に並べる
                st.metric(label=name, value=d.get('price', '取得不可'), delta=d.get('change', '0.0%'))
        else:
            st.write("データを収集中です。")
            
        st.divider()
        st.markdown("**出典元リンク:**")
        st.markdown("- [Yahoo!ファイナンス](https://finance.yahoo.co.jp/)")
        st.markdown("- [Google Finance](https://www.google.com/finance/)")
        st.markdown("- [財務省(国債)](https://www.mof.go.jp/)")

with col_right:
    # 上半分：スケジュールとニュース
    st.subheader("📅 本日の市場データ・予定")
    col_sched, col_news = st.columns(2)
    with col_sched:
        with st.container(border=True):
            st.markdown("#### 🗓️ 主な予定")
            st.markdown(sched_data.get('schedule', 'データ収集中...'))
    with col_news:
        with st.container(border=True):
            st.markdown("#### 📰 経済指標")
            st.markdown(sched_data.get('news', 'データ収集中...'))

    # 下半分：寄与度とヒートマップリンク
    st.subheader("🔍 日経225 内部データ（騰落数・寄与度）")
    with st.container(border=True):
        st.markdown(sched_data.get('contribution', 'データ収集中...'))
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            st.link_button("📊 みんかぶ（全銘柄寄与度）を開く", "https://fu.minkabu.jp/chart/nikkei225/contribution", use_container_width=True)
        with col_btn2:
            st.link_button("🗺️ 日経平均ヒートマップを開く", "https://nikkei225jp.com/chart/nikkei.php", use_container_width=True)

st.divider()

# --- 下段：AIニュース分析 ---
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
            
            # 【事実】と【推測】を含む強力な要約フォーマットに対応
            if any(k in title_sum for k in ["トランプ", "台湾", "ロシア", "プーチン", "イラン", "空爆", "地政学", "ミサイル"]): cat = "世界情勢・地政学"
            if any(k in title_sum for k in ["原油", "バレル", "経済悪影響", "インフレ"]): cat = "世界経済・マクロ指標"
            
            if cat in results: results[cat].append(item)
            else: results["その他"].append(item)
            
        tabs = st.tabs(categories)
        for i, cat in enumerate(categories):
            with tabs[i]:
                if not results[cat]: st.write("このカテゴリの記事は現在ありません。")
                else:
                    for item in results[cat]:
                        st.subheader(f"📰 {item['title']}")
                        try:
                            dt = datetime.fromisoformat(item.get('fetched_at', ''))
                            f_time = dt.strftime("%Y/%m/%d %H:%M")
                        except: f_time = "不明"
                        st.caption(f"⏱ 取得日時: {f_time} | [🔗 元記事を読む]({item.get('link', '')})")
                        # Markdown形式で【事実】と【プロの推測】を表示
                        st.markdown(item.get('summary', ''))
                        st.divider()
