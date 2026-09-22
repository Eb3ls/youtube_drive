import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from playwright.sync_api import sync_playwright

import yt_interface


CHROMIUM_PATH = os.environ.get("YOUTUBE_DRIVE_TEST_BROWSER")


def make_download_page(download):
    page = MagicMock()
    row = MagicMock()
    page.locator.return_value.filter.return_value = row
    row.count.return_value = 1
    page.expect_download.return_value.__enter__.return_value.value = download
    return page


class DownloadFileSafetyTests(unittest.TestCase):
    def test_download_uses_unique_mp4_path_and_preserves_existing_entries(self):
        with tempfile.TemporaryDirectory() as tempdir:
            dest_dir = Path(tempdir)
            existing = dest_dir / "remote-name.webm"
            existing.write_bytes(b"do not overwrite")
            download = MagicMock(suggested_filename="remote-name.webm")

            def save_as(path):
                Path(path).write_bytes(b"downloaded video")

            download.save_as.side_effect = save_as
            output = Path(
                yt_interface.download_video(
                    make_download_page(download), "report", dest_dir
                )
            )

            self.assertEqual(existing.read_bytes(), b"do not overwrite")
            self.assertEqual(output.parent, dest_dir)
            self.assertEqual(output.suffix, ".mp4")
            self.assertNotEqual(output.name, "remote-name.webm")
            self.assertEqual(output.read_bytes(), b"downloaded video")

    def test_download_removes_partial_unique_file_when_save_fails(self):
        with tempfile.TemporaryDirectory() as tempdir:
            dest_dir = Path(tempdir)
            existing = dest_dir / "keep.mp4"
            existing.write_bytes(b"keep")
            download = MagicMock(suggested_filename="suggested.mp4")

            def save_as(path):
                Path(path).write_bytes(b"partial")
                raise OSError("save failed")

            download.save_as.side_effect = save_as

            with self.assertRaises(OSError):
                yt_interface.download_video(make_download_page(download), "report", dest_dir)

            self.assertEqual(existing.read_bytes(), b"keep")
            self.assertEqual(sorted(dest_dir.iterdir()), [existing])


@unittest.skipUnless(CHROMIUM_PATH, "set YOUTUBE_DRIVE_TEST_BROWSER to run browser tests")
class RemoteSelectionBrowserTests(unittest.TestCase):
    def setUp(self):
        self.playwright = sync_playwright().start()
        if CHROMIUM_PATH == "chromium":
            self.browser = self.playwright.chromium.launch(headless=True)
        else:
            self.browser = self.playwright.chromium.launch(
                executable_path=CHROMIUM_PATH, headless=True
            )
        self.page = self.browser.new_page()

    def tearDown(self):
        self.browser.close()
        self.playwright.stop()

    def set_rows(self, titles):
        rows = "".join(
            f'''<div class="ytcp-video-list-cell-video right-section" data-title="{title}">
                <a id="video-title">{title}</a>
                <span class="other-text">report</span>
                <button aria-label="Options" onclick="window.actions.push('options:' + this.parentElement.dataset.title)">Options</button>
            </div>'''
            for title in titles
        )
        self.page.set_content(
            f'''<!doctype html><body>
                <script>window.actions = [];</script>
                {rows}
                <tp-yt-paper-item style="display:block" onclick="window.actions.push('delete')">Delete forever</tp-yt-paper-item>
                <ytcp-checkbox-lit id="confirm-checkbox" style="display:block;width:20px;height:20px" onclick="window.actions.push('confirm-checkbox')">Confirm</ytcp-checkbox-lit>
                <ytcp-button id="confirm-button" style="display:block;width:20px;height:20px" onclick="window.actions.push('confirm')">Confirm</ytcp-button>
            </body>'''
        )

    def test_delete_selects_only_exact_child_video_title(self):
        self.set_rows(["report", "report-final", "report[1]", "unrelated"])

        yt_interface.delete_video(self.page, "report")

        self.assertEqual(
            self.page.evaluate("window.actions"),
            ["options:report", "delete", "confirm-checkbox", "confirm"],
        )

    def test_delete_selects_punctuation_title_exactly(self):
        self.set_rows(["report", "report-final", "report[1]"])

        yt_interface.delete_video(self.page, "report[1]")

        self.assertEqual(
            self.page.evaluate("window.actions"),
            ["options:report[1]", "delete", "confirm-checkbox", "confirm"],
        )

    def test_delete_rejects_missing_title_before_remote_actions(self):
        self.set_rows(["report-final", "report[1]"])

        with self.assertRaises(Exception):
            yt_interface.delete_video(self.page, "report")

        self.assertEqual(self.page.evaluate("window.actions"), [])

    def test_delete_rejects_duplicate_exact_titles_before_remote_actions(self):
        self.set_rows(["report", "report"])

        with self.assertRaises(Exception):
            yt_interface.delete_video(self.page, "report")

        self.assertEqual(self.page.evaluate("window.actions"), [])


if __name__ == "__main__":
    unittest.main()
