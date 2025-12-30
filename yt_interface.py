import os
from pathlib import Path
from playwright.sync_api import (
    TimeoutError as PlaywrightTimeoutError,
    Playwright,
    Browser,
    BrowserContext,
    Page,
)

COOKIES_PATH = "yt_cookies.json"
# TODO: not all videos are loaded at once, API to find all videos may be needed
# anyway need to use the search bar to click the correct options


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


def delete_video(page: Page, video_title: str) -> None:
    row = page.locator(".ytcp-video-list-cell-video.right-section").filter(
        has_text=video_title
    )
    if row.count() == 0:
        raise Exception(f"Video titled '{video_title}' not found on the page.")

    row.hover()
    row.locator('[aria-label="Options"]').click()
    page.click("tp-yt-paper-item:has-text('Delete forever')")
    page.click("ytcp-checkbox-lit#confirm-checkbox")
    page.click("ytcp-button#confirm-button")


def download_video(page: Page, video_title: str, dest_dir: Path) -> str:
    row = page.locator(".ytcp-video-list-cell-video.right-section").filter(
        has_text=video_title
    )
    if row.count() == 0:
        raise Exception(f"Video titled '{video_title}' not found on the page.")

    row.hover()
    with page.expect_download() as download_info:
        row.locator('[aria-label="Options"]').click()
        page.click("tp-yt-paper-item:has-text('Download')")

    # save download
    download = download_info.value
    filename = download.suggested_filename or "downloaded_video"
    dest_path = os.path.join(dest_dir, filename)
    download.save_as(dest_path)

    return dest_path


def create_yt_istance(sync_p: Playwright) -> tuple[Browser, BrowserContext, Page]:
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
