import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


STORE_VERSION = 2
MAX_HISTORY_ITEMS = 200
STATUS_NEW = "novo"
STATUS_UPDATED = "atualizado"
STATUS_UNCHANGED = "sem mudanças"


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_hash(value: str) -> str:
    return hashlib.sha1((value or "").encode("utf-8")).hexdigest()


def _normalize_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_string_list(value) -> List[str]:
    if not isinstance(value, list):
        return []

    values = []
    for item in value:
        if item is None:
            continue
        item_text = str(item).strip()
        if not item_text:
            continue
        values.append(item_text)
    return sorted(set(values))


def _normalize_signature_hashes(value) -> List[str]:
    normalized = _normalize_string_list(value)
    output = []
    for item in normalized:
        is_sha1 = len(item) == 40 and all(ch in "0123456789abcdefABCDEF" for ch in item)
        output.append(item.lower() if is_sha1 else _stable_hash(item))
    return sorted(set(output))


def _hash_from_items(items: List[str]) -> str:
    if not items:
        return _stable_hash("")
    return _stable_hash("||".join(sorted(set(items))))


def _default_payload() -> Dict[str, object]:
    return {"version": STORE_VERSION, "meta": {"updated_at": None}, "books": {}}


def _trim_history(events: List[dict]) -> List[dict]:
    if len(events) <= MAX_HISTORY_ITEMS:
        return events
    return events[-MAX_HISTORY_ITEMS:]


def _sanitize_event_list(events) -> List[dict]:
    if not isinstance(events, list):
        return []
    clean = [event for event in events if isinstance(event, dict)]
    return _trim_history(clean)


