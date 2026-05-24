import asyncio
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from services.fb_poster import post_to_multiple
from services.storage import read_json, write_json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/posts", tags=["posts"])

UPLOADS_DIR = Path(__file__).parent.parent / "data" / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/send")
async def send_post(
    content: str = Form(...),
    account_ids: str = Form(...),       # comma-separated IDs
    group_ids: str = Form(...),         # comma-separated IDs
    image: Optional[UploadFile] = File(None),
    headless: Optional[str] = Form(None),  # "true" | "false", override account setting
):
    """Post immediately to selected accounts × groups."""
    logger.info(
        "POST /posts/send | accounts=%s | groups=%s | content_len=%d | headless=%s",
        account_ids,
        group_ids,
        len(content),
        headless,
    )

    # Resolve accounts
    all_accounts = read_json("accounts")
    selected_account_ids = [i.strip() for i in account_ids.split(",") if i.strip()]
    selected_accounts = [a for a in all_accounts if a["id"] in selected_account_ids]
    if not selected_accounts:
        logger.warning("Không có tài khoản hợp lệ: ids=%s", account_ids)
        raise HTTPException(400, "Không có tài khoản hợp lệ được chọn")

    # Resolve groups
    all_groups = read_json("groups")
    selected_group_ids = [i.strip() for i in group_ids.split(",") if i.strip()]
    selected_groups = [g for g in all_groups if g["id"] in selected_group_ids]
    if not selected_groups:
        logger.warning("Không có group hợp lệ: ids=%s", group_ids)
        raise HTTPException(400, "Không có group hợp lệ được chọn")

    # Save uploaded image
    image_path = None
    if image and image.filename:
        ext = Path(image.filename).suffix
        filename = f"{uuid.uuid4()}{ext}"
        save_path = UPLOADS_DIR / filename
        with open(save_path, "wb") as f:
            f.write(await image.read())
        image_path = str(save_path)
        logger.info("Đã lưu ảnh upload: %s", image_path)

    # Headless: form override > account setting > default True
    if headless is not None:
        run_headless = headless.lower() in ("true", "1", "yes")
    else:
        run_headless = selected_accounts[0].get("headless", True)

    logger.info("Chạy Playwright | headless=%s | %d account(s) | %d group(s)", run_headless, len(selected_accounts), len(selected_groups))

    results = await post_to_multiple(
        accounts=selected_accounts,
        groups=selected_groups,
        content=content,
        image_path=image_path,
        headless=run_headless,
    )

    success_count = sum(1 for r in results if r["success"])
    logger.info("POST /posts/send hoàn tất | success=%d/%d", success_count, len(results))
    for r in results:
        logger.info(
            "  → %s | %s | success=%s | %s",
            r.get("account_email"), r.get("group_name"), r.get("success"), r.get("message"),
        )

    # Save to history
    posts_history = read_json("posts")
    post_record = {
        "id": str(uuid.uuid4()),
        "content": content,
        "image_path": image_path,
        "created_at": datetime.now().isoformat(),
        "type": "immediate",
        "results": results,
        "total": len(results),
        "success_count": success_count,
    }
    posts_history.append(post_record)
    write_json("posts", posts_history)

    return post_record


@router.get("/history")
def get_history():
    posts = read_json("posts")
    return sorted(posts, key=lambda p: p.get("created_at", ""), reverse=True)


@router.delete("/history/{post_id}")
def delete_history(post_id: str):
    posts = read_json("posts")
    new_list = [p for p in posts if p["id"] != post_id]
    if len(new_list) == len(posts):
        raise HTTPException(404, "Bản ghi không tồn tại")
    write_json("posts", new_list)
    return {"message": "Đã xóa bản ghi"}
