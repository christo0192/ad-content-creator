"""Agent 2 — Blog & Publications (Tab 2).

Sources = the reference-workbook publication set:
  RSS (clean feeds):  Towards Data Science, DataAspirant, Entrepreneur India, arXiv
  Scrape (no RSS):    Analytics India Magazine, AIM Research, Tredence, KodeKloud,
                      TechGig, LiquidMetal AI  -> Jina Reader listing -> article links

Each article -> Haiku extraction via `claude -p` -> {recommended_skill, audience,
urgency, curriculum_match}. Rows validate against schemas.BlogRow.
"""
from __future__ import annotations
import os, sys, re, json, time
from datetime import date
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "shared")))
import urllib.parse as up

import config as C
import schemas as S
import fetch as F
import llm as L
from pydantic import ValidationError

MAX_ARTICLES = int(os.getenv("MR_BLOG_MAX", "30"))
PER_SOURCE = int(os.getenv("MR_BLOG_PER_SOURCE", "4"))

ARXIV = ("http://export.arxiv.org/api/query?search_query="
         "cat:cs.LG+OR+cat:cs.AI+OR+cat:cs.CL&sortBy=submittedDate&"
         "sortOrder=descending&max_results=10")
RSS_FEEDS = {
    "Towards Data Science": "https://towardsdatascience.com/feed/",
    "DataAspirant": "https://dataaspirant.com/feed/",
    "Entrepreneur India": "https://www.entrepreneur.com/latest.rss",
    "arXiv (cs.AI/LG/CL)": ARXIV,
}
# Sites with no usable RSS -> Jina Reader listing scrape.
# {publication: (listing_url, must_contain_or_None)}
SCRAPE_SITES = {
    "Analytics India Magazine": ("https://analyticsindiamag.com/", None),
    "AIM Research": ("https://aimresearch.co/", None),
    "Tredence": ("https://www.tredence.com/blog", "/blog/"),
    "KodeKloud": ("https://kodekloud.com/blog", "/blog/"),
    "TechGig": ("https://www.techgig.com/tech-news", "/tech-news/"),
    "LiquidMetal AI": ("https://liquidmetal.ai/blog", None),
}

_LINK = re.compile(r"(?<!!)\[([^\]]{15,140})\]\((https?://[^)\s]+)\)")
_IMG_EXT = (".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif", ".ico")
_NAV = ("/category/", "/tag/", "/author/", "/page/", "login", "/about", "/contact",
        "privacy", "subscribe", "/industries/", "/services/", "/solutions/",
        "/platform", "/company", "/careers", "/pricing", "/reports", "/research-calendar",
        "/terms", "/cookie", "/sitemap", "/feed", "twitter.com", "linkedin.com",
        "facebook.com", "youtube.com", "/assets/", "/wp-content/")


def _curriculum_context() -> str:
    try:
        return json.dumps(json.load(open(C.IK_CURRICULUM_JSON, encoding="utf-8")))[:1800]
    except Exception:
        return ("IK India teaches AI/ML upskilling: Agentic AI, GenAI, RAG, LLMs, "
                "MLOps, ML fundamentals, interview prep; primarily AWS cloud.")


CURRICULUM = _curriculum_context()

BATCH_SIZE = int(os.getenv("MR_BLOG_BATCH", "5"))

# Batched: classify MANY articles in ONE claude -p call (returns a JSON array).
# This is the key latency/yield fix — N articles cost 1 call, not N.
BATCH_PROMPT = """You classify AI/ML articles for Interview Kickstart (IK) India, an upskilling EdTech.
IK curriculum coverage (JSON): {curriculum}

For EACH article below, decide the single most relevant skill/tool IK should teach and whether IK
already covers it. Return ONLY a JSON array with one object per article, preserving the index "i".
No prose, no markdown:
[{{"i": <index>,
   "recommended_skill": "<single most relevant skill/tool>",
   "audience": "<one of: Fresher, Working Professional, Manager/Leader, Career Switcher>",
   "urgency": "<one of: Must-have NOW, High priority, Future trend>",
   "curriculum_match": "<one of: Yes, Partial, No - GAP, N/A>"}}, ...]

ARTICLES:
{articles}"""


def _batch_classify(cands: list[dict]) -> list:
    """Return a list aligned to cands, each an extraction dict or None.
    Articles are grouped into batches of BATCH_SIZE -> one claude -p call each."""
    results = [None] * len(cands)
    groups, prompts = [], []
    for start in range(0, len(cands), BATCH_SIZE):
        group = cands[start:start + BATCH_SIZE]
        lines = "\n".join(
            f'[{i}] Publication: {c["publication"]} | Title: {c["title"]} | '
            f'Summary: {(c["summary"] or "")[:180]}'
            for i, c in enumerate(group))
        groups.append((start, group))
        prompts.append(BATCH_PROMPT.format(curriculum=CURRICULUM, articles=lines))
    outs = L.map_extract(prompts, model=C.EXTRACT_MODEL, timeout=300)
    for (start, group), out in zip(groups, outs):
        if isinstance(out, dict):
            out = out.get("articles") or out.get("results") or [out]
        if not isinstance(out, list):
            continue
        for obj in out:
            if not isinstance(obj, dict):
                continue
            i = obj.get("i")
            if isinstance(i, int) and 0 <= i < len(group):
                results[start + i] = obj
    return results


