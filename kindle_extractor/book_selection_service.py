import hashlib
import re
import unicodedata
from datetime import datetime
from typing import Dict, List, Optional

from .datetime_utils import format_iso_for_display, to_utc_iso

STATUS_NEW = "novo"
STATUS_NEVER_EXPORTED = "nunca_exportado"
STATUS_WITH_NEWS = "com_novidades"
STATUS_NO_NEWS = "sem_novidades"

STATUS_LABELS = {
    STATUS_NEW: "Novo",
    STATUS_NEVER_EXPORTED: "Pendente",
    STATUS_WITH_NEWS: "Alterado",
    STATUS_NO_NEWS: "Exportado",
}

FILTER_ALL = "todos"
FILTER_SELECTED = "selecionados"
FILTER_NEW = "novo"
FILTER_NEVER_EXPORTED = "nunca_exportado"
FILTER_WITH_NEWS = "com_novidades"
FILTER_NO_NEWS = "sem_novidades"

STATUS_FILTER_LABELS = {
    FILTER_ALL: "Todos",
    FILTER_NEW: "Novo",
    FILTER_NEVER_EXPORTED: "Pendente",
    FILTER_WITH_NEWS: "Alterado",
    FILTER_NO_NEWS: "Exportado",
    FILTER_SELECTED: "Selecionado",
}


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


class BookSelectionService:
    def __init__(self, store):
        self.store = store

    def _build_snapshot(self, entries: List[dict]) -> dict:
        title = entries[0]["title"]
        author = entries[0]["author"] or "Autor desconhecido"
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

    def _classify_book(self, snapshot: dict, previous: Optional[dict]) -> dict:
        current_highlight_hashes = set(snapshot.get("highlight_signature_hashes") or [])

        if previous is None:
            new_highlights = len(current_highlight_hashes)
            return {
                "status": STATUS_NEW,
                "new_highlights_count": new_highlights,
                "has_new_highlights": new_highlights > 0,
                "has_changes_since_export": True,
            }

        last_export_at = previous.get("last_export_at") or previous.get("last_exported_at")
        if not last_export_at:
            new_highlights = len(current_highlight_hashes)
            return {
                "status": STATUS_NEVER_EXPORTED,
                "new_highlights_count": new_highlights,
                "has_new_highlights": new_highlights > 0,
                "has_changes_since_export": True,
            }

        export_highlight_hashes = set(
            previous.get("last_export_highlight_signature_hashes")
            or (previous.get("last_export") or {}).get("highlight_signature_hashes")
            or []
        )
        if not export_highlight_hashes:
            export_highlight_hashes = set(previous.get("highlight_signature_hashes") or [])

        new_highlights = len(current_highlight_hashes - export_highlight_hashes)
        has_new_highlights = new_highlights > 0

        last_export_signature = previous.get("last_export_signature") or (
            (previous.get("last_export") or {}).get("content_signature_hash")
        )
        has_changes_since_export = (
            True
            if not last_export_signature
            else snapshot.get("content_signature_hash") != last_export_signature
        )

        status = STATUS_WITH_NEWS if has_changes_since_export else STATUS_NO_NEWS
        return {
            "status": status,
            "new_highlights_count": new_highlights,
            "has_new_highlights": has_new_highlights,
            "has_changes_since_export": has_changes_since_export,
        }

    def _sort_rows(self, rows: List[dict]) -> List[dict]:
        status_priority = {
            STATUS_NEW: 0,
            STATUS_WITH_NEWS: 1,
            STATUS_NEVER_EXPORTED: 2,
            STATUS_NO_NEWS: 3,
        }

        def row_key(row):
            return (
                status_priority.get(row["status"], 99),
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
        current_analysis_iso = to_utc_iso(processed_at) if persist else None

        for entries in books.values():
            if not entries:
                continue
            snapshot = self._build_snapshot(entries)
            snapshots[snapshot["book_key"]] = snapshot
            previous = previous_books.get(snapshot["book_key"])
            classification = self._classify_book(snapshot, previous)

            status = classification["status"]
            default_selected = status in {
                STATUS_NEW,
                STATUS_NEVER_EXPORTED,
                STATUS_WITH_NEWS,
            }

            previous_analysis_at = (previous or {}).get("last_analysis_at") or (
                previous or {}
            ).get("last_processed_at")
            last_analysis_at = current_analysis_iso or previous_analysis_at
            last_export_at = (previous or {}).get("last_export_at") or (
                previous or {}
            ).get("last_exported_at")

            rows.append(
                {
                    "book_key": snapshot["book_key"],
                    "title": snapshot["title"],
                    "author": snapshot["author"],
                    "highlights": snapshot["highlight_count"],
                    "notes": snapshot["note_count"],
                    "bookmarks": snapshot["bookmark_count"],
                    "status": status,
                    "status_label": STATUS_LABELS.get(status, status),
                    "new_highlights_count": classification["new_highlights_count"],
                    "has_new_highlights": classification["has_new_highlights"],
                    "has_changes_since_export": classification["has_changes_since_export"],
                    "default_selected": default_selected,
                    "last_analysis_at": last_analysis_at,
                    "last_analysis_display": format_iso_for_display(last_analysis_at),
                    "last_export_at": last_export_at,
                    "last_export_display": format_iso_for_display(last_export_at),
                    "last_export_formats": (previous or {}).get("last_export_formats", []),
                    "was_processed_before": previous is not None,
                    "was_exported_before": bool(last_export_at),
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

    def keep_only_new_entries(
        self, books: Dict[str, List[dict]]
    ) -> Dict[str, List[dict]]:
        """Descarta as entradas que ja sairam no ultimo export de cada livro.

        Livro sem export anterior entra inteiro. Livro sem nada novo sai do
        resultado, para nao gerar um arquivo vazio.
        """
        previous_books = self.store.get_books()
        filtered: Dict[str, List[dict]] = {}

        for book_key, entries in books.items():
            previous = previous_books.get(book_key) or {}
            exported = set(previous.get("last_export_entry_signature_hashes") or [])
            if not exported:
                filtered[book_key] = entries
                continue

            fresh = [
                entry
                for entry in entries
                if _hash_signature(build_entry_signature(entry)) not in exported
            ]
            if fresh:
                filtered[book_key] = fresh

        return filtered

    def mark_exported(
        self,
        selected_book_keys,
        exported_at: Optional[datetime] = None,
        export_formats: Optional[List[str]] = None,
    ):
        export_formats = export_formats or []
        export_map = {book_key: export_formats for book_key in selected_book_keys}
        self.store.mark_exported(export_map, exported_at=exported_at)
