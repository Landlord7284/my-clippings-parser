import html
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .datetime_utils import format_date_pt, today_in_app_timezone


def _sortable_date(value):
    if not isinstance(value, datetime):
        return datetime.min
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _position_label(entry: dict) -> Optional[str]:
    start_pos = entry.get("start_pos")
    end_pos = entry.get("end_pos")
    if start_pos is None or end_pos is None:
        return None
    if start_pos == end_pos:
        return f"Posição: {start_pos}"
    return f"Posição: {start_pos}-{end_pos}"


def location_parts(entry: dict) -> List[str]:
    parts = []
    if entry.get("page") is not None:
        parts.append(f"Página {entry['page']}")

    position = _position_label(entry)
    if position:
        parts.append(position)

    if entry.get("date_formatted"):
        parts.append(entry["date_formatted"])
    return parts


def _bookmark_positions(bookmarks: List[dict]) -> List[str]:
    return [
        str(bookmark["start_pos"])
        for bookmark in bookmarks
        if bookmark.get("start_pos") is not None
    ]


def _generated_at_label() -> str:
    return format_date_pt(today_in_app_timezone())


def _renders(entry: dict, include_bookmarks: bool) -> bool:
    """Bookmarks nao tem conteudo: valem pela posicao. Os demais precisam de texto."""
    if entry["type"] == "bookmark":
        return bool(include_bookmarks)
    return bool(entry["content"])


def _is_renderable(entry: dict, app_config: dict) -> bool:
    return _renders(entry, app_config["include_bookmarks"])


def sort_entries(entries: List[dict]) -> List[dict]:
    def sort_key(entry):
        pos = entry["start_pos"] if entry["start_pos"] is not None else float("inf")
        return (pos, _sortable_date(entry["date_obj"]))

    return sorted(entries, key=sort_key)


def _build_book_metadata(entries: List[dict]) -> Dict[str, object]:
    highlights = [e for e in entries if e["type"] == "highlight"]
    notes = [e for e in entries if e["type"] == "note"]
    bookmarks = [e for e in entries if e["type"] == "bookmark"]
    author = entries[0]["author"] if entries else "Autor desconhecido"

    dates = [_sortable_date(e["date_obj"]) for e in entries if e["date_obj"]]
    if dates:
        period = f"{format_date_pt(min(dates))} - {format_date_pt(max(dates))}"
    else:
        period = "Período desconhecido"

    full_title = f"{entries[0]['title']} - {author}" if (
        entries and author != "Autor desconhecido"
    ) else (entries[0]["title"] if entries else "Sem título")

    return {
        "highlights": highlights,
        "notes": notes,
        "bookmarks": bookmarks,
        "author": author,
        "period": period,
        "full_title": full_title,
    }


class _RawYaml(str):
    """Valor emitido sem aspas: o Obsidian so tipa a propriedade como data assim."""


