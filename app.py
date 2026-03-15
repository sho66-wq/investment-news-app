import streamlit as st
import feedparser
import google.generativeai as genai
import time

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

# 分析するニュースの件数を設定（今回は15件）
news_count = st.slider("取得するニュースの件数を選んでください", min_value=5, max_value=30, value=15)

if st.button("🔄 ニュースを取得して分析開始"):
    
    # カテゴリの用意
    categories = ["金融", "為替", "株式投資", "投資市場", "世界経済情勢", "日本経済情勢", "その他"]
    results = {cat: [] for cat in categories}
    
    rss_url = "https://news.yahoo.co.jp/rss/topics/business.xml"
    feed = feedparser.parse(rss_url)
    target_entries = feed.entries[:news_count]

    # プログレスバー（進捗状況）を表示
    progress_text = "AIがニュースを読み込んで分析中..."
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
            
            # AIの回答からカテゴリを自動判別して振り分ける
            detected_category = "その他"
            for cat in categories:
                if f"【カテゴリ】{cat}" in ai_text or f"【カテゴリ】 {cat}" in ai_text:
                    detected_category = cat
                    break
            
            # 結果を辞書に保存
            results[detected_category].append({
                "title": title,
                "link": link,
                "summary": ai_text
            })
            
        except Exception as e:
            pass # エラーが起きても止まらずに次のニュースへ
            
        # 進捗バーを更新
        my_bar.progress((i + 1) / len(target_entries), text=f"{i+1}件目の分析が完了...")
        time.sleep(2) # 連続アクセス制限を防ぐ
        
    my_bar.empty() # 終わったらバーを消す
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
