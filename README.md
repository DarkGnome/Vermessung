# Vermessung Tätigkeits-Log

Desktop-Anwendung (PySide6) zur schnellen Erfassung von Tätigkeiten und Baustellenzeiten einer Vermessungsabteilung. Die Daten werden lokal als SQLite-Datenbank `%OneDrive%\Stunden\log.db` gespeichert. Der Ordner wird bei Bedarf automatisch angelegt.

## Voraussetzungen
- Python 3.10+
- [PySide6](https://doc.qt.io/qtforpython/) (`pip install PySide6`)
- Optional: `openpyxl` für den Excel-Export (`pip install openpyxl`)

## Starten
```bash
python app.py
```

Beim Start zeigt die Anwendung den Speicherort der Datenbank an. In der Oberfläche können Tagesdatum, Mitarbeiter, Arbeitszeit sowie Rundungsfaktor eingestellt werden. Es stehen zwei Eingabemodi zur Auswahl:
- **Start/Ende**: Zeiten eingeben; Anteil wird anhand der Arbeitszeit/Tag berechnet und auf den Rundungsschritt aufgerundet.
- **Tagesanteil**: Anteil direkt wählen oder frei eingeben (max. 1,0); Zeiten bleiben leer.
- Zusätzlich lässt sich die tägliche Arbeitszeit mit Beginn, Ende und Pausenminuten erfassen und speichern. Der erfasste Nettowert wird automatisch für die Anteilberechnung verwendet.

Für das schnelle Ein-/Ausstempeln pro Kostenstelle stehen "Jetzt"-Buttons neben Start- und Endzeit zur Verfügung.

Eine Tabellenansicht zeigt die Einträge des ausgewählten Tages. Einträge lassen sich per Doppelklick bearbeiten, duplizieren oder löschen. Buttons unterstützen das Übernehmen der zuletzt genutzten Baustelle/Kostenstelle.

### Export
Über den Export-Block kann ein Monat gewählt und als CSV exportiert werden (Summen pro Tag/Baustelle sowie Monatssummen pro Baustelle). Wenn `openpyxl` installiert ist, wird zusätzlich eine Excel-Datei `monatsbericht_YYYY_MM.xlsx` erzeugt.
