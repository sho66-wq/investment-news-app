import streamlit as st
import json
import os
from datetime import datetime

st.set_page_config(page_title="投資ニュースAIサマリー", page_icon="📈", layout="wide")

st.title("📊 個人専用：投資ニュースAIサマリー (自動更新版)")
st.write("裏方ロボットが定期的に収集・分析した最新の市場データと経済ニュースをストック表示しています。")

SCHEDULE_FILE = "schedule_data.json"
sched_data = {}
if os.path.exists(SCHEDULE_FILE):
    try:
        with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
            sched_data = json.load(f)
    except: pass

# 左 1.2 : 右 2.5 のレイアウト
col_left, col_right = st.columns([1.2, 2.5])

# ----------------------------------------
# 【左側カラム】市況ボード ＋ 内部データ
# ----------------------------------------
with col_left:
    st.subheader("📈 リアルタイム市況")
    
    indices_data = sched_data.get('indices', {})
    if isinstance(indices_data, dict) and indices_data:
        order = ["日本日経平均", "日経先物", "日本TOPIX", "日本国債10年利回り", "為替 ドル円", "為替 ユーロ円", "米国NYダウ", "VIX恐怖指数", "日経VI", "WTI原油先物", "NY金先物", "ビットコイン"]
        
        html_board = "<style>.market-board { width: 100%; border-collapse: collapse; font-family: sans-serif; box-shadow: 0 1px 3px rgba(0,0,0,0.2); border-radius: 4px; overflow: hidden; } .market-board tr { border-bottom: 1px solid #ddd; background-color: #fff; } .market-board td { padding: 10px 8px; vertical-align: middle; } .market-board .name-col { width: 35%; background-color: #424242; color: #fff; font-weight: bold; font-size: 13px; text-align: left; border-right: 1px solid #555;} .market-board .price-col { width: 35%; font-size: 18px; font-weight: bold; text-align: right; color: #333; } .market-board .change-col { width: 30%; font-size: 14px; font-weight: bold; text-align: right; } .change-up { color: #d32f2f; background-color: #ffebee; border-radius: 3px; padding: 4px; display: inline-block;} .change-down { color: #2e7d32; background-color: #e8f5e9; border-radius: 3px; padding: 4px; display: inline-block;} .change-flat { color: #555; background-color: #f5f5f5; border-radius: 3px; padding: 4px; display: inline-block;} </style><table class='market-board'>"
        
        for name in order:
            d = indices_data.get(name, {"price": "取得不可", "change": "0.0%"})
            p = d.get('price', '取得不可')
            c = str(d.get('change', '0.0%'))
            
            if "-" in c:
                change_class = "change-down"
            elif "+" in c or (c != "0.0%" and c != "0.0pt" and "取得不可" not in c):
                change_class = "change-up"
                if not c.startswith("+"): c = "+" + c
            else:
                change_class = "change-flat"
                
            html_board += f"<tr><td class='name-col'>{name}</td><td class='price-col'>{p}</td><td class='change-col'><span class='{change_class}'>{c}</span></td></tr>"
            
        html_board += "</table>"
        st.markdown(html_board, unsafe_allow_html=True)
    else:
        st.write("データを収集中です。")
        
    st.write("")
    st.caption("*(データ取得元: [Yahoo Finance](https://finance.yahoo.co.jp/) / [Google Finance](https://www.google.com/finance/) / [財務省](https://www.mof.go.jp/) / [日経プロフィル](https://indexes.nikkei.co.jp/))*")

    st.write("") # 少し隙間を空ける
    
    # ▼▼ ここに右側から「日経225内部データ」をお引越ししました！ ▼▼
    st.subheader("🔍 日経225 内部データ")
    with st.container(border=True):
        st.markdown(sched_data.get('contribution', 'データ収集中...'))
        
        # 細いカラムに合わせて、ボタンを横並びではなく「縦積み」にしています
        st.link_button("📊 みんかぶ（全銘柄寄与度）を開く", "https://fu.minkabu.jp/chart/nikkei225/contribution", use_container_width=True)
        st.link_button("🗺️ 日経平均ヒートマップを開く", "https://nikkei225jp.com/chart/nikkei.php", use_container_width=True)


# ----------------------------------------
# 【右側カラム】スケジュール ＋ ニュース（経済指標）
# ----------------------------------------
with col_right:
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


st.divider()

# ----------------------------------------
# 【下段】AIニュース分析
# ----------------------------------------
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
                        st.info(item.get('summary', ''))
                        st.divider()
