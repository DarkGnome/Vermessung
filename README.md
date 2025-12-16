# Vermessungs-Log

Desktop-App (PySide6) zum Erfassen von Tätigkeits- und Baustellenzeiten für Vermessungsabteilungen.

## Funktionen
- Tagesmaske mit Datum, Mitarbeiter, Arbeitszeit/Tag und Rundungsschritt
- Wahl zwischen **Start/Ende** oder direktem **Tagesanteil**
- Pflichtfelder: Baustelle, Kostenstelle, Tätigkeit, Ergebnis
- Automatische Berechnung und Rundung des Tagesanteils bei Start/Ende, Validierung gegen > 1,0
- Liste der Tageseinträge mit Bearbeiten, Löschen und Duplizieren
- Schnellfunktion „Letzte Baustelle übernehmen“
- Autocomplete für Baustellen/Kostenstellen/Tätigkeiten
- Monatsauswertung als CSV sowie optional Excel (wenn Pandas verfügbar)

## Installation
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
```

## Start
```bash
python -m vermessung_log.app
```

Die Datenbank wird automatisch unter `%OneDrive%/Stunden/log.db` (bzw. `~/OneDrive/Stunden/log.db`) angelegt.

## Export
Wähle im unteren Bereich den Monat (YYYY-MM) und exportiere CSV oder Excel (benötigt Pandas). CSV enthält Tages- und Monatssummen pro Baustelle/Kostenstelle.
