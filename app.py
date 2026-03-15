import streamlit as st
import feedparser
import google.generativeai as genai
import time

# 【重要】Streamlitのシークレット機能（金庫）からAPIキーを安全に読み込む
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
except Exception as e:
    st.error("エラー: APIキーが設定されていません。StreamlitのSecrets設定を確認してください。")
    st.stop()

# モデル選択のロジック
available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
preferred_models = ['models/gemini-2.5-flash', 'models/gemini-1.5-flash', 'models/gemini-1.5-pro']
selected_model = next((pm for pm in preferred_models if pm in available_models), available_models[0] if available_models else None)
model = genai.GenerativeModel(selected_model.replace("models/", ""))

# --- Web画面のデザイン ---
st.set_page_config(page_title="投資ニュースAIサマリー", page_icon="📈")
st.title("📊 個人専用：投資ニュースAIサマリー")
st.write("最新の経済ニュースを取得し、プロの投資家視点で分析します。")

if st.button("🔄 ニュースを取得して分析開始"):
    with st.spinner('ニュースを取得・分析中...（少し時間がかかります）'):
        rss_url = "https://news.yahoo.co.jp/rss/topics/business.xml"
        feed = feedparser.parse(rss_url)
        
        for entry in feed.entries[:3]:
            title = entry.title
            link = entry.link
            
            prompt = f"""
            あなたはプロの機関投資家・証券アナリストです。以下のニュースを分析してください。
            ニュースタイトル: {title}
            【指示】
            1. [金融、為替、株式投資、投資市場、世界経済情勢、日本経済情勢]からカテゴリを1つ選ぶ。
            2. 市場や株価動向への影響の仮説を2〜3行で要約。
            3. 中東情勢、防衛、エネルギー、宇宙、サイバー、レアアースなどの成長セクターに関連する取引材料になり得るか見解を述べる。
            """
            
            try:
                response = model.generate_content(prompt)
                st.subheader(f"📰 {title}")
                st.write(f"[🔗 元記事を読む]({link})")
                st.info(response.text)
                st.divider()
                time.sleep(2)
            except Exception as e:
                st.error(f"エラーが発生しました: {e}")
                
    st.success("✅ 全ての分析が完了しました！")
