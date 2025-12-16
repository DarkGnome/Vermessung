from __future__ import annotations

import sys
from dataclasses import replace
from datetime import date, datetime
from typing import List, Optional
import getpass

from PySide6 import QtCore, QtGui, QtWidgets

from . import storage
from .models import LogEntry
from .utils import calculate_day_fraction


class LogTable(QtWidgets.QTableWidget):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setColumnCount(10)
        self.setHorizontalHeaderLabels([
            "ID",
            "Datum",
            "Mitarbeiter",
            "Baustelle",
            "KSt",
            "Tätigkeit",
            "Start",
            "Ende",
            "Anteil",
            "Ergebnis",
        ])
        self.hideColumn(0)
        self.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

    def set_entries(self, entries: List[LogEntry]) -> None:
        self.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            values = [
                entry.id or "",
                entry.date.isoformat(),
                entry.employee,
                entry.site_name,
                entry.kst,
                entry.activity,
                entry.start_time.strftime("%H:%M") if entry.start_time else "",
                entry.end_time.strftime("%H:%M") if entry.end_time else "",
                f"{entry.day_fraction or 0:.2f}",
                entry.result,
            ]
            for col, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(str(value))
                self.setItem(row, col, item)

    def selected_entry_id(self) -> Optional[int]:
        selected = self.selectedItems()
        if not selected:
            return None
        row = selected[0].row()
        id_item = self.item(row, 0)
        try:
            return int(id_item.text()) if id_item else None
        except ValueError:
            return None


