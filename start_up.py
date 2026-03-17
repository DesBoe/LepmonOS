from times import get_times_power
from OLED_panel import *
from service import *
from logging_utils import log_schreiben
from lora import send_lora
from logging_utils import *
import time
from times import *
from json_read_write import *
from RTC_alarm import set_alarm
from fram_operations import *
from service import *
from runtime import *
from GPIO_Setup import turn_off_led
from end import trap_shutdown
from bootconfig import add_to_bootconfig
from hardware import *
import os
from serial_number_manual import *



def start_up(log_mode):
    #dev_info()
    # Update 2.3.0 muss Ram Neu Beschreiben für INFO zur Firmware.
    new_version = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "software", "version")
    new_date = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "software", "date")
    try:
        write_fram(0x0520, new_version.ljust(7)) 
        write_fram(0x0510, new_date.ljust(10))
        print(f"Firmware Version im FRAM aktualisiert:{new_version}; {new_date}")
    except Exception as e:
        pass
    
    print("starte Setup")
    #add_to_bootconfig("gpio=13=op,dl")
    turn_off_led("blau")
    turn_off_led("heizung")
    RPI_time(log_mode)


    display_image_3_2("/home/Ento/LepmonOS/startsequenz/start_K2W.png",sleeptime = 4)
    display_image_3_2("/home/Ento/LepmonOS/startsequenz/start_U2C.png",sleeptime = 0) # Logo wird für die Dauer angezeigt, in der es möglich ist, die SN manuell zu setzen.
    sn_trigger, forced_by_user = trigger_manual_sn()
    if sn_trigger:
        sn_manual, gen_manual = set_sn_manually()


    
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
        print("Überprüfe ob ein Tag seit letztem Fang vergangen ist. Wenn ja, wird Kontrollbit zurückgesetzt, um neuen Ordner zu erstellen")
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
        log_schreiben(f"{'Letzter Durchlauf':<22} | { ' ordnungsgemäß beendet. Fahre mit neuem Ordner fort:'}", log_mode=log_mode)
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
        log_schreiben(f"{'Letzter Durchlauf':<22} | { 'nicht ordnungsgemäß beendet. Fahre mit dem alten Ordner fort:'}", log_mode=log_mode)
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
    if device_run is not None:
        log_schreiben(f"{'ARNI run':<22} | {sn}__{device_run}", log_mode=log_mode)
    Version = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "software", "version")
    log_schreiben(f"{'Firmware':<22} | {Version} vom {date}", log_mode=log_mode)
    log_schreiben("==============================================", log_mode=log_mode)

    if sn_trigger:
        log_schreiben("Manuelle SN Eingabe durch User erzwungen.", log_mode=log_mode)
        log_schreiben(f"Manuell gesetzte SN: {sn_manual}, Gen: {gen_manual}", log_mode=log_mode)

    
    display_text_and_image("Wel-","come", "", "/home/Ento/LepmonOS/startsequenz/Logo_6_9.png",1)   
    power_on, power_off = get_times_power()
    set_alarm(power_on, power_off, log_mode)
    send_lora(f"Zeit für Power on mit Attiny:  {power_on}\nZeit für Power off mit Attiny: {power_off}")
    

    display_text_and_image("Bien-","venido","", "/home/Ento/LepmonOS/startsequenz/Logo_7_9.png",1)
    sunset, sunrise, Zeitzone = get_sun()
    send_lora(f"Zeiten für Power Management\nSonnenuntergang: {sunset.strftime('%H:%M:%S')}\nSonnenaufgang: {sunrise.strftime('%H:%M:%S')}")

    display_text_and_image("Bien-","venido", "", "/home/Ento/LepmonOS/startsequenz/Logo_8_9.png",1)
    experiment_start_time, experiment_end_time, _, _ = get_experiment_times()
    minutes_after_sunset = str(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "capture_mode", "minutes_after_sunset"))

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

    
    
    display_text_and_image("Bien-","venido", "", "/home/Ento/LepmonOS/startsequenz/Logo_9_9.png",1)
    try:
        store_times_power(power_on, power_off)
        print("Start & Stop Zeiten im FRam aktualisiert")
    except Exception as e:
        print(f"Fehler beim Speichern der Zeiten: {e}")
        print("ARNI besitzt kein Power Management. Fahre fort")
    
    write_timestamp(0x07E0)
        
    print("beende Setup")   

if __name__ == "__main__":
    start_up(log_mode="manual")     