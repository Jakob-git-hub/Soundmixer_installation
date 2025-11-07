import serial as sp
import pythoncom
from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume, IAudioEndpointVolume
from comtypes import CLSCTX_ALL
import time
import os
import csv

from load_app_mapping import load_app_mapping 

# --- KONFIGURATION ---
COM_PORT = 'COM9'
BAUD_RATE = 115200 

NUM_SLIDERS = 5 

MIN_CHANGE_THRESHOLD = 2

CONFIG_FILE = 'config.csv'
DEFAULT_MAPPING = ["System", "Spotify.exe", "firefox.exe", "discord.exe", "chrome.exe"]

# Globale Variablen zur Statusverwaltung
LAST_VOLUME_VALUES = {}       # Speichert den zuletzt gesetzten Prozentwert (0-100)
CURRENT_DISPLAY_VALUES = {i: 0.0 for i in range(NUM_SLIDERS)} # Initialisiert 5 Einträge

# --- KONFIGURATION LADEN ---

def load_app_mapping_not_used(filename=CONFIG_FILE):
    app_map = {}
    
    # 1. Versuche, die Konfiguration aus der Datei zu laden
    try:
        with open(filename, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.reader(file)
            next(reader)  # Überspringe die Header-Zeile
            for row in reader:  
                try:                
                    process_name = row[1] if row[1].strip() != "" else "NONE"
                    app_map.append = process_name
                except ValueError:
                    # Ignoriere Zeilen mit ungültigem Index
                    continue
                    
            NUM_SLIDERS - len(app_map) = Diff
            while Diff > 0: 
                app_map.append("NONE")
                
            return app_map
            
    except FileNotFoundError:
        return DEFAULT_MAPPING

APP_MAPPING = load_app_mapping(CONFIG_FILE, NUM_SLIDERS)

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

    if process_name == "NONE":
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

def COM_Setup():
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
    


# --- HAUPTSCHLEIFE FÜR SERIELLE KOMMUNIKATION ---

def main():
    

    NUM_SLIDERS = 5 

    MIN_CHANGE_THRESHOLD = 2

    CONFIG_FILE = 'config.csv'
    
    COM_Setup()
    
    
    display_update_counter = 0
    UPDATE_FREQUENCY = 50 # Update alle 50 Schleifendurchläufe

    while True:
        value_changed = False 
        
        try:
            # Liest eine Zeile vom seriellen Port (endet mit \r oder \n)
            line = ser.readline()
            
            if line:
                data_string = line.decode('utf-8').strip()
                
                if '|' in data_string:
                    str_values = data_string.split('|')
                    value_list=[]
                    for s in str_values:
                        value_list.append(int(s))

                    if len(value_list) == NUM_SLIDERS:
                        for value in value_list:
                            # Setzt die Lautstärke, gibt True zurück, wenn PyCaw es gesetzt hat
                            if set_filtered_volume(value):
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
