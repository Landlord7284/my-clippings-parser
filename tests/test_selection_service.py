from datetime import datetime, timezone

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
        "Apenas Novo": [entry_factory(title="Apenas Novo", author="Autor D")],
    }

    rows = service.build_books_table(books_after, persist=False)

    assert [(row["title"], row["status"]) for row in rows] == [
        ("Apenas Novo", STATUS_NEW),
        ("Nunca Exportado", STATUS_NEVER_EXPORTED),
        ("Com Novidades", STATUS_WITH_NEWS),
        ("Sem Novidades", STATUS_NO_NEWS),
    ]


def test_filters_by_status_search_and_selected_only(workspace_tmp_path, entry_factory):
    store = ProcessingStore(workspace_tmp_path / "state.json")
    service = BookSelectionService(store)

    rows = service.build_books_table(
        {
            "Sem Novidades": [entry_factory(title="Sem Novidades", author="Autor A")],
            "Com Novidades": [entry_factory(title="Com Novidades", author="Autor B")],
        },
        persist=True,
        processed_at=datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc),
    )
    keys = {row["title"]: row["book_key"] for row in rows}

    service.mark_exported(
        [keys["Sem Novidades"], keys["Com Novidades"]],
        exported_at=datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc),
        export_formats=["markdown"],
    )

    rows = service.build_books_table(
        {
            "Sem Novidades": [entry_factory(title="Sem Novidades", author="Autor A")],
            "Com Novidades": [
                entry_factory(title="Com Novidades", author="Autor B"),
                entry_factory(
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

    selection_map = service.build_default_selection_map(rows)
    selection_map[keys["Sem Novidades"]] = True

    with_news = service.filter_rows(rows, selection_map=selection_map, status_filter=FILTER_WITH_NEWS)
    no_news = service.filter_rows(rows, selection_map=selection_map, status_filter=FILTER_NO_NEWS)
    searched = service.filter_rows(rows, selection_map=selection_map, search_term="autor b")
    selected = service.filter_rows(rows, selection_map=selection_map, status_filter=FILTER_SELECTED)

    assert [row["title"] for row in with_news] == ["Com Novidades"]
    assert [row["title"] for row in no_news] == ["Sem Novidades"]
    assert [row["title"] for row in searched] == ["Com Novidades"]
    assert [row["title"] for row in selected] == ["Com Novidades", "Sem Novidades"]


def test_batch_actions_apply_only_to_visible_items(workspace_tmp_path):
    service = BookSelectionService(ProcessingStore(workspace_tmp_path / "state.json"))

    rows = [
        {"book_key": "a", "default_selected": True, "status": STATUS_NEW, "title": "A", "author": "Autor", "highlights": 1},
        {"book_key": "b", "default_selected": False, "status": STATUS_NO_NEWS, "title": "B", "author": "Autor", "highlights": 1},
        {"book_key": "c", "default_selected": True, "status": STATUS_WITH_NEWS, "title": "C", "author": "Autor", "highlights": 1},
    ]
    selection_map = {"a": False, "b": False, "c": False}

    selection_map = service.apply_batch_action(
        rows,
        selection_map,
        visible_book_keys=["a", "b"],
        action=BATCH_SELECT_VISIBLE,
    )
    assert selection_map == {"a": True, "b": True, "c": False}

    selection_map = service.apply_batch_action(
        rows,
        selection_map,
        visible_book_keys=["b"],
        action=BATCH_CLEAR_VISIBLE,
    )
    assert selection_map == {"a": True, "b": False, "c": False}

    selection_map = service.apply_batch_action(
        rows,
        selection_map,
        visible_book_keys=["a", "b"],
        action=BATCH_RECOMMENDED,
    )
    assert selection_map == {"a": True, "b": False, "c": False}
