import time
import os
import random
import re
from gpiozero import LED
from LepmonOS_Dev_Camera_loop import * 
from GPIO_Setup import *
from OLED_panel import *
from Lights import *
import time
from service import get_usb_path
from fram_direct import *
from logging_utils import log_schreiben

from Camera_AV import *
from Camera_RPI import * 
from hardware import get_device_info
from times import Zeit_aktualisieren
from sensor_data import read_sensor_data
from fram_direct import *
from LepmonOS_Service_fram_delete import clear_fram
from configparser import ConfigParser
from LepmonOS_Service_fram_tabelle import get_Fram_table, write_fram_table_to_log
from LepmonOS_Service_fram_configurator import write_config_to_fram
from RTC_new_time import set_hwc

sn = "SN010083"
try:
    write_fram(0x0110, sn)
except Exception as e:
    print(f"Fehler beim Schreiben der Seriennummer in den FRAM: {e}")


def buttons(up, down, right, inp, oben, unten, rechts, enter):
    if button_pressed("oben"):
        log_schreiben("Knopf oben gedrückt", log_mode)
        oben = True
        up += 1
    if button_pressed("unten"):
        log_schreiben("Knopf unten gedrückt", log_mode)  
        unten = True
        down += 1
    if button_pressed("rechts"):
        log_schreiben("Knopf rechts gedrückt", log_mode)  
        rechts = True
        right += 1
    if button_pressed("enter"):
        log_schreiben("Knopf enter gedrückt", log_mode) 
        enter = True
        inp += 1
        
    return up, down, right, inp, oben, unten, rechts, enter 


def set_paths(sn):
    usb_path,_ = get_usb_path("manual")
    log_dateipfad = f"{usb_path}/Lepmon_Diagnose_{sn}_log.log"
    write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json","general","current_log",log_dateipfad) 
    write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json","general","current_folder",usb_path) 
    initialisiere_logfile("Diagnose")


    print(f"Setze Log Pfad auf: {log_dateipfad}")
    print(f"Setze Arbeitsverzeichnis auf: {usb_path}")


def update_sensor_data(code,lokale_Zeit, log_mode):
    sensor_data, sensor_status = read_sensor_data(code,lokale_Zeit, log_mode)
    lux = sensor_data.get("LUX_(Lux)")
    temp_in = sensor_data.get("Temp_in_(°C)")
    temp_out = sensor_data.get("Temp_out_(°C)")
    air_pressure = sensor_data.get("air_pressure_(hPa)")
    air_humidity = sensor_data.get("air_humidity_(%)")
    power = sensor_data.get("power_(W)")
    bus_voltage = sensor_data.get("bus_voltage_(V)")
    shunt_voltage = sensor_data.get("shunt_voltage_(V)")
    current = sensor_data.get("current_(mA)")

    # Statuswerte
    light_status = sensor_status.get("Light_Sensor")
    inner_status = sensor_status.get("Inner_Sensor")
    power_status = sensor_status.get("Power_Sensor")
    env_status = sensor_status.get("Environment_Sensor")

    # Beispielhafte Verwendung
    print(f"Licht: {lux}, Innen-Temp: {temp_in}, Außen-Temp: {temp_out}")
    print(f"Luftdruck: {air_pressure}, Luftfeuchte: {air_humidity}")
    print(f"Leistung: {power} W, Busspannung: {bus_voltage} V, Strom: {current} mA")
    print(f"Status Licht: {light_status}, Status Umwelt: {env_status}")

    
    return lux, temp_in, temp_out,air_pressure,power,light_status,inner_status,power_status, env_status


