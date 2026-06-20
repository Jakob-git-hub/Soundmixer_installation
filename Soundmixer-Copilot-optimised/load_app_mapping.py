import csv

CONFIG_FILE = 'config.csv'
DEFAULT_MAPPING = ["System", "Spotify.exe", "firefox.exe", "discord.exe", "chrome.exe"]

def load_app_mapping(filename, NUM_SLIDERS):
    app_map = []
    
    # 1. Versuche, die Konfiguration aus der Datei zu laden
    try:
        with open(filename, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.reader(file)
            next(reader)  # Überspringe die Header-Zeile
            for row in reader:  
                try:                
                    process_name = row[1] if len(row) > 1 and row[1].strip() != "" else "NONE"
                    app_map.append(process_name)
                except (ValueError, IndexError):
                    # Ignoriere Zeilen mit ungültigem Index
                    continue
                    
            Diff = NUM_SLIDERS - len(app_map) 
            while Diff > 0: 
                app_map.append("NONE")
                Diff -= 1
            if len(app_map) > NUM_SLIDERS:
                app_map = app_map[:NUM_SLIDERS]
            return app_map
            
    except FileNotFoundError:
        defaults = DEFAULT_MAPPING[:NUM_SLIDERS]
        while len(defaults) < NUM_SLIDERS:
            defaults.append("NONE")
        return defaults

if __name__ == "__main__":
    APP_MAPPING = load_app_mapping(CONFIG_FILE, 5)
    print("Mapping geladen:", APP_MAPPING)