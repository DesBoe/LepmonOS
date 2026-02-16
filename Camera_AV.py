from vimba import *
#from vmbpy import *
from Lights import *
from json_read_write import *
import time
from datetime import datetime 
import os
import cv2
from OLED_panel import *
from logging_utils import log_schreiben
from GPIO_Setup import *
from gpiozero import LED
from sensor_data import get_power
from logging_utils import *

from service import *
from runtime import write_timestamp
from image_quality_check import *
import numpy as np
import gc

lang = get_language()
          
          
def get_frame_AV(Exposure,cam_mode,log_mode,Gain):
    cams = None 
    cam_Initiliase_tries = 0
    power_vis = "---"
    frame = None
    while cams is None:
        if cam_mode == "display" and cam_Initiliase_tries == 0:
            show_message("cam_1",lang=lang)
        cam_Initiliase_tries += 1
        time.sleep(0.1)
        #with VmbSystem.get_instance() as vmb:
        #    cams = vmb.get_all_cameras()
        with Vimba.get_instance() as vimba:
            cams = vimba.get_all_cameras()

            try:
                with cams[0] as cam:
                    try: 
                        cam.set_pixel_format(PixelFormat.Bgr8)
                        #cam.PixelFormat.set(PixelFormat.Bgr8)
                    except Exception as e:
                        print(f"Fehler beim Setzen des Pixelformats: {e}")

                    settings_file = '/home/Ento/LepmonOS/Kamera_Einstellungen.xml'.format(cam.get_id())

                    try:
                        cam.load_settings(settings_file, PersistType.All)
                    except Exception as e:
                        print(f"Fehler beim Laden der Kameraeinstellungen: {e}")
                    

                    # Set exposure time (convert ms to microseconds)
                    #cam.ExposureTime.set(Exposure * 1000)
                    #print(f"Exposure in Kamera Einstellungen geändert:{(cam.ExposureTime.get()/1000):.0f}")
                    exposure_time = cam.ExposureTime
                    exposure_time.set(Exposure*1000)
                    print(f"Exposure in Kamera Einstellungen geändert:{(exposure_time.get()/1000):.0f}")
                    

                    # Set gain
                    #cam.Gain.set(Gain)
                    #print(f"Gain in Kamera Einstellungen geändert:{cam.Gain.get()}")
                    gain_value = cam.Gain
                    gain_value.set(Gain)
                    print(f"Gain in Kamera Einstellungen geändert:{gain_value.get()}")

                    if cam_mode != "focus":
                        dim_up()
                        
                        _, _, _, power_vis, _ = get_power()
                    
                    # Capture frame using new API# Capture frame using new API
                    
                    frame = cam.get_frame(timeout_ms=5000).as_opencv_image()
                    
                    if cam_mode != "focus":
                        dim_down()

                    Kamera_Status = 1
                    if cam_mode == "display":
                        show_message("cam_2",lang=lang)
                        print("frame erfolgreich aufgenommen")
                        
        
            except Exception as e:    
                        
                        Kamera_Status = 0
                        cams = None
                        if cam_Initiliase_tries > 5:
                            show_message("err_1a",lang=lang,tries = cam_Initiliase_tries)
                            print(f"Fehler beim Abrufen des Frames: {e}")
                            print(f"Prüfe Kamera Verbindung und Stromversorgung. Versuch {cam_Initiliase_tries}")

        if cam_Initiliase_tries > 90:
            print(f"Kamera nach {cam_Initiliase_tries} Versuchen nicht initalisiert")
            log_schreiben(f"Kamera nach {cam_Initiliase_tries} Versuchen nicht initalisiert", log_mode=log_mode)
            show_message("cam_3",lang=lang)    
            time.sleep(5)
            e = f"Kamera nach {cam_Initiliase_tries} Versuchen nicht initalisiert"   
            error_message(1,e,log_mode)
            print(f"Fehler beim Abrufen des Frames: {e}")
            print("Prüfe Kamera Verbindung und Stromversorgung")
            break 
        
    return frame,Kamera_Status, power_vis
        
        
#####################


