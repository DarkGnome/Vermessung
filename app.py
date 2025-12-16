import os
import sys
from datetime import datetime, time
from pathlib import Path
from typing import Dict, Optional

from PySide6.QtCore import QDate, QTime, Qt
from PySide6.QtGui import QCompleter
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)

from database import DEFAULT_ROUNDING_STEP, LogDatabase, round_to_step


def default_employee() -> str:
    try:
        return os.environ.get("USERNAME") or os.environ.get("USER") or os.getlogin()
    except OSError:
        return ""


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Vermessung Tätigkeits-Log")
        self.db = LogDatabase()
        self.current_edit_id: Optional[int] = None

        self._init_ui()
        self._load_autocomplete_values()
        self.load_entries_for_date()

    def _init_ui(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)

        layout.addWidget(self._build_header())
        layout.addWidget(self._build_form())
        layout.addWidget(self._build_table())
        layout.addWidget(self._build_export_area())

        self.setCentralWidget(container)

    def _build_header(self) -> QWidget:
        box = QGroupBox("Allgemein")
        form = QFormLayout(box)

        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.dateChanged.connect(self.load_entries_for_date)

        self.employee_edit = QLineEdit(default_employee())

        self.workday_hours = QDoubleSpinBox()
        self.workday_hours.setRange(1.0, 24.0)
        self.workday_hours.setValue(8.0)
        self.workday_hours.setSingleStep(0.25)

        form.addRow("Datum", self.date_edit)
        form.addRow("Mitarbeiter", self.employee_edit)
        form.addRow("Arbeitszeit (h)", self.workday_hours)
        return box

    def _build_form(self) -> QWidget:
        box = QGroupBox("Erfassung")
        layout = QVBoxLayout(box)

        form = QFormLayout()
        self.site_combo = QComboBox()
        self.site_combo.setEditable(True)

        self.kst_combo = QComboBox()
        self.kst_combo.setEditable(True)

        self.activity_combo = QComboBox()
        self.activity_combo.setEditable(True)
        self.activity_combo.addItems([
            "Aufmaß",
            "Absteckung",
            "Scan",
            "Büro",
            "Sonstiges",
        ])

        self.result_edit = QLineEdit()
        self.notes_edit = QTextEdit()
        self.notes_edit.setFixedHeight(60)

        form.addRow("Baustelle", self.site_combo)
        form.addRow("Kostenstelle", self.kst_combo)
        form.addRow("Tätigkeit", self.activity_combo)
        form.addRow("Ergebnis", self.result_edit)
        form.addRow("Notizen", self.notes_edit)

        layout.addLayout(form)

        # Mode selection
        mode_layout = QHBoxLayout()
        self.start_end_radio = QRadioButton("Start/Ende")
        self.day_fraction_radio = QRadioButton("Tagesanteil")
        self.start_end_radio.setChecked(True)
        self.start_end_radio.toggled.connect(self._toggle_mode)

        mode_layout.addWidget(self.start_end_radio)
        mode_layout.addWidget(self.day_fraction_radio)
        layout.addLayout(mode_layout)

        time_layout = QFormLayout()
        self.start_time_edit = QTimeEdit(QTime.fromString("08:00", "HH:mm"))
        self.start_time_edit.setDisplayFormat("HH:mm")
        self.end_time_edit = QTimeEdit(QTime.fromString("12:00", "HH:mm"))
        self.end_time_edit.setDisplayFormat("HH:mm")

        self.day_fraction_combo = QComboBox()
        self.day_fraction_combo.setEditable(True)
        for value in [0.1, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.75, 0.8, 1.0]:
            self.day_fraction_combo.addItem(f"{value:.2f}")

        time_layout.addRow("Start", self.start_time_edit)
        time_layout.addRow("Ende", self.end_time_edit)
        time_layout.addRow("Tagesanteil", self.day_fraction_combo)

        layout.addLayout(time_layout)

        button_layout = QHBoxLayout()
        save_btn = QPushButton("Speichern")
        save_btn.clicked.connect(self.save_entry)

        last_btn = QPushButton("Letzte Baustelle übernehmen")
        last_btn.clicked.connect(self.fill_last_site)

        duplicate_btn = QPushButton("Duplizieren")
        duplicate_btn.clicked.connect(self.duplicate_entry)

        delete_btn = QPushButton("Löschen")
        delete_btn.clicked.connect(self.delete_selected)

        button_layout.addWidget(save_btn)
        button_layout.addWidget(last_btn)
        button_layout.addWidget(duplicate_btn)
        button_layout.addWidget(delete_btn)

        layout.addLayout(button_layout)

        self._toggle_mode()
        return box

    def _build_table(self) -> QWidget:
        box = QGroupBox("Tagesübersicht")
        vbox = QVBoxLayout(box)

        self.table = QTableWidget()
        headers = [
            "Datum",
            "Mitarbeiter",
            "Baustelle",
            "KST",
            "Tätigkeit",
            "Start",
            "Ende",
            "Tagesanteil",
            "Stunden",
            "Ergebnis",
            "Notizen",
        ]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setSelectionBehavior(self.table.SelectRows)
        self.table.itemSelectionChanged.connect(self._load_selected_for_edit)

        vbox.addWidget(self.table)
        return box

    def _build_export_area(self) -> QWidget:
        box = QGroupBox("Auswertung")
        layout = QHBoxLayout(box)

        self.month_edit = QDateEdit(QDate.currentDate())
        self.month_edit.setDisplayFormat("yyyy-MM")
        self.month_edit.setCalendarPopup(True)

        export_btn = QPushButton("CSV Export")
        export_btn.clicked.connect(self.export_month)

        layout.addWidget(QLabel("Monat"))
        layout.addWidget(self.month_edit)
        layout.addWidget(export_btn)
        layout.addStretch()
        return box

    def _toggle_mode(self) -> None:
        use_times = self.start_end_radio.isChecked()
        self.start_time_edit.setEnabled(use_times)
        self.end_time_edit.setEnabled(use_times)
        self.day_fraction_combo.setEnabled(not use_times)

    def _load_autocomplete_values(self) -> None:
        for combo, column in [
            (self.site_combo, "site_name"),
            (self.kst_combo, "kst"),
            (self.activity_combo, "activity"),
        ]:
            values = self.db.get_distinct_values(column)
            combo.addItems([v for v in values if combo.findText(v) == -1])
            completer = QCompleter(values)
            completer.setCaseSensitivity(Qt.CaseInsensitive)
            combo.setCompleter(completer)

    def _parse_day_fraction(self) -> Optional[float]:
        text = self.day_fraction_combo.currentText().replace(",", ".").strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    def save_entry(self) -> None:
        date_str = self.date_edit.date().toString("yyyy-MM-dd")
        employee = self.employee_edit.text().strip()
        site = self.site_combo.currentText().strip()
        kst = self.kst_combo.currentText().strip()
        activity = self.activity_combo.currentText().strip()
        result = self.result_edit.text().strip()
        notes = self.notes_edit.toPlainText().strip() or None
        workday_hours = self.workday_hours.value()

        if not all([employee, site, kst, activity, result]):
            QMessageBox.warning(self, "Pflichtfelder", "Bitte alle Pflichtfelder ausfüllen.")
            return

        start_time: Optional[time] = None
        end_time: Optional[time] = None
        day_fraction: Optional[float] = None
        duration_hours: Optional[float] = None

        if self.start_end_radio.isChecked():
            start_time = self.start_time_edit.time().toPython()
            end_time = self.end_time_edit.time().toPython()
            if end_time <= start_time:
                QMessageBox.warning(self, "Zeitfehler", "Endzeit muss nach Startzeit liegen.")
                return
            delta = datetime.combine(datetime.today(), end_time) - datetime.combine(datetime.today(), start_time)
            duration_hours = round(delta.total_seconds() / 3600, 2)
            day_fraction = round_to_step(duration_hours / workday_hours, DEFAULT_ROUNDING_STEP)
        else:
            day_fraction = self._parse_day_fraction()
            if day_fraction is None:
                QMessageBox.warning(self, "Eingabe", "Bitte gültigen Tagesanteil eingeben.")
                return
            if day_fraction > 1.0:
                QMessageBox.warning(self, "Eingabe", "Tagesanteil darf 1.0 nicht überschreiten.")
                return

        if day_fraction is None:
            QMessageBox.warning(self, "Eingabe", "Entweder Start/Ende oder Tagesanteil angeben.")
            return

        data: Dict[str, Optional[str]] = {
            "date": date_str,
            "employee": employee,
            "site_name": site,
            "kst": kst,
            "activity": activity,
            "start_time": start_time.strftime("%H:%M") if start_time else None,
            "end_time": end_time.strftime("%H:%M") if end_time else None,
            "day_fraction": day_fraction,
            "duration_hours": duration_hours,
            "result": result,
            "notes": notes,
        }

        if self.current_edit_id:
            self.db.update_entry(self.current_edit_id, data)  # type: ignore[arg-type]
            self.current_edit_id = None
        else:
            self.db.add_entry(data)  # type: ignore[arg-type]

        self._load_autocomplete_values()
        self.clear_form()
        self.load_entries_for_date()

    def clear_form(self) -> None:
        self.result_edit.clear()
        self.notes_edit.clear()
        self.current_edit_id = None

    def load_entries_for_date(self) -> None:
        date_str = self.date_edit.date().toString("yyyy-MM-dd")
        entries = self.db.get_entries_for_date(date_str)
        self.table.setRowCount(len(entries))
        for row_idx, entry in enumerate(entries):
            values = [
                entry["date"],
                entry["employee"],
                entry["site_name"],
                entry["kst"],
                entry["activity"],
                entry.get("start_time") or "",
                entry.get("end_time") or "",
                f"{entry.get('day_fraction') or 0:.2f}",
                f"{entry.get('duration_hours') or 0:.2f}",
                entry["result"],
                entry.get("notes") or "",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, entry["id"])
                self.table.setItem(row_idx, col, item)
        self.table.resizeColumnsToContents()

    def _load_selected_for_edit(self) -> None:
        items = self.table.selectedItems()
        if not items:
            self.current_edit_id = None
            return
        entry_id = items[0].data(Qt.UserRole)
        date_str = items[0].text()
        entries = self.db.get_entries_for_date(date_str)
        entry = next((e for e in entries if e["id"] == entry_id), None)
        if not entry:
            return

        self.current_edit_id = entry_id
        self.date_edit.setDate(QDate.fromString(entry["date"], "yyyy-MM-dd"))
        self.employee_edit.setText(entry["employee"])
        self.site_combo.setCurrentText(entry["site_name"])
        self.kst_combo.setCurrentText(entry["kst"])
        self.activity_combo.setCurrentText(entry["activity"])
        self.result_edit.setText(entry["result"])
        self.notes_edit.setText(entry.get("notes") or "")

        if entry.get("start_time") and entry.get("end_time"):
            self.start_end_radio.setChecked(True)
            self.start_time_edit.setTime(QTime.fromString(entry["start_time"], "HH:mm"))
            self.end_time_edit.setTime(QTime.fromString(entry["end_time"], "HH:mm"))
        else:
            self.day_fraction_radio.setChecked(True)
            self.day_fraction_combo.setCurrentText(f"{entry.get('day_fraction') or 0:.2f}")
        self._toggle_mode()

    def delete_selected(self) -> None:
        items = self.table.selectedItems()
        if not items:
            return
        entry_id = items[0].data(Qt.UserRole)
        self.db.delete_entry(entry_id)
        self.load_entries_for_date()

    def duplicate_entry(self) -> None:
        items = self.table.selectedItems()
        if not items:
            return
        entry_id = items[0].data(Qt.UserRole)
        date_str = items[0].text()
        entries = self.db.get_entries_for_date(date_str)
        entry = next((e for e in entries if e["id"] == entry_id), None)
        if not entry:
            return
        self.current_edit_id = None
        self.date_edit.setDate(QDate.fromString(entry["date"], "yyyy-MM-dd"))
        self.employee_edit.setText(entry["employee"])
        self.site_combo.setCurrentText(entry["site_name"])
        self.kst_combo.setCurrentText(entry["kst"])
        self.activity_combo.setCurrentText(entry["activity"])
        self.result_edit.setText(entry["result"])
        self.notes_edit.setText(entry.get("notes") or "")
        if entry.get("start_time") and entry.get("end_time"):
            self.start_end_radio.setChecked(True)
            self.start_time_edit.setTime(QTime.fromString(entry["start_time"], "HH:mm"))
            self.end_time_edit.setTime(QTime.fromString(entry["end_time"], "HH:mm"))
        else:
            self.day_fraction_radio.setChecked(True)
            self.day_fraction_combo.setCurrentText(f"{entry.get('day_fraction') or 0:.2f}")
        self._toggle_mode()

    def fill_last_site(self) -> None:
        last = self.db.get_last_entry()
        if not last:
            return
        self.site_combo.setCurrentText(last["site_name"])
        self.kst_combo.setCurrentText(last["kst"])

    def export_month(self) -> None:
        month_date = self.month_edit.date()
        year = month_date.year()
        month = month_date.month()
        folder = QFileDialog.getExistingDirectory(self, "Zielordner auswählen")
        if not folder:
            return
        summary = self.db.get_monthly_summary(year, month)
        totals = self.db.get_monthly_totals_by_site(year, month)
        filename = Path(folder) / f"monatsbericht_{year:04d}_{month:02d}.csv"
        with open(filename, "w", encoding="utf-8") as f:
            f.write("Datum;KST;Tagesanteil\n")
            for date_str, kst, total_fraction in summary:
                f.write(f"{date_str};{kst};{total_fraction:.2f}\n")
            f.write("\nKST;Summe im Monat\n")
            for kst, total_fraction in totals:
                f.write(f"{kst};{total_fraction:.2f}\n")
        QMessageBox.information(self, "Export", f"CSV gespeichert unter {filename}")


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(1000, 800)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

