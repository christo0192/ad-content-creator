"""Agent 1 — Social Media Trends (Tab 1).

Free signals only: GitHub (stars/trending), Hacker News (Algolia points),
package version/release signals (PyPI/npm/GitHub Releases). Reddit via Apify is
optional (runs only if APIFY_TOKEN is set). No LLM required — sentiment is a
transparent magnitude heuristic (trending tech skews positive); upgrade to
claude -p sentiment later if desired.

Output rows validate against schemas.SocialTrendRow (the tool-call gate).
"""
from __future__ import annotations
import os, sys, re
from datetime import datetime, timezone
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "shared")))

import config as C
import schemas as S
import fetch as F
from pydantic import ValidationError

GH_HEADERS = {"Accept": "application/vnd.github+json"}
if os.getenv("GITHUB_TOKEN"):
    GH_HEADERS["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]

# Curated AI/ML repos to always track (name -> category).
GH_TRACK = {
    "langchain-ai/langchain": "framework", "run-llama/llama_index": "framework",
    "langgenius/dify": "framework", "ollama/ollama": "infra",
    "vllm-project/vllm": "infra", "huggingface/transformers": "framework",
    "langfuse/langfuse": "observability", "crewAIInc/crewAI": "agents",
    "microsoft/autogen": "agents", "modelcontextprotocol/servers": "agents",
    "pytorch/pytorch": "framework", "ggml-org/llama.cpp": "infra",
    "open-webui/open-webui": "tool", "comfyanonymous/ComfyUI": "tool",
}
# Package version signals (PyPI / npm).
PYPI_PKGS = ["langchain", "llama-index", "anthropic", "openai", "crewai",
             "transformers", "vllm", "mcp", "dspy-ai"]
NPM_PKGS = ["@langchain/core", "@anthropic-ai/sdk", "ai"]
HN_QUERIES = ["AI", "LLM", "agents", "RAG", "GPT", "Claude"]


def _sentiment(value: int, hi: int, mid: int) -> int:
    return 5 if value >= hi else 4 if value >= mid else 3


def _row(**kw):
    try:
        return S.SocialTrendRow(run_id=RUN_ID, run_date=C.REPORT_DATE, **kw)
    except ValidationError:
        return None


def github() -> list:
    rows = []
    # curated repos
    for repo, cat in GH_TRACK.items():
        try:
            d = F.http_json(f"https://api.github.com/repos/{repo}", headers=GH_HEADERS)
        except Exception:
            continue
        stars = d.get("stargazers_count", 0)
        r = _row(source="GitHub", topic=d.get("name", repo.split("/")[-1]),
                 sentiment=_sentiment(stars, 50000, 10000),
                 engagement=f"{stars:,} stars", engagement_value=stars,
                 category=cat, reference_url=d.get("html_url", f"https://github.com/{repo}"))
        if r: rows.append(r)
    # trending search (recently pushed, high-star AI repos)
    try:
        q = "topic:llm topic:ai pushed:>" + (C.WEEKLY_WINDOW_START.isoformat())
        d = F.http_json("https://api.github.com/search/repositories",
                        params={"q": q, "sort": "stars", "order": "desc", "per_page": 15},
                        headers=GH_HEADERS)
        for it in d.get("items", []):
            if it.get("full_name") in GH_TRACK:
                continue
            stars = it.get("stargazers_count", 0)
            r = _row(source="GitHub", topic=it.get("name", ""),
                     sentiment=_sentiment(stars, 50000, 10000),
                     engagement=f"{stars:,} stars", engagement_value=stars,
                     category="trending", reference_url=it.get("html_url", ""))
            if r: rows.append(r)
    except Exception:
        pass
    return rows


def hackernews() -> list:
    rows, seen = [], set()
    since = int(datetime(C.WEEKLY_WINDOW_START.year, C.WEEKLY_WINDOW_START.month,
                         C.WEEKLY_WINDOW_START.day, tzinfo=timezone.utc).timestamp())
    for q in HN_QUERIES:
        try:
            # date-sorted recent stories; filter recency + points client-side
            # (Algolia numericFilters comma-syntax 400s, so we filter here).
            d = F.http_json("https://hn.algolia.com/api/v1/search_by_date",
                            params={"query": q, "tags": "story", "hitsPerPage": 40})
        except Exception:
            continue
        for h in d.get("hits", []):
            oid = h.get("objectID")
            if oid in seen or not h.get("title"):
                continue
            if (h.get("created_at_i") or 0) < since or (h.get("points") or 0) < 50:
                continue
            seen.add(oid)
            pts = h.get("points", 0); ncom = h.get("num_comments", 0)
            url = h.get("url") or f"https://news.ycombinator.com/item?id={oid}"
            r = _row(source="Hacker News", topic=h["title"][:200],
                     sentiment=_sentiment(pts, 300, 100),
                     engagement=f"{pts} points, {ncom} comments", engagement_value=pts,
                     category="discussion", reference_url=url)
            if r: rows.append(r)
    return rows


def versions() -> list:
    rows = []
    for pkg in PYPI_PKGS:
        try:
            d = F.http_json(f"https://pypi.org/pypi/{pkg}/json")
            v = d["info"]["version"]
            r = _row(source="PyPI", topic=f"{pkg} {v}", sentiment=4,
                     engagement=f"v{v} (latest)", category="release",
                     reference_url=f"https://pypi.org/project/{pkg}/")
            if r: rows.append(r)
        except Exception:
            continue
    for pkg in NPM_PKGS:
        try:
            d = F.http_json(f"https://registry.npmjs.org/{pkg}")
            v = d.get("dist-tags", {}).get("latest", "")
            r = _row(source="npm", topic=f"{pkg} {v}", sentiment=4,
                     engagement=f"v{v} (latest)", category="release",
                     reference_url=f"https://www.npmjs.com/package/{pkg}")
            if r: rows.append(r)
        except Exception:
            continue
    return rows


def reddit() -> list:
    """Optional — only if APIFY_TOKEN present. Free acct #2."""
    if not os.getenv("APIFY_TOKEN"):
        return []
    try:
        import governor as G
        gov = G.BudgetGovernor()
        subs = ["developersIndia", "MachineLearning", "LocalLLaMA"]
        max_items = int(os.getenv("MR_REDDIT_MAX", "30"))   # probe small first, then scale
        url_input = {"searches": ["AI"], "subreddits": subs, "maxItems": max_items,
                     "sort": "top", "time": "week"}
        items, cost, meta = G.run_actor("trudax/reddit-scraper-lite", url_input, gov, "reddit")
        print(f"[reddit] run cost=${meta.get('cost_usd')} session=${round(gov.session_spent,4)} "
              f"items={meta.get('n_items')}")
        rows = []
        for it in items if isinstance(items, list) else []:
            title = it.get("title") or it.get("body", "")[:120]
            if not title:
                continue
            ups = it.get("upVotes") or it.get("score") or it.get("ups") or 0
            r = _row(source="Reddit", topic=title[:200], sentiment=_sentiment(int(ups or 0), 500, 100),
                     engagement=f"{ups} upvotes", engagement_value=int(ups or 0),
                     category="discussion", reference_url=it.get("url", ""))
            if r: rows.append(r)
        return rows
    except Exception as e:
        msg, tok = str(e), os.environ.get("APIFY_TOKEN")   # never print the token
        print(f"[reddit] skipped: {msg.replace(tok, '***') if tok else msg}")
        return []


RUN_ID = C.RUN_ID


def collect(run_id: str | None = None) -> list:
    global RUN_ID
    if run_id:
        RUN_ID = run_id
    rows = github() + hackernews() + versions() + reddit()
    # dedup by (source, topic)
    seen, out = set(), []
    for r in rows:
        k = (r.source, r.topic.lower())
        if k in seen:
            continue
        seen.add(k); out.append(r)
    return out


def main():
    rows = collect()
    print(f"[social] {len(rows)} validated rows")
    bysrc = {}
    for r in rows:
        bysrc[r.source] = bysrc.get(r.source, 0) + 1
    print("  by source:", bysrc)
    import bq as BQ
    res = BQ.write_snapshot("social", [r.to_bq() for r in rows], RUN_ID)
    print(f"[social][BQ] {res}")


if __name__ == "__main__":
    main()
