import sys
from datetime import date
from typing import Optional

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QCompleter,
    QDateEdit,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config import ACTIVITIES, EMPLOYEES, TIME_SHARES
from db import DB, validate_entry


class ActivityLogApp(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Tätigkeits- & Baustellen-Log")
        self.resize(1100, 700)
        self._create_widgets()
        self._layout_widgets()
        self._connect_signals()
        self._populate_defaults()
        self.refresh_table()
        self.update_autocomplete()

    def _create_widgets(self) -> None:
        self.site_input = QLineEdit()
        self.activity_combo = QComboBox()
        self.activity_combo.addItems(ACTIVITIES)

        self.result_input = QLineEdit()
        self.result_input.setPlaceholderText("z.B. Aufmaßplan Aushub")

        self.time_share_combo = QComboBox()
        for val in TIME_SHARES:
            self.time_share_combo.addItem(str(val), val)

        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.employee_combo = QComboBox()
        self.employee_combo.addItems(EMPLOYEES)

        self.note_input = QLineEdit()
        self.note_input.setPlaceholderText("Optional: Korrekturhinweis")

        self.corrects_input = QSpinBox()
        self.corrects_input.setRange(0, 10_000_000)
        self.corrects_input.setSpecialValueText("-")

        self.is_correction_combo = QComboBox()
        self.is_correction_combo.addItems(["Nein", "Ja"])

        self.save_button = QPushButton("Speichern")
        self.reset_button = QPushButton("Zurücksetzen")
        self.export_button = QPushButton("CSV Export")

        self.month_filter = QComboBox()
        self.year_filter = QComboBox()
        self.stats_label = QLabel("Statistik: ")

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["Datum", "Mitarbeiter", "Baustelle", "Tätigkeit", "Ergebnis", "Zeitanteil", "Timestamp"]
        )
        self.table.setSortingEnabled(False)

    def _layout_widgets(self) -> None:
        form_layout = QFormLayout()
        form_layout.addRow("Baustelle", self.site_input)
        form_layout.addRow("Tätigkeit", self.activity_combo)
        form_layout.addRow("Ergebnis", self.result_input)
        form_layout.addRow("Zeitanteil", self.time_share_combo)
        form_layout.addRow("Datum", self.date_input)
        form_layout.addRow("Mitarbeiter", self.employee_combo)
        form_layout.addRow("Korrektur?", self.is_correction_combo)
        form_layout.addRow("Korrigiert ID", self.corrects_input)
        form_layout.addRow("Notiz", self.note_input)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.reset_button)
        button_layout.addWidget(self.export_button)

        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Monat"))
        filter_layout.addWidget(self.month_filter)
        filter_layout.addWidget(QLabel("Jahr"))
        filter_layout.addWidget(self.year_filter)
        filter_layout.addStretch()
        filter_layout.addWidget(self.stats_label)

        top_box = QGroupBox("Eingabe")
        top_layout = QVBoxLayout()
        top_layout.addLayout(form_layout)
        top_layout.addLayout(button_layout)
        top_box.setLayout(top_layout)

        main_layout = QVBoxLayout()
        main_layout.addWidget(top_box)
        main_layout.addLayout(filter_layout)
        main_layout.addWidget(self.table)
        self.setLayout(main_layout)

    def _connect_signals(self) -> None:
        self.save_button.clicked.connect(self.save_entry)
        self.reset_button.clicked.connect(self.reset_form)
        self.export_button.clicked.connect(self.export_csv)
        self.month_filter.currentIndexChanged.connect(self.refresh_table)
        self.year_filter.currentIndexChanged.connect(self.refresh_table)

    def _populate_defaults(self) -> None:
        today = QDate.currentDate()
        self.date_input.setDate(today)
        self.month_filter.addItem("Alle", None)
        for month in range(1, 13):
            self.month_filter.addItem(f"{month:02d}", month)
        current_year = date.today().year
        self.year_filter.addItem("Alle", None)
        for year in range(current_year - 3, current_year + 2):
            self.year_filter.addItem(str(year), year)
        self.year_filter.setCurrentText(str(current_year))
        self.month_filter.setCurrentIndex(today.month())

    def update_autocomplete(self) -> None:
        sites = DB.distinct_sites()
        completer = QCompleter(sites)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.site_input.setCompleter(completer)

    def _current_month_year(self) -> tuple[Optional[int], Optional[int]]:
        month = self.month_filter.currentData()
        year = self.year_filter.currentData()
        return (month, year)

    def refresh_table(self) -> None:
        month, year = self._current_month_year()
        entries = DB.fetch_recent_entries(limit=200, month=month, year=year)
        self.table.setRowCount(len(entries))
        for row_idx, row in enumerate(entries):
            self.table.setItem(row_idx, 0, QTableWidgetItem(row["date"]))
            self.table.setItem(row_idx, 1, QTableWidgetItem(row["employee"]))
            self.table.setItem(row_idx, 2, QTableWidgetItem(row["site"]))
            self.table.setItem(row_idx, 3, QTableWidgetItem(row["activity"]))
            self.table.setItem(row_idx, 4, QTableWidgetItem(row["result"]))
            self.table.setItem(row_idx, 5, QTableWidgetItem(str(row["time_share"])))
            self.table.setItem(row_idx, 6, QTableWidgetItem(row["timestamp"]))
        self.table.resizeColumnsToContents()
        self.table.resizeRowsToContents()
        self.update_stats(month, year)

    def update_stats(self, month: Optional[int], year: Optional[int]) -> None:
        if not month or not year:
            self.stats_label.setText("Statistik: Bitte Monat & Jahr wählen")
            return
        stats = DB.time_share_statistics(month, year)
        if not stats:
            self.stats_label.setText("Statistik: Keine Daten")
            return
        parts = [f"{row['employee']}: {row['total_time']:.2f}" for row in stats]
        self.stats_label.setText("Statistik: " + ", ".join(parts))

    def export_csv(self) -> None:
        path = DB.export_csv()
        QMessageBox.information(self, "CSV Export", f"Export gespeichert unter\n{path}")

    def _validate_inputs(self) -> Optional[str]:
        if not self.site_input.text().strip():
            return "Baustelle darf nicht leer sein."
        if len(self.result_input.text().strip()) < 5:
            return "Ergebnis muss mindestens 5 Zeichen enthalten."
        if self.employee_combo.currentText().strip() == "":
            return "Bitte Mitarbeiter auswählen."
        return None

    def save_entry(self) -> None:
        error = self._validate_inputs()
        if error:
            QMessageBox.warning(self, "Validierung", error)
            return

        activity = self.activity_combo.currentText()
        time_share = float(self.time_share_combo.currentData())
        try:
            validate_entry(activity, time_share)
        except ValueError as exc:
            QMessageBox.warning(self, "Validierung", str(exc))
            return

        entry_date = self.date_input.date().toPython()
        employee = self.employee_combo.currentText()
        site = self.site_input.text().strip()
        result_text = self.result_input.text().strip()
        is_correction = self.is_correction_combo.currentIndex() == 1
        corrects_id = self.corrects_input.value() or None
        note = self.note_input.text().strip()

        new_id = DB.add_entry(
            entry_date=entry_date,
            employee=employee,
            site=site,
            activity=activity,
            result_text=result_text,
            time_share=time_share,
            is_correction=is_correction,
            corrects_id=corrects_id,
            note=note,
        )
        QMessageBox.information(self, "Gespeichert", f"Eintrag #{new_id} wurde gespeichert.")
        self.refresh_table()
        self.update_autocomplete()
        self.reset_form()

    def reset_form(self) -> None:
        self.site_input.clear()
        self.result_input.clear()
        self.time_share_combo.setCurrentIndex(0)
        self.activity_combo.setCurrentIndex(0)
        self.employee_combo.setCurrentIndex(0)
        self.date_input.setDate(QDate.currentDate())
        self.is_correction_combo.setCurrentIndex(0)
        self.corrects_input.setValue(0)
        self.note_input.clear()


def main() -> None:
    app = QApplication(sys.argv)
    window = ActivityLogApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
