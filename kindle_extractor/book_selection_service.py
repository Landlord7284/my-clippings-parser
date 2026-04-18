import hashlib
import re
import unicodedata
from datetime import datetime
from typing import Dict, List, Optional, Tuple


STATUS_NEW = "novo"
STATUS_UPDATED = "atualizado"
STATUS_UNCHANGED = "sem mudanças"


def _normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "")
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def build_book_key(title: str, author: str) -> str:
    stable = f"{_normalize_text(title)}||{_normalize_text(author)}"
    return hashlib.sha1(stable.encode("utf-8")).hexdigest()


def build_entry_signature(entry: dict) -> str:
    entry_type = entry.get("type", "unknown")
    start_pos = entry.get("start_pos")
    end_pos = entry.get("end_pos")
    page = entry.get("page")
    normalized_content = _normalize_text(entry.get("content", ""))
    return f"{entry_type}|{start_pos}|{end_pos}|{page}|{normalized_content}"


def build_highlight_signature(entry: dict) -> str:
    entry_type = entry.get("type", "highlight")
    start_pos = entry.get("start_pos")
    end_pos = entry.get("end_pos")
    normalized_content = _normalize_text(entry.get("content", ""))
    return f"{entry_type}|{start_pos}|{end_pos}|{normalized_content}"


def _hash_signature(value: str) -> str:
    return hashlib.sha1((value or "").encode("utf-8")).hexdigest()


def _build_snapshot_hash(hashes: List[str]) -> str:
    if not hashes:
        return _hash_signature("")
    return _hash_signature("||".join(sorted(set(hashes))))


def _iso_to_display(value: Optional[str]) -> str:
    if not value:
        return "-"
    try:
        date_obj = datetime.fromisoformat(value)
        return date_obj.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return "-"


class BookSelectionService:
    def __init__(self, store):
        self.store = store

    def _build_snapshot(self, title: str, entries: List[dict]) -> dict:
        author = entries[0]["author"] if entries else "Autor desconhecido"
        entry_signature_hashes = sorted(
            {_hash_signature(build_entry_signature(entry)) for entry in entries}
        )
        highlight_signature_hashes = sorted(
            {
                _hash_signature(build_highlight_signature(entry))
                for entry in entries
                if entry.get("type") == "highlight"
            }
        )

        highlights = len([entry for entry in entries if entry.get("type") == "highlight"])
        notes = len([entry for entry in entries if entry.get("type") == "note"])
        bookmarks = len([entry for entry in entries if entry.get("type") == "bookmark"])

        return {
            "book_key": build_book_key(title, author),
            "title": title,
            "author": author,
            "entry_signature_hashes": entry_signature_hashes,
            "highlight_signature_hashes": highlight_signature_hashes,
            "content_signature_hash": _build_snapshot_hash(entry_signature_hashes),
            "highlight_signature_hash": _build_snapshot_hash(highlight_signature_hashes),
            "highlight_count": highlights,
            "note_count": notes,
            "bookmark_count": bookmarks,
        }

    def _classify_book(self, snapshot: dict, previous: Optional[dict]) -> Tuple[str, int, bool]:
        comparison = self.store.compare_snapshot(snapshot, previous=previous)
        return (
            comparison["status"],
            comparison["new_highlights_count"],
            comparison["has_new_highlights"],
        )

    def _sort_rows(self, rows: List[dict]) -> List[dict]:
        status_priority = {
            STATUS_NEW: 0,
            STATUS_UPDATED: 1,
            STATUS_UNCHANGED: 2,
        }

        def row_key(row):
            return (
                status_priority[row["status"]],
                0 if row["has_new_highlights"] else 1,
                row["title"].lower(),
                row["author"].lower(),
            )

        return sorted(rows, key=row_key)

    def build_books_table(
        self,
        books: Dict[str, List[dict]],
        processed_at: Optional[datetime] = None,
        persist: bool = True,
        force_reprocess: bool = False,
    ) -> List[dict]:
        previous_books = self.store.get_books()
        snapshots = {}
        rows = []

        for title, entries in books.items():
            snapshot = self._build_snapshot(title, entries)
            snapshots[snapshot["book_key"]] = snapshot
            previous = previous_books.get(snapshot["book_key"])
            status, new_highlights_count, has_new_highlights = self._classify_book(
                snapshot,
                previous,
            )

            default_selected = status == STATUS_NEW or (
                status == STATUS_UPDATED and has_new_highlights
            )

            rows.append(
                {
                    "book_key": snapshot["book_key"],
                    "title": snapshot["title"],
                    "author": snapshot["author"],
                    "highlights": snapshot["highlight_count"],
                    "notes": snapshot["note_count"],
                    "bookmarks": snapshot["bookmark_count"],
                    "status": status,
                    "new_highlights_count": new_highlights_count,
                    "has_new_highlights": has_new_highlights,
                    "default_selected": default_selected,
                    "last_processed_at": (previous or {}).get("last_processed_at"),
                    "last_processed_display": _iso_to_display(
                        (previous or {}).get("last_processed_at")
                    ),
                    "last_exported_at": (previous or {}).get("last_exported_at"),
                    "last_exported_display": _iso_to_display(
                        (previous or {}).get("last_exported_at")
                    ),
                    "last_export_formats": (previous or {}).get("last_export_formats", []),
                    "was_processed_before": previous is not None,
                    "was_exported_before": bool((previous or {}).get("last_exported_at")),
                    "was_reexported_before": len((previous or {}).get("export_history", [])) > 1,
                    "forced_reprocess": bool(force_reprocess),
                }
            )

        ordered_rows = self._sort_rows(rows)
        if persist:
            self.store.save_processed_snapshots(
                snapshots,
                processed_at=processed_at,
                forced=force_reprocess,
            )
        return ordered_rows

    def build_default_selection_map(self, rows: List[dict]) -> Dict[str, bool]:
        return {row["book_key"]: row["default_selected"] for row in rows}

    def mark_exported(
        self,
        selected_book_keys,
        exported_at: Optional[datetime] = None,
        export_formats: Optional[List[str]] = None,
    ):
        export_formats = export_formats or []
        export_map = {book_key: export_formats for book_key in selected_book_keys}
        self.store.mark_exported(export_map, exported_at=exported_at)
