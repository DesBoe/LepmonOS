from datetime import datetime
from json_read_write import get_value_from_section, write_value_to_section
from lora import send_lora
import time
from OLED_panel import show_message
from GPIO_Setup import turn_on_led, turn_off_led
import os
from hardware import *
import hashlib
from language import get_language

lang = get_language()


try:
    from fram_direct import *
except ImportError:
    print("FRAM module not found. Skipping FRAM related operations.")
    pass

def log_schreiben(text, log_mode):
    """
    "log" schreibt einen Eintrag in das Logfile,
    "manual" gibt den Eintrag nur auf der Konsole aus.
    """
    
    lokale_Zeit = datetime.now().strftime("%H:%M:%S")
    

    if log_mode == "manual":
        print(f"{lokale_Zeit}; {text}")
        return

    if log_mode == "log":
        log_dateipfad = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","general","current_log") 
        if not os.path.exists(log_dateipfad):
            print(f"WARNUNG: Logfile muss neu erstellt werden, weil Pfad nicht existiert: {log_dateipfad}")
            time.sleep(5)
            from service import initialisiere_logfile
            initialisiere_logfile(log_mode)

        for attempt in range(30):
            try:
                with open(log_dateipfad, 'a') as f:
                    f.write(f"{lokale_Zeit}; {text}\n")
                    checklist(log_dateipfad, log_mode, algorithm="md5")
                return
            except Exception as e:
                if attempt ==3:
                    print(f"Versuche log zu schreiben. Versuch Nr. {attempt} -- Fehler: {e}")
                    try:
                        Errorcode = int.from_bytes(read_fram_bytes(0x0810, 4), byteorder='big')
                        time.sleep(.5)
                    except Exception as e:  
                        try:
                            Errorcode = int(get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "capture_mode", "error_code"))
                        except Exception:
                            Errorcode = 0
                    print(f"Fehlercode: {Errorcode}")
                    if Errorcode != 3:
                        error_message(10, e, log_mode)
                if 4 <= attempt < 29:
                    print(f"Versuche log zu schreiben. Versuch Nr. {attempt} -- Fehler: {e}")
                    turn_on_led("blau")
                    turn_on_led("gelb")
                    print("Warte für LEDs")
                    time.sleep(2)
                    turn_off_led("blau")
                    turn_off_led("gelb")
                if attempt == 29:
                    print("Logeintrag nach 30 Versuchen gescheitert. Vermutlich liegt ein Problem in der Verbindung zum USB stick vor. Starte neu") 
                    from end import trap_shutdown
                    trap_shutdown(log_mode, 10) 
                    break

Logging_MESSAGES = {
    1: ("Fehler beim Abrufen des Frames - Bild nicht gespeichert. Prüfe Kamera-USB Kabel", "Fehler 1"),
    2: ("kamera wiederholt nicht initialisiert. ARNI startet neu zur Fehlerbehandlung", "Fehler 2"),
    3: ("USB Stick nicht gefunden. Anschluss prüfen", "Fehler 3"),
    4: ("Fehler in der Verbindung zum Lichtsensor. Wert des Umgebungslichtes auf Schwellenwert gesetzt: 90", "Fehler 4"),
    5: ("Fehler in der Verbindung zum Umweltsensor", "Fehler 5"),
    6: ("Fehler in der Verbindung zum Innen-Temperatursensor", "Fehler 6"),
    7: ("Fehler in der Verbindung zum Stromsensor. Kein Monitoring der LED möglich", "Fehler 7"),
    8: ("Fehler in der Verbindung zur HardwareUhr. Prüfe Kabelverbindung, Batterie oder eingegebenen Zeitstring", "Fehler 8"),
    9: ("Fehler in der Kommunikation zwischen Raspberry Pi und Fram Modul", "Fehler 9"),
    10: ("Logging File nicht gefunden und Eintrag nicht erstellt", "Fehler 10"),
    11: ("Checksumme für Bild,logfile oder Metadatentabelle nicht ermittelt", "Fehler 11"),
    12: ("Beleuchtungs LED ist verdunkelt. Leistung (in W)", "Fehler 12"),
    13: ("Aktuelle Daten konnten nicht in Metadaten Tabelle geschrieben werden", "Fehler 13"),
    14: ("Foto hat Sanity Check nicht bestanden und wurde neu aufgenommen", "Fehler 14"),
    15: ("Pakete installation nach Update fehlgeschlagen", "Fehler 15"),
    16: ("Land/Region konnte nicht bestimmt werden", "Fehler 16"),
}

ERROR_COUNTER_ADDR = {
    1: 0x0840,
    2: 0x0860,
    3: 0x0880,
    4: 0x08A0,
    5: 0x08C0,
    6: 0x08E0,
    7: 0x0900,
    8: 0x0920,
    9: 0x0940,
    10: 0x0960,
    11: 0x0980,
    12: 0x09A0,
    13: 0x09C0,
    14: 0x09E0,
    15: 0x0A00,
    16: 0x0A20,
}

