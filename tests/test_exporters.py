import re
from datetime import datetime

from kindle_extractor.book_selection_service import build_book_key
from kindle_extractor.extractor import KindleHighlightsExtractor
from kindle_extractor.exporters import (
    build_note_blocks,
    generate_html,
    generate_markdown,
    generate_obsidian,
    generate_txt,
    render_note_blocks_html,
    render_note_blocks_markdown,
)


def _sample_entries():
    return [
        {
            "type": "highlight",
            "title": "Clean Code",
            "author": "Robert C. Martin",
            "page": 12,
            "start_pos": 200,
            "end_pos": 201,
            "content": "Código limpo importa.",
            "date_formatted": "2 de fevereiro de 2024",
            "date_obj": datetime(2024, 2, 2),
            "metadata_line": "",
        },
        {
            "type": "note",
            "title": "Clean Code",
            "author": "Robert C. Martin",
            "page": 12,
            "start_pos": 202,
            "end_pos": 202,
            "content": "Revisar este trecho depois.",
            "date_formatted": "2 de fevereiro de 2024",
            "date_obj": datetime(2024, 2, 2),
            "metadata_line": "",
        },
        {
            "type": "bookmark",
            "title": "Clean Code",
            "author": "Robert C. Martin",
            "page": 12,
            "start_pos": 203,
            "end_pos": 203,
            "content": "",
            "date_formatted": "2 de fevereiro de 2024",
            "date_obj": datetime(2024, 2, 2),
            "metadata_line": "",
        },
    ]


def test_markdown_export_contains_core_book_content_not_cosmetic_details():
    entries = _sample_entries()
    content = generate_markdown(
        "Clean Code",
        entries,
        {"include_metadata": True},
        {"include_bookmarks": True},
    )

    assert "# Clean Code - Robert C. Martin" in content
    assert "**Total de destaques**: 1" in content
    assert "Código limpo importa." in content
    assert "**NOTA**" in content


def test_html_and_txt_allow_metadata_toggle():
    entries = _sample_entries()

    html = generate_html(
        "Clean Code",
        entries,
        {"include_metadata": False},
        {"include_bookmarks": True},
    )
    txt = generate_txt(
        "Clean Code",
        entries,
        {"include_metadata": False},
        {"include_bookmarks": True},
    )

    assert "<h1>Clean Code - Robert C. Martin</h1>" in html
    assert "Autor:" not in html
    assert "Total de destaques" not in txt
    assert "Revisar este trecho depois." in txt


def test_html_escapes_content_so_kindle_clip_limit_marker_survives():
    """O Kindle grava '<Você alcançou o limite de recortes...>' dentro do destaque.

    Sem escaping o navegador trata isso como tag e engole o texto.
    """
    entries = [
        {
            **_sample_entries()[0],
            "content": 'Pensar em mais de uma coisa e <Você alcançou o limite> & "fim".',
        }
    ]

    html = generate_html(
        "Clean Code",
        entries,
        {"include_metadata": False},
        {"include_bookmarks": True},
    )

    assert "&lt;Você alcançou o limite&gt;" in html
    assert "&amp;" in html
    assert "<Você alcançou" not in html


def test_html_escapes_title_and_author():
    entries = [{**_sample_entries()[0], "title": "A & B", "author": "<script>"}]

    html = generate_html(
        "A & B",
        entries,
        {"include_metadata": True},
        {"include_bookmarks": True},
    )

    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "A &amp; B" in html


def test_dates_use_portuguese_months_regardless_of_locale():
    """strftime('%B') dependeria do locale do processo e imprimiria 'February'."""
    entries = _sample_entries()

    for content in (
        generate_markdown("Clean Code", entries, {"include_metadata": True}, {"include_bookmarks": True}),
        generate_html("Clean Code", entries, {"include_metadata": True}, {"include_bookmarks": True}),
        generate_txt("Clean Code", entries, {"include_metadata": True}, {"include_bookmarks": True}),
    ):
        assert "2 de fevereiro de 2024" in content
        assert "February" not in content


