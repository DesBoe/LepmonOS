import os
from lora import  send_lora
from OLED_panel import *
import time
from datetime import datetime, timedelta
from times import Zeit_aktualisieren
from RTC_alarm import set_alarm
from json_read_write import  get_value_from_section
from runtime import on_shutdown
try:
    from fram_direct import *
except ImportError:
    print("FRAM module not found. Skipping FRAM related operations.")
    pass
from language import get_language
import RPi.GPIO as GPIO
from logging_utils import *
from times import *
from fram_operations import store_times_power

GPIO.setmode(GPIO.BCM)

Power_control_GPIO = 12
GPIO.setup(Power_control_GPIO, GPIO.OUT, initial=GPIO.HIGH)

from hardware import get_hardware_version  
hardware = get_hardware_version()

def trap_shutdown(i,log_mode,execution="full"):
    ''' 
    modes:
    - full: Shutdown - Neustart mit Attiny erst am nächsten Tag, wenn experimentiert wird
    - test: Shutdown - Neustart mit Attiny nach 1 Minute (für Testzwecke)
    - anzeige: Zeige Countdown und Nachricht, aber führe keinen echten Shutdown durch (für Demozwecke)

    '''
    try:
        Errorcode = int.from_bytes(read_fram_bytes(0x0810, 4), byteorder='big')
        print(f"Fehlercode {Errorcode} aus dem FRAM gelesen.")
        time.sleep(.5)
    except Exception as e:  
        try:
            Errorcode = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "capture_mode", "error_code"))
            print(f"Fehlercode {Errorcode} aus der Konfigurationsdatei gelesen.")
            time.sleep(.5)
        except Exception:
            Errorcode = 0
            log_schreiben(f"Fehler beim Lesen des Errorcodes: {e}", log_mode)
    log_schreiben(f"Fehlercode vor Shutdown: {Errorcode}", log_mode)
    
    try:
        power_mode = read_fram(0x03B0, 16).replace('\x00', '').strip()
        time.sleep(.5)
    except Exception as e:
        log_schreiben(f"Fehler beim Lesen des Power-Modus: {e}", log_mode)
        try:
            power_mode = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "powermode", "supply")
            time.sleep(.5)
        except Exception as e:
            log_schreiben(f"Fehler beim Lesen des Power-Modus aus der Konfigurationsdatei: {e}", log_mode)
            power_mode = "Netz"
    print(f"Power-Modus vor Shutdown: {power_mode}, error_code: {Errorcode}")

    if 8 > Errorcode >= 0 :
        jetzt_local, _,_ = Zeit_aktualisieren(log_mode)
        jetzt_local = datetime.strptime(jetzt_local, "%Y-%m-%d %H:%M:%S")
        next_experiment_start_time, next_experiment_end_time = get_times_power()
        next_experiment_start_time = datetime.strptime(next_experiment_start_time, "%Y-%m-%d %H:%M:%S")
        next_experiment_end_time = datetime.strptime(next_experiment_end_time, "%Y-%m-%d %H:%M:%S")
        log_schreiben(f"nächstes Anschalten: {next_experiment_start_time}", log_mode)

        timebuffer_powermanager = timedelta(minutes=int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "capture_mode", "timebuffer_powermanager")))

        Nächstes_Ausschalten = jetzt_local + timedelta(days=1)
        
        Nächstes_Ausschalten = Nächstes_Ausschalten.replace(hour=next_experiment_end_time.hour, minute=next_experiment_end_time.minute, second=next_experiment_end_time.second) - timebuffer_powermanager
        log_schreiben(f"Nächstes Ausschalten berechnet, Zeitstempel zum schreiben: {Nächstes_Ausschalten}", log_mode)

        try:
            set_alarm(next_experiment_start_time.strftime("%Y-%m-%d %H:%M:%S"), Nächstes_Ausschalten.strftime("%Y-%m-%d %H:%M:%S"), log_mode)
            log_schreiben(f"Alarm für nächstes Anschalten gesetzt auf:  {next_experiment_start_time.strftime('%Y-%m-%d %H:%M:%S')}", log_mode)
            log_schreiben(f"Alarm für nächstes Ausschalten gesetzt auf: {Nächstes_Ausschalten.strftime('%Y-%m-%d %H:%M:%S')}", log_mode)
        except Exception as e:
            log_schreiben(f"Fehler beim Setzen der Alarme: {e}", log_mode)

        send_lora(f"ARNI fährt herunter.\nnächstes Experiment für {next_experiment_start_time} erwartet.\nLetzte Nachricht im aktuellen Run")
        time.sleep(.5)

    else :
        send_lora(f"ARNI fährt herunter. Letzte Nachricht im aktuellen Run\nBeachte, dass der Solarregler ARNI ggf. erst kurz vor der nächsten Dämmerung wieder aktiviert")
        time.sleep(.5)

    if execution != "full":
        print("Überschreibe Alarmzeit auf 1 Minute in der Zukunft für manuelles Testen.")
        next_experiment_start_time = datetime.now() + timedelta(minutes=1)
        Nächstes_Ausschalten = next_experiment_start_time + timedelta(minutes=4)
        try:
            #set_alarm(Nächstes_Anschalten.strftime("%Y-%m-%d %H:%M:%S"), Nächstes_Ausschalten.strftime("%Y-%m-%d %H:%M:%S"), log_mode)
            set_alarm(next_experiment_start_time.strftime("%Y-%m-%d %H:%M:%S"), Nächstes_Ausschalten.strftime("%Y-%m-%d %H:%M:%S"), log_mode)

            print(f"Alarm für nächstes Anschalten gesetzt auf:  {next_experiment_start_time}")
            print(f"Alarm für nächstes Ausschalten gesetzt auf: {Nächstes_Ausschalten.strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception as e:
            print(f"Fehler beim Setzen der Alarme: {e}")

    try:
        store_times_power(next_experiment_start_time, Nächstes_Ausschalten.strftime('%Y-%m-%d %H:%M:%S'), "end")
        print("zeiten des nächsten Experiments auch im FRAM gemerkt")
    except Exception as e:
        log_schreiben(f"Fehler beim Speichern der Zeiten des nächsten Experiments im FRAM:{e}", log_mode)

    for sec in range(i, 0, -1):
        show_message("end_1", lang = get_language(), time = sec)
    display_text_and_image("Neustart","restart","reiniciar","/home/Ento/LepmonOS/startsequenz/end.png",0)
        
    
    on_shutdown()
    time.sleep(2)


    if hardware in ["Pro_Gen_1","Pro_Gen_2", "Pro_Gen_3"]:
        if power_mode == "Netz":
            log_schreiben("Reboot im Netzmodus in 5 Sekunden", log_mode)
            log_schreiben("##################################",log_mode)
            log_schreiben("### SELBSTINDUZIERTER SHUTDOWN ###",log_mode)
            log_schreiben("##################################",log_mode)
            time.sleep(5)
            if execution == "full":
                os.system("sudo reboot")
                time.sleep(2)
                print("Systembefehl zum Neustart ausgeführt.")
            elif execution != "full":
                print("System würde jetzt neu starten (Reboot)")

        if power_mode == "Solar":
            log_schreiben("Shutdown im PV Modus in 5 Sekunden", log_mode)
            log_schreiben("##################################",log_mode)
            log_schreiben("### SELBSTINDUZIERTER SHUTDOWN ###",log_mode)
            log_schreiben("##################################",log_mode)
            time.sleep(2)
            if execution == "full":
                os.system("sudo shutdown -r 5")
            elif execution != "full":
                print("System würde jetzt im PV Modus neu starten (Reboot in 61 Sekunden)")

    elif hardware in ["Pro_Gen_4","CSS_Gen_1", "CSL_Gen_1"]:
            log_schreiben("setze GPIO Pin für Power Control auf LOW, um ARNI herunterzufahren", log_mode)
            if execution == "anzeige":
                print("GPIO Pin für Power Control würde auf LOW gesetzt, um ARNI herunterzufahren")
                time.sleep(0.25)
                print("System würde jetzt im Power Safe Modus herunterfahren (Attiny übernimmt Steuerung)")
            elif execution == "full" or execution == "test":
                GPIO.output(Power_control_GPIO, GPIO.LOW)
            status = GPIO.input(Power_control_GPIO)
            log_schreiben(f"Status GPIO Pin für Power Control: {status}", log_mode)

            time.sleep(0.25)
            log_schreiben("Shutdown mit Power Safe Modus (Attiny)", log_mode)
            log_schreiben("##################################",log_mode)
            log_schreiben("### SELBSTINDUZIERTER SHUTDOWN ###",log_mode)
            log_schreiben("##################################",log_mode)
            if execution == "full" or execution == "test":
                os.system("sudo shutdown -h now")
        

if __name__ == "__main__":
    trap_shutdown(i=2, log_mode="manual", execution="test")
    print("Ende")