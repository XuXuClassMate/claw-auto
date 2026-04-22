#!/usr/bin/env python3
"""
美股数据获取脚本
使用 yfinance 获取主要美股数据
"""

import yfinance as yf
import json
from datetime import datetime, timezone

# 美股主要标的列表
STOCKS = {
    "AAPL": {"name": "Apple Inc.", "sector": "科技"},
    "MSFT": {"name": "Microsoft Corporation", "sector": "科技"},
    "GOOGL": {"name": "Alphabet Inc.", "sector": "科技"},
    "AMZN": {"name": "Amazon.com Inc.", "sector": "消费"},
    "NVDA": {"name": "NVIDIA Corporation", "sector": "科技"},
    "META": {"name": "Meta Platforms Inc.", "sector": "科技"},
    "TSLA": {"name": "Tesla Inc.", "sector": "新能源"},
    "BRK.B": {"name": "Berkshire Hathaway", "sector": "金融"},
    "JPM": {"name": "JPMorgan Chase", "sector": "金融"},
    "V": {"name": "Visa Inc.", "sector": "金融"},
    "JNJ": {"name": "Johnson & Johnson", "sector": "医疗"},
    "UNH": {"name": "UnitedHealth Group", "sector": "医疗"},
    "XOM": {"name": "Exxon Mobil", "sector": "能源"},
    "PG": {"name": "Procter & Gamble", "sector": "消费"},
    "HD": {"name": "Home Depot", "sector": "消费"},
    "MA": {"name": "Mastercard", "sector": "金融"},
    "DIS": {"name": "Walt Disney", "sector": "娱乐"},
    "NFLX": {"name": "Netflix Inc.", "sector": "娱乐"},
    "ADBE": {"name": "Adobe Inc.", "sector": "科技"},
    "CRM": {"name": "Salesforce Inc.", "sector": "科技"},
}


def format_large_number(num):
    """格式化大数字"""
    if num >= 1e12:
        return f"${num/1e12:.2f}T"
    elif num >= 1e9:
        return f"${num/1e9:.2f}B"
    elif num >= 1e6:
        return f"${num/1e6:.2f}M"
    else:
        return f"${num:,.2f}"


def fetch_stock_data():
    """获取美股数据"""
    result = {
        "last_update": datetime.now(timezone.utc).isoformat(),
        "source": "Yahoo Finance (yfinance)",
        "market_status": "open",
        "data": []
    }
    
    for symbol, info in STOCKS.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="2d")
            
            if hist.empty or len(hist) < 2:
                print(f"⚠️ {symbol}: 无数据")
                continue
            
            current_price = hist['Close'].iloc[-1]
            prev_close = hist['Close'].iloc[-2]
            high_52w = hist['High'].max()
            low_52w = hist['Low'].min()
            
            # 计算价格变化
            price_change = current_price - prev_close
            price_change_pct = (price_change / prev_close) * 100
            
            # 获取市值和PE
            info_data = ticker.info
            market_cap = info_data.get('marketCap', 0)
            pe_ratio = info_data.get('trailingPE', 0)
            
            stock_data = {
                "symbol": symbol,
                "name": info["name"],
                "sector": info["sector"],
                "current_price": round(current_price, 2),
                "price_change": round(price_change, 2),
                "price_change_percentage": round(price_change_pct, 2),
                "high_52w": round(high_52w, 2),
                "low_52w": round(low_52w, 2),
                "market_cap": market_cap,
                "market_cap_formatted": format_large_number(market_cap) if market_cap else "N/A",
                "pe_ratio": round(pe_ratio, 2) if pe_ratio else None,
                "prev_close": round(prev_close, 2),
            }
            
            result["data"].append(stock_data)
            print(f"✅ {symbol}: ${current_price:.2f} ({price_change_pct:+.2f}%)")
            
        except Exception as e:
            print(f"❌ {symbol}: 获取失败 - {e}")
            continue
    
    return result


if __name__ == "__main__":
    print("=" * 50)
    print("📈 开始获取美股数据...")
    print("=" * 50)
    
    data = fetch_stock_data()
    
    # 保存到JSON文件
    with open('stock_prices.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print("=" * 50)
    print(f"✅ 美股数据已保存，共 {len(data['data'])} 只股票")
    print(f"⏰ 更新时间: {data['last_update']}")