def _yaml_scalar(value: str) -> str:
    """Aspas duplas cobrem qualquer titulo -- inclusive os que tem ':' ou aspas."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def build_obsidian_properties(title: str, author: str) -> List[tuple]:
    """Espelha as propriedades do template do Web Clipper.

    Só recebe valor o que os clippings do Kindle realmente dizem. O resto fica
    em branco, presente na nota, para preenchimento manual no Obsidian.
    """
    return [
        ("type", "livro"),
        ("title", title),
        ("author", author),
        ("contributors", []),
        ("pages", None),
        ("language", None),
        ("isbn", None),
        ("created", _RawYaml(today_in_app_timezone().strftime("%Y-%m-%d"))),
        ("source", None),
        ("format", ["ebook"]),
        ("genres", []),
        ("series", None),
        ("volume", None),
        ("started", None),
        ("finished", None),
        ("status", None),
        ("rating", None),
        ("documented", True),
    ]


def _yaml_property(name: str, value) -> str:
    if value is None or value == []:
        return f"{name}:"
    if value is True:
        return f"{name}: true"
    if isinstance(value, _RawYaml):
        return f"{name}: {value}"
    if isinstance(value, list):
        items = "\n".join(f"  - {_yaml_scalar(item)}" for item in value)
        return f"{name}:\n{items}"
    return f"{name}: {_yaml_scalar(value)}"


def _obsidian_frontmatter(title: str, author: str) -> str:
    properties = build_obsidian_properties(title, author)
    body = "\n".join(_yaml_property(name, value) for name, value in properties)
    return f"---\n{body}\n---\n"


def _as_blockquote(text: str) -> str:
    return "\n".join(f"> {line}" if line else ">" for line in text.split("\n"))


METADATA_CALLOUT_TITLE = "Metadados do recorte"


def _metadata_fields(meta: Dict[str, object], include_bookmarks: bool) -> List[tuple]:
    """Rastreabilidade do recorte. Titulo e autor ficam de fora: ja sao propriedades."""
    fields = [
        ("Total de destaques", str(len(meta["highlights"]))),
        ("Total de notas", str(len(meta["notes"]))),
    ]
    if include_bookmarks and meta["bookmarks"]:
        positions = ", ".join(_bookmark_positions(meta["bookmarks"]))
        fields.append(("Posições marcadas", positions))
    fields.append(("Período", str(meta["period"])))
    fields.append(("Gerado em", _generated_at_label()))
    return fields


def build_note_blocks(
    entries: List[dict],
    *,
    include_metadata: bool = True,
    include_bookmarks: bool = True,
) -> List[dict]:
    """Corpo da nota do Obsidian descrito em blocos, sem markdown nem HTML.

    Fonte unica das duas renderizacoes -- o `.md` exportado e a pagina de
    recorte. Enquanto cada caminho montava o proprio corpo eles divergiram em
    silencio, e so o usuario percebia, ja dentro do cofre.
    """
    entries = sort_entries(entries)
    blocks: List[dict] = []

    if include_metadata:
        meta = _build_book_metadata(entries)
        blocks.append(
            {
                "kind": "callout",
                "type": "info",
                "fold": "-",
                "title": METADATA_CALLOUT_TITLE,
                "fields": _metadata_fields(meta, include_bookmarks),
            }
        )

    for entry in entries:
        if not _renders(entry, include_bookmarks):
            continue

        location = " · ".join(location_parts(entry))

        if entry["type"] == "bookmark":
            # Sem corpo: um callout vazio renderiza uma linha `>` solta.
            blocks.append({"kind": "marker", "label": "Marcador", "location": location})
        elif entry["type"] == "note":
            blocks.append(
                {
                    "kind": "callout",
                    "type": "note",
                    "title": f"Nota — {location}",
                    "text": entry["content"],
                }
            )
        else:
            blocks.append(
                {
                    "kind": "callout",
                    "type": "quote",
                    "title": location,
                    "text": entry["content"],
                }
            )

    return blocks


def _text_paragraphs(text: str) -> List[List[str]]:
    """Paragrafos do destaque, cada um como lista de linhas."""
    paragraphs = re.split(r"\n[ \t]*\n", text)
    return [
        [line for line in paragraph.split("\n")]
        for paragraph in paragraphs
        if paragraph.strip()
    ]


def render_note_blocks_markdown(blocks: List[dict]) -> str:
    parts = []

    for block in blocks:
        if block["kind"] == "marker":
            parts.append(f"**{block['label']}** — {block['location']}")
            continue

        header = f"> [!{block['type']}]{block.get('fold', '')} {block['title']}"

        if "fields" in block:
            # Dois espacos no fim de cada linha menos a ultima: quebra forte, do
            # mesmo jeito que o generate_markdown ja separa os metadados dele.
            joined = "  \n".join(
                f"**{label}**: {value}" for label, value in block["fields"]
            )
            body = "\n".join(f"> {line}" for line in joined.split("\n"))
        else:
            body = _as_blockquote(block["text"])

        parts.append(f"{header}\n{body}")

    return "\n\n".join(parts) + "\n" if parts else ""


def render_note_blocks_html(blocks: List[dict]) -> str:
    """Marcacao que o conversor do Web Clipper devolve como os mesmos blocos.

    A extensao converte `div.callout[data-callout]` em `> [!tipo] titulo`, lendo
    o titulo de `.callout-title-inner` e o corpo de `.callout-content`. Escrever
    `[!tipo]` como texto nao funciona: o conversor escapa os colchetes.
    """
    parts = []

    for block in blocks:
        if block["kind"] == "marker":
            parts.append(
                f"<p><strong>{html.escape(block['label'])}</strong> — "
                f"{html.escape(block['location'])}</p>"
            )
            continue

        fold = block.get("fold") or ""
        fold_attr = f' data-callout-fold="{html.escape(fold)}"' if fold else ""

        if "fields" in block:
            content = "<p>" + "<br>".join(
                f"<strong>{html.escape(label)}</strong>: {html.escape(value)}"
                for label, value in block["fields"]
            ) + "</p>"
        else:
            content = "".join(
                "<p>" + "<br>".join(html.escape(line) for line in lines) + "</p>"
                for lines in _text_paragraphs(block["text"])
            )

        parts.append(
            f'<div class="callout" data-callout="{html.escape(block["type"])}"{fold_attr}>'
            f'<div class="callout-title"><div class="callout-title-inner">'
            f'{html.escape(block["title"])}</div></div>'
            f'<div class="callout-content">{content}</div>'
            f"</div>"
        )

    return "\n".join(parts)


def generate_obsidian(
    title: str, entries: List[dict], format_config: dict, app_config: dict
) -> str:
    """Nota pronta para o cofre: propriedades no topo, destaques sob a secao usual."""
    entries = sort_entries(entries)
    meta = _build_book_metadata(entries)

    content = _obsidian_frontmatter(title, meta["author"])
    content += "\n# Citações e Destaques\n\n"
    content += render_note_blocks_markdown(
        build_note_blocks(
            entries,
            include_metadata=format_config.get("include_metadata", True),
            include_bookmarks=app_config["include_bookmarks"],
        )
    )

    return content


def generate_markdown(
    title: str, entries: List[dict], format_config: dict, app_config: dict
) -> str:
    entries = sort_entries(entries)
    meta = _build_book_metadata(entries)
    full_title = (
        f"{title} - {meta['author']}"
        if meta["author"] != "Autor desconhecido"
        else title
    )
    md_content = f"# {full_title}\n\n"

    if format_config.get("include_metadata", True):
        md_content += f"**Autor**: {meta['author']}  \n"
        md_content += f"**Total de destaques**: {len(meta['highlights'])}  \n"
        md_content += f"**Total de notas**: {len(meta['notes'])}  \n"

        if app_config["include_bookmarks"] and meta["bookmarks"]:
            positions = _bookmark_positions(meta["bookmarks"])
            md_content += f"**Posições marcadas**: {', '.join(positions)}  \n"

        md_content += f"**Período**: {meta['period']}  \n"
        md_content += f"**Gerado em**: {_generated_at_label()}  \n"
        md_content += "\n---\n\n"

    for entry in entries:
        if not _is_renderable(entry, app_config):
            continue

        location = " | ".join(location_parts(entry))

        if entry["type"] == "note":
            md_content += f"- **NOTA** {location}\n"
            md_content += f"**{entry['content']}**\n\n"
        elif entry["type"] == "bookmark":
            md_content += f"- **MARCADOR** {location}\n\n"
        else:
            md_content += f"- {location}\n"
            md_content += f"{entry['content']}\n\n"

    return md_content


def generate_html(
    title: str, entries: List[dict], format_config: dict, app_config: dict
) -> str:
    entries = sort_entries(entries)
    meta = _build_book_metadata(entries)
    full_title = (
        f"{title} - {meta['author']}"
        if meta["author"] != "Autor desconhecido"
        else title
    )

    css = """
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                line-height: 1.6;
                color: #333;
            }
            h1 {
                color: #2c3e50;
                border-bottom: 3px solid #3498db;
                padding-bottom: 10px;
            }
            .metadata {
                background-color: #f8f9fa;
                padding: 15px;
                border-left: 4px solid #3498db;
                margin-bottom: 30px;
            }
            .metadata p { margin: 5px 0; }
            .entry {
                margin-bottom: 25px;
                padding: 15px;
                border-left: 3px solid #e0e0e0;
            }
            .entry-meta {
                color: #666;
                font-size: 0.9em;
                margin-bottom: 8px;
                font-weight: bold;
                font-style: italic;
            }
            .entry-content {
                color: #444;
                font-style: normal;
            }
            .note {
                background-color: #fff3cd;
                border-left-color: #ffc107;
            }
            .note .entry-content {
                font-weight: bold;
                font-style: normal;
            }
            .highlight {
                background-color: #d4edda;
                border-left-color: #28a745;
            }
        </style>
    """

    escaped_title = html.escape(full_title)
    html_content = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{escaped_title}</title>
    {css}
</head>
<body>
    <h1>{escaped_title}</h1>
"""

    if format_config.get("include_metadata", True):
        html_content += f"""
    <div class="metadata">
        <p><strong>Autor:</strong> {html.escape(meta['author'])}</p>
        <p><strong>Total de destaques:</strong> {len(meta['highlights'])}</p>
        <p><strong>Total de notas:</strong> {len(meta['notes'])}</p>
"""
        if app_config["include_bookmarks"] and meta["bookmarks"]:
            positions = _bookmark_positions(meta["bookmarks"])
            html_content += (
                "        <p><strong>Posições marcadas:</strong> "
                f"{html.escape(', '.join(positions))}</p>\n"
            )

        html_content += f"""        <p><strong>Período:</strong> {html.escape(meta['period'])}</p>
        <p><strong>Gerado em:</strong> {html.escape(_generated_at_label())}</p>
    </div>
"""

    for entry in entries:
        if not _is_renderable(entry, app_config):
            continue

        css_class = "note" if entry["type"] == "note" else "highlight"
        location = html.escape(" | ".join(location_parts(entry)))
        prefix = {"note": "NOTA ", "bookmark": "MARCADOR "}.get(entry["type"], "")
        html_content += f"""
    <div class="entry {css_class}">
        <div class="entry-meta">{prefix}{location}</div>
        <div class="entry-content">{html.escape(entry['content'])}</div>
    </div>
"""

    html_content += """
</body>
</html>"""
    return html_content


