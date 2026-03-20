from GPIO_Setup import *
from OLED_panel import *
from json_read_write import *
from fram_direct import check_fram_present
import time

sn_list= [
    ("SN010001", "Pro_Gen_1"),
    ("SN010003", "Pro_Gen_1"),
    ("SN010004", "Pro_Gen_2"),
    ("SN010005", "Pro_Gen_1"),
    ("SN010006", "Pro_Gen_1"),
    ("SN010007", "Pro_Gen_2"),
    ("SN010008", "Pro_Gen_1"),
    ("SN010009", "Pro_Gen_2"),
    ("SN010010", "Pro_Gen_2"),
    ("SN010011", "Pro_Gen_2")
]
for i in range(12, 91):
    sn = f"SN01{str(i).zfill(4)}"
    sn_list.append((sn, "Pro_Gen_3"))

def set_sn_manually():
    turn_on_led("blau")
    index = 0
    while True:
        if button_pressed("oben"):
            index = (index - 1) % len(sn_list)
        if button_pressed("unten"):
            index = (index + 1) % len(sn_list)
        sn, gen = sn_list[index]
        display_text_with_arrows(line1 = "Please select:", line2 = sn, line3 = gen, x_position=None)

        if button_pressed("rechts") or button_pressed("enter"):

            write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "ARNI_Gen", gen)
            write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "serielnumber", sn)

            print(f"Manuell gesetzte SN: {sn}, Gen: {gen}")
            turn_off_led("blau")
            return sn, gen
    
def trigger_manual_sn():
    sn_json = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","general","serielnumber")
    Gen_json = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","general","ARNI_Gen")
    Ram = check_fram_present()
    forced_by_user = False
    sn_trigger = False
    print(f"SN in JSON: {sn_json}, Gen in JSON: {Gen_json}, RAM vorhanden: {Ram}")

    reset_time_out = time.time() + 4

    print("user hat 4 Sekunden Zeit, um die SN neu zu setzen auf ARNI Gen 1 und 2")
    while time.time() < reset_time_out:
        if not Ram and button_pressed("enter") or button_pressed("rechts"):
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
    sn_trigger, forced_by_user = trigger_manual_sn()
    if sn_trigger:
        set_sn_manually()