"""
flatfield.py - Flatfield-/Shading-Korrektur fuer die Lepmon-Insektenfalle.

Idee:
  Ein einmal aufgenommenes Weissbild (homogener Schirm) wird zu einem glatten
  2D-Helligkeitsmodell ('flat') verarbeitet. Jeder spaeter aufgenommene Frame
  wird durch dieses Modell geteilt -> gleichmaessig ausgeleuchteter Hintergrund.

Entwurf fuer den Einsatz in Camera_AV.py:
  - Das Flatfield wird EINMAL beim Programmstart aus einer PNG/NPY-Datei geladen
    und im Speicher gehalten (load_flatfield / FlatfieldCorrector).
  - correct(frame) wird direkt nach cam.get_frame() aufgerufen.
  - Schlaegt irgendetwas fehl, wird der unveraenderte Frame zurueckgegeben.
    Die naechtliche Aufnahme darf NIE an der Korrektur scheitern.

Voraussetzung fuer die einfache Division ohne Schrauben-Registrierung:
  Der korrigierte Frame muss dieselbe Pixelgeometrie haben wie das Weissbild,
  aus dem das Flat erzeugt wurde. Solange die Korrektur auf dem rohen,
  unbeschnittenen Kameraframe laeuft, ist das automatisch erfuellt.
"""

import os
from pathlib import Path
import numpy as np
from serial_list import get_generation_by_serial
import re

try:
    import cv2
    _HAS_CV2 = True
except Exception:
    _HAS_CV2 = False


# ----------------------------------------------------------------------
# 1) Flatfield-Modell aus einem Weissbild ERZEUGEN (einmalig, offline)
# ----------------------------------------------------------------------

def _poly_design(x, y, order):
    """Entwurfsmatrix fuer ein 2D-Polynom bis Grad `order`."""
    cols = []
    for i in range(order + 1):
        for j in range(order + 1 - i):
            cols.append((x ** i) * (y ** j))
    return np.column_stack(cols)


def build_flatfield_from_white(white_bgr, poly_order=4):
    """
    Erzeugt aus einem Weissbild (BGR uint8) ein glattes Flatfield-Modell.

    Rueckgabe:
        flat : float32-Array (H, W), Mittelwert ~1.0 ueber den gueltigen Bereich.

    Die granulare Schirmstruktur und die dunklen Eckschrauben werden ausmaskiert,
    sodass nur der niederfrequente Helligkeitsverlauf modelliert wird.
    """
    if white_bgr.ndim == 3:
        gray = cv2.cvtColor(white_bgr, cv2.COLOR_BGR2GRAY) if _HAS_CV2 \
            else white_bgr.mean(axis=2)
    else:
        gray = white_bgr
    gray = gray.astype(np.float32) / 255.0
    h, w = gray.shape

    # Maske: heller Schirm = gueltig, dunkle Schrauben/Rahmen = raus
    bg = float(np.median(gray))
    mask = gray > (bg * 0.6)
    if _HAS_CV2:
        k = np.ones((21, 21), np.uint8)
        mask = cv2.erode(mask.astype(np.uint8), k).astype(bool)

    # 2D-Polynomanpassung auf normierten Koordinaten [-1, 1]
    xs = np.linspace(-1, 1, w, dtype=np.float32)
    ys = np.linspace(-1, 1, h, dtype=np.float32)
    X, Y = np.meshgrid(xs, ys)

    A_fit = _poly_design(X[mask], Y[mask], poly_order)
    coeffs, *_ = np.linalg.lstsq(A_fit, gray[mask], rcond=None)

    A_all = _poly_design(X.ravel(), Y.ravel(), poly_order)
    flat = (A_all @ coeffs).reshape(h, w).astype(np.float32)

    # Auf Mittelwert 1 normieren (nur ueber gueltige Pixel)
    flat /= float(flat[mask].mean())
    # Sicherheitsgrenzen, damit spaeter keine Division durch ~0 passiert
    flat = np.clip(flat, 0.05, 20.0)
    return flat


def save_flatfield(flat, path):
    """
    Speichert das Flat. Endung entscheidet ueber das Format:
      .npy            -> exakt (float32), empfohlen fuer die Pipeline
      .png/.tif       -> als 16-bit Graustufen (Wert 1.0 -> 32768)
    """
    ext = os.path.splitext(path)[1].lower()
    if ext == ".npy":
        np.save(path, flat.astype(np.float32))
    elif ext in (".png", ".tif", ".tiff"):
        if not _HAS_CV2:
            raise RuntimeError("cv2 noetig fuer PNG/TIF-Export")
        img16 = np.clip(flat * 32768.0, 0, 65535).astype(np.uint16)
        cv2.imwrite(path, img16)
    else:
        raise ValueError(f"Unbekannte Endung: {ext}")


