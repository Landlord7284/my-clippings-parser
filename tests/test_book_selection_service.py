import shutil
import unittest
import uuid
from datetime import datetime
from pathlib import Path

from kindle_extractor.book_selection_service import (
    STATUS_NEW,
    STATUS_UNCHANGED,
    STATUS_UPDATED,
    BookSelectionService,
)
from kindle_extractor.processing_store import ProcessingStore


def make_entry(
    entry_type="highlight",
    title="Livro",
    author="Autor",
    start_pos=10,
    end_pos=12,
    content="Trecho",
):
    return {
        "type": entry_type,
        "title": title,
        "author": author,
        "page": 1,
        "start_pos": start_pos,
        "end_pos": end_pos,
        "content": content,
        "date_formatted": "1 de janeiro de 2024",
        "date_obj": datetime(2024, 1, 1),
        "metadata_line": "",
    }


class BookSelectionServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp_root = Path("tests") / f".tmp_state_{uuid.uuid4().hex}"
        self.tmp_root.mkdir(parents=True, exist_ok=True)
        self.store = ProcessingStore(self.tmp_root / "state.json")
        self.service = BookSelectionService(self.store)

    def tearDown(self):
        if self.tmp_root.exists():
            shutil.rmtree(self.tmp_root)

    def test_classifies_new_book_and_marks_default_selected(self):
        books = {"Livro A": [make_entry(title="Livro A", author="Autor A")]}
        rows = self.service.build_books_table(books, persist=False)

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["status"], STATUS_NEW)
        self.assertTrue(row["default_selected"])
        self.assertEqual(row["new_highlights_count"], 1)
        self.assertEqual(row["last_processed_display"], "-")

    def test_classifies_unchanged_book_and_unselects_by_default(self):
        books = {"Livro A": [make_entry(title="Livro A", author="Autor A")]}
        self.service.build_books_table(books, persist=True, processed_at=datetime(2024, 1, 1))

        rows = self.service.build_books_table(books, persist=False)
        row = rows[0]
        self.assertEqual(row["status"], STATUS_UNCHANGED)
        self.assertFalse(row["default_selected"])
        self.assertFalse(row["has_new_highlights"])
        self.assertNotEqual(row["last_processed_display"], "-")

    def test_detects_new_highlights_using_signature_not_only_count(self):
        books_v1 = {
            "Livro A": [make_entry(title="Livro A", author="Autor A", start_pos=10, end_pos=12)]
        }
        self.service.build_books_table(
            books_v1,
            persist=True,
            processed_at=datetime(2024, 1, 1, 10, 0),
        )

        books_v2 = {
            "Livro A": [
                make_entry(title="Livro A", author="Autor A", start_pos=10, end_pos=12),
                make_entry(
                    title="Livro A",
                    author="Autor A",
                    start_pos=30,
                    end_pos=33,
                    content="novo trecho",
                ),
            ]
        }
        rows = self.service.build_books_table(books_v2, persist=False)
        row = rows[0]

        self.assertEqual(row["status"], STATUS_UPDATED)
        self.assertEqual(row["new_highlights_count"], 1)
        self.assertTrue(row["has_new_highlights"])
        self.assertTrue(row["default_selected"])

    def test_updated_without_new_highlights_stays_unselected(self):
        books_v1 = {
            "Livro A": [make_entry(title="Livro A", author="Autor A", content="texto base")]
        }
        self.service.build_books_table(books_v1, persist=True)

        books_v2 = {
            "Livro A": [
                make_entry(title="Livro A", author="Autor A", content="texto base"),
                make_entry(
                    entry_type="note",
                    title="Livro A",
                    author="Autor A",
                    start_pos=40,
                    end_pos=40,
                    content="minha nota",
                ),
            ]
        }
        row = self.service.build_books_table(books_v2, persist=False)[0]

        self.assertEqual(row["status"], STATUS_UPDATED)
        self.assertEqual(row["new_highlights_count"], 0)
        self.assertFalse(row["has_new_highlights"])
        self.assertFalse(row["default_selected"])

    def test_orders_books_prioritizing_new_and_updated(self):
        self.service.build_books_table(
            {"Livro Antigo": [make_entry(title="Livro Antigo", author="Autor A")]},
            persist=True,
        )

        books = {
            "Livro Antigo": [make_entry(title="Livro Antigo", author="Autor A")],
            "Livro Atualizado": [
                make_entry(title="Livro Atualizado", author="Autor B"),
                make_entry(
                    title="Livro Atualizado",
                    author="Autor B",
                    start_pos=50,
                    end_pos=51,
                    content="novo trecho",
                ),
            ],
            "Livro Novo": [make_entry(title="Livro Novo", author="Autor C")],
        }
        self.service.build_books_table(
            {"Livro Atualizado": [make_entry(title="Livro Atualizado", author="Autor B")]},
            persist=True,
        )

        rows = self.service.build_books_table(books, persist=False)
        ordered_titles = [row["title"] for row in rows]
        ordered_statuses = [row["status"] for row in rows]

        self.assertEqual(ordered_titles[0], "Livro Novo")
        self.assertEqual(ordered_statuses[0], STATUS_NEW)
        self.assertEqual(ordered_statuses[1], STATUS_UPDATED)
        self.assertEqual(ordered_statuses[2], STATUS_UNCHANGED)

    def test_force_reprocess_is_recorded_without_changing_status(self):
        books = {"Livro A": [make_entry(title="Livro A", author="Autor A")]}
        self.service.build_books_table(
            books,
            persist=True,
            processed_at=datetime(2024, 1, 1, 10, 0),
        )

        rows = self.service.build_books_table(
            books,
            persist=True,
            processed_at=datetime(2024, 1, 2, 11, 0),
            force_reprocess=True,
        )
        self.assertEqual(rows[0]["status"], STATUS_UNCHANGED)

        persisted = self.store.get_books()[rows[0]["book_key"]]
        self.assertEqual(len(persisted["processing_history"]), 2)
        self.assertTrue(persisted["processing_history"][-1]["forced"])
        self.assertEqual(
            persisted["processing_history"][-1]["detected_status"],
            STATUS_UNCHANGED,
        )

    def test_marks_export_formats_and_keeps_processing_export_timestamps_distinct(self):
        books = {"Livro A": [make_entry(title="Livro A", author="Autor A")]}
        rows = self.service.build_books_table(
            books,
            persist=True,
            processed_at=datetime(2024, 1, 1, 9, 0),
        )

        self.service.mark_exported(
            [rows[0]["book_key"]],
            exported_at=datetime(2024, 1, 1, 10, 30),
            export_formats=["markdown", "html"],
        )

        persisted = self.store.get_books()[rows[0]["book_key"]]
        self.assertEqual(persisted["last_processed_at"], "2024-01-01T09:00:00")
        self.assertEqual(persisted["last_exported_at"], "2024-01-01T10:30:00")
        self.assertEqual(persisted["last_export_formats"], ["html", "markdown"])
        self.assertEqual(persisted["export_history"][-1]["formats"], ["html", "markdown"])


if __name__ == "__main__":
    unittest.main()
