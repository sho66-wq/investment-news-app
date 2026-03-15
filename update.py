import os
import json
import traceback
import google.generativeai as genai

# エラーを隠さず、すべてJSONに書き込むための診断スクリプト
api_key = os.environ.get("GOOGLE_API_KEY")
genai.configure(api_key=api_key)

result_message = "テスト開始\n"

try:
    # 1. 使えるモデルの一覧を取得してみる
    models = [m.name for m in genai.list_models()]
    result_message += f"✅ モデル一覧取得成功: {models[:3]}...\n"
    
    # 2. 実際にGeminiを呼び出してみる
    model = genai.GenerativeModel("models/gemini-1.5-flash") # 正式名称で指定
    response = model.generate_content("これはテストです。返事をしてください。")
    result_message += f"✅ AI呼び出し成功: {response.text}\n"

except Exception as e:
    # エラーが起きたら、その詳細な原因（トレースバック）をすべて記録する
    result_message += f"\n❌ 致命的なエラー発生:\n{traceback.format_exc()}"

# 診断結果を news_data.json に上書き保存する
data = [{
    "title": "🚨 AI通信テスト結果",
    "link": "https://github.com",
    "summary": result_message,
    "category": "その他",
    "fetched_at": "2026-03-16T00:00:00"
}]

with open("news_data.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
