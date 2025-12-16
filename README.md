# Vermessung Tätigkeits-Log

Desktop-App für die schnelle Erfassung von Tätigkeiten und Baustellenzeiten einer Vermessungsabteilung.

## Voraussetzungen
- Python 3.10+
- Abhängigkeiten installieren: `pip install -r requirements.txt`

## Starten
```
python app.py
```

Die Datenbank wird automatisch unter `%OneDrive%/Stunden/log.db` angelegt (OneDrive-Pfad wird aus der Umgebung ermittelt; falls nicht vorhanden, wird `~/OneDrive/Stunden` genutzt).

## Funktionen
- Tagesbasierte Eingabe mit Start-/Endzeit oder direktem Tagesanteil.
- Automatische Berechnung des Tagesanteils basierend auf der konfigurierbaren Arbeitszeit (Standard 8h) und Rundung auf 0,05.
- Pflichtfelder: Datum, Mitarbeiter, Baustelle, Kostenstelle, Tätigkeit, Ergebnis sowie entweder Zeiten oder Tagesanteil.
- Autocomplete für Baustelle/Kostenstelle/Tätigkeit aus vorhandenen Einträgen.
- Einträge des Tages anzeigen, bearbeiten, duplizieren oder löschen.
- Schnellfunktion „Letzte Baustelle übernehmen“.
- Monatliche Auswertung und CSV-Export mit Tagessummen je KST und Monatsgesamt je KST.
