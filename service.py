import os
from datetime import datetime
from json_read_write import *
from times import *
from logging_utils import error_message, log_schreiben
import time
from times import *
import subprocess
from fram_operations import *
from OLED_panel import show_message
from language import get_language
from hardware import get_hardware_version
import re
from GPIO_Setup import *

lang = get_language()



def get_Lepmon_code(log_mode):
    province = None
    Kreis_code = None
    project_name = None
    sn = None
    
    try:
        project_name = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","general","project_name")
    except Exception as e:
        error_message(11,e,log_mode)
        print(f"Fehler beim Lesen des Projektnamens: {e}")
        project_name = "Lepmon#"    
    time.sleep(.5)
        
    try:
        province = read_fram(0x04D0,3).replace('\x00', '').strip()
    except Exception as e:
        error_message(9,e,log_mode)
    time.sleep(.5)    
    
    if province == None or province == "":
        print("Fehler: Provinz im FRAM leer!")
        time.sleep(.5)
        try:
            province = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "locality", "province")
        except Exception as e:
            error_message(11,e)
            province = "Fehler_Provinz"
    time.sleep(.5)    
        
    try:
        Kreis_code = read_fram(0x04F0,3).replace('\x00', '').strip()
    except Exception as e:
        error_message(9,e,log_mode)
    time.sleep(.5)
    if Kreis_code == None or Kreis_code == "":
        print("Fehler: Kreiskürzel im FRAM leer!")
        time.sleep(.5)
        try:
            Kreis_code = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "locality", "Kreis")
        except Exception as e:
            error_message(11,e)
            Kreis_code = "Fehler_Kreis"
            
    try: 
        sn = read_fram(0x0110, 8).strip()
    except Exception as e:
        error_message(9,e,log_mode)
    time.sleep(.5)
    
    if sn == None:
        print("Konnte sn nicht aus Ram lesen, nutze Konfigurationsdatei")
        try:        
            sn = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","general","serielnumber")  
        except Exception as e:
            error_message(11,e,log_mode)
            sn = "Fehler_sn"      
                
    return project_name,province, Kreis_code, sn



def get_usb_path(log_mode):
    """Ermittelt den Pfad des USB-Sticks. Wiederholt, bis ein Stick gefunden wird."""
    zielverzeichnis = None
    status = 0
    username = os.getenv('USER')
    media_path = f"/media/{username}"
    search_counter = 0
    while zielverzeichnis is None:
        search_counter += 1  
        if search_counter == 3:
            error_message(3, "USB-Stick nicht gefunden", log_mode)
        if 4 < search_counter < 9:
            turn_on_led("gelb")
            time.sleep(.5)
            turn_off_led("gelb")
        if search_counter > 10:
            print("USB Stick nach 10 versuchen nicht gefunden. Zielverzeichneis ist None")
            zielverzeichnis = "Kein USB-Stick gefunden"
            return zielverzeichnis, status
        if os.path.exists(media_path):
            for item in os.listdir(media_path):
                pot_dir = os.path.join(media_path, item)
                if os.path.ismount(pot_dir):
                    zielverzeichnis = pot_dir
                    status = 1
                    
                    return zielverzeichnis, status
        print("Suche nach USB-Stick...")
        time.sleep(.5)
    return zielverzeichnis, status      
            
