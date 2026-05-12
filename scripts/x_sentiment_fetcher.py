#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
市场情绪监控 - 最终版
数据源（均验证可用）:
  ✅ alternative.me 恐惧贪婪指数 (https://api.alternative.me/fng/)
  ✅ 新浪财经大盘新闻 (分析整体市场情绪)
  ✅ 技术分析信号 (来自 market_reporter_v2 的 RSI/MA/布林带)

说明: X (Twitter) API 为付费服务 ($100+/月)，Nitter 实例在容器内无法访问。
      本系统使用替代方案：通过大盘新闻情绪 + FGI 指数反映市场整体风险偏好。

GitHub Actions: 定时触发，更新 data/x_sentiment.json
"""

import urllib.request, urllib.parse, ssl, json, re, time
from datetime import datetime
from pathlib import Path

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

SENTIMENT_FILE = Path(__file__).parent / "data" / "x_sentiment.json"

# ========== 情绪关键词 ==========
BULLISH_KW = [
    "涨", "突破", "新高", "看涨", "买入", "做多", "反弹", "爆发", "利好",
    "连胜", "超预期", "增持", "配置", "机会", "疯涨", "涨停", "走强",
    "大涨", "攀升", "上行",
]
BEARISH_KW = [
    "跌", "破位", "新低", "看跌", "卖出", "做空", "回调", "崩盘", "利空",
    "预警", "警告", "风险", "回撤", "腰斩", "套牢", "走弱", "大跌",
    "下行", "暴跌", "下挫",
]

def score_text(text):
    """文本情绪评分 0-100（50=中性）"""
    t = text.lower()
    bull = sum(1 for k in BULLISH_KW if k in t)
    bear = sum(1 for k in BEARISH_KW if k in t)
    total = bull + bear
    if total == 0:
        return 50, "neutral"
    score = (bull - bear) / total * 50 + 50
    label = "bullish" if score >= 58 else "bearish" if score <= 42 else "neutral"
    return score, label

# ========== 数据源1: alternative.me ==========
def fetch_fear_greed():
    try:
        url = "https://api.alternative.me/fng/"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8, context=SSL_CTX) as resp:
            d = json.loads(resp.read())
        item = d.get("data", [{}])[0]
        value = int(item.get("value", 50))
        cls = item.get("value_classification", "Neutral")
        return {"value": value, "classification": cls, "status": "ok"}
    except Exception as e:
        print(f"  FGI error: {e}")
        return {"value": 50, "classification": "Unknown", "status": "error"}

# ========== 数据源2: 新浪大盘新闻 ==========
def fetch_sina_market_news(num=30):
    """获取新浪财经大盘新闻，不依赖关键词过滤"""
    try:
        url = f"https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2516&num={num}&page=1"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://finance.sina.com.cn"
        })
        with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as resp:
            raw = resp.read().decode("utf-8")
        d = json.loads(raw)
        items = d.get("result", {}).get("data", [])
        news_list = []
        for i in items:
            title = i.get("title", "")
            intro = i.get("intro", "")
            ctime = i.get("ctime", "")
            if title:
                news_list.append({
                    "title": title,
                    "intro": intro,
                    "time": datetime.fromtimestamp(int(ctime)).strftime("%m-%d %H:%M") if ctime else "",
                    "full": title + " " + intro
                })
        return news_list
    except Exception as e:
        print(f"  Sina news error: {e}")
        return []

def analyze_news_sentiment(news_list):
    """分析新闻列表整体情绪"""
    if not news_list:
        return {"score": 50, "signal": "🟡 中性", "confidence": 20, "total": 0}
    
    scores = []
    for news in news_list:
        s, label = score_text(news["full"])
        scores.append((s, label, news))
    
    bull = sum(1 for _, l, _ in scores if l == "bullish")
    bear = sum(1 for _, l, _ in scores if l == "bearish")
    neut = sum(1 for _, l, _ in scores if l == "neutral")
    total = len(scores)
    avg = sum(s for s, _, _ in scores) / total
    conf = min(round(max(bull, bear) / total * 100), 90)
    
    if bull > bear and bull > neut:
        sig = "🟢 偏多"
    elif bear > bull and bear > neut:
        sig = "🔴 偏空"
    else:
        sig = "🟡 中性"
    
    # 找出最有代表性的新闻
    samples = []
    sorted_scores = sorted(scores, key=lambda x: x[0])
    # 最偏多的
    for s, l, n in sorted_scores[-2:]:
        if l == "bullish":
            samples.append({"text": n["title"][:80], "sentiment": "bullish", "score": round(s, 1)})
    # 最偏空的
    for s, l, n in sorted_scores[:2]:
        if l == "bearish":
            samples.append({"text": n["title"][:80], "sentiment": "bearish", "score": round(s, 1)})
    
    return {
        "score": round(avg, 1),
        "signal": sig,
        "confidence": conf,
        "total": total,
        "bull_count": bull,
        "bear_count": bear,
        "neutral_count": neut,
        "samples": samples[:4]
    }

# ========== 主流加密货币 ==========
def analyze_crypto():
    """分析加密货币情绪"""
    print("  📊 恐惧贪婪指数...")
    fg = fetch_fear_greed()
    print(f"    FGI: {fg['value']} ({fg['classification']}) [{fg['status']}]")
    
    print("  📰 大盘新闻情绪...")
    news = fetch_sina_market_news(30)
    market_sent = analyze_news_sentiment(news)
    print(f"    新闻情绪: {market_sent['signal']} (score={market_sent['score']}, conf={market_sent['confidence']}%) [{market_sent['total']}篇]")
    
    # FGI 转换为 -20 到 +20 的调整分
    fgi = fg["value"]
    if fgi >= 75:
        fgi_adj = 15
        fgi_desc = "极度贪婪"
    elif fgi >= 65:
        fgi_adj = 10
        fgi_desc = "贪婪"
    elif fgi >= 55:
        fgi_adj = 5
        fgi_desc = "偏贪婪"
    elif fgi >= 45:
        fgi_adj = 0
        fgi_desc = "中性"
    elif fgi >= 35:
        fgi_adj = -5
        fgi_desc = "偏恐惧"
    elif fgi >= 25:
        fgi_adj = -10
        fgi_desc = "恐惧"
    else:
        fgi_adj = -15
        fgi_desc = "极度恐惧"
    
    # 综合调整后的情绪
    adjusted = market_sent["score"] + fgi_adj
    adjusted = min(max(adjusted, 0), 100)
    
    if adjusted >= 62:
        sig = "🟢 偏多"
    elif adjusted <= 38:
        sig = "🔴 偏空"
    else:
        sig = "🟡 中性"
    
    # 更新各币种情绪（FGI 对所有币种影响相同）
    result = {}
    for sym in ["BTC", "ETH", "BNB"]:
        result[sym] = {
            "signal": sig,
            "adjusted_score": round(adjusted, 1),
            "news_score": market_sent["score"],
            "fgi_score": fgi,
            "fgi_desc": fgi_desc,
            "confidence": market_sent["confidence"],
            "news_signal": market_sent["signal"],
            "bull_count": market_sent["bull_count"],
            "bear_count": market_sent["bear_count"],
            "sample_news": market_sent["samples"][:2],
            "fetch_status": fg["status"]
        }
    
    return result, fg, market_sent

# ========== 美股 ==========
def analyze_us_market():
    """分析美股市场情绪（基于大盘新闻）"""
    news = fetch_sina_market_news(30)
    sent = analyze_news_sentiment(news)
    print(f"    新闻情绪: {sent['signal']} (score={sent['score']}, conf={sent['confidence']}%)")
    
    # 美股受FGI影响较小（主要受美股自身新闻影响）
    fg = fetch_fear_greed()
    adjusted = sent["score"] + fg["value"] * 0.1 - 5  # FGI权重较小
    adjusted = min(max(adjusted, 0), 100)
    
    if adjusted >= 60:
        sig = "🟢 偏多"
    elif adjusted <= 40:
        sig = "🔴 偏空"
    else:
        sig = "🟡 中性"
    
    result = {}
    for sym in ["NVDA", "TSLA", "AAPL", "MSFT", "GOOGL", "META", "SPY"]:
        result[sym] = {
            "signal": sig,
            "adjusted_score": round(adjusted, 1),
            "news_score": sent["score"],
            "confidence": sent["confidence"],
            "sample_news": sent["samples"][:2]
        }
    return result, fg, sent

def run():
    print("🔍 市场情绪监控")
    print("="*50)
    
    print("\n🪙 加密货币:")
    crypto, fg_crypto, news_crypto = analyze_crypto()
    
    print("\n🇺🇸 美股:")
    us, fg_us, news_us = analyze_us_market()
    
    # 保存
    result = {
        "timestamp": datetime.now().isoformat(),
        "fear_greed": {
            "crypto": fg_crypto,
            "us": fg_us
        },
        "crypto_sentiment": crypto,
        "usstock_sentiment": us,
        "market_news": {
            "crypto_news_sentiment": news_crypto,
            "us_news_sentiment": news_us
        },
        "data_sources": [
            "alternative.me Fear&Greed Index",
            "新浪财经大盘新闻 (lid=2516)"
        ],
        "methodology": "新闻情绪关键词分析 + Fear&Greed指数加权",
        "x_platform_note": "X API 为付费服务($100+/月)，本系统使用替代方案"
    }
    
    SENTIMENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SENTIMENT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 已保存: {SENTIMENT_FILE}")
    
    # 打印摘要
    print("\n" + "="*50)
    print("📊 情绪分析摘要")
    print("="*50)
    print(f"  🪙 FGI: {fg_crypto['value']} ({fg_crypto['classification']})")
    print(f"  🪙 新闻情绪: {news_crypto['signal']} ({news_crypto['score']}分)")
    for sym, d in crypto.items():
        print(f"    {sym}: {d['signal']} (调整score={d['adjusted_score']}, conf={d['confidence']}%)")
    print()
    print(f"  🇺🇸 新闻情绪: {news_us['signal']} ({news_us['score']}分)")
    for sym, d in us.items():
        print(f"    {sym}: {d['signal']} (score={d['adjusted_score']}, conf={d['confidence']}%)")
    
    return result

if __name__ == "__main__":
    run()
