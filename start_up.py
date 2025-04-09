from times import get_times_power
from OLED_panel import *
from service import *
from logging_utils import log_schreiben
from lora import send_lora
from logging_utils import *
import time
from times import *
from json_read_write import *
from RTC_alarm import *
from fram_operations import *
from service import *
from runtime import *
from GPIO_Setup import turn_off_led
from end import trap_shutdown
from bootconfig import add_to_bootconfig
from hardware import *
import os
from serial_number_manual import *
from datetime import datetime
from Box_Experiment_Times import *
import pandas as pd


def version_tuple(version_str):
    return tuple(map(int, version_str.strip().split(".")))

def start_up(log_mode):
    # Update:Ram Neu Beschreiben für INFO zur Firmware.
    # Kontrollbit für Trigger versteckte Menüs bei (nur) bei Update zusätzlich zurücksetzen

    new_version = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "software", "version")
    new_date = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "software", "date")

    try: 
        current_version = read_fram(0x0520, 5)
        current_version = current_version.strip()
    except Exception as e:
        print(f"Fehler beim Lesen der aktuellen Firmware-Version aus dem FRAM: {e}")
        current_version = None

    try:
        if not current_version == None and version_tuple(new_version) > version_tuple(current_version):
        
            write_fram(0x0520, new_version.ljust(7)) 
            write_fram(0x0510, new_date.ljust(10))
            print(f"Firmware Version im FRAM aktualisiert:{new_version}; {new_date}")
    
            write_fram_bytes(0x078F, b'\x00')
            print("Kontrollbit für versteckte Menüs zurückgesetzt")
        
        elif current_version == None:

            print("keine aktuelle Firmware-Version im FRAM gefunden")
    
    except Exception as e:
                print(f"Fehler beim Zugriff auf FRAN wärend Kontrollbit bzw. Versionsvergleich im FRAM: {e}")
    


    print("starte Setup")
    turn_off_led("blau")
    turn_off_led("heizung")
    RPI_time(log_mode)


    display_image_3_2("/home/Ento/LepmonOS/startsequenz/start_K2W.png",sleeptime = 0) # Logo wird für die Dauer angezeigt, in der es möglich ist, die SN manuell zu setzen.
    sn_trigger, _, Gen_json = trigger_manual_sn()
    if sn_trigger:
        sn_manual, gen_manual = set_sn_manually()
        if gen_manual == "Pro_Gen_1" and Gen_json != "Pro_Gen_1":
            display_text_and_image("Neustart","restart","reiniciar","/home/Ento/LepmonOS/startsequenz/end.png",0)
            os.system("sudo reboot")
            time.sleep(2)
            os.system("sudo reboot")

    display_image_3_2("/home/Ento/LepmonOS/startsequenz/start_U2C.png",sleeptime = 4)
    display_text_and_image("Leitfaden","Guide","Guia","/home/Ento/LepmonOS/startsequenz/link_manual.png",4)
    on_start()
    sn = compare_fram_json(log_mode)
    
    check_Lepmon_code()
    
    time.sleep(3)
    
    lang = get_language()
    hardware=get_hardware_version()
    show_message("device_1", lang=lang,
                 hardware=hardware,
                 sn=sn[2:],
                 version=get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "software", "version"))
    time.sleep(1)
    
    
    
    date = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "software", "date") 

    write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "serielnumber", sn)

    send_lora("Starte Lepmon Software")
    
    try:
        device_run = ram_counter(0x0310)
    except Exception as e:
        print(f"Fehler beim Lesen des RAM-Counters: {e}")

    delete_error_code()
    status_USB = 0
    try:
        USB_stick, status_USB = get_usb_path(log_mode)
        print(f"USB stick: {USB_stick}")
        write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "usb_drive", USB_stick)
    except Exception as e:
        print(f"Fehler beim USB Stick:{e}")
    if not status_USB:   
        print(f"Fehler beim Erkennen des USB-Sticks")
        try:
            log_schreiben("##################################", log_mode=log_mode)
            log_schreiben("### SELBSTINDUZIERTER SHUTDOWN ###", log_mode=log_mode)
            log_schreiben("##################################", log_mode=log_mode) 
        except Exception as e:
            pass
        trap_shutdown(log_mode,10)
        return
        
    display_text_and_image("Will-","kommen", "", "/home/Ento/LepmonOS/startsequenz/Logo_1_9.png",1) 
    try:
        control_bit = read_fram_bytes(0x07A0, 1) == b'\x01'
        # Kontrollbit wird nur im Capturing zurückgesetzt --> Ordner für Updates und manuelle Neustarts durch Nutzer werden geloggt und bleiben erhalten
    except Exception as e:    
        control_bit = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "Control_End")
    print("letzer Fang nicht ordnungsgemäß beendet:", control_bit)    
    
    display_text_and_image("Will-","kommen", "", "/home/Ento/LepmonOS/startsequenz/Logo_2_9.png",1)
    # Neuen Ordner auch dann erstellen, wenn der alte Ordner nicht gefunden wird --> USB Stick wurde gewechselt
    ordner_from_config = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "current_folder")
    ordner = os.path.basename(ordner_from_config)
    print(f"Ordner aus ConfigJson: {ordner_from_config}")
    print(f"letzter Ordner- Name:  {ordner}")
    ordner_path = os.path.join(USB_stick, ordner)
    print(f"Vollständiger Pfad zum neuen Ordner: {ordner_path}")
    
    print(f"bestimme, ob neuer Ordner existiert: {ordner_path}")

    
    if not os.path.exists(ordner_path) or ordner == "":
        control_bit = False
        print("Ordner auf USB Stick nicht gefunden. Annahme, dass ein neuer USB Stick eingelegt wurde. Erstelle neuen Ordner")
    elif os.path.exists(ordner_path):
        print("vorhierige Ordner gefunden")
        
    display_text_and_image("Will-","kommen", "", "/home/Ento/LepmonOS/startsequenz/Logo_3_9.png",1)
    
    if control_bit:
        print("Überprüfe ob ein halber Tag seit letztem Fang vergangen ist. Wenn ja, wird Kontrollbit zurückgesetzt, um neuen Ordner zu erstellen")
        control_bit = gap_day()

    if not control_bit:
        ordner = erstelle_ordner(log_mode)
        print (f"neuer Ordner erstellt: {ordner}")
        if ordner == None:
            display_text("USB Stick","nicht erkannt","neu einstecken",3)
            log_schreiben("##################################", log_mode=log_mode)
            log_schreiben("### SELBSTINDUZIERTER SHUTDOWN ###", log_mode=log_mode)
            log_schreiben("##################################", log_mode=log_mode)
            trap_shutdown(log_mode,10)
            return
        initialisiere_logfile(log_mode)
        log_schreiben("==============================================", log_mode=log_mode)
        log_schreiben(f"Run- Informationen", log_mode=log_mode)
        log_schreiben("----------------------------------------------", log_mode=log_mode)
        log_schreiben(f"{'Letzter Durchlauf':<22} | {'ordnungsgemäß beendet. Fahre mit neuem Ordner fort:'}", log_mode=log_mode)
        log_schreiben(f"{'Alter Ordner':<22} | {ordner_from_config}", log_mode=log_mode)
        log_schreiben(f"{'Neuer Ordner':<22} | {ordner}", log_mode=log_mode)
    
    display_text_and_image("Wel-","come", "", "/home/Ento/LepmonOS/startsequenz/Logo_4_9.png",4)   
    if control_bit:
        print("letzer Fang nicht ordnungsgemäß beendet, benutze alten Ordner")
        write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "current_folder", ordner_path)
        
        initialisiere_logfile(log_mode)
        log_schreiben("#######################################################################################", log_mode=log_mode)
        log_schreiben("### Letzter Durchlauf nicht ordnungsgemäß beendet. Fahre mit dem alten Ordner fort ###", log_mode=log_mode)
        log_schreiben("#######################################################################################", log_mode=log_mode)
        log_schreiben("==============================================", log_mode=log_mode)
        log_schreiben(f"Run- Informationen", log_mode=log_mode)
        log_schreiben("----------------------------------------------", log_mode=log_mode)
        log_schreiben(f"{'Letzter Durchlauf':<22} | {'nicht ordnungsgemäß beendet. Fahre mit dem alten Ordner fort:'}", log_mode=log_mode)
        log_schreiben(f"{'Alter Ordner':<22} | {ordner_from_config}", log_mode=log_mode)
        log_schreiben(f"{'Neuer Ordner':<22} | {ordner_path}", log_mode=log_mode)

        
    
    display_text_and_image("Wel-","come", "", "/home/Ento/LepmonOS/startsequenz/Logo_5_9.png",1)

    log_schreiben("==============================================", log_mode=log_mode)
    log_schreiben(f"Gerätedaten", log_mode=log_mode)
    log_schreiben("----------------------------------------------", log_mode=log_mode)
    log_schreiben(f"{'ARNI SN Nummer':<22} | {sn}", log_mode=log_mode)
    log_schreiben(f"{'ARNI Generation':<22} | {hardware}", log_mode=log_mode)
    log_schreiben(f"{'verbaute Kamera':<22} | {get_device_info('camera')}", log_mode=log_mode)
    log_schreiben(f"{'verbauter Sensor':<22} | {get_device_info('sensor')}", log_mode=log_mode)
    log_schreiben(f"{'Auflösung (LxB)':<22} | {get_device_info('length')} x {get_device_info('height')}", log_mode=log_mode)
    if get_device_info('camera') == "AV__Alvium_1800_U-2050":
        log_schreiben(f"{'Red Balance':<22} | {get_value_from_section('/home/Ento/LepmonOS/Lepmon_config.json', 'AV__Alvium_1800_U-2050', 'balance_ratio_red'):.6f}", log_mode=log_mode)
        log_schreiben(f"{'Blue Balance':<22} | {get_value_from_section('/home/Ento/LepmonOS/Lepmon_config.json', 'AV__Alvium_1800_U-2050', 'balance_ratio_blue'):.6f}", log_mode=log_mode)
    if device_run is not None:
        log_schreiben(f"{'ARNI run':<22} | {sn}__{device_run}", log_mode=log_mode)
    Version = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "software", "version")
    log_schreiben(f"{'Firmware':<22} | {Version} vom {date}", log_mode=log_mode)
    log_schreiben("==============================================", log_mode=log_mode)

    if sn_trigger:
        log_schreiben("Manuelle SN Eingabe durch User erzwungen.", log_mode=log_mode)
        log_schreiben(f"Manuell gesetzte SN: {sn_manual}, Gen: {gen_manual}", log_mode=log_mode)

    
    display_text_and_image("Wel-","come", "", "/home/Ento/LepmonOS/startsequenz/Logo_6_9.png",1)  
    try: 
        power_on, power_off = get_times_power()
        set_alarm(power_on, power_off, log_mode)
        send_lora(f"Zeit für Power on mit Attiny:  {power_on}\nZeit für Power off mit Attiny: {power_off}")
    except Exception as e:
        log_schreiben(f"Fehler beim Berechnen der Zeiten für Power Management: {e}", log_mode=log_mode)
        now = datetime.now()
        now_str = now.strftime('%Y-%m-%d %H:%M:%S')
        power_on = now_str
        power_off = (now + timedelta(hours=12)).strftime('%Y-%m-%d %H:%M:%S')
        log_schreiben(f"Setze Zeiten für Power Management, basierend auf aktueler Zeit, auf: Power on: {power_on}; Power off: {power_off}", log_mode=log_mode)

    display_text_and_image("Bien-","venido","", "/home/Ento/LepmonOS/startsequenz/Logo_7_9.png",1)
    try:
        sunset, sunrise, Zeitzone = get_sun()
        send_lora(f"Zeiten für Power Management\nSonnenuntergang: {sunset.strftime('%H:%M:%S')}\nSonnenaufgang: {sunrise.strftime('%H:%M:%S')}")
    except Exception as e:
        log_schreiben(f"Fehler beim Abrufen der Sonnenzeiten: {e}", log_mode=log_mode)

    display_text_and_image("Bien-","venido", "", "/home/Ento/LepmonOS/startsequenz/Logo_8_9.png",1)
    try:
        experiment_start_time, experiment_end_time, _, _ = get_experiment_times()
        minutes_after_sunset = str(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "capture_mode", "minutes_after_sunset"))
    except Exception as e:
        log_schreiben(f"Fehler beim Abrufen der Experimentzeiten: {e}", log_mode=log_mode)
        experiment_start_time, experiment_end_time, minutes_after_sunset = "---", "---", "---"
        

    log_schreiben(f"Experiment Zeiten", log_mode=log_mode)
    log_schreiben("----------------------------------------------", log_mode=log_mode)
    log_schreiben(f"{'Beginn Experiment':<22} | {power_on[:10]}", log_mode=log_mode)
    log_schreiben(f"{'Attiny on':<22} | {power_on[11:]}", log_mode=log_mode)
    log_schreiben(f"{'Start Aufnahme':<22} | {experiment_start_time}", log_mode=log_mode)
    log_schreiben(f"{'Sonnenuntergang':<22} | {sunset.strftime('%H:%M:%S')}", log_mode=log_mode)
    log_schreiben(f"{'Verzögerung Start':<22} | {minutes_after_sunset} Minuten", log_mode=log_mode)
    log_schreiben("----------------------------------------------", log_mode=log_mode)
    log_schreiben(f"{'Ende Experiment':<22} | {power_off[:10]}", log_mode=log_mode)
    log_schreiben(f"{'Ende Aufnahme':<22} | {experiment_end_time}", log_mode=log_mode)
    log_schreiben(f"{'Attiny off':<22} | {power_off[11:]}", log_mode=log_mode)
    log_schreiben(f"{'Sonnenaufgang':<22} | {sunrise.strftime('%H:%M:%S')}", log_mode=log_mode)
    log_schreiben("==============================================", log_mode=log_mode)

    try:
        estimated_start_based_on_last_run = read_fram(0x06A0,19)
        estimated_end_based_on_last_run = read_fram(0x06C0,19)
    except Exception as e:
        print(e)
    print(f"estimated_start_based_on_last_run{estimated_start_based_on_last_run}, estimated_end_based_on_last_run{estimated_end_based_on_last_run}")
    
    try:
        estimated_start_based_on_last_run = datetime.strptime(estimated_start_based_on_last_run.strip(), "%Y-%m-%d %H:%M:%S")
        estimated_end_based_on_last_run = datetime.strptime(estimated_end_based_on_last_run.strip(), "%Y-%m-%d %H:%M:%S")
        print(f"estimated_start_based_on_last_run{estimated_start_based_on_last_run}, estimated_end_based_on_last_run{estimated_end_based_on_last_run}")
    except Exception as e:
        log_schreiben(f"Fehler beim lesen der zuletzt in 'end' gespeicherten Zeiten:{e}", log_mode=log_mode)
        estimated_start_based_on_last_run = "---"
        estimated_end_based_on_last_run = "---"
        

    log_schreiben(f"Vergleiche Experiment Zeiten", log_mode=log_mode)
    log_schreiben("----------------------------------------------", log_mode=log_mode)
    log_schreiben(f"{'gespeicherter Anfang':<22} | {estimated_start_based_on_last_run}", log_mode=log_mode)
    log_schreiben(f"{'gespeichertes Ende':<22} | {estimated_end_based_on_last_run}", log_mode=log_mode)

    try: 
        power_on = datetime.strptime(power_on.strip(), "%Y-%m-%d %H:%M:%S")
        diff_start = power_on - estimated_start_based_on_last_run
        print(f"estimated_start_based_on_last_run:{estimated_start_based_on_last_run}")
        print(f"Power on:{power_on}")
        log_schreiben(f"{'Differenz Startzeiten':<22} | {diff_start}", log_mode=log_mode)
    except Exception as e:
        log_schreiben(f"Fehler im Vergleich der Startzeit aus 'end' und der tatsächlichen Startzeit:{e}", log_mode=log_mode)
        log_schreiben(f"{'Differenz Startzeiten':<22} | ---", log_mode=log_mode)
    log_schreiben("eine positive Differenz oder 0:00 ist erwartet - der im letzten Run errechnete Stratzeitpunkt liegt vor dem tatsächlichen. Kein Datenverlust ist erwartet", log_mode=log_mode)

    display_text_and_image("Bien-","venido", "", "/home/Ento/LepmonOS/startsequenz/Logo_9_9.png",1)
    try:
        store_times_power(power_on, power_off, "start_up")
        print("Start & Stop Zeiten im FRam aktualisiert")
    except Exception as e:
        print(f"Fehler beim Speichern der Zeiten: {e}")
        print("ARNI besitzt kein Power Management. Fahre fort")

    
    # Setze Alarme zurück
    reset_alarms(log_mode)
    
    write_timestamp(0x07E0)

    # Experiment für Boundingboxen mit Delay, wenn ARNI im entsprechenden Experiment eingesetzt wird
    if sn in ["SN010010", "SN010011"]:
        jetzt_local, _, _= Zeit_aktualisieren(log_mode=log_mode)
        Delay, Box_Experiment_Run, Round = get_experiment_delay(sn, jetzt_local)
        Delay_str = str(Delay).split()[-1]
        log_schreiben("==============================================", log_mode=log_mode)
        log_schreiben(f"ARNI im Experiment für Boundingboxen mit Delay eingesetzt", log_mode=log_mode)
        log_schreiben("----------------------------------------------", log_mode=log_mode)
        log_schreiben(f"{'Verzögerung':<22} | {Delay_str}", log_mode=log_mode)
        log_schreiben(f"{'Box Experiment Run':<22} | {Box_Experiment_Run}", log_mode=log_mode)
        log_schreiben(f"{'Runde':<22} | {Round}", log_mode=log_mode)
        log_schreiben("==============================================", log_mode=log_mode)
        try:
            log_schreiben(f"Start auf diesem ARNI: {experiment_start_time + Delay}", log_mode=log_mode)
        except Exception as e:
            log_schreiben(f"Fehler beim Berechnen der Startzeit mit Delay: {e}", log_mode=log_mode)


    log_schreiben("##################################", log_mode=log_mode)
    log_schreiben("##################################", log_mode=log_mode)
    log_schreiben("beende start_up", log_mode=log_mode)
    log_schreiben("##################################", log_mode=log_mode)
    log_schreiben("##################################", log_mode=log_mode)


if __name__ == "__main__":
    start_up(log_mode="log")     