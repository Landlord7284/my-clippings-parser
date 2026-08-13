# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Backend (Python 3.11+, run from repo root):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt      # pulls in requirements.txt
uvicorn kindle_extractor.api:app --reload  # http://127.0.0.1:8000
pytest                                    # full suite
pytest tests/test_parser.py -q            # single module
pytest tests/test_dedup.py::test_name -q  # single test
```

Frontend (Node 20+, from `frontend/`):

```bash
npm install
npm run dev     # http://127.0.0.1:5173, proxies /api -> 127.0.0.1:8000
npm run test    # vitest run
npm run build   # tsc -b && vite build — also the typecheck gate
```

`npm run test:e2e` is a PowerShell wrapper (`scripts/run-e2e.ps1`) and only works on Windows. On macOS/Linux, start `npm run dev` yourself and run `npx playwright test` against `http://127.0.0.1:5173`.

Docker (single container serving API + built frontend on port 8501):

```bash
docker build -t legroom2669/my-clippings-parser:dev .
docker run --rm -p 8501:8501 -v "$PWD/data:/data" legroom2669/my-clippings-parser:dev
```

Published as `legroom2669/my-clippings-parser` (tags `1.0.0` and `latest`,
`linux/amd64` + `linux/arm64`). Docker prose lives in `DOCKER.md`, not `README.md`.

`docker-entrypoint.sh` runs before the app: as root with `PUID`/`PGID` set it chowns `HISTORY_DIR` and drops privileges via `gosu`; started already non-root (`--user`) it execs straight through; with both vars blank it stays root. Changing it means re-testing all three paths.

Note: `README.md` documents commands for PowerShell first, with a bash section after; translate as needed. Prose documentation lives in `README.md` and `DOCKER.md` — `docs/` holds just the Obsidian Web Clipper template JSONs. There is no linter or formatter configured — only `.editorconfig`.

## Architecture

Pipeline: upload → parse → dedup → group by book → classify status vs. history → select → export ZIP → record history.

**`kindle_extractor/extractor.py`** (`KindleHighlightsExtractor`) is the orchestrator. It splits `My Clippings.txt` on `==========`, delegates field extraction to `parser.py`, runs `dedup.decide_duplicate` per entry, and accumulates `self.books: Dict[book_key, List[entry]]` plus a `self.stats` dict (including per-reason `dedup_metrics` and a `dedup_report` trail). It also owns file generation via `exporters.py`. Most of its methods are thin pass-throughs to the module functions — the real logic lives in the modules, not the class.

`book_key` is `build_book_key(title, author)` from `book_selection_service.py` — the same identity the API and frontend use, so no layer has to translate between title and key. Title and author are read back from `entries[0]`. Keying by title alone would merge distinct books that share one.

**`parser.py`** targets Portuguese Kindle clippings (`Destaque`/`Nota`/`Marcador`, `posição`, `página`, `X de <mês> de YYYY`). It defends against latin1/UTF-8 mojibake (`_fix_mojibake`) and accent-folds before regex matching. Entry type is inferred in `extractor.process_entry` by substring match on the metadata line, so it is language-coupled to Portuguese.

**`dedup.py`** is a layered, priority-ranked strategy, not a single rule. `detect_duplicate_candidate` returns the highest-priority match (exact 100 → same-start containment 90 → same-range containment 85 → position overlap 80 → same-start expansion 75 → text containment w/o position 60 → similarity fallback 50); `decide_duplicate` picks the best candidate across all existing entries, then `choose_survivor` decides whether the new entry *replaces* the stored one (preference order: has date → newer date → longer normalized text → larger `end_pos`). A "duplicate" may therefore still mutate stored data. Thresholds come from config keys `similarity_threshold`, `dedup_position_overlap_ratio`, `dedup_token_overlap_threshold`, `dedup_session_window_minutes`.

**`book_selection_service.py`** turns `books` into UI rows. It builds a per-book snapshot keyed by `build_book_key(title, author)` (SHA1 of normalized title+author) with two hash sets — `entry_signature_hashes` (all entries) and `highlight_signature_hashes` (highlights only) — then classifies against the stored previous snapshot:

- `novo` — no history at all
- `nunca_exportado` — analyzed before, never exported
- `com_novidades` — content hash differs from the last export's hash
- `sem_novidades` — unchanged since last export

The first three default to selected. Status strings are Portuguese internal identifiers; `STATUS_LABELS` maps them to different UI words (`nunca_exportado` → "Pendente", `com_novidades` → "Alterado", `sem_novidades` → "Exportado"). Don't rename the identifiers to match the labels.

**`processing_store.py`** persists `.kindle_processing_store.json` (version 2, `HISTORY_DIR` env var sets the directory, defaults to CWD). Key invariants: `last_analysis_at` and `last_export_at` are tracked separately (analyzing never counts as exporting); every read passes through `_sanitize_book`, which normalizes legacy field names (`last_processed_at`/`last_exported_at`, `*_signatures` vs `*_signature_hashes`) and re-hashes non-SHA1 values — so schema changes must extend that sanitizer rather than assume a shape; writes go through `update(mutator)` under a per-resolved-path `threading.RLock` and land via unique temp file + atomic replace; history lists are capped at 200 events. Single-writer-process design only.

