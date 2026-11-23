"""
CaptionReportStorage: the CSV file of a caption length report. Plain dictionaries
only, temporary files, no Domain, no engine.
"""

import csv
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.infrastructure.storage.caption_report_storage import (
    CaptionReportStorage,
    CaptionReportStorageError,
)


class CaptionReportStorageTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.path = Path(self.tmp) / "report.csv"

    def read(self):
        with open(self.path, encoding="utf-8-sig", newline="") as handle:
            return list(csv.reader(handle))

    def test_accents_quotes_commas_and_line_breaks_survive_a_round_trip(self):
        tricky = 'Kaëlya "woman", crème brûlée\nligne 2\r\nligne 3 « guillemets » ; fin'
        rows = [{"a": "1", "b": tricky}, {"a": "", "b": "plain"}]

        CaptionReportStorage.write(self.path, ("a", "b"), rows)

        parsed = self.read()
        self.assertEqual(parsed[0], ["a", "b"])
        self.assertEqual(parsed[1], ["1", tricky])
        self.assertEqual(parsed[2], ["", "plain"])
        self.assertTrue(self.path.read_bytes().startswith(b"\xef\xbb\xbf"))   # UTF-8 with BOM

    def test_overwriting_replaces_the_previous_report_and_leaves_no_temporary_file(self):
        CaptionReportStorage.write(self.path, ("a",), [{"a": "old"}])
        CaptionReportStorage.write(self.path, ("a",), [{"a": "new"}])

        self.assertEqual(self.read(), [["a"], ["new"]])
        self.assertEqual([p.name for p in Path(self.tmp).iterdir()], ["report.csv"])

    def test_a_failure_leaves_no_half_written_report_and_no_temporary_file(self):
        with patch("src.infrastructure.storage.caption_report_storage.os.replace", side_effect=OSError("denied")):
            with self.assertRaises(CaptionReportStorageError):
                CaptionReportStorage.write(self.path, ("a",), [{"a": "x"}])

        self.assertEqual(list(Path(self.tmp).iterdir()), [])

    def test_an_unknown_column_is_refused_and_cleaned_up(self):
        with self.assertRaises(CaptionReportStorageError):
            CaptionReportStorage.write(self.path, ("a",), [{"a": "x", "extra": "y"}])

        self.assertEqual(list(Path(self.tmp).iterdir()), [])

    def test_nothing_is_written_when_the_directory_is_not_creatable(self):
        blocker = Path(self.tmp) / "file"
        blocker.write_text("x")

        with self.assertRaises(CaptionReportStorageError):
            CaptionReportStorage.write(blocker / "sub" / "r.csv", ("a",), [{"a": "x"}])


if __name__ == "__main__":
    unittest.main()
