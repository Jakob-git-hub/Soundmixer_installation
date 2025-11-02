CONFIG_FILE = 'config.csv'
DEFAULT_MAPPING = { 0: "System", 1: "Spotify.exe", 2: "firefox.exe", 3: "discord.exe", 4: "chrome.exe" }


def load_app_mapping(filename=CONFIG_FILE):
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

APP_MAPPING = load_app_mapping() 
print(APP_MAPPING)