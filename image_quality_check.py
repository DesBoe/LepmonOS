from PIL import Image
from logging_utils import *
from json_read_write import *
from runtime import write_timestamp
from libcamera import controls, Transform
import os
from picamera2 import Picamera2, Preview 
import cv2
import numpy as np
from hardware import *
from OLED_panel import *


##################################
### beide Kameras###
##################################
def check_image(dateipfad, log_mode = "log"):
    if log_mode == "log":
        write_timestamp(0x07E0)

    try:
        sanity_level = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","frame_brightness","black_sanity_level")
    except Exception as e:
        print(f"Fehler beim Lesen des Sanity Levels aus der Konfigurationsdatei: {e}")
        error_message(14,e, log_mode)
        sanity_level = 0.05  # Standardwert, falls das Lesen fehlschlägt

    camera = get_device_info("camera")
    length = get_device_info("length")
    height = get_device_info("height")
    try:
        with Image.open(dateipfad) as img:
            img.load()

            if img.width != length or img.height != height:
                raise ValueError(f"Falsche Bildgröße: erwartet {length}x{height} von {camera}, erhalten {img.width}x{img.height}")
            
            
            
            
            img_gray = img.convert("L")
            pixels = img_gray.getdata()
            total_pixels = img_gray.width * img_gray.height
            black_pixels = sum(1 for p in pixels if p == 0)
            black_ratio = black_pixels / total_pixels
            if black_ratio > sanity_level:
                raise ValueError(f"Bild enthält zu viele schwarze Pixel ({black_ratio:.2%})")
            print(f"Foto hat Sanity Check bestanden und ist vollständig. Schwarze Pixel: {black_ratio:.2%}")
            return True
    except Exception as e:
        print(f"Foto {dateipfad} hat Sanity Check nicht bestanden: {e}")
        log_schreiben(f"unvollständiges Foto {dateipfad} erkannt. ARNI nimmt neu auf.", log_mode=log_mode)
        error_message(14,e, log_mode)
        os.remove(dateipfad)
        return False
    

def first_exp(Night, log_mode, camera):
    exposure,gain = 160,9
    if Night == 0: # False --> Nacht hat noch nicht begonnen und Kamera fängt mit default werten an
        try:
            if camera == "AV__Alvium_1800_U-2050":
                exposure = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","AV__Alvium_1800_U-2050","initial_exposure"))
                gain = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","AV__Alvium_1800_U-2050","initial_gain_10"))/10
            elif camera == "RPI_Module_3":
                exposure = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_Module_3","initial_exposure_10")/10
                gain = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_Module_3","initial_gain_10")/10
            elif camera == "RPI_HQ":
                exposure = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_HQ","initial_exposure_10")/10
                gain = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_HQ","initial_gain_10")/10
            print(f"Initialer Exposure: {exposure}, Initialer Gain: {gain}")
        except Exception as e:
            print(f"Fehler beim Lesen des initialen Exposure und Gain aus der Konfigurationsdatei: {e}")
            error_message(9,e,log_mode)
    
    elif Night == 1:
        try:

            gain_bytes = read_fram_bytes(0x069C, 1)
            gain = int.from_bytes(gain_bytes, byteorder='big')/10
            print(f"Gelesener Gain: {gain}")

            exposure_bytes = read_fram_bytes(0x0698, 1)
            exposure = int.from_bytes(exposure_bytes, byteorder='big')
            print(f"Gelesene Exposure: {exposure}")

            # Prüfen, ob Werte 0 sind, falls ja, Default-Werte verwenden
            #if gain > 26 or not 85 < exposure < 9999982:
            #    print(f"Warnung: Gain oder Exposure im FRAM nicht im gültigen Bereich: Gain={gain}, Exposure={exposure}. Nutze Werte aus der Konfigurationsdatei.")
            #    exposure = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","capture_mode","initial_exposure"))
            #    gain = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","capture_mode","initial_gain"))
            #    print(f"Default Exposure: {exposure}, Default Gain: {gain}")
        except Exception as e:
            print(f"Fehler beim Lesen des aktuellen Exposure und Gain aus dem FRAM: {e}")
            error_message(9,e, log_mode)
            try:
                if camera == "AV__Alvium_1800_U-2050":
                    exposure = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","AV__Alvium_1800_U-2050","initial_exposure"))
                    gain = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","AV__Alvium_1800_U-2050","initial_gain_10"))/10
                elif camera == "RPI_Module_3":
                    exposure = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_Module_3","current_exposure_10"))/10
                    gain = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_Module_3","current_gain_10"))/10
                elif camera == "RPI_HQ":
                    exposure = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_HQ","current_exposure_10")/10
                    gain = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_HQ","current_gain_10"))/10
                print(f"Initialer Exposure: {exposure}, Initialer Gain: {gain}")

                print(f"Initialer Exposure: {exposure}, Initialer Gain: {gain}")
            except Exception as e:
                print(f"Fehler beim Lesen des initialen Exposure und Gain aus der Konfigurationsdatei: {e}")
    else:
        print("Nachtkontrolbit nicht erkannt")
        
    return exposure, gain
 
    
