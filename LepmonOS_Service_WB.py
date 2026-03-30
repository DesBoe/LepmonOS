import numpy as np
from PIL import Image
import json

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
    

def extract_mask_from_log(log_path):
    """
    Extrahiert die Maske aus einer Logdatei (zwischen 'Beginn' und 'Ende').
    Gibt ein NumPy-Array zurück.
    """
    with open(log_path, "r") as f:
        lines = f.readlines()
    mask_lines = []
    in_mask = False
    for line in lines:
        if "Matrix_BW_Beginn" in line:
            in_mask = True
            continue
        if "Matrix_BW_Ende" in line and in_mask:
            break
        if in_mask:
            # Zeitstempel am Anfang entfernen, falls vorhanden (Format: HH:MM:SS; )
            parts = line.strip().split("; ", 1)
            if len(parts) == 2:
                row = parts[1]
            else:
                row = parts[0]
            mask_lines.append(row)
    if not mask_lines:
        raise ValueError("Keine Maske im Log gefunden.")
    mask = np.array([[int(val) for val in row.split()] for row in mask_lines], dtype=np.uint8)
    return mask

def show_mask_as_image(mask):
    """
    Zeigt eine Maske (0/1-Array) als Bild an.
    """
    import matplotlib.pyplot as plt
    plt.imshow(mask, cmap="gray")
    plt.title("Maskenbild aus Logdatei")
    plt.axis("off")
    plt.show()

def show_mask_from_current_log(log_dateipfad="/home/Ento/LepmonOS/Lepmon_config.json"):
    """
    Extrahiert und zeigt die Maske aus der aktuellen Logdatei laut Konfiguration.
    """
    # Prüfe, ob log_dateipfad auf .json oder .log endet
    if log_dateipfad.endswith(".json"):
        log_dateipfad = get_value_from_section(log_dateipfad, "general", "current_log")
        if not log_dateipfad:
            print("Kein Logpfad in der Konfiguration gefunden.")
            return
    elif log_dateipfad.endswith(".log"):
        pass  # log_dateipfad bleibt wie übergeben
    else:
        print("Ungültiger Dateityp für log_dateipfad.")
        return
    mask = extract_mask_from_log(log_dateipfad)
    show_mask_as_image(mask)


if __name__ == "__main__":
    log_dateipfad = '/Volumes/Dennis_OTG/LEPMON/Neuer Ordner/Neuer Ordner 2/Lepmon#SN010039_NW_BN_2026-03-24_T_1906.log'
    show_mask_from_current_log(log_dateipfad)