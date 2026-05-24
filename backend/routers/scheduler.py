import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.fb_poster import post_to_multiple
from services.storage import read_json, write_json

router = APIRouter(prefix="/schedules", tags=["schedules"])


class ScheduleCreate(BaseModel):
    content: str
    account_ids: List[str]
    group_ids: List[str]
    scheduled_at: str   # ISO 8601: "2024-12-31T08:00:00"
    image_path: Optional[str] = None


@router.get("/")
def list_schedules():
    schedules = read_json("schedules")
    return sorted(schedules, key=lambda s: s.get("scheduled_at", ""))


@router.post("/")
def create_schedule(body: ScheduleCreate):
    # Validate datetime
    try:
        scheduled_dt = datetime.fromisoformat(body.scheduled_at)
    except ValueError:
        raise HTTPException(400, "Định dạng thời gian không hợp lệ (dùng ISO 8601)")

    if scheduled_dt <= datetime.now():
        raise HTTPException(400, "Thời gian phải ở trong tương lai")

    schedules = read_json("schedules")
    new_schedule = {
        "id": str(uuid.uuid4()),
        "content": body.content,
        "account_ids": body.account_ids,
        "group_ids": body.group_ids,
        "scheduled_at": body.scheduled_at,
        "image_path": body.image_path,
        "status": "pending",    # pending | running | done | failed
        "created_at": datetime.now().isoformat(),
        "result": None,
    }
    schedules.append(new_schedule)
    write_json("schedules", schedules)

    # Register with APScheduler
    from main import scheduler as app_scheduler
    app_scheduler.add_job(
        _run_scheduled_post,
        "date",
        run_date=scheduled_dt,
        args=[new_schedule["id"]],
        id=new_schedule["id"],
        replace_existing=True,
    )

    return new_schedule


@router.delete("/{schedule_id}")
def delete_schedule(schedule_id: str):
    schedules = read_json("schedules")
    schedule = next((s for s in schedules if s["id"] == schedule_id), None)
    if not schedule:
        raise HTTPException(404, "Lịch không tồn tại")

    # Remove from APScheduler
    try:
        from main import scheduler as app_scheduler
        app_scheduler.remove_job(schedule_id)
    except Exception:
        pass

    new_list = [s for s in schedules if s["id"] != schedule_id]
    write_json("schedules", new_list)
    return {"message": "Đã xóa lịch đăng bài"}


def _run_scheduled_post(schedule_id: str):
    """Called by APScheduler at scheduled time."""
    schedules = read_json("schedules")
    schedule = next((s for s in schedules if s["id"] == schedule_id), None)
    if not schedule:
        return

    # Update status to running
    schedule["status"] = "running"
    write_json("schedules", schedules)

    # Resolve accounts & groups
    all_accounts = read_json("accounts")
    all_groups = read_json("groups")
    selected_accounts = [a for a in all_accounts if a["id"] in schedule["account_ids"]]
    selected_groups = [g for g in all_groups if g["id"] in schedule["group_ids"]]

    headless = selected_accounts[0].get("headless", False) if selected_accounts else False

    # Run async in new event loop
    loop = asyncio.new_event_loop()
    try:
        results = loop.run_until_complete(
            post_to_multiple(
                accounts=selected_accounts,
                groups=selected_groups,
                content=schedule["content"],
                image_path=schedule.get("image_path"),
                headless=headless,
            )
        )
        schedule["status"] = "done"
        schedule["result"] = results
    except Exception as e:
        schedule["status"] = "failed"
        schedule["result"] = [{"success": False, "message": str(e)}]
    finally:
        loop.close()

    # Save to posts history
    posts = read_json("posts")
    posts.append({
        "id": str(uuid.uuid4()),
        "content": schedule["content"],
        "image_path": schedule.get("image_path"),
        "created_at": datetime.now().isoformat(),
        "type": "scheduled",
        "results": schedule["result"],
        "total": len(schedule["result"]) if schedule["result"] else 0,
        "success_count": sum(1 for r in (schedule["result"] or []) if r.get("success")),
    })
    write_json("posts", posts)
    write_json("schedules", schedules)
