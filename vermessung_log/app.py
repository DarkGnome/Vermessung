import getpass
import sys
from datetime import datetime, date, time
from typing import Dict, Optional

from PySide6.QtCore import QDate, QTime, Qt
from PySide6.QtGui import QCloseEvent, QDoubleValidator
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QCompleter,
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
)

from .database import DatabaseManager, default_db_path
from .exporter import MonthExporter


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Vermessungs-Log")
        self.db_path = default_db_path()
        self.db = DatabaseManager(self.db_path)
        self.exporter = MonthExporter(self.db_path.parent)

        self.editing_id: Optional[int] = None
        self.default_employee = getpass.getuser()

        self._build_ui()
        self.load_entries_for_selected_date()
        self.refresh_completers()

    # UI construction
    def _build_ui(self) -> None:
        container = QWidget()
        main_layout = QVBoxLayout()

        main_layout.addLayout(self._build_header())
        main_layout.addWidget(self._build_entry_group())
        main_layout.addWidget(self._build_action_buttons())
        main_layout.addWidget(self._build_table())
        main_layout.addWidget(self._build_export_group())

        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def _build_header(self) -> QHBoxLayout:
        layout = QHBoxLayout()

        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.dateChanged.connect(self.load_entries_for_selected_date)

        self.employee_edit = QLineEdit(self.default_employee)

        self.workday_hours = QDoubleSpinBox()
        self.workday_hours.setRange(1.0, 24.0)
        self.workday_hours.setSingleStep(0.25)
        self.workday_hours.setValue(8.0)

        self.rounding_step = QDoubleSpinBox()
        self.rounding_step.setRange(0.01, 1.0)
        self.rounding_step.setSingleStep(0.01)
        self.rounding_step.setValue(0.05)

        layout.addWidget(QLabel("Datum:"))
        layout.addWidget(self.date_edit)
        layout.addWidget(QLabel("Mitarbeiter:"))
        layout.addWidget(self.employee_edit)
        layout.addWidget(QLabel("Arbeitszeit/Tag (h):"))
        layout.addWidget(self.workday_hours)
        layout.addWidget(QLabel("Rundungsschritt:"))
        layout.addWidget(self.rounding_step)
        layout.addStretch(1)

        return layout

    def _build_entry_group(self) -> QGroupBox:
        group = QGroupBox("Neuer Eintrag")
        layout = QFormLayout()

        self.site_combo = QComboBox()
        self.site_combo.setEditable(True)

        self.kst_combo = QComboBox()
        self.kst_combo.setEditable(True)

        self.activity_combo = QComboBox()
        self.activity_combo.setEditable(True)
        for activity in ["Aufmaß", "Absteckung", "Scan", "Büro", "Sonstiges"]:
            self.activity_combo.addItem(activity)

        self.result_edit = QLineEdit()
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Notizen (optional)")

        # Mode selection
        self.mode_group = QButtonGroup()
        self.mode_time_radio = QRadioButton("Start/Ende")
        self.mode_fraction_radio = QRadioButton("Tagesanteil")
        self.mode_time_radio.setChecked(True)
        self.mode_group.addButton(self.mode_time_radio)
        self.mode_group.addButton(self.mode_fraction_radio)
        self.mode_time_radio.toggled.connect(self._toggle_mode_fields)

        mode_layout = QHBoxLayout()
        mode_layout.addWidget(self.mode_time_radio)
        mode_layout.addWidget(self.mode_fraction_radio)

        # Time inputs
        self.start_time_edit = QTimeEdit(QTime.currentTime())
        self.end_time_edit = QTimeEdit(QTime.currentTime())

        # Day fraction input
        self.day_fraction_combo = QComboBox()
        self.day_fraction_combo.setEditable(True)
        self.day_fraction_combo.addItems(
            ["0.1", "0.2", "0.25", "0.3", "0.4", "0.5", "0.6", "0.75", "0.8", "1.0"]
        )
        self.day_fraction_combo.setEditText("0.5")
        self.day_fraction_combo.lineEdit().setValidator(QDoubleValidator(0.0, 1.0, 2))

        self.copy_last_site_button = QPushButton("Letzte Baustelle übernehmen")
        self.copy_last_site_button.clicked.connect(self.use_last_site)

        layout.addRow(QLabel("Baustelle:"), self.site_combo)
        layout.addRow(QLabel("Kostenstelle:"), self.kst_combo)
        layout.addRow(QLabel("Tätigkeit:"), self.activity_combo)
        layout.addRow(QLabel("Ergebnis:"), self.result_edit)
        layout.addRow(QLabel("Modus:"), mode_layout)
        layout.addRow(QLabel("Startzeit:"), self.start_time_edit)
        layout.addRow(QLabel("Endzeit:"), self.end_time_edit)
        layout.addRow(QLabel("Tagesanteil:"), self.day_fraction_combo)
        layout.addRow(self.copy_last_site_button)
        layout.addRow(QLabel("Notizen:"), self.notes_edit)

        group.setLayout(layout)
        self._toggle_mode_fields()
        return group

    def _build_action_buttons(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout()

        self.save_button = QPushButton("Speichern")
        self.save_button.clicked.connect(self.save_entry)

        self.edit_button = QPushButton("Laden zum Bearbeiten")
        self.edit_button.clicked.connect(self.load_selected_entry)

        self.delete_button = QPushButton("Löschen")
        self.delete_button.clicked.connect(self.delete_selected_entry)

        self.duplicate_button = QPushButton("Duplizieren")
        self.duplicate_button.clicked.connect(self.duplicate_selected_entry)

        layout.addWidget(self.save_button)
        layout.addWidget(self.edit_button)
        layout.addWidget(self.delete_button)
        layout.addWidget(self.duplicate_button)
        layout.addStretch(1)

        widget.setLayout(layout)
        return widget

    def _build_table(self) -> QGroupBox:
        group = QGroupBox("Einträge am Tag")
        layout = QVBoxLayout()

        self.entry_table = QTableWidget()
        self.entry_table.setColumnCount(11)
        self.entry_table.setHorizontalHeaderLabels(
            [
                "ID",
                "Datum",
                "Mitarbeiter",
                "Baustelle",
                "Kst",
                "Tätigkeit",
                "Start",
                "Ende",
                "Tagesanteil",
                "Ergebnis",
                "Notizen",
            ]
        )
        self.entry_table.setColumnHidden(0, True)
        self.entry_table.cellDoubleClicked.connect(lambda *_: self.load_selected_entry())

        layout.addWidget(self.entry_table)
        group.setLayout(layout)
        return group

    def _build_export_group(self) -> QGroupBox:
        group = QGroupBox("Auswertung / Export")
        layout = QHBoxLayout()

        self.month_edit = QDateEdit(QDate.currentDate())
        self.month_edit.setDisplayFormat("yyyy-MM")
        self.month_edit.setCalendarPopup(True)
        self.month_edit.setDate(QDate.currentDate().addDays(-QDate.currentDate().day() + 1))

        export_csv_button = QPushButton("Export CSV")
        export_csv_button.clicked.connect(self.export_csv)

        export_excel_button = QPushButton("Export Excel")
        export_excel_button.clicked.connect(self.export_excel)

        layout.addWidget(QLabel("Monat:"))
        layout.addWidget(self.month_edit)
        layout.addWidget(export_csv_button)
        layout.addWidget(export_excel_button)
        layout.addStretch(1)

        group.setLayout(layout)
        return group

    # Data handling
    def _toggle_mode_fields(self) -> None:
        use_time = self.mode_time_radio.isChecked()
        self.start_time_edit.setEnabled(use_time)
        self.end_time_edit.setEnabled(use_time)
        self.day_fraction_combo.setEnabled(not use_time)

    def _collect_entry_data(self) -> Optional[Dict]:
        selected_date = self.date_edit.date().toString("yyyy-MM-dd")
        employee = self.employee_edit.text().strip() or self.default_employee
        site_name = self.site_combo.currentText().strip()
        kst = self.kst_combo.currentText().strip()
        activity = self.activity_combo.currentText().strip()
        result_text = self.result_edit.text().strip()
        notes = self.notes_edit.toPlainText().strip() or None
        rounding_step = float(self.rounding_step.value())

        if not site_name or not kst or not activity or not result_text:
            QMessageBox.warning(self, "Fehlende Daten", "Bitte alle Pflichtfelder ausfüllen.")
            return None

        workday_hours = float(self.workday_hours.value())
        day_fraction: Optional[float] = None
        duration_hours: Optional[float] = None
        start_time_str: Optional[str] = None
        end_time_str: Optional[str] = None

        if self.mode_time_radio.isChecked():
            start_qtime = self.start_time_edit.time()
            end_qtime = self.end_time_edit.time()
            start_time_str = start_qtime.toString("HH:mm")
            end_time_str = end_qtime.toString("HH:mm")

            start_dt = datetime.combine(date.today(), time(start_qtime.hour(), start_qtime.minute()))
            end_dt = datetime.combine(date.today(), time(end_qtime.hour(), end_qtime.minute()))
            if end_dt <= start_dt:
                QMessageBox.warning(self, "Ungültige Zeit", "Endzeit muss nach Startzeit liegen.")
                return None
            duration_hours = (end_dt - start_dt).total_seconds() / 3600
            day_fraction_raw = duration_hours / workday_hours
            day_fraction = round(day_fraction_raw / rounding_step) * rounding_step
            if day_fraction > 1.0:
                QMessageBox.warning(self, "Zu großer Anteil", "Tagesanteil darf nicht größer als 1,0 sein.")
                return None
        else:
            try:
                day_fraction = float(self.day_fraction_combo.currentText())
            except ValueError:
                QMessageBox.warning(self, "Ungültiger Tagesanteil", "Bitte gültige Zahl eingeben.")
                return None
            if day_fraction > 1.0:
                QMessageBox.warning(self, "Zu großer Anteil", "Tagesanteil darf nicht größer als 1,0 sein.")
                return None
            duration_hours = day_fraction * workday_hours
            start_time_str = None
            end_time_str = None

        if day_fraction is None:
            QMessageBox.warning(self, "Fehlende Zeitangaben", "Bitte Start/Endzeit oder Tagesanteil angeben.")
            return None

        created = datetime.now().isoformat(timespec="seconds")

        return {
            "date": selected_date,
            "employee": employee,
            "site_name": site_name,
            "kst": kst,
            "activity": activity,
            "start_time": start_time_str,
            "end_time": end_time_str,
            "day_fraction": round(day_fraction, 3),
            "duration_hours": round(duration_hours or 0, 3),
            "result": result_text,
            "notes": notes,
            "created_at": created,
            "updated_at": created,
        }

    def save_entry(self) -> None:
        entry = self._collect_entry_data()
        if not entry:
            return

        if self.editing_id is None:
            self.db.insert_entry(entry)
        else:
            entry.pop("created_at", None)
            entry["updated_at"] = datetime.now().isoformat(timespec="seconds")
            self.db.update_entry(self.editing_id, entry)

        self.clear_form()
        self.load_entries_for_selected_date()
        self.refresh_completers()

    def load_entries_for_selected_date(self) -> None:
        date_str = self.date_edit.date().toString("yyyy-MM-dd")
        entries = self.db.entries_for_date(date_str)
        self.entry_table.setRowCount(len(entries))

        for row_idx, entry in enumerate(entries):
            values = [
                entry["id"],
                entry["date"],
                entry["employee"],
                entry["site_name"],
                entry["kst"],
                entry["activity"],
                entry["start_time"] or "",
                entry["end_time"] or "",
                f"{entry['day_fraction']:.2f}" if entry["day_fraction"] is not None else "",
                entry["result"],
                entry["notes"] or "",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                self.entry_table.setItem(row_idx, col, item)

        self.entry_table.resizeColumnsToContents()

    def _selected_entry_id(self) -> Optional[int]:
        current_row = self.entry_table.currentRow()
        if current_row < 0:
            return None
        item = self.entry_table.item(current_row, 0)
        if item:
            return int(item.text())
        return None

    def load_selected_entry(self) -> None:
        entry_id = self._selected_entry_id()
        if entry_id is None:
            QMessageBox.information(self, "Auswahl", "Bitte einen Eintrag auswählen.")
            return
        entry = self.db.get_entry(entry_id)
        if not entry:
            return

        self.editing_id = entry_id
        self.date_edit.setDate(QDate.fromString(entry["date"], "yyyy-MM-dd"))
        self.employee_edit.setText(entry["employee"])
        self.site_combo.setEditText(entry["site_name"])
        self.kst_combo.setEditText(entry["kst"])
        self.activity_combo.setEditText(entry["activity"])
        self.result_edit.setText(entry["result"])
        self.notes_edit.setPlainText(entry["notes"] or "")

        if entry["start_time"] and entry["end_time"]:
            self.mode_time_radio.setChecked(True)
            self.start_time_edit.setTime(QTime.fromString(entry["start_time"], "HH:mm"))
            self.end_time_edit.setTime(QTime.fromString(entry["end_time"], "HH:mm"))
        else:
            self.mode_fraction_radio.setChecked(True)
            if entry["day_fraction"] is not None:
                self.day_fraction_combo.setEditText(str(entry["day_fraction"]))
        self._toggle_mode_fields()

    def delete_selected_entry(self) -> None:
        entry_id = self._selected_entry_id()
        if entry_id is None:
            QMessageBox.information(self, "Auswahl", "Bitte einen Eintrag auswählen.")
            return
        if QMessageBox.question(self, "Löschen", "Eintrag wirklich löschen?") == QMessageBox.StandardButton.Yes:
            self.db.delete_entry(entry_id)
            self.load_entries_for_selected_date()

    def duplicate_selected_entry(self) -> None:
        entry_id = self._selected_entry_id()
        if entry_id is None:
            QMessageBox.information(self, "Auswahl", "Bitte einen Eintrag auswählen.")
            return
        entry = self.db.get_entry(entry_id)
        if not entry:
            return

        new_entry = dict(entry)
        new_entry.pop("id", None)
        new_entry["date"] = self.date_edit.date().toString("yyyy-MM-dd")
        now_str = datetime.now().isoformat(timespec="seconds")
        new_entry["created_at"] = now_str
        new_entry["updated_at"] = now_str
        self.db.insert_entry(new_entry)
        self.load_entries_for_selected_date()
        self.refresh_completers()

    def use_last_site(self) -> None:
        entry = self.db.latest_entry()
        if not entry:
            QMessageBox.information(self, "Keine Daten", "Es existieren noch keine Einträge.")
            return
        self.site_combo.setEditText(entry["site_name"])
        self.kst_combo.setEditText(entry["kst"])

    def export_csv(self) -> None:
        month_label = self.month_edit.date().toString("yyyy-MM")
        year = self.month_edit.date().year()
        month = self.month_edit.date().month()
        entries = [dict(row) for row in self.db.entries_for_month(year, month)]
        path = self.exporter.export_csv(month_label, entries)
        QMessageBox.information(self, "Export", f"CSV gespeichert unter\n{path}")

    def export_excel(self) -> None:
        month_label = self.month_edit.date().toString("yyyy-MM")
        year = self.month_edit.date().year()
        month = self.month_edit.date().month()
        entries = [dict(row) for row in self.db.entries_for_month(year, month)]
        try:
            path = self.exporter.export_excel(month_label, entries)
            QMessageBox.information(self, "Export", f"Excel gespeichert unter\n{path}")
        except Exception as exc:  # pragma: no cover - GUI feedback only
            QMessageBox.warning(self, "Export fehlgeschlagen", str(exc))

    def clear_form(self) -> None:
        self.editing_id = None
        self.result_edit.clear()
        self.notes_edit.clear()
        self.mode_time_radio.setChecked(True)
        self.start_time_edit.setTime(QTime.currentTime())
        self.end_time_edit.setTime(QTime.currentTime())
        self.day_fraction_combo.setEditText("0.5")
        self._toggle_mode_fields()

    def refresh_completers(self) -> None:
        self._set_completer(self.site_combo, self.db.distinct_values("site_name"))
        self._set_completer(self.kst_combo, self.db.distinct_values("kst"))
        self._set_completer(self.activity_combo, self.db.distinct_values("activity"))

    def _set_completer(self, combo: QComboBox, values: list[str]) -> None:
        completer = QCompleter(values)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        combo.setCompleter(completer)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self.db.close()
        event.accept()


def run() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run()
