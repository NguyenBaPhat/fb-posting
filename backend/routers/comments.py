import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Form, HTTPException

from services.fb_poster import comment_on_multiple
from services.job_store import complete_job, create_job, fail_job, get_job, update_job_progress
from services.storage import read_json, write_json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/comments", tags=["comments"])
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


@router.get("/targets")
def list_comment_targets():
    posts = read_json("posts")
    targets = []
    for post in posts:
        for i, r in enumerate(post.get("results") or []):
            if not r.get("success"):
                continue
            targets.append({
                "id": f"{post['id']}:{i}",
                "history_id": post["id"],
                "result_index": i,
                "post_url": r.get("post_url") or "",
                "group_url": r.get("group_url") or "",
                "group_name": r.get("group_name") or "",
                "account_email": r.get("account_email") or "",
                "post_content": (post.get("content") or "")[:200],
                "posted_at": post.get("created_at"),
            })
    return sorted(targets, key=lambda t: t.get("posted_at", ""), reverse=True)


async def _run_comment_job(
    job_id: str,
    selected_accounts: list,
    target_list: list,
    content: str,
    run_headless: bool,
):
    def on_progress(data: dict):
        update_job_progress(
            job_id,
            data["done"],
            data["total"],
            data["results"],
            data.get("current"),
        )

    try:
        results = await comment_on_multiple(
            accounts=selected_accounts,
            targets=target_list,
            content=content,
            headless=run_headless,
            on_progress=on_progress,
        )
        success_count = sum(1 for r in results if r.get("success"))
        record = {
            "id": str(uuid.uuid4()),
            "content": content,
            "target_count": len(target_list),
            "account_count": len(selected_accounts),
            "created_at": datetime.now(VN_TZ).isoformat(),
            "results": results,
            "total": len(results),
            "success_count": success_count,
        }
        comments_history = read_json("comments")
        comments_history.append(record)
        write_json("comments", comments_history)
        complete_job(job_id, record)
    except Exception as e:
        logger.exception("Comment job failed: %s", e)
        fail_job(job_id, str(e))


@router.post("/send")
async def send_comments(
    content: str = Form(...),
    account_ids: str = Form(...),
    targets: str = Form(...),
    headless: Optional[str] = Form(None),
):
    if not content.strip():
        raise HTTPException(400, "Nội dung bình luận không được trống")

    try:
        target_list = json.loads(targets)
    except json.JSONDecodeError:
        raise HTTPException(400, "Danh sách bài viết không hợp lệ")

    if not isinstance(target_list, list) or len(target_list) == 0:
        raise HTTPException(400, "Chọn ít nhất 1 bài viết")

    selected_account_ids = [i.strip() for i in account_ids.split(",") if i.strip()]
    if not selected_account_ids:
        raise HTTPException(400, "Chọn ít nhất 1 tài khoản")

    all_accounts = read_json("accounts")
    selected_accounts = [a for a in all_accounts if a["id"] in selected_account_ids]
    if not selected_accounts:
        raise HTTPException(400, "Không có tài khoản hợp lệ được chọn")

    run_headless = headless is None or headless.lower() in ("true", "1", "yes")

    total = len(selected_accounts) * len(target_list)
    job_id = create_job("comment", total)
    asyncio.create_task(
        _run_comment_job(job_id, selected_accounts, target_list, content.strip(), run_headless)
    )
    return {"job_id": job_id, "total": total}


@router.get("/jobs/{job_id}")
def get_comment_job(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job không tồn tại")
    return job


@router.get("/history")
def get_comment_history():
    comments = read_json("comments")
    return sorted(comments, key=lambda c: c.get("created_at", ""), reverse=True)