def _within(pp) -> bool:
    if not pp:
        return True
    try:
        return date(pp.tm_year, pp.tm_mon, pp.tm_mday) >= C.WEEKLY_WINDOW_START
    except Exception:
        return True


def _pub_date(pp):
    try:
        return date(pp.tm_year, pp.tm_mon, pp.tm_mday)
    except Exception:
        return None


def _is_article(title: str, link: str, domain: str, must: str | None) -> bool:
    l = link.lower().split("#")[0]
    if domain not in l or l.rstrip("/").endswith(domain):
        return False
    if title.strip().lower().startswith("image") or l.endswith(_IMG_EXT):
        return False
    if any(x in l for x in _NAV):
        return False
    if must:
        # a specific article path is given -> trust it, as long as there's a
        # slug/id after it (handles non-slug URLs like TechGig's .../articleshow/123.cms)
        i = l.find(must)
        return i >= 0 and bool(l[i + len(must):].strip("/"))
    slug = l.rstrip("/").rsplit("/", 1)[-1]
    return "-" in slug and len(slug) > 10        # article slugs are hyphenated


def gather_rss() -> list[dict]:
    cands, seen = [], set()
    for pub, url in RSS_FEEDS.items():
        try:
            entries = F.rss(url)
        except Exception as e:
            print(f"[blog] rss fail {pub}: {e}")
            continue
        # prefer in-window; if the source didn't publish this week, fall back to
        # its most-recent entries so every source is still represented.
        fresh = [e for e in entries if e["title"] and _within(e.get("published_parsed"))]
        pool = fresh if fresh else [e for e in entries if e["title"]]
        kept = 0
        for e in pool:
            if e["link"] in seen:
                continue
            seen.add(e["link"])
            cands.append({"publication": pub, "title": e["title"][:300],
                          "summary": (e["summary"] or "")[:1000], "link": e["link"],
                          "pub_date": _pub_date(e.get("published_parsed"))})
            kept += 1
            if kept >= PER_SOURCE:
                break
        print(f"[blog] rss {pub}: {kept}{'' if fresh else ' (most-recent fallback)'}")
    return cands


def gather_scrape() -> list[dict]:
    cands = []
    for pub, (listing, must) in SCRAPE_SITES.items():
        try:
            md = F.jina_reader(listing)
        except Exception as e:
            print(f"[blog] scrape fail {pub}: {e}")
            continue
        domain = up.urlparse(listing).netloc.replace("www.", "")
        seen, kept = set(), 0
        for title, link in _LINK.findall(md):
            link = link.split("#")[0]
            if link in seen or not _is_article(title, link, domain, must):
                continue
            seen.add(link)
            cands.append({"publication": pub, "title": title.strip()[:300],
                          "summary": "", "link": link, "pub_date": None})
            kept += 1
            if kept >= PER_SOURCE:
                break
        print(f"[blog] scrape {pub}: {kept}")
    return cands


def gather() -> list[dict]:
    cands, seen = [], set()
    for c in gather_rss() + gather_scrape():
        if c["link"] in seen:
            continue
        seen.add(c["link"]); cands.append(c)
    return cands[:MAX_ARTICLES]


def collect(run_id: str | None = None) -> list:
    rid = run_id or C.RUN_ID
    cands = gather()
    nbatch = (len(cands) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"[blog] {len(cands)} candidates -> {nbatch} batched claude -p calls ({C.EXTRACT_MODEL})")
    t0 = time.time()
    extracted = _batch_classify(cands)
    print(f"[blog] extraction done in {time.time()-t0:.0f}s")
    rows = []
    for c, ex in zip(cands, extracted):
        if not isinstance(ex, dict):
            continue
        try:
            rows.append(S.BlogRow(
                run_id=rid, run_date=C.REPORT_DATE, source=c["publication"],
                publication=c["publication"], title=c["title"],
                recommended_skill=str(ex.get("recommended_skill", ""))[:200],
                audience=str(ex.get("audience", ""))[:80],
                urgency=ex.get("urgency"), curriculum_match=ex.get("curriculum_match"),
                published_date=c["pub_date"], summary=(c["summary"] or "")[:500] or None,
                reference_url=c["link"]))
        except ValidationError:
            continue
    return rows


def main():
    rows = collect()
    bypub = {}
    for r in rows:
        bypub[r.publication] = bypub.get(r.publication, 0) + 1
    print(f"[blog] {len(rows)} validated rows | by publication: {bypub}")
    import bq as BQ
    res = BQ.write_snapshot("blog", [r.to_bq() for r in rows], C.RUN_ID)
    print(f"[blog][BQ] {res}")


if __name__ == "__main__":
    main()