**`api.py`** is the FastAPI layer: `/api/health`, `/api/analyze`, `/api/export` (ZIP), `/api/export/book` (base64 files), `/api/analysis/{id}/books/{key}/entries` (reading panel), and `/clip/{id}/{key}` — an HTML page carrying schema.org `@Book` JSON-LD plus highlights under `[data-testid="highlights"]`, shaped for the Obsidian Web Clipper template in `docs/kindle-highlights-clipper.json`. That template and `exporters.generate_obsidian` must emit the same property set *and* the same note body; `build_obsidian_properties` and `build_note_blocks` are the single sources for them — the clip page renders blocks via `render_note_blocks_html`, the export via `render_note_blocks_markdown`, so neither side hand-rolls the body. The callout markup (`div.callout[data-callout]`, `.callout-title-inner`, `.callout-content`) is what the extension's HTML→markdown converter turns into `> [!type] title`; writing `[!type]` as literal text does not work, it escapes the brackets. See the Obsidian section of `README.md`. Analysis results live in a module-level in-memory `ANALYSIS_CACHE` keyed by SHA1 of the uploaded bytes, backed by `analysis_store.py` on disk: on a cache miss `_cached_analysis_or_409` rehydrates by re-parsing the stored upload with `persist=False`, and only returns **409** when the file is gone from disk too. `GET /api/analysis/latest` serves the most recent stored analysis so the app opens already filled in. `AppConfig` is a Pydantic model using camelCase aliases (`exportMarkdown`, …) with `populate_by_name=True`; `build_extractor_config` translates it into the nested dict shape `config.py`/`extractor.py` expect. If `frontend/dist` exists it is mounted at `/` — that is how the Docker image serves both from one port.

**`frontend/`** is a Vite + React 19 + Tailwind + shadcn/ui app, essentially all in `src/App.tsx` (~1100 lines) with `@/` aliased to `src/`. **Filtering and batch selection live only in `src/lib/selection.ts`** — the backend has no say in them. A parallel Python implementation used to exist in `book_selection_service.py`; it was never wired to any endpoint, drifted from the TypeScript, and was deleted. Don't reintroduce it: if filtering has to move server-side, move it, don't mirror it. The frontend `AppConfig` type is a subset of the backend one — the `dedup*` tuning fields exist server-side only and fall back to Pydantic defaults.

## Working in this repo

- Sensitive modules: `parser.py` (affects grouping and classification), `dedup.py` (aggressive rules delete real data), `processing_store.py` (schema changes need legacy sanitization), `book_selection_service.py` (wrong status → wrong default export set), and `exporters.py` + the clip page in `api.py` (the note body is a contract with the Web Clipper's HTML→markdown converter — changing the callout markup breaks clipping silently, without breaking the download).
- Bug fixes should land with a regression test in the matching `tests/test_*.py`; parser/dedup tests should use realistic clippings (see `tests/fixtures/my_clippings_excerpt.txt` and the `real_clippings_excerpt` fixture).
- `tests/conftest.py` provides `entry_factory`, `snapshot_factory`, `extractor_config`, `fixture_dir`, and `workspace_tmp_path` (pytest's own tmpdir plugin is disabled in `pytest.ini`; use `workspace_tmp_path`). API tests isolate history with `monkeypatch.setenv("HISTORY_DIR", ...)` and must `ANALYSIS_CACHE.clear()` since the cache is module-global.
- `processing_store` records both `last_export_highlight_signature_hashes` (highlights) and `last_export_entry_signature_hashes` (all entries). The second one drives incremental export (`BookSelectionService.keep_only_new_entries`); the first still feeds status classification. Both need a `_sanitize_book` fallback to the export event, or pre-existing history reads as "never exported".
- Exporter output must never depend on the process locale — use `datetime_utils.format_date_pt`, not `strftime('%B')` — and `generate_html` must `html.escape()` every interpolated value. Real clippings contain `<Você alcançou o limite de recortes para este item>`, which silently vanishes in a browser when unescaped.
- On Node 26 `window.localStorage` is shadowed by an inert native global; `frontend/src/test/setup.ts` polyfills it. Without that, every `App.test.tsx` case fails at setup.
- Before closing a change: `pytest`, then `npm run test` and `npm run build` in `frontend/`, and manually exercise upload → analyze → select → export if the flow changed.
- Commits follow `tipo(escopo): resumo curto` (`feat`, `fix`, `test`, `docs`, `refactor`) per `CONTRIBUTING.md`.
- User-facing strings, status identifiers, and most docs are in Portuguese; code identifiers and newer docs are in English. Match whatever the file you're editing already uses.
