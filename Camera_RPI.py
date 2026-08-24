import os
os.environ["QT_QPA_PLATFORM"] = "xcb"
from picamera2 import Picamera2, Preview

from json_read_write import get_value_from_section
from datetime import datetime
import time
from logging_utils import *
from libcamera import controls, Transform
from Lights import *
import os
from image_quality_check import *
from service import *
import xml.etree.ElementTree as ET
from OLED_panel import *

import cv2
from Lights import dim_up, dim_down
from runtime import write_timestamp
from hardware import get_hardware_version, get_device_info
from sensor_data import get_power
import numpy as np
import gc
from gamma_korr import gamma_correction
from dev_mode import DEV_MODE, note_mock
from mock_hardware import generate_mock_frame

from flatfield import load_flatfield, apply_flatfield

HARDWARE_VERSION = get_hardware_version()

flatfield_correction = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "capture_mode", "flatfield_correction")
if flatfield_correction:
    if HARDWARE_VERSION in ["CSS_Gen_1"]:
        FLATFIELD_TIF = "/home/Ento/LepmonOS/flatfield_masks/flatfield_divisor_16bit_CSS_Gen_1.tif"

    def _load_flat(log_mode="manual"):
        # log_mode defaults to "manual" (console-only): this runs at module
        # import time, before erstelle_ordner()/initialisiere_logfile() has
        # necessarily created a session log file, so log_mode="log" here would
        # retry against a possibly-missing path and could trigger a forced
        # reboot (see log_schreiben) on every import.
        try:
            flat = load_flatfield(FLATFIELD_TIF)
            if flat is None:
                log_schreiben(f"Flatfield nicht ladbar, Korrektur deaktiviert: {FLATFIELD_TIF}", log_mode=log_mode)
            else:
                log_schreiben(f"Flatfield geladen ({flat.shape[1]}x{flat.shape[0]}), Korrektur aktiv.", log_mode=log_mode)
            return flat
        except Exception as e:
            log_schreiben(f"Fehler beim Laden des Flatfields: {e}", log_mode=log_mode)
            return None



    _FLAT = _load_flat()
elif not flatfield_correction:
    _FLAT = None
    log_schreiben("Flatfield Korrektur deaktiviert.", log_mode="manual")

def apply_flat(frame,log_mode="manual"):
    # --- Flatfield-Korrektur (greift nur bei gueltigem Flat
    #     und passender Groesse; sonst unveraendertes Original) ---
    print(f"wende Flatfield an:{_FLAT}")
    if _FLAT is not None:
        print("wende Flatfiled Korrektur an...")
        if frame.shape[:2] == _FLAT.shape[:2]:
            frame = apply_flatfield(frame, _FLAT)
            print("Flatfield-Korrektur angewandt")
        elif _FLAT is None:
            log_schreiben(
                f"Flatfield-Groesse {_FLAT.shape[:2]} != Frame "
                f"{frame.shape[:2]} -> Korrektur uebersprungen.",
                log_mode=log_mode)
    return frame




def dict_to_xml(tag, d):
    elem = ET.Element(tag)
    for key, val in d.items():
        child = ET.SubElement(elem, key)
        child.text = str(val)
    return elem


def _rpi_camera_present():
    """Cheap presence check - lists cameras without opening/configuring one."""
    try:
        return bool(Picamera2.global_camera_info())
    except Exception:
        return False


