"""FastAPI app for IBM Headline Linker.

Run it with ``./run_web.sh``, then open:

* http://127.0.0.1:8000/      browser UI
* http://127.0.0.1:8000/docs  Swagger UI
"""

from __future__ import annotations

import os
import shutil
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from ibm_scraper import tavily_search
from ibm_scraper.config import (
    DEFAULT_MAX_DRAFTS,
    LOOKBACK_DAYS,
    TAVILY_MAX_SEARCHES_PER_WEEK,
)
from ibm_scraper.drafters.events import _fallback_template, draft_event_post
from ibm_scraper.llm import resolve_api_key
from ibm_scraper.models import Event, Headline
from ibm_scraper.runner import run
from ibm_scraper.scraper import scrape_headlines
from ibm_scraper.web.draft_files import list_draft_files, read_draft_file
from ibm_scraper.web.jobs import JobBusyError, JobManager

STATIC_DIR = Path(__file__).parent / "static"
MAX_DRAFT_COUNT = 20

jobs = JobManager()


# ── schemas ───────────────────────────────────────────────────────────────

class HeadlineJobRequest(BaseModel):
    count: int = Field(DEFAULT_MAX_DRAFTS, ge=1, le=MAX_DRAFT_COUNT, description="Drafts to generate")
    save: bool = Field(True, description="Write a file to drafts/ and send a macOS notification")


class EventJobRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200, examples=["IBM Think 2026"])
    date: date
    location: str = Field("", max_length=200, examples=["Boston, MA"])
    description: str = Field("", max_length=5000, description="Your notes and takeaways")
    url: str = Field("", max_length=2000, pattern=r"^$|^https?://\S+$")
    save: bool = Field(True, description="Write a file to drafts/ and send a macOS notification")


class HeadlineOut(BaseModel):
    title: str
    url: str
    published: str
    source: str
    score: float


class DraftOut(BaseModel):
    title: str
    post: str
    url: str = ""
    published: str = ""
    drafted: bool = Field(True, description="False when the LLM did not write this post")
    warning: str = Field("", description="Checks to review before posting")
    web_context: str = ""


class JobResult(BaseModel):
    headlines: List[HeadlineOut] = []
    drafts: List[DraftOut] = []
    saved: bool = False


class JobOut(BaseModel):
    id: str
    kind: Literal["scrape", "headlines", "event"]
    status: Literal["running", "succeeded", "failed"]
    created_at: datetime
    finished_at: Optional[datetime] = None
    log: str = ""
    result: Optional[JobResult] = None
    error: str = ""


class LlmStatus(BaseModel):
    configured: bool
    backend: str


class WebSearchStatus(BaseModel):
    configured: bool
    max_searches_per_run: int


class StatusOut(BaseModel):
    llm: LlmStatus
    web_search: WebSearchStatus
    default_count: int
    max_count: int
    lookback_days: int
    active_job_id: Optional[str] = None


class DraftFileSummary(BaseModel):
    name: str
    kind: Literal["headlines", "event"]
    title: str
    created: str
    draft_count: int


class DraftFile(DraftFileSummary):
    drafts: List[DraftOut]
    markdown: str


# ── job work ──────────────────────────────────────────────────────────────

def _headline_out(headline: Headline) -> HeadlineOut:
    return HeadlineOut(
        title=headline.title,
        url=headline.url,
        published=headline.published.date().isoformat(),
        source=headline.source,
        score=round(headline.score, 1),
    )


def _scrape_work() -> JobResult:
    print(f"[web] scraping IBM Newsroom and Research (last {LOOKBACK_DAYS} days)…")
    headlines = scrape_headlines()
    print(f"[web] {len(headlines)} ranked headline(s) found")
    return JobResult(headlines=[_headline_out(item) for item in headlines])


def _headlines_work(request: HeadlineJobRequest) -> JobResult:
    result = run(dry_run=not request.save, max_drafts=request.count, notify=True)
    # With no headlines, run() returns a placeholder post and saves nothing.
    drafts = [
        DraftOut(
            title=headline.title,
            post=post,
            url=headline.url,
            published=headline.published.date().isoformat(),
            drafted=headline.drafted,
            warning=headline.draft_warning,
            web_context=headline.tavily_context,
        )
        for headline, post in zip(result.headlines, result.linkedin_posts)
    ]
    return JobResult(
        headlines=[_headline_out(item) for item in result.headlines],
        drafts=drafts,
        saved=request.save and bool(result.headlines),
    )