def calculate_Exposure_and_gain(current_image, initial_exposure, initial_gain, camera, log_mode="log"):
    # general
    brightness_tolerance = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","frame_brightness","brightness_tolerance")
    brightness_reference = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","frame_brightness","brightness_reference")

    # camera specific
    if camera == "AV__Alvium_1800_U-2050":
        minimal_gain = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","AV__Alvium_1800_U-2050","minimal_gain_10"))/10
        maximal_gain = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","AV__Alvium_1800_U-2050","maximal_gain_10"))/10
        step_gain = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","AV__Alvium_1800_U-2050","step_gain_10"))/10
        maximal_exposure = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","AV__Alvium_1800_U-2050","maximal_exposure")
        minimal_exposure = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","AV__Alvium_1800_U-2050","minimal_exposure")
        step_exposure = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","AV__Alvium_1800_U-2050","step_exposure")

    elif camera == "RPI_Module_3":
        minimal_gain = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_Module_3","minimal_gain_10"))/10
        maximal_gain = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_Module_3","maximal_gain_10"))/10
        step_gain = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_Module_3","step_gain_10"))/10
        maximal_exposure = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_Module_3","maximal_exposure_10"))/10
        minimal_exposure = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_Module_3","minimal_exposure_10"))/10
        step_exposure = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_Module_3","step_exposure_10"))/10
    
    elif camera == "RPI_HQ":
        minimal_gain = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_HQ","minimal_gain_10"))/10
        maximal_gain = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_HQ","maximal_gain_10"))/10
        step_gain = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_HQ","step_gain_10"))/10
        maximal_exposure = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_HQ","maximal_exposure_10"))/10
        minimal_exposure = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_HQ","minimal_exposure_10"))/10
        step_exposure = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_HQ","step_exposure_10"))/10 

    
    
    avg_brightness = 1000
    new_gain = initial_gain
    new_exposure = initial_exposure
    good_exposure = False
    try:
        if isinstance(current_image, str):
            img = cv2.imread(current_image)
            if img is None:
                raise ValueError(f"Bild konnte nicht geladen werden: {current_image}")
        else:
            img = current_image

    except Exception as e:
        print(f"Fehler beim Laden den Bildes/Frames zur Analyse der Exposure und des Gains:{e}")
        return avg_brightness, new_exposure, new_gain, good_exposure
        
    if img is not None:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        avg_brightness = gray.mean()
        avg_brightness = round(avg_brightness,2)
        print(f"Aktuelle durchschnittliche Helligkeit: {avg_brightness:.2f}")
        
        control = avg_brightness - brightness_reference
        if control <= -brightness_tolerance:

            if initial_exposure < maximal_exposure:
                new_exposure = initial_exposure + step_exposure
                print(f"Exposure erhöht von {initial_exposure} auf {new_exposure}")
                log_schreiben(f"Exposure erhöht von {initial_exposure} auf {new_exposure}", log_mode=log_mode)
            elif initial_gain < maximal_gain:
                new_gain = initial_gain + step_gain
                print(f"Gain erhöht von {initial_gain} auf {new_gain}")
                log_schreiben(f"Gain erhöht von {initial_gain} auf {new_gain}", log_mode=log_mode)
                write_current_exp(new_exposure, new_gain, camera, log_mode)
            
            elif initial_exposure == maximal_exposure and initial_gain == maximal_gain:
                print("Sowohl Exposure als auch Gain haben das Maximum erreicht. Keine weitere Erhöhung möglich.")
                log_schreiben("Sowohl Exposure als auch Gain haben das Maximum erreicht. Keine weitere Erhöhung möglich.", log_mode=log_mode)
                good_exposure = True
                new_exposure = initial_exposure
                new_gain = initial_gain
                return avg_brightness, new_exposure, new_gain, good_exposure
                
        elif control >= brightness_tolerance:
            if initial_gain > minimal_gain:
                new_gain = initial_gain - step_gain
                log_schreiben(f"Gain verringert von {initial_gain} auf {new_gain}",log_mode)
            elif initial_exposure > minimal_exposure:
                new_exposure = initial_exposure - step_exposure
                log_schreiben(f"Exposure verringert von {initial_exposure} auf {new_exposure}",log_mode)
                write_current_exp(new_exposure, new_gain,camera, log_mode)
                
            elif initial_exposure == minimal_exposure and initial_gain == minimal_gain:
                print("Sowohl Exposure als auch Gain haben das Minimum erreicht. Keine weitere Verringerung möglich.")
                log_schreiben("Sowohl Exposure als auch Gain haben das Minimum erreicht. Keine weitere Verringerung möglich.",log_mode)
                good_exposure = True
                new_exposure = initial_exposure
                new_gain = initial_gain
                return avg_brightness, new_exposure, new_gain, good_exposure

        elif -brightness_tolerance < control < brightness_tolerance:
            print("Helligkeit im optimalen Bereich. Keine Anpassung von Exposure oder Gain erforderlich.")
            good_exposure = True
        
        
        else:
            print(f"Unbekannter Kontrollwert für die Helligkeitsanpassung: {control}")
        
        print("Helligkeitsberechnung beendet")
        time.sleep(7)
            
        
    return avg_brightness, new_exposure, new_gain, good_exposure
       
          
       
