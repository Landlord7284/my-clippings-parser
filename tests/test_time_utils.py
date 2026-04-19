from datetime import datetime, timezone

from kindle_extractor.datetime_utils import ensure_utc_datetime, format_iso_for_display, parse_iso_to_utc


def test_ensure_utc_datetime_treats_naive_datetime_as_utc():
    value = ensure_utc_datetime(datetime(2024, 1, 1, 12, 0))

    assert value.isoformat() == "2024-01-01T12:00:00+00:00"


def test_ensure_utc_datetime_converts_aware_datetime_to_utc():
    value = ensure_utc_datetime(datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc))

    assert value.isoformat() == "2024-01-01T09:00:00+00:00"


def test_parse_iso_to_utc_accepts_z_suffix_and_invalid_values():
    parsed = parse_iso_to_utc("2024-01-01T12:00:00Z")

    assert parsed is not None
    assert parsed.isoformat() == "2024-01-01T12:00:00+00:00"
    assert parse_iso_to_utc("nao-e-data") is None


def test_format_iso_for_display_returns_dash_for_invalid_values():
    assert format_iso_for_display("nao-e-data") == "-"


def test_format_iso_for_display_converts_to_america_sao_paulo():
    display = format_iso_for_display("2024-01-01T12:00:00+00:00")

    assert display == "2024-01-01 09:00"
