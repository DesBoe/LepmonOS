from fram_operations import *

def get_hardware_version():
    """
    Gibt die Geräte-Generation zurück.
    Default: "Pro_Gen_3"
    """
    default = "Pro_Gen_3"

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
            ).strip()
        except Exception as e:
            print(f"Fehler beim Lesen der ARNI_Gen aus der JSON: {e}")
            ARNI_Gen = default

    return ARNI_Gen

if __name__ == "__main__":
    print(f"Dieser ARNI ist ein {get_hardware_version()} Modell")

