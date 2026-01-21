import shutil
import os
from service import get_usb_path
from times import Zeit_aktualisieren
import subprocess
from fram_direct import *
from OLED_panel import *
import time
from json_read_write import get_value_from_section
from logging_utils import log_schreiben
from end import trap_shutdown
import stat
from language import get_language

lang = get_language()

def update_LepmonOS(log_mode):
    usb_mount,_ = get_usb_path(log_mode)
    Version = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "software", "version")
    timestamp,_ ,_ = Zeit_aktualisieren(log_mode)
    update_folder = os.path.join(usb_mount, "LepmonOS_update")
    target_folder = "/home/Ento/LepmonOS"
    backup_folder = target_folder + f"_backup_{Version}__{timestamp}"

    if os.path.exists(update_folder):
        show_message("update_3", lang=lang)
        print("Update-Ordner gefunden. Starte Update...")
        if os.path.exists(backup_folder):
            shutil.rmtree(backup_folder)
            
        print(f"Sichere aktuelles LepmonOS in {backup_folder}...") 
        shutil.copytree(target_folder, backup_folder)
        log_schreiben(f"altes Programm im Ordner {backup_folder} hinterlegt", log_mode=log_mode)         
        
        print("Lösche altes LepmonOS...")
        shutil.rmtree(target_folder)
        log_schreiben("alter Programmordner gelöscht", log_mode=log_mode)  
                
        print("Kopiere neues LepmonOS...")
        shutil.copytree(update_folder, target_folder)
        log_schreiben("neue LepmonOS Version geladen", log_mode=log_mode)  

        print("lösche Update Ordner vom USB Stick...")
        shutil.rmtree(update_folder)
        log_schreiben(f"Update-Ordner {update_folder} vom USB Stick gelöscht", log_mode=log_mode) 

        print("Update abgeschlossen")
    else:
        print("Kein Update-Ordner auf USB-Stick gefunden.")
        show_message("update_4", lang=lang)
        log_schreiben("kein Update gefunden", log_mode=log_mode)
        
           
def is_valid_update_stick(log_mode):
    usb_mount,_ = get_usb_path(log_mode)
    marker_file = os.path.join(usb_mount, "LEPMON_UPDATE.KEY")
    if not os.path.exists(marker_file):
        print("LEPMON_UPDATE.KEY Datei nicht gefunden.")
        show_message("update_5", lang = lang)
        return False
    with open(marker_file, "r") as f:
        content = f.read()
        print(f"LEPMON_UPDATE.KEY Datei gefunden. Inhalt: {content} Fahre mit Update fort")
        show_message("update_6", lang = lang)
    return "LEPMON-UPDATE-KEY-2025" in content

def get_new_version_from_stick(log_mode):
    usb_mount,_ = get_usb_path(log_mode)
    version_file = os.path.join(usb_mount, "version.txt")
    if not os.path.exists(version_file):
        print("Keine version.txt auf dem Stick gefunden!")
        return None
    with open(version_file, "r") as f:
        return f.read().strip()
    
def get_current_version():
    # Lies die aktuelle Version aus dem FRAM (als String)
    try:
        current_version = read_fram(0x0520, 5)
    except Exception as e:
        current_version = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "software", "version")
    if current_version:
        return current_version.strip()
    return None

def version_tuple(version_str):
    return tuple(map(int, version_str.strip().split(".")))

def is_update_allowed(log_mode):
    new_version = get_new_version_from_stick(log_mode)
    current_version = get_current_version()
    if not new_version or not current_version:
        print("Konnte Version nicht lesen.")
        show_message("update_7", lang = lang)
        log_schreiben("neue Version nicht gefunden",2, log_mode=log_mode)
        return False
    if version_tuple(new_version) == version_tuple(current_version):
        print("Version ist gleich, Update nicht nötig.")
        show_message("update_8", lang = lang)
        log_schreiben("Firmwareversion bereits aktuell", log_mode=log_mode)
        return False
    elif version_tuple(new_version) < version_tuple(current_version):
        print("Downgrade nicht erlaubt!")
        show_message("update_9", lang = lang)
        log_schreiben("Downgrade nicht erlaubt", log_mode=log_mode)
        return False
    else:
        print("Update erlaubt!")
        return True


def write_to_fram():

    try:
        write_fram(0x0620, "images_expected".ljust(16))
        write_fram(0x0640, "images_count".ljust(16))
        write_fram(0x0680, "current_Exp_Gain".ljust(16))
        write_fram(0x0790, "Control_Catch".ljust(16))
        write_fram(0x07B0, "Control_End".ljust(16))
        write_fram(0x03A0, "power_mode".ljust(16))
        write_fram(0x0490, "Land".ljust(32))
        write_fram(0x04A0, "Germany".ljust(16))
        write_fram(0x04C0, "Provinz".ljust(16))
        write_fram(0x0600," language".ljust(16))
        write_fram(0x0460, "Zeitumstellung".ljust(16))
        write_fram(0x0560, "new_package".ljust(16))
    except:
        pass    

