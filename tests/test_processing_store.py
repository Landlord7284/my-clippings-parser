import json
import shutil
import unittest
import uuid
from datetime import datetime
from pathlib import Path

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

    def test_load_returns_default_when_file_is_missing(self):
        payload = self.store.load()
        self.assertEqual(payload["version"], 2)
        self.assertEqual(payload["books"], {})

    def test_load_returns_default_when_file_is_corrupted(self):
        self.store_path.write_text("{invalid-json", encoding="utf-8")
        payload = self.store.load()
        self.assertEqual(payload["version"], 2)
        self.assertEqual(payload["books"], {})

    def test_load_sanitizes_incomplete_legacy_book_shape(self):
        legacy_payload = {
            "version": 1,
            "books": {
                "book-key": {
                    "title": "Livro",
                    "author": "Autor",
                    "entry_signatures": ["raw-signature"],
                    "highlight_count": "2",
                }
            },
        }
        self.store.save(legacy_payload)

        books = self.store.get_books()
        self.assertIn("book-key", books)
        book = books["book-key"]
        self.assertEqual(book["title"], "Livro")
        self.assertEqual(book["highlight_count"], 2)
        self.assertEqual(len(book["entry_signature_hashes"]), 1)
        self.assertIn("processing_history", book)
        self.assertIn("export_history", book)

    def test_save_processed_snapshots_creates_history_and_hashes(self):
        snapshot = {
            "book-key": {
                "book_key": "book-key",
                "title": "Livro",
                "author": "Autor",
                "entry_signature_hashes": ["a" * 40],
                "highlight_signature_hashes": ["b" * 40],
                "highlight_count": 1,
                "note_count": 0,
                "bookmark_count": 0,
            }
        }
        self.store.save_processed_snapshots(
            snapshot,
            processed_at=datetime(2024, 1, 1, 12, 0),
        )

        book = self.store.get_books()["book-key"]
        self.assertEqual(book["last_processed_at"], "2024-01-01T12:00:00")
        self.assertEqual(book["last_detected_processing"]["detected_status"], "novo")
        self.assertEqual(len(book["processing_history"]), 1)
        self.assertEqual(book["content_signature_hash"], book["processing_history"][0]["content_signature_hash"])

    def test_reexport_without_changes_is_flagged(self):
        snapshot = {
            "book-key": {
                "book_key": "book-key",
                "title": "Livro",
                "author": "Autor",
                "entry_signature_hashes": ["a" * 40],
                "highlight_signature_hashes": ["b" * 40],
                "highlight_count": 1,
                "note_count": 0,
                "bookmark_count": 0,
            }
        }
        self.store.save_processed_snapshots(snapshot, processed_at=datetime(2024, 1, 1, 8, 0))

        self.store.mark_exported(
            {"book-key": ["markdown"]},
            exported_at=datetime(2024, 1, 1, 9, 0),
        )
        self.store.mark_exported(
            {"book-key": ["markdown", "html"]},
            exported_at=datetime(2024, 1, 1, 10, 0),
        )

        book = self.store.get_books()["book-key"]
        self.assertEqual(book["last_exported_at"], "2024-01-01T10:00:00")
        self.assertEqual(book["last_export_formats"], ["html", "markdown"])
        self.assertEqual(len(book["export_history"]), 2)
        self.assertFalse(book["export_history"][0]["reexport_without_changes"])
        self.assertTrue(book["export_history"][1]["reexport_without_changes"])

    def test_compare_snapshot_detects_updated(self):
        snapshot_v1 = {
            "book-key": {
                "book_key": "book-key",
                "title": "Livro",
                "author": "Autor",
                "entry_signature_hashes": ["a" * 40],
                "highlight_signature_hashes": ["b" * 40],
                "highlight_count": 1,
                "note_count": 0,
                "bookmark_count": 0,
            }
        }
        self.store.save_processed_snapshots(snapshot_v1, processed_at=datetime(2024, 1, 1, 8, 0))

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


if __name__ == "__main__":
    unittest.main()