def write_current_exp(exposure, gain, camera, log_mode):
    try:
        # Sicherstellen, dass Werte Integer sind
        if not isinstance(exposure, int):
            exposure = int(round(exposure))
        gain = gain*10
        print(f"Zu schreibender Gain : {gain}")
        if not isinstance(gain, int):
            gain = int(round(gain))
        write_fram_bytes(0x0698, exposure.to_bytes(1, byteorder='big'))
        write_fram_bytes(0x069C, gain.to_bytes(1, byteorder='big'))
        print(f"Aktuelle Exposure ({exposure}) und Gain ({gain}) in FRAM geschrieben")
    except Exception as e:
        print(f"Fehler beim Schreiben von Exposure und Gain in FRAM: {e}")
        error_message(9,e, log_mode)  
    
    try:
        if camera == "AV__Alvium_1800_U-2050":
            write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "AV__Alvium_1800_U-2050", "current_exposure", str(exposure))
            write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "AV__Alvium_1800_U-2050", "current_gain_10", str(gain))
        elif camera == "RPI_Module_3":
            write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "RPI_Module_3", "current_exposure_10", str(exposure))
            write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "RPI_Module_3", "current_gain_10", str(gain))
        elif camera == "RPI_HQ":
            write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "RPI_HQ", "current_exposure_10", exposure)
            write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "RPI_HQ", "current_gain_10", gain)
        print(f"Aktuelle Exposure ({exposure}) und Gain ({gain}) in config geschrieben")
    except Exception as e:
        print(f"Fehler beim Schreiben von Exposure und Gain in die Konfigurationsdatei: {e}")
        


    
