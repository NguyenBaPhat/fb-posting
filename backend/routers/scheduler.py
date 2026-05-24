import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from services.fb_poster import post_to_multiple
from services.storage import read_json, write_json

router = APIRouter(prefix="/schedules", tags=["schedules"])
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
UPLOADS_DIR = Path(__file__).parent.parent / "data" / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/")
def list_schedules():
    schedules = read_json("schedules")
    return sorted(schedules, key=lambda s: s.get("scheduled_at", ""))


@router.post("/")
async def create_schedule(
    content: str = Form(...),
    account_ids: str = Form(...),
    group_ids: str = Form(...),
    scheduled_at: str = Form(...),
    headless: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
):
    selected_account_ids = [i.strip() for i in account_ids.split(",") if i.strip()]
    selected_group_ids = [i.strip() for i in group_ids.split(",") if i.strip()]
    if not selected_account_ids:
        raise HTTPException(400, "Chọn ít nhất 1 tài khoản")
    if not selected_group_ids:
        raise HTTPException(400, "Chọn ít nhất 1 nhóm")

    # Validate datetime
    try:
        # Accept both:
        # - naive local time: "2026-05-24T18:30:00"  (treat as VN time)
        # - timezone-aware:   "2026-05-24T11:30:00Z" or "+07:00"
        scheduled_raw = scheduled_at.replace("Z", "+00:00")
        scheduled_dt = datetime.fromisoformat(scheduled_raw)
    except ValueError:
        raise HTTPException(400, "Định dạng thời gian không hợp lệ (dùng ISO 8601)")

    if scheduled_dt.tzinfo is None:
        scheduled_dt = scheduled_dt.replace(tzinfo=VN_TZ)
    else:
        scheduled_dt = scheduled_dt.astimezone(VN_TZ)

    if scheduled_dt <= datetime.now(VN_TZ):
        raise HTTPException(400, "Thời gian phải ở trong tương lai")

    image_path = None
    if image and image.filename:
        ext = Path(image.filename).suffix
        filename = f"{uuid.uuid4()}{ext}"
        save_path = UPLOADS_DIR / filename
        with open(save_path, "wb") as f:
            f.write(await image.read())
        image_path = str(save_path)

    run_headless = None
    if headless is not None:
        run_headless = headless.lower() in ("true", "1", "yes")

    schedules = read_json("schedules")
    new_schedule = {
        "id": str(uuid.uuid4()),
        "content": content,
        "account_ids": selected_account_ids,
        "group_ids": selected_group_ids,
        "scheduled_at": scheduled_at,
        "image_path": image_path,
        "headless": run_headless,
        "status": "pending",    # pending | running | done | failed
        "created_at": datetime.now(VN_TZ).isoformat(),
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

    if schedule.get("headless") is not None:
        run_headless = schedule["headless"]
    else:
        run_headless = selected_accounts[0].get("headless", True) if selected_accounts else True

    # Run async in new event loop
    loop = asyncio.new_event_loop()
    try:
        results = loop.run_until_complete(
            post_to_multiple(
                accounts=selected_accounts,
                groups=selected_groups,
                content=schedule["content"],
                image_path=schedule.get("image_path"),
                headless=run_headless,
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
        "created_at": datetime.now(VN_TZ).isoformat(),
        "type": "scheduled",
        "results": schedule["result"],
        "total": len(schedule["result"]) if schedule["result"] else 0,
        "success_count": sum(1 for r in (schedule["result"] or []) if r.get("success")),
    })
    write_json("posts", posts)
    write_json("schedules", schedules)