def ignore_special_files(dir, files):
    ignored = []
    for f in files:
        full_path = os.path.join(dir, f)
        try:
            mode = os.lstat(full_path).st_mode
            if stat.S_ISFIFO(mode) or stat.S_ISSOCK(mode):
                ignored.append(f)
        except Exception:
            pass
    return ignored   

def safe_rmtree(path):
    for root, dirs, files in os.walk(path, topdown=False):
        for name in files:
            file_path = os.path.join(root, name)
            try:
                mode = os.lstat(file_path).st_mode
                if stat.S_ISFIFO(mode) or stat.S_ISSOCK(mode):
                    os.remove(file_path)
                else:
                    os.remove(file_path)
            except Exception:
                pass
        for name in dirs:
            dir_path = os.path.join(root, name)
            try:
                os.rmdir(dir_path)
            except Exception:
                pass
    try:
        os.rmdir(path)
    except Exception:
        pass 



def update(log_mode):
    write_to_fram()
    show_message("update_10", lang = lang)
    log_schreiben("Menü zum Updaten geöffnet", log_mode)
    time.sleep(2)
    if is_valid_update_stick(log_mode) and is_update_allowed(log_mode):
        log_schreiben("Update-Stick ist gültig und Update erlaubt.", log_mode=log_mode)
        try:
            print("Starte LepmonOS Update...")
            show_message("update_11", lang = lang)
            
            # --- Update-Prozess mit Spezialdatei-Behandlung ---
            usb_mount,_ = get_usb_path(log_mode)
            Version = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "software", "version")
            timestamp, _, _ = Zeit_aktualisieren(log_mode)
            update_folder = os.path.join(usb_mount, "LepmonOS_update")
            target_folder = "/home/Ento/LepmonOS"
            backup_folder = target_folder + f"_backup_{Version}__{timestamp}"

            if os.path.exists(update_folder):
                show_message("update_12", lang=lang)
                print("Update-Ordner gefunden. Starte Update...")
                if os.path.exists(backup_folder):
                    safe_rmtree(backup_folder)
                print(f"Sichere aktuelles LepmonOS in {backup_folder}...")
                shutil.copytree(target_folder, backup_folder, ignore=ignore_special_files)
                log_schreiben(f"altes Programm im Ordner {backup_folder} hinterlegt", log_mode=log_mode)
                print("Lösche altes LepmonOS...")
                safe_rmtree(target_folder)
                log_schreiben("alter Programmordner gelöscht", log_mode=log_mode)
                print("Kopiere neues LepmonOS...")
                shutil.copytree(update_folder, target_folder, ignore=ignore_special_files)
                log_schreiben("neue LepmonOS Version geladen", log_mode=log_mode)
                print("lösche Update Ordner vom USB Stick...")
                safe_rmtree(update_folder)
                log_schreiben(f"Update-Ordner {update_folder} vom USB Stick gelöscht", log_mode=log_mode)
                print("Update abgeschlossen")
            else:
                print("Kein Update-Ordner auf USB-Stick gefunden.")
                show_message("update_13", lang=lang)
                log_schreiben("kein Update gefunden", log_mode=log_mode)
                return

            print("Update erfolgreich!")
            write_fram(0x052F,b'\x01') # kontrollbit um HMI neu zu starten
            write_fram_bytes(0x056F , b'\x00') # Kontrollbit um Package Installer zu triggern
            
            show_message("update_14", lang=lang)
            new_version = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "software", "version")
            new_date = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "software", "date")
            show_message("update_15", lang=lang, version = new_version, date= new_date)
            log_schreiben(f"neue Firmwareversion:{new_version}", log_mode=log_mode)
            try:
                write_fram(0x0520, new_version.ljust(7)) 
                write_fram(0x0510, new_date.ljust(10))
                print("Version im FRAM aktualisiert.")
            except Exception as e:
                pass
            show_message("update_16", lang=lang)
            log_schreiben("##################################", log_mode=log_mode)
            log_schreiben("### SELBSTINDUZIERTER SHUTDOWN ###", log_mode=log_mode)
            log_schreiben("##################################", log_mode=log_mode)
            trap_shutdown(log_mode, 5)
            time.sleep(1)
            os.system("sudo reboot now")

        except Exception as e:
            print(f"Fehler beim Update: {e}")
            show_message("update_17", lang=lang)
            log_schreiben(f"Fehler beim update:{e}")
            return
    else:
        print("Update nicht erlaubt oder kein gültiger Update-Stick gefunden.")
        log_schreiben("Update nicht erlaubt oder kein gültiger Update-Stick gefunden.", log_mode=log_mode)


if __name__ == "__main__":
    update(log_mode="manual")
                