from datetime import datetime, timezone

from kindle_extractor.book_selection_service import (
    STATUS_NEVER_EXPORTED,
    STATUS_NO_NEWS,
    STATUS_WITH_NEWS,
    BookSelectionService,
)
from kindle_extractor.datetime_utils import format_iso_for_display, to_utc_iso
from kindle_extractor.processing_store import ProcessingStore


def test_load_returns_default_payload_when_store_is_missing(workspace_tmp_path):
    store = ProcessingStore(workspace_tmp_path / "state.json")

    payload = store.load()

    assert payload["version"] == 2
    assert payload["books"] == {}


def test_load_handles_corrupted_or_incomplete_payload_with_safe_fallback(workspace_tmp_path):
    store_path = workspace_tmp_path / "state.json"
    store_path.write_text('{"version": 2, "books": {"book-key": {"title": "Livro"}}}', encoding="utf-8")

    store = ProcessingStore(store_path)
    book = store.get_books()["book-key"]

    assert book["author"] == "Autor desconhecido"
    assert book["entry_signature_hashes"] == []
    assert book["processing_history"] == []


def test_save_processed_snapshots_persists_last_analysis_as_utc_iso(
    workspace_tmp_path,
    snapshot_factory,
):
    store = ProcessingStore(workspace_tmp_path / "state.json")

    store.save_processed_snapshots(snapshot_factory(), processed_at=datetime(2024, 1, 1, 12, 0))

    book = store.get_books()["book-key"]
    assert book["last_analysis_at"] == "2024-01-01T12:00:00+00:00"
    assert book["last_processed_at"] == "2024-01-01T12:00:00+00:00"


def test_mark_exported_keeps_last_analysis_and_last_export_separated(
    workspace_tmp_path,
    snapshot_factory,
):
    store = ProcessingStore(workspace_tmp_path / "state.json")
    store.save_processed_snapshots(
        snapshot_factory(),
        processed_at=datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc),
    )

    store.mark_exported(
        {"book-key": ["markdown", "html"]},
        exported_at=datetime(2024, 1, 1, 10, 30, tzinfo=timezone.utc),
    )

    book = store.get_books()["book-key"]
    assert book["last_analysis_at"] == "2024-01-01T09:00:00+00:00"
    assert book["last_export_at"] == "2024-01-01T10:30:00+00:00"
    assert book["last_export_formats"] == ["html", "markdown"]


def test_novelty_status_for_never_exported_book(workspace_tmp_path, entry_factory):
    store = ProcessingStore(workspace_tmp_path / "state.json")
    service = BookSelectionService(store)
    books = {"Livro A": [entry_factory(title="Livro A", author="Autor A")]}

    service.build_books_table(
        books,
        persist=True,
        processed_at=datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc),
    )
    row = service.build_books_table(books, persist=False)[0]

    assert row["status"] == STATUS_NEVER_EXPORTED
    assert row["new_highlights_count"] == 1


def test_novelty_status_for_exported_book_without_news(workspace_tmp_path, entry_factory):
    store = ProcessingStore(workspace_tmp_path / "state.json")
    service = BookSelectionService(store)
    books = {"Livro A": [entry_factory(title="Livro A", author="Autor A")]}

    rows = service.build_books_table(
        books,
        persist=True,
        processed_at=datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc),
    )
    service.mark_exported(
        [rows[0]["book_key"]],
        exported_at=datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc),
        export_formats=["markdown"],
    )

    row = service.build_books_table(books, persist=False)[0]
    assert row["status"] == STATUS_NO_NEWS
    assert row["new_highlights_count"] == 0


def test_novelty_status_for_exported_book_with_news(workspace_tmp_path, entry_factory):
    store = ProcessingStore(workspace_tmp_path / "state.json")
    service = BookSelectionService(store)

    first_books = {"Livro A": [entry_factory(title="Livro A", author="Autor A", start_pos=10, end_pos=12)]}
    rows = service.build_books_table(
        first_books,
        persist=True,
        processed_at=datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc),
    )
    service.mark_exported(
        [rows[0]["book_key"]],
        exported_at=datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc),
        export_formats=["markdown"],
    )

    second_books = {
        "Livro A": [
            entry_factory(title="Livro A", author="Autor A", start_pos=10, end_pos=12),
            entry_factory(
                title="Livro A",
                author="Autor A",
                start_pos=20,
                end_pos=22,
                content="novo destaque",
            ),
        ]
    }

    row = service.build_books_table(second_books, persist=False)[0]
    assert row["status"] == STATUS_WITH_NEWS
    assert row["new_highlights_count"] == 1


def test_to_utc_iso_serializes_naive_datetime_as_utc():
    value = to_utc_iso(datetime(2024, 1, 1, 12, 0))

    assert value == "2024-01-01T12:00:00+00:00"


def test_format_iso_for_display_uses_america_sao_paulo_timezone():
    display_value = format_iso_for_display("2024-01-01T12:00:00+00:00")

    assert display_value == "2024-01-01 09:00"


def test_concurrent_store_instances_preserve_all_snapshot_updates(workspace_tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    store_path = workspace_tmp_path / "state.json"
    book_count = 20

    def save_book(index: int):
        book_key = f"book-{index}"
        ProcessingStore(store_path).save_processed_snapshots(
            {
                book_key: {
                    "book_key": book_key,
                    "title": f"Livro {index}",
                    "author": "Autor",
                    "entry_signature_hashes": [f"{index:040x}"],
                    "highlight_signature_hashes": [f"{index + 100:040x}"],
                    "highlight_count": 1,
                    "note_count": 0,
                    "bookmark_count": 0,
                }
            },
            processed_at=datetime(2024, 1, 1, 12, index, tzinfo=timezone.utc),
        )

    with ThreadPoolExecutor(max_workers=book_count) as executor:
        list(executor.map(save_book, range(book_count)))

    books = ProcessingStore(store_path).get_books()
    assert set(books) == {f"book-{index}" for index in range(book_count)}
    assert not list(workspace_tmp_path.glob("state.json.*.tmp"))
