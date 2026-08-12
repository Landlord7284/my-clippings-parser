import base64
import hashlib
import io
import json
import os
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
from typing_extensions import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .book_selection_service import FILTER_ALL, STATUS_FILTER_LABELS, BookSelectionService
from .extractor import KindleHighlightsExtractor
from .processing_store import ProcessingStore


app = FastAPI(title="Kindle Notes Extractor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


ANALYSIS_CACHE: Dict[str, dict] = {}


class AppConfig(BaseModel):
    export_markdown: Annotated[bool, Field(alias="exportMarkdown")] = True
    export_html: Annotated[bool, Field(alias="exportHtml")] = False
    export_txt: Annotated[bool, Field(alias="exportTxt")] = False
    remove_duplicates: Annotated[bool, Field(alias="removeDuplicates")] = True
    similarity_threshold: Annotated[float, Field(alias="similarityThreshold")] = 0.8
    dedup_position_overlap_ratio: Annotated[
        float, Field(alias="dedupPositionOverlapRatio")
    ] = 0.60
    dedup_token_overlap_threshold: Annotated[
        float, Field(alias="dedupTokenOverlapThreshold")
    ] = 0.75
    dedup_session_window_minutes: Annotated[
        int, Field(alias="dedupSessionWindowMinutes")
    ] = 15
    include_bookmarks: Annotated[bool, Field(alias="includeBookmarks")] = True
    include_metadata: Annotated[bool, Field(alias="includeMetadata")] = True

    model_config = ConfigDict(populate_by_name=True)


class ExportRequest(BaseModel):
    analysisId: str
    selectedBookKeys: List[str]
    config: AppConfig


class ExportBookRequest(BaseModel):
    analysisId: str
    bookKey: str
    config: AppConfig


MIME_TYPES = {
    ".md": "text/markdown; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
}


def get_processing_store() -> ProcessingStore:
    history_dir_value = os.environ.get("HISTORY_DIR")
    history_dir = Path(history_dir_value) if history_dir_value else Path(".")
    history_dir.mkdir(parents=True, exist_ok=True)
    return ProcessingStore(history_dir / ".kindle_processing_store.json")


def build_extractor_config(config: AppConfig) -> dict:
    return {
        "output_folder": "temp_output",
        "export_formats": {
            "markdown": {
                "enabled": config.export_markdown,
                "include_metadata": config.include_metadata,
                "folder": "markdown",
            },
            "html": {
                "enabled": config.export_html,
                "include_metadata": config.include_metadata,
                "css_style": "default",
                "folder": "html",
            },
            "txt": {
                "enabled": config.export_txt,
                "include_metadata": config.include_metadata,
                "plain_text": True,
                "folder": "txt",
            },
        },
        "remove_duplicates": config.remove_duplicates,
        "similarity_threshold": config.similarity_threshold,
        "dedup_position_overlap_ratio": config.dedup_position_overlap_ratio,
        "dedup_token_overlap_threshold": config.dedup_token_overlap_threshold,
        "dedup_session_window_minutes": config.dedup_session_window_minutes,
        "include_bookmarks": config.include_bookmarks,
        "date_format": "portuguese",
        "encoding": "utf-8",
    }


def _parse_config(config_json: str) -> AppConfig:
    try:
        payload = json.loads(config_json)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=400, detail="Invalid config JSON.") from error
    return AppConfig.model_validate(payload)


def _selected_format_labels(config: AppConfig) -> List[str]:
    labels = []
    if config.export_markdown:
        labels.append("markdown")
    if config.export_html:
        labels.append("html")
    if config.export_txt:
        labels.append("txt")
    return labels


def _create_zip_file(output_dir: Path) -> io.BytesIO:
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for file_path in output_dir.rglob("*"):
            if file_path.is_file():
                relative_path = file_path.relative_to(output_dir)
                zip_file.write(file_path, relative_path)
    zip_buffer.seek(0)
    return zip_buffer


def _build_author_options(rows: List[dict]) -> List[str]:
    return sorted({str(row["author"]) for row in rows})


def _current_export_datetime() -> datetime:
    return datetime.now(timezone.utc)


def _cached_analysis_or_409(analysis_id: str) -> dict:
    cached_analysis = ANALYSIS_CACHE.get(analysis_id)
    if cached_analysis is None:
        raise HTTPException(
            status_code=409,
            detail="Analysis not found. Reanalyze the uploaded file before exporting.",
        )
    return cached_analysis