def load_flatfield(path):
    """
    Laedt ein Flat. Komplement zu save_flatfield.
    Gibt float32 (H, W), Mittelwert ~1, zurueck - oder None bei Fehler.
    """
    try:
        ext = os.path.splitext(path)[1].lower()
        if ext == ".npy":
            flat = np.load(path).astype(np.float32)
        elif ext in (".png", ".tif", ".tiff"):
            if not _HAS_CV2:
                return None
            raw = cv2.imread(path, cv2.IMREAD_UNCHANGED)
            if raw is None:
                return None
            flat = raw.astype(np.float32) / 32768.0
        else:
            return None
        # Renormieren zur Sicherheit
        m = float(np.mean(flat[flat > 0]))
        if m <= 0 or not np.isfinite(m):
            return None
        flat = np.clip(flat / m, 0.05, 20.0)
        return flat
    except Exception:
        return None


# ----------------------------------------------------------------------
# 2) Korrektur ANWENDEN (zur Laufzeit, pro Frame)
# ----------------------------------------------------------------------

def apply_flatfield(frame_bgr, flat):
    """
    Teilt einen BGR-uint8-Frame durch das Flatfield.

    Gibt einen korrigierten uint8-BGR-Frame zurueck. Bei jeder
    Unstimmigkeit (None, Groessenkonflikt, Fehler) wird der
    ORIGINAL-Frame unveraendert zurueckgegeben.
    """
    try:
        if frame_bgr is None or flat is None:
            return frame_bgr
        if frame_bgr.shape[:2] != flat.shape[:2]:
            # Geometrie passt nicht -> nicht raten, Original behalten
            return frame_bgr

        img = frame_bgr.astype(np.float32)
        if img.ndim == 3:
            div = flat[:, :, None]   # Broadcast ueber Farbkanaele
        else:
            div = flat
        out = img / div
        out = np.clip(out, 0, 255).astype(np.uint8)
        return out
    except Exception:
        return frame_bgr


class FlatfieldCorrector:
    """
    Bequemer Wrapper fuer die Pipeline: einmal initialisieren, dann pro Frame
    .correct(frame) aufrufen. Ist kein gueltiges Flat vorhanden, ist .correct
    eine reine Durchreiche (kein Effekt, kein Fehler).
    """

    def __init__(self, flat_path=None, log_fn=None):
        self._log = log_fn if callable(log_fn) else (lambda *a, **k: None)
        self.flat = None
        self.enabled = False
        if flat_path:
            self.load(flat_path)

    def load(self, flat_path):
        if not os.path.exists(flat_path):
            self._log(f"Flatfield nicht gefunden, Korrektur deaktiviert: {flat_path}")
            self.enabled = False
            return False
        flat = load_flatfield(flat_path)
        if flat is None:
            self._log(f"Flatfield konnte nicht geladen werden: {flat_path}")
            self.enabled = False
            return False
        self.flat = flat
        self.enabled = True
        self._log(f"Flatfield geladen ({flat.shape[1]}x{flat.shape[0]}), Korrektur aktiv.")
        return True

    def correct(self, frame_bgr):
        if not self.enabled or self.flat is None:
            return frame_bgr
        if frame_bgr is not None and frame_bgr.shape[:2] != self.flat.shape[:2]:
            self._log(
                f"Flatfield-Groesse {self.flat.shape[:2]} != Frame "
                f"{frame_bgr.shape[:2]} -> Korrektur uebersprungen."
            )
            return frame_bgr
        return apply_flatfield(frame_bgr, self.flat)

# ----------------------------------------------------------------------
# Hilfsfunktionen für Anwendung auf bereits aufgenommene und gespeicherte Bilder
PROJECT_ROOT = Path(__file__).resolve().parent
LEGACY_ROOT = Path("/home/Ento/LepmonOS")


def project_path(*parts):
    """Pfad relativ zum aktuellen Projektordner, mit Raspberry-Fallback."""
    candidate = PROJECT_ROOT.joinpath(*parts)
    if candidate.exists():
        return str(candidate)

    legacy = LEGACY_ROOT.joinpath(*parts)
    if legacy.exists():
        return str(legacy)

    return str(candidate)


