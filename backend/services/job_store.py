"""In-memory job status for long-running post/comment tasks."""
import threading
import uuid
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
_lock = threading.Lock()
_JOBS: dict[str, dict[str, Any]] = {}


def create_job(job_type: str, total: int) -> str:
    job_id = str(uuid.uuid4())
    with _lock:
        _JOBS[job_id] = {
            "id": job_id,
            "type": job_type,
            "status": "running",
            "done": 0,
            "total": total,
            "success_count": 0,
            "results": [],
            "current": None,
            "error": None,
            "created_at": datetime.now(VN_TZ).isoformat(),
            "record": None,
        }
    return job_id


def update_job_progress(
    job_id: str,
    done: int,
    total: int,
    results: list,
    current: Optional[dict] = None,
) -> None:
    with _lock:
        job = _JOBS.get(job_id)
        if not job:
            return
        job["done"] = done
        job["total"] = total
        job["results"] = results
        job["current"] = current
        job["success_count"] = sum(1 for r in results if r.get("success"))


def complete_job(job_id: str, record: Optional[dict] = None) -> None:
    with _lock:
        job = _JOBS.get(job_id)
        if not job:
            return
        job["status"] = "completed"
        job["record"] = record
        job["done"] = job["total"]


def fail_job(job_id: str, error: str) -> None:
    with _lock:
        job = _JOBS.get(job_id)
        if not job:
            return
        job["status"] = "failed"
        job["error"] = error


def get_job(job_id: str) -> Optional[dict]:
    with _lock:
        job = _JOBS.get(job_id)
        return dict(job) if job else None
