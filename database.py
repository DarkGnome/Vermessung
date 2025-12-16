import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

DEFAULT_ROUNDING_STEP = 0.05


def get_storage_path() -> Path:
    onedrive = os.environ.get("OneDrive") or os.environ.get("OneDriveCommercial") or os.environ.get("OneDriveConsumer")
    base = Path(onedrive) if onedrive else Path.home() / "OneDrive"
    storage_dir = base / "Stunden"
    storage_dir.mkdir(parents=True, exist_ok=True)
    return storage_dir / "log.db"


class LogDatabase:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or get_storage_path()
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    employee TEXT NOT NULL,
                    site_name TEXT NOT NULL,
                    kst TEXT NOT NULL,
                    activity TEXT NOT NULL,
                    start_time TEXT,
                    end_time TEXT,
                    day_fraction REAL,
                    duration_hours REAL,
                    result TEXT NOT NULL,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def add_entry(self, entry: Dict[str, Any]) -> int:
        now = datetime.utcnow().isoformat()
        entry["created_at"] = now
        entry["updated_at"] = now
        columns = ", ".join(entry.keys())
        placeholders = ", ".join([":" + key for key in entry.keys()])
        with self._connect() as conn:
            cur = conn.execute(f"INSERT INTO entries ({columns}) VALUES ({placeholders})", entry)
            return cur.lastrowid

    def update_entry(self, entry_id: int, entry: Dict[str, Any]) -> None:
        entry["updated_at"] = datetime.utcnow().isoformat()
        assignments = ", ".join([f"{k} = :{k}" for k in entry.keys()])
        entry["id"] = entry_id
        with self._connect() as conn:
            conn.execute(f"UPDATE entries SET {assignments} WHERE id = :id", entry)

    def delete_entry(self, entry_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))

    def get_entries_for_date(self, date_str: str) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT id, date, employee, site_name, kst, activity, start_time, end_time,
                       day_fraction, duration_hours, result, notes, created_at, updated_at
                FROM entries
                WHERE date = ?
                ORDER BY start_time IS NULL, start_time
                """,
                (date_str,),
            )
            return [self._row_to_dict(row) for row in cur.fetchall()]

    def get_last_entry(self) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT id, date, employee, site_name, kst, activity, start_time, end_time, day_fraction, duration_hours, result, notes, created_at, updated_at FROM entries ORDER BY id DESC LIMIT 1"
            )
            row = cur.fetchone()
            return self._row_to_dict(row) if row else None

    def get_distinct_values(self, column: str) -> List[str]:
        if column not in {"site_name", "kst", "activity"}:
            raise ValueError("Unsupported column for distinct values")
        with self._connect() as conn:
            cur = conn.execute(f"SELECT DISTINCT {column} FROM entries WHERE {column} IS NOT NULL AND {column} != '' ORDER BY {column}")
            return [row[0] for row in cur.fetchall()]

    def get_monthly_summary(self, year: int, month: int) -> List[Tuple[str, str, float]]:
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT date, kst, SUM(day_fraction) as total_fraction
                FROM entries
                WHERE substr(date, 1, 7) = ?
                GROUP BY date, kst
                ORDER BY date, kst
                """,
                (f"{year:04d}-{month:02d}",),
            )
            return cur.fetchall()

    def get_monthly_totals_by_site(self, year: int, month: int) -> List[Tuple[str, float]]:
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT kst, SUM(day_fraction) as total_fraction
                FROM entries
                WHERE substr(date, 1, 7) = ?
                GROUP BY kst
                ORDER BY kst
                """,
                (f"{year:04d}-{month:02d}",),
            )
            return cur.fetchall()

    @staticmethod
    def _row_to_dict(row: Iterable[Any]) -> Dict[str, Any]:
        keys = [
            "id",
            "date",
            "employee",
            "site_name",
            "kst",
            "activity",
            "start_time",
            "end_time",
            "day_fraction",
            "duration_hours",
            "result",
            "notes",
            "created_at",
            "updated_at",
        ]
        return {k: v for k, v in zip(keys, row)}


def round_to_step(value: float, step: float = DEFAULT_ROUNDING_STEP) -> float:
    if step <= 0:
        return value
    rounded = round(value / step) * step
    return round(rounded + 1e-9, 2)