def get_frame_RPI(expected_camera, cam_mode,log_mode, Exposure, Gain, compression_quality, focus= 5.3):
    error_details = ""
    red_gain, blue_gain = None, None
    cam_Initiliase_tries = 0
    power_vis = "---"
    Kamera_RPI_Status = 0
    frame = None
    metadata = ""



    if cam_mode == "display":
            show_message("cam_1",lang=lang)
            print("nehme Frame auf")

    if DEV_MODE and not _rpi_camera_present():
        note_mock("Raspberry Pi camera (picamera2)")
        frame = generate_mock_frame(get_device_info('length'), get_device_info('height'), label="DEV MODE - RPI")
        try:
            _, _, _, power_vis, _ = get_power()
        except Exception:
            power_vis = "---"
        return frame, 1, power_vis, metadata, red_gain, blue_gain

    if expected_camera == "RPI_Module_3": #imx708
        while cam_Initiliase_tries <= 90 and Kamera_RPI_Status == 0:
            time.sleep(0.1)
            picam2 = None
            picam2 = Picamera2()
            picam2.options["quality"] = compression_quality
            camera_config = picam2.create_still_configuration(main={"size": (4608, 2592)})
            picam2.configure(camera_config)
            try:
                picam2.start()
                
                if cam_mode != "focus":
                    dim_up()
                    _, _, _, power_vis, _ = get_power()
                    
                picam2.set_controls({
                        "AnalogueGain": Gain,
                        "ExposureTime": Exposure * 1000,
                        "AwbEnable": True,
                        #"AwbMode": controls.AwbModeEnum.Auto,
                        #"AfMode": controls.AfModeEnum.Continuous,
                        "AfMode": controls.AfModeEnum.Manual,
                        "LensPosition": focus 
                    })
                time.sleep(2.5)

                frame = picam2.capture_array("main") 
                                
                if cam_mode != "focus":
                    dim_down()
                try:
                    print("Konvertiere Frame der RPI_Model_3 Kamera von BGR zu RGB...")
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                except Exception as e:
                    print(f"Fehler beim Konvertieren des Frames der RPI_Model_3 Kamera: {e}")


                metadata = picam2.capture_metadata()
                #print("Alle Metadaten:", metadata)
                #ExposureTime = metadata["ExposureTime"]
                #AnalogueGain = metadata["AnalogueGain"] 
                #awb_gains = metadata.get("AwbGains")
                #colour_gains = metadata.get("ColourGains")
                #colour_temp = metadata.get("ColourTemperature")
                #red_gain = colour_gains[0]
                #blue_gain = colour_gains[1]                 
                print("Metadaten gelesen") 
                Kamera_RPI_Status = 1  
                break
        
            except Exception as e:
                cam_Initiliase_tries +=1
                picam2.stop()
                picam2.close() 
                if cam_Initiliase_tries > 5:
                    print(cam_Initiliase_tries)
                    show_message("err_1a",lang=lang,tries = cam_Initiliase_tries)
                    print(f"Fehler beim Abrufen des Frames: {e}")                            
                    print(f"Prüfe Kamera Verbindung und Stromversorgung. Versuch {cam_Initiliase_tries}")



    picam2.stop()
    picam2.close() # shutdown camera
 

    if cam_Initiliase_tries > 90:
        print(f"Kamera nach {cam_Initiliase_tries} Versuchen nicht initalisiert")
        log_schreiben(f"Kamera nach {cam_Initiliase_tries} Versuchen nicht initalisiert", log_mode=log_mode)
        Kamera_RPI_Status = 0
        show_message("cam_3",lang=lang)    
        time.sleep(5)
        if not error_details:
            error_details = f"Kamera nach {cam_Initiliase_tries} Versuchen nicht initalisiert"   
        log_schreiben(f"Fehlerdetails: {error_details}", log_mode=log_mode)
        error_message(1,error_details,log_mode)     
        print(f"Fehler beim Abrufen des Frames: {error_details}")
        print("Prüfe Kamera Verbindung")

    if expected_camera not in ["RPI_HQ","RPI_Module_3"]:
                log_schreiben("Unbekannte Raspberry Kamera erkannt.", log_mode)
                Kamera_RPI_Status = 0
            
    print("Frame aufnahme beendet")
    return frame,Kamera_RPI_Status, power_vis, metadata, red_gain, blue_gain



