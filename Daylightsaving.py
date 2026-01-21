
from times import *
from logging_utils import *
from datetime import timedelta, datetime
from fram_operations import *
from GPIO_Setup import *
from RTC_new_time import set_hwc


def daylight_saving_check(log_mode):
    latitude, longitude, _, _, _, _ = get_coordinates()
    jetzt_local,_ ,_ = Zeit_aktualisieren(log_mode)
    Zeitzone = berechne_zeitzone(latitude, longitude)
    Zeitumstellung, Änderung = zeitumstellung_info(jetzt_local,Zeitzone)

    try:
        if Zeitumstellung and read_fram_bytes(0x048F, 1) == b'\x00':
            print("Stelle UhrZeit um")
            log_schreiben("------------------", log_mode=log_mode)
            log_schreiben("Stelle UhrZeit um", log_mode=log_mode)
            if isinstance(jetzt_local, str):
                jetzt_local = datetime.strptime(jetzt_local, "%Y-%m-%d %H:%M:%S")
            neue_zeit = jetzt_local + timedelta(hours=Änderung)
            log_schreiben(f"neue Zeit: {neue_zeit} - Uhr wird um {Änderung} Stunde(n) geändert", log_mode=log_mode)
            try:
                #set_hwc("daylight_saving", [neue_zeit.year, neue_zeit.month, neue_zeit.day, neue_zeit.hour, neue_zeit.minute, neue_zeit.second])
                set_hwc("daylight_saving", log_mode,neue_zeit.strftime("%Y%m%d%H%M%S"))
                print("Zeitumstellung erfolgreich durchgeführt")
            except Exception as e:
                log_schreiben(f"Fehler beim Setzen der neuen Zeit für die Zeitumstellung: {e}", log_mode=log_mode)
            time.sleep(2)
            write_fram_bytes(0x048F, b'\x01')
            print("Kontrollbit für Zeitumstellung gesetzt")
        
        elif not Zeitumstellung and read_fram_bytes(0x048F, 1) == b'\x01':
            write_fram_bytes(0x048F, b'\x00')
            log_schreiben("------------------", log_mode=log_mode)
            log_schreiben("RTC wurde im letzten Run neu gestellt. In diesem Run wird das Kontrollbit zurückgesetzt.", log_mode=log_mode)
            print("Kontrollbit für Zeitumstellung zurückgesetzt")
            
        elif  Zeitumstellung and read_fram_bytes(0x048F, 1) == b'\x01':
            print("Zeitumstellung bereits durchgeführt. Nichts zu tun.")
            log_schreiben("------------------", log_mode=log_mode)
            log_schreiben("Zeitumstellung bereits an diesem Tag durchgeführt.", log_mode=log_mode)
        
        

    except Exception as e:
        print(f"Fehler bei der Zeitumstellung: {e}")
        
if __name__ == "__main__":
    print("Beispieldatum für Zeitumstellung: 2025-10-26 12:00:00\nsetze RTC auf dieses Datum für einen Test")
    set_hwc("daylight_saving","manual", "20251026120000")
    daylight_saving_check(log_mode="manual")
    print("---------------------------------")
    print("Nochmaliger Test am selben Tag (keine Änderung erwartet)")
    daylight_saving_check(log_mode="manual")
    print("---------------------------------")
    print("Test am folgenden Tag ohne Zeitumstellung (keine Änderung erwartet, nur Rücksetzen des Kontrollbits)")
    set_hwc("daylight_saving", "manual","20251027020000")
    daylight_saving_check(log_mode="manual")