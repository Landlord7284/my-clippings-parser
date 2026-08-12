import html
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


def _is_renderable(entry: dict, app_config: dict) -> bool:
    """Bookmarks nao tem conteudo: valem pela posicao. Os demais precisam de texto."""
    if entry["type"] == "bookmark":
        return bool(app_config["include_bookmarks"])
    return bool(entry["content"])


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


def generate_obsidian(
    title: str, entries: List[dict], format_config: dict, app_config: dict
) -> str:
    """Nota pronta para o cofre: propriedades no topo, destaques sob a secao usual."""
    entries = sort_entries(entries)
    meta = _build_book_metadata(entries)

    content = _obsidian_frontmatter(title, meta["author"])
    content += "\n# Citações e Destaques\n\n"

    for entry in entries:
        if not _is_renderable(entry, app_config):
            continue

        location = " · ".join(location_parts(entry))

        if entry["type"] == "bookmark":
            content += f"- **Marcador** — {location}\n\n"
        elif entry["type"] == "note":
            content += f"**Nota** — {location}\n\n{entry['content']}\n\n"
        else:
            content += f"{_as_blockquote(entry['content'])}\n>\n> *{location}*\n\n"

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