def get_ARNI_Gen_by_filename(filename):
    """
    Extrahiert die Seriennummer aus dem Dateinamen und gibt die Generation zurück.
    Erwartetes Format:"Lepmon#SN010059_BW_FR_2026-08-04_T_0253.jpg"
    """
    generation = "Pro_Gen_3"  # Standardwert, falls keine Seriennummer gefunden wird
    match = re.search(r'SN\d{6}', filename)
    if match:
        serial_number = match.group(0)
        generation = get_generation_by_serial(serial_number)
        if generation not in {"Pro_Gen_1", "Pro_Gen_2", "Pro_Gen_3", "Pro_Gen_4", "CSS_Gen_1"}:
            generation = "Pro_Gen_3"
    else:
        print("Seriennummer nicht gefunden")

    return generation


def load_correction_mask(filename):
    HARDWARE_VERSION = get_ARNI_Gen_by_filename(filename)
    try:
        if HARDWARE_VERSION in ["Pro_Gen_1", "Pro_Gen_2"]:
            FLATFIELD_TIF = project_path("flatfield_masks", "flatfield_divisor_16bit_Pro_Gen_1_2.tif")
        elif HARDWARE_VERSION in ["Pro_Gen_3"]:
            FLATFIELD_TIF = project_path("flatfield_masks", "flatfield_divisor_16bit_Pro_Gen_3.tif")
        elif HARDWARE_VERSION in ["Pro_Gen_4"]:
            FLATFIELD_TIF = project_path("flatfield_masks", "flatfield_divisor_16bit_Pro_Gen_4.tif")
        elif HARDWARE_VERSION in ["CSS_Gen_1"]:
            FLATFIELD_TIF = project_path("flatfield_masks", "flatfield_divisor_16bit_CSS_Gen_1.tif")
        else:
            FLATFIELD_TIF = project_path("flatfield_masks", "flatfield_divisor_16bit_Pro_Gen_1_2.tif")

        flatfield = load_flatfield(FLATFIELD_TIF)
        if flatfield is None:
                print(f"Konnte Flatfield nicht laden: {FLATFIELD_TIF}")
                sys.exit(1)
    except Exception as e:
        print(f"Fehler beim Laden der Korrekturmaske: {e}")
        exit(1)

    return flatfield

#
# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
# 3) CLI: Weissbild -> Flatfield-Datei erzeugen
#        python flatfield.py build weissbild.jpeg flatfield.npy
# ----------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    # Verwendung von Andreas für Ersterstellung eines Flatfields aus einem Weissbild
    if len(sys.argv) >= 4 and sys.argv[1] == "build":
        white_path, out_path = sys.argv[2], sys.argv[3]
        white = cv2.imread(white_path, cv2.IMREAD_COLOR)
        if white is None:
            print(f"Konnte Weissbild nicht laden: {white_path}")
            sys.exit(1)
        flat = build_flatfield_from_white(white)
        save_flatfield(flat, out_path)
        print(f"Flatfield erzeugt: {out_path}  (shape {flat.shape}, "
              f"min {flat.min():.3f}, max {flat.max():.3f})")

    # Verwendung für Korrektur eines einzelnen Bildes mit einem Flatfield
    elif len(sys.argv) == 1 or sys.argv[1] == "correct":
        step = "input"
        while step == "input":
            raw_filename = input("Pfad zum Bild eingeben: ")
            filename = raw_filename.strip().strip("'\"")
            filename = os.path.expanduser(filename)

            if os.path.isfile(filename):
                step = "load_flatfield"
            else:
                print(f"Datei nicht gefunden: {raw_filename!r}, verwende Pfad kopieren, wegen # im Dateinamen.")
                print(f"Normalisierter Pfad: {filename}")

        if step == "load_flatfield":
            flatfield = load_correction_mask(filename)
            step = "load_image"

        if step == "load_image":
            image = cv2.imread(filename, cv2.IMREAD_COLOR)
            if image is None:
                print(f"Konnte Bild nicht laden: {filename}")
                sys.exit(1)
            step = "apply_correction"

        if step == "apply_correction":
            corrected_image = apply_flatfield(image, flatfield)
            step = "save_corrected_image"

        if step == "save_corrected_image":
            base, ext = os.path.splitext(filename)
            corrected_filename = f"{base}_corrected{ext}"
            cv2.imwrite(corrected_filename, corrected_image)
            print(f"Korrigiertes Bild gespeichert: {corrected_filename}")


    else:
        print("Verwendung:")
        print("  python flatfield.py build <weissbild> <flatfield.npy|.png|.tif>")