def erstelle_ordner(log_mode, Cameramodel = "None"):
    project_name, province, Kreis_code,sn = get_Lepmon_code(log_mode)
    zielverzeichnis,_ = get_usb_path(log_mode)
    jetzt_local, _, _ = Zeit_aktualisieren(log_mode)
    jetzt_local = datetime.strptime(jetzt_local, "%Y-%m-%d %H:%M:%S")
    aktueller_nachtordner = None
    try:
        #if aktueller_nachtordner is None or not os.path.exists(aktueller_nachtordner):
        if log_mode == "log":
            ordnername = f"{project_name}{sn}_{province}_{Kreis_code}_{jetzt_local.strftime('%Y')}-{jetzt_local.strftime('%m')}-{jetzt_local.strftime('%d')}_T_{jetzt_local.strftime('%H%M')}"
            aktueller_nachtordner = os.path.join(zielverzeichnis, ordnername)
            os.makedirs(aktueller_nachtordner, exist_ok=True)
            print(f"Ordner erstellt: {aktueller_nachtordner}")
            write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "current_folder",aktueller_nachtordner)
            write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "Control_End", True)
            write_fram_bytes(0x07A0, b'\x01')
            print("Pfad des Ausgabe Ordner in der Konfigurationsdatei gespeichert")
            return aktueller_nachtordner
        elif log_mode == "manual":
            ordnername = f"{project_name}{sn}_Manueller_TestRun_{jetzt_local.strftime('%Y')}-{jetzt_local.strftime('%m')}-{jetzt_local.strftime('%d')}_T_{jetzt_local.strftime('%H%M')}"
            aktueller_nachtordner = os.path.join(zielverzeichnis, ordnername)
            os.makedirs(aktueller_nachtordner, exist_ok=True)
            print(f"Ordner für Manuellen Testlauf erstellt: {aktueller_nachtordner}")
            write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "current_folder",aktueller_nachtordner)
            print("Pfad des Ausgabe Ordner in der Konfigurationsdatei gespeichert")
            return aktueller_nachtordner
        elif log_mode == "kamera_test":
            print("Debug1")
            ordnername = f"Belichtungsreihe_{Cameramodel}"
            aktueller_nachtordner = os.path.join(zielverzeichnis, ordnername)
            os.makedirs(aktueller_nachtordner, exist_ok=True)
            print(f"Ordner Kameratestlauf erstellt: {aktueller_nachtordner}")
            write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "current_folder",aktueller_nachtordner)
            print("Pfad des Kamera Test Ordner in der Konfigurationsdatei gespeichert")
            return aktueller_nachtordner
    except Exception as e:
        error_message(3,e, log_mode)
        return aktueller_nachtordner
        

def delete_USB_content(log_mode):  
    zielverzeichnis,_ = get_usb_path(log_mode)
    aktueller_nachtordner = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "current_folder")
    do_not_delete_path = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "locality", "do_not_delete_path")
    try:
        ordner_liste = [
            os.path.join(zielverzeichnis, item)
            for item in os.listdir(zielverzeichnis)
            if os.path.isdir(os.path.join(zielverzeichnis, item))
            and os.path.abspath(os.path.join(zielverzeichnis, item)) != os.path.abspath(aktueller_nachtordner)
            and os.path.abspath(os.path.join(zielverzeichnis, item)) != os.path.abspath(do_not_delete_path)
        ]
        gesamtzahl = len(ordner_liste)
        zaehler = 0

        for item_path in ordner_liste:
            zaehler += 1
            show_message("service_1", lang= get_language(), zaehler=zaehler, gesamtzahl=gesamtzahl)
            try:
                subprocess.run(['rm', '-rf', item_path], check=True)
                lokale_Zeit = datetime.now().strftime("%Y-%m-%d %H:%M:%S",)
                log_schreiben(f"Ordner gelöscht: {item_path}", log_mode=log_mode)
                print(f"Ordner gelöscht: {item_path}")
            except Exception as e:
                log_schreiben(f"Fehler beim Löschen des Ordners {item_path}: {e}", log_mode=log_mode)
        for item in os.listdir(zielverzeichnis):
            item_path = os.path.join(zielverzeichnis, item)
            if os.path.isfile(item_path) and (item_path.endswith('.Key') or item_path.endswith('.txt')):
                try:
                    os.remove(item_path)
                    lokale_Zeit = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    log_schreiben(f"Datei gelöscht: {item_path}", log_mode=log_mode)
                    print(f"Datei gelöscht: {item_path}")
                except Exception as e:
                    log_schreiben(f"Fehler beim Löschen der Datei {item_path}: {e}",log_mode=log_mode)

    except Exception as e:
        log_schreiben(f"Fehler beim Löschen des USB-Inhalts: {e}",log_mode=log_mode)


