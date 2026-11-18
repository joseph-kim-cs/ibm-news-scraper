"""Read the Markdown draft files written to ``drafts/``."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

DRAFTS_DIR = Path(__file__).resolve().parents[2] / "drafts"

_FILE_NAME_RE = re.compile(r"(linkedin_draft|event_draft)_[\w-]+\.md")
_TIMESTAMP_RE = re.compile(r"(\d{4}-\d{2}-\d{2})_(\d{2})(\d{2})\.md$")
_HEADLINE_LINK_RE = re.compile(r"^- \[(.*)\]\((\S*)\) — (\d{4}-\d{2}-\d{2})$", re.MULTILINE)
_SECTION_RE = re.compile(r"^## Draft Option \d+(?:: (.*))?$", re.MULTILINE)
_REVIEW_RE = re.compile(r"^> \*\*Review before posting:\*\* (.*)$", re.MULTILINE)
_NOTES_RE = re.compile(r"<details>\s*<summary>.*?</summary>(.*?)</details>", re.DOTALL)
_POST_URL_RE = re.compile(r"^https?://\S+$", re.MULTILINE)
_NOT_GENERATED_RE = re.compile(r"^\[No draft generated: (.*?)\]")


def _timestamp(name: str) -> str:
    match = _TIMESTAMP_RE.search(name)
    return f"{match[1]} {match[2]}:{match[3]}" if match else ""


def _draft(title: str, post: str, **extra: Any) -> Dict[str, Any]:
    fields = {
        "title": title,
        "post": post,
        "url": "",
        "published": "",
        "drafted": True,
        "warning": "",
        "web_context": "",
    }
    fields.update(extra)
    return fields


def _clean_notes(block: str) -> str:
    return re.sub(r"^```\w*\n?|\n?```$", "", block.strip()).strip()


def _parse_headline_file(text: str) -> List[Dict[str, Any]]:
    links = {title: (url, day) for title, url, day in _HEADLINE_LINK_RE.findall(text)}
    matches = list(_SECTION_RE.finditer(text))
    drafts: List[Dict[str, Any]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        section = text[match.end():end].strip()
        section = re.sub(r"\n---\s*$", "", section)

        # Collapsible blocks hold Tavily context or hand-written fact-check notes.
        notes = "\n\n".join(_clean_notes(block) for block in _NOTES_RE.findall(section))
        review = _REVIEW_RE.search(section)
        post = _REVIEW_RE.sub("", _NOTES_RE.sub("", section)).strip()
        missing = _NOT_GENERATED_RE.match(post)

        title = match[1] or f"Draft {index + 1}"
        url, published = links.get(title, ("", ""))
        if not url:  # Edited files may retitle a draft; the post still has its link.
            post_url = _POST_URL_RE.search(post)
            url = post_url[0] if post_url else ""
        warning = missing[1] if missing else (review[1] if review else "")
        drafts.append(
            _draft(
                title,
                post,
                url=url,
                published=published,
                drafted=not missing,
                warning=warning,
                web_context=notes,
            )
        )
    return drafts


def _parse_event_file(text: str) -> List[Dict[str, Any]]:
    header, _, post = text.partition("\n---\n")
    title = re.search(r"^# LinkedIn Draft — (.*)$", header, re.MULTILINE)
    day = re.search(r"^\*\*Date:\*\* (.*)$", header, re.MULTILINE)
    url = re.search(r"^\*\*URL:\*\* (.*)$", header, re.MULTILINE)
    return [
        _draft(
            title[1] if title else "Event post",
            post.strip(),
            url=url[1] if url else "",
            published=day[1] if day else "",
        )
    ]


def _parse(name: str, text: str) -> List[Dict[str, Any]]:
    return _parse_event_file(text) if name.startswith("event_") else _parse_headline_file(text)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _summary(path: Path, drafts: List[Dict[str, Any]]) -> Dict[str, Any]:
    is_event = path.name.startswith("event_")
    return {
        "name": path.name,
        "kind": "event" if is_event else "headlines",
        "title": drafts[0]["title"] if is_event and drafts else "Headline drafts",
        "created": _timestamp(path.name),
        "draft_count": len(drafts),
    }


def list_draft_files() -> List[Dict[str, Any]]:
    """Return saved draft files, newest first."""
    if not DRAFTS_DIR.is_dir():
        return []
    files = [
        _summary(path, _parse(path.name, _read(path)))
        for path in DRAFTS_DIR.iterdir()
        if path.is_file() and _FILE_NAME_RE.fullmatch(path.name)
    ]
    return sorted(files, key=lambda item: (item["created"], item["name"]), reverse=True)


def read_draft_file(name: str) -> Optional[Dict[str, Any]]:
    """Return one saved file, or ``None`` if *name* is not a saved draft."""
    # The strict name pattern also rules out path traversal.
    if not _FILE_NAME_RE.fullmatch(name):
        return None
    path = DRAFTS_DIR / name
    if not path.is_file():
        return None
    text = _read(path)
    drafts = _parse(name, text)
    return {**_summary(path, drafts), "drafts": drafts, "markdown": text}
