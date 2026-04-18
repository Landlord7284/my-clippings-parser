import re
import unicodedata
from datetime import datetime
from typing import Optional, Tuple


def normalize_title(title: str) -> str:
    title = re.sub(r"\s+", " ", title).strip()
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        title = title.replace(char, "")
    filename = title.lower().replace(" ", "-")
    filename = "".join(
        c for c in unicodedata.normalize("NFD", filename)
        if unicodedata.category(c) != "Mn"
    )
    return filename[:100]


def parse_title_and_author(title_line: str) -> Tuple[str, str]:
    author_match = re.search(r"\(([^)]+)\)$", title_line)

    if author_match:
        author_raw = author_match.group(1).strip()
        title = re.sub(r"\s*\([^)]+\)$", "", title_line).strip()

        if "," in author_raw:
            parts = [part.strip() for part in author_raw.split(",", 1)]
            if len(parts) == 2:
                sobrenome, nome = parts
                author = f"{nome} {sobrenome}"
            else:
                author = author_raw
        else:
            author = author_raw

        author_words = author.split()
        if len(author_words) >= 2:
            title_words = title.split()
            if len(title_words) >= len(author_words):
                last_words = title_words[-len(author_words):]
                if " ".join(last_words).lower() == author.lower():
                    title = " ".join(title_words[:-len(author_words)]).strip()
                    title = re.sub(r"\s*[-–]\s*$", "", title).strip()

        return title, author

    return title_line, "Autor desconhecido"


def parse_location(location_str: str) -> Tuple[Optional[int], Optional[int]]:
    match = re.search(
        r"posi[çc][ãa]o[:\s]+(\d+)(?:-(\d+))?",
        location_str,
        re.IGNORECASE,
    )
    if match:
        start = int(match.group(1))
        end = int(match.group(2)) if match.group(2) else start
        return start, end
    return None, None


def parse_page(location_str: str) -> Optional[int]:
    match = re.search(r"p[áa]gina\s+(\d+)", location_str, re.IGNORECASE)
    return int(match.group(1)) if match else None


def parse_date(date_str: str) -> Tuple[str, datetime]:
    months = {
        "janeiro": 1,
        "fevereiro": 2,
        "março": 3,
        "abril": 4,
        "maio": 5,
        "junho": 6,
        "julho": 7,
        "agosto": 8,
        "setembro": 9,
        "outubro": 10,
        "novembro": 11,
        "dezembro": 12,
    }

    match = re.search(r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})", date_str)
    if match:
        day = int(match.group(1))
        month_name = match.group(2).lower()
        year = int(match.group(3))

        if month_name in months:
            month = months[month_name]
            dt = datetime(year, month, day)
            formatted = f"{day} de {month_name} de {year}"
            return formatted, dt

    return date_str, datetime.now()
