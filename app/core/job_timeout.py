from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple, Optional
import time
from datetime import datetime, timezone


@dataclass
class JobTimeoutEntry:
    category: str
    job_id: str
    timeout_seconds: int
    started_monotonic: float
    started_at: datetime
    # Optional traceability context
    project_id: Optional[str] = None
    file_id: Optional[str] = None


class JobTimeoutRegistry:
    """Simple in-memory registry for tracking per-job total timeout budgets.

    Note: This is per-process memory only. If you run multiple workers/processes,
    each will track its own registry.
    """

    def __init__(self) -> None:
        self._entries: Dict[Tuple[str, str], JobTimeoutEntry] = {}

    def register_job(self, category: str, job_id: str, timeout_seconds: int, *, project_id: Optional[str] = None, file_id: Optional[str] = None) -> None:
        key = (category, job_id)
        if key in self._entries:
            return
        self._entries[key] = JobTimeoutEntry(
            category=category,
            job_id=job_id,
            timeout_seconds=int(timeout_seconds),
            started_monotonic=time.monotonic(),
            started_at=datetime.now(timezone.utc),
            project_id=project_id,
            file_id=file_id,
        )

    def get_entry(self, category: str, job_id: str) -> Optional[JobTimeoutEntry]:
        return self._entries.get((category, job_id))

    def seconds_elapsed(self, category: str, job_id: str) -> Optional[float]:
        entry = self.get_entry(category, job_id)
        if not entry:
            return None
        return max(0.0, time.monotonic() - entry.started_monotonic)
    
    def get_latency_ms(self, category: str, job_id: str) -> Optional[int]:
        """Get latency in milliseconds for a job"""
        elapsed_sec = self.seconds_elapsed(category, job_id)
        if elapsed_sec is None:
            return None
        return int(elapsed_sec * 1000)

    def is_timed_out(self, category: str, job_id: str) -> bool:
        entry = self.get_entry(category, job_id)
        if not entry:
            return False
        elapsed = time.monotonic() - entry.started_monotonic
        return elapsed >= entry.timeout_seconds

    def remove_job(self, category: str, job_id: str) -> bool:
        """Remove a job from the timeout registry (e.g., when completed)"""
        key = (category, job_id)
        if key in self._entries:
            del self._entries[key]
            return True
        return False

    def get_project_and_file(self, category: str, job_id: str) -> tuple[Optional[str], Optional[str]]:
        entry = self.get_entry(category, job_id)
        if not entry:
            return None, None
        return entry.project_id, entry.file_id


job_timeout_registry = JobTimeoutRegistry()


