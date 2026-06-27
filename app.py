import os
from flask import Flask, request, jsonify
from pykrx import stock
import yfinance as yf
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

# 💡 마법의 공간: 서버가 켜질 때 전체 주식 2,800개를 한 번에 다 외워버림!
kr_stocks_cache = {}
print("⏳ 한국 주식 전체 데이터 외우는 중... (약 2~3초 소요)")
try:
    tickers = stock.get_market_ticker_list(market="ALL")
    for t in tickers:
        name = stock.get_market_ticker_name(t)
        kr_stocks_cache[name] = t
    print(f"✅ 한국 주식 {len(kr_stocks_cache)}개 완벽하게 다 외움!")
except Exception as e:
    print(f"🚨 로딩 실패: {e}")

def get_kr_price_naver(code):
    """네이버 금융에서 현재가만 0.1초 만에 긁어오기"""
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
        req = request.get_json()
        user_msg = req.get('userRequest', {}).get('utterance', '').strip()
        
        if not user_msg:
            return jsonify({"version": "2.0", "template": {"outputs": [{"simpleText": {"text": "메시지를 읽지 못했어요."}}]}})

        # 1. 아까 외워둔 2,800개 주머니에서 바로 찾기 (0.001초 컷!)
        kr_code = kr_stocks_cache.get(user_msg)

        if kr_code:
            # 2. 코드를 찾았으면 네이버 금융에서 가격 가져오기
            price = get_kr_price_naver(kr_code)
            res_text = f"🇰🇷 {user_msg} ({kr_code})\n💰 현재가: {price}"
        else:
            # 3. 한국 주식에 없으면 미국 주식(yfinance) 검색
            ticker = yf.Ticker(user_msg).history(period="1d")
            if not ticker.empty:
                price = f"${ticker['Close'].iloc[0]:.2f}"
                res_text = f"🇺🇸 {user_msg} 현재가: {price}"
            else:
                res_text = f"🧐 '{user_msg}' 종목을 찾지 못했어요.\n한국 주식은 정확한 이름, 미국 주식은 티커(예: TSLA)를 입력해 줘!"

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
