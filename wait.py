from OLED_panel import *
import time
from datetime import datetime
from times import *
from logging_utils import log_schreiben
from language import get_language
from usb_controller import reset_all_usb_ports
from runtime import write_timestamp
from hardware import get_hardware_version
from json_read_write import get_value_from_section
from end import trap_shutdown
from GPIO_Setup import turn_on_led, turn_off_led
from Experiments import apply_delay

HARDWARE_VERSION = get_hardware_version()
power = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","powermode","supply")



def wait(log_mode, skip = False):
    lang = get_language()
    write_timestamp(0x07E0)
    
    experiment_start_time, experiment_end_time,time_buffer, minutes_to_sunrise = get_experiment_times(log_mode)
    _, lokale_Zeit, _ = Zeit_aktualisieren(log_mode)
    experiment_start_time = datetime.strptime(experiment_start_time, "%H:%M:%S")
    experiment_end_time = datetime.strptime(experiment_end_time, "%H:%M:%S")
    lokale_Zeit = datetime.strptime(lokale_Zeit, "%H:%M:%S")
    heater = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","powermode","Heizung")
    waiter = True
    
    print(f"minutes_to_sunset:  {time_buffer}")
    print(f"minutes_to_sunrise: {minutes_to_sunrise}")

    print(f"experiment_start_time: {experiment_start_time.strftime('%H:%M:%S')}")
    print(f"jetzt :                {lokale_Zeit.strftime('%H:%M:%S')}")
    print(f"experiment_end_time:   {experiment_end_time.strftime('%H:%M:%S')}")
    

    # Experiment für Boundingboxen mit Delay, wenn ARNI im entsprechenden Experiment eingesetzt wird
    experiment_start_time = apply_delay(experiment_start_time, log_mode)


    #if not (experiment_end_time > lokale_Zeit >= experiment_start_time):
    if experiment_end_time >= lokale_Zeit or experiment_start_time <= lokale_Zeit:
        log_schreiben(f"{'Warte auf Beginn':<22} | nein, starte Schleife", log_mode=log_mode)
        log_schreiben("==============================================", log_mode=log_mode)

        return heater, waiter

    
    else:
        countdown = (experiment_start_time - lokale_Zeit).total_seconds()
        countdown_time = experiment_start_time - lokale_Zeit
        log_schreiben(f"{'Warte auf Beginn':<22} | ja, in {countdown_time}", log_mode=log_mode)
        log_schreiben("==============================================", log_mode=log_mode)

        if skip:
            log_schreiben("Warten übersprungen", log_mode=log_mode)
            log_schreiben("==============================================", log_mode=log_mode)
            return heater, waiter
        '''
        for _ in range(30):
            if countdown <= 0:
                break
            turn_on_led("blau")
            hours, remainder = divmod(int(countdown), 3600)  # Stunden berechnen
            minutes, seconds = divmod(remainder, 60)  # Minuten und Sekunden berechnen
            show_message("wait_1", lang=lang, hours = f"{hours:02d}", minutes = f"{minutes:02d}", seconds = f"{seconds:02d}")
            countdown -= 1
            turn_off_led("blau")
            hours, remainder = divmod(int(countdown), 3600)  # Stunden berechnen
            minutes, seconds = divmod(remainder, 60)  # Minuten und Sekunden berechnen
            show_message("wait_1", lang=lang, hours = f"{hours:02d}", minutes = f"{minutes:02d}", seconds = f"{seconds:02d}")
            countdown -= 1
        '''

        turn_off_led("blau)")
        show_message("blank", lang= lang)
        
        if  countdown > 60: 
            countdown -= 60 
            
        print(f"Countdown bis zum Start des Experiments: {countdown} Sekunden")
        print(HARDWARE_VERSION)
        print(power)
        print(countdown > 15*60)
        if countdown > 0:

            # Solarbetriebene ARNI CSS_Gen_1 und Pro_Gen_4 sollen bei countdown über 15 Minuten in den Sleep-Modus gehen, um Energie zu sparen.
            if HARDWARE_VERSION in ["CSS_Gen_1", "Pro_Gen_4"] and countdown > 15*60 and power == "Solar":
                log_schreiben(f"Coundown > 15 Minuten, ARNI fährt mit ATTINY Kontrolle herunter, um Strom zu sparen", log_mode=log_mode)
                try:
                    trap_shutdown(i=60, log_mode=log_mode, execution="full", anzeige = "SolareingabeHMI15Min")
                except Exception as e:
                    try:
                        log_schreiben(f"Fehler im Shutdown: {e}", "log")
                    except Exception as log_error:
                        print(f"Fehler im Shutdown: {e}", "log")

            time.sleep(countdown)
            write_timestamp(0x07E0)
            reset_all_usb_ports(log_mode=log_mode)
            time.sleep(5)




        return heater, waiter  
    
if __name__ == "__main__":
    wait(log_mode="manual", skip=False)