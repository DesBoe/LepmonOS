import faulthandler; faulthandler.enable()
from Camera_AV import snap_image_AV
from Camera_RPI import snap_image_rpi
from GPIO_Setup import turn_on_led, turn_off_led, button_pressed
from OLED_panel import *
import time
from RTC_new_time import set_hwc
from coordinates import set_coordinates
from times import *
from json_read_write import *
import json
from sensor_data import *
from service import *
from logging_utils import log_schreiben
from Lights import *
from find_focus import set_focus
from site_selection import *
import os
from fram_operations import *
from updater import *
from end import trap_shutdown    
from service import *
from hardware import *
from json_read_write import get_value_from_section, write_value_to_section
from language import *
from runtime import write_timestamp
from coordinates_region_check import find_country_and_region

def display_sensor_status_with_text(sensor_data, sensor_status, log_mode):
    """
    Gibt die Sensorinformationen mit display_text aus.
    1. Zeile: Sensorname (wie in sensor_status angegeben)
    2. Zeile: Sensorzustand (OK oder Fehler)
    3. Zeile: Erster Wert, den der Sensor in sensor_data schreibt, inkl. Einheit.
    """
    if hardware in ["Pro_Gen_1", "Pro_Gen_2"]:
        sensors = [
            ("Light_Sensor", "LUX", "Lux"),
            ("Inner_Sensor", "Temp_in", "°C"),
            #("Power_Sensor", "bus_voltage", "V"), # Power_Sensor nicht verbaut in Pro Gen 1 und 2
            ("Environment_Sensor", "Temp_out", "°C")
        ]
        log_schreiben("Power_Sensor nicht verbaut in Pro Gen 1 und 2", log_mode=log_mode)
    
    elif hardware in ["Pro_Gen_3", 
                      "CSL_Gen_1", "CSS_Gen_1"]:
        sensors = [
            ("Light_Sensor", "LUX", "Lux"),
            ("Inner_Sensor", "Temp_in", "°C"),
            ("Power_Sensor", "bus_voltage", "V"),
            ("Environment_Sensor", "Temp_out", "°C")
        ]
    
    for sensor_name, data_key, einheit in sensors:
        if sensor_name == "Power_Sensor" and hardware in ["Pro_Gen_1", "Pro_Gen_2"]:
            status = "nicht"
            value = "verbaut"
        else:
            status_value = sensor_status.get(sensor_name, 0)
            status = "OK" if str(status_value) == "1" or status_value == 1 else "Fehler"
            value = sensor_data.get(data_key, "---")
        
        display_text(sensor_name, f"Status: {status}", f"Wert: {value} {einheit}", 1.5)
        log_schreiben(f"Sensor: {sensor_name}, Status: {status}, Wert: {value} {einheit}", log_mode=log_mode)
        
        
def all_sensors_ok(sensor_status):
    # Prüfe nur die Sensorstatus-Keys, nicht z.B. Zeitstempel
    status_keys = [k for k in sensor_status if k.endswith('_Sensor')]
    return all(sensor_status.get(k, 0) == 1 for k in status_keys)
        
        

hmi_timeout = 5

