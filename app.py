import streamlit as st
import json
import os
from datetime import datetime
import ast

def clean_text(text):
    if not isinstance(text, str):
        return str(text)
    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, dict):
            return "\n\n".join([f"**{k}**\n" + ("\n".join(v) if isinstance(v, list) else str(v)) for k, v in parsed.items()])
        elif isinstance(parsed, list):
            return "\n".join([str(i) for i in parsed])
    except:
        pass
    return text.replace("['", "").replace("']", "").replace("', '", "\n")

st.set_page_config(page_title="投資ニュースAIサマリー", page_icon="📈", layout="wide")
st.title("📊 個人専用：投資ニュースAIサマリー (自動更新版) 🚀")
st.write("裏方ロボットが定期的に収集・分析した最新の市場データと経済ニュースをストック表示しています。")

# --- 上段：市場データ・予定 ---
st.subheader("📅 本日の市場データ・予定")
SCHEDULE_FILE = "schedule_data.json"

if os.path.exists(SCHEDULE_FILE):
    try:
        with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
            sched_data = json.load(f)
            
        col1, col2, col3 = st.columns([1, 1.2, 1])
        
        with col1:
            with st.container(border=True):
                st.markdown("#### 🗓️ 主な予定")
                st.markdown(clean_text(sched_data.get('schedule', 'データなし')))
                
        with col2:
            with st.container(border=True):
                st.markdown("#### 📈 指定12指数・為替")
                
                # 【100点デザイン】テキストの羅列をやめ、カード型のウィジェットを並べる
                indices_data = sched_data.get('indices', {})
                
                if isinstance(indices_data, dict):
                    order = [
                        "日本日経平均", "日経先物", "日本TOPIX", "日本国債10年利回り",
                        "為替 ドル円", "為替 ユーロ円", "米国NYダウ", "VIX恐怖指数",
                        "日経VI", "WTI原油先物", "NY金先物", "ビットコイン"
                    ]
                    
                    # 枠の中にさらに2つのカラムを作って、美しく配置する
                    metric_cols = st.columns(2)
                    for i, name in enumerate(order):
                        data = indices_data.get(name, {"price": "取得不可", "change": "0.0"})
                        price = data.get("price", "取得不可")
                        change = data.get("change", "0.0")
                        
                        # st.metric を使って証券アプリのような美しい表示に！
                        metric_cols[i % 2].metric(label=name, value=price, delta=change)
                else:
                    st.write("データのフォーマットが古いです。次の更新をお待ちください。")
                    
                st.caption("*(データ取得元: [Yahoo](https://finance.yahoo.co.jp/) / [Google](https://www.google.com/finance/) / [財務省](https://www.mof.go.jp/))*")
                st.caption("※価格の横に(※)がある場合は、直近の取得に失敗したため前回のデータを表示しています。")
                
        with col3:
            with st.container(border=True):
                st.markdown("#### 📰 NEWS（経済指標）")
                st.markdown(clean_text(sched_data.get('news', 'データなし')))

        # --- 中段：日経225内部データ ---
        st.subheader("🔍 日経225 内部データ（騰落数・寄与度）")
        with st.container(border=True):
            st.markdown(clean_text(sched_data.get('contribution', '現在データ収集中です...')))
            
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
    
    categories = [
        "国内株・企業業績", "米国株・海外株", "日米金利・物価・為替", "世界経済・マクロ指標", 
        "国際情勢・地政学", "成長テーマ・新技術", "商品・暗号資産", 
        "不動産・住宅市場", "生活・社会保障", "その他"
    ]
    
    results = {cat: [] for cat in categories}
    
    legacy_mapping = {
        "株式・投資信託": "国内株・企業業績",
        "マクロ経済・地政学": "国際情勢・地政学",
        "世界情勢・地政学": "国際情勢・地政学",
        "為替・金利": "日米金利・物価・為替",
        "不動産・生活": "生活・社会保障",
        "成長テーマ": "成長テーマ・新技術"
    }
    
    for item in news_data:
        cat = item.get("category", "その他")
        title_summary = item.get("title", "") + item.get("summary", "")
        
        if cat in legacy_mapping:
            cat = legacy_mapping[cat]
            
        if any(k in title_summary for k in ["トランプ", "台湾", "ロシア", "ウクライナ", "プーチン", "イラン", "空爆", "報復", "制裁", "紛争", "外交", "地政学", "ユダヤ", "サイバー攻撃", "ウラン"]):
            cat = "国際情勢・地政学"
        elif any(k in title_summary for k in ["原油", "バレル", "経済悪影響", "インフレ"]):
            cat = "世界経済・マクロ指標"
        
        if cat not in categories:
            cat = "その他"
            
        results[cat].append(item)

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
