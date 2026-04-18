from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
import re
import unicodedata
from typing import Dict, List, Optional


DEFAULT_PREFIX_WORDS = 5


@dataclass
class DedupDecision:
    is_duplicate: bool
    reason: Optional[str] = None
    matched_index: Optional[int] = None
    replace_existing: bool = False


def normalize_text(text: Optional[str]) -> str:
    if not text:
        return ""

    normalized = unicodedata.normalize("NFD", text.casefold())
    normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _normalized_prefix(text: Optional[str], words: int) -> str:
    normalized = normalize_text(text)
    if not normalized:
        return ""
    tokens = normalized.split()
    return " ".join(tokens[:words])


def _text_completeness_score(entry: Dict) -> int:
    return len(normalize_text(entry.get("content", "")))


def _entry_recency_value(entry: Dict):
    value = entry.get("date_obj")
    if isinstance(value, datetime):
        return value
    return datetime.min


def _entry_preference_key(entry: Dict):
    end_pos = entry.get("end_pos")
    safe_end_pos = end_pos if isinstance(end_pos, int) else -1
    return (
        safe_end_pos,
        _text_completeness_score(entry),
        _entry_recency_value(entry),
    )


def _build_similarity_ratio(new_entry: Dict, existing: Dict) -> float:
    return SequenceMatcher(
        None,
        new_entry.get("content", "") or "",
        existing.get("content", "") or "",
    ).ratio()


def decide_duplicate(
    new_entry: Dict,
    existing_entries: List[Dict],
    config: Dict,
) -> DedupDecision:
    if not config["remove_duplicates"]:
        return DedupDecision(False)

    new_start = new_entry.get("start_pos")
    new_end = new_entry.get("end_pos")
    new_content_normalized = normalize_text(new_entry.get("content"))

    # Layer 1: exact duplicates
    for idx, existing in enumerate(existing_entries):
        if (
            new_start == existing.get("start_pos")
            and new_end == existing.get("end_pos")
            and new_content_normalized == normalize_text(existing.get("content"))
        ):
            if _entry_preference_key(new_entry) > _entry_preference_key(existing):
                return DedupDecision(
                    True,
                    reason="exact_duplicate_replaced_by_better_record",
                    matched_index=idx,
                    replace_existing=True,
                )
            return DedupDecision(True, reason="exact_duplicate", matched_index=idx)

    # Layer 2: same start position + same normalized text prefix
    prefix_words = int(config.get("dedup_prefix_words", DEFAULT_PREFIX_WORDS))
    new_prefix = _normalized_prefix(new_entry.get("content"), prefix_words)
    if new_start is not None and new_prefix:
        for idx, existing in enumerate(existing_entries):
            if new_start != existing.get("start_pos"):
                continue
            existing_prefix = _normalized_prefix(existing.get("content"), prefix_words)
            if not existing_prefix or new_prefix != existing_prefix:
                continue

            if _entry_preference_key(new_entry) > _entry_preference_key(existing):
                return DedupDecision(
                    True,
                    reason="same_start_prefix_replaced_by_better_record",
                    matched_index=idx,
                    replace_existing=True,
                )

            return DedupDecision(
                True,
                reason="same_start_prefix_kept_existing_better_record",
                matched_index=idx,
            )

    # Layer 3: existing fallback similarity rule
    for idx, existing in enumerate(existing_entries):
        if (
            new_start == existing.get("start_pos")
            and new_end == existing.get("end_pos")
            and new_start is not None
        ):
            if new_entry.get("content") and existing.get("content"):
                similarity = _build_similarity_ratio(new_entry, existing)
                if similarity >= config["similarity_threshold"]:
                    if _entry_preference_key(new_entry) > _entry_preference_key(existing):
                        return DedupDecision(
                            True,
                            reason="similarity_fallback_replaced_by_better_record",
                            matched_index=idx,
                            replace_existing=True,
                        )
                    return DedupDecision(
                        True,
                        reason="similarity_fallback",
                        matched_index=idx,
                    )
            elif not new_entry.get("content") and not existing.get("content"):
                if _entry_preference_key(new_entry) > _entry_preference_key(existing):
                    return DedupDecision(
                        True,
                        reason="similarity_fallback_empty_content_replaced_by_better_record",
                        matched_index=idx,
                        replace_existing=True,
                    )
                return DedupDecision(
                    True,
                    reason="similarity_fallback_empty_content",
                    matched_index=idx,
                )

    return DedupDecision(False)


def is_duplicate(new_entry: Dict, existing_entries: List[Dict], config: Dict) -> bool:
    return decide_duplicate(new_entry, existing_entries, config).is_duplicate
