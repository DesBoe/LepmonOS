from GPIO_Setup import *
from OLED_panel import show_message
import json
import time
from json_read_write import *
from logging_utils import log_schreiben
from fram_operations import write_fram, read_fram
from language import get_language
import os

with open("/home/Ento/LepmonOS/sites.json", "r") as f:
    data = json.load(f)

lang = get_language()

def set_location_code(log_mode):
    country_old = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "locality", "country")
    province_old = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "locality", "province")
    Kreis_code_old = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "locality", "Kreis")
    level = "country"
    index = 0
    country = None
    province = None
    Kreis_code = None
    while True:
        turn_on_led("blau")
        if level == "country":
            countries = list(data.keys())
            show_message("side_1", lang = lang, country = f"{countries[index]}")
        elif level == "province":
            provinces = list(data[country].keys())
            show_message("side_2", lang = lang, province = f"{provinces[index]}")
        elif level == "Kreis":
            codes = data[country][province][1:]
            show_message("side_3", lang = lang, Kreis = f"{codes[index]}")

        if button_pressed("oben"):
            if level == "country":
                index = (index - 1) % len(data)
                time.sleep(.05)
            elif level == "province":
                index = (index - 1) % len(data[country])
                time.sleep(.05)                
            elif level == "Kreis":
                Kreis_count = len(data[country][province][1:])
                time.sleep(.05)                
                if Kreis_count >1:
                    index = (index - 1) % Kreis_count
                    index = max(0, index)
                if index == 1:
                    index = Kreis_count-1  

        if button_pressed("unten"):
            if level == "country":
                index = (index + 1) % len(data)
                time.sleep(.05)
            elif level == "province":
                index = (index + 1) % len(data[country])
                time.sleep(.05)
            elif level == "Kreis":
                Kreis_count = len(data[country][province][1:])
                time.sleep(.05)
                if Kreis_count >1:
                    index = (index + 1) % Kreis_count
                    index = max(0, index)   
                elif Kreis_count ==1:
                    index = 1  
        if button_pressed("rechts"):
            if level == "country":
                country = countries[index]
                level = "province"
                index = 0
                time.sleep(.75)               
            elif level == "province":
                provinces = list(data[country].keys())
                province = provinces[index]
                codes = data[country][province]
                province_code = codes[0] if codes else None
                print(province_code)
                level = "Kreis"
                Kreis_count = len(data[country][province])
                index = 0
                time.sleep(.05)                
            elif level == "Kreis":
                codes = data[country][province][1:]
                Kreis_code = codes[index]
        if button_pressed("enter"):
            if Kreis_code == None:   
                pass               
            if level == "Kreis" and Kreis_code != None:     
                show_message("side_4", lang = lang)
                print(f"Ausgewählter Ort: {country} {province_code} {Kreis_code}")
                show_message("side_5", lang = lang, country = f"{country}",province = f"{province}", Kreiscode = f"{Kreis_code}" )
                break
        time.sleep(.05)
        
        
    write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "locality", "country", country)   
    write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "locality", "province",province_code)
    write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "locality", "Kreis",Kreis_code)
    print("saved information on location code in configuration file")
    
    try:
        Country_Fram_alt = read_fram(0x04A0,32).strip()
        Province_Fram_alt = read_fram(0x04D0,16).strip()
        Kreis_Fram_alt = read_fram(0x04F0,16).strip()
    except Exception as e:
        print(f"Fehler beim Lesen des Lepmon Codes aus dem FRAM: {e}")
        Country_Fram_alt = None
        Province_Fram_alt = None
        Kreis_Fram_alt = None    
    
    if Country_Fram_alt != country and Country_Fram_alt is not None:
        try:
            write_fram(0x04A0, b'\x00' * 32)  # 32 Nullbytes schreiben
            print("RAM-Bereich 0x04A0 erfolgreich gelöscht.")
        except Exception as e:
            print(f"Fehler beim Löschen des RAM-Bereichs 0x04A0: {e}")
        
        write_fram(0x04A0, country.ljust(32).encode('utf-8'))
        print("Land in FRAM aktualisiert")
        
    if Province_Fram_alt != province_code and Province_Fram_alt is not None:
        try:
            write_fram(0x04D0, b'\x00' * 16)  # 16 Nullbytes schreiben
            print("RAM-Bereich 0x04D0 erfolgreich gelöscht.")
        except Exception as e:
            print(f"Fehler beim Löschen des RAM-Bereichs 0x04D0: {e}")
        write_fram(0x04D0, province_code.ljust(16).encode('utf-8'))
        print("Provinz in FRAM aktualisiert")
        
    if Kreis_Fram_alt != Kreis_code and Kreis_Fram_alt is not None:
        try:
            write_fram(0x04F0, b'\x00' * 16)  # 16 Nullbytes schreiben
            print("RAM-Bereich 0x04F0 erfolgreich gelöscht.")
        except Exception as e:
            print(f"Fehler beim Löschen des RAM-Bereichs 0x04F0: {e}")
        write_fram(0x04F0, Kreis_code.ljust(16).encode('utf-8'))
        print("Kreis in FRAM aktualisiert")
    
        
    new = False
        
    if country == country_old:
        log_schreiben(f"Land unverändert: {country}", log_mode=log_mode)
    elif country != country_old:
        log_schreiben(f"Land wurde neu eingegeben: {country}", log_mode=log_mode)
        new = True
        
    if province_code == province_old:
        log_schreiben(f"Provinz unverändert: {province}", log_mode=log_mode)
    elif province_code != province_old:
        log_schreiben(f"Provinz wurde neu eingegeben: {province}", log_mode=log_mode)
        new = True
        
    if Kreis_code == Kreis_code_old:
        log_schreiben(f"Kreis unverändert: {Kreis_code}", log_mode=log_mode)
    elif Kreis_code != Kreis_code_old:
        log_schreiben(f"Kreis wurde neu eingegeben: {Kreis_code}", log_mode=log_mode)
        new = True
            
    return new, province_old, Kreis_code_old, province_code, Kreis_code


