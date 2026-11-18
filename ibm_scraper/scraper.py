"""IBM headline collection, article fetching, and editorial ranking."""

from __future__ import annotations

import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

from ibm_scraper.config import (
    IBM_NEWSROOM_LISTINGS,
    IBM_RESEARCH_RSS_URL,
    IBM_RSS_URL,
    KEYWORDS,
    LOOKBACK_DAYS,
    MAX_ARTICLE_CHARS,
    MAX_QUANTUM_IN_TOP_STORIES,
    NON_NEWS_TITLE_PATTERNS,
    RANKING_SIGNALS,
    STOP_PHRASES,
)
from ibm_scraper.models import Headline

# ── optional deps ──────────────────────────────────────────────────────────
try:
    import feedparser  # type: ignore
except ImportError:
    feedparser = None

try:
    from bs4 import BeautifulSoup  # type: ignore
except ImportError:
    BeautifulSoup = None

_USER_AGENT = "Mozilla/5.0 (compatible; ibm-headline-linker/1.0)"
_KEYWORD_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(k) for k in sorted(KEYWORDS, key=len, reverse=True)) + r")s?\b",
    re.IGNORECASE,
)
_NON_NEWS_RES = [re.compile(p, re.IGNORECASE) for p in NON_NEWS_TITLE_PATTERNS]
_SIGNAL_RES = [(re.compile(p, re.IGNORECASE), weight) for p, weight in RANKING_SIGNALS]
_STAT_RE = re.compile(r"\d+(?:\.\d+)?\s?(?:%|x\b|percent|million|billion|trillion)|\$\d", re.I)
_ACQUISITION_RE = re.compile(r"\b(?:acquires?|acquired|acquisition of)\b", re.IGNORECASE)
_TITLE_STOPWORDS = {
    "a", "an", "and", "at", "by", "for", "from", "ibm", "in", "new", "of", "on", "the",
    "to", "with",
}


def _is_ibm_url(url: str) -> bool:
    """True if *url* is hosted on ibm.com (or a subdomain)."""
    host = (urlparse(url).hostname or "").lower()
    return host == "ibm.com" or host.endswith(".ibm.com")


def _clean_url(url: str) -> str:
    """Remove tracking parameters from *url*."""
    parts = urlparse(url)
    query = [(k, v) for k, v in parse_qsl(parts.query) if not k.startswith("utm_")]
    return urlunparse(parts._replace(query=urlencode(query), fragment=""))


