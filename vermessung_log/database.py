import os
import sqlite3
from pathlib import Path
from typing import Dict, Iterable, List, Optional


class DatabaseManager:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self.connection.execute(
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
        self.connection.commit()

    def insert_entry(self, entry: Dict) -> int:
        cursor = self.connection.cursor()
        cursor.execute(
            """
            INSERT INTO entries (
                date, employee, site_name, kst, activity,
                start_time, end_time, day_fraction, duration_hours,
                result, notes, created_at, updated_at
            ) VALUES (
                :date, :employee, :site_name, :kst, :activity,
                :start_time, :end_time, :day_fraction, :duration_hours,
                :result, :notes, :created_at, :updated_at
            )
            """,
            entry,
        )
        self.connection.commit()
        return cursor.lastrowid

    def update_entry(self, entry_id: int, entry: Dict) -> None:
        self.connection.execute(
            """
            UPDATE entries
            SET date = :date,
                employee = :employee,
                site_name = :site_name,
                kst = :kst,
                activity = :activity,
                start_time = :start_time,
                end_time = :end_time,
                day_fraction = :day_fraction,
                duration_hours = :duration_hours,
                result = :result,
                notes = :notes,
                updated_at = :updated_at
            WHERE id = :id
            """,
            {"id": entry_id, **entry},
        )
        self.connection.commit()

    def delete_entry(self, entry_id: int) -> None:
        self.connection.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
        self.connection.commit()

    def get_entry(self, entry_id: int) -> Optional[sqlite3.Row]:
        cursor = self.connection.execute("SELECT * FROM entries WHERE id = ?", (entry_id,))
        return cursor.fetchone()

    def entries_for_date(self, date_str: str):
        cursor = self.connection.execute(
            "SELECT * FROM entries WHERE date = ? ORDER BY start_time IS NULL, start_time, created_at",
            (date_str,),
        )
        return cursor.fetchall()

    def latest_entry(self) -> Optional[sqlite3.Row]:
        cursor = self.connection.execute(
            "SELECT * FROM entries ORDER BY datetime(created_at) DESC LIMIT 1"
        )
        return cursor.fetchone()

    def distinct_values(self, field: str) -> List[str]:
        if field not in {"site_name", "kst", "activity", "employee"}:
            return []
        cursor = self.connection.execute(
            f"SELECT DISTINCT {field} FROM entries WHERE {field} IS NOT NULL AND {field} != ''"
        )
        return [row[0] for row in cursor.fetchall()]

    def entries_for_month(self, year: int, month: int) -> Iterable[sqlite3.Row]:
        start_date = f"{year:04d}-{month:02d}-01"
        if month == 12:
            end_date = f"{year + 1:04d}-01-01"
        else:
            end_date = f"{year:04d}-{month + 1:02d}-01"
        cursor = self.connection.execute(
            "SELECT * FROM entries WHERE date >= ? AND date < ? ORDER BY date, site_name, kst",
            (start_date, end_date),
        )
        return cursor.fetchall()

    def close(self) -> None:
        self.connection.close()


def default_db_path() -> Path:
    onedrive_env = os.environ.get("OneDrive")
    if onedrive_env:
        root = Path(onedrive_env)
    else:
        root = Path.home() / "OneDrive"
    return root / "Stunden" / "log.db"
