import os
import json
import traceback
import google.generativeai as genai

api_key = os.environ.get("GOOGLE_API_KEY")
genai.configure(api_key=api_key)

result_message = "2.5-flash 呼び出しテスト開始\n"

try:
    # 前回ListModelsで確認できた正式名称をそのまま使用
    model = genai.GenerativeModel("models/gemini-2.5-flash")
    # 投資に関する簡単なテストリクエスト
    response = model.generate_content("日本の株式市場について1文で教えてください。")
    result_message += f"✅ 成功: {response.text}\n"
    
except Exception as e:
    # エラーを一切隠さず、すべてJSONに書き込む
    result_message += f"\n❌ 2.5-flash呼び出しエラー発生:\n{traceback.format_exc()}"

data = [{
    "title": "🚨 2.5-flash 通信テスト結果",
    "link": "https://github.com",
    "summary": result_message,
    "category": "その他",
    "fetched_at": "2026-03-16T00:00:00"
}]

with open("news_data.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
