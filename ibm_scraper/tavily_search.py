"""Tavily web-search enrichment for IBM headlines.

Credit budget
─────────────
Each call to ``tavily.search()`` (or the REST API) costs **1 credit**.
We allow at most ``TAVILY_MAX_SEARCHES_PER_WEEK`` calls per weekly run
(configured in config.py, default 5).  That leaves 25 credits of margin
inside a 30-credit weekly budget even if you run the scraper manually a
few extra times.

The enrichment attaches a short context string to each Headline so that
the LLM drafter can reference real, current details beyond the headline
title alone.
"""

from __future__ import annotations

import os
import sys
from typing import List, Optional

from ibm_scraper.models import Headline

# ── optional dep ──────────────────────────────────────────────────────────
try:
    from tavily import TavilyClient  # type: ignore
    _TAVILY_AVAILABLE = True
except ImportError:
    _TAVILY_AVAILABLE = False


def _api_key() -> Optional[str]:
    return os.getenv("TAVILY_API_KEY") or None


def _build_query(headline: Headline) -> str:
    """Turn a headline into a focused search query."""
    # Trim to ~100 chars so Tavily doesn't treat the whole title as noise.
    title = headline.title[:100]
    return f'IBM "{title}" site:ibm.com OR site:research.ibm.com OR site:newsroom.ibm.com'


def _format_results(results: list) -> str:
    """Flatten Tavily result dicts into a concise context block."""
    lines: List[str] = []
    for r in results:
        title = r.get("title", "").strip()
        url = r.get("url", "").strip()
        content = r.get("content", "").strip()
        # Keep snippets short — we only need enough for the LLM to add colour.
        snippet = content[:300].replace("\n", " ")
        if title or snippet:
            lines.append(f"• {title} — {url}\n  {snippet}")
    return "\n".join(lines)


def enrich_headlines(
    headlines: List[Headline],
    max_searches: int = 5,
) -> List[Headline]:
    """Attach Tavily search context to the top *max_searches* headlines.

    Headlines beyond the budget cap are returned unchanged.  If Tavily is
    unavailable or not configured, all headlines are returned unchanged and
    a warning is printed.

    Args:
        headlines:   Scraped and filtered Headline objects (already sorted).
        max_searches: Hard cap on API calls this run.  Caller should pass
                      ``config.TAVILY_MAX_SEARCHES_PER_WEEK``.

    Returns:
        The same list with ``tavily_context`` populated on the enriched items.
    """
    api_key = _api_key()

    if not api_key:
        print("[tavily] TAVILY_API_KEY not set — skipping web enrichment.", file=sys.stderr)
        return headlines

    if not _TAVILY_AVAILABLE:
        print(
            "[tavily] 'tavily-python' not installed — run: pip install tavily-python\n"
            "         Skipping web enrichment.",
            file=sys.stderr,
        )
        return headlines

    client = TavilyClient(api_key=api_key)
    budget_used = 0

    for hl in headlines:
        if budget_used >= max_searches:
            print(
                f"[tavily] Search budget reached ({max_searches} calls). "
                "Remaining headlines will not be enriched.",
            )
            break

        query = _build_query(hl)
        try:
            response = client.search(
                query=query,
                search_depth="basic",   # "basic" = 1 credit; "advanced" = 2
                max_results=3,
                include_answer=False,
            )
            budget_used += 1
            results = response.get("results", [])
            if results:
                hl.tavily_context = _format_results(results)
                print(
                    f"[tavily] [{budget_used}/{max_searches}] enriched: {hl.title[:60]}…"
                )
            else:
                print(f"[tavily] [{budget_used}/{max_searches}] no results for: {hl.title[:60]}…")
        except Exception as exc:
            print(f"[tavily] search failed for '{hl.title[:60]}': {exc}", file=sys.stderr)
            # Don't count a failed call against the budget.

    return headlines
