"""Refaktorisierte Version der seriellen Lautstärkesteuerung."""

import argparse
import os
import time
from typing import List, Optional, Sequence

import pythoncom
import serial as sp
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume, ISimpleAudioVolume

from load_app_mapping import load_app_mapping

NUM_SLIDERS = 5
MIN_CHANGE_THRESHOLD = 0.02  # Minimale Änderungsschwelle (2%)
DEFAULT_COM_PORT = "COM9"
DEFAULT_BAUD_RATE = 115200
DEFAULT_CONFIG_FILE = "config.csv"


def get_session_volume_control(process_name: str) -> Optional[object]:
    """Gibt das Lautstärke-Steuerelement für den Prozess zurück."""
    if process_name == "System":
        try:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            return interface.QueryInterface(IAudioEndpointVolume)
        except Exception as exc:
            print(f"WARNUNG: System-Lautstärke konnte nicht abgefragt werden: {exc}")
            return None

    if process_name == "NONE":
        return None

    try:
        sessions = AudioUtilities.GetAllSessions()
    except Exception as exc:
        print(f"WARNUNG: Konnte Audio-Sessions nicht lesen: {exc}")
        return None

    controls: List[ISimpleAudioVolume] = []
    for session in sessions:
        if session.Process and session.Process.name() == process_name:
            try:
                controls.append(session._ctl.QueryInterface(ISimpleAudioVolume))
            except Exception:
                continue

    return controls if controls else None


def parse_serial_values(line: bytes, num_sliders: int) -> Optional[List[float]]:
    """Parst eine serielle Zeile in eine Liste von Volumenwerten zwischen 0.0 und 1.0."""
    if not line:
        return None

    try:
        text = line.decode("utf-8", errors="ignore").strip()
    except Exception:
        return None

    if "|" not in text:
        return None

    parts = [part.strip() for part in text.split("|")]
    if len(parts) != num_sliders:
        print(f"WARNUNG: Erwartet {num_sliders} Werte, gefunden {len(parts)}: {text}")
        return None

    values: List[float] = []
    for part in parts:
        try:
            raw_value = int(part)
        except ValueError:
            print(f"WARNUNG: Ungültiger Wert in serieller Eingabe: {part}")
            return None

        values.append(max(0, min(100, raw_value)) / 100.0)

    return values


def set_filtered_volume(
    index: int,
    target_volume_scalar: float,
    volume_control: Optional[object],
    current_display_values: List[float],
    app_name: str,
) -> bool:
    """Setzt die Lautstärke und aktualisiert den angezeigten Wert."""
    if volume_control is None:
        return False

    try:
        if app_name == "System":
            volume_control.SetMasterVolumeLevelScalar(target_volume_scalar, None)
        elif isinstance(volume_control, list):
            for ctl in volume_control:
                try:
                    ctl.SetMasterVolume(target_volume_scalar, None)
                except Exception as exc:
                    print(f"WARNUNG: Session-Lautstärke für {app_name} konnte nicht gesetzt werden: {exc}")
                    continue
        else:
            volume_control.SetMasterVolume(target_volume_scalar, None)
    except Exception as exc:
        print(f"WARNUNG: Lautstärke für {app_name} konnte nicht gesetzt werden: {exc}")
        return False

    current_display_values[index] = target_volume_scalar
    return True


def print_status(app_mapping: Sequence[str], current_display_values: Sequence[float], sessions_active: Sequence[bool]) -> None:
    os.system("cls" if os.name == "nt" else "clear")
    print("--- Serielle Lautstärkeregelung aktiv (5 Regler) ---")
    for index, app_name in enumerate(app_mapping):
        active_text = " [AKTIV]" if sessions_active[index] else ""
        print(
            f"Regler {index + 1} ({app_name}): Lautstärke: {int(current_display_values[index] * 100)}%{active_text}"
        )


def create_serial_connection(port: str, baud_rate: int, timeout: float = 0.1) -> sp.Serial:
    return sp.Serial(port, baud_rate, timeout=timeout)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serielle Lautstärkeregelung für Windows-Audio.")
    parser.add_argument("--config", default=DEFAULT_CONFIG_FILE, help="Pfad zur config.csv")
    parser.add_argument("--port", default=DEFAULT_COM_PORT, help="Serieller COM-Port")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD_RATE, help="Baudrate für die serielle Verbindung")
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    app_mapping = load_app_mapping(args.config, NUM_SLIDERS)
    sessions_active = [False] * NUM_SLIDERS
    current_display_values = [0.0] * NUM_SLIDERS

    try:
        pythoncom.CoInitialize()
    except Exception:
        pass

    try:
        ser = create_serial_connection(args.port, args.baud)
    except sp.SerialException:
        print(f"FEHLER: Konnte COM-Port {args.port} nicht öffnen. Prüfen Sie Anschluss und Baudrate.")
        print("Stellen Sie sicher, dass das Pico-Gerät angeschlossen ist.")
        return

    print("--- Serielle Lautstärkeregelung gestartet ---")

    try:
        while True:
            try:
                line = ser.readline()
                values = parse_serial_values(line, NUM_SLIDERS)
                if values is None:
                    continue

                update_needed = False
                for index, value in enumerate(values):
                    app_name = app_mapping[index]
                    volume_control = get_session_volume_control(app_name)
                    active = volume_control is not None

                    if active != sessions_active[index]:
                        sessions_active[index] = active
                        update_needed = True

                    if active and abs(value - current_display_values[index]) > MIN_CHANGE_THRESHOLD:
                        if set_filtered_volume(index, value, volume_control, current_display_values, app_name):
                            update_needed = True

                if update_needed:
                    print_status(app_mapping, current_display_values, sessions_active)
            except sp.SerialTimeoutException:
                pass
            except Exception as exc:
                print(f"Ein unerwarteter Fehler ist aufgetreten: {exc}")
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            ser.close()
        except Exception:
            pass
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


if __name__ == "__main__":
    main()
