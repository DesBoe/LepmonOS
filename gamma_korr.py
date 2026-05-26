import cv2
import numpy as np
import sys
import os
import gc

def gamma_correction(input, gamma = 1):
    if gamma <= 0:
        print("Fehler bei der Gamma Korrektur: Gamma-Wert muss größer als 0 sein.")
        return input
    
    frame = None
    mode = None
    if isinstance(input, str):
        frame = cv2.imread(input)
        mode = "path"
    elif isinstance(input, np.ndarray):
        image_path = None
        mode = "array"
        frame = input
    else:
        print("Fehler bei der Gamma Korrektur: Ungültiger Eingabetyp. Bitte geben Sie einen Bildpfad oder ein Bildarray an.")
        return
    
    if frame is None:
        print(f"Fehler: Bild {image_path} konnte nicht geladen werden.")
        return
    

    height = frame.shape[0]
    print(f"Teile Frame mit {height} Pixeln in 3 Teile auf für Gamma Korrektur, um Speicherprobleme zu vermeiden...")
    
    split1 = height // 3
    split2 = 2 * height // 3
                
    teile = [frame[:split1], frame[split1:split2], frame[split2:]]
    del frame

    bearbeitet = []
    for i, teil in enumerate(teile):
        print(f"korrigiere frame Teil {i+1}", flush=True)
        teil = teil / 255.0
        teil = np.power(teil, gamma)
        teil = (teil * 255).astype(np.uint8)
        bearbeitet.append(teil)
        del teil
        gc.collect()
    frame = np.vstack(bearbeitet)
    del bearbeitet
    gc.collect()
    print("Belichtungsoptimierung: Gamma Korrektur vollständig angewendet", flush=True)  

    if mode == "array":
        print("Gebe korrigiertes Bildarray zurück")
        return frame
    
    if mode == "path":
        try:
            # Neuen Dateinamen erzeugen
            base, ext = os.path.splitext(image_path)
            out_path = f"{base}_GammaKorr_{gamma}{ext}"
            # Bild speichern
            cv2.imwrite(out_path, frame)
            print(f"Bild gespeichert als {out_path}")
        except Exception as e:
            print(f"Fehler beim Speichern des Bildes: {e}")
            return frame

if __name__ == "__main__":
    image_path = "test_image.jpg"  # Pfad zum Eingabebild
    gamma = 0.9  # Beispiel-Gamma-Wert

    gamma_correction(image_path, gamma)
