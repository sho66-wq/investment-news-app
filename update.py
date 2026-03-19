# --- 【追加任務】経済指標カレンダーのAIスクレイピング ---
import requests
from bs4 import BeautifulSoup

try:
    schedule_url = "https://nikkei225jp.com/schedule/"
    # サイトに怪しまれないように「普通のパソコンからのアクセスですよ」と偽装する
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    res = requests.get(schedule_url, headers=headers)
    res.encoding = res.apparent_encoding # 文字化け防止
    soup = BeautifulSoup(res.text, "html.parser")
    
    # サイトの裏側のコード（スクリプトなど）を掃除して、純粋なテキストだけを抽出
    for script in soup(["script", "style"]):
        script.extract()
    page_text = soup.get_text(separator='\n')
    
    # テキストが長すぎるとAIがパンクするので、上のほう（約8000文字）だけ切り取る
    page_text_short = page_text[:8000]

    # AIに「今日の予定だけを抜き出して」とお願いする
    schedule_prompt = f"""
    あなたは優秀な金融アシスタントです。以下のWebページのテキストデータから、
    「本日の主な予定」と「NEWS（経済指標）」に関する情報を抽出し、
    投資家向けに見やすく箇条書きでまとめてください。
    余計な挨拶や説明は不要です。情報が見つからない場合は「本日の重要な経済指標はありません」と出力してください。
    
    【Webページのテキスト】
    {page_text_short}
    """
    
    schedule_response = model.generate_content(schedule_prompt, safety_settings=safety_settings)
    schedule_result = schedule_response.text
    
    # 結果をテキストファイルとして保存
    with open("schedule_data.txt", "w", encoding="utf-8") as f:
        f.write(schedule_result)
        
except Exception as e:
    print(f"Schedule fetch error: {e}")
