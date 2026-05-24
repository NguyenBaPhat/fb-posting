"""
Facebook Group Auto-Poster using Playwright.
Tự động đăng nhập, lưu session, và đăng bài lên group.
"""
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

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


async def _attach_image_to_composer(page, image_path: str) -> bool:
    """Đính kèm ảnh vào dialog soạn bài group."""
    abs_path = str(Path(image_path).resolve())
    if not Path(abs_path).is_file():
        logger.error("[FB] File ảnh không tồn tại: %s", abs_path)
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
                        await inp.set_input_files(abs_path, timeout=8000)
                        logger.info("[FB] set_input_files OK | %s [%d]", sel, i)
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
    image_path: Optional[str] = None,
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

    if image_path and os.path.exists(image_path):
        if not await _attach_image_to_composer(page, image_path):
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

    logger.info("[FB] Đã nhấn nút Đăng bài")
    await page.wait_for_timeout(5000)
    result["success"] = True
    result["message"] = f"Đăng bài thành công lên group: {group_url}"
    logger.info(result["message"])
    return result


async def post_to_group(
    account: dict,
    group_url: str,
    content: str,
    image_path: Optional[str] = None,
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

            result = await _post_content_to_group(page, group_url, content, image_path)
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
    image_path: Optional[str] = None,
    headless: bool = True,
) -> list[dict]:
    """Post to multiple groups. Mỗi tài khoản đăng nhập 1 lần, đăng nhiều group."""
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

    results = []

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
                    for group in groups:
                        results.append({
                            "account_email": account["email"],
                            "group_name": group["name"],
                            "group_url": group["url"],
                            "success": False,
                            "message": login["message"],
                        })
                    continue

                for group in groups:
                    try:
                        res = await _post_content_to_group(
                            page, group["url"], content, image_path
                        )
                    except PWTimeout as e:
                        res = {"success": False, "message": f"Timeout: {str(e)}"}
                    except Exception as e:
                        res = {"success": False, "message": f"Lỗi: {str(e)}"}

                    results.append({
                        "account_email": account["email"],
                        "group_name": group["name"],
                        "group_url": group["url"],
                        **res,
                    })

                await context.storage_state(path=str(session_file))

            finally:
                await browser.close()

    return results
