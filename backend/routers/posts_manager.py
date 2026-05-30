import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, Form, HTTPException

from services.fb_scraper import delete_posts_for_accounts, fetch_posts_for_accounts
from services.job_store import (
    complete_job, create_job, fail_job, get_job, update_job_progress,
)
from services.storage import read_json, write_json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/posts-manager", tags=["posts-manager"])


@router.get("/saved-posts")
def get_saved_posts():
    return read_json("managed_posts")


# ── Fetch ─────────────────────────────────────────────────────────────────────

def _merge_saved_posts(new_posts: list) -> list:
    """Thêm bài mới vào danh sách đã lưu, bỏ qua nếu post_url đã tồn tại."""
    saved = read_json("managed_posts")
    existing_urls = {p["post_url"] for p in saved if p.get("post_url")}
    added = 0
    for p in new_posts:
        url = p.get("post_url", "")
        if url and url not in existing_urls:
            saved.append(p)
            existing_urls.add(url)
            added += 1
    if added:
        write_json("managed_posts", saved)
    logger.info("[PostsManager] Thêm %d bài mới (bỏ qua %d duplicate)",
                added, len(new_posts) - added)
    return saved


async def _run_fetch_job(
    job_id: str, accounts: list, groups: list, headless: bool
):
    def on_progress(data: dict):
        update_job_progress(
            job_id,
            data.get("done", 0),
            data.get("total", 1),
            data.get("results", []),
            data.get("current"),
        )

    try:
        posts = await fetch_posts_for_accounts(
            accounts=accounts,
            groups=groups,
            headless=headless,
            on_progress=on_progress,
        )
        merged = _merge_saved_posts(posts)
        complete_job(job_id, {"posts": merged, "count": len(merged)})
    except Exception as e:
        logger.exception("Fetch posts job failed: %s", e)
        fail_job(job_id, str(e))


@router.post("/fetch")
async def start_fetch(
    account_ids: str = Form(...),
    group_ids: str = Form(...),
    headless: Optional[str] = Form("true"),
):
    sel_account_ids = [i.strip() for i in account_ids.split(",") if i.strip()]
    sel_group_ids = [i.strip() for i in group_ids.split(",") if i.strip()]

    all_accounts = read_json("accounts")
    all_groups = read_json("groups")
    accounts = [a for a in all_accounts if a["id"] in sel_account_ids]
    groups = [g for g in all_groups if g["id"] in sel_group_ids]

    if not accounts:
        raise HTTPException(400, "Không có tài khoản hợp lệ")
    if not groups:
        raise HTTPException(400, "Không có nhóm hợp lệ")

    run_headless = headless is None or headless.lower() in ("true", "1", "yes")
    total = len(accounts) * len(groups)
    job_id = create_job("fetch_posts", total)
    asyncio.create_task(_run_fetch_job(job_id, accounts, groups, run_headless))
    return {"job_id": job_id, "total": total}


@router.get("/jobs/{job_id}")
def get_manager_job(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job không tồn tại")
    return job


# ── Delete ────────────────────────────────────────────────────────────────────

async def _run_delete_job(job_id: str, items: list, accounts_map: dict, headless: bool):
    def on_progress(data: dict):
        update_job_progress(
            job_id,
            data.get("done", 0),
            data.get("total", 1),
            data.get("results", []),
            data.get("current"),
        )

    try:
        results = await delete_posts_for_accounts(
            items=items,
            accounts_map=accounts_map,
            headless=headless,
            on_progress=on_progress,
        )
        success_count = sum(1 for r in results if r.get("success"))

        # Remove successfully deleted posts from saved JSON
        deleted_urls = {r["post_url"] for r in results if r.get("success")}
        if deleted_urls:
            saved = read_json("managed_posts")
            write_json(
                "managed_posts",
                [p for p in saved if p.get("post_url") not in deleted_urls],
            )

        complete_job(job_id, {
            "results": results,
            "success_count": success_count,
            "total": len(results),
        })
    except Exception as e:
        logger.exception("Delete posts job failed: %s", e)
        fail_job(job_id, str(e))


@router.post("/delete")
async def delete_posts(
    items: str = Form(...),
    headless: Optional[str] = Form("true"),
):
    try:
        item_list = json.loads(items)
    except Exception:
        raise HTTPException(400, "Danh sách bài viết không hợp lệ (JSON)")

    if not item_list:
        raise HTTPException(400, "Chọn ít nhất 1 bài viết")

    all_accounts = read_json("accounts")
    accounts_map = {a["id"]: a for a in all_accounts}

    for item in item_list:
        if item.get("account_id") not in accounts_map:
            raise HTTPException(400, f"Tài khoản không tồn tại: {item.get('account_id')}")

    run_headless = headless is None or headless.lower() in ("true", "1", "yes")
    job_id = create_job("delete_posts", len(item_list))
    asyncio.create_task(_run_delete_job(job_id, item_list, accounts_map, run_headless))
    return {"job_id": job_id, "total": len(item_list)}
