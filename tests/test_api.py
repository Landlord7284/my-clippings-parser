import base64
import io
import json
import zipfile
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from kindle_extractor import api as api_module
from kindle_extractor.api import ANALYSIS_CACHE, app
from kindle_extractor.datetime_utils import format_iso_for_display
from kindle_extractor.processing_store import ProcessingStore


def _config(**overrides):
    payload = {
        "exportMarkdown": True,
        "exportHtml": False,
        "exportTxt": False,
        "removeDuplicates": True,
        "similarityThreshold": 0.8,
        "includeBookmarks": True,
        "includeMetadata": True,
    }
    payload.update(overrides)
    return payload


def _analyze(client, content: bytes, config=None):
    return client.post(
        "/api/analyze",
        files={"file": ("My Clippings.txt", content, "text/plain")},
        data={
            "config": json.dumps(config or _config()),
            "forceReprocess": "false",
        },
    )


def test_health_check():
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_analyze_returns_rows_options_and_default_selection(
    workspace_tmp_path, real_clippings_excerpt, monkeypatch
):
    monkeypatch.setenv("HISTORY_DIR", str(workspace_tmp_path))
    ANALYSIS_CACHE.clear()
    client = TestClient(app)

    response = _analyze(client, real_clippings_excerpt.encode("utf-8"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["analysisId"]
    assert payload["stats"]["books_processed"] == 3
    assert len(payload["rows"]) == 3
    assert "Philip K. Dick" in payload["authorOptions"]
    assert payload["selectionMap"][payload["rows"][0]["book_key"]] is True
    assert {option["value"] for option in payload["statusOptions"]} >= {
        "todos",
        "selecionados",
        "novo",
    }
    assert {option["label"] for option in payload["statusOptions"]} >= {
        "Novo",
        "Pendente",
        "Alterado",
        "Exportado",
    }


def test_analyze_rejects_non_utf8_file(workspace_tmp_path, monkeypatch):
    monkeypatch.setenv("HISTORY_DIR", str(workspace_tmp_path))
    ANALYSIS_CACHE.clear()
    client = TestClient(app)

    response = _analyze(client, b"\xff\xfe\x00")

    assert response.status_code == 400
    assert "UTF-8" in response.json()["detail"]


def test_analysis_cache_keeps_only_the_most_recent_analyses(
    workspace_tmp_path, real_clippings_excerpt, monkeypatch
):
    monkeypatch.setenv("HISTORY_DIR", str(workspace_tmp_path))
    ANALYSIS_CACHE.clear()
    client = TestClient(app)

    ids = [
        _analyze(client, f"{real_clippings_excerpt}\n{index}".encode("utf-8")).json()["analysisId"]
        for index in range(api_module.MAX_CACHED_ANALYSES + 2)
    ]

    assert len(ANALYSIS_CACHE) == api_module.MAX_CACHED_ANALYSES
    assert ids[0] not in ANALYSIS_CACHE
    assert ids[-1] in ANALYSIS_CACHE


def test_export_returns_zip_for_selected_book_only_and_marks_store(
    workspace_tmp_path, real_clippings_excerpt, monkeypatch
):
    monkeypatch.setenv("HISTORY_DIR", str(workspace_tmp_path))
    ANALYSIS_CACHE.clear()
    client = TestClient(app)
    analysis = _analyze(client, real_clippings_excerpt.encode("utf-8")).json()
    selected_row = next(row for row in analysis["rows"] if row["title"] == "Blade Runner")

    response = client.post(
        "/api/export",
        json={
            "analysisId": analysis["analysisId"],
            "selectedBookKeys": [selected_row["book_key"]],
            "config": _config(exportMarkdown=False, exportTxt=True, includeMetadata=False),
        },
    )

    assert response.status_code != 405
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = archive.namelist()
        assert names == ["txt/blade-runner-philip-k.-dick.txt"]
        exported_text = archive.read(names[0]).decode("utf-8")
        assert "Blade Runner - Philip K. Dick" in exported_text
        assert "A Morte de Ivan Ilitch" not in exported_text
        assert "Autor:" not in exported_text

    store = ProcessingStore(workspace_tmp_path / ".kindle_processing_store.json")
    exported_book = store.get_books()[selected_row["book_key"]]
    assert exported_book["last_export_at"]
    assert exported_book["last_export_formats"] == ["txt"]


def test_export_book_returns_direct_files_and_marks_store(
    workspace_tmp_path, real_clippings_excerpt, monkeypatch
):
    monkeypatch.setenv("HISTORY_DIR", str(workspace_tmp_path))
    ANALYSIS_CACHE.clear()
    client = TestClient(app)
    analysis = _analyze(client, real_clippings_excerpt.encode("utf-8")).json()
    selected_row = next(row for row in analysis["rows"] if row["title"] == "Blade Runner")

    response = client.post(
        "/api/export/book",
        json={
            "analysisId": analysis["analysisId"],
            "bookKey": selected_row["book_key"],
            "config": _config(exportHtml=True, exportTxt=True, includeMetadata=False),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert {file["format"] for file in payload["files"]} == {"html", "markdown", "txt"}
    assert {file["filename"] for file in payload["files"]} == {
        "blade-runner-philip-k.-dick.html",
        "blade-runner-philip-k.-dick.md",
        "blade-runner-philip-k.-dick.txt",
    }

    txt_file = next(file for file in payload["files"] if file["format"] == "txt")
    txt_content = base64.b64decode(txt_file["contentBase64"]).decode("utf-8")
    assert "Blade Runner - Philip K. Dick" in txt_content
    assert txt_file["mimeType"] == "text/plain; charset=utf-8"

    store = ProcessingStore(workspace_tmp_path / ".kindle_processing_store.json")
    exported_book = store.get_books()[selected_row["book_key"]]
    assert exported_book["last_export_at"]
    assert exported_book["last_export_formats"] == ["html", "markdown", "txt"]


def test_export_uses_timezone_aware_timestamp_for_display(
    workspace_tmp_path, real_clippings_excerpt, monkeypatch
):
    monkeypatch.setenv("HISTORY_DIR", str(workspace_tmp_path))
    monkeypatch.setattr(
        api_module,
        "_current_export_datetime",
        lambda: datetime(2026, 6, 8, 21, 40, tzinfo=ZoneInfo("America/Sao_Paulo")),
    )
    ANALYSIS_CACHE.clear()
    client = TestClient(app)
    analysis = _analyze(client, real_clippings_excerpt.encode("utf-8")).json()
    selected_row = next(row for row in analysis["rows"] if row["title"] == "Blade Runner")

    response = client.post(
        "/api/export",
        json={
            "analysisId": analysis["analysisId"],
            "selectedBookKeys": [selected_row["book_key"]],
            "config": _config(),
        },
    )

    assert response.status_code == 200
    store = ProcessingStore(workspace_tmp_path / ".kindle_processing_store.json")
    exported_book = store.get_books()[selected_row["book_key"]]
    assert exported_book["last_export_at"] == "2026-06-09T00:40:00+00:00"
    assert format_iso_for_display(exported_book["last_export_at"]) == "2026-06-08 21:40"


def test_export_requires_known_analysis_id(workspace_tmp_path, monkeypatch):
    monkeypatch.setenv("HISTORY_DIR", str(workspace_tmp_path))
    ANALYSIS_CACHE.clear()
    client = TestClient(app)

    response = client.post(
        "/api/export",
        json={
            "analysisId": "missing",
            "selectedBookKeys": ["book"],
            "config": _config(),
        },
    )

    assert response.status_code == 409
    assert "Reanalyze" in response.json()["detail"]


def test_export_requires_selected_books(
    workspace_tmp_path, real_clippings_excerpt, monkeypatch
):
    monkeypatch.setenv("HISTORY_DIR", str(workspace_tmp_path))
    ANALYSIS_CACHE.clear()
    client = TestClient(app)
    analysis = _analyze(client, real_clippings_excerpt.encode("utf-8")).json()

    response = client.post(
        "/api/export",
        json={
            "analysisId": analysis["analysisId"],
            "selectedBookKeys": [],
            "config": _config(),
        },
    )

    assert response.status_code == 400
    assert "Select at least one book" in response.json()["detail"]
