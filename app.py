import streamlit as st
import json
import os
from datetime import datetime
import ast
import streamlit.components.v1 as components  # TradingView埋め込みに必要

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
st.write("裏方ロボットが集めたニュースと、TradingViewのリアルタイム市況（20分遅れ含む）を表示しています。")

# --- 上段：市場データ・予定 ---
st.subheader("📅 本日の市場データ・予定")
SCHEDULE_FILE = "schedule_data.json"

if os.path.exists(SCHEDULE_FILE):
    try:
        with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
            sched_data = json.load(f)
            
        # カラムの幅を微調整（真ん中の TradingViewボードを少し広く）
        col1, col2, col3 = st.columns([1, 1.8, 1])
        
        with col1:
            with st.container(border=True):
                st.markdown("#### 🗓️ 主な予定")
                st.markdown(clean_text(sched_data.get('schedule', 'データなし')))
                
        with col2:
            with st.container(border=True):
                st.markdown("#### 📈 リアルタイム市況 (TradingView)")
                
                # 【裏技】TradingView の Market Overview ウィジェットを HTML/JS で埋め込み
                # 指定した12個の主要指標をタブ切り替えで表示します
                tradingview_html = """
                <div class="tradingview-widget-container">
                  <div class="tradingview-widget-container__widget"></div>
                  <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-market-overview.js" async>
                  {
                  "colorTheme": "light",
                  "dateRange": "12M",
                  "showChart": true,
                  "locale": "ja",
                  "width": "100%",
                  "height": 550,
                  "largeChartUrl": "",
                  "isTransparent": false,
                  "showSymbolLogo": true,
                  "showFloatingTooltip": false,
                  "tabs": [
                    {
                      "title": "日本市場",
                      "symbols": [
                        { "proName": "OSE:NI2251!", "title": "日経平均先物" },
                        { "proName": "TSE:TOPIX", "title": "TOPIX" },
                        { "proName": "TVC:JP10Y", "title": "日本国債10年利回り" },
                        { "proName": "CAPITALCOM:VIXNK", "title": "日経VI" }
                      ]
                    },
                    {
                      "title": "為替・米国・商品",
                      "symbols": [
                        { "proName": "FX:USDJPY", "title": "ドル/円" },
                        { "proName": "FX:EURJPY", "title": "ユーロ/円" },
                        { "proName": "CBOT:YM1!", "title": "NYダウ先物" },
                        { "proName": "CME_MINI:ES1!", "title": "S&P500先物" },
                        { "proName": "CME:NQ1!", "title": "ナスダック先物" },
                        { "proName": "NYMEX:CL1!", "title": "WTI原油先物" },
                        { "proName": "COMEX:GC1!", "title": "NY金先物" },
                        { "proName": "BITSTAMP:BTCJPY", "title": "ビットコイン" }
                      ]
                    }
                  ]
                }
                  </script>
                </div>
                """
                # Streamlitの中にHTMLを表示させる（高さはウィジェットに合わせて微調整）
                components.html(tradingview_html, height=560)
                
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
            #fetched_at で降順ソート
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
        
        # ① まず古いカテゴリ名を変換
        if cat in legacy_mapping:
            cat = legacy_mapping[cat]
            
        # ② 【超強力・強制仕分け】中身を見て、間違った箱に入っていても力ずくで正しい箱へ移動！
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