class LogApp(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        storage.init_db()
        self.current_edit_id: Optional[int] = None
        self.entries: List[LogEntry] = []
        self.setWindowTitle("Tätigkeits- & Baustellen-Log")
        self.resize(1100, 750)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)

        layout.addLayout(self._build_header())
        layout.addWidget(self._build_mode_selector())
        layout.addLayout(self._build_inputs())
        layout.addWidget(self._build_buttons())
        layout.addWidget(self._build_table())
        layout.addWidget(self._build_export())

        self.refresh_autocomplete()
        self._update_mode_visibility()
        self.load_entries()

    def _build_header(self) -> QtWidgets.QLayout:
        layout = QtWidgets.QGridLayout()
        self.date_edit = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.dateChanged.connect(self.load_entries)

        self.employee_edit = QtWidgets.QLineEdit(getpass.getuser())
        self.workday_hours_spin = QtWidgets.QDoubleSpinBox()
        self.workday_hours_spin.setRange(1, 24)
        self.workday_hours_spin.setSingleStep(0.5)
        self.workday_hours_spin.setValue(8.0)

        self.round_step_spin = QtWidgets.QDoubleSpinBox()
        self.round_step_spin.setRange(0.01, 1.0)
        self.round_step_spin.setSingleStep(0.05)
        self.round_step_spin.setValue(0.05)

        layout.addWidget(QtWidgets.QLabel("Datum"), 0, 0)
        layout.addWidget(self.date_edit, 0, 1)
        layout.addWidget(QtWidgets.QLabel("Mitarbeiter"), 0, 2)
        layout.addWidget(self.employee_edit, 0, 3)
        layout.addWidget(QtWidgets.QLabel("Arbeitstag (h)"), 0, 4)
        layout.addWidget(self.workday_hours_spin, 0, 5)
        layout.addWidget(QtWidgets.QLabel("Rundung"), 0, 6)
        layout.addWidget(self.round_step_spin, 0, 7)
        return layout

    def _build_mode_selector(self) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox("Modus")
        layout = QtWidgets.QHBoxLayout(box)
        self.mode_start_end = QtWidgets.QRadioButton("Start/Ende")
        self.mode_fraction = QtWidgets.QRadioButton("Tagesanteil")
        self.mode_start_end.setChecked(True)
        layout.addWidget(self.mode_start_end)
        layout.addWidget(self.mode_fraction)
        self.mode_start_end.toggled.connect(self._update_mode_visibility)
        self.mode_fraction.toggled.connect(self._update_mode_visibility)
        return box

    def _build_inputs(self) -> QtWidgets.QLayout:
        form_layout = QtWidgets.QGridLayout()

        self.site_combo = QtWidgets.QComboBox()
        self.site_combo.setEditable(True)
        self.kst_combo = QtWidgets.QComboBox()
        self.kst_combo.setEditable(True)
        self.activity_combo = QtWidgets.QComboBox()
        self.activity_combo.setEditable(True)
        self.activity_combo.addItems(["Aufmaß", "Absteckung", "Scan", "Büro", "Sonstiges"])

        self.result_edit = QtWidgets.QLineEdit()
        self.notes_edit = QtWidgets.QTextEdit()
        self.start_time_edit = QtWidgets.QTimeEdit(QtCore.QTime.currentTime())
        self.end_time_edit = QtWidgets.QTimeEdit(QtCore.QTime.currentTime())
        self.day_fraction_combo = QtWidgets.QComboBox()
        self.day_fraction_combo.setEditable(True)
        self.day_fraction_combo.addItems(["0.1", "0.2", "0.25", "0.3", "0.4", "0.5", "0.6", "0.75", "0.8", "1.0"])

        form_layout.addWidget(QtWidgets.QLabel("Baustelle"), 0, 0)
        form_layout.addWidget(self.site_combo, 0, 1)
        form_layout.addWidget(QtWidgets.QLabel("KSt"), 0, 2)
        form_layout.addWidget(self.kst_combo, 0, 3)
        form_layout.addWidget(QtWidgets.QLabel("Tätigkeit"), 0, 4)
        form_layout.addWidget(self.activity_combo, 0, 5)

        form_layout.addWidget(QtWidgets.QLabel("Ergebnis"), 1, 0)
        form_layout.addWidget(self.result_edit, 1, 1, 1, 5)

        form_layout.addWidget(QtWidgets.QLabel("Notizen"), 2, 0)
        form_layout.addWidget(self.notes_edit, 2, 1, 1, 5)

        form_layout.addWidget(QtWidgets.QLabel("Start"), 3, 0)
        form_layout.addWidget(self.start_time_edit, 3, 1)
        form_layout.addWidget(QtWidgets.QLabel("Ende"), 3, 2)
        form_layout.addWidget(self.end_time_edit, 3, 3)

        form_layout.addWidget(QtWidgets.QLabel("Tagesanteil"), 4, 0)
        form_layout.addWidget(self.day_fraction_combo, 4, 1)

        return form_layout

    def _build_buttons(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(widget)
        self.save_button = QtWidgets.QPushButton("Speichern")
        self.save_button.clicked.connect(self.save_entry)
        self.last_site_button = QtWidgets.QPushButton("Letzte Baustelle übernehmen")
        self.last_site_button.clicked.connect(self.fill_last_site)
        self.duplicate_button = QtWidgets.QPushButton("Duplizieren (Auswahl)")
        self.duplicate_button.clicked.connect(self.duplicate_selected)
        self.delete_button = QtWidgets.QPushButton("Löschen (Auswahl)")
        self.delete_button.clicked.connect(self.delete_selected)
        self.edit_button = QtWidgets.QPushButton("Bearbeiten (Auswahl)")
        self.edit_button.clicked.connect(self.edit_selected)

        layout.addWidget(self.save_button)
        layout.addWidget(self.last_site_button)
        layout.addWidget(self.duplicate_button)
        layout.addWidget(self.edit_button)
        layout.addWidget(self.delete_button)
        layout.addStretch()
        return widget

    def _build_table(self) -> QtWidgets.QWidget:
        self.table = LogTable()
        container = QtWidgets.QGroupBox("Einträge des Tages")
        vbox = QtWidgets.QVBoxLayout(container)
        vbox.addWidget(self.table)
        return container

    def _build_export(self) -> QtWidgets.QWidget:
        box = QtWidgets.QGroupBox("Auswertung / Export")
        layout = QtWidgets.QHBoxLayout(box)
        self.month_edit = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.month_edit.setDisplayFormat("yyyy-MM")
        self.month_edit.setCalendarPopup(True)
        self.export_csv_button = QtWidgets.QPushButton("Export CSV")
        self.export_excel_button = QtWidgets.QPushButton("Export Excel")
        self.export_csv_button.clicked.connect(self.export_csv)
        self.export_excel_button.clicked.connect(self.export_excel)
        layout.addWidget(QtWidgets.QLabel("Monat"))
        layout.addWidget(self.month_edit)
        layout.addWidget(self.export_csv_button)
        layout.addWidget(self.export_excel_button)
        layout.addStretch()
        return box

    # UI helpers
    def _update_mode_visibility(self) -> None:
        is_start_end = self.mode_start_end.isChecked()
        self.start_time_edit.setEnabled(is_start_end)
        self.end_time_edit.setEnabled(is_start_end)
        self.day_fraction_combo.setEnabled(not is_start_end)

    def refresh_autocomplete(self) -> None:
        sites, ksts = storage.fetch_distinct_sites_and_ksts()
        self._refresh_combo(self.site_combo, sites)
        self._refresh_combo(self.kst_combo, ksts)

    def _refresh_combo(self, combo: QtWidgets.QComboBox, values: List[str]) -> None:
        existing_text = combo.currentText()
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(values)
        combo.setEditText(existing_text)
        completer = QtWidgets.QCompleter(values)
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        combo.setCompleter(completer)
        combo.blockSignals(False)

    def _current_date(self) -> date:
        return self.date_edit.date().toPython()

    def load_entries(self) -> None:
        self.entries = storage.fetch_entries_for_date(self._current_date())
        self.table.set_entries(self.entries)
        self.current_edit_id = None

    def fill_last_site(self) -> None:
        last_entry = storage.fetch_last_entry()
        if not last_entry:
            QtWidgets.QMessageBox.information(self, "Hinweis", "Keine vorherigen Einträge gefunden.")
            return
        self.site_combo.setEditText(last_entry.site_name)
        self.kst_combo.setEditText(last_entry.kst)

    def _build_entry_from_form(self) -> LogEntry:
        today_date = self._current_date()
        employee = self.employee_edit.text().strip() or getpass.getuser()
        site = self.site_combo.currentText().strip()
        kst = self.kst_combo.currentText().strip()
        activity = self.activity_combo.currentText().strip()
        result = self.result_edit.text().strip()
        notes = self.notes_edit.toPlainText().strip()
        workday_hours = self.workday_hours_spin.value()
        round_step = self.round_step_spin.value()

        if not site or not kst or not activity or not result:
            raise ValueError("Bitte alle Pflichtfelder ausfüllen (Baustelle, KSt, Tätigkeit, Ergebnis).")

        if self.mode_start_end.isChecked():
            start_time = self.start_time_edit.time().toPython()
            end_time = self.end_time_edit.time().toPython()
            fraction = calculate_day_fraction(start_time, end_time, workday_hours, round_step)
            day_fraction = fraction
            if day_fraction > 1.0:
                raise ValueError("Tagesanteil darf nicht größer als 1.0 sein.")
        else:
            start_time = None
            end_time = None
            try:
                day_fraction = float(self.day_fraction_combo.currentText().replace(",", "."))
            except ValueError as exc:
                raise ValueError("Ungültiger Tagesanteil.") from exc
            if day_fraction <= 0:
                raise ValueError("Tagesanteil muss größer als 0 sein.")
            if day_fraction > 1.0:
                raise ValueError("Tagesanteil darf nicht größer als 1.0 sein.")

        if day_fraction > 1.0:
            raise ValueError("Tagesanteil darf nicht größer als 1.0 sein.")

        now = datetime.now()
        return LogEntry(
            id=None,
            date=today_date,
            employee=employee,
            site_name=site,
            kst=kst,
            activity=activity,
            start_time=start_time,
            end_time=end_time,
            day_fraction=day_fraction,
            result=result,
            notes=notes,
            created_at=now,
            updated_at=now,
        )

    def save_entry(self) -> None:
        try:
            entry = self._build_entry_from_form()
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Fehler", str(exc))
            return

        if self.current_edit_id:
            entry = replace(entry, created_at=self._existing_created_at(self.current_edit_id))
            storage.update_entry(self.current_edit_id, entry)
            self.current_edit_id = None
        else:
            storage.insert_entry(entry)

        self.clear_form()
        self.refresh_autocomplete()
        self.load_entries()

    def _existing_created_at(self, entry_id: int) -> datetime:
        for entry in self.entries:
            if entry.id == entry_id:
                return entry.created_at
        return datetime.now()

    def clear_form(self) -> None:
        self.result_edit.clear()
        self.notes_edit.clear()
        self.start_time_edit.setTime(QtCore.QTime.currentTime())
        self.end_time_edit.setTime(QtCore.QTime.currentTime())
        self.day_fraction_combo.setEditText("0.5")
        self.current_edit_id = None
        self.mode_start_end.setChecked(True)
        self._update_mode_visibility()

    def edit_selected(self) -> None:
        entry_id = self.table.selected_entry_id()
        if not entry_id:
            return
        entry = next((e for e in self.entries if e.id == entry_id), None)
        if not entry:
            return
        self.current_edit_id = entry_id
        self.date_edit.setDate(QtCore.QDate(entry.date))
        self.employee_edit.setText(entry.employee)
        self.site_combo.setEditText(entry.site_name)
        self.kst_combo.setEditText(entry.kst)
        self.activity_combo.setEditText(entry.activity)
        self.result_edit.setText(entry.result)
        self.notes_edit.setPlainText(entry.notes)
        if entry.start_time and entry.end_time:
            self.mode_start_end.setChecked(True)
            self.start_time_edit.setTime(QtCore.QTime(entry.start_time))
            self.end_time_edit.setTime(QtCore.QTime(entry.end_time))
        else:
            self.mode_fraction.setChecked(True)
            self.day_fraction_combo.setEditText(str(entry.day_fraction or ""))
        self._update_mode_visibility()

    def delete_selected(self) -> None:
        entry_id = self.table.selected_entry_id()
        if not entry_id:
            return
        confirm = QtWidgets.QMessageBox.question(self, "Löschen", "Eintrag wirklich löschen?")
        if confirm == QtWidgets.QMessageBox.Yes:
            storage.delete_entry(entry_id)
            self.load_entries()

    def duplicate_selected(self) -> None:
        entry_id = self.table.selected_entry_id()
        if not entry_id:
            return
        storage.duplicate_entry(entry_id, new_date=self._current_date())
        self.load_entries()

    def export_csv(self) -> None:
        qdate = self.month_edit.date()
        year, month = qdate.year(), qdate.month()
        export_path = storage.get_db_path().parent / f"report_{year}_{month:02d}.csv"
        storage.export_month_to_csv(year, month, export_path)
        QtWidgets.QMessageBox.information(self, "Export", f"CSV gespeichert unter\n{export_path}")

    def export_excel(self) -> None:
        qdate = self.month_edit.date()
        year, month = qdate.year(), qdate.month()
        export_path = storage.get_db_path().parent / f"monatsbericht_{year}_{month:02d}.xlsx"
        storage.export_month_to_excel(year, month, export_path)
        QtWidgets.QMessageBox.information(self, "Export", f"Excel gespeichert unter\n{export_path}\n(Hinweis: benötigt openpyxl)")


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    window = LogApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