def test_bookmarks_appear_in_the_body_when_enabled():
    entries = _sample_entries()

    markdown = generate_markdown(
        "Clean Code", entries, {"include_metadata": True}, {"include_bookmarks": True}
    )
    txt = generate_txt(
        "Clean Code", entries, {"include_metadata": True}, {"include_bookmarks": True}
    )
    hidden = generate_markdown(
        "Clean Code", entries, {"include_metadata": True}, {"include_bookmarks": False}
    )

    assert "**MARCADOR** Página 12 | Posição: 203" in markdown
    assert "MARCADOR Página 12 | Posição: 203" in txt
    assert "MARCADOR" not in hidden


def test_position_zero_is_not_dropped_as_falsy():
    entries = [{**_sample_entries()[0], "page": 0, "start_pos": 0, "end_pos": 0}]

    markdown = generate_markdown(
        "Clean Code", entries, {"include_metadata": False}, {"include_bookmarks": True}
    )

    assert "Página 0" in markdown
    assert "Posição: 0" in markdown


def test_obsidian_export_carries_the_web_clipper_properties():
    entries = _sample_entries()

    content = generate_obsidian(
        "Clean Code", entries, {"include_metadata": True}, {"include_bookmarks": True}
    )

    frontmatter = content.split("---")[1]
    assert 'title: "Clean Code"' in frontmatter
    assert 'author: "Robert C. Martin"' in frontmatter
    assert 'type: "livro"' in frontmatter
    assert "documented: true" in frontmatter
    assert 'format:\n  - "ebook"' in frontmatter
    # Sem aspas: o Obsidian so reconhece a propriedade como data desse jeito.
    assert re.search(r"\ncreated: \d{4}-\d{2}-\d{2}\n", frontmatter)

    # As demais propriedades do template existem, vazias, para preenchimento manual.
    for name in ("contributors", "pages", "language", "isbn", "genres", "started", "rating"):
        assert f"\n{name}:\n" in frontmatter

    assert "# Citações e Destaques" in content
    assert "> [!quote] Página 12 · Posição: 200" in content
    assert "> Código limpo importa." in content
    assert "> [!note] Nota — Página 12 · Posição: 202" in content
    assert "**Marcador** — Página 12 · Posição: 203" in content


def test_obsidian_frontmatter_survives_titles_with_colons_and_quotes():
    entries = [{**_sample_entries()[0], "author": 'Autor "X"'}]

    content = generate_obsidian(
        'Livro: a "sequência"', entries, {"include_metadata": True}, {"include_bookmarks": True}
    )

    assert 'title: "Livro: a \\"sequência\\""' in content
    assert 'author: "Autor \\"X\\""' in content


def test_obsidian_export_quotes_multiline_highlights():
    entries = [{**_sample_entries()[0], "content": "Primeira linha.\n\nSegunda linha."}]

    content = generate_obsidian(
        "Clean Code", entries, {"include_metadata": False}, {"include_bookmarks": True}
    )

    assert "> Primeira linha.\n>\n> Segunda linha." in content


def test_obsidian_metadata_callout_follows_the_include_metadata_flag():
    entries = _sample_entries()

    with_metadata = generate_obsidian(
        "Clean Code", entries, {"include_metadata": True}, {"include_bookmarks": True}
    )
    without_metadata = generate_obsidian(
        "Clean Code", entries, {"include_metadata": False}, {"include_bookmarks": True}
    )

    assert "> [!info]- Metadados do recorte" in with_metadata
    # Dois espacos no fim: a quebra forte que o Obsidian precisa dentro do callout.
    assert "> **Total de destaques**: 1  \n" in with_metadata
    assert "> **Total de notas**: 1  \n" in with_metadata
    assert "> **Posições marcadas**: 203  \n" in with_metadata
    assert "> **Período**: 2 de fevereiro de 2024 - 2 de fevereiro de 2024  \n" in with_metadata
    # Titulo e autor ficam so nas propriedades.
    assert "**Autor**" not in with_metadata

    assert "Metadados do recorte" not in without_metadata
    assert "> [!quote] Página 12 · Posição: 200" in without_metadata


