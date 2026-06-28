import os
import re
from flask import Flask, request, jsonify
import yfinance as yf
import FinanceDataReader as fdr
import requests
import threading

app = Flask(__name__)

# 💡 마법의 공간: 서버가 켜질 때 전체 주식 목록 2,800개를 미리 외워둠 (메모리 캐시)
print("⏳ 한국 주식 전체 데이터 가져오는 중...")
try:
    df_krx = fdr.StockListing('KRX')
    kr_stocks_cache = {}
    for idx, row in df_krx.iterrows():
        name = row['Name']
        code = row['Code']  # 6자리 종목코드
        kr_stocks_cache[name] = code
    print(f"✅ 한국 주식 {len(kr_stocks_cache)}개 완벽하게 맵핑 완료!")
except Exception as e:
    kr_stocks_cache = {}
    print(f"🚨 로딩 실패: {e}")

def get_kr_price_naver_mobile(code):
    url = f"https://m.stock.naver.com/api/stock/{code}/price?pageSize=1&page=1"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers, timeout=3)
        data = res.json()
        price = data[0]['closePrice']
        return f"{price}원"
    except:
        return "가격 정보 로딩 실패"

def get_recent_news():
    """구글 뉴스 RSS를 활용해 실시간 경제 뉴스 3개를 긁어오는 함수"""
    url = "https://news.google.com/rss/search?q=%EA%B2%BD%EC%A0%9C&hl=ko&gl=KR&ceid=KR:ko"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers, timeout=3)
        # 정규식으로 <title> 태그 안에 있는 뉴스 제목들만 쏙 빼오기
        titles = re.findall(r'<title>(.*?)</title>', res.text)
        news_headlines = []
        
        # 첫 번째 타이틀은 채널명이므로 제외하고 1번부터 3번까지 가져옴
        for t in titles[1:4]:
            clean_title = t.replace('&quot;', '"').replace('&amp;', '&').replace('&#39;', "'")
            news_headlines.append(f"📰 {clean_title}")
        return "\n".join(news_headlines) if news_headlines else "최근 뉴스가 없습니다."
    except:
        return "📰 뉴스 로딩 실패"

# ---------------------------------------------------------
# 💡 백그라운드에서 주가/시황을 조회하고 카카오로 콜백을 쏘는 함수
# ---------------------------------------------------------
def process_stock_and_callback(callback_url, user_msg):
    res_text = ""
    try:
        # 1. 사용자가 시황이나 뉴스를 요구했을 때
        if user_msg in ["시황", "오늘의시황", "오늘의 시황", "뉴스"]:
            # 코스피 지수 계산
            try:
                kospi_df = fdr.DataReader('KS11')
                kospi_price = kospi_df['Close'].iloc[-1]
                kospi_change = kospi_price - kospi_df['Close'].iloc[-2]
                kospi_sign = "+" if kospi_change > 0 else ""
                kospi_str = f"{kospi_price:,.2f} ({kospi_sign}{kospi_change:,.2f})"
            except:
                kospi_str = "로딩 실패"
                
            # 코스닥 지수 계산
            try:
                kosdaq_df = fdr.DataReader('KQ11')
                kosdaq_price = kosdaq_df['Close'].iloc[-1]
                kosdaq_change = kosdaq_price - kosdaq_df['Close'].iloc[-2]
                kosdaq_sign = "+" if kosdaq_change > 0 else ""
                kosdaq_str = f"{kosdaq_price:,.2f} ({kosdaq_sign}{kosdaq_change:,.2f})"
            except:
                kosdaq_str = "로딩 실패"
            
            # 실시간 뉴스 가져오기
            news_str = get_recent_news()
            
            res_text = f"📊 오늘의 시장 시황\n\n🔹 코스피: {kospi_str}\n🔹 코스닥: {kosdaq_str}\n\n🔥 실시간 주요 뉴스\n{news_str}"
            
        # 2. 한국 주식 검색
        elif user_msg in kr_stocks_cache:
            code = kr_stocks_cache[user_msg]
            price = get_kr_price_naver_mobile(code)
            res_text = f"🇰🇷 {user_msg}\n💰 현재가: {price}"
                
        # 3. 미국 주식 검색
        else:
            ticker_data = yf.Ticker(user_msg).history(period="1d")
            if not ticker_data.empty:
                price = float(ticker_data['Close'].iloc[-1])
                res_text = f"🇺🇸 {user_msg} 현재가: ${price:.2f}"
            else:
                res_text = f"🧐 '{user_msg}' 종목이나 명령어를 찾지 못했어요.\n\n💡 '시황', '뉴스'를 입력하거나 '삼성전자', 'AAPL' 같은 종목명을 입력해 줘!"
                
    except Exception as e:
        res_text = f"🚨 봇 오류 발생: {str(e)}"

    # 카카오 콜백 규격에 맞춰 데이터 전송
    payload = {
        "version": "2.0",
        "template": {"outputs": [{"simpleText": {"text": res_text}}]}
    }
    headers = {'Content-Type': 'application/json; charset=utf-8'}
    requests.post(callback_url, json=payload, headers=headers)
    print(f"✅ [{user_msg}] 콜백 전송 완료!")


# ---------------------------------------------------------
# 챗봇 메인 라우트
# ---------------------------------------------------------
@app.route('/api/stock', methods=['POST'])
def stock_bot():
    try:
        req = request.get_json()
        user_msg = req.get('userRequest', {}).get('utterance', '').strip()
        callback_url = req.get('userRequest', {}).get('callbackUrl')
        
        if not user_msg:
            return jsonify({"version": "2.0", "template": {"outputs": [{"simpleText": {"text": "메시지를 읽지 못했어요."}}]}})

        # 콜백 URL이 들어왔다면 비동기 모드로 작동 (Render Cold Start 방어)
        if callback_url:
            task = threading.Thread(target=process_stock_and_callback, args=(callback_url, user_msg))
            task.start()
            return jsonify({"useCallback": True})
            
        # 혹시 콜백 설정이 꺼져있을 때를 대비한 백업용 동기 방식
        else:
            if user_msg in kr_stocks_cache:
                code = kr_stocks_cache[user_msg]
                price = get_kr_price_naver_mobile(code)
                res_text = f"🇰🇷 {user_msg}\n💰 현재가: {price}"
            else:
                ticker_data = yf.Ticker(user_msg).history(period="1d")
                if not ticker_data.empty:
                    price = float(ticker_data['Close'].iloc[-1])
                    res_text = f"🇺🇸 {user_msg} 현재가: ${price:.2f}"
                else:
                    res_text = f"🧐 '{user_msg}' 종목을 찾지 못했어요."

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
