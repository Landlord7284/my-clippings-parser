from datetime import datetime, timezone
from typing import Dict, List


def _sortable_date(value):
    if not isinstance(value, datetime):
        return datetime.min
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


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
        first_date = min(dates)
        last_date = max(dates)
        period = (
            f"{first_date.strftime('%d de %B de %Y')} - "
            f"{last_date.strftime('%d de %B de %Y')}"
        )
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
            bookmark_positions = [
                str(b["start_pos"]) for b in meta["bookmarks"] if b["start_pos"]
            ]
            md_content += f"**Posições marcadas**: {', '.join(bookmark_positions)}  \n"

        md_content += f"**Período**: {meta['period']}  \n"
        md_content += f"**Gerado em**: {datetime.now().strftime('%d de %B de %Y')}  \n"
        md_content += "\n---\n\n"

    for entry in entries:
        if entry["type"] == "bookmark" and not app_config["include_bookmarks"]:
            continue

        if entry["page"]:
            location = f"Página {entry['page']} | "
        else:
            location = ""

        if entry["start_pos"] and entry["end_pos"]:
            if entry["start_pos"] == entry["end_pos"]:
                location += f"Posição: {entry['start_pos']}"
            else:
                location += f"Posição: {entry['start_pos']}-{entry['end_pos']}"

        if entry["date_formatted"]:
            location += f" | {entry['date_formatted']}"

        if entry["type"] == "note":
            md_content += f"- **NOTA** {location}\n"
            if entry["content"]:
                md_content += f"**{entry['content']}**\n\n"
        elif entry["content"]:
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

    html_content = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{full_title}</title>
    {css}
</head>
<body>
    <h1>{full_title}</h1>
"""

    if format_config.get("include_metadata", True):
        html_content += f"""
    <div class="metadata">
        <p><strong>Autor:</strong> {meta['author']}</p>
        <p><strong>Total de destaques:</strong> {len(meta['highlights'])}</p>
        <p><strong>Total de notas:</strong> {len(meta['notes'])}</p>
"""
        if app_config["include_bookmarks"] and meta["bookmarks"]:
            bookmark_positions = [
                str(b["start_pos"]) for b in meta["bookmarks"] if b["start_pos"]
            ]
            html_content += (
                "        <p><strong>Posições marcadas:</strong> "
                f"{', '.join(bookmark_positions)}</p>\n"
            )

        html_content += f"""        <p><strong>Período:</strong> {meta['period']}</p>
        <p><strong>Gerado em:</strong> {datetime.now().strftime('%d de %B de %Y')}</p>
    </div>
"""

    for entry in entries:
        if entry["type"] == "bookmark" and not app_config["include_bookmarks"]:
            continue
        if not entry["content"] and entry["type"] != "note":
            continue

        css_class = "note" if entry["type"] == "note" else "highlight"
        location_parts = []
        if entry["page"]:
            location_parts.append(f"Página {entry['page']}")
        if entry["start_pos"] and entry["end_pos"]:
            if entry["start_pos"] == entry["end_pos"]:
                location_parts.append(f"Posição: {entry['start_pos']}")
            else:
                location_parts.append(f"Posição: {entry['start_pos']}-{entry['end_pos']}")
        if entry["date_formatted"]:
            location_parts.append(entry["date_formatted"])

        location = " | ".join(location_parts)
        prefix = "NOTA " if entry["type"] == "note" else ""
        html_content += f"""
    <div class="entry {css_class}">
        <div class="entry-meta">{prefix}{location}</div>
        <div class="entry-content">{entry['content']}</div>
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
            bookmark_positions = [
                str(b["start_pos"]) for b in meta["bookmarks"] if b["start_pos"]
            ]
            txt_content += f"Posições marcadas: {', '.join(bookmark_positions)}\n"

        txt_content += f"Período: {meta['period']}\n"
        txt_content += f"Gerado em: {datetime.now().strftime('%d de %B de %Y')}\n"
        txt_content += "\n" + "-" * 50 + "\n\n"

    for entry in entries:
        if entry["type"] == "bookmark" and not app_config["include_bookmarks"]:
            continue
        if not entry["content"] and entry["type"] != "note":
            continue

        location_parts = []
        if entry["page"]:
            location_parts.append(f"Página {entry['page']}")
        if entry["start_pos"] and entry["end_pos"]:
            if entry["start_pos"] == entry["end_pos"]:
                location_parts.append(f"Posição: {entry['start_pos']}")
            else:
                location_parts.append(f"Posição: {entry['start_pos']}-{entry['end_pos']}")
        if entry["date_formatted"]:
            location_parts.append(entry["date_formatted"])

        location = " | ".join(location_parts)
        prefix = "NOTA " if entry["type"] == "note" else ""
        txt_content += f"{prefix}{location}\n"
        if entry["content"]:
            txt_content += f"{entry['content']}\n\n"

    return txt_content
