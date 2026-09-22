import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

import app


class TransferFileSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def setUp(self):
        self.previous_cwd = Path.cwd()
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        os.chdir(self.root)
        with patch("app.get_video_list", return_value=[]):
            self.window = app.FileTransferWindow(None, None, None)
        self.errors = []
        self.window.show_error_popup = self.errors.append

    def tearDown(self):
        self.window.close()
        os.chdir(self.previous_cwd)
        self.directory.cleanup()

    def run_upload(self, filename, title, failure=None):
        intermediates = []
        uploaded = []

        def encode(source, output, key, rsc):
            output = Path(output)
            intermediates.append(output)
            output.write_bytes(b"encoded video")
            if failure == "encode":
                raise RuntimeError("encoding failed")

        def upload(output, page):
            uploaded.append(Path(output).read_bytes())
            if failure == "upload":
                raise RuntimeError("upload failed")

        with patch("app.QInputDialog.getText", return_value=(title, True)), \
                patch("app.convert_file_to_video", side_effect=encode), \
                patch("app.upload_video_to_youtube", side_effect=upload):
            self.window.process_local_file(filename)
        return intermediates, uploaded

    def test_upload_mp4_preserves_source(self):
        source = self.root / "holiday.mp4"
        source.write_bytes(b"original movie")

        intermediates, uploaded = self.run_upload(source.name, "holiday")

        self.assertEqual(source.read_bytes(), b"original movie")
        self.assertEqual(uploaded, [b"encoded video"])
        self.assertEqual(intermediates[0].name, "holiday.mp4")
        self.assertFalse(intermediates[0].exists())
        self.assertFalse(self.errors)

    def test_upload_preserves_existing_video_with_same_title(self):
        source = self.root / "report.txt"
        source.write_bytes(b"original document")
        existing = self.root / "report.mp4"
        existing.write_bytes(b"unrelated movie")

        intermediates, _ = self.run_upload(source.name, "report")

        self.assertEqual(source.read_bytes(), b"original document")
        self.assertEqual(existing.read_bytes(), b"unrelated movie")
        self.assertFalse(intermediates[0].exists())
        self.assertFalse(self.errors)

    def test_failed_upload_and_encoding_clean_only_temporary_files(self):
        source = self.root / "holiday.mp4"
        for failure in ("encode", "upload"):
            with self.subTest(failure=failure):
                source.write_bytes(b"original movie")
                intermediates, _ = self.run_upload(source.name, "holiday", failure)
                self.assertEqual(source.read_bytes(), b"original movie")
                self.assertFalse(intermediates[0].exists())
                self.assertEqual(self.window.right_list.count(), 0)
                self.assertIn("failed", self.errors[-1])

    def test_unsafe_title_is_rejected_before_encoding(self):
        source = self.root / "document.txt"
        source.write_bytes(b"original")
        for title in (
            "../escape", "/absolute", r"..\escape", "C:escape", "bad\x00title",
            "CON", "NUL", "COM1", "LPT9", "CON.txt", "aux", "COM¹",
        ):
            with self.subTest(title=title), \
                    patch("app.QInputDialog.getText", return_value=(title, True)), \
                    patch("app.convert_file_to_video") as encode, \
                    patch("app.upload_video_to_youtube") as upload:
                self.window.process_local_file(source.name)
                encode.assert_not_called()
                upload.assert_not_called()
                self.assertTrue(self.errors)
        self.assertEqual(source.read_bytes(), b"original")

    def run_download(self, failure=None):
        intermediates = []

        def download(page, title, destination):
            video = Path(destination) / "report.mp4"
            video.write_bytes(b"downloaded video")
            intermediates.append(video)
            if failure == "download":
                raise RuntimeError("download failed")
            return str(video)

        def extract(video, key, rsc):
            self.assertEqual(Path(video).read_bytes(), b"downloaded video")
            if failure == "decode":
                raise RuntimeError("decode failed")
            (self.root / "restored.txt").write_bytes(b"recovered contents")

        with patch("app.download_video", side_effect=download), \
                patch("app.extract_file_from_video", side_effect=extract):
            self.window.process_remote_file("report")
        return intermediates

    def test_download_preserves_local_video_and_cleans_temporary_copy(self):
        existing = self.root / "report.mp4"
        existing.write_bytes(b"original movie")

        intermediates = self.run_download()

        self.assertEqual(existing.read_bytes(), b"original movie")
        self.assertEqual((self.root / "restored.txt").read_bytes(), b"recovered contents")
        self.assertFalse(intermediates[0].exists())
        self.assertFalse(self.errors)

    def test_real_codec_transfer_preserves_original_and_restores_a_copy(self):
        source = self.root / "holiday.mp4"
        original = b"arbitrary file bytes with an mp4 filename\x00\xff"
        source.write_bytes(original)
        stored_video = []
        intermediates = []

        def upload(output, page):
            intermediates.append(Path(output))
            stored_video.append(Path(output).read_bytes())

        def download(page, title, destination):
            output = Path(destination) / "download.mp4"
            output.write_bytes(stored_video[0])
            intermediates.append(output)
            return str(output)

        with patch("app.QInputDialog.getText", return_value=("holiday", True)), \
                patch("app.upload_video_to_youtube", side_effect=upload):
            self.window.process_local_file(source.name)
        self.assertFalse(self.errors)
        self.assertEqual(source.read_bytes(), original)

        with patch("app.download_video", side_effect=download):
            self.window.process_remote_file("holiday")

        self.assertFalse(self.errors)
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual((self.root / "holiday_1.mp4").read_bytes(), original)
        self.assertTrue(all(not path.exists() for path in intermediates))

    def test_failed_download_and_decode_preserve_local_files(self):
        existing = self.root / "report.mp4"
        for failure in ("download", "decode"):
            with self.subTest(failure=failure):
                existing.write_bytes(b"original movie")
                intermediates = self.run_download(failure)
                self.assertEqual(existing.read_bytes(), b"original movie")
                self.assertFalse(intermediates[0].exists())
                self.assertFalse((self.root / "restored.txt").exists())
                self.assertIn("failed", self.errors[-1])


if __name__ == "__main__":
    unittest.main()
