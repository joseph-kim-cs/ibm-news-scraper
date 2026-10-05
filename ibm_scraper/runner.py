"""Orchestration: scrape + draft + persist + notify."""

from __future__ import annotations

import os
from datetime import datetime

from ibm_scraper.config import IBM_RSS_URL, LOOKBACK_DAYS
from ibm_scraper.drafters.headlines import draft_linkedin_posts
from ibm_scraper.models import DraftResult
from ibm_scraper.notifications import send_macos_notification
from ibm_scraper.scraper import scrape_headlines


def run(dry_run: bool = False, max_drafts: int = 10, notify: bool = True) -> DraftResult:
    """Scrape IBM headlines, draft LinkedIn posts, and optionally save them.

    Args:
        dry_run:    Print drafts to stdout instead of writing files.
        max_drafts: Maximum number of headline drafts to generate.
        notify:     Fire a macOS desktop notification when done.

    Returns:
        A :class:`~ibm_scraper.models.DraftResult` with all drafts.
    """
    print(f"[ibm-linkerdrafter] scraping {IBM_RSS_URL} (last {LOOKBACK_DAYS} days)…")
    headlines = scrape_headlines()
    print(f"[results] {len(headlines)} eye-catching headline(s) found:")
    for hl in headlines:
        print(f"  • [{hl.published.date()}] {hl.title}")

    posts = draft_linkedin_posts(headlines, max_drafts=max_drafts)
    result = DraftResult(headlines=headlines, linkedin_posts=posts)

    if dry_run or not headlines:
        print("\n" + "=" * 72)
        print(f"DRY-RUN LINKEDIN DRAFTS ({len(posts)} option{'s' if len(posts) > 1 else ''})")
        print("=" * 72)
        for idx, post in enumerate(posts, 1):
            hl = headlines[idx - 1] if idx - 1 < len(headlines) else None
            title_str = f": {hl.title}" if hl else ""
            print(f"\n--- DRAFT OPTION {idx}{title_str} ---\n")
            print(post)
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
            fh.write(f"\n{header}{post}\n\n---\n")
    print(f"\n[saved] draft written to {draft_path}")

    if notify:
        send_macos_notification(
            title="IBM Headline Linker",
            message=f"Generated {len(posts)} Monday LinkedIn drafts ready for review!",
        )

    return result
