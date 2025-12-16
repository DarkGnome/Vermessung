from __future__ import annotations

import os
import sqlite3
import csv
from contextlib import contextmanager
from datetime import date, datetime, time
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from .models import LogEntry, MonthlySummaryRow


DEFAULT_DB_DIR = os.path.expandvars(r"%OneDrive%/Stunden")
FALLBACK_DB_DIR = Path.home() / "OneDrive" / "Stunden"
DB_FILENAME = "log.db"


def get_db_path() -> Path:
    base = Path(DEFAULT_DB_DIR)
    if "%OneDrive%" in DEFAULT_DB_DIR or not str(base) or str(base).startswith("%OneDrive%"):
        base = FALLBACK_DB_DIR
    return base / DB_FILENAME


def ensure_db_dir() -> Path:
    path = get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def get_connection() -> Iterable[sqlite3.Connection]:
    db_path = ensure_db_dir()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS log_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                employee TEXT NOT NULL,
                site_name TEXT NOT NULL,
                kst TEXT NOT NULL,
                activity TEXT NOT NULL,
                start_time TEXT,
                end_time TEXT,
                day_fraction REAL,
                result TEXT NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )


def _parse_time(value: Optional[str]) -> Optional[time]:
    if value is None:
        return None
    if value == "":
        return None
    return datetime.strptime(value, "%H:%M").time()


def row_to_entry(row: sqlite3.Row) -> LogEntry:
    return LogEntry(
        id=row["id"],
        date=datetime.strptime(row["date"], "%Y-%m-%d").date(),
        employee=row["employee"],
        site_name=row["site_name"],
        kst=row["kst"],
        activity=row["activity"],
        start_time=_parse_time(row["start_time"]),
        end_time=_parse_time(row["end_time"]),
        day_fraction=row["day_fraction"],
        result=row["result"],
        notes=row["notes"] or "",
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def insert_entry(entry: LogEntry) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO log_entries (
                date, employee, site_name, kst, activity, start_time, end_time,
                day_fraction, result, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.date.isoformat(),
                entry.employee,
                entry.site_name,
                entry.kst,
                entry.activity,
                entry.start_time.strftime("%H:%M") if entry.start_time else None,
                entry.end_time.strftime("%H:%M") if entry.end_time else None,
                entry.day_fraction,
                entry.result,
                entry.notes,
                entry.created_at.isoformat(),
                entry.updated_at.isoformat(),
            ),
        )
        return cursor.lastrowid


def update_entry(entry_id: int, entry: LogEntry) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE log_entries
            SET date = ?, employee = ?, site_name = ?, kst = ?, activity = ?,
                start_time = ?, end_time = ?, day_fraction = ?, result = ?,
                notes = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                entry.date.isoformat(),
                entry.employee,
                entry.site_name,
                entry.kst,
                entry.activity,
                entry.start_time.strftime("%H:%M") if entry.start_time else None,
                entry.end_time.strftime("%H:%M") if entry.end_time else None,
                entry.day_fraction,
                entry.result,
                entry.notes,
                entry.updated_at.isoformat(),
                entry_id,
            ),
        )


def delete_entry(entry_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM log_entries WHERE id = ?", (entry_id,))


def fetch_entries_for_date(target_date: date) -> List[LogEntry]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM log_entries WHERE date = ? ORDER BY created_at ASC",
            (target_date.isoformat(),),
        ).fetchall()
        return [row_to_entry(row) for row in rows]


def fetch_last_entry() -> Optional[LogEntry]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM log_entries ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        return row_to_entry(row) if row else None


def duplicate_entry(entry_id: int, new_date: Optional[date] = None) -> Optional[int]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM log_entries WHERE id = ?", (entry_id,)).fetchone()
        if not row:
            return None
        existing = row_to_entry(row)
        now = datetime.now()
        new_entry = LogEntry(
            id=None,
            date=new_date or existing.date,
            employee=existing.employee,
            site_name=existing.site_name,
            kst=existing.kst,
            activity=existing.activity,
            start_time=existing.start_time,
            end_time=existing.end_time,
            day_fraction=existing.day_fraction,
            result=existing.result,
            notes=existing.notes,
            created_at=now,
            updated_at=now,
        )
        return insert_entry(new_entry)


def fetch_distinct_sites_and_ksts() -> Tuple[List[str], List[str]]:
    with get_connection() as conn:
        sites = [row[0] for row in conn.execute("SELECT DISTINCT site_name FROM log_entries WHERE site_name != ''")]
        ksts = [row[0] for row in conn.execute("SELECT DISTINCT kst FROM log_entries WHERE kst != ''")]
        return sites, ksts


def monthly_summary(year: int, month: int) -> List[MonthlySummaryRow]:
    with get_connection() as conn:
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)
        rows = conn.execute(
            """
            SELECT date, site_name, kst, SUM(day_fraction) AS total
            FROM log_entries
            WHERE date >= ? AND date < ?
            GROUP BY date, site_name, kst
            ORDER BY date ASC, site_name ASC
            """,
            (start_date.isoformat(), end_date.isoformat()),
        ).fetchall()
        return [
            MonthlySummaryRow(
                date=datetime.strptime(row["date"], "%Y-%m-%d").date(),
                site_name=row["site_name"],
                kst=row["kst"],
                day_fraction_total=row["total"] or 0.0,
            )
            for row in rows
        ]


def monthly_totals_by_site(year: int, month: int) -> List[Tuple[str, str, float]]:
    with get_connection() as conn:
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)
        rows = conn.execute(
            """
            SELECT site_name, kst, SUM(day_fraction) AS total
            FROM log_entries
            WHERE date >= ? AND date < ?
            GROUP BY site_name, kst
            ORDER BY site_name ASC
            """,
            (start_date.isoformat(), end_date.isoformat()),
        ).fetchall()
        return [(row["site_name"], row["kst"], row["total"] or 0.0) for row in rows]


def export_month_to_csv(year: int, month: int, csv_path: Path) -> None:
    summary_rows = monthly_summary(year, month)
    totals = monthly_totals_by_site(year, month)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Datum", "Baustelle", "KSt", "Tagesanteil"])
        for row in summary_rows:
            writer.writerow([
                row.date.isoformat(),
                row.site_name,
                row.kst,
                f"{row.day_fraction_total:.2f}",
            ])
        writer.writerow([])
        writer.writerow(["Summe pro Baustelle im Monat"])
        writer.writerow(["Baustelle", "KSt", "Summe"])
        for site, kst, total in totals:
            writer.writerow([site, kst, f"{total:.2f}"])


def export_month_to_excel(year: int, month: int, xlsx_path: Path) -> None:
    try:
        import openpyxl
    except ImportError:
        return

    summary_rows = monthly_summary(year, month)
    totals = monthly_totals_by_site(year, month)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Tagesübersicht"
    ws.append(["Datum", "Baustelle", "KSt", "Tagesanteil"])
    for row in summary_rows:
        ws.append([row.date.isoformat(), row.site_name, row.kst, row.day_fraction_total])
    ws2 = wb.create_sheet("Monatssummen")
    ws2.append(["Baustelle", "KSt", "Summe"])
    for site, kst, total in totals:
        ws2.append([site, kst, total])
    xlsx_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(xlsx_path)


