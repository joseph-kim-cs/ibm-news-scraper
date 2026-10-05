"""ibm_scraper — IBM Headline Linker package.

Public surface for programmatic use:

    from ibm_scraper import run, draft_event_post, Event, Headline, DraftResult
"""

from ibm_scraper.drafters import (
    draft_event_post,
    draft_linkedin_post,
    draft_linkedin_posts,
    draft_single_post,
)
from ibm_scraper.models import DraftResult, Event, Headline
from ibm_scraper.runner import run
from ibm_scraper.scraper import scrape_headlines

__all__ = [
    "run",
    "scrape_headlines",
    "draft_event_post",
    "draft_linkedin_post",
    "draft_linkedin_posts",
    "draft_single_post",
    "Headline",
    "Event",
    "DraftResult",
]
