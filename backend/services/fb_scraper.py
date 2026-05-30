"""
Scrape & delete Facebook posts for managed accounts.
Reuses session cookies from fb_poster.
"""
import logging
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

SESSIONS_DIR = Path(__file__).parent.parent / "data" / "sessions"
DEBUG_DIR = Path(__file__).parent.parent / "data" / "debug"
DEBUG_DIR.mkdir(parents=True, exist_ok=True)


async def _save_html_debug(html: str, label: str) -> None:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = DEBUG_DIR / f"{label}_{ts}.html"
    try:
        path.write_text(html, encoding="utf-8")
        logger.info("[Scraper] Debug HTML saved: %s (%d bytes)", path, len(html))
    except Exception as e:
        logger.warning("[Scraper] Không lưu được debug HTML: %s", e)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

ProgressCallback = Optional[Callable[[dict], None]]


def _session_path(account_id: str) -> Path:
    return SESSIONS_DIR / f"{account_id}.json"


async def _get_fb_user_id(page) -> Optional[str]:
    cookies = await page.context.cookies("https://www.facebook.com")
    return next((c["value"] for c in cookies if c["name"] == "c_user"), None)


async def _resolve_group_numeric_id(page, group_url: str) -> Optional[str]:
    """Return numeric group ID without navigating if already in URL."""
    m = re.search(r"/groups/(\d+)", group_url)
    if m:
        return m.group(1)
    # Vanity URL — need to load page and parse source
    try:
        await page.goto(group_url, wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(2000)
        m = re.search(r"/groups/(\d+)", page.url)
        if m:
            return m.group(1)
        gid = await page.evaluate(r"""() => {
            const html = document.documentElement.innerHTML;
            for (const p of [/"groupID":"(\d+)"/, /"group_id":"(\d+)"/, /groupID=(\d+)/]) {
                const m = html.match(p);
                if (m) return m[1];
            }
            return null;
        }""")
        return gid
    except Exception as e:
        logger.debug("Không lấy được group ID từ %s: %s", group_url, e)
        return None


def _parse_posts_from_html(html: str, group_id: str) -> list:
    """Parse posts from Facebook embedded JSON.

    Strategy: find "creation_time" immediately followed by the post "url"
    (within 400 chars), then look 40 kB before that anchor for the
    "text" field that contains the post body.
    """
    import json as _json

    posts: dict = {}

    # Step 1: Collect (pid, url, utime) via creation_time + url in JSON
    for m in re.finditer(r'"creation_time":(\d+)', html):
        ctime_ms = int(m.group(1)) * 1000
        nearby = html[m.start(): m.start() + 400]
        url_m = re.search(
            r'"url":"(https:[^"]*groups[^"]*posts[^"]*)"', nearby
        )
        if not url_m:
            continue
        raw_url = url_m.group(1).replace("\\/", "/")
        # Normalize về www.facebook.com
        raw_url = re.sub(
            r'https?://(web\.|m\.)?facebook\.com',
            'https://www.facebook.com',
            raw_url,
        )
        if f"/groups/{group_id}/posts/" not in raw_url:
            continue
        pid_m = re.search(r"/posts/(\d+)", raw_url)
        if not pid_m:
            continue
        pid = pid_m.group(1)
        url = raw_url if raw_url.endswith("/") else raw_url + "/"
        posts.setdefault(pid, {"url": url, "content": "", "utime": ctime_ms})

    # Step 2: For each post, find the creation_time anchor and look
    #         40 kB backwards for the longest "text" field (= post body).
    for pid, data in posts.items():
        ct_idx = -1
        search = 0
        while True:
            search = html.find('"creation_time":', search)
            if search == -1:
                break
            nearby = html[search: search + 400].replace("\\/", "/")
            if f"/posts/{pid}/" in nearby:
                ct_idx = search
                break
            search += 1

        if ct_idx == -1:
            continue

        chunk = html[max(0, ct_idx - 40000): ct_idx]
        texts = re.findall(r'"text":"((?:[^"\\]|\\.){100,})"', chunk)
        if not texts:
            continue
        raw = texts[-1]
        try:
            data["content"] = _json.loads(f'"{raw}"')
        except Exception:
            data["content"] = (
                raw.replace("\\n", "\n")
                .replace("\\t", "\t")
                .replace('\\"', '"')
            )

    return [
        {
            "postUrl": d["url"],
            "content": d["content"],
            "utime": d["utime"],
            "timeText": "",
        }
        for d in posts.values()
    ]


_EXTRACT_POSTS_JS = r"""
(groupId) => {
    const html = document.documentElement.innerHTML;
    const posts = {};

    // Step 1: find (pid, url, utime) via "creation_time" + nearby "url" in JSON.
    // Facebook stores them consecutively: "creation_time":N,...,"url":"groups/.../posts/PID/"
    const ctRe = /"creation_time":(\d+)/g;
    let m;
    while ((m = ctRe.exec(html)) !== null) {
        const ctimeMs = parseInt(m[1]) * 1000;
        const nearby = html.slice(m.index, m.index + 400);
        const um = nearby.match(
            /"url":"(https:\\\/\\\/www\.facebook\.com\\\/groups\\\/[^"]*\/posts\/(\d+)[^"]*)"/
        );
        if (!um) continue;
        const pid = um[2];
        const rawUrl = um[1].replace(/\\\//g, '/');
        if (!rawUrl.includes('/groups/' + groupId + '/posts/')) continue;
        const url = rawUrl.endsWith('/') ? rawUrl : rawUrl + '/';
        if (!posts[pid]) posts[pid] = { url, content: '', utime: ctimeMs };
    }

    // Step 2: for each post, look 40 kB BEFORE the creation_time anchor for
    // the "text" field that holds the post body (longest match = post content).
    for (const [pid, d] of Object.entries(posts)) {
        // Find the creation_time that is followed by this pid's URL
        let ctIdx = -1;
        let search = 0;
        while (true) {
            const idx = html.indexOf('"creation_time":', search);
            if (idx === -1) break;
            const nearby = html.slice(idx, idx + 400).replace(/\\\//g, '/');
            if (nearby.includes('/posts/' + pid + '/')) { ctIdx = idx; break; }
            search = idx + 1;
        }
        if (ctIdx === -1) continue;

        const chunk = html.slice(Math.max(0, ctIdx - 40000), ctIdx);
        // Find all "text":"..." values with 100+ chars
        const textRe = /"text":"((?:[^"\\]|\\.){100,})"/g;
        let lastText = null, tm;
        while ((tm = textRe.exec(chunk)) !== null) lastText = tm[1];
        if (!lastText) continue;
        try { d.content = JSON.parse('"' + lastText + '"'); }
        catch { d.content = lastText.replace(/\\n/g, '\n').replace(/\\t/g, '\t'); }
    }

    // Step 3: fill still-missing content from live DOM article elements
    const msgEls = [...document.querySelectorAll(
        '[data-ad-comet-preview="message"],[data-ad-preview="message"]'
    )];
    for (const el of msgEls) {
        const text = (el.innerText || '').trim();
        if (!text) continue;
        const article = el.closest('[role="article"]') || el;
        let pid = null;
        for (const a of article.querySelectorAll('a[href*="set=pcb."]')) {
            const mm = a.href.match(/set=pcb\.(\d+)/);
            if (mm) { pid = mm[1]; break; }
        }
        if (!pid) {
            for (const a of article.querySelectorAll('a[href*="/posts/"]')) {
                const mm = a.href.match(/\/posts\/(\d+)/);
                if (mm) { pid = mm[1]; break; }
            }
        }
        if (pid && posts[pid] && !posts[pid].content)
            posts[pid].content = text.slice(0, 2000);
    }

    return Object.entries(posts)
        .filter(([, d]) => d.url && (!groupId || d.url.includes('/groups/' + groupId + '/')))
        .map(([, d]) => ({
            postUrl: d.url,
            content: d.content || '',
            utime: d.utime,
            timeText: d.utime ? new Date(d.utime).toLocaleString('vi-VN') : '',
        }));
}
"""


async def _scrape_my_posts_in_group(
    page, group: dict, fb_user_id: Optional[str], max_scroll: int
) -> list:
    """Navigate to /groups/{id}/user/{uid}/, scroll to load posts, extract data."""
    from .fb_poster import _dismiss_cookie_banner

    group_url = group["url"]
    m = re.search(r"facebook\.com/groups/([^/?#]+)", group_url)
    group_identifier = m.group(1).rstrip("/") if m else None

    m_num = re.search(r"^\d+$", group_identifier or "")
    group_id = group_identifier if m_num else None
    if not group_id:
        m2 = re.search(r"/groups/(\d+)", group_url)
        group_id = m2.group(1) if m2 else group_identifier

    if group_identifier and fb_user_id:
        target = (
            f"https://www.facebook.com/groups/{group_identifier}"
            f"/user/{fb_user_id}/"
        )
    else:
        target = group_url

    gid = group_id or group_identifier or ""

    # ── Intercept GraphQL responses ────────────────────────────────────────
    # Scroll-triggered posts arrive via XHR, not embedded in page HTML.
    # We capture every /api/graphql response and parse post data from them.
    captured_bodies: list[str] = []

    async def _on_response(response):
        try:
            url_r = response.url
            if "graphql" not in url_r and "/api/" not in url_r:
                return
            ct = response.headers.get("content-type", "")
            if "json" not in ct and "javascript" not in ct and "text" not in ct:
                return
            body = await response.text()
            if '"creation_time"' in body or '"permalink_url"' in body:
                captured_bodies.append(body)
        except Exception:
            pass

    page.on("response", _on_response)
    # ──────────────────────────────────────────────────────────────────────

    logger.info("[Scraper] Điều hướng đến: %s", target)
    await page.goto(target, wait_until="domcontentloaded")
    await _dismiss_cookie_banner(page)

    # Chờ render ban đầu
    try:
        await page.wait_for_load_state("networkidle", timeout=20000)
    except Exception:
        await page.wait_for_timeout(5000)

    # Scroll từng bước — mỗi lần scroll kích hoạt GraphQL fetch mới
    prev_height = 0
    for i in range(max_scroll):
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        try:
            await page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
        await page.wait_for_timeout(2000)

        cur_height = await page.evaluate("document.body.scrollHeight")
        logger.debug(
            "[Scraper] Scroll %d/%d height=%d→%d | %s",
            i + 1, max_scroll, prev_height, cur_height, group["name"],
        )
        if cur_height == prev_height:
            logger.info(
                "[Scraper] Không có content mới sau scroll %d, dừng | %s",
                i + 1, group["name"],
            )
            break
        prev_height = cur_height

    # Chờ thêm để đảm bảo tất cả lazy-load xong
    await page.wait_for_timeout(3000)
    try:
        await page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass

    page.remove_listener("response", _on_response)

    logger.info(
        "[Scraper] URL: %s | title: %s | graphql_bodies=%d",
        page.url, await page.title(), len(captured_bodies),
    )

    # Lấy HTML SAU KHI đã scroll xong hoàn toàn
    html = await page.content()
    group_slug = re.sub(r"[^\w]", "_", group.get("name", "group"))[:40]
    await _save_html_debug(html, f"scraper_{group_slug}")

    # ── Parse từ tất cả nguồn, merge theo thứ tự ưu tiên ─────────────────

    merged: dict = {}  # postUrl → post dict

    def _merge(posts: list, label: str) -> None:
        for p in posts:
            url = p.get("postUrl", "")
            if not url:
                continue
            if url not in merged:
                merged[url] = p
            else:
                if p.get("content") and not merged[url].get("content"):
                    merged[url]["content"] = p["content"]
                if p.get("utime") and not merged[url].get("utime"):
                    merged[url]["utime"] = p["utime"]
                if p.get("timeText") and not merged[url].get("timeText"):
                    merged[url]["timeText"] = p["timeText"]
        logger.info(
            "[Scraper] %s: +%d bài → tổng %d | %s",
            label, len(posts), len(merged), group["name"],
        )

    # 1. GraphQL XHR responses (ưu tiên cao nhất — có đủ data nhất)
    gql_posts: list = []
    for body in captured_bodies:
        gql_posts.extend(_parse_posts_from_html(body, gid))
    _merge(gql_posts, "GraphQL")

    # 2. Embedded JSON trong page HTML
    html_posts = _parse_posts_from_html(html, gid)
    _merge(html_posts, "HTML")

    # 3. Live DOM via JS evaluate (lấy content từ rendered DOM)
    try:
        dom_posts = await page.evaluate(_EXTRACT_POSTS_JS, gid)
        _merge(dom_posts, "DOM-JS")
    except Exception as e:
        logger.warning("[Scraper] JS eval thất bại: %s", e)

    result = list(merged.values())
    logger.info(
        "[Scraper] Tổng cuối: %d bài | %s", len(result), group["name"]
    )
    return result


async def fetch_posts_for_accounts(
    accounts: list,
    groups: list,
    max_scroll: int = 5,
    headless: bool = True,
    on_progress: ProgressCallback = None,
) -> list:
    """Scrape each account's posts from the given groups."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return []

    from .fb_poster import _ensure_logged_in

    all_posts: list = []
    total = len(accounts) * len(groups)
    done = 0

    def _emit(account_email: str, label: str):
        if on_progress:
            on_progress({
                "done": done,
                "total": total,
                "results": all_posts[:],
                "current": {"account_email": account_email, "label": label},
            })

    for account in accounts:
        account_id = account.get("id", account["email"])
        session_file = _session_path(account_id)

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--no-sandbox",
                ],
            )
            ctx_kwargs = {
                "user_agent": USER_AGENT,
                "locale": "vi-VN",
                "viewport": {"width": 1280, "height": 900},
            }
            if session_file.exists():
                ctx_kwargs["storage_state"] = str(session_file)

            context = await browser.new_context(**ctx_kwargs)
            page = await context.new_page()

            try:
                login = await _ensure_logged_in(page, account, headless=headless)
                if not login["success"]:
                    logger.warning("[Scraper] Login thất bại: %s", account["email"])
                    done += len(groups)
                    _emit(account["email"], f"Đăng nhập thất bại: {login['message']}")
                    continue

                fb_user_id = await _get_fb_user_id(page)
                logger.info("[Scraper] uid=%s | %s", fb_user_id, account["email"])

                for group in groups:
                    _emit(account["email"], f"Đang quét: {group['name']}")
                    scraped = []
                    for attempt in range(2):
                        try:
                            scraped = await _scrape_my_posts_in_group(
                                page, group, fb_user_id, max_scroll
                            )
                            break
                        except Exception as e:
                            err = str(e)
                            if "Page crashed" in err and attempt == 0:
                                logger.warning(
                                    "[Scraper] Page crashed, mở page mới | %s",
                                    group["name"],
                                )
                                try:
                                    await page.close()
                                except Exception:
                                    pass
                                page = await context.new_page()
                                # chờ hệ thống giải phóng bộ nhớ
                                await page.wait_for_timeout(3000)
                            else:
                                logger.warning(
                                    "[Scraper] Lỗi quét %s: %s",
                                    group["name"], e,
                                )
                                break
                    for item in scraped:
                        all_posts.append({
                            "id": f"{account_id}::{item['postUrl']}",
                            "account_id": account_id,
                            "account_email": account["email"],
                            "group_id": group["id"],
                            "group_name": group["name"],
                            "group_url": group["url"],
                            "post_url": item["postUrl"],
                            "content": item["content"],
                            "utime": item["utime"],
                            "time_text": item["timeText"],
                        })
                    done += 1
                    _emit(account["email"], f"Xong: {group['name']}")

                await context.storage_state(path=str(session_file))
            except Exception as e:
                logger.error("[Scraper] Lỗi account %s: %s", account["email"], e)
                done += len(groups)
            finally:
                await browser.close()

    return all_posts




_FIND_MENU_BTN_JS = """(postId) => {
    const prefixes = [
        'Hành động với bài viết này',
        'Hành động cho bài viết này',
        'Hành động đối với bài viết này',
        'Actions for this post',
    ];
    const match = (lbl) => prefixes.some(k => lbl === k || lbl.startsWith(k));

    // Strategy 1: tìm qua link chứa post ID (chính xác nhất)
    if (postId) {
        for (const a of document.querySelectorAll(`a[href*="${postId}"]`)) {
            let node = a.parentElement;
            for (let i = 0; i < 30 && node; i++, node = node.parentElement) {
                for (const b of node.querySelectorAll('[role="button"]')) {
                    const lbl = (b.getAttribute('aria-label') || '').trim();
                    if (match(lbl)) {
                        b.scrollIntoView({ block: 'center' });
                        b.click();
                        return lbl;
                    }
                }
            }
        }
    }

    // Strategy 2: startsWith match toàn trang — lấy button đầu tiên tìm được
    for (const b of document.querySelectorAll('[role="button"]')) {
        const lbl = (b.getAttribute('aria-label') || '').trim();
        if (match(lbl)) {
            b.scrollIntoView({ block: 'center' });
            b.click();
            return lbl;
        }
    }

    // Debug info
    const links = postId
        ? [...document.querySelectorAll(`a[href*="${postId}"]`)].map(a => a.href.split('?')[0])
        : [];
    const actionBtns = [...document.querySelectorAll('[role="button"][aria-label]')]
        .map(b => b.getAttribute('aria-label'))
        .filter(l => l.includes('Hành động') || l.includes('Action'));
    return JSON.stringify({ links: links.slice(0, 3), actionBtns });
}"""


async def _delete_single_post(page, post_url: str) -> dict:
    """Navigate to post → click 3-dot → Xóa bài viết → confirm Xóa."""
    from .fb_poster import _dismiss_cookie_banner

    post_url = re.sub(
        r'https?://(web\.|m\.)?facebook\.com',
        'https://www.facebook.com', post_url,
    )
    logger.info("[Scraper] Xóa bài: %s", post_url)

    try:
        await page.goto(post_url, wait_until="domcontentloaded")
    except Exception as e:
        if "Page crashed" in str(e):
            await page.wait_for_timeout(3000)
            try:
                await page.goto(post_url, wait_until="domcontentloaded")
            except Exception as e2:
                return {"success": False, "message": f"Page crashed: {e2}"}
        else:
            return {"success": False, "message": str(e)}

    await page.wait_for_timeout(5000)
    try:
        await page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    await _dismiss_cookie_banner(page)

    pid_m = re.search(r'/posts/(\d+)|/permalink/(\d+)', post_url)
    post_id = (pid_m.group(1) or pid_m.group(2)) if pid_m else ""

    # ── Bước 1: Click nút 3 chấm — retry 3 lần, chờ 2s giữa mỗi lần ──────
    clicked_menu = None
    for attempt in range(3):
        if attempt > 0:
            await page.wait_for_timeout(2000)
        result = await page.evaluate(_FIND_MENU_BTN_JS, post_id)
        # Nếu trả về string JSON → chưa tìm được, log và retry
        if result and result.startswith('{'):
            logger.warning("[Scraper] Attempt %d: chưa tìm thấy nút 3 chấm | %s",
                           attempt + 1, result)
        elif result:
            clicked_menu = result
            break

    if not clicked_menu:
        return {"success": False, "message": "Không tìm thấy nút 3 chấm (không có quyền xóa)"}

    logger.info("[Scraper] Click 3 chấm: %s", clicked_menu)
    await page.wait_for_timeout(1500)

    # ── Bước 2: Click "Xóa bài viết" — retry 2 lần ───────────────────────
    deleted = None
    for attempt in range(2):
        if attempt > 0:
            await page.wait_for_timeout(1500)
        deleted = await page.evaluate("""() => {
            for (const el of document.querySelectorAll('[role="menuitem"]')) {
                const t = (el.innerText || '').trim();
                if (t === 'Xóa bài viết' || t === 'Delete post') { el.click(); return t; }
            }
            const items = [...document.querySelectorAll('[role="menuitem"]')]
                .map(m => (m.innerText || '').trim()).filter(Boolean);
            return items.length ? 'no-delete|' + items.join(',') : null;
        }""")
        if deleted and not deleted.startswith('no-delete'):
            break
        if deleted:
            logger.warning("[Scraper] Attempt %d: menu items=%s", attempt + 1, deleted)

    if not deleted or deleted.startswith('no-delete'):
        return {"success": False, "message": "Không tìm thấy tùy chọn 'Xóa bài viết'"}

    logger.info("[Scraper] Click: %s", deleted)
    await page.wait_for_timeout(2000)

    # ── Bước 3: Click "Xóa" trong dialog xác nhận — retry 3 lần ──────────
    confirmed = False
    for attempt in range(3):
        if attempt > 0:
            await page.wait_for_timeout(1500)
        confirmed = await page.evaluate("""() => {
            for (const d of document.querySelectorAll('[role="dialog"]')) {
                const btns = [...d.querySelectorAll('[role="button"], button')];
                const texts = btns.map(b => (b.innerText || '').trim());
                const hasCancel = texts.some(t => t === 'Hủy' || t === 'Cancel');
                const delBtn = btns.find(b => {
                    const t = (b.innerText || '').trim();
                    return t === 'Xóa' || t === 'Delete';
                });
                if (hasCancel && delBtn) { delBtn.click(); return true; }
            }
            return false;
        }""")
        if confirmed:
            break
        logger.warning("[Scraper] Attempt %d: chưa thấy confirm dialog", attempt + 1)

    if not confirmed:
        return {"success": False, "message": "Không tìm thấy nút xác nhận 'Xóa'"}

    await page.wait_for_timeout(4000)
    logger.info("[Scraper] ✅ Đã xóa bài: %s", post_url)
    return {"success": True, "message": "Đã xóa bài viết"}


async def delete_posts_for_accounts(
    items: list,
    accounts_map: dict,
    headless: bool = True,
    on_progress: ProgressCallback = None,
) -> list:
    """Delete posts grouped by account_id."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return [{"post_url": i["post_url"], "success": False, "message": "Playwright chưa cài"} for i in items]

    from .fb_poster import _ensure_logged_in

    by_account: dict = defaultdict(list)
    for item in items:
        by_account[item["account_id"]].append(item)

    all_results: list = []
    total = len(items)
    done = 0

    def _emit(account_email: str = "", group_name: str = ""):
        if on_progress:
            on_progress({
                "done": done,
                "total": total,
                "results": all_results[:],
                "current": {"account_email": account_email, "group_name": group_name},
            })

    for account_id, account_items in by_account.items():
        account = accounts_map.get(account_id)
        if not account:
            for item in account_items:
                all_results.append({
                    "post_url": item["post_url"],
                    "group_name": item.get("group_name", ""),
                    "account_email": item.get("account_email", account_id),
                    "success": False,
                    "message": "Không tìm thấy tài khoản",
                })
                done += 1
            continue

        session_file = _session_path(account_id)

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--no-sandbox",
                ],
            )
            ctx_kwargs = {
                "user_agent": USER_AGENT,
                "locale": "vi-VN",
                "viewport": {"width": 1280, "height": 900},
            }
            if session_file.exists():
                ctx_kwargs["storage_state"] = str(session_file)

            context = await browser.new_context(**ctx_kwargs)
            page = await context.new_page()

            try:
                login = await _ensure_logged_in(page, account, headless=headless)
                if not login["success"]:
                    for item in account_items:
                        all_results.append({
                            "post_url": item["post_url"],
                            "group_name": item.get("group_name", ""),
                            "account_email": account["email"],
                            "success": False,
                            "message": login["message"],
                        })
                        done += 1
                    continue

                for item in account_items:
                    _emit(account["email"], item.get("group_name", ""))
                    try:
                        res = await _delete_single_post(page, item["post_url"])
                    except Exception as e:
                        res = {"success": False, "message": str(e)}

                    all_results.append({
                        "post_url": item["post_url"],
                        "group_name": item.get("group_name", ""),
                        "account_email": account["email"],
                        **res,
                    })
                    done += 1
                    _emit(account["email"], item.get("group_name", ""))

                await context.storage_state(path=str(session_file))
            except Exception as e:
                logger.error("[Scraper] Lỗi xóa account %s: %s", account["email"], e)
            finally:
                await browser.close()

    return all_results
