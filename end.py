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

def trap_shutdown(log_mode,i):
    try:
        Errorcode = int.from_bytes(read_fram_bytes(0x0810, 4), byteorder='big')
        time.sleep(.5)
    except Exception as e:  
        try:
            Errorcode = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "capture_mode", "error_code"))
        except Exception:
            Errorcode = 0
    print(f"Fehlercode: {Errorcode}")
    
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

    if 8 > Errorcode > 0 :
        jetzt_local, _,_ = Zeit_aktualisieren(log_mode)
        jetzt_local_dt = datetime.strptime(jetzt_local, "%Y-%m-%d %H:%M:%S")
        print(f"Aktuelle Zeit: {jetzt_local}")
        
        Nächstes_Anschalten = jetzt_local_dt + timedelta(minutes=2)
        Nächster_Tag = jetzt_local_dt + timedelta(days=1)
        set_alarm(Nächstes_Anschalten.strftime("%Y-%m-%d %H:%M:%S"), Nächster_Tag.strftime("%Y-%m-%d %H:%M:%S"), log_mode)
        print(f"Alarm gesetzt auf: {Nächstes_Anschalten.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Alarm gesetzt auf: {Nächster_Tag.strftime('%Y-%m-%d %H:%M:%S')}")
        send_lora(f"ARNI fährt in {i} Sekunden herunter und startet dann neu. Letzte Nachricht im aktuellen Run")
        time.sleep(.5)

    else :
        send_lora(f"ARNI fährt in {i} Sekunden herunter. Letzte Nachricht im aktuellen Run\nBeachte, dass der Solarregler ARNI ggf. erst kurz vor der nächsten Dämmerung wieder aktiviert")
        time.sleep(.5)
        
    for sec in range(i, 0, -1):
        show_message("end_1", lang = get_language(), time = sec)
    display_text_and_image("Neustart","restart","reiniciar","/home/Ento/LepmonOS/startsequenz/end.png",0)
        
    
    on_shutdown()
    time.sleep(2)
    if power_mode == "Netz":
        if log_mode == "log":
            os.system("sudo reboot")
            time.sleep(2)
            print("Systembefehl zum Neustart ausgeführt.")
        elif log_mode == "manual":
            print("System würde jetzt neu starten (Reboot)")

    if power_mode == "Solar":
        if log_mode == "log":
            print("PV Modus neustart in 61 Sekunden")
            time.sleep(1)
            os.system("sudo shutdown -r 61")
        elif log_mode == "manual":
            print("System würde jetzt im PV Modus neu starten (Reboot in 61 Sekunden)")

if __name__ == "__main__":
    trap_shutdown("manual",2)    
    print("Ende")