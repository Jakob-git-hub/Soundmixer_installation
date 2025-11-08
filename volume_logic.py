import serial as sp
import pythoncom
from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume, IAudioEndpointVolume
from comtypes import CLSCTX_ALL
import time
import os
import csv

from load_app_mapping import load_app_mapping 

# --- KONFIGURATION ---
 

NUM_SLIDERS = 5 

MIN_CHANGE_THRESHOLD = 2

#CONFIG_FILE = 'config.csv'

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

def set_filtered_volume(regler_index, new_input_value, APP_MAPPING, CURRENT_DISPLAY_VALUES):
    """Setzt die Lautstärke unter Berücksichtigung von Debouncing und Skalierung."""
    LAST_VOLUME_VALUES = []       
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
    app_name = APP_MAPPING[regler_index]
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
    NUM_SLIDERS = 5 
    CONFIG_FILE = 'config.csv'
    
    COM_PORT = 'COM9'
    BAUD_RATE = 115200
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

    LAST_VOLUME_VALUES = []       # Speichert den zuletzt gesetzten Prozentwert (0-100)
    CURRENT_DISPLAY_VALUES = [0.0 for i in range(NUM_SLIDERS)]
    # Initialisiert 5 Einträge
    try:
        while True:
            value_changed = False 
            APP_MAPPING = load_app_mapping(CONFIG_FILE, NUM_SLIDERS)
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
                            i = 0
                            for value in value_list:

                                # Setzt die Lautstärke, gibt True zurück, wenn PyCaw es gesetzt hat
                                if set_filtered_volume(i,value, APP_MAPPING, CURRENT_DISPLAY_VALUES):
                                    value_changed = True
                                i += 1    
            # Aktualisiere die Konsolenausgabe nur bei value_changed = TRUE Schleifendurchläufe
                if value_changed:
                    os.system('cls' if os.name == 'nt' else 'clear')
                    print("--- Serielle Lautstärkeregelung aktiv (5 Regler) ---")
                
                    for i in range(NUM_SLIDERS):
                        name = APP_MAPPING[i]
                        current_vol_perc = int(CURRENT_DISPLAY_VALUES[i] * 100)

                        print(f"Regler {i+1} ({name}): Lautstärke: {current_vol_perc}%")

            except sp.SerialTimeoutException:
            # Kein Fehler, wenn Timeout erreicht wird, ohne Daten zu finden
                pass
            except Exception as e:
            # Allgemeine Fehlerbehandlung
                print(f"Ein unerwarteter Fehler ist aufgetreten: {e}")
                time.sleep(1)
    except KeyboardInterrupt:        
        ser.close()
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass
    
if __name__ == "__main__":
    main()