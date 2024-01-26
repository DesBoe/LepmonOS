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

def get_generation_by_serial(serial_number):
    """
    Gibt die Generation für eine gegebene Seriennummer zurück.
    """
    sn_list = dict(get_serial_list())
    return sn_list.get(serial_number, "Seriennummer nicht gefunden")
    

if __name__ == "__main__":
    sn_list = get_serial_list()
    print(sn_list)
    print(get_generation_by_serial("SN010005"))