from datetime import datetime

from kindle_extractor.book_selection_service import build_book_key
from kindle_extractor.extractor import KindleHighlightsExtractor
from kindle_extractor.parser import parse_date, parse_location, parse_page, parse_title_and_author


def test_parse_title_and_author_with_surname_first_format():
    title, author = parse_title_and_author("A Morte de Ivan Ilitch (Tolstói, Leon)")

    assert title == "A Morte de Ivan Ilitch"
    assert author == "Leon Tolstói"


def test_parse_title_and_author_when_author_is_missing():
    title, author = parse_title_and_author("Livro Sem Autor")

    assert title == "Livro Sem Autor"
    assert author == "Autor desconhecido"


def test_parse_title_and_author_removes_duplicated_author_suffix():
    title, author = parse_title_and_author(
        "Respire - uma vida em movimento - Rickson Gracie (Rickson Gracie)"
    )

    assert title == "Respire - uma vida em movimento"
    assert author == "Rickson Gracie"


def test_parse_location_accepts_utf8_and_legacy_encoded_text():
    utf8_line = "- Seu destaque na página 56 | posição 521-525 | Adicionado em 21 de julho de 2023"
    legacy_line = "- Seu destaque na pÃ¡gina 56 | posiÃ§Ã£o 521-525 | Adicionado em 21 de julho de 2023"

    assert parse_location(utf8_line) == (521, 525)
    assert parse_location(legacy_line) == (521, 525)


def test_parse_page_accepts_utf8_and_legacy_encoded_text():
    utf8_line = "- Seu destaque na página 56 | posição 521-525"
    legacy_line = "- Seu destaque na pÃ¡gina 56 | posiÃ§Ã£o 521-525"

    assert parse_page(utf8_line) == 56
    assert parse_page(legacy_line) == 56


def test_parse_date_reads_portuguese_months_and_returns_datetime():
    raw = "- Seu destaque | Adicionado: terça-feira, 1 de março de 2024 10:20:00"

    formatted, parsed = parse_date(raw)

    assert formatted == "1 de março de 2024"
    assert parsed == datetime(2024, 3, 1)


def test_parse_date_returns_none_when_date_is_not_parseable():
    raw = "- Seu destaque | Adicionado: data desconhecida"

    formatted, parsed = parse_date(raw)

    assert formatted == raw
    assert parsed is None


def test_parse_content_groups_entries_by_book(real_clippings_excerpt):
    extractor = KindleHighlightsExtractor(
        {
            "remove_duplicates": False,
            "export_formats": {
                "markdown": {"enabled": False, "folder": "markdown"},
                "html": {"enabled": False, "folder": "html"},
                "txt": {"enabled": False, "folder": "txt"},
            },
        }
    )

    extractor.parse_content(real_clippings_excerpt)

    titles = {entries[0]["title"] for entries in extractor.books.values()}
    assert titles == {
        "Blade Runner",
        "A Morte de Ivan Ilitch",
        "Livro Sem Autor",
    }

    blade_runner = extractor.books[build_book_key("Blade Runner", "Philip K. Dick")]
    assert len(blade_runner) == 2
    assert blade_runner[0]["author"] == "Philip K. Dick"


def test_books_with_the_same_title_are_kept_apart_by_author():
    content = (
        "Ensaios (Montaigne, Michel de)\n"
        "- Seu destaque na página 10 | posição 101-101 | Adicionado em 1 de março de 2024\n\n"
        "Trecho de Montaigne\n"
        "==========\n"
        "Ensaios (Emerson, Ralph Waldo)\n"
        "- Seu destaque na página 10 | posição 101-101 | Adicionado em 2 de março de 2024\n\n"
        "Trecho de Emerson\n"
    )

    extractor = KindleHighlightsExtractor({"remove_duplicates": True})
    extractor.parse_content(content)

    assert len(extractor.books) == 2
    assert extractor.stats["books_processed"] == 2
    montaigne = extractor.books[build_book_key("Ensaios", "Michel de Montaigne")]
    emerson = extractor.books[build_book_key("Ensaios", "Ralph Waldo Emerson")]
    assert montaigne[0]["content"] == "Trecho de Montaigne"
    assert emerson[0]["content"] == "Trecho de Emerson"


def test_parse_content_sets_unknown_author_when_missing_parentheses():
    content = (
        "Livro Sem Autor\n"
        "- Seu destaque na página 10 | posição 101-101 | Adicionado em 1 de março de 2024\n\n"
        "Trecho A\n"
        "==========\n"
        "Livro Sem Autor\n"
        "- Seu destaque na página 10 | posição 105-106 | Adicionado em 2 de março de 2024\n\n"
        "Trecho B\n"
    )

    extractor = KindleHighlightsExtractor(
        {
            "remove_duplicates": False,
            "export_formats": {
                "markdown": {"enabled": False, "folder": "markdown"},
                "html": {"enabled": False, "folder": "html"},
                "txt": {"enabled": False, "folder": "txt"},
            },
        }
    )
    extractor.parse_content(content)

    entries = extractor.books[build_book_key("Livro Sem Autor", "Autor desconhecido")]
    assert len(entries) == 2
    assert {entry["author"] for entry in entries} == {"Autor desconhecido"}
