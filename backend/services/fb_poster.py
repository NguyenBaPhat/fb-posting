"""
Facebook Group Auto-Poster using Playwright.
Launches a real Chromium browser (headless=False) so user can handle 2FA.
"""
import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

UPLOADS_DIR = Path(__file__).parent.parent / "data" / "uploads"


async def post_to_group(
    account: dict,
    group_url: str,
    content: str,
    image_path: Optional[str] = None,
    headless: bool = False,
) -> dict:
    """
    Post content to a Facebook Group using Playwright.
    Returns {"success": bool, "message": str}
    """
    try:
        from playwright.async_api import async_playwright, TimeoutError as PWTimeout
    except ImportError:
        return {"success": False, "message": "Playwright chưa được cài đặt."}

    result = {"success": False, "message": ""}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        try:
            # ── 1. Login ──────────────────────────────────────────────────────
            logger.info(f"[FB] Đăng nhập tài khoản: {account['email']}")
            await page.goto("https://www.facebook.com/login", wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)

            # Fill email
            await page.fill("#email", account["email"])
            await page.fill("#pass", account["password"])
            await page.click('[name="login"]')
            await page.wait_for_timeout(4000)

            # Check login result
            current_url = page.url
            if "checkpoint" in current_url or "two_step" in current_url:
                result["message"] = (
                    "Tài khoản yêu cầu xác minh 2 bước. "
                    "Vui lòng xử lý thủ công trong cửa sổ trình duyệt."
                )
                # Wait longer for user to handle 2FA (60 seconds)
                await page.wait_for_url("**/groups/**", timeout=60000)
            elif "login" in current_url.lower():
                result["message"] = "Đăng nhập thất bại. Kiểm tra email/mật khẩu."
                return result

            # ── 2. Navigate to Group ──────────────────────────────────────────
            logger.info(f"[FB] Điều hướng đến group: {group_url}")
            await page.goto(group_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)

            # ── 3. Click "Write something" box ───────────────────────────────
            # Try multiple selectors for the post composer
            composer_selectors = [
                '[data-testid="group-composer-prompt"]',
                'div[role="button"]:has-text("Viết gì đó")',
                'div[role="button"]:has-text("Write something")',
                'div[aria-label="Tạo bài viết"]',
                'div[aria-label="Create a post"]',
                'span:has-text("Viết gì đó")',
                'span:has-text("Write something")',
            ]

            clicked = False
            for sel in composer_selectors:
                try:
                    elem = page.locator(sel).first
                    if await elem.is_visible(timeout=3000):
                        await elem.click()
                        clicked = True
                        logger.info(f"[FB] Clicked composer với selector: {sel}")
                        break
                except Exception:
                    continue

            if not clicked:
                result["message"] = "Không tìm thấy ô soạn bài viết trong group."
                return result

            await page.wait_for_timeout(2000)

            # ── 4. Type content ───────────────────────────────────────────────
            # Find the active text area in the dialog
            text_selectors = [
                'div[role="dialog"] div[contenteditable="true"]',
                'div[contenteditable="true"][data-lexical-editor="true"]',
                'div[contenteditable="true"]',
            ]

            typed = False
            for sel in text_selectors:
                try:
                    elem = page.locator(sel).last
                    if await elem.is_visible(timeout=3000):
                        await elem.click()
                        await elem.type(content, delay=30)
                        typed = True
                        logger.info(f"[FB] Đã nhập nội dung")
                        break
                except Exception:
                    continue

            if not typed:
                result["message"] = "Không nhập được nội dung bài viết."
                return result

            await page.wait_for_timeout(1000)

            # ── 5. Attach image (optional) ────────────────────────────────────
            if image_path and os.path.exists(image_path):
                try:
                    photo_btn_selectors = [
                        'div[aria-label="Ảnh/video"]',
                        'div[aria-label="Photo/Video"]',
                        'div[role="button"]:has-text("Photo")',
                        'div[role="button"]:has-text("Ảnh")',
                    ]
                    for sel in photo_btn_selectors:
                        try:
                            btn = page.locator(sel).first
                            if await btn.is_visible(timeout=2000):
                                await btn.click()
                                await page.wait_for_timeout(1500)
                                break
                        except Exception:
                            continue

                    # Upload file via file input
                    async with page.expect_file_chooser() as fc_info:
                        file_input = page.locator('input[type="file"]').first
                        await file_input.click()
                    file_chooser = await fc_info.value
                    await file_chooser.set_files(image_path)
                    await page.wait_for_timeout(2000)
                    logger.info(f"[FB] Đã đính kèm ảnh: {image_path}")
                except Exception as e:
                    logger.warning(f"[FB] Không đính kèm được ảnh: {e}")

            # ── 6. Submit post ────────────────────────────────────────────────
            submit_selectors = [
                'div[aria-label="Đăng"]',
                'div[aria-label="Post"]',
                'button[type="submit"]:has-text("Đăng")',
                'button:has-text("Post")',
                'div[role="button"]:has-text("Đăng")',
                'div[role="button"]:has-text("Post")',
            ]

            posted = False
            for sel in submit_selectors:
                try:
                    btn = page.locator(sel).last
                    if await btn.is_visible(timeout=3000):
                        await btn.click()
                        posted = True
                        logger.info("[FB] Đã nhấn nút Đăng bài")
                        break
                except Exception:
                    continue

            if not posted:
                result["message"] = "Không tìm thấy nút đăng bài."
                return result

            # Wait for post to complete
            await page.wait_for_timeout(5000)
            result["success"] = True
            result["message"] = f"Đăng bài thành công lên group: {group_url}"
            logger.info(result["message"])

        except PWTimeout as e:
            result["message"] = f"Timeout: {str(e)}"
            logger.error(result["message"])
        except Exception as e:
            result["message"] = f"Lỗi: {str(e)}"
            logger.error(result["message"])
        finally:
            await page.wait_for_timeout(2000)
            await browser.close()

    return result


async def post_to_multiple(
    accounts: list[dict],
    groups: list[dict],
    content: str,
    image_path: Optional[str] = None,
    headless: bool = False,
) -> list[dict]:
    """Post to multiple groups using multiple accounts. Returns list of results."""
    results = []
    for account in accounts:
        for group in groups:
            res = await post_to_group(
                account=account,
                group_url=group["url"],
                content=content,
                image_path=image_path,
                headless=headless,
            )
            results.append({
                "account_email": account["email"],
                "group_name": group["name"],
                "group_url": group["url"],
                **res,
            })
    return results