def snap_image_rpi(file_extension, cam_mode, Kamera_Fehlerserie, log_mode, expected_camera, Exposure, Gain=1.0, focus=5.3, sn = ""):
    """
    Nimmt ein Bild mit der Raspberry Pi Cam auf
    
        :file_extension (str): z.B. "jpg"
        :Kamera_Fehlerserie (int): numerischer Parameter (nicht im Dateinamen)
        :expected_camera: RPI_HQ oder RPI_Module_3
        :Exposure (int): Belichtungszeit in Millisekunden
        :param cam_mode: "display" für lokale ausgabe; "log" für speichern in der schleife; "kamera_test" für Kameratest,
    """
    print(f"erwartetes Kamera Modul:{expected_camera}")

    awb_mode = "auto"
    status_picam = 0
    power_on = 0
    code = 000
    image_file = ""
    Bild_erfolgreich_gespeichert = False
    hardware = get_device_info("hardware")

    avg_brightness, good_exposure = "---", False
    image_correction = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","capture_mode","gamma_correction")

    if expected_camera == "RPI_Module_3":
        gamma = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_Module_3","gamma_value")
        compression_quality = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_Module_3","compression_quality")
    elif expected_camera == "RPI_HQ":
        gamma = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_HQ","gamma_value")
        compression_quality = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_HQ","compression_quality")

    focus = round(focus,2)

    ordnerpfad = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","general","current_folder")
    
    if cam_mode != "kamera_test":
        project_name,province, Kreis_code, sensor_id = get_Lepmon_code(log_mode)
        now = datetime.now()
        if now.strftime('%Y') < '2026':
            now = Zeit_überschrieben(log_mode="log")
        code = f"{project_name}{sensor_id}_{province}_{Kreis_code}_{now.strftime('%Y')}-{now.strftime('%m')}-{now.strftime('%d')}_T_{now.strftime('%H%M')}"
        image_file = f"{code}.{file_extension}"
        dateipfad = os.path.join(ordnerpfad, image_file)
    
    if cam_mode == "kamera_test":
        print(f"Ordner:{ordnerpfad}")
        if not os.path.exists(ordnerpfad):
            ordnerpfad = erstelle_ordner(log_mode, expected_camera)
            print(f"Ordner '{ordnerpfad}' wurde erstellt.") 
        if expected_camera == "RPI_Module_3": #imx708  
            image_file = f"{expected_camera}_{Exposure}_{Gain}_{focus}.jpg"
        elif expected_camera == "RPI_HQ": # imx477
            image_file = f"{expected_camera}_{Exposure}_{Gain}.jpg"
        dateipfad = os.path.join(ordnerpfad, image_file)
        print(f"Kamera Test Bild wird gespeichert in: {dateipfad}")
        

    if cam_mode == "Diagnose":
        dateipfad = f"{ordnerpfad}/Lepmon_Diagnose_{sn}_Testbild.jpg"
        print(f"Kamera Diagnose Bild wird gespeichert in: {dateipfad}")



    if cam_mode == "display":
        show_message("cam_4",lang=lang)
        time.sleep(1)
        show_message("cam_5",lang=lang)
        LepiLED_start("show")
        ordnerpfad,_ = get_usb_path(log_mode)
        dateipfad = "Testbild.jpg"
        dateipfad = os.path.join(ordnerpfad, dateipfad)
        log_schreiben(f"Dateipfad für Testbild: {dateipfad}", log_mode=log_mode)
    




    # prüfen ob Ordnerpfad existiert, außer im display Modus, da hier nur ein Testbild gespeichert wird und der Ordner nicht zwingend vorhanden sein muss

    if not os.path.exists(ordnerpfad) and cam_mode != "display":
        if ordnerpfad == "":
            ordnerpfad = erstelle_ordner(log_mode, Cameramodel = "None")
            write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "current_folder", ordnerpfad)
            print(f"Ordnerpfad war leer, neuer Ordner erstellt: {ordnerpfad}")
            print("Skript neu starten, um mit dem neuen Ordner zu arbeiten.")
        error_message(3, f"USB-Stick nicht gefunden: {ordnerpfad}", log_mode)
        print(f"Fehler: USB-Stick nicht gefunden: {ordnerpfad}")
        Status_Kamera = 0
       
        return code, dateipfad, Status_Kamera, power_on, Kamera_Fehlerserie, avg_brightness, good_exposure, Exposure, Gain, None, None

    # Abrufen des Frames in Abhängigkeit vom Kameramodus

    if cam_mode == "display":
        log_schreiben("Versuche Frame von Kamera abzurufen...", log_mode=log_mode)
        frame,Kamera_RPI_Status, power_vis, metadata, red_gain, blue_gain = get_frame_RPI(expected_camera, cam_mode,log_mode, Exposure, Gain, compression_quality, focus)
        show_message("cam_6",lang=lang) 
        LepiLED_ende("show")
        if frame is None:
            error_message(1, "Fehler beim Abrufen des Frames", log_mode)
        elif frame is not None:
            log_schreiben("Frame erfolgreich von Kamera abgerufen", log_mode=log_mode)
            try:
                cv2.imwrite(dateipfad, frame)
                log_schreiben(f"Testbild erfolgreich gespeichert:{dateipfad}", log_mode=log_mode)
                show_message("cam_7", lang=lang)
                os.remove(dateipfad)
                log_schreiben(f"Testbild vom Speicher gelöscht: {dateipfad}", log_mode=log_mode)
                log_schreiben("Kamera Zugriff erfolgreich", log_mode=log_mode)
            except Exception as e:
                print(f"Kamerafehler:{e}")
                error_message(3, f"Bild konnte nicht gespeichert werden: {dateipfad}", log_mode)
                log_schreiben(f"Fehlerdetails: {e}", log_mode=log_mode)
                Status_Kamera = 0




    if cam_mode == "Diagnose" or cam_mode == "kamera_test":
        frame,Kamera_RPI_Status, power_vis, metadata, red_gain, blue_gain = get_frame_RPI(expected_camera, cam_mode,log_mode, Exposure, Gain, compression_quality, focus)
        show_message("cam_6",lang=lang) 
        LepiLED_ende("show")
        if image_correction:
            print("Wende Gamma Korrektur an für Belichtungsoptimierung...")
            frame = gamma_correction(frame, gamma=gamma)
            print("Gamma Korrektur angewendet")
        try:
            print("Drehe Frame um 180 Grad...") 
            frame = cv2.rotate(frame, cv2.ROTATE_180)
        except Exception as e:
            print(f"Fehler beim Drehen des Frames um 180 Grad: {e}")
            log_schreiben(f"Fehler beim Drehen des Frames um 180 Grad: {e}", log_mode=log_mode)
        time.sleep(.5)

        frame = apply_flat(frame, log_mode)

        try:
            cv2.imwrite(dateipfad, frame)
            print(f"Bild erfolgreich gespeichert!\nPfad: {dateipfad}")
            Status_Kamera = 1
            Kamera_Fehlerserie = 0
            log_schreiben(f"Bild gespeichert: {dateipfad}", log_mode=log_mode)

        except Exception as e:
                print(f"Kamerafehler:{e}")
                log_schreiben(f"Bild gespeichert: {dateipfad}", log_mode=log_mode)  
                Status_Kamera = 0
                Kamera_Fehlerserie += 1        

        try:
            _, _, _, power_cam, _ = get_power()
            if hardware in ["Pro_Gen_1", "Pro_Gen_2"]:
                print("Stromverbrauch der Visible LED kann auf diesem ARNI-Modell nicht gemessen werden.")
                power_on = "---"
            elif hardware in ["Pro_Gen_3", "Pro_Gen_4", "CSL_Gen_1", "CSS_Gen_1"]:
                power_on = round(power_vis - power_cam, 2)
            time.sleep(0.1)
        except Exception as e:
            power_on = "---"
            log_schreiben(f"Fehler beim Messen des Stromverbrauchs der Visible LED: {e}", log_mode=log_mode)

        try: 
            Bild_erfolgreich_gespeichert = check_image(dateipfad, log_mode = "log")
            if Bild_erfolgreich_gespeichert:
                print("Foto Sanity Check bestanden")
            elif not Bild_erfolgreich_gespeichert:
                print("Foto Sanity nicht Check bestanden")
        except Exception as e:
            log_schreiben(f"Fehler bei der Bildprüfung: {e}", log_mode=log_mode)



    if cam_mode == "log":
        _, now, _ = Zeit_aktualisieren(log_mode=log_mode)
        sanity_tries = 0

        while (not Bild_erfolgreich_gespeichert) and (sanity_tries < 3):
            print(f"Versuch {sanity_tries + 1}: Bildaufnahme und Speicherung läuft...")

            now_dt = datetime.strptime(now, "%H:%M:%S")
            write_timestamp(0x07E0)
            show_message("blank", lang=lang)

            frame,Kamera_RPI_Status, power_vis, metadata, red_gain, blue_gain = get_frame_RPI(expected_camera, cam_mode,log_mode, Exposure, Gain, compression_quality, focus)

            if frame is not None:
                if image_correction:
                    print("Wende Gamma Korrektur an für Belichtungsoptimierung...")
                    frame = gamma_correction(frame, gamma=gamma)

                try:
                    print("Drehe Frame um 180 Grad...") 
                    frame = cv2.rotate(frame, cv2.ROTATE_180)
                except Exception as e:
                    print(f"Fehler beim Drehen des Frames um 180 Grad: {e}")
                    log_schreiben(f"Fehler beim Drehen des Frames um 180 Grad: {e}", log_mode=log_mode)
                time.sleep(.5)

                frame = apply_flat(frame, log_mode)


            
                Kamera_Fehlerserie = 0
                try:
                    cv2.imwrite(dateipfad, frame)
                    print(f"Bild erfolgreich gespeichert!\nPfad: {dateipfad}")
                    Status_Kamera = 1
                    Kamera_Fehlerserie = 0
                    log_schreiben(f"Bild gespeichert: {dateipfad}", log_mode=log_mode)

                except Exception as e:
                    print(f"Kamerafehler:{e}")
                    error_message(3, f"Bild konnte nicht gespeichert werden: {dateipfad}", log_mode)
                    Status_Kamera = 0
                    Kamera_Fehlerserie += 1
                
                avg_brightness, Exposure, Gain, good_exposure  = calculate_Exposure_and_gain(frame, Exposure, Gain, expected_camera, log_mode) 
                avg_brightness = round(avg_brightness,0)


                try: 
                    Bild_erfolgreich_gespeichert = check_image(dateipfad, log_mode = "log")
                    if Bild_erfolgreich_gespeichert:
                        print("Foto Sanity Check bestanden")
                        break
                    elif not Bild_erfolgreich_gespeichert:
                        sanity_tries += 1

                except Exception as e:
                    print(f"Fehler bei der Bildprüfung: {e}")
                    sanity_tries += 1


            if frame is None:
                Kamera_Fehlerserie += 1
                log_schreiben("Kein Frame zum Speichern vorhanden", log_mode)
            



  
    try:
        xml_dateiname = os.path.basename(ordnerpfad)
        xml_zieldatei = os.path.join(ordnerpfad, f"{xml_dateiname}_Kameraeinstellungen.xml")
        if not os.path.exists(xml_zieldatei) and metadata is not None and not cam_mode in ["Diagnose", "display", "kamera_test"]:
            metadata_xml = dict_to_xml("metadata", metadata)
            tree = ET.ElementTree(metadata_xml)
            tree.write(xml_zieldatei, encoding="utf-8", xml_declaration=True)
            checklist(xml_zieldatei, log_mode, algorithm="md5")
            log_schreiben(f"Kameraeinstellungen geschrieben in: {xml_zieldatei}", log_mode)
    except Exception as e:
        log_schreiben(f"Fehler beim Schreiben der Kameraeinstellungen: {e}", log_mode)

    try:
        _, _, _, power_cam, _ = get_power()
        if hardware in ["Pro_Gen_1", "Pro_Gen_2"]:
            print("Stromverbrauch der Visible LED kann auf diesem ARNI-Modell nicht gemessen werden.")
            power_on = "---"
        elif hardware in ["Pro_Gen_3", "Pro_Gen_4", "CSL_Gen_1", "CSS_Gen_1"]:
            power_on = round(power_vis - power_cam, 2)
            time.sleep(0.1)
    except Exception as e:
        power_on = "---"
        log_schreiben(f"Fehler beim Messen des Stromverbrauchs der Visible LED: {e}", log_mode=log_mode)


    return code, dateipfad, Kamera_RPI_Status, power_on, Kamera_Fehlerserie, avg_brightness, good_exposure, Exposure, Gain, red_gain, blue_gain
    



