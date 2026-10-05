"""Headline LinkedIn post drafter: slug templates + LLM drafter."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from ibm_scraper.llm import call_llm
from ibm_scraper.models import Headline


# ── slug templates ────────────────────────────────────────────────────────

def _slug_matcher(title_lower: str) -> str:
    """Detect which storytelling slug best fits a headline."""
    if any(k in title_lower for k in ["us open", "usta", "tennis", "sports", "fan"]):
        return "sports"
    if any(k in title_lower for k in ["moon", "lunar", "space", "nasa"]):
        return "moon"
    if any(k in title_lower for k in ["breakthrough", "milestone", "open-source", "open source"]):
        return "breakthrough"
    return "general"


def _sports_slug(headline: Headline) -> str:
    return (
        "As a lifelong sports enthusiast and former high school tennis JV warrior, "
        "it was especially exciting to see how AI is transforming tennis beyond what "
        "happens on the court.\n\n"
        "This year's US Open showcased what happens when data, AI, and fan engagement "
        "come together at scale. Through their partnership, IBM and the (USTA) United "
        "States Tennis Association introduced experiences powered by watsonx, including "
        "Match Chat, Likelihood to Win, personalized content, and the new Serve Quality "
        "metric. These innovations helped more than 14 million fans engage with the "
        "tournament in a more interactive and personalized way.\n\n"
        "It was fascinating to see this technology firsthand at IBM's recent tennis and "
        "AI showcase in New York. It reminded me of a common theme I've seen across AI "
        "projects: the most successful solutions don't just generate more information, "
        "they make complex information easier to understand and act on.\n\n"
        "AI is most impactful when it enhances experiences while making organizations "
        "more efficient.\n\n"
        "#IBM #AI #USOpen #watsonx #SportsAnalytics"
    )


def _moon_slug(headline: Headline) -> str:
    return (
        "I love the Moon. 🌙\n\n"
        'My friends know this about me. A \u201cgo look at the Moon\u201d text is not a rare '
        "notification on my phone.\n\n"
        "Needless to say, this latest IBM Research and NASA - National Aeronautics and "
        "Space Administration announcement caught my attention. 🚀\n\n"
        "NASA has spent decades collecting an extraordinary amount of data about the "
        "Moon. Now, IBM and NASA have released an open-source AI foundation model "
        "designed to help scientists make even more of it. By connecting observations "
        "across instruments and identifying patterns that can be difficult to see in "
        "isolation, the model can help scientists explore questions around lunar craters, "
        "surface features, potential ice deposits, and more.\n\n"
        "And because it's open source, researchers around the world can access it, "
        "build on it, and contribute to what we discover next. 🌎\n\n"
        "Decades of lunar data, and still so much left to discover. I think that's such "
        "a cool example of how AI can help us look at the data we already have in "
        "entirely new ways.\n\n"
        "Check out what IBM and NASA are building 👇\n"
        "https://lnkd.in/g83vwAym"
    )


def _breakthrough_slug(headline: Headline) -> str:
    return (
        f"{headline.title}\n\n"
        f"Big news out of IBM this week — and it's the kind of project that reminds "
        f"me why I love being in tech sales. When organizations can turn complex data "
        f"into actionable insight at scale, that's where real value is created.\n\n"
        f"AI is most impactful when it enhances human capability while making "
        f"organizations more efficient.\n\n"
        f"Read the full announcement: {headline.url}\n\n"
        f"#IBM #AI #Innovation"
    )


def _general_slug(headline: Headline) -> str:
    return (
        f"{headline.title}\n\n"
        f"This week's IBM announcement caught my eye. As someone who works with "
        f"organizations navigating digital transformation, I'm always looking for "
        f"stories about how AI is making complex information easier to understand and "
        f"act on.\n\n"
        f"AI is most impactful when it enhances experiences while making organizations "
        f"more efficient.\n\n"
        f"Read more: {headline.url}\n\n"
        f"#IBM #AI #watsonx"
    )


def slug_dispatch(headline: Headline) -> str:
    """Pick and return the right template-based slug for a headline."""
    slug = _slug_matcher(headline.title.lower())
    dispatch = {
        "sports": _sports_slug,
        "moon": _moon_slug,
        "breakthrough": _breakthrough_slug,
        "general": _general_slug,
    }
    return dispatch.get(slug, _general_slug)(headline)


# ── LLM drafter ───────────────────────────────────────────────────────────

def _build_headline_prompt(headline: Headline) -> str:
    sample_sports = _sports_slug(
        Headline(title="US Open & IBM Watsonx", url="", published=datetime.now())
    )
    sample_moon = _moon_slug(
        Headline(title="NASA & IBM Moon Model", url="", published=datetime.now())
    )
    return (
        "You are an expert tech writer and LinkedIn storyteller drafting engaging posts "
        "in a distinct, authentic voice.\n"
        "Style characteristics:\n"
        "- Conversational, genuine, reflective, and relatable hook.\n"
        "- Connect the announcement to broader business impact: making complex technology "
        "easier to understand and act on, or enhancing human capability.\n"
        "- Concise, punchy paragraphs.\n"
        "- Include the article link and 3-5 relevant hashtags (e.g. #IBM #AI #watsonx).\n"
        "- CRITICAL CONSTRAINT: Keep the entire output strictly under 250 tokens (~180 words).\n\n"
        "Reference style samples:\n"
        f"--- SAMPLE 1 ---\n{sample_sports}\n\n"
        f"--- SAMPLE 2 ---\n{sample_moon}\n\n"
        f"Draft a LinkedIn post for this announcement:\n"
        f"Headline: {headline.title}\n"
        f"URL: {headline.url}\n"
        f"Source: {headline.source}\n\n"
        "Output ONLY the LinkedIn post text, link, and hashtags. Keep under 250 tokens."
    )


# ── public drafting API ───────────────────────────────────────────────────

def draft_single_post(primary: Headline, other_headlines: List[Headline]) -> str:
    """Draft a LinkedIn post focused on *primary*, with a catch-up footer."""
    prompt = _build_headline_prompt(primary)
    llm_draft: Optional[str] = call_llm(prompt, max_tokens=250, temperature=0.7)
    post = llm_draft if llm_draft else slug_dispatch(primary)

    # Append up to 3 other headlines in the catch-up section.
    extras = [h for h in other_headlines if h.url != primary.url][:3]
    if extras:
        lines = ["\n\n", "—\n", "A few other things IBM is cooking up this week 👇\n"]
        for hl in extras:
            day_str = hl.published.strftime("%b %-d") if hasattr(hl.published, "strftime") else ""
            lines.append(f"· {hl.title} ({day_str}) — {hl.url}")
        post += "\n".join(lines)

    return post


def draft_linkedin_posts(headlines: List[Headline], max_drafts: int = 10) -> List[str]:
    """Draft LinkedIn posts for up to *max_drafts* top headlines."""
    if not headlines:
        return [
            "No eye-catching IBM headlines found this week. "
            "I'll keep watching for the next big reveal.\n\n#IBM #AI"
        ]
    return [draft_single_post(hl, headlines) for hl in headlines[:max_drafts]]


def draft_linkedin_post(headlines: List[Headline]) -> str:
    """Backward-compatible single-post helper."""
    posts = draft_linkedin_posts(headlines, max_drafts=1)
    return posts[0] if posts else ""