def update_folder_and_log(json_path, province_old, Kreis_code_old, province, Kreis_code, log_mode):
    success_folder, success_log = False, False
    log_schreiben("Neuer LEPMON Code eingegeben. Aktualisiere Ordner- und Log-Namen.", log_mode=log_mode)
    current_folder = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "current_folder")
    current_log = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "current_log")

    if province_old not in current_folder or Kreis_code_old not in current_folder or f"_{province_old}_{Kreis_code_old}_" not in current_folder:
        print("Die alten Werte sind nicht im aktuellen Ordnerpfad enthalten. Ordner- und Log-Umbenennung wird übersprungen.")
        print(f"Ein möglicher Grund ist der aktuelle Logmode 'manual': {log_mode == 'manual'}")
        log_schreiben("Die alten Werte sind nicht im aktuellen Ordnerpfad enthalten. Ordner- und Log-Umbenennung wird übersprungen.", log_mode=log_mode)
        return
    
    new_folder = current_folder.replace(f"_{province_old}_{Kreis_code_old}_", f"_{province}_{Kreis_code}_")
    new_log = current_log.replace(f"_{province_old}_{Kreis_code_old}_", f"_{province}_{Kreis_code}_")
    
    try:
        os.rename(current_folder, new_folder)
        print(f"Ordner umbenannt: {current_folder} -> {new_folder}")
        write_value_to_section(json_path, "general", "current_folder", new_folder)
        success_folder = True
             
    except Exception as e:
        print(f"Fehler beim Umbenennen des Ordners: {e}")
        return
    
    current_log = os.path.join(new_folder, os.path.basename(current_log))
    
    try:
        os.rename(current_log, new_log)
        print(f"Log-Datei umbenannt: {current_log} -> {new_log}")
        write_value_to_section(json_path, "general", "current_log", new_log)
        success_log = True
    except Exception as f:
        print(f"Fehler beim Umbenennen der Log-Datei: {f}")
        return
    time.sleep(1)
    
    if success_folder:
        log_schreiben(f"Ordner erfolgreich umbenannt zu {new_folder}", log_mode=log_mode)
    if success_log:
        log_schreiben(f"Log-Datei erfolgreich umbenannt zu {new_log}", log_mode=log_mode)
        
            
            
    md5_file = f"{os.path.join(new_folder, os.path.splitext(os.path.basename(current_log))[0])}_MD5.txt"
    print(f"Lösche MD5-Datei: {md5_file}")
    if os.path.exists(md5_file):
        try:
            os.remove(md5_file)
            print(f"MD5-Datei gelöscht: {md5_file}")
            log_schreiben(f"MD5-Datei gelöscht: {md5_file}", log_mode=log_mode)
        except Exception as e:
            print(f"Fehler beim Löschen der MD5-Datei: {e}")
            log_schreiben(f"Fehler beim Löschen der MD5-Datei: {e}", log_mode=log_mode)
    else:
        print(f"MD5-Datei nicht gefunden: {md5_file}")
    
    
if __name__ == "__main__":
    print("LEPMON Code, bestehend aus Provinz und Kreis, auf dem lokalem HMI auswählen")
    set_location_code("manual")