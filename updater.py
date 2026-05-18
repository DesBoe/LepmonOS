import shutil
import os
from service import get_usb_path
from times import Zeit_aktualisieren
import subprocess
from fram_direct import *
from OLED_panel import *
import time
from json_read_write import *
from logging_utils import log_schreiben
from end import trap_shutdown
import stat
from language import get_language
from hardware import *

lang = get_language()        
log_dict = {}        


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
    log_schreiben(f"gefundenes USB-Laufwerk: {usb_mount}", log_mode=log_mode)
    version_file = os.path.join(usb_mount, "version.txt")
    if not os.path.exists(version_file):
        log_schreiben("version.txt auf dem Stick nicht gefunden", log_mode=log_mode)
        return None
    with open(version_file, "r") as f:
        return f.read().strip()
    
def get_current_version(log_mode):
    # Lies die aktuelle Version aus dem FRAM (als String)
    try:
        current_version = read_fram(0x0520, 5)
    except Exception as e:
        current_version = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "software", "version")
    if current_version:
        log_schreiben(f"Aktuelle Version aus FRAM gelesen: {current_version.strip()}", log_mode=log_mode)
        return current_version.strip()
    log_schreiben("Konnte aktuelle Version nicht lesen", log_mode=log_mode)
    return None

def version_tuple(version_str, log_mode):
    try:
        return tuple(map(int, version_str.strip().split(".")))
    except Exception:
        log_schreiben(f"Ungültiges Versionsformat: {version_str}", log_mode=log_mode)
        log_schreiben("wende Fallback-Version (1.2.3) an", log_mode=log_mode)
        return (1,2, 3)

def is_update_allowed(log_mode):
    new_version = get_new_version_from_stick(log_mode)
    current_version = get_current_version(log_mode)
    if not new_version or not current_version:
        print("Konnte Version nicht lesen.")
        show_message("update_7", lang = lang)
        log_schreiben("neue Version nicht gefunden",2, log_mode=log_mode)
        return False
    if version_tuple(new_version, log_mode) == version_tuple(current_version, log_mode):
        show_message("update_8", lang = lang)
        log_schreiben("Firmwareversion bereits aktuell", log_mode=log_mode)
        return False
    elif version_tuple(new_version, log_mode) < version_tuple(current_version, log_mode):
        show_message("update_9", lang = lang)
        log_schreiben("Downgrade nicht erlaubt", log_mode=log_mode)
        return False
    else:
        print("Update erlaubt!")
        return True


def write_to_fram():
    camera = get_device_info("camera")
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
        if camera == "RPI_Module_3":
            write_fram_bytes(0x078F, b'\x01') # Fokusieren bei RPI Module 3 erzwingen

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

def safe_rmtree(path, log_mode):
    for root, dirs, files in os.walk(path, topdown=False):
        for name in files:
            file_path = os.path.join(root, name)
            try:
                mode = os.lstat(file_path).st_mode
                if stat.S_ISFIFO(mode) or stat.S_ISSOCK(mode):
                    os.remove(file_path)
                else:
                    os.remove(file_path)
            except Exception as e:
                log_dict["safe_rmtree_1"] = f"Fehler bei safe_rmtree_files: {e}"
                pass
        for name in dirs:
            dir_path = os.path.join(root, name)
            try:
                os.rmdir(dir_path)
            except Exception as e:
                log_dict["safe_rmtree_2"] = f"Fehler bei safe_rmtree_dirs: {e}"
                pass
    try:
        os.rmdir(path)
    except Exception as e:
        log_dict["safe_rmtree_3"] = f"Fehler bei safe_rmtree: {e}"
        pass 



