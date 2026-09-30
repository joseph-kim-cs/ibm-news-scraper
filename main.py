#!/usr/bin/env python3
"""
IBM Headline Linker — Monday morning LinkedIn post drafter.

Scrapes recent IBM-press releases (last 7 days), filters for eye-catching
headlines about AI / moonshots / sports partnerships, then drafts a
LinkedIn post in the user's signature storytelling style.

Two deployment options are included:
  1. Local cron job (run `python main.py` on a Monday-8am cron)
  2. GitHub Actions workflow (.github/workflows/monday_ibm_scrape.yml)

Run directly:  python3 main.py
         or:   python3 main.py --dry-run  (prints post without saving)
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List

# ── optional deps & env loading ────────────────────────────────────────────
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except ImportError:
    pass

try:
    import feedparser  # type: ignore
except ImportError:
    feedparser = None

try:
    from bs4 import BeautifulSoup  # type: ignore
except ImportError:
    BeautifulSoup = None

try:
    import requests  # type: ignore
except ImportError:
    requests = None

# ── constants ──────────────────────────────────────────────────────────────
IBM_RSS_URL = "https://newsroom.ibm.com/rss"
LOOKBACK_DAYS = 7

# Keywords that catch "big-IBM-eye-catching" headlines.
# Matched case-insensitively against headline text.
KEYWORDS = [
    # AI / research / moonshots
    "ai", "artificial intelligence", "watson", "watsonx", "genai", "llm",
    "foundation model", "machine learning", "quantum",
    "moon", "lunar", "space", "nasa", "open-source", "open source",
    "breakthrough", "milestone", "announcement", "partnership",
    # Sports / consumer-facing
    "us open", "usta", "tennis", "sports", "fan engagement",
    "copenhagen", "formula 1", "f1", "nfl", "nba", "grand slam",
    # Business / cloud
    "cloud", "red hat", "hybrid", "security", "blockchain",
    "sustainability", "climate", "green",
]

# Exclude boilerplate / non-headline noise.
STOP_PHRASES = [
    "dividends", "quarterly earnings", "financial results",
    "board of directors", "leadership appointment", "earnings per share",
]

# ── data model ─────────────────────────────────────────────────────────────
@dataclass
class Headline:
    """A scraped headline ready for post drafting."""
    title: str
    url: str
    published: datetime
    source: str = "IBM Newsroom"


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


# ── scraping ───────────────────────────────────────────────────────────────
def _fetch_rss() -> List[Headline]:
    """Pull the last LOOKBACK_DAYS from the IBM RSS feed."""
    if feedparser is None:
        raise RuntimeError(
            "feedparser not installed — run: pip install feedparser"
        )
    cutoff = datetime.now() - timedelta(days=LOOKBACK_DAYS)
    parsed = feedparser.parse(IBM_RSS_URL)
    items: List[Headline] = []
    for entry in parsed.entries:
        pub = datetime(*entry.published_parsed[:6]) if hasattr(entry, "published_parsed") else cutoff
        if pub < cutoff:
            continue
        items.append(
            Headline(
                title=entry.title,
                url=entry.link,
                published=pub,
                source="IBM Newsroom",
            )
        )
    return items


def _fetch_latest_blog_cards() -> List[Headline]:
    """Fallback: scrape the IBM Research blog 'latest' page for headline cards.

    This is a lightweight HTML scrape (no JS). It catches pieces that may not
    appear in the RSS feed yet.
    """
    if BeautifulSoup is None:
        return []
    import urllib.request
    url = "https://research.ibm.com/blog"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return []

    soup = BeautifulSoup(html, "html.parser")
    cards = soup.find_all("a", href=True)
    cutoff = datetime.now() - timedelta(days=LOOKBACK_DAYS)
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
                published=datetime.now(),  # best-effort
                source="IBM Research",
            )
        )
    return items[:20]


def scrape_headlines() -> List[Headline]:
    """Scrape + filter headlines from the last week."""
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

    # Filter by keywords + stop phrases.
    filtered: List[Headline] = []
    for hl in unique:
        lowered = hl.title.lower()
        if any(sp in lowered for sp in STOP_PHRASES):
            continue
        if any(kw in lowered for kw in KEYWORDS):
            filtered.append(hl)

    # Sort newest-first (RSS entries are roughly chronological).
    filtered.sort(key=lambda h: h.published, reverse=True)
    return filtered


# ── drafting ───────────────────────────────────────────────────────────────
def _slug_matcher(title_lower: str):
    """Detect which storytelling 'slug' fits a headline."""
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
        "My friends know this about me. A “go look at the Moon” text is not a rare "
        "notification on my phone.\n\n"
        "Needless to say, this latest IBM Research and NASA - National Aeronautics and "
        "Space Administration announcement caught my attention. 🚀\n\n"
        "NASA has spent decades collecting an extraordinary amount of data about the "
        "Moon. Now, IBM and NASA have released an open-source AI foundation model "
        "designed to help scientists make even more of it. By connecting observations "
        "across instruments and identifying patterns that can be difficult to see in "
        "isolation, the model can help scientists explore questions around lunar craters, "
        "surface features, potential ice deposits, and more.\n\n"
        "And because it’s open source, researchers around the world can access it, "
        "build on it, and contribute to what we discover next. 🌎\n\n"
        "Decades of lunar data, and still so much left to discover. I think that’s such "
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


def _slug_dispatch(headline: Headline) -> str:
    slug = _slug_matcher(headline.title.lower())
    if slug == "sports":
        # Only use the sports template if the headline is actually about sports.
        return _sports_slug(headline)
    if slug == "moon":
        return _moon_slug(headline)
    if slug == "breakthrough":
        return _breakthrough_slug(headline)
    return _general_slug(headline)


def _call_llm_drafter(headline: Headline) -> str | None:
    """Call LLM API using BOB_API_KEY (or BOBSHELL_API_KEY / WATSONX_API_KEY).
    
    Generates a storytelling LinkedIn draft strictly under 250 tokens in the author's voice.
    Falls back to None if API key is not configured or request fails.
    """
    api_key = (
        os.getenv("BOB_API_KEY")
        or os.getenv("BOBSHELL_API_KEY")
        or os.getenv("WATSONX_API_KEY")
    )
    if not api_key or requests is None:
        return None

    # Reference few-shot sample style
    sample_sports = _sports_slug(Headline(title="US Open & IBM Watsonx", url="", published=datetime.now()))
    sample_moon = _moon_slug(Headline(title="NASA & IBM Moon Model", url="", published=datetime.now()))

    system_prompt = (
        "You are an expert tech writer and LinkedIn storyteller drafting engaging posts in a distinct, authentic voice.\n"
        "Style characteristics:\n"
        "- Conversational, genuine, reflective, and relatable hook (referencing personal passion, tech excitement, or industry observation).\n"
        "- Connect the announcement to broader business impact: making complex technology easier to understand and act on, or enhancing human capability.\n"
        "- Concise, punchy paragraphs.\n"
        "- Include the article link and 3-5 relevant hashtags (e.g. #IBM #AI #watsonx).\n"
        "- CRITICAL CONSTRAINT: Keep the entire output strictly under 250 tokens (~180 words).\n\n"
        "Here are reference style samples:\n"
        f"--- SAMPLE 1 (Sports/Event) ---\n{sample_sports}\n\n"
        f"--- SAMPLE 2 (Research/Moonshot) ---\n{sample_moon}\n"
    )

    user_prompt = (
        f"Draft a LinkedIn post based on this IBM announcement:\n"
        f"Headline: {headline.title}\n"
        f"URL: {headline.url}\n"
        f"Source: {headline.source}\n\n"
        f"Remember: Output ONLY the post body with the link and hashtags. Keep under 250 tokens."
    )

    endpoint = os.getenv("BOB_API_URL") or os.getenv("LLM_API_URL")

    # 1. Custom or OpenAI-compatible endpoint (default if URL provided)
    if endpoint:
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            team_id = os.getenv("BOB_TEAM_ID")
            if team_id:
                headers["X-Team-Id"] = team_id

            payload = {
                "model": os.getenv("LLM_MODEL", "ibm/granite-3-8b-instruct"),
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": 250,
                "temperature": 0.7,
            }
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                if "choices" in data and len(data["choices"]) > 0:
                    return data["choices"][0]["message"]["content"].strip()
                if "results" in data and len(data["results"]) > 0:
                    return data["results"][0].get("generated_text", "").strip()
        except Exception as exc:
            print(f"[warn] LLM generation request failed: {exc}", file=sys.stderr)

    # 2. Watsonx.ai direct endpoint integration if WATSONX_PROJECT_ID or WATSONX_API_KEY is present
    project_id = os.getenv("WATSONX_PROJECT_ID")
    if project_id:
        try:
            # Exchange IAM API key for IAM token
            iam_resp = requests.post(
                "https://iam.cloud.ibm.com/identity/token",
                data={"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": api_key},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=15,
            )
            if iam_resp.status_code == 200:
                token = iam_resp.json().get("access_token")
                wx_url = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com") + "/ml/v1/text/generation?version=2024-05-01"
                full_input = f"{system_prompt}\n\nUser: {user_prompt}\n\nAssistant:"
                wx_payload = {
                    "input": full_input,
                    "parameters": {
                        "max_new_tokens": 250,
                        "temperature": 0.7,
                        "decoding_method": "sample",
                    },
                    "model_id": os.getenv("WATSONX_MODEL_ID", "ibm/granite-3-8b-instruct"),
                    "project_id": project_id,
                }
                wx_resp = requests.post(
                    wx_url,
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    json=wx_payload,
                    timeout=20,
                )
                if wx_resp.status_code == 200:
                    wx_data = wx_resp.json()
                    results = wx_data.get("results", [])
                    if results:
                        return results[0].get("generated_text", "").strip()
        except Exception as exc:
            print(f"[warn] watsonx.ai generation request failed: {exc}", file=sys.stderr)

    return None


def draft_single_post(primary: Headline, other_headlines: List[Headline]) -> str:
    """Draft a LinkedIn post focused on a specific primary headline."""
    # Attempt LLM generation first
    llm_draft = _call_llm_drafter(primary)
    post = llm_draft if llm_draft else _slug_dispatch(primary)

    # Append up to 3 other headlines in the "catch-up" section
    extras = [h for h in other_headlines if h.url != primary.url][:3]
    if extras:
        lines = [
            "\n\n",
            "—\n",
            "A few other things IBM is cooking up this week 👇\n",
        ]
        for hl in extras:
            day_str = hl.published.strftime("%b %-d") if hasattr(hl.published, "strftime") else ""
            lines.append(f"· {hl.title} ({day_str}) — {hl.url}")
        post += "\n".join(lines)

    return post


def _send_macos_notification(title: str, message: str, sound: str = "default") -> None:
    """Send a native macOS desktop notification via AppleScript osascript."""
    if sys.platform != "darwin":
        return
    import subprocess
    # Escape quotes
    safe_title = title.replace('"', '\\"')
    safe_msg = message.replace('"', '\\"')
    script = f'display notification "{safe_msg}" with title "{safe_title}" sound name "{sound}"'
    try:
        subprocess.run(["osascript", "-e", script], check=False, capture_output=True)
    except Exception:
        pass


def draft_linkedin_posts(headlines: List[Headline], max_drafts: int = 10) -> List[str]:
    """Draft LinkedIn posts for up to max_drafts top headlines."""
    if not headlines:
        return [
            "No eye-catching IBM headlines found this week. "
            "I'll keep watching for the next big reveal.\n\n"
            "#IBM #AI"
        ]

    top_headlines = headlines[:max_drafts]
    return [draft_single_post(hl, headlines) for hl in top_headlines]


def draft_linkedin_post(headlines: List[Headline]) -> str:
    """Backward-compatible single post generator for the first headline."""
    posts = draft_linkedin_posts(headlines, max_drafts=1)
    return posts[0] if posts else ""


# ── orchestration ──────────────────────────────────────────────────────────
def run(dry_run: bool = False, max_drafts: int = 10, notify: bool = True) -> DraftResult:
    """Scrape + draft. Optionally persist to a drafts folder and notify."""
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

    # Save draft to disk so the user can review & post manually.
    drafts_dir = os.path.join(os.path.dirname(__file__), "drafts")
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
        _send_macos_notification(
            title="IBM Headline Linker",
            message=f"Generated {len(posts)} Monday LinkedIn drafts ready for review!",
        )

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="IBM Headline Linker — Monday LinkedIn draft generator"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print the drafts to stdout instead of saving a file",
    )
    parser.add_argument(
        "--count", type=int, default=10,
        help="Number of headline draft options to generate (default: 10)",
    )
    parser.add_argument(
        "--no-notify", action="store_true",
        help="Disable macOS desktop notification",
    )
    args = parser.parse_args()
    run(dry_run=args.dry_run, max_drafts=args.count, notify=not args.no_notify)


if __name__ == "__main__":
    main()
