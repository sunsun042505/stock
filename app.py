import os
from flask import Flask, request, jsonify
import yfinance as yf
import FinanceDataReader as fdr
import requests

app = Flask(__name__)

# 💡 마법의 공간: 서버가 켜질 때 전체 주식 목록 2,800개를 미리 외워둠
print("⏳ 한국 주식 전체 데이터 가져오는 중...")
try:
    df_krx = fdr.StockListing('KRX')
    kr_stocks_cache = {}
    for idx, row in df_krx.iterrows():
        name = row['Name']
        code = row['Code']  # 6자리 종목코드 (예: 005930)
        kr_stocks_cache[name] = code
    print(f"✅ 한국 주식 {len(kr_stocks_cache)}개 완벽하게 맵핑 완료!")
except Exception as e:
    kr_stocks_cache = {}
    print(f"🚨 로딩 실패: {e}")

def get_kr_price_naver_mobile(code):
    """네이버 모바일 전용 API: 방화벽 절대 안 막히고 엄청 빠름!"""
    url = f"https://m.stock.naver.com/api/stock/{code}/price?pageSize=1&page=1"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers, timeout=3)
        data = res.json()
        price = data[0]['closePrice'] # JSON에서 종가만 쏙 빼오기
        return f"{price}원"
    except:
        return "가격 정보 로딩 실패"

@app.route('/api/stock', methods=['POST'])
def stock_bot():
    try:
        req = request.get_json()
        user_msg = req.get('userRequest', {}).get('utterance', '').strip()
        
        if not user_msg:
            return jsonify({"version": "2.0", "template": {"outputs": [{"simpleText": {"text": "메시지를 읽지 못했어요."}}]}})

        res_text = ""

        # 1. 한국 주식인지 확인
        if user_msg in kr_stocks_cache:
            code = kr_stocks_cache[user_msg]
            price = get_kr_price_naver_mobile(code)  # 야후 버리고 네이버 모바일 API 사용!
            res_text = f"🇰🇷 {user_msg}\n💰 현재가: {price}"
                
        else:
            # 2. 한국 주식에 없으면 미국 주식(yfinance)으로 검색
            ticker_data = yf.Ticker(user_msg).history(period="1d")
            if not ticker_data.empty:
                price = float(ticker_data['Close'].iloc[-1])
                res_text = f"🇺🇸 {user_msg} 현재가: ${price:.2f}"
            else:
                res_text = f"🧐 '{user_msg}' 종목을 찾지 못했어요.\n(미국 주식은 AAPL처럼 영어 티커로 입력해 줘!)"

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
