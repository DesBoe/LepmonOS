from fram_direct import *
from configparser import ConfigParser
from datetime import datetime, timedelta
from json_read_write import *


from LepmonOS_Service_fram_delete import clear_fram

CONFIG_PATH = "LepmonOS_Service_fram_config.ini"
CONFIG_PATH = "/home/Ento/LepmonOS/LepmonOS_Service_fram_config.ini"

def write_config_to_fram():
    now = datetime.now()
    ts_now = now.strftime("%Y-%m-%d %H:%M:%S")
    ts_plus1h = (now + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    ts_minus1y = (now - timedelta(days=365)).strftime("%Y-%m-%d %H:%M:%S")
    

    config = ConfigParser()
    try:
        config.read(CONFIG_PATH)
        if "FRAM" not in config.sections():
            print("Sektion [FRAM] fehlt! Datei oder Pfad prüfen.")
        elif"FRAM" in config.sections():
            print("FRAM Konfigurationsdatei erfolgreich gelesen.")
    except Exception as e:
        print(f"Fehler beim Lesen der FRAM Konfigurationsdatei: {e}")
        
    
        return
 ####Attiny Data####       
    write_fram(0x0000, "power_on")
    write_fram(0x0010, ts_now)
    write_fram(0x0030, "power_off")
    write_fram(0x0040, ts_plus1h)
    write_fram(0x0060, "status")
    
#### Raspi Data ####  
    write_fram(0x0100, "serial_number")
    write_fram(0x0120, "trap_version") 
    write_fram(0x0130, config.get("FRAM", "fallen_version"))    
    write_fram(0x0140, "backplane_vers") 
    write_fram(0x0150, config.get("FRAM", "backplane_version")) 
    write_fram(0x0160, "delivery_PMJ")  
    write_fram(0x0170, config.get("FRAM", "lieferdatum_an_PMJ"))  
    
#### laufzeit Labels ####
    write_fram(0x0300, "boot_counter")
    write_fram(0x0320, "user_counter")
    write_fram(0x0340, "total_runtime")
    write_fram(0x0360, "last_start")
    write_fram(0x0380, "GB_used_start")
### Power Management ###
    write_fram(0x03A0, "power_mode") 
    power_mode = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","powermode","supply")
    write_fram(0x03B0, power_mode)
    
### Lepmon GPS Daten ####
    latitude = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","GPS","latitude")
    write_fram(0x03C0, str(latitude)) # latitude N-S
    write_fram(0x03D0, "N") # latitude Vorzeichen
    longitude = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","GPS","longitude")
    write_fram(0x03E0, str(longitude)) # longitude E-W
    write_fram(0x03F0, "E") # longitude Vorzeichen

### Lepmon Code Standort Daten ####
    write_fram(0x0490, "Land") 
    Land = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","locality","country")
    write_fram(0x04A0 , Land)    
    write_fram(0x04C0, "Provinz")
    Provinz = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","locality","province")
    write_fram(0x04D0, Provinz)
    write_fram(0x04E0, "Stadt")
    Kreis = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","locality","Kreis")
    write_fram(0x04F0, Kreis)
    
#### Software Informationen ####    
    write_fram(0x0500, "software")
    software_date = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","software","date")
    software_version = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","software","version")
    write_fram(0x0510, software_date)
    write_fram(0x0520, software_version)

    write_fram(0x0560, "new_package")
    
#### Sprache ####
    write_fram(0x0600, "language")
    lang = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","general","language")
    write_fram(0x0610, lang)

### RPI Activity Log ###
    write_fram(0x0620, "images_expected".ljust(16))
    write_fram(0x0640, "images_count".ljust(16))
    
### Current Exp/Gain ###    
    write_fram(0x0680, "current_Exp_Gain".ljust(16))
    current_exposure = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","capture_mode","initial_exposure")
    current_gain = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","capture_mode","initial_gain")
    write_fram_bytes(0x0698, (current_exposure).to_bytes(1, byteorder='big'))
    write_fram_bytes(0x069C, (current_gain).to_bytes(1, byteorder='big'))
    #write_fram(0x0698, str(current_exposure))
    #write_fram(0x069C, str(current_gain))
    
    
    
    write_fram(0x07D0, "RPI_activity")
    write_fram(0x07E0, ts_minus1y)  # Letzte Aktivität
    
#### Fehlercode 0###
    write_fram(0x0800, "error_code")
    write_fram_bytes(0x081F, (0).to_bytes(4, byteorder='big'))  # Fehlercode 0
#### Fehlerhäufigkeitstabelle ####   
    write_fram(0x0820, "error_counts") 
    write_fram(0x0830, "Err01")
    write_fram(0x0850, "Err02")
    write_fram(0x0870, "Err03") 
    write_fram(0x0890, "Err04")
    write_fram(0x08B0, "Err05")
    write_fram(0x08D0, "Err06")
    write_fram(0x08F0, "Err07")
    write_fram(0x0910, "Err08")
    write_fram(0x0930, "Err09")
    write_fram(0x0950, "Err10")
    write_fram(0x0970, "Err11")
    write_fram(0x0990, "Err12")
    write_fram(0x09B0, "Err13")
    write_fram(0x09D0, "Err14")


    print("Alle Werte erfolgreich in FRAM geschrieben.")

if __name__ == "__main__":
    clear_fram("setup")
    print("FRAM Configurator GEN 2")
    write_config_to_fram()
    dump_fram(0x0000, 0x09EF)