def snap_image_AV(file_extension,cam_mode, Kamera_Fehlerserie, log_mode, Exposure,Gain = 9, sn = ""):
    """
    nimmt ein Bild auf

    :param file_extension: Dateierweiterung
    :param cam_mode: "display" für lokale ausgabe; "log" für speichern in der schleife; "kamera_test" für Kameratest, Diagnose für Diagnose
    """
    code = 000
    power_on = 0
    image_file = ""
    
    avg_brightness, good_exposure = "---", False
    image_correction = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","capture_mode","gamma_correction")
    gamma = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","AV__Alvium_1800_U-2050","gamma_value")

    camera = LED(5)

    camera.on()
    if cam_mode == "display":
        show_message("cam_4",lang=lang)

    ordnerpfad = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","general","current_folder")
    
    if cam_mode != "kamera_test":
        project_name,province, Kreis_code, sensor_id = get_Lepmon_code(log_mode)
        now = datetime.now()
        code = f"{project_name}{sensor_id}_{province}_{Kreis_code}_{now.strftime('%Y')}-{now.strftime('%m')}-{now.strftime('%d')}_T_{now.strftime('%H%M')}"
        image_file = f"{code}.{file_extension}"
        dateipfad = os.path.join(ordnerpfad, image_file)
        
    if cam_mode == "kamera_test":
        if not os.path.exists(ordnerpfad):
            erstelle_ordner(log_mode, "AV__Alvium_1800_U-2050")
            print(f"Ordner '{ordnerpfad}' wurde erstellt.")        
        
        image_file = f"AV__Alvium_1800_U-2050_{Exposure}_{Gain}.jpg"
        dateipfad = os.path.join(ordnerpfad, image_file)
        
        print(f"Kamera Test Bild wird gespeichert in: {dateipfad}")
    
    if cam_mode == "Diagnose":
        image_file = f"{ordnerpfad}/Lepmon_Diagnose_{sn}_Testbild.jpg"

    if not cam_mode == "Diagnose":
        time.sleep(4)    
        
    
    if cam_mode == "display":
        show_message("cam_5",lang=lang) 
        LepiLED_start("show")
        ordnerpfad,_ = get_usb_path(log_mode)
        dateipfad = "Testbild.jpg"
        dateipfad = os.path.join(ordnerpfad, dateipfad)
        print(f"Ordnerpfad für Testbild:{dateipfad}")
        
        
        
    if cam_mode == "log":
        time.sleep(5)    
    
    frame,Status_Kamera, power_vis = get_frame_AV(Exposure,cam_mode,log_mode,Gain)

    if frame is not None:
        Kamera_Fehlerserie = 0
        if cam_mode == "log":
            avg_brightness, Exposure, Gain, good_exposure  = calculate_Exposure_and_gain(frame, Exposure, Gain, "AV__Alvium_1800_U-2050",log_mode) 
            avg_brightness = round(avg_brightness,0)
            
            # gamma correction for shadow brightening
            if image_correction and gamma is not None and gamma != 0:
                time.sleep(1)
                print(f"Belichtungsoptimierung: Wende Gamma Korrektur an (gamma={gamma})", flush=True)
                
                height = frame.shape[0]
                split1 = height // 3
                split2 = 2 * height // 3
                
                teile = [frame[:split1], frame[split1:split2], frame[split2:]]
                del frame
                
                bearbeitet = []
                for i, teil in enumerate(teile):
                    print(f"korrigiere frame Teil {i+1}", flush=True)
                    teil = teil / 255.0
                    teil = np.power(teil, 1 / gamma)
                    teil = (teil * 255).astype(np.uint8)
                    bearbeitet.append(teil)
                    del teil
                    gc.collect()
                frame = np.vstack(bearbeitet)
                del bearbeitet
                gc.collect()
                print("Belichtungsoptimierung: Gamma Korrektur vollständig angewendet", flush=True)  
            elif gamma is None or gamma == 0:
                    print(f"FEHLER: gamma ist :{gamma}!", flush=True)    
            

    if frame is None:
        if cam_mode == "display":
            error_message(1,"Fehler beim Abrufen des Frames", log_mode)

        if cam_mode == "log": 
           Kamera_Fehlerserie += 1

    if cam_mode == "log" or cam_mode == "Diagnose":
        time.sleep(.5)
        try:
            _, _, _, power_cam, _ = get_power()
            power_on = round(power_vis - power_cam,2)
            time.sleep(.1)   
        except Exception as e:
            power_on = "---"
            print(f"Fehler beim Messen des Stromverbrauchs der Visible LED: {e}") 
    camera.off()    
    camera.close()
    
    if cam_mode == "display":
        show_message("cam_6",lang=lang) 
        LepiLED_ende("show")
    if not os.path.exists(ordnerpfad) and cam_mode != "display":
            if ordnerpfad == "":
                ordnerpfad = f"Ordnerpfad ist leer!"
            error_message(3, f"USB-Stick nicht gefunden: {ordnerpfad}", log_mode)
            print(f"Fehler: USB-Stick nicht gefunden: {ordnerpfad}")
            #Status_Kamera = 0
            #Kamera_Fehlerserie = 1
            print("Zum estelllen des Ordners bitte USB-Stick anschließen und start_up.py ausführen ")
            return code, dateipfad, Status_Kamera, power_on, Kamera_Fehlerserie, avg_brightness, good_exposure, Exposure, Gain
    
    if frame is not None:
        try:
            cv2.imwrite(dateipfad, frame)

            Status_Kamera = 1
            if cam_mode == "display":
                show_message("cam_7",lang=lang) 
                os.remove(dateipfad)
                print(f"Bild vom Speicher gelöscht: {dateipfad}")
                log_schreiben("Kamera Zugriff erfolgreich",log_mode=log_mode)
            if cam_mode == "log": 
                log_schreiben(f"Bild gespeichert: {dateipfad}", log_mode=log_mode)  
            
        except Exception as e:

            print(f"Kamerafehler:{e}")
            error_message(3, f"Bild konnte nicht gespeichert werden: {dateipfad}", log_mode)
            Status_Kamera = 0
            Kamera_Fehlerserie += 1
            return code, dateipfad, Status_Kamera, power_on, Kamera_Fehlerserie, avg_brightness, good_exposure, Exposure, Gain
    elif frame is None:
        print("Kein Bild zum Speichern vorhanden")       
                        

    if cam_mode == "log":
        write_timestamp(0x07E0)
    
    return code, dateipfad, Status_Kamera, power_on, Kamera_Fehlerserie, avg_brightness, good_exposure, Exposure, Gain


if __name__ == "__main__":
    print("Nehme ein Bild mit der AV Kamera auf")
    #gain = input("Gain Wert eingeben:")
    #exposure = input("Belichtungszeit in ms eingeben:")
    exposure = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","AV__Alvium_1800_U-2050","initial_exposure"))
    gain = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","AV__Alvium_1800_U-2050","initial_gain_10"))/10
    snap_image_AV("jpg","log",0,"log",exposure,gain) 