def open_trap_hmi(log_mode, start_step = 0):
    lang = get_language()
    menu_exit = False
    print("starte lokales HMI")   
    
    set_new_location_code = force_new_location_code(log_mode)
    if set_new_location_code:
        log_schreiben("Änderung der Provinz und Kreiskürzel erzwungen", log_mode)
    Menu_open = False
    turn_on_led("blau") 

    hardware = get_hardware_version()
    if hardware == "Pro_Gen_1":
        show_message("hmi_01", lang=lang)
        print("Eingabe Menü mit der Taste Enter ganz links unten öffnen")
    
    elif hardware in ["Pro_Gen_2","Pro_Gen_3", 
                      "CSL_Gen_1", "CSS_Gen_1"]:
        show_message("hmi_02", lang=lang)            
        print("Eingabe Menü mit der Taste Enter ganz rechts unten öffnen")
        
    menu_start_time = time.time()
    while not menu_exit:
        if time.time() - menu_start_time > hmi_timeout:
            print("HMI timeout erreicht. leite über zu wait")
            break
             
        if (button_pressed("enter") 
            or set_new_location_code 
            or read_fram_bytes(0x078F, 1) == b'\x01' # erzwinge erneutes Menü öffnen nach fehlerhaftem Fokussieren
            or read_fram_bytes(0x052F, 1) == b'\x01' # erzwinge erneutes Menü öffnen nach Update
            or log_mode == "manual"):
                
            try:
                
                menu_exit = menu_options(log_mode, set_new_location_code, lang, start_step = start_step)
                Menu_open = True
                if read_fram_bytes(0x052F, 1) == b'\x01': # Erzwingen durch Update zurückgesetzt                        
                    write_fram_bytes(0x052F, b'\x00')
                if read_fram_bytes(0x078F, 1) == b'\x01':
                    write_fram_bytes(0x078F, b'\x00') # Erzwingen durch fehlerhaftem Fokussieren zurückgesetzt     
                show_message("blank", lang=lang)
                     
                break
            except Exception as e:
                print(f"Fehler im lokalen Menü: {e}")
                log_schreiben(f"Fehler im lokalen Menü: {e}", log_mode=log_mode)
                for i in range(5): 
                    turn_on_led("rot")
                    turn_on_led("gelb")
                    time.sleep(0.5)
                    turn_off_led("rot")
                    time.sleep(0.5)   
                    turn_off_led("gelb")  
                    
            time.sleep(.05)
                       
    if not Menu_open:
        log_schreiben("------------------", log_mode=log_mode)
        log_schreiben("ARNI nicht mit lokalem User Interface parametrisiert", log_mode=log_mode)

    latitude, longitude, _, _, _, _ = (get_coordinates())
    log_schreiben("------------------", log_mode=log_mode)
    log_schreiben(f"Breite: {latitude}", log_mode=log_mode)
    log_schreiben(f"Länge: {longitude}", log_mode=log_mode)
    try:
        power_mode = read_fram(0x03B0, 16).replace('\x00', '').strip()
        time.sleep(.5)
    except Exception as e:
        print(f"Fehler beim Lesen des Power-Modus: {e}")
        try:
            power_mode = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "powermode", "supply")
            time.sleep(.5)
        except Exception as e:
            print(f"Fehler beim Lesen des Power-Modus aus der Konfigurationsdatei: {e}")
            power_mode = "Netz"
    log_schreiben(f"Stromversorgung:{power_mode}", log_mode = log_mode)
    show_message("blank", lang = lang)
    turn_off_led("blau")
    
    
    print("beende lokales HMI")   
    write_timestamp(0x07E0)  
        
    return    
    
    
    
                  
                  
                  
                  
