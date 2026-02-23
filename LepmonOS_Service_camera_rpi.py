#########################
#########################
# This file is obsolete #
#########################
#########################

import os
os.environ["QT_QPA_PLATFORM"] = "xcb"
from picamera2 import Picamera2, Preview

from json_read_write import get_value_from_section
from datetime import datetime
import time
from logging_utils import error_message
from libcamera import controls, Transform
import os
from image_quality_check import *
from service import *

from RPi_cam import check_connected_camera




def Preview_Picam2(width=800, flip="", timeout=10):
    """
    zeigt Vorschau im Display an
    :width: Weite in Pixeln, Default 800
    :flip: Drehung des Bildes horizontal und/oder vertical -  options: "v", "h", "vh" ""
    :timeout: Zeit in Sekunden, wie lange die Vorschau angezeigt wird, Default 10s
    """
    sensor, _, _ = check_connected_camera()
    picam2 = Picamera2()
    
    config = picam2.create_preview_configuration()
    picam2.configure(config)
    
    if flip == "h":
        transform = Transform(hflip=1)
    elif flip == "v":
        transform = Transform(vflip=1)
    elif flip == "vh" or flip == "hv":
        transform = Transform(hflip=1, vflip=1)
    else:
        transform = Transform()
    
    height = int(0.75 * width)
    picam2.start_preview(Preview.QTGL, x=100, y=200,
                         width=width, height=height,
                        transform=transform)
    if sensor is not None:
        if sensor == "imx708":
            print("imx708 Sensor erkannt.")
            picam2.set_controls({"AfMode": controls.AfModeEnum.Continuous,  #continius AF
                        #"AfMode": controls.AfModeEnum.Manual,       # manual af
                        #"LensPosition": 0.0,                        # manual af - Dioptrien
                        "ExposureTime": 10000,                      # Belichtungszeit in Mikrosekunden
                        "AnalogueGain": 1.0})      

        elif sensor == "imx477":
            print("imx477 Sensor erkannt.")
                 # Verstärkung / ISO

        else: 
            print("Unbekannter Sensor erkannt.")
    time.sleep(.1)
    picam2.start()
 
    picam2.title_fields = ["ExposureTime", "AnalogueGain"]
    
    '''
    with picam2.controls as controls:
        controls.ExposureTime = 20000
        controls.AnalogueGain = 0.9
    '''
    time.sleep(timeout)
    picam2.stop_preview()
    picam2.stop()
    picam2.close() 
    
    
