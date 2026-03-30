import cv2
import numpy as np
import sys
import os

def gamma_correction(image_path, gamma):
    # Bild einlesen
    frame = cv2.imread(image_path)
    if frame is None:
        print(f"Fehler: Bild {image_path} konnte nicht geladen werden.")
        return
    # Gamma-Korrektur anwenden
    frame = frame / 255.0
    frame = np.power(frame, 1 / gamma)
    frame = (frame * 255).astype(np.uint8)
    # Neuen Dateinamen erzeugen
    base, ext = os.path.splitext(image_path)
    out_path = f"{base}_GammaKorr_{gamma}{ext}"
    # Bild speichern
    cv2.imwrite(out_path, frame)
    print(f"Bild gespeichert als {out_path}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Verwendung: python gamma_korr.py <bilddatei> <gamma>")
        sys.exit(1)
    image_path = sys.argv[1]
    gamma = float(sys.argv[2])
    gamma_correction(image_path, gamma)
