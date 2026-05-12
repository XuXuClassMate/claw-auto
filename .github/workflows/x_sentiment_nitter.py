#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
X/Twitter 情绪监控 - RSS 方案
GitHub Actions Runner 上验证可用的数据源:
  ✅ CoinTelegraph RSS (https://cointelegraph.com/rss)
  ✅ CryptoNews RSS (https://cryptonews.com/feed/)
  ✅ Decrypt RSS (https://decrypt.co/feed)
  ✅ alternative.me Fear&Greed Index

GitHub Actions: 每4小时自动运行，更新 data/x_sentiment.json
"""

import urllib.request, ssl, json, re, time, sys, html
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.parent.parent  # -> repo root
SENTIMENT_FILE = SCRIPT_DIR / "data" / "x_sentiment.json"
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Hermes/1.0)",
    "Accept": "application/rss+xml, application/xml, text/xml, application/atom+xml",
}

RSS_FEEDS = {
    "crypto": [
        "https://cointelegraph.com/rss",
        "https://cryptonews.com/feed/",
        "https://decrypt.co/feed",
    ],
    "stocks": [
        "https://cointelegraph.com/rss",  # 兼顾科技股新闻
    ],
}

# ========== 情绪分析 ==========
BULLISH_KW = [
    "bullish", "buy", "long", "moon", "pump", "gain", "rise", "up", "high", 
    "breakout", "call", "accumulate", "hold", "soar", "surge", "rally", "growth",
    "新高", "突破", "看涨", "买入", "暴涨", "疯涨", "强势",
]
BEARISH_KW = [
    "bearish", "sell", "short", "dump", "drop", "fall", "down", "low", 
    "breakdown", "put", "warn", "crash", "lose", "plunge", "decline", "risk",
    "暴跌", "崩盘", "看跌", "卖出", "新低", "破位", "风险", "警告",
]

def score_text(text):
    t = text.lower()
    bull = sum(1 for k in BULLISH_KW if k in t)
    bear = sum(1 for k in BEARISH_KW if k in t)
    if bull + bear == 0:
        return 50, "neutral"
    score = (bull - bear) / (bull + bear) * 50 + 50
    label = "bullish" if score >= 58 else "bearish" if score <= 42 else "neutral"
    return round(min(max(score, 0), 100), 1), label

def clean_html(text):
    """去除HTML标签"""
    text = re.sub(r'<[^>]+>', '', text)
    text = html.unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# ========== RSS 抓取 ==========
def fetch_rss(url, timeout=10):
    """抓取RSS并提取文章"""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
        return raw
    except Exception as e:
        print(f"  RSS [{url}] error: {e}", file=sys.stderr)
        return ""

def parse_rss_items(xml_content):
    """解析RSS/Atom XML，提取所有文章标题和描述"""
    items = []
    
    # 提取 <item> 标签 (RSS 2.0)
    for item_match in re.finditer(r'<item[^>]*>(.*?)</item>', xml_content, re.DOTALL):
        item_xml = item_match.group(1)
        title = re.search(r'<title[^>]*><!\[CDATA\[(.*?)\]\]></title>|<title[^>]*>(.*?)</title>', item_xml, re.DOTALL)
        desc = re.search(r'<description[^>]*><!\[CDATA\[(.*?)\]\]></description>|<description[^>]*>(.*?)</description>', item_xml, re.DOTALL)
        link = re.search(r'<link[^>]*>(.*?)</link>', item_xml, re.DOTALL)
        
        t = ""
        if title:
            t = title.group(1) or title.group(2) or ""
        d = ""
        if desc:
            d = desc.group(1) or desc.group(2) or ""
        
        t = clean_html(t)
        d = clean_html(d)
        
        if t:
            items.append({"title": t, "desc": d[:300], "text": t + " " + d})
    
    # 提取 <entry> 标签 (Atom)
    for entry_match in re.finditer(r'<entry[^>]*>(.*?)</entry>', xml_content, re.DOTALL):
        entry_xml = entry_match.group(1)
        title = re.search(r'<title[^>]*><!\[CDATA\[(.*?)\]\]></title>|<title[^>]*>(.*?)</title>', entry_xml, re.DOTALL)
        summary = re.search(r'<summary[^>]*><!\[CDATA\[(.*?)\]\]></summary>|<summary[^>]*>(.*?)</summary>', entry_xml, re.DOTALL)
        content = re.search(r'<content[^>]*><!\[CDATA\[(.*?)\]\]></content>|<content[^>]*>(.*?)</content>', entry_xml, re.DOTALL)
        
        t = ""
        if title:
            t = title.group(1) or title.group(2) or ""
        s = ""
        if summary:
            s = summary.group(1) or summary.group(2) or ""
        elif content:
            s = content.group(1) or content.group(2) or ""
        
        t = clean_html(t)
        s = clean_html(s)
        
        if t:
            items.append({"title": t, "desc": s[:300], "text": t + " " + s})
    
    return items

def fetch_fear_greed():
    """获取 alternative.me 恐惧贪婪指数"""
    try:
        url = "https://api.alternative.me/fng/"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8, context=SSL_CTX) as resp:
            d = json.loads(resp.read())
        item = d.get("data", [{}])[0]
        return {"value": int(item.get("value", 50)), "classification": item.get("value_classification", "Neutral")}
    except Exception as e:
        print(f"  FGI error: {e}", file=sys.stderr)
        return {"value": 50, "classification": "Unknown"}

def analyze_rss_sentiment(feeds, keywords=None):
    """从RSS源提取并分析情绪"""
    all_articles = []
    
    for feed_url in feeds:
        print(f"  📡 {feed_url[:50]}...", file=sys.stderr)
        xml = fetch_rss(feed_url)
        if xml:
            items = parse_rss_items(xml)
            all_articles.extend(items)
            print(f"    -> {len(items)} articles", file=sys.stderr)
            time.sleep(0.5)
    
    if not all_articles:
        return {"signal": "⚠️ 无数据", "score": 50, "confidence": 0, "total": 0, "articles": []}
    
    # 关键词过滤（如果指定了关键词）
    if keywords:
        filtered = []
        kw_pattern = "|".join(re.escape(k) for k in keywords)
        for article in all_articles:
            if re.search(kw_pattern, article["text"], re.IGNORECASE):
                filtered.append(article)
        if filtered:
            all_articles = filtered
    
    # 评分
    scored = []
    for article in all_articles:
        score, label = score_text(article["text"])
        scored.append((article, score, label))
    
    bull = [a for a, s, l in scored if l == "bullish"]
    bear = [a for a, s, l in scored if l == "bearish"]
    neut = [a for a, s, l in scored if l == "neutral"]
    total = len(scored)
    avg = sum(s for _, s, _ in scored) / total if total else 50
    conf = min(round(max(len(bull), len(bear)) / total * 100), 90) if total else 20
    
    if len(bull) > len(bear) and len(bull) > len(neut):
        sig = "🟢 偏多"
    elif len(bear) > len(bull) and len(bear) > len(neut):
        sig = "🔴 偏空"
    else:
        sig = "🟡 中性"
    
    # 样本（找最有情绪的）
    samples = []
    for article, score, label in sorted(scored, key=lambda x: x[1]):
        if label != "neutral" and len(samples) < 3:
            samples.append({
                "title": article["title"][:100],
                "sentiment": label,
                "score": score
            })
    
    return {
        "signal": sig,
        "score": round(avg, 1),
        "confidence": conf,
        "total": total,
        "bull_count": len(bull),
        "bear_count": len(bear),
        "articles": all_articles[:5],
        "samples": samples
    }

# ========== 主流程 ==========
def run():
    print("🔍 X/社交媒体情绪监控 (RSS方案)", file=sys.stderr)
    print("="*60, file=sys.stderr)
    
    # Fear & Greed Index
    print("\n📊 Fear & Greed Index...", file=sys.stderr)
    fg = fetch_fear_greed()
    print(f"  FGI: {fg['value']} ({fg['classification']})", file=sys.stderr)
    
    # 加密货币情绪
    print("\n🪙 加密货币情绪 (CoinTelegraph + CryptoNews + Decrypt)...", file=sys.stderr)
    crypto_kw = ["BTC", "Bitcoin", "ETH", "Ethereum", "BNB", "crypto", "Coin", "DeFi"]
    crypto_sent = analyze_rss_sentiment(RSS_FEEDS["crypto"], keywords=crypto_kw)
    print(f"  {crypto_sent['signal']} (score={crypto_sent['score']}, conf={crypto_sent['confidence']}%) [{crypto_sent['total']}篇]", file=sys.stderr)
    
    # 美股情绪
    print("\n🇺🇸 美股情绪 (CoinTelegraph)...", file=sys.stderr)
    stock_kw = ["NVDA", "Nvidia", "TSLA", "Tesla", "AAPL", "Apple", "stock", "S&P", "Fed", "ETF"]
    stock_sent = analyze_rss_sentiment(RSS_FEEDS["stocks"], keywords=stock_kw)
    print(f"  {stock_sent['signal']} (score={stock_sent['score']}, conf={stock_sent['confidence']}%) [{stock_sent['total']}篇]", file=sys.stderr)
    
    # 按标的汇总
    results = {}
    
    # FGI 调整
    fgi_val = fg["value"]
    if fgi_val >= 65:
        fgi_adj = 8
    elif fgi_val >= 55:
        fgi_adj = 4
    elif fgi_val <= 35:
        fgi_adj = -8
    elif fgi_val <= 45:
        fgi_adj = -4
    else:
        fgi_adj = 0
    
    # 加密标的
    crypto_syms = {
        "BTC": ["BTC", "Bitcoin", "bitcoin"],
        "ETH": ["ETH", "Ethereum", "ethereum"],
        "BNB": ["BNB", "Binance"],
    }
    
    for sym, kws in crypto_syms.items():
        sym_articles = []
        for article in crypto_sent.get("articles", []):
            if any(k.lower() in article["text"].lower() for k in kws):
                sym_articles.append(article)
        
        if sym_articles:
            scored = [(a, *score_text(a["text"])) for a in sym_articles]
            avg_s = sum(s for _, s, _ in scored) / len(scored)
            bull = sum(1 for _, _, l in scored if l == "bullish")
            bear = sum(1 for _, _, l in scored if l == "bearish")
            conf = min(round(max(bull, bear) / len(scored) * 100), 90)
            adj = min(max(avg_s + fgi_adj, 0), 100)
            
            if adj >= 60:
                sig = "🟢 偏多"
            elif adj <= 40:
                sig = "🔴 偏空"
            else:
                sig = "🟡 中性"
            
            results[sym] = {
                "signal": sig,
                "score": round(adj, 1),
                "raw_score": round(avg_s, 1),
                "fgi_adjust": fgi_adj,
                "confidence": conf,
                "fgi_value": fgi_val,
                "fgi_class": fg["classification"],
                "total_articles": len(sym_articles),
                "samples": [{"title": a["title"][:100], "sentiment": score_text(a["text"])[1]} for a in sym_articles[:2]]
            }
        else:
            # 没有专门文章，用整体加密情绪
            adj = min(max(crypto_sent["score"] + fgi_adj, 0), 100)
            results[sym] = {
                "signal": "🟡 中性" if 40 <= adj <= 60 else ("🟢 偏多" if adj >= 60 else "🔴 偏空"),
                "score": round(adj, 1),
                "raw_score": crypto_sent["score"],
                "fgi_adjust": fgi_adj,
                "confidence": crypto_sent["confidence"],
                "fgi_value": fgi_val,
                "fgi_class": fg["classification"],
                "total_articles": 0,
                "note": "使用整体加密市场情绪"
            }
    
    # 美股标的
    us_syms = {
        "NVDA": ["NVDA", "Nvidia", "nvidia", "GPU", "AI chip"],
        "TSLA": ["TSLA", "Tesla", "tesla", "EV", "elon"],
        "AAPL": ["AAPL", "Apple", "apple", "iPhone", "iOS"],
        "SPY": ["S&P", "SPY", "stock market", "index", "ETF"],
    }
    
    us_fgi_adj = fgi_adj * 0.3  # FGI对美股影响较小
    for sym, kws in us_syms.items():
        sym_articles = []
        for article in stock_sent.get("articles", []):
            if any(k.lower() in article["text"].lower() for k in kws):
                sym_articles.append(article)
        
        if sym_articles:
            scored = [(a, *score_text(a["text"])) for a in sym_articles]
            avg_s = sum(s for _, s, _ in scored) / len(scored)
            bull = sum(1 for _, _, l in scored if l == "bullish")
            bear = sum(1 for _, _, l in scored if l == "bearish")
            conf = min(round(max(bull, bear) / len(scored) * 100), 90)
            adj = min(max(avg_s + us_fgi_adj, 0), 100)
            
            if adj >= 60:
                sig = "🟢 偏多"
            elif adj <= 40:
                sig = "🔴 偏空"
            else:
                sig = "🟡 中性"
            
            results[sym] = {
                "signal": sig,
                "score": round(adj, 1),
                "raw_score": round(avg_s, 1),
                "confidence": conf,
                "fgi_value": fgi_val,
                "total_articles": len(sym_articles),
                "samples": [{"title": a["title"][:100], "sentiment": score_text(a["text"])[1]} for a in sym_articles[:2]]
            }
        else:
            results[sym] = {
                "signal": "🟡 中性",
                "score": round(stock_sent["score"] * 0.5 + 50, 1),
                "confidence": 20,
                "fgi_value": fgi_val,
                "total_articles": 0,
                "note": "使用整体市场情绪"
            }
    
    # 保存
    SENTIMENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "source": "RSS feeds (CoinTelegraph + CryptoNews + Decrypt)",
        "fear_greed": fg,
        "results": results,
        "methodology": "RSS新闻情绪关键词分析 + Fear&Greed指数加权",
        "rss_feeds": RSS_FEEDS,
    }
    
    with open(SENTIMENT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Saved: {SENTIMENT_FILE}", file=sys.stderr)
    
    # 打印摘要
    print("\n" + "="*60, file=sys.stderr)
    print("📊 情绪分析摘要", file=sys.stderr)
    print(f"  FGI: {fg['value']} ({fg['classification']})", file=sys.stderr)
    print("\n  🪙 加密货币:", file=sys.stderr)
    for sym in ["BTC", "ETH", "BNB"]:
        d = results.get(sym, {})
        print(f"    {sym}: {d.get('signal','⚠️')} (score={d.get('score','?')}, conf={d.get('confidence','?')}% [{d.get('total_articles',0)}篇])", file=sys.stderr)
    print("\n  🇺🇸 美股:", file=sys.stderr)
    for sym in ["NVDA", "TSLA", "AAPL", "SPY"]:
        d = results.get(sym, {})
        print(f"    {sym}: {d.get('signal','⚠️')} (score={d.get('score','?')}, conf={d.get('confidence','?')}% [{d.get('total_articles',0)}篇])", file=sys.stderr)
    
    return result

if __name__ == "__main__":
    run()
