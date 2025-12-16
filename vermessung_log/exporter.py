import csv
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Iterable

try:
    import pandas as pd  # type: ignore
except ImportError:  # pragma: no cover
    pd = None


class MonthExporter:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_csv(self, month_label: str, entries: Iterable[dict]) -> Path:
        csv_path = self.output_dir / f"monatsbericht_{month_label}.csv"
        daily_totals = defaultdict(float)
        monthly_totals = defaultdict(float)

        normalized_entries = []
        for entry in entries:
            day_fraction = float(entry.get("day_fraction") or 0)
            key_day = (entry["date"], entry["site_name"], entry["kst"])
            key_month = (entry["site_name"], entry["kst"])
            daily_totals[key_day] += day_fraction
            monthly_totals[key_month] += day_fraction
            normalized_entries.append(entry)

        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Datum", "Baustelle", "Kst", "Mitarbeiter", "Tätigkeit", "Tagesanteil", "Ergebnis"])
            for entry in normalized_entries:
                writer.writerow(
                    [
                        entry["date"],
                        entry["site_name"],
                        entry["kst"],
                        entry["employee"],
                        entry["activity"],
                        entry.get("day_fraction", ""),
                        entry.get("result", ""),
                    ]
                )

            writer.writerow([])
            writer.writerow(["Summe pro Baustelle und Tag", "", "", "", "", ""])
            writer.writerow(["Datum", "Baustelle", "Kst", "Summe Tagesanteile"])
            for (entry_date, site, kst), total in sorted(daily_totals.items()):
                writer.writerow([entry_date, site, kst, f"{total:.2f}"])

            writer.writerow([])
            writer.writerow(["Monatssummen pro Baustelle", "", "", "", "", ""])
            writer.writerow(["Baustelle", "Kst", "Summe Tagesanteile"])
            for (site, kst), total in sorted(monthly_totals.items()):
                writer.writerow([site, kst, f"{total:.2f}"])

        return csv_path

    def export_excel(self, month_label: str, entries: Iterable[dict]) -> Path:
        if pd is None:
            raise RuntimeError("Pandas ist nicht installiert, daher kein Excel-Export möglich.")

        excel_path = self.output_dir / f"monatsbericht_{month_label}.xlsx"
        data_rows = []
        for entry in entries:
            row = dict(entry)
            row["day_fraction"] = float(entry.get("day_fraction") or 0)
            data_rows.append(row)

        df = pd.DataFrame(data_rows)
        if df.empty:
            df = pd.DataFrame(
                [
                    {
                        "date": date.today().strftime("%Y-%m-%d"),
                        "site_name": "",
                        "kst": "",
                        "day_fraction": 0,
                    }
                ]
            )

        pivot_site_day = pd.pivot_table(
            df,
            values="day_fraction",
            index=["date", "site_name", "kst"],
            aggfunc="sum",
        )

        pivot_site_total = pd.pivot_table(
            df,
            values="day_fraction",
            index=["site_name", "kst"],
            aggfunc="sum",
        )

        with pd.ExcelWriter(excel_path) as writer:
            df.to_excel(writer, sheet_name="Einzelbuchungen", index=False)
            pivot_site_day.to_excel(writer, sheet_name="Tagessummen")
            pivot_site_total.to_excel(writer, sheet_name="Monatssummen")

        return excel_path
