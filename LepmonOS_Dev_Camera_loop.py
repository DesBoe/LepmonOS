from Camera import *
from LepmonOS_Service_camera_rpi import *
import time
import csv
from sensor_data import *
from service import *
from csv_handler import erstelle_und_aktualisiere_csv
from logging_utils import *
from datetime import datetime
from datetime import datetime

gain_min = 1
gain_max = 10
gain_step = .1

exposure_min = 90
exposure_max = 180
exposure_step = 15

focus = 1
log_mode = "log"
sensor = False


def find_camera():
    erwartete_Kamera = input(
    "angeschlossene Kamera:\n'a': Allied Vision\n'r': eine Raspberry Kamera\n")
    
    #### Abfrage Sensor Modell ####
    print("Ermittle angeschlossene Kamera...")
    
    if erwartete_Kamera == "a":
        print("Suche nach AV Kameras...")
        sensor = snap_image("jpg", "Sensor_Suche", 0, log_mode, 140, 7)
        if sensor == "imx183":
            print(f"Verwendetes Kameramodell AV Kamera mit Sensortyp: {sensor}")
        
    elif erwartete_Kamera == "r":
        print("Suche nach Raspberry Pi Kameras...")
        sensor, _, _ = check_connected_camera()
        if sensor == "imx708" or sensor == "imx477":
            print(f"Verwendetes Kameramodell: {sensor}")
        else:
            print("Keine kompatible Kamera erkannt. Beende Programm.")
            exit()
    return sensor
    
        
if __name__ == "__main__":
    '''
    delay = input("Wartezeit vor Beginn der Belichtungsreihe in Stunden:")
    delay_seconds = float(delay) * 3600
    print("wartezeit...")
    time.sleep(delay_seconds)
    print("beginne Belichtungsreihe")
    '''
    RPI_time(log_mode)
    jetzt_local = datetime.now().strftime("%Y-%m-%d--%H_%M_%S")
    
    aktueller_nachtordner = erstelle_ordner("kamera_test", jetzt_local)
    print(f"Erstelle Ordner für Belichtungsreihe: {aktueller_nachtordner}")
    initialisiere_logfile("manual")
    
    sensor = find_camera()
    

            
    
    #### Aufnahmeschleife ####

    for gain in range(int(gain_min * 10), int(gain_max * 10) + 1, int(gain_step * 10)):
        gain = gain / 10.0
        RPI_time(log_mode)
        metadata = {}
        now = datetime.now()
        for exposure in range(exposure_min, exposure_max, exposure_step):
            time.sleep(2)
            image_is_sharp = False
            image_is_complete = False
            
            if sensor == "" or sensor == "imx183": # AV
                try:
                    while not image_is_complete:
                        print("Probebild mit AV Kamera")
                        dateipfad = "---"
                        code, dateipfad, Status_Kamera, power_on, Kamera_Fehlerserie, sensor, length, height, avg_brightness, good_exposure, _, _  = snap_image("jpg", "kamera_test", 0, log_mode, Exposure=exposure, Gain=gain)
                        image_is_complete = check_image(dateipfad, sensor, length, height)
                except Exception as e:
                    print(f"Fehler beim Aufnehmen des Bildes mit Gain={gain} und Belichtungszeit={exposure}: {e}")


            elif sensor == "" or sensor == "imx708": # Camera Module 3
                try:
                    while not image_is_complete or not image_is_sharp:
                        print("Probebild mit Camera Module 3")
                        dateipfad = "---"
                                                                                                                
                        code, dateipfad, status_picam, power_on, Kamera_Fehlerserie, sensor, length, height = snap_image_rpi("jpg", "kamera_test", "manual", 0, Exposure=exposure, Gain=gain)
                        image_is_complete = check_image(dateipfad, sensor, length, height)
                        
                        if dateipfad != "---":
                            try:
                                image_is_sharp, variance =check_focus(dateipfad, threshold=100.0)
                            except Exception as e:
                                print(f"Fehler beim Überprüfen der Bildschärfe: {e}")
                                
                        if dateipfad != "---" and not image_is_sharp:
                            try:
                                focus = set_focus_rpi_cam()
                                print(f"Neuer Fokuswert gesetzt: {focus}")
                            except Exception as e:
                                print(f"Fehler beim Setzen des Fokuswerts: {e}")
                            
                except Exception as e:
                    print(f"Fehler beim Aufnehmen des Bildes mit Gain={gain} und Belichtungszeit={exposure}: {e}")
                
                
            elif sensor == "" or sensor == "imx477": # HQ Camera
                try:
                    while not image_is_complete:
                        print("Probebild mit HQ Kamera")
                        dateipfad = "---"              
                        code, dateipfad, status_picam, power_on, Kamera_Fehlerserie, sensor, length, height = snap_image_rpi("jpg", "kamera_test", "manual", 0, Exposure=exposure, Gain=gain)
                        image_is_complete = check_image(dateipfad,sensor, length, height,"kamera_test")
                except Exception as e:
                    print(f"Fehler beim Aufnehmen des Bildes mit Gain={gain} und Belichtungszeit={exposure}: {e}")
                        
                        
            if dateipfad != "---":
                helligkeit, new_exposure, new_gain, good_exposure = calculate_Exposure_and_gain(dateipfad, exposure, gain)
                    
                filename = os.path.basename(dateipfad)

                update_sensor_data(metadata,"time", now)
                update_sensor_data(metadata,"filename", filename)
                update_sensor_data(metadata,"Sensor", sensor)
                update_sensor_data(metadata,"gain", gain)
                update_sensor_data(metadata,"exposure", exposure)
                update_sensor_data(metadata,"avg_brightness", helligkeit)
                erstelle_und_aktualisiere_csv(metadata, log_mode="kamera_test")
    print("Belichtungsreihe abgeschlossen.")