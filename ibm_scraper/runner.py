"""Orchestration: scrape + draft + persist + notify."""

from __future__ import annotations

import os
from datetime import datetime

from ibm_scraper.config import (
    DEFAULT_MAX_DRAFTS,
    LOOKBACK_DAYS,
    TAVILY_MAX_SEARCHES_PER_WEEK,
)
from ibm_scraper.drafters.headlines import draft_linkedin_posts
from ibm_scraper.models import DraftResult
from ibm_scraper.notifications import send_macos_notification
from ibm_scraper.scraper import scrape_headlines
from ibm_scraper.tavily_search import enrich_headlines


def run(dry_run: bool = False, max_drafts: int = DEFAULT_MAX_DRAFTS, notify: bool = True) -> DraftResult:
    """Scrape IBM headlines, draft LinkedIn posts, and optionally save them.

    Args:
        dry_run:    Print drafts to stdout instead of writing files.
        max_drafts: Maximum number of headline drafts to generate.
        notify:     Fire a macOS desktop notification when done.

    Returns:
        A :class:`~ibm_scraper.models.DraftResult` with all drafts.
    """
    print(f"[ibm-linkerdrafter] scraping IBM Newsroom and Research (last {LOOKBACK_DAYS} days)…")
    headlines = scrape_headlines()
    print(f"[results] {len(headlines)} ranked headline(s) found:")
    for hl in headlines:
        print(f"  • [{hl.published.date()}] ({hl.score:.1f}) {hl.title}")

    max_searches = min(TAVILY_MAX_SEARCHES_PER_WEEK, max_drafts)
    print(f"\n[tavily] enriching top {max_searches} headlines with web search…")
    headlines = enrich_headlines(headlines, max_searches=max_searches)

    posts = draft_linkedin_posts(headlines, max_drafts=max_drafts)
    result = DraftResult(headlines=headlines, linkedin_posts=posts)
    attempted = headlines[:len(posts)]
    drafted_count = sum(hl.drafted for hl in attempted)
    print(f"[drafts] {drafted_count} of {len(attempted)} generated")

    if dry_run or not headlines:
        print("\n" + "=" * 72)
        print(f"DRY-RUN LINKEDIN DRAFTS ({len(posts)} option{'s' if len(posts) > 1 else ''})")
        print("=" * 72)
        for idx, post in enumerate(posts, 1):
            hl = headlines[idx - 1] if idx - 1 < len(headlines) else None
            title_str = f": {hl.title}" if hl else ""
            print(f"\n--- DRAFT OPTION {idx}{title_str} ---\n")
            print(post)
            if hl and hl.draft_warning:
                print(f"\n[review] {hl.draft_warning}")
            print("\n" + "-" * 72)
        print("=" * 72)
        return result

    # Persist drafts for manual review before posting.
    drafts_dir = os.path.join(os.path.dirname(__file__), "..", "drafts")
    os.makedirs(drafts_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    draft_path = os.path.join(drafts_dir, f"linkedin_draft_{ts}.md")
    with open(draft_path, "w", encoding="utf-8") as fh:
        fh.write("## Top headlines\n\n")
        for hl in headlines:
            fh.write(f"- [{hl.title}]({hl.url}) — {hl.published.strftime('%Y-%m-%d')}\n")
        fh.write("\n---\n")
        for idx, post in enumerate(posts, 1):
            hl = headlines[idx - 1] if idx - 1 < len(headlines) else None
            header = f"## Draft Option {idx}: {hl.title}\n\n" if hl else f"## Draft Option {idx}\n\n"
            fh.write(f"\n{header}{post}\n\n")
            if hl and hl.drafted and hl.draft_warning:
                fh.write(f"> **Review before posting:** {hl.draft_warning}\n\n")
            # Append Tavily context as a collapsible reference block if present.
            if hl and hl.tavily_context:
                fh.write(
                    "<details>\n<summary>🔍 Tavily web context</summary>\n\n"
                    f"```\n{hl.tavily_context}\n```\n\n"
                    "</details>\n\n"
                )
            fh.write("---\n")
    print(f"\n[saved] draft written to {draft_path}")

    if notify:
        send_macos_notification(
            title="IBM Headline Linker",
            message=f"{drafted_count} of {len(attempted)} LinkedIn drafts ready for review.",
        )

    return result
