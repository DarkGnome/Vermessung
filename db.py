import csv
import logging
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

from config import ACTIVITIES, DB_FILENAME, DATA_DIR_NAME, EXPORT_FILENAME, TIME_SHARES, fallback_home_dir

logger = logging.getLogger(__name__)


class StoragePaths:
    """Helper to locate and ensure required storage paths."""

    def __init__(self) -> None:
        self.data_dir = self._resolve_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / DB_FILENAME
        self.log_path = self.data_dir / "activity_log.log"
        self.export_path = self.data_dir / EXPORT_FILENAME

    def _resolve_data_dir(self) -> Path:
        for env_name in ("OneDrive", "OneDriveCommercial", "OneDriveConsumer"):
            one_drive = os.environ.get(env_name)
            if one_drive:
                return Path(one_drive) / DATA_DIR_NAME
        logger.warning("OneDrive environment variable not found. Falling back to home directory.")
        return fallback_home_dir()


PATHS = StoragePaths()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.FileHandler(PATHS.log_path, encoding="utf-8"), logging.StreamHandler()],
)


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    employee TEXT NOT NULL,
                    site TEXT NOT NULL,
                    activity TEXT NOT NULL,
                    result TEXT NOT NULL,
                    time_share REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    is_correction INTEGER DEFAULT 0,
                    corrects_id INTEGER,
                    note TEXT
                );
                """
            )
            conn.commit()

    def add_entry(
        self,
        *,
        entry_date: date,
        employee: str,
        site: str,
        activity: str,
        result_text: str,
        time_share: float,
        is_correction: bool = False,
        corrects_id: Optional[int] = None,
        note: str = "",
    ) -> int:
        timestamp = datetime.now().isoformat(timespec="seconds")
        with sqlite3.connect(self.path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO entries (date, employee, site, activity, result, time_share, timestamp, is_correction, corrects_id, note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry_date.isoformat(),
                    employee,
                    site,
                    activity,
                    result_text,
                    time_share,
                    timestamp,
                    int(is_correction),
                    corrects_id,
                    note,
                ),
            )
            conn.commit()
            new_id = int(cur.lastrowid)
            logger.info("Saved entry %s for %s", new_id, employee)
            return new_id

    def fetch_recent_entries(
        self, limit: int = 200, month: Optional[int] = None, year: Optional[int] = None
    ) -> List[sqlite3.Row]:
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            query = "SELECT * FROM entries"
            params: List[str] = []
            if month and year:
                query += " WHERE strftime('%m', date) = ? AND strftime('%Y', date) = ?"
                params.extend([f"{month:02d}", str(year)])
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            return list(conn.execute(query, params))

    def distinct_sites(self) -> List[str]:
        with sqlite3.connect(self.path) as conn:
            cur = conn.execute("SELECT DISTINCT site FROM entries ORDER BY site ASC")
            return [row[0] for row in cur.fetchall()]

    def export_csv(self, path: Optional[Path] = None) -> Path:
        export_path = path or PATHS.export_path
        rows = self.fetch_recent_entries(limit=10000)
        fieldnames = [
            "id",
            "date",
            "employee",
            "site",
            "activity",
            "result",
            "time_share",
            "timestamp",
            "is_correction",
            "corrects_id",
            "note",
        ]
        with export_path.open("w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({key: row[key] for key in fieldnames})
        logger.info("Exported %s rows to %s", len(rows), export_path)
        return export_path

    def time_share_statistics(self, month: int, year: int) -> List[sqlite3.Row]:
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            query = (
                "SELECT employee, SUM(time_share) as total_time FROM entries "
                "WHERE strftime('%m', date) = ? AND strftime('%Y', date) = ? GROUP BY employee ORDER BY total_time DESC"
            )
            return list(conn.execute(query, (f"{month:02d}", str(year))))


def validate_entry(activity: str, time_share: float) -> None:
    if activity not in ACTIVITIES:
        raise ValueError("Ungültige Tätigkeit.")
    if time_share not in TIME_SHARES:
        raise ValueError("Ungültiger Zeitanteil.")


DB = Database(PATHS.db_path)