def nehme_bild_auf(camera, log_mode, Kamera_Fehlerserie, sn):
    Status_Kamera = 0
    photo_sanity_check = False
    if camera == "RPI_Module_3":
        Exposure = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "RPI_Module_3", "initial_exposure_10"))/10
        gain = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "RPI_Module_3", "initial_gain_10"))/10
        focus = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "RPI_Module_3", "focus")
    elif camera == "RPI_HQ":
        Exposure = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "RPI_HQ", "initial_exposure_10"))/10
        gain = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "RPI_HQ", "initial_gain_10"))/10
    elif camera == "AV__Alvium_1800_U-2050":
        Exposure = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "AV__Alvium_1800_U-2050", "initial_exposure"))
        gain = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "AV__Alvium_1800_U-2050", "initial_gain_10"))/10


    while not photo_sanity_check:
        print("starte Kamera")
        power_on = 0
        try:
            if camera == "AV__Alvium_1800_U-2050":
                code, current_image, Status_Kamera, power_on, Kamera_Fehlerserie, _, _, _, _ = snap_image_AV("jpg", "Diagnose", Kamera_Fehlerserie, log_mode, Exposure=Exposure, Gain=gain, sn = sn)
            elif camera == "RPI_Module_3":
                code, current_image, Status_Kamera, power_on, Kamera_Fehlerserie, _, _, _, _, _, _, _, _ = snap_image_rpi("jpg","Diagnose", Kamera_Fehlerserie, log_mode, camera, Exposure=int(Exposure), Gain=gain, focus=focus, sn = sn)
            elif camera == "RPI_HQ":
                print("starte Kamera3")
                code, current_image, Status_Kamera, power_on, Kamera_Fehlerserie, _, _, _, _, _, _ = snap_image_rpi("jpg","Diagnose", Kamera_Fehlerserie, log_mode, camera, Exposure=int(Exposure), Gain=gain, sn = sn)

        except Exception as e:
            log_schreiben(f"Fehler beim Aufnehmen des Bildes: {e}", log_mode)
            print(f"Fehler beim Aufnehmen des Bildes: {e}")
        
        if Status_Kamera == 1:
                try:
                    photo_sanity_check = check_image(current_image, log_mode)
                except Exception as e:
                    log_schreiben(f"Fehler bei der Bildprüfung: {e}", log_mode)
                    print(f"Fehler bei der Bildprüfung: {e}")
                    photo_sanity_check = False

                try:
                    time.sleep(1.5)
                    os.sync()
                    size = os.path.getsize(current_image)
                    print(f"Foto hat die Größe:{size}")
                    log_schreiben(f"Foto hat die Größe:{size} B", log_mode)
                except:
                    size = sum(
                    os.path.getsize(os.path.join(w, f))
                    for w, _, files in os.walk(current_image)
                    for f in files if os.path.isfile(os.path.join(w, f))
                    )
        
        
    print(f"Leistungsaufnahme Visible LED:{power_on}")
    log_schreiben(f"Listungsaufnahme Visible LED:{power_on}", log_mode)


    
    return photo_sanity_check, code, Status_Kamera, Kamera_Fehlerserie

'''
def set_sn():
    valid = False
    while not valid:
        sn_input = input("Seriennummer im Format 123456: ").strip()
        print(f"DEBUG: Eingabe war: '{sn_input}' (Länge: {len(sn_input)})")
        if re.match(r"^\d{6}$", sn_input):
            sn = f"SN{sn_input}"
            valid = True
            print(f"Seriennummer: {sn}") 
            write_fram(0x0110, sn)
            return sn
        else:
            print("Ungültiges Format. Beispiel: 123456")
            time.sleep(.5)
'''


def LEDs():
    log_schreiben("Teste Kontroll LEDs", log_mode)
    zeile1,zeile2,zeile3,zeile4,zeile5,zeile6 = "","","","","",""
    display_text(line1="LED Diagnose",line2=zeile2,line3=zeile3,line4=zeile4,line5=zeile5,line6=zeile6)

    for i in range(3):   
        turn_on_led("gelb")
        zeile3 = "gelb LED an"
        display_text(line1="LED Diagnose",line2=zeile2,line3=zeile3,line4=zeile4,line5=zeile5,line6=zeile6)
        time.sleep(.125)
        turn_on_led("blau")
        zeile4 = "Blaue LED an"
        display_text(line1="LED Diagnose",line2=zeile2,line3=zeile3,line4=zeile4,line5=zeile5,line6=zeile6)
        time.sleep(.125)
        turn_on_led("rot")
        zeile5 = "Rote LED an"
        display_text(line1="LED Diagnose",line2=zeile2,line3=zeile3,line4=zeile4,line5=zeile5,line6=zeile6)

        time.sleep(.5) 
        turn_off_led("rot")
        zeile3 = "Rote LED    aus"
        display_text(line1="LED Diagnose",line2=zeile2,line3=zeile3,line4=zeile4,line5=zeile5,line6=zeile6)
        time.sleep(.125)
        turn_off_led("blau")
        zeile4 = "Blaue LED    aus"
        display_text(line1="LED Diagnose",line2=zeile2,line3=zeile3,line4=zeile4,line5=zeile5,line6=zeile6)
        time.sleep(.125)
        turn_off_led("gelb")
        zeile5 = "Gelbe LED    aus"
        display_text(line1="LED Diagnose",line2=zeile2,line3=zeile3,line4=zeile4,line5=zeile5,line6=zeile6)
        time.sleep(.5)
        zeile1,zeile2,zeile3,zeile4,zeile5,zeile6 = "","","","","",""
        display_text(line1="LED Diagnose",line2=zeile2,line3=zeile3,line4=zeile4,line5=zeile5,line6=zeile6)