class ProcessingStore:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> Dict[str, object]:
        if not self.path.exists():
            return _default_payload()

        try:
            with open(self.path, "r", encoding="utf-8") as file:
                raw_data = json.load(file)
        except (json.JSONDecodeError, OSError):
            return _default_payload()

        payload = self._sanitize_payload(raw_data)
        return payload

    def save(self, data: Dict[str, object]):
        payload = self._sanitize_payload(data)
        payload["meta"]["updated_at"] = _now_utc_iso()

        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        with open(tmp_path, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2, sort_keys=True)
        tmp_path.replace(self.path)

    def get_books(self) -> Dict[str, dict]:
        return deepcopy(self.load().get("books", {}))

    def compare_snapshot(self, snapshot: dict, previous: Optional[dict] = None) -> dict:
        previous_book = previous if previous is not None else self.get_books().get(
            snapshot.get("book_key")
        )
        current_entry_hashes = set(
            snapshot.get("entry_signature_hashes") or snapshot.get("entry_signatures") or []
        )
        current_highlight_hashes = set(
            snapshot.get("highlight_signature_hashes")
            or snapshot.get("highlight_signatures")
            or []
        )

        previous_entry_hashes = set(
            (previous_book or {}).get("entry_signature_hashes")
            or (previous_book or {}).get("entry_signatures")
            or []
        )
        previous_highlight_hashes = set(
            (previous_book or {}).get("highlight_signature_hashes")
            or (previous_book or {}).get("highlight_signatures")
            or []
        )

        if previous_book is None or (
            not previous_entry_hashes and not previous_book.get("last_processed_at")
        ):
            new_highlights = len(current_highlight_hashes)
            return {
                "status": STATUS_NEW,
                "new_highlights_count": new_highlights,
                "has_new_highlights": new_highlights > 0,
            }

        if current_entry_hashes == previous_entry_hashes:
            return {
                "status": STATUS_UNCHANGED,
                "new_highlights_count": 0,
                "has_new_highlights": False,
            }

        new_highlights = len(current_highlight_hashes - previous_highlight_hashes)
        return {
            "status": STATUS_UPDATED,
            "new_highlights_count": new_highlights,
            "has_new_highlights": new_highlights > 0,
        }

    def save_processed_snapshots(
        self,
        snapshots: Dict[str, dict],
        processed_at: Optional[datetime] = None,
        forced: bool = False,
    ):
        payload = self.load()
        books = payload.get("books", {})
        processed_iso = (processed_at or datetime.now(timezone.utc)).isoformat()
        process_id = _stable_hash(f"{processed_iso}|{len(snapshots)}")

        for book_key, snapshot in snapshots.items():
            previous = self._sanitize_book(book_key, books.get(book_key, {}))
            normalized_snapshot = self._normalize_snapshot(book_key, snapshot)
            comparison = self.compare_snapshot(normalized_snapshot, previous=previous)
            content_signature_hash = normalized_snapshot["content_signature_hash"]
            highlight_signature_hash = normalized_snapshot["highlight_signature_hash"]

            event = {
                "process_id": process_id,
                "processed_at": processed_iso,
                "forced": bool(forced),
                "detected_status": comparison["status"],
                "new_highlights_count": comparison["new_highlights_count"],
                "content_signature_hash": content_signature_hash,
                "highlight_signature_hash": highlight_signature_hash,
                "highlight_count": normalized_snapshot["highlight_count"],
                "note_count": normalized_snapshot["note_count"],
                "bookmark_count": normalized_snapshot["bookmark_count"],
            }

            processing_history = _trim_history(previous["processing_history"] + [event])
            updated_book = deepcopy(previous)
            updated_book.update(normalized_snapshot)
            updated_book["last_processed_at"] = processed_iso
            updated_book["last_detected_processing"] = deepcopy(event)
            updated_book["processing_history"] = processing_history
            books[book_key] = updated_book

        payload["books"] = books
        self.save(payload)

    def mark_exported(
        self,
        book_keys_or_exports,
        exported_at: Optional[datetime] = None,
    ):
        payload = self.load()
        books = payload.get("books", {})
        exported_iso = (exported_at or datetime.now(timezone.utc)).isoformat()

        if isinstance(book_keys_or_exports, dict):
            exports_map = book_keys_or_exports
        else:
            exports_map = {book_key: [] for book_key in book_keys_or_exports}

        for book_key, formats in exports_map.items():
            if book_key not in books:
                continue

            book = self._sanitize_book(book_key, books.get(book_key, {}))
            normalized_formats = _normalize_string_list(formats)
            export_id = _stable_hash(
                f"{book_key}|{exported_iso}|{','.join(normalized_formats)}|"
                f"{book.get('content_signature_hash')}"
            )
            last_export = book.get("last_export") or {}
            current_content_hash = book.get("content_signature_hash")
            reexport_without_changes = (
                bool(last_export)
                and current_content_hash
                and last_export.get("content_signature_hash") == current_content_hash
            )
            event = {
                "export_id": export_id,
                "exported_at": exported_iso,
                "formats": normalized_formats,
                "content_signature_hash": current_content_hash,
                "processed_at": book.get("last_processed_at"),
                "reexport_without_changes": reexport_without_changes,
            }

            export_history = _trim_history(book["export_history"] + [event])
            book["last_exported_at"] = exported_iso
            book["last_export_formats"] = normalized_formats
            book["last_export"] = deepcopy(event)
            book["export_history"] = export_history
            books[book_key] = book

        payload["books"] = books
        self.save(payload)

    def _sanitize_payload(self, raw_data: dict) -> Dict[str, object]:
        payload = _default_payload()
        if not isinstance(raw_data, dict):
            return payload

        raw_books = raw_data.get("books", {})
        books = {}
        if isinstance(raw_books, dict):
            for raw_key, raw_book in raw_books.items():
                book_key = str(raw_key)
                books[book_key] = self._sanitize_book(book_key, raw_book)

        payload["books"] = books
        raw_meta = raw_data.get("meta", {})
        if isinstance(raw_meta, dict):
            payload["meta"]["updated_at"] = raw_meta.get("updated_at")
        return payload

    def _normalize_snapshot(self, book_key: str, snapshot: dict) -> dict:
        title = str(snapshot.get("title") or "")
        author = str(snapshot.get("author") or "Autor desconhecido")
        entry_hashes = _normalize_signature_hashes(
            snapshot.get("entry_signature_hashes") or snapshot.get("entry_signatures")
        )
        highlight_hashes = _normalize_signature_hashes(
            snapshot.get("highlight_signature_hashes") or snapshot.get("highlight_signatures")
        )
        content_signature_hash = snapshot.get("content_signature_hash") or _hash_from_items(
            entry_hashes
        )
        highlight_signature_hash = snapshot.get("highlight_signature_hash") or _hash_from_items(
            highlight_hashes
        )
        return {
            "book_key": book_key,
            "title": title,
            "author": author,
            "entry_signature_hashes": entry_hashes,
            "highlight_signature_hashes": highlight_hashes,
            "content_signature_hash": content_signature_hash,
            "highlight_signature_hash": highlight_signature_hash,
            "highlight_count": _normalize_int(snapshot.get("highlight_count"), 0),
            "note_count": _normalize_int(snapshot.get("note_count"), 0),
            "bookmark_count": _normalize_int(snapshot.get("bookmark_count"), 0),
        }

    def _sanitize_book(self, book_key: str, raw_book: dict) -> dict:
        if not isinstance(raw_book, dict):
            raw_book = {}

        entry_hashes = _normalize_signature_hashes(
            raw_book.get("entry_signature_hashes") or raw_book.get("entry_signatures")
        )
        highlight_hashes = _normalize_signature_hashes(
            raw_book.get("highlight_signature_hashes") or raw_book.get("highlight_signatures")
        )
        content_signature_hash = raw_book.get("content_signature_hash") or _hash_from_items(
            entry_hashes
        )
        highlight_signature_hash = raw_book.get("highlight_signature_hash") or _hash_from_items(
            highlight_hashes
        )
        last_export_formats = _normalize_string_list(raw_book.get("last_export_formats"))
        processing_history = _sanitize_event_list(raw_book.get("processing_history"))
        export_history = _sanitize_event_list(raw_book.get("export_history"))

        last_detected = raw_book.get("last_detected_processing")
        if not isinstance(last_detected, dict):
            last_detected = processing_history[-1] if processing_history else None
        last_export = raw_book.get("last_export")
        if not isinstance(last_export, dict):
            last_export = export_history[-1] if export_history else None

        return {
            "book_key": book_key,
            "title": str(raw_book.get("title") or ""),
            "author": str(raw_book.get("author") or "Autor desconhecido"),
            "entry_signature_hashes": entry_hashes,
            "highlight_signature_hashes": highlight_hashes,
            "content_signature_hash": content_signature_hash,
            "highlight_signature_hash": highlight_signature_hash,
            "highlight_count": _normalize_int(raw_book.get("highlight_count"), 0),
            "note_count": _normalize_int(raw_book.get("note_count"), 0),
            "bookmark_count": _normalize_int(raw_book.get("bookmark_count"), 0),
            "last_processed_at": raw_book.get("last_processed_at"),
            "last_exported_at": raw_book.get("last_exported_at"),
            "last_export_formats": last_export_formats,
            "last_detected_processing": last_detected,
            "last_export": last_export,
            "processing_history": processing_history,
            "export_history": export_history,
        }
