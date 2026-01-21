from pathlib import Path
from PIL import Image

def finde_defekte_bilder(ordnerpfad: str) -> list[str]:
    """
    Prüft alle Bilddateien in einem Ordner auf Lesbarkeit und gibt
    eine Liste mit den fehlerhaften Bildpfaden zurück.
    """
    ordner = Path(ordnerpfad)
    fehlerhafte_bilder = []

    # gängige Bild-Endungen anpassen/erweitern
    endungen = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}

    for datei in ordner.iterdir():
        if datei.suffix.lower() in endungen:
            try:
                with Image.open(datei) as img:
                    img.verify()  # prüft Integrität ohne vollständiges Laden
            except Exception as e:
                # Bei Fehler: Dateiname merken
                fehlerhafte_bilder.append(str(datei))
                print(f"Fehler bei {datei.name}: {e}")

    return fehlerhafte_bilder

# --- Beispielaufruf ---
if __name__ == "__main__":
    ordner= input("Pfad zu einem Ordner mit Bildern auf dem Raspberry oder angeschlossenem Stick eingeben:")
    kaputt = finde_defekte_bilder(ordner)
    if kaputt:
        print("Defekte oder unvollständige Bilder gefunden:")
        for k in kaputt:
            print(" -", k)
    else:
        print("Alle Bilder sind in Ordnung.")
