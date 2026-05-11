#!/usr/bin/env python3
"""
角色蒸馏器 — 调研模块 v2.1
职责：搜索+抓取+视频字幕+保存结构化材料。不生成角色卡。

用法:
  python3 distill.py "角色名" "作品名"
  python3 distill.py "角色名" "作品名" --lang en
  python3 distill.py "角色名" "作品名" --type game

输出:
  ~/.hermes/characters/_research/<角色名>/
    ├── wiki.md       # 基础档案
    ├── quotes.md     # 台词与行为
    ├── analysis.md   # 社区解读
    └── meta.json     # 调研元数据
"""
import sys
import os
import json
import subprocess
import argparse
import shutil
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, "/root/.hermes/scripts")
from tavily_client import tavily_search, tavily_extract

SMART_CRAWL = "/root/.hermes/scripts/smart_crawl.py"
RESEARCH_DIR = Path(os.path.expanduser("~/.hermes/characters/_research"))

BLACKLIST = ["baike.baidu.com", "mp.weixin.qq.com"]
YTDLP = shutil.which("yt-dlp") or os.path.expanduser("~/.local/bin/yt-dlp")
HAS_YTDLP = os.path.isfile(YTDLP) and os.access(YTDLP, os.X_OK)


# ═══════════════════════════════════════════════════════════
# 搜索词模板（按角色类型）
# ═══════════════════════════════════════════════════════════

def _queries_wiki(char, work, lang, media_type):
    """Agent A 搜索词"""
    if lang == "zh":
        base = [
            f"{char} {work} 人物介绍 角色设定",
            f"{char} 萌娘百科",
            f"{char} {work} fandom wiki",
        ]
        if media_type == "game":
            base += [f"{char} {work} site:bangumi.tv", f"{char} {work} 游戏设定集"]
        elif media_type == "anime":
            base += [f"{char} {work} site:bangumi.tv", f"{char} {work} 动画 角色"]
        elif media_type == "novel":
            base += [f'"{char}" "{work}" 人物设定 site:tieba.baidu.com']
        elif media_type == "film":
            base += [f"{char} {work} 角色分析 影评"]
    else:
        base = [
            f"{char} {work} wiki character profile",
            f"{char} {work} fandom",
            f"{char} character biography {work}",
        ]
        if media_type == "game":
            base += [f"{char} {work} site:gamefaqs.gamespot.com"]
        elif media_type == "anime":
            base += [f"{char} {work} myanimelist character"]
    return base


def _queries_quotes(char, work, lang, media_type):
    """Agent B 搜索词"""
    if lang == "zh":
        base = [
            f"{char} 经典台词 语录 {work}",
            f"{char} 名场面 行为 {work}",
            f"{char} {work} 对话 场景",
        ]
        if media_type == "game":
            base += [f"{char} {work} 全语音 台词", f"{char} {work} voice lines"]
        elif media_type == "anime":
            base += [f"{char} {work} 名台词 名场面合集"]
        elif media_type == "novel":
            base += [f'"{char}" "{work}" "说道" OR "道"', f"{char} {work} 经典片段"]
    else:
        base = [
            f"{char} quotes {work}",
            f"{char} {work} memorable dialogue",
            f"{char} {work} best scenes",
        ]
        if media_type == "game":
            base += [f"{char} {work} all voice lines", f"{work} script site:gamefaqs.gamespot.com"]
        elif media_type == "anime":
            base += [f"{char} {work} iconic lines"]
    return base


def _queries_analysis(char, work, lang, media_type):
    """Agent C 搜索词"""
    if lang == "zh":
        base = [
            f"{char} 人物分析 角色解析 {work}",
            f"{char} 争议 为什么喜欢 {work}",
            f"{char} {work} 性格 深度解读",
        ]
        if media_type in ("game", "anime"):
            base += [f"{char} {work} site:nga.178.com OR site:tieba.baidu.com"]
        elif media_type == "novel":
            base += [f"{char} {work} 豆瓣 书评 人物"]
        elif media_type == "film":
            base += [f"{char} {work} 影评 角色"]
    else:
        base = [
            f"{char} character analysis {work}",
            f"{char} {work} reddit discussion analysis",
            f"{char} {work} controversial OR underrated",
        ]
    return base


# ═══════════════════════════════════════════════════════════
# 搜索与抓取（三级降级）
# ═══════════════════════════════════════════════════════════

def _is_blacklisted(url):
    return any(b in url for b in BLACKLIST)


def _tavily_search(query, max_results=5):
    try:
        result = tavily_search(query, max_results=max_results)
        return result.get("results", [])
    except Exception:
        return None


def _playwright_search(query):
    try:
        r = subprocess.run(
            ["python3", SMART_CRAWL, "search", query],
            capture_output=True, text=True, timeout=45
        )
        if r.returncode == 0 and r.stdout.strip():
            return json.loads(r.stdout).get("results", [])
    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception):
        pass
    return None


