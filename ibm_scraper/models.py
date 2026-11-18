"""Domain models shared across the package."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List


@dataclass
class Headline:
    """A scraped IBM headline ready for post drafting."""

    title: str
    url: str
    published: datetime
    source: str = "IBM Newsroom"
    tavily_context: str = ""  # populated by tavily_search.enrich_headlines()
    body: str = ""  # article text fetched from the source page
    score: float = 0.0  # editorial ranking score
    drafted: bool = False  # True when the LLM produced a post
    draft_warning: str = ""  # checks to review before posting


@dataclass
class Event:
    """A custom event the user attended, used to draft a LinkedIn post."""

    name: str
    date: str  # ISO date string, e.g. "2025-05-05"
    location: str = ""
    description: str = ""
    url: str = ""


@dataclass
class DraftResult:
    """Final draft package returned to the caller."""

    headlines: List[Headline] = field(default_factory=list)
    linkedin_posts: List[str] = field(default_factory=list)
    drafted_at: datetime = field(default_factory=datetime.now)

    @property
    def linkedin_post(self) -> str:
        """Backward-compatible access to the first draft post."""
        return self.linkedin_posts[0] if self.linkedin_posts else ""
