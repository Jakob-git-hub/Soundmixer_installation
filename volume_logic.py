import serial as sp
import pythoncom
from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume, IAudioEndpointVolume
from comtypes import CLSCTX_ALL
import time
import os
import csv

# --- KONFIGURATION ---
COM_PORT = 'COM9'
BAUD_RATE = 115200 

# Wie viele Regler das System aktuell unterstützt
NUM_SLIDERS = 5 

# Lautstärkelogik:
MIN_CHANGE_THRESHOLD = 2      # Eine Änderung von 2% ist notwendig (2 von 100)
CONFIG_FILE = 'config.csv'
DEFAULT_MAPPING = {
    0: "System",
    1: "Spotify.exe",
    2: "firefox.exe",
    3: "discord.exe",
    4: "chrome.exe"
}

# Globale Variablen zur Statusverwaltung
LAST_VOLUME_VALUES = {}       # Speichert den zuletzt gesetzten Prozentwert (0-100)
CURRENT_DISPLAY_VALUES = {i: 0.0 for i in range(NUM_SLIDERS)} # Initialisiert 5 Einträge

# --- KONFIGURATION LADEN ---

def load_app_mapping(filename=CONFIG_FILE):
    """Läd das APP_MAPPING aus der CSV-Datei."""
    app_map = {}
    
    # 1. Versuche, die Konfiguration aus der Datei zu laden
    try:
        with open(filename, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.reader(file)
            next(reader)  # Überspringe die Header-Zeile
            for row in reader:
                if len(row) == 2:
                    try:
                        index = int(row[0])
                        # Speichere den Prozessnamen (oder "KEINE ZUORDNUNG", wenn leer)
                        process_name = row[1] if row[1].strip() != "" else "KEINE ZUORDNUNG"
                        app_map[index] = process_name
                    except ValueError:
                        # Ignoriere Zeilen mit ungültigem Index
                        continue
    except FileNotFoundError:
        # 2. Wenn die Datei nicht existiert, verwende Standardwerte
        app_map = DEFAULT_MAPPING
    
    # 3. Ergänze fehlende Regler mit "KEINE ZUORDNUNG" (falls die CSV unvollständig war)
    for i in range(NUM_SLIDERS):
        if i not in app_map:
            app_map[i] = "KEINE ZUORDNUNG"
            
    return app_map

APP_MAPPING = load_app_mapping() 

# --- PYCAW & LAUTSTÄRKE-FUNKTIONEN ---

def get_session_volume_control(process_name):
    """Gibt das Lautstärke-Steuerelement für den Prozess zurück."""
    if process_name == "System":
        try:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            return interface.QueryInterface(IAudioEndpointVolume)
        except Exception:
            return None
    
    if process_name == "KEINE ZUORDNUNG":
        return None

    sessions = AudioUtilities.GetAllSessions()
    for session in sessions:
        if session.Process and session.Process.name() == process_name:
            return session._ctl.QueryInterface(ISimpleAudioVolume)
            
    return None

def set_filtered_volume(regler_index, new_input_value):
    """Setzt die Lautstärke unter Berücksichtigung von Debouncing und Skalierung."""
    
    # Wert prüfen (erwartet 0-100 vom Pico)
    try:
        filtered_value = int(new_input_value)
    except ValueError:
        return False # Ungültiger Wert
    
    # Begrenzung auf 0-100
    filtered_value = max(0, min(100, filtered_value))
    
    # 1. Filterung kleiner Änderungen (Debouncing)
    last_value = LAST_VOLUME_VALUES.get(regler_index, -1)
    
    if last_value != -1 and abs(filtered_value - last_value) < MIN_CHANGE_THRESHOLD:
        return False 
    
    # 2. Lautstärke-Mapping (0-100 auf 0.0-1.0)
    target_volume_scalar = filtered_value / 100.0
    
    # 3. Lautstärke setzen
    app_name = APP_MAPPING.get(regler_index)
    volume_control = get_session_volume_control(app_name)
    
    is_updated = False
    
    if volume_control:
        # Lautstärke setzen
        if app_name == "System":
            volume_control.SetMasterVolumeLevelScalar(target_volume_scalar, None)
        else:
            volume_control.SetMasterVolume(target_volume_scalar, None)
        
        # Speichern des neuen gültigen Wertes
        LAST_VOLUME_VALUES[regler_index] = filtered_value
        is_updated = True 

    # 4. Speichern des aktuellen Status für die Konsolenausgabe
    CURRENT_DISPLAY_VALUES[regler_index] = target_volume_scalar
    return is_updated

# --- HAUPTSCHLEIFE FÜR SERIELLE KOMMUNIKATION ---

def main():
    try:
        # CoInitialize muss einmal pro Thread aufgerufen werden, um COM-Objekte zu nutzen
        pythoncom.CoInitialize() 
    except Exception:
        pass

    try:
        # Initialisierung der seriellen Verbindung
        ser = sp.Serial(COM_PORT, BAUD_RATE, timeout=0.1)
    except sp.SerialException:
        print(f"FEHLER: Konnte COM-Port {COM_PORT} nicht öffnen. Prüfen Sie Anschluss und Baudrate.")
        print("Stellen Sie sicher, dass das Pico-Gerät angeschlossen ist.")
        return

    print("--- Serielle Lautstärkeregelung (5 Regler) gestartet ---")
    
    # NEU: Zähler, um die Konsolenausgabe regelmäßig zu aktualisieren, auch wenn sich die Lautstärke nicht ändert.
    display_update_counter = 0
    UPDATE_FREQUENCY = 50 # Update alle 50 Schleifendurchläufe

    while True:
        value_changed = False 
        
        try:
            # Liest eine Zeile vom seriellen Port (endet mit \r oder \n)
            line = ser.readline()
            
            if line:
                data_string = line.decode('utf-8').strip()
                
                # --- DEBUGGING: UNKOMMENTIEREN, UM ROHDATEN ZU SEHEN ---
                # if data_string:
                #    print(f"DEBUG: Rohdaten: {data_string}")
                # --------------------------------------------------------
                
                # Erwartetes Format: Zahl|Zahl|Zahl|Zahl|Zahl (z.B. 45|90|0|10|55)
                if '|' in data_string:
                    str_values = data_string.split('|')
                    
                    # PRÜFUNG: Muss mindestens so viele Werte haben wie Regler konfiguriert
                    if len(str_values) >= NUM_SLIDERS:
                        int_values = []
                        
                        # Wir verarbeiten nur die ersten NUM_SLIDERS Werte
                        for s in str_values[:NUM_SLIDERS]:
                            try:
                                # Die Werte sind bereits 0-100
                                int_values.append(int(s.strip()))
                            except ValueError:
                                # Wenn ein Wert nicht geparst werden kann, verwenden wir 0
                                int_values.append(0) 

                        if len(int_values) == NUM_SLIDERS:
                            for index, value in enumerate(int_values):
                                # Setzt die Lautstärke, gibt True zurück, wenn PyCaw es gesetzt hat
                                if set_filtered_volume(index, value):
                                    value_changed = True
            
            # NEU: Konsolenausgabe nur bei einer Änderung ODER wenn das Update fällig ist
            display_update_counter += 1
            should_update_display = value_changed or (display_update_counter >= UPDATE_FREQUENCY)

            if should_update_display:
                os.system('cls' if os.name == 'nt' else 'clear')
                print("--- Serielle Lautstärkeregelung aktiv (5 Regler) ---")
                
                for i in range(NUM_SLIDERS):
                    name = APP_MAPPING.get(i, "UNBEKANNT")
                    current_vol_perc = int(CURRENT_DISPLAY_VALUES.get(i, 0.0) * 100)
                    
                    # Zeige "KEINE ZUORDNUNG" mit 0% an
                    display_name = name if name != "KEINE ZUORDNUNG" else f"Regler {i+1} (Nicht zugeordnet)"
                    
                    print(f"Regler {i+1} ({display_name}): Lautstärke: {current_vol_perc}%")
                
                # Counter zurücksetzen, wenn aktualisiert wurde
                if display_update_counter >= UPDATE_FREQUENCY:
                    display_update_counter = 0
        
        except sp.SerialTimeoutException:
            # Kein Fehler, wenn Timeout erreicht wird, ohne Daten zu finden
            pass
        except Exception as e:
            # Allgemeine Fehlerbehandlung
            print(f"Ein unerwarteter Fehler ist aufgetreten: {e}")
            time.sleep(1)
            
    ser.close()
    try:
        pythoncom.CoUninitialize()
    except Exception:
        pass

if __name__ == "__main__":
    main()
