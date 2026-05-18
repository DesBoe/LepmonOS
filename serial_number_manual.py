from GPIO_Setup import *
from OLED_panel import *
from json_read_write import *
from fram_direct import *
import time
from service import *

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

            try:
                write_fram_bytes(0x0110, b'\x00' * 16)
                print("SN in FRAM gelöscht")
                write_fram(0x0110, sn.ljust(16))
                print(f"SN in den RAM geschrieben: {sn}")
                write_fram_bytes(0x0130, b'\x00' * 16)
                print("Gen in FRAM gelöscht")
                write_fram(0x0130, gen.ljust(16))
                print(f"Gen in den RAM geschrieben: {gen}")
                fram_success = True



            except Exception as e:
                print(f"Fehler beim Schreiben der SN und Gen in den RAM: {e}")
                fram_success = False
                

            print(f"Manuell gesetzte SN: {sn}, Gen: {gen}")
            turn_off_led("blau")
            return sn, gen, fram_success
    
def trigger_manual_sn(log_mode):
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
    sn_trigger, forced_by_user = trigger_manual_sn()
    if sn_trigger:
        set_sn_manually()