import os
import urllib.parse
from flask import Flask, request, jsonify
import yfinance as yf
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

# 💡 센스 만점 퀵 서치 (한국 주식 + 자주 찾는 미국 주식 한글화)
quick_search = {
    "삼성전자": "005930",
    "에스엠": "041510",
    "애플": "AAPL",
    "테슬라": "TSLA",
    "엔비디아": "NVDA",
    "마이크로소프트": "MSFT"
}

def find_kr_stock_code(name):
    """네이버 금융 검색을 이용해 0.1초 만에 종목 코드 알아내기 (방화벽 절대 안 막힘!)"""
    try:
        # 한글을 네이버가 인식하는 euc-kr 방식으로 변환해서 검색 쏩니다!
        encoded_name = urllib.parse.quote(name.encode('euc-kr'))
        url = f"https://finance.naver.com/search/searchList.naver?query={encoded_name}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        # 검색하면 네이버가 알아서 해당 주식 페이지로 쓩 이동시켜줌
        res = requests.get(url, headers=headers)
        
        # 최종 도착한 주소에 'code=숫자6자리'가 있으면 종목 찾기 성공!
        if 'code=' in res.url:
            return res.url.split('code=')[-1][:6]
    except:
        pass
    return None

def get_kr_price_naver(code):
    """찾아낸 코드로 가격만 쏙 빼오기"""
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
            if code_or_ticker.isalpha():  # 영어(알파벳)면 미국 주식
                ticker = yf.Ticker(code_or_ticker).history(period="1d")
                price = f"${ticker['Close'].iloc[0]:.2f}"
                res_text = f"🇺🇸 {user_msg}({code_or_ticker}) 현재가: {price}"
            else:  # 숫자면 한국 주식
                price = get_kr_price_naver(code_or_ticker)
                res_text = f"🇰🇷 {user_msg}({code_or_ticker}) 현재가: {price}"
        
        else:
            # 2. 주머니에 없으면 네이버 검색으로 한국 주식 찾기!
            kr_code = find_kr_stock_code(user_msg)
            
            if kr_code:
                price = get_kr_price_naver(kr_code)
                res_text = f"🇰🇷 {user_msg} ({kr_code})\n💰 현재가: {price}"
            else:
                # 3. 네이버 검색에도 안 나오면 미국 주식(티커)으로 시도
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
