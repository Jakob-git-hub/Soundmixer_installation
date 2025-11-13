from binascii import Error
import serial as sp
from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume, IAudioEndpointVolume
from comtypes import CLSCTX_ALL
import time, os, pythoncom

from load_app_mapping import load_app_mapping 

#Konstante Definitionen
NUM_SLIDERS = 5 
MIN_CHANGE_THRESHOLD = 0.02  # Minimale Änderungsschwelle (2%)

def get_session_volume_control(process_name):
    """Gibt das Lautstärke-Steuerelement für den Prozess zurück.
    Für 'System' -> IAudioEndpointVolume, für Prozesse -> Liste von ISimpleAudioVolume (evtl. mehrere Sessions)."""
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
    controls = []
    for session in sessions:
        if session.Process and session.Process.name() == process_name:
            try:
                controls.append(session._ctl.QueryInterface(ISimpleAudioVolume))
            except Exception:
                continue
    return controls if controls else None

def set_filtered_volume(regler_index, new_input_value, APP_MAPPING, CURRENT_DISPLAY_VALUES):
    """Setzt die Lautstärke unter Berücksichtigung von Debouncing und Skalierung."""

    try:
        target_volume_scalar = float(new_input_value)
    except ValueError:
        return False # Ungültiger Wert
 
    app_name = APP_MAPPING[regler_index]
    volume_control = get_session_volume_control(app_name)
    
    Allright = True
    if volume_control:
        # Lautstärke setzen
        try:
            if app_name == "System":
                # Single endpoint interface
                volume_control.SetMasterVolumeLevelScalar(target_volume_scalar, None)
                is_updated = True
            else:
                # Für Prozesse: volume_control kann eine Liste von Session-Interfaces sein
                if isinstance(volume_control, list):
                    for ctl in volume_control:
                        try:
                            ctl.SetMasterVolume(target_volume_scalar, None)
                        except Exception:
                            # einzelne Session fehlgeschlagen -> weiter zu nächsten
                            continue
                else:
                    # Falls aus irgendeinem Grund ein einzelnes Interface zurückkam
                    volume_control.SetMasterVolume(target_volume_scalar, None)         
            active = True        
        except Exception:
           Allright = False
    else:
        pass 
        active = False
    # 4. Speichern des aktuellen Status für die Konsolenausgabe
    CURRENT_DISPLAY_VALUES[regler_index] = target_volume_scalar
    return active, Allright

# --- HAUPTSCHLEIFE FÜR SERIELLE KOMMUNIKATION ---

def main(): 
    CONFIG_FILE = 'config.csv'
    Sessions_active = [False for _ in range(NUM_SLIDERS)]
    COM_PORT = 'COM9'
    BAUD_RATE = 115200
    value_changed = []
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
            value_changed = [] 
            APP_MAPPING = load_app_mapping(CONFIG_FILE, NUM_SLIDERS)
            try:
            # Liest eine Zeile vom seriellen Port (endet mit \r oder \n)
                line = ser.readline()
                #Einlesen und Verarbeiten der Lautstärkedaten
                if line:
                    data_string = line.decode('utf-8', errors='ignore').strip()

                    if '|' in data_string:
                        str_values = [s.strip() for s in data_string.split('|')]

                        value_list=[]
                        for s in str_values:
                            value_list.append(int(s))
                        #Ändert die Lautstärke nur, wenn alle 5 Reglerwerte empfangen wurden
                        if len(value_list) == NUM_SLIDERS: 
                            for index, value in enumerate(value_list):
                                value = (max(0, min(100, value)) / 100.0)
                                if CURRENT_DISPLAY_VALUES[index] != 0.0 and abs(value - CURRENT_DISPLAY_VALUES[index]) < MIN_CHANGE_THRESHOLD:
                                    value_changed.append(True)
                                    Sessions_active[index], value_changed = set_filtered_volume(index, value, APP_MAPPING, CURRENT_DISPLAY_VALUES, Sessions_active[index])                
                        else:
                            print("WARNUNG: NUM_SLIDERS stimmt nicht mit empfangenen Werten überein.")
                            break

            # Aktualisiere die Konsolenausgabe nur bei value_changed = TRUE
                if value_changed:
                    os.system('cls' if os.name == 'nt' else 'clear')
                    print("--- Serielle Lautstärkeregelung aktiv (5 Regler) ---")
                    for i in range(NUM_SLIDERS):
                        name = APP_MAPPING[i]
                        current_vol_perc = int(CURRENT_DISPLAY_VALUES[i] * 100)
                        print(f"Regler {i+1} ({name}): Lautstärke: {current_vol_perc}%{" [AKTIV]" if Sessions_active[i] else ""}")

            except sp.SerialTimeoutException:
            # Kein Fehler, wenn Timeout erreicht wird, ohne Daten zu finden
                pass
            #except Exception as e:
            # Allgemeine Fehlerbehandlung
                #print(f"Ein unerwarteter Fehler ist aufgetreten: {e}")
                #time.sleep(1)
    except KeyboardInterrupt:        
        ser.close()
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass
    
if __name__ == "__main__":
    main()