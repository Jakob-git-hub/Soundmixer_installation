# Soundmixer_installation

Python-Projekt zur seriellen Steuerung der Windows-Lautstärke über 5 Hardware-Regler.

## Inhalte

- `/gui_config.py` – GUI zur Zuordnung von Reglern zu Apps/Prozessen
- `/volume_logic.py` – Laufzeitlogik für serielle Eingaben und Lautstärkesteuerung
- `/load_app_mapping.py` – Laden der `config.csv`
- `/config.csv` – Aktuelle Regler-Zuordnung

## Voraussetzungen

- Windows (für `pycaw`, COM-Audio und Registry-Abfragen)
- Python 3.10+
- Installierte Pakete:
  - `customtkinter`
  - `psutil`
  - `pyserial`
  - `pycaw`
  - `comtypes`

## Nutzung

1. `gui_config.py` starten.
2. Pro Regler eine Zuordnung wählen.
3. Auf **Konfiguration speichern** klicken.
4. Die Logik wird mit aktueller Konfiguration neu gestartet.

## Konfigurationsdatei

Die Datei `config.csv` hat dieses Format:

```csv
Regler_Index,Prozess_Name
0,System
1,Spotify.exe
...
```

Leere Einträge werden intern als `NONE` behandelt.