def initialisiere_logfile(log_mode):
  aktueller_nachtordner = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json","general","current_folder")
  #jetzt_local = datetime.now()
  #lokale_Zeit = jetzt_local.strftime("%H:%M:%S")
  jetzt_local, lokale_Zeit,_ = Zeit_aktualisieren(log_mode)
  
  ordnername = os.path.basename(aktueller_nachtordner)
  log_dateiname = f"{ordnername}.log"
  log_dateipfad = os.path.join(aktueller_nachtordner, log_dateiname)
  
  try:
        # Initiales Erstellen des Logfiles
        if not os.path.exists(log_dateipfad):
            with open(log_dateipfad, 'w') as f:
                f.write(f"{lokale_Zeit}; Logfile erstellt: {log_dateipfad}\n")
                print(f"logdatei erstellt:{log_dateipfad}")
                write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "current_log",log_dateipfad)
                print(f"Pfad der Logdatei in der Konfigurationsdatei gespeichert")
                time.sleep(.5)
  except Exception as e:
        lokale_Zeit = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"{lokale_Zeit}; Fehler beim Erstellen des Logfiles: {e}")
        return None

def get_disk_space(log_mode):
    path, status = get_usb_path(log_mode)
    try:
        stat = os.statvfs(path) # Erhalte Informationen über den Dateisystemstatus
        total_space = stat.f_frsize * stat.f_blocks # Gesamtgröße des Dateisystems in Bytes
        used_space = stat.f_frsize * (stat.f_blocks - stat.f_bfree) # Verwendeter Speicherplatz in Bytes
        free_space = stat.f_frsize * stat.f_bavail # Freier Speicherplatz in Bytes
        
        # Konvertiere Bytes in GB
        total_space_gb = round(total_space / (1024 ** 3), 2)
        used_space_gb = round(used_space / (1024 ** 3), 2)
        free_space_gb = round(free_space / (1024 ** 3), 2)
        
        used_percent = round((used_space / total_space) * 100, 2) # Berechne Prozentanteil des belegten und freien Speicherplatzes
        free_percent = round((free_space / total_space) * 100, 2)


        print(f"Speicher gesamt:{total_space_gb}")
        print(f"Speicher belegt:{used_space_gb}")
        print(f"Speicher frei:{free_space_gb}")
        print(f"Speicher belegt:{used_percent}")
        print(f"Speicher frei:{free_percent}")

        return total_space_gb, used_space_gb, free_space_gb, used_percent, free_percent
    except Exception as e:
        log_schreiben(f"Fehler beim Abrufen des Speicherplatzes: {e}", log_mode=log_mode)
        return None, None, None, None, None   



def RPI_time(log_mode):
    """
    Funktion um die Zeit des Raspberry Pi zu setzen
    """
    jetzt_local,_ ,_ = Zeit_aktualisieren(log_mode)
        
    try:
        subprocess.run(['sudo', 'date', "-s", jetzt_local])
        print(f"Uhrzeit des Pi auf {jetzt_local} gestellt")
    except Exception as e:
        print(f"Fehler beim Stellen der RPi Uhr: {e}") 
        
def compare_hardware_version():
    ARNI_Gen_ram = None
    ARNI_Gen_json = None
    try: 
        ARNI_Gen_ram = read_fram(0x0130, 16).replace('\x00', '').strip() or ""
    except Exception as e:
        print(f"Fehler beim Lesen der ARNI_Gen aus dem FRAM: {e}")
    try:
        ARNI_Gen_json = get_value_from_section("/home/Ento/serial_number.json", "general", "Fallenversion")
        print("Lese ARNI_Gen aus der JSON Datei nach FRAM Fehler")
    except Exception as e:
                print(f"Fehler beim Lesen der ARNI_Gen aus der JSON: {e}")
    
    if ARNI_Gen_ram != None:
        if ARNI_Gen_ram == ARNI_Gen_json:
            print("ARNI Generationslabel stimmen im Fram und JSON Datei überein")
        
        if ARNI_Gen_ram != ARNI_Gen_json:
            write_value_to_section("/home/Ento/serial_number.json", "general", "Fallenversion",ARNI_Gen_ram)    
            print(f"ARNI Generation im Jsonfile aktualisiert:")
            print(f"    ARNI Generation aus RAM  gelesen:    {ARNI_Gen_ram}")    
            print(f"    ARNI Generation aus JSON gelesen:    {ARNI_Gen_json}")  
            print(f"    ARNI Generation in JSON geschrieben: {ARNI_Gen_ram}")       
                
    
            
