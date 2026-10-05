"""Package-wide configuration: constants and dotenv bootstrapping."""

from __future__ import annotations

# ── optional dotenv loading ────────────────────────────────────────────────
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except ImportError:
    pass

# ── scraping constants ─────────────────────────────────────────────────────
IBM_RSS_URL = "https://newsroom.ibm.com/rss"
LOOKBACK_DAYS = 7

# Keywords that flag eye-catching IBM headlines.
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

# Phrases that mark boilerplate / investor-relations noise to exclude.
STOP_PHRASES = [
    "dividends", "quarterly earnings", "financial results",
    "board of directors", "leadership appointment", "earnings per share",
]
