import os
from flask import Flask, request, jsonify
from pykrx import stock
import yfinance as yf
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

# 💡 1. Render 환경 변수(금고)에서 아이디/비밀번호 가져오기
# (Render의 Environment 탭에 세팅해두면 여기서 알아서 꺼내 씀! 코드엔 안 보임)
KRX_ID = os.environ.get("KRX_ID")
KRX_PW = os.environ.get("KRX_PW")

# 💡 2. 초고속 검색을 위한 '고정 종목' 주머니 (여기에 자주 보는 거 추가해!)
kr_stocks_cache = {
    "삼성전자": "005930",
    "에스엠": "041510", 
    "카카오": "035720",
    "네이버": "035420"
}

def get_krx_ticker(stock_name):
    """KRX를 이용해 종목 코드 찾기 (캐시에 없으면 작동)"""
    try:
        tickers = stock.get_market_ticker_list(market="ALL")
        for t in tickers:
            name = stock.get_market_ticker_name(t)
            if name == stock_name:
                return t
    except:
        pass
    return None

def get_kr_price_naver(code):
    """네이버 금융에서 현재가만 0.1초 만에 긁어오기 (403 방화벽 회피)"""
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        price = soup.select_one('.no_today .blind').text.strip() + "원"
        return price
    except:
        return "가격 정보 로딩 실패"

@app.route('/api/stock', methods=['POST'])
def stock_bot():
    try:
        # 카카오톡에서 보낸 메시지 꺼내기
        req = request.get_json()
        user_msg = req.get('userRequest', {}).get('utterance', '').strip()
        
        if not user_msg:
            return jsonify({"version": "2.0", "template": {"outputs": [{"simpleText": {"text": "메시지를 읽지 못했어요."}}]}})

        res_text = ""

        # --- 🇰🇷 한국 주식 검색 로직 ---
        # 1. 먼저 초고속 주머니(캐시)에서 찾아봄
        kr_code = kr_stocks_cache.get(user_msg)
        
        # 2. 주머니에 없으면 KRX 라이브러리로 전체 종목 검색
        if not kr_code:
            kr_code = get_krx_ticker(user_msg)

        if kr_code:
            # 3. 코드를 찾았으면 네이버 금융에서 가격만 쏙 빼옴
            price = get_kr_price_naver(kr_code)
            res_text = f"🇰🇷 {user_msg} ({kr_code})\n💰 현재가: {price}"
        
        # --- 🇺🇸 미국 주식 검색 로직 (한국 주식이 아닐 때) ---
        else:
            ticker = yf.Ticker(user_msg).history(period="1d")
            if not ticker.empty:
                price = f"${ticker['Close'].iloc[0]:.2f}"
                res_text = f"🇺🇸 {user_msg} 현재가: {price}"
            else:
                res_text = f"🧐 '{user_msg}' 종목을 찾지 못했어요.\n한국 주식은 정확한 이름, 미국 주식은 티커(예: TSLA)를 입력해 줘!"

        # 카카오톡 서버로 예쁘게 포장해서 보내기
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
