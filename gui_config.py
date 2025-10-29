import customtkinter as ctk # Import für modernes Design
from tkinter import messagebox
import psutil 
import csv
import subprocess
import os
import sys
import winreg # Für das Auslesen installierter Windows-Programme

# --- KONSTANTEN ---
CONFIG_FILE = 'config.csv'
NUM_SLIDERS = 5
DEFAULT_MAPPING = {0: "System", 1: "Spotify.exe", 2: "firefox.exe", 3: "discord.exe", 4: "chrome.exe"}

# --- HILFSFUNKTIONEN FÜR PYINSTALLER ---

def resource_path(relative_path):
    """Gibt den korrekten Pfad zu einer Ressource zurück, 
    unabhängig davon, ob das Skript normal oder als EXE läuft."""
    try:
        # Pfad, wenn es als PyInstaller-Bundle läuft
        base_path = sys._MEIPASS
    except Exception:
        # Normaler Skriptmodus
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)

# --- DATENERFASSUNG: ERWEITERTE APP-LISTE ---

# get_running_apps() wurde entfernt, da laufende Prozesse nicht mehr gewünscht sind.

def get_installed_programs():
    """Versucht, Programme aus der Windows-Registrierung auszulesen."""
    programs = set()
    
    # Pfade in der Registry, wo deinstallierbare Programme gelistet sind
    reg_paths = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"
    ]
    
    # Versuche 32-Bit und 64-Bit Registry-Zugriff
    for path in reg_paths:
        try:
            # Öffne den Reg-Key
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_READ)
            
            for i in range(winreg.QueryInfoKey(key)[0]):
                try:
                    # Unterordner-Name (z.B. der GUID-Name)
                    subkey_name = winreg.EnumKey(key, i)
                    subkey = winreg.OpenKey(key, subkey_name)
                    
                    # Versuche, den DisplayName zu lesen (den Anzeigenamen des Programms)
                    display_name = None
                    try:
                        display_name, _ = winreg.QueryValueEx(subkey, "DisplayName")
                    except FileNotFoundError:
                        pass
                    
                    # Versuche, den UninstallString zu lesen, um den EXE-Namen zu extrahieren
                    exe_name = None
                    try:
                        uninstall_string, _ = winreg.QueryValueEx(subkey, "UninstallString")
                        # Vereinfachte Annahme: Wir suchen nur den .exe Namen, wenn möglich.
                        if "\\" in uninstall_string:
                            # Extrahiert den Pfad und dann den Dateinamen
                            path_part = uninstall_string.split('"')[1] if '"' in uninstall_string else uninstall_string
                            exe_name = os.path.basename(path_part)
                            if exe_name.lower().endswith(".exe"):
                                programs.add(exe_name) # Fügen den EXE-Namen hinzu
                    except Exception:
                        pass
                        
                    # Füge den Anzeigenamen hinzu, da er besser lesbar ist
                    if display_name and display_name.strip() and display_name not in programs:
                         programs.add(display_name)
                         
                    winreg.CloseKey(subkey)
                except Exception:
                    continue
            winreg.CloseKey(key)
        except Exception:
            # Registry-Pfad nicht gefunden oder Fehler beim Zugriff
            continue

    return programs

def get_steam_games():
    """Listet installierte Steam-Spiele basierend auf gängigen Pfaden auf."""
    steam_games = set()
    
    # Gängige Steam-Installationspfade (kann variieren!)
    steam_path = os.path.join(os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)'), 'Steam')
    library_path = os.path.join(steam_path, 'steamapps', 'common')
    
    if os.path.exists(library_path):
        # Geht durch die Unterordner in 'steamapps/common'
        for folder_name in os.listdir(library_path):
            full_path = os.path.join(library_path, folder_name)
            if os.path.isdir(full_path):
                # Fügt den Ordnernamen als Spielnamen hinzu (z.B. 'Cyberpunk 2077')
                steam_games.add(folder_name)
                
    return steam_games

