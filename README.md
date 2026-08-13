# Kindle Notes Extractor

Local FastAPI + Vite React app for parsing Kindle `My Clippings.txt` files, grouping entries by book, reviewing the selection, and exporting only the books you choose.

## Features

- Parses Kindle highlights, notes, and bookmarks.
- Deduplicates repeated or overlapping entries.
- Tracks analysis and export history per book.
- Lets you search, filter, and select books before exporting.
- Exports selected books as Markdown, Obsidian, TXT, and/or HTML notes.
- Remembers the last uploaded file, so the app reopens already filled in after a restart.
- Exports incrementally: only the entries added since the previous export.
- Reads highlights in the app, with full-text search per book.

## App Flow

1. Upload a Kindle `My Clippings.txt` file.
2. Parse, deduplicate, and group entries by book.
3. Classify each book with one of the internal statuses: `novo`, `nunca_exportado`, `com_novidades`, or `sem_novidades`.
4. Review books with filters, search, and batch selection actions.
5. Export selected books as `markdown`, `obsidian`, `txt`, and/or `html`.
6. Update local history in `.kindle_processing_store.json`.

## Requirements

- Python 3.11+
- Node.js 20+

## Local Setup

### Windows (PowerShell)

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

### macOS / Linux

Starting from scratch, create the virtualenv and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Once the `.venv` exists (either just created or already present in the repo), start the backend and frontend in two terminals:

```bash
# terminal 1 — backend
source .venv/bin/activate
uvicorn kindle_extractor.api:app --reload
```

```bash
# terminal 2 — frontend
cd frontend
npm run dev
```

The backend runs at `http://127.0.0.1:8000` and the Vite frontend at `http://127.0.0.1:5173`, proxying `/api/...` requests to the backend. Run `npm install` in `frontend/` first if `node_modules` isn't present yet.

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

The published image runs the whole app — API plus built frontend — on port
`8501`:

```bash
docker run --rm -p 8501:8501 -v "$PWD/data:/data" legroom2669/my-clippings-parser:1.0.0
```

Image tags, building, non-root setups, and the entrypoint's three paths are
documented in [DOCKER.md](DOCKER.md).

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

Dockerfile
docker-entrypoint.sh
DOCKER.md

docs/
  goodreads-clipper.json
  kindle-highlights-clipper.json
  kindle-highlights-append-clipper.json
```

`docs/` holds only the Obsidian Web Clipper templates. Prose lives in this file,
except for Docker, which has its own [DOCKER.md](DOCKER.md).

## Module Overview

- `parser.py`: parses title, author, location, page, date, and entry type.
- `dedup.py`: layered deduplication strategy for Kindle entries.
- `processing_store.py`: local processing and export history.
- `book_selection_service.py`: book status classification, sorting, filtering, and selection logic.
- `exporters.py`: Markdown, HTML, TXT, and Obsidian output generation, plus the clip page body.
- `datetime_utils.py`: UTC utilities and `America/Sao_Paulo` display formatting.
- `api.py`: FastAPI endpoints for analysis and export, plus the `/clip/` page served to the Obsidian Web Clipper.
- `analysis_store.py`: keeps analyzed uploads on disk so an analysis survives a restart.
- `frontend/`: Vite React interface built with shadcn/ui components.
- `extractor.py`: parser, deduplication, and export orchestration.

## Obsidian

There are two ways to get highlights into a vault, and both produce the same
note body — `exporters.build_note_blocks` is the single source for it.

**Manual export** — enable the `Obsidian` format and export. You get a `.md`
with YAML frontmatter and the highlights, ready to drop into the vault.

**Web Clipper** — after analyzing, open a book and click *Página de recorte*,
then clip that page with the Obsidian Web Clipper extension. The clipper fills
the properties from the page and creates the note directly in the right vault
folder, with no file to move by hand. It is also the only route that combines
with a Goodreads clip.

### The clip page

`/clip/{analysisId}/{bookKey}` serves a page meant to be read by the extension,
not by humans:

- a `<script type="application/ld+json">` carrying a schema.org `@Book`, which
  feeds `{{schema:@Book:name}}` and `{{schema:@Book:author[0].name}}`;
- the note body inside `[data-testid="highlights"]`, which the templates read
  with `{{selectorHtml:[data-testid="highlights"]|markdown|trim}}`.

The `<h1>` title and the author line sit **outside** that selector on purpose:
they identify the open tab and never reach the note, where they would only
repeat the `title` and `author` properties.

| Query parameter | Effect |
| --- | --- |
| `only_new=true` | Only entries that were not in the book's previous export. |
| `metadata=false` | Omits the metadata callout. |

The *Página de recorte* button builds both from the *Só novidades* and
*Metadados* settings.

### Note format

The body is identical on both routes. The sample below is Portuguese because
the app is — month names come from `datetime_utils.format_date_pt`:

```markdown
> [!info]- Metadados do recorte
> **Total de destaques**: 96
> **Total de notas**: 0
> **Posições marcadas**: 139, 1204
> **Período**: 13 de agosto de 2024 - 30 de agosto de 2024
> **Gerado em**: 12 de agosto de 2026

