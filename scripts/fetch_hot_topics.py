#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日热点话题抓取 - 国内 + 国际 + X/Twitter
国内: 微博热搜 / 知乎热榜
国际: Hacker News / GitHub Trending / StackExchange / Lobsters
X/Twitter: Nitter 实例抓取 trending 话题

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

# ========== X/Twitter ==========
def fetch_x_trending():
    """通过 Nitter 实例抓取 X/Twitter trending 话题。"""
    # 尝试多个 Nitter 实例（RSS + HTML fallback）
    nitter_instances = [
        "https://nitter.net",
        "https://nitter.privacydev.net",
        "https://nitter.poast.org",
        "https://nitter.fdn.fr",
        "https://nitter.kavin.rocks",
    ]
    items = []

    # 策略1: 尝试 RSS feed（部分实例支持 /rss/trending）
    for base in nitter_instances:
        try:
            url = f"{base}/rss/trending"
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=8, context=SSL_CTX) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
            titles = re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>', raw)
            titles = [clean_text(t) for t in titles if t.strip() and "nitter" not in t.lower()]
            if titles:
                for i, title in enumerate(titles[:10], 1):
                    items.append({"rank": i, "title": title})
                print(f"  X/Twitter Trending (RSS@{base}): {len(items)} 条")
                return items
        except Exception:
            pass

    # 策略2: HTML 抓取 explore 页面（趋势话题）
    for base in nitter_instances:
        try:
            url = f"{base}/i/trends"
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=8, context=SSL_CTX) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
            # 找趋势链接模式: /search?q=%23xxx
            trends = re.findall(r'href="(/search\?q=%23[^"&]+)"[^>]*>([^<]+)<', raw)
            if trends:
                trends = trends[:10]
            else:
                # 备选: 找任意趋势标签
                trends = re.findall(r'href="(/search\?q=[^"&]+)"[^>]*>([^<]+)<', raw)
                trends = [(t[0], t[1]) for t in trends if '%23' in t[0]][:10]
            if not trends:
                # 备选: 抓 JS 里的趋势数据
                js_trends = re.findall(r'"name":"(#[^"]+)","url"', raw)
                if js_trends:
                    for i, name in enumerate(js_trends[:10], 1):
                        items.append({"rank": i, "title": name})
                    print(f"  X/Twitter Trending (JS@{base}): {len(items)} 条")
                    return items
            for i, (href, name) in enumerate(trends[:10], 1):
                name = html.unescape(name).strip()
                if name:
                    items.append({"rank": i, "title": name})
            if items:
                print(f"  X/Twitter Trending (HTML@{base}): {len(items)} 条")
                return items
        except Exception:
            pass

    # 策略3: 通过 Nitter 搜索 "trending" 获取高曝光 tweet
    for base in nitter_instances:
        try:
            url = f"{base}/search?f=tweets&q=trending&since=&until=&near="
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=8, context=SSL_CTX) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
            # 提取推文标题/内容摘要
            tweets = re.findall(r'<a href="/([^/]+)/status/\d+"[^>]*>([^<]{20,100}?)</a>', raw)
            if tweets:
                seen = set()
                for i, (_, text) in enumerate(tweets[:10]):
                    text = clean_text(text)
                    if text and text not in seen:
                        seen.add(text)
                        items.append({"rank": len(items)+1, "title": text})
                        if len(items) >= 10:
                            break
                if items:
                    print(f"  X/Twitter (Search@{base}): {len(items)} 条")
                    return items
        except Exception:
            pass

    print(f"  X/Twitter Trending: 所有实例均不可达（网络限制）")
    return []

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
def fetch_hackernews_top():
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

def fetch_hackernews_ask():
    """Hacker News Ask HN"""
    try:
        req = urllib.request.Request("https://hacker-news.firebaseio.com/v0/askstories.json", headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as resp:
            ids = json.loads(resp.read().decode())
        items = []
        for story_id in ids[:5]:
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
        print(f"  Hacker News Ask error: {e}")
        return []

def fetch_stackexchange(site="stackoverflow", label="StackOverflow", limit=5):
    """StackExchange 热问"""
    try:
        url = f"https://api.stackexchange.com/2.3/questions?order=desc&sort=activity&site={site}&pagesize={limit}"
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as resp:
            data = json.loads(resp.read().decode())
        items = data.get("items", [])[:limit]
        return [{
            "rank": i+1,
            "title": clean_text(item.get("title", "")),
            "answers": item.get("answer_count", 0),
            "score": item.get("score", 0),
            "tags": (item.get("tags", []) or [])[:3],
        } for i, item in enumerate(items)]
    except Exception as e:
        print(f"  {label} error: {e}")
        return []

def fetch_github_trending():
    """GitHub Trending 热门项目"""
    try:
        # 按更新时间排序，选取近期有活动的热门项目
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
            "language": item.get("language", "") or "",
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
            "url": item.get("url", "")[:80],
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
    hn_top = fetch_hackernews_top()
    hn_ask = fetch_hackernews_ask()
    gh = fetch_github_trending()
    lobsters = fetch_lobsters()

    # StackExchange 多站点
    so_stackoverflow = fetch_stackexchange("stackoverflow", "StackOverflow", 5)
    so_security = fetch_stackexchange("security", "Security", 3)
    so_ai = fetch_stackexchange("ai", "AI", 3)
    so_unix = fetch_stackexchange("unix", "Unix", 3)

    print(f"  Hacker News Top: {len(hn_top)} 条")
    print(f"  Hacker News Ask: {len(hn_ask)} 条")
    print(f"  GitHub Trending: {len(gh)} 条")
    print(f"  Lobsters: {len(lobsters)} 条")
    print(f"  StackOverflow: {len(so_stackoverflow)} 条")
    print(f"  Security: {len(so_security)} 条")
    print(f"  AI: {len(so_ai)} 条")
    print(f"  Unix: {len(so_unix)} 条")

    print("\n🐦 X/Twitter Trending...")
    x_trending = fetch_x_trending()
    print(f"  X/Twitter: {len(x_trending)} 条")

    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "domestic": {
            "weibo": {"source": "微博热搜", "items": weibo},
            "zhihu": {"source": "知乎热榜", "items": zhihu},
        },
        "international": {
            "hackernews_top": {"source": "Hacker News Top", "items": hn_top},
            "hackernews_ask": {"source": "Hacker News Ask HN", "items": hn_ask},
            "github": {"source": "GitHub Trending", "items": gh},
            "lobsters": {"source": "Lobsters", "items": lobsters},
            "stackoverflow": {"source": "StackOverflow", "items": so_stackoverflow},
            "security": {"source": "Security (StackExchange)", "items": so_security},
            "ai": {"source": "AI (StackExchange)", "items": so_ai},
            "unix": {"source": "Unix (StackExchange)", "items": so_unix},
        },
        "x_trending": {"source": "X/Twitter Trending", "items": x_trending},
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
    for item in hn_top[:3]:
        print(f"  {item['rank']}. {item['title'][:40]}")
    print("\n🔧 StackOverflow TOP3")
    for item in so_stackoverflow[:3]:
        print(f"  {item['rank']}. {item['title'][:40]}")
    print("\n🐦 X/Twitter TOP3")
    for item in x_trending[:3]:
        print(f"  {item['rank']}. {item['title'][:40]}")

    return result

if __name__ == "__main__":
    main()
