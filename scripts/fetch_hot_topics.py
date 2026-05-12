#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日热点话题抓取 - 国内 + 国际
国内: 微博热搜 / 知乎热榜
国际: Hacker News / NPR News / WSJ / GitHub Trending / Dev.to

GitHub Actions: 每天8点(UTC)运行，保存到 data/hot_topics.json
"""
import urllib.request, ssl, json, re, time, html
from datetime import datetime, timezone

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Hermes/1.0)",
    "Accept": "application/json, text/html, application/rss+xml",
}

def fetch_url(url, timeout=10):
    """通用HTTP GET，返回原始文本"""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"  [{url[:40]}] {e}")
        return None

def clean_text(text):
    """清理HTML，移除多余空白"""
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
        req = urllib.request.Request(url, headers={**HEADERS, "Referer": "https://weibo.com"})
        with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as resp:
            data = json.loads(resp.read().decode())
        if data and data.get("data", {}).get("realtime"):
            items = data["data"]["realtime"][:10]
            return [{"rank": i+1, "title": str(item.get("word", "")), "hot": item.get("raw_hot", "")} for i, item in enumerate(items)]
    except Exception as e:
        print(f"  微博热搜 error: {e}")
    return []

def fetch_zhihu_hot():
    """知乎热榜"""
    try:
        url = "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=10"
        req = urllib.request.Request(url, headers={**HEADERS, "User-Agent": "ZhihuAndroid/1.0"})
        with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as resp:
            data = json.loads(resp.read().decode())
        if data and data.get("data"):
            items = data["data"][:10]
            return [{"rank": i+1, "title": clean_text(item.get("target", {}).get("title", ""))} for i, item in enumerate(items)]
    except Exception as e:
        print(f"  知乎热榜 error: {e}")
    return []

# ========== 国际热点 ==========
def fetch_hackernews():
    """Hacker News Top Stories"""
    try:
        req = urllib.request.Request("https://hacker-news.firebaseio.com/v0/topstories.json", headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as resp:
            ids = json.loads(resp.read().decode())

        items = []
        for story_id in ids[:10]:
            try:
                req2 = urllib.request.Request(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json", headers=HEADERS)
                with urllib.request.urlopen(req2, timeout=8, context=SSL_CTX) as r:
                    item = json.loads(r.read().decode())
                if item.get("title"):
                    items.append({
                        "rank": len(items)+1,
                        "title": clean_text(item["title"]),
                        "score": item.get("score", 0),
                        "url": item.get("url", "")[:80]
                    })
                    time.sleep(0.05)
            except:
                continue
        return items
    except Exception as e:
        print(f"  Hacker News error: {e}")
    return []

def fetch_npr_news():
    """NPR News RSS"""
    raw = fetch_url("https://feeds.npr.org/1001/rss.xml")
    if raw:
        titles = re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>', raw)
        return [{"rank": i+1, "title": clean_text(t)} for i, t in enumerate(titles[2:12])]
    return []

def fetch_wsj_world():
    """WSJ World News RSS"""
    raw = fetch_url("https://feeds.a.dj.com/rss/RSSWorldNews.xml")
    if raw:
        titles = re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>', raw)
        return [{"rank": i+1, "title": clean_text(t)} for i, t in enumerate(titles[:10])]
    return []

def fetch_devto_feed():
    """Dev.to 技术热文 RSS"""
    raw = fetch_url("https://dev.to/feed")
    if raw:
        titles = re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>', raw)
        links = re.findall(r'<link>(https://dev\.to/[^<]+)</link>', raw)
        result = []
        for i, t in enumerate(titles[2:12]):
            link = links[i] if i < len(links) else ""
            result.append({"rank": i+1, "title": clean_text(t), "url": link[:80]})
        return result
    return []

def fetch_github_trending():
    """GitHub Trending 热门项目"""
    try:
        # 获取今日热门项目
        url = "https://api.github.com/search/repositories?q=created:>2026-05-09&sort=stars&order=desc&per_page=10"
        req = urllib.request.Request(url, headers={**HEADERS, "Accept": "application/vnd.github.v3+json"})
        with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as resp:
            data = json.loads(resp.read().decode())
        items = data.get("items", [])[:10]
        return [{
            "rank": i+1,
            "title": clean_text(item.get("full_name", "")),
            "desc": clean_text(item.get("description", "") or "")[:80],
            "stars": item.get("stargazers_count", 0),
            "language": item.get("language", ""),
        } for i, item in enumerate(items)]
    except Exception as e:
        print(f"  GitHub Trending error: {e}")
    return []

def fetch_lobsters():
    """Lobsters 热帖"""
    try:
        req = urllib.request.Request("https://lobste.rs/hottest.json", headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as resp:
            data = json.loads(resp.read().decode())
        return [{
            "rank": i+1,
            "title": clean_text(item.get("title", "")),
            "short_id": item.get("short_id", ""),
        } for i, item in enumerate(data[:10])]
    except Exception as e:
        print(f"  Lobsters error: {e}")
    return []

def main():
    print("🔍 每日热点话题抓取")
    print("="*50)

    print("\n📌 国内热点...")
    weibo = fetch_weibo_hot()
    zhihu = fetch_zhihu_hot()

    print(f"  微博热搜: {len(weibo)} 条")
    print(f"  知乎热榜: {len(zhihu)} 条")

    print("\n🌍 国际热点...")
    hn = fetch_hackernews()
    npr = fetch_npr_news()
    wsj = fetch_wsj_world()
    devto = fetch_devto_feed()
    gh = fetch_github_trending()
    lobsters = fetch_lobsters()

    print(f"  Hacker News: {len(hn)} 条")
    print(f"  NPR News: {len(npr)} 条")
    print(f"  WSJ World: {len(wsj)} 条")
    print(f"  Dev.to: {len(devto)} 条")
    print(f"  GitHub Trending: {len(gh)} 条")
    print(f"  Lobsters: {len(lobsters)} 条")

    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "domestic": {
            "weibo": {"source": "微博热搜", "items": weibo},
            "zhihu": {"source": "知乎热榜", "items": zhihu},
        },
        "international": {
            "hackernews": {"source": "Hacker News", "items": hn},
            "npr": {"source": "NPR News", "items": npr},
            "wsj": {"source": "WSJ World", "items": wsj},
            "devto": {"source": "Dev.to", "items": devto},
            "github": {"source": "GitHub Trending", "items": gh},
            "lobsters": {"source": "Lobsters", "items": lobsters},
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

    # 摘要
    print("\n" + "="*50)
    print("📰 国内 TOP3 (微博)")
    for item in weibo[:3]:
        print(f"  {item['rank']}. {item['title'][:40]}")
    print("\n🌍 国际 TOP3 (Hacker News)")
    for item in hn[:3]:
        print(f"  {item['rank']}. {item['title'][:40]}")

    return result

if __name__ == "__main__":
    main()
