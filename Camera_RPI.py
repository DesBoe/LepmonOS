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
from hardware import get_device_info
from sensor_data import get_power
import numpy as np
import gc

def dict_to_xml(tag, d):
    elem = ET.Element(tag)
    for key, val in d.items():
        child = ET.SubElement(elem, key)
        child.text = str(val)
    return elem


def get_frame_RPI(expected_camera, cam_mode,log_mode, Exposure, Gain, compression_quality, focus= 5.3):
    red_gain, blue_gain = None, None
    cam_Initiliase_tries = 0
    power_vis = "---"
    Kamera_RPI_Status = 0
    frame = None
    metadata = ""



    if cam_mode == "display":
            show_message("cam_1",lang=lang)
            print("nehme Frame auf")

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



    if expected_camera == "RPI_HQ": # imx477
        print(f"Konfiguriere {expected_camera}...")
        #picam2.options["quality"] = compression_quality
    

        while cam_Initiliase_tries <= 90:
            time.sleep(0.1)
            print(cam_Initiliase_tries)
            picam2 = None
            picam2 = Picamera2()
            camera_config = picam2.create_still_configuration(main={"size": (4056, 3040)})
            picam2.configure(camera_config)
            try:
                picam2.start()
                picam2.set_controls({"AnalogueGain": Gain, 
                                "ExposureTime": Exposure * 1000, 
                                "AwbEnable": False, 
                                #"AwbMode": controls.AwbModeEnum.Auto,
                                "ColourGains": (3.3, 1.5)
                                })
                time.sleep(.5)
                if cam_mode != "focus":
                    dim_up()
                    _, _, _, power_vis, _ = get_power()

                frame = picam2.capture_array("main") 

                if cam_mode != "focus":
                    dim_down()
                    
                try:
                    print("Konvertiere Frame der RPI_HQ Kamera von BGR zu RGB...")
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                except Exception as e:
                    print(f"Fehler beim Konvertieren des Frames der RPI_HQ Kamera: {e}")
                metadata = picam2.capture_metadata()
                #print("Alle Metadaten:", metadata)
                #ExposureTime = metadata["ExposureTime"]
                #AnalogueGain = metadata["AnalogueGain"] 
                #awb_gains = metadata.get("AwbGains")
                colour_gains = metadata.get("ColourGains")
                #colour_temp = metadata.get("ColourTemperature")
                red_gain = colour_gains[0]
                blue_gain = colour_gains[1] 
                #print(f"red_gain: {red_gain}, blue_gain: {blue_gain}")                
                print("Metadaten gelesen") 
                Kamera_RPI_Status = 1  
                break
                
            except Exception as e:
                cam_Initiliase_tries +=1
                picam2.stop()
                picam2.close() 
                if cam_Initiliase_tries > 5:
                    show_message("err_1a",lang=lang,tries = cam_Initiliase_tries)
                    print(f"Fehler beim Abrufen des Frames: {e}")  
            

            


    picam2.stop()
    picam2.close() # shutdown camera
 

    if cam_Initiliase_tries > 90:
        print(f"Kamera nach {cam_Initiliase_tries} Versuchen nicht initalisiert")
        log_schreiben(f"Kamera nach {cam_Initiliase_tries} Versuchen nicht initalisiert", log_mode=log_mode)
        Kamera_RPI_Status = 0
        show_message("cam_3",lang=lang)    
        time.sleep(5)
        e = f"Kamera nach {cam_Initiliase_tries} Versuchen nicht initalisiert"   
        error_message(1,e,log_mode)     
        print(f"Fehler beim Abrufen des Frames: {e}")
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
        code = f"{project_name}{sensor_id}_{province}_{Kreis_code}_{now.strftime('%Y')}-{now.strftime('%m')}-{now.strftime('%d')}_T_{now.strftime('%H%M')}"
        image_file = f"{code}.{file_extension}"
        dateipfad = os.path.join(ordnerpfad, image_file)
    
    if cam_mode == "kamera_test":
        if not os.path.exists(ordnerpfad):
            erstelle_ordner(log_mode, expected_camera)
            print(f"Ordner '{ordnerpfad}' wurde erstellt.") 
        if expected_camera == "RPI_Module_3": #imx708  
            image_file = f"{expected_camera}_{Exposure}_{Gain}_{focus}.jpg"
        elif expected_camera == "RPI_HQ": # imx477
            image_file = f"{expected_camera}_{Exposure}_{Gain}.jpg"
        dateipfad = os.path.join(ordnerpfad, image_file)
        print(f"Kamera Test Bild wird gespeichert in: {dateipfad}")

    if cam_mode == "Diagnose":
        dateipfad = f"{ordnerpfad}/Lepmon_Diagnose_{sn}_Testbild.jpg"
        print(f"Kamera Test Bild wird gespeichert in: {dateipfad}")



    if cam_mode == "display":
        show_message("cam_4",lang=lang)
        time.sleep(1)
        show_message("cam_5",lang=lang)
        LepiLED_start("show")
        ordnerpfad,_ = get_usb_path(log_mode)
        dateipfad = "Testbild.jpg"
        dateipfad = os.path.join(ordnerpfad, dateipfad)
        print(f"Ordnerpfad für Testbild:{dateipfad}")
    
    #### Frage Frame der RPI Cam ab ####
    frame,Kamera_RPI_Status, power_vis, metadata, red_gain, blue_gain = get_frame_RPI(expected_camera, cam_mode,log_mode, Exposure, Gain, compression_quality, focus)
                                                                 


    if frame is not None:
        Kamera_Fehlerserie = 0
        if cam_mode == "log":
            avg_brightness, Exposure, Gain, good_exposure  = calculate_Exposure_and_gain(frame, Exposure, Gain, expected_camera, log_mode) 
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
            return code, dateipfad, Kamera_RPI_Status, power_on, Kamera_Fehlerserie, avg_brightness, good_exposure, Exposure, Gain, red_gain, blue_gain
    
    if frame is not None:
        if expected_camera == "RPI_Module_3" and frame is not None:
            try: 
                frame = cv2.rotate(frame, cv2.ROTATE_180)
                cv2.imwrite(dateipfad, frame)
                log_schreiben(f"Bild für imx708 um 180 Grad gedreht und gespeichert: {dateipfad}", log_mode)
            except Exception as e:
                log_schreiben(f"Fehler beim Drehen des Bildes um 180 Grad: {e}", log_mode)

        try:
            print(dateipfad)
            cv2.imwrite(dateipfad, frame)

            Kamera_RPI_Status = 1
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
            Kamera_RPI_Status = 0
            Kamera_Fehlerserie += 1
            return code, dateipfad, Kamera_RPI_Status, power_on, Kamera_Fehlerserie, avg_brightness, good_exposure, Exposure, Gain, red_gain, blue_gain
    elif frame is None:
        print("Kein Bild zum Speichern vorhanden")       
                        

    if cam_mode == "log":
        write_timestamp(0x07E0)

  
    try:
        xml_dateiname = os.path.basename(ordnerpfad)
        xml_zieldatei = os.path.join(ordnerpfad, f"{xml_dateiname}_Kameraeinstellungen.xml")
        if not os.path.exists(xml_zieldatei) and metadata is not None and not cam_mode in ["Diagnose", "display"]:
            metadata_xml = dict_to_xml("metadata", metadata)
            tree = ET.ElementTree(metadata_xml)
            tree.write(xml_zieldatei, encoding="utf-8", xml_declaration=True)
            checklist(xml_zieldatei, log_mode, algorithm="md5")
            log_schreiben(f"Kameraeinstellungen geschrieben in: {xml_zieldatei}", log_mode)
    except Exception as e:
        log_schreiben(f"Fehler beim Schreiben der Kameraeinstellungen: {e}", log_mode)
  

    return code, dateipfad, Kamera_RPI_Status, power_on, Kamera_Fehlerserie, avg_brightness, good_exposure, Exposure, Gain, red_gain, blue_gain
    