def get_all_available_apps():
    """Kombiniert alle Quellen (Installiert, Steam, Spezielle) zu einer Master-Liste."""
    
    # Spezielle Einträge
    master_list = ["System", "KEINE ZUORDNUNG"]
    
    # 1. Installierte Programme (Display Name und EXE-Name)
    installed = get_installed_programs()
    
    # 2. Steam-Spiele (als lesbare Namen)
    steam = get_steam_games()
    
    # Fügt alle eindeutigen Programme hinzu
    all_apps = installed.union(steam)
    
    # Sortiert und entfernt leere Einträge
    sorted_apps = sorted([app for app in all_apps if app.strip()])
    
    master_list.extend(sorted_apps)
    return master_list

# --- KLASSE FÜR DIE GUI ---

class VolumeMixerGUI:
    def __init__(self, master):
        self.master = master
        master.title("Serieller Volume Mixer Konfiguration")
        
        # CTk-Erscheinungsbild festlegen
        ctk.set_appearance_mode("Dark")  # Kann "Light", "Dark" oder "System" sein
        ctk.set_default_color_theme("blue") 
        
        # Lade Mapping und erstelle verfügbare App-Liste
        self.current_mapping = self.load_mapping_from_file()
        self.selected_processes = {}
        
        # Die Liste enthält jetzt KEINE laufenden Prozesse mehr
        self.available_processes = get_all_available_apps()

        self.create_widgets()
        self.set_initial_values()

    def load_mapping_from_file(self):
        """Läd die letzte Zuordnung aus der CSV-Datei."""
        app_map = {}
        try:
            # Nutzt resource_path, um die Datei zu finden
            with open(resource_path(CONFIG_FILE), mode='r', newline='', encoding='utf-8') as file:
                reader = csv.reader(file)
                next(reader)
                for row in reader:
                    if len(row) == 2:
                        app_map[int(row[0])] = row[1]
        except FileNotFoundError:
            app_map = DEFAULT_MAPPING
        except Exception as e:
            # Fehler beim Lesen der CSV
            print(f"Fehler beim Laden der Konfiguration: {e}")
            app_map = DEFAULT_MAPPING
            
        return app_map

    def save_mapping_to_file(self):
        """Speichert die aktuelle Zuordnung in der CSV-Datei."""
        new_mapping = []
        for i in range(NUM_SLIDERS):
            process_name = self.selected_processes[i].get()
            
            # 'KEINE ZUORDNUNG' wird als leeres Feld in der CSV gespeichert
            if process_name == "KEINE ZUORDNUNG":
                 process_name = ""
            
            new_mapping.append([i, process_name])

        try:
            # Nutzt resource_path, um die Datei zu speichern
            with open(resource_path(CONFIG_FILE), mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(["Regler_Index", "Prozess_Name"])
                writer.writerows(new_mapping)
            messagebox.showinfo("Speichern erfolgreich", "Die Konfiguration wurde gespeichert. Starten Sie das Logik-Skript neu.")
            return True
        except Exception as e:
            messagebox.showerror("Fehler beim Speichern", f"Fehler beim Speichern der Datei: {e}")
            return False

    def set_initial_values(self):
        """Setzt die Dropdowns auf die zuletzt gespeicherten Werte. 
        Bestätigt, dass der in config.csv gespeicherte Wert beim Start angezeigt wird."""
        
        for i in range(NUM_SLIDERS):
            # Holt den gespeicherten Prozessnamen (z.B. 'Spotify.exe' oder '')
            saved_app = self.current_mapping.get(i, "")
            
            # Wenn der Wert leer ist, soll 'KEINE ZUORDNUNG' angezeigt werden
            if saved_app == "":
                display_value = "KEINE ZUORDNUNG"
            else:
                # Prüft, ob der gespeicherte Wert in der neuen Master-Liste ist.
                # WICHTIG: Wenn der gespeicherte Wert NICHT in der aktuellen Liste
                # der verfügbaren Apps ist (weil es z.B. ein alter, nicht mehr existierender 
                # Prozessname war), wird er auf "KEINE ZUORDNUNG" zurückgesetzt.
                if saved_app in self.available_processes:
                    display_value = saved_app
                else:
                    # Falls der gespeicherte Wert ungültig ist, muss er trotzdem angezeigt werden,
                    # um dem Benutzer zu zeigen, was gespeichert war.
                    # CTkComboBox kann aber nur Werte aus der 'values'-Liste anzeigen.
                    # Wir setzen ihn daher auf den gespeicherten Wert, wenn er nicht None ist,
                    # und hoffen, dass CTk dies intern zulässt, oder setzen auf 'KEINE ZUORDNUNG'.
                    
                    # Da CTkComboBox streng ist, müssen wir auf 'KEINE ZUORDNUNG' zurückfallen.
                    display_value = "KEINE ZUORDNUNG" 
            
            # Setzt den Wert im Dropdown (sichtbar für den Benutzer)
            self.selected_processes[i].set(display_value)
            
    def create_widgets(self):
        """Erstellt die GUI-Elemente im CustomTkinter-Stil."""
        
        # Rahmen für Inhalt
        main_frame = ctk.CTkFrame(self.master, padding=20)
        main_frame.pack(padx=20, pady=20, fill="both", expand=True)

        # Titel (CTkLabel)
        ctk.CTkLabel(main_frame, text="Serieller Volume Mixer Zuordnung", 
                     font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # Erstelle Dropdowns für jeden Regler (5 Stück)
        for i in range(NUM_SLIDERS):
            
            # Label
            ctk.CTkLabel(main_frame, text=f"Regler {i+1} zuordnen:").grid(row=i + 1, column=0, padx=10, pady=10, sticky='w')
            
            # String-Variable für das Dropdown
            self.selected_processes[i] = ctk.StringVar(main_frame)
            
            # Dropdown-Menü (CTkComboBox)
            combobox = ctk.CTkComboBox(main_frame, 
                                    variable=self.selected_processes[i], 
                                    values=self.available_processes,
                                    width=350,
                                    state="readonly")
            combobox.grid(row=i + 1, column=1, padx=10, pady=10, sticky='ew')
            
        # Platzhalter für Trennlinie
        ctk.CTkFrame(main_frame, height=2, fg_color="gray50").grid(row=NUM_SLIDERS + 1, columnspan=2, sticky='ew', pady=(15, 15))

        # Buttons
        ctk.CTkButton(main_frame, text="Konfiguration speichern", command=self.save_mapping_to_file,
                      fg_color="#3B82F6", hover_color="#2563EB").grid(row=NUM_SLIDERS + 2, column=0, columnspan=2, pady=(10, 5), sticky='ew', padx=10)
        
        ctk.CTkButton(main_frame, text="Logik-Skript starten", command=self.start_logic_script,
                      fg_color="#10B981", hover_color="#059669").grid(row=NUM_SLIDERS + 3, column=0, columnspan=2, pady=(5, 10), sticky='ew', padx=10)
        
        # Info-Feld
        ctk.CTkLabel(main_frame, text="Hinweis: Die App-Liste umfasst installierte Apps und Steam-Spiele (keine laufenden Prozesse).", 
                     wraplength=450, text_color="gray70").grid(row=NUM_SLIDERS + 4, column=0, columnspan=2, pady=(10, 0))


    def start_logic_script(self):
        """Versucht, das volume_logic.py Skript auszuführen."""
        
        # 1. Konfiguration speichern (obligatorisch)
        if not self.save_mapping_to_file():
             return

        # 2. Skript im Hintergrund starten (verwendet den gebündelten Interpreter)
        try:
            # Statt os.path.join verwenden wir resource_path
            script_path = resource_path("volume_logic.py")
            
            # Im gebündelten Zustand ist sys.executable die .exe selbst!
            subprocess.Popen([sys.executable, script_path]) 
            
            messagebox.showinfo("Skript gestartet", "Das Volume-Logik-Skript wurde im Hintergrund gestartet.")
        except FileNotFoundError:
            messagebox.showerror("Fehler", "Das Skript 'volume_logic.py' wurde nicht gefunden. Fehler bei der Pfadbestimmung.")
        except Exception as e:
            messagebox.showerror("Fehler beim Start", f"Fehler beim Starten des Python-Skripts: {e}")

if __name__ == '__main__':
    root = ctk.CTk()
    # Legt die minimale Größe des Fensters fest, um es nicht zu klein zu machen
    root.geometry("500x550") 
    root.resizable(False, False) # Größe fixieren
    app = VolumeMixerGUI(root)
    root.mainloop()

