import shutil
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path

from kindle_extractor.book_selection_service import (
    BATCH_CLEAR_VISIBLE,
    BATCH_RECOMMENDED,
    BATCH_SELECT_VISIBLE,
    FILTER_NO_NEWS,
    FILTER_SELECTED,
    FILTER_WITH_NEWS,
    STATUS_NEVER_EXPORTED,
    STATUS_NEW,
    STATUS_NO_NEWS,
    STATUS_WITH_NEWS,
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
        "date_obj": datetime(2024, 1, 1, tzinfo=timezone.utc),
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

        row = rows[0]
        self.assertEqual(row["status"], STATUS_NEW)
        self.assertTrue(row["default_selected"])
        self.assertEqual(row["new_highlights_count"], 1)
        self.assertEqual(row["last_export_display"], "-")

    def test_classifies_previously_analyzed_but_never_exported(self):
        books = {"Livro A": [make_entry(title="Livro A", author="Autor A")]}
        self.service.build_books_table(
            books,
            persist=True,
            processed_at=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
        )

        rows = self.service.build_books_table(books, persist=False)
        row = rows[0]

        self.assertEqual(row["status"], STATUS_NEVER_EXPORTED)
        self.assertTrue(row["default_selected"])
        self.assertEqual(row["new_highlights_count"], 1)

    def test_classifies_exported_without_news_as_not_selected(self):
        books = {"Livro A": [make_entry(title="Livro A", author="Autor A")]}
        rows = self.service.build_books_table(
            books,
            persist=True,
            processed_at=datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc),
        )

        self.service.mark_exported(
            [rows[0]["book_key"]],
            exported_at=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
            export_formats=["markdown"],
        )

        row = self.service.build_books_table(books, persist=False)[0]
        self.assertEqual(row["status"], STATUS_NO_NEWS)
        self.assertFalse(row["default_selected"])
        self.assertEqual(row["new_highlights_count"], 0)

    def test_classifies_exported_with_news_since_last_export(self):
        books_v1 = {
            "Livro A": [make_entry(title="Livro A", author="Autor A", start_pos=10, end_pos=12)]
        }
        first_rows = self.service.build_books_table(
            books_v1,
            persist=True,
            processed_at=datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc),
        )
        self.service.mark_exported(
            [first_rows[0]["book_key"]],
            exported_at=datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc),
            export_formats=["markdown"],
        )

        books_v2 = {
            "Livro A": [
                make_entry(title="Livro A", author="Autor A", start_pos=10, end_pos=12),
                make_entry(
                    title="Livro A",
                    author="Autor A",
                    start_pos=20,
                    end_pos=22,
                    content="novo destaque",
                ),
            ]
        }
        row = self.service.build_books_table(books_v2, persist=False)[0]

        self.assertEqual(row["status"], STATUS_WITH_NEWS)
        self.assertTrue(row["default_selected"])
        self.assertEqual(row["new_highlights_count"], 1)

    def test_orders_books_by_export_guided_status_then_title(self):
        base_books = {
            "Sem Novidades": [make_entry(title="Sem Novidades", author="Autor A")],
            "Com Novidades": [make_entry(title="Com Novidades", author="Autor B")],
            "Nunca Exportado": [make_entry(title="Nunca Exportado", author="Autor C")],
        }
        initial_rows = self.service.build_books_table(
            base_books,
            persist=True,
            processed_at=datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc),
        )
        keys = {row["title"]: row["book_key"] for row in initial_rows}

        self.service.mark_exported(
            [keys["Sem Novidades"], keys["Com Novidades"]],
            exported_at=datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc),
            export_formats=["markdown"],
        )

        books_after = {
            "Sem Novidades": [make_entry(title="Sem Novidades", author="Autor A")],
            "Com Novidades": [
                make_entry(title="Com Novidades", author="Autor B"),
                make_entry(
                    title="Com Novidades",
                    author="Autor B",
                    start_pos=40,
                    end_pos=42,
                    content="destaque novo",
                ),
            ],
            "Nunca Exportado": [make_entry(title="Nunca Exportado", author="Autor C")],
            "Apenas Novo": [make_entry(title="Apenas Novo", author="Autor D")],
        }

        rows = self.service.build_books_table(books_after, persist=False)

        self.assertEqual(
            [(row["title"], row["status"]) for row in rows],
            [
                ("Apenas Novo", STATUS_NEW),
                ("Nunca Exportado", STATUS_NEVER_EXPORTED),
                ("Com Novidades", STATUS_WITH_NEWS),
                ("Sem Novidades", STATUS_NO_NEWS),
            ],
        )

    def test_filters_and_search_use_visible_set(self):
        books = {
            "Sem Novidades": [make_entry(title="Sem Novidades", author="Autor A")],
            "Com Novidades": [make_entry(title="Com Novidades", author="Autor B")],
        }
        rows = self.service.build_books_table(
            books,
            persist=True,
            processed_at=datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc),
        )
        keys = {row["title"]: row["book_key"] for row in rows}
        self.service.mark_exported(
            [keys["Sem Novidades"], keys["Com Novidades"]],
            exported_at=datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc),
            export_formats=["markdown"],
        )

        rows = self.service.build_books_table(
            {
                "Sem Novidades": [make_entry(title="Sem Novidades", author="Autor A")],
                "Com Novidades": [
                    make_entry(title="Com Novidades", author="Autor B"),
                    make_entry(
                        title="Com Novidades",
                        author="Autor B",
                        start_pos=50,
                        end_pos=55,
                        content="novo",
                    ),
                ],
            },
            persist=False,
        )

        selection_map = self.service.build_default_selection_map(rows)
        selection_map[keys["Sem Novidades"]] = True

        only_news = self.service.filter_rows(
            rows,
            selection_map=selection_map,
            status_filter=FILTER_WITH_NEWS,
        )
        self.assertEqual([row["title"] for row in only_news], ["Com Novidades"])

        only_no_news = self.service.filter_rows(
            rows,
            selection_map=selection_map,
            status_filter=FILTER_NO_NEWS,
        )
        self.assertEqual([row["title"] for row in only_no_news], ["Sem Novidades"])

        searched = self.service.filter_rows(rows, selection_map=selection_map, search_term="com")
        self.assertEqual([row["title"] for row in searched], ["Com Novidades"])

        selected_only = self.service.filter_rows(
            rows,
            selection_map=selection_map,
            status_filter=FILTER_SELECTED,
        )
        self.assertEqual([row["title"] for row in selected_only], ["Com Novidades", "Sem Novidades"])

    def test_batch_actions_affect_only_visible_rows(self):
        rows = [
            {
                "book_key": "a",
                "default_selected": True,
                "status": STATUS_NEW,
                "title": "A",
                "author": "Autor",
                "highlights": 1,
            },
            {
                "book_key": "b",
                "default_selected": False,
                "status": STATUS_NO_NEWS,
                "title": "B",
                "author": "Autor",
                "highlights": 1,
            },
            {
                "book_key": "c",
                "default_selected": True,
                "status": STATUS_WITH_NEWS,
                "title": "C",
                "author": "Autor",
                "highlights": 1,
            },
        ]
        selection_map = {"a": False, "b": False, "c": False}

        selection_map = self.service.apply_batch_action(
            rows,
            selection_map,
            visible_book_keys=["a", "b"],
            action=BATCH_SELECT_VISIBLE,
        )
        self.assertEqual(selection_map, {"a": True, "b": True, "c": False})

        selection_map = self.service.apply_batch_action(
            rows,
            selection_map,
            visible_book_keys=["b"],
            action=BATCH_CLEAR_VISIBLE,
        )
        self.assertEqual(selection_map, {"a": True, "b": False, "c": False})

        selection_map = self.service.apply_batch_action(
            rows,
            selection_map,
            visible_book_keys=["a", "b"],
            action=BATCH_RECOMMENDED,
        )
        self.assertEqual(selection_map, {"a": True, "b": False, "c": False})


if __name__ == "__main__":
    unittest.main()