def _known_book_keys(cached_analysis: dict, selected_book_keys: List[str]) -> List[str]:
    known = {row["book_key"] for row in cached_analysis["rows"]}
    return [key for key in selected_book_keys if key in known]


def _build_export_extractor(
    cached_analysis: dict,
    config: AppConfig,
    selected_keys: List[str],
) -> KindleHighlightsExtractor:
    extractor = KindleHighlightsExtractor(build_extractor_config(config))
    extractor.books = cached_analysis["books"]
    selected_entries = sum(len(extractor.books.get(key, [])) for key in selected_keys)
    extractor.stats["books_processed"] = len(selected_keys)
    extractor.stats["total_entries"] = selected_entries
    return extractor


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/analyze")
async def analyze_file(
    file: UploadFile = File(...),
    config: str = Form(...),
    force_reprocess: bool = Form(False, alias="forceReprocess"),
):
    app_config = _parse_config(config)
    raw_content = await file.read()
    analysis_id = hashlib.sha1(raw_content).hexdigest()

    try:
        content = raw_content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise HTTPException(
            status_code=400,
            detail="Nao foi possivel ler o arquivo como UTF-8.",
        ) from error

    extractor = KindleHighlightsExtractor(build_extractor_config(app_config))
    extractor.parse_content(content)

    service = BookSelectionService(get_processing_store())
    rows = service.build_books_table(
        extractor.books,
        persist=True,
        force_reprocess=force_reprocess,
    )
    selection_map = service.build_default_selection_map(rows)

    ANALYSIS_CACHE[analysis_id] = {
        "books": extractor.books,
        "rows": rows,
        "stats": extractor.stats,
        "uploaded_name": file.filename,
        "selection_map": selection_map,
    }

    return {
        "analysisId": analysis_id,
        "uploadedName": file.filename,
        "stats": extractor.stats,
        "rows": rows,
        "selectionMap": selection_map,
        "statusOptions": [
            {"value": key, "label": label}
            for key, label in STATUS_FILTER_LABELS.items()
            if key != FILTER_ALL or rows
        ],
        "authorOptions": _build_author_options(rows),
    }


@app.post("/api/export")
def export_books(request: ExportRequest):
    cached_analysis = _cached_analysis_or_409(request.analysisId)
    if not request.selectedBookKeys:
        raise HTTPException(status_code=400, detail="Select at least one book before exporting.")

    selected_keys = _known_book_keys(cached_analysis, request.selectedBookKeys)
    if not selected_keys:
        raise HTTPException(
            status_code=400,
            detail="No valid selected books were found for this analysis.",
        )

    extractor = _build_export_extractor(cached_analysis, request.config, selected_keys)

    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "temp_output"
        extractor.generate_files(output_dir, selected_keys=selected_keys)
        zip_buffer = _create_zip_file(output_dir)

    exported_at = _current_export_datetime()
    service = BookSelectionService(get_processing_store())
    service.mark_exported(
        request.selectedBookKeys,
        exported_at=exported_at,
        export_formats=_selected_format_labels(request.config),
    )

    filename = f"kindle_destaques_{exported_at.strftime('%Y%m%d_%H%M%S')}.zip"
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/export/book")
def export_book_files(request: ExportBookRequest):
    cached_analysis = _cached_analysis_or_409(request.analysisId)
    selected_keys = _known_book_keys(cached_analysis, [request.bookKey])
    if not selected_keys:
        raise HTTPException(
            status_code=400,
            detail="No valid selected book was found for this analysis.",
        )

    extractor = _build_export_extractor(cached_analysis, request.config, selected_keys)
    files = []
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "temp_output"
        extractor.generate_files(output_dir, selected_keys=selected_keys)
        for file_path in sorted(output_dir.rglob("*")):
            if not file_path.is_file():
                continue
            files.append(
                {
                    "filename": file_path.name,
                    "format": file_path.parent.name,
                    "mimeType": MIME_TYPES.get(file_path.suffix, "application/octet-stream"),
                    "contentBase64": base64.b64encode(file_path.read_bytes()).decode("ascii"),
                }
            )

    if not files:
        raise HTTPException(
            status_code=400,
            detail="No files were generated. Enable at least one export format.",
        )

    service = BookSelectionService(get_processing_store())
    service.mark_exported(
        [request.bookKey],
        exported_at=_current_export_datetime(),
        export_formats=_selected_format_labels(request.config),
    )

    return {"files": files}


frontend_dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
