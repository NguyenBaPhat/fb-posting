"""
Facebook Group Auto-Poster using Playwright.
Tự động đăng nhập, lưu session, và đăng bài lên group.
"""
import asyncio
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

ProgressCallback = Optional[Callable[[dict], None]]

logger = logging.getLogger(__name__)

UPLOADS_DIR = Path(__file__).parent.parent / "data" / "uploads"
SESSIONS_DIR = Path(__file__).parent.parent / "data" / "sessions"
DEBUG_DIR = Path(__file__).parent.parent / "data" / "debug"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
DEBUG_DIR.mkdir(parents=True, exist_ok=True)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def _session_path(account_id: str) -> Path:
    return SESSIONS_DIR / f"{account_id}.json"


async def _save_debug(page, account_id: str, step: str) -> None:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = DEBUG_DIR / f"{account_id}_{step}_{ts}.png"
    try:
        await page.screenshot(path=str(path), full_page=True)
        logger.info("[FB] Debug screenshot: %s", path)
    except Exception as e:
        logger.warning("[FB] Không chụp được screenshot: %s", e)


async def _save_html_debug(html: str, label: str) -> None:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = DEBUG_DIR / f"{label}_{ts}.html"
    try:
        path.write_text(html, encoding="utf-8")
        logger.info("[FB] Debug HTML saved: %s (%d bytes)", path, len(html))
    except Exception as e:
        logger.warning("[FB] Không lưu được debug HTML: %s", e)


async def _log_page_state(page, step: str) -> None:
    try:
        info = await page.evaluate("""() => {
            const els = [...document.querySelectorAll('input, button, [role="button"]')].slice(0, 25);
            return {
                url: location.href,
                title: document.title,
                elements: els.map(el => ({
                    tag: el.tagName,
                    type: el.type || '',
                    name: el.name || '',
                    id: el.id || '',
                    aria: el.getAttribute('aria-label') || '',
                    text: el.type === 'password' ? '***' : (el.innerText || el.value || '').trim().slice(0, 40),
                    visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length),
                })),
            };
        }""")
        logger.info("[FB] DOM [%s] url=%s title=%s", step, info.get("url"), info.get("title"))
        for el in info.get("elements", []):
            logger.info(
                "[FB]   <%s> type=%s name=%s id=%s visible=%s text=%r aria=%s",
                el["tag"], el["type"], el["name"], el["id"],
                el["visible"], el["text"], el["aria"],
            )
    except Exception as e:
        logger.warning("[FB] Không đọc được DOM [%s]: %s", step, e)


async def _dismiss_cookie_banner(page) -> None:
    selectors = [
        'button[data-cookiebanner="accept_button"]',
        'button:has-text("Allow all cookies")',
        'button:has-text("Cho phép tất cả cookie")',
        'button:has-text("Accept All")',
        'button:has-text("Chấp nhận")',
    ]
    for sel in selectors:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=2000):
                await btn.click()
                await page.wait_for_timeout(1000)
                return
        except Exception:
            continue


async def _has_fb_session(page) -> bool:
    cookies = await page.context.cookies("https://www.facebook.com")
    return any(c["name"] == "c_user" for c in cookies)


async def _fill_first_visible(page, selectors: list[str], value: str, step: str = "fill") -> bool:
    for sel in selectors:
        try:
            loc = page.locator(sel)
            count = await loc.count()
            if count == 0:
                logger.debug("[FB] %s | selector=%s | count=0", step, sel)
                continue
            elem = loc.first
            visible = await elem.is_visible(timeout=3000)
            logger.debug("[FB] %s | selector=%s | count=%d | visible=%s", step, sel, count, visible)
            if visible:
                await elem.click()
                await elem.fill(value)
                logger.info("[FB] %s OK | selector=%s", step, sel)
                return True
        except Exception as e:
            logger.debug("[FB] %s FAIL | selector=%s | %s", step, sel, e)
            continue
    logger.error("[FB] %s | không tìm thấy element | url=%s", step, page.url)
    return False


async def _click_first_visible(page, selectors: list[str], step: str = "click") -> bool:
    for sel in selectors:
        try:
            loc = page.locator(sel)
            count = await loc.count()
            if count == 0:
                logger.debug("[FB] %s | selector=%s | count=0", step, sel)
                continue
            elem = loc.first
            visible = await elem.is_visible(timeout=3000)
            logger.debug("[FB] %s | selector=%s | count=%d | visible=%s", step, sel, count, visible)
            if visible:
                await elem.click()
                logger.info("[FB] %s OK | selector=%s", step, sel)
                return True
        except Exception as e:
            logger.debug("[FB] %s FAIL | selector=%s | %s", step, sel, e)
            continue
    logger.error("[FB] %s | không tìm thấy element | url=%s", step, page.url)
    return False


async def _submit_login(page) -> bool:
    """Thử nhiều cách submit form đăng nhập Facebook."""
    login_btn_selectors = [
        'motion.div[role="button"][aria-label="Đăng nhập"]',
        'div[role="button"][aria-label="Đăng nhập"]',
        'div[role="button"][aria-label="Log in"]',
        'div[role="button"]:has-text("Đăng nhập")',
        '#loginbutton',
        'button#loginbutton',
        'input#loginbutton',
        'button[name="login"]',
        'input[name="login"]',
        'button[type="submit"]',
        'input[type="submit"]',
        '[data-testid="royal-login-button"]',
        'button:has-text("Log in")',
        'button:has-text("Đăng nhập")',
    ]

    if await _click_first_visible(page, login_btn_selectors, step="login_btn"):
        return True

    try:
        submitted = await page.evaluate("""() => {
            const form = document.querySelector('form');
            if (form) { form.requestSubmit(); return 'form'; }
            const btn = document.querySelector('input[type="submit"], button[type="submit"]');
            if (btn) { btn.click(); return 'submit'; }
            return null;
        }""")
        if submitted:
            logger.info("[FB] login_btn OK | fallback JS submit (%s)", submitted)
            return True
    except Exception as e:
        logger.debug("[FB] login JS submit FAIL | %s", e)

    pass_selectors = ['input[name="pass"]', 'input#pass', 'input[type="password"]']
    for sel in pass_selectors:
        try:
            elem = page.locator(sel).first
            if await elem.is_visible(timeout=2000):
                await elem.press("Enter")
                logger.info("[FB] login_btn OK | fallback Enter trên %s", sel)
                return True
        except Exception as e:
            logger.debug("[FB] login Enter FAIL | selector=%s | %s", sel, e)

    return False