def set_focus_rpi_cam():
    picam2 = Picamera2()
    picam2.start()
    success = picam2.autofocus_cycle()
    time.sleep(1)
    
    metadata = picam2.capture_metadata()
    if "LensPosition" in metadata:
        saved_focus = metadata["LensPosition"]
        print(f"Gefundener Fokuswert: {saved_focus}")
    else:
        print("Fokuswert konnte nicht gefunden werden.")
        saved_focus = 0.0
        
    picam2.stop()
    picam2.close()
    
    return saved_focus 

    
def check_focus(current_image, camera, log_mode):
    """
    Analysiert die Schärfe eines aufgenommenen Bildes oder eines Frames und entscheidet, ob es scharf ist.
    
    Parameter:
        current_image (str oder np.ndarray): Pfad zum aufgenommenen Bild oder ein Frame als NumPy-Array.
        threshold (float): Schwellwert für die Schärfe. Bilder mit einer Varianz unter diesem Wert gelten als unscharf.
    
    Rückgabe:
        bool: True, wenn das Bild scharf ist, False, wenn neu fokussiert werden muss.
        float: Die berechnete Varianz des Laplace-Operators (Schärfewert).
    """


    if camera == "RPI_Module_3":
        threshold = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_Module_3","focus_threshold")
    elif camera == "RPI_HQ":
        threshold = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_HQ","focus_threshold")
    elif camera == "AV__Alvium_1800_U-2050":
        threshold = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","AV__Alvium_1800_U-2050","focus_threshold")

    
    try:
        # Prüfen, ob current_image ein Dateipfad (String) oder ein Frame (NumPy-Array) ist
        if isinstance(current_image, str):
            img = cv2.imread(current_image, cv2.IMREAD_GRAYSCALE)
            if img is None:
                raise ValueError(f"Bild konnte nicht geladen werden: {current_image}")
        elif isinstance(current_image, np.ndarray):
            img = cv2.cvtColor(current_image, cv2.COLOR_BGR2GRAY)  # Konvertiere Frame in Graustufen
        else:
            raise TypeError("current_image muss entweder ein Dateipfad (str) oder ein Frame (np.ndarray) sein.")
        
        # Schärfeanalyse mit Laplace-Operator
        laplacian = cv2.Laplacian(img, cv2.CV_64F)
        variance = laplacian.var()
        
        print(f"Fokus-Varianz: {variance:.2f}")
        
        if variance >= float(threshold) and camera == "AV__Alvium_1800_U-2050":
            log_schreiben(f"Bilder der {camera} sind scharf: Schwellenwert: {threshold}, gemessene Fokusvarianz: {variance:.2f}", log_mode)
            return True, variance
        elif variance >= float(threshold) and camera == "RPI_Module_3":
            log_schreiben(f"Bilder der {camera} sind scharf: Schwellenwert: {threshold}, gemessene Fokusvarianz: {variance:.2f}", log_mode)
            return True, variance
        elif variance >= float(threshold) and camera == "RPI_HQ":
            log_schreiben(f"Bilder der {camera} sind scharf: Schwellenwert: {threshold}, gemessene Fokusvarianz: {variance:.2f}", log_mode)
            return True, variance

        else:
            print("Bild ist unscharf. Neu fokussieren erforderlich.")
            log_schreiben(f"WARNUNG: Bilder der {camera} sind verschwommen: Schwellenwert: {threshold}, gemessene Fokusvarianz: {variance:.2f}", log_mode)
            return False, variance
    except Exception as e:
        print(f"Fehler bei der Fokusanalyse: {e}")
        return False, 0.0
    

if "__main__" == __name__:
    path = "/media/Ento/LEPMON/Belichtungsreihe_RPI_HQ/RPI_HQ_50_1.jpg"
    if not os.path.exists(path):
        print(f"Datei existiert nicht: {path}\nnutze Logo")
        path = "/home/Ento/LepmonOS/startscreen/LepmonOS_Logo_9_9.jpg"
    log_mode = "manual"
        
    camera = get_device_info("camera")

    print("---------------------------------")
    print("Sanity Check")
    check_image(path, log_mode)
    print("---------------------------------")
    print("Focus Check")
    check_focus(path, camera, log_mode)
    print("---------------------------------")
    
