import streamlit as st
import feedparser
import google.generativeai as genai
import time
import random

# --- 1. APIキーの設定 ---
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
except Exception as e:
    st.error("APIキーが設定されていません。StreamlitのSecrets設定を確認してください。")
    st.stop()

# モデル選択
available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
preferred_models = ['models/gemini-2.5-flash', 'models/gemini-1.5-flash', 'models/gemini-1.5-pro']
selected_model = next((pm for pm in preferred_models if pm in available_models), available_models[0] if available_models else None)
model = genai.GenerativeModel(selected_model.replace("models/", ""))

# --- 2. 画面のデザイン ---
st.set_page_config(page_title="投資ニュースAIサマリー", page_icon="📈", layout="wide")
st.title("📊 個人専用：投資ニュースAIサマリー")

# 取得先が増えたので、最大件数も少し増やしておきます
news_count = st.slider("取得するニュースの総件数を選んでください", min_value=10, max_value=50, value=20, step=5)

if st.button("🔄 ニュースを取得して分析開始"):
    
    categories = ["金融", "為替", "株式投資", "投資市場", "世界経済情勢", "日本経済情勢", "その他"]
    results = {cat: [] for cat in categories}
    
    # 【大幅強化】プロ向けの情報源と特定セクターのレーダーを追加
    rss_urls = [
        "https://news.yahoo.co.jp/rss/topics/business.xml", # Yahoo!ビジネス
        "https://www.nhk.or.jp/rss/news/cat6.xml",           # NHK 経済
        "https://news.yahoo.co.jp/rss/media/bloom_st/all.xml", # ブルームバーグ（Yahoo経由）
        "https://media.rakuten-sec.net/list/feed/rss",      # トウシル（楽天証券の投資メディア）
        "https://news.google.com/rss/search?q=%E6%8A%95%E8%B3%87+OR+%E6%A0%AA%E5%BC%8F+OR+%E7%82%BA%E6%9B%BF&hl=ja&gl=JP&ceid=JP:ja", # Googleニュース (投資全般)
        "https://news.google.com/rss/search?q=%E5%AE%87%E5%AE%99+OR+%E9%98%B2%E8%A1%9B+OR+%E3%82%B5%E3%82%A4%E3%83%90%E3%83%BC+OR+%E3%83%AC%E3%82%A2%E3%82%A2%E3%83%BC%E3%82%B9+OR+%E3%82%A8%E3%83%8D%E3%83%AB%E3%82%AE%E3%83%BC&hl=ja&gl=JP&ceid=JP:ja" # Googleニュース (成長セクター特化)
    ]
    
    all_entries = []
    
    # 各サイトから均等に記事を取得する
    count_per_site = news_count // len(rss_urls)
    # 割り切れなかった分の余りを補正
    count_per_site = count_per_site if count_per_site > 0 else 1 

    for url in rss_urls:
        try:
            feed = feedparser.parse(url)
            all_entries.extend(feed.entries[:count_per_site])
        except Exception:
            pass # どこかのサイトが一時的に落ちていても無視して進む
        
    # 記事の順番をランダムに混ぜる
    random.shuffle(all_entries)
    
    target_entries = all_entries[:news_count]

    progress_text = "世界中のメディアからニュースを集め、AIが分析中..."
    my_bar = st.progress(0, text=progress_text)
    
    for i, entry in enumerate(target_entries):
        title = entry.title
        link = entry.link
        
        prompt = f"""
        あなたはプロの機関投資家です。以下のニュースを分析してください。
        ニュースタイトル: {title}
        
        【指示】
        1. 以下のカテゴリから最も適切なものを1つだけ選び、必ず「【カテゴリ】〇〇」という形式で1行目に書いてください。
           [金融、為替、株式投資、投資市場、世界経済情勢、日本経済情勢、その他]
        2. 市場や株価への影響を2〜3行で要約してください。
        3. 特に、防衛、エネルギー、宇宙、サイバー、レアアースなどの成長セクターや中東情勢に関連する場合は見解を加えてください。
        """
        
        try:
            response = model.generate_content(prompt)
            ai_text = response.text
            
            detected_category = "その他"
            for cat in categories:
                if f"【カテゴリ】{cat}" in ai_text or f"【カテゴリ】 {cat}" in ai_text:
                    detected_category = cat
                    break
            
            results[detected_category].append({
                "title": title,
                "link": link,
                "summary": ai_text
            })
            
        except Exception as e:
            pass
            
        my_bar.progress((i + 1) / len(target_entries), text=f"{i+1}件目の分析が完了...")
        time.sleep(2)
        
    my_bar.empty()
    st.success("✅ 全ての分析が完了しました！")

    # --- 3. カテゴリ別にタブで表示する ---
    tabs = st.tabs(categories)
    
    for i, cat in enumerate(categories):
        with tabs[i]:
            if len(results[cat]) == 0:
                st.write("このカテゴリのニュースは現在ありません。")
            else:
                for item in results[cat]:
                    st.subheader(f"📰 {item['title']}")
                    st.write(f"[🔗 元記事を読む]({item['link']})")
                    st.info(item['summary'])
                    st.divider()