def compare_sn(log_mode):
    sn_ram = None
    sn_json = None    
    hardware = get_hardware_version()
    
    try:
        sn_json = get_value_from_section("/home/Ento/serial_number.json", "general", "serielnumber")
        sn = sn_json
    except Exception as e:
        print(f"Fehler beim Lesen der Seriennnummer aus der separaten json Datei: {e}")    
        
    if hardware == "Pro_Gen_3":
        try: 
            sn_ram = read_fram(0x0110, 8).strip()
            print(f"Serial Number from FRAM: {sn_ram}") 
        except Exception as e:
            print(f"Fehler beim Lesen der Seriennummer aus dem FRAM: {e}")   
            error_message(9,e, log_mode)  
         
    if sn_ram is not None and sn_json is not None:
        if sn_ram == sn_json:
            print("Seriennummern in Ram und json Datei stimmen überein")
            
        if sn_ram != sn_json:
            write_value_to_section("/home/Ento/serial_number.json", "general", "serielnumber",sn_ram)    
            print(f"Seriennummer im Jsonfile aktualisiert:")
            print(f"    SN aus RAM  gelesen:    {sn_ram}")    
            print(f"    SN aus JSON gelesen:    {sn_json}")  
            print(f"    SN in JSON geschrieben: {sn_ram}")    
            sn = sn_ram    
    return sn 


def compare_fram_json(log_mode):
    compare_hardware_version()
    sn = compare_sn(log_mode)
    
    return sn
    
   
def force_new_location_code(log_mode):
    allowed_pattern = re.compile(r"^[a-zA-Z0-9_\-]+$")
    _, province, Kreis_code, _ = get_Lepmon_code(log_mode)
    
    if not allowed_pattern.match(province) or not allowed_pattern.match(Kreis_code):
        print(f"Warnung: LEPMON Code enthält unerlaubte Zeichen: {province} {Kreis_code}")
        force_set_location_code = True
    else:
        force_set_location_code = False
    
    return force_set_location_code

def dev_info():
    show_message("dev_1", lang="de")
    print("##############################\n##############################\n#### interne Test Version ####\n##############################\n##############################")
    time.sleep(1)
    
    
       

if __name__ == "__main__":
    print("Hilfsfunktionen für den Service")
    project_name,province, Kreis_code, sn = get_Lepmon_code(log_mode="manual")
    print(f"Zeichenfolge: {project_name}-{province}-{Kreis_code}-{sn}")
    print("---------------------------------")
    print("Suche angeschlossenen USB-Stick...")
    usb_path, status = get_usb_path(log_mode="manual")
    print(f"USB-Stick Pfad: {usb_path}")
    print("---------------------------------")
    print("Speicherplatz des USB-Sticks abfragen...")
    total_space_gb, used_space_gb, free_space_gb, used_percent, free_percent = get_disk_space(log_mode="manual")
    print("---------------------------------")
    print("aktualisiere Uhrzeit des Raspberry Pi...")
    RPI_time(log_mode="manual")
    print("---------------------------------")
    print("Vergleiche Hardware Version und Seriennummer zwischen FRAM und JSON...")
    compare_hardware_version()
    print("---------------------------------")
    print("Vergleiche Seriennummer zwischen FRAM und JSON...")
    compare_sn(log_mode="manual")