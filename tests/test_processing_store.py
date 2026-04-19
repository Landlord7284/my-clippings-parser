import shutil
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path

from kindle_extractor.datetime_utils import format_iso_for_display
from kindle_extractor.processing_store import ProcessingStore


class ProcessingStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp_root = Path("tests") / f".tmp_store_{uuid.uuid4().hex}"
        self.tmp_root.mkdir(parents=True, exist_ok=True)
        self.store_path = self.tmp_root / "state.json"
        self.store = ProcessingStore(self.store_path)

    def tearDown(self):
        if self.tmp_root.exists():
            shutil.rmtree(self.tmp_root)

    def _snapshot(self, entry_hashes=None, highlight_hashes=None):
        return {
            "book-key": {
                "book_key": "book-key",
                "title": "Livro",
                "author": "Autor",
                "entry_signature_hashes": entry_hashes or ["a" * 40],
                "highlight_signature_hashes": highlight_hashes or ["b" * 40],
                "highlight_count": len(highlight_hashes or ["b" * 40]),
                "note_count": 0,
                "bookmark_count": 0,
            }
        }

    def test_load_returns_default_when_file_is_missing(self):
        payload = self.store.load()
        self.assertEqual(payload["version"], 2)
        self.assertEqual(payload["books"], {})

    def test_load_returns_default_when_file_is_corrupted(self):
        self.store_path.write_text("{invalid-json", encoding="utf-8")
        payload = self.store.load()
        self.assertEqual(payload["version"], 2)
        self.assertEqual(payload["books"], {})

    def test_save_processed_snapshots_persists_last_analysis_in_utc(self):
        self.store.save_processed_snapshots(
            self._snapshot(),
            processed_at=datetime(2024, 1, 1, 12, 0),
        )

        book = self.store.get_books()["book-key"]
        self.assertEqual(book["last_analysis_at"], "2024-01-01T12:00:00+00:00")
        self.assertEqual(book["last_processed_at"], "2024-01-01T12:00:00+00:00")
        self.assertEqual(book["last_detected_processing"]["detected_status"], "novo")
        self.assertEqual(len(book["processing_history"]), 1)

    def test_mark_exported_keeps_analysis_and_export_timestamps_distinct(self):
        self.store.save_processed_snapshots(
            self._snapshot(),
            processed_at=datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc),
        )

        self.store.mark_exported(
            {"book-key": ["markdown", "html"]},
            exported_at=datetime(2024, 1, 1, 10, 30, tzinfo=timezone.utc),
        )

        book = self.store.get_books()["book-key"]
        self.assertEqual(book["last_analysis_at"], "2024-01-01T09:00:00+00:00")
        self.assertEqual(book["last_export_at"], "2024-01-01T10:30:00+00:00")
        self.assertEqual(book["last_exported_at"], "2024-01-01T10:30:00+00:00")
        self.assertEqual(book["last_export_formats"], ["html", "markdown"])
        self.assertEqual(book["last_export_signature"], book["content_signature_hash"])
        self.assertEqual(
            book["last_export_highlight_signature_hashes"],
            ["b" * 40],
        )

    def test_reexport_without_changes_is_flagged(self):
        self.store.save_processed_snapshots(
            self._snapshot(),
            processed_at=datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc),
        )

        self.store.mark_exported(
            {"book-key": ["markdown"]},
            exported_at=datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc),
        )
        self.store.mark_exported(
            {"book-key": ["markdown", "html"]},
            exported_at=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
        )

        book = self.store.get_books()["book-key"]
        self.assertEqual(len(book["export_history"]), 2)
        self.assertFalse(book["export_history"][0]["reexport_without_changes"])
        self.assertTrue(book["export_history"][1]["reexport_without_changes"])

    def test_compare_snapshot_detects_updated(self):
        self.store.save_processed_snapshots(
            self._snapshot(entry_hashes=["a" * 40], highlight_hashes=["b" * 40]),
            processed_at=datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc),
        )

        current = {
            "book_key": "book-key",
            "entry_signature_hashes": ["a" * 40, "c" * 40],
            "highlight_signature_hashes": ["b" * 40, "d" * 40],
        }
        previous = self.store.get_books()["book-key"]
        result = self.store.compare_snapshot(current, previous=previous)

        self.assertEqual(result["status"], "atualizado")
        self.assertEqual(result["new_highlights_count"], 1)
        self.assertTrue(result["has_new_highlights"])

    def test_timezone_display_converts_utc_to_america_sao_paulo(self):
        display_value = format_iso_for_display("2024-01-01T12:00:00+00:00")
        self.assertEqual(display_value, "2024-01-01 09:00")


if __name__ == "__main__":
    unittest.main()
