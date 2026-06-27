import os

# 💡 여기에 방금 가입한 KRX 아이디와 비밀번호를 넣어줘!
os.environ["KRX_ID"] = "sunsun042505"
os.environ["KRX_PW"] = "nerverfin2@"

# ... (이 아래로는 기존 코드 그대로 둬!) ...

from flask import Flask, request, jsonify
from pykrx import stock
import yfinance as yf
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

print("⏳ 한국 주식 종목 코드를 불러오는 중입니다... (약 5~10초 소요)")
kr_stocks = {}

try:
    # 1. 정상적인 시간일 때 KRX에서 전체 목록 가져오기
    tickers = stock.get_market_ticker_list(market="ALL")
    # 점검 시간이라 데이터가 비어있으면 강제로 에러를 발생시켜서 except로 넘김
    if not tickers:
        raise ValueError("KRX 서버 점검 중 (데이터 없음)")
        
    for t in tickers:
        name = stock.get_market_ticker_name(t)
        kr_stocks[name] = t
    print(f"✅ 로딩 완료! 총 {len(kr_stocks)}개의 한국 주식을 뇌에 입력했습니다.")
    
except Exception as e:
    # 2. 밤 12시 서버 점검 등으로 에러가 났을 때 작동하는 비상 모드!
    print(f"🚨 KRX 전체 목록 로딩 실패 ({e})")
    print("🌙 현재 한국거래소 심야 점검 시간이라 비상용 목록으로 서버를 켭니다!")
    # 테스트할 때 자주 썼던 종목들만 임시로 기억해 둠
    kr_stocks = {
        "삼성전자": "005930",
        "에스엠": "041510",
        "카카오": "035720",
        "네이버": "035420"
    }

def get_kr_stock_info(code):
    """🇰🇷 네이버에서 현재가와 뉴스 가져오기"""
    main_url = f"https://finance.naver.com/item/main.naver?code={code}"
    news_url = f"https://finance.naver.com/item/news_news.naver?code={code}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    try:
        res_main = requests.get(main_url, headers=headers)
        soup_main = BeautifulSoup(res_main.text, 'html.parser')
        price_tag = soup_main.select_one('.no_today .blind')
        price = price_tag.text.strip() + "원" if price_tag else "정보 없음"
        
        news_list = []
        res_news = requests.get(news_url, headers=headers)
        soup_news = BeautifulSoup(res_news.text, 'html.parser')
        for tag in soup_news.select('.tit')[:3]:
            news_list.append(tag.text.strip())
            
        return price, news_list
    except Exception as e:
        print(f"🚨 국내 주가 수집 에러: {e}")
        return "정보 없음", []

def search_us_stock_ticker(name):
    """🇺🇸 야후 파이낸스로 미국 주식 티커 검색"""
    url = f"https://query2.finance.yahoo.com/v1/finance/search?q={name}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        res = requests.get(url, headers=headers).json()
        if res.get('quotes') and len(res['quotes']) > 0:
            return res['quotes'][0]['symbol']
    except Exception as e:
        print(f"🚨 미국 종목 검색 에러: {e}")
    return None

def get_us_stock_info(ticker):
    """🇺🇸 야후 파이낸스로 미국 주가와 뉴스 가져오기"""
    try:
        us_stock = yf.Ticker(ticker)
        hist = us_stock.history(period="1d")
        price = f"${hist['Close'].iloc[0]:.2f}" if not hist.empty else "정보 없음"
            
        news_list = [news['title'] for news in us_stock.news[:3]] if us_stock.news else []
        return price, news_list
    except Exception as e:
        print(f"🚨 미국 주가 수집 에러: {e}")
        return "정보 없음", []

@app.route('/api/stock', methods=['POST'])
def stock_bot():
    req = request.get_json()
    user_msg = req['userRequest']['utterance'].strip()
    
    res_text = ""
    
    # 한국 주식 처리 (비상 모드일 땐 등록된 임시 종목만 검색됨)
    if user_msg in kr_stocks:
        kr_code = kr_stocks[user_msg]
        price, news_list = get_kr_stock_info(kr_code)
        res_text = f"🇰🇷 {user_msg} ({kr_code})\n💰 현재가: {price}\n\n📰 관련 뉴스:\n"
    else:
        # 미국 주식 처리
        us_ticker = search_us_stock_ticker(user_msg)
        if us_ticker:
            price, news_list = get_us_stock_info(us_ticker)
            res_text = f"🇺🇸 {user_msg} ({us_ticker})\n💰 현재가: {price}\n\n📰 관련 뉴스:\n"
        else:
            res_text = f"😥 '{user_msg}' 종목을 찾을 수 없어. 정확한 이름이나 티커를 입력해 줘!"

    if "관련 뉴스" in res_text:
        if news_list:
            for i, news in enumerate(news_list, 1):
                res_text += f"  {i}. {news}\n"
        else:
            res_text += "  (최신 뉴스가 없습니다.)"

    return jsonify({
        "version": "2.0",
        "template": {
            "outputs": [{"simpleText": {"text": res_text}}]
        }
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)