def increment_error_counter(error_number):
    addr = ERROR_COUNTER_ADDR.get(error_number)
    if addr is None:
        return
    try:
        counter_bytes = read_fram_bytes(addr, 4)
        if not counter_bytes or not isinstance(counter_bytes, (bytes, bytearray)):
            counter = 1
        else:
            counter = int.from_bytes(counter_bytes, byteorder='big') + 1
        write_fram_bytes(addr, counter.to_bytes(4, byteorder='big'))
    except Exception as e:
        print(f"Fehler beim Zählen des Fehlers {error_number}: {e}")

def print_error_table():
    print("\nAktuelle Fehlerhäufigkeiten:")
    print(f"{'Fehler':<8} | {'Adresse':<8} | {'Anzahl':<8}")
    print("-" * 32)
    for err_num, addr in ERROR_COUNTER_ADDR.items():
        try:
            counter_bytes = read_fram_bytes(addr, 4)
            if not counter_bytes or not isinstance(counter_bytes, (bytes, bytearray)):
                count = 0
            else:
                count = int.from_bytes(counter_bytes, byteorder='big')
        except Exception as e:
            count = "?"
        print(f"{err_num:<8} | {hex(addr):<8} | {count:<8}")
        

# Separate function for Logging_MESSAGES
def get_log_message(error_number):
    return Logging_MESSAGES.get(error_number, ("Unbekannter Fehler", f"Fehler {error_number}"))

def error_message(error_number, error_details, log_mode):
    """
    Zeigt die Fehlermeldung auf dem Display an, loggt sie und sendet sie per LoRa.
    :param error_number: Fehlernummer (int)
    """
    if error_number != 9 and get_hardware_version() != "Pro_Gen_1" or error_number != 9 and get_hardware_version() != "Pro_Gen_2":
        turn_on_led("rot")  
        logging_text, _ = get_log_message(error_number)  
        try:
            show_message(f"err_{error_number}",lang = lang)
        except Exception as e:
            print(f"Fehler in der Anzeige {e}")

        if not error_number == 10:
            try:
                log_schreiben(f"Fehler {error_number}: {logging_text}: {error_details}", log_mode=log_mode)
            except Exception as e:
                pass   
        
        try:
            send_lora(f"Fehler {error_number}: {logging_text} {error_details}") 
        except Exception as e:
            pass
        
        try:
            write_fram_bytes(0x0810, error_number.to_bytes(4, byteorder='big'))
        except Exception as e:  
            print(f"Fehler beim Schreiben in den FRAM: {e}")
            pass
        
        write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "capture_mode", "error_code", error_number)
        
        try:
            increment_error_counter(error_number)
            print_error_table()
        except Exception as e:
            print("Ram nicht verfügbar. Fehlerzähler nicht erhöht:", e)  
              
        time.sleep(.5)
        turn_off_led("rot")



def checksum(dateipfad, log_mode, algorithm="md5"):
  try:
    if not os.path.exists(dateipfad): 
      raise FileNotFoundError(f"Datei nicht gefunden: {dateipfad}")

    hash_func = hashlib.new(algorithm) 
    
    with open(dateipfad, "rb") as file:
      while chunk := file.read(8192):
        hash_func.update(chunk)
 
    checksum = hash_func.hexdigest()
  
    dir_name = os.path.dirname(dateipfad)
    base_name = os.path.basename(dateipfad)
    checksum_file_name = f"{base_name}.{algorithm}"
    checksum_dateipfad = os.path.join(dir_name, checksum_file_name)
  
    with open(checksum_dateipfad, "w") as checksum_file:
      checksum_file.write(checksum)
  
  except Exception as e:
     error_message(11,e, log_mode)
     print(f"Fehler beim Berechnen der Prüfsumme: {e}")
     pass
 
def checklist(dateipfad, log_mode, algorithm="md5"):
    try:
        log_path = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "current_log")
        base, _ = os.path.splitext(log_path)
        checklist_path = f"{base}_MD5.txt"
        if os.path.abspath(dateipfad) == os.path.abspath(checklist_path):
            return

        if not os.path.exists(dateipfad):
            raise FileNotFoundError(f"Datei nicht gefunden: {dateipfad}")

        # Checksumme berechnen
        hash_func = hashlib.new(algorithm)
        with open(dateipfad, "rb") as file:
            while chunk := file.read(8192):
                hash_func.update(chunk)
        checksum_value = hash_func.hexdigest()
        base_name = os.path.basename(dateipfad)
        entry = f"{checksum_value} {base_name}\n"

        # Prüfe, ob checklist.txt existiert, sonst anlegen
        if not os.path.exists(checklist_path):
            with open(checklist_path, "w") as f:
                f.write(entry)
            return

        # Für csv/log: Eintrag ersetzen, für Bilder: ergänzen
        update_entry = base_name.endswith(".csv") or base_name.endswith(".log")
        lines = []
        found = False

        with open(checklist_path, "r") as f:
            lines = f.readlines()

        if update_entry:
            for i, line in enumerate(lines):
                if line.strip().endswith(base_name):
                    lines[i] = entry
                    found = True
                    break
            if not found:
                lines.append(entry)
        else:
            lines.append(entry)

        with open(checklist_path, "w") as f:
            f.writelines(lines)

    except Exception as e:
        error_message(11, e, log_mode)
        print(f"Fehler beim Berechnen der Checkliste: {e}")
        pass 
 
if __name__ == "__main__":
    print("logging Werkzeuge")
    
    print_error_table()