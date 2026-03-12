from Camera_AV import *
from Camera_RPI import *
import time
import csv
from sensor_data import *
from service import *
from csv_handler import erstelle_und_aktualisiere_csv
from logging_utils import *
from datetime import datetime
from datetime import datetime
from image_quality_check import *
from times import *
from fram_direct import *
import os
from hardware import *
from OLED_panel import *

log_mode = "log"

_, lokale_Zeit,_ = Zeit_aktualisieren(log_mode)
_, experiment_end_time,_, _ = get_experiment_times()
experiment_start_time = "22:00:00"

camera = get_device_info('camera')



if __name__ == "__main__":
    display_text("Belichtungsreihe", f"{camera}", "", sleeptime =0)
    experiment_start_time = datetime.strptime(experiment_start_time, "%H:%M:%S")
    experiment_end_time = datetime.strptime(experiment_end_time, "%H:%M:%S")
    lokale_Zeit = datetime.strptime(lokale_Zeit, "%H:%M:%S")

    if camera == "AV__Alvium_1800_U-2050":
        minimal_gain = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","AV__Alvium_1800_U-2050","minimal_gain_10"))/10
        maximal_gain = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","AV__Alvium_1800_U-2050","maximal_gain_10"))/10
        step_gain = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","AV__Alvium_1800_U-2050","step_gain_10"))/10
        maximal_exposure = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","AV__Alvium_1800_U-2050","maximal_exposure"))
        minimal_exposure = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","AV__Alvium_1800_U-2050","minimal_exposure"))
        step_exposure = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","AV__Alvium_1800_U-2050","step_exposure"))

    elif camera == "RPI_Module_3":
        minimal_gain = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_Module_3","minimal_gain_10"))/10
        maximal_gain = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_Module_3","maximal_gain_10"))/10
        step_gain = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_Module_3","step_gain_10"))/10
        maximal_exposure = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_Module_3","maximal_exposure_10"))/10
        minimal_exposure = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_Module_3","minimal_exposure_10"))/10
        step_exposure = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_Module_3","step_exposure_10"))/10
        focus = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_Module_3","focus")
    
    elif camera == "RPI_HQ":
        minimal_gain = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_HQ","minimal_gain_10"))/10
        maximal_gain = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_HQ","maximal_gain_10"))/10
        step_gain = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_HQ","step_gain_10"))/10
        maximal_exposure = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_HQ","maximal_exposure_10"))/10
        minimal_exposure = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_HQ","minimal_exposure_10"))/10
        step_exposure = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_HQ","step_exposure_10"))/10

    if not experiment_start_time <= lokale_Zeit <= experiment_end_time:
        print(" keine Nacht, warte bis zum Experimentzeitraum")
        wait = experiment_start_time - lokale_Zeit
        wait_seconds = wait.total_seconds()
        print(f" wartezeit in Sekunden: {wait_seconds}")
        display_text("warte:", f"{wait_seconds} Sekunden", "", sleeptime =0)
        if wait_seconds > 0:
            time.sleep(wait_seconds + 60)  # wartezeit plus 1 Minute Puffer
            time.sleep(1)
            display_text("", "", "", sleeptime =0)

    RPI_time(log_mode)
    jetzt_local = datetime.now().strftime("%Y-%m-%d--%H_%M_%S")
    
    aktueller_nachtordner = erstelle_ordner("kamera_test", camera)
    print(f"Erstelle Ordner für Belichtungsreihe: {aktueller_nachtordner}")
    initialisiere_logfile("manual")
    
    
    if camera == "RPI_Module_3":
        focus = set_focus_rpi_cam()
            
    
    #### Aufnahmeschleife ####
    if read_fram(0x058F, 1) != b'\x01':
        print(f"Starte Belichtungsreihe für Kalibrierung der Kamera {camera}...")
        #if True: # für Fokusreihe
        for gain in range(int(minimal_gain * 10), int(maximal_gain * 10) + 1, int(step_gain * 10)):
            time.sleep(5)
            gain = gain / 10.0
            
            RPI_time(log_mode)
            metadata = {}
            now = datetime.now()
            
            for exposure in range(minimal_exposure, maximal_exposure, step_exposure):
                exposure = int(exposure)
                focus = 5.1 
        
            #for focus in range(45, 58):
            #    focus = focus / 10
            #    exposure = 5
            #    gain = 0.7
                
                time.sleep(2)
                image_is_sharp = False
                image_is_complete = False
                if camera == "AV__Alvium_1800_U-2050":
                    try:
                        while not image_is_complete:
                            print("Probebild mit AV Kamera")
                            dateipfad = "---"
                            code, dateipfad, Status_Kamera, power_on, Kamera_Fehlerserie, avg_brightness, good_exposure, Exposure, Gain  = snap_image_AV("jpg", "kamera_test", 0, log_mode, Exposure=exposure, Gain=gain)
                            focus = "manual"
                            image_is_complete = check_image(current_image, camera, log_mode)
                    except Exception as e:
                        print(f"Fehler beim Aufnehmen des Bildes mit Gain={gain} und Belichtungszeit={exposure}: {e}")

                elif camera == "RPI_Module_3":
                    dateipfad = "---"
                    try:
                        #while not image_is_complete or not image_is_sharp:
                            print("Probebild mit Camera Module 3")
                            
                            code, dateipfad, Kamera_RPI_Status, power_on, Kamera_Fehlerserie, avg_brightness, good_exposure, Exposure, Gai, red_gain, blue_gain = snap_image_rpi("jpg","kamera_test", 0, "manual", camera, Exposure=exposure, Gain=gain)
                            image_is_complete = check_image(current_image, camera, log_mode)
                        
                            if dateipfad != "---":
                                try:
                                    image_is_sharp, variance =check_focus(dateipfad, camera, log_mode)
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
                
                elif camera == "RPI_HQ":   
                    dateipfad = "---" 
                    try:
                        
                        while not image_is_complete:
                            print("Probebild mit HQ Kamera")
                                        
                            code, dateipfad, Kamera_RPI_Status, power_on, Kamera_Fehlerserie, avg_brightness, good_exposure, Exposure, Gain, red_gain, blue_gain = snap_image_rpi("jpg","kamera_test", 0, "manual", camera, Exposure=exposure, Gain=gain)
                            focus = "manual"
                            image_is_complete = check_image(current_image, camera, log_mode)
                    except Exception as e:
                        print(f"Fehler beim Aufnehmen des Bildes mit Gain={gain} und Belichtungszeit={exposure}: {e}")
                         
                            
                elif camera not in ["AV__Alvium_1800_U-2050", "RPI_HQ", "RPI_Module_3"]:
                    print("KAMERA NICHT GEFUNDEN")
                    time.sleep(5)
                if dateipfad != "---":
                    helligkeit, new_exposure, new_gain, good_exposure = calculate_Exposure_and_gain(dateipfad, exposure, gain, camera)
                        
                    filename = os.path.basename(dateipfad)

                    update_sensor_data(metadata,"time", now)
                    update_sensor_data(metadata,"filename", filename)
                    update_sensor_data(metadata,"camera", camera)
                    update_sensor_data(metadata,"gain", gain)
                    update_sensor_data(metadata,"exposure", exposure)
                    update_sensor_data(metadata,"avg_brightness", helligkeit)
                    update_sensor_data(metadata,"red_gain", red_gain)
                    update_sensor_data(metadata,"blue_gain", blue_gain)
                    update_sensor_data(metadata,"focus", focus)
                    erstelle_und_aktualisiere_csv(metadata, log_mode="kamera_test")
        print("Belichtungsreihe abgeschlossen.")
        write_fram_bytes(0x058F, 1) == b'\x01'
        os.system("sudo shutdown -r 61")




#############
# Schlaf Befehl in Zeile 63 auskommentieren, um die Wartezeit zu aktivieren.



# kein quality Check (Bild vollständig, schwarze Pixel) --> Zeile 116 auskommentieren
#############