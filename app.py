import os
from flask import Flask, request, jsonify
import yfinance as yf
import FinanceDataReader as fdr

app = Flask(__name__)

# 💡 마법의 공간: 서버가 켜질 때 전체 주식 목록을 공식 데이터로 안전하게 가져옴
print("⏳ 한국 주식 전체 데이터 가져오는 중...")
try:
    # FinanceDataReader로 KRX 상장 목록 가져오기 (종목명, 종목코드, 시장구분)
    df_krx = fdr.StockListing('KRX')
    
    kr_stocks_cache = {}
    for idx, row in df_krx.iterrows():
        name = row['Name']
        code = row['Code']
        market = row['Market']
        
        # 코스피(KOSPI)는 .KS, 코스닥(KOSDAQ) 등은 .KQ를 붙여야 야후가 인식함!
        if market in ['KOSPI', 'KOSPI200']:
            ticker = f"{code}.KS"
        else:
            ticker = f"{code}.KQ"
            
        kr_stocks_cache[name] = ticker

    print(f"✅ 한국 주식 {len(kr_stocks_cache)}개 완벽하게 맵핑 완료!")
except Exception as e:
    kr_stocks_cache = {}
    print(f"🚨 로딩 실패: {e}")

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
            ticker_symbol = kr_stocks_cache[user_msg] # 예: 009150.KS (삼성전기)
            
            # 야후 파이낸스에서 가격 가져오기 (Render 서버에서도 절대 안 막힘!)
            ticker_data = yf.Ticker(ticker_symbol).history(period="1d")
            
            if not ticker_data.empty:
                price = int(ticker_data['Close'].iloc[-1])
                formatted_price = f"{price:,}원" # 보기 좋게 콤마(,) 찍기
                res_text = f"🇰🇷 {user_msg}\n💰 현재가: {formatted_price}"
            else:
                res_text = f"😢 {user_msg}의 가격 정보를 야후에서 불러오지 못했어요."
                
        else:
            # 2. 한국 주식 목록에 없으면 미국 주식(티커)으로 시도
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