def snap_image_rpi(file_extension, cam_mode, Kamera_Fehlerserie, log_mode, Exposure, Gain=1.0, focus=4.5):
    """
    Nimmt ein Bild mit der Raspberry Pi HQ Camera auf und speichert es als Testbild.
    
    Parameter:
        file_extension (str): z.B. "jpg"
        Kamera_Fehlerserie (int): numerischer Parameter (nicht im Dateinamen)
        Exposure (int): Belichtungszeit in Millisekunden
    """
    sensor, length, height = check_connected_camera()
    print(f" erkannter Sensor: {sensor}")
    compression_quality=95 #quality default 90 - JPEG quality level, where 0 is the worst quality and 95 is best.
    awb_mode = "auto"
    status_picam = 0
    camera_tries = 0
    power_on = 0
    code = 000
    
    if cam_mode != "kamera_test":
        project_name,province, Kreis_code, sensor_id = get_Lepmon_code(log_mode)
        ordnerpfad = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","general","current_folder")
        now = datetime.now()
        code = f"{project_name}{sensor_id}_{province}_{Kreis_code}_{now.strftime('%Y')}-{now.strftime('%m')}-{now.strftime('%d')}_T_{now.strftime('%H%M')}"
        image_file = f"{code}.{file_extension}"
        dateipfad = os.path.join(ordnerpfad, image_file)
    
    if cam_mode == "kamera_test":
        ordnerpfad = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","general","current_folder")
        print(f"Ordner:{ordnerpfad}")
        if not os.path.exists(ordnerpfad):
            erstelle_ordner(log_mode, Cameramodel = "RPi Kamera")
            print(f"Ordner '{ordnerpfad}' wurde erstellt.")        
        
        focus = round(focus,2)
    
    while status_picam == 0 and camera_tries < 90:
        try:
            picam2 = Picamera2()
            status_picam = 1
            camera_tries = 0
            print("RPI Kamera initialisiert")
        except Exception as e:
            if camera_tries== 90:
                print(f"Fehler beim Initialisieren der Pi Kamera nach {camera_tries} Versuchen: {e}")
                return code, dateipfad, status_picam, power_on, Kamera_Fehlerserie, sensor, length, height
        camera_tries += 1

    if status_picam == 1:
        if sensor == "imx708":    
            image_file = f"{sensor}_{Exposure}_{Gain}_{focus}.jpg"
            dateipfad = os.path.join(ordnerpfad, image_file)
            print(f"Kamera Test Bild wird gespeichert in: {dateipfad}")
            picam2.options["quality"] = compression_quality
            camera_config = picam2.create_still_configuration(main={"size": (4608, 2592)})
            picam2.configure(camera_config)
            picam2.start()
                     
            picam2.set_controls({"AnalogueGain": Gain, 
                             "ExposureTime": Exposure * 1000, 
                             "AwbEnable": True,
                             #"AfMode": controls.AfModeEnum.Continuous,
                             "AfMode": controls.AfModeEnum.Manual,
                            "LensPosition": focus  # Autofokus auf gefundenen Wert setzen
                             })
            time.sleep(3) # wait for settings to take effect



        elif sensor == "imx477":
            image_file = f"{sensor}_{Exposure}_{Gain}_{focus}.jpg"
            dateipfad = os.path.join(ordnerpfad, image_file)
            print(f"Kamera Test Bild wird gespeichert in: {dateipfad}")
            #picam2.options["quality"] = compression_quality
            camera_config = picam2.create_still_configuration(main={"size": (4056, 3040)})
            picam2.configure(camera_config)
            picam2.start()
            picam2.set_controls({"AnalogueGain": Gain, 
                             "ExposureTime": Exposure * 1000, 
                             "AwbEnable": True,
                             })
            time.sleep(3) # wait for settings to take effect
            
        else:
            print("sensor unbekannt")
            time.sleep(3)
            return code, dateipfad, status_picam, power_on, Kamera_Fehlerserie, sensor, length, height

        try:
            picam2.capture_file(dateipfad)
            metadata = picam2.capture_metadata()
            Kamera_Fehlerserie = 0   
            print(f"Bild gespeichert als {dateipfad} mit Exposure={Exposure} ms, Gain={Gain}, AWB={awb_mode}")

            ExposureTime = metadata["ExposureTime"]
            AnalogueGain = metadata["AnalogueGain"] 

        except Exception as e:
            print(f"Fehler beim Aufnehmen des Bildes: {e}")
            Kamera_Fehlerserie += 1
            ExposureTime ="None"
            AnalogueGain = "None"
            
        picam2.stop()
        picam2.close() # shutdown camera

        return code, dateipfad, status_picam, power_on, Kamera_Fehlerserie, sensor, length, height





if __name__ == "__main__":
    
    print("preview starten")
    '''
    try:
        Preview_Picam2(width=800, flip="", timeout=6)
    except Exception as e:
        print(f"Vorschau nicht Möglich: {e}")
    '''
    code, dateipfad, status_picam, power_on, Kamera_Fehlerserie, sensor, length, height = snap_image_rpi("jpg","kamera_test",0, "manual", Exposure=110, Gain=2)
    print(f"Sensor:{sensor}")
                                                                                        
    if sensor == "imx708":
        focus = set_focus_rpi_cam()
        code, dateipfad, status_picam, power_on, Kamera_Fehlerserie, sensor, length, height = snap_image_rpi("jpg","kamera_test","manual",0, Exposure=110, Gain=2, focus=focus)