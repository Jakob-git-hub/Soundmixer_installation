import serial as sp
from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume, IAudioEndpointVolume
from comtypes import CLSCTX_ALL
import time, os, pythoncom

from load_app_mapping import load_app_mapping 

#Konstante Definitionen
NUM_SLIDERS = 5 
MIN_CHANGE_THRESHOLD = 2

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
           
    # Wert prüfen (erwartet 0-100 vom Pico)
    try:
        filtered_value = int(new_input_value)
    except ValueError:
        return False # Ungültiger Wert
    #Skalierung auf 0.0 - 1.0
    target_volume_scalar = (max(0, min(100, filtered_value)) / 100.0)

    # 1. Filterung kleiner Änderungen (Debouncing)
    last_value = CURRENT_DISPLAY_VALUES[regler_index]
    if last_value != 0.0 and abs(target_volume_scalar - last_value) < MIN_CHANGE_THRESHOLD:
        return False 
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
        CURRENT_DISPLAY_VALUES[regler_index] = filtered_value
        is_updated = True 
    else:
        # Kein Lautstärke-Steuerelement gefunden
        pass
        is_updated = False
    # 4. Speichern des aktuellen Status für die Konsolenausgabe
    CURRENT_DISPLAY_VALUES[regler_index] = target_volume_scalar
    return is_updated


# --- HAUPTSCHLEIFE FÜR SERIELLE KOMMUNIKATION ---

def main(): 
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

    
    CURRENT_DISPLAY_VALUES = [0.0 for i in range(NUM_SLIDERS)]
    # Initialisiert 5 Einträge
    try:
        while True:
            value_changed = False 
            APP_MAPPING = load_app_mapping(CONFIG_FILE, NUM_SLIDERS)
            try:
            # Liest eine Zeile vom seriellen Port (endet mit \r oder \n)
                line = ser.readline()
                #Einlesen und Verarbeiten der Lautstärkedaten
                if line:
                    data_string = line.decode('utf-8').strip()

                    if '|' in data_string:
                        str_values = data_string.split('|')
                        value_list=[]
                        for s in str_values:
                            value_list.append(int(s))
                        #Ändert die Lautstärke nur, wenn alle 5 Reglerwerte empfangen wurden
                        if len(value_list) == NUM_SLIDERS: 
                            for regler_index, value in enumerate(value_list):
                                if APP_MAPPING[regler_index] != "Nicht zugeordnet":
                                # Setzt die Lautstärke, gibt True zurück, wenn PyCaw es gesetzt hat
                                    if set_filtered_volume(regler_index, value, APP_MAPPING, CURRENT_DISPLAY_VALUES):
                                        value_changed = True

            # Aktualisiere die Konsolenausgabe nur bei value_changed = TRUE
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