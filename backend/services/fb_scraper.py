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


def _parse_urls_from_html(html: str, group_id: str) -> list:
    """Extract post URLs from Facebook's embedded JSON (permalink_url field)."""
    raw_urls = re.findall(r'"permalink_url":"(https:[^"]+)"', html)
    needle = f"/groups/{group_id}/posts/"
    seen: set = set()
    urls = []
    for raw in raw_urls:
        url = raw.replace("\\/", "/")  # noqa: W605
        if needle not in url:
            continue
        # Normalize trailing slash
        if not url.endswith("/"):
            url += "/"
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


_EXTRACT_POSTS_JS = r"""
(groupId) => {
    function cleanUrl(href) {
        try {
            const u = new URL(href);
            // accept /posts/{id} and /permalink/{id}
            if (/\/(posts|permalink)\/\d+\/?$/.test(u.pathname) &&
                u.pathname.includes('/groups/')) {
                let p = u.pathname;
                if (!p.endsWith('/')) p += '/';
                return u.origin + p;
            }
        } catch {}
        return null;
    }

    const results = [];
    const seenUrl = new Set();

    // Strategy: find content divs, walk up to find the post container + link
    const msgEls = [
        ...document.querySelectorAll(
            '[data-ad-comet-preview="message"],[data-ad-preview="message"]'
        )
    ];

    for (const el of msgEls) {
        const content = (el.innerText || '').trim().slice(0, 600);
        if (!content) continue;

        // Walk up to find a /posts/ link
        let postUrl = null;
        let node = el.parentElement;
        for (let depth = 0; depth < 30 && node; depth++, node = node.parentElement) {
            const links = node.querySelectorAll('a[href*="/posts/"],a[href*="/permalink/"]');
            for (const a of links) {
                const url = cleanUrl(a.href);
                if (url && url.includes('/groups/' + groupId + '/')) {
                    postUrl = url;
                    break;
                }
            }
            if (postUrl) break;
        }

        if (!postUrl || seenUrl.has(postUrl)) continue;
        seenUrl.add(postUrl);

        // Try to get timestamp
        let utime = null, timeText = '';
        const abbrEl = (el.closest('[role="article"]') || document)
            .querySelector('abbr[data-utime]');
        if (abbrEl) {
            utime = parseInt(abbrEl.getAttribute('data-utime')) * 1000;
            timeText = abbrEl.title || abbrEl.innerText || '';
        }

        results.push({ postUrl, content, utime, timeText });
    }
    return results;
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

    logger.info("[Scraper] Điều hướng đến: %s", target)
    await page.goto(target, wait_until="domcontentloaded")
    await _dismiss_cookie_banner(page)

    # Wait for initial render
    try:
        await page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        await page.wait_for_timeout(4000)

    # Scroll 3 times to load more posts
    for i in range(3):
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        try:
            await page.wait_for_load_state("networkidle", timeout=6000)
        except Exception:
            await page.wait_for_timeout(2500)
        logger.debug("[Scraper] Scroll %d/3 | %s", i + 1, group["name"])

    logger.info(
        "[Scraper] URL: %s | title: %s", page.url, await page.title()
    )

    # Primary: JS evaluation extracts URL+content from live DOM
    dom_posts = []
    try:
        dom_posts = await page.evaluate(_EXTRACT_POSTS_JS, group_id or "")
        logger.info(
            "[Scraper] DOM: %d bài | %s", len(dom_posts), group["name"]
        )
    except Exception as e:
        logger.warning("[Scraper] JS eval thất bại: %s", e)

    # Fallback: extract URLs from embedded JSON then return URL-only entries
    html = await page.content()
    group_slug = re.sub(r"[^\w]", "_", group.get("name", "group"))[:40]
    await _save_html_debug(html, f"scraper_{group_slug}")

    if dom_posts:
        return dom_posts

    logger.info("[Scraper] Dùng fallback HTML parsing | %s", group["name"])
    html_urls = _parse_urls_from_html(html, group_id or group_identifier or "")
    posts = [
        {"postUrl": u, "content": "", "utime": None, "timeText": ""}
        for u in html_urls
    ]
    logger.info("[Scraper] HTML: %d bài | %s", len(posts), group["name"])
    return posts


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
                args=["--disable-blink-features=AutomationControlled"],
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
                    try:
                        scraped = await _scrape_my_posts_in_group(
                            page, group, fb_user_id, max_scroll
                        )
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
                    except Exception as e:
                        logger.warning("[Scraper] Lỗi quét %s: %s", group["name"], e)
                    done += 1
                    _emit(account["email"], f"Xong: {group['name']}")

                await context.storage_state(path=str(session_file))
            except Exception as e:
                logger.error("[Scraper] Lỗi account %s: %s", account["email"], e)
                done += len(groups)
            finally:
                await browser.close()

    return all_posts


async def _delete_single_post(page, post_url: str) -> dict:
    """Delete one Facebook post by navigating to it and using the action menu."""
    from .fb_poster import _dismiss_cookie_banner

    logger.info("[Scraper] Xóa bài: %s", post_url)
    await page.goto(post_url, wait_until="domcontentloaded")
    await page.wait_for_timeout(4000)
    await _dismiss_cookie_banner(page)

    # Open the 3-dot action menu on the post
    menu_selectors = [
        'div[role="article"] div[aria-label="Hành động cho bài viết này"]',
        'div[role="article"] div[aria-label="Actions for this post"]',
        'div[role="article"] div[aria-label*="Hành động"]',
        'div[role="article"] div[aria-label*="Action"]',
    ]
    clicked_menu = False
    for sel in menu_selectors:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=3000):
                await btn.click()
                clicked_menu = True
                break
        except Exception:
            continue

    if not clicked_menu:
        try:
            found = await page.evaluate("""() => {
                const art = document.querySelector('div[role="article"]');
                if (!art) return false;
                for (const b of [...art.querySelectorAll('div[role="button"]')].reverse()) {
                    const label = b.getAttribute('aria-label') || '';
                    if (label.includes('Hành động') || label.includes('Action') || label.includes('More')) {
                        b.click(); return true;
                    }
                }
                return false;
            }""")
            if found:
                clicked_menu = True
                await page.wait_for_timeout(1500)
        except Exception:
            pass

    if not clicked_menu:
        return {"success": False, "message": "Không tìm thấy menu bài viết (không có quyền xóa)"}

    await page.wait_for_timeout(1500)

    delete_selectors = [
        'div[role="menuitem"]:has-text("Xóa bài viết")',
        'div[role="menuitem"]:has-text("Delete post")',
        'div[role="menu"] span:has-text("Xóa bài viết")',
        'div[role="menu"] span:has-text("Delete post")',
    ]
    clicked_delete = False
    for sel in delete_selectors:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=2000):
                await btn.click()
                clicked_delete = True
                break
        except Exception:
            continue

    if not clicked_delete:
        return {"success": False, "message": "Không tìm thấy tùy chọn 'Xóa bài viết'"}

    await page.wait_for_timeout(2000)

    confirm_selectors = [
        'div[role="dialog"] div[aria-label="Xóa"][role="button"]',
        'div[role="dialog"] div[role="button"]:has-text("Xóa")',
        'div[role="dialog"] button:has-text("Xóa")',
        'div[role="dialog"] div[role="button"]:has-text("Delete")',
        'div[role="dialog"] button:has-text("Delete")',
    ]
    for sel in confirm_selectors:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=3000):
                await btn.click()
                await page.wait_for_timeout(3000)
                logger.info("[Scraper] Đã xóa bài: %s", post_url)
                return {"success": True, "message": "Đã xóa bài viết"}
        except Exception:
            continue

    return {"success": False, "message": "Không tìm thấy nút xác nhận xóa"}


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
                args=["--disable-blink-features=AutomationControlled"],
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