> [!quote] Página 10 · Posição: 139-140 · 13 de agosto de 2024
> A polícia, porém, não importava. Somente a Polícia do Pensamento importava.

> [!note] Nota — Página 12 · Posição: 202 · 2 de fevereiro de 2024
> Revisar este trecho depois.

**Marcador** — Página 22 · Posição: 300 · 3 de fevereiro de 2024
```

Title and author are absent from the body — they are already properties. The
metadata callout carries the clip's traceability: how many entries, over what
period, and when the file was generated. Bookmarks are not callouts because
they have no body; an empty callout renders a stray `>` line.

`type`, `title`, `author`, `format`, `created`, and `documented` come pre-filled
from the clippings; the remaining properties (`pages`, `isbn`, `genres`,
`rating`, …) are present but empty, to fill in by hand.

Highlight text is passed through untouched, so a highlight containing `*`, `_`,
`[`, `]`, or a backtick comes out backslash-escaped in the **clipped** version —
the extension's converter escapes those to preserve the literal text. The
downloaded `.md` does not escape them. That is the only difference between the
two routes, besides trailing whitespace on blank lines inside multi-line
highlights.

`Obsidian` and `Markdown` are not the same format: `Markdown` is a plain report
(`# Title`, a metadata block, one bullet per entry) meant to be read anywhere;
`Obsidian` uses YAML frontmatter and Obsidian callouts under
`# Citações e Destaques`.

### Templates

All three live in `docs/` and are imported in *Web Clipper → Templates →
Import*.

| File | `behavior` | Triggers on | Purpose |
| --- | --- | --- | --- |
| `goodreads-clipper.json` | `create` | Goodreads book page | Creates the note with cover, synopsis, and properties. |
| `kindle-highlights-clipper.json` | `create` | `/clip/` | Creates a note holding just the highlights. |
| `kindle-highlights-append-clipper.json` | `append-specific` | `/clip/` | Appends the highlights to a note that already exists. |

Both Kindle templates trigger on ports 8501 (Docker), 8000 (uvicorn directly),
and 5173 (Vite dev server), on `127.0.0.1` and `localhost`.

The properties in `kindle-highlights-clipper.json` are the same 18, in the same
order, that `build_obsidian_properties` emits in the downloaded `.md`. Change
one, change the other.

### Why the callouts need that exact markup

Writing `[!quote]` as plain text on the page **does not work**: the extension's
converter escapes brackets in text nodes and the result comes out `\[!quote\]`.
What works is the markup it recognizes as a callout — an element with a
`data-callout` attribute **and** a `callout` class, with the title in
`.callout-title-inner` and the body in `.callout-content`.
`render_note_blocks_html` emits exactly that.

For the same reason the container is a `<div>` and not a `<ul>`: a list makes
the converter emit `- > text` with the location indented by a tab. Since the
templates select by attribute (`[data-testid="highlights"]`), swapping the tag
required no change to them. The selector must keep matching **exactly one**
element — matching more than one makes the extension serialize everything as
JSON.

### Goodreads + Kindle in one note

A Web Clipper template only sees the DOM of the page currently open. No
variable on a Goodreads page can reach `http://127.0.0.1:.../clip/…` to pull the
highlights. The way through is to append to the same note, in two steps:

1. **On the Goodreads book page**, clip with `goodreads-clipper.json`. That
   creates `Clippings/<title>.md` with the cover, the synopsis, and the
   properties, ending in an empty `# Citações e Destaques`.
2. **On the app's *Página de recorte***, clip with
   `kindle-highlights-append-clipper.json`. The highlights are appended to the
   end of that same note — which is exactly under the heading left by step 1.

Both templates target the same note through `noteNameFormat`
(`{{schema:@Book:name}}`) plus `path` (`Clippings`).

The append template has `properties: []` on purpose. The extension always
prefixes the frontmatter to the content it sends, regardless of `behavior`; an
append template with properties would inject a `---` block into the middle of
the note. With an empty list the frontmatter comes out empty and only the body
is appended.

### Troubleshooting

**The highlights created a new note instead of appending.** The Kindle title
and the Goodreads title often differ (subtitle, edition, translation). The note
name is editable in the clipper popup before saving — check it on step 2.

**The clip page opens blank.** In development, `/clip` has to be in the Vite
proxy (`frontend/vite.config.ts`); without it the dev server answers with the
SPA's `index.html`.

**The page returns 409.** The analysis is gone from both memory and disk —
upload and analyze the file again.

**The right template is not selected automatically.** Check that the port you
are using is in the template's `triggers` list.

## Deduplication Settings

Deduplication runs a priority-ranked ladder of seven strategies and keeps the
highest-priority match. Only two of them are tunable, through four settings in
the *Deduplicação* panel — all four are disabled while *Remover duplicatas* is
off. The other five strategies (exact duplicate, same-start containment,
same-range containment, same-start expansion, text containment without
position) are fixed.

