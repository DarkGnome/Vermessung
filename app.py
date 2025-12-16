import csv
import sys
import math
import datetime
import getpass
from typing import Optional, Dict, Any, List

from PySide6 import QtWidgets, QtCore, QtGui

from database import Database, get_db_path


ROUNDING_STEP_DEFAULT = 0.05
WORKDAY_HOURS_DEFAULT = 8.0
FRACTION_CHOICES = [0.1, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.75, 0.8, 1.0]


class EntryTableModel(QtCore.QAbstractTableModel):
    HEADERS = [
        "Datum",
        "Mitarbeiter",
        "Baustelle",
        "Kst",
        "Tätigkeit",
        "Start",
        "Ende",
        "Anteil",
        "Dauer (h)",
        "Ergebnis",
        "Notizen",
    ]

    def __init__(self, entries: List[Dict[str, Any]]):
        super().__init__()
        self.entries = entries

    def update_entries(self, entries: List[Dict[str, Any]]):
        self.beginResetModel()
        self.entries = entries
        self.endResetModel()

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self.entries)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return len(self.HEADERS)

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None
        entry = self.entries[index.row()]
        column = index.column()
        if role == QtCore.Qt.DisplayRole:
            key_map = {
                0: "date",
                1: "employee",
                2: "site_name",
                3: "kst",
                4: "activity",
                5: "start_time",
                6: "end_time",
                7: "day_fraction",
                8: "duration_hours",
                9: "result",
                10: "notes",
            }
            key = key_map.get(column)
            value = entry.get(key)
            if key in {"day_fraction", "duration_hours"} and value is not None:
                return f"{value:.2f}"
            return value or ""
        return None

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return self.HEADERS[section]
        return None

    def entry_id(self, row: int) -> Optional[int]:
        if 0 <= row < len(self.entries):
            return self.entries[row].get("id")
        return None


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = Database()
        self.current_edit_id: Optional[int] = None
        self.rounding_step = ROUNDING_STEP_DEFAULT
        self.setWindowTitle("Vermessung Tätigkeits-Log")
        self.resize(1200, 800)
        self._build_ui()
        self._load_suggestions()
        self.refresh_table()

    def _build_ui(self):
        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central)

        layout.addWidget(self._build_header())
        layout.addWidget(self._build_form())
        layout.addWidget(self._build_buttons())
        layout.addWidget(self._build_table())
        layout.addWidget(self._build_export())

        self.setCentralWidget(central)

    def _build_header(self) -> QtWidgets.QWidget:
        container = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(container)

        self.date_edit = QtWidgets.QDateEdit(datetime.date.today())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.dateChanged.connect(self.refresh_table)

        self.employee_edit = QtWidgets.QLineEdit(getpass.getuser())

        self.workday_spin = QtWidgets.QDoubleSpinBox()
        self.workday_spin.setRange(0.5, 24.0)
        self.workday_spin.setSingleStep(0.25)
        self.workday_spin.setValue(WORKDAY_HOURS_DEFAULT)

        self.rounding_spin = QtWidgets.QDoubleSpinBox()
        self.rounding_spin.setRange(0.01, 1.0)
        self.rounding_spin.setSingleStep(0.01)
        self.rounding_spin.setValue(self.rounding_step)
        self.rounding_spin.valueChanged.connect(self._update_rounding)

        form.addRow("Datum", self.date_edit)
        form.addRow("Mitarbeiter", self.employee_edit)
        form.addRow("Arbeitszeit/Tag (h)", self.workday_spin)
        form.addRow("Rundung (Anteil)", self.rounding_spin)
        return container

    def _build_form(self) -> QtWidgets.QWidget:
        container = QtWidgets.QGroupBox("Eintrag")
        grid = QtWidgets.QGridLayout(container)

        self.site_combo = QtWidgets.QComboBox()
        self.site_combo.setEditable(True)

        self.kst_combo = QtWidgets.QComboBox()
        self.kst_combo.setEditable(True)

        self.activity_combo = QtWidgets.QComboBox()
        self.activity_combo.setEditable(True)
        self.activity_combo.addItems(["Aufmaß", "Absteckung", "Scan", "Büro", "Sonstiges"])

        self.result_edit = QtWidgets.QLineEdit()
        self.notes_edit = QtWidgets.QPlainTextEdit()
        self.notes_edit.setFixedHeight(50)

        # Mode selection
        self.mode_group = QtWidgets.QButtonGroup(self)
        self.mode_start_end = QtWidgets.QRadioButton("Start/Ende")
        self.mode_fraction = QtWidgets.QRadioButton("Tagesanteil")
        self.mode_start_end.setChecked(True)
        self.mode_group.addButton(self.mode_start_end)
        self.mode_group.addButton(self.mode_fraction)
        self.mode_group.buttonToggled.connect(self._toggle_mode)

        mode_layout = QtWidgets.QHBoxLayout()
        mode_layout.addWidget(self.mode_start_end)
        mode_layout.addWidget(self.mode_fraction)

        # Start/End time widgets
        self.start_time_edit = QtWidgets.QTimeEdit(QtCore.QTime.currentTime())
        self.start_time_edit.setDisplayFormat("HH:mm")
        self.end_time_edit = QtWidgets.QTimeEdit(QtCore.QTime.currentTime())
        self.end_time_edit.setDisplayFormat("HH:mm")

        # Day fraction widgets
        self.fraction_combo = QtWidgets.QComboBox()
        self.fraction_combo.setEditable(True)
        self.fraction_combo.addItems([str(v) for v in FRACTION_CHOICES])
        self.fraction_spin = QtWidgets.QDoubleSpinBox()
        self.fraction_spin.setRange(0.0, 1.0)
        self.fraction_spin.setSingleStep(0.05)

        grid.addWidget(QtWidgets.QLabel("Baustelle"), 0, 0)
        grid.addWidget(self.site_combo, 0, 1)
        grid.addWidget(QtWidgets.QLabel("Kst"), 0, 2)
        grid.addWidget(self.kst_combo, 0, 3)

        grid.addWidget(QtWidgets.QLabel("Tätigkeit"), 1, 0)
        grid.addWidget(self.activity_combo, 1, 1)
        grid.addWidget(QtWidgets.QLabel("Ergebnis"), 1, 2)
        grid.addWidget(self.result_edit, 1, 3)

        grid.addWidget(QtWidgets.QLabel("Modus"), 2, 0)
        grid.addLayout(mode_layout, 2, 1, 1, 3)

        self.mode_stack = QtWidgets.QStackedWidget()
        # Page 0: start/end
        page_time = QtWidgets.QWidget()
        time_layout = QtWidgets.QFormLayout(page_time)
        time_layout.addRow("Start", self.start_time_edit)
        time_layout.addRow("Ende", self.end_time_edit)
        # Page 1: day fraction
        page_fraction = QtWidgets.QWidget()
        frac_layout = QtWidgets.QFormLayout(page_fraction)
        frac_layout.addRow("Anteil (Dropdown)", self.fraction_combo)
        frac_layout.addRow("Anteil (frei)", self.fraction_spin)

        self.mode_stack.addWidget(page_time)
        self.mode_stack.addWidget(page_fraction)

        grid.addWidget(self.mode_stack, 3, 0, 1, 4)

        grid.addWidget(QtWidgets.QLabel("Notizen"), 4, 0)
        grid.addWidget(self.notes_edit, 4, 1, 1, 3)

        return container

    def _build_buttons(self) -> QtWidgets.QWidget:
        container = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(container)

        self.save_button = QtWidgets.QPushButton("Speichern")
        self.save_button.clicked.connect(self.save_entry)

        self.delete_button = QtWidgets.QPushButton("Löschen")
        self.delete_button.clicked.connect(self.delete_selected)

        self.duplicate_button = QtWidgets.QPushButton("Duplizieren")
        self.duplicate_button.clicked.connect(self.duplicate_selected)

        self.last_site_button = QtWidgets.QPushButton("Letzte Baustelle übernehmen")
        self.last_site_button.clicked.connect(self.apply_last_site)

        layout.addWidget(self.save_button)
        layout.addWidget(self.delete_button)
        layout.addWidget(self.duplicate_button)
        layout.addWidget(self.last_site_button)
        layout.addStretch()
        self.status_label = QtWidgets.QLabel()
        layout.addWidget(self.status_label)

        return container

    def _build_table(self) -> QtWidgets.QWidget:
        self.table_view = QtWidgets.QTableView()
        self.table_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table_view.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table_view.doubleClicked.connect(self.load_selected_into_form)
        self.table_model = EntryTableModel([])
        self.table_view.setModel(self.table_model)
        return self.table_view

    def _build_export(self) -> QtWidgets.QWidget:
        container = QtWidgets.QGroupBox("Export")
        layout = QtWidgets.QHBoxLayout(container)

        self.month_edit = QtWidgets.QDateEdit(datetime.date.today())
        self.month_edit.setDisplayFormat("yyyy-MM")
        self.month_edit.setCalendarPopup(True)
        self.month_edit.setMinimumDate(QtCore.QDate(2000, 1, 1))

        export_csv_btn = QtWidgets.QPushButton("Monat als CSV exportieren")
        export_csv_btn.clicked.connect(self.export_csv)

        export_excel_btn = QtWidgets.QPushButton("Excel (optional)")
        export_excel_btn.clicked.connect(self.export_excel)

        layout.addWidget(QtWidgets.QLabel("Monat"))
        layout.addWidget(self.month_edit)
        layout.addWidget(export_csv_btn)
        layout.addWidget(export_excel_btn)
        layout.addStretch()
        return container

    def _toggle_mode(self):
        self.mode_stack.setCurrentIndex(0 if self.mode_start_end.isChecked() else 1)

    def _update_rounding(self, value: float):
        self.rounding_step = value

    def _load_suggestions(self):
        values = self.db.fetch_unique_values()
        for combo_name, combo in (
            ("site_name", self.site_combo),
            ("kst", self.kst_combo),
            ("activity", self.activity_combo),
        ):
            combo.clear()
            combo.addItems(values.get(combo_name, []))
            combo.setEditText("" if combo.isEditable() else combo.currentText())
            completer = QtWidgets.QCompleter(values.get(combo_name, []))
            completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
            combo.setCompleter(completer)

    def _collect_form_data(self) -> Optional[Dict[str, Any]]:
        date_str = self.date_edit.date().toString("yyyy-MM-dd")
        employee = self.employee_edit.text().strip()
        site_name = self.site_combo.currentText().strip()
        kst = self.kst_combo.currentText().strip()
        activity = self.activity_combo.currentText().strip()
        result = self.result_edit.text().strip()
        notes = self.notes_edit.toPlainText().strip()
        workday_hours = self.workday_spin.value()

        if not all([date_str, employee, site_name, kst, activity, result]):
            QtWidgets.QMessageBox.warning(self, "Fehlende Daten", "Bitte alle Pflichtfelder ausfüllen.")
            return None

        data: Dict[str, Any] = {
            "date": date_str,
            "employee": employee,
            "site_name": site_name,
            "kst": kst,
            "activity": activity,
            "result": result,
            "notes": notes,
        }

        if self.mode_start_end.isChecked():
            start_time = self.start_time_edit.time()
            end_time = self.end_time_edit.time()
            if end_time <= start_time:
                QtWidgets.QMessageBox.warning(self, "Zeitfehler", "Endzeit muss nach Startzeit liegen.")
                return None
            start_dt = datetime.datetime.combine(datetime.date.today(), start_time.toPyTime())
            end_dt = datetime.datetime.combine(datetime.date.today(), end_time.toPyTime())
            duration_hours = (end_dt - start_dt).total_seconds() / 3600
            day_fraction = duration_hours / workday_hours if workday_hours > 0 else 0
            day_fraction = self._round_fraction(day_fraction)
            if day_fraction > 1.0:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Anteil zu hoch",
                    "Berechneter Tagesanteil ist größer als 1.0. Bitte prüfen.",
                )
                return None
            data.update(
                {
                    "start_time": start_time.toString("HH:mm"),
                    "end_time": end_time.toString("HH:mm"),
                    "duration_hours": duration_hours,
                    "day_fraction": day_fraction,
                }
            )
        else:
            fraction_text = self.fraction_combo.currentText().strip()
            fraction_value = self.fraction_spin.value()
            fraction = fraction_value if fraction_value > 0 else (float(fraction_text) if fraction_text else 0.0)
            if fraction <= 0:
                QtWidgets.QMessageBox.warning(self, "Kein Anteil", "Bitte einen Tagesanteil angeben.")
                return None
            if fraction > 1.0:
                QtWidgets.QMessageBox.warning(self, "Anteil zu hoch", "Tagesanteil darf nicht größer als 1.0 sein.")
                return None
            data.update(
                {
                    "start_time": None,
                    "end_time": None,
                    "duration_hours": None,
                    "day_fraction": self._round_fraction(fraction),
                }
            )
        return data

    def _round_fraction(self, value: float) -> float:
        step = self.rounding_step or ROUNDING_STEP_DEFAULT
        rounded = math.ceil(value / step) * step
        return round(rounded, 2)

    def save_entry(self):
        data = self._collect_form_data()
        if not data:
            return
        if self.current_edit_id:
            self.db.update_entry(self.current_edit_id, data)
            self.status_label.setText("Eintrag aktualisiert")
        else:
            self.db.insert_entry(data)
            self.status_label.setText("Eintrag gespeichert")
        self.current_edit_id = None
        self._clear_form()
        self._load_suggestions()
        self.refresh_table()

    def _clear_form(self):
        self.result_edit.clear()
        self.notes_edit.clear()
        self.start_time_edit.setTime(QtCore.QTime.currentTime())
        self.end_time_edit.setTime(QtCore.QTime.currentTime())
        self.fraction_spin.setValue(0.0)
        self.fraction_combo.setCurrentIndex(0)
        self.mode_start_end.setChecked(True)

    def refresh_table(self):
        date_str = self.date_edit.date().toString("yyyy-MM-dd")
        rows = self.db.fetch_entries_by_date(date_str)
        entries = [dict(row) for row in rows]
        self.table_model.update_entries(entries)
        self.table_view.resizeColumnsToContents()

    def load_selected_into_form(self):
        index = self.table_view.currentIndex()
        if not index.isValid():
            return
        entry_id = self.table_model.entry_id(index.row())
        if not entry_id:
            return
        row = self.db.fetch_entry(entry_id)
        if not row:
            return
        self.current_edit_id = entry_id
        self.employee_edit.setText(row["employee"])
        self.site_combo.setEditText(row["site_name"])
        self.kst_combo.setEditText(row["kst"])
        self.activity_combo.setEditText(row["activity"])
        self.result_edit.setText(row["result"])
        self.notes_edit.setPlainText(row["notes"] or "")
        date = QtCore.QDate.fromString(row["date"], "yyyy-MM-dd")
        self.date_edit.setDate(date)
        if row["start_time"]:
            self.mode_start_end.setChecked(True)
            self.start_time_edit.setTime(QtCore.QTime.fromString(row["start_time"], "HH:mm"))
            self.end_time_edit.setTime(QtCore.QTime.fromString(row["end_time"], "HH:mm"))
        else:
            self.mode_fraction.setChecked(True)
            self.fraction_spin.setValue(row["day_fraction"] or 0.0)
            self.fraction_combo.setEditText(str(row["day_fraction"] or ""))

    def delete_selected(self):
        index = self.table_view.currentIndex()
        if not index.isValid():
            return
        entry_id = self.table_model.entry_id(index.row())
        if not entry_id:
            return
        confirm = QtWidgets.QMessageBox.question(
            self,
            "Löschen bestätigen",
            "Eintrag wirklich löschen?",
        )
        if confirm == QtWidgets.QMessageBox.Yes:
            self.db.delete_entry(entry_id)
            self.refresh_table()
            self.status_label.setText("Eintrag gelöscht")

    def duplicate_selected(self):
        index = self.table_view.currentIndex()
        if not index.isValid():
            return
        entry_id = self.table_model.entry_id(index.row())
        if not entry_id:
            return
        row = self.db.fetch_entry(entry_id)
        if not row:
            return
        data = dict(row)
        data.pop("id", None)
        data.pop("created_at", None)
        data.pop("updated_at", None)
        data["date"] = self.date_edit.date().toString("yyyy-MM-dd")
        self.db.insert_entry(data)
        self.refresh_table()
        self.status_label.setText("Eintrag dupliziert")

    def apply_last_site(self):
        last = self.db.fetch_recent_site()
        if last:
            site, kst = last
            self.site_combo.setEditText(site)
            self.kst_combo.setEditText(kst)
            self.status_label.setText("Letzte Baustelle übernommen")
        else:
            self.status_label.setText("Keine vorherigen Einträge")

    def export_csv(self):
        date = self.month_edit.date().toPython()
        year, month = date.year, date.month
        summaries = self.db.fetch_month_summaries(year, month)
        totals = self.db.fetch_month_totals_by_site(year, month)

        save_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "CSV speichern",
            f"monatsbericht_{year}_{month:02d}.csv",
            "CSV Files (*.csv)",
        )
        if not save_path:
            return

        with open(save_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Datum", "Baustelle", "Kst", "Tagesanteil"])
            for row in summaries:
                writer.writerow([row["date"], row["site_name"], row["kst"], f"{row['total_fraction']:.2f}"])
            writer.writerow([])
            writer.writerow(["Baustelle", "Kst", "Summe Monat"])
            for row in totals:
                writer.writerow([row["site_name"], row["kst"], f"{row['total_fraction']:.2f}"])

        QtWidgets.QMessageBox.information(self, "Export", "CSV exportiert.")

    def export_excel(self):
        try:
            import openpyxl
        except ImportError:
            QtWidgets.QMessageBox.warning(
                self,
                "OpenPyXL fehlt",
                "openpyxl ist nicht installiert. CSV-Export kann genutzt werden.",
            )
            return

        date = self.month_edit.date().toPython()
        year, month = date.year, date.month
        summaries = self.db.fetch_month_summaries(year, month)
        totals = self.db.fetch_month_totals_by_site(year, month)

        save_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Excel speichern",
            f"monatsbericht_{year}_{month:02d}.xlsx",
            "Excel (*.xlsx)",
        )
        if not save_path:
            return

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Tagesübersicht"
        ws.append(["Datum", "Baustelle", "Kst", "Tagesanteil"])
        for row in summaries:
            ws.append([row["date"], row["site_name"], row["kst"], float(row["total_fraction"] or 0)])

        ws2 = wb.create_sheet("Monatssummen")
        ws2.append(["Baustelle", "Kst", "Summe Anteil"])
        for row in totals:
            ws2.append([row["site_name"], row["kst"], float(row["total_fraction"] or 0)])

        wb.save(save_path)
        QtWidgets.QMessageBox.information(self, "Export", "Excel exportiert.")

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self.db.close()
        return super().closeEvent(event)


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    db_path = get_db_path()
    QtWidgets.QMessageBox.information(
        window,
        "Datenbank",
        f"Datenbankpfad: {db_path}\nOrdner wird bei Bedarf erstellt.",
    )
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
