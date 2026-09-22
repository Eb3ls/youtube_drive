import os
import random
import tempfile
import unittest
from pathlib import Path

import reedsolo

import codec


KEY = b"0123456789abcdef"


class CodecRoundTripTests(unittest.TestCase):
    def setUp(self):
        self._cwd = os.getcwd()
        self._tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tempdir.name)
        self.source_dir = self.root / "source"
        self.source_dir.mkdir()
        os.chdir(self.root)
        self.rsc = reedsolo.RSCodec(codec.RS_ERROR_CORRECTION_BYTES)

    def tearDown(self):
        os.chdir(self._cwd)
        self._tempdir.cleanup()

    def round_trip(self, filename, contents):
        source = self.source_dir / filename
        source.write_bytes(contents)
        video = self.root / "encoded.mp4"
        codec.convert_file_to_video(str(source), str(video), KEY, self.rsc)
        codec.extract_file_from_video(str(video), KEY, self.rsc)
        return video, self.root / filename

    def test_round_trip_text_file(self):
        _, restored = self.round_trip("note.txt", b"hello from a text file\n")

        self.assertEqual(restored.read_bytes(), b"hello from a text file\n")

    def test_round_trip_large_seeded_random_data(self):
        data = random.Random(0).randbytes(80_000)
        _, restored = self.round_trip("random.bin", data)

        self.assertEqual(restored.read_bytes(), data)

    def test_round_trip_empty_file(self):
        _, restored = self.round_trip("empty.bin", b"")

        self.assertEqual(restored.read_bytes(), b"")

    def test_round_trip_unicode_filename(self):
        _, restored = self.round_trip("résumé.txt", b"unicode filename")

        self.assertEqual(restored.read_bytes(), b"unicode filename")

    def test_round_trip_extensionless_filename(self):
        _, restored = self.round_trip("README", b"extensionless")

        self.assertTrue(restored.exists())
        self.assertEqual(restored.read_bytes(), b"extensionless")
        self.assertFalse((self.root / "README.").exists())

    def test_round_trip_hidden_dotfile(self):
        _, restored = self.round_trip(".env", b"TOKEN=value\n")

        self.assertEqual(restored.read_bytes(), b"TOKEN=value\n")

    def test_restore_collision_uses_suffix_without_overwriting(self):
        existing = self.root / "report.txt"
        existing.write_bytes(b"existing contents")

        self.round_trip("report.txt", b"restored contents")

        self.assertEqual(existing.read_bytes(), b"existing contents")
        self.assertEqual((self.root / "report_1.txt").read_bytes(), b"restored contents")

    def test_extract_keeps_caller_supplied_video(self):
        video, restored = self.round_trip("keep-video.txt", b"do not delete video")

        self.assertTrue(video.exists())
        self.assertEqual(restored.read_bytes(), b"do not delete video")

    def test_wrong_key_leaves_existing_files_intact(self):
        source = self.source_dir / "secret.txt"
        source.write_bytes(b"protected payload")
        video = self.root / "encoded.mp4"
        codec.convert_file_to_video(str(source), str(video), KEY, self.rsc)
        existing = self.root / "secret.txt"
        existing.write_bytes(b"do not change")

        with self.assertRaises(ValueError):
            codec.extract_file_from_video(str(video), b"abcdef0123456789", self.rsc)

        self.assertTrue(video.exists())
        self.assertEqual(existing.read_bytes(), b"do not change")
        self.assertFalse((self.root / "secret_1.txt").exists())


if __name__ == "__main__":
    unittest.main()
