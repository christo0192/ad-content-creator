"""Free fetch helpers: JSON APIs, RSS, raw HTML, JS-page reading (Jina Reader),
and article-body extraction (trafilatura -> Jina fallback). Heavy libs are
imported lazily so the module loads even if they're absent.
"""
from __future__ import annotations
import requests
import config as C

_S = requests.Session()
_S.headers.update({"User-Agent": C.USER_AGENT})


def http_json(url: str, params: dict | None = None, headers: dict | None = None):
    r = _S.get(url, params=params, headers=headers, timeout=C.HTTP_TIMEOUT_S)
    r.raise_for_status()
    return r.json()


def get_text(url: str, headers: dict | None = None) -> str:
    r = _S.get(url, headers=headers, timeout=C.HTTP_TIMEOUT_S)
    r.raise_for_status()
    return r.text


def rss(url: str) -> list[dict]:
    """Parsed RSS/Atom entries as plain dicts. Fetches with our User-Agent first
    (some hosts, e.g. arXiv, block feedparser's default UA), then parses."""
    import feedparser
    try:
        content = _S.get(url, timeout=C.HTTP_TIMEOUT_S).content
        feed = feedparser.parse(content)
        if not feed.entries:
            feed = feedparser.parse(url)
    except Exception:
        feed = feedparser.parse(url)
    out = []
    for e in feed.entries:
        out.append({
            "title": e.get("title", ""),
            "link": e.get("link", ""),
            "summary": e.get("summary", "") or e.get("description", ""),
            "published": e.get("published", "") or e.get("updated", ""),
            "published_parsed": e.get("published_parsed") or e.get("updated_parsed"),
        })
    return out


def jina_reader(url: str) -> str:
    """Free JS-rendered page read via r.jina.ai -> clean markdown."""
    return get_text("https://r.jina.ai/" + url)


def article_text(url: str, min_chars: int = 300) -> str:
    """Best article body. trafilatura first; fall back to Jina Reader."""
    try:
        import trafilatura
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            txt = trafilatura.extract(downloaded, include_comments=False,
                                      include_tables=False) or ""
            if len(txt) >= min_chars:
                return txt
    except Exception:
        pass
    try:
        txt = jina_reader(url)
        return txt or ""
    except Exception:
        return ""
