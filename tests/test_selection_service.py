from datetime import datetime, timezone

from kindle_extractor.book_selection_service import (
    STATUS_NEVER_EXPORTED,
    STATUS_NEW,
    STATUS_NO_NEWS,
    STATUS_WITH_NEWS,
    BookSelectionService,
)
from kindle_extractor.processing_store import ProcessingStore


def test_status_classification_and_default_selection(workspace_tmp_path, entry_factory):
    store = ProcessingStore(workspace_tmp_path / "state.json")
    service = BookSelectionService(store)

    books = {"Livro A": [entry_factory(title="Livro A", author="Autor A")]}
    rows = service.build_books_table(books, persist=False)

    assert rows[0]["status"] == STATUS_NEW
    assert rows[0]["default_selected"] is True


def test_priority_sorting_by_status_then_title(workspace_tmp_path, entry_factory):
    store = ProcessingStore(workspace_tmp_path / "state.json")
    service = BookSelectionService(store)

    base_books = {
        "Sem Novidades": [entry_factory(title="Sem Novidades", author="Autor A")],
        "Com Novidades": [entry_factory(title="Com Novidades", author="Autor B")],
        "Nunca Exportado": [entry_factory(title="Nunca Exportado", author="Autor C")],
        "Ainda Nunca Exportado": [
            entry_factory(title="Ainda Nunca Exportado", author="Autor D")
        ],
    }

    initial_rows = service.build_books_table(
        base_books,
        persist=True,
        processed_at=datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc),
    )
    keys = {row["title"]: row["book_key"] for row in initial_rows}

    service.mark_exported(
        [keys["Sem Novidades"], keys["Com Novidades"]],
        exported_at=datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc),
        export_formats=["markdown"],
    )

    books_after = {
        "Sem Novidades": [entry_factory(title="Sem Novidades", author="Autor A")],
        "Com Novidades": [
            entry_factory(title="Com Novidades", author="Autor B"),
            entry_factory(
                title="Com Novidades",
                author="Autor B",
                start_pos=40,
                end_pos=42,
                content="destaque novo",
            ),
        ],
        "Nunca Exportado": [entry_factory(title="Nunca Exportado", author="Autor C")],
        "Ainda Nunca Exportado": [
            entry_factory(title="Ainda Nunca Exportado", author="Autor D")
        ],
        "Apenas Novo": [entry_factory(title="Apenas Novo", author="Autor D")],
    }

    rows = service.build_books_table(books_after, persist=False)

    assert [(row["title"], row["status"]) for row in rows] == [
        ("Apenas Novo", STATUS_NEW),
        ("Com Novidades", STATUS_WITH_NEWS),
        ("Ainda Nunca Exportado", STATUS_NEVER_EXPORTED),
        ("Nunca Exportado", STATUS_NEVER_EXPORTED),
        ("Sem Novidades", STATUS_NO_NEWS),
    ]


def test_status_labels_are_compact(workspace_tmp_path, entry_factory):
    store = ProcessingStore(workspace_tmp_path / "state.json")
    service = BookSelectionService(store)

    rows = service.build_books_table(
        {"Livro A": [entry_factory(title="Livro A", author="Autor A")]},
        persist=False,
    )

    assert rows[0]["status_label"] == "Novo"

