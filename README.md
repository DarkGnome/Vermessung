# Vermessung Tätigkeits-Log

Desktop-App (PySide6) für Tätigkeits- & Baustellen-Log einer Vermessungsabteilung. Die Daten werden lokal in einer SQLite-Datenbank gespeichert unter `%OneDrive%\Stunden\log.db` (Fallback: `~/OneDrive/Stunden/log.db`).

## Features
- Tagesweise Erfassung mit Start/Ende oder direktem Tagesanteil.
- Automatische Berechnung und Rundung des Tagesanteils auf konfigurierbare Schritte (Standard: 0,05 bei 8h Arbeitstag).
- Pflichtfelder: Datum, Mitarbeiter, Baustelle, KSt, Tätigkeit, Ergebnis.
- Validierung: Endzeit nach Startzeit, Tagesanteil ≤ 1,0, genau ein Modus aktiv.
- Autovervollständigung für Baustelle/KSt aus vorhandenen Einträgen.
- Schnellaktionen: letzte Baustelle übernehmen, Einträge duplizieren, Bearbeiten/Löschen aus der Tagesliste.
- Monats-Export als CSV; optional Excel (erfordert `openpyxl`).

## Installation
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
```

## Nutzung
```bash
python -m src.main
```

Die Anwendung legt den benötigten Ordner automatisch an. CSV/Excel-Export landet im gleichen Ordner wie die Datenbank.