def test_clip_page_body_and_obsidian_body_come_from_the_same_blocks():
    """Os dois caminhos ja divergiram em silencio; a paridade agora e estrutural."""
    entries = _sample_entries()
    blocks = build_note_blocks(entries, include_metadata=True, include_bookmarks=True)

    markdown = render_note_blocks_markdown(blocks)
    page = render_note_blocks_html(blocks)

    for block in blocks:
        if block["kind"] == "marker":
            assert f"**{block['label']}** — {block['location']}" in markdown
            assert f"<strong>{block['label']}</strong> — {block['location']}" in page
            continue

        fold = block.get("fold", "")
        assert f"> [!{block['type']}]{fold} {block['title']}" in markdown
        assert f'data-callout="{block["type"]}"' in page
        assert f'<div class="callout-title-inner">{block["title"]}</div>' in page

        if "fields" in block:
            for label, value in block["fields"]:
                assert f"> **{label}**: {value}" in markdown
                assert f"<strong>{label}</strong>: {value}" in page
        else:
            assert f"> {block['text']}" in markdown
            assert f"<p>{block['text']}</p>" in page


def test_clip_page_body_escapes_html_in_highlights():
    entries = [
        {
            **_sample_entries()[0],
            "content": "<Você alcançou o limite de recortes para este item>",
        }
    ]

    page = render_note_blocks_html(
        build_note_blocks(entries, include_metadata=False, include_bookmarks=True)
    )

    assert "&lt;Você alcançou o limite de recortes para este item&gt;" in page
    assert "<Você" not in page


def test_generate_files_uses_normalized_filenames(workspace_tmp_path):
    extractor = KindleHighlightsExtractor(
        {
            "export_formats": {
                "markdown": {"enabled": True, "include_metadata": True, "folder": "markdown"},
                "html": {"enabled": False, "folder": "html"},
                "txt": {"enabled": False, "folder": "txt"},
            }
        }
    )
    extractor.books = {
        "Código Limpo: edição especial": [
            {
                **_sample_entries()[0],
                "title": "Código Limpo: edição especial",
                "author": "Robert C. Martin",
            }
        ]
    }

    extractor.generate_files(workspace_tmp_path)

    expected = workspace_tmp_path / "markdown" / "codigo-limpo-edicao-especial-robert-c.-martin.md"
    assert expected.exists()


def test_generate_files_exports_only_selected_books(workspace_tmp_path):
    extractor = KindleHighlightsExtractor(
        {
            "export_formats": {
                "markdown": {"enabled": True, "include_metadata": True, "folder": "markdown"},
                "html": {"enabled": True, "include_metadata": True, "folder": "html"},
                "txt": {"enabled": True, "include_metadata": True, "folder": "txt"},
            }
        }
    )

    key_a = build_book_key("Livro A", "Autor A")
    key_b = build_book_key("Livro B", "Autor B")
    extractor.books = {
        key_a: [{**_sample_entries()[0], "title": "Livro A", "author": "Autor A"}],
        key_b: [{**_sample_entries()[0], "title": "Livro B", "author": "Autor B"}],
    }

    extractor.generate_files(workspace_tmp_path, selected_keys=[key_b])

    assert (workspace_tmp_path / "markdown" / "livro-b-autor-b.md").exists()
    assert (workspace_tmp_path / "html" / "livro-b-autor-b.html").exists()
    assert (workspace_tmp_path / "txt" / "livro-b-autor-b.txt").exists()

    assert not (workspace_tmp_path / "markdown" / "livro-a-autor-a.md").exists()
    assert not (workspace_tmp_path / "html" / "livro-a-autor-a.html").exists()
    assert not (workspace_tmp_path / "txt" / "livro-a-autor-a.txt").exists()
