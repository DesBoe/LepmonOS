import numpy as np
from PIL import Image
from OLED_panel import *
from Camera_AV import *
from json_read_write import *

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
    log_dateipfad = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","general","current_log")
    if not log_dateipfad:
        print("Kein Logpfad in der Konfiguration gefunden.")
        return
    mask = extract_mask_from_log(log_dateipfad)
    show_mask_as_image(mask)


if __name__ == "__main__":
    log_dateipfad = "/home/Ento/LepmonOS/Lepmon_config.json"
    show_mask_from_current_log(log_dateipfad)