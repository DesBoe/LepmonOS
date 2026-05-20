from fram_operations import *
from fram_direct import *
from json_read_write import *
from serial_number_manual  import *

geraete_bibliothek = {
    "Pro_Gen_1": {
        "camera": "AV__Alvium_1800_U-2050",
        "sensor": "imx183",
        "length": 5496,
        "height": 3672,
        "Schirmbreite": 360,
        "Schirmhöhe": 240,
        "effective_resolution": 16,
        "distance": 680
    },
    "Pro_Gen_2": {
        "camera": "AV__Alvium_1800_U-2050",
        "sensor": "imx183",
        "length": 5496,
        "height": 3672,
        "Schirmbreite": 360,
        "Schirmhöhe": 240,
        "effective_resolution": 16,
        "distance": 680
    },
    "Pro_Gen_3": {
        "camera": "AV__Alvium_1800_U-2050",
        "sensor": "imx183",
        "length": 5496,
        "height": 3672,
        "Schirmbreite": 360,
        "Schirmhöhe": 240,
        "effective_resolution": 16,
        "distance": 680
    },
    "Pro_Gen_4": {
        "camera": "AV__Alvium_1800_U-2050",
        "sensor": "imx183",
        "length": 5496,
        "height": 3672,
        "Schirmbreite": 360,
        "Schirmhöhe": 240,
        "effective_resolution": 16,
        "distance": 680
    },
    "CSS_Gen_1": {
        "camera": "RPI_Module_3",
        "sensor": "imx708",
        "length": 4608,
        "height": 2592,
        "Schirmbreite": 265,
        "Schirmhöhe": 150,
        "effective_resolution": 16,
        "distance": 210
    },
    "CSL_Gen_1": {
        "camera": "RPI_HQ",
        "sensor": "imx477",
        "length": 4056,
        "height": 3040,
        "Schirmbreite": 000,
        "Schirmhöhe": 000,
        "effective_resolution": 000,
        "distance": 000
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
        if ARNI_Gen not in geraete_bibliothek:
            print(f"Fehler:ARNI_Gen '{ARNI_Gen}' nicht in Gerätebibliothek gefunden.")
            ARNI_Gen = ""
    except Exception as e:
        print(f"Fehler beim Lesen der ARNI_Gen aus dem FRAM: {e}")
        ARNI_Gen = ""

    if not ARNI_Gen:
        try:
            ARNI_Gen = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "ARNI_Gen").strip()
            if ARNI_Gen not in geraete_bibliothek:
                print(f"Fehler:ARNI_Gen '{ARNI_Gen}' nicht in Gerätebibliothek gefunden.")
                ARNI_Gen = ""
        except Exception as e:
            print(f"Fehler beim Lesen der ARNI_Gen aus der JSON: {e}")
            ARNI_Gen = ""

    if ARNI_Gen == "":
        print(f"ARNI_Gen konnte nicht ermittelt werden. Es muss manuell eingestellt werden.")
        set_sn_manually()
    else:
        return ARNI_Gen

if __name__ == "__main__":
    print(f"Dieser ARNI ist ein {get_hardware_version()} Modell")
    print(f"verbaute Kamera {get_device_info('camera')} mit Sensor {get_device_info('sensor')}")
    print(f"Auflösung: {get_device_info('length')} x {get_device_info('height')}") 
    print(f"Schirmbreite x Höhe in mm: {get_device_info('Schirmbreite')} x {get_device_info('Schirmhöhe')}")
    print(f"Abstand zwischen Kamera und Schirm: {get_device_info('distance')} ")
    print(f"Effektive Auflösung: {get_device_info('effective_resolution')} ")
