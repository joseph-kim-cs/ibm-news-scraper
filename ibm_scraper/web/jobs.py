"""Background jobs for the web app.

Scraping and drafting take minutes, so they run outside the request. Only one
job runs at a time: this keeps a double click from spending Tavily and LLM
credits twice, and lets each job capture the pipeline's ``print`` output.
"""

from __future__ import annotations

import io
import sys
import threading
import traceback
import uuid
from collections import OrderedDict
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, TextIO

MAX_LOG_CHARS = 200_000
MAX_FINISHED_JOBS = 20


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Job:
    id: str
    kind: str
    status: str = "running"  # running | succeeded | failed
    created_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    log: str = ""
    result: Any = None
    error: str = ""


class JobBusyError(Exception):
    """Raised when a job is requested while another is running."""

    def __init__(self, job_id: str) -> None:
        super().__init__(f"Job {job_id} is still running")
        self.job_id = job_id


class _LogWriter(io.TextIOBase):
    """Send text to the job log and to the server's terminal."""

    def __init__(self, manager: "JobManager", job_id: str, terminal: TextIO) -> None:
        self._manager = manager
        self._job_id = job_id
        self._terminal = terminal

    def writable(self) -> bool:
        return True

    def write(self, text: str) -> int:
        self._terminal.write(text)
        self._manager.append_log(self._job_id, text)
        return len(text)

    def flush(self) -> None:
        self._terminal.flush()


class JobManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: "OrderedDict[str, Job]" = OrderedDict()
        self._active_id: Optional[str] = None

    @property
    def active_id(self) -> Optional[str]:
        with self._lock:
            return self._active_id

    def start(self, kind: str, work: Callable[[], Any]) -> Dict[str, Any]:
        """Start *work* in the background, or raise :class:`JobBusyError`."""
        with self._lock:
            if self._active_id:
                raise JobBusyError(self._active_id)
            job = Job(id=uuid.uuid4().hex[:12], kind=kind, created_at=_now())
            self._jobs[job.id] = job
            self._active_id = job.id
            self._prune()
            snapshot = dict(vars(job))

        # Daemon thread: stopping the server should not wait for a long run.
        threading.Thread(target=self._run, args=(job, work), daemon=True).start()
        return snapshot

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(vars(job)) if job else None

    def append_log(self, job_id: str, text: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.log = (job.log + text)[-MAX_LOG_CHARS:]

    def _run(self, job: Job, work: Callable[[], Any]) -> None:
        stdout = _LogWriter(self, job.id, sys.stdout)
        stderr = _LogWriter(self, job.id, sys.stderr)
        result: Any = None
        error = ""
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                result = work()
            except Exception as exc:
                error = str(exc) or type(exc).__name__
                traceback.print_exc()

        with self._lock:
            job.result = result
            job.error = error
            job.status = "failed" if error else "succeeded"
            job.finished_at = _now()
            self._active_id = None

    def _prune(self) -> None:
        finished = [key for key, job in self._jobs.items() if job.status != "running"]
        for key in finished[:-MAX_FINISHED_JOBS]:
            del self._jobs[key]