def menu_options(log_mode, set_new_location_code, lang, start_step = 0):        
                print("Eingabe Menü geöffnet")
                hardware = get_hardware_version()
                camera = get_device_info('camera') 
                print("erwartete Kamera: {camera}")
                show_message("hmi_03", lang=lang)
                log_schreiben("------------------", log_mode=log_mode)
                try:
                    hmi_counter = ram_counter(0x0330)
                except:
                    hmi_counter = "---" 
                log_schreiben(f"Lokales User Interface von ARNI wurde geöffnet. Es wurde zum {hmi_counter} mal geöffnet", log_mode=log_mode)
                print(f"Eingabe Menü auf diesem ARNI zum {hmi_counter} mal geöffnet")
                print("versteckte Menüs:\noben  = Updater\nrechts = fokusieren\nunten = Sprache wähen")                
                
                
                Neustart = False
                province_old = Kreis_code_old = province = Kreis_code = None
                latitude_ohne_Vorzeichen = longitude_ohne_Vorzeichen = None
                
                if hardware in ["Pro_Gen_2", "Pro_Gen_3", "Pro_Gen_4"]:
                    steps = ["hidden","power", "delete_usb", "heat", "time", "gps","diagnose_return","diagnose_start"]
                elif hardware in ["Pro_Gen_1","CSL_Gen_1", "CSS_Gen_1"]:
                    steps = ["hidden","power", "delete_usb", "time", "gps","diagnose_return","diagnose_start"]
                
                print(log_mode, start_step)
                if log_mode == "manual" and start_step > 0:
                    step = start_step
                    print(f"Starte lokales Menü ab Schritt {steps[step]}")
                else:    
                    step = 0
   

                while step < len(steps):
                    current = steps[step]
                    print(f"aktives Menü:{current}")
                    if current == "hidden":
                        hidden_menu_start = time.time()   

                        while True:
                            if time.time() - hidden_menu_start > hmi_timeout:
                                print("HMI timeout für versteckte Menüs erreicht. Leite über zum sichtbaren Menü")
                                log_schreiben("kein Verstecktes Menü geöffnet", log_mode=log_mode)
                                step += 1
                                break
                            if button_pressed("rechts") or read_fram_bytes(0x078F, 1) == b'\x01':
                                print("Rechts gedrückt. Öffne Fokusmenü")
                                log_schreiben("------------------", log_mode=log_mode)
                                log_schreiben("lokale Fokussierhilfe geöffnet", log_mode=log_mode)
                                set_focus(log_mode)
                                turn_off_led("gelb")
                                show_message("hmi_03", lang=lang)
                                hidden_menu_start = time.time()
                                
                                    
                            if button_pressed("oben"):
                                print("Oben gedrückt. Öffne Update Menü")
                                turn_off_led("blau")
                                log_schreiben("------------------", log_mode=log_mode)
                                update(log_mode)
                                log_schreiben("fahre fort", log_mode=log_mode)
                                show_message("hmi_03", lang=lang)
                                hidden_menu_start = time.time()

                            if button_pressed("unten"):
                                print("Unten gedrückt. Öffne Sprach Auswahl")
                                turn_off_led("blau")
                                log_schreiben("------------------", log_mode=log_mode)
                                log_schreiben("Sprachmenü geöffnet", log_mode=log_mode)
                                new_language = set_language()
                                time.sleep(1)
                                lang = new_language
                                log_schreiben(f"gespeicherte Sprache: {new_language}", log_mode=log_mode)
                                log_schreiben("Sprachmenü geschossen", log_mode=log_mode)

                                time.sleep(.5)
                                show_message("hmi_03", lang=lang)
                                hidden_menu_start = time.time()
                            time.sleep(.05)
                            

                
