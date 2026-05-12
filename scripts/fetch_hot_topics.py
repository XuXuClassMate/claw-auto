#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Daily Hot Topics Fetcher
Domestic: Weibo Hot Search / Zhihu Hot
International: Hacker News / GitHub Trending / StackExchange / Lobsters
Finance: Sina Finance RSS
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

def clean_text(text):
    try:
        text = re.sub(r'<[^>]+>', '', text)
        text = html.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:200]
    except:
        return str(text)[:200]

def fetch_sina_news():
    try:
        url = "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2516&num=15&page=1"
        req = urllib.request.Request(url, headers={**HEADERS, "Referer": "https://finance.sina.com.cn"})
        with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
        d = json.loads(raw)
        items = d.get("result", {}).get("data", [])
        result = []
        for item in items[:10]:
            result.append({
                "rank": len(result) + 1,
                "title": clean_text(item.get("title", "")),
                "ctime": item.get("ctime", ""),
                "intro": clean_text(item.get("intro", ""))[:80],
            })
        print(f"  Sina Finance RSS: {len(result)} items")
        return result
    except Exception as e:
        print(f"  Sina Finance RSS error: {e}")
        return []

def fetch_weibo_hot():
    try:
        url = "https://weibo.com/ajax/side/hotSearch"
        req = urllib.request.Request(url, headers={**HEADERS, "Referer": "https://weibo.com"})
        with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as resp:
            data = json.loads(resp.read().decode())
        if data and data.get("data", {}).get("realtime"):
            items = data["data"]["realtime"][:10]
            return [{"rank": i+1, "title": str(item.get("word", "")), "hot": item.get("raw_hot", "")} for i, item in enumerate(items)]
    except Exception as e:
        print(f"  Weibo error: {e}")
    return []

def fetch_zhihu_hot():
    try:
        url = "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=10"
        req = urllib.request.Request(url, headers={**HEADERS, "User-Agent": "ZhihuAndroid/1.0"})
        with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as resp:
            data = json.loads(resp.read().decode())
        if data and data.get("data"):
            items = data["data"][:10]
            return [{"rank": i+1, "title": clean_text(item.get("target", {}).get("title", ""))} for i, item in enumerate(items)]
    except Exception as e:
        print(f"  Zhihu error: {e}")
    return []

def fetch_hackernews_top():
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
                    items.append({"rank": len(items)+1, "title": clean_text(item["title"]), "score": item.get("score", 0)})
                    time.sleep(0.05)
            except:
                continue
        return items
    except Exception as e:
        print(f"  HN Top error: {e}")
        return []

def fetch_hackernews_ask():
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
                    items.append({"rank": len(items)+1, "title": clean_text(item["title"])})
                    time.sleep(0.05)
            except:
                continue
        return items
    except Exception as e:
        print(f"  HN Ask error: {e}")
        return []

def fetch_stackexchange(site="stackoverflow", label="StackOverflow", limit=5):
    try:
        url = f"https://api.stackexchange.com/2.3/questions?order=desc&sort=activity&site={site}&pagesize={limit}"
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as resp:
            data = json.loads(resp.read().decode())
        items = data.get("items", [])[:limit]
        return [{"rank": i+1, "title": clean_text(item.get("title", "")), "answers": item.get("answer_count", 0), "tags": (item.get("tags", []) or [])[:3]} for i, item in enumerate(items)]
    except Exception as e:
        print(f"  {label} error: {e}")
        return []

def fetch_github_trending():
    try:
        url = "https://api.github.com/search/repositories?q=created:>2026-05-09&sort=stars&order=desc&per_page=10"
        req = urllib.request.Request(url, headers={**HEADERS, "Accept": "application/vnd.github.v3+json"})
        with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as resp:
            data = json.loads(resp.read().decode())
        items = data.get("items", [])[:10]
        return [{"rank": i+1, "title": clean_text(item.get("full_name", "")), "stars": item.get("stargazers_count", 0), "language": item.get("language", "") or ""} for i, item in enumerate(items)]
    except Exception as e:
        print(f"  GitHub Trending error: {e}")
        return []

def fetch_lobsters():
    try:
        req = urllib.request.Request("https://lobste.rs/hottest.json", headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as resp:
            data = json.loads(resp.read().decode())
        return [{"rank": i+1, "title": clean_text(item.get("title", ""))} for i, item in enumerate(data[:10])]
    except Exception as e:
        print(f"  Lobsters error: {e}")
        return []

def main():
    print("=== Hot Topics Fetcher ===")

    print("\n[CN] Weibo + Zhihu...")
    weibo = fetch_weibo_hot()
    zhihu = fetch_zhihu_hot()
    print(f"  Weibo: {len(weibo)}, Zhihu: {len(zhihu)}")

    print("\n[Intl] HN + GH + Lobsters + SE...")
    hn_top = fetch_hackernews_top()
    hn_ask = fetch_hackernews_ask()
    gh = fetch_github_trending()
    lobsters = fetch_lobsters()
    so_so = fetch_stackexchange("stackoverflow", "StackOverflow", 5)
    so_sec = fetch_stackexchange("security", "Security", 3)
    so_ai = fetch_stackexchange("ai", "AI", 3)
    so_unix = fetch_stackexchange("unix", "Unix", 3)
    print(f"  HN Top: {len(hn_top)}, HN Ask: {len(hn_ask)}, GH: {len(gh)}, Lobsters: {len(lobsters)}")

    print("\n[Finance Social] Sina Finance RSS...")
    sina_news = fetch_sina_news()

    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "domestic": {
            "weibo": {"source": "Weibo Hot Search", "items": weibo},
            "zhihu": {"source": "Zhihu Hot", "items": zhihu},
        },
        "international": {
            "hackernews_top": {"source": "Hacker News Top", "items": hn_top},
            "hackernews_ask": {"source": "Hacker News Ask HN", "items": hn_ask},
            "github": {"source": "GitHub Trending", "items": gh},
            "lobsters": {"source": "Lobsters", "items": lobsters},
            "stackoverflow": {"source": "StackOverflow", "items": so_so},
            "security": {"source": "Security (StackExchange)", "items": so_sec},
            "ai": {"source": "AI (StackExchange)", "items": so_ai},
            "unix": {"source": "Unix (StackExchange)", "items": so_unix},
        },
        "sina_news": {"source": "Sina Finance RSS", "items": sina_news},
    }

    import os
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "hot_topics.json")
    out_path = os.path.normpath(out_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to {out_path}")
    return result

if __name__ == "__main__":
    main()
