import os
import re
import tempfile
from pathlib import Path
from playwright.sync_api import (
    TimeoutError as PlaywrightTimeoutError,
    Playwright,
    Browser,
    BrowserContext,
    Page,
)

COOKIES_PATH = "yt_cookies.json"


def upload_video_to_youtube(video_path: str, page: Page) -> None:
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file {video_path} not found")

    try:
        page.click("button:has(div:has-text('Create'))")
        page.click("tp-yt-paper-item:has-text('Upload videos')")

        # uploading the video file
        with page.expect_file_chooser() as fc_info:
            page.click("button:has(div:has-text('Select files'))")
        file_chooser = fc_info.value
        file_chooser.set_files(video_path)

        # filling video details

        page.click('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]')
        page.click("#next-button")
        page.click("#next-button")
        page.click("#next-button")
        page.locator('tp-yt-paper-radio-button[name="PRIVATE"]').click()

        # saving and closing
        page.click("button:has(div:has-text('Save'))")
        page.click("ytcp-button#close-button")

    except PlaywrightTimeoutError:
        raise Exception("Error during video upload process.")


def get_video_list(page: Page) -> list[str]:
    anchors = page.query_selector_all("a#video-title")
    titles: list[str] = []
    for a in anchors:
        text = (a.inner_text() or "").strip()
        titles.append(text)
    return titles


def _find_video_row(page: Page, video_title: str):
    title = page.locator("a#video-title").filter(
        has_text=re.compile(rf"^\s*{re.escape(video_title)}\s*$")
    )
    row = page.locator(".ytcp-video-list-cell-video.right-section").filter(
        has=title
    )
    count = row.count()
    if count == 0:
        raise Exception(f"Video titled '{video_title}' not found on the page.")
    if count > 1:
        raise Exception(
            f"Multiple videos are titled '{video_title}'. Rename them in YouTube Studio first."
        )
    return row


def delete_video(page: Page, video_title: str) -> None:
    row = _find_video_row(page, video_title)

    row.hover()
    row.locator('[aria-label="Options"]').click()
    page.click("tp-yt-paper-item:has-text('Delete forever')")
    page.click("ytcp-checkbox-lit#confirm-checkbox")
    page.click("ytcp-button#confirm-button")


def download_video(page: Page, video_title: str, dest_dir: Path) -> str:
    """Save to a unique temporary path that the caller owns and must clean up."""
    row = _find_video_row(page, video_title)
    row.hover()
    with page.expect_download() as download_info:
        row.locator('[aria-label="Options"]').click()
        page.click("tp-yt-paper-item:has-text('Download')")

    # Reserve a unique path; the remote filename must never overwrite a local file.
    download = download_info.value
    with tempfile.NamedTemporaryFile(
        prefix="youtube-drive-", suffix=".mp4", dir=dest_dir, delete=False
    ) as temporary:
        dest_path = temporary.name
    try:
        download.save_as(dest_path)
    except Exception:
        Path(dest_path).unlink(missing_ok=True)
        raise

    return dest_path


def create_yt_instance(sync_p: Playwright) -> tuple[Browser, BrowserContext, Page]:
    browser = sync_p.firefox.launch(headless=False)

    context = browser.new_context(
        locale="en-US",
        storage_state=COOKIES_PATH if os.path.exists(COOKIES_PATH) else None,
    )
    page = context.new_page()

    page.goto("https://studio.youtube.com", wait_until="load")

    while "accounts.google.com" in page.url:
        print(
            "Login to YouTube Studio in the Playwright window, then press Enter here."
        )
        input("Press Enter after logging in...")
        page.goto("https://studio.youtube.com", wait_until="load")

        if "accounts.google.com" not in page.url:
            context.storage_state(path=COOKIES_PATH)
            print("Saved login cookies.")
            break

    print("Logged in successfully.")

    try:
        page.click("tp-yt-paper-icon-item:has(div:has-text('Content'))")
    except PlaywrightTimeoutError:
        raise Exception(
            "Could not find 'Content' button after login. Set the language to English."
        )

    return browser, context, page
