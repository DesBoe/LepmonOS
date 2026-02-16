from fram_operations import *
from fram_direct import *
from json_read_write import *

geraete_bibliothek = {
    "Pro_Gen_1": {
        "camera": "AV__Alvium_1800_U-2050",
        "sensor": "imx183",
        "length": 5496,
        "height": 3672
    },
    "Pro_Gen_2": {
        "camera": "AV__Alvium_1800_U-2050",
        "sensor": "imx183",
        "length": 5496,
        "height": 3672
    },
    "Pro_Gen_3": {
        "camera": "AV__Alvium_1800_U-2050",
        "sensor": "imx183",
        "length": 5496,
        "height": 3672
    },
    "CSS_Gen_1": {
        "camera": "RPI_Module_3",
        "sensor": "imx708",
        "length": 4608,
        "height": 2592
    },
    "CSL_Gen_1": {
        "camera": "RPI_HQ",
        "sensor": "imx477",
        "length": 4056,
        "height": 3040
    }
}



def get_device_info(key):
    """
    :param Generation: Geräte-Generation (z.B. 'Pro_Gen_1')
    :param key: 'kamera' oder 'sensor'
    :return: Wert der jeweiligen Eigenschaft oder Fehlermeldung
    """
    ARNI_Gen = get_hardware_version()
    if ARNI_Gen in geraete_bibliothek:
        return geraete_bibliothek[ARNI_Gen].get(key, "Eigenschaft nicht gefunden")
    else:
        return "Generation nicht gefunden"





def get_hardware_version():
    """
    Gibt die Geräte-Generation zurück.
    Default: "Unknown"
    """
    default = "Unknown"

    try:
        # lesen und Null-Bytes/Leerzeichen entfernen
        ARNI_Gen = read_fram(0x0130, 16).replace("\x00", "").strip() or ""
    except Exception as e:
        print(f"Fehler beim Lesen der ARNI_Gen aus dem FRAM: {e}")
        ARNI_Gen = ""

    if not ARNI_Gen:
        try:
            ARNI_Gen = get_value_from_section(
                "/home/Ento/serial_number.json", "general", "Fallenversion"
                # please note: the file is NOT located in the LepmonOS folder but indeed in the Ento folder. A copy of the jsonfile is in the LepmonOS folder, but only for testing purposes
                # see service.py: compare_hardware_version(): information are also written in that specific json file.
            ).strip()
        except Exception as e:
            print(f"Fehler beim Lesen der ARNI_Gen aus der JSON: {e}")
            ARNI_Gen = default

    if ARNI_Gen == "unknown":
        raise ValueError("ARNI_Gen ist 'unknown'")
    else:
        return ARNI_Gen

if __name__ == "__main__":
    print(f"Dieser ARNI ist ein {get_hardware_version()} Modell")
    print(f"verbaute Kamera {get_device_info('kamera')} mit Sensor {get_device_info('sensor')}")
    print(f"Auflösung: {get_device_info('length')} x {get_device_info('height')}")
    

