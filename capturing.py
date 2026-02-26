from Lights import *
from Camera_AV import *
from Camera_RPI import *
from sensor_data import read_sensor_data
from times import *
from json_read_write import *
from service import *
from csv_handler import erstelle_und_aktualisiere_csv
from Lights import *
from lora import send_lora
from logging_utils import *
import shutil
import os
from datetime import timedelta, datetime
from wait import wait 
from fram_operations import *
import struct
import time
from GPIO_Setup import *
import math
from sensor_data import get_light
from usb_controller import remount_usb_drive
from Daylightsaving import daylight_saving_check
from service import *
from hardware import *

'''
from capturing_state import (
    set_capturing_active, 
    update_capture_progress, 
    increment_image_count,
    is_stop_requested,
    clear_stop_request
)
'''

def capturing(log_mode):
    überleiten_zu_shutdown = False

    gamma_correction = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","image_quality","gamma_correction")
    dusk_treshold = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "capture_mode", "dusk_treshold")
    interval = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "capture_mode", "interval")
    camera = get_device_info('camera')

    if camera == "RPI_Module_3":
        gamma_value = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_Module_3","gamma_value")
        Exposure = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_Module_3","initial_exposure_10"))/10
        gain = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_Module_3","initial_gain_10"))/10
        compression_quality = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_Module_3","compression_quality")
       
        focus = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "RPI_Module_3", "focus")
    elif camera == "RPI_HQ":
        gamma_value = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_HQ","gamma_value")
        Exposure = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_HQ","initial_exposure_10"))/10
        gain = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_HQ","initial_gain_10"))/10
        compression_quality = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","RPI_HQ","compression_quality")
    elif camera == "AV__Alvium_1800_U-2050":
        gamma_value = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","AV__Alvium_1800_U-2050","gamma_value")
        Exposure = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","AV__Alvium_1800_U-2050","initial_exposure"))
        gain = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","AV__Alvium_1800_U-2050","initial_gain_10"))/10


    print("starte Capturing")  
    '''
    # Signal that capturing is starting
    set_capturing_active(True)
    clear_stop_request()
    '''


    heater,Warteschleife = wait(log_mode)
    log_schreiben("##################################", log_mode)
    log_schreiben("##################################", log_mode)
    log_schreiben("Beginne Daten und Bildaufnahme",log_mode)
    if gamma_correction:
        log_schreiben(f"Aufgenommene frames werden mit Gamma Wert {gamma_value} aufgehellt", log_mode)

    # USB Speicherplatz prüfen
    try: 
        total_space_gb, used_space_gb, free_space_gb, used_percent, free_percent = get_disk_space(log_mode)
        log_schreiben(f"USB Speicher gesamt: {total_space_gb} GB",log_mode)
        log_schreiben(f"USB Speicher belegt: {used_space_gb} GB  {used_percent} %",log_mode)
        log_schreiben(f"USB Speicher frei:   {free_space_gb} GB  {free_percent} %",log_mode)

    except Exception as e:
        error_message(3,e, log_mode)

    try:
        send_lora(f"USB Speicher gesamt: {total_space_gb} GB\nUSB Speicher belegt: {used_space_gb} GB\nUSB Speicher frei:   {free_space_gb} GB")
    except:
        print(f"USB Speicherdaten nicht gesendet")
        pass

    try: 
        write_fram_bytes(0x0390, struct.pack('f', free_space_gb))
        print(f"freien Speicher im Ram gemerkt:{free_space_gb}")
    except Exception as e:
        print(f"Fehler beim Schreiben des freien Speichers in den RAM: {e}")

        
    # Zeiten laden  
    experiment_start_time, experiment_end_time, _, _ = get_experiment_times()
    _, sunrise, _ = get_sun()
    sunrise = sunrise.strftime('%H:%M:%S')

    Fang_begonnen = False
    UV_active = False
    Kamera_Fehlerserie = 0
    Bilder_mit_heizung = 0
    Heizung_active = False
    Night = False



    # Bildzahl
    try:

        _, lokale_Zeit,_ = Zeit_aktualisieren(log_mode) # Warte bis zur nächsten vollen Minute für präzise Schätzung der erwarteten Bilder
        
        now = datetime.now()
        seconds_to_next_minute = 60 - now.second
        if seconds_to_next_minute < 60:
            print(f"Warte {seconds_to_next_minute} Sekunden bis zur nächsten vollen Minute...")

        start_time = datetime.strptime(experiment_start_time, "%H:%M:%S")
        if not experiment_end_time <= lokale_Zeit <= experiment_start_time:
            start_time = datetime.strptime(lokale_Zeit, "%H:%M:%S")
        
        end_time = datetime.strptime(experiment_end_time, "%H:%M:%S")

        if end_time <= start_time:
            end_time += timedelta(days=1)

        time_difference_seconds = (end_time - start_time).total_seconds()
        erwartete_Bilder = math.floor(time_difference_seconds / (interval * 60))+1
        print(f"erwartete Bilder: {erwartete_Bilder}")
        log_schreiben(f"erwartete Bilder: {erwartete_Bilder}",log_mode)
        write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "expected_images", erwartete_Bilder)
    except Exception as e:
        print(f"Fehler bei der Berechnung der erwarteten Bilder: {e}")
        erwartete_Bilder = "---"

    try:
        write_fram_bytes(0x6230, (erwartete_Bilder).to_bytes(4, byteorder='big'))
        write_fram_bytes(0x0650, b'\x00' * 4)
    except Exception as e:
        error_message(9,e, log_mode)
        print(f"Fehler beim Löschen des Bildzählers und Schreiben der erwarteten Bilder in den RAM: {e}")

    # Kameraeinstellungen kopieren - bei Raspberry Kameras übernimmt das die Bildaufnahme Funktion
    if camera == "AV__Alvium_1800_U-2050":
        try:
            ordner = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "current_folder")
            Dateiname = os.path.basename(ordner)
            zieldatei = os.path.join(ordner, f"{Dateiname}_Kameraeinstellungen.xml")
            shutil.copy("/home/Ento/LepmonOS/Kamera_Einstellungen.xml", zieldatei)
            checklist(zieldatei, log_mode, algorithm="md5")
            print("Kameraeinstellungen kopiert")
        except Exception as e:
            print(f"Fehler beim Kopieren der Kameraeinstellungen: {e}")
        
    # erste Belichtung
    try:
        Night = read_fram_bytes(0x07A0, 1) == b'\x01' # Kontrollbit bei Anschalten UV auf True --> wird true ausgegeben, ist letzer Fang nicht beendet
    except Exception as e:
        print(f"Fehler beim Lesen aus dem FRAM: {e}")
        try:
            Night = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "Control_Night")
        except Exception as e:
            print(f"Fehler beim Schreiben in die Konfigurationsdatei: {e}")
    Exposure, gain = first_exp(Night,log_mode, camera)
    
    usb_reset = False


    # Schleife
    while True:
        _, lokale_Zeit,_ = Zeit_aktualisieren(log_mode)
        ambient_light, Sensorstatus_Licht = get_light(log_mode)
        photo_sanity_check = False
        good_exposure = False

        if (ambient_light <= dusk_treshold and not experiment_end_time <= lokale_Zeit <= experiment_start_time) or\
        (ambient_light > dusk_treshold and not sunrise <= lokale_Zeit <= experiment_start_time)or\
            Warteschleife:
            if  Warteschleife:
                Warteschleife = False

            if heater and Bilder_mit_heizung < 10:
                if Heizung_active == False:
                    Heizung_active = True
                    turn_on_led("Heizung")
                    if not Fang_begonnen:
                        log_schreiben("Scheibenheizung zu Beginn der Aufnahme Schleife eingeschaltet",log_mode)
                        print("Scheibenheizung zu Beginn der Aufnahme Schleife eingeschaltet")
                Bilder_mit_heizung += 1
                if Bilder_mit_heizung >= 9:
                    turn_off_led("Heizung")
                    log_schreiben("Scheibenheizung nach 8 Bildern ausgeschaltet",log_mode)
                    print("Scheibenheizung nach 8 Bildern ausgeschaltet")
                    write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "powermode", "Heizung", False)
                    Heizung_active = False
                    heater = False
                    
            if not Fang_begonnen:
                LepiLED_start("show")
                log_schreiben("LepiLED eingeschaltet",log_mode)
                log_schreiben("------------------",log_mode)
                send_lora("LepiLED eingeschaltet")
                Fang_begonnen = True
                try:
                    write_fram_bytes(0x07A0, b'\x01')
                except Exception as e:
                    print(f"Fehler beim Schreiben in den FRAM: {e}")
                try:
                    write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "Control_Night", True)
                except Exception as e:
                    print(f"Fehler beim Schreiben in die Konfigurationsdatei: {e}")
                UV_active = True
                
            RPI_time(log_mode)
                
            experiment_start_string = datetime.strptime(experiment_start_time, "%H:%M:%S")
            lokale_Zeit_string = datetime.strptime(lokale_Zeit, "%H:%M:%S")
            
            print(f"Aufnahmezeitpunkt: {lokale_Zeit_string.strftime('%H:%M:%S')}")
            print(Exposure, gain)
            time.sleep(5)
            while not photo_sanity_check and not good_exposure:

                '''
                if is_stop_requested():
                    log_schreiben("Stop requested from web interface", log_mode)
                    überleiten_zu_shutdown = True
                    break
                '''
                if camera == "AV__Alvium_1800_U-2050":
                    code, current_image, Status_Kamera, power_on, Kamera_Fehlerserie, avg_brightness, good_exposure, Exposure, gain = snap_image_AV("jpg", "log", Kamera_Fehlerserie, log_mode, Exposure=Exposure, Gain=gain)
                    write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "AV__Alvium_1800_U-2050", "current_exposure", Exposure)
                    write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "AV__Alvium_1800_U-2050", "current_gain", gain)
                elif camera == "RPI_Module_3":
                    code, current_image, Status_Kamera, power_on, Kamera_Fehlerserie, avg_brightness, good_exposure, Exposure, gain,_ ,_ = snap_image_rpi("jpg","log", Kamera_Fehlerserie, log_mode, camera, Exposure=int(Exposure), Gain=gain, focus=focus)
                elif camera == "RPI_HQ":
                    code, current_image, Status_Kamera, power_on, Kamera_Fehlerserie, avg_brightness, good_exposure, Exposure, gain,_ ,_ = snap_image_rpi("jpg","log", Kamera_Fehlerserie, log_mode, camera, Exposure=int(Exposure), Gain=gain)

                elif camera not in ["AV__Alvium_1800_U-2050","RPI_Module_3","RPI_HQ"]:
                    log_schreiben(f"unbekannte Kamera gefunden:{camera}.", log_mode)

                '''
                update_capture_progress(
                    current_exposure=Exposure,
                    current_gain=gain,
                    last_image_path=current_image)
                '''

                time.sleep(1)

                if Status_Kamera == 1:
                    try:
                        photo_sanity_check = check_image(current_image)
                    except Exception as e:
                        print(f"Fehler bei der Bildprüfung: {e}")
                        photo_sanity_check = False
                        
                if Kamera_Fehlerserie >= 3:
                    error_message(2, "", log_mode)
                    überleiten_zu_shutdown = True
                    break
                
            if photo_sanity_check:
                try:
                        aktuelles_Bild = ram_counter(0x0650)
                        print(f"Bild-Counter im Ram Modul erhöht: {aktuelles_Bild}")
                        '''
                        # Update web UI with image count
                        increment_image_count()
                        '''
                except Exception as e:
                        print(f"Fehler beim Schreiben des Bild-Counters im Ram Modul: {e}")

            if not überleiten_zu_shutdown:
                        
                time.sleep(1)        
                sensors,_ = read_sensor_data(code, lokale_Zeit, log_mode)
                

                sensors["Status_Kamera"] = Status_Kamera
                sensors["Exposure"] = Exposure
                sensors["Gain"] = f"{gain:.1f}"
                sensors["Brightness"] = f"{avg_brightness:.1f}"

                try:
                    if power_on >= 3:
                        Status_LED = 1
                    if 1 < power_on < 3 or power_on == "---":
                        Status_LED = 0
                    if 1 >= power_on or power_on == "---":
                        Status_LED = 0 
                except Exception as e:
                    print(f"Fehler bei der Auswertung des Visible LED Status: {e}")
                    Status_LED = "---"
                
                sensors["Status_Visible_LED"] = Status_LED 
                if not power_on == "---":
                    sensors["Power_Visible_LED"] = f"{power_on:.2f}" 
                elif power_on == "---":
                    sensors["Power_Visible_LED"] = "---"                    
                if UV_active:
                    sensors["LepiLED"] = "active" 
                elif not UV_active:
                    sensors["LepiLED"] = "inactive"      
                
                if gamma_correction:
                    sensors["Gamma_Corr_value"] = gamma_value                              

                try:
                    csv_path = erstelle_und_aktualisiere_csv(sensors, log_mode="log")
                except Exception as e:
                    log_schreiben(f"Fehler beim Erstellen/Aktualisieren der CSV Datei: {e}", log_mode)
                    
                checklist(current_image,log_mode, algorithm="md5")

                last_image = datetime.strptime(lokale_Zeit, "%H:%M:%S")
                next_image = (last_image + timedelta(minutes=interval)).replace(second=0, microsecond=0)
                _, lokale_Zeit,_ = Zeit_aktualisieren(log_mode)
                lokale_Zeit = datetime.strptime(lokale_Zeit, "%H:%M:%S")
                time_to_next_image = (next_image - lokale_Zeit).total_seconds()

                if time_to_next_image < 0:
                    time_to_next_image = 0
                log_schreiben(f"Warten bis zur nächsten Aufnahme: {round(time_to_next_image,0)} Sekunden",log_mode)
                show_message("blank", lang = lang)
                
                if 0 <= lokale_Zeit.minute <= 15 and not usb_reset and lokale_Zeit.hour % 2 == 0:
                    sharp,_ = check_focus(current_image, camera, log_mode)
                    if not sharp and camera == "RPI_Module_3":
                        log_schreiben("Unscharfe Bilder erkannt. Starte Fokussierung ...", log_mode)
                        dioptrien_alt = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "RPI_Module_3", "focus")
                        dioptrien_neu = set_focus_rpi_cam()
                        log_schreiben(f"Fokus RPI Module 3 geändert von {dioptrien_alt} auf {dioptrien_neu}", log_mode=log_mode)
                        time.sleep(5)
                    remount_usb_drive(log_mode)
                    usb_reset = True
                
                if 15 <= lokale_Zeit.minute < 30 and not usb_reset and lokale_Zeit.hour % 2 == 0:
                    usb_reset = False
                
                print(f"Warte bis zur nächsten Aufnahme: {time_to_next_image} Sekunden")
                time.sleep(time_to_next_image)

        else:
            überleiten_zu_shutdown = True
        
        if überleiten_zu_shutdown:
            LepiLED_ende("show")
            daylight_saving_check(log_mode)
            print("Beende Aufnahme Schleife\nLeite zum Ausschalten über")
            log_schreiben("##################################",log_mode)
            log_schreiben("##################################",log_mode)
            _, _, free_space_gb_after_run, _, _ = get_disk_space(log_mode)
            try:
                    write_fram_bytes(0x07A0, b'\x00')
                    write_fram_bytes(0x07C0, b'\x00')
            except Exception as e:
                    print(f"Fehler beim Schreiben in den FRAM: {e}")
            try:
                    write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "Control_Night", False)
                    write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "Control_End", False)
            except Exception as e:
                    print(f"Fehler beim Schreiben in die Konfigurationsdatei: {e}")
            try:
                # Lese die 4 Bytes Float aus dem FRAM und rechne mit aktuellem Wert
                free_space_before_run_bytes = read_fram_bytes(0x0390, 4)
                free_space_before_run = struct.unpack('f', free_space_before_run_bytes)[0]
                size = free_space_before_run - free_space_gb_after_run
                size_rounded = f"{abs(size):.3f}"
                expected_images = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "expected_images")
                counted_images = int.from_bytes(read_fram_bytes(0x0650, 4), byteorder='big')
                log_schreiben(f"in dieser Nacht wurden {size_rounded} GB an Daten generiert",log_mode)
                log_schreiben(f"erwartete Bilder: {expected_images}, aufgenommene Bilder: {counted_images}",log_mode)
                send_lora(f"in dieser Nacht wurden {size_rounded} GB an Daten mit {counted_images} gezählten Bildern von {expected_images} erwarteten Bildern generiert")
                
            except Exception as e:
                log_schreiben("Verbrauchter Speicher und gezählte Bildernicht gemessen: {e}",log_mode)
                pass
            log_schreiben("Beende Aufnahme Schleife. Leite zum Ausschalten über",log_mode)
            log_schreiben("Fahre ARNI in 1 Minute herunter und starte neu",log_mode)
            log_schreiben("##################################",log_mode)
            log_schreiben("### SELBSTINDUZIERTER SHUTDOWN ###",log_mode)
            log_schreiben("##################################",log_mode)
        
            '''
            # Signal that capturing has ended
            set_capturing_active(False)            
            '''
            print("hauptschleife beendet")
            return
    
if __name__ == "__main__":
    erstelle_ordner("manual")
    initialisiere_logfile("manual")
    log_schreiben("Logeinträge werden im Terminal angezeigt bei Manueller ausführung von Capturing", "log")
    capturing("manual")
    