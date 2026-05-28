import asyncio
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from services.fb_poster import post_to_multiple
from services.job_store import (
    complete_job, create_job, fail_job, get_job, update_job_progress,
)
from services.storage import read_json, write_json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/posts", tags=["posts"])

UPLOADS_DIR = Path(__file__).parent.parent / "data" / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


async def _run_post_job(
    job_id: str,
    selected_accounts: list,
    selected_groups: list,
    content: str,
    image_paths: List[str],
    run_headless: bool,
    marketplace_data: Optional[dict] = None,
):
    total = len(selected_accounts) * len(selected_groups)
    post_id = str(uuid.uuid4())

    # Tạo bản ghi ngay từ đầu, status=running
    post_record: dict = {
        "id": post_id,
        "content": content,
        "image_paths": image_paths,
        "created_at": datetime.now().isoformat(),
        "type": "immediate",
        "results": [],
        "total": total,
        "success_count": 0,
        "status": "running",
    }
    history = read_json("posts")
    history.append(post_record)
    write_json("posts", history)

    def _update_history(results: list) -> None:
        """Cập nhật bản ghi trong file JSON sau mỗi task hoàn thành."""
        h = read_json("posts")
        for p in h:
            if p["id"] == post_id:
                p["results"] = results
                p["success_count"] = sum(1 for r in results if r["success"])
                break
        write_json("posts", h)

    def on_progress(data: dict):
        update_job_progress(
            job_id,
            data["done"],
            data["total"],
            data["results"],
            data.get("current"),
        )
        _update_history(data["results"])

    try:
        results = await post_to_multiple(
            accounts=selected_accounts,
            groups=selected_groups,
            content=content,
            image_paths=image_paths,
            headless=run_headless,
            on_progress=on_progress,
            marketplace_data=marketplace_data,
        )
        # Cập nhật lần cuối — đánh dấu done
        h = read_json("posts")
        for p in h:
            if p["id"] == post_id:
                p["results"] = results
                p["success_count"] = sum(1 for r in results if r["success"])
                p["status"] = "done"
                post_record = p
                break
        write_json("posts", h)
        complete_job(job_id, post_record)
    except Exception as e:
        logger.exception("Post job failed: %s", e)
        fail_job(job_id, str(e))


@router.post("/send")
async def send_post(
    content: str = Form(""),
    account_ids: str = Form(...),
    group_ids: str = Form(...),
    images: List[UploadFile] = File(default=[]),
    headless: Optional[str] = Form(None),
    post_type: Optional[str] = Form("normal"),
    mp_title: Optional[str] = Form(None),
    mp_price: Optional[str] = Form(None),
    mp_condition: Optional[str] = Form("Mới"),
):
    """Bắt đầu đăng bài — trả job_id để poll tiến độ."""
    all_accounts = read_json("accounts")
    selected_account_ids = [
        i.strip() for i in account_ids.split(",") if i.strip()
    ]
    selected_accounts = [
        a for a in all_accounts if a["id"] in selected_account_ids
    ]
    if not selected_accounts:
        raise HTTPException(400, "Không có tài khoản hợp lệ được chọn")

    all_groups = read_json("groups")
    selected_group_ids = [
        i.strip() for i in group_ids.split(",") if i.strip()
    ]
    selected_groups = [
        g for g in all_groups if g["id"] in selected_group_ids
    ]
    if not selected_groups:
        raise HTTPException(400, "Không có group hợp lệ được chọn")

    if post_type == "marketplace":
        if not mp_title or not mp_title.strip():
            raise HTTPException(400, "Tên mặt hàng không được để trống")
        if not mp_price or not mp_price.strip():
            raise HTTPException(400, "Giá bán không được để trống")

    image_paths: List[str] = []
    for img in images:
        if img and img.filename:
            ext = Path(img.filename).suffix
            filename = f"{uuid.uuid4()}{ext}"
            save_path = UPLOADS_DIR / filename
            with open(save_path, "wb") as f:
                f.write(await img.read())
            image_paths.append(str(save_path))

    if headless is not None:
        run_headless = headless.lower() in ("true", "1", "yes")
    else:
        run_headless = selected_accounts[0].get("headless", True)

    marketplace_data = None
    if post_type == "marketplace":
        marketplace_data = {
            "title": mp_title.strip(),
            "price": mp_price.strip(),
            "condition": (mp_condition or "Mới").strip(),
        }

    total = len(selected_accounts) * len(selected_groups)
    job_id = create_job("post", total)
    asyncio.create_task(
        _run_post_job(
            job_id, selected_accounts, selected_groups, content,
            image_paths, run_headless, marketplace_data,
        )
    )
    return {"job_id": job_id, "total": total}


@router.get("/jobs/{job_id}")
def get_post_job(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job không tồn tại")
    return job


@router.get("/history")
def get_history():
    posts = read_json("posts")
    return sorted(
        posts, key=lambda p: p.get("created_at", ""), reverse=True
    )


@router.patch("/history/{post_id}/post-url")
def update_result_post_url(
    post_id: str,
    result_index: int = Query(...),
    post_url: str = Query(...),
):
    posts = read_json("posts")
    post = next((p for p in posts if p["id"] == post_id), None)
    if not post:
        raise HTTPException(404, "Bản ghi không tồn tại")
    results = post.get("results") or []
    if result_index < 0 or result_index >= len(results):
        raise HTTPException(400, "Chỉ số kết quả không hợp lệ")
    results[result_index]["post_url"] = post_url.strip()
    write_json("posts", posts)
    return {
        "message": "Đã cập nhật link bài viết",
        "post_url": post_url.strip(),
    }


@router.delete("/history/{post_id}")
def delete_history(post_id: str):
    posts = read_json("posts")
    new_list = [p for p in posts if p["id"] != post_id]
    if len(new_list) == len(posts):
        raise HTTPException(404, "Bản ghi không tồn tại")
    write_json("posts", new_list)
    return {"message": "Đã xóa bản ghi"}
