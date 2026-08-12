from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
import re
import unicodedata
from typing import Dict, List, Optional

MIN_CONTAINMENT_SHORT_LENGTH = 40
MIN_CONTAINMENT_RATIO = 0.45
EXPANSION_SIMILARITY_THRESHOLD = 0.72
EXPANSION_TOKEN_OVERLAP_THRESHOLD = 0.75
DEFAULT_POSITION_OVERLAP_RATIO = 0.60
DEFAULT_TOKEN_OVERLAP_THRESHOLD = 0.75
DEFAULT_SESSION_WINDOW_MINUTES = 15
MIN_POSITION_OVERLAP_UNITS = 3


@dataclass
class DedupDecision:
    is_duplicate: bool
    reason: Optional[str] = None
    matched_index: Optional[int] = None
    replace_existing: bool = False


@dataclass
class DuplicateCandidate:
    reason: str
    priority: int
    score: float = 0.0


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


def _normalized_content(entry: Dict) -> str:
    return normalize_text(entry.get("content", ""))


def _text_completeness_score(entry: Dict) -> int:
    return len(_normalized_content(entry))


def _entry_recency_value(entry: Dict) -> datetime:
    value = entry.get("date_obj")
    if not isinstance(value, datetime):
        return datetime.min
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _entry_preference_key(entry: Dict):
    end_pos = entry.get("end_pos")
    safe_end_pos = end_pos if isinstance(end_pos, int) else -1
    recency = _entry_recency_value(entry)
    return (
        recency != datetime.min,
        recency,
        _text_completeness_score(entry),
        safe_end_pos,
    )


def choose_survivor(new_entry: Dict, existing: Dict) -> Dict:
    if _entry_preference_key(new_entry) > _entry_preference_key(existing):
        return new_entry
    return existing


def _prefer_new_entry(new_entry: Dict, existing: Dict) -> bool:
    return choose_survivor(new_entry, existing) is new_entry


def _replacement_reason(reason: str) -> str:
    return f"{reason}_replaced_by_preferred_record"


def _kept_existing_reason(reason: str) -> str:
    return f"{reason}_kept_existing_preferred_record"


def _has_same_type(new_entry: Dict, existing: Dict) -> bool:
    return _entry_type(new_entry) == _entry_type(existing)


def _has_same_type_and_start(new_entry: Dict, existing: Dict) -> bool:
    return _has_same_type(new_entry, existing) and (
        new_entry.get("start_pos") == existing.get("start_pos")
    )


def _has_position_range(entry: Dict) -> bool:
    return isinstance(entry.get("start_pos"), int) and isinstance(entry.get("end_pos"), int)


def _normalized_range(entry: Dict):
    if not _has_position_range(entry):
        return None
    start = entry["start_pos"]
    end = entry["end_pos"]
    return (min(start, end), max(start, end))


def _same_full_range(new_entry: Dict, existing: Dict) -> bool:
    return (
        _has_position_range(new_entry)
        and _has_position_range(existing)
        and _normalized_range(new_entry) == _normalized_range(existing)
    )


def _position_overlap_units(new_entry: Dict, existing: Dict) -> int:
    new_range = _normalized_range(new_entry)
    existing_range = _normalized_range(existing)
    if not new_range or not existing_range:
        return 0

    overlap_start = max(new_range[0], existing_range[0])
    overlap_end = min(new_range[1], existing_range[1])
    if overlap_end < overlap_start:
        return 0
    return overlap_end - overlap_start + 1


def _position_overlap_ratio(new_entry: Dict, existing: Dict) -> float:
    overlap = _position_overlap_units(new_entry, existing)
    if overlap <= 0:
        return 0.0

    new_range = _normalized_range(new_entry)
    existing_range = _normalized_range(existing)
    if not new_range or not existing_range:
        return 0.0

    new_length = new_range[1] - new_range[0] + 1
    existing_length = existing_range[1] - existing_range[0] + 1
    return overlap / max(min(new_length, existing_length), 1)


def _valid_session_delta_seconds(new_entry: Dict, existing: Dict):
    new_date = _entry_recency_value(new_entry)
    existing_date = _entry_recency_value(existing)
    if new_date == datetime.min or existing_date == datetime.min:
        return None
    return abs((new_date - existing_date).total_seconds())


def _within_session_window(new_entry: Dict, existing: Dict, config: Dict) -> bool:
    window_minutes = float(
        config.get("dedup_session_window_minutes", DEFAULT_SESSION_WINDOW_MINUTES)
    )
    if window_minutes <= 0:
        return False

    delta_seconds = _valid_session_delta_seconds(new_entry, existing)
    if delta_seconds is None:
        return False
    return delta_seconds <= window_minutes * 60


def _material_position_overlap(new_entry: Dict, existing: Dict, config: Dict) -> float:
    overlap_units = _position_overlap_units(new_entry, existing)
    if overlap_units <= 0:
        return 0.0

    ratio = _position_overlap_ratio(new_entry, existing)
    threshold = float(
        config.get("dedup_position_overlap_ratio", DEFAULT_POSITION_OVERLAP_RATIO)
    )
    if ratio >= threshold:
        return ratio
    if overlap_units >= MIN_POSITION_OVERLAP_UNITS:
        return ratio
    if _within_session_window(new_entry, existing, config):
        return ratio
    return 0.0


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


