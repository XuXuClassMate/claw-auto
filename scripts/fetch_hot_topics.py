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
def fetch_hackernews():
    """Hacker News 热帖"""
    try:
        # 获取Top Stories IDs
        ids_url = "https://hacker-news.firebaseio.com/v0/topstories.json"
        req = urllib.request.Request(ids_url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as resp:
            ids = json.loads(resp.read().decode())
        
        items = []
        for story_id in ids[:10]:
            try:
                item_url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
                req2 = urllib.request.Request(item_url, headers=HEADERS)
                with urllib.request.urlopen(req2, timeout=8, context=SSL_CTX) as r:
                    item = json.loads(r.read().decode())
                if item.get("title"):
                    items.append({
                        "rank": len(items)+1,
                        "title": clean_text(item.get("title", "")),
                        "score": item.get("score", 0),
                        "url": item.get("url", "")[:80]
                    })
                    time.sleep(0.1)
            except:
                continue
        return items
    except Exception as e:
        print(f"  Hacker News error: {e}")
        return []

def fetch_google_news():
    """Google News 国际要闻 RSS"""
    try:
        url = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
        items = re.findall(r'<item><title><!\[CDATA\[(.*?)\]\]></title>.*?<link>(.*?)</link>', raw, re.DOTALL)
        result = []
        for i, (title, link) in enumerate(items[:10]):
            result.append({
                "rank": i+1,
                "title": clean_text(title),
                "link": link.strip()[:100]
            })
        return result
    except Exception as e:
        print(f"  Google News error: {e}")
        return []

def fetch_reuters_world():
    """路透社世界新闻"""
    try:
        url = "https://feeds.reuters.com/reuters/worldnews"
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
        titles = re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>', raw)
        return [{"rank": i+1, "title": clean_text(t)} for i, t in enumerate(titles[2:12])]  # skip header
    except Exception as e:
        print(f"  Reuters error: {e}")
        return []

def fetch_aljazeera():
    """半岛电视台 Al Jazeera"""
    try:
        url = "https://www.aljazeera.com/xml/rss/all.xml"
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
        titles = re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>', raw)
        return [{"rank": i+1, "title": clean_text(t)} for i, t in enumerate(titles[2:12])]
    except Exception as e:
        print(f"  Al Jazeera error: {e}")
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
    hn = fetch_hackernews()
    google = fetch_google_news()
    reuters = fetch_reuters_world()
    alj = fetch_aljazeera()
    
    print(f"  Hacker News: {len(hn)} 条")
    print(f"  Google News: {len(google)} 条")
    print(f"  路透社: {len(reuters)} 条")
    print(f"  半岛电视台: {len(alj)} 条")
    
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "domestic": {
            "weibo": {"source": "微博热搜", "items": weibo},
            "baidu": {"source": "百度热搜", "items": baidu},
            "zhihu": {"source": "知乎热榜", "items": zhihu},
        },
        "international": {
            "hackernews": {"source": "Hacker News", "items": hn},
            "google": {"source": "Google News", "items": google},
            "reuters": {"source": "Reuters World", "items": reuters},
            "aljazeera": {"source": "Al Jazeera", "items": alj},
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
    
    print("\n🌍 国际热点 TOP5 (Hacker News)")
    for item in hn[:5]:
        print(f"  {item['rank']}. {item['title'][:40]}")
    
    return result

if __name__ == "__main__":
    main()