| Setting | Range | Default | What it gates |
| --- | --- | --- | --- |
| Sobreposição de posição | 0.30–1.00 | 0.60 | `position_overlap` |
| Palavras em comum | 0.50–1.00 | 0.75 | `position_overlap` |
| Janela de sessão | 0–60 min | 15 | `position_overlap` |
| Similaridade | 0.50–1.00 | 0.80 | `similarity_fallback` |

**Sobreposição de posição** — the fraction of the *shorter* position range that
the intersection must cover. Lower merges more. It targets re-highlighting a
passage with slightly different drag handles, where Kindle emits two entries at,
say, positions 1200-1240 and 1215-1260.

Its real reach is narrower than it looks: any overlap of **3 or more position
units passes regardless of this setting**, so the slider only decides overlaps
of one or two units — highlights that merely touch at their edges. Raising it to
1.00 does not stop overlapping passages from merging.

**Palavras em comum** — the second gate for `position_overlap`, applied once two
entries are found to overlap positionally: the fraction of shared unique words,
measured in both directions, taking the smaller. This is the setting with the
broadest real-world effect. At 1.00 the word path is effectively off; at 0.50,
two overlapping entries that share half their vocabulary merge. It targets a
re-highlight that trimmed or extended a clause.

**Janela de sessão** — rescues a positional overlap that failed the ratio test,
on the theory that two highlights made minutes apart at adjacent positions are
one reading gesture. Same narrow scope as the first setting: it only applies to
overlaps of one or two units, and it does nothing when either entry has no
parseable date. `0` disables it.

**Similaridade** — a raw-character similarity ratio. It applies in two cases:
when either entry lacks a full position range (common for notes and sideloaded
books, where Kindle wrote no position in the metadata line), **and** when both
entries carry the exact same position range but their texts differ enough to
have escaped the cheaper text tests. Lowering it to 0.50 merges paraphrase-level
near-matches and risks collapsing genuinely distinct notes at the same position.

When a duplicate is found, the surviving record is chosen in this order: has a
parseable date at all → more recent date → longer normalized text → larger
`end_pos`. A full tie keeps the stored entry, so a "duplicate" may still update
what was already there.

## Known Limitations

- The parser focuses on common Portuguese `My Clippings.txt` patterns; unusual formats may fall back to best-effort parsing.
- Deduplication is conservative and may not catch every edge case.
- The analysis id is a hash of the file bytes only, not of the settings. Analyzing the same file again with different deduplication settings replaces the previous stored analysis.
- Single writer only: run one backend process against a given history directory.

## Local History

Everything the app keeps between runs lives in `HISTORY_DIR` (the process
working directory by default, `/data` in the Docker image):

- `.kindle_processing_store.json` — per-book analysis and export history.
- `analyses/` — the last 5 uploaded files plus an `index.json`, which is what
  lets an analysis survive a restart and lets the app open already filled in
  from any device. Each file is roughly the size of your `My Clippings.txt`.

### `.kindle_processing_store.json`

This store holds **no highlight text**: per book it keeps only SHA-1 signature
hashes, counts, and timestamps. That is what classifies each book as
Novo/Pendente/Alterado/Exportado and what drives incremental export.

```json
{
  "version": 2,
  "meta": { "updated_at": "2026-04-18T20:10:00+00:00" },
  "books": {
    "<book_key>": {
      "book_key": "...",
      "title": "...",
      "author": "...",
      "entry_signature_hashes": ["sha1", "..."],
      "highlight_signature_hashes": ["sha1", "..."],
      "content_signature_hash": "sha1",
      "highlight_signature_hash": "sha1",
      "highlight_count": 12,
      "note_count": 3,
      "bookmark_count": 4,
      "last_analysis_at": "ISO-8601 UTC",
      "last_export_at": "ISO-8601 UTC",
      "last_export_formats": ["markdown", "html"],
      "last_detected_processing": {
        "process_id": "sha1",
        "processed_at": "ISO-8601 UTC",
        "forced": false,
        "detected_status": "novo|atualizado|sem_mudancas",
        "new_highlights_count": 0,
        "content_signature_hash": "sha1",
        "highlight_signature_hash": "sha1"
      },
      "last_export": {
        "export_id": "sha1",
        "exported_at": "ISO-8601 UTC",
        "formats": ["markdown"],
        "content_signature_hash": "sha1",
        "processed_at": "ISO-8601 UTC",
        "reexport_without_changes": false
      },
      "processing_history": ["..."],
      "export_history": ["..."]
    }
  }
}
```

Notes on the format:

- The loader tolerates a missing, corrupted, or incomplete file, and normalizes
  legacy field names into stable SHA-1 hashes — so schema changes must extend
  that sanitizer rather than assume a shape.
- `last_analysis_at` and `last_export_at` stay separate: analyzing never counts
  as exporting. `detected_status` (`novo|atualizado|sem_mudancas`) is a
  different vocabulary from the four UI statuses.
- Dates are serialized in UTC and displayed as `America/Sao_Paulo`.
- History is capped at the last 200 events of each kind.
- Writes go through a per-path lock covering `load -> merge -> save`, and land
  via a unique temp file plus atomic replace.
