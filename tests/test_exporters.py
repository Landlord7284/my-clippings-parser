from datetime import datetime

from kindle_extractor.extractor import KindleHighlightsExtractor
from kindle_extractor.exporters import generate_html, generate_markdown, generate_txt


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

    extractor.books = {
        "Livro A": [{**_sample_entries()[0], "title": "Livro A", "author": "Autor A"}],
        "Livro B": [{**_sample_entries()[0], "title": "Livro B", "author": "Autor B"}],
    }

    extractor.generate_files(workspace_tmp_path, selected_titles=["Livro B"])

    assert (workspace_tmp_path / "markdown" / "livro-b-autor-b.md").exists()
    assert (workspace_tmp_path / "html" / "livro-b-autor-b.html").exists()
    assert (workspace_tmp_path / "txt" / "livro-b-autor-b.txt").exists()

    assert not (workspace_tmp_path / "markdown" / "livro-a-autor-a.md").exists()
    assert not (workspace_tmp_path / "html" / "livro-a-autor-a.html").exists()
    assert not (workspace_tmp_path / "txt" / "livro-a-autor-a.txt").exists()
