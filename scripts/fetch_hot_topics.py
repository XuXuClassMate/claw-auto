#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日热点话题抓取 - 国内 + 国际
数据源:
  国内: 新浪微博热搜 / 百度热榜 / 知乎热榜
  国际: Reddit r/all / Twitter/X trending / Google Trends

GitHub Actions: 每天8点(UTC)运行，保存到 data/hot_topics.json
"""
import urllib.request, ssl, json, re, time, html
from datetime import datetime, timezone

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Hermes/1.0)",
    "Accept": "application/json, text/html",
}

def fetch_json(url, headers=None, timeout=10):
    try:
        h = dict(HEADERS)
        if headers:
            h.update(headers)
        req = urllib.request.Request(url, headers=h)
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
            return json.loads(raw)
    except Exception as e:
        print(f"  error: {e}")
        return None

def clean_text(text):
    """清理HTML，移除多余空白（保留中文）"""
    try:
        text = re.sub(r'<[^>]+>', '', text)
        text = html.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:200]
    except:
        return str(text)[:200]

# ========== 国内热点 ==========
def fetch_weibo_hot():
    """微博热搜榜"""
    try:
        url = "https://weibo.com/ajax/side/hotSearch"
        data = fetch_json(url, {"Referer": "https://weibo.com"})
        if data and data.get("data", {}).get("realtime"):
            items = data["data"]["realtime"][:10]
            return [{"rank": i+1, "title": str(item.get("word", "")), "hot": item.get("raw_hot", "")} for i, item in enumerate(items)]
    except Exception as e:
        print(f"  微博热搜 error: {e}")
    return []

def fetch_baidu_hot():
    """百度热搜榜"""
    try:
        url = "https://top.baidu.com/api.php?query=热搜&sf=1&expires=1h"
        data = fetch_json(url)
        if data and data.get("data"):
            items = data["data"][:10]
            return [{"rank": i+1, "title": clean_text(item.get("query", "")), "hot": item.get("hotScore", "")} for i, item in enumerate(items)]
    except Exception as e:
        print(f"  百度热搜 error: {e}")
    return []

def fetch_zhihu_hot():
    """知乎热榜"""
    try:
        url = "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=10"
        data = fetch_json(url, {"User-Agent": "ZhihuOAuth/1.0"})
        if data and data.get("data"):
            items = data["data"][:10]
            return [{"rank": i+1, "title": clean_text(item.get("target", {}).get("title", "")), "desc": clean_text(item.get("target", {}).get("excerpt", ""))[:100]} for i, item in enumerate(items)]
    except Exception as e:
        print(f"  知乎热搜 error: {e}")
    return []

# ========== 国际热点 ==========
def fetch_reddit_hot():
    """Reddit r/all 热帖"""
    try:
        url = "https://www.reddit.com/r/all/hot.json?limit=10"
        data = fetch_json(url)
        if data and data.get("data", {}).get("children"):
            items = data["data"]["children"]
            return [{"rank": i+1, "title": clean_text(item["data"].get("title", "")), "subreddit": item["data"].get("subreddit", ""), "score": item["data"].get("score", 0)} for i, item in enumerate(items)]
    except Exception as e:
        print(f"  Reddit error: {e}")
    return []

def fetch_twitter_trending():
    """Twitter/X Trending (via Nitter instance - 免费方案)"""
    # Nitter 实例列表（备用）
    nitter_instances = [
        "https://nitter.net",
        "https://nitter.privacydev.net",
        "https://nitter.poast.org",
    ]
    for instance in nitter_instances:
        try:
            url = f"{instance}/i/trends"
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=8, context=SSL_CTX) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
            
            # 解析趋势标签
            trends = re.findall(r'href="/[a-zA-Z0-9_]+/search\?q=[^"]+">([^<]+)<', raw)
            if trends:
                return [{"rank": i+1, "topic": clean_text(t)} for i, t in enumerate(trends[:10])]
        except Exception as e:
            print(f"  Nitter [{instance}] error: {e}")
            continue
    return []

def fetch_google_trends():
    """Google Trends 实时热点 (via alternative.me)"""
    try:
        # Google Trends 没有免费公开API，用 CryptoCompare 的 news 作为国际经济参考
        url = "https://min-api.cryptocompare.com/data/v2/news/?lang=EN&categories=Technology"
        data = fetch_json(url)
        if data and data.get("Data"):
            items = data["Data"][:10]
            return [{"rank": i+1, "title": clean_text(item.get("title", "")), "source": item.get("categories", ""), "url": item.get("url", "")[:80]} for i, item in enumerate(items)]
    except Exception as e:
        print(f"  Google Trends error: {e}")
    return []

def fetch_bbc_news():
    """BBC News 国际要闻"""
    try:
        url = "https://feeds.bbci.co.uk/news/world/rss.xml"
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
        items = re.findall(r'<item><title><!\[CDATA\[(.*?)\]\]></title>.*?<description><!\[CDATA\[(.*?)\]\]>', raw, re.DOTALL)
        return [{"rank": i+1, "title": clean_text(t), "desc": clean_text(d)[:100]} for i, (t, d) in enumerate(items[:10])]
    except Exception as e:
        print(f"  BBC error: {e}")
    return []

def main():
    print("🔍 每日热点话题抓取")
    print("="*50)
    
    print("\n📌 国内热点...")
    weibo = fetch_weibo_hot()
    baidu = fetch_baidu_hot()
    zhihu = fetch_zhihu_hot()
    
    print(f"  微博热搜: {len(weibo)} 条")
    print(f"  百度热搜: {len(baidu)} 条")
    print(f"  知乎热榜: {len(zhihu)} 条")
    
    print("\n🌍 国际热点...")
    reddit = fetch_reddit_hot()
    twitter = fetch_twitter_trending()
    bbc = fetch_bbc_news()
    
    print(f"  Reddit r/all: {len(reddit)} 条")
    print(f"  Twitter/X趋势: {len(twitter)} 条")
    print(f"  BBC News: {len(bbc)} 条")
    
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "domestic": {
            "weibo": {"source": "微博热搜", "items": weibo},
            "baidu": {"source": "百度热搜", "items": baidu},
            "zhihu": {"source": "知乎热榜", "items": zhihu},
        },
        "international": {
            "reddit": {"source": "Reddit r/all", "items": reddit},
            "twitter": {"source": "Twitter/X Trending", "items": twitter},
            "bbc": {"source": "BBC News World", "items": bbc},
        },
    }
    
    # 保存
    import os
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "hot_topics.json")
    out_path = os.path.normpath(out_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 已保存: {out_path}")
    
    # 打印摘要
    print("\n" + "="*50)
    print("📰 国内热点 TOP5 (微博)")
    for item in weibo[:5]:
        print(f"  {item['rank']}. {item['title'][:40]}")
    
    print("\n🌍 国际热点 TOP5 (Reddit)")
    for item in reddit[:5]:
        print(f"  {item['rank']}. {item['title'][:40]}")
    
    return result

if __name__ == "__main__":
    main()
