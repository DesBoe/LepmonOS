import time
from fram_operations import*
import datetime



def get_unix_time():
    return int(time.time())

def write_runtime_start():
    # Schreibe aktuellen Unix-Zeitstempel ins FRAM (4 Byte)
    try:
        write_fram_bytes(0x0370, get_unix_time().to_bytes(4, 'big'))
    except Exception as e:
        print(f"Fehler beim Schreiben des Startzeitpunkts: {e}")    
        
        
def write_timestamp(adress):
    # Schreibe aktuelle Uhrzeit als String ins FRAM (19 Byte)
    '''
    RPI Activity Timestamp: 0x07E0
    Daylight Saving: 0x0470
    Format: "YYYY-MM-DD HH:MM:SS"'''
    try:
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        write_fram_bytes(adress, now_str.encode("utf-8"))
    except Exception as e:
        print(f"Fehler beim Schreiben des RPI-Aktivitätszeitstempels: {e}")

def read_runtime_start():
    try:
        return int.from_bytes(read_fram_bytes(0x0370, 4), 'big')
    except Exception as e:
        print(f"Fehler beim Lesen des Startzeitpunkts: {e}")
        return 0

def write_total_runtime(total_seconds):
    try:
        write_fram_bytes(0x0350, int(total_seconds).to_bytes(4, 'big'))
    except Exception as e:
        print(f"Fehler beim Schreiben der Gesamtlaufzeit: {e}")

def read_total_runtime():
    try:
        return int.from_bytes(read_fram_bytes(0x0350, 4), 'big')
    except Exception as e:
        print(f"Fehler beim Lesen der Gesamtlaufzeit: {e}")
        return 0

def on_start():
    now = get_unix_time()
    try:
        last_start = read_runtime_start()
        total_runtime = read_total_runtime()
    except Exception as e:
        print("Fehler beim Lesen der Laufzeitdaten:", e)
        last_start = 0
        total_runtime = 0

    # Prüfe, ob ein alter Startwert existiert (Gerät wurde nicht sauber beendet)
    if last_start > 0 and last_start < now:
        diff = now - last_start
        total_runtime += diff
        try:
            write_total_runtime(total_runtime)
            print(f"Unsauberer Shutdown erkannt, {diff} Sekunden nachgetragen.")
        except Exception as e:
            print("Fehler beim Schreiben der Laufzeit:", e)
            total_runtime = 0


def on_shutdown():
    now = get_unix_time()
    try:
        last_start = read_runtime_start()
        total_runtime = read_total_runtime()
    except Exception as e:
        print("Fehler beim Lesen der Laufzeitdaten:", e)
        last_start = None
        total_runtime = None
    if last_start is not None and last_start > 0 and last_start < now:
        diff = now - last_start
        total_runtime += diff
        write_total_runtime(total_runtime)
        print(f"Laufzeit {diff} Sekunden hinzugefügt.")
        
def gap_day():
    """
    Überprüft, ob der Aktivitätszeitstempel im FRAM weniger als 1 Tag alt ist.
    Gibt True zurück, wenn der Zeitstempel aktuell ist, sonst False.
    """
    try:
        # Lese den Aktivitätszeitstempel aus dem FRAM
        activity_timestamp_bytes = read_fram_bytes(0x07E0, 19)
        activity_timestamp_str = activity_timestamp_bytes.decode("utf-8")
        activity_time = datetime.datetime.strptime(activity_timestamp_str, "%Y-%m-%d %H:%M:%S")
        
        # Hole den aktuellen Zeitstempel
        now = datetime.datetime.now()
        
        # Berechne den Unterschied in Tagen
        difference = (now - activity_time).total_seconds()
        print(f"Letzter Aktivitätszeitstempel: {activity_time}, jetzt:{now}, Unterschied in Sekunden: {difference}")
        
        # Überprüfe, ob der Unterschied mehr als 1 Tag beträgt
        return difference <= 86399  # 86400 Sekunden = 1 Tag
    except Exception as e:
        print(f"Fehler beim Überprüfen des Aktivitätszeitstempels: {e}")
        return False

if __name__ == "__main__":
    print("Laufzeitwerkzeuge")
    print(f"Gesamtlaufzeit: {read_total_runtime()} Sekunden")
    print(f"Letzter Startzeitpunkt: {read_runtime_start()}")