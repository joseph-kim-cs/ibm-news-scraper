#!/usr/bin/env python3
"""
IBM Headline Linker — CLI entry point.

Headline scraping mode (default):
    python3 main.py
    python3 main.py --dry-run
    python3 main.py --count 5

Event post mode:
    python3 main.py --event-name "IBM Think 2025" \\
                    --event-date "2025-05-05" \\
                    --event-location "Boston, MA" \\
                    --event-description "Keynote on watsonx and agentic AI" \\
                    --event-url "https://www.ibm.com/events/think/"
"""

from __future__ import annotations

import argparse

from ibm_scraper import draft_event_post, run
from ibm_scraper.models import Event


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="IBM Headline Linker — LinkedIn draft generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print drafts to stdout instead of saving files",
    )
    parser.add_argument(
        "--count", type=int, default=10,
        help="Number of headline draft options to generate (default: 10)",
    )
    parser.add_argument(
        "--no-notify", action="store_true",
        help="Disable macOS desktop notification",
    )

    event_group = parser.add_argument_group(
        "event post",
        "Draft a LinkedIn post from a custom event you attended. "
        "Requires at least --event-name and --event-date.",
    )
    event_group.add_argument(
        "--event-name", metavar="NAME",
        help="Event name, e.g. 'IBM Think 2025'",
    )
    event_group.add_argument(
        "--event-date", metavar="DATE",
        help="Event date, e.g. '2025-05-05'",
    )
    event_group.add_argument(
        "--event-location", metavar="LOCATION", default="",
        help="City / venue",
    )
    event_group.add_argument(
        "--event-description", metavar="DESCRIPTION", default="",
        help="Key takeaways, talks, or notes from the event",
    )
    event_group.add_argument(
        "--event-url", metavar="URL", default="",
        help="Event URL or reference link",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.event_name:
        if not args.event_date:
            parser.error("--event-date is required when --event-name is provided")
        event = Event(
            name=args.event_name,
            date=args.event_date,
            location=args.event_location,
            description=args.event_description,
            url=args.event_url,
        )
        draft_event_post(event, dry_run=args.dry_run)
        return

    run(dry_run=args.dry_run, max_drafts=args.count, notify=not args.no_notify)


if __name__ == "__main__":
    main()
