import os
import urllib.parse
from flask import Flask, request, jsonify
import yfinance as yf
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

# 💡 센스 만점 퀵 서치 (가장 자주 보는 거나 미국 주식 한글 패치만 남겨둠)
quick_search = {
    "삼성전자": "005930",
    "에스엠": "041510",
    "애플": "AAPL",
    "테슬라": "TSLA",
    "엔비디아": "NVDA",
    "마이크로소프트": "MSFT"
}

def find_kr_stock_code(name):
    """네이버 금융 '자동완성 API'를 써서 0.01초 만에 코드 훔쳐오기 (막힐 일 절대 없음!)"""
    url = f"https://ac.finance.naver.com/ac?q={name}&q_enc=utf-8&st=111&r_format=json&r_enc=utf-8"
    try:
        res = requests.get(url, timeout=3)
        data = res.json()
        items = data.get('items', [])
        # 검색 결과가 있으면 첫 번째 종목의 6자리 코드를 바로 가져옴
        if items and len(items[0]) > 0:
            return items[0][0][1]
    except:
        pass
    return None

def get_kr_price_naver(code):
    """찾아낸 6자리 코드로 가격만 쏙 빼오기"""
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        price = soup.select_one('.no_today .blind').text.strip() + "원"
        return price
    except:
        return "가격 로딩 실패"

@app.route('/api/stock', methods=['POST'])
def stock_bot():
    try:
        req = request.get_json()
        user_msg = req.get('userRequest', {}).get('utterance', '').strip()
        
        if not user_msg:
            return jsonify({"version": "2.0", "template": {"outputs": [{"simpleText": {"text": "메시지를 읽지 못했어요."}}]}})

        res_text = ""

        # 1. 퀵 서치 주머니에서 먼저 확인
        if user_msg in quick_search:
            code_or_ticker = quick_search[user_msg]
            if code_or_ticker.isalpha():  # 영어면 미국 주식
                ticker = yf.Ticker(code_or_ticker).history(period="1d")
                price = f"${ticker['Close'].iloc[0]:.2f}"
                res_text = f"🇺🇸 {user_msg}({code_or_ticker}) 현재가: {price}"
            else:  # 숫자면 한국 주식
                price = get_kr_price_naver(code_or_ticker)
                res_text = f"🇰🇷 {user_msg}({code_or_ticker}) 현재가: {price}"
        
        else:
            # 2. 네이버 자동완성 API로 '모든' 한국 주식 알아서 다 찾기!
            kr_code = find_kr_stock_code(user_msg)
            
            if kr_code:
                price = get_kr_price_naver(kr_code)
                res_text = f"🇰🇷 {user_msg} ({kr_code})\n💰 현재가: {price}"
            else:
                # 3. 그래도 없으면 미국 주식(티커)으로 시도
                ticker = yf.Ticker(user_msg).history(period="1d")
                if not ticker.empty:
                    price = f"${ticker['Close'].iloc[0]:.2f}"
                    res_text = f"🇺🇸 {user_msg} 현재가: {price}"
                else:
                    res_text = f"🧐 '{user_msg}' 종목을 찾지 못했어요.\n(미국 주식은 AAPL처럼 영어로 입력해 줘!)"

        return jsonify({
            "version": "2.0",
            "template": {"outputs": [{"simpleText": {"text": res_text}}]}
        })
        
    except Exception as e:
        return jsonify({
            "version": "2.0",
            "template": {"outputs": [{"simpleText": {"text": f"🚨 봇 오류 발생: {str(e)}"}}]}
        })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