def write_fram_random():
    zufallszahl = random.randint(100, 999)
    zufallszahl_str = str(zufallszahl)
    write_fram(0x0577, zufallszahl_str)
        
    return zufallszahl 
 

def read_fram_random() -> bytes:
    status_ram = 0
    try:
        result = read_fram(0x0577,3)
        status_ram = 1
    except Exception as e:
        log_schreiben(f"Fehler beim Lesen des RAMs: {e}", log_mode)
        print(f"Fehler beim Lesen des RAMs: {e}")
        result = None
    return result, status_ram



def display_text(line1=None, line2=None, line3=None, line4=None, line5=None, line6=None, sleeptime=0):
    global zeile1, zeile2, zeile3, zeile4, zeile5, zeile6
    # Nur die übergebenen Zeilen aktualisieren, andere behalten
    if line1 is not None:
        zeile1 = line1
    if line2 is not None:
        zeile2 = line2
    if line3 is not None:
        zeile3 = line3
    if line4 is not None:
        zeile4 = line4
    if line5 is not None:
        zeile5 = line5
    if line6 is not None:
        zeile6 = line6
    try:
        with canvas(oled) as draw:
            draw.text((2, 1),  zeile1, font=oled_font, fill="white")
            draw.text((2, 11), zeile2, font=oled_font, fill="white")
            draw.text((2, 21), zeile3, font=oled_font, fill="white")
            draw.text((2, 31), zeile4, font=oled_font, fill="white")
            draw.text((2, 41), zeile5, font=oled_font, fill="white")
            draw.text((2, 51), zeile6, font=oled_font, fill="white")
        time.sleep(sleeptime)
    except:
        pass

def get_config():
    CONFIG_PATH = "/home/Ento/LepmonOS/LepmonOS_Service_fram_config.ini"
    config = ConfigParser()
    ARNI_version, backplane_version, lieferdatum_an_PMJ = None, None, None
    try:
        config.read(CONFIG_PATH)
        if "FRAM" not in config.sections():
            print("Sektion [FRAM] fehlt! Datei oder Pfad prüfen.")
        elif "FRAM" in config.sections():
            print("FRAM Konfigurationsdatei erfolgreich gelesen.")
            fram_config = dict(config.items("FRAM"))
            # Optional: Variablen direkt zuweisen
            ARNI_version = fram_config.get("arni_version")
            backplane_version = fram_config.get("backplane_version")
            lieferdatum_an_PMJ = fram_config.get("lieferdatum_an_pmj")

    except Exception as e:
        print(f"Fehler beim Lesen der FRAM Konfigurationsdatei: {e}")
    
    return ARNI_version, backplane_version, lieferdatum_an_PMJ




####################################################################################################################################################
####################################################################################################################################################
####################################################################################################################################################
####################################################################################################################################################
####################################################################################################################################################


