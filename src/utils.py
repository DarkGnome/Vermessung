from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Optional


def calculate_day_fraction(
    start: time, end: time, workday_hours: float, step: float
) -> float:
    if end <= start:
        raise ValueError("Endzeit muss nach Startzeit liegen.")
    start_dt = datetime.combine(datetime.today(), start)
    end_dt = datetime.combine(datetime.today(), end)
    duration_hours = (end_dt - start_dt).total_seconds() / 3600.0
    if workday_hours <= 0:
        raise ValueError("Arbeitszeit pro Tag muss größer als 0 sein.")
    raw_fraction = duration_hours / workday_hours
    rounded = round(raw_fraction / step) * step
    return round(rounded, 2)


def parse_time_string(value: str) -> Optional[time]:
    value = value.strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError as exc:
        raise ValueError("Zeitformat sollte HH:MM sein.") from exc


def timedelta_from_hours(hours: float) -> timedelta:
    return timedelta(hours=hours)

