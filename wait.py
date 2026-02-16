from OLED_panel import *
import time
from datetime import datetime
from times import *
from logging_utils import log_schreiben
from language import get_language
from usb_controller import reset_all_usb_ports
from runtime import write_timestamp



def wait(log_mode):
    lang = get_language()
    write_timestamp(0x07E0)
    
    experiment_start_time, experiment_end_time,time_buffer, minutes_to_sunrise = get_experiment_times()
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
    
    #if not (experiment_end_time > lokale_Zeit >= experiment_start_time):
    if experiment_end_time >= lokale_Zeit or experiment_start_time <= lokale_Zeit:
        log_schreiben("Aktuelle Zeit liegt nach geplantem Nachtbeginn. Starte Schleife", log_mode=log_mode)
        return heater, waiter

    else:
        countdown = (experiment_start_time - lokale_Zeit).total_seconds()
        countdown_time = experiment_start_time - lokale_Zeit
        log_schreiben(f"warte bis Nachtbeginn: {countdown_time}", log_mode=log_mode)
        
        for _ in range(60):
            hours, remainder = divmod(int(countdown), 3600)  # Stunden berechnen
            minutes, seconds = divmod(remainder, 60)  # Minuten und Sekunden berechnen
            show_message("wait_1", lang=lang, hours = f"{hours:02d}", minutes = f"{minutes:02d}", seconds = f"{seconds:02d}")
            countdown -= 1
            if countdown == 0:
                break

        show_message("blank", lang= lang)
        
        if  countdown > 60: 
            countdown -= 60 
            

        if countdown > 0:
            time.sleep(countdown)
            write_timestamp(0x07E0)
            reset_all_usb_ports(log_mode=log_mode)
            time.sleep(5)
        return heater, waiter  
    
if __name__ == "__main__":
    wait(log_mode="manual")