if __name__ == "__main__":
    selected_tests = {
        0 : "Seriennummer",
        1: "OLED",
        2: "LEDs",
        3: "Sensoren",
        4: "Uhr",
        5: "RAM",
        6: "RAM_löschen",
        7: "RAM_Konfiguration",
        8: "Knöpfe",
        9: "Kamera"
    }
    
    Kamera_Fehlerserie = 0 
    log_mode = "log"
    ARNI_version, backplane_version, lieferdatum_an_PMJ = get_config()
    zeile1, zeile2, zeile3, zeile4, zeile5, zeile6 = "", "", "", "", "", ""




    print("FRAM Konfigurator und ARNI Diagnose GEN 4")
    print(f"Achtung! Verschiedene Generationen für ARNI Pro und CS. Überprüfe config.ini Einträge!\naktuelle Konfiguration:\nARNI Version:   {ARNI_version},\nBackplane Version:{backplane_version},\nLieferdatum an PMJ:    {lieferdatum_an_PMJ}\n")
    time.sleep(2)
    '''
    check = input("Verwende:\n"
        "  Pro_Gen_4 für Allied Vision Variante\n"
        "  CSS_Gen_1 für 3D Druck\n"
        "  CSL_Gen_1 für Einbeiniges Gerät\n"
        "\n"
        "Eintrag ist kontrolliert und korrekt: 'ok'\n"
        "Korrektur nötig: 'stop'\n"
    )
    if check.strip().lower() == "ok":
        configuration_ok = True
    else:
        print("Diagnose abgebrochen. Korrigiere .ini Datei und starte erneut.")
        exit()
    '''

    print("\nStarte Diagnose. Schritt 1-9 frei einstellbar in Zeil3 268 (1-OLED,2-LEDs,3-Sensoren,4-Uhr,5-RAM,6-RAM_löschen,7-RAM_Konfiguration,8-Knöpfe,9-Kamera)\n")

    '''   
    if 0 in selected_tests:
        sn = set_sn()
        
    else:
        sn = "SN000000"
    '''
    set_paths(sn)
    print("erster log in main")
    log_schreiben(f"Seriennummer gesetzt auf: {sn}","Diagnose")
    print(f"Seriennummer gesetzt auf: {sn}")
    

    if 1 in selected_tests:
        log_schreiben("---------------------------", log_mode)
        log_schreiben("Initialisiere Display", log_mode)
        print("Initialisiere Display")
        try:
            serial = i2c(port=1, address=0x3C)
            oled = sh1106(serial)
            oled_font = ImageFont.truetype('FreeSans.ttf', 10)
            log_schreiben("Display initialisiert", log_mode)
            print("Display initialisiert")
        except:
            log_schreiben("Display nicht initialisiert", log_mode)
            print("Display nicht initialisiert")
            pass


    log_schreiben("Beginne Diaganose", log_mode)
    print("Beginne Diaganose")
    Zeit, _, _ = Zeit_aktualisieren(log_mode)


    if 2 in selected_tests:
        log_schreiben("---------------------------", log_mode)
        log_schreiben("Teste Kontroll LEDs", log_mode)
        print("Teste Kontroll LEDs")
        LEDs()
    

    if 3 in selected_tests:
        log_schreiben("---------------------------", log_mode)
        log_schreiben("Teste Sensoren", log_mode)
        print("Teste Sensoren")
        erster_run = True
        logged = False
        light_status, inner_status, power_status, env_status = 0,0,0,0
        while light_status == 0 or inner_status == 0 or power_status == 0 or env_status == 0 or erster_run:
            erster_run = False
            for i in range(10):
                lux, temp_in, temp_out,air_pressure,power,light_status,inner_status,power_status, env_status = update_sensor_data("000",Zeit, log_mode)
                Zeit, _, _ = Zeit_aktualisieren(log_mode)
                zeile1 = "Sensordiagnose"
                zeile2 = ""
                zeile3 = f"Light:{lux}Lux; In:{temp_in}°C"
                zeile4 = f"Power:{power}W; out:{air_pressure }hPa"
                zeile5 = f"Statuus:{light_status}-{inner_status}-{power_status}-{env_status}"
                zeile6 =f"Zeit {Zeit}"
                
                display_text(line1=zeile1,line2=zeile2,line3=zeile3,line4=zeile4,line5=zeile5,line6=zeile6)
                time.sleep(.5)
                if logged == False:
                    log_schreiben(f"Status Sensoren: \nLicht:{light_status}; \nInnen:{inner_status}; \nLeistung:{power_status}; \nUmwelt:{env_status}", log_mode)
                    log_schreiben(f"Sensorwerte: \nLicht:{lux}Lux; \nInnen:{temp_in}°C; \nAußen:{temp_out}°C; \nLuftdruck:{air_pressure }hPa; \nLeistung:{power}W", log_mode)
                    logged = True
                if light_status == 0 or inner_status == 0 or power_status == 0 or env_status == 0:
                    log_schreiben("Fehlerhafte Sensorwerte erkannt, wiederhole Messung", log_mode)
                    print("Fehlerhafte Sensorwerte erkannt, wiederhole Messung")
                    logged == False
                    time.sleep(1)
        
        display_text("","","","","","")
        time.sleep(1)

    if 4 in selected_tests:
        zeile1, zeile2, zeile3, zeile4, zeile5, zeile6 = "teste Uhr", "", "", "", "", ""
        display_text(line1=zeile1,line2=zeile2,line3=zeile3,line4=zeile4,line5=zeile5,line6=zeile6)
        log_schreiben("---------------------------", log_mode)
        log_schreiben("Teste Uhr", log_mode)
        print("Teste Uhr")
        try:
            
            date_time_list =     "20260202190000"  
            zeile2 = f"Setze Uhr auf:"
            zeile3 = f"{date_time_list}"
            display_text(line1=zeile1,line2=zeile2,line3=zeile3,line4=zeile4,line5=zeile5,line6=zeile6)
            set_hwc(rtc_mode="manual", log_mode="manual", date_time_list=date_time_list)
            log_schreiben(f"RTC Uhr erfolgreich gesetzt auf {date_time_list}", log_mode)
            print("RTC Uhr erfolgreich gesetzt")
            zeile4 = "RTC Uhr aktualisiert"
            display_text(line1=zeile1,line2=zeile2,line3=zeile3,line4=zeile4,line5=zeile5,line6=zeile6)
        except Exception as e:
            log_schreiben(f"Fehler beim Setzen der RTC Uhr: {e}", log_mode)
            print(f"Fehler beim Setzen der RTC Uhr: {e}")
            zeile4 = "Fehler bei der RTC"
            display_text(line1=zeile1,line2=zeile2,line3=zeile3,line4=zeile4,line5=zeile5,line6=zeile6)
            pass


    if 5 in selected_tests:
        log_schreiben("---------------------------", log_mode)
        log_schreiben("Teste Ram", log_mode)
        print("Teste Ram")
        zeile1 = "RAM Diagnose"
        zeile2 = f"SN gelesen: {read_fram(0x0110, 8).strip()}"
        zeile3, zeile6 = "",""

        ram_test_liste = []
        for i in range(5):
            Zeit, _, _ = Zeit_aktualisieren(log_mode)
            geschrieben = write_fram_random()
            time.sleep(.75)
            zeile4 = f"geschrieben: {geschrieben}"
            zeile6 =f"Zeit {Zeit}"
            display_text(line1=zeile1,line2=zeile2,line3=zeile3,line4=zeile4,line5="",line6=zeile6)
            time.sleep(.5)
            gelesen, status_ram = read_fram_random()
            zeile5 = f"gelesen:        {gelesen}"
            display_text(line1=zeile1,line2=zeile2,line3=zeile3,line4=zeile4,line5=zeile5,line6=zeile6)
            time.sleep(1)
            ram_test_liste.append((geschrieben, gelesen))


        print("\nRAM-Test Ergebnisse (geschrieben/gelesen):")
        log_schreiben("RAM-Test Ergebnisse (geschrieben/gelesen):", log_mode)
        alle_ok = True
        for idx, (w, r) in enumerate(ram_test_liste):
            ok = (str(w) == str(r))
            ergebnis_str = f"{idx+1}: geschrieben={w}, gelesen={r} -> {'OK' if ok else 'FEHLER'}"
            print(ergebnis_str)
            log_schreiben(ergebnis_str, log_mode)
            if not ok:
                alle_ok = False
        if alle_ok and status_ram == 1:
            print("Alle Werte stimmen überein!")
            log_schreiben("Alle Werte stimmen überein!", log_mode)
            ram_success = True
        else:
            print("Mindestens ein Wert stimmt NICHT überein!")
            log_schreiben("Mindestens ein Wert stimmt NICHT überein!", log_mode)
            ram_success = False


    if 6 in selected_tests:
        Zeit, _, _ = Zeit_aktualisieren(log_mode)
        zeile1, zeile2, zeile3, zeile4, zeile5, zeile6 = "RAM löschen", "", "", "", "", ""
        zeile6 =f"Zeit {Zeit}"
        display_text(line1=zeile1,line2=zeile2,line3=zeile3,line4=zeile4,line5=zeile5,line6=zeile6)
        log_schreiben("---------------------------", log_mode)
        log_schreiben("Lösche RAM Bereich 0x0118 - 0x0BFF", log_mode)
        
        print("Lösche RAM Bereich 0x0118 - 0x0BFF")
        try:
            zeile2 = "..."
            display_text(line1=zeile1,line2=zeile2,line3=zeile3,line4=zeile4,line5=zeile5,line6=zeile6)
            clear_fram("setup", log_mode)
            log_schreiben("RAM Bereich 0x0118 - 0x0BFF erfolgreich gelöscht", log_mode)
            print("RAM Bereich 0x0118 - 0x0BFF erfolgreich gelöscht")
            zeile3 = "Ram gelöscht"
            display_text(line1=zeile1,line2=zeile2,line3=zeile3,line4=zeile4,line5=zeile5,line6=zeile6)
        except Exception as e:
            log_schreiben(f"Fehler beim Löschen des RAM-Bereichs: {e}", log_mode)
            print(f"Fehler beim Löschen des RAM-Bereichs: {e}")
            zeile3 = "Fehler beim Löschen"
            display_text(line1=zeile1,line2=zeile2,line3=zeile3,line4=zeile4,line5=zeile5,line6=zeile6)
            pass


    if 7 in selected_tests:
        if not 5 in selected_tests:
            ram_success = True
        if not ram_success:
            log_schreiben("RAM Diagnose fehlgeschlagen, keine Konfiguration durchgeführt", log_mode)
            print("RAM Diagnose fehlgeschlagen, keine Konfiguration durchgeführt")
        
        if ram_success:
            Zeit, _, _ = Zeit_aktualisieren(log_mode)
            zeile1, zeile2, zeile3, zeile4, zeile5, zeile6 = "RAM konfigurieren", "", "", "", "", ""
            zeile6 = f"Zeit {Zeit}"
            display_text(line1=zeile1,line2=zeile2,line3=zeile3,line4=zeile4,line5=zeile5,line6=zeile6)
            try:
                print("konfiguriere Ram...")
                log_schreiben("---------------------------", log_mode)
                log_schreiben("Konfiguriere RAM", log_mode)
                zeile2 = "..."
                display_text(line1=zeile1,line2=zeile2,line3=zeile3,line4=zeile4,line5=zeile5,line6=zeile6)
                write_config_to_fram(ARNI_version, backplane_version, lieferdatum_an_PMJ,log_mode)
                zeile3 = "RAM konfiguration beendet"
                display_text(line1=zeile1,line2=zeile2,line3=zeile3,line4=zeile4,line5=zeile5,line6=zeile6)
                
            except Exception as e:
                log_schreiben(f"Fehler bei der RAM Konfiguration: {e}", log_mode)
                print(f"Fehler bei der RAM Konfiguration: {e}")
                zeile3 = "Fehler bei RAM Konfiguration"
                display_text(line1=zeile1,line2=zeile2,line3=zeile3,line4=zeile4,line5=zeile5,line6=zeile6)
                pass
            try:
                Zeit, _, _ = Zeit_aktualisieren(log_mode)
                
                print("Lese RAM Konfiguration aus...")
                log_schreiben("Lese RAM Konfiguration aus", log_mode)
                zeile4 = "lese Ram"
                zeile6 =f"Zeit {Zeit}"
                display_text(line1=zeile1,line2=zeile2,line3=zeile3,line4=zeile4,line5=zeile5,line6=zeile6) 
                werte = get_Fram_table(log_mode)
                print("RAM Konfiguration ausgelesen")
                log_schreiben("RAM Konfiguration:", log_mode)
                zeile5 = "Ram gelesen --> Terminal"
                display_text(line1=zeile1,line2=zeile2,line3=zeile3,line4=zeile4,line5=zeile5,line6=zeile6)
                write_fram_table_to_log(werte, log_mode)
                dump_fram(0x0000, 0x09EF)
            except Exception as e:
                log_schreiben(f"Fehler beim Lesen der RAM Konfiguration: {e}", log_mode)
                print(f"Fehler beim Lesen der RAM Konfiguration: {e}")
                zeile5 = "Fehler beim Lesen des RAMs"
                zeile6 =f"Zeit {Zeit}"
                display_text(line1=zeile1,line2=zeile2,line3=zeile3,line4=zeile4,line5=zeile5,line6=zeile6)
    

    if 8 in selected_tests:
        log_schreiben("---------------------------", log_mode)
        log_schreiben("Teste Knöpfe", log_mode)
        print("Teste Knöpfe")
        zeile1 = "Knopf Diagnose"
        up, down, right, inp, oben, unten, rechts, enter = 0,0,0,0,False,False,False,False
        while oben == False or unten == False or rechts == False or enter == False:
            up, down, right, inp, oben, unten, rechts, enter = buttons(up, down, right, inp, oben, unten, rechts, enter)
            Zeit, _, _ = Zeit_aktualisieren(log_mode)
            zeile2 = f"Oben:  {oben}  -  {up}"
            zeile3 = f"Unten: {unten}  -  {down}"
            zeile4 = f"Rechts:{rechts}  -  {right}"
            zeile5 = f"Enter: {enter}  -  {inp}"
            zeile6 =f"Zeit {Zeit}"
            display_text(line1=zeile1,line2=zeile2,line3=zeile3,line4=zeile4,line5=zeile5,line6=zeile6)
            time.sleep(.05)
        if oben:
            log_schreiben("Knopf oben gedrückt", log_mode)
            print("Knopf oben gedrückt")
        if unten:
            log_schreiben("Knopf unten gedrückt", log_mode)
            print("Knopf unten gedrückt")
        if rechts:
            log_schreiben("Knopf rechts gedrückt", log_mode)
            print("Knopf rechts gedrückt")
        if enter:
            log_schreiben("Knopf enter gedrückt", log_mode)
            print("Knopf enter gedrückt")   
        if oben and unten and rechts and enter:
            log_schreiben("Alle Knöpfe erfolgreich getestet", log_mode)
            print("Alle Knöpfe erfolgreich getestet")
        

    if 9 in selected_tests:
        log_schreiben("---------------------------", log_mode)
        log_schreiben("Teste Kamera", log_mode)
        print("Teste Kamera")
        camera = get_device_info("camera")
        log_schreiben(f"verwendete Kamera: {camera}", log_mode)
        print(f"verwendete Kamera: {camera}")
        zeile1,zeile2,zeile3,zeile4,zeile5,zeile6 = "","","","","",""
        zeile1 = "Diagnose Kamera"
        zeile2 = "Initialisiere Kamera"
        if camera == "AV__Alvium_1800_U-2050":
            for i in range(1, 7):
                print('-' * i)
                time.sleep(1)
                display_text(line1=zeile1,line2=zeile2,line3=zeile3,line4=zeile4,line5=zeile5,line6=zeile6)
        
        zeile3 = "Strahler und UV dimmen"
        display_text(line1=zeile1,line2=zeile2,line3=zeile3,line4=zeile4,line5=zeile5,line6=zeile6)
        LepiLED_start("show")
        log_schreiben("Strahler und UV an", log_mode)

        photo_sanity_check, code, Status_Kamera, Kamera_Fehlerserie = nehme_bild_auf(camera, log_mode, Kamera_Fehlerserie, sn)

        LepiLED_ende("show")
        log_schreiben("Strahler und UV aus", log_mode)

        zeile4 = f"Status Kamera: {1}"
        zeile5 = f"Bild vollständig: {photo_sanity_check}"

        log_schreiben(f"Status Kamera: {Status_Kamera}", log_mode)
        log_schreiben(f"Bild vollständig: {photo_sanity_check}", log_mode)

        display_text(line1=zeile1,line2=zeile2,line3=zeile3,line4=zeile4,line5=zeile5,line6=zeile6)
        time.sleep (3)
        display_text(line1="Diagnose",line2="",line3="erfolgreich",line4="",line5="",line6="beendet")
        time.sleep(3)
    log_schreiben("Diagnose beendet", log_mode)
    exit()