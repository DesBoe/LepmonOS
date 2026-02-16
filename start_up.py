from times import get_times_power
from OLED_panel import display_text, display_text_and_image
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



def start_up(log_mode):
    dev_info()
    
    print("starte Setup")
    add_to_bootconfig("gpio=13=op,dl")
    turn_off_led("blau")
    turn_off_led("heizung")
    RPI_time(log_mode)
    
    display_text_and_image("Leitfaden","Guide","Guia","/home/Ento/LepmonOS/startsequenz/link_manual.png",0)
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
    ordner = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "current_folder")
    print(f"\nletzter verwendeter Ordner: {ordner}\n")
    if os.path.exists(os.path.join(USB_stick, ordner)) == False or ordner == "":
        control_bit = False
        print("Alter Ordner auf USB Stick nicht gefunden. Annahme, dass ein neuer USB Stick eingelegt wurde. Erstelle neuen Ordner")

    display_text_and_image("Will-","kommen", "", "/home/Ento/LepmonOS/startsequenz/Logo_3_9.png",1)
    
    if control_bit:
        print("Überprüfe ob ein Tag seit letztem Fang vergangen ist. Wenn ja, wird Kontrollbit zurückgesetzt, um neuen Ordner zu erstellen")
        control_bit = gap_day()

    if not control_bit:
        ordner = erstelle_ordner(log_mode)
        print (f"neuer Ordner: {ordner}")
    elif control_bit:
        print("letzer Fang nicht ordnungsgemäß beendet, benutze alten Ordner")
        ordner = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "current_folder")
        log_schreiben("#######################################################################################", log_mode=log_mode)
        log_schreiben("### Letzter Durchlauf nicht ordnungsgemäß beendet. Fahre mit dem alten Ordner fort ###", log_mode=log_mode)
        log_schreiben("#######################################################################################", log_mode=log_mode)
        
    display_text_and_image("Wel-","come", "", "/home/Ento/LepmonOS/startsequenz/Logo_4_9.png",1) 
    if ordner == None:
        display_text("USB Stick","nicht erkannt","neu einstecken",3)
        log_schreiben("##################################", log_mode=log_mode)
        log_schreiben("### SELBSTINDUZIERTER SHUTDOWN ###", log_mode=log_mode)
        log_schreiben("##################################", log_mode=log_mode)
        trap_shutdown(log_mode,10)
        return
         
    initialisiere_logfile(log_mode)
    
    display_text_and_image("Wel-","come", "", "/home/Ento/LepmonOS/startsequenz/Logo_5_9.png",1)
    log_schreiben(f"ARNI SN Nummer:   {sn}", log_mode=log_mode)
    log_schreiben(f"ARNI Generation:  {hardware}", log_mode=log_mode)
    log_schreiben(f"verbaute Kamera:  {get_device_info('camera')}",log_mode=log_mode)
    log_schreiben(f"verbauter Sensor: {get_device_info('sensor')}",log_mode=log_mode)
    log_schreiben(f"Auflösung (LxB):  {get_device_info('length')} x {get_device_info('height')}",log_mode=log_mode)


    if device_run is not None:
        log_schreiben(f"ARNI run:         {sn}__{device_run}", log_mode=log_mode)
    
    Version = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "software", "version")
    log_schreiben(f"Firmware:         {Version} vom {date}", log_mode=log_mode)
    
    display_text_and_image("Wel-","come", "", "/home/Ento/LepmonOS/startsequenz/Logo_6_9.png",1)   
    power_on, power_off = get_times_power()
    set_alarm(power_on, power_off, log_mode)
    send_lora(f"Zeit für Power on mit Attiny:  {power_on}\nZeit für Power off mit Attiny: {power_off}")
    

    display_text_and_image("Bien-","venido","", "/home/Ento/LepmonOS/startsequenz/Logo_7_9.png",1)
    sunset, sunrise, Zeitzone = get_sun()
    send_lora(f"Zeiten für Power Management\nSonnenuntergang: {sunset.strftime('%H:%M:%S')}\nSonnenaufgang: {sunrise.strftime('%H:%M:%S')}")

    display_text_and_image("Bien-","venido", "", "/home/Ento/LepmonOS/startsequenz/Logo_8_9.png",1)
    experiment_start_time, experiment_end_time, _, _ = get_experiment_times()
  
    log_schreiben("------------------", log_mode=log_mode)
    log_schreiben(f"Beginn Experiment: {power_on[:10]}", log_mode=log_mode)
    log_schreiben(f"        Attiny on:   {power_on[11:]}", log_mode=log_mode)
    log_schreiben(f"   Start Aufnahme:   {experiment_start_time}", log_mode=log_mode)
    log_schreiben(f"  Sonnenuntergang:   {sunset.strftime('%H:%M:%S')}", log_mode=log_mode)
    
    log_schreiben(f"Ende Experiment:   {power_off[:10]}", log_mode=log_mode)
    log_schreiben(f"  Ende Aufnahme:     {experiment_end_time}", log_mode=log_mode)
    log_schreiben(f"     Attiny off:     {power_off[11:]}", log_mode=log_mode)
    log_schreiben(f"  Sonnenaufgang:     {sunrise.strftime('%H:%M:%S')}", log_mode=log_mode)
    log_schreiben("------------------", log_mode=log_mode)
    
    
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