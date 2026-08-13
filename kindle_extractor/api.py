import base64
import hashlib
import html
import io
import json
import os
import zipfile
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Dict, List, Optional
from typing_extensions import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .analysis_store import AnalysisStore
from .book_selection_service import FILTER_ALL, STATUS_FILTER_LABELS, BookSelectionService
from .exporters import build_note_blocks, render_note_blocks_html, sort_entries
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


# Cada analise guarda o `books` inteiro. Sem teto, um backend de vida longa
# acumula uma copia por arquivo analisado e nunca devolve a memoria.
MAX_CACHED_ANALYSES = 5

ANALYSIS_CACHE: "OrderedDict[str, dict]" = OrderedDict()


def _cache_analysis(analysis_id: str, payload: dict) -> None:
    ANALYSIS_CACHE[analysis_id] = payload
    ANALYSIS_CACHE.move_to_end(analysis_id)
    while len(ANALYSIS_CACHE) > MAX_CACHED_ANALYSES:
        ANALYSIS_CACHE.popitem(last=False)


class AppConfig(BaseModel):
    export_markdown: Annotated[bool, Field(alias="exportMarkdown")] = True
    export_html: Annotated[bool, Field(alias="exportHtml")] = False
    export_txt: Annotated[bool, Field(alias="exportTxt")] = False
    export_obsidian: Annotated[bool, Field(alias="exportObsidian")] = False
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
    export_only_new: Annotated[bool, Field(alias="exportOnlyNew")] = False

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


def get_history_dir() -> Path:
    history_dir_value = os.environ.get("HISTORY_DIR")
    history_dir = Path(history_dir_value) if history_dir_value else Path(".")
    history_dir.mkdir(parents=True, exist_ok=True)
    return history_dir


def get_processing_store() -> ProcessingStore:
    return ProcessingStore(get_history_dir() / ".kindle_processing_store.json")