def generate_txt(
    title: str, entries: List[dict], format_config: dict, app_config: dict
) -> str:
    entries = sort_entries(entries)
    meta = _build_book_metadata(entries)
    full_title = (
        f"{title} - {meta['author']}"
        if meta["author"] != "Autor desconhecido"
        else title
    )

    txt_content = f"{full_title}\n"
    txt_content += "=" * len(full_title) + "\n\n"

    if format_config.get("include_metadata", True):
        txt_content += f"Autor: {meta['author']}\n"
        txt_content += f"Total de destaques: {len(meta['highlights'])}\n"
        txt_content += f"Total de notas: {len(meta['notes'])}\n"

        if app_config["include_bookmarks"] and meta["bookmarks"]:
            positions = _bookmark_positions(meta["bookmarks"])
            txt_content += f"Posições marcadas: {', '.join(positions)}\n"

        txt_content += f"Período: {meta['period']}\n"
        txt_content += f"Gerado em: {_generated_at_label()}\n"
        txt_content += "\n" + "-" * 50 + "\n\n"

    for entry in entries:
        if not _is_renderable(entry, app_config):
            continue

        location = " | ".join(location_parts(entry))
        prefix = {"note": "NOTA ", "bookmark": "MARCADOR "}.get(entry["type"], "")
        txt_content += f"{prefix}{location}\n"
        if entry["content"]:
            txt_content += f"{entry['content']}\n\n"

    return txt_content
