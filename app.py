import requests
import re
import urllib.parse
from flask import Flask, request, jsonify
import threading

app = Flask(__name__)

# ---------------------------------------------------------
# 1. 사용자가 친 '이름'을 '6자리 코드'로 찾고 가격까지 가져오는 만능 함수
# ---------------------------------------------------------
def search_and_get_price(keyword):
    try:
        # (1) 네이버 금융 검색으로 6자리 종목 코드 알아내기
        # 한글 이름을 EUC-KR로 변환해서 네이버에 검색
        enc_keyword = urllib.parse.quote(keyword.encode('euc-kr'))
        search_url = f"https://finance.naver.com/search/searchList.naver?query={enc_keyword}"
        search_res = requests.get(search_url)
        
        # HTML 결과에서 'code=숫자6자리' 패턴 찾기
        match = re.search(r'code=(\d{6})', search_res.text)
        if not match:
            return f"❌ '{keyword}' 종목을 찾을 수 없어. (정확한 이름을 입력해 줘!)"
        
        code = match.group(1)
        
        # (2) 알아낸 코드로 모바일 API 찔러서 가격 가져오기
        price_url = f"https://m.stock.naver.com/api/stock/{code}/integration"
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15'
        }
        price_res = requests.get(price_url, headers=headers).json()
        
        name = price_res['stockName']
        price = price_res['totalInfos']['closePrice']
        diff = price_res['totalInfos']['compareToPreviousClosePrice']
        
        return f"📊 {name} ({code})\n현재가: {price}원\n전일대비: {diff}원"
        
    except Exception as e:
        return f"❌ 검색 중 에러가 발생했어!"

# ---------------------------------------------------------
# 2. 백그라운드 작업 (크롤링 + 카카오톡 발송)
# ---------------------------------------------------------
def process_crawling_and_send(callback_url, user_text):
    print(f"✅ 사용자가 입력한 검색어: {user_text}")
    
    # 여기서 유저가 친 텍스트로 주식 검색!
    result_text = search_and_get_price(user_text)
    
    # 카카오 콜백 형식에 맞춘 JSON
    payload = {
        "version": "2.0",
        "template": {
            "outputs": [
                {
                    "simpleText": {
                        "text": result_text
                    }
                }
            ]
        }
    }
    
    headers = {'Content-Type': 'application/json; charset=utf-8'}
    requests.post(callback_url, json=payload, headers=headers)
    print("✅ 콜백 응답 발송 완료")

# ---------------------------------------------------------
# 3. 메인 라우트
# ---------------------------------------------------------
@app.route('/api/stock', methods=['POST'])
def chatbot_api():
    req_data = request.get_json()
    
    user_request = req_data.get('userRequest', {})
    callback_url = user_request.get('callbackUrl')
    
    # 💡 여기가 핵심! 사용자가 카톡 창에 입력한 텍스트를 가져옴
    utterance = user_request.get('utterance', '').strip()
    
    if callback_url:
        # 스레드에 콜백 주소랑 '사용자가 입력한 단어(utterance)'를 같이 넘겨줌
        task = threading.Thread(target=process_crawling_and_send, args=(callback_url, utterance))
        task.start()
        
        return jsonify({"useCallback": True})
    else:
        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [{"simpleText": {"text": "콜백 설정이 안 켜져 있어!"}}]
            }
        })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
