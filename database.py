import os
import sqlite3
import datetime
from typing import List, Optional, Dict, Any, Tuple


def get_data_directory() -> str:
    one_drive = os.environ.get("OneDrive")
    if one_drive:
        base_dir = os.path.join(one_drive, "Stunden")
    else:
        # Fallback to a OneDrive-like folder in the user's home directory
        home = os.path.expanduser("~")
        base_dir = os.path.join(home, "OneDrive", "Stunden")
    os.makedirs(base_dir, exist_ok=True)
    return base_dir


def get_db_path() -> str:
    return os.path.join(get_data_directory(), "log.db")


class Database:
    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path or get_db_path()
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self._initialize()

    def _initialize(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
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
        self.conn.commit()

    def insert_entry(self, data: Dict[str, Any]) -> int:
        now = datetime.datetime.now().isoformat(timespec="seconds")
        data = data.copy()
        data["created_at"] = now
        data["updated_at"] = now
        cols = ",".join(data.keys())
        placeholders = ":" + ",:".join(data.keys())
        cur = self.conn.cursor()
        cur.execute(f"INSERT INTO entries ({cols}) VALUES ({placeholders})", data)
        self.conn.commit()
        return cur.lastrowid

    def update_entry(self, entry_id: int, data: Dict[str, Any]) -> None:
        data = data.copy()
        data["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
        assignments = ", ".join(f"{k} = :{k}" for k in data.keys())
        data["id"] = entry_id
        sql = f"UPDATE entries SET {assignments} WHERE id = :id"
        self.conn.execute(sql, data)
        self.conn.commit()

    def delete_entry(self, entry_id: int) -> None:
        self.conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
        self.conn.commit()

    def fetch_entries_by_date(self, date_str: str) -> List[sqlite3.Row]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM entries WHERE date = ? ORDER BY start_time IS NULL, start_time, id",
            (date_str,),
        )
        return cur.fetchall()

    def fetch_recent_site(self) -> Optional[Tuple[str, str]]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT site_name, kst FROM entries ORDER BY datetime(created_at) DESC LIMIT 1"
        )
        row = cur.fetchone()
        if row:
            return row[0], row[1]
        return None

    def fetch_unique_values(self) -> Dict[str, List[str]]:
        cur = self.conn.cursor()
        values: Dict[str, List[str]] = {}
        for column in ("site_name", "kst", "activity"):
            cur.execute(f"SELECT DISTINCT {column} FROM entries ORDER BY {column}")
            values[column] = [r[0] for r in cur.fetchall() if r[0]]
        return values

    def fetch_entry(self, entry_id: int) -> Optional[sqlite3.Row]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM entries WHERE id = ?", (entry_id,))
        return cur.fetchone()

    def fetch_month_summaries(self, year: int, month: int) -> List[sqlite3.Row]:
        month_str = f"{year:04d}-{month:02d}"
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT date, site_name, kst, SUM(day_fraction) AS total_fraction
            FROM entries
            WHERE substr(date, 1, 7) = ?
            GROUP BY date, site_name, kst
            ORDER BY date, site_name
            """,
            (month_str,),
        )
        return cur.fetchall()

    def fetch_month_totals_by_site(self, year: int, month: int) -> List[sqlite3.Row]:
        month_str = f"{year:04d}-{month:02d}"
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT site_name, kst, SUM(day_fraction) AS total_fraction
            FROM entries
            WHERE substr(date, 1, 7) = ?
            GROUP BY site_name, kst
            ORDER BY site_name
            """,
            (month_str,),
        )
        return cur.fetchall()

    def close(self) -> None:
        self.conn.close()
