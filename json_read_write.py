import json
from fram_direct import read_fram


def get_value_from_section(file_path, section_name, key_name):
    try:
        # JSON-Datei öffnen und laden
        with open(file_path, "r") as json_file:
            data = json.load(json_file)
        
        # Prüfen, ob die Sektion existiert
        if section_name in data:
            section = data[section_name]
            # Prüfen, ob der Schlüssel in der Sektion existiert
            if key_name in section:
                return section[key_name]  # Wert des Schlüssels zurückgeben
            else:
                return f"Der Schlüssel '{key_name}' existiert nicht in der Sektion '{section_name}'."
        else:
            return f"Die Sektion '{section_name}' existiert nicht in der Datei."
    except FileNotFoundError:
        return f"Die Datei {file_path} wurde nicht gefunden."
    except json.JSONDecodeError as e:
        return f"Fehler beim Parsen der JSON-Datei: {e}"
    except Exception as e:
        return f"Fehler: {e}"

def get_coordinates():
    try:
        try:
            lat_raw = read_fram(0x03C0, 16)
            lon_raw = read_fram(0x03E0, 16)
        except Exception as fram_error:
            raise IOError(f"Fehler beim Lesen von FRAM: {fram_error}")

        lat_str = lat_raw.replace('\x00', '').strip()
        lon_str = lon_raw.replace('\x00', '').strip()


        # Prüfen auf leere oder ungültige Werte
        if not lat_str or not lon_str:
            raise ValueError("Latitude oder Longitude im FRAM leer!")

        try:
            latitude = float(lat_str)
            longitude = float(lon_str)
        except ValueError:
            raise ValueError("Latitude oder Longitude ist keine gültige Zahl!")

        Pol = read_fram(0x03D0, 1).replace('\x00', '').strip()
        Block = read_fram(0x03F0, 1).replace('\x00', '').strip()

    except Exception as e:
        print(f"Fehler beim Lesen der Koordinaten aus dem FRAM: {e}. Verwende Konfigurationsdatei.")
        latitude = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "GPS", "latitude")
        longitude = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "GPS", "longitude")
        Pol = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "GPS", "Pol")
        Block = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "GPS", "Block")

    # Pol- und Blockzeichen auswerten
    if Pol == "N":
        Pol = ""
    elif Pol == "S":
        Pol = "-"

    if Block == "E":
        Block = ""
    elif Block == "W":
        Block = "-"
        
    latitude_ohne_Vorzeichen = latitude
    longitude_ohne_Vorzeichen = longitude    
    latitude = float(Pol + str(latitude))
    longitude = float(Block + str(longitude))

    return latitude, longitude, Pol, Block, latitude_ohne_Vorzeichen, longitude_ohne_Vorzeichen


def write_value_to_section(file_path, section_name, key_name, value):
    try:
        # JSON-Datei laden oder erstellen, falls sie nicht existiert
        try:
            with open(file_path, "r") as json_file:
                data = json.load(json_file)
        except FileNotFoundError:
            data = {}  # Leeres Dictionary, falls die Datei nicht existiert

        # Sicherstellen, dass die Sektion existiert
        if section_name not in data:
            data[section_name] = {}

        # Wert in der Sektion setzen
        data[section_name][key_name] = value

        # JSON-Datei speichern
        with open(file_path, "w") as json_file:
            json.dump(data, json_file, indent=4)

        return f"Wert '{value}' erfolgreich in Sektion '{section_name}' unter Schlüssel '{key_name}' geschrieben."
    except json.JSONDecodeError as e:
        return f"Fehler beim Parsen der JSON-Datei: {e}"
    except Exception as e:
        return f"Ein unerwarteter Fehler ist aufgetreten: {e}"
     


if __name__ == "__main__":
    print("Funktionen, um die Konfigurationsdatei zu lesen und Einträge zu verändern")
    latitude, longitude, Pol, Block,_,_ = get_coordinates()
    print(f"Koordinaten abgefragt:\n{Pol}{latitude},\n{Block}{longitude}")
    