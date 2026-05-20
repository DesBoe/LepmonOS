from OLED_panel import display_text_with_arrows
from GPIO_Setup import *
from json_read_write import *
from fram_direct import *

def get_serial_list():
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

    return sn_list


def set_sn_manually():
    
    sn_list = get_serial_list()
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
    

if __name__ == "__main__":
    sn_list = get_serial_list()
    print(sn_list)