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
        # 1. 네이버 증권 자동완성 API (이게 진짜 빠르고 정확함)
        # 띄어쓰기나 인코딩 문제 없이 깔끔하게 JSON으로 종목 코드를 찾아줌
        search_url = f"https://ac.finance.naver.com/ac?q={keyword}&q_enc=utf-8&st=111&frm=stock&r_format=json&r_enc=utf-8&r_unicode=1&t_kcond=0&l_type=2"
        
        search_res = requests.get(search_url).json()
        items = search_res.get('items', [])
        
        # 검색 결과가 비어있으면 에러 메시지
        if not items or not items[0]:
            return f"❌ '{keyword}' 종목을 찾을 수 없어. (이름을 확인해 줘!)"
            
        # 첫 번째 검색 결과의 [이름, 종목코드] 가져오기
        first_result = items[0][0]
        code = first_result[1]  # '005930' 같은 6자리 코드
        
        # 2. 알아낸 코드로 모바일 API 찔러서 가격 가져오기
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
        print(f"에러 로그: {e}")
        return f"❌ '{keyword}' 검색 중 에러가 발생했어!"


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