def get_analysis_store() -> AnalysisStore:
    return AnalysisStore(get_history_dir() / "analyses")


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
            "obsidian": {
                "enabled": config.export_obsidian,
                "include_metadata": config.include_metadata,
                "folder": "obsidian",
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
    if config.export_obsidian:
        labels.append("obsidian")
    return labels


def _create_zip_file(files: Dict[str, str]) -> io.BytesIO:
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for relative_path, content in sorted(files.items()):
            zip_file.writestr(relative_path, content)
    zip_buffer.seek(0)
    return zip_buffer


def _serialize_entry(entry: dict) -> dict:
    """Campos explicitos: a entrada crua carrega date_obj e caches internos da dedup."""
    return {
        "type": entry["type"],
        "page": entry["page"],
        "start_pos": entry["start_pos"],
        "end_pos": entry["end_pos"],
        "content": entry["content"],
        "date_formatted": entry["date_formatted"],
    }


def _build_author_options(rows: List[dict]) -> List[str]:
    return sorted({str(row["author"]) for row in rows})


def _current_export_datetime() -> datetime:
    return datetime.now(timezone.utc)


def _build_analysis_payload(
    content: str,
    app_config: AppConfig,
    filename: Optional[str],
    *,
    persist: bool,
    force_reprocess: bool = False,
) -> dict:
    extractor = KindleHighlightsExtractor(build_extractor_config(app_config))
    extractor.parse_content(content)

    service = BookSelectionService(get_processing_store())
    rows = service.build_books_table(
        extractor.books,
        persist=persist,
        force_reprocess=force_reprocess,
    )

    return {
        "books": extractor.books,
        "rows": rows,
        "stats": extractor.stats,
        "uploaded_name": filename,
        "selection_map": service.build_default_selection_map(rows),
    }


def _analysis_response(analysis_id: str, payload: dict) -> dict:
    rows = payload["rows"]
    return {
        "analysisId": analysis_id,
        "uploadedName": payload["uploaded_name"],
        "stats": payload["stats"],
        "rows": rows,
        "selectionMap": payload["selection_map"],
        "statusOptions": [
            {"value": key, "label": label}
            for key, label in STATUS_FILTER_LABELS.items()
            if key != FILTER_ALL or rows
        ],
        "authorOptions": _build_author_options(rows),
    }


def _rehydrate_stored_analysis(stored: dict) -> dict:
    """Reconstroi a analise a partir do upload guardado e repovoa o cache.

    `persist=False` e o ponto delicado: reidratar nao e uma analise nova. Com
    `True`, todo restart empurraria `last_analysis_at` para frente e enfileiraria
    um evento por livro no `processing_history`.
    """
    try:
        app_config = AppConfig.model_validate(stored.get("config") or {})
    except ValidationError:
        app_config = AppConfig()

    payload = _build_analysis_payload(
        stored["content"],
        app_config,
        stored.get("filename"),
        persist=False,
    )
    _cache_analysis(stored["id"], payload)
    return payload


def _cached_analysis_or_409(analysis_id: str) -> dict:
    cached_analysis = ANALYSIS_CACHE.get(analysis_id)

    if cached_analysis is None:
        stored = get_analysis_store().get(analysis_id)
        if stored is not None:
            cached_analysis = _rehydrate_stored_analysis(stored)

    if cached_analysis is None:
        raise HTTPException(
            status_code=409,
            detail="Analysis not found. Reanalyze the uploaded file before exporting.",
        )

    ANALYSIS_CACHE.move_to_end(analysis_id)
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
    books = cached_analysis["books"]
    if config.export_only_new:
        selected_books = {key: books[key] for key in selected_keys if key in books}
        books = BookSelectionService(get_processing_store()).keep_only_new_entries(selected_books)

    extractor.books = books
    selected_entries = sum(len(books.get(key, [])) for key in selected_keys)
    extractor.stats["books_processed"] = len(selected_keys)
    extractor.stats["total_entries"] = selected_entries
    return extractor


def _no_files_error(config: AppConfig) -> HTTPException:
    if config.export_only_new:
        return HTTPException(
            status_code=400,
            detail="Nenhuma novidade desde o último export. Desative 'Só novidades' para exportar tudo.",
        )
    return HTTPException(
        status_code=400,
        detail="No files were generated. Enable at least one export format.",
    )


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

    payload = _build_analysis_payload(
        content,
        app_config,
        file.filename,
        persist=True,
        force_reprocess=force_reprocess,
    )
    _cache_analysis(analysis_id, payload)

    # Guarda os bytes crus: e o que faz a analise sobreviver a um restart e
    # aparecer ao abrir o app de outro dispositivo.
    get_analysis_store().save(
        analysis_id,
        raw_content,
        file.filename,
        app_config.model_dump(by_alias=True),
    )

    return _analysis_response(analysis_id, payload)


@app.get("/api/analysis/latest")
def latest_analysis():
    """Ultima analise guardada, para o app abrir ja preenchido."""
    stored = get_analysis_store().get_latest()
    if stored is None:
        raise HTTPException(status_code=404, detail="No stored analysis yet.")

    payload = ANALYSIS_CACHE.get(stored["id"])
    if payload is None:
        payload = _rehydrate_stored_analysis(stored)

    ANALYSIS_CACHE.move_to_end(stored["id"])
    return _analysis_response(stored["id"], payload)


@app.get("/api/analysis/{analysis_id}/books/{book_key}/entries")
def get_book_entries(analysis_id: str, book_key: str):
    cached_analysis = _cached_analysis_or_409(analysis_id)
    entries = cached_analysis["books"].get(book_key)
    if not entries:
        raise HTTPException(status_code=404, detail="Book not found in this analysis.")

    return {
        "book_key": book_key,
        "title": entries[0]["title"],
        "author": entries[0]["author"],
        "entries": [_serialize_entry(entry) for entry in sort_entries(entries)],
    }


def _render_clip_page(
    title: str, author: str, entries: List[dict], include_metadata: bool = True
) -> str:
    """Pagina servida ao Web Clipper do Obsidian.

    O JSON-LD alimenta {{schema:@Book:name}} e {{schema:@Book:author[0].name}},
    os mesmos campos que o template do Goodreads ja usa. O corpo sai de
    `build_note_blocks`, o mesmo que gera o `.md` do formato Obsidian, sob um
    seletor estavel para o {{selectorHtml:...|markdown}}.

    O <h1> e o autor ficam fora desse seletor de proposito: servem para
    identificar a aba aberta e nunca entram na nota, onde seriam redundantes
    com as propriedades title/author.
    """
    book_schema = json.dumps(
        {
            "@context": "https://schema.org",
            "@type": "Book",
            "name": title,
            "author": [{"@type": "Person", "name": author}],
            "bookFormat": "EBook",
        },
        ensure_ascii=False,
    )

    body = render_note_blocks_html(
        build_note_blocks(
            entries,
            include_metadata=include_metadata,
            include_bookmarks=AppConfig().include_bookmarks,
        )
    )

    escaped_title = html.escape(title)
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escaped_title}</title>
<script type="application/ld+json">{book_schema}</script>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 46rem; margin: 2rem auto; padding: 0 1rem; line-height: 1.6; }}
  .callout {{ margin-bottom: 1.5rem; padding: .75rem 1rem; border-left: 3px solid #ccc; background: #f6f6f6; }}
  .callout[data-callout="info"] {{ border-left-color: #6b8bbd; }}
  .callout-title {{ font-weight: 600; font-size: .875rem; color: #555; margin-bottom: .5rem; }}
  .callout-content p {{ margin: 0 0 .5rem; }}
  .callout-content p:last-child {{ margin-bottom: 0; }}
</style>
</head>
<body>
<h1>{escaped_title}</h1>
<p>{html.escape(author)}</p>
<div data-testid="highlights">
{body}
</div>
</body>
</html>"""


@app.get("/clip/{analysis_id}/{book_key}")
def clip_page(
    analysis_id: str,
    book_key: str,
    only_new: bool = False,
    metadata: bool = True,
):
    cached_analysis = _cached_analysis_or_409(analysis_id)
    entries = cached_analysis["books"].get(book_key)
    if not entries:
        raise HTTPException(status_code=404, detail="Book not found in this analysis.")

    title, author = entries[0]["title"], entries[0]["author"]
    if only_new:
        service = BookSelectionService(get_processing_store())
        entries = service.keep_only_new_entries({book_key: entries}).get(book_key, [])

    return Response(
        content=_render_clip_page(title, author, sort_entries(entries), metadata),
        media_type="text/html; charset=utf-8",
    )


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
    files = extractor.build_files(selected_keys)
    if not files:
        raise _no_files_error(request.config)

    zip_buffer = _create_zip_file(files)

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
    for relative_path, content in sorted(extractor.build_files(selected_keys).items()):
        path = PurePosixPath(relative_path)
        files.append(
            {
                "filename": path.name,
                "format": path.parent.name,
                "mimeType": MIME_TYPES.get(path.suffix, "application/octet-stream"),
                "contentBase64": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            }
        )

    if not files:
        raise _no_files_error(request.config)

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
