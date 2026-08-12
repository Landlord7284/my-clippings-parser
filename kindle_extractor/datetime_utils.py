from datetime import datetime, timedelta, timezone
from typing import Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

APP_TIMEZONE_NAME = "America/Sao_Paulo"

MONTHS_PT = {
    1: "janeiro",
    2: "fevereiro",
    3: "março",
    4: "abril",
    5: "maio",
    6: "junho",
    7: "julho",
    8: "agosto",
    9: "setembro",
    10: "outubro",
    11: "novembro",
    12: "dezembro",
}


def format_date_pt(value: datetime) -> str:
    """Formata como "14 de julho de 2023" sem depender do locale do processo."""
    return f"{value.day} de {MONTHS_PT[value.month]} de {value.year}"


def today_in_app_timezone() -> datetime:
    return datetime.now(timezone.utc).astimezone(_get_app_timezone())


def _get_app_timezone():
    if ZoneInfo is None:
        return timezone(timedelta(hours=-3))
    return ZoneInfo(APP_TIMEZONE_NAME)


def ensure_utc_datetime(value: Optional[datetime]) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def to_utc_iso(value: Optional[datetime]) -> str:
    return ensure_utc_datetime(value).isoformat()


def parse_iso_to_utc(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None

    text_value = str(value).strip()
    if not text_value:
        return None
    if text_value.endswith("Z"):
        text_value = f"{text_value[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(text_value)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def format_iso_for_display(value: Optional[str], fmt: str = "%Y-%m-%d %H:%M") -> str:
    parsed = parse_iso_to_utc(value)
    if parsed is None:
        return "-"
    return parsed.astimezone(_get_app_timezone()).strftime(fmt)
