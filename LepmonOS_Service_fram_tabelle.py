from fram_direct import read_fram, read_fram_bytes
from tabulate import tabulate
import time
from datetime import datetime, timedelta
from service import *
from language import get_language
from image_quality_check import first_exp

def decode_bytes(data):
    if isinstance(data, str):
        return data
    if isinstance(data, bytes):
        try:
            text = data.decode("utf-8").strip('\x00')
            if text and all(32 <= ord(c) < 127 for c in text):
                return text
        except Exception:
            pass
        if len(data) <= 4:
            try:
                return int.from_bytes(data, "big")
            except Exception:
                pass
        return " ".join(f"{b:02X}" for b in data)
    return str(data)

def format_runtime(secs):
    try:
        secs = int(secs)
        minutes, sec = divmod(secs, 60)
        hours, minute = divmod(minutes, 60)
        days, hour = divmod(hours, 24)
        years, day = divmod(days, 365)
        months, day = divmod(day, 30)
        return f"{years}y {months}m {day}d {hour}h {minute}min"
    except Exception:
        return str(secs)

def format_timestamp(ts):
    try:
        ts = int(ts)
        dt = datetime.fromtimestamp(ts)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ts)

def format_gb(val):
    try:
        gb = int(val) / 1024 / 1024 / 1024
        return f"{gb:.1f} GB"
    except Exception:
        return str(val)

if __name__ == "__main__":
    logmode = "manual"
    
    _,province, Kreis_code, sn = get_Lepmon_code(log_mode=logmode)
    
    
    werte = []

    werte.append(("Power_ON", decode_bytes(read_fram_bytes(0x0010,16))))
    werte.append(("Power_OFF", decode_bytes(read_fram_bytes(0x0040,16))))
    werte.append(("Serialnumber", sn))
    werte.append(("ARNI_Version", decode_bytes(read_fram(0x0130,9))))
    werte.append(("Backplane", decode_bytes(read_fram(0x0150,15))))
    werte.append(("Lieferdatum", decode_bytes(read_fram(0x0170,10))))
    werte.append(("Boot_counter", decode_bytes(read_fram_bytes(0x0310,4))))
    werte.append(("User_Interface_counter", decode_bytes(read_fram_bytes(0x0330,4))))

    # total_runtime
    total_runtime_raw = decode_bytes(read_fram_bytes(0x0350,4))
    werte.append(("total_runtime", format_runtime(total_runtime_raw)))

    # timestamp_last_start
    ts_last_start_raw = decode_bytes(read_fram_bytes(0x0370,4))
    werte.append(("timestamp_last_start", format_timestamp(ts_last_start_raw)))

    # Gigabytes_free_at_start
    gb_free_raw = decode_bytes(read_fram_bytes(0x0390,4))
    werte.append(("Gigabytes_used_at_start", format_gb(gb_free_raw)))

    power_mode = read_fram(0x03B0, 16).replace('\x00', '').strip()
    werte.append(("Strom", power_mode))
    
    # Koordinaten
    latitude = decode_bytes(read_fram(0x03C0, 16)).replace('\x00', '').strip()
    longitude = decode_bytes(read_fram(0x03E0, 16)).replace('\x00', '').strip()
    Pol = decode_bytes(read_fram(0x03D0, 1)).replace('\x00', '').strip()
    Block = decode_bytes(read_fram(0x03F0, 1)).replace('\x00', '').strip()
    
    werte.append(("latitude", latitude))
    werte.append(("Pol", Pol))
    werte.append(("longitude", longitude))
    werte.append(("Block", Block))


    # Lepmon Code
    
    Country_Fram_alt = decode_bytes(read_fram(0x04A0,7))
    #Province_Fram_alt = decode_bytes(read_fram(0x04D0,2))
    #Kreis_Fram_alt = decode_bytes(read_fram(0x04F0,1))
  
    werte.append(("Land", Country_Fram_alt))
    werte.append(("Provinz", province))
    werte.append(("Stadt", Kreis_code))
    
    werte.append(("Software_Date", decode_bytes(read_fram(0x0510,10))))
    software_version = decode_bytes(read_fram(0x0520, 10)).replace('\x00', '').strip()
    werte.append(("Software_Version", software_version))
    last_rpi_activity = decode_bytes(read_fram(0x07E0, 19)).replace('\x00', '').strip()
    werte.append(("new_package", "no" if read_fram_bytes(0x056F, 1)[0] == 0x01 else "yes"))
    
    werte.append(("Sprache", get_language()))

    werte.append(("erwartete Bildzahl", "Siehe LepmonOS_config.json"))
    counted_images = int.from_bytes(read_fram_bytes(0x0650, 4), byteorder='big')
    werte.append(("gezählte Bilder", counted_images))
    exp, gain = first_exp(1, "manual")
    werte.append(("Exposure", exp))
    werte.append(("Gain", gain))
    
    
    
    
    
    
    
    
    
    
    
    
    werte.append(("Kontrolle_Fang", "yes" if read_fram_bytes(0x07A0, 1) == b'\x01' else "no"))
    werte.append(("Kontrolle_Nacht", "yes" if read_fram_bytes(0x07C0, 1) == b'\x01' else "no"))
    werte.append(("last_RPI_activity", last_rpi_activity))
    try:
        aktueller_fehler_bytes = read_fram_bytes(0x0810, 4)
        aktueller_fehler = int.from_bytes(aktueller_fehler_bytes, "big")
    except Exception:
        aktueller_fehler = "unbekannt"
    werte.append(("aktueller_Fehler", aktueller_fehler))
    #werte.append(("aktueller_Fehler", decode_bytes(read_fram_bytes(0x0810,4))))

    # Fehler-Tabelle
    for i, addr in enumerate(range(0x0840, 0x09F0, 0x20), 1):
        werte.append((f"Fehler {i:02d}", decode_bytes(read_fram_bytes(addr, 4))))
        time.sleep(.1)

    print(tabulate(werte, headers=["Label", "Wert"], tablefmt="github"))