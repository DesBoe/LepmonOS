from GPIO_Setup import *
from OLED_panel import *
from json_read_write import *
from fram_direct import *
import time
from service import *
from serial_list import *


    
def trigger_manual_sn(log_mode):
    sn_list = get_serial_list()
    sn_json = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","general","serielnumber")
    Gen_json = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","general","ARNI_Gen")
    _, _, _, sn_ram = get_Lepmon_code(log_mode)
    Ram = check_fram_present()
    forced_by_user = False
    sn_trigger = False
    print(f"SN in JSON: {sn_json}, Gen in JSON: {Gen_json}, RAM vorhanden: {Ram}")

    reset_time_out = time.time() + 4

    print("user hat 4 Sekunden Zeit, um die SN neu zu setzen auf ARNI Gen 1 und 2")
    while time.time() < reset_time_out:
        if ((not Ram and (button_pressed("enter") or button_pressed("rechts")))
            or (sn_ram not in sn_list and (button_pressed("enter") or button_pressed("rechts")))):
            print("Manuelle SN Eingabe durch User erzwungen.")
            forced_by_user = True
            sn_trigger = True
            time.sleep(2)
            show_message("blank", lang= "de")
            break
        time.sleep(.1)

    if not Ram and (sn_json == "" or Gen_json == ""):
        sn_trigger = True

    else:
        print(f"SN: {sn_json} und Gen: {Gen_json} Einträge bereits vorhanden. Keine Manuelle Eingabe nötig.")
    
    return sn_trigger, forced_by_user, Gen_json




if __name__ == "__main__":
    log_mode = "manual"
    sn_trigger, forced_by_user = trigger_manual_sn(log_mode)
    if sn_trigger:
        set_sn_manually()