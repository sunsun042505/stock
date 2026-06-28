import requests
import json
import threading
from flask import Flask, request, jsonify

app = Flask(__name__)

# 실제 네이버에서 주가와 뉴스를 긁어서 카카오 콜백 주소로 보내는 함수 (백그라운드에서 실행)
def fetch_data_and_callback(callback_url, stock_code):
    try:
        # 1. 우리가 저번에 성공했던 네이버 모바일 API로 주가 긁기
        url = f"https://m.stock.naver.com/api/stock/{stock_code}/integration"
        headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)'}
        response = requests.get(url, headers=headers)
        data = response.json()
        
        name = data['stockName']
        price = data['totalInfos']['closePrice']
        diff = data['totalInfos']['compareToPreviousClosePrice']
        
        message_text = f"📊 요청하신 {name} 시황이야!\n현재가: {price}원\n전일대비: {diff}"
        
    except Exception as e:
        message_text = f"😢 시황 정보를 가져오는데 실패했어: {e}"
    
    # 2. 카카오가 기다리고 있는 콜백 주소로 결과 메시지 쏘기
    callback_payload = {
        "version": "2.0",
        "template": {
            "outputs": [
                {
                    "simpleText": {
                        "text": message_text
                    }
                }
            ]
        }
    }
    
    # 카카오 서버로 결과 전송!
    requests.post(callback_url, json=callback_payload)

# 카카오톡 챗봇이 버튼 클릭 시 처음으로 찌르는 주소
@app.route('/chatbot', methods=['POST'])
def chatbot_handler():
    req_data = request.get_json()
    
    # 카카오가 준 요청에서 콜백 주소 꺼내기
    callback_url = req_data.get('userRequest', {}).get('callbackUrl')
    
    # 사용자가 입력한 종목 코드 (예: 삼성전자 005930)
    # 버튼 설정에 따라 변수 가져오는 방식은 다를 수 있어!
    stock_code = "005930" 
    
    if callback_url:
        # 핵심!! 데이터 긁는 함수를 '쓰레드(Thread)'로 돌려서 백그라운드에서 일하게 만듦
        # 이렇게 하면 이 함수가 끝나길 기다리지 않고 바로 아래 return으로 넘어가!
        threading.Thread(target=fetch_data_and_callback, args=(callback_url, stock_code)).start()
        
        # 카카오한테 0.1초 만에 "나 지금 준비 중이야!" 하고 먼저 응답 던지기
        # 카카오는 이 응답을 받으면 5초 타임아웃을 안 내고 대기 상태로 들어감
        return jsonify({
            "version": "2.0",
            "useCallback": True  # 카카오한테 콜백 쓸 테니까 기다리라고 말해주는 플래그
        })
    
    else:
        # 혹시 콜백 주소가 안 넘어왔을 때의 예외 처리
        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [{"simpleText": {"text": "콜백 주소를 찾을 수 없어."}}]
            }
        })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