async def _get_login_error(page) -> Optional[str]:
    """Đọc thông báo lỗi thật trên trang login (không bắt nhãn form)."""
    try:
        err = await page.evaluate("""() => {
            const patterns = [
                /mật khẩu.*không chính xác/i,
                /password.*incorrect/i,
                /wrong password/i,
                /sai mật khẩu/i,
                /tài khoản.*không tồn tại/i,
                /couldn't find your account/i,
                /could not find your account/i,
                /không tìm thấy tài khoản/i,
                /too many attempts/i,
                /quá nhiều lần thử/i,
            ];
            const check = (text) => {
                const t = (text || '').trim();
                if (t.length < 12 || t.length > 180) return null;
                return patterns.some(p => p.test(t)) ? t : null;
            };
            for (const el of document.querySelectorAll(
                '[role="alert"], [data-testid="royal_login_error"], ._9ay7'
            )) {
                const hit = check(el.innerText);
                if (hit) return hit;
            }
            for (const el of document.querySelectorAll('motion.div, div, span')) {
                const t = (el.innerText || '').trim();
                if (el.children.length > 2) continue;
                const hit = check(t);
                if (hit) return hit;
            }
            return null;
        }""")
        return err
    except Exception:
        return None


async def _is_login_loading(page) -> bool:
    try:
        return await page.evaluate("""() => {
            if (document.querySelector('[role="progressbar"], [aria-busy="true"]')) return true;
            const btn = document.querySelector('div[role="button"][aria-label="Đăng nhập"]');
            if (btn && btn.querySelector('svg, [role="progressbar"]')) return true;
            return false;
        }""")
    except Exception:
        return False


MANUAL_2FA_TIMEOUT_MS = 300000  # 5 phút chờ xác minh 2FA thủ công


def _is_2fa_url(url: str) -> bool:
    u = url.lower()
    return "checkpoint" in u or "two_step" in u or "two-factor" in u


