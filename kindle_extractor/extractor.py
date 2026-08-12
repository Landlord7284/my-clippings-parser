from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .book_selection_service import build_book_key
from .config import deep_merge, get_default_config
from .dedup import decide_duplicate, is_duplicate
from .exporters import generate_html, generate_markdown, generate_txt
from .parser import (
    normalize_title,
    parse_date,
    parse_location,
    parse_page,
    parse_title_and_author,
)


class KindleHighlightsExtractor:
    def __init__(self, config_dict: dict = None):
        self.config = deep_merge(get_default_config(), config_dict or {})
        self.books: Dict[str, List[dict]] = {}
        self.stats = {
            "total_entries": 0,
            "duplicates_removed": 0,
            "books_processed": 0,
            "errors": 0,
            "files_generated": {"markdown": 0, "html": 0, "txt": 0},
            "dedup_metrics": {
                "exact_duplicates_removed": 0,
                "same_start_containment_conflicts": 0,
                "same_start_expansion_conflicts": 0,
                "same_range_containment_conflicts": 0,
                "position_overlap_conflicts": 0,
                "similarity_fallback_removed": 0,
                "records_replaced": 0,
            },
            "dedup_report": [],
        }

    def get_default_config(self) -> dict:
        return get_default_config()

    def normalize_title(self, title: str) -> str:
        return normalize_title(title)

    def parse_title_and_author(self, title_line: str) -> Tuple[str, str]:
        return parse_title_and_author(title_line)

    def parse_location(self, location_str: str) -> Tuple[Optional[int], Optional[int]]:
        return parse_location(location_str)

    def parse_page(self, location_str: str) -> Optional[int]:
        return parse_page(location_str)

    def parse_date(self, date_str: str):
        return parse_date(date_str)

    def is_duplicate(self, new_entry: dict, existing_entries: List[dict]) -> bool:
        return is_duplicate(new_entry, existing_entries, self.config)

    def _register_dedup_result(self, title: str, entry: dict, reason: str):
        dedup_metrics = self.stats["dedup_metrics"]
        if reason.startswith("exact_duplicate"):
            dedup_metrics["exact_duplicates_removed"] += 1
        elif reason.startswith("same_start_containment"):
            dedup_metrics["same_start_containment_conflicts"] += 1
        elif reason.startswith("same_start_expansion"):
            dedup_metrics["same_start_expansion_conflicts"] += 1
        elif reason.startswith("same_range_containment"):
            dedup_metrics["same_range_containment_conflicts"] += 1
        elif reason.startswith("position_overlap"):
            dedup_metrics["position_overlap_conflicts"] += 1
        elif reason.startswith("similarity_fallback"):
            dedup_metrics["similarity_fallback_removed"] += 1

        if "replaced_by_" in reason:
            dedup_metrics["records_replaced"] += 1

        self.stats["dedup_report"].append(
            {
                "title": title,
                "reason": reason,
                "start_pos": entry.get("start_pos"),
                "end_pos": entry.get("end_pos"),
                "content_preview": (entry.get("content", "") or "")[:120],
            }
        )

    def process_entry(self, entry_text: str):
        lines = entry_text.strip().split("\n")
        if len(lines) < 2:
            return

        try:
            title_line = lines[0].strip()
            title, author = self.parse_title_and_author(title_line)
            metadata_line = lines[1].strip()

            if "destaque" in metadata_line.lower():
                entry_type = "highlight"
            elif "nota" in metadata_line.lower():
                entry_type = "note"
            elif "marcador" in metadata_line.lower():
                entry_type = "bookmark"
            else:
                entry_type = "unknown"

            start_pos, end_pos = self.parse_location(metadata_line)
            page = self.parse_page(metadata_line)
            date_formatted, date_obj = self.parse_date(metadata_line)

            content = ""
            if len(lines) > 2:
                content = "\n".join(lines[2:]).strip()

            entry = {
                "type": entry_type,
                "title": title,
                "author": author,
                "page": page,
                "start_pos": start_pos,
                "end_pos": end_pos,
                "content": content,
                "date_formatted": date_formatted,
                "date_obj": date_obj,
                "metadata_line": metadata_line,
            }

            book_entries = self.books.setdefault(build_book_key(title, author), [])

            dedup_decision = decide_duplicate(entry, book_entries, self.config)
            if not dedup_decision.is_duplicate:
                book_entries.append(entry)
                self.stats["total_entries"] += 1
            else:
                if (
                    dedup_decision.replace_existing
                    and dedup_decision.matched_index is not None
                ):
                    book_entries[dedup_decision.matched_index] = entry
                self.stats["duplicates_removed"] += 1
                self._register_dedup_result(
                    title,
                    entry,
                    dedup_decision.reason or "dedup_unknown_reason",
                )
        except Exception:
            self.stats["errors"] += 1

    def parse_content(self, content: str):
        entries = content.split("==========")
        for entry in entries:
            if entry.strip():
                self.process_entry(entry.strip())
        self.stats["books_processed"] = len(self.books)

    def sort_entries(self, entries: List[dict]) -> List[dict]:
        from .exporters import sort_entries

        return sort_entries(entries)

    def generate_markdown(self, title: str, entries: List[dict], format_config: dict) -> str:
        return generate_markdown(title, entries, format_config, self.config)

    def generate_html(self, title: str, entries: List[dict], format_config: dict) -> str:
        return generate_html(title, entries, format_config, self.config)

    def generate_txt(self, title: str, entries: List[dict], format_config: dict) -> str:
        return generate_txt(title, entries, format_config, self.config)

    def generate_files(self, output_dir: Path, selected_keys=None):
        keys_to_export = selected_keys or list(self.books.keys())

        for format_name, format_config in self.config["export_formats"].items():
            if not format_config.get("enabled", False):
                continue

            format_dir = output_dir / format_config["folder"]
            format_dir.mkdir(parents=True, exist_ok=True)

            for book_key in keys_to_export:
                entries = self.books.get(book_key, [])
                if not entries:
                    continue
                title = entries[0]["title"]
                author = entries[0]["author"] or "autor-desconhecido"
                safe_author = self.normalize_title(author)
                filename = f"{self.normalize_title(title)}-{safe_author}"

                if format_name == "markdown":
                    content = self.generate_markdown(title, entries, format_config)
                    filepath = format_dir / f"{filename}.md"
                elif format_name == "html":
                    content = self.generate_html(title, entries, format_config)
                    filepath = format_dir / f"{filename}.html"
                elif format_name == "txt":
                    content = self.generate_txt(title, entries, format_config)
                    filepath = format_dir / f"{filename}.txt"
                else:
                    continue

                try:
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(content)
                    self.stats["files_generated"][format_name] += 1
                except Exception:
                    self.stats["errors"] += 1
