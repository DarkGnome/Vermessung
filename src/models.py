from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Optional


@dataclass
class LogEntry:
    id: Optional[int]
    date: date
    employee: str
    site_name: str
    kst: str
    activity: str
    start_time: Optional[time]
    end_time: Optional[time]
    day_fraction: Optional[float]
    result: str
    notes: str
    created_at: datetime
    updated_at: datetime


@dataclass
class MonthlySummaryRow:
    date: date
    site_name: str
    kst: str
    day_fraction_total: float

