"""IBM headline scraping: RSS feed and Research blog fallback."""

from __future__ import annotations

import sys
import urllib.request
from datetime import datetime, timedelta
from typing import List

from ibm_scraper.config import IBM_RSS_URL, KEYWORDS, LOOKBACK_DAYS, STOP_PHRASES
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


def _fetch_rss() -> List[Headline]:
    """Pull the last LOOKBACK_DAYS of entries from the IBM RSS feed."""
    if feedparser is None:
        raise RuntimeError("feedparser not installed — run: pip install feedparser")

    cutoff = datetime.now() - timedelta(days=LOOKBACK_DAYS)
    parsed = feedparser.parse(IBM_RSS_URL)
    items: List[Headline] = []
    for entry in parsed.entries:
        pub = (
            datetime(*entry.published_parsed[:6])
            if hasattr(entry, "published_parsed")
            else cutoff
        )
        if pub < cutoff:
            continue
        items.append(
            Headline(title=entry.title, url=entry.link, published=pub, source="IBM Newsroom")
        )
    return items


def _fetch_latest_blog_cards() -> List[Headline]:
    """Fallback: scrape the IBM Research blog 'latest' page for headline cards.

    Lightweight HTML scrape (no JS). Catches pieces that may not appear in the
    RSS feed yet.
    """
    if BeautifulSoup is None:
        return []

    url = "https://research.ibm.com/blog"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return []

    soup = BeautifulSoup(html, "html.parser")
    cards = soup.find_all("a", href=True)
    items: List[Headline] = []
    seen: set[str] = set()
    for card in cards:
        title_tag = card.find(attrs={"data-testid": "card-title"}) or card
        raw_title = title_tag.get_text(strip=True)
        href = card["href"]
        if not raw_title or len(raw_title) < 20:
            continue
        if href in seen or raw_title.lower() in seen:
            continue
        seen.add(href)
        seen.add(raw_title.lower())
        items.append(
            Headline(
                title=raw_title[:140],
                url=href if href.startswith("http") else f"https://research.ibm.com{href}",
                published=datetime.now(),  # best-effort; blog cards have no date
                source="IBM Research",
            )
        )
    return items[:20]


def scrape_headlines() -> List[Headline]:
    """Scrape, deduplicate, filter, and sort headlines from the last week."""
    all_items: List[Headline] = []
    try:
        all_items.extend(_fetch_rss())
    except Exception as exc:
        print(f"[warn] RSS scrape failed: {exc}", file=sys.stderr)
    all_items.extend(_fetch_latest_blog_cards())

    # Deduplicate by title (case-insensitive).
    seen_titles: set[str] = set()
    unique: List[Headline] = []
    for hl in all_items:
        t = hl.title.strip().lower()
        if t in seen_titles:
            continue
        seen_titles.add(t)
        unique.append(hl)

    # Filter by keywords, excluding stop phrases.
    filtered: List[Headline] = []
    for hl in unique:
        lowered = hl.title.lower()
        if any(sp in lowered for sp in STOP_PHRASES):
            continue
        if any(kw in lowered for kw in KEYWORDS):
            filtered.append(hl)

    # Sort newest-first.
    filtered.sort(key=lambda h: h.published, reverse=True)
    return filtered
