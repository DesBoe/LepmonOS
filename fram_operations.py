from json_read_write import *
try:
    from fram_direct import *
except Exception as e:
     print(f"Fehler beim Importieren von fram_direct: {e}")  

from hardware import *
     
     
def ram_counter(ramadresse):
    """
    Liest eine 4-Byte-Zahl aus dem FRAM an der angegebenen Adresse, erhöht sie um 1 und schreibt sie zurück.
    Gibt den Wert als vierstelligen String mit führenden Nullen aus.
    """
    try:
        counter_bytes = read_fram_bytes(ramadresse, 4)
        # Falls leer, initialisiere mit 0
        if not counter_bytes or not isinstance(counter_bytes, (bytes, bytearray)):
            counter_int = 0
        else:
            counter_int = int.from_bytes(counter_bytes, byteorder='big')
        counter_int += 1
        write_fram_bytes(ramadresse, counter_int.to_bytes(4, byteorder='big'))
        counter_str = f"{counter_int:04d}"
        #print(f"Counter an Adresse {hex(ramadresse)} als String: {counter_str}")
        return counter_str
    except Exception as e:
        print(f"Counter an Adresse {hex(ramadresse)} konnte nicht erhöht werden: {e}")
        return None
    
def delete_error_code():
    """
    Funktion um den Error Code zu löschen
    """
    try:
        write_fram_bytes(0x1010, (0).to_bytes(4, byteorder='big'))
        print("Fehlercode in FRAM auf 0 gesetzt")
    except Exception as e:
        print("Fehlercode in FRAM nicht gelöscht")
        
    try:
        write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "capture_mode", "error_code", "0")
        print("Fehlercode in config auf 0 gesetzt")
    except Exception as e:
        print("Fehlercode in config nicht gelöscht")
        pass
    
def store_times_power(power_on, power_off):
    """
    Funktion um die Zeiten für den Power on und Power off in den FRAM zu speichern
    """
    try:
        write_fram(0x0010, str(power_on))
        write_fram(0x0040, str(power_off))
        time.sleep(1)
        print("start time and stop time written to FRAM")

    except Exception as e:
        time.sleep(5)
        
def check_version():
    """
    Funktion um die Version der Software zu überprüfen
    """
    Version_json = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "software", "version")
    date_json = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "software", "date")
    print(f"Software- Version: {Version_json} vom {date_json}")
    try:
        Version_fram = read_fram(0x0130, 8)
        date_fram = read_fram(0x0140, 8)
    except Exception as e:
        print(f"Fehler beim Lesen der Version/Daten aus dem FRAM: {e}")
        Version_fram = None
        date_fram = None
        return

    if Version_fram is not None and Version_json != Version_fram:
        write_fram(0x0130, Version_json)
        print("Version in FRAM aktualisiert")
    if Version_fram is not None and date_fram != date_json:
        write_fram(0x0140, date_json)
        print("Datum in FRAM aktualisiert")
        
def check_Lepmon_code():
    try:
        Country_Fram_alt = read_fram(0x04A0, 32).replace('\x00', '').strip() or ""
        Province_Fram_alt = read_fram(0x04D0, 16).replace('\x00', '').strip() or ""
        Kreis_Fram_alt = read_fram(0x04F0, 16).replace('\x00', '').strip() or ""
        print(f"Lepmoncode im Fram: {Country_Fram_alt}-{Province_Fram_alt}-{Kreis_Fram_alt}")
    except Exception as e:
        print(f"Fehler beim Lesen des Lepmon Codes aus dem FRAM: {e}")
        Country_Fram_alt = None
        Province_Fram_alt = None
        Kreis_Fram_alt = None

    if not Country_Fram_alt or not Province_Fram_alt or not Kreis_Fram_alt:
        print("Lepmon Code im FRAM nicht gefunden")
        return

    Country_json_alt = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "locality", "country")
    Province_json_alt = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "locality", "province")
    Kreis_json_alt = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "locality", "Kreis")

    if Country_Fram_alt != Country_json_alt and Country_Fram_alt is not None:
        write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "locality", "country", Country_Fram_alt)
        print("Land in Lepmon_config Datei aktualisiert")
    if Province_Fram_alt != Province_json_alt and Province_Fram_alt is not None:
        write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "locality", "province", Province_Fram_alt)
        print("Provinz in Lepmon_config Datei aktualisiert")
    if Kreis_Fram_alt != Kreis_json_alt and Kreis_Fram_alt is not None:
        write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "locality", "Kreis", Kreis_Fram_alt)
        print("Stadt in Lepmon_config Datei aktualisiert")
   
        
if __name__ == "__main__":
    print("Funktionen zum Lesen und Ändern einzelner Ram Einträge")
    check_Lepmon_code()