def search_with_fallback(query, max_results=5):
    results = _tavily_search(query, max_results)
    if results is not None:
        return results
    results = _playwright_search(query)
    if results is not None:
        return results
    return []


def fetch_url(url):
    """抓取 URL：Tavily → smart_crawl → force-playwright"""
    # Tavily extract
    try:
        result = tavily_extract([url])
        results = result.get("results", [])
        if results and len(results[0].get("raw_content", "")) > 100:
            return results[0]["raw_content"]
    except Exception:
        pass
    # smart_crawl（内置 fallback）
    try:
        r = subprocess.run(
            ["python3", SMART_CRAWL, url], capture_output=True, text=True, timeout=60
        )
        if r.returncode == 0 and len(r.stdout.strip()) > 100:
            return r.stdout.strip()
    except Exception:
        pass
    # 强制 Playwright
    try:
        r = subprocess.run(
            ["python3", SMART_CRAWL, url, "--force-playwright"],
            capture_output=True, text=True, timeout=60
        )
        if r.returncode == 0 and len(r.stdout.strip()) > 100:
            return r.stdout.strip()
    except Exception:
        pass
    return ""


# ═══════════════════════════════════════════════════════════
# Fandom 子页面主动爬取
# ═══════════════════════════════════════════════════════════

def _try_fandom_subpages(search_results):
    """从搜索结果中找到 fandom URL，主动爬取 /Quotes 子页面（限时）"""
    extra_texts = []
    for r in search_results:
        url = r.get("url", "")
        if "fandom.com" not in url:
            continue
        base_url = url.rstrip("/")
        # 只爬 /Quotes（最有价值），限制总耗时
        for suffix in ["/Quotes"]:
            sub_url = base_url + suffix
            content = fetch_url(sub_url)
            if content and len(content) > 200:
                extra_texts.append({"url": sub_url, "text": content[:5000], "full": True})
        break
    return extra_texts


# ═══════════════════════════════════════════════════════════
# yt-dlp 视频字幕提取
# ═══════════════════════════════════════════════════════════

def _ytdlp_search_and_extract(char, work, lang):
    """搜索 YouTube/B站视频并提取字幕"""
    if not HAS_YTDLP:
        return []

    # 搜索视频 URL
    if lang == "zh":
        video_query = f"{char} {work} 台词合集 OR 全语音 OR voice lines"
    else:
        video_query = f"{char} {work} all voice lines OR all dialogue"

    results = search_with_fallback(video_query, max_results=3)
    video_urls = [
        r["url"] for r in results
        if any(v in r.get("url", "") for v in ["youtube.com", "youtu.be", "bilibili.com"])
    ]

    if not video_urls:
        return []

    texts = []
    for url in video_urls[:2]:  # 最多处理2个视频
        try:
            r = subprocess.run(
                [YTDLP, "--write-sub", "--write-auto-sub", "--skip-download",
                 "--sub-lang", "zh-Hans,zh,en", "--sub-format", "srt/vtt/best",
                 "-o", "/tmp/ytdlp_sub_%(id)s", url],
                capture_output=True, text=True, timeout=30
            )
            # 读取生成的字幕文件
            import glob
            sub_files = glob.glob("/tmp/ytdlp_sub_*")
            for sf in sub_files:
                content = Path(sf).read_text(encoding="utf-8", errors="ignore")
                if len(content) > 100:
                    texts.append({"url": url, "text": content[:4000], "full": True})
                os.remove(sf)
        except (subprocess.TimeoutExpired, Exception):
            continue

    return texts


# ═══════════════════════════════════════════════════════════
# Agent 主逻辑
# ═══════════════════════════════════════════════════════════

def collect_texts(search_results, max_fetch=3):
    """从搜索结果收集文本，对高价值 URL 抓取全文"""
    texts = []
    fetched = 0
    seen = set()

    for r in search_results:
        url = r.get("url", "")
        if url in seen or _is_blacklisted(url):
            continue
        seen.add(url)

        content = r.get("content", "")
        if content:
            texts.append({"url": url, "text": content, "full": False})

        if fetched < max_fetch and any(k in url for k in ["wiki", "fandom", "moegirl", "bangumi"]):
            full = fetch_url(url)
            if full and len(full) > len(content) * 2:
                texts.append({"url": url, "text": full[:6000], "full": True})
                fetched += 1

    return texts


def agent_a(char, work, lang, media_type):
    """Agent A: 基础档案"""
    queries = _queries_wiki(char, work, lang, media_type)
    all_results = []
    for q in queries:
        all_results.extend(search_with_fallback(q, max_results=4))

    texts = collect_texts(all_results, max_fetch=3)
    return texts


def agent_b(char, work, lang, media_type):
    """Agent B: 台词与行为"""
    queries = _queries_quotes(char, work, lang, media_type)
    all_results = []
    for q in queries:
        all_results.extend(search_with_fallback(q, max_results=4))

    texts = collect_texts(all_results, max_fetch=2)

    # 主动爬取 fandom /Quotes 子页面
    fandom_quotes = _try_fandom_subpages(all_results)
    texts.extend(fandom_quotes)

    # yt-dlp 视频字幕
    if HAS_YTDLP and media_type in ("game", "anime"):
        video_texts = _ytdlp_search_and_extract(char, work, lang)
        texts.extend(video_texts)

    return texts


