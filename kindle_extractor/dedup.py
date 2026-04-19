from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
import re
import unicodedata
from typing import Dict, List, Optional

DEFAULT_PREFIX_WORDS = 5
MIN_CONTAINMENT_SHORT_LENGTH = 40
MIN_CONTAINMENT_RATIO = 0.45
EXPANSION_SIMILARITY_THRESHOLD = 0.72
EXPANSION_TOKEN_OVERLAP_THRESHOLD = 0.75


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


def _entry_type(entry: Dict) -> str:
    return str(entry.get("type") or "highlight")


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


def _normalized_content(entry: Dict) -> str:
    return normalize_text(entry.get("content", ""))


def _has_same_type_and_start(new_entry: Dict, existing: Dict) -> bool:
    return (
        _entry_type(new_entry) == _entry_type(existing)
        and new_entry.get("start_pos") == existing.get("start_pos")
    )


def _text_contains_with_proximity(text_a: str, text_b: str) -> bool:
    if not text_a or not text_b:
        return False
    if text_a == text_b:
        return True

    shorter, longer = (text_a, text_b) if len(text_a) <= len(text_b) else (text_b, text_a)
    if shorter not in longer:
        return False

    if len(shorter) >= MIN_CONTAINMENT_SHORT_LENGTH:
        return True

    ratio = len(shorter) / max(len(longer), 1)
    return ratio >= MIN_CONTAINMENT_RATIO


def _token_overlap_ratio(base_text: str, other_text: str) -> float:
    base_tokens = base_text.split()
    if not base_tokens:
        return 0.0

    base_unique = set(base_tokens)
    if not base_unique:
        return 0.0

    other_unique = set(other_text.split())
    common = len(base_unique & other_unique)
    return common / len(base_unique)


def _is_clear_expansion_pair(text_a: str, text_b: str) -> bool:
    if not text_a or not text_b:
        return False

    shorter, longer = (text_a, text_b) if len(text_a) <= len(text_b) else (text_b, text_a)

    if shorter in longer:
        return True

    similarity = SequenceMatcher(None, shorter, longer[: len(shorter) + 40]).ratio()
    overlap = _token_overlap_ratio(shorter, longer)
    return (
        similarity >= EXPANSION_SIMILARITY_THRESHOLD
        and overlap >= EXPANSION_TOKEN_OVERLAP_THRESHOLD
    )


def _prefer_new_entry(new_entry: Dict, existing: Dict) -> bool:
    return _entry_preference_key(new_entry) > _entry_preference_key(existing)


def decide_duplicate(
    new_entry: Dict,
    existing_entries: List[Dict],
    config: Dict,
) -> DedupDecision:
    if not config["remove_duplicates"]:
        return DedupDecision(False)

    new_start = new_entry.get("start_pos")
    new_end = new_entry.get("end_pos")
    new_type = _entry_type(new_entry)
    new_content_normalized = _normalized_content(new_entry)

    # Layer 1: exact duplicates (same type, same position range, same normalized text)
    for idx, existing in enumerate(existing_entries):
        if (
            new_type == _entry_type(existing)
            and new_start == existing.get("start_pos")
            and new_end == existing.get("end_pos")
            and new_content_normalized == _normalized_content(existing)
        ):
            if _prefer_new_entry(new_entry, existing):
                return DedupDecision(
                    True,
                    reason="exact_duplicate_replaced_by_better_record",
                    matched_index=idx,
                    replace_existing=True,
                )
            return DedupDecision(True, reason="exact_duplicate", matched_index=idx)

    # Layer 2: same start position + text containment (excluding exact same range)
    for idx, existing in enumerate(existing_entries):
        if not _has_same_type_and_start(new_entry, existing):
            continue
        if new_end == existing.get("end_pos"):
            continue

        existing_normalized = _normalized_content(existing)
        if not _text_contains_with_proximity(new_content_normalized, existing_normalized):
            continue

        if _prefer_new_entry(new_entry, existing):
            return DedupDecision(
                True,
                reason="same_start_containment_replaced_by_better_record",
                matched_index=idx,
                replace_existing=True,
            )

        return DedupDecision(
            True,
            reason="same_start_containment_kept_existing_better_record",
            matched_index=idx,
        )

    # Layer 3: same start position + clear expansion by longer range/text
    for idx, existing in enumerate(existing_entries):
        if not _has_same_type_and_start(new_entry, existing):
            continue

        existing_end = existing.get("end_pos")
        if not isinstance(new_end, int) or not isinstance(existing_end, int):
            continue
        if new_end == existing_end:
            continue

        existing_normalized = _normalized_content(existing)
        if not _is_clear_expansion_pair(new_content_normalized, existing_normalized):
            continue

        if _prefer_new_entry(new_entry, existing):
            return DedupDecision(
                True,
                reason="same_start_expansion_replaced_by_better_record",
                matched_index=idx,
                replace_existing=True,
            )

        return DedupDecision(
            True,
            reason="same_start_expansion_kept_existing_better_record",
            matched_index=idx,
        )

    # Layer 4: same full range + redundant subtext
    for idx, existing in enumerate(existing_entries):
        if (
            new_type != _entry_type(existing)
            or new_start != existing.get("start_pos")
            or new_end != existing.get("end_pos")
        ):
            continue

        existing_normalized = _normalized_content(existing)
        if not _text_contains_with_proximity(new_content_normalized, existing_normalized):
            continue

        if _prefer_new_entry(new_entry, existing):
            return DedupDecision(
                True,
                reason="same_range_containment_replaced_by_better_record",
                matched_index=idx,
                replace_existing=True,
            )

        return DedupDecision(
            True,
            reason="same_range_containment_kept_existing_better_record",
            matched_index=idx,
        )

    # Layer 5: conservative fallback by similarity
    similarity_threshold = float(config.get("similarity_threshold", 0.8))
    for idx, existing in enumerate(existing_entries):
        if (
            new_type != _entry_type(existing)
            or new_start != existing.get("start_pos")
            or new_end != existing.get("end_pos")
            or new_start is None
        ):
            continue

        existing_content = existing.get("content")
        new_content = new_entry.get("content")

        if new_content and existing_content:
            similarity = _build_similarity_ratio(new_entry, existing)
            if similarity >= similarity_threshold:
                if _prefer_new_entry(new_entry, existing):
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
        elif not new_content and not existing_content:
            if _prefer_new_entry(new_entry, existing):
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