if __name__ == "__main__":
    camera = get_device_info("camera")
    
    if camera == "RPI_HQ":
        Exposure = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_HQ","initial_exposure_10"))/10
        Gain = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_HQ","initial_gain_10"))/10
        compression_quality = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_HQ","compression_quality")

    if camera == "RPI_Module_3":
        Exposure = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_Module_3","initial_exposure_10"))/10
        Gain = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_Module_3","initial_gain_10"))/10
        compression_quality = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_Module_3","compression_quality")

    elif camera not in ["AV__Alvium_1800_U-2050","RPI_Module_3","RPI_HQ"]:
        print(f"unbekannte Kamera gefunden:{camera}.")
    time.sleep(2)


    if camera == "RPI_HQ":
        code, dateipfad, Kamera_RPI_Status, power_on, Kamera_Fehlerserie, avg_brightness, good_exposure, Exposure, Gain, red_gain, blue_gain = snap_image_rpi("jpg","kamera_test", 0, "manual", camera, Exposure, Gain)
        

                                                                                        
    if camera == "RPI_Module_3":
        #focus = set_focus_rpi_cam()
        focus = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_Module_3","focus")
        code, dateipfad, Kamera_RPI_Status, power_on, Kamera_Fehlerserie, avg_brightness, good_exposure, Exposure, Gain, red_gain, blue_gain = snap_image_rpi("jpg","kamera_test", 0, "manual", camera, Exposure, Gain, focus = focus)