def _event_work(request: EventJobRequest) -> JobResult:
    event = Event(
        name=request.name,
        date=request.date.isoformat(),
        location=request.location,
        description=request.description,
        url=request.url,
    )
    post = draft_event_post(event, dry_run=not request.save)
    used_template = post == _fallback_template(event)
    draft = DraftOut(
        title=event.name,
        post=post,
        url=event.url,
        published=event.date,
        warning="The LLM was unavailable, so this is the generic template." if used_template else "",
    )
    return JobResult(drafts=[draft], saved=request.save)


# ── app ───────────────────────────────────────────────────────────────────

app = FastAPI(
    title="IBM Headline Linker",
    version="1.0.0",
    description=(
        "Scrape recent IBM news and draft LinkedIn posts. Jobs run in the background: "
        "start one, then poll `GET /api/jobs/{job_id}`. Only one job runs at a time."
    ),
)

# Together these stop other websites open in the browser from driving this
# local server, which could otherwise spend Tavily and LLM credits.
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])


@app.middleware("http")
async def reject_cross_origin_writes(request: Request, call_next: Any) -> Any:
    origin = request.headers.get("origin")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and origin:
        if urlsplit(origin).netloc != request.headers.get("host"):
            return JSONResponse({"detail": "Cross-origin request rejected"}, status_code=403)
    return await call_next(request)


def _llm_backend() -> str:
    if not resolve_api_key():
        return ""
    endpoint = os.getenv("BOB_API_URL") or os.getenv("LLM_API_URL") or ""
    if endpoint and "your-endpoint" not in endpoint and "example.com" not in endpoint:
        return "HTTP endpoint"
    if os.getenv("WATSONX_PROJECT_ID"):
        return "watsonx.ai"
    return "Bob CLI" if shutil.which("bob") else ""


def _start_job(kind: str, work: Any) -> Dict[str, Any]:
    try:
        return jobs.start(kind, work)
    except JobBusyError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"message": "Another job is still running", "job_id": exc.job_id},
        ) from exc


@app.get("/api/status", response_model=StatusOut, tags=["status"])
def get_status() -> StatusOut:
    """Show which services are configured. Never returns API keys."""
    backend = _llm_backend()
    return StatusOut(
        llm=LlmStatus(configured=bool(backend), backend=backend),
        web_search=WebSearchStatus(
            configured=bool(tavily_search._api_key()) and tavily_search._TAVILY_AVAILABLE,
            max_searches_per_run=TAVILY_MAX_SEARCHES_PER_WEEK,
        ),
        default_count=DEFAULT_MAX_DRAFTS,
        max_count=MAX_DRAFT_COUNT,
        lookback_days=LOOKBACK_DAYS,
        active_job_id=jobs.active_id,
    )


@app.post("/api/jobs/scrape", response_model=JobOut, status_code=202, tags=["jobs"])
def start_scrape() -> Dict[str, Any]:
    """Scrape and rank headlines. Uses no Tavily or LLM credits."""
    return _start_job("scrape", _scrape_work)


@app.post("/api/jobs/headlines", response_model=JobOut, status_code=202, tags=["jobs"])
def start_headline_drafts(request: HeadlineJobRequest) -> Dict[str, Any]:
    """Run the full pipeline. Uses Tavily searches and LLM calls."""
    return _start_job("headlines", lambda: _headlines_work(request))


@app.post("/api/jobs/event", response_model=JobOut, status_code=202, tags=["jobs"])
def start_event_draft(request: EventJobRequest) -> Dict[str, Any]:
    """Draft a post about an event you attended. Uses an LLM call."""
    return _start_job("event", lambda: _event_work(request))


@app.get("/api/jobs/{job_id}", response_model=JobOut, tags=["jobs"])
def get_job(job_id: str) -> Dict[str, Any]:
    """Get a job's status, log, and result."""
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return job


@app.get("/api/drafts", response_model=List[DraftFileSummary], tags=["drafts"])
def get_draft_files() -> List[Dict[str, Any]]:
    """List saved draft files, newest first."""
    return list_draft_files()


@app.get("/api/drafts/{name}", response_model=DraftFile, tags=["drafts"])
def get_draft_file(name: str) -> Dict[str, Any]:
    """Read one saved draft file."""
    draft_file = read_draft_file(name)
    if draft_file is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Draft file not found")
    return draft_file


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
