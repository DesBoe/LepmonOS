import numpy as np
from PIL import Image
import cv2
import os
from OLED_panel import *
from language import get_language
from Camera_AV import *
from logging_utils import log_schreiben
from json_read_write import *

lang = get_language()

def reduce_image_size(image, border_ignore=0.05):
    h, w, _ = image.shape

    bh = int(h * border_ignore)
    bw = int(w * border_ignore)
    inner = image[bh:h-bh, bw:w-bw]
    print(f"Inner shape: {inner.shape}")
    resized = cv2.resize(inner, (w//2, h//2), interpolation=cv2.INTER_AREA)
    print(f"Original: {image.shape}, Inner: {inner.shape}, Nach Reduktion: {resized.shape}")
    return resized


def apply_white_balance(image, red_ratio, blue_ratio):
    """
    Wendet den Weißabgleich auf das Bild an und gibt das korrigierte Bild zurück.
    """
    img_corr = image.astype(np.float32)
    # Grün bleibt, Rot und Blau werden skaliert
    img_corr[..., 0] *= red_ratio   # R
    img_corr[..., 1] *= 1.0        # G
    img_corr[..., 2] *= blue_ratio # B
    img_corr = np.clip(img_corr, 0, 255).astype(np.uint8)
    return img_corr


def get_background_pixels(image, mask):
    """
    Extrahiere weiße RGB-Pixel (ohne Insekten).
    mask: 2D-Array (bool oder 0/255), True/255 = Hintergrund
    image: 3D-Array (H, W, 3)
    """
    # Falls Maske als uint8 (0/255) vorliegt, in bool umwandeln
    if mask.dtype != bool:
        mask = mask > 127
    # Nur die Hintergrundpixel extrahieren
    pixels = image[mask]
    return pixels

def get_rgb_means(pixels):
    r = np.mean(pixels[:, 0])
    g = np.mean(pixels[:, 1])
    b = np.mean(pixels[:, 2])
    return r, g, b

def compute_wb(r, g, b):
    r = max(r, 1e-6)
    b = max(b, 1e-6)
    red_ratio  = g / r
    blue_ratio = g / b

    print(f"WB -> Red: {red_ratio:.3f}, Blue: {blue_ratio:.3f}")
    return red_ratio, blue_ratio


def extract_mask(
    image,
    otsu_offset=10
):
    print(f"Extracting mask for image with shape: {image.shape}")

    gray_inner = np.mean(image, axis=2).astype(np.uint8)

    otsu_thresh, _ = cv2.threshold(
        gray_inner, 0, 255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )
    # min_threshold deutlich erhöhen
    threshold = max(otsu_thresh + otsu_offset,155)

    gray_full = np.mean(image, axis=2).astype(np.uint8)
    # Weniger starker Median-Filter
    gray_full = cv2.medianBlur(gray_full, 5)
    mask = gray_full > threshold
    mask_uint8 = (mask * 255).astype(np.uint8)

    # Noch kleinerer Kernel für Morphologie
    kernel = np.ones((2, 2), np.uint8)
    mask_clean = cv2.morphologyEx(mask_uint8, cv2.MORPH_OPEN, kernel)
    mask_bool = mask_clean > 0

    return mask_bool, threshold


def get_wb(current_image, log_mode= "manual", show = False):
    log_schreiben(f"Starte Weißabgleichsberechnung für Bild: {current_image}", log_mode)
    
    show_message("wb_01", lang=lang)
    red_ratio, blue_ratio = 1.0, 1.0

    if isinstance(current_image, str):
        img = np.array(Image.open(current_image).convert("RGB"))
        print(f"Loaded image from path: {current_image} with shape: {img.shape}")
        if img is None:
            raise ValueError(f"Bild konnte nicht geladen werden: {current_image}")
    elif isinstance(current_image, np.ndarray):
        img = current_image
        print(f"Received image as NumPy array with shape: {img.shape}")
    else:
        log_schreiben(f"Ungültiger Eingabetyp für get_wb: {type(current_image)}", log_mode)
        raise ValueError("Ungültiger Eingabetyp. Erwartet wird ein Dateipfad oder ein NumPy-Array.")
    
    print(f"Processing...")
    try:
        img = reduce_image_size(img)  # Bildgröße reduzieren, um Rauschen am Rand zu vermeiden
    except Exception as e:
        log_schreiben(f"Fehler bei reduce_image_size: {e}", log_mode)

    try:
        mask, threshold = extract_mask(img)
        log_schreiben(f"Maske erstellt mit Threshold: {threshold}", log_mode)
    except Exception as e:
        log_schreiben(f"Fehler beim Erstellen der Maske: {e}", log_mode)

    try:
        pixels = get_background_pixels(img, mask)
    except Exception as e:
        log_schreiben(f"Fehler beim Extrahieren der Hintergrundpixel: {e}", log_mode)
        pixels = np.array([])

    if len(pixels) < 100:
        log_schreiben("Zu wenig Hintergrund erkannt, Standard-WB-Verhältnisse werden verwendet.", log_mode)
        red_ratio, blue_ratio = 1.0, 1.0
    else:
        try:
            log_schreiben(f"Berechne RGB-Mittelwerte für {len(pixels)} Hintergrundpixel...", log_mode)
            r, g, b = get_rgb_means(pixels)
            red_ratio, blue_ratio = compute_wb(r, g, b)
            log_schreiben(f"Berechnete WB-Verhältnisse -> Rot: {red_ratio:.3f}, Blau: {blue_ratio:.3f}", log_mode)
        except Exception as e:
            log_schreiben(f"Fehler bei der Berechnung der WB-Verhältnisse: {e}", log_mode)
            red_ratio, blue_ratio = 1.0, 1.0

    log_schreiben("##################################", log_mode=log_mode)
    log_schreiben("##################################", log_mode=log_mode)
    log_schreiben("verwendete Maske:",log_mode=log_mode)
    log_schreiben("Matrix_BW_Beginn", log_mode=log_mode)
    mask_str = "\n".join(" ".join(str(int(val)) for val in row) for row in mask)
    log_schreiben(mask_str, log_mode=log_mode)
    log_schreiben("Matrix_BW_Ende", log_mode=log_mode)
    log_schreiben("##################################", log_mode=log_mode)
    log_schreiben("##################################", log_mode=log_mode)



    if show == True:
        print("korrigiertes Bild wird gespeichert...")
        
        img_corr = apply_white_balance(img, red_ratio, blue_ratio)

        base_name = os.path.splitext(current_image)[0]
        output_base = os.path.join(os.path.dirname(current_image), base_name)

        # Maske als Bild speichern
        mask_img = (mask * 255).astype(np.uint8)
        Image.fromarray(mask_img).save(output_base + "_mask.png")
        Image.fromarray(img_corr).save(output_base + "_image_korrigiert.jpg")

    red_balance_old = float(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "AV__Alvium_1800_U-2050", "balance_ratio_red"))
    blue_balance_old = float(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "AV__Alvium_1800_U-2050", "balance_ratio_blue"))

    red_balance_new = red_ratio * red_balance_old
    blue_balance_new = blue_ratio * blue_balance_old
    log_schreiben("Übenehme Weißabgleich:", log_mode=log_mode)

    log_schreiben(f"{'Red Balance  old':<22} | {red_balance_old:.6f}", log_mode=log_mode)
    log_schreiben(f"{'Blue Balance old':<22} | {blue_balance_old:.6f}", log_mode=log_mode)
    log_schreiben(f"{'Red Balance  new':<22} | {red_balance_new:.6f}", log_mode=log_mode)
    log_schreiben(f"{'Blue Balance new':<22} | {blue_balance_new:.6f}", log_mode=log_mode)

    write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "AV__Alvium_1800_U-2050", "balance_ratio_red", red_balance_new)
    write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "AV__Alvium_1800_U-2050", "balance_ratio_blue", blue_balance_new)

    return red_ratio, blue_ratio


if __name__ == "__main__":
    
    exposure = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "AV__Alvium_1800_U-2050", "initial_exposure"))
    gain = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "AV__Alvium_1800_U-2050", "initial_gain_10")) / 10
    code, dateipfad, Status_Kamera, power_on, Kamera_Fehlerserie, avg_brightness, good_exposure, Exposure, Gain = snap_image_AV("jpg", "log", 0, "manual", exposure, gain)
    get_wb(dateipfad, log_mode= "log", show = True)

    

