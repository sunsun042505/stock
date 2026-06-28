import os
import re
from flask import Flask, request, jsonify
import yfinance as yf
import FinanceDataReader as fdr
import requests
import threading

app = Flask(__name__)

print("⏳ 한국 주식 전체 데이터 가져오는 중...")
try:
    df_krx = fdr.StockListing('KRX')
    kr_stocks_cache = {}
    for idx, row in df_krx.iterrows():
        name = row['Name']
        code = row['Code'] 
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
        price = res.json()[0]['closePrice']
        return f"{price}원"
    except:
        return "가격 정보 로딩 실패"

def get_recent_news():
    url = "https://news.google.com/rss/search?q=%EA%B2%BD%EC%A0%9C&hl=ko&gl=KR&ceid=KR:ko"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers, timeout=3)
        titles = re.findall(r'<title>(.*?)</title>', res.text)
        news_headlines = []
        for t in titles[1:4]:
            clean_title = t.replace('&quot;', '"').replace('&amp;', '&').replace('&#39;', "'")
            news_headlines.append(f"📰 {clean_title}")
        return "\n".join(news_headlines) if news_headlines else "최근 뉴스가 없습니다."
    except:
        return "📰 뉴스 로딩 실패"

# ---------------------------------------------------------
# 💡 버튼(textCard)을 쏴주는 메인 콜백 로직
# ---------------------------------------------------------
def process_stock_and_callback(callback_url, user_msg):
    title = ""
    desc = ""
    buttons = [] # 카카오톡 버튼을 담을 리스트

    try:
        # 1. 사용자가 '시황' 버튼을 눌렀거나 직접 쳤을 때
        if user_msg in ["시황", "오늘의시황", "오늘의 시황", "뉴스"]:
            try:
                kospi_df = fdr.DataReader('KS11')
                kospi_price = kospi_df['Close'].iloc[-1]
                kospi_change = kospi_price - kospi_df['Close'].iloc[-2]
                kospi_sign = "+" if kospi_change > 0 else ""
                kospi_str = f"{kospi_price:,.2f} ({kospi_sign}{kospi_change:,.2f})"
            except:
                kospi_str = "로딩 실패"
                
            try:
                kosdaq_df = fdr.DataReader('KQ11')
                kosdaq_price = kosdaq_df['Close'].iloc[-1]
                kosdaq_change = kosdaq_price - kosdaq_df['Close'].iloc[-2]
                kosdaq_sign = "+" if kosdaq_change > 0 else ""
                kosdaq_str = f"{kosdaq_price:,.2f} ({kosdaq_sign}{kosdaq_change:,.2f})"
            except:
                kosdaq_str = "로딩 실패"
            
            news_str = get_recent_news()
            
            title = "📊 오늘의 증시 & 뉴스"
            desc = f"🔹 코스피: {kospi_str}\n🔹 코스닥: {kosdaq_str}\n\n🔥 실시간 뉴스\n{news_str}"
            
        # 2. 한국 주식 검색 시 -> 가격 + [시황 보기 버튼] 달아주기
        elif user_msg in kr_stocks_cache:
            code = kr_stocks_cache[user_msg]
            price = get_kr_price_naver_mobile(code)
            
            title = f"🇰🇷 {user_msg}"
            desc = f"💰 현재가: {price}"
            buttons = [{"action": "message", "label": "📈 시황 및 뉴스 보기", "messageText": "시황"}]
                
        # 3. 미국 주식 검색 시 -> 가격 + [시황 보기 버튼] 달아주기
        else:
            ticker_data = yf.Ticker(user_msg).history(period="1d")
            if not ticker_data.empty:
                price = float(ticker_data['Close'].iloc[-1])
                
                title = f"🇺🇸 {user_msg}"
                desc = f"현재가: ${price:.2f}"
                buttons = [{"action": "message", "label": "📈 시황 및 뉴스 보기", "messageText": "시황"}]
            else:
                title = "알림"
                desc = f"🧐 '{user_msg}' 종목을 찾지 못했어요."
                
    except Exception as e:
        title = "오류"
        desc = f"🚨 봇 오류 발생: {str(e)}"

    # 💡 simpleText 대신 textCard 규격으로 변경 (버튼 포함)
    card_content = {
        "title": title,
        "description": desc
    }
    if buttons:
        card_content["buttons"] = buttons

    payload = {
        "version": "2.0",
        "template": {
            "outputs": [{"textCard": card_content}]
        }
    }
    
    headers = {'Content-Type': 'application/json; charset=utf-8'}
    requests.post(callback_url, json=payload, headers=headers)
    print(f"✅ [{user_msg}] 텍스트 카드 콜백 전송 완료!")

@app.route('/api/stock', methods=['POST'])
def stock_bot():
    try:
        req = request.get_json()
        user_msg = req.get('userRequest', {}).get('utterance', '').strip()
        callback_url = req.get('userRequest', {}).get('callbackUrl')
        
        if not user_msg:
            return jsonify({"version": "2.0", "template": {"outputs": [{"simpleText": {"text": "메시지를 읽지 못했어요."}}]}})

        # 콜백(비동기) 주소가 있을 때 무조건 이쪽으로!
        if callback_url:
            task = threading.Thread(target=process_stock_and_callback, args=(callback_url, user_msg))
            task.start()
            return jsonify({"useCallback": True})
            
        else:
            return jsonify({
                "version": "2.0",
                "template": {"outputs": [{"simpleText": {"text": "⚠️ 카카오 챗봇 관리자 센터에서 '콜백(비동기) 처리'를 ON으로 켜야 버튼이 작동해!"}}]}
            })
        
    except Exception as e:
        return jsonify({
            "version": "2.0",
            "template": {"outputs": [{"simpleText": {"text": f"🚨 봇 오류 발생: {str(e)}"}}]}
        })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