###############################

                    
                    if current == "power":
                        print("Wähle Stromversorgung:\nOben = Solar\nUnten = Netz\nRechts = Zurück")
                        show_message("hmi_06", lang=lang)
                        turn_on_led("blau")
                        while True:
                            if button_pressed("oben"):
                                log_schreiben("------------------", log_mode=log_mode)
                                turn_off_led("blau")
                                powermode = "Solar"
                                write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "powermode", "supply", powermode)
                                try:
                                    write_fram(0x03B0, b"\x00" * 16)
                                    write_fram(0x03B0, powermode)
                                except:
                                    pass
                                log_schreiben("Stromversorgung auf Solar gesetzt", log_mode=log_mode)
                                show_message("hmi_07", lang=lang)
                                step += 1
                                break
                            elif button_pressed("unten"):
                                powermode = "Netz"
                                log_schreiben("------------------", log_mode=log_mode)
                                turn_off_led("blau")
                                write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "powermode", "supply", powermode)
                                try:
                                    write_fram(0x03B0, b"\x00" * 16)
                                    write_fram(0x03B0, powermode)
                                except:
                                    pass
                                log_schreiben("Stromversorgung auf Netz gesetzt", log_mode=log_mode)
                                show_message("hmi_08", lang=lang)
                                step += 1
                                break
                            elif button_pressed("rechts") and step > 0:
                                turn_off_led("blau")
                                step -= 1
                                log_schreiben(f"Gehe einen Schritt zurück in lokalen Auswahlmenü: {steps[step]}", log_mode=log_mode)
                                show_message("hmi_03", lang=lang)
                                break
                            time.sleep(.05)
                            
                            
                    elif current == "delete_usb":
                        print("USB Stick löschen?\nOben = Ja\nUnten = Nein\nRechts = Zurück")
                        show_message("hmi_09", lang=lang)
                        turn_on_led("blau")
                        while True:
                            if button_pressed("oben"):
                                log_schreiben("------------------", log_mode=log_mode)
                                log_schreiben("Menü zum Löschen des USB Sticks geöffnet", log_mode=log_mode)
                                show_message("hmi_10", lang=lang)
                                turn_off_led("blau")
                                delete_USB_content(log_mode)
                                log_schreiben("Menü zum Löschen des USB Sticks geschlossen", log_mode=log_mode)
                                show_message("hmi_11", lang=lang)
                                step += 1
                                break
                            elif button_pressed("unten"):
                                turn_off_led("blau")
                                show_message("hmi_12", lang=lang)
                                log_schreiben("USB Stick nicht gelöscht", log_mode=log_mode)
                                step += 1
                                break
                            elif button_pressed("rechts") and step > 0:
                                turn_off_led("blau")
                                step -= 1
                                log_schreiben(f"Gehe einen Schritt zurück in lokalen Auswahlmenü: {steps[step]}", log_mode=log_mode)
                                break
                            time.sleep(.05)
                    elif current == "heat":
                        if hardware == "Pro_Gen_2" or hardware == "Pro_Gen_3":
                            print("Scheibenheizung aktivieren?\nOben = Ja\nUnten = Nein\nRechts = Zurück")
                            turn_on_led("blau")
                            show_message("hmi_13", lang=lang)
                            while True:
                                if button_pressed("oben"):
                                    log_schreiben("------------------", log_mode=log_mode)
                                    log_schreiben("Scheibenheizung wird aktiviert", log_mode=log_mode)
                                    show_message("hmi_14", lang=lang)
                                    turn_off_led("blau")
                                    write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "powermode", "Heizung", True)
                                    step += 1
                                    break
                                elif button_pressed("unten"):
                                    turn_off_led("blau")
                                    write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "powermode", "Heizung", False)
                                    log_schreiben("Scheibenheizung wird nicht aktiviert", log_mode=log_mode)
                                    show_message("hmi_15", lang=lang)
                                    step += 1
                                    break
                                elif button_pressed("rechts") and step > 0:
                                    turn_off_led("blau")
                                    step -= 1
                                    log_schreiben(f"Gehe einen Schritt zurück in lokalen Auswahlmenü: {steps[step]}", log_mode=log_mode)
                                    break
                                time.sleep(.05)
                        else:
                            write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "powermode", "Heizung", False)
                            log_schreiben("Keine Scheibenheizung auf diesem ARNI vorhanden.", log_mode=log_mode)
                            print("Keine Scheibenheizung auf diesem ARNI vorhanden.")
                    if current == "time":
                        print("Hardware Clock neu stellen?\nOben = Ja\nUnten = Nein\nRechts = Zurück")
                        show_message("hmi_16", lang=lang)
                        status_rtc = 0
                        com_rtc = 0
                        user_time_update = True
                        turn_on_led("blau")
                        while True:
                            if com_rtc < 2:
                                try:
                                    jetzt_local, _, status_rtc = Zeit_aktualisieren(log_mode)
                                    jetzt_local_dt = datetime.strptime(jetzt_local, "%Y-%m-%d %H:%M:%S")
                                    com_rtc += 1
                                except:
                                    jetzt_local = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    jetzt_local_dt = datetime.strptime(jetzt_local, "%Y-%m-%d %H:%M:%S")
                                    com_rtc += 1
                            else:
                                jetzt_local = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                jetzt_local_dt = datetime.strptime(jetzt_local, "%Y-%m-%d %H:%M:%S")
                            show_message("hmi_17", lang=lang, date=jetzt_local_dt.strftime("%Y-%m-%d"), time=jetzt_local_dt.strftime("%H:%M:%S"))
                            if button_pressed("oben"):
                                turn_off_led("blau")
                                log_schreiben("------------------", log_mode=log_mode)
                                log_schreiben("Menü zum aktualisieren der Uhrzeit geöffnet", log_mode=log_mode)
                                time.sleep(1)
                                set_hwc(rtc_mode="hmi", log_mode=log_mode)
                                log_schreiben("Menü zum aktualisieren der Uhrzeit geschlossen", log_mode=log_mode)
                                step += 1
                                break
                            elif button_pressed("unten"):
                                turn_off_led("blau")
                                user_time_update = False
                                step += 1
                                log_schreiben("------------------", log_mode=log_mode)
                                log_schreiben("Uhrzeit nicht mit dem lokalen Interface aktualisiert", log_mode=log_mode)
                                log_schreiben("------------------", log_mode=log_mode)
                                break
                            elif button_pressed("rechts") and step > 0:
                                turn_off_led("blau")
                                step -= 1
                                log_schreiben(f"Gehe einen Schritt zurück in lokalen Auswahlmenü: {steps[step]}", log_mode=log_mode)
                                break
                            time.sleep(.05)
                        print("Zeitmenü Ende")
                        
                        
                    if current == "gps":
                        user_selection_Code = False
                        user_verified_region = False
                        print("GPS Menü: Koordinaten mit \nOben = ändern\nUnten = bestätigen\nRechts = Zurück")
                        latitude, longitude, _, _, latitude_ohne_Vorzeichen, longitude_ohne_Vorzeichen = (get_coordinates())
                        show_message("hmi_18", lang=lang)
                        show_message("hmi_19", lang=lang, latitude=latitude, longitude=longitude)
                        turn_on_led("blau")
                        while True:
                            if button_pressed("oben") or set_new_location_code:
                                    turn_off_led("blau")
                                    log_schreiben("------------------", log_mode=log_mode)
                                    log_schreiben("Menü zum aktualisieren der Koordinaten geöffnet", log_mode=log_mode)
                                    print("Menü zum aktualisieren der Koordinaten geöffnet")
                                    
                                    while not user_verified_region:
                                        time.sleep(1)
                                        set_coordinates(log_mode)
                                    
                                        
                                        show_message("hmi_gps_check_1", lang=lang)
                                        try:
                                            country_name, region_name = find_country_and_region()
                                            log_schreiben(f"Eingegebene Koordinaten befinden sich in Land: {country_name}, Region: {region_name}", log_mode=log_mode)
                                            turn_on_led("blau")
                                            show_message("hmi_gps_check_2", lang=lang, country_name=country_name, region_name=region_name)
                                            while True:
                                                if button_pressed("unten"):
                                                    user_verified_region = True
                                                    log_schreiben("Nutzender hat bestätigt, dass die eingegebenen Koordinaten in der Zielregion liegen", log_mode=log_mode)
                                                    break
                                                if button_pressed("oben"):
                                                    user_verified_region = False
                                                    log_schreiben("Nutzender hat angegeben, dass die eingegebenen Koordinaten nicht in der Zielregion liegen", log_mode=log_mode)
                                                    break
                                            turn_off_led("blau")
                                        
                                        
                                        except Exception as e:
                                            country_name = "unbekannt"
                                            region_name = "unbekannt"
                                            log_schreiben(f"Fehler bei der Bestimmung von Land und Region der eingegebenen Koordinaten: {e}", log_mode=log_mode)
                                            error_message(16, e, log_mode)
                                            user_verified_region = True

                                    
                                        
                                    log_schreiben("Menü zum aktualisieren der Koordinaten geschlossen", log_mode=log_mode)
                                    show_message("hmi_20", lang=lang)
                                    _, provinz, Kreiscode, _ = get_Lepmon_code(log_mode)
                                    show_message("hmi_21", lang=lang, provinz=provinz, Kreiscode=Kreiscode)
                                    turn_on_led("blau")
                                    while user_selection_Code == False:
                                        if button_pressed("oben") or set_new_location_code:
                                            turn_off_led("blau")
                                            log_schreiben("------------------", log_mode=log_mode)
                                            log_schreiben("Menü zum Ändern der Provinz und Kreiskürzel geöffnet. Erwarte neuen LEPMON-Code", log_mode=log_mode)
                                            time.sleep(1)
                                            Neustart, province_old, Kreis_code_old, province, Kreis_code = set_location_code(log_mode)
                                            user_selection_Code = True
                                            if not Neustart:
                                                log_schreiben("Menü zum Ändern der Provinz und Kreiskürzel beendet. Es wurden keine Änderungen eingegeben. Fahre fort", log_mode=log_mode)
                                                show_message("hmi_22", lang=lang)
                                                user_selection_hidden = 1
                                                turn_off_led("blau")
                                            elif Neustart:
                                                log_schreiben("Menü zum Ändern der Provinz und Kreistkürzel beendet. Es wurden Änderungen eingegeben. Nach dem Systemcheck erfolgt die Übernahme", log_mode=log_mode)
                                                show_message("hmi_23", lang=lang)
                                                turn_off_led("blau")
                                        elif button_pressed("unten"):
                                            turn_off_led("blau")
                                            user_selection_Code = True
                                            log_schreiben("------------------", log_mode=log_mode)
                                            log_schreiben("Provinz und Kreiskürzel nicht mit dem lokalen Interface aktualisiert", log_mode=log_mode)
                                            show_message("hmi_24", lang=lang)
                                        elif button_pressed("rechts") and step > 0:
                                            turn_off_led("blau")
                                            step -= 1
                                            break
                                        time.sleep(.05)
                                    step += 1
                                    break
                            elif button_pressed("unten"):
                                log_schreiben("Menü für Koordinaten und Lepmon Code nicht geöffnet", log_mode=log_mode)
                                print("Menü für Koordinaten und Lepmon Code nicht geöffnet")
                                turn_off_led("blau")
                                write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "GPS", "latitude", latitude_ohne_Vorzeichen)
                                write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "GPS", "longitude", longitude_ohne_Vorzeichen)
                                print("Koordinaten aus Ram in Konfigurationsdatei geschrieben")
                                step += 1
                                break
                            elif button_pressed("rechts") and step > 0:
                                turn_off_led("blau")
                                step -= 1
                                log_schreiben(f"Gehe einen Schritt zurück in lokalen Auswahlmenü: {steps[step]}", log_mode=log_mode)
                                break
                            time.sleep(.05)
                            
                    if current == "diagnose_return":
                        show_message("hmi_25", lang=lang)
                        turn_on_led("blau")
                        print("Diagnose starten?\nOben = Ja\nRechts = Zurück")
                        while True:
                            if button_pressed("oben"):
                                step +=1
                                turn_off_led
                                log_schreiben("Eingaben beendet", log_mode=log_mode)
                                break
                                
                            if button_pressed("rechts"):
                                step -=1
                                log_schreiben(f"Gehe einen Schritt zurück in lokalen Auswahlmenü: {steps[step]}", log_mode=log_mode)
                                break
                            time.sleep(.05)
                        

                            
                    if current == "diagnose_start":
                            
                            log_schreiben("------------------", log_mode=log_mode)
                            log_schreiben("Starte Systemcheck", log_mode=log_mode)

                            _,lokale_Zeit,_ = Zeit_aktualisieren(log_mode) 
                            sensor_data, sensor_status = read_sensor_data("Test_hmi",lokale_Zeit, log_mode) 

                            display_sensor_data(sensor_data, sensor_status)# Terminal
                            display_sensor_status_with_text(sensor_data, sensor_status, log_mode) 
                            if not all_sensors_ok(sensor_status):
                                Sensor_reads = 0
                                turn_on_led("gelb")
                                show_message("hmi_sensor_check_1", lang=lang)
                                while Sensor_reads < 5 and not all_sensors_ok(sensor_status):
                                    turn_on_led("blau")
                                    _,lokale_Zeit,_ = Zeit_aktualisieren(log_mode) 
                                    sensor_data, sensor_status = read_sensor_data("Test_hmi",lokale_Zeit, log_mode) 
                                    display_sensor_data(sensor_data, sensor_status)# Terminal
                                    
                                    Sensor_reads += 1
                                    turn_off_led("blau")
                                    time.sleep(.0125)
                                turn_off_led("gelb")
                                if all_sensors_ok(sensor_status):
                                    log_schreiben("Alle Sensoren nach erneutem Auslesen OK", log_mode=log_mode)
                                    show_message("hmi_sensor_check_2", lang=lang)
                                    display_sensor_status_with_text(sensor_data, sensor_status, log_mode) 
                                    
                                if not all_sensors_ok(sensor_status):
                                    log_schreiben("Nicht alle Sensoren nach erneutem Auslesen OK. LEPMON kontaktieren. ARNI fährt fort", log_mode=log_mode)
                                    show_message("hmi_sensor_check_3", lang=lang)
                                    turn_off_led("rot")
                                   

                                  
                            print("starte Kameratest...")
                            
                            show_message("hmi_26", lang=lang)
                            Status_Kamera = 0
                            Versuche_Kamera = 0

                            #### AV #####
                            if camera == "AV__Alvium_1800_U-2050":
                                print("Teste Allied Vision Kamera")
                                exposure = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","AV__Alvium_1800_U-2050","initial_exposure"))
                                gain = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","AV__Alvium_1800_U-2050","initial_gain_10"))/10
                                while Versuche_Kamera < 3 and Status_Kamera != 1:    
                                    try:
                                        
                                        code, current_image, Status_Kamera, power_on, Kamera_Fehlerserie,_ ,_ ,_ ,_ = snap_image_AV("jpg", "display", 0, log_mode ,Exposure=exposure, Gain=gain)
                                        if Status_Kamera == 0:
                                            Versuche_Kamera += 1
    
                                    except Exception as e: 
                                        print(f"Kamera Test fehlgeschlagen: {e}")
                                        Versuche_Kamera += 1
                                    
                                    if Versuche_Kamera >=3:
                                        break
                            
                            #### HQ #####
                            if camera == "RPI_Module_3": 
                                print("Teste RPI_Module_3 Kamera")
                                gain = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "RPI_Module_3", "initial_gain_10"))/10
                                Exposure = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "RPI_Module_3", "initial_exposure_10"))/10
                                focus = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "RPI_Module_3", "focus")
                                while Versuche_Kamera < 3 and Status_Kamera != 1: 
                                    try:
                                        code, dateipfad, Status_Kamera, power_on, Kamera_Fehlerserie, _, _, _, _, _, _ = snap_image_rpi("jpg","display", 0, log_mode, camera, int(Exposure), Gain=gain, focus=focus)
                                        if Status_Kamera == 0:
                                            Versuche_Kamera += 1

                                    except Exception as e:
                                        print(f"Kamera Test fehlgeschlagen: {e}")
                                        Versuche_Kamera += 1

                                    if Versuche_Kamera >=3:
                                        break
                    
                            #### Module 3 #####
                            if camera == "RPI_HQ":
                                print("Teste RPI HQ Kamera")
                                gain = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "RPI_HQ", "initial_gain_10"))/10
                                Exposure = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "RPI_HQ", "initial_exposure_10"))/10
                                while Versuche_Kamera < 3 and Status_Kamera != 1:      
                                    try:
                                        code, dateipfad, Status_Kamera, power_on, Kamera_Fehlerserie, _, _, _, _, _, _ = snap_image_rpi("jpg","display", 0, log_mode, camera, int(Exposure), Gain=gain)
                                        if Status_Kamera == 0:
                                            Versuche_Kamera += 1
    
                                    except Exception as e:
                                        print(f"Kamera Test fehlgeschlagen: {e}")
                                        Versuche_Kamera += 1
                                    
                                    if Versuche_Kamera >=3:
                                        break                   
                                         

                            if Status_Kamera == 0:
                                        show_message("hmi_27", lang=lang)
                                        log_schreiben("Kamera Test fehlgeschlagen, Kamera nicht verfügbar",log_mode=log_mode)
                                        log_schreiben("#####\nSELBSTINDUZIERTER SHUTDOWN\n#####", log_mode=log_mode)
                                        trap_shutdown(log_mode,5)
                                        os.system('sudo reboot')
                                        show_message("blank", lang=lang)
                                        time.sleep(10)
                                        
                            elif Status_Kamera == 1:        
                                    show_message("hmi_28", lang=lang)  
                                    log_schreiben("Kamera Test erfolgreich beendet",log_mode)
                                
                            USB = 0
                            while USB == 0:
                                total_space_gb = None
                                total_space_gb, used_space_gb, free_space_gb, _, _ = get_disk_space(log_mode)
                                show_message("hmi_29", lang=lang, total_space = str(total_space_gb), free_space = str(free_space_gb))
                                log_schreiben(f"USB Speicher: gesamt: {str(total_space_gb)} GB; frei: {str(free_space_gb)} GB",log_mode=log_mode)
                                if total_space_gb is None:
                                    show_message("hmi_30", lang=lang)
                                    log_schreiben("#####\nSELBSTINDUZIERTER SHUTDOWN\n#####", log_mode=log_mode)
                                    trap_shutdown(log_mode,5)
                                    return
                                elif free_space_gb < 16:
                                    show_message("hmi_31", lang=lang)
                                    log_schreiben("USB Speicher fast voll, bitte leeren", log_mode=log_mode)
                                    log_schreiben("##################################", log_mode=log_mode)
                                    log_schreiben("#####\nSELBSTINDUZIERTER SHUTDOWN\n#####", log_mode=log_mode)
                                    log_schreiben("##################################", log_mode=log_mode)
                                    trap_shutdown(log_mode, 5)
                                    return
                                elif free_space_gb >= 16:
                                    show_message("hmi_32", lang=lang)
                                    log_schreiben("USB Speicher OK", log_mode=log_mode)
                                    USB = 1   
                                time.sleep(.05)    
                    
                            sunset, sunrise, Zeitzone = get_sun()
                            sunset = sunset.strftime('%H:%M:%S')
                            sunrise = sunrise.strftime('%H:%M:%S')
                            log_schreiben(f"Sonnenuntergang: {sunset}", log_mode=log_mode)
                            log_schreiben(f"Sonnenaufgang:   {sunrise}", log_mode=log_mode)
                            print(f"Anzeige Dämmerung:{sunset}")
                            print(f"Anzeige Dämmerung:{sunrise}")
                            try:
                                show_message("hmi_33", lang=lang, sunset = sunset, sunrise = sunrise)
                                #show_message("hmi_34", lang=lang, sunrise = sunrise)
                            except Exception as e:
                                print(f"Fehler beim Anzeigen der Dämmerungszeiten: {e}")

                            
                            if Neustart:
                                show_message("hmi_35", lang=lang)
                                json_path = "/home/Ento/LepmonOS/Lepmon_config.json"
                                update_folder_and_log(json_path, province_old, Kreis_code_old, province, Kreis_code, log_mode)
                                show_message("hmi_36", lang=lang)
                                log_schreiben("Beende Systemcheck", log_mode=log_mode)
                                menu_exit = True
                                break
                                
                            elif not Neustart:
                                show_message("hmi_36", lang=lang)
                                log_schreiben("Beende Systemcheck", log_mode=log_mode)
                                menu_exit = True
                                break
            
                    
    

if __name__ == "__main__":
    print("#################")
    print("Hinweis: Die Tasteneingaben 'Oben', 'Unten', 'Links' und 'Rechts' können durch eintippen dieser Worte im Terminal simuliert werden.")
    print("#################")
    open_trap_hmi(log_mode="manual", start_step=6)
    
    # MENÜ Punkte:      start_step:
    #hidden             0
    #power              1   
    #delete_usb         2
    #heat               3 --> nur Pro_Gen_2, Pro_Gen_3, Pro_Gen_4
    #time               4
    #gps                5
    #diagnose_return    6
    #diagnose_start     7