async def _wait_manual_2fa(page, timeout_ms: int = MANUAL_2FA_TIMEOUT_MS) -> bool:
    """Giữ trình duyệt mở, chờ user hoàn thành 2FA thủ công."""
    logger.warning(
        "[FB] ⚠️ Facebook yêu cầu xác minh 2 bước. "
        "Vui lòng hoàn thành trong cửa sổ Chrome (tối đa %d phút)...",
        timeout_ms // 60000,
    )
    elapsed = 0
    interval = 3000
    while elapsed < timeout_ms:
        if await _has_fb_session(page):
            logger.info("[FB] ✅ Xác minh 2FA thành công sau %ds | url=%s", elapsed // 1000, page.url)
            return True
        url = page.url
        if not _is_2fa_url(url) and "login" not in url.lower():
            await page.wait_for_timeout(2000)
            if await _has_fb_session(page):
                logger.info("[FB] ✅ Đăng nhập thành công sau xác minh | url=%s", page.url)
                return True
        if elapsed > 0 and elapsed % 15000 == 0:
            logger.info("[FB] Đang chờ bạn xác minh 2FA... (%ds / %ds)", elapsed // 1000, timeout_ms // 1000)
        await page.wait_for_timeout(interval)
        elapsed += interval
    logger.warning("[FB] Hết thời gian chờ xác minh 2FA thủ công")
    return False


async def _wait_login_success(page, headless: bool = True, timeout_ms: int = 45000) -> bool:
    """Chờ đăng nhập thành công. c_user là httpOnly — đọc qua context cookies."""
    logger.info("[FB] Chờ đăng nhập thành công (timeout=%ds)...", timeout_ms // 1000)
    await page.wait_for_timeout(2000)
    elapsed = 2000
    interval = 1000
    while elapsed < timeout_ms:
        if await _has_fb_session(page):
            logger.info("[FB] Cookie c_user detected sau %dms | url=%s", elapsed, page.url)
            return True
        url = page.url
        if _is_2fa_url(url):
            if not headless:
                return await _wait_manual_2fa(page)
            logger.warning("[FB] Phát hiện checkpoint/2FA (headless) | url=%s", url[:120])
            return False
        if await _is_login_loading(page):
            logger.debug("[FB] Login đang loading... (%dms)", elapsed)
        elif elapsed >= 4000:
            fb_err = await _get_login_error(page)
            if fb_err:
                logger.warning("[FB] Facebook báo lỗi: %s", fb_err)
                return False
        if elapsed > 5000 and "login" not in url.lower():
            logger.info("[FB] Đã rời trang login | url=%s — chờ cookie...", url)
        await page.wait_for_timeout(interval)
        elapsed += interval
    logger.warning(
        "[FB] Hết thời gian chờ login | url=%s | has_session=%s",
        page.url, await _has_fb_session(page),
    )
    return False


async def _ensure_logged_in(page, account: dict, headless: bool = True) -> dict:
    """Đăng nhập Facebook nếu chưa có session. Trả về {success, message}."""
    account_id = account.get("id", account["email"])

    await page.goto("https://www.facebook.com/", wait_until="domcontentloaded")
    await page.wait_for_timeout(2000)
    await _dismiss_cookie_banner(page)

    if await _has_fb_session(page):
        logger.info(f"[FB] Đã có session: {account['email']}")
        return {"success": True, "message": "Đã đăng nhập (session)"}

    logger.info(f"[FB] Đăng nhập tài khoản: {account['email']}")
    await page.goto("https://www.facebook.com/login", wait_until="domcontentloaded")
    await page.wait_for_timeout(3000)
    await _dismiss_cookie_banner(page)
    logger.info("[FB] Trang login | url=%s", page.url)
    await _log_page_state(page, "login_page")

    email_selectors = [
        'input[name="email"]',
        'input#email',
        'input[autocomplete="username"]',
        'input[type="text"]',
    ]
    pass_selectors = [
        'input[name="pass"]',
        'input#pass',
        'input[type="password"]',
    ]

    if not await _fill_first_visible(page, email_selectors, account["email"], step="email"):
        await _log_page_state(page, "email_not_found")
        await _save_debug(page, account_id, "email_not_found")
        return {"success": False, "message": "Không tìm thấy ô nhập email/số điện thoại."}

    if not await _fill_first_visible(page, pass_selectors, account["password"], step="password"):
        await _log_page_state(page, "password_not_found")
        await _save_debug(page, account_id, "password_not_found")
        return {"success": False, "message": "Không tìm thấy ô nhập mật khẩu."}

    if not await _submit_login(page):
        await _log_page_state(page, "login_btn_not_found")
        await _save_debug(page, account_id, "login_btn_not_found")
        return {"success": False, "message": "Không tìm thấy nút đăng nhập."}

    logger.info("[FB] Đã submit login, chờ xác nhận... (headless=%s)", headless)

    if await _wait_login_success(page, headless=headless):
        session_file = _session_path(account_id)
        await page.context.storage_state(path=str(session_file))
        logger.info("[FB] Đăng nhập thành công, đã lưu session: %s | url=%s", account['email'], page.url)
        return {"success": True, "message": "Đăng nhập thành công"}

    current_url = page.url
    fb_err = await _get_login_error(page)

    # Còn trang 2FA + hiện trình duyệt → thử chờ thêm (phòng khi miss trong vòng lặp ngắn)
    if _is_2fa_url(current_url) and not headless:
        logger.info("[FB] Thử chờ xác minh 2FA thủ công lần nữa...")
        if await _wait_manual_2fa(page):
            session_file = _session_path(account_id)
            await page.context.storage_state(path=str(session_file))
            logger.info("[FB] Đăng nhập thành công sau 2FA thủ công: %s", account['email'])
            return {"success": True, "message": "Đăng nhập thành công (sau xác minh 2 bước)"}

    await _log_page_state(page, "login_failed")
    await _save_debug(page, account_id, "login_failed")
    if fb_err:
        return {"success": False, "message": f"Facebook: {fb_err}"}
    if _is_2fa_url(current_url):
        if headless:
            return {
                "success": False,
                "message": "Tài khoản yêu cầu xác minh 2 bước. Chọn 'Hiện trình duyệt' khi đăng bài để xử lý thủ công.",
            }
        return {
            "success": False,
            "message": "Hết thời gian chờ xác minh 2 bước. Thử lại và hoàn thành xác minh trong cửa sổ Chrome.",
        }
    if "login" in current_url.lower():
        return {"success": False, "message": "Đăng nhập thất bại. Kiểm tra SĐT/email và mật khẩu."}
    return {"success": False, "message": f"Đăng nhập không thành công. URL hiện tại: {current_url}"}


async def _ensure_joined_group(page) -> None:
    """Bấm Tham gia nhóm nếu tài khoản chưa là thành viên."""
    join_selectors = [
        'div[role="button"][aria-label="Tham gia nhóm"]',
        'div[aria-label="Tham gia nhóm"]',
        'div[role="button"]:has-text("Tham gia nhóm")',
        'div[role="button"]:has-text("Join group")',
        'div[aria-label="Join group"]',
        'button:has-text("Tham gia nhóm")',
    ]
    if await _click_first_visible(page, join_selectors, step="join_group"):
        logger.info("[FB] Đã bấm Tham gia nhóm — chờ trang tải lại...")
        await page.wait_for_timeout(5000)
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await page.wait_for_timeout(2000)


async def _open_group_composer(page) -> bool:
    """Mở ô soạn bài viết trên trang group."""
    composer_selectors = [
        '[data-testid="group-composer-prompt"]',
        'div[role="button"]:has-text("Bạn viết gì đi")',
        'div[role="button"]:has-text("Bạn viết gì đi...")',
        'div[role="button"]:has-text("Viết gì đó")',
        'div:has-text("Bạn viết gì đi")',
        'span:has-text("Bạn viết gì đi")',
        'div[role="button"]:has-text("Write something")',
        'div[aria-label="Tạo bài viết"]',
        'div[aria-label="Create a post"]',
        'div[aria-label="Write something"]',
    ]
    if await _click_first_visible(page, composer_selectors, step="composer"):
        return True

    for text in ("Bạn viết gì đi", "Viết gì đó", "Write something", "What's on your mind"):
        try:
            loc = page.get_by_text(text, exact=False).first
            if await loc.is_visible(timeout=3000):
                await loc.click()
                logger.info("[FB] composer OK | get_by_text(%r)", text)
                return True
        except Exception as e:
            logger.debug("[FB] composer get_by_text(%r) FAIL | %s", text, e)

    for sel in (
        'div[contenteditable="true"][role="textbox"]',
        'div[contenteditable="true"][data-lexical-editor="true"]',
        'div[contenteditable="true"]',
    ):
        try:
            elem = page.locator(sel).first
            if await elem.is_visible(timeout=3000):
                await elem.click()
                logger.info("[FB] composer OK | click trực tiếp %s", sel)
                return True
        except Exception as e:
            logger.debug("[FB] composer direct %s FAIL | %s", sel, e)

    return False


async def _wait_image_uploaded(page, timeout_ms: int = 45000) -> bool:
    """Chờ Facebook xử lý xong ảnh đính kèm."""
    indicators = [
        'div[role="dialog"] img[src^="blob:"]',
        'div[role="dialog"] img[src^="https://"]',
        '[aria-label*="Xóa ảnh"]',
        '[aria-label*="Remove"]',
        '[aria-label*="remove photo"]',
        'div[role="dialog"] [aria-label*="Ảnh đã tải"]',
    ]
    deadline = timeout_ms
    step = 1500
    elapsed = 0
    while elapsed < deadline:
        for sel in indicators:
            try:
                loc = page.locator(sel).first
                if await loc.is_visible(timeout=500):
                    logger.info("[FB] Ảnh đã hiển thị preview | %s", sel)
                    return True
            except Exception:
                continue
        await page.wait_for_timeout(step)
        elapsed += step
    logger.warning("[FB] Hết thời gian chờ upload ảnh (%ds)", timeout_ms // 1000)
    return False


async def _attach_images_to_composer(page, image_paths: list[str]) -> bool:
    """Đính kèm nhiều ảnh vào dialog soạn bài group."""
    abs_paths = [str(Path(p).resolve()) for p in image_paths if Path(p).is_file()]
    if not abs_paths:
        logger.error("[FB] Không có file ảnh hợp lệ")
        return False

    photo_btn_selectors = [
        'div[role="dialog"] div[aria-label="Ảnh/video"]',
        'div[role="dialog"] div[aria-label="Photo/video"]',
        'div[role="dialog"] div[aria-label="Photo/Video"]',
        'div[aria-label="Ảnh/video"]',
        'div[aria-label="Photo/video"]',
        'div[aria-label="Photo/Video"]',
        'div[role="button"]:has-text("Ảnh")',
        'span:has-text("Ảnh/video")',
    ]
    file_input_selectors = [
        'div[role="dialog"] input[type="file"]',
        'input[type="file"][accept*="image"]',
        'input[type="file"]',
    ]

    async def _try_set_files() -> bool:
        for sel in file_input_selectors:
            try:
                loc = page.locator(sel)
                count = await loc.count()
                for i in range(count):
                    inp = loc.nth(i)
                    try:
                        await inp.set_input_files(abs_paths, timeout=8000)
                        logger.info("[FB] set_input_files OK | %d ảnh | %s [%d]", len(abs_paths), sel, i)
                        await page.wait_for_timeout(2000)
                        if await _wait_image_uploaded(page):
                            return True
                    except Exception as e:
                        logger.debug("[FB] set_input_files %s[%d] FAIL | %s", sel, i, e)
            except Exception as e:
                logger.debug("[FB] locator %s FAIL | %s", sel, e)
        return False

    if await _try_set_files():
        return True

    if await _click_first_visible(page, photo_btn_selectors, step="photo_btn"):
        await page.wait_for_timeout(2000)
        if await _try_set_files():
            return True

    for label in ("Ảnh/video", "Photo/video", "Photo", "Ảnh"):
        try:
            btn = page.get_by_role("button", name=label, exact=False).first
            if await btn.is_visible(timeout=2000):
                await btn.click()
                await page.wait_for_timeout(2000)
                if await _try_set_files():
                    return True
        except Exception as e:
            logger.debug("[FB] get_by_role(%r) FAIL | %s", label, e)

    return False


async def _type_post_content(page, content: str) -> bool:
    """Nhập nội dung vào ô soạn bài (dialog hoặc inline)."""
    text_selectors = [
        'div[role="dialog"] div[contenteditable="true"]',
        'div[contenteditable="true"][data-lexical-editor="true"]',
        'div[contenteditable="true"][role="textbox"]',
        'div[contenteditable="true"][aria-label*="Bạn viết"]',
        'div[contenteditable="true"][aria-label*="Create"]',
        'div[contenteditable="true"]',
    ]
    for sel in text_selectors:
        try:
            elem = page.locator(sel).last
            if await elem.is_visible(timeout=3000):
                await elem.click()
                await elem.fill(content)
                logger.info("[FB] Đã nhập nội dung | selector=%s", sel)
                return True
        except Exception as e:
            logger.debug("[FB] type FAIL | %s | %s", sel, e)

    try:
        await page.keyboard.type(content, delay=30)
        logger.info("[FB] Đã nhập nội dung | keyboard.type")
        return True
    except Exception as e:
        logger.debug("[FB] keyboard.type FAIL | %s", e)
    return False


async def _post_content_to_group(
    page,
    group_url: str,
    content: str,
    image_paths: Optional[list[str]] = None,
) -> dict:
    """Đăng bài lên group (giả định đã đăng nhập)."""
    result = {"success": False, "message": ""}

    logger.info(f"[FB] Điều hướng đến group: {group_url}")
    await page.goto(group_url, wait_until="domcontentloaded")
    await page.wait_for_timeout(4000)
    try:
        await page.wait_for_load_state("networkidle", timeout=20000)
    except Exception:
        pass
    await _dismiss_cookie_banner(page)
    await _ensure_joined_group(page)

    if not await _open_group_composer(page):
        await _log_page_state(page, "composer_not_found")
        await _save_debug(page, "composer", "composer_not_found")
        result["message"] = (
            "Không tìm thấy ô soạn bài trong group. "
            "Kiểm tra tài khoản đã tham gia nhóm và có quyền đăng bài."
        )
        return result

    await page.wait_for_timeout(2000)

    valid_images = [p for p in (image_paths or []) if os.path.exists(p)]
    if valid_images:
        if not await _attach_images_to_composer(page, valid_images):
            await _log_page_state(page, "image_attach_failed")
            await _save_debug(page, "post", "image_attach_failed")
            result["message"] = "Không đính kèm được ảnh. Thử bật「Hiện trình duyệt」để xem popup."
            return result
        await page.wait_for_timeout(1500)

    if not await _type_post_content(page, content):
        await _log_page_state(page, "type_failed")
        result["message"] = "Không nhập được nội dung bài viết."
        return result

    await page.wait_for_timeout(1000)

    submit_selectors = [
        'div[aria-label="Đăng"]',
        'div[aria-label="Post"]',
        'button[type="submit"]:has-text("Đăng")',
        'button:has-text("Post")',
        'div[role="button"]:has-text("Đăng")',
        'div[role="button"]:has-text("Post")',
    ]

    if not await _click_first_visible(page, submit_selectors, step="post_btn"):
        await _log_page_state(page, "post_btn_not_found")
        result["message"] = "Không tìm thấy nút đăng bài."
        return result

    logger.info("[FB] Đã nhấn nút Đăng bài — chờ dialog đóng...")

    # Chờ dialog compose đóng
    try:
        await page.wait_for_selector(
            'div[role="dialog"]', state="hidden", timeout=15000
        )
        logger.info("[FB] Dialog compose đã đóng")
    except Exception:
        logger.debug("[FB] Dialog timeout hoặc đã đóng trước")

    # Chờ thêm để feed load bài mới
    await page.wait_for_timeout(4000)

    # Lấy toàn bộ HTML và lưu debug
    html = ""
    try:
        html = await page.content()
        logger.info("[FB] Raw HTML size: %d bytes | url=%s", len(html), page.url)
        await _save_html_debug(html, "after_post")
    except Exception as e:
        logger.warning("[FB] Không lấy được HTML: %s", e)

    # Parse HTML tìm post URL
    post_url = _extract_post_url_from_html(html, group_url) if html else None
    if post_url:
        result["post_url"] = post_url
        logger.info("[FB] ✅ Post URL: %s", post_url)
    else:
        logger.warning("[FB] ⚠️  Không tìm được post URL trong HTML")

    result["success"] = True
    result["message"] = f"Đăng bài thành công lên group: {group_url}"
    logger.info(result["message"])
    return result


def _extract_post_url_from_html(html: str, group_url: str) -> Optional[str]:
    """Parse raw HTML để tìm URL bài viết mới nhất. Fallback khi network không bắt được."""
    group_id_m = re.search(r'/groups/([^/?#]+)', group_url)
    group_id = group_id_m.group(1) if group_id_m else None

    patterns = [
        r'href="(https://www\.facebook\.com/groups/[^"]+/posts/\d+[^"]*)"',
        r'"(https://www\.facebook\.com/groups/[^"\\]+/posts/\d+[^"\\]*)"',
        r'href="([^"]*story_fbid=\d+[^"]*id=\d+[^"]*)"',
        r'"([^"\\]*story_fbid=\d+[^"\\]*id=\d+[^"\\]*)"',
    ]

    seen: set = set()
    candidates: list = []
    for pat in patterns:
        for m in re.finditer(pat, html):
            url = m.group(1).replace('\\/', '/').replace('&amp;', '&')
            if url in seen:
                continue
            seen.add(url)
            if group_id and group_id not in url:
                continue
            candidates.append(url)

    logger.info(
        "[FB][URL] HTML fallback: tìm thấy %d candidate(s) | group_id=%s",
        len(candidates), group_id,
    )
    for i, u in enumerate(candidates[:5]):
        logger.info("[FB][URL]   [%d] %s", i, u)

    return candidates[0] if candidates else None


async def _start_network_url_capture(page):
    """
    Gắn listener vào page TRƯỚC KHI click Đăng.
    Trả về coroutine getter — gọi `await getter()` sau khi click để lấy URL.

    Facebook gửi GraphQL mutation khi tạo bài, response chứa permalink_url.
    Ta intercept response đó để lấy URL ngay lập tức, không cần parse DOM.
    """
    captured: list = []
    done = asyncio.Event()

    async def on_response(response):
        if done.is_set():
            return
        url = response.url
        if response.status != 200:
            return
        # Chỉ quan tâm GraphQL và API calls
        if 'graphql' not in url and '/api/' not in url:
            return
        try:
            text = await response.text()
            logger.debug(
                "[FB][URL] Checking response | url=%s | size=%d",
                url[:80], len(text),
            )

            # Pattern 1: "permalink_url":"https:\/\/www.facebook.com\/groups\/...\/posts\/..."
            m = re.search(
                r'"permalink_url"\s*:\s*"(https?:\\?/\\?/(?:www\.)?facebook\.com[^"\\]+)"',
                text,
            )
            if m:
                raw = m.group(1).replace('\\/', '/')
                if any(k in raw for k in ['/posts/', 'story_fbid', '/permalink']):
                    logger.info("[FB][URL] ✅ Network capture (permalink_url): %s", raw)
                    captured.append(raw)
                    done.set()
                    return

            # Pattern 2: "url":"https://www.facebook.com/groups/.../posts/..."
            for m in re.finditer(
                r'"url"\s*:\s*"(https?:\\?/\\?/(?:www\.)?facebook\.com'
                r'/groups/[^"\\]+/posts/\d+[^"\\]*)"',
                text,
            ):
                raw = m.group(1).replace('\\/', '/')
                logger.info("[FB][URL] ✅ Network capture (url field): %s", raw)
                captured.append(raw)
                done.set()
                return

            # Pattern 3: story_fbid=XXX&id=YYY
            m = re.search(r'story_fbid[=\\u003D]+(\d+)[^"]*id[=\\u003D]+(\d+)', text)
            if m:
                raw = (
                    f"https://www.facebook.com/permalink.php"
                    f"?story_fbid={m.group(1)}&id={m.group(2)}"
                )
                logger.info("[FB][URL] ✅ Network capture (story_fbid): %s", raw)
                captured.append(raw)
                done.set()

        except Exception as e:
            logger.debug("[FB][URL] on_response parse FAIL | %s | %s", url[:60], e)

    page.on("response", on_response)
    logger.info("[FB][URL] Network listener đã gắn — chờ GraphQL response sau khi đăng...")

    async def get_url(timeout_s: float = 15.0) -> Optional[str]:
        try:
            await asyncio.wait_for(done.wait(), timeout=timeout_s)
        except asyncio.TimeoutError:
            logger.warning(
                "[FB][URL] Network listener timeout sau %.0fs — chuyển sang HTML fallback",
                timeout_s,
            )
        finally:
            try:
                page.remove_listener("response", on_response)
            except Exception:
                pass
        return captured[0] if captured else None

    return get_url


async def _post_marketplace_to_group(
    page,
    group_url: str,
    content: str,
    mp_title: str,
    mp_price: str,
    mp_condition: str = "Mới",
    image_paths: Optional[list[str]] = None,
) -> dict:
    """Đăng niêm yết mặt hàng lên nhóm mua bán Facebook."""
    result = {"success": False, "message": ""}

    logger.info("[FB][MP] Điều hướng đến group marketplace: %s", group_url)
    await page.goto(group_url, wait_until="domcontentloaded")
    await page.wait_for_timeout(4000)
    try:
        await page.wait_for_load_state("networkidle", timeout=20000)
    except Exception:
        pass
    await _dismiss_cookie_banner(page)
    await _ensure_joined_group(page)

    # Step 1: Click "Bán gì đó" / "Sell something" — entry point for marketplace in group
    sell_btn_selectors = [
        'div[aria-label="Bán gì đó"]',
        'div[role="button"][aria-label="Bán gì đó"]',
        'div[role="button"]:has-text("Bán gì đó")',
        'span:has-text("Bán gì đó")',
        'div[aria-label="Sell something"]',
        'div[role="button"]:has-text("Sell something")',
        'div[aria-label*="Đăng bài niêm yết"]',
        'div[role="button"]:has-text("Đăng bài niêm yết mới")',
    ]
    if not await _click_first_visible(page, sell_btn_selectors, step="sell_btn"):
        # Try navigating to buy_sell tab as fallback
        buy_sell_selectors = [
            'div[role="tab"]:has-text("Mua và bán")',
            'a[role="tab"]:has-text("Mua và bán")',
            'a[href*="buy_sell"]',
            'a[href*="buying_selling"]',
            'div[role="tab"]:has-text("Buy and Sell")',
        ]
        await _click_first_visible(page, buy_sell_selectors, step="buy_sell_tab")
        await page.wait_for_timeout(3000)
        # Try sell button again after tab click
        if not await _click_first_visible(page, sell_btn_selectors, step="sell_btn_after_tab"):
            await _log_page_state(page, "mp_sell_btn_not_found")
            await _save_debug(page, "mp", "sell_btn_not_found")
            result["message"] = (
                "Không tìm thấy nút 'Bán gì đó' trong nhóm. "
                "Kiểm tra nhóm có tính năng Mua & Bán không."
            )
            return result

    logger.info("[FB][MP] Đã nhấn Bán gì đó, chờ dialog load...")

    # Wait for the dialog to appear
    try:
        await page.wait_for_selector('div[role="dialog"]', timeout=10000)
        logger.info("[FB][MP] Dialog đã xuất hiện")
    except Exception:
        logger.warning("[FB][MP] Không thấy dialog sau 10s, tiếp tục...")

    # Wait for dialog skeleton to finish loading — FB lazy-loads dialog content
    # Poll until "Mặt hàng cần bán" or "Tiêu đề" input appears (max 12s)
    dialog_loaded = False
    for _ in range(12):
        try:
            has_option = await page.locator(
                'div[role="button"]:has-text("Mặt hàng cần bán"), '
                'input[placeholder="Tiêu đề"]'
            ).first.is_visible(timeout=1000)
            if has_option:
                dialog_loaded = True
                break
        except Exception:
            pass
        await page.wait_for_timeout(1000)

    await _save_debug(page, "mp", "after_sell_btn")
    logger.info("[FB][MP] Dialog loaded=%s", dialog_loaded)

    # Step 2: Click "Mặt hàng cần bán" if the type-selection screen appeared
    item_for_sale_selectors = [
        'div[role="button"]:has-text("Mặt hàng cần bán")',
        'div[aria-label*="Mặt hàng cần bán"]',
        'span:has-text("Mặt hàng cần bán")',
        'div[role="button"]:has-text("Item for Sale")',
        'div[role="button"]:has-text("Item for sale")',
        'span:has-text("Item for sale")',
    ]
    item_clicked = await _click_first_visible(page, item_for_sale_selectors, step="item_for_sale")
    if item_clicked:
        logger.info("[FB][MP] Đã chọn Mặt hàng cần bán, chờ form load...")
        # Wait for form fields to appear
        try:
            await page.wait_for_selector('input[placeholder="Tiêu đề"]', timeout=10000)
            logger.info("[FB][MP] Form niêm yết đã load")
        except Exception:
            logger.warning("[FB][MP] Chưa thấy field Tiêu đề sau 10s")
        await _save_debug(page, "mp", "after_item_for_sale")

    # Step 3: Fill title — exact placeholders from FB form
    filled_title = False
    title_selectors = [
        'input[placeholder="Tiêu đề"]',
        'input[placeholder*="Tiêu đề"]',
        'input[aria-label="Tiêu đề"]',
        'input[placeholder="Title"]',
        'input[aria-label="Title"]',
        'input[placeholder*="Tên mặt hàng"]',
        'input[aria-label*="Tên mặt hàng"]',
    ]
    for sel in title_selectors:
        try:
            loc = page.locator(sel).first
            if await loc.is_visible(timeout=4000):
                await loc.click()
                await loc.fill(mp_title)
                logger.info("[FB][MP] Đã nhập tiêu đề | %s", sel)
                filled_title = True
                break
        except Exception as e:
            logger.debug("[FB][MP] title fill FAIL | %s | %s", sel, e)

    if not filled_title:
        await _log_page_state(page, "mp_title_not_found")
        await _save_debug(page, "mp", "title_not_found")
        # Last resort: all visible text inputs in dialog
        try:
            inputs = await page.locator('div[role="dialog"] input:visible').all()
            logger.info("[FB][MP] Fallback: %d input trong dialog", len(inputs))
            if inputs:
                await inputs[0].click()
                await inputs[0].fill(mp_title)
                logger.info("[FB][MP] Đã nhập tiêu đề | fallback dialog input[0]")
                filled_title = True
        except Exception as e:
            logger.debug("[FB][MP] title fallback FAIL | %s", e)

    if not filled_title:
        result["message"] = "Không tìm thấy ô Tiêu đề trong form niêm yết."
        return result

    await page.wait_for_timeout(500)

    # Step 4: Fill price — exact placeholder "Giá" from FB form
    filled_price = False
    price_selectors = [
        'input[placeholder="Giá"]',
        'input[placeholder*="Giá"]',
        'input[aria-label="Giá"]',
        'input[placeholder="Price"]',
        'input[aria-label="Price"]',
    ]
    for sel in price_selectors:
        try:
            loc = page.locator(sel).first
            if await loc.is_visible(timeout=3000):
                await loc.click()
                await loc.fill(mp_price)
                logger.info("[FB][MP] Đã nhập giá | %s", sel)
                filled_price = True
                break
        except Exception as e:
            logger.debug("[FB][MP] price fill FAIL | %s | %s", sel, e)

    if not filled_price:
        try:
            inputs = await page.locator('div[role="dialog"] input:visible').all()
            logger.info("[FB][MP] Fallback giá: %d inputs trong dialog", len(inputs))
            if len(inputs) > 1:
                await inputs[1].click()
                await inputs[1].fill(mp_price)
                logger.info("[FB][MP] Đã nhập giá | fallback dialog input[1]")
                filled_price = True
        except Exception as e:
            logger.debug("[FB][MP] price fallback FAIL | %s", e)

    if not filled_price:
        logger.warning("[FB][MP] Không tìm thấy ô giá, tiếp tục...")

    await page.wait_for_timeout(500)

    # Step 5: Select condition
    # "Tình trạng" renders as a styled div with placeholder="Tình trạng" (not aria-label).
    # Strategy: JS-first — find the element, click it, then pick option.
    condition_opened = False
    try:
        cond_info = await page.evaluate(r"""() => {
            const dialog = document.querySelector('[role="dialog"]');
            if (!dialog) return null;
            // Find by placeholder attr, aria-label, or aria-placeholder
            let el = dialog.querySelector('[placeholder="Tình trạng"], [aria-label="Tình trạng"], [aria-placeholder="Tình trạng"]');
            if (!el) {
                // Try by role=combobox (FB custom select)
                el = dialog.querySelector('[role="combobox"]');
            }
            if (!el) {
                // Try native select
                el = dialog.querySelector('select');
            }
            if (!el) return null;
            const tag = el.tagName.toLowerCase();
            const role = el.getAttribute('role') || '';
            if (tag === 'select') {
                return {found: true, method: 'select', tag};
            }
            el.click();
            return {found: true, method: 'click', tag, role};
        }""")
        if cond_info and cond_info.get("found"):
            logger.info("[FB][MP] Mở dropdown Tình trạng | %s", cond_info)
            condition_opened = True
            if cond_info.get("method") == "select":
                # Native select: use Playwright select_option
                for sel in ('div[role="dialog"] select', 'select'):
                    try:
                        loc = page.locator(sel).first
                        if await loc.is_visible(timeout=2000):
                            await loc.select_option(label=mp_condition)
                            logger.info("[FB][MP] Đã chọn tình trạng (native select) | %s", mp_condition)
                            condition_opened = False  # already done, skip option click
                            break
                    except Exception:
                        pass
        else:
            logger.warning("[FB][MP] JS không tìm thấy dropdown Tình trạng")
    except Exception as e:
        logger.warning("[FB][MP] JS condition find FAIL | %s", e)

    # Fallback: Playwright get_by_placeholder
    if not condition_opened:
        try:
            loc = page.get_by_placeholder("Tình trạng").first
            if await loc.is_visible(timeout=3000):
                await loc.click()
                condition_opened = True
                logger.info("[FB][MP] Mở dropdown Tình trạng | get_by_placeholder")
        except Exception as e:
            logger.debug("[FB][MP] get_by_placeholder FAIL | %s", e)

    if condition_opened:
        await page.wait_for_timeout(800)
        # Pick the option from opened dropdown
        opt_selectors = [
            f'div[role="option"]:has-text("{mp_condition}")',
            f'li[role="option"]:has-text("{mp_condition}")',
            f'span[role="option"]:has-text("{mp_condition}")',
            f'div[role="menuitem"]:has-text("{mp_condition}")',
        ]
        picked = await _click_first_visible(page, opt_selectors, step="condition_option")
        if picked:
            logger.info("[FB][MP] Đã chọn tình trạng | %s", mp_condition)
        else:
            try:
                await page.evaluate(
                    r"""(cond) => {
                        for (const s of ['[role="option"]','[role="menuitem"]','li']) {
                            const m = [...document.querySelectorAll(s)]
                                .find(o => (o.textContent||'').trim().startsWith(cond));
                            if (m) { m.click(); return true; }
                        }
                        return false;
                    }""",
                    mp_condition,
                )
                logger.info("[FB][MP] Đã chọn tình trạng (JS option) | %s", mp_condition)
            except Exception as e:
                logger.warning("[FB][MP] JS option FAIL | %s", e)
        await page.wait_for_timeout(600)

    await page.wait_for_timeout(500)

    # Step 6: Fill description/content (optional)
    if content and content.strip():
        desc_selectors = [
            'div[contenteditable="true"][aria-label*="Mô tả"]',
            'div[contenteditable="true"][aria-label*="Description"]',
            'textarea[aria-label*="Mô tả"]',
            'textarea[aria-label*="Description"]',
            'div[contenteditable="true"][role="textbox"]',
            'div[contenteditable="true"]',
        ]
        for sel in desc_selectors:
            try:
                elem = page.locator(sel).last
                if await elem.is_visible(timeout=3000):
                    await elem.click()
                    await elem.fill(content)
                    logger.info("[FB][MP] Đã nhập mô tả | %s", sel)
                    break
            except Exception as e:
                logger.debug("[FB][MP] desc type FAIL | %s | %s", sel, e)

    await page.wait_for_timeout(500)

    # Step 7: Attach images (optional)
    valid_mp_images = [p for p in (image_paths or []) if os.path.exists(p)]
    if valid_mp_images:
        if not await _attach_images_to_composer(page, valid_mp_images):
            logger.warning("[FB][MP] Không đính kèm được ảnh, tiếp tục không có ảnh...")

    await page.wait_for_timeout(1000)

    # Step 8: Click "Tiếp" (Next) — only click when it becomes ENABLED
    # DO NOT force-click while disabled — that closes the dialog
    next_clicked = False
    for label in ("Tiếp", "Next"):
        try:
            loc = page.locator(
                f'[aria-label="{label}"][role="button"], '
                f'div[role="button"]:has-text("{label}"), '
                f'button:has-text("{label}")'
            ).first
            if not await loc.is_visible(timeout=3000):
                continue
            # Wait up to 10s for button to become enabled
            enabled = False
            for i in range(10):
                disabled = await loc.evaluate(
                    "el => el.getAttribute('aria-disabled') === 'true' || el.disabled === true"
                )
                if not disabled:
                    enabled = True
                    break
                logger.debug("[FB][MP] Tiếp disabled (chờ condition được chọn) %d/10", i + 1)
                await page.wait_for_timeout(1000)

            if not enabled:
                logger.warning("[FB][MP] Tiếp vẫn disabled sau 10s — có thể condition chưa được chọn")
                await _save_debug(page, "mp", "tiep_still_disabled")
                # Do NOT force-click — skip and let submit section handle it
                break

            await loc.click(timeout=5000)
            next_clicked = True
            logger.info("[FB][MP] Đã nhấn Tiếp")
            break
        except Exception as e:
            logger.debug("[FB][MP] next_btn '%s' FAIL | %s", label, e)

    if next_clicked:
        await page.wait_for_timeout(3000)

    # Step 9: Submit
    submit_selectors = [
        'div[role="button"]:has-text("Đăng niêm yết")',
        'button:has-text("Đăng niêm yết")',
        'div[aria-label="Đăng"]',
        'div[aria-label="Post"]',
        'div[role="button"]:has-text("Publish listing")',
        'button:has-text("Publish")',
        'div[role="button"]:has-text("Đăng")',
        'div[role="button"]:has-text("Post")',
    ]
    if not await _click_first_visible(page, submit_selectors, step="mp_post_btn"):
        await _log_page_state(page, "mp_post_btn_not_found")
        await _save_debug(page, "mp", "post_btn_not_found")
        result["message"] = "Không tìm thấy nút đăng niêm yết."
        return result

    logger.info("[FB][MP] Đã nhấn nút Đăng niêm yết")
    await page.wait_for_timeout(5000)
    post_url = await _capture_post_url(page, mp_title)
    if post_url:
        result["post_url"] = post_url
    result["success"] = True
    result["message"] = f"Đăng niêm yết thành công lên group: {group_url}"
    logger.info(result["message"])
    return result


async def _resolve_post_url(page, target: dict) -> Optional[str]:
    """Lấy URL bài từ target hoặc tìm trên feed group."""
    post_url = (target.get("post_url") or "").strip()
    if post_url:
        return post_url
    group_url = (target.get("group_url") or "").strip()
    snippet = (target.get("post_content") or target.get("content") or "").strip()
    if not group_url or not snippet:
        return None
    logger.info("[FB] Tìm bài trên group | %s", group_url)
    await page.goto(group_url, wait_until="domcontentloaded")
    await page.wait_for_timeout(4000)
    await _dismiss_cookie_banner(page)
    return await _capture_post_url(page, snippet)


async def _comment_on_post(page, post_url: str, comment: str) -> dict:
    """Bình luận trên một bài viết Facebook."""
    result = {"success": False, "message": "", "post_url": post_url}
    logger.info("[FB] Mở bài viết để bình luận: %s", post_url)
    await page.goto(post_url, wait_until="domcontentloaded")
    await page.wait_for_timeout(4000)
    try:
        await page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    await _dismiss_cookie_banner(page)

    focus_selectors = [
        'div[aria-label="Viết bình luận"]',
        'div[aria-label="Viết bình luận dưới tên bạn"]',
        'div[aria-label="Write a comment"]',
        'div[role="button"]:has-text("Bình luận")',
        'span:has-text("Bình luận")',
    ]
    await _click_first_visible(page, focus_selectors, step="comment_focus")
    await page.wait_for_timeout(1500)

    text_selectors = [
        'div[contenteditable="true"][aria-label*="ình luận"]',
        'div[contenteditable="true"][aria-label*="omment"]',
        'div[role="article"] div[contenteditable="true"]',
        'form div[contenteditable="true"]',
        'div[contenteditable="true"]',
    ]
    typed = False
    for sel in text_selectors:
        try:
            elem = page.locator(sel).first
            if await elem.is_visible(timeout=3000):
                await elem.click()
                await elem.fill(comment)
                typed = True
                logger.info("[FB] Đã nhập bình luận | %s", sel)
                break
        except Exception as e:
            logger.debug("[FB] comment type %s FAIL | %s", sel, e)

    if not typed:
        try:
            await page.keyboard.type(comment, delay=25)
            typed = True
        except Exception as e:
            logger.debug("[FB] keyboard type comment FAIL | %s", e)

    if not typed:
        result["message"] = "Không tìm thấy ô bình luận."
        return result

    await page.wait_for_timeout(800)
    submit_selectors = [
        'div[aria-label="Bình luận"][role="button"]',
        'div[role="button"]:has-text("Bình luận")',
        'div[aria-label="Comment"][role="button"]',
        'div[role="button"]:has-text("Comment")',
    ]
    submitted = await _click_first_visible(page, submit_selectors, step="comment_submit")
    if not submitted:
        await page.keyboard.press("Enter")
    await page.wait_for_timeout(3000)
    result["success"] = True
    result["message"] = "Bình luận thành công"
    return result


async def comment_on_multiple(
    accounts: list[dict],
    targets: list[dict],
    content: str,
    headless: bool = True,
    on_progress: ProgressCallback = None,
) -> list[dict]:
    """Nhiều tài khoản bình luận trên nhiều bài viết."""
    try:
        from playwright.async_api import async_playwright, TimeoutError as PWTimeout
    except ImportError:
        msg = "Playwright chưa được cài đặt."
        return [
            {
                "account_email": a["email"],
                "target_label": t.get("label") or t.get("group_name") or t.get("post_url", ""),
                "success": False,
                "message": msg,
            }
            for a in accounts
            for t in targets
        ]

    results = []
    total = len(accounts) * len(targets)

    def _emit(current: Optional[dict] = None) -> None:
        if on_progress:
            on_progress({
                "done": len(results),
                "total": total,
                "results": list(results),
                "current": current,
            })

    for account in accounts:
        account_id = account.get("id", account["email"])
        session_file = _session_path(account_id)

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=headless,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context_kwargs = {
                "user_agent": USER_AGENT,
                "locale": "vi-VN",
                "viewport": {"width": 1280, "height": 900},
            }
            if session_file.exists():
                context_kwargs["storage_state"] = str(session_file)

            context = await browser.new_context(**context_kwargs)
            page = await context.new_page()

            try:
                login = await _ensure_logged_in(page, account, headless=headless)
                if not login["success"]:
                    for target in targets:
                        label = target.get("label") or target.get("group_name", "")
                        item = {
                            "account_email": account["email"],
                            "account_id": account_id,
                            "target_id": target.get("id"),
                            "group_name": target.get("group_name"),
                            "post_url": target.get("post_url"),
                            "target_label": label,
                            "success": False,
                            "message": login["message"],
                        }
                        results.append(item)
                        _emit(item)
                    continue

                for target in targets:
                    label = target.get("label") or target.get("group_name") or target.get("post_url", "")
                    pending = {
                        "account_email": account["email"],
                        "account_id": account_id,
                        "target_label": label,
                        "status": "running",
                    }
                    _emit(pending)
                    try:
                        post_url = await _resolve_post_url(page, target)
                        if not post_url:
                            res = {
                                "success": False,
                                "message": "Không có URL bài viết. Dán link bài hoặc đăng lại để lưu URL.",
                            }
                        else:
                            res = await _comment_on_post(page, post_url, content)
                    except PWTimeout as e:
                        res = {"success": False, "message": f"Timeout: {str(e)}"}
                    except Exception as e:
                        res = {"success": False, "message": f"Lỗi: {str(e)}"}

                    item = {
                        "account_email": account["email"],
                        "account_id": account_id,
                        "target_id": target.get("id"),
                        "group_name": target.get("group_name"),
                        "post_url": res.get("post_url") or target.get("post_url"),
                        "target_label": label,
                        **res,
                    }
                    results.append(item)
                    _emit(item)

                await context.storage_state(path=str(session_file))
            finally:
                await browser.close()

    return results


async def post_to_group(
    account: dict,
    group_url: str,
    content: str,
    image_paths: Optional[list[str]] = None,
    headless: bool = True,
) -> dict:
    """Post content to a Facebook Group using Playwright."""
    try:
        from playwright.async_api import async_playwright, TimeoutError as PWTimeout
    except ImportError:
        return {"success": False, "message": "Playwright chưa được cài đặt."}

    result = {"success": False, "message": ""}
    account_id = account.get("id", account["email"])
    session_file = _session_path(account_id)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context_kwargs = {
            "user_agent": USER_AGENT,
            "locale": "vi-VN",
            "viewport": {"width": 1280, "height": 900},
        }
        if session_file.exists():
            context_kwargs["storage_state"] = str(session_file)

        context = await browser.new_context(**context_kwargs)
        page = await context.new_page()

        try:
            login = await _ensure_logged_in(page, account, headless=headless)
            if not login["success"]:
                result["message"] = login["message"]
                return result

            result = await _post_content_to_group(page, group_url, content, image_paths)
            if result["success"]:
                await context.storage_state(path=str(session_file))

        except PWTimeout as e:
            result["message"] = f"Timeout: {str(e)}"
            logger.error(result["message"])
        except Exception as e:
            result["message"] = f"Lỗi: {str(e)}"
            logger.error(result["message"])
        finally:
            await browser.close()

    return result


async def post_to_multiple(
    accounts: list[dict],
    groups: list[dict],
    content: str,
    image_paths: Optional[list[str]] = None,
    headless: bool = True,
    on_progress: ProgressCallback = None,
    marketplace_data: Optional[dict] = None,
    parallel: int = 1,
) -> list[dict]:
    """Post to multiple groups — chạy tuần tự từng task một."""
    try:
        from playwright.async_api import async_playwright, TimeoutError as PWTimeout
    except ImportError:
        msg = "Playwright chưa được cài đặt."
        return [
            {
                "account_email": a["email"],
                "group_name": g["name"],
                "group_url": g["url"],
                "success": False,
                "message": msg,
            }
            for a in accounts
            for g in groups
        ]

    results: list[dict] = []
    total = len(accounts) * len(groups)
    semaphore = asyncio.Semaphore(parallel)
    results_lock = asyncio.Lock()
    # Per-account lock để tránh ghi đè session file đồng thời
    session_locks = {a.get("id", a["email"]): asyncio.Lock() for a in accounts}

    def _emit(current: Optional[dict] = None) -> None:
        if on_progress:
            on_progress({
                "done": len(results),
                "total": total,
                "results": list(results),
                "current": current,
            })

    async def _post_one(account: dict, group: dict) -> None:
        account_id = account.get("id", account["email"])
        session_file = _session_path(account_id)
        base_item = {
            "account_email": account["email"],
            "account_id": account_id,
            "group_name": group["name"],
            "group_url": group["url"],
        }
        _emit({**base_item, "status": "running"})

        async with semaphore:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=headless,
                    args=["--disable-blink-features=AutomationControlled"],
                )
                context_kwargs = {
                    "user_agent": USER_AGENT,
                    "locale": "vi-VN",
                    "viewport": {"width": 1280, "height": 900},
                }
                async with session_locks[account_id]:
                    if session_file.exists():
                        context_kwargs["storage_state"] = str(session_file)

                context = await browser.new_context(**context_kwargs)
                page = await context.new_page()
                try:
                    login = await _ensure_logged_in(page, account, headless=headless)
                    if not login["success"]:
                        res = {"success": False, "message": login["message"]}
                    else:
                        try:
                            if marketplace_data:
                                res = await _post_marketplace_to_group(
                                    page,
                                    group["url"],
                                    content,
                                    mp_title=marketplace_data["title"],
                                    mp_price=marketplace_data["price"],
                                    mp_condition=marketplace_data.get("condition", "Mới"),
                                    image_paths=image_paths,
                                )
                            else:
                                res = await _post_content_to_group(
                                    page, group["url"], content, image_paths
                                )
                        except PWTimeout as e:
                            res = {"success": False, "message": f"Timeout: {str(e)}"}
                        except Exception as e:
                            res = {"success": False, "message": f"Lỗi: {str(e)}"}

                        if res.get("success"):
                            async with session_locks[account_id]:
                                await context.storage_state(path=str(session_file))
                finally:
                    await browser.close()

        item = {**base_item, **res}
        async with results_lock:
            results.append(item)
        _emit(item)

    tasks = [_post_one(account, group) for account in accounts for group in groups]
    await asyncio.gather(*tasks)
    return results