def _text_contains(text_a: str, text_b: str) -> bool:
    if not text_a or not text_b:
        return False
    shorter, longer = (text_a, text_b) if len(text_a) <= len(text_b) else (text_b, text_a)
    return shorter in longer


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


def _bidirectional_token_overlap_ratio(text_a: str, text_b: str) -> float:
    if not text_a or not text_b:
        return 0.0
    return min(_token_overlap_ratio(text_a, text_b), _token_overlap_ratio(text_b, text_a))


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


def _has_related_text(text_a: str, text_b: str, config: Dict) -> bool:
    if not text_a or not text_b:
        return False
    if _text_contains_with_proximity(text_a, text_b):
        return True

    token_threshold = float(
        config.get("dedup_token_overlap_threshold", DEFAULT_TOKEN_OVERLAP_THRESHOLD)
    )
    if _bidirectional_token_overlap_ratio(text_a, text_b) >= token_threshold:
        return True

    return _is_clear_expansion_pair(text_a, text_b)


def _build_similarity_ratio(new_entry: Dict, existing: Dict) -> float:
    return SequenceMatcher(
        None,
        new_entry.get("content", "") or "",
        existing.get("content", "") or "",
    ).ratio()


def _missing_any_position(new_entry: Dict, existing: Dict) -> bool:
    return not _has_position_range(new_entry) or not _has_position_range(existing)


def _candidate(reason: str, priority: int, score: float = 0.0) -> DuplicateCandidate:
    return DuplicateCandidate(reason=reason, priority=priority, score=score)


def _candidate_sort_key(candidate: DuplicateCandidate):
    return (candidate.priority, candidate.score)


def detect_duplicate_candidate(
    new_entry: Dict,
    existing: Dict,
    config: Dict,
) -> Optional[DuplicateCandidate]:
    if not _has_same_type(new_entry, existing):
        return None

    new_content_normalized = _normalized_content(new_entry)
    existing_normalized = _normalized_content(existing)

    if (
        _same_full_range(new_entry, existing)
        and new_content_normalized == existing_normalized
    ):
        return _candidate("exact_duplicate", 100, 1.0)

    if (
        _has_same_type_and_start(new_entry, existing)
        and new_entry.get("end_pos") != existing.get("end_pos")
        and _text_contains(new_content_normalized, existing_normalized)
    ):
        return _candidate("same_start_containment", 90, 1.0)

    if (
        _same_full_range(new_entry, existing)
        and _text_contains(new_content_normalized, existing_normalized)
    ):
        return _candidate("same_range_containment", 85, 1.0)

    position_score = _material_position_overlap(new_entry, existing, config)
    if (
        position_score
        and not _same_full_range(new_entry, existing)
        and _has_related_text(new_content_normalized, existing_normalized, config)
    ):
        return _candidate("position_overlap", 80, position_score)

    if _has_same_type_and_start(new_entry, existing):
        existing_end = existing.get("end_pos")
        new_end = new_entry.get("end_pos")
        if (
            isinstance(new_end, int)
            and isinstance(existing_end, int)
            and new_end != existing_end
            and _is_clear_expansion_pair(new_content_normalized, existing_normalized)
        ):
            return _candidate("same_start_expansion", 75, 1.0)

    similarity_threshold = float(config.get("similarity_threshold", 0.8))
    if _missing_any_position(new_entry, existing):
        if new_content_normalized and existing_normalized:
            if _text_contains_with_proximity(new_content_normalized, existing_normalized):
                return _candidate("text_containment_without_position", 60, 1.0)

            similarity = _build_similarity_ratio(new_entry, existing)
            if similarity >= similarity_threshold:
                return _candidate("similarity_fallback", 50, similarity)

        if not new_content_normalized and not existing_normalized:
            return _candidate("similarity_fallback_empty_content", 50, 1.0)

    if _same_full_range(new_entry, existing):
        existing_content = existing.get("content")
        new_content = new_entry.get("content")

        if new_content and existing_content:
            similarity = _build_similarity_ratio(new_entry, existing)
            if similarity >= similarity_threshold:
                return _candidate("similarity_fallback", 50, similarity)
        elif not new_content and not existing_content:
            return _candidate("similarity_fallback_empty_content", 50, 1.0)

    return None


def decide_duplicate(
    new_entry: Dict,
    existing_entries: List[Dict],
    config: Dict,
) -> DedupDecision:
    if not config["remove_duplicates"]:
        return DedupDecision(False)

    best_match = None
    best_candidate = None
    for idx, existing in enumerate(existing_entries):
        candidate = detect_duplicate_candidate(new_entry, existing, config)
        if not candidate:
            continue
        if best_candidate is None or _candidate_sort_key(candidate) > _candidate_sort_key(
            best_candidate
        ):
            best_match = idx
            best_candidate = candidate

    if best_match is not None and best_candidate is not None:
        existing = existing_entries[best_match]
        if _prefer_new_entry(new_entry, existing):
            return DedupDecision(
                True,
                reason=_replacement_reason(best_candidate.reason),
                matched_index=best_match,
                replace_existing=True,
            )
        return DedupDecision(
            True,
            reason=_kept_existing_reason(best_candidate.reason),
            matched_index=best_match,
        )

    return DedupDecision(False)
