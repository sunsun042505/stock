from flask import Flask, request, jsonify
import requests
import threading

app = Flask(__name__)

# ---------------------------------------------------------
# 1. 백그라운드에서 실행될 실제 작업 (크롤링 + 카카오톡 발송)
# ---------------------------------------------------------
def process_crawling_and_send(callback_url):
    print("✅ 데이터 수집 스레드 시작!")
    
    # 여기서 네이버 증권 데이터 긁어오기 (아까 짠 코드 활용)
    # KOSPI 긁어오기
    # KOSDAQ 긁어오기
    # 삼성전자 가격 긁어오기 등등...
    
    # 긁어왔다고 가정하고 결과 텍스트 만들기
    result_text = "📊 오늘의 증시 요약\n코스피: 2,750.31\n코스닥: 852.42\n삼성전자: 81,000원"
    
    # 콜백 형식에 맞춘 카카오톡 응답 JSON 만들기
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
    
    # 카카오가 알려준 callback_url로 데이터를 쏴줌!
    headers = {'Content-Type': 'application/json; charset=utf-8'}
    res = requests.post(callback_url, json=payload, headers=headers)
    print(f"✅ 콜백 응답 발송 완료 (상태 코드: {res.status_code})")


# ---------------------------------------------------------
# 2. 챗봇 요청을 받는 메인 라우트 (여긴 1초 안에 끝남)
# ---------------------------------------------------------
@app.route('/api/stock', methods=['POST'])
def chatbot_api():
    req_data = request.get_json()
    
    # 카카오가 넘겨준 정보에서 'callbackUrl' 쏙 빼오기
    user_request = req_data.get('userRequest', {})
    callback_url = user_request.get('callbackUrl')
    
    if callback_url:
        print(f"🔗 콜백 URL 수신 완료: {callback_url}")
        
        # 스레드(Thread)를 만들어서 백그라운드로 크롤링 작업 던지기
        # 이러면 메인 흐름은 크롤링을 안 기다리고 밑으로 바로 내려감!
        task = threading.Thread(target=process_crawling_and_send, args=(callback_url,))
        task.start()
        
        # 카카오한테 "어 땡큐! 수집해서 나중에 줄게!" 하고 바로 응답 (타임아웃 방어 성공!)
        return jsonify({"useCallback": True})
        
    else:
        # 혹시 챗봇 빌더에서 콜백 옵션을 안 켜서 URL이 안 왔을 때의 에러 처리
        print("❌ 콜백 URL이 없습니다. 챗봇 빌더 설정을 확인하세요.")
        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [{"simpleText": {"text": "서버 설정에 문제가 있습니다. (콜백 URL 누락)"}}]
            }
        })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
