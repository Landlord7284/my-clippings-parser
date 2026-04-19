from __future__ import annotations

import sys
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
import uuid

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


@pytest.fixture
def fixture_dir() -> Path:
    return Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def workspace_tmp_path() -> Path:
    root = Path(__file__).resolve().parent / ".tmp"
    path = root / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def real_clippings_excerpt(fixture_dir: Path) -> str:
    return (fixture_dir / "my_clippings_excerpt.txt").read_text(encoding="utf-8")


@pytest.fixture
def extractor_config() -> dict:
    return {
        "remove_duplicates": True,
        "similarity_threshold": 0.8,
        "include_bookmarks": True,
        "export_formats": {
            "markdown": {"enabled": True, "include_metadata": True, "folder": "markdown"},
            "html": {"enabled": True, "include_metadata": True, "folder": "html"},
            "txt": {"enabled": True, "include_metadata": True, "folder": "txt"},
        },
    }


@pytest.fixture
def entry_factory() -> Callable[..., dict]:
    def _build(
        *,
        entry_type: str = "highlight",
        title: str = "Livro",
        author: str = "Autor",
        page: int | None = 1,
        start_pos: int | None = 10,
        end_pos: int | None = 12,
        content: str = "Trecho",
        date_obj: datetime | None = None,
        date_formatted: str = "1 de janeiro de 2024",
    ) -> dict:
        return {
            "type": entry_type,
            "title": title,
            "author": author,
            "page": page,
            "start_pos": start_pos,
            "end_pos": end_pos,
            "content": content,
            "date_formatted": date_formatted,
            "date_obj": date_obj or datetime(2024, 1, 1, tzinfo=timezone.utc),
            "metadata_line": "",
        }

    return _build


@pytest.fixture
def snapshot_factory() -> Callable[..., dict]:
    def _build(
        *,
        book_key: str = "book-key",
        title: str = "Livro",
        author: str = "Autor",
        entry_hashes: list[str] | None = None,
        highlight_hashes: list[str] | None = None,
    ) -> dict:
        entry_hashes = entry_hashes or ["a" * 40]
        highlight_hashes = highlight_hashes or ["b" * 40]
        return {
            book_key: {
                "book_key": book_key,
                "title": title,
                "author": author,
                "entry_signature_hashes": entry_hashes,
                "highlight_signature_hashes": highlight_hashes,
                "highlight_count": len(highlight_hashes),
                "note_count": 0,
                "bookmark_count": 0,
            }
        }

    return _build