def agent_c(char, work, lang, media_type):
    """Agent C: 社区解读"""
    queries = _queries_analysis(char, work, lang, media_type)
    all_results = []
    for q in queries:
        all_results.extend(search_with_fallback(q, max_results=4))

    texts = collect_texts(all_results, max_fetch=2)
    return texts


# ═══════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════

def format_texts(texts):
    parts = []
    for t in texts:
        tag = "[全文]" if t["full"] else "[摘要]"
        parts.append(f"### {tag} {t['url']}\n\n{t['text']}")
    return "\n\n---\n\n".join(parts) if parts else "(无有效信息)"


def run_research(char_name, work_name, lang="zh", media_type="auto"):
    print(f"\n正在调研 {char_name}（{work_name}）...")
    if HAS_YTDLP:
        print(f"  yt-dlp: ✓ 可用")
    else:
        print(f"  yt-dlp: ✗ 未安装（游戏/动漫角色建议安装以获取视频台词）")
    print()

    results = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            pool.submit(agent_a, char_name, work_name, lang, media_type): "wiki",
            pool.submit(agent_b, char_name, work_name, lang, media_type): "quotes",
            pool.submit(agent_c, char_name, work_name, lang, media_type): "analysis",
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                results[key] = future.result()
            except Exception as e:
                print(f"  ✗ {key} 异常: {e}", file=sys.stderr)
                results[key] = []

    wiki_texts = results.get("wiki", [])
    quotes_texts = results.get("quotes", [])
    analysis_texts = results.get("analysis", [])

    counts = {
        "wiki": len(wiki_texts),
        "quotes": len(quotes_texts),
        "analysis": len(analysis_texts),
    }
    total = sum(counts.values())

    def q(n):
        return "✓" if n >= 5 else "△" if n >= 2 else "✗"

    print(f"  ✓ 档案 — {counts['wiki']} 条")
    print(f"  ✓ 台词 — {counts['quotes']} 条")
    print(f"  ✓ 解读 — {counts['analysis']} 条")
    print(f"\n─── 调研完成 ────────────────────────────")
    print(f"角色档案  {q(counts['wiki'])}  {counts['wiki']} 条信息")
    print(f"台词/行为  {q(counts['quotes'])}  {counts['quotes']} 条记录")
    print(f"社区解读  {q(counts['analysis'])}  {counts['analysis']} 篇分析")
    print(f"────────────────────────────────────────")
    print(f"总计：{total} 条有效信息")

    if total < 3:
        print("\n⚠ 公开资料极少。建议告诉 Agent「我来提供材料」手工补充。")
    elif total < 8:
        print("\n△ 材料有限，角色卡可生成但深度可能不足。可手工补充提升质量。")

    return {
        "wiki": format_texts(wiki_texts),
        "quotes": format_texts(quotes_texts),
        "analysis": format_texts(analysis_texts),
        "counts": counts,
        "total": total,
    }


def save_research(char_name, work_name, data, media_type):
    out_dir = RESEARCH_DIR / char_name
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "wiki.md").write_text(
        f"# {char_name} — 基础档案\n\n{data['wiki']}", encoding="utf-8"
    )
    (out_dir / "quotes.md").write_text(
        f"# {char_name} — 台词与行为\n\n{data['quotes']}", encoding="utf-8"
    )
    (out_dir / "analysis.md").write_text(
        f"# {char_name} — 社区解读\n\n{data['analysis']}", encoding="utf-8"
    )
    (out_dir / "meta.json").write_text(json.dumps({
        "char_name": char_name,
        "work_name": work_name,
        "media_type": media_type,
        "researched_at": datetime.now().isoformat(),
        "has_ytdlp": HAS_YTDLP,
        "counts": data["counts"],
        "total": data["total"],
        "quality": "sufficient" if data["total"] >= 8 else "limited" if data["total"] >= 3 else "insufficient",
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n✓ 材料已保存到: {out_dir}/")
    return out_dir


def main():
    parser = argparse.ArgumentParser(description="角色蒸馏器 — 调研模块 v2.1")
    parser.add_argument("char_name", help="角色名")
    parser.add_argument("work_name", nargs="?", default="", help="作品名")
    parser.add_argument("--lang", default="zh", choices=["zh", "en"], help="搜索语言")
    parser.add_argument("--type", default="auto", dest="media_type",
                        choices=["auto", "game", "anime", "novel", "film"],
                        help="角色类型（影响搜索策略）")
    args = parser.parse_args()

    data = run_research(args.char_name, args.work_name, args.lang, args.media_type)
    save_research(args.char_name, args.work_name, data, args.media_type)


if __name__ == "__main__":
    main()
