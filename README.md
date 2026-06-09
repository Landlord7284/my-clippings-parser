# Kindle Notes Extractor

Local FastAPI + Vite React app for parsing Kindle `My Clippings.txt` files, grouping entries by book, reviewing the selection, and exporting only the books you choose.

## Features

- Parses Kindle highlights, notes, and bookmarks.
- Deduplicates repeated or overlapping entries.
- Tracks analysis and export history per book.
- Lets you search, filter, and select books before exporting.
- Exports selected books as Markdown, HTML, and/or TXT.

## App Flow

1. Upload a Kindle `My Clippings.txt` file.
2. Parse, deduplicate, and group entries by book.
3. Classify each book with one of the internal statuses: `novo`, `nunca_exportado`, `com_novidades`, or `sem_novidades`.
4. Review books with filters, search, and batch selection actions.
5. Export selected books as `markdown`, `html`, and/or `txt`.
6. Update local history in `.kindle_processing_store.json`.

## Requirements

- Python 3.11+
- Node.js 20+

## Local Setup

Install Python dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Start the backend:

```powershell
uvicorn kindle_extractor.api:app --reload
```

The backend runs at `http://127.0.0.1:8000`.

Start the frontend:

```powershell
cd frontend
npm install
npm run dev
```

The Vite frontend runs at `http://127.0.0.1:5173` and proxies `/api/...` requests to `http://127.0.0.1:8000`.

## Testing

Run the Python test suite:

```powershell
pytest
```

Run frontend tests and build checks:

```powershell
cd frontend
npm run test
npm run build
```

Run a specific Python test module:

```powershell
pytest tests/test_parser.py -q
```

## Docker

Build the image:

```powershell
docker build -t legroom2669/parser:1.0 .
```

Run the container on port `8501`:

```powershell
docker run --rm -p 8501:8501 -v "${PWD}\data:/data" legroom2669/parser:1.0
```

Open `http://127.0.0.1:8501`. The `/data` volume stores `.kindle_processing_store.json` outside the container.

## Project Structure

```text
kindle_extractor/
  api.py
  parser.py
  dedup.py
  processing_store.py
  book_selection_service.py
  exporters.py
  datetime_utils.py
  extractor.py

frontend/
  src/
  tests/

tests/
  conftest.py
  fixtures/
  test_parser.py
  test_dedup.py
  test_history.py
  test_selection_service.py
  test_exporters.py
  test_time_utils.py

docs/
  architecture.md
  dev-workflow.md
  processing_store_format.md
```

## Module Overview

- `parser.py`: parses title, author, location, page, date, and entry type.
- `dedup.py`: layered deduplication strategy for Kindle entries.
- `processing_store.py`: local processing and export history.
- `book_selection_service.py`: book status classification, sorting, filtering, and selection logic.
- `exporters.py`: Markdown, HTML, and TXT output generation.
- `datetime_utils.py`: UTC utilities and `America/Sao_Paulo` display formatting.
- `api.py`: FastAPI endpoints for analysis and export.
- `frontend/`: Vite React interface built with shadcn/ui components.
- `extractor.py`: parser, deduplication, and export orchestration.

## Known Limitations

- The parser focuses on common Portuguese `My Clippings.txt` patterns; unusual formats may fall back to best-effort parsing.
- Deduplication is conservative and may not catch every edge case.
- Analysis results are cached in memory. After restarting the backend, upload and analyze the file again before exporting.

## Local History

- `.kindle_processing_store.json` is the local history store.
- Store updates serialize the `load -> merge -> save` flow inside the backend process to reduce lost updates during local concurrent requests.