def update(log_mode, execution="full"):
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
                
                print("prüfe, ob der Backup-Ordner bereits existiert...")
                if os.path.exists(backup_folder):
                    print("Backup-Ordner existiert bereits. Lösche Backup-Ordner...")
                    safe_rmtree(backup_folder, log_mode=log_mode)
                
                print(f"Sichere aktuellen LepmonOS Ordner in {backup_folder}...")
                try:
                    shutil.copytree(target_folder, backup_folder, ignore=ignore_special_files)
                    log_schreiben(f"altes Programm im Ordner {backup_folder} hinterlegt", log_mode=log_mode)
                except Exception as e:
                    log_schreiben(f"Fehler beim Sichern des alten LepmonOS: {e}", log_mode=log_mode)

                print("frage alten logging path, GPS, und SN ab...")
                old_log_path = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "current_log")
                sn = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "serielnumber")
                hardware_version = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "ARNI_Gen")
                latitude = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "GPS", "latitude")
                longitude = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "GPS", "longitude")
                Pol = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "GPS", "Pol")
                Block = get_value_from_section("/home/Ento/LepmonOS/Lepmon_config.json", "GPS", "Block")
                print(f"alter logging path: {old_log_path}")
                print(f"serielnumber: {sn}")
                print(f"hardware_version: {hardware_version}")
                print(f"latitude: {latitude}")
                print(f"longitude: {longitude}")
                print(f"Pol: {Pol}")
                print(f"Block: {Block}")

                print("lösche alten LepmonOS Ordner...")
                try:
                    safe_rmtree(target_folder, log_mode=log_mode)
                    log_dict["folder_delete_1"] = "alter Programmordner erfolgreich gelöscht"
                except Exception as e:
                    log_dict["folder_delete_2"] = f"Fehler beim Löschen des alten LepmonOS: {e}"
                
                print("Kopiere neues LepmonOS...")
                try:
                    shutil.copytree(update_folder, target_folder, ignore=ignore_special_files)
                    log_dict["folder_copy_1"] = "neue LepmonOS Version erfolgreich geladen"
                except Exception as e:
                    log_dict["folder_copy_2"] = f"Fehler beim Kopieren des neuen LepmonOS: {e}"

                print("setze logging path und andere Werte im neuen LepmonOS auf alten Werte...")
                write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "current_log", old_log_path)
                write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "serielnumber", sn)
                write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "general", "ARNI_Gen", hardware_version)
                write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "GPS", "latitude", latitude)
                write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "GPS", "longitude", longitude)
                write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "GPS", "Pol", Pol)
                write_value_to_section("/home/Ento/LepmonOS/Lepmon_config.json", "GPS", "Block", Block)
                log_dict["logging_path_1"] = f"logging path und Geräteinformationen im neuer Config auf alte Werte gesetzt"
                print("schreibe Logeinträge aus dem Update-Prozess in das Log...")
                print(log_dict)
                for key, value in log_dict.items():
                    try:
                        log_schreiben(value, log_mode=log_mode)
                    except Exception as e:
                        print(f"Fehler beim Schreiben des Logeintrags {key}: {e}")


                print("lösche Update Ordner vom USB Stick...")
                try:
                    safe_rmtree(update_folder, log_mode=log_mode)
                    log_schreiben(f"Update-Ordner {update_folder} vom USB Stick gelöscht", log_mode=log_mode)
                except Exception as e:
                    log_schreiben(f"Fehler beim Löschen des Update-Ordners: {e}", log_mode=log_mode)
                print("############\nUpdate abgeschlossen\n############")
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
            log_schreiben(f"Update erfolgreich abgeschlossen. Neue Firmwareversion:{new_version}", log_mode=log_mode)
            log_schreiben("leite Neustart ein, um Update abzuschließen", log_mode=log_mode)
            try:
                write_fram(0x0520, new_version.ljust(7)) 
                write_fram(0x0510, new_date.ljust(10))
                print("Version im FRAM aktualisiert.")
            except Exception as e:
                pass
            show_message("update_16", lang=lang)
            trap_shutdown(5,log_mode, execution=execution)
            time.sleep(1)
            os.system("sudo reboot now")
            show_message("blank", lang=lang)
            time.sleep(10)

        except Exception as e:
            print(f"Fehler beim Update: {e}")
            show_message("update_17", lang=lang)
            log_schreiben(f"Fehler beim update:{e}", log_mode=log_mode)
            return
    else:
        log_schreiben("Update nicht erlaubt oder kein gültiger Update-Stick gefunden.", log_mode=log_mode)


if __name__ == "__main__":
    update(log_mode="manual", execution="anzeige")