if __name__ == "__main__":
    camera = get_device_info("camera")
    
    '''if camera == "RPI_HQ":
        Exposure = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_HQ","initial_exposure_10"))/10
        Gain = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_HQ","initial_gain_10"))/10
        compression_quality = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_HQ","compression_quality")
    '''
    if camera == "RPI_Module_3":
        Exposure = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_Module_3","initial_exposure_10"))/10
        Gain = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_Module_3","initial_gain_10"))/10
        compression_quality = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_Module_3","compression_quality")

    elif camera not in ["AV__Alvium_1800_U-2050","RPI_Module_3","RPI_HQ"]:
        print(f"unbekannte Kamera gefunden:{camera}.")
    time.sleep(2)

    '''
    if camera == "RPI_HQ":
        code, dateipfad, Kamera_RPI_Status, power_on, Kamera_Fehlerserie, avg_brightness, good_exposure, Exposure, Gain, red_gain, blue_gain = snap_image_rpi("jpg","kamera_test", 0, "manual", camera, Exposure, Gain)
    '''   

                                                                                        
    if camera == "RPI_Module_3":
        #focus = set_focus_rpi_cam()
        focus = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_Module_3","focus")
        code, dateipfad, Kamera_RPI_Status, power_on, Kamera_Fehlerserie, avg_brightness, good_exposure, Exposure, Gain, red_gain, blue_gain = snap_image_rpi("jpg","kamera_test", 0, "manual", camera, 2, 2, focus = focus, sn = "")