def _get_html(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def _cutoff() -> datetime:
    return datetime.now() - timedelta(days=LOOKBACK_DAYS)


def _fetch_rss(url: str, source: str) -> List[Headline]:
    """Return dated entries from an RSS feed inside the lookback window."""
    if feedparser is None:
        raise RuntimeError("feedparser not installed — run: pip install feedparser")

    cutoff = _cutoff()
    items: List[Headline] = []
    for entry in feedparser.parse(url).entries:
        parsed = entry.get("published_parsed")
        if not parsed:
            continue
        published = datetime(*parsed[:6])
        if published >= cutoff:
            items.append(
                Headline(
                    title=entry.title.strip(),
                    url=_clean_url(entry.link),
                    published=published,
                    source=source,
                )
            )
    return items


def _parse_listing_date(text: str) -> Optional[datetime]:
    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(text.strip(), fmt)
        except ValueError:
            pass
    return None


def _fetch_newsroom_listing(url: str) -> List[Headline]:
    """Return dated stories from an IBM Newsroom listing page."""
    if BeautifulSoup is None:
        raise RuntimeError("beautifulsoup4 not installed — run: pip install beautifulsoup4")

    cutoff = _cutoff()
    soup = BeautifulSoup(_get_html(url), "html.parser")
    items: List[Headline] = []
    for item in soup.select(".wd_item"):
        date_node = item.select_one(".wd_date")
        links = item.select(".wd_title a[href]")
        published = _parse_listing_date(date_node.get_text()) if date_node else None
        if not links or not published or published < cutoff:
            continue
        # Campaign items may link to a wrapper first and the article second.
        link = next((a for a in links if "item=" not in a["href"]), links[0])
        items.append(
            Headline(
                title=link.get_text(" ", strip=True),
                url=_clean_url(urljoin(url, link["href"])),
                published=published,
                source="IBM Newsroom",
            )
        )
    return items


def _fetch_article_text(url: str) -> str:
    """Return readable article text, or an empty string if unavailable."""
    if BeautifulSoup is None:
        return ""
    try:
        soup = BeautifulSoup(_get_html(url), "html.parser")
    except Exception as exc:
        print(f"[warn] could not read {url}: {exc}", file=sys.stderr)
        return ""

    for tag in soup(["script", "style", "noscript", "nav", "footer", "aside", "form"]):
        tag.decompose()
    node = (
        soup.select_one(".wd_news_body")
        or soup.select_one(".wd_body")
        or soup.select_one("main")
        or soup.body
    )
    if node is None:
        return ""
    return " ".join(node.get_text(" ", strip=True).split())[:MAX_ARTICLE_CHARS]


def _source_priority(headline: Headline) -> int:
    """Prefer formal press releases, then newsroom posts, then blogs."""
    path = urlparse(headline.url).path
    if re.match(r"/\d{4}-\d{2}-\d{2}-", path):
        return 0
    return 1 if headline.source == "IBM Newsroom" else 2


def _title_tokens(title: str) -> Set[str]:
    return set(re.findall(r"[a-z0-9]+", title.lower())) - _TITLE_STOPWORDS


def _same_story(first: Set[str], second: Set[str]) -> bool:
    shared = first & second
    smaller = min(len(first), len(second))
    return len(shared) >= 4 and len(shared) / max(smaller, 1) >= 0.7


def _deduplicate(items: List[Headline]) -> List[Headline]:
    unique: List[Headline] = []
    tokens: List[Set[str]] = []
    seen_urls: Set[str] = set()
    for headline in sorted(items, key=lambda h: (_source_priority(h), -h.published.timestamp())):
        current = _title_tokens(headline.title)
        if headline.url in seen_urls or any(_same_story(current, other) for other in tokens):
            continue
        seen_urls.add(headline.url)
        tokens.append(current)
        unique.append(headline)
    return unique


def _is_candidate(headline: Headline) -> bool:
    title = headline.title.strip()
    lowered = title.lower()
    if any(phrase in lowered for phrase in STOP_PHRASES):
        return False
    if any(pattern.search(title) for pattern in _NON_NEWS_RES):
        return False
    return bool(_KEYWORD_RE.search(title))


def _score(headline: Headline, now: datetime) -> float:
    score = sum(weight for pattern, weight in _SIGNAL_RES if pattern.search(headline.title))
    score += min(len(_STAT_RE.findall(headline.body[:3000])), 6) * 0.5
    if _ACQUISITION_RE.search(headline.body[:1200]) and not _ACQUISITION_RE.search(headline.title):
        score += 3.0
    if _source_priority(headline) == 0:
        score += 1.0
    age_days = max((now - headline.published).total_seconds() / 86400, 0)
    score += max(0.0, 1.0 - age_days / LOOKBACK_DAYS)
    if not headline.body:
        score -= 5.0
    return score


def _limit_quantum(headlines: List[Headline]) -> List[Headline]:
    """Move low-value and extra quantum stories below the strongest stories."""
    kept: List[Headline] = []
    overflow: List[Headline] = []
    quantum_count = 0
    for headline in headlines:
        is_quantum = "quantum" in headline.title.lower()
        over_limit = is_quantum and quantum_count >= MAX_QUANTUM_IN_TOP_STORIES
        if headline.score < 0 or over_limit:
            overflow.append(headline)
            continue
        quantum_count += int(is_quantum)
        kept.append(headline)
    return kept + sorted(overflow, key=lambda h: h.score, reverse=True)


def _collect() -> List[Headline]:
    sources: List[Tuple[str, object, tuple]] = [
        (IBM_RSS_URL, _fetch_rss, (IBM_RSS_URL, "IBM Newsroom")),
        (IBM_RESEARCH_RSS_URL, _fetch_rss, (IBM_RESEARCH_RSS_URL, "IBM Research")),
    ]
    sources.extend((url, _fetch_newsroom_listing, (url,)) for url in IBM_NEWSROOM_LISTINGS)

    items: List[Headline] = []
    for label, fetcher, args in sources:
        try:
            items.extend(fetcher(*args))  # type: ignore[operator]
        except Exception as exc:
            print(f"[warn] could not read {label}: {exc}", file=sys.stderr)
    return items


def scrape_headlines() -> List[Headline]:
    """Collect recent IBM stories, read them, and return them best-first."""
    items = [headline for headline in _collect() if _is_ibm_url(headline.url)]
    candidates = [headline for headline in _deduplicate(items) if _is_candidate(headline)]

    with ThreadPoolExecutor(max_workers=6) as pool:
        bodies: Dict[str, str] = dict(
            zip(
                (headline.url for headline in candidates),
                pool.map(_fetch_article_text, (headline.url for headline in candidates)),
            )
        )

    now = datetime.now()
    for headline in candidates:
        headline.body = bodies.get(headline.url, "")
        headline.score = _score(headline, now)

    candidates.sort(key=lambda h: (h.score, h.published), reverse=True)
    return _limit_quantum(candidates)
