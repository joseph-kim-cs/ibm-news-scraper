"""Event LinkedIn post drafter."""

from __future__ import annotations

import os
from datetime import datetime

from ibm_scraper.llm import call_llm
from ibm_scraper.models import Event
from ibm_scraper.notifications import send_macos_notification


def _build_event_prompt(event: Event) -> str:
    location_line = f"Location: {event.location}\n" if event.location else ""
    url_line = f"Event URL / reference: {event.url}\n" if event.url else ""
    return (
        "You are an expert tech writer and LinkedIn storyteller.\n"
        "The user attended or hosted an event and wants to share the experience on LinkedIn.\n"
        "Style characteristics:\n"
        "- Start with a genuine, personal hook — what made the event stand out.\n"
        "- Highlight one or two key takeaways or conversations that stuck with you.\n"
        "- Reflect on what it means for your field or community.\n"
        "- Conversational, concise paragraphs. No corporate fluff.\n"
        "- End with a forward-looking thought or question to spark engagement.\n"
        "- Include the event URL (if provided) and 3-5 relevant hashtags.\n"
        "- CRITICAL CONSTRAINT: Keep the entire output strictly under 280 tokens (~200 words).\n\n"
        "Event details:\n"
        f"Name: {event.name}\n"
        f"Date: {event.date}\n"
        f"{location_line}"
        f"Description / notes: {event.description}\n"
        f"{url_line}"
        "\nOutput ONLY the LinkedIn post text, link (if any), and hashtags. Keep under 280 tokens."
    )


def _fallback_template(event: Event) -> str:
    """Template-based post used when no LLM backend is available."""
    loc_str = f" in {event.location}" if event.location else ""
    desc_str = f"\n\n{event.description}" if event.description else ""
    url_str = f"\n\n{event.url}" if event.url else ""
    return (
        f"Just wrapped up {event.name}{loc_str} ({event.date}) — "
        f"and I'm still processing everything.{desc_str}"
        f"\n\nThe conversations, the energy, the ideas — "
        f"there's something special about being in the room where it happens."
        f"{url_str}"
        f"\n\n#IBM #Tech #Innovation"
    )


def draft_event_post(event: Event, dry_run: bool = False) -> str:
    """Draft a LinkedIn post for a custom event.

    Tries LLM generation first; falls back to a template.
    Prints the draft to stdout in dry-run mode; otherwise saves to ``drafts/``.
    """
    print(f"[event-drafter] drafting LinkedIn post for: {event.name} ({event.date})")

    prompt = _build_event_prompt(event)
    llm_draft = call_llm(prompt, max_tokens=280, temperature=0.75)
    post = llm_draft if llm_draft else _fallback_template(event)

    if dry_run:
        print("\n" + "=" * 72)
        print(f"EVENT LINKEDIN DRAFT: {event.name}")
        print("=" * 72)
        print(post)
        print("=" * 72)
        return post

    drafts_dir = os.path.join(os.path.dirname(__file__), "..", "..", "drafts")
    os.makedirs(drafts_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    safe_name = (
        "".join(c if c.isalnum() or c in "-_ " else "_" for c in event.name)
        .strip()
        .replace(" ", "_")
    )
    draft_path = os.path.join(drafts_dir, f"event_draft_{safe_name}_{ts}.md")
    with open(draft_path, "w", encoding="utf-8") as fh:
        fh.write(f"# LinkedIn Draft — {event.name}\n\n")
        fh.write(f"**Date:** {event.date}\n")
        if event.location:
            fh.write(f"**Location:** {event.location}\n")
        if event.url:
            fh.write(f"**URL:** {event.url}\n")
        if event.description:
            fh.write(f"\n**Notes:** {event.description}\n")
        fh.write(f"\n---\n\n{post}\n")

    print(f"[saved] event draft written to {draft_path}")
    send_macos_notification(
        title="IBM Headline Linker",
        message=f"Event draft for '{event.name}' is ready!",